"""Zero-leak PCRE hygiene and ScenarioPack separation tests."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest

from engine.leak_check import main as leak_main, scan_repo_for_leaks, scan_text_for_leaks
from engine.pack_loader import DEFAULT_REPO_ROOT


def test_repo_passes_zero_leak_scan() -> None:
    findings = scan_repo_for_leaks(DEFAULT_REPO_ROOT)
    assert findings == [], f"Unexpected leak findings: {findings}"

    rc = leak_main(["--root", str(DEFAULT_REPO_ROOT)])
    assert rc == 0


def test_leak_scanner_catches_all_forbidden_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Construct all negative fixtures dynamically so zero leak literals appear in this test file.
    live_pid = "sandbox-live-" + "443322"
    monkeypatch.setenv("PROJECT_ID", live_pid)

    samples = {
        "corp_domain": "host." + "corp.google." + "com",
        "googleplex_domain": "dev." + "googleplex." + "com",
        "internal_shortlink": "See " + "go/" + "internal-doc",
        "goto_domain": "https://" + "goto.google." + "com/test",
        "depot_path": "//" + "depot/" + "branch/file.py",
        "monorepo_path": "path/" + "google" + "3/experimental/foo.py",
        "bug_or_cl_id": "Tracked in " + "b/" + "12345678",
        "bug_or_cl_id_cl": "Reviewed in " + "cl/" + "98765432",
        "internal_chat_url": "https://" + "chat.google." + "com/room/abc",
        "internal_mail_chat": "https://" + "mail.google." + "com/chat/u/0",
        "internal_gtm_token": "team-" + "cloud" + "-gtm",
        "internal_code_gtap": "Program " + "g" + "TAP approved",
        "internal_code_edp": "Signed " + "E" + "DP addendum",
        "internal_code_bundle_adj": "Applied " + "Bundle " + "Adjustment",
        "internal_code_da_fast": "Using " + "DA " + "FAST track",
        "internal_code_kcmd": "Run " + "k" + "cmd now",
        "google_email": "user@" + "google." + "com",
        "google_email_subdomain": "user@" + "sub.google." + "com",
        "altostrat_email": "admin@" + "altostrat." + "com",
        "altostrat_email_subdomain": "admin@" + "team.altostrat." + "com",
        "non_placeholder_email": "exec@" + "customer-realcorp" + ".io",
        "non_placeholder_service_account": "runner@" + "other-proj-99" + ".iam." + "gserviceaccount.com",
        "gcp_6digit_project_id": "my-real-proj-" + "123456",
    }

    for expected_rule, content in samples.items():
        findings = scan_text_for_leaks(content, path_label="fixture.txt")
        rules = {f.rule for f in findings}
        base_rule = expected_rule.removesuffix("_subdomain").removesuffix("_cl")
        assert any(r == base_rule or r == expected_rule for r in rules), (
            f"Expected leak rule {expected_rule} for sample {content!r}, got {rules}"
        )

    # Dynamic PROJECT_ID leak in tmp_path repo & results/*.jsonl
    (tmp_path / "bad_config.txt").write_text(f"project = {live_pid}\n", encoding="utf-8")
    (tmp_path / "results").mkdir()
    (tmp_path / "results" / "live_eval_runs.jsonl").write_text(
        f'{{"project": "{live_pid}", "sa": "agent@{live_pid}.iam.gserviceaccount.com"}}\n',
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(f'PROJECT_ID="{live_pid}"\n', encoding="utf-8")
    repo_findings = scan_repo_for_leaks(tmp_path)
    assert any(f.rule == "live_project_id_leak" for f in repo_findings)
    assert any("results/live_eval_runs.jsonl" in f.path for f in repo_findings)

    # Safe placeholder identifiers must produce 0 findings
    monkeypatch.setenv("PROJECT_ID", "example-project-id")
    safe_text = (
        "PROJECT_ID=example-project-id\n"
        "SA=cfo-regional@example-project-id.iam.gserviceaccount.com\n"
        "contact=demo@example.com\n"
        "org_contact=demo@example.org\n"
        "net_contact=demo@example.net\n"
        "url=https://example.org/docs/go-live\n"
        "decision=Go/No-Go gate\n"
    )
    assert scan_text_for_leaks(safe_text, path_label="safe.txt") == []


def test_engine_and_server_have_zero_hardcoded_scenario_identifiers() -> None:
    forbidden_phrases = [
        "meridian " + "commerce",
        "cfo_" + "regional",
        "sg_" + "coldchain",
        "cold_chain_" + "margin_gold",
        "arctic" + "haul",
        "ln-" + "409",
    ]
    targets: list[Path] = []
    for folder_name in ("engine", "server"):
        targets.extend(sorted((DEFAULT_REPO_ROOT / folder_name).rglob("*.py")))
    prov_ctx = DEFAULT_REPO_ROOT / "scripts" / "provision_context_layer.py"
    if prov_ctx.is_file():
        targets.append(prov_ctx)
    for py_file in targets:
        lowered = py_file.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in lowered, f"Forbidden scenario reference {phrase!r} in {py_file}"


def test_leak_check_cli_exits_zero_cleanly() -> None:
    res = subprocess.run(
        [sys.executable, "-m", "engine.leak_check"],
        cwd=str(DEFAULT_REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "RuntimeWarning" not in res.stderr
