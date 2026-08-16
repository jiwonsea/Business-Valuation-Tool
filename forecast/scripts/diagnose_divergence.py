"""Divergence diagnosis (workstream ①, PLAN_backtest_honesty.md).

Runs the same no-look-ahead backtest projection as cli.py, then attributes each
quarter's model-vs-actual EPS error to {revenue, gross margin, opex, tax/finance,
shares} via engine.attribution. Read-only: changes no forecast numbers.

Usage:
    python scripts/diagnose_divergence.py --company sk_hynix
    python scripts/diagnose_divergence.py --company sk_hynix --no-cache   # live DART

Offline (sandbox): cache hits in reports/.cache/ need no network, but the DART
client still requires DART_API_KEY to be set to any non-empty value.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.attribution import attribute_eps_error  # noqa: E402
from engine.backtest import implied_basic_shares, iter_backtest_forecasts  # noqa: E402
from pipeline.dart_fetcher import fetch_quarterly_actuals_series  # noqa: E402
from pipeline.ir_loader import load_profile  # noqa: E402


def _quarter_sort_key(label: str) -> tuple[int, int]:
    year_text, quarter_text = label.split("Q", 1)
    return int(year_text), int(quarter_text)


def _pct(value: float) -> str:
    return f"{value * 100:+.1f}%"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EPS-error driver attribution")
    parser.add_argument("--company", required=True, help="Profile name (without .yaml)")
    parser.add_argument("--no-cache", action="store_true", help="Force live DART (default: cache)")
    args = parser.parse_args(argv)

    profile_path = REPO_ROOT / "profiles" / f"{args.company}.yaml"
    profile = load_profile(profile_path)

    backtest_window = profile["backtest_window"]
    end_quarter = str(backtest_window["end_quarter"])
    lookback_quarters = int(backtest_window["lookback_quarters"])
    start_year = int(str(backtest_window["start_quarter"])[:4]) - 1
    end_year = int(end_quarter[:4])

    actuals = fetch_quarterly_actuals_series(
        profile["company"].corp_code_dart,
        start_year,
        end_year,
        profile["segment_revenue_split"],
        use_cache=not args.no_cache,
        skip_unavailable=True,  # offline diagnostics: unfiled/uncached future quarters warn+skip
    )
    end_key = _quarter_sort_key(end_quarter)
    history = [a for a in actuals if _quarter_sort_key(a.quarter_label) <= end_key]

    base_assumptions, base_margin, base_finance = profile["scenarios"]["base"]
    shares = profile["shares"]

    rows = list(
        iter_backtest_forecasts(
            history,
            base_assumptions,
            base_margin,
            profile["anchor_margins"],
            base_finance,
            shares,
            profile["historical_drivers"],
            lookback_quarters,
        )
    )

    header = (
        f"{'Quarter':<8} {'EPS err':>9} | {'revenue':>9} {'gross-m':>9} "
        f"{'opex':>9} {'tax/fin':>9} {'shares':>9}  (contribution to EPS err)"
    )
    print(header)
    print("-" * len(header))

    sums = {"revenue": 0.0, "gross_margin": 0.0, "opex": 0.0, "tax_finance": 0.0, "shares": 0.0}
    n = 0
    for _seed, target, forecast in rows:
        # Mirror the backtest EPS bridge: seed-implied share count, profile fallback.
        model_shares = implied_basic_shares(_seed) or shares.weighted_avg_basic
        attr = attribute_eps_error(target, forecast, model_shares)
        print(
            f"{attr.quarter_label:<8} {_pct(attr.eps_error_total):>9} | "
            f"{_pct(attr.contrib_revenue):>9} {_pct(attr.contrib_gross_margin):>9} "
            f"{_pct(attr.contrib_opex):>9} {_pct(attr.contrib_tax_finance):>9} "
            f"{_pct(attr.contrib_shares):>9}"
        )
        sums["revenue"] += attr.contrib_revenue
        sums["gross_margin"] += attr.contrib_gross_margin
        sums["opex"] += attr.contrib_opex
        sums["tax_finance"] += attr.contrib_tax_finance
        sums["shares"] += attr.contrib_shares
        n += 1

    if n:
        print("-" * len(header))
        print(
            f"{'MEAN':<8} {'':>9} | "
            f"{_pct(sums['revenue'] / n):>9} {_pct(sums['gross_margin'] / n):>9} "
            f"{_pct(sums['opex'] / n):>9} {_pct(sums['tax_finance'] / n):>9} "
            f"{_pct(sums['shares'] / n):>9}"
        )
        # Share-count sanity line (model = seed-implied, vs the target quarter's own implied).
        last_seed, last_target, last_forecast = rows[-1]
        last_shares = implied_basic_shares(last_seed) or shares.weighted_avg_basic
        last = attribute_eps_error(last_target, last_forecast, last_shares)
        print(
            f"\nshare count (latest quarter): model seed-implied {last.model_basic_shares:,} vs "
            f"target implied {last.actual_implied_basic_shares:,.0f} (profile forward count {shares.weighted_avg_basic:,})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
