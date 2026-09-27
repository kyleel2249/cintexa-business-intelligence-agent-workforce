#!/usr/bin/env python3
"""Database backup/restore for CINTEXA BI (closes G20, docs/GAP_REGISTER.md).

Prior state: no backup/restore procedure existed anywhere in this repo —
`docs/PRODUCTION_READINESS.md` only listed "Backup + restore drill evidence"
as a missing checklist item, and `docs/RECOVERY.md` covers a different
concern entirely (in-process restart recovery, not losing the database).
The gap register's note ("Documented procedure; needs ops environment")
overstated what existed — there was no documented procedure to run.

This script supports both backends the app actually uses:
  - SQLite (default for dev/test; `sqlite:///path.db`)
  - PostgreSQL (production; `postgresql://...`)

Usage:
    python3 scripts/backup_restore.py backup  [--out PATH]
    python3 scripts/backup_restore.py restore --in PATH [--yes]
    python3 scripts/backup_restore.py verify  --in PATH

Reads DATABASE_URL from the environment (same variable the app itself uses;
see database/session.py). Exits non-zero on any failure — never partially
overwrites the live database without an explicit --yes confirmation.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./cintexa_bi.db")
    # normalise the async driver prefix the app defaults to, same as
    # database/session.py does, so this script works with either form
    if url.startswith("sqlite+aiosqlite://"):
        url = "sqlite://" + url[len("sqlite+aiosqlite://"):]
    return url


def _sqlite_path(url: str) -> str:
    # sqlite:///relative/path.db or sqlite:////absolute/path.db
    assert url.startswith("sqlite://")
    return url[len("sqlite://"):] or url[len("sqlite:///"):]


def backup(out_path: str) -> None:
    url = _database_url()
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if url.startswith("sqlite://"):
        src_path = _sqlite_path(url)
        if not os.path.exists(src_path):
            print(f"ERROR: source database does not exist: {src_path}", file=sys.stderr)
            sys.exit(1)
        # sqlite3's .backup API is safe against a live/open database
        # (uses the online backup API, not a raw file copy which could
        # race a writer mid-transaction).
        src = sqlite3.connect(src_path)
        dst = sqlite3.connect(str(out))
        with dst:
            src.backup(dst)
        src.close()
        dst.close()
        print(f"OK: SQLite backup written to {out} ({out.stat().st_size} bytes)")
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        # pg_dump in custom format (-Fc): compressed, supports parallel
        # restore and selective restore via pg_restore.
        cmd = ["pg_dump", "-Fc", "-f", str(out), url]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: pg_dump failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: PostgreSQL backup written to {out} ({out.stat().st_size} bytes)")
    else:
        print(f"ERROR: unsupported DATABASE_URL scheme: {url}", file=sys.stderr)
        sys.exit(1)


def verify(in_path: str) -> None:
    """Sanity-check a backup file without touching the live database."""
    url = _database_url()
    if url.startswith("sqlite://"):
        con = sqlite3.connect(f"file:{in_path}?mode=ro", uri=True)
        try:
            result = con.execute("PRAGMA integrity_check").fetchone()
            tables = con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            if result[0] != "ok":
                print(f"ERROR: integrity check failed: {result[0]}", file=sys.stderr)
                sys.exit(1)
            print(f"OK: backup integrity check passed, {tables} tables present")
        finally:
            con.close()
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        result = subprocess.run(["pg_restore", "--list", in_path], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: pg_restore --list failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        n_objects = len([l for l in result.stdout.splitlines() if l.strip()])
        print(f"OK: backup readable, {n_objects} catalog entries present")
    else:
        print(f"ERROR: unsupported DATABASE_URL scheme: {url}", file=sys.stderr)
        sys.exit(1)


def restore(in_path: str, confirmed: bool) -> None:
    url = _database_url()
    if not os.path.exists(in_path):
        print(f"ERROR: backup file not found: {in_path}", file=sys.stderr)
        sys.exit(1)

    if not confirmed:
        print(
            "This will OVERWRITE the live database at "
            f"{url!r} with the contents of {in_path!r}.\n"
            "Re-run with --yes to proceed.",
            file=sys.stderr,
        )
        sys.exit(2)

    if url.startswith("sqlite://"):
        dest_path = _sqlite_path(url)
        # Verify the backup opens cleanly before touching the live file.
        verify(in_path)
        if os.path.exists(dest_path):
            safety_copy = f"{dest_path}.pre-restore-{os.getpid()}.bak"
            shutil.copy2(dest_path, safety_copy)
            print(f"Pre-restore safety copy of the live DB saved to {safety_copy}")
        shutil.copy2(in_path, dest_path)
        print(f"OK: restored {in_path} -> {dest_path}")
    elif url.startswith("postgresql://") or url.startswith("postgres://"):
        cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "-d", url, in_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: pg_restore failed:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(f"OK: restored {in_path} into {urlparse(url).path.lstrip('/')}")
    else:
        print(f"ERROR: unsupported DATABASE_URL scheme: {url}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_backup = sub.add_parser("backup", help="Write a backup of the current database")
    p_backup.add_argument("--out", default="backups/cintexa_bi.backup", help="Output file path")

    p_restore = sub.add_parser("restore", help="Restore the database from a backup file")
    p_restore.add_argument("--in", dest="in_path", required=True, help="Backup file to restore from")
    p_restore.add_argument("--yes", action="store_true", help="Confirm overwriting the live database")

    p_verify = sub.add_parser("verify", help="Sanity-check a backup file without restoring it")
    p_verify.add_argument("--in", dest="in_path", required=True, help="Backup file to verify")

    args = parser.parse_args()
    if args.command == "backup":
        backup(args.out)
    elif args.command == "restore":
        restore(args.in_path, args.yes)
    elif args.command == "verify":
        verify(args.in_path)


if __name__ == "__main__":
    main()
