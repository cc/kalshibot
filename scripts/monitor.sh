#!/usr/bin/env bash
# Run the EPL pre-game movement monitor as a persistent process.
# Usage: ./scripts/monitor.sh
# Or keep it running in the background: nohup ./scripts/monitor.sh &

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

python3 -m kalshibot.monitor
