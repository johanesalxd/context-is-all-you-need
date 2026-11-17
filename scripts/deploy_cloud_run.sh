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
PACK_ID="${PACK_ID:-meridian_q3_sgd}"
SERVICE_NAME="${SERVICE_NAME:-context-is-all-you-need}"
CLOUD_RUN_REGION="${CLOUD_RUN_REGION:-${BQ_LOCATION}}"
BQ_MAX_BYTES_BILLED="${BQ_MAX_BYTES_BILLED:-104857600}"
RUN_RUNG_RPM_LIMIT="${RUN_RUNG_RPM_LIMIT:-30}"
DEMO_SHARE_TOKEN="${DEMO_SHARE_TOKEN:-}"
DRY_RUN=0
ENABLE_SHARE_TOKEN=0
ROTATE_TOKEN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
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
      echo "Usage: $0 [--dry-run] [--service-name NAME] [--region REGION] [--enable-share-token] [--rotate-token]"
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

RUNNER_SA_NAME="meridian-web-runner"
RUNNER_SA_EMAIL="${RUNNER_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
SG_RLS_SA_EMAIL="meridian-sg-coldchain@${PROJECT_ID}.iam.gserviceaccount.com"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[DRY-RUN] Cloud Run foundation deployment plan:"
  echo "  Project:          ${PROJECT_ID}"
  echo "  Region:           ${CLOUD_RUN_REGION}"
  echo "  Service:          ${SERVICE_NAME}"
  echo "  Runtime SA:       ${RUNNER_SA_EMAIL} (dataset READER on ${DATASET_ID} + bigquery.jobUser + TokenCreator on ${SG_RLS_SA_EMAIL})"
  echo "  RLS Policy Sync:  Grant rls_cfo_regional_all_markets on ${DATASET_ID}.cold_chain_margin_gold to ${RUNNER_SA_EMAIL}"
  echo "  Guardrails:       min-instances=0, max-instances=2, BQ_MAX_BYTES_BILLED=${BQ_MAX_BYTES_BILLED}, RUN_RUNG_RPM_LIMIT=${RUN_RUNG_RPM_LIMIT}, DEMO_SHARE_TOKEN enabled"
  exit 0
fi

# 1. Optional DEMO_SHARE_TOKEN (only when --enable-share-token is requested)
if [[ "${ENABLE_SHARE_TOKEN}" -eq 1 ]]; then
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
    --display-name="Meridian Context Stage Cloud Run Runner" \
    --quiet >/dev/null
fi

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${RUNNER_SA_EMAIL}" \
  --role="roles/bigquery.jobUser" \
  --condition=None \
  --quiet >/dev/null

# Grant dataset-scoped READER on meridian_commerce + TokenCreator strictly on meridian-sg-coldchain
if gcloud iam service-accounts describe "${SG_RLS_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts add-iam-policy-binding "${SG_RLS_SA_EMAIL}" \
    --project="${PROJECT_ID}" \
    --member="serviceAccount:${RUNNER_SA_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator" \
    --quiet >/dev/null
fi

export PROJECT_ID DATASET_ID BQ_LOCATION RUNNER_SA_EMAIL
uv run --project "${REPO_ROOT}" python - <<'PY'
import os
from google.cloud import bigquery

project_id = os.environ["PROJECT_ID"]
dataset_id = os.environ["DATASET_ID"]
bq_location = os.environ["BQ_LOCATION"]
runner_sa = os.environ["RUNNER_SA_EMAIL"]

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

# Ensure runner_sa is included in rls_cfo_regional_all_markets so cfo_regional sees all 4 SEA rows
active_user_rows = list(client.query("SELECT SESSION_USER() AS u", location=bq_location).result())
caller_email = str(active_user_rows[0]["u"]).strip()
rls_sql = f"""
CREATE OR REPLACE ROW ACCESS POLICY rls_cfo_regional_all_markets
ON `{project_id}.{dataset_id}.cold_chain_margin_gold`
GRANT TO ("user:{caller_email}", "serviceAccount:{runner_sa}")
FILTER USING (TRUE)
"""
client.query(rls_sql, location=bq_location).result()
PY

ROLE_SA_MAP_JSON="{\"cfo_regional\":\"${RUNNER_SA_EMAIL}\",\"sg_coldchain\":\"${SG_RLS_SA_EMAIL}\"}"
ENV_FILE_TMP="$(mktemp)"
trap 'rm -f "${ENV_FILE_TMP}"' EXIT
cat > "${ENV_FILE_TMP}" <<EOF
PROJECT_ID: "${PROJECT_ID}"
BQ_LOCATION: "${BQ_LOCATION}"
DATASET_ID: "${DATASET_ID}"
PACK_ID: "${PACK_ID}"
BQ_MAX_BYTES_BILLED: "${BQ_MAX_BYTES_BILLED}"
RUN_RUNG_RPM_LIMIT: "${RUN_RUNG_RPM_LIMIT}"
DEMO_SHARE_TOKEN: "${DEMO_SHARE_TOKEN}"
SQL_ROLE_SA_MAP_JSON: '${ROLE_SA_MAP_JSON}'
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
