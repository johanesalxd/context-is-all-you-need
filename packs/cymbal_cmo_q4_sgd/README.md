# Cymbal Commerce 3-Screen Interactive Demo (`cymbal_cmo_q4_sgd`)

Self-contained, sanitized static presentation flow and SQL-only BigQuery ScenarioPack for **Cymbal Commerce — "Context Is All You Need"**, optionally wired to the live FastAPI + BigQuery runner.

## 3-Screen Presentation Flow (`web/cymbal/`)

1. **Entry Redirect (`/cymbal/` -> `intro_landing/`)**: `web/cymbal/index.html` immediately redirects to `./intro_landing/`.
2. **Screen 1 — Scene & Personas (`intro_landing/index.html`)**: Introduces Cymbal Commerce (SG & MY omnichannel retail), the Q4 budget-lock dilemma, and the two anonymized personas:
   - **Samir Gupta (`SG`)** — Chief Marketing Officer
   - **Jordan Ang (`JA`, "Jo")** — Chief Data Officer
3. **Screen 2 — Workspace Chat Context (`chat_intro_mockup/index.html`)**: Simulated Workspace Chat threads (Agency wrap, CFO budget warning, CDO handoff) linking directly to `../ui_studio_v5/index.html`.
4. **Screen 3 — Gemini Enterprise Studio (`ui_studio_v5/index.html`)**: Interactive 6-turn Raw Schema vs. Knowledge Catalog showcase backed by `ui_studio_v5/scenarios/storyline_data_v5.js`, plus session audit scoreboard (`closing_session_audit`).

## Feature Matrix: Live BigQuery vs. Stand-In vs. Canned

The studio renders fast, zero-latency cards and inline SVG charts in the browser by default (safe for live presentations and offline `file://` usage). When served by `server/app.py` with the three Cymbal BigQuery datasets provisioned, the Context Inspector exposes a **Live BigQuery Verification** card (`POST /api/run-rung`) so technical audiences can execute the underlying SQL/GQL live on BigQuery:

| Turn / Surface | Main UI Card & Visual | Live BigQuery (`POST /api/run-rung`) | What Executes in BigQuery (`asia-southeast1`) |
| :--- | :--- | :--- | :--- |
| **Q1 · Net Campaign Revenue** (`r1_net_revenue`) | Pre-rendered | **Live SQL** | Queries `cymbal_dw.campaign_orders` (raw gross) vs. `cymbal_commerce.campaign_orders` (attributed ex-GST settled + returns). |
| **Q2 · Return Spike Root Cause** (`r2_return_drivers`) | Pre-rendered | **Live SQL (Stand-In)** | Queries `cymbal_dw.campaign_returns_staging` vs. `cymbal_commerce.campaign_returns_certified`. Deterministic SQL stand-in; `AI.KEY_DRIVERS()` and BigQuery RLS policies are reference architecture (disclosed in Inspector). |
| **Q3 · Channel P&L** (`r3_channel_pnl`) | Pre-rendered | **Live SQL** | Queries `cymbal_dw.campaign_clicks_raw` (`1:N` fan-out) vs. grain-locked `cymbal_commerce.channel_pnl_orders` & `channel_pnl_spend`. |
| **Q4 · Promo Fraud Ring** (`r4_fraud_graph`) | Pre-rendered | **Live Property Graph ISO GQL** | Executes `GRAPH_TABLE(...cymbal_fraud_graph MATCH ...)` 4-hop traversal across 5 node tables and 4 edge tables (`28` devices, `640` accounts, `SGD 96,000` coupons). |
| **Q5 · Agency Clawback** (`r5_clawback_s3_pdf`) | Pre-rendered | **Live SQL (Regional Stand-In)** | Scans `1.42M` rows in `cymbal_lake.q3_paid_social_clicks` joined to pre-populated `cymbal_commerce.agency_msa_clause_7_4`. Regional copy in `asia-southeast1`; cross-cloud S3 federation and Object Table `AI.GENERATE()` are reference architecture (disclosed in Inspector). |
| **Q6 · Q4 Budget Forecast** (`r6_q4_forecast`) | Pre-rendered | **Live SQL (Table Stand-In)** | Queries `cymbal_dw.q3_weekly_gross_raw` vs. pre-computed `cymbal_commerce.q4_forecast`. Stand-in table; live `AI.FORECAST` model inference is reference architecture (disclosed in Inspector). |
| **Q7 · Session Audit Scoreboard** (`closing_session_audit`) | Pre-rendered | **Canned only** (no button) | Intentionally omitted from live execution to keep the runtime service account scoped strictly to dataset `READER` (no `INFORMATION_SCHEMA.JOBS` grant). |
| **Sibling Follow-Ups & Free-Form Prompts** | Pre-rendered | **Canned only** (no button) | Resolved in-browser via `storyline_data_v5.js`; no live LLM NL2SQL loop (`POST /api/run-agent` is not wired for this pack). |
| **Audience Polls** (`/api/poll/*`) | N/A | **Configured in pack YAML** | 4 poll prompts defined in `rungs/*.yaml` and queryable via `GET /api/poll/state?pack_id=cymbal_cmo_q4_sgd`. |

## Live BigQuery Bridge (`web/cymbal/ui_studio_v5/live_bridge.js`)

When `web/cymbal/ui_studio_v5/index.html` is served over HTTP/HTTPS alongside the FastAPI backend:

