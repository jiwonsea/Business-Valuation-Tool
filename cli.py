"""범용 기업가치 분석 CLI.

Usage:
    python cli.py --profile profiles/sk_ecoplant.yaml
    python cli.py --company "AAPL"
    python cli.py --company "삼성E&A" --auto
    python cli.py --discover --market KR
"""

import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from schemas.models import ValuationInput, ValuationResult, MarketComparisonResult
from engine.market_comparison import compare_to_market
from valuation_runner import load_profile, run_valuation
from output.console_report import print_report


def _fetch_and_compare_market_price(vi: ValuationInput, result: ValuationResult) -> ValuationResult:
    """상장 기업의 시장가격을 조회하고 괴리율을 계산."""
    is_listed = vi.company.legal_status in ("상장", "listed")
    if not is_listed or not vi.company.ticker or result.weighted_value <= 0:
        return result

    price = 0
    try:
        from pipeline.yahoo_finance import get_stock_info
        ticker = vi.company.ticker
        if vi.company.market == "KR":
            ticker = f"{ticker}.KS"
        info = get_stock_info(ticker)
        if info:
            price = info.get("price", 0)
    except Exception:
        pass

    # Yahoo 실패 시 KRX fallback (KR only)
    if not price and vi.company.market == "KR":
        try:
            from pipeline.market_data import get_krx_market_cap
            data = get_krx_market_cap(vi.company.ticker)
            if data:
                price = data.get("price", 0)
        except Exception:
            pass

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
        from pipeline.profile_generator import auto_fetch, auto_analyze
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
