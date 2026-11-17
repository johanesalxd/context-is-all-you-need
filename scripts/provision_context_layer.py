#!/usr/bin/env python3
"""Idempotent Phase 2 GCP Governance & Knowledge Catalog provisioner / teardown."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

# Preserve Cloudtop Context-Aware Access mTLS vars while clearing hijacking vars BEFORE SDK imports.
_HIJACKING_ENV_VARS = (
    "CLOUDSDK_ACTIVE_CONFIG_NAME",
    "CLOUDSDK_AUTH_ACCESS_TOKEN",
    "CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE",
    "CLOUDSDK_CORE_PROJECT",
    "CLOUDSDK_CORE_ACCOUNT",
    "CLOUDSDK_BILLING_QUOTA_PROJECT",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "BIGQUERYRC",
)
for _var in _HIJACKING_ENV_VARS:
    os.environ.pop(_var, None)

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.capture_rungs import list_active_row_access_policies
from engine.pack_loader import (
    discover_rls_target,
    load_context_layer,
    load_dotenv_if_present,
    resolve_phase2_settings,
    substitute_placeholders,
)
from engine.rls_impersonation import redact_bundle_data, resolve_agent_sa_map

_DATAPLEX_BASE = "https://dataplex.googleapis.com/v1"
_BQ_CONN_BASE = "https://bigqueryconnection.googleapis.com/v1"
_LEGACY_LEAK_COL_TOKENS = ("rebate_settled", "certified_at", "yoy_delta_bps")
_LEGACY_LEAK_TBL_TOKENS = ("_gold", "staging_", "sla_overlay")


def _run_cmd(cmd: Sequence[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    for var in _HIJACKING_ENV_VARS:
        env.pop(var, None)
    return subprocess.run(
        list(cmd),
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=check,
    )


def _strip_mtls_preamble(raw: str) -> str:
    lines = [
        line.strip()
        for line in (raw or "").splitlines()
        if line.strip() and not line.strip().startswith("Created ")
    ]
    return lines[-1] if lines else ""


def _resolve_active_gcloud_account() -> str:
    proc = _run_cmd(
        ["gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"],
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return _strip_mtls_preamble(proc.stdout)


def _resolve_project_number(project_id: str) -> str:
    proc = _run_cmd(
        ["gcloud", "projects", "describe", project_id, "--format=value(projectNumber)"],
        check=False,
    )
    val = _strip_mtls_preamble(proc.stdout) if proc.returncode == 0 else ""
    if val and val.isdigit():
        return val
    raise RuntimeError(f"Could not resolve numeric projectNumber for {project_id!r}: {proc.stderr.strip()}")


def _get_bearer_token() -> str:
    try:
        import google.auth
        from google.auth.transport.requests import Request as GoogleAuthRequest

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(GoogleAuthRequest())
        tok = str(getattr(creds, "token", "") or "").strip()
        if tok:
            return tok
    except Exception:
        pass
    proc = _run_cmd(["gcloud", "auth", "print-access-token"], check=True)
    tok = _strip_mtls_preamble(proc.stdout)
    if not tok:
        raise RuntimeError("Failed to obtain GCP OAuth access token.")
    return tok


class _RestClient:
    """Tiny idempotent REST helper with LRO polling over stdlib urllib."""

    def __init__(
        self,
        *,
        token_provider: Callable[[], str] | None = None,
        transport: Callable[[str, str, dict[str, Any] | None], tuple[int, dict[str, Any]]] | None = None,
    ) -> None:
        self._token_provider = token_provider or _get_bearer_token
        self._transport = transport

    def request(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
        allow_statuses: Sequence[int] = (200, 201),
    ) -> tuple[int, dict[str, Any]]:
        if self._transport is not None:
            status, body = self._transport(method, url, payload)
            if status not in allow_statuses:
                raise RuntimeError(f"HTTP {status} for {method} {url}: {json.dumps(body)[:400]}")
            return status, body

        token = self._token_provider()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
            data = json.dumps(payload).encode("utf-8")

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=30.0) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw.strip() else {}
                if resp.status not in allow_statuses:
                    raise RuntimeError(f"HTTP {resp.status} for {method} {url}: {raw[:400]}")
                return resp.status, parsed
        except HTTPError as err:
            raw_err = err.read().decode("utf-8", errors="replace") if err.fp else ""
            try:
                parsed_err = json.loads(raw_err) if raw_err.strip() else {"message": raw_err}
            except json.JSONDecodeError:
                parsed_err = {"message": raw_err}
            if err.code in allow_statuses:
                return err.code, parsed_err
            raise RuntimeError(f"HTTP {err.code} for {method} {url}: {raw_err[:500]}") from err
        except URLError as err:
            raise RuntimeError(f"Network error for {method} {url}: {err}") from err

    def wait_lro(self, op_or_resource: dict[str, Any], *, timeout_s: float = 120.0) -> dict[str, Any]:
        if "done" not in op_or_resource or not isinstance(op_or_resource.get("name"), str):
            return op_or_resource
        if op_or_resource.get("done"):
            if op_or_resource.get("error"):
                raise RuntimeError(f"GCP LRO failed: {op_or_resource['error']}")
            return dict(op_or_resource.get("response") or op_or_resource)
        op_name = op_or_resource["name"].lstrip("/")
        op_url = f"{_DATAPLEX_BASE}/{op_name}"
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(2.0)
            _, latest = self.request("GET", op_url, allow_statuses=(200,))
            if latest.get("done"):
                if latest.get("error"):
                    raise RuntimeError(f"GCP LRO failed ({op_name}): {latest['error']}")
                return dict(latest.get("response") or latest)
        raise TimeoutError(f"Timed out waiting for LRO {op_name}")


def _sa_exists(sa_email: str) -> bool:
    proc = _run_cmd(["gcloud", "iam", "service-accounts", "describe", sa_email], check=False)
    return proc.returncode == 0


def _ensure_sa_exists(sa_email: str, *, project_id: str, display_name: str) -> None:
    if _sa_exists(sa_email):
        return
    sa_id = sa_email.split("@", 1)[0]
    _run_cmd(
        [
            "gcloud",
            "iam",
            "service-accounts",
            "create",
            sa_id,
            f"--project={project_id}",
            f"--display-name={display_name}",
        ],
        check=True,
    )


def _bind_project_role(project_id: str, member: str, role: str) -> None:
    for attempt in range(2):
        proc = _run_cmd(
            [
                "gcloud",
                "projects",
                "add-iam-policy-binding",
                project_id,
                f"--member={member}",
                f"--role={role}",
                "--condition=None",
                "--quiet",
            ],
            check=False,
        )
        if proc.returncode == 0:
            return
        if attempt == 0:
            time.sleep(3)
        else:
            raise RuntimeError(f"Failed binding {role} to {member}: {proc.stderr.strip()}")


def _bind_sa_token_creator(project_id: str, target_sa: str, member: str) -> None:
    for attempt in range(2):
        proc = _run_cmd(
            [
                "gcloud",
                "iam",
                "service-accounts",
                "add-iam-policy-binding",
                target_sa,
                f"--project={project_id}",
                f"--member={member}",
                "--role=roles/iam.serviceAccountTokenCreator",
                "--condition=None",
                "--quiet",
            ],
            check=False,
        )
        if proc.returncode == 0:
            return
        if attempt == 0:
            time.sleep(3)
        else:
            raise RuntimeError(f"Failed TokenCreator on {target_sa} for {member}: {proc.stderr.strip()}")


def resolve_provision_plan(
    *,
    pack_id: str,
    repo_root: Path | None = None,
    packs_dir: Path | None = None,
    allow_missing_context_layer: bool = False,
) -> dict[str, Any]:
    """Builds the 100% pack-driven Phase 2 governance provisioning plan without network calls."""
    root = (repo_root or REPO_ROOT).resolve()
    load_dotenv_if_present(root)
    settings = resolve_phase2_settings(root, pack_id=pack_id)
    project_id = settings["PROJECT_ID"]
    dataset_id = settings["DATASET_ID"]
    blind_dataset_id = settings["BLIND_DATASET_ID"]
    bq_location = settings["BQ_LOCATION"]
    connection_id = settings["BQ_CONNECTION_ID"]
    model_id = settings["AGENT_MODEL_ID"]
    model_location = settings["AGENT_MODEL_LOCATION"]

    try:
        ctx = load_context_layer(
            pack_id,
            packs_dir=packs_dir,
            project_id=project_id,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
    except FileNotFoundError:
        if not allow_missing_context_layer:
            raise
        ctx = {}
    ctx = substitute_placeholders(
        ctx,
        project_id=project_id,
        dataset_id=dataset_id,
        bq_location=bq_location,
        extra={
            "BLIND_DATASET_ID": blind_dataset_id,
            "BQ_CONNECTION_ID": connection_id,
        },
    )
    agent_sas = resolve_agent_sa_map(
        project_id=project_id,
        pack_id=pack_id,
        context_layer=ctx,
    )
    prefix = re.sub(r"[^a-z0-9-]", "-", (pack_id.split("_")[0] if pack_id else "agent").lower()).strip("-")[:15]
    web_runner_sa = str(
        ctx.get("web_runner_sa") or f"{prefix}-web-runner@{project_id}.iam.gserviceaccount.com"
    ).strip()

    rls_table, rls_cfo_policy = discover_rls_target(pack_id, packs_dir=packs_dir)
    unstructured = dict(ctx.get("unstructured_contracts") or {})
    bucket_suffix = str(unstructured.get("bucket_suffix") or f"{prefix}-contracts").strip()
    bucket_name = f"{project_id}-{bucket_suffix}"

    shadow_count = int(ctx.get("shadow_table_count") or 190)
    shadow_prefix = str(ctx.get("shadow_table_prefix") or "shadow_auto_tbl_").strip()
    blind_tables = [str(t).strip() for t in (ctx.get("blind_dataset_tables") or []) if str(t).strip()]
    shadow_source = str(ctx.get("shadow_source_table") or "").strip()
    if not shadow_source:
        shadow_source = next(
            (t for t in blind_tables if "r1" in t.lower() or "staging" in t.lower()),
            blind_tables[0] if blind_tables else "",
        )

    return {
        "pack_id": pack_id,
        "project_id": project_id,
        "dataset_id": dataset_id,
        "blind_dataset_id": blind_dataset_id,
        "bq_location": bq_location,
        "connection_id": connection_id,
        "model_id": model_id,
        "model_location": model_location,
        "blind_agent_sa": agent_sas["blind"],
        "governed_agent_sa": agent_sas["governed"],
        "web_runner_sa": web_runner_sa,
        "rls_table": rls_table,
        "rls_cfo_policy": rls_cfo_policy,
        "legacy_tables_to_drop": [str(t).strip() for t in (ctx.get("legacy_tables_to_drop") or []) if str(t).strip()],
        "blind_dataset_tables": blind_tables,
        "shadow_source_table": shadow_source,
        "shadow_table_prefix": shadow_prefix,
        "shadow_table_count": shadow_count,
        "glossary": ctx.get("glossary") or {},
        "aspect_types": list(ctx.get("aspect_types") or []),
        "data_quality_scans": list(ctx.get("data_quality_scans") or []),
        "unstructured_contracts": unstructured,
        "bucket_name": bucket_name,
    }


def _reconcile_dataset_acls(
    bq_client: Any,
    *,
    project_id: str,
    dataset_id: str,
    grant_reader_sas: Sequence[str],
    scrub_sas: Sequence[str],
) -> None:
    from google.cloud import bigquery

    ds = bq_client.get_dataset(f"{project_id}.{dataset_id}")
    scrub_set = {sa.lower() for sa in scrub_sas if sa}
    scrub_set |= {f"serviceaccount:{sa.lower()}" for sa in scrub_sas if sa}

    before_sig = [(e.role, e.entity_type, (e.entity_id or "").lower()) for e in ds.access_entries]
    updated = [e for e in ds.access_entries if (e.entity_id or "").lower() not in scrub_set]

    for grant_sa in grant_reader_sas:
        if not grant_sa:
            continue
        targets = {grant_sa.lower(), f"serviceaccount:{grant_sa.lower()}"}
        already = any(
            e.role in {"READER", "roles/bigquery.dataViewer"} and (e.entity_id or "").lower() in targets
            for e in updated
        )
        if not already:
            updated.append(bigquery.AccessEntry(role="READER", entity_type="userByEmail", entity_id=grant_sa))

    after_sig = [(e.role, e.entity_type, (e.entity_id or "").lower()) for e in updated]
    if after_sig != before_sig:
        ds.access_entries = updated
        bq_client.update_dataset(ds, ["access_entries"])


def _sync_rls_cfo_policy(
    bq_client: Any,
    *,
    project_id: str,
    dataset_id: str,
    bq_location: str,
    rls_table: str | None,
    rls_cfo_policy: str | None,
    caller_email: str,
    governed_sa: str,
    web_runner_sa: str | None,
) -> None:
    if not rls_table or not rls_cfo_policy:
        return

    grantees: list[str] = []
    if caller_email:
        if caller_email.endswith(".gserviceaccount.com"):
            grantees.append(f"serviceAccount:{caller_email}")
        else:
            grantees.append(f"user:{caller_email}")
    grantees.append(f"serviceAccount:{governed_sa}")
    if web_runner_sa:
        grantees.append(f"serviceAccount:{web_runner_sa}")

    # Preserve existing non-restricted CFO grantees already attached on the policy if any.
    for existing_pol in list_active_row_access_policies(
        bq_client,
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=rls_table,
        location=bq_location,
    ):
        pol_id = existing_pol.get("policy_id") if isinstance(existing_pol, Mapping) else getattr(existing_pol, "policy_id", "")
        pol_grantees = (
            existing_pol.get("grantees") if isinstance(existing_pol, Mapping) else getattr(existing_pol, "grantees", [])
        ) or []
        if pol_id == rls_cfo_policy:
            for g in pol_grantees:
                if g not in grantees and "coldchain" not in g.lower() and "denied" not in g.lower() and "blind-agent" not in g.lower():
                    grantees.append(g)

    grant_sql = ", ".join(f'"{g}"' for g in grantees)
    ddl = (
        f"CREATE OR REPLACE ROW ACCESS POLICY `{rls_cfo_policy}` "
        f"ON `{project_id}.{dataset_id}.{rls_table}` "
        f"GRANT TO ({grant_sql}) FILTER USING (TRUE);"
    )
    bq_client.query(ddl, location=bq_location).result()


def _assert_blind_zero_leak_and_parity(
    bq_client: Any,
    *,
    project_id: str,
    dataset_id: str,
    blind_dataset_id: str,
    bq_location: str,
    blind_tables: Sequence[str],
    rls_table: str | None,
) -> dict[str, int]:
    """Verifies physical table parity, RLS completeness (>=4 rows on RLS table), and zero giveaway leaks."""
    counts: dict[str, int] = {}
    for tbl in blind_tables:
        comm_rows = list(
            bq_client.query(
                f"SELECT COUNT(*) AS cnt FROM `{project_id}.{dataset_id}.{tbl}`",
                location=bq_location,
            ).result()
        )
        blind_rows = list(
            bq_client.query(
                f"SELECT COUNT(*) AS cnt FROM `{project_id}.{blind_dataset_id}.{tbl}`",
                location=bq_location,
            ).result()
        )
        comm_cnt = int(comm_rows[0]["cnt"])
        blind_cnt = int(blind_rows[0]["cnt"])
        if blind_cnt != comm_cnt or blind_cnt == 0:
            raise RuntimeError(
                f"Blind CTAS parity failed for {tbl}: {dataset_id}={comm_cnt} rows, "
                f"{blind_dataset_id}={blind_cnt} rows (possible RLS masking or empty seed)."
            )
        if rls_table and tbl == rls_table and blind_cnt < 4:
            raise RuntimeError(
                f"RLS table {tbl} expected >= 4 unmasked rows during CTAS, got {blind_cnt}."
            )
        counts[tbl] = blind_cnt

    for item in bq_client.list_tables(f"{project_id}.{blind_dataset_id}"):
        t_name = str(item.table_id)
        t_lower = t_name.lower()
        if getattr(item, "table_type", "TABLE") != "TABLE":
            raise RuntimeError(f"Blind dataset table {t_name!r} must be a physical TABLE, not {item.table_type!r}.")
        if any(bad in t_lower for bad in _LEGACY_LEAK_TBL_TOKENS):
            raise RuntimeError(f"Disallowed legacy/overlay table detected in {blind_dataset_id}: {t_name!r}")

        tbl_meta = bq_client.get_table(f"{project_id}.{blind_dataset_id}.{t_name}")
        if getattr(tbl_meta, "description", None):
            raise RuntimeError(f"Blind table {t_name!r} unexpectedly has a description.")
        tc = getattr(tbl_meta, "table_constraints", None)
        if tc and (getattr(tc, "primary_key", None) or getattr(tc, "foreign_keys", None)):
            raise RuntimeError(f"Blind table {t_name!r} unexpectedly has table constraints.")
        for field in getattr(tbl_meta, "schema", None) or []:
            f_lower = field.name.lower()
            if any(bad_col in f_lower for bad_col in _LEGACY_LEAK_COL_TOKENS):
                raise RuntimeError(
                    f"Disallowed giveaway column {field.name!r} leaked into {blind_dataset_id}.{t_name}!"
                )
            if getattr(field, "description", None):
                raise RuntimeError(f"Blind column {t_name}.{field.name} unexpectedly has a description.")

    return counts


def _strip_blind_table_metadata(bq_client: Any, *, table_id: str) -> None:
    from google.cloud import bigquery

    tbl = bq_client.get_table(table_id)
    changed = False
    if tbl.description:
        tbl.description = None
        changed = True
    new_schema = []
    for f in tbl.schema:
        if f.description:
            changed = True
        new_schema.append(
            bigquery.SchemaField(
                f.name,
                f.field_type,
                mode=f.mode,
                fields=f.fields,
            )
        )
    if changed:
        tbl.schema = new_schema
        bq_client.update_table(tbl, ["description", "schema"])


def _build_metadata_template(aspect_spec: Mapping[str, Any]) -> dict[str, Any]:
    fields = []
    for idx, field in enumerate(aspect_spec.get("fields") or [], start=1):
        ftype = str(field.get("type") or "string").lower()
        item: dict[str, Any] = {
            "index": int(field.get("index") or idx),
            "name": str(field["name"]),
            "type": ftype,
            "annotations": {"displayName": str(field.get("display_name") or field["name"])},
            "constraints": {"required": bool(field.get("required", False))},
        }
        if ftype == "enum" and field.get("enum_values"):
            item["enumValues"] = [
                {"index": e_idx, "name": str(val)}
                for e_idx, val in enumerate(field["enum_values"], start=1)
            ]
        fields.append(item)
    return {
        "name": str(aspect_spec["aspect_type_id"]),
        "type": "record",
        "recordFields": fields,
    }


def _poll_entry_exists(rest: _RestClient, *, project_id: str, bq_location: str, entry_name: str, timeout_s: float = 45.0) -> None:
    url = (
        f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}:lookupEntry"
        f"?entry={quote(entry_name, safe='/:@')}&view=BASIC"
    )
    deadline = time.monotonic() + timeout_s
    while True:
        status, _ = rest.request("GET", url, allow_statuses=(200, 404))
        if status == 200:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for projected Knowledge Catalog entry: {entry_name}")
        time.sleep(3.0)


def _create_or_update_entry_link(
    rest: _RestClient,
    *,
    project_id: str,
    bq_location: str,
    entry_link_id: str,
    bq_entry_name: str,
    linked_column: str,
    term_entry_name: str,
) -> None:
    parent = f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery"
    url = f"{_DATAPLEX_BASE}/{parent}/entryLinks?entryLinkId={quote(entry_link_id)}"
    link_type = "projects/dataplex-types/locations/global/entryLinkTypes/definition"

    primary_body = {
        "entryLinkType": link_type,
        "entryReferences": [
            {"name": bq_entry_name, "path": f"Schema.{linked_column}", "type": "SOURCE"},
            {"name": term_entry_name, "type": "TARGET"},
        ],
    }
    status, resp = rest.request("POST", url, payload=primary_body, allow_statuses=(200, 201, 400, 409))
    if status == 400:
        swapped_body = {
            "entryLinkType": link_type,
            "entryReferences": [
                {"name": bq_entry_name, "path": f"Schema.{linked_column}", "type": "TARGET"},
                {"name": term_entry_name, "type": "SOURCE"},
            ],
        }
        status2, resp2 = rest.request("POST", url, payload=swapped_body, allow_statuses=(200, 201, 409))
        if status2 == 409:
            return
        rest.wait_lro(resp2)
        return
    if status == 409:
        return
    rest.wait_lro(resp)


def run_provision(
    plan: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    packs_dir: Path | None = None,
    bq_client: Any = None,
    storage_client: Any = None,
    rest_client: _RestClient | None = None,
    caller_email: str | None = None,
    project_number: str | None = None,
) -> dict[str, Any]:
    """Executes idempotent live GCP Phase 2 provisioning against BigQuery, KC, GCS & Vertex AI."""
    from google.cloud import bigquery, storage

    root = (repo_root or REPO_ROOT).resolve()
    project_id = plan["project_id"]
    dataset_id = plan["dataset_id"]
    blind_dataset_id = plan["blind_dataset_id"]
    bq_location = plan["bq_location"]
    connection_id = plan["connection_id"]
    blind_sa = plan["blind_agent_sa"]
    governed_sa = plan["governed_agent_sa"]
    web_runner_sa = plan["web_runner_sa"]

    bq = bq_client or bigquery.Client(project=project_id, location=bq_location)
    gcs = storage_client or storage.Client(project=project_id)
    rest = rest_client or _RestClient()
    active_caller = caller_email if caller_email is not None else _resolve_active_gcloud_account()
    proj_num = project_number if project_number is not None else _resolve_project_number(project_id)

    # Ensure agent SAs & TokenCreator exist BEFORE CTAS so RLS policy sync can grant governed_sa.
    _ensure_sa_exists(blind_sa, project_id=project_id, display_name="Context Engine Blind Agent SA")
    _ensure_sa_exists(governed_sa, project_id=project_id, display_name="Context Engine Governed Agent SA")
    _bind_project_role(project_id, f"serviceAccount:{blind_sa}", "roles/bigquery.jobUser")
    _bind_project_role(project_id, f"serviceAccount:{governed_sa}", "roles/bigquery.jobUser")
    _bind_project_role(project_id, f"serviceAccount:{governed_sa}", "roles/dataplex.catalogViewer")

    web_runner_exists = _sa_exists(web_runner_sa)
    if active_caller:
        caller_member = f"serviceAccount:{active_caller}" if active_caller.endswith(".gserviceaccount.com") else f"user:{active_caller}"
        _bind_sa_token_creator(project_id, blind_sa, caller_member)
        _bind_sa_token_creator(project_id, governed_sa, caller_member)
    if web_runner_exists:
        _bind_sa_token_creator(project_id, blind_sa, f"serviceAccount:{web_runner_sa}")
        _bind_sa_token_creator(project_id, governed_sa, f"serviceAccount:{web_runner_sa}")

    # Step (a): Drop legacy Phase-1 tables (+ old RLS) and stale shadow tables in commerce dataset.
    existing_comm = {t.table_id: t.table_type for t in bq.list_tables(f"{project_id}.{dataset_id}")}
    for legacy_tbl in plan.get("legacy_tables_to_drop") or []:
        if legacy_tbl in existing_comm:
            if list_active_row_access_policies(
                bq, project_id=project_id, dataset_id=dataset_id, table_id=legacy_tbl, location=bq_location
            ):
                bq.query(
                    f"DROP ALL ROW ACCESS POLICIES ON `{project_id}.{dataset_id}.{legacy_tbl}`;",
                    location=bq_location,
                ).result()
            bq.delete_table(f"{project_id}.{dataset_id}.{legacy_tbl}", not_found_ok=True)

    shadow_source = plan["shadow_source_table"]
    if shadow_source:
        src_tbl = bq.get_table(f"{project_id}.{dataset_id}.{shadow_source}")
        expected_sig = [(f.name, f.field_type) for f in src_tbl.schema]
        prefix = plan["shadow_table_prefix"]
        count = int(plan["shadow_table_count"])

        def _heal_commerce_shadow(idx: int) -> None:
            tname = f"{prefix}{idx:03d}"
            tid = f"{project_id}.{dataset_id}.{tname}"
            if tname in existing_comm:
                try:
                    cur = bq.get_table(tid)
                    if [(f.name, f.field_type) for f in cur.schema] == expected_sig:
                        return
                except Exception:
                    pass
                bq.delete_table(tid, not_found_ok=True)
            bq.create_table(bigquery.Table(tid, schema=src_tbl.schema), exists_ok=True)

        with ThreadPoolExecutor(max_workers=20) as pool:
            for fut in as_completed([pool.submit(_heal_commerce_shadow, i) for i in range(1, count + 1)]):
                fut.result()

    # Ensure dataset ACLs & sync CFO RLS policy BEFORE blind CTAS so provisioner sees all RLS rows!
    _reconcile_dataset_acls(
        bq,
        project_id=project_id,
        dataset_id=dataset_id,
        grant_reader_sas=[governed_sa],
        scrub_sas=[blind_sa],
    )
    if plan.get("rls_table") and plan["rls_table"] in existing_comm:
        _sync_rls_cfo_policy(
            bq,
            project_id=project_id,
            dataset_id=dataset_id,
            bq_location=bq_location,
            rls_table=plan.get("rls_table"),
            rls_cfo_policy=plan.get("rls_cfo_policy"),
            caller_email=active_caller,
            governed_sa=governed_sa,
            web_runner_sa=web_runner_sa if web_runner_exists else None,
        )

    # Step (b): Materialize physical Blind dataset + 190 empty shadows + strict ACLs + assertions.
    blind_ds = bigquery.Dataset(f"{project_id}.{blind_dataset_id}")
    blind_ds.location = bq_location
    bq.create_dataset(blind_ds, exists_ok=True)

    _reconcile_dataset_acls(
        bq,
        project_id=project_id,
        dataset_id=blind_dataset_id,
        grant_reader_sas=[blind_sa],
        scrub_sas=[governed_sa, web_runner_sa],
    )

    blind_tables = list(plan["blind_dataset_tables"])
    shadow_prefix = plan["shadow_table_prefix"]
    shadow_count = int(plan["shadow_table_count"])
    valid_shadows = {f"{shadow_prefix}{i:03d}" for i in range(1, shadow_count + 1)}
    keep_blind = set(blind_tables) | valid_shadows

    for existing in bq.list_tables(f"{project_id}.{blind_dataset_id}"):
        if existing.table_id not in keep_blind:
            bq.delete_table(f"{project_id}.{blind_dataset_id}.{existing.table_id}", not_found_ok=True)

    for tbl in blind_tables:
        bq.query(
            f"CREATE OR REPLACE TABLE `{project_id}.{blind_dataset_id}.{tbl}` "
            f"AS SELECT * FROM `{project_id}.{dataset_id}.{tbl}`;",
            location=bq_location,
        ).result()
        _strip_blind_table_metadata(bq, table_id=f"{project_id}.{blind_dataset_id}.{tbl}")

    if shadow_source:
        clean_shadow_schema = [
            bigquery.SchemaField(f.name, f.field_type, mode=f.mode, fields=f.fields)
            for f in bq.get_table(f"{project_id}.{blind_dataset_id}.{shadow_source}").schema
        ]
        existing_blind_shadows = {
            t.table_id: t.table_type
            for t in bq.list_tables(f"{project_id}.{blind_dataset_id}")
            if t.table_id.startswith(shadow_prefix)
        }
        expected_blind_sig = [(f.name, f.field_type) for f in clean_shadow_schema]

        def _sync_blind_shadow(idx: int) -> None:
            tname = f"{shadow_prefix}{idx:03d}"
            tid = f"{project_id}.{blind_dataset_id}.{tname}"
            if tname in existing_blind_shadows:
                try:
                    cur = bq.get_table(tid)
                    has_desc = bool(cur.description or any(f.description for f in cur.schema))
                    if (
                        cur.table_type == "TABLE"
                        and (cur.num_rows or 0) == 0
                        and not has_desc
                        and [(f.name, f.field_type) for f in cur.schema] == expected_blind_sig
                    ):
                        return
                except Exception:
                    pass
                bq.delete_table(tid, not_found_ok=True)
            bq.create_table(bigquery.Table(tid, schema=clean_shadow_schema), exists_ok=True)

        with ThreadPoolExecutor(max_workers=20) as pool:
            for fut in as_completed([pool.submit(_sync_blind_shadow, i) for i in range(1, shadow_count + 1)]):
                fut.result()

    row_counts = _assert_blind_zero_leak_and_parity(
        bq,
        project_id=project_id,
        dataset_id=dataset_id,
        blind_dataset_id=blind_dataset_id,
        bq_location=bq_location,
        blind_tables=blind_tables,
        rls_table=plan.get("rls_table"),
    )

    # Step (d): Knowledge Catalog Glossary + Term + @dataplex projection poll + EntryLink.
    glossary = plan.get("glossary") or {}
    if glossary and glossary.get("glossary_id"):
        g_id = str(glossary["glossary_id"])
        g_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/glossaries?glossaryId={quote(g_id)}"
        st, g_resp = rest.request(
            "POST",
            g_url,
            payload={
                "displayName": str(glossary.get("display_name") or g_id),
                "description": str(glossary.get("description") or ""),
            },
            allow_statuses=(200, 201, 409),
        )
        if st != 409:
            rest.wait_lro(g_resp)

        for term in glossary.get("terms") or []:
            t_id = str(term["term_id"])
            g_resource = f"projects/{project_id}/locations/{bq_location}/glossaries/{g_id}"
            t_url = f"{_DATAPLEX_BASE}/{g_resource}/terms?termId={quote(t_id)}"
            st_t, t_resp = rest.request(
                "POST",
                t_url,
                payload={
                    "displayName": str(term.get("display_name") or t_id),
                    "description": str(term.get("description") or ""),
                    "parent": g_resource,
                },
                allow_statuses=(200, 201, 409),
            )
            if st_t == 409:
                _, patch_resp = rest.request(
                    "PATCH",
                    f"{_DATAPLEX_BASE}/{g_resource}/terms/{t_id}?updateMask=displayName,description",
                    payload={
                        "displayName": str(term.get("display_name") or t_id),
                        "description": str(term.get("description") or ""),
                        "parent": g_resource,
                    },
                    allow_statuses=(200,),
                )
                rest.wait_lro(patch_resp)
            else:
                rest.wait_lro(t_resp)

            if term.get("linked_table") and term.get("linked_column"):
                term_entry = (
                    f"projects/{project_id}/locations/{bq_location}/entryGroups/@dataplex/entries/"
                    f"projects/{proj_num}/locations/{bq_location}/glossaries/{g_id}/terms/{t_id}"
                )
                _poll_entry_exists(rest, project_id=project_id, bq_location=bq_location, entry_name=term_entry)
                bq_entry = (
                    f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery/entries/"
                    f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{term['linked_table']}"
                )
                _poll_entry_exists(rest, project_id=project_id, bq_location=bq_location, entry_name=bq_entry)
                link_id = str(term.get("entry_link_id") or f"{term['linked_table']}-{term['linked_column']}-{t_id}")
                _create_or_update_entry_link(
                    rest,
                    project_id=project_id,
                    bq_location=bq_location,
                    entry_link_id=link_id,
                    bq_entry_name=bq_entry,
                    linked_column=str(term["linked_column"]),
                    term_entry_name=term_entry,
                )

    # Step (e): Custom AspectType + Entry Aspects + Auto Data Quality DataScan.
    for aspect_spec in plan.get("aspect_types") or []:
        at_id = str(aspect_spec["aspect_type_id"])
        template = _build_metadata_template(aspect_spec)
        at_payload = {
            "displayName": str(aspect_spec.get("display_name") or at_id),
            "description": str(aspect_spec.get("description") or ""),
            "metadataTemplate": template,
        }
        at_create_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/aspectTypes?aspectTypeId={quote(at_id)}"
        st_at, at_resp = rest.request("POST", at_create_url, payload=at_payload, allow_statuses=(200, 201, 409))
        if st_at == 409:
            _, p_resp = rest.request(
                "PATCH",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/aspectTypes/{at_id}?updateMask=displayName,description,metadataTemplate",
                payload=at_payload,
                allow_statuses=(200,),
            )
            rest.wait_lro(p_resp)
        else:
            rest.wait_lro(at_resp)

        aspect_key = f"{proj_num}.{bq_location}.{at_id}"
        aspect_type_ref = f"projects/{project_id}/locations/{bq_location}/aspectTypes/{at_id}"
        for attach in aspect_spec.get("attachments") or []:
            tbl_id = str(attach["table_id"])
            entry_name = (
                f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery/entries/"
                f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{tbl_id}"
            )
            _poll_entry_exists(rest, project_id=project_id, bq_location=bq_location, entry_name=entry_name)
            patch_url = (
                f"{_DATAPLEX_BASE}/{entry_name}"
                f"?updateMask=aspects&aspectKeys={quote(aspect_key)}"
            )
            rest.request(
                "PATCH",
                patch_url,
                payload={"aspects": {aspect_key: {"aspectType": aspect_type_ref, "data": dict(attach.get("data") or {})}}},
                allow_statuses=(200,),
            )

    for scan_spec in plan.get("data_quality_scans") or []:
        scan_id = str(scan_spec["data_scan_id"])
        target_tbl = str(scan_spec["target_table"])
        scan_body = {
            "displayName": str(scan_spec.get("display_name") or scan_id),
            "description": str(scan_spec.get("description") or ""),
            "data": {
                "resource": f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{target_tbl}"
            },
            "executionSpec": {"trigger": {"onDemand": {}}},
            "dataQualitySpec": {
                "samplingPercent": float(scan_spec.get("sampling_percent") or 100.0),
                "catalogPublishingEnabled": bool(scan_spec.get("catalog_publishing_enabled", True)),
                "rules": list(scan_spec.get("rules") or []),
            },
        }
        ds_create_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans?dataScanId={quote(scan_id)}"
        st_ds, ds_resp = rest.request("POST", ds_create_url, payload=scan_body, allow_statuses=(200, 201, 409))
        if st_ds == 409:
            _, upd_resp = rest.request(
                "PATCH",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{scan_id}?updateMask=displayName,description,dataQualitySpec,executionSpec",
                payload=scan_body,
                allow_statuses=(200,),
            )
            rest.wait_lro(upd_resp)
        else:
            rest.wait_lro(ds_resp)

        jobs_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{scan_id}/jobs"
        _, jobs_resp = rest.request("GET", jobs_url, allow_statuses=(200,))
        existing_jobs = list(jobs_resp.get("dataScanJobs") or [])
        if not any(j.get("state") == "SUCCEEDED" for j in existing_jobs):
            _, run_resp = rest.request(
                "POST",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{scan_id}:run",
                payload={},
                allow_statuses=(200,),
            )
            job_name = str((run_resp.get("job") or {}).get("name") or "")
            if job_name:
                deadline = time.monotonic() + 120.0
                while time.monotonic() < deadline:
                    time.sleep(3.0)
                    _, j_latest = rest.request("GET", f"{_DATAPLEX_BASE}/{job_name}", allow_statuses=(200,))
                    state = str(j_latest.get("state") or "")
                    if state == "SUCCEEDED":
                        break
                    if state in {"FAILED", "CANCELLED"}:
                        raise RuntimeError(f"DataScan job {job_name} failed: {j_latest}")

    # Step (f): GCS contracts + BigQuery Connection + Object Table + Safe AI.GENERATE staging.
    unstructured = dict(plan.get("unstructured_contracts") or {})
    if unstructured:
        bucket_name = plan["bucket_name"]
        try:
            bucket = gcs.get_bucket(bucket_name)
        except Exception:
            bucket = gcs.bucket(bucket_name)
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            bucket.iam_configuration.public_access_prevention = "enforced"
            bucket = gcs.create_bucket(bucket, location=bq_location)
        if not bucket.iam_configuration.uniform_bucket_level_access_enabled or bucket.iam_configuration.public_access_prevention != "enforced":
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            bucket.iam_configuration.public_access_prevention = "enforced"
            bucket.patch()

        base_packs = Path(packs_dir) if packs_dir else (root / "packs")
        source_dir = base_packs / plan["pack_id"] / str(unstructured.get("source_dir") or "contracts")
        for md_file in sorted(source_dir.glob("*.md")):
            blob = bucket.blob(md_file.name)
            blob.upload_from_filename(str(md_file), content_type="text/plain")

        conn_id = plan["connection_id"]
        conn_create_url = f"{_BQ_CONN_BASE}/projects/{project_id}/locations/{bq_location}/connections?connectionId={quote(conn_id)}"
        st_c, conn_resp = rest.request("POST", conn_create_url, payload={"cloudResource": {}}, allow_statuses=(200, 201, 409))
        if st_c == 409:
            _, conn_resp = rest.request(
                "GET",
                f"{_BQ_CONN_BASE}/projects/{project_id}/locations/{bq_location}/connections/{conn_id}",
                allow_statuses=(200,),
            )
        conn_sa = str((conn_resp.get("cloudResource") or {}).get("serviceAccountId") or "").strip()
        if not conn_sa:
            raise RuntimeError(f"BigQuery Connection {conn_id!r} missing cloudResource.serviceAccountId")

        _bind_project_role(project_id, f"serviceAccount:{conn_sa}", "roles/aiplatform.user")
        policy = bucket.get_iam_policy(requested_policy_version=3)
        target_member = f"serviceAccount:{conn_sa}"
        if not any(b.get("role") == "roles/storage.objectViewer" and target_member in (b.get("members") or set()) for b in policy.bindings):
            policy.bindings.append({"role": "roles/storage.objectViewer", "members": {target_member}})
            bucket.set_iam_policy(policy)

        obj_tbl = str(unstructured.get("object_table") or "contract_docs_obj")
        ext_ddl = (
            f"CREATE OR REPLACE EXTERNAL TABLE `{project_id}.{dataset_id}.{obj_tbl}` "
            f"WITH CONNECTION `{project_id}.{bq_location}.{conn_id}` "
            f"OPTIONS(object_metadata='SIMPLE', uris=['gs://{bucket_name}/*.md']);"
        )
        bq.query(ext_ddl, location=bq_location).result()

        extracted_tbl = str(unstructured.get("target_table") or "sla_overlay_extracted")
        target_pattern = str(unstructured.get("target_file_pattern") or "Amendment_2.md")
        vendor_filter = str(unstructured.get("target_vendor_filter") or "")
        model_endpoint = (
            f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/{plan['model_location']}"
            f"/publishers/google/models/{plan['model_id']}"
        )
        prompt_text = str(
            unstructured.get("extraction_prompt")
            or "Extract structured SLA amendment parameters from this contract document as exact numeric values."
        ).replace("'", "\\'")
        output_schema = str(
            unstructured.get("output_schema")
            or "vendor STRING, temp_threshold_c FLOAT64, duration_threshold_min INT64, credit_rate FLOAT64, quarterly_cap_sgd FLOAT64"
        )
        vendor_expr = f"'{vendor_filter}'" if vendor_filter else "REGEXP_EXTRACT(uri, r'/([^/]+)\\.md$')"
        ai_sql = (
            f"CREATE OR REPLACE TABLE `{project_id}.{dataset_id}.{extracted_tbl}` AS\n"
            f"WITH generated AS (\n"
            f"  SELECT\n"
            f"    uri,\n"
            f"    AI.GENERATE(\n"
            f"      ('{prompt_text}', OBJ.GET_ACCESS_URL(ref, 'r')),\n"
            f"      connection_id => '{bq_location}.{conn_id}',\n"
            f"      endpoint => '{model_endpoint}',\n"
            f"      output_schema => '{output_schema}'\n"
            f"    ) AS res\n"
            f"  FROM `{project_id}.{dataset_id}.{obj_tbl}`\n"
            f"  WHERE uri LIKE '%{target_pattern}%'\n"
            f")\n"
            f"SELECT\n"
            f"  COALESCE(res.vendor, {vendor_expr}) AS vendor,\n"
            f"  res.temp_threshold_c,\n"
            f"  res.duration_threshold_min,\n"
            f"  res.credit_rate,\n"
            f"  res.quarterly_cap_sgd,\n"
            f"  uri AS source_uri,\n"
            f"  res.status AS extraction_status\n"
            f"FROM generated;"
        )

        # Retry briefly if BigQuery connection IAM binding takes a few seconds to propagate.
        for attempt in range(6):
            try:
                bq.query(ai_sql, location=bq_location).result()
                break
            except Exception as err:
                msg = str(err).lower()
                transient = any(tok in msg for tok in ("access denied", "permission", "403", "does not have", "iam"))
                if attempt < 5 and transient:
                    time.sleep(10.0)
                    continue
                raise

        # Validate extracted invariants cleanly against expected_invariants!
        invariants = dict(unstructured.get("expected_invariants") or {})
        if invariants:
            ext_rows = list(
                bq.query(
                    f"SELECT * FROM `{project_id}.{dataset_id}.{extracted_tbl}`",
                    location=bq_location,
                ).result()
            )
            if not ext_rows:
                raise RuntimeError(f"AI.GENERATE staging table {extracted_tbl} produced 0 rows.")
            row = ext_rows[0]
            for k, expected_v in invariants.items():
                actual_v = row.get(k) if hasattr(row, "get") else row[k]
                if actual_v is None or abs(float(actual_v) - float(expected_v)) > 1e-4:
                    raise RuntimeError(
                        f"AI.GENERATE invariant mismatch on {extracted_tbl}.{k}: expected {expected_v}, got {actual_v}"
                    )

    return {
        "status": "provisioned",
        "pack_id": plan["pack_id"],
        "blind_dataset_id": blind_dataset_id,
        "blind_table_counts": row_counts,
        "shadow_tables": plan["shadow_table_count"],
        "glossary_id": (plan.get("glossary") or {}).get("glossary_id"),
        "connection_id": connection_id,
    }


def run_teardown(
    plan: Mapping[str, Any],
    *,
    delete_agent_sas: bool = False,
    bq_client: Any = None,
    storage_client: Any = None,
    rest_client: _RestClient | None = None,
) -> dict[str, Any]:
    """Dependency-ordered teardown of Phase 2 Knowledge Catalog, GCS, Blind dataset & SAs."""
    from google.cloud import bigquery, storage

    project_id = plan["project_id"]
    dataset_id = plan["dataset_id"]
    blind_dataset_id = plan["blind_dataset_id"]
    bq_location = plan["bq_location"]
    connection_id = plan["connection_id"]

    bq = bq_client or bigquery.Client(project=project_id, location=bq_location)
    gcs = storage_client or storage.Client(project=project_id)
    rest = rest_client or _RestClient()
    deleted_steps: list[str] = []

    glossary = plan.get("glossary") or {}
    g_id = str(glossary.get("glossary_id") or "").strip()

    # 1. EntryLinks -> Terms -> Glossary
    if g_id:
        for term in glossary.get("terms") or []:
            t_id = str(term["term_id"])
            if term.get("linked_table") and term.get("linked_column"):
                link_id = str(term.get("entry_link_id") or f"{term['linked_table']}-{term['linked_column']}-{t_id}")
                link_url = (
                    f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}"
                    f"/entryGroups/@bigquery/entryLinks/{quote(link_id)}"
                )
                st, resp = rest.request("DELETE", link_url, allow_statuses=(200, 202, 204, 404))
                if st != 404 and isinstance(resp, dict):
                    rest.wait_lro(resp)
                deleted_steps.append(f"entryLink:{link_id}")

            term_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/glossaries/{g_id}/terms/{t_id}"
            st, resp = rest.request("DELETE", term_url, allow_statuses=(200, 202, 204, 404))
            if st != 404 and isinstance(resp, dict):
                rest.wait_lro(resp)
            deleted_steps.append(f"term:{t_id}")

        g_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/glossaries/{g_id}"
        st, resp = rest.request("DELETE", g_url, allow_statuses=(200, 202, 204, 404))
        if st != 404 and isinstance(resp, dict):
            rest.wait_lro(resp)
        deleted_steps.append(f"glossary:{g_id}")

    # 2. DataScans
    for scan in plan.get("data_quality_scans") or []:
        scan_id = str(scan["data_scan_id"])
        ds_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{scan_id}?force=true"
        st, resp = rest.request("DELETE", ds_url, allow_statuses=(200, 202, 204, 404))
        if st != 404 and isinstance(resp, dict):
            rest.wait_lro(resp)
        deleted_steps.append(f"dataScan:{scan_id}")

    # 3. AspectTypes
    for aspect_spec in plan.get("aspect_types") or []:
        at_id = str(aspect_spec["aspect_type_id"])
        at_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/aspectTypes/{at_id}"
        st, resp = rest.request("DELETE", at_url, allow_statuses=(200, 202, 204, 404))
        if st != 404 and isinstance(resp, dict):
            rest.wait_lro(resp)
        deleted_steps.append(f"aspectType:{at_id}")

    # 4. Object Table / Extracted SLA Overlay -> BigQuery Connection
    unstructured = dict(plan.get("unstructured_contracts") or {})
    for tbl_key in ("target_table", "object_table"):
        tbl_name = str(unstructured.get(tbl_key) or "").strip()
        if tbl_name:
            bq.delete_table(f"{project_id}.{dataset_id}.{tbl_name}", not_found_ok=True)
            deleted_steps.append(f"table:{dataset_id}.{tbl_name}")

    conn_url = f"{_BQ_CONN_BASE}/projects/{project_id}/locations/{bq_location}/connections/{connection_id}"
    rest.request("DELETE", conn_url, allow_statuses=(200, 202, 204, 404))
    deleted_steps.append(f"connection:{connection_id}")

    # 5. GCS objects & bucket
    bucket_name = plan.get("bucket_name")
    if bucket_name:
        try:
            bucket = gcs.get_bucket(bucket_name)
            for blob in list(bucket.list_blobs()):
                blob.delete()
            bucket.delete(force=True)
            deleted_steps.append(f"bucket:{bucket_name}")
        except Exception:
            pass

    # 6. Blind BigQuery dataset
    bq.delete_dataset(f"{project_id}.{blind_dataset_id}", delete_contents=True, not_found_ok=True)
    deleted_steps.append(f"dataset:{blind_dataset_id}")

    # 7. Optional Agent SAs
    if delete_agent_sas:
        for sa_email in (plan["blind_agent_sa"], plan["governed_agent_sa"]):
            for role in ("roles/bigquery.jobUser", "roles/dataplex.catalogViewer"):
                _run_cmd(
                    [
                        "gcloud",
                        "projects",
                        "remove-iam-policy-binding",
                        project_id,
                        f"--member=serviceAccount:{sa_email}",
                        f"--role={role}",
                        "--quiet",
                    ],
                    check=False,
                )
            _run_cmd(
                ["gcloud", "iam", "service-accounts", "delete", sa_email, f"--project={project_id}", "--quiet"],
                check=False,
            )
            deleted_steps.append(f"sa:{sa_email}")

    return {
        "status": "torn_down",
        "pack_id": plan["pack_id"],
        "deleted": deleted_steps,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Provision or tear down Phase 2 Blind/Governed GCP Knowledge Catalog & AI extraction layer."
    )
    parser.add_argument("--pack", default=None, help="Scenario pack ID under packs/ (defaults to PACK_ID from .env/.env.example).")
    parser.add_argument("--dry-run", action="store_true", help="Print redacted provisioning/teardown plan with zero network calls.")
    parser.add_argument("--live-gcp", action="store_true", help="Execute idempotent live GCP provisioning.")
    parser.add_argument("--teardown", action="store_true", help="Tear down Phase 2 governance/blind resources in dependency order.")
    parser.add_argument("--delete-agent-sas", action="store_true", help="Also delete blind/governed SAs during --teardown.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    load_dotenv_if_present(REPO_ROOT)
    defaults = resolve_phase2_settings(REPO_ROOT, pack_id=args.pack)
    pack_id = args.pack or defaults.get("PACK_ID") or ""
    if not pack_id:
        raise SystemExit("ERROR: Specify --pack or set PACK_ID in environment/.env.")
    plan = resolve_provision_plan(
        pack_id=pack_id,
        repo_root=REPO_ROOT,
        allow_missing_context_layer=bool(args.teardown),
    )

    if args.dry_run or (not args.live_gcp and not args.teardown):
        mode = "teardown" if args.teardown else "provision"
        dry_summary = {
            "mode": mode,
            "dry_run": True,
            "delete_agent_sas": bool(args.delete_agent_sas),
            "plan": plan,
        }
        print(json.dumps(redact_bundle_data(dry_summary, live_project_id=plan["project_id"]), indent=2))
        return 0

    if not plan["project_id"] or plan["project_id"] == "example-project-id":
        raise SystemExit("ERROR: PROJECT_ID must be set to a live GCP project ID for --live-gcp / --teardown.")

    if args.teardown:
        result = run_teardown(plan, delete_agent_sas=bool(args.delete_agent_sas))
    else:
        result = run_provision(plan)

    print(json.dumps(redact_bundle_data(result, live_project_id=plan["project_id"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
