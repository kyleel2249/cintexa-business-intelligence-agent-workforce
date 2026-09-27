# Universal Internet Intelligence & Web Access Fabric

## Principle

```text
Agent → Intent → Research plan → Search → Source eval → Retrieve
  → Extract → Evidence → Cross-check → Cite → Result
```

External content is always **`UNTRUSTED_EXTERNAL_CONTENT`**, never system instructions.

## Integration

| Layer | Reuse |
|-------|--------|
| URL/SSRF security | `external_fabric.url_security` |
| Browser sessions | `external_fabric.browser` |
| Interaction governor | `external_fabric.governor` |
| PDF/DOCX parse | `knowledge_fabric.document_parsers` |
| Persistence | Phase 1 UnitOfWork / SQLAlchemy |
| Reliability | Search provider failover + search logs |
| Events | `events.bus` |

## Packages

- `internet_fabric/search.py` — multi-provider SearchFabric
- `internet_fabric/sources.py` — SourceRegistry + quality classification
- `internet_fabric/evidence.py` — evidence, claims, conflicts, citations
- `internet_fabric/orchestrator.py` — InternetResearchOrchestrator
- `internet_fabric/providers/mock_search.py` — offline fixture search (no live fabrication)

## API

- `GET /internet/capabilities`
- `POST /internet/search`
- `POST /internet/research`
- `GET /internet/research/{id}`

Header: `X-Org-Id` for tenancy.

## Providers

| Provider | Status |
|----------|--------|
| `MockSearchProvider` | Implemented (tests / offline) |
| Live Google/Bing/etc. | Plug in via `SearchProvider` interface — credentials required |

## Non-goals (explicit)

- CAPTCHA/paywall bypass
- Credential exposure to models
- Fabricated URLs or citations
- Silent success when retrieval failed (`ACCESS_FAILED` recorded)

## Research depths

`SURFACE` | `STANDARD` | `DEEP` | `EXHAUSTIVE` — more query families and budget usage.
