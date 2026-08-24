"""Regression tests for visible SOTP scenario spread guardrails."""

import logging
from pathlib import Path

import yaml

from output.console_report import print_report
from valuation_runner import load_profile, run_valuation


_FIXTURE = Path(__file__).parent / "fixtures" / "msft_frozen.yaml"


def _wide_profile(tmp_path: Path, *, curated: bool, allow_wide: bool) -> Path:
    raw = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    raw["curated"] = curated
    raw["allow_wide_scenario_spread"] = allow_wide
    raw["scenarios"]["Bull"]["segment_multiples"]["PBP"] = 66.0
    path = tmp_path / "wide_scenario.yaml"
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def test_clamp_is_logged_reported_and_penalized(tmp_path, caplog, capsys):
    path = _wide_profile(tmp_path, curated=False, allow_wide=False)

    with caplog.at_level(logging.WARNING, logger="valuation_runner"):
        vi = load_profile(str(path))
    result = run_valuation(vi)
    print_report(vi, result)

    warning = vi.scenario_spread_warnings[0]
    stdout = capsys.readouterr().out
    assert vi.scenario_multiples_clamped is True
    assert vi.scenarios["Bull"].segment_multiples["PBP"] == 44.0
    assert "66.00x → 44.00x" in warning
    assert "3.00x → 2.00x" in warning
    assert warning in caplog.text
    assert stdout.index(f"⚠ {warning}") < stdout.index("[WACC]")
    assert result.quality is not None
    assert result.quality.scenario_consistency < 25
    assert any("multiple 클램프 발동" in item for item in result.quality.warnings)


def test_curated_profile_requires_explicit_wide_spread_opt_in(tmp_path):
    path = _wide_profile(tmp_path, curated=True, allow_wide=False)

    vi = load_profile(str(path))

    assert vi.scenario_multiples_clamped is True
    assert vi.scenarios["Bull"].segment_multiples["PBP"] == 44.0


def test_allow_wide_without_curated_still_clamps(tmp_path):
    path = _wide_profile(tmp_path, curated=False, allow_wide=True)

    vi = load_profile(str(path))

    assert vi.scenario_multiples_clamped is True
    assert vi.scenarios["Bull"].segment_multiples["PBP"] == 44.0


def test_curated_explicit_opt_in_warns_without_clamping(tmp_path, caplog):
    path = _wide_profile(tmp_path, curated=True, allow_wide=True)

    with caplog.at_level(logging.WARNING, logger="valuation_runner"):
        vi = load_profile(str(path))

    assert vi.scenario_multiples_clamped is False
    assert vi.scenarios["Bull"].segment_multiples["PBP"] == 66.0
    assert "curated wide spread 허용" in vi.scenario_spread_warnings[0]
    assert vi.scenario_spread_warnings[0] in caplog.text


def test_in_band_profile_has_no_spread_warning():
    vi = load_profile(str(_FIXTURE))
    result = run_valuation(vi)

    assert vi.scenario_multiples_clamped is False
    assert vi.scenario_spread_warnings == []
    assert result.scenario_multiples_clamped is False
    assert result.scenario_spread_warnings == []


def test_multi_segment_clamp_is_independent(tmp_path):
    raw = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    raw["scenarios"]["Bull"]["segment_multiples"]["PBP"] = 66.0
    raw["scenarios"]["Bull"]["segment_multiples"]["IC"] = 55.0
    path = tmp_path / "multi_segment_wide.yaml"
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    vi = load_profile(str(path))
    result = run_valuation(vi)

    assert vi.scenarios["Bull"].segment_multiples["PBP"] == 44.0
    assert vi.scenarios["Bull"].segment_multiples["IC"] == 36.0
    assert len(vi.scenario_spread_warnings) == 2
    assert result.scenario_spread_warnings == vi.scenario_spread_warnings


def test_kr_mid_band_profile_matches_explicit_million_unit(tmp_path):
    raw = yaml.safe_load(_FIXTURE.read_text(encoding="utf-8"))
    raw["company"].update(
        {"market": "KR", "currency": "KRW", "currency_unit": "백만원"}
    )
    raw["company"].pop("unit_multiplier", None)
    raw["consolidated"][2025]["revenue"] = 36_700

    auto_path = tmp_path / "auto_unit.yaml"
    auto_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    auto_vi = load_profile(str(auto_path))
    auto_result = run_valuation(auto_vi)

    raw["company"]["unit_multiplier"] = 1_000_000
    explicit_path = tmp_path / "explicit_unit.yaml"
    explicit_path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    explicit_result = run_valuation(load_profile(str(explicit_path)))

    assert auto_vi.company.unit_multiplier == 1_000_000
    assert auto_result.weighted_value == explicit_result.weighted_value
    assert {
        code: result.post_dlom for code, result in auto_result.scenarios.items()
    } == {code: result.post_dlom for code, result in explicit_result.scenarios.items()}
