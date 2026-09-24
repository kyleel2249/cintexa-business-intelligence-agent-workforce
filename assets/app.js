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
    $("#taskCount").textContent = String(loadTasks().length);
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
        `<article class="card agent-card">
          <h3>${a.name}</h3>
          <div class="role">${a.role}</div>
          <div class="desc">agent_id: <code>${a.id}</code></div>
        </article>`
    ).join("");
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
    const status = $("#apiStatus");
    const base = getApiBase();
    if (!base) {
      status.textContent = "API: not configured";
      status.className = "status-pill err";
      return;
    }
    try {
      const res = await fetch(base + "/health");
      if (!res.ok) throw new Error("bad status");
      const data = await res.json();
      status.textContent = "API: " + (data.status || "ok");
      status.className = "status-pill ok";
      if (data.agents) $("#agentCount").textContent = String(data.agents.length);
    } catch (e) {
      status.textContent = "API: unreachable";
      status.className = "status-pill err";
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
      if (data.results && data.results.diagnostic && data.results.diagnostic.findings) {
        const score = data.results.diagnostic.findings.overall_score;
        if (score != null) $("#healthScore").textContent = score + "/100";
      }
    } catch (e) {
      status.textContent = e.message || String(e);
      resultBody.textContent = String(e);
      resultCard.classList.remove("hidden");
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
        $("#healthScore").textContent = data.diagnostic.findings.overall_score + "/100";
      }
      if (data.task_id) saveTask({ task_id: data.task_id, state: data.state, request: "diagnostic" });
    } catch (e) {
      out.textContent = String(e);
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
    } catch (e) {
      out.textContent = String(e);
    }
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
    $("#btnSaveApi").addEventListener("click", () => {
      setApiBase($("#apiBase").value.trim());
      $("#settingsMsg").textContent = "Saved.";
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
  renderScenarios();
  renderTasks();
  bind();
  pingApi();
})();
