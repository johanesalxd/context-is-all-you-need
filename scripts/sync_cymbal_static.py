#!/usr/bin/env python3
"""Syncs, sanitizes, and wires the 3-screen Cymbal static demo into web/cymbal/.

This script is intentionally generic and public-safe: source paths and any
presenter-name replacements are passed via CLI flags at runtime rather than
hardcoded in the repository.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST_DIR = DEFAULT_REPO_ROOT / "web" / "cymbal"

REQUIRED_REL_PATHS = (
    Path("intro_landing/index.html"),
    Path("chat_intro_mockup/index.html"),
    Path("ui_studio_v5/index.html"),
    Path("ui_studio_v5/scenarios/storyline_data_v5.js"),
)

_SAFE_EMAIL_DOMAINS = frozenset({"example.com", "example.org", "example.net"})
_EMAIL_RE = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
_ABS_STUDIO_URL_RE = re.compile(
    r"""https?://[^\s"'<>`]+/(ui_studio_v5/index\.html)"""
)
_DATA_IMG_TAG_RE = re.compile(
    r"""<img\b([^>]*?)\bsrc\s*=\s*(?:"data:image/(?:jpeg|jpg|png|webp);base64,[^"]*"|'data:image/(?:jpeg|jpg|png|webp);base64,[^']*')([^>]*)>""",
    re.IGNORECASE | re.DOTALL,
)
_ALT_ATTR_RE = re.compile(r"""\balt\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)
_CLASS_ATTR_RE = re.compile(r"""\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)

_AVATAR_CSS = """
    .avatar-initials {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 22px;
      letter-spacing: 0.02em;
      color: #ffffff;
      user-select: none;
    }
    .avatar-initials.tone-0 {
      background: linear-gradient(135deg, #1a73e8, #0b57d0);
    }
    .avatar-initials.tone-1 {
      background: linear-gradient(135deg, #137333, #0d652d);
    }
"""

_INDEX_REDIRECT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="0; url=./intro_landing/" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Cymbal Commerce — Context Is All You Need</title>
  <script>window.location.replace("./intro_landing/");</script>
</head>
<body>
  <p>Redirecting to <a href="./intro_landing/">Cymbal Commerce Demo</a>...</p>
