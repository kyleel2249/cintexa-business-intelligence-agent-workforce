# Backup & Restore

## Status

`scripts/backup_restore.py` provides real, tested backup/restore tooling
for both database backends the app supports. This did not previously
exist anywhere in the repo — see "What this replaces" below.

**Verified in this environment:** a full drill (seed data → backup →
verify → simulate database loss → restore → verify data integrity) was
run end-to-end against SQLite and passed — exact pre-disaster data was
recovered. **Not yet verified:** the PostgreSQL path (`pg_dump`/`pg_restore`
commands are implemented and follow standard practice, but this sandbox has
no Postgres server to drill against — someone with a real Postgres
instance should run the drill below once against staging before relying on
this in production).

## Usage

```bash
# Back up the database DATABASE_URL currently points at
python3 scripts/backup_restore.py backup --out backups/cintexa_bi_$(date +%Y%m%d).backup

# Sanity-check a backup file without touching the live database
python3 scripts/backup_restore.py verify --in backups/cintexa_bi_20260101.backup

# Restore (requires --yes; makes a pre-restore safety copy first for SQLite)
python3 scripts/backup_restore.py restore --in backups/cintexa_bi_20260101.backup --yes
```

Reads `DATABASE_URL` from the environment — the same variable
`database/session.py` uses, so this always targets whatever database the
app itself is configured against.

- **SQLite**: uses `sqlite3`'s online backup API (`Connection.backup()`),
  which is safe against a live/open database — not a raw file copy, which
  could race a concurrent writer mid-transaction. Restore keeps a
  timestamped `.pre-restore-<pid>.bak` copy of the live file before
  overwriting it.
- **PostgreSQL**: uses `pg_dump -Fc` (custom format — compressed, supports
  selective restore) and `pg_restore --clean --if-exists --no-owner`.

## Recommended drill cadence

Run the full backup → verify → restore-into-a-scratch-database cycle:
- Once before first production deploy (required — see
  `docs/PRODUCTION_READINESS.md` item 4).
- After every schema-changing Alembic migration.
- On a recurring schedule (monthly is a reasonable starting point) as a
  standing check that backups are actually restorable, not just present.

## What this replaces

Before this, `docs/PRODUCTION_READINESS.md` listed "Backup + restore drill
evidence" only as an outstanding checklist item (line 45), and
`docs/RECOVERY.md` covers a different concern — in-process restart recovery
(resuming durable mission/task state after the app process restarts), not
recovering from losing the underlying database itself. There was no actual
backup/restore procedure or tooling anywhere in the repository.
