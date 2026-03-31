"""잔여이익모델(RIM: Residual Income Model) 엔진 — 순수 함수.

금융업종(은행, 보험, 증권 등) 특화 밸류에이션.
Value = BV₀ + Σ RIₜ / (1+kₑ)ᵗ
여기서 RIₜ = (ROE − kₑ) × BVₜ₋₁
"""

from dataclasses import dataclass


@dataclass
class RIMProjection:
    """연도별 RIM 예측."""
    year: int
    bv: int          # 기초 장부가치 (표시 단위)
    net_income: int   # 당기순이익 (표시 단위)
    roe: float        # ROE (%)
    ri: int           # 잔여이익 (표시 단위)
    pv_ri: int        # 잔여이익 현재가치


@dataclass
class RIMResult:
    """RIM 밸류에이션 결과."""
    bv_current: int           # 현재 장부가치
    ke: float                 # 자기자본비용 (%)
    terminal_growth: float    # 영구성장률 (%)
    projections: list[RIMProjection]
    pv_ri_sum: int            # 예측기간 RI 현재가치 합계
    terminal_ri: int          # 잔여이익 Terminal Value
    pv_terminal: int          # TV 현재가치
    equity_value: int         # 총 자기자본가치 (BV + PV(RI) + PV(TV))
    per_share: int            # 주당 가치


def calc_rim(
    book_value: int,
    roe_forecasts: list[float],
    ke: float,
    terminal_growth: float = 0.0,
    shares: int = 1,
    unit_multiplier: int = 1_000_000,
    payout_ratio: float = 0.0,
) -> RIMResult:
    """RIM 밸류에이션 계산.

    Args:
        book_value: 현재 자기자본 장부가치 (표시 단위, e.g. 백만원)
        roe_forecasts: 예측기간 ROE 리스트 (%, e.g. [12.0, 11.5, 11.0, 10.5, 10.0])
        ke: 자기자본비용 (%, e.g. 10.0)
        terminal_growth: RI 영구성장률 (%, e.g. 0.0 — 보수적 추정)
        shares: 발행주식수
        unit_multiplier: 1표시단위 = 몇 원/$
        payout_ratio: 배당성향 (%, e.g. 30.0). 0이면 clean surplus 가정 (이익 전액 BV 유보).

    Returns:
        RIMResult
    """
    k = ke / 100
    g = terminal_growth / 100
    payout = payout_ratio / 100

    if k <= g:
        raise ValueError(
            f"Ke({ke}%) must be greater than terminal_growth({terminal_growth}%). "
            "RIM terminal value is not finite when growth >= cost of equity."
        )

    projections = []
    bv = book_value
    pv_sum = 0

    for i, roe_pct in enumerate(roe_forecasts):
        roe = roe_pct / 100
        ni = round(bv * roe)
        ri = round(bv * (roe - k))
        discount = (1 + k) ** (i + 1)
        pv_ri = round(ri / discount)
        pv_sum += pv_ri

        projections.append(RIMProjection(
            year=i + 1,
            bv=bv,
            net_income=ni,
            roe=roe_pct,
            ri=ri,
            pv_ri=pv_ri,
        ))

        # 장부가치 갱신: BV_{t} = BV_{t-1} + NI - Dividends
        dividends = round(ni * payout)
        bv = bv + ni - dividends

    # Terminal Value: last RI × (1+g) / (ke - g)
    last_ri = projections[-1].ri if projections else 0
    if k > g and last_ri != 0:
        terminal_ri_next = round(last_ri * (1 + g))
        terminal_value = round(terminal_ri_next / (k - g))
    else:
        terminal_ri_next = 0
        terminal_value = 0

    n = len(projections)
    pv_terminal = round(terminal_value / (1 + k) ** n) if n > 0 else 0

    equity_value = book_value + pv_sum + pv_terminal
    ps = round(equity_value * unit_multiplier / shares) if shares > 0 else 0

    return RIMResult(
        bv_current=book_value,
        ke=ke,
        terminal_growth=terminal_growth,
        projections=projections,
        pv_ri_sum=pv_sum,
        terminal_ri=terminal_value,
        pv_terminal=pv_terminal,
        equity_value=equity_value,
        per_share=ps,
    )
