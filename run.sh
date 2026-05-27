#!/bin/bash
echo "🐶 Starting Marty Pricing Agent..."
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8910 --reload
