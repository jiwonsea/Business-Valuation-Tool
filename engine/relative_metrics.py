"""Relative valuation ratios -- diagnostic multiples, justified multiples, PEG/PEGY.

Pure functions (no IO, no state). Complements the intrinsic-value engines
(DCF/SOTP/rNPV/DDM/RIM/NAV) with a *diagnostic* relative-valuation layer:

  Tier 1  Current-price ratios (P/E, P/B, EV/EBITDA, EV/Sales, dividend yield)
  Tier 2  PEG / PEGY with sector guardrails
  Tier 3  Justified multiples (fundamental-consistent P/E, P/B) + verdict

Design intent (see CLAUDE.md "reverse-DCF / decode market assumptions" ethos):
these ratios are NOT new primary valuation methods. They are a context/sanity
layer. PEG in particular is unreliable for financials, cyclicals, and
low/negative-growth names -- those cases return status="na" or "caution"
rather than a misleading number.

Units convention (matches the rest of engine/): growth, ROE, ke, and dividend
yield are all passed as PERCENTAGES (e.g. 12.5 for 12.5%). Monetary metrics
(market_cap, net_debt, ebitda, revenue, net_income, book_value) are in the
model's display unit; ratios are scale-invariant so the unit cancels.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Status vocabulary
OK = "ok"  # metric is meaningful
CAUTION = "caution"  # computed, but interpret with care (reason in .note)
NA = "na"  # not meaningful -- value is None

# Default guardrail thresholds
_MIN_PEG_GROWTH_PCT = 2.0  # below this, PEG denominator is unreliable
_MIN_KE_G_SPREAD = 0.005  # 0.5% minimum ke-g spread for justified multiples
_JUSTIFIED_BAND = 0.15  # +/-15% band around fair value for the verdict


@dataclass
class RelativeMetric:
    """A single diagnostic ratio with an interpretability status."""

    name: str
    value: Optional[float]
    status: str  # OK | CAUTION | NA
    note: str = ""  # reason for na/caution, growth source, etc.

    @property
    def is_meaningful(self) -> bool:
        return self.status != NA and self.value is not None


# ─────────────────────────────────────────────────────────────────────────
# Tier 1 -- current-price diagnostic ratios
# ─────────────────────────────────────────────────────────────────────────


def trailing_pe(price: float, eps: float) -> RelativeMetric:
    """P/E = price / trailing EPS. NA when EPS <= 0 (P/E meaningless)."""
    if eps is None or eps <= 0:
        return RelativeMetric("P/E", None, NA, "이익 0 이하 -- P/E 무의미")
    return RelativeMetric("P/E", round(price / eps, 2), OK)


def forward_pe(price: float, forward_eps: Optional[float]) -> RelativeMetric:
    """Forward P/E = price / forward EPS."""
    if forward_eps is None or forward_eps <= 0:
        return RelativeMetric("Fwd P/E", None, NA, "예상 EPS 없음/음수")
    return RelativeMetric("Fwd P/E", round(price / forward_eps, 2), OK)


def price_to_book(price: float, book_value_per_share: float) -> RelativeMetric:
    """P/B = price / BVPS. Negative book value flagged (distress)."""
    if book_value_per_share is None or book_value_per_share == 0:
        return RelativeMetric("P/B", None, NA, "주당순자산 데이터 없음")
    if book_value_per_share < 0:
        return RelativeMetric("P/B", None, NA, "자본잠식(BVPS<0)")
    return RelativeMetric("P/B", round(price / book_value_per_share, 2), OK)


def ev_ebitda(market_cap: float, net_debt: float, ebitda: float) -> RelativeMetric:
    """EV/EBITDA where EV = market cap + net debt."""
    if ebitda is None or ebitda <= 0:
        return RelativeMetric("EV/EBITDA", None, NA, "EBITDA 0 이하")
    ev = market_cap + net_debt
    return RelativeMetric("EV/EBITDA", round(ev / ebitda, 2), OK)


def ev_sales(market_cap: float, net_debt: float, revenue: float) -> RelativeMetric:
    """EV/Sales where EV = market cap + net debt."""
    if revenue is None or revenue <= 0:
        return RelativeMetric("EV/Sales", None, NA, "매출 데이터 없음")
    ev = market_cap + net_debt
    return RelativeMetric("EV/Sales", round(ev / revenue, 2), OK)


def dividend_yield(dps: float, price: float) -> RelativeMetric:
    """Dividend yield % = DPS / price * 100. 0 dividend -> 0.0 (OK, informative)."""
    if price is None or price <= 0:
        return RelativeMetric("Div Yield", None, NA, "가격 데이터 없음")
    dps = dps or 0.0
    return RelativeMetric("Div Yield", round(dps / price * 100, 2), OK)


# ─────────────────────────────────────────────────────────────────────────
# Tier 2 -- PEG / PEGY with sector guardrails
# ─────────────────────────────────────────────────────────────────────────


def peg(
    pe: Optional[float],
    growth_pct: Optional[float],
    *,
    is_financial: bool = False,
    is_cyclical: bool = False,
    growth_source: str = "",
    min_growth_pct: float = _MIN_PEG_GROWTH_PCT,
) -> RelativeMetric:
    """PEG = P/E / expected earnings growth (%).

    Guardrails (return NA/CAUTION instead of a misleading number):
      * P/E missing or <= 0            -> NA  (negative earnings)
      * growth <= min_growth_pct       -> NA  (denominator unstable / negative)
      * financial company              -> CAUTION (PBR-ROE / RIM is preferred)
      * cyclical company               -> CAUTION (use through-cycle earnings)

    `growth_source` (e.g. "analyst consensus" / "model EBITDA CAGR") is recorded
    in the note so the reader knows what the denominator represents.
    """
    src = f" [{growth_source}]" if growth_source else ""
    if pe is None or pe <= 0:
        return RelativeMetric("PEG", None, NA, "이익 0 이하 -- PEG 무의미")
    if growth_pct is None or growth_pct <= min_growth_pct:
        return RelativeMetric(
            "PEG",
            None,
            NA,
            f"성장률 {growth_pct}% <= {min_growth_pct}% -- PEG 부적합{src}",
        )
    value = round(pe / growth_pct, 2)
    if is_financial:
        return RelativeMetric("PEG", value, CAUTION, f"금융업 -- PBR-ROE/RIM 권장{src}")
    if is_cyclical:
        return RelativeMetric(
            "PEG", value, CAUTION, f"시클리컬 -- through-cycle 이익 확인{src}"
        )
    return RelativeMetric("PEG", value, OK, f"성장률 출처{src}".strip())


def pegy(
    pe: Optional[float],
    growth_pct: Optional[float],
    dividend_yield_pct: Optional[float],
    *,
    is_financial: bool = False,
    is_cyclical: bool = False,
    growth_source: str = "",
    min_growth_pct: float = _MIN_PEG_GROWTH_PCT,
) -> RelativeMetric:
    """PEGY = P/E / (growth% + dividend yield%).

    Better suited than PEG to dividend-paying names (common in KR market):
    a low grower with a fat yield is not automatically 'expensive'. Same
    guardrails as PEG, applied to the combined denominator.
    """
    src = f" [{growth_source}]" if growth_source else ""
    if pe is None or pe <= 0:
        return RelativeMetric("PEGY", None, NA, "이익 0 이하 -- PEGY 무의미")
    g = growth_pct or 0.0
    y = dividend_yield_pct or 0.0
    denom = g + y
    if denom <= min_growth_pct:
        return RelativeMetric(
            "PEGY",
            None,
            NA,
            f"성장률+배당 {denom}% <= {min_growth_pct}% -- PEGY 부적합{src}",
        )
    value = round(pe / denom, 2)
    if is_financial:
        return RelativeMetric(
            "PEGY", value, CAUTION, f"금융업 -- PBR-ROE/RIM 권장{src}"
        )
    if is_cyclical:
        return RelativeMetric(
            "PEGY", value, CAUTION, f"시클리컬 -- through-cycle 이익 확인{src}"
        )
    return RelativeMetric("PEGY", value, OK, f"성장률 출처{src}".strip())


# ─────────────────────────────────────────────────────────────────────────
# Tier 3 -- justified (fundamental-consistent) multiples + verdict
# ─────────────────────────────────────────────────────────────────────────


def justified_pe(
    payout_ratio_pct: float,
    growth_pct: float,
    ke_pct: float,
) -> RelativeMetric:
    """Justified leading P/E = payout * (1+g) / (ke - g)  (Gordon-consistent).

    All inputs in %. Returns NA when ke - g spread is too small (blows up) or
    payout is non-positive.
    """
    if payout_ratio_pct is None or payout_ratio_pct <= 0:
        return RelativeMetric("Justified P/E", None, NA, "배당성향 0 이하")
    payout = payout_ratio_pct / 100.0
    g = (growth_pct or 0.0) / 100.0
    ke = (ke_pct or 0.0) / 100.0
    if ke - g < _MIN_KE_G_SPREAD:
        return RelativeMetric("Justified P/E", None, NA, "ke-g 스프레드 과소(<0.5%)")
    value = round(payout * (1 + g) / (ke - g), 2)
    return RelativeMetric("Justified P/E", value, OK)


def justified_pb(
    roe_pct: float,
    growth_pct: float,
    ke_pct: float,
) -> RelativeMetric:
    """Justified P/B = (ROE - g) / (ke - g).

    The intrinsic counterpart to a P/B multiple; pairs naturally with RIM for
    financials. All inputs in %.
    """
    if roe_pct is None or ke_pct is None:
        return RelativeMetric("Justified P/B", None, NA, "ROE/ke 데이터 없음")
    roe = roe_pct / 100.0
    g = (growth_pct or 0.0) / 100.0
    ke = ke_pct / 100.0
    if ke - g < _MIN_KE_G_SPREAD:
        return RelativeMetric("Justified P/B", None, NA, "ke-g 스프레드 과소(<0.5%)")
    value = round((roe - g) / (ke - g), 2)
    if value <= 0:
        return RelativeMetric("Justified P/B", None, NA, "정당 P/B 0 이하 — 해석 불가")
    return RelativeMetric("Justified P/B", value, OK)


@dataclass
class MultipleVerdict:
    """Actual multiple vs its fundamental-justified level."""

    name: str  # "P/E" | "P/B"
    actual: Optional[float]
    justified: Optional[float]
    gap_pct: Optional[float]  # (actual - justified) / justified * 100
    verdict: str  # "저평가" | "적정" | "고평가" | "판단불가"
    note: str = ""


def multiple_verdict(
    name: str,
    actual: Optional[float],
    justified: Optional[float],
    band: float = _JUSTIFIED_BAND,
) -> MultipleVerdict:
    """Compare an actual multiple to its justified level.

    verdict: actual below justified*(1-band) -> 저평가(cheap vs fundamentals);
    above justified*(1+band) -> 고평가; within band -> 적정.
    """
    if actual is None or justified is None or justified <= 0:
        return MultipleVerdict(
            name, actual, justified, None, "판단불가", "actual/justified 데이터 부족"
        )
    gap = (actual - justified) / justified * 100.0
    if actual < justified * (1 - band):
        verdict = "저평가"
    elif actual > justified * (1 + band):
        verdict = "고평가"
    else:
        verdict = "적정"
    return MultipleVerdict(name, actual, justified, round(gap, 1), verdict)


# ─────────────────────────────────────────────────────────────────────────
# Aggregator
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class RelativeValuationReport:
    """Bundle of diagnostic ratios + justified-multiple verdicts."""

    ratios: list[RelativeMetric]
    verdicts: list[MultipleVerdict]

    def meaningful_ratios(self) -> list[RelativeMetric]:
        return [m for m in self.ratios if m.is_meaningful]
