# Production Readiness

## Status: **HARDENED FOUNDATION — NOT FULLY PRODUCTION-CERTIFIED**

This release closes multi-worker coordination gaps and secret/canary foundations.
It does **not** claim full production certification until container sandboxes, vector ops,
backup restore drills, and load tests run in a real environment.

## What is now durable / multi-worker aware

| Capability | Mechanism |
|------------|-----------|
| Job queue | `plat_jobs` claim + visibility timeout + dead status |
| Leases | `plat_leases` + fencing_token |
| Circuits / health | `plat_circuits` / `plat_health` |
| Freeze | `plat_freeze` (+ process bridge) |
| Canary traffic | `plat_canary_routes` + weighted/sticky `choose()` |
| Idempotency | `plat_idempotency` |
| Secrets | `cintexa_platform.vault.SecretVault` (server-side) |

## Production settings gate

```python
from config.settings import get_settings, validate_production_settings
validate_production_settings(get_settings())
```

Fails if: weak secret_key, auth_dev_fallback, or sqlite URL in `environment=production`.

## Deploy topology (authoritative)

| Role | Responsibility |
|------|----------------|
| **Edge (Pages/CDN)** | Static UI only — no secrets, no long work |
| **API (uvicorn/gunicorn)** | HTTP, authz, short requests |
| **Workers** | Jobs, recovery, evaluation, indexing |
| **PostgreSQL** | Authoritative state |
| **Optional Redis** | Cache/backpressure only — not source of truth |

## Still required before "production ready"

1. Container/seccomp sandbox for untrusted code  
2. pgvector (or equivalent) operationalized  
3. Vault/KMS backend (not memory/env alone)  
4. Backup + restore drill evidence  
5. Load + chaos tests in staging  
6. OIDC/SSO for enterprise tenants  

## Intentional non-goals

- Exactly-once delivery  
- LLM-as-judge authority  
- Uncontrolled self-modification  
- Automatic promotion of model claims to trusted knowledge  
