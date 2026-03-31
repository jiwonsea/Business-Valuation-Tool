"""범용 기업가치 분석 CLI.

Usage:
    python cli.py --profile profiles/sk_ecoplant.yaml
"""

import argparse
import sys
from datetime import date
from pathlib import Path

import yaml

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from schemas.models import (
    CompanyProfile, WACCParams, ScenarioParams, DCFParams, PeerCompany,
    ValuationInput, ValuationResult, CrossValidationItem, MonteCarloResult,
    MarketComparisonResult,
)
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.scenario import calc_scenario
from engine.sensitivity import sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf
from engine.multiples import cross_validate
from engine.peer_analysis import calc_peer_stats
from engine.units import detect_unit, per_share
from engine.method_selector import suggest_method
from engine.market_comparison import compare_to_market


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
    elif method == "dcf_primary":
        return _run_dcf_valuation(vi, wacc_result, um)
    else:
        # ddm, multiples 등 → DCF primary로 fallback (추후 확장)
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


def print_report(vi: ValuationInput, result: ValuationResult):
    """콘솔 출력."""
    by = vi.base_year
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
    unit = vi.company.currency_unit
    currency_sym = "원" if vi.company.market == "KR" else "$"

    print("=" * 60)
    print(f"{vi.company.name} 기업가치평가 모델 [{result.primary_method.upper()}]")
    print("=" * 60)

    # WACC
    w = result.wacc
    print(f"\n[WACC] βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%, WACC={w.wacc}%")

    # D&A 배분 (SOTP인 경우만)
    if result.da_allocations and by in result.da_allocations:
        total_da = vi.consolidated[by]["dep"] + vi.consolidated[by]["amort"]
        print(f"\n[D&A 배분] 총 D&A = {total_da:,}{unit}")
        print(f"{'부문':<20} {'자산비중':>10} {'D&A':>12} {'EBITDA':>14}")
        print("-" * 60)
        alloc = result.da_allocations[by]
        for code in vi.segments:
            if code in alloc:
                a = alloc[code]
                print(f"{seg_names.get(code, code):<20} {a.asset_share:>9.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}")

    # SOTP (있는 경우)
    if result.sotp:
        print(f"\n[SOTP EV] {result.total_ev:>14,}{unit}")

    # 시나리오
    if result.scenarios:
        print(f"\n[시나리오 분석]")
        for code, sc in vi.scenarios.items():
            if code in result.scenarios:
                r = result.scenarios[code]
                print(f"  시나리오 {code} ({sc.name}, {sc.prob}%): "
                      f"Equity={r.equity_value:>12,}{unit}, "
                      f"주당(DLOM후)={r.post_dlom:>8,}{currency_sym}, "
                      f"가중기여={r.weighted:>6,}{currency_sym}")
        print(f"\n  >> 확률가중 주당 가치: {result.weighted_value:,}{currency_sym}")

    # DCF
    if result.dcf:
        dcf = result.dcf
        print(f"\n[DCF]")
        print(f"  DCF EV: {dcf.ev_dcf:>12,}{unit}")
        if result.sotp and result.total_ev > 0:
            diff_pct = (dcf.ev_dcf - result.total_ev) / result.total_ev * 100
            print(f"  SOTP EV: {result.total_ev:>12,}{unit}")
            print(f"  DCF vs SOTP: {diff_pct:>+.1f}%")

    # 시장가격 비교
    if result.market_comparison:
        mc = result.market_comparison
        print(f"\n[시장가격 비교]")
        print(f"  내재가치: {mc.intrinsic_value:,}{currency_sym}")
        print(f"  현재 주가: {mc.market_price:,.0f}{currency_sym}")
        print(f"  괴리율: {mc.gap_ratio:+.1%}")
        if mc.flag:
            print(f"  ⚠ {mc.flag}")

    # Monte Carlo
    if result.monte_carlo:
        mc = result.monte_carlo
        print(f"\n[Monte Carlo 시뮬레이션 ({mc.n_sims:,}회)]")
        print(f"  Mean: {mc.mean:>10,}{currency_sym}  |  Median: {mc.median:>10,}{currency_sym}  |  Std: {mc.std:>8,}{currency_sym}")
        print(f"  5th: {mc.p5:>11,}{currency_sym}  |  25th: {mc.p25:>12,}{currency_sym}")
        print(f"  75th: {mc.p75:>10,}{currency_sym}  |  95th: {mc.p95:>12,}{currency_sym}")

    # Peer
    if result.peer_stats:
        print(f"\n[Peer 멀티플 통계 (EV/EBITDA)]")
        print(f"{'부문':<20} {'N':>3} {'Median':>8} {'Mean':>8} {'Q1':>8} {'Q3':>8} {'적용':>8}")
        print("-" * 68)
        for ps in result.peer_stats:
            print(f"{ps.segment_name:<20} {ps.count:>3} {ps.ev_ebitda_median:>7.1f}x "
                  f"{ps.ev_ebitda_mean:>7.1f}x {ps.ev_ebitda_q1:>7.1f}x "
                  f"{ps.ev_ebitda_q3:>7.1f}x {ps.applied_multiple:>7.1f}x")

    # 멀티플 교차검증
    if result.cross_validations:
        print(f"\n[멀티플 교차검증]")
        print(f"{'방법론':<20} {'지표값':>12} {'배수':>8} {'EV':>14} {'Equity':>14} {'주당가치':>10}")
        print("-" * 82)
        for cv in result.cross_validations:
            print(f"{cv.method:<20} {cv.metric_value:>12,.0f} {cv.multiple:>7.1f}x "
                  f"{cv.enterprise_value:>13,} {cv.equity_value:>13,} {cv.per_share:>9,}")

    print("\n" + "=" * 60)
    print(f"완료! [{result.primary_method.upper()}] 확률가중 주당 가치: {result.weighted_value:,}{currency_sym}")
    print("=" * 60)


