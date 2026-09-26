# Phase 2 — Agent Operating System

## Package

`agent_os/` — registry, lifecycle, runtime, contracts, durable models.

## Lifecycle

`REGISTERED → ACTIVE → PAUSED | DRAINING → DISABLED`

Invalid transitions raise `ConflictError`.

Only `ACTIVE` agents accept **new** work. `DRAINING` may finish in-flight work but is not selected for new assignments.

## Capability discovery

`AgentOSRegistry.find_by_capability(org, capability)` and `select_agent(org, capability)`.

## Extensibility

Register a new agent without changing scheduler/persistence:

```python
reg.register(organisation_id=..., agent_key="my_agent", name="...", capabilities=["..."])
reg.activate(...)
runtime.register_handler("my_agent", my_handler)
```

## Tables

`aos_agents`, `aos_capabilities`, `aos_executions`, `aos_messages`, `aos_escalations`, `aos_graph_nodes`
