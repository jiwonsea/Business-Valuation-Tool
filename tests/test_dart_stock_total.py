"""Regression tests for pipeline.dart_client.get_stock_total_info.

Bug: stockTotqySttus.json returns 4 rows (보통주 / 우선주 / 합계 / 비고).
The 비고 row's tesstk_co holds multi-line free text (treasury-stock
history), which crashed _parse_dart_number with ValueError on SK hynix
("주식수 정규화 0% / 주식 API 오류 10/0" in the multi-year pilot).

Fix under test: the row loop skips non-보통주/우선주 rows before parsing.
_parse_dart_number stays fail-closed: only blank/'-' map to 0, any other
non-numeric string raises ValueError (a silent 0 on a valid share-class
row would understate treasury shares without any signal to valuation).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

import pipeline.dart_client as dart_client
from pipeline.api_guard import ApiGuard
from pipeline.dart_client import _parse_dart_number, get_stock_total_info


@pytest.fixture(autouse=True)
def _reset_guard(tmp_path: Path, monkeypatch):
    """Reset ApiGuard singleton, redirect usage file, provide API key."""
    import pipeline.api_guard as mod

    ApiGuard._reset_singleton()
    monkeypatch.setattr(mod, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(mod, "_USAGE_FILE", tmp_path / "api_usage.json")
    monkeypatch.setattr(mod, "_USAGE_LOCK", tmp_path / "api_usage.lock")
    monkeypatch.setenv("DART_API_KEY", "test-key")
    yield
    ApiGuard._reset_singleton()


def _mock_httpx_get(monkeypatch, payload: dict) -> None:
    """Patch dart_client.httpx.get to return a canned JSON response."""
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    monkeypatch.setattr(dart_client.httpx, "get", MagicMock(return_value=resp))


# ---------------------------------------------------------------------------
# Fixtures: real-shaped stockTotqySttus payloads
# ---------------------------------------------------------------------------

# SK hynix FY2024 annual report shape: no preferred shares ("-"), 비고 row
# carries multi-line treasury-stock history as free text.
SK_HYNIX_REMARKS = (
    "-. 2014.04.22 주식교환\n"
    "-. 2015.07.23~10.01 장내취득\n"
    "-. 2017.11.08~2018.01.30 장내취득\n"
    "-. 2019.01.02 자기주식 처분(상여)"
)

SK_HYNIX_PAYLOAD = {
    "status": "000",
    "message": "정상",
    "list": [
        {
            "corp_name": "SK하이닉스",
            "se": "보통주",
            "isu_stock_totqy": "728,002,365",
            "istc_totqy": "728,002,365",
            "tesstk_co": "26,310,845",
            "distb_stock_co": "701,691,520",
        },
        {
            "corp_name": "SK하이닉스",
            "se": "우선주",
            "isu_stock_totqy": "-",
            "istc_totqy": "-",
            "tesstk_co": "-",
            "distb_stock_co": "-",
        },
        {
            "corp_name": "SK하이닉스",
            "se": "합계",
            "isu_stock_totqy": "728,002,365",
            "istc_totqy": "728,002,365",
            "tesstk_co": "26,310,845",
            "distb_stock_co": "701,691,520",
        },
        {
            "corp_name": "SK하이닉스",
            "se": "비고",
            "isu_stock_totqy": "-",
            "istc_totqy": "-",
            "tesstk_co": SK_HYNIX_REMARKS,
            "distb_stock_co": "-",
        },
    ],
}

# Samsung Electronics-like shape: both ordinary and preferred share classes.
SAMSUNG_LIKE_PAYLOAD = {
    "status": "000",
    "message": "정상",
    "list": [
        {
            "se": "보통주",
            "istc_totqy": "5,969,782,550",
            "tesstk_co": "24,000,000",
        },
        {
            "se": "우선주",
            "istc_totqy": "822,886,700",
            "tesstk_co": "3,000,000",
        },
        {
            "se": "합계",
            "istc_totqy": "6,792,669,250",
            "tesstk_co": "27,000,000",
        },
        {
            "se": "비고",
            "istc_totqy": "-",
            "tesstk_co": "-. 2018.05.04 액면분할(50:1)",
        },
    ],
}


# ---------------------------------------------------------------------------
# get_stock_total_info
# ---------------------------------------------------------------------------


class TestGetStockTotalInfo:
    def test_sk_hynix_remarks_row_does_not_crash(self, monkeypatch):
        """비고 row free text must not raise ValueError (SK hynix regression)."""
        _mock_httpx_get(monkeypatch, SK_HYNIX_PAYLOAD)

        result = get_stock_total_info("00164779", 2024)

        assert result is not None
        assert result["shares_ordinary"] == 728_002_365
        assert result["treasury_ordinary"] == 26_310_845
        assert result["shares_preferred"] == 0
        assert result["treasury_preferred"] == 0

    def test_preferred_share_company_split(self, monkeypatch):
        """Ordinary vs preferred rows stay separated (Samsung-like case)."""
        _mock_httpx_get(monkeypatch, SAMSUNG_LIKE_PAYLOAD)

        result = get_stock_total_info("00126380", 2024)

        assert result is not None
        assert result["shares_ordinary"] == 5_969_782_550
        assert result["treasury_ordinary"] == 24_000_000
        assert result["shares_preferred"] == 822_886_700
        assert result["treasury_preferred"] == 3_000_000

    def test_sum_row_not_double_counted(self, monkeypatch):
        """합계 row must be skipped, not folded into either share class."""
        _mock_httpx_get(monkeypatch, SAMSUNG_LIKE_PAYLOAD)

        result = get_stock_total_info("00126380", 2024)

        assert result is not None
        total = result["shares_ordinary"] + result["shares_preferred"]
        assert total == 6_792_669_250  # equals 합계, proving no double count

    def test_non_ok_status_returns_none(self, monkeypatch):
        _mock_httpx_get(monkeypatch, {"status": "013", "message": "no data"})

        assert get_stock_total_info("00000000", 2024) is None


# ---------------------------------------------------------------------------
# _parse_dart_number fail-closed behavior
# ---------------------------------------------------------------------------


class TestParseDartNumber:
    def test_normal_number(self):
        assert _parse_dart_number("5,969,782,550") == 5_969_782_550

    def test_dash_and_empty(self):
        assert _parse_dart_number("-") == 0
        assert _parse_dart_number("") == 0
        assert _parse_dart_number("  ") == 0

    def test_free_text_raises_instead_of_silent_zero(self):
        """Fail-closed: unexpected text on a share-class row must raise,
        not silently become 0 (which would understate treasury shares).
        The 비고-row crash is prevented by the caller's row filter instead."""
        with pytest.raises(ValueError):
            _parse_dart_number(SK_HYNIX_REMARKS)
