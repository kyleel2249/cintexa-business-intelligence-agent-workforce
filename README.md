# CINTEXA Business Intelligence Agent Workforce

**Production-ready multi-agent Business Intelligence department** — the first fully operational department within the CINTEXA multi-agent business operating system.

One coordinated workforce. Twelve specialist agents. Shared orchestration, evidence, memory, validation and reporting. Designed so later CINTEXA departments (Marketing, Sales, Finance, Operations, Creative Studio, etc.) can plug in without a major architectural rewrite.

---

## What this is

You submit one high-level business request. The **Orchestrator** decides which specialists are needed, which tools they may use, what evidence is required, what order the work runs in, and what returns to you after Quality Assurance.

Specialists never invent market statistics, competitor figures, financial numbers or citations. If information is unavailable it is marked unavailable. Every significant claim carries evidence IDs, confidence classification and source metadata.

## The twelve agents

| Agent ID | Name | Role |
|----------|------|------|
| `orchestrator` | CINTEXA Business Intelligence Orchestrator | Task planning, agent selection, state management, synthesis |
| `strategy` | Executive Strategy Agent | Strategic plans, SWOT/PESTLE/Porter, SMART goals, roadmaps |
| `intelligence` | Business Intelligence Agent | KPI analysis, trends, segmentation, dashboards |
| `diagnostic` | Business Diagnostic Agent | Business Health Score across 10 configurable pillars |
| `market` | Market Intelligence Agent | Industry, demand, trends, regulations, geographic factors |
| `competitor` | Competitor Research Agent | Evidence-based competitor profiles and comparisons |
| `research` | Research Agent | General research, source quality grading (A–D), cross-checking |
| `decision` | Decision Support Agent | Options, consequences, risks — informs, never decides for you |
| `forecasting` | Forecasting Agent | Data-supported forecasts with uncertainty ranges |
| `knowledge` | Knowledge Manager Agent | Indexing, versioning, stale detection, retrieval |
| `memory` | Memory Agent | Short-term / working / long-term / user-provided / derived memory |
| `quality` | Quality Assurance Agent | Factual, numerical, source, freshness, consistency and hallucination checks |

## Architecture (high level)

```
USER
  ↓
CINTEXA BI ORCHESTRATOR
  ↓
TASK PLANNER
  ↓
SPECIALIST AGENTS  ←→  TOOLS / DATA / KNOWLEDGE
  ↓
VALIDATION
  ↓
SYNTHESIS
  ↓
QUALITY ASSURANCE
  ↓
FINAL BUSINESS INTELLIGENCE OUTPUT
```

## Core systems

- **Shared Evidence System** — every claim references an evidence object (`evidence_id`, source, dates, confidence, classification).
- **Confidence System** — HIGH / MEDIUM / LOW / UNKNOWN with reason codes (MEASURED, ESTIMATED, INFERRED, USER_PROVIDED, EXTERNALLY_REPORTED, MODEL_GENERATED).
- **Task States** — PENDING → PLANNING → RUNNING → WAITING_* → VALIDATING → COMPLETED / FAILED / CANCELLED / PAUSED.
- **Agent Message Protocol** — structured inter-agent messages (request, response, handoff, clarification, warning, failure, approval_request, completion).
- **Human Approval Gates** — required for publishing, record changes, deletions, permission changes and irreversible actions.
- **Tool Permission System** — least-privilege, configurable per agent.
- **Event System** — `diagnostic.completed`, `research.completed`, `approval.required`, etc., ready for other CINTEXA departments to subscribe.
- **Organisation Isolation** — no cross-organisation data access.
- **Audit Logs** — operational traces, tool calls, evidence and results (no hidden chain-of-thought).

## Quick start

