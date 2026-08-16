"""CLI entry point.

Usage:
    python cli.py --company sk_hynix
    python cli.py --company sk_hynix --dry-run         # fixture-only, no API calls
    python cli.py --company sk_hynix --skip-pdf        # skip Chrome PDF export
    python cli.py --company sk_hynix --inline-plotly   # embed plotly.js (offline)

Pipeline (all to be wired by Codex):
    1. pipeline.ir_loader.load_profile         -> profile dict
    2. pipeline.dart_fetcher.fetch_quarterly_financials  -> raw DART
       pipeline.dart_fetcher.extract_quarterly_actual    -> list[QuarterlyActual]
    3. pipeline.yahoo_fetcher.fetch_consensus  -> raw Yahoo
       pipeline.consensus_loader.to_consensus_record    -> ConsensusRecord
    4. For each scenario in [bear, base, bull]:
         engine.segment_revenue.project_quarterly_revenue
         engine.margin_model.project_margins
         engine.tax_finance.apply_taxes_and_finance
         engine.eps_bridge.project_eps
         engine.scenario.aggregate_quarterly_to_annual
    5. engine.scenario.build_scenario_tree    -> ScenarioTree
    6. engine.consensus_diff.compute_consensus_gap  -> list[ConsensusGap]
    7. engine.backtest.run_backtest           -> BacktestResult
    8. output.plotly_charts.{build_fan_chart, build_beat_miss_bar, build_scenario_compare}
       output.static_charts.{save_fan_chart_png, save_beat_miss_png}
       output.html_builder.render_html_report
       output.md_builder.render_md_report
       output.xlsx_writer.write_xlsx
       (optional) output.pdf_export.html_to_pdf
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PROFILES_DIR = REPO_ROOT / "profiles"
REPORTS_DIR = REPO_ROOT / "reports"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
# httpx logs full request URLs at INFO, which would leak the DART API key
# (passed as the crtfc_key query parameter). Silence it to WARNING.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger("earnings-forecast")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Quarterly earnings forecast engine")
    parser.add_argument(
        "--company",
        required=True,
        help="Profile name in profiles/ (without .yaml). e.g. sk_hynix",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use tests/fixtures/ instead of live API calls",
    )
    parser.add_argument(
        "--inline-plotly",
        action="store_true",
        help="Bundle plotly.js into HTML (offline-friendly, +~3MB)",
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip Chrome headless PDF export",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPORTS_DIR,
        help="Output directory (default: reports/)",
    )
    parser.add_argument(
        "--call-brief",
        action="store_true",
        help="Signal layer: generate next-quarter earnings-call pre-briefing",
    )
    parser.add_argument(
        "--signal-backtest",
        action="store_true",
        help="Signal layer: run CAR event-study backtest of text signals",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    profile_path = PROFILES_DIR / f"{args.company}.yaml"
    if not profile_path.exists():
        logger.error("Profile not found: %s", profile_path)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.signal_backtest:
        return run_signal_backtest_mode(args, profile_path)
    if args.call_brief:
        return run_call_brief_mode(args, profile_path)

    today = date.today().strftime("%Y%m%d")
    base_name = f"{args.company}_{today}"
    html_path = args.out_dir / f"{base_name}.html"
    md_path = args.out_dir / f"{base_name}.md"
    xlsx_path = args.out_dir / f"{base_name}.xlsx"
    fan_png_path = args.out_dir / f"{base_name}_fan.png"
    beat_miss_png_path = args.out_dir / f"{base_name}_beat_miss.png"
    pdf_path = args.out_dir / f"{base_name}.pdf"

    logger.info("Profile: %s", profile_path)
    logger.info("Out dir: %s", args.out_dir)
    logger.info("Dry run: %s", args.dry_run)

    from dotenv import load_dotenv

    from engine.backtest import run_backtest
    from engine.below_op_events import build_event_adjusted_eps
    from engine.consensus_diff import compute_consensus_gap
    from engine.eps_bridge import project_eps
    from engine.margin_model import project_margins
    from engine.risk_band import build_eps_risk_band
    from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
    from engine.segment_revenue import build_margin_carryover, project_quarterly_revenue
    from engine.tax_finance import apply_taxes_and_finance
    from engine.valuation_bridge import sensitivity_to_dcf
    from output.html_builder import render_html_report
    from output.md_builder import render_md_report
    from output.static_charts import save_beat_miss_png, save_fan_chart_png
    from output.xlsx_writer import write_xlsx
    from pipeline.consensus_loader import to_consensus_record
    from pipeline.dart_fetcher import extract_quarterly_actual, fetch_quarterly_actuals_series
    from pipeline.ir_loader import load_profile
    from pipeline.yahoo_fetcher import fetch_consensus
    from schemas.models import BacktestResult, MarginBaseline, QuarterlyActual, ScenarioCase

    load_dotenv(REPO_ROOT / ".env")
    profile = load_profile(profile_path)
    segment_split = profile["segment_revenue_split"]

    if args.dry_run:
        with open(FIXTURES_DIR / "sk_hynix_2024q4_dart.json", encoding="utf-8") as f:
            dart_q4_raw = json.load(f)
        with open(FIXTURES_DIR / "sk_hynix_2024q3_dart.json", encoding="utf-8") as f:
            dart_q3_raw = json.load(f)
        with open(FIXTURES_DIR / "sk_hynix_yahoo_estimates.json", encoding="utf-8") as f:
            yahoo_raw = json.load(f)
        historical_actuals = [
            QuarterlyActual.model_validate(
                extract_quarterly_actual(
                    dart_q3_raw,
                    "2024Q3",
                    segment_revenue_split=segment_split,
                )
            ),
            QuarterlyActual.model_validate(
                extract_quarterly_actual(
                    dart_q4_raw,
                    "2024Q4",
                    q3_raw_dart=dart_q3_raw,
                    segment_revenue_split=segment_split,
                )
            ),
        ]
    else:
        start_year = int(str(profile["backtest_window"]["start_quarter"])[:4]) - 1
        forecast_start_year = int(str(profile["forecast_window"]["start_quarter"])[:4])
        end_year = max(int(str(profile["backtest_window"]["end_quarter"])[:4]), forecast_start_year)
        historical_actuals = fetch_quarterly_actuals_series(
            profile["company"].corp_code_dart,
            start_year,
            end_year,
            segment_split,
        )
        yahoo_raw = fetch_consensus(profile["company"].ticker_yahoo)

    seed_label = _previous_quarter_label(str(profile["forecast_window"]["start_quarter"]))
    try:
        prior_actual = _actual_for_quarter(historical_actuals, seed_label)
    except ValueError:
        if not args.dry_run:
            raise
        logger.warning("Dry-run fixture lacks %s; using latest fixture quarter as seed.", seed_label)
        prior_actual = sorted(historical_actuals, key=lambda item: item.period_end)[-1]
    baseline = MarginBaseline(
        gp_margin=prior_actual.gross_profit / prior_actual.revenue_total,
        op_margin=prior_actual.operating_profit / prior_actual.revenue_total,
        np_margin=prior_actual.net_profit / prior_actual.revenue_total,
        dram_blended_asp=next(s.revenue for s in prior_actual.revenue_by_segment if s.segment_id == "dram"),
        nand_blended_asp=next(s.revenue for s in prior_actual.revenue_by_segment if s.segment_id == "nand"),
    )
    margin_carryover = build_margin_carryover(profile["historical_drivers"], seed_label)

    cases = {}
    n_quarters = int(profile["forecast_window"]["n_quarters"])
    for name in ("bear", "base", "bull"):
        segment_assumptions, margin_assumptions, finance_assumptions = profile["scenarios"][name]
        quarterly = project_quarterly_revenue(
            prior_actual,
            baseline,
            segment_assumptions,
            n_quarters,
            margin_carryover,
        )
        quarterly = project_margins(quarterly, baseline, margin_assumptions, profile["anchor_margins"])
        quarterly = apply_taxes_and_finance(quarterly, finance_assumptions)
        quarterly = project_eps(quarterly, profile["shares"])
        annual = aggregate_quarterly_to_annual(quarterly, name)
        cases[name] = ScenarioCase(
            scenario=name,
            probability=getattr(profile["probabilities"], name),
            rationale=profile["rationales"][name],
            quarterly=quarterly,
            annual=annual,
        )

    tree = build_scenario_tree(
        profile["company"],
        date.today(),
        cases["bear"],
        cases["base"],
        cases["bull"],
        profile["probabilities"],
    )
    consensus = to_consensus_record(
        yahoo_raw,
        profile["company"].ticker_yahoo,
        weighted_avg_basic_shares=profile["shares"].weighted_avg_basic,
    )
    if consensus.notes:
        profile["raw"]["consensus_notes"] = consensus.notes
    gaps = compute_consensus_gap(tree, consensus)

    base_assumptions, base_margin_assumptions, base_finance_assumptions = profile["scenarios"]["base"]
    backtest_history = _actuals_through_quarter(historical_actuals, str(profile["backtest_window"]["end_quarter"]))
    lookback_quarters = int(profile["backtest_window"]["lookback_quarters"])
    if len(backtest_history) >= lookback_quarters + 4:
        backtest = run_backtest(
            backtest_history,
            base_assumptions,
            base_margin_assumptions,
            profile["anchor_margins"],
            base_finance_assumptions,
            profile["shares"],
            profile["historical_drivers"],
            lookback_quarters,
            consensus_history=consensus.history,
        )
    elif args.dry_run:
        logger.warning("Dry-run fixtures do not contain enough quarters for backtest; emitting empty backtest.")
        backtest = BacktestResult(
            lookback_quarters=0,
            quarters=[],
            revenue_mape=0.0,
            eps_mape=None,
            hit_ratio_direction=0.0,
            bias_revenue=0.0,
            bias_eps=None,
        )
    else:
        raise ValueError(f"need at least {lookback_quarters + 4} real quarters for backtest")

    # Post-mortem EPS-error attribution (PLAN_skill_adoption.md EFE-1) — rendering
    # layer only. Reuses the exact backtest projection; nothing is fed back into
    # forecasts or the backtest, and BacktestResult itself is untouched.
    attributions = None
    if backtest.quarters:
        from engine.attribution import attribute_eps_error
        from engine.backtest import implied_basic_shares, iter_backtest_forecasts

        try:
            attributions = [
                attribute_eps_error(
                    target, forecast, implied_basic_shares(seed) or profile["shares"].weighted_avg_basic
                )
                for seed, target, forecast in iter_backtest_forecasts(
                    backtest_history,
                    base_assumptions,
                    base_margin_assumptions,
                    profile["anchor_margins"],
                    base_finance_assumptions,
                    profile["shares"],
                    profile["historical_drivers"],
                    lookback_quarters,
                )
            ]
        except ValueError as exc:
            logger.warning("EPS-error attribution skipped: %s", exc)
            attributions = None

    # Below-OP EPS risk band (separate layer over the point estimate; overlays are
    # surfaced as annotations only — PLAN_tax_finance_overlay.md). None when the
    # profile omits a risk_band block, leaving the report unchanged.
    risk_band = None
    risk_band_cfg = profile.get("risk_band")
    if risk_band_cfg:
        eps_points = [(q.quarter_label, q.eps_basic) for q in tree.weighted_quarterly]
        risk_band = build_eps_risk_band(
            eps_points,
            half_width_pct=risk_band_cfg["half_width_pct"],
            method=risk_band_cfg["method"],
            k=risk_band_cfg["k"],
            overlays=profile.get("overlays"),
        )

    # Valuation bridge: forward FY1 EPS gap vs consensus -> fair-value delta
    # (elasticity), plus the macro overlay/risk layer (separate). Consensus is held
    # only on genuine quality failures (quality_notes -> §①-B yfinance .KS guard),
    # not on benign field absence (Codex follow-up #1).
    valuation = None
    valuation_cfg = profile.get("valuation")
    if valuation_cfg and tree.weighted_annual and tree.weighted_annual[0].eps_basic is not None:
        fy1 = tree.weighted_annual[0].fiscal_year
        valuation = sensitivity_to_dcf(
            tree,
            consensus.eps_estimate_annual.get(fy1),
            fair_value_elasticity=valuation_cfg.fair_value_elasticity,
            eps_half_width_pct=(risk_band.half_width_pct if risk_band is not None else None),
            overlays=profile.get("overlays"),
            overlay_weight=valuation_cfg.overlay_weight,
            consensus_reliable=(len(consensus.quality_notes) == 0),
        )

    # Identified below-OP events are computed only after valuation, as an
    # output-only alternative EPS scenario. They never mutate tree and are never
    # passed to risk_band, backtest, or valuation_bridge.
    below_op_event_scenario = None
    if profile.get("below_op_events"):
        below_op_event_scenario = build_event_adjusted_eps(
            [(q.quarter_label, q.eps_basic) for q in tree.weighted_quarterly],
            profile["shares"].weighted_avg_basic,
            profile["below_op_events"],
            calculation_as_of=tree.as_of,
            effective_tax_rate=profile["scenarios"]["base"][2].effective_tax_rate,
        )

    save_fan_chart_png(tree, fan_png_path)
    save_beat_miss_png(backtest, beat_miss_png_path)
    render_html_report(html_path, tree, gaps, backtest, profile["raw"], args.inline_plotly, risk_band=risk_band, valuation=valuation, below_op_event_scenario=below_op_event_scenario, attributions=attributions)
    render_md_report(md_path, tree, gaps, backtest, fan_png_path, beat_miss_png_path, consensus.notes, risk_band=risk_band, valuation=valuation, below_op_event_scenario=below_op_event_scenario)
    write_xlsx(xlsx_path, tree, backtest)

    logger.info("Wrote %s", html_path)
    logger.info("Wrote %s", md_path)
    logger.info("Wrote %s", xlsx_path)
    if not args.skip_pdf:
        try:
            from output.pdf_export import html_to_pdf

            html_to_pdf(html_path, pdf_path)
            logger.info("Wrote %s", pdf_path)
        except Exception as exc:
            logger.warning("PDF export skipped: %s", exc)
    return 0


def _load_daily_closes(price_payload: dict) -> dict:
    """Map a fetch_price_history payload to {date: close} for CAR computation."""
    from datetime import datetime

    closes: dict = {}
    for row in price_payload.get("history", []):
        stamp = row.get("Date") or row.get("index")
        close = row.get("Close")
        if stamp is None or close is None:
            continue
        day = datetime.fromisoformat(str(stamp).replace("Z", "").split("T")[0]).date()
        closes[day] = float(close)
    return closes


def _event_dates_from_yahoo(events_payload: dict) -> dict:
    """Map fetch_earnings_dates payload to {event_label: announcement date}.

    event_label is the reporting quarter the announcement is FOR. yfinance gives
    the announcement timestamp; the quarter is announcement_quarter - 1 (results
    are reported after the period closes). Codex may refine the mapping if the
    profile pins explicit event_label<->date pairs.
    """
    from datetime import datetime

    out: dict = {}
    for row in events_payload.get("events", []):
        stamp = row.get("Earnings Date") or row.get("index") or row.get("Date")
        if stamp is None:
            continue
        announced = datetime.fromisoformat(str(stamp).replace("Z", "").split("T")[0]).date()
        reported_q = (announced.month - 1) // 3 + 1
        year = announced.year
        quarter = reported_q - 1 or 4
        if quarter == 4:
            year -= 1
        out[f"{year}Q{quarter}"] = announced
    return out


def run_signal_backtest_mode(args: argparse.Namespace, profile_path: Path) -> int:
    """CAR event-study backtest of text signals (Phase B). DORMANT.

    Unreachable in the current configuration: no profile carries a `signal_layer`
    section (dropped in 4ebeb7c, 2026-07-10), so this returns 2 before touching
    any loader. Reactivation = restore the profile block + real deck/DART
    fixtures + the extraction-completeness contract in
    pipeline/disclosure_loader.py, as one piece of work.

    Wiring only — leaf functions (disclosure_loader, ai.extractor, engine.*) are
    implemented by Codex. dry-run uses fixtures so no API key/decks are required.
    """
    from datetime import date as date_

    from ai.extractor import MODEL_ID, extract_signal
    from engine.signal_backtest import run_signal_backtest
    from engine.signal_extractor import build_extracted_signal
    from output.call_brief_builder import render_signal_backtest_html, render_signal_backtest_md
    from pipeline.disclosure_loader import load_ir_decks
    from pipeline.ir_loader import load_profile

    profile = load_profile(profile_path)
    signal_cfg = profile["raw"].get("signal_layer")
    if not signal_cfg:
        logger.error("profiles/%s.yaml has no signal_layer section", args.company)
        return 2

    taxonomy = signal_cfg.get("topic_taxonomy", [])
    window = signal_cfg.get("event_window", {})
    primary = int(window.get("primary_days", 1))
    secondary = int(window.get("secondary_days", 5))
    benchmark = window.get("benchmark", "^KS11")
    ticker = profile["company"].ticker_yahoo
    today = date_.today()

    if args.dry_run:
        signals, event_dates, stock_closes, market_closes = _load_signal_backtest_fixtures(today)
    else:
        from pipeline.yahoo_fetcher import fetch_earnings_dates, fetch_price_history

        decks_dir = Path(signal_cfg.get("decks_dir", r"C:/temp/earnings_forecast/decks"))
        documents = load_ir_decks(signal_cfg.get("decks", []), decks_dir)
        signals = {
            doc.period_label: build_extracted_signal(
                extract_signal(doc, taxonomy), doc, MODEL_ID, today
            )
            for doc in documents
        }
        event_dates = _event_dates_from_yahoo(fetch_earnings_dates(ticker))
        stock_closes = _load_daily_closes(fetch_price_history(ticker, "5y"))
        market_closes = _load_daily_closes(fetch_price_history(benchmark, "5y"))

    result = run_signal_backtest(
        signals, event_dates, stock_closes, market_closes, primary, secondary
    )

    base = f"{args.company}_signal_backtest_{today:%Y%m%d}"
    md_path = args.out_dir / f"{base}.md"
    html_path = args.out_dir / f"{base}.html"
    render_signal_backtest_md(md_path, result)
    render_signal_backtest_html(html_path, result)
    logger.info("Wrote %s", md_path)
    logger.info("Wrote %s", html_path)
    return 0


def run_call_brief_mode(args: argparse.Namespace, profile_path: Path) -> int:
    """Forward earnings-call pre-briefing (Phase B). DORMANT.

    Same status as run_signal_backtest_mode: no profile carries `signal_layer`,
    so this returns 2 before fetching anything. See
    pipeline/disclosure_loader.py for the known extraction gaps that must be
    closed as part of reactivation.

    Wiring only — leaf functions implemented by Codex. dry-run uses fixtures.
    """
    from datetime import date as date_

    from ai.extractor import MODEL_ID, extract_signal
    from engine.signal_extractor import build_extracted_signal
    from engine.signal_predictor import build_call_brief
    from output.call_brief_builder import render_call_brief_html, render_call_brief_md
    from pipeline.ir_loader import load_profile

    profile = load_profile(profile_path)
    signal_cfg = profile["raw"].get("signal_layer")
    if not signal_cfg:
        logger.error("profiles/%s.yaml has no signal_layer section", args.company)
        return 2

    taxonomy = signal_cfg.get("topic_taxonomy", [])
    brief_cfg = signal_cfg.get("call_brief", {})
    target_event = brief_cfg.get("target_event", "")
    today = date_.today()

    if args.dry_run:
        signal, consensus = _load_call_brief_fixtures(profile, today)
    else:
        from pipeline.consensus_loader import to_consensus_record
        from pipeline.disclosure_loader import fetch_dart_mdna
        from pipeline.yahoo_fetcher import fetch_consensus

        mdna = brief_cfg["mdna"]
        document = fetch_dart_mdna(
            mdna["rcp_no"], mdna["period_label"], date_.fromisoformat(mdna["doc_date"])
        )
        signal = build_extracted_signal(extract_signal(document, taxonomy), document, MODEL_ID, today)
        consensus = to_consensus_record(
            fetch_consensus(profile["company"].ticker_yahoo),
            profile["company"].ticker_yahoo,
            weighted_avg_basic_shares=profile["shares"].weighted_avg_basic,
        )

    brief = build_call_brief(signal, consensus, target_event, today)
    base = f"{args.company}_call_brief_{today:%Y%m%d}"
    html_path = args.out_dir / f"{base}.html"
    md_path = args.out_dir / f"{base}.md"
    render_call_brief_html(html_path, brief)
    render_call_brief_md(md_path, brief)
    logger.info("Wrote %s", html_path)
    logger.info("Wrote %s", md_path)
    return 0


def _load_signal_backtest_fixtures(as_of: "date") -> tuple[dict, dict, dict, dict]:
    """Load signal-backtest fixtures (extractions + event dates + daily closes).

    See tests/fixtures/signal_backtest_fixture.json (created in the scaffold).
    Returns (signals, event_dates, stock_closes, market_closes).
    """
    from datetime import date as date_

    from engine.signal_extractor import build_extracted_signal
    from schemas.models import DisclosureDocument

    with open(FIXTURES_DIR / "signal_backtest_fixture.json", encoding="utf-8") as f:
        fx = json.load(f)
    signals: dict = {}
    for item in fx["documents"]:
        doc = DisclosureDocument.model_validate(item["document"])
        signals[doc.period_label] = build_extracted_signal(
            item["extraction"], doc, "fixture", as_of
        )
    event_dates = {k: date_.fromisoformat(v) for k, v in fx["event_dates"].items()}
    stock_closes = {date_.fromisoformat(k): v for k, v in fx["stock_closes"].items()}
    market_closes = {date_.fromisoformat(k): v for k, v in fx["market_closes"].items()}
    return signals, event_dates, stock_closes, market_closes


def _load_call_brief_fixtures(profile: dict, as_of: "date") -> tuple:
    """Load call-brief fixtures (one extraction + a consensus record)."""
    from engine.signal_extractor import build_extracted_signal
    from pipeline.consensus_loader import to_consensus_record
    from schemas.models import DisclosureDocument

    with open(FIXTURES_DIR / "call_brief_fixture.json", encoding="utf-8") as f:
        fx = json.load(f)
    document = DisclosureDocument.model_validate(fx["document"])
    signal = build_extracted_signal(fx["extraction"], document, "fixture", as_of)
    with open(FIXTURES_DIR / "sk_hynix_yahoo_estimates.json", encoding="utf-8") as f:
        yahoo_raw = json.load(f)
    consensus = to_consensus_record(
        yahoo_raw,
        profile["company"].ticker_yahoo,
        weighted_avg_basic_shares=profile["shares"].weighted_avg_basic,
    )
    return signal, consensus


def _previous_quarter_label(label: str) -> str:
    year_text, quarter_text = label.split("Q", 1)
    year = int(year_text)
    quarter = int(quarter_text)
    if quarter == 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


def _quarter_sort_key(label: str) -> tuple[int, int]:
    year_text, quarter_text = label.split("Q", 1)
    return int(year_text), int(quarter_text)


def _actual_for_quarter(actuals: list["QuarterlyActual"], quarter_label: str) -> "QuarterlyActual":
    for actual in actuals:
        if actual.quarter_label == quarter_label:
            return actual
    available = ", ".join(actual.quarter_label for actual in actuals) or "none"
    raise ValueError(f"missing real DART actual for seed quarter {quarter_label}; available: {available}")


def _actuals_through_quarter(actuals: list["QuarterlyActual"], quarter_label: str) -> list["QuarterlyActual"]:
    end_key = _quarter_sort_key(quarter_label)
    return [
        actual
        for actual in sorted(actuals, key=lambda item: item.period_end)
        if _quarter_sort_key(actual.quarter_label) <= end_key
    ]


if __name__ == "__main__":
    sys.exit(main())
