#!/usr/bin/env bash
set -euo pipefail

# Safely tear down a provisioned ScenarioPack BigQuery dataset.

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
DATASET_ID="${DATASET_ID:-}"
PACK_ID="${PACK_ID:-meridian_q3_sgd}"
BQ_LOCATION="${BQ_LOCATION:-asia-southeast1}"
CLOUD_RUN_REGION="${CLOUD_RUN_REGION:-${BQ_LOCATION}}"
DRY_RUN=0
CONFIRM_YES=0
DELETE_RLS_SAS=0
DELETE_CLOUD_RUN=0
DELETE_POLL_DB=0
TEARDOWN_CONTEXT_LAYER=1
SERVICE_NAME="${SERVICE_NAME:-context-is-all-you-need}"

run_repo_python() {
  if command -v uv >/dev/null 2>&1; then
    uv run --project "${REPO_ROOT}" python "$@"
  elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    "${REPO_ROOT}/.venv/bin/python" "$@"
  else
    return 127
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --yes|-y)
      CONFIRM_YES=1
      shift
      ;;
    --pack)
      PACK_ID="$2"
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
      BQ_LOCATION="$2"
      shift 2
      ;;
    --teardown-context-layer)
      TEARDOWN_CONTEXT_LAYER=1
      shift
      ;;
    --skip-context-layer)
      TEARDOWN_CONTEXT_LAYER=0
      shift
      ;;
    --delete-rls-sas)
      DELETE_RLS_SAS=1
      shift
      ;;
    --delete-cloud-run)
      DELETE_CLOUD_RUN=1
      shift
      ;;
    --delete-poll-db)
      DELETE_POLL_DB=1
      shift
      ;;
    --all)
      DELETE_RLS_SAS=1
      DELETE_CLOUD_RUN=1
      DELETE_POLL_DB=1
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--pack PACK_ID] [--project PROJECT_ID] [--service-name NAME] [--region REGION] [--dry-run] [--yes] [--teardown-context-layer] [--skip-context-layer] [--delete-rls-sas] [--delete-cloud-run] [--delete-poll-db] [--all]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "example-project-id" ]]; then
  echo "ERROR: PROJECT_ID must be set to a real non-placeholder GCP project ID." >&2
  exit 1
fi
if [[ ! "${DATASET_ID}" =~ ^[A-Za-z_][A-Za-z0-9_]{0,1023}$ ]]; then
  echo "ERROR: Invalid or empty DATASET_ID: '${DATASET_ID}'" >&2
  exit 1
fi

