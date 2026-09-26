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

## Session — full assessment pass

Same standard as before: cloned fresh, installed into a clean venv, ran the
real test suite and a live server, verified every change against actual
`curl` output rather than reading code and assuming. Nothing was deleted.

### Critical fix

1. **The entire app failed to import.** `api/main.py`'s mission SSE stream
   endpoint (`GET /bi/missions/{id}/stream`, added since the last pass)
   built its final event with
   `f'...{json.dumps({\"event_type\": ...})}...'` — an f-string with
   backslash-escaped quotes inside its own `{}` expression, which is a
   `SyntaxError` in Python (confirmed: reproduces even on 3.12 with PEP 701).
   Because this is a module-level syntax error, **every route in the app was
   broken**, not just the stream endpoint — `import api.main` itself failed,
   so all 43 existing tests would have failed too had anyone tried to run
   them against this exact commit.
   **Fix:** build the payload as a plain dict first (`end_payload = {...}`),
   then `json.dumps(end_payload)` once — matching the pattern the same
   function already uses for its other events a few lines above.
   Verified live: streamed a real mission and captured a well-formed
   `stream.end` JSON event.

### Orphaned-but-functional code, wired up (nothing deleted)

2. **Mission reports.** The newer Workforce Orchestrator (`/bi/missions`,
   documented extensively in the README) had no report generation, even
   though the older task pipeline could turn a synthesis into
   Markdown/HTML/JSON via `/bi/reports`. Added `mission_id` support to
   `POST /bi/reports` and a new `GET /bi/missions/{mission_id}/report`
   (consistent with the existing `plan|tasks|agents|evidence|conflicts|
   events|trace|metrics` mission sub-resources). First cut had its own bug —
   checked `isinstance(mission.result, dict)`, but `mission.result` is
   actually a `MissionResult` **pydantic model**
   (`mission.result.execution_trace` is used elsewhere in
   `orchestrator/workforce.py`), so the check was always `False` and every
   mission report silently fell back to a one-line placeholder instead of
   the real findings. Caught by testing live output, not just reading the
   diff. Fixed to `model_dump(mode="json")` the result when it's a model.

3. **The dashboard never called `/bi/missions` at all.** Despite the Mission
   API being the more heavily documented of the two orchestration systems,
   `assets/app.js` only ever submitted to the older `/bi/tasks` pipeline.
   Added a full **Missions** view: launch a mission (`POST /bi/missions`),
   see its status/confidence/result, and generate a report from it directly
   (Markdown/HTML/JSON, via the new endpoint above) without leaving the
   page. Recent missions persist per-browser-session like the existing
   Tasks view. The Reports view also gained a Mission ID field so either
   pipeline can be reported on from one place.

### Real bug, not just a gap

4. **First-run UX dead end.** `getApiBase()` in `assets/app.js` never
   defaulted to the page's own origin. Following the README's own Quick
   Start — `uvicorn api.main:app` serving the API *and* this dashboard from
   the same process — still left the dashboard saying "Set an API base URL
   in Settings first," even though it was already being served by that
   exact API (`assets/chat.js` already got this right — same-origin by
   default, override via `window.__CINTEXA_API__`). Fixed `getApiBase()` to
   fall back to `window.location.origin` when nothing is saved, while an
   explicit Settings save still overrides it for cross-origin hosting
   (e.g. Cloudflare Pages UI + a separately-hosted API). Verified the three
   cases (default / explicit save / cleared-back-to-default) with a
   sandboxed Node simulation of the browser globals.

### Security hardening (feature kept, made safer)

5. **SSRF exposure in the edge chat's URL-browsing feature.**
   `functions/bi/chat.js`'s `browseUrl()` fetches arbitrary user- and
   model-supplied URLs server-side from the Cloudflare edge — this is the
   documented, intended feature (the chat's `NEED_URLS` mechanism), so the
   fix is not to disable it but to refuse obviously dangerous targets before
   ever calling `fetch()`: loopback/localhost, RFC1918 private ranges, the
   169.254.169.254 cloud metadata address, and non-`http(s)` schemes. Also
   closed a redirect-based bypass — the old `redirect: "follow"` would
   silently chase an initially-safe URL to a blocked internal one before the
   caller ever saw the final URL to check it; switched to manual redirect
   handling so every hop is validated, with a hop limit against redirect
   loops. Verified against 9 known safe/unsafe URLs (including the metadata
   IP and a `file://` URL) with a sandboxed Node test.

### Test coverage added

- `tests/test_api.py` — 6 new regression tests: the SSE stream fix (#1,
  asserts the module even imports and the stream terminates with a valid
  `stream.end` event), mission report reflecting real synthesis rather than
  the placeholder (#2), JSON/HTML mission report formats, a 404 for an
  unknown mission, `mission_id` support on `POST /bi/reports`, and the
  updated 400 error message.
- **49/49 tests pass** (43 existing + 6 new) on a completely fresh
  `python -m venv` + `pip install -r requirements.txt`.

### Verified working end-to-end (not just unit-tested)

Booted the real server and hit it with `curl` for: `/health`, `/dashboard`,
`/bi/diagnostics`, mission creation, `GET /bi/missions/{id}/stream` (the
fixed endpoint — captured a real `stream.end` event), `GET
/bi/missions/{id}/report` in all three formats, and `POST /bi/reports` with
`mission_id`. `node --check` on every JS file including the two just
changed; `python -m py_compile` on every `.py` file in the repo; a full
nested-tag structural check of `dashboard.html` (not just a bracket count).
All `assets/` ↔ `ui/` mirrors re-synced and re-verified identical.

### Known gap, intentionally left as-is (not a regression)

`database/models.py` / `database/init_db.py` define a complete SQLAlchemy
schema (organisations, users, tasks, diagnostics, decisions, etc.) that is
**not wired into the live request path** — missions and tasks currently
live entirely in-process (`orchestrator/workforce.py`'s in-memory store) and
are lost on restart. This predates this session and isn't something broken
by any change above; wiring real persistence through the in-memory store and
every endpoint is a substantial feature in its own right, not a bug fix, so
it was left exactly as-is — nothing here was deleted or hidden, just called
out plainly as the next real piece of work if persistence across restarts
is wanted.
