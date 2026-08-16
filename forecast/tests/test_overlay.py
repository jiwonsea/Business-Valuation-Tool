"""Overlay schema: lookahead guard + EPS-path isolation.

PLAN_tax_finance_overlay.md §3.2 / §4: overlays are date-tagged macro/timing/risk
factors that feed the valuation/risk layer, NEVER the EPS point estimate. Two
guarantees are pinned here:

  1. Lookahead guard — an overlay claiming to inform a target quarter but dated on
     or after that quarter's period_end is hindsight; it must be rejected.
  2. EPS isolation — adding overlays (and the risk_band block) to the profile must
     leave the forward base-scenario EPS and revenue bit-identical. The forward
     chain takes only scenario/anchor/share inputs; overlays live in a separate
     profile key and must never leak in.

Deterministic: uses tests/fixtures/ (committed), no network.
"""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest
import yaml

from pipeline.dart_fetcher import extract_quarterly_actual
from pipeline.ir_loader import load_profile
from schemas.models import Overlay

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


# --- Lookahead guard ------------------------------------------------------- #

def test_overlay_rejects_as_of_on_or_after_period_end() -> None:
    """as_of_date >= target period_end is hindsight -> reject (ValueError)."""
    # 2026Q3 period_end = 2026-09-30. Exactly on the end is already lookahead.
    with pytest.raises(ValueError):
        Overlay(
            as_of_date=date(2026, 9, 30),
            target_period_label="2026Q3",
            driver="USD/KRW FX valuation loss",
            direction="risk_down",
            magnitude=0.03,
        )
    # After the end is also rejected.
    with pytest.raises(ValueError):
        Overlay(
            as_of_date=date(2026, 10, 1),
            target_period_label="2026Q3",
            driver="UST 10Y spike",
            direction="risk_down",
            magnitude=0.05,
        )


def test_overlay_accepts_as_of_before_period_end() -> None:
    """Known before the target period closes -> a legitimate forward overlay."""
    overlay = Overlay(
        as_of_date=date(2026, 5, 15),
        target_period_label="2026Q3",
        driver="USD/KRW FX valuation loss",
        direction="risk_down",
        magnitude=0.03,
        confidence=0.4,
    )
    assert overlay.target_period_label == "2026Q3"
    assert overlay.confidence == 0.4


def test_overlay_quarter_period_ends_are_calendar_quarter_ends() -> None:
    """period_end helper maps YYYYQN to the calendar quarter end (FY-Dec issuer)."""
    # Each is accepted only when as_of_date is strictly before the listed end.
    for label, last_day in (
        ("2026Q1", date(2026, 3, 31)),
        ("2026Q2", date(2026, 6, 30)),
        ("2026Q3", date(2026, 9, 30)),
        ("2026Q4", date(2026, 12, 31)),
    ):
        with pytest.raises(ValueError):
            Overlay(
                as_of_date=last_day,
                target_period_label=label,
                driver="x",
                direction="neutral",
                magnitude=0.0,
            )
        ok = Overlay(
            as_of_date=date(last_day.year, last_day.month, last_day.day - 1),
            target_period_label=label,
            driver="x",
            direction="neutral",
            magnitude=0.0,
        )
        assert ok.target_period_label == label


# --- EPS-path isolation ---------------------------------------------------- #

def _base_forward(profile: dict) -> tuple[list[float | None], list[float]]:
    """Forward base-scenario EPS + revenue from the committed DART fixtures.

    Mirrors the cli.py forward loop for the base scenario only — overlays are NOT
    an input to any of these functions, which is exactly the property under test.
    """
    from engine.eps_bridge import project_eps
    from engine.margin_model import project_margins
    from engine.segment_revenue import build_margin_carryover, project_quarterly_revenue
    from engine.tax_finance import apply_taxes_and_finance
    from schemas.models import MarginBaseline, QuarterlyActual

    split = profile["segment_revenue_split"]
    import json

    q3_raw = json.load(open(FIXTURES / "sk_hynix_2024q3_dart.json", encoding="utf-8"))
    q4_raw = json.load(open(FIXTURES / "sk_hynix_2024q4_dart.json", encoding="utf-8"))
    actuals = [
        QuarterlyActual.model_validate(
            extract_quarterly_actual(q3_raw, "2024Q3", segment_revenue_split=split)
        ),
        QuarterlyActual.model_validate(
            extract_quarterly_actual(
                q4_raw, "2024Q4", q3_raw_dart=q3_raw, segment_revenue_split=split
            )
        ),
    ]
    seed = sorted(actuals, key=lambda a: a.period_end)[-1]
    baseline = MarginBaseline(
        gp_margin=seed.gross_profit / seed.revenue_total,
        op_margin=seed.operating_profit / seed.revenue_total,
        np_margin=seed.net_profit / seed.revenue_total,
        dram_blended_asp=next(s.revenue for s in seed.revenue_by_segment if s.segment_id == "dram"),
        nand_blended_asp=next(s.revenue for s in seed.revenue_by_segment if s.segment_id == "nand"),
    )
    carry = build_margin_carryover(profile["historical_drivers"], "2025Q4")
    segment, margin, finance = profile["scenarios"]["base"]
    n_quarters = int(profile["forecast_window"]["n_quarters"])
    chain = project_quarterly_revenue(seed, baseline, segment, n_quarters, carry)
    chain = project_margins(chain, baseline, margin, profile["anchor_margins"])
    chain = apply_taxes_and_finance(chain, finance)
    chain = project_eps(chain, profile["shares"])
    return [q.eps_basic for q in chain], [q.revenue_total for q in chain]


def test_overlays_do_not_perturb_forward_eps_or_revenue(tmp_path) -> None:
    """Forward base EPS/revenue are bit-identical with vs without the overlay block.

    If a future change wired overlay magnitude into the EPS path, stripping the
    overlays would move EPS and this assertion would fail.
    """
    full = load_profile(REPO_ROOT / "profiles" / "sk_hynix.yaml")
    assert full.get("overlays"), "profile should carry parsed overlays (draft)"
    eps_full, rev_full = _base_forward(full)

    stripped_raw = copy.deepcopy(full["raw"])
    stripped_raw.pop("overlays", None)
    stripped_raw.pop("risk_band", None)
    stripped_path = tmp_path / "sk_hynix_no_overlays.yaml"
    stripped_path.write_text(
        yaml.safe_dump(stripped_raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    stripped = load_profile(stripped_path)
    assert not stripped.get("overlays")
    eps_stripped, rev_stripped = _base_forward(stripped)

    assert eps_full == eps_stripped
    assert rev_full == rev_stripped
