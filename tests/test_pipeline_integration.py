"""Pipeline integration tests with mocked HTTP responses.

Tests data flow through pipeline clients without hitting real APIs.
Uses unittest.mock to patch httpx calls at the module level.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── Yahoo Finance ──


def _mock_yahoo_chart_response(ticker="AAPL"):
    """Build a mock httpx.Response for Yahoo Finance chart API."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "regularMarketPrice": 185.50,
                        "currency": "USD",
                        "shortName": "Apple Inc.",
                        "exchangeName": "NMS",
                        "exchange": "NMS",
                    }
                }
            ]
        }
    }
    resp.raise_for_status = MagicMock()
    return resp


def _mock_yahoo_summary_response():
    """Build a mock httpx.Response for Yahoo Finance quoteSummary API."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "quoteSummary": {
            "result": [
                {
                    "defaultKeyStatistics": {
                        "sharesOutstanding": {"raw": 15_000_000_000},
                        "beta": {"raw": 1.25},
                        "enterpriseValue": {"raw": 2_800_000_000_000},
                        "enterpriseToEbitda": {"raw": 22.5},
                        "trailingPE": {"raw": 28.3},
                        "forwardPE": {"raw": 25.1},
                    },
                    "financialData": {
                        "currentPrice": {"raw": 185.50},
                    },
                    "price": {
                        "marketCap": {"raw": 2_900_000_000_000},
                    },
                }
            ]
        }
    }
    resp.raise_for_status = MagicMock()
    return resp


@patch("pipeline.yahoo_finance._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_get_stock_info_returns_parsed_data(mock_guard_cls, mock_client):
    """Yahoo chart API -> parsed stock info dict."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.return_value = _mock_yahoo_chart_response()

    from pipeline.yahoo_finance import get_stock_info

    result = get_stock_info("AAPL")

    assert result is not None
    assert result["price"] == 185.50
    assert result["currency"] == "USD"
    assert result["name"] == "Apple Inc."
    assert result["exchange"] == "NMS"


@patch("pipeline.yahoo_finance._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_get_quote_summary_returns_multiples(mock_guard_cls, mock_client):
    """Yahoo quoteSummary API -> market cap, beta, EV/EBITDA."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.return_value = _mock_yahoo_summary_response()

    from pipeline.yahoo_finance import get_quote_summary

    result = get_quote_summary("AAPL")

    assert result is not None
    assert result["market_cap"] == 2_900_000_000_000
    assert result["beta"] == 1.25
    assert result["ev_ebitda"] == 22.5
    assert result["trailing_pe"] == 28.3


@patch("pipeline.yahoo_finance._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_get_stock_info_handles_http_error(mock_guard_cls, mock_client):
    """Yahoo Finance gracefully returns None on HTTP error."""
    import httpx

    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.side_effect = httpx.HTTPError("Connection refused")

    from pipeline.yahoo_finance import get_stock_info

    result = get_stock_info("INVALID")

    assert result is None


@patch("pipeline.yahoo_finance._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_get_stock_info_handles_empty_result(mock_guard_cls, mock_client):
    """Yahoo Finance returns None when chart has no result."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    resp = MagicMock()
    resp.json.return_value = {"chart": {"result": []}}
    resp.raise_for_status = MagicMock()
    mock_client.get.return_value = resp

    from pipeline.yahoo_finance import get_stock_info

    result = get_stock_info("AAPL")

    assert result is None


# ── SEC EDGAR ──


def _mock_edgar_company_tickers():
    """Build a mock httpx.Response for SEC company_tickers.json."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
        "2": {"cik_str": 1652044, "ticker": "GOOG", "title": "Alphabet Inc."},
    }
    resp.raise_for_status = MagicMock()
    return resp


def _mock_edgar_company_facts():
    """Build a mock httpx.Response for EDGAR company facts."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "val": 365_817_000_000,
                                "fy": 2022,
                                "fp": "FY",
                                "form": "10-K",
                                "end": "2022-09-24",
                                "filed": "2022-10-28",
                            },
                            {
                                "val": 394_328_000_000,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                            },
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "val": 94_680_000_000,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "end": "2023-09-30",
                                "filed": "2023-11-03",
                            },
                        ]
                    }
                },
            }
        },
    }
    resp.raise_for_status = MagicMock()
    return resp


