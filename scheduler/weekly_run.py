"""Weekly automated news collection + valuation pipeline.

Usage:
    python -m scheduler.weekly_run                               # KR+US, 3 companies
    python -m scheduler.weekly_run --markets KR,US --max-companies 5
    python -m scheduler.weekly_run --dry-run                     # Discovery only
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from .scoring import score_companies

_RESULTS_BASE = Path(
    os.environ.get(
        "VALUATION_RESULTS_DIR",
        Path(__file__).resolve().parent.parent / "valuation-results",
    )
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _week_number(dt: datetime) -> int:
    """Calculate which week of the month the date falls in."""
    first_day = dt.replace(day=1)
    return (dt.day + first_day.weekday()) // 7 + 1


def _week_label(dt: datetime) -> str:
    """'3월 5째주 (3/29)' 형식의 날짜 라벨."""
    return f"{dt.month}월 {_week_number(dt)}째주 ({dt.month}/{dt.day})"


def run_weekly(
    markets: list[str] | None = None,
    max_companies: int = 3,
    dry_run: bool = False,
) -> dict:
    """Execute weekly Discovery + valuation pipeline.

    1. Per-market news collection + AI analysis (DiscoveryEngine)
    2. Company importance scoring (news frequency + market cap)
    3. Auto-valuation for top N companies (auto_analyze)
    4. DB save

    Returns:
        {"run_date", "markets", "discoveries", "scored_companies", "valuations", "errors"}
    """
    from discovery.discovery_engine import DiscoveryEngine

    markets = markets or ["KR", "US"]
    start = time.time()
    now = datetime.now()

    summary: dict = {
        "run_date": now.isoformat(),
        "label": _week_label(now),
        "markets": markets,
        "discoveries": [],
        "scored_companies": [],
        "valuations": [],
        "errors": [],
    }

    # Create run record in DB
    run_id = _save_run_start(markets)

    # ── Phase 1: Per-market news collection + AI analysis (parallel) ──
    engine = DiscoveryEngine()
    all_companies: list[dict] = []
    all_news: list[dict] = []
    total_news = 0

    def _discover_market(market: str) -> tuple[str, dict | None, str | None]:
        try:
            return market, engine.discover(market=market), None
        except Exception as e:
            return market, None, str(e)

    with ThreadPoolExecutor(max_workers=len(markets)) as pool:
        futures = {pool.submit(_discover_market, m): m for m in markets}
        for fut in as_completed(futures):
            market, result, error = fut.result()
            if error:
                logger.error("Discovery 실패 [%s]: %s", market, error)
                summary["errors"].append({
                    "phase": "discovery", "market": market, "error": error,
                })
                continue
            news_count = result.get("news_count", 0)
            total_news += news_count
            market_news = result.get("news", [])
            all_news.extend(market_news)
            if not market_news:
                logger.warning("[%s] 뉴스 수집 결과 0건 — API 키/네트워크 확인 필요", market)
            for co in result.get("companies", []):
                co["market"] = market
                all_companies.append(co)
            summary["discoveries"].append({
                "market": market,
                "news_count": news_count,
                "companies": result.get("companies", []),
            })

    # ── Phase 2: Deduplication + importance scoring ──
    seen_names: set[str] = set()
    unique_companies: list[dict] = []
    for co in all_companies:
        name = co.get("name", "")
        if name and name not in seen_names:
            seen_names.add(name)
            unique_companies.append(co)

    scored = score_companies(unique_companies, all_news)
    summary["scored_companies"] = scored

    targets = scored[:max_companies]

    # ── Print results ──
    _print_summary_header(summary["label"], total_news, scored)

    if dry_run:
        logger.info("Dry run — 밸류에이션 건너뜀.")
        _finalize_run(run_id, summary, time.time() - start, total_news, scored)
        return summary

    # ── Phase 3: Auto-valuation for top companies ──
    from pipeline.profile_generator import auto_analyze

    # Weekly output folder: valuation-results/2026-03-5째주/
    week_dir = _RESULTS_BASE / f"{now.year}-{now.month:02d}-{_week_number(now)}째주"
    week_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Excel 출력 폴더: %s", week_dir)

    def _run_valuation(co: dict) -> dict:
        name = co.get("name", "")
        try:
            logger.info("밸류에이션 시작: %s %s", co.get("stars", ""), name)
            result = auto_analyze(name, output_dir=str(week_dir))
            status = "success" if result else "no_result"
            return {"company": name, "status": status}
        except Exception as e:
            logger.error("밸류에이션 실패 [%s]: %s", name, e)
            return {"company": name, "status": "failed", "error": str(e)}

    if not targets:
        logger.warning("밸류에이션 대상 기업이 없습니다.")
    with ThreadPoolExecutor(max_workers=max(min(len(targets), 3), 1)) as pool:
        futures = {pool.submit(_run_valuation, co): co for co in targets}
        for fut in as_completed(futures):
            entry = fut.result()
            summary["valuations"].append(entry)
            if entry.get("status") == "failed":
                summary["errors"].append({
                    "phase": "valuation",
                    "company": entry["company"],
                    "error": entry.get("error", ""),
                })

    # ── Phase 4: Completion ──
    duration = time.time() - start
    _finalize_run(run_id, summary, duration, total_news, scored)
    _print_completion(summary, duration, week_dir)

    return summary


def _print_summary_header(
    label: str,
    total_news: int,
    scored: list[dict],
) -> None:
    """Print weekly analysis result header."""
    print(f"\n{'=' * 50}")
    print(f"[주간 자동 분석] {label}")
    print(f"{'=' * 50}")
    print(f"  뉴스 수집: {total_news}건\n")

    if scored:
        print("  [발굴 기업 - 중요도 순]")
        for co in scored:
            stars = co.get("stars", "★☆☆☆☆")
            name = co.get("name", "")
            reason = co.get("reason", "")
            news_cnt = co.get("news_count", 0)
            print(f"  {stars} {name} - {reason} (뉴스 {news_cnt}건)")
    else:
        print("  발굴된 기업이 없습니다.")
    print()


def _print_completion(summary: dict, duration: float, output_dir: Path | None = None) -> None:
    """Print completion message."""
    success = sum(1 for v in summary["valuations"] if v["status"] == "success")
    total = len(summary["valuations"])
    errors = len(summary["errors"])

    print(f"\n{'=' * 50}")
    print(f"[완료] {summary['label']}")
    print(f"  실행 시간: {duration:.0f}초")
    print(f"  밸류에이션: {success}/{total} 성공")
    if output_dir:
        print(f"  결과 폴더: {output_dir}")
    if errors:
        print(f"  오류: {errors}건")
    print(f"{'=' * 50}")


def _save_run_start(markets: list[str]) -> str | None:
    """Record run start in DB."""
    try:
        from db.repository import save_discovery_run
        return save_discovery_run({
            "markets": markets,
            "status": "running",
        })
    except Exception as e:
        logger.debug("DB 기록 실패 (시작): %s", e)
        return None


def _finalize_run(
    run_id: str | None,
    summary: dict,
    duration: float,
    total_news: int,
    scored: list[dict],
) -> None:
    """Record run completion in DB."""
    if not run_id:
        return
    try:
        from db.repository import update_discovery_run

        status = "completed" if not summary["errors"] else "completed_with_errors"
        update_discovery_run(run_id, {
            "status": status,
            "news_count": total_news,
            "companies_discovered": scored,
            "companies_analyzed": [
                v["company"] for v in summary["valuations"]
            ],
            "errors": summary["errors"],
            "duration_seconds": round(duration, 1),
        })
    except Exception as e:
        logger.debug("DB 기록 실패 (완료): %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="주간 자동 뉴스 수집 + 밸류에이션",
    )
    parser.add_argument(
        "--markets", default="KR,US",
        help="대상 시장 (콤마 구분, 기본: KR,US)",
    )
    parser.add_argument(
        "--max-companies", type=int, default=3,
        help="밸류에이션 최대 기업 수 (기본: 3)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="발굴만 수행, 밸류에이션 미실행",
    )
    args = parser.parse_args()

    run_weekly(
        markets=args.markets.split(","),
        max_companies=args.max_companies,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
