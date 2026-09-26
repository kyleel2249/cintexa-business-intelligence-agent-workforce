# Phase 4 — Execution & Tool Fabric

## Package

`tool_fabric/` — registry, policy, sandbox, execution engine.

## Pipeline

REQUEST → VALIDATE → AUTHORIZE → POLICY → SANDBOX → EXECUTE → ARTIFACTS → EVENTS

## Security

- Workspace isolation (org hash + execution id)
- Path traversal blocked
- `shell=False` argv lists only
- Command allow/deny lists
- Network domain policy (blocks localhost/private by default in allowlist mode)
- Agent capability permissions
- Approval gate for critical tools (`deploy.apply`)
- Secrets stripped from child process env

## Built-in tools

file.read/write/list, code.python/javascript, shell.run, http.request, git.status/clone, browser.open, deploy.apply
