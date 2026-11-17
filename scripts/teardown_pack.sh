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
BQ_LOCATION="${BQ_LOCATION:-asia-southeast1}"
DRY_RUN=0
CONFIRM_YES=0

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
    --help|-h)
      echo "Usage: $0 [--dry-run] [--yes]"
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

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[DRY-RUN] Would delete BigQuery dataset ${PROJECT_ID}.${DATASET_ID} (location=${BQ_LOCATION}) and all its contents."
  exit 0
fi

if [[ "${CONFIRM_YES}" -ne 1 ]]; then
  echo "ERROR: Refusing destructive teardown without --yes (or pass --dry-run)." >&2
  exit 1
fi

export PROJECT_ID DATASET_ID BQ_LOCATION
uv run --project "${REPO_ROOT}" python - <<'PY'
import os
from google.cloud import bigquery

project_id = os.environ["PROJECT_ID"]
dataset_id = os.environ["DATASET_ID"]
bq_location = os.environ["BQ_LOCATION"]

client = bigquery.Client(project=project_id, location=bq_location)
client.delete_dataset(f"{project_id}.{dataset_id}", delete_contents=True, not_found_ok=True)
print(f"Deleted dataset (if existed): {dataset_id}")
PY
