# Internet Intelligence Fabric — Independent Verification Report

## 1. EXECUTIVE VERDICT

```text
NOT_PRODUCTION_READY
```

**FOUNDATION_VERIFIED** for mock-backed research with real security/provenance controls.  
Live search/browser providers, Courtroom Engine package, and multi-worker research recovery remain incomplete.

## 2. WHAT WAS VERIFIED

| Area | Result |
|------|--------|
| Search (mock) + failover | PASS |
| Empty / all-fail (no fabrication) | PASS |
| Strategy engine depth families | PASS |
| Research orchestrator + refinement | PASS |
| Depth SURFACE vs DEEP query growth | PASS |
| SSRF / private IP / schemes | PASS |
| Prompt injection as data | PASS |
| ACCESS_FAILED / BLOCKED_BY_POLICY | PASS |
| Citation integrity | PASS |
| Conflict OPEN records | PASS |
| Restart research case persistence | PASS |
| Tenant isolation | PASS |
| Tenant search cache isolation | PASS |
| API /internet/* | PASS |
| Capability registry (≥30) | PASS |
| External API registry HTTPS-only + stub invoke | PASS |
| Courtroom adapter (null sink) | PASS (honest NOT_INSTALLED) |
| pytest internet suite | **19 passed** |

## 3. WHAT WAS REPAIRED / EXTENDED

- Strategy engine (`strategy.py`): query families, refine-after-gap, early stop
- Tenant cache (`cache.py`)
- Entity heuristics (`entities.py`)
- External API registry foundation (`api_registry.py`)
- Courtroom adapter contract (`courtroom_adapter.py`) — no fake engine
- Expanded capabilities (≥30)
- Orchestrator uses external_fabric browser correctly
- API: `/plan`, `/apis`, `/courtroom/package/{id}`

## 4–8. FINDINGS SUMMARY

- **Security:** SSRF and injection-as-data hold on tested paths.
- **Reliability:** Provider failover works; durable Phase 5 circuits still **not** wired into search (BUILT, NOT INTEGRATED pattern).
- **Performance:** Functional only; no load numbers claimed.
- **Integration:** external_fabric URL/browser; Phase 1 persistence; events. **No Courtroom package** in repo.
- **Blockers:** live SearchProvider, Playwright workers, Courtroom engine, multi-worker research leases, DNS rebinding lab.

## 9. TEST RESULTS

```text
pytest tests/test_internet_fabric.py → 19 passed
```

## 10. DEFECT REGISTER

| ID | Sev | Status |
|----|-----|--------|
| IF-001 Empty query corpus | P2 | FIXED (prior) |
| IF-002 Live search/browser | P1 | OPEN / BLOCKED |
| IF-003 Courtroom package | P1 | OPEN (adapter only) |
| IF-004 Durable circuits on search | P2 | OPEN |
| IF-010 SourceRegistry call kwargs mismatch | P2 | FIXED this pass |

## 11. PRODUCTION-READINESS STATUS

```text
NOT_PRODUCTION_READY
```

## 12. EVIDENCE

Commands: pytest; adversarial paths via tests; API TestClient. Mock ≠ live web.
