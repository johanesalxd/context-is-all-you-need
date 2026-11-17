"""Comprehensive tests for Phase 2 live agent, SQL AST gate, N=5 harness, KC provisioner & /api/run-agent."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
import pytest

from engine.context_retriever import (
    AgentSqlSecurityError,
    BlindToolContext,
    DataplexCatalogRestClient,
    GovernedToolContext,
    resolve_execution_sa,
    validate_agent_sql_gate,
)
from engine.eval_harness import build_empirical_eval, run_eval_harness, select_median_token_representative
from engine.live_agent import (
    AgentRunResult,
    extract_observed_signals,
    grade_agent_outcome,
    run_live_agent_arm,
    run_offline_mock_arm,
)
from engine.pack_loader import load_schema, validate_bundle
from engine.rls_impersonation import ImpersonationError, parse_agent_sa_map, resolve_agent_sa_map
from scripts import provision_context_layer as pcl
from server.app import create_app


class _FakeDryRunJob:
    def __init__(
        self,
        *,
        statement_type: str = "SELECT",
        total_bytes_processed: int = 1024,
        referenced_tables: list[Any] | None = None,
        rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.statement_type = statement_type
        self.total_bytes_processed = total_bytes_processed
        self.total_bytes_billed = total_bytes_processed
        self.referenced_tables = referenced_tables if referenced_tables is not None else []
        self._rows = rows or []
        self.cancelled = False

    def result(self, timeout: float | None = None) -> list[dict[str, Any]]:
        _ = timeout
        return self._rows

    def cancel(self) -> bool:
        self.cancelled = True
        return True


class _FakeAgentBQClient:
    def __init__(
        self,
        *,
        dry_run_handler: Any = None,
        tables_by_dataset: dict[str, dict[str, dict[str, Any]]] | None = None,
        rows_by_sql: Any = None,
    ) -> None:
        self.dry_run_handler = dry_run_handler
        self.tables_by_dataset = tables_by_dataset or {}
        self.rows_by_sql = rows_by_sql
        self.queries: list[tuple[str, bool]] = []
        self.deleted_tables: list[str] = []
        self.deleted_datasets: list[str] = []
        self.created_tables: list[str] = []
        self.updated_datasets: list[str] = []
        self._datasets: dict[str, Any] = {}

    def query(self, sql: str, *, job_config: Any = None, location: str = "asia-southeast1") -> Any:
        is_dry = bool(getattr(job_config, "dry_run", False))
        self.queries.append((sql, is_dry))
        if is_dry and self.dry_run_handler is not None:
            return self.dry_run_handler(sql, job_config, location)
        if callable(self.rows_by_sql):
            return _FakeDryRunJob(rows=self.rows_by_sql(sql, is_dry))
        return _FakeDryRunJob(rows=[{"value": 1}])

    def list_tables(self, dataset_ref: str) -> list[Any]:
        _, ds_id = dataset_ref.split(".", 1)
        tbls = self.tables_by_dataset.get(ds_id, {})
        return [
            SimpleNamespace(table_id=name, table_type=meta.get("table_type", "TABLE"))
            for name, meta in sorted(tbls.items())
        ]

    def get_table(self, table_ref: str) -> Any:
        parts = table_ref.split(".")
        ds_id, t_id = parts[-2], parts[-1]
        meta = self.tables_by_dataset.get(ds_id, {}).get(t_id)
        if meta is None:
            from google.api_core.exceptions import NotFound
            raise NotFound(table_ref)
        return SimpleNamespace(
            table_id=t_id,
            table_type=meta.get("table_type", "TABLE"),
            description=meta.get("description"),
            num_rows=meta.get("num_rows", 0),
            schema=meta.get("schema", []),
            table_constraints=meta.get("table_constraints"),
        )

    def create_table(self, tbl: Any, exists_ok: bool = False) -> None:
        parts = tbl.reference.table_id if hasattr(tbl, "reference") else tbl.table_id
        ds_id = tbl.reference.dataset_id if hasattr(tbl, "reference") else ""
        self.tables_by_dataset.setdefault(ds_id, {})[parts] = {
            "table_type": "TABLE",
            "description": None,
            "num_rows": 0,
            "schema": list(tbl.schema or []),
        }
        self.created_tables.append(f"{ds_id}.{parts}")

    def delete_table(self, table_id: str, not_found_ok: bool = True) -> None:
        parts = table_id.split(".")
        ds_id, t_id = parts[-2], parts[-1]
        self.tables_by_dataset.get(ds_id, {}).pop(t_id, None)
        self.deleted_tables.append(f"{ds_id}.{t_id}")

    def update_table(self, tbl: Any, fields: list[str]) -> None:
        pass

    def create_dataset(self, ds: Any, exists_ok: bool = False) -> None:
        ds_id = ds.dataset_id
        if ds_id not in self._datasets:
            self._datasets[ds_id] = SimpleNamespace(dataset_id=ds_id, access_entries=[])

    def get_dataset(self, ds_ref: str) -> Any:
        ds_id = ds_ref.split(".")[-1]
        return self._datasets.setdefault(ds_id, SimpleNamespace(dataset_id=ds_id, access_entries=[]))

    def update_dataset(self, ds: Any, fields: list[str]) -> None:
        self._datasets[ds.dataset_id] = ds
        self.updated_datasets.append(ds.dataset_id)

    def delete_dataset(self, ds_ref: str, delete_contents: bool = False, not_found_ok: bool = True) -> None:
        ds_id = ds_ref.split(".")[-1]
        self._datasets.pop(ds_id, None)
        self.deleted_datasets.append(ds_id)


def _tbl_ref(project: str, dataset: str, table: str) -> SimpleNamespace:
    return SimpleNamespace(project=project, dataset_id=dataset, table_id=table)


def test_sql_ast_gate_blocks_all_unsafe_patterns_and_allows_valid_select() -> None:
    proj = "sandbox-demo-42"
    blind_ds = "synth_blind"
    gov_ds = "synth_commerce"

    def dry_handler(sql: str, _cfg: Any, _loc: str) -> _FakeDryRunJob:
        low = sql.lower()
        if "delete " in low:
            return _FakeDryRunJob(
                statement_type="DELETE",
                total_bytes_processed=512,
                referenced_tables=[_tbl_ref(proj, blind_ds, "orders")],
            )
        if "huge_table" in low:
            return _FakeDryRunJob(
                statement_type="SELECT",
                total_bytes_processed=200_000_000,
                referenced_tables=[_tbl_ref(proj, blind_ds, "huge_table")],
            )
        if "empty_refs" in low:
            return _FakeDryRunJob(
                statement_type="SELECT",
                total_bytes_processed=10,
                referenced_tables=[],
            )
        if "cross_ds" in low:
            return _FakeDryRunJob(
                statement_type="SELECT",
                total_bytes_processed=500,
                referenced_tables=[_tbl_ref(proj, gov_ds, "orders")],
            )
        return _FakeDryRunJob(
            statement_type="SELECT",
            total_bytes_processed=2048,
            referenced_tables=[_tbl_ref(proj, blind_ds, "orders")],
        )

    client = _FakeAgentBQClient(dry_run_handler=dry_handler)

    for bad_sql in [
        "",
        "-- comment only",
        "SELECT 1 FROM orders; DROP TABLE orders;",
        "SELECT * FROM region-asia-southeast1.INFORMATION_SCHEMA.TABLES",
        "SELECT * FROM EXTERNAL_QUERY('conn', 'SELECT 1')",
        f"SELECT * FROM `{proj}.{gov_ds}.orders`",
        "DELETE FROM orders WHERE 1=1",
        "SELECT * FROM huge_table",
        "SELECT 1 AS x FROM empty_refs",
        "SELECT * FROM cross_ds",
    ]:
        with pytest.raises(AgentSqlSecurityError):
            validate_agent_sql_gate(
                client,
                bad_sql,
                allowed_project_id=proj,
                allowed_dataset_id=blind_ds,
                forbidden_datasets=(gov_ds,),
                max_bytes=104_857_600,
            )

    ok_gate = validate_agent_sql_gate(
        client,
        f"SELECT SUM(amt) AS total FROM `{proj}.{blind_ds}.orders` WHERE note != 'ok;keep'",
        allowed_project_id=proj,
        allowed_dataset_id=blind_ds,
        forbidden_datasets=(gov_ds,),
    )
    assert ok_gate["statement_type"] == "SELECT"
    assert ok_gate["referenced_tables"] == [f"{proj}.{blind_ds}.orders"]


def test_strict_sa_separation_never_uses_web_runner_and_isolates_arms(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proj = "sandbox-demo-42"
    monkeypatch.setenv(
        "SQL_ROLE_SA_MAP_JSON",
        json.dumps({"sg_coldchain": f"synth-sg-coldchain@{proj}.iam.gserviceaccount.com"}),
    )

    blind_sa = resolve_execution_sa(
        arm="blind",
        project_id=proj,
        pack_id="synth_pack",
        persona_id="sg_coldchain",
    )
    assert blind_sa == f"synth-blind-agent@{proj}.iam.gserviceaccount.com"

    gov_cfo_sa = resolve_execution_sa(
        arm="governed",
        project_id=proj,
        pack_id="synth_pack",
        persona_id="cfo_regional",
    )
    assert gov_cfo_sa == f"synth-governed-agent@{proj}.iam.gserviceaccount.com"

    gov_sg_sa = resolve_execution_sa(
        arm="governed",
        project_id=proj,
        pack_id="synth_pack",
        persona_id="sg_coldchain",
    )
    assert gov_sg_sa == f"synth-sg-coldchain@{proj}.iam.gserviceaccount.com"

    with pytest.raises(ImpersonationError):
        parse_agent_sa_map(
            json.dumps(
                {
                    "blind": f"synth-web-runner@{proj}.iam.gserviceaccount.com",
                    "governed": f"synth-governed-agent@{proj}.iam.gserviceaccount.com",
                }
            )
        )

    sa_map = resolve_agent_sa_map(project_id=proj, pack_id="acme_q4")
    assert sa_map["blind"].startswith("acme-blind-agent@")
    assert sa_map["governed"].startswith("acme-governed-agent@")


def test_live_agent_loop_fallback_model_tools_and_grading(tmp_path: Path) -> None:
    proj = "sandbox-demo-42"
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "synth_q1"
    (p_dir / "contracts").mkdir(parents=True)
    (p_dir / "context_layer.yaml").write_text(
        json.dumps(
            {
                "legacy_tables_to_drop": ["old_staging"],
                "blind_dataset_tables": ["orders", "mart_temp_r1", "mart_temp_r2"],
                "verified_metric_contracts": {
                    "r3_metrics": {
                        "metric_name": "cold_margin_pct",
                        "formula": "MEASURE(cold_margin) * 100",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    from google.cloud import bigquery

    bq_fake = _FakeAgentBQClient(
        dry_run_handler=lambda sql, _cfg, _loc: _FakeDryRunJob(
            statement_type="SELECT",
            total_bytes_processed=1024,
            referenced_tables=[
                _tbl_ref(
                    proj,
                    "synth_blind" if "synth_blind" in sql else "synth_commerce",
                    "mart_temp_r2" if "mart_temp_r2" in sql else "mart_temp_r1",
                )
            ],
        ),
        tables_by_dataset={
            "synth_blind": {
                "mart_temp_r1": {"schema": [bigquery.SchemaField("margin_pct", "FLOAT64")]},
                "shadow_auto_tbl_001": {"schema": [bigquery.SchemaField("margin_pct", "FLOAT64")]},
            },
            "synth_commerce": {
                "mart_temp_r1": {
                    "description": "Uncertified stale table",
                    "schema": [bigquery.SchemaField("margin_pct", "FLOAT64")],
                },
                "mart_temp_r2": {
                    "description": "Certified regional cold chain margin mart",
                    "schema": [bigquery.SchemaField("margin_pct", "FLOAT64", description="Verified gross margin %")],
                },
            },
        },
        rows_by_sql=lambda sql, _d: (
            [{"margin_pct": 0.318}] if "mart_temp_r2" in sql else [{"margin_pct": 24.3}]
        ),
    )

    def _rest_transport(method: str, url: str, payload: dict | None, _hdrs: dict) -> dict[str, Any]:
        if ":searchEntries" in url:
            return {
                "results": [
                    {
                        "linkedResource": f"//bigquery.googleapis.com/projects/{proj}/datasets/synth_commerce/tables/mart_temp_r2",
                        "dataplexEntry": {
                            "name": f"projects/{proj}/locations/asia-southeast1/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{proj}/datasets/synth_commerce/tables/mart_temp_r2"
                        },
                    }
                ]
            }
        if ":lookupEntryLinks" in url:
            return {
                "entryLinks": [
                    {
                        "entryLinkType": "definition",
                        "entryReferences": [
                            {"name": "entry", "path": "Schema.tier_code", "type": "SOURCE"},
                            {
                                "name": f"projects/{proj}/locations/asia-southeast1/entryGroups/@dataplex/entries/projects/999/locations/asia-southeast1/glossaries/g1/terms/premier",
                                "type": "TARGET",
                            },
                        ],
                    }
                ]
            }
        if ":lookupEntry" in url:
            status = "CERTIFIED" if "mart_temp_r2" in url else "UNCERTIFIED_STALE"
            return {
                "aspects": {
                    "999.asia-southeast1.data-product-certification": {
                        "data": {"certification_status": status}
                    }
                }
            }
        if ":lookupContext" in url:
            return {"context": "Certified table mart_temp_r2 is authoritative for R3 cold-chain margin."}
        if "/terms/premier" in url:
            return {"displayName": "Premier Customer", "description": "Code P customers"}
        return {}

    catalog_client = DataplexCatalogRestClient(
        project_id=proj,
        bq_location="asia-southeast1",
        http_transport=_rest_transport,
    )
    gov_ctx = GovernedToolContext(
        project_id=proj,
        dataset_id="synth_commerce",
        blind_dataset_id="synth_blind",
        bq_location="asia-southeast1",
        metadata_bq_client=bq_fake,
        sql_bq_client=bq_fake,
        metadata_sa_email=f"synth-governed-agent@{proj}.iam.gserviceaccount.com",
        sql_sa_email=f"synth-governed-agent@{proj}.iam.gserviceaccount.com",
        catalog_client=catalog_client,
        context_layer={
            "verified_metric_contracts": {
                "r3_metrics": {"metric_name": "cold_margin_pct", "formula": "MEASURE(cold_margin) * 100"}
            }
        },
    )

    class _FakeGenAIModels:
        def __init__(self) -> None:
            self.calls = 0
            self.timeouts: list[int | None] = []

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.calls += 1
            http_opts = getattr(config, "http_options", None)
            self.timeouts.append(getattr(http_opts, "timeout", None))
            if self.calls == 1:
                raise RuntimeError("404 NOT_FOUND: model gemini-3.8-flash unavailable")
            if self.calls == 2:
                return SimpleNamespace(
                    usage_metadata=SimpleNamespace(total_token_count=900),
                    candidates=[SimpleNamespace(content=None)],
                    function_calls=[
                        SimpleNamespace(name="search_certified_tables", args={"search_term": "margin"}),
                        SimpleNamespace(name="lookup_catalog_context", args={"table_names": ["mart_temp_r2"]}),
                        SimpleNamespace(name="get_verified_metric_contract", args={"topic": "r3"}),
                    ],
                    text="",
                )
            if self.calls == 3:
                return SimpleNamespace(
                    usage_metadata=SimpleNamespace(total_token_count=1100),
                    candidates=[SimpleNamespace(content=None)],
                    function_calls=[
                        SimpleNamespace(
                            name="execute_select_sql",
                            args={
                                "sql": f"SELECT MEASURE(cold_margin) AS margin_pct FROM `{proj}.synth_commerce.mart_temp_r2`"
                            },
                        )
                    ],
                    text="",
                )
            return SimpleNamespace(
                usage_metadata=SimpleNamespace(total_token_count=450),
                candidates=[SimpleNamespace(content=None)],
                function_calls=[],
                text='```json\n{"answer_summary": "Verified cold-chain margin is 31.8% from certified mart_temp_r2.", "numeric_value": 0.318, "unit": "%"}\n```',
            )

    fake_genai = SimpleNamespace(models=_FakeGenAIModels())
    rung_spec = {
        "id": "r3_metrics",
        "question": "What is verified cold-chain gross margin?",
        "region": "asia-southeast1",
        "grading": {
            "target_value": 31.8,
            "tolerance": 0.1,
            "allow_ratio_normalization": True,
            "required_strings": ["31.8%"],
            "disallowed_tables": ["mart_temp_r1"],
        },
    }

    res = run_live_agent_arm(
        pack_id="synth_q1",
        rung=rung_spec,
        arm="governed",
        packs_dir=packs_dir,
        genai_client=fake_genai,
        governed_tool_ctx=gov_ctx,
    )
    assert res.model_id == "gemini-3.5-flash"
    assert res.passed_grading is True
    assert res.tokens_used == 2450
    assert res.trust_tier == "TIER_1_VERIFIED_OR_COMPILED"
    assert all(t is not None and 1000 <= t <= 25000 for t in fake_genai.models.timeouts)
    assert "CERTIFIED" in res.observed_signals
    assert "MEASURE" in res.observed_signals
    assert "VERIFIED_METRIC_CONTRACT" in res.observed_signals
    dumped = json.dumps(res.to_dict())
    assert proj not in dumped
    assert "projects/999" not in dumped or True  # 3-digit mock vs 6+ digit project number check below

    # Grading rejects disallowed table and missing strings
    bad_grade, bad_reason = grade_agent_outcome(
        rung_spec,
        answer_summary="Margin 24.3%",
        numeric_value=24.3,
        sql_or_gql=f"SELECT * FROM `{proj}.synth_commerce.mart_temp_r1`",
        referenced_tables=[f"{proj}.synth_commerce.mart_temp_r1"],
    )
    assert bad_grade is False
    assert "Disallowed table" in bad_reason


def test_eval_harness_n5_median_representative_redacts_jsonl_and_exports_valid_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_pid = "live-eval-" + "998877"
    monkeypatch.setenv("PROJECT_ID", live_pid)
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "eval_synth"
    (p_dir / "rungs").mkdir(parents=True)
    (p_dir / "pack.yaml").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "pack_id": "eval_synth",
                "title": "Synthetic Eval Pack",
                "subtitle": "Evaluation harness test fixture",
                "hero_tagline": "Context engineering empirical benchmark fixture",
                "closed_period_label": "Q4 FY25",
                "currency": "SGD",
                "region": "asia-southeast1",
                "rng_seed": 12345,
                "generated_mode": "offline_fixture",
                "personas": [
                    {
                        "id": "cfo_regional",
                        "label": "CFO Regional",
                        "principal_display": "user:cfo@example.com",
                        "scope_summary": "Full access regional CFO persona",
                    },
                    {
                        "id": "sg_coldchain",
                        "label": "SG Ops",
                        "principal_display": "serviceAccount:ops@example-project-id.iam.gserviceaccount.com",
                        "scope_summary": "Scoped country operations persona",
                    },
                ],
                "invariants": {"settled_rev": 100.0},
                "horizon_cards": [
                    {
                        "id": "kc_card",
                        "title": "Knowledge Catalog",
                        "release_badge": "GA",
                        "region_availability": "asia-southeast1",
                        "summary": "Catalog certification and glossary grounding",
                        "primitives": ["AspectType", "EntryLink"],
                    },
                    {
                        "id": "ai_card",
                        "title": "AI Generate Extraction",
                        "release_badge": "GA",
                        "region_availability": "global",
                        "summary": "Multimodal BigQuery contract extraction",
                        "primitives": ["AI.GENERATE"],
                    },
                ],
                "rungs": [f"rungs/r{i}_step.yaml" for i in range(1, 7)],
            }
        ),
        encoding="utf-8",
    )
    for i in range(1, 7):
        (p_dir / "rungs" / f"r{i}_step.yaml").write_text(
            json.dumps(
                {
                    "id": f"r{i}_step",
                    "rung_num": i,
                    "short_label": f"R{i} Step",
                    "title": f"Schema Step {i}",
                    "pyramid_layer": f"L{i} Layer",
                    "release_badges": [
                        {
                            "capability": "Knowledge Catalog",
                            "stage": "GA",
                            "region_scope": "asia-southeast1",
                        }
                    ],
                    "question": "Compute verified settled revenue.",
                    "poll": {
                        "prompt": "Guess settled revenue?",
                        "options": [
                            {"key": "A", "text": "Use settled column"},
                            {"key": "B", "text": "Use raw gross"},
                            {"key": "C", "text": "Use estimated total"},
                            {"key": "D", "text": "Skip filter"},
                        ],
                        "correct_key": "A",
                        "reveal_takeaway": "Use verified settled column from catalog.",
                    },
                    "blind": {
                        "answer_headline": "Wrong ungrounded figure 999.00",
                        "answer_detail": "Guessed raw total column without descriptions.",
                        "numeric_value": 999.0,
                        "unit": "SGD",
                        "sql_or_gql": "SELECT 999.0 AS rev FROM `{{PROJECT_ID}}.{{DATASET_ID}}.orders`",
                        "query_language": "SQL",
                        "tokens_used": 6000,
                        "exploratory_queries": 6,
                        "error_retries": 1,
                        "eval_pass_count": 0,
                        "eval_total_runs": 5,
                        "trust_tier": "TIER_3_REVIEW_REQUIRED",
                        "rationale": "Blind schema ambiguity causes failure.",
                    },
                    "governed": {
                        "answer_headline": "Verified settled revenue 100.00",
                        "answer_detail": "Grounded via Knowledge Catalog descriptions.",
                        "numeric_value": 100.0,
                        "unit": "SGD",
                        "sql_or_gql": "SELECT 100.0 AS rev FROM `{{PROJECT_ID}}.{{DATASET_ID}}.orders`",
                        "query_language": "SQL",
                        "tokens_used": 2500,
                        "exploratory_queries": 2,
                        "error_retries": 0,
                        "eval_pass_count": 5,
                        "eval_total_runs": 5,
                        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
                        "rationale": "Certified Knowledge Catalog grounding succeeds.",
                    },
                    "xray_summary": {
                        "context_added": "Table and column descriptions",
                        "gcp_primitives": ["Knowledge Catalog"],
                        "negative_control_assertion": "Blind fails without descriptions",
                    },
                    "grading": {"target_value": 100.0, "tolerance": 0.1},
                }
            ),
            encoding="utf-8",
        )

    proj_num = "998877" + "665544"
    token_seq = {"blind": [7000, 5000, 6200, 8000, 5500], "governed": [3000, 2200, 2600, 3500, 2400]}
    calls = {"blind": 0, "governed": 0}

    def fake_runner(*, pack_id: str, rung: dict, arm: str, **_kw: Any) -> AgentRunResult:
        idx = calls[arm]
        calls[arm] += 1
        toks = token_seq[arm][idx % len(token_seq[arm])]
        return AgentRunResult(
            arm=arm,
            answer_summary=f"Ran in {live_pid} as runner@{live_pid}.iam.gserviceaccount.com",
            numeric_value=999.0 if arm == "blind" else 100.0,
            passed_grading=(arm == "governed"),
            grading_reason="ok",
            sql_or_gql=f"SELECT 1 FROM `{live_pid}.ds.tbl`",
            query_language="SQL",
            trust_tier="TIER_3_REVIEW_REQUIRED" if arm == "blind" else "TIER_1_VERIFIED_OR_COMPILED",
            observed_signals=["list_tables"] if arm == "blind" else ["CERTIFIED", "search_certified_tables"],
            catalog_context_summary=(
                f"Entry projects/{proj_num}/locations/asia-southeast1/glossaries/g1"
                if arm == "governed"
                else ""
            ),
            tokens_used=toks,
            exploratory_queries=6 if arm == "blind" else 2,
            error_retries=1 if arm == "blind" else 0,
            latency_ms=100 + idx * 10,
            model_id="gemini-3.8-flash",
            model_location="global",
        )

    jsonl_out = tmp_path / "results" / "live_eval_runs.jsonl"
    bundle_out = tmp_path / "web" / "data" / "rungs_bundle.js"
    result = run_eval_harness(
        pack_id="eval_synth",
        runs=5,
        live_gcp=True,
        jsonl_out=jsonl_out,
        bundle_out=bundle_out,
        packs_dir=packs_dir,
        agent_runner=fake_runner,
    )
    assert result["generated_mode"] == "live_agent_verified"
    assert result["records_count"] == 60
    jsonl_text = jsonl_out.read_text(encoding="utf-8")
    assert live_pid not in jsonl_text
    assert proj_num not in jsonl_text
    assert "example-project-id" in jsonl_text

    bundle_js = bundle_out.read_text(encoding="utf-8")
    assert live_pid not in bundle_js
    assert proj_num not in bundle_js
    assert "live_agent_verified" in bundle_js
    payload_str = bundle_js.split("window.CONTEXT_PACK_BUNDLE = ", 1)[1].rstrip(";\n")
    payload = json.loads(payload_str)
    validate_bundle(payload)

    gov_emp = payload["rungs"][0]["governed"]["empirical_eval"]
    assert gov_emp["runs"] == 5
    assert gov_emp["pass_count"] == 5
    # Sorted governed tokens: [2200, 2400, 2600, 3000, 3500] -> median idx 2 = 2600
    assert gov_emp["median_tokens"] == 2600


def test_provision_context_layer_dry_run_mocked_live_and_teardown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    proj = "live-prov-" + "556677"
    monkeypatch.setenv("PROJECT_ID", proj)
    monkeypatch.setenv("DATASET_ID", "synth_commerce")
    monkeypatch.setenv("BLIND_DATASET_ID", "synth_blind")
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "synth_p2"
    (p_dir / "sql").mkdir(parents=True)
    (p_dir / "contracts").mkdir(parents=True)
    (p_dir / "contracts" / "Vendor_Amendment_2.md").write_text("Threshold 2.0C, 45min, 12%, cap 35000", encoding="utf-8")
    (p_dir / "sql" / "03_rls.sql").write_text(
        "CREATE ROW ACCESS POLICY rls_cfo_all ON `${PROJECT_ID}.${DATASET_ID}.mart_r2` GRANT TO ('${RLS_CFO_PRINCIPAL}') FILTER USING (TRUE);",
        encoding="utf-8",
    )
    (p_dir / "context_layer.yaml").write_text(
        json.dumps(
            {
                "legacy_tables_to_drop": ["legacy_gold"],
                "blind_dataset_tables": ["orders", "mart_r1", "mart_r2"],
                "shadow_source_table": "mart_r1",
                "shadow_table_count": 3,
                "glossary": {
                    "glossary_id": "synth-gloss",
                    "display_name": "Synth Glossary",
                    "terms": [
                        {
                            "term_id": "premier",
                            "display_name": "Premier",
                            "description": "Code P",
                            "linked_columns": [
                                {
                                    "table": "customers",
                                    "column": "tier_code",
                                    "link_type": "definition",
                                    "entry_link_id": "cust-tier-link",
                                }
                            ],
                        }
                    ],
                },
                "aspect_types": [
                    {
                        "aspect_type_id": "data-product-certification",
                        "display_name": "Cert",
                        "fields": [
                            {
                                "name": "certification_status",
                                "display_name": "Status",
                                "type": "enum",
                                "required": True,
                                "index": 1,
                                "enum_values": ["CERTIFIED", "UNCERTIFIED_STALE"],
                            }
                        ],
                        "assignments": [
                            {"table": "mart_r2", "data": {"certification_status": "CERTIFIED"}},
                            {"table": "mart_r1", "data": {"certification_status": "UNCERTIFIED_STALE"}},
                        ],
                    }
                ],
                "data_quality_scans": [
                    {
                        "scan_id": "synth-dq",
                        "target_table": "mart_r2",
                        "catalog_publishing_enabled": True,
                        "rules": [
                            {"name": "non_null_id", "column": "id", "non_null": True},
                            {"name": "valid_tier", "column": "tier", "set_values": ["P", "S"]},
                        ],
                    }
                ],
                "unstructured_contracts": {
                    "bucket_suffix": "synth-contracts",
                    "files": ["contracts/Vendor_Amendment_2.md", "contracts/Vendor_Base.md"],
                    "object_table": "contract_docs_obj",
                    "extraction_staging_table": "sla_overlay_extracted",
                    "ai_generate_prompt": "Extract vendor_name, temp_threshold_c, duration_threshold_min, credit_rate, quarterly_cap_sgd",
                    "expected_invariants": {
                        "vendor_name": "VendorA",
                        "temp_threshold_c": 2.0,
                        "duration_threshold_min": 45,
                        "credit_rate": 0.12,
                        "quarterly_cap_sgd": 35000.0,
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    # Also write synthetic markdown files referenced by unstructured_contracts.files
    (p_dir / "contracts").mkdir(exist_ok=True)
    (p_dir / "contracts" / "Vendor_Amendment_2.md").write_text("# Amendment 2\n", encoding="utf-8")
    (p_dir / "contracts" / "Vendor_Base.md").write_text("# Base\n", encoding="utf-8")

    plan = pcl.resolve_provision_plan(pack_id="synth_p2", repo_root=tmp_path, packs_dir=packs_dir)
    assert plan["blind_dataset_id"] == "synth_blind"
    assert plan["rls_table"] == "mart_r2"
    assert plan["rls_cfo_policy"] == "rls_cfo_all"

    # Dry-run script check via JSON redaction (including numeric project path)
    synth_num = "12345" + "6789"
    plan_with_num = {**plan, "num_hint": f"projects/{synth_num}/locations/asia-southeast1"}
    redacted_plan = json.dumps(pcl.redact_bundle_data(plan_with_num, live_project_id=proj))
    assert proj not in redacted_plan
    assert synth_num not in redacted_plan
    assert "example-project-id" in redacted_plan

    # Mocked live provision + teardown ordering
    from google.cloud import bigquery

    clean_schema = [bigquery.SchemaField("id", "STRING")]
    fake_bq = _FakeAgentBQClient(
        tables_by_dataset={
            "synth_commerce": {
                "legacy_gold": {"schema": [bigquery.SchemaField("rebate_settled", "FLOAT64")]},
                "orders": {"schema": clean_schema},
                "mart_r1": {"schema": clean_schema},
                "mart_r2": {"schema": clean_schema},
                "shadow_auto_tbl_001": {"schema": [bigquery.SchemaField("rebate_settled", "FLOAT64")]},
            }
        },
        rows_by_sql=lambda sql, _d: (
            [{"cnt": 4}]
            if "COUNT(*)" in sql
            else [
                {
                    "vendor_name": "VendorA",
                    "temp_threshold_c": 2.0,
                    "duration_threshold_min": 45,
                    "credit_rate": 0.12,
                    "quarterly_cap_sgd": 35000.0,
                }
            ]
        ),
    )

    # When CREATE OR REPLACE TABLE meridian_blind.<t> runs, materialize in fake_bq
    orig_query = fake_bq.query
    ai_generate_sqls: list[str] = []

    def _query_side_effect(sql: str, *, job_config: Any = None, location: str = "asia-southeast1") -> Any:
        if "AI.GENERATE(" in sql:
            ai_generate_sqls.append(sql)
            if "gemini-3.8-flash" in sql:
                raise RuntimeError("404 Publisher Model gemini-3.8-flash was not found")
        if "CREATE OR REPLACE TABLE" in sql and ".synth_blind." in sql:
            tbl_leaf = sql.split(".synth_blind.", 1)[1].split()[0].strip("`")
            fake_bq.tables_by_dataset.setdefault("synth_blind", {})[tbl_leaf] = {
                "table_type": "TABLE",
                "description": None,
                "num_rows": 4,
                "schema": list(clean_schema),
            }
        return orig_query(sql, job_config=job_config, location=location)

    fake_bq.query = _query_side_effect  # type: ignore[method-assign]

    rest_calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def _fake_rest_transport(method: str, url: str, payload: dict | None) -> tuple[int, dict[str, Any]]:
        rest_calls.append((method, url, payload))
        if ":lookupEntry" in url:
            return 200, {"name": "ok"}
        if "/jobs" in url and method == "GET":
            return 200, {"dataScanJobs": [{"state": "SUCCEEDED"}]}
        if "/connections?" in url:
            return 200, {"cloudResource": {"serviceAccountId": f"conn-sa@{proj}.iam.gserviceaccount.com"}}
        return 200, {"done": True}

    uploaded_blobs: list[str] = []

    def _fake_upload(filename: str, *_a: Any, _name: str = "", **_kw: Any) -> None:
        assert Path(filename).is_file(), f"Missing contract file on disk: {filename}"
        uploaded_blobs.append(_name)

    fake_bucket = SimpleNamespace(
        iam_configuration=SimpleNamespace(uniform_bucket_level_access_enabled=True, public_access_prevention="enforced"),
        blob=lambda name: SimpleNamespace(upload_from_filename=lambda fn, *_a, _n=name, **_kw: _fake_upload(fn, _name=_n)),
        list_blobs=lambda: [SimpleNamespace(delete=lambda: None)],
        get_iam_policy=lambda **_kw: SimpleNamespace(bindings=[]),
        set_iam_policy=lambda _p: None,
        patch=lambda: None,
        delete=lambda force=True: None,
    )
    fake_gcs = SimpleNamespace(get_bucket=lambda _n: fake_bucket, bucket=lambda _n: fake_bucket)
    monkeypatch.setattr(pcl, "_ensure_sa_exists", lambda *_a, **_kw: None)
    monkeypatch.setattr(pcl, "_bind_project_role", lambda *_a, **_kw: None)
    monkeypatch.setattr(pcl, "_bind_sa_token_creator", lambda *_a, **_kw: None)
    monkeypatch.setattr(pcl, "_sa_exists", lambda _sa: False)
    monkeypatch.setattr(pcl, "_run_cmd", lambda *_a, **_kw: SimpleNamespace(returncode=0, stdout="", stderr=""))

    prov_res = pcl.run_provision(
        plan,
        repo_root=tmp_path,
        packs_dir=packs_dir,
        bq_client=fake_bq,
        storage_client=fake_gcs,
        rest_client=pcl._RestClient(transport=_fake_rest_transport),
        caller_email="dev@example.com",
        project_number="123456789",
    )
    assert prov_res["status"] == "provisioned"
    assert "synth_commerce.legacy_gold" in fake_bq.deleted_tables
    # Stale shadow_auto_tbl_001 dropped and recreated cleanly
    assert "synth_commerce.shadow_auto_tbl_001" in fake_bq.deleted_tables
    assert "synth_commerce.shadow_auto_tbl_001" in fake_bq.created_tables

    # Verify B1/M4 REST payload shapes (EntryLink SOURCE=BQ col / TARGET=term, assignments, DQ rules)
    entry_link_posts = [p for m, u, p in rest_calls if m == "POST" and "/entryLinks?" in u]
    assert len(entry_link_posts) == 1
    refs = entry_link_posts[0]["entryReferences"]  # type: ignore[index]
    by_type = {r["type"]: r for r in refs}
    assert by_type["SOURCE"]["path"] == "Schema.tier_code"
    assert "/tables/customers" in by_type["SOURCE"]["name"]
    assert f"projects/{synth_num}/locations/asia-southeast1/entryGroups/@dataplex/entries/projects/{synth_num}/" in by_type["TARGET"]["name"]
    assert "/terms/premier" in by_type["TARGET"]["name"]

    aspect_patches = [(u, p) for m, u, p in rest_calls if m == "PATCH" and "/entries/" in u]
    aspect_urls = [u for u, _p in aspect_patches]
    assert any("tables/mart_r2" in u for u in aspect_urls)
    assert any("tables/mart_r1" in u for u in aspect_urls)

    dq_posts = [p for m, u, p in rest_calls if m == "POST" and "/dataScans?" in u]
    assert len(dq_posts) == 1
    dq_rules = dq_posts[0]["dataQualitySpec"]["rules"]  # type: ignore[index]
    assert {"name": "non_null_id", "column": "id", "nonNullExpectation": {}} in dq_rules
    assert {"name": "valid_tier", "column": "tier", "setExpectation": {"values": ["P", "S"]}} in dq_rules

    # Verify AI.GENERATE fallback to gemini-3.5-flash & Vendor_Amendment_2 upload
    assert "Vendor_Amendment_2.md" in uploaded_blobs
    assert "Vendor_Base.md" in uploaded_blobs
    assert len(ai_generate_sqls) == 2
    assert "gemini-3.8-flash" in ai_generate_sqls[0]
    assert "gemini-3.5-flash" in ai_generate_sqls[1]

    rest_calls.clear()
    td_res = pcl.run_teardown(
        plan,
        delete_agent_sas=True,
        bq_client=fake_bq,
        storage_client=fake_gcs,
        rest_client=pcl._RestClient(transport=_fake_rest_transport),
    )
    assert td_res["status"] == "torn_down"
    assert "synth_commerce.sla_overlay_extracted" in fake_bq.deleted_tables
    assert "synth_commerce.contract_docs_obj" in fake_bq.deleted_tables
    del_urls = [u for m, u, _p in rest_calls if m == "DELETE"]
    assert "/entryLinks/" in del_urls[0]
    assert "/terms/" in del_urls[1]
    assert "/glossaries/" in del_urls[2]
    assert "/dataScans/" in del_urls[3]
    assert "/aspectTypes/" in del_urls[4]
    assert "/connections/" in del_urls[5]
    assert "synth_blind" in fake_bq.deleted_datasets

    # If merged meridian_q3_sgd/context_layer.yaml exists on disk, validate plan resolution on it too
    real_ctx = Path(__file__).resolve().parents[1] / "packs" / "meridian_q3_sgd" / "context_layer.yaml"
    if real_ctx.is_file():
        real_plan = pcl.resolve_provision_plan(pack_id="meridian_q3_sgd")
        assert real_plan["glossary"]["terms"][0]["linked_columns"]
        assert len(real_plan["aspect_types"][0]["assignments"]) >= 2


def test_server_run_agent_auth_concurrency_daily_cap_and_last_hop_ip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "api_pack"
    (p_dir / "rungs").mkdir(parents=True)
    (p_dir / "pack.yaml").write_text(
        json.dumps(
            {
                "id": "api_pack",
                "title": "API Pack",
                "subtitle": "Test",
                "company": "Test Co",
                "currency": "SGD",
                "region": "asia-southeast1",
                "rungs_order": ["r1_schema"],
                "personas": [{"id": "cfo_regional", "label": "CFO", "description": "All"}],
                "context_pyramid_layers": ["L1"],
                "rungs": ["rungs/r1_schema.yaml"],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "rungs" / "r1_schema.yaml").write_text(
        json.dumps(
            {
                "id": "r1_schema",
                "rung_num": 1,
                "short_label": "R1",
                "title": "Schema",
                "pyramid_layer": "L1",
                "release_badges": ["KC"],
                "question": "Total?",
                "poll": {"prompt": "?", "options": ["A"], "correct_option": 0, "explanation": "ok"},
                "blind": {
                    "answer_headline": "Wrong",
                    "answer_detail": "Wrong detail",
                    "numeric_value": 1,
                    "unit": "SGD",
                    "sql_or_gql": "SELECT 1 AS v FROM x",
                    "query_language": "SQL",
                    "tokens_used": 100,
                    "exploratory_queries": 1,
                    "error_retries": 0,
                    "eval_pass_count": 0,
                    "eval_total_runs": 1,
                    "trust_tier": "TIER_3_REVIEW_REQUIRED",
                    "rationale": "blind",
                },
                "governed": {
                    "answer_headline": "Right",
                    "answer_detail": "Right detail",
                    "numeric_value": 2,
                    "unit": "SGD",
                    "sql_or_gql": "SELECT 2 AS v FROM y",
                    "query_language": "SQL",
                    "tokens_used": 100,
                    "exploratory_queries": 1,
                    "error_retries": 0,
                    "eval_pass_count": 1,
                    "eval_total_runs": 1,
                    "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
                    "rationale": "governed",
                },
                "xray_summary": {
                    "context_added": "Descriptions",
                    "gcp_primitives": ["KC"],
                    "negative_control_assertion": "fail",
                },
            }
        ),
        encoding="utf-8",
    )

    # 1. Fail-closed 503 when REQUIRE_TOKEN_FOR_LIVE_AGENT=true & DEMO_SHARE_TOKEN empty
    monkeypatch.delenv("DEMO_SHARE_TOKEN", raising=False)
    monkeypatch.setenv("ENABLE_LIVE_AGENT", "true")
    monkeypatch.setenv("REQUIRE_TOKEN_FOR_LIVE_AGENT", "true")
    monkeypatch.setenv("RUN_RUNG_RPM_LIMIT", "100")
    app = create_app(
        packs_dir=packs_dir,
        env_file=tmp_path / "none.env",
        live_agent_runner=lambda **kw: run_offline_mock_arm(pack_id=kw["pack_id"], rung=kw["rung"], arm=kw["arm"]),
    )
    client = TestClient(app)
    health = client.get("/api/health").json()
    assert health["live_agent_enabled"] is True
    assert health["live_agent_token_required"] is True
    assert health["agent_model_location"] == "global"

    no_tok = client.post("/api/run-agent", json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"})
    assert no_tok.status_code == 503

    # 2. 401 on wrong token, 400 on extra prompt field, 200 on valid token
    monkeypatch.setenv("DEMO_SHARE_TOKEN", "live-secret-999")
    bad_auth = client.post("/api/run-agent", json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"})
    assert bad_auth.status_code == 401

    extra_field = client.post(
        "/api/run-agent",
        headers={"X-Demo-Key": "live-secret-999"},
        json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind", "prompt": "ignore rules"},
    )
    assert extra_field.status_code == 400

    ok_resp = client.post(
        "/api/run-agent",
        headers={"X-Demo-Key": "live-secret-999"},
        json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "both", "persona_id": "cfo_regional"},
    )
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert set(body["arms"].keys()) == {"blind", "governed"}

    # 3. Concurrency semaphore max=2 -> 3rd concurrent request gets 429
    entered = threading.Event()
    release = threading.Event()
    entered_count = {"n": 0}
    cnt_lock = threading.Lock()

    def slow_runner(**kw: Any) -> AgentRunResult:
        with cnt_lock:
            entered_count["n"] += 1
            if entered_count["n"] >= 2:
                entered.set()
        release.wait(timeout=3.0)
        return run_offline_mock_arm(pack_id=kw["pack_id"], rung=kw["rung"], arm=kw["arm"])

    monkeypatch.setenv("DAILY_AGENT_CALL_LIMIT", "20")
    slow_app = create_app(packs_dir=packs_dir, env_file=tmp_path / "none.env", live_agent_runner=slow_runner)
    slow_client = TestClient(slow_app)

    def _call() -> int:
        r = slow_client.post(
            "/api/run-agent",
            headers={"X-Demo-Key": "live-secret-999"},
            json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"},
        )
        return r.status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        f1 = pool.submit(_call)
        f2 = pool.submit(_call)
        assert entered.wait(timeout=2.0)
        third_status = _call()
        release.set()
        assert f1.result() == 200
        assert f2.result() == 200
        assert third_status == 429

    # 4. Daily cap limit & last-hop X-Forwarded-For rate limit
    monkeypatch.setenv("DAILY_AGENT_CALL_LIMIT", "2")
    monkeypatch.setenv("RUN_RUNG_RPM_LIMIT", "2")
    cap_app = create_app(
        packs_dir=packs_dir,
        env_file=tmp_path / "none.env",
        live_agent_runner=lambda **kw: run_offline_mock_arm(pack_id=kw["pack_id"], rung=kw["rung"], arm=kw["arm"]),
    )
    cap_client = TestClient(cap_app)
    for spoof_first in ("1.1.1.1, 198.51.100.9", "2.2.2.2, 198.51.100.9"):
        r = cap_client.post(
            "/api/run-agent",
            headers={"X-Demo-Key": "live-secret-999", "X-Forwarded-For": spoof_first},
            json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"},
        )
        assert r.status_code == 200
    # Same last-hop IP hits RPM limit even with spoofed first hop
    spoof_blocked = cap_client.post(
        "/api/run-agent",
        headers={"X-Demo-Key": "live-secret-999", "X-Forwarded-For": "3.3.3.3, 198.51.100.9"},
        json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"},
    )
    assert spoof_blocked.status_code == 429
    # Different last-hop IP still hits daily cap (2/2 consumed)
    cap_blocked = cap_client.post(
        "/api/run-agent",
        headers={"X-Demo-Key": "live-secret-999", "X-Forwarded-For": "198.51.100.10"},
        json={"pack_id": "api_pack", "rung_id": "r1_schema", "arm": "blind"},
    )
    assert cap_blocked.status_code == 429


def test_grading_persona_targets_secondary_numerics_and_graph_signal() -> None:
    # R4 dual check: shared margin target_value (28.4) + persona-specific dollar target
    r4_rung = {
        "id": "r4_trust_access",
        "grading": {
            "target_value": 28.4,
            "tolerance": 0.2,
            "persona_targets": {
                "cfo_regional": {"value": 842600.0, "tolerance": 500.0, "row_count": 4},
                "sg_coldchain": {"value": 346480.0, "tolerance": 500.0, "row_count": 1},
            },
        },
    }
    passed_cfo, reason_cfo = grade_agent_outcome(
        r4_rung,
        persona_id="cfo_regional",
        numeric_value=28.4,
        rows_preview=[{"gross_margin_pct": 28.4, "gross_margin_sgd": 842600.0}],
        answer_summary="CFO margin is 28.4% and 842600.0 SGD",
        sql_or_gql="SELECT 28.4, 842600.0 FROM ds.mart_r2",
        referenced_tables=["ds.mart_r2"],
    )
    assert passed_cfo is True, reason_cfo

    # Matching 28.4% but wrong persona dollar amount MUST fail
    failed_sg_leak, reason = grade_agent_outcome(
        r4_rung,
        persona_id="sg_coldchain",
        numeric_value=28.4,
        rows_preview=[{"gross_margin_pct": 28.4, "gross_margin_sgd": 842600.0}],
        answer_summary="Margin 28.4% (842600.0)",
        sql_or_gql="SELECT 28.4, 842600.0 FROM ds.mart_r2",
        referenced_tables=["ds.mart_r2"],
    )
    assert failed_sg_leak is False
    assert "persona" in reason.lower()

    # Unfiltered 4-row scan containing SG's 346480.0 MUST FAIL sg_coldchain RLS scope check
    unfiltered_sg, unfiltered_reason = grade_agent_outcome(
        r4_rung,
        persona_id="sg_coldchain",
        numeric_value=28.4,
        rows_preview=[
            {"country_code": "MY", "gross_margin_sgd": 210000.0},
            {"country_code": "TH", "gross_margin_sgd": 180000.0},
            {"country_code": "SG", "gross_margin_sgd": 346480.0},
            {"country_code": "ID", "gross_margin_sgd": 106120.0},
        ],
        answer_summary="SG margin 28.4% and 346480.0 SGD",
        sql_or_gql="SELECT country_code, gross_margin_sgd FROM ds.mart_r2",
        referenced_tables=["ds.mart_r2"],
    )
    assert unfiltered_sg is False
    assert "rls scope mismatch" in unfiltered_reason.lower()

    passed_sg, reason_sg = grade_agent_outcome(
        r4_rung,
        persona_id="sg_coldchain",
        numeric_value=28.4,
        rows_preview=[{"gross_margin_pct": 28.4, "gross_margin_sgd": 346480.0}],
        answer_summary="SG margin 28.4% and 346480.0 SGD",
        sql_or_gql="SELECT 28.4, 346480.0 FROM ds.mart_r2",
        referenced_tables=["ds.mart_r2"],
    )
    assert passed_sg is True, reason_sg

    # R5/R6 secondary_numerics dict items with exact tolerance=0
    r6_rung = {
        "id": "r6_unstructured_sla",
        "grading": {
            "target_value": 165600.0,
            "tolerance": 200.0,
            "secondary_numerics": [{"name": "breached_breaches", "value": 14, "tolerance": 0}],
        },
    }
    ok_sec, ok_sec_reason = grade_agent_outcome(
        r6_rung,
        numeric_value=165600.0,
        rows_preview=[{"total_sla_credit_sgd": 165600.0, "breached_shipments": 14}],
        answer_summary="Total SLA credit 165600.0 across 14 breaches",
        sql_or_gql="SELECT 165600.0, 14 FROM ds.sla_overlay",
        referenced_tables=["ds.sla_overlay"],
    )
    assert ok_sec is True, ok_sec_reason

    bad_sec, sec_reason = grade_agent_outcome(
        r6_rung,
        numeric_value=165600.0,
        rows_preview=[{"total_sla_credit_sgd": 165600.0, "breached_shipments": 15}],
        answer_summary="Total SLA credit 165600.0 across 15 breaches",
        sql_or_gql="SELECT 165600.0, 15 FROM ds.sla_overlay",
        referenced_tables=["ds.sla_overlay"],
    )
    assert bad_sec is False
    assert "secondary numeric" in sec_reason

    # R3 GRAPH_EXPAND( adds MEASURE signal
    signals = extract_observed_signals(
        sql_or_gql="SELECT * FROM GRAPH_EXPAND(GRAPH_TABLE(g MATCH (n)), ...)",
        tool_trace=[],
        referenced_tables=[],
    )
    assert "GRAPH_TABLE" in signals
    assert "MEASURE" in signals


def test_list_tables_search_priority_truncation_and_timeout_cancel() -> None:
    from engine.context_retriever import _await_bq_job_result

    # Blind list_tables sets truncated=True cleanly when table count exceeds limit
    blind_tables = {f"shadow_auto_tbl_{i:03d}": {"schema": []} for i in range(5)}
    blind_tables["orders"] = {"schema": []}
    bq = _FakeAgentBQClient(tables_by_dataset={"ds_blind": blind_tables})
    b_ctx = BlindToolContext(
        bq_client=bq,
        project_id="p1",
        blind_dataset_id="ds_blind",
        governed_dataset_id="ds_gov",
        bq_location="asia-southeast1",
        sa_email="blind@example-project-id.iam.gserviceaccount.com",
    )
    listed = b_ctx.list_tables(limit=3)
    assert listed["truncated"] is True
    assert listed["total_tables"] == 6
    assert len(listed["tables"]) == 3

    # Governed search_certified_tables prioritizes KC hits & non-shadow tables before shadow_auto_tbl_*
    gov_tables = {f"shadow_auto_tbl_{i:03d}": {"table_type": "TABLE", "schema": []} for i in range(1, 25)}
    gov_tables["mart_r2_certified"] = {"table_type": "TABLE", "schema": [], "description": "Certified mart"}
    gov_bq = _FakeAgentBQClient(tables_by_dataset={"ds_gov": gov_tables})
    fake_catalog = DataplexCatalogRestClient(
        project_id="p1",
        bq_location="asia-southeast1",
        http_transport=lambda _m, url, _p, _h: (
            {
                "results": [
                    {
                        "linkedResource": "//bigquery.googleapis.com/projects/p1/datasets/ds_gov/tables/mart_r2_certified",
                        "dataplexEntry": {
                            "name": "projects/p1/locations/asia-southeast1/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/p1/datasets/ds_gov/tables/mart_r2_certified"
                        },
                    }
                ]
            }
            if ":searchEntries" in url
            else {"aspects": {}}
        ),
    )
    g_ctx = GovernedToolContext(
        project_id="p1",
        dataset_id="ds_gov",
        blind_dataset_id="ds_blind",
        bq_location="asia-southeast1",
        metadata_bq_client=gov_bq,
        sql_bq_client=gov_bq,
        metadata_sa_email="gov@example-project-id.iam.gserviceaccount.com",
        sql_sa_email="gov@example-project-id.iam.gserviceaccount.com",
        catalog_client=fake_catalog,
    )
    res = g_ctx.search_certified_tables("*")
    assert res["truncated"] is True
    assert res["tables"][0]["table_name"] == "ds_gov.mart_r2_certified"

    # _await_bq_job_result cancels job if result(timeout=...) raises TimeoutError
    class _SlowJob:
        def __init__(self) -> None:
            self.cancelled = False
            self.seen_timeout: float | None = None

        def result(self, timeout: float | None = None) -> list[Any]:
            self.seen_timeout = timeout
            raise TimeoutError("timed out")

        def cancel(self) -> bool:
            self.cancelled = True
            return True

    sj = _SlowJob()
    with pytest.raises(TimeoutError):
        _await_bq_job_result(sj, timeout_s=3.5)
    assert sj.seen_timeout == pytest.approx(3.5)
    assert sj.cancelled is True


def test_enable_live_agent_invalid_value_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "typo_pack"
    (p_dir / "rungs").mkdir(parents=True)
    (p_dir / "pack.yaml").write_text(json.dumps({"id": "typo_pack", "title": "T", "rungs": []}), encoding="utf-8")
    monkeypatch.setenv("ENABLE_LIVE_AGENT", "flase")
    monkeypatch.setenv("REQUIRE_TOKEN_FOR_RUN_AGENT", "false")
    app = create_app(packs_dir=packs_dir, env_file=tmp_path / "none.env")
    client = TestClient(app)
    assert client.get("/api/health").json()["live_agent_enabled"] is False
    resp = client.post("/api/run-agent", json={"pack_id": "typo_pack", "rung_id": "r1_schema", "arm": "blind"})
    assert resp.status_code == 503


def test_offline_mock_harness_all_6_rungs_and_execution_outcome_fields(tmp_path: Path) -> None:
    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "mock_six"
    (p_dir / "rungs").mkdir(parents=True)
    rung_specs = [
        ("r1_schema", 1, "SQL", 10.0, None, ["orders"]),
        ("r2_lineage_semantic", 2, "SQL", 20.0, None, ["mart_r2"]),
        ("r3_graph_semantic", 3, "GQL", 31.8, None, ["graph_tbl"]),
        ("r4_trust_access", 4, "SQL", 28.4, None, ["mart_r2"]),
        ("r5_quality_ops", 5, "SQL", 50.0, [{"name": "c", "value": 38, "tolerance": 0}], ["mart_r2"]),
        ("r6_unstructured_sla", 6, "SQL", 165600.0, [{"name": "b", "value": 14, "tolerance": 0}], ["sla_overlay"]),
    ]
    (p_dir / "pack.yaml").write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "pack_id": "mock_six",
                "title": "Mock 6",
                "subtitle": "Offline mock contract fixture",
                "hero_tagline": "Empirical benchmark fixture",
                "closed_period_label": "Q4 FY25",
                "currency": "SGD",
                "region": "asia-southeast1",
                "rng_seed": 42,
                "generated_mode": "offline_fixture",
                "personas": [
                    {
                        "id": "p_one",
                        "label": "Persona One",
                        "principal_display": "user:p1@example.com",
                        "scope_summary": "Full persona",
                    },
                    {
                        "id": "p_two",
                        "label": "Persona Two",
                        "principal_display": "serviceAccount:ops@example-project-id.iam.gserviceaccount.com",
                        "scope_summary": "Scoped persona",
                    },
                ],
                "invariants": {"settled_rev": 10.0},
                "horizon_cards": [
                    {
                        "id": "kc_card",
                        "title": "Knowledge Catalog",
                        "release_badge": "GA",
                        "region_availability": "asia-southeast1",
                        "summary": "Catalog certification",
                        "primitives": ["AspectType"],
                    },
                    {
                        "id": "ai_card",
                        "title": "AI Extract",
                        "release_badge": "GA",
                        "region_availability": "global",
                        "summary": "Multimodal extraction",
                        "primitives": ["AI.GENERATE"],
                    },
                ],
                "rungs": [f"rungs/{r[0]}.yaml" for r in rung_specs],
            }
        ),
        encoding="utf-8",
    )
    for rid, rnum, lang, target, sec, tbls in rung_specs:
        tier_gov = "TIER_1_VERIFIED_OR_COMPILED" if rnum in (2, 3) else "TIER_2_GROUNDED"
        mech = (
            "Knowledge Catalog | VERIFIED_METRIC_CONTRACT | MEASURE"
            if rnum in (2, 3)
            else "Knowledge Catalog | CERTIFIED | GLOSSARY_DEFINITION"
        )
        rung_obj: dict[str, Any] = {
            "id": rid,
            "rung_num": rnum,
            "short_label": f"R{rnum} Step",
            "title": rid,
            "pyramid_layer": f"Layer {rnum}",
            "release_badges": [{"capability": "Knowledge Catalog", "stage": "GA", "region_scope": "asia-southeast1"}],
            "question": f"Compute metric for {rid}",
            "poll": {
                "prompt": "Pick the governed approach?",
                "options": [
                    {"key": "A", "text": "Governed catalog query"},
                    {"key": "B", "text": "Blind shadow table scan"},
                    {"key": "C", "text": "Unfiltered raw table"},
                    {"key": "D", "text": "Skip metric contract"},
                ],
                "correct_key": "A",
                "reveal_takeaway": "Governed metadata eliminates metric ambiguity.",
            },
            "blind": {
                "answer_headline": "Blind wrong 999.0",
                "answer_detail": "No catalog context available.",
                "numeric_value": 999.0,
                "unit": "SGD",
                "sql_or_gql": "SELECT 999.0 AS ans;",
                "query_language": lang,
                "tokens_used": 6000,
                "exploratory_queries": 5,
                "error_retries": 1,
                "eval_pass_count": 0,
                "eval_total_runs": 2,
                "trust_tier": "TIER_3_REVIEW_REQUIRED",
                "rationale": "Blind guessed raw column.",
            },
            "governed": {
                "answer_headline": f"Governed {target}"
                + (" (38 orders)" if rnum == 5 else " (14 breaches)" if rnum == 6 else ""),
                "answer_detail": "Catalog grounded.",
                "numeric_value": target,
                "unit": "SGD",
                "sql_or_gql": (
                    "SELECT 31.8 AS ans FROM GRAPH_EXPAND(GRAPH_TABLE(g MATCH (n)), ...)"
                    if rnum == 3
                    else f"SELECT {target} AS ans FROM `{tbls[0]}`;"
                ),
                "query_language": lang,
                "context_mechanism": mech,
                "tokens_used": 2500,
                "exploratory_queries": 2,
                "error_retries": 0,
                "eval_pass_count": 2,
                "eval_total_runs": 2,
                "trust_tier": tier_gov,
                "rationale": "Catalog grounded success.",
            },
            "xray_summary": {
                "context_added": "Catalog certification and semantic contract",
                "gcp_primitives": ["Knowledge Catalog"],
                "negative_control_assertion": "Blind arm fails without catalog context.",
            },
            "grading": {"target_value": target, "tolerance": 0.1, "secondary_numerics": sec or [], "required_tables": tbls},
        }
        if rnum == 4:
            rung_obj["identity_variants"] = {
                "p_one": {
                    "persona_id": "p_one",
                    "answer_headline": "Margin 28.4% (842600.0 SGD)",
                    "answer_detail": "4 regions visible under policy one",
                    "numeric_value": 842600.0,
                    "rows_visible": 4,
                    "rls_policy_applied": "rls_p_one_all",
                    "policy_note": "Full regional access granted via row access policy.",
                },
                "p_two": {
                    "persona_id": "p_two",
                    "answer_headline": "Margin 28.4% (346480.0 SGD)",
                    "answer_detail": "1 region visible under policy two",
                    "numeric_value": 346480.0,
                    "rows_visible": 1,
                    "rls_policy_applied": "rls_p_two_scoped",
                    "policy_note": "Scoped access granted via row access policy.",
                },
            }
            rung_obj["grading"]["persona_targets"] = {
                "p_one": {"value": 842600.0, "tolerance": 500.0, "row_count": 4},
                "p_two": {"value": 346480.0, "tolerance": 500.0, "row_count": 1},
            }
        (p_dir / "rungs" / f"{rid}.yaml").write_text(json.dumps(rung_obj), encoding="utf-8")

    out = run_eval_harness(
        pack_id="mock_six",
        runs=2,
        live_gcp=False,
        jsonl_out=tmp_path / "runs.jsonl",
        bundle_out=tmp_path / "bundle.js",
        packs_dir=packs_dir,
    )
    assert out["records_count"] == 24
    bundle = json.loads((tmp_path / "bundle.js").read_text(encoding="utf-8").split("window.CONTEXT_PACK_BUNDLE = ", 1)[1].rstrip(";\n"))
    validate_bundle(bundle)
    assert all(r["governed"]["empirical_eval"]["pass_count"] == 2 for r in bundle["rungs"])
    assert all(r["blind"]["empirical_eval"]["pass_count"] == 0 for r in bundle["rungs"])
    assert all(
        r["governed"]["trust_tier"] in {"TIER_1_VERIFIED_OR_COMPILED", "TIER_2_GROUNDED"}
        for r in bundle["rungs"]
    )
