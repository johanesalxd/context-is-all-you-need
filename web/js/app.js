(function () {
  "use strict";

  const VALID_MODES = new Set(["stage", "workbench"]);
  const VALID_BEATS = new Set(["question", "blind", "governed", "compare"]);
  const VALID_THEMES = new Set(["paper", "dark"]);
  const VALID_TABS = new Set(["context", "sql", "arch"]);
  const BEAT_CYCLE_B = ["compare", "blind", "governed"];

  const SQL_KEYWORDS = new Set([
    "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "FULL", "OUTER",
    "CROSS", "ON", "USING", "GROUP", "BY", "ORDER", "ASC", "DESC", "LIMIT", "OFFSET",
    "HAVING", "WITH", "AS", "AND", "OR", "NOT", "IN", "IS", "NULL", "TRUE", "FALSE",
    "CASE", "WHEN", "THEN", "ELSE", "END", "DISTINCT", "UNION", "ALL", "EXCEPT",
    "INTERSECT", "CREATE", "OR", "REPLACE", "TABLE", "PROPERTY", "GRAPH", "NODE",
    "TABLES", "EDGE", "KEY", "REFERENCES", "LABEL", "PROPERTIES", "MEASURE", "ROW",
    "ACCESS", "POLICY", "GRANT", "TO", "FILTER", "GRAPH_TABLE", "MATCH", "RETURN",
    "COLUMNS", "EXISTS", "BETWEEN", "LIKE", "CAST", "SAFE_CAST", "OVER", "PARTITION"
  ]);

  const SQL_FUNCTIONS = new Set([
    "SUM", "COUNT", "AVG", "MIN", "MAX", "ROUND", "LEAST", "GREATEST", "COALESCE",
    "IFNULL", "NULLIF", "ANY_VALUE", "ARRAY_AGG", "STRING_AGG", "SAFE_DIVIDE",
    "EXTRACT", "DATE", "TIMESTAMP", "AI", "GENERATE", "JSON_VALUE", "UPPER", "LOWER"
  ]);

  function el(tag, opts, ...children) {
    const node = document.createElement(tag);
    if (opts && typeof opts === "object") {
      if (opts.className) {
        node.className = opts.className;
      }
      if (opts.attrs) {
        for (const [key, val] of Object.entries(opts.attrs)) {
          if (val !== null && val !== undefined && val !== false) {
            node.setAttribute(key, String(val));
          }
        }
      }
      if (opts.text !== undefined && opts.text !== null) {
        node.textContent = String(opts.text);
      }
      if (opts.onClick) {
        node.addEventListener("click", opts.onClick);
      }
    }
    for (const child of children) {
      if (child === null || child === undefined || child === false) {
        continue;
      }
      if (Array.isArray(child)) {
        for (const nested of child) {
          if (nested !== null && nested !== undefined && nested !== false) {
            node.appendChild(typeof nested === "string" || typeof nested === "number"
              ? document.createTextNode(String(nested))
              : nested);
          }
        }
      } else {
        node.appendChild(typeof child === "string" || typeof child === "number"
          ? document.createTextNode(String(child))
          : child);
      }
    }
    return node;
  }

  function formatNumber(val) {
    if (typeof val !== "number" || !Number.isFinite(val)) {
      return String(val ?? "");
    }
    const hasFraction = Math.abs(val % 1) > 1e-9;
    return val.toLocaleString("en-US", {
      minimumFractionDigits: hasFraction ? 2 : 0,
      maximumFractionDigits: hasFraction ? 2 : 0
    });
  }

  function formatMetricValue(val, unit, currency) {
    if (typeof val !== "number" || !Number.isFinite(val)) {
      return String(val ?? "");
    }
    const upperUnit = String(unit || "").toUpperCase();
    if (upperUnit === "PCT" || unit === "%") {
      return `${val.toFixed(1)}%`;
    }
    if (currency && upperUnit === String(currency).toUpperCase()) {
      return `${currency} ${val.toLocaleString("en-US", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })}`;
    }
    return `${formatNumber(val)}${unit ? " " + unit : ""}`;
  }

  function formatVariantMetricValue(variant, rung, currency) {
    const headline = String(variant.answer_headline || "");
    if (headline.includes("%")) {
      return formatMetricValue(variant.numeric_value, "%", currency);
    }
    if (currency && headline.toUpperCase().includes(String(currency).toUpperCase())) {
      return formatMetricValue(variant.numeric_value, currency, currency);
    }
    const rungUnit = String((rung && rung.governed && rung.governed.unit) || "");
    if (rungUnit && !["PCT", "%"].includes(rungUnit.toUpperCase())) {
      return formatMetricValue(variant.numeric_value, rungUnit, currency);
    }
    return formatMetricValue(variant.numeric_value, currency || "", currency);
  }

  function formatGeneratedMode(mode) {
    switch (mode) {
      case "live_gcp_verified":
        return "Live GCP Verified";
      case "dry_run_verified":
        return "Dry-Run Verified";
      case "offline_fixture":
      default:
        return "Offline Fixture";
    }
  }

  function prettyJsonOrText(raw) {
    if (!raw) {
      return "No structured context payload attached for this rung.";
    }
    try {
      const parsed = JSON.parse(raw);
      return JSON.stringify(parsed, null, 2);
    } catch (_err) {
      return String(raw);
    }
  }

  function stageBadgeClass(stage) {
    if (stage === "GA") {
      return "badge badge-ga";
    }
    if (stage === "Preview") {
      return "badge badge-preview";
    }
    return "badge badge-ref";
  }

  function trustBadgeClass(tier) {
    if (tier === "TIER_1_VERIFIED_OR_COMPILED") {
      return "badge badge-tier-1";
    }
    if (tier === "TIER_2_GROUNDED") {
      return "badge badge-tier-2";
    }
    return "badge badge-tier-3";
  }

  /**
   * Safe DOM-based tokenizer for SQL and ISO GQL using pure text nodes.
   */
  function buildHighlightedCodeNodes(source) {
    const pre = el("pre", { className: "code-pre" });
    const text = String(source || "");
    const tokenRe = /(--[^\n]*|\/\*[\s\S]*?\*\/|'(?:''|[^'])*'|"(?:""|[^"])*"|`[^`]+`|\b[A-Za-z_][A-Za-z0-9_]*\b|\b\d+(?:\.\d+)?\b|[(){}[\].,;=<>!+\-*/:]+)/g;
    let lastIndex = 0;
    let match;

    while ((match = tokenRe.exec(text)) !== null) {
      if (match.index > lastIndex) {
        pre.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      const token = match[0];
      let cls = null;
      if (token.startsWith("--") || token.startsWith("/*")) {
        cls = "tok-cmt";
      } else if (token.startsWith("'") || token.startsWith('"')) {
        cls = "tok-str";
      } else if (token.startsWith("`")) {
        cls = "tok-fn";
      } else if (/^\d/.test(token)) {
        cls = "tok-num";
      } else if (/^[A-Za-z_]/.test(token)) {
        const upper = token.toUpperCase();
        if (SQL_KEYWORDS.has(upper)) {
          cls = "tok-kw";
        } else if (SQL_FUNCTIONS.has(upper)) {
          cls = "tok-fn";
        }
      } else {
        cls = "tok-op";
      }

      if (cls) {
        pre.appendChild(el("span", { className: cls, text: token }));
      } else {
        pre.appendChild(document.createTextNode(token));
      }
      lastIndex = tokenRe.lastIndex;
    }

    if (lastIndex < text.length) {
      pre.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    return pre;
  }

  function normalizeBundle(raw) {
    if (!raw || typeof raw !== "object" || !Array.isArray(raw.rungs) || raw.rungs.length === 0) {
      return null;
    }
    const rungs = [...raw.rungs].sort((a, b) => Number(a.rung_num || 0) - Number(b.rung_num || 0));
    const personas = Array.isArray(raw.personas) ? raw.personas : [];
    const personaMap = new Map();
    for (const p of personas) {
      if (p && p.id) {
        personaMap.set(p.id, p);
      }
    }
    return {
      ...raw,
      rungs,
      personas,
      personaMap,
      horizon_cards: Array.isArray(raw.horizon_cards) ? raw.horizon_cards : []
    };
  }

  function resolveRungSelection(rungs, rawParam) {
    if (!rawParam) {
      return { isHorizon: false, rungIndex: 0 };
    }
    const trimmed = String(rawParam).trim();
    if (trimmed.toLowerCase() === "horizon") {
      return { isHorizon: true, rungIndex: 0 };
    }
    const byId = rungs.findIndex((r) => r.id === trimmed);
    if (byId >= 0) {
      return { isHorizon: false, rungIndex: byId };
    }
    const num = Number.parseInt(trimmed, 10);
    if (Number.isFinite(num)) {
      const byNum = rungs.findIndex((r) => Number(r.rung_num) === num);
      if (byNum >= 0) {
        return { isHorizon: false, rungIndex: byNum };
      }
      if (num >= 1 && num <= rungs.length) {
        return { isHorizon: false, rungIndex: num - 1 };
      }
    }
    return { isHorizon: false, rungIndex: 0 };
  }

  function resolvePersonaForRung(rung, preferredPersonaId, bundle) {
    if (!rung || !rung.identity_variants || typeof rung.identity_variants !== "object") {
      return null;
    }
    const keys = Object.keys(rung.identity_variants);
    if (keys.length === 0) {
      return null;
    }
    if (preferredPersonaId && Object.prototype.hasOwnProperty.call(rung.identity_variants, preferredPersonaId)) {
      return preferredPersonaId;
    }
    for (const p of bundle.personas) {
      if (Object.prototype.hasOwnProperty.call(rung.identity_variants, p.id)) {
        return p.id;
      }
    }
    return keys[0];
  }

  function orderedVariantKeys(rung, bundle) {
    if (!rung || !rung.identity_variants) {
      return [];
    }
    const keys = Object.keys(rung.identity_variants);
    const ordered = [];
    for (const p of bundle.personas) {
      if (keys.includes(p.id)) {
        ordered.push(p.id);
      }
    }
    for (const k of keys) {
      if (!ordered.includes(k)) {
        ordered.push(k);
      }
    }
    return ordered;
  }

  function initApp() {
    const root = document.getElementById("app-root");
    const bundle = normalizeBundle(window.CONTEXT_PACK_BUNDLE);

    if (!root) {
      return;
    }

    if (!bundle) {
      root.replaceChildren(
        el("main", { className: "stage-canvas" },
          el("div", { className: "noscript-banner", attrs: { role: "alert" } },
            "Unable to load window.CONTEXT_PACK_BUNDLE. Ensure data/rungs_bundle.js or js/fallback_bundle.js is present."
          )
        )
      );
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const initMode = VALID_MODES.has(params.get("mode")) ? params.get("mode") : "stage";
    const initTheme = VALID_THEMES.has(params.get("theme")) ? params.get("theme") : "paper";
    const initBeat = VALID_BEATS.has(params.get("beat")) ? params.get("beat") : "compare";
    const initTab = VALID_TABS.has(params.get("tab")) ? params.get("tab") : "context";
    const initRungSel = resolveRungSelection(bundle.rungs, params.get("rung"));

    const state = {
      mode: initMode,
      theme: initTheme,
      beat: initBeat,
      tab: initTab,
      isHorizon: initRungSel.isHorizon,
      rungIndex: initRungSel.rungIndex,
      preferredPersona: params.get("persona") || null,
      pollOpen: false,
      pollSelectedKey: null,
      pollRevealed: false,
      liveTargetMode: "governed",
      liveLoading: false,
      liveResult: null,
      copiedPane: null
    };

    function activeRung() {
      return bundle.rungs[state.rungIndex] || bundle.rungs[0];
    }

    function activePersonaId() {
      if (state.isHorizon) {
        return null;
      }
      return resolvePersonaForRung(activeRung(), state.preferredPersona, bundle);
    }

    function syncUrlAndDocument() {
      document.documentElement.setAttribute("data-theme", state.theme);
      document.documentElement.setAttribute("data-mode", state.mode);

      const nextParams = new URLSearchParams();
      nextParams.set("mode", state.mode);
      nextParams.set("rung", state.isHorizon ? "horizon" : String(activeRung().rung_num));
      if (state.mode === "stage" && !state.isHorizon) {
        nextParams.set("beat", state.beat);
      }
      if (state.mode === "workbench") {
        nextParams.set("tab", state.tab);
      }
      nextParams.set("theme", state.theme);
      const pid = activePersonaId();
      if (pid) {
        nextParams.set("persona", pid);
      }

      try {
        const nextUrl = `${window.location.pathname}?${nextParams.toString()}`;
        window.history.replaceState(null, "", nextUrl);
      } catch (_err) {
        // Ignore history restrictions on strict file:// sandboxes.
      }
    }

    function setState(patch) {
      Object.assign(state, patch);
      render();
    }

    function selectRung(index) {
      setState({
        isHorizon: false,
        rungIndex: Math.max(0, Math.min(bundle.rungs.length - 1, index)),
        beat: "compare",
        pollSelectedKey: null,
        pollRevealed: false,
        liveResult: null
      });
    }

    function selectHorizon() {
      setState({
        isHorizon: true,
        pollOpen: false,
        liveResult: null
      });
    }

    function stepForward() {
      if (state.isHorizon) {
        return;
      }
      if (state.beat === "question") {
        setState({ beat: "blind" });
        return;
      }
      if (state.beat === "blind") {
        setState({ beat: "governed" });
        return;
      }
      // From "governed" or "compare", move to next rung's opening beat (or Horizon after last rung).
      if (state.rungIndex < bundle.rungs.length - 1) {
        setState({
          rungIndex: state.rungIndex + 1,
          beat: "question",
          pollSelectedKey: null,
          pollRevealed: false,
          liveResult: null
        });
      } else {
        selectHorizon();
      }
    }

    function stepBackward() {
      if (state.isHorizon) {
        setState({
          isHorizon: false,
          rungIndex: bundle.rungs.length - 1,
          beat: "compare",
          liveResult: null
        });
        return;
      }
      if (state.beat === "governed") {
        setState({ beat: "blind" });
        return;
      }
      if (state.beat === "blind") {
        setState({ beat: "question" });
        return;
      }
      if (state.rungIndex > 0) {
        setState({
          rungIndex: state.rungIndex - 1,
          beat: "compare",
          pollSelectedKey: null,
          pollRevealed: false,
          liveResult: null
        });
      }
    }

    function cycleBeatB() {
      if (state.isHorizon) {
        return;
      }
      if (state.beat === "question") {
        setState({ beat: "blind" });
        return;
      }
      const idx = BEAT_CYCLE_B.indexOf(state.beat);
      const next = BEAT_CYCLE_B[(idx + 1) % BEAT_CYCLE_B.length];
      setState({ beat: next });
    }

    function toggleMode() {
      setState({
        mode: state.mode === "stage" ? "workbench" : "stage",
        pollOpen: false
      });
    }

    function toggleTheme() {
      setState({
        theme: state.theme === "paper" ? "dark" : "paper"
      });
    }

    function togglePoll() {
      if (state.isHorizon && !state.pollOpen) {
        setState({ isHorizon: false, pollOpen: true });
        return;
      }
      setState({ pollOpen: !state.pollOpen });
    }

    async function handleRunLiveQuery() {
      if (state.isHorizon) {
        return;
      }
      const rung = activeRung();
      const personaId = activePersonaId();

      if (window.location.protocol === "file:") {
        setState({
          liveResult: {
            kind: "info",
            message: "Offline file:// mode active — displaying recorded verified run. Launch uvicorn server.app:app over http:// to execute POST /api/run-rung."
          }
        });
        return;
      }

      setState({ liveLoading: true, liveResult: null });
      const startedAt = performance.now();
      const payload = {
        pack_id: bundle.pack_id,
        rung_id: rung.id,
        mode: state.liveTargetMode
      };
      if (personaId) {
        payload.persona_id = personaId;
      }

      try {
        const response = await fetch("/api/run-rung", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const elapsedMs = Math.round(performance.now() - startedAt);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = data.detail || data.error || `HTTP ${response.status}`;
          setState({
            liveLoading: false,
            liveResult: {
              kind: "error",
              message: `Live query request failed (${elapsedMs} ms): ${String(detail)}`
            }
          });
          return;
        }
        const latencyMs = typeof data.latency_ms === "number"
          ? Math.round(data.latency_ms)
          : (typeof data.elapsed_ms === "number" ? Math.round(data.elapsed_ms) : elapsedMs);
        const headline = data.answer_headline || data.headline || (data.outcome && data.outcome.answer_headline) || "Completed";
        const val = data.numeric_value ?? data.value ?? (data.outcome && data.outcome.numeric_value);
        const rowCount = data.row_count ?? data.rows_visible ?? (Array.isArray(data.rows) ? data.rows.length : null);
        const tier = data.trust_tier || (data.outcome && data.outcome.trust_tier) || "";
        const valSummary = typeof val === "number" ? ` (${formatNumber(val)})` : "";
        const rowsSummary = typeof rowCount === "number" ? ` · ${rowCount} row(s)` : "";
        const tierSummary = tier ? ` · ${tier}` : "";
        setState({
          liveLoading: false,
          liveResult: {
            kind: "success",
            message: `Live /api/run-rung [${state.liveTargetMode}${personaId ? " · " + personaId : ""}] completed in ${latencyMs} ms → ${headline}${valSummary}${rowsSummary}${tierSummary}`
          }
        });
      } catch (err) {
        const elapsedMs = Math.round(performance.now() - startedAt);
        setState({
          liveLoading: false,
          liveResult: {
            kind: "error",
            message: `Live runner unreachable (${elapsedMs} ms): ${err && err.message ? err.message : "Network error"}`
          }
        });
      }
    }

    function copyTextToClipboard(paneKey, text) {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        navigator.clipboard.writeText(text).then(() => {
          setState({ copiedPane: paneKey });
          window.setTimeout(() => {
            if (state.copiedPane === paneKey) {
              setState({ copiedPane: null });
            }
          }, 1500);
        }).catch(() => {});
      }
    }

    /* ----------------------------------------------------------------------
       Shared UI Fragment Builders (100% safe DOM construction)
       ---------------------------------------------------------------------- */

    function buildRungStepper() {
      const group = el("nav", {
        className: "stage-stepper segmented-group",
        attrs: { "aria-label": "Rung progression" }
      });

      bundle.rungs.forEach((rung, idx) => {
        const isActive = !state.isHorizon && state.rungIndex === idx;
        group.appendChild(
          el("button", {
            className: `seg-btn${isActive ? " is-active" : ""}`,
            text: `R${rung.rung_num}`,
            attrs: {
              type: "button",
              title: rung.short_label,
              "aria-label": `${rung.short_label}: ${rung.title}`,
              "aria-current": isActive ? "step" : null,
              "data-rung-id": rung.id
            },
            onClick: () => selectRung(idx)
          })
        );
      });

      group.appendChild(
        el("button", {
          className: `seg-btn is-horizon${state.isHorizon ? " is-active" : ""}`,
          text: "Act IV Horizon",
          attrs: {
            type: "button",
            "aria-current": state.isHorizon ? "step" : null,
            "data-rung-id": "horizon"
          },
          onClick: () => selectHorizon()
        })
      );

      return group;
    }

    function buildModeAndThemeSwitches() {
      const modeGroup = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Display mode" }
      },
        el("button", {
          className: `seg-btn${state.mode === "stage" ? " is-active" : ""}`,
          attrs: { type: "button", "aria-pressed": state.mode === "stage" ? "true" : "false" },
          onClick: () => setState({ mode: "stage", pollOpen: false })
        }, "Stage ", el("span", { className: "kbd-hint", text: "W" })),
        el("button", {
          className: `seg-btn${state.mode === "workbench" ? " is-active" : ""}`,
          attrs: { type: "button", "aria-pressed": state.mode === "workbench" ? "true" : "false" },
          onClick: () => setState({ mode: "workbench", pollOpen: false })
        }, "Workbench")
      );

      const themeGroup = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Color theme" }
      },
        el("button", {
          className: `seg-btn${state.theme === "paper" ? " is-active" : ""}`,
          attrs: { type: "button", "aria-pressed": state.theme === "paper" ? "true" : "false" },
          onClick: () => setState({ theme: "paper" })
        }, "Paper ", el("span", { className: "kbd-hint", text: "T" })),
        el("button", {
          className: `seg-btn${state.theme === "dark" ? " is-active" : ""}`,
          attrs: { type: "button", "aria-pressed": state.theme === "dark" ? "true" : "false" },
          onClick: () => setState({ theme: "dark" })
        }, "Dark")
      );

      return { modeGroup, themeGroup };
    }

    function buildIdentitySwitchPanel(rung) {
      const keys = orderedVariantKeys(rung, bundle);
      if (keys.length === 0) {
        return null;
      }
      const currentId = activePersonaId();
      const variant = rung.identity_variants[currentId];
      const personaMeta = bundle.personaMap.get(currentId);

      const segGroup = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Beat 4b Switch Identity" }
      });

      for (const pid of keys) {
        const pInfo = bundle.personaMap.get(pid);
        const label = pInfo ? pInfo.label : pid;
        const isActive = pid === currentId;
        segGroup.appendChild(
          el("button", {
            className: `seg-btn${isActive ? " is-active" : ""}`,
            text: label,
            attrs: {
              type: "button",
              "data-persona-id": pid,
              "aria-pressed": isActive ? "true" : "false"
            },
            onClick: () => setState({ preferredPersona: pid })
          })
        );
      }

      return el("section", {
        className: "identity-panel",
        attrs: { "aria-label": "Beat 4b Identity and Row-Level Security" }
      },
        el("div", { className: "identity-header" },
          el("span", { className: "identity-title", text: "Beat 4b · Switch Identity" }),
          segGroup
        ),
        variant
          ? el("div", { className: "identity-meta-grid" },
              el("div", { className: "identity-meta-item" },
                el("strong", { text: "Principal: " }),
                el("span", { className: "badge-mono", text: personaMeta ? personaMeta.principal_display : currentId })
              ),
              el("div", { className: "identity-meta-item" },
                el("strong", { text: "Rows Visible: " }),
                el("span", { className: "badge-mono", text: String(variant.rows_visible) })
              ),
              el("div", { className: "identity-meta-item" },
                el("strong", { text: "RLS Policy: " }),
                el("span", { className: "badge-mono", text: variant.rls_policy_applied })
              ),
              el("div", { className: "identity-meta-item" },
                el("strong", { text: "Policy Note: " }),
                el("span", { text: variant.policy_note })
              )
            )
          : null
      );
    }

    function buildHorizonShowcase() {
      const grid = el("div", { className: "horizon-grid" });
      for (const card of bundle.horizon_cards) {
        const primList = el("ul", { className: "primitives-list" },
          ...(Array.isArray(card.primitives) ? card.primitives : []).map((p) =>
            el("li", { className: "primitive-chip", text: p })
          )
        );
        grid.appendChild(
          el("article", {
            className: "horizon-card",
            attrs: { "data-horizon-id": card.id }
          },
            el("div", { className: "horizon-card-head" },
              el("h2", { className: "horizon-card-title", text: card.title }),
              el("span", { className: stageBadgeClass(card.release_badge), text: card.release_badge })
            ),
            el("div", { className: "release-badges-row" },
              el("span", { className: "badge", text: card.region_availability })
            ),
            el("p", { className: "horizon-card-summary", text: card.summary }),
            primList
          )
        );
      }

      return el("section", {
        className: "horizon-showcase",
        attrs: { "aria-label": "Act IV Horizon Architectural Showcase" }
      },
        el("div", { className: "horizon-banner" },
          el("span", { className: "horizon-banner-eyebrow", text: "Act IV · Architectural Horizon (Decoupled from R1–R6 Live Scope)" }),
          el("h1", { className: "horizon-banner-title", text: "Where Knowledge Governance Goes Next: Context Studio & Cross-Cloud Federation" }),
          el("p", {
            className: "horizon-banner-subtitle",
            text: `Rungs 1–6 execute strictly within ${bundle.region}. These Horizon capabilities map regional Preview tracks and multi-cloud GA federation patterns.`
          })
        ),
        grid
      );
    }

    /* ----------------------------------------------------------------------
       Stage Mode Renderer (10% / 80% / 10% Quiet Stage V2)
       ---------------------------------------------------------------------- */

    function buildMetricsStrip(outcome) {
      return el("div", { className: "outcome-metrics-strip" },
        el("div", { className: "metric-chip" },
          el("span", { className: "metric-chip-label", text: "Golden Eval" }),
          el("span", { className: "metric-chip-value", text: `${outcome.eval_pass_count}/${outcome.eval_total_runs}` })
        ),
        el("div", { className: "metric-chip" },
          el("span", { className: "metric-chip-label", text: "Queries" }),
          el("span", { className: "metric-chip-value", text: String(outcome.exploratory_queries) })
        ),
        el("div", { className: "metric-chip" },
          el("span", { className: "metric-chip-label", text: "Retries" }),
          el("span", { className: "metric-chip-value", text: String(outcome.error_retries) })
        ),
        el("div", { className: "metric-chip" },
          el("span", { className: "metric-chip-label", text: "Tokens" }),
          el("span", { className: "metric-chip-value", text: formatNumber(outcome.tokens_used) })
        )
      );
    }

    function buildStageView() {
      const rung = activeRung();
      const { modeGroup, themeGroup } = buildModeAndThemeSwitches();

      const beatToggle = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Beat focus" }
      },
        el("button", {
          className: `seg-btn${state.beat === "question" ? " is-active" : ""}`,
          text: "Q",
          attrs: { type: "button", title: "Step 1: Business Question", disabled: state.isHorizon ? true : null },
          onClick: () => setState({ beat: "question" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "blind" ? " is-active" : ""}`,
          text: "Blind",
          attrs: { type: "button", disabled: state.isHorizon ? true : null },
          onClick: () => setState({ beat: "blind" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "compare" ? " is-active" : ""}`,
          text: "Compare",
          attrs: { type: "button", disabled: state.isHorizon ? true : null },
          onClick: () => setState({ beat: "compare" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "governed" ? " is-active" : ""}`,
          text: "Governed",
          attrs: { type: "button", disabled: state.isHorizon ? true : null },
          onClick: () => setState({ beat: "governed" })
        })
      );

      const tokenRetryPill = el("div", {
        className: "token-retry-pill",
        attrs: { "aria-label": "Context tokens and retries delta" }
      },
        state.isHorizon
          ? el("span", { text: "Act IV · Roadmap Scope" })
          : [
              el("span", { text: `Tokens ${formatNumber(rung.blind.tokens_used)} → ` }),
              el("span", { className: "delta-good", text: formatNumber(rung.governed.tokens_used) }),
              el("span", { text: ` · Retries ${rung.blind.error_retries} → ` }),
              el("span", { className: "delta-good", text: String(rung.governed.error_retries) })
            ]
      );

      const topbar = el("header", { className: "stage-topbar" },
        el("div", { className: "stage-topbar-row" },
          el("div", { className: "brand-block" },
            el("div", { className: "brand-title-row" },
              el("p", { className: "brand-title", text: bundle.title }),
              el("span", { className: "badge badge-mono", text: `${bundle.closed_period_label} · ${bundle.region}` }),
              el("span", { className: "brand-tagline", text: bundle.hero_tagline })
            )
          ),
          el("div", { className: "stage-actions" },
            el("button", {
              className: "btn btn-accent",
              attrs: { type: "button", title: "Open CDO Myth-Busting Poll (Key P)" },
              onClick: () => togglePoll()
            }, "Poll ", el("span", { className: "kbd-hint", text: "P" })),
            modeGroup,
            themeGroup
          )
        ),
        el("div", { className: "stage-topbar-row stage-topbar-nav" },
          buildRungStepper(),
          el("div", { className: "stage-actions" },
            beatToggle,
            el("button", {
              className: "btn",
              attrs: { type: "button", title: "Cycle Beat Focus (Key B)", disabled: state.isHorizon ? true : null },
              onClick: () => cycleBeatB()
            }, "Focus ", el("span", { className: "kbd-hint", text: "B" })),
            tokenRetryPill
          )
        )
      );

      let canvasChildren;
      if (state.isHorizon) {
        canvasChildren = [buildHorizonShowcase()];
      } else {
        const questionHero = el("section", {
          className: "question-hero",
          attrs: { "aria-label": "Business question" }
        },
          el("div", { className: "question-meta-row" },
            el("div", { className: "question-eyebrow" },
              el("span", { className: "badge badge-mono", text: rung.short_label }),
              el("span", { className: "badge", text: rung.pyramid_layer })
            ),
            el("div", { className: "release-badges-row" },
              ...rung.release_badges.map((rb) =>
                el("span", {
                  className: stageBadgeClass(rb.stage),
                  text: `${rb.capability} · ${rb.stage} (${rb.region_scope})`
                })
              )
            )
          ),
          el("h1", { className: "question-headline", text: rung.question })
        );

        if (state.beat === "question") {
          canvasChildren = [
            questionHero,
            el("div", { className: "beat-banner" },
              el("span", { text: "Beat 1 of 3 · Business Question presented. Step forward to inspect the Blind Agent Trap." }),
              el("button", {
                className: "btn btn-primary",
                text: "Reveal Blind Agent Trap →",
                attrs: { type: "button" },
                onClick: () => stepForward()
              })
            )
          ];
        } else {
          const personaId = activePersonaId();
          const activeVariant = personaId && rung.identity_variants
            ? rung.identity_variants[personaId]
            : null;

          const govHeadline = activeVariant ? activeVariant.answer_headline : rung.governed.answer_headline;
          const govDetail = activeVariant ? activeVariant.answer_detail : rung.governed.answer_detail;
          const govNumericFormatted = activeVariant
            ? formatVariantMetricValue(activeVariant, rung, bundle.currency)
            : formatMetricValue(rung.governed.numeric_value, rung.governed.unit, bundle.currency);

          const blindCardClass = `outcome-card is-blind${state.beat === "governed" ? " is-subdued" : ""}`;
          const blindCard = el("article", {
            className: blindCardClass,
            attrs: { "aria-label": "Blind Agent Trap outcome" }
          },
            el("div", null,
              el("div", { className: "outcome-card-head" },
                el("div", { className: "outcome-label-group" },
                  el("span", { className: "outcome-role-title", text: "Blind Agent Trap" }),
                  el("span", { className: "badge badge-mono", text: rung.blind.query_language })
                ),
                el("span", { className: trustBadgeClass(rung.blind.trust_tier), text: rung.blind.trust_tier })
              ),
              el("p", { className: "outcome-kpi", text: rung.blind.answer_headline }),
              el("p", { className: "outcome-detail", text: rung.blind.answer_detail })
            ),
            el("div", null,
              el("p", { className: "outcome-rationale", text: `Failure Mechanism: ${rung.blind.rationale}` }),
              buildMetricsStrip(rung.blind)
            )
          );

          const govCardClass = `outcome-card is-governed${state.beat === "blind" ? " is-veiled" : ""}`;
          const governedCard = state.beat === "blind"
            ? el("article", {
                className: govCardClass,
                attrs: { "aria-label": "Governed Context pending beat" }
              },
                el("div", { className: "veil-placeholder" },
                  el("span", { className: "outcome-role-title", text: "Governed Enterprise Context" }),
                  el("p", { className: "outcome-detail", text: "Beat 2 of 3 · Blind Agent Trap active. Apply governed metadata, contracts, and policy rules next." }),
                  el("button", {
                    className: "btn btn-primary",
                    text: "Apply Governed Context [Space] →",
                    attrs: { type: "button" },
                    onClick: () => setState({ beat: "governed" })
                  })
                )
              )
            : el("article", {
                className: govCardClass,
                attrs: { "aria-label": "Governed Enterprise Context outcome" }
              },
                el("div", null,
                  el("div", { className: "outcome-card-head" },
                    el("div", { className: "outcome-label-group" },
                      el("span", { className: "outcome-role-title", text: "Governed Enterprise Context" }),
                      el("span", { className: "badge badge-mono", text: rung.governed.query_language })
                    ),
                    el("span", { className: trustBadgeClass(rung.governed.trust_tier), text: rung.governed.trust_tier })
                  ),
                  el("p", { className: "outcome-kpi", text: govHeadline }),
                  el("p", { className: "outcome-detail", text: govDetail }),
                  activeVariant
                    ? el("div", { className: "scoped-metric-row" },
                        el("span", {
                          className: "badge badge-ga badge-mono",
                          text: `Scoped Metric: ${govNumericFormatted}`
                        })
                      )
                    : null,
                  buildIdentitySwitchPanel(rung)
                ),
                el("div", null,
                  rung.governed.context_mechanism
                    ? el("div", { className: "context-callout" },
                        el("span", { className: "context-callout-label", text: "Context Injected:" }),
                        el("span", { text: rung.governed.context_mechanism })
                      )
                    : null,
                  el("p", { className: "outcome-rationale", text: `Grounding: ${rung.governed.rationale}` }),
                  buildMetricsStrip(rung.governed)
                )
              );

          const gridModifier = state.beat === "blind"
            ? " is-focus-blind"
            : (state.beat === "governed" ? " is-focus-governed" : "");

          canvasChildren = [
            questionHero,
            el("section", {
              className: `comparison-grid${gridModifier}`,
              attrs: { "aria-label": "Blind vs Governed comparison" }
            }, blindCard, governedCard)
          ];
        }
      }

      const canvas = el("main", { className: "stage-canvas" }, canvasChildren);

      // Bottom 10% Eval & Trust Bar
      const evalDots = el("span", { className: "eval-dots", attrs: { "aria-hidden": "true" } });
      if (!state.isHorizon) {
        for (let i = 0; i < rung.governed.eval_total_runs; i += 1) {
          const pass = i < rung.governed.eval_pass_count;
          evalDots.appendChild(el("span", { className: `eval-dot ${pass ? "is-pass" : "is-fail"}` }));
        }
      }

      const footer = el("footer", { className: "stage-footer" },
        state.isHorizon
          ? el("div", { className: "eval-trust-group" },
              el("span", { className: "badge", text: `Act IV Horizon · ${bundle.horizon_cards.length} Architectural Cards` }),
              el("span", { className: "eval-label", text: `Live Scope: ${bundle.region}` })
            )
          : el("div", { className: "eval-trust-group" },
              el("div", { className: "eval-block" },
                el("span", { className: "eval-label", text: "Golden Eval Pass Rate" }),
                evalDots,
                el("span", {
                  className: "badge badge-mono",
                  text: `${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs} → ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}`
                })
              ),
              el("div", { className: "eval-block" },
                el("span", { className: "eval-label", text: "TrustTier" }),
                el("span", { className: trustBadgeClass(rung.blind.trust_tier), text: rung.blind.trust_tier }),
                el("span", { text: "→" }),
                el("span", { className: trustBadgeClass(rung.governed.trust_tier), text: rung.governed.trust_tier })
              ),
              el("div", { className: "eval-block" },
                el("span", { className: "eval-label", text: "Exploratory Queries" }),
                el("span", {
                  className: "badge badge-mono",
                  text: `${rung.blind.exploratory_queries} → ${rung.governed.exploratory_queries}`
                })
              )
            ),
        el("div", { className: "nav-controls-group" },
          el("div", { className: "shortcut-legend", attrs: { "aria-label": "Keyboard shortcuts" } },
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "Space/→" }), "Advance"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "P" }), "Poll"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "B" }), "Focus"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "W" }), "Workbench"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "T" }), "Theme")
          ),
          el("button", {
            className: "btn",
            text: "← Prev",
            attrs: {
              type: "button",
              disabled: !state.isHorizon && state.rungIndex === 0 && state.beat === "question" ? true : null
            },
            onClick: () => stepBackward()
          }),
          el("button", {
            className: "btn btn-primary",
            text: state.isHorizon ? "End · Act IV" : "Next →",
            attrs: { type: "button", disabled: state.isHorizon ? true : null },
            onClick: () => stepForward()
          })
        )
      );

      return el("div", { className: "stage-shell" }, topbar, canvas, footer);
    }

    /* ----------------------------------------------------------------------
       Workbench Mode Renderer (Progression Bar + 3-Tab Engineering X-Ray)
       ---------------------------------------------------------------------- */

    function buildProgressionBar() {
      let blindPassSum = 0;
      let govPassSum = 0;
      let totalRunsSum = 0;
      let blindRetrySum = 0;
      let govRetrySum = 0;

      for (const r of bundle.rungs) {
        blindPassSum += Number(r.blind.eval_pass_count || 0);
        govPassSum += Number(r.governed.eval_pass_count || 0);
        totalRunsSum += Number(r.governed.eval_total_runs || 0);
        blindRetrySum += Number(r.blind.error_retries || 0);
        govRetrySum += Number(r.governed.error_retries || 0);
      }

      const cardsWrap = el("div", { className: "progression-cards" });
      bundle.rungs.forEach((rung, idx) => {
        const isActive = !state.isHorizon && state.rungIndex === idx;
        const pct = Math.round((rung.governed.eval_pass_count / Math.max(1, rung.governed.eval_total_runs)) * 100);
        cardsWrap.appendChild(
          el("button", {
            className: `prog-card${isActive ? " is-active" : ""}`,
            attrs: {
              type: "button",
              "aria-current": isActive ? "step" : null,
              "data-prog-rung": rung.id
            },
            onClick: () => selectRung(idx)
          },
            el("div", { className: "prog-card-top" },
              el("span", { className: "prog-card-label", text: rung.short_label }),
              el("span", { className: trustBadgeClass(rung.governed.trust_tier), text: rung.governed.trust_tier.replace(/_/g, " ").split(" ").slice(0, 2).join(" ") })
            ),
            el("span", { className: "prog-card-layer", text: rung.pyramid_layer }),
            el("div", { className: "prog-bar-track" },
              el("div", {
                className: "prog-bar-fill",
                attrs: { style: `width: ${pct}%` }
              })
            ),
            el("div", { className: "prog-card-stats" },
              el("span", { text: `Eval ${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs} → ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}` }),
              el("span", { text: `Retries ${rung.blind.error_retries} → ${rung.governed.error_retries}` })
            )
          )
        );
      });

      return el("section", {
        className: "progression-section",
        attrs: { "aria-label": "Cumulative Accuracy and Retry Progression Bar" }
      },
        el("div", { className: "progression-head" },
          el("h2", { className: "progression-title", text: "Cumulative Golden Eval Accuracy & Retry Progression" }),
          el("div", { className: "release-badges-row" },
            el("span", {
              className: "badge badge-tier-3 badge-mono",
              text: `Blind Cumulative: ${blindPassSum}/${totalRunsSum}`
            }),
            el("span", {
              className: "badge badge-ga badge-mono",
              text: `Governed Cumulative: ${govPassSum}/${totalRunsSum}`
            }),
            el("span", {
              className: "badge badge-mono",
              text: `Error Retries: ${blindRetrySum} → ${govRetrySum}`
            })
          )
        ),
        cardsWrap
      );
    }

    function buildXrayInspector(rung) {
      const tabs = [
        { id: "context", label: "1. Context Injected" },
        { id: "sql", label: "2. Compiled SQL / ISO GQL" },
        { id: "arch", label: "3. Architecture & Negative Control" }
      ];

      const tablist = el("div", {
        className: "xray-tablist",
        attrs: { role: "tablist", "aria-label": "Engineering X-Ray Inspector" }
      },
        ...tabs.map((t) =>
          el("button", {
            className: `xray-tab${state.tab === t.id ? " is-active" : ""}`,
            text: t.label,
            attrs: {
              type: "button",
              role: "tab",
              id: `xray-tab-${t.id}`,
              "aria-selected": state.tab === t.id ? "true" : "false",
              "aria-controls": "xray-tabpanel"
            },
            onClick: () => setState({ tab: t.id })
          })
        )
      );

      let bodyChildren = [];
      if (state.tab === "context") {
        bodyChildren.push(
          el("div", { className: "context-callout" },
            el("span", { className: "context-callout-label", text: "Context Mechanism:" }),
            el("span", { text: rung.governed.context_mechanism || rung.xray_summary.context_added })
          ),
          el("p", { className: "outcome-detail", text: `X-Ray Summary: ${rung.xray_summary.context_added}` }),
          el("div", { className: "code-pane" },
            el("div", { className: "code-pane-head" },
              el("span", { className: "badge badge-mono", text: "Injected Context Payload" }),
              el("button", {
                className: "btn",
                text: state.copiedPane === "context" ? "Copied" : "Copy Payload",
                attrs: { type: "button" },
                onClick: () => copyTextToClipboard("context", prettyJsonOrText(rung.governed.context_payload))
              })
            ),
            el("pre", { className: "code-pre", text: prettyJsonOrText(rung.governed.context_payload) })
          )
        );

        const variantKeys = orderedVariantKeys(rung, bundle);
        if (variantKeys.length > 0) {
          const rows = variantKeys.map((pid) => {
            const v = rung.identity_variants[pid];
            const p = bundle.personaMap.get(pid);
            return el("tr", null,
              el("td", { text: p ? p.label : pid }),
              el("td", { className: "badge-mono", text: p ? p.principal_display : pid }),
              el("td", { className: "badge-mono", text: v.rls_policy_applied }),
              el("td", { className: "badge-mono", text: String(v.rows_visible) }),
              el("td", { text: v.answer_headline }),
              el("td", { text: v.policy_note })
            );
          });
          bodyChildren.push(
            el("div", { className: "rls-table-wrap" },
              el("table", { className: "rls-table" },
                el("thead", null,
                  el("tr", null,
                    el("th", { text: "Persona" }),
                    el("th", { text: "Principal" }),
                    el("th", { text: "RLS Policy Applied" }),
                    el("th", { text: "Rows Visible" }),
                    el("th", { text: "Outcome" }),
                    el("th", { text: "Policy Note" })
                  )
                ),
                el("tbody", null, rows)
              )
            )
          );
        }
      } else if (state.tab === "sql") {
        bodyChildren.push(
          el("div", { className: "code-diff-grid" },
            el("div", { className: "code-pane" },
              el("div", { className: "code-pane-head" },
                el("div", { className: "outcome-label-group" },
                  el("span", { className: "badge badge-tier-3", text: `Blind · ${rung.blind.query_language}` }),
                  el("span", { className: "badge badge-mono", text: `${formatNumber(rung.blind.tokens_used)} tok · ${rung.blind.error_retries} retries` })
                ),
                el("button", {
                  className: "btn",
                  text: state.copiedPane === "blind_sql" ? "Copied" : "Copy",
                  attrs: { type: "button" },
                  onClick: () => copyTextToClipboard("blind_sql", rung.blind.sql_or_gql)
                })
              ),
              buildHighlightedCodeNodes(rung.blind.sql_or_gql)
            ),
            el("div", { className: "code-pane" },
              el("div", { className: "code-pane-head" },
                el("div", { className: "outcome-label-group" },
                  el("span", { className: "badge badge-ga", text: `Governed · ${rung.governed.query_language}` }),
                  el("span", { className: "badge badge-mono", text: `${formatNumber(rung.governed.tokens_used)} tok · ${rung.governed.error_retries} retries` })
                ),
                el("button", {
                  className: "btn",
                  text: state.copiedPane === "gov_sql" ? "Copied" : "Copy",
                  attrs: { type: "button" },
                  onClick: () => copyTextToClipboard("gov_sql", rung.governed.sql_or_gql)
                })
              ),
              buildHighlightedCodeNodes(rung.governed.sql_or_gql)
            )
          )
        );
      } else {
        bodyChildren.push(
          el("div", null,
            el("h3", { className: "progression-title", text: "GCP Primitives" }),
            el("ul", { className: "primitives-list" },
              ...rung.xray_summary.gcp_primitives.map((prim) =>
                el("li", { className: "primitive-chip", text: prim })
              )
            )
          ),
          el("div", { className: "rls-table-wrap" },
            el("table", { className: "rls-table" },
              el("thead", null,
                el("tr", null,
                  el("th", { text: "Capability" }),
                  el("th", { text: "Release Stage" }),
                  el("th", { text: "Region Scope" })
                )
              ),
              el("tbody", null,
                ...rung.release_badges.map((rb) =>
                  el("tr", null,
                    el("td", { text: rb.capability }),
                    el("td", null, el("span", { className: stageBadgeClass(rb.stage), text: rb.stage })),
                    el("td", { className: "badge-mono", text: rb.region_scope })
                  )
                )
              )
            )
          ),
          el("div", { className: "neg-control-box" },
            el("h3", { className: "neg-control-title", text: "Negative Control Assertion" }),
            el("p", { className: "outcome-detail", text: rung.xray_summary.negative_control_assertion })
          )
        );
      }

      return el("section", {
        className: "xray-panel",
        attrs: { "aria-label": "Engineering X-Ray Inspector" }
      },
        tablist,
        el("div", {
          className: "xray-body",
          attrs: {
            role: "tabpanel",
            id: "xray-tabpanel",
            "aria-labelledby": `xray-tab-${state.tab}`
          }
        }, bodyChildren)
      );
    }

    function buildWorkbenchView() {
      const rung = activeRung();
      const { modeGroup, themeGroup } = buildModeAndThemeSwitches();
      const personaId = activePersonaId();
      const activeVariant = !state.isHorizon && personaId && rung.identity_variants
        ? rung.identity_variants[personaId]
        : null;

      const header = el("header", { className: "workbench-header" },
        el("div", { className: "brand-block" },
          el("div", { className: "brand-title-row" },
            el("p", { className: "brand-title", text: `${bundle.title} · Engineering Workbench` }),
            el("span", { className: "badge badge-mono", text: bundle.pack_id })
          ),
          el("p", { className: "brand-tagline", text: bundle.subtitle })
        ),
        buildRungStepper(),
        el("div", { className: "stage-actions" },
          el("button", {
            className: "btn btn-accent",
            attrs: { type: "button", title: "Open Poll Modal (Key P)" },
            onClick: () => togglePoll()
          }, "Poll ", el("span", { className: "kbd-hint", text: "P" })),
          modeGroup,
          themeGroup
        )
      );

      const runnerTargetGroup = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Live query target mode" }
      },
        el("button", {
          className: `seg-btn${state.liveTargetMode === "governed" ? " is-active" : ""}`,
          text: "Governed",
          attrs: { type: "button" },
          onClick: () => setState({ liveTargetMode: "governed" })
        }),
        el("button", {
          className: `seg-btn${state.liveTargetMode === "blind" ? " is-active" : ""}`,
          text: "Blind",
          attrs: { type: "button" },
          onClick: () => setState({ liveTargetMode: "blind" })
        })
      );

      const execBadgeText = bundle.generated_mode === "live_gcp_verified"
        ? `Live GCP Verified (${bundle.region})`
        : `[Recorded Verified Run] · ${formatGeneratedMode(bundle.generated_mode)}`;

      const statusBar = el("div", { className: "workbench-status-bar" },
        el("div", { className: "outcome-label-group" },
          el("span", {
            className: bundle.generated_mode === "live_gcp_verified" ? "badge badge-ga" : "badge badge-ref",
            text: execBadgeText
          }),
          el("span", { className: "badge badge-mono", text: `Period: ${bundle.closed_period_label}` }),
          personaId ? el("span", { className: "badge badge-mono", text: `Persona: ${personaId}` }) : null
        ),
        el("div", { className: "live-runner-controls" },
          runnerTargetGroup,
          el("button", {
            className: "btn btn-primary",
            text: state.liveLoading ? "Running..." : "▶ Run Live Query",
            attrs: {
              type: "button",
              disabled: state.liveLoading || state.isHorizon ? true : null,
              title: window.location.protocol === "file:"
                ? "Offline file:// mode: displaying recorded verified run. Serve via uvicorn server.app:app to run live queries."
                : "Execute allowlisted pack query via POST /api/run-rung"
            },
            onClick: () => handleRunLiveQuery()
          })
        )
      );

      const liveBanner = state.liveResult
        ? el("div", {
            className: `live-result-banner is-${state.liveResult.kind}`,
            attrs: { role: "status", "aria-live": "polite" }
          },
            el("span", { text: state.liveResult.message }),
            el("button", {
              className: "btn",
              text: "Dismiss",
              attrs: { type: "button" },
              onClick: () => setState({ liveResult: null })
            })
          )
        : null;

      let mainSection;
      if (state.isHorizon) {
        mainSection = buildHorizonShowcase();
      } else {
        const govHeadline = activeVariant ? activeVariant.answer_headline : rung.governed.answer_headline;
        const govDetail = activeVariant ? activeVariant.answer_detail : rung.governed.answer_detail;

        mainSection = [
          el("section", { className: "workbench-summary-card", attrs: { "aria-label": "Selected rung summary" } },
            el("div", { className: "question-meta-row" },
              el("div", { className: "question-eyebrow" },
                el("span", { className: "badge badge-mono", text: rung.short_label }),
                el("span", { className: "badge", text: rung.title }),
                el("span", { className: "badge", text: rung.pyramid_layer })
              ),
              el("div", { className: "release-badges-row" },
                ...rung.release_badges.map((rb) =>
                  el("span", { className: stageBadgeClass(rb.stage), text: `${rb.capability} (${rb.stage})` })
                )
              )
            ),
            el("h1", { className: "question-headline", text: rung.question }),
            el("div", { className: "workbench-outcomes-mini" },
              el("div", { className: "mini-outcome is-blind" },
                el("div", { className: "outcome-card-head" },
                  el("span", { className: "outcome-role-title", text: "Blind Agent Trap" }),
                  el("span", { className: trustBadgeClass(rung.blind.trust_tier), text: rung.blind.trust_tier })
                ),
                el("p", { className: "outcome-kpi", text: rung.blind.answer_headline }),
                el("p", { className: "outcome-detail", text: rung.blind.answer_detail })
              ),
              el("div", { className: "mini-outcome is-governed" },
                el("div", { className: "outcome-card-head" },
                  el("span", { className: "outcome-role-title", text: "Governed Context Outcome" }),
                  el("span", { className: trustBadgeClass(rung.governed.trust_tier), text: rung.governed.trust_tier })
                ),
                el("p", { className: "outcome-kpi", text: govHeadline }),
                el("p", { className: "outcome-detail", text: govDetail }),
                buildIdentitySwitchPanel(rung)
              )
            )
          ),
          buildXrayInspector(rung)
        ];
      }

      const main = el("main", { className: "workbench-main" },
        statusBar,
        liveBanner,
        buildProgressionBar(),
        mainSection
      );

      return el("div", { className: "workbench-shell" }, header, main);
    }

    /* ----------------------------------------------------------------------
       CDO Myth-Busting Poll Modal
       ---------------------------------------------------------------------- */

    function buildPollModal() {
      if (!state.pollOpen) {
        return null;
      }
      const rung = activeRung();
      const poll = rung.poll;

      const optionsList = el("div", { className: "poll-options" },
        ...poll.options.map((opt) => {
          const isSelected = state.pollSelectedKey === opt.key;
          const isCorrect = state.pollRevealed && opt.key === poll.correct_key;
          const isWrongSelection = state.pollRevealed && isSelected && opt.key !== poll.correct_key;
          let cls = "poll-option-btn";
          if (isCorrect) {
            cls += " is-correct";
          } else if (isWrongSelection) {
            cls += " is-incorrect";
          } else if (isSelected) {
            cls += " is-selected";
          }

          return el("button", {
            className: cls,
            attrs: {
              type: "button",
              "aria-pressed": isSelected ? "true" : "false",
              "data-poll-key": opt.key
            },
            onClick: () => setState({ pollSelectedKey: opt.key })
          },
            el("span", { className: "poll-key-pill", text: opt.key }),
            el("span", { text: opt.text })
          );
        })
      );

      const backdrop = el("div", {
        className: "modal-backdrop",
        attrs: { role: "presentation" },
        onClick: (e) => {
          if (e.target === backdrop) {
            setState({ pollOpen: false });
          }
        }
      },
        el("div", {
          className: "modal-dialog",
          attrs: {
            role: "dialog",
            "aria-modal": "true",
            "aria-labelledby": "poll-modal-title"
          }
        },
          el("div", { className: "modal-head" },
            el("div", null,
              el("span", { className: "badge badge-mono", text: `CDO Myth-Busting Poll · ${rung.short_label}` }),
              el("h2", { className: "modal-title", id: "poll-modal-title", text: poll.prompt })
            ),
            el("button", {
              className: "btn",
              text: "Close [Esc]",
              attrs: { type: "button", "aria-label": "Close poll dialog" },
              onClick: () => setState({ pollOpen: false })
            })
          ),
          optionsList,
          state.pollRevealed
            ? el("div", { className: "poll-takeaway", attrs: { role: "status" } },
                el("strong", { text: `Answer ${poll.correct_key}: ` }),
                el("span", { text: poll.reveal_takeaway })
              )
            : null,
          el("div", { className: "modal-foot" },
            el("span", { className: "eval-label", text: "Select A / B / C / D then reveal answer" }),
            el("div", { className: "stage-actions" },
              el("button", {
                className: "btn",
                text: "Reset",
                attrs: { type: "button" },
                onClick: () => setState({ pollSelectedKey: null, pollRevealed: false })
              }),
              el("button", {
                className: "btn btn-primary",
                text: state.pollRevealed ? "Answer Revealed" : "Reveal Answer",
                attrs: { type: "button", disabled: state.pollRevealed ? true : null },
                onClick: () => setState({ pollRevealed: true })
              })
            )
          )
        )
      );

      return backdrop;
    }

    /* ----------------------------------------------------------------------
       Main Render & Global Keyboard Controls
       ---------------------------------------------------------------------- */

    function render() {
      syncUrlAndDocument();
      const mainShell = state.mode === "workbench" ? buildWorkbenchView() : buildStageView();
      const pollModal = buildPollModal();
      if (pollModal) {
        root.replaceChildren(mainShell, pollModal);
      } else {
        root.replaceChildren(mainShell);
      }
    }

    function isEditableTarget(target) {
      if (!target || !(target instanceof HTMLElement)) {
        return false;
      }
      const tag = target.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
    }

    window.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.metaKey || e.altKey || isEditableTarget(e.target)) {
        return;
      }
      if (e.code === "Escape") {
        if (state.pollOpen) {
          e.preventDefault();
          setState({ pollOpen: false });
        }
        return;
      }
      if (e.code === "KeyP") {
        e.preventDefault();
        togglePoll();
        return;
      }
      if (state.pollOpen) {
        return;
      }
      if (e.code === "Space" || e.code === "ArrowRight") {
        e.preventDefault();
        stepForward();
        return;
      }
      if (e.code === "ArrowLeft") {
        e.preventDefault();
        stepBackward();
        return;
      }
      if (e.code === "KeyB") {
        e.preventDefault();
        cycleBeatB();
        return;
      }
      if (e.code === "KeyW") {
        e.preventDefault();
        toggleMode();
        return;
      }
      if (e.code === "KeyT") {
        e.preventDefault();
        toggleTheme();
      }
    });

    render();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
  } else {
    initApp();
  }
})();
