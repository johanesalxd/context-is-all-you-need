"""Lightweight allowlisted FastAPI runner and static web server.

Designed for local Workbench exploration: executes strictly allowlisted
`(pack_id, rung_id, mode, persona_id)` queries without client-supplied SQL or
HTTP HMAC assertion headers (external multi-tenant gateways can wire
`engine.rls_impersonation.verify_role_assertion` in front of requests).
"""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import hmac
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from engine.capture_rungs import (
    _execute_query_rows,
    _extract_table_ids_from_sql,
    _match_persona_policy,
    _rewrite_table_with_rls_predicate,
    list_active_row_access_policies,
    resolve_persona_bigquery_client,
)
from engine.live_agent import AgentRunResult, run_live_agent_arm
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    discover_packs,
    load_raw_pack,
    parse_bool_flag,
    render_bundle_placeholders,
    resolve_bq_location,
    resolve_env_settings,
    resolve_phase2_settings,
)
from engine.poll_store import (
    FirestorePollStore,
    InMemoryPollStore,
    PollCapacityError,
    PollStoreUnavailableError,
    PollValidationError,
    render_poll_qr_svg,
)
from engine.rls_impersonation import (
    parse_role_sa_map,
    redact_bundle_data,
    redact_sensitive_identifiers,
)
from engine.trust_classifier import classify_rung_outcome

__all__ = [
    "PollResetRequest",
    "PollSyncStageRequest",
    "PollVoteRequest",
    "RunAgentRequest",
    "RunRungRequest",
    "app",
    "create_app",
]

_logger = logging.getLogger(__name__)
_ID_SLUG_REGEX = re.compile(r"^[a-z0-9_]+$")
_VALID_HOST_REGEX = re.compile(r"^(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?$")
_VALID_PUBLIC_ORIGIN_REGEX = re.compile(r"^https?://(?:\[[0-9A-Fa-f:]+\]|[A-Za-z0-9.-]+)(?::[0-9]{1,5})?$")
_PLACEHOLDER_PROJECT = "example-project-id"
_DEFAULT_POLL_READ_RPM_LIMIT = 3000
_POLL_VOTER_RPM_LIMIT = 15
_MAX_TRACKED_VOTER_BUCKETS = 2000
_MAX_QR_SVG_CACHE = 128


class RunRungRequest(BaseModel):
    """Strict allowlisted request payload for executing a pack rung."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)
    mode: Literal["blind", "governed"]
    persona_id: str | None = Field(default=None, min_length=1, max_length=64)
    live: bool | None = None


class RunAgentRequest(BaseModel):
    """Strict allowlisted request payload for running the live Gemini Blind vs Governed agent."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)
    arm: Literal["blind", "governed", "both"] = "both"
    persona_id: str | None = Field(default=None, min_length=1, max_length=64)


class PollVoteRequest(BaseModel):
    """Strict allowlisted request payload for casting or switching an audience poll vote."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)
    choice: Literal["A", "B", "C", "D"]
    voter_token: str = Field(min_length=16, max_length=64, pattern=r"^[A-Za-z0-9_-]{16,64}$")


class PollResetRequest(BaseModel):
    """Strict allowlisted request payload for presenter-gated poll reset."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)


