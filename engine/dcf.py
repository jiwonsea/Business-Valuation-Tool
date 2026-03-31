"""DCF (Discounted Cash Flow) 엔진 — FCFF 기반."""

from schemas.models import DCFParams, DCFProjection, DCFResult


def calc_dcf(
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: DCFParams,
    base_year: int = 2025,
) -> DCFResult:
    """EBITDA 기반 간접 FCFF → DCF Enterprise Value 산출.

    FCFF = NOPAT + D&A - Capex - ΔNWC
    여기서 NOPAT = (EBITDA - D&A) × (1 - Tax%)
    """
    wacc = wacc_pct / 100
    tg = params.terminal_growth / 100
    tax = params.tax_rate / 100
    growth_rates = params.ebitda_growth_rates

    da_to_ebitda = da_base / ebitda_base if ebitda_base > 0 else 0.5

    # 실제 Capex가 있으면 Capex/D&A 비율을 역산, 없으면 파라미터 사용
    if params.actual_capex is not None and da_base > 0:
        capex_ratio = params.actual_capex / da_base
    else:
        capex_ratio = params.capex_to_da

    # 실제 NWC가 있으면 ΔNWC/ΔRevenue 비율을 역산
    if params.actual_nwc is not None and params.prior_nwc is not None and revenue_base > 0:
        delta_nwc_actual = params.actual_nwc - params.prior_nwc
        # 매출 성장률로 implied revenue delta 추정
        nwc_to_rev = params.actual_nwc / revenue_base if revenue_base > 0 else params.nwc_to_rev_delta
        nwc_ratio = nwc_to_rev
    else:
        nwc_ratio = params.nwc_to_rev_delta

    projections = []
    prev_ebitda = ebitda_base
    prev_revenue = revenue_base
    prev_nwc = params.actual_nwc if params.actual_nwc is not None else round(revenue_base * nwc_ratio)

    for i, g in enumerate(growth_rates):
        yr = base_year + 1 + i
        ebitda = round(prev_ebitda * (1 + g))
        da = round(ebitda * da_to_ebitda)
        op = ebitda - da
        nopat = round(op * (1 - tax))
        capex = round(da * capex_ratio)
        revenue = round(prev_revenue * (1 + g))

        if params.actual_nwc is not None:
            # NWC를 매출 비례로 예측
            nwc_current = round(revenue * nwc_ratio)
            delta_nwc = nwc_current - prev_nwc
            prev_nwc = nwc_current
        else:
            delta_nwc = round((revenue - prev_revenue) * nwc_ratio)

        fcff = nopat + da - capex - delta_nwc

        projections.append(DCFProjection(
            year=yr, ebitda=ebitda, op=op, da=da,
            nopat=nopat, capex=capex, delta_nwc=delta_nwc,
            fcff=fcff, growth=g,
        ))
        prev_ebitda = ebitda
        prev_revenue = revenue

    # PV of projection period
    pv_fcff = 0
    for i, p in enumerate(projections):
        df = (1 + wacc) ** (i + 1)
        p.pv_fcff = round(p.fcff / df)
        pv_fcff += p.pv_fcff

    # Terminal Value (Gordon Growth)
    last_fcff = projections[-1].fcff
    terminal_fcff = round(last_fcff * (1 + tg))
    terminal_value = round(terminal_fcff / (wacc - tg))
    n = len(projections)
    pv_terminal = round(terminal_value / (1 + wacc) ** n)

    ev_dcf = pv_fcff + pv_terminal

    return DCFResult(
        projections=projections,
        pv_fcff_sum=pv_fcff,
        terminal_value=terminal_value,
        pv_terminal=pv_terminal,
        ev_dcf=ev_dcf,
        wacc=wacc_pct,
        terminal_growth=params.terminal_growth,
    )
