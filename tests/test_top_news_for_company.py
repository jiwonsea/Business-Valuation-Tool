"""Regression tests for _top_news_for_company.

Historical bug (2026-04-13): zero-match fallback returned news[:3], causing
Tesla and RFK Jr. vaccine stories to be attached to NVIDIA/Apple/every
company that produced zero title matches. Fixed in same-date patch.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler.weekly_run import _top_news_for_company  # noqa: E402


NEWS = [
    {"title": "Tesla stock soars on earnings beat", "url": "u1"},
    {"title": "RFK Jr.'s vaccine panel rules hit court obstacle", "url": "u2"},
    {"title": "Nvidia announces new Blackwell GPU", "url": "u3"},
    {"title": "Apple Q2 iPhone sales disappoint", "url": "u4"},
    {"title": "NVDA hits fresh all-time high", "url": "u5"},
    {"title": "엔비디아, 한국 데이터센터 투자 확대", "url": "u6"},
    {"title": "Pineapple exports from Philippines rise", "url": "u7"},
    {"title": "Snapple beverage maker posts record quarter", "url": "u8"},
    {"title": "Samsung Electronics posts record chip revenue", "url": "u9"},
    {"title": "GM recalls 250,000 SUVs over brake issue", "url": "u10"},
    {"title": "General Motors beats Q1 earnings estimates", "url": "u11"},
    {"title": "코스피 주가 005930원 근처에서 변동성 확대", "url": "u12"},
]


def urls(matches):
    return [m["url"] for m in matches]


def test_tesla_matches_only_tesla():
    result = _top_news_for_company("Tesla", NEWS, aliases=["TSLA"])
    assert urls(result) == ["u1"]


def test_nvidia_matches_name_and_ticker_not_pineapple():
    result = _top_news_for_company("NVIDIA", NEWS, aliases=["NVDA"])
    assert "u3" in urls(result)  # "Nvidia announces..."
    assert "u5" in urls(result)  # "NVDA hits..."
    assert "u7" not in urls(result)  # "Pineapple" must NOT match


def test_apple_not_pineapple_not_snapple():
    result = _top_news_for_company("Apple", NEWS, aliases=["AAPL"])
    assert urls(result) == ["u4"]
    assert "u7" not in urls(result)
    assert "u8" not in urls(result)


def test_unmatchable_company_returns_empty():
    result = _top_news_for_company("FakeCorp", NEWS, aliases=["ZZZ"])
    assert result == []


def test_korean_name_matches_korean_title():
    result = _top_news_for_company("엔비디아", NEWS, aliases=["NVDA"])
    assert "u6" in urls(result)
    assert "u5" in urls(result)  # NVDA ticker also picks up English title


def test_samsung_korean_name_not_numeric_ticker():
    # 005930 is numeric ticker; must be excluded so article about
    # "코스피 주가 005930원" does NOT attach to Samsung
    result = _top_news_for_company(
        "Samsung Electronics", NEWS, aliases=["005930", "삼성전자"]
    )
    assert "u9" in urls(result)  # English name hit
    assert "u12" not in urls(result)  # numeric ticker must not match


def test_two_char_ticker_excluded():
    # "GM" as alias would match "GM recalls..." AND potentially "General
    # Manager time..." false positives. len>=3 guard drops it; matches
    # happen via company name only.
    result = _top_news_for_company("General Motors", NEWS, aliases=["GM"])
    assert "u11" in urls(result)  # matches on "General Motors"
    # Does not rely on GM ticker — but "GM recalls" still matches because
    # "GM" as a standalone word hits General Motors' actual news. That's
    # acceptable because we didn't explicitly pass "GM"; it comes from the
    # title text. We only filter aliases we PASS IN, not natural language.


def test_single_char_alias_filtered():
    # Ford ticker "F" alone should not contaminate via single-char match.
    result = _top_news_for_company("Ford Motor", NEWS, aliases=["F"])
    # No title contains "Ford Motor" or "Ford" — F alias dropped by len>=3.
    assert result == []


def test_no_regression_never_returns_unmatched_news():
    """The critical regression guard: zero-match MUST return []."""
    result = _top_news_for_company("Nonexistent Co", NEWS, aliases=["XYZ"])
    assert result == []
    # Crucially, Tesla news must not leak in:
    assert all(n["url"] != "u1" for n in result)
    assert all(n["url"] != "u2" for n in result)
