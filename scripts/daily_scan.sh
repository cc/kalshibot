#!/usr/bin/env bash
# Run the Kalshi anomaly scan and append to a daily log.
# Add to crontab with:
#   0 8 * * * /path/to/kalshibot/scripts/daily_scan.sh >> /path/to/kalshibot/output/cron.log 2>&1

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "--- $(date -u '+%Y-%m-%d %H:%M UTC') ---"
python -m kalshibot
