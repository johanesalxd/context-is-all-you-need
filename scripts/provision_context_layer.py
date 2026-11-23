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
    effective_packs_dir = packs_dir or (root / "packs")
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
            packs_dir=effective_packs_dir,
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

    rls_table, rls_cfo_policy = discover_rls_target(pack_id, packs_dir=effective_packs_dir)
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
        "shadow_table_description": str(ctx.get("shadow_table_description") or "").strip(),
        "glossary": ctx.get("glossary") or {},
        "aspect_types": list(ctx.get("aspect_types") or []),
        "data_quality_scans": list(ctx.get("data_quality_scans") or []),
        "data_profile_scans": list(ctx.get("data_profile_scans") or []),
        "data_documentation_scans": list(ctx.get("data_documentation_scans") or []),
        "data_products": list(ctx.get("data_products") or []),
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


def _resolve_dataplex_service_agent(project_id: str) -> str | None:
    try:
        proj_num = _resolve_project_number(project_id)
    except Exception:
        return None
    if proj_num and proj_num.isdigit():
        return f"service-{proj_num}@gcp-sa-dataplex.iam.gserviceaccount.com"
    return None


def _fetch_rls_grantees_via_rest(
    rest_client: _RestClient | None,
    *,
    project_id: str,
    dataset_id: str,
    rls_table: str,
    rls_cfo_policy: str,
) -> tuple[bool, list[str]]:
    if rest_client is None:
        return False, []
    base = (
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{quote(project_id)}"
        f"/datasets/{quote(dataset_id)}/tables/{quote(rls_table)}/rowAccessPolicies"
    )
    try:
        st, resp = rest_client.request("GET", base, allow_statuses=(200, 403, 404))
    except Exception:
        return False, []
    if st != 200 or not isinstance(resp, Mapping):
        return False, []
    for item in resp.get("rowAccessPolicies") or []:
        if not isinstance(item, Mapping):
            continue
        ref = item.get("rowAccessPolicyReference")
        pol_id = str(
            (ref.get("policyId") if isinstance(ref, Mapping) else None)
            or item.get("policy_id")
            or item.get("policyId")
            or ""
        )
        if pol_id != rls_cfo_policy:
            continue
        direct = [str(g).strip() for g in (item.get("grantees") or item.get("grantee_list") or []) if str(g).strip()]
        if direct:
            return True, direct
        try:
            st_iam, iam_resp = rest_client.request(
                "POST",
                f"{base}/{quote(rls_cfo_policy)}:getIamPolicy",
                payload={},
                allow_statuses=(200, 403, 404),
            )
            if st_iam == 200 and isinstance(iam_resp, Mapping):
                members: list[str] = []
                for binding in iam_resp.get("bindings") or []:
                    if isinstance(binding, Mapping):
                        for m in binding.get("members") or []:
                            ms = str(m).strip()
                            if ms and ms not in members:
                                members.append(ms)
                return True, members
        except Exception:
            return True, []
        return True, []
    return False, []


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
    rest_client: _RestClient | None = None,
    dataplex_sa: str | None = None,
    restricted_sas: Sequence[str] = (),
) -> None:
    if not rls_table or not rls_cfo_policy:
        return

    merged: dict[str, str] = {}

    def _add_grantee(principal: str) -> None:
        cleaned = str(principal or "").strip()
        if cleaned:
            merged.setdefault(cleaned.lower(), cleaned)

    if caller_email:
        if caller_email.endswith(".gserviceaccount.com"):
            _add_grantee(f"serviceAccount:{caller_email}")
        else:
            _add_grantee(f"user:{caller_email}")
    _add_grantee(f"serviceAccount:{governed_sa}")
    if web_runner_sa:
        _add_grantee(f"serviceAccount:{web_runner_sa}")
    if dataplex_sa:
        d_sa = dataplex_sa.strip()
        _add_grantee(d_sa if d_sa.startswith("serviceAccount:") else f"serviceAccount:{d_sa}")

    policy_exists = False
    existing_grantees: list[str] = []
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
            policy_exists = True
            existing_grantees.extend(str(g).strip() for g in pol_grantees if str(g).strip())

    if not existing_grantees:
        rest_exists, rest_grantees = _fetch_rls_grantees_via_rest(
            rest_client,
            project_id=project_id,
            dataset_id=dataset_id,
            rls_table=rls_table,
            rls_cfo_policy=rls_cfo_policy,
        )
        if rest_exists:
            policy_exists = True
        existing_grantees.extend(rest_grantees)

    if policy_exists and not existing_grantees:
        raise RuntimeError(
            f"Refusing to overwrite existing RLS policy {rls_cfo_policy}: could not read existing grantees"
        )

    restricted_set = {
        *(sa.strip().lower() for sa in restricted_sas if sa and sa.strip()),
        *(f"serviceaccount:{sa.strip().lower()}" for sa in restricted_sas if sa and sa.strip()),
    }
    for g in existing_grantees:
        g_low = g.lower()
        if g_low.startswith("deleted:"):
            continue
        if g_low in restricted_set:
            continue
        if "coldchain" in g_low or "denied" in g_low or "blind-agent" in g_low:
            continue
        _add_grantee(g)

    grantees = sorted(merged.values(), key=lambda x: x.lower())
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


