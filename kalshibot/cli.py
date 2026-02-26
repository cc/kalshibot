"""
Entry point for the daily scan.

Usage:
    python -m kalshibot          # run a scan with settings from .env
    kalshibot                    # if installed via pip
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .kalshi_client import KalshiClient
from .analyzer import find_anomalies
from .reporter import print_report, write_json_report


def main() -> None:
    env = os.getenv("KALSHI_ENV", "prod")
    min_score = float(os.getenv("MIN_ANOMALY_SCORE", "0.5"))
    max_volume = int(os.getenv("MAX_VOLUME_THRESHOLD", "500"))
    min_spread = float(os.getenv("MIN_SPREAD_THRESHOLD", "10"))
    output_dir = os.getenv("OUTPUT_DIR", "./output")

    print(f"[kalshibot] connecting to Kalshi ({env})...")
    client = KalshiClient(env=env)

    max_markets = int(os.getenv("MAX_MARKETS", "10000"))

    print("[kalshibot] fetching open markets...")
    markets = client.iter_markets(status="open", max_markets=max_markets)
    print(f"[kalshibot] {len(markets)} open markets retrieved")

    resolve_days = int(os.getenv("RESOLVE_DAYS", "7"))
    cutoff = datetime.now(timezone.utc) + timedelta(days=resolve_days)
    markets = [
        m for m in markets
        if m.get("close_time") and datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")) <= cutoff
    ]
    print(f"[kalshibot] {len(markets)} markets closing within {resolve_days} days")

    signals = find_anomalies(
        markets,
        min_score=min_score,
        volume_threshold=max_volume,
        spread_threshold=min_spread,
    )

    print_report(signals)

    if signals:
        path = write_json_report(signals, output_dir=output_dir)
        print(f"\n[kalshibot] report saved → {path}")
    else:
        print("\n[kalshibot] no anomalies found above threshold")


if __name__ == "__main__":
    main()
