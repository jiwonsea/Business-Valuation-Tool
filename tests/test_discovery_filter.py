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


def test_blocklist_term_inside_a_longer_word_is_not_a_match():
    # "ft" (Financial Times) is a substring of every name below.
    names = [
        "Microsoft",
        "Lyft",
        "Kraft Heinz",
        "SoftBank Group",
        "Shift4 Payments",
        "DraftKings",
        "Fifth Third Bancorp",
        "Check Point Software Technologies",
    ]
    companies = [{"name": name, "ticker": "TICK", "market": "US"} for name in names]
    result = _filter_companies(companies, "US")
    assert [c["name"] for c in result] == names


def test_kr_listed_name_containing_a_blocklist_term_is_kept():
    companies = [{"name": "SOFTCAMP", "ticker": "258790", "market": "KR"}]
    result = _filter_companies(companies, "KR")
    assert [c["name"] for c in result] == ["SOFTCAMP"]


def test_blocklist_term_as_a_whole_word_is_still_blocked():
    names = [
        "FT",
        "The FT",
        "FT.com",
        "Financial Times",
        "Bloomberg News",
        "Yahoo! Finance",
        "The Wall Street Journal",
    ]
    companies = [{"name": name, "ticker": None, "market": "US"} for name in names]
    assert _filter_companies(companies, "US") == []


def test_media_names_joined_to_hangul_are_still_blocked():
    # Hangul has no word spacing: an outlet name runs straight into its suffix.
    names = ["CNBC코리아", "FT코리아", "한국경제신문", "블룸버그통신", "연합뉴스TV"]
    companies = [{"name": name, "ticker": None, "market": "KR"} for name in names]
    assert _filter_companies(companies, "KR") == []
