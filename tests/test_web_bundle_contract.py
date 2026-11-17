"""Contract tests for the offline-safe dual-mode web UI and fallback bundle."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import jsonschema

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"
SCHEMA_PATH = REPO_ROOT / "schemas" / "rung_v2.schema.json"
README_PATH = REPO_ROOT / "README.md"


class _ScriptSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[dict[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            attr_map = {k.lower(): v for k, v in attrs}
            self.scripts.append(attr_map)


def _extract_bundle_json(js_path: Path) -> dict:
    raw = js_path.read_text(encoding="utf-8")
    match = re.search(
        r"window\.CONTEXT_PACK_BUNDLE\s*=\s*(\{.*\})\s*;",
        raw,
        re.DOTALL,
    )
    assert match is not None, f"Could not extract CONTEXT_PACK_BUNDLE JSON from {js_path}"
    return json.loads(match.group(1))


def _owned_web_files() -> list[Path]:
    files = [WEB_DIR / "index.html"]
    files.extend(sorted((WEB_DIR / "css").rglob("*.css")))
    files.extend(sorted((WEB_DIR / "js").rglob("*.js")))
    return files


def test_index_html_loads_classic_scripts_in_order_without_modules() -> None:
    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    parser = _ScriptSrcParser()
    parser.feed(index_html)

    srcs = [s.get("src") for s in parser.scripts]
    assert srcs == [
        "data/rungs_bundle.js",
        "js/fallback_bundle.js",
        "js/app.js",
    ]
    for script in parser.scripts:
        assert (script.get("type") or "").lower() != "module"

    assert 'type="module"' not in index_html.lower()


def test_fallback_bundle_guards_undefined_and_validates_against_schema() -> None:
    fallback_path = WEB_DIR / "js" / "fallback_bundle.js"
    fallback_text = fallback_path.read_text(encoding="utf-8")
    assert 'typeof window.CONTEXT_PACK_BUNDLE === "undefined"' in fallback_text

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bundle = _extract_bundle_json(fallback_path)

    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(bundle)

    assert bundle["pack_id"] == "sample_context_pack"
    assert [r["id"] for r in bundle["rungs"]] == [
        "r1_schema",
        "r2_glossary",
        "r3_metrics",
        "r4_trust_access",
        "r5_graph",
        "r6_contracts",
    ]
    assert len(bundle["personas"]) >= 2
    assert len(bundle["horizon_cards"]) >= 2
    assert "identity_variants" in bundle["rungs"][3]


def test_generated_bundle_if_present_also_validates_against_schema() -> None:
    bundle_path = WEB_DIR / "data" / "rungs_bundle.js"
    if not bundle_path.exists():
        return
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    bundle = _extract_bundle_json(bundle_path)
    jsonschema.Draft202012Validator(schema).validate(bundle)


def test_web_sources_have_zero_meridian_or_hardcoded_pack_coupling() -> None:
    forbidden_patterns = [
        r"meridian",
        r"cfo_regional",
        r"sg_coldchain",
        r"arctichaul",
        r"#ln-409",
        r"staging_cold_chain_oct11",
        r"cold_chain_margin_gold",
        r"1,684,200|1684200",
        r"1,312,450|1312450",
        r"317203\.20",
        r"131,016|131016",
        r"842,600|842600",
        r"346,480|346480",
        r"19,380|19380",
        r"18,960|18960",
    ]
    for path in _owned_web_files():
        content = path.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert re.search(pat, content, re.IGNORECASE) is None, (
                f"Forbidden scenario-specific pattern {pat!r} found in {path}"
            )


def test_web_and_readme_enforce_official_naming_and_zero_trust_pct() -> None:
    for path in [*_owned_web_files(), README_PATH]:
        content = path.read_text(encoding="utf-8")
        assert re.search(r"\bdataplex\b", content, re.IGNORECASE) is None, (
            f"Deprecated product name found in {path}; use Knowledge Catalog."
        )
        assert "Context Studio" not in content
        assert "rented commodities" not in content.lower()
        assert "Trust %" not in content

    readme_text = README_PATH.read_text(encoding="utf-8")
    assert "Knowledge Catalog" in readme_text
    assert "Workload Identity Federation" in readme_text
    assert "--offline-fixture" in readme_text
    assert "--dry-run" in readme_text
    assert "--live-gcp" in readme_text
    assert "scripts/provision_pack.sh" in readme_text
    assert "uvicorn server.app:app" in readme_text


def test_app_js_keyboard_url_params_file_safety_and_dom_security() -> None:
    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")

    # No ES module syntax or unsafe DOM sinks anywhere in web/js/
    for js_path in sorted((WEB_DIR / "js").rglob("*.js")):
        js_src = js_path.read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|export)\s+", js_src, re.MULTILINE)
        assert "innerHTML" not in js_src
        assert "outerHTML" not in js_src
        assert "insertAdjacentHTML" not in js_src
        assert "document.write" not in js_src
        assert not re.search(r"\beval\s*\(", js_src)

    # file:// protocol guard prevents startup/click fetch() failures over file://
    assert 'window.location.protocol === "file:"' in app_js
    assert "/api/run-rung" in app_js

    # Required Ballroom keyboard codes
    for key_code in ("Space", "ArrowRight", "ArrowLeft", "KeyP", "KeyB", "KeyW", "KeyT", "Escape"):
        assert f'"{key_code}"' in app_js

    # Required URL query parameter parsing
    for param in ("mode", "rung", "beat", "theme", "persona", "tab"):
        assert f'params.get("{param}")' in app_js

    # Required Stage, Workbench, X-Ray, Poll, Horizon, and Beat 4b Identity Switch markers
    for marker in (
        "Beat 4b · Switch Identity",
        "Act IV Horizon",
        "Act IV · Architectural Horizon",
        "CDO Myth-Busting Poll",
        'attrs: { id: "poll-modal-title" }',
        "Reveal Answer",
        "Context Injected",
        "Compiled SQL / ISO GQL",
        "Architecture & Negative Control",
        "Negative Control Assertion",
        "Recorded Verified Run",
        "▶ Run Live Query",
    ):
        assert marker in app_js
