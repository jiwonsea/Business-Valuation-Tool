"""EPS-to-DCF fair-value elasticity measurement."""

from schemas.models import DCFParams, EpsElasticityResult

from .dcf import calc_dcf


def measure_eps_elasticity(
    *,
    ebitda_base: int,
    da_base: int,
    revenue_base: int,
    net_income_base: int,
    wacc_pct: float,
    dcf_params: DCFParams,
    net_debt: int,
    shares: int,
    unit_multiplier: int,
    shock_pct: float,
    base_year: int = 2025,
    tax_rate_pct: float | None = None,
) -> EpsElasticityResult:
    """Measure recurring reported-NI shock elasticity on per-share equity value.

    A tax override applies both to the NI-to-OP gross-up and to the DCF itself.
    Revenue, D&A, net debt, and shares remain fixed. ``tax_rate_basis`` is
    derived, never accepted: an explicit ``tax_rate_pct`` -- even one equal to
    ``dcf_params.tax_rate`` -- records that the operator made a normalization
    decision (``"normalized"``); ``None`` means the profile rate was used as-is
    (``"profile_as_is"``). The label can therefore never contradict
    ``tax_rate_pct``.
    """
    if shock_pct == 0:
        raise ValueError("shock_pct must be non-zero")
    if shares <= 0:
        raise ValueError("shares must be positive")
    effective_tax_rate = dcf_params.tax_rate if tax_rate_pct is None else tax_rate_pct
    tax_rate_basis = "profile_as_is" if tax_rate_pct is None else "normalized"
    if not 0 <= effective_tax_rate < 100:
        raise ValueError("tax_rate_pct must be in [0, 100)")
    effective_params = dcf_params.model_copy(update={"tax_rate": effective_tax_rate})

    ebitda_shocked = round(
        ebitda_base + net_income_base * shock_pct / (1 - effective_tax_rate / 100)
    )
    if ebitda_shocked <= 0:
        raise ValueError("shocked EBITDA must be positive")

    base = calc_dcf(
        ebitda_base, da_base, revenue_base, wacc_pct, effective_params, base_year
    )
    shocked = calc_dcf(
        ebitda_shocked, da_base, revenue_base, wacc_pct, effective_params, base_year
    )
    equity_base = base.ev_dcf - net_debt
    equity_shocked = shocked.ev_dcf - net_debt
    if equity_base == 0:
        raise ValueError("base equity value must be non-zero")

    fv_base = equity_base * unit_multiplier / shares
    fv_shocked = equity_shocked * unit_multiplier / shares
    elasticity_ev = ((shocked.ev_dcf - base.ev_dcf) / base.ev_dcf) / shock_pct
    elasticity_fv = ((fv_shocked - fv_base) / fv_base) / shock_pct

    return EpsElasticityResult(
        elasticity_fv=elasticity_fv,
        elasticity_ev=elasticity_ev,
        fv_base=fv_base,
        fv_shocked=fv_shocked,
        ev_base=base.ev_dcf,
        ev_shocked=shocked.ev_dcf,
        shock_pct=shock_pct,
        mapping="recurring_ni_level_shock",
        tax_rate_pct=effective_tax_rate,
        tax_rate_basis=tax_rate_basis,
    )
