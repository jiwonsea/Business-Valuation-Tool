"""Generic four-lever postmortem tests."""

import pytest

from engine.generic_postmortem import (
    attribute_eps_error_four_levers,
    score_generic_release,
)
from engine.skill_metrics import SkillRow, compute_skill
from schemas.postmortem import FrozenPoint, GenericActualRelease


def _actual() -> GenericActualRelease:
    return GenericActualRelease.model_validate(
        {
            "quarter_label": "2026Q2",
            "provenance": {"source": "synthetic golden", "as_of": "2026-07-23"},
            "revenue_total": 120.0,
            "gaap_eps_diluted": 1.05,
            "diluted_shares": 12_000_000.0,
            "operating_income": 18.0,
            "net_income": 12.6,
            "automotive_revenue": 80.0,
            "energy_revenue": 25.0,
            "services_revenue": 15.0,
            "automotive_gross_margin_ex_credits": 0.20,
            "regulatory_credits": 5.0,
            "other_income_expense": -2.0,
            "non_gaap_eps": 1.20,
            "stock_based_compensation": 1.2,
        }
    )


def _forecast() -> FrozenPoint:
    return FrozenPoint(
        revenue_total=100.0,
        operating_income=20.0,
        net_income=15.0,
        eps_diluted=1.5,
        diluted_shares=10_000_000.0,
    )


def test_four_lever_attribution_is_complete_without_fifth_lever() -> None:
    result = attribute_eps_error_four_levers(_forecast(), _actual(), 1_000_000.0)

    assert result.revenue == pytest.approx(-0.30)
    assert result.operating_margin == pytest.approx(0.45)
    assert result.op_to_ni == pytest.approx(0.09)
    assert result.share_count == pytest.approx(0.21)
    assert result.eps_error_total == pytest.approx(0.45)
    assert result.revenue + result.operating_margin + result.op_to_ni + result.share_count == pytest.approx(result.eps_error_total)
    assert result.residual == pytest.approx(0.0, abs=1e-12)
    assert set(result.model_dump()) == {
        "eps_error_total", "revenue", "operating_margin", "op_to_ni", "share_count", "residual"
    }


def test_score_reuses_compute_skill_contract() -> None:
    actual = _actual()
    result = score_generic_release(
        actual=actual,
        base=_forecast(),
        weighted=_forecast(),
        prior_revenue=90.0,
        prior_eps=0.90,
        consensus_eps=1.10,
        unit_scale=1_000_000.0,
        segment_forecasts={"automotive": 75.0},
        include_tesla=True,
    )
    expected = compute_skill(
        [SkillRow("2026Q2", 120.0, 100.0, 90.0, 1.05, 1.5, 0.90)],
        consensus_history={"2026Q2": {"estimate": 1.10}},
    )

    assert result.skill == expected
    assert result.skill.mase_revenue == pytest.approx(2 / 3)
    assert result.skill.surprise_direction_accuracy == 0.0
    assert result.tesla is not None
    assert result.tesla.automotive_gross_profit_ex_credits == pytest.approx(15.0)
    assert result.tesla.regulatory_credits == 5.0
    assert result.tesla.automotive_gross_profit_including_credits == pytest.approx(20.0)


def test_incomplete_actual_fails_closed_for_scoring() -> None:
    actual = GenericActualRelease.model_validate(
        {
            "quarter_label": "2026Q2",
            "provenance": {"source": "IR", "as_of": "2026-07-23"},
        }
    )
    with pytest.raises(ValueError, match="revenue_total.*gaap_eps_diluted"):
        attribute_eps_error_four_levers(_forecast(), actual, 1_000_000.0)


def test_inconsistent_actual_eps_fails_before_attribution() -> None:
    actual = _actual().model_copy(update={"gaap_eps_diluted": 1.20})

    with pytest.raises(ValueError, match="inconsistent with net_income"):
        attribute_eps_error_four_levers(_forecast(), actual, 1_000_000.0)
