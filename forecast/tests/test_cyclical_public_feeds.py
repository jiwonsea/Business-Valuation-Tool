from __future__ import annotations

from datetime import date

from engine.cyclical_drivers.public_feeds import (
    EXPLICIT_GAPS,
    PricePoint,
    fetch_yahoo_monthly,
    public_feed_coverage,
)


def test_fetch_yahoo_monthly_uses_registered_ticker_with_injected_downloader() -> None:
    calls = []

    def downloader(ticker: str, period: str, interval: str):
        calls.append((ticker, period, interval))
        return [PricePoint(date(2026, 1, 31), 100.0, "fixture")]

    points = fetch_yahoo_monthly("steel_hrc", period="1y", downloader=downloader)

    assert calls == [("HRC=F", "1y", "1mo")]
    assert points[0].value == 100.0


def test_public_feed_coverage_keeps_paywalled_outputs_explicit() -> None:
    coverage = public_feed_coverage()

    assert {"steel_hrc", "iron_ore_62fe"}.issubset(set(coverage["steel"]))
    assert {"crude_wti", "crude_brent"}.issubset(set(coverage["oil_gas"]))
    assert "batteries.output" in EXPLICIT_GAPS
    assert "chemicals.output" in EXPLICIT_GAPS
