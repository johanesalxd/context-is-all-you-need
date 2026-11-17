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
PACKS_DIR="${PACKS_DIR:-${REPO_ROOT}/packs}"
PROVISION_RLS_SAS="${PROVISION_RLS_SAS:-0}"

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
    --provision-rls-sas)
      PROVISION_RLS_SAS=1
      shift
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

PACK_DIR="${PACKS_DIR}/${PACK_ID}"
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

validate_rls_principals_py() {
  uv run --project "${REPO_ROOT}" python - <<'PY'
import os
import sys
from engine.rls_impersonation import is_valid_customer_sa

cfo = os.environ.get("RLS_CFO_PRINCIPAL", "").strip()
sg = os.environ.get("RLS_SG_PRINCIPAL", "").strip()
if not cfo or not sg:
    print("ERROR: RLS_CFO_PRINCIPAL and RLS_SG_PRINCIPAL must both be non-empty.", file=sys.stderr)
    sys.exit(1)
if cfo.lower() == sg.lower():
    print("ERROR: RLS_CFO_PRINCIPAL and RLS_SG_PRINCIPAL must be distinct principals.", file=sys.stderr)
    sys.exit(1)
for label, principal in (("RLS_CFO_PRINCIPAL", cfo), ("RLS_SG_PRINCIPAL", sg)):
    if principal.startswith("serviceAccount:"):
        email = principal.split(":", 1)[1].strip()
        if not is_valid_customer_sa(email):
            print(f"ERROR: {label} is not a valid customer-managed service account: {email}", file=sys.stderr)
            sys.exit(1)
PY
}

ensure_sa_exists() {
  local sa_name="$1"
  local display_name="$2"
  local sa_email="${sa_name}@${PROJECT_ID}.iam.gserviceaccount.com"
  uv run --project "${REPO_ROOT}" python - "${sa_email}" <<'PY'
import sys
from engine.rls_impersonation import is_valid_customer_sa

email = sys.argv[1]
if not is_valid_customer_sa(email):
    print(f"ERROR: Invalid customer-managed SA email: {email}", file=sys.stderr)
    sys.exit(1)
PY
  if ! gcloud iam service-accounts describe "${sa_email}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${sa_name}" \
      --project="${PROJECT_ID}" \
      --display-name="${display_name}" >/dev/null
  fi
}

resolve_rls_principals() {
  if [[ -n "${SQL_ROLE_SA_MAP_JSON:-}" ]]; then
    eval "$(
      uv run --project "${REPO_ROOT}" python - <<'PY'
import os, shlex, sys
from engine.rls_impersonation import parse_role_sa_map

data = parse_role_sa_map(os.environ["SQL_ROLE_SA_MAP_JSON"])
unique_vals = list(dict.fromkeys(data.values()))
if len(unique_vals) < 2:
    print(
        "ERROR: SQL_ROLE_SA_MAP_JSON must map at least 2 distinct customer service accounts for differential RLS.",
        file=sys.stderr,
    )
    sys.exit(1)
cfo = next(
    (v for k, v in data.items() if "cfo" in k.lower() or "all" in k.lower() or "regional" in k.lower()),
    unique_vals[0],
)
sg = next((v for v in unique_vals if v != cfo), unique_vals[-1])
print(f"export RLS_CFO_PRINCIPAL={shlex.quote('serviceAccount:' + cfo)}")
print(f"export RLS_SG_PRINCIPAL={shlex.quote('serviceAccount:' + sg)}")
PY
    )"
    validate_rls_principals_py
    return 0
  fi

  if [[ -n "${RLS_CFO_PRINCIPAL:-}" && -n "${RLS_SG_PRINCIPAL:-}" ]]; then
    validate_rls_principals_py
    return 0
  fi

  if [[ "${PROVISION_RLS_SAS}" == "1" ]]; then
    if [[ -z "${RLS_CFO_PRINCIPAL:-}" ]]; then
      ensure_sa_exists "rls-cfo-regional" "CFO Regional RLS Persona"
      export RLS_CFO_PRINCIPAL="serviceAccount:rls-cfo-regional@${PROJECT_ID}.iam.gserviceaccount.com"
    fi
    if [[ -z "${RLS_SG_PRINCIPAL:-}" ]]; then
      ensure_sa_exists "sg-coldchain" "SG Cold-Chain RLS Persona"
      export RLS_SG_PRINCIPAL="serviceAccount:sg-coldchain@${PROJECT_ID}.iam.gserviceaccount.com"
    fi
    validate_rls_principals_py
    return 0
  fi

  if [[ -z "${ACTIVE_GCLOUD_ACCOUNT}" && -z "${RLS_CFO_PRINCIPAL:-}" ]]; then
    echo "ERROR: Could not determine active gcloud account and SQL_ROLE_SA_MAP_JSON / RLS_CFO_PRINCIPAL is unset." >&2
    exit 1
  fi

  export RLS_CFO_PRINCIPAL="${RLS_CFO_PRINCIPAL:-user:${ACTIVE_GCLOUD_ACCOUNT}}"

  if [[ -z "${RLS_SG_PRINCIPAL:-}" ]]; then
    local policy_json
    policy_json="$(gcloud projects get-iam-policy "${PROJECT_ID}" --format=json 2>/dev/null || true)"
    if [[ -n "${policy_json}" ]]; then
      export _IAM_POLICY_JSON="${policy_json}"
      export PROJECT_ID
      local picked_sa
      picked_sa="$(
        uv run --project "${REPO_ROOT}" python - <<'PY'
