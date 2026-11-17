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

    def result(self) -> list[dict[str, Any]]:
        return self._rows


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

        def generate_content(self, *, model: str, contents: Any, config: Any) -> Any:
            self.calls += 1
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
    assert res.trust_tier == 1
    assert "CERTIFIED" in res.observed_signals
    assert "MEASURE" in res.observed_signals
    assert "VERIFIED_METRIC_CONTRACT" in res.observed_signals
    assert proj not in json.dumps(res.to_dict())

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
            trust_tier=3 if arm == "blind" else 1,
            observed_signals=["list_tables"] if arm == "blind" else ["CERTIFIED", "search_certified_tables"],
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
    assert "example-project-id" in jsonl_text

    bundle_js = bundle_out.read_text(encoding="utf-8")
    assert live_pid not in bundle_js
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
                            "linked_table": "customers",
                            "linked_column": "tier_code",
                            "entry_link_id": "cust-tier-link",
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
                        "attachments": [{"table_id": "mart_r2", "data": {"certification_status": "CERTIFIED"}}],
                    }
                ],
                "data_quality_scans": [
                    {
                        "data_scan_id": "synth-dq",
                        "target_table": "mart_r2",
                        "catalog_publishing_enabled": True,
                        "rules": [{"name": "non_null_id", "column": "id", "nonNullExpectation": {}}],
                    }
                ],
                "unstructured_contracts": {
                    "bucket_suffix": "synth-contracts",
                    "target_table": "sla_overlay_extracted",
                    "target_file_pattern": "Vendor_Amendment_2.md",
                    "target_vendor_filter": "VendorA",
                    "object_table": "contract_docs_obj",
                    "expected_invariants": {
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

    plan = pcl.resolve_provision_plan(pack_id="synth_p2", repo_root=tmp_path, packs_dir=packs_dir)
    assert plan["blind_dataset_id"] == "synth_blind"
    assert plan["rls_table"] == "mart_r2"
    assert plan["rls_cfo_policy"] == "rls_cfo_all"

    # Dry-run script check via JSON redaction
    redacted_plan = json.dumps(pcl.redact_bundle_data(plan, live_project_id=proj))
    assert proj not in redacted_plan
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

    def _query_side_effect(sql: str, *, job_config: Any = None, location: str = "asia-southeast1") -> Any:
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

    rest_calls: list[tuple[str, str]] = []

    def _fake_rest_transport(method: str, url: str, payload: dict | None) -> tuple[int, dict[str, Any]]:
        rest_calls.append((method, url))
        if ":lookupEntry" in url:
            return 200, {"name": "ok"}
        if "/jobs" in url and method == "GET":
            return 200, {"dataScanJobs": [{"state": "SUCCEEDED"}]}
        if "/connections?" in url:
            return 200, {"cloudResource": {"serviceAccountId": f"conn-sa@{proj}.iam.gserviceaccount.com"}}
        return 200, {"done": True}

    fake_bucket = SimpleNamespace(
        iam_configuration=SimpleNamespace(uniform_bucket_level_access_enabled=True, public_access_prevention="enforced"),
        blob=lambda name: SimpleNamespace(upload_from_filename=lambda *_a, **_kw: None),
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

    rest_calls.clear()
    td_res = pcl.run_teardown(
        plan,
        delete_agent_sas=True,
        bq_client=fake_bq,
        storage_client=fake_gcs,
        rest_client=pcl._RestClient(transport=_fake_rest_transport),
    )
    assert td_res["status"] == "torn_down"
    del_urls = [u for m, u in rest_calls if m == "DELETE"]
    assert "/entryLinks/" in del_urls[0]
    assert "/terms/" in del_urls[1]
    assert "/glossaries/" in del_urls[2]
    assert "/dataScans/" in del_urls[3]
    assert "/aspectTypes/" in del_urls[4]
    assert "/connections/" in del_urls[5]
    assert "synth_blind" in fake_bq.deleted_datasets


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
