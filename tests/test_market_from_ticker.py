"""Tests for _market_from_ticker — deterministic market derivation.

Fixes a bug where the discovery loop variable (KR/US) was used as the market
tag, even when the AI surfaced a US company from KR news. Now market is
derived from ticker format: 6-digit numeric -> KR, else US.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scheduler.weekly_run import _market_from_ticker  # noqa: E402


def test_kr_ticker_is_kr():
    assert _market_from_ticker("005930", fallback="US") == "KR"


def test_us_alpha_ticker_is_us():
    assert _market_from_ticker("NVDA", fallback="KR") == "US"


def test_us_dotted_ticker_is_us():
    assert _market_from_ticker("BRK.B", fallback="KR") == "US"


def test_single_letter_us_ticker_is_us():
    assert _market_from_ticker("F", fallback="KR") == "US"


def test_none_ticker_uses_fallback():
    assert _market_from_ticker(None, fallback="KR") == "KR"
    assert _market_from_ticker(None, fallback="US") == "US"


def test_empty_ticker_uses_fallback():
    assert _market_from_ticker("", fallback="KR") == "KR"


def test_short_numeric_not_kr():
    # KR tickers are exactly 6 digits — 4-digit numeric is not KR
    assert _market_from_ticker("1234", fallback="US") == "US"


def test_seven_digit_numeric_not_kr():
    assert _market_from_ticker("1234567", fallback="US") == "US"
