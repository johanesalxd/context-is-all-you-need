#!/usr/bin/env python3
"""Milestone 0 capability preflight probe (--dry-run and --live-gcp)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.error
import urllib.request

from engine.pack_loader import DEFAULT_REPO_ROOT, resolve_env_settings
from engine.rls_impersonation import redact_bundle_data


def _get_bearer_token() -> str:
    res = subprocess.run(
        ["gcloud", "auth", "print-access-token"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [
        ln.strip()
        for ln in res.stdout.splitlines()
        if ln.strip() and not ln.startswith("Created ")
    ]
    if not lines:
        raise RuntimeError("Empty access token from gcloud auth print-access-token")
    return lines[-1]


def _http_json(method: str, url: str, token: str, body: dict | None = None) -> tuple[int, object]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")[:300]


def run_probe(*, live_gcp: bool, repo_root: Path | None = None) -> dict[str, object]:
    root = repo_root or DEFAULT_REPO_ROOT
    settings = resolve_env_settings(root)
    project_id = settings["PROJECT_ID"]
    dataset_id = settings["DATASET_ID"]
    bq_location = settings["BQ_LOCATION"]
    model_id = os.environ.get("AGENT_MODEL_ID", "gemini-3.8-flash").strip()
    model_location = os.environ.get("AGENT_MODEL_LOCATION", "global").strip()

    plan = {
        "mode": "live_gcp" if live_gcp else "dry_run",
        "project_id": "example-project-id" if not live_gcp else project_id,
        "bq_location": bq_location,
        "agent_model_id": model_id,
        "agent_model_location": model_location,
        "checks": [
            f"Vertex Gemini generateContent ({model_location}/{model_id})",
            f"Knowledge Catalog glossaries.list ({bq_location})",
            f"Knowledge Catalog aspectTypes.list ({bq_location})",
            f"Knowledge Catalog dataScans.list ({bq_location})",
            f"Knowledge Catalog lookupContext ({bq_location})",
            f"BigQuery Connection service ({bq_location})",
        ],
    }
    if not live_gcp:
        return redact_bundle_data(plan, extra_tokens=[project_id], live_project_id=project_id)

    if not project_id or project_id == "example-project-id":
        raise RuntimeError("Live probe requires non-placeholder PROJECT_ID in .env or environment")

    token = _get_bearer_token()
    results: dict[str, int] = {}

    st_model, _ = _http_json(
        "POST",
        f"https://aiplatform.googleapis.com/v1/projects/{project_id}/locations/{model_location}/publishers/google/models/{model_id}:generateContent",
        token,
        {"contents": [{"role": "user", "parts": [{"text": "Reply OK"}]}], "generationConfig": {"maxOutputTokens": 8}},
    )
    results["vertex_gemini_model"] = st_model

    for key, path in [
        ("kc_glossaries", f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{bq_location}/glossaries"),
        ("kc_aspect_types", f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{bq_location}/aspectTypes"),
        ("kc_data_scans", f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{bq_location}/dataScans"),
        ("bq_connections", f"https://bigqueryconnection.googleapis.com/v1/projects/{project_id}/locations/{bq_location}/connections"),
    ]:
        code, _ = _http_json("GET", path, token)
        results[key] = code

    st_lc, _ = _http_json(
        "POST",
        f"https://dataplex.googleapis.com/v1/projects/{project_id}/locations/{bq_location}:lookupContext",
        token,
        {
            "resources": [
                f"projects/{project_id}/locations/{bq_location}/entryGroups/@bigquery/entries/bigquery.googleapis.com/projects/{project_id}/datasets/{dataset_id}/tables/orders"
            ]
        },
    )
    results["kc_lookup_context"] = st_lc

    failed = {k: v for k, v in results.items() if v != 200}
    if failed:
        raise RuntimeError(f"M0 capability probe failed on endpoints: {failed}")

    plan["results"] = results
    return redact_bundle_data(plan, extra_tokens=[project_id], live_project_id=project_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe GCP capabilities for Context Is All You Need.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", help="Print planned capability checks without network calls.")
    group.add_argument("--live-gcp", action="store_true", help="Execute live read-only GCP API capability checks.")
    args = parser.parse_args(argv)

    summary = run_probe(live_gcp=bool(args.live_gcp))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