def auto_fetch(company_query: str) -> dict:
    """기업명/ticker 입력 → 자동 판별 → 재무 데이터 수집 → raw dict 반환.

    Usage:
        python cli.py --company "Apple"
        python cli.py --company "AAPL"
        python cli.py --company "삼성E&A"
    """
    from pipeline.data_fetcher import DataFetcher

    fetcher = DataFetcher()

    # Step 1: 기업 식별
    print(f"\n[1/3] 기업 식별 중: '{company_query}'")
    identity = fetcher.identify(company_query)
    if not identity:
        print(f"  [ERROR] 기업을 찾을 수 없습니다: {company_query}")
        return {}

    market_label = "한국 (DART)" if identity.market == "KR" else "미국 (SEC EDGAR)"
    print(f"  → {identity.name} | {market_label}")
    if identity.ticker:
        print(f"    Ticker: {identity.ticker}")
    if identity.cik:
        print(f"    CIK: {identity.cik}")
    if identity.corp_code:
        print(f"    DART corp_code: {identity.corp_code}")

    # Step 2: 재무제표 수집
    print(f"\n[2/3] 재무제표 수집 중...")
    financials = fetcher.fetch_financials(identity)
    if not financials:
        print("  [ERROR] 재무제표를 수집할 수 없습니다.")
        return {}

    for year, data in sorted(financials.items(), reverse=True):
        rev = data.get("revenue", 0)
        op = data.get("op", 0)
        unit = "$M" if identity.market == "US" else "백만원"
        print(f"  {year}: 매출 {rev:,}{unit}, 영업이익 {op:,}{unit}")

    # Step 3: 주식수 / 시장 데이터
    print(f"\n[3/3] 시장 데이터 수집 중...")
    shares_info = fetcher.fetch_shares(identity)
    if shares_info.get("shares_total"):
        print(f"  총 주식수: {shares_info['shares_total']:,}")
    if shares_info.get("price"):
        currency = shares_info.get("currency", "")
        print(f"  현재가: {shares_info['price']:,.2f} {currency}")

    # Step 4: YAML 프로필 자동 생성
    yaml_path = _generate_draft_profile(identity, financials, shares_info)

    print(f"\n{'='*60}")
    print(f"데이터 수집 완료: {identity.name}")
    print(f"시장: {identity.market} | 연도: {sorted(financials.keys())}")
    print(f"{'='*60}")
    if yaml_path:
        print(f"\n[Draft YAML 생성됨] {yaml_path}")
        print(f"  → 부문 데이터, 멀티플, 시나리오를 편집한 후:")
        print(f"    python cli.py --profile {yaml_path} --excel")

    return {
        "identity": identity,
        "financials": financials,
        "shares": shares_info,
        "yaml_path": yaml_path,
    }


