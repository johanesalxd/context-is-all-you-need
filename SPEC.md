# SPEC.md — *Context Is All You Need* Authoritative Architecture & Contract

This specification is the **authoritative Step-0 contract** for building, testing, and verifying the *Context Is All You Need* foundation repository. Every module, SQL/GQL artifact, ScenarioPack YAML, and UI view MUST conform strictly to this specification.

---

## 1. Core Design Goals & Extensibility

1. **Thesis:** *"Frontier models are table stakes—governed enterprise context is the differentiator."* (Never use dismissive "rented commodities" copy.)
2. **Engine vs. Declarative `ScenarioPack` Separation:**
   - `engine/` and `web/` MUST contain **zero** hardcoded `Meridian Commerce` numbers, SQL strings, or persona names.
   - All scenario schemas, synthetic data generators, SQL/GQL queries, audience polls, and expected invariants live inside `packs/<pack_id>/` (starting with `packs/meridian_q3_sgd/`) and validate against `schemas/rung_v2.schema.json`.
   - Adding a new industry pack (`packs/fsi_wealth/`, `packs/aviation_ops/`) or adjusting copy/rungs requires zero edits to `engine/` or `web/`.
3. **Public-Safe Zero-Leak Hygiene:**
   - Repository is Apache-2.0 licensed and 100% customer-agnostic.
   - Never hardcode real GCP project IDs, service account emails, customer names, or internal Google URLs/shortlinks in tracked files. Read `PROJECT_ID`, `BQ_LOCATION`, and `DATASET_ID` strictly from environment variables (`.env.example` defaults to `example-project-id`, `asia-southeast1`, `meridian_commerce`).

---

## 2. Disjoint File Ownership Table (Zero Worktree Collisions)

Concurrent builders MUST modify ONLY their assigned paths:

| Track / Role | Owned Paths (Strict Write Scope) | Forbidden Paths |
| :--- | :--- | :--- |
| **Step 0 (Coordinator Locked)** | `SPEC.md`, `schemas/rung_v2.schema.json`, `pyproject.toml`, `uv.lock`, `.env.example`, `.gitignore`, `LICENSE` | Modified only by Coordinator if schema evolution is explicitly required. |
| **`pack-meridian`** | `packs/meridian_q3_sgd/**`, `tests/test_math_invariants.py` | `engine/**`, `server/**`, `scripts/**`, `web/**`, `README.md` |
| **`context-engine`** | `engine/**`, `server/**`, `scripts/**`, `tests/test_schema_and_trust.py`, `tests/test_zero_leak.py` | `packs/**`, `web/index.html`, `web/css/**`, `web/js/**`, `README.md` |
| **`stage-ui`** | `web/index.html`, `web/css/**`, `web/js/**`, `README.md`, `tests/test_web_bundle_contract.py` | `packs/**`, `engine/**`, `server/**`, `scripts/**` |
| **`cloud-runner` (Post-Review)** | Merges approved commits on `main`, generates `web/data/rungs_bundle.js` via `engine/capture_rungs.py`, verifies sandbox BigQuery in `asia-southeast1` | Never edits application logic without routing back to the owning author. |

*Bootstrap coordination note on `web/data/rungs_bundle.js`:* `stage-ui` MUST read `window.CONTEXT_PACK_BUNDLE` with a graceful built-in fallback loader or sample check, and `cloud-runner` (or `context-engine` CLI invoked after merge) generates the canonical `web/data/rungs_bundle.js` from `packs/meridian_q3_sgd/`. Neither `pack-meridian` nor `stage-ui` commits `web/data/rungs_bundle.js` on their feature branch so merges have zero conflicts.

---

## 3. Unified Mathematical Invariants (`packs/meridian_q3_sgd/`, Seed `20261126`)

`packs/meridian_q3_sgd/seed_meridian.py` MUST deterministically generate synthetic rows (`random.Random(20261126)`) for Closed Q3 (`2026-07-01` to `2026-09-30`, currency `SGD`, Singapore GST `9%`) that satisfy ALL cross-rung invariants simultaneously, verified both in pure Python (`tests/test_math_invariants.py`) AND when loaded into BigQuery (`asia-southeast1`):