def _poll_entry_exists(
    rest: _RestClient,
    *,
    project_id: str,
    bq_location: str,
    entry_name: str,
    timeout_s: float = 45.0,
    poll_interval_s: float = 3.0,
) -> None:
    url = (
        f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}:lookupEntry"
        f"?entry={quote(entry_name, safe='/:@')}&view=BASIC"
    )
    deadline = time.monotonic() + timeout_s
    while True:
        status, _ = rest.request("GET", url, allow_statuses=(200, 403, 404))
        if status == 200:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for projected Knowledge Catalog entry: {entry_name}")
        if poll_interval_s > 0:
            time.sleep(poll_interval_s)


def _is_already_exists_error(status: int, resp: Any) -> bool:
    if status == 409:
        return True
    if status == 400:
        msg = resp if isinstance(resp, str) else json.dumps(resp or {}, ensure_ascii=True)
        return "already exists" in msg.lower()
    return False


def _sanitize_dataplex_id(raw_id: str, *, fallback_prefix: str = "link") -> str:
    """Normalizes a Dataplex resource ID to [a-z][a-z0-9-]{0,61}[a-z0-9]."""
    cleaned = re.sub(r"[^a-z0-9-]+", "-", raw_id.strip().lower())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-")
    if not cleaned or not ("a" <= cleaned[0] <= "z"):
        cleaned = f"{fallback_prefix}-{cleaned}".strip("-")
    cleaned = cleaned[:63].rstrip("-")
    if not cleaned or not ("a" <= cleaned[0] <= "z"):
        cleaned = f"{fallback_prefix}-id"
    if not cleaned[-1].isalnum():
        cleaned = f"{cleaned[:62]}0"
    return cleaned


def _iter_term_column_links(term: Mapping[str, Any]) -> list[dict[str, str]]:
    """Normalizes glossary term linked_columns (list) or legacy single linked_table/linked_column."""
    t_id = str(term.get("term_id") or "").strip()
    links: list[dict[str, str]] = []
    for raw in term.get("linked_columns") or []:
        if not isinstance(raw, Mapping):
            continue
        tbl = str(raw.get("table") or "").strip()
        col = str(raw.get("column") or "").strip()
        if not tbl or not col:
            continue
        ltype = str(raw.get("link_type") or "definition").strip() or "definition"
        lid = _sanitize_dataplex_id(str(raw.get("entry_link_id") or f"{tbl}-{col}-{t_id}"))
        links.append({"table": tbl, "column": col, "link_type": ltype, "entry_link_id": lid})
    if not links and term.get("linked_table") and term.get("linked_column"):
        tbl = str(term["linked_table"]).strip()
        col = str(term["linked_column"]).strip()
        lid = _sanitize_dataplex_id(str(term.get("entry_link_id") or f"{tbl}-{col}-{t_id}"))
        links.append({"table": tbl, "column": col, "link_type": "definition", "entry_link_id": lid})
    return links


