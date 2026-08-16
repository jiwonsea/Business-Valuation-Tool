"""Shared pytest fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sk_hynix_dart_raw() -> dict:
    """Real DART fnlttSinglAcntAll response — SK Hynix 2024 annual (reprt_code 11011, CFS).

    thstrm_amount = full-year figure; thstrm_add_amount empty. Q4-standalone is
    derived as annual minus the Q3 cumulative (see sk_hynix_dart_q3_raw).
    """
    path = FIXTURES / "sk_hynix_2024q4_dart.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sk_hynix_dart_q3_raw() -> dict:
    """Real DART fnlttSinglAcntAll response — SK Hynix 2024 Q3 (reprt_code 11014, CFS).

    For income-statement rows (sj_div 'CIS'): thstrm_amount = current 3-month
    (quarter-standalone), thstrm_add_amount = cumulative (9-month). Basic/diluted
    per-share quarterly EPS are present (기본/희석주당분기순이익(손실)).
    """
    path = FIXTURES / "sk_hynix_2024q3_dart.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def sk_hynix_yahoo_raw() -> dict:
    """Real yfinance consensus snapshot for 000660.KS (captured 2026-05-30).

    Consensus covers only 0q/+1q (forward 2 quarters) + 0y/+1y. revenue_estimate
    is KRW absolute (divide by 1e9 for KRW_billion). NaN serialized as null.
    """
    path = FIXTURES / "sk_hynix_yahoo_estimates.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def profile_path() -> Path:
    return Path(__file__).resolve().parents[1] / "profiles" / "sk_hynix.yaml"
