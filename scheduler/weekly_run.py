"""Weekly automated news collection + valuation pipeline.

Usage:
    python -m scheduler.weekly_run                                # KR+US, 5 per market
    python -m scheduler.weekly_run --markets KR,US --max-per-market 3
    python -m scheduler.weekly_run --dry-run                      # Discovery only
"""

from __future__ import annotations
import _ssl_fix  # noqa: F401 — must run before any yfinance/curl_cffi import

import argparse
import calendar
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# Load .env so Task Scheduler (which doesn't inherit shell env) gets all API keys
try:
    from dotenv import load_dotenv

    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

from .scoring import score_companies

_RESULTS_BASE = Path(
    os.environ.get(
        "VALUATION_RESULTS_DIR",
        Path(__file__).resolve().parent.parent / "valuation-results",
    )
)

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            _LOG_DIR / f"weekly_{datetime.now().strftime('%Y%m%d')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def _alert(phase: str, error: str) -> None:
    """Send error alert via Gmail (best-effort)."""
    try:
        from .email_sender import send_error_alert

        send_error_alert(phase, error)
    except Exception:
        pass


def _week_number(dt: datetime) -> int:
    """Calculate which week of the month the date falls in."""
    first_day = dt.replace(day=1)
    return (dt.day + first_day.weekday()) // 7 + 1


def _ordinal(n: int) -> str:
    """Return ordinal string: 1st, 2nd, 3rd, 4th, 5th."""
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


def _week_folder(dt: datetime) -> str:
    """Folder name: '2026-03-31(Mar 5th week)' (local display)."""
    wn = _week_number(dt)
    mon = calendar.month_abbr[dt.month]
    return f"{dt.year}-{dt.month:02d}-{dt.day:02d}({mon} {_ordinal(wn)} week)"


def _storage_folder(week_folder_name: str) -> str:
    """Sanitize folder name for Supabase Storage keys.

    Supabase Storage rejects keys containing parentheses or spaces.
    '2026-03-31(Mar 5th week)' -> '2026-03-31_Mar-5th-week'
    """
    return week_folder_name.replace("(", "_").replace(")", "").replace(" ", "-")


def _week_label(dt: datetime) -> str:
    """Human-readable label: 'Mar 5th week (3/31)'."""
    wn = _week_number(dt)
    mon = calendar.month_abbr[dt.month]
    return f"{mon} {_ordinal(wn)} week ({dt.month}/{dt.day})"


