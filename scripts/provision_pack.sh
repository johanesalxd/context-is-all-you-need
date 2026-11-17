#!/usr/bin/env bash
set -euo pipefail

# Provision BigQuery dataset, tables, seeded JSONL rows, 190 shadow tables,
# Row-Level Security policies, and Property Graph for a ScenarioPack.

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
DATASET_ID="${DATASET_ID:-}"
PACK_ID="${PACK_ID:-}"

if [[ $# -ge 1 && -n "${1:-}" && "${1:-}" != --* ]]; then
  PACK_ID="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pack)
      PACK_ID="${2:?--pack requires an argument}"
      shift 2
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "example-project-id" ]]; then
  echo "ERROR: PROJECT_ID must be set to a real sandbox GCP project (not example-project-id)." >&2
  exit 1
fi
if [[ -z "${DATASET_ID}" ]]; then
  echo "ERROR: DATASET_ID must not be empty." >&2
  exit 1
fi
if [[ -z "${PACK_ID}" ]]; then
  echo "ERROR: PACK_ID must not be empty." >&2
  exit 1
fi

PACK_DIR="${REPO_ROOT}/packs/${PACK_ID}"
if [[ ! -d "${PACK_DIR}" ]]; then
  echo "ERROR: ScenarioPack directory not found: ${PACK_DIR}" >&2
  exit 1
fi

SEED_SCRIPT=""
for candidate in "${PACK_DIR}"/seed*.py; do
  if [[ -f "${candidate}" ]]; then
    SEED_SCRIPT="${candidate}"
    break
  fi
done
if [[ -z "${SEED_SCRIPT}" ]]; then
  echo "ERROR: No seed*.py script found in ${PACK_DIR}" >&2
  exit 1
fi

ACTIVE_GCLOUD_ACCOUNT="$(
  gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null \
    | grep -v '^Created ' \
    | grep '@' \
    | tail -n 1 \
    | tr -d '[:space:]' || true
)"

resolve_rls_principals() {
  if [[ -n "${SQL_ROLE_SA_MAP_JSON:-}" ]]; then
    eval "$(
      uv run --project "${REPO_ROOT}" python - <<'PY'
import os, shlex
from engine.rls_impersonation import parse_role_sa_map
data = parse_role_sa_map(os.environ["SQL_ROLE_SA_MAP_JSON"])
vals = list(data.values())
cfo = next((v for k, v in data.items() if "cfo" in k.lower() or "all" in k.lower()), vals[0])
sg = next((v for k, v in data.items() if v != cfo), vals[-1])
print(f"export RLS_CFO_PRINCIPAL={shlex.quote('serviceAccount:' + cfo)}")
print(f"export RLS_SG_PRINCIPAL={shlex.quote('serviceAccount:' + sg)}")
PY
    )"
    return 0
  fi

  if [[ -n "${RLS_CFO_PRINCIPAL:-}" && -n "${RLS_SG_PRINCIPAL:-}" ]]; then
    return 0
  fi

  if [[ -z "${ACTIVE_GCLOUD_ACCOUNT}" ]]; then
    echo "ERROR: Could not determine active gcloud account and SQL_ROLE_SA_MAP_JSON is unset." >&2
    exit 1
  fi

  export RLS_CFO_PRINCIPAL="${RLS_CFO_PRINCIPAL:-user:${ACTIVE_GCLOUD_ACCOUNT}}"

  if [[ -z "${RLS_SG_PRINCIPAL:-}" ]]; then
    local candidate_sa="sg-coldchain@${PROJECT_ID}.iam.gserviceaccount.com"
    if gcloud iam service-accounts describe "${candidate_sa}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
      export RLS_SG_PRINCIPAL="serviceAccount:${candidate_sa}"
    elif gcloud iam service-accounts create "sg-coldchain" \
      --project="${PROJECT_ID}" \
      --display-name="SG Cold-Chain RLS Persona" >/dev/null 2>&1; then
      export RLS_SG_PRINCIPAL="serviceAccount:${candidate_sa}"
    else
      local existing_sa
      existing_sa="$(
        gcloud iam service-accounts list --project="${PROJECT_ID}" --format='value(email)' 2>/dev/null \
          | grep -v '^Created ' \
          | grep '@' \
          | head -n 1 \
          | tr -d '[:space:]' || true
      )"
      if [[ -n "${existing_sa}" ]]; then
        export RLS_SG_PRINCIPAL="serviceAccount:${existing_sa}"
      else
        echo "WARN: Could not create or list a secondary service account; falling back to active user." >&2
        export RLS_SG_PRINCIPAL="user:${ACTIVE_GCLOUD_ACCOUNT}"
      fi
    fi
  fi
}

resolve_rls_principals

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "Generating deterministic JSONL fixtures via ${SEED_SCRIPT##*/}..."
uv run --project "${REPO_ROOT}" python "${SEED_SCRIPT}" --output-dir "${TMP_DIR}"

