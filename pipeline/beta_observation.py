"""Collect reproducible weekly price observations for beta regression."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, timedelta
from pathlib import Path

from engine.beta_regression import regress_beta
from schemas.provenance import BetaObservation, Source

_ROOT = Path(__file__).resolve().parent.parent
_MIN_OBSERVATIONS = 80
_BENCHMARKS = {"US": "^GSPC", "JP": "^TOPX", "KR": "^KS11"}
_YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def _from_payload(payload: dict, digest: str) -> BetaObservation:
    beta, n_obs = regress_beta(payload["stock_returns"], payload["benchmark_returns"])
    window_start = date.fromisoformat(payload["window_start"])
    window_end = date.fromisoformat(payload["window_end"])
    return BetaObservation(
        equity_beta=Source(
            value=beta,
            source="yfinance",
            url=_YAHOO_CHART_URL.format(ticker=payload["ticker"]),
            as_of=window_end,
            method="derived",
            derived_from=[payload["ticker"], payload["benchmark"], digest],
        ),
        window_start=window_start,
        window_end=window_end,
        frequency=payload["frequency"],
        benchmark=payload["benchmark"],
        observation_count=n_obs,
        calculation_method=payload["calculation_method"],
    )


def _weekly_log_returns(series) -> dict[date, float]:
    weekly = series.resample("W-FRI").last().dropna()
    values: dict[date, float] = {}
    previous = None
    for timestamp, price in weekly.items():
        price = float(price)
        if previous is not None and price > 0 and previous > 0:
            values[timestamp.date()] = math.log(price / previous)
        previous = price
    return values


def collect_beta_observation(
    ticker: str,
    market: str,
    analysis_date: date,
    *,
    benchmark: str | None = None,
) -> tuple[BetaObservation, str, str]:
    """Fetch adjusted prices during profile generation and persist a dated snapshot."""
    import yfinance as yf

    benchmark = benchmark or _BENCHMARKS.get(market, "^GSPC")
    cache_dir = _ROOT / ".cache" / "beta_observations"
    cached = sorted(cache_dir.glob(f"{ticker}_{benchmark}_*.json"), reverse=True)
    for snapshot in cached:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        window_end = date.fromisoformat(payload["window_end"])
        if window_end <= analysis_date and (analysis_date - window_end).days <= 7:
            encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            digest = hashlib.sha256(encoded).hexdigest()
            return _from_payload(payload, digest), digest, str(snapshot)

    start = analysis_date - timedelta(days=2 * 365 + 14)
    end = analysis_date + timedelta(days=1)
    stock = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)["Close"]
    index = yf.Ticker(benchmark).history(start=start, end=end, auto_adjust=True)["Close"]
    stock_returns = _weekly_log_returns(stock)
    benchmark_returns = _weekly_log_returns(index)
    common = sorted(set(stock_returns) & set(benchmark_returns))
    if len(common) < _MIN_OBSERVATIONS:
        raise ValueError(f"beta regression requires {_MIN_OBSERVATIONS} observations; got {len(common)}")
    if (analysis_date - common[-1]).days > 7:
        raise ValueError("beta observation is stale")
    beta, n_obs = regress_beta(
        [stock_returns[d] for d in common], [benchmark_returns[d] for d in common]
    )
    payload = {
        "ticker": ticker,
        "benchmark": benchmark,
        "window_start": common[0].isoformat(),
        "window_end": common[-1].isoformat(),
        "frequency": "weekly",
        "calculation_method": "ols_weekly_log_returns_adjusted_close",
        "stock_returns": [stock_returns[d] for d in common],
        "benchmark_returns": [benchmark_returns[d] for d in common],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    snapshot = _ROOT / ".cache" / "beta_observations" / f"{ticker}_{benchmark}_{common[-1]}.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_bytes(encoded)
    observation = _from_payload(payload, digest)
    return observation, digest, str(snapshot)
