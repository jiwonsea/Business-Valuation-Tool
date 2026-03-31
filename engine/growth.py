"""Dynamic EBITDA growth rate generation -- industry base-rate + linear fade."""

from .method_selector import classify_industry


def linear_fade(start: float, end: float, n: int) -> list[float]:
    """Generate n linearly interpolated values from start to end.

    >>> linear_fade(0.12, 0.04, 5)
    [0.12, 0.10, 0.08, 0.06, 0.04]
    """
    if n <= 0:
        raise ValueError(f"n must be positive: {n}")
    if n == 1:
        return [round(start, 4)]
    step = (end - start) / (n - 1)
    return [round(start + step * i, 4) for i in range(n)]


def calc_ebitda_growth(consolidated: dict[int, dict]) -> float | None:
    """Compute trailing 1-year EBITDA growth from consolidated financials. Returns None if insufficient data.

    EBITDA = op + dep + amort. Uses the most recent trend as Y1 basis.
    """
    years = sorted(consolidated.keys())
    if len(years) < 2:
        return None

    prev_yr, last_yr = years[-2], years[-1]
    prev = consolidated[prev_yr]
    last = consolidated[last_yr]

    ebitda_prev = prev.get("op", 0) + prev.get("dep", 0) + prev.get("amort", 0)
    ebitda_last = last.get("op", 0) + last.get("dep", 0) + last.get("amort", 0)

    if ebitda_prev <= 0 or ebitda_last <= 0:
        return None

    return round(ebitda_last / ebitda_prev - 1, 4)


# Clamping range (used when industry is unspecified + YoY fallback)
_GROWTH_FLOOR = 0.02
_GROWTH_CAP = 0.30

# Market-specific convergence target (Y5)
_FADE_END = {"KR": 0.03, "US": 0.04}
_FADE_END_DEFAULT = 0.035

# Industry category Y1 base-rate (based on Damodaran 2026.1 Fundamental EBIT Growth)
# Growth: Semi 9.6%, Electronics 13.8%, Software 21.6% -> conservative median 10%
# Mature: Chemical 5.7%, Food 5.2%, Auto 3.5%, Telecom 1.4% -> median 5%
# Default: midpoint of Growth/Mature 8%
_INDUSTRY_BASE_RATE = {"growth": 0.10, "mature": 0.05, "default": 0.08}


def generate_growth_rates(
    consolidated: dict[int, dict],
    market: str = "KR",
    n: int = 5,
    fallback_start: float = 0.08,
    industry: str = "",
) -> list[float]:
    """Auto-generate EBITDA growth rate array.

    Y1 determination priority:
      1. industry provided -> industry base-rate (outside view)
      2. no industry but financial data available -> clamped YoY (backward compatible)
      3. neither available -> fallback_start
    Yn: market-specific GDP-linked convergence target
    Intermediate years: linear interpolation
    """
    fade_end = _FADE_END.get(market, _FADE_END_DEFAULT)

    category = classify_industry(industry)
    if industry:
        fade_start = _INDUSTRY_BASE_RATE[category]
    else:
        yoy = calc_ebitda_growth(consolidated)
        if yoy is not None:
            fade_start = max(_GROWTH_FLOOR, min(yoy, _GROWTH_CAP))
        else:
            fade_start = fallback_start

    # If Y1 is below convergence target, clamp to prevent reverse fade
    if fade_start < fade_end:
        fade_start = fade_end

    return linear_fade(fade_start, fade_end, n)
