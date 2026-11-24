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

## 2. Repository Boundaries & Build Hygiene

- **Core Contracts & Tooling:** `SPEC.md`, `schemas/rung_v2.schema.json`, `pyproject.toml`, `.env.example`, `.gitignore`, `LICENSE`.
- **Declarative Scenario Packs:** `packs/<pack_id>/` (`pack.yaml`, `context_layer.yaml`, `rungs/*.yaml`, `seed_*.py`, `sql/`, `contracts/`).
- **Engine, Server & Provisioning:** `engine/`, `server/`, `scripts/`.
- **Zero-Build Stage & Workbench UI:** `web/` (`web/index.html`, `web/vote.html`, `web/css/`, `web/js/`, and generated `web/data/rungs_bundle.js`).

---

## 3. Unified Mathematical Invariants (`packs/meridian_q3_sgd/`, Seed `20261126`)

`packs/meridian_q3_sgd/seed_meridian.py` MUST deterministically generate synthetic rows (`random.Random(20261126)`) for Closed Q3 (`2026-07-01` to `2026-09-30`, currency `SGD`, Singapore GST `9%`) that satisfy ALL cross-rung invariants simultaneously, verified both in pure Python (`tests/test_math_invariants.py`) AND when loaded into BigQuery (`asia-southeast1`):

### 3.1 Core Tables & Shadow Estate (`sql/01_tables.sql`, `sql/02_shadow_clones.sql`)
1. `customers` (`customer_id`, `country_code`, `tier_code`, `segment_label`, `trailing_12m_spend_sgd`, `return_rate`, `channel_pref`)
   - Official Business Glossary definition of **Premier** (`Rung 2` & `Rung 5`): `tier_code = 'PRM_HV'` (enforcing `trailing_12m_spend_sgd >= 5000.00 AND return_rate < 0.08`).
   - Distractor trap column: `segment_label` includes `'Premier_Promo_Trial'` on low-value promo accounts so naive `segment_label LIKE '%Premier%'` produces a wrong answer.
2. `orders` (`order_id`, `customer_id`, `country_code`, `sales_channel`, `fulfillment_tier`, `order_date`, `order_status`, `amt_gross_billed_sgd`, `amt_item_subtotal_sgd`, `amt_gst_sgd`, `fulfillment_fee_sgd`, `amt_net_settled_sgd`)
   - Closed Q3 (`2026-07-01`..`2026-09-30`), markets `SG`, `MY`, `TH`, `ID`.
3. `order_lines` (`order_line_id`, `order_id`, `sku_id`, `lot_id`, `qty`, `gross_line_sgd`, `gst_line_sgd`, `returned_line_sgd`, `net_line_revenue_sgd`, `cogs_line_sgd`)
   - **Exact Header-to-Line Tie-Out:** For every `COMPLETED` order, `SUM(order_lines.net_line_revenue_sgd) == orders.amt_net_settled_sgd` to `0.01 SGD` (`0.00` aggregate drift).
4. `parcel_legs` (`leg_id`, `order_id`, `hub_code`, `carrier_vendor`, `leg_seq`, `leg_cost_sgd`, `temp_excursion_celsius`, `excursion_minutes`)
   - **`1:N` Fan-Trap (`Rung 3`):** Same-Day orders (`fulfillment_tier = 'SAME_DAY'`) span `2` to `4` parcel transfer legs per order (`1:N` against `orders` and `order_lines`).
5. `cold_chain_batches` (`batch_id`, `supplier_tier`, `vendor_name`, `temp_peak_celsius`, `excursion_duration_min`, `shipment_invoice_sgd`, `batch_status`) & `sku_lot_allocations` (`lot_id`, `batch_id`, `sku_id`, `temp_sensitive_class`)
   - Powers 4-hop supply-chain lineage (`ColdChainBatch -> SkuLotAllocation -> OrderLine -> Order -> Customer`) in `Rung 5`.
