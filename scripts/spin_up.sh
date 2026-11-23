#!/usr/bin/env bash
set -euo pipefail

# One-command full GCP spin-up:
#   1. BigQuery dataset, tables, 190 shadow clones, RLS & Property Graph (provision_pack.sh)
#   2. Blind dataset, Knowledge Catalog Glossary/Aspects/Scans/Data Product & AI.GENERATE (provision_context_layer.py)
#   3. Cloud Run Stage/Workbench/Poll service deployment (deploy_cloud_run.sh)

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

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

DRY_RUN=0
PACK_ID="${PACK_ID:-meridian_q3_sgd}"
PROJECT_ARG=""
REGION_ARG=""
ENABLE_SHARE_TOKEN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --pack)
      PACK_ID="${2:?--pack requires an argument}"
      shift 2
      ;;
    --project)
      PROJECT_ARG="${2:?--project requires an argument}"
      shift 2
      ;;
    --region)
      REGION_ARG="${2:?--region requires an argument}"
      shift 2
      ;;
    --enable-share-token)
      ENABLE_SHARE_TOKEN=1
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [--pack PACK_ID] [--project PROJECT_ID] [--region REGION] [--enable-share-token]"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "${PROJECT_ARG}" ]]; then
  export PROJECT_ID="${PROJECT_ARG}"
fi
if [[ -n "${REGION_ARG}" ]]; then
  export BQ_LOCATION="${REGION_ARG}"
  export CLOUD_RUN_REGION="${REGION_ARG}"
fi

PROV_ARGS=(--provision-rls-sas --pack "${PACK_ID}")
CTX_ARGS=(--pack "${PACK_ID}")
DEPLOY_ARGS=(--pack "${PACK_ID}")

if [[ -n "${PROJECT_ARG}" ]]; then
  PROV_ARGS+=(--project "${PROJECT_ARG}")
  DEPLOY_ARGS+=(--project "${PROJECT_ARG}")
fi
if [[ -n "${REGION_ARG}" ]]; then
  PROV_ARGS+=(--region "${REGION_ARG}")
  DEPLOY_ARGS+=(--region "${REGION_ARG}")
fi
if [[ "${ENABLE_SHARE_TOKEN}" -eq 1 ]]; then
  DEPLOY_ARGS+=(--enable-share-token)
fi
if [[ "${DRY_RUN}" -eq 1 ]]; then
  PROV_ARGS+=(--dry-run)
  CTX_ARGS+=(--dry-run)
  DEPLOY_ARGS+=(--dry-run)
else
  CTX_ARGS+=(--live-gcp)
fi

echo "==> [1/3] Provisioning ScenarioPack BigQuery tables, RLS, and Property Graph..."
bash "${SCRIPT_DIR}/provision_pack.sh" "${PROV_ARGS[@]}"

echo "==> [2/3] Provisioning Blind dataset, Knowledge Catalog, and Object Table extraction..."
if command -v uv >/dev/null 2>&1; then
  uv run --project "${REPO_ROOT}" python "${SCRIPT_DIR}/provision_context_layer.py" "${CTX_ARGS[@]}"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  "${REPO_ROOT}/.venv/bin/python" "${SCRIPT_DIR}/provision_context_layer.py" "${CTX_ARGS[@]}"
else
  echo "ERROR: Neither uv nor ${REPO_ROOT}/.venv/bin/python was found." >&2
  exit 1
fi

echo "==> [3/3] Deploying Cloud Run app & Firestore Poll database..."
bash "${SCRIPT_DIR}/deploy_cloud_run.sh" "${DEPLOY_ARGS[@]}"
