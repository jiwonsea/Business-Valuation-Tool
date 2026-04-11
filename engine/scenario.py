"""Scenario analysis engine."""

from schemas.models import AdjustmentItem, ScenarioParams, ScenarioResult
from .units import per_share


def calc_scenario(
    sc: ScenarioParams,
    total_ev: int,
    net_debt: int,
    eco_frontier: int,
    cps_principal: int,
    cps_years: int,
    rcps_principal: int = 0,
    rcps_years: int = 0,
    unit_multiplier: int = 1_000_000,
    cps_dividend_rate: float = 0.0,
    rcps_dividend_rate: float = 0.0,
) -> ScenarioResult:
    """Compute equity value and per-share value for each scenario.

    CPS/RCPS redemption logic:
      - Manual override (cps_repay/rcps_repay not None) takes priority.
      - When dividend_rate > 0, dividends are already paid out to investors,
        so effective compound rate = max(IRR - dividend_rate, 0).
      - CPS (zero-coupon): compound IRR — principal × (1+IRR)^years.
      - RCPS (dividend-paying): effective_rate = max(IRR - dividend_rate, 0).
    """
    # Calculate CPS redemption amount
    if sc.cps_repay is not None:
        cps_repay = sc.cps_repay
    elif cps_principal > 0:
        effective_rate = max((sc.irr or 0) - cps_dividend_rate, 0.0)
        cps_repay = round(cps_principal * (1 + effective_rate / 100) ** cps_years)
    else:
        cps_repay = 0

    # Calculate RCPS redemption amount (dividend_rate reduces effective compound rate)
    if sc.rcps_repay is not None:
        rcps_repay = sc.rcps_repay
    elif rcps_principal > 0:
        effective_rate = max((sc.irr or 0) - rcps_dividend_rate, 0.0)
        rcps_repay = round(rcps_principal * (1 + effective_rate / 100) ** rcps_years)
    else:
        rcps_repay = 0
    buyback = sc.buyback

    # Build dynamic equity bridge adjustment items
    adjustments: list[AdjustmentItem] = []
    if net_debt:
        adjustments.append(AdjustmentItem(name="순차입금", value=net_debt))
    if cps_repay:
        adjustments.append(AdjustmentItem(name="CPS 상환", value=cps_repay))
    if rcps_repay:
        adjustments.append(AdjustmentItem(name="RCPS 상환", value=rcps_repay))
    if buyback:
        adjustments.append(AdjustmentItem(name="자사주 매입", value=buyback))
    if eco_frontier:
        adjustments.append(AdjustmentItem(name="기타 차감", value=eco_frontier))

    # Equity bridge calculation
    total_claims = sum(a.value for a in adjustments)
    equity_value = total_ev - total_claims

    # Per-share value (negative equity propagates for distress scenarios)
    pre_dlom = per_share(equity_value, unit_multiplier, sc.shares)
    if equity_value > 0:
        post_dlom = round(pre_dlom * (1 - sc.dlom / 100))
    else:
        # DLOM not applied to negative equity (limited liability: floor at negative value)
        post_dlom = pre_dlom

    weighted = round(post_dlom * sc.prob / 100)

    return ScenarioResult(
        total_ev=total_ev,
        net_debt=net_debt,
        cps_repay=cps_repay,
        rcps_repay=rcps_repay,
        buyback=buyback,
        eco_frontier=eco_frontier,
        equity_value=equity_value,
        shares=sc.shares,
        pre_dlom=pre_dlom,
        post_dlom=post_dlom,
        weighted=weighted,
        adjustments=adjustments,
    )
