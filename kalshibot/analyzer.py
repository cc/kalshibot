"""
Detect low-liquidity + price anomaly markets on Kalshi.

Anomaly score is a 0–1 composite of:
  1. Spread score   – wide bid/ask spread relative to midpoint
  2. Liquidity score – low 24h volume and thin orderbook
  3. Skew score      – yes_bid far from complement of no_bid (internal inconsistency)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MarketSignal:
    ticker: str
    title: str
    category: str
    yes_bid: float          # cents (0–99)
    yes_ask: float
    no_bid: float
    no_ask: float
    volume_24h: int
    open_interest: int
    spread: float           # yes_ask - yes_bid in cents
    midpoint: float         # (yes_bid + yes_ask) / 2
    skew: float             # |yes_bid - (100 - no_ask)| — internal inconsistency
    anomaly_score: float    # composite 0–1
    flags: list[str] = field(default_factory=list)
    close_time: Optional[str] = None


def _spread_score(spread: float, midpoint: float) -> float:
    """Higher score for larger spread relative to midpoint."""
    if midpoint <= 0:
        return 0.0
    # A 20-cent spread on a 50-cent market is significant
    relative = spread / max(midpoint, 1)
    return min(relative / 0.5, 1.0)   # saturates at 50% relative spread


def _liquidity_score(volume_24h: int, open_interest: int, max_vol: int) -> float:
    """Higher score for lower volume (more illiquid)."""
    vol_score = 1.0 - min(volume_24h / max(max_vol, 1), 1.0)
    oi_score = 1.0 - min(open_interest / max(max_vol * 5, 1), 1.0)
    return 0.6 * vol_score + 0.4 * oi_score


def _skew_score(yes_bid: float, no_ask: float) -> float:
    """
    On a fair book: yes_bid + no_ask should equal ~100.
    A gap means the market maker left a pricing inconsistency.
    """
    gap = abs(yes_bid + no_ask - 100)
    return min(gap / 20.0, 1.0)   # saturates at 20-cent gap


def score_market(market: dict, volume_threshold: int = 500) -> Optional[MarketSignal]:
    """
    Given a raw Kalshi market dict, return a MarketSignal if scoreable, else None.
    """
    ticker = market.get("ticker", "")

    yes_bid = market.get("yes_bid", 0) or 0
    yes_ask = market.get("yes_ask", 0) or 0
    no_bid = market.get("no_bid", 0) or 0
    no_ask = market.get("no_ask", 0) or 0
    volume_24h = market.get("volume_24h", 0) or 0
    open_interest = market.get("open_interest", 0) or 0

    # Skip markets with no active pricing on either side
    if yes_ask == 0 or no_ask == 0:
        return None

    spread = yes_ask - yes_bid
    midpoint = (yes_bid + yes_ask) / 2.0
    skew = abs(yes_bid + no_ask - 100)

    s_score = _spread_score(spread, midpoint)
    l_score = _liquidity_score(volume_24h, open_interest, volume_threshold)
    k_score = _skew_score(yes_bid, no_ask)

    # Weighted composite
    anomaly_score = round(0.40 * s_score + 0.35 * l_score + 0.25 * k_score, 3)

    flags: list[str] = []
    if spread >= 10:
        flags.append(f"wide-spread ({spread}¢)")
    if volume_24h <= volume_threshold:
        flags.append(f"low-volume ({volume_24h})")
    if skew >= 5:
        flags.append(f"price-skew ({skew:.1f}¢ gap)")

    return MarketSignal(
        ticker=ticker,
        title=market.get("title", ticker),
        category=market.get("category", ""),
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        volume_24h=volume_24h,
        open_interest=open_interest,
        spread=spread,
        midpoint=midpoint,
        skew=skew,
        anomaly_score=anomaly_score,
        flags=flags,
        close_time=market.get("close_time"),
    )


def find_anomalies(
    markets: list[dict],
    min_score: float = 0.5,
    volume_threshold: int = 500,
    spread_threshold: float = 10.0,
    min_volume: int = 1,
) -> list[MarketSignal]:
    """
    Score all markets and return those that exceed min_score,
    sorted by anomaly_score descending.
    """
    signals: list[MarketSignal] = []
    for m in markets:
        sig = score_market(m, volume_threshold=volume_threshold)
        if sig and sig.volume_24h < min_volume:
            continue
        if sig and sig.anomaly_score >= min_score:
            signals.append(sig)
        # Also include any market that meets the spread threshold even if score is lower
        elif sig and sig.spread >= spread_threshold:
            sig.flags.append("spread-threshold")
            signals.append(sig)

    signals.sort(key=lambda s: s.anomaly_score, reverse=True)
    return signals
