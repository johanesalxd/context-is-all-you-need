#!/usr/bin/env bash
set -euo pipefail

# Deploy the Dual-Mode Stage/Workbench app + live BigQuery runner to Cloud Run
# in asia-southeast1 using a dedicated least-privilege service account.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

# Preserve Cloudtop CAA mTLS env vars while clearing hijacking overrides.
unset CLOUDSDK_ACTIVE_CONFIG_NAME \
  CLOUDSDK_AUTH_ACCESS_TOKEN \
  CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE \
  CLOUDSDK_CORE_PROJECT \
  CLOUDSDK_CORE_ACCOUNT \
  CLOUDSDK_BILLING_QUOTA_PROJECT \
  GOOGLE_APPLICATION_CREDENTIALS \
  BIGQUERYRC

load_env_defaults() {
  local env_file="$1"
  [[ -f "${env_file}" ]] || return 0
  while IFS= read -r raw_line || [[ -n "${raw_line}" ]]; do
    local line="${raw_line#"${raw_line%%[![:space:]]*}"}"
    [[ -z "${line}" || "${line}" == \#* ]] && continue
    line="${line#export }"
    [[ "${line}" == *=* ]] || continue
    local key="${line%%=*}"
    local val="${line#*=}"
    key="${key//[[:space:]]/}"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%"${val##*[![:space:]]}"}"
    if [[ ${#val} -ge 2 ]]; then
      if [[ "${val:0:1}" == '"' && "${val: -1}" == '"' ]]; then
        val="${val:1:-1}"
      elif [[ "${val:0:1}" == "'" && "${val: -1}" == "'" ]]; then
        val="${val:1:-1}"
      fi
    fi
    if [[ -n "${key}" && -z "${!key+x}" ]]; then
      export "${key}=${val}"
    fi
  done < "${env_file}"
}

load_env_defaults "${REPO_ROOT}/.env"
load_env_defaults "${REPO_ROOT}/.env.example"

PROJECT_ID="${PROJECT_ID:-}"
BQ_LOCATION="${BQ_LOCATION:-asia-southeast1}"
DATASET_ID="${DATASET_ID:-meridian_commerce}"
BLIND_DATASET_ID="${BLIND_DATASET_ID:-meridian_blind}"
PACK_ID="${PACK_ID:-meridian_q3_sgd}"
SERVICE_NAME="${SERVICE_NAME:-context-is-all-you-need}"
CLOUD_RUN_REGION="${CLOUD_RUN_REGION:-${BQ_LOCATION}}"
BQ_MAX_BYTES_BILLED="${BQ_MAX_BYTES_BILLED:-104857600}"
RUN_RUNG_RPM_LIMIT="${RUN_RUNG_RPM_LIMIT:-30}"
AGENT_MODEL_ID="${AGENT_MODEL_ID:-gemini-3.8-flash}"
AGENT_MODEL_LOCATION="${AGENT_MODEL_LOCATION:-global}"
BQ_CONNECTION_ID="${BQ_CONNECTION_ID:-meridian_vertex_conn}"
ENABLE_LIVE_AGENT="${ENABLE_LIVE_AGENT:-true}"
REQUIRE_TOKEN_FOR_LIVE_AGENT="${REQUIRE_TOKEN_FOR_LIVE_AGENT:-true}"
REQUIRE_TOKEN_FOR_RUN_RUNG="${REQUIRE_TOKEN_FOR_RUN_RUNG:-false}"
DAILY_AGENT_CALL_LIMIT="${DAILY_AGENT_CALL_LIMIT:-200}"
ENABLE_LIVE_POLL="${ENABLE_LIVE_POLL:-true}"
POLL_READ_RPM_LIMIT="${POLL_READ_RPM_LIMIT:-3000}"
POLL_VOTE_RPM_LIMIT="${POLL_VOTE_RPM_LIMIT:-240}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
DEMO_SHARE_TOKEN="${DEMO_SHARE_TOKEN:-}"
DRY_RUN=0
APP_ONLY=0
PACK_EXPLICIT=0
ENABLE_SHARE_TOKEN=0
ROTATE_TOKEN=0

run_repo_python() {
  if command -v uv >/dev/null 2>&1; then
    uv run --project "${REPO_ROOT}" python "$@"
  elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    "${REPO_ROOT}/.venv/bin/python" "$@"
  else
    /usr/bin/python3 -IB "$@"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --app-only)
      APP_ONLY=1
      shift
      ;;
    --pack)
      PACK_ID="$2"
      PACK_EXPLICIT=1
      shift 2
      ;;
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --region)
      CLOUD_RUN_REGION="$2"
      shift 2
      ;;
    --enable-share-token)
      ENABLE_SHARE_TOKEN=1
      shift
      ;;
    --rotate-token)
      ENABLE_SHARE_TOKEN=1
      ROTATE_TOKEN=1
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [--app-only] [--project PROJECT_ID] [--pack PACK_ID] [--service-name NAME] [--region REGION] [--enable-share-token] [--rotate-token]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "example-project-id" ]]; then
  if [[ "${DRY_RUN}" -eq 1 ]]; then
    PROJECT_ID="example-project-id"
  else
    echo "ERROR: PROJECT_ID must be set to a real non-placeholder GCP project ID in .env." >&2
    exit 1
  fi
