"""Tests for pipeline/edgar_fetcher.py (NVDA-1a/1b).

Synthetic companyfacts blobs reproduce the exact failure modes found in the
NVDA history (REVIEW_nvidia_codex.md): as-filed facts coexisting with later
filings' split-adjusted comparatives for the same period, missing Q4 rows,
and calendar-mislabelled fiscal quarters.
"""

from __future__ import annotations

from datetime import date

import pytest

from pipeline.edgar_fetcher import (
    Fact,
    build_standalone_quarters,
    iter_facts,
    model_label_for_period,
)


def _fact(concept, unit, start, end, val, accn, form, filed, fy=None, fp=None, frame=None):
    return {
        "start": start,
        "end": end,
        "val": val,
        "accn": accn,
        "fy": fy,
        "fp": fp,
        "form": form,
        "filed": filed,
        "frame": frame,
    }


def _blob(concept_rows: dict[tuple[str, str], list[dict]]) -> dict:
    facts: dict = {}
    for (concept, unit), rows in concept_rows.items():
        facts.setdefault(concept, {"units": {}})["units"].setdefault(unit, []).extend(rows)
    return {"cik": 1045810, "facts": {"us-gaap": facts}}


# --- One NVDA-like fiscal year (FYE late Jan): Q1..Q3 as-filed 10-Qs, 10-K,
# --- and a LATER 10-Q carrying a split-adjusted comparative for Q3.
Q1 = ("2020-01-27", "2020-04-26")
Q2 = ("2020-04-27", "2020-07-26")
Q3 = ("2020-07-27", "2020-10-25")
YTD9 = ("2020-01-27", "2020-10-25")
FY = ("2020-01-27", "2021-01-31")

A_Q1 = "0001-20-0001"  # Q1 10-Q, filed 2020-05-21
A_Q2 = "0001-20-0002"  # Q2 10-Q, filed 2020-08-19
A_Q3 = "0001-20-0003"  # Q3 10-Q, filed 2020-11-18
A_FY = "0001-21-0004"  # 10-K,   filed 2021-02-26
A_LATER = "0001-21-0163"  # next-year Q3 10-Q, filed 2021-11-22 (post-4:1 comparatives)


def _nvda_like_blob() -> dict:
    rev = [
        _fact("Revenues", "USD", *Q1, 3080e6, A_Q1, "10-Q", "2020-05-21"),
        _fact("Revenues", "USD", *Q2, 3866e6, A_Q2, "10-Q", "2020-08-19"),
        _fact("Revenues", "USD", *Q3, 4726e6, A_Q3, "10-Q", "2020-11-18"),
        _fact("Revenues", "USD", *Q3, 4726e6, A_LATER, "10-Q", "2021-11-22"),
        _fact("Revenues", "USD", *YTD9, 11672e6, A_Q3, "10-Q", "2020-11-18"),
        _fact("Revenues", "USD", *FY, 16675e6, A_FY, "10-K", "2021-02-26"),
    ]
    ni = [
        _fact("NetIncomeLoss", "USD", *Q1, 917e6, A_Q1, "10-Q", "2020-05-21"),
        _fact("NetIncomeLoss", "USD", *Q2, 622e6, A_Q2, "10-Q", "2020-08-19"),
        _fact("NetIncomeLoss", "USD", *Q3, 1336e6, A_Q3, "10-Q", "2020-11-18"),
        _fact("NetIncomeLoss", "USD", *Q3, 1336e6, A_LATER, "10-Q", "2021-11-22"),
        _fact("NetIncomeLoss", "USD", *YTD9, 2875e6, A_Q3, "10-Q", "2020-11-18"),
        _fact("NetIncomeLoss", "USD", *FY, 4332e6, A_FY, "10-K", "2021-02-26"),
    ]
    shares = [
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *Q1, 624e6, A_Q1, "10-Q", "2020-05-21"),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *Q2, 627e6, A_Q2, "10-Q", "2020-08-19"),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *Q3, 630e6, A_Q3, "10-Q", "2020-11-18"),
        # Later filing's retroactively split-adjusted comparative (4:1).
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *Q3, 2520e6, A_LATER, "10-Q", "2021-11-22"),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *YTD9, 627e6, A_Q3, "10-Q", "2020-11-18"),
        _fact("WeightedAverageNumberOfDilutedSharesOutstanding", "shares", *FY, 629e6, A_FY, "10-K", "2021-02-26"),
    ]
    eps = [
        _fact("EarningsPerShareDiluted", "USD/shares", *Q3, 2.12, A_Q3, "10-Q", "2020-11-18"),
        # The mixed-basis trap: same period, post-split comparative.
        _fact("EarningsPerShareDiluted", "USD/shares", *Q3, 0.53, A_LATER, "10-Q", "2021-11-22"),
        _fact("EarningsPerShareDiluted", "USD/shares", *FY, 6.90, A_FY, "10-K", "2021-02-26"),
    ]
    return _blob(
        {
            ("Revenues", "USD"): rev,
            ("NetIncomeLoss", "USD"): ni,
            ("WeightedAverageNumberOfDilutedSharesOutstanding", "shares"): shares,
            ("EarningsPerShareDiluted", "USD/shares"): eps,
        }
    )


