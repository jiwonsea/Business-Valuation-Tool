"""General-purpose corporate valuation CLI.

Usage:
    python cli.py --profile profiles/sk_ecoplant.yaml
    python cli.py --company "AAPL"
    python cli.py --company "삼성E&A" --auto
    python cli.py --discover --market KR
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Prevent Unicode output corruption on Windows cp949 console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from schemas.models import ValuationInput, ValuationResult, MarketComparisonResult
from engine.market_comparison import compare_to_market
from valuation_runner import load_profile, run_valuation
from orchestrator import _save_to_db
from output.console_report import print_report

logger = logging.getLogger(__name__)


def _fetch_and_compare_market_price(vi: ValuationInput, result: ValuationResult) -> ValuationResult:
    """Fetch market price for listed companies and calculate the gap ratio."""
    is_listed = vi.company.legal_status in ("상장", "listed")
    if not is_listed or not vi.company.ticker or result.weighted_value <= 0:
        return result

    import math

    price = 0
    # Primary: yfinance_fetcher (leverages existing _ticker_info_cache)
    try:
        from pipeline.yfinance_fetcher import fetch_market_data
        md = fetch_market_data(vi.company.ticker, vi.company.market)
        if md:
            price = md.get("price", 0)
    except Exception:
        pass

    # Fallback: yahoo_finance REST
    if not price:
        try:
            from pipeline.yahoo_finance import get_stock_info
            ticker = vi.company.ticker
            if vi.company.market == "KR" and not ticker.endswith((".KS", ".KQ")):
                try:
                    from pipeline.yfinance_fetcher import resolve_kr_ticker
                    ticker = resolve_kr_ticker(ticker)
                except (ImportError, Exception):
                    ticker = f"{ticker}.KS"
            info = get_stock_info(ticker)
            if info:
                price = info.get("price", 0)
        except Exception as e:
            logger.debug("Yahoo Finance 조회 실패 (%s): %s", vi.company.ticker, e)

    # KRX fallback on Yahoo failure (KR only)
    if not price and vi.company.market == "KR":
        try:
            from pipeline.market_data import get_krx_market_cap
            data = get_krx_market_cap(vi.company.ticker)
            if data:
                price = data.get("price", 0)
        except Exception as e:
            logger.debug("KRX fallback 실패 (%s): %s", vi.company.ticker, e)

    # Sanity check: reject invalid price values
    if price and not math.isnan(price) and price > 0:
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
                        help="Weekly mode: target markets (comma-separated, default: KR,US)")
    parser.add_argument("--max-per-market", type=int, default=5,
                        help="Weekly mode: max companies per market (default: 5)")
    parser.add_argument("--max-companies", type=int, default=None,
                        help="(deprecated: use --max-per-market)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Weekly mode: discovery only, skip valuation")
    args = parser.parse_args()

    # Discovery mode
    if args.discover:
        from discovery.discovery_engine import DiscoveryEngine
        engine = DiscoveryEngine()
        return engine.discover(market=args.market)

    # Weekly auto-analysis mode
    if args.weekly:
        from scheduler.weekly_run import run_weekly
        max_val = args.max_per_market
        if args.max_companies is not None:
            max_val = args.max_companies
        return run_weekly(
            markets=args.markets.split(","),
            max_per_market=max_val,
            dry_run=args.dry_run,
        )

    # Auto-fetch mode
    if args.company:
        from pipeline.profile_generator import auto_fetch, auto_analyze
        if args.auto:
            return auto_analyze(args.company, args.output_dir)
        return auto_fetch(args.company)

    # Profile-based valuation mode
    profile_path = Path(args.profile).resolve()
    profiles_dir = (Path(__file__).parent / "profiles").resolve()
    if not profile_path.is_relative_to(profiles_dir):
        parser.error(f"프로필은 profiles/ 디렉토리 내부만 허용됩니다: {args.profile}")
    vi = load_profile(str(profile_path))
    result = run_valuation(vi)

    # Listed company market price comparison
    result = _fetch_and_compare_market_price(vi, result)

    print_report(vi, result)

    # Save to DB (when Supabase is configured)
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
