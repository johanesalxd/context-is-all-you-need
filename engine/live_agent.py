"""Symmetric zero-trust Gemini live agent loop, signal classifier, and grader."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any

from engine.context_retriever import (
    AgentContextError,
    AgentSqlSecurityError,
    BlindToolContext,
    DataplexCatalogRestClient,
    GovernedToolContext,
    build_impersonated_bq_client,
    build_impersonated_credentials_for_sa,
    resolve_execution_sa,
)
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    load_context_layer,
    resolve_phase2_settings,
)
from engine.rls_impersonation import (
    is_valid_customer_sa,
    parse_role_sa_map,
    redact_bundle_data,
    resolve_agent_sa_map,
)
from engine.trust_classifier import TrustTier, classify_outcome, strip_sql_literals_and_comments

__all__ = [
    "AgentRunResult",
    "extract_observed_signals",
    "grade_agent_outcome",
    "run_live_agent_arm",
    "run_offline_mock_arm",
]

_FALLBACK_MODEL_ID = "gemini-3.5-flash"
_NUMBER_TOKEN_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_PROJECT_NUM_IN_PATH_RE = re.compile(r"projects/([0-9]{6,})\b")
_TIER_SEVERITY = {
    TrustTier.TIER_1_VERIFIED_OR_COMPILED.value: 1,
    TrustTier.TIER_2_GROUNDED.value: 2,
    TrustTier.TIER_3_REVIEW_REQUIRED.value: 3,
}


@dataclass
class AgentRunResult:
    """Structured telemetry and grading output for one Blind or Governed agent run."""

    arm: str
    answer_summary: str
    numeric_value: float | None
    passed_grading: bool
    grading_reason: str
    sql_or_gql: str
    query_language: str
    trust_tier: str
    trust_reasons: list[str] = field(default_factory=list)
    observed_signals: list[str] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)
    catalog_context_summary: str = ""
    tokens_used: int = 0
    exploratory_queries: int = 0
    error_retries: int = 0
    latency_ms: int = 0
    rows_preview: list[dict[str, Any]] = field(default_factory=list)
    model_id: str = ""
    model_location: str = ""
    persona_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_query_language(sql_or_gql: str | None) -> str:
    if not sql_or_gql:
        return "SQL"
    stripped = strip_sql_literals_and_comments(sql_or_gql)
    if re.search(r"(?<![A-Za-z0-9_`])GRAPH_TABLE\s*\(", stripped, flags=re.IGNORECASE):
        return "GQL"
    return "SQL"


def _parse_final_agent_json(text: str) -> tuple[str, float | None, str | None]:
    raw = (text or "").strip()
    if not raw:
        return "", None, None

    candidate_json: dict[str, Any] | None = None
    fence_matches = _JSON_FENCE_RE.findall(raw)
    for snippet in reversed(fence_matches):
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                candidate_json = parsed
                break
        except json.JSONDecodeError:
            continue

    if candidate_json is None:
        brace_start = raw.rfind("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            try:
                parsed = json.loads(raw[brace_start : brace_end + 1])
                if isinstance(parsed, dict) and ("answer_summary" in parsed or "numeric_value" in parsed):
                    candidate_json = parsed
            except json.JSONDecodeError:
                pass

    if candidate_json is not None:
        summary = str(candidate_json.get("answer_summary") or raw).strip()
        num_val = _coerce_float(candidate_json.get("numeric_value"))
        unit = candidate_json.get("unit")
        return summary, num_val, str(unit) if unit is not None else None

    return raw, None, None


def _coerce_float(val: Any) -> float | None:
    if val is None or isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "").rstrip("%")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _extract_scalar_from_rows(rows: Sequence[Mapping[str, Any]]) -> float | None:
    if not rows:
        return None
    first = rows[0]
    preferred_keys = (
        "net_revenue",
        "revenue",
        "gross_margin_pct",
        "margin_pct",
        "gross_margin",
        "sla_credit",
        "credit_sgd",
        "total_credit",
        "value",
        "metric",
        "total",
        "amount",
    )
    for pref in preferred_keys:
        for k, v in first.items():
            if pref in k.lower():
                parsed = _coerce_float(v)
                if parsed is not None:
                    return parsed
    for v in first.values():
        parsed = _coerce_float(v)
        if parsed is not None:
            return parsed
    return None


def _extract_numeric_tokens(text: str) -> list[float]:
    values: list[float] = []
    for tok in _NUMBER_TOKEN_RE.findall(text or ""):
        cleaned = tok.replace(",", "")
        try:
            values.append(float(cleaned))
        except ValueError:
            continue
    return values


def _numbers_close(a: float, b: float, *, tolerance: float = 0.01) -> bool:
    eff_tol = max(tolerance, abs(b) * 1e-4, 1e-6)
    return abs(a - b) <= eff_tol


def extract_observed_signals(
    *,
    tool_trace: Sequence[Mapping[str, Any]],
    sql_or_gql: str,
    referenced_tables: Sequence[str] = (),
    catalog_context_summary: str = "",
    has_persona_isolation: bool = False,
) -> list[str]:
    """Deterministically derives observed execution signals from live tool & SQL traces."""
    signals: set[str] = set()
    for step in tool_trace:
        name = str(step.get("tool_name") or "").strip()
        status = str(step.get("status") or "").strip().lower()
        preview = str(step.get("output_preview") or "")
        if name and status == "ok":
            signals.add(name)
            if name == "get_verified_metric_contract":
                signals.add("VERIFIED_METRIC_CONTRACT")
            if name == "search_certified_tables" and "CERTIFIED" in preview:
                signals.add("CERTIFIED")
            if name == "lookup_catalog_context" and (
                "glossary" in preview.lower() or "definition" in preview.lower()
            ):
                signals.add("GLOSSARY_DEFINITION")
            if name == "execute_select_sql":
                signals.add("DRY_RUN_VALIDATED")
        if "shadow_auto_tbl" in preview.lower() or "shadow_auto_tbl" in str(step.get("args_summary") or "").lower():
            signals.add("SHADOW_TABLE_PROBED")

    stripped_sql = strip_sql_literals_and_comments(sql_or_gql or "")
    if re.search(r"(?<![A-Za-z0-9_`])(?:MEASURE|GRAPH_EXPAND)\s*\(", stripped_sql, re.IGNORECASE):
        signals.add("MEASURE")
    if re.search(r"(?<![A-Za-z0-9_`])GRAPH_EXPAND\s*\(", stripped_sql, re.IGNORECASE):
        signals.add("GRAPH_EXPAND")
    if re.search(r"(?<![A-Za-z0-9_`])GRAPH_TABLE\s*\(", stripped_sql, re.IGNORECASE):
        signals.add("GRAPH_TABLE")

    all_tables_str = " ".join([*referenced_tables, stripped_sql]).lower()
    if "sla_overlay" in all_tables_str:
        signals.add("SLA_OVERLAY")
    if "shadow_auto_tbl" in all_tables_str:
        signals.add("SHADOW_TABLE_PROBED")

    summary_low = (catalog_context_summary or "").lower()
    if "certified" in summary_low:
        signals.add("CERTIFIED")
    if "glossary" in summary_low or "entry_link" in summary_low:
        signals.add("GLOSSARY_DEFINITION")

    if has_persona_isolation:
        signals.add("RLS_PERSONA_ISOLATION")

    return sorted(signals)


def _resolve_persona_id(rung: Mapping[str, Any], persona_id: str | None) -> str:
    cleaned = (persona_id or "").strip()
    if cleaned and cleaned != "default":
        return cleaned
    if isinstance(rung.get("default_persona"), str) and rung["default_persona"].strip():
        return rung["default_persona"].strip()
    variants = rung.get("identity_variants")
    if isinstance(variants, Mapping) and variants:
        return str(next(iter(variants.keys())))
    if isinstance(variants, Sequence) and not isinstance(variants, (str, bytes)) and variants:
        first = variants[0]
        if isinstance(first, Mapping) and first.get("persona_id"):
            return str(first["persona_id"]).strip()
    grading = rung.get("grading")
    if isinstance(grading, Mapping):
        pts = grading.get("persona_targets")
        if isinstance(pts, Mapping) and pts:
            return str(next(iter(pts.keys())))
    return "default"


def _resolve_grading_spec(rung: Mapping[str, Any], persona_id: str | None) -> dict[str, Any]:
    raw_grading = rung.get("grading")
    if not isinstance(raw_grading, Mapping):
        return {}
    spec = dict(raw_grading)
    persona_targets = spec.get("persona_targets")
    if isinstance(persona_targets, Mapping) and persona_targets:
        chosen_key: str | None = None
        chosen: Mapping[str, Any] | None = None
        if persona_id and persona_id in persona_targets and isinstance(persona_targets[persona_id], Mapping):
            chosen_key = persona_id
            chosen = persona_targets[persona_id]
        elif len(persona_targets) == 1:
            first_key = str(next(iter(persona_targets.keys())))
            first_val = persona_targets[first_key]
            if isinstance(first_val, Mapping):
                chosen_key = first_key
                chosen = first_val
        if chosen is not None:
            merged = dict(spec)
            if "target_value" in chosen:
                merged.update(chosen)
                return merged
            if "value" in chosen:
                if merged.get("target_value") is None:
                    merged["target_value"] = chosen["value"]
                    if "tolerance" in chosen:
                        merged["tolerance"] = chosen["tolerance"]
                else:
                    merged["_persona_target"] = {
                        "persona_id": chosen_key or "persona",
                        "value": chosen["value"],
                        "tolerance": chosen.get("tolerance", merged.get("tolerance", 0.01)),
                    }
                return merged
            merged.update(chosen)
            return merged
    return spec


def _extract_row_numerics(rows_preview: Sequence[Mapping[str, Any]]) -> list[float]:
    nums: list[float] = []
    for row in rows_preview:
        if not isinstance(row, Mapping):
            continue
        for val in row.values():
            parsed = _coerce_float(val)
            if parsed is not None:
                nums.append(parsed)
    return nums


def grade_agent_outcome(
    rung: Mapping[str, Any],
    *,
    answer_summary: str,
    numeric_value: float | None,
    sql_or_gql: str,
    rows_preview: Sequence[Mapping[str, Any]] = (),
    referenced_tables: Sequence[str] = (),
    persona_id: str | None = None,
) -> tuple[bool, str]:
    """Deterministically grades an agent outcome against rung['grading'] invariants."""
    effective_persona = _resolve_persona_id(rung, persona_id)
    spec = _resolve_grading_spec(rung, effective_persona)
    if not spec:
        return False, "Missing rung grading specification."

    stripped_sql = strip_sql_literals_and_comments(sql_or_gql or "")
    referenced_leaf_tables = {
        tbl.rsplit(".", 1)[-1].strip("`\"").lower()
        for tbl in referenced_tables
        if tbl
    }
    for disallowed in spec.get("disallowed_tables") or []:
        bad_leaf = str(disallowed).strip().lower()
        if not bad_leaf:
            continue
        if bad_leaf in referenced_leaf_tables or re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(bad_leaf)}(?![A-Za-z0-9_])",
            stripped_sql,
            re.IGNORECASE,
        ):
            return False, f"Disallowed table used: {bad_leaf}"

    target_value = _coerce_float(spec.get("target_value"))
    raw_tol = _coerce_float(spec.get("tolerance"))
    tolerance = raw_tol if raw_tol is not None else 0.01
    allow_ratio = bool(spec.get("allow_ratio_normalization", False))

    persona_target = spec.get("_persona_target")
    persona_val = _coerce_float(persona_target.get("value")) if isinstance(persona_target, Mapping) else None
    persona_tol_raw = _coerce_float(persona_target.get("tolerance")) if isinstance(persona_target, Mapping) else None
    persona_tol = persona_tol_raw if persona_tol_raw is not None else tolerance
    persona_name = str(persona_target.get("persona_id") or effective_persona) if isinstance(persona_target, Mapping) else effective_persona

    observed_num = numeric_value
    if observed_num is None and rows_preview:
        observed_num = _extract_scalar_from_rows(rows_preview)

    answer_and_row_nums: list[float] = []
    if observed_num is not None:
        answer_and_row_nums.append(observed_num)
    answer_and_row_nums.extend(_extract_row_numerics(rows_preview))
    answer_and_row_nums.extend(_extract_numeric_tokens(answer_summary or ""))

    if target_value is not None:
        if observed_num is None:
            return False, f"Missing numeric_value (expected {target_value})."

        primary_candidates = [observed_num]
        if allow_ratio:
            primary_candidates.extend([observed_num * 100.0, observed_num / 100.0])

        matched_primary_scalar = any(_numbers_close(cand, target_value, tolerance=tolerance) for cand in primary_candidates)
        matched_persona_scalar = persona_val is not None and _numbers_close(observed_num, persona_val, tolerance=persona_tol)

        if not matched_primary_scalar and not matched_persona_scalar:
            return (
                False,
                f"Numeric mismatch: expected {target_value} (±{tolerance}), got {observed_num}",
            )

        if matched_persona_scalar and not matched_primary_scalar:
            expanded_all = list(answer_and_row_nums)
            if allow_ratio:
                expanded_all.extend([n * 100.0 for n in answer_and_row_nums] + [n / 100.0 for n in answer_and_row_nums])
            if not any(_numbers_close(cand, target_value, tolerance=tolerance) for cand in expanded_all):
                return (
                    False,
                    f"Numeric mismatch: expected {target_value} (±{tolerance}) alongside persona value.",
                )

    if persona_val is not None:
        if not any(_numbers_close(obs, persona_val, tolerance=persona_tol) for obs in answer_and_row_nums):
            return (
                False,
                f"Persona target mismatch for {persona_name}: expected {persona_val} (±{persona_tol})",
            )

    combined_text = "\n".join(
        [
            answer_summary or "",
            sql_or_gql or "",
            json.dumps(list(rows_preview), ensure_ascii=True),
        ]
    )
    combined_lower = combined_text.lower()

    for req in spec.get("required_strings") or []:
        req_str = str(req).strip()
        if not req_str:
            continue
        options = [opt.strip() for opt in req_str.split("|") if opt.strip()]
        if not any(opt.lower() in combined_lower for opt in options):
            return False, f"Missing required string in answer/rows: {req_str!r}"

    secondary = spec.get("secondary_numerics")
    if secondary:
        items: Sequence[Any]
        if isinstance(secondary, Mapping):
            items = list(secondary.values())
        elif isinstance(secondary, Sequence) and not isinstance(secondary, (str, bytes)):
            items = list(secondary)
        else:
            items = [secondary]

        for expected_raw in items:
            sec_name = ""
            exact_zero = False
            sec_tol = max(tolerance, 1e-4)
            if isinstance(expected_raw, Mapping):
                sec_name = str(expected_raw.get("name") or "").strip()
                expected_f = _coerce_float(expected_raw.get("value"))
                item_tol = _coerce_float(expected_raw.get("tolerance"))
                if item_tol is not None:
                    exact_zero = item_tol == 0.0
                    sec_tol = item_tol
            else:
                expected_f = _coerce_float(expected_raw)

            if expected_f is None:
                continue

            cand_targets = [expected_f]
            if 0.0 < abs(expected_f) < 1.0:
                cand_targets.append(expected_f * 100.0)

            search_pool = list(answer_and_row_nums)
            if sec_name:
                named_vals = [
                    parsed
                    for row in rows_preview
                    if isinstance(row, Mapping) and sec_name in row
                    for parsed in [_coerce_float(row.get(sec_name))]
                    if parsed is not None
                ]
                if named_vals:
                    search_pool = named_vals

            def _sec_matches(obs: float, tgt: float) -> bool:
                if exact_zero:
                    return abs(obs - tgt) <= 1e-9
                return _numbers_close(obs, tgt, tolerance=sec_tol)

            if not any(_sec_matches(obs, tgt) for obs in search_pool for tgt in cand_targets):
                label = f" ({sec_name})" if sec_name else ""
                return False, f"Missing expected secondary numeric{label}: {expected_f}"

    return True, f"Passed grading (target={target_value})"


def _build_blind_declarations() -> list[Any]:
    from google.genai import types

    return [
        types.FunctionDeclaration(
            name="list_tables",
            description="List physical tables available in the target dataset.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "pattern": types.Schema(
                        type=types.Type.STRING,
                        description="Optional case-insensitive substring filter for table names.",
                    ),
                    "limit": types.Schema(
                        type=types.Type.INTEGER,
                        description="Maximum tables to return (1-250, default 50).",
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="get_table_ddl",
            description="Inspect raw column names and BigQuery types for one table.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "table_name": types.Schema(
                        type=types.Type.STRING,
                        description="Table name in the target dataset.",
                    ),
                },
                required=["table_name"],
            ),
        ),
        types.FunctionDeclaration(
            name="execute_select_sql",
            description="Validate and execute a single read-only GoogleSQL SELECT query (including GRAPH_TABLE).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "sql": types.Schema(
                        type=types.Type.STRING,
                        description="Single GoogleSQL SELECT statement using backticked dataset.table or project.dataset.table identifiers.",
                    ),
                },
                required=["sql"],
            ),
        ),
    ]


def _build_governed_declarations() -> list[Any]:
    from google.genai import types

    return [
        types.FunctionDeclaration(
            name="search_certified_tables",
            description="Search Knowledge Catalog for certified tables, governance aspects, DQ scores, and table/column descriptions.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "search_term": types.Schema(
                        type=types.Type.STRING,
                        description="Search keywords or '*' to inspect dataset tables with certification status.",
                    ),
                },
                required=["search_term"],
            ),
        ),
        types.FunctionDeclaration(
            name="lookup_catalog_context",
            description="Fetch Knowledge Catalog lookupContext, column descriptions, table constraints, and Business Glossary EntryLink definitions for specific tables.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "table_names": types.Schema(
                        type=types.Type.ARRAY,
                        items=types.Schema(type=types.Type.STRING),
                        description="List of table names in the governed dataset.",
                    ),
                },
                required=["table_names"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_verified_metric_contract",
            description="Retrieve verified semantic metric formulas, fan-trap rules, property graph patterns, or contract SLA extraction rules.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "topic": types.Schema(
                        type=types.Type.STRING,
                        description="Topic keywords (e.g. 'margin', 'metric', 'graph', 'contract', 'sla').",
                    ),
                },
                required=["topic"],
            ),
        ),
        types.FunctionDeclaration(
            name="execute_select_sql",
            description="Validate and execute a single read-only GoogleSQL SELECT query (including GRAPH_TABLE and MEASURE()).",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "sql": types.Schema(
                        type=types.Type.STRING,
                        description="Single GoogleSQL SELECT statement using backticked dataset.table or project.dataset.table identifiers.",
                    ),
                },
                required=["sql"],
            ),
        ),
    ]


def _is_model_unavailable_error(err: Exception) -> bool:
    msg = str(err).lower()
    return (
        "404" in msg
        or "not_found" in msg
        or "not found" in msg
        or "unavailable" in msg
        or "does not have access to" in msg
    )


def _format_args_summary(args: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(args), ensure_ascii=True)
    return raw[:180] + ("..." if len(raw) > 180 else "")


def _normalize_result_rows_for_trust(
    rows_preview: Sequence[Mapping[str, Any]],
    numeric_value: float | None,
) -> list[dict[str, Any]]:
    normalized = [dict(r) for r in rows_preview]
    if not normalized or numeric_value is None:
        return normalized
    first_vals = [_coerce_float(v) for v in normalized[0].values()]
    if any(v is not None and _numbers_close(v, numeric_value, tolerance=0.01) for v in first_vals):
        return normalized
    for idx, row in enumerate(normalized[1:], start=1):
        row_vals = [_coerce_float(v) for v in row.values()]
        if any(v is not None and _numbers_close(v, numeric_value, tolerance=0.01) for v in row_vals):
            reordered = [dict(row)] + normalized[:idx] + normalized[idx + 1 :]
            return reordered
    return normalized


def _finalize_trust_classification(
    *,
    arm: str,
    sql_or_gql: str,
    query_language: str,
    answer_summary: str,
    question: str,
    numeric_value: float | None,
    rows_preview: Sequence[Mapping[str, Any]],
    observed_signals: Sequence[str],
    catalog_context_summary: str,
    error_retries: int,
    passed_grading: bool,
) -> tuple[str, list[str]]:
    lines = (answer_summary or "").splitlines()
    first_line = (lines[0] if lines else "")[:240]
    reconciled_rows = _normalize_result_rows_for_trust(rows_preview, numeric_value)
    assessment = classify_outcome(
        sql_or_gql=sql_or_gql,
        query_language=query_language,
        answer_headline=first_line,
        answer_detail=answer_summary,
        question=question,
        numeric_value=numeric_value,
        result_rows=reconciled_rows,
        context_mechanism=" | ".join(observed_signals) or ("blind_schema_only" if arm == "blind" else "knowledge_catalog"),
        context_payload=catalog_context_summary,
        is_blind=(arm == "blind"),
        error_retries=error_retries,
        has_verified_query_contract=("VERIFIED_METRIC_CONTRACT" in observed_signals),
        strict_prose_reconcile=False,
    )
    tier = assessment.tier.value
    reasons = list(assessment.reasons)
    if arm == "blind" and _TIER_SEVERITY.get(tier, 3) < 3:
        tier = TrustTier.TIER_3_REVIEW_REQUIRED.value
        reasons.append("ungrounded_blind_query")
    if not passed_grading and _TIER_SEVERITY.get(tier, 3) < 3:
        tier = TrustTier.TIER_3_REVIEW_REQUIRED.value
        reasons.append("failed_grading")
    return tier, sorted(set(reasons))


def run_live_agent_arm(
    *,
    pack_id: str,
    rung: Mapping[str, Any],
    arm: str,
    persona_id: str | None = None,
    repo_root: Path | None = None,
    packs_dir: Path | None = None,
    max_turns: int = 4,
    timeout_s: float = 25.0,
    genai_client: Any = None,
    blind_tool_ctx: BlindToolContext | None = None,
    governed_tool_ctx: GovernedToolContext | None = None,
) -> AgentRunResult:
    """Executes one real symmetric Gemini + BigQuery/Knowledge Catalog agent arm."""
    if arm not in {"blind", "governed"}:
        raise ValueError(f"Unsupported arm {arm!r}; expected 'blind' or 'governed'.")

    t0 = time.monotonic()
    root = repo_root or DEFAULT_REPO_ROOT
    settings = resolve_phase2_settings(root, pack_id=pack_id)
    project_id = settings["PROJECT_ID"]
    dataset_id = settings["DATASET_ID"]
    blind_dataset_id = settings["BLIND_DATASET_ID"]
    bq_location = str(rung.get("region") or settings["BQ_LOCATION"] or "asia-southeast1")
    model_id = settings["AGENT_MODEL_ID"]
    model_location = settings["AGENT_MODEL_LOCATION"]
    max_bytes = int(os.environ.get("BQ_MAX_BYTES_BILLED", "104857600") or "104857600")

    try:
        ctx_layer = load_context_layer(
            pack_id,
            packs_dir=packs_dir,
            project_id=project_id,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
    except FileNotFoundError:
        ctx_layer = {}

    agent_sa_map = resolve_agent_sa_map(
        project_id=project_id,
        pack_id=pack_id,
        context_layer=ctx_layer,
    )
    resolved_persona = _resolve_persona_id(rung, persona_id)

    tool_ctx: BlindToolContext | GovernedToolContext
    has_persona_isolation = False
    if arm == "blind":
        if blind_tool_ctx is not None:
            tool_ctx = blind_tool_ctx
        else:
            blind_sa = resolve_execution_sa(
                arm="blind",
                project_id=project_id,
                pack_id=pack_id,
                context_layer=ctx_layer,
                agent_sa_map=agent_sa_map,
            )
            blind_bq = build_impersonated_bq_client(
                target_sa=blind_sa,
                project_id=project_id,
                location=bq_location,
            )
            tool_ctx = BlindToolContext(
                project_id=project_id,
                blind_dataset_id=blind_dataset_id,
                governed_dataset_id=dataset_id,
                bq_location=bq_location,
                bq_client=blind_bq,
                sa_email=blind_sa,
                max_bytes=max_bytes,
            )
        target_dataset = tool_ctx.blind_dataset_id
        declarations = _build_blind_declarations()
    else:
        if governed_tool_ctx is not None:
            tool_ctx = governed_tool_ctx
            has_persona_isolation = tool_ctx.sql_sa_email != tool_ctx.metadata_sa_email
        else:
            gov_meta_sa = resolve_execution_sa(
                arm="governed",
                project_id=project_id,
                pack_id=pack_id,
                persona_id=None,
                context_layer=ctx_layer,
                agent_sa_map=agent_sa_map,
            )
            gov_sql_sa = resolve_execution_sa(
                arm="governed",
                project_id=project_id,
                pack_id=pack_id,
                persona_id=resolved_persona,
                context_layer=ctx_layer,
                agent_sa_map=agent_sa_map,
            )
            has_persona_isolation = gov_sql_sa != gov_meta_sa
            meta_creds = build_impersonated_credentials_for_sa(gov_meta_sa)
            from google.cloud import bigquery

            meta_bq = bigquery.Client(project=project_id, credentials=meta_creds, location=bq_location)
            sql_bq = (
                meta_bq
                if gov_sql_sa == gov_meta_sa
                else build_impersonated_bq_client(
                    target_sa=gov_sql_sa,
                    project_id=project_id,
                    location=bq_location,
                )
            )
            catalog_client = DataplexCatalogRestClient(
                project_id=project_id,
                bq_location=bq_location,
                credentials=meta_creds,
            )
            tool_ctx = GovernedToolContext(
                project_id=project_id,
                dataset_id=dataset_id,
                blind_dataset_id=blind_dataset_id,
                bq_location=bq_location,
                metadata_bq_client=meta_bq,
                sql_bq_client=sql_bq,
                metadata_sa_email=gov_meta_sa,
                sql_sa_email=gov_sql_sa,
                catalog_client=catalog_client,
                context_layer=ctx_layer,
                max_bytes=max_bytes,
            )
        target_dataset = tool_ctx.dataset_id
        declarations = _build_governed_declarations()

    from google import genai
    from google.genai import types

    client = genai_client or genai.Client(
        vertexai=True,
        project=project_id,
        location=model_location,
    )

    system_instruction = (
        f"You are a careful read-only BigQuery SQL/GQL analyst operating exclusively inside dataset "
        f"`{project_id}.{target_dataset}` (location `{bq_location}`).\n"
        f"Rules:\n"
        f"1. Inspect the schema or context using ONLY your declared tools before executing SQL.\n"
        f"2. Write a single valid read-only GoogleSQL SELECT statement (including GRAPH_TABLE when appropriate). "
        f"Fully qualify tables inside `{project_id}.{target_dataset}.<table>` (never use multi-statement SQL or INFORMATION_SCHEMA).\n"
        f"3. Base every numeric claim strictly on actual tool/SQL outputs.\n"
        f"4. Finish with a concise answer ending with a ```json``` block containing keys: "
        f'`{{"answer_summary": string, "numeric_value": number_or_null, "unit": string_or_null}}`.'
    )

    question = str(rung.get("question") or "").strip()
    prompt_user = question
    if resolved_persona and resolved_persona != "default":
        prompt_user = f"{question}\n\nExecution persona scope: {resolved_persona}"

    contents: list[Any] = [types.Content(role="user", parts=[types.Part.from_text(text=prompt_user)])]
    deadline = t0 + max(1.0, float(timeout_s))

    def _turn_config(remaining_s: float) -> Any:
        timeout_ms = max(1000, int(math.ceil(max(0.5, remaining_s) * 1000.0)))
        return types.GenerateContentConfig(
            temperature=0.0,
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=declarations)],
            http_options=types.HttpOptions(timeout=timeout_ms),
        )

    active_model = model_id
    tokens_used = 0
    exploratory_queries = 0
    error_retries = 0
    tool_trace: list[dict[str, Any]] = []
    last_sql = ""
    last_rows: list[dict[str, Any]] = []
    last_refs: list[str] = []
    catalog_snippets: list[str] = []
    final_text = ""

    for turn_idx in range(1, max_turns + 1):
        remaining_s = deadline - time.monotonic()
        if remaining_s <= 0:
            final_text = final_text or f"Execution stopped after reaching {timeout_s:.0f}s budget."
            break

        try:
            response = client.models.generate_content(
                model=active_model,
                contents=contents,
                config=_turn_config(remaining_s),
            )
        except Exception as err:
            if turn_idx == 1 and active_model != _FALLBACK_MODEL_ID and _is_model_unavailable_error(err):
                active_model = _FALLBACK_MODEL_ID
                rem_retry = max(0.5, deadline - time.monotonic())
                response = client.models.generate_content(
                    model=active_model,
                    contents=contents,
                    config=_turn_config(rem_retry),
                )
            else:
                error_retries += 1
                final_text = f"Model invocation failed: {err}"
                break

        usage = getattr(response, "usage_metadata", None)
        if usage is not None:
            turn_total = getattr(usage, "total_token_count", None)
            if turn_total is not None:
                tokens_used += int(turn_total)
            else:
                tokens_used += int(getattr(usage, "prompt_token_count", 0) or 0) + int(
                    getattr(usage, "candidates_token_count", 0) or 0
                )

        candidates = getattr(response, "candidates", None) or []
        model_content = candidates[0].content if candidates and getattr(candidates[0], "content", None) else None
        if model_content is not None:
            contents.append(model_content)

        fn_calls = list(getattr(response, "function_calls", None) or [])
        if not fn_calls:
            final_text = str(getattr(response, "text", "") or "").strip()
            break

        response_parts: list[Any] = []
        for fc in fn_calls:
            fn_name = str(getattr(fc, "name", "") or "")
            raw_args = dict(getattr(fc, "args", None) or {})
            status = "ok"
            result_payload: dict[str, Any]
            exec_remaining = deadline - time.monotonic()
            if exec_remaining <= 0:
                status = "timeout"
                error_retries += 1
                result_payload = {"error": f"Execution budget ({timeout_s:.0f}s) exhausted before tool {fn_name}."}
                tool_trace.append(
                    {
                        "turn": turn_idx,
                        "tool_name": fn_name,
                        "args_summary": _format_args_summary(raw_args),
                        "status": status,
                        "output_preview": json.dumps(result_payload, ensure_ascii=True),
                    }
                )
                response_parts.append(
                    types.Part.from_function_response(name=fn_name, response={"result": result_payload})
                )
                continue

            try:
                if arm == "blind" and isinstance(tool_ctx, BlindToolContext):
                    if fn_name == "list_tables":
                        exploratory_queries += 1
                        result_payload = tool_ctx.list_tables(
                            pattern=str(raw_args.get("pattern") or ""),
                            limit=int(raw_args.get("limit") or 50),
                        )
                    elif fn_name == "get_table_ddl":
                        exploratory_queries += 1
                        result_payload = tool_ctx.get_table_ddl(str(raw_args.get("table_name") or ""))
                    elif fn_name == "execute_select_sql":
                        last_sql = str(raw_args.get("sql") or "")
                        result_payload = tool_ctx.execute_select_sql(last_sql, timeout_s=exec_remaining)
                        last_rows = list(result_payload.get("rows") or [])
                        last_refs = list(result_payload.get("referenced_tables") or [])
                    else:
                        raise AgentContextError(f"Tool {fn_name!r} is not authorized on Blind arm.")
                elif arm == "governed" and isinstance(tool_ctx, GovernedToolContext):
                    if fn_name == "search_certified_tables":
                        exploratory_queries += 1
                        result_payload = tool_ctx.search_certified_tables(str(raw_args.get("search_term") or "*"))
                        catalog_snippets.append(
                            f"search_certified_tables({raw_args.get('search_term')}): "
                            + ", ".join(
                                f"{t['table_name']}[{t['certification_status']}]"
                                for t in (result_payload.get("tables") or [])[:5]
                            )
                        )
                    elif fn_name == "lookup_catalog_context":
                        exploratory_queries += 1
                        result_payload = tool_ctx.lookup_catalog_context(raw_args.get("table_names") or [])
                        catalog_snippets.append(
                            f"lookup_catalog_context({raw_args.get('table_names')}): "
                            + str(result_payload.get("lookup_context") or "")[:240]
                        )
                    elif fn_name == "get_verified_metric_contract":
                        exploratory_queries += 1
                        result_payload = tool_ctx.get_verified_metric_contract(str(raw_args.get("topic") or ""))
                        catalog_snippets.append(
                            f"get_verified_metric_contract({raw_args.get('topic')}): "
                            + ",".join(sorted((result_payload.get("matched_contracts") or {}).keys()))
                        )
                    elif fn_name == "execute_select_sql":
                        last_sql = str(raw_args.get("sql") or "")
                        result_payload = tool_ctx.execute_select_sql(last_sql, timeout_s=exec_remaining)
                        last_rows = list(result_payload.get("rows") or [])
                        last_refs = list(result_payload.get("referenced_tables") or [])
                    else:
                        raise AgentContextError(f"Tool {fn_name!r} is not authorized on Governed arm.")
                else:
                    raise AgentContextError(f"Tool context mismatch for arm {arm!r}.")
            except AgentSqlSecurityError as sec_err:
                status = "blocked"
                error_retries += 1
                result_payload = {"error": str(sec_err), "blocked_by_zero_trust_gate": True}
            except TimeoutError as to_err:
                status = "timeout"
                error_retries += 1
                result_payload = {"error": str(to_err)}
            except Exception as tool_err:
                status = "error"
                error_retries += 1
                result_payload = {"error": str(tool_err)}

            preview_raw = json.dumps(result_payload, ensure_ascii=True)
            tool_trace.append(
                {
                    "turn": turn_idx,
                    "tool_name": fn_name,
                    "args_summary": _format_args_summary(raw_args),
                    "status": status,
                    "output_preview": preview_raw[:240] + ("..." if len(preview_raw) > 240 else ""),
                }
            )
            response_parts.append(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": result_payload},
                )
            )

        if fn_calls and sum(1 for s in tool_trace if s["tool_name"] == "execute_select_sql") > 1:
            exploratory_queries += 1

        contents.append(types.Content(role="user", parts=response_parts))
    else:
        if not final_text:
            final_text = str(getattr(response, "text", "") or "").strip() if "response" in locals() else ""

    answer_summary, numeric_value, _unit = _parse_final_agent_json(final_text)
    if numeric_value is None and last_rows:
        numeric_value = _extract_scalar_from_rows(last_rows)
    if not answer_summary:
        answer_summary = (
            f"Executed {len(last_rows)} row(s) via {last_sql[:80]}..."
            if last_sql
            else "No final response returned."
        )

    catalog_context_summary = " | ".join(catalog_snippets)[:1000]
    observed_signals = extract_observed_signals(
        tool_trace=tool_trace,
        sql_or_gql=last_sql,
        referenced_tables=last_refs,
        catalog_context_summary=catalog_context_summary,
        has_persona_isolation=has_persona_isolation,
    )
    query_lang = _detect_query_language(last_sql)
    passed_grading, grading_reason = grade_agent_outcome(
        rung,
        answer_summary=answer_summary,
        numeric_value=numeric_value,
        sql_or_gql=last_sql,
        rows_preview=last_rows[:20],
        referenced_tables=last_refs,
        persona_id=resolved_persona,
    )
    trust_tier, trust_reasons = _finalize_trust_classification(
        arm=arm,
        sql_or_gql=last_sql,
        query_language=query_lang,
        answer_summary=answer_summary,
        question=question,
        numeric_value=numeric_value,
        rows_preview=last_rows[:20],
        observed_signals=observed_signals,
        catalog_context_summary=catalog_context_summary,
        error_retries=error_retries,
        passed_grading=passed_grading,
    )

    latency_ms = max(1, int(round((time.monotonic() - t0) * 1000)))
    raw_result = AgentRunResult(
        arm=arm,
        answer_summary=answer_summary,
        numeric_value=numeric_value,
        passed_grading=passed_grading,
        grading_reason=grading_reason,
        sql_or_gql=last_sql,
        query_language=query_lang,
        trust_tier=trust_tier,
        trust_reasons=trust_reasons,
        observed_signals=observed_signals,
        tool_trace=tool_trace,
        catalog_context_summary=catalog_context_summary,
        tokens_used=tokens_used,
        exploratory_queries=exploratory_queries,
        error_retries=error_retries,
        latency_ms=latency_ms,
        rows_preview=last_rows[:20],
        model_id=active_model,
        model_location=model_location,
        persona_id=resolved_persona,
    )
    scrub_pid = tool_ctx.project_id if tool_ctx.project_id and tool_ctx.project_id != "example-project-id" else project_id
    raw_dump = json.dumps(raw_result.to_dict(), ensure_ascii=True)
    extra_toks = [tool_ctx.project_id, project_id, os.environ.get("PROJECT_NUMBER", "")]
    extra_toks.extend(_PROJECT_NUM_IN_PATH_RE.findall(raw_dump))
    redacted_dict = redact_bundle_data(
        raw_result.to_dict(),
        extra_tokens=extra_toks,
        live_project_id=scrub_pid,
    )
    return AgentRunResult(**redacted_dict)


def _lookup_identity_variant(rung: Mapping[str, Any], persona_id: str) -> dict[str, Any] | None:
    variants = rung.get("identity_variants")
    if isinstance(variants, Mapping):
        val = variants.get(persona_id)
        return dict(val) if isinstance(val, Mapping) else None
    if isinstance(variants, Sequence) and not isinstance(variants, (str, bytes)):
        for item in variants:
            if isinstance(item, Mapping) and str(item.get("persona_id") or "") == persona_id:
                return dict(item)
    return None


def run_offline_mock_arm(
    *,
    pack_id: str,
    rung: Mapping[str, Any],
    arm: str,
    persona_id: str | None = None,
    repo_root: Path | None = None,
) -> AgentRunResult:
    """Runs deterministic offline mock evaluation exercising real signals, grading, and redaction."""
    if arm not in {"blind", "governed"}:
        raise ValueError(f"Unsupported arm {arm!r}; expected 'blind' or 'governed'.")

    root = repo_root or DEFAULT_REPO_ROOT
    settings = resolve_phase2_settings(root, pack_id=pack_id)
    project_id = settings["PROJECT_ID"]
    model_id = settings["AGENT_MODEL_ID"]
    model_location = settings["AGENT_MODEL_LOCATION"]
    resolved_persona = _resolve_persona_id(rung, persona_id)

    arm_data = dict(rung.get(arm) or (rung.get("arms") or {}).get(arm) or {})
    sql_or_gql = str(arm_data.get("sql_or_gql") or "SELECT 1 AS value")
    rows_preview = [dict(r) for r in (arm_data.get("result_rows") or [])[:20]]
    numeric_value = _coerce_float(arm_data.get("numeric_value"))
    if numeric_value is None:
        numeric_value = _coerce_float(arm_data.get("metric_value"))
    if numeric_value is None and rows_preview:
        numeric_value = _extract_scalar_from_rows(rows_preview)

    answer_headline = str(arm_data.get("answer_headline") or "")
    answer_detail = str(arm_data.get("answer_detail") or "")
    variant = _lookup_identity_variant(rung, resolved_persona) if arm == "governed" else None
    if variant is not None:
        var_num = _coerce_float(variant.get("numeric_value"))
        if not rows_preview and numeric_value is not None and var_num is not None:
            rows_preview = [
                {
                    "primary_metric": numeric_value,
                    "persona_value": var_num,
                    "rows_visible": variant.get("rows_visible"),
                }
            ]
        var_head = str(variant.get("answer_headline") or "").strip()
        var_det = str(variant.get("answer_detail") or "").strip()
        answer_summary = " | ".join(part for part in (answer_headline, var_head, var_det or answer_detail) if part).strip()
    else:
        answer_summary = f"{answer_headline} {answer_detail}".strip()

    mechanism = str(arm_data.get("context_mechanism") or "")
    payload = str(arm_data.get("context_payload") or "")
    cost = dict(arm_data.get("cost") or {})

    if arm == "blind":
        tool_trace = [
            {
                "turn": 1,
                "tool_name": "list_tables",
                "args_summary": '{"pattern": ""}',
                "status": "ok",
                "output_preview": f'{{"dataset_id": "{settings["BLIND_DATASET_ID"]}", "total_tables": 198, "truncated": true}}',
            },
            {
                "turn": 2,
                "tool_name": "execute_select_sql",
                "args_summary": _format_args_summary({"sql": sql_or_gql}),
                "status": "ok",
                "output_preview": json.dumps({"row_count": len(rows_preview)}, ensure_ascii=True),
            },
        ]
    else:
        tool_trace = [
            {
                "turn": 1,
                "tool_name": "search_certified_tables",
                "args_summary": '{"search_term": "*"}',
                "status": "ok",
                "output_preview": '{"certification_status": "CERTIFIED"}',
            },
            {
                "turn": 1,
                "tool_name": "lookup_catalog_context",
                "args_summary": '{"table_names": ["context"]}',
                "status": "ok",
                "output_preview": '{"glossary_definitions": [{"term": "glossary"}]}',
            },
            {
                "turn": 2,
                "tool_name": "execute_select_sql",
                "args_summary": _format_args_summary({"sql": sql_or_gql}),
                "status": "ok",
                "output_preview": json.dumps({"row_count": len(rows_preview)}, ensure_ascii=True),
            },
        ]
        if any(tok in mechanism.lower() for tok in ("contract", "measure", "graph", "metric", "semantic")):
            tool_trace.insert(
                2,
                {
                    "turn": 1,
                    "tool_name": "get_verified_metric_contract",
                    "args_summary": '{"topic": "verified"}',
                    "status": "ok",
                    "output_preview": '{"matched_contracts": ["verified"]}',
                },
            )

    observed_signals = extract_observed_signals(
        tool_trace=tool_trace,
        sql_or_gql=sql_or_gql,
        referenced_tables=[],
        catalog_context_summary=f"{mechanism} | {payload}",
        has_persona_isolation=("rls" in mechanism.lower() or "row access" in mechanism.lower()),
    )

    if rung.get("grading"):
        passed_grading, grading_reason = grade_agent_outcome(
            rung,
            answer_summary=answer_summary,
            numeric_value=numeric_value,
            sql_or_gql=sql_or_gql,
            rows_preview=rows_preview,
            persona_id=resolved_persona,
        )
    else:
        passed_grading = arm == "governed"
        grading_reason = "No grading block in rung; inferred from arm."

    query_lang = str(arm_data.get("query_language") or _detect_query_language(sql_or_gql))
    error_retries = int(
        arm_data["error_retries"]
        if arm_data.get("error_retries") is not None
        else (cost.get("error_retries") or 0)
    )
    tokens_used = int(
        arm_data.get("tokens_used")
        or cost.get("llm_tokens_est")
        or (6400 if arm == "blind" else 2800)
    )
    exploratory_queries = int(
        arm_data["exploratory_queries"]
        if arm_data.get("exploratory_queries") is not None
        else (
            cost["exploratory_queries"]
            if cost.get("exploratory_queries") is not None
            else (6 if arm == "blind" else 2)
        )
    )
    latency_ms = int(
        arm_data.get("latency_ms")
        or cost.get("latency_ms")
        or (1400 if arm == "blind" else 850)
    )
    trust_tier, trust_reasons = _finalize_trust_classification(
        arm=arm,
        sql_or_gql=sql_or_gql,
        query_language=query_lang,
        answer_summary=answer_summary,
        question=str(rung.get("question") or ""),
        numeric_value=numeric_value,
        rows_preview=rows_preview,
        observed_signals=observed_signals,
        catalog_context_summary=payload,
        error_retries=error_retries,
        passed_grading=passed_grading,
    )

    raw_result = AgentRunResult(
        arm=arm,
        answer_summary=answer_summary,
        numeric_value=numeric_value,
        passed_grading=passed_grading,
        grading_reason=grading_reason,
        sql_or_gql=sql_or_gql,
        query_language=query_lang,
        trust_tier=trust_tier,
        trust_reasons=trust_reasons,
        observed_signals=observed_signals,
        tool_trace=tool_trace,
        catalog_context_summary=payload[:500] if arm == "governed" else "",
        tokens_used=tokens_used,
        exploratory_queries=exploratory_queries,
        error_retries=error_retries,
        latency_ms=latency_ms,
        rows_preview=rows_preview,
        model_id=model_id,
        model_location=model_location,
        persona_id=resolved_persona,
    )
    redacted_dict = redact_bundle_data(
        raw_result.to_dict(),
        extra_tokens=[os.environ.get("PROJECT_NUMBER", "")],
        live_project_id=project_id,
    )
    return AgentRunResult(**redacted_dict)
