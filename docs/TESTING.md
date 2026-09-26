# Testing

```bash
pytest tests/test_phase1_persistence.py -v
pytest tests/ -q
```

Phase 1 suite covers:

- membership
- task persistence + org isolation
- workflow checkpoints + restart
- durable events
- memory isolation
- mission restart recovery
- idempotency
- optimistic concurrency
- log scrubbing
