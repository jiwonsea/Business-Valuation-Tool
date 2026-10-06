"""R24 final display polish; inputs, scoring evidence and facts stay unchanged."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from openpyxl import Workbook
from openpyxl.styles import Font

from forecast.scripts.mu_report import build
from forecast.scripts.mu_report.gates import GateError, gate_g15b_localized_ui
from forecast.scripts.mu_report.render import _html_from_markdown, _write_ed1_xlsx_summary
from forecast.tests.test_mu_report_r22 import rendered_text


@pytest.fixture(scope="module")
def prepared_r24():
    return build._run_e2b_preflight()


@pytest.mark.parametrize("locale,header", [("ko", "쪽"), ("en", "Page")])
def test_r24_short_page_header_and_no_word_break(prepared_r24, locale, header):
    text, _ = rendered_text(prepared_r24, locale)
    change_heading = "| 항목 | 원안 | 변경 | 사유 |" if locale == "ko" else "| Item | Original | Change | Reason |"
    assert change_heading + f" {header} |" in text
    html = _html_from_markdown(text, locale)
    assert "class='post-print-changes'" in html
    assert "word-break:keep-all" in html and "hyphens:none" in html


def test_r24_summary_title_height():
    from forecast.scripts.mu_report.inputs import load_conflict_confirmation
    sheet = Workbook().active
    sheet["A1"].font = Font(name="Arial", size=16, bold=True)
    conflict = load_conflict_confirmation(
        Path("forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml"), "ed1",
        datetime(2026, 10, 5, 21, tzinfo=timezone(timedelta(hours=9))),
    )
    _write_ed1_xlsx_summary(sheet, conflict, "2026-10-05")
    assert sheet.row_dimensions[1].height >= sheet["A1"].font.sz * 1.5 + 8
    assert sheet["A1"].alignment.vertical == "center"


@pytest.mark.parametrize("locale,label,note", [
    ("ko", "해당 없음(가이던스 없음)", "GAAP 영업비용은 회사 가이던스가 없어 라벨 채점 대상이 아니다."),
    ("en", "n/a (no guidance)", "GAAP opex had no company guidance, so it is not label-scored;"),
])
def test_r24_opex_display_and_raw_evidence(prepared_r24, locale, label, note):
    text, _ = rendered_text(prepared_r24, locale)
    row = next(line for line in text.splitlines() if line.startswith("| GAAP") and "Narrative failure" in line) if locale == "en" else next(line for line in text.splitlines() if "서술 실패" in line and line.startswith("|"))
    assert label in row and "(d-1)" not in row
    assert note in text and text.count(note) == 1
    assert "77%" in text
    assert "(d-1)" in prepared_r24["manifest"].fact("scored.verdict.4.4.FQ4FY26").raw_value


@pytest.mark.parametrize("locale", ["ko", "en"])
def test_r24_appendix_percentages_and_readable_status(prepared_r24, locale):
    from forecast.scripts.mu_report.narrative import appendix_markdown
    from forecast.scripts.mu_report.render import _locale
    assumptions = prepared_r24["assumptions"]
    before = deepcopy(assumptions.rules)
    text = "\n".join(appendix_markdown(assumptions, locale, _locale(locale)))
    for percentage in ("84.95%", "13.67%", "3.45%", "−0.23%", "17.29%", "4.32%", "19.05%"):
        assert percentage in text
    assert "≤ −2%" in text
    assert "가정이 없어 추정하지 않음" in text if locale == "ko" else "not estimated (no assumption)" in text
    assert "AVAILABLE" not in text and "NOT_ACTIVATED" not in text
    assert assumptions.rules == before
    # Amounts and per-share inputs must not be scaled into percentages.
    assert "11500/13500/12500/12500" in text and ": 0.15" in text


@pytest.mark.parametrize("locale", ["ko", "en"])
@pytest.mark.parametrize("code", ["AVAILABLE", "AVAILABLE_BACKSOLVED", "UNAVAILABLE_WITHOUT_ASSUMPTIONS", "NOT_ACTIVATED", "PASS_GAAP"])
def test_r24_raw_status_code_rejected(locale, code):
    texts = {"ko": "", "en": ""}
    texts[locale] = f"| Applied value | {code} |"
    with pytest.raises(GateError, match="raw status code"):
        gate_g15b_localized_ui({"ko": {}, "en": {}}, texts)
