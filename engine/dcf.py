"""DCF (Discounted Cash Flow) engine — FCFF-based."""

import logging

from schemas.models import DCFParams, DCFProjection, DCFResult

logger = logging.getLogger(__name__)


def calc_dcf(
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    wacc_pct: float,
    params: DCFParams,
    base_year: int = 2025,
) -> DCFResult:
    """Compute DCF Enterprise Value via indirect FCFF from EBITDA.

    FCFF = NOPAT + D&A - Capex - delta_NWC
    where NOPAT = (EBITDA - D&A) x (1 - Tax%)
    """
    wacc = wacc_pct / 100
    tg = params.terminal_growth / 100
    tax_rate = params.tax_rate / 100
    growth_rates = params.ebitda_growth_rates

    # Auto-generate growth rates if not provided or empty (5-year fade from 8% to 3%)
    if not growth_rates:
        growth_rates = [0.08, 0.07, 0.06, 0.05, 0.03]

    # Revenue growth rates: use separate schedule if provided, else fall back to EBITDA rates.
    # Allows modeling margin expansion/compression without distorting EBITDA projection.
    # Pad with last value if shorter than growth_rates (robust to mismatched list lengths).
    rev_growth_rates = params.revenue_growth_rates if params.revenue_growth_rates else growth_rates
    if len(rev_growth_rates) < len(growth_rates):
        rev_growth_rates = list(rev_growth_rates) + [rev_growth_rates[-1]] * (len(growth_rates) - len(rev_growth_rates))

    if ebitda_base <= 0:
        raise ValueError(
            f"EBITDA({ebitda_base:,})가 0 이��입니다. "
            "DCF는 양의 현금흐름을 전제로 하므로, 적자 기업에는 Multiples/P/S 등 대안 방법론을 사용하세요."
        )

    if wacc <= tg:
        raise ValueError(
            f"WACC({wacc_pct:.2f}%)가 영구성장률({params.terminal_growth:.2f}%) 이하입니다. "
            "Terminal Value가 음수/무한대가 되어 DCF 산출이 불가합니다."
        )

    # Use 3-year average override when provided; fallback to single-year ratio
    if params.da_to_ebitda_override is not None and params.da_to_ebitda_override > 0:
        da_to_ebitda = params.da_to_ebitda_override
    else:
        da_to_ebitda = da_base / ebitda_base if ebitda_base > 0 else 0.5

    # If actual Capex available, derive Capex/D&A ratio; otherwise use parameter
    if params.actual_capex is not None and da_base > 0:
        capex_ratio = params.actual_capex / da_base
        if capex_ratio >= 3.0 and params.capex_fade_to is None:
            logger.warning(
                "Capex/D&A = %.1fx (투자 사이클 주의: actual_capex=%s, D&A=%s). "
                "capex_fade_to 설정으로 정규화 권장.",
                capex_ratio, f"{params.actual_capex:,}", f"{da_base:,}",
            )
    else:
        capex_ratio = params.capex_to_da

    # Capex fade: linearly interpolate from actual ratio to normalized target
    capex_fade_to = params.capex_fade_to
    use_capex_fade = capex_fade_to is not None and capex_fade_to != capex_ratio

    # If actual NWC available, derive delta_NWC/delta_Revenue ratio
    if params.actual_nwc is not None and params.prior_nwc is not None and revenue_base > 0:
        # Derive NWC/revenue ratio from actuals (projects NWC proportionally to revenue)
        nwc_ratio = params.actual_nwc / revenue_base
    else:
        nwc_ratio = params.nwc_to_rev_delta

    projections = []
    prev_ebitda = ebitda_base
    prev_revenue = revenue_base
    # Use actual NWC only when both actual and prior are available (paired validation)
    _use_actual_nwc = params.actual_nwc is not None and params.prior_nwc is not None
    prev_nwc = params.actual_nwc if _use_actual_nwc else round(revenue_base * nwc_ratio)

    for i, g in enumerate(growth_rates):
        yr = base_year + 1 + i
        ebitda = round(prev_ebitda * (1 + g))
        da = round(ebitda * da_to_ebitda)
        op = ebitda - da
        # No tax shield when operating at a loss (no NOL schedule modeled).
        # Limitation: companies with accumulated NOLs will have NOPAT understated
        # in early profitable years because NOL carryforward tax shelter is not applied.
        nopat = round(op * (1 - tax_rate)) if op > 0 else op
        # Fade capex ratio from actual to normalized target over projection period
        if use_capex_fade:
            n_years = len(growth_rates)
            # Linear interpolation: year 0 = actual ratio, year N-1 = fade target
            t = i / max(n_years - 1, 1)
            year_capex_ratio = capex_ratio + (capex_fade_to - capex_ratio) * t
        else:
            year_capex_ratio = capex_ratio
        capex = round(da * year_capex_ratio)
        revenue = round(prev_revenue * (1 + rev_growth_rates[i]))

        if _use_actual_nwc:
            # Project NWC proportional to revenue
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

    # PV of projection period (power-based for numerical precision)
    pv_fcff = 0
    for i, p in enumerate(projections):
        df = (1 + wacc) ** (i + 1)
        p.pv_fcff = round(p.fcff / df)
        pv_fcff += p.pv_fcff

    # Terminal Value (Gordon Growth)
    # Use normalized FCFF: maintenance capex = D&A (capex/DA → 1.0) in steady-state.
    # This avoids perpetuating capex-fade artifacts into terminal value.
    last_p = projections[-1]
    last_nopat = last_p.nopat
    last_da = last_p.da
    # Steady-state FCFF: NOPAT + DA - DA(maintenance) - delta_NWC ≈ NOPAT - delta_NWC
    # For terminal, assume NWC grows at terminal growth rate
    normalized_fcff = last_nopat - last_p.delta_nwc if last_nopat > 0 else last_p.fcff
    terminal_fcff = round(normalized_fcff * (1 + tg))
    terminal_value = round(terminal_fcff / (wacc - tg))
    n = len(projections)
    pv_terminal = round(terminal_value / (1 + wacc) ** n)

    ev_dcf = pv_fcff + pv_terminal
    tv_ev_ratio = round(pv_terminal / ev_dcf * 100, 1) if ev_dcf > 0 else 0.0

    # Exit Multiple terminal value (optional cross-check)
    terminal_value_exit = None
    pv_terminal_exit = None
    ev_dcf_exit = None
    if params.terminal_ev_ebitda is not None and params.terminal_ev_ebitda > 0:
        last_ebitda = projections[-1].ebitda
        terminal_value_exit = round(last_ebitda * params.terminal_ev_ebitda)
        pv_terminal_exit = round(terminal_value_exit / (1 + wacc) ** n)
        ev_dcf_exit = pv_fcff + pv_terminal_exit

    return DCFResult(
        projections=projections,
        pv_fcff_sum=pv_fcff,
        terminal_value=terminal_value,
        pv_terminal=pv_terminal,
        ev_dcf=ev_dcf,
        wacc=wacc_pct,
        terminal_growth=params.terminal_growth,
        terminal_value_exit=terminal_value_exit,
        pv_terminal_exit=pv_terminal_exit,
        ev_dcf_exit=ev_dcf_exit,
        terminal_ev_ebitda=params.terminal_ev_ebitda,
        tv_ev_ratio=tv_ev_ratio,
    )
