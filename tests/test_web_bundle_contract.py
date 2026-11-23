"""Contract tests for the offline-safe dual-mode web UI and fallback bundle."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
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
    assert isinstance(bundle.get("eval_methodology"), dict)
    for rung in bundle["rungs"]:
        for arm_name in ("blind", "governed"):
            emp = rung[arm_name].get("empirical_eval")
            assert isinstance(emp, dict)
            assert emp["runs"] >= 1
            assert 0 <= emp["pass_count"] <= emp["runs"]
    assert "amt_gross_billed_usd" in fallback_text
    assert "amt_net_settled_usd" in fallback_text
    assert "mart_temp_margin_q4_r1" in fallback_text
    assert "mart_temp_margin_q4_r2" in fallback_text


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
    for marker in (
        "scripts/provision_context_layer.py",
        "engine/eval_harness.py",
        "scripts/deploy_cloud_run.sh",
        "/api/run-agent",
        "KeyX",
        "X-Demo-Key",
        "meridian_blind",
    ):
        assert marker in readme_text


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
        assert not re.search(r"\bFunction\s*\(", js_src)

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
        "What's Next",
        "What's Next · Horizon & Multi-Cloud",
        "CDO Myth-Busting Poll",
        'attrs: { id: "poll-modal-title" }',
        "Reveal Answer",
        "Context Injected",
        "Compiled SQL / ISO GQL",
        "Architecture & Negative Control",
        "Negative Control Assertion",
        "Recorded Verified Run",
        "▶ Run Live Query",
        # Phase 2 Stage X-Ray drawer, Regional Honesty, Live Agent, and WCAG Share Key markers
        "KeyX",
        "Escape",
        "isEditableTarget",
        'id: "stage-xray-toggle-btn"',
        'id: "stage-xray-drawer"',
        "Close [Esc]",
        "aria-expanded",
        "aria-controls",
        "Data, Graph, Catalog & RLS in",
        "Gemini PayGo Inference via",
        "/api/health",
        "/api/run-agent",
        "X-Demo-Key",
        "history.replaceState",
        'params.delete("key")',
        "live_agent_enabled === false",
        "response.status === 401",
        "🤖 Run Live Agent (Blind vs. Governed)",
        "Compare Both",
        "Blind Only",
        "Governed Only",
        "Empirical N=",
        "Empirical N=5 vs. Authored Baseline Telemetry",
        "live_agent_verified",
        'for: "demo-key-input"',
        'autocomplete: "off"',
        "aria-describedby",
    ):
        assert marker in app_js

    index_html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
    assert 'content="no-referrer"' in index_html

    styles_css = (WEB_DIR / "css" / "styles.css").read_text(encoding="utf-8")
    for css_selector in (
        ".badge-region",
        ".badge-empirical",
        ".xray-drawer",
        ".live-agent-panel",
        ".demo-key-bar",
    ):
        assert css_selector in styles_css


def test_identity_variant_scoped_metric_never_formats_currency_as_percent() -> None:
    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    assert "formatVariantMetricValue" in app_js
    assert "Math.abs(val) <= 100" in app_js

    bundle = _extract_bundle_json(WEB_DIR / "js" / "fallback_bundle.js")
    r4 = bundle["rungs"][3]
    assert r4["governed"]["unit"] == "PCT"
    assert r4["identity_variants"]["analyst_global"]["numeric_value"] == 450000.0
    assert "%" in r4["identity_variants"]["analyst_global"]["answer_headline"]

    node_bin = shutil.which("node")
    if not node_bin:
        return

    match = re.search(
        r"(function formatNumber\(.*?\n  \}\n\n  function formatMetricValue\(.*?\n  \}\n\n  function formatVariantMetricValue\(.*?\n  \})",
        app_js,
        re.DOTALL,
    )
    assert match is not None, "Could not extract metric formatter functions from web/js/app.js"

    script = f"""
{match.group(1)}
const r4 = {json.dumps(r4)};
const globalOut = formatVariantMetricValue(r4.identity_variants.analyst_global, r4, "USD");
const apacOut = formatVariantMetricValue(r4.identity_variants.analyst_apac, r4, "USD");
const synthetic420k = formatVariantMetricValue(
  {{ answer_headline: "SGD 420,000.00 (4 SEA Markets · 28.4%)", numeric_value: 420000.0 }},
  {{ governed: {{ unit: "PCT" }} }},
  "SGD"
);
const plain420k = formatVariantMetricValue(
  {{ answer_headline: "420,000 units (28.4%)", numeric_value: 420000.0 }},
  {{ governed: {{ unit: "PCT" }} }},
  "SGD"
);
const pctVariant = formatVariantMetricValue(
  {{ answer_headline: "28.4% Margin (Regional)", numeric_value: 28.4 }},
  {{ governed: {{ unit: "PCT" }} }},
  "SGD"
);
console.log(JSON.stringify({{ globalOut, apacOut, synthetic420k, plain420k, pctVariant }}));
"""
    res = subprocess.run(
        [node_bin, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    outputs = json.loads(res.stdout.strip())
    assert outputs["globalOut"] == "USD 450,000.00"
    assert "%" not in outputs["globalOut"]
    assert outputs["apacOut"] == "USD 185,000.00"
    assert "%" not in outputs["apacOut"]
    assert outputs["synthetic420k"] == "SGD 420,000.00"
    assert "%" not in outputs["synthetic420k"]
    assert outputs["plain420k"] == "420,000"
    assert "%" not in outputs["plain420k"]
    assert outputs["pctVariant"] == "28.4%"


def test_overview_and_help_drawer_contracts_and_routing() -> None:
    fallback_bundle = _extract_bundle_json(WEB_DIR / "js" / "fallback_bundle.js")
    assert isinstance(fallback_bundle.get("overview"), dict)
    ov_text = json.dumps(fallback_bundle["overview"], ensure_ascii=False)
    assert "meridian" not in ov_text.lower()
    assert "singapore" not in ov_text.lower()
    assert "sgd" not in ov_text.lower()

    app_js = (WEB_DIR / "js" / "app.js").read_text(encoding="utf-8")
    for marker in (
        "function isNonRung()",
        "buildOverviewShowcase",
        "buildHelpDrawer",
        "helpOpen",
        "? Guide",
        'id: "overview-start-btn"',
        'id: "help-guide-btn"',
        'id: "help-guide-drawer"',
        'id: "help-drawer-close"',
        'BEAT_CYCLE_B = ["blind", "governed", "compare"]',
        'e.key === "?" || e.code === "KeyH"',
        "What are Layers 1–5? Open ? Guide",
        "The 5-Layer Enterprise Context Pyramid (L1 → L5)",
    ):
        assert marker in app_js

    assert "Live query target mode" not in app_js
    assert "6 Context Layers" not in json.dumps(fallback_bundle["overview"])

    # KeyP must strictly no-op on Overview
    keyp_match = re.search(r"function togglePoll\(\)\s*\{.*?\n    \}", app_js, re.DOTALL)
    assert keyp_match is not None
    assert "if (state.isOverview)" in keyp_match.group(0)

    node_bin = shutil.which("node")
    if not node_bin:
        return

    sel_match = re.search(
        r"(function resolveRungSelection\(rungs,\s*rawParam,\s*options\)\s*\{.*?\n  \})",
        app_js,
        re.DOTALL,
    )
    assert sel_match is not None, "Could not extract resolveRungSelection from web/js/app.js"

    script = f"""
{sel_match.group(1)}
const rungs = [
  {{ id: "r1_schema", rung_num: 1 }},
  {{ id: "r2_glossary", rung_num: 2 }},
  {{ id: "r3_metrics", rung_num: 3 }},
  {{ id: "r4_trust_access", rung_num: 4 }},
  {{ id: "r5_graph", rung_num: 5 }},
  {{ id: "r6_contracts", rung_num: 6 }}
];
console.log(JSON.stringify({{
  stageOmittedWithOverview: resolveRungSelection(rungs, null, {{ hasOverview: true, mode: "stage" }}),
  stageOmittedNoOverview: resolveRungSelection(rungs, null, {{ hasOverview: false, mode: "stage" }}),
  workbenchOmittedWithOverview: resolveRungSelection(rungs, null, {{ hasOverview: true, mode: "workbench" }}),
  workbenchOverviewParam: resolveRungSelection(rungs, "overview", {{ hasOverview: true, mode: "workbench" }}),
  stageOverviewParam: resolveRungSelection(rungs, "overview", {{ hasOverview: true, mode: "stage" }}),
  stageOverviewMissing: resolveRungSelection(rungs, "overview", {{ hasOverview: false, mode: "stage" }}),
  stageHorizon: resolveRungSelection(rungs, "horizon", {{ hasOverview: true, mode: "stage" }}),
  stageRung3: resolveRungSelection(rungs, "3", {{ hasOverview: true, mode: "stage" }})
}}));
"""
    res = subprocess.run(
        [node_bin, "-e", script],
        check=True,
        capture_output=True,
        text=True,
    )
    out = json.loads(res.stdout.strip())
    assert out["stageOmittedWithOverview"] == {"isOverview": True, "isHorizon": False, "rungIndex": 0}
    assert out["stageOmittedNoOverview"] == {"isOverview": False, "isHorizon": False, "rungIndex": 0}
    assert out["workbenchOmittedWithOverview"] == {"isOverview": False, "isHorizon": False, "rungIndex": 0}
    assert out["workbenchOverviewParam"] == {"isOverview": False, "isHorizon": False, "rungIndex": 0}
    assert out["stageOverviewParam"] == {"isOverview": True, "isHorizon": False, "rungIndex": 0}
    assert out["stageOverviewMissing"] == {"isOverview": False, "isHorizon": False, "rungIndex": 0}
    assert out["stageHorizon"] == {"isOverview": False, "isHorizon": True, "rungIndex": 0}
    assert out["stageRung3"] == {"isOverview": False, "isHorizon": False, "rungIndex": 2}

