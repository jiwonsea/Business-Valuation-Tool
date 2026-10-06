"""R23 display regressions without changing financial facts or narrative text."""
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from forecast.scripts.mu_report.gates import GateError, gate_pdf_bold_runs
from forecast.scripts.mu_report.render import _html_from_markdown


@pytest.mark.parametrize("bold", [True, False])
def test_bold_ligature_character_mapping(bold):
    # A preceding ligature shifts string offsets; the target contains one too.
    chars = [{"text": "fl", "fontname": "Regular"}]
    chars += [{"text": text, "fontname": "Noto-Bold" if bold else "Regular"}
              for text in ("p", "r", "i", "c", "e", " ", "fl", "o", "o", "r")]
    chars.append({"text": "after", "fontname": "Regular"})
    document = SimpleNamespace(pages=[SimpleNamespace(chars=chars)])
    with patch("pdfplumber.open") as opened:
        opened.return_value.__enter__.return_value = document
        if bold:
            assert gate_pdf_bold_runs(None, ["price floor"]) == {"price floor": 1}
        else:
            with pytest.raises(GateError, match="Bold"):
                gate_pdf_bold_runs(None, ["price floor"])


def test_tables_separated_at_blank_line():
    html = _html_from_markdown("| Metric | Value |\n|---|---:|\n| EPS | 32.57 |\n\n"
                               "| Metric | Value |\n|---|---:|\n| P/B | 9.10x |", "en")
    assert html.count("<table") == 2
    assert "td.wide-number" in html


@pytest.mark.parametrize("locale,heading", [("ko", "근거 쪽"), ("en", "Source page")])
def test_change_table_class_and_header_cell_bounds(locale, heading):
    from weasyprint import HTML
    markup = f"| Item | Original | Change | Reason | {heading} |\n|---|---|---|---|---|\n| GM | FQ1 | Flat | Source rationale | 9 |"
    html = _html_from_markdown(markup, locale)
    assert "class='post-print-changes'" in html
    document = HTML(string=html).render()
    cells = []
    for page in document.pages:
        for box in page._page_box.descendants():
            if type(box).__name__ == "TableCellBox":
                cells.append(box)
                for child in box.descendants():
                    if type(child).__name__ == "TextBox":
                        assert child.position_x >= box.position_x - .1
                        assert child.position_x + child.width <= box.position_x + box.border_width() + .1
            if type(box).__name__ == "TableBox":
                assert (box.position_x + box.border_width()) * .75 <= 549.9
    assert cells


def test_new_narrative_sections_in_contract():
    from forecast.scripts.mu_report.revision import NEW_SECTIONS
    assert {"business_structure", "methodology"} <= set(NEW_SECTIONS)


def test_header_gate_rejects_nowrap_overflow():
    from forecast.scripts.mu_report.gates import gate_r23_table_layout
    header = "FY26E PREREG_A extended header " * 15
    html = _html_from_markdown(f"| Metric | {header} |\n|---|---:|\n| EPS | 32.57 |", "en")
    html = html.replace("</style>", "th { white-space:nowrap; width:20px; }</style>")
    with pytest.raises(GateError, match="outside its own cell"):
        gate_r23_table_layout(html)


@pytest.fixture(scope="module")
def prepared_r23():
    from forecast.scripts.mu_report import build
    return build._run_e2b_preflight()


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_approved_sections_market_units_and_verdict_display(prepared_r23, locale):
    from forecast.tests.test_mu_report_r22 import rendered_text
    text, _ = rendered_text(prepared_r23, locale)
    assert "USD/share · 2026-10-01" in text
    assert "million shares · FQ4 A-8K" in text
    assert "USD million · " in text
    assert not any(code in text for code in ("ABOVE_HIGH", "IN_RANGE", "BELOW_LOW"))
    assert "Trailing P/B:" in text
    assert "| Trailing P/B |" not in text
    for section in ("business_structure", "methodology"):
        for paragraph in prepared_r23["narrative"][section][locale]:
            assert paragraph in text
    ratio = text.split("비율·주요 지표" if locale == "ko" else "Ratios and key metrics")[-1]
    assert "† " in ratio and "‡ " in ratio


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_full_report_headers_and_appendix_inside_content(prepared_r23, locale):
    from forecast.tests.test_mu_report_r22 import rendered_text
    from forecast.scripts.mu_report.gates import gate_r23_table_layout
    text, _ = rendered_text(prepared_r23, locale)
    audit = gate_r23_table_layout(_html_from_markdown(text, locale), "forecast/reports")
    assert audit["headers"] > 50
    assert {item["class"] for item in audit["appendix_tables"]} == {"appendix-rules", "post-print-changes"}


def test_g15b_rejects_raw_verdict_code(prepared_r23):
    from forecast.tests.test_mu_report_r22 import rendered_text
    from forecast.scripts.mu_report.gates import gate_g15b_localized_ui
    pairs = {locale: rendered_text(prepared_r23, locale) for locale in ("ko", "en")}
    charts = {locale: pair[1] for locale, pair in pairs.items()}
    texts = {locale: pair[0] for locale, pair in pairs.items()}
    texts["ko"] += "\n| 실제 라벨 | ABOVE_HIGH |"
    with pytest.raises(GateError, match="raw verdict code"):
        gate_g15b_localized_ui(charts, texts)


def test_new_section_numeric_parity_rejects_changed_company_statement(prepared_r23):
    import copy
    from forecast.scripts.mu_report.gates import gate_narrative_contract
    broken = copy.deepcopy(prepared_r23["narrative"])
    broken["business_structure"]["en"][0] = broken["business_structure"]["en"][0].replace("18.0", "18.1")
    with pytest.raises(GateError, match="numeric parity"):
        gate_narrative_contract(broken, prepared_r23["manifest"])


@pytest.mark.parametrize("chart_id", ["11_eps_error_waterfall", "15_operating_income_waterfall"])
def test_waterfall_zoom_rounding_and_label_geometry(prepared_r23, chart_id):
    import matplotlib.pyplot as plt
    from forecast.scripts.mu_report.charts import e2b_specs
    from forecast.scripts.mu_report.render import _locale
    from forecast.scripts.mu_report.revision import draw_revision_chart
    manifest = prepared_r23["manifest"]
    spec = next(spec for spec in e2b_specs(manifest, "en", _locale("en")) if spec.chart_id == chart_id)
    values = [manifest.fact(point.fact_id).raw_value for point in spec.points]
    figure, axis = plt.subplots(figsize=(7.2, 3.8), dpi=120)
    try:
        draw_revision_chart(figure, axis, manifest, spec, values, "en")
        figure.tight_layout()
        figure.canvas.draw()
        labels = axis.texts
        boxes = [label.get_window_extent(figure.canvas.get_renderer()) for label in labels]
        assert all(not left.overlaps(right) for index, left in enumerate(boxes) for right in boxes[index + 1:])
        bars = [bar.get_window_extent(figure.canvas.get_renderer()) for bar in axis.patches]
        assert all(not label.overlaps(bar) for label in boxes for bar in bars)
        if chart_id.startswith("11_"):
            assert axis.get_ylim() == (31.5, 34.0)
        else:
            assert all("." not in label.get_text() for label in labels)
    finally:
        plt.close(figure)
