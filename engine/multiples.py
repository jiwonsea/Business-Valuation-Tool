"""멀티플 교차검증 엔진 — EV/EBITDA 외 다중 밸류에이션 방법론.

SOTP(EV/EBITDA) 외에 EV/Revenue, P/E, P/BV로 교차검증하여
Football Field 범위를 확장한다.
"""

from dataclasses import dataclass

from .units import per_share as _per_share


@dataclass
class MultipleValuation:
    method: str  # "EV/EBITDA", "EV/Revenue", "P/E", "P/BV"
    metric_value: float  # 적용 지표값 (EBITDA, Revenue 등)
    multiple: float  # 적용 배수
    enterprise_value: int  # EV (or equity value for P/E, P/BV)
    equity_value: int  # EV - net debt (EV methods) or direct
    per_share: int  # 주당 가치


def calc_ev_revenue(
    revenue: int,
    multiple: float,
    net_debt: int,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """EV/Revenue 방법."""
    ev = round(revenue * multiple)
    equity = ev - net_debt
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="EV/Revenue", metric_value=revenue, multiple=multiple,
        enterprise_value=ev, equity_value=equity, per_share=ps,
    )


def calc_pe(
    net_income: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/E 방법 (직접 Equity Value)."""
    equity = round(net_income * multiple) if net_income > 0 else 0
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="P/E", metric_value=net_income, multiple=multiple,
        enterprise_value=0, equity_value=equity, per_share=ps,
    )


def calc_pbv(
    book_value: int,
    multiple: float,
    shares: int,
    unit_multiplier: int = 1_000_000,
) -> MultipleValuation:
    """P/BV 방법 (직접 Equity Value)."""
    equity = round(book_value * multiple)
    ps = _per_share(equity, unit_multiplier, shares)
    return MultipleValuation(
        method="P/BV", metric_value=book_value, multiple=multiple,
        enterprise_value=0, equity_value=equity, per_share=ps,
    )


def cross_validate(
    revenue: int,
    ebitda: int,
    net_income: int,
    book_value: int,
    net_debt: int,
    shares: int,
    sotp_ev: int,
    dcf_ev: int,
    ev_revenue_multiple: float = 0,
    pe_multiple: float = 0,
    pbv_multiple: float = 0,
    unit_multiplier: int = 1_000_000,
) -> list[MultipleValuation]:
    """다중 방법론 교차검증 결과 리스트.

    Args:
        revenue, ebitda, net_income, book_value: 재무 지표 (단위: 백만원/$M)
        net_debt: 순차입금
        shares: 주식수
        sotp_ev, dcf_ev: 기존 SOTP/DCF EV
        ev_revenue_multiple: EV/Revenue 배수 (0이면 implied 역산)
        pe_multiple: P/E 배수 (0이면 스킵)
        pbv_multiple: P/BV 배수 (0이면 스킵)

    Returns:
        [MultipleValuation, ...] (SOTP, DCF 포함)
    """
    results = []

    # 1. SOTP (기존)
    sotp_equity = sotp_ev - net_debt
    sotp_ps = _per_share(sotp_equity, unit_multiplier, shares)
    implied_ev_ebitda = round(sotp_ev / ebitda, 1) if ebitda > 0 else 0
    results.append(MultipleValuation(
        method="SOTP (EV/EBITDA)", metric_value=ebitda, multiple=implied_ev_ebitda,
        enterprise_value=sotp_ev, equity_value=sotp_equity, per_share=sotp_ps,
    ))

    # 2. DCF (기존)
    dcf_equity = dcf_ev - net_debt
    dcf_ps = _per_share(dcf_equity, unit_multiplier, shares)
    results.append(MultipleValuation(
        method="DCF (FCFF)", metric_value=ebitda, multiple=0,
        enterprise_value=dcf_ev, equity_value=dcf_equity, per_share=dcf_ps,
    ))

    # 3. EV/Revenue
    if ev_revenue_multiple > 0 and revenue > 0:
        results.append(calc_ev_revenue(revenue, ev_revenue_multiple, net_debt, shares, unit_multiplier))

    # 4. P/E
    if pe_multiple > 0 and net_income > 0:
        results.append(calc_pe(net_income, pe_multiple, shares, unit_multiplier))

    # 5. P/BV
    if pbv_multiple > 0 and book_value > 0:
        results.append(calc_pbv(book_value, pbv_multiple, shares, unit_multiplier))

    return results