</body>
</html>
"""

_INSPECTOR_EVENT_LINE = (
    'document.dispatchEvent(new CustomEvent("v5:inspector", { detail: '
    '(window.__v5LastInspector = { turnId: activeTurnId, mode: activeMode, isSibling: Boolean(isSibling) }) }));'
)


def _html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _compute_initials(label: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", label.strip()) if w]
    if not words:
        return "CC"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    # Apply longest source strings first so full names resolve before partial tokens.
    ordered = sorted(replacements, key=lambda pair: len(pair[0]), reverse=True)
    for old, new in ordered:
        text = text.replace(old, new)
    return text


def _sanitize_emails(text: str) -> str:
    def _repl(match: re.Match[str]) -> str:
        local, domain = match.group(1), match.group(2)
        lowered = domain.lower()
        if lowered in _SAFE_EMAIL_DOMAINS or lowered.endswith(".iam.gserviceaccount.com"):
            return match.group(0)
        return f"{local}@example.com"

    return _EMAIL_RE.sub(_repl, text)


def _rewrite_demo_urls(text: str) -> str:
    return _ABS_STUDIO_URL_RE.sub(r"../\1", text)


def _replace_base64_portraits(text: str) -> str:
    counter = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal counter
        attrs = f"{match.group(1)} {match.group(2)}"
        alt_m = _ALT_ATTR_RE.search(attrs)
        alt_text = (alt_m.group(1) if alt_m and alt_m.group(1) is not None else (alt_m.group(2) if alt_m else "")) or ""
        cls_m = _CLASS_ATTR_RE.search(attrs)
        cls_text = (cls_m.group(1) if cls_m and cls_m.group(1) is not None else (cls_m.group(2) if cls_m else "")) or "avatar-photo"
        initials = _compute_initials(alt_text)
        tone = f"tone-{counter % 2}"
        counter += 1
        aria = _html_escape(alt_text or f"Persona {initials}")
        classes = _html_escape(f"{cls_text} avatar-initials {tone}".strip())
        return f'<div class="{classes}" role="img" aria-label="{aria}">{initials}</div>'

    updated = _DATA_IMG_TAG_RE.sub(_repl, text)
    if counter > 0 and ".avatar-initials" not in updated and "</style>" in updated:
        updated = updated.replace("</style>", f"{_AVATAR_CSS}  </style>", 1)
    return updated


def _instrument_ui_studio_v5(text: str) -> str:
    # 1. Inject live_bridge.js defer script before </body> idempotently.
    if "./live_bridge.js" not in text:
        body_close_re = re.compile(r"</body>", re.IGNORECASE)
        if not body_close_re.search(text):
            raise RuntimeError("Could not locate </body> tag in ui_studio_v5/index.html")
        text = body_close_re.sub('  <script src="./live_bridge.js" defer></script>\n</body>', text, count=1)

    # 2. Instrument renderInspector() so every return path emits v5:inspector.
    if 'new CustomEvent("v5:inspector"' not in text:
        start_anchor = '        var isGov = activeMode === "governed";'
        end_anchor = "        wireInspectorHandlers();\n      }\n\n      function wireInspectorHandlers() {"
        if start_anchor not in text:
            raise RuntimeError("Could not locate activeMode/isGov anchor inside renderInspector()")
        if end_anchor not in text:
            raise RuntimeError("Could not locate end of renderInspector() before wireInspectorHandlers()")

        injected_start = (
            '        var isGov = activeMode === "governed";\n'
            '        var isSibling = Boolean(selectedEntry && selectedEntry.kind === "sibling");\n'
            '        var activeTurnId = selectedEntry ? (isSibling ? (selectedEntry.siblingId || null) '
            ': ((sc.turns[selectedEntry.turnIndex] || {}).id || null)) : null;\n'
            "        (function () {"
        )
        injected_end = (
            "        wireInspectorHandlers();\n"
            "        })();\n"
            f"        {_INSPECTOR_EVENT_LINE}\n"
            "      }\n\n"
            "      function wireInspectorHandlers() {"
        )
        text = text.replace(start_anchor, injected_start, 1)
        text = text.replace(end_anchor, injected_end, 1)

    return text


def _parse_replace_args(raw_pairs: list[str], name_map_path: Path | None) -> list[tuple[str, str]]:
    merged: dict[str, str] = {}
    if name_map_path is not None:
        raw_obj = json.loads(name_map_path.read_text(encoding="utf-8"))
        if not isinstance(raw_obj, dict):
            raise ValueError(f"--name-map file must contain a JSON object: {name_map_path}")
        for k, v in raw_obj.items():
            if not isinstance(k, str) or not isinstance(v, str) or not k:
                raise ValueError(f"Invalid entry in --name-map: {k!r}={v!r}")
            merged[k] = v

    for item in raw_pairs:
        if "=" not in item:
            raise ValueError(f"Invalid --replace argument (expected OLD=NEW): {item!r}")
        old, new = item.split("=", 1)
        if not old:
            raise ValueError(f"Invalid --replace argument with empty OLD key: {item!r}")
        merged[old] = new

    return list(merged.items())


def _file_summary(path: Path, root: Path) -> str:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()[:16]
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        label = str(path.relative_to(root))
    except ValueError:
        label = str(path)
    return f"  {label:<52} sha256:{digest}  bytes={len(raw):>7}  mtime={mtime}"


def sync_cymbal_static(
    *,
    src_dir: Path,
    dest_dir: Path,
    replacements: list[tuple[str, str]],
    run_leak_check: bool = True,
) -> list[Path]:
    src_resolved = src_dir.resolve()
    dest_resolved = dest_dir.resolve()
    if not src_resolved.is_dir():
        raise FileNotFoundError(f"Source directory does not exist: {src_resolved}")

    for rel in REQUIRED_REL_PATHS:
        candidate = src_resolved / rel
        if not candidate.is_file():
            raise FileNotFoundError(f"Required source file missing: {candidate}")

    written_files: list[Path] = []
    dest_resolved.mkdir(parents=True, exist_ok=True)

    # Preserve live_bridge.js untouched across re-syncs if it already exists.
    bridge_path = dest_resolved / "ui_studio_v5" / "live_bridge.js"

    for rel in REQUIRED_REL_PATHS:
        src_file = src_resolved / rel
        out_file = dest_resolved / rel
        out_file.parent.mkdir(parents=True, exist_ok=True)

        text = src_file.read_text(encoding="utf-8")
        text = _apply_replacements(text, replacements)
        text = _rewrite_demo_urls(text)
        if rel in (Path("intro_landing/index.html"), Path("chat_intro_mockup/index.html")):
            text = _replace_base64_portraits(text)
        text = _sanitize_emails(text)
        if rel == Path("ui_studio_v5/index.html"):
            text = _instrument_ui_studio_v5(text)

        if re.search(r"data:image/(?:jpeg|jpg|png|webp);base64,", text, re.IGNORECASE):
            raise RuntimeError(f"Raster base64 data URI remained after sanitization in {rel}")

        out_file.write_text(text, encoding="utf-8")
        written_files.append(out_file)

    index_file = dest_resolved / "index.html"
    index_file.write_text(_INDEX_REDIRECT_HTML, encoding="utf-8")
    written_files.append(index_file)

    if bridge_path.is_file():
        written_files.append(bridge_path)

    print("Synced Cymbal static bundle:")
    for f in written_files:
        print(_file_summary(f, DEFAULT_REPO_ROOT))

    if run_leak_check:
        if str(DEFAULT_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(DEFAULT_REPO_ROOT))
        from engine.leak_check import scan_repo_for_leaks

        findings = scan_repo_for_leaks(
            DEFAULT_REPO_ROOT,
            paths=[dest_resolved, Path(__file__).resolve()],
        )
        if findings:
            for finding in findings:
                print(
                    f"LEAK [{finding.rule}] {finding.path}:{finding.line_num}: {finding.preview}",
                    file=sys.stderr,
                )
            raise RuntimeError(f"Zero-leak verification failed with {len(findings)} finding(s).")
        print("Zero-leak check passed (0 findings).")

    return written_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sync, sanitize, and wire static Cymbal 3-screen demo assets into web/cymbal/."
    )
    parser.add_argument(
        "--src",
        required=True,
        type=Path,
        help="Path to local export directory containing intro_landing/, chat_intro_mockup/, and ui_studio_v5/.",
    )
    parser.add_argument(
        "--dest",
        default=DEFAULT_DEST_DIR,
        type=Path,
        help="Destination directory (default: web/cymbal).",
    )
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Repeatable exact string replacement for anonymization (applied longest-first).",
    )
    parser.add_argument(
        "--name-map",
        default=None,
        type=Path,
        help="Optional JSON file mapping OLD -> NEW replacement strings.",
    )
    parser.add_argument(
        "--no-leak-check",
        action="store_true",
        help="Skip post-sync engine.leak_check verification.",
    )
    args = parser.parse_args(argv)

    replacements = _parse_replace_args(args.replace, args.name_map)
    sync_cymbal_static(
        src_dir=args.src,
        dest_dir=args.dest,
        replacements=replacements,
        run_leak_check=not args.no_leak_check,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