PACK_PREFIX="${PACK_ID%%_*}"
[[ -n "${PACK_PREFIX}" ]] || PACK_PREFIX="meridian"
if [[ -z "${FIRESTORE_DATABASE_ID:-}" || "${FIRESTORE_DATABASE_ID}" == "example-polls" ]]; then
  FIRESTORE_DATABASE_ID="${PACK_PREFIX}-polls"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
  if [[ "${TEARDOWN_CONTEXT_LAYER}" -eq 1 ]]; then
    echo "[DRY-RUN] Would tear down Phase 2 context layer for pack=${PACK_ID} before deleting ${PROJECT_ID}.${DATASET_ID}."
    if [[ -f "${REPO_ROOT}/scripts/provision_context_layer.py" ]]; then
      ctx_args=(--pack "${PACK_ID}" --teardown --dry-run)
      if [[ "${DELETE_RLS_SAS}" -eq 1 ]]; then
        ctx_args+=(--delete-agent-sas)
      fi
      if command -v uv >/dev/null 2>&1 || [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
        PROJECT_ID="example-project-id" run_repo_python "${REPO_ROOT}/scripts/provision_context_layer.py" "${ctx_args[@]}"
      else
        echo "[DRY-RUN] (Skipping detailed context-layer JSON preview; uv/.venv python not on PATH.)"
      fi
    fi
  fi
  echo "[DRY-RUN] Would delete BigQuery dataset ${PROJECT_ID}.${DATASET_ID} (location=${BQ_LOCATION}) and all its contents."
  if [[ "${DELETE_CLOUD_RUN}" -eq 1 ]]; then
    echo "[DRY-RUN] Would delete Cloud Run service ${SERVICE_NAME} (${CLOUD_RUN_REGION}), Artifact Registry package cloud-run-source-deploy/${SERVICE_NAME} (${CLOUD_RUN_REGION}), remove project IAM bindings (jobUser, aiplatform.user, datastore.user), and delete ${PACK_PREFIX}-web-runner@${PROJECT_ID}.iam.gserviceaccount.com"
  fi
  if [[ "${DELETE_POLL_DB}" -eq 1 ]]; then
    echo "[DRY-RUN] Would delete Firestore Native poll database '${FIRESTORE_DATABASE_ID}' in project ${PROJECT_ID}."
  fi
  if [[ "${DELETE_RLS_SAS}" -eq 1 ]]; then
    echo "[DRY-RUN] Would remove project jobUser bindings and delete dedicated RLS SAs: meridian-sg-coldchain@${PROJECT_ID}.iam.gserviceaccount.com, meridian-denied-probe@${PROJECT_ID}.iam.gserviceaccount.com"
  fi
  exit 0
fi

if [[ "${CONFIRM_YES}" -ne 1 ]]; then
  echo "ERROR: Refusing destructive teardown without --yes (or pass --dry-run)." >&2
  exit 1
fi

if [[ "${TEARDOWN_CONTEXT_LAYER}" -eq 1 && -f "${REPO_ROOT}/scripts/provision_context_layer.py" ]]; then
  ctx_args=(--pack "${PACK_ID}" --teardown)
  if [[ "${DELETE_RLS_SAS}" -eq 1 ]]; then
    ctx_args+=(--delete-agent-sas)
  fi
  run_repo_python "${REPO_ROOT}/scripts/provision_context_layer.py" "${ctx_args[@]}"
fi

export PROJECT_ID DATASET_ID BQ_LOCATION
run_repo_python - <<'PY'
import os
from google.cloud import bigquery

project_id = os.environ["PROJECT_ID"]
dataset_id = os.environ["DATASET_ID"]
bq_location = os.environ["BQ_LOCATION"]

client = bigquery.Client(project=project_id, location=bq_location)
client.delete_dataset(f"{project_id}.{dataset_id}", delete_contents=True, not_found_ok=True)
print(f"Deleted dataset (if existed): {dataset_id}")
PY

if [[ "${DELETE_RLS_SAS}" -eq 1 ]]; then
  for sa_name in meridian-sg-coldchain meridian-denied-probe; do
    sa_email="${sa_name}@${PROJECT_ID}.iam.gserviceaccount.com"
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${sa_email}" \
      --role="roles/bigquery.jobUser" \
      --all \
      --quiet >/dev/null 2>&1 || true
    if gcloud iam service-accounts describe "${sa_email}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
      gcloud iam service-accounts delete "${sa_email}" --project="${PROJECT_ID}" --quiet >/dev/null
      echo "Deleted dedicated RLS sandbox SA: ${sa_email}"
    fi
  done
fi

if [[ "${DELETE_CLOUD_RUN}" -eq 1 ]]; then
  gcloud run services delete "${SERVICE_NAME}" --project="${PROJECT_ID}" --region="${CLOUD_RUN_REGION}" --quiet >/dev/null 2>&1 || true
  gcloud artifacts packages delete "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${CLOUD_RUN_REGION}" \
    --repository="cloud-run-source-deploy" \
    --quiet >/dev/null 2>&1 || true
  runner_sa="${PACK_PREFIX}-web-runner@${PROJECT_ID}.iam.gserviceaccount.com"
  for runner_role in roles/bigquery.jobUser roles/aiplatform.user roles/datastore.user; do
    gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
      --member="serviceAccount:${runner_sa}" \
      --role="${runner_role}" \
      --all \
      --quiet >/dev/null 2>&1 || true
  done
  if gcloud iam service-accounts describe "${runner_sa}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts delete "${runner_sa}" --project="${PROJECT_ID}" --quiet >/dev/null
    echo "Deleted Cloud Run runtime SA: ${runner_sa}"
  fi
fi

if [[ "${DELETE_POLL_DB}" -eq 1 ]]; then
  if gcloud firestore databases describe --database="${FIRESTORE_DATABASE_ID}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud firestore databases delete --database="${FIRESTORE_DATABASE_ID}" --project="${PROJECT_ID}" --quiet >/dev/null
    echo "Deleted Firestore poll database: ${FIRESTORE_DATABASE_ID}"
  fi
fi