fi

# Dynamically discover the RLS target table and CFO policy from the active ScenarioPack.
RLS_DISCOVERY="$(
  PACK_ID="${PACK_ID}" REPO_ROOT="${REPO_ROOT}" run_repo_python - <<'PY' 2>/dev/null || true
import os, re
from pathlib import Path

pack_id = os.environ["PACK_ID"]
root = Path(os.environ["REPO_ROOT"])
rls_path = root / "packs" / pack_id / "sql" / "03_rls.sql"
table_name, policy_name = None, None
try:
    import sys
    sys.path.insert(0, str(root))
    from engine.pack_loader import discover_rls_target
    table_name, policy_name = discover_rls_target(pack_id)
except Exception:
    if rls_path.is_file():
        text = rls_path.read_text(encoding="utf-8")
        for m in re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?ROW\s+ACCESS\s+POLICY\s+([^\s]+)\s+ON\s+([^\s(]+)", text, re.I):
            pol = m.group(1).strip('`"')
            tbl = m.group(2).strip('`"').split(".")[-1].strip('`"')
            if table_name is None or any(k in pol.lower() for k in ("cfo", "all", "regional", "global")):
                table_name, policy_name = tbl, pol
                if "cfo" in pol.lower():
                    break
print(f"{table_name or 'mart_coldchain_q3_r2'}|{policy_name or 'rls_cfo_regional_all_markets'}")
PY
)"
RLS_TABLE="${RLS_DISCOVERY%%|*}"
RLS_CFO_POLICY="${RLS_DISCOVERY##*|}"
[[ -n "${RLS_TABLE}" ]] || RLS_TABLE="mart_coldchain_q3_r2"
[[ -n "${RLS_CFO_POLICY}" ]] || RLS_CFO_POLICY="rls_cfo_regional_all_markets"

PACK_PREFIX="${PACK_ID%%_*}"
[[ -n "${PACK_PREFIX}" ]] || PACK_PREFIX="meridian"
if [[ -z "${FIRESTORE_DATABASE_ID:-}" || "${FIRESTORE_DATABASE_ID}" == "example-polls" ]]; then
  FIRESTORE_DATABASE_ID="${PACK_PREFIX}-polls"
fi
if [[ "${ENABLE_LIVE_POLL}" == "true" && "${FIRESTORE_DATABASE_ID}" != "none" ]]; then
  if [[ ! "${FIRESTORE_DATABASE_ID}" =~ ^[a-z][a-z0-9-]{2,61}[a-z0-9]$ ]]; then
    echo "ERROR: Invalid FIRESTORE_DATABASE_ID '${FIRESTORE_DATABASE_ID}'; expected ^[a-z][a-z0-9-]{2,61}[a-z0-9]$." >&2
    exit 1
  fi
