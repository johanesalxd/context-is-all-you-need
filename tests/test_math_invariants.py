"""End-to-end schema, determinism, SQL execution, and cross-rung invariant tests."""

from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys

import jsonschema
import pytest
import yaml

from packs.meridian_q3_sgd import seed_meridian

REPO_ROOT = Path(__file__).resolve().parents[1]
PACK_DIR = REPO_ROOT / "packs" / "meridian_q3_sgd"
SCHEMA_PATH = REPO_ROOT / "schemas" / "rung_v2.schema.json"


def _load_assembled_pack() -> tuple[dict, dict]:
    pack_meta = yaml.safe_load((PACK_DIR / "pack.yaml").read_text(encoding="utf-8"))
    rung_files = sorted((PACK_DIR / "rungs").glob("*.yaml"))
    rungs = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in rung_files]
    rungs.sort(key=lambda r: r["rung_num"])
    bundle = dict(pack_meta)
    bundle["rungs"] = rungs
    return pack_meta, bundle


def _create_sqlite_db(tables: dict[str, list[dict]]) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE customers (
            customer_id TEXT PRIMARY KEY,
            country_code TEXT NOT NULL,
            tier_code TEXT NOT NULL,
            segment_label TEXT NOT NULL,
            trailing_12m_spend_sgd REAL NOT NULL,
            return_rate REAL NOT NULL,
            channel_pref TEXT NOT NULL
        );
        CREATE TABLE cold_chain_batches (
            batch_id TEXT PRIMARY KEY,
            supplier_tier TEXT NOT NULL,
            vendor_name TEXT NOT NULL,
            temp_peak_celsius REAL NOT NULL,
            excursion_duration_min INTEGER NOT NULL,
            shipment_invoice_sgd REAL NOT NULL,
            batch_status TEXT NOT NULL
        );
        CREATE TABLE sku_lot_allocations (
            lot_id TEXT PRIMARY KEY,
            batch_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            temp_sensitive_class TEXT NOT NULL
        );
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            country_code TEXT NOT NULL,
            sales_channel TEXT NOT NULL,
            fulfillment_tier TEXT NOT NULL,
            order_date TEXT NOT NULL,
            order_status TEXT NOT NULL,
            amt_gross_billed_sgd REAL NOT NULL,
            amt_item_subtotal_sgd REAL NOT NULL,
            amt_gst_sgd REAL NOT NULL,
            fulfillment_fee_sgd REAL NOT NULL,
            amt_net_settled_sgd REAL NOT NULL
        );
        CREATE TABLE order_lines (
            order_line_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            sku_id TEXT NOT NULL,
            lot_id TEXT NOT NULL,
            qty INTEGER NOT NULL,
            gross_line_sgd REAL NOT NULL,
            gst_line_sgd REAL NOT NULL,
            returned_line_sgd REAL NOT NULL,
            net_line_revenue_sgd REAL NOT NULL,
            cogs_line_sgd REAL NOT NULL
        );
        CREATE TABLE parcel_legs (
            leg_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            hub_code TEXT NOT NULL,
            carrier_vendor TEXT NOT NULL,
            leg_seq INTEGER NOT NULL,
            leg_cost_sgd REAL NOT NULL,
            temp_excursion_celsius REAL NOT NULL,
            excursion_minutes INTEGER NOT NULL
        );
        CREATE TABLE mart_coldchain_q3_r2 (
            country_code TEXT NOT NULL,
            quarter TEXT NOT NULL,
            net_revenue_sgd REAL NOT NULL,
            gross_margin_sgd REAL NOT NULL,
            gross_margin_pct REAL NOT NULL,
            close_batch_code TEXT NOT NULL
        );
        CREATE TABLE mart_coldchain_q3_r1 (
            country_code TEXT NOT NULL,
            quarter TEXT NOT NULL,
            net_revenue_sgd REAL NOT NULL,
            gross_margin_sgd REAL NOT NULL,
            gross_margin_pct REAL NOT NULL,
            close_batch_code TEXT NOT NULL
        );
        CREATE TABLE vendor_sla_ledger (
            event_id TEXT PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            contract_id TEXT NOT NULL,
            sku_class TEXT NOT NULL,
            quarter TEXT NOT NULL,
            shipment_ref TEXT NOT NULL,
            temp_peak_celsius REAL NOT NULL,
            excursion_duration_min INTEGER NOT NULL,
            shipment_invoice_sgd REAL NOT NULL,
            base_temp_threshold_c REAL NOT NULL,
            base_duration_min INTEGER NOT NULL,
            base_credit_rate REAL NOT NULL
        );
        CREATE TABLE sla_overlay (
            overlay_id TEXT PRIMARY KEY,
            vendor_name TEXT NOT NULL,
            amendment_ref TEXT NOT NULL,
            source_doc_path TEXT NOT NULL,
            sku_class TEXT NOT NULL,
            effective_date TEXT NOT NULL,
            temp_threshold_c REAL NOT NULL,
            duration_threshold_min INTEGER NOT NULL,
            credit_rate REAL NOT NULL,
            quarterly_cap_sgd REAL NOT NULL,
            extraction_tokens INTEGER NOT NULL,
            verified_by TEXT NOT NULL
        );
        """
    )

    for table_name, rows in tables.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        placeholders = ", ".join(f":{c}" for c in cols)
        col_list = ", ".join(cols)
        cur.executemany(
            f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})",
            rows,
        )
    conn.commit()
    return conn


def _to_sqlite_sql(bq_sql: str) -> str:
    sql = bq_sql.replace("`${PROJECT_ID}.${DATASET_ID}.", "`").replace(
        "${PROJECT_ID}.${DATASET_ID}.", ""
    )
    sql = re.sub(r"\bDATE\s+'(\d{4}-\d{2}-\d{2})'", r"'\1'", sql)
    return sql


def test_pack_validates_against_rung_v2_schema() -> None:
    pack_meta, bundle = _load_assembled_pack()
    assert "rungs" not in pack_meta, "pack.yaml must omit rungs so pack_loader.py populates them"
    assert len(bundle["rungs"]) == 6

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(bundle)


def test_naming_and_release_stage_honesty() -> None:
    _, bundle = _load_assembled_pack()
    assert bundle["hero_tagline"] == (
        "Frontier models are table stakes—governed enterprise context is the differentiator."
    )
    serialized = json.dumps(bundle)
    assert "Dataplex" not in serialized
    assert "rented commodities" not in serialized.lower()

    rungs_by_num = {r["rung_num"]: r for r in bundle["rungs"]}
    assert rungs_by_num[1]["governed"]["eval_pass_count"] == 4
    assert rungs_by_num[1]["governed"]["trust_tier"] == "TIER_2_GROUNDED"
    assert rungs_by_num[2]["governed"]["eval_pass_count"] == 5
    assert rungs_by_num[2]["governed"]["trust_tier"] == "TIER_2_GROUNDED"
    for rnum in (3, 4, 5, 6):
        assert rungs_by_num[rnum]["governed"]["eval_pass_count"] == 5
        assert rungs_by_num[rnum]["governed"]["trust_tier"] == "TIER_1_VERIFIED_OR_COMPILED"

    r1_badges = {b["capability"]: b for b in rungs_by_num[1]["release_badges"]}
    assert r1_badges["Knowledge Catalog lookupContext"]["stage"] == "Preview"
    assert r1_badges["BigQuery Schema + Data Insights"]["region_scope"] == "asia-southeast1"
    assert r1_badges["Gemini PayGo Inference"]["stage"] == "GA"
    assert r1_badges["Gemini PayGo Inference"]["region_scope"] == "global endpoint"

    eval_meth = bundle.get("eval_methodology", {})
    assert "asia-southeast1" in eval_meth.get("regional_honesty_label", "")
    assert "global" in eval_meth.get("regional_honesty_label", "").lower()

    for rnum in range(1, 7):
        assert "grading" in rungs_by_num[rnum], f"Missing grading block on R{rnum}"
        badges = {b["capability"]: b for b in rungs_by_num[rnum]["release_badges"]}
        assert any("global" in b["region_scope"].lower() for b in badges.values())
        assert any("asia-southeast1" in b["region_scope"] for b in badges.values())

    assert rungs_by_num[1]["grading"] == {
        "target_value": 1312450.0,
        "tolerance": 0.01,
        "unit": "SGD",
    }
    assert rungs_by_num[2]["grading"] == {
        "target_value": 612.5,
        "tolerance": 0.01,
        "required_strings": ["B2B Corporate Portal"],
    }
    assert rungs_by_num[3]["grading"] == {
        "target_value": 31.8,
        "tolerance": 0.1,
        "allow_ratio_normalization": True,
    }
    assert rungs_by_num[4]["grading"] == {
        "target_value": 28.4,
        "tolerance": 0.1,
        "allow_ratio_normalization": True,
        "disallowed_tables": ["mart_coldchain_q3_r1"],
        "persona_targets": {
            "cfo_regional": {"value": 842600.0, "tolerance": 0.01},
            "sg_coldchain": {"value": 346480.0, "tolerance": 0.01},
        },
    }
    assert rungs_by_num[5]["grading"] == {
        "target_value": 19380.0,
        "tolerance": 0.01,
        "secondary_numerics": [{"name": "exposed_order_count", "value": 38, "tolerance": 0}],
    }
    assert rungs_by_num[6]["grading"] == {
        "target_value": 18960.0,
        "tolerance": 0.01,
        "secondary_numerics": [{"name": "qualifying_shipments", "value": 14, "tolerance": 0}],
    }

    horizon = {c["id"]: c for c in bundle["horizon_cards"]}
    assert horizon["knowledge_studio"]["release_badge"] == "Preview"
    assert (
        horizon["knowledge_studio"]["region_availability"]
        == "US / EU multi-regions (Preview; not yet in asia-southeast1)"
    )
    assert horizon["open_lakehouse_federation"]["release_badge"] == "GA"
    fed_text = json.dumps(horizon["open_lakehouse_federation"])
    assert "Workload Identity Federation" in fed_text
    assert "per-user OIDC" in fed_text
    assert "Snowflake Horizon Catalog via per-user OIDC" not in fed_text


def test_seed_determinism_and_invariants_tie_out() -> None:
    ds1 = seed_meridian.generate_dataset(seed=20261126)
    ds2 = seed_meridian.generate_dataset(seed=20261126)
    assert ds1 == ds2

    pack_meta, _ = _load_assembled_pack()
    computed = seed_meridian.evaluate_invariants(ds1, seed=20261126)
    assert computed == pack_meta["invariants"]


def test_seed_cli_flags(tmp_path: Path) -> None:
    out_dir = tmp_path / "jsonl"
    verify = subprocess.run(
        [sys.executable, str(PACK_DIR / "seed_meridian.py"), "--verify-json", "--output-dir", str(out_dir)],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(verify.stdout)
    assert payload["verified"] is True
    assert payload["max_discrepancy"] == 0.0
    assert payload["mismatches"] == {}
    for table_name in payload["row_counts"]:
        jsonl = out_dir / f"{table_name}.jsonl"
        assert jsonl.exists()
        assert len(jsonl.read_text(encoding="utf-8").splitlines()) == payload["row_counts"][table_name]

    shadow = subprocess.run(
        [sys.executable, str(PACK_DIR / "seed_meridian.py"), "--emit-shadow-ddl"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert shadow.stdout.count("CREATE TABLE IF NOT EXISTS") == 190
    assert "shadow_auto_tbl_001" in shadow.stdout
    assert "shadow_auto_tbl_190" in shadow.stdout


def test_sql_execution_of_rungs_in_sqlite() -> None:
    tables = seed_meridian.generate_dataset(seed=20261126)
    _, bundle = _load_assembled_pack()
    rungs = {r["rung_num"]: r for r in bundle["rungs"]}
    conn = _create_sqlite_db(tables)

    try:
        # Structural integrity: 0.00 header-to-line drift on COMPLETED orders
        drift_row = conn.execute(
            """
            SELECT
              MAX(ABS(ROUND(ol_sum, 2) - ROUND(o.amt_net_settled_sgd, 2))) AS max_drift,
              ABS(SUM(ol_sum) - SUM(o.amt_net_settled_sgd)) AS agg_drift
            FROM orders AS o
            JOIN (
              SELECT order_id, SUM(net_line_revenue_sgd) AS ol_sum
              FROM order_lines
              GROUP BY order_id
            ) AS l USING (order_id)
            WHERE o.order_status = 'COMPLETED'
            """
        ).fetchone()
        assert round(drift_row["max_drift"], 2) == 0.0
        assert round(drift_row["agg_drift"], 2) == 0.0

        # ERP schema ambiguity invariants on orders
        erp_check = conn.execute(
            """
            SELECT
              SUM(amt_item_subtotal_sgd) AS all_subtotal,
              SUM(CASE WHEN order_status != 'COMPLETED' THEN amt_item_subtotal_sgd ELSE 0.0 END) AS noncomp_subtotal,
              SUM(CASE WHEN order_status != 'COMPLETED' THEN amt_net_settled_sgd ELSE 0.0 END) AS noncomp_settled,
              MIN(CASE WHEN order_status != 'COMPLETED' THEN amt_item_subtotal_sgd ELSE NULL END) AS min_noncomp_subtotal,
              SUM(CASE WHEN order_status = 'COMPLETED' THEN amt_item_subtotal_sgd ELSE 0.0 END) AS comp_subtotal
            FROM orders
            WHERE country_code = 'SG'
              AND order_date BETWEEN '2026-07-01' AND '2026-09-30'
            """
        ).fetchone()
        assert erp_check["all_subtotal"] == pytest.approx(1545137.73, abs=0.01)
        assert erp_check["noncomp_settled"] == pytest.approx(0.0, abs=1e-6)
        assert erp_check["min_noncomp_subtotal"] > 0.0
        assert erp_check["comp_subtotal"] > 1312450.00  # partial returns remain inside amt_item_subtotal_sgd

        # R1 Blind & Governed
        r1_blind = conn.execute(_to_sqlite_sql(rungs[1]["blind"]["sql_or_gql"])).fetchone()
        r1_gov = conn.execute(_to_sqlite_sql(rungs[1]["governed"]["sql_or_gql"])).fetchone()
        assert r1_blind["amt_gross_billed_sgd"] == pytest.approx(1684200.00, abs=0.01)
        assert r1_gov["amt_net_settled_sgd"] == pytest.approx(1312450.00, abs=0.01)
        assert r1_gov["completed_order_count"] == 3400

        # R2 Blind & Governed + Glossary thresholds + overall 640 orders / 495.63 AOV
        r2_blind = conn.execute(_to_sqlite_sql(rungs[2]["blind"]["sql_or_gql"])).fetchone()
        r2_gov = conn.execute(_to_sqlite_sql(rungs[2]["governed"]["sql_or_gql"])).fetchone()
        assert r2_blind["sales_channel"] == "Mobile App"
        assert r2_blind["aov_sgd"] == pytest.approx(284.10, abs=0.01)
        assert r2_gov["sales_channel"] == "B2B Corporate Portal"
        assert r2_gov["order_count"] == 240
        assert r2_gov["total_net_revenue_sgd"] == pytest.approx(147000.00, abs=0.01)
        assert r2_gov["aov_sgd"] == pytest.approx(612.50, abs=0.01)

        bad_hv = conn.execute(
            """
            SELECT COUNT(*) AS cnt FROM customers
            WHERE tier_code = 'PRM_HV' AND (trailing_12m_spend_sgd < 5000.0 OR return_rate >= 0.08)
            """
        ).fetchone()
        assert bad_hv["cnt"] == 0

        r2_all_hv = conn.execute(
            """
            SELECT COUNT(*) AS cnt, ROUND(SUM(o.amt_net_settled_sgd), 2) AS rev,
                   ROUND(AVG(o.amt_net_settled_sgd), 2) AS aov
            FROM orders o JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.country_code = 'SG' AND o.order_status = 'COMPLETED' AND c.tier_code = 'PRM_HV'
            """
        ).fetchone()
        assert r2_all_hv["cnt"] == 640
        assert r2_all_hv["rev"] == pytest.approx(317203.20, abs=0.01)
        assert r2_all_hv["aov"] == pytest.approx(495.63, abs=0.01)

        # R3 Blind (3-way JOIN) & Grain-Locked SAME_DAY equivalent
        r3_blind = conn.execute(_to_sqlite_sql(rungs[3]["blind"]["sql_or_gql"])).fetchone()
        assert r3_blind["contribution_margin_pct"] == pytest.approx(14.2, abs=0.05)

        leg_bounds = conn.execute(
            """
            SELECT MIN(leg_cnt) AS min_legs, MAX(leg_cnt) AS max_legs
            FROM (
              SELECT o.order_id, COUNT(pl.leg_id) AS leg_cnt
              FROM orders o JOIN parcel_legs pl ON o.order_id = pl.order_id
              WHERE o.country_code = 'SG' AND o.order_status = 'COMPLETED'
                AND o.fulfillment_tier = 'SAME_DAY'
              GROUP BY o.order_id
            )
            """
        ).fetchone()
        assert leg_bounds["min_legs"] >= 2
        assert leg_bounds["max_legs"] <= 4

        r3_gov = conn.execute(
            """
            WITH line_m AS (
              SELECT order_id, SUM(cogs_line_sgd) AS cogs_sgd
              FROM order_lines GROUP BY order_id
            ),
            leg_m AS (
              SELECT order_id, SUM(leg_cost_sgd) AS leg_cost_sgd
              FROM parcel_legs GROUP BY order_id
            )
            SELECT
              ROUND(100.0 * SUM(o.amt_net_settled_sgd - line_m.cogs_sgd - o.fulfillment_fee_sgd - leg_m.leg_cost_sgd)
                    / SUM(o.amt_net_settled_sgd), 1) AS margin_pct,
              ROUND(SUM(o.amt_net_settled_sgd - line_m.cogs_sgd - o.fulfillment_fee_sgd - leg_m.leg_cost_sgd), 2) AS margin_sgd,
              ROUND(SUM(o.amt_net_settled_sgd), 2) AS rev_sgd
            FROM orders o
            JOIN line_m USING (order_id)
            JOIN leg_m USING (order_id)
            WHERE o.country_code = 'SG' AND o.order_status = 'COMPLETED'
              AND o.fulfillment_tier = 'SAME_DAY'
            """
        ).fetchone()
        assert r3_gov["rev_sgd"] == pytest.approx(412000.00, abs=0.01)
        assert r3_gov["margin_sgd"] == pytest.approx(131016.00, abs=0.01)
        assert r3_gov["margin_pct"] == pytest.approx(31.8, abs=0.05)

        # R4 Blind & Governed + Beat 4b RLS filter verification
        r4_blind = conn.execute(_to_sqlite_sql(rungs[4]["blind"]["sql_or_gql"])).fetchone()
        r4_cfo = conn.execute(_to_sqlite_sql(rungs[4]["governed"]["sql_or_gql"])).fetchone()
        r4_sg = conn.execute(
            _to_sqlite_sql(rungs[4]["governed"]["sql_or_gql"]) + " AND country_code = 'SG'"
        ).fetchone()
        assert r4_blind["gross_margin_pct"] == pytest.approx(24.3, abs=0.05)
        assert r4_cfo["gross_margin_pct"] == pytest.approx(28.4, abs=0.05)
        assert r4_cfo["gross_margin_sgd"] == pytest.approx(842600.00, abs=0.01)
        assert r4_cfo["rows_visible"] == 4
        assert r4_sg["gross_margin_sgd"] == pytest.approx(346480.00, abs=0.01)
        assert r4_sg["rows_visible"] == 1

        # R5 Blind & Governed 4-hop traversal + subset consistency with R2 PRM_HV
        r5_blind = conn.execute(_to_sqlite_sql(rungs[5]["blind"]["sql_or_gql"])).fetchone()
        assert r5_blind["exposed_revenue_sgd"] == pytest.approx(4120.00, abs=0.01)
        assert r5_blind["exposed_order_count"] == 8

        r5_rows = conn.execute(
            """
            SELECT DISTINCT o.order_id, o.amt_net_settled_sgd
            FROM cold_chain_batches b
            JOIN sku_lot_allocations lot ON b.batch_id = lot.batch_id
            JOIN order_lines ol ON lot.lot_id = ol.lot_id
            JOIN orders o ON ol.order_id = o.order_id
            JOIN customers c ON o.customer_id = c.customer_id
            WHERE b.batch_id = '#LN-409' AND b.supplier_tier = 'TIER_2'
              AND o.country_code = 'SG' AND o.order_status = 'COMPLETED'
              AND c.tier_code = 'PRM_HV'
            """
        ).fetchall()
        assert len(r5_rows) == 38
        r5_rev = round(sum(r["amt_net_settled_sgd"] for r in r5_rows), 2)
        assert r5_rev == pytest.approx(19380.00, abs=0.01)
        assert round(r5_rev / len(r5_rows), 2) == pytest.approx(510.00, abs=0.01)

        r2_hv_ids = {
            r["order_id"]
            for r in conn.execute(
                """
                SELECT o.order_id FROM orders o
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.country_code = 'SG' AND o.order_status = 'COMPLETED'
                  AND c.tier_code = 'PRM_HV'
                """
            ).fetchall()
        }
        assert {r["order_id"] for r in r5_rows}.issubset(r2_hv_ids)

        # R6 Blind & Governed SLA recovery
        r6_blind = conn.execute(_to_sqlite_sql(rungs[6]["blind"]["sql_or_gql"])).fetchone()
        r6_gov = conn.execute(_to_sqlite_sql(rungs[6]["governed"]["sql_or_gql"])).fetchone()
        assert r6_blind["recoverable_credit_sgd"] == pytest.approx(1420.00, abs=0.01)
        assert r6_blind["qualifying_breaches"] == 3
        assert r6_gov["recoverable_credit_sgd"] == pytest.approx(18960.00, abs=0.01)
        assert r6_gov["qualifying_shipments"] == 14
    finally:
        conn.close()


def test_sql_property_graph_rls_contracts_and_placeholder_hygiene() -> None:
    sql_dir = PACK_DIR / "sql"
    contracts_dir = PACK_DIR / "contracts"

    pg_sql = (sql_dir / "04_property_graph.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE PROPERTY GRAPH `${PROJECT_ID}.${DATASET_ID}.meridian_supply_graph`" in pg_sql
    assert "LABEL CustomerOrder" in pg_sql
    assert "LABEL Order\n" not in pg_sql  # Avoid unescaped GQL reserved keyword Order
    assert "MEASURE(SUM(amt_net_settled_sgd))" in pg_sql
    assert "MEASURE(SUM(fulfillment_fee_sgd))" in pg_sql
    assert "MEASURE(SUM(cogs_line_sgd))" in pg_sql
    assert "MEASURE(SUM(leg_cost_sgd))" in pg_sql
    # Every MEASURE source column must also be declared as a dimension property
    for col in ("amt_net_settled_sgd", "fulfillment_fee_sgd", "cogs_line_sgd", "leg_cost_sgd"):
        assert pg_sql.count(col) >= 2

    tables_sql = (sql_dir / "01_tables.sql").read_text(encoding="utf-8")
    assert "CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.mart_coldchain_q3_r1`" in tables_sql
    assert "CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.mart_coldchain_q3_r2`" in tables_sql
    for col in (
        "amt_gross_billed_sgd",
        "amt_item_subtotal_sgd",
        "amt_gst_sgd",
        "fulfillment_fee_sgd",
        "amt_net_settled_sgd",
    ):
        assert col in tables_sql

    r5_yaml = yaml.safe_load((PACK_DIR / "rungs" / "r5_graph.yaml").read_text(encoding="utf-8"))
    r5_gql = r5_yaml["governed"]["sql_or_gql"]
    assert "GRAPH_TABLE(" in r5_gql
    assert "FILTER " in r5_gql
    assert "RETURN" in r5_gql
    assert "COLUMNS" not in r5_gql

    rls_sql = (sql_dir / "03_rls.sql").read_text(encoding="utf-8")
    assert "${RLS_CFO_PRINCIPAL}" in rls_sql
    assert "${RLS_SG_PRINCIPAL}" in rls_sql
    assert "ON `${PROJECT_ID}.${DATASET_ID}.mart_coldchain_q3_r2`" in rls_sql
    assert "FILTER USING (TRUE)" in rls_sql
    assert "FILTER USING (country_code = 'SG')" in rls_sql

    shadow_sql = (sql_dir / "02_shadow_clones.sql").read_text(encoding="utf-8")
    assert "staging_cold_chain_oct11" not in shadow_sql
    assert "close_batch_code STRING" in shadow_sql
    assert shadow_sql.count("shadow_auto_tbl_") >= 190
    assert "shadow_auto_tbl_001" in shadow_sql
    assert "shadow_auto_tbl_190" in shadow_sql

    assert (contracts_dir / "ArcticHaul_Amendment_2.md").exists()
    assert (contracts_dir / "ArcticHaul_MSA_2025.md").exists()
    assert (contracts_dir / "SiamFrost_Logistics_MSA_2025.md").exists()
    assert (contracts_dir / "StraitsTemp_Cargo_MSA_2025.md").exists()
    assert (contracts_dir / "sla_overlay.sql").exists()

    # Legacy column and table giveaway names must be completely eliminated from the pack
    legacy_re = re.compile(
        r"\b(net_realized_revenue_sgd|gross_total_sgd|gross_item_sgd|gst_sgd|cold_chain_margin_gold|staging_cold_chain_oct11|rebate_settled|certified_at)\b"
    )
    for path in PACK_DIR.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".yaml", ".sql", ".md"}:
            continue
        if path.name == "context_layer.yaml":
            # Only legacy_tables_to_drop may reference legacy R4 table names
            non_drop_lines = [
                line
                for line in path.read_text(encoding="utf-8").splitlines()
                if "cold_chain_margin_gold" not in line and "staging_cold_chain_oct11" not in line
            ]
            assert not legacy_re.search("\n".join(non_drop_lines)), f"Unexpected legacy name in {path}"
        else:
            assert not legacy_re.search(path.read_text(encoding="utf-8")), f"Legacy name found in {path}"

    # Zero-leak placeholder check across pack files (patterns built without literal leaked strings)
    leak_patterns = [
        re.compile(r"@[g]oogle\.com\b"),
        re.compile(r"altostr[a]t\.com"),
        re.compile(r"\b[a-z0-9-]+\.corp\.[g]oogle\.com"),
        re.compile(r"[g]oogleplex\.com"),
        re.compile(r"//dep[o]t/"),
        re.compile(r"\bgo/[a-z0-9_-]+"),
        re.compile(r"\b[a-z][a-z0-9-]{3,23}-[0-9]{6}\b"),
    ]
    for path in list(PACK_DIR.rglob("*")) + [Path(__file__)]:
        if path.is_file() and path.suffix in {".py", ".yaml", ".sql", ".md"}:
            text = path.read_text(encoding="utf-8")
            for pattern in leak_patterns:
                assert not pattern.search(text), f"Leak pattern {pattern.pattern} matched in {path}"


def test_context_layer_yaml_contract() -> None:
    ctx_path = PACK_DIR / "context_layer.yaml"
    assert ctx_path.exists()
    ctx = yaml.safe_load(ctx_path.read_text(encoding="utf-8"))

    required_keys = {
        "blind_dataset_tables",
        "shadow_table_prefix",
        "shadow_table_count",
        "legacy_tables_to_drop",
        "glossary",
        "aspect_types",
        "data_quality_scans",
        "unstructured_contracts",
        "verified_metric_contracts",
    }
    assert required_keys.issubset(ctx.keys())

    assert ctx["blind_dataset_tables"] == [
        "customers",
        "orders",
        "order_lines",
        "parcel_legs",
        "cold_chain_batches",
        "sku_lot_allocations",
        "mart_coldchain_q3_r1",
        "mart_coldchain_q3_r2",
        "vendor_sla_ledger",
    ]
    for excluded in ("sla_overlay", "sla_overlay_extracted", "contract_docs_obj"):
        assert excluded not in ctx["blind_dataset_tables"]
    assert ctx["shadow_table_prefix"] == "shadow_auto_tbl_"
    assert ctx["shadow_table_count"] == 190
    assert set(ctx["legacy_tables_to_drop"]) == {
        "cold_chain_margin_gold",
        "staging_cold_chain_oct11",
    }

    assert ctx["glossary"]["glossary_id"] == "meridian-commerce-glossary"
    terms = {t["term_id"]: t for t in ctx["glossary"]["terms"]}
    assert "premier-customer" in terms
    assert "PRM_HV" in terms["premier-customer"]["description"]
    assert terms["premier-customer"]["linked_columns"] == [
        {"table": "customers", "column": "tier_code", "link_type": "definition"}
    ]

    aspects = {a["aspect_type_id"]: a for a in ctx["aspect_types"]}
    cert = aspects["data-product-certification"]
    assigns = {a["table"]: a["data"] for a in cert["assignments"]}
    assert assigns["mart_coldchain_q3_r2"]["certification_status"] == "CERTIFIED"
    assert assigns["mart_coldchain_q3_r1"]["certification_status"] == "UNCERTIFIED_STALE"

    dq = {d["scan_id"]: d for d in ctx["data_quality_scans"]}["meridian-coldchain-dq"]
    assert dq["target_table"] == "mart_coldchain_q3_r2"
    assert dq["catalog_publishing_enabled"] is True

    uc = ctx["unstructured_contracts"]
    assert uc["object_table"] == "contract_docs_obj"
    assert uc["extraction_staging_table"] == "sla_overlay_extracted"
    assert uc["fallback_table"] == "sla_overlay"
    assert uc["target_vendor_filter"] == "ArcticHaul"
    assert uc["expected_invariants"] == {
        "temp_threshold_c": 2.0,
        "duration_threshold_min": 45,
        "credit_rate": 0.12,
        "quarterly_cap_sgd": 35000.0,
    }

    vmc = ctx["verified_metric_contracts"]
    assert set(vmc.keys()) == {"r3_metrics", "r5_graph", "r6_contracts"}
    assert "amt_net_settled_sgd" in json.dumps(vmc)
    assert "meridian_supply_graph" in json.dumps(vmc["r5_graph"])
    assert "sla_overlay" in json.dumps(vmc["r6_contracts"])
    # Verified metric contracts describe rules/patterns, never precomputed target sums
    for answer_literal in ("1312450", "19380", "18960"):
        assert answer_literal not in json.dumps(vmc)

