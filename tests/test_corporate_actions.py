from datetime import date

import pytest
from pydantic import ValidationError

from schemas.models import CompanyProfile, CorporateAction
from valuation_runner import load_profile


def _company(**updates) -> CompanyProfile:
    values = {
        "name": "Test",
        "shares_total": 100,
        "shares_ordinary": 100,
        "treasury_shares": 10,
        "share_state_as_of": date(2026, 1, 1),
    }
    values.update(updates)
    return CompanyProfile(**values)


def test_sk_hynix_q2_roll_applies_each_share_state_delta():
    company = load_profile("profiles/000660.yaml").company
    state = company.share_state_at(date(2026, 7, 14))

    assert state.shares_total == 730_492_365
    assert state.shares_ordinary == 730_492_365
    assert state.treasury_shares == 11_010_845
    assert state.shares_outstanding == 719_481_520
    assert state.contains_derived_action is True
    assert company.shares_outstanding == 719_481_520


def test_split_uses_ratio_path_and_requires_zero_deltas():
    action = CorporateAction(
        effective_date=date(2026, 2, 1),
        kind="split",
        split_ratio=2.0,
        source="filing",
        confidence="confirmed",
    )
    state = _company(corporate_actions=[action]).share_state_at(date(2026, 2, 1))

    assert state.shares_total == 200
    assert state.shares_ordinary == 200
    assert state.treasury_shares == 20
    assert state.shares_outstanding == 180

    with pytest.raises(ValidationError, match="must not carry share deltas"):
        CorporateAction(
            effective_date=date(2026, 2, 1),
            kind="split",
            ordinary_issued_delta=1,
            split_ratio=2.0,
            source="filing",
            confidence="confirmed",
        )


def test_registry_requires_dated_base_state():
    action = CorporateAction(
        effective_date=date(2026, 2, 1),
        kind="buyback",
        treasury_delta=5,
        source="filing",
        confidence="confirmed",
    )

    with pytest.raises(ValidationError, match="share_state_as_of is required"):
        CompanyProfile(
            name="Test",
            shares_total=100,
            shares_ordinary=100,
            corporate_actions=[action],
        )
