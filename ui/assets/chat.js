(function () {
  "use strict";

  const KEY_STORAGE = "cintexa_llm_api_key";
  const SESSIONS_KEY = "cintexa_chat_sessions_v2";

  const SUGGESTIONS = [
    "Assess my business health",
    "Forecast next 12 months of revenue",
    "Create a 12-month growth strategy",
    "What should I know before expanding?",
  ];

  let sessionId = null;
  let busy = false;

  const $ = (s) => document.querySelector(s);

  /**
   * API root: same origin by default (when UI is served by FastAPI).
   * Optional one-time override: window.__CINTEXA_API__ = "https://your-api.example.com"
   * Users never configure this in Settings — only the secret API key.
   */
  function apiRoot() {
    if (typeof window !== "undefined" && window.__CINTEXA_API__) {
      return String(window.__CINTEXA_API__).replace(/\/$/, "");
    }
    return "";
  }

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

  function maskKey(key) {
    if (!key) return "not set";
    if (key.length < 12) return "set";
    return key.slice(0, 5) + "…" + key.slice(-4);
  }

  function updateKeyBadge() {
    const k = getApiKey();
    const badge = $("#keyBadge");
    if (badge) badge.textContent = "Key: " + maskKey(k);
  }

  function loadLocalSessions() {
    try {
      return JSON.parse(localStorage.getItem(SESSIONS_KEY) || "[]");
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
    localStorage.setItem(SESSIONS_KEY, JSON.stringify(list.slice(0, 40)));
    renderSessionList();
  }

  function headers() {
    const h = { "Content-Type": "application/json" };
    const key = getApiKey();
    if (key) h["X-LLM-Api-Key"] = key;
    return h;
  }

  async function api(path, opts = {}) {
    const res = await fetch(apiRoot() + path, {
      ...opts,
      headers: { ...headers(), ...(opts.headers || {}) },
    });
    if (!res.ok) {
      let msg = res.status + " error";
      try {
        const j = await res.json();
        if (j.detail) msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
      } catch (_) {
        try {
          msg = (await res.text()).slice(0, 200);
        } catch (__) {}
      }
      throw new Error(msg);
    }
    return res.json();
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function simpleMarkdown(text) {
    let s = escapeHtml(text);
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  }

  function renderSuggestions() {
    const el = $("#suggestions");
    if (!el) return;
    el.innerHTML = SUGGESTIONS.map(
      (s) => `<button type="button" data-s="${escapeHtml(s)}">${escapeHtml(s)}</button>`
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
        <p>Ask about business health, markets, competitors, forecasts or strategy. Twelve specialist agents plan the work and quality-check the answer.</p>
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
    if (!getApiKey()) {
      openSettings();
      appendMessage(
        "assistant",
        "Add your API key in Settings first (OpenAI recommended). The key stays in this browser only."
      );
      return;
    }

    busy = true;
    $("#btnSend").disabled = true;
    appendMessage("user", text.trim());
    $("#input").value = "";
    autoSize();
    showTyping();

    try {
      const data = await api("/bi/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text.trim(),
          session_id: sessionId || undefined,
        }),
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
        "I could not complete that request.\n\n" + (err.message || String(err))
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
    try {
      const res = await fetch(apiRoot() + "/health");
      if (!res.ok) throw new Error("bad");
      el.textContent = getApiKey() ? "Ready · key present" : "Online · add API key in Settings";
      el.className = "status-line ok";
    } catch {
      el.textContent = "API offline — run the server (uvicorn api.main:app)";
      el.className = "status-line err";
    }
    updateKeyBadge();
  }

  function openSettings() {
    $("#apiKey").value = getApiKey();
    $("#settingsModal").classList.remove("hidden");
    setTimeout(() => $("#apiKey").focus(), 50);
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
      const key = ($("#apiKey").value || "").trim();
      setApiKey(key);
      $("#apiKey").value = key;
      $("#settingsModal").classList.add("hidden");
      updateKeyBadge();
      ping();
    });
    $("#btnClearKey").addEventListener("click", () => {
      setApiKey("");
      $("#apiKey").value = "";
      updateKeyBadge();
      ping();
    });
    $("#btnToggleSidebar")?.addEventListener("click", () => {
      $("#sidebar").classList.toggle("open");
    });
    // Clear password field from DOM on page hide for slightly safer UX
    window.addEventListener("pagehide", () => {
      const inp = $("#apiKey");
      if (inp) inp.value = getApiKey();
    });
    renderSuggestions();
    renderSessionList();
    updateSendState();
    updateKeyBadge();
    ping();
  }

  bind();
})();