fi
if [[ -n "${PUBLIC_BASE_URL}" && ! "${PUBLIC_BASE_URL}" =~ ^https?://([A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(:[0-9]{1,5})?/?$ ]]; then
  echo "ERROR: Invalid PUBLIC_BASE_URL '${PUBLIC_BASE_URL}'; expected bare https://host[:port] or http://host[:port] origin without path." >&2
  exit 1
fi
RUNNER_SA_NAME="${PACK_PREFIX}-web-runner"
RUNNER_SA_EMAIL="${RUNNER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SG_RLS_SA_EMAIL="${PACK_PREFIX}-sg-coldchain@${PROJECT_ID}.iam.gserviceaccount.com"
BLIND_AGENT_SA_EMAIL="${PACK_PREFIX}-blind-agent@${PROJECT_ID}.iam.gserviceaccount.com"
GOVERNED_AGENT_SA_EMAIL="${PACK_PREFIX}-governed-agent@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ "${APP_ONLY}" -eq 1 && "${PACK_EXPLICIT}" -eq 1 ]]; then
  echo "ERROR: --app-only cannot be combined with --pack (--app-only preserves the live service's existing PACK_ID and env vars; run a full deploy to switch packs)." >&2
  exit 2
fi

if [[ "${APP_ONLY}" -eq 1 && ( "${ENABLE_SHARE_TOKEN}" -eq 1 || "${ROTATE_TOKEN}" -eq 1 ) ]]; then
  echo "ERROR: --app-only cannot be combined with --enable-share-token or --rotate-token (use full deploy to mutate service env vars)." >&2
  exit 2
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ "${APP_ONLY}" -eq 1 ]]; then
    echo "[DRY RUN] --app-only Cloud Run redeploy plan:"
    echo "  Project:          ${PROJECT_ID}"
    echo "  Region:           ${CLOUD_RUN_REGION}"
    echo "  Service:          ${SERVICE_NAME}"
    echo "  Skipped:          API enablement, SA/IAM bootstrap, Firestore creation, BQ dataset ACL updates, RLS policy recreation, and .env/env-var overwrite"
    echo "  Deploy:           gcloud run deploy ${SERVICE_NAME} --project=${PROJECT_ID} --source=${REPO_ROOT} --region=${CLOUD_RUN_REGION} --quiet (preserves existing env vars, SA, and IAM policy)"
    exit 0
  fi
  echo "[DRY-RUN] Cloud Run foundation deployment plan:"
  echo "  Project:          ${PROJECT_ID}"
  echo "  Region:           ${CLOUD_RUN_REGION}"
  echo "  Service:          ${SERVICE_NAME}"
  echo "  Runtime SA:       ${RUNNER_SA_EMAIL} (dataset READER on ${DATASET_ID} + zero access to ${BLIND_DATASET_ID} + bigquery.jobUser + aiplatform.user + datastore.user + TokenCreator on ${SG_RLS_SA_EMAIL}, ${BLIND_AGENT_SA_EMAIL}, ${GOVERNED_AGENT_SA_EMAIL})"
  echo "  Poll Database:    Firestore Native '${FIRESTORE_DATABASE_ID}' in ${BQ_LOCATION} (roles/datastore.user strictly on ${RUNNER_SA_EMAIL}; excluded from ${BLIND_AGENT_SA_EMAIL} and ${GOVERNED_AGENT_SA_EMAIL})"
  echo "  RLS Policy Sync:  Grant ${RLS_CFO_POLICY} on ${DATASET_ID}.${RLS_TABLE} to ${GOVERNED_AGENT_SA_EMAIL} and ${RUNNER_SA_EMAIL}"
  echo "  Live Agent Config: model=${AGENT_MODEL_ID}@${AGENT_MODEL_LOCATION}, blind_dataset=${BLIND_DATASET_ID}, enable_live_agent=${ENABLE_LIVE_AGENT}, require_token_live=${REQUIRE_TOKEN_FOR_LIVE_AGENT}, daily_limit=${DAILY_AGENT_CALL_LIMIT}"
  echo "  Guardrails:       min-instances=0, max-instances=2, BQ_MAX_BYTES_BILLED=${BQ_MAX_BYTES_BILLED}, RUN_RUNG_RPM_LIMIT=${RUN_RUNG_RPM_LIMIT}, ENABLE_LIVE_POLL=${ENABLE_LIVE_POLL}, POLL_READ_RPM_LIMIT=${POLL_READ_RPM_LIMIT}, POLL_VOTE_RPM_LIMIT=${POLL_VOTE_RPM_LIMIT}, DEMO_SHARE_TOKEN enabled"
  exit 0
fi

