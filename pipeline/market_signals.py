"""Market signals aggregator -- external data for scenario calibration.

Fetches quantitative market signals from free APIs and aggregates them into
a single MarketSignals object for prompt injection and post-LLM validation.

Data sources:
  - FRED (macro): Fed Funds, 10Y Treasury, Breakeven Inflation, BAA spread, VIX
  - yfinance (analyst consensus): target prices, recommendation
  - FinBERT (sentiment): news headline sentiment scoring (optional dependency)
  - yfinance (options): implied volatility, put/call ratio (US listed only)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from schemas.models import MarketSignals

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "market_signals"
_FRED_CACHE_TTL = 86400  # 24 hours


# ---------------------------------------------------------------------------
# FRED Macro Data (5 series, public CSV endpoint, no API key)
# ---------------------------------------------------------------------------

_FRED_SERIES = {
    "fed_funds_rate": "DFF",
    "us_10y_yield": "DGS10",
    "breakeven_inflation": "T10YIE",
    "credit_spread_baa": "BAMLC0A4CBBB",
    "vix": "VIXCLS",
}


def _fetch_fred_series(series_id: str) -> float | None:
    """Fetch latest value from FRED CSV endpoint with disk cache."""
    from .api_guard import ApiGuard

    cache_path = _CACHE_DIR / "fred" / f"{series_id}.json"

    # Check disk cache
    if cache_path.exists():
        try:
            if time.time() - cache_path.stat().st_mtime < _FRED_CACHE_TTL:
                data = json.loads(cache_path.read_text(encoding="utf-8"))
                cached_val = data.get("value")
                if cached_val is not None:
                    logger.debug("FRED 캐시 적중: %s=%.2f", series_id, cached_val)
                    ApiGuard.get().record_cache_hit("fred")
                    return cached_val
        except (json.JSONDecodeError, OSError):
            pass

    # API call
    guard = ApiGuard.get()
    guard.check("fred")
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv"
    cosd = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    try:
        resp = httpx.get(url, params={"id": series_id, "cosd": cosd}, timeout=5)
        resp.raise_for_status()
        lines = resp.text.strip().split("\n")
        if len(lines) < 2:
            guard.record_success("fred")
            return None

        # Walk backward to find last non-missing value
        for line in reversed(lines[1:]):
            val_str = line.split(",")[-1].strip()
            if val_str != ".":
                rate = float(val_str)
                guard.record_success("fred")

                # Save to cache
                try:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(
                        json.dumps(
                            {"value": rate, "fetched_at": datetime.now().isoformat()}
                        ),
                        encoding="utf-8",
                    )
                except OSError:
                    pass
                return rate

        guard.record_success("fred")
        return None
    except (httpx.HTTPError, ValueError, IndexError) as e:
        logger.debug("FRED %s 조회 실패: %s", series_id, e)
        try:
            guard.record_failure("fred", e)
        except Exception:
            pass
        return None


def _fetch_fred_macro() -> dict[str, float | None]:
    """Fetch all FRED macro series. Returns {field_name: value}."""
    result: dict[str, float | None] = {}
    for field_name, series_id in _FRED_SERIES.items():
        try:
            result[field_name] = _fetch_fred_series(series_id)
        except Exception as e:
            logger.debug("FRED %s 스킵: %s", series_id, e)
            result[field_name] = None
    return result


# ---------------------------------------------------------------------------
# Analyst Consensus (yfinance Ticker.info)
# ---------------------------------------------------------------------------


def _fetch_analyst_consensus(ticker: str, market: str) -> dict[str, object]:
    """Fetch analyst target prices and recommendation from yfinance."""
    result: dict[str, object] = {}
    try:
        import yfinance as yf

        if market == "KR":
            from . import yfinance_fetcher

            ticker = yfinance_fetcher.resolve_kr_ticker(ticker)

        info = yf.Ticker(ticker).info
        result["target_mean"] = info.get("targetMeanPrice")
        result["target_high"] = info.get("targetHighPrice")
        result["target_low"] = info.get("targetLowPrice")
        result["analyst_count"] = info.get("numberOfAnalystOpinions")
        result["recommendation"] = info.get("recommendationKey")
    except Exception as e:
        logger.debug("Analyst consensus 조회 실패 (%s): %s", ticker, e)

    return result


# ---------------------------------------------------------------------------
# FinBERT Sentiment (optional dependency)
# ---------------------------------------------------------------------------


def _compute_news_sentiment(news: list[dict]) -> dict[str, object]:
    """Run FinBERT on news headlines. Graceful fallback if not installed."""
    result: dict[str, object] = {}
    if not news:
        return result

    try:
        from .sentiment import compute_sentiment

        score, label, count = compute_sentiment(news)
        result["news_sentiment_score"] = score
        result["sentiment_label"] = label
        result["sentiment_article_count"] = count
    except ImportError:
        logger.debug("FinBERT 미설치 — 감성 분석 스킵")
    except Exception as e:
        logger.debug("감성 분석 실패: %s", e)

    return result


# ---------------------------------------------------------------------------
# Options IV (US listed only, yfinance options chain)
# ---------------------------------------------------------------------------


def _fetch_options_iv(ticker: str) -> dict[str, float | None]:
    """Extract 30-day ATM IV and put/call ratio from yfinance."""
    result: dict[str, float | None] = {
        "iv_30d_atm": None,
        "iv_percentile": None,
        "put_call_ratio": None,
    }
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        tk = yf.Ticker(ticker)
        expiry_dates = tk.options
        if not expiry_dates:
            return result

        # Find nearest expiry >= 20 days out
        target_date = datetime.now() + timedelta(days=20)
        selected_expiry: str | None = None
        for exp_str in expiry_dates:
            exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
            if exp_date >= target_date:
                selected_expiry = exp_str
                break

        if selected_expiry is None:
            selected_expiry = expiry_dates[-1]

        chain = tk.option_chain(selected_expiry)
        calls = chain.calls
        puts = chain.puts

        if calls.empty or puts.empty:
            return result

        # Current price for ATM strike selection
        info = tk.info
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current_price:
            return result

        # Find ATM strike (nearest to current price)
        calls_sorted = calls.copy()
        calls_sorted["dist"] = abs(calls_sorted["strike"] - current_price)
        atm_idx = calls_sorted["dist"].idxmin()
        atm_strike = calls_sorted.loc[atm_idx, "strike"]

        # ATM IV (average of call + put at ATM)
        call_iv = calls_sorted.loc[atm_idx, "impliedVolatility"]
        put_at_atm = puts[puts["strike"] == atm_strike]
        if not put_at_atm.empty:
            put_iv = put_at_atm.iloc[0]["impliedVolatility"]
            atm_iv = (call_iv + put_iv) / 2
        else:
            atm_iv = call_iv

        result["iv_30d_atm"] = round(atm_iv * 100, 1)  # Convert to percentage

        # Put/call volume ratio
        total_call_vol = calls["volume"].sum()
        total_put_vol = puts["volume"].sum()
        if total_call_vol and total_call_vol > 0:
            result["put_call_ratio"] = round(total_put_vol / total_call_vol, 2)

        # IV percentile vs 1Y historical volatility (simplified: compare to HV)
        try:
            hist = tk.history(period="1y")
            if len(hist) > 20:
                returns = hist["Close"].pct_change().dropna()
                hv_annual = float(returns.std() * (252**0.5) * 100)
                if hv_annual > 0:
                    # Rough percentile: where current IV sits relative to HV
                    result["iv_percentile"] = round(
                        min(100, max(0, (atm_iv * 100 / hv_annual) * 50)), 0
                    )
        except Exception:
            pass

    except Exception as e:
        logger.debug("Options IV 조회 실패 (%s): %s", ticker, e)

    return result


# ---------------------------------------------------------------------------
# Main aggregator
# ---------------------------------------------------------------------------


def fetch_market_signals(
    ticker: str | None = None,
    market: str = "KR",
    company_name: str = "",
    news: list[dict] | None = None,
) -> MarketSignals:
    """Aggregate all external market signals. Graceful degradation on any failure.

    Each sub-fetcher is independent; failure in one does not block others.
    """
    data: dict[str, object] = {}

    # 1. FRED Macro (always)
    try:
        fred_data = _fetch_fred_macro()
        data.update(fred_data)
        logger.info(
            "[signals] FRED: %s",
            {k: v for k, v in fred_data.items() if v is not None},
        )
    except Exception as e:
        logger.warning("[signals] FRED 전체 실패: %s", e)

    # 2. Analyst Consensus (listed companies with ticker)
    if ticker:
        try:
            analyst_data = _fetch_analyst_consensus(ticker, market)
            data.update(analyst_data)
            if analyst_data.get("target_mean"):
                logger.info(
                    "[signals] Analyst: target=%.1f (N=%s, %s)",
                    analyst_data["target_mean"],
                    analyst_data.get("analyst_count"),
                    analyst_data.get("recommendation"),
                )
        except Exception as e:
            logger.warning("[signals] Analyst consensus 실패: %s", e)

    # 3. Sentiment (when news available)
    if news:
        try:
            sentiment_data = _compute_news_sentiment(news)
            data.update(sentiment_data)
            if sentiment_data.get("news_sentiment_score") is not None:
                logger.info(
                    "[signals] Sentiment: %.2f (%s, %d건)",
                    sentiment_data["news_sentiment_score"],
                    sentiment_data.get("sentiment_label"),
                    sentiment_data.get("sentiment_article_count", 0),
                )
        except Exception as e:
            logger.warning("[signals] Sentiment 분석 실패: %s", e)

    # 4. Options IV (US listed only)
    if ticker and market == "US":
        try:
            iv_data = _fetch_options_iv(ticker)
            data.update(iv_data)
            if iv_data.get("iv_30d_atm"):
                logger.info(
                    "[signals] Options: IV=%.1f%% (pctl=%s, P/C=%s)",
                    iv_data["iv_30d_atm"],
                    iv_data.get("iv_percentile"),
                    iv_data.get("put_call_ratio"),
                )
        except Exception as e:
            logger.warning("[signals] Options IV 실패: %s", e)

    data["fetched_at"] = datetime.now().isoformat()
    return MarketSignals(**{k: v for k, v in data.items() if v is not None})
