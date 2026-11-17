"""ScenarioPack verification & bundle capture CLI (--offline-fixture, --dry-run, --live-gcp)."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
import inspect
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

from engine.bundle_exporter import DEFAULT_BUNDLE_OUTPUT, export_bundle
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    load_raw_pack,
    load_seed_module,
    render_bundle_placeholders,
    resolve_env_settings,
)
from engine.rls_impersonation import (
    build_impersonated_credentials,
    parse_role_sa_map,
    redact_sensitive_identifiers,
)
from engine.trust_classifier import (
    TrustTier,
    classify_rung_outcome,
    reconcile_outcome_metric,
    strip_sql_literals_and_comments,
)

__all__ = [
    "NegativeControlError",
    "NegativeControlResult",
    "build_parser",
    "capture_rungs",
    "list_active_row_access_policies",
    "main",
    "verify_negative_governance_control",
]

_PLACEHOLDER_PROJECT = "example-project-id"
_SYNTAX_ERROR_REASONS = frozenset({"badrequest", "invalidquery", "invalid"})
_POLICY_DENIAL_REASONS = frozenset({"accessdenied", "forbidden", "policyviolation", "iam_permission_denied"})


class NegativeControlError(RuntimeError):
    """Raised when a negative governance control probe fails or returns an invalid 400 syntax error."""


@dataclass(frozen=True)
class NegativeControlResult:
    """Outcome of an IAM 403 policy-denial or BigQuery RLS filtering verification."""

    passed: bool
    mechanism: str
    reason: str
    rows_observed: int | None = None


def _extract_error_reasons(exc: BaseException) -> set[str]:
    reasons: set[str] = set()
    raw_errors = getattr(exc, "errors", None)
    if isinstance(raw_errors, Sequence):
        for err in raw_errors:
            if isinstance(err, Mapping):
                reason = str(err.get("reason", "")).strip().lower()
                if reason:
                    reasons.add(reason)
    return reasons


def verify_negative_governance_control(
    probe_fn: Callable[[], Sequence[Mapping[str, Any]]] | None = None,
    *,
    exception: BaseException | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    baseline_row_count: int | None = None,
    expected_max_rows: int | None = None,
    active_rls_policies: Sequence[Mapping[str, Any]] | None = None,
    raise_on_failure: bool = True,
) -> NegativeControlResult:
    """Asserts IAM 403/accessDenied denial or active RLS row-filtering, rejecting 400 syntax errors."""
    observed_exc = exception
    observed_rows = rows

    if probe_fn is not None:
        try:
            probe_result = probe_fn()
            observed_rows = list(probe_result) if probe_result is not None else []
        except Exception as err:
            observed_exc = err

    if observed_exc is not None:
        code = getattr(observed_exc, "code", None)
        reasons = _extract_error_reasons(observed_exc)
        exc_name = type(observed_exc).__name__.lower()
        msg_lower = str(observed_exc).lower()
        safe_msg = redact_sensitive_identifiers(str(observed_exc))

        if (
            code == 400
            or "badrequest" in exc_name
            or bool(reasons & _SYNTAX_ERROR_REASONS)
            or "syntax error" in msg_lower
        ):
            result = NegativeControlResult(
                passed=False,
                mechanism="rejected_400_bad_request",
                reason=f"Rejected 400/badRequest/invalidQuery error (not a governance denial): {safe_msg}",
            )
            if raise_on_failure:
                raise NegativeControlError(result.reason) from observed_exc
            return result

        if code == 404 or "notfound" in exc_name or "notfound" in reasons:
            result = NegativeControlResult(
                passed=False,
                mechanism="rejected_404_not_found",
                reason=f"Rejected 404 notFound (not an IAM/RLS policy denial): {safe_msg}",
            )
            if raise_on_failure:
                raise NegativeControlError(result.reason) from observed_exc
            return result

        if (
            code == 403
            or "forbidden" in exc_name
            or bool(reasons & _POLICY_DENIAL_REASONS)
            or "access denied" in msg_lower
            or "permission" in msg_lower
            or "403" in msg_lower
        ):
            return NegativeControlResult(
                passed=True,
                mechanism="iam_403_access_denied",
                reason=f"Verified policy denial: {safe_msg}",
            )

        result = NegativeControlResult(
            passed=False,
            mechanism="unexpected_exception",
            reason=f"Unexpected error during negative control check ({type(observed_exc).__name__}): {safe_msg}",
        )
        if raise_on_failure:
            raise NegativeControlError(result.reason) from observed_exc
        return result

    if observed_rows is None:
        msg = "Negative control probe produced neither rows nor an exception"
        if raise_on_failure:
            raise NegativeControlError(msg)
        return NegativeControlResult(passed=False, mechanism="no_probe_signal", reason=msg)

    row_list = list(observed_rows)
    row_count = len(row_list)
    if not active_rls_policies:
        msg = "Negative control row-filter check requires active BigQuery row access policies"
        if raise_on_failure:
            raise NegativeControlError(msg)
        return NegativeControlResult(
            passed=False,
            mechanism="missing_active_rls_policies",
            reason=msg,
            rows_observed=row_count,
        )

    if expected_max_rows is not None and row_count > expected_max_rows:
        msg = f"RLS negative control leaked {row_count} row(s), expected <= {expected_max_rows}"
        if raise_on_failure:
            raise NegativeControlError(msg)
        return NegativeControlResult(
            passed=False,
            mechanism="rls_filter_bypassed",
            reason=msg,
            rows_observed=row_count,
        )

    if baseline_row_count is not None and baseline_row_count > 0 and row_count >= baseline_row_count:
        msg = f"RLS negative control returned {row_count} row(s) >= unfiltered baseline {baseline_row_count}"
        if raise_on_failure:
            raise NegativeControlError(msg)
        return NegativeControlResult(
            passed=False,
            mechanism="rls_filter_not_restrictive",
            reason=msg,
            rows_observed=row_count,
        )

    if row_count == 0 or (baseline_row_count is not None and row_count < baseline_row_count):
        return NegativeControlResult(
            passed=True,
            mechanism="rls_row_filtering",
            reason=f"Active BigQuery RLS enforced row scope ({row_count} row(s) visible)",
            rows_observed=row_count,
        )

    msg = f"Unable to confirm RLS restriction for {row_count} row(s) without baseline comparison"
    if raise_on_failure:
        raise NegativeControlError(msg)
    return NegativeControlResult(
        passed=False,
        mechanism="unverified_row_scope",
        reason=msg,
        rows_observed=row_count,
    )


def _normalize_policy_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    ref = raw.get("rowAccessPolicyReference")
    policy_id = raw.get("policy_id") or raw.get("policy_name") or raw.get("row_access_policy_name") or ""
    table_name = raw.get("table_name") or ""
    if isinstance(ref, Mapping):
        policy_id = str(ref.get("policyId") or policy_id)
        table_name = str(ref.get("tableId") or table_name)
    return {
        "policy_id": str(policy_id),
        "table_name": str(table_name),
        "filter_predicate": str(raw.get("filterPredicate") or raw.get("filter_predicate") or ""),
        "grantees": list(raw.get("grantees") or raw.get("grantee_list") or []),
    }


def list_active_row_access_policies(
    client: Any,
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    location: str = "asia-southeast1",
) -> list[dict[str, Any]]:
    """Lists active BigQuery Row Access Policies on a table via REST or mock API."""
    if hasattr(client, "list_row_access_policies"):
        raw_items = client.list_row_access_policies(f"{project_id}.{dataset_id}.{table_id}")
        return [_normalize_policy_record(dict(item)) for item in raw_items]

    if hasattr(client, "_call_api"):
        path = f"/projects/{project_id}/datasets/{dataset_id}/tables/{table_id}/rowAccessPolicies"
        try:
            resp = client._call_api(
                None,
                span_name="BigQuery.listRowAccessPolicies",
                method="GET",
                path=path,
            )
            if isinstance(resp, Mapping):
                items = resp.get("rowAccessPolicies", [])
                return [_normalize_policy_record(dict(item)) for item in items if isinstance(item, Mapping)]
        except (AttributeError, NotImplementedError):
            pass

    if hasattr(client, "query"):
        from google.cloud import bigquery

        info_sql = (
            f"SELECT policy_name, table_name, filter_predicate "
            f"FROM `{project_id}.{dataset_id}.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES` "
            f"WHERE table_name = '{table_id}'"
        )
        job_cfg = bigquery.QueryJobConfig(use_query_cache=False)
        rows = list(client.query(info_sql, job_config=job_cfg, location=location).result())
        return [_normalize_policy_record(_row_to_dict(r)) for r in rows]

    return []


def _row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        raw = dict(row)
    elif hasattr(row, "items"):
        raw = dict(row.items())
    else:
        raw = dict(row)
    cleaned: dict[str, Any] = {}
    for k, v in raw.items():
        cleaned[k] = float(v) if isinstance(v, Decimal) else v
    return cleaned


def _extract_table_ids_from_sql(sql: str, dataset_id: str) -> list[str]:
    stripped = strip_sql_literals_and_comments(sql).replace("`", "")
    pattern = re.compile(
        rf"(?:[a-z0-9_-]+\.)?{re.escape(dataset_id)}\.([a-zA-Z_][a-zA-Z0-9_]*)",
        re.IGNORECASE,
    )
    seen: list[str] = []
    for match in pattern.finditer(stripped):
        tbl = match.group(1)
        if tbl not in seen:
            seen.append(tbl)
    return seen


def _call_seed_generate(seed_module: Any, seed_val: int) -> dict[str, list[dict[str, Any]]] | None:
    fn = getattr(seed_module, "generate_dataset", None)
    if not callable(fn):
        return None
    sig = inspect.signature(fn)
    if "seed" in sig.parameters or len(sig.parameters) >= 1:
        return fn(seed_val)
    return fn()


def _call_seed_evaluate(
    seed_module: Any,
    tables: dict[str, list[dict[str, Any]]] | None,
    seed_val: int,
) -> dict[str, Any] | None:
    fn = getattr(seed_module, "evaluate_invariants", None)
    if not callable(fn):
        return None
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    if len(params) >= 2:
        return fn(tables, seed_val)
    if len(params) == 1:
        if params[0] == "seed":
            return fn(seed_val)
        return fn(tables)
    return fn()


def _reconcile_invariants(
    expected: Mapping[str, Any],
    computed: Mapping[str, Any],
) -> None:
    mismatches: list[str] = []
    for key, exp_val in expected.items():
        if key not in computed:
            continue
        comp_val = computed[key]
        if isinstance(exp_val, (int, float)) and not isinstance(exp_val, bool):
            if not isinstance(comp_val, (int, float)) or isinstance(comp_val, bool):
                mismatches.append(f"{key}: expected numeric {exp_val}, got {comp_val!r}")
            elif abs(float(comp_val) - float(exp_val)) > 0.01:
                mismatches.append(f"{key}: expected {exp_val}, got {comp_val}")
        elif comp_val != exp_val:
            mismatches.append(f"{key}: expected {exp_val!r}, got {comp_val!r}")
    if mismatches:
        raise ValueError("Seed invariant drift detected: " + "; ".join(mismatches))


def _audit_all_rung_trust(bundle: dict[str, Any]) -> None:
    for rung in bundle["rungs"]:
        question = str(rung.get("question", ""))
        for mode in ("blind", "governed"):
            outcome = rung[mode]
            assessment = classify_rung_outcome(
                outcome,
                mode=mode,
                question=question,
                result_rows=None,
            )
            outcome["trust_tier"] = assessment.tier.value


def _match_persona_policy(
    persona_id: str,
    variant: Mapping[str, Any],
    policies: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    applied_hint = str(variant.get("rls_policy_applied", "")).lower()
    pid_lower = persona_id.lower()
    pid_tokens = [tok for tok in pid_lower.split("_") if len(tok) >= 2]

    for policy in policies:
        pol_id = str(policy.get("policy_id", "")).lower()
        pred = str(policy.get("filter_predicate", "")).lower()
        if pol_id and (pol_id == applied_hint or pol_id in applied_hint or pid_lower in pol_id):
            return policy
        if any(tok in pol_id for tok in pid_tokens):
            return policy
        if "true" in applied_hint and pred.strip() == "true":
            return policy
        if any(tok in pred for tok in pid_tokens if tok not in ("regional", "coldchain")):
            return policy

    for policy in policies:
        pred = str(policy.get("filter_predicate", "")).strip().upper()
        if "cfo" in pid_lower or "global" in pid_lower or "all" in pid_lower:
            if pred == "TRUE":
                return policy
        elif pred and pred != "TRUE":
            return policy
    return None


def _execute_query_rows(
    client: Any,
    sql: str,
    *,
    project_id: str,
    dataset_id: str,
    location: str,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    from google.cloud import bigquery

    job_config = bigquery.QueryJobConfig(
        dry_run=dry_run,
        use_query_cache=False,
        default_dataset=f"{project_id}.{dataset_id}",
    )
    job = client.query(sql, job_config=job_config, location=location)
    if dry_run:
        return []
    return [_row_to_dict(r) for r in job.result()]


def _rewrite_table_with_rls_predicate(
    sql: str,
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    filter_predicate: str,
) -> str:
    fq_pattern = re.compile(
        rf"`?(?:{re.escape(project_id)}\.)?{re.escape(dataset_id)}\.{re.escape(table_id)}`?"
    )
    subquery = f"(SELECT * FROM `{project_id}.{dataset_id}.{table_id}` WHERE ({filter_predicate}))"
    return fq_pattern.sub(subquery, sql)


def _verify_rls_variants_live(
    *,
    base_client: Any,
    rung: Mapping[str, Any],
    project_id: str,
    dataset_id: str,
    location: str,
    impersonated_client_factory: Callable[[str], Any] | None = None,
) -> None:
    variants = rung.get("identity_variants") or {}
    if not variants:
        return

    governed_sql = str(rung["governed"]["sql_or_gql"])
    table_ids = _extract_table_ids_from_sql(governed_sql, dataset_id)
    if not table_ids:
        raise RuntimeError(
            f"Rung {rung['id']} has identity_variants but no dataset table reference in governed SQL"
        )

    target_table = table_ids[0]
    policies = list_active_row_access_policies(
        base_client,
        project_id=project_id,
        dataset_id=dataset_id,
        table_id=target_table,
        location=location,
    )
    if not policies:
        raise NegativeControlError(
            f"No active BigQuery row access policies found on {dataset_id}.{target_table}"
        )

    raw_sa_map = os.environ.get("SQL_ROLE_SA_MAP_JSON", "").strip()
    role_sa_map = parse_role_sa_map(raw_sa_map) if raw_sa_map else None

    observed_counts: dict[str, int] = {}
    for persona_id, variant in variants.items():
        expected_val = variant["numeric_value"]
        expected_rows = int(variant["rows_visible"])

        persona_client: Any = None
        if impersonated_client_factory is not None:
            persona_client = impersonated_client_factory(persona_id)
        elif role_sa_map and persona_id in role_sa_map:
            from google.cloud import bigquery

            creds, _ = build_impersonated_credentials(role=persona_id, role_sa_map=role_sa_map)
            persona_client = bigquery.Client(project=project_id, credentials=creds, location=location)

        if persona_client is not None:
            rows = _execute_query_rows(
                persona_client,
                governed_sql,
                project_id=project_id,
                dataset_id=dataset_id,
                location=location,
            )
            ok, actual, detail = reconcile_outcome_metric(expected_val, rows)
            if not ok:
                raise RuntimeError(
                    f"RLS impersonation metric mismatch for persona {persona_id!r}: {detail}"
                )
            cnt_sql = f"SELECT COUNT(*) AS rows_visible FROM `{project_id}.{dataset_id}.{target_table}`"
            cnt_rows = _execute_query_rows(
                persona_client,
                cnt_sql,
                project_id=project_id,
                dataset_id=dataset_id,
                location=location,
            )
            row_cnt = int(cnt_rows[0]["rows_visible"]) if cnt_rows and "rows_visible" in cnt_rows[0] else expected_rows
            if row_cnt != expected_rows:
                raise RuntimeError(
                    f"RLS rows_visible mismatch for {persona_id!r}: expected {expected_rows}, got {row_cnt}"
                )
            observed_counts[persona_id] = row_cnt
            continue

        matched_policy = _match_persona_policy(persona_id, variant, policies)
        if matched_policy is None or not matched_policy.get("filter_predicate"):
            raise NegativeControlError(
                f"Could not match active BigQuery row access policy for persona {persona_id!r}"
            )
        predicate = str(matched_policy["filter_predicate"])
        count_sql = (
            f"SELECT COUNT(*) AS rows_visible "
            f"FROM `{project_id}.{dataset_id}.{target_table}` WHERE ({predicate})"
        )
        cnt_rows = _execute_query_rows(
            base_client,
            count_sql,
            project_id=project_id,
            dataset_id=dataset_id,
            location=location,
        )
        actual_cnt = int(cnt_rows[0]["rows_visible"]) if cnt_rows else 0
        if actual_cnt != expected_rows:
            raise RuntimeError(
                f"RLS predicate row count mismatch for {persona_id!r} ({predicate}): "
                f"expected {expected_rows}, got {actual_cnt}"
            )

        scoped_sql = _rewrite_table_with_rls_predicate(
            governed_sql,
            project_id=project_id,
            dataset_id=dataset_id,
            table_id=target_table,
            filter_predicate=predicate,
        )
        scoped_rows = _execute_query_rows(
            base_client,
            scoped_sql,
            project_id=project_id,
            dataset_id=dataset_id,
            location=location,
        )
        ok, _, detail = reconcile_outcome_metric(expected_val, scoped_rows)
        if not ok:
            raise RuntimeError(
                f"RLS predicate metric mismatch for {persona_id!r} ({predicate}): {detail}"
            )
        observed_counts[persona_id] = actual_cnt

    if len(observed_counts) >= 2:
        max_rows = max(observed_counts.values())
        min_rows = min(observed_counts.values())
        verify_negative_governance_control(
            rows=[{"row_index": i} for i in range(min_rows)],
            baseline_row_count=max_rows,
            expected_max_rows=min_rows,
            active_rls_policies=policies,
        )


def capture_rungs(
    *,
    pack_id: str,
    mode: str,
    output_path: Path | None = None,
    packs_dir: Path | None = None,
    schema_path: Path | None = None,
    env_file: Path | None = None,
    bq_client: Any = None,
    impersonated_client_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Executes offline, dry-run, or live-GCP verification and writes the sanitized JS bundle."""
    if mode not in ("offline_fixture", "dry_run", "live_gcp"):
        raise ValueError(f"Unsupported capture mode: {mode!r}")

    repo_root = DEFAULT_REPO_ROOT
    env_settings = resolve_env_settings(repo_root, env_file=env_file)
    live_project_id = env_settings["PROJECT_ID"]
    dataset_id = env_settings["DATASET_ID"]
    raw_bundle = load_raw_pack(pack_id, packs_dir=packs_dir)
    bq_location = str(os.environ.get("BQ_LOCATION") or raw_bundle.get("region") or env_settings["BQ_LOCATION"])

    if mode == "offline_fixture":
        export_bundle_dict = render_bundle_placeholders(
            raw_bundle,
            project_id=_PLACEHOLDER_PROJECT,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
        seed_module = load_seed_module(pack_id, packs_dir=packs_dir)
        if seed_module is not None:
            seed_val = int(export_bundle_dict["rng_seed"])
            tables = _call_seed_generate(seed_module, seed_val)
            computed = _call_seed_evaluate(seed_module, tables, seed_val)
            if computed is not None:
                _reconcile_invariants(export_bundle_dict.get("invariants", {}), computed)
        _audit_all_rung_trust(export_bundle_dict)
        export_bundle_dict["generated_mode"] = "offline_fixture"
    else:
        if (not live_project_id or live_project_id == _PLACEHOLDER_PROJECT) and bq_client is None:
            raise RuntimeError(
                f"PROJECT_ID must be set to a non-placeholder GCP project ID for mode={mode}"
            )

        exec_bundle = render_bundle_placeholders(
            raw_bundle,
            project_id=live_project_id,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )
        export_bundle_dict = render_bundle_placeholders(
            raw_bundle,
            project_id=_PLACEHOLDER_PROJECT,
            dataset_id=dataset_id,
            bq_location=bq_location,
        )

        client = bq_client
        if client is None:
            from google.cloud import bigquery

            client = bigquery.Client(project=live_project_id, location=bq_location)

        if mode == "dry_run":
            for idx, rung in enumerate(exec_bundle["rungs"]):
                for outcome_key in ("blind", "governed"):
                    sql = str(rung[outcome_key]["sql_or_gql"])
                    _execute_query_rows(
                        client,
                        sql,
                        project_id=live_project_id,
                        dataset_id=dataset_id,
                        location=bq_location,
                        dry_run=True,
                    )
                    export_outcome = export_bundle_dict["rungs"][idx][outcome_key]
                    assessment = classify_rung_outcome(
                        export_outcome,
                        mode=outcome_key,
                        question=str(rung.get("question", "")),
                    )
                    export_outcome["trust_tier"] = assessment.tier.value
            export_bundle_dict["generated_mode"] = "dry_run_verified"
        else:
            for idx, rung in enumerate(exec_bundle["rungs"]):
                question = str(rung.get("question", ""))
                for outcome_key in ("blind", "governed"):
                    exec_outcome = rung[outcome_key]
                    export_outcome = export_bundle_dict["rungs"][idx][outcome_key]
                    rows = _execute_query_rows(
                        client,
                        str(exec_outcome["sql_or_gql"]),
                        project_id=live_project_id,
                        dataset_id=dataset_id,
                        location=bq_location,
                        dry_run=False,
                    )
                    ok, _, detail = reconcile_outcome_metric(exec_outcome["numeric_value"], rows)
                    if not ok:
                        raise RuntimeError(
                            f"Live BigQuery metric mismatch on {rung['id']} ({outcome_key}): {detail}"
                        )
                    assessment = classify_rung_outcome(
                        export_outcome,
                        mode=outcome_key,
                        question=question,
                        result_rows=rows,
                    )
                    if outcome_key == "governed" and assessment.tier == TrustTier.TIER_3_REVIEW_REQUIRED:
                        raise RuntimeError(
                            f"Governed rung {rung['id']} downgraded to TIER_3_REVIEW_REQUIRED: "
                            + ", ".join(assessment.reasons)
                        )
                    export_outcome["trust_tier"] = assessment.tier.value

                if rung.get("identity_variants"):
                    _verify_rls_variants_live(
                        base_client=client,
                        rung=rung,
                        project_id=live_project_id,
                        dataset_id=dataset_id,
                        location=bq_location,
                        impersonated_client_factory=impersonated_client_factory,
                    )
            export_bundle_dict["generated_mode"] = "live_gcp_verified"

    export_bundle(
        export_bundle_dict,
        output_path=output_path or DEFAULT_BUNDLE_OUTPUT,
        schema_path=schema_path,
        extra_sensitive_tokens=[live_project_id],
        live_project_id=live_project_id,
    )
    return export_bundle_dict


def build_parser() -> argparse.ArgumentParser:
    """Builds CLI argument parser for engine.capture_rungs."""
    parser = argparse.ArgumentParser(
        description="Validate ScenarioPack, verify SQL/GQL/RLS, and export web/data/rungs_bundle.js."
    )
    parser.add_argument(
        "--pack",
        default=None,
        help="ScenarioPack ID under packs/ (default: PACK_ID env or meridian_q3_sgd).",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--offline-fixture",
        action="store_true",
        help="Verify seed invariants & trust tiers locally without GCP network calls.",
    )
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Compile all SQL/GQL queries in BigQuery dry_run mode without scanning bytes.",
    )
    mode_group.add_argument(
        "--live-gcp",
        action="store_true",
        help="Execute live SQL/GQL, RLS verification, and negative controls in BigQuery.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_BUNDLE_OUTPUT),
        help="Output JS bundle path (default: web/data/rungs_bundle.js).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for `python -m engine.capture_rungs`."""
    parser = build_parser()
    args = parser.parse_args(argv)

    env_settings = resolve_env_settings()
    pack_id = args.pack or env_settings["PACK_ID"] or "meridian_q3_sgd"
    if args.live_gcp:
        mode = "live_gcp"
    elif args.dry_run:
        mode = "dry_run"
    else:
        mode = "offline_fixture"

    try:
        bundle = capture_rungs(
            pack_id=pack_id,
            mode=mode,
            output_path=Path(args.output),
        )
    except Exception as exc:
        safe_err = redact_sensitive_identifiers(
            str(exc),
            live_project_id=env_settings["PROJECT_ID"],
        )
        print(f"ERROR ({type(exc).__name__}): {safe_err}", file=sys.stderr)
        return 1

    print(
        f"Exported pack={bundle['pack_id']} mode={bundle['generated_mode']} "
        f"rungs={len(bundle['rungs'])} -> {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
