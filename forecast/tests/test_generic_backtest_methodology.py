"""Regression coverage for decoupled generic forward/backtest drivers."""

from generic_cli import _render_window, backtest_generic
from engine.generic_forecast import run_generic_forecast
from schemas.generic import GenericProfile


def _profile(**overrides) -> GenericProfile:
    raw = dict(
        name="Test Co",
        name_kr="테스트",
        ticker="TST",
        currency="USD",
        reporting_unit="USD_million",
        fiscal_year_end_month=12,
        weighted_avg_diluted=1_000_000_000,
        seed=dict(quarter_label="2025Q1", revenue_total=100.0),
        window=dict(start_quarter="2025Q2", n_quarters=4),
        actuals=[
            dict(quarter_label="2024Q1", revenue_total=100.0),
            dict(quarter_label="2024Q2", revenue_total=120.0),
        ],
        bear=dict(probability=0.25, revenue_growth_qoq=[0.0] * 4, op_margin=0.1, effective_tax_rate=0.2),
        base=dict(probability=0.50, revenue_growth_qoq=[0.05] * 4, op_margin=0.2, effective_tax_rate=0.2),
        bull=dict(probability=0.25, revenue_growth_qoq=[0.1] * 4, op_margin=0.3, effective_tax_rate=0.2),
    )
    raw.update(overrides)
    return GenericProfile.model_validate(raw)


def test_backtest_methodology_overrides_base_without_changing_forward() -> None:
    legacy_profile = _profile()
    profile = _profile(
        backtest_methodology=dict(
            revenue_growth_qoq=[0.0, 0.20, 0.0, 0.0],
            op_margin=0.2,
            effective_tax_rate=0.2,
        )
    )

    result = backtest_generic(profile)

    assert result["rows"][0]["model_rev"] == 120.0
    assert [q.model_dump() for q in run_generic_forecast(profile).weighted_quarterly] == [
        q.model_dump()
        for q in run_generic_forecast(legacy_profile).weighted_quarterly
    ]


def test_backtest_without_methodology_preserves_legacy_base_fallback() -> None:
    result = backtest_generic(_profile())

    assert result["rows"][0]["model_rev"] == 105.0


def test_backtest_calendar_slots_do_not_depend_on_forward_window_length() -> None:
    profile = _profile(
        window=dict(start_quarter="2025Q2", n_quarters=1),
        backtest_methodology=dict(
            revenue_growth_qoq=[0.0, 0.20, 0.0, 0.0],
            op_margin=0.2,
            effective_tax_rate=0.2,
        ),
    )

    result = backtest_generic(profile)

    assert result["rows"][0]["model_rev"] == 120.0


def test_render_empty_window_uses_na_instead_of_formatting_none() -> None:
    window = {
        "n": 0,
        "n_eps": 0,
        "revenue_mape": None,
        "revenue_bias": None,
        "eps_mape": None,
        "eps_bias": None,
        "skill": {},
    }

    rendered = _render_window("pre-break", window)

    assert "매출 MAPE N/A / bias N/A" in rendered[0]
    assert "EPS MAPE N/A / bias N/A" in rendered[0]
