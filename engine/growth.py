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


def _ebitda(year_data: dict) -> float:
    return year_data.get("op", 0) + year_data.get("dep", 0) + year_data.get("amort", 0)


def calc_ebitda_growth(consolidated: dict[int, dict]) -> float | None:
    """Compute EBITDA growth using longest available CAGR (up to 3 years).

    Uses multi-year CAGR instead of 1-year trailing to reduce single-year outlier noise.
    Falls back to 1-year YoY when only 2 years of data exist.
    Returns None if insufficient or negative EBITDA data.
    """
    years = sorted(consolidated.keys())
    if len(years) < 2:
        return None

    # Prefer 3-year CAGR (years[-3] -> years[-1]) when available
    if len(years) >= 3:
        start_yr, end_yr = years[-3], years[-1]
        n_years = end_yr - start_yr
        ebitda_start = _ebitda(consolidated[start_yr])
        ebitda_end = _ebitda(consolidated[end_yr])
        if ebitda_start > 0 and ebitda_end > 0 and n_years > 0:
            return round((ebitda_end / ebitda_start) ** (1 / n_years) - 1, 4)

    # Fallback: 1-year YoY
    prev_yr, last_yr = years[-2], years[-1]
    ebitda_prev = _ebitda(consolidated[prev_yr])
    ebitda_last = _ebitda(consolidated[last_yr])
    if ebitda_prev <= 0 or ebitda_last <= 0:
        return None
    return round(ebitda_last / ebitda_prev - 1, 4)


# Clamping range
_GROWTH_FLOOR = 0.02
_GROWTH_CAP = 0.30

# Deeply negative threshold: below this, trailing data is too distorted to use as Y1
# (e.g. Tesla 2023-2025 CAGR ~ -10% due to margin compression, not structural decline)
_NEGATIVE_OUTLIER_THRESHOLD = -0.05

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
      1. industry provided -> industry base-rate (outside view, Damodaran)
      2. no industry, trailing CAGR >= -5% -> clamped multi-year CAGR
      3. no industry, trailing CAGR < -5% (deeply negative outlier)
         -> fallback_start (inside-view suppressed, outside view used)
      4. no data -> fallback_start
    Yn: market-specific GDP-linked convergence target
    Intermediate years: linear interpolation
    """
    fade_end = _FADE_END.get(market, _FADE_END_DEFAULT)

    category = classify_industry(industry)
    if industry:
        # Outside view: use industry base-rate regardless of trailing performance
        fade_start = _INDUSTRY_BASE_RATE[category]
    else:
        cagr = calc_ebitda_growth(consolidated)
        if cagr is not None:
            if cagr < _NEGATIVE_OUTLIER_THRESHOLD:
                # Deeply negative trailing: single-period distortion likely
                # Use fallback (outside view) to avoid locking in temporary trough
                fade_start = fallback_start
            else:
                fade_start = max(_GROWTH_FLOOR, min(cagr, _GROWTH_CAP))
        else:
            fade_start = fallback_start

    # Prevent reverse fade (Y1 < Yn is meaningless)
    if fade_start < fade_end:
        fade_start = fade_end

    return linear_fade(fade_start, fade_end, n)