if [[ "${APP_ONLY}" -eq 1 ]]; then
  DESCRIBE_ERR_FILE="$(mktemp)"
  if DESCRIBE_RAW="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${CLOUD_RUN_REGION}" --format='value(status.url)' 2>"${DESCRIBE_ERR_FILE}")"; then
    rm -f "${DESCRIBE_ERR_FILE}"
    EXISTING_URL="$(printf '%s\n' "${DESCRIBE_RAW}" | { grep -v '^Created ' || true; } | tail -n 1)"
    if [[ -z "${EXISTING_URL}" ]]; then
      echo "ERROR: Cloud Run service '${SERVICE_NAME}' returned an empty status.url." >&2
      exit 1
    fi
  else
    DESCRIBE_ERR="$(cat "${DESCRIBE_ERR_FILE}" 2>/dev/null || true)"
    rm -f "${DESCRIBE_ERR_FILE}"
    if printf '%s' "${DESCRIBE_ERR}" | grep -qiE 'NOT_FOUND|could not be found|Cannot find service'; then
      echo "ERROR: Cloud Run service '${SERVICE_NAME}' was not found in ${PROJECT_ID} (${CLOUD_RUN_REGION})." >&2
      echo "Run a full deploy first without --app-only to provision IAM, Firestore, BigQuery ACLs, RLS, and service env vars." >&2
    else
      echo "ERROR: Failed to inspect Cloud Run service '${SERVICE_NAME}' in ${PROJECT_ID} (${CLOUD_RUN_REGION}):" >&2
      printf '%s\n' "${DESCRIBE_ERR}" >&2
    fi
    exit 1
  fi

  CLOUDSDK_CORE_INTERACTIVE_UX_STYLE=OFF gcloud run deploy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --source="${REPO_ROOT}" \
    --region="${CLOUD_RUN_REGION}" \
    --quiet

  SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${CLOUD_RUN_REGION}" --format='value(status.url)' | grep -v '^Created ' | tail -n 1)"
  echo "Deployed Cloud Run Service (--app-only): ${SERVICE_URL}"
  exit 0
fi

# 1. Generate/persist DEMO_SHARE_TOKEN in .env (never echoed raw) when live agent requires auth or requested.
if [[ "${ENABLE_SHARE_TOKEN}" -eq 1 || "${REQUIRE_TOKEN_FOR_LIVE_AGENT}" == "true" ]]; then
  if [[ -z "${DEMO_SHARE_TOKEN}" || "${ROTATE_TOKEN}" -eq 1 ]]; then
    DEMO_SHARE_TOKEN="$(/usr/bin/python3 -IB -c 'import secrets; print(secrets.token_urlsafe(18))')"
    if [[ -f "${REPO_ROOT}/.env" ]]; then
      grep -v '^DEMO_SHARE_TOKEN=' "${REPO_ROOT}/.env" > "${REPO_ROOT}/.env.tmp" || true
      mv "${REPO_ROOT}/.env.tmp" "${REPO_ROOT}/.env"
    fi
    printf 'DEMO_SHARE_TOKEN="%s"\n' "${DEMO_SHARE_TOKEN}" >> "${REPO_ROOT}/.env"
    chmod 600 "${REPO_ROOT}/.env"
  fi
else
  DEMO_SHARE_TOKEN=""
fi

# 2. Provision dedicated least-privilege runtime SA (never use default Compute SA)
if ! gcloud iam service-accounts describe "${RUNNER_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${RUNNER_SA_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="Context Stage Cloud Run Runner" \
    --quiet >/dev/null
fi

for runner_role in roles/bigquery.jobUser roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNNER_SA_EMAIL}" \
    --role="${runner_role}" \
    --condition=None \
    --quiet >/dev/null
done

# Enable Firestore Native API, provision dedicated poll database, and grant datastore.user ONLY when ENABLE_LIVE_POLL=true.
if [[ "${ENABLE_LIVE_POLL}" == "true" && -n "${FIRESTORE_DATABASE_ID}" && "${FIRESTORE_DATABASE_ID}" != "none" ]]; then
  gcloud services enable firestore.googleapis.com --project="${PROJECT_ID}" --quiet >/dev/null
  if ! gcloud firestore databases describe --database="${FIRESTORE_DATABASE_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud firestore databases create \
      --database="${FIRESTORE_DATABASE_ID}" \
      --location="${BQ_LOCATION}" \
      --type=firestore-native \
      --project="${PROJECT_ID}" \
      --quiet >/dev/null
  fi
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${RUNNER_SA_EMAIL}" \
    --role="roles/datastore.user" \
    --condition=None \
    --quiet >/dev/null
fi

