# Recovery

## After process restart

1. Application reconnects to the database.
2. `MissionManager.get` / `get_for_org` loads mission payloads from `missions`.
3. `WorkflowRepository` + `CheckpointRepository` expose completed vs pending steps.
4. Orchestrator resumes only incomplete work.
5. Durable events remain queryable via `EventRepository` / `bus.history(organisation_id=...)`.

## Restart recovery test

`tests/test_phase1_persistence.py::test_mission_restart_recovery` and
`test_workflow_checkpoint_recovery` prove state survives engine reset + cache clear.
