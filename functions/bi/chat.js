/**
 * Cloudflare Pages Function — POST /bi/chat
 * OpenRouter / OpenAI / Anthropic + web browse + memory + completion loop.
 */

const SYSTEM = `You are CINTEXA Business Intelligence, a coordinated multi-agent BI workforce.
You can use browsed web page text provided in context. Prefer evidence from those pages.
Rules:
- Never invent market statistics, competitor figures, financial numbers, or citations.
- If data is missing, say it is unavailable.
- British English. Clear executive tone.
- Use memory from prior conversation turns when relevant.
- When the user provides URLs, treat extracted page text as primary evidence.
- If you still need specific public URLs to finish, end with a single line:
NEED_URLS: https://example.com/a | https://example.com/b
- When the request is fully answered, do NOT emit NEED_URLS.
- Structure long answers with short sections when useful.`;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers":
        "Content-Type, X-LLM-Api-Key, Authorization, X-Organisation-Id, X-User-Id",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    },
  });
}

function newId(prefix) {
  return prefix + crypto.randomUUID();
}

function detectProvider(key) {
  if (!key) return "none";
  if (key.startsWith("sk-or-v1-") || key.startsWith("sk-or-")) return "openrouter";
  if (key.startsWith("sk-ant-")) return "anthropic";
  return "openai";
}

function extractUrls(text) {
  if (!text) return [];
  const re = /https?:\/\/[^\s\]\)"'<>]+/g;
  const found = text.match(re) || [];
  const out = [];
  for (let u of found) {
    u = u.replace(/[.,;:)]+$/, "");
    if (!out.includes(u)) out.push(u);
  }
  return out.slice(0, 10);
}

function stripHtml(html) {
  let s = String(html || "");
  s = s.replace(/<script[\s\S]*?<\/script>/gi, " ");
  s = s.replace(/<style[\s\S]*?<\/style>/gi, " ");
  s = s.replace(/<noscript[\s\S]*?<\/noscript>/gi, " ");
  const titleMatch = s.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? titleMatch[1].replace(/\s+/g, " ").trim() : "";
  s = s.replace(/<\/(p|div|h1|h2|h3|h4|li|tr|br)>/gi, "\n");
  s = s.replace(/<[^>]+>/g, " ");
  s = s.replace(/&nbsp;/g, " ").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
  s = s.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  return { title, text: s.slice(0, 20000) };
}

async function browseUrl(url) {
  try {
    const res = await fetch(url, {
      redirect: "follow",
      headers: {
        "User-Agent": "CINTEXA-BI/1.0 (+https://cintexa.com)",
        Accept: "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
      },
    });
    const ct = (res.headers.get("content-type") || "").toLowerCase();
    const buf = await res.arrayBuffer();
    const bytes = new Uint8Array(buf).slice(0, 1_200_000);
    const raw = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    if (!res.ok) {
      return { ok: false, url, status: res.status, error: "HTTP " + res.status };
    }
    if (ct.includes("application/json") || ct.includes("text/plain")) {
      return {
        ok: true,
        url: res.url || url,
        status: res.status,
        title: ct.includes("json") ? "JSON" : "Text",
        text: raw.slice(0, 20000),
      };
    }
    const { title, text } = stripHtml(raw);
    return {
      ok: true,
      url: res.url || url,
      status: res.status,
      title: title || url,
      text,
    };
  } catch (e) {
    return { ok: false, url, error: String(e && e.message ? e.message : e).slice(0, 300) };
  }
}

async function browseMany(urls) {
  const unique = [];
  for (const u of urls) {
    if (u && !unique.includes(u)) unique.push(u);
  }
  const pages = [];
  for (const u of unique.slice(0, 6)) {
    pages.push(await browseUrl(u));
  }
  return pages;
}

function formatPages(pages) {
  return pages
    .map((p, i) => {
      if (!p.ok) return `[Source ${i + 1}] FAILED ${p.url}: ${p.error || "error"}`;
      return `[Source ${i + 1}] ${p.title}\nURL: ${p.url}\n---\n${(p.text || "").slice(0, 9000)}\n---`;
    })
    .join("\n\n");
}

async function callOpenAICompatible(apiKey, messages, opts) {
  const headers = {
    Authorization: "Bearer " + apiKey,
    "Content-Type": "application/json",
  };
  if (opts.extraHeaders) Object.assign(headers, opts.extraHeaders);
  const res = await fetch(opts.url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: opts.model,
      temperature: 0.3,
      max_tokens: 2500,
      messages,
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(opts.label + " " + res.status + ": " + errText.slice(0, 400));
  }
  const data = await res.json();
  return (
    (data.choices &&
      data.choices[0] &&
      data.choices[0].message &&
      data.choices[0].message.content) ||
    ""
  );
}

async function callAnthropic(apiKey, system, messages) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2500,
      temperature: 0.3,
      system,
      messages: messages.filter((m) => m.role === "user" || m.role === "assistant"),
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error("Anthropic " + res.status + ": " + errText.slice(0, 400));
  }
  const data = await res.json();
  return (data.content || []).map((b) => b.text || "").filter(Boolean).join("\n");
}

