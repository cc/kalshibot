"""
Write scan results to stdout (rich table) and/or a dated log file.
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from .analyzer import MarketSignal

if TYPE_CHECKING:
    from .soccer import MovementAlert


def _fmt_cents(v: float) -> str:
    return f"{v:.0f}¢"


def _fmt_mid(v: float) -> str:
    """Show one decimal place so e.g. 18.5¢ is visible rather than rounding to 18¢."""
    return f"{v:.1f}¢"


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


def _fixture_key(event_ticker: str) -> str:
    """Strip series prefix to get the fixture identifier, shared across all series for a game.

    e.g. "KXEPLGAME-26MAR14NEWEVE" and "KXEPLSPREAD-26MAR14NEWEVE" both return "26MAR14NEWEVE".
    """
    parts = (event_ticker or "").split("-", 1)
    return parts[1] if len(parts) > 1 else event_ticker


def _fmt_fixture_key(key: str) -> str:
    """Strip date prefix from a fixture key, returning just the teams code.

    e.g. "26FEB28EVENE" -> "EVENE", "26MAR14NEWEVE" -> "NEWEVE"
    """
    m = re.match(r'^\d{2}[A-Z]{3}\d{2}(.+)$', key)
    return m.group(1) if m else key


def _game_label(group: list) -> str:
    """Derive a human-readable fixture label from a group of alerts for the same event."""
    # KXEPLGAME titles are "Team A vs Team B Winner?" — cleanest form
    for a in group:
        if a.series_ticker == "KXEPLGAME":
            return a.title.replace(" Winner?", "").replace("?", "").strip()
    # Fallback: extract from any "X vs Y" title
    for a in group:
        if " vs " in a.title:
            before, after = a.title.split(" vs ", 1)
            team1 = before.split()[-1] if before.split() else before
            team2_words = after.split("?")[0].strip().split()
            team2 = team2_words[0] if team2_words else after
            return f"{team1} vs {team2}"
    # Last resort: format the fixture key (e.g. "EVENE · Mar 14")
    return _fmt_fixture_key(_fixture_key(group[0].event_ticker or group[0].ticker))


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
        table.add_column("Price history", width=22)
        table.add_column("Alerts")
        table.add_column("Kickoff", width=18)

        # Group by fixture key (strips series prefix so WIN/BTTS/TOTAL/SPREAD for the same
        # game land in the same group), sorted by kickoff time
        groups: dict = {}
        for a in alerts:
            key = _fixture_key(a.event_ticker or a.ticker)
            groups.setdefault(key, []).append(a)
        # Within each group: KXEPLGAME first (best title), then by magnitude descending
        for g in groups.values():
            g.sort(key=lambda a: (a.series_ticker != "KXEPLGAME", -a.magnitude))
        sorted_groups = sorted(groups.values(), key=lambda g: g[0].close_time or "")

        first = True
        for group in sorted_groups:
            if not first:
                table.add_section()
            first = False

            game_name = _game_label(group)
            kickoff = group[0].close_time[:16].replace("T", " ") + " UTC" if group[0].close_time else "—"
            table.add_row(
                f"[bold white]{game_name}[/bold white]",
                "", "", "", "",
                f"[dim]{kickoff}[/dim]",
                style="on grey23",
            )

            for a in group:
                url = _market_url(a.event_ticker, a.ticker)
                history_lines = []
                if a.midpoint_long_ago is not None:
                    arrow = "↑" if a.midpoint > a.midpoint_long_ago else "↓"
                    history_lines.append(f"{_fmt_mid(a.midpoint_long_ago)} {arrow} {_fmt_mid(a.midpoint)}  (12h)")
                if a.midpoint_short_ago is not None:
                    arrow = "↑" if a.midpoint > a.midpoint_short_ago else "↓"
                    history_lines.append(f"{_fmt_mid(a.midpoint_short_ago)} {arrow} {_fmt_mid(a.midpoint)}  (30m)")
                if a.volume_earlier is not None and a.volume_recent is not None:
                    history_lines.append(f"vol  {a.volume_earlier} → {a.volume_recent}")
                table.add_row(
                    f"[link={url}]{a.title}[/link]",
                    a.subtitle or "—",
                    f"{_fmt_cents(a.yes_bid)} / {_fmt_cents(a.yes_ask)}",
                    "\n".join(history_lines) or "—",
                    "\n".join(a.alerts),
                    "",
                )

        console.print(table)
        console.print(f"[dim]{len(alerts)} alert(s) across {len(groups)} game(s)[/dim]")

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