6. `mart_coldchain_q3_r2` (certified Knowledge Catalog Data Product table, `country_code`, `quarter`, `net_revenue_sgd`, `gross_margin_sgd`, `gross_margin_pct`, `close_batch_code = 'B26Q3_R2'`) vs. `mart_coldchain_q3_r1` (uncertified Oct 11 snapshot `close_batch_code = 'B26Q3_R1'` missing late-Q3 supplier rebate settlements) + **`190` empty script-generated shadow tables** (`shadow_auto_tbl_001` .. `shadow_auto_tbl_190`, generated programmatically by `sql/02_shadow_clones.sql` or `scripts/provision_pack.sh`).
7. `vendor_sla_ledger` (base contract table encoding legacy `> 4.0°C for >= 90 min -> 5% credit`) vs. `sla_overlay` (structured 480-token extraction from `contracts/ArcticHaul_Amendment_2.md` encoding `> 2.0°C for >= 45 min -> 12% credit, quarterly cap SGD 35,000.00` for `BIOLOGIC_CHILLED` SKUs).

### 3.2 Exact Target Numbers Across Rungs 1–6 (Zero Contradictions)

| Rung | Pyramid Layer & Capability (`asia-southeast1` Status) | Business Question | Blind Agent Trap (`TIER_3_REVIEW_REQUIRED`) | Governed Context Outcome (`TIER_2` / `TIER_1`) |
| :--- | :--- | :--- | :--- | :--- |
| **R1 · Schema** | Layers 1–2: BigQuery Schema + Data Insights (`GA`) + KC `lookupContext` (`Preview`) | *"What was Singapore's Closed Q3 Net Realized Revenue?"* | Queries `SUM(amt_gross_billed_sgd)` across all `SG` orders (includes `9%` GST + `CANCELLED`/`RETURNED` orders) -> **`SGD 1,684,200.00`** (`0/5` eval pass). | Applies enriched column descriptions + Data Insights predicate (`country_code='SG' AND order_status='COMPLETED'`, ex-GST, net of returns) -> **`SGD 1,312,450.00`** (`4/5` eval pass, `TIER_2_GROUNDED`). |
| **R2 · Glossary** | Layer 4: Knowledge Catalog Business Glossary (`GA`) | *"Which sales channel led Closed Q3 Singapore Premier segment AOV?"* | Filters `segment_label LIKE '%Premier%'` (sweeps in `'Premier_Promo_Trial'` mobile coupons) -> **`Mobile App (SGD 284.10)`** (`0/5` eval pass). | Resolves governed Glossary term `Premier Customer` -> `tier_code = 'PRM_HV'` -> **`B2B Corporate Portal (SGD 612.50)`** across `240` orders (`640` total SG `PRM_HV` orders, overall SG `PRM_HV` AOV `SGD 495.63`; `5/5` eval pass, `TIER_2_GROUNDED`). |
| **R3 · Metrics** | Layer 4: BigQuery Graph `MEASURE()` (`GA`) + Verified Query (`GA`) + Semantic Contract (`Reference Architecture`) | *"What was Singapore's Q3 Same-Day Contribution Margin %?"* | Naive 3-way `JOIN` (`orders JOIN order_lines JOIN parcel_legs`) duplicates revenue/cogs across `1:N` parcel legs -> distorted **`14.2%`** (`0/5` eval pass). | Grain-locked BigQuery Property Graph `MEASURE()` / Verified Query (`amt_net_settled_sgd - cogs - fulfillment_fee - SUM(leg_cost)`) -> **`31.8%`** (`SGD 131,016.00` on `SGD 412,000.00` Same-Day revenue; `5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |
| **R4 · Trust & Access** | Layer 1 + Layer 5: KC Data Products + Auto Data Quality (`GA`) + BigQuery RLS & EntryGroup IAM (`GA`) | *"Did Cold-Chain Gross Margin really drop 410 bps in Q3—and what does each role see?"* | Scans uncertified `mart_coldchain_q3_r1` amid `190` shadow tables -> false alarm **`24.3% (-410 bps drop)`** (`1/5` eval pass). | Routes strictly to certified `mart_coldchain_q3_r2` -> steady **`28.4% (-15 bps YoY)`**. **Beat 4b Identity Switch:** `cfo_regional` sees **`SGD 842,600.00`** (4 SEA markets); `sg_coldchain` RLS filter (`country_code='SG'`) sees **`SGD 346,480.00`** (`5/5` eval pass, `TIER_1_VERIFIED_OR_COMPILED`). |
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

- **5-Layer Enterprise Context Pyramid (`L1 → L5`, Executive Storytelling Alignment):**
  - **Layer 1 · Technical Metadata** (`R1`, `R4`) — Table schemas, PK/FK constraints, certified Data Products, and automated data quality freshness.
  - **Layer 2 · Intent-Driven Enrichment** (`R1`) — Automated schema insights and runtime context retrieval (`BigQuery Data Insights` & `Knowledge Catalog lookupContext (Preview)`).
  - **Layer 3 · Institutional Knowledge** (`R6`) — Policies, contracts, and amendments living in unstructured documents outside SQL tables.
  - **Layer 4 · Semantic Knowledge** (`R2`, `R3`, `R5`) — Shared business glossaries, grain-locked metrics (`MEASURE()`), and multi-hop relationship graphs (`ISO GQL`).
  - **Layer 5 · Personalization & Access Governance** (`R4 · Beat 4b`) — Identity-scoped Row-Level Security and access boundaries so answers adapt to who is asking.

1. **Mode 1 — `Stage Mode` (Default on open / `?mode=stage`, Nov 26 Ballroom Presentation):**
   - **10% / 80% / 10% Quiet Stage V2 Proportions:**
     - Top `10%`: Event header, Rung pill stepper (`Overview` + `R1`..`R6` + `What's Next`, with Stage defaulting to `Overview` / `?rung=overview` when the pack defines optional `overview` in `schemas/rung_v2.schema.json`), **`Blind` vs `Governed` beat toggle (`[B]`)**, **`? Guide` plain-English drawer (`?` / `H`)**, **`Stage | Workbench` switch (`[W]`)**, and theme switch (`Theme 01 Paper` default / `Theme 04 Dark Stage` via `[T]`).
     - Center `80%` Hero Canvas: Executive Briefing `Overview` landing screen (spoiler-free customer profile, Business vs. Tech perspectives, and visual 6-step `R1`–`R6` Context Journey), "You Are Here" escalation rail, beat-gated story strip, Question card, clean `Blind Agent Trap` vs `Governed Enterprise Context` outcome cards, compact `Beat 4b · Switch Identity` (`cfo_regional` ↔ `sg_coldchain`) toggle on Rung 4, and closing Takeaways + pre-rendered public QR showcase.
     - Bottom `10%` Bar: Calm executive summary pill (`Same AI Model · Progressive Enterprise Context · Press [X] X-Ray for SQL & Eval Proof`), `[X] X-Ray` drawer trigger, and navigation controls. Detailed **`k / N` Golden Eval Pass Rate**, **`TrustTier`**, and token/retry telemetry remain cleanly tucked inside X-Ray (`[X]`) and Workbench (`[W]`). (On `Overview`, `[X]` and `[P]` remain hidden/disabled to preserve zero spoilers.)
   - **Working Ballroom Keyboard Controls:**
     - `Space` or `ArrowRight`: Advance beat (`Overview -> R1 Question -> Blind Trap -> Governed Fix -> Next Rung`).
     - `ArrowLeft`: Previous beat / rung (returning from `R1` Question/Compare to `Overview` when `overview` is present).
     - `KeyP`: Open/close `A/B/C/D` CDO Myth-Busting Poll overlay with answer reveal (no-op on `Overview`).
     - `KeyB`: Toggle `Blind` vs `Governed` vs `Compare` focus (`blind -> governed -> compare -> blind`).
     - `KeyW`: Toggle `Stage Mode` ↔ `Workbench Mode` (Workbench opens on `R1`, never `Overview`).
     - `KeyT`: Toggle `Paper` (`Theme 01`) ↔ `Dark Stage` (`Theme 04`).
     - `?` or `KeyH`: Toggle the plain-English `? Guide` slide-over drawer (`Escape` closes).
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


---

## 8. Phase 2 Core Completion Architecture (Live Knowledge Catalog, Zero-Trust Agent & Empirical `N=5` Eval)

### 8.1 Regional & Endpoint Honesty Contract
- **Storage, Graph, Governance & Catalog (`asia-southeast1`):** All BigQuery datasets (`meridian_commerce` and `meridian_blind`), BigQuery Property Graph (`meridian_supply_graph`), Row-Level Security policies, Knowledge Catalog Business Glossaries/EntryLinks/AspectTypes/Auto Data Quality scans, GCS contract bucket, and BigQuery Object Tables reside strictly in **`asia-southeast1` (Singapore)**.
- **Gemini PayGo Inference (`global` Endpoint):** Standard PayGo Vertex Gemini (`AGENT_MODEL_ID`, default `gemini-3.8-flash` with fallback `gemini-3.5-flash`) and BigQuery `AI.GENERATE` execute inference via the **`global` Vertex endpoint**. UI badges and X-Ray metadata MUST state this distinction transparently (*"Data, Graph, Catalog & RLS in `asia-southeast1` · Gemini PayGo Inference via `global` Endpoint"*).

### 8.2 Genuine Physical Schema Ambiguity (Eliminating Filename/Column Giveaways)
To ensure a real Blind LLM agent faces authentic enterprise ambiguity without rigging prompts:
1. **`orders` Revenue Columns (`Rung 1`):**
   - Realistic ERP columns: `amt_gross_billed_sgd` (includes 9% GST and unadjusted on `CANCELLED`/`RETURNED`), `amt_item_subtotal_sgd` (ex-GST item subtotal BEFORE deducting returns/cancellations), `amt_gst_sgd`, and `amt_net_settled_sgd` (where `CANCELLED`/`RETURNED` rows have `0.00` and `COMPLETED` orders hold exact ex-GST, net-of-returns realized revenue, documented in `OPTIONS(description=...)` on `meridian_commerce.orders`).
2. **Neutral Cold-Chain Candidate Tables (`Rung 4`):**
   - Provide neutral table names `mart_coldchain_q3_r1` (uncertified Oct 11 snapshot, `24.3%`) and `mart_coldchain_q3_r2` (certified Knowledge Catalog Data Product protected by BigQuery RLS, `28.4%`) so a Blind agent scanning `meridian_blind` (`mart_coldchain_q3_r1`, `mart_coldchain_q3_r2`, plus `190` `shadow_auto_tbl_*` clones) cannot guess from `_gold` or `staging_` in the table name and genuinely requires Knowledge Catalog's `data-product-certification` Aspect (`CERTIFIED` vs `UNCERTIFIED_STALE`).
3. **Physical `meridian_blind` Dataset (`M1`):**
   - `meridian_blind` MUST be built as **physical BigQuery tables** (not views!) with identical rows and table names to `meridian_commerce` (excluding `sla_overlay`), stripped of all table/column `OPTIONS(description=...)`, `PRIMARY KEY`/`FOREIGN KEY` constraints, and Knowledge Catalog EntryLinks/Aspects.

### 8.3 Declarative `context_layer.yaml` & Live GCP Provisioning (`scripts/provision_context_layer.py`)
- Store all Meridian-specific catalog definitions inside `packs/meridian_q3_sgd/context_layer.yaml` so `engine/` and `scripts/` contain zero hardcoded Meridian terms.
- `scripts/provision_context_layer.py` MUST support `--dry-run`, `--live-gcp`, and dependency-ordered `--teardown` (EntryLinks -> Glossary Terms -> Glossary, DataScans, Aspect Detach -> AspectTypes, DataAssets -> DataProducts, Object Table / Staging -> Connection IAM -> Connection -> GCS Bucket, `meridian_blind` dataset, and read-only agent SAs):
  1. **Physical `meridian_blind` tables** (`asia-southeast1`) + governed shadow-table descriptions on `meridian_commerce`.
  2. **Knowledge Catalog Business Glossary** (`meridian-commerce-glossary` in `asia-southeast1`) + 4 canonical terms (`premier-customer`, `net-realized-revenue`, `certified-close-cycle`, `biologic-chilled-class`) linked via `definition` `EntryLink` to their governing BigQuery columns.
  3. **Knowledge Catalog Custom `AspectType`, Data Scans & Data Product** (`data-product-certification` in `asia-southeast1` attached to `mart_coldchain_q3_r2` vs. `mart_coldchain_q3_r1`), **Auto Data Quality (`DATA_QUALITY`)**, **Data Profile (`DATA_PROFILE`)**, **BigQuery Data Insights (`DATA_DOCUMENTATION`)** scans, and native Knowledge Catalog **Data Product** (`meridian-coldchain-q3-product`).
  4. **GCS Contract Upload + BigQuery Object Table + Safe `AI.GENERATE` Staging (`Rung 6`):** Upload the 4 `.md` contracts as `text/plain` to `gs://<project>-meridian-contracts` (`asia-southeast1`), create dedicated BigQuery Connection `meridian_vertex_conn` (`asia-southeast1`) + Object Table `meridian_commerce.contract_docs_obj` (with table description), extract structured amendment parameters via `AI.GENERATE` into staging table `meridian_commerce.sla_overlay_extracted` (with table and 11 column descriptions), validate exact invariant match (`temp_threshold_c == 2.0`, `duration_threshold_min == 45`, `credit_rate == 0.12`, `quarterly_cap_sgd == 35000.0`), and keep `meridian_commerce.sla_overlay` intact as verified fallback.

### 8.4 Zero-Trust Live Agent Engine (`engine/context_retriever.py`, `engine/live_agent.py`, `POST /api/run-agent`)
1. **Strict SA Separation & `SELECT`-Only Dry-Run Gate:**
   - Never execute LLM-generated SQL under `meridian-web-runner`!
   - Provision two strictly read-only SAs:
     - `meridian-blind-agent`: dataset `READER` (`roles/bigquery.dataViewer`) **only** on `meridian_blind` + `roles/bigquery.jobUser`.
     - `meridian-governed-agent`: dataset `READER` **only** on `meridian_commerce` + `roles/dataplex.catalogViewer` + `roles/bigquery.jobUser` (for `sg_coldchain` persona on R4, execute the verified/generated `SELECT` via `meridian-sg-coldchain`).
   - Before executing ANY agent-generated SQL/GQL, run a BigQuery `dry_run=True` AST check and reject any query where `statement_type != "SELECT"`, multiple statements are present, `total_bytes_processed > 100 MB`, or `referenced_tables` references any dataset outside the arm's allowed dataset (`meridian_blind` for Blind; `meridian_commerce` for Governed).
2. **Symmetric Blind vs. Governed Agent Contract & Abuse Protection:**
   - Both arms use identical `AGENT_MODEL_ID`, `AGENT_MODEL_LOCATION` (`global`), `temperature=0.0`, `max_turns=4`, `timeout_s=25`, and `100 MB` byte budget.
   - Governed arm retrieves context dynamically via live GCP tools (`search_certified_tables`, `lookup_catalog_context` calling `CatalogService.LookupContext`, and `get_verified_metric_contract` exposing pack Verified Queries / Property Graph DDL).
   - `POST /api/run-agent` accepts strictly `{pack_id, rung_id, arm: "blind"|"governed"|"both", persona_id}` (zero free-form prompt text), **requires `DEMO_SHARE_TOKEN`** (`X-Demo-Key` header or `?key=`) when `REQUIRE_TOKEN_FOR_LIVE_AGENT=true` (default `true`), keys rate-limiting on the **last** proxy hop in `X-Forwarded-For` + process concurrency semaphore (`max=2`) + daily call cap (`DAILY_AGENT_CALL_LIMIT`, default `200`), and respects `ENABLE_LIVE_AGENT=false` kill-switch.

### 8.5 Empirical `N=5` Evaluation Harness (`engine/eval_harness.py` -> `results/live_eval_runs.jsonl`)
- Per-rung grading rules live in `packs/meridian_q3_sgd/` (`grading` block supporting numeric tolerance, unit/percent normalization `31.8` vs `0.318`, string channel match on R2, multi-metric match on R5, and persona-scoped match on R4).
- Runs `N=5` iterations per rung × arm, redacts 100% of project IDs/SA emails via `redact_bundle_data` before writing `results/live_eval_runs.jsonl` (scanned by `engine/leak_check.py`), populates `empirical_eval` on each rung in `web/data/rungs_bundle.js` using a deterministic median-token representative run rule, and keeps **Stage Mode** instant (`0ms` bundle + `~1s` `/api/run-rung` + slide-up Stage X-Ray Drawer `[X]`), while **Workbench Mode (`[W]`)** exposes **`🤖 Run Live Agent`** alongside empirical `N=5` telemetry!

---

## 9. Milestone 5 — In-App QR Audience Poll (`/vote`) & Stage `[P]` Live Integration

1. **Multi-Instance Poll Store (`engine/poll_store.py`):**
   - `FirestorePollStore(project_id, database_id)` targeting a named Firestore Native database (`FIRESTORE_DATABASE_ID`, default `<prefix>-polls` -> `meridian-polls` in `asia-southeast1`, `"example-polls"` in `.env.example`), with `InMemoryPollStore` fallback strictly for local/offline mode (`PROJECT_ID="example-project-id"` or `FIRESTORE_DATABASE_ID` empty/`"none"`).
   - Zero-PII voter ballot IDs (`e{epoch}_{sha256(pack_id:rung_id:e{epoch}:voter_token)[:32]}`), idempotent `A -> B` vote switching, `MAX_VOTERS_PER_EPOCH = 300` cap for net-new voters, `1.0s` TTL read cache, and transactional `epoch` increment on `reset_poll`.
   - Offline SVG QR code generation via `segno` (`render_poll_qr_svg(vote_url)`).
2. **Server Routes & Security Boundaries (`server/app.py`):**
   - `GET /vote` (`GET /vote/`, `GET /vote.html`) serving `web/vote.html` (`Cache-Control: no-cache`).
   - `GET /api/poll/state` (**zero-spoiler invariant:** strictly omits `correct_key` and `reveal_takeaway` so audience voters never see answers before Stage reveal, while static Stage bundle `web/data/rungs_bundle.js` retains presenter reveal data for offline `file://` Stage Mode; `POLL_READ_RPM_LIMIT=3000/min` per IP).
   - `POST /api/poll/vote` (shared hotel-NAT IP limit `POLL_VOTE_RPM_LIMIT=240/min` + `15/min` per hashed `voter_token` capped at `2000` tracked entries).
   - `POST /api/poll/reset` and `POST /api/poll/sync-stage` strictly gated by `DEMO_SHARE_TOKEN` (`X-Demo-Key`, fail-closed `401`/`503`).
   - `GET /api/poll/qr.svg` generating QR strictly for server-derived `{origin}/vote?pack=...&rung=...` from validated `pack_id`/`rung_id` and `PUBLIC_BASE_URL` or validated `Host` header (never raw URL params).
3. **Stage `[P]` Modal & Mobile `/vote` UI (`web/`):**
   - Stage `[P]` modal renders a 2-column QR + live animated vote-bar view with `2000ms` visibility-aware diff-guarded polling, presenter stage-sync, `Clear Room Votes`, and optional `poll.external_poll_url` (`schemas/rung_v2.schema.json`).
   - `/vote` (`web/vote.html`, `web/js/vote.js`) provides a zero-CDN, dark-default executive voting UI with `>=56px` touch targets, R1–R6 switcher, `"Live on Stage"` jump banner, and `3000ms` live refresh.
4. **Cloud Run Provisioning & Teardown (`scripts/deploy_cloud_run.sh`, `scripts/teardown_pack.sh`):**
   - Enables `firestore.googleapis.com`, provisions `${FIRESTORE_DATABASE_ID}` (`firestore-native` in `${BQ_LOCATION}`), grants `roles/datastore.user` strictly to `<prefix>-web-runner` (never to blind/governed agent SAs), and supports `--delete-poll-db` teardown.
