"""Lightweight allowlisted FastAPI runner and static web server."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import re
import time
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from engine.capture_rungs import (
    _execute_query_rows,
    _extract_table_ids_from_sql,
    _match_persona_policy,
    _rewrite_table_with_rls_predicate,
    list_active_row_access_policies,
)
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    discover_packs,
    load_raw_pack,
    render_bundle_placeholders,
    resolve_env_settings,
)
from engine.rls_impersonation import (
    build_impersonated_credentials,
    parse_role_sa_map,
    redact_bundle_data,
    redact_sensitive_identifiers,
)
from engine.trust_classifier import classify_rung_outcome

__all__ = ["RunRungRequest", "app", "create_app"]

_ID_SLUG_REGEX = re.compile(r"^[a-z0-9_]+$")
_PLACEHOLDER_PROJECT = "example-project-id"


class RunRungRequest(BaseModel):
    """Strict allowlisted request payload for executing a pack rung."""

    model_config = ConfigDict(extra="forbid")

    pack_id: str = Field(min_length=1, max_length=64)
    rung_id: str = Field(min_length=1, max_length=64)
    mode: Literal["blind", "governed"]
    persona_id: str | None = Field(default=None, min_length=1, max_length=64)
    live: bool | None = None


def create_app(
    *,
    packs_dir: Path | None = None,
    web_dir: Path | None = None,
    env_file: Path | None = None,
    bq_client: Any = None,
    impersonated_client_factory: Callable[[str], Any] | None = None,
) -> FastAPI:
    """Creates a FastAPI app exposing /api/health, /api/run-rung, and static web/."""
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

    @application.get("/api/health")
    def health() -> dict[str, Any]:
        settings = resolve_env_settings(DEFAULT_REPO_ROOT, env_file=env_file)
        live_pid = settings["PROJECT_ID"]
        return {
            "status": "ok",
            "packs": discover_packs(resolved_packs_dir),
            "live_gcp_configured": bool(
                (live_pid and live_pid != _PLACEHOLDER_PROJECT) or bq_client is not None
            ),
            "bq_location": settings["BQ_LOCATION"],
        }

    @application.post("/api/run-rung")
    def run_rung(req: RunRungRequest) -> dict[str, Any]:
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
        bq_location = str(
            os.environ.get("BQ_LOCATION")
            or raw_bundle.get("region")
            or settings["BQ_LOCATION"]
        )

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
            if display_variant is not None and req.persona_id is not None:
                raw_sa_map = os.environ.get("SQL_ROLE_SA_MAP_JSON", "").strip()
                role_sa_map = parse_role_sa_map(raw_sa_map) if raw_sa_map else None
                if impersonated_client_factory is not None:
                    active_client = impersonated_client_factory(req.persona_id)
                elif role_sa_map and req.persona_id in role_sa_map:
                    from google.cloud import bigquery

                    creds, _ = build_impersonated_credentials(
                        role=req.persona_id,
                        role_sa_map=role_sa_map,
                    )
                    active_client = bigquery.Client(
                        project=live_project_id,
                        credentials=creds,
                        location=bq_location,
                    )
                else:
                    table_ids = _extract_table_ids_from_sql(sql_to_run, dataset_id)
                    if table_ids:
                        policies = list_active_row_access_policies(
                            client,
                            project_id=live_project_id,
                            dataset_id=dataset_id,
                            table_id=table_ids[0],
                            location=bq_location,
                        )
                        matched = _match_persona_policy(req.persona_id, display_variant, policies)
                        if matched and matched.get("filter_predicate"):
                            sql_to_run = _rewrite_table_with_rls_predicate(
                                sql_to_run,
                                project_id=live_project_id,
                                dataset_id=dataset_id,
                                table_id=table_ids[0],
                                filter_predicate=str(matched["filter_predicate"]),
                            )

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

    if resolved_web_dir.is_dir():
        application.mount(
            "/",
            StaticFiles(directory=str(resolved_web_dir), html=True),
            name="web",
        )

    return application


app = create_app()
