"""Recurring fair-value exposure registry stays outside forecast EPS."""

from datetime import date
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from pipeline.ir_loader import load_profile
from schemas.models import RecurringFairValueBlock


def _block(**updates) -> RecurringFairValueBlock:
    data = {
        "instrument": "kioxia_spc2_cb",
        "accounting_basis": "FVPL",
        "carrying_value": 136_094,
        "carrying_value_as_of": date(2026, 3, 31),
        "observable_proxy": "Kioxia share price",
        "sensitivity": -0.8,
        "confidence": "confirmed",
        "source": "KIND 20260624002216",
    }
    data.update(updates)
    return RecurringFairValueBlock.model_validate(data)


def test_negative_proxy_sensitivity_is_preserved() -> None:
    assert _block().sensitivity == -0.8


def test_fair_value_amount_and_eps_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _block(fair_value_gain=10_190.8)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _block(eps_adjustment=11_054)


def test_registry_load_does_not_change_base_eps(tmp_path) -> None:
    profile_path = Path("profiles/sk_hynix.yaml")
    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    raw["recurring_fair_value_blocks"] = [_block().model_dump(mode="json")]
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    before = load_profile(profile_path)
    after = load_profile(path)
    assert after["shares"] == before["shares"]
    assert after["scenarios"] == before["scenarios"]
    assert after["recurring_fair_value_blocks"] == [_block()]


def test_same_instrument_cannot_be_event_and_recurring(tmp_path) -> None:
    raw = yaml.safe_load(Path("profiles/sk_hynix.yaml").read_text(encoding="utf-8"))
    raw["below_op_events"][0]["instrument"] = "kioxia_spc2_cb"
    raw["recurring_fair_value_blocks"] = [_block().model_dump(mode="json")]
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ValueError, match="both BelowOpEvent and RecurringFairValueBlock"):
        load_profile(path)


def test_pipeline_accepts_no_recurring_amounts() -> None:
    profile = load_profile(Path("profiles/sk_hynix.yaml"))
    assert profile["recurring_fair_value_blocks"] == []
