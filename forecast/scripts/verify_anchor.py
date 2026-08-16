"""Reproduce provenance anchors without invoking CLI or network services.

The relative tolerance of 1e-9 is intentional: it absorbs environment-specific
last-ULP differences documented by the dual canonical hashes in
``verify_9q_sha.py``. Do not tighten this gate to exact equality.

Never overwrite an ``expected`` value to match current output. When an anchor
changes intentionally, add ``superseded_by`` to the old entry and append a new
entry. In-place replacement is forbidden because it destroys the audit trail.

Usage: python scripts/verify_anchor.py
Exit code 0 = every active anchor and the canonical 9Q SHA passed.
Exit code 1 = anchor provenance, offline reproduction, or 9Q SHA failed.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

REL_TOLERANCE = 1e-9


class ExpectedAnchor(BaseModel):
    """Five forecast values protected by the G1 gate."""

    model_config = ConfigDict(extra="forbid")

    base_revenue: float
    weighted_revenue: float
    weighted_operating_profit: float
    weighted_net_income: float
    weighted_eps: float


class SupersededBy(BaseModel):
    """Explicit reason an historical anchor is no longer reproduced."""

    model_config = ConfigDict(extra="forbid")

    at_commit: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    date: date


class AnchorEntry(BaseModel):
    """A forecast anchor plus the provenance required to audit it."""

    model_config = ConfigDict(extra="forbid")

    company: str = Field(..., min_length=1)
    period: str = Field(..., pattern=r"^\d{4}Q[1-4]$")
    anchor_date: date
    expected: ExpectedAnchor
    source_artifact: str = Field(..., min_length=1)
    driving_profile_commit: str = Field(..., min_length=1)
    measured_at: date
    measured_env: str = Field(..., min_length=1)
    verified_at_commit: str = Field(..., min_length=1)
    superseded_by: SupersededBy | None = None


# These values were measured from the immutable 2026Q2 scoring anchor. A new
# intentional anchor must be appended; the existing expected values stay intact.
ANCHOR_REGISTRY_DATA: tuple[dict[str, Any], ...] = (
    {
        "company": "sk_hynix",
        "period": "2026Q2",
        "anchor_date": "2026-07-10",
        "expected": {
            "base_revenue": 79070.26666360501,
            "weighted_revenue": 77212.75104432012,
            "weighted_operating_profit": 60426.28566423651,
            "weighted_net_income": 49824.89024685436,
            "weighted_eps": 70607.8551553665,
        },
        "source_artifact": "reports/sk_hynix_20260710.xlsx",
        "driving_profile_commit": "4ebeb7c",
        "measured_at": "2026-08-02",
        "measured_env": "CPython 3.14.3 / win32",
        "verified_at_commit": "23b1d97",
    },
)


def load_registry(data: tuple[dict[str, Any], ...] = ANCHOR_REGISTRY_DATA) -> list[AnchorEntry]:
    """Validate all registry entries, failing closed on missing provenance."""

    return [AnchorEntry.model_validate(item) for item in data]


def _previous_quarter_label(label: str) -> str:
    year = int(label[:4])
    quarter = int(label[-1])
    if quarter == 1:
        return f"{year - 1}Q4"
    return f"{year}Q{quarter - 1}"


def reproduce_anchor(entry: AnchorEntry) -> dict[str, float]:
    """Run the forward chain directly from committed DART cache data."""

    import pipeline.dart_fetcher as dart_fetcher
    from engine.eps_bridge import project_eps
    from engine.margin_model import project_margins
    from engine.scenario import aggregate_quarterly_to_annual, build_scenario_tree
    from engine.segment_revenue import build_margin_carryover, project_quarterly_revenue
    from engine.tax_finance import apply_taxes_and_finance
    from pipeline.ir_loader import load_profile
    from schemas.models import MarginBaseline, ScenarioCase

    profile = load_profile(REPO / "profiles" / f"{entry.company}.yaml")
    start_year = int(str(profile["backtest_window"]["start_quarter"])[:4]) - 1
    forecast_start = str(profile["forecast_window"]["start_quarter"])
    end_year = max(
        int(str(profile["backtest_window"]["end_quarter"])[:4]),
        int(forecast_start[:4]),
    )

    def fetch_cached_only(
        corp_code: str,
        year: int,
        reprt_code: str,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        del use_cache
        cache_path = dart_fetcher.CACHE_DIR / f"dart_{corp_code}_{year}_{reprt_code}.json"
        if not cache_path.exists():
            raise RuntimeError(f"DART API error 013: no committed cache at {cache_path}")
        with open(cache_path, encoding="utf-8") as cache_file:
            return json.load(cache_file)

    with (
        patch("pipeline.dart_fetcher.fetch_quarterly_financials", side_effect=fetch_cached_only),
        patch(
            "pipeline.dart_fetcher.httpx.get",
            side_effect=RuntimeError("network access forbidden by verify_anchor.py"),
        ) as guarded_get,
    ):
        actuals = dart_fetcher.fetch_quarterly_actuals_series(
            profile["company"].corp_code_dart,
            start_year,
            end_year,
            profile["segment_revenue_split"],
            use_cache=True,
            skip_unavailable=True,
        )
    if guarded_get.call_count:
        raise RuntimeError(
            f"offline invariant failed: attempted {guarded_get.call_count} network call(s)"
        )

    seed_label = _previous_quarter_label(forecast_start)
    try:
        prior_actual = next(actual for actual in actuals if actual.quarter_label == seed_label)
    except StopIteration as exc:
        available = ", ".join(actual.quarter_label for actual in actuals) or "none"
        raise ValueError(
            f"missing real DART actual for seed quarter {seed_label}; available: {available}"
        ) from exc

    baseline = MarginBaseline(
        gp_margin=prior_actual.gross_profit / prior_actual.revenue_total,
        op_margin=prior_actual.operating_profit / prior_actual.revenue_total,
        np_margin=prior_actual.net_profit / prior_actual.revenue_total,
        dram_blended_asp=next(
            segment.revenue
            for segment in prior_actual.revenue_by_segment
            if segment.segment_id == "dram"
        ),
        nand_blended_asp=next(
            segment.revenue
            for segment in prior_actual.revenue_by_segment
            if segment.segment_id == "nand"
        ),
    )
    margin_carryover = build_margin_carryover(profile["historical_drivers"], seed_label)
    cases: dict[str, ScenarioCase] = {}
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
        quarterly = project_margins(
            quarterly,
            baseline,
            margin_assumptions,
            profile["anchor_margins"],
        )
        quarterly = apply_taxes_and_finance(quarterly, finance_assumptions)
        quarterly = project_eps(quarterly, profile["shares"])
        cases[name] = ScenarioCase(
            scenario=name,
            probability=getattr(profile["probabilities"], name),
            rationale=profile["rationales"][name],
            quarterly=quarterly,
            annual=aggregate_quarterly_to_annual(quarterly, name),
        )

    tree = build_scenario_tree(
        profile["company"],
        entry.anchor_date,
        cases["bear"],
        cases["base"],
        cases["bull"],
        profile["probabilities"],
    )
    base_quarter = next(q for q in tree.base.quarterly if q.quarter_label == entry.period)
    weighted = next(q for q in tree.weighted_quarterly if q.quarter_label == entry.period)
    if weighted.eps_basic is None:
        raise ValueError(f"{entry.company} {entry.period} weighted EPS is missing")
    return {
        "base_revenue": base_quarter.revenue_total,
        "weighted_revenue": weighted.revenue_total,
        "weighted_operating_profit": weighted.operating_profit,
        "weighted_net_income": weighted.net_profit,
        "weighted_eps": weighted.eps_basic,
    }


def _relative_error(expected: float, actual: float) -> float:
    if expected == 0.0:
        return abs(actual)
    return abs(actual - expected) / abs(expected)


def _print_remediation() -> None:
    print(
        "  -> 되돌리거나, reports/sk_hynix_q2_2026_scorecard.md §8 등급을 "
        "하향하고 사유를 기록할 것."
    )
    print(
        "  -> 의도된 변경이면 superseded_by 를 달고 새 엔트리를 추가할 것 "
        "(제자리 수정 금지)."
    )


def verify_entry(entry: AnchorEntry) -> bool:
    """Verify one active entry, or loudly skip an explicitly superseded one."""

    if entry.superseded_by is not None:
        superseded = entry.superseded_by
        print(
            f"SKIPPED: {entry.company} {entry.period} "
            f"(superseded at {superseded.at_commit}: {superseded.reason})"
        )
        return True

    actual = reproduce_anchor(entry)
    for field, expected in entry.expected.model_dump().items():
        got = actual[field]
        relative_error = _relative_error(expected, got)
        if relative_error > REL_TOLERANCE:
            print(
                f"FAIL: {entry.company} {entry.period} anchor drift "
                f"({field}: expected {expected!r}, got {got!r}, "
                f"relative error {relative_error:.3e})"
            )
            _print_remediation()
            return False
    print(
        f"PASS: {entry.company} {entry.period} anchor reproduced "
        f"(relative tolerance {REL_TOLERANCE:g}; network calls 0)"
    )
    return True


def main() -> int:
    """Run active anchors followed by the canonical 9Q SHA gate."""

    try:
        entries = load_registry()
        anchors_ok = all(verify_entry(entry) for entry in entries)
    except Exception as exc:
        print(f"FAIL: anchor verification could not run ({exc})")
        _print_remediation()
        return 1

    if not anchors_ok:
        return 1

    from scripts.verify_9q_sha import main as verify_9q_sha

    print("9Q SHA gate:")
    if verify_9q_sha() != 0:
        print("FAIL: canonical 9Q SHA drift")
        _print_remediation()
        return 1
    print("PASS: G1 anchor reproduction and canonical 9Q SHA")
    return 0


if __name__ == "__main__":
    sys.exit(main())
