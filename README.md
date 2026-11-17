# Context Is All You Need

> **Frontier models are table stakes—governed enterprise context is the differentiator.**

An Apache-2.0 benchmark engine, declarative `ScenarioPack` framework, and dual-mode presentation/engineering UI demonstrating how governed enterprise context across **BigQuery** and **Knowledge Catalog** eliminates analytical drift, join fan-traps, and stale-table hallucinations—without changing the underlying frontier model.

---

## Architecture Overview

The repository enforces a strict separation between **declarative scenario packs**, the **verification, live-agent & eval engine**, and the **zero-build web application**:

- **`schemas/rung_v2.schema.json`** — Authoritative JSON Schema (Draft 2020-12) for `ContextScenarioPackBundleV2` bundles, outcomes, `EmpiricalEval` (`N=5`) telemetry, trust tiers, identity variants, polls, and Horizon cards.
- **`packs/<pack_id>/`** — Self-contained domain packs (starting with `packs/meridian_q3_sgd/`) housing `pack.yaml`, `rungs/*.yaml`, deterministic synthetic seed generators, BigQuery DDL/SQL/ISO GQL scripts (including `meridian_blind` physical CTAS trap tables alongside governed marts), and unstructured vendor contract fixtures.
- **`engine/`** — Pack-agnostic loader (`pack_loader.py`), stateless 3-tier trust classifier (`trust_classifier.py`), HMAC role-assertion & identifier redaction helpers (`rls_impersonation.py`), deterministic PCRE leak scanner (`leak_check.py`), live-agent AST `dry_run` + tool-calling harness (`eval_harness.py`), bundle exporter (`bundle_exporter.py`), and CLI runner (`capture_rungs.py`).
- **`server/app.py`** — Optional FastAPI server serving `web/` statically and exposing `GET /api/health`, allowlisted BigQuery rung verification (`POST /api/run-rung`), and Zero-Trust `X-Demo-Key`-protected live Blind vs. Governed agent comparison (`POST /api/run-agent`).
- **`web/`** — Zero-build vanilla HTML5/CSS3/ES6 Stage & Workbench application that opens directly via `file:///.../web/index.html` or over `http://` via `uvicorn server.app:app` / Cloud Run.

Adding a new industry pack (for example `packs/fsi_wealth/` or `packs/aviation_ops/`) requires **zero edits** to `engine/` or `web/`.

---

## 5-Layer Context Pyramid, Rungs 1–6 & Act IV Horizon

### Rungs 1–6 (`asia-southeast1` Live Scope)

Every SQL query, `CREATE PROPERTY GRAPH` (`GRAPH_TABLE` + `MEASURE()`), and Row-Level Security policy across Rungs 1–6 is scoped to execute cleanly in BigQuery `asia-southeast1`:

| Rung | Context Layer & Capability | `asia-southeast1` Status | Failure Mode Eliminated |
| :--- | :--- | :--- | :--- |
| **R1 · Schema** | BigQuery Schema + Data Insights; Knowledge Catalog `lookupContext` | `GA` (Schema/Insights), `Preview` (`lookupContext`) | Gross-vs-net tax and cancelled-row revenue inflation |
| **R2 · Glossary** | Knowledge Catalog Business Glossary | `GA` | Distractor column matching (`LIKE '%...'`) instead of canonical tier codes |
| **R3 · Metrics** | BigQuery Graph `MEASURE()` + Verified Query + Custom Semantic Contract | `GA` (`MEASURE()`, Verified Query), `Reference Architecture` (Semantic Contract) | `1:N` multi-leg join fan-traps duplicating header revenue and COGS |
| **R4 · Trust & Access** | Knowledge Catalog Data Products + Auto Data Quality + BigQuery Row-Level Security (`Beat 4b` Identity Switch) | `GA` | Stale staging table selection amid shadow clones and cross-territory overexposure |
| **R5 · Graph** | BigQuery Property Graph (`CREATE PROPERTY GRAPH` + `ISO GQL` `GRAPH_TABLE` + `MEASURE()`) | `GA` | Brittle multi-hop self-joins dropping intermediate allocation bridge tables |
| **R6 · Contracts** | Gemini Enterprise Drive Connector + BigQuery Object Tables + `AI.GENERATE` / DocAI | `GA` | Missing executed contract amendments stored in unstructured documents |

