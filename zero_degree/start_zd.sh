#!/bin/bash
echo "🛡️ Cleaning Port 8000..."
fuser -k 8000/tcp 2>/dev/null
export PYTHONPATH=.
echo "🚀 Starting Zero Degree on 8000..."
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload