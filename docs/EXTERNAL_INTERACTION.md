# External Web, Browser, Media & Social Interaction Fabric

## Principle

External content is **DATA** (`EXTERNAL_UNTRUSTED`), never control-plane instructions.

## Stack

```
Agent → Capability → Governor (rate/dupe/budget/kill) → URL security
  → BrowserProvider (mock|playwright later) → Observe/Act → Verify → Audit
```

## Providers

| Provider | Status |
|----------|--------|
| `MockBrowserProvider` | **Implemented** (tests) |
| Playwright/Chromium | Adapter interface ready — not bundled as default runtime |

## Safety

- SSRF / private IP / metadata host / blocked schemes
- Kill switch for external **writes**
- Approval for MEDIUM+ risk writes
- Duplicate content & rate limits
- No CAPTCHA bypass
- No stealth anti-bot evasion

## APIs (programmatic)

- `BrowserEngine.create_session / navigate / observe / close`
- `ExternalActionService.request / approve`
- `WebResearchEngine.research`
- `MediaEngine.analyze_video`
- `ExternalKillSwitch.activate / deactivate`
