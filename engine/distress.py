"""Financial distress discount for SOTP multiples -- pure functions, no IO.

Computes a haircut factor (0.0 to ~0.35) based on consolidated financial health.
Applied to peer-based EV/EBITDA multiples before SOTP calculation so that
distressed companies are not valued at healthy-peer multiples.

Signals used (each contributes independently, capped at max_discount):
  1. D/E ratio stress  — high leverage vs market-specific norms
  2. Consecutive losses — negative net income trend
  3. Interest coverage  — EBITDA / interest expense

Returns a DistressResult with the composite discount and per-signal breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass


# Cyclical industries: single-year loss is expected during downcycles
_CYCLICAL_KEYWORDS = frozenset(
    {
        "auto",
        "automotive",
        "automobile",
        "steel",
        "metals",
        "shipping",
        "marine",
        "semiconductor",
        "semiconductors",
        "oil",
        "oil & gas",
        "upstream",
        "refining",
        "mining",
        "construction",
        "chemical",
        "chemicals",
    }
)

# Market-specific D/E thresholds (Korean chaebol routinely operate at 150-300%)
_DE_THRESHOLDS = {
    "KR": {"start": 150, "max_at": 300, "max_penalty": 0.15},
    "US": {"start": 80, "max_at": 200, "max_penalty": 0.15},
}
_DE_DEFAULT = _DE_THRESHOLDS["US"]


@dataclass(frozen=True)
class DistressResult:
    """Distress discount computation result."""

    discount: float  # 0.0 (healthy) to max_discount (severe distress)
    de_penalty: float  # D/E ratio contribution
    loss_penalty: float  # Consecutive loss contribution
    icr_penalty: float  # Interest coverage contribution
    applied: bool  # Whether discount > 0 (for reporting)
    detail: str  # Human-readable summary (Korean)


def calc_distress_discount(
    consolidated: dict[int, dict],
    base_year: int,
    max_discount: float = 0.25,
    market: str = "US",
    kd_pre: float = 5.0,
    industry: str = "",
) -> DistressResult:
    """Calculate financial distress discount from consolidated data.

    Args:
        consolidated: {year: {"de_ratio", "net_income", "dep", "amort", "op",
                              "gross_borr", ...}}
        base_year: The valuation base year
        max_discount: Maximum total discount (default 25%). Empirical basis:
            Damodaran distress discount studies show public-company peer-multiple
            haircuts cluster at 20-25% (median) and ~30% (90th percentile).
            35% applies only to near-bankruptcy proceedings, not going-concern SOTP.
            Override via ValuationInput.distress_max_discount if needed.
        market: "KR" or "US" — affects D/E threshold
        kd_pre: Pre-tax cost of debt (%) from wacc_params

    Returns:
        DistressResult with composite discount and breakdown.
    """
    base = consolidated.get(base_year)
    if base is None:
        return DistressResult(0.0, 0.0, 0.0, 0.0, False, "")

    years = sorted(consolidated.keys())

    # ── Signal 1: D/E ratio stress (market-specific thresholds) ──
    de_cfg = _DE_THRESHOLDS.get(market, _DE_DEFAULT)
    de_start = de_cfg["start"]
    de_max_at = de_cfg["max_at"]
    de_max_pen = de_cfg["max_penalty"]

    de_ratio = base.get("de_ratio", 0)
    if de_ratio > de_start:
        de_penalty = min(
            (de_ratio - de_start) / (de_max_at - de_start) * de_max_pen,
            de_max_pen,
        )
    else:
        de_penalty = 0.0

    # ── Signal 2: Consecutive EBITDA losses ──
    # Use EBITDA (op + dep + amort) instead of net income to avoid penalising
    # one-off below-the-line items (tax charges, FX losses, impairments).
    loss_streak = 0
    for yr in reversed(years):
        if yr > base_year:
            continue
        d = consolidated[yr]
        ebitda_yr = d.get("op", 0) + d.get("dep", 0) + d.get("amort", 0)
        if ebitda_yr < 0:
            loss_streak += 1
        else:
            break

    is_cyclical = (
        any(kw in industry.lower() for kw in _CYCLICAL_KEYWORDS) if industry else False
    )

    if loss_streak >= 3:
        loss_penalty = 0.15
    elif loss_streak == 2:
        # Cyclical industries (shipbuilding, shipping, etc.) routinely post 2-year losses
        loss_penalty = 0.05 if is_cyclical else 0.10
    elif loss_streak == 1:
        loss_penalty = 0.0 if is_cyclical else 0.05
    else:
        loss_penalty = 0.0

    # ── Signal 3: Interest coverage ratio (EBITDA / interest expense) ──
    op = base.get("op", 0)
    dep = base.get("dep", 0)
    amort = base.get("amort", 0)
    ebitda = op + dep + amort
    gross_borr = base.get("gross_borr", 0)
    # Prefer actual interest expense from financial statements; fall back to estimate.
    # yfinance (US) provides it directly; DART (KR) extracts it when available.
    actual_ie = base.get("interest_expense", 0)
    if actual_ie > 0:
        interest_expense = actual_ie
    elif gross_borr > 0:
        interest_expense = gross_borr * kd_pre / 100
    else:
        interest_expense = 0

    if interest_expense > 0 and ebitda > 0:
        icr = ebitda / interest_expense
        if icr < 2.0:
            icr_penalty = 0.10
        elif icr < 4.0:
            icr_penalty = 0.05
        else:
            icr_penalty = 0.0
    elif ebitda <= 0 and gross_borr > 0:
        icr_penalty = 0.10  # Negative EBITDA with debt = severe
    else:
        icr_penalty = 0.0

    # ── Composite ──
    raw = de_penalty + loss_penalty + icr_penalty
    discount = min(raw, max_discount)

    # Detail string
    parts = []
    if de_penalty > 0:
        parts.append(f"D/E {de_ratio:.0f}% (−{de_penalty:.0%})")
    if loss_penalty > 0:
        parts.append(f"연속EBITDA적자 {loss_streak}년 (−{loss_penalty:.0%})")
    if icr_penalty > 0:
        icr_val = (
            ebitda / interest_expense if interest_expense > 0 and ebitda > 0 else 0
        )
        parts.append(f"ICR {icr_val:.1f}x (−{icr_penalty:.0%})")

    if parts:
        detail = f"Distress haircut −{discount:.0%}: " + ", ".join(parts)
    else:
        detail = ""

    return DistressResult(
        discount=round(discount, 4),
        de_penalty=round(de_penalty, 4),
        loss_penalty=round(loss_penalty, 4),
        icr_penalty=round(icr_penalty, 4),
        applied=discount > 0,
        detail=detail,
    )


def apply_distress_discount(
    multiples: dict[str, float],
    discount: float,
    exempt_segments: set[str] | None = None,
    healthy_segments: set[str] | None = None,
) -> dict[str, float]:
    """Apply distress discount to segment multiples.

    Three tiers:
      - exempt: no discount (ev_revenue, distress_exempt)
      - healthy: half discount (profitable segment in diversified company)
      - default: full discount

    Args:
        multiples: {segment_code: multiple}
        discount: 0.0 to max_discount
        exempt_segments: codes fully exempt (e.g., ev_revenue segments)
        healthy_segments: codes getting half discount (profitable + high asset share)

    Returns:
        New dict with discounted multiples (originals unchanged).
    """
    if discount <= 0:
        return multiples
    exempt = exempt_segments or set()
    healthy = healthy_segments or set()
    result = {}
    for code, m in multiples.items():
        if code in exempt:
            result[code] = m
        elif code in healthy:
            result[code] = round(m * (1.0 - discount * 0.5), 2)
        else:
            result[code] = round(m * (1.0 - discount), 2)
    return result
