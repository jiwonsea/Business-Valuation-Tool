"""Tests for db.backtest_repository query/parsing logic.

Focus: list_outcomes_needing_refresh — the OR-NULL filter and the nested
analysis_date extraction from the prediction_snapshots inner-join.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from db import backtest_repository as repo


# ── Fake Supabase query builder ──


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    """Records every chained call so tests can assert on the query shape."""

    def __init__(self, data):
        self._data = data
        self.calls: list[tuple[str, tuple, dict]] = []

    def _record(self, name, *args, **kwargs):
        self.calls.append((name, args, kwargs))
        return self

    def select(self, *a, **kw):
        return self._record("select", *a, **kw)

    def or_(self, *a, **kw):
        return self._record("or_", *a, **kw)

    def is_(self, *a, **kw):
        return self._record("is_", *a, **kw)

    def order(self, *a, **kw):
        return self._record("order", *a, **kw)

    def limit(self, *a, **kw):
        return self._record("limit", *a, **kw)

    def execute(self):
        return _FakeResponse(self._data)


class _FakeClient:
    def __init__(self, data):
        self.query = _FakeQuery(data)

    def table(self, _name):
        return self.query


# ── Tests ──


@pytest.fixture
def today():
    return date(2026, 4, 13)


def _row(
    *,
    snap_date: str | None = "2025-10-01",
    own_date: str | None = "2025-10-01",
    t3m=None,
    t6m=None,
    t12m=None,
    snap_as_list: bool = False,
):
    snap = {"analysis_date": snap_date} if snap_date is not None else {}
    return {
        "id": "outcome-1",
        "analysis_date": own_date,
        "price_t3m": t3m,
        "price_t6m": t6m,
        "price_t12m": t12m,
        "prediction_snapshots": [snap] if snap_as_list else snap,
    }


def _run(rows, today):
    client = _FakeClient(rows)
    with patch.object(repo, "get_client", return_value=client):
        result = repo.list_outcomes_needing_refresh(today)
    return result, client.query


def test_or_filter_uses_all_three_horizons(today):
    """Filter must catch rows where ANY of t3m/t6m/t12m is NULL."""
    _, q = _run([], today)
    or_calls = [c for c in q.calls if c[0] == "or_"]
    assert len(or_calls) == 1
    expr = or_calls[0][1][0]
    assert "price_t3m.is.null" in expr
    assert "price_t6m.is.null" in expr
    assert "price_t12m.is.null" in expr


def test_select_joins_prediction_snapshots_inner(today):
    _, q = _run([], today)
    sel = next(c for c in q.calls if c[0] == "select")
    assert "prediction_snapshots!inner(analysis_date)" in sel[1][0]


def test_long_horizon_null_with_t3m_filled_is_included(today):
    """t3m filled but t12m NULL → row must be returned (was the bug)."""
    rows = [_row(snap_date="2024-01-01", t3m=100.0, t6m=110.0, t12m=None)]
    out, _ = _run(rows, today)
    assert len(out) == 1


def test_future_horizon_excluded(today):
    """t3m NULL but analysis_date too recent → not yet due."""
    rows = [_row(snap_date="2026-04-01", t3m=None)]
    out, _ = _run(rows, today)
    assert out == []


def test_nested_analysis_date_preferred_over_top_level(today):
    """When join returns nested dict, that path is used."""
    # Nested date is past-due (>3m), top-level is future. Should include.
    rows = [
        _row(
            snap_date="2025-01-01",
            own_date="2027-01-01",
            t3m=None,
        )
    ]
    out, _ = _run(rows, today)
    assert len(out) == 1


def test_nested_as_list_handled(today):
    """Some PostgREST responses wrap embedded resources in a list."""
    rows = [_row(snap_date="2024-06-01", t12m=None, snap_as_list=True)]
    out, _ = _run(rows, today)
    assert len(out) == 1


def test_falls_back_to_top_level_when_nested_missing(today):
    """If join key missing in row, fall back to outcomes.analysis_date."""
    row = {
        "id": "outcome-x",
        "analysis_date": "2024-06-01",
        "price_t3m": None,
        "price_t6m": None,
        "price_t12m": None,
        "prediction_snapshots": None,
    }
    out, _ = _run([row], today)
    assert len(out) == 1


def test_invalid_date_skipped(today):
    rows = [_row(snap_date="not-a-date", own_date=None, t3m=None)]
    out, _ = _run(rows, today)
    assert out == []


def test_no_client_returns_empty(today):
    with patch.object(repo, "get_client", return_value=None):
        assert repo.list_outcomes_needing_refresh(today) == []
