"""배당할인모델(DDM) — Gordon Growth Model 기반 순수 함수.

Total Payout DDM: 자사주매입을 포함한 총주주환원 기반 평가 지원.
"""

from dataclasses import dataclass


@dataclass
class DDMResult:
    """DDM 밸류에이션 결과."""
    dps: float  # 주당 배당금
    buyback_per_share: float  # 주당 자사주매입 환원액
    total_payout: float  # 주당 총환원 (DPS + buyback)
    growth: float  # 성장률 (%)
    ke: float  # 자기자본비용 (%)
    equity_per_share: int  # 주당 내재가치


def calc_ddm(
    dps: float,
    growth: float,
    ke: float,
    buyback_per_share: float = 0.0,
) -> DDMResult:
    """Gordon Growth DDM (Total Payout 지원).

    주당가치 = TotalPayout × (1+g) / (Ke - g)
    TotalPayout = DPS + 주당 자사주매입 환원액

    미국 금융주는 자사주매입 비중이 높아 DPS만으로는 과소평가됨.
    buyback_per_share > 0이면 Total Shareholder Yield 모델로 작동.

    Args:
        dps: 주당 배당금 (원 or $)
        growth: 배당/환원 성장률 (%, e.g., 3.0 = 3%)
        ke: 자기자본비용 (%, e.g., 10.0 = 10%)
        buyback_per_share: 주당 자사주매입 환원액 (원 or $, 기본 0)

    Returns:
        DDMResult with equity_per_share
    """
    g = growth / 100
    k = ke / 100

    if k <= g:
        raise ValueError(
            f"Ke({ke}%) must be greater than growth({growth}%). "
            "DDM is not applicable when growth >= cost of equity."
        )

    total_payout = dps + buyback_per_share
    value = total_payout * (1 + g) / (k - g)
    return DDMResult(
        dps=dps,
        buyback_per_share=buyback_per_share,
        total_payout=total_payout,
        growth=growth,
        ke=ke,
        equity_per_share=round(value),
    )