import json, os, sys
from engine.rls_impersonation import is_valid_customer_sa

raw = os.environ.get("_IAM_POLICY_JSON", "")
idx = raw.find("{")
if idx < 0:
    sys.exit(0)
policy = json.loads(raw[idx:])
project_id = os.environ.get("PROJECT_ID", "").strip()
cfo = os.environ.get("RLS_CFO_PRINCIPAL", "").strip().lower()

job_roles = {"roles/bigquery.jobUser", "roles/bigquery.user", "roles/bigquery.admin"}
data_roles = {
    "roles/bigquery.dataViewer",
    "roles/bigquery.dataEditor",
    "roles/bigquery.dataOwner",
    "roles/bigquery.admin",
}
overbroad_roles = {"roles/owner", "roles/editor", "roles/bigquery.admin"}

sa_roles: dict[str, set[str]] = {}
for binding in policy.get("bindings", []):
    role = str(binding.get("role", ""))
    for member in binding.get("members", []):
        if isinstance(member, str) and member.startswith("serviceAccount:"):
            email = member.split(":", 1)[1].strip()
            if is_valid_customer_sa(email) and f"serviceaccount:{email.lower()}" != cfo:
                sa_roles.setdefault(email, set()).add(role)

job_capable = [
    (bool(roles & overbroad_roles), not bool(roles & data_roles), email, bool(roles & data_roles))
    for email, roles in sa_roles.items()
    if (roles & job_roles)
]
if not job_capable:
    sys.exit(0)


def can_impersonate(sa_email: str) -> bool:
    if not project_id:
        return False
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = AuthorizedSession(creds)
        url = (
            f"https://iam.googleapis.com/v1/projects/{project_id}"
            f"/serviceAccounts/{sa_email}:testIamPermissions"
        )
        resp = session.post(
            url,
            json={"permissions": ["iam.serviceAccounts.getAccessToken"]},
            timeout=2.0,
        )
        if resp.status_code == 200:
            perms = resp.json().get("permissions") or []
            return "iam.serviceAccounts.getAccessToken" in perms
    except Exception:
        pass
    return False


data_only = [email for _, _, email, has_data in job_capable if has_data]
if len(job_capable) == 1 and len(data_only) == 1:
    print(data_only[0])
else:
    scored = []
    for overbroad, missing_proj_data, email, has_data in job_capable:
        impersonatable = can_impersonate(email)
        # Accept SAs with project-level data role, OR job-capable SAs explicitly grantable via TokenCreator
        # (which may hold dataset-scoped BigQuery dataViewer/dataEditor bindings).
        if has_data or impersonatable:
            scored.append((not impersonatable, missing_proj_data, overbroad, email))
    scored.sort()
    if scored:
        print(scored[0][3])
PY
      )"
      unset _IAM_POLICY_JSON
      if [[ -n "${picked_sa}" ]]; then
        export RLS_SG_PRINCIPAL="serviceAccount:${picked_sa}"
      fi
    fi
  fi

  if [[ -z "${RLS_SG_PRINCIPAL:-}" ]]; then
    echo "ERROR: Could not resolve a distinct least-privileged customer SA for RLS_SG_PRINCIPAL." >&2
    echo "Provide SQL_ROLE_SA_MAP_JSON, explicit distinct RLS_CFO_PRINCIPAL/RLS_SG_PRINCIPAL, or pass --provision-rls-sas." >&2
    exit 1
  fi

  validate_rls_principals_py
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
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from engine.capture_rungs import list_active_row_access_policies
from engine.pack_loader import _strip_sql_comments, extract_create_table_statement

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


