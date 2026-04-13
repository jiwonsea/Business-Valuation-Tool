"""Markdown report writer for calibration recommendations.

Output: ``output/calibration/YYYY-MM-DD.md`` (filesystem location, not the
Python ``output/`` package). The package directory at the project root and
the report directory under it coexist because adding subdirectories beneath
a Python package does not affect imports.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Iterable

from backtest.models import BacktestRecord

from .grid import bucket_records
from .tuner import Recommendation, search_sc_prob

logger = logging.getLogger(__name__)

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR: Path = PROJECT_ROOT / "output" / "calibration"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _fmt_probs(probs: dict[str, float] | None) -> str:
    if probs is None:
        return "—"
    return f"{probs.get('bull', 0):.0f}/{probs.get('base', 0):.0f}/{probs.get('bear', 0):.0f}"


def render_report(
    recommendations: list[Recommendation],
    *,
    report_date: date | None = None,
) -> str:
    """Render Recommendations into a single markdown document."""
    report_date = report_date or date.today()
    tier_count = {"stable": 0, "preliminary": 0, "insufficient": 0}
    for r in recommendations:
        tier_count[r.tier] = tier_count.get(r.tier, 0) + 1

    lines: list[str] = []
    lines.append(f"# Calibration Report — {report_date.isoformat()}")
    lines.append("")
    lines.append(
        "Sector key uses `BacktestRecord.primary_method` as a proxy. "
        "Probabilities are bull/base/bear roles assigned by post_dlom value rank "
        "within each record. Recommendations are advisory; promote into "
        "`profiles/*.yaml` manually after review."
    )
    lines.append("")
    lines.append(
        f"Total buckets: **{len(recommendations)}** "
        f"(stable: {tier_count['stable']}, "
        f"preliminary: {tier_count['preliminary']}, "
        f"insufficient: {tier_count['insufficient']})"
    )
    lines.append("")
    lines.append(
        "| Market | Sector | Horizon | N | Tier | Baseline (bull/base/bear) | "
        "Recommended | MAPE base→rec | Coverage base→rec | Notes |"
    )
    lines.append("|---|---|---|---:|---|---|---|---|---|---|")

    ordered = sorted(recommendations, key=lambda r: r.bucket_key)
    for rec in ordered:
        market, sector, horizon = rec.bucket_key
        notes = "; ".join(rec.notes) if rec.notes else ""
        lines.append(
            f"| {market} | {sector} | {horizon} | {rec.n} | {rec.tier} | "
            f"{_fmt_probs(rec.baseline)} | {_fmt_probs(rec.recommended)} | "
            f"{_fmt_pct(rec.baseline_mape)} → {_fmt_pct(rec.recommended_mape)} | "
            f"{_fmt_pct(rec.baseline_coverage)} → {_fmt_pct(rec.recommended_coverage)} | "
            f"{notes} |"
        )

    lines.append("")
    lines.append("## How to apply")
    lines.append(
        "1. Identify profiles in each bucket (market + primary_method).\n"
        "2. Adjust scenario `prob` values toward the recommended bull/base/bear mix.\n"
        "3. Keep `sum(prob) = 100` and each `prob ∈ [5, 90]`.\n"
        "4. Re-run backtest after the next quarter to verify MAPE improvement."
    )
    return "\n".join(lines) + "\n"


def emit_yaml_diff(
    records: Iterable[BacktestRecord],
    *,
    output_dir: Path | None = None,
    report_date: date | None = None,
) -> Path:
    """Build buckets, search optimal probs, write markdown report. Returns path."""
    report_date = report_date or date.today()
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    records_list = list(records)
    buckets = bucket_records(records_list, today=report_date)
    recommendations = [search_sc_prob(b) for b in buckets.values()]
    text = render_report(recommendations, report_date=report_date)

    out_path = output_dir / f"{report_date.isoformat()}.md"
    out_path.write_text(text, encoding="utf-8")
    logger.info(
        "Wrote calibration report: %s (%d buckets)", out_path, len(recommendations)
    )
    return out_path


def main() -> None:
    """Entry point for ``python -m calibration.report``."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    from backtest.dataset import build_backtest_dataset

    records = build_backtest_dataset()
    if not records:
        logger.warning("No backtest records available — empty report will be written")
    out = emit_yaml_diff(records)
    print(f"Calibration report → {out}")


if __name__ == "__main__":
    main()
