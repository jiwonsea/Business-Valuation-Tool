"""Item 1 — skill-gate reliability: n>=8 gate + dual-window (full / trailing-8Q).

The forward-EPS block must ABSTAIN (stance neutral) when the backtest is too
short to claim skill, and must surface both the expanding-window and trailing-8Q
skill so a regime turn is visible instead of averaged away.
"""

from __future__ import annotations

from engine.generic_signal import MIN_SKILL_N, build_signal_block


def _rows(model_errs: list[float], rw_errs: list[float]) -> list[dict]:
    """Rows with a fixed 10.0 actual EPS and given signed fractional errors."""
    rows = []
    for i, (me, re) in enumerate(zip(model_errs, rw_errs)):
        actual = 10.0
        rows.append(
            {
                "quarter": f"20{20 + i // 4}Q{i % 4 + 1}",
                "actual_eps": actual,
                "model_eps": actual * (1 + me),
                "rw_eps": actual * (1 + re),
            }
        )
    return rows


ANNUAL = [{"fiscal_year": 2026, "scenario": "weighted", "eps_basic": 11.0}]
QUARTERLY = [
    {"quarter_label": "2026Q1", "eps_diluted": 2.0},
    {"quarter_label": "2026Q4", "eps_diluted": 2.6},  # rising
]


def test_short_window_abstains_even_when_beating_naive() -> None:
    rows = _rows(model_errs=[0.01, 0.01, 0.01], rw_errs=[0.20, 0.20, 0.20])
    block = build_signal_block(ANNUAL, QUARTERLY, {"rows": rows}, consensus_fy1_eps=None)
    assert block["skill"]["n"] == 3
    assert block["skill"]["skill_pass"] is False
    assert "n<min_n" in block["skill"]["reason"]
    assert block["stance"] == "neutral"


def test_long_window_beating_naive_passes_and_is_bullish() -> None:
    rows = _rows(model_errs=[0.02] * 10, rw_errs=[0.18] * 10)
    block = build_signal_block(ANNUAL, QUARTERLY, {"rows": rows}, consensus_fy1_eps=None)
    assert block["skill"]["n"] == 10
    assert block["skill"]["n"] >= MIN_SKILL_N
    assert block["skill"]["skill_pass"] is True
    assert block["stance"] == "bullish"


def test_long_window_not_beating_naive_abstains() -> None:
    rows = _rows(model_errs=[0.25] * 10, rw_errs=[0.05] * 10)
    block = build_signal_block(ANNUAL, QUARTERLY, {"rows": rows}, consensus_fy1_eps=None)
    assert block["skill"]["skill_pass"] is False
    assert block["skill"]["reason"] == "does_not_beat_naive"
    assert block["stance"] == "neutral"


def test_dual_window_exposes_regime_shift() -> None:
    # full: (0+0 + 8*0.21)/10 = 16.8% < 20% naive -> beats.
    # trailing-8: 21% > 20% naive -> does not beat. Regime turn surfaced.
    rows = _rows(model_errs=[0.0, 0.0] + [0.21] * 8, rw_errs=[0.20] * 10)
    block = build_signal_block(ANNUAL, QUARTERLY, {"rows": rows}, consensus_fy1_eps=None)
    sk = block["skill"]
    assert sk["full_window"]["n"] == 10
    assert sk["trailing_8q"]["n"] == 8
    assert sk["full_window"]["beats_naive"] is True
    assert sk["trailing_8q"]["beats_naive"] is False
    assert sk["regime_shift"] is True


def test_backcompat_scalar_backtest_without_rows() -> None:
    block = build_signal_block(
        ANNUAL, QUARTERLY,
        {"n": 9, "eps_mape": 4.0, "naive_rw_eps_mape": 9.0},
        consensus_fy1_eps=None,
    )
    assert block["skill"]["n"] == 9
    assert block["skill"]["skill_pass"] is True


def test_trailing_8q_loss_abstains_even_when_full_window_beats() -> None:
    rows = []
    for i in range(10):
        actual = 10.0
        if i < 2:
            model = 10.0
            rw = 100.0
        else:
            model = 20.0
            rw = 11.0
        rows.append(
            {
                "quarter": f"202{i // 4}Q{(i % 4) + 1}",
                "actual_eps": actual,
                "model_eps": model,
                "rw_eps": rw,
            }
        )
    block = build_signal_block(
        ANNUAL,
        QUARTERLY,
        {"n": 10, "rows": rows},
        consensus_fy1_eps=None,
    )
    assert block["skill"]["full_window"]["beats_naive"] is True
    assert block["skill"]["trailing_8q"]["beats_naive"] is False
    assert block["skill"]["skill_pass"] is False
    assert block["skill"]["reason"] == "trailing_8q_does_not_beat_naive"
    assert block["stance"] == "neutral"


def test_backcompat_scalar_short_n_abstains() -> None:
    block = build_signal_block(
        ANNUAL, QUARTERLY,
        {"n": 3, "eps_mape": 4.0, "naive_rw_eps_mape": 9.0},
        consensus_fy1_eps=None,
    )
    assert block["skill"]["skill_pass"] is False
    assert block["stance"] == "neutral"
