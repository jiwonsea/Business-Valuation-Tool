from __future__ import annotations

import pytest

from pipeline.dart_fetcher import extract_quarterly_actual


SEGMENT_SPLIT = {"dram": 0.70, "nand": 0.25, "other": 0.05}


def test_q4_is_annual_minus_q3_cumulative(sk_hynix_dart_raw, sk_hynix_dart_q3_raw):
    actual = extract_quarterly_actual(
        sk_hynix_dart_raw,
        "2024Q4",
        q3_raw_dart=sk_hynix_dart_q3_raw,
        segment_revenue_split=SEGMENT_SPLIT,
    )

    assert actual["revenue_total"] == pytest.approx(19_767.035)
    assert actual["gross_profit"] == pytest.approx(10_365.653)
    assert actual["operating_profit"] == pytest.approx(8_082.796)


def test_q3_uses_standalone_quarter_amount(sk_hynix_dart_q3_raw):
    actual = extract_quarterly_actual(
        sk_hynix_dart_q3_raw,
        "2024Q3",
        segment_revenue_split=SEGMENT_SPLIT,
    )

    assert actual["revenue_total"] == pytest.approx(17_573.069)
    assert [segment["segment_id"] for segment in actual["revenue_by_segment"]] == ["dram", "nand", "other"]
