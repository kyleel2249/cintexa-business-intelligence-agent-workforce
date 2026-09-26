# Persistence

## Unit of Work

```python
from persistence.unit_of_work import UnitOfWork

with UnitOfWork() as uow:
    uow.tasks.create(...)
    uow.events.publish(...)
    # commits on clean exit; rolls back on exception
```

## Repositories

`OrganisationRepository`, `UserRepository`, `TaskRepository`, `WorkflowRepository`,
`MissionRepository`, `EventRepository`, `MemoryRepository`, `CheckpointRepository`,
`ConversationRepository`, `AuditRepository`.

All organisation-owned reads filter by `organisation_id`.
