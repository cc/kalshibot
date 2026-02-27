"""
EPL pre-game movement detection.

Given a market dict and its candlestick history, detects:
  1. Short-term price move  — midpoint shift since PRICE_MOVE_SHORT_MINUTES ago
  2. Long-term price move   — midpoint shift since PRICE_MOVE_LONG_HOURS ago
  3. Volume spike           — recent candle volume vs earlier candle volume
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MovementAlert:
    ticker: str
    series_ticker: str
    event_ticker: str
    title: str
    subtitle: str
    yes_bid: float
    yes_ask: float
    midpoint: float
    volume_24h: int
    alerts: list[str]
    magnitude: float    # largest price move in cents, for sorting
    close_time: str


def _candle_midpoint(candle: dict) -> Optional[float]:
    """Midpoint from a candle's yes_bid.close and yes_ask.close."""
    bid = (candle.get("yes_bid") or {}).get("close")
    ask = (candle.get("yes_ask") or {}).get("close")
    if bid is None or ask is None:
        return None
    return (bid + ask) / 2.0


def _nearest_candle(candles: list[dict], target_ts: int) -> Optional[dict]:
    """Return the candle whose end_period_ts is closest to target_ts."""
    if not candles:
        return None
    return min(candles, key=lambda c: abs(c["end_period_ts"] - target_ts))


def detect_movements(
    market: dict,
    candles: list[dict],
    short_minutes: int = 30,
    short_cents: float = 5.0,
    long_hours: int = 2,
    long_cents: float = 10.0,
    volume_multiplier: float = 2.0,
) -> Optional[MovementAlert]:
    """
    Analyse candlestick history for a single market.
    Returns a MovementAlert if any threshold is breached, else None.
    """
    if not candles:
        return None

    # Current state from market dict (live prices)
    yes_bid = market.get("yes_bid") or 0
    yes_ask = market.get("yes_ask") or 0
    if yes_ask == 0:
        return None
    current_mid = (yes_bid + yes_ask) / 2.0
    current_ts = max(c["end_period_ts"] for c in candles)

    alerts: list[str] = []
    magnitude = 0.0

    # 1. Short-term price move
    short_target_ts = current_ts - (short_minutes * 60)
    short_candle = _nearest_candle(candles, short_target_ts)
    if short_candle:
        short_mid = _candle_midpoint(short_candle)
        if short_mid is not None:
            move = current_mid - short_mid
            if abs(move) >= short_cents:
                direction = "+" if move > 0 else ""
                alerts.append(f"price {direction}{move:.0f}¢ in {short_minutes}m")
                magnitude = max(magnitude, abs(move))

    # 2. Long-term price move
    long_target_ts = current_ts - (long_hours * 3600)
    long_candle = _nearest_candle(candles, long_target_ts)
    if long_candle:
        long_mid = _candle_midpoint(long_candle)
        if long_mid is not None:
            move = current_mid - long_mid
            if abs(move) >= long_cents:
                direction = "+" if move > 0 else ""
                alerts.append(f"price {direction}{move:.0f}¢ in {long_hours}h")
                magnitude = max(magnitude, abs(move))

    # 3. Volume spike — split candles in half, compare halves
    if len(candles) >= 4:
        mid = len(candles) // 2
        earlier_vol = sum(c.get("volume", 0) for c in candles[:mid]) or 1
        recent_vol = sum(c.get("volume", 0) for c in candles[mid:])
        ratio = recent_vol / earlier_vol
        if ratio >= volume_multiplier:
            alerts.append(f"volume spike {ratio:.1f}x")
            magnitude = max(magnitude, ratio * 5)   # scale to cents-ish for sorting

    if not alerts:
        return None

    event_ticker = market.get("event_ticker", "")
    series_ticker = event_ticker.split("-")[0] if event_ticker else ""

    return MovementAlert(
        ticker=market.get("ticker", ""),
        series_ticker=series_ticker,
        event_ticker=event_ticker,
        title=market.get("title", ""),
        subtitle=market.get("subtitle") or "",
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        midpoint=current_mid,
        volume_24h=market.get("volume_24h") or 0,
        alerts=alerts,
        magnitude=magnitude,
        close_time=market.get("close_time", ""),
    )
