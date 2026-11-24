"""Comprehensive unit & integration tests for pack_loader, trust_classifier, RLS, capture_rungs, server, and scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any

from fastapi.testclient import TestClient
from jsonschema import ValidationError
import pytest
import yaml

from engine.bundle_exporter import LeakDetectedError, export_bundle
from engine.capture_rungs import (
    NegativeControlError,
    capture_rungs,
    main as capture_main,
    verify_negative_governance_control,
)
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    discover_packs,
    extract_create_table_statement,
    load_pack,
    load_seed_module,
    resolve_bq_location,
    resolve_env_settings,
)
from engine.rls_impersonation import (
    ImpersonationError,
    build_impersonated_credentials,
    is_valid_customer_sa,
    mint_hmac_role_assertion,
    parse_role_sa_map,
    redact_sensitive_identifiers,
    verify_role_assertion,
)
from engine.trust_classifier import (
    TrustTier,
    classify_outcome,
    normalize_sql_for_match,
    reconcile_outcome_metric,
    reconcile_prose_numbers,
    strip_sql_literals_and_comments,
)
from server.app import create_app


def _write_synthetic_pack(
    packs_dir: Path,
    *,
    pack_id: str = "synthetic_pack",
    include_bad_field: bool = False,
) -> Path:
    pack_root = packs_dir / pack_id
    rungs_dir = pack_root / "rungs"
    rungs_dir.mkdir(parents=True, exist_ok=True)

    pack_doc: dict[str, Any] = {
        "schema_version": "2.0",
        "pack_id": pack_id,
        "title": "Synthetic Governed Context Pack",
        "subtitle": "Minimal fixture pack for independent engine verification",
        "hero_tagline": "Frontier models are table stakes—governed enterprise context is the differentiator.",
        "closed_period_label": "Closed Q1 2026",
        "currency": "USD",
        "region": "asia-southeast1",
        "rng_seed": 12345,
        "generated_mode": "offline_fixture",
        "personas": [
            {
                "id": "analyst_global",
                "label": "Global Analyst",
                "principal_display": "analyst-global@example-project-id.iam.gserviceaccount.com",
                "scope_summary": "Sees all 4 synthetic regions.",
            },
            {
                "id": "analyst_sg",
                "label": "SG Analyst",
                "principal_display": "analyst-sg@example-project-id.iam.gserviceaccount.com",
                "scope_summary": "Restricted to SG rows via BigQuery RLS.",
            },
        ],
        "invariants": {
            "total_metric": 400.0,
            "sg_metric": 100.0,
            "verified_flag": True,
        },
        "horizon_cards": [
            {
                "id": "knowledge_studio",
                "title": "Knowledge Studio",
                "release_badge": "Preview",
                "region_availability": "US / EU multi-regions",
                "summary": "Preview context authoring workflow.",
                "primitives": ["Context Sets", "Enrichment Agent"],
            },
            {
                "id": "open_lakehouse",
                "title": "Open Lakehouse Federation",
                "release_badge": "GA",
                "region_availability": "Global GA",
                "summary": "Federated catalog access across engines.",
                "primitives": ["Workload Identity Federation", "OIDC"],
            },
        ],
    }
    if include_bad_field:
        pack_doc["unexpected_extra_key"] = "should_fail_additionalProperties"

    (pack_root / "pack.yaml").write_text(yaml.safe_dump(pack_doc, sort_keys=False), encoding="utf-8")

    # Write 6 rungs intentionally out of filename sort order for r1/r2 to verify sorting by rung_num.
    specs = [
        (1, "r1_schema", "z_r1_schema.yaml", "TIER_2_GROUNDED", "SQL", "BigQuery Schema + Data Insights", "SELECT SUM(gross) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.orders`", "SELECT SUM(net) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.orders` WHERE status = 'DONE'", 150.0, 100.0),
        (2, "r2_glossary", "a_r2_glossary.yaml", "TIER_2_GROUNDED", "SQL", "Knowledge Catalog Business Glossary", "SELECT AVG(val) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.customers` WHERE label LIKE '%Vip%'", "SELECT AVG(val) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.customers` WHERE tier = 'VIP_CORE'", 50.0, 200.0),
        (3, "r3_metrics", "r3_metrics.yaml", "TIER_1_VERIFIED_OR_COMPILED", "SQL", "BigQuery Graph MEASURE() Verified Query", "SELECT SUM(a) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.orders` JOIN `${PROJECT_ID}.${DATASET_ID}.legs` USING(id)", "SELECT metric_value FROM GRAPH_TABLE(`${PROJECT_ID}.${DATASET_ID}.supply_graph` MATCH (o:Orders) COLUMNS (MEASURE(o.margin) AS metric_value))", 15.0, 300.0),
        (4, "r4_trust_access", "r4_trust_access.yaml", "TIER_1_VERIFIED_OR_COMPILED", "SQL", "Certified Data Product + BigQuery RLS", "SELECT SUM(val) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.staging_old`", "SELECT SUM(val) AS metric_value, COUNT(*) AS rows_visible FROM `${PROJECT_ID}.${DATASET_ID}.gold_margin`", 250.0, 400.0),
        (5, "r5_graph", "r5_graph.yaml", "TIER_1_VERIFIED_OR_COMPILED", "GQL", "BigQuery Property Graph ISO GQL", "SELECT COUNT(*) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.orders` WHERE batch = 'B1'", "SELECT exposed_val AS metric_value FROM GRAPH_TABLE(`${PROJECT_ID}.${DATASET_ID}.supply_graph` MATCH (b:Batch)-[:ALLOC]->(o:Orders) COLUMNS (SUM(o.val) AS exposed_val))", 25.0, 500.0),
        (6, "r6_contracts", "r6_contracts.yaml", "TIER_1_VERIFIED_OR_COMPILED", "SQL", "DocAI sla_overlay Compiled Contract", "SELECT SUM(credit) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.base_sla`", "SELECT SUM(credit) AS metric_value FROM `${PROJECT_ID}.${DATASET_ID}.sla_overlay`", 40.0, 600.0),
    ]

    for num, rid, fname, gov_tier, q_lang, mech, blind_sql, gov_sql, blind_val, gov_val in specs:
        rung_doc: dict[str, Any] = {
            "id": rid,
            "rung_num": num,
            "short_label": f"Rung {num}",
            "title": f"Synthetic Rung {num} Title",
            "pyramid_layer": f"Layer {num} Governance",
            "release_badges": [
                {"capability": "BigQuery SQL", "stage": "GA", "region_scope": "asia-southeast1"}
            ],
            "question": f"What is the synthetic metric for rung {num}?",
            "poll": {
                "prompt": f"Poll question for rung {num}?",
                "options": [
                    {"key": "A", "text": "Option A"},
                    {"key": "B", "text": "Option B"},
                    {"key": "C", "text": "Option C"},
                    {"key": "D", "text": "Option D"},
                ],
                "correct_key": "B",
                "reveal_takeaway": "Governed context removes ambiguity.",
            },
            "blind": {
                "answer_headline": f"USD {blind_val:.2f}",
                "answer_detail": "Blind execution hit semantic trap.",
                "numeric_value": blind_val,
                "unit": "USD",
                "sql_or_gql": blind_sql,
                "query_language": "SQL",
                "tokens_used": 1200,
                "exploratory_queries": 3,
                "error_retries": 1,
                "eval_pass_count": 0,
                "eval_total_runs": 5,
                "trust_tier": "TIER_3_REVIEW_REQUIRED",
                "rationale": "Ungrounded query missed business rules.",
            },
            "governed": {
                "answer_headline": f"USD {gov_val:.2f}",
                "answer_detail": "Governed execution returned exact verified figure.",
                "numeric_value": gov_val,
                "unit": "USD",
                "sql_or_gql": gov_sql,
                "query_language": q_lang,
                "context_payload": '{"glossary": "synthetic"}',
                "context_mechanism": mech,
                "tokens_used": 450,
                "exploratory_queries": 0,
                "error_retries": 0,
                "eval_pass_count": 5,
                "eval_total_runs": 5,
                "trust_tier": gov_tier,
                "rationale": "Governed context compiled cleanly.",
            },
            "xray_summary": {
                "context_added": "Added glossary & compiled metric definition.",
                "gcp_primitives": ["BigQuery", "Knowledge Catalog"],
                "negative_control_assertion": "Asserts 403 or RLS row filtering.",
            },
        }
        if num == 4:
            rung_doc["identity_variants"] = {
                "analyst_global": {
                    "persona_id": "analyst_global",
                    "answer_headline": "USD 400.00",
                    "answer_detail": "Full 4-region visibility.",
                    "numeric_value": 400.0,
                    "rows_visible": 4,
                    "rls_policy_applied": "rls_global_all",
                    "policy_note": "FILTER USING (TRUE)",
                },
                "analyst_sg": {
                    "persona_id": "analyst_sg",
                    "answer_headline": "USD 100.00",
                    "answer_detail": "SG-only visibility.",
                    "numeric_value": 100.0,
                    "rows_visible": 1,
                    "rls_policy_applied": "rls_sg_only",
                    "policy_note": "FILTER USING (country_code = 'SG')",
                },
            }

        (rungs_dir / fname).write_text(yaml.safe_dump(rung_doc, sort_keys=False), encoding="utf-8")

    seed_code = """
