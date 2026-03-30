"""범용 7-시트 Excel 빌더.

ValuationInput + ValuationResult → xlsx
"""

import os
from pathlib import Path

from openpyxl import Workbook
from openpyxl.utils import get_column_letter
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Font

from schemas.models import ValuationInput, ValuationResult
from .excel_styles import (
    NAVY, BLUE_FILL, YELLOW_FILL, GREEN_FILL, RED_FILL, GRAY_FILL,
    HEADER_FONT, SECTION_FONT, TITLE_FONT,
    NUM_FMT, PCT_FMT, MULT_FMT, THIN_BORDER, BASE_BORDER,
    style_header_row, write_cell,
)


def export(vi: ValuationInput, result: ValuationResult, output_dir: str | None = None) -> str:
    """Excel 워크북 생성 및 저장.

    Args:
        vi: 밸류에이션 입력 데이터
        result: 밸류에이션 결과
        output_dir: 출력 디렉토리 (None이면 현재 디렉토리)

    Returns:
        저장된 파일 경로
    """
    wb = Workbook()
    by = vi.base_year
    seg_names = {code: info["name"] for code, info in vi.segments.items()}
    seg_codes = list(vi.segments.keys())
    cons = vi.consolidated
    years = sorted(cons.keys())

    # ── Sheet 1: Assumptions ──
    ws = wb.active
    ws.title = "Assumptions"
    ws.sheet_properties.tabColor = NAVY
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 40

    write_cell(ws, 1, 1, f"{vi.company.name} 기업가치평가 — 핵심 가정값", font=TITLE_FONT)
    write_cell(ws, 2, 1, f"분석일: {vi.company.analysis_date}",
               font=Font(size=10, color="566573"))

    # WACC
    r = 4
    w = result.wacc
    wp = vi.wacc_params
    write_cell(ws, r, 1, "WACC 구성요소", font=SECTION_FONT); r += 1
    params = [
        ("무위험이자율 (Rf)", f"{wp.rf:.2f}%", "국고채 10Y"),
        ("주식위험프리미엄 (ERP)", f"{wp.erp:.2f}%", "시장 ERP"),
        ("Unlevered Beta (βu)", f"{wp.bu:.3f}", "Peer 평균"),
        ("D/E Ratio", f"{wp.de:.1f}%", f"{by}년말"),
        ("법인세율", f"{wp.tax:.1f}%", "실효세율"),
        ("Levered Beta (βL)", f"{w.bl:.3f}", "βu × [1+(1-t)×D/E]"),
        ("자기자본비용 (Ke)", f"{w.ke:.2f}%", "Rf + βL × ERP"),
        ("세전 타인자본비용 (Kd)", f"{wp.kd_pre:.2f}%", "신용등급 기반"),
        ("세후 타인자본비용", f"{w.kd_at:.2f}%", "Kd × (1-t)"),
        ("자기자본 비중", f"{wp.eq_w:.1f}%", f"{by}년말"),
        ("WACC", f"{w.wacc:.2f}%", "Ke×E% + Kd(세후)×D%"),
    ]
    for label, val, note in params:
        write_cell(ws, r, 1, label)
        write_cell(ws, r, 2, val, fill=BLUE_FILL)
        write_cell(ws, r, 3, note)
        r += 1

    # 멀티플
    r += 1
    write_cell(ws, r, 1, "부문별 EV/EBITDA 멀티플", font=SECTION_FONT); r += 1
    for code in seg_codes:
        write_cell(ws, r, 1, seg_names[code])
        write_cell(ws, r, 2, f"{vi.multiples[code]:.1f}x", fill=BLUE_FILL)
        r += 1

    # 시나리오 확률
    r += 1
    sc_codes = list(vi.scenarios.keys())
    write_cell(ws, r, 1, "시나리오 확률 / DLOM / IRR", font=SECTION_FONT); r += 1
    write_cell(ws, r, 1, "항목")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, f"{sc_code}: {vi.scenarios[sc_code].name}")
    style_header_row(ws, r, 1 + len(sc_codes)); r += 1
    write_cell(ws, r, 1, "확률")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, f"{vi.scenarios[sc_code].prob}%", fill=BLUE_FILL)
    r += 1
    write_cell(ws, r, 1, "DLOM")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, f"{vi.scenarios[sc_code].dlom}%", fill=BLUE_FILL)
    r += 1
    write_cell(ws, r, 1, "FI IRR")
    for i, sc_code in enumerate(sc_codes, 2):
        irr = vi.scenarios[sc_code].irr
        write_cell(ws, r, i, f"{irr}%" if irr else "-", fill=BLUE_FILL)

    # 기타
    r += 2
    write_cell(ws, r, 1, "기타 파라미터", font=SECTION_FONT); r += 1
    others = [
        ("순차입금 (백만원)", f"{vi.net_debt:,}"),
        ("CPS 원금 (백만원)", f"{vi.cps_principal:,}"),
        ("보통주 발행주식수", f"{vi.company.shares_ordinary:,}"),
        ("총발행주식수", f"{vi.company.shares_total:,}"),
    ]
    if vi.eco_frontier:
        others.insert(1, ("에코프론티어 파생상품부채", f"{vi.eco_frontier:,}"))
    for label, val in others:
        write_cell(ws, r, 1, label)
        write_cell(ws, r, 2, val, fill=BLUE_FILL)
        r += 1

    # ── Sheet 2: Financial Summary ──
    ws2 = wb.create_sheet("Financial Summary")
    ws2.sheet_properties.tabColor = "2E86C1"
    ws2.column_dimensions['A'].width = 24

    write_cell(ws2, 1, 1, "연결 재무제표 요약 (백만원)", font=TITLE_FONT)

    headers = ["항목"] + [str(y) for y in years]
    r = 3
    for c, h in enumerate(headers, 1):
        write_cell(ws2, r, c, h)
        ws2.column_dimensions[get_column_letter(c)].width = 18 if c > 1 else 24
    style_header_row(ws2, r, len(headers))

    rows_data = [
        ("매출액", [cons[y]["revenue"] for y in years]),
        ("영업이익", [cons[y]["op"] for y in years]),
        ("당기순이익", [cons[y]["net_income"] for y in years]),
        ("총자산", [cons[y]["assets"] for y in years]),
        ("총부채", [cons[y]["liabilities"] for y in years]),
        ("총자본", [cons[y]["equity"] for y in years]),
        ("부채비율 (%)", [cons[y]["de_ratio"] for y in years]),
        ("감가상각비", [cons[y]["dep"] for y in years]),
        ("무형자산상각비", [cons[y]["amort"] for y in years]),
        ("D&A 합계", [cons[y]["dep"] + cons[y]["amort"] for y in years]),
        ("EBITDA", [cons[y]["op"] + cons[y]["dep"] + cons[y]["amort"] for y in years]),
    ]
    for label, vals in rows_data:
        r += 1
        write_cell(ws2, r, 1, label, bold=True)
        for i, v in enumerate(vals, 2):
            f = '#,##0' if isinstance(v, int) else '0.0'
            write_cell(ws2, r, i, v, fmt=f, fill=YELLOW_FILL)

    # 부문별 데이터
    r += 2
    write_cell(ws2, r, 1, "부문별 재무 — 유무형자산 비중 D&A 배분", font=TITLE_FONT); r += 1

    for yr in reversed(years):
        r += 1
        write_cell(ws2, r, 1, f"── {yr}년 ──", font=SECTION_FONT); r += 1
        seg_headers = ["부문", "매출", "영업이익", "유무형자산", "자산비중", "D&A 배분", "EBITDA"]
        for c, h in enumerate(seg_headers, 1):
            write_cell(ws2, r, c, h)
        style_header_row(ws2, r, 7)

        alloc = result.da_allocations[yr]
        for code in seg_codes:
            r += 1
            s = vi.segment_data[yr][code]
            a = alloc[code]
            write_cell(ws2, r, 1, seg_names[code])
            write_cell(ws2, r, 2, s["revenue"], fmt=NUM_FMT, fill=YELLOW_FILL)
            write_cell(ws2, r, 3, s["op"], fmt=NUM_FMT, fill=YELLOW_FILL)
            write_cell(ws2, r, 4, s["assets"], fmt=NUM_FMT, fill=YELLOW_FILL)
            write_cell(ws2, r, 5, a.asset_share / 100, fmt=PCT_FMT)
            write_cell(ws2, r, 6, a.da_allocated, fmt=NUM_FMT)
            write_cell(ws2, r, 7, a.ebitda, fmt=NUM_FMT,
                       fill=GREEN_FILL if a.ebitda > 0 else RED_FILL)

        r += 1
        write_cell(ws2, r, 1, "합계", bold=True)
        write_cell(ws2, r, 2, sum(vi.segment_data[yr][c]["revenue"] for c in seg_codes), fmt=NUM_FMT, bold=True)
        write_cell(ws2, r, 3, sum(vi.segment_data[yr][c]["op"] for c in seg_codes), fmt=NUM_FMT, bold=True)
        write_cell(ws2, r, 4, sum(vi.segment_data[yr][c]["assets"] for c in seg_codes), fmt=NUM_FMT, bold=True)
        write_cell(ws2, r, 5, 1.0, fmt=PCT_FMT, bold=True)
        write_cell(ws2, r, 6, sum(alloc[c].da_allocated for c in seg_codes), fmt=NUM_FMT, bold=True)
        write_cell(ws2, r, 7, sum(alloc[c].ebitda for c in seg_codes), fmt=NUM_FMT, bold=True)

    # ── Sheet 3: SOTP Valuation ──
    ws3 = wb.create_sheet("SOTP Valuation")
    ws3.sheet_properties.tabColor = "27AE60"
    ws3.column_dimensions['A'].width = 20

    write_cell(ws3, 1, 1, f"SOTP 밸류에이션 ({by}년 기준, 백만원)", font=TITLE_FONT)

    r = 3
    write_cell(ws3, r, 1, "유무형자산 비중 D&A 배분", font=SECTION_FONT); r += 1
    sotp_headers = ["부문", "EBITDA", "멀티플", "Segment EV", "EV 비중"]
    for c, h in enumerate(sotp_headers, 1):
        write_cell(ws3, r, c, h)
        ws3.column_dimensions[get_column_letter(c)].width = 16
    style_header_row(ws3, r, 5)

    for code in seg_codes:
        r += 1
        s = result.sotp[code]
        write_cell(ws3, r, 1, seg_names[code])
        write_cell(ws3, r, 2, s.ebitda, fmt=NUM_FMT)
        write_cell(ws3, r, 3, s.multiple, fmt=MULT_FMT, fill=BLUE_FILL)
        write_cell(ws3, r, 4, s.ev, fmt=NUM_FMT, fill=GREEN_FILL if s.ev > 0 else None)
        ev_pct = s.ev / result.total_ev if result.total_ev > 0 else 0
        write_cell(ws3, r, 5, ev_pct, fmt=PCT_FMT)
    r += 1
    write_cell(ws3, r, 1, "합계", bold=True)
    write_cell(ws3, r, 2, sum(result.sotp[c].ebitda for c in seg_codes), fmt=NUM_FMT, bold=True)
    write_cell(ws3, r, 4, result.total_ev, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)
    write_cell(ws3, r, 5, 1.0, fmt=PCT_FMT, bold=True)

    # ── Sheet 4: Peer Comparison ──
    ws4 = wb.create_sheet("Peer Comparison")
    ws4.sheet_properties.tabColor = "17A589"
    write_cell(ws4, 1, 1, "유사기업 비교분석", font=TITLE_FONT)

    r = 3
    peer_headers = ["기업명", "매핑 부문", "EV/EBITDA", "비고"]
    for c, h in enumerate(peer_headers, 1):
        write_cell(ws4, r, c, h)
        ws4.column_dimensions[get_column_letter(c)].width = [20, 18, 12, 50][c - 1]
    style_header_row(ws4, r, 4)

    for p in vi.peers:
        r += 1
        write_cell(ws4, r, 1, p.name)
        write_cell(ws4, r, 2, seg_names.get(p.segment_code, p.segment_code))
        write_cell(ws4, r, 3, p.ev_ebitda, fmt=MULT_FMT, fill=YELLOW_FILL)
        write_cell(ws4, r, 4, p.notes)

    # 적용 멀티플 요약
    r += 2
    write_cell(ws4, r, 1, "적용 멀티플 요약", font=SECTION_FONT); r += 1
    for code in seg_codes:
        if vi.multiples[code] > 0:
            write_cell(ws4, r, 1, seg_names[code])
            write_cell(ws4, r, 2, f"{vi.multiples[code]:.1f}x", fill=BLUE_FILL)
            r += 1

    # ── Sheet 5: Scenario Analysis ──
    ws5 = wb.create_sheet("Scenario Analysis")
    ws5.sheet_properties.tabColor = "F39C12"
    write_cell(ws5, 1, 1, f"시나리오 분석 (백만원)", font=TITLE_FONT)

    r = 3
    sc_headers = ["항목"] + [f"{c}: {vi.scenarios[c].name}" for c in sc_codes]
    col_widths = [28] + [18] * len(sc_codes)
    for c, h in enumerate(sc_headers, 1):
        write_cell(ws5, r, c, h)
        ws5.column_dimensions[get_column_letter(c)].width = col_widths[c - 1]
    style_header_row(ws5, r, len(sc_headers))

    bridge_items = [
        ("확률", "prob", "%"), ("IPO 상태", "ipo_status", None),
        ("FI IRR", "fi_irr", "%"), ("DLOM", "dlom", "%"),
        ("", None, None),
        ("SOTP EV", "total_ev", "M"), ("(-) 순차입금", "net_debt", "M"),
        ("(-) CPS 상환", "cps_repay", "M"), ("(-) RCPS 상환", "rcps_repay", "M"),
        ("(-) 보통주 매입", "buyback", "M"), ("(-) 기타 차감", "eco_frontier", "M"),
        ("Equity Value", "equity_value", "M_bold"),
        ("", None, None),
        ("적용 주식수", "shares", "shares"),
        ("주당 가치 (DLOM 전)", "pre_dlom", "won"),
        ("주당 가치 (DLOM 후)", "post_dlom", "won_bold"),
        ("확률가중 기여", "weighted", "won"),
    ]

    for label, key, fmt_type in bridge_items:
        r += 1
        is_bold = fmt_type and "bold" in fmt_type if fmt_type else False
        write_cell(ws5, r, 1, label, bold=is_bold)
        if key is None:
            continue

        for i, sc_code in enumerate(sc_codes, 2):
            sc = vi.scenarios[sc_code]
            sr = result.scenarios[sc_code]

            if key == "prob":
                write_cell(ws5, r, i, f"{sc.prob}%", fill=BLUE_FILL)
            elif key == "ipo_status":
                write_cell(ws5, r, i, sc.ipo)
            elif key == "fi_irr":
                write_cell(ws5, r, i, f"{sc.irr}%" if sc.irr else "-", fill=BLUE_FILL)
            elif key == "dlom":
                write_cell(ws5, r, i, f"{sc.dlom}%", fill=BLUE_FILL)
            elif key in ("total_ev", "net_debt", "cps_repay", "rcps_repay", "buyback", "eco_frontier"):
                val = getattr(sr, key)
                write_cell(ws5, r, i, val, fmt=NUM_FMT, bold=is_bold)
            elif key == "equity_value":
                val = sr.equity_value
                fill = GREEN_FILL if val > 0 else RED_FILL
                write_cell(ws5, r, i, val, fmt=NUM_FMT, bold=True, fill=fill)
            elif key == "shares":
                write_cell(ws5, r, i, sr.shares, fmt=NUM_FMT)
            elif key in ("pre_dlom", "post_dlom", "weighted"):
                val = getattr(sr, key)
                write_cell(ws5, r, i, val, fmt=NUM_FMT, bold=is_bold,
                           fill=GREEN_FILL if val > 0 and key == "post_dlom" else None)

    r += 2
    write_cell(ws5, r, 1, "확률가중 주당 가치", font=Font(bold=True, size=13, color=NAVY))
    write_cell(ws5, r, 2, result.weighted_value, fmt=NUM_FMT,
               font=Font(bold=True, size=13, color="27AE60"), fill=GREEN_FILL)
    write_cell(ws5, r, 3, "원", font=Font(bold=True, size=13, color=NAVY))

    # ── Sheet 6: Sensitivity ──
    ws6 = wb.create_sheet("Sensitivity")
    ws6.sheet_properties.tabColor = "E74C3C"
    write_cell(ws6, 1, 1, "민감도 분석", font=TITLE_FONT)

    # Build lookup dicts
    mult_lookup = {(x.row_val, x.col_val): x.value for x in result.sensitivity_multiples}
    irr_lookup = {(x.row_val, x.col_val): x.value for x in result.sensitivity_irr_dlom}
    dcf_lookup = {(x.row_val, x.col_val): x.value for x in result.sensitivity_dcf}

    # Infer ranges from data
    mult_row_range = sorted(set(x.row_val for x in result.sensitivity_multiples))
    mult_col_range = sorted(set(x.col_val for x in result.sensitivity_multiples))
    irr_range = sorted(set(x.row_val for x in result.sensitivity_irr_dlom))
    dlom_range = sorted(set(x.col_val for x in result.sensitivity_irr_dlom))
    wacc_range = sorted(set(x.row_val for x in result.sensitivity_dcf))
    tg_range = sorted(set(x.col_val for x in result.sensitivity_dcf))

    # Table 1: Multiples sensitivity
    r = 3
    write_cell(ws6, r, 1, "① 멀티플 민감도 → Scenario A 주당가치 (원)", font=SECTION_FONT)
    r += 1
    write_cell(ws6, r, 1, "Row \\ Col", fill=GRAY_FILL, font=HEADER_FONT)
    for j, col_m in enumerate(mult_col_range, 2):
        write_cell(ws6, r, j, f"{col_m:.0f}x", fill=GRAY_FILL, font=HEADER_FONT)
        ws6.column_dimensions[get_column_letter(j)].width = 12

    sens1_start = r + 1
    for row_m in mult_row_range:
        r += 1
        write_cell(ws6, r, 1, f"{row_m:.0f}x", fill=GRAY_FILL, font=HEADER_FONT)
        for j, col_m in enumerate(mult_col_range, 2):
            val = mult_lookup.get((row_m, col_m), 0)
            fill = GREEN_FILL if val > 0 else RED_FILL
            write_cell(ws6, r, j, val, fmt=NUM_FMT, fill=fill)
    sens1_end = r

    # Heatmap
    end_col = get_column_letter(1 + len(mult_col_range))
    ws6.conditional_formatting.add(
        f"B{sens1_start}:{end_col}{sens1_end}", ColorScaleRule(
        start_type='min', start_color='FADBD8',
        mid_type='percentile', mid_value=50, mid_color='F5F6FA',
        end_type='max', end_color='D5F5E3',
    ))

    # Table 2: IRR × DLOM
    r += 3
    write_cell(ws6, r, 1, "② FI IRR × DLOM → Scenario B 주당가치 (원, 확률 미적용)", font=SECTION_FONT)
    r += 1
    write_cell(ws6, r, 1, "IRR \\ DLOM", fill=GRAY_FILL, font=HEADER_FONT)
    for j, dlom in enumerate(dlom_range, 2):
        write_cell(ws6, r, j, f"{int(dlom)}%", fill=GRAY_FILL, font=HEADER_FONT)

    sens2_start = r + 1
    for irr in irr_range:
        r += 1
        write_cell(ws6, r, 1, f"{irr:.0f}%", fill=GRAY_FILL, font=HEADER_FONT)
        for j, dlom in enumerate(dlom_range, 2):
            val = irr_lookup.get((irr, dlom), 0)
            fill = GREEN_FILL if val > 0 else RED_FILL
            write_cell(ws6, r, j, val, fmt=NUM_FMT, fill=fill)
    sens2_end = r

    end_col2 = get_column_letter(1 + len(dlom_range))
    ws6.conditional_formatting.add(
        f"B{sens2_start}:{end_col2}{sens2_end}", ColorScaleRule(
        start_type='min', start_color='FADBD8',
        mid_type='percentile', mid_value=50, mid_color='F5F6FA',
        end_type='max', end_color='D5F5E3',
    ))

    # Table 3: WACC × Terminal Growth → DCF EV
    r += 3
    write_cell(ws6, r, 1, "③ WACC × 영구성장률 → DCF EV (백만원)", font=SECTION_FONT)
    r += 1
    write_cell(ws6, r, 1, "WACC \\ Tg", fill=GRAY_FILL, font=HEADER_FONT)
    for j, tg in enumerate(tg_range, 2):
        write_cell(ws6, r, j, f"{tg:.1f}%", fill=GRAY_FILL, font=HEADER_FONT)
    style_header_row(ws6, r, 1 + len(tg_range))
    r += 1

    sens3_start = r
    for wacc_v in wacc_range:
        write_cell(ws6, r, 1, f"{wacc_v:.1f}%", fill=GRAY_FILL, font=HEADER_FONT)
        for j, tg in enumerate(tg_range, 2):
            val = dcf_lookup.get((wacc_v, tg), 0)
            fill = GREEN_FILL if val >= result.total_ev else RED_FILL
            write_cell(ws6, r, j, val, fmt=NUM_FMT, fill=fill)
        r += 1
    sens3_end = r - 1

    end_col3 = get_column_letter(1 + len(tg_range))
    ws6.conditional_formatting.add(
        f"B{sens3_start}:{end_col3}{sens3_end}", ColorScaleRule(
        start_type='min', start_color='FADBD8',
        mid_type='percentile', mid_value=50, mid_color='F5F6FA',
        end_type='max', end_color='D5F5E3',
    ))

    write_cell(ws6, r, 1, f"참조: SOTP EV = {result.total_ev:,}백만원",
               font=Font(italic=True, size=9, color="566573"))

    # ── Sheet 7: Dashboard ──
    ws7 = wb.create_sheet("Dashboard")
    ws7.sheet_properties.tabColor = NAVY
    ws7.column_dimensions['A'].width = 30
    ws7.column_dimensions['B'].width = 20
    ws7.column_dimensions['C'].width = 20
    ws7.column_dimensions['D'].width = 20

    write_cell(ws7, 1, 1, f"{vi.company.name} 기업가치평가 Dashboard",
               font=Font(bold=True, size=16, color=NAVY))
    write_cell(ws7, 2, 1, f"분석일: {vi.company.analysis_date}  |  D&A 배분: 유무형자산 비중 기반",
               font=Font(size=10, color="566573"))

    # 핵심 결론
    r = 4
    write_cell(ws7, r, 1, "확률가중 적정 주당 가치",
               font=Font(bold=True, size=14, color=NAVY))
    write_cell(ws7, r, 2, f"{result.weighted_value:,}원",
               font=Font(bold=True, size=18, color="27AE60"), fill=GREEN_FILL)

    # 시나리오 요약
    r += 2
    write_cell(ws7, r, 1, "시나리오별 주당 가치", font=SECTION_FONT); r += 1
    sc_sum_headers = ["시나리오", "주당가치 (원)", "확률", "가중기여 (원)"]
    for c, h in enumerate(sc_sum_headers, 1):
        write_cell(ws7, r, c, h)
    style_header_row(ws7, r, 4)
    sc_header_row = r

    for sc_code in sc_codes:
        r += 1
        sc = vi.scenarios[sc_code]
        sr = result.scenarios[sc_code]
        write_cell(ws7, r, 1, f"{sc_code}: {sc.name}")
        write_cell(ws7, r, 2, sr.post_dlom, fmt=NUM_FMT,
                   fill=GREEN_FILL if sr.post_dlom > 0 else RED_FILL)
        write_cell(ws7, r, 3, f"{sc.prob}%")
        write_cell(ws7, r, 4, sr.weighted, fmt=NUM_FMT)

    r += 1
    write_cell(ws7, r, 1, "합계", bold=True)
    write_cell(ws7, r, 2, result.weighted_value, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)
    write_cell(ws7, r, 3, "100%", bold=True)
    write_cell(ws7, r, 4, result.weighted_value, fmt=NUM_FMT, bold=True)

    # EV Bridge
    r += 2
    write_cell(ws7, r, 1, "Enterprise Value 구성 (백만원)", font=SECTION_FONT); r += 1
    ev_data_start = r
    active_segs = [c for c in seg_codes if result.sotp[c].ev > 0]
    for code in active_segs:
        s = result.sotp[code]
        write_cell(ws7, r, 1, f"{seg_names[code]} ({s.multiple:.0f}x)")
        write_cell(ws7, r, 2, s.ev, fmt=NUM_FMT)
        r += 1
    ev_data_end = r - 1
    write_cell(ws7, r, 1, "Total EV", bold=True)
    write_cell(ws7, r, 2, result.total_ev, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)

    # 핵심 재무지표
    r += 2
    cons_by = vi.consolidated[by]
    total_da = cons_by["dep"] + cons_by["amort"]
    ebitda = cons_by["op"] + total_da
    write_cell(ws7, r, 1, f"핵심 재무지표 ({by})", font=SECTION_FONT); r += 1
    kpis = [
        ("매출액", cons_by["revenue"]),
        ("영업이익", cons_by["op"]),
        ("EBITDA", ebitda),
        ("순차입금", vi.net_debt),
        ("부채비율", f"{cons_by['de_ratio']:.1f}%"),
        ("SOTP EV", result.total_ev),
        ("DCF EV", result.dcf.ev_dcf),
        ("DCF vs SOTP", f"{(result.dcf.ev_dcf - result.total_ev) / result.total_ev * 100:+.1f}%"),
        ("EV/EBITDA (implied)", f"{result.total_ev / ebitda:.1f}x" if ebitda > 0 else "N/A"),
    ]
    for label, val in kpis:
        write_cell(ws7, r, 1, label)
        if isinstance(val, str):
            write_cell(ws7, r, 2, val)
        else:
            write_cell(ws7, r, 2, val, fmt=NUM_FMT)
        r += 1

    # ── Charts ──
    # Chart 1: 시나리오별 주당 가치
    chart1 = BarChart()
    chart1.type = "col"
    chart1.style = 10
    chart1.title = "시나리오별 주당 가치 (원)"
    chart1.y_axis.title = "원"

    cats1 = Reference(ws7, min_col=1, min_row=sc_header_row + 1, max_row=sc_header_row + len(sc_codes))
    vals1 = Reference(ws7, min_col=2, min_row=sc_header_row, max_row=sc_header_row + len(sc_codes))
    chart1.add_data(vals1, titles_from_data=True)
    chart1.set_categories(cats1)
    chart1.shape = 4
    chart1.width = 18
    chart1.height = 12

    sc_colors = ["1B2A4A", "27AE60", "E74C3C", "F39C12", "8E44AD"]
    s1 = chart1.series[0]
    s1.graphicalProperties.solidFill = sc_colors[0]
    for idx in range(1, len(sc_codes)):
        pt = DataPoint(idx=idx)
        pt.graphicalProperties.solidFill = sc_colors[idx % len(sc_colors)]
        s1.data_points.append(pt)

    chart1.legend = None
    s1.dLbls = DataLabelList()
    s1.dLbls.showVal = True
    s1.dLbls.showSerName = False
    s1.dLbls.numFmt = '#,##0'

    r += 2
    ws7.add_chart(chart1, f"A{r}")

    # Chart 2: EV 구성
    chart2 = BarChart()
    chart2.type = "col"
    chart2.style = 10
    chart2.title = "사업부별 Enterprise Value (백만원)"
    chart2.y_axis.title = "백만원"

    cats2 = Reference(ws7, min_col=1, min_row=ev_data_start, max_row=ev_data_end)
    vals2 = Reference(ws7, min_col=2, min_row=ev_data_start, max_row=ev_data_end)
    chart2.add_data(vals2, titles_from_data=False)
    chart2.set_categories(cats2)
    chart2.shape = 4
    chart2.width = 18
    chart2.height = 12
    chart2.legend = None

    seg_colors = ["1B2A4A", "2E86C1", "27AE60", "F39C12", "8E44AD"]
    s2 = chart2.series[0]
    for idx, color in enumerate(seg_colors[:len(active_segs)]):
        pt = DataPoint(idx=idx)
        pt.graphicalProperties.solidFill = color
        s2.data_points.append(pt)

    s2.dLbls = DataLabelList()
    s2.dLbls.showVal = True
    s2.dLbls.showSerName = False
    s2.dLbls.numFmt = '#,##0'

    r += 16
    ws7.add_chart(chart2, f"A{r}")

    # ── Save ──
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent)
    filename = f"{vi.company.name}_밸류에이션_모델.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    return filepath
