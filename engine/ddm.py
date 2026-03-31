"""배당할인모델(DDM) — Gordon Growth Model 기반 순수 함수."""

from dataclasses import dataclass


@dataclass
class DDMResult:
    """DDM 밸류에이션 결과."""
    dps: float  # 주당 배당금
    growth: float  # 배당 성장률 (%)
    ke: float  # 자기자본비용 (%)
    equity_per_share: int  # 주당 내재가치


def calc_ddm(
    dps: float,
    growth: float,
    ke: float,
) -> DDMResult:
    """Gordon Growth DDM: 주당가치 = DPS × (1+g) / (Ke - g).

    Args:
        dps: 주당 배당금 (원 or $)
        growth: 배당 성장률 (%, e.g., 3.0 = 3%)
        ke: 자기자본비용 (%, e.g., 10.0 = 10%)

    Returns:
        DDMResult with equity_per_share

    Raises:
        ValueError: ke <= growth (영구 성장이 할인율 이상이면 모델 불가)
    """
    g = growth / 100
    k = ke / 100

    if k <= g:
        raise ValueError(
            f"Ke({ke}%) must be greater than growth({growth}%). "
            "DDM is not applicable when growth >= cost of equity."
        )

    value = dps * (1 + g) / (k - g)
    return DDMResult(
        dps=dps,
        growth=growth,
        ke=ke,
        equity_per_share=round(value),
    )
