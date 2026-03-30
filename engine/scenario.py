"""시나리오 분석 엔진."""

from schemas.models import ScenarioParams, ScenarioResult


def calc_scenario(
    sc: ScenarioParams,
    total_ev: int,
    net_debt: int,
    eco_frontier: int,
    cps_principal: int,
    cps_years: int,
) -> ScenarioResult:
    """시나리오별 Equity Value 및 주당 가치 산출."""
    # CPS 상환액 계산
    if sc.cps_repay is not None:
        cps_repay = sc.cps_repay
    elif sc.irr is not None:
        cps_repay = round(cps_principal * (1 + sc.irr / 100) ** cps_years)
    else:
        cps_repay = 0

    rcps_repay = sc.rcps_repay
    buyback = sc.buyback

    # Equity bridge
    total_claims = net_debt + cps_repay + rcps_repay + buyback + eco_frontier
    equity_value = total_ev - total_claims

    # 주당 가치
    if equity_value > 0:
        pre_dlom = round(equity_value * 1_000_000 / sc.shares)
        post_dlom = round(pre_dlom * (1 - sc.dlom / 100))
    else:
        pre_dlom = 0
        post_dlom = 0

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
    )
