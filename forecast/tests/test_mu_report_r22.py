"""R22 presentation regressions; financial inputs and rules are immutable."""
from __future__ import annotations

import re

import pytest

from forecast.scripts.mu_report import build
from forecast.scripts.mu_report.charts import chart_data_contract, e2b_specs
from forecast.scripts.mu_report.render import _html_from_markdown, _locale, render_markdown
from forecast.scripts.mu_report.gates import GateError, gate_missing_glyphs, gate_pdf_bold_runs


@pytest.fixture(scope="session")
def prepared_r22():
    return build._run_e2b_preflight()


def rendered_text(prepared, locale):
    manifest = prepared["manifest"]
    charts = {spec.chart_id: chart_data_contract(manifest, spec, locale)
              for spec in e2b_specs(manifest, locale, _locale(locale))}
    text, _ = render_markdown(manifest, locale, narrative=prepared["narrative"],
                              assumptions=prepared["assumptions"], chart_manifest=charts,
                              render_date="2026-10-05")
    return text, charts


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_r22_figures_once_in_first_appearance_order(prepared_r22, locale):
    text, charts = rendered_text(prepared_r22, locale)
    images = re.findall(r"!\[([^]]+)]", text)
    assert len(images) == len(set(images)) == 16
    numbers = [int(re.search(r"\d+", charts[key]["caption"]["number"]).group()) for key in images]
    assert numbers == list(range(1, 17))


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_r22_cover_numeric_rows_and_short_missing_markers(prepared_r22, locale):
    text, _ = rendered_text(prepared_r22, locale)
    cover = text.split("<!-- TOC_START -->")[0]
    assert "$" not in cover
    assert len([line for line in cover.splitlines() if line.startswith("| FY27E")]) == 2
    assert "—†" in text and "—‡" in text
    assert "—(사전등록 범위 밖)" not in text


def test_r22_numeric_headers_and_cover_list():
    html = _html_from_markdown("| Metric | Value |\n|---|---:|\n| Test | 32.57 |\n\n- First\n- Second", "en")
    assert "<th class='wide-number'>Value</th>" in html
    assert "<ul><li>First</li><li>Second</li></ul>" in html


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_r22_public_appendix_and_captions_have_no_internal_ids(prepared_r22, locale):
    text, charts = rendered_text(prepared_r22, locale)
    assert "SRC-" not in text
    assert "A12_sbc" not in text and "median_rate" not in text
    for chart in charts.values():
        assert "SRC-" not in chart["caption"]["source"]
        assert "CITED" not in chart["caption"]["basis"]


def test_r22_missing_glyph_warning_fails_gate():
    with pytest.raises(GateError, match="missing glyph"):
        gate_missing_glyphs(["Glyph 8594 missing from font(s) Noto Sans."])
    gate_missing_glyphs([])


def test_r22_bbox_rejects_clipped_text_and_overlapping_note():
    import matplotlib.pyplot as plt
    from forecast.scripts.mu_report.charts import validate_chart_text_bounds
    figure, axis = plt.subplots()
    try:
        note = figure.text(.5, .5, "overlapping note")
        with pytest.raises(GateError, match="overlaps"):
            validate_chart_text_bounds(figure)
        note.set_position((2, 2))
        with pytest.raises(GateError, match="outside figure"):
            validate_chart_text_bounds(figure)
    finally:
        plt.close(figure)


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_r22_all_chart_labels_and_outside_notes_fit(prepared_r22, locale, tmp_path):
    from forecast.scripts.mu_report.charts import render_charts
    manifest = prepared_r22["manifest"]
    rendered = render_charts(manifest, e2b_specs(manifest, locale, _locale(locale)), tmp_path, locale)
    assert len(rendered) == 16
    assert rendered["09_gm_beat_compression"]["layout"]["outside_bounds"]
    assert not rendered["16_sca_structure"]["layout"]["outside_bounds"]
    assert all(not chart["render_warnings"] for chart in rendered.values())
    assert all(chart["layout"]["minimum_legend_tick_pdf_pt"] >= 7 for chart in rendered.values())
    annual_labels = [item["text"] for item in rendered["06_annual_income"]["layout"]["text_bounds"]]
    assert not any(text == "53w" for text in annual_labels)
    assert sum("53주" in text if locale == "ko" else "53 weeks" in text for text in annual_labels) == 2


def test_r22_pdf_font_runs_are_really_bold(tmp_path):
    from weasyprint import HTML
    path = tmp_path / "bold.pdf"
    markup = _html_from_markdown("# MICRON TECHNOLOGY · NASDAQ: MU\n### **강세 논거**\n#### **논거 제목**\n일반체", "ko")
    HTML(string=markup).write_pdf(path)
    assert gate_pdf_bold_runs(path, ["MICRON TECHNOLOGY · NASDAQ: MU", "강세 논거", "논거 제목"])
    with pytest.raises(GateError, match="Bold font run"):
        gate_pdf_bold_runs(path, ["일반체"])
