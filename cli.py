"""General-purpose corporate valuation CLI.

Usage:
    python cli.py --profile profiles/sk_ecoplant.yaml
    python cli.py --company "AAPL"
    python cli.py --company "삼성E&A" --auto
    python cli.py --discover --market KR
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
import _ssl_fix  # noqa: F401, E402 — must run before any yfinance/curl_cffi import

# Prevent Unicode output corruption on Windows cp949 console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from schemas.models import ValuationInput, ValuationResult, MarketComparisonResult
from engine.market_comparison import compare_to_market
from valuation_runner import enrich_market_dependent_result, load_profile, run_valuation
from orchestrator import _save_to_db
from output.console_report import print_report

logger = logging.getLogger(__name__)


def _fetch_live_market_price(vi: ValuationInput) -> float:
    """Fetch a current quote without deciding whether it should be used."""
    price = 0
    # Primary: yfinance_fetcher (leverages existing _ticker_info_cache)
    try:
        from pipeline.yfinance_fetcher import fetch_market_data

        md = fetch_market_data(vi.company.ticker, vi.company.market)
        if md:
            price = md.get("price", 0)
    except Exception as e:
        logger.debug("yfinance_fetcher 조회 실패 (%s): %s", vi.company.ticker, e)

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

    return float(price or 0)


def _format_price(price: float, market: str) -> str:
    if market == "KR":
        return f"{price:,.0f}원"
    return f"${price:,.2f}"


def _fetch_and_compare_market_price(
    vi: ValuationInput,
    result: ValuationResult,
    use_live_price: bool = False,
) -> ValuationResult:
    """Select an as-of profile price by default and calculate the market gap."""
    import math

    is_listed = vi.company.legal_status in ("상장", "listed")
    if not is_listed or not vi.company.ticker or result.weighted_value <= 0:
        return result

    profile_price = float(vi.market_price or 0)
    if not math.isfinite(profile_price) or profile_price <= 0:
        profile_price = 0
    live_price = _fetch_live_market_price(vi)
    if not math.isfinite(live_price) or live_price <= 0:
        live_price = 0

    explicit_as_of = bool(vi.price_as_of and profile_price)
    if vi.price_as_of and not profile_price:
        logger.warning(
            "price_as_of=%s가 선언됐지만 유효한 market_price가 없습니다 — "
            "실시간 가격을 사용합니다",
            vi.price_as_of,
        )

    if use_live_price and live_price:
        price = live_price
        price_source = "live"
        price_as_of = date.today()
    elif explicit_as_of:
        price = profile_price
        price_source = "profile_as_of"
        price_as_of = vi.price_as_of
    elif live_price:
        price = live_price
        price_source = "live"
        price_as_of = date.today()
    else:
        price = profile_price
        price_source = "profile_snapshot" if profile_price else ""
        price_as_of = None

    if profile_price and live_price and not math.isclose(profile_price, live_price):
        profile_text = _format_price(profile_price, vi.company.market)
        live_text = _format_price(live_price, vi.company.market)
        if price_source == "profile_as_of":
            logger.warning(
                "as-of %s 사용 (analysis_date %s) — 실시간 %s은 무시됨. "
                "실시간을 쓰려면 --live-price",
                profile_text,
                vi.company.analysis_date,
                live_text,
            )
        elif use_live_price and explicit_as_of:
            logger.warning(
                "--live-price: 실시간 %s 사용 — as-of %s "
                "(analysis_date %s)는 무시됨",
                live_text,
                profile_text,
                vi.price_as_of,
            )
        elif not explicit_as_of:
            logger.warning(
                "자동수집 스냅샷 %s vs 실시간 %s — 실시간 가격을 사용합니다. "
                "as-of 고정을 원하면 price_as_of 선언",
                profile_text,
                live_text,
            )
    elif use_live_price and profile_price and not live_price:
        fallback_label = "as-of" if explicit_as_of else "자동 스냅샷"
        logger.warning(
            "실시간 가격 조회 실패 — 프로필 %s 가격을 사용합니다", fallback_label
        )

    if price_source == "profile_as_of" and price_as_of:
        age_days = (date.today() - price_as_of).days
        if age_days >= 7:
            divergence = ""
            if live_price:
                gap_pct = abs(profile_price - live_price) / profile_price * 100
                divergence = f" 실시간 대비 {gap_pct:.1f}% 차이."
            logger.warning(
                "as-of %s 가격(%s) 사용 — 실행일 대비 %d일 경과.%s "
                "최신 시장 비교는 --live-price",
                price_as_of,
                _format_price(profile_price, vi.company.market),
                age_days,
                divergence,
            )

    # Sanity check: reject invalid price values
    if price > 0:
        mc = compare_to_market(result.weighted_value, price)
        result.market_comparison = MarketComparisonResult(
            intrinsic_value=mc.intrinsic_value,
            market_price=mc.market_price,
            price_source=price_source,
            price_as_of=price_as_of,
            gap_ratio=mc.gap_ratio,
            flag=mc.flag,
        )

        result = enrich_market_dependent_result(vi, result)

    return result


def main():
    parser = argparse.ArgumentParser(description="범용 기업가치 분석 도구")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--profile", "-p", help="YAML 프로필 경로")
    group.add_argument("--company", "-c", help="기업명/ticker (자동 데이터 수집)")
    group.add_argument(
        "--discover",
        "-d",
        action="store_true",
        help="뉴스 기반 기업 추천 (AI Discovery 모드)",
    )
    group.add_argument(
        "--weekly", "-w", action="store_true", help="주간 자동 뉴스 수집 + 밸류에이션"
    )
    group.add_argument(
        "--backtest", action="store_true", help="캘리브레이션 백테스트 리포트"
    )
    parser.add_argument(
        "--auto", action="store_true", help="AI 자동 분석 (--company와 함께 사용)"
    )
    parser.add_argument("--excel", action="store_true", help="Excel 내보내기")
    parser.add_argument(
        "--band",
        action="store_true",
        help="역사적 LTM P/B·P/S 밴드 출력 (1단계: 파일럿 3사 스냅샷, --profile 전용, 참고용)",
    )
    parser.add_argument(
        "--live-price",
        action="store_true",
        help="프로필의 as-of 가격 대신 실시간 가격을 우선 사용",
    )
    parser.add_argument("--json", action="store_true", help="Emit ValuationResult JSON")
    parser.add_argument("--output-dir", "-o", default=None, help="Excel 출력 디렉토리")
    parser.add_argument(
        "--market",
        default="KR",
        choices=["KR", "US", "JP"],
        help="Discovery 모드 시장 선택 (기본: KR)",
    )
    parser.add_argument(
        "--markets",
        default="KR,US",
        help="Weekly mode: target markets (comma-separated, default: KR,US)",
    )
    parser.add_argument(
        "--max-per-market",
        type=int,
        default=5,
        help="Weekly mode: max companies per market (default: 5)",
    )
    parser.add_argument(
        "--max-companies",
        type=int,
        default=None,
        help="(deprecated: use --max-per-market)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Weekly mode: discovery only, skip valuation",
    )
    parser.add_argument(
        "--backtest-min-age",
        type=int,
        default=90,
        help="Backtest: 최소 밸류에이션 경과일 (기본: 90)",
    )
    args = parser.parse_args()

    # Backtest mode
    if args.backtest:
        from backtest.dataset import build_backtest_dataset
        from backtest.report import generate_report

        records = build_backtest_dataset(min_age_days=args.backtest_min_age)
        text, _ = generate_report(records)
        print(text)
        return

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

        if args.band:
            print("[band] --band는 1단계에서 --profile 경로 전용입니다 — 생략.")
        if args.auto:
            return auto_analyze(args.company, args.output_dir)
        market_hint = args.market if args.market != "KR" else None
        return auto_fetch(args.company, market_hint=market_hint)

    # Profile-based valuation mode
    profile_path = Path(args.profile).resolve()
    profiles_dir = (Path(__file__).parent / "profiles").resolve()
    if not profile_path.is_relative_to(profiles_dir):
        parser.error(f"프로필은 profiles/ 디렉토리 내부만 허용됩니다: {args.profile}")
    vi = load_profile(str(profile_path))
    result = run_valuation(vi)

    # Listed company market price comparison
    result = _fetch_and_compare_market_price(
        vi, result, use_live_price=args.live_price
    )

    # Recompute quality score now that market_comparison is attached
    # (run_valuation computes quality before market price is available)
    if result.market_comparison and result.market_comparison.market_price > 0:
        from engine.quality import calc_quality_score
        from valuation_runner import _apply_investability_gate

        result.quality = calc_quality_score(vi, result)
        result = _apply_investability_gate(vi, result)

    if args.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return result

    print_report(vi, result)

    # Historical band (--band, reporting-only — not a valuation input)
    bands = None
    band_current = None
    if args.band:
        from pipeline.timeseries import build_band_reports

        bands = build_band_reports(
            company_name=vi.company.name, ticker=vi.company.ticker
        )
        if bands:
            rv = result.relative_valuation
            band_current = {
                m.name: m.value
                for m in (rv.ratios if rv else [])
                if m.name in ("P/B", "P/S") and m.value is not None
            }
            from output.band_report import print_band_reports

            print_band_reports(bands, band_current)

    # Save to DB (when Supabase is configured)
    val_id = _save_to_db(vi, result, args.profile)
    if val_id:
        print(f"\n[DB] Supabase 저장 완료: {val_id}")

    if args.excel:
        from output.excel_builder import export

        path = export(
            vi, result, args.output_dir,
            band_reports=bands, band_current=band_current,
        )
        print(f"\n[Excel] 저장 완료: {path}")

    return result


if __name__ == "__main__":
    main()