def _translate_dq_rules(raw_rules: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Translates simplified YAML DQ rules into Dataplex v1 DataQualityRule JSON payloads."""
    translated: list[dict[str, Any]] = []
    for raw in raw_rules:
        if not isinstance(raw, Mapping):
            continue
        rule: dict[str, Any] = {}
        for k in ("name", "column", "dimension", "description", "ignoreNull", "threshold", "suspended"):
            if k in raw:
                rule[k] = raw[k]
        if "set_values" in raw and "setExpectation" not in raw:
            rule["setExpectation"] = {"values": [str(v) for v in (raw.get("set_values") or [])]}
        if raw.get("non_null") is True and "nonNullExpectation" not in raw:
            rule["nonNullExpectation"] = {}
        for k, v in raw.items():
            if k.endswith("Expectation") and k not in rule:
                rule[k] = v
        translated.append(rule)
    return translated


def _create_or_update_entry_link(
    rest: _RestClient,
    *,
    project_id: str,
    bq_location: str,
    entry_link_id: str,
    bq_entry_name: str,
    linked_column: str,
    term_entry_name: str,
    link_type_slug: str = "definition",
) -> None:
    parent = f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery"
    url = f"{_DATAPLEX_BASE}/{parent}/entryLinks?entryLinkId={quote(entry_link_id)}"
    link_type = f"projects/dataplex-types/locations/global/entryLinkTypes/{link_type_slug}"

    primary_body = {
        "entryLinkType": link_type,
        "entryReferences": [
            {"name": bq_entry_name, "path": f"Schema.{linked_column}", "type": "SOURCE"},
            {"name": term_entry_name, "type": "TARGET"},
        ],
    }
    status, resp = rest.request("POST", url, payload=primary_body, allow_statuses=(200, 201, 400, 409))
    if _is_already_exists_error(status, resp):
        return
    if status == 400:
        err_text = (resp if isinstance(resp, str) else json.dumps(resp or {}, ensure_ascii=True)).lower()
        orientation_err = any(
            tok in err_text
            for tok in ("entryreference", "entry reference", "source", "target", "entrylinktype", "link type")
        )
        if not orientation_err:
            raise RuntimeError(f"HTTP 400 for POST {url}: {err_text[:500]}")
        swapped_body = {
            "entryLinkType": link_type,
            "entryReferences": [
                {"name": bq_entry_name, "path": f"Schema.{linked_column}", "type": "TARGET"},
                {"name": term_entry_name, "type": "SOURCE"},
            ],
        }
        status2, resp2 = rest.request("POST", url, payload=swapped_body, allow_statuses=(200, 201, 400, 409))
        if _is_already_exists_error(status2, resp2):
            return
        if status2 == 400:
            raise RuntimeError(f"HTTP 400 for POST {url}: {json.dumps(resp2)[:500]}")
        rest.wait_lro(resp2)
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
    shadow_desc = str(plan.get("shadow_table_description") or "").strip()
    if shadow_source:
        src_tbl = bq.get_table(f"{project_id}.{dataset_id}.{shadow_source}")
        expected_sig = [(f.name, f.field_type) for f in src_tbl.schema]
        prefix = plan["shadow_table_prefix"]
        count = int(plan["shadow_table_count"])

        def _heal_commerce_shadow(idx: int) -> None:
            tname = f"{prefix}{idx:03d}"
            tid = f"{project_id}.{dataset_id}.{tname}"
            if tname in existing_comm:
                cur = None
                schema_matches = False
                try:
                    cur = bq.get_table(tid)
                    schema_matches = [(f.name, f.field_type) for f in cur.schema] == expected_sig
                except Exception:
                    schema_matches = False
                if schema_matches and cur is not None:
                    if shadow_desc and (getattr(cur, "description", None) or "").strip() != shadow_desc:
                        cur.description = shadow_desc
                        bq.update_table(cur, ["description"])
                    return
                bq.delete_table(tid, not_found_ok=True)
            tbl_obj = bigquery.Table(tid, schema=src_tbl.schema)
            if shadow_desc:
                tbl_obj.description = shadow_desc
            bq.create_table(tbl_obj, exists_ok=True)

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
        rls_tbl_name = str(plan.get("rls_table") or "").strip()
        all_scan_tables = {
            str(s.get("target_table") or "").strip()
            for k in ("data_quality_scans", "data_profile_scans", "data_documentation_scans")
            for s in (plan.get(k) or [])
            if isinstance(s, Mapping)
        }
        dataplex_sa: str | None = None
        if rls_tbl_name and rls_tbl_name in all_scan_tables:
            dataplex_sa = _resolve_dataplex_service_agent(project_id)
            if not dataplex_sa and project_number and str(project_number).strip().isdigit():
                dataplex_sa = f"service-{str(project_number).strip()}@gcp-sa-dataplex.iam.gserviceaccount.com"
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
            rest_client=rest,
            dataplex_sa=dataplex_sa,
            restricted_sas=[blind_sa],
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
            allow_statuses=(200, 201, 400, 409),
        )
        if _is_already_exists_error(st, g_resp):
            pass
        elif st == 400:
            raise RuntimeError(f"HTTP 400 for POST {g_url}: {json.dumps(g_resp)[:500]}")
        else:
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
                allow_statuses=(200, 201, 400, 409),
            )
            if _is_already_exists_error(st_t, t_resp):
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
            elif st_t == 400:
                raise RuntimeError(f"HTTP 400 for POST {t_url}: {json.dumps(t_resp)[:500]}")
            else:
                rest.wait_lro(t_resp)

            for link_spec in _iter_term_column_links(term):
                linked_tbl = link_spec["table"]
                linked_col = link_spec["column"]
                term_entry = (
                    f"projects/{proj_num}/locations/{bq_location}/entryGroups/@dataplex/entries/"
                    f"projects/{proj_num}/locations/{bq_location}/glossaries/{g_id}/terms/{t_id}"
                )
                _poll_entry_exists(rest, project_id=project_id, bq_location=bq_location, entry_name=term_entry)
                bq_entry = (
                    f"projects/{proj_num}/locations/{bq_location}/entryGroups/@bigquery/entries/"
                    f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{linked_tbl}"
                )
                _poll_entry_exists(rest, project_id=project_id, bq_location=bq_location, entry_name=bq_entry)
                _create_or_update_entry_link(
                    rest,
                    project_id=project_id,
                    bq_location=bq_location,
                    entry_link_id=link_spec["entry_link_id"],
                    bq_entry_name=bq_entry,
                    linked_column=linked_col,
                    term_entry_name=term_entry,
                    link_type_slug=link_spec["link_type"],
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
        st_at, at_resp = rest.request("POST", at_create_url, payload=at_payload, allow_statuses=(200, 201, 400, 409))
        if _is_already_exists_error(st_at, at_resp):
            _, p_resp = rest.request(
                "PATCH",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/aspectTypes/{at_id}?updateMask=displayName,description,metadataTemplate",
                payload=at_payload,
                allow_statuses=(200,),
            )
            rest.wait_lro(p_resp)
        elif st_at == 400:
            raise RuntimeError(f"HTTP 400 for POST {at_create_url}: {json.dumps(at_resp)[:500]}")
        else:
            rest.wait_lro(at_resp)

        aspect_key = f"{proj_num}.{bq_location}.{at_id}"
        aspect_type_ref = f"projects/{project_id}/locations/{bq_location}/aspectTypes/{at_id}"
        for attach in (aspect_spec.get("assignments") or aspect_spec.get("attachments") or []):
            tbl_id = str(attach.get("table") or attach["table_id"])
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

    def _provision_and_run_scan(
        scan_spec: Mapping[str, Any],
        *,
        spec_key: str,
        spec_payload: dict[str, Any],
    ) -> str:
        scan_id = str(scan_spec.get("scan_id") or scan_spec["data_scan_id"])
        quoted_scan_id = quote(scan_id)
        target_tbl = str(scan_spec["target_table"])
        scan_body = {
            "displayName": str(scan_spec.get("display_name") or scan_id),
            "description": str(scan_spec.get("description") or ""),
            "data": {
                "resource": f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{target_tbl}"
            },
            "executionSpec": {"trigger": {"onDemand": {}}},
            spec_key: spec_payload,
        }
        ds_create_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans?dataScanId={quoted_scan_id}"
        st_ds, ds_resp = rest.request("POST", ds_create_url, payload=scan_body, allow_statuses=(200, 201, 400, 409))
        if _is_already_exists_error(st_ds, ds_resp):
            _, upd_resp = rest.request(
                "PATCH",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{quoted_scan_id}?updateMask=displayName,description,{spec_key},executionSpec",
                payload=scan_body,
                allow_statuses=(200,),
            )
            rest.wait_lro(upd_resp)
        elif st_ds == 400:
            raise RuntimeError(f"HTTP 400 for POST {ds_create_url}: {json.dumps(ds_resp)[:500]}")
        else:
            rest.wait_lro(ds_resp)

        jobs_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{quoted_scan_id}/jobs"
        _, jobs_resp = rest.request("GET", jobs_url, allow_statuses=(200,))
        existing_jobs = list(jobs_resp.get("dataScanJobs") or [])
        if not any(j.get("state") == "SUCCEEDED" for j in existing_jobs):
            active_job = next(
                (j for j in existing_jobs if j.get("state") in {"PENDING", "RUNNING"}),
                None,
            )
            if active_job is not None:
                job_name = str(active_job.get("name") or "")
            else:
                _, run_resp = rest.request(
                    "POST",
                    f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{quoted_scan_id}:run",
                    payload={},
                    allow_statuses=(200,),
                )
                job_name = str((run_resp.get("job") or {}).get("name") or "")
            if job_name:
                try:
                    timeout_s = max(1.0, float(os.environ.get("DATASCAN_POLL_TIMEOUT_S") or 120.0))
                except ValueError:
                    timeout_s = 120.0
                deadline = time.monotonic() + timeout_s
                succeeded = False
                while time.monotonic() < deadline:
                    time.sleep(3.0)
                    _, j_latest = rest.request(
                        "GET",
                        f"{_DATAPLEX_BASE}/{job_name.lstrip('/')}",
                        allow_statuses=(200,),
                    )
                    state = str(j_latest.get("state") or "")
                    if state == "SUCCEEDED":
                        succeeded = True
                        break
                    if state in {"FAILED", "CANCELLED"}:
                        raise RuntimeError(f"DataScan job {job_name} failed: {j_latest}")
                if not succeeded:
                    raise TimeoutError(f"DataScan job {job_name} timed out after {timeout_s}s")
        return scan_id

    for scan_spec in plan.get("data_quality_scans") or []:
        dq_sampling = (
            float(scan_spec["sampling_percent"])
            if scan_spec.get("sampling_percent") is not None
            else 100.0
        )
        _provision_and_run_scan(
            scan_spec,
            spec_key="dataQualitySpec",
            spec_payload={
                "samplingPercent": dq_sampling,
                "catalogPublishingEnabled": bool(scan_spec.get("catalog_publishing_enabled", True)),
                "rules": _translate_dq_rules(scan_spec.get("rules") or []),
            },
        )

    # Step (f): GCS contracts + BigQuery Connection + Object Table + Safe AI.GENERATE staging.
    # Run BEFORE optional Data Profile / Data Insights scans and Data Products so core R6 is never blocked.
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
        pack_dir = base_packs / plan["pack_id"]
        listed_files = [str(f).strip() for f in (unstructured.get("files") or []) if str(f).strip()]
        if listed_files:
            upload_paths = [pack_dir / rel_f for rel_f in listed_files]
        else:
            source_dir = pack_dir / str(unstructured.get("source_dir") or "contracts")
            upload_paths = sorted(source_dir.glob("*.md"))
        for md_file in upload_paths:
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
        obj_desc = str(unstructured.get("object_table_description") or "").strip()
        if obj_desc:
            obj_tbl_ref = bq.get_table(f"{project_id}.{dataset_id}.{obj_tbl}")
            if getattr(obj_tbl_ref, "description", None) != obj_desc:
                obj_tbl_ref.description = obj_desc
                bq.update_table(obj_tbl_ref, ["description"])

        extracted_tbl = str(
            unstructured.get("extraction_staging_table")
            or unstructured.get("target_table")
            or "sla_overlay_extracted"
        )
        target_pattern = str(unstructured.get("target_file_pattern") or "Amendment_2.md")
        vendor_filter = str(unstructured.get("target_vendor_filter") or "")
        prompt_text = str(
            unstructured.get("ai_generate_prompt")
            or unstructured.get("extraction_prompt")
            or "Extract structured SLA amendment parameters from this contract document as exact numeric values."
        ).replace("'", "\\'")
        default_schema = (
            "overlay_id STRING, vendor_name STRING, sku_class STRING, effective_quarter STRING, "
            "source_document STRING, temp_threshold_c FLOAT64, duration_threshold_min INT64, "
            "credit_rate FLOAT64, quarterly_cap_sgd FLOAT64"
        )
        output_schema = str(unstructured.get("output_schema") or default_schema)
        vendor_expr = f"'{vendor_filter}'" if vendor_filter else "REGEXP_EXTRACT(uri, r'/([^/]+)\\.md$')"

        def _build_ai_sql(target_model_id: str) -> str:
            model_endpoint = (
                f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/{plan['model_location']}"
                f"/publishers/google/models/{target_model_id}"
            )
            return (
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
                f"  res.overlay_id,\n"
                f"  COALESCE(res.vendor_name, {vendor_expr}) AS vendor_name,\n"
                f"  res.sku_class,\n"
                f"  res.effective_quarter,\n"
                f"  res.source_document,\n"
                f"  res.temp_threshold_c,\n"
                f"  res.duration_threshold_min,\n"
                f"  res.credit_rate,\n"
                f"  res.quarterly_cap_sgd,\n"
                f"  uri AS source_uri,\n"
                f"  res.status AS extraction_status\n"
                f"FROM generated;"
            )

        active_model_id = str(plan["model_id"])
        fallback_model_id = "gemini-3.5-flash"
        # Retry briefly for IAM propagation AND fall back on 404/not-found to gemini-3.5-flash.
        for attempt in range(6):
            try:
                bq.query(_build_ai_sql(active_model_id), location=bq_location).result()
                break
            except Exception as err:
                msg = str(err).lower()
                unavailable = any(
                    tok in msg
                    for tok in ("404", "not_found", "not found", "unavailable", "does not have access to")
                )
                if unavailable and active_model_id != fallback_model_id:
                    active_model_id = fallback_model_id
                    continue
                transient = any(tok in msg for tok in ("access denied", "permission", "403", "does not have", "iam"))
                if attempt < 5 and transient:
                    time.sleep(10.0)
                    continue
                raise

        ext_desc = str(unstructured.get("extraction_table_description") or "").strip()
        ext_col_descs = unstructured.get("extraction_column_descriptions") or {}
        if ext_desc or (isinstance(ext_col_descs, Mapping) and ext_col_descs):
            ext_tbl_ref = bq.get_table(f"{project_id}.{dataset_id}.{extracted_tbl}")
            update_fields: list[str] = []
            if ext_desc and getattr(ext_tbl_ref, "description", None) != ext_desc:
                ext_tbl_ref.description = ext_desc
                update_fields.append("description")
            if isinstance(ext_col_descs, Mapping) and ext_col_descs and getattr(ext_tbl_ref, "schema", None):
                new_schema = []
                schema_changed = False
                for field in ext_tbl_ref.schema:
                    col_desc = str(ext_col_descs.get(field.name) or "").strip()
                    if col_desc and getattr(field, "description", None) != col_desc:
                        schema_changed = True
                        if hasattr(field, "to_api_repr") and hasattr(bigquery.SchemaField, "from_api_repr"):
                            api_repr = field.to_api_repr()
                            api_repr["description"] = col_desc
                            new_schema.append(bigquery.SchemaField.from_api_repr(api_repr))
                        else:
                            new_schema.append(
                                bigquery.SchemaField(
                                    field.name,
                                    field.field_type,
                                    mode=field.mode,
                                    description=col_desc,
                                    fields=field.fields,
                                )
                            )
                    else:
                        new_schema.append(field)
                if schema_changed:
                    ext_tbl_ref.schema = new_schema
                    update_fields.append("schema")
            if update_fields:
                bq.update_table(ext_tbl_ref, update_fields)

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
                if isinstance(expected_v, str):
                    if actual_v is None or str(actual_v).strip().lower() != expected_v.strip().lower():
                        raise RuntimeError(
                            f"AI.GENERATE invariant mismatch on {extracted_tbl}.{k}: expected {expected_v!r}, got {actual_v!r}"
                        )
                elif isinstance(expected_v, bool):
                    if bool(actual_v) is not expected_v:
                        raise RuntimeError(
                            f"AI.GENERATE invariant mismatch on {extracted_tbl}.{k}: expected {expected_v}, got {actual_v}"
                        )
                elif actual_v is None or abs(float(actual_v) - float(expected_v)) > 1e-4:
                    raise RuntimeError(
                        f"AI.GENERATE invariant mismatch on {extracted_tbl}.{k}: expected {expected_v}, got {actual_v}"
                    )

    # Step (g): Concurrent Data Profile + Data Insights DataScans and Native Knowledge Catalog Data Products.
    concurrent_scans: list[tuple[Mapping[str, Any], str, dict[str, Any]]] = []
    for scan_spec in plan.get("data_profile_scans") or []:
        prof_sampling = (
            float(scan_spec["sampling_percent"])
            if scan_spec.get("sampling_percent") is not None
            else 100.0
        )
        concurrent_scans.append(
            (
                scan_spec,
                "dataProfileSpec",
                {
                    "samplingPercent": prof_sampling,
                    "catalogPublishingEnabled": bool(scan_spec.get("catalog_publishing_enabled", True)),
                },
            )
        )
    for scan_spec in plan.get("data_documentation_scans") or []:
        concurrent_scans.append(
            (
                scan_spec,
                "dataDocumentationSpec",
                {
                    "catalogPublishingEnabled": bool(scan_spec.get("catalog_publishing_enabled", True)),
                },
            )
        )
    if concurrent_scans:
        scan_errors: list[str] = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            fut_to_id = {
                pool.submit(_provision_and_run_scan, s_spec, spec_key=s_key, spec_payload=s_payload): str(
                    s_spec.get("scan_id") or s_spec["data_scan_id"]
                )
                for s_spec, s_key, s_payload in concurrent_scans
            }
            for fut in as_completed(fut_to_id):
                s_id = fut_to_id[fut]
                try:
                    fut.result()
                except Exception as err:
                    scan_errors.append(f"{s_id}: {err}")
        if scan_errors:
            raise RuntimeError(
                "One or more DataScan runs failed: " + "; ".join(sorted(scan_errors))
            )

    for dp_spec in plan.get("data_products") or []:
        dp_id = str(dp_spec.get("data_product_id") or dp_spec["id"])
        raw_owners = [str(e).strip() for e in (dp_spec.get("owner_emails") or []) if str(e).strip()]
        if raw_owners:
            owner_emails = raw_owners
        elif active_caller and "@" in active_caller:
            owner_emails = [active_caller]
        else:
            raise RuntimeError(
                f"Cannot provision DataProduct {dp_id!r}: owner_emails not provided and active gcloud account unavailable."
            )

        dp_payload = {
            "displayName": str(dp_spec.get("display_name") or dp_id),
            "description": str(dp_spec.get("description") or ""),
            "ownerEmails": owner_emails,
        }
        dp_create_url = (
            f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}"
            f"/dataProducts?dataProductId={quote(dp_id)}"
        )
        st_dp, dp_resp = rest.request("POST", dp_create_url, payload=dp_payload, allow_statuses=(200, 201, 400, 409))
        if _is_already_exists_error(st_dp, dp_resp):
            if raw_owners:
                patch_mask = "displayName,description,ownerEmails"
                patch_payload = dp_payload
            else:
                patch_mask = "displayName,description"
                patch_payload = {
                    "displayName": dp_payload["displayName"],
                    "description": dp_payload["description"],
                }
            _, upd_dp = rest.request(
                "PATCH",
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataProducts/{quote(dp_id)}?updateMask={patch_mask}",
                payload=patch_payload,
                allow_statuses=(200,),
            )
            rest.wait_lro(upd_dp)
        elif st_dp == 400:
            raise RuntimeError(f"HTTP 400 for POST {dp_create_url}: {json.dumps(dp_resp)[:500]}")
        else:
            rest.wait_lro(dp_resp)

        for asset in dp_spec.get("assets") or []:
            asset_id = str(asset["asset_id"])
            asset_tbl = str(asset["table"])
            asset_url = (
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}"
                f"/dataProducts/{quote(dp_id)}/dataAssets?dataAssetId={quote(asset_id)}"
            )
            asset_payload = {
                "resource": f"//bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{asset_tbl}"
            }
            st_a, a_resp = rest.request("POST", asset_url, payload=asset_payload, allow_statuses=(200, 201, 400, 409))
            if _is_already_exists_error(st_a, a_resp):
                continue
            if st_a == 400:
                raise RuntimeError(f"HTTP 400 for POST {asset_url}: {json.dumps(a_resp)[:500]}")
            rest.wait_lro(a_resp)

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
            for link_spec in _iter_term_column_links(term):
                link_id = link_spec["entry_link_id"]
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

    # 2. DataScans (Quality, Profile, Documentation)
    for scan_list_key in ("data_quality_scans", "data_profile_scans", "data_documentation_scans"):
        for scan in plan.get(scan_list_key) or []:
            scan_id = str(scan.get("scan_id") or scan["data_scan_id"])
            ds_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataScans/{quote(scan_id)}?force=true"
            st, resp = rest.request("DELETE", ds_url, allow_statuses=(200, 202, 204, 404))
            if st != 404 and isinstance(resp, dict):
                rest.wait_lro(resp)
            deleted_steps.append(f"dataScan:{scan_id}")

    # 3. Detach Entry Aspects -> Delete AspectTypes
    aspect_types = list(plan.get("aspect_types") or [])
    proj_num_for_aspects = ""
    if aspect_types:
        try:
            proj_num_for_aspects = _resolve_project_number(project_id)
        except Exception:
            proj_num_for_aspects = ""

    for aspect_spec in aspect_types:
        at_id = str(aspect_spec["aspect_type_id"])
        aspect_key = f"{proj_num_for_aspects or project_id}.{bq_location}.{at_id}"
        for attach in (aspect_spec.get("assignments") or aspect_spec.get("attachments") or []):
            tbl_id = str(attach.get("table") or attach["table_id"])
            entry_name = (
                f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery/entries/"
                f"bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/{tbl_id}"
            )
            detach_url = f"{_DATAPLEX_BASE}/{entry_name}?updateMask=aspects&aspectKeys={quote(aspect_key)}"
            try:
                rest.request("PATCH", detach_url, payload={"aspects": {}}, allow_statuses=(200, 400, 403, 404))
            except Exception as err:
                print(
                    f"WARNING: Could not detach aspect {aspect_key} from {tbl_id}: {err}",
                    file=sys.stderr,
                )

        at_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/aspectTypes/{quote(at_id)}"
        st, resp = rest.request("DELETE", at_url, allow_statuses=(200, 202, 204, 400, 404, 409))
        if st in (400, 409):
            print(
                f"WARNING: Could not delete aspectType {at_id} (HTTP {st}); continuing teardown: {resp}",
                file=sys.stderr,
            )
        else:
            if st != 404 and isinstance(resp, dict):
                rest.wait_lro(resp)
            deleted_steps.append(f"aspectType:{at_id}")

    # 3b. DataProducts (delete child DataAssets BEFORE parent DataProduct)
    for dp_spec in plan.get("data_products") or []:
        dp_id = str(dp_spec.get("data_product_id") or dp_spec["id"])
        for asset in dp_spec.get("assets") or []:
            asset_id = str(asset["asset_id"])
            asset_url = (
                f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}"
                f"/dataProducts/{quote(dp_id)}/dataAssets/{quote(asset_id)}"
            )
            st_a, resp_a = rest.request("DELETE", asset_url, allow_statuses=(200, 202, 204, 404))
            if st_a != 404 and isinstance(resp_a, dict):
                rest.wait_lro(resp_a)
            deleted_steps.append(f"dataAsset:{dp_id}/{asset_id}")

        dp_url = f"{_DATAPLEX_BASE}/projects/{project_id}/locations/{bq_location}/dataProducts/{quote(dp_id)}"
        st_dp, resp_dp = rest.request("DELETE", dp_url, allow_statuses=(200, 202, 204, 404))
        if st_dp != 404 and isinstance(resp_dp, dict):
            rest.wait_lro(resp_dp)
        deleted_steps.append(f"dataProduct:{dp_id}")

    # 4. Object Table / Extracted SLA Overlay -> Connection SA IAM -> BigQuery Connection
    unstructured = dict(plan.get("unstructured_contracts") or {})
    seen_del_tbls: set[str] = set()
    for tbl_key in ("extraction_staging_table", "target_table", "object_table"):
        tbl_name = str(unstructured.get(tbl_key) or "").strip()
        if tbl_name and tbl_name not in seen_del_tbls:
            seen_del_tbls.add(tbl_name)
            bq.delete_table(f"{project_id}.{dataset_id}.{tbl_name}", not_found_ok=True)
            deleted_steps.append(f"table:{dataset_id}.{tbl_name}")

    conn_url = f"{_BQ_CONN_BASE}/projects/{project_id}/locations/{bq_location}/connections/{quote(connection_id)}"
    st_conn_get, conn_info = rest.request("GET", conn_url, allow_statuses=(200, 404))
    if st_conn_get == 200 and isinstance(conn_info, Mapping):
        conn_sa = str((conn_info.get("cloudResource") or {}).get("serviceAccountId") or "").strip()
        if conn_sa:
            _run_cmd(
                [
                    "gcloud",
                    "projects",
                    "remove-iam-policy-binding",
                    project_id,
                    f"--member=serviceAccount:{conn_sa}",
                    "--role=roles/aiplatform.user",
                    "--all",
                    "--quiet",
                ],
                check=False,
            )
            deleted_steps.append(f"iam:{conn_sa}:roles/aiplatform.user")

    rest.request("DELETE", conn_url, allow_statuses=(200, 202, 204, 404))
    deleted_steps.append(f"connection:{connection_id}")

    # 5. GCS objects & bucket
    bucket_name = plan.get("bucket_name")
    if bucket_name:
        from google.api_core.exceptions import NotFound

        try:
            bucket = gcs.get_bucket(bucket_name)
        except NotFound:
            bucket = None
        if bucket is not None:
            for blob in list(bucket.list_blobs()):
                blob.delete()
            bucket.delete(force=True)
            deleted_steps.append(f"bucket:{bucket_name}")

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
                        "--all",
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
        dry_plan = dict(plan)
        if dry_plan.get("data_products"):
            dry_dps: list[dict[str, Any]] = []
            for dp in dry_plan["data_products"]:
                dp_copy = dict(dp)
                if not dp_copy.get("owner_emails"):
                    dp_copy["owner_emails"] = ["data-stewards@example.com"]
                dry_dps.append(dp_copy)
            dry_plan["data_products"] = dry_dps
        dry_summary = {
            "mode": mode,
            "dry_run": True,
            "delete_agent_sas": bool(args.delete_agent_sas),
            "plan": dry_plan,
        }
        print(json.dumps(redact_bundle_data(dry_summary, live_project_id=plan["project_id"]), indent=2))
        return 0

    if not plan["project_id"] or plan["project_id"] == "example-project-id":
        raise SystemExit("ERROR: PROJECT_ID must be set to a live GCP project ID for --live-gcp / --teardown.")

    if args.teardown:
        result = run_teardown(plan, delete_agent_sas=bool(args.delete_agent_sas))
    else:
        result = run_provision(plan)

    extra_scrub = [t for t in (plan["project_id"], os.environ.get("PROJECT_NUMBER", "")) if t]
    print(json.dumps(redact_bundle_data(result, extra_tokens=extra_scrub, live_project_id=plan["project_id"]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
