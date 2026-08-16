from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from engine.backtest import run_backtest
from engine.eps_bridge import project_eps
from engine.margin_model import project_margins
from engine.segment_revenue import project_quarterly_revenue
from engine.tax_finance import apply_taxes_and_finance
from schemas.models import (
    AnchorMargins,
    FinanceAssumptions,
    HistoricalDriver,
    MarginAssumptions,
    MarginBaseline,
    QuarterlyActual,
    SegmentAssumptions,
    SegmentForecast,
    SharesOutstanding,
)


def _actual(idx: int, revenue: float) -> QuarterlyActual:
    year = 2023 + idx // 4
    quarter = idx % 4 + 1
    month = quarter * 3
    return QuarterlyActual(
        quarter_label=f"{year}Q{quarter}",
        period_end=date(year, month, 31 if month in {3, 12} else 30),
        revenue_total=revenue,
        revenue_by_segment=[
            SegmentForecast(segment_id="dram", revenue=revenue * 0.7),
            SegmentForecast(segment_id="nand", revenue=revenue * 0.25),
            SegmentForecast(segment_id="other", revenue=revenue * 0.05),
        ],
        gross_profit=revenue * 0.4,
        operating_profit=revenue * 0.25,
        net_profit=revenue * 0.2,
        eps_basic=revenue,
    )


def _assumptions() -> SegmentAssumptions:
    return SegmentAssumptions(
        dram_bit_growth_qoq=[0.1],
        dram_hbm_share_qoq=[0.0],
        dram_hbm_asp_yoy=0.0,
        dram_ddr_asp_qoq=[0.0],
        nand_bit_growth_qoq=[0.1],
        nand_asp_qoq=[0.0],
        other_revenue_growth_qoq=[0.1],
    )


def _margin_assumptions() -> MarginAssumptions:
    return MarginAssumptions(
        sga_pct_of_revenue=0.05,
        rnd_pct_of_revenue=0.10,
    )


def _anchor_margins() -> AnchorMargins:
    return AnchorMargins(
        gm_hbm=0.8,
        gm_ddr=0.4,
        gm_nand=0.4,
        gm_other=0.4,
    )


def _finance_assumptions() -> FinanceAssumptions:
    return FinanceAssumptions(
        effective_tax_rate=0.25,
        net_interest_pct_of_revenue=-0.01,
    )


def _shares() -> SharesOutstanding:
    return SharesOutstanding(
        weighted_avg_basic=1_000_000_000,
        weighted_avg_diluted=1_100_000_000,
    )


def _baseline(prior_window: list[QuarterlyActual]) -> MarginBaseline:
    seed = prior_window[-1]
    return MarginBaseline(
        gp_margin=sum(q.gross_profit / q.revenue_total for q in prior_window) / len(prior_window),
        op_margin=sum(q.operating_profit / q.revenue_total for q in prior_window) / len(prior_window),
        np_margin=sum(q.net_profit / q.revenue_total for q in prior_window) / len(prior_window),
        dram_blended_asp=next(s.revenue for s in seed.revenue_by_segment if s.segment_id == "dram"),
        nand_blended_asp=next(s.revenue for s in seed.revenue_by_segment if s.segment_id == "nand"),
    )


def test_insufficient_history_raises():
    with pytest.raises(ValueError):
        run_backtest(
            [_actual(0, 100.0)],
            _assumptions(),
            _margin_assumptions(),
            _anchor_margins(),
            _finance_assumptions(),
            _shares(),
            lookback_quarters=1,
        )


def test_mape_and_bias_definitions():
    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 100.0), _actual(5, 110.0)]

    result = run_backtest(
        history,
        _assumptions(),
        _margin_assumptions(),
        _anchor_margins(),
        _finance_assumptions(),
        _shares(),
        lookback_quarters=2,
    )

    assert result.revenue_mape == pytest.approx((0.1 + 0.0) / 2)
    assert result.bias_revenue == pytest.approx((0.1 + 0.0) / 2)


def test_no_lookahead_bias():
    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 1000.0)]

    result = run_backtest(
        history,
        _assumptions(),
        _margin_assumptions(),
        _anchor_margins(),
        _finance_assumptions(),
        _shares(),
        lookback_quarters=1,
    )

    assert result.quarters[0].model_revenue == pytest.approx(110.0)


