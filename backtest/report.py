"""Calibration report generation — console text + JSON."""

from __future__ import annotations

from collections import defaultdict

from .metrics import (
    calc_forecast_price_error,
    calc_gap_closure,
    calc_interval_score,
    calc_calibration_curve,
)
from .models import BacktestRecord


def generate_report(records: list[BacktestRecord]) -> tuple[str, dict]:
    """Generate calibration report from backtest records.

    Returns:
        (console_text, report_json)
    """
    lines: list[str] = []
    report: dict = {}

    listed = [r for r in records if r.is_listed]
    lines.append(f"═══ Calibration Report (N={len(listed)} listed valuations) ═══")
    lines.append("")
    report["n_total"] = len(records)
    report["n_listed"] = len(listed)

    if not listed:
        lines.append("No listed company valuations found for backtesting.")
        return "\n".join(lines), report

    # ── Forecast-to-Price Error ──
    lines.append("Forecast-to-Price Error:")
    lines.append(f"  {'Horizon':<9} │ {'MAPE':>6} │ {'Median':>7} │ {'Log Ratio':>10} │ {'N':>4}")
    lines.append(f"  {'─' * 9} │ {'─' * 6} │ {'─' * 7} │ {'─' * 10} │ {'─' * 4}")

    report["forecast_error"] = {}
    for horizon, label in [("t3m", "T+3m"), ("t6m", "T+6m"), ("t12m", "T+12m")]:
        err = calc_forecast_price_error(listed, horizon)
        report["forecast_error"][horizon] = err
        if err["n"] > 0 and err["mape"] is not None:
            lines.append(
                f"  {label:<9} │ {err['mape']:>5.0%} │ {err['median_ape']:>6.0%} │ "
                f"{err['log_ratio_mean']:>+9.2f} │ {err['n']:>4}"
            )
        else:
            lines.append(f"  {label:<9} │    -- │     -- │        -- │    0")
    lines.append("")

    # ── Gap Closure ──
    lines.append("Gap Closure:")
    lines.append(f"  {'Horizon':<9} │ {'Mean':>6} │ {'Median':>7} │ {'Pos Rate':>9} │ {'N':>4}")
    lines.append(f"  {'─' * 9} │ {'─' * 6} │ {'─' * 7} │ {'─' * 9} │ {'─' * 4}")

    report["gap_closure"] = {}
    for horizon, label in [("t3m", "T+3m"), ("t6m", "T+6m"), ("t12m", "T+12m")]:
        gc = calc_gap_closure(listed, horizon)
        report["gap_closure"][horizon] = gc
        if gc["n"] > 0 and gc["mean_closure"] is not None:
            lines.append(
                f"  {label:<9} │ {gc['mean_closure']:>5.2f} │ {gc['median_closure']:>6.2f} │ "
                f"{gc['positive_closure_rate']:>8.0%} │ {gc['n']:>4}"
            )
        else:
            lines.append(f"  {label:<9} │    -- │     -- │       -- │    0")
    lines.append("")

    # ── Interval Score ──
    lines.append("Interval Score:")
    lines.append(f"  {'Horizon':<9} │ {'Coverage':>9} │ {'Width':>7} │ {'Pinball':>8} │ {'N':>4}")
    lines.append(f"  {'─' * 9} │ {'─' * 9} │ {'─' * 7} │ {'─' * 8} │ {'─' * 4}")

    report["interval_score"] = {}
    for horizon, label in [("t3m", "T+3m"), ("t6m", "T+6m"), ("t12m", "T+12m")]:
        iv = calc_interval_score(listed, horizon)
        report["interval_score"][horizon] = iv
        if iv["n"] > 0 and iv["coverage_rate"] is not None:
            width_str = f"{iv['mean_interval_width']:>6.0%}" if iv["mean_interval_width"] is not None else "    --"
            pinball_str = f"{iv['pinball_loss']:>7.2f}" if iv["pinball_loss"] is not None else "     --"
            lines.append(
                f"  {label:<9} │ {iv['coverage_rate']:>8.0%} │ {width_str} │ {pinball_str} │ {iv['n']:>4}"
            )
        else:
            lines.append(f"  {label:<9} │       -- │     -- │      -- │    0")
    lines.append("")

    # ── Calibration Curve ──
    cal = calc_calibration_curve(listed, "t6m")
    report["calibration_curve"] = cal
    if cal is None:
        lines.append("Calibration Curve: insufficient data (need 30+ scenario observations)")
    else:
        lines.append("Calibration Curve (T+6m):")
        lines.append(f"  {'Bin':<10} │ {'Assigned':>9} │ {'Realized':>9} │ {'Count':>6}")
        lines.append(f"  {'─' * 10} │ {'─' * 9} │ {'─' * 9} │ {'─' * 6}")
        for b in cal:
            lines.append(
                f"  {b['bin_label']:<10} │ {b['assigned_prob_mean']:>8.1f}% │ "
                f"{b['realized_freq']:>8.1f}% │ {b['count']:>6}"
            )
    lines.append("")

    # ── Per-Company Breakdown ──
    by_company: dict[str, list[BacktestRecord]] = defaultdict(list)
    for r in listed:
        by_company[r.company_name].append(r)

    if by_company:
        lines.append("Per-Company Breakdown:")
        lines.append(f"  {'Company':<16} │ {'T+6m MAPE':>10} │ {'Gap Closure':>12} │ {'Coverage':>9}")
        lines.append(f"  {'─' * 16} │ {'─' * 10} │ {'─' * 12} │ {'─' * 9}")

        report["per_company"] = {}
        for company, company_records in sorted(by_company.items()):
            err = calc_forecast_price_error(company_records, "t6m")
            gc = calc_gap_closure(company_records, "t6m")
            iv = calc_interval_score(company_records, "t6m")

            mape_str = f"{err['mape']:>9.0%}" if err["mape"] is not None else "       --"
            gc_str = f"{gc['mean_closure']:>11.2f}" if gc["mean_closure"] is not None else "         --"
            cov_str = "YES" if (iv["coverage_rate"] is not None and iv["coverage_rate"] > 0.5) else "NO"
            if iv["coverage_rate"] is None:
                cov_str = "--"

            lines.append(f"  {company:<16} │ {mape_str} │ {gc_str} │ {cov_str:>9}")

            report["per_company"][company] = {
                "forecast_error": err,
                "gap_closure": gc,
                "interval_score": iv,
            }
        lines.append("")

    # ── Systematic Bias Warning ──
    err_6m = report.get("forecast_error", {}).get("t6m", {})
    log_ratio = err_6m.get("log_ratio_mean")
    if log_ratio is not None and abs(log_ratio) > 0.05:
        direction = "과대추정" if log_ratio > 0 else "과소추정"
        pct = abs(log_ratio) * 100
        lines.append(f"⚠ Systematic Bias: Log ratio {log_ratio:+.2f} → {pct:.0f}% 체계적 {direction} 경향")
        report["systematic_bias"] = {"log_ratio": log_ratio, "direction": direction}

    # ── Phase 4 A/B Comparison (signals v0 vs v1) ──
    ab = calc_ab_comparison(listed)
    if ab:
        report["ab_comparison"] = ab
        lines.append("")
        lines.append("Phase 4 A/B Comparison (Market Signals):")
        for key in ("v0", "v1"):
            grp = ab.get(key, {})
            if grp.get("n", 0) == 0:
                continue
            label = "Baseline (v0)" if key == "v0" else "Signals (v1)"
            mape_str = f"{grp['mape_t6m']:.0%}" if grp.get("mape_t6m") is not None else "--"
            gc_str = f"{grp['gap_closure_t6m']:.2f}" if grp.get("gap_closure_t6m") is not None else "--"
            cov_str = f"{grp['coverage_t6m']:.0%}" if grp.get("coverage_t6m") is not None else "--"
            lines.append(f"  {label:<18} │ N={grp['n']:>3} │ MAPE={mape_str:>5} │ GapClosure={gc_str:>5} │ Coverage={cov_str:>5}")

    return "\n".join(lines), report


def calc_ab_comparison(records: list[BacktestRecord]) -> dict | None:
    """Compare calibration metrics between v0 (no signals) and v1 (with signals).

    Returns None if either group has insufficient data (< 3 records).
    """
    v0 = [r for r in records if getattr(r, "market_signals_version", 0) == 0]
    v1 = [r for r in records if getattr(r, "market_signals_version", 0) >= 1]

    if len(v0) < 3 and len(v1) < 3:
        return None

    result = {}
    for key, group in [("v0", v0), ("v1", v1)]:
        if not group:
            result[key] = {"n": 0}
            continue
        err = calc_forecast_price_error(group, "t6m")
        gc = calc_gap_closure(group, "t6m")
        iv = calc_interval_score(group, "t6m")
        result[key] = {
            "n": len(group),
            "mape_t6m": err.get("mape"),
            "gap_closure_t6m": gc.get("mean_closure"),
            "coverage_t6m": iv.get("coverage_rate"),
        }

    return result
