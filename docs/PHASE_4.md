# Phase 4 — Execution & Tool Fabric

## Pipeline

REQUEST → VALIDATE → AUTHORIZE → POLICY → SANDBOX → EXECUTE → ARTIFACTS → EVENTS

## Package

`tool_fabric/` — registry, policy, sandbox, engine, secrets, computer abstraction.

## Built-in tools

file.read|write|list, code.python|javascript, shell.run, http.request, git.status|clone,
browser.open, deploy.apply, db.query, computer.inspect

## Security

- Workspace isolation (org hash + execution id)
- Path traversal blocked
- `shell=False` argv lists; command allow/deny
- Network domain policy (blocks localhost/private in allowlist mode)
- Agent capability permissions
- Approval gate for critical tools
- Secrets: `SecretProvider` injects only into sandbox env; redaction helper
- Computer use: null provider (no host control by default)

## HTTP API

- POST `/bi/tf/bootstrap`
- GET `/bi/tf/tools`
- POST `/bi/tf/invoke`
- GET `/bi/tf/executions/{id}`
- POST `/bi/tf/executions/{id}/cancel`

## Knowledge integration

Tool artifacts/text can be ingested via Knowledge Fabric `ingest_document`.
