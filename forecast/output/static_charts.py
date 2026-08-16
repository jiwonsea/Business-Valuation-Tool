"""matplotlib PNG fallback charts for MD embedding and email previews.

Same chart types as plotly_charts.py but rendered to static PNG.
Used by md_builder.render_md_report.
"""

from __future__ import annotations

from pathlib import Path

from schemas.models import BacktestResult, ScenarioTree


def save_fan_chart_png(tree: ScenarioTree, out_path: Path, dpi: int = 150) -> Path:
    """Save static fan chart PNG."""
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [q.quarter_label for q in tree.weighted_quarterly]
    plt.figure(figsize=(8, 4))
    plt.plot(labels, [q.revenue_total for q in tree.weighted_quarterly], label="Weighted")
    plt.fill_between(
        labels,
        [q.revenue_total for q in tree.bear.quarterly],
        [q.revenue_total for q in tree.bull.quarterly],
        alpha=0.2,
        label="Bear-Bull",
    )
    plt.ylabel("KRW bn")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi)
    plt.close()
    return out_path


def save_beat_miss_png(backtest: BacktestResult, out_path: Path, dpi: int = 150) -> Path:
    """Save static beat/miss bar PNG."""
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [q.quarter_label for q in backtest.quarters]
    values = [q.revenue_error_pct * 100 for q in backtest.quarters]
    plt.figure(figsize=(8, 4))
    plt.bar(labels, values)
    plt.ylabel("Revenue error %")
    plt.tight_layout()
    plt.savefig(out_path, dpi=dpi)
    plt.close()
    return out_path
