(() => {
  "use strict";
  const params = new URLSearchParams(location.search);
  const compact = params.get("mode") === "compact";
  if (compact) document.body.classList.add("compact");

  const invoke = async (command, args = {}) => {
    if (!window.__TAURI__?.core?.invoke) throw new Error("Tauri bridge unavailable");
    return window.__TAURI__.core.invoke(command, args);
  };
  const $ = (id) => document.getElementById(id);
  const n = (v) => Number.isFinite(Number(v)) ? Number(v).toLocaleString() : "—";
  const safe = (v, fallback = "—") => v === undefined || v === null ? fallback : String(v);
  let initialAttentionLoaded = false;
  const seenAttention = new Set();
  let coreStarting = false;

  async function api(path) {
    const raw = await invoke("core_get", { path });
    return JSON.parse(raw);
  }

  function kv(target, rows) {
    target.innerHTML = rows.map(([k, v]) => `<div class="k">${escapeHtml(k)}</div><div class="v">${escapeHtml(safe(v))}</div>`).join("");
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
  }

  function renderPipeline(p) {
    const s = p?.stages || {};
    $("m-obs").textContent = n(s.provider_observations);
    $("m-quant").textContent = n(s.quant_evaluations);
    $("m-labels").textContent = n(s.online_labels);
    $("pipeline-live").textContent = p?.end_to_end_live ? "END-TO-END LIVE" : "CHECK PIPELINE";
    const keys = [
      ["PROVIDER OBS", s.provider_observations], ["BUS IN", s.event_bus_in],
      ["TAPE ACCEPTS", s.tape_accepts], ["UNIVERSE ELIGIBLE", s.universe_eligible],
      ["QUANT EVAL", s.quant_evaluations], ["EXPERIMENTS", s.experiments],
      ["FORWARD MARKS", s.forward_marks], ["MODEL UPDATES", s.online_updates]
    ];
    $("pipeline-grid").innerHTML = keys.map(([k, v]) => `<div class="metric-cell"><em>${k}</em><strong>${n(v)}</strong></div>`).join("");
  }

  function renderResearch(r) {
    const e = r?.experiments || {}, o = r?.online || {}, a = r?.archive || {}, s = r?.science || {};
    $("r-exp").textContent = n(e.experiments);
    $("r-marks").textContent = n(e.forward_marks);
    $("r-learned").textContent = n(e.learned);
    kv($("research-details"), [
      ["MODEL", o.model_key], ["PROTOCOL", o.protocol], ["ACCURACY", o.accuracy],
      ["DRIFT", `${o.drift_detector || "—"} / ${n(o.drift_events)}`], ["REPLAYED", n(o.replayed_predictions)],
      ["ARCHIVE ROWS", n(a.rows)], ["PARQUET", `${n(a.parquet_files)} files / ${n(a.parquet_bytes)} bytes`],
      ["SCIENTIST", `${s.state || "—"} / n=${n(s.sample_n)}`], ["PROMOTION", s.promotion_allowed === true ? "ALLOWED" : "NOT ALLOWED"]
    ]);
  }

  function renderEvidence(e) {
    const store = e?.store || {}, graph = e?.graph || {}, risk = e?.risk || {};
    const ga = graph?.analysis || graph;
    $("e-security").textContent = n(store.security_evidence ?? risk.evidence_count);
    $("e-edges").textContent = n(ga.edges);
    kv($("evidence-details"), [
      ["STORE ROWS", n(store.total_rows ?? store.rows)], ["RISK MODE", risk.explained_evidence_only ? "EVIDENCE ONLY" : "NO MYSTERY SCORE"],
      ["GRAPH NODES", n(ga.nodes)], ["GRAPH COMPONENTS", n(ga.components)],
      ["SOCIAL", "PROJECT / INDEPENDENT SEPARATED"], ["MEMORY", "FACT / OBSERVATION / HYPOTHESIS / CLAIM / CONCLUSION"]
    ]);
  }

  function attentionId(p) {
    return `${p.identity_key || "unknown"}:${p.created_at || JSON.stringify(p.trigger_reasons || [])}`;
  }

  async function renderAttention(data) {
    const items = Array.isArray(data?.items) ? data.items : [];
    $("attention-feed").innerHTML = items.length ? items.map((p) => {
      const changed = (p.what_changed || []).slice(0, 2).map(x => `<p>${escapeHtml(x)}</p>`).join("");
      const counter = (p.counter_evidence || []).slice(0, 2).map(x => `<p class="counter">COUNTER · ${escapeHtml(x)}</p>`).join("");
      const unknown = (p.unknowns || []).slice(0, 2).map(x => `<p class="unknown">UNKNOWN · ${escapeHtml(x)}</p>`).join("");
      return `<article class="attention-card"><div class="attention-head"><span>${escapeHtml(safe(p.identity_key))}</span><span class="attention-status">${escapeHtml(safe(p.status))}</span></div><h3>${escapeHtml((p.why_it_matters_for_research || ["Evidence changed"])[0])}</h3>${changed}${counter}${unknown}</article>`;
    }).join("") : '<div class="empty">NO SEMANTIC PACKETS YET</div>';

    if (initialAttentionLoaded) {
      for (const p of items) {
        const id = attentionId(p);
        if (!seenAttention.has(id)) {
          const body = (p.what_changed || p.why_it_matters_for_research || ["Research evidence changed"])[0];
          try { await invoke("notify_attention", { title: `JARVIS · ${p.status || "EVIDENCE UPDATE"}`, body: String(body).slice(0, 220) }); } catch (_) {}
        }
      }
    }
    for (const p of items) seenAttention.add(attentionId(p));
    initialAttentionLoaded = true;
  }

  async function renderSystem() {
    let models = {}, agents = {};
    try { models = await api("/api/models"); } catch (e) { models = { available: false, error: String(e) }; }
    try { agents = await api("/api/agents"); } catch (e) { agents = { available: false, error: String(e) }; }
    const modelNames = (models.models || models.items || []).map(x => typeof x === "string" ? x : (x.name || x.model)).filter(Boolean);
    kv($("system-details"), [
      ["OLLAMA", models.available === false ? "OPTIONAL / OFFLINE" : "AVAILABLE"],
      ["MODELS", modelNames.length ? modelNames.join(", ") : "RUNTIME DISCOVERY"],
      ["AGENTS", agents.available === false ? "OPTIONAL / OFFLINE" : (agents.mode || agents.state || "BOUNDED TEAM")],
      ["CORE OWNERSHIP", "UNCHANGED / DETERMINISTIC"], ["TRANSACTIONS", "DISABLED"]
    ]);
    $("system-error").textContent = models.error || agents.error || "";
  }

  async function ensureCore() {
    if (coreStarting) return;
    coreStarting = true;
    try { await invoke("ensure_core_running"); } finally { coreStarting = false; }
  }

  async function refresh() {
    try {
      const [pipeline, research, evidence, attention] = await Promise.all([
        api("/api/pipeline"), api("/api/research"), api("/api/evidence"), api("/api/attention?limit=40")
      ]);
      $("core-dot").classList.add("live");
      $("core-state").textContent = "CORE LIVE";
      renderPipeline(pipeline); renderResearch(research); renderEvidence(evidence); await renderAttention(attention);
      $("last-update").textContent = `UPDATED ${new Date().toLocaleTimeString()}`;
    } catch (err) {
      $("core-dot").classList.remove("live");
      $("core-state").textContent = "CORE STARTING";
      $("last-update").textContent = String(err).slice(0, 90);
      await ensureCore();
    }
  }

  async function refreshAutostart() {
    try { const enabled = await invoke("autostart_status"); $("autostart-btn").textContent = `AUTOSTART ${enabled ? "ON" : "OFF"}`; } catch (_) {}
  }

  function setupDragging() {
    if (compact) return;
    let z = 40;
    document.querySelectorAll(".desk-window").forEach((win) => {
      const bar = win.querySelector(".window-bar");
      win.addEventListener("pointerdown", () => { document.querySelectorAll(".desk-window").forEach(x => x.classList.remove("active")); win.classList.add("active"); win.style.zIndex = String(++z); });
      bar.addEventListener("pointerdown", (ev) => {
        if (ev.button !== 0) return;
        const box = win.getBoundingClientRect(), parent = $("workspace").getBoundingClientRect();
        const dx = ev.clientX - box.left, dy = ev.clientY - box.top;
        bar.setPointerCapture(ev.pointerId);
        const move = (e) => {
          const left = Math.max(0, Math.min(parent.width - 120, e.clientX - parent.left - dx));
          const top = Math.max(0, Math.min(parent.height - 50, e.clientY - parent.top - dy));
          win.style.left = `${left}px`; win.style.top = `${top}px`; win.style.right = "auto"; win.style.bottom = "auto";
        };
        const up = () => { bar.removeEventListener("pointermove", move); bar.removeEventListener("pointerup", up); };
        bar.addEventListener("pointermove", move); bar.addEventListener("pointerup", up);
      });
    });
  }

  $("compact-btn")?.addEventListener("click", () => invoke("toggle_compact"));
  $("hide-btn")?.addEventListener("click", () => compact ? invoke("toggle_compact") : invoke("hide_workstation"));
  $("autostart-btn")?.addEventListener("click", async () => {
    const current = await invoke("autostart_status");
    const result = await invoke("set_autostart", { enabled: !current });
    $("autostart-btn").textContent = `AUTOSTART ${result ? "ON" : "OFF"}`;
  });

  setupDragging();
  refreshAutostart();
  refresh();
  renderSystem();
  setInterval(refresh, 2200);
  setInterval(renderSystem, 15000);
})();