```bash
# Clone
git clone https://github.com/kyleel2249/cintexa-business-intelligence-agent-workforce.git
cd cintexa-business-intelligence-agent-workforce

# Python 3.11+ recommended
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

pip install -r requirements.txt

# Configure
cp .env.example .env
# edit .env with DATABASE_URL, SECRET_KEY, optional OPENAI/ANTHROPIC keys, etc.

# Initialise database
python -m database.init_db

# Run API + worker
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## Project layout

```
/agents          # 12 agent implementations + registry
/orchestrator    # task planner, state machine, synthesis
/tools           # registered tools + permission matrix
/workflows       # configurable multi-agent workflows
/memory          # short/working/long-term memory layers
/knowledge       # knowledge items, versioning, retrieval
/research        # research engine + source grading
/diagnostics     # configurable business health pillars
/forecasting     # forecast methods + uncertainty
/analytics       # metric calculations
/reports         # HTML / Markdown / PDF / DOCX / JSON generators
/qa              # quality assurance rules
/security        # auth, RBAC, organisation isolation
/database        # SQLAlchemy models + migrations
/api             # FastAPI routes
/ui              # executive workspace (dashboard, agent activity)
/events          # event bus
/tests           # unit + multi-agent integration tests
/docs            # architecture & operator guides
```

## Key API endpoints

- `POST /bi/tasks` — submit a high-level request
- `GET /bi/tasks/{id}` — task status & results
- `POST /bi/diagnostics` — run business health assessment
- `POST /bi/research` — research request
- `POST /bi/forecasts` — generate forecast
- `POST /bi/competitors/research` — competitor research
- `POST /bi/decisions/analyze` — decision support
- `GET /bi/dashboard` — executive overview
- `POST /bi/reports` — generate a report (from a `task_id` or raw `sections`); `format`: markdown | html | json
- `GET /bi/reports/{task_id}` — generate a report directly from a task's synthesis
- `GET /bi/events` — lifecycle event stream (diagnostic/research/competitor/QA started & completed, forecast.created, agent.failed), scoped to your organisation
- `GET /bi/agents` — agent registry & activity
- `GET /dashboard` — executive workspace UI (agents, tasks, diagnostics, forecasts, reports, settings)
- `GET /` / `GET /app` / `GET /ui` — the chat UI

Full OpenAPI schema is available at `/docs`.

## Demonstration scenarios

1. Assess my business health  
2. Analyse my market  
3. Research my competitors  
4. Analyse my sales performance  
5. Forecast next 12 months of revenue  
6. Create a strategic growth plan  
7. Compare two strategic options  
8. Analyse an uploaded financial/business report  
9. Create an executive report from business data  
10. Research this industry and identify documented opportunities and risks  

Run them via the test suite or the `/bi/tasks` endpoint.

## Design principles you can rely on

- No fabricated statistics, competitor data, citations or forecasts.
- Evidence IDs instead of duplicated source blobs.
- Explicit distinction between measured / estimated / inferred / user-provided.
- Specialists never run without appropriate context.
- Human approval before high-impact external actions.
- Modular agents, tools and workflows — callable programmatically, not hard-coded into UI.

## Future department compatibility

The event bus and standardised message protocol are ready for Marketing, Sales, Finance, Operations, Customer Experience, Engineering, Creative Studio, Analytics, HR, Security and Governance departments to request BI context and receive structured, evidence-backed answers.

---

Built as the foundation for the wider CINTEXA agent workforce.

Licence: MIT (see LICENSE).



## Chat interface

The primary UI is a **full chat experience** (sidebar sessions, message bubbles, suggestions, typing state) talking to:

```
POST /bi/chat
```

Body:

```json
{ "message": "Assess my business health", "session_id": null }
```

Headers: `X-Organisation-Id`, `X-User-Id`.

### Recommended LLM API

| Provider | Env var | Default model | Role |
|----------|---------|---------------|------|
| **OpenAI (recommended)** | `OPENAI_API_KEY` | `gpt-4o` | Planning + natural-language synthesis |
| Anthropic (fallback) | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-20241022` | Same if OpenAI key absent |

Without an LLM key the orchestrator still runs specialist agents (diagnostics, forecasts from your numbers, etc.) and returns a structured deterministic reply. With a key you get full conversational synthesis.

Get an OpenAI key: https://platform.openai.com/api-keys

```bash
export OPENAI_API_KEY=sk-...
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Then open the Pages UI → **Settings** → set API base URL to your API host (e.g. `http://localhost:8000` or your cloud URL).


## Deployment

### Cloudflare Pages (this UI)

Cloudflare Pages serves **static files only**. It cannot run the Python FastAPI workers.

1. Connect the GitHub repo to Cloudflare Pages.
2. Build settings:
   - **Framework preset:** None
   - **Build command:** leave empty
   - **Build output directory:** `/` (repo root hosts `index.html` + `assets/`)
   - Or set output directory to `ui` if you prefer the `ui/` folder only.
3. Deploy. You should see the CINTEXA executive workspace at your `*.pages.dev` URL.

4. In **Settings** on the live site, set **API base URL** to wherever the FastAPI app is running (see below).

### API (FastAPI) — separate host

Run the workforce API on any Python host (Railway, Render, Fly.io, a VPS, or local):

```bash
pip install -r requirements.txt
cp .env.example .env
# Set CORS_ORIGINS to include your Pages URL, e.g.
# CORS_ORIGINS=https://cintexa-business-intelligence-agent-workforce.pages.dev,http://localhost:8000
python -m database.init_db
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

API docs: `https://<your-api-host>/docs`

Required request headers for BI routes:

- `X-Organisation-Id`
- `X-User-Id`

### Why the 404 happened

`*.pages.dev` was pointed at a Python-only repository with no static entrypoint. Pages looked for `index.html` (or a built SPA) and returned HTTP 404. The static UI is now at the repo root so a plain Pages deploy works.


