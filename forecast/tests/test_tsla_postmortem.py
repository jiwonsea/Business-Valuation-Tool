"""TSLA Q2 2026 scoring scaffold and immutable-anchor tests."""

import hashlib
from pathlib import Path

import pytest

from scripts.score_tsla_q2_2026 import (
    END_MARKER,
    FROZEN_ANCHOR,
    FROZEN_PATH,
    FROZEN_SHA256,
    START_MARKER,
    _surprise_direction,
    append_to_handoff,
    render_postmortem,
    score_tsla,
)
from schemas.postmortem import GenericActualRelease

REPO_ROOT = Path(__file__).resolve().parent.parent


def _synthetic_actual() -> GenericActualRelease:
    return GenericActualRelease.model_validate(
        {
            "quarter_label": "2026Q2",
            "provenance": {"source": "synthetic TSLA IR", "as_of": "2026-07-23"},
            "revenue_total": 27_000.0,
            "gaap_eps_diluted": 0.40,
            "diluted_shares": 3_540_000_000.0,
            "operating_income": 1_620.0,
            "net_income": 1_416.0,
            "automotive_revenue": 20_100.0,
            "energy_revenue": 3_800.0,
            "services_revenue": 3_100.0,
            "automotive_gross_margin_ex_credits": 0.13,
            "regulatory_credits": 300.0,
            "other_income_expense": -100.0,
            "non_gaap_eps": 0.55,
            "stock_based_compensation": 400.0,
        }
    )


def test_frozen_anchor_is_transcribed_and_artifact_is_immutable() -> None:
    assert FROZEN_ANCHOR["scenarios"]["base"]["revenue_total"] == 26_864.0
    assert FROZEN_ANCHOR["weighted"]["revenue_total"] == 26_808.0
    assert FROZEN_ANCHOR["consensus"]["ir"] == {
        "revenue_total": 27_580.0,
        "gaap_eps": 0.36,
        "non_gaap_eps": 0.55,
    }
    assert hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest() == FROZEN_SHA256


def test_template_loads_but_cannot_score_before_release() -> None:
    actual = GenericActualRelease.model_validate(
        {
            "quarter_label": "2026Q2",
            "provenance": {"source": "empty template", "as_of": "TBD"},
        }
    )
    with pytest.raises(ValueError, match="missing required fields"):
        score_tsla(actual)


@pytest.mark.parametrize(
    ("model", "actual", "consensus", "expected"),
    [
        (0.43, 0.40, 0.36, "HIT"),
        (0.43, 0.32, 0.36, "MISS"),
        (0.43, 0.36, 0.36, "NO-SURPRISE"),
        (0.36, 0.40, 0.36, "MISS"),
    ],
)
def test_surprise_direction_labels_are_explicit(
    model: float,
    actual: float,
    consensus: float,
    expected: str,
) -> None:
    status, model_gap, actual_gap = _surprise_direction(model, actual, consensus)

    assert status == expected
    assert model_gap == pytest.approx(model - consensus)
    assert actual_gap == pytest.approx(actual - consensus)


def test_render_and_atomic_handoff_update_are_idempotent(tmp_path: Path) -> None:
    frozen_before = hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest()
    block = render_postmortem(score_tsla(_synthetic_actual()))
    handoff = tmp_path / "handoff.md"
    handoff.write_text("# Handoff\n\n## 4. 사후 채점\n\nTBD\n\n## 5. 범위 가드레일\n", encoding="utf-8")

    append_to_handoff(handoff, block)
    append_to_handoff(handoff, block)
    updated = handoff.read_text(encoding="utf-8")

    assert updated.count(START_MARKER) == 1
    assert updated.count(END_MARKER) == 1
    assert "사후 귀인 — 예측 신호 아님" in updated
    assert "IR GAAP EPS 컨센 surprise 방향: **HIT**" in updated
    assert "model +0.070 / actual +0.040" in updated
    assert "Automotive GP (크레딧 제외)" in updated
    assert hashlib.sha256(FROZEN_PATH.read_bytes()).hexdigest() == frozen_before