### 3.1 Core Tables & Shadow Estate (`sql/01_tables.sql`, `sql/02_shadow_clones.sql`)
1. `customers` (`customer_id`, `country_code`, `tier_code`, `segment_label`, `trailing_12m_spend_sgd`, `return_rate`, `channel_pref`)
   - Official Business Glossary definition of **Premier** (`Rung 2` & `Rung 5`): `tier_code = 'PRM_HV'` (enforcing `trailing_12m_spend_sgd >= 5000.00 AND return_rate < 0.08`).
   - Distractor trap column: `segment_label` includes `'Premier_Promo_Trial'` on low-value promo accounts so naive `segment_label LIKE '%Premier%'` produces a wrong answer.
2. `orders` (`order_id`, `customer_id`, `country_code`, `sales_channel`, `fulfillment_tier`, `order_date`, `order_status`, `gross_item_sgd`, `gross_total_sgd`, `gst_sgd`, `fulfillment_fee_sgd`, `net_realized_revenue_sgd`)
   - Closed Q3 (`2026-07-01`..`2026-09-30`), markets `SG`, `MY`, `TH`, `ID`.
3. `order_lines` (`order_line_id`, `order_id`, `sku_id`, `lot_id`, `qty`, `gross_line_sgd`, `gst_line_sgd`, `returned_line_sgd`, `net_line_revenue_sgd`, `cogs_line_sgd`)
   - **Exact Header-to-Line Tie-Out:** For every `COMPLETED` order, `SUM(order_lines.net_line_revenue_sgd) == orders.net_realized_revenue_sgd` to `0.01 SGD` (`0.00` aggregate drift).
4. `parcel_legs` (`leg_id`, `order_id`, `hub_code`, `carrier_vendor`, `leg_seq`, `leg_cost_sgd`, `temp_excursion_celsius`, `excursion_minutes`)
   - **`1:N` Fan-Trap (`Rung 3`):** Same-Day orders (`fulfillment_tier = 'SAME_DAY'`) span `2` to `4` parcel transfer legs per order (`1:N` against `orders` and `order_lines`).
5. `cold_chain_batches` (`batch_id`, `supplier_tier`, `vendor_name`, `temp_peak_celsius`, `excursion_duration_min`, `shipment_invoice_sgd`, `batch_status`) & `sku_lot_allocations` (`lot_id`, `batch_id`, `sku_id`, `temp_sensitive_class`)
   - Powers 4-hop supply-chain lineage (`ColdChainBatch -> SkuLotAllocation -> OrderLine -> Order -> Customer`) in `Rung 5`.
6. `cold_chain_margin_gold` (certified Knowledge Catalog Data Product table, `country_code`, `quarter`, `net_revenue_sgd`, `gross_margin_sgd`, `gross_margin_pct`, `rebate_settled`, `certified_at`) vs. `staging_cold_chain_oct11` (stale uncertified clone missing late-Q3 supplier rebate settlements) + **`190` empty script-generated shadow tables** (`shadow_auto_tbl_001` .. `shadow_auto_tbl_190`, generated programmatically by `sql/02_shadow_clones.sql` or `seed_meridian.py --emit-shadow-ddl`).
7. `vendor_sla_ledger` (base contract table encoding legacy `> 4.0°C for >= 90 min -> 5% credit`) vs. `sla_overlay` (structured 480-token extraction from `contracts/ArcticHaul_Amendment_2.md` encoding `> 2.0°C for >= 45 min -> 12% credit, quarterly cap SGD 35,000.00` for `BIOLOGIC_CHILLED` SKUs).

### 3.2 Exact Target Numbers Across Rungs 1–6 (Zero Contradictions)