*Scope note:* LookML is intentionally excluded from Rungs 1–6; Rung 3 standardizes on BigQuery Graph `MEASURE()`, Verified Query contracts, and custom semantic contracts.

### Act IV Horizon (`horizon_cards`, Decoupled from R1–R6)

Architectural roadmap and cross-cloud governance cards are strictly isolated in `Act IV Horizon`:

1. **Knowledge Studio (`Context Sets` & `Enrichment Agent`)** — **`Preview`**, available in **US / EU multi-regions (`Preview`; not yet in `asia-southeast1`)**.
2. **Cross-Cloud Lakehouse Catalog Federation** — **`GA`**, with explicit per-catalog identity parity:
   - **Databricks Unity Catalog:** Per-user OIDC (`GA`)
   - **Snowflake Horizon Catalog:** Workload Identity Federation (`GA` — never per-user OIDC)
   - **AWS Glue Data Catalog:** IAM role delegation (`GA`)

### Trust Tiers & Evaluation Metrics

- **`TrustTier` Classification:**
  - `TIER_3_REVIEW_REQUIRED` — Ungrounded blind query or numeric reconciliation mismatch.
  - `TIER_2_GROUNDED` — Grounded via schema descriptions, Data Insights predicates, or Business Glossary bindings.
  - `TIER_1_VERIFIED_OR_COMPILED` — Executed via Verified Query, BigQuery Property Graph `MEASURE()` / `ISO GQL`, certified Data Product + RLS, or compiled SLA contract overlay.
- **Golden Eval Pass Rate (`k / N`):** Repeatable evaluation pass count across runs (e.g., `0/5 -> 5/5`), paired with Context Token delta, exploratory query count, and error retries—never an invented scalar trust-percentage score.

---

## Dual-Mode Web Interface (`web/`)

Open `web/index.html` directly over `file://` (no build step, no ES module CORS failures, no startup `fetch()`) or serve via `server/app.py`.

### Mode 1 — Stage Mode (`?mode=stage`, Default)

Designed for live executive presentations using `10% / 80% / 10%` Quiet Stage V2 proportions:

- **Top `10%` Bar:** Pack header, `hero_tagline`, explicit **Regional Honesty Badge** (`Data, Graph, Catalog & RLS in asia-southeast1 · Gemini PayGo Inference via global Endpoint`), Rung stepper (`R1`–`R6` + `Act IV Horizon`), `Q | Blind | Compare | Governed` beat controls, `Stage | Workbench` switch, `Paper | Dark` theme switch, `Poll [P]` trigger, and live Context Token & Retry delta pill.
- **Center `80%` Hero Canvas:** Business question, `pyramid_layer` and explicit `GA` / `Preview` / `Reference Architecture` badges, side-by-side `Blind Agent Trap` vs `Governed Enterprise Context` comparison, `Empirical N=5` alongside `Target:` badges when `empirical_eval` is present, interactive **`Beat 4b · Switch Identity`** toggle on Rung 4, and the decoupled **`Act IV Horizon`** showcase.
- **Slide-Up Stage X-Ray Drawer (`[X]`):** Press `X` (`KeyX`) or click `[X] X-Ray` in the Stage footer to reveal injected Knowledge Catalog & Governance context (`context_mechanism`, `context_payload`, `xray_summary`, `gcp_primitives`), side-by-side compiled `Blind` vs `Governed` SQL/ISO GQL, and empirical `N=5` telemetry without leaving Stage Mode (`Escape` closes).
- **Bottom `10%` Bar:** `k / N` Golden Eval Pass Rate + `Empirical N=5` telemetry indicator, `TrustTier` progression, exploratory query comparison, `[X] X-Ray` drawer button, and navigation controls (no slow live-agent runner on the main Stage bar so transitions stay `0ms`).

