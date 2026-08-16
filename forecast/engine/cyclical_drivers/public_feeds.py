"""Public cyclical price feed adapters.

IO lives here; driver math stays in ``base.py``. The adapters return normalized
price points so callers can build ``DriverInputs`` without baking provider quirks
into the pure spread-to-margin model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable


@dataclass(frozen=True)
class PricePoint:
    period: date
    value: float
    source: str


Downloader = Callable[[str, str, str], list[PricePoint]]


YAHOO_TICKERS: dict[str, str] = {
    "crude_wti": "CL=F",
    "crude_brent": "BZ=F",
    "steel_hrc": "HRC=F",
    "iron_ore_62fe": "TIO=F",
    "lithium_proxy": "LIT",
    "nickel": "NIK=F",
    "copper_proxy": "HG=F",
}

EXPLICIT_GAPS: dict[str, str] = {
    "memory_semis.output": "TrendForce DRAM/NAND contract ASP is paywalled; use declared DXI proxy only when supplied.",
    "chemicals.output": "Platts ethylene/PX spread is paywalled; no public equivalent wired.",
    "batteries.output": "BNEF/IHS battery cell ASP is paywalled; input-metals basket only is public.",
    "shipping.output": "BDI public history is not consistently exposed through Yahoo in this environment.",
    "airlines.output": "Passenger yield/RASK is carrier-reported, not a common public commodity feed.",
}


def fetch_yahoo_monthly(
    key: str,
    *,
    period: str = "5y",
    downloader: Downloader | None = None,
) -> list[PricePoint]:
    """Fetch a public Yahoo series by registry key.

    ``downloader`` is injectable for tests and alternate providers. The default
    uses yfinance and returns an empty list on provider/cert/schema failure so
    callers can abstain instead of fabricating data.
    """
    ticker = YAHOO_TICKERS[key]
    if downloader is not None:
        return downloader(ticker, period, "1mo")
    try:
        # Set the ASCII-safe CA bundle BEFORE yfinance/curl_cffi loads — under a
        # non-ASCII Windows home path (e.g. a Korean username) curl_cffi cannot
        # open certifi's bundle and TLS fails. Every other EFE Yahoo consumer runs
        # this at import; this adapter was missing it (the cyclical-pilot cert error).
        from pipeline._ssl_setup import ensure_ssl_env

        ensure_ssl_env()

        import yfinance as yf

        frame = yf.download(
            ticker,
            period=period,
            interval="1mo",
            progress=False,
            auto_adjust=False,
        )
    except Exception:
        return []
    if frame is None or frame.empty:
        return []
    close = frame["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    points: list[PricePoint] = []
    for idx, value in close.dropna().items():
        points.append(PricePoint(idx.date(), float(value), f"Yahoo {ticker}"))
    return points


def public_feed_coverage() -> dict[str, list[str]]:
    """Public series wired by sector. Paywalled outputs remain explicit gaps."""
    return {
        "oil_gas": ["crude_wti", "crude_brent"],
        "steel": ["steel_hrc", "iron_ore_62fe"],
        "batteries": ["lithium_proxy", "nickel", "copper_proxy"],
        "shipping": [],
        "airlines": [],
    }

