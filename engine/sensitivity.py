"""민감도 분석 엔진 — 3종 2-way 테이블."""

from schemas.models import DAAllocation, DCFParams, SensitivityRow
from .sotp import calc_sotp
from .dcf import calc_dcf


def sensitivity_multiples(
    base_ebitda_by_seg: dict[str, DAAllocation],
    multiples: dict[str, float],
    net_debt: int,
    eco_frontier: int,
    shares: int,
    row_seg: str = "HI",
    col_seg: str = "ALC",
    row_range: list[float] | None = None,
    col_range: list[float] | None = None,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """민감도: 두 부문 멀티플 변동 → Scenario A 주당 가치."""
    if row_range is None:
        row_range = [6.0, 7.0, 8.0, 9.0, 10.0]
    if col_range is None:
        col_range = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0]

    rows = []
    for row_m in row_range:
        for col_m in col_range:
            mults = dict(multiples)
            mults[row_seg] = row_m
            mults[col_seg] = col_m
            _, ev = calc_sotp(base_ebitda_by_seg, mults)
            eq = ev - net_debt - eco_frontier
            ps = round(eq * 1_000_000 / shares) if eq > 0 else 0
            rows.append(SensitivityRow(row_val=row_m, col_val=col_m, value=ps))
    return rows, row_range, col_range


def sensitivity_irr_dlom(
    total_ev: int,
    net_debt: int,
    eco_frontier: int,
    cps_principal: int,
    cps_years: int,
    rcps_repay: int,
    buyback: int,
    shares: int,
    irr_range: list[float] | None = None,
    dlom_range: list[float] | None = None,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """민감도: FI IRR × DLOM → Scenario B 주당 가치 (확률 미적용)."""
    if irr_range is None:
        irr_range = [3.0, 5.0, 8.0, 10.0, 12.0, 15.0]
    if dlom_range is None:
        dlom_range = [0, 10, 15, 20, 25, 30]

    rows = []
    for irr in irr_range:
        cps_r = round(cps_principal * (1 + irr / 100) ** cps_years)
        claims = net_debt + cps_r + rcps_repay + buyback + eco_frontier
        eq = total_ev - claims
        for dlom in dlom_range:
            if eq > 0:
                ps = round(eq * 1_000_000 / shares * (1 - dlom / 100))
            else:
                ps = 0
            rows.append(SensitivityRow(row_val=irr, col_val=dlom, value=ps))
    return rows, irr_range, dlom_range


def sensitivity_dcf(
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    params: DCFParams,
    base_year: int = 2025,
    wacc_range: list[float] | None = None,
    tg_range: list[float] | None = None,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """민감도: WACC × 영구성장률 → DCF EV (백만원)."""
    if wacc_range is None:
        wacc_range = [7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0]
    if tg_range is None:
        tg_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]

    rows = []
    for w in wacc_range:
        for tg in tg_range:
            p = params.model_copy(update={"terminal_growth": tg})
            r = calc_dcf(ebitda_base, da_base, revenue_base, w, p, base_year)
            rows.append(SensitivityRow(row_val=w, col_val=tg, value=r.ev_dcf))
    return rows, wacc_range, tg_range
