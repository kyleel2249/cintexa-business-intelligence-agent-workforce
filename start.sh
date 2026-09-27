#!/usr/bin/env sh
# Run the full Python BI workforce (UI + API on one origin).
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
pip install -q -r requirements.txt

export PORT="${PORT:-8000}"

# Run migrations before serving traffic (see docs/DEPLOYMENT_ARCHITECTURE.md:
# "Migrations run as a release job before traffic"). `alembic upgrade head`
# is idempotent — a no-op if the schema is already current. api/main.py's
# lifespan() also calls init_db() as a defensive fallback, but Alembic is
# the authoritative path since it tracks schema history properly.
alembic upgrade head

echo "CINTEXA BI → http://127.0.0.1:${PORT}/"
exec uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
