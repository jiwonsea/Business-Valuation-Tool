"""SK hynix Q2 2026 postmortem scoring tests."""

from copy import deepcopy
import hashlib
from pathlib import Path

import pytest

from scripts.score_sk_hynix_q2_2026 import (
    ANCHOR_PATH,
    ANCHOR_SHA256,
    END_MARKER,
    START_MARKER,
    append_block,
    attribute_eps_error,
    load_actual,
    load_anchor,
    render,
)


def test_anchor_hash_and_transcribed_values() -> None:
    assert hashlib.sha256(ANCHOR_PATH.read_bytes()).hexdigest() == ANCHOR_SHA256
    anchor = load_anchor()
    assert anchor.revenue == 77212.75104432012
    assert anchor.operating_profit == 60426.28566423651
    assert anchor.net_income == 49824.89024685436
    assert anchor.eps == 70607.8551553665


def test_attribution_telescopes_and_marks_degenerate_levers() -> None:
    actual, payload = load_actual()
    result = attribute_eps_error(load_anchor(), actual, payload)

    assert abs(result.residual) < 1e-9
    assert abs(result.residual_model_eps) < 1e-9
    assert result.shares == pytest.approx(0.0, abs=1e-15)
    assert result.shares_lever_degenerate is True
    assert result.comparable_to_backtest_five_lever is False
    assert result.total == pytest.approx((load_anchor().eps - actual.eps) / actual.eps)
    assert result.total_model_eps == pytest.approx(
        (load_anchor().eps - actual.eps) / load_anchor().eps
    )

    revenue_error = (load_anchor().revenue - actual.revenue) / actual.revenue
    expected_ratio = (
        load_anchor().eps / actual.eps
        * actual.revenue / load_anchor().revenue
    )
    assert result.revenue / revenue_error == pytest.approx(expected_ratio)
    assert result.revenue / revenue_error == pytest.approx(0.545, abs=0.001)


def test_confirmed_actual_shares_are_used_without_hardcoding() -> None:
    actual, payload = load_actual()
    revised = deepcopy(payload)
    revised_shares = 700_000_000.0
    revised["actuals"]["weighted_avg_shares"]["value"] = revised_shares
    revised_actual = actual.__class__(
        revenue=actual.revenue,
        operating_profit=actual.operating_profit,
        net_income=actual.net_income,
        eps=actual.net_income * 1_000_000_000.0 / revised_shares,
    )

    result = attribute_eps_error(load_anchor(), revised_actual, revised)

    assert abs(result.residual) < 1e-9
    assert abs(result.residual_model_eps) < 1e-9
    assert result.shares_lever_degenerate is False
    assert result.shares != pytest.approx(0.0, abs=1e-15)


def test_append_is_idempotent(tmp_path: Path) -> None:
    actual, payload = load_actual()
    model = load_anchor()
    block = render(model, actual, attribute_eps_error(model, actual, payload))
    scorecard = tmp_path / "scorecard.md"
    scorecard.write_text("# Scorecard\n", encoding="utf-8")

    append_block(scorecard, block)
    append_block(scorecard, block)
    updated = scorecard.read_text(encoding="utf-8")

    assert updated.count(START_MARKER) == 1
    assert updated.count(END_MARKER) == 1
    assert "shares_lever_degenerate: true" in updated
    assert "백테스트 5레버 워터폴과 직접 비교 불가" in updated
    assert "정규화 압축" in updated
    assert "÷모델EPS (비교용)" in updated
