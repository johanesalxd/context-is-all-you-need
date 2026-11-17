"""Empirical N=5 evaluation harness for Blind vs. Governed live agent runs."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any

from engine.bundle_exporter import LeakDetectedError, export_bundle
from engine.leak_check import scan_text_for_leaks
from engine.live_agent import AgentRunResult, run_live_agent_arm, run_offline_mock_arm
from engine.pack_loader import (
    DEFAULT_REPO_ROOT,
    load_pack,
    resolve_env_settings,
    resolve_phase2_settings,
)
from engine.rls_impersonation import redact_bundle_data

__all__ = [
    "build_empirical_eval",
    "main",
    "run_eval_harness",
    "select_median_token_representative",
]


def select_median_token_representative(runs: Sequence[AgentRunResult]) -> AgentRunResult:
    """Selects the representative run at the median of tokens_used."""
    if not runs:
        raise ValueError("Cannot select representative from empty runs list.")
    sorted_runs = sorted(runs, key=lambda r: (int(r.tokens_used), int(r.latency_ms)))
    return sorted_runs[len(sorted_runs) // 2]


def build_empirical_eval(runs: Sequence[AgentRunResult]) -> dict[str, Any]:
    """Computes schema-compliant EmpiricalEval summary from N runs using median-token selection."""
    rep = select_median_token_representative(runs)
    return {
        "model_id": rep.model_id or "gemini-3.8-flash",
        "model_location": rep.model_location or "global",
        "runs": len(runs),
        "pass_count": sum(1 for r in runs if r.passed_grading),
        "median_tokens": max(0, int(rep.tokens_used)),
        "median_exploratory_queries": max(0, int(rep.exploratory_queries)),
        "median_error_retries": max(0, int(rep.error_retries)),
        "median_latency_ms": float(max(0, rep.latency_ms)),
        "sample_sql_or_gql": rep.sql_or_gql,
        "observed_signals": list(rep.observed_signals),
    }


def _default_persona_for_rung(rung: Mapping[str, Any]) -> str | None:
    if isinstance(rung.get("default_persona"), str) and rung["default_persona"].strip():
        return rung["default_persona"].strip()
    variants = rung.get("identity_variants")
    if isinstance(variants, Mapping) and variants:
        return str(next(iter(variants.keys())))
    if isinstance(variants, Sequence) and not isinstance(variants, (str, bytes)) and variants and isinstance(variants[0], Mapping):
        pid = str(variants[0].get("persona_id") or "").strip()
        if pid:
            return pid
    grading = rung.get("grading")
    if isinstance(grading, Mapping):
        pts = grading.get("persona_targets")
        if isinstance(pts, Mapping) and pts:
            return str(next(iter(pts.keys())))
    return None


def _resolve_pack_runner_mode(
    *,
    live_gcp: bool,
    agent_runner: Callable[..., AgentRunResult] | None,
) -> Callable[..., AgentRunResult]:
    if agent_runner is not None:
        return agent_runner
    if live_gcp:
        return run_live_agent_arm
    return run_offline_mock_arm


def run_eval_harness(
    *,
    pack_id: str,
    runs: int = 5,
    live_gcp: bool = False,
    jsonl_out: Path | None = None,
    bundle_out: Path | None = None,
    repo_root: Path | None = None,
    packs_dir: Path | None = None,
    rung_filter: Sequence[str] | None = None,
    agent_runner: Callable[..., AgentRunResult] | None = None,
) -> dict[str, Any]:
    """Runs N iterations across rungs x (blind, governed), writes redacted JSONL & bundle."""
    if runs < 1:
        raise ValueError(f"runs must be >= 1, got {runs}")

    root = (repo_root or DEFAULT_REPO_ROOT).resolve()
    env_defaults = resolve_env_settings(root)
    settings = resolve_phase2_settings(root, pack_id=pack_id)
    live_pid = settings["PROJECT_ID"] if live_gcp else env_defaults.get("PROJECT_ID", "example-project-id")
    if live_gcp and (not live_pid or live_pid == "example-project-id"):
        raise RuntimeError("PROJECT_ID must be set to a live project ID for --live-gcp evaluation.")

    bundle = load_pack(
        pack_id,
        packs_dir=packs_dir,
        project_id=settings["PROJECT_ID"] if live_gcp else "example-project-id",
        dataset_id=settings["DATASET_ID"] if live_gcp else None,
        bq_location=settings["BQ_LOCATION"],
        validate=False,
    )

    runner_fn = _resolve_pack_runner_mode(live_gcp=live_gcp, agent_runner=agent_runner)
    allowed_rungs = {r.strip() for r in (rung_filter or []) if r.strip()}
    jsonl_records: list[dict[str, Any]] = []
    timestamp_utc = datetime.now(timezone.utc).isoformat()

    for rung in bundle.get("rungs") or []:
        rung_id = str(rung.get("id") or "")
        if allowed_rungs and rung_id not in allowed_rungs:
            continue
        persona_id = _default_persona_for_rung(rung)

        for arm in ("blind", "governed"):
            arm_runs: list[AgentRunResult] = []
            for iter_idx in range(1, runs + 1):
                if live_gcp or agent_runner is not None:
                    res = runner_fn(
                        pack_id=pack_id,
                        rung=rung,
                        arm=arm,
                        persona_id=persona_id,
                        repo_root=root,
                        packs_dir=packs_dir,
                    )
                else:
                    res = runner_fn(
                        pack_id=pack_id,
                        rung=rung,
                        arm=arm,
                        persona_id=persona_id,
                        repo_root=root,
                    )
                arm_runs.append(res)
                raw_record = {
                    "timestamp_utc": timestamp_utc,
                    "pack_id": pack_id,
                    "rung_id": rung_id,
                    "rung_num": rung.get("rung_num"),
                    "arm": arm,
                    "run_index": iter_idx,
                    "mode": "live_gcp" if live_gcp else "offline_mock",
                    **res.to_dict(),
                }
                extra_toks = [t for t in (live_pid, os.environ.get("PROJECT_NUMBER", "")) if t and t != "example-project-id"]
                redacted_record = redact_bundle_data(raw_record, extra_tokens=extra_toks, live_project_id=live_pid)
                jsonl_records.append(redacted_record)

            emp_eval = build_empirical_eval(arm_runs)
            outcome_obj = rung.get(arm)
            if isinstance(outcome_obj, dict):
                outcome_obj["empirical_eval"] = emp_eval

    if live_gcp:
        bundle["generated_mode"] = "live_agent_verified"

    forbidden_toks = [t for t in (live_pid, os.environ.get("PROJECT_NUMBER", "")) if t and t != "example-project-id"]
    if jsonl_out is not None:
        out_jsonl = jsonl_out if jsonl_out.is_absolute() else (root / jsonl_out)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        for idx, rec in enumerate(jsonl_records, start=1):
            line = json.dumps(rec, ensure_ascii=True)
            findings = scan_text_for_leaks(
                line,
                path_label=str(out_jsonl),
                forbidden_tokens=forbidden_toks,
            )
            if findings:
                summary = ", ".join(f"{f.rule}:{f.preview}" for f in findings)
                raise LeakDetectedError(
                    f"Aborted JSONL export at record #{idx} due to leak pattern(s): {summary}"
                )
            lines.append(line)
        out_jsonl.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    exported_path: Path | None = None
    if bundle_out is not None:
        out_bundle = bundle_out if bundle_out.is_absolute() else (root / bundle_out)
        exported_path = export_bundle(
            bundle,
            output_path=out_bundle,
            live_project_id=live_pid if live_pid != "example-project-id" else None,
        )

    return {
        "pack_id": pack_id,
        "runs": runs,
        "live_gcp": live_gcp,
        "generated_mode": bundle.get("generated_mode"),
        "records_count": len(jsonl_records),
        "jsonl_out": str(jsonl_out) if jsonl_out else None,
        "bundle_out": str(exported_path) if exported_path else None,
        "bundle": redact_bundle_data(bundle, live_project_id=live_pid),
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run N-iteration Blind vs. Governed evaluation harness and export bundle/JSONL."
    )
    parser.add_argument("--pack", default="meridian_q3_sgd", help="Scenario pack ID under packs/.")
    parser.add_argument("--runs", type=int, default=None, help="Iterations per arm per rung (default EVAL_RUNS or 5).")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--offline-mock", action="store_true", help="Run deterministic offline mock harness.")
    mode_group.add_argument("--live-gcp", action="store_true", help="Run live Gemini + BigQuery/KC evaluation.")
    parser.add_argument("--jsonl-out", default="results/live_eval_runs.jsonl", help="Redacted per-run JSONL output path.")
    parser.add_argument("--bundle-out", default="web/data/rungs_bundle.js", help="Validated JS bundle output path.")
    parser.add_argument("--rungs", default="", help="Optional comma-separated rung IDs to filter.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    settings = resolve_phase2_settings(DEFAULT_REPO_ROOT, pack_id=args.pack)
    runs = args.runs if args.runs is not None else int(settings.get("EVAL_RUNS") or "5")
    rung_filter = [part.strip() for part in args.rungs.split(",") if part.strip()] if args.rungs else None

    result = run_eval_harness(
        pack_id=args.pack,
        runs=runs,
        live_gcp=bool(args.live_gcp),
        jsonl_out=Path(args.jsonl_out) if args.jsonl_out else None,
        bundle_out=Path(args.bundle_out) if args.bundle_out else None,
        rung_filter=rung_filter,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "pack_id": result["pack_id"],
                "runs": result["runs"],
                "live_gcp": result["live_gcp"],
                "generated_mode": result["generated_mode"],
                "records_count": result["records_count"],
                "jsonl_out": result["jsonl_out"],
                "bundle_out": result["bundle_out"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
