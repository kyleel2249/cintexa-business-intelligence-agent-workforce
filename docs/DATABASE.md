# Database

## Engine

Configured via `DATABASE_URL` / `settings.database_url`.

Default development: `sqlite:///./cintexa_bi.db`  
(async URLs with `+aiosqlite` are normalised to sync for the repository layer).

## Core tables (Phase 1)

- `organisations`, `users`, `memberships`
- `agent_tasks`, `agent_runs`
- `workflows`, `workflow_steps`, `checkpoints`
- `missions`, `mission_events`, `orchestration_decisions`
- `durable_events`, `events`
- `memories`, `conversations`
- `artifacts`, `audit_logs`
- reports / evidence / QA tables from prior schema

## Indexes

Organisation-scoped composite indexes exist on tasks, workflows, missions, events, memories, conversations.
