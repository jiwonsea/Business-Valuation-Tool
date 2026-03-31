"""밸류에이션 실행 엔진 — YAML 로딩 + 방법론별 분기 실행."""

from datetime import date
from pathlib import Path

import yaml

from schemas.models import (
    CompanyProfile, WACCParams, ScenarioParams, DCFParams, DDMParams, NAVParams,
    RIMParams, RIMProjectionResult, RIMValuationResult,
    PeerCompany, ValuationInput, ValuationResult, CrossValidationItem,
    MonteCarloResult, DDMValuationResult, NAVResult, MultiplesResult,
)
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.ddm import calc_ddm as calc_ddm_engine
from engine.rim import calc_rim as calc_rim_engine
from engine.scenario import calc_scenario
from engine.sensitivity import (
    sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf,
    sensitivity_ddm, sensitivity_rim, sensitivity_nav, sensitivity_multiple_range,
)
from engine.multiples import cross_validate, calc_ev_revenue, calc_pe, calc_pbv
from engine.peer_analysis import calc_peer_stats
from engine.nav import calc_nav
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method


def _seg_names(vi: ValuationInput) -> dict[str, str]:
    """segments 딕셔너리에서 {code: name} 매핑 추출."""
    return {code: info["name"] for code, info in vi.segments.items()}


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

    # RIM (Optional)
    rim_params = None
    if "rim_params" in raw:
        rim_params = RIMParams(**raw["rim_params"])

    # NAV (Optional)
    nav_params = None
    if "nav_params" in raw:
        nav_params = NAVParams(**raw["nav_params"])

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
    )


def run_valuation(vi: ValuationInput) -> ValuationResult:
    """전체 밸류에이션 파이프라인 실행 — 방법론별 분기."""
    # 금융업종 자동 감지 → Hamada 스킵
    from engine.method_selector import _FINANCIAL_KEYWORDS
    industry_lower = vi.industry.lower()
    if any(kw in industry_lower for kw in _FINANCIAL_KEYWORDS):
        vi.wacc_params.is_financial = True

    # 공통: WACC (방법론 판단 전에 필요 — 금융주 DDM/RIM 판단에 Ke 사용)
    wacc_result = calc_wacc(vi.wacc_params)
    um = vi.company.unit_multiplier

    # 방법론 결정
    method = vi.valuation_method
    if method == "auto":
        # 금융주 DDM/RIM 판단용: ROE 계산
        by = vi.base_year
        cons = vi.consolidated[by]
        equity_bv = cons.get("equity", 0)
        net_income = cons.get("net_income", 0)
        roe = (net_income / equity_bv * 100) if equity_bv > 0 else 0.0

        method = suggest_method(
            n_segments=len(vi.segments),
            legal_status=vi.company.legal_status,
            industry=vi.industry,
            has_peers=len(vi.peers) >= 3,
            roe=roe,
            ke=wacc_result.ke,
            has_ddm_params=vi.ddm_params is not None,
            has_rim_params=vi.rim_params is not None,
        )

    if method == "sotp":
        return _run_sotp_valuation(vi, wacc_result, um)
    elif method == "ddm":
        return _run_ddm_valuation(vi, wacc_result, um)
    elif method == "rim":
        return _run_rim_valuation(vi, wacc_result, um)
    elif method == "nav":
        return _run_nav_valuation(vi, wacc_result, um)
    elif method == "multiples":
        return _run_multiples_valuation(vi, wacc_result, um)
    elif method == "dcf_primary":
        return _run_dcf_valuation(vi, wacc_result, um)
    else:
        return _run_dcf_valuation(vi, wacc_result, um)


