"""Tests for db.backtest_repository query/parsing logic.

Focus: list_outcomes_needing_refresh — the OR-NULL filter and the nested
analysis_date extraction from the prediction_snapshots inner-join.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
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
        valuation_bucket="holding_governance_sensitive",
    )
    if signals_version_attr != "absent":
        result_kwargs["market_signals_version"] = signals_version_attr
    return vi, SimpleNamespace(**result_kwargs)


@pytest.mark.parametrize(
    "attr,expected",
    [
        ("absent", 1),  # no attribute → default 1
        (None, 1),  # explicit None → default 1
        (0, 0),  # explicit 0 → preserved (was the bug: coerced to 1)
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
    assert row["valuation_bucket"] == "holding_governance_sensitive"


def test_scenario_spread_audit_fields_are_persisted():
    vi, result = _make_vi_result("absent")
    result.scenario_multiples_clamped = True
    result.wide_scenario_spread_allowed = False
    result.scenario_spread_warnings = ["Bull GAME 3.00x → 2.00x"]
    client = _FakeClient([{"id": "snap-1"}])

    with patch.object(repo, "get_client", return_value=client):
        repo.save_prediction_snapshot(vi, result, valuation_id="val-1")

    upsert_call = next(c for c in client.query.calls if c[0] == "upsert")
    row = upsert_call[1][0]
    assert row["scenario_multiples_clamped"] is True
    assert row["wide_scenario_spread_allowed"] is False
    assert row["scenario_spread_warnings"] == ["Bull GAME 3.00x → 2.00x"]


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
    first_page = [_row(snap_date="2024-01-01", t12m=None) for _ in range(200)]
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


def test_pagination_warns_when_max_rows_reached(today, caplog, monkeypatch):
    """Hitting max_rows without a short page must emit a truncation warning."""
    # Shrink caps so the test runs fast.
    monkeypatch.setattr(
        repo, "list_outcomes_needing_refresh", repo.list_outcomes_needing_refresh
    )
    # Build pages that always fill page_size; loop will exit via max_rows.
    page_size = 200
    full_page = [_row(snap_date="2024-01-01", t12m=None) for _ in range(page_size)]
    # Enough full pages to blow past max_rows=5000 (25 full pages = 5000).
    pages = [full_page] * 30
    # Also provide a final never-reached page so .data access is safe.
    pages.append([])

    client = _FakePagedClient(pages)
    with patch.object(repo, "get_client", return_value=client):
        with caplog.at_level("WARNING"):
            repo.list_outcomes_needing_refresh(today)

    assert any(
        "truncated" in rec.message and "max_rows" in rec.message
        for rec in caplog.records
    )


# ── save_prediction_snapshot: log hygiene on failure ──


class _RaisingQuery:
    """FakeQuery that raises on execute() — simulates schema drift / PGRST204."""

    def __init__(self, exc):
        self._exc = exc

    def upsert(self, *a, **kw):
        return self

    def insert(self, *a, **kw):
        return self

    def execute(self):
        raise self._exc


class _RaisingClient:
    def __init__(self, exc):
        self._exc = exc

    def table(self, _name):
        return _RaisingQuery(self._exc)


def test_save_prediction_snapshot_logs_error_not_traceback(caplog):
    """Publication failures must log one ERROR without a traceback dump."""
    import logging

    # Simulate supabase-py raising with PGRST204-style message
    exc = RuntimeError(
        "{'code': 'PGRST204', 'message': \"Could not find the "
        "'valuation_bucket' column of 'prediction_snapshots' in the schema cache\"}"
    )
    vi, result = _make_vi_result("absent")
    client = _RaisingClient(exc)

    with patch.object(repo, "get_client", return_value=client):
        with caplog.at_level(logging.DEBUG, logger="db.backtest_repository"):
            uid = repo.save_prediction_snapshot(vi, result, valuation_id="val-x")

    assert uid is None

    repo_records = [r for r in caplog.records if r.name == "db.backtest_repository"]
    warnings = [r for r in repo_records if r.levelno == logging.WARNING]
    errors = [r for r in repo_records if r.levelno >= logging.ERROR]

    assert warnings == []
    assert len(errors) == 1
    msg = errors[0].getMessage()
    assert "Acme" in msg
    assert "RuntimeError" in msg
    assert errors[0].exc_info is None


@pytest.mark.parametrize("market", ["KR", "US", "JP"])
def test_native_snapshot_writer_reader_metrics_round_trip(market):
    """Use the writer's actual row, not a separately invented reader payload."""
    from backtest.dataset import _parse_scenarios
    from backtest.metrics import calc_forecast_price_error, calc_interval_score
    from backtest.models import BacktestRecord
    from calibration.tuner import _role_means, predict_with_probs

    fixture_path = Path(__file__).parent / "fixtures" / "j13_native_per_share.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    case = next(
        case for case in fixture["cases"] if case["company"]["market"] == market
    )
    company = SimpleNamespace(**case["company"])
    company.analysis_date = date.fromisoformat(company.analysis_date)
    scenarios = {sc["code"]: SimpleNamespace(**sc) for sc in case["scenarios"]}
    vi = SimpleNamespace(company=company, scenarios=scenarios)
    result_data = case["result"]
    result = SimpleNamespace(
        weighted_value=result_data["weighted_value"],
        wacc=SimpleNamespace(wacc=result_data["wacc"]),
        primary_method=result_data["primary_method"],
        market_comparison=SimpleNamespace(**result_data["market_comparison"]),
        scenarios=scenarios,
    )
    client = _FakeClient([{"id": "snap-1"}])
    with patch.object(repo, "get_client", return_value=client):
        assert repo.save_prediction_snapshot(vi, result, "v-1") == "snap-1"
    row = next(call for call in client.query.calls if call[0] == "upsert")[1][0]
    assert row["unit_multiplier"] == 1_000_000
    assert row["predicted_weighted_value"] == round(result.weighted_value, 4)
    record = BacktestRecord(
        snapshot_id="snap-1",
        valuation_id=row.get("valuation_id", ""),
        ticker=row["ticker"],
        market=row["market"],
        currency=row.get("currency", "KRW"),
        unit_multiplier=row.get("unit_multiplier", 1_000_000),
        company_name=row.get("company_name", ""),
        legal_status=row.get("legal_status", "상장"),
        analysis_date=date.fromisoformat(row["analysis_date"]),
        predicted_value=row.get("predicted_weighted_value", 0),
        predicted_gap_ratio=row.get("predicted_gap_ratio"),
        price_at_prediction=row.get("price_at_prediction"),
        wacc_pct=row.get("wacc_pct"),
        price_t0=row["price_at_prediction"],
        price_t6m=row["price_at_prediction"],
        scenarios=_parse_scenarios(row["scenario_values"]),
        primary_method=row.get("primary_method"),
        valuation_bucket=row.get("valuation_bucket", "plain_operating"),
        market_signals_version=row.get("market_signals_version", 0),
    )
    posts = [round(sc.post_dlom, 4) for sc in scenarios.values()]
    pres = [round(sc.pre_dlom, 4) for sc in scenarios.values()]
    assert record.predicted_value_native == round(result.weighted_value, 4)
    assert record.scenario_range_native() == (min(posts), max(posts))
    assert record.scenario_pre_dlom_range_native() == (min(pres), max(pres))
    error = calc_forecast_price_error([record], "t6m")
    price = row["price_at_prediction"]
    assert error["mape"] == pytest.approx(
        abs(record.predicted_value_native - price) / price
    )
    interval = calc_interval_score([record], "t6m")
    assert interval["coverage_rate"] == int(min(posts) <= price <= max(posts))
    assert interval["mean_interval_width"] == pytest.approx(
        (max(posts) - min(posts)) / record.predicted_value_native
    )
    means = _role_means(record)
    assert means["bear"] == min(posts)
    assert means["bull"] == max(posts)
    assert predict_with_probs(record, {"bull": 25, "base": 50, "bear": 25}) == (
        max(posts) * 0.25 + sorted(posts)[1] * 0.5 + min(posts) * 0.25
    )


