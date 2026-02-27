"""
Write scan results to stdout (rich table) and/or a dated log file.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .analyzer import MarketSignal

if TYPE_CHECKING:
    from .soccer import MovementAlert


def _fmt_cents(v: float) -> str:
    return f"{v:.0f}¢"


def write_json_report(signals: list[MarketSignal], output_dir: str = "./output") -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(output_dir) / f"scan_{date_str}.json"
    data = [s.__dict__ for s in signals]
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def print_report(signals: list[MarketSignal], top_n: int = 20) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        _print_rich(signals[:top_n])
    except ImportError:
        _print_plain(signals[:top_n])


def _print_rich(signals: list[MarketSignal]) -> None:
    from rich.console import Console
    from rich.table import Table
    from rich import box

    console = Console()
    table = Table(
        title=f"Kalshi Anomaly Scan — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        box=box.ROUNDED,
        show_lines=True,
    )
    table.add_column("Score", justify="right", style="bold yellow", width=6)
    table.add_column("Ticker", style="cyan", width=24)
    table.add_column("Bid/Ask (yes)", justify="center", width=14)
    table.add_column("Spread", justify="right", width=7)
    table.add_column("Vol 24h", justify="right", width=8)
    table.add_column("Flags", width=32)
    table.add_column("Title")
    table.add_column("Bet")

    for s in signals:
        base = (s.event_ticker or s.ticker).rsplit("-", 1)[0]
        url = f"https://kalshi.com/markets/{base}"
        table.add_row(
            f"{s.anomaly_score:.2f}",
            f"[link={url}]{s.ticker}[/link]",
            f"{_fmt_cents(s.yes_bid)} / {_fmt_cents(s.yes_ask)}",
            _fmt_cents(s.spread),
            str(s.volume_24h),
            ", ".join(s.flags) or "—",
            s.title,
            s.subtitle or "—",
        )

    console.print(table)
    console.print(f"[dim]{len(signals)} market(s) flagged[/dim]")


def _print_plain(signals: list[MarketSignal]) -> None:
    print(f"\n=== Kalshi Anomaly Scan {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
    print(f"{'Score':>6}  {'Ticker':<24}  {'Bid/Ask':>12}  {'Spread':>7}  {'Vol':>6}  Flags")
    print("-" * 90)
    for s in signals:
        print(
            f"{s.anomaly_score:>6.2f}  {s.ticker:<24}  "
            f"{_fmt_cents(s.yes_bid)}/{_fmt_cents(s.yes_ask):>6}  "
            f"{_fmt_cents(s.spread):>7}  {s.volume_24h:>6}  {', '.join(s.flags)}"
            f"\n        https://kalshi.com/markets/{(s.event_ticker or s.ticker).rsplit('-', 1)[0]}"
        )
    print(f"\n{len(signals)} market(s) flagged")


# ------------------------------------------------------------------
# Movement alert reporter (EPL monitor)
# ------------------------------------------------------------------

def _market_url(event_ticker: str, ticker: str) -> str:
    base = (event_ticker or ticker).rsplit("-", 1)[0]
    return f"https://kalshi.com/markets/{base}"


def print_movement_alerts(alerts: "list[MovementAlert]") -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        table = Table(
            title=f"EPL Movement Alerts — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("Market", style="cyan")
        table.add_column("Bet")
        table.add_column("Bid/Ask", justify="center", width=12)
        table.add_column("Alerts")
        table.add_column("Kickoff", width=18)

        for a in alerts:
            url = _market_url(a.event_ticker, a.ticker)
            kickoff = a.close_time[:16].replace("T", " ") + " UTC" if a.close_time else "—"
            table.add_row(
                f"[link={url}]{a.title}[/link]",
                a.subtitle or "—",
                f"{_fmt_cents(a.yes_bid)} / {_fmt_cents(a.yes_ask)}",
                "\n".join(a.alerts),
                kickoff,
            )

        console.print(table)
        console.print(f"[dim]{len(alerts)} alert(s)[/dim]")

    except ImportError:
        print(f"\n=== EPL Movement Alerts {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} ===")
        for a in alerts:
            url = _market_url(a.event_ticker, a.ticker)
            print(f"  {a.title} — {', '.join(a.alerts)}")
            print(f"  {url}")
        print(f"\n{len(alerts)} alert(s)")


def write_movement_report(alerts: "list[MovementAlert]", output_dir: str = "./output") -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = Path(output_dir) / f"movements_{date_str}.json"
    ts = datetime.now(timezone.utc).isoformat()
    data = [{"ts": ts, **a.__dict__} for a in alerts]
    # Append to existing file if present
    existing: list = []
    if path.exists():
        with open(path) as f:
            existing = json.load(f)
    with open(path, "w") as f:
        json.dump(existing + data, f, indent=2, default=str)
    print(f"\n[monitor] report saved → {path}")
    return path
