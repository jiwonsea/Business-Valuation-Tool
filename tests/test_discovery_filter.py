"""Regression tests for `_filter_companies` — ensures AI-hallucinated media
outlets and mis-classified companies don't reach the valuation phase.

Backstory: the 2026-04-12 weekly run had 일렉트렉 and 야후 파이낸스 listed as
US companies with `ticker=None`; they reached `_run_valuation` and failed.
"""

from discovery.discovery_engine import _filter_companies


def test_english_media_outlets_blocked_us():
    companies = [
        {"name": "Electrek", "ticker": None, "market": "US"},
        {"name": "Yahoo Finance", "ticker": None, "market": "US"},
        {"name": "Bloomberg", "ticker": None, "market": "US"},
        {"name": "Apple", "ticker": "AAPL", "market": "US"},
    ]
    result = _filter_companies(companies, "US")
    assert [c["name"] for c in result] == ["Apple"]


def test_korean_transliterations_of_media_blocked():
    companies = [
        {"name": "일렉트렉", "ticker": None, "market": "US"},
        {"name": "야후 파이낸스", "ticker": None, "market": "US"},
        {"name": "야후파이낸스", "ticker": None, "market": "US"},
    ]
    result = _filter_companies(companies, "US")
    assert result == []


def test_korean_named_us_company_blocked():
    companies = [
        {"name": "테슬라", "ticker": "TSLA", "market": "US"},
        {"name": "엔비디아", "ticker": "NVDA", "market": "US"},
    ]
    result = _filter_companies(companies, "US")
    assert result == []


def test_kr_market_requires_hangul_or_krx_ticker():
    companies = [
        {"name": "삼성전자", "ticker": "005930", "market": "KR"},
        {"name": "Tesla", "ticker": "TSLA", "market": "KR"},
    ]
    result = _filter_companies(companies, "KR")
    assert [c["name"] for c in result] == ["삼성전자"]