def _calc_effective_net_debt(vi: ValuationInput) -> int:
    """금융자회사 분리 SOTP 시 유효 순차입금 계산.

    금융 세그먼트(method=pbv/pe)의 net_debt는 P/BV에 이미 내재되어 있으므로
    전체 net_debt에서 차감한다. segment_net_debt가 없으면 net_debt 그대로 반환.
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
    """금융자회사 분리 SOTP 여부 판단."""
    return bool(vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in vi.segments.values()
    )


def _run_sotp_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """SOTP 기반 밸류에이션 (다부문 기업, Mixed Method 지원)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    # 금융자회사 분리 SOTP 판단
    is_mixed = _has_mixed_sotp(vi)
    effective_net_debt = _calc_effective_net_debt(vi) if is_mixed else vi.net_debt

    # 세그먼트 method 정보 추출
    seg_methods = {c: info.get("method", "ev_ebitda") for c, info in vi.segments.items()}

    # D&A 배분 (전 연도) — 금융 부문 제외
    da_allocations = {}
    for yr, segs in vi.segment_data.items():
        c = vi.consolidated[yr]
        total_da = c["dep"] + c["amort"]
        da_allocations[yr] = allocate_da(segs, total_da, seg_methods if is_mixed else None)

    # SOTP (base year) — Mixed Method 지원
    base_alloc = da_allocations[by]
    sotp, total_ev = calc_sotp(
        base_alloc, vi.multiples,
        segments_info=vi.segments if is_mixed else None,
    )

    # 시나리오 — market_sentiment_pct 적용 (SOTP는 DCF driver 미적용)
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc_ev = total_ev
        sentiment = getattr(sc, "market_sentiment_pct", 0.0)
        if sentiment != 0:
            sc_ev = round(sc_ev * (1 + sentiment / 100))
        r = calc_scenario(sc, sc_ev, effective_net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DCF 교차검증 — mixed SOTP면 제조 부문만
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

    # 민감도
    sens_mult, _, _ = sensitivity_multiples(
        base_alloc, vi.multiples, effective_net_debt, vi.eco_frontier,
        vi.company.shares_total, unit_multiplier=um,
    )
    ref_sc = _get_reference_scenario(vi.scenarios)
    sens_irr, _, _ = sensitivity_irr_dlom(
        total_ev, effective_net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        ref_sc.rcps_repay if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        vi.company.shares_ordinary,
        unit_multiplier=um,
    )
    sens_dcf_rows, _, _ = sensitivity_dcf(
        ebitda_base, dcf_da_base, dcf_revenue,
        vi.dcf_params, vi.base_year,
    )

    # 멀티플 교차검증 — effective_net_debt 적용
    cv_items = _cross_validate_common(
        vi, cons, ebitda_base, total_ev, dcf_result.ev_dcf, um,
        net_debt_override=effective_net_debt if is_mixed else None,
    )

    # Monte Carlo
    mc_result = _run_mc_if_enabled(vi, wacc_result, base_alloc, um, dcf_result=dcf_result)

    # Peer 통계
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

    # SOTP 교차검증 (다부문 기업이면 SOTP도 계산)
    sotp_ev = 0
    sotp_result = {}
    da_allocations = {}
    if len(vi.segments) > 1 and by in vi.segment_data:
        da_allocations[by] = allocate_da(vi.segment_data[by], total_da_base)
        sotp_result, sotp_ev = calc_sotp(da_allocations[by], vi.multiples)

    cv_items = _cross_validate_common(vi, cons, ebitda_base, sotp_ev, dcf_result.ev_dcf, um)

    # Peer 통계
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
    """DDM 기반 밸류에이션 (금융업종)."""
    if not vi.ddm_params:
        raise ValueError(
            "DDM 방법론이 선택되었으나 ddm_params가 없습니다. "
            "YAML에 ddm_params: {dps: ..., dividend_growth: ...}를 추가하세요."
        )

    ke = wacc_result.ke
    buyback_ps = vi.ddm_params.buyback_per_share
    base_growth = vi.ddm_params.dividend_growth

    # Base DDM (기본 성장률)
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
    )

    # 시나리오별 DDM: 각 시나리오에 ddm_growth가 있으면 해당 성장률로 재계산
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        sc_growth = sc.ddm_growth if sc.ddm_growth is not None else base_growth
        sc_ddm = calc_ddm_engine(
            vi.ddm_params.dps, sc_growth, ke,
            buyback_per_share=buyback_ps,
        )
        sc_ev = sc_ddm.equity_per_share * vi.company.shares_total // (um or 1)
        r = calc_scenario(sc, sc_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    # DDM base EV (교차검증용)
    total_ev = ddm_raw.equity_per_share * vi.company.shares_total // (um or 1)

    # 시나리오 미설정 시 DDM 값 직접 사용
    if not scenario_results:
        total_weighted = ddm_raw.equity_per_share

    # 금융주는 EBITDA 기반 DCF가 무의미 → P/E, P/BV만 교차검증
    by = vi.base_year
    cons = vi.consolidated[by]
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer 통계
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # DDM 민감도: Ke × 배당성장률
    sens_ddm = sensitivity_ddm(
        vi.ddm_params.dps, ke, base_growth,
        buyback_per_share=buyback_ps,
    )

    return ValuationResult(
        primary_method="ddm",
        wacc=wacc_result,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        ddm=ddm_result,
        cross_validations=cv_items,
        peer_stats=peer_stats,
        sensitivity_primary=sens_ddm,
        sensitivity_primary_label=f"Ke × 배당성장률 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_rim_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """RIM(잔여이익모델) 기반 밸류에이션 (금융업종 — BV 기반)."""
    by = vi.base_year
    cons = vi.consolidated[by]
    equity_bv = cons.get("equity", 0)
    shares = vi.company.shares_total
    ke = wacc_result.ke

    # RIM 파라미터: 명시적 rim_params 또는 재무제표 기반 자동 생성
    if vi.rim_params:
        roe_forecasts = vi.rim_params.roe_forecasts
        tg = vi.rim_params.terminal_growth
        payout = vi.rim_params.payout_ratio
    else:
        # ROE를 최근 재무제표에서 역산하여 5년 예측 (점진 수렴)
        net_income = cons.get("net_income", 0)
        current_roe = (net_income / equity_bv * 100) if equity_bv > 0 else ke
        # ROE가 Ke 방향으로 점진 수렴 (5년)
        roe_forecasts = [
            round(current_roe + (ke - current_roe) * i / 5, 1)
            for i in range(5)
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

    # RIM은 Equity Value 직접 산출 → EV 역산
    total_ev = rim_raw.equity_value + vi.net_debt

    # 시나리오
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = rim_raw.per_share

    # 금융주는 EBITDA 기반 DCF가 무의미 → P/E, P/BV만 교차검증
    cv_items = _cross_validate_financial(vi, cons, um)

    # Peer 통계
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # RIM 민감도: Ke × Terminal Growth
    sens_rim = sensitivity_rim(
        equity_bv, roe_forecasts, ke, shares,
        terminal_growth_base=tg, payout_ratio=payout,
        unit_multiplier=um,
    )

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
    )


def _run_multiples_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """상대가치평가법 기반 밸류에이션 (성숙/안정 기업 + Peer 충분)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    net_income = cons.get("net_income", 0)
    book_value = cons.get("equity", 0)
    shares = vi.company.shares_total

    # 주방법론 선택: EV/EBITDA → P/E → P/BV 우선순위
    # Peer 기반 멀티플 또는 YAML에 명시된 멀티플 사용
    primary_mv = None

    # 1. EV/EBITDA (세그먼트 멀티플 평균)
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
        # 멀티플 데이터 부족 → DCF fallback
        return _run_dcf_valuation(vi, wacc_result, um)

    total_ev = primary_mv.enterprise_value or round(
        primary_mv.equity_value + vi.net_debt
    )

    # 시나리오
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = primary_mv.per_share

    # DCF 교차검증
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_result.ev_dcf, um)

    # Peer 통계
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # Multiples 민감도: 적용 멀티플 × 할인율
    sens_mult_primary = sensitivity_multiple_range(
        primary_mv.metric_value, vi.net_debt, shares,
        primary_mv.multiple, unit_multiplier=um,
    )

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
        sensitivity_primary=sens_mult_primary,
        sensitivity_primary_label=f"적용 멀티플 × 할인율 → 주당가치 ({vi.company.currency_unit})",
    )