@patch("pipeline.edgar_client._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_search_company_filters_by_ticker(mock_guard_cls, mock_client):
    """EDGAR search_company finds exact ticker match."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.return_value = _mock_edgar_company_tickers()

    from pipeline.edgar_client import search_company

    results = search_company("AAPL")

    assert len(results) == 1
    assert results[0]["ticker"] == "AAPL"
    assert results[0]["cik"] == "320193"
    assert results[0]["name"] == "Apple Inc."


@patch("pipeline.edgar_client._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_search_company_filters_by_name(mock_guard_cls, mock_client):
    """EDGAR search_company partial name match returns results."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.return_value = _mock_edgar_company_tickers()

    from pipeline.edgar_client import search_company

    results = search_company("microsoft")

    assert len(results) == 1
    assert results[0]["ticker"] == "MSFT"


@patch("pipeline.edgar_client._client")
@patch("pipeline.api_guard.ApiGuard.get")
def test_get_company_facts_returns_financials(mock_guard_cls, mock_client):
    """EDGAR company facts API -> parsed JSON with revenue data."""
    mock_guard = MagicMock()
    mock_guard_cls.return_value = mock_guard
    mock_guard.check.return_value = None
    mock_client.get.return_value = _mock_edgar_company_facts()

    from pipeline.edgar_client import get_company_facts

    facts = get_company_facts("320193")

    assert facts is not None
    assert facts["entityName"] == "Apple Inc."
    revenues = facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"]
    assert len(revenues) == 2
    assert revenues[-1]["val"] == 394_328_000_000


# ── Exchange Classification (no HTTP) ──


def test_classify_exchange_major():
    """Major exchanges -> listed."""
    from pipeline.yahoo_finance import classify_exchange

    assert classify_exchange("NMS", "NMS") == "상장"
    assert classify_exchange("NYSE", "NYQ") == "상장"
    assert classify_exchange("NASDAQ", "") == "상장"


def test_classify_exchange_otc():
    """OTC exchanges -> OTC."""
    from pipeline.yahoo_finance import classify_exchange

    assert classify_exchange("PNK", "PNK") == "OTC"
    assert classify_exchange("OTC Pink Sheets", "") == "OTC"


def test_classify_exchange_unknown():
    """Unknown exchanges -> unlisted."""
    from pipeline.yahoo_finance import classify_exchange

    assert classify_exchange("", "") == "비상장"
    assert classify_exchange("UNKNOWN", "XYZ") == "비상장"


# ── Peer Fetcher (cross-module integration) ──


@patch("pipeline.yahoo_finance.get_quote_summary")
def test_peer_fetcher_collects_multiples(mock_summary):
    """peer_fetcher.fetch_peer_multiples -> updated PeerCompany objects."""
    from schemas.models import PeerCompany

    mock_summary.return_value = {
        "market_cap": 100_000_000_000,
        "shares_outstanding": 1_000_000_000,
        "beta": 1.1,
        "enterprise_value": 120_000_000_000,
        "ev_ebitda": 15.5,
        "trailing_pe": 20.0,
        "forward_pe": 18.0,
        "price": 100.0,
    }

    peers = [
        PeerCompany(name="Apple", segment_code="TECH", ev_ebitda=0, ticker="AAPL"),
        PeerCompany(name="Microsoft", segment_code="TECH", ev_ebitda=0, ticker="MSFT"),
    ]

    from pipeline.peer_fetcher import fetch_peer_multiples

    result = fetch_peer_multiples(peers)

    assert len(result) == 2
    for peer in result:
        assert peer.ev_ebitda == 15.5
        assert peer.trailing_pe == 20.0
        assert peer.source == "yahoo"


@patch("pipeline.yahoo_finance.get_quote_summary")
def test_peer_fetcher_preserves_on_failure(mock_summary):
    """peer_fetcher preserves manual data when Yahoo lookup returns None."""
    from schemas.models import PeerCompany

    mock_summary.side_effect = [
        {
            "ev_ebitda": 12.0,
            "trailing_pe": 18.0,
            "market_cap": 50_000_000_000,
            "beta": 0.9,
            "enterprise_value": 60_000_000_000,
            "forward_pe": 16.0,
        },
        None,  # second peer fails
    ]

    peers = [
        PeerCompany(name="Apple", segment_code="TECH", ev_ebitda=8.0, ticker="AAPL"),
        PeerCompany(
            name="Unknown", segment_code="TECH", ev_ebitda=5.0, ticker="INVALID"
        ),
    ]

    from pipeline.peer_fetcher import fetch_peer_multiples

    result = fetch_peer_multiples(peers)

    assert len(result) == 2
    assert result[0].ev_ebitda == 12.0  # updated from Yahoo
    assert result[1].ev_ebitda == 5.0  # preserved original


# ── Ticker Validation ──


def test_yahoo_ticker_validation_rejects_injection():
    """Ticker validation prevents URL injection."""
    from pipeline.yahoo_finance import _validate_ticker

    with pytest.raises(ValueError):
        _validate_ticker("../../../etc/passwd")
    with pytest.raises(ValueError):
        _validate_ticker("AAPL; rm -rf /")
    with pytest.raises(ValueError):
        _validate_ticker("")


def test_yahoo_ticker_validation_accepts_valid():
    """Valid tickers pass validation."""
    from pipeline.yahoo_finance import _validate_ticker

    assert _validate_ticker("AAPL") == "AAPL"
    assert _validate_ticker("005930.KS") == "005930.KS"
    assert _validate_ticker("BRK-B") == "BRK-B"


def test_edgar_cik_validation_rejects_non_numeric():
    """CIK validation prevents non-numeric input."""
    from pipeline.edgar_client import _validate_cik

    with pytest.raises(ValueError):
        _validate_cik("abc")
    with pytest.raises(ValueError):
        _validate_cik("123; DROP TABLE")
