"""Opex-lever diagnosis (Open Problem "Opex systematic bias -4.2%", 2026-07-02).

Read-only: mirrors the cli.py/diagnose_divergence.py backtest wiring and compares,
per backtest quarter, the model's opex ratio against the realized opex ratio
(GP - OP) / revenue. Purpose: decide whether the -4.2% mean opex EPS-error
contribution (7/8 quarters negative) is

  (a) a level miscalibration  -- assumed % is simply too high vs realized, or
  (b) a shape mismatch        -- opex is sticky in absolute KRW (operating
      leverage), so a constant % of revenue overstates opex in high-revenue
      quarters and the bias scales with the up-cycle.

Verdict (2026-07-02, 8Q): both — assumed constant 15% vs realized mean 12.52%,
corr(revenue, opex%rev) = -0.77, OLS opex = 992 bn + 7.3% x revenue. Addressed
by the optional fixed+variable opex split (PLAN_opex_model.md); the model column
below reflects whichever path the profile configures.

Changes no forecast numbers. Assumption values stay user-owned.

Usage:
    DART_API_KEY=<any> python scripts/diagnose_opex.py --company sk_hynix
    (cache hit in reports/.cache -> offline)
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.backtest import iter_backtest_forecasts  # noqa: E402
from pipeline.dart_fetcher import fetch_quarterly_actuals_series  # noqa: E402
from pipeline.ir_loader import load_profile  # noqa: E402


def _quarter_sort_key(label: str) -> tuple[int, int]:
    year_text, quarter_text = label.split("Q", 1)
    return int(year_text), int(quarter_text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Opex-lever diagnosis (read-only)")
    parser.add_argument("--company", required=True, help="Profile name (without .yaml)")
    parser.add_argument("--no-cache", action="store_true", help="Force live DART (default: cache)")
    args = parser.parse_args(argv)

    profile = load_profile(REPO_ROOT / "profiles" / f"{args.company}.yaml")
    backtest_window = profile["backtest_window"]
    end_quarter = str(backtest_window["end_quarter"])
    lookback_quarters = int(backtest_window["lookback_quarters"])
    start_year = int(str(backtest_window["start_quarter"])[:4]) - 1

    actuals = fetch_quarterly_actuals_series(
        profile["company"].corp_code_dart,
        start_year,
        int(end_quarter[:4]),
        profile["segment_revenue_split"],
        use_cache=not args.no_cache,
        skip_unavailable=True,  # offline diagnostics: unfiled/uncached future quarters warn+skip
    )
    end_key = _quarter_sort_key(end_quarter)
    history = [a for a in actuals if _quarter_sort_key(a.quarter_label) <= end_key]

    base_assumptions, base_margin, base_finance = profile["scenarios"]["base"]
    rows = list(
        iter_backtest_forecasts(
            history,
            base_assumptions,
            base_margin,
            profile["anchor_margins"],
            base_finance,
            profile["shares"],
            profile["historical_drivers"],
            lookback_quarters,
        )
    )

    header = (
        f"{'Quarter':<8} {'rev (bn)':>10} {'act opex':>9} {'act %rev':>9} "
        f"{'mdl %rev':>9} {'gap (pp)':>9}   (opex = GP - OP)"
    )
    print(header)
    print("-" * len(header))

    revenues: list[float] = []
    opex_abs: list[float] = []
    opex_pct: list[float] = []
    model_pct: list[float] = []
    for _seed, target, forecast in rows:
        a_opex = target.gross_profit - target.operating_profit
        a_pct = a_opex / target.revenue_total
        m_pct = (forecast.gross_profit - forecast.operating_profit) / forecast.revenue_total
        revenues.append(target.revenue_total)
        opex_abs.append(a_opex)
        opex_pct.append(a_pct)
        model_pct.append(m_pct)
        print(
            f"{target.quarter_label:<8} {target.revenue_total:>10,.0f} {a_opex:>9,.0f} "
            f"{a_pct:>8.2%} {m_pct:>8.2%} {(m_pct - a_pct) * 100:>+8.2f}p"
        )

    n = len(rows)
    if n < 3:
        print(f"\nonly {n} quarters — summary skipped")
        return 0

    print("-" * len(header))
    mean_pct = statistics.fmean(opex_pct)
    mean_model_pct = statistics.fmean(model_pct)
    print(
        f"{'MEAN':<8} {statistics.fmean(revenues):>10,.0f} {statistics.fmean(opex_abs):>9,.0f} "
        f"{mean_pct:>8.2%} {mean_model_pct:>8.2%} {(mean_model_pct - mean_pct) * 100:>+8.2f}p"
    )

    if base_margin.opex_fixed_krw_bn is not None:
        print(
            f"\nmodel path: fixed+variable split — opex = {base_margin.opex_fixed_krw_bn:,.0f} bn"
            f" + {base_margin.opex_variable_pct_of_revenue:.1%} x revenue"
        )
    else:
        constant = base_margin.sga_pct_of_revenue + base_margin.rnd_pct_of_revenue
        print(f"\nmodel path: constant ratio — opex = {constant:.1%} x revenue (sga + rnd)")

    # Shape test: constant-% (CV of ratio ~ 0) vs sticky-absolute (CV of KRW ~ 0).
    cv_pct = statistics.stdev(opex_pct) / mean_pct
    cv_abs = statistics.stdev(opex_abs) / statistics.fmean(opex_abs)
    corr = statistics.correlation(revenues, opex_pct)

    # Least-squares opex = a + b * revenue: intercept share says how "fixed" opex is.
    slope, intercept = statistics.linear_regression(revenues, opex_abs)
    fitted_mean = intercept + slope * statistics.fmean(revenues)
    intercept_share = intercept / fitted_mean if fitted_mean else float("nan")

    print(
        f"shape: CV(opex %rev) = {cv_pct:.3f}  vs  CV(opex KRW bn) = {cv_abs:.3f}"
        f"  -> {'ratio more stable (supports %-of-revenue)' if cv_pct < cv_abs else 'absolute more stable (supports sticky/fixed opex)'}"
    )
    print(f"corr(revenue, opex %rev) = {corr:+.3f}  (strongly negative -> operating leverage)")
    print(
        f"realized fit: opex = {intercept:,.0f} + {slope:.4f} x revenue"
        f"  (intercept = {intercept_share:.0%} of mean opex -> fixed-cost share)"
    )
    print(
        f"\nlevel gap: model mean {mean_model_pct:.2%} vs realized mean {mean_pct:.2%}"
        f" ({(mean_model_pct - mean_pct) * 100:+.2f}pp)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
