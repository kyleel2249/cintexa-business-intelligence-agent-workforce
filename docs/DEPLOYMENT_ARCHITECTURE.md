# Deployment Architecture

```
Browser UI  →  CDN/Pages (static)
                 │
                 ▼
            API service  ── PostgreSQL
                 │
                 ├── enqueue jobs → plat_jobs
                 │
Workers  ←───────┘  claim jobs, renew leases
```

- Long-running agent/tool/eval work → **workers**, not request threads.
- Edge must not hold provider API keys.
- Migrations run as a release job before traffic.
