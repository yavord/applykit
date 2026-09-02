#!/usr/bin/env bash
# Boot API + Vite dev servers; Ctrl-C stops both.
set -euo pipefail

cd "$(dirname "$0")"

uv run python -m app.data.migrate

uv run uvicorn app.web.main:app &
UVICORN_PID=$!
trap 'kill "$UVICORN_PID"' EXIT

# `npm run predev` rewrites API types from the live server, so wait for it.
until (exec 3<>/dev/tcp/127.0.0.1/8000) 2>/dev/null; do
    kill -0 "$UVICORN_PID" 2>/dev/null || { wait "$UVICORN_PID"; exit 1; }
    sleep 0.2
done

cd frontend
npm run dev
