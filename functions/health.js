/** Cloudflare Pages Function — GET /health */

export async function onRequest() {
  return new Response(
    JSON.stringify({
      status: "ok",
      service: "CINTEXA Business Intelligence",
      chat: true,
      runtime: "cloudflare_pages_function",
      server_llm_configured: false,
      note: "Edge health. Chat uses your X-LLM-Api-Key per request.",
    }),
    {
      status: 200,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
      },
    }
  );
}