def generate_dataset(seed=12345):
    return {
        "gold_margin": [
            {"country_code": "SG", "val": 100.0},
            {"country_code": "MY", "val": 100.0},
            {"country_code": "TH", "val": 100.0},
            {"country_code": "ID", "val": 100.0},
        ]
    }

def evaluate_invariants(tables=None, seed=12345):
    rows = (tables or generate_dataset(seed))["gold_margin"]
    return {
        "total_metric": sum(r["val"] for r in rows),
        "sg_metric": sum(r["val"] for r in rows if r["country_code"] == "SG"),
        "verified_flag": True,
    }
"""
    (pack_root / "seed_synthetic.py").write_text(seed_code.strip() + "\n", encoding="utf-8")
    return pack_root


class _FakeQueryJob:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def result(self) -> list[dict[str, Any]]:
        return self._rows


class _FakeBigQueryClient:
    """Minimal BigQuery client fake for dry-run and live-gcp tests."""

    def __init__(
        self,
        *,
        policies: list[dict[str, Any]] | None = None,
        raise_on_query: Exception | None = None,
        persona: str | None = None,
        session_user: str | None = None,
        deny_tables: set[str] | None = None,
    ) -> None:
        self.queries: list[tuple[str, bool, str | None]] = []
        self._policies = policies or [
            {
                "rowAccessPolicyReference": {"tableId": "gold_margin", "policyId": "rls_global_all"},
                "filterPredicate": "TRUE",
                "grantees": ["user:global@example.com"],
            },
            {
                "rowAccessPolicyReference": {"tableId": "gold_margin", "policyId": "rls_sg_only"},
                "filterPredicate": "country_code = 'SG'",
                "grantees": ["serviceAccount:analyst-sg@example-project-id.iam.gserviceaccount.com"],
            },
        ]
        self._raise_on_query = raise_on_query
        self._persona = persona
        self._session_user = session_user
        self._deny_tables = deny_tables or set()

    def _call_api(self, *_args: Any, path: str = "", **_kwargs: Any) -> dict[str, Any]:
        if path.endswith("/rowAccessPolicies"):
            return {"rowAccessPolicies": self._policies}
        return {}

    def query(self, sql: str, job_config: Any = None, location: str | None = None) -> _FakeQueryJob:
        if self._raise_on_query is not None:
            raise self._raise_on_query
        dry_run = bool(getattr(job_config, "dry_run", False))
        self.queries.append((sql, dry_run, location))
        if dry_run:
            return _FakeQueryJob([])

        for tbl in self._deny_tables:
            if tbl in sql:
                err = RuntimeError("Policy denied access to restricted resource")
                err.code = 403  # type: ignore[attr-defined]
                err.errors = [{"reason": "accessDenied"}]  # type: ignore[attr-defined]
                raise err

        if "SESSION_USER()" in sql:
            return _FakeQueryJob([{"session_user": self._session_user}] if self._session_user else [])

        if "WHERE NOT (" in sql:
            if self._persona == "analyst_sg":
                return _FakeQueryJob([])
            return _FakeQueryJob(
                [{"country_code": "MY"}, {"country_code": "TH"}, {"country_code": "ID"}]
            )

        if sql.startswith("SELECT COUNT(*) AS rows_visible"):
            return _FakeQueryJob(
                [{"rows_visible": 1 if ("country_code = 'SG'" in sql or self._persona == "analyst_sg") else 4}]
            )
        if "WHERE (country_code = 'SG')" in sql or self._persona == "analyst_sg":
            return _FakeQueryJob([{"metric_value": 100.0, "rows_visible": 1}])
        if "gold_margin" in sql:
            return _FakeQueryJob([{"metric_value": 400.0, "rows_visible": 4}])
        if "staging_old" in sql:
            return _FakeQueryJob([{"metric_value": 250.0}])
        if "status = 'DONE'" in sql:
            return _FakeQueryJob([{"metric_value": 100.0}])
        if "SUM(gross)" in sql:
            return _FakeQueryJob([{"metric_value": 150.0}])
        if "VIP_CORE" in sql:
            return _FakeQueryJob([{"metric_value": 200.0}])
        if "LIKE '%Vip%'" in sql:
            return _FakeQueryJob([{"metric_value": 50.0}])
        if "MEASURE(" in sql:
            return _FakeQueryJob([{"metric_value": 300.0}])
        if "JOIN" in sql:
            return _FakeQueryJob([{"metric_value": 15.0}])
        if "GRAPH_TABLE" in sql:
            return _FakeQueryJob([{"metric_value": 500.0}])
        if "batch = 'B1'" in sql:
            return _FakeQueryJob([{"metric_value": 25.0}])
        if "sla_overlay" in sql:
            return _FakeQueryJob([{"metric_value": 600.0}])
        if "base_sla" in sql:
            return _FakeQueryJob([{"metric_value": 40.0}])
        return _FakeQueryJob([{"metric_value": 0.0}])


def test_pack_loader_discovers_sorts_and_validates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir)
    assert discover_packs(packs_dir) == ["synthetic_pack"]

    bundle = load_pack("synthetic_pack", packs_dir=packs_dir, dataset_id="test_ds")
    assert [r["rung_num"] for r in bundle["rungs"]] == [1, 2, 3, 4, 5, 6]
    assert "example-project-id.test_ds.orders" in bundle["rungs"][0]["governed"]["sql_or_gql"]

    seed_mod = load_seed_module("synthetic_pack", packs_dir=packs_dir)
    assert seed_mod is not None
    assert seed_mod.evaluate_invariants()["sg_metric"] == 100.0

    # Comment-before-CREATE and ';' inside OPTIONS string literal must not trip staging DDL extraction
    ddl_sql = (
        "-- Notes: run CREATE TABLE IF NOT EXISTS `p.d.staging_cold_chain_oct11` first.\n"
        "/* Another comment mentioning CREATE TABLE IF NOT EXISTS `p.d.staging_cold_chain_oct11`; */\n"
        "CREATE TABLE IF NOT EXISTS `p.d.other_tbl` (id STRING);\n"
        "CREATE TABLE IF NOT EXISTS `p.d.staging_cold_chain_oct11` (\n"
        '  country_code STRING OPTIONS(description="keep; -- not a comment"),\n'
        "  margin FLOAT64\n"
        ");\n"
    )
    extracted = extract_create_table_statement(ddl_sql, "staging_cold_chain_oct11")
    assert extracted is not None
    assert extracted.startswith("CREATE TABLE IF NOT EXISTS `p.d.staging_cold_chain_oct11`")
    assert 'description="keep; -- not a comment"' in extracted
    assert "other_tbl" not in extracted

    # BQ_LOCATION precedence: env/.env > pack.yaml region > default
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    env_file = tmp_path / "empty.env"
    env_file.write_text("", encoding="utf-8")
    settings = resolve_env_settings(tmp_path, env_file=env_file)
    assert resolve_bq_location({"region": "us-central1"}, env_settings=settings) == "us-central1"
    monkeypatch.setenv("BQ_LOCATION", "europe-west1")
    assert resolve_bq_location({"region": "us-central1"}, env_settings=settings) == "europe-west1"


def test_pack_loader_rejects_additional_properties(tmp_path: Path) -> None:
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir, include_bad_field=True)
    with pytest.raises(ValidationError):
        load_pack("synthetic_pack", packs_dir=packs_dir)


def test_trust_classifier_sql_normalization_and_reconciliation() -> None:
    sql_a = """
    -- leading comment
    SELECT /* block */ `proj.ds.customers`, SUM(val)
    FROM `proj.ds.customers`
    WHERE label = 'Premier  Promo_Trial' AND note = 'MEASURE(fake)';
    """
    sql_b = "select proj.ds.customers , sum ( val ) from proj.ds.customers where label = 'Premier  Promo_Trial' and note = 'MEASURE(fake)'"
    norm_a = normalize_sql_for_match(sql_a)
    norm_b = normalize_sql_for_match(sql_b)
    assert "'Premier  Promo_Trial'" in norm_a
    assert "'MEASURE(fake)'" in norm_a
    assert norm_a.replace(" ,", ",").replace(" ( ", "(").replace(" )", ")") == norm_b.replace(" ,", ",").replace(" ( ", "(").replace(" )", ")")

    stripped = strip_sql_literals_and_comments(sql_a)
    assert "MEASURE" not in stripped
    assert "Premier" not in stripped

    # Literal 'MEASURE(fake)' alone must NOT trigger TIER_1
    literal_trap = classify_outcome(
        sql_or_gql="SELECT val FROM tbl WHERE note = 'MEASURE(fake)'",
        query_language="SQL",
        answer_headline="USD 100.00",
        numeric_value=100.0,
        result_rows=[{"val": 100.0}],
        context_mechanism="Schema + Business Glossary",
        context_payload='{"term": "x"}',
    )
    assert literal_trap.tier == TrustTier.TIER_2_GROUNDED
    assert not literal_trap.uses_measure

    # Genuine MEASURE() -> TIER_1
    tier1 = classify_outcome(
        sql_or_gql="SELECT metric_value FROM GRAPH_TABLE(g MATCH (o:Orders) COLUMNS (MEASURE(o.m) AS metric_value))",
        query_language="GQL",
        answer_headline="USD 300.00",
        numeric_value=300.0,
        result_rows=[{"metric_value": 300.0}],
        context_mechanism="BigQuery Graph MEASURE()",
    )
    assert tier1.tier == TrustTier.TIER_1_VERIFIED_OR_COMPILED
    assert tier1.uses_measure and tier1.uses_graph_table

    # Numeric mismatch downgrades to TIER_3
    mismatch = classify_outcome(
        sql_or_gql="SELECT metric_value FROM GRAPH_TABLE(g MATCH (o:Orders) COLUMNS (MEASURE(o.m) AS metric_value))",
        query_language="GQL",
        answer_headline="USD 999.00",
        numeric_value=300.0,
        result_rows=[{"metric_value": 300.0}],
        context_mechanism="BigQuery Graph MEASURE()",
    )
    assert mismatch.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert any("unverified_headline_numeric" in r for r in mismatch.reasons)

    # Standalone prose audit catches fabricated figures and assumption markers
    unverified = reconcile_prose_numbers(
        "Revenue hit USD 1,234.56 with 42.5% margin in Q1 2026.",
        question="What was Q1 2026 revenue?",
        result_rows=[{"rev": 1234.56}],
    )
    assert unverified == ("42.5%",)
    ok_metric, actual, _ = reconcile_outcome_metric(100.0, [{"x": 40.0}, {"x": 60.0}])
    assert ok_metric and actual == 100.0

    # Narrow hyphenated alphanumeric tag tokens (letters-hyphen-digits) + SQL string/date year literals -> TIER_1
    tag_and_sql_year = classify_outcome(
        sql_or_gql=(
            "SELECT SUM(exposed_amount) AS exposed_amount FROM GRAPH_TABLE(g MATCH (n) "
            "WHERE n.created_date >= DATE '2026-07-01' COLUMNS (19380.0 AS exposed_amount))"
        ),
        query_language="GQL",
        answer_headline="Tier-2 Synth Stream Batch #TX-409 (ISO-3166) total exposure was SGD 19,380.00 during Q3 2026.",
        numeric_value=19380.0,
        result_rows=[{"exposed_amount": 19380.0}],
        context_mechanism="GRAPH_TABLE",
    )
    assert tag_and_sql_year.tier == TrustTier.TIER_1_VERIFIED_OR_COMPILED
    assert tag_and_sql_year.reasons == ()

    # Unquoted numeric year in SQL (not a string/date literal) must NOT exempt headline year
    unquoted_sql_year = classify_outcome(
        sql_or_gql="SELECT 19380.0 AS exposed_amount FROM synth_gov.orders WHERE fiscal_year = 2026",
        query_language="SQL",
        answer_headline="Exposed amount was SGD 19,380.00 in 2026.",
        numeric_value=19380.0,
        result_rows=[{"exposed_amount": 19380.0}],
        context_mechanism="knowledge_catalog",
    )
    assert unquoted_sql_year.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "unverified_headline_numeric:2026" in unquoted_sql_year.reasons

    # ISO currency hyphen, hyphenated decimal, or negative loss still audited; fabricated money headline stays TIER_3
    assert reconcile_prose_numbers("Impact was SGD-500 on metric-42.5.", result_rows=[{"x": 10}]) == (
        "500",
        "42.5",
    )
    assert reconcile_prose_numbers("Loss was -500.", result_rows=[{"x": 10}]) == ("-500",)
    fabricated_money = classify_outcome(
        sql_or_gql="SELECT net_revenue AS val FROM synth_gov.orders",
        query_language="SQL",
        answer_headline="Total completed revenue was SGD 1,684,200.",
        numeric_value=1312450.0,
        result_rows=[{"val": 1312450.0}],
        context_mechanism="knowledge_catalog",
    )
    assert fabricated_money.tier == TrustTier.TIER_3_REVIEW_REQUIRED
    assert "unverified_headline_numeric:1,684,200" in fabricated_money.reasons


def test_rls_impersonation_hmac_sa_validation_and_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "0123456789abcdef0123456789abcdef"
    now_ts = 1_700_000_000
    token = mint_hmac_role_assertion("analyst_sg", "alice@example.org", hmac_secret=secret, now=now_ts, ttl_seconds=120)
    verified = verify_role_assertion(token, hmac_secret=secret, now=now_ts + 10)
    assert verified.role == "analyst_sg"
    assert verified.subject == "alice@example.org"

    # Tampered signature rejected
    bad_sig = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")
    with pytest.raises(ImpersonationError, match="signature"):
        verify_role_assertion(bad_sig, hmac_secret=secret, now=now_ts + 10)

    # Expired token, subject mismatch, and audience mismatch rejected
    with pytest.raises(ImpersonationError, match="expired"):
        verify_role_assertion(token, hmac_secret=secret, now=now_ts + 500)
    with pytest.raises(ImpersonationError, match="subject"):
        verify_role_assertion(token, hmac_secret=secret, now=now_ts + 10, expected_subject="bob@example.org")
    with pytest.raises(ImpersonationError, match="audience"):
        verify_role_assertion(token, hmac_secret=secret, now=now_ts + 10, expected_audience="other-aud")

    # Customer SA validation vs Google-managed SAs
    sa_suffix = "gserviceaccount" + ".com"
    assert is_valid_customer_sa("analyst-sg@example-project-id.iam.gserviceaccount.com")
    assert not is_valid_customer_sa("service-12345@" + "gcp-sa-bigquery" + ".iam." + sa_suffix)
    assert not is_valid_customer_sa("12345@" + "cloudservices." + sa_suffix)
    assert not is_valid_customer_sa("12345-compute@" + "developer." + sa_suffix)

    parsed = parse_role_sa_map(
        '{"analyst_sg":"analyst-sg@example-project-id.iam.gserviceaccount.com"}'
    )
    assert parsed["analyst_sg"].endswith(".iam.gserviceaccount.com")

    with pytest.raises(ImpersonationError):
        parse_role_sa_map('{"bad":"svc@' + "gcp-sa-bigquery" + '.iam.' + sa_suffix + '"}')

    from types import SimpleNamespace

    creds, sa = build_impersonated_credentials(
        role="analyst_sg",
        role_sa_map=parsed,
        source_credentials=SimpleNamespace(universe_domain="googleapis.com"),
    )
    assert sa == "analyst-sg@example-project-id.iam.gserviceaccount.com"
    assert creds is not None

    fake_live_proj = "sandbox-alpha-" + "998877"
    fake_sa = "reader@" + fake_live_proj + ".iam.gserviceaccount.com"
    fake_user = "alice@" + "corp-domain.example"
    raw_text = (
        f"Project {fake_live_proj} ran as {fake_sa} for {fake_user}; "
        "safe=analyst-sg@example-project-id.iam.gserviceaccount.com"
    )
    redacted = redact_sensitive_identifiers(raw_text, extra_tokens=[fake_live_proj])
    assert fake_live_proj not in redacted
    assert fake_sa not in redacted
    assert fake_user not in redacted
    assert "redacted-sa@example-project-id.iam.gserviceaccount.com" in redacted
    assert "analyst-sg@example-project-id.iam.gserviceaccount.com" in redacted
    assert redact_sensitive_identifiers(redacted, extra_tokens=[fake_live_proj]) == redacted


def test_negative_governance_control_distinguishes_403_from_400() -> None:
    class ForbiddenError(Exception):
        code = 403
        errors = [{"reason": "accessDenied", "message": "Access Denied"}]

    class BadRequestError(Exception):
        code = 400
        errors = [{"reason": "invalidQuery", "message": "Syntax error"}]

    res_403 = verify_negative_governance_control(exception=ForbiddenError("403 accessDenied"))
    assert res_403.passed
    assert res_403.mechanism == "iam_403_access_denied"

    with pytest.raises(NegativeControlError, match="400"):
        verify_negative_governance_control(exception=BadRequestError("400 badRequest"))

    # Tightened check: plain RuntimeError mentioning '403' / 'permission' without 403/Forbidden/reason must fail
    with pytest.raises(NegativeControlError, match="Unexpected error"):
        verify_negative_governance_control(
            exception=RuntimeError("Query string mentions permission or 403 literal")
        )

    class NotFoundError(Exception):
        code = 404
        errors = [{"reason": "notFound", "message": "Missing table"}]

    with pytest.raises(NegativeControlError, match="404"):
        verify_negative_governance_control(exception=NotFoundError("404 notFound"))

    # Unfiltered RLS bypass must fail closed
    with pytest.raises(NegativeControlError, match="baseline"):
        verify_negative_governance_control(
            rows=[{"r": i} for i in range(4)],
            baseline_row_count=4,
            active_rls_policies=[{"policy_id": "rls_sg_only"}],
        )

    # Active RLS row filtering succeeds only with policies & strict reduction
    res_rls = verify_negative_governance_control(
        rows=[{"country_code": "SG"}],
        baseline_row_count=4,
        expected_max_rows=1,
        active_rls_policies=[{"policy_id": "rls_sg_only"}],
    )
    assert res_rls.passed and res_rls.mechanism == "rls_row_filtering"

    with pytest.raises(NegativeControlError, match="active BigQuery row access policies"):
        verify_negative_governance_control(rows=[], baseline_row_count=4, active_rls_policies=[])


def test_capture_rungs_all_cli_modes_and_redaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SQL_ROLE_SA_MAP_JSON", raising=False)
    monkeypatch.delenv("SQL_NEGATIVE_CONTROL_SA", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir)
    out_js = tmp_path / "out" / "rungs_bundle.js"
    no_env = tmp_path / "nonexistent.env"

    # 1. --offline-fixture
    bundle_off = capture_rungs(
        pack_id="synthetic_pack",
        mode="offline_fixture",
        output_path=out_js,
        packs_dir=packs_dir,
        env_file=no_env,
    )
    assert bundle_off["generated_mode"] == "offline_fixture"
    assert out_js.is_file()
    assert "window.CONTEXT_PACK_BUNDLE = " in out_js.read_text(encoding="utf-8")

    # 2. --dry-run (mocked BigQuery client + fake live PROJECT_ID scrubbed from output)
    live_proj = "live-sandbox-" + "776655"
    monkeypatch.setenv("PROJECT_ID", live_proj)
    monkeypatch.setenv("DATASET_ID", "synthetic_ds")
    fake_bq = _FakeBigQueryClient()
    bundle_dry = capture_rungs(
        pack_id="synthetic_pack",
        mode="dry_run",
        output_path=out_js,
        packs_dir=packs_dir,
        env_file=no_env,
        bq_client=fake_bq,
    )
    assert bundle_dry["generated_mode"] == "dry_run_verified"
    assert len(fake_bq.queries) == 12
    assert all(dry for _, dry, _ in fake_bq.queries)
    assert all(live_proj in sql for sql, _, _ in fake_bq.queries)
    assert live_proj not in out_js.read_text(encoding="utf-8")
    assert "example-project-id" in out_js.read_text(encoding="utf-8")

    # 3. --live-gcp with explicit impersonation factory + 403 negative probe passes cleanly
    class _Denied403(Exception):
        code = 403
        errors = [{"reason": "accessDenied"}]

    def _raise_403() -> list[dict[str, Any]]:
        raise _Denied403("Access Denied")

    fake_live = _FakeBigQueryClient()
    bundle_live = capture_rungs(
        pack_id="synthetic_pack",
        mode="live_gcp",
        output_path=out_js,
        packs_dir=packs_dir,
        env_file=no_env,
        bq_client=fake_live,
        impersonated_client_factory=lambda persona: _FakeBigQueryClient(persona=persona),
        negative_control_probe=_raise_403,
    )
    assert bundle_live["generated_mode"] == "live_gcp_verified"
    assert live_proj not in out_js.read_text(encoding="utf-8")

    # 4. --live-gcp WITHOUT impersonation and WITHOUT matching SESSION_USER() fails closed
    sentinel_out = tmp_path / "out" / "should_not_exist_live.js"
    with pytest.raises(NegativeControlError, match="predicate simulation is disabled"):
        capture_rungs(
            pack_id="synthetic_pack",
            mode="live_gcp",
            output_path=sentinel_out,
            packs_dir=packs_dir,
            env_file=no_env,
            bq_client=_FakeBigQueryClient(),
        )
    assert not sentinel_out.exists()

    # 5. --live-gcp with SQL_ROLE_SA_MAP_JSON executes governed SQL via primary persona SA
    # even when the base runner client is denied access to the RLS table.
    from types import SimpleNamespace

    sa_global = "analyst-global@example-project-id.iam.gserviceaccount.com"
    sa_sg = "analyst-sg@example-project-id.iam.gserviceaccount.com"
    monkeypatch.setenv(
        "SQL_ROLE_SA_MAP_JSON",
        json.dumps({"analyst_global": sa_global, "analyst_sg": sa_sg}),
    )

    def _fake_build_creds(*, role: str, role_sa_map: dict[str, str], **_kw: Any) -> tuple[Any, str]:
        return SimpleNamespace(_fake_role=role), role_sa_map[role]

    def _fake_bq_ctor(*, project: str, credentials: Any = None, location: str = "") -> _FakeBigQueryClient:
        role = getattr(credentials, "_fake_role", None)
        return _FakeBigQueryClient(persona=role)

    monkeypatch.setattr("engine.capture_rungs.build_impersonated_credentials", _fake_build_creds)
    monkeypatch.setattr("google.cloud.bigquery.Client", _fake_bq_ctor)

    base_restricted_client = _FakeBigQueryClient(deny_tables={"gold_margin"})
    bundle_sa_map = capture_rungs(
        pack_id="synthetic_pack",
        mode="live_gcp",
        output_path=out_js,
        packs_dir=packs_dir,
        env_file=no_env,
        bq_client=base_restricted_client,
    )
    assert bundle_sa_map["generated_mode"] == "live_gcp_verified"

    # 6. Zero-flag --live-gcp (SQL_ROLE_SA_MAP_JSON unset): BigQuery REST GET rowAccessPolicies
    # omits grantees, so list_active_row_access_policies fetches bindings via POST :getIamPolicy,
    # SESSION_USER matches user: grantee, and SG SA is impersonated via build_impersonated_credentials.
    monkeypatch.delenv("SQL_ROLE_SA_MAP_JSON", raising=False)

    class _FakeRestPolicyBQClient(_FakeBigQueryClient):
        def _call_api(self, *_args: Any, method: str = "GET", path: str = "", **_kwargs: Any) -> dict[str, Any]:
            if path.endswith("/rowAccessPolicies") and method == "GET":
                return {
                    "rowAccessPolicies": [
                        {
                            "rowAccessPolicyReference": {"tableId": "gold_margin", "policyId": "rls_global_all"},
                            "filterPredicate": "TRUE",
                        },
                        {
                            "rowAccessPolicyReference": {"tableId": "gold_margin", "policyId": "rls_sg_only"},
                            "filterPredicate": "country_code = 'SG'",
                        },
                    ]
                }
            if path.endswith("/rls_global_all:getIamPolicy") and method == "POST":
                return {
                    "bindings": [
                        {"role": "roles/bigquery.filteredDataViewer", "members": ["user:global@example.com"]}
                    ]
                }
            if path.endswith("/rls_sg_only:getIamPolicy") and method == "POST":
                return {
                    "bindings": [
                        {
                            "role": "roles/bigquery.filteredDataViewer",
                            "members": [f"serviceAccount:{sa_sg}"],
                        }
                    ]
                }
            return {}

    zero_flag_client = _FakeRestPolicyBQClient(session_user="global@example.com")
    bundle_zero_flag = capture_rungs(
        pack_id="synthetic_pack",
        mode="live_gcp",
        output_path=out_js,
        packs_dir=packs_dir,
        env_file=no_env,
        bq_client=zero_flag_client,
    )
    assert bundle_zero_flag["generated_mode"] == "live_gcp_verified"

    # 7. CLI main() flag coverage (--pack --offline-fixture --output)
    monkeypatch.setattr("engine.capture_rungs.DEFAULT_REPO_ROOT", tmp_path)
    monkeypatch.setattr("engine.pack_loader.DEFAULT_REPO_ROOT", tmp_path)
    (tmp_path / "schemas").mkdir(exist_ok=True)
    (tmp_path / "schemas" / "rung_v2.schema.json").write_text(
        (DEFAULT_REPO_ROOT / "schemas" / "rung_v2.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    cli_out = tmp_path / "cli_bundle.js"
    rc = capture_main(["--pack", "synthetic_pack", "--offline-fixture", "--output", str(cli_out)])
    assert rc == 0
    assert cli_out.is_file()


def test_export_bundle_refuses_to_write_leaks(tmp_path: Path) -> None:
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir)
    bundle = load_pack("synthetic_pack", packs_dir=packs_dir)
    bundle["subtitle"] = "Internal docs at https://" + "goto." + "google.com/secret"
    with pytest.raises(LeakDetectedError):
        export_bundle(bundle, output_path=tmp_path / "bad_bundle.js")


def test_fastapi_server_allowlist_and_live_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SQL_ROLE_SA_MAP_JSON", raising=False)
    monkeypatch.delenv("BQ_LOCATION", raising=False)
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir)
    live_proj = "live-api-" + "445566"
    monkeypatch.setenv("PROJECT_ID", live_proj)
    monkeypatch.setenv("DATASET_ID", "synthetic_ds")
    no_env = tmp_path / "nonexistent.env"

    fake_bq = _FakeBigQueryClient()
    app = create_app(
        packs_dir=packs_dir,
        web_dir=tmp_path / "nonexistent_web",
        env_file=no_env,
        bq_client=fake_bq,
    )
    client = TestClient(app)

    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["packs"] == ["synthetic_pack"]
    assert live_proj not in health_resp.text

    # Valid governed run without impersonation labels predicate_simulation
    run_resp = client.post(
        "/api/run-rung",
        json={
            "pack_id": "synthetic_pack",
            "rung_id": "r4_trust_access",
            "mode": "governed",
            "persona_id": "analyst_sg",
            "live": True,
        },
    )
    assert run_resp.status_code == 200
    payload = run_resp.json()
    assert payload["numeric_value"] == 100.0
    assert payload["row_count"] == 1
    assert payload["trust_tier"] == "TIER_1_VERIFIED_OR_COMPILED"
    assert payload["rls_enforcement"] == "predicate_simulation"
    assert live_proj not in json.dumps(payload)

    # With impersonation factory, labels bigquery_rls_impersonated
    imp_app = create_app(
        packs_dir=packs_dir,
        web_dir=tmp_path / "nonexistent_web",
        env_file=no_env,
        bq_client=fake_bq,
        impersonated_client_factory=lambda persona: _FakeBigQueryClient(persona=persona),
    )
    imp_resp = TestClient(imp_app).post(
        "/api/run-rung",
        json={
            "pack_id": "synthetic_pack",
            "rung_id": "r4_trust_access",
            "mode": "governed",
            "persona_id": "analyst_sg",
            "live": True,
        },
    )
    assert imp_resp.status_code == 200
    assert imp_resp.json()["rls_enforcement"] == "bigquery_rls_impersonated"
    assert imp_resp.json()["row_count"] == 1

    # Offline run
    off_resp = client.post(
        "/api/run-rung",
        json={
            "pack_id": "synthetic_pack",
            "rung_id": "r1_schema",
            "mode": "blind",
            "live": False,
        },
    )
    assert off_resp.status_code == 200
    assert off_resp.json()["execution_mode"] == "offline_fixture"
    assert off_resp.json()["rls_enforcement"] == "offline_fixture"
    assert off_resp.json()["trust_tier"] == "TIER_3_REVIEW_REQUIRED"

    # Reject extra raw SQL field (extra="forbid")
    sqli_resp = client.post(
        "/api/run-rung",
        json={
            "pack_id": "synthetic_pack",
            "rung_id": "r1_schema",
            "mode": "governed",
            "sql": "DROP TABLE orders;",
        },
    )
    assert sqli_resp.status_code in (400, 422)

    # Reject unknown pack / rung / path traversal
    assert (
        client.post(
            "/api/run-rung",
            json={"pack_id": "../etc", "rung_id": "r1_schema", "mode": "governed"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/run-rung",
            json={"pack_id": "unknown_pack", "rung_id": "r1_schema", "mode": "governed"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/run-rung",
            json={"pack_id": "synthetic_pack", "rung_id": "r99_missing", "mode": "governed"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/run-rung",
            json={
                "pack_id": "synthetic_pack",
                "rung_id": "r4_trust_access",
                "mode": "governed",
                "persona_id": "evil_persona",
            },
        ).status_code
        == 404
    )

    # Error responses redact live PROJECT_ID
    err_app = create_app(
        packs_dir=packs_dir,
        web_dir=tmp_path / "nonexistent_web",
        bq_client=_FakeBigQueryClient(raise_on_query=RuntimeError(f"Denied on {live_proj}")),
    )
    err_client = TestClient(err_app)
    err_resp = err_client.post(
        "/api/run-rung",
        json={"pack_id": "synthetic_pack", "rung_id": "r1_schema", "mode": "governed", "live": True},
    )
    assert err_resp.status_code == 500
    assert live_proj not in err_resp.text
    assert "example-project-id" in err_resp.text


def test_shell_scripts_syntax_permissions_and_teardown_guards(tmp_path: Path) -> None:
    scripts_dir = DEFAULT_REPO_ROOT / "scripts"
    for script_name in ("provision_pack.sh", "teardown_pack.sh"):
        script_path = scripts_dir / script_name
        assert script_path.is_file()
        assert bool(script_path.stat().st_mode & stat.S_IXUSR), f"{script_name} must be executable"
        syntax_res = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True, check=False)
        assert syntax_res.returncode == 0, syntax_res.stderr

    teardown_path = scripts_dir / "teardown_pack.sh"
    # Placeholder PROJECT_ID must fail closed
    env_placeholder = {k: v for k, v in os.environ.items() if k != "PROJECT_ID"}
    env_placeholder["PROJECT_ID"] = "example-project-id"
    fail_res = subprocess.run(
        ["bash", str(teardown_path), "--dry-run"],
        env=env_placeholder,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_res.returncode != 0

    # Valid non-placeholder PROJECT_ID dry-run succeeds cleanly
    env_ok = dict(os.environ)
    env_ok["PROJECT_ID"] = "sandbox-demo-42"
    env_ok["DATASET_ID"] = "synthetic_ds"
    dry_res = subprocess.run(
        ["bash", str(teardown_path), "--dry-run"],
        env=env_ok,
        capture_output=True,
        text=True,
        check=False,
    )
    assert dry_res.returncode == 0
    assert "[DRY-RUN]" in dry_res.stdout

    # Missing --yes refuses destructive teardown
    refuse_res = subprocess.run(
        ["bash", str(teardown_path)],
        env=env_ok,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refuse_res.returncode != 0

    # Verify provision_pack.sh principal guards (no fallback to active user or developer SA)
    provision_path = scripts_dir / "provision_pack.sh"
    packs_dir = tmp_path / "packs"
    pack_dir = packs_dir / "sentinel_pack"
    pack_dir.mkdir(parents=True)
    (pack_dir / "seed_sentinel.py").write_text(
        "import os, sys\n"
        "print('PROVISION_PRINCIPALS=' + os.environ.get('RLS_CFO_PRINCIPAL', '') + '|' + os.environ.get('RLS_SG_PRINCIPAL', ''))\n"
        "sys.exit(88)\n",
        encoding="utf-8",
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    gcloud_stub = fake_bin / "gcloud"
    sa_suffix = "gserviceaccount" + ".com"
    dev_sa = "12345-compute@" + "developer." + sa_suffix
    valid_sa = "bq-reader@" + "sandbox-demo-42" + ".iam." + sa_suffix
    iam_policy = {
        "bindings": [
            {"role": "roles/editor", "members": [f"serviceAccount:{dev_sa}"]},
            {"role": "roles/bigquery.jobUser", "members": [f"serviceAccount:{valid_sa}"]},
            {"role": "roles/bigquery.dataEditor", "members": [f"serviceAccount:{valid_sa}"]},
        ]
    }
    gcloud_stub.write_text(
        "#!/usr/bin/env bash\n"
        'if [[ -n "${GCLOUD_LOG:-}" ]]; then echo "$*" >> "${GCLOUD_LOG}"; fi\n'
        'if [[ "$*" == *"auth list"* ]]; then\n'
        '  echo "Created enterprise-certificate-proxy configuration file [tmp]."\n'
        '  echo "runner@example.com"\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$*" == *"get-iam-policy"* ]]; then\n'
        '  if [[ "${FAKE_EMPTY_POLICY:-0}" == "1" ]]; then\n'
        '    echo \'{"bindings": [{"role": "roles/editor", "members": ["serviceAccount:' + dev_sa + '"]}]}\'\n'
        "  else\n"
        f"    cat <<'JSON'\n{json.dumps(iam_policy)}\nJSON\n"
        "  fi\n"
        "  exit 0\n"
        "fi\n"
        'if [[ "$*" == *"iam service-accounts describe"* ]]; then\n'
        "  exit 1\n"
        "fi\n"
        'if [[ "$*" == *"iam service-accounts create"* ]]; then\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    gcloud_stub.chmod(0o755)

    base_env = {
        "PATH": f"{fake_bin}:{os.environ.get('PATH', '')}",
        "HOME": os.environ.get("HOME", ""),
        "PROJECT_ID": "sandbox-demo-42",
        "DATASET_ID": "synthetic_ds",
        "PACKS_DIR": str(packs_dir),
    }

    # 1) Empty / developer-SA-only policy without --provision-rls-sas must fail closed
    empty_env = dict(base_env, FAKE_EMPTY_POLICY="1")
    fail_no_sa = subprocess.run(
        ["bash", str(provision_path), "--pack", "sentinel_pack"],
        env=empty_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_no_sa.returncode not in (0, 88)
    assert "Could not resolve a distinct least-privileged customer SA" in fail_no_sa.stderr

    # 2) Equal explicit RLS principals must fail closed
    dup_env = dict(
        base_env,
        RLS_CFO_PRINCIPAL="user:runner@example.com",
        RLS_SG_PRINCIPAL="user:runner@example.com",
    )
    fail_dup = subprocess.run(
        ["bash", str(provision_path), "--pack", "sentinel_pack"],
        env=dup_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert fail_dup.returncode not in (0, 88)
    assert "distinct" in fail_dup.stderr.lower()

    # 3) Zero-flag IAM policy picks least-privileged customer SA with jobUser + dataEditor
    ok_zero_flag = subprocess.run(
        ["bash", str(provision_path), "--pack", "sentinel_pack"],
        env=base_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok_zero_flag.returncode == 88, ok_zero_flag.stderr
    assert f"PROVISION_PRINCIPALS=user:runner@example.com|serviceAccount:{valid_sa}" in ok_zero_flag.stdout

    # 4) --provision-rls-sas creates dedicated least-privilege sandbox SAs with project jobUser
    # + SA-level TokenCreator (never project-wide dataViewer and never touching valid_sa)
    gcloud_log = tmp_path / "gcloud_calls.log"
    opt_in_env = dict(empty_env, GCLOUD_LOG=str(gcloud_log))
    ok_opt_in = subprocess.run(
        ["bash", str(provision_path), "--pack", "sentinel_pack", "--provision-rls-sas"],
        env=opt_in_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert ok_opt_in.returncode == 88, ok_opt_in.stderr
    expected_sg_sa = "meridian-sg-coldchain@" + "sandbox-demo-42" + ".iam." + sa_suffix
    expected_denied_sa = "meridian-denied-probe@" + "sandbox-demo-42" + ".iam." + sa_suffix
    assert (
        f"PROVISION_PRINCIPALS=user:runner@example.com|serviceAccount:{expected_sg_sa}"
    ) in ok_opt_in.stdout
    log_text = gcloud_log.read_text(encoding="utf-8")
    assert "iam service-accounts create meridian-sg-coldchain" in log_text
    assert "iam service-accounts create meridian-denied-probe" in log_text
    assert f"--member=serviceAccount:{expected_sg_sa} --role=roles/bigquery.jobUser" in log_text
    assert f"--member=serviceAccount:{expected_denied_sa} --role=roles/bigquery.jobUser" in log_text
    assert "roles/bigquery.dataViewer" not in log_text
    assert valid_sa not in log_text
    assert "iam service-accounts add-iam-policy-binding " + expected_sg_sa in log_text
    assert "iam service-accounts add-iam-policy-binding " + expected_denied_sa in log_text
    assert "--role=roles/iam.serviceAccountTokenCreator" in log_text

    # 5) teardown_pack.sh --dry-run --delete-rls-sas surfaces dedicated SA cleanup
    td_sas = subprocess.run(
        ["bash", str(teardown_path), "--dry-run", "--delete-rls-sas"],
        env=env_ok,
        capture_output=True,
        text=True,
        check=False,
    )
    assert td_sas.returncode == 0
    assert "meridian-sg-coldchain" in td_sas.stdout
    assert "meridian-denied-probe" in td_sas.stdout

    # Ensure CLI module executes cleanly
    help_res = subprocess.run(
        [sys.executable, "-m", "engine.capture_rungs", "--help"],
        cwd=str(DEFAULT_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_res.returncode == 0
    assert "--offline-fixture" in help_res.stdout


def test_phase2_pack_loader_helpers_and_rls_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engine.pack_loader import (
        discover_rls_target,
        load_context_layer,
        parse_bool_flag,
        resolve_phase2_settings,
    )

    assert parse_bool_flag("true", default=False) is True
    assert parse_bool_flag("0", default=True) is False
    assert parse_bool_flag(None, default=True) is True
    assert parse_bool_flag("flase", default=True, on_invalid=False) is False
    assert parse_bool_flag("tyop", default=True, on_invalid=True) is True

    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=tmp_path / "missing.env")
    assert settings["BLIND_DATASET_ID"]
    assert settings["AGENT_MODEL_ID"] == "gemini-3.8-flash"
    assert settings["AGENT_MODEL_LOCATION"] == "global"

    packs_dir = tmp_path / "packs"
    p_dir = packs_dir / "acme_test"
    (p_dir / "sql").mkdir(parents=True)
    (p_dir / "sql" / "03_rls.sql").write_text(
        "CREATE OR REPLACE ROW ACCESS POLICY rls_cfo_all ON `${PROJECT_ID}.${DATASET_ID}.mart_test_r2` GRANT TO ('user:a@example.com') FILTER USING (TRUE);",
        encoding="utf-8",
    )
    (p_dir / "context_layer.yaml").write_text(
        "glossary:\n  glossary_id: '${DATASET_ID}-gloss'\n  location: '${BQ_LOCATION}'\n",
        encoding="utf-8",
    )
    ctx = load_context_layer(
        "acme_test",
        packs_dir=packs_dir,
        project_id="example-project-id",
        dataset_id="acme_ds",
        bq_location="asia-southeast1",
    )
    assert ctx["glossary"]["glossary_id"] == "acme_ds-gloss"
    tbl, pol = discover_rls_target("acme_test", packs_dir=packs_dir)
    assert tbl == "mart_test_r2"
    assert pol == "rls_cfo_all"


def test_overview_schema_optional_maxlength_and_no_spoilers(tmp_path: Path) -> None:
    import re
    from engine.pack_loader import load_schema, validate_bundle

    # 1) Backward compatibility: pack without overview validates cleanly
    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir, pack_id="no_overview_pack")
    no_ov_bundle = load_pack("no_overview_pack", packs_dir=packs_dir)
    assert "overview" not in no_ov_bundle
    validate_bundle(no_ov_bundle)

    # 2) maxLength enforcement on overview fields
    valid_ov = {
        "eyebrow": "Executive Briefing",
        "headline": "Same Model. Two Different Realities.",
        "subheadline": "How governed enterprise context eliminates raw schema hallucinations.",
        "company_name": "Acme Sample",
        "company_profile": "A regional retail operator closing Q1 across multiple markets.",
        "problem_statement": "Raw schemas scale plausible SQL errors across ambiguous columns and joins.",
        "estate_stats": [
            {"value": "50 Tables", "label": "Sample Estate", "detail": "Core marts + legacy snapshots"},
            {"value": "5 Layers", "label": "Context Stack", "detail": "Schemas, Glossary, Graph, RLS, Contracts"},
        ],
        "experiment": {
            "fixed_control": "Held constant: the same Gemini model and 6 benchmark questions.",
            "blind_arm": "Raw physical schema only with zero glossary or contract overlays.",
            "governed_arm": "Progressive enterprise context via Knowledge Catalog and Property Graph.",
        },
        "cta_label": "Start Simulation · R1 →",
    }
    with_ov = dict(no_ov_bundle, overview=valid_ov)
    validate_bundle(with_ov)

    for bad_field, bad_val in (
        ("headline", "X" * 71),
        ("subheadline", "Y" * 141),
        ("cta_label", "Z" * 49),
        ("company_profile", "P" * 281),
    ):
        bad_ov = dict(valid_ov, **{bad_field: bad_val})
        with pytest.raises(ValidationError):
            validate_bundle(dict(no_ov_bundle, overview=bad_ov))

    # 3) Meridian pack & exported bundle: schema valid, Knowledge Catalog wording, zero spoilers, empirical preserved
    meridian_bundle = load_pack(
        "meridian_q3_sgd",
        project_id="example-project-id",
        dataset_id="meridian_commerce",
        bq_location="asia-southeast1",
    )
    assert "overview" in meridian_bundle
    validate_bundle(meridian_bundle, schema_path=DEFAULT_REPO_ROOT / "schemas" / "rung_v2.schema.json")

    bundle_js_path = DEFAULT_REPO_ROOT / "web" / "data" / "rungs_bundle.js"
    raw_js = bundle_js_path.read_text(encoding="utf-8")
    match = re.search(r"window\.CONTEXT_PACK_BUNDLE\s*=\s*(\{.*\})\s*;", raw_js, re.DOTALL)
    assert match is not None
    exported = json.loads(match.group(1))
    jsonschema_schema = load_schema(DEFAULT_REPO_ROOT / "schemas" / "rung_v2.schema.json")
    assert "overview" in jsonschema_schema["properties"]
    assert exported.get("generated_mode") == "live_agent_verified"
    assert isinstance(exported.get("overview"), dict)

    ov_blob = json.dumps(exported["overview"], ensure_ascii=False)
    assert "dataplex" not in ov_blob.lower()
    assert "Knowledge Catalog" in ov_blob

    forbidden_spoilers = {
        "28/30",
        "0/30",
        "1,312,450",
        "612.50",
        "31.8%",
        "18,960",
        "28.4%",
        "19,380",
        "93.3%",
    }
    total_blind_emp = 0
    total_gov_emp = 0
    total_runs_emp = 0
    for rung in exported["rungs"]:
        for arm in ("blind", "governed"):
            outcome = rung[arm]
            assert isinstance(outcome.get("empirical_eval"), dict), f"Missing empirical_eval on {rung['id']}.{arm}"
            emp = outcome["empirical_eval"]
            if arm == "blind":
                total_blind_emp += int(emp["pass_count"])
            else:
                total_gov_emp += int(emp["pass_count"])
                total_runs_emp += int(emp["runs"])
            forbidden_spoilers.add(str(outcome["answer_headline"]))
            val = float(outcome["numeric_value"])
            if abs(val) >= 100:
                forbidden_spoilers.add(f"{val:,.2f}")
                forbidden_spoilers.add(f"{int(round(val)):,}")
                forbidden_spoilers.add(str(int(round(val))))
            else:
                forbidden_spoilers.add(f"{val:.1f}%")
            forbidden_spoilers.add(f"{outcome['eval_pass_count']}/{outcome['eval_total_runs']}")
            forbidden_spoilers.add(f"{emp['pass_count']}/{emp['runs']}")
    if total_runs_emp > 0:
        forbidden_spoilers.add(f"{total_blind_emp}/{total_runs_emp}")
        forbidden_spoilers.add(f"{total_gov_emp}/{total_runs_emp}")

    for token in sorted(forbidden_spoilers):
        if token:
            assert token not in ov_blob, f"Spoiler token {token!r} leaked into bundle.overview"

    # Also ensure stage_story.step_title and stage_story.backend_layer (rendered on Overview) contain zero spoilers
    for rung in exported["rungs"]:
        stage_story = rung.get("stage_story")
        if isinstance(stage_story, dict):
            overview_story_blob = " ".join(
                str(stage_story.get(k, "")) for k in ("step_title", "backend_layer")
            )
            for token in sorted(forbidden_spoilers):
                if token:
                    assert token not in overview_story_blob, (
                        f"Spoiler token {token!r} leaked into {rung['id']}.stage_story Overview fields"
                    )


def test_stage_readability_schema_enum_and_maxlength_bounds(tmp_path: Path) -> None:
    from copy import deepcopy
    from engine.pack_loader import validate_bundle

    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir, pack_id="stage_schema_pack")
    base_bundle = load_pack("stage_schema_pack", packs_dir=packs_dir)
    validate_bundle(base_bundle)

    # Valid optional Stage readability fields
    valid_bundle = deepcopy(base_bundle)
    valid_bundle["rungs"][0]["difficulty_tier"] = "Easy"
    valid_bundle["rungs"][0]["blind"]["stage_delta_pill"] = "+25.0% Overstated"
    valid_bundle["rungs"][0]["blind"]["stage_summary"] = "Concise human summary without SQL identifiers."
    valid_bundle["rungs"][0]["governed"]["stage_delta_pill"] = "Board-Ready"
    valid_bundle["rungs"][0]["governed"]["stage_summary"] = "Verified executive answer."
    validate_bundle(valid_bundle)

    # Invalid difficulty_tier enum
    bad_tier = deepcopy(valid_bundle)
    bad_tier["rungs"][0]["difficulty_tier"] = "Expert"
    with pytest.raises(ValidationError):
        validate_bundle(bad_tier)

    # Exceeding stage_summary maxLength (220)
    bad_summary = deepcopy(valid_bundle)
    bad_summary["rungs"][0]["blind"]["stage_summary"] = "S" * 221
    with pytest.raises(ValidationError):
        validate_bundle(bad_summary)

    # Exceeding stage_delta_pill maxLength (48)
    bad_pill = deepcopy(valid_bundle)
    bad_pill["rungs"][0]["governed"]["stage_delta_pill"] = "P" * 49
    with pytest.raises(ValidationError):
        validate_bundle(bad_pill)


def test_stage_story_and_closing_takeaways_schema_bounds(tmp_path: Path) -> None:
    from copy import deepcopy
    from engine.pack_loader import validate_bundle

    packs_dir = tmp_path / "packs"
    _write_synthetic_pack(packs_dir, pack_id="story_schema_pack")
    base_bundle = load_pack("story_schema_pack", packs_dir=packs_dir)

    valid_story = {
        "step_title": "Verify Q1 Domestic Net Realized Revenue",
        "backend_layer": "Layers 1–2 · BigQuery Schema & Insights",
        "audience_role": "Chief Financial Officer",
        "situation": "Board close requires exact net realized revenue excluding cancelled orders.",
        "business_goal": "Confirm board-ready revenue before filing.",
        "tech_challenge": "Raw gross columns sweep in tax and cancellations.",
        "context_unlock": "Catalog descriptions lock net column and status filter.",
    }
    valid_closing = {
        "eyebrow": "Executive Takeaways",
        "headline": "Same AI Model. Governed Context Wins.",
        "repo_url": "https://github.com/example/context-demo",
        "repo_label": "Run the 6-rung benchmark yourself",
        "qr_svg_data_uri": "data:image/svg+xml;base64,PHN2Zy8+",
        "takeaways": [
            {"title": "Schema Grounding", "detail": "Eliminates gross vs. net guesswork."},
            {"title": "Semantic Consistency", "detail": "Locks KPI definitions across teams."},
            {"title": "Policy Enforcement", "detail": "BigQuery RLS enforces identity boundaries."},
        ],
    }

    good_bundle = deepcopy(base_bundle)
    good_bundle["rungs"][0]["stage_story"] = valid_story
    good_bundle["closing_takeaways"] = valid_closing
    validate_bundle(good_bundle)

    # stage_story maxLength bounds
    story_max_lengths = {
        "step_title": 70,
        "backend_layer": 56,
        "audience_role": 56,
        "situation": 180,
        "business_goal": 140,
        "tech_challenge": 140,
        "context_unlock": 72,
    }
    for field, limit in story_max_lengths.items():
        bad_story_bundle = deepcopy(good_bundle)
        bad_story_bundle["rungs"][0]["stage_story"] = dict(valid_story, **{field: "X" * (limit + 1)})
        with pytest.raises(ValidationError):
            validate_bundle(bad_story_bundle)

    # closing_takeaways.qr_svg_data_uri regex validation
    for bad_uri in (
        "data:image/png;base64,iVBORw0KGgo=",
        "data:image/svg+xml,<svg></svg>",
        "javascript:alert(1)",
        "https://example.org/qr.svg",
        "data:image/svg+xml;base64,not valid!@#",
    ):
        bad_qr_bundle = deepcopy(good_bundle)
        bad_qr_bundle["closing_takeaways"] = dict(valid_closing, qr_svg_data_uri=bad_uri)
        with pytest.raises(ValidationError):
            validate_bundle(bad_qr_bundle)

    # closing_takeaways.repo_url must be https://
    bad_url_bundle = deepcopy(good_bundle)
    bad_url_bundle["closing_takeaways"] = dict(valid_closing, repo_url="http://example.com/demo")
    with pytest.raises(ValidationError):
        validate_bundle(bad_url_bundle)

