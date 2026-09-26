# Authorization (Phase 1 foundation)

- `Membership` links users to organisations with roles.
- Repositories refuse cross-organisation reads.
- `X-Organisation-Id` / `X-User-Id` headers are **request metadata**.
- In `development` / `test`, `auth_dev_fallback` may bootstrap membership.
- Production must set `environment=production` and `auth_dev_fallback=false` and supply real auth (Phase later).
