"""Deterministic zero-leak PCRE/regex scanner for tracked and unignored files."""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
import sys

from engine.pack_loader import DEFAULT_REPO_ROOT, parse_env_file

__all__ = [
    "LeakFinding",
    "main",
    "scan_repo_for_leaks",
    "scan_text_for_leaks",
]

_PLACEHOLDER_PROJECT = "example-project-id"
_PLACEHOLDER_USER_EMAIL = "redacted-user@example.com"

# Patterns are authored using regex character-classes / escapes so the scanner
# never self-triggers when auditing its own source file.
_STRUCTURAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("corp_domain", re.compile(r"\b[a-z0-9-]+\.[c]orp\.google\.com\b", re.IGNORECASE)),
    ("googleplex_domain", re.compile(r"[g]oogleplex\.com\b", re.IGNORECASE)),
    (
        "internal_shortlink",
        re.compile(r"(?:https?://|(?<![A-Za-z0-9_/.:-]))[g]o/[a-z0-9_-]+"),
    ),
    ("goto_domain", re.compile(r"[g]oto\.google\.com\b", re.IGNORECASE)),
    ("depot_path", re.compile(r"/[/]depot/", re.IGNORECASE)),
    ("monorepo_path", re.compile(r"\b[g]oogle3/")),
    ("bug_or_cl_id", re.compile(r"\b(?:b|cl)/[0-9]{4,}\b", re.IGNORECASE)),
    ("internal_chat_url", re.compile(r"[c]hat\.google\.com/", re.IGNORECASE)),
    ("internal_mail_chat", re.compile(r"[m]ail\.google\.com/chat", re.IGNORECASE)),
    ("internal_gtm_token", re.compile(r"\b[c]loud[-][g]tm\b", re.IGNORECASE)),
    ("internal_code_gtap", re.compile(r"\b[g]TAP\b")),
    ("internal_code_edp", re.compile(r"\b[E]DP\b")),
    ("internal_code_bundle_adj", re.compile(r"\b[B]undle\s+[A]djustment\b")),
    ("internal_code_da_fast", re.compile(r"\b[D]A\s+[F]AST\b")),
    ("internal_code_kcmd", re.compile(r"\b[k]cmd\b")),
    ("google_email", re.compile(r"@[g]oogle\.com\b", re.IGNORECASE)),
    ("altostrat_email", re.compile(r"@[a]ltostrat\.com\b", re.IGNORECASE)),
    ("gcp_6digit_project_id", re.compile(r"\b[a-z][a-z0-9-]{3,23}-[0-9]{6}\b")),
)

_SA_EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._+-]+@([a-z0-9-]+)\.iam\.gserviceaccount\.com\b",
    re.IGNORECASE,
)

_SKIP_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".pdf", ".zip", ".pyc"})


@dataclass(frozen=True)
class LeakFinding:
    """Single detected confidentiality or leak policy violation."""

    path: str
    line_num: int
    rule: str
    preview: str


def _resolve_live_project_tokens(
    root_dir: Path,
    extra_project_ids: Iterable[str] | None = None,
) -> list[str]:
    tokens: set[str] = set()
    env_pid = os.environ.get("PROJECT_ID", "").strip()
    if env_pid and env_pid != _PLACEHOLDER_PROJECT:
        tokens.add(env_pid)
    dotenv_vals = parse_env_file(root_dir / ".env")
    dotenv_pid = dotenv_vals.get("PROJECT_ID", "").strip()
    if dotenv_pid and dotenv_pid != _PLACEHOLDER_PROJECT:
        tokens.add(dotenv_pid)
    if extra_project_ids:
        for pid in extra_project_ids:
            cleaned = pid.strip()
            if cleaned and cleaned != _PLACEHOLDER_PROJECT:
                tokens.add(cleaned)
    return sorted(tokens, key=len, reverse=True)


