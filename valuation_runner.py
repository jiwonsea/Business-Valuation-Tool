"""Valuation execution engine -- YAML loading + method-specific dispatch."""

import logging
from datetime import date

import yaml

logger = logging.getLogger(__name__)

from schemas.models import (
    CompanyProfile, WACCParams, WACCResult, ScenarioParams,
    DCFParams, DDMParams, NAVParams,
    RIMParams, RIMProjectionResult, RIMValuationResult,
    PeerCompany, ValuationInput, ValuationResult, CrossValidationItem,
    MonteCarloResult, DDMValuationResult, NAVResult, MultiplesResult,
    NewsDriver,
)
from engine.drivers import resolve_drivers
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.distress import calc_distress_discount, apply_distress_discount
from engine.dcf import calc_dcf
from engine.ddm import calc_ddm as calc_ddm_engine
from engine.rim import calc_rim as calc_rim_engine
from engine.scenario import calc_scenario
from engine.sensitivity import (
    sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf,
    sensitivity_ddm, sensitivity_rim, sensitivity_nav, sensitivity_multiple_range,
)
from engine.multiples import cross_validate, calc_pe, calc_pbv
from engine.peer_analysis import calc_peer_stats
from engine.quality import calc_quality_score
from engine.nav import calc_nav
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method, is_financial


def _seg_names(vi: ValuationInput) -> dict[str, str]:
    """Extract {code: name} mapping from segments dictionary."""
    return {code: info["name"] for code, info in vi.segments.items()}


def _adjust_wacc(base: WACCResult, wacc_adj: float, eq_w: float = 100.0) -> WACCResult:
    """Per-scenario WACC adjustment. wacc_adj shifts Ke; WACC is recomputed from components.

    Args:
        base: Base WACC result
        wacc_adj: Ke shift in %p (e.g., +0.5 -> Ke + 0.5%p)
        eq_w: Equity weight (%) from WACCParams -- needed to recompute WACC correctly
    """
    if wacc_adj == 0:
        return base
    new_ke = round(base.ke + wacc_adj, 4)
    dw = 100 - eq_w
    new_wacc = round(new_ke * eq_w / 100 + base.kd_at * dw / 100, 4)
    return WACCResult(
        bl=base.bl,
        ke=new_ke,
        kd_at=base.kd_at,
        wacc=new_wacc,
    )