export REPO_ROOT PACK_DIR TMP_DIR PROJECT_ID DATASET_ID BQ_LOCATION

uv run --project "${REPO_ROOT}" python - <<'PY'
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from pathlib import Path
import re
from google.cloud import bigquery

project_id = os.environ["PROJECT_ID"]
dataset_id = os.environ["DATASET_ID"]
bq_location = os.environ["BQ_LOCATION"]
pack_dir = Path(os.environ["PACK_DIR"])
tmp_dir = Path(os.environ["TMP_DIR"])
rls_cfo = os.environ.get("RLS_CFO_PRINCIPAL", "")
rls_sg = os.environ.get("RLS_SG_PRINCIPAL", "")

client = bigquery.Client(project=project_id, location=bq_location)

dataset_ref = bigquery.Dataset(f"{project_id}.{dataset_id}")
dataset_ref.location = bq_location
client.create_dataset(dataset_ref, exists_ok=True)
print(f"Dataset ready: {dataset_id} ({bq_location})")


def substitute_sql(raw: str) -> str:
    return (
        raw.replace("${PROJECT_ID}", project_id)
        .replace("${DATASET_ID}", dataset_id)
        .replace("${BQ_LOCATION}", bq_location)
        .replace("${RLS_CFO_PRINCIPAL}", rls_cfo)
        .replace("${RLS_SG_PRINCIPAL}", rls_sg)
    )


def run_sql_file(sql_path: Path, *, staging_only: bool = False) -> None:
    if not sql_path.is_file():
        return
    sql_text = substitute_sql(sql_path.read_text(encoding="utf-8")).strip()
    if not sql_text:
        return
    if staging_only:
        match = re.search(
            r"CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[^;]*?staging_cold_chain_oct11[^;]*;",
            sql_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return
        sql_text = match.group(0)
    job_cfg = bigquery.QueryJobConfig(
        use_query_cache=False,
        default_dataset=f"{project_id}.{dataset_id}",
    )
    client.query(sql_text, job_config=job_cfg, location=bq_location).result()
    print(f"Executed SQL: {sql_path.relative_to(pack_dir)}")


# 1. Create core tables (and contract overlay DDL + staging table DDL if separate) BEFORE loading JSONL.
run_sql_file(pack_dir / "sql" / "01_tables.sql")
for contract_sql in sorted((pack_dir / "contracts").glob("*.sql")) if (pack_dir / "contracts").is_dir() else []:
    run_sql_file(contract_sql)
run_sql_file(pack_dir / "sql" / "02_shadow_clones.sql", staging_only=True)

# 2. Load generated JSONL fixtures concurrently into BigQuery tables.
jsonl_files = sorted(tmp_dir.glob("*.jsonl"))
if not jsonl_files:
    raise RuntimeError(f"No .jsonl files produced by seed script in {tmp_dir}")


def load_one_jsonl(jsonl_path: Path) -> str:
    table_name = jsonl_path.stem
    table_id = f"{project_id}.{dataset_id}.{table_name}"
    table_exists = True
    try:
        client.get_table(table_id)
    except Exception:
        table_exists = False

    job_cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        autodetect=not table_exists,
    )
    with jsonl_path.open("rb") as fh:
        job = client.load_table_from_file(fh, table_id, job_config=job_cfg, location=bq_location)
    job.result()
    return f"{table_name}:{job.output_rows}"


with ThreadPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(load_one_jsonl, jf) for jf in jsonl_files]
    loaded_summary = [fut.result() for fut in as_completed(futures)]
print("Loaded JSONL tables:", ", ".join(sorted(loaded_summary)))

# 3. Provision 190 empty shadow tables concurrently via BigQuery API (<10s).
shadow_schema = [
    bigquery.SchemaField("country_code", "STRING"),
    bigquery.SchemaField("quarter", "STRING"),
    bigquery.SchemaField("gross_margin_pct", "FLOAT64"),
    bigquery.SchemaField("snapshot_tag", "STRING"),
]
try:
    staging_tbl = client.get_table(f"{project_id}.{dataset_id}.staging_cold_chain_oct11")
    if staging_tbl.schema:
        shadow_schema = list(staging_tbl.schema)
except Exception:
    pass


def create_shadow(idx: int) -> None:
    tbl_name = f"shadow_auto_tbl_{idx:03d}"
    tbl = bigquery.Table(f"{project_id}.{dataset_id}.{tbl_name}", schema=shadow_schema)
    client.create_table(tbl, exists_ok=True)


with ThreadPoolExecutor(max_workers=20) as pool:
    futs = [pool.submit(create_shadow, i) for i in range(1, 191)]
    for fut in as_completed(futs):
        fut.result()
print("Provisioned 190 shadow tables (shadow_auto_tbl_001..shadow_auto_tbl_190)")

# 4. Apply Row-Level Security policies and Property Graph DDL.
run_sql_file(pack_dir / "sql" / "03_rls.sql")
run_sql_file(pack_dir / "sql" / "04_property_graph.sql")
print("Provisioning complete.")
PY
