"""Tests for db.backtest_repository query/parsing logic.

Focus: list_outcomes_needing_refresh — the OR-NULL filter and the nested
analysis_date extraction from the prediction_snapshots inner-join.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
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

    def upsert(self, *a, **kw):
        return self._record("upsert", *a, **kw)

    def insert(self, *a, **kw):
        return self._record("insert", *a, **kw)

    def update(self, *a, **kw):
        return self._record("update", *a, **kw)

    def eq(self, *a, **kw):
        return self._record("eq", *a, **kw)

    def is_(self, *a, **kw):
        return self._record("is_", *a, **kw)

    def order(self, *a, **kw):
        return self._record("order", *a, **kw)

    def limit(self, *a, **kw):
        return self._record("limit", *a, **kw)

    def range(self, *a, **kw):
        return self._record("range", *a, **kw)

    def execute(self):
        return _FakeResponse(self._data)


class _FakeClient:
    def __init__(self, data):
        self.query = _FakeQuery(data)

    def table(self, _name):
        return self.query


class _FakePagedQuery(_FakeQuery):
    """Serves distinct data slices per range() call to simulate paging."""

    def __init__(self, pages):
        super().__init__([])
        self._pages = list(pages)
        self._idx = 0

    def execute(self):
        if self._idx < len(self._pages):
            data = self._pages[self._idx]
            self._idx += 1
        else:
            data = []
        return _FakeResponse(data)


class _FakePagedClient:
    def __init__(self, pages):
        self.query = _FakePagedQuery(pages)

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


# ── save_prediction_snapshot: market_signals_version semantics ──


def _make_vi_result(signals_version_attr):
    """Build minimal vi/result namespaces. `signals_version_attr` is either
    a sentinel 'absent' meaning do not set the attribute at all, or the
    value to assign (including None / 0 / ints)."""
    vi = SimpleNamespace(
        scenarios={},
        company=SimpleNamespace(
            name="Acme",
            ticker="ACM",
            market="US",
            currency="USD",
            unit_multiplier=1,
            legal_status="listed",
            analysis_date=date(2026, 1, 1),
        ),
    )
    result_kwargs = dict(
        scenarios={},
        weighted_value=100.0,
        market_comparison=None,
        wacc=SimpleNamespace(wacc=0.09),
        primary_method="sotp",
    )
    if signals_version_attr != "absent":
        result_kwargs["market_signals_version"] = signals_version_attr
    return vi, SimpleNamespace(**result_kwargs)


@pytest.mark.parametrize(
    "attr,expected",
    [
        ("absent", 1),  # no attribute → default 1
        (None, 1),      # explicit None → default 1
        (0, 0),         # explicit 0 → preserved (was the bug: coerced to 1)
        (1, 1),
        (2, 2),
    ],
)
def test_market_signals_version_preserves_explicit_zero(attr, expected):
    vi, result = _make_vi_result(attr)
    client = _FakeClient([{"id": "snap-1"}])
    with patch.object(repo, "get_client", return_value=client):
        repo.save_prediction_snapshot(vi, result, valuation_id="val-1")

    upsert_call = next(c for c in client.query.calls if c[0] == "upsert")
    row = upsert_call[1][0]
    assert row["market_signals_version"] == expected


# ── update_backtest_prices: zero-row detection ──


def test_update_backtest_prices_returns_false_for_zero_rows(caplog):
    client = _FakeClient([])  # empty data → 0 rows affected
    with patch.object(repo, "get_client", return_value=client):
        with caplog.at_level("WARNING"):
            ok = repo.update_backtest_prices("missing-id", {"price_t3m": 42.0})
    assert ok is False
    assert any("0 rows" in rec.message for rec in caplog.records)


def test_update_backtest_prices_returns_true_when_row_updated():
    client = _FakeClient([{"id": "outcome-1"}])
    with patch.object(repo, "get_client", return_value=client):
        ok = repo.update_backtest_prices("outcome-1", {"price_t3m": 42.0})
    assert ok is True


def test_update_backtest_prices_uses_count_when_data_empty():
    """Some Supabase clients return count separately from data."""
    class _Resp:
        def __init__(self):
            self.data = []
            self.count = 1

    class _Q(_FakeQuery):
        def execute(self):  # type: ignore[override]
            return _Resp()

    class _C:
        def __init__(self):
            self.query = _Q([])

        def table(self, _):
            return self.query

    client = _C()
    with patch.object(repo, "get_client", return_value=client):
        ok = repo.update_backtest_prices("outcome-1", {"price_t3m": 42.0})
    assert ok is True


# ── list_outcomes_needing_refresh: pagination ──


def test_pagination_fetches_subsequent_pages(today):
    """First page full (200) must trigger a second fetch."""
    first_page = [
        _row(snap_date="2024-01-01", t12m=None) for _ in range(200)
    ]
    # Rewrite ids so results remain distinct
    for i, r in enumerate(first_page):
        r["id"] = f"outcome-p1-{i}"
    second_page = [_row(snap_date="2024-01-01", t12m=None)]
    second_page[0]["id"] = "outcome-p2-0"

    client = _FakePagedClient([first_page, second_page])
    with patch.object(repo, "get_client", return_value=client):
        out = repo.list_outcomes_needing_refresh(today)

    range_calls = [c for c in client.query.calls if c[0] == "range"]
    assert len(range_calls) >= 2
    assert range_calls[0][1] == (0, 199)
    assert range_calls[1][1] == (200, 399)
    assert len(out) == 201


def test_pagination_stops_when_page_short(today):
    """Partial first page → no second fetch."""
    page = [_row(snap_date="2024-01-01", t12m=None)]
    client = _FakePagedClient([page])
    with patch.object(repo, "get_client", return_value=client):
        repo.list_outcomes_needing_refresh(today)
    range_calls = [c for c in client.query.calls if c[0] == "range"]
    assert len(range_calls) == 1
