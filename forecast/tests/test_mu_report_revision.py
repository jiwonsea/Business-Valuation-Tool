"""R20 pre-render checks: no report, spreadsheet or chart image is generated."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from forecast.scripts.mu_report import build
from forecast.scripts.mu_report.charts import chart_data_contract, e2b_specs
from forecast.scripts.mu_report.gates import (
    GateError, gate_g13_charts, gate_g13c_chart_semantics, gate_g15_parity,
    gate_g15b_localized_ui, gate_g16_caption, gate_narrative_contract,
)
from forecast.scripts.mu_report.render import _html_from_markdown, _locale, render_markdown
from forecast.scripts.mu_report.revision import RANGE_J, draw_revision_chart


@pytest.fixture(scope="session")
def prepared():
    return build._run_e2b_preflight()


def contracts(manifest, locale):
    return {spec.chart_id: chart_data_contract(manifest, spec, locale)
            for spec in e2b_specs(manifest, locale, _locale(locale))}


def test_r20_cli_stops_without_rendering_or_conflict_read(prepared, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("preflight must not render or read conflict confirmation")

    monkeypatch.setattr(build, "_run_e2b_preflight", lambda: prepared)
    monkeypatch.setattr(build, "render_e2b_bundle", forbidden)
    monkeypatch.setattr("forecast.scripts.mu_report.inputs.load_conflict_confirmation", forbidden)
    monkeypatch.setattr("sys.argv", ["build.py", "--phase", "E2-B", "--edition", "1", "--preflight-only"])
    assert build.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] == "STOPPED_PRE_RENDER_R20"


def test_r20_sources_narrative_and_existing_values_are_unchanged(prepared):
    path = Path("forecast/inputs/mu_fy2026q4_narrative_ed1.yaml")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == build.E2B_BASELINES[path.as_posix()]
    original = json.loads(Path("forecast/reports/mu_report_fy2026q4_ed1_manifest.json").read_text(encoding="utf-8"))
    for key, fact in original["facts"].items():
        assert prepared["manifest"].fact(key).raw_value == fact["raw_value"], key
    assert len(prepared["fact_bindings"]) == 19
    for key, expected in (("derived.gm_beat.FQ2-26", 7.41), ("derived.gm_beat.FQ3-26", 3.56), ("derived.gm_beat.FQ4-26", .7561636763)):
        assert prepared["fact_bindings"][key] == pytest.approx(expected)


def test_r20_all_chart_data_and_caption_contracts(prepared):
    manifest = prepared["manifest"]
    for locale in ("ko", "en"):
        charts = contracts(manifest, locale)
        assert len(charts) == 16
        gate_g13_charts(charts)
        gate_g13c_chart_semantics(manifest, charts)
        for chart in charts.values():
            gate_g16_caption(chart["caption"])
    assert prepared["c14_missing"] == []


@pytest.mark.parametrize("chart_id", ["09_gm_beat_compression", "10_price_bit_ranges", "11_eps_error_waterfall", "12_fq1_guidance_comparison", "13_scenario_sensitivity_eps", "14_opex_net_capex_trend", "15_operating_income_waterfall", "16_sca_structure"])
def test_r20_missing_new_chart_is_rejected(prepared, chart_id):
    charts = contracts(prepared["manifest"], "en")
    del charts[chart_id]
    with pytest.raises(GateError, match="sixteen|chart set"):
        gate_g13_charts(charts)


def test_r20_c10_j_table_and_altered_endpoint_are_rejected(prepared):
    manifest = copy.deepcopy(prepared["manifest"])
    charts = contracts(manifest, "ko")
    chart = charts["10_price_bit_ranges"]
    assert "J(판단)" in chart["footnote"]
    for low, high in RANGE_J.values():
        assert f"{low}–{high}%" in chart["footnote"]
    key = chart["fact_ids"][0]
    manifest.facts[key] = replace(manifest.fact(key), raw_value=40)
    charts = contracts(manifest, "ko")
    with pytest.raises(GateError, match="approved J conversion"):
        gate_g13c_chart_semantics(manifest, charts)


def test_r20_c14_missing_source_is_blank_with_reason(prepared):
    manifest = copy.deepcopy(prepared["manifest"])
    del manifest.facts["cf.net_capex.FY2025Q2.A"]
    manifest.metadata["c14_missing"] = [{"period": "FY2025Q2", "series": "net_capex", "reason": "No unique quarterly net-capex row in pinned release"}]
    spec = next(spec for spec in e2b_specs(manifest, "ko", _locale("ko")) if spec.chart_id.startswith("14_"))
    data = chart_data_contract(manifest, spec, "ko")
    assert "FY2025Q2/net_capex" in data["footnote"]
    assert "빈칸" in data["footnote"] and "보간하지" in data["footnote"]
    assert "pin된 보도자료" in data["footnote"]
    gate_g13c_chart_semantics(manifest, contracts(manifest, "ko"))
    axis = MagicMock()
    draw_revision_chart(None, axis, manifest, spec, data["values"], "ko")
    capex_series = axis.plot.call_args_list[1].args[1]
    assert math.isnan(capex_series[5])
    missing_note = contracts(manifest, "ko")
    missing_note[spec.chart_id]["footnote"] = ""
    with pytest.raises(GateError, match="absent from footnote"):
        gate_g13c_chart_semantics(manifest, missing_note)


def test_r20_frozen_guidance_and_sensitivity_are_not_rle_paths(prepared):
    manifest = prepared["manifest"]
    assert [manifest.fact(f"prereg.guide_mid.FQ1FY27.{scenario}").raw_value for scenario in ("bear", "base", "bull")] == [39600, 48750, 57300]
    assert [manifest.fact(f"sensitivity.eps.{name}.FY2027E").raw_value for name in ("slowdown", "zero", "r8", "original_gm")] == pytest.approx([165.56, 159.63, 170.14, 167.46], abs=.01)
    assert manifest.fact("sca.deposits.FQ4FY26").raw_value == 12700
    assert manifest.fact("bs.customer_contract_liabilities.FQ4FY26").raw_value == 12895


def test_r20_operating_income_bridge_identity(prepared):
    manifest = prepared["manifest"]
    start = manifest.fact("is.operating_income.FY2026A.A-8K").raw_value
    end = manifest.fact("is.operating_income.FY2027E.base").raw_value
    steps = [manifest.fact(f"bridge.op_amount.{name}.FY2026A_to_FY2027E").raw_value for name in ("revenue", "gm", "opex")]
    assert start + sum(steps) == pytest.approx(end)


@pytest.mark.parametrize("prefix", ["09_", "10_", "11_", "12_", "13_", "14_", "15_", "16_"])
def test_r20_plot_population_without_image_render(prepared, prefix):
    manifest = prepared["manifest"]
    for locale in ("ko", "en"):
        spec = next(spec for spec in e2b_specs(manifest, locale, _locale(locale)) if spec.chart_id.startswith(prefix))
        figure, axis = MagicMock(), MagicMock()
        axis.get_legend_handles_labels.return_value = ([], [])
        axis.twinx.return_value.get_legend_handles_labels.return_value = ([], [])
        figure.subplots.return_value = (MagicMock(), MagicMock())
        draw_revision_chart(figure, axis, manifest, spec, chart_data_contract(manifest, spec, locale)["values"], locale)
        figure.savefig.assert_not_called()


def test_r20_prose_evidence_boxes_and_parity_in_memory(prepared):
    manifest, narrative, assumptions = (prepared[key] for key in ("manifest", "narrative", "assumptions"))
    charts, texts, refs = {}, {}, {}
    for locale in ("ko", "en"):
        charts[locale] = contracts(manifest, locale)
        texts[locale], refs[locale] = render_markdown(manifest, locale, narrative=narrative, assumptions=assumptions,
                                                   chart_manifest=charts[locale], render_date="2026-10-05")
        html = _html_from_markdown(texts[locale], locale)
        assert html.count("<aside class='reading-box'>") == 2
        assert "<h3><strong>" in html and "<h4><strong>" in html
        assert "MICRON TECHNOLOGY · NASDAQ: MU" in html
        assert "logo" not in html.lower()
        assert texts[locale].count("![09_gm_beat_compression]") == 1
        for paragraph in narrative["company"][locale]:
            assert paragraph.split("{{fact:")[0] in texts[locale]
    gate_g15_parity(refs, manifest, texts)
    gate_g15b_localized_ui(charts, texts)
    broken = copy.deepcopy(narrative)
    broken["company"]["en"].pop()
    with pytest.raises(GateError, match="structure differs"):
        gate_narrative_contract(broken, manifest)


@pytest.mark.parametrize("value", ["1,147M", "USD 1,258,706 million", "$1,097.39", "+7.41%p", "−30,794"])
def test_r20_all_numeric_cells_use_one_alignment_rule(value):
    html = _html_from_markdown(f"| Metric | Value |\n|---|---:|\n| Test | {value} |", "en")
    assert f"<td class='wide-number'>{value}</td>" in html


def test_r20_numeric_first_column_uses_same_alignment_rule():
    html = _html_from_markdown("| Year | Statement |\n|---|---|\n| 2027 | Supply constrained |", "en")
    assert "<td class='wide-number'>2027</td>" in html
