"""Integration tests for calibration.report — end-to-end markdown emission."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backtest.models import BacktestRecord, ScenarioSnapshot

from calibration.report import emit_yaml_diff, render_report
from calibration.tuner import Recommendation


def _scn(code: str, prob: float, post_dlom: int) -> ScenarioSnapshot:
    return ScenarioSnapshot(code=code, name=code, prob=prob, pre_dlom=post_dlom, post_dlom=post_dlom)


def _record(ticker: str, *, price_t12m: float, true_probs: tuple[int, int, int]) -> BacktestRecord:
    bull_v, base_v, bear_v = 200, 100, 50
    p_bull, p_base, p_bear = true_probs
    # Force price to align with a planted prob mix so the search has a real signal.
    return BacktestRecord(
        snapshot_id=f"snap-{ticker}",
        valuation_id=f"val-{ticker}",
        ticker=ticker,
        market="US",
        currency="USD",
        unit_multiplier=1,
        company_name="Test",
        legal_status="listed",
        analysis_date=date(2024, 1, 1),
        predicted_value=100,
        scenarios=[_scn("BEAR", 25, bear_v), _scn("BASE", 50, base_v), _scn("BULL", 25, bull_v)],
        primary_method="dcf_primary",
        price_t12m=price_t12m,
    )


def _planted_records(n: int, true_probs: tuple[int, int, int]) -> list[BacktestRecord]:
    p_bull, p_base, p_bear = true_probs
    price = (p_bull * 200 + p_base * 100 + p_bear * 50) / 100.0
    return [_record(f"T{i}", price_t12m=price + i * 0.1, true_probs=true_probs) for i in range(n)]


class TestEmitYamlDiff:
    def test_writes_dated_markdown_file(self, tmp_path: Path):
        records = _planted_records(30, (40, 35, 25))
        out = emit_yaml_diff(
            records,
            output_dir=tmp_path,
            report_date=date(2026, 4, 13),
        )
        assert out.exists()
        assert out.name == "2026-04-13.md"
        content = out.read_text(encoding="utf-8")
        assert "Calibration Report" in content
        assert "dcf_primary" in content
        assert "stable" in content

    def test_creates_output_dir_if_missing(self, tmp_path: Path):
        target = tmp_path / "nested" / "calibration"
        records = _planted_records(30, (45, 30, 25))
        out = emit_yaml_diff(records, output_dir=target, report_date=date(2026, 1, 1))
        assert out.parent == target
        assert target.exists()

    def test_empty_records_still_writes_file(self, tmp_path: Path):
        out = emit_yaml_diff([], output_dir=tmp_path, report_date=date(2026, 1, 1))
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "Total buckets: **0**" in content

    def test_produces_at_least_one_stable_recommendation(self, tmp_path: Path):
        records = _planted_records(30, (40, 35, 25))
        out = emit_yaml_diff(records, output_dir=tmp_path, report_date=date(2026, 4, 13))
        content = out.read_text(encoding="utf-8")
        # 30 records at t12m → stable bucket
        assert "| stable |" in content


class TestRenderReport:
    def test_renders_tier_counts(self):
        rec = Recommendation(
            bucket_key=("US", "dcf_primary", "t12m"),
            n=30,
            tier="stable",
            baseline={"bull": 25, "base": 50, "bear": 25},
            recommended={"bull": 40, "base": 35, "bear": 25},
            baseline_mape=0.20,
            recommended_mape=0.10,
            baseline_coverage=0.80,
            recommended_coverage=0.75,
            notes=[],
        )
        text = render_report([rec], report_date=date(2026, 4, 13))
        assert "stable: 1" in text
        assert "40/35/25" in text
        assert "20.0% → 10.0%" in text

    def test_insufficient_bucket_renders_em_dash(self):
        rec = Recommendation(
            bucket_key=("KR", "rim", "t12m"),
            n=3,
            tier="insufficient",
            baseline={"bull": 0, "base": 0, "bear": 0},
            recommended=None,
            baseline_mape=None,
            recommended_mape=None,
            baseline_coverage=None,
            recommended_coverage=None,
            notes=["sample size 3 below N≥10; recommendation suppressed"],
        )
        text = render_report([rec], report_date=date(2026, 4, 13))
        assert "insufficient" in text
        assert "suppressed" in text
        assert "—" in text