def load_profile(path: str) -> ValuationInput:
    """Parse YAML profile into ValuationInput."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Company
    co_raw = raw["company"]
    if isinstance(co_raw.get("analysis_date"), str):
        co_raw["analysis_date"] = date.fromisoformat(co_raw["analysis_date"])
    company = CompanyProfile(**co_raw)

    # Segments info
    segments = raw["segments"]

    # Segment data: year(int) → code → financials dict
    segment_data = {}
    for yr_str, segs in raw["segment_data"].items():
        yr = int(yr_str)
        segment_data[yr] = {code: data for code, data in segs.items()}

    # Consolidated: year(int) → financials dict
    consolidated = {}
    for yr_str, data in raw["consolidated"].items():
        yr = int(yr_str)
        consolidated[yr] = data

    # WACC
    wacc_params = WACCParams(**raw["wacc_params"])

    # Multiples (from segments info)
    multiples = {code: info["multiple"] for code, info in segments.items()}

    # Scenarios
    scenarios = {}
    for code, sc_raw in raw["scenarios"].items():
        scenarios[code] = ScenarioParams(code=code, **sc_raw)

    # DCF
    dcf_params = DCFParams(**raw["dcf_params"])
    # Auto-generate from financial data when ebitda_growth_rates not specified
    if dcf_params.ebitda_growth_rates is None:
        from engine.growth import generate_growth_rates
        _industry = raw.get("industry", "") or co_raw.get("industry", "")
        dcf_params = dcf_params.model_copy(update={
            "ebitda_growth_rates": generate_growth_rates(
                consolidated, market=company.market, industry=_industry,
            )
        })

    # DDM (Optional)
    ddm_params = None
    if "ddm_params" in raw:
        ddm_params = DDMParams(**raw["ddm_params"])

    # RIM (Optional)
    rim_params = None
    if "rim_params" in raw:
        rim_params = RIMParams(**raw["rim_params"])

    # NAV (Optional)
    nav_params = None
    if "nav_params" in raw:
        nav_params = NAVParams(**raw["nav_params"])

    # Peers (skip entries with non-numeric ev_ebitda from AI output)
    peers = []
    for p in raw.get("peers", []):
        try:
            peers.append(PeerCompany(**p))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Skipping invalid peer entry %s: %s", p, e)

    # News drivers (multi-variable scenario approach)
    news_drivers = []
    for nd_raw in raw.get("news_drivers", []):
        try:
            news_drivers.append(NewsDriver(**nd_raw))
        except (ValueError, TypeError, KeyError) as e:
            logger.warning("Skipping invalid news_driver entry %s: %s", nd_raw, e)
    news_key_issues = raw.get("news_key_issues")

    # Auto-detect unit_multiplier (when not specified in YAML)
    if "unit_multiplier" not in raw.get("company", {}):
        latest_yr = max(consolidated.keys())
        revenue = consolidated[latest_yr].get("revenue", 0)
        label, multiplier = detect_unit(revenue, company.market)
        company.currency_unit = label
        company.unit_multiplier = multiplier

    # Validate scenario override keys against known segment codes
    _valid_seg_codes = set(segments.keys())
    for sc_code, sc in scenarios.items():
        for attr_name in ("segment_multiples", "segment_ebitda", "segment_revenue"):
            override_dict = getattr(sc, attr_name, None)
            if not override_dict:
                continue
            bad_keys = set(override_dict.keys()) - _valid_seg_codes
            if bad_keys:
                logger.warning(
                    "[%s] scenario '%s' %s has unrecognized keys %s "
                    "(valid: %s) — overrides will be ignored",
                    company.name, sc_code, attr_name, bad_keys, _valid_seg_codes,
                )

    return ValuationInput(
        company=company,
        valuation_method=raw.get("valuation_method", "auto"),
        industry=raw.get("industry", "") or co_raw.get("industry", ""),
        segments=segments,
        segment_data=segment_data,
        consolidated=consolidated,
        wacc_params=wacc_params,
        multiples=multiples,
        scenarios=scenarios,
        dcf_params=dcf_params,
        ddm_params=ddm_params,
        rim_params=rim_params,
        nav_params=nav_params,
        cps_principal=raw.get("cps_principal", 0),
        cps_years=raw.get("cps_years", 0),
        cps_dividend_rate=raw.get("cps_dividend_rate", 0.0),
        rcps_principal=raw.get("rcps_principal", 0),
        rcps_years=raw.get("rcps_years", 0),
        rcps_dividend_rate=raw.get("rcps_dividend_rate", 0.0),
        net_debt=raw.get("net_debt", 0),
        segment_net_debt=raw.get("segment_net_debt", {}),
        eco_frontier=raw.get("eco_frontier", 0),
        peers=peers,
        base_year=raw.get("base_year", 2025),
        ev_revenue_multiple=raw.get("ev_revenue_multiple", 0.0),
        pe_multiple=raw.get("pe_multiple", 0.0),
        pbv_multiple=raw.get("pbv_multiple", 0.0),
        ps_multiple=raw.get("ps_multiple", 0.0),
        pffo_multiple=raw.get("pffo_multiple", 0.0),
        ffo=raw.get("ffo", 0),
        mc_enabled=raw.get("mc_enabled", False),
        mc_sims=raw.get("mc_sims", 10_000),
        mc_multiple_std_pct=raw.get("mc_multiple_std_pct", 15.0),
        mc_dlom_mean=raw.get("mc_dlom_mean", 0.0),
        mc_dlom_std=raw.get("mc_dlom_std", 5.0),
        news_drivers=news_drivers,
        news_key_issues=news_key_issues,
    )


def run_valuation(vi: ValuationInput) -> ValuationResult:
    """Execute full valuation pipeline -- dispatch by methodology."""
    # Auto-detect financial sector -> skip Hamada
    if is_financial(vi.industry):
        vi.wacc_params.is_financial = True

    # Common: WACC (needed before method selection -- Ke used for DDM/RIM decision)
    # NOTE: WACC uses 2-component capital structure (equity + debt). When CPS/RCPS exist,
    # their cost differs from kd_pre but is not separately weighted — WACC may be understated.
    if vi.cps_principal or vi.rcps_principal:
        logger.warning("CPS/RCPS present but WACC uses 2-component structure (Ke/Kd only) "
                        "— preferred equity cost is not separately weighted")
    wacc_result = calc_wacc(vi.wacc_params)
    um = vi.company.unit_multiplier

    # Determine methodology
    method = vi.valuation_method
    if method == "auto":
        # Calculate ROE for financial DDM/RIM decision
        by = vi.base_year
        cons = vi.consolidated[by]
        equity_bv = cons.get("equity", 0)
        net_income = cons.get("net_income", 0)
        roe = (net_income / equity_bv * 100) if equity_bv > 0 else 0.0

        seg_names = [info["name"] for info in vi.segments.values()]
        method = suggest_method(
            n_segments=len(vi.segments),
            legal_status=vi.company.legal_status,
            industry=vi.industry,
            has_peers=len(vi.peers) >= 3,
            roe=roe,
            ke=wacc_result.ke,
            has_ddm_params=vi.ddm_params is not None,
            has_rim_params=vi.rim_params is not None,
            segment_names=seg_names,
        )

    dispatch = {
        "sotp": _run_sotp_valuation,
        "ddm": _run_ddm_valuation,
        "rim": _run_rim_valuation,
        "nav": _run_nav_valuation,
        "multiples": _run_multiples_valuation,
        "dcf_primary": _run_dcf_valuation,
    }
    runner = dispatch.get(method, _run_dcf_valuation)
    result = runner(vi, wacc_result, um)

    # Quality scoring (pure function, zero IO)
    result.quality = calc_quality_score(vi, result)

    return result


def _calc_effective_net_debt(vi: ValuationInput) -> int:
    """Calculate effective net debt for financial subsidiary split SOTP.

    Net debt of financial segments (method=pbv/pe) is already embedded in P/BV,
    so it is deducted from total net_debt. Returns net_debt as-is if segment_net_debt is empty.
    """
    if not vi.segment_net_debt:
        return vi.net_debt
    financial_debt = sum(
        vi.segment_net_debt[c]
        for c, info in vi.segments.items()
        if info.get("method") in ("pbv", "pe") and c in vi.segment_net_debt
    )
    return vi.net_debt - financial_debt


def _has_mixed_sotp(vi: ValuationInput) -> bool:
    """Determine if this is a financial subsidiary split SOTP."""
    return bool(vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )


def _needs_method_dispatch(vi: ValuationInput) -> bool:
    """True if any segment uses a non-default method (ev_revenue, pbv, pe)."""
    return any(
        info.get("method") not in (None, "ev_ebitda")
        for info in vi.segments.values()
    )


def _run_sotp_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """SOTP-based valuation (multi-segment companies, Mixed Method support)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    # Financial subsidiary split SOTP check
    is_mixed = _has_mixed_sotp(vi)
    needs_dispatch = is_mixed or _needs_method_dispatch(vi)
    effective_net_debt = _calc_effective_net_debt(vi) if is_mixed else vi.net_debt

    # Extract segment method info
    seg_methods = {c: info.get("method", "ev_ebitda") for c, info in vi.segments.items()}

    # D&A allocation (all years) -- excluding financial segments
    da_allocations = {}
    for yr, segs in vi.segment_data.items():
        c = vi.consolidated[yr]
        total_da = c["dep"] + c["amort"]
        da_allocations[yr] = allocate_da(segs, total_da, seg_methods if needs_dispatch else None)

    # Financial distress discount on multiples
    distress = calc_distress_discount(
        vi.consolidated, by,
        market=vi.company.market,
        kd_pre=vi.wacc_params.kd_pre,
        industry=vi.industry,
        max_discount=vi.distress_max_discount,
    )
    # ev_revenue and distress_exempt segments keep original multiples
    exempt = {c for c, info in vi.segments.items()
              if info.get("method") == "ev_revenue" or info.get("distress_exempt")}
    # Healthy segments: profitable (op > 0) in diversified companies get half discount
    healthy: set[str] = set()
    if len(vi.segments) >= 3 and distress.applied:
        base_seg_data = vi.segment_data.get(by, {})
        healthy = {c for c in vi.segments
                   if c not in exempt and base_seg_data.get(c, {}).get("op", 0) > 0}
    effective_multiples = apply_distress_discount(
        vi.multiples, distress.discount, exempt, healthy,
    )
    if distress.applied:
        logger.info("[Distress] %s: %s", vi.company.name, distress.detail)

    # Build segment revenue map for ev_revenue segments
    seg_revenue = {c: vi.segment_data.get(by, {}).get(c, {}).get("revenue", 0)
                   for c in vi.segments}

    # SOTP (base year) -- Mixed Method support
    base_alloc = da_allocations[by]
    sotp, total_ev = calc_sotp(
        base_alloc, effective_multiples,
        segments_info=vi.segments if needs_dispatch else None,
        revenue_by_seg=seg_revenue if needs_dispatch else None,
    )

    # Warn if all scenarios lack SOTP-specific drivers (will produce identical EV)
    _all_undifferentiated = all(
        not sc.segment_ebitda and not sc.segment_multiples and not sc.segment_revenue
        and sc.growth_adj_pct == 0 and sc.market_sentiment_pct == 0
        for sc in vi.scenarios.values()
    )
    if _all_undifferentiated and len(vi.scenarios) > 1:
        logger.warning(
            "SOTP 시나리오에 segment_multiples/segment_ebitda/growth_adj_pct 미설정 "
            "— 모든 시나리오 동일 EV. --auto로 재생성하거나 YAML에 드라이버를 추가하세요."
        )

    # Scenarios -- apply per-scenario SOTP overrides + market_sentiment_pct
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)

        # Per-scenario SOTP: recalculate if drivers are set
        needs_recalc = (sc.segment_ebitda or sc.segment_multiples or sc.segment_revenue
                        or sc.segment_method_override
                        or sc.growth_adj_pct != 0)
        if needs_recalc:
            # Apply growth_adj_pct to base EBITDA allocation
            adj_alloc = base_alloc
            if sc.growth_adj_pct != 0:
                mult = 1 + sc.growth_adj_pct / 100
                adj_alloc = {
                    c: alloc.model_copy(update={"ebitda": round(alloc.ebitda * mult)})
                    for c, alloc in base_alloc.items()
                }

            # Method transition: merge overrides into segments_info copy
            sc_segments = vi.segments if needs_dispatch else None
            if sc.segment_method_override and needs_dispatch:
                sc_segments = {
                    c: {**info, "method": sc.segment_method_override.get(c, info.get("method", "ev_ebitda"))}
                    for c, info in vi.segments.items()
                }
                # Re-allocate D&A for method transitions (ev_revenue→ev_ebitda gets D&A)
                sc_seg_methods = {c: sc_segments[c].get("method", "ev_ebitda") for c in sc_segments}
                total_da = cons["dep"] + cons["amort"]
                adj_alloc = allocate_da(vi.segment_data[by], total_da, sc_seg_methods)
                if sc.growth_adj_pct != 0:
                    gm = 1 + sc.growth_adj_pct / 100
                    adj_alloc = {
                        c: alloc.model_copy(update={"ebitda": round(alloc.ebitda * gm)})
                        for c, alloc in adj_alloc.items()
                    }

            _, sc_ev = calc_sotp(
                adj_alloc,
                effective_multiples,
                segments_info=sc_segments,
                ebitda_override=sc.segment_ebitda,
                multiple_override=sc.segment_multiples,
                revenue_by_seg=seg_revenue if needs_dispatch else None,
                revenue_override=sc.segment_revenue,
            )
        else:
            sc_ev = total_ev

        # Market sentiment is cumulative
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(sc, sc_ev, effective_net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF cross-validation -- for mixed SOTP, manufacturing segments only
    total_da_base = cons["dep"] + cons["amort"]
    if is_mixed:
        mfg_ebitda = sum(
            alloc.ebitda for c, alloc in base_alloc.items()
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        mfg_da = sum(
            alloc.da_allocated for c, alloc in base_alloc.items()
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        mfg_revenue = sum(
            vi.segment_data[by][c].get("revenue", 0) for c in vi.segment_data[by]
            if seg_methods.get(c, "ev_ebitda") == "ev_ebitda"
        )
        ebitda_base = mfg_ebitda
        dcf_da_base = mfg_da
        dcf_revenue = mfg_revenue
    else:
        ebitda_base = cons["op"] + total_da_base
        dcf_da_base = total_da_base
        dcf_revenue = cons["revenue"]

    dcf_result = calc_dcf(
        ebitda_base, dcf_da_base, dcf_revenue,
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    # Sensitivity
    ref_sc = _get_reference_scenario(vi.scenarios)
    sens_mult, _, _ = sensitivity_multiples(
        base_alloc, effective_multiples, effective_net_debt, vi.eco_frontier,
        vi.company.shares_outstanding, unit_multiplier=um,
        segments_info=vi.segments if needs_dispatch else None,
        revenue_by_seg=seg_revenue if needs_dispatch else None,
        cps_repay=round(vi.cps_principal * (1 + (ref_sc.irr if ref_sc else 0) / 100) ** vi.cps_years) if vi.cps_principal else 0,
        rcps_repay=(ref_sc.rcps_repay or 0) if ref_sc else 0,
        buyback=ref_sc.buyback if ref_sc else 0,
    )
    sens_irr, _, _ = sensitivity_irr_dlom(
        total_ev, effective_net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        (ref_sc.rcps_repay or 0) if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        vi.company.shares_outstanding,
        unit_multiplier=um,
        cps_dividend_rate=vi.cps_dividend_rate,
    )
    sens_dcf_rows, _, _ = sensitivity_dcf(
        ebitda_base, dcf_da_base, dcf_revenue,
        vi.dcf_params, vi.base_year,
        wacc_base=wacc_result.wacc,
    )

    # Multiple cross-validation -- apply effective_net_debt
    cv_items = _cross_validate_common(
        vi, cons, ebitda_base, total_ev, dcf_result.ev_dcf, um,
        net_debt_override=effective_net_debt if is_mixed else None,
    )

    # Monte Carlo
    sotp_seg_ebitdas = {code: base_alloc[code].ebitda for code in vi.segments}
    mc_result = _run_monte_carlo(
        vi, wacc_result, sotp_seg_ebitdas, um,
        dcf_result=dcf_result, effective_multiples=effective_multiples,
        seg_revenues=seg_revenue, segment_methods=seg_methods,
        net_debt_override=effective_net_debt if is_mixed else None,
    )

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    return ValuationResult(
        primary_method="sotp",
        wacc=wacc_result,
        da_allocations={yr: {c: a for c, a in allocs.items()}
                        for yr, allocs in da_allocations.items()},
        sotp=sotp,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_multiples=sens_mult,
        sensitivity_irr_dlom=sens_irr,
        sensitivity_dcf=sens_dcf_rows,
    )


def _make_scenario_dcf_params(
    base: DCFParams, sc: ScenarioParams, wacc: float,
) -> DCFParams | None:
    """Generate per-scenario DCF parameters. Returns None if no adjustments."""
    if sc.growth_adj_pct == 0 and sc.terminal_growth_adj == 0:
        return None
    adjusted_rates = [g * (1 + sc.growth_adj_pct / 100) for g in base.ebitda_growth_rates]
    adjusted_tg = base.terminal_growth + sc.terminal_growth_adj
    # Safety: floor at 0% (negative TGR implies perpetual shrinkage), cap below WACC
    adjusted_tg = max(0.0, min(adjusted_tg, wacc - 0.5))
    return DCFParams(
        ebitda_growth_rates=adjusted_rates,
        tax_rate=base.tax_rate,
        capex_to_da=base.capex_to_da,
        nwc_to_rev_delta=base.nwc_to_rev_delta,
        terminal_growth=adjusted_tg,
        actual_capex=base.actual_capex,
        actual_nwc=base.actual_nwc,
        prior_nwc=base.prior_nwc,
        da_to_ebitda_override=base.da_to_ebitda_override,
        terminal_ev_ebitda=base.terminal_ev_ebitda,
    )


def _run_dcf_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DCF-based valuation (single-segment or growth companies)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base

    # DCF (primary)
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )
    total_ev = dcf_result.ev_dcf

    # Scenarios (DCF EV-based, per-scenario DCF driver + WACC adjustment applied)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev  # Default: base DCF EV

        # Per-scenario WACC adjustment
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        effective_wacc = sc_wacc.wacc

        # Per-scenario DCF driver adjustment
        sc_dcf_params = _make_scenario_dcf_params(vi.dcf_params, sc, effective_wacc)
        if sc_dcf_params is not None:
            sc_dcf = calc_dcf(
                ebitda_base, total_da_base, cons["revenue"],
                effective_wacc, sc_dcf_params, vi.base_year,
            )
            sc_ev = sc_dcf.ev_dcf
        elif sc.wacc_adj != 0:
            # Recalculate DCF even without growth adjustment (WACC change alone)
            sc_dcf = calc_dcf(
                ebitda_base, total_da_base, cons["revenue"],
                effective_wacc, vi.dcf_params, vi.base_year,
            )
            sc_ev = sc_dcf.ev_dcf

        # Market sentiment post-processing
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))

        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF sensitivity
    sens_dcf_rows, _, _ = sensitivity_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        vi.dcf_params, vi.base_year,
        wacc_base=wacc_result.wacc,
    )

    # SOTP cross-validation (calculate SOTP if multi-segment)
    sotp_ev = 0
    sotp_result = {}
    da_allocations = {}
    if len(vi.segments) > 1 and by in vi.segment_data:
        da_allocations[by] = allocate_da(vi.segment_data[by], total_da_base)
        _cv_seg_revenue = {c: vi.segment_data.get(by, {}).get(c, {}).get("revenue", 0)
                          for c in vi.segments}
        sotp_result, sotp_ev = calc_sotp(
            da_allocations[by], vi.multiples,
            segments_info=vi.segments if len(vi.segments) > 1 else None,
            revenue_by_seg=_cv_seg_revenue,
        )

    cv_items = _cross_validate_common(vi, cons, ebitda_base, sotp_ev, dcf_result.ev_dcf, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    return ValuationResult(
        primary_method="dcf_primary",
        wacc=wacc_result,
        da_allocations={yr: {c: a for c, a in allocs.items()}
                        for yr, allocs in da_allocations.items()},
        sotp=sotp_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        sensitivity_dcf=sens_dcf_rows,
    )


def _run_ddm_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DDM-based valuation (financial sector)."""
    if not vi.ddm_params:
        raise ValueError(
            "DDM 방법론이 선택되었으나 ddm_params가 없습니다. "
            "YAML에 ddm_params: {dps: ..., dividend_growth: ...}를 추가하세요."
        )

    ke = wacc_result.ke
    buyback_ps = vi.ddm_params.buyback_per_share
    base_growth = vi.ddm_params.dividend_growth

    # Base DDM (default growth rate)
    ddm_raw = calc_ddm_engine(
        vi.ddm_params.dps, base_growth, ke,
        buyback_per_share=buyback_ps,
    )
    ddm_result = DDMValuationResult(
        dps=ddm_raw.dps,
        buyback_per_share=ddm_raw.buyback_per_share,
        total_payout=ddm_raw.total_payout,
        growth=ddm_raw.growth,
        ke=ddm_raw.ke,
        equity_per_share=ddm_raw.equity_per_share,
        warnings=ddm_raw.warnings,
    )

    # Per-scenario DDM: recalculate with ddm_growth + wacc_adj (Ke adjustment)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_growth = sc.ddm_growth if sc.ddm_growth is not None else base_growth
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        sc_ke = sc_wacc.ke
        sc_ddm = calc_ddm_engine(
            vi.ddm_params.dps, sc_growth, sc_ke,
            buyback_per_share=buyback_ps,
        )
        sc_ev = sc_ddm.equity_per_share * vi.company.shares_outstanding // (um or 1)

        # Market sentiment is cumulative
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))

        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DDM base EV (for cross-validation)
    total_ev = ddm_raw.equity_per_share * vi.company.shares_outstanding // (um or 1)

    # Use DDM value directly when no scenarios are set
    if not scenario_results:
        total_weighted = ddm_raw.equity_per_share

    # EBITDA-based DCF is meaningless for financials -> P/E, P/BV cross-validation only
    by = vi.base_year
    cons = vi.consolidated[by]
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # DDM sensitivity: Ke x dividend growth rate
    sens_ddm = sensitivity_ddm(
        vi.ddm_params.dps, ke, base_growth,
        buyback_per_share=buyback_ps,
    )

    # Monte Carlo (segment EBITDA-based -- auxiliary distribution)
    mc_result = _run_monte_carlo(vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um)

    return ValuationResult(
        primary_method="ddm",
        wacc=wacc_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        ddm=ddm_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_primary=sens_ddm,
        sensitivity_primary_label=f"Ke × 배당성장률 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_rim_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """RIM (Residual Income Model) valuation (financial sector -- BV-based)."""
    by = vi.base_year
    cons = vi.consolidated[by]
    equity_bv = cons.get("equity", 0)
    shares = vi.company.shares_outstanding
    ke = wacc_result.ke

    # RIM parameters: explicit rim_params or auto-generated from financial statements
    if vi.rim_params:
        roe_forecasts = vi.rim_params.roe_forecasts
        tg = vi.rim_params.terminal_growth
        payout = vi.rim_params.payout_ratio
    else:
        # Back-calculate ROE from recent financials for 5-year forecast (gradual convergence)
        net_income = cons.get("net_income", 0)
        current_roe = (net_income / equity_bv * 100) if equity_bv > 0 else ke
        # ROE gradually converges toward Ke (5 years, fully reaching Ke at year 5)
        roe_forecasts = [
            round(current_roe + (ke - current_roe) * i / 5, 1)
            for i in range(1, 6)
        ]
        tg = 0.0
        payout = 30.0

    rim_raw = calc_rim_engine(
        book_value=equity_bv,
        roe_forecasts=roe_forecasts,
        ke=ke,
        terminal_growth=tg,
        shares=shares,
        unit_multiplier=um,
        payout_ratio=payout,
    )
    rim_result = RIMValuationResult(
        bv_current=rim_raw.bv_current,
        ke=rim_raw.ke,
        terminal_growth=rim_raw.terminal_growth,
        projections=[
            RIMProjectionResult(
                year=p.year, bv=p.bv, net_income=p.net_income,
                roe=p.roe, ri=p.ri, pv_ri=p.pv_ri,
            ) for p in rim_raw.projections
        ],
        pv_ri_sum=rim_raw.pv_ri_sum,
        terminal_ri=rim_raw.terminal_ri,
        pv_terminal=rim_raw.pv_terminal,
        equity_value=rim_raw.equity_value,
        per_share=rim_raw.per_share,
    )

    # RIM directly yields Equity Value -> reverse-calculate EV
    total_ev = rim_raw.equity_value + vi.net_debt

    # Scenarios -- recalculate RIM with rim_roe_adj + wacc_adj (Ke adjustment)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev
        sc_wacc = _adjust_wacc(wacc_result, sc.wacc_adj, vi.wacc_params.eq_w)
        sc_ke = sc_wacc.ke
        needs_recalc = (sc.rim_roe_adj != 0) or (sc.wacc_adj != 0)
        if needs_recalc:
            adj_roes = [r + sc.rim_roe_adj for r in roe_forecasts]
            try:
                sc_rim = calc_rim_engine(
                    book_value=equity_bv, roe_forecasts=adj_roes, ke=sc_ke,
                    terminal_growth=tg, shares=shares,
                    unit_multiplier=um, payout_ratio=payout,
                )
                sc_ev = sc_rim.equity_value + vi.net_debt
            except ValueError:
                pass

        # Market sentiment is cumulative
        if sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = rim_raw.per_share

    # EBITDA-based DCF is meaningless for financials -> P/E, P/BV cross-validation only
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # RIM sensitivity: Ke x Terminal Growth
    sens_rim = sensitivity_rim(
        equity_bv, roe_forecasts, ke, shares,
        terminal_growth_base=tg, payout_ratio=payout,
        unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um)

    return ValuationResult(
        primary_method="rim",
        wacc=wacc_result,
        total_ev=total_ev,
        rim=rim_result,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        cross_validations=cv_items,
        sensitivity_primary=sens_rim,
        sensitivity_primary_label=f"Ke × 영구성장률 → RIM 주당가치 ({vi.company.currency_unit})",
        peer_stats=peer_stats,
        monte_carlo=mc_result,
    )


def _run_multiples_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """Multiples-based valuation (mature/stable companies with sufficient peers)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    net_income = cons.get("net_income", 0)
    book_value = cons.get("equity", 0)
    shares = vi.company.shares_outstanding

    # Primary method selection: EV/EBITDA -> P/E -> P/BV priority
    # Use peer-based multiples or multiples specified in YAML
    primary_mv = None

    # 1. EV/EBITDA (segment multiple average)
    seg_multiples = [m for m in vi.multiples.values() if m > 0]
    if seg_multiples and ebitda_base > 0:
        avg_multiple = sum(seg_multiples) / len(seg_multiples)
        ev = round(ebitda_base * avg_multiple)
        equity = ev - vi.net_debt
        ps = per_share(equity, um, shares)
        primary_mv = MultiplesResult(
            primary_multiple_method="EV/EBITDA",
            metric_value=ebitda_base, multiple=avg_multiple,
            enterprise_value=ev, equity_value=equity, per_share=ps,
        )
    # 2. P/E fallback
    elif vi.pe_multiple > 0 and net_income > 0:
        mv = calc_pe(net_income, vi.pe_multiple, shares, um)
        primary_mv = MultiplesResult(
            primary_multiple_method="P/E",
            metric_value=mv.metric_value, multiple=mv.multiple,
            enterprise_value=mv.enterprise_value,
            equity_value=mv.equity_value, per_share=mv.per_share,
        )
    # 3. P/BV fallback
    elif vi.pbv_multiple > 0 and book_value > 0:
        mv = calc_pbv(book_value, vi.pbv_multiple, shares, um)
        primary_mv = MultiplesResult(
            primary_multiple_method="P/BV",
            metric_value=mv.metric_value, multiple=mv.multiple,
            enterprise_value=mv.enterprise_value,
            equity_value=mv.equity_value, per_share=mv.per_share,
        )
    else:
        # Insufficient multiple data -> DCF fallback
        return _run_dcf_valuation(vi, wacc_result, um)

    total_ev = primary_mv.enterprise_value or round(
        primary_mv.equity_value + vi.net_debt
    )

    # Scenarios -- recalculate EV with modified multiple when ev_multiple is set
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev
        if sc.ev_multiple is not None and primary_mv.metric_value > 0:
            sc_ev = round(primary_mv.metric_value * sc.ev_multiple)
        elif sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = primary_mv.per_share

    # DCF cross-validation (may fail for ebitda<=0 or wacc<=tg)
    dcf_ev = 0
    try:
        dcf_result = calc_dcf(
            ebitda_base, total_da_base, cons["revenue"],
            wacc_result.wacc, vi.dcf_params, vi.base_year,
        )
        dcf_ev = dcf_result.ev_dcf
    except ValueError:
        pass

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_ev, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # Multiples sensitivity: applied multiple x discount rate
    sens_mult_primary = sensitivity_multiple_range(
        primary_mv.metric_value, vi.net_debt, shares,
        primary_mv.multiple, unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um, dcf_result=dcf_result)

    return ValuationResult(
        primary_method="multiples",
        wacc=wacc_result,
        total_ev=total_ev,
        multiples_primary=primary_mv,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
        sensitivity_primary=sens_mult_primary,
        sensitivity_primary_label=f"적용 멀티플 × 할인율 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_nav_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """NAV (Net Asset Value) valuation (holding companies/REITs/asset-heavy)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_assets = cons.get("assets", 0)
    total_liabilities = cons.get("liabilities", 0)
    revaluation = vi.nav_params.revaluation if vi.nav_params else 0
    shares = vi.company.shares_outstanding

    nav_raw = calc_nav(
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        shares=shares,
        revaluation=revaluation,
        unit_multiplier=um,
    )
    nav_result = NAVResult(
        total_assets=nav_raw.total_assets,
        revaluation=nav_raw.revaluation,
        adjusted_assets=nav_raw.adjusted_assets,
        total_liabilities=nav_raw.total_liabilities,
        nav=nav_raw.nav,
        per_share=nav_raw.per_share,
    )

    # NAV = Equity Value concept -> reverse-calculate EV (for cross-validation)
    total_ev = nav_raw.nav + vi.net_debt

    # Scenarios -- apply holding company discount via nav_discount
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc = resolve_drivers(sc, vi.news_drivers)
        sc_ev = total_ev
        if sc.nav_discount != 0:
            # Apply holding company discount to NAV then add net_debt back for EV
            discounted_nav = round(nav_raw.nav * (1 - sc.nav_discount / 100))
            sc_ev = discounted_nav + vi.net_debt
        elif sc.market_sentiment_pct != 0:
            sc_ev = round(sc_ev * (1 + sc.market_sentiment_pct / 100))
        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years,
                          vi.rcps_principal, vi.rcps_years, um,
                          vi.cps_dividend_rate, vi.rcps_dividend_rate)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = nav_raw.per_share

    # DCF cross-validation (may fail for ebitda<=0 or wacc<=tg)
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_ev = 0
    try:
        dcf_result = calc_dcf(
            ebitda_base, total_da_base, cons["revenue"],
            wacc_result.wacc, vi.dcf_params, vi.base_year,
        )
        dcf_ev = dcf_result.ev_dcf
    except ValueError:
        pass

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_ev, um)

    # Peer statistics
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # NAV sensitivity: revaluation x holding company discount
    sens_nav = sensitivity_nav(
        total_assets, total_liabilities, shares,
        base_revaluation=revaluation, unit_multiplier=um,
    )

    # Monte Carlo
    mc_result = _run_monte_carlo(vi, wacc_result, _build_seg_ebitdas_from_consolidated(vi, cons), um, dcf_result=dcf_result)

    return ValuationResult(
        primary_method="nav",
        wacc=wacc_result,
        total_ev=total_ev,
        nav=nav_result,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        sensitivity_primary=sens_nav,
        sensitivity_primary_label=f"재평가 조정액 × 지주할인율 → 주당 NAV ({vi.company.currency_unit})",
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        monte_carlo=mc_result,
    )


def _get_reference_scenario(scenarios: dict) -> ScenarioParams | None:
    """Return the highest-probability scenario (for sensitivity analysis)."""
    if not scenarios:
        return None
    return max(scenarios.values(), key=lambda sc: sc.prob)


def _cross_validate_financial(vi, cons, um):
    """Financial stock cross-validation -- P/E, P/BV only (EBITDA-based DCF/SOTP meaningless)."""
    items = []
    shares = vi.company.shares_outstanding
    net_income = cons.get("net_income", 0)
    book_value = cons.get("equity", 0)

    if vi.pe_multiple > 0 and net_income > 0:
        mv = calc_pe(net_income, vi.pe_multiple, shares, um)
        items.append(CrossValidationItem(
            method="P/E", metric_value=net_income, multiple=vi.pe_multiple,
            enterprise_value=0, equity_value=mv.equity_value, per_share=mv.per_share,
        ))
    if vi.pbv_multiple > 0 and book_value > 0:
        mv = calc_pbv(book_value, vi.pbv_multiple, shares, um)
        items.append(CrossValidationItem(
            method="P/BV", metric_value=book_value, multiple=vi.pbv_multiple,
            enterprise_value=0, equity_value=mv.equity_value, per_share=mv.per_share,
        ))
    return items


def _cross_validate_common(vi, cons, ebitda_base, sotp_ev, dcf_ev, um,
                           net_debt_override=None):
    """Common multiples cross-validation."""
    net_debt = net_debt_override if net_debt_override is not None else vi.net_debt
    cv_results = cross_validate(
        revenue=cons["revenue"],
        ebitda=ebitda_base,
        net_income=cons.get("net_income", 0),
        book_value=cons.get("equity", 0),
        net_debt=net_debt,
        shares=vi.company.shares_outstanding,
        sotp_ev=sotp_ev,
        dcf_ev=dcf_ev,
        ev_revenue_multiple=vi.ev_revenue_multiple,
        pe_multiple=vi.pe_multiple,
        pbv_multiple=vi.pbv_multiple,
        ps_multiple=vi.ps_multiple,
        pffo_multiple=vi.pffo_multiple,
        ffo=vi.ffo,
        unit_multiplier=um,
    )
    return [
        CrossValidationItem(
            method=mv.method, metric_value=mv.metric_value, multiple=mv.multiple,
            enterprise_value=mv.enterprise_value, equity_value=mv.equity_value,
            per_share=mv.per_share,
        ) for mv in cv_results
    ]


