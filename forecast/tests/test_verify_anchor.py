"""Tests for the offline G1 anchor reproduction gate."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from scripts.verify_anchor import (
    ANCHOR_REGISTRY_DATA,
    AnchorEntry,
    SupersededBy,
    load_registry,
    reproduce_anchor,
    verify_entry,
)


def test_registry_requires_all_provenance_metadata() -> None:
    required_metadata = (
        "source_artifact",
        "driving_profile_commit",
        "measured_at",
        "measured_env",
        "verified_at_commit",
    )
    for field in required_metadata:
        incomplete = deepcopy(ANCHOR_REGISTRY_DATA[0])
        del incomplete[field]
        with pytest.raises(ValidationError):
            AnchorEntry.model_validate(incomplete)


def test_reproduction_uses_cache_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.dart_fetcher as dart_fetcher

    calls = 0

    def reject_network(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        raise AssertionError("network call attempted")

    monkeypatch.setattr(dart_fetcher.httpx, "get", reject_network)
    entry = load_registry()[0]

    actual = reproduce_anchor(entry)

    assert calls == 0
    for field, expected in entry.expected.model_dump().items():
        assert actual[field] == pytest.approx(expected, rel=1e-9)


def test_superseded_entry_is_loud_skip_not_failure(capsys: pytest.CaptureFixture[str]) -> None:
    entry = load_registry()[0].model_copy(
        update={
            "superseded_by": SupersededBy(
                at_commit="abc1234",
                reason="forward window roll",
                date="2026-09-01",
            )
        }
    )

    assert verify_entry(entry) is True
    output = capsys.readouterr().out
    assert "SKIPPED" in output
    assert "abc1234" in output
    assert "forward window roll" in output


def test_anchor_drift_prints_required_remediation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    entry = load_registry()[0]
    drifted = entry.expected.model_dump()
    drifted["weighted_eps"] += 1.0
    monkeypatch.setattr("scripts.verify_anchor.reproduce_anchor", lambda _: drifted)

    assert verify_entry(entry) is False
    output = capsys.readouterr().out
    assert "FAIL: sk_hynix 2026Q2 anchor drift" in output
    assert "등급을 하향" in output
    assert "superseded_by" in output
    assert "제자리 수정 금지" in output