# Grant TokenCreator strictly on the RLS persona SA, Blind Agent SA, and Governed Agent SA
for target_sa in "${SG_RLS_SA_EMAIL}" "${BLIND_AGENT_SA_EMAIL}" "${GOVERNED_AGENT_SA_EMAIL}"; do
  if gcloud iam service-accounts describe "${target_sa}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts add-iam-policy-binding "${target_sa}" \
      --project="${PROJECT_ID}" \
      --member="serviceAccount:${RUNNER_SA_EMAIL}" \
      --role="roles/iam.serviceAccountTokenCreator" \
      --condition=None \
      --quiet >/dev/null
  fi
done

export REPO_ROOT PROJECT_ID DATASET_ID BLIND_DATASET_ID BQ_LOCATION RUNNER_SA_EMAIL GOVERNED_AGENT_SA_EMAIL SG_RLS_SA_EMAIL BLIND_AGENT_SA_EMAIL RLS_TABLE RLS_CFO_POLICY
bq add-iam-policy-binding \
  --member="serviceAccount:${RUNNER_SA_EMAIL}" \
  --role="roles/bigquery.dataOwner" \
  "${PROJECT_ID}:${DATASET_ID}.${RLS_TABLE}" >/dev/null

run_repo_python - <<'PY'
import os
import sys
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

repo_root = os.environ["REPO_ROOT"]
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from engine.capture_rungs import list_active_row_access_policies

project_id = os.environ["PROJECT_ID"]
dataset_id = os.environ["DATASET_ID"]
blind_dataset_id = os.environ["BLIND_DATASET_ID"]
bq_location = os.environ["BQ_LOCATION"]
runner_sa = os.environ["RUNNER_SA_EMAIL"]
governed_sa = os.environ["GOVERNED_AGENT_SA_EMAIL"]
rls_table = os.environ["RLS_TABLE"]
rls_cfo_policy = os.environ["RLS_CFO_POLICY"]

client = bigquery.Client(project=project_id, location=bq_location)
ds_ref = f"{project_id}.{dataset_id}"
dataset = client.get_dataset(ds_ref)
entries = list(dataset.access_entries)
target_entry = bigquery.AccessEntry(
    role="READER",
    entity_type="userByEmail",
    entity_id=runner_sa,
)
if not any(e.entity_id == runner_sa and e.role == "READER" for e in entries):
    entries.append(target_entry)
    dataset.access_entries = entries
    client.update_dataset(dataset, ["access_entries"])

# Ensure Cloud Run runner SA has zero dataset access to BLIND_DATASET_ID.
try:
    blind_ds = client.get_dataset(f"{project_id}.{blind_dataset_id}")
    scrub = {runner_sa.lower(), f"serviceaccount:{runner_sa.lower()}"}
    filtered = [e for e in blind_ds.access_entries if (e.entity_id or "").lower() not in scrub]
    if len(filtered) != len(blind_ds.access_entries):
        blind_ds.access_entries = filtered
        client.update_dataset(blind_ds, ["access_entries"])
except NotFound:
    pass

# Ensure governed_agent_sa and runner_sa are included in rls_cfo_regional_all_markets while preserving existing collaborator grantees.
active_user_rows = list(client.query("SELECT SESSION_USER() AS u", location=bq_location).result())
caller_email = str(active_user_rows[0]["u"]).strip()
caller_member = f"serviceAccount:{caller_email}" if caller_email.endswith(".gserviceaccount.com") else f"user:{caller_email}"

merged_grantees: dict[str, str] = {}

def _add_grantee(principal: str) -> None:
    cleaned = str(principal or "").strip()
    if cleaned:
        merged_grantees.setdefault(cleaned.lower(), cleaned)

_add_grantee(caller_member)
_add_grantee(f"serviceAccount:{governed_sa}")
_add_grantee(f"serviceAccount:{runner_sa}")

sg_rls_sa = os.environ.get("SG_RLS_SA_EMAIL", "").strip().lower()
blind_sa = os.environ.get("BLIND_AGENT_SA_EMAIL", "").strip().lower()
excluded_principals = {
    f"serviceaccount:{sa}" for sa in (sg_rls_sa, blind_sa) if sa
}

policy_exists = False
existing_grantees: list[str] = []
for pol in list_active_row_access_policies(
    client,
    project_id=project_id,
    dataset_id=dataset_id,
    table_id=rls_table,
    location=bq_location,
):
    if pol.get("policy_id") == rls_cfo_policy:
        policy_exists = True
        existing_grantees.extend(str(g or "").strip() for g in (pol.get("grantees") or []) if str(g or "").strip())

