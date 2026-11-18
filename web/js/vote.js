(function () {
  "use strict";

  const VOTER_TOKEN_KEY = "context_poll_voter_token";
  const CHOICE_STORAGE_PREFIX = "context_poll_choice:";
  const VOTER_TOKEN_RE = /^[A-Za-z0-9_-]{16,64}$/;
  const POLL_REFRESH_MS = 3000;
  const MAX_POLL_BACKOFF_MS = 12000;

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
            node.appendChild(
              typeof nested === "string" || typeof nested === "number"
                ? document.createTextNode(String(nested))
                : nested
            );
          }
        }
      } else {
        node.appendChild(
          typeof child === "string" || typeof child === "number"
            ? document.createTextNode(String(child))
            : child
        );
      }
    }
    return node;
  }

  function generateVoterToken() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID().replace(/-/g, "");
    }
    if (window.crypto && typeof window.crypto.getRandomValues === "function") {
      const bytes = new Uint8Array(16);
      window.crypto.getRandomValues(bytes);
      return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
    }
    throw new Error("Cryptographically secure random generator unavailable.");
  }

  function getOrCreateVoterToken() {
    try {
      const existing = window.localStorage && window.localStorage.getItem(VOTER_TOKEN_KEY);
      if (existing && VOTER_TOKEN_RE.test(existing)) {
        return existing;
      }
      const created = generateVoterToken();
      if (window.localStorage) {
        window.localStorage.setItem(VOTER_TOKEN_KEY, created);
      }
      return created;
    } catch (_err) {
      return generateVoterToken();
    }
  }

  function choiceStorageKey(packId, rungId, epoch) {
    return `${CHOICE_STORAGE_PREFIX}${packId}:${rungId}:e${epoch}`;
  }

  function loadSavedChoice(packId, rungId, epoch) {
    try {
      if (!window.sessionStorage) {
        return null;
      }
      const val = window.sessionStorage.getItem(choiceStorageKey(packId, rungId, epoch));
      return val && ["A", "B", "C", "D"].includes(val) ? val : null;
    } catch (_err) {
      return null;
    }
  }

  function saveChoice(packId, rungId, epoch, choice) {
    try {
      if (!window.sessionStorage) {
        return;
      }
      window.sessionStorage.setItem(choiceStorageKey(packId, rungId, epoch), choice);
    } catch (_err) {}
  }

  function extractErrorMessage(data, status) {
    if (data && typeof data.detail === "string") {
      return data.detail;
    }
    if (data && data.detail !== undefined && data.detail !== null) {
      return JSON.stringify(data.detail);
    }
    return `HTTP ${status}`;
  }

  function initVotePage() {
    const root = document.getElementById("vote-root");
    if (!root) {
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const voterToken = getOrCreateVoterToken();
    const initialTheme = params.get("theme") === "paper" ? "paper" : "dark";
    document.documentElement.setAttribute("data-theme", initialTheme);

    const state = {
      theme: initialTheme,
      packId: params.get("pack") || "",
      rungId: params.get("rung") || "",
      loading: true,
      submitting: false,
      error: null,
      voteError: null,
      staleNotice: null,
      pollData: null,
      selectedChoice: null
    };

    let activeFetchSeq = 0;
    let targetPackId = state.packId;
    let targetRungId = state.rungId;
    let pollDelayMs = POLL_REFRESH_MS;
    let refreshTimerId = null;
    let renderedViewKey = null;

    function syncUrl(packId, rungId) {
      const next = new URLSearchParams();
      if (packId) {
        next.set("pack", packId);
      }
      if (rungId) {
        next.set("rung", rungId);
      }
      if (state.theme === "paper") {
        next.set("theme", "paper");
      }
      try {
        const q = next.toString();
        window.history.replaceState(null, "", q ? `${window.location.pathname}?${q}` : window.location.pathname);
      } catch (_err) {}
    }

    function scheduleNextRefresh() {
      if (refreshTimerId !== null) {
        window.clearTimeout(refreshTimerId);
        refreshTimerId = null;
      }
      refreshTimerId = window.setTimeout(() => {
        refreshTimerId = null;
        if (document.visibilityState === "visible" && !state.submitting) {
          fetchPollState({ packId: targetPackId, rungId: targetRungId });
        } else {
          scheduleNextRefresh();
        }
      }, pollDelayMs);
    }

    function viewKeyFor(data) {
      if (!data) {
        return null;
      }
      return `${data.pack_id}:${data.rung_id}:${data.epoch}`;
    }

    function renderStageBannerSlot(slot, data) {
      if (!slot) {
        return;
      }
      const rungs = Array.isArray(data.available_rungs) ? data.available_rungs : [];
      if (data.active_stage_rung_id && data.active_stage_rung_id !== data.rung_id) {
        const stageRung = rungs.find((r) => r.id === data.active_stage_rung_id);
        const stageLabel = stageRung ? stageRung.short_label : data.active_stage_rung_id;
        const desiredText = `Live on Stage: ${stageLabel} — Tap to Jump →`;
        const existingBtn = slot.querySelector(".vote-stage-banner");
        if (existingBtn && existingBtn.getAttribute("data-stage-rung") === data.active_stage_rung_id) {
          if (existingBtn.textContent !== desiredText) {
            existingBtn.textContent = desiredText;
          }
          return;
        }
        slot.replaceChildren(
          el("button", {
            className: "vote-stage-banner",
            attrs: {
              type: "button",
              "data-stage-rung": data.active_stage_rung_id
            },
            text: desiredText,
            onClick: () => switchRung(data.active_stage_rung_id)
          })
        );
      } else if (slot.childNodes.length > 0) {
        slot.replaceChildren();
      }
    }

    function patchVoteDomInPlace() {
      const data = state.pollData;
      if (!data || renderedViewKey !== viewKeyFor(data)) {
        return false;
      }
      const card = root.querySelector(`[data-vote-view="${renderedViewKey}"]`);
      if (!card) {
        return false;
      }

      const totalVotes = Number(data.total_votes || 0);
      const counts = data.counts || {};
      const showTally = Boolean(state.selectedChoice) || totalVotes > 0;

      const totalBadge = root.querySelector("#vote-total-badge");
      if (totalBadge) {
        totalBadge.textContent = `${totalVotes} room votes`;
      }

      renderStageBannerSlot(root.querySelector("#vote-stage-banner-slot"), data);

      const optionBtns = card.querySelectorAll("[data-vote-choice]");
      for (const btn of optionBtns) {
        const key = btn.getAttribute("data-vote-choice");
        if (!key) {
          continue;
        }
        const isChosen = state.selectedChoice === key;
        const count = Number(counts[key] || 0);
        const pct = totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0;

        btn.classList.toggle("is-selected", isChosen);
        btn.setAttribute("aria-pressed", isChosen ? "true" : "false");
        if (state.submitting) {
          btn.setAttribute("disabled", "true");
        } else {
          btn.removeAttribute("disabled");
        }

        const bar = btn.querySelector(".poll-option-bar");
        if (bar) {
          bar.style.width = `${showTally ? pct : 0}%`;
        }
        const stat = btn.querySelector(".poll-option-stat");
        if (stat) {
          if (showTally) {
            stat.textContent = `${count} · ${pct}%`;
            stat.removeAttribute("hidden");
          } else {
            stat.textContent = "";
            stat.setAttribute("hidden", "hidden");
          }
        }
      }

      const statusBanner = card.querySelector("#vote-status-banner");
      if (statusBanner) {
        statusBanner.classList.toggle("is-counted", Boolean(state.selectedChoice));
        statusBanner.textContent = state.selectedChoice
          ? `✓ Your vote (${state.selectedChoice}) is counted — tap any option to switch`
          : "Tap A, B, C, or D to cast your live vote.";
      }

      const staleBanner = card.querySelector("#vote-stale-banner");
      if (staleBanner) {
        if (state.staleNotice) {
          staleBanner.textContent = state.staleNotice;
          staleBanner.removeAttribute("hidden");
        } else {
          staleBanner.textContent = "";
          staleBanner.setAttribute("hidden", "hidden");
        }
      }

      const errBanner = card.querySelector("#vote-error-banner");
      if (errBanner) {
        if (state.voteError) {
          errBanner.textContent = state.voteError;
          errBanner.removeAttribute("hidden");
        } else {
          errBanner.textContent = "";
          errBanner.setAttribute("hidden", "hidden");
        }
      }

      return true;
    }

    function updateOrRender() {
      if (!patchVoteDomInPlace()) {
        render();
      }
    }

    async function fetchPollState(opts) {
      const seq = (opts && opts.seq !== undefined) ? opts.seq : activeFetchSeq;
      const requestedPack = (opts && opts.packId !== undefined) ? opts.packId : targetPackId;
      const requestedRung = (opts && opts.rungId !== undefined) ? opts.rungId : targetRungId;

      const query = new URLSearchParams();
      if (requestedPack) {
        query.set("pack_id", requestedPack);
      }
      if (requestedRung) {
        query.set("rung_id", requestedRung);
      }
      const qStr = query.toString();
      const url = qStr ? `/api/poll/state?${qStr}` : "/api/poll/state";

      try {
        const res = await fetch(url, { method: "GET", cache: "no-store" });
        const data = await res.json().catch(() => null);

        // Drop stale in-flight responses if user switched rung since this fetch started.
        if (seq !== activeFetchSeq || requestedRung !== targetRungId) {
          return;
        }

        if (!res.ok || !data || typeof data !== "object") {
          state.loading = false;
          const msg = extractErrorMessage(data, res.status);
          if (state.pollData) {
            pollDelayMs = Math.min(MAX_POLL_BACKOFF_MS, pollDelayMs * 2);
            state.staleNotice = res.status === 429
              ? "High room traffic — slowing live refresh (your vote is safe)."
              : `Refresh delayed (${msg}) — showing last received counts.`;
            updateOrRender();
          } else {
            state.error = msg;
            render();
          }
          scheduleNextRefresh();
          return;
        }

        pollDelayMs = POLL_REFRESH_MS;
        state.loading = false;
        state.error = null;
        state.staleNotice = null;
        targetPackId = data.pack_id;
        targetRungId = data.rung_id;
        state.packId = data.pack_id;
        state.rungId = data.rung_id;
        state.selectedChoice = loadSavedChoice(data.pack_id, data.rung_id, data.epoch);
        state.pollData = data;
        syncUrl(data.pack_id, data.rung_id);
        updateOrRender();
        scheduleNextRefresh();
      } catch (err) {
        if (seq !== activeFetchSeq || requestedRung !== targetRungId) {
          return;
        }
        state.loading = false;
        const msg = err && err.message ? err.message : "Unable to reach poll server.";
        if (state.pollData) {
          pollDelayMs = Math.min(MAX_POLL_BACKOFF_MS, pollDelayMs * 2);
          state.staleNotice = "Reconnecting to live poll — showing last received counts.";
          updateOrRender();
        } else {
          state.error = msg;
          render();
        }
        scheduleNextRefresh();
      }
    }

    async function submitVote(choice) {
      if (!state.pollData || state.submitting) {
        return;
      }
      state.submitting = true;
      state.voteError = null;
      const targetPack = state.pollData.pack_id;
      const targetRung = state.pollData.rung_id;
      updateOrRender();

      try {
        const res = await fetch("/api/poll/vote", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pack_id: targetPack,
            rung_id: targetRung,
            choice,
            voter_token: voterToken
          })
        });
        const data = await res.json().catch(() => ({}));
        state.submitting = false;
        if (!res.ok) {
          state.voteError = extractErrorMessage(data, res.status);
          updateOrRender();
          return;
        }
        const tallyEpoch = Number(data.epoch || state.pollData.epoch || 1);
        const recordedEpoch = Number(data.recorded_epoch || tallyEpoch);
        const acceptedChoice = (data.recorded_choice && tallyEpoch === recordedEpoch)
          ? String(data.recorded_choice)
          : null;
        if (acceptedChoice) {
          saveChoice(targetPack, targetRung, tallyEpoch, acceptedChoice);
        }
        state.selectedChoice = acceptedChoice;
        state.staleNotice = null;
        pollDelayMs = POLL_REFRESH_MS;
        state.pollData = {
          ...state.pollData,
          counts: data.counts || state.pollData.counts,
          total_votes: Number(data.total_votes ?? state.pollData.total_votes),
          epoch: tallyEpoch
        };
        updateOrRender();
      } catch (err) {
        state.submitting = false;
        state.voteError = err && err.message ? err.message : "Network error recording vote.";
        updateOrRender();
      }
    }

    function switchRung(nextRungId) {
      if (!nextRungId || nextRungId === targetRungId) {
        return;
      }
      activeFetchSeq += 1;
      targetRungId = nextRungId;
      pollDelayMs = POLL_REFRESH_MS;
      state.rungId = nextRungId;
      state.loading = true;
      state.error = null;
      state.voteError = null;
      state.staleNotice = null;
      state.selectedChoice = null;
      renderedViewKey = null;
      render();
      fetchPollState({ packId: targetPackId, rungId: nextRungId, seq: activeFetchSeq });
    }

    function toggleTheme() {
      state.theme = state.theme === "dark" ? "paper" : "dark";
      document.documentElement.setAttribute("data-theme", state.theme);
      if (state.pollData) {
        syncUrl(state.pollData.pack_id, state.pollData.rung_id);
      }
      renderedViewKey = null;
      render();
    }

    function render() {
      document.documentElement.setAttribute("data-theme", state.theme);
      const data = state.pollData;

      const header = el("header", { className: "vote-header" },
        el("div", { className: "vote-brand" },
          el("span", { className: "vote-eyebrow", text: "Live Audience Poll" }),
          el("h1", {
            className: "vote-brand-title",
            text: data ? data.pack_title : "Executive Context Poll"
          })
        ),
        el("button", {
          className: "btn",
          text: state.theme === "dark" ? "Paper Theme" : "Dark Theme",
          attrs: {
            type: "button",
            "aria-label": state.theme === "dark" ? "Switch to paper light theme" : "Switch to dark ballroom theme"
          },
          onClick: toggleTheme
        })
      );

      if (state.loading && (!data || data.rung_id !== targetRungId)) {
        renderedViewKey = null;
        root.replaceChildren(
          header,
          el("main", { className: "vote-main" },
            el("div", { className: "vote-card", attrs: { role: "status" } },
              el("p", { className: "outcome-detail", text: "Loading live audience poll..." })
            )
          )
        );
        return;
      }

      if (state.error && !data) {
        renderedViewKey = null;
        root.replaceChildren(
          header,
          el("main", { className: "vote-main" },
            el("div", { className: "live-result-banner is-error", attrs: { role: "alert" } },
              el("span", { text: state.error }),
              el("button", {
                className: "btn",
                text: "Retry",
                attrs: { type: "button" },
                onClick: () => fetchPollState({ packId: targetPackId, rungId: targetRungId, seq: activeFetchSeq })
              })
            )
          )
        );
        return;
      }

      const rungs = Array.isArray(data.available_rungs) ? data.available_rungs : [];
      const rungSwitcher = el("nav", {
        className: "vote-rung-pills",
        attrs: { "aria-label": "Select poll rung" }
      },
        ...rungs.map((r) => {
          const isActive = r.id === data.rung_id;
          return el("button", {
            className: `seg-btn vote-rung-btn${isActive ? " is-active" : ""}`,
            text: `R${r.rung_num}`,
            attrs: {
              type: "button",
              title: r.short_label,
              "aria-current": isActive ? "step" : null
            },
            onClick: () => switchRung(r.id)
          });
        })
      );

      const stageBannerSlot = el("div", {
        className: "vote-stage-banner-slot",
        attrs: { id: "vote-stage-banner-slot" }
      });
      renderStageBannerSlot(stageBannerSlot, data);

      const totalVotes = Number(data.total_votes || 0);
      const counts = data.counts || {};
      const showTally = Boolean(state.selectedChoice) || totalVotes > 0;
      const viewKey = viewKeyFor(data);
      renderedViewKey = viewKey;

      const optionsWrap = el("div", { className: "vote-options" },
        ...(Array.isArray(data.options) ? data.options : []).map((opt) => {
          const isChosen = state.selectedChoice === opt.key;
          const count = Number(counts[opt.key] || 0);
          const pct = totalVotes > 0 ? Math.round((count / totalVotes) * 100) : 0;

          return el("button", {
            className: `vote-option-btn${isChosen ? " is-selected" : ""}`,
            attrs: {
              type: "button",
              disabled: state.submitting ? true : null,
              "aria-pressed": isChosen ? "true" : "false",
              "data-vote-choice": opt.key
            },
            onClick: () => submitVote(opt.key)
          },
            el("span", {
              className: "poll-option-bar",
              attrs: { style: `width: ${showTally ? pct : 0}%`, "aria-hidden": "true" }
            }),
            el("span", { className: "poll-option-row" },
              el("span", { className: "poll-key-pill", text: opt.key }),
              el("span", { className: "poll-option-text", text: opt.text }),
              el("span", {
                className: "poll-option-stat badge badge-mono",
                text: showTally ? `${count} · ${pct}%` : "",
                attrs: { hidden: showTally ? null : "hidden" }
              })
            )
          );
        })
      );

      const statusBanner = el("div", {
        className: `vote-status${state.selectedChoice ? " is-counted" : ""}`,
        attrs: { id: "vote-status-banner", role: "status", "aria-live": "polite" }
      },
        state.selectedChoice
          ? `✓ Your vote (${state.selectedChoice}) is counted — tap any option to switch`
          : "Tap A, B, C, or D to cast your live vote."
      );

      const staleBanner = el("div", {
        className: "vote-stale-banner",
        attrs: {
          id: "vote-stale-banner",
          role: "status",
          "aria-live": "polite",
          hidden: state.staleNotice ? null : "hidden"
        },
        text: state.staleNotice || ""
      });

      const errorBanner = el("div", {
        className: "live-result-banner is-error",
        attrs: {
          id: "vote-error-banner",
          role: "alert",
          hidden: state.voteError ? null : "hidden"
        },
        text: state.voteError || ""
      });

      const externalUrl =
        data.external_poll_url && String(data.external_poll_url).startsWith("https://")
          ? String(data.external_poll_url)
          : null;

      const card = el("section", {
        className: "vote-card",
        attrs: {
          "aria-labelledby": "vote-prompt",
          "data-vote-view": viewKey
        }
      },
        el("div", { className: "vote-card-meta" },
          el("span", { className: "badge badge-mono", text: data.short_label }),
          el("span", {
            className: "badge badge-mono",
            attrs: { id: "vote-total-badge" },
            text: `${totalVotes} room votes`
          })
        ),
        el("p", { className: "vote-question-sub", text: data.question }),
        el("h2", { className: "vote-prompt", attrs: { id: "vote-prompt" }, text: data.prompt }),
        optionsWrap,
        statusBanner,
        staleBanner,
        errorBanner,
        externalUrl
          ? el("div", { className: "vote-external-row" },
              el("a", {
                className: "btn",
                text: "Open External Poll ↗",
                attrs: { href: externalUrl, target: "_blank", rel: "noopener" }
              })
            )
          : null
      );

      root.replaceChildren(
        header,
        el("main", { className: "vote-main" },
          rungSwitcher,
          stageBannerSlot,
          card
        )
      );
    }

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible" && !state.submitting) {
        pollDelayMs = POLL_REFRESH_MS;
        fetchPollState({ packId: targetPackId, rungId: targetRungId, seq: activeFetchSeq });
      }
    });

    window.addEventListener("beforeunload", () => {
      if (refreshTimerId !== null) {
        window.clearTimeout(refreshTimerId);
      }
    });

    render();
    fetchPollState({ packId: targetPackId, rungId: targetRungId, seq: activeFetchSeq });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initVotePage);
  } else {
    initVotePage();
  }
})();