def scan_text_for_leaks(
    text: str,
    *,
    path_label: str = "<memory>",
    forbidden_tokens: Sequence[str] = (),
) -> list[LeakFinding]:
    """Scans text line-by-line for structural leaks and dynamic forbidden tokens."""
    findings: list[LeakFinding] = []
    for line_num, line in enumerate(text.splitlines(), start=1):
        for rule_name, pattern in _STRUCTURAL_PATTERNS:
            for match in pattern.finditer(line):
                findings.append(
                    LeakFinding(
                        path=path_label,
                        line_num=line_num,
                        rule=rule_name,
                        preview=match.group(0)[:48],
                    )
                )

        for sa_match in _SA_EMAIL_PATTERN.finditer(line):
            project_segment = sa_match.group(1).lower()
            if project_segment != _PLACEHOLDER_PROJECT:
                findings.append(
                    LeakFinding(
                        path=path_label,
                        line_num=line_num,
                        rule="non_placeholder_service_account",
                        preview=f"*@{project_segment}.iam.gserviceaccount.com",
                    )
                )

        for tok in forbidden_tokens:
            if tok and tok in line:
                findings.append(
                    LeakFinding(
                        path=path_label,
                        line_num=line_num,
                        rule="live_project_id_leak",
                        preview="[REDACTED_PROJECT_ID]",
                    )
                )

    return findings


def _list_repo_files(root_dir: Path) -> list[Path]:
    git_check = subprocess.run(
        ["git", "-C", str(root_dir), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    if git_check.returncode == 0:
        res = subprocess.run(
            ["git", "-C", str(root_dir), "ls-files", "-co", "--exclude-standard", "-z"],
            capture_output=True,
            check=True,
        )
        raw_paths = [p for p in res.stdout.decode("utf-8", errors="replace").split("\x00") if p]
        return [root_dir / rel for rel in raw_paths if (root_dir / rel).is_file()]

    return sorted(
        p
        for p in root_dir.rglob("*")
        if p.is_file() and ".git" not in p.parts and ".venv" not in p.parts and p.name != ".env"
    )


def scan_repo_for_leaks(
    root_dir: Path | None = None,
    *,
    paths: Sequence[Path] | None = None,
    extra_project_ids: Iterable[str] | None = None,
) -> list[LeakFinding]:
    """Scans tracked and untracked-non-ignored files in root_dir for leak patterns."""
    resolved_root = (root_dir or DEFAULT_REPO_ROOT).resolve()
    forbidden_tokens = _resolve_live_project_tokens(resolved_root, extra_project_ids)

    target_files: list[Path]
    if paths:
        target_files = []
        for p in paths:
            candidate = p if p.is_absolute() else (resolved_root / p)
            if candidate.is_dir():
                target_files.extend(
                    f for f in sorted(candidate.rglob("*")) if f.is_file() and ".git" not in f.parts
                )
            elif candidate.is_file():
                target_files.append(candidate)
    else:
        target_files = _list_repo_files(resolved_root)

    findings: list[LeakFinding] = []
    for file_path in target_files:
        if file_path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        raw_bytes = file_path.read_bytes()
        if b"\x00" in raw_bytes:
            continue
        text = raw_bytes.decode("utf-8", errors="replace")
        try:
            rel_label = str(file_path.resolve().relative_to(resolved_root))
        except ValueError:
            rel_label = str(file_path)
        findings.extend(
            scan_text_for_leaks(
                text,
                path_label=rel_label,
                forbidden_tokens=forbidden_tokens,
            )
        )

    return findings


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for `python -m engine.leak_check [paths...]`."""
    parser = argparse.ArgumentParser(
        description="Deterministic zero-leak scanner across tracked and non-ignored repo files."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional file or directory paths to scan (defaults to git ls-files -co --exclude-standard).",
    )
    parser.add_argument(
        "--root",
        default=str(DEFAULT_REPO_ROOT),
        help="Repository root directory.",
    )
    args = parser.parse_args(argv)

    root_dir = Path(args.root).resolve()
    path_objs = [Path(p) for p in args.paths] if args.paths else None
    findings = scan_repo_for_leaks(root_dir, paths=path_objs)

    if findings:
        for finding in findings:
            print(
                f"LEAK [{finding.rule}] {finding.path}:{finding.line_num}: {finding.preview}",
                file=sys.stderr,
            )
        return 1

    print("Zero-leak check passed (0 findings).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