def run_ddl_sql(sql_text: str) -> None:
    job_cfg = bigquery.QueryJobConfig(
        use_query_cache=False,
        default_dataset=f"{project_id}.{dataset_id}",
    )
    client.query(sql_text, job_config=job_cfg, location=bq_location).result()


def run_sql_file(sql_path: Path, *, staging_only: bool = False) -> None:
    if not sql_path.is_file():
        return
    sql_text = substitute_sql(sql_path.read_text(encoding="utf-8")).strip()
    if not sql_text:
        return
    if staging_only:
        extracted = extract_create_table_statement(sql_text, "staging_cold_chain_oct11")
        if not extracted:
            return
        sql_text = extracted
    run_ddl_sql(sql_text)
    print(f"Executed SQL: {sql_path.relative_to(pack_dir)}")


def extract_declared_targets(sql_path: Path, pattern: str) -> list[str]:
    if not sql_path.is_file():
        return []
    sql_text = substitute_sql(sql_path.read_text(encoding="utf-8"))
    regex = re.compile(pattern, flags=re.IGNORECASE)
    found: list[str] = []
    for stmt in _strip_sql_comments(sql_text):
        match = regex.match(stmt)
        if match:
            found.append(match.group(1).strip().strip('`"'))
    return found


def reset_existing_objects_for_idempotency() -> None:
    existing_types = {t.table_id: t.table_type for t in client.list_tables(f"{project_id}.{dataset_id}")}
    if not existing_types:
        return

    graph_sql_path = pack_dir / "sql" / "04_property_graph.sql"
    for graph_ident in extract_declared_targets(
        graph_sql_path,
        r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?PROPERTY\s+GRAPH\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(;]+)",
    ):
        leaf = graph_ident.split(".")[-1]
        run_ddl_sql(f"DROP PROPERTY GRAPH IF EXISTS `{project_id}.{dataset_id}.{leaf}`;")

    for tbl_name, tbl_type in sorted(existing_types.items()):
        if tbl_type != "TABLE" or tbl_name.startswith("shadow_auto_tbl_"):
            continue
        if list_active_row_access_policies(
            client,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=tbl_name,
            location=bq_location,
        ):
            run_ddl_sql(f"DROP ALL ROW ACCESS POLICIES ON `{project_id}.{dataset_id}.{tbl_name}`;")

    contract_files = sorted((pack_dir / "contracts").glob("*.sql")) if (pack_dir / "contracts").is_dir() else []
    ddl_files = [pack_dir / "sql" / "01_tables.sql", *contract_files]
    declared_tables: list[str] = []
    for path in ddl_files:
        for ident in extract_declared_targets(
            path,
            r"^\s*CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([^\s(;]+)",
        ):
            leaf = ident.split(".")[-1]
            if leaf not in declared_tables:
                declared_tables.append(leaf)

    # Drop in reverse declaration order so FK child tables are dropped before parents.
    for tbl_name in reversed(declared_tables):
        if existing_types.get(tbl_name) == "TABLE":
            run_ddl_sql(f"DROP TABLE IF EXISTS `{project_id}.{dataset_id}.{tbl_name}`;")


reset_existing_objects_for_idempotency()

# 1. Create core tables (and contract overlay DDL + staging table DDL if separate) BEFORE loading JSONL.
run_sql_file(pack_dir / "sql" / "01_tables.sql")
for contract_sql in sorted((pack_dir / "contracts").glob("*.sql")) if (pack_dir / "contracts").is_dir() else []:
    run_sql_file(contract_sql)
run_sql_file(pack_dir / "sql" / "02_shadow_clones.sql", staging_only=True)

# 2. Load generated JSONL fixtures concurrently into BigQuery tables while preserving DDL constraints/descriptions.
jsonl_files = sorted(tmp_dir.glob("*.jsonl"))
if not jsonl_files:
    raise RuntimeError(f"No .jsonl files produced by seed script in {tmp_dir}")


def load_one_jsonl(jsonl_path: Path) -> str:
    table_name = jsonl_path.stem
    table_id = f"{project_id}.{dataset_id}.{table_name}"
    existing_tbl = None
    try:
        existing_tbl = client.get_table(table_id)
    except NotFound:
        existing_tbl = None

    if existing_tbl is not None:
        if existing_tbl.num_rows and existing_tbl.num_rows > 0:
            run_ddl_sql(f"TRUNCATE TABLE `{table_id}`")
        job_cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema=existing_tbl.schema,
            autodetect=False,
        )
    else:
        job_cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            autodetect=True,
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
    bigquery.SchemaField("record_id", "STRING"),
    bigquery.SchemaField("country_code", "STRING"),
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
