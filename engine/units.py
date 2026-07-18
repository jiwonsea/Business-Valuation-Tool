"""Currency unit detection and per-share value conversion -- pure functions."""


def detect_unit(revenue: int, market: str) -> tuple[str, int]:
    """Return the default display label and arithmetic unit multiplier.

    Args:
        revenue: Revenue in the engine's internal millions unit. Kept for API
            compatibility; revenue scale must not change the storage unit.
        market: "KR" | "US" | "JP"

    Returns:
        (display_label, unit_multiplier)
        - KR: ("백만원", 1_000_000)
        - US: always ("$M", 1_000_000)
        - JP: always ("百万円", 1_000_000)

    Profiles that truly store values in a different unit must declare an
    explicit ``company.unit_multiplier``. A display label never changes the
    arithmetic multiplier.
    """
    if market == "US":
        return "$M", 1_000_000
    if market == "JP":
        return "百万円", 1_000_000

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
    if shares <= 0:
        return 0
    return round(equity * unit_multiplier / shares)
