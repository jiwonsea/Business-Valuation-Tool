"""Calibration infrastructure (Phase 3).

Recommends sc.prob adjustments at the (market × sector) level using realized
prices as ground truth. Report-only: profiles/*.yaml are updated manually
by humans after reviewing output/calibration/YYYY-MM-DD.md.

Sector is proxied by ``BacktestRecord.primary_method`` because the existing
schema does not carry an explicit sector field; primary method correlates
with industry archetype (e.g. dcf_primary≈growth, multiples≈mature,
ddm/rim≈financials, sotp≈conglomerate, rnpv≈biotech).
"""

from .grid import (
    Bucket,
    BucketKey,
    bucket_records,
    classify_scenarios,
    horizon_is_mature,
)
from .tuner import (
    GRID_STEP,
    PROB_BOUNDS,
    Recommendation,
    confidence_tier,
    enumerate_prob_grid,
    predict_with_probs,
    search_sc_prob,
)
from .report import emit_yaml_diff, render_report
from .walk_forward import (
    FoldResult,
    WalkForwardResult,
    format_summary,
    tune_walk_forward,
    walk_forward_splits,
)

__all__ = [
    "Bucket",
    "BucketKey",
    "FoldResult",
    "GRID_STEP",
    "PROB_BOUNDS",
    "Recommendation",
    "WalkForwardResult",
    "bucket_records",
    "classify_scenarios",
    "confidence_tier",
    "emit_yaml_diff",
    "enumerate_prob_grid",
    "format_summary",
    "horizon_is_mature",
    "predict_with_probs",
    "render_report",
    "search_sc_prob",
    "tune_walk_forward",
    "walk_forward_splits",
]