async function llmChat(apiKey, provider, messages) {
  if (provider === "openrouter") {
    return callOpenAICompatible(apiKey, messages, {
      url: "https://openrouter.ai/api/v1/chat/completions",
      model: "openai/gpt-4o",
      label: "OpenRouter",
      extraHeaders: {
        "HTTP-Referer": "https://cintexa-business-intelligence-agent-workforce.pages.dev",
        "X-Title": "CINTEXA Business Intelligence",
      },
    });
  }
  if (provider === "anthropic") {
    const system = messages.find((m) => m.role === "system");
    const rest = messages.filter((m) => m.role !== "system");
    return callAnthropic(apiKey, (system && system.content) || SYSTEM, rest);
  }
  return callOpenAICompatible(apiKey, messages, {
    url: "https://api.openai.com/v1/chat/completions",
    model: "gpt-4o",
    label: "OpenAI",
  });
}

function parseNeedUrls(reply) {
  const line = (reply || "").split("\n").find((l) => l.trim().startsWith("NEED_URLS:"));
  if (!line) return [];
  const rest = line.replace(/^NEED_URLS:\s*/i, "");
  return extractUrls(rest.replace(/\|/g, " "));
}

export async function onRequest(context) {
  const { request } = context;
  if (request.method === "OPTIONS") return json({ ok: true });
  if (request.method !== "POST") {
    return json({ detail: "Use POST" }, 405);
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ detail: "Invalid JSON body" }, 400);
  }

  const message = (body.message || "").trim();
  if (!message) return json({ detail: "message is required" }, 400);

  const apiKey =
    (request.headers.get("X-LLM-Api-Key") || "").trim() ||
    (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();
  if (!apiKey) {
    return json(
      { detail: "Missing API key. Open Settings and paste OpenRouter (sk-or-v1-…), OpenAI, or Anthropic key." },
      401
    );
  }

  const provider = detectProvider(apiKey);
  const sessionId = body.session_id || newId("CHAT-");
  const taskId = newId("TASK-");
  const title = message.length > 48 ? message.slice(0, 48) + "…" : message;
  const prior = Array.isArray(body.messages) ? body.messages : [];

  // Collect URLs from user message, history, and optional body.urls
  let urlQueue = [
    ...extractUrls(message),
    ...(Array.isArray(body.urls) ? body.urls : []),
  ];
  for (const m of prior.slice(-12)) {
    if (m && m.content) urlQueue.push(...extractUrls(m.content));
  }
  // de-dupe
  urlQueue = [...new Set(urlQueue)].slice(0, 8);

  const browsed = [];
  if (urlQueue.length) {
    const pages = await browseMany(urlQueue);
    browsed.push(...pages);
  }

  const memoryBlock = prior
    .slice(-16)
    .map((m) => `${m.role}: ${(m.content || "").slice(0, 1500)}`)
    .join("\n");

  let browseBlock = browsed.length ? formatPages(browsed) : "(no pages fetched yet)";

  const baseMessages = () => {
    const msgs = [{ role: "system", content: SYSTEM }];
    if (memoryBlock) {
      msgs.push({
        role: "system",
        content: "Conversation memory (prior turns):\n" + memoryBlock.slice(0, 12000),
      });
    }
    msgs.push({
      role: "system",
      content: "Browsed page evidence:\n" + browseBlock.slice(0, 28000),
    });
    for (const m of prior.slice(-10)) {
      if (m.role === "user" || m.role === "assistant") {
        msgs.push({ role: m.role, content: m.content });
      }
    }
    msgs.push({ role: "user", content: message });
    return msgs;
  };

  try {
    let reply = "";
    let loops = 0;
    const maxLoops = 4;
    const allSources = [...browsed];

    while (loops < maxLoops) {
      loops += 1;
      reply = await llmChat(apiKey, provider, baseMessages());
      const need = parseNeedUrls(reply);
      if (!need.length) break;
      const fresh = need.filter((u) => !allSources.some((p) => p.url === u || (p.url && p.url.startsWith(u))));
      if (!fresh.length) {
        reply = reply.replace(/^NEED_URLS:.*$/gim, "").trim();
        reply +=
          "\n\n(Additional requested URLs were already fetched or could not be expanded further.)";
        break;
      }
      const more = await browseMany(fresh);
      allSources.push(...more);
      browseBlock = formatPages(allSources);
      // strip NEED_URLS from intermediate reply and continue loop
    }

    // Clean any residual control line
    reply = (reply || "").replace(/^NEED_URLS:.*$/gim, "").trim();

    const userMsg = {
      role: "user",
      content: message,
      timestamp: new Date().toISOString(),
    };
    const assistantMsg = {
      role: "assistant",
      content: reply,
      timestamp: new Date().toISOString(),
      task_id: taskId,
      meta: {
        sources: allSources.map((p) => ({
          url: p.url,
          ok: !!p.ok,
          title: p.title || null,
        })),
        loops,
        memory_turns: prior.length,
      },
    };

    return json({
      session_id: sessionId,
      title,
      message: assistantMsg,
      task_id: taskId,
      task_state: "COMPLETED",
      llm_provider: provider,
      sources: assistantMsg.meta.sources,
      messages: [...prior, userMsg, assistantMsg],
    });
  } catch (err) {
    return json(
      { detail: "Chat failed: " + (err && err.message ? err.message : String(err)) },
      502
    );
  }
}
