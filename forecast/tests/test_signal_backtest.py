"""Signal backtest CAR event-study tests."""

from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

from engine.signal_backtest import run_signal_backtest
from engine.signal_extractor import build_extracted_signal
from schemas.models import DisclosureDocument

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture():
    with open(FIXTURES / "signal_backtest_fixture.json", encoding="utf-8") as f:
        return json.load(f)


def test_non_circular_signature():
    params = set(inspect.signature(run_signal_backtest).parameters)
    forbidden = {"actuals", "historical_actuals", "revenue", "financials", "quarterly_actuals"}
    assert params & forbidden == set()
    assert {"signals", "event_dates", "stock_closes", "market_closes"} <= params


def test_exact_car_for_anchor_event():
    fx = _load_fixture()
    signals = {}
    for item in fx["documents"]:
        doc = DisclosureDocument.model_validate(item["document"])
        signals[doc.period_label] = build_extracted_signal(
            item["extraction"], doc, "fixture", date(2025, 1, 23)
        )
    event_dates = {k: date.fromisoformat(v) for k, v in fx["event_dates"].items()}
    stock = {date.fromisoformat(k): v for k, v in fx["stock_closes"].items()}
    market = {date.fromisoformat(k): v for k, v in fx["market_closes"].items()}

    result = run_signal_backtest(signals, event_dates, stock, market, 1, 5)

    anchor = next(e for e in result.events if e.event_label == "2024Q4")
    assert abs(anchor.car_t1 - 0.05) <= 1e-9
    assert abs(anchor.car_t5 - 0.15) <= 1e-9
    assert anchor.direction_match_t1 is True
    assert result.sample_n == 4
    assert abs(result.directional_hit_ratio - 1.0) <= 1e-9
    assert result.information_coefficient is not None and result.information_coefficient > 0