- On load, `live_bridge.js` reads any `?key=<TOKEN>` query parameter, persists it to `sessionStorage` (`context_demo_key`), and strips `key` from the browser URL via `window.history.replaceState` so token-gated direct links work cleanly without leaving the token in the address bar.
- It calls `GET /api/health` and activates **only** when `cymbal_cmo_q4_sgd` is present in `data.packs`. Under `file://` or without the pack loaded, it performs zero DOM mutations and logs zero errors.
- On every `renderInspector()` update, the studio dispatches a `v5:inspector` `CustomEvent` with `{ turnId, mode, isSibling }`.
- For primary turns `t1`..`t6` (mapped 1:1 to `r1_net_revenue`..`r6_q4_forecast`), `live_bridge.js` injects a **Live BigQuery Verification** card inside `#contextInspector` with an honest action button (**Run governed SQL on BigQuery** for Knowledge Catalog mode, **Run raw SQL on BigQuery** for Raw Schema mode). Sibling follow-ups and `closing_session_audit` receive no live button.
- Clicking the button sends `POST /api/run-rung` with `{ pack_id: "cymbal_cmo_q4_sgd", rung_id, mode }` (including `X-Demo-Key` from `sessionStorage.getItem("context_demo_key")` when `REQUIRE_TOKEN_FOR_RUN_RUNG=true`) and renders `execution_mode`, `latency_ms`, `row_count`, `sql_or_gql`, any governed provenance notice, and up to 10 result rows strictly via `document.createElement` and `textContent`.

## Re-Syncing Updated Static HTML Exports

Run the repeatable sync and sanitization script against a local export directory, passing presenter anonymization pairs at runtime:

```bash
uv run python scripts/sync_cymbal_static.py \
  --src /path/to/export \
  --replace "Presenter One=Samir Gupta" \
  --replace "Presenter Two=Jordan Ang"
```

Pass longest strings first (or repeat `--replace`) using explicit `OLD=NEW` pairs. The sync script rewrites absolute demo URLs to `../ui_studio_v5/index.html`, converts embedded base64 portrait `<img>` tags into styled CSS initials avatars, normalizes non-placeholder email domains to `@example.com`, preserves `ui_studio_v5/live_bridge.js`, injects the `v5:inspector` event dispatch hook, and runs `engine.leak_check` verification automatically.

## Provisioning, Dataset IAM & Teardown (SQL-Only Pack)

`cymbal_cmo_q4_sgd` is a pure-SQL pack with no external uploads or Python data generator. Replace `PROJECT_ID`, `BQ_LOCATION`, `REGION`, `SERVICE_NAME`, and `RUNTIME_SA` with your target project values before running.

### 1. Provision Tables & Property Graph in BigQuery

```bash
export PROJECT_ID="example-project-id"
export BQ_LOCATION="asia-southeast1"

for sql_file in \
  packs/cymbal_cmo_q4_sgd/sql/01_tables.sql \
  packs/cymbal_cmo_q4_sgd/sql/02_property_graph.sql; do
  sed -e "s/\${PROJECT_ID}/${PROJECT_ID}/g" -e "s/\${BQ_LOCATION}/${BQ_LOCATION}/g" "$sql_file" \
    | bq query --project_id="$PROJECT_ID" --location="$BQ_LOCATION" --use_legacy_sql=false
done
```

### 2. Grant Dataset-Only `READER` to the Cloud Run Runtime Service Account

Grant read access strictly on the three Cymbal datasets (do not grant project-wide `bigquery.dataViewer`):

```bash
export RUNTIME_SA="example-runner@${PROJECT_ID}.iam.gserviceaccount.com"

uv run python - "$PROJECT_ID" "$RUNTIME_SA" <<'PY'
import sys
from google.cloud import bigquery

project_id, runtime_sa = sys.argv[1], sys.argv[2]
client = bigquery.Client(project=project_id)

for ds_name in ("cymbal_dw", "cymbal_commerce", "cymbal_lake"):
    ds = client.get_dataset(f"{project_id}.{ds_name}")
    entries = list(ds.access_entries)
    if not any(e.entity_id == runtime_sa and e.role == "READER" for e in entries):
        entries.append(bigquery.AccessEntry(role="READER", entity_type="userByEmail", entity_id=runtime_sa))
        ds.access_entries = entries
        client.update_dataset(ds, ["access_entries"])
    print(f"Granted READER to {runtime_sa} on {project_id}.{ds_name}")
PY
```

### 3. Verify Live Execution & Export Check

```bash
uv run python -m engine.capture_rungs \
  --pack cymbal_cmo_q4_sgd \
  --live-gcp \
  --output /tmp/cymbal_bundle.js
```

### 4. Deploy a No-Traffic Cloud Run Preview Revision

Deploy a tagged preview revision without shifting production traffic (`meridian_q3_sgd` remains the default unless `PACK_ID` is explicitly changed):

```bash
export REGION="asia-southeast1"
export SERVICE_NAME="context-is-all-you-need"

gcloud run deploy "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --source=. \
  --service-account="$RUNTIME_SA" \
  --no-traffic \
  --tag=cymbal
```

If the service sets `REQUIRE_TOKEN_FOR_RUN_RUNG=true` (with `DEMO_SHARE_TOKEN` configured), open the direct studio URL with `?key=<TOKEN>` appended (for example `https://cymbal---<service-hash>.a.run.app/cymbal/ui_studio_v5/index.html?key=<TOKEN>`). `live_bridge.js` captures `key` into `sessionStorage`, strips it from the URL, and sends it as `X-Demo-Key` on `POST /api/run-rung`.

### 5. Teardown

Remove the three Cymbal datasets and all tables/graphs inside them when finished:

```bash
for ds_name in cymbal_dw cymbal_commerce cymbal_lake; do
  bq rm -r -f -d "${PROJECT_ID}:${ds_name}"
done
```
