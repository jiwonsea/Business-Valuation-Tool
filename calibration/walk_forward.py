"""Walk-forward cross-validation harness for sc.prob calibration.

Splits records by ``analysis_date`` into expanding-window train/test folds,
tunes on each train slice via :func:`search_sc_prob`, and re-evaluates the
recommendation on the held-out test slice. Aggregates per-fold MAPE so the
overfitting gap (train − test) is observable.

The module is infrastructure-only: with the current snapshot pool (mature
records arriving 2026-07 onward) ``tune_walk_forward`` returns an empty
result. Synthetic fixtures exercise the harness in tests/test_walk_forward.py.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from backtest.models import BacktestRecord

from .grid import Bucket, BucketKey
from .tuner import Recommendation, _bucket_loss, search_sc_prob

logger = logging.getLogger(__name__)

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_REPORT_DIR: Path = PROJECT_ROOT / "output" / "calibration"


@dataclass
class FoldResult:
    """Per-fold outcome of one train→test cycle."""

    fold_index: int
    train_size: int
    test_size: int
    train_mape: float | None
    test_mape: float | None
    baseline_test_mape: float | None
    recommended_probs: dict[str, float] | None
    tier: str
    notes: list[str] = field(default_factory=list)


@dataclass
class WalkForwardResult:
    """Aggregated walk-forward CV outcome over ``n_splits`` folds."""

    market: str
    sector: str
    horizon: str
    n_splits_requested: int
    n_records: int
    folds: list[FoldResult]
    mean_train_mape: float | None
    mean_test_mape: float | None
    std_test_mape: float | None
    overfitting_gap: float | None
    notes: list[str] = field(default_factory=list)


def walk_forward_splits(
    records: list[BacktestRecord],
    n_splits: int = 5,
    min_train_size: int = 10,
) -> list[tuple[list[BacktestRecord], list[BacktestRecord]]]:
    """Expanding-window walk-forward splits sorted by ``analysis_date``.

    Each split's train set contains strictly earlier records than its test set;
    the train window grows over folds while the test window stays roughly
    ``len(records) // (n_splits + 1)``.

    Returns ``[]`` when ``len(records) < min_train_size + n_splits`` so callers
    can short-circuit on insufficient data.
    """
    if n_splits < 1:
        return []
    if len(records) < min_train_size + n_splits:
        return []

    ordered = sorted(records, key=lambda r: r.analysis_date)
    n = len(ordered)

    fold_size = n // (n_splits + 1)
    if fold_size < 1:
        return []

    splits: list[tuple[list[BacktestRecord], list[BacktestRecord]]] = []
    for i in range(n_splits):
        train_end = n - (n_splits - i) * fold_size
        test_end = train_end + fold_size
        if train_end < min_train_size:
            continue
        train = ordered[:train_end]
        test = ordered[train_end:test_end]
        if not train or not test:
            continue
        splits.append((train, test))
    return splits


def _infer_market(records: list[BacktestRecord]) -> str:
    markets = {r.market for r in records}
    return next(iter(markets)) if len(markets) == 1 else "mixed"


def _infer_sector(records: list[BacktestRecord]) -> str:
    sectors = {r.primary_method or "unknown" for r in records}
    return next(iter(sectors)) if len(sectors) == 1 else "mixed"


def _evaluate_on_test(
    test_records: list[BacktestRecord],
    rec: Recommendation,
    horizon: str,
) -> tuple[float | None, float | None]:
    """Return (test_mape under recommended, test_mape under baseline)."""
    baseline_mape, _ = _bucket_loss(test_records, rec.baseline, horizon)
    if rec.recommended is None:
        return None, baseline_mape
    test_mape, _ = _bucket_loss(test_records, rec.recommended, horizon)
    return test_mape, baseline_mape


def tune_walk_forward(
    records: list[BacktestRecord],
    horizon: str = "t6m",
    n_splits: int = 5,
    min_train_size: int = 10,
    market: str | None = None,
    sector: str | None = None,
) -> WalkForwardResult:
    """Run :func:`search_sc_prob` on each fold's train, evaluate on the test.

    Aggregates per-fold train/test MAPE into mean/std and an overfitting gap
    (mean train − mean test). Folds where the tuner suppresses a
    recommendation (insufficient tier or below the MAPE-improvement gate)
    contribute baseline test MAPE only.
    """
    if records:
        market_label = market or _infer_market(records)
        sector_label = sector or _infer_sector(records)
    else:
        market_label = market or "unknown"
        sector_label = sector or "unknown"
    splits = walk_forward_splits(records, n_splits=n_splits, min_train_size=min_train_size)

    if not splits:
        return WalkForwardResult(
            market=market_label,
            sector=sector_label,
            horizon=horizon,
            n_splits_requested=n_splits,
            n_records=len(records),
            folds=[],
            mean_train_mape=None,
            mean_test_mape=None,
            std_test_mape=None,
            overfitting_gap=None,
            notes=[
                f"insufficient data: {len(records)} records < "
                f"min_train_size({min_train_size}) + n_splits({n_splits})"
            ],
        )

    fold_results: list[FoldResult] = []
    for idx, (train, test) in enumerate(splits):
        bucket = Bucket(
            key=BucketKey(market=market_label, sector=sector_label, horizon=horizon),
            records=list(train),
        )
        rec = search_sc_prob(bucket)
        test_mape, baseline_test_mape = _evaluate_on_test(list(test), rec, horizon)
        fold_results.append(
            FoldResult(
                fold_index=idx,
                train_size=len(train),
                test_size=len(test),
                train_mape=rec.recommended_mape if rec.recommended else rec.baseline_mape,
                test_mape=test_mape,
                baseline_test_mape=baseline_test_mape,
                recommended_probs=rec.recommended,
                tier=rec.tier,
                notes=list(rec.notes),
            )
        )

    train_values = [f.train_mape for f in fold_results if f.train_mape is not None]
    # Per docstring, suppressed folds (no recommendation) contribute the
    # baseline test MAPE to the aggregate rather than being dropped. Excluding
    # them silently biased mean_test_mape / overfitting_gap toward only the
    # folds that actually emitted a recommendation.
    test_values: list[float] = []
    for f in fold_results:
        value = f.test_mape if f.test_mape is not None else f.baseline_test_mape
        if value is not None:
            test_values.append(value)
    mean_train = sum(train_values) / len(train_values) if train_values else None
    mean_test = sum(test_values) / len(test_values) if test_values else None
    std_test = statistics.stdev(test_values) if len(test_values) >= 2 else None
    gap = (
        mean_test - mean_train
        if (mean_train is not None and mean_test is not None)
        else None
    )

    return WalkForwardResult(
        market=market_label,
        sector=sector_label,
        horizon=horizon,
        n_splits_requested=n_splits,
        n_records=len(records),
        folds=fold_results,
        mean_train_mape=mean_train,
        mean_test_mape=mean_test,
        std_test_mape=std_test,
        overfitting_gap=gap,
        notes=[],
    )


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _fmt_signed_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:+.2f}pp"


def _fmt_probs(probs: dict[str, float] | None) -> str:
    if probs is None:
        return "n/a"
    return f"{probs.get('bull', 0):.0f}/{probs.get('base', 0):.0f}/{probs.get('bear', 0):.0f}"


def render_report(
    result: WalkForwardResult,
    *,
    report_date: date | None = None,
) -> str:
    """Render a :class:`WalkForwardResult` into a markdown document.

    Includes the bucket header, aggregate train/test MAPE + overfitting gap,
    and a per-fold table. When ``result.folds`` is empty (insufficient data),
    only the bucket header and notes are emitted so the file is still useful
    as a "harness ready" placeholder before mature records arrive.
    """
    report_date = report_date or date.today()
    lines: list[str] = []
    lines.append(
        f"# Walk-Forward CV Report -- {report_date.isoformat()} "
        f"({result.market}/{result.sector}/{result.horizon})"
    )
    lines.append("")
    lines.append(
        f"Records: **{result.n_records}**, "
        f"folds: **{len(result.folds)}** "
        f"(requested {result.n_splits_requested})"
    )
    lines.append("")

    if not result.folds:
        notes = "; ".join(result.notes) if result.notes else "no folds produced"
        lines.append(f"_No folds were produced: {notes}._")
        lines.append("")
        lines.append(
            "Re-run after additional mature records accrue (first t3m batch "
            "expected 2026-07)."
        )
        return "\n".join(lines) + "\n"

    lines.append("## Aggregate")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Mean train MAPE | {_fmt_pct(result.mean_train_mape)} |")
    lines.append(f"| Mean test MAPE  | {_fmt_pct(result.mean_test_mape)} |")
    lines.append(f"| Test MAPE std   | {_fmt_pct(result.std_test_mape)} |")
    lines.append(f"| Overfit gap (test - train) | {_fmt_signed_pp(result.overfitting_gap)} |")
    lines.append("")

    lines.append("## Per-fold")
    lines.append("")
    lines.append(
        "| Fold | Train N | Test N | Tier | Recommended (bull/base/bear) | "
        "Train MAPE | Test MAPE | Baseline Test MAPE | Notes |"
    )
    lines.append("|---:|---:|---:|---|---|---|---|---|---|")
    for fold in result.folds:
        notes = "; ".join(fold.notes) if fold.notes else ""
        lines.append(
            f"| {fold.fold_index} | {fold.train_size} | {fold.test_size} | "
            f"{fold.tier} | {_fmt_probs(fold.recommended_probs)} | "
            f"{_fmt_pct(fold.train_mape)} | {_fmt_pct(fold.test_mape)} | "
            f"{_fmt_pct(fold.baseline_test_mape)} | {notes} |"
        )
    lines.append("")
    lines.append("## How to read")
    lines.append(
        "- A positive **overfit gap** means recommended probs underperform on "
        "held-out folds vs. their train slice -- treat the recommendation as "
        "tentative until the gap narrows.\n"
        "- **Baseline Test MAPE** is the held-out MAPE under each fold's "
        "current/baseline prob mix; a recommendation is only worth promoting "
        "when Test MAPE < Baseline Test MAPE consistently across folds.\n"
        "- Folds with `tier=insufficient` contribute baseline test MAPE only "
        "(the tuner suppresses a recommendation)."
    )
    return "\n".join(lines) + "\n"


def write_report(
    result: WalkForwardResult,
    *,
    output_dir: Path | None = None,
    report_date: date | None = None,
) -> Path:
    """Render and write the walk-forward report to ``output/calibration/``.

    Returns the written path. Output directory is created if missing.
    """
    report_date = report_date or date.today()
    output_dir = output_dir or DEFAULT_REPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    text = render_report(result, report_date=report_date)
    out_path = output_dir / f"walk_forward_{report_date.isoformat()}.md"
    out_path.write_text(text, encoding="utf-8")
    logger.info(
        "Wrote walk-forward report: %s (%d folds)", out_path, len(result.folds)
    )
    return out_path


def format_summary(result: WalkForwardResult) -> str:
    """Single-paragraph human summary suitable for CLI output."""
    if not result.folds:
        notes = "; ".join(result.notes) if result.notes else "no folds"
        return (
            f"[WalkForward {result.market}/{result.sector}/{result.horizon}] "
            f"n={result.n_records}, folds=0 -- {notes}"
        )
    parts = [
        f"[WalkForward {result.market}/{result.sector}/{result.horizon}]",
        f"n={result.n_records}, folds={len(result.folds)}",
    ]
    if result.mean_train_mape is not None:
        parts.append(f"train MAPE={result.mean_train_mape * 100:.2f}%")
    if result.mean_test_mape is not None:
        parts.append(f"test MAPE={result.mean_test_mape * 100:.2f}%")
    if result.std_test_mape is not None:
        parts.append(f"+/-{result.std_test_mape * 100:.2f}pp")
    if result.overfitting_gap is not None:
        parts.append(f"gap={result.overfitting_gap * 100:+.2f}pp")
    return " ".join(parts)


def main() -> None:
    """Entry point for ``python -m calibration.walk_forward``."""
    import argparse
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Walk-forward calibration harness")
    parser.add_argument("--horizon", default="t6m", choices=("t3m", "t6m", "t12m"))
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--min-age-days", type=int, default=90)
    parser.add_argument("--min-train-size", type=int, default=10)
    parser.add_argument(
        "--no-report", action="store_true",
        help="skip writing output/calibration/walk_forward_<date>.md",
    )
    args = parser.parse_args()

    from backtest.dataset import build_backtest_dataset

    records = build_backtest_dataset(min_age_days=args.min_age_days)
    listed = [r for r in records if r.is_listed]
    if not listed:
        print(
            f"[WalkForward] Insufficient data: {len(records)} records after "
            f"min_age_days={args.min_age_days} filter."
        )
        print(
            "[WalkForward] Harness ready -- rerun after 2026-07 (first t3m mature records)."
        )
        if not args.no_report:
            empty = WalkForwardResult(
                market="unknown", sector="unknown", horizon=args.horizon,
                n_splits_requested=args.n_splits, n_records=len(records), folds=[],
                mean_train_mape=None, mean_test_mape=None, std_test_mape=None,
                overfitting_gap=None,
                notes=[
                    f"no listed records after min_age_days={args.min_age_days} filter"
                ],
            )
            out = write_report(empty)
            print(f"[WalkForward] Placeholder report -> {out}")
        return

    result = tune_walk_forward(
        listed, horizon=args.horizon, n_splits=args.n_splits,
        min_train_size=args.min_train_size,
    )
    print(format_summary(result))
    if not args.no_report:
        out = write_report(result)
        print(f"[WalkForward] Report -> {out}")
    for fold in result.folds:
        train_mape = (
            f"{fold.train_mape * 100:.2f}%" if fold.train_mape is not None else "n/a"
        )
        test_mape = (
            f"{fold.test_mape * 100:.2f}%" if fold.test_mape is not None else "n/a"
        )
        print(
            f"  fold {fold.fold_index}: train={fold.train_size} "
            f"test={fold.test_size} tier={fold.tier} "
            f"train_mape={train_mape} test_mape={test_mape}"
        )


if __name__ == "__main__":
    main()
