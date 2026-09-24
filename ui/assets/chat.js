(function () {
  "use strict";

  const KEYS = {
    api: "cintexa_api_base",
    org: "cintexa_org",
    user: "cintexa_user",
    sessions: "cintexa_chat_sessions_v1",
  };

  const SUGGESTIONS = [
    "Assess my business health",
    "Forecast next 12 months of revenue",
    "Create a 12-month growth strategy",
    "What should I know before expanding?",
  ];

  let sessionId = null;
  let busy = false;

  const $ = (s) => document.querySelector(s);

  function getApi() {
    return (localStorage.getItem(KEYS.api) || "").replace(/\/$/, "");
  }
  function getOrg() {
    return localStorage.getItem(KEYS.org) || "demo-org";
  }
  function getUser() {
    return localStorage.getItem(KEYS.user) || "demo-user";
  }

  function loadLocalSessions() {
    try {
      return JSON.parse(localStorage.getItem(KEYS.sessions) || "[]");
    } catch {
      return [];
    }
  }

  function saveLocalSession(session) {
    const list = loadLocalSessions().filter((s) => s.session_id !== session.session_id);
    list.unshift({
      session_id: session.session_id,
      title: session.title || "Chat",
      updated_at: session.updated_at || new Date().toISOString(),
      messages: session.messages || [],
    });
    localStorage.setItem(KEYS.sessions, JSON.stringify(list.slice(0, 40)));
    renderSessionList();
  }

  function headers() {
    return {
      "Content-Type": "application/json",
      "X-Organisation-Id": getOrg(),
      "X-User-Id": getUser(),
    };
  }

  async function api(path, opts = {}) {
    const base = getApi();
    if (!base) throw new Error("Set API base URL in Settings");
    const res = await fetch(base + path, {
      ...opts,
      headers: { ...headers(), ...(opts.headers || {}) },
    });
    if (!res.ok) {
      const t = await res.text();
      throw new Error(res.status + ": " + t.slice(0, 240));
    }
    return res.json();
  }

  function renderSuggestions() {
    const el = $("#suggestions");
    if (!el) return;
    el.innerHTML = SUGGESTIONS.map(
      (s) => `<button type="button" data-s="${s.replace(/"/g, "&quot;")}">${s}</button>`
    ).join("");
    el.querySelectorAll("button").forEach((b) => {
      b.addEventListener("click", () => {
        $("#input").value = b.getAttribute("data-s");
        $("#input").dispatchEvent(new Event("input"));
        $("#composer").requestSubmit();
      });
    });
  }

  function renderSessionList() {
    const list = loadLocalSessions();
    const el = $("#sessionList");
    if (!list.length) {
      el.innerHTML = '<p style="color:var(--muted);font-size:0.8rem;padding:0.5rem">No chats yet</p>';
      return;
    }
    el.innerHTML = list
      .map(
        (s) =>
          `<button type="button" class="session-item ${s.session_id === sessionId ? "active" : ""}" data-id="${s.session_id}">${escapeHtml(s.title || "Chat")}</button>`
      )
      .join("");
    el.querySelectorAll(".session-item").forEach((btn) => {
      btn.addEventListener("click", () => openSession(btn.getAttribute("data-id")));
    });
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function simpleMarkdown(text) {
    // Minimal safe formatting: **bold**, `code`, newlines already pre-wrap
    let s = escapeHtml(text);
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  }

  function appendMessage(role, content, meta) {
    const welcome = $("#welcome");
    if (welcome) welcome.remove();

    const row = document.createElement("div");
    row.className = "msg " + role;
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = role === "user" ? "You" : "C";
    const bubble = document.createElement("div");
    bubble.className = "bubble";
    const body = document.createElement("div");
    body.className = "content";
    body.innerHTML = simpleMarkdown(content);
    bubble.appendChild(body);
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      bubble.appendChild(m);
    }
    row.appendChild(avatar);
    row.appendChild(bubble);
    $("#messages").appendChild(row);
    $("#messages").scrollTop = $("#messages").scrollHeight;
    return row;
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "msg assistant";
    row.id = "typingRow";
    row.innerHTML =
      '<div class="avatar">C</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>';
    $("#messages").appendChild(row);
    $("#messages").scrollTop = $("#messages").scrollHeight;
  }

  function hideTyping() {
    const t = $("#typingRow");
    if (t) t.remove();
  }

  function newChat() {
    sessionId = null;
    $("#chatTitle").textContent = "CINTEXA BI";
    $("#messages").innerHTML = `
      <div class="welcome" id="welcome">
        <div class="welcome-icon">C</div>
        <h2>Business Intelligence workforce</h2>
        <p>Ask anything about your business — health, market, competitors, forecasts, strategy. Twelve specialist agents plan, research and QA the answer.</p>
        <div class="suggestions" id="suggestions"></div>
      </div>`;
    renderSuggestions();
    renderSessionList();
  }

  function openSession(id) {
    const list = loadLocalSessions();
    const s = list.find((x) => x.session_id === id);
    if (!s) return;
    sessionId = id;
    $("#chatTitle").textContent = s.title || "Chat";
    $("#messages").innerHTML = "";
    (s.messages || []).forEach((m) => {
      if (m.role === "user" || m.role === "assistant") {
        const meta =
          m.role === "assistant" && m.meta
            ? [m.meta.objective, m.meta.qa, m.meta.llm_provider].filter(Boolean).join(" · ")
            : null;
        appendMessage(m.role, m.content, meta);
      }
    });
    renderSessionList();
    $("#sidebar").classList.remove("open");
  }

  async function sendMessage(text) {
    if (busy || !text.trim()) return;
    busy = true;
    $("#btnSend").disabled = true;

    appendMessage("user", text.trim());
    $("#input").value = "";
    autoSize();
    showTyping();

    try {
      const body = {
        message: text.trim(),
        session_id: sessionId || undefined,
      };
      const data = await api("/bi/chat", {
        method: "POST",
        body: JSON.stringify(body),
      });

      hideTyping();
      sessionId = data.session_id;
      $("#chatTitle").textContent = data.title || "Chat";

      const meta = [
        data.task_state,
        data.message?.meta?.objective,
        data.message?.meta?.qa,
        data.llm_provider ? "LLM: " + data.llm_provider : null,
      ]
        .filter(Boolean)
        .join(" · ");

      appendMessage("assistant", data.message?.content || "No response", meta);

      saveLocalSession({
        session_id: data.session_id,
        title: data.title,
        updated_at: new Date().toISOString(),
        messages: data.messages || [],
      });
    } catch (err) {
      hideTyping();
      appendMessage(
        "assistant",
        "I could not complete that request.\n\n" + (err.message || String(err)) +
          "\n\nCheck Settings → API base URL, and that the API is running with CORS allowing this origin."
      );
    } finally {
      busy = false;
      updateSendState();
    }
  }

  function autoSize() {
    const ta = $("#input");
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  }

  function updateSendState() {
    $("#btnSend").disabled = busy || !$("#input").value.trim();
  }

  async function ping() {
    const el = $("#apiStatus");
    const badge = $("#llmBadge");
    const base = getApi();
    if (!base) {
      el.textContent = "API not configured — open Settings";
      el.className = "status-line err";
      badge.textContent = "LLM: —";
      return;
    }
    try {
      const res = await fetch(base + "/health");
      const data = await res.json();
      el.textContent = data.llm_available
        ? "API online · LLM " + (data.llm_provider || "ready")
        : "API online · add OPENAI_API_KEY for full chat synthesis";
      el.className = "status-line ok";
      badge.textContent = "LLM: " + (data.llm_provider || "none");
    } catch {
      el.textContent = "API unreachable";
      el.className = "status-line err";
      badge.textContent = "LLM: —";
    }
  }

  function openSettings() {
    $("#apiBase").value = getApi();
    $("#orgId").value = getOrg();
    $("#userId").value = getUser();
    $("#settingsModal").classList.remove("hidden");
  }

  function bind() {
    $("#composer").addEventListener("submit", (e) => {
      e.preventDefault();
      sendMessage($("#input").value);
    });
    $("#input").addEventListener("input", () => {
      autoSize();
      updateSendState();
    });
    $("#input").addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        $("#composer").requestSubmit();
      }
    });
    $("#btnNewChat").addEventListener("click", newChat);
    $("#btnOpenSettings").addEventListener("click", openSettings);
    $("#btnCloseSettings").addEventListener("click", () => $("#settingsModal").classList.add("hidden"));
    $("#btnSaveSettings").addEventListener("click", () => {
      localStorage.setItem(KEYS.api, ($("#apiBase").value || "").trim().replace(/\/$/, ""));
      localStorage.setItem(KEYS.org, ($("#orgId").value || "demo-org").trim());
      localStorage.setItem(KEYS.user, ($("#userId").value || "demo-user").trim());
      $("#settingsModal").classList.add("hidden");
      ping();
    });
    $("#btnToggleSidebar")?.addEventListener("click", () => {
      $("#sidebar").classList.toggle("open");
    });
    renderSuggestions();
    renderSessionList();
    updateSendState();
    ping();
  }

  bind();
})();
