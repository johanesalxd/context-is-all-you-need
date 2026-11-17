"""Zero-trust SQL AST gate, strict SA isolation, and live Knowledge Catalog tools."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import date, datetime, time as dt_time
from decimal import Decimal
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from engine.pack_loader import _strip_sql_comments
from engine.rls_impersonation import (
    ImpersonationError,
    build_impersonated_credentials,
    is_valid_customer_sa,
    parse_role_sa_map,
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

    def _bearer_token(self) -> str:
        if self.credentials is None:
            raise AgentContextError("Impersonated credentials are required for Knowledge Catalog REST calls.")
        from google.auth.transport.requests import Request as GoogleAuthRequest

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
        body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace") if err.fp else ""
            raise AgentContextError(
                f"Knowledge Catalog HTTP {err.code} for {method} {url}: {err_body[:400]}"
            ) from err
        except URLError as err:
            raise AgentContextError(f"Knowledge Catalog transport error for {url}: {err}") from err

    def search_entries(self, query: str, *, page_size: int = 20) -> list[dict[str, Any]]:
        url = f"{_DATAPLEX_BASE}/projects/{self.project_id}/locations/global:searchEntries"
        resp = self._request_json(
            "POST",
            url,
            payload={"query": query, "pageSize": min(max(1, page_size), 50)},
        )
        return list(resp.get("results") or [])

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

    def list_tables(self, pattern: str = "", limit: int = 50) -> dict[str, Any]:
        dataset_ref = f"{self.project_id}.{self.blind_dataset_id}"
        all_names = sorted(str(tbl.table_id) for tbl in self.bq_client.list_tables(dataset_ref))
        pat = (pattern or "").strip().lower()
        filtered = [name for name in all_names if pat in name.lower()] if pat else all_names
        capped = max(1, min(int(limit or 50), 250))
        return {
            "dataset_id": self.blind_dataset_id,
            "total_tables": len(all_names),
            "matched_tables": len(filtered),
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

    def execute_select_sql(self, sql: str) -> dict[str, Any]:
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
        rows_raw = list(job.result())
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

    def _entry_name(self, table_leaf: str) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.bq_location}/entryGroups/@bigquery/entries/"
            f"bigquery.googleapis.com/projects/{self.project_id}/datasets/{self.dataset_id}/tables/{table_leaf}"
        )

    @staticmethod
    def _extract_aspects_summary(entry_payload: Mapping[str, Any]) -> dict[str, Any]:
        aspects = entry_payload.get("aspects")
        if not isinstance(aspects, Mapping):
            return {}
        summary: dict[str, Any] = {}
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

    def search_certified_tables(self, search_term: str) -> dict[str, Any]:
        term = (search_term or "").strip()
        results: list[dict[str, Any]] = []
        seen_tables: set[str] = set()

        search_queries = [f"{term} dataset={self.dataset_id}" if term and term != "*" else f"dataset={self.dataset_id}"]
        if term and term not in {"*", "all"}:
            search_queries.append(term)

        candidate_entries: list[dict[str, Any]] = []
        for q in search_queries:
            try:
                hits = self.catalog_client.search_entries(q, page_size=25)
            except AgentContextError:
                hits = []
            for hit in hits:
                linked = str(hit.get("linkedResource") or "")
                dp_entry = hit.get("dataplexEntry") or {}
                entry_name = str(dp_entry.get("name") or "")
                marker = f"/datasets/{self.dataset_id}/tables/"
                if marker in linked or marker in entry_name:
                    candidate_entries.append(hit)
            if candidate_entries:
                break

        for hit in candidate_entries:
            dp_entry = hit.get("dataplexEntry") or {}
            entry_name = str(dp_entry.get("name") or "")
            if "/tables/" not in entry_name:
                continue
            table_leaf = entry_name.rsplit("/tables/", 1)[-1].split("/", 1)[0]
            if table_leaf and table_leaf not in seen_tables:
                seen_tables.add(table_leaf)

        # Also inspect live BigQuery inventory in dataset_id when search_term matches names/descriptions
        # or to guarantee zero search-index propagation lag right after provisioning.
        tokens = [t.lower() for t in re.split(r"[^A-Za-z0-9_]+", term) if len(t) >= 2]
        dataset_ref = f"{self.project_id}.{self.dataset_id}"
        try:
            bq_tables = list(self.metadata_bq_client.list_tables(dataset_ref))
        except Exception:
            bq_tables = []

        for tbl_item in bq_tables:
            tbl_leaf = str(tbl_item.table_id)
            if tbl_leaf in seen_tables:
                continue
            if not tokens or term in {"*", "all"} or any(tok in tbl_leaf.lower() for tok in tokens):
                seen_tables.add(tbl_leaf)
            elif len(seen_tables) < 3:
                try:
                    tbl_meta = self.metadata_bq_client.get_table(f"{dataset_ref}.{tbl_leaf}")
                    desc = str(getattr(tbl_meta, "description", "") or "").lower()
                    if any(tok in desc for tok in tokens):
                        seen_tables.add(tbl_leaf)
                except Exception:
                    pass

        for tbl_leaf in sorted(seen_tables)[:15]:
            entry_name = self._entry_name(tbl_leaf)
            aspect_summary: dict[str, Any] = {}
            kc_error: str | None = None
            try:
                looked = self.catalog_client.lookup_entry(entry_name, view="ALL")
                aspect_summary = self._extract_aspects_summary(looked)
            except AgentContextError as err:
                kc_error = str(err)

            description = ""
            columns: list[dict[str, Any]] = []
            try:
                tbl_obj = self.metadata_bq_client.get_table(f"{dataset_ref}.{tbl_leaf}")
                description = str(getattr(tbl_obj, "description", "") or "")
                columns = [
                    {
                        "name": f.name,
                        "type": f.field_type,
                        "description": getattr(f, "description", None) or "",
                    }
                    for f in (getattr(tbl_obj, "schema", None) or [])
                ]
            except Exception:
                pass

            cert = aspect_summary.get("certification") or {}
            cert_status = str(cert.get("certification_status") or "UNTAGGED")
            rank = 0 if cert_status == "CERTIFIED" else (2 if "UNCERTIFIED" in cert_status or "STALE" in cert_status else 1)
            results.append(
                {
                    "table_name": f"{self.dataset_id}.{tbl_leaf}",
                    "fqn": f"{self.project_id}.{self.dataset_id}.{tbl_leaf}",
                    "certification_status": cert_status,
                    "certification_aspect": cert,
                    "data_quality": aspect_summary.get("data_quality"),
                    "description": description,
                    "columns": columns,
                    "_sort_rank": rank,
                    **({"catalog_note": kc_error} if kc_error else {}),
                }
            )

        results.sort(key=lambda item: (item["_sort_rank"], item["table_name"]))
        for item in results:
            item.pop("_sort_rank", None)

        return {
            "dataset_id": self.dataset_id,
            "search_term": term,
            "tables": results,
            "metadata_sa": self.metadata_sa_email,
        }

    def lookup_catalog_context(self, table_names: Sequence[str] | str) -> dict[str, Any]:
        if isinstance(table_names, str):
            raw_list = [part.strip() for part in table_names.split(",") if part.strip()]
        else:
            raw_list = [str(part).strip() for part in table_names if str(part).strip()]
        if not raw_list:
            raise AgentContextError("lookup_catalog_context requires at least one table name.")

        leaves = [_extract_table_leaf(name, allowed_dataset_id=self.dataset_id) for name in raw_list[:8]]
        entry_names = [self._entry_name(leaf) for leaf in leaves]

        context_text = ""
        try:
            context_text = self.catalog_client.lookup_context(entry_names)
        except AgentContextError as err:
            context_text = f"[lookupContext note: {err}]"

        tables_detail: list[dict[str, Any]] = []
        for leaf, entry_name in zip(leaves, entry_names, strict=True):
            looked: dict[str, Any] = {}
            aspects: dict[str, Any] = {}
            glossary_definitions: list[dict[str, Any]] = []
            try:
                looked = self.catalog_client.lookup_entry(entry_name, view="ALL")
                aspects = self._extract_aspects_summary(looked)
            except AgentContextError:
                pass

            try:
                links = self.catalog_client.lookup_entry_links(entry_name)
            except AgentContextError:
                links = []

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
                        try:
                            term_data = self.catalog_client.get_glossary_term(ref_name)
                            term_info["display_name"] = term_data.get("displayName")
                            term_info["description"] = term_data.get("description")
                        except AgentContextError:
                            pass
                if term_info["term_entry"] or term_info["column_path"]:
                    glossary_definitions.append(term_info)

            tbl_desc = ""
            col_details: list[dict[str, Any]] = []
            constraints_info: dict[str, Any] = {}
            try:
                tbl_obj = self.metadata_bq_client.get_table(f"{self.project_id}.{self.dataset_id}.{leaf}")
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
            except Exception:
                pass

            tables_detail.append(
                {
                    "table_name": f"{self.dataset_id}.{leaf}",
                    "fqn": f"{self.project_id}.{self.dataset_id}.{leaf}",
                    "description": tbl_desc,
                    "columns": col_details,
                    "certification": aspects.get("certification"),
                    "data_quality": aspects.get("data_quality"),
                    "glossary_definitions": glossary_definitions,
                    "table_constraints": constraints_info,
                }
            )

        return {
            "dataset_id": self.dataset_id,
            "lookup_context": context_text[:6000],
            "tables": tables_detail,
            "metadata_sa": self.metadata_sa_email,
        }

    def get_verified_metric_contract(self, topic: str) -> dict[str, Any]:
        contracts = self.context_layer.get("verified_metric_contracts")
        if not isinstance(contracts, Mapping) or not contracts:
            return {
                "topic": topic,
                "matched_contracts": {},
                "available_topics": [],
                "note": "No verified_metric_contracts found in pack context_layer.yaml.",
            }

        query_tokens = [tok.lower() for tok in re.split(r"[^A-Za-z0-9_]+", topic or "") if len(tok) >= 2]
        matched: dict[str, Any] = {}
        for key, body in contracts.items():
            haystack = json.dumps({key: body}, ensure_ascii=True).lower()
            if not query_tokens or any(tok in haystack for tok in query_tokens):
                matched[str(key)] = body

        if not matched:
            matched = dict(contracts)

        return {
            "topic": topic,
            "matched_contracts": matched,
            "available_topics": sorted(str(k) for k in contracts.keys()),
        }

    def execute_select_sql(self, sql: str) -> dict[str, Any]:
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
        rows_raw = list(job.result())
        rows_preview, row_count = _rows_to_json_safe(rows_raw, max_rows=50)
        return {
            "rows": rows_preview,
            "row_count": row_count,
            "bytes_billed": int(getattr(job, "total_bytes_billed", 0) or gate["total_bytes_processed"]),
            "referenced_tables": gate["referenced_tables"],
            "statement_type": gate["statement_type"],
            "executed_as_sa": self.sql_sa_email,
        }
