"""Synthetic calibration preview — generates BacktestRecords in-memory
(no DB), runs the calibration pipeline, and writes a preview report.

Exercises all three tiers (stable / preliminary / insufficient) so the
report layout can be inspected before real backtest data matures.

Usage:
    python scripts/seed_synthetic_calibration.py
"""

from __future__ import annotations

import random
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest.models import BacktestRecord, ScenarioSnapshot
from calibration.grid import bucket_records
from calibration.report import render_report
from calibration.tuner import search_sc_prob

SEED = 20260413
RNG = random.Random(SEED)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "output" / "calibration" / "synthetic_preview.md"

# Bucket plan: (market, method, horizon, n_records, true_probs)
# true_probs drive the simulated actual price so grid-search has signal
# to recover. Baseline scenario.prob = 25/50/25 (deliberately off).
BUCKET_PLAN = [
    ("US", "sotp",        "t12m", 40, (45, 35, 20)),  # stable
    ("US", "dcf_primary", "t12m", 35, (30, 40, 30)),  # stable
    ("US", "ddm",         "t12m", 12, (20, 60, 20)),  # preliminary
    ("KR", "sotp",        "t12m", 32, (50, 30, 20)),  # stable
    ("KR", "dcf_primary", "t6m",  18, (25, 50, 25)),  # preliminary (t6m never stable)
    ("KR", "rnpv",        "t12m",  7, (40, 40, 20)),  # insufficient
    ("JP", "sotp",        "t12m", 15, (35, 45, 20)),  # preliminary
]

BASELINE_PROBS = (25.0, 50.0, 25.0)  # bull/base/bear, held constant on records


def _make_scenarios(bull: int, base: int, bear: int) -> list[ScenarioSnapshot]:
    """Three scenarios with baseline 25/50/25 probs and ordered post_dlom values."""
    return [
        ScenarioSnapshot(
            code="A", name="Bull",
            prob=BASELINE_PROBS[0], pre_dlom=bull, post_dlom=bull,
        ),
        ScenarioSnapshot(
            code="B", name="Base",
            prob=BASELINE_PROBS[1], pre_dlom=base, post_dlom=base,
        ),
        ScenarioSnapshot(
            code="C", name="Bear",
            prob=BASELINE_PROBS[2], pre_dlom=bear, post_dlom=bear,
        ),
    ]


def _record_from_plan(
    idx: int,
    market: str,
    method: str,
    horizon: str,
    true_probs: tuple[int, int, int],
) -> BacktestRecord:
    # Anchor price levels; native currency scaled via unit_multiplier=1.
    base = 100 + RNG.uniform(-20, 20)
    spread = base * RNG.uniform(0.35, 0.55)
    bull = int(round(base + spread))
    bear = int(round(base - spread))
    base_i = int(round(base))
    scenarios = _make_scenarios(bull, base_i, bear)

    # "Realised" price = true-prob-weighted scenario value + modest noise.
    tb, tm, tr = true_probs
    true_mean = (bull * tb + base_i * tm + bear * tr) / 100.0
    noise = RNG.gauss(0.0, true_mean * 0.08)
    actual = max(1.0, true_mean + noise)

    horizon_prices = {"price_t3m": None, "price_t6m": None, "price_t12m": None}
    horizon_prices[f"price_{horizon}"] = actual

    # Stagger analysis_date so horizon_is_mature() passes comfortably.
    analysis_date = date(2024, 1, 1)

    return BacktestRecord(
        snapshot_id=f"syn-{market}-{method}-{horizon}-{idx}",
        valuation_id=f"val-{market}-{method}-{horizon}-{idx}",
        ticker=f"SYN{idx:03d}",
        market=market,
        currency="USD" if market == "US" else ("KRW" if market == "KR" else "JPY"),
        unit_multiplier=1,
        company_name=f"Synthetic {market} {method} #{idx}",
        legal_status="listed",
        analysis_date=analysis_date,
        predicted_value=base_i,
        price_at_prediction=base,
        scenarios=scenarios,
        primary_method=method,
        **horizon_prices,
    )


def build_synthetic_records() -> list[BacktestRecord]:
    records: list[BacktestRecord] = []
    for market, method, horizon, n, true_probs in BUCKET_PLAN:
        for i in range(n):
            records.append(_record_from_plan(i, market, method, horizon, true_probs))
    return records


def main() -> None:
    records = build_synthetic_records()
    report_date = date(2026, 4, 13)
    buckets = bucket_records(records, today=report_date)
    recommendations = [search_sc_prob(b) for b in buckets.values()]
    text = render_report(recommendations, report_date=report_date)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({len(recommendations)} buckets, {len(records)} records)")


if __name__ == "__main__":
    main()
