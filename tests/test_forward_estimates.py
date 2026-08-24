from datetime import date

import pandas as pd

from pipeline.forward_estimates import collect_forward_anchor


class _FakeTicker:
    info = {"nextFiscalYearEnd": 1800835200}  # 2027-01-25 UTC
    revenue_estimate = pd.DataFrame(
        {"avg": [392_000_000_000, 556_000_000_000], "numberOfAnalysts": [51, 54]},
        index=["0y", "+1y"],
    )
    earnings_estimate = pd.DataFrame(
        {"avg": [8.98, 12.80], "numberOfAnalysts": [50, 49]},
        index=["0y", "+1y"],
    )


def test_fy27_maps_to_zero_year_not_plus_one(monkeypatch, tmp_path):
    import pipeline.forward_estimates as module
    import yfinance

    monkeypatch.setattr(yfinance, "Ticker", lambda ticker: _FakeTicker())
    monkeypatch.setattr(module, "_ROOT", tmp_path)
    result = collect_forward_anchor("NVDA", date(2026, 7, 17), target_fiscal_year=2027)
    assert result.relative_period == "0y"
    assert result.fiscal_period == "FY27"
    assert result.revenue.value == 392_000
    assert result.revenue.n_analysts == 51
    assert result.eps.n_analysts == 50
    assert len(result.source_hash) == 64


def test_plus_one_year_is_not_promoted_to_unverified_fiscal_period(
    monkeypatch, tmp_path
):
    import pipeline.forward_estimates as module
    import yfinance

    monkeypatch.setattr(yfinance, "Ticker", lambda ticker: _FakeTicker())
    monkeypatch.setattr(module, "_ROOT", tmp_path)
    result = collect_forward_anchor("NVDA", date(2026, 7, 17), target_fiscal_year=2028)
    assert result.relative_period == "+1y"
    assert result.fiscal_period is None
    assert result.fiscal_period_end is None
