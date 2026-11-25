(function () {
  "use strict";

  var PACK_ID = "cymbal_cmo_q4_sgd";
  var GOVERNED_PROVENANCE_NOTES = {
    r2_return_drivers:
      "Executed live on certified BigQuery tables in asia-southeast1 (deterministic SQL stand-in; AI.KEY_DRIVERS() and BigQuery Row-Level Security are the reference architecture).",
    r5_clawback_s3_pdf:
      "Executed in asia-southeast1 on a regional copy of the S3 click log. S3 federation and Object Table AI.GENERATE are the reference architecture.",
    r6_q4_forecast:
      "Executed live on a pre-computed Q4 forecast table in asia-southeast1 (stand-in for live AI.FORECAST model inference)."
  };
  var TURN_TO_RUNG = {
    t1: "r1_net_revenue",
    t2: "r2_return_drivers",
    t3: "r3_channel_pnl",
    t4: "r4_fraud_graph",
    t5: "r5_clawback_s3_pdf",
    t6: "r6_q4_forecast"
  };

  if (window.location.protocol !== "http:" && window.location.protocol !== "https:") return;

  try {
    var searchParams = new URLSearchParams(window.location.search);
    var urlKey = searchParams.get("key");
    if (urlKey) {
      if (window.sessionStorage) {
        window.sessionStorage.setItem("context_demo_key", urlKey);
      }
      searchParams.delete("key");
      var remainingQs = searchParams.toString();
      var cleanUrl =
        window.location.pathname +
        (remainingQs ? "?" + remainingQs : "") +
        window.location.hash;
      if (window.history && typeof window.history.replaceState === "function") {
        window.history.replaceState(null, "", cleanUrl);
      }
    }
  } catch (_e) {}

  var active = false;
  var latestDetail = window.__v5LastInspector || null;
  var resultCache = Object.create(null);
  var inFlightKeys = new Set();

  function hasOwn(obj, key) {
    return Object.prototype.hasOwnProperty.call(obj, key);
  }

  function resolveDetailState(detail) {
    if (!detail || detail.isSibling || !detail.turnId || !hasOwn(TURN_TO_RUNG, detail.turnId)) {
      return null;
    }
    var rungId = TURN_TO_RUNG[detail.turnId];
    var mode = detail.mode === "governed" ? "governed" : "blind";
    return {
      rungId: rungId,
      mode: mode,
      cacheKey: rungId + ":" + mode
    };
  }

  function el(tag, text, styles) {
    var node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = String(text);
    if (styles) Object.assign(node.style, styles);
    return node;
  }

  function renderResult(body, rungId, mode, data) {
    body.textContent = "";
    var meta = [
      "Mode: " + (data.execution_mode || "unknown"),
      typeof data.latency_ms === "number" ? "Latency: " + data.latency_ms + " ms" : null,
      typeof data.row_count === "number" ? "Rows: " + data.row_count : null
    ].filter(Boolean).join("  |  ");
    body.appendChild(el("div", meta, { fontSize: "11.5px", color: "var(--on-surface-variant-strong)", fontFamily: "var(--font-mono)" }));

    if (mode === "governed" && hasOwn(GOVERNED_PROVENANCE_NOTES, rungId)) {
      body.appendChild(el("div", GOVERNED_PROVENANCE_NOTES[rungId], {
        fontSize: "11.5px", lineHeight: "1.45", padding: "7px 9px", borderRadius: "8px",
        background: "var(--vs-info-bg)", border: "1px solid var(--vs-info-border)", color: "var(--vs-info-text)"
      }));
    }
    if (data.sql_or_gql) {
      body.appendChild(el("pre", data.sql_or_gql, {
        margin: "0", padding: "9px 10px", borderRadius: "8px", background: "var(--code-bg)", color: "#ffffff",
        fontFamily: "var(--font-mono)", fontSize: "10.5px", lineHeight: "1.45", whiteSpace: "pre-wrap",
        wordBreak: "break-word", maxHeight: "170px", overflowY: "auto"
      }));
    }

    var rows = Array.isArray(data.rows) ? data.rows.slice(0, 10) : [];
    if (!rows.length) {
      body.appendChild(el("div", "0 live rows returned (offline fixture or empty result).", { fontSize: "11.5px", color: "var(--on-surface-variant)" }));
      return;
    }

    var cols = Object.keys(rows[0]);
    var wrap = el("div", null, { overflowX: "auto", border: "1px solid var(--outline-variant)", borderRadius: "8px" });
    var table = el("table", null, { width: "100%", borderCollapse: "collapse", fontSize: "11px", fontFamily: "var(--font-mono)" });
    var thead = document.createElement("thead");
    var hr = document.createElement("tr");
    cols.forEach(function (c) {
      hr.appendChild(el("th", c, {
        textAlign: "left", padding: "5px 8px", background: "var(--surface)",
        borderBottom: "1px solid var(--outline-variant)", color: "var(--on-surface-variant-strong)", fontWeight: "600", whiteSpace: "nowrap"
      }));
    });
    thead.appendChild(hr);
    table.appendChild(thead);

    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      cols.forEach(function (c) {
        var v = row[c];
        tr.appendChild(el("td", v === null || v === undefined ? "NULL" : (typeof v === "object" ? JSON.stringify(v) : String(v)), {
          padding: "5px 8px", borderBottom: "1px solid var(--outline-variant)", color: "var(--on-surface)", whiteSpace: "nowrap"
        }));
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    wrap.appendChild(table);
    body.appendChild(wrap);
  }

  function renderBox(detail) {
    if (!active) return;
    var mount = document.getElementById("inspBodyMount") || document.getElementById("contextInspector");
    if (!mount) return;
    var existing = document.getElementById("liveBridgeBox");
    if (existing) existing.remove();

    var state = resolveDetailState(detail);
    if (!state) return;

    var rungId = state.rungId;
    var mode = state.mode;
    var cacheKey = state.cacheKey;
    var btnIdleLabel = mode === "governed" ? "Run governed SQL on BigQuery" : "Run raw SQL on BigQuery";
    var isInFlight = inFlightKeys.has(cacheKey);

    var box = el("section", null, {
      marginTop: "2px", padding: "12px", borderRadius: "12px", background: "var(--surface-container-low)",
      border: "1px solid var(--outline-variant)", display: "flex", flexDirection: "column", gap: "9px", flexShrink: "0"
    });
    box.id = "liveBridgeBox";

    var head = el("div", null, { display: "flex", alignItems: "center", justifyContent: "space-between", gap: "8px", flexWrap: "wrap" });
    head.appendChild(el("span", "Live BigQuery Verification", { fontSize: "12.5px", fontWeight: "650", color: "var(--on-surface)" }));
    var btn = el("button", isInFlight ? "Running..." : btnIdleLabel, {
      padding: "5px 11px", borderRadius: "9999px", border: "1px solid var(--primary-overlay-border)",
      background: "var(--accent-fixed)", color: "#ffffff", fontSize: "11.5px", fontWeight: "600", cursor: isInFlight ? "wait" : "pointer"
    });
    btn.type = "button";
    btn.disabled = isInFlight;
    head.appendChild(btn);
    box.appendChild(head);

    var body = el("div", null, { display: "flex", flexDirection: "column", gap: "8px" });
    box.appendChild(body);
    mount.appendChild(box);

    if (isInFlight) {
      body.appendChild(el("div", "Running query on BigQuery...", { fontSize: "11.5px", color: "var(--on-surface-variant)" }));
    } else if (hasOwn(resultCache, cacheKey)) {
      var cached = resultCache[cacheKey];
      if (cached.error) {
        body.appendChild(el("div", cached.error, {
          fontSize: "11.5px", color: "var(--error)", padding: "7px 9px", borderRadius: "8px", background: "var(--error-container)"
        }));
      } else {
        renderResult(body, rungId, mode, cached.data);
      }
    }

    btn.addEventListener("click", function () {
      if (inFlightKeys.has(cacheKey)) return;
      inFlightKeys.add(cacheKey);
      btn.disabled = true;
      btn.textContent = "Running...";
      btn.style.cursor = "wait";
      body.textContent = "";
      body.appendChild(el("div", "Running query on BigQuery...", { fontSize: "11.5px", color: "var(--on-surface-variant)" }));

      var headers = { "Content-Type": "application/json" };
      try {
        var key = window.sessionStorage && window.sessionStorage.getItem("context_demo_key");
        if (key) headers["X-Demo-Key"] = key;
      } catch (_e) {}

      fetch("/api/run-rung", {
        method: "POST", credentials: "same-origin", headers: headers,
        body: JSON.stringify({ pack_id: PACK_ID, rung_id: rungId, mode: mode })
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (payload) {
          if (!res.ok) throw new Error(payload.detail || ("Request failed (HTTP " + res.status + ")"));
          return payload;
        });
      }).then(function (data) {
        resultCache[cacheKey] = { data: data };
      }).catch(function (err) {
        var msg = (err && err.message) ? err.message : "Live BigQuery request failed.";
        resultCache[cacheKey] = { error: msg };
      }).finally(function () {
        inFlightKeys.delete(cacheKey);
        var currentState = resolveDetailState(latestDetail);
        if (currentState && currentState.cacheKey === cacheKey) {
          renderBox(latestDetail);
        }
      });
    });
  }

  document.addEventListener("v5:inspector", function (ev) {
    latestDetail = ev && ev.detail ? ev.detail : null;
    renderBox(latestDetail);
  });

  fetch("/api/health", { credentials: "same-origin" })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (data && Array.isArray(data.packs) && data.packs.indexOf(PACK_ID) !== -1) {
        active = true;
        if (latestDetail) renderBox(latestDetail);
      }
    })
    .catch(function () {});
})();
