"""Tests for Cloud Run live runner security, rate-limiting, byte-cap, and deploy dry-run."""

from __future__ import annotations

from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

from engine.pack_loader import DEFAULT_REPO_ROOT
from server.app import create_app


def test_demo_share_token_blocks_unauthorized_and_accepts_header_or_query(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEMO_SHARE_TOKEN", "secret-stage-token-123")
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    # By default REQUIRE_TOKEN_FOR_RUN_RUNG is false (zero-prompt Stage demo),
    # while live agent token gating defaults to true.
    monkeypatch.delenv("REQUIRE_TOKEN_FOR_RUN_RUNG", raising=False)
    default_app = create_app(env_file=tmp_path / "nonexistent.env")
    default_client = TestClient(default_app)
    default_health = default_client.get("/api/health").json()
    assert default_health["share_token_required"] is False
    assert default_health["live_agent_enabled"] is True
    assert default_health["live_agent_token_required"] is True
    assert default_health["agent_model_id"] == "gemini-3.8-flash"
    assert default_health["agent_model_location"] == "global"

    # When REQUIRE_TOKEN_FOR_RUN_RUNG=true, /api/run-rung enforces DEMO_SHARE_TOKEN
    monkeypatch.setenv("REQUIRE_TOKEN_FOR_RUN_RUNG", "true")
    app = create_app(env_file=tmp_path / "nonexistent.env")
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["share_token_required"] is True
    assert "secret-stage-token-123" not in health.text

    # Missing token -> 401
    denied = client.post(
        "/api/run-rung",
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema", "mode": "governed"},
    )
    assert denied.status_code == 401

    # Wrong token -> 401
    wrong = client.post(
        "/api/run-rung",
        headers={"X-Demo-Key": "wrong-token"},
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema", "mode": "governed"},
    )
    assert wrong.status_code == 401

    # Valid X-Demo-Key header -> 200
    ok_header = client.post(
        "/api/run-rung",
        headers={"X-Demo-Key": "secret-stage-token-123"},
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema", "mode": "governed"},
    )
    assert ok_header.status_code == 200
    assert ok_header.json()["numeric_value"] == 1312450.0

    # Valid ?key= query param -> 200
    ok_query = client.post(
        "/api/run-rung?key=secret-stage-token-123",
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r3_metrics", "mode": "governed"},
    )
    assert ok_query.status_code == 200
    assert ok_query.json()["numeric_value"] == 31.8


def test_rate_limiter_enforces_rpm_ceiling(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("DEMO_SHARE_TOKEN", raising=False)
    monkeypatch.setenv("RUN_RUNG_RPM_LIMIT", "2")
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    app = create_app(env_file=tmp_path / "nonexistent.env")
    client = TestClient(app)

    for _ in range(2):
        res = client.post(
            "/api/run-rung",
            headers={"X-Forwarded-For": "10.0.0.5, 203.0.113.10"},
            json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema", "mode": "governed"},
        )
        assert res.status_code == 200

    throttled = client.post(
        "/api/run-rung",
        headers={"X-Forwarded-For": "192.0.2.99, 203.0.113.10"},
        json={"pack_id": "meridian_q3_sgd", "rung_id": "r1_schema", "mode": "governed"},
    )
    assert throttled.status_code == 429


def test_deploy_and_teardown_cloud_run_dry_run_flags() -> None:
    deploy_script = DEFAULT_REPO_ROOT / "scripts" / "deploy_cloud_run.sh"
    res = subprocess.run(
        ["bash", str(deploy_script), "--dry-run"],
        cwd=DEFAULT_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "[DRY-RUN] Cloud Run foundation deployment plan:" in res.stdout
    assert "meridian-web-runner@" in res.stdout
    assert "meridian-blind-agent@" in res.stdout
    assert "meridian-governed-agent@" in res.stdout
    assert "aiplatform.user" in res.stdout
    deploy_src = deploy_script.read_text(encoding="utf-8")
    assert "cold_chain_margin_gold" not in deploy_src

    teardown_script = DEFAULT_REPO_ROOT / "scripts" / "teardown_pack.sh"
    res_td = subprocess.run(
        ["bash", str(teardown_script), "--dry-run", "--delete-cloud-run"],
        cwd=DEFAULT_REPO_ROOT,
        env={"PATH": "/usr/bin:/bin", "PROJECT_ID": "demo-sandbox-123", "DATASET_ID": "meridian_commerce"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_td.returncode == 0, res_td.stderr
    assert "Cloud Run service" in res_td.stdout
    assert "Phase 2 context layer" in res_td.stdout


def test_deploy_cloud_run_app_only_dry_run_skips_bootstrap_and_preserves_dotenv() -> None:
    deploy_script = DEFAULT_REPO_ROOT / "scripts" / "deploy_cloud_run.sh"
    dotenv_path = DEFAULT_REPO_ROOT / ".env"
    dotenv_before = dotenv_path.read_bytes() if dotenv_path.is_file() else None

    res = subprocess.run(
        ["bash", str(deploy_script), "--app-only", "--dry-run"],
        cwd=DEFAULT_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, res.stderr
    assert "--app-only" in res.stdout
    assert "[DRY RUN] --app-only" in res.stdout
    assert "--env-vars-file" not in res.stdout

    dotenv_after = dotenv_path.read_bytes() if dotenv_path.is_file() else None
    assert dotenv_before == dotenv_after


def test_deploy_cloud_run_app_only_live_stub_and_guardrails(tmp_path: Path) -> None:
    deploy_script = DEFAULT_REPO_ROOT / "scripts" / "deploy_cloud_run.sh"
    dotenv_path = DEFAULT_REPO_ROOT / ".env"
    dotenv_before = dotenv_path.read_bytes() if dotenv_path.is_file() else None

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_file = tmp_path / "gcloud_calls.log"
    stub_gcloud = bin_dir / "gcloud"
    stub_gcloud.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "${GCLOUD_LOG_FILE}"
if [[ "${1:-}" == "run" && "${2:-}" == "services" && "${3:-}" == "describe" ]]; then
  mode="${STUB_DESCRIBE_MODE:-ok}"
  if [[ "${mode}" == "not_found" ]]; then
    echo "ERROR: (gcloud.run.services.describe) NOT_FOUND: Service not found." >&2
    exit 1
  elif [[ "${mode}" == "auth_error" ]]; then
    echo "ERROR: (gcloud.run.services.describe) PERMISSION_DENIED: Caller lacks run.services.get" >&2
    exit 1
  elif [[ "${mode}" == "empty_url" ]]; then
    exit 0
  fi
  echo "https://context-stub-uc.a.run.app"
  exit 0
fi
if [[ "${1:-}" == "run" && "${2:-}" == "deploy" ]]; then
  exit 0
fi
echo "UNEXPECTED GCLOUD CALL: $*" >&2
exit 99
""",
        encoding="utf-8",
    )
    stub_gcloud.chmod(0o755)

    base_env = {
        "PATH": f"{bin_dir}:/usr/bin:/bin",
        "HOME": str(tmp_path),
        "PROJECT_ID": "example-sandbox-42",
        "GCLOUD_LOG_FILE": str(log_file),
    }

    # 1. Conflicting flags --app-only + --rotate-token and --app-only + --pack must exit 2
    res_rot = subprocess.run(
        ["bash", str(deploy_script), "--app-only", "--rotate-token"],
        cwd=DEFAULT_REPO_ROOT,
        env=base_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_rot.returncode == 2

    res_pack = subprocess.run(
        ["bash", str(deploy_script), "--app-only", "--pack", "meridian_q3_sgd"],
        cwd=DEFAULT_REPO_ROOT,
        env=base_env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_pack.returncode == 2
    assert "PACK_ID" in res_pack.stderr

    # 2. Live --app-only happy path: calls describe + minimal deploy without --env-vars-file / IAM mutations
    res_ok = subprocess.run(
        ["bash", str(deploy_script), "--app-only"],
        cwd=DEFAULT_REPO_ROOT,
        env={**base_env, "STUB_DESCRIBE_MODE": "ok"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_ok.returncode == 0, res_ok.stderr
    assert "Deployed Cloud Run Service (--app-only): https://context-stub-uc.a.run.app" in res_ok.stdout
    calls = log_file.read_text(encoding="utf-8").splitlines()
    deploy_calls = [c for c in calls if c.startswith("run deploy ")]
    assert len(deploy_calls) == 1
    assert "--env-vars-file" not in deploy_calls[0]
    assert "--service-account" not in deploy_calls[0]
    assert "--allow-unauthenticated" not in deploy_calls[0]
    assert "--labels" not in deploy_calls[0]

    # 3. Fail-fast when service does not exist vs auth/permission error
    res_nf = subprocess.run(
        ["bash", str(deploy_script), "--app-only"],
        cwd=DEFAULT_REPO_ROOT,
        env={**base_env, "STUB_DESCRIBE_MODE": "not_found"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_nf.returncode == 1
    assert "Run a full deploy first" in res_nf.stderr

    res_auth = subprocess.run(
        ["bash", str(deploy_script), "--app-only"],
        cwd=DEFAULT_REPO_ROOT,
        env={**base_env, "STUB_DESCRIBE_MODE": "auth_error"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_auth.returncode == 1
    assert "PERMISSION_DENIED" in res_auth.stderr
    assert "was not found" not in res_auth.stderr

    res_empty = subprocess.run(
        ["bash", str(deploy_script), "--app-only"],
        cwd=DEFAULT_REPO_ROOT,
        env={**base_env, "STUB_DESCRIBE_MODE": "empty_url"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_empty.returncode == 1
    assert "returned an empty status.url" in res_empty.stderr

    dotenv_after = dotenv_path.read_bytes() if dotenv_path.is_file() else None
    assert dotenv_before == dotenv_after


def test_spin_up_and_spin_down_dry_run_and_bash_syntax() -> None:
    scripts = [
        DEFAULT_REPO_ROOT / "scripts" / "spin_up.sh",
        DEFAULT_REPO_ROOT / "scripts" / "spin_down.sh",
        DEFAULT_REPO_ROOT / "scripts" / "teardown_pack.sh",
        DEFAULT_REPO_ROOT / "scripts" / "deploy_cloud_run.sh",
        DEFAULT_REPO_ROOT / "scripts" / "provision_pack.sh",
    ]
    for s in scripts:
        assert s.is_file(), f"Missing script: {s}"
        syn = subprocess.run(["bash", "-n", str(s)], capture_output=True, text=True, check=False)
        assert syn.returncode == 0, f"bash -n failed for {s}: {syn.stderr}"

    up_res = subprocess.run(
        ["bash", str(DEFAULT_REPO_ROOT / "scripts" / "spin_up.sh"), "--dry-run"],
        cwd=DEFAULT_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up_res.returncode == 0, up_res.stderr
    assert "[DRY-RUN] ScenarioPack BigQuery foundation plan:" in up_res.stdout
    assert '"mode": "provision"' in up_res.stdout
    assert "[DRY-RUN] Cloud Run foundation deployment plan:" in up_res.stdout

    down_res = subprocess.run(
        ["bash", str(DEFAULT_REPO_ROOT / "scripts" / "spin_down.sh"), "--dry-run"],
        cwd=DEFAULT_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert down_res.returncode == 0, down_res.stderr
    assert "Phase 2 context layer" in down_res.stdout
    assert "Cloud Run service" in down_res.stdout
    assert "Artifact Registry package" in down_res.stdout
    assert "Firestore Native poll database" in down_res.stdout
    assert "dedicated RLS SAs" in down_res.stdout



