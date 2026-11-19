#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
umask 077
PYTHON="${ABC_PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  python3 -m venv .venv
fi
"$PYTHON" -m pip install -r requirements-web.txt
npm --prefix frontend ci
npm --prefix frontend run build
set --
if [ -f .env ]; then
  set -- --env-file .env
fi
exec "$PYTHON" -m uvicorn web.api:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log "$@"
