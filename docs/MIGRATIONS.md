# Migrations

Alembic is configured (`alembic.ini`, `alembic/env.py`).

```bash
# Apply
alembic upgrade head

# Or for local/dev quick schema create
python -m database.init_db
```

Revision `001_phase1` creates the full metadata schema.