def _run_nav_valuation(vi: ValuationInput, wacc_result, um: int) -> ValuationResult:
    """NAV(순자산가치) 기반 밸류에이션 (지주사/리츠/자산중심)."""
    by = vi.base_year
    cons = vi.consolidated[by]

    total_assets = cons.get("assets", 0)
    total_liabilities = cons.get("liabilities", 0)
    revaluation = vi.nav_params.revaluation if vi.nav_params else 0
    shares = vi.company.shares_total

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

    # NAV = Equity Value 개념 → EV 역산 (교차검증용)
    total_ev = nav_raw.nav + vi.net_debt

    # 시나리오
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years, um)
        scenario_results[code] = r
        total_weighted += r.weighted

    if not scenario_results:
        total_weighted = nav_raw.per_share

    # DCF 교차검증
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    cv_items = _cross_validate_common(vi, cons, ebitda_base, 0, dcf_result.ev_dcf, um)

    # Peer 통계
    seg_names = _seg_names(vi)
    peer_stats = calc_peer_stats(vi.peers, vi.multiples, seg_names)

    # NAV 민감도: 재평가 × 지주할인율
    sens_nav = sensitivity_nav(
        total_assets, total_liabilities, shares,
        base_revaluation=revaluation, unit_multiplier=um,
    )

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
    )


