"""Contract tests for packs/cymbal_cmo_q4_sgd and Meridian default preservation."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
import pytest

from engine.pack_loader import load_pack, load_raw_pack, validate_bundle
from server.app import create_app

EXPECTED_RUNG_IDS = [
    "r1_net_revenue",
    "r2_return_drivers",
    "r3_channel_pnl",
    "r4_fraud_graph",
    "r5_clawback_s3_pdf",
    "r6_q4_forecast",
]

_UNQUALIFIED_DATASET_RE = re.compile(r"(?<!\$\{PROJECT_ID\}\.)\b(?:cymbal_dw|cymbal_commerce|cymbal_lake)\.")
_CTE_NAME_RE = re.compile(r"(?:\bWITH\s+|,\s*)([a-z0-9_]+)\s+AS\s*\(", re.IGNORECASE)
_BARE_TABLE_RE = re.compile(
    r"(?:\b(?:FROM|JOIN)\s+|\bGRAPH_TABLE\s*\(\s*)`?((?:campaign_|fraud_|q3_|q4_|agency_|erp_|cymbal_fraud_graph)[a-z0-9_]*)",
    re.IGNORECASE,
)


def _find_bare_table_ref(sql: str) -> str | None:
    cte_names = {m.group(1).lower() for m in _CTE_NAME_RE.finditer(sql)}
    for match in _BARE_TABLE_RE.finditer(sql):
        if match.group(1).lower() not in cte_names:
            return match.group(0)
    return None


def test_cymbal_pack_schema_and_rung_ids() -> None:
    raw = load_raw_pack("cymbal_cmo_q4_sgd")
    validate_bundle(raw)
    rendered = load_pack("cymbal_cmo_q4_sgd")
    assert [r["id"] for r in rendered["rungs"]] == EXPECTED_RUNG_IDS


def test_cymbal_sql_uses_fully_qualified_tables_only() -> None:
    assert _find_bare_table_ref("SELECT * FROM ok JOIN campaign_clicks_raw USING (id)") is not None
    assert _find_bare_table_ref("SELECT * FROM GRAPH_TABLE(cymbal_fraud_graph MATCH (n))") is not None
    assert _find_bare_table_ref("WITH q3_totals AS (SELECT 1) SELECT * FROM a CROSS JOIN q3_totals") is None
    raw = load_raw_pack("cymbal_cmo_q4_sgd")
    for rung in raw["rungs"]:
        for arm in ("blind", "governed"):
            sql = rung[arm]["sql_or_gql"]
            assert _UNQUALIFIED_DATASET_RE.search(sql) is None, f"Unqualified dataset in {rung['id']}.{arm}"
            bare = _find_bare_table_ref(sql)
            assert bare is None, f"Bare table {bare!r} in {rung['id']}.{arm}"


def test_meridian_remains_default_when_pack_id_set(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PACK_ID", "meridian_q3_sgd")
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "none")
    client = TestClient(create_app(env_file=tmp_path / "nonexistent.env"))
    res = client.get("/api/poll/state")
    assert res.status_code == 200
    assert res.json()["pack_id"] == "meridian_q3_sgd"


def test_meridian_remains_default_when_pack_id_unset(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PACK_ID", raising=False)
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    monkeypatch.setenv("FIRESTORE_DATABASE_ID", "none")
    client = TestClient(create_app(env_file=tmp_path / "nonexistent.env"))
    res = client.get("/api/poll/state")
    assert res.status_code == 200
    assert res.json()["pack_id"] == "meridian_q3_sgd"

    # Also verify fallback branch when resolved settings contain empty PACK_ID
    # (cymbal_cmo_q4_sgd sorts before meridian_q3_sgd alphabetically).
    import sys

    app_mod = sys.modules["server.app"]
    orig_resolve = app_mod.resolve_phase2_settings
    monkeypatch.setattr(
        app_mod,
        "resolve_phase2_settings",
        lambda *args, **kwargs: {**orig_resolve(*args, **kwargs), "PACK_ID": ""},
    )
    fallback_client = TestClient(app_mod.create_app(env_file=tmp_path / "nonexistent.env"))
    fallback_res = fallback_client.get("/api/poll/state")
    assert fallback_res.status_code == 200
    assert fallback_res.json()["pack_id"] == "meridian_q3_sgd"