if policy_exists and not existing_grantees:
    raise RuntimeError(
        f"Refusing to overwrite existing RLS policy {rls_cfo_policy}: could not read existing grantees"
    )

for g_str in existing_grantees:
    g_low = g_str.lower()
    if g_low.startswith("deleted:"):
        continue
    if g_low in excluded_principals or "coldchain" in g_low or "denied" in g_low or "blind-agent" in g_low:
        continue
    _add_grantee(g_str)

grantee_list = sorted(merged_grantees.values(), key=lambda x: x.lower())
grant_sql = ", ".join(f'"{g}"' for g in grantee_list)
rls_sql = f"""
CREATE OR REPLACE ROW ACCESS POLICY `{rls_cfo_policy}`
ON `{project_id}.{dataset_id}.{rls_table}`
GRANT TO ({grant_sql})
FILTER USING (TRUE)
"""
client.query(rls_sql, location=bq_location).result()
PY

ROLE_SA_MAP_JSON="{\"sg_coldchain\":\"${SG_RLS_SA_EMAIL}\"}"
AGENT_SA_MAP_JSON="{\"blind\":\"${BLIND_AGENT_SA_EMAIL}\",\"governed\":\"${GOVERNED_AGENT_SA_EMAIL}\"}"
ENV_FILE_TMP="$(mktemp)"
trap 'rm -f "${ENV_FILE_TMP}"' EXIT
cat > "${ENV_FILE_TMP}" <<EOF
PROJECT_ID: "${PROJECT_ID}"
BQ_LOCATION: "${BQ_LOCATION}"
DATASET_ID: "${DATASET_ID}"
BLIND_DATASET_ID: "${BLIND_DATASET_ID}"
PACK_ID: "${PACK_ID}"
BQ_MAX_BYTES_BILLED: "${BQ_MAX_BYTES_BILLED}"
RUN_RUNG_RPM_LIMIT: "${RUN_RUNG_RPM_LIMIT}"
AGENT_MODEL_ID: "${AGENT_MODEL_ID}"
AGENT_MODEL_LOCATION: "${AGENT_MODEL_LOCATION}"
BQ_CONNECTION_ID: "${BQ_CONNECTION_ID}"
ENABLE_LIVE_AGENT: "${ENABLE_LIVE_AGENT}"
REQUIRE_TOKEN_FOR_LIVE_AGENT: "${REQUIRE_TOKEN_FOR_LIVE_AGENT}"
REQUIRE_TOKEN_FOR_RUN_RUNG: "${REQUIRE_TOKEN_FOR_RUN_RUNG}"
DAILY_AGENT_CALL_LIMIT: "${DAILY_AGENT_CALL_LIMIT}"
FIRESTORE_DATABASE_ID: "${FIRESTORE_DATABASE_ID}"
ENABLE_LIVE_POLL: "${ENABLE_LIVE_POLL}"
POLL_READ_RPM_LIMIT: "${POLL_READ_RPM_LIMIT}"
POLL_VOTE_RPM_LIMIT: "${POLL_VOTE_RPM_LIMIT}"
PUBLIC_BASE_URL: "${PUBLIC_BASE_URL}"
DEMO_SHARE_TOKEN: "${DEMO_SHARE_TOKEN}"
SQL_ROLE_SA_MAP_JSON: '${ROLE_SA_MAP_JSON}'
AGENT_SA_MAP_JSON: '${AGENT_SA_MAP_JSON}'
EOF

CLOUDSDK_CORE_INTERACTIVE_UX_STYLE=OFF gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --source="${REPO_ROOT}" \
  --region="${CLOUD_RUN_REGION}" \
  --service-account="${RUNNER_SA_EMAIL}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=2 \
  --concurrency=16 \
  --memory=512Mi \
  --env-vars-file="${ENV_FILE_TMP}" \
  --labels=managed-by=cloud-express,app=context-is-all-you-need \
  --quiet

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${CLOUD_RUN_REGION}" --format='value(status.url)' | grep -v '^Created ' | tail -n 1)"
echo "Deployed Cloud Run Service: ${SERVICE_URL}"
if [[ -n "${DEMO_SHARE_TOKEN}" ]]; then
  echo "Shareable Live Demo URL:    ${SERVICE_URL}/?key=[REDACTED_SAVED_IN_DOTENV]"
else
  echo "Shareable Live Demo URL:    ${SERVICE_URL}"
fi
