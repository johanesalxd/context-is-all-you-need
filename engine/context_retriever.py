"""Zero-trust SQL AST gate, strict SA isolation, and live Knowledge Catalog tools."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time as dt_time
from decimal import Decimal
import inspect
import json
import os
import re
import threading
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from engine.pack_loader import _strip_sql_comments
from engine.rls_impersonation import (
    build_impersonated_credentials,
    is_valid_customer_sa,
    parse_role_sa_map,
    redact_sensitive_identifiers,
    resolve_agent_sa_map,
)
from engine.trust_classifier import strip_sql_literals_and_comments

__all__ = [
    "AgentContextError",
    "AgentSqlSecurityError",
    "BlindToolContext",
    "DataplexCatalogRestClient",
    "GovernedToolContext",
    "build_impersonated_bq_client",
    "resolve_execution_sa",
    "validate_agent_sql_gate",
]

_DEFAULT_MAX_BYTES_BILLED = 104_857_600  # 100 MB
_DATAPLEX_BASE = "https://dataplex.googleapis.com/v1"
_CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
_MAX_DISCOVERY_TABLES = 25
_LOOKUP_CONTEXT_MAX_CHARS = 3600
_CATALOG_INSPECT_MAX_WORKERS = 16
_GOVERNANCE_POLICY_NOTE = (
    "Query CERTIFIED Data Products (certification_status == 'CERTIFIED') as authoritative; "
    "never query or UNION UNCERTIFIED_STALE or DEPRECATED tables—execution against them is blocked by governance policy."
)
_BLOCKED_CERTIFICATION_STATUSES = frozenset({"UNCERTIFIED_STALE", "DEPRECATED"})
_CONTRACT_STOPWORDS = frozenset(
    {
        "metric",
        "metrics",
        "table",
        "tables",
        "total",
        "value",
        "values",
        "data",
        "verified",
        "contract",
        "contracts",
        "pct",
        "rate",
        "amount",
        "margin",
        "gross",
        "net",
        "revenue",
        "order",
        "orders",
        "customer",
        "customers",
        "line",
        "lines",
        "country",
        "date",
        "tier",
        "status",
        "completed",
    }
)
_AUTO_STRUCTURAL_ASPECT_TYPES = frozenset(
    {
        "dataplex-types.global.schema",
        "dataplex-types.global.storage",
        "dataplex-types.global.bigquery-table",
        "dataplex-types.global.bigquery-view",
        "dataplex-types.global.bigquery-dataset",
        "dataplex-types.global.bigquery-routine",
        "dataplex-types.global.bigquery-model",
    }
)


class AgentContextError(RuntimeError):
    """Raised when Knowledge Catalog lookup or tool configuration fails."""


class AgentSqlSecurityError(ValueError):
    """Raised when an agent SQL/GQL query fails the zero-trust dry-run gate."""


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, Mapping):
        return {str(k): _json_safe_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe_value(v) for v in value]
    return str(value)


def _rows_to_json_safe(rows: Iterable[Any], *, max_rows: int = 50) -> tuple[list[dict[str, Any]], int]:
    collected: list[dict[str, Any]] = []
    total = 0
    for row in rows:
        total += 1
        if len(collected) < max_rows:
            if isinstance(row, Mapping):
                collected.append({str(k): _json_safe_value(v) for k, v in row.items()})
            elif hasattr(row, "items"):
                collected.append({str(k): _json_safe_value(v) for k, v in row.items()})
            elif hasattr(row, "keys"):
                collected.append({str(k): _json_safe_value(row[k]) for k in row.keys()})
            else:
                collected.append({"value": _json_safe_value(row)})
    return collected, total


def _extract_table_leaf(raw_name: str, *, allowed_dataset_id: str) -> str:
    cleaned = raw_name.strip().strip("`\"")
    if not cleaned:
        raise AgentSqlSecurityError("Table name cannot be empty.")
    parts = [p.strip("`\"") for p in cleaned.split(".") if p.strip("`\"")]
    if len(parts) == 1:
        table_leaf = parts[0]
    elif len(parts) == 2:
        ds, table_leaf = parts
        if ds != allowed_dataset_id:
            raise AgentSqlSecurityError(
                f"Cross-dataset table reference {raw_name!r} rejected; only {allowed_dataset_id!r} is allowed."
            )
    elif len(parts) == 3:
        _, ds, table_leaf = parts
        if ds != allowed_dataset_id:
            raise AgentSqlSecurityError(
                f"Cross-dataset table reference {raw_name!r} rejected; only {allowed_dataset_id!r} is allowed."
            )
    else:
        raise AgentSqlSecurityError(f"Invalid table identifier: {raw_name!r}")

    if not re.match(r"^[A-Za-z0-9_$-]+$", table_leaf):
        raise AgentSqlSecurityError(f"Unsafe table identifier: {raw_name!r}")
    return table_leaf


def _check_sql_text_pre_gate(
    sql: str,
    *,
    allowed_dataset_id: str,
    forbidden_datasets: Iterable[str] | None = None,
) -> None:
    if not isinstance(sql, str) or not sql.strip():
        raise AgentSqlSecurityError("SQL query must be a non-empty string.")

    statements = _strip_sql_comments(sql)
    if len(statements) != 1:
        raise AgentSqlSecurityError(
            f"Multi-statement or empty SQL blocked by security gate (got {len(statements)} statements)."
        )

    stripped_code = strip_sql_literals_and_comments(sql)
    if re.search(r"\bINFORMATION_SCHEMA\b", stripped_code, flags=re.IGNORECASE):
        raise AgentSqlSecurityError("INFORMATION_SCHEMA queries are blocked by zero-trust gate.")

    if re.search(r"\bEXTERNAL_QUERY\b", stripped_code, flags=re.IGNORECASE):
        raise AgentSqlSecurityError("EXTERNAL_QUERY calls are blocked by zero-trust gate.")

    if forbidden_datasets:
        for forbidden_ds in forbidden_datasets:
            ds = str(forbidden_ds or "").strip()
            if ds and ds != allowed_dataset_id:
                pattern = rf"(?<![A-Za-z0-9_]){re.escape(ds)}(?![A-Za-z0-9_])\s*\."
                if re.search(pattern, stripped_code, flags=re.IGNORECASE):
                    raise AgentSqlSecurityError(
                        f"Query references unauthorized dataset {ds!r}; only {allowed_dataset_id!r} is permitted."
                    )


def validate_agent_sql_gate(
    bq_client: Any,
    sql: str,
    *,
    allowed_project_id: str,
    allowed_dataset_id: str,
    forbidden_datasets: Iterable[str] | None = None,
    max_bytes: int = _DEFAULT_MAX_BYTES_BILLED,
    location: str = "asia-southeast1",
) -> dict[str, Any]:
    """Enforces mandatory BigQuery dry-run=True AST validation before any SQL execution."""
    if bq_client is None:
        raise AgentContextError("BigQuery client is required for SQL validation gate.")

    _check_sql_text_pre_gate(
        sql,
        allowed_dataset_id=allowed_dataset_id,
        forbidden_datasets=forbidden_datasets,
    )

    from google.cloud import bigquery

    dry_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    try:
        dry_job = bq_client.query(sql, job_config=dry_config, location=location)
    except Exception as err:
        raise AgentSqlSecurityError(f"BigQuery dry_run rejected SQL: {err}") from err

    stmt_type = str(getattr(dry_job, "statement_type", "") or "").upper()
    if stmt_type != "SELECT":
        raise AgentSqlSecurityError(
            f"Only SELECT statements are permitted; dry_run reported statement_type={stmt_type!r}."
        )

    bytes_processed = int(getattr(dry_job, "total_bytes_processed", 0) or 0)
    if bytes_processed > max_bytes:
        raise AgentSqlSecurityError(
            f"Query estimated {bytes_processed} bytes exceeds limit {max_bytes} bytes."
        )

    referenced_tables = list(getattr(dry_job, "referenced_tables", None) or [])
    if not referenced_tables:
        raise AgentSqlSecurityError(
            "Query must reference at least one physical table (empty referenced_tables blocked)."
        )

    normalized_refs: list[str] = []
    for ref in referenced_tables:
        ref_project = str(getattr(ref, "project", "") or "").strip()
        ref_dataset = str(getattr(ref, "dataset_id", "") or "").strip()
        ref_table = str(getattr(ref, "table_id", "") or "").strip()
        if ref_project != allowed_project_id or ref_dataset != allowed_dataset_id:
            raise AgentSqlSecurityError(
                f"Unauthorized table reference {ref_project}.{ref_dataset}.{ref_table}; "
                f"expected {allowed_project_id}.{allowed_dataset_id}.*"
            )
        normalized_refs.append(f"{ref_project}.{ref_dataset}.{ref_table}")

    return {
        "statement_type": stmt_type,
        "total_bytes_processed": bytes_processed,
        "referenced_tables": sorted(set(normalized_refs)),
    }


def resolve_execution_sa(
    *,
    arm: str,
    project_id: str,
    pack_id: str = "",
    persona_id: str | None = None,
    context_layer: Mapping[str, Any] | None = None,
    agent_sa_map: Mapping[str, str] | None = None,
    role_sa_map: Mapping[str, str] | None = None,
) -> str:
    """Resolves exact execution SA email enforcing zero web-runner SQL and Blind/Governed isolation."""
    resolved_agent_sas = (
        dict(agent_sa_map)
        if agent_sa_map is not None
        else resolve_agent_sa_map(
            project_id=project_id,
            pack_id=pack_id,
            context_layer=context_layer,
        )
    )
    if arm == "blind":
        target_sa = resolved_agent_sas["blind"]
    elif arm == "governed":
        target_sa = resolved_agent_sas["governed"]
        effective_role_map: dict[str, str] = {}
        if role_sa_map is not None:
            effective_role_map = dict(role_sa_map)
        else:
            raw_role_map = os.environ.get("SQL_ROLE_SA_MAP_JSON", "").strip()
            if raw_role_map:
                effective_role_map = parse_role_sa_map(raw_role_map)
        if persona_id and persona_id in effective_role_map:
            candidate_sa = effective_role_map[persona_id].strip()
            if "web-runner" in candidate_sa.lower():
                raise AgentSqlSecurityError(
                    f"Persona {persona_id!r} cannot map to web-runner SA: {candidate_sa!r}"
                )
            target_sa = candidate_sa
    else:
        raise ValueError(f"Unsupported arm {arm!r}; expected 'blind' or 'governed'.")

    if "web-runner" in target_sa.lower() or not is_valid_customer_sa(target_sa):
        raise AgentSqlSecurityError(f"Unsafe or invalid execution SA resolved: {target_sa!r}")
    return target_sa


def build_impersonated_credentials_for_sa(
    target_sa: str,
    *,
    source_credentials: Any = None,
    lifetime_seconds: int = 300,
) -> Any:
    """Builds short-lived OAuth2 impersonated credentials for an allowlisted customer SA."""
    if "web-runner" in target_sa.lower():
        raise AgentSqlSecurityError(f"Refusing to impersonate web-runner SA: {target_sa!r}")
    creds, _ = build_impersonated_credentials(
        role="target",
        role_sa_map={"target": target_sa},
        target_scopes=(_CLOUD_PLATFORM_SCOPE,),
        lifetime_seconds=lifetime_seconds,
        source_credentials=source_credentials,
    )
    return creds


def build_impersonated_bq_client(
    *,
    target_sa: str,
    project_id: str,
    location: str,
    source_credentials: Any = None,
) -> Any:
    """Builds a BigQuery client authenticated as the impersonated customer SA."""
    from google.cloud import bigquery

    creds = build_impersonated_credentials_for_sa(
        target_sa,
        source_credentials=source_credentials,
    )
    return bigquery.Client(project=project_id, credentials=creds, location=location)


class DataplexCatalogRestClient:
    """Thin REST client for Dataplex Knowledge Catalog using impersonated SA bearer tokens."""

    def __init__(
        self,
        *,
        project_id: str,
        bq_location: str,
        credentials: Any = None,
        http_transport: Callable[[str, str, dict[str, Any] | None, dict[str, str]], dict[str, Any]]
        | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self.project_id = project_id
        self.bq_location = bq_location
        self.credentials = credentials
        self._http_transport = http_transport
        self.timeout_s = timeout_s
        self._token_lock = threading.Lock()
        self._session: Any = None
        if http_transport is None:
            try:
                import requests
                from requests.adapters import HTTPAdapter

                session = requests.Session()
                adapter = HTTPAdapter(
                    pool_connections=_CATALOG_INSPECT_MAX_WORKERS + 6,
                    pool_maxsize=_CATALOG_INSPECT_MAX_WORKERS + 6,
                )
                session.mount("https://", adapter)
                session.mount("http://", adapter)
                self._session = session
            except ImportError:
                self._session = None

    def _bearer_token(self) -> str:
        if self.credentials is None:
            raise AgentContextError("Impersonated credentials are required for Knowledge Catalog REST calls.")
        from google.auth.transport.requests import Request as GoogleAuthRequest

        with self._token_lock:
            if not getattr(self.credentials, "valid", False) or not getattr(self.credentials, "token", None):
                self.credentials.refresh(GoogleAuthRequest())
            token = str(getattr(self.credentials, "token", "") or "").strip()
        if not token:
            raise AgentContextError("Failed to obtain bearer token from impersonated credentials.")
        return token

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"

        if self._http_transport is not None:
            return self._http_transport(method, url, payload, headers)

        headers["Authorization"] = f"Bearer {self._bearer_token()}"
        if self._session is not None:
            try:
                import requests

                resp = self._session.request(
                    method,
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout_s,
                )
                if resp.status_code >= 400:
                    safe_url = redact_sensitive_identifiers(url, live_project_id=self.project_id)
                    safe_body = redact_sensitive_identifiers(resp.text, live_project_id=self.project_id)
                    raise AgentContextError(
                        f"Knowledge Catalog HTTP {resp.status_code} for {method} {safe_url}: {safe_body[:400]}"
                    )
                return resp.json() if resp.text.strip() else {}
            except AgentContextError:
                raise
            except requests.RequestException as err:
                safe_err = redact_sensitive_identifiers(str(err), live_project_id=self.project_id)
                safe_url = redact_sensitive_identifiers(url, live_project_id=self.project_id)
                raise AgentContextError(f"Knowledge Catalog transport error for {safe_url}: {safe_err}") from err

        body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace") if err.fp else ""
            safe_url = redact_sensitive_identifiers(url, live_project_id=self.project_id)
            safe_body = redact_sensitive_identifiers(err_body, live_project_id=self.project_id)
            raise AgentContextError(
                f"Knowledge Catalog HTTP {err.code} for {method} {safe_url}: {safe_body[:400]}"
            ) from err
        except URLError as err:
            safe_err = redact_sensitive_identifiers(str(err), live_project_id=self.project_id)
            safe_url = redact_sensitive_identifiers(url, live_project_id=self.project_id)
            raise AgentContextError(f"Knowledge Catalog transport error for {safe_url}: {safe_err}") from err

    def search_entries(
        self,
        query: str,
        *,
        page_size: int = 50,
        max_pages: int = 1,
    ) -> list[dict[str, Any]]:
        url = f"{_DATAPLEX_BASE}/projects/{self.project_id}/locations/global:searchEntries"
        all_results: list[dict[str, Any]] = []
        page_token = ""
        seen_tokens: set[str] = set()
        effective_size = min(max(1, page_size), 100)
        for _ in range(max(1, max_pages)):
            req_payload: dict[str, Any] = {"query": query, "pageSize": effective_size}
            if page_token:
                req_payload["pageToken"] = page_token
            resp = self._request_json("POST", url, payload=req_payload)
            all_results.extend(list(resp.get("results") or []))
            next_token = str(resp.get("nextPageToken") or "").strip()
            if not next_token or next_token in seen_tokens:
                break
            seen_tokens.add(next_token)
            page_token = next_token
        return all_results

    def lookup_entry(self, entry_name: str, *, view: str = "ALL") -> dict[str, Any]:
        url = (
            f"{_DATAPLEX_BASE}/projects/{self.project_id}/locations/{self.bq_location}:lookupEntry"
            f"?entry={quote(entry_name, safe='/:@')}&view={quote(view)}"
        )
        return self._request_json("GET", url)

    def lookup_context(self, resources: Sequence[str]) -> str:
        url = f"{_DATAPLEX_BASE}/projects/{self.project_id}/locations/{self.bq_location}:lookupContext"
        resp = self._request_json(
            "POST",
            url,
            payload={"resources": list(resources)},
        )
        return str(resp.get("context") or "")

    def lookup_entry_links(self, entry_name: str) -> list[dict[str, Any]]:
        url = (
            f"{_DATAPLEX_BASE}/projects/{self.project_id}/locations/{self.bq_location}:lookupEntryLinks"
            f"?entry={quote(entry_name, safe='/:@')}"
        )
        resp = self._request_json("GET", url)
        return list(resp.get("entryLinks") or [])

    def get_glossary_term(self, term_resource_name: str) -> dict[str, Any]:
        clean = term_resource_name.strip().lstrip("/")
        if "/entryGroups/@dataplex/entries/" in clean:
            clean = clean.split("/entryGroups/@dataplex/entries/", 1)[1]
        url = f"{_DATAPLEX_BASE}/{clean}"
        return self._request_json("GET", url)


def _await_bq_job_result(job: Any, timeout_s: float | None = None) -> list[Any]:
    """Waits for a BigQuery job respecting timeout_s and cancelling timed-out jobs."""
    if timeout_s is None:
        return list(job.result())
    eff_timeout = max(0.5, float(timeout_s))
    result_fn = getattr(job, "result")
    supports_timeout = False
    try:
        sig = inspect.signature(result_fn)
        supports_timeout = (
            "timeout" in sig.parameters
            or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
        )
    except (TypeError, ValueError):
        supports_timeout = False

    if not supports_timeout:
        return list(result_fn())
    try:
        return list(result_fn(timeout=eff_timeout))
    except Exception as err:
        msg = str(err).lower()
        is_timeout = isinstance(err, TimeoutError) or "timeout" in type(err).__name__.lower() or "timed out" in msg
        if is_timeout:
            cancel_fn = getattr(job, "cancel", None)
            if callable(cancel_fn):
                try:
                    cancel_fn()
                except Exception:
                    pass
            raise TimeoutError(f"BigQuery job exceeded {eff_timeout:.1f}s timeout: {err}") from err
        raise


class BlindToolContext:
    """Strictly raw, unannotated tool suite restricted to the Blind dataset."""

    def __init__(
        self,
        *,
        project_id: str,
        blind_dataset_id: str,
        governed_dataset_id: str,
        bq_location: str,
        bq_client: Any,
        sa_email: str,
        max_bytes: int = _DEFAULT_MAX_BYTES_BILLED,
    ) -> None:
        self.project_id = project_id
        self.blind_dataset_id = blind_dataset_id
        self.forbidden_datasets = (governed_dataset_id,) if governed_dataset_id != blind_dataset_id else ()
        self.bq_location = bq_location
        self.bq_client = bq_client
        self.sa_email = sa_email
        self.max_bytes = max_bytes

    def list_tables(self, pattern: str = "", limit: int = 250) -> dict[str, Any]:
        dataset_ref = f"{self.project_id}.{self.blind_dataset_id}"
        all_names = sorted(str(tbl.table_id) for tbl in self.bq_client.list_tables(dataset_ref))
        pat = (pattern or "").strip().lower()
        filtered = [name for name in all_names if pat in name.lower()] if pat else all_names
        capped = max(1, min(int(limit or 250), 250))
        return {
            "dataset_id": self.blind_dataset_id,
            "total_tables": len(all_names),
            "matched_tables": len(filtered),
            "truncated": len(filtered) > capped,
            "tables": filtered[:capped],
            "note": "Raw table inventory only; zero descriptions, semantic contracts, or catalog certification metadata exist here.",
        }

    def get_table_ddl(self, table_name: str) -> dict[str, Any]:
        leaf = _extract_table_leaf(table_name, allowed_dataset_id=self.blind_dataset_id)
        table_ref = f"{self.project_id}.{self.blind_dataset_id}.{leaf}"
        table_obj = self.bq_client.get_table(table_ref)
        cols = [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": getattr(field, "mode", "NULLABLE"),
            }
            for field in (getattr(table_obj, "schema", None) or [])
        ]
        return {
            "table_name": f"{self.blind_dataset_id}.{leaf}",
            "columns": cols,
            "description": None,
            "constraints": None,
            "num_rows": getattr(table_obj, "num_rows", None),
        }

    def execute_select_sql(self, sql: str, *, timeout_s: float | None = None) -> dict[str, Any]:
        gate = validate_agent_sql_gate(
            self.bq_client,
            sql,
            allowed_project_id=self.project_id,
            allowed_dataset_id=self.blind_dataset_id,
            forbidden_datasets=self.forbidden_datasets,
            max_bytes=self.max_bytes,
            location=self.bq_location,
        )
        from google.cloud import bigquery

        run_cfg = bigquery.QueryJobConfig(
            use_query_cache=False,
            maximum_bytes_billed=self.max_bytes,
        )
        job = self.bq_client.query(sql, job_config=run_cfg, location=self.bq_location)
        rows_raw = _await_bq_job_result(job, timeout_s=timeout_s)
        rows_preview, row_count = _rows_to_json_safe(rows_raw, max_rows=50)
        return {
            "rows": rows_preview,
            "row_count": row_count,
            "bytes_billed": int(getattr(job, "total_bytes_billed", 0) or gate["total_bytes_processed"]),
            "referenced_tables": gate["referenced_tables"],
            "statement_type": gate["statement_type"],
            "executed_as_sa": self.sa_email,
        }


class GovernedToolContext:
    """Governed Knowledge Catalog + Semantic Contract + RLS-enforced SQL tool suite."""

    def __init__(
        self,
        *,
        project_id: str,
        dataset_id: str,
        blind_dataset_id: str,
        bq_location: str,
        metadata_bq_client: Any,
        sql_bq_client: Any,
        metadata_sa_email: str,
        sql_sa_email: str,
        catalog_client: DataplexCatalogRestClient,
        context_layer: Mapping[str, Any] | None = None,
        max_bytes: int = _DEFAULT_MAX_BYTES_BILLED,
    ) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.forbidden_datasets = (blind_dataset_id,) if blind_dataset_id != dataset_id else ()
        self.bq_location = bq_location
        self.metadata_bq_client = metadata_bq_client
        self.sql_bq_client = sql_bq_client
        self.metadata_sa_email = metadata_sa_email
        self.sql_sa_email = sql_sa_email
        self.catalog_client = catalog_client
        self.context_layer = dict(context_layer or {})
        self.max_bytes = max_bytes
        self._cert_lock = threading.Lock()
        self._table_cert_cache: dict[str, str] = {}
        self._known_tables_cache: set[str] | None = None

    def _cache_table_certification(self, table_leaf: str, cert_status: str) -> None:
        cleaned = str(cert_status or "UNTAGGED").strip().upper() or "UNTAGGED"
        with self._cert_lock:
            self._table_cert_cache[table_leaf] = cleaned

    def _known_table_names(self) -> set[str]:
        with self._cert_lock:
            if self._known_tables_cache is not None:
                return set(self._known_tables_cache)
        try:
            dataset_ref = f"{self.project_id}.{self.dataset_id}"
            names = {str(tbl.table_id) for tbl in self.metadata_bq_client.list_tables(dataset_ref)}
        except Exception:
            names = set()
        if names:
            with self._cert_lock:
                self._known_tables_cache = set(names)
        return names

    @staticmethod
    def _extract_certification_status(aspects_summary: Mapping[str, Any]) -> str:
        cert_info = aspects_summary.get("certification")
        if isinstance(cert_info, Mapping):
            status = str(cert_info.get("certification_status") or "").strip().upper()
            if status:
                return status
        return "UNTAGGED"

    def _entry_name(self, table_leaf: str) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.bq_location}/entryGroups/@bigquery/entries/"
            f"bigquery.googleapis.com/projects/{self.project_id}/datasets/{self.dataset_id}/tables/{table_leaf}"
        )

    @staticmethod
    def _has_curated_aspects(aspects: Any) -> bool:
        if not isinstance(aspects, Mapping):
            return False
        for aspect_key, aspect_val in aspects.items():
            if not isinstance(aspect_val, Mapping):
                continue
            key_low = str(aspect_key).strip().lower()
            if any(
                key_low == sys_type or key_low.endswith(f"/{sys_type}") or sys_type in key_low
                for sys_type in _AUTO_STRUCTURAL_ASPECT_TYPES
            ):
                continue
            if "dataplex-types.global.overview" in key_low:
                data = aspect_val.get("data")
                if isinstance(data, Mapping) and str(data.get("content") or "").strip():
                    return True
                continue
            return True
        return False

    @classmethod
    def _extract_aspects_summary(cls, entry_payload: Mapping[str, Any]) -> dict[str, Any]:
        aspects = entry_payload.get("aspects")
        if not isinstance(aspects, Mapping):
            return {}
        summary: dict[str, Any] = {}
        if cls._has_curated_aspects(aspects):
            summary["has_curated_aspect"] = True
        for aspect_key, aspect_val in aspects.items():
            if not isinstance(aspect_val, Mapping):
                continue
            data = aspect_val.get("data")
            key_lower = str(aspect_key).lower()
            if "certification" in key_lower and isinstance(data, Mapping):
                summary["certification"] = dict(data)
            elif "data-quality" in key_lower or "dq" in key_lower or "dataplex-types.global.data-quality" in key_lower:
                if isinstance(data, Mapping):
                    summary["data_quality"] = {
                        k: data[k]
                        for k in ("score", "passed", "rowCount", "scannedTime")
                        if k in data
                    } or dict(data)
            elif "schema" in key_lower and isinstance(data, Mapping):
                summary["schema_aspect"] = data
        return summary

    def _fetch_bq_table_safe(self, table_ref: str) -> Any:
        try:
            return self.metadata_bq_client.get_table(table_ref)
        except Exception:
            return None

    def _inspect_discovery_table(
        self,
        tbl_leaf: str,
        *,
        tbl_obj: Any,
        kc_hint: Mapping[str, Any],
        inspect_dataplex: bool,
    ) -> dict[str, Any] | None:
        entry_name = self._entry_name(tbl_leaf)
        aspect_summary: dict[str, Any] = {}
        kc_error: str | None = None
        has_glossary_link = False

        bq_description = str(getattr(tbl_obj, "description", "") or "").strip() if tbl_obj is not None else ""
        kc_desc = str(kc_hint.get("entry_desc") or "").strip()
        effective_desc = bq_description or kc_desc
        column_names = (
            [f.name for f in (getattr(tbl_obj, "schema", None) or [])]
            if tbl_obj is not None
            else []
        )

        if inspect_dataplex:
            try:
                looked = self.catalog_client.lookup_entry(entry_name, view="ALL")
                aspect_summary = self._extract_aspects_summary(looked)
            except AgentContextError as err:
                kc_error = str(err)

            cert = aspect_summary.get("certification") or {}
            cert_status = self._extract_certification_status(aspect_summary)
            if kc_error is None:
                self._cache_table_certification(tbl_leaf, cert_status)
            has_curated_aspect = (
                bool(aspect_summary.get("has_curated_aspect"))
                if kc_error is None
                else bool(kc_hint.get("has_curated_aspect"))
            )
            if cert_status != "CERTIFIED" and not has_curated_aspect and not effective_desc:
                try:
                    links = self.catalog_client.lookup_entry_links(entry_name)
                    has_glossary_link = bool(links)
                except AgentContextError:
                    has_glossary_link = False
        else:
            cert = {}
            cert_status = "UNTAGGED"
            has_curated_aspect = bool(kc_hint.get("has_curated_aspect"))

        is_curated = (
            cert_status == "CERTIFIED"
            or has_curated_aspect
            or has_glossary_link
            or bool(effective_desc)
        )
        if not is_curated:
            return None

        rank = 0 if cert_status == "CERTIFIED" else (2 if "UNCERTIFIED" in cert_status or "STALE" in cert_status else 1)
        result: dict[str, Any] = {
            "table_name": f"{self.dataset_id}.{tbl_leaf}",
            "fqn": f"{self.project_id}.{self.dataset_id}.{tbl_leaf}",
            "certification_status": cert_status,
            "certification_aspect": cert,
            "data_quality": aspect_summary.get("data_quality"),
            "description": effective_desc,
            "column_names": column_names,
            "_sort_rank": rank,
            **({"catalog_note": kc_error} if kc_error else {}),
        }
        if cert_status in _BLOCKED_CERTIFICATION_STATUSES:
            result["query_blocked_by_governance_policy"] = True
        return result

    def _configured_aspect_type_ids(self) -> list[str]:
        ids: list[str] = []
        raw_aspects = self.context_layer.get("aspect_types")
        if isinstance(raw_aspects, list):
            for entry in raw_aspects:
                if isinstance(entry, Mapping):
                    aid = str(entry.get("aspect_type_id") or entry.get("id") or "").strip()
                    if aid and aid not in ids:
                        ids.append(aid)
        cert_cfg = self.context_layer.get("certification_aspect")
        if isinstance(cert_cfg, Mapping):
            aid = str(cert_cfg.get("aspect_type_id") or cert_cfg.get("id") or "").strip()
            if aid and aid not in ids:
                ids.append(aid)
        return ids

    @staticmethod
    def _tokenize_identifier_text(text: str) -> list[str]:
        tokens: list[str] = []
        seen: set[str] = set()
        for raw in re.split(r"[^A-Za-z0-9]+", text or ""):
            if len(raw) >= 2:
                low = raw.lower()
                if low not in seen:
                    seen.add(low)
                    tokens.append(low)
            for camel in re.findall(r"[A-Z]+(?=[A-Z][a-z]|[^A-Za-z]|$)|[A-Z]?[a-z]+", raw):
                if len(camel) >= 2:
                    clow = camel.lower()
                    if clow not in seen:
                        seen.add(clow)
                        tokens.append(clow)
        return tokens

    def _resolve_placeholders(self, raw: str) -> str:
        return (
            (raw or "")
            .replace("${PROJECT_ID}", self.project_id)
            .replace("${DATASET_ID}", self.dataset_id)
            .replace("${BQ_LOCATION}", self.bq_location)
        )

    def _extract_property_graphs(self, term: str, tokens: Sequence[str], *, is_wildcard: bool) -> list[dict[str, Any]]:
        contracts = self.context_layer.get("verified_metric_contracts")
        if not isinstance(contracts, Mapping):
            return []
        graphs: list[dict[str, Any]] = []
        for key, body in contracts.items():
            if not isinstance(body, Mapping) or not body.get("graph_name"):
                continue
            resolved_fqn = self._resolve_placeholders(str(body.get("graph_name") or "")).strip().strip("`")
            leaf = resolved_fqn.rsplit(".", 1)[-1] if resolved_fqn else ""
            if not leaf:
                continue
            graph_item = {
                "contract_topic": str(key),
                "graph_name": f"{self.dataset_id}.{leaf}",
                "fqn": f"{self.project_id}.{self.dataset_id}.{leaf}",
                "display_name": str(body.get("display_name") or ""),
                "description": str(body.get("description") or ""),
                "edge_chain": str(body.get("edge_chain") or ""),
            }
            if is_wildcard or not tokens:
                graphs.append(graph_item)
                continue
            haystack = " ".join(
                [
                    graph_item["contract_topic"],
                    graph_item["graph_name"],
                    graph_item["display_name"],
                    graph_item["description"],
                    graph_item["edge_chain"],
                    " ".join(str(x) for x in (body.get("node_labels") or [])),
                    " ".join(str(x) for x in (body.get("edge_labels") or [])),
                ]
            ).lower()
            if any(tok in haystack for tok in tokens):
                graphs.append(graph_item)
        return graphs

    def search_certified_tables(self, search_term: str) -> dict[str, Any]:
        term = (search_term or "").strip()
        is_wildcard = term.lower() in {"", "*", "all"}
        tokens = [t.lower() for t in re.split(r"[^A-Za-z0-9_]+", term) if len(t) >= 2]
        kc_ordered: list[str] = []
        seen_tables: set[str] = set()
        kc_hints: dict[str, dict[str, Any]] = {}
        dataset_ref = f"{self.project_id}.{self.dataset_id}"
        marker = f"/datasets/{self.dataset_id}/tables/"

        def _list_bq_tables() -> list[Any]:
            try:
                return list(self.metadata_bq_client.list_tables(dataset_ref))
            except Exception:
                return []

        if is_wildcard:
            wildcard_specs: list[tuple[str, int, int, bool]] = [
                (f"fully_qualified_name:{self.project_id}.{self.dataset_id}", 100, 3, False),
                (f"{self.dataset_id} aspect:dataplex-types.global.data-quality", 50, 1, True),
            ]
            for aid in self._configured_aspect_type_ids():
                wildcard_specs.append(
                    (
                        f"{self.dataset_id} aspect:{self.project_id}.{self.bq_location}.{aid}",
                        50,
                        1,
                        True,
                    )
                )

            def _run_search(spec: tuple[str, int, int, bool]) -> tuple[bool, list[dict[str, Any]]]:
                q, psize, mpages, is_aspect_q = spec
                try:
                    return is_aspect_q, self.catalog_client.search_entries(q, page_size=psize, max_pages=mpages)
                except AgentContextError:
                    return is_aspect_q, []

            with ThreadPoolExecutor(max_workers=len(wildcard_specs) + 1) as pool:
                fut_bq = pool.submit(_list_bq_tables)
                search_batches = list(pool.map(_run_search, wildcard_specs))
                bq_tables = fut_bq.result()
        else:
            def _search_specific() -> list[tuple[bool, list[dict[str, Any]]]]:
                queries = (
                    f"{term} fully_qualified_name:{self.project_id}.{self.dataset_id}",
                    f"{term} parent:{self.dataset_id}",
                    term,
                )
                for q in queries:
                    try:
                        hits = self.catalog_client.search_entries(q, page_size=50, max_pages=1)
                    except AgentContextError:
                        hits = []
                    filtered_hits = [
                        h
                        for h in hits
                        if marker in str(h.get("linkedResource") or "")
                        or marker in str((h.get("dataplexEntry") or {}).get("name") or "")
                    ]
                    if filtered_hits:
                        return [(False, filtered_hits)]
                return []

            with ThreadPoolExecutor(max_workers=2) as pool:
                fut_bq = pool.submit(_list_bq_tables)
                fut_kc = pool.submit(_search_specific)
                bq_tables = fut_bq.result()
                search_batches = fut_kc.result()

        for is_aspect_q, hits in search_batches:
            for hit in hits:
                linked = str(hit.get("linkedResource") or "")
                dp_entry = hit.get("dataplexEntry") or {}
                entry_name = str(dp_entry.get("name") or "")
                if marker not in linked and marker not in entry_name:
                    continue
                if "/tables/" not in entry_name:
                    continue
                table_leaf = entry_name.rsplit("/tables/", 1)[-1].split("/", 1)[0]
                if not table_leaf:
                    continue
                entry_source = dp_entry.get("entrySource") if isinstance(dp_entry, Mapping) else {}
                entry_desc = str(entry_source.get("description") or "").strip() if isinstance(entry_source, Mapping) else ""
                has_aspect = is_aspect_q or self._has_curated_aspects(dp_entry.get("aspects") if isinstance(dp_entry, Mapping) else None)
                hint = kc_hints.setdefault(table_leaf, {"entry_desc": "", "has_curated_aspect": False})
                if entry_desc and not hint["entry_desc"]:
                    hint["entry_desc"] = entry_desc
                if has_aspect:
                    hint["has_curated_aspect"] = True
                if table_leaf not in seen_tables:
                    seen_tables.add(table_leaf)
                    kc_ordered.append(table_leaf)

        bq_fallback: list[str] = []
        unmatched_leaves: list[str] = []
        for tbl_item in bq_tables:
            tbl_leaf = str(tbl_item.table_id)
            if tbl_leaf in seen_tables:
                continue
            if is_wildcard or not tokens or any(tok in tbl_leaf.lower() for tok in tokens):
                seen_tables.add(tbl_leaf)
                bq_fallback.append(tbl_leaf)
            else:
                unmatched_leaves.append(tbl_leaf)

        bq_meta_map: dict[str, Any] = {}
        if not is_wildcard and tokens and len(seen_tables) < 5 and unmatched_leaves:
            probe_leaves = unmatched_leaves[:25]
            with ThreadPoolExecutor(max_workers=_CATALOG_INSPECT_MAX_WORKERS) as pool:
                probe_objs = list(pool.map(lambda lf: self._fetch_bq_table_safe(f"{dataset_ref}.{lf}"), probe_leaves))
            for lf, tbl_meta in zip(probe_leaves, probe_objs, strict=True):
                bq_meta_map[lf] = tbl_meta
                if tbl_meta is None:
                    continue
                desc = str(getattr(tbl_meta, "description", "") or "").lower()
                if any(tok in desc for tok in tokens):
                    seen_tables.add(lf)
                    bq_fallback.append(lf)

        bq_fallback.sort()
        live_bq_names = {str(tbl.table_id) for tbl in bq_tables}
        if live_bq_names:
            with self._cert_lock:
                self._known_tables_cache = set(live_bq_names)
            kc_ordered = [lf for lf in kc_ordered if lf in live_bq_names]
        ordered_tables = [*kc_ordered, *bq_fallback]

        kc_provides_descriptions = len(ordered_tables) > 40 and any(
            bool(hint.get("entry_desc")) for hint in kc_hints.values()
        )
        bq_fetch_candidates: list[str] = []
        fast_omitted = 0
        for lf in ordered_tables:
            if lf in bq_meta_map:
                continue
            if kc_provides_descriptions and lf in kc_hints:
                hint = kc_hints[lf]
                if not hint.get("entry_desc") and not hint.get("has_curated_aspect"):
                    fast_omitted += 1
                    continue
            bq_fetch_candidates.append(lf)

        if bq_fetch_candidates:
            with ThreadPoolExecutor(max_workers=min(_CATALOG_INSPECT_MAX_WORKERS, len(bq_fetch_candidates))) as pool:
                fetched_objs = list(
                    pool.map(lambda lf: self._fetch_bq_table_safe(f"{dataset_ref}.{lf}"), bq_fetch_candidates)
                )
            for lf, tbl_obj in zip(bq_fetch_candidates, fetched_objs, strict=True):
                bq_meta_map[lf] = tbl_obj

        inspect_all_dataplex = len(ordered_tables) <= 40

        def _should_inspect_dataplex(lf: str) -> bool:
            if kc_provides_descriptions and lf not in bq_meta_map:
                return False
            if inspect_all_dataplex:
                return True
            hint = kc_hints.get(lf) or {}
            if hint.get("has_curated_aspect") or hint.get("entry_desc"):
                return True
            tbl_obj = bq_meta_map.get(lf)
            if tbl_obj is not None:
                if str(getattr(tbl_obj, "description", "") or "").strip():
                    return True
                tc = getattr(tbl_obj, "table_constraints", None)
                if tc and (getattr(tc, "primary_key", None) or getattr(tc, "foreign_keys", None)):
                    return True
            return False

        dataplex_targets = [lf for lf in ordered_tables if _should_inspect_dataplex(lf)]
        uncertified_omitted = fast_omitted + (len(ordered_tables) - fast_omitted - len(dataplex_targets))

        results: list[dict[str, Any]] = []
        if dataplex_targets:
            with ThreadPoolExecutor(max_workers=min(_CATALOG_INSPECT_MAX_WORKERS, len(dataplex_targets))) as pool:
                inspected = list(
                    pool.map(
                        lambda lf: self._inspect_discovery_table(
                            lf,
                            tbl_obj=bq_meta_map.get(lf),
                            kc_hint=kc_hints.get(lf) or {},
                            inspect_dataplex=True,
                        ),
                        dataplex_targets,
                    )
                )
            for item in inspected:
                if item is None:
                    uncertified_omitted += 1
                else:
                    results.append(item)

        results.sort(key=lambda item: (item["_sort_rank"], item["table_name"]))
        for item in results:
            item.pop("_sort_rank", None)

        property_graphs = self._extract_property_graphs(term, tokens, is_wildcard=is_wildcard)
        response: dict[str, Any] = {
            "dataset_id": self.dataset_id,
            "search_term": term,
            "total_matched": len(results),
            "uncertified_omitted": uncertified_omitted,
            "truncated": len(results) > _MAX_DISCOVERY_TABLES,
            "governance_policy": _GOVERNANCE_POLICY_NOTE,
            "tables": results[:_MAX_DISCOVERY_TABLES],
            "metadata_sa": self.metadata_sa_email,
        }
        if property_graphs:
            response["property_graphs"] = property_graphs
        return response

    def _inspect_table_detail(self, leaf: str, entry_name: str) -> dict[str, Any]:
        looked: dict[str, Any] = {}
        aspects: dict[str, Any] = {}
        glossary_definitions: list[dict[str, Any]] = []

        def _fetch_entry() -> tuple[bool, dict[str, Any]]:
            try:
                return True, self.catalog_client.lookup_entry(entry_name, view="ALL")
            except AgentContextError:
                return False, {}

        def _fetch_links() -> list[dict[str, Any]]:
            try:
                return self.catalog_client.lookup_entry_links(entry_name)
            except AgentContextError:
                return []

        with ThreadPoolExecutor(max_workers=3) as pool:
            fut_entry = pool.submit(_fetch_entry)
            fut_links = pool.submit(_fetch_links)
            fut_bq = pool.submit(self._fetch_bq_table_safe, f"{self.project_id}.{self.dataset_id}.{leaf}")
            entry_ok, looked = fut_entry.result()
            links = fut_links.result()
            tbl_obj = fut_bq.result()

        aspects = self._extract_aspects_summary(looked)
        cert_status = self._extract_certification_status(aspects)
        if entry_ok:
            self._cache_table_certification(leaf, cert_status)

        term_entries_to_fetch: list[str] = []
        parsed_links: list[dict[str, Any]] = []
        for link in links:
            link_type = str(link.get("entryLinkType") or "")
            refs = link.get("entryReferences") or []
            term_info: dict[str, Any] = {
                "entry_link_type": link_type,
                "column_path": None,
                "term_entry": None,
                "display_name": None,
                "description": None,
            }
            for ref in refs:
                ref_name = str(ref.get("name") or "")
                if ref.get("path"):
                    term_info["column_path"] = ref["path"]
                if "/glossaries/" in ref_name and "/terms/" in ref_name:
                    term_info["term_entry"] = ref_name
                    if ref_name not in term_entries_to_fetch:
                        term_entries_to_fetch.append(ref_name)
            if term_info["term_entry"] or term_info["column_path"]:
                parsed_links.append(term_info)

        term_data_map: dict[str, dict[str, Any]] = {}
        if term_entries_to_fetch:
            def _fetch_term(tname: str) -> dict[str, Any]:
                try:
                    return self.catalog_client.get_glossary_term(tname)
                except AgentContextError:
                    return {}

            with ThreadPoolExecutor(max_workers=min(4, len(term_entries_to_fetch))) as pool:
                term_results = list(pool.map(_fetch_term, term_entries_to_fetch))
            term_data_map = dict(zip(term_entries_to_fetch, term_results, strict=True))

        for term_info in parsed_links:
            tname = term_info.get("term_entry")
            if tname and tname in term_data_map:
                tdata = term_data_map[tname]
                term_info["display_name"] = tdata.get("displayName")
                term_info["description"] = tdata.get("description")
            glossary_definitions.append(term_info)

        tbl_desc = ""
        col_details: list[dict[str, Any]] = []
        constraints_info: dict[str, Any] = {}
        if tbl_obj is not None:
            tbl_desc = str(getattr(tbl_obj, "description", "") or "")
            col_details = [
                {
                    "name": f.name,
                    "type": f.field_type,
                    "description": getattr(f, "description", None) or "",
                }
                for f in (getattr(tbl_obj, "schema", None) or [])
            ]
            tc = getattr(tbl_obj, "table_constraints", None)
            if tc is not None:
                pk = getattr(tc, "primary_key", None)
                fks = getattr(tc, "foreign_keys", None) or []
                constraints_info = {
                    "primary_key": list(getattr(pk, "columns", []) or []) if pk else [],
                    "foreign_keys": [
                        {
                            "name": getattr(fk, "name", ""),
                            "referenced_table": str(getattr(getattr(fk, "referenced_table", None), "table_id", "")),
                            "columns": [
                                f"{col_ref.referencing_column}->{col_ref.referenced_column}"
                                for col_ref in (getattr(fk, "column_references", None) or [])
                            ],
                        }
                        for fk in fks
                    ],
                }

        detail: dict[str, Any] = {
            "table_name": f"{self.dataset_id}.{leaf}",
            "fqn": f"{self.project_id}.{self.dataset_id}.{leaf}",
            "description": tbl_desc,
            "columns": col_details,
            "certification": aspects.get("certification"),
            "data_quality": aspects.get("data_quality"),
            "glossary_definitions": glossary_definitions,
            "table_constraints": constraints_info,
        }
        if cert_status in _BLOCKED_CERTIFICATION_STATUSES:
            detail["query_blocked_by_governance_policy"] = True
        return detail

    def lookup_catalog_context(self, table_names: Sequence[str] | str) -> dict[str, Any]:
        if isinstance(table_names, str):
            raw_list = [part.strip() for part in table_names.split(",") if part.strip()]
        else:
            raw_list = [str(part).strip() for part in table_names if str(part).strip()]
        if not raw_list:
            raise AgentContextError("lookup_catalog_context requires at least one table name.")

        leaves = [_extract_table_leaf(name, allowed_dataset_id=self.dataset_id) for name in raw_list[:8]]
        entry_names = [self._entry_name(leaf) for leaf in leaves]

        def _fetch_context() -> str:
            try:
                return self.catalog_client.lookup_context(entry_names)
            except AgentContextError as err:
                return f"[lookupContext note: {err}]"

        with ThreadPoolExecutor(max_workers=min(_CATALOG_INSPECT_MAX_WORKERS, len(leaves) + 1)) as pool:
            fut_context = pool.submit(_fetch_context)
            fut_details = [
                pool.submit(self._inspect_table_detail, leaf, entry_name)
                for leaf, entry_name in zip(leaves, entry_names, strict=True)
            ]
            context_text = fut_context.result()
            tables_detail = [fut.result() for fut in fut_details]

        return {
            "dataset_id": self.dataset_id,
            "lookup_context": context_text[:_LOOKUP_CONTEXT_MAX_CHARS],
            "governance_policy": _GOVERNANCE_POLICY_NOTE,
            "tables": tables_detail,
            "metadata_sa": self.metadata_sa_email,
        }

    def _glossary_exclusion_tokens(self) -> set[str]:
        glossary = self.context_layer.get("glossary")
        if not isinstance(glossary, Mapping):
            return set()
        excluded: set[str] = set()
        for term_entry in glossary.get("terms") or []:
            if not isinstance(term_entry, Mapping):
                continue
            for field in (term_entry.get("term_id"), term_entry.get("display_name")):
                excluded.update(self._tokenize_identifier_text(str(field or "")))
        return excluded

    def get_verified_metric_contract(self, topic: str) -> dict[str, Any]:
        contracts = self.context_layer.get("verified_metric_contracts")
        if not isinstance(contracts, Mapping) or not contracts:
            return {
                "topic": topic,
                "matched_contracts": {},
                "note": (
                    "No verified_metric_contracts exist in this pack. Do NOT retry get_verified_metric_contract; "
                    "proceed to search_certified_tables('*'), lookup_catalog_context, or execute_select_sql."
                ),
            }

        glossary_tokens = self._glossary_exclusion_tokens()
        raw_tokens = self._tokenize_identifier_text(topic or "")
        query_tokens = [
            tok for tok in raw_tokens if tok not in _CONTRACT_STOPWORDS and tok not in glossary_tokens
        ]
        topic_norm = (topic or "").strip().lower()
        matched: dict[str, Any] = {}

        if query_tokens or topic_norm:
            def _filtered_tokens(fields: list[str] | tuple[str, ...]) -> set[str]:
                return {
                    t
                    for field in fields
                    for t in self._tokenize_identifier_text(field)
                    if t not in _CONTRACT_STOPWORDS and t not in glossary_tokens
                }

            primary_by_key: dict[str, tuple[str, ...]] = {}
            primary_tokens_by_key: dict[str, set[str]] = {}
            secondary_tokens_by_key: dict[str, set[str]] = {}
            full_doc_freq: dict[str, int] = {}

            for key, body in contracts.items():
                key_str = str(key)
                if isinstance(body, Mapping):
                    graph_leaf = str(body.get("graph_name") or "").rsplit(".", 1)[-1].strip("`")
                    primary_fields: tuple[str, ...] = (
                        key_str,
                        str(body.get("metric_name") or ""),
                        str(body.get("display_name") or ""),
                        graph_leaf,
                    )
                    secondary_fields: list[str] = [
                        str(body.get("description") or ""),
                        str(body.get("edge_chain") or ""),
                    ]
                    for list_key in ("node_labels", "edge_labels"):
                        val = body.get(list_key)
                        if isinstance(val, (list, tuple)):
                            secondary_fields.extend(str(item) for item in val)
                    all_fields: list[str] = [*primary_fields, *secondary_fields]
                    for list_key in ("governing_tables", "allowed_tables"):
                        val = body.get(list_key)
                        if isinstance(val, (list, tuple)):
                            all_fields.extend(str(item) for item in val)
                else:
                    primary_fields = (key_str,)
                    secondary_fields = []
                    all_fields = [key_str]

                primary_by_key[key_str] = primary_fields
                primary_tokens_by_key[key_str] = _filtered_tokens(primary_fields)
                secondary_tokens_by_key[key_str] = _filtered_tokens(secondary_fields)
                for tok in _filtered_tokens(all_fields):
                    full_doc_freq[tok] = full_doc_freq.get(tok, 0) + 1

            # Primary matching: require either exact name/key/graph match OR >= 1 contract-unique
            # token (full_doc_freq == 1 across all contracts), and retain only max-score matches.
            primary_scored: list[tuple[tuple[int, int, int], str, Any]] = []
            for key, body in contracts.items():
                key_str = str(key)
                exact_targets = {f.strip().lower() for f in primary_by_key[key_str] if f and f.strip()}
                exact_hit = 1 if (topic_norm and topic_norm in exact_targets) else 0
                p_tokens = primary_tokens_by_key[key_str]
                token_hits = {tok for tok in query_tokens if tok in p_tokens}
                unique_hits = sum(1 for tok in token_hits if full_doc_freq.get(tok, 0) == 1)
                if exact_hit or unique_hits >= 1:
                    primary_scored.append(((exact_hit, unique_hits, len(token_hits)), key_str, body))

            if primary_scored:
                best_primary_score = max(score for score, _, _ in primary_scored)
                for score, key_str, body in primary_scored:
                    if score == best_primary_score:
                        matched[key_str] = body

            # Secondary runtime-derived structural matching (e.g., node/edge labels & description):
            # only match tokens unique to a single contract (df == 1) and keep max-score matches.
            if not matched and query_tokens:
                secondary_scored: list[tuple[tuple[int, int], str, Any]] = []
                for key, body in contracts.items():
                    key_str = str(key)
                    s_tokens = secondary_tokens_by_key[key_str]
                    token_hits = {tok for tok in query_tokens if tok in s_tokens}
                    unique_hits = sum(1 for tok in token_hits if full_doc_freq.get(tok, 0) == 1)
                    if unique_hits >= 1:
                        secondary_scored.append(((unique_hits, len(token_hits)), key_str, body))
                if secondary_scored:
                    best_secondary_score = max(score for score, _, _ in secondary_scored)
                    for score, key_str, body in secondary_scored:
                        if score == best_secondary_score:
                            matched[key_str] = body

        response: dict[str, Any] = {
            "topic": topic,
            "matched_contracts": matched,
        }
        if not matched:
            response["note"] = (
                "No verified metric contract matched this topic. Do NOT retry get_verified_metric_contract; "
                "proceed to search_certified_tables('*'), lookup_catalog_context on the relevant tables, "
                "or execute your query directly with execute_select_sql."
            )
        return response

    def _configured_graph_leaves(self) -> set[str]:
        contracts = self.context_layer.get("verified_metric_contracts")
        if not isinstance(contracts, Mapping):
            return set()
        leaves: set[str] = set()
        for body in contracts.values():
            if not isinstance(body, Mapping):
                continue
            raw_name = self._resolve_placeholders(str(body.get("graph_name") or "")).strip().strip("`")
            leaf = raw_name.rsplit(".", 1)[-1].strip().lower()
            if leaf:
                leaves.add(leaf)
        return leaves

    def _extract_sql_table_leaves_for_governance(self, sql: str) -> list[str]:
        if not isinstance(sql, str) or not sql.strip():
            return []
        stripped_code = strip_sql_literals_and_comments(sql)
        ident_seg = r"(?:`[^`]+`|[A-Za-z0-9_$-]+)"
        scan_sql = re.sub(
            rf"\bGRAPH_TABLE\s*\(\s*(?:`[^`]+`|{ident_seg}(?:\s*\.\s*{ident_seg})*)",
            "GRAPH_TABLE(",
            stripped_code,
            flags=re.IGNORECASE,
        )
        cte_names = {
            m.group(1).lower()
            for m in re.finditer(
                r"(?:\bWITH(?:\s+RECURSIVE)?|,)\s*`?([A-Za-z_][A-Za-z0-9_$]*)`?\s+AS\s*\(",
                scan_sql,
                flags=re.IGNORECASE,
            )
        }
        graph_leaves = self._configured_graph_leaves()
        known_tables = self._known_table_names()
        with self._cert_lock:
            cached_leaves = set(self._table_cert_cache.keys())

        found: list[str] = []
        seen: set[str] = set()

        def _record(leaf_raw: str) -> None:
            leaf = leaf_raw.strip("`").strip()
            if not leaf or leaf.upper() == "INFORMATION_SCHEMA":
                return
            low = leaf.lower()
            if low in graph_leaves or low in seen:
                return
            seen.add(low)
            found.append(leaf)

        qual_pat = re.compile(
            rf"(`[^`.\s]+(?:\.[^`.\s]+){{1,2}}`|{ident_seg}(?:\.{ident_seg}){{1,2}})"
        )
        for m in qual_pat.finditer(scan_sql):
            parts = [p.strip("`") for p in m.group(1).split(".") if p.strip("`")]
            if len(parts) == 2:
                ds, leaf = parts
            elif len(parts) == 3:
                _, ds, leaf = parts
            else:
                continue
            if ds == self.dataset_id:
                _record(leaf)

        sql_keywords = {
            "select",
            "with",
            "unnest",
            "lateral",
            "graph_table",
            "graph_expand",
            "table",
            "values",
        }
        scalar_from_prefix = re.compile(r"\b(?:EXTRACT|SUBSTRING|TRIM)\s*\([^()]*\bFROM\s*$", re.IGNORECASE)
        unqual_pat = re.compile(r"\b(?:FROM|JOIN)\s+(`?[A-Za-z_][A-Za-z0-9_$-]*`?)(?!\s*[.(])", re.IGNORECASE)
        for m in unqual_pat.finditer(scan_sql):
            before_ident = scan_sql[max(0, m.start(1) - 60) : m.start(1)]
            if scalar_from_prefix.search(before_ident):
                continue
            ident = m.group(1).strip("`")
            low = ident.lower()
            if low in sql_keywords or low in cte_names or low in graph_leaves:
                continue
            if known_tables and ident not in known_tables and ident not in cached_leaves:
                continue
            _record(ident)

        return found

    def _enforce_governance_certification_before_dry_run(self, sql: str) -> None:
        table_leaves = self._extract_sql_table_leaves_for_governance(sql)
        if not table_leaves:
            return
        for leaf in table_leaves:
            with self._cert_lock:
                cert_status = self._table_cert_cache.get(leaf)
            if cert_status is None:
                try:
                    looked = self.catalog_client.lookup_entry(self._entry_name(leaf), view="ALL")
                except AgentContextError as err:
                    raise AgentSqlSecurityError(
                        f"Governance policy blocked query: failed to verify certification aspect for "
                        f"{self.dataset_id}.{leaf}: {err}"
                    ) from err
                aspects = self._extract_aspects_summary(looked)
                cert_status = self._extract_certification_status(aspects)
                self._cache_table_certification(leaf, cert_status)
            if cert_status in _BLOCKED_CERTIFICATION_STATUSES:
                raise AgentSqlSecurityError(
                    f"Governance policy blocked query: table {self.dataset_id}.{leaf} has "
                    f"certification_status={cert_status!r}; query the CERTIFIED Data Product instead."
                )

    def execute_select_sql(self, sql: str, *, timeout_s: float | None = None) -> dict[str, Any]:
        self._enforce_governance_certification_before_dry_run(sql)
        gate = validate_agent_sql_gate(
            self.sql_bq_client,
            sql,
            allowed_project_id=self.project_id,
            allowed_dataset_id=self.dataset_id,
            forbidden_datasets=self.forbidden_datasets,
            max_bytes=self.max_bytes,
            location=self.bq_location,
        )
        from google.cloud import bigquery

        run_cfg = bigquery.QueryJobConfig(
            use_query_cache=False,
            maximum_bytes_billed=self.max_bytes,
        )
        job = self.sql_bq_client.query(sql, job_config=run_cfg, location=self.bq_location)
        rows_raw = _await_bq_job_result(job, timeout_s=timeout_s)
        rows_preview, row_count = _rows_to_json_safe(rows_raw, max_rows=50)
        return {
            "rows": rows_preview,
            "row_count": row_count,
            "bytes_billed": int(getattr(job, "total_bytes_billed", 0) or gate["total_bytes_processed"]),
            "referenced_tables": gate["referenced_tables"],
            "statement_type": gate["statement_type"],
            "executed_as_sa": self.sql_sa_email,
        }
