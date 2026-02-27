"""
EPL pre-game movement monitor.

Runs a continuous polling loop fetching EPL markets from Kalshi,
pulling candlestick history for each market, and alerting on
significant price moves or volume spikes before kickoff.

Usage:
    python -m kalshibot.monitor
    kalshibot-monitor                    # if installed via pip
"""

import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from kalshibot.kalshi_client import KalshiClient
from kalshibot.soccer import detect_movements
from kalshibot.reporter import print_movement_alerts, write_movement_report


def run_monitor() -> None:
    env = os.getenv("KALSHI_ENV", "prod")
    output_dir = os.getenv("OUTPUT_DIR", "./output")
    poll_interval = int(os.getenv("POLL_INTERVAL_MINUTES", "15"))
    poll_once = os.getenv("POLL_ONCE", "").lower() in ("1", "true", "yes")
    soccer_series = [s.strip() for s in os.getenv("SOCCER_SERIES", "KXEPLGAME,KXEPLBTTS,KXEPLTOTAL,KXEPLSPREAD").split(",")]
    short_minutes = int(os.getenv("PRICE_MOVE_SHORT_MINUTES", "30"))
    short_cents = float(os.getenv("PRICE_MOVE_SHORT_CENTS", "5"))
    long_hours = int(os.getenv("PRICE_MOVE_LONG_HOURS", "2"))
    long_cents = float(os.getenv("PRICE_MOVE_LONG_CENTS", "10"))
    volume_multiplier = float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "2.0"))
    max_spread_cents = float(os.getenv("MAX_SPREAD_CENTS", "20"))

    mode = "one-shot" if poll_once else f"poll every {poll_interval}m"
    print(f"[monitor] starting EPL monitor ({mode})")
    client = KalshiClient(env=env)

    while True:
        now = int(time.time())
        lookback_start = now - (long_hours * 3600)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        print(f"\n[monitor] {ts} — fetching EPL markets...")

        markets = []
        for series in soccer_series:
            batch = client.iter_markets(series_ticker=series, max_markets=500)
            markets.extend(batch)

        print(f"[monitor] {len(markets)} EPL markets — checking for movements...")

        alerts = []
        for market in markets:
            event_ticker = market.get("event_ticker", "")
            series_ticker = event_ticker.split("-")[0] if event_ticker else ""
            if not series_ticker:
                continue

            try:
                candles = client.get_candlesticks(
                    series_ticker=series_ticker,
                    market_ticker=market["ticker"],
                    start_ts=lookback_start,
                    end_ts=now,
                )
            except Exception:
                continue

            alert = detect_movements(
                market,
                candles,
                short_minutes=short_minutes,
                short_cents=short_cents,
                long_hours=long_hours,
                long_cents=long_cents,
                volume_multiplier=volume_multiplier,
                max_spread_cents=max_spread_cents,
            )
            if alert:
                alerts.append(alert)

        if alerts:
            alerts.sort(key=lambda a: a.magnitude, reverse=True)
            print_movement_alerts(alerts)
            write_movement_report(alerts, output_dir=output_dir)
        else:
            print(f"[monitor] no movements detected")

        if poll_once:
            break

        print(f"[monitor] next check in {poll_interval}m")
        time.sleep(poll_interval * 60)
