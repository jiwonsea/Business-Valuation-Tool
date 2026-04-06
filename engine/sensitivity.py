"""Sensitivity analysis engine -- 2-way tables by valuation method."""

from __future__ import annotations

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
    """Sensitivity: two-segment multiple variation -> Scenario A per-share value."""
    # Auto-select segment codes (avoid hardcoding)
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

    # Pre-compute EV for non-varying segments (negative EBITDA -> negative EV)
    fixed_ev = 0
    for code, alloc in base_ebitda_by_seg.items():
        if code != row_seg and code != col_seg:
            m = multiples.get(code, 0)
            fixed_ev += round(alloc.ebitda * m)
    deductions = net_debt + eco_frontier

    rows = []
    orig_row = multiples.get(row_seg)
    orig_col = multiples.get(col_seg)
    row_alloc = base_ebitda_by_seg.get(row_seg)
    col_alloc = base_ebitda_by_seg.get(col_seg)
    try:
        for row_m in row_range:
            row_ev = round(row_alloc.ebitda * row_m) if row_alloc else 0
            for col_m in col_range:
                col_ev = round(col_alloc.ebitda * col_m) if col_alloc else 0
                eq = fixed_ev + row_ev + col_ev - deductions
                ps = per_share(eq, unit_multiplier, shares)
                rows.append(SensitivityRow(row_val=row_m, col_val=col_m, value=ps))
    finally:
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
    cps_dividend_rate: float = 0.0,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """Sensitivity: FI IRR x DLOM -> Scenario B per-share value (pre-probability)."""
    if irr_range is None:
        irr_range = [3.0, 5.0, 8.0, 10.0, 12.0, 15.0]
    if dlom_range is None:
        dlom_range = [0, 10, 15, 20, 25, 30]

    rows = []
    for irr in irr_range:
        effective_rate = max(irr - cps_dividend_rate, 0.0)
        cps_r = round(cps_principal * (1 + effective_rate / 100) ** cps_years)
        claims = net_debt + cps_r + rcps_repay + buyback + eco_frontier
        eq = total_ev - claims
        base_ps = per_share(eq, unit_multiplier, shares) if eq > 0 else 0
        for dlom in dlom_range:
            ps = round(base_ps * (1 - dlom / 100)) if base_ps > 0 else 0
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
    wacc_base: float | None = None,
) -> tuple[list[SensitivityRow], list[float], list[float]]:
    """Sensitivity: WACC x terminal growth -> DCF EV (in display unit).

    Optimization: FCFF projections are independent of WACC/Tg, computed once;
    only discounting (PV) + Terminal Value recalculated per (WACC, Tg) combination.

    Args:
        wacc_base: Actual WACC (%). When provided and wacc_range is None,
            generates a dynamic range centered on WACC ± 2%p with 0.5%p steps.
    """
    if wacc_range is None:
        if wacc_base is not None:
            center = round(wacc_base * 2) / 2  # snap to nearest 0.5
            wacc_range = [round(center + d * 0.5, 1) for d in range(-4, 5)]
        else:
            wacc_range = [7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0]
    if tg_range is None:
        tg_range = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]

    # Compute FCFF projections once (using actual WACC; projections are WACC-independent)
    seed_wacc = wacc_base if wacc_base is not None else wacc_range[len(wacc_range) // 2]
    base_result = calc_dcf(ebitda_base, da_base, revenue_base,
                           seed_wacc, params, base_year)
    fcffs = [p.fcff for p in base_result.projections]
    n = len(fcffs)
    last_fcff = fcffs[-1]

    rows = []
    for w in wacc_range:
        wacc = w / 100
        # PV of projection period
        discount = 1 + wacc
        pv_fcff = 0
        df = 1.0
        for fcff in fcffs:
            df *= discount
            pv_fcff += round(fcff / df)
        for tg in tg_range:
            tg_dec = tg / 100
            if wacc <= tg_dec:
                rows.append(SensitivityRow(row_val=w, col_val=tg, value=0))
                continue
            terminal_fcff = round(last_fcff * (1 + tg_dec))
            tv = round(terminal_fcff / (wacc - tg_dec))
            pv_tv = round(tv / (1 + wacc) ** n)
            ev = pv_fcff + pv_tv
            rows.append(SensitivityRow(row_val=w, col_val=tg, value=ev))
    return rows, wacc_range, tg_range


def sensitivity_ddm(
    dps: float,
    ke_base: float,
    g_base: float,
    buyback_per_share: float = 0.0,
    ke_range: list[float] | None = None,
    g_range: list[float] | None = None,
) -> list[SensitivityRow]:
    """Sensitivity: Ke x dividend growth rate -> per-share value."""
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
    """Sensitivity: Ke x terminal growth rate -> RIM per-share value."""
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
    """Sensitivity: revaluation adjustment x holding discount -> NAV per share."""
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
    """Sensitivity: applied multiple x discount rate -> per-share value."""
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
