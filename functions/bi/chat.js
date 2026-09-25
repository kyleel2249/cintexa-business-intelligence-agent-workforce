/**
 * Cloudflare Pages Function — POST /bi/chat
 * Supports OpenRouter (sk-or-v1-…), OpenAI, and Anthropic (sk-ant-…).
 * Uses X-LLM-Api-Key only — never stored.
 */

const SYSTEM = `You are CINTEXA Business Intelligence, a coordinated multi-agent BI workforce.
You plan work across specialist roles (diagnostic, market, competitor, forecasting, strategy, decision, quality).
Rules:
- Never invent market statistics, competitor figures, financial numbers, or citations.
- If data is missing, say it is unavailable and ask for metrics or context.
- British English. Clear executive tone.
- Structure replies with short sections when useful (Summary, Findings, Risks, Recommendations).
- You inform decisions; you do not make irreversible decisions for the user.`;

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers":
        "Content-Type, X-LLM-Api-Key, Authorization, X-Organisation-Id, X-User-Id",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      ...extraHeaders,
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

async function callOpenAICompatible(apiKey, userMessage, history, opts) {
  const messages = [{ role: "system", content: SYSTEM }];
  for (const m of history || []) {
    if (m.role === "user" || m.role === "assistant") {
      messages.push({ role: m.role, content: m.content });
    }
  }
  messages.push({ role: "user", content: userMessage });

  const headers = {
    Authorization: "Bearer " + apiKey,
    "Content-Type": "application/json",
  };
  if (opts.extraHeaders) {
    Object.assign(headers, opts.extraHeaders);
  }

  const res = await fetch(opts.url, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model: opts.model,
      temperature: 0.35,
      max_tokens: 2000,
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

async function callAnthropic(apiKey, userMessage, history) {
  const messages = [];
  for (const m of history || []) {
    if (m.role === "user" || m.role === "assistant") {
      messages.push({ role: m.role, content: m.content });
    }
  }
  messages.push({ role: "user", content: userMessage });

  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": apiKey,
      "anthropic-version": "2023-06-01",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 2000,
      temperature: 0.35,
      system: SYSTEM,
      messages,
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error("Anthropic " + res.status + ": " + errText.slice(0, 400));
  }
  const data = await res.json();
  const parts = (data.content || []).map((b) => b.text || "").filter(Boolean);
  return parts.join("\n");
}

export async function onRequest(context) {
  const { request } = context;

  if (request.method === "OPTIONS") {
    return json({ ok: true });
  }

  if (request.method !== "POST") {
    return json(
      {
        detail:
          "Method not allowed. Use POST. Redeploy Pages with functions/ enabled if you see 405.",
      },
      405
    );
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return json({ detail: "Invalid JSON body" }, 400);
  }

  const message = (body.message || "").trim();
  if (!message) {
    return json({ detail: "message is required" }, 400);
  }

  const apiKey =
    (request.headers.get("X-LLM-Api-Key") || "").trim() ||
    (request.headers.get("Authorization") || "").replace(/^Bearer\s+/i, "").trim();

  if (!apiKey) {
    return json(
      {
        detail:
          "Missing API key. Open Settings and paste your OpenRouter (sk-or-v1-…), OpenAI, or Anthropic key.",
      },
      401
    );
  }

  const provider = detectProvider(apiKey);
  const sessionId = body.session_id || newId("CHAT-");
  const taskId = newId("TASK-");
  const title = message.length > 48 ? message.slice(0, 48) + "…" : message;
  const prior = Array.isArray(body.messages) ? body.messages : [];

  try {
    let reply;
    if (provider === "openrouter") {
      reply = await callOpenAICompatible(apiKey, message, prior, {
        url: "https://openrouter.ai/api/v1/chat/completions",
        model: "openai/gpt-4o",
        label: "OpenRouter",
        extraHeaders: {
          "HTTP-Referer":
            "https://cintexa-business-intelligence-agent-workforce.pages.dev",
          "X-Title": "CINTEXA Business Intelligence",
        },
      });
    } else if (provider === "anthropic") {
      reply = await callAnthropic(apiKey, message, prior);
    } else {
      reply = await callOpenAICompatible(apiKey, message, prior, {
        url: "https://api.openai.com/v1/chat/completions",
        model: "gpt-4o",
        label: "OpenAI",
      });
    }

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
        objective: "edge_chat",
        state: "COMPLETED",
        llm_provider: provider,
        qa: "APPROVED",
        runtime: "cloudflare_pages_function",
      },
    };

    return json({
      session_id: sessionId,
      title,
      message: assistantMsg,
      task_id: taskId,
      task_state: "COMPLETED",
      llm_provider: provider,
      messages: [...prior, userMsg, assistantMsg],
    });
  } catch (err) {
    return json(
      {
        detail: "Chat failed: " + (err && err.message ? err.message : String(err)),
      },
      502
    );
  }
}
