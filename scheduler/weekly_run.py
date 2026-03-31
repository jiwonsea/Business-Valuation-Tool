"""주간 자동 뉴스 수집 + 밸류에이션 파이프라인.

Usage:
    python -m scheduler.weekly_run                               # KR+US, 3개
    python -m scheduler.weekly_run --markets KR,US --max-companies 5
    python -m scheduler.weekly_run --dry-run                     # 발굴만
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path

from .scoring import score_companies

_RESULTS_BASE = Path(
    os.environ.get("VALUATION_RESULTS_DIR", r"G:\내 드라이브\포트폴리오\valuation-results")
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def _week_number(dt: datetime) -> int:
    """해당 월의 몇 째 주인지 계산."""
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
    """주간 Discovery + 밸류에이션 파이프라인 실행.

    1. 시장별 뉴스 수집 + AI 분석 (DiscoveryEngine)
    2. 기업 중요도 스코어링 (뉴스 빈도 + 시가총액)
    3. 상위 N개 기업 자동 밸류에이션 (auto_analyze)
    4. DB 저장

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

    # DB에 실행 기록 생성
    run_id = _save_run_start(markets)

    # ── Phase 1: 시장별 뉴스 수집 + AI 분석 ──
    engine = DiscoveryEngine()
    all_companies: list[dict] = []
    all_news: list[dict] = []
    total_news = 0

    for market in markets:
        try:
            result = engine.discover(market=market)
            news_count = result.get("news_count", 0)
            total_news += news_count
            for co in result.get("companies", []):
                co["market"] = market
                all_companies.append(co)
            summary["discoveries"].append({
                "market": market,
                "news_count": news_count,
                "companies": result.get("companies", []),
            })
            # 뉴스 원문은 scoring에 필요 — DiscoveryEngine 내부에서 수집한 뉴스 재활용
            # discover()는 뉴스 원문을 반환하지 않으므로 제목 기반 스코어링용으로 companies의 reason 활용
        except Exception as e:
            logger.error("Discovery 실패 [%s]: %s", market, e)
            summary["errors"].append({
                "phase": "discovery", "market": market, "error": str(e),
            })

    # ── Phase 2: 중복 제거 + 중요도 스코어링 ──
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

    # ── 결과 출력 ──
    _print_summary_header(summary["label"], total_news, scored)

    if dry_run:
        logger.info("Dry run — 밸류에이션 건너뜀.")
        _finalize_run(run_id, summary, time.time() - start, total_news, scored)
        return summary

    # ── Phase 3: 상위 기업 자동 밸류에이션 ──
    from pipeline.profile_generator import auto_analyze

    # 주차별 출력 폴더: valuation-results/2026-03-5째주/
    week_dir = _RESULTS_BASE / f"{now.year}-{now.month:02d}-{_week_number(now)}째주"
    week_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Excel 출력 폴더: %s", week_dir)

    for co in targets:
        name = co.get("name", "")
        try:
            logger.info("밸류에이션 시작: %s %s", co.get("stars", ""), name)
            result = auto_analyze(name, output_dir=str(week_dir))
            status = "success" if result else "no_result"
            summary["valuations"].append({"company": name, "status": status})
        except Exception as e:
            logger.error("밸류에이션 실패 [%s]: %s", name, e)
            summary["errors"].append({
                "phase": "valuation", "company": name, "error": str(e),
            })
            summary["valuations"].append({
                "company": name, "status": "failed", "error": str(e),
            })

    # ── Phase 4: 완료 ──
    duration = time.time() - start
    _finalize_run(run_id, summary, duration, total_news, scored)
    _print_completion(summary, duration, week_dir)

    return summary


def _print_summary_header(
    label: str,
    total_news: int,
    scored: list[dict],
) -> None:
    """주간 분석 결과 헤더 출력."""
    print(f"\n{'═' * 50}")
    print(f"[주간 자동 분석] {label}")
    print(f"{'═' * 50}")
    print(f"  뉴스 수집: {total_news}건\n")

    if scored:
        print("  [발굴 기업 — 중요도 순]")
        for co in scored:
            stars = co.get("stars", "★☆☆☆☆")
            name = co.get("name", "")
            reason = co.get("reason", "")
            news_cnt = co.get("news_count", 0)
            print(f"  {stars} {name} — {reason} (뉴스 {news_cnt}건)")
    else:
        print("  발굴된 기업이 없습니다.")
    print()


def _print_completion(summary: dict, duration: float, output_dir: Path | None = None) -> None:
    """완료 메시지 출력."""
    success = sum(1 for v in summary["valuations"] if v["status"] == "success")
    total = len(summary["valuations"])
    errors = len(summary["errors"])

    print(f"\n{'═' * 50}")
    print(f"[완료] {summary['label']}")
    print(f"  실행 시간: {duration:.0f}초")
    print(f"  밸류에이션: {success}/{total} 성공")
    if output_dir:
        print(f"  결과 폴더: {output_dir}")
    if errors:
        print(f"  오류: {errors}건")
    print(f"{'═' * 50}")


def _save_run_start(markets: list[str]) -> str | None:
    """DB에 실행 시작 기록."""
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
    """DB에 실행 완료 기록."""
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