#### Ballroom Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `Space` / `ArrowRight` | Advance beat or next rung (`Question -> Blind Trap -> Governed Fix -> Next Rung -> Act IV Horizon`) |
| `ArrowLeft` | Step back to previous beat or rung |
| `X` (`KeyX`) | Open / close the **Slide-Up Stage X-Ray Drawer** (`Escape` closes; ignored inside inputs) |
| `P` (`KeyP`) | Open / close `A/B/C/D` CDO Myth-Busting Poll modal (`Escape` closes) |
| `B` (`KeyB`) | Cycle focus between `Compare`, `Blind`, and `Governed` |
| `W` (`KeyW`) | Toggle `Stage Mode` ↔ `Workbench Mode` |
| `T` (`KeyT`) | Toggle `Theme 01 Paper` ↔ `Theme 04 Dark Stage` |

### Mode 2 — Workbench Mode (`?mode=workbench`)

Reusable Customer Engineering inspection console:

- **Cumulative Accuracy & Retry Progression Bar:** Interactive rung cards summarizing Golden Eval pass rates and error-retry elimination across all rungs.
- **3-Tab Engineering X-Ray Inspector (`?tab=context|sql|arch`):**
  1. **Context Injected:** Context mechanism, payload JSON, and RLS persona policy matrix.
  2. **Compiled SQL / ISO GQL:** Syntax-highlighted side-by-side `Blind` vs `Governed` query panes with copy actions.
  3. **Architecture & Negative Control:** GCP primitives, `asia-southeast1` release stages, and policy-denial verification assertions.
- **Execution Mode Pill, Regional Honesty & Live BigQuery Query Runner:** Displays `[Recorded Verified Run]` offline over `file://`, surfaces the Regional Honesty Badge (`asia-southeast1` data/graph/catalog/RLS + `global` Gemini inference), and activates **`[▶ Run Live Query]`** (`POST /api/run-rung`) when served over `http://` / `https://`.
- **Live Zero-Trust Agent Runner (`🤖 Run Live Agent (Blind vs. Governed)`):** Queries `GET /api/health` over HTTP/HTTPS and invokes `POST /api/run-agent` (`arm: "both" | "blind" | "governed"`, passing active Rung 4 `persona_id`) with an `X-Demo-Key` header. Passing `?key=...` saves the demo share key into browser `sessionStorage` and immediately strips `key` from the visible URL via `history.replaceState` to prevent screen-share leaks; missing keys or `401` responses open an accessible inline Demo Share Key bar (password field with `autocomplete="off"`, paste support, and show/hide toggle). Renders side-by-side `Blind` vs `Governed` agent cards (`passed_grading`, `answer_summary`, `trust_tier`, `latency_ms`, `tokens_used`, `tool_trace`, `catalog_context_summary`, `sql_or_gql`, `observed_signals`, `rows_preview`) alongside an **`Empirical N=5 vs. Authored Baseline Telemetry`** comparison table, and gracefully disables live-agent execution when opened via `file://` or when `live_agent_enabled === false`.

### URL Deep-Linking Parameters

| Parameter | Values | Default |
| :--- | :--- | :--- |
| `mode` | `stage`, `workbench` | `stage` |
| `rung` | `1`..`6`, `<rung_id>`, `horizon` | First rung |
| `beat` | `compare`, `question`, `blind`, `governed` | `compare` |
| `theme` | `paper`, `dark` | `paper` |
| `persona` | Persona ID from active rung's `identity_variants` | First persona on rung |
| `tab` | `context`, `sql`, `arch` | `context` |

Example: `web/index.html?mode=stage&rung=4&theme=dark`

---

## Setup, CLI & BigQuery `asia-southeast1` Usage

### 1. Install Dependencies

```bash
uv sync
```

### 2. Offline Mode (Zero Network / Zero GCP Required)

Generate `web/data/rungs_bundle.js` deterministically from the offline fixture and inspect in any browser:

```bash
uv run python -m engine.capture_rungs --pack meridian_q3_sgd --offline-fixture
```

Then open `web/index.html` directly via `file://` or serve it locally with FastAPI:

```bash
uv run uvicorn server.app:app --host 127.0.0.1 --port 8000
```

### 3. Live BigQuery `asia-southeast1` Provisioning & Capture

Copy `.env.example` to `.env` (gitignored) and configure your non-production sandbox target:

```bash
cp .env.example .env
# Edit .env with your sandbox PROJECT_ID, BQ_LOCATION="asia-southeast1", DATASET_ID
```

Provision tables, 190 shadow clones, row-level security policies, and the BigQuery Property Graph:

