# CINTEXA BI — Architecture (Phase 1)

## Layers

```
API / Controllers (api/)
        ↓
Application services (orchestrator/, api/chat.py)
        ↓
Domain services (agents/, orchestrator/*)
        ↓
Repositories (persistence/repositories.py)
        ↓
Database (SQLAlchemy models + SQLite/Postgres)
```

## Source of truth

The **database** is authoritative for:

- organisations, users, memberships
- tasks, workflows, workflow steps
- missions (full payload)
- checkpoints
- durable events
- memories
- conversations
- audit logs
- agent runs / executions

In-process dictionaries are **caches only**. `MissionManager.clear_cache()` simulates a process restart; state reloads from the database.

## Key packages

| Package | Role |
|---------|------|
| `database/` | Models, session, init |
| `persistence/` | Repositories + UnitOfWork |
| `core/` | Errors, logging, auth foundation |
| `events/` | Durable event bus |
| `orchestrator/` | Mission coordination |
| `alembic/` | Migrations |
