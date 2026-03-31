"""Currency unit detection and per-share value conversion -- pure functions."""


def detect_unit(revenue: int, market: str) -> tuple[str, int]:
    """Auto-determine display unit based on financial statement scale.

    Args:
        revenue: Revenue (internal storage unit: millions KRW or $M)
        market: "KR" | "US"

    Returns:
        (display_label, unit_multiplier)
        - KR: revenue < 10,000 (under 10B KRW) -> ("백만원", 1_000_000)
              revenue 10,000~1,000,000 (10B~1T KRW) -> ("억원", 100_000_000)
              revenue > 1,000,000 (over 1T KRW) -> ("백만원", 1_000_000)
        - US: always ("$M", 1_000_000)
    """
    if market == "US":
        return "$M", 1_000_000

    # KR market
    if revenue < 10_000:
        return "백만원", 1_000_000
    elif revenue <= 1_000_000:
        return "억원", 100_000_000
    else:
        return "백만원", 1_000_000


def per_share(equity: int, unit_multiplier: int, shares: int) -> int:
    """Convert equity value to per-share value.

    Args:
        equity: Equity value (in display unit)
        unit_multiplier: KRW/$ per display unit (e.g., 1_000_000 for millions)
        shares: Number of shares outstanding

    Returns:
        Per-share value (KRW or $)
    """
    if equity <= 0 or shares <= 0:
        return 0
    return round(equity * unit_multiplier / shares)
