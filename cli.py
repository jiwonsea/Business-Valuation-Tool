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
    ValuationInput, ValuationResult,
)
from engine.wacc import calc_wacc
from engine.sotp import allocate_da, calc_sotp
from engine.dcf import calc_dcf
from engine.scenario import calc_scenario
from engine.sensitivity import sensitivity_multiples, sensitivity_irr_dlom, sensitivity_dcf


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

    return ValuationInput(
        company=company,
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
    )


def run_valuation(vi: ValuationInput) -> ValuationResult:
    """전체 밸류에이션 파이프라인 실행."""
    by = vi.base_year
    cons = vi.consolidated[by]

    # 1. WACC
    wacc_result = calc_wacc(vi.wacc_params)

    # 2. D&A 배분 (전 연도)
    da_allocations = {}
    for yr, segs in vi.segment_data.items():
        c = vi.consolidated[yr]
        total_da = c["dep"] + c["amort"]
        da_allocations[yr] = allocate_da(segs, total_da)

    # 3. SOTP (base year)
    base_alloc = da_allocations[by]
    sotp, total_ev = calc_sotp(base_alloc, vi.multiples)

    # 4. 시나리오
    scenario_results = {}
    total_weighted = 0
    for code, sc in vi.scenarios.items():
        r = calc_scenario(sc, total_ev, vi.net_debt, vi.eco_frontier,
                          vi.cps_principal, vi.cps_years)
        scenario_results[code] = r
        total_weighted += r.weighted

    # 5. DCF 교차검증
    total_da_base = cons["dep"] + cons["amort"]
    ebitda_base = cons["op"] + total_da_base
    dcf_result = calc_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        wacc_result.wacc, vi.dcf_params, vi.base_year,
    )

    # 6. 민감도
    sens_mult, hi_range, alc_range = sensitivity_multiples(
        base_alloc, vi.multiples, vi.net_debt, vi.eco_frontier,
        vi.company.shares_total,
    )
    sens_irr, irr_range, dlom_range = sensitivity_irr_dlom(
        total_ev, vi.net_debt, vi.eco_frontier,
        vi.cps_principal, vi.cps_years,
        vi.scenarios["B"].rcps_repay if "B" in vi.scenarios else 0,
        vi.scenarios["B"].buyback if "B" in vi.scenarios else 0,
        vi.company.shares_ordinary,
    )
    sens_dcf_rows, wacc_range_dcf, tg_range_dcf = sensitivity_dcf(
        ebitda_base, total_da_base, cons["revenue"],
        vi.dcf_params, vi.base_year,
    )

    return ValuationResult(
        wacc=wacc_result,
        da_allocations={yr: {c: a for c, a in allocs.items()}
                        for yr, allocs in da_allocations.items()},
        sotp=sotp,
        total_ev=total_ev,
        scenarios=scenario_results,
        weighted_value=total_weighted,
        dcf=dcf_result,
        sensitivity_multiples=sens_mult,
        sensitivity_irr_dlom=sens_irr,
        sensitivity_dcf=sens_dcf_rows,
    )


def print_report(vi: ValuationInput, result: ValuationResult):
    """콘솔 출력."""
    by = vi.base_year
    seg_names = {code: info["name"] for code, info in vi.segments.items()}

    print("=" * 60)
    print(f"{vi.company.name} 기업가치평가 모델")
    print("=" * 60)

    # WACC
    w = result.wacc
    print(f"\n[WACC] βL={w.bl}, Ke={w.ke}%, Kd(세후)={w.kd_at}%, WACC={w.wacc}%")

    # D&A 배분
    total_da = vi.consolidated[by]["dep"] + vi.consolidated[by]["amort"]
    print(f"\n[D&A 배분] 총 D&A = {total_da:,}백만원")
    print(f"{'부문':<20} {'자산비중':>10} {'D&A':>12} {'EBITDA':>14}")
    print("-" * 60)
    alloc = result.da_allocations[by]
    for code in vi.segments:
        a = alloc[code]
        print(f"{seg_names[code]:<20} {a.asset_share:>9.2f}% {a.da_allocated:>11,} {a.ebitda:>13,}")

    # SOTP
    print(f"\n[SOTP EV] {result.total_ev:>14,}백만원 ({result.total_ev/100:,.0f}억원)")

    # 시나리오
    print(f"\n[시나리오 분석]")
    for code, sc in vi.scenarios.items():
        r = result.scenarios[code]
        print(f"  시나리오 {code} ({sc.name}, {sc.prob}%): "
              f"Equity={r.equity_value:>12,}백만원, "
              f"주당(DLOM후)={r.post_dlom:>8,}원, "
              f"가중기여={r.weighted:>6,}원")

    print(f"\n  >> 확률가중 주당 가치: {result.weighted_value:,}원")

    # DCF
    dcf = result.dcf
    print(f"\n[DCF 교차검증]")
    print(f"  DCF EV: {dcf.ev_dcf:>12,}백만원 ({dcf.ev_dcf/100:,.0f}억원)")
    print(f"  SOTP EV: {result.total_ev:>12,}백만원")
    diff_pct = (dcf.ev_dcf - result.total_ev) / result.total_ev * 100
    print(f"  DCF vs SOTP: {diff_pct:>+.1f}%")

    print("\n" + "=" * 60)
    print(f"완료! 확률가중 주당 가치: {result.weighted_value:,}원")
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

    # Summary
    print(f"\n{'='*60}")
    print(f"데이터 수집 완료: {identity.name}")
    print(f"시장: {identity.market} | 연도: {sorted(financials.keys())}")
    print(f"{'='*60}")
    print(f"\n[다음 단계]")
    print(f"  1. profiles/ 에 YAML 프로필을 생성하세요")
    print(f"  2. 부문 데이터, 멀티플, 시나리오를 수동 설정하세요")
    print(f"  3. python cli.py --profile profiles/<name>.yaml 으로 밸류에이션 실행")

    return {
        "identity": identity,
        "financials": financials,
        "shares": shares_info,
    }


def main():
    parser = argparse.ArgumentParser(description="범용 기업가치 분석 도구")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", "-p", help="YAML 프로필 경로")
    group.add_argument("--company", "-c", help="기업명/ticker (자동 데이터 수집)")
    parser.add_argument("--excel", action="store_true", help="Excel 내보내기")
    parser.add_argument("--output-dir", "-o", default=None, help="Excel 출력 디렉토리")
    args = parser.parse_args()

    # 자동 수집 모드
    if args.company:
        return auto_fetch(args.company)

    # 프로필 기반 밸류에이션 모드
    vi = load_profile(args.profile)
    result = run_valuation(vi)
    print_report(vi, result)

    if args.excel:
        from output.excel_builder import export
        path = export(vi, result, args.output_dir)
        print(f"\n[Excel] 저장 완료: {path}")

    return result


if __name__ == "__main__":
    main()
