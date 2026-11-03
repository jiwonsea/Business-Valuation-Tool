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


def per_share(equity: int, unit_multiplier: int, shares: int) -> float:
    """Convert equity value to per-share value.

    Args:
        equity: Equity value (in display unit)
        unit_multiplier: KRW/$ per display unit (e.g., 1_000_000 for millions)
        shares: Number of shares outstanding

    Returns:
        Per-share value (KRW or $)
    """
    if shares <= 0:
        return 0.0
    return equity * unit_multiplier / shares


def display_decimals(currency: str) -> int:
    """Display precision only; calculation precision is independent."""
    return 0 if currency in {"KRW", "JPY"} else 2


def currency_symbol(currency: str) -> str:
    """Return a display symbol without inferring currency from listing market."""
    return {"KRW": "원", "USD": "$", "JPY": "¥", "EUR": "€"}.get(currency, currency)


def format_per_share(value: float, currency: str) -> str:
    """Format native per-share values with explicit half-up display rounding."""
    from decimal import Decimal, ROUND_HALF_UP

    decimals = display_decimals(currency)
    rounded = Decimal(str(value)).quantize(
        Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP
    )
    return f"{rounded:,.{decimals}f}"