def _get_reference_scenario(scenarios: dict) -> ScenarioParams | None:
    """가장 확률 높은 시나리오 반환 (민감도 분석용)."""
    if not scenarios:
        return None
    return max(scenarios.values(), key=lambda sc: sc.prob)


def _cross_validate_financial(vi, cons, um):
    """금융주 교차검증 — P/E, P/BV만 (EBITDA 기반 DCF/SOTP 무의미)."""
    items = []
    shares = vi.company.shares_total
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
    """공통 멀티플 교차검증."""
    net_debt = net_debt_override if net_debt_override is not None else vi.net_debt
    cv_results = cross_validate(
        revenue=cons["revenue"],
        ebitda=ebitda_base,
        net_income=cons.get("net_income", 0),
        book_value=cons.get("equity", 0),
        net_debt=net_debt,
        shares=vi.company.shares_total,
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


def _run_mc_if_enabled(vi, wacc_result, base_alloc, um, dcf_result=None):
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

    # DCF 정보 전달 (WACC/TG 샘플링 → TV 변동 반영)
    dcf_kwargs = {}
    if dcf_result and dcf_result.projections:
        dcf_kwargs = dict(
            wacc_for_dcf=wacc_result.wacc,
            dcf_last_fcff=dcf_result.projections[-1].fcff,
            dcf_pv_fcff_sum=dcf_result.pv_fcff_sum,
            dcf_n_periods=len(dcf_result.projections),
        )

    mc_raw = run_monte_carlo(
        mc_params, seg_ebitdas, vi.net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        ref_sc.rcps_repay if ref_sc else 0,
        ref_sc.buyback if ref_sc else 0,
        ref_sc.shares if ref_sc else vi.company.shares_total,
        irr=ref_sc.irr if ref_sc and ref_sc.irr else 5.0,
        unit_multiplier=um,
        **dcf_kwargs,
    )
    return MonteCarloResult(
        n_sims=mc_raw.n_sims, mean=mc_raw.mean, median=mc_raw.median,
        std=mc_raw.std, p5=mc_raw.p5, p25=mc_raw.p25, p75=mc_raw.p75,
        p95=mc_raw.p95, min_val=mc_raw.min_val, max_val=mc_raw.max_val,
        histogram_bins=mc_raw.histogram_bins, histogram_counts=mc_raw.histogram_counts,
    )
