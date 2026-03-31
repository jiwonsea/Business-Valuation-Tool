"""범용 기업가치 분석 CLI.

Usage:
    python cli.py --profile profiles/sk_ecoplant.yaml
    python cli.py --company "AAPL"
    python cli.py --company "삼성E&A" --auto
    python cli.py --discover --market KR
"""

import argparse
import logging
from pathlib import Path

from schemas.models import ValuationInput, ValuationResult, MarketComparisonResult
from engine.market_comparison import compare_to_market
from valuation_runner import load_profile, run_valuation
from orchestrator import _save_to_db
from output.console_report import print_report

logger = logging.getLogger(__name__)


def _fetch_and_compare_market_price(vi: ValuationInput, result: ValuationResult) -> ValuationResult:
    """상장 기업의 시장가격을 조회하고 괴리율을 계산."""
    is_listed = vi.company.legal_status in ("상장", "listed")
    if not is_listed or not vi.company.ticker or result.weighted_value <= 0:
        return result

    price = 0
    try:
        from pipeline.yahoo_finance import get_stock_info
        ticker = vi.company.ticker
        if vi.company.market == "KR" and not ticker.endswith((".KS", ".KQ")):
            ticker = f"{ticker}.KS"
        info = get_stock_info(ticker)
        if info:
            price = info.get("price", 0)
    except Exception as e:
        logger.debug("Yahoo Finance 조회 실패 (%s): %s", vi.company.ticker, e)

    # Yahoo 실패 시 KRX fallback (KR only)
    if not price and vi.company.market == "KR":
        try:
            from pipeline.market_data import get_krx_market_cap
            data = get_krx_market_cap(vi.company.ticker)
            if data:
                price = data.get("price", 0)
        except Exception as e:
            logger.debug("KRX fallback 실패 (%s): %s", vi.company.ticker, e)

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
    group.add_argument("--weekly", "-w", action="store_true",
                       help="주간 자동 뉴스 수집 + 밸류에이션")
    parser.add_argument("--auto", action="store_true", help="AI 자동 분석 (--company와 함께 사용)")
    parser.add_argument("--excel", action="store_true", help="Excel 내보내기")
    parser.add_argument("--output-dir", "-o", default=None, help="Excel 출력 디렉토리")
    parser.add_argument("--market", default="KR", choices=["KR", "US"],
                        help="Discovery 모드 시장 선택 (기본: KR)")
    parser.add_argument("--markets", default="KR,US",
                        help="주간 모드 시장 선택 (콤마 구분, 기본: KR,US)")
    parser.add_argument("--max-companies", type=int, default=3,
                        help="주간 모드 최대 분석 기업 수 (기본: 3)")
    parser.add_argument("--dry-run", action="store_true",
                        help="주간 모드: 발굴만 수행, 밸류에이션 미실행")
    args = parser.parse_args()

    # Discovery 모드
    if args.discover:
        from discovery.discovery_engine import DiscoveryEngine
        engine = DiscoveryEngine()
        return engine.discover(market=args.market)

    # 주간 자동 분석 모드
    if args.weekly:
        from scheduler.weekly_run import run_weekly
        return run_weekly(
            markets=args.markets.split(","),
            max_companies=args.max_companies,
            dry_run=args.dry_run,
        )

    # 자동 수집 모드
    if args.company:
        from pipeline.profile_generator import auto_fetch, auto_analyze
        if args.auto:
            return auto_analyze(args.company, args.output_dir)
        return auto_fetch(args.company)

    # 프로필 기반 밸류에이션 모드
    profile_path = Path(args.profile).resolve()
    profiles_dir = (Path(__file__).parent / "profiles").resolve()
    if not profile_path.is_relative_to(profiles_dir):
        parser.error(f"프로필은 profiles/ 디렉토리 내부만 허용됩니다: {args.profile}")
    vi = load_profile(str(profile_path))
    result = run_valuation(vi)

    # 상장사 시장가격 비교
    result = _fetch_and_compare_market_price(vi, result)

    print_report(vi, result)

    # DB 저장 (Supabase 설정 시)
    val_id = _save_to_db(vi, result, args.profile)
    if val_id:
        print(f"\n[DB] Supabase 저장 완료: {val_id}")

    if args.excel:
        from output.excel_builder import export
        path = export(vi, result, args.output_dir)
        print(f"\n[Excel] 저장 완료: {path}")

    return result


if __name__ == "__main__":
    main()
