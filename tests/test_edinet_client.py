from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

from pipeline import edinet_client
from pipeline.data_fetcher import DataFetcher, _is_jp_ticker


FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_edinet_xbrl_ifrs_tags_to_jpy_millions() -> None:
    xml = (FIXTURES / "edinet_toyota_mini.xbrl").read_text(encoding="utf-8")

    parsed = edinet_client.parse_xbrl_text(xml)

    row = parsed[2025]
    assert row["revenue"] == 48_036_700
    assert row["op"] == 5_352_900
    assert row["net_income"] == 4_765_100
    assert row["assets"] == 90_000_000
    assert row["equity"] == 35_000_000
    assert row["dep"] == 2_100_000
    assert row["capex"] == 2_200_000
    assert row["gross_borr"] == 28_000_000
    assert row["net_borr"] == 19_000_000
    assert row["de_ratio"] == 80.0


def test_parse_edinet_xbrl_zip_selects_public_doc() -> None:
    xml = (FIXTURES / "edinet_toyota_mini.xbrl").read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("XBRL/PublicDoc/toyota.xbrl", xml)

    parsed = edinet_client.parse_xbrl_zip(buf.getvalue())

    assert parsed[2025]["revenue"] == 48_036_700


def test_document_lookup_normalizes_five_digit_sec_code(monkeypatch) -> None:
    rows_by_date = {
        date(2026, 6, 20): [
            {
                "docID": "S100TEST",
                "edinetCode": "E02144",
                "secCode": "72030",
                "filerName": "Toyota Motor Corporation",
                "docTypeCode": "120",
                "docDescription": "有価証券報告書",
                "periodEnd": "2026-03-31",
                "submitDateTime": "2026-06-20 15:00",
            }
        ]
    }

    monkeypatch.setattr(
        edinet_client, "_cached_document_list", lambda d: rows_by_date.get(d, [])
    )

    doc = edinet_client.find_latest_document(
        "7203", as_of=date(2026, 6, 21), days_back=3
    )

    assert doc is not None
    assert doc.edinet_code == "E02144"
    assert doc.sec_code == "72030"


def test_data_fetcher_routes_jp_to_edinet(monkeypatch) -> None:
    import pipeline.data_fetcher as data_fetcher

    monkeypatch.setattr(data_fetcher, "yfinance_fetcher", None)
    monkeypatch.setattr(edinet_client, "get_edinet_code", lambda code: "E02144")
    monkeypatch.setattr(
        edinet_client,
        "fetch_financials",
        lambda code, years=None: {
            2025: {
                "revenue": 1,
                "op": 1,
                "net_income": 1,
                "assets": 1,
                "liabilities": 1,
                "equity": 1,
            }
        },
    )

    fetcher = DataFetcher()
    identity = fetcher.identify("7203", market_hint="JP")

    assert identity is not None
    assert identity.market == "JP"
    assert identity.ticker == "7203.T"
    assert identity.edinet_code == "E02144"
    assert fetcher.fetch_financials(identity) == {
        2025: {
            "revenue": 1,
            "op": 1,
            "net_income": 1,
            "assets": 1,
            "liabilities": 1,
            "equity": 1,
        }
    }


def test_jp_ticker_detection() -> None:
    assert _is_jp_ticker("7203")
    assert _is_jp_ticker("6758.T")
    assert not _is_jp_ticker("005930")
    assert not _is_jp_ticker("AAPL")