@pytest.mark.parametrize("error_kind", ["valuation", "snapshot"])
def test_numeric_storage_failure_is_visible_as_error(error_kind, caplog):
    from db import repository

    vi, result = _make_vi_result("absent")
    vi.company.analysis_date = date(2026, 11, 3)
    vi.base_year = 2025
    vi.model_dump = lambda **kwargs: {}
    result.total_ev = 100
    result.model_dump = lambda **kwargs: {}
    client = _RaisingClient(
        RuntimeError("400 22P02 invalid input syntax for type bigint")
    )
    if error_kind == "snapshot":
        with patch.object(repo, "get_client", return_value=client):
            assert repo.save_prediction_snapshot(vi, result, "v-1") is None
    else:
        with patch.object(repository, "get_client", return_value=client):
            assert repository.save_valuation(vi, result) is None
    assert any(
        r.levelname == "ERROR" and "22P02" in r.getMessage() for r in caplog.records
    )


def test_effective_probability_and_input_survive_snapshot_round_trip():
    from backtest.dataset import _parse_scenarios

    vi, result = _make_vi_result("absent")
    vi.scenarios = {
        "Base": SimpleNamespace(
            name="Base",
            prob=50.05,
            growth_adj_pct=0,
            wacc_adj=0,
            terminal_growth_adj=0,
            market_sentiment_pct=0,
        )
    }
    result.scenarios = {
        "Base": SimpleNamespace(
            pre_dlom=3.25112345,
            post_dlom=3.25112345,
            prob_effective_pct=50.05 * 100 / 100.05,
        )
    }
    result.weighted_value = 3.25112345
    client = _FakeClient([{"id": "snap-1"}])
    with patch.object(repo, "get_client", return_value=client):
        repo.save_prediction_snapshot(vi, result, "v-1")
    row = next(c for c in client.query.calls if c[0] == "upsert")[1][0]
    sc = _parse_scenarios(row["scenario_values"])[0]
    assert sc.prob == result.scenarios["Base"].prob_effective_pct
    assert sc.prob_input == 50.05
    assert sc.post_dlom == 3.2511
    legacy = dict(row["scenario_values"]["Base"])
    legacy.pop("prob_input")
    assert _parse_scenarios({"Base": legacy})[0].prob_input is None