| Rung | Pyramid Layer & Capability (`asia-southeast1` Status) | Business Question | Blind Agent Trap (`TIER_3_REVIEW_REQUIRED`) | Governed Context Outcome (`TIER_2` / `TIER_1`) |
| :--- | :--- | :--- | :--- | :--- |
| **R1 · Schema** | Layers 1–2: BigQuery Schema + Data Insights (`GA`) + KC `lookupContext` (`Preview`) | *"What was Singapore's Closed Q3 Net Realized Revenue?"* | Queries `SUM(gross_total_sgd)` across all `SG` orders (includes `9%` GST + `CANCELLED`/`RETURNED` orders) -> **`SGD 1,684,200.00`** (`0/5` eval pass). | Applies enriched column descriptions + Data Insights predicate (`country_code='SG' AND order_status='COMPLETED'`, ex-GST, net of returns) -> **`SGD 1,312,450.00`** (`4/5` eval pass, `TIER_2_GROUNDED`). |
| **R2 · Glossary** | Layer 4: Knowledge Catalog Business Glossary (`GA`) | *"Which sales channel led Closed Q3 Singapore Premier segment AOV?"* | Filters `segment_label LIKE '%Premier%'` (sweeps in `'Premier_Promo_Trial'` mobile coupons) -> **`Mobile App (SGD 284.10)`** (`0/5` eval pass). | Resolves governed Glossary term `Premier Customer` -> `tier_code = 'PRM_HV'` -> **`B2B Corporate Portal (SGD 612.50)`** across `240` orders (`640` total SG `PRM_HV` orders, overall SG `PRM_HV` AOV `SGD 495.63`; `5/5` eval pass, `TIER_2_GROUNDED`). |
| **R3 · Metrics** | Layer 4: BigQuery Graph `MEASURE()` (`GA`) + Verified Query (`GA`) + Semantic Contract (`Reference Architecture`) | *"What was Singapore's Q3 Same-Day Contribution Margin %?"* | Naive 3-way `JOIN` (`orders JOIN order_lines JOIN parcel_legs`) duplicates revenue/cogs across `1:N` parcel legs -> distorted **`14.2%`** (`0/5` eval pass). | Grain-locked BigQuery Property Graph `MEASURE()` / Verified Query (`net_realized_revenue - cogs - fulfillment_fee - SUM(leg_cost)`) -> **`31.8%`** (`SGD 131,016.00` on `SGD 412,000.00` Same-Day revenue; `5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |
| **R4 · Trust & Access** | Layer 1 + Layer 5: KC Data Products + Auto Data Quality (`GA`) + BigQuery RLS & EntryGroup IAM (`GA`) | *"Did Cold-Chain Gross Margin really drop 410 bps in Q3—and what does each role see?"* | Scans uncertified `staging_cold_chain_oct11` amid `190` shadow tables -> false alarm **`24.3% (-410 bps drop)`** (`1/5` eval pass). | Routes strictly to certified `cold_chain_margin_gold` -> steady **`28.4% (-15 bps YoY)`**. **Beat 4b Identity Switch:** `cfo_regional` sees **`SGD 842,600.00`** (4 SEA markets); `sg_coldchain` RLS filter (`country_code='SG'`) sees **`SGD 346,480.00`** (`5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |
| **R5 · Graph** | Layer 4: BigQuery Property Graph (`CREATE PROPERTY GRAPH` + `ISO GQL` + `MEASURE()`, `GA` in `asia-southeast1`) | *"Which SG Premier orders & revenue are exposed to delayed Tier-2 Batch `#LN-409`?"* | Attempts brittle self-joins / drops Tier-2 `sku_lot_allocations` bridge -> **`0` or incomplete orders (`SGD 4,120.00`)** (`1/5` eval pass). | 4-hop `GRAPH_TABLE` ISO GQL traversal (`ColdChainBatch '#LN-409' -> SkuLotAllocation -> OrderLine -> Order -> Customer['PRM_HV']`) -> **`38` SG Premier orders, `SGD 19,380.00` at risk (`SGD 510.00` AOV)**—100% consistent with R2's `PRM_HV` population (`5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |
| **R6 · Contracts** | Layer 3: Gemini Enterprise Drive Connector (`GA`) + BigQuery Object Tables + `AI.GENERATE` / DocAI (`GA` in `asia-southeast1`) | *"How much vendor SLA credit is recoverable on Q3 Cold-Chain excursions?"* | Queries only base `vendor_sla_ledger` (`> 4.0°C for 90m`) and misses executed Amendment #2 -> **`SGD 1,420.00`** (`3` breaches; `0/5` eval pass). | Joins structured `480`-token `sla_overlay` extracted from `ArcticHaul_Amendment_2.md` (`> 2.0°C for 45m -> 12% credit, cap SGD 35K`) -> **`SGD 18,960.00`** across `14` qualifying chilled shipments (`5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |

---

## 4. Regional & Release-Stage Honesty Rules (`asia-southeast1`)

1. **Rungs 1–6 Live Scope:** Every BigQuery SQL, `CREATE PROPERTY GRAPH` (`GRAPH_TABLE` + `MEASURE()`), and `CREATE ROW ACCESS POLICY` DDL in `packs/meridian_q3_sgd/sql/` MUST execute cleanly in BigQuery `asia-southeast1`.
2. **Explicit Badges:**
   - Knowledge Catalog `lookupContext`: badge `Preview`.
   - LookML is **excluded** from Rungs 1–6 build scope (Rung 3 uses BigQuery Graph `MEASURE()` + Verified Query + custom Semantic Contract).
   - **Act IV Horizon Cards (`horizon_cards` in `pack.yaml`, strictly decoupled from R1–R6):**
     1. `knowledge_studio`: Knowledge Studio (`Context Sets` & `Enrichment Agent`) — `Preview`, region availability `"US / EU multi-regions (Preview; not yet in asia-southeast1)"`.
     2. `open_lakehouse_federation`: Cross-Cloud Lakehouse Catalog Federation — `GA`, explicitly distinguishing `Databricks Unity Catalog` (per-user OIDC `GA`), `Snowflake Horizon Catalog` (Workload Identity Federation `GA` — **never** claim per-user OIDC for Horizon), and `AWS Glue Data Catalog` (IAM role delegation `GA`).

---

## 5. Engine, Trust Classifier & Negative Controls (`engine/`)

1. **`engine/trust_classifier.py` & `engine/rls_impersonation.py`:**
   - Clean, self-contained modules (implementing stateless 3-Tier stream/SQL trust classification and HMAC role-scoped service account assertion helpers).
   - Implements `TrustTier` (`TIER_3_REVIEW_REQUIRED`, `TIER_2_GROUNDED`, `TIER_1_VERIFIED_OR_COMPILED`), SQL literal-preserving normalization, prose-to-table numeric reconciliation, HMAC role assertions, and customer-SA validation + email redaction.
2. **`engine/capture_rungs.py` CLI Modes (Every Flag Must Be Exercised in Tests):**
   - `--pack meridian_q3_sgd` (default)
   - `--offline-fixture`: Runs `seed_meridian.py` in-memory/SQLite or deterministic evaluator, validates against `schemas/rung_v2.schema.json`, and writes `web/data/rungs_bundle.js` with zero network/GCP dependency.
   - `--dry-run`: Runs BigQuery `dry_run=True` syntax & byte-estimate validation against `$PROJECT_ID.$DATASET_ID` in `$BQ_LOCATION` (`asia-southeast1`) and verifies SQL/GQL compilation without scanning bytes.
   - `--live-gcp`: Executes real BigQuery SQL & ISO GQL queries against `$PROJECT_ID.$DATASET_ID` (`asia-southeast1`), verifies exact tie-outs against `pack.yaml` invariants, tests both `Beat 4b` RLS personas (`cfo_regional` vs `sg_coldchain` filter semantics), asserts negative governance controls (confirming explicit policy/access denial reason on unauthorized access rather than generic `400` syntax errors), redacts any project IDs / SA emails, and emits `web/data/rungs_bundle.js` (`generated_mode: "live_gcp_verified"`).
3. **`server/app.py` (Optional Reusable SEA CE Live Runner):**
   - Lightweight FastAPI server serving `web/` statically at `/` and exposing `GET /api/health` and `POST /api/run-rung` (`{pack_id, rung_id, mode: "blind"|"governed", persona_id}`) that executes only allowlisted pack queries (never arbitrary client SQL!) in `--offline-fixture` or `--live-gcp` mode.

---

## 6. Dual-Mode Web Application (`web/`)

Single zero-build vanilla HTML5/CSS3/ES6 app (`web/index.html`) that works **100% offline via `file:///.../web/index.html`** (loading `<script src="data/rungs_bundle.js"></script>` -> `window.CONTEXT_PACK_BUNDLE`, zero `fetch()` CORS failure on `file://`) AND seamlessly enables `[▶ Run Live Query]` when served via `server/app.py`:

1. **Mode 1 — `Stage Mode` (Default on open / `?mode=stage`, Nov 26 Ballroom Presentation):**
   - **10% / 80% / 10% Quiet Stage V2 Proportions:**
     - Top `10%`: Event header, Rung pill stepper (`R1`..`R6` + `Act IV Horizon`), **`Blind` vs `Governed` beat toggle (`[B]`)**, **`Stage | Workbench` switch (`[W]`)**, theme switch (`Theme 01 Paper` default / `Theme 04 Dark Stage` via `[T]`), and live Token / Retry meter.
     - Center `80%` Hero Canvas: Question card, crisp side-by-side or progressive `Blind LLM` vs `Governed Context` outcome card, `Beat 4b · Switch Identity` (`cfo_regional` ↔ `sg_coldchain`) interactive toggle on Rung 4, and clean `GA` / `Preview` capability pills.
     - Bottom `10%` Eval & Trust Bar: **`k / N` Golden Eval Pass Rate** (`0/5` -> `5/5`), **`TrustTier` badge** (`TIER_3_REVIEW_REQUIRED` -> `TIER_2_GROUNDED` -> `TIER_1_VERIFIED_OR_COMPILED`), and Context Token delta (replacing invented scalar `"Trust %"`).
   - **Working Ballroom Keyboard Controls:**
     - `Space` or `ArrowRight`: Advance beat (`Question -> Blind Trap -> Governed Fix -> Next Rung`).
     - `ArrowLeft`: Previous beat / rung.
     - `KeyP`: Open/close `A/B/C/D` CDO Myth-Busting Poll overlay with answer reveal.
     - `KeyB`: Toggle `Blind` vs `Governed` comparison focus.
     - `KeyW`: Toggle `Stage Mode` ↔ `Workbench Mode`.
     - `KeyT`: Toggle `Paper` (`Theme 01`) ↔ `Dark Stage` (`Theme 04`).
2. **Mode 2 — `Workbench Mode` (`?mode=workbench` or `[W]` toggle, SEA DA CE Reusable Asset):**
   - **Accuracy & Token Progression Bar:** Visualizes cumulative Golden Eval Pass Rate (`0% -> 80% -> 100%`) alongside exploratory retry elimination across Rungs 1–6.
   - **3-Tab Engineering X-Ray Inspector:**
     1. `Context Injected` (Glossary JSON, Data Product aspect, `sla_overlay` 480-token contract, RLS policy).
     2. `Compiled SQL / ISO GQL` (syntax-highlighted side-by-side `Blind` vs `Governed` query diff).
     3. `Architecture & Negative Control` (GCP primitives, `asia-southeast1` release stage badges, and policy-denial verification).
   - **Execution Mode Pill:** `[Recorded Verified Run]` (offline `file://` safe) + `[▶ Run Live Query]` button (calls `/api/run-rung` when `http://localhost` server is active, showing live latency & row count).

---

## 7. Mandatory Verification & Zero-Leak Gate

Before declaring completion:
1. `uv run pytest` MUST pass 100% (`test_math_invariants.py`, `test_schema_and_trust.py`, `test_zero_leak.py`, and any UI contract tests).
2. `uv run python -m engine.capture_rungs --offline-fixture` MUST exit `0` and validate `web/data/rungs_bundle.js` against `schemas/rung_v2.schema.json`.
3. When sandbox GCP credentials are active (configured via untracked `.env`), `scripts/provision_pack.sh`, `uv run python -m engine.capture_rungs --dry-run`, and `uv run python -m engine.capture_rungs --live-gcp` MUST execute cleanly in `asia-southeast1` and sanitize any project IDs before writing `web/data/rungs_bundle.js`.
4. Deterministic PCRE zero-leak scan (`engine/leak_check.py` + `tests/test_zero_leak.py`) MUST return `0` matches across all tracked and untracked-but-not-ignored files for corporate internal domains, internal shortlinks, internal monorepo paths, non-placeholder GCP project IDs, and real customer or account names.