def _generate_draft_profile(identity, financials: dict, shares_info: dict) -> str | None:
    """수집된 데이터로 draft YAML 프로필 자동 생성."""
    import re

    years = sorted(financials.keys())
    if not years:
        return None

    latest = years[-1]
    cons = financials[latest]

    is_us = identity.market == "US"
    currency = "USD" if is_us else "KRW"
    unit = "$M" if is_us else "백만원"

    shares_total = shares_info.get("shares_total", 0)
    shares_ordinary = shares_info.get("shares_ordinary", shares_total)

    # D/E ratio
    equity = cons.get("equity", 0)
    liabilities = cons.get("liabilities", 0)
    de_ratio = round(liabilities / equity * 100, 1) if equity > 0 else 100.0

    # WACC defaults by market
    if is_us:
        rf, erp, bu, tax, kd_pre = 4.25, 5.50, 1.0, 21.0, 5.50
    else:
        rf, erp, bu, tax, kd_pre = 3.50, 7.00, 0.75, 22.0, 5.50

    eq_w = round(100 / (1 + de_ratio / 100), 1)

    # 파일명 생성
    safe_name = re.sub(r"[^\w\-]", "_", identity.name.lower().replace(" ", "_"))
    if identity.ticker:
        safe_name = identity.ticker.lower()
    yaml_filename = f"profiles/{safe_name}.yaml"
    yaml_path = str(Path(__file__).parent / yaml_filename)

    # consolidated YAML 블록
    cons_blocks = []
    for yr in years:
        d = financials[yr]
        cons_blocks.append(f"""  {yr}:
    revenue: {d.get('revenue', 0)}
    op: {d.get('op', 0)}
    net_income: {d.get('net_income', 0)}
    assets: {d.get('assets', 0)}
    liabilities: {d.get('liabilities', 0)}
    equity: {d.get('equity', 0)}
    dep: {d.get('dep', 0)}
    amort: {d.get('amort', 0)}
    gross_borr: {d.get('gross_borr', 0)}
    net_borr: {d.get('net_borr', 0)}
    de_ratio: {d.get('de_ratio', 0)}""")

    net_debt = cons.get("net_borr", 0)

    content = f"""# {identity.name} — Auto-generated draft profile
# Source: {'SEC EDGAR' if is_us else 'DART'} | Generated by valuation-tool
# TODO: Add segment data, multiples, and scenario parameters

company:
  name: "{identity.name}"
  legal_status: "{'상장' if is_us or identity.legal_status == '상장' else '비상장'}"
  market: "{identity.market}"
  currency: "{currency}"
  currency_unit: "{unit}"
  ticker: {f'"{identity.ticker}"' if identity.ticker else 'null'}
  cik: {f'"{identity.cik}"' if identity.cik else 'null'}
  corp_code: {f'"{identity.corp_code}"' if identity.corp_code else 'null'}
  shares_total: {shares_total}
  shares_ordinary: {shares_ordinary}
  shares_preferred: 0
  analysis_date: "{date.today().isoformat()}"

# TODO: Define business segments (REQUIRED for SOTP)
segments:
  MAIN:
    name: "Main Business"
    multiple: 10.0   # TODO: Set appropriate EV/EBITDA multiple

# TODO: Add segment-level financials (revenue, op, assets per segment)
segment_data:
  {latest}:
    MAIN: {{revenue: {cons.get('revenue', 0)}, gross_profit: 0, op: {cons.get('op', 0)}, assets: {cons.get('assets', 0)}}}

consolidated:
{chr(10).join(cons_blocks)}

wacc_params:
  rf: {rf}
  erp: {erp}
  bu: {bu}
  de: {de_ratio}
  tax: {tax}
  kd_pre: {kd_pre}
  eq_w: {eq_w}

# TODO: Design scenarios appropriate for this company
scenarios:
  Base:
    name: "Base Case"
    prob: 50
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_total}
    desc: "Base case with consensus estimates"
  Bull:
    name: "Bull Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_total}
    desc: "Upside scenario"
  Bear:
    name: "Bear Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: {'20' if not is_us else '0'}
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_total}
    desc: "Downside scenario"

dcf_params:
  ebitda_growth_rates: [0.10, 0.08, 0.06, 0.05, 0.04]
  tax_rate: {tax}
  capex_to_da: 1.10
  nwc_to_rev_delta: 0.05
  terminal_growth: 2.5

cps_principal: 0
cps_years: 0
net_debt: {net_debt}
eco_frontier: 0
base_year: {latest}

peers: []
  # TODO: Add peer companies
  # - {{name: "Peer Co", segment_code: "MAIN", ev_ebitda: 10.0, notes: ""}}
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)

    return yaml_filename


def auto_analyze(company_query: str, output_dir: str | None = None):
    """AI 기반 end-to-end 자동 분석.

    1. 데이터 수집 (auto_fetch)
    2. AI가 부문/멀티플/시나리오 설계
    3. YAML 프로필 보강
    4. 밸류에이션 실행 + Excel 출력

    Usage:
        python cli.py --company "삼성E&A" --auto
    """
    import json as json_mod

    # Step 1: 데이터 수집
    fetch_result = auto_fetch(company_query)
    if not fetch_result or not fetch_result.get("yaml_path"):
        print("[ERROR] 데이터 수집 실패. --auto 중단.")
        return None

    yaml_path = str(Path(__file__).parent / fetch_result["yaml_path"])
    identity = fetch_result["identity"]
    financials = fetch_result["financials"]

    # Step 2: AI 분석
    print(f"\n{'='*60}")
    print(f"[AI 분석 시작] {identity.name}")
    print(f"{'='*60}")

    try:
        from ai.analyst import AIAnalyst
        analyst = AIAnalyst()
    except Exception as e:
        print(f"[WARN] AI 모듈 로드 실패 ({e}). Draft YAML로 진행합니다.")
        vi = load_profile(yaml_path)
        result = run_valuation(vi)
        print_report(vi, result)
        from output.excel_builder import export
        path = export(vi, result, output_dir)
        print(f"\n[Excel] 저장 완료: {path}")
        return result

    latest = max(financials.keys())
    cons = financials[latest]

    # 매출 구성 텍스트
    revenue_text = f"총 매출: {cons.get('revenue', 0):,}, 영업이익: {cons.get('op', 0):,}"

    # AI Step 2: 부문 분류
    print("[AI 2/5] 부문 분류 중...")
    try:
        seg_result = analyst.classify_segments(identity.name, revenue_text)
        segments = seg_result.get("segments", [])
        print(f"  → {len(segments)}개 부문 식별")
    except Exception as e:
        print(f"  [WARN] 부문 분류 실패: {e}")
        segments = []

    # AI Step 3: Peer/멀티플 추천
    peers_all = []
    multiples_ai = {}
    if segments:
        print("[AI 3/5] Peer 기업 추천 중...")
        for seg in segments:
            code = seg.get("code", "MAIN")
            name = seg.get("name", "Main")
            try:
                peer_result = analyst.recommend_peers(
                    identity.name, code, name,
                    seg.get("peer_group", ""),
                )
                for p in peer_result.get("peers", []):
                    peers_all.append({
                        "name": p["name"],
                        "segment_code": code,
                        "ev_ebitda": p.get("ev_ebitda", 10.0),
                        "notes": p.get("notes", ""),
                    })
                multiples_ai[code] = peer_result.get("recommended_multiple", 10.0)
                print(f"  → {code}: {peer_result.get('recommended_multiple', '?')}x "
                      f"({len(peer_result.get('peers', []))} peers)")
            except Exception as e:
                print(f"  [WARN] {code} Peer 추천 실패: {e}")
                multiples_ai[code] = 10.0

    # AI Step 4: WACC 추천
    print("[AI 4/5] WACC 추정 중...")
    equity = cons.get("equity", 0)
    liabilities = cons.get("liabilities", 0)
    de_ratio = round(liabilities / equity * 100, 1) if equity > 0 else 100.0
    try:
        wacc_result = analyst.suggest_wacc(identity.name, de_ratio, "")
        print(f"  → WACC ≈ {wacc_result.get('wacc_estimate', '?')}%")
    except Exception as e:
        print(f"  [WARN] WACC 추정 실패: {e}")
        wacc_result = {}

    # AI Step 5: 시나리오 설계
    print("[AI 5/5] 시나리오 설계 중...")
    legal = "상장" if identity.market == "US" else "비상장"
    try:
        sc_result = analyst.design_scenarios(identity.name, legal, "")
        ai_scenarios = sc_result.get("scenarios", [])
        print(f"  → {len(ai_scenarios)}개 시나리오")
    except Exception as e:
        print(f"  [WARN] 시나리오 설계 실패: {e}")
        ai_scenarios = []

    # Step 3: YAML 보강
    print(f"\n[YAML 보강 중] {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # 부문 정보 업데이트
    if segments:
        raw["segments"] = {}
        seg_data_update = {}
        for seg in segments:
            code = seg.get("code", "MAIN")
            raw["segments"][code] = {
                "name": seg.get("name", code),
                "multiple": multiples_ai.get(code, 10.0),
            }
            # segment_data: 단일 부문으로 총합 배분 (비중 기반)
            share = seg.get("revenue_share_pct", 100.0 / len(segments)) / 100
            seg_data_update[code] = {
                "revenue": round(cons.get("revenue", 0) * share),
                "gross_profit": 0,
                "op": round(cons.get("op", 0) * share),
                "assets": round(cons.get("assets", 0) * share),
            }
        raw["segment_data"] = {latest: seg_data_update}

    # WACC 업데이트
    if wacc_result:
        for key in ["rf", "erp", "bu", "kd_pre", "tax"]:
            if key in wacc_result:
                raw["wacc_params"][key] = wacc_result[key]

    # 시나리오 업데이트
    if ai_scenarios:
        shares = raw["company"]["shares_total"]
        raw["scenarios"] = {}
        for sc in ai_scenarios:
            code = sc.get("code", "A")
            raw["scenarios"][code] = {
                "name": sc.get("name", f"Scenario {code}"),
                "prob": sc.get("prob", 33),
                "ipo": "N/A",
                "irr": None,
                "dlom": sc.get("dlom", 0),
                "cps_repay": 0,
                "rcps_repay": 0,
                "buyback": 0,
                "shares": shares,
                "desc": sc.get("description", ""),
            }

    # Peers 업데이트
    if peers_all:
        raw["peers"] = peers_all

    # MC 활성화
    raw["mc_enabled"] = True

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(raw, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  → YAML 저장 완료")

    # Step 4: 밸류에이션 실행
    print(f"\n{'='*60}")
    print(f"[밸류에이션 실행]")
    print(f"{'='*60}")

    vi = load_profile(yaml_path)
    result = run_valuation(vi)
    print_report(vi, result)

    from output.excel_builder import export
    path = export(vi, result, output_dir)
    print(f"\n[Excel] 저장 완료: {path}")

    return result


def _fetch_and_compare_market_price(vi: ValuationInput, result: ValuationResult) -> ValuationResult:
    """상장 기업의 시장가격을 조회하고 괴리율을 계산."""
    is_listed = vi.company.legal_status in ("상장", "listed")
    if not is_listed or not vi.company.ticker or result.weighted_value <= 0:
        return result

    try:
        if vi.company.market == "US":
            from pipeline.yahoo_finance import get_stock_info
            info = get_stock_info(vi.company.ticker)
            price = info.get("price", 0)
        else:
            from pipeline.market_data import get_krx_price
            price = get_krx_price(vi.company.ticker)
    except Exception:
        price = 0

    if price and price > 0:
        mc = compare_to_market(result.weighted_value, price)
        result.market_comparison = MarketComparisonResult(
            intrinsic_value=mc.intrinsic_value,
            market_price=mc.market_price,
            gap_ratio=mc.gap_ratio,
            flag=mc.flag,
        )

    return result


def main():
    parser = argparse.ArgumentParser(description="범용 기업가치 분석 도구")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", "-p", help="YAML 프로필 경로")
    group.add_argument("--company", "-c", help="기업명/ticker (자동 데이터 수집)")
    group.add_argument("--discover", "-d", action="store_true",
                       help="뉴스 기반 기업 추천 (AI Discovery 모드)")
    parser.add_argument("--auto", action="store_true", help="AI 자동 분석 (--company와 함께 사용)")
    parser.add_argument("--excel", action="store_true", help="Excel 내보내기")
    parser.add_argument("--output-dir", "-o", default=None, help="Excel 출력 디렉토리")
    parser.add_argument("--market", default="KR", choices=["KR", "US"],
                        help="Discovery 모드 시장 선택 (기본: KR)")
    args = parser.parse_args()

    # Discovery 모드
    if args.discover:
        from discovery.discovery_engine import DiscoveryEngine
        engine = DiscoveryEngine()
        return engine.discover(market=args.market)

    # 자동 수집 모드
    if args.company:
        if args.auto:
            return auto_analyze(args.company, args.output_dir)
        return auto_fetch(args.company)

    # 프로필 기반 밸류에이션 모드
    vi = load_profile(args.profile)
    result = run_valuation(vi)

    # 상장사 시장가격 비교
    result = _fetch_and_compare_market_price(vi, result)

    print_report(vi, result)

    if args.excel:
        from output.excel_builder import export
        path = export(vi, result, args.output_dir)
        print(f"\n[Excel] 저장 완료: {path}")

    return result


if __name__ == "__main__":
    main()
