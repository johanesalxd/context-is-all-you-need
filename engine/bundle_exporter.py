"""Schema-validated, leak-checked JS bundle exporter for offline Stage/Workbench UI."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import copy
import json
from pathlib import Path
from typing import Any

from engine.leak_check import scan_text_for_leaks
from engine.pack_loader import DEFAULT_REPO_ROOT, validate_bundle
from engine.rls_impersonation import redact_bundle_data

__all__ = ["LeakDetectedError", "export_bundle"]

DEFAULT_BUNDLE_OUTPUT = DEFAULT_REPO_ROOT / "web" / "data" / "rungs_bundle.js"


class LeakDetectedError(RuntimeError):
    """Raised when exported bundle output fails the zero-leak scan."""


def export_bundle(
    bundle: Mapping[str, Any],
    *,
    output_path: Path | None = None,
    schema_path: Path | None = None,
    extra_sensitive_tokens: Iterable[str] | None = None,
    live_project_id: str | None = None,
) -> Path:
    """Redacts sensitive identifiers, validates schema, scans for leaks, and writes JS bundle."""
    target = output_path or DEFAULT_BUNDLE_OUTPUT

    sanitized = redact_bundle_data(
        copy.deepcopy(dict(bundle)),
        extra_tokens=extra_sensitive_tokens,
        live_project_id=live_project_id,
    )
    validate_bundle(sanitized, schema_path=schema_path)

    json_payload = json.dumps(sanitized, indent=2, ensure_ascii=False).replace("</", "<\\/")
    js_content = f"window.CONTEXT_PACK_BUNDLE = {json_payload};\n"

    forbidden: list[str] = []
    if live_project_id and live_project_id != "example-project-id":
        forbidden.append(live_project_id)
    if extra_sensitive_tokens:
        for tok in extra_sensitive_tokens:
            if tok and tok != "example-project-id":
                forbidden.append(tok)

    findings = scan_text_for_leaks(
        js_content,
        path_label=str(target),
        forbidden_tokens=forbidden,
    )
    if findings:
        rules = ", ".join(sorted({f.rule for f in findings}))
        raise LeakDetectedError(
            f"Refusing to write {target}: detected {len(findings)} leak(s) [{rules}]"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(js_content, encoding="utf-8")
    return target