def run_weekly(
    markets: list[str] | None = None,
    max_per_market: int = 5,
    dry_run: bool = False,
) -> dict:
    """Execute weekly Discovery + valuation pipeline.

    1. Per-market news collection + AI analysis (DiscoveryEngine)
    2. Company importance scoring (news frequency + market cap)
    3. Auto-valuation for top N per market (auto_analyze)
    4. Upload Excel to Supabase Storage
    5. Save JSON summary for downstream delivery (Gamma + Gmail)
    6. DB save

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
                summary["errors"].append(
                    {
                        "phase": "discovery",
                        "market": market,
                        "error": error,
                    }
                )
                continue
            news_count = result.get("news_count", 0)
            total_news += news_count
            market_news = result.get("news", [])
            all_news.extend(market_news)
            if not market_news:
                msg = f"[{market}] 뉴스 수집 결과 0건 — API 키/네트워크 확인 필요"
                logger.warning(msg)
                _alert("Discovery", msg)
            for co in result.get("companies", []):
                co["market"] = market
                all_companies.append(co)
            summary["discoveries"].append(
                {
                    "market": market,
                    "news_count": news_count,
                    "companies": result.get("companies", []),
                }
            )

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

    # ── Per-market selection: top N per market ──
    # Filter out sector/theme names (e.g. '반도체 관련주', '방위산업 관련 기업군')
    _SECTOR_KEYWORDS = (
        "관련주",
        "관련 기업",
        "관련기업",
        "기업군",
        "관련 종목",
        "관련종목",
        # English sector/group expressions (US market AI outputs)
        " sector",
        " companies",
        " firms",
        " industry",
    )

    def _is_real_company(co: dict) -> bool:
        name = co.get("name", "")
        return not any(kw in name for kw in _SECTOR_KEYWORDS)

    targets: list[dict] = []
    for market in markets:
        market_companies = [
            c for c in scored if c.get("market") == market and _is_real_company(c)
        ]
        actual = market_companies[:max_per_market]
        targets.extend(actual)
        if len(actual) < max_per_market:
            logger.info(
                "%s: %d/%d companies available (below target)",
                market,
                len(actual),
                max_per_market,
            )

    # ── Print results ──
    _print_summary_header(summary["label"], total_news, scored)

    if dry_run:
        logger.info("Dry run — skipping valuation.")
        _finalize_run(run_id, summary, time.time() - start, total_news, scored)
        return summary

    # ── Cost estimation before valuation ──
    from pipeline.api_guard import ApiGuard, estimate_weekly_cost

    estimate = estimate_weekly_cost(markets, len(targets))
    total_est = sum(estimate["estimated_api_calls"].values())
    logger.info(
        "Estimated API calls: %d, LLM calls: %d, LLM cost: $%.2f",
        total_est,
        estimate["estimated_llm_calls"],
        estimate["estimated_llm_cost_usd"],
    )
    low_quota = {
        k: v
        for k, v in estimate["remaining_quota"].items()
        if 0 <= v < estimate["estimated_api_calls"].get(k, 0)
    }
    if low_quota:
        logger.warning("Insufficient quota for: %s", low_quota)

    # ── Quota safety net: trim targets to fit LLM quota ──
    # If OpenRouter is active, sum both budgets (Anthropic is the fallback).
    # If Anthropic only, use its budget alone.
    if os.getenv("OPENROUTER_API_KEY"):
        # Only count Anthropic budget if the fallback key is actually configured
        anthropic_bonus = (
            estimate["remaining_quota"].get("anthropic", 0)
            if os.getenv("ANTHROPIC_API_KEY")
            else 0
        )
        llm_budget = estimate["remaining_quota"].get("openrouter", 0) + anthropic_bonus
    else:
        llm_budget = estimate["remaining_quota"].get("anthropic", 50)
    calls_per_company = (
        6  # classify + peers_batch + wacc + scenarios + news_summary + profile_gen
    )
    max_affordable = max(llm_budget // calls_per_company, 1)
    if len(targets) > max_affordable:
        logger.warning(
            "Trimming targets from %d to %d to fit LLM quota (%d remaining)",
            len(targets),
            max_affordable,
            llm_budget,
        )
        targets = targets[:max_affordable]

    # ── Phase 3: Auto-valuation for top companies ──
    from pipeline.profile_generator import auto_analyze

    week_folder_name = _week_folder(now)
    week_dir = _RESULTS_BASE / week_folder_name
    week_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Excel output folder: %s", week_dir)
    summary["folder_name"] = week_folder_name
    summary["week_dir"] = str(week_dir)

    def _run_valuation(co: dict) -> dict:
        name = co.get("name", "")
        ticker = co.get("ticker")
        reason = co.get("reason", "")
        try:
            logger.info("Valuation start: %s %s", co.get("stars", ""), name)
            analyze_result = auto_analyze(
                name, output_dir=str(week_dir), scored_data=co
            )
            if analyze_result:
                return {
                    "company": name,
                    "ticker": ticker,
                    "reason": reason,
                    "market": co.get("market", ""),
                    "status": "success",
                    "excel_path": analyze_result.excel_path,
                    "summary_md": analyze_result.summary_md,
                    "market_cap_usd": co.get("market_cap_usd"),
                }
            return {
                "company": name,
                "ticker": ticker,
                "reason": reason,
                "market": co.get("market", ""),
                "status": "no_result",
            }
        except Exception as e:
            logger.error("Valuation failed [%s]: %s", name, e)
            return {
                "company": name,
                "ticker": ticker,
                "reason": reason,
                "market": co.get("market", ""),
                "status": "failed",
                "error": str(e),
            }

    if not targets:
        msg = "Discovery returned 0 companies — valuation skipped. Check NAVER/OpenRouter API keys and network."
        logger.warning(msg)
        _alert("Valuation", msg)
    _summary_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=max(min(len(targets), 3), 1)) as pool:
        futures = {pool.submit(_run_valuation, co): co for co in targets}
        for fut in as_completed(futures):
            entry = fut.result()
            with _summary_lock:
                summary["valuations"].append(entry)
                if entry.get("status") == "failed":
                    summary["errors"].append(
                        {
                            "phase": "valuation",
                            "company": entry["company"],
                            "error": entry.get("error", ""),
                        }
                    )

    # ── Phase 3.5: Upload Excel to Supabase Storage ──
    _upload_excels_to_storage(summary, _storage_folder(week_folder_name))

    # ── Phase 3.6: Save JSON summary for delivery agent ──
    _save_json_summary(summary, week_dir)

    # ── Phase 5: Send email notification (best-effort) ──
    try:
        from .email_sender import send_weekly_email

        send_weekly_email(summary)
    except Exception as e:
        logger.warning("Email notification failed: %s", e)

    # ── Phase 6a: WordPress posting (US only, best-effort) ──
    try:
        from .wp_poster import post_to_wordpress

        wp_url = post_to_wordpress(summary)
        if wp_url:
            summary["wp_url"] = wp_url
    except Exception as e:
        logger.warning("WordPress posting failed: %s", e)
        _alert("WordPress", str(e))

    # ── Phase 6b: Naver Blog posting (KR+US, best-effort) ──
    try:
        from .naver_poster import post_to_naver

        naver_url = post_to_naver(summary)
        if naver_url:
            summary["naver_url"] = naver_url
    except Exception as e:
        logger.warning("Naver Blog posting failed: %s", e)
        _alert("Naver Blog", str(e))

    # ── Phase 7: YouTube video creation + upload (disabled) ──
    # TODO: Re-enable when YouTube pipeline is ready
    # try:
    #     from .video_creator import create_weekly_video
    #     from .youtube_uploader import upload_to_youtube
    #     video_path = create_weekly_video(summary, output_dir=week_dir)
    #     if video_path:
    #         yt_url = upload_to_youtube(video_path, summary)
    #         if yt_url:
    #             summary["youtube_url"] = yt_url
    # except Exception as e:
    #     logger.warning("YouTube pipeline failed: %s", e)
    #     _alert("YouTube", str(e))

    # ── Phase 8: Completion ──
    duration = time.time() - start
    _finalize_run(run_id, summary, duration, total_news, scored)
    _print_completion(summary, duration, week_dir)

    # Log API usage summary
    try:
        usage = ApiGuard.get().get_usage_summary()
        active = {
            k: v for k, v in usage.items() if v["calls"] > 0 or v["cache_hits"] > 0
        }
        if active:
            logger.info("API usage summary: %s", active)
    except Exception:
        pass

    return summary


def _upload_excels_to_storage(summary: dict, week_folder_name: str) -> None:
    """Upload Excel files to Supabase Storage (best-effort)."""
    try:
        from db.storage import upload_and_get_url
    except ImportError:
        logger.debug("db.storage not available — skipping upload")
        return

    for i, entry in enumerate(summary["valuations"]):
        if entry["status"] == "success" and entry.get("excel_path"):
            try:
                ticker = entry.get("ticker")
                if ticker and str(ticker).strip():
                    remote_filename = f"{ticker}_valuation.xlsx"
                else:
                    # Fallback: sanitize company name; if result is empty (Korean-only),
                    # use positional index to guarantee a valid non-empty key
                    from db.storage import _sanitize_key as _sk

                    safe = _sk(Path(entry["excel_path"]).stem)
                    remote_filename = (
                        f"{safe}_valuation.xlsx"
                        if safe
                        else f"company_{i}_valuation.xlsx"
                    )
                upload = upload_and_get_url(
                    entry["excel_path"], week_folder_name, remote_filename
                )
                if upload:
                    entry["download_url"] = upload["download_url"]
                    entry["remote_path"] = upload["remote_path"]
                    logger.info(
                        "Storage upload OK [%s] ticker=%s → %s",
                        entry["company"],
                        ticker,
                        upload["remote_path"],
                    )
            except Exception as e:
                logger.warning("Storage upload failed [%s]: %s", entry["company"], e)


def _save_json_summary(summary: dict, week_dir: Path) -> None:
    """Save JSON summary file for the delivery agent to read."""
    success_count = sum(1 for v in summary["valuations"] if v["status"] == "success")
    failed_count = sum(1 for v in summary["valuations"] if v["status"] == "failed")

    summary_json = {
        **summary,
        "status_summary": {
            "total": len(summary["valuations"]),
            "success": success_count,
            "failed": failed_count,
        },
    }

    summary_path = week_dir / "_weekly_summary.json"
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_json, f, ensure_ascii=False, indent=2, default=str)
        logger.info("JSON summary saved: %s", summary_path)
    except Exception as e:
        logger.warning("Failed to save JSON summary: %s", e)


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


def _print_completion(
    summary: dict, duration: float, output_dir: Path | None = None
) -> None:
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

        return save_discovery_run(
            {
                "markets": markets,
                "status": "running",
            }
        )
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
        update_discovery_run(
            run_id,
            {
                "status": status,
                "news_count": total_news,
                "companies_discovered": scored,
                "companies_analyzed": [v["company"] for v in summary["valuations"]],
                "errors": summary["errors"],
                "duration_seconds": round(duration, 1),
            },
        )
    except Exception as e:
        logger.debug("DB 기록 실패 (완료): %s", e)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Weekly automated news collection + valuation",
    )
    parser.add_argument(
        "--markets",
        default="KR,US",
        help="Target markets (comma-separated, default: KR,US)",
    )
    parser.add_argument(
        "--max-per-market",
        type=int,
        default=5,
        help="Max companies per market (default: 5)",
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
        help="Discovery only, skip valuation",
    )
    args = parser.parse_args()

    max_val = args.max_per_market
    if args.max_companies is not None:
        max_val = args.max_companies

    run_weekly(
        markets=args.markets.split(","),
        max_per_market=max_val,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
