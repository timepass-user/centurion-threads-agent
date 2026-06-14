#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

if [ -z "$THREADS_ACCESS_TOKEN" ] && [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$THREADS_ACCESS_TOKEN" ]; then
  echo "Missing THREADS_ACCESS_TOKEN. Run:"
  echo "  python scripts/oauth_auto.py YOUR_APP_ID YOUR_APP_SECRET"
  exit 1
fi

echo "Starting Centurion daemon (cycle every 2h)..."
python -m agent.main daemon
