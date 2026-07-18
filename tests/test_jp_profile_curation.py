from __future__ import annotations

import statistics
from pathlib import Path

import yaml

from valuation_runner import load_profile, run_valuation


def test_jp_curated_profiles_are_not_drafts_and_have_sane_dcf_cross_check() -> None:
    for profile in ["profiles/7203_t.yaml", "profiles/6758_t.yaml"]:
        vi = load_profile(profile)
        result = run_valuation(vi)
        dcf = next(
            cv.per_share
            for cv in result.cross_validations
            if cv.method == "DCF (FCFF)"
        )
        peer_values = [
            cv.per_share
            for cv in result.cross_validations
            if cv.method not in {"SOTP (EV/EBITDA)", "SOTP (Mixed)", "DCF (FCFF)"}
            and cv.per_share > 0
        ]

        assert vi.company.market == "JP"
        assert vi.draft is False
        assert result.draft is False
        assert len(vi.segments) > 1
        assert peer_values
        assert 0.7 <= dcf / statistics.median(peer_values) <= 1.5


def test_explicit_draft_profile_runs_but_is_quality_f(tmp_path: Path) -> None:
    raw = yaml.safe_load(Path("profiles/7203_t.yaml").read_text(encoding="utf-8"))
    raw["draft"] = True
    path = tmp_path / "draft_7203.yaml"
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")

    vi = load_profile(str(path))
    result = run_valuation(vi)

    assert vi.draft is True
    assert result.draft is True
    assert result.quality is not None
    assert result.quality.draft is True
    assert result.quality.grade == "F"
    assert result.quality.total == 0


def test_profile_text_todo_reaches_production_investability_gate(
    tmp_path: Path, caplog
) -> None:
    caplog.set_level("INFO", logger="valuation_runner")
    raw = yaml.safe_load(Path("profiles/7203_t.yaml").read_text(encoding="utf-8"))
    first_segment = next(iter(raw["segments"].values()))
    first_segment["multiple"] = 10.0
    path = tmp_path / "todo_7203.yaml"
    text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
    path.write_text(text + "\n# TODO: replace placeholder multiple\n", encoding="utf-8")

    vi = load_profile(str(path))
    result = run_valuation(vi)

    assert "TODO: replace placeholder multiple" in vi.profile_text
    assert result.draft is True
    assert "todo" in caplog.text.lower() or "placeholder" in caplog.text.lower()
    assert result.quality.grade == "F"
    assert result.quality.total == 0