def test_backtest_eps_matches_forward_engine_chain():
    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 120.0)]
    margin_assumptions = _margin_assumptions()
    anchor_margins = _anchor_margins()
    finance_assumptions = _finance_assumptions()
    shares = _shares()

    result = run_backtest(
        history,
        _assumptions(),
        margin_assumptions,
        anchor_margins,
        finance_assumptions,
        shares,
        lookback_quarters=1,
    )

    prior_window = history[:4]
    baseline = _baseline(prior_window)
    expected = project_quarterly_revenue(history[3], baseline, _assumptions(), 1)
    expected = project_margins(expected, baseline, margin_assumptions, anchor_margins)
    expected = apply_taxes_and_finance(expected, finance_assumptions)
    # backtest scores each quarter with the SEED-implied share count (no-lookahead);
    # the synthetic seeds imply 0.2*rev bn NI / rev EPS = 200M shares.
    implied_shares = SharesOutstanding(weighted_avg_basic=200_000_000, weighted_avg_diluted=200_000_000)
    expected = project_eps(expected, implied_shares)

    assert result.quarters[0].model_eps == pytest.approx(expected[0].eps_basic)


def test_backtest_uses_historical_hbm_share_for_target_quarter():
    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 120.0)]
    margin_assumptions = _margin_assumptions()
    anchor_margins = _anchor_margins()
    finance_assumptions = _finance_assumptions()
    shares = _shares()

    result = run_backtest(
        history,
        _assumptions(),
        margin_assumptions,
        anchor_margins,
        finance_assumptions,
        shares,
        {"2024Q1": 1.0},
        lookback_quarters=1,
    )

    prior_window = history[:4]
    baseline = _baseline(prior_window)
    expected = project_quarterly_revenue(history[3], baseline, _assumptions(), 1)
    expected = [expected[0].model_copy(update={"hbm_share": 1.0})]
    expected = project_margins(expected, baseline, margin_assumptions, anchor_margins)
    expected = apply_taxes_and_finance(expected, finance_assumptions)
    # backtest scores each quarter with the SEED-implied share count (no-lookahead);
    # the synthetic seeds imply 0.2*rev bn NI / rev EPS = 200M shares.
    implied_shares = SharesOutstanding(weighted_avg_basic=200_000_000, weighted_avg_diluted=200_000_000)
    expected = project_eps(expected, implied_shares)

    assert result.quarters[0].model_eps == pytest.approx(expected[0].eps_basic)


def test_anchor_quarter_reproduces_actual_gross_margin():
    """Anchor quarter (first backtest quarter) must reproduce the DART actual GP margin.

    The profile calibrates anchor_margins so the 2024Q1 blended GP equals the DART
    actual (~38.6%). The anchor quarter is the reference point of the cost-per-bit
    chain, so it must be projected with margin_periods_since_anchor == 0 and ASP
    factor == 1.0 — no cost-decline / ASP leverage applied to the anchor itself.

    Skips where the DART pipeline / SSL setup or the committed cache is unavailable
    (e.g. bare CI); runs on the Windows host and against reports/.cache/.
    """
    os.environ.setdefault("DART_API_KEY", "cache-only")
    try:
        from engine.backtest import iter_backtest_forecasts as _iter
        from pipeline.dart_fetcher import fetch_quarterly_actuals_series
        from pipeline.ir_loader import load_profile
    except Exception as exc:  # pragma: no cover - env-dependent (Windows SSL path)
        pytest.skip(f"DART pipeline unavailable: {exc}")

    profile_path = Path(__file__).resolve().parents[1] / "profiles" / "sk_hynix.yaml"
    profile = load_profile(profile_path)
    window = profile["backtest_window"]
    start_quarter = str(window["start_quarter"])
    end_quarter = str(window["end_quarter"])
    lookback = int(window["lookback_quarters"])

    def _key(label: str) -> tuple[int, int]:
        year_text, quarter_text = label.split("Q", 1)
        return int(year_text), int(quarter_text)

    try:
        actuals = fetch_quarterly_actuals_series(
            profile["company"].corp_code_dart,
            int(start_quarter[:4]) - 1,
            int(end_quarter[:4]),
            profile["segment_revenue_split"],
            use_cache=True,
            skip_unavailable=True,
        )
    except Exception as exc:  # pragma: no cover - needs DART cache or network
        pytest.skip(f"DART actuals unavailable: {exc}")

    history = [a for a in actuals if _key(a.quarter_label) <= _key(end_quarter)]
    base_assumptions, base_margin, base_finance = profile["scenarios"]["base"]
    rows = list(
        _iter(
            history,
            base_assumptions,
            base_margin,
            profile["anchor_margins"],
            base_finance,
            profile["shares"],
            profile["historical_drivers"],
            lookback,
        )
    )

    _seed, target, forecast = rows[0]
    assert target.quarter_label == start_quarter
    model_gp_margin = forecast.gross_profit / forecast.revenue_total
    actual_gp_margin = target.gross_profit / target.revenue_total
    assert model_gp_margin == pytest.approx(actual_gp_margin, abs=0.015)


