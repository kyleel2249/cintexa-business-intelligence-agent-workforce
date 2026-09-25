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
echo "CINTEXA BI → http://127.0.0.1:${PORT}/"
exec uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