```bash
bash scripts/provision_pack.sh
```

Validate query syntax and byte estimates (`--dry-run`), then execute live queries and negative governance controls (`--live-gcp`):

```bash
uv run python -m engine.capture_rungs --pack meridian_q3_sgd --dry-run
uv run python -m engine.capture_rungs --pack meridian_q3_sgd --live-gcp
```

#### Phase 2 Live Knowledge Catalog, Zero-Trust Agent & `N=5` Eval Architecture

- **Physical Blind Trap vs. Governed Marts (`meridian_blind`):** `scripts/provision_pack.sh` creates an unannotated `meridian_blind` CTAS copy alongside governed marts in `asia-southeast1`. Unannotated ERP `orders` columns (`amt_gross_billed_sgd`, `amt_item_subtotal_sgd`, `amt_gst_sgd`, `amt_net_settled_sgd`) and unranked lookalike cold-chain tables (`mart_coldchain_q3_r1`, `mart_coldchain_q3_r2`) cause blind agents to over-query schemas or pick the wrong metric without Knowledge Catalog context.
- **Knowledge Catalog Metadata & Unstructured Contract Layer (`scripts/provision_context_layer.py`):** Provisions Knowledge Catalog Glossary terms, `EntryLink` synonym/ownership relationships, `AspectType` governance metadata, and Auto DQ (`DataScan`) validation, plus the GCS Object Table `contract_docs_obj` feeding BigQuery `AI.GENERATE` into staging table `sla_overlay_extracted`.
- **Zero-Trust Live Agent SAs & AST `dry_run` Gate:** `POST /api/run-agent` enforces least-privilege service account boundaries (`meridian-blind-agent` scoped strictly to `meridian_blind`, `meridian-governed-agent` on curated views/catalog, and `meridian-sg-coldchain` for regional RLS verification), parses and validates generated SQL/ISO GQL via a `dry_run` AST gate before query execution, and enforces `X-Demo-Key` authentication when enabled.
- **Empirical `N=5` Eval Harness (`engine/eval_harness.py`):** Executes repeated blind and governed Gemini runs via the `global` PayGo inference endpoint against `asia-southeast1` BigQuery resources, records structured per-run telemetry in `results/live_eval_runs.jsonl`, and embeds `empirical_eval` summaries into `web/data/rungs_bundle.js`.
- **Cloud Run Deployment (`scripts/deploy_cloud_run.sh`):** Deploys the hardened FastAPI Stage + Workbench service and zero-trust runtime configuration to a target GCP project (for example `--project example-project-id`) in `asia-southeast1` with `X-Demo-Key` token protection for live-agent endpoints.

To tear down the sandbox dataset cleanly:

```bash
bash scripts/teardown_pack.sh --dry-run
bash scripts/teardown_pack.sh --yes
```

---

## Authoring New `packs/<pack_id>/` Scenarios

1. Create `packs/<pack_id>/pack.yaml` declaring metadata, `personas`, `invariants`, and `horizon_cards` conforming to `schemas/rung_v2.schema.json`.
2. Add `packs/<pack_id>/rungs/r1_*.yaml` through `r6_*.yaml` defining each rung's `question`, `poll`, `blind` vs `governed` outcomes, optional `identity_variants`, and `xray_summary`.
3. Add deterministic data generation (`seed_<pack_id>.py` exposing `generate_dataset(seed)` and `evaluate_invariants(tables, seed)`), BigQuery SQL/GQL DDL in `sql/`, and optional unstructured contract fixtures in `contracts/`.
4. Generate and validate your bundle without touching `engine/` or `web/`:

```bash
uv run python -m engine.capture_rungs --pack <pack_id> --offline-fixture
```

---

## Verification & Zero-Leak Hygiene

Before committing or sharing generated bundles, verify all mathematical invariants, schema contracts, UI contracts, and zero-leak checks:

```bash
uv run pytest
uv run python -m engine.leak_check
```

`engine/leak_check.py` fails closed if any tracked or non-ignored file contains non-placeholder GCP project IDs (anything other than `example-project-id`), service account or user emails, internal shortlinks, or corporate domain names.

---

## License

Apache License 2.0 — see [LICENSE](LICENSE).
