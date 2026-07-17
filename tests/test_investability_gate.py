"""Item 3 — investability validation gate (safety spine).

Fail ANY blocking check -> not investable -> draft: true -> orchestrator abstains.
"""

from __future__ import annotations

from engine.investability_gate import (
    GateInputs,
    apply_gate_to_profile,
    evaluate_investability,
    gate_inputs_from_profile,
)


def _clean_inputs(**over) -> GateInputs:
    base = dict(
        dcf_value=100.0,
        peer_median_value=100.0,
        quality_grade="B",
        method="sotp",
        segment_revenues=[60.0, 40.0],
        consolidated_revenue=100.0,
        placeholder_multiples=[],
        text="Final curated profile. Segments and multiples set.",
    )
    base.update(over)
    return GateInputs(**base)


def test_clean_profile_is_investable() -> None:
    report = evaluate_investability(_clean_inputs())
    assert report.investable is True
    assert report.draft is False
    assert report.blockers == []


def test_dcf_far_from_peer_blocks() -> None:
    report = evaluate_investability(_clean_inputs(dcf_value=200.0, peer_median_value=100.0))
    assert report.investable is False
    assert any("DCF/peer-median" in b for b in report.blockers)


def test_dcf_peer_band_edges() -> None:
    assert evaluate_investability(_clean_inputs(dcf_value=70.0, peer_median_value=100.0)).investable
    assert evaluate_investability(_clean_inputs(dcf_value=150.0, peer_median_value=100.0)).investable
    assert not evaluate_investability(_clean_inputs(dcf_value=69.0, peer_median_value=100.0)).investable
    assert not evaluate_investability(_clean_inputs(dcf_value=151.0, peer_median_value=100.0)).investable


def test_optionality_does_not_widen_dcf_peer_band() -> None:
    report = evaluate_investability(
        _clean_inputs(dcf_value=60.0, peer_median_value=100.0, optionality_flag=True)
    )
    assert report.investable is False
    assert any("optionality not auto-widened" in b for b in report.blockers)


def test_missing_peer_comp_blocks() -> None:
    report = evaluate_investability(_clean_inputs(peer_median_value=None))
    assert report.investable is False
    assert any("no peer-median comp" in b for b in report.blockers)


def test_missing_dcf_blocks_with_specific_finding() -> None:
    report = evaluate_investability(_clean_inputs(dcf_value=None))
    assert report.investable is False
    assert any("no DCF value" in b for b in report.blockers)


def test_grade_below_C_blocks() -> None:
    assert not evaluate_investability(_clean_inputs(quality_grade="D")).investable
    assert not evaluate_investability(_clean_inputs(quality_grade="F")).investable
    assert evaluate_investability(_clean_inputs(quality_grade="C")).investable


def test_segments_do_not_reconcile_blocks() -> None:
    report = evaluate_investability(_clean_inputs(segment_revenues=[60.0, 50.0]))  # sum 110 vs 100
    assert report.investable is False
    assert any("segment sum" in b for b in report.blockers)


def test_sotp_without_segments_blocks() -> None:
    report = evaluate_investability(_clean_inputs(method="sotp", segment_revenues=[]))
    assert report.investable is False
    assert any("no segment revenues" in b for b in report.blockers)


def test_placeholder_multiple_blocks() -> None:
    report = evaluate_investability(_clean_inputs(placeholder_multiples=["cloud.multiple=10.0(default)"]))
    assert report.investable is False


def test_todo_marker_blocks() -> None:
    report = evaluate_investability(_clean_inputs(text="# TODO: Define business segments"))
    assert report.investable is False
    assert any("TODO" in b for b in report.blockers)


def test_non_marker_placeholder_text_does_not_block() -> None:
    report = evaluate_investability(
        _clean_inputs(text='notes: "peer set is final; no placeholder remains"')
    )
    assert report.investable is True


def test_auto_generated_header_without_todo_does_not_block() -> None:
    report = evaluate_investability(
        _clean_inputs(text="# NAVER — Auto-generated draft profile (enhanced)")
    )
    assert report.investable is True


def test_explicit_draft_metadata_blocks() -> None:
    report = evaluate_investability(_clean_inputs(declared_draft=True))
    assert report.investable is False
    assert any("profile status" in blocker for blocker in report.blockers)


def test_curated_profile_treats_legacy_todo_as_warning() -> None:
    report = evaluate_investability(
        _clean_inputs(curated=True, text="# TODO: stale review note")
    )
    assert report.investable is True
    finding = next(f for f in report.findings if f.check == "no_todo_markers")
    assert finding.severity == "warn"


def test_apply_gate_sets_draft_true_on_fail() -> None:
    raw = {"ticker": "X", "draft": False}
    report = evaluate_investability(_clean_inputs(quality_grade="F"))
    updated = apply_gate_to_profile(raw, report)
    assert updated["draft"] is True
    assert raw["draft"] is False  # original untouched


def test_apply_gate_leaves_clean_profile() -> None:
    raw = {"ticker": "X"}
    report = evaluate_investability(_clean_inputs())
    updated = apply_gate_to_profile(raw, report)
    assert updated.get("draft") in (None, False)


def test_peer_beta_outlier_blocks_even_after_blume_consumption() -> None:
    report = evaluate_investability(_clean_inputs(peer_beta_status="outlier_high"))
    assert report.investable is False
    assert any("outlier_high" in blocker for blocker in report.blockers)


def test_unavailable_peer_beta_judgement_warns_without_blocking_legacy() -> None:
    report = evaluate_investability(_clean_inputs(peer_beta_status="insufficient_peers"))
    finding = next(f for f in report.findings if f.check == "peer_beta_range")
    assert finding.severity == "warn"
    assert report.investable is True


def test_from_profile_extracts_segments_and_placeholders() -> None:
    raw = {
        "primary_method": "sotp",
        "segments": {
            "a": {"revenue": 60.0, "multiple": 12.0},
            "b": {"revenue": 40.0, "multiple": 10.0},
        },
    }
    text = "# TODO: Set appropriate EV/EBITDA multiple"
    gi = gate_inputs_from_profile(
        raw, dcf_value=100.0, peer_median_value=100.0,
        quality_grade="B", consolidated_revenue=100.0, text=text,
    )
    assert gi.segment_revenues == [60.0, 40.0]
    assert any("b.multiple=10.0" in p for p in gi.placeholder_multiples)
    # and the assembled inputs fail the gate on the TODO + placeholder
    assert evaluate_investability(gi).investable is False
