"""Below-OP events: lookahead guard, EPS isolation, and disclosure wording."""

from __future__ import annotations

from datetime import date

import pytest

from engine.below_op_events import build_event_adjusted_eps
from engine.risk_band import build_eps_risk_band
from output.html_builder import _below_op_event_html, _valuation_html
from output.md_builder import _below_op_event_lines, _valuation_lines
from schemas.models import BelowOpEvent, ValuationBridgeResult


def _event(**updates) -> BelowOpEvent:
    data = {
        "id": "kioxia_spc1_disposal",
        "as_of_date": date(2026, 6, 24),
        "amount_as_of": date(2026, 7, 28),
        "target_period_label": "2026Q2",
        "kind": "asset_disposal_gain",
        "amount_krw_bn": 40_000.0,
        "basis": "net_income_level",
        "probability": 0.8,
        "confidence": "estimated",
        "source": "KRX event disclosure; Meritz amount estimate",
        "note": "The event explains 91% of the NI gap; residual is about KRW 4,098bn.",
        "revision_trigger": "half-year report",
    }
    data.update(updates)
    return BelowOpEvent.model_validate(data)


def test_event_rejects_as_of_on_or_after_target_period_end() -> None:
    with pytest.raises(ValueError, match="lookahead"):
        _event(as_of_date=date(2026, 6, 30))
    with pytest.raises(ValueError, match="lookahead"):
        _event(as_of_date=date(2026, 7, 1))


def test_event_requires_declared_confidence_and_bounded_probability() -> None:
    assert _event().confidence == "estimated"
    assert _event(confidence="confirmed").confidence == "confirmed"
    with pytest.raises(ValueError):
        _event(confidence="speculative")
    with pytest.raises(ValueError):
        _event(probability=1.01)


def test_amount_date_cannot_precede_event_existence_date() -> None:
    with pytest.raises(ValueError, match="cannot precede"):
        _event(amount_as_of=date(2026, 6, 23))


def test_event_adjustment_is_separate_and_judgment_weighted() -> None:
    points = [("2026Q2", 70_000.0), ("2026Q3", 80_000.0)]
    scenario = build_event_adjusted_eps(
        points, 800_000_000, [_event()], calculation_as_of=date(2026, 7, 28)
    )

    assert points == [("2026Q2", 70_000.0), ("2026Q3", 80_000.0)]
    assert len(scenario.quarters) == 1
    quarter = scenario.quarters[0]
    assert quarter.eps_no_event == 70_000.0
    assert quarter.eps_if_realized == 120_000.0
    assert quarter.eps_expected == 110_000.0


def test_amount_lookahead_is_rejected_at_calculation_time() -> None:
    with pytest.raises(ValueError, match="amount lookahead"):
        build_event_adjusted_eps(
            [("2026Q2", 70_000.0)],
            800_000_000,
            [_event()],
            calculation_as_of=date(2026, 7, 10),
        )


def test_pre_tax_event_applies_explicit_tax_rate() -> None:
    event = _event(basis="pre_tax")
    scenario = build_event_adjusted_eps(
        [("2026Q2", 70_000.0)],
        800_000_000,
        [event],
        calculation_as_of=date(2026, 7, 28),
        effective_tax_rate=0.2,
    )
    assert scenario.quarters[0].eps_if_realized == 110_000.0
    with pytest.raises(ValueError, match="requires effective_tax_rate"):
        build_event_adjusted_eps(
            [("2026Q2", 70_000.0)],
            800_000_000,
            [event],
            calculation_as_of=date(2026, 7, 28),
        )


def test_events_do_not_change_existing_risk_band() -> None:
    points = [("2026Q2", 70_000.0)]
    before = build_eps_risk_band(points, half_width_pct=0.2279, method="mad", k=1.5)
    build_event_adjusted_eps(
        points, 800_000_000, [_event()], calculation_as_of=date(2026, 7, 28)
    )
    after = build_eps_risk_band(points, half_width_pct=0.2279, method="mad", k=1.5)
    assert before.model_dump() == after.model_dump()


def test_reports_disclose_judgment_probability_and_approximate_separation() -> None:
    scenario = build_event_adjusted_eps(
        [("2026Q2", 70_000.0)],
        800_000_000,
        [_event()],
        calculation_as_of=date(2026, 7, 28),
    )
    md = "\n".join(_below_op_event_lines(scenario))
    html = _below_op_event_html(scenario)
    for rendered in (md, html):
        assert "통계 추정치가 아닌 판단값" in rendered
        assert "근사적으로 분리" in rendered
        assert "잔여 중복은 0이 아니며 정량화하지 않는다" in rendered
        assert "기대값은 실현 불가능한 중간값" in rendered
        assert "91%" in rendered
        assert "4,098" in rendered


def test_valuation_footnote_changes_only_when_events_are_present() -> None:
    valuation = ValuationBridgeResult(
        fiscal_year=2026,
        model_eps_fy=100.0,
        consensus_eps_fy=80.0,
        eps_delta_pct=0.25,
        elasticity=1.2,
        fair_value_delta_pct=0.3,
    )
    legacy_md = "\n".join(_valuation_lines(valuation))
    legacy_html = _valuation_html(valuation)
    event_md = "\n".join(
        _valuation_lines(valuation, below_op_events_present=True)
    )
    event_html = _valuation_html(valuation, below_op_events_present=True)

    for rendered in (legacy_md, legacy_html):
        assert "이벤트 조정 EPS는 절대 주입하지 않음" not in rendered
    for rendered in (event_md, event_html):
        assert "이벤트 조정 EPS는 절대 주입하지 않음" in rendered


def test_zero_share_denominator_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        build_event_adjusted_eps(
            [("2026Q2", 1.0)],
            0,
            [_event()],
            calculation_as_of=date(2026, 7, 28),
        )
