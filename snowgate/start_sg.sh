#!/bin/bash
echo "🛡️ Cleaning Port 8001..."
fuser -k 8001/tcp 2>/dev/null
export PYTHONPATH=.
echo "🚀 Starting SnowGate on 8001..."
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload