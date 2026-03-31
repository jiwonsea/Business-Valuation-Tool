"""밸류에이션 실행 엔진 — YAML 로딩 + 방법론별 분기 실행."""

from datetime import date
from pathlib import Path

import yaml

from schemas.models import (
    CompanyProfile, WACCParams, ScenarioParams, DCFParams, DDMParams,
    PeerCompany, ValuationInput, ValuationResult, CrossValidationItem,
    MonteCarloResult, DDMValuationResult,
)
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.ddm import calc_ddm as calc_ddm_engine
from engine.scenario import calc_scenario
from engine.sensitivity import sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf
from engine.multiples import cross_validate
from engine.peer_analysis import calc_peer_stats
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method


def load_profile(path: str) -> ValuationInput:
    """YAML 프로필 → ValuationInput 파싱."""
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

    # DDM (Optional)
    ddm_params = None
    if "ddm_params" in raw:
        ddm_params = DDMParams(**raw["ddm_params"])

    # Peers
    peers = [PeerCompany(**p) for p in raw.get("peers", [])]

    # unit_multiplier 자동 감지 (YAML에 명시되지 않은 경우)
    if "unit_multiplier" not in raw.get("company", {}):
        latest_yr = max(consolidated.keys())
        revenue = consolidated[latest_yr].get("revenue", 0)
        label, multiplier = detect_unit(revenue, company.market)
        company.currency_unit = label
        company.unit_multiplier = multiplier

    return ValuationInput(
        company=company,
        valuation_method=raw.get("valuation_method", "auto"),
        industry=raw.get("industry", ""),
        segments=segments,
        segment_data=segment_data,
        consolidated=consolidated,
        wacc_params=wacc_params,
        multiples=multiples,
        scenarios=scenarios,
        dcf_params=dcf_params,
        ddm_params=ddm_params,
        cps_principal=raw.get("cps_principal", 0),
        cps_years=raw.get("cps_years", 0),
        net_debt=raw.get("net_debt", 0),
        eco_frontier=raw.get("eco_frontier", 0),
        peers=peers,
        base_year=raw.get("base_year", 2025),
        ev_revenue_multiple=raw.get("ev_revenue_multiple", 0.0),
        pe_multiple=raw.get("pe_multiple", 0.0),
        pbv_multiple=raw.get("pbv_multiple", 0.0),
        mc_enabled=raw.get("mc_enabled", False),
        mc_sims=raw.get("mc_sims", 10_000),
        mc_multiple_std_pct=raw.get("mc_multiple_std_pct", 15.0),
        mc_dlom_mean=raw.get("mc_dlom_mean", 0.0),
        mc_dlom_std=raw.get("mc_dlom_std", 5.0),
    )


def run_valuation(vi: ValuationInput) -> ValuationResult:
    """전체 밸류에이션 파이프라인 실행 — 방법론별 분기."""
    # 방법론 결정
    method = vi.valuation_method
    if method == "auto":
        method = suggest_method(
            n_segments=len(vi.segments),
            legal_status=vi.company.legal_status,
            industry=vi.industry,
        )

    # 공통: WACC
    wacc_result = calc_wacc(vi.wacc_params)
    um = vi.company.unit_multiplier

    if method == "sotp":
        return _run_sotp_valuation(vi, wacc_result, um)
    elif method == "ddm":
        return _run_ddm_valuation(vi, wacc_result, um)
    elif method == "dcf_primary":
        return _run_dcf_valuation(vi, wacc_result, um)
    else:
        # multiples 등 → DCF primary로 fallback
        return _run_dcf_valuation(vi, wacc_result, um)


def _run_sotp_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """SOTP 기반 밸류에이션 (다부문 기업)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    # D&A 배분 (전 연도)
    da_allocations = {}
    for yr, segs in vi.segment_data.items():
        c = vi.consolidated[yr]
        total_da = c["dep"] + c["amort"]
        da_allocations[yr] = allocate_da(segs, total_da)

    # SOTP (base year)
    base_alloc = da_allocations[by]
    sotp, total_ev = calc_sotp(base_alloc, vi.multiples)

    # 시나리오
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF 교차검증
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    # 민감도
    sens_mult, _, _ = sensitivity_multiples(
        base_alloc, vi.multiples, vi.net_debt, vi.eco_frontier,
        vi.company.shares_total, unit_multiplier=um,
    )
    # IRR/DLOM 민감도: 가장 확률 높은 시나리오 기준
    ref_sc = _get_reference_scenario(vi.scenarios)
    sens_irr, _, _ = sensitivity_irr_dlom(
        total_ev, vi.net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        ref_sc.rcps_repay if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        vi.company.shares_ordinary,
        unit_multiplier=um,
    )
    sens_dcf_rows, _, _ = sensitivity_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        vi.dcf_params, vi.base_year,
    )

    # 멀티플 교차검증
    cv_items = _cross_validate_common(vi, cons, ebitda_base, total_ev, dcf_result.ev_dcf, um)

    # Monte Carlo
    mc_result = _run_mc_if_enabled(vi, wacc_result, base_alloc, um)

    # Peer 통계
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
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


def _run_dcf_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DCF 기반 밸류에이션 (단일부문 또는 성장 기업)."""
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

    # 시나리오 (DCF EV 기반)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF 민감도
    sens_dcf_rows, _, _ = sensitivity_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        vi.dcf_params, vi.base_year,
    )

    # 멀티플 교차검증 (SOTP EV = 0)
    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_result.ev_dcf, um)

    # Peer 통계
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    return ValuationResult(
        primary_method="dcf_primary",
        wacc=wacc_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        sensitivity_dcf=sens_dcf_rows,
    )


def _run_ddm_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """DDM 기반 밸류에이션 (금융업종)."""
    if not vi.ddm_params:
        raise ValueError(
            "DDM 방법론이 선택되었으나 ddm_params가 없습니다. "
            "YAML에 ddm_params: {dps: ..., dividend_growth: ...}를 추가하세요."
        )

    ke = wacc_result.ke
    ddm_raw = calc_ddm_engine(vi.ddm_params.dps, vi.ddm_params.dividend_growth, ke)
    ddm_result = DDMValuationResult(
        dps=ddm_raw.dps,
        growth=ddm_raw.growth,
        ke=ddm_raw.ke,
        equity_per_share=ddm_raw.equity_per_share,
    )

    # DDM은 주당 가치를 직접 산출 → EV 역산 (교차검증용)
    total_ev = ddm_raw.equity_per_share * vi.company.shares_total // (um or 1)

    # 시나리오 (DDM EV 기반)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    # 시나리오 미설정 시 DDM 값 직접 사용
    if not scenario_results:
        total_weighted = ddm_raw.equity_per_share

    # DCF 교차검증
    by = vi.base_year
    cons = vi.consolidated[by]
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_result.ev_dcf, um)

    # Peer 통계
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    return ValuationResult(
        primary_method="ddm",
        wacc=wacc_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        ddm=ddm_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
    )


def _get_reference_scenario(scenarios: dict) -> ScenarioParams | None:
    """가장 확률 높은 시나리오 반환 (민감도 분석용)."""
    if not scenarios:
        return None
    return max(scenarios.values(), key=lambda sc: sc.prob)


def _cross_validate_common(vi, cons, ebitda_base, sotp_ev, dcf_ev, um):
    """공통 멀티플 교차검증."""
    cv_results = cross_validate(
        revenue=cons["revenue"],
        ebitda=ebitda_base,
        net_income=cons.get("net_income", 0),
        book_value=cons.get("equity", 0),
        net_debt=vi.net_debt,
        shares=vi.company.shares_total,
        sotp_ev=sotp_ev,
        dcf_ev=dcf_ev,
        ev_revenue_multiple=vi.ev_revenue_multiple,
        pe_multiple=vi.pe_multiple,
        pbv_multiple=vi.pbv_multiple,
        unit_multiplier=um,
    )
    return [
        CrossValidationItem(
            method=mv.method, metric_value=mv.metric_value, multiple=mv.multiple,
            enterprise_value=mv.enterprise_value, equity_value=mv.equity_value,
            per_share=mv.per_share,
        ) for mv in cv_results
    ]


def _run_mc_if_enabled(vi, wacc_result, base_alloc, um):
    """Monte Carlo 실행 (mc_enabled=True인 경우)."""
    if not vi.mc_enabled:
        return None

    from engine.monte_carlo import MCInput, run_monte_carlo
    seg_ebitdas = {code: base_alloc[code].ebitda for code in vi.segments}
    mc_params = MCInput(
        multiple_params={
            code: (vi.multiples[code], vi.multiples[code] * vi.mc_multiple_std_pct / 100)
            for code in vi.segments if vi.multiples[code] > 0
        },
        wacc_mean=wacc_result.wacc,
        wacc_std=1.0,
        dlom_mean=vi.mc_dlom_mean,
        dlom_std=vi.mc_dlom_std,
        tg_mean=vi.dcf_params.terminal_growth,
        tg_std=0.5,
        n_sims=vi.mc_sims,
    )
    ref_sc = _get_reference_scenario(vi.scenarios)
    mc_raw = run_monte_carlo(
        mc_params, seg_ebitdas, vi.net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        ref_sc.rcps_repay if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        ref_sc.shares if ref_sc else vi.company.shares_total,
        irr=ref_sc.irr if ref_sc and ref_sc.irr else 5.0,
        unit_multiplier=um,
    )
    return MonteCarloResult(
        n_sims=mc_raw.n_sims, mean=mc_raw.mean, median=mc_raw.median,
        std=mc_raw.std, p5=mc_raw.p5, p25=mc_raw.p25, p75=mc_raw.p75,
        p95=mc_raw.p95, min_val=mc_raw.min_val, max_val=mc_raw.max_val,
        histogram_bins=mc_raw.histogram_bins, histogram_counts=mc_raw.histogram_counts,
    )