def test_backtest_accumulates_historical_asp_indexes_from_window_anchor():
    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 120.0), _actual(5, 130.0)]
    margin_assumptions = MarginAssumptions(
        sga_pct_of_revenue=0.05,
        rnd_pct_of_revenue=0.10,
    )
    anchor_margins = AnchorMargins(
        gm_hbm=0.8,
        gm_ddr=0.4,
        gm_nand=0.4,
        gm_other=0.4,
        cost_decline_qoq_hbm=0.0,
        cost_decline_qoq_ddr=0.10,
        cost_decline_qoq_nand=0.10,
    )
    finance_assumptions = _finance_assumptions()
    shares = _shares()
    historical_drivers = {
        "2024Q1": HistoricalDriver(
            quarter_label="2024Q1",
            hbm_share=0.0,
            hbm_asp_qoq=0.0,
            ddr_asp_qoq=0.10,
            nand_asp_qoq=0.10,
        ),
        "2024Q2": HistoricalDriver(
            quarter_label="2024Q2",
            hbm_share=0.0,
            hbm_asp_qoq=0.0,
            ddr_asp_qoq=0.10,
            nand_asp_qoq=0.10,
        ),
    }

    result = run_backtest(
        history,
        _assumptions(),
        margin_assumptions,
        anchor_margins,
        finance_assumptions,
        shares,
        historical_drivers,
        lookback_quarters=2,
    )

    prior_window = history[1:5]
    baseline = _baseline(prior_window)
    expected = project_quarterly_revenue(
        history[4],
        baseline,
        SegmentAssumptions(
            dram_bit_growth_qoq=[0.1],
            dram_hbm_share_qoq=[0.0],
            dram_hbm_asp_yoy=0.0,
            dram_ddr_asp_qoq=[0.10],
            nand_bit_growth_qoq=[0.1],
            nand_asp_qoq=[0.10],
            other_revenue_growth_qoq=[0.1],
        ),
        1,
    )
    # The first scored quarter (2024Q1) is the anchor reference (periods=0, ASP=1.0).
    # The second scored quarter (2024Q2) carries exactly ONE post-anchor step: the
    # 2024Q2 driver qoq only. (Pre-fix this double-counted the anchor's own qoq,
    # yielding asp 1.10*1.10 and periods=2.)
    expected = [
        expected[0].model_copy(
            update={
                "hbm_share": 0.0,
                "asp_hbm": 1.0,
                "asp_ddr": 1.10,
                "asp_nand": 1.10,
                "margin_periods_since_anchor": 1,
            }
        )
    ]
    expected = project_margins(expected, baseline, margin_assumptions, anchor_margins)
    expected = apply_taxes_and_finance(expected, finance_assumptions)
    # backtest scores each quarter with the SEED-implied share count (no-lookahead);
    # the synthetic seeds imply 0.2*rev bn NI / rev EPS = 200M shares.
    implied_shares = SharesOutstanding(weighted_avg_basic=200_000_000, weighted_avg_diluted=200_000_000)
    expected = project_eps(expected, implied_shares)

    assert result.quarters[1].model_eps == pytest.approx(expected[0].eps_basic)
    assert result.quarters[1].model_revenue == pytest.approx(expected[0].revenue_total)


def test_backtest_uses_seed_implied_shares_with_profile_fallback():
    from engine.backtest import iter_backtest_forecasts

    history = [_actual(i, 100.0) for i in range(4)] + [_actual(4, 120.0)]
    rows = list(
        iter_backtest_forecasts(
            history,
            _assumptions(),
            _margin_assumptions(),
            _anchor_margins(),
            _finance_assumptions(),
            _shares(),
            lookback_quarters=1,
        )
    )
    _seed, _target, with_implied = rows[0]

    # Seed without usable EPS -> falls back to the profile share count (1e9),
    # which is 5x the implied 200M -> model EPS shrinks 5x.
    blind_history = history[:3] + [history[3].model_copy(update={"eps_basic": None})] + history[4:]
    rows = list(
        iter_backtest_forecasts(
            blind_history,
            _assumptions(),
            _margin_assumptions(),
            _anchor_margins(),
            _finance_assumptions(),
            _shares(),
            lookback_quarters=1,
        )
    )
    _seed, _target, with_fallback = rows[0]

    assert with_implied.eps_basic == pytest.approx(with_fallback.eps_basic * 5.0)
