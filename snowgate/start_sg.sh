#!/bin/bash
export PYTHONPATH=.
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload