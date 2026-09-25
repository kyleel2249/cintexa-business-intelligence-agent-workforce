(function () {
  "use strict";

  const KEY_STORAGE = "cintexa_llm_api_key";
  const TASKS_KEY = "cintexa_bi_tasks_v2";

  const TITLES = {
    overview: "Overview",
    request: "New request",
    agents: "Agents",
    diagnostics: "Diagnostics",
    market: "Market intelligence",
    competitors: "Competitors",
    forecasts: "Forecasts",
    decisions: "Decision support",
    reports: "Reports",
    tasks: "Activity",
    settings: "Settings",
  };

  const AGENTS = [
    { id: "orchestrator", name: "Orchestrator", role: "Task planning & synthesis" },
    { id: "strategy", name: "Executive Strategy", role: "Strategic plans & SMART goals" },
    { id: "intelligence", name: "Business Intelligence", role: "KPIs, trends, segmentation" },
    { id: "diagnostic", name: "Business Diagnostic", role: "Health across core pillars" },
    { id: "market", name: "Market Intelligence", role: "Industry, demand, trends" },
    { id: "competitor", name: "Competitor Research", role: "Evidence-based profiles" },
    { id: "research", name: "Research", role: "Source-graded research" },
    { id: "decision", name: "Decision Support", role: "Options & risks — informs only" },
    { id: "forecasting", name: "Forecasting", role: "Forecasts with uncertainty" },
    { id: "knowledge", name: "Knowledge Manager", role: "Indexing & retrieval" },
    { id: "memory", name: "Memory", role: "Working & long-term context" },
    { id: "quality", name: "Quality Assurance", role: "Final gate before output" },
  ];

  const SCENARIOS = [
    "Assess my business health",
    "Analyse my market opportunity",
    "Research my main competitors",
    "Forecast the next 12 months of revenue",
    "Create a 12-month growth strategy",
    "Compare expand vs deepen as strategic options",
    "Draft an executive brief on growth readiness",
  ];

  const $ = (s) => document.querySelector(s);
  const $all = (s) => Array.from(document.querySelectorAll(s));

  function getApiKey() {
    try {
      return sessionStorage.getItem(KEY_STORAGE) || "";
    } catch {
      return "";
    }
  }

  function setApiKey(key) {
    try {
      if (key) sessionStorage.setItem(KEY_STORAGE, key);
      else sessionStorage.removeItem(KEY_STORAGE);
    } catch (_) {}
  }

  function loadTasks() {
    try {
      return JSON.parse(localStorage.getItem(TASKS_KEY) || "[]");
    } catch {
      return [];
    }
  }

  function saveTask(entry) {
    const list = loadTasks();
    list.unshift({
      id: entry.id || "RUN-" + Date.now(),
      tool: entry.tool || "request",
      title: entry.title || "Run",
      at: new Date().toISOString(),
      preview: (entry.preview || "").slice(0, 180),
    });
    localStorage.setItem(TASKS_KEY, JSON.stringify(list.slice(0, 50)));
    renderTasks();
    renderOverview();
  }

  function simpleMarkdown(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/^### (.+)$/gm, "<h4>$1</h4>")
      .replace(/^## (.+)$/gm, "<h3>$1</h3>")
      .replace(/^# (.+)$/gm, "<h3>$1</h3>")
      .replace(/^- (.+)$/gm, "• $1")
      .replace(/\n/g, "<br>");
  }

  function showResult(el, text, isError) {
    el.classList.remove("hidden");
    el.classList.add("rich");
    if (isError) {
      el.textContent = text;
    } else {
      el.innerHTML = simpleMarkdown(text);
    }
  }

  async function biChat(prompt) {
    const key = getApiKey();
    if (!key) {
      throw new Error("Add your API key in Settings (OpenRouter sk-or-v1-… recommended).");
    }
    const res = await fetch("/bi/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-LLM-Api-Key": key,
      },
      body: JSON.stringify({ message: prompt }),
    });
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error(res.status + " error");
    }
    if (!res.ok) {
      throw new Error(data.detail || data.message || res.status + " error");
    }
    return data.message?.content || data.content || JSON.stringify(data);
  }

  function showView(name) {
    $all(".view").forEach((v) => v.classList.remove("active"));
    $all(".nav-item").forEach((n) => n.classList.toggle("active", n.dataset.view === name));
    const view = $("#view-" + name);
    if (view) view.classList.add("active");
    $("#viewTitle").textContent = TITLES[name] || name;
  }

  function renderAgents() {
    const grid = $("#agentGrid");
    if (!grid) return;
    grid.innerHTML = AGENTS.map(
      (a) =>
        `<div class="agent-card"><span class="agent-dot"></span><div><h4>${a.name}</h4><p>${a.role}</p></div></div>`
    ).join("");
  }

  function renderScenarios() {
    const host = $("#scenarioList");
    if (!host) return;
    host.innerHTML = SCENARIOS.map(
      (s) => `<button type="button" data-scenario="${s.replace(/"/g, "&quot;")}">${s}</button>`
    ).join("");
    host.querySelectorAll("button").forEach((btn) => {
      btn.addEventListener("click", () => {
        $("#reqText").value = btn.getAttribute("data-scenario");
        showView("request");
        $("#reqText").focus();
      });
    });
  }

  function renderTasks() {
    const list = loadTasks();
    const host = $("#taskList");
    const overview = $("#overviewTasks");
    const html =
      list.length === 0
        ? '<p class="empty">No activity yet.</p>'
        : list
            .map(
              (t) =>
                `<div class="task-row"><span class="badge ok">${t.tool}</span><div style="flex:1;min-width:0"><strong>${escapeHtml(
                  t.title
                )}</strong><div class="muted" style="font-size:0.78rem">${new Date(
                  t.at
                ).toLocaleString()} — ${escapeHtml(t.preview)}</div></div></div>`
            )
            .join("");
    if (host) host.innerHTML = html;
    if (overview) {
      overview.innerHTML =
        list.length === 0
          ? '<p class="empty">No runs yet — use a tool to begin.</p>'
          : list
              .slice(0, 5)
              .map(
                (t) =>
                  `<div class="task-row"><span class="badge">${t.tool}</span><span>${escapeHtml(
                    t.title
                  )}</span></div>`
              )
              .join("");
    }
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function renderOverview() {
    $("#kpiAgents").textContent = String(AGENTS.length);
    $("#kpiTasks").textContent = String(loadTasks().length);
    $("#kpiKey").textContent = getApiKey() ? "Set" : "Not set";
  }

  async function pingApi() {
    const el = $("#apiStatus");
    const kpi = $("#kpiApi");
    try {
      const res = await fetch("/health");
      if (!res.ok) throw new Error("offline");
      el.textContent = "Online";
      el.className = "status-pill ok";
      if (kpi) kpi.textContent = "OK";
    } catch {
      el.textContent = "Offline";
      el.className = "status-pill err";
      if (kpi) kpi.textContent = "—";
    }
  }

  async function runTool(opts) {
    const { button, resultEl, tool, title, prompt } = opts;
    if (button) button.disabled = true;
    resultEl.classList.remove("hidden");
    resultEl.textContent = "Running…";
    try {
      const text = await biChat(prompt);
      showResult(resultEl, text, false);
      saveTask({ tool, title, preview: text });
    } catch (e) {
      showResult(resultEl, String(e.message || e), true);
    } finally {
      if (button) button.disabled = false;
    }
  }

  function bind() {
    $all(".nav-item").forEach((btn) => {
      btn.addEventListener("click", () => showView(btn.dataset.view));
    });
    $all("[data-goto]").forEach((btn) => {
      btn.addEventListener("click", () => showView(btn.getAttribute("data-goto")));
    });

    $("#btnRefresh")?.addEventListener("click", () => {
      renderOverview();
      renderTasks();
      pingApi();
    });

    $("#btnSubmit")?.addEventListener("click", () => {
      const text = ($("#reqText").value || "").trim();
      if (!text) return;
      runTool({
        button: $("#btnSubmit"),
        resultEl: $("#reqResult"),
        tool: "request",
        title: text.slice(0, 60),
        prompt:
          "You are CINTEXA Business Intelligence. Structure a professional analysis for this request. Use sections: Summary, Findings, Risks, Recommendations, Open data gaps. Never invent metrics.\n\nRequest:\n" +
          text,
      });
    });

    $("#btnDiag")?.addEventListener("click", () => {
      const name = ($("#diagName").value || "").trim() || "the business";
      const industry = ($("#diagIndustry").value || "").trim();
      const ctx = ($("#diagContext").value || "").trim();
      runTool({
        button: $("#btnDiag"),
        resultEl: $("#diagResult"),
        tool: "diagnostic",
        title: "Diagnostic · " + name,
        prompt: `Run a business diagnostic for ${name}${industry ? " in " + industry : ""}.
Cover pillars: Strategy, Customers, Product, Operations, Finance, Talent, Go-to-market, Technology, Risk, Leadership.
For each pillar: status (Strong / Adequate / Weak / Unknown), evidence from user input only, and one improvement.
End with an overall readiness view and priority actions.
User context:
${ctx || "(none provided — mark unknowns clearly)"}`,
      });
    });

    $("#btnMarket")?.addEventListener("click", () => {
      const m = ($("#mktName").value || "").trim();
      if (!m) return;
      const focus = ($("#mktFocus").value || "").trim();
      runTool({
        button: $("#btnMarket"),
        resultEl: $("#mktResult"),
        tool: "market",
        title: "Market · " + m,
        prompt: `Market intelligence brief for: ${m}
Focus: ${focus || "structure, demand, segments, barriers"}
Rules: do not invent market size or growth rates. Mark unavailable data. Sections: Market definition, Customer segments, Demand drivers, Barriers, Competitive structure, Open questions.`,
      });
    });

    $("#btnComp")?.addEventListener("click", () => {
      const self = ($("#compSelf").value || "").trim() || "our business";
      const list = ($("#compList").value || "").trim();
      if (!list) return;
      const dims = ($("#compDims").value || "").trim();
      runTool({
        button: $("#btnComp"),
        resultEl: $("#compResult"),
        tool: "competitors",
        title: "Competitors",
        prompt: `Competitor research for ${self} vs: ${list}
Dimensions: ${dims || "positioning, ICP, pricing model, strengths, gaps"}
Evidence-first. No invented market share. Table-style comparison where useful. Note unknowns.`,
      });
    });

    $("#btnForecast")?.addEventListener("click", () => {
      const metric = ($("#fcMetric").value || "revenue").trim();
      const horizon = $("#fcHorizon").value || "12";
      const series = ($("#fcSeries").value || "").trim();
      const assumptions = ($("#fcAssumptions").value || "").trim();
      runTool({
        button: $("#btnForecast"),
        resultEl: $("#fcResult"),
        tool: "forecast",
        title: "Forecast · " + metric,
        prompt: `Build a ${horizon}-month forecast for metric: ${metric}
Historical series / description: ${series || "not provided"}
Assumptions: ${assumptions || "none stated"}
Output: method, base case path, low/high uncertainty bands, key drivers, and what would change the outlook. Do not invent precise history if none was given.`,
      });
    });

    $("#btnDecision")?.addEventListener("click", () => {
      const title = ($("#decTitle").value || "").trim();
      if (!title) return;
      const options = ($("#decOptions").value || "").trim();
      const constraints = ($("#decConstraints").value || "").trim();
      runTool({
        button: $("#btnDecision"),
        resultEl: $("#decResult"),
        tool: "decision",
        title: "Decision · " + title.slice(0, 40),
        prompt: `Decision support (inform only — do not decide for the user).
Decision: ${title}
Options:
${options || "(not specified)"}
Constraints: ${constraints || "(not specified)"}
Structure: Option summary, Pros/cons, Risks, Information gaps, Suggested evaluation criteria.`,
      });
    });

    $("#btnReport")?.addEventListener("click", () => {
      const topic = ($("#repTopic").value || "").trim();
      if (!topic) return;
      const notes = ($("#repNotes").value || "").trim();
      runTool({
        button: $("#btnReport"),
        resultEl: $("#repResult"),
        tool: "report",
        title: "Report · " + topic.slice(0, 40),
        prompt: `Write a concise executive report on: ${topic}
Source notes:
${notes || "(none — state limitations)"}
Sections: Executive summary, Situation, Analysis, Risks, Recommendations, Open questions. British English. No fabricated numbers.`,
      });
    });

    $("#btnCopyReport")?.addEventListener("click", async () => {
      const el = $("#repResult");
      const text = el.innerText || el.textContent || "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        $("#settingsMsg") && ($("#settingsMsg").textContent = "");
        const btn = $("#btnCopyReport");
        const prev = btn.textContent;
        btn.textContent = "Copied";
        setTimeout(() => (btn.textContent = prev), 1200);
      } catch (_) {}
    });

    $("#btnSaveKey")?.addEventListener("click", () => {
      const key = ($("#apiKey").value || "").trim();
      setApiKey(key);
      $("#apiKey").value = "";
      $("#settingsMsg").textContent = key ? "Key saved for this session." : "Key cleared.";
      renderOverview();
    });

    $("#btnClearKey")?.addEventListener("click", () => {
      setApiKey("");
      $("#apiKey").value = "";
      $("#settingsMsg").textContent = "Key cleared.";
      renderOverview();
    });
  }

  renderAgents();
  renderScenarios();
  renderTasks();
  renderOverview();
  bind();
  pingApi();
})();
