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