def _mc_raw_to_result(mc_raw):
    """Convert MCResult to MonteCarloResult."""
    return MonteCarloResult(
        n_sims=mc_raw.n_sims, mean=mc_raw.mean, median=mc_raw.median,
        std=mc_raw.std, p5=mc_raw.p5, p25=mc_raw.p25, p75=mc_raw.p75,
        p95=mc_raw.p95, min_val=mc_raw.min_val, max_val=mc_raw.max_val,
        histogram_bins=mc_raw.histogram_bins, histogram_counts=mc_raw.histogram_counts,
    )


def _run_monte_carlo(
    vi, wacc_result, seg_ebitdas: dict[str, int], um: int,
    dcf_result=None,
    effective_multiples: dict[str, float] | None = None,
    seg_revenues: dict[str, int] | None = None,
    segment_methods: dict[str, str] | None = None,
    net_debt_override: int | None = None,
) -> MonteCarloResult | None:
    """Run Monte Carlo -- common entry point for SOTP/non-SOTP.

    Args:
        seg_ebitdas: {seg_code: ebitda} -- allocate_da result for SOTP, or consolidated-based allocation.
        effective_multiples: Distress-adjusted multiples (falls back to vi.multiples if None).
        seg_revenues: {seg_code: revenue} for ev_revenue segments.
        segment_methods: {seg_code: method} for method dispatch in MC.
    """
    if not vi.mc_enabled:
        return None

    from engine.monte_carlo import MCInput, run_monte_carlo

    mults = effective_multiples or vi.multiples
    # Include ev_revenue segments in MC even if their EBITDA is 0
    mc_mult_codes = set(seg_ebitdas.keys())
    if segment_methods:
        mc_mult_codes |= {c for c, m in segment_methods.items() if m == "ev_revenue"}
    # Revenue uncertainty for ev_revenue segments (std = mc_revenue_std_pct of base revenue)
    rev_params: dict[str, tuple[float, float]] = {}
    if segment_methods and seg_revenues:
        for c, m in segment_methods.items():
            if m == "ev_revenue":
                rev = seg_revenues.get(c, 0)
                if rev > 0:
                    rev_params[c] = (float(rev), rev * vi.mc_revenue_std_pct / 100)
    mc_params = MCInput(
        multiple_params={
            c: (mults[c], mults[c] * vi.mc_multiple_std_pct / 100)
            for c in mc_mult_codes if mults.get(c, 0) > 0
        },
        segment_methods=segment_methods or {},
        revenue_params=rev_params,
        wacc_mean=wacc_result.wacc,
        wacc_std=1.0,
        dlom_mean=vi.mc_dlom_mean,
        dlom_std=vi.mc_dlom_std,
        tg_mean=vi.dcf_params.terminal_growth,
        tg_std=0.5,
        n_sims=vi.mc_sims,
    )
    ref_sc = _get_reference_scenario(vi.scenarios)

    dcf_kwargs = {}
    if dcf_result and dcf_result.projections:
        dcf_kwargs = dict(
            wacc_for_dcf=wacc_result.wacc,
            dcf_last_fcff=dcf_result.projections[-1].fcff,
            dcf_pv_fcff_sum=dcf_result.pv_fcff_sum,
            dcf_n_periods=len(dcf_result.projections),
        )

    mc_net_debt = net_debt_override if net_debt_override is not None else vi.net_debt
    mc_raw = run_monte_carlo(
        mc_params, seg_ebitdas, mc_net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        (ref_sc.rcps_repay or 0) if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        ref_sc.shares if ref_sc else vi.company.shares_outstanding,
        irr=ref_sc.irr if ref_sc and ref_sc.irr else 5.0,
        unit_multiplier=um,
        seg_revenues=seg_revenues,
        **dcf_kwargs,
    )
    result = _mc_raw_to_result(mc_raw)

    # Per-scenario MC (lightweight: fewer sims, no histogram stored)
    from schemas.models import MCScenarioSummary
    sc_mc: dict[str, MCScenarioSummary] = {}
    for sc_code, sc in vi.scenarios.items():
        has_overrides = sc.segment_multiples or sc.segment_revenue or sc.growth_adj_pct != 0
        if not has_overrides:
            continue
        # Build scenario-specific multiples
        sc_mults = dict(mults)
        if sc.segment_multiples:
            sc_mults.update(sc.segment_multiples)
        # Build scenario-specific revenues
        sc_revs = dict(seg_revenues or {})
        if sc.segment_revenue:
            sc_revs.update(sc.segment_revenue)
        # Build scenario-specific EBITDAs (growth_adj_pct)
        sc_ebitdas = dict(seg_ebitdas)
        if sc.growth_adj_pct != 0:
            mult_g = 1 + sc.growth_adj_pct / 100
            sc_ebitdas = {c: round(e * mult_g) for c, e in seg_ebitdas.items()}
        if sc.segment_ebitda:
            sc_ebitdas.update(sc.segment_ebitda)

        sc_rev_params: dict[str, tuple[float, float]] = {}
        if segment_methods and sc_revs:
            for c, m in (segment_methods or {}).items():
                if m == "ev_revenue":
                    rev = sc_revs.get(c, 0)
                    if rev > 0:
                        sc_rev_params[c] = (float(rev), rev * vi.mc_revenue_std_pct / 100)

        sc_params = MCInput(
            multiple_params={
                c: (sc_mults[c], sc_mults[c] * vi.mc_multiple_std_pct / 100)
                for c in mc_mult_codes if sc_mults.get(c, 0) > 0
            },
            segment_methods=segment_methods or {},
            revenue_params=sc_rev_params,
            wacc_mean=wacc_result.wacc,
            wacc_std=1.0,
            dlom_mean=vi.mc_dlom_mean,
            dlom_std=vi.mc_dlom_std,
            tg_mean=vi.dcf_params.terminal_growth,
            tg_std=0.5,
            n_sims=min(2000, vi.mc_sims),
            seed=hash(sc_code) % (2**31),
        )
        sc_raw = run_monte_carlo(
            sc_params, sc_ebitdas, vi.net_debt, vi.eco_frontier,
            vi.cps_principal, vi.cps_years,
            sc.rcps_repay or 0, sc.buyback, sc.shares,
            irr=sc.irr if sc.irr else 5.0,
            unit_multiplier=um,
            seg_revenues=sc_revs,
            **dcf_kwargs,
        )
        sc_mc[sc_code] = MCScenarioSummary(
            mean=sc_raw.mean, median=sc_raw.median,
            p5=sc_raw.p5, p95=sc_raw.p95,
        )

    if sc_mc:
        result.scenario_mc = sc_mc
    return result


def _build_seg_ebitdas_from_consolidated(vi, cons) -> dict[str, int]:
    """For non-SOTP methods: allocate consolidated EBITDA to segments."""
    total_da = cons.get("dep", 0) + cons.get("amort", 0)
    ebitda = cons.get("op", 0) + total_da

    seg_codes = list(vi.segments.keys())
    if len(seg_codes) == 1:
        return {seg_codes[0]: ebitda}

    seg_data = vi.segment_data.get(vi.base_year, {})
    total_rev = sum(s.get("revenue", 0) for s in seg_data.values())
    if total_rev > 0:
        return {
            c: round(ebitda * seg_data.get(c, {}).get("revenue", 0) / total_rev)
            for c in seg_codes
        }
    return {seg_codes[0]: ebitda}