# ---------- 1a: fact context preserved, same-accession discipline ----------


def test_iter_facts_preserves_disclosure_context():
    facts = iter_facts(_nvda_like_blob(), ("EarningsPerShareDiluted",))
    q3 = [f for f in facts if f.end == date(2020, 10, 25) and f.duration_days < 120]
    assert {f.accn for f in q3} == {A_Q3, A_LATER}
    as_filed = next(f for f in q3 if f.accn == A_Q3)
    assert (as_filed.form, as_filed.filed, as_filed.val) == ("10-Q", date(2020, 11, 18), 2.12)


def test_standalone_quarter_uses_single_as_filed_accession():
    rows = build_standalone_quarters(_nvda_like_blob(), fiscal_year_end_month=1)
    q3 = next(r for r in rows if r["quarter_label"] == "2020Q3")
    # All items from the ORIGINAL 10-Q, not the later split-adjusted comparative.
    assert q3["accn"] == A_Q3
    assert q3["diluted_shares"] == pytest.approx(630e6)  # as-filed basis
    assert q3["eps_diluted_as_filed"] == pytest.approx(2.12)  # provenance only
    assert q3["revenue"] == pytest.approx(4726e6)
    assert q3["net_income"] == pytest.approx(1336e6)


def test_incomplete_accession_falls_through_to_one_that_has_all_items():
    blob = _nvda_like_blob()
    # Strip the as-filed Q3 shares fact: A_Q3 no longer covers all required
    # items, so the builder must fall through to A_LATER for the WHOLE row
    # (consistent basis) instead of mixing accessions.
    shares = blob["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"]
    shares[:] = [r for r in shares if not (r["accn"] == A_Q3 and r["start"] == Q3[0] and r["end"] == Q3[1])]
    rows = build_standalone_quarters(blob, fiscal_year_end_month=1)
    q3 = next(r for r in rows if r["quarter_label"] == "2020Q3")
    assert q3["accn"] == A_LATER
    assert q3["diluted_shares"] == pytest.approx(2520e6)
    assert q3["eps_diluted_as_filed"] == pytest.approx(0.53)  # same-accession EPS


# ---------- 1b: label contract, Q4 restoration, no Q3→Q1 joins ----------


def test_model_label_contract_jan_ending_fy():
    # NVDA fiscal FY(N) Qq -> model (N-1)Qq; Jan-ending quarter belongs to the
    # PREVIOUS calendar year's Q4.
    assert model_label_for_period(date(2020, 4, 26), 1) == "2020Q1"
    assert model_label_for_period(date(2021, 5, 2), 1) == "2021Q1"  # early-May Q1 end
    assert model_label_for_period(date(2020, 7, 26), 1) == "2020Q2"
    assert model_label_for_period(date(2021, 8, 1), 1) == "2021Q2"
    assert model_label_for_period(date(2020, 10, 25), 1) == "2020Q3"
    assert model_label_for_period(date(2021, 1, 31), 1) == "2020Q4"
    assert model_label_for_period(date(2026, 1, 25), 1) == "2025Q4"


def test_model_label_contract_calendar_fy():
    assert model_label_for_period(date(2020, 3, 31), 12) == "2020Q1"
    assert model_label_for_period(date(2020, 12, 31), 12) == "2020Q4"


def test_q4_restored_as_annual_minus_9m_from_original_filings():
    rows = build_standalone_quarters(_nvda_like_blob(), fiscal_year_end_month=1)
    labels = [r["quarter_label"] for r in rows]
    assert labels == ["2020Q1", "2020Q2", "2020Q3", "2020Q4"]  # contiguous, no Q3→Q1 join
    q4 = next(r for r in rows if r["quarter_label"] == "2020Q4")
    assert q4["q4_derived"] is True
    assert q4["revenue"] == pytest.approx(16675e6 - 11672e6)
    assert q4["net_income"] == pytest.approx(4332e6 - 2875e6)
    assert q4["diluted_shares"] == pytest.approx(4 * 629e6 - 3 * 627e6)
    assert A_FY in q4["accn"] and A_Q3 in q4["accn"]  # both vintages audited


def test_q4_share_derivation_guards_against_basis_mixing():
    blob = _nvda_like_blob()
    # Simulate a post-split 10-K against a pre-split Q3 10-Q: FY shares 4×
    # while 9M shares stay — 4×FY−3×9M explodes and must be rejected.
    for row in blob["facts"]["us-gaap"]["WeightedAverageNumberOfDilutedSharesOutstanding"]["units"]["shares"]:
        if row["accn"] == A_FY:
            row["val"] = 629e6 * 4
    with pytest.raises(ValueError, match="basis-mixed"):
        build_standalone_quarters(blob, fiscal_year_end_month=1)
