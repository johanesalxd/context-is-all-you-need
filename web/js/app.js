(function () {
  "use strict";

  const VALID_MODES = new Set(["stage", "workbench"]);
  const VALID_BEATS = new Set(["question", "blind", "governed", "compare"]);
  const VALID_THEMES = new Set(["paper", "dark"]);
  const VALID_TABS = new Set(["context", "sql", "arch"]);
  const VALID_AGENT_ARMS = new Set(["both", "blind", "governed"]);
  const BEAT_CYCLE_B = ["blind", "governed", "compare"];
  const DEMO_KEY_STORAGE = "context_demo_key";

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
    const headline = String(variant.answer_headline || "").trim();
    const val = variant.numeric_value;
    const rungUnit = String((rung && rung.governed && rung.governed.unit) || "");
    const upperHeadline = headline.toUpperCase();
    const upperCurrency = currency ? String(currency).toUpperCase() : "";

    const leadingCurrencyMatch = headline.match(/^([A-Z]{3})(?=\s+[\d,.-])/);
    if (leadingCurrencyMatch) {
      return formatMetricValue(val, leadingCurrencyMatch[1], leadingCurrencyMatch[1]);
    }
    if (upperCurrency && upperHeadline.startsWith(upperCurrency)) {
      return formatMetricValue(val, upperCurrency, upperCurrency);
    }

    const pctIdx = headline.indexOf("%");
    const currencyIdx = upperCurrency ? upperHeadline.indexOf(upperCurrency) : -1;
    if (currencyIdx >= 0 && (pctIdx === -1 || currencyIdx < pctIdx)) {
      return formatMetricValue(val, upperCurrency, upperCurrency);
    }

    if (
      ["PCT", "%"].includes(rungUnit.toUpperCase()) &&
      typeof val === "number" &&
      Math.abs(val) <= 100 &&
      pctIdx >= 0 &&
      (currencyIdx === -1 || pctIdx < currencyIdx)
    ) {
      return formatMetricValue(val, "%", currency);
    }

    if (rungUnit && !["PCT", "%"].includes(rungUnit.toUpperCase())) {
      return formatMetricValue(val, rungUnit, currency);
    }
    return formatNumber(val);
  }

  function formatGeneratedMode(mode) {
    switch (mode) {
      case "live_agent_verified":
        return "Live Agent Verified";
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

  function getSavedDemoKey() {
    try {
      return (window.sessionStorage && window.sessionStorage.getItem(DEMO_KEY_STORAGE)) || "";
    } catch (_e) {
      return "";
    }
  }

  function saveDemoKey(value) {
    try {
      if (!window.sessionStorage) {
        return;
      }
      const trimmed = String(value || "").trim();
      if (trimmed) {
        window.sessionStorage.setItem(DEMO_KEY_STORAGE, trimmed);
      } else {
        window.sessionStorage.removeItem(DEMO_KEY_STORAGE);
      }
    } catch (_e) {}
  }

  function extractErrorMessage(data, status) {
    if (data && data.detail !== undefined && data.detail !== null) {
      return typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    }
    if (data && data.error !== undefined && data.error !== null) {
      return typeof data.error === "string" ? data.error : JSON.stringify(data.error);
    }
    return `HTTP ${status}`;
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
      overview: raw.overview && typeof raw.overview === "object" ? raw.overview : null,
      horizon_cards: Array.isArray(raw.horizon_cards) ? raw.horizon_cards : []
    };
  }

  function resolveRungSelection(rungs, rawParam, options) {
    const hasOverview = Boolean(options && options.hasOverview);
    const mode = (options && options.mode) || "stage";
    if (!rawParam) {
      return { isOverview: hasOverview && mode === "stage", isHorizon: false, rungIndex: 0 };
    }
    const trimmed = String(rawParam).trim();
    const lowered = trimmed.toLowerCase();
    if (lowered === "overview") {
      return { isOverview: hasOverview && mode === "stage", isHorizon: false, rungIndex: 0 };
    }
    if (lowered === "horizon") {
      return { isOverview: false, isHorizon: true, rungIndex: 0 };
    }
    const byId = rungs.findIndex((r) => r.id === trimmed);
    if (byId >= 0) {
      return { isOverview: false, isHorizon: false, rungIndex: byId };
    }
    const num = Number.parseInt(trimmed, 10);
    if (Number.isFinite(num)) {
      const byNum = rungs.findIndex((r) => Number(r.rung_num) === num);
      if (byNum >= 0) {
        return { isOverview: false, isHorizon: false, rungIndex: byNum };
      }
      if (num >= 1 && num <= rungs.length) {
        return { isOverview: false, isHorizon: false, rungIndex: num - 1 };
      }
    }
    return { isOverview: false, isHorizon: false, rungIndex: 0 };
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

  function getEmpiricalPair(rung) {
    const blindEmp = rung && rung.blind && rung.blind.empirical_eval ? rung.blind.empirical_eval : null;
    const govEmp = rung && rung.governed && rung.governed.empirical_eval ? rung.governed.empirical_eval : null;
    return {
      hasAny: Boolean(blindEmp || govEmp),
      blindEmp,
      govEmp
    };
  }

  function formatEmpiricalHeadline(rung) {
    const { hasAny, blindEmp, govEmp } = getEmpiricalPair(rung);
    if (!hasAny) {
      return null;
    }
    const runs = Number((govEmp && govEmp.runs) || (blindEmp && blindEmp.runs) || 5);
    const blindStr = blindEmp ? `${blindEmp.pass_count}/${blindEmp.runs}` : "—";
    const govStr = govEmp ? `${govEmp.pass_count}/${govEmp.runs}` : "—";
    return `Empirical N=${runs}: ${blindStr} → ${govStr}`;
  }

  function initApp() {
    const root = document.getElementById("app-root");
    const params = new URLSearchParams(window.location.search);
    const urlDemoKey = params.get("key");
    if (urlDemoKey) {
      saveDemoKey(urlDemoKey);
      params.delete("key");
      try {
        const cleanedQuery = params.toString();
        const cleanedUrl = cleanedQuery
          ? `${window.location.pathname}?${cleanedQuery}`
          : window.location.pathname;
        window.history.replaceState(null, "", cleanedUrl);
      } catch (_err) {
        // Ignore history restrictions on strict file:// sandboxes.
      }
    }

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

    const hasOverview = Boolean(bundle.overview);
    const initMode = VALID_MODES.has(params.get("mode")) ? params.get("mode") : "stage";
    const initTheme = VALID_THEMES.has(params.get("theme")) ? params.get("theme") : "paper";
    const initBeat = VALID_BEATS.has(params.get("beat")) ? params.get("beat") : "compare";
    const initTab = VALID_TABS.has(params.get("tab")) ? params.get("tab") : "context";
    const initRungSel = resolveRungSelection(bundle.rungs, params.get("rung"), { hasOverview, mode: initMode });

    const state = {
      mode: initMode,
      theme: initTheme,
      beat: initBeat,
      tab: initTab,
      isOverview: initRungSel.isOverview,
      isHorizon: initRungSel.isHorizon,
      rungIndex: initRungSel.rungIndex,
      preferredPersona: params.get("persona") || null,
      helpOpen: false,
      pollOpen: false,
      pollSelectedKey: null,
      pollRevealed: false,
      pollLiveCounts: { A: 0, B: 0, C: 0, D: 0 },
      pollLiveTotal: 0,
      pollLiveEpoch: 1,
      pollLiveOnline: false,
      pollResetBusy: false,
      pollResetConfirmPending: false,
      pendingPollReset: false,
      pollStatusMsg: null,
      stageXrayOpen: false,
      liveTargetMode: "governed",
      liveLoading: false,
      liveResult: null,
      health: null,
      healthLoaded: false,
      agentArm: "both",
      agentLoading: false,
      agentError: null,
      agentResult: null,
      authDialogOpen: false,
      authDialogError: null,
      authKeyVisible: false,
      authInputDraft: "",
      pendingAgentAction: false,
      copiedPane: null
    };

    let pollIntervalId = null;
    let pollResetConfirmTimerId = null;
    let prevHelpOpen = false;

    function isNonRung() {
      return state.isOverview || state.isHorizon;
    }

    function cancelPollResetConfirm() {
      if (pollResetConfirmTimerId !== null) {
        window.clearTimeout(pollResetConfirmTimerId);
        pollResetConfirmTimerId = null;
      }
      state.pollResetConfirmPending = false;
    }

    function stopPollTimer() {
      if (pollIntervalId !== null) {
        window.clearInterval(pollIntervalId);
        pollIntervalId = null;
      }
    }

    function patchPollModalInPlace(rungId, counts, totalVotes) {
      const modal = document.querySelector(`[data-poll-modal-rung="${rungId}"]`);
      if (!modal) {
        return false;
      }
      const badge = modal.querySelector("#poll-live-count-badge");
      if (badge) {
        badge.textContent = `${totalVotes} room votes`;
      }
      const optButtons = modal.querySelectorAll("[data-poll-key]");
      for (const btn of optButtons) {
        const key = btn.getAttribute("data-poll-key");
        if (!key) {
          continue;
        }
        const optCount = Number(counts[key] || 0);
        const pct = totalVotes > 0 ? Math.round((optCount / totalVotes) * 100) : 0;
        const bar = btn.querySelector(".poll-option-bar");
        if (bar) {
          bar.style.width = `${pct}%`;
        }
        const stat = btn.querySelector(".poll-option-stat");
        if (stat) {
          if (totalVotes > 0) {
            stat.textContent = `${optCount} · ${pct}%`;
            stat.removeAttribute("hidden");
          } else {
            stat.textContent = "";
            stat.setAttribute("hidden", "hidden");
          }
        }
      }
      return true;
    }

    async function fetchPollState() {
      if (window.location.protocol === "file:" || !state.pollOpen || isNonRung() || state.authDialogOpen) {
        return;
      }
      const rung = activeRung();
      const url = `/api/poll/state?pack_id=${encodeURIComponent(bundle.pack_id)}&rung_id=${encodeURIComponent(rung.id)}`;
      try {
        const res = await fetch(url, { method: "GET", cache: "no-store" });
        if (!res.ok) {
          return;
        }
        const data = await res.json().catch(() => null);
        if (!data || typeof data !== "object") {
          return;
        }
        if (!state.pollOpen || isNonRung() || state.authDialogOpen || activeRung().id !== rung.id) {
          return;
        }
        const rawCounts = data.counts && typeof data.counts === "object" ? data.counts : {};
        const nextCounts = {
          A: Number(rawCounts.A || 0),
          B: Number(rawCounts.B || 0),
          C: Number(rawCounts.C || 0),
          D: Number(rawCounts.D || 0)
        };
        const nextTotal = Number(data.total_votes || 0);
        const nextEpoch = Number(data.epoch || 1);
        const countsChanged =
          nextCounts.A !== state.pollLiveCounts.A ||
          nextCounts.B !== state.pollLiveCounts.B ||
          nextCounts.C !== state.pollLiveCounts.C ||
          nextCounts.D !== state.pollLiveCounts.D;
        if (
          !state.pollLiveOnline ||
          countsChanged ||
          nextTotal !== state.pollLiveTotal ||
          nextEpoch !== state.pollLiveEpoch
        ) {
          state.pollLiveOnline = true;
          state.pollLiveCounts = nextCounts;
          state.pollLiveTotal = nextTotal;
          state.pollLiveEpoch = nextEpoch;
          if (!patchPollModalInPlace(rung.id, nextCounts, nextTotal)) {
            render();
          }
        }
      } catch (_err) {
        // Keep current counts silently if network temporarily drops.
      }
    }

    function syncStageIfAuthorized() {
      if (window.location.protocol === "file:" || isNonRung()) {
        return;
      }
      const savedKey = getSavedDemoKey();
      if (!savedKey) {
        return;
      }
      const rung = activeRung();
      fetch("/api/poll/sync-stage", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Demo-Key": savedKey
        },
        body: JSON.stringify({
          pack_id: bundle.pack_id,
          rung_id: rung.id
        })
      }).catch(() => {});
    }

    function startPollTimer() {
      stopPollTimer();
      if (!state.pollOpen || isNonRung() || window.location.protocol === "file:") {
        return;
      }
      fetchPollState();
      syncStageIfAuthorized();
      pollIntervalId = window.setInterval(() => {
        if (state.pollOpen && !isNonRung() && document.visibilityState === "visible") {
          fetchPollState();
        }
      }, 2000);
    }

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && state.pollOpen && !isNonRung() && window.location.protocol !== "file:") {
        fetchPollState();
      }
    });

    function activeRung() {
      return bundle.rungs[state.rungIndex] || bundle.rungs[0];
    }

    function activePersonaId() {
      if (isNonRung()) {
        return null;
      }
      return resolvePersonaForRung(activeRung(), state.preferredPersona, bundle);
    }

    function activeContextKey() {
      const rung = activeRung();
      const pid = activePersonaId();
      return `${rung.id}:${pid || ""}`;
    }

    function getRegionalHonestyText() {
      const dataRegion = (state.health && state.health.bq_location) || bundle.region || "asia-southeast1";
      const inferRegion = (state.health && state.health.agent_model_location) || "global";
      return `Data, Graph, Catalog & RLS in ${dataRegion} · Gemini PayGo Inference via ${inferRegion} Endpoint`;
    }

    function syncUrlAndDocument() {
      document.documentElement.setAttribute("data-theme", state.theme);
      document.documentElement.setAttribute("data-mode", state.mode);

      const nextParams = new URLSearchParams();
      nextParams.set("mode", state.mode);
      nextParams.set("rung", state.isOverview ? "overview" : (state.isHorizon ? "horizon" : String(activeRung().rung_num)));
      if (state.mode === "stage" && !isNonRung()) {
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

    function selectRung(index, opts = {}) {
      const nextBeat = opts && VALID_BEATS.has(opts.beat)
        ? opts.beat
        : (state.isOverview ? "question" : "compare");
      stopPollTimer();
      cancelPollResetConfirm();
      setState({
        isOverview: false,
        isHorizon: false,
        rungIndex: Math.max(0, Math.min(bundle.rungs.length - 1, index)),
        beat: nextBeat,
        pollOpen: false,
        stageXrayOpen: false,
        helpOpen: false,
        pollSelectedKey: null,
        pollRevealed: false,
        pollLiveCounts: { A: 0, B: 0, C: 0, D: 0 },
        pollLiveTotal: 0,
        pollLiveEpoch: 1,
        pollLiveOnline: false,
        pollStatusMsg: null,
        liveResult: null,
        agentError: null,
        agentResult: null
      });
    }

    function selectOverview() {
      if (!hasOverview) {
        return;
      }
      stopPollTimer();
      cancelPollResetConfirm();
      setState({
        mode: "stage",
        isOverview: true,
        isHorizon: false,
        pollOpen: false,
        stageXrayOpen: false,
        helpOpen: false,
        liveResult: null,
        agentError: null,
        agentResult: null
      });
    }

    function selectHorizon() {
      stopPollTimer();
      cancelPollResetConfirm();
      setState({
        isOverview: false,
        isHorizon: true,
        pollOpen: false,
        stageXrayOpen: false,
        helpOpen: false,
        liveResult: null,
        agentError: null,
        agentResult: null
      });
    }

    function stepForward() {
      if (state.isHorizon) {
        return;
      }
      if (state.isOverview) {
        selectRung(0, { beat: "question" });
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
      if (state.rungIndex < bundle.rungs.length - 1) {
        setState({
          rungIndex: state.rungIndex + 1,
          beat: "question",
          pollSelectedKey: null,
          pollRevealed: false,
          pollLiveCounts: { A: 0, B: 0, C: 0, D: 0 },
          pollLiveTotal: 0,
          pollLiveEpoch: 1,
          pollLiveOnline: false,
          pollStatusMsg: null,
          liveResult: null,
          agentError: null,
          agentResult: null
        });
      } else {
        selectHorizon();
      }
    }

    function stepBackward() {
      if (state.isOverview) {
        return;
      }
      if (state.isHorizon) {
        setState({
          isOverview: false,
          isHorizon: false,
          rungIndex: bundle.rungs.length - 1,
          beat: "governed",
          liveResult: null,
          agentError: null,
          agentResult: null
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
          beat: "governed",
          pollSelectedKey: null,
          pollRevealed: false,
          pollLiveCounts: { A: 0, B: 0, C: 0, D: 0 },
          pollLiveTotal: 0,
          pollLiveEpoch: 1,
          pollLiveOnline: false,
          pollStatusMsg: null,
          liveResult: null,
          agentError: null,
          agentResult: null
        });
      } else if (hasOverview && (state.beat === "question" || state.beat === "compare")) {
        selectOverview();
      }
    }

    function cycleBeatB() {
      if (isNonRung()) {
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
      stopPollTimer();
      cancelPollResetConfirm();
      const nextMode = state.mode === "stage" ? "workbench" : "stage";
      setState({
        mode: nextMode,
        isOverview: nextMode === "workbench" ? false : state.isOverview,
        pollOpen: false,
        stageXrayOpen: false,
        helpOpen: false
      });
    }

    function toggleTheme() {
      setState({
        theme: state.theme === "paper" ? "dark" : "paper"
      });
    }

    function toggleHelp() {
      if (state.authDialogOpen) {
        return;
      }
      const nextOpen = !state.helpOpen;
      if (nextOpen) {
        stopPollTimer();
        cancelPollResetConfirm();
      }
      setState({
        helpOpen: nextOpen,
        pollOpen: false,
        stageXrayOpen: false
      });
    }

    function togglePoll() {
      if (state.isOverview) {
        return;
      }
      if (state.isHorizon && !state.pollOpen) {
        setState({
          isHorizon: false,
          pollOpen: true,
          pollStatusMsg: null,
          stageXrayOpen: false,
          helpOpen: false
        });
        startPollTimer();
        return;
      }
      const nextOpen = !state.pollOpen;
      if (!nextOpen) {
        stopPollTimer();
      }
      setState({
        pollOpen: nextOpen,
        pollStatusMsg: nextOpen ? null : state.pollStatusMsg,
        stageXrayOpen: false,
        helpOpen: false
      });
      if (nextOpen) {
        startPollTimer();
      }
    }

    function toggleStageXray() {
      if (state.mode !== "stage" || isNonRung() || state.pollOpen || state.helpOpen) {
        return;
      }
      setState({ stageXrayOpen: !state.stageXrayOpen });
    }

    async function fetchHealth() {
      if (window.location.protocol === "file:") {
        return;
      }
      try {
        const res = await fetch("/api/health", { method: "GET" });
        if (!res.ok) {
          return;
        }
        const data = await res.json().catch(() => null);
        if (data && typeof data === "object") {
          state.health = data;
          state.healthLoaded = true;
          if (!state.authDialogOpen && !state.pollOpen && !isEditableTarget(document.activeElement)) {
            render();
          }
        }
      } catch (_err) {
        // Silent fallback when static file server has no /api/health endpoint.
      }
    }

    async function handleRunLiveQuery() {
      if (isNonRung()) {
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
        const reqHeaders = { "Content-Type": "application/json" };
        const savedKey = getSavedDemoKey();
        if (savedKey) {
          reqHeaders["X-Demo-Key"] = savedKey;
        }
        const response = await fetch("/api/run-rung", {
          method: "POST",
          headers: reqHeaders,
          body: JSON.stringify(payload)
        });
        const elapsedMs = Math.round(performance.now() - startedAt);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = extractErrorMessage(data, response.status);
          setState({
            liveLoading: false,
            liveResult: {
              kind: "error",
              message: `Live query request failed (${elapsedMs} ms): ${detail}`
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

    function openAuthPrompt(errorMsg, retryAgentAfterSave, retryPollResetAfterSave) {
      setState({
        authDialogOpen: true,
        authDialogError: errorMsg || null,
        authInputDraft: "",
        pendingAgentAction: Boolean(retryAgentAfterSave),
        pendingPollReset: Boolean(retryPollResetAfterSave)
      });
      window.requestAnimationFrame(() => {
        const input = document.getElementById("demo-key-input");
        if (input) {
          input.focus();
        }
      });
    }

    async function handleClearRoomVotes() {
      if (window.location.protocol === "file:" || state.pollResetBusy || isNonRung()) {
        return;
      }
      const savedKey = getSavedDemoKey();
      if (!savedKey) {
        openAuthPrompt("A Demo Share Key (X-Demo-Key) is required to clear room votes.", false, true);
        return;
      }
      const rung = activeRung();
      setState({
        pollResetBusy: true,
        pollStatusMsg: null,
        authDialogOpen: false,
        authDialogError: null,
        pendingPollReset: false
      });

      try {
        const response = await fetch("/api/poll/reset", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Demo-Key": savedKey
          },
          body: JSON.stringify({
            pack_id: bundle.pack_id,
            rung_id: rung.id
          })
        });
        const data = await response.json().catch(() => ({}));
        if (response.status === 401) {
          const detail = extractErrorMessage(data, response.status);
          setState({ pollResetBusy: false });
          openAuthPrompt(`Authentication failed (401): ${detail}. Paste a valid X-Demo-Key to clear room votes.`, false, true);
          return;
        }
        if (!response.ok) {
          setState({
            pollResetBusy: false,
            pollStatusMsg: `Clear votes failed (${extractErrorMessage(data, response.status)})`
          });
          return;
        }
        const rawCounts = data.counts && typeof data.counts === "object" ? data.counts : {};
        setState({
          pollResetBusy: false,
          pollLiveOnline: true,
          pollLiveCounts: {
            A: Number(rawCounts.A || 0),
            B: Number(rawCounts.B || 0),
            C: Number(rawCounts.C || 0),
            D: Number(rawCounts.D || 0)
          },
          pollLiveTotal: Number(data.total_votes || 0),
          pollLiveEpoch: Number(data.epoch || 1),
          pollStatusMsg: `Room votes cleared (Epoch ${Number(data.epoch || 1)}).`
        });
      } catch (err) {
        setState({
          pollResetBusy: false,
          pollStatusMsg: `Clear votes unreachable: ${err && err.message ? err.message : "Network error"}`
        });
      }
    }

    async function handleRunLiveAgent() {
      if (isNonRung()) {
        return;
      }
      if (window.location.protocol === "file:") {
        setState({
          agentError: "Offline file:// mode active — live Gemini agent execution is disabled. Serve via uvicorn server.app:app over http:// or Cloud Run."
        });
        return;
      }
      if (state.health && state.health.live_agent_enabled === false) {
        setState({
          agentError: "Live agent runner is disabled by server configuration (ENABLE_LIVE_AGENT=false)."
        });
        return;
      }

      const savedKey = getSavedDemoKey();
      const tokenRequired = state.health ? state.health.live_agent_token_required === true : false;
      if (tokenRequired && !savedKey) {
        openAuthPrompt("A Demo Share Key (X-Demo-Key) is required to run the live Gemini agent.", true);
        return;
      }

      const rung = activeRung();
      const personaId = activePersonaId();
      const contextKey = activeContextKey();
      const arm = VALID_AGENT_ARMS.has(state.agentArm) ? state.agentArm : "both";
      const payload = {
        pack_id: bundle.pack_id,
        rung_id: rung.id,
        arm
      };
      if (personaId) {
        payload.persona_id = personaId;
      }

      setState({
        agentLoading: true,
        agentError: null,
        authDialogOpen: false,
        authDialogError: null,
        pendingAgentAction: false
      });

      const startedAt = performance.now();
      try {
        const reqHeaders = { "Content-Type": "application/json" };
        if (savedKey) {
          reqHeaders["X-Demo-Key"] = savedKey;
        }
        const response = await fetch("/api/run-agent", {
          method: "POST",
          headers: reqHeaders,
          body: JSON.stringify(payload)
        });
        const elapsedMs = Math.round(performance.now() - startedAt);
        const data = await response.json().catch(() => ({}));

        if (response.status === 401) {
          const detail = extractErrorMessage(data, response.status);
          setState({
            agentLoading: false,
            agentError: null
          });
          openAuthPrompt(`Authentication failed (401): ${detail}. Paste a valid X-Demo-Key to retry.`, true);
          return;
        }

        if (!response.ok) {
          const detail = extractErrorMessage(data, response.status);
          setState({
            agentLoading: false,
            agentError: `Live agent request failed (${elapsedMs} ms, HTTP ${response.status}): ${detail}`
          });
          return;
        }

        if (activeContextKey() !== contextKey) {
          setState({ agentLoading: false });
          return;
        }

        setState({
          agentLoading: false,
          agentError: null,
          agentResult: {
            contextKey,
            elapsedMs,
            data
          }
        });
      } catch (err) {
        const elapsedMs = Math.round(performance.now() - startedAt);
        setState({
          agentLoading: false,
          agentError: `Live agent endpoint unreachable (${elapsedMs} ms): ${err && err.message ? err.message : "Network error"}`
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

    function buildRegionalHonestyBadge() {
      return el("span", {
        className: "badge badge-region",
        attrs: { "data-regional-honesty": "true" },
        text: getRegionalHonestyText()
      });
    }

    function buildRungStepper() {
      const group = el("nav", {
        className: "stage-stepper segmented-group",
        attrs: { "aria-label": "Rung progression" }
      });

      if (hasOverview && state.mode === "stage") {
        group.appendChild(
          el("button", {
            className: `seg-btn is-overview${state.isOverview ? " is-active" : ""}`,
            text: "Overview",
            attrs: {
              type: "button",
              title: "Executive Briefing Overview",
              "aria-label": "Overview: Executive Briefing",
              "aria-current": state.isOverview ? "step" : null,
              "data-rung-id": "overview"
            },
            onClick: () => selectOverview()
          })
        );
      }

      bundle.rungs.forEach((rung, idx) => {
        const isActive = !isNonRung() && state.rungIndex === idx;
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
            onClick: () => selectRung(idx, state.isOverview ? { beat: "question" } : {})
          })
        );
      });

      group.appendChild(
        el("button", {
          className: `seg-btn is-horizon${state.isHorizon ? " is-active" : ""}`,
          text: "What's Next",
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
          onClick: () => {
            stopPollTimer();
            cancelPollResetConfirm();
            setState({ mode: "stage", pollOpen: false, stageXrayOpen: false, helpOpen: false });
          }
        }, "Stage ", el("span", { className: "kbd-hint", text: "W" })),
        el("button", {
          className: `seg-btn${state.mode === "workbench" ? " is-active" : ""}`,
          attrs: { type: "button", "aria-pressed": state.mode === "workbench" ? "true" : "false" },
          onClick: () => {
            stopPollTimer();
            cancelPollResetConfirm();
            setState({ mode: "workbench", isOverview: false, pollOpen: false, stageXrayOpen: false, helpOpen: false });
          }
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
            onClick: () => setState({ preferredPersona: pid, agentResult: null, agentError: null })
          })
        );
      }

      const variantMetric = variant
        ? formatVariantMetricValue(variant, rung, bundle.currency)
        : null;

      return el("section", {
        className: "identity-panel",
        attrs: { "aria-label": "Beat 4b Identity and Row-Level Security" }
      },
        el("div", { className: "identity-header" },
          el("span", { className: "identity-title", text: "Beat 4b · Switch Identity" }),
          segGroup
        ),
        variant
          ? el("div", { className: "identity-outcome-box" },
              el("div", { className: "identity-outcome-head" },
                el("strong", { className: "identity-outcome-kpi", text: variant.answer_headline }),
                el("span", { className: "badge badge-ga badge-mono", text: `Scoped Metric: ${variantMetric}` })
              ),
              el("p", { className: "identity-outcome-detail", text: variant.answer_detail })
            )
          : null,
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

    function extractLayerTag(pyramidLayer) {
      const raw = String(pyramidLayer || "").trim();
      if (!raw) {
        return "";
      }
      const sepIdx = raw.indexOf("·");
      return sepIdx >= 0 ? raw.slice(0, sepIdx).trim() : raw;
    }

    function buildOverviewShowcase() {
      const ov = bundle.overview;
      if (!ov) {
        return null;
      }

      const hero = el("section", {
        className: "overview-hero",
        attrs: { "aria-label": "Executive briefing headline" }
      },
        el("div", { className: "overview-hero-meta" },
          el("span", { className: "overview-eyebrow", text: ov.eyebrow }),
          el("span", { className: "badge badge-mono", text: `${bundle.closed_period_label} · ${bundle.currency}` })
        ),
        el("h1", { className: "overview-headline", text: ov.headline }),
        el("p", { className: "overview-subheadline", text: ov.subheadline })
      );

      const statsGrid = el("div", { className: "overview-stats-grid" },
        ...(Array.isArray(ov.estate_stats) ? ov.estate_stats : []).map((stat) =>
          el("div", { className: "overview-stat-tile" },
            el("div", { className: "overview-stat-value", text: stat.value }),
            el("div", { className: "overview-stat-label", text: stat.label }),
            el("div", { className: "overview-stat-detail", text: stat.detail })
          )
        )
      );

      const leftCard = el("article", {
        className: "overview-card",
        attrs: { "aria-label": `Customer profile: ${ov.company_name}` }
      },
        el("div", { className: "overview-card-head" },
          el("h2", { className: "overview-card-title", text: `Meet ${ov.company_name}` }),
          el("span", { className: "badge badge-mono", text: bundle.region })
        ),
        el("p", { className: "overview-body-copy", text: ov.company_profile }),
        statsGrid,
        el("div", { className: "overview-problem-box" },
          el("span", { className: "overview-problem-label", text: "Why Raw Schemas Fail" }),
          el("p", { className: "overview-problem-copy", text: ov.problem_statement })
        )
      );

      const exp = ov.experiment || {};
      const rightCard = el("article", {
        className: "overview-card",
        attrs: { "aria-label": "Live experiment design" }
      },
        el("div", { className: "overview-card-head" },
          el("h2", { className: "overview-card-title", text: "The Live Experiment" }),
          el("span", { className: "badge badge-ga", text: "Zero Spoilers" })
        ),
        el("div", { className: "overview-control-box" },
          el("span", { className: "overview-control-label", text: "Fixed Control" }),
          el("p", { className: "overview-body-copy", text: exp.fixed_control || "" })
        ),
        el("div", { className: "overview-arms-stack" },
          el("div", { className: "overview-arm-card is-blind" },
            el("div", { className: "overview-arm-head" },
              el("span", { className: "overview-arm-badge is-blind", text: "Blind Arm" }),
              el("span", { className: "badge badge-tier-3", text: "Raw Schema Only" })
            ),
            el("p", { className: "overview-arm-copy", text: exp.blind_arm || "" })
          ),
          el("div", { className: "overview-arm-card is-governed" },
            el("div", { className: "overview-arm-head" },
              el("span", { className: "overview-arm-badge is-governed", text: "Governed Arm" }),
              el("span", { className: "badge badge-ga", text: "Progressive Context" })
            ),
            el("p", { className: "overview-arm-copy", text: exp.governed_arm || "" })
          )
        )
      );

      const roadmapGrid = el("div", { className: "overview-roadmap-grid" },
        ...bundle.rungs.map((rung, idx) => {
          const layerTag = extractLayerTag(rung.pyramid_layer);
          return el("button", {
            className: "overview-roadmap-card",
            attrs: {
              type: "button",
              "data-overview-rung": rung.id,
              "aria-label": `R${rung.rung_num}: ${rung.question}`
            },
            onClick: () => selectRung(idx, { beat: "question" })
          },
            el("div", { className: "overview-roadmap-top" },
              el("span", { className: "overview-roadmap-label", text: rung.short_label }),
              layerTag
                ? el("span", { className: "badge badge-mono overview-layer-tag", text: layerTag })
                : null
            ),
            el("span", { className: "overview-roadmap-question", text: rung.question })
          );
        })
      );

      const roadmapSection = el("section", {
        className: "overview-roadmap",
        attrs: { "aria-label": "Boardroom simulation roadmap" }
      },
        el("div", { className: "overview-roadmap-header" },
          el("div", { className: "overview-roadmap-title-row" },
            el("h2", { className: "overview-roadmap-title", text: `${bundle.rungs.length} Live Boardroom Questions` }),
            el("button", {
              className: "overview-guide-link",
              text: "What are Layers 1–5? Open ? Guide",
              attrs: { type: "button" },
              onClick: () => toggleHelp()
            })
          ),
          el("span", { className: "overview-roadmap-hint", text: "Select any card to jump to its question" })
        ),
        roadmapGrid
      );

      return el("section", {
        className: "overview-showcase",
        attrs: { "aria-label": "Executive Briefing Overview" }
      },
        hero,
        el("div", { className: "overview-grid" }, leftCard, rightCard),
        roadmapSection
      );
    }

    function buildHorizonShowcase() {
      const grid = el("div", { className: "horizon-grid" });
      const cardTitles = [];
      for (const card of bundle.horizon_cards) {
        if (card && card.title) {
          cardTitles.push(card.title);
        }
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

      const subtitleText = cardTitles.length > 0
        ? `Rungs 1–6 execute strictly within ${bundle.region}. Horizon cards rendered dynamically from ${bundle.pack_id}: ${cardTitles.join(" · ")}.`
        : `Rungs 1–6 execute strictly within ${bundle.region}. Architectural capabilities below are decoupled from the live rung scope.`;

      return el("section", {
        className: "horizon-showcase",
        attrs: { "aria-label": "What's Next Architectural Horizon Showcase" }
      },
        el("div", { className: "horizon-banner" },
          el("span", { className: "horizon-banner-eyebrow", text: "What's Next · Architectural Horizon (Decoupled from R1–R6 Live Scope)" }),
          el("h1", { className: "horizon-banner-title", text: "What's Next · Horizon & Multi-Cloud" }),
          el("p", {
            className: "horizon-banner-subtitle",
            text: subtitleText
          })
        ),
        grid
      );
    }

    function buildEmpiricalSummaryBlock(rung, copyKeyPrefix) {
      const { hasAny, blindEmp, govEmp } = getEmpiricalPair(rung);
      if (!hasAny) {
        return el("div", { className: "empirical-empty-note" },
          el("span", {
            text: `Empirical N=5 telemetry has not been attached to this bundle yet (Target: Blind ${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs} → Governed ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}). Run eval_harness.py --runs 5 --live-gcp to populate live N=5 metrics.`
          })
        );
      }

      const arms = [
        { key: "blind", label: "Blind Arm (Raw Schema Only)", outcome: rung.blind, emp: blindEmp },
        { key: "governed", label: "Governed Arm (Catalog + Contracts)", outcome: rung.governed, emp: govEmp }
      ];

      return el("div", { className: "empirical-cards-grid" },
        ...arms.map(({ key, label, outcome, emp }) =>
          el("div", { className: `empirical-arm-card is-${key}` },
            el("div", { className: "outcome-card-head" },
              el("strong", { className: "outcome-role-title", text: label }),
              emp
                ? el("span", {
                    className: emp.pass_count === emp.runs ? "badge badge-ga badge-mono" : "badge badge-tier-3 badge-mono",
                    text: `Empirical N=${emp.runs}: ${emp.pass_count}/${emp.runs} · Target: ${outcome.eval_pass_count}/${outcome.eval_total_runs}`
                  })
                : el("span", {
                    className: "badge badge-mono",
                    text: `Target: ${outcome.eval_pass_count}/${outcome.eval_total_runs}`
                  })
            ),
            emp
              ? [
                  el("div", { className: "empirical-meta-row" },
                    el("span", { className: "badge badge-mono", text: `${emp.model_id} (${emp.model_location})` }),
                    el("span", { className: "badge badge-mono", text: `Median Tokens: ${formatNumber(emp.median_tokens)}` }),
                    el("span", { className: "badge badge-mono", text: `Queries: ${emp.median_exploratory_queries}` }),
                    el("span", { className: "badge badge-mono", text: `Retries: ${emp.median_error_retries}` }),
                    el("span", { className: "badge badge-mono", text: `Latency: ${Math.round(emp.median_latency_ms)} ms` })
                  ),
                  Array.isArray(emp.observed_signals) && emp.observed_signals.length > 0
                    ? el("div", { className: "signal-chips" },
                        ...emp.observed_signals.map((sig) =>
                          el("span", { className: "badge badge-mono", text: sig })
                        )
                      )
                    : null,
                  emp.sample_sql_or_gql
                    ? el("div", { className: "code-pane" },
                        el("div", { className: "code-pane-head" },
                          el("span", { className: "badge badge-mono", text: "Median-Token Representative SQL / GQL" }),
                          el("button", {
                            className: "btn",
                            text: state.copiedPane === `${copyKeyPrefix}_${key}_emp` ? "Copied" : "Copy",
                            attrs: { type: "button" },
                            onClick: () => copyTextToClipboard(`${copyKeyPrefix}_${key}_emp`, emp.sample_sql_or_gql)
                          })
                        ),
                        buildHighlightedCodeNodes(emp.sample_sql_or_gql)
                      )
                    : null
                ]
              : el("p", { className: "outcome-detail", text: "Empirical runs not recorded for this arm." })
          )
        )
      );
    }

    /* ----------------------------------------------------------------------
       Stage Mode Renderer (10% / 80% / 10% Quiet Stage V2 + [X] X-Ray Drawer)
       ---------------------------------------------------------------------- */

    function buildMetricsStrip(outcome) {
      const emp = outcome.empirical_eval;
      return el("div", { className: "outcome-metrics-strip" },
        el("div", { className: "metric-chip" },
          el("span", { className: "metric-chip-label", text: emp ? "Target Eval" : "Golden Eval" }),
          el("span", { className: "metric-chip-value", text: `${outcome.eval_pass_count}/${outcome.eval_total_runs}` })
        ),
        emp
          ? el("div", { className: "metric-chip is-empirical" },
              el("span", { className: "metric-chip-label", text: `Empirical N=${emp.runs}` }),
              el("span", { className: "metric-chip-value", text: `${emp.pass_count}/${emp.runs}` })
            )
          : null,
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

    function buildStageXrayDrawer() {
      if (state.mode !== "stage" || isNonRung() || !state.stageXrayOpen) {
        return null;
      }
      const rung = activeRung();

      const backdrop = el("div", {
        className: "xray-drawer-backdrop",
        attrs: { role: "presentation" },
        onClick: (e) => {
          if (e.target === backdrop) {
            setState({ stageXrayOpen: false });
          }
        }
      },
        el("section", {
          className: "xray-drawer",
          attrs: {
            id: "stage-xray-drawer",
            role: "dialog",
            "aria-modal": "true",
            "aria-labelledby": "stage-xray-drawer-title"
          }
        },
          el("header", { className: "xray-drawer-head" },
            el("div", { className: "xray-drawer-title-block" },
              el("div", { className: "outcome-label-group" },
                el("span", { className: "badge badge-mono", text: `Stage X-Ray · ${rung.short_label}` }),
                buildRegionalHonestyBadge()
              ),
              el("h2", {
                className: "xray-drawer-title",
                attrs: { id: "stage-xray-drawer-title" },
                text: `${rung.title} — Live Governance & Telemetry Proof`
              })
            ),
            el("div", { className: "stage-actions" },
              el("button", {
                className: "btn",
                text: "Open Full Workbench [W]",
                attrs: { type: "button" },
                onClick: () => setState({ mode: "workbench", stageXrayOpen: false })
              }),
              el("button", {
                className: "btn btn-primary",
                text: "Close [Esc]",
                attrs: { type: "button", "aria-label": "Close Stage X-Ray drawer" },
                onClick: () => setState({ stageXrayOpen: false })
              })
            )
          ),
          el("div", { className: "xray-drawer-body" },
            el("section", { className: "xray-drawer-section", attrs: { "aria-label": "Injected Knowledge Catalog and Governance Context" } },
              el("h3", { className: "progression-title", text: "1. Injected Knowledge Catalog & Governance Context" }),
              el("div", { className: "context-callout" },
                el("span", { className: "context-callout-label", text: "Context Mechanism:" }),
                el("span", { text: rung.governed.context_mechanism || rung.xray_summary.context_added })
              ),
              el("p", { className: "outcome-detail", text: `Context Added: ${rung.xray_summary.context_added}` }),
              el("div", { className: "release-badges-row" },
                ...rung.release_badges.map((rb) =>
                  el("span", {
                    className: stageBadgeClass(rb.stage),
                    text: `${rb.capability} · ${rb.stage} (${rb.region_scope})`
                  })
                ),
                ...rung.xray_summary.gcp_primitives.map((prim) =>
                  el("span", { className: "primitive-chip", text: prim })
                )
              ),
              el("div", { className: "code-pane" },
                el("div", { className: "code-pane-head" },
                  el("span", { className: "badge badge-mono", text: "Injected Context Payload" }),
                  el("button", {
                    className: "btn",
                    text: state.copiedPane === "drawer_context" ? "Copied" : "Copy Payload",
                    attrs: { type: "button" },
                    onClick: () => copyTextToClipboard("drawer_context", prettyJsonOrText(rung.governed.context_payload))
                  })
                ),
                el("pre", { className: "code-pre", text: prettyJsonOrText(rung.governed.context_payload) })
              ),
              el("div", { className: "neg-control-box" },
                el("h4", { className: "neg-control-title", text: "Negative Control Assertion" }),
                el("p", { className: "outcome-detail", text: rung.xray_summary.negative_control_assertion })
              )
            ),
            el("section", { className: "xray-drawer-section", attrs: { "aria-label": "Compiled Blind vs Governed SQL and ISO GQL" } },
              el("h3", { className: "progression-title", text: "2. Compiled Blind vs. Governed SQL / ISO GQL" }),
              el("div", { className: "code-diff-grid" },
                el("div", { className: "code-pane" },
                  el("div", { className: "code-pane-head" },
                    el("div", { className: "outcome-label-group" },
                      el("span", { className: "badge badge-tier-3", text: `Blind · ${rung.blind.query_language}` }),
                      el("span", { className: "badge badge-mono", text: `${formatNumber(rung.blind.tokens_used)} tok · ${rung.blind.error_retries} retries` })
                    ),
                    el("button", {
                      className: "btn",
                      text: state.copiedPane === "drawer_blind_sql" ? "Copied" : "Copy",
                      attrs: { type: "button" },
                      onClick: () => copyTextToClipboard("drawer_blind_sql", rung.blind.sql_or_gql)
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
                      text: state.copiedPane === "drawer_gov_sql" ? "Copied" : "Copy",
                      attrs: { type: "button" },
                      onClick: () => copyTextToClipboard("drawer_gov_sql", rung.governed.sql_or_gql)
                    })
                  ),
                  buildHighlightedCodeNodes(rung.governed.sql_or_gql)
                )
              )
            ),
            el("section", { className: "xray-drawer-section", attrs: { "aria-label": "Empirical N=5 Telemetry Summary" } },
              el("h3", { className: "progression-title", text: "3. Empirical N=5 Telemetry Summary" }),
              buildEmpiricalSummaryBlock(rung, "drawer")
            )
          )
        )
      );

      return backdrop;
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
          attrs: { type: "button", title: "Step 1: Business Question", disabled: isNonRung() ? true : null },
          onClick: () => setState({ beat: "question" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "blind" ? " is-active" : ""}`,
          text: "Blind",
          attrs: { type: "button", disabled: isNonRung() ? true : null },
          onClick: () => setState({ beat: "blind" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "governed" ? " is-active" : ""}`,
          text: "Governed",
          attrs: { type: "button", disabled: isNonRung() ? true : null },
          onClick: () => setState({ beat: "governed" })
        }),
        el("button", {
          className: `seg-btn${state.beat === "compare" ? " is-active" : ""}`,
          text: "Compare",
          attrs: { type: "button", disabled: isNonRung() ? true : null },
          onClick: () => setState({ beat: "compare" })
        })
      );

      const tokenRetryPill = el("div", {
        className: "token-retry-pill",
        attrs: { "aria-label": "Context tokens and retries delta" }
      },
        state.isOverview
          ? el("span", { text: `Briefing · ${bundle.rungs.length} Live Rungs` })
          : (state.isHorizon
              ? el("span", { text: "What's Next · Roadmap Scope" })
              : [
                  el("span", { text: `Tokens ${formatNumber(rung.blind.tokens_used)} → ` }),
                  el("span", { className: "delta-good", text: formatNumber(rung.governed.tokens_used) }),
                  el("span", { text: ` · Retries ${rung.blind.error_retries} → ` }),
                  el("span", { className: "delta-good", text: String(rung.governed.error_retries) })
                ])
      );

      const topbar = el("header", { className: "stage-topbar" },
        el("div", { className: "stage-topbar-row" },
          el("div", { className: "brand-block" },
            el("div", { className: "brand-title-row" },
              el("p", { className: "brand-title", text: bundle.title }),
              el("span", { className: "badge badge-mono", text: `${bundle.closed_period_label} · ${bundle.region}` }),
              buildRegionalHonestyBadge(),
              el("span", { className: "brand-tagline", text: bundle.hero_tagline })
            )
          ),
          el("div", { className: "stage-actions" },
            el("button", {
              className: `btn${state.helpOpen ? " btn-primary" : ""}`,
              attrs: {
                type: "button",
                id: "help-guide-btn",
                title: "Explain what is on screen (? or H)",
                "aria-expanded": state.helpOpen ? "true" : "false",
                "aria-controls": "help-guide-drawer"
              },
              onClick: () => toggleHelp()
            }, "? Guide"),
            el("button", {
              className: "btn btn-accent",
              attrs: {
                type: "button",
                disabled: state.isOverview ? true : null,
                title: state.isOverview
                  ? "Audience Poll activates once R1 starts"
                  : "Open CDO Myth-Busting Poll (Key P)"
              },
              onClick: () => togglePoll()
            }, "Poll ", el("span", { className: "kbd-hint", text: "P" })),
            modeGroup,
            themeGroup
          )
        ),
        el("div", { className: "stage-topbar-row stage-topbar-nav" },
          buildRungStepper(),
          el("div", { className: "stage-actions" },
            !state.isOverview ? beatToggle : null,
            !state.isOverview
              ? el("button", {
                  className: "btn",
                  attrs: { type: "button", title: "Cycle Beat Focus (Key B)", disabled: isNonRung() ? true : null },
                  onClick: () => cycleBeatB()
                }, "Focus ", el("span", { className: "kbd-hint", text: "B" }))
              : null,
            window.location.protocol !== "file:" && !isNonRung()
              ? el("button", {
                  className: "btn btn-primary",
                  text: state.liveLoading ? "Running..." : "▶ Verify Live BQ",
                  attrs: {
                    type: "button",
                    disabled: state.liveLoading ? true : null,
                    title: "Execute governed BigQuery / Property Graph / RLS query via /api/run-rung"
                  },
                  onClick: () => {
                    state.liveTargetMode = "governed";
                    handleRunLiveQuery();
                  }
                })
              : null,
            tokenRetryPill
          )
        )
      );

      let canvasChildren;
      if (state.isOverview) {
        canvasChildren = [buildOverviewShowcase()];
      } else if (state.isHorizon) {
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
                  el("p", { className: "outcome-kpi", text: rung.governed.answer_headline }),
                  el("p", { className: "outcome-detail", text: rung.governed.answer_detail }),
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

      const stageLiveBanner = state.liveResult
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
      const canvas = el("main", { className: "stage-canvas" }, stageLiveBanner, canvasChildren);

      // Bottom 10% Eval & Trust Bar
      const evalDots = el("span", { className: "eval-dots", attrs: { "aria-hidden": "true" } });
      if (!isNonRung()) {
        for (let i = 0; i < rung.governed.eval_total_runs; i += 1) {
          const pass = i < rung.governed.eval_pass_count;
          evalDots.appendChild(el("span", { className: `eval-dot ${pass ? "is-pass" : "is-fail"}` }));
        }
      }

      const empiricalBadgeText = isNonRung() ? null : formatEmpiricalHeadline(rung);
      const targetRateText = isNonRung()
        ? ""
        : `${empiricalBadgeText ? "Target: " : ""}${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs} → ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}`;

      let footerLeft;
      if (state.isOverview) {
        footerLeft = el("div", { className: "eval-trust-group" },
          el("span", { className: "badge badge-mono", text: `Briefing · ${bundle.rungs.length}-Rung Live Simulation` }),
          el("span", { className: "eval-label", text: `Region: ${bundle.region}` })
        );
      } else if (state.isHorizon) {
        footerLeft = el("div", { className: "eval-trust-group" },
          el("span", { className: "badge", text: `What's Next · ${bundle.horizon_cards.length} Architectural Cards` }),
          el("span", { className: "eval-label", text: `Live Scope: ${bundle.region}` })
        );
      } else {
        footerLeft = el("div", { className: "eval-trust-group" },
          el("div", { className: "eval-block" },
            el("span", { className: "eval-label", text: "Golden Eval Pass Rate" }),
            evalDots,
            el("span", {
              className: "badge badge-mono",
              text: targetRateText
            }),
            empiricalBadgeText
              ? el("span", {
                  className: "badge badge-empirical badge-mono",
                  attrs: { "data-empirical-badge": "true" },
                  text: empiricalBadgeText
                })
              : null
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
        );
      }

      const shortcutItems = state.isOverview
        ? [
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "Space/→" }), "Start R1"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "W" }), "Workbench"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "T" }), "Theme"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "?" }), "Guide")
          ]
        : [
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "Space/→" }), "Advance"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "P" }), "Poll"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "X" }), "X-Ray"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "B" }), "Focus"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "W" }), "Workbench"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "T" }), "Theme"),
            el("span", { className: "shortcut-item" }, el("span", { className: "kbd-hint", text: "?" }), "Guide")
          ];

      const prevDisabled = state.isOverview || (!hasOverview && !state.isHorizon && state.rungIndex === 0 && state.beat === "question");

      const footer = el("footer", { className: "stage-footer" },
        footerLeft,
        el("div", { className: "nav-controls-group" },
          el("div", { className: "shortcut-legend", attrs: { "aria-label": "Keyboard shortcuts" } }, ...shortcutItems),
          !isNonRung()
            ? el("button", {
                className: `btn ${state.stageXrayOpen ? "btn-primary" : "btn-accent"}`,
                attrs: {
                  type: "button",
                  id: "stage-xray-toggle-btn",
                  "aria-expanded": state.stageXrayOpen ? "true" : "false",
                  "aria-controls": "stage-xray-drawer",
                  title: "Open Slide-Up Stage X-Ray Drawer (Key X)"
                },
                onClick: () => toggleStageXray()
              }, el("span", { className: "kbd-hint", text: "X" }), " X-Ray")
            : null,
          el("button", {
            className: "btn",
            text: "← Prev",
            attrs: {
              type: "button",
              disabled: prevDisabled ? true : null
            },
            onClick: () => stepBackward()
          }),
          state.isOverview && bundle.overview
            ? el("button", {
                className: "btn btn-primary",
                text: bundle.overview.cta_label,
                attrs: { type: "button", id: "overview-start-btn" },
                onClick: () => stepForward()
              })
            : el("button", {
                className: "btn btn-primary",
                text: state.isHorizon ? "End · What's Next" : "Next →",
                attrs: { type: "button", disabled: state.isHorizon ? true : null },
                onClick: () => stepForward()
              })
        )
      );

      return el("div", { className: `stage-shell${state.isOverview ? " is-overview-mode" : ""}` }, topbar, canvas, footer);
    }

    /* ----------------------------------------------------------------------
       Workbench Mode Renderer (Progression Bar + Live Agent + 3-Tab X-Ray)
       ---------------------------------------------------------------------- */

    function buildProgressionBar() {
      let blindPassSum = 0;
      let govPassSum = 0;
      let totalRunsSum = 0;
      let blindRetrySum = 0;
      let govRetrySum = 0;
      let empBlindSum = 0;
      let empGovSum = 0;
      let empTotalSum = 0;

      for (const r of bundle.rungs) {
        blindPassSum += Number(r.blind.eval_pass_count || 0);
        govPassSum += Number(r.governed.eval_pass_count || 0);
        totalRunsSum += Number(r.governed.eval_total_runs || 0);
        blindRetrySum += Number(r.blind.error_retries || 0);
        govRetrySum += Number(r.governed.error_retries || 0);
        const { blindEmp, govEmp } = getEmpiricalPair(r);
        if (blindEmp) {
          empBlindSum += Number(blindEmp.pass_count || 0);
        }
        if (govEmp) {
          empGovSum += Number(govEmp.pass_count || 0);
          empTotalSum += Number(govEmp.runs || 0);
        }
      }

      const cardsWrap = el("div", { className: "progression-cards" });
      bundle.rungs.forEach((rung, idx) => {
        const isActive = !isNonRung() && state.rungIndex === idx;
        const pct = Math.round((rung.governed.eval_pass_count / Math.max(1, rung.governed.eval_total_runs)) * 100);
        const empLine = formatEmpiricalHeadline(rung);
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
              el("span", { text: `${empLine ? "Target " : "Eval "}${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs} → ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}` }),
              el("span", { text: `Retries ${rung.blind.error_retries} → ${rung.governed.error_retries}` })
            ),
            empLine
              ? el("div", { className: "prog-card-emp" },
                  el("span", { className: "badge badge-empirical badge-mono", text: empLine })
                )
              : null
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
              text: `Target Blind: ${blindPassSum}/${totalRunsSum}`
            }),
            el("span", {
              className: "badge badge-ga badge-mono",
              text: `Target Governed: ${govPassSum}/${totalRunsSum}`
            }),
            empTotalSum > 0
              ? el("span", {
                  className: "badge badge-empirical badge-mono",
                  text: `Empirical Cumulative: ${empBlindSum}/${empTotalSum} → ${empGovSum}/${empTotalSum}`
                })
              : null,
            el("span", {
              className: "badge badge-mono",
              text: `Error Retries: ${blindRetrySum} → ${govRetrySum}`
            })
          )
        ),
        cardsWrap
      );
    }

    function buildRowsPreviewTable(rowsPreview) {
      if (!Array.isArray(rowsPreview) || rowsPreview.length === 0) {
        return null;
      }
      const firstRow = rowsPreview[0];
      if (!firstRow || typeof firstRow !== "object" || Array.isArray(firstRow)) {
        return el("div", { className: "code-pane" },
          el("div", { className: "code-pane-head" },
            el("span", { className: "badge badge-mono", text: `Rows Preview (${rowsPreview.length})` })
          ),
          el("pre", { className: "code-pre", text: JSON.stringify(rowsPreview, null, 2) })
        );
      }

      const columns = Object.keys(firstRow);
      return el("div", { className: "rls-table-wrap" },
        el("table", { className: "rls-table rows-preview-table" },
          el("thead", null,
            el("tr", null, ...columns.map((col) => el("th", { text: col })))
          ),
          el("tbody", null,
            ...rowsPreview.map((row) =>
              el("tr", null,
                ...columns.map((col) => {
                  const val = row[col];
                  const rendered = val === null || val === undefined
                    ? "null"
                    : (typeof val === "object" ? JSON.stringify(val) : String(val));
                  return el("td", { className: "badge-mono", text: rendered });
                })
              )
            )
          )
        )
      );
    }

    function buildAgentArmCard(armKey, result, rungId) {
      if (!result || typeof result !== "object") {
        return null;
      }
      const isBlind = armKey === "blind";
      const passBadge = el("span", {
        className: result.passed_grading ? "badge badge-ga badge-mono" : "badge badge-tier-3 badge-mono",
        text: result.passed_grading ? "PASS · Grading Verified" : "FAIL · Grading Mismatch"
      });
      const copyKey = `agent_${rungId}_${armKey}`;
      const latencyText = typeof result.latency_ms === "number" ? `${Math.round(result.latency_ms)} ms` : "—";
      const numericText = typeof result.numeric_value === "number"
        ? formatNumber(result.numeric_value)
        : null;

      return el("article", {
        className: `agent-result-card ${isBlind ? "is-blind" : "is-governed"}`,
        attrs: { "data-agent-arm": armKey }
      },
        el("div", { className: "outcome-card-head" },
          el("div", { className: "outcome-label-group" },
            el("span", {
              className: "outcome-role-title",
              text: isBlind ? "Blind Agent (Raw Schema Only)" : "Governed Agent (Knowledge Catalog + Verified Context)"
            }),
            result.query_language
              ? el("span", { className: "badge badge-mono", text: result.query_language })
              : null
          ),
          el("div", { className: "outcome-label-group" },
            passBadge,
            result.trust_tier
              ? el("span", { className: trustBadgeClass(result.trust_tier), text: result.trust_tier })
              : null
          )
        ),
        el("div", { className: "agent-answer-block" },
          el("p", { className: "outcome-kpi", text: result.answer_summary || "No answer summary returned." }),
          numericText !== null
            ? el("span", { className: "badge badge-mono", text: `Numeric Output: ${numericText}` })
            : null
        ),
        result.grading_reason
          ? el("p", { className: "outcome-detail", text: `Grading: ${result.grading_reason}` })
          : null,
        el("div", { className: "outcome-metrics-strip" },
          el("div", { className: "metric-chip" },
            el("span", { className: "metric-chip-label", text: "Latency" }),
            el("span", { className: "metric-chip-value", text: latencyText })
          ),
          el("div", { className: "metric-chip" },
            el("span", { className: "metric-chip-label", text: "Tokens" }),
            el("span", { className: "metric-chip-value", text: formatNumber(result.tokens_used) })
          ),
          el("div", { className: "metric-chip" },
            el("span", { className: "metric-chip-label", text: "Queries" }),
            el("span", { className: "metric-chip-value", text: String(result.exploratory_queries ?? 0) })
          ),
          el("div", { className: "metric-chip" },
            el("span", { className: "metric-chip-label", text: "Retries" }),
            el("span", { className: "metric-chip-value", text: String(result.error_retries ?? 0) })
          )
        ),
        result.catalog_context_summary
          ? el("div", { className: "context-callout" },
              el("span", { className: "context-callout-label", text: "Catalog & Context Summary:" }),
              el("span", { text: result.catalog_context_summary })
            )
          : null,
        Array.isArray(result.trust_reasons) && result.trust_reasons.length > 0
          ? el("ul", { className: "trust-reasons-list" },
              ...result.trust_reasons.map((reason) => el("li", { text: reason }))
            )
          : null,
        Array.isArray(result.observed_signals) && result.observed_signals.length > 0
          ? el("div", { className: "signal-chips" },
              ...result.observed_signals.map((sig) =>
                el("span", { className: "badge badge-mono", text: sig })
              )
            )
          : null,
        Array.isArray(result.tool_trace) && result.tool_trace.length > 0
          ? el("div", { className: "rls-table-wrap" },
              el("table", { className: "rls-table tool-trace-table" },
                el("thead", null,
                  el("tr", null,
                    el("th", { text: "Turn" }),
                    el("th", { text: "Tool" }),
                    el("th", { text: "Args Summary" }),
                    el("th", { text: "Status" }),
                    el("th", { text: "Output Preview" })
                  )
                ),
                el("tbody", null,
                  ...result.tool_trace.map((step) =>
                    el("tr", null,
                      el("td", { className: "badge-mono", text: String(step.turn ?? "") }),
                      el("td", { className: "badge-mono", text: String(step.tool_name || "") }),
                      el("td", { className: "badge-mono", text: String(step.args_summary || "") }),
                      el("td", { className: "badge-mono", text: String(step.status || "") }),
                      el("td", { text: String(step.output_preview || "") })
                    )
                  )
                )
              )
            )
          : null,
        result.sql_or_gql
          ? el("div", { className: "code-pane" },
              el("div", { className: "code-pane-head" },
                el("span", { className: "badge badge-mono", text: `Generated ${result.query_language || "SQL"}` }),
                el("button", {
                  className: "btn",
                  text: state.copiedPane === copyKey ? "Copied" : "Copy",
                  attrs: { type: "button" },
                  onClick: () => copyTextToClipboard(copyKey, result.sql_or_gql)
                })
              ),
              buildHighlightedCodeNodes(result.sql_or_gql)
            )
          : null,
        buildRowsPreviewTable(result.rows_preview)
      );
    }

    function buildEmpiricalVsBaselineTable(rung, liveResponse) {
      const arms = [
        { key: "blind", label: "Blind", outcome: rung.blind },
        { key: "governed", label: "Governed", outcome: rung.governed }
      ];
      const liveArms = liveResponse && liveResponse.arms ? liveResponse.arms : {};

      return el("div", { className: "empirical-table-wrap" },
        el("h3", { className: "progression-title", text: "Empirical N=5 vs. Authored Baseline Telemetry" }),
        el("div", { className: "rls-table-wrap" },
          el("table", { className: "rls-table" },
            el("thead", null,
              el("tr", null,
                el("th", { text: "Arm" }),
                el("th", { text: "Authored Baseline (Step 0)" }),
                el("th", { text: "Empirical N=5 (Live Eval)" }),
                el("th", { text: "Observed Signals" }),
                el("th", { text: "Latest Live Agent Run" })
              )
            ),
            el("tbody", null,
              ...arms.map(({ key, label, outcome }) => {
                const emp = outcome.empirical_eval;
                const live = liveArms[key];
                return el("tr", null,
                  el("td", null,
                    el("span", {
                      className: key === "blind" ? "badge badge-tier-3" : "badge badge-ga",
                      text: label
                    })
                  ),
                  el("td", {
                    className: "badge-mono",
                    text: `Target ${outcome.eval_pass_count}/${outcome.eval_total_runs} · ${formatNumber(outcome.tokens_used)} tok · ${outcome.exploratory_queries} q · ${outcome.error_retries} retries`
                  }),
                  el("td", {
                    className: "badge-mono",
                    text: emp
                      ? `Empirical N=${emp.runs}: ${emp.pass_count}/${emp.runs} · ${formatNumber(emp.median_tokens)} tok · ${emp.median_exploratory_queries} q · ${emp.median_error_retries} retries · ${Math.round(emp.median_latency_ms)} ms (${emp.model_id} @ ${emp.model_location})`
                      : "Pending live eval_harness.py run"
                  }),
                  el("td", null,
                    emp && Array.isArray(emp.observed_signals) && emp.observed_signals.length > 0
                      ? el("div", { className: "signal-chips" },
                          ...emp.observed_signals.map((sig) =>
                            el("span", { className: "badge badge-mono", text: sig })
                          )
                        )
                      : el("span", { className: "eval-label", text: "—" })
                  ),
                  el("td", {
                    className: "badge-mono",
                    text: live
                      ? `${live.passed_grading ? "PASS" : "FAIL"} · ${formatNumber(live.tokens_used)} tok · ${Math.round(live.latency_ms)} ms · ${live.trust_tier}`
                      : "Not run in session"
                  })
                );
              })
            )
          )
        )
      );
    }

    function buildDemoKeyInlineBar() {
      if (!state.authDialogOpen) {
        return null;
      }
      const hasSaved = Boolean(getSavedDemoKey());
      const keyInput = el("input", {
        className: "demo-key-input",
        attrs: {
          id: "demo-key-input",
          name: "demo_key",
          type: state.authKeyVisible ? "text" : "password",
          autocomplete: "off",
          spellcheck: "false",
          placeholder: "Paste demo share key...",
          "aria-describedby": "demo-key-help",
          required: "required"
        }
      });
      keyInput.value = state.authInputDraft || "";
      keyInput.addEventListener("input", (e) => {
        state.authInputDraft = e.target.value;
      });

      const form = el("form", {
        className: "demo-key-bar",
        attrs: {
          id: "demo-key-form",
          role: "region",
          "aria-labelledby": "demo-key-label"
        }
      },
        el("div", { className: "demo-key-head" },
          el("label", {
            className: "demo-key-label",
            attrs: { for: "demo-key-input", id: "demo-key-label" },
            text: "Demo Share Key (X-Demo-Key)"
          }),
          el("span", {
            className: "demo-key-help",
            attrs: { id: "demo-key-help" },
            text: "Stored only in sessionStorage for this browser tab and never written to the visible URL."
          })
        ),
        state.authDialogError
          ? el("p", {
              className: "demo-key-error",
              attrs: { role: "alert" },
              text: state.authDialogError
            })
          : null,
        el("div", { className: "demo-key-input-row" },
          keyInput,
          el("button", {
            className: "btn",
            text: state.authKeyVisible ? "Hide" : "Show",
            attrs: {
              type: "button",
              "aria-pressed": state.authKeyVisible ? "true" : "false",
              "aria-label": state.authKeyVisible ? "Hide demo share key" : "Show demo share key"
            },
            onClick: () => setState({ authKeyVisible: !state.authKeyVisible })
          }),
          el("button", {
            className: "btn btn-primary",
            text: state.pendingAgentAction
              ? "Save Key & Run Agent"
              : (state.pendingPollReset ? "Save Key & Clear Votes" : "Save Key"),
            attrs: { type: "submit" }
          }),
          hasSaved
            ? el("button", {
                className: "btn",
                text: "Clear Saved Key",
                attrs: { type: "button" },
                onClick: () => {
                  saveDemoKey("");
                  setState({
                    authDialogOpen: false,
                    authDialogError: null,
                    authKeyVisible: false,
                    authInputDraft: "",
                    pendingAgentAction: false,
                    pendingPollReset: false
                  });
                }
              })
            : null,
          el("button", {
            className: "btn",
            text: "Cancel",
            attrs: { type: "button" },
            onClick: () => setState({
              authDialogOpen: false,
              authDialogError: null,
              authKeyVisible: false,
              authInputDraft: "",
              pendingAgentAction: false,
              pendingPollReset: false
            })
          })
        )
      );

      form.addEventListener("submit", (e) => {
        e.preventDefault();
        const val = String(keyInput.value || "").trim();
        if (!val) {
          setState({ authDialogError: "Please paste a non-empty Demo Share Key." });
          return;
        }
        saveDemoKey(val);
        const shouldRetryAgent = state.pendingAgentAction;
        const shouldRetryPollReset = state.pendingPollReset;
        setState({
          authDialogOpen: false,
          authDialogError: null,
          authKeyVisible: false,
          authInputDraft: "",
          pendingAgentAction: false,
          pendingPollReset: false
        });
        if (shouldRetryAgent) {
          handleRunLiveAgent();
        } else if (shouldRetryPollReset) {
          syncStageIfAuthorized();
          handleClearRoomVotes();
        } else if (state.pollOpen) {
          syncStageIfAuthorized();
        }
      });

      return form;
    }

    function buildLiveAgentPanel(rung, personaId) {
      const isFileProtocol = window.location.protocol === "file:";
      const disabledByServer = Boolean(state.health && state.health.live_agent_enabled === false);
      const isDisabled = isFileProtocol || disabledByServer || state.agentLoading || isNonRung();
      const savedKey = getSavedDemoKey();
      const modelId = (state.agentResult && state.agentResult.data && state.agentResult.data.model_id)
        || (state.health && state.health.agent_model_id)
        || null;
      const modelLoc = (state.agentResult && state.agentResult.data && state.agentResult.data.model_location)
        || (state.health && state.health.agent_model_location)
        || "global";

      const armSelector = el("div", {
        className: "segmented-group",
        attrs: { role: "group", "aria-label": "Live agent arm selector" }
      },
        el("button", {
          className: `seg-btn${state.agentArm === "both" ? " is-active" : ""}`,
          text: "Compare Both",
          attrs: { type: "button", "aria-pressed": state.agentArm === "both" ? "true" : "false" },
          onClick: () => setState({ agentArm: "both" })
        }),
        el("button", {
          className: `seg-btn${state.agentArm === "blind" ? " is-active" : ""}`,
          text: "Blind Only",
          attrs: { type: "button", "aria-pressed": state.agentArm === "blind" ? "true" : "false" },
          onClick: () => setState({ agentArm: "blind" })
        }),
        el("button", {
          className: `seg-btn${state.agentArm === "governed" ? " is-active" : ""}`,
          text: "Governed Only",
          attrs: { type: "button", "aria-pressed": state.agentArm === "governed" ? "true" : "false" },
          onClick: () => setState({ agentArm: "governed" })
        })
      );

      let disabledNote = null;
      if (isFileProtocol) {
        disabledNote = "Disabled in offline file:// preview. Serve via uvicorn server.app:app over http:// or Cloud Run to invoke live Gemini agents.";
      } else if (disabledByServer) {
        disabledNote = "Disabled by server kill-switch (ENABLE_LIVE_AGENT=false).";
      }

      const matchingResult = state.agentResult && state.agentResult.contextKey === activeContextKey()
        ? state.agentResult.data
        : null;

      const armCards = [];
      if (matchingResult && matchingResult.arms) {
        if (matchingResult.arms.blind) {
          armCards.push(buildAgentArmCard("blind", matchingResult.arms.blind, rung.id));
        }
        if (matchingResult.arms.governed) {
          armCards.push(buildAgentArmCard("governed", matchingResult.arms.governed, rung.id));
        }
      }

      return el("section", {
        className: "live-agent-panel",
        attrs: { "aria-label": "Run Live Agent Blind vs Governed" }
      },
        el("div", { className: "live-agent-header" },
          el("div", { className: "outcome-label-group" },
            el("h2", { className: "live-agent-title", text: "🤖 Run Live Agent (Blind vs. Governed)" }),
            buildRegionalHonestyBadge(),
            modelId
              ? el("span", { className: "badge badge-mono", text: `Model: ${modelId} (${modelLoc})` })
              : null,
            personaId
              ? el("span", { className: "badge badge-mono", text: `Persona: ${personaId}` })
              : null
          ),
          el("div", { className: "live-agent-controls" },
            armSelector,
            !isFileProtocol
              ? el("button", {
                  className: "btn",
                  text: savedKey ? "Demo Key: Saved" : "Set Demo Key",
                  attrs: {
                    type: "button",
                    "aria-expanded": state.authDialogOpen ? "true" : "false",
                    "aria-controls": "demo-key-form"
                  },
                  onClick: () => {
                    if (state.authDialogOpen) {
                      setState({ authDialogOpen: false, authDialogError: null, pendingAgentAction: false });
                    } else {
                      openAuthPrompt(null, false);
                    }
                  }
                })
              : null,
            el("button", {
              className: "btn btn-primary",
              text: state.agentLoading ? "Running Live Agent..." : "🤖 Run Live Agent",
              attrs: {
                type: "button",
                id: "run-live-agent-btn",
                disabled: isDisabled ? true : null,
                title: disabledNote || "Execute zero-trust Blind vs Governed live agent loop via POST /api/run-agent"
              },
              onClick: () => handleRunLiveAgent()
            })
          )
        ),
        disabledNote
          ? el("p", { className: "outcome-detail", text: disabledNote })
          : null,
        !state.pollOpen ? buildDemoKeyInlineBar() : null,
        state.agentLoading
          ? el("div", { className: "live-result-banner is-info", attrs: { role: "status", "aria-live": "polite" } },
              el("span", { text: `Running zero-trust ${state.agentArm} agent loop on ${rung.short_label}${personaId ? " (" + personaId + ")" : ""} via POST /api/run-agent...` })
            )
          : null,
        state.agentError
          ? el("div", { className: "live-result-banner is-error", attrs: { role: "alert" } },
              el("span", { text: state.agentError }),
              el("button", {
                className: "btn",
                text: "Dismiss",
                attrs: { type: "button" },
                onClick: () => setState({ agentError: null })
              })
            )
          : null,
        armCards.length > 0
          ? el("div", { className: `agent-cards-grid${armCards.length === 1 ? " is-single" : ""}` }, armCards)
          : null,
        buildEmpiricalVsBaselineTable(rung, matchingResult)
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
        const { blindEmp, govEmp } = getEmpiricalPair(rung);
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
        if ((blindEmp && blindEmp.sample_sql_or_gql) || (govEmp && govEmp.sample_sql_or_gql)) {
          bodyChildren.push(
            el("div", { className: "code-diff-grid" },
              blindEmp && blindEmp.sample_sql_or_gql
                ? el("div", { className: "code-pane" },
                    el("div", { className: "code-pane-head" },
                      el("span", { className: "badge badge-empirical badge-mono", text: `Empirical N=${blindEmp.runs} Blind Median SQL` }),
                      el("button", {
                        className: "btn",
                        text: state.copiedPane === "emp_blind_sql" ? "Copied" : "Copy",
                        attrs: { type: "button" },
                        onClick: () => copyTextToClipboard("emp_blind_sql", blindEmp.sample_sql_or_gql)
                      })
                    ),
                    buildHighlightedCodeNodes(blindEmp.sample_sql_or_gql)
                  )
                : el("div", null),
              govEmp && govEmp.sample_sql_or_gql
                ? el("div", { className: "code-pane" },
                    el("div", { className: "code-pane-head" },
                      el("span", { className: "badge badge-empirical badge-mono", text: `Empirical N=${govEmp.runs} Governed Median SQL` }),
                      el("button", {
                        className: "btn",
                        text: state.copiedPane === "emp_gov_sql" ? "Copied" : "Copy",
                        attrs: { type: "button" },
                        onClick: () => copyTextToClipboard("emp_gov_sql", govEmp.sample_sql_or_gql)
                      })
                    ),
                    buildHighlightedCodeNodes(govEmp.sample_sql_or_gql)
                  )
                : el("div", null)
            )
          );
        }
      } else {
        bodyChildren.push(
          el("div", { className: "release-badges-row" }, buildRegionalHonestyBadge()),
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
            className: `btn${state.helpOpen ? " btn-primary" : ""}`,
            attrs: {
              type: "button",
              id: "help-guide-btn",
              title: "Explain what is on screen (? or H)",
              "aria-expanded": state.helpOpen ? "true" : "false",
              "aria-controls": "help-guide-drawer"
            },
            onClick: () => toggleHelp()
          }, "? Guide"),
          el("button", {
            className: "btn btn-accent",
            attrs: { type: "button", title: "Open Poll Modal (Key P)" },
            onClick: () => togglePoll()
          }, "Poll ", el("span", { className: "kbd-hint", text: "P" })),
          modeGroup,
          themeGroup
        )
      );

      const isLiveVerified = bundle.generated_mode === "live_gcp_verified" || bundle.generated_mode === "live_agent_verified";
      const execBadgeText = isLiveVerified
        ? `${formatGeneratedMode(bundle.generated_mode)} (${bundle.region})`
        : `[Recorded Verified Run] · ${formatGeneratedMode(bundle.generated_mode)}`;

      const statusBar = el("div", { className: "workbench-status-bar" },
        el("div", { className: "outcome-label-group" },
          el("span", {
            className: isLiveVerified ? "badge badge-ga" : "badge badge-ref",
            text: execBadgeText
          }),
          buildRegionalHonestyBadge(),
          el("span", { className: "badge badge-mono", text: `Period: ${bundle.closed_period_label}` }),
          personaId ? el("span", { className: "badge badge-mono", text: `Persona: ${personaId}` }) : null
        ),
        el("div", { className: "live-runner-controls" },
          el("button", {
            className: "btn btn-primary",
            text: state.liveLoading ? "Running..." : "▶ Run Live Query",
            attrs: {
              type: "button",
              disabled: state.liveLoading || isNonRung() ? true : null,
              title: window.location.protocol === "file:"
                ? "Offline file:// mode: displaying recorded verified run. Serve via uvicorn server.app:app to run live queries."
                : "Execute governed allowlisted pack query via POST /api/run-rung"
            },
            onClick: () => {
              state.liveTargetMode = "governed";
              handleRunLiveQuery();
            }
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
        const blindEmp = rung.blind.empirical_eval;
        const govEmp = rung.governed.empirical_eval;
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
                  el("div", { className: "outcome-label-group" },
                    el("span", {
                      className: "badge badge-mono",
                      text: `Target: ${rung.blind.eval_pass_count}/${rung.blind.eval_total_runs}`
                    }),
                    blindEmp
                      ? el("span", {
                          className: "badge badge-empirical badge-mono",
                          text: `Empirical N=${blindEmp.runs}: ${blindEmp.pass_count}/${blindEmp.runs}`
                        })
                      : null,
                    el("span", { className: trustBadgeClass(rung.blind.trust_tier), text: rung.blind.trust_tier })
                  )
                ),
                el("p", { className: "outcome-kpi", text: rung.blind.answer_headline }),
                el("p", { className: "outcome-detail", text: rung.blind.answer_detail })
              ),
              el("div", { className: "mini-outcome is-governed" },
                el("div", { className: "outcome-card-head" },
                  el("span", { className: "outcome-role-title", text: "Governed Context Outcome" }),
                  el("div", { className: "outcome-label-group" },
                    el("span", {
                      className: "badge badge-mono",
                      text: `Target: ${rung.governed.eval_pass_count}/${rung.governed.eval_total_runs}`
                    }),
                    govEmp
                      ? el("span", {
                          className: "badge badge-empirical badge-mono",
                          text: `Empirical N=${govEmp.runs}: ${govEmp.pass_count}/${govEmp.runs}`
                        })
                      : null,
                    el("span", { className: trustBadgeClass(rung.governed.trust_tier), text: rung.governed.trust_tier })
                  )
                ),
                el("p", { className: "outcome-kpi", text: rung.governed.answer_headline }),
                el("p", { className: "outcome-detail", text: rung.governed.answer_detail }),
                buildIdentitySwitchPanel(rung)
              )
            )
          ),
          buildLiveAgentPanel(rung, personaId),
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
      const isFileProtocol = window.location.protocol === "file:";
      const totalVotes = Number(state.pollLiveTotal || 0);
      const externalPollUrl =
        poll.external_poll_url && String(poll.external_poll_url).startsWith("https://")
          ? String(poll.external_poll_url)
          : null;

      const closePoll = () => {
        stopPollTimer();
        cancelPollResetConfirm();
        setState({
          pollOpen: false,
          authDialogOpen: false,
          authDialogError: null,
          pendingPollReset: false
        });
      };

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
          const optCount = Number((state.pollLiveCounts && state.pollLiveCounts[opt.key]) || 0);
          const pct = totalVotes > 0 ? Math.round((optCount / totalVotes) * 100) : 0;

          return el("button", {
            className: cls,
            attrs: {
              type: "button",
              "aria-pressed": isSelected ? "true" : "false",
              "data-poll-key": opt.key
            },
            onClick: () => setState({ pollSelectedKey: opt.key })
          },
            el("span", {
              className: "poll-option-bar",
              attrs: { style: `width: ${pct}%`, "aria-hidden": "true" }
            }),
            el("span", { className: "poll-option-row" },
              el("span", { className: "poll-key-pill", text: opt.key }),
              el("span", { className: "poll-option-text", text: opt.text }),
              el("span", {
                className: "poll-option-stat badge badge-mono",
                text: totalVotes > 0 ? `${optCount} · ${pct}%` : "",
                attrs: { hidden: totalVotes > 0 ? null : "hidden" }
              })
            )
          );
        })
      );

      const votePath = `/vote?pack=${encodeURIComponent(bundle.pack_id)}&rung=${encodeURIComponent(rung.id)}`;
      const qrSrc = `/api/poll/qr.svg?pack_id=${encodeURIComponent(bundle.pack_id)}&rung_id=${encodeURIComponent(rung.id)}`;

      const qrAside = isFileProtocol
        ? el("aside", { className: "poll-qr-aside", attrs: { "aria-label": "Offline poll mode" } },
            el("p", {
              className: "poll-offline-note",
              text: "Offline file:// Mode — Use Show-of-Hands Vote (QR activates automatically on Cloud Run)"
            }),
            externalPollUrl
              ? el("a", {
                  className: "btn",
                  text: "External Poll ↗",
                  attrs: { href: externalPollUrl, target: "_blank", rel: "noopener" }
                })
              : null
          )
        : el("aside", { className: "poll-qr-aside", attrs: { "aria-label": "Audience QR voting link" } },
            el("div", { className: "poll-qr-card" },
              el("img", {
                className: "poll-qr-img",
                attrs: {
                  src: qrSrc,
                  alt: "Scan QR code to vote on your phone",
                  width: "185",
                  height: "185"
                }
              })
            ),
            el("span", { className: "poll-qr-label", text: "Scan to Vote Live" }),
            el("a", {
              className: "poll-qr-link badge-mono",
              text: votePath,
              attrs: { href: votePath, target: "_blank", rel: "noopener" }
            }),
            el("span", {
              className: "badge badge-mono poll-live-count-badge",
              attrs: { id: "poll-live-count-badge" },
              text: `${totalVotes} room votes`
            }),
            externalPollUrl
              ? el("a", {
                  className: "btn",
                  text: "External Poll ↗",
                  attrs: { href: externalPollUrl, target: "_blank", rel: "noopener" }
                })
              : null
          );

      const mainCol = el("div", { className: "poll-main-col" },
        optionsList,
        state.pollRevealed
          ? el("div", { className: "poll-takeaway", attrs: { role: "status" } },
              el("strong", { text: `Answer ${poll.correct_key}: ` }),
              el("span", { text: poll.reveal_takeaway })
            )
          : null,
        state.authDialogOpen ? buildDemoKeyInlineBar() : null,
        state.pollStatusMsg
          ? el("div", { className: "live-result-banner is-info", attrs: { role: "status", "aria-live": "polite" } },
              el("span", { text: state.pollStatusMsg })
            )
          : null
      );

      const backdrop = el("div", {
        className: "modal-backdrop",
        attrs: { role: "presentation" },
        onClick: (e) => {
          if (e.target === backdrop) {
            closePoll();
          }
        }
      },
        el("div", {
          className: "modal-dialog has-live-qr",
          attrs: {
            role: "dialog",
            "aria-modal": "true",
            "aria-labelledby": "poll-modal-title",
            "data-poll-modal-rung": rung.id
          }
        },
          el("div", { className: "modal-head" },
            el("div", null,
              el("span", { className: "badge badge-mono", text: `CDO Myth-Busting Poll · ${rung.short_label}` }),
              el("h2", { className: "modal-title", attrs: { id: "poll-modal-title" }, text: poll.prompt })
            ),
            el("button", {
              className: "btn",
              text: "Close [Esc]",
              attrs: { type: "button", "aria-label": "Close poll dialog" },
              onClick: () => closePoll()
            })
          ),
          el("div", { className: "poll-layout-grid" }, qrAside, mainCol),
          el("div", { className: "modal-foot" },
            el("span", { className: "eval-label", text: "Select A / B / C / D then reveal answer" }),
            el("div", { className: "stage-actions" },
              el("button", {
                className: "btn",
                text: "Reset",
                attrs: { type: "button" },
                onClick: () => setState({ pollSelectedKey: null, pollRevealed: false })
              }),
              !isFileProtocol
                ? el("button", {
                    className: `btn${state.pollResetConfirmPending ? " btn-danger" : ""}`,
                    text: state.pollResetBusy
                      ? "Clearing..."
                      : (state.pollResetConfirmPending ? "Confirm Clear?" : "Clear Room Votes"),
                    attrs: {
                      type: "button",
                      disabled: state.pollResetBusy ? true : null
                    },
                    onClick: () => {
                      if (!state.pollResetConfirmPending) {
                        cancelPollResetConfirm();
                        setState({ pollResetConfirmPending: true });
                        pollResetConfirmTimerId = window.setTimeout(() => {
                          pollResetConfirmTimerId = null;
                          if (state.pollResetConfirmPending) {
                            setState({ pollResetConfirmPending: false });
                          }
                        }, 4000);
                        return;
                      }
                      cancelPollResetConfirm();
                      handleClearRoomVotes();
                    }
                  })
                : null,
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
       Plain-English Help Drawer (? Guide)
       ---------------------------------------------------------------------- */

    function deriveLayerRungs(layerDigit, includeIdentityNote) {
      const matches = [];
      for (const r of bundle.rungs) {
        const tag = extractLayerTag(r.pyramid_layer);
        const hasRange12 = layerDigit === "1" || layerDigit === "2" ? /1[–-]2/.test(tag) : false;
        const hasDigit = new RegExp(`\\b${layerDigit}\\b`).test(tag);
        if (hasRange12 || hasDigit) {
          let label = `R${r.rung_num}`;
          if (includeIdentityNote && r.identity_variants && Object.keys(r.identity_variants).length > 0) {
            label += " · Beat 4b";
          }
          matches.push(label);
        }
      }
      return matches.length > 0 ? matches.join(", ") : "—";
    }

    function buildHelpDrawer() {
      if (!state.helpOpen) {
        return null;
      }

      const closeHelp = () => setState({ helpOpen: false });
      const dataRegion = (state.health && state.health.bq_location) || bundle.region || "asia-southeast1";

      const pyramidRows = [
        {
          layer: "Layer 1 · Technical Metadata",
          rungs: deriveLayerRungs("1", false),
          desc: "Table schemas, PK/FK constraints, certified Data Products, and automated data quality freshness."
        },
        {
          layer: "Layer 2 · Intent-Driven Enrichment",
          rungs: deriveLayerRungs("2", false),
          desc: "Automated schema insights and runtime context retrieval (BigQuery Data Insights & Knowledge Catalog lookupContext (Preview))."
        },
        {
          layer: "Layer 3 · Institutional Knowledge",
          rungs: deriveLayerRungs("3", false),
          desc: "Policies, contracts, and amendments living in unstructured documents outside SQL tables."
        },
        {
          layer: "Layer 4 · Semantic Knowledge",
          rungs: deriveLayerRungs("4", false),
          desc: "Shared business glossaries, grain-locked metrics (MEASURE()), and multi-hop relationship graphs (ISO GQL)."
        },
        {
          layer: "Layer 5 · Personalization & Access Governance",
          rungs: deriveLayerRungs("5", true),
          desc: "Identity-scoped Row-Level Security and access boundaries so answers adapt to who is asking."
        }
      ];

      const glossaryItems = [
        {
          term: "Target Eval (k/N)",
          desc: "Expected consistency across 5 repeated runs of the same business question."
        },
        {
          term: "Empirical N=5",
          desc: "Actual measured pass rate from running the live Gemini agent 5 separate times per arm (proving results aren't a lucky one-off)."
        },
        {
          term: "Trust Tier (TIER_3 → TIER_2 → TIER_1)",
          desc: "Automated safety grade from Review Required (unverified SQL / math drift) to Grounded (schema/glossary) up to Verified / Compiled (certified metrics, graphs, RLS, or contracts)."
        },
        {
          term: "Tokens",
          desc: "Total prompt, schema lookup, and response text processed by the AI—lower wasted exploration means faster, cheaper answers."
        },
        {
          term: "Exploratory Queries & Retries",
          desc: "How many trial-and-error SQL queries the agent ran (and fixed after errors) while guessing what tables/columns mean; governed context reduces retries."
        },
        {
          term: "Verify Live BQ (▶)",
          desc: `Runs the active rung's real SQL or ISO GQL directly against BigQuery (${dataRegion}), including live Row-Level Security identity switching when available.`
        },
        {
          term: "Stage X-Ray ([X]) & Live QR Poll ([P])",
          desc: "Behind-the-scenes Knowledge Catalog payload / SQL drawer (X) and audience mobile QR voting modal (P → /vote)."
        }
      ];

      const shortcutRows = [
        ["Space / →", "Advance from Overview to R1, step through beats, or advance rungs"],
        ["←", "Step back to the previous beat, rung, or Overview"],
        ["P", "Open / close the CDO Myth-Busting QR Poll modal (active on R1–R6)"],
        ["X", "Open / close the Slide-Up Stage X-Ray drawer (Stage R1–R6)"],
        ["B", "Cycle card focus between Compare, Blind, and Governed"],
        ["W", "Switch between Stage presentation mode and Engineering Workbench"],
        ["T", "Toggle Paper (light) and Dark Stage themes"],
        ["? / H", "Open or close this plain-English Guide drawer (Esc closes)"]
      ];

      const backdrop = el("div", {
        className: "help-drawer-backdrop",
        attrs: { role: "presentation" },
        onClick: (e) => {
          if (e.target === backdrop) {
            closeHelp();
          }
        }
      },
        el("aside", {
          className: "help-drawer",
          attrs: {
            id: "help-guide-drawer",
            role: "dialog",
            "aria-modal": "true",
            "aria-labelledby": "help-drawer-title"
          }
        },
          el("header", { className: "help-drawer-head" },
            el("div", { className: "help-drawer-title-block" },
              el("span", { className: "badge badge-mono", text: "Plain-English Field Guide" }),
              el("h2", {
                className: "help-drawer-title",
                attrs: { id: "help-drawer-title" },
                text: "How to Read This Screen"
              })
            ),
            el("button", {
              className: "btn btn-primary",
              text: "Close [Esc]",
              attrs: {
                type: "button",
                id: "help-drawer-close",
                "aria-label": "Close Guide drawer"
              },
              onClick: () => closeHelp()
            })
          ),
          el("div", { className: "help-drawer-body" },
            el("section", { className: "help-section", attrs: { "aria-label": "How This Screen Works" } },
              el("h3", { className: "help-section-title", text: "1. How This Screen Works" }),
              el("div", { className: "help-callout-grid" },
                el("div", { className: "help-callout is-blind" },
                  el("strong", { className: "help-callout-head", text: "Blind Agent Trap" }),
                  el("p", {
                    className: "help-copy",
                    text: "Same AI model, raw schemas only—it guesses cryptic columns, hits join fan-traps, and misses amendments, producing confident-sounding mistakes."
                  })
                ),
                el("div", { className: "help-callout is-governed" },
                  el("strong", { className: "help-callout-head", text: "Governed Enterprise Context" }),
                  el("p", {
                    className: "help-copy",
                    text: "The exact same AI model paired with live Knowledge Catalog, Property Graph, Row-Level Security, and extracted contracts produces verified answers."
                  })
                )
              ),
              el("p", {
                className: "help-copy",
                text: "Use Stage Mode for clean executive storytelling (Overview → R1–R6 → What's Next), or switch to Workbench [W] for the 3-tab X-Ray inspector, SQL diffs, and live Gemini agent execution."
              })
            ),
            el("section", { className: "help-section", attrs: { "aria-label": "The 5-Layer Enterprise Context Pyramid" } },
              el("h3", { className: "help-section-title", text: "2. The 5-Layer Enterprise Context Pyramid (L1 → L5)" }),
              el("p", {
                className: "help-copy",
                text: "Rungs R1–R6 follow the executive investigation story rather than strict L1→L5 order. Here is how each pyramid layer maps to the live rungs:"
              }),
              el("div", { className: "help-pyramid-list" },
                ...pyramidRows.map((row) =>
                  el("div", { className: "help-pyramid-item" },
                    el("div", { className: "help-pyramid-head" },
                      el("strong", { className: "help-item-term", text: row.layer }),
                      el("span", { className: "badge badge-mono", text: row.rungs })
                    ),
                    el("p", { className: "help-copy", text: row.desc })
                  )
                )
              )
            ),
            el("section", { className: "help-section", attrs: { "aria-label": "What Every Badge and Metric Means" } },
              el("h3", { className: "help-section-title", text: "3. What Every Badge & Metric Means" }),
              el("dl", { className: "help-glossary" },
                ...glossaryItems.map((item) =>
                  el("div", { className: "help-glossary-item" },
                    el("dt", { className: "help-item-term", text: item.term }),
                    el("dd", { className: "help-copy", text: item.desc })
                  )
                )
              )
            ),
            el("section", { className: "help-section", attrs: { "aria-label": "Quick Keyboard Shortcuts" } },
              el("h3", { className: "help-section-title", text: "4. Quick Keyboard Shortcuts" }),
              el("div", { className: "rls-table-wrap" },
                el("table", { className: "rls-table help-shortcut-table" },
                  el("thead", null,
                    el("tr", null,
                      el("th", { text: "Key" }),
                      el("th", { text: "Action" })
                    )
                  ),
                  el("tbody", null,
                    ...shortcutRows.map(([k, action]) =>
                      el("tr", null,
                        el("td", null, el("span", { className: "kbd-hint", text: k })),
                        el("td", { text: action })
                      )
                    )
                  )
                )
              )
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
      const wasHelpOpen = prevHelpOpen;
      prevHelpOpen = state.helpOpen;
      syncUrlAndDocument();
      const mainShell = state.mode === "workbench" ? buildWorkbenchView() : buildStageView();
      const pollModal = buildPollModal();
      const xrayDrawer = buildStageXrayDrawer();
      const helpDrawer = buildHelpDrawer();
      const nodes = [mainShell];
      if (xrayDrawer) {
        nodes.push(xrayDrawer);
      }
      if (pollModal) {
        nodes.push(pollModal);
      }
      if (helpDrawer) {
        nodes.push(helpDrawer);
      }
      root.replaceChildren(...nodes);
      if (!wasHelpOpen && state.helpOpen) {
        const closeBtn = document.getElementById("help-drawer-close");
        if (closeBtn) {
          closeBtn.focus();
        }
      } else if (wasHelpOpen && !state.helpOpen) {
        const guideBtn = document.getElementById("help-guide-btn");
        if (guideBtn) {
          guideBtn.focus();
        }
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
      if (e.code === "Escape") {
        if (state.authDialogOpen) {
          e.preventDefault();
          setState({
            authDialogOpen: false,
            authDialogError: null,
            pendingAgentAction: false,
            pendingPollReset: false
          });
          return;
        }
        if (state.helpOpen) {
          e.preventDefault();
          setState({ helpOpen: false });
          return;
        }
        if (state.pollOpen) {
          e.preventDefault();
          stopPollTimer();
          setState({ pollOpen: false });
          return;
        }
        if (state.stageXrayOpen) {
          e.preventDefault();
          setState({ stageXrayOpen: false });
          return;
        }
        return;
      }
      if (state.helpOpen && e.key === "Tab") {
        const drawer = document.getElementById("help-guide-drawer");
        if (drawer) {
          const focusables = Array.from(
            drawer.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')
          );
          if (focusables.length > 0) {
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            if (e.shiftKey && (document.activeElement === first || !drawer.contains(document.activeElement))) {
              e.preventDefault();
              last.focus();
            } else if (!e.shiftKey && (document.activeElement === last || !drawer.contains(document.activeElement))) {
              e.preventDefault();
              first.focus();
            }
          }
        }
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey || isEditableTarget(e.target)) {
        return;
      }
      if (e.key === "?" || e.code === "KeyH") {
        e.preventDefault();
        toggleHelp();
        return;
      }
      if (state.helpOpen) {
        return;
      }
      if (e.code === "KeyP") {
        if (state.isOverview) {
          return;
        }
        e.preventDefault();
        togglePoll();
        return;
      }
      if (state.pollOpen) {
        return;
      }
      if (e.code === "KeyX") {
        if (state.mode === "stage" && !isNonRung()) {
          e.preventDefault();
          toggleStageXray();
        }
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
        return;
      }
      if (state.mode !== "stage" || state.stageXrayOpen) {
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
      }
    });

    render();
    if (state.isOverview) {
      const startBtn = document.getElementById("overview-start-btn");
      if (startBtn) {
        startBtn.focus();
      }
    }
    fetchHealth();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
  } else {
    initApp();
  }
})();
