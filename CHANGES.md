# Fix &amp; build log — CINTEXA Business Intelligence Agent Workforce

Everything below was verified by actually running the app (fresh venv install,
full pytest suite, live server + curl against every endpoint touched) — not
just read through. Nothing was deleted; orphaned/broken code was wired up and
made functional instead.

## Critical fixes

1. **QA gate was silently broken in production.**
   `agents/quality.py` called `self.finish_run(..., qa_result=...)`, but
   `BaseAgent.finish_run()` (in `agents/base.py`) didn't accept that keyword
   argument. Every single call — `/bi/diagnostics`, `/bi/research`,
   `/bi/forecasts`, `/bi/competitors/research`, `/bi/decisions/analyze`, and
   chat — was raising inside the Quality Assurance agent and returning
   `{"status": "failed", "error": "...unexpected keyword argument
   'qa_result'"}` instead of an actual QA verdict. The Quality Assurance
   agent is described in the app's own agent registry as the *"final gate
   before user output"* — it was never running successfully.
   **Fix:** extended `finish_run()` to accept and store `qa_result` (the
   `AgentRunRecord` schema already had the field — it just wasn't wired up).
   Verified live: `qa.qa_result` now correctly returns `"APPROVED"`.

2. **Two missing dependencies would break a fresh `pip install -r
   requirements.txt`.** The app uses `sqlite+aiosqlite` as its DB URL and
   SQLAlchemy's async engine, but `aiosqlite` and `greenlet` were never
   listed. Added `sqlalchemy[asyncio]`, `aiosqlite>=0.20.0`,
   `greenlet>=3.1.0`. Also removed a duplicate `httpx` line.

## Orphaned-but-functional code, wired up (nothing deleted)

3. **`reports/generator.py`** (Markdown/HTML/JSON report generation) had zero
   API route despite the README explicitly documenting `GET/POST
   /bi/reports`. Added both endpoints in `api/main.py`. While wiring it up,
   also fixed a real quality bug in the generator itself: nested dict values
   (e.g. diagnostic findings containing enums) were rendered with Python's
   raw `repr()` — producing `<ConfidenceLevel.UNKNOWN: 'UNKNOWN'>` in
   reports. Now rendered as clean, indented JSON blocks. The HTML report
   also used a naive `\n` → `<br>` replace despite `markdown` already being a
   declared dependency; it now does real Markdown→HTML rendering.

4. **`events/bus.py`** (a complete pub/sub event bus with 19 documented
   event types) was never imported anywhere in the codebase. Wired it into
   `orchestrator/core.py` so `diagnostic.*`, `research.*`,
   `competitor.research.*`, `qa.*`, `forecast.created` and `agent.failed`
   events are actually published during task execution, and exposed a new
   `GET /bi/events` endpoint (organisation-scoped) so the event stream is
   observable, not just internal.

5. **`assets/app.js` + the dashboard stylesheet** (a full "executive
   workspace" UI — agent grid, task list, diagnostics form, forecast form,
   settings — matching the README's documented `/ui` architecture) had no
   HTML page anywhere in the repo to load it, and its correct matching
   stylesheet (`ui/assets/styles.css`) had silently diverged from an
   unrelated, unused duplicate at `assets/styles.css` (a stale copy of the
   chat theme that nothing ever linked to). Built the missing
   `dashboard.html` (root + `ui/` mirror for Cloudflare Pages), added
   `assets/dashboard.css` (+ `ui/` mirror) from the correct stylesheet, wired
   a new `GET /dashboard` server route, and extended `app.js` with a
   "Reports" view/handler so the newly-wired `/bi/reports` endpoint is
   actually reachable from the UI. The old, unused `styles.css` files were
   **kept, not deleted** — just annotated with a comment noting they're
   superseded, so nothing that existed before is gone.

## Cleanup

6. Replaced all deprecated `datetime.utcnow()` calls with timezone-aware
   `datetime.now(timezone.utc)` across `orchestrator/core.py`,
   `agents/base.py`, `agents/memory.py`, `agents/knowledge.py`,
   `api/chat.py`, `events/bus.py`, `reports/generator.py`, and the
   `schemas/*.py` `Field(default_factory=...)` defaults.
7. Replaced deprecated Pydantic v1-style `class Config: from_attributes =
   True` with `model_config = ConfigDict(from_attributes=True)` in
   `schemas/evidence.py` and `schemas/tasks.py`.
8. Left SQLAlchemy column defaults (`database/models.py`) on naive
   `datetime.utcnow` intentionally — switching those to timezone-aware
   values risks breaking existing SQLite comparisons and wasn't causing any
   observed bug.

## Test coverage added

- `tests/test_api.py` (new, 10 tests) — HTTP-level regression tests via
  `fastapi.testclient.TestClient`, including an explicit regression test for
  the QA-gate bug (#1), full coverage of the new `/bi/reports` +
  `/bi/reports/{task_id}` endpoints (#3), and the new `/bi/events` endpoint
  (#4).
- **27/27 tests pass**, zero warnings, on a completely fresh
  `python -m venv` + `pip install -r requirements.txt`.

## Verified working end-to-end (not just unit-tested)

Booted the real server and hit it with `curl` for: `/health`, `/dashboard`,
`/bi/diagnostics` (QA now returns `APPROVED`), `/bi/chat` (meta.qa now
populated instead of `null`), `/bi/reports` (all three formats), `GET
/bi/reports/{task_id}`, `/bi/events`, and `python -m database.init_db`
(creates all 14 tables cleanly, SQLite schema included).

## Interface pass — advanced features & 3D motion

- **New shared toolkit**: `assets/motion.js` + `assets/motion.css`, used by
  both `index.html` (chat) and the new `dashboard.html`:
  - Pointer + device-orientation (gyroscope) parallax with independent
    per-layer depth, using the CSS `translate` property so it composes with
    each element's own keyframe animation instead of overwriting it.
  - Real per-card 3D tilt-on-hover, computed from the cursor's position
    inside each element's own bounding box (every card tilts independently
    and tracks the cursor).
  - A draggable 3D "agent orbit" ring (CSS `rotateY` + `translateZ`),
    auto-rotating with momentum/inertia on release, click a node for detail.
  - Animated count-up numbers for metric cards.
  - A toast notification system, wired into every dashboard action
    (request submitted, diagnostic run, forecast run, report generated,
    settings saved, errors).
  - A Ctrl/Cmd+K command palette — searchable, keyboard-navigable — on
    both pages, with page-specific commands (jump to a view, run a
    diagnostic/forecast, generate a report, open the other page).
  - `prefers-reduced-motion` is honoured throughout: every animation above
    disables itself automatically for users who've asked for that.
- **New on the dashboard**: a live activity feed (`#eventFeed`) polling the
  `/bi/events` endpoint every 6s, and a breathing "live" pulse indicator on
  the connection status pill.
- All new/changed frontend files mirrored into `ui/` for the Cloudflare
  Pages static-hosting copy, as with everything else in this repo.
- Verified: `node --check` on all three JS files, full HTML balance check
  on both pages, and a live server smoke test confirming every new asset
  and DOM id (`agentOrbit`, `eventFeed`, `btnCmdk`, `pulseDot`, …) resolves
  with `200`. Backend test suite unaffected — still 27/27.
