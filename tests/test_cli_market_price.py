"""Regression tests for as-of price selection and reverse-DCF eligibility."""

from datetime import date, timedelta
from pathlib import Path

import pytest

import cli
from engine.gap_diagnostics import GapDiagnostic as EngineGapDiagnostic
from schemas.models import MarketComparisonResult, RelativeInputs
from valuation_runner import attach_gap_diagnostic, load_profile, run_valuation


PROFILES = Path(__file__).parent.parent / "profiles"


def _nexus():
    vi = load_profile(str(PROFILES / "nexus.yaml"))
    return vi, run_valuation(vi)


def test_profile_market_price_precedes_live_price(monkeypatch, caplog):
    vi, result = _nexus()
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 1_558.0)

    cli._fetch_and_compare_market_price(vi, result)

    assert result.market_comparison.market_price == 1_505
    assert result.market_comparison.price_source == "profile_as_of"
    assert result.market_comparison.price_as_of == date(2026, 7, 10)
    assert "as-of 1,505원 사용" in caplog.text
    assert "실시간 1,558원은 무시됨" in caplog.text


def test_live_price_flag_overrides_profile_price(monkeypatch):
    vi, result = _nexus()
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 1_558.0)

    cli._fetch_and_compare_market_price(vi, result, use_live_price=True)

    assert result.market_comparison.market_price == 1_558
    assert result.market_comparison.price_source == "live"
    assert result.market_comparison.price_as_of == date.today()


def test_automatic_snapshot_keeps_live_price_priority(monkeypatch, caplog):
    vi = load_profile(str(PROFILES / "aapl.yaml"))
    result = run_valuation(vi)
    assert vi.price_as_of is None
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 317.31)

    cli._fetch_and_compare_market_price(vi, result)

    assert result.market_comparison.market_price == 317.31
    assert result.market_comparison.price_source == "live"
    assert "자동수집 스냅샷" in caplog.text
    assert "price_as_of 선언" in caplog.text


def test_stale_as_of_price_warns_with_live_divergence(monkeypatch, caplog):
    vi, result = _nexus()
    vi = vi.model_copy(update={"price_as_of": date.today() - timedelta(days=8)})
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 1_558.0)

    cli._fetch_and_compare_market_price(vi, result)

    assert "실행일 대비 8일 경과" in caplog.text
    assert "실시간 대비 3.5% 차이" in caplog.text
    assert "최신 시장 비교는 --live-price" in caplog.text


def test_price_as_of_without_market_price_warns_and_uses_live(monkeypatch, caplog):
    vi, result = _nexus()
    vi = vi.model_copy(update={"market_price": None})
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 1_558.0)

    cli._fetch_and_compare_market_price(vi, result)

    assert result.market_comparison.market_price == 1_558
    assert result.market_comparison.price_source == "live"
    assert "유효한 market_price가 없습니다" in caplog.text


def test_missing_engine_dcf_suppresses_gap_diagnostic(caplog):
    vi, result = _nexus()
    assert result.dcf is None
    result.market_comparison = MarketComparisonResult(
        intrinsic_value=result.weighted_value,
        market_price=1_505,
        gap_ratio=(result.weighted_value - 1_505) / 1_505,
    )

    attach_gap_diagnostic(vi, result)

    assert result.gap_diagnostic is None
    assert "engine DCF result is unavailable" in caplog.text


def test_gap_diagnostic_market_ev_uses_valuation_shares(monkeypatch):
    vi = load_profile(str(PROFILES / "aapl.yaml"))
    reference_code = max(vi.scenarios, key=lambda code: vi.scenarios[code].prob)
    valuation_shares = vi.company.shares_outstanding + 123_456
    scenarios = dict(vi.scenarios)
    scenarios[reference_code] = scenarios[reference_code].model_copy(
        update={"shares": valuation_shares}
    )
    vi = vi.model_copy(
        update={
            "scenarios": scenarios,
            "relative_inputs": RelativeInputs(basis_aligned=True),
        }
    )
    result = run_valuation(vi)
    result.market_comparison = MarketComparisonResult(
        intrinsic_value=result.weighted_value,
        market_price=10.0,
        gap_ratio=(result.weighted_value - 10.0) / 10.0,
    )
    captured = {}

    def fake_diagnose_gap(**kwargs):
        captured.update(kwargs)
        return EngineGapDiagnostic(gap_pct=900.0, direction="market_discount")

    monkeypatch.setattr("engine.gap_diagnostics.diagnose_gap", fake_diagnose_gap)

    attach_gap_diagnostic(vi, result)

    expected_market_ev = (
        10.0 * valuation_shares / vi.company.unit_multiplier + max(vi.net_debt, 0)
    )
    assert captured["market_ev"] == pytest.approx(expected_market_ev)
    assert result.gap_diagnostic is not None


@pytest.mark.parametrize(
    "profile_name", ["aapl", "msft", "nvda_ttm", "nvda_fy27e", "tsla"]
)
def test_ev_based_profiles_remain_eligible_for_reverse_dcf(profile_name):
    vi = load_profile(str(PROFILES / f"{profile_name}.yaml"))
    result = run_valuation(vi)
    assert result.dcf is not None
    market_price = max(abs(result.weighted_value) * 2, 1)
    result.market_comparison = MarketComparisonResult(
        intrinsic_value=result.weighted_value,
        market_price=market_price,
        gap_ratio=(result.weighted_value - market_price) / market_price,
    )

    attach_gap_diagnostic(vi, result)

    assert result.gap_diagnostic is not None


def test_equity_based_segment_suppresses_reverse_dcf(caplog):
    vi = load_profile(str(PROFILES / "aapl.yaml"))
    only_code = next(iter(vi.segments))
    segments = dict(vi.segments)
    segments[only_code] = {**segments[only_code], "method": "pbv"}
    vi = vi.model_copy(update={"segments": segments})
    result = run_valuation(load_profile(str(PROFILES / "aapl.yaml")))
    result.market_comparison = MarketComparisonResult(
        intrinsic_value=100,
        market_price=200,
        gap_ratio=-0.5,
    )

    attach_gap_diagnostic(vi, result)

    assert result.gap_diagnostic is None
    assert "equity-based SOTP segment" in caplog.text


def test_raw_data_records_price_source_and_as_of(monkeypatch):
    from openpyxl import Workbook

    from output.sheets._ctx import make_ctx
    from output.sheets.raw_data import sheet_raw_data

    vi, result = _nexus()
    monkeypatch.setattr(cli, "_fetch_live_market_price", lambda _vi: 1_558.0)
    cli._fetch_and_compare_market_price(vi, result)
    wb = Workbook()
    wb.remove(wb.active)

    sheet_raw_data(make_ctx(vi, result, wb))

    values = {
        row[0].value: row[1].value
        for row in wb["Raw Data"].iter_rows()
        if row[0].value
    }
    assert values["기준 주가 (원)"] == 1_505
    assert values["주가 출처"] == "프로필 as-of 가격"
    assert values["주가 기준일"] == "2026-07-10"


def test_profile_yaml_atomic_rewrite_removes_stale_tail(tmp_path):
    import yaml

    from pipeline.profile_generator import _atomic_write_yaml

    path = tmp_path / "profile.yaml"
    path.write_bytes(b"legacy: value\n" + b"\x00" * 512)

    _atomic_write_yaml(str(path), {"market_price": 1_505})

    data = path.read_bytes()
    assert b"\x00" not in data
    assert yaml.safe_load(data.decode("utf-8")) == {"market_price": 1_505}
