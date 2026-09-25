(function () {
  "use strict";

  const STORAGE_KEY = "cintexa_bi_api_base";
  const TASKS_KEY = "cintexa_bi_tasks";

  const AGENTS = [
    { id: "orchestrator", name: "Orchestrator", role: "Task planning & synthesis" },
    { id: "strategy", name: "Executive Strategy", role: "Strategic plans & SMART goals" },
    { id: "intelligence", name: "Business Intelligence", role: "KPIs, trends, segmentation" },
    { id: "diagnostic", name: "Business Diagnostic", role: "Health score across 10 pillars" },
    { id: "market", name: "Market Intelligence", role: "Industry, demand, trends" },
    { id: "competitor", name: "Competitor Research", role: "Evidence-based profiles" },
    { id: "research", name: "Research", role: "General research, source grades A–D" },
    { id: "decision", name: "Decision Support", role: "Options & risks — informs only" },
    { id: "forecasting", name: "Forecasting", role: "Forecasts with uncertainty bands" },
    { id: "knowledge", name: "Knowledge Manager", role: "Indexing, versioning, retrieval" },
    { id: "memory", name: "Memory", role: "Short / working / long-term memory" },
    { id: "quality", name: "Quality Assurance", role: "Final gate before user output" },
  ];

  const SCENARIOS = [
    "Assess my business health",
    "Analyse my market",
    "Research my competitors",
    "Analyse my sales performance",
    "Forecast my next 12 months of revenue",
    "Create a strategic growth plan",
    "Compare two strategic options",
    "Create an executive report from my business data",
    "Research this industry and identify documented opportunities and risks",
  ];

  function $(sel) { return document.querySelector(sel); }
  function $all(sel) { return Array.from(document.querySelectorAll(sel)); }

  function getApiBase() {
    return (localStorage.getItem(STORAGE_KEY) || "").replace(/\/$/, "");
  }

  function setApiBase(url) {
    localStorage.setItem(STORAGE_KEY, (url || "").replace(/\/$/, ""));
  }

  function headers() {
    return {
      "Content-Type": "application/json",
      "X-Organisation-Id": $("#orgId").value.trim() || "demo-org",
      "X-User-Id": $("#userId").value.trim() || "demo-user",
    };
  }

  async function api(path, options = {}) {
    const base = getApiBase();
    if (!base) {
      throw new Error("Set an API base URL in Settings first.");
    }
    const res = await fetch(base + path, {
      ...options,
      headers: { ...headers(), ...(options.headers || {}) },
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(res.status + " " + text.slice(0, 200));
    }
    return res.json();
  }

  function loadTasks() {
    try {
      return JSON.parse(localStorage.getItem(TASKS_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveTask(task) {
    const list = loadTasks();
    list.unshift(task);
    localStorage.setItem(TASKS_KEY, JSON.stringify(list.slice(0, 30)));
    renderTasks();
    const count = loadTasks().length;
    $("#taskCount").textContent = String(count);
    const cardCount = $("#taskCountCard");
    if (cardCount && window.CintexaMotion) window.CintexaMotion.countUp(cardCount, count, { duration: 500 });
    else if (cardCount) cardCount.textContent = String(count);
  }

  function showView(name) {
    $all(".view").forEach((v) => v.classList.remove("active"));
    $all(".nav-item").forEach((n) => n.classList.remove("active"));
    const view = $("#view-" + name);
    if (view) view.classList.add("active");
    const nav = document.querySelector('.nav-item[data-view="' + name + '"]');
    if (nav) nav.classList.add("active");
    const titles = {
      overview: "Overview",
      request: "New request",
      agents: "Agents",
      tasks: "Tasks",
      diagnostics: "Diagnostics",
      forecasts: "Forecasts",
      reports: "Reports",
      settings: "Settings",
    };
    $("#viewTitle").textContent = titles[name] || name;
  }

  function renderAgents() {
    const grid = $("#agentGrid");
    grid.innerHTML = AGENTS.map(
      (a) =>
        `<article class="card agent-card tilt">
          <h3>${a.name}</h3>
          <div class="role">${a.role}</div>
          <div class="desc">agent_id: <code>${a.id}</code></div>
        </article>`
    ).join("");
  }

  function renderAgentOrbit() {
    const host = $("#agentOrbit");
    if (!host || !window.CintexaMotion) return;
    window.CintexaMotion.orbit(
      host,
      AGENTS.map((a) => ({ label: a.name, sub: a.role })),
      {
        radius: Math.min(170, Math.max(120, host.clientWidth / 3.2)),
        speed: 0.012,
        onSelect: (item, i) => {
          const a = AGENTS[i];
          window.CintexaMotion.toast(a.name + " — " + a.role, "info");
        },
      }
    );
  }

  function renderScenarios() {
    const el = $("#scenarioList");
    el.innerHTML = SCENARIOS.map(
      (s) => `<button type="button" data-scenario="${s.replace(/"/g, "&quot;")}">${s}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#requestText").value = btn.getAttribute("data-scenario");
        showView("request");
      });
    });
  }

  function renderTasks() {
    const list = loadTasks();
    const el = $("#taskList");
    if (!list.length) {
      el.innerHTML = '<p class="muted">No tasks yet in this session.</p>';
      return;
    }
    el.innerHTML = list
      .map(
        (t) =>
          `<div class="task-item">
            <strong>${t.task_id || "task"}</strong>
            <span class="chip ${t.state === "COMPLETED" ? "ok" : "warn"}">${t.state || "?"}</span>
            <div class="muted small">${(t.request || "").slice(0, 120)}</div>
          </div>`
      )
      .join("");
  }

  async function pingApi() {
    const statusText = $("#apiStatusText");
    const pulseDot = $("#pulseDot");
    const statusCard = $("#apiStatusCard");
    const base = getApiBase();
    if (!base) {
      if (statusText) statusText.textContent = "API: not configured";
      if (pulseDot) pulseDot.classList.remove("live");
      if (statusCard) statusCard.textContent = "Not configured";
      return;
    }
    try {
      const res = await fetch(base + "/health");
      if (!res.ok) throw new Error("bad status");
      const data = await res.json();
      if (statusText) statusText.textContent = "API: " + (data.status || "ok");
      if (pulseDot) pulseDot.classList.add("live");
      if (statusCard) statusCard.textContent = "Connected";
      if (data.agents) {
        const el = $("#agentCountCard");
        if (el && window.CintexaMotion) window.CintexaMotion.countUp(el, data.agents.length, { duration: 700 });
      }
    } catch (e) {
      if (statusText) statusText.textContent = "API: unreachable";
      if (pulseDot) pulseDot.classList.remove("live");
      if (statusCard) statusCard.textContent = "Unreachable";
    }
  }

  function setHealthScore(score) {
    const el = $("#healthScore");
    if (!el || score == null) return;
    if (window.CintexaMotion) {
      window.CintexaMotion.countUp(el, score, { duration: 900, suffix: "/100" });
    } else {
      el.textContent = score + "/100";
    }
  }

  let lastEventTs = null;
  async function pollEvents() {
    const host = $("#eventFeed");
    if (!host || !getApiBase()) return;
    try {
      const events = await api("/bi/events?limit=12");
      if (!events.length) {
        host.innerHTML = '<div class="event-empty">No events yet — run a request to see live activity.</div>';
        return;
      }
      host.innerHTML = events
        .slice()
        .reverse()
        .map((e) => {
          const t = e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : "";
          return `<div class="event-row"><span class="event-type">${e.event_type}</span><span class="event-time">${t}</span></div>`;
        })
        .join("");
      const newest = events[events.length - 1];
      if (newest && newest.timestamp && newest.timestamp !== lastEventTs) {
        lastEventTs = newest.timestamp;
      }
    } catch (e) {
      // Silent — events are a nice-to-have, not core functionality.
    }
  }

  function parseJsonField(el, fallback) {
    const raw = el.value.trim();
    if (!raw) return fallback;
    return JSON.parse(raw);
  }

  async function submitRequest() {
    const status = $("#submitStatus");
    const resultCard = $("#resultCard");
    const resultBody = $("#resultBody");
    const resultMeta = $("#resultMeta");
    status.textContent = "Running…";
    resultCard.classList.add("hidden");

    try {
      const context = {};
      const industry = $("#reqIndustry").value.trim();
      const geo = $("#reqGeo").value.trim();
      if (industry) context.industry = industry;
      if (geo) context.geography = geo;
      try {
        context.metrics = parseJsonField($("#reqMetrics"), undefined);
      } catch {
        throw new Error("Metrics JSON is invalid");
      }
      try {
        const series = parseJsonField($("#reqSeries"), undefined);
        if (series) context.historical_series = series;
      } catch {
        throw new Error("Series JSON is invalid");
      }

      const body = {
        request: $("#requestText").value.trim(),
        organisation_id: $("#orgId").value.trim() || "demo-org",
        user_id: $("#userId").value.trim() || "demo-user",
        priority: "high",
        context,
      };
      if (!body.request) throw new Error("Enter a request");

      const data = await api("/bi/tasks", { method: "POST", body: JSON.stringify(body) });
      saveTask(data);
      resultMeta.innerHTML =
        `<span class="chip">task: ${data.task_id || "—"}</span>` +
        `<span class="chip ${data.state === "COMPLETED" ? "ok" : "warn"}">${data.state || ""}</span>` +
        `<span class="chip">objective: ${data.objective || "—"}</span>`;
      resultBody.textContent = JSON.stringify(data, null, 2);
      resultCard.classList.remove("hidden");
      status.textContent = "Done";
      if (window.CintexaMotion) window.CintexaMotion.toast("Request completed — " + (data.objective || data.state), data.state === "COMPLETED" ? "ok" : "info");
      if (data.results && data.results.diagnostic && data.results.diagnostic.findings) {
        const score = data.results.diagnostic.findings.overall_score;
        if (score != null) setHealthScore(score);
      }
    } catch (e) {
      status.textContent = e.message || String(e);
      resultBody.textContent = String(e);
      resultCard.classList.remove("hidden");
      if (window.CintexaMotion) window.CintexaMotion.toast(e.message || String(e), "err");
    }
  }

  async function runDiagnostic() {
    const out = $("#diagResult");
    out.classList.remove("hidden");
    out.textContent = "Running…";
    try {
      const metrics = parseJsonField($("#diagMetrics"), {});
      const data = await api("/bi/diagnostics", {
        method: "POST",
        body: JSON.stringify({ metrics }),
      });
      out.textContent = JSON.stringify(data, null, 2);
      if (data.diagnostic && data.diagnostic.findings && data.diagnostic.findings.overall_score != null) {
        setHealthScore(data.diagnostic.findings.overall_score);
      }
      if (data.task_id) saveTask({ task_id: data.task_id, state: data.state, request: "diagnostic" });
      if (window.CintexaMotion) {
        const approved = data.qa && data.qa.qa_result === "APPROVED";
        window.CintexaMotion.toast("Diagnostic complete — QA " + (data.qa ? data.qa.qa_result : "pending"), approved ? "ok" : "info");
      }
      pollEvents();
    } catch (e) {
      out.textContent = String(e);
      if (window.CintexaMotion) window.CintexaMotion.toast(String(e), "err");
    }
  }

  async function runForecast() {
    const out = $("#fcResult");
    out.classList.remove("hidden");
    out.textContent = "Running…";
    try {
      const series = parseJsonField($("#fcSeries"), null);
      if (!series) throw new Error("Provide historical_series JSON");
      const data = await api("/bi/forecasts", {
        method: "POST",
        body: JSON.stringify({
          metric: $("#fcMetric").value.trim() || "revenue",
          historical_series: series,
          horizon_months: Number($("#fcHorizon").value) || 12,
        }),
      });
      out.textContent = JSON.stringify(data, null, 2);
      if (data.task_id) saveTask({ task_id: data.task_id, state: data.state, request: "forecast" });
      if (window.CintexaMotion) window.CintexaMotion.toast("Forecast generated for " + ($("#fcMetric").value.trim() || "revenue"), "ok");
      pollEvents();
    } catch (e) {
      out.textContent = String(e);
      if (window.CintexaMotion) window.CintexaMotion.toast(String(e), "err");
    }
  }

  async function generateReport() {
    const status = $("#reportStatus");
    const out = $("#reportResult");
    const format = $("#reportFormat").value;
    let taskId = $("#reportTaskId").value.trim();
    if (!taskId) {
      const tasks = loadTasks();
      if (!tasks.length) {
        status.textContent = "No tasks yet — run a request first, or enter a Task ID.";
        return;
      }
      taskId = tasks[0].task_id;
      $("#reportTaskId").value = taskId;
    }
    status.textContent = "Generating…";
    out.classList.remove("hidden");
    out.textContent = "";
    try {
      const data = await api("/bi/reports", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId, format }),
      });
      if (format === "json") {
        out.textContent = JSON.stringify(data, null, 2);
      } else {
        out.textContent = data.content || JSON.stringify(data, null, 2);
      }
      status.textContent = "Done.";
      if (window.CintexaMotion) window.CintexaMotion.toast("Report generated (" + format + ")", "ok");
    } catch (e) {
      out.textContent = String(e);
      status.textContent = "Failed.";
      if (window.CintexaMotion) window.CintexaMotion.toast(String(e), "err");
    }
  }

  function initMotion() {
    if (!window.CintexaMotion) return;
    window.CintexaMotion.spawnParticles("particles");
    const stageCtl = window.CintexaMotion.initStage(".stage");
    window.CintexaMotion.initTilt(".tilt, .btn.primary, .nav-item");
    document.addEventListener("pointerdown", () => stageCtl.enableGyro(), { once: true });
  }

  function initCommandPalette() {
    if (!window.CintexaMotion) return;
    const views = ["overview", "request", "agents", "tasks", "diagnostics", "forecasts", "reports", "settings"];
    const cmdk = window.CintexaMotion.commandPalette({
      commands: [
        ...views.map((v) => ({
          id: "view-" + v,
          label: "Go to " + v[0].toUpperCase() + v.slice(1),
          hint: "view",
          run: () => showView(v),
        })),
        { id: "run-diag", label: "Run diagnostic", hint: "action", run: () => { showView("diagnostics"); runDiagnostic(); } },
        { id: "run-fc", label: "Run forecast", hint: "action", run: () => { showView("forecasts"); runForecast(); } },
        { id: "gen-report", label: "Generate report", hint: "action", run: () => { showView("reports"); generateReport(); } },
        { id: "ping", label: "Test API connection", hint: "action", run: pingApi },
        { id: "open-chat", label: "Open chat", hint: "navigate", run: () => (window.location.href = "index.html") },
        ...AGENTS.map((a) => ({ id: "agent-" + a.id, label: a.name, hint: a.role, run: () => { showView("agents"); window.CintexaMotion.toast(a.name + " — " + a.role, "info"); } })),
      ],
    });
    $("#btnCmdk")?.addEventListener("click", cmdk.open);
  }

  function bind() {
    $all(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => showView(btn.dataset.view));
    });
    $all("[data-goto]").forEach((btn) => {
      btn.addEventListener("click", () => showView(btn.getAttribute("data-goto")));
    });
    $("#btnSubmit").addEventListener("click", submitRequest);
    $("#btnDiag").addEventListener("click", runDiagnostic);
    $("#btnForecast").addEventListener("click", runForecast);
    $("#btnGenerateReport").addEventListener("click", generateReport);
    $("#btnSaveApi").addEventListener("click", () => {
      setApiBase($("#apiBase").value.trim());
      $("#settingsMsg").textContent = "Saved.";
      if (window.CintexaMotion) window.CintexaMotion.toast("API base URL saved", "ok");
      pingApi();
    });
    $("#btnPing").addEventListener("click", () => {
      pingApi().then(() => {
        $("#settingsMsg").textContent = "Ping finished — see status in the sidebar.";
      });
    });

    const saved = getApiBase();
    if (saved) $("#apiBase").value = saved;
    $("#taskCount").textContent = String(loadTasks().length);
  }

  renderAgents();
  renderAgentOrbit();
  renderScenarios();
  renderTasks();
  bind();
  initMotion();
  initCommandPalette();
  pingApi();
  pollEvents();
  setInterval(pollEvents, 6000);
})();