class PollSyncStageRequest(BaseModel):
    """Strict allowlisted request payload for syncing the live presenter stage rung."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)


def create_app(
    *,
    packs_dir: Path | None = None,
    web_dir: Path | None = None,
    env_file: Path | None = None,
    bq_client: Any = None,
    impersonated_client_factory: Callable[[str], Any] | None = None,
    live_agent_runner: Callable[..., AgentRunResult] | None = None,
    poll_store: Any = None,
) -> FastAPI:
    """Creates a FastAPI app exposing /api/health, /api/run-rung, /api/run-agent, /vote, /api/poll/*, and static web/."""
    resolved_packs_dir = packs_dir or (DEFAULT_REPO_ROOT / "packs")
    resolved_web_dir = web_dir or (DEFAULT_REPO_ROOT / "web")

    application = FastAPI(
        title="Context ScenarioPack Live Runner",
        version="0.1.0",
    )

    @application.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = redact_bundle_data(exc.errors())
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid request payload", "errors": safe_errors},
        )

    rate_buckets: dict[str, deque[float]] = {}
    poll_read_buckets: OrderedDict[str, deque[float]] = OrderedDict()
    poll_vote_ip_buckets: OrderedDict[str, deque[float]] = OrderedDict()
    poll_voter_buckets: OrderedDict[str, deque[float]] = OrderedDict()
    pack_poll_cache: dict[str, tuple[tuple[Any, ...], dict[str, Any], dict[str, dict[str, Any]]]] = {}
    qr_svg_cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()
    state_lock = threading.Lock()
    agent_semaphore = threading.BoundedSemaphore(2)
    daily_counter = {"date": "", "count": 0}
    active_poll_store_box: dict[str, Any] = {"store": poll_store}

    def _get_poll_store() -> Any:
        if active_poll_store_box["store"] is not None:
            return active_poll_store_box["store"]
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        live_pid = settings["PROJECT_ID"]
        db_id = settings.get("FIRESTORE_DATABASE_ID", "").strip()
        use_firestore = bool(
            live_pid
            and live_pid != _PLACEHOLDER_PROJECT
            and db_id
            and db_id.lower() != "none"
        )
        with state_lock:
            if active_poll_store_box["store"] is None:
                if use_firestore:
                    active_poll_store_box["store"] = FirestorePollStore(
                        project_id=live_pid,
                        database_id=db_id,
                    )
                else:
                    active_poll_store_box["store"] = InMemoryPollStore()
            return active_poll_store_box["store"]

    def _resolve_share_token() -> str:
        resolve_env_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        return os.environ.get("DEMO_SHARE_TOKEN", "").strip()

    def _extract_client_ip(http_req: Request) -> str:
        parts = [
            p.strip()
            for p in http_req.headers.get("x-forwarded-for", "").split(",")
            if p.strip()
        ]
        if parts:
            return parts[-1]
        return http_req.client.host if http_req.client else "local"

    def _consume_bounded_rate_bucket(
        buckets: OrderedDict[str, deque[float]],
        key: str,
        limit: int,
        *,
        detail: str,
        max_keys: int = _MAX_TRACKED_VOTER_BUCKETS,
    ) -> None:
        if limit <= 0:
            return
        now_ts = time.monotonic()
        with state_lock:
            bucket = buckets.get(key)
            if bucket is None:
                while len(buckets) >= max_keys:
                    buckets.popitem(last=False)
                bucket = deque()
                buckets[key] = bucket
            else:
                buckets.move_to_end(key)
            while bucket and (now_ts - bucket[0]) > 60.0:
                bucket.popleft()
            if len(bucket) >= limit:
                raise HTTPException(status_code=429, detail=detail)
            bucket.append(now_ts)

    def _check_rate_limit(http_req: Request) -> None:
        rpm_limit = int(os.environ.get("RUN_RUNG_RPM_LIMIT", "30"))
        if rpm_limit > 0:
            now_ts = time.monotonic()
            client_ip = _extract_client_ip(http_req)
            with state_lock:
                bucket = rate_buckets.setdefault(client_ip, deque())
                while bucket and (now_ts - bucket[0]) > 60.0:
                    bucket.popleft()
                if len(bucket) >= rpm_limit:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded ({rpm_limit} live queries per minute).",
                    )
                bucket.append(now_ts)

    def _pack_mtime_sig(pack_id: str) -> tuple[tuple[str, int], ...]:
        pack_root = resolved_packs_dir / pack_id
        items: list[tuple[str, int]] = []
        pack_yaml = pack_root / "pack.yaml"
        if pack_yaml.is_file():
            items.append(("pack.yaml", pack_yaml.stat().st_mtime_ns))
        rungs_dir = pack_root / "rungs"
        if rungs_dir.is_dir():
            for p in sorted(rungs_dir.iterdir()):
                if p.is_file() and p.suffix in (".yaml", ".yml"):
                    items.append((p.name, p.stat().st_mtime_ns))
        return tuple(items)

    def _get_cached_display_pack(
        resolved_pack: str,
        settings: Mapping[str, str],
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        sig = (
            _pack_mtime_sig(resolved_pack),
            str(settings.get("DATASET_ID") or ""),
            str(settings.get("BQ_LOCATION") or ""),
        )
        with state_lock:
            cached = pack_poll_cache.get(resolved_pack)
            if cached is not None and cached[0] == sig:
                return cached[1], cached[2]

        raw_bundle = load_raw_pack(resolved_pack, packs_dir=resolved_packs_dir)
        bq_location = resolve_bq_location(raw_bundle, env_settings=settings)
        display_bundle = render_bundle_placeholders(
            raw_bundle,
            project_id=_PLACEHOLDER_PROJECT,
            dataset_id=settings["DATASET_ID"],
            bq_location=bq_location,
        )
        rungs_by_id = {
            str(r["id"]): r
            for r in (display_bundle.get("rungs") or [])
            if isinstance(r, Mapping) and r.get("id")
        }
        with state_lock:
            pack_poll_cache[resolved_pack] = (sig, display_bundle, rungs_by_id)
        return display_bundle, rungs_by_id

    def _resolve_pack_and_rung(
        pack_id: str | None,
        rung_id: str | None,
        *,
        require_rung: bool,
        settings: Mapping[str, str],
    ) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        available_packs = discover_packs(resolved_packs_dir)
        if not available_packs:
            raise HTTPException(status_code=404, detail="No ScenarioPacks discovered on server.")

        if pack_id is None or not pack_id.strip():
            configured_pack = str(settings.get("PACK_ID") or "").strip()
            resolved_pack = configured_pack if configured_pack in available_packs else available_packs[0]
        else:
            resolved_pack = pack_id.strip()
            if not _ID_SLUG_REGEX.match(resolved_pack):
                raise HTTPException(status_code=400, detail="Invalid pack_id format")
            if resolved_pack not in available_packs:
                raise HTTPException(status_code=404, detail=f"Unknown pack_id: {resolved_pack}")

        display_bundle, rungs_by_id = _get_cached_display_pack(resolved_pack, settings)
        rungs = display_bundle.get("rungs") or []
        if not rungs:
            raise HTTPException(status_code=404, detail=f"Pack {resolved_pack} has no rungs.")

        if rung_id is None or not rung_id.strip():
            if require_rung:
                raise HTTPException(status_code=400, detail="rung_id is required")
            return resolved_pack, display_bundle, None

        cleaned_rung = rung_id.strip()
        if not _ID_SLUG_REGEX.match(cleaned_rung):
            raise HTTPException(status_code=400, detail="Invalid rung_id format")
        matched = rungs_by_id.get(cleaned_rung)
        if matched is None:
            raise HTTPException(status_code=404, detail=f"Unknown rung_id: {cleaned_rung}")
        return resolved_pack, display_bundle, matched

    def _derive_trusted_origin(http_req: Request, settings: Mapping[str, str]) -> str:
        configured = str(settings.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
        if configured:
            if not _VALID_PUBLIC_ORIGIN_REGEX.match(configured):
                raise HTTPException(status_code=500, detail="Invalid PUBLIC_BASE_URL configuration")
            return configured

        raw_proto = http_req.headers.get("x-forwarded-proto", "")
        proto_hops = [p.strip().lower() for p in raw_proto.split(",") if p.strip()]
        if proto_hops and (proto_hops[0] == "https" or proto_hops[-1] == "https"):
            proto = "https"
        else:
            proto = http_req.url.scheme or "http"

        raw_host = (http_req.headers.get("host") or http_req.url.netloc or "").strip()
        if not raw_host or not _VALID_HOST_REGEX.match(raw_host):
            raise HTTPException(status_code=400, detail="Invalid Host header")
        return f"{proto}://{raw_host}"

    def _verify_share_token(http_req: Request, *, require_token: bool, fail_closed_on_missing: bool) -> None:
        expected_token = _resolve_share_token()
        if not require_token:
            return
        if not expected_token:
            if fail_closed_on_missing:
                raise HTTPException(
                    status_code=503,
                    detail="DEMO_SHARE_TOKEN is not configured on the server.",
                )
            return
        supplied = (
            http_req.headers.get("x-demo-key", "").strip()
            or http_req.query_params.get("key", "").strip()
        )
        if not supplied or not hmac.compare_digest(supplied, expected_token):
            raise HTTPException(
                status_code=401,
                detail="Valid demo share key required (open via shared ?key=... link).",
            )

    def _enforce_access_and_rate_limit(http_req: Request) -> None:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        req_token = parse_bool_flag(settings.get("REQUIRE_TOKEN_FOR_RUN_RUNG"), default=False, on_invalid=True)
        _verify_share_token(http_req, require_token=req_token, fail_closed_on_missing=True)
        _check_rate_limit(http_req)

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        live_pid = settings["PROJECT_ID"]
        token_configured = bool(_resolve_share_token())
        req_run_rung = parse_bool_flag(settings.get("REQUIRE_TOKEN_FOR_RUN_RUNG"), default=False, on_invalid=True)
        req_live_agent = parse_bool_flag(settings.get("REQUIRE_TOKEN_FOR_LIVE_AGENT"), default=True, on_invalid=True)
        live_agent_enabled = parse_bool_flag(settings.get("ENABLE_LIVE_AGENT"), default=True, on_invalid=False)
        live_poll_enabled = parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False)
        store = _get_poll_store()
        poll_storage_warning = None
        if os.environ.get("K_SERVICE") and store.storage_mode == "memory":
            poll_storage_warning = (
                "InMemoryPollStore active under Cloud Run (K_SERVICE); "
                "configure non-placeholder PROJECT_ID and FIRESTORE_DATABASE_ID for multi-instance shared tallies."
            )
            _logger.warning(poll_storage_warning)
        return {
            "status": "ok",
            "packs": discover_packs(resolved_packs_dir),
            "live_gcp_configured": bool(
                (live_pid and live_pid != _PLACEHOLDER_PROJECT) or bq_client is not None
            ),
            "bq_location": settings["BQ_LOCATION"],
            "agent_model_id": settings["AGENT_MODEL_ID"],
            "agent_model_location": settings["AGENT_MODEL_LOCATION"],
            "share_token_required": bool(req_run_rung and token_configured),
            "live_agent_enabled": live_agent_enabled,
            "live_agent_token_required": req_live_agent,
            "live_poll_enabled": live_poll_enabled,
            "poll_storage_mode": store.storage_mode,
            "poll_storage_warning": poll_storage_warning,
        }

    @application.post("/api/run-rung")
    def run_rung(req: RunRungRequest, http_req: Request) -> dict[str, Any]:
        _enforce_access_and_rate_limit(http_req)
        started = time.perf_counter()
        if not _ID_SLUG_REGEX.match(req.pack_id):
            raise HTTPException(status_code=400, detail="Invalid pack_id format")
        if not _ID_SLUG_REGEX.match(req.rung_id):
            raise HTTPException(status_code=400, detail="Invalid rung_id format")
        if req.persona_id is not None and not _ID_SLUG_REGEX.match(req.persona_id):
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        available_packs = discover_packs(resolved_packs_dir)
        if req.pack_id not in available_packs:
            raise HTTPException(status_code=404, detail=f"Unknown pack_id: {req.pack_id}")

        settings = resolve_env_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        live_project_id = settings["PROJECT_ID"]
        dataset_id = settings["DATASET_ID"]
        raw_bundle = load_raw_pack(req.pack_id, packs_dir=resolved_packs_dir)
        bq_location = resolve_bq_location(raw_bundle, env_settings=settings)

        matching_rungs = [r for r in raw_bundle["rungs"] if r.get("id") == req.rung_id]
        if not matching_rungs:
            raise HTTPException(status_code=404, detail=f"Unknown rung_id: {req.rung_id}")
        raw_rung = matching_rungs[0]

        valid_personas = {str(p.get("id")) for p in raw_bundle.get("personas", [])}
        variants = raw_rung.get("identity_variants") or {}
        if req.persona_id is not None:
            if req.persona_id not in valid_personas:
                raise HTTPException(status_code=404, detail=f"Unknown persona_id: {req.persona_id}")
            if variants and req.persona_id not in variants:
                raise HTTPException(
                    status_code=404,
                    detail=f"Persona {req.persona_id} not configured for rung {req.rung_id}",
                )

        display_bundle = render_bundle_placeholders(
            raw_bundle,
            project_id=_PLACEHOLDER_PROJECT,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
        display_rung = next(r for r in display_bundle["rungs"] if r.get("id") == req.rung_id)
        display_outcome = dict(display_rung[req.mode])
        display_variant: Mapping[str, Any] | None = (
            display_rung.get("identity_variants", {}).get(req.persona_id)
            if (req.persona_id and req.mode == "governed" and variants)
            else None
        )

        use_live = (
            req.live
            if req.live is not None
            else bool((live_project_id and live_project_id != _PLACEHOLDER_PROJECT) or bq_client is not None)
        )

        if not use_live:
            assessment = classify_rung_outcome(
                display_outcome,
                mode=req.mode,
                question=str(display_rung.get("question", "")),
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            headline = (
                display_variant["answer_headline"]
                if display_variant
                else display_outcome["answer_headline"]
            )
            detail = (
                display_variant["answer_detail"]
                if display_variant
                else display_outcome["answer_detail"]
            )
            num_val = (
                display_variant["numeric_value"]
                if display_variant
                else display_outcome["numeric_value"]
            )
            return redact_bundle_data(
                {
                    "pack_id": req.pack_id,
                    "rung_id": req.rung_id,
                    "mode": req.mode,
                    "persona_id": req.persona_id,
                    "execution_mode": "offline_fixture",
                    "rls_enforcement": "offline_fixture",
                    "latency_ms": elapsed_ms,
                    "answer_headline": headline,
                    "answer_detail": detail,
                    "numeric_value": num_val,
                    "unit": display_outcome["unit"],
                    "trust_tier": assessment.tier.value,
                    "query_language": display_outcome["query_language"],
                    "sql_or_gql": display_outcome["sql_or_gql"],
                    "row_count": display_variant["rows_visible"] if display_variant else 1,
                    "rows_returned": display_variant["rows_visible"] if display_variant else 1,
                    "rows": [],
                },
                extra_tokens=[live_project_id],
                live_project_id=live_project_id,
            )

        if (not live_project_id or live_project_id == _PLACEHOLDER_PROJECT) and bq_client is None:
            raise HTTPException(
                status_code=400,
                detail="Live BigQuery execution requires non-placeholder PROJECT_ID",
            )

        exec_bundle = render_bundle_placeholders(
            raw_bundle,
            project_id=live_project_id,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
        exec_rung = next(r for r in exec_bundle["rungs"] if r.get("id") == req.rung_id)
        exec_outcome = exec_rung[req.mode]
        sql_to_run = str(exec_outcome["sql_or_gql"])

        try:
            client = bq_client
            if client is None:
                from google.cloud import bigquery

                client = bigquery.Client(project=live_project_id, location=bq_location)

            active_client = client
            rls_enforcement = "not_applicable"
            if display_variant is not None and req.persona_id is not None:
                raw_sa_map = os.environ.get("SQL_ROLE_SA_MAP_JSON", "").strip()
                role_sa_map = parse_role_sa_map(raw_sa_map) if raw_sa_map else None
                table_ids = _extract_table_ids_from_sql(sql_to_run, dataset_id)
                target_table = ""
                policies: list[dict[str, Any]] = []
                for candidate_tbl in table_ids:
                    found = list_active_row_access_policies(
                        client,
                        project_id=live_project_id,
                        dataset_id=dataset_id,
                        table_id=candidate_tbl,
                        location=bq_location,
                    )
                    if found:
                        target_table = candidate_tbl
                        policies = found
                        break
                if not target_table and table_ids:
                    target_table = table_ids[0]

                resolved = None
                if impersonated_client_factory is not None or role_sa_map or bq_client is None:
                    try:
                        resolved = resolve_persona_bigquery_client(
                            base_client=client,
                            persona_id=req.persona_id,
                            variant=display_variant,
                            policies=policies,
                            project_id=live_project_id,
                            dataset_id=dataset_id,
                            location=bq_location,
                            role_sa_map=role_sa_map,
                            impersonated_client_factory=impersonated_client_factory,
                        )
                    except Exception:
                        if impersonated_client_factory is not None or role_sa_map:
                            raise
                        resolved = None

                if resolved is not None:
                    active_client, _, _ = resolved
                    rls_enforcement = "bigquery_rls_impersonated"
                elif target_table and policies:
                    matched = _match_persona_policy(req.persona_id, display_variant, policies)
                    if matched and matched.get("filter_predicate"):
                        sql_to_run = _rewrite_table_with_rls_predicate(
                            sql_to_run,
                            project_id=live_project_id,
                            dataset_id=dataset_id,
                            table_id=target_table,
                            filter_predicate=str(matched["filter_predicate"]),
                        )
                        rls_enforcement = "predicate_simulation"

            rows = _execute_query_rows(
                active_client,
                sql_to_run,
                project_id=live_project_id,
                dataset_id=dataset_id,
                location=bq_location,
                dry_run=False,
            )
            assessment = classify_rung_outcome(
                {
                    **display_outcome,
                    "answer_headline": (
                        display_variant["answer_headline"]
                        if display_variant
                        else display_outcome["answer_headline"]
                    ),
                    "numeric_value": (
                        display_variant["numeric_value"]
                        if display_variant
                        else display_outcome["numeric_value"]
                    ),
                },
                mode=req.mode,
                question=str(display_rung.get("question", "")),
                result_rows=rows,
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
            return redact_bundle_data(
                {
                    "pack_id": req.pack_id,
                    "rung_id": req.rung_id,
                    "mode": req.mode,
                    "persona_id": req.persona_id,
                    "execution_mode": "live_gcp",
                    "rls_enforcement": rls_enforcement,
                    "latency_ms": elapsed_ms,
                    "answer_headline": (
                        display_variant["answer_headline"]
                        if display_variant
                        else display_outcome["answer_headline"]
                    ),
                    "answer_detail": (
                        display_variant["answer_detail"]
                        if display_variant
                        else display_outcome["answer_detail"]
                    ),
                    "numeric_value": (
                        display_variant["numeric_value"]
                        if display_variant
                        else display_outcome["numeric_value"]
                    ),
                    "unit": display_outcome["unit"],
                    "trust_tier": assessment.tier.value,
                    "query_language": display_outcome["query_language"],
                    "sql_or_gql": display_outcome["sql_or_gql"],
                    "row_count": len(rows),
                    "rows_returned": len(rows),
                    "rows": rows[:20],
                },
                extra_tokens=[live_project_id],
                live_project_id=live_project_id,
            )
        except HTTPException:
            raise
        except Exception as exc:
            status_code = 403 if getattr(exc, "code", None) == 403 else 500
            safe_err = redact_sensitive_identifiers(
                str(exc),
                extra_tokens=[live_project_id],
                live_project_id=live_project_id,
            )
            raise HTTPException(
                status_code=status_code,
                detail=f"Query execution failed ({type(exc).__name__}): {safe_err}",
            ) from exc

    @application.post("/api/run-agent")
    def run_agent(req: RunAgentRequest, http_req: Request) -> dict[str, Any]:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_AGENT"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live agent endpoint is disabled (ENABLE_LIVE_AGENT=false).")

        req_live_token = parse_bool_flag(settings.get("REQUIRE_TOKEN_FOR_LIVE_AGENT"), default=True, on_invalid=True)
        _verify_share_token(http_req, require_token=req_live_token, fail_closed_on_missing=True)
        _check_rate_limit(http_req)

        if not _ID_SLUG_REGEX.match(req.pack_id):
            raise HTTPException(status_code=400, detail="Invalid pack_id format")
        if not _ID_SLUG_REGEX.match(req.rung_id):
            raise HTTPException(status_code=400, detail="Invalid rung_id format")
        if req.persona_id is not None and not _ID_SLUG_REGEX.match(req.persona_id):
            raise HTTPException(status_code=400, detail="Invalid persona_id format")

        available_packs = discover_packs(resolved_packs_dir)
        if req.pack_id not in available_packs:
            raise HTTPException(status_code=404, detail=f"Unknown pack_id: {req.pack_id}")

        live_project_id = settings["PROJECT_ID"]
        if live_agent_runner is None and (not live_project_id or live_project_id == _PLACEHOLDER_PROJECT):
            raise HTTPException(
                status_code=503,
                detail="Live GCP project is not configured for live agent execution.",
            )

        raw_bundle = load_raw_pack(req.pack_id, packs_dir=resolved_packs_dir)
        bq_location = resolve_bq_location(raw_bundle, env_settings=settings)
        rendered_bundle = render_bundle_placeholders(
            raw_bundle,
            project_id=live_project_id if live_project_id else _PLACEHOLDER_PROJECT,
            dataset_id=settings["DATASET_ID"],
            bq_location=bq_location,
        )
        matching_rungs = [r for r in rendered_bundle["rungs"] if r.get("id") == req.rung_id]
        if not matching_rungs:
            raise HTTPException(status_code=404, detail=f"Unknown rung_id: {req.rung_id}")
        raw_rung = matching_rungs[0]

        valid_personas = {str(p.get("id")) for p in rendered_bundle.get("personas", [])}
        if req.persona_id is not None and valid_personas and req.persona_id not in valid_personas and req.persona_id != "default":
            raise HTTPException(status_code=404, detail=f"Unknown persona_id: {req.persona_id}")

        if not agent_semaphore.acquire(blocking=False):
            raise HTTPException(
                status_code=429,
                detail="Live agent concurrency limit reached (max 2 concurrent runs). Retry shortly.",
            )

        arms_to_run = ["blind", "governed"] if req.arm == "both" else [req.arm]
        runner = live_agent_runner or run_live_agent_arm
        arms_output: dict[str, Any] = {}
        active_model_id = settings["AGENT_MODEL_ID"]
        active_model_location = settings["AGENT_MODEL_LOCATION"]
        try:
            daily_limit = int(settings.get("DAILY_AGENT_CALL_LIMIT") or "200")
            today_str = datetime.now(timezone.utc).date().isoformat()
            with state_lock:
                if daily_counter["date"] != today_str:
                    daily_counter["date"] = today_str
                    daily_counter["count"] = 0
                if (daily_counter["count"] + len(arms_to_run)) > daily_limit:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Daily live agent call cap reached ({daily_limit} calls/day).",
                    )
                daily_counter["count"] += len(arms_to_run)

            for arm_name in arms_to_run:
                res = runner(
                    pack_id=req.pack_id,
                    rung=raw_rung,
                    arm=arm_name,
                    persona_id=req.persona_id,
                    packs_dir=resolved_packs_dir,
                )
                res_dict = res.to_dict() if hasattr(res, "to_dict") else dict(res)
                if res_dict.get("model_id"):
                    active_model_id = str(res_dict["model_id"])
                if res_dict.get("model_location"):
                    active_model_location = str(res_dict["model_location"])
                arms_output[arm_name] = res_dict
        except HTTPException:
            raise
        except Exception as exc:
            status_code = 403 if getattr(exc, "code", None) == 403 else 500
            extra_scrub = [t for t in (live_project_id, os.environ.get("PROJECT_NUMBER", "")) if t]
            safe_err = redact_sensitive_identifiers(
                str(exc),
                extra_tokens=extra_scrub,
                live_project_id=live_project_id,
            )
            raise HTTPException(
                status_code=status_code,
                detail=f"Live agent execution failed ({type(exc).__name__}): {safe_err}",
            ) from exc
        finally:
            agent_semaphore.release()

        extra_scrub = [t for t in (live_project_id, os.environ.get("PROJECT_NUMBER", "")) if t]
        return redact_bundle_data(
            {
                "pack_id": req.pack_id,
                "rung_id": req.rung_id,
                "persona_id": req.persona_id or raw_rung.get("default_persona") or "default",
                "model_id": active_model_id,
                "model_location": active_model_location,
                "bq_location": bq_location,
                "arms": arms_output,
            },
            extra_tokens=extra_scrub,
            live_project_id=live_project_id,
        )

    def _serve_vote_html() -> FileResponse:
        vote_html = resolved_web_dir / "vote.html"
        if not vote_html.is_file():
            raise HTTPException(status_code=404, detail="vote.html not found")
        return FileResponse(
            path=vote_html,
            media_type="text/html",
            headers={"Cache-Control": "no-cache"},
        )

    @application.get("/vote")
    def vote_page() -> FileResponse:
        return _serve_vote_html()

    @application.get("/vote/")
    def vote_page_slash() -> FileResponse:
        return _serve_vote_html()

    @application.get("/vote.html")
    def vote_page_html() -> FileResponse:
        return _serve_vote_html()

    def _raise_poll_unavailable(exc: PollStoreUnavailableError, live_pid: str) -> None:
        safe_err = redact_sensitive_identifiers(
            str(exc),
            extra_tokens=[live_pid],
            live_project_id=live_pid,
        )
        _logger.warning("Live poll backend unavailable: %s", safe_err)
        raise HTTPException(
            status_code=503,
            detail=f"Live poll storage unavailable: {safe_err}",
        ) from exc

    @application.get("/api/poll/state")
    def get_poll_state(
        http_req: Request,
        pack_id: str | None = None,
        rung_id: str | None = None,
    ) -> JSONResponse:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live poll endpoint is disabled (ENABLE_LIVE_POLL=false).")

        try:
            read_rpm_limit = int(settings.get("POLL_READ_RPM_LIMIT") or str(_DEFAULT_POLL_READ_RPM_LIMIT))
        except ValueError:
            read_rpm_limit = _DEFAULT_POLL_READ_RPM_LIMIT

        client_ip = _extract_client_ip(http_req)
        _consume_bounded_rate_bucket(
            poll_read_buckets,
            client_ip,
            read_rpm_limit,
            detail=f"Poll state rate limit exceeded ({read_rpm_limit} reads per minute).",
        )

        resolved_pack, display_bundle, explicit_rung = _resolve_pack_and_rung(
            pack_id,
            rung_id,
            require_rung=False,
            settings=settings,
        )
        store = _get_poll_store()
        rungs = list(display_bundle["rungs"])
        rung_ids = {str(r["id"]) for r in rungs}
        live_pid = settings["PROJECT_ID"]

        try:
            stored_stage_rung = store.get_active_stage_rung(resolved_pack)
            active_stage_rung_id = stored_stage_rung if stored_stage_rung in rung_ids else None

            if explicit_rung is not None:
                target_rung = explicit_rung
            elif active_stage_rung_id is not None:
                target_rung = next(r for r in rungs if r["id"] == active_stage_rung_id)
            else:
                target_rung = rungs[0]

            tally = store.get_poll_tally(resolved_pack, str(target_rung["id"]))
        except PollStoreUnavailableError as exc:
            _raise_poll_unavailable(exc, live_pid)

        poll = target_rung["poll"]

        # Zero-spoiler invariant: never expose correct_key or reveal_takeaway on /api/poll/state.
        payload = redact_bundle_data(
            {
                "pack_id": resolved_pack,
                "pack_title": str(display_bundle.get("title") or resolved_pack),
                "rung_id": str(target_rung["id"]),
                "rung_num": int(target_rung["rung_num"]),
                "short_label": str(target_rung["short_label"]),
                "title": str(target_rung["title"]),
                "question": str(target_rung["question"]),
                "prompt": str(poll["prompt"]),
                "options": [
                    {"key": str(opt["key"]), "text": str(opt["text"])}
                    for opt in poll["options"]
                ],
                "external_poll_url": poll.get("external_poll_url"),
                "counts": dict(tally["counts"]),
                "total_votes": int(tally["total_votes"]),
                "epoch": int(tally["epoch"]),
                "active_stage_rung_id": active_stage_rung_id,
                "available_rungs": [
                    {
                        "id": str(r["id"]),
                        "rung_num": int(r["rung_num"]),
                        "short_label": str(r["short_label"]),
                    }
                    for r in rungs
                ],
                "storage_mode": str(tally["storage_mode"]),
            },
            extra_tokens=[live_pid],
            live_project_id=live_pid,
        )
        return JSONResponse(content=payload, headers={"Cache-Control": "no-store"})

    @application.post("/api/poll/vote")
    def cast_poll_vote(req: PollVoteRequest, http_req: Request) -> JSONResponse:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live poll endpoint is disabled (ENABLE_LIVE_POLL=false).")

        try:
            vote_ip_rpm = int(settings.get("POLL_VOTE_RPM_LIMIT") or "240")
        except ValueError:
            vote_ip_rpm = 240

        client_ip = _extract_client_ip(http_req)
        _consume_bounded_rate_bucket(
            poll_vote_ip_buckets,
            client_ip,
            vote_ip_rpm,
            detail=f"Poll vote IP rate limit exceeded ({vote_ip_rpm} votes per minute).",
        )
        voter_rate_key = hashlib.sha256(req.voter_token.encode("utf-8")).hexdigest()[:32]
        _consume_bounded_rate_bucket(
            poll_voter_buckets,
            voter_rate_key,
            _POLL_VOTER_RPM_LIMIT,
            detail=f"Per-voter rate limit exceeded ({_POLL_VOTER_RPM_LIMIT} vote updates per minute).",
        )

        resolved_pack, _, target_rung = _resolve_pack_and_rung(
            req.pack_id,
            req.rung_id,
            require_rung=True,
            settings=settings,
        )
        assert target_rung is not None
        store = _get_poll_store()
        live_pid = settings["PROJECT_ID"]
        try:
            result = store.cast_vote(
                resolved_pack,
                str(target_rung["id"]),
                req.choice,
                req.voter_token,
            )
        except PollCapacityError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except PollValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PollStoreUnavailableError as exc:
            _raise_poll_unavailable(exc, live_pid)

        scrubbed = redact_bundle_data(
            result,
            extra_tokens=[live_pid],
            live_project_id=live_pid,
        )
        return JSONResponse(content=scrubbed, headers={"Cache-Control": "no-store"})

    @application.post("/api/poll/reset")
    def reset_poll_votes(req: PollResetRequest, http_req: Request) -> JSONResponse:
        _verify_share_token(http_req, require_token=True, fail_closed_on_missing=True)
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live poll endpoint is disabled (ENABLE_LIVE_POLL=false).")

        resolved_pack, _, target_rung = _resolve_pack_and_rung(
            req.pack_id,
            req.rung_id,
            require_rung=True,
            settings=settings,
        )
        assert target_rung is not None
        store = _get_poll_store()
        live_pid = settings["PROJECT_ID"]
        try:
            result = store.reset_poll(resolved_pack, str(target_rung["id"]))
        except PollStoreUnavailableError as exc:
            _raise_poll_unavailable(exc, live_pid)

        scrubbed = redact_bundle_data(
            result,
            extra_tokens=[live_pid],
            live_project_id=live_pid,
        )
        return JSONResponse(content=scrubbed, headers={"Cache-Control": "no-store"})

    @application.post("/api/poll/sync-stage")
    def sync_poll_stage(req: PollSyncStageRequest, http_req: Request) -> dict[str, str]:
        _verify_share_token(http_req, require_token=True, fail_closed_on_missing=True)
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live poll endpoint is disabled (ENABLE_LIVE_POLL=false).")

        resolved_pack, _, target_rung = _resolve_pack_and_rung(
            req.pack_id,
            req.rung_id,
            require_rung=True,
            settings=settings,
        )
        assert target_rung is not None
        store = _get_poll_store()
        live_pid = settings["PROJECT_ID"]
        try:
            active_id = store.set_active_stage_rung(resolved_pack, str(target_rung["id"]))
        except PollStoreUnavailableError as exc:
            _raise_poll_unavailable(exc, live_pid)
        return {"pack_id": resolved_pack, "active_stage_rung_id": active_id}

    @application.get("/api/poll/qr.svg")
    def get_poll_qr_svg(
        http_req: Request,
        pack_id: str | None = None,
        rung_id: str | None = None,
    ) -> Response:
        settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        if not parse_bool_flag(settings.get("ENABLE_LIVE_POLL"), default=True, on_invalid=False):
            raise HTTPException(status_code=503, detail="Live poll endpoint is disabled (ENABLE_LIVE_POLL=false).")

        resolved_pack, _, target_rung = _resolve_pack_and_rung(
            pack_id,
            rung_id,
            require_rung=False,
            settings=settings,
        )
        origin = _derive_trusted_origin(http_req, settings)
        rung_key = str(target_rung["id"]) if target_rung is not None else ""
        cache_key = (origin, resolved_pack, rung_key)
        with state_lock:
            cached_svg = qr_svg_cache.get(cache_key)
            if cached_svg is not None:
                qr_svg_cache.move_to_end(cache_key)
                return Response(
                    content=cached_svg,
                    media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=300"},
                )

        if rung_key:
            vote_url = f"{origin}/vote?pack={resolved_pack}&rung={rung_key}"
        else:
            vote_url = f"{origin}/vote?pack={resolved_pack}"
        try:
            svg_markup = render_poll_qr_svg(vote_url)
        except PollValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        with state_lock:
            while len(qr_svg_cache) >= _MAX_QR_SVG_CACHE:
                qr_svg_cache.popitem(last=False)
            qr_svg_cache[cache_key] = svg_markup
        return Response(
            content=svg_markup,
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=300"},
        )

    if resolved_web_dir.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=str(resolved_web_dir), html=True),
            name="web",
        )

    return application


app = create_app()
