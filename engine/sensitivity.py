"""민감도 분석 엔진 — 방법론별 2-way 테이블."""

from schemas.models import DAAllocation, DCFParams, SensitivityRow
from .sotp import calc_sotp
from .dcf import calc_dcf
from .ddm import calc_ddm
from .rim import calc_rim
from .nav import calc_nav
from .units import per_share


def sensitivity_multiples(
    base_ebitda_by_seg: dict[str, DAAllocation],
    multiples: dict[str, float],
    net_debt: int,
    eco_frontier: int,
    shares: int,
    row_seg: str | None = None,
    col_seg: str | None = None,
    row_range: list[float] | None = None,
    col_range: list[float] | None = None,
    unit_multiplier: int = 1_000_000,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """민감도: 두 부문 멀티플 변동 → Scenario A 주당 가치."""
    # 세그먼트 코드 자동 선택 (하드코딩 방지)
    seg_codes = list(multiples.keys())
    if row_seg is None:
        row_seg = seg_codes[0] if len(seg_codes) > 0 else ""
    if col_seg is None:
        col_seg = seg_codes[1] if len(seg_codes) > 1 else row_seg

    if row_range is None:
        base_m = multiples.get(row_seg, 8.0)
        row_range = [round(base_m + i, 1) for i in range(-2, 3)]
    if col_range is None:
        base_m = multiples.get(col_seg, 13.0)
        col_range = [round(base_m + i, 1) for i in range(-3, 4)]

    rows = []
    orig_row = multiples.get(row_seg)
    orig_col = multiples.get(col_seg)
    for row_m in row_range:
        multiples[row_seg] = row_m
        for col_m in col_range:
            multiples[col_seg] = col_m
            _, ev = calc_sotp(base_ebitda_by_seg, multiples)
            eq = ev - net_debt - eco_frontier
            ps = per_share(eq, unit_multiplier, shares)
            rows.append(SensitivityRow(row_val=row_m, col_val=col_m, value=ps))
    # 원래 값 복원
    if orig_row is not None:
        multiples[row_seg] = orig_row
    if orig_col is not None:
        multiples[col_seg] = orig_col
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
    unit_multiplier: int = 1_000_000,
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
                ps = round(per_share(eq, unit_multiplier, shares) * (1 - dlom / 100))
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


def sensitivity_ddm(
    dps: float,
    ke_base: float,
    g_base: float,
    buyback_per_share: float = 0.0,
    ke_range: list[float] | None = None,
    g_range: list[float] | None = None,
) -> list[SensitivityRow]:
    """민감도: Ke × 배당성장률 → 주당가치."""
    if ke_range is None:
        ke_range = [ke_base + d for d in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]]
    if g_range is None:
        g_range = [g_base + d for d in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]]

    rows = []
    for ke in ke_range:
        for g in g_range:
            try:
                r = calc_ddm(dps, g, ke, buyback_per_share=buyback_per_share)
                v = r.equity_per_share
            except ValueError:
                v = 0
            rows.append(SensitivityRow(row_val=ke, col_val=g, value=v))
    return rows


def sensitivity_rim(
    book_value: int,
    roe_forecasts: list[float],
    ke_base: float,
    shares: int,
    terminal_growth_base: float = 0.0,
    payout_ratio: float = 0.0,
    unit_multiplier: int = 1_000_000,
    ke_range: list[float] | None = None,
    tg_range: list[float] | None = None,
) -> list[SensitivityRow]:
    """민감도: Ke × 영구성장률 → RIM 주당가치."""
    if ke_range is None:
        ke_range = [ke_base + d for d in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]]
    if tg_range is None:
        tg_range = [terminal_growth_base + d for d in [-1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]]

    rows = []
    for ke in ke_range:
        for tg in tg_range:
            try:
                r = calc_rim(book_value, roe_forecasts, ke,
                             terminal_growth=tg, shares=shares,
                             unit_multiplier=unit_multiplier,
                             payout_ratio=payout_ratio)
                v = r.per_share
            except ValueError:
                v = 0
            rows.append(SensitivityRow(row_val=ke, col_val=tg, value=v))
    return rows


def sensitivity_nav(
    total_assets: int,
    total_liabilities: int,
    shares: int,
    base_revaluation: int = 0,
    unit_multiplier: int = 1_000_000,
    reval_range: list[float] | None = None,
    discount_range: list[float] | None = None,
) -> list[SensitivityRow]:
    """민감도: 재평가 조정액 × 지주할인율 → 주당 NAV."""
    if reval_range is None:
        step = max(abs(base_revaluation) // 3, 500_000)
        reval_range = [base_revaluation + step * d for d in [-3, -2, -1, 0, 1, 2, 3]]
    if discount_range is None:
        discount_range = [0, 10, 20, 30, 40]

    rows = []
    for reval in reval_range:
        r = calc_nav(total_assets, total_liabilities, shares, int(reval), unit_multiplier)
        for disc in discount_range:
            ps = round(r.per_share * (1 - disc / 100))
            rows.append(SensitivityRow(row_val=reval, col_val=disc, value=ps))
    return rows


def sensitivity_multiple_range(
    metric_value: int,
    net_debt: int,
    shares: int,
    base_multiple: float,
    unit_multiplier: int = 1_000_000,
    mult_range: list[float] | None = None,
    discount_range: list[float] | None = None,
) -> list[SensitivityRow]:
    """민감도: 적용 멀티플 × 할인율 → 주당가치."""
    if mult_range is None:
        mult_range = [round(base_multiple + d * 0.5, 1) for d in range(-4, 5)]
    if discount_range is None:
        discount_range = [0, 5, 10, 15, 20]

    rows = []
    for m in mult_range:
        ev = round(metric_value * m)
        eq = ev - net_debt
        for disc in discount_range:
            if eq > 0:
                ps = round(per_share(eq, unit_multiplier, shares) * (1 - disc / 100))
            else:
                ps = 0
            rows.append(SensitivityRow(row_val=m, col_val=disc, value=ps))
    return rows
