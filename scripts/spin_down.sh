#!/usr/bin/env bash
set -euo pipefail

# One-command full GCP spin-down: forwards to teardown_pack.sh --all.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  echo "Usage: $0 [--dry-run] [--yes] [--pack PACK_ID] [--service-name NAME] [--region REGION]"
  exit 0
fi

HAS_DRY_RUN=0
HAS_PROJECT_ARG=0
for arg in "$@"; do
  if [[ "${arg}" == "--dry-run" ]]; then
    HAS_DRY_RUN=1
  elif [[ "${arg}" == "--project" || "${arg}" == --project=* ]]; then
    HAS_PROJECT_ARG=1
  fi
done

if [[ "${HAS_DRY_RUN}" -eq 1 && "${HAS_PROJECT_ARG}" -eq 0 ]]; then
  if [[ -z "${PROJECT_ID:-}" || "${PROJECT_ID:-}" == "example-project-id" ]]; then
    if [[ ! -f "${REPO_ROOT}/.env" ]] || ! grep -q '^PROJECT_ID=' "${REPO_ROOT}/.env"; then
      export PROJECT_ID="example-dryrun-project"
    fi
  fi
fi

exec bash "${SCRIPT_DIR}/teardown_pack.sh" --all "$@"
