"""범용 Excel 빌더 — 방법론별 시트 자동 분기.

ValuationInput + ValuationResult → xlsx
지원 방법론: sotp, dcf_primary, ddm, rim, nav, multiples
"""

import os
from dataclasses import dataclass, field
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
    NAVY, BLUE_FILL, YELLOW_FILL, GREEN_FILL, RED_FILL, GRAY_FILL, DARK_FILL, DRIVER_FILL,
    HEADER_FONT, SECTION_FONT, TITLE_FONT, NOTE_FONT, WHITE_FONT, RESULT_FONT,
    NUM_FMT, PCT_FMT, MULT_FMT, THIN_BORDER, BASE_BORDER,
    style_header_row, write_cell,
)


# ── Build Context ──


@dataclass
class _Ctx:
    """시트 함수 간 공유 컨텍스트."""
    vi: ValuationInput
    result: ValuationResult
    wb: Workbook
    method: str
    by: int
    seg_names: dict
    seg_codes: list
    cons: dict
    years: list
    unit: str
    currency_sym: str
    sc_codes: list = field(default_factory=list)


def _make_ctx(vi: ValuationInput, result: ValuationResult, wb: Workbook) -> _Ctx:
    return _Ctx(
        vi=vi, result=result, wb=wb,
        method=result.primary_method,
        by=vi.base_year,
        seg_names={code: info["name"] for code, info in vi.segments.items()},
        seg_codes=list(vi.segments.keys()),
        cons=vi.consolidated,
        years=sorted(vi.consolidated.keys()),
        unit=vi.company.currency_unit,
        currency_sym="원" if vi.company.market == "KR" else "$",
        sc_codes=list(vi.scenarios.keys()),
    )


# ── Main Entry Point ──


def export(vi: ValuationInput, result: ValuationResult, output_dir: str | None = None) -> str:
    """Excel 워크북 생성 및 저장."""
    wb = Workbook()
    # 기본 빈 시트 제거 (Assumptions가 첫 시트가 됨)
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    ctx = _make_ctx(vi, result, wb)

    _sheet_assumptions(ctx)
    _sheet_financials(ctx)

    # 방법론별 Valuation 시트
    _VALUATION_MAP.get(ctx.method, _valuation_dcf)(ctx)

    _sheet_peers(ctx)
    if ctx.result.scenarios:
        _sheet_scenarios(ctx)
    _sheet_sensitivity(ctx)
    _sheet_dashboard(ctx)

    # Save
    if output_dir is None:
        output_dir = str(Path(__file__).parent.parent)
    filename = f"{vi.company.name}_밸류에이션_모델.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    return filepath


# ═════════════════════════════════════════════════════════════════
# Sheet 1: Assumptions
# ═════════════════════════════════════════════════════════════════


def _sheet_assumptions(ctx: _Ctx):
    ws = ctx.wb.active or ctx.wb.create_sheet("Assumptions")
    ws.title = "Assumptions"
    ws.sheet_properties.tabColor = NAVY
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 40

    write_cell(ws, 1, 1, f"{ctx.vi.company.name} 기업가치평가 — 핵심 가정값", font=TITLE_FONT)
    write_cell(ws, 2, 1, f"분석일: {ctx.vi.company.analysis_date}  |  방법론: {ctx.method.upper()}",
               font=NOTE_FONT)

    r = 4

    # ── WACC / Ke (공통) ──
    w = ctx.result.wacc
    wp = ctx.vi.wacc_params

    if ctx.method in ("ddm", "rim"):
        # DDM/RIM: Ke만 핵심
        write_cell(ws, r, 1, "자기자본비용 (Ke)", font=SECTION_FONT); r += 1
        ke_params = [
            ("무위험이자율 (Rf)", f"{wp.rf:.2f}%", "국고채 10Y"),
            ("주식위험프리미엄 (ERP)", f"{wp.erp:.2f}%", "시장 ERP"),
            ("Beta (βL)", f"{w.bl:.3f}", "Equity Beta" if wp.is_financial else "Hamada 조정"),
            ("자기자본비용 (Ke)", f"{w.ke:.2f}%", "Rf + βL × ERP"),
        ]
        for label, val, note in ke_params:
            write_cell(ws, r, 1, label)
            write_cell(ws, r, 2, val, fill=BLUE_FILL)
            write_cell(ws, r, 3, note)
            r += 1
    else:
        # SOTP/DCF/NAV/Multiples: 전체 WACC
        write_cell(ws, r, 1, "WACC 구성요소", font=SECTION_FONT); r += 1
        wacc_params = [
            ("무위험이자율 (Rf)", f"{wp.rf:.2f}%", "국고채 10Y"),
            ("주식위험프리미엄 (ERP)", f"{wp.erp:.2f}%", "시장 ERP"),
            ("Unlevered Beta (βu)", f"{wp.bu:.3f}", "Peer 평균"),
            ("D/E Ratio", f"{wp.de:.1f}%", f"{ctx.by}년말"),
            ("법인세율", f"{wp.tax:.1f}%", "실효세율"),
            ("Levered Beta (βL)", f"{w.bl:.3f}", "βu × [1+(1-t)×D/E]"),
            ("자기자본비용 (Ke)", f"{w.ke:.2f}%", "Rf + βL × ERP"),
            ("세전 타인자본비용 (Kd)", f"{wp.kd_pre:.2f}%", "신용등급 기반"),
            ("세후 타인자본비용", f"{w.kd_at:.2f}%", "Kd × (1-t)"),
            ("자기자본 비중", f"{wp.eq_w:.1f}%", f"{ctx.by}년말"),
            ("WACC", f"{w.wacc:.2f}%", "Ke×E% + Kd(세후)×D%"),
        ]
        for label, val, note in wacc_params:
            write_cell(ws, r, 1, label)
            write_cell(ws, r, 2, val, fill=BLUE_FILL)
            write_cell(ws, r, 3, note)
            r += 1

    # ── 방법론별 추가 가정 ──
    r += 1

    if ctx.method == "sotp":
        # 부문별 멀티플 (Mixed SOTP 대응)
        write_cell(ws, r, 1, "부문별 적용 멀티플", font=SECTION_FONT); r += 1
        for code in ctx.seg_codes:
            seg_info = ctx.vi.segments.get(code, {})
            method = seg_info.get("method", "ev_ebitda")
            method_label = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(method, method)
            write_cell(ws, r, 1, f"{ctx.seg_names[code]} ({method_label})")
            write_cell(ws, r, 2, f"{ctx.vi.multiples[code]:.1f}x", fill=BLUE_FILL)
            r += 1

    elif ctx.method == "dcf_primary":
        dcf_p = ctx.vi.dcf_params
        write_cell(ws, r, 1, "DCF 핵심 가정", font=SECTION_FONT); r += 1
        dcf_items = [
            ("영구성장률 (Terminal Growth)", f"{dcf_p.terminal_growth:.1f}%", "Gordon Growth"),
            ("법인세율", f"{dcf_p.tax_rate:.1f}%", "실효세율"),
            ("Capex / D&A", f"{dcf_p.capex_to_da:.2f}x", "유지보수 투자"),
            ("ΔNWC / ΔRevenue", f"{dcf_p.nwc_to_rev_delta:.1%}", "운전자본 변동"),
        ]
        for i, g in enumerate(dcf_p.ebitda_growth_rates):
            dcf_items.append((f"EBITDA 성장률 Y{i+1}", f"{g:.1%}", ""))
        for label, val, note in dcf_items:
            write_cell(ws, r, 1, label)
            write_cell(ws, r, 2, val, fill=BLUE_FILL)
            if note:
                write_cell(ws, r, 3, note)
            r += 1

    elif ctx.method == "ddm":
        ddm_p = ctx.vi.ddm_params
        if ddm_p:
            write_cell(ws, r, 1, "DDM 파라미터", font=SECTION_FONT); r += 1
            ddm_items = [
                ("주당 배당금 (DPS)", f"{ddm_p.dps:,.0f}{ctx.currency_sym}", "최근 실적"),
                ("배당 성장률 (g)", f"{ddm_p.dividend_growth:.2f}%", "지속가능 성장률"),
            ]
            if ddm_p.buyback_per_share > 0:
                ddm_items.append(("주당 자사주매입", f"{ddm_p.buyback_per_share:,.0f}{ctx.currency_sym}", "Total Payout"))
            for label, val, note in ddm_items:
                write_cell(ws, r, 1, label)
                write_cell(ws, r, 2, val, fill=BLUE_FILL)
                write_cell(ws, r, 3, note)
                r += 1

    elif ctx.method == "rim":
        rim_p = ctx.vi.rim_params
        if rim_p:
            write_cell(ws, r, 1, "RIM 파라미터", font=SECTION_FONT); r += 1
            rim_items = [
                ("영구성장률 (Terminal)", f"{rim_p.terminal_growth:.2f}%", "RI 영구성장률"),
                ("배당성향", f"{rim_p.payout_ratio:.1f}%", "Clean Surplus 조정"),
            ]
            for i, roe in enumerate(rim_p.roe_forecasts):
                rim_items.append((f"ROE 예측 Y{i+1}", f"{roe:.1f}%", ""))
            for label, val, note in rim_items:
                write_cell(ws, r, 1, label)
                write_cell(ws, r, 2, val, fill=BLUE_FILL)
                if note:
                    write_cell(ws, r, 3, note)
                r += 1

    elif ctx.method == "nav":
        nav_p = ctx.vi.nav_params
        if nav_p:
            write_cell(ws, r, 1, "NAV 가정", font=SECTION_FONT); r += 1
            write_cell(ws, r, 1, "투자자산 재평가 조정액")
            write_cell(ws, r, 2, f"{nav_p.revaluation:,}", fill=BLUE_FILL)
            write_cell(ws, r, 3, "공정가치 − 장부가")
            r += 1

    elif ctx.method == "multiples":
        write_cell(ws, r, 1, "적용 멀티플", font=SECTION_FONT); r += 1
        mp = ctx.result.multiples_primary
        if mp:
            write_cell(ws, r, 1, f"방법론: {mp.primary_multiple_method}")
            write_cell(ws, r, 2, f"{mp.multiple:.1f}x", fill=BLUE_FILL)
            r += 1

    # ── 시나리오 가정 요약 (있을 때만) ──
    is_listed = ctx.vi.company.legal_status == "상장"
    has_dlom = any(ctx.vi.scenarios[c].dlom > 0 for c in ctx.sc_codes) if ctx.sc_codes else False

    if ctx.sc_codes:
        r += 1
        section_title = "시나리오 확률" + (" / DLOM" if has_dlom else "")
        write_cell(ws, r, 1, section_title, font=SECTION_FONT); r += 1
        write_cell(ws, r, 1, "항목")
        for i, sc_code in enumerate(ctx.sc_codes, 2):
            write_cell(ws, r, i, f"{sc_code}: {ctx.vi.scenarios[sc_code].name}")
        style_header_row(ws, r, 1 + len(ctx.sc_codes)); r += 1

        # 확률은 항상 표시
        write_cell(ws, r, 1, "확률")
        for i, sc_code in enumerate(ctx.sc_codes, 2):
            write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].prob}%", fill=BLUE_FILL)
        r += 1

        # DLOM — 비상장이거나 실제 적용된 경우만
        if not is_listed or has_dlom:
            write_cell(ws, r, 1, "DLOM")
            for i, sc_code in enumerate(ctx.sc_codes, 2):
                write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].dlom}%", fill=BLUE_FILL)
            r += 1

        # 방법론별 드라이버 가정
        _write_assumption_drivers(ws, r, ctx)
        r += 1  # 드라이버가 없어도 최소 1줄 건너뜀

        # IRR (비상장 + CPS 있는 경우만)
        if any(ctx.vi.scenarios[c].irr is not None for c in ctx.sc_codes):
            write_cell(ws, r, 1, "FI IRR")
            for i, sc_code in enumerate(ctx.sc_codes, 2):
                irr = ctx.vi.scenarios[sc_code].irr
                write_cell(ws, r, i, f"{irr}%" if irr else "-", fill=BLUE_FILL)
            r += 1

    # ── 기타 파라미터 ──
    r += 1
    write_cell(ws, r, 1, "기타 파라미터", font=SECTION_FONT); r += 1
    # Mixed SOTP: 유효 순차입금 표시
    _is_mixed = bool(ctx.vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in ctx.vi.segments.values()
    )
    write_cell(ws, r, 1, f"순차입금 ({ctx.unit})")
    write_cell(ws, r, 2, ctx.vi.net_debt, fmt=NUM_FMT, fill=BLUE_FILL)
    r += 1
    if _is_mixed:
        fin_debt = sum(
            ctx.vi.segment_net_debt[c]
            for c, info in ctx.vi.segments.items()
            if info.get("method") in ("pbv", "pe") and c in ctx.vi.segment_net_debt
        )
        eff_nd = ctx.vi.net_debt - fin_debt
        write_cell(ws, r, 1, f"(-) 금융부문 부채 (PBV 내재)")
        write_cell(ws, r, 2, fin_debt, fmt=NUM_FMT, fill=BLUE_FILL)
        r += 1
        write_cell(ws, r, 1, f"유효 순차입금")
        write_cell(ws, r, 2, eff_nd, fmt=NUM_FMT, fill=BLUE_FILL)
        r += 1
    write_cell(ws, r, 1, "보통주 발행주식수")
    write_cell(ws, r, 2, ctx.vi.company.shares_ordinary, fmt=NUM_FMT, fill=BLUE_FILL)
    r += 1
    if ctx.vi.company.shares_preferred > 0:
        write_cell(ws, r, 1, "우선주 발행주식수")
        write_cell(ws, r, 2, ctx.vi.company.shares_preferred, fmt=NUM_FMT, fill=BLUE_FILL)
        r += 1
    write_cell(ws, r, 1, "총발행주식수")
    write_cell(ws, r, 2, ctx.vi.company.shares_total, fmt=NUM_FMT, fill=BLUE_FILL)
    r += 1
    if ctx.vi.company.treasury_shares > 0:
        write_cell(ws, r, 1, "자사주 (보통주)")
        write_cell(ws, r, 2, ctx.vi.company.treasury_shares, fmt=NUM_FMT, fill=BLUE_FILL)
        r += 1
        write_cell(ws, r, 1, "유통보통주식수 (주당가치 기준)")
        write_cell(ws, r, 2, ctx.vi.company.shares_outstanding, fmt=NUM_FMT,
                   fill=BLUE_FILL, bold=True)
        r += 1


def _write_assumption_drivers(ws, r: int, ctx: _Ctx):
    """Assumptions 시트에 시나리오별 핵심 드라이버 가정 표시."""
    method = ctx.method
    sc_codes = ctx.sc_codes

    if method == "multiples":
        write_cell(ws, r, 1, "적용 멀티플")
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            m = sc.ev_multiple
            if m is None:
                mp = ctx.result.multiples_primary
                m = mp.multiple if mp else 0
            write_cell(ws, r, i, f"{m:.1f}x", fill=BLUE_FILL)

    elif method == "ddm":
        write_cell(ws, r, 1, "배당성장률")
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            g = sc.ddm_growth if sc.ddm_growth is not None else (
                ctx.vi.ddm_params.dividend_growth if ctx.vi.ddm_params else 0)
            write_cell(ws, r, i, f"{g:.1f}%", fill=BLUE_FILL)

    elif method == "rim":
        write_cell(ws, r, 1, "ROE 조정 (%p)")
        for i, sc_code in enumerate(sc_codes, 2):
            adj = ctx.vi.scenarios[sc_code].rim_roe_adj
            label = f"{adj:+.1f}%p" if adj != 0 else "기본"
            write_cell(ws, r, i, label, fill=BLUE_FILL)

    elif method == "nav":
        write_cell(ws, r, 1, "지주할인율")
        for i, sc_code in enumerate(sc_codes, 2):
            write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].nav_discount:.0f}%", fill=BLUE_FILL)


# ═════════════════════════════════════════════════════════════════
# Sheet 2: Financial Summary
# ═════════════════════════════════════════════════════════════════


def _sheet_financials(ctx: _Ctx):
    ws = ctx.wb.create_sheet("Financial Summary")
    ws.sheet_properties.tabColor = "2E86C1"
    ws.column_dimensions['A'].width = 24

    write_cell(ws, 1, 1, f"연결 재무제표 요약 ({ctx.unit})", font=TITLE_FONT)

    headers = ["항목"] + [str(y) for y in ctx.years]
    r = 3
    for c, h in enumerate(headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = 18 if c > 1 else 24
    style_header_row(ws, r, len(headers))

    cons = ctx.cons
    years = ctx.years
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
        write_cell(ws, r, 1, label, bold=True)
        for i, v in enumerate(vals, 2):
            f = '#,##0' if isinstance(v, int) else '0.0'
            write_cell(ws, r, i, v, fmt=f, fill=YELLOW_FILL)

    # 부문별 D&A 배분 (SOTP인 경우만)
    if ctx.method == "sotp" and ctx.result.da_allocations:
        r += 2
        # Mixed SOTP 여부
        _has_mixed_fs = any(
            info.get("method") in ("pbv", "pe") for info in ctx.vi.segments.values()
        )
        fs_title = "부문별 재무 — D&A 배분 (금융 부문 제외)" if _has_mixed_fs else "부문별 재무 — 유무형자산 비중 D&A 배분"
        write_cell(ws, r, 1, fs_title, font=TITLE_FONT); r += 1

        for yr in reversed(years):
            if yr not in ctx.result.da_allocations:
                continue
            r += 1
            write_cell(ws, r, 1, f"── {yr}년 ──", font=SECTION_FONT); r += 1
            if _has_mixed_fs:
                seg_headers = ["부문", "Method", "매출", "영업이익", "유무형자산", "자산비중", "D&A 배분", "EBITDA"]
                ncols_fs = 8
            else:
                seg_headers = ["부문", "매출", "영업이익", "유무형자산", "자산비중", "D&A 배분", "EBITDA"]
                ncols_fs = 7
            for c, h in enumerate(seg_headers, 1):
                write_cell(ws, r, c, h)
            style_header_row(ws, r, ncols_fs)

            alloc = ctx.result.da_allocations[yr]
            for code in ctx.seg_codes:
                r += 1
                s = ctx.vi.segment_data[yr][code]
                a = alloc[code]
                if _has_mixed_fs:
                    seg_method = ctx.vi.segments.get(code, {}).get("method", "ev_ebitda")
                    m_lbl = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(seg_method, seg_method)
                    write_cell(ws, r, 1, ctx.seg_names[code])
                    write_cell(ws, r, 2, m_lbl)
                    write_cell(ws, r, 3, s["revenue"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 4, s["op"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 5, s["assets"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 6, a.asset_share / 100, fmt=PCT_FMT)
                    write_cell(ws, r, 7, a.da_allocated, fmt=NUM_FMT)
                    write_cell(ws, r, 8, a.ebitda, fmt=NUM_FMT,
                               fill=GREEN_FILL if a.ebitda > 0 else RED_FILL)
                else:
                    write_cell(ws, r, 1, ctx.seg_names[code])
                    write_cell(ws, r, 2, s["revenue"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 3, s["op"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 4, s["assets"], fmt=NUM_FMT, fill=YELLOW_FILL)
                    write_cell(ws, r, 5, a.asset_share / 100, fmt=PCT_FMT)
                    write_cell(ws, r, 6, a.da_allocated, fmt=NUM_FMT)
                    write_cell(ws, r, 7, a.ebitda, fmt=NUM_FMT,
                               fill=GREEN_FILL if a.ebitda > 0 else RED_FILL)

            r += 1
            write_cell(ws, r, 1, "합계", bold=True)
            if _has_mixed_fs:
                write_cell(ws, r, 3, sum(ctx.vi.segment_data[yr][c]["revenue"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 4, sum(ctx.vi.segment_data[yr][c]["op"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 5, sum(ctx.vi.segment_data[yr][c]["assets"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 6, 1.0, fmt=PCT_FMT, bold=True)
                write_cell(ws, r, 7, sum(alloc[c].da_allocated for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 8, sum(alloc[c].ebitda for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
            else:
                write_cell(ws, r, 2, sum(ctx.vi.segment_data[yr][c]["revenue"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 3, sum(ctx.vi.segment_data[yr][c]["op"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 4, sum(ctx.vi.segment_data[yr][c]["assets"] for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 5, 1.0, fmt=PCT_FMT, bold=True)
                write_cell(ws, r, 6, sum(alloc[c].da_allocated for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)
                write_cell(ws, r, 7, sum(alloc[c].ebitda for c in ctx.seg_codes), fmt=NUM_FMT, bold=True)


# ═════════════════════════════════════════════════════════════════
# Sheet 3: Valuation (방법론별)
# ═════════════════════════════════════════════════════════════════


def _valuation_sotp(ctx: _Ctx):
    ws = ctx.wb.create_sheet("SOTP Valuation")
    ws.sheet_properties.tabColor = "27AE60"
    ws.column_dimensions['A'].width = 20

    write_cell(ws, 1, 1, f"SOTP 밸류에이션 ({ctx.by}년 기준, {ctx.unit})", font=TITLE_FONT)

    r = 3
    if ctx.result.sotp:
        # Mixed SOTP 여부 판단
        has_mixed = any(
            getattr(s, "method", "ev_ebitda") != "ev_ebitda"
            for s in ctx.result.sotp.values()
        )
        if has_mixed:
            write_cell(ws, r, 1, "부문별 SOTP (Mixed Method)", font=SECTION_FONT); r += 1
            sotp_headers = ["부문", "Method", "지표값", "멀티플", "Segment Value", "비중"]
            ncols = 6
        else:
            write_cell(ws, r, 1, "부문별 EV/EBITDA", font=SECTION_FONT); r += 1
            sotp_headers = ["부문", "EBITDA", "멀티플", "Segment EV", "EV 비중"]
            ncols = 5
        for c, h in enumerate(sotp_headers, 1):
            write_cell(ws, r, c, h)
            ws.column_dimensions[get_column_letter(c)].width = 16
        style_header_row(ws, r, ncols)

        for code in ctx.seg_codes:
            if code not in ctx.result.sotp:
                continue
            r += 1
            s = ctx.result.sotp[code]
            ev_pct = s.ev / ctx.result.total_ev if ctx.result.total_ev > 0 else 0
            if has_mixed:
                method = getattr(s, "method", "ev_ebitda")
                method_label = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(method, method)
                # 지표값: EV/EBITDA→EBITDA, P/BV→Book Equity, P/E→Net Income
                seg_info = ctx.vi.segments.get(code, {})
                if method == "pbv":
                    metric_val = seg_info.get("book_equity", 0)
                elif method == "pe":
                    metric_val = seg_info.get("net_income_segment", 0)
                else:
                    metric_val = s.ebitda
                write_cell(ws, r, 1, ctx.seg_names[code])
                write_cell(ws, r, 2, method_label)
                write_cell(ws, r, 3, metric_val, fmt=NUM_FMT)
                write_cell(ws, r, 4, s.multiple, fmt=MULT_FMT, fill=BLUE_FILL)
                write_cell(ws, r, 5, s.ev, fmt=NUM_FMT, fill=GREEN_FILL if s.ev > 0 else None)
                write_cell(ws, r, 6, ev_pct, fmt=PCT_FMT)
            else:
                write_cell(ws, r, 1, ctx.seg_names[code])
                write_cell(ws, r, 2, s.ebitda, fmt=NUM_FMT)
                write_cell(ws, r, 3, s.multiple, fmt=MULT_FMT, fill=BLUE_FILL)
                write_cell(ws, r, 4, s.ev, fmt=NUM_FMT, fill=GREEN_FILL if s.ev > 0 else None)
                write_cell(ws, r, 5, ev_pct, fmt=PCT_FMT)
        r += 1
        write_cell(ws, r, 1, "합계", bold=True)
        if has_mixed:
            write_cell(ws, r, 5, ctx.result.total_ev, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)
            write_cell(ws, r, 6, 1.0, fmt=PCT_FMT, bold=True)
        else:
            write_cell(ws, r, 2, sum(ctx.result.sotp[c].ebitda for c in ctx.seg_codes if c in ctx.result.sotp), fmt=NUM_FMT, bold=True)
            write_cell(ws, r, 4, ctx.result.total_ev, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)
            write_cell(ws, r, 5, 1.0, fmt=PCT_FMT, bold=True)

        # Mixed SOTP: Equity Bridge 표시
        if has_mixed:
            r += 2
            write_cell(ws, r, 1, "Equity Bridge (Mixed SOTP)", font=SECTION_FONT); r += 1
            ev_segs_val = sum(s.ev for s in ctx.result.sotp.values() if not getattr(s, "is_equity_based", False))
            eq_segs_val = sum(s.ev for s in ctx.result.sotp.values() if getattr(s, "is_equity_based", False))
            fin_debt = sum(
                ctx.vi.segment_net_debt.get(c, 0)
                for c, info in ctx.vi.segments.items()
                if info.get("method") in ("pbv", "pe")
            )
            eff_nd = ctx.vi.net_debt - fin_debt
            bridge_items = [
                ("제조 부문 EV (EV/EBITDA)", ev_segs_val),
                ("(-) 유효 순차입금 (제조)", eff_nd),
                ("제조 부문 Equity", ev_segs_val - eff_nd),
                ("(+) 금융 부문 Equity (P/BV)", eq_segs_val),
                ("Total Equity", ev_segs_val - eff_nd + eq_segs_val),
            ]
            for label, val in bridge_items:
                is_total = label == "Total Equity"
                write_cell(ws, r, 1, label, bold=is_total)
                write_cell(ws, r, 2, val, fmt=NUM_FMT, bold=is_total,
                           fill=GREEN_FILL if is_total else YELLOW_FILL)
                write_cell(ws, r, 3, ctx.unit)
                r += 1


def _valuation_dcf(ctx: _Ctx):
    ws = ctx.wb.create_sheet("DCF Valuation")
    ws.sheet_properties.tabColor = "2E86C1"
    ws.column_dimensions['A'].width = 24

    write_cell(ws, 1, 1, f"DCF 밸류에이션 — FCFF ({ctx.unit})", font=TITLE_FONT)

    dcf = ctx.result.dcf
    if not dcf:
        write_cell(ws, 3, 1, "DCF 결과 없음", font=SECTION_FONT)
        return

    # FCF Projection 테이블
    r = 3
    write_cell(ws, r, 1, "Free Cash Flow 추정", font=SECTION_FONT); r += 1
    proj_headers = ["연도", "EBITDA", "D&A", "영업이익", "NOPAT", "Capex", "ΔNWC", "FCFF", "성장률", "PV(FCFF)"]
    for c, h in enumerate(proj_headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = 14
    style_header_row(ws, r, len(proj_headers))

    for p in dcf.projections:
        r += 1
        vals = [
            (p.year, None), (p.ebitda, NUM_FMT), (p.da, NUM_FMT), (p.op, NUM_FMT),
            (p.nopat, NUM_FMT), (p.capex, NUM_FMT), (p.delta_nwc, NUM_FMT),
            (p.fcff, NUM_FMT), (p.growth, PCT_FMT), (p.pv_fcff, NUM_FMT),
        ]
        for c, (v, fmt) in enumerate(vals, 1):
            fill = GREEN_FILL if c == 8 and v > 0 else (RED_FILL if c == 8 and v < 0 else None)
            write_cell(ws, r, c, v, fmt=fmt, fill=fill)

    # DCF 요약
    r += 2
    write_cell(ws, r, 1, "DCF 밸류에이션 요약", font=SECTION_FONT); r += 1
    summary = [
        ("PV(FCFF) 합계", dcf.pv_fcff_sum),
        ("Terminal Value", dcf.terminal_value),
        ("PV(Terminal Value)", dcf.pv_terminal),
        ("Enterprise Value (DCF)", dcf.ev_dcf),
    ]
    for label, val in summary:
        write_cell(ws, r, 1, label)
        is_ev = "Enterprise" in label
        write_cell(ws, r, 2, val, fmt=NUM_FMT,
                   fill=GREEN_FILL if is_ev else YELLOW_FILL,
                   bold=is_ev)
        write_cell(ws, r, 3, ctx.unit)
        r += 1

    r += 1
    write_cell(ws, r, 1, f"WACC: {dcf.wacc:.2f}%  |  Terminal Growth: {dcf.terminal_growth:.1f}%",
               font=NOTE_FONT)


def _valuation_ddm(ctx: _Ctx):
    ws = ctx.wb.create_sheet("DDM Valuation")
    ws.sheet_properties.tabColor = "27AE60"
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 36

    write_cell(ws, 1, 1, "DDM 밸류에이션 — 배당할인모델 (Gordon Growth)", font=TITLE_FONT)

    ddm = ctx.result.ddm
    if not ddm:
        write_cell(ws, 3, 1, "DDM 결과 없음", font=SECTION_FONT)
        return

    r = 3
    write_cell(ws, r, 1, "DDM 핵심 파라미터", font=SECTION_FONT); r += 1
    ddm_items = [
        ("주당 배당금 (DPS)", f"{ddm.dps:,.0f}", "최근 실적 기반"),
    ]
    if ddm.buyback_per_share > 0:
        ddm_items.append(("주당 자사주매입", f"{ddm.buyback_per_share:,.0f}", "Total Payout"))
        ddm_items.append(("Total Payout/주", f"{ddm.total_payout:,.0f}", "DPS + Buyback"))
    ddm_items += [
        ("배당 성장률 (g)", f"{ddm.growth:.2f}%", "지속가능 성장률"),
        ("자기자본비용 (Ke)", f"{ddm.ke:.2f}%", "CAPM: Rf + βL × ERP"),
        ("", "", ""),
        ("주당 내재가치", f"{ddm.equity_per_share:,}", "DPS×(1+g) / (Ke-g)"),
    ]
    for label, val, note in ddm_items:
        if not label:
            r += 1; continue
        write_cell(ws, r, 1, label)
        is_result = "내재가치" in label
        fill = GREEN_FILL if is_result else BLUE_FILL
        font = RESULT_FONT if is_result else None
        write_cell(ws, r, 2, val, fill=fill, font=font)
        write_cell(ws, r, 3, note)
        r += 1

    # DDM 민감도 (Ke × Growth)
    r += 1
    _write_ddm_sensitivity(ws, r, ddm, ctx.currency_sym)


def _write_ddm_sensitivity(ws, r: int, ddm, currency_sym: str):
    """DDM Ke × Growth 민감도 테이블."""
    write_cell(ws, r, 1, f"DDM 민감도 — Ke × 배당성장률 → 주당가치 ({currency_sym})", font=SECTION_FONT)
    r += 1

    ke_base, g_base = ddm.ke, ddm.growth
    ke_range = [ke_base + d for d in [-2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0]]
    g_range = [g_base + d for d in [-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5]]

    write_cell(ws, r, 1, "Ke \\ Growth", fill=GRAY_FILL, font=HEADER_FONT)
    for j, g_val in enumerate(g_range, 2):
        write_cell(ws, r, j, f"{g_val:.1f}%", fill=GRAY_FILL, font=HEADER_FONT)
        ws.column_dimensions[get_column_letter(j)].width = 12

    from engine.ddm import calc_ddm as _calc_ddm
    sens_start = r + 1
    for ke_val in ke_range:
        r += 1
        write_cell(ws, r, 1, f"{ke_val:.1f}%", fill=GRAY_FILL, font=HEADER_FONT)
        for j, g_val in enumerate(g_range, 2):
            try:
                v = _calc_ddm(ddm.dps, g_val, ke_val,
                              buyback_per_share=getattr(ddm, 'buyback_per_share', 0.0)).equity_per_share
            except ValueError:
                v = 0
            is_base = abs(ke_val - ke_base) < 0.01 and abs(g_val - g_base) < 0.01
            fill = GREEN_FILL if is_base else (RED_FILL if v <= 0 else None)
            write_cell(ws, r, j, v, fmt=NUM_FMT, fill=fill)
    sens_end = r

    if g_range:
        end_col = get_column_letter(1 + len(g_range))
        ws.conditional_formatting.add(
            f"B{sens_start}:{end_col}{sens_end}", ColorScaleRule(
            start_type='min', start_color='FADBD8',
            mid_type='percentile', mid_value=50, mid_color='F5F6FA',
            end_type='max', end_color='D5F5E3',
        ))


def _valuation_rim(ctx: _Ctx):
    ws = ctx.wb.create_sheet("RIM Valuation")
    ws.sheet_properties.tabColor = "8E44AD"
    for col in 'ABCDEF':
        ws.column_dimensions[col].width = 20
    ws.column_dimensions['A'].width = 28

    write_cell(ws, 1, 1, "RIM 밸류에이션 — 잔여이익모델 (Residual Income)", font=TITLE_FONT)

    rim = ctx.result.rim
    if not rim:
        write_cell(ws, 3, 1, "RIM 결과 없음", font=SECTION_FONT)
        return

    r = 3
    write_cell(ws, r, 1, "RIM 핵심 파라미터", font=SECTION_FONT); r += 1
    rim_items = [
        ("장부가치 (BV₀)", f"{rim.bv_current:,}", "현재 자기자본"),
        ("자기자본비용 (Ke)", f"{rim.ke:.2f}%", "CAPM: Rf + βL × ERP"),
        ("영구성장률 (g)", f"{rim.terminal_growth:.2f}%", "RI Terminal Growth"),
        ("PV(RI)", f"{rim.pv_ri_sum:,}", "예측기간 잔여이익 현재가치"),
        ("PV(TV)", f"{rim.pv_terminal:,}", "잔여이익 Terminal Value 현재가치"),
        ("자기자본가치", f"{rim.equity_value:,}", "BV + PV(RI) + PV(TV)"),
        ("주당 내재가치", f"{rim.per_share:,}", "자기자본가치 / 주식수"),
    ]
    for label, val, note in rim_items:
        write_cell(ws, r, 1, label, fill=GRAY_FILL, font=WHITE_FONT)
        is_result = "내재가치" in label
        write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else None,
                   font=RESULT_FONT if is_result else None)
        write_cell(ws, r, 3, note, font=NOTE_FONT)
        r += 1

    # 연도별 예측
    r += 1
    write_cell(ws, r, 1, "연도별 잔여이익 예측", font=SECTION_FONT); r += 1
    headers = ["Year", "기초 BV", "당기순이익", "ROE (%)", "잔여이익 (RI)", "PV(RI)"]
    for j, h in enumerate(headers, 1):
        write_cell(ws, r, j, h, fill=DARK_FILL, font=WHITE_FONT)
    r += 1
    for p in rim.projections:
        write_cell(ws, r, 1, f"Y{p.year}")
        write_cell(ws, r, 2, p.bv, fmt=NUM_FMT)
        write_cell(ws, r, 3, p.net_income, fmt=NUM_FMT)
        write_cell(ws, r, 4, p.roe / 100, fmt=PCT_FMT)
        write_cell(ws, r, 5, p.ri, fmt=NUM_FMT)
        write_cell(ws, r, 6, p.pv_ri, fmt=NUM_FMT)
        r += 1


def _valuation_nav(ctx: _Ctx):
    ws = ctx.wb.create_sheet("NAV Valuation")
    ws.sheet_properties.tabColor = "E67E22"
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 36

    write_cell(ws, 1, 1, "NAV 밸류에이션 — 순자산가치평가법", font=TITLE_FONT)

    nav = ctx.result.nav
    if not nav:
        write_cell(ws, 3, 1, "NAV 결과 없음", font=SECTION_FONT)
        return

    r = 3
    write_cell(ws, r, 1, f"순자산가치 구성 ({ctx.unit})", font=SECTION_FONT); r += 1
    nav_items = [
        ("총자산 (장부가)", nav.total_assets, ""),
        ("(+) 투자자산 재평가", nav.revaluation, "공정가치 − 장부가"),
        ("조정 후 총자산", nav.adjusted_assets, ""),
        ("(-) 총부채", nav.total_liabilities, ""),
        ("", 0, ""),
        ("순자산가치 (NAV)", nav.nav, "조정자산 − 부채"),
        ("주당 NAV", nav.per_share, f"{ctx.currency_sym}"),
    ]
    for label, val, note in nav_items:
        if not label:
            r += 1; continue
        write_cell(ws, r, 1, label)
        is_result = "주당" in label or "순자산가치 (NAV)" in label
        write_cell(ws, r, 2, val, fmt=NUM_FMT,
                   fill=GREEN_FILL if is_result else YELLOW_FILL,
                   font=RESULT_FONT if "주당" in label else None)
        if note:
            write_cell(ws, r, 3, note, font=NOTE_FONT)
        r += 1


def _valuation_multiples(ctx: _Ctx):
    ws = ctx.wb.create_sheet("Multiples Valuation")
    ws.sheet_properties.tabColor = "17A589"
    ws.column_dimensions['A'].width = 24
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 18

    write_cell(ws, 1, 1, "상대가치평가 — Multiples Primary", font=TITLE_FONT)

    mp = ctx.result.multiples_primary
    if not mp:
        write_cell(ws, 3, 1, "Multiples 결과 없음", font=SECTION_FONT)
        return

    r = 3
    write_cell(ws, r, 1, "적용 방법론", font=SECTION_FONT); r += 1
    items = [
        ("방법론", mp.primary_multiple_method, ""),
        ("지표값", f"{mp.metric_value:,.0f}", ctx.unit),
        ("적용 멀티플", f"{mp.multiple:.1f}x", "Peer Median 기반"),
        ("Enterprise Value", f"{mp.enterprise_value:,}", ctx.unit),
        ("Equity Value", f"{mp.equity_value:,}", ctx.unit),
        ("주당 가치", f"{mp.per_share:,}", ctx.currency_sym),
    ]
    for label, val, note in items:
        write_cell(ws, r, 1, label)
        is_result = "주당" in label
        write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else BLUE_FILL,
                   font=RESULT_FONT if is_result else None)
        if note:
            write_cell(ws, r, 3, note, font=NOTE_FONT)
        r += 1


_VALUATION_MAP = {
    "sotp": _valuation_sotp,
    "dcf_primary": _valuation_dcf,
    "ddm": _valuation_ddm,
    "rim": _valuation_rim,
    "nav": _valuation_nav,
    "multiples": _valuation_multiples,
}


# ═════════════════════════════════════════════════════════════════
# Sheet 4: Peer Comparison
# ═════════════════════════════════════════════════════════════════


def _sheet_peers(ctx: _Ctx):
    if not ctx.vi.peers and not ctx.result.peer_stats:
        return

    ws = ctx.wb.create_sheet("Peer Comparison")
    ws.sheet_properties.tabColor = "17A589"
    write_cell(ws, 1, 1, "유사기업 비교분석 (Comparable Company Analysis)", font=TITLE_FONT)

    r = 3
    has_extra = any(p.ticker for p in ctx.vi.peers)
    if has_extra:
        peer_headers = ["기업명", "Ticker", "매핑 부문", "EV/EBITDA", "P/E (TTM)", "P/BV", "Beta", "출처", "비고"]
        col_widths = [20, 10, 16, 12, 12, 10, 8, 8, 40]
    else:
        peer_headers = ["기업명", "매핑 부문", "EV/EBITDA", "비고"]
        col_widths = [20, 18, 12, 50]
    for c, h in enumerate(peer_headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = col_widths[c - 1]
    style_header_row(ws, r, len(peer_headers))

    for p in ctx.vi.peers:
        r += 1
        c = 1
        write_cell(ws, r, c, p.name); c += 1
        if has_extra:
            write_cell(ws, r, c, p.ticker or "-"); c += 1
        write_cell(ws, r, c, ctx.seg_names.get(p.segment_code, p.segment_code)); c += 1
        write_cell(ws, r, c, p.ev_ebitda, fmt=MULT_FMT, fill=YELLOW_FILL); c += 1
        if has_extra:
            write_cell(ws, r, c, p.trailing_pe or "-", fmt=MULT_FMT if p.trailing_pe else None); c += 1
            write_cell(ws, r, c, p.pbv or "-", fmt=MULT_FMT if p.pbv else None); c += 1
            write_cell(ws, r, c, f"{p.beta:.2f}" if p.beta else "-"); c += 1
            write_cell(ws, r, c, p.source); c += 1
        write_cell(ws, r, c, p.notes)

    # 부문별 멀티플 통계
    if ctx.result.peer_stats:
        r += 2
        write_cell(ws, r, 1, "부문별 EV/EBITDA 멀티플 통계", font=SECTION_FONT); r += 1
        stat_headers = ["부문", "Peer 수", "Min", "Q1", "Median", "Mean", "Q3", "Max", "적용 멀티플"]
        for c, h in enumerate(stat_headers, 1):
            write_cell(ws, r, c, h)
            ws.column_dimensions[get_column_letter(c)].width = max(
                ws.column_dimensions[get_column_letter(c)].width or 0, [18, 8, 8, 8, 8, 8, 8, 8, 12][c - 1]
            )
        style_header_row(ws, r, len(stat_headers))

        for ps in ctx.result.peer_stats:
            r += 1
            write_cell(ws, r, 1, ps.segment_name)
            write_cell(ws, r, 2, ps.count)
            write_cell(ws, r, 3, ps.ev_ebitda_min, fmt=MULT_FMT)
            write_cell(ws, r, 4, ps.ev_ebitda_q1, fmt=MULT_FMT)
            write_cell(ws, r, 5, ps.ev_ebitda_median, fmt=MULT_FMT, fill=GREEN_FILL)
            write_cell(ws, r, 6, ps.ev_ebitda_mean, fmt=MULT_FMT)
            write_cell(ws, r, 7, ps.ev_ebitda_q3, fmt=MULT_FMT)
            write_cell(ws, r, 8, ps.ev_ebitda_max, fmt=MULT_FMT)
            applied = ps.applied_multiple
            fill = GREEN_FILL if abs(applied - ps.ev_ebitda_median) <= 2.0 else YELLOW_FILL
            write_cell(ws, r, 9, applied, fmt=MULT_FMT, fill=fill, bold=True)


# ═════════════════════════════════════════════════════════════════
# Sheet 5: Scenario Analysis (동적 Waterfall Bridge)
# ═════════════════════════════════════════════════════════════════


def _sheet_scenarios(ctx: _Ctx):
    ws = ctx.wb.create_sheet("Scenario Analysis")
    ws.sheet_properties.tabColor = "F39C12"
    write_cell(ws, 1, 1, f"시나리오 분석 ({ctx.unit})", font=TITLE_FONT)

    sc_codes = ctx.sc_codes
    if not sc_codes:
        return

    r = 3
    sc_headers = ["항목"] + [f"{c}: {ctx.vi.scenarios[c].name}" for c in sc_codes]
    for c, h in enumerate(sc_headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = 20 if c > 1 else 28
    style_header_row(ws, r, len(sc_headers))

    is_listed = ctx.vi.company.legal_status == "상장"
    has_dlom = any(ctx.vi.scenarios[c].dlom > 0 for c in sc_codes)

    # ── 시나리오 기본 가정 ──
    r += 1
    write_cell(ws, r, 1, "확률")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].prob}%", fill=BLUE_FILL)

    # 방법론별 핵심 드라이버 (시나리오 간 차이를 만드는 수치)
    r = _write_scenario_drivers(ws, r, ctx)

    # DLOM — 비상장사이거나 실제로 DLOM이 적용된 경우만 표시
    if not is_listed or has_dlom:
        r += 1
        write_cell(ws, r, 1, "DLOM")
        for i, sc_code in enumerate(sc_codes, 2):
            write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].dlom}%", fill=BLUE_FILL)

    # IRR (비상장 + CPS 있는 경우만)
    if any(ctx.vi.scenarios[c].irr is not None for c in sc_codes):
        r += 1
        write_cell(ws, r, 1, "FI IRR")
        for i, sc_code in enumerate(sc_codes, 2):
            irr = ctx.vi.scenarios[sc_code].irr
            write_cell(ws, r, i, f"{irr}%" if irr else "-", fill=BLUE_FILL)

    # 구분선
    r += 1

    # ── 동적 Equity Bridge (adjustments 기반) ──
    r += 1
    write_cell(ws, r, 1, _ev_label(ctx.method), bold=True)
    for i, sc_code in enumerate(sc_codes, 2):
        sr = ctx.result.scenarios[sc_code]
        write_cell(ws, r, i, sr.total_ev, fmt=NUM_FMT)

    # Adjustments — Waterfall
    first_sr = ctx.result.scenarios[sc_codes[0]]
    for adj_idx, adj in enumerate(first_sr.adjustments):
        r += 1
        write_cell(ws, r, 1, f"(-) {adj.name}")
        for i, sc_code in enumerate(sc_codes, 2):
            sr = ctx.result.scenarios[sc_code]
            val = sr.adjustments[adj_idx].value if adj_idx < len(sr.adjustments) else 0
            write_cell(ws, r, i, val, fmt=NUM_FMT)

    # Equity Value
    r += 1
    write_cell(ws, r, 1, "Equity Value", bold=True)
    for i, sc_code in enumerate(sc_codes, 2):
        sr = ctx.result.scenarios[sc_code]
        fill = GREEN_FILL if sr.equity_value > 0 else RED_FILL
        write_cell(ws, r, i, sr.equity_value, fmt=NUM_FMT, bold=True, fill=fill)

    r += 1  # 구분선

    # ── 주당 가치 ──
    r += 1
    write_cell(ws, r, 1, "적용 주식수")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, ctx.result.scenarios[sc_code].shares, fmt=NUM_FMT)

    if not is_listed or has_dlom:
        # 비상장사: DLOM 전/후 모두 표시
        r += 1
        write_cell(ws, r, 1, "주당 가치 (DLOM 전)")
        for i, sc_code in enumerate(sc_codes, 2):
            write_cell(ws, r, i, ctx.result.scenarios[sc_code].pre_dlom, fmt=NUM_FMT)

        r += 1
        write_cell(ws, r, 1, "주당 가치 (DLOM 후)", bold=True)
        for i, sc_code in enumerate(sc_codes, 2):
            sr = ctx.result.scenarios[sc_code]
            write_cell(ws, r, i, sr.post_dlom, fmt=NUM_FMT, bold=True,
                       fill=GREEN_FILL if sr.post_dlom > 0 else None)
    else:
        # 상장사: 주당 가치 한 줄만 표시
        r += 1
        write_cell(ws, r, 1, "주당 가치", bold=True)
        for i, sc_code in enumerate(sc_codes, 2):
            sr = ctx.result.scenarios[sc_code]
            write_cell(ws, r, i, sr.post_dlom, fmt=NUM_FMT, bold=True,
                       fill=GREEN_FILL if sr.post_dlom > 0 else None)

    r += 1
    write_cell(ws, r, 1, "확률가중 기여")
    for i, sc_code in enumerate(sc_codes, 2):
        write_cell(ws, r, i, ctx.result.scenarios[sc_code].weighted, fmt=NUM_FMT)

    # 확률가중 결론
    r += 2
    write_cell(ws, r, 1, "확률가중 주당 가치", font=Font(bold=True, size=13, color=NAVY))
    write_cell(ws, r, 2, ctx.result.weighted_value, fmt=NUM_FMT,
               font=Font(bold=True, size=13, color="27AE60"), fill=GREEN_FILL)
    write_cell(ws, r, 3, ctx.currency_sym, font=Font(bold=True, size=13, color=NAVY))

    # ── 시나리오 설명 및 확률 근거 ──
    r += 3
    write_cell(ws, r, 1, "시나리오 설명 및 확률 배분 근거", font=SECTION_FONT); r += 1

    for sc_code in sc_codes:
        sc = ctx.vi.scenarios[sc_code]
        r += 1
        write_cell(ws, r, 1, f"{sc_code}: {sc.name}", font=Font(bold=True, color=NAVY))
        write_cell(ws, r, 2, f"확률 {sc.prob}%", fill=BLUE_FILL)
        if sc.desc:
            r += 1
            write_cell(ws, r, 1, f"  설명: {sc.desc}", font=NOTE_FONT)
            # 긴 텍스트 병합 표시용 너비 확보
            ws.column_dimensions[get_column_letter(1)].width = max(
                ws.column_dimensions[get_column_letter(1)].width or 0, 50)
        if sc.probability_rationale:
            r += 1
            write_cell(ws, r, 1, f"  확률 근거: {sc.probability_rationale}", font=NOTE_FONT)

    # ── 뉴스 → 드라이버 매핑 (AI 분석 근거) ──
    has_rationale = any(
        ctx.vi.scenarios[c].driver_rationale for c in sc_codes
    )
    if has_rationale:
        r += 3
        write_cell(ws, r, 1, "뉴스 → 드라이버 매핑 (AI 분석 근거)", font=SECTION_FONT)
        r += 1
        driver_labels = {
            "growth_adj_pct": "EBITDA 성장률 조정",
            "terminal_growth_adj": "영구성장률 조정",
            "wacc_adj": "WACC 조정",
            "market_sentiment_pct": "시장 심리 조정",
            "ddm_growth": "배당성장률",
            "ev_multiple": "적용 멀티플",
            "rim_roe_adj": "ROE 조정",
            "nav_discount": "지주할인율",
        }
        for sc_code in sc_codes:
            sc = ctx.vi.scenarios[sc_code]
            if not sc.driver_rationale:
                continue
            r += 1
            write_cell(ws, r, 1, f"{sc_code}: {sc.name}",
                       font=Font(bold=True, color=NAVY))
            for driver_name, rationale in sc.driver_rationale.items():
                r += 1
                label = driver_labels.get(driver_name, driver_name)
                write_cell(ws, r, 1, f"  {label}", font=NOTE_FONT)
                write_cell(ws, r, 2, rationale, font=NOTE_FONT)


def _write_scenario_drivers(ws, r: int, ctx: _Ctx) -> int:
    """방법론별 시나리오 핵심 드라이버 + 계산 과정 행 출력."""
    sc_codes = ctx.sc_codes
    method = ctx.method
    calc_font = Font(italic=True, size=9, color="566573")

    if method == "multiples":
        mp = ctx.result.multiples_primary
        base_metric = mp.metric_value if mp else 0
        base_method = mp.primary_multiple_method if mp else "EV/EBITDA"

        # 드라이버: 적용 멀티플
        r += 1
        write_cell(ws, r, 1, f"적용 {base_method}", bold=True)
        sc_multiples = []
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            m = sc.ev_multiple if sc.ev_multiple is not None else (mp.multiple if mp else 0)
            sc_multiples.append(m)
            write_cell(ws, r, i, f"{m:.1f}x", fill=DRIVER_FILL, bold=True)

        # 계산: 기초 지표
        r += 1
        metric_label = {"EV/EBITDA": "EBITDA", "P/E": "순이익", "P/BV": "자기자본"}.get(
            base_method, "Metric")
        write_cell(ws, r, 1, metric_label, font=calc_font)
        for i in range(len(sc_codes)):
            write_cell(ws, r, i + 2, base_metric, fmt=NUM_FMT, font=calc_font)

        # 계산: 산식 = Metric × Multiple
        r += 1
        write_cell(ws, r, 1, f"  {metric_label} × {base_method}", font=calc_font)
        for i, m in enumerate(sc_multiples):
            write_cell(ws, r, i + 2, round(base_metric * m), fmt=NUM_FMT, font=calc_font)

    elif method == "ddm":
        ddm = ctx.result.ddm
        dps = ddm.dps if ddm else 0
        ke = ddm.ke if ddm else 0

        # 드라이버: 배당성장률
        r += 1
        write_cell(ws, r, 1, "배당성장률 (g)", bold=True)
        sc_growths = []
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            g = sc.ddm_growth if sc.ddm_growth is not None else (
                ctx.vi.ddm_params.dividend_growth if ctx.vi.ddm_params else 0)
            sc_growths.append(g)
            write_cell(ws, r, i, f"{g:.1f}%", fill=DRIVER_FILL, bold=True)

        # 계산: Ke (시나리오별 wacc_adj 반영)
        r += 1
        has_wacc_adj = any(ctx.vi.scenarios[c].wacc_adj != 0 for c in sc_codes)
        write_cell(ws, r, 1, "Ke (자기자본비용)", font=calc_font)
        for i, sc_code in enumerate(sc_codes):
            sc_ke = ke + ctx.vi.scenarios[sc_code].wacc_adj
            write_cell(ws, r, i + 2, f"{sc_ke:.2f}%", font=calc_font)

        # 계산: DPS
        r += 1
        write_cell(ws, r, 1, "DPS (주당배당금)", font=calc_font)
        for i in range(len(sc_codes)):
            write_cell(ws, r, i + 2, f"{dps:,.0f}원", font=calc_font)

        # 계산: 산식 (시나리오별 Ke 반영)
        r += 1
        write_cell(ws, r, 1, "산식: DPS×(1+g) / (Ke-g)", font=calc_font)
        for i, g in enumerate(sc_growths):
            sc_ke = ke + ctx.vi.scenarios[sc_codes[i]].wacc_adj
            spread = sc_ke - g
            if spread > 0:
                val = round(dps * (1 + g / 100) / (spread / 100))
            else:
                val = 0
            write_cell(ws, r, i + 2, f"{val:,.0f}원", font=calc_font)

    elif method == "rim":
        ke = ctx.result.wacc.ke
        base_roes = ctx.vi.rim_params.roe_forecasts if ctx.vi.rim_params else []
        by = ctx.vi.base_year
        equity_bv = ctx.vi.consolidated[by].get("equity", 0)

        # 드라이버: ROE 조정
        r += 1
        write_cell(ws, r, 1, "ROE 조정 (%p)", bold=True)
        sc_adjs = []
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            adj = sc.rim_roe_adj
            sc_adjs.append(adj)
            label = f"{adj:+.1f}%p" if adj != 0 else "기본"
            write_cell(ws, r, i, label, fill=DRIVER_FILL, bold=True)

        # 계산: 적용 ROE (1년차)
        if base_roes:
            r += 1
            write_cell(ws, r, 1, "적용 ROE (1년차)", font=calc_font)
            for i, adj in enumerate(sc_adjs):
                roe1 = base_roes[0] + adj
                write_cell(ws, r, i + 2, f"{roe1:.1f}%", font=calc_font)

        # 계산: Ke (시나리오별 wacc_adj 반영)
        r += 1
        write_cell(ws, r, 1, "Ke (자기자본비용)", font=calc_font)
        for i, sc_code in enumerate(sc_codes):
            sc_ke = ke + ctx.vi.scenarios[sc_code].wacc_adj
            write_cell(ws, r, i + 2, f"{sc_ke:.2f}%", font=calc_font)

        # 계산: RI Spread = ROE - Ke (시나리오별)
        if base_roes:
            r += 1
            write_cell(ws, r, 1, "RI Spread (ROE-Ke)", font=calc_font)
            for i, adj in enumerate(sc_adjs):
                sc_ke = ke + ctx.vi.scenarios[sc_codes[i]].wacc_adj
                spread = base_roes[0] + adj - sc_ke
                color = "27AE60" if spread > 0 else "E74C3C"
                write_cell(ws, r, i + 2, f"{spread:+.1f}%p",
                           font=Font(italic=True, size=9, color=color))

        # 계산: 장부가
        r += 1
        write_cell(ws, r, 1, "자기자본 (BV)", font=calc_font)
        for i in range(len(sc_codes)):
            write_cell(ws, r, i + 2, equity_bv, fmt=NUM_FMT, font=calc_font)

        # 계산: 산식 설명
        r += 1
        write_cell(ws, r, 1, "산식: BV + PV(RI) + PV(TV)", font=calc_font)

    elif method == "nav":
        nav_result = ctx.result.nav
        base_nav = nav_result.nav if nav_result else 0

        # 드라이버: 지주할인율
        r += 1
        write_cell(ws, r, 1, "지주할인율", bold=True)
        sc_discounts = []
        for i, sc_code in enumerate(sc_codes, 2):
            sc = ctx.vi.scenarios[sc_code]
            sc_discounts.append(sc.nav_discount)
            write_cell(ws, r, i, f"{sc.nav_discount:.0f}%", fill=DRIVER_FILL, bold=True)

        # 계산: NAV (할인 전)
        r += 1
        write_cell(ws, r, 1, "NAV (할인 전)", font=calc_font)
        for i in range(len(sc_codes)):
            write_cell(ws, r, i + 2, base_nav, fmt=NUM_FMT, font=calc_font)

        # 계산: 산식 = NAV × (1 - 할인율)
        r += 1
        write_cell(ws, r, 1, "산식: NAV × (1 - 할인율)", font=calc_font)
        for i, disc in enumerate(sc_discounts):
            discounted = round(base_nav * (1 - disc / 100))
            write_cell(ws, r, i + 2, discounted, fmt=NUM_FMT, font=calc_font)

    elif method == "dcf_primary":
        has_growth = any(ctx.vi.scenarios[c].growth_adj_pct != 0 for c in sc_codes)
        has_tg = any(ctx.vi.scenarios[c].terminal_growth_adj != 0 for c in sc_codes)
        if has_growth:
            r += 1
            write_cell(ws, r, 1, "EBITDA 성장률 조정", bold=True)
            for i, sc_code in enumerate(sc_codes, 2):
                adj = ctx.vi.scenarios[sc_code].growth_adj_pct
                label = f"{adj:+.0f}%" if adj != 0 else "기본"
                write_cell(ws, r, i, label, fill=DRIVER_FILL, bold=True)
        if has_tg:
            r += 1
            write_cell(ws, r, 1, "영구성장률 조정", bold=True)
            for i, sc_code in enumerate(sc_codes, 2):
                adj = ctx.vi.scenarios[sc_code].terminal_growth_adj
                label = f"{adj:+.1f}%p" if adj != 0 else "기본"
                write_cell(ws, r, i, label, fill=DRIVER_FILL, bold=True)
        # 계산: WACC (시나리오별 wacc_adj 반영)
        r += 1
        write_cell(ws, r, 1, "WACC", font=calc_font)
        for i, sc_code in enumerate(sc_codes):
            sc_wacc = ctx.result.wacc.wacc + ctx.vi.scenarios[sc_code].wacc_adj
            write_cell(ws, r, i + 2, f"{sc_wacc:.2f}%", font=calc_font)
        r += 1
        write_cell(ws, r, 1, "산식: DCF(FCFF, WACC, TGR)", font=calc_font)

    has_sentiment = any(ctx.vi.scenarios[c].market_sentiment_pct != 0 for c in sc_codes)
    if has_sentiment:
        r += 1
        write_cell(ws, r, 1, "시장 심리 조정", bold=True)
        for i, sc_code in enumerate(sc_codes, 2):
            adj = ctx.vi.scenarios[sc_code].market_sentiment_pct
            label = f"{adj:+.0f}%" if adj != 0 else "-"
            write_cell(ws, r, i, label, fill=DRIVER_FILL, bold=True)

    # WACC 조정 (크로스컷팅 — DCF/DDM/RIM 외 방법론에서도 표시)
    # DDM/RIM/DCF는 각자 Ke/WACC 행에 이미 반영하므로, 여기선 SOTP/Multiples용
    if method in ("sotp", "multiples", "nav"):
        has_wacc_adj = any(ctx.vi.scenarios[c].wacc_adj != 0 for c in sc_codes)
        if has_wacc_adj:
            r += 1
            write_cell(ws, r, 1, "WACC 조정 (%p)", bold=True)
            for i, sc_code in enumerate(sc_codes, 2):
                adj = ctx.vi.scenarios[sc_code].wacc_adj
                label = f"{adj:+.2f}%p" if adj != 0 else "기본"
                write_cell(ws, r, i, label, fill=DRIVER_FILL, bold=True)

    return r


def _ev_label(method: str) -> str:
    """방법론별 EV/Value 라벨."""
    labels = {
        "sotp": "SOTP EV",
        "dcf_primary": "DCF EV",
        "ddm": "DDM Equity Value",
        "rim": "RIM Equity Value",
        "nav": "NAV",
        "multiples": "Multiples EV",
    }
    return labels.get(method, "Enterprise Value")


# ═════════════════════════════════════════════════════════════════
# Sheet 6: Sensitivity (방법론별)
# ═════════════════════════════════════════════════════════════════


def _sheet_sensitivity(ctx: _Ctx):
    ws = ctx.wb.create_sheet("Sensitivity")
    ws.sheet_properties.tabColor = "E74C3C"
    write_cell(ws, 1, 1, "민감도 분석", font=TITLE_FONT)

    r = 3
    method = ctx.method

    # ── SOTP: 멀티플 × 멀티플 ──
    if method == "sotp" and ctx.result.sensitivity_multiples:
        r = _write_sensitivity_table(
            ws, r,
            f"① 멀티플 민감도 → 주당가치 ({ctx.currency_sym})",
            ctx.result.sensitivity_multiples,
            "Row \\ Col", lambda v: f"{v:.0f}x", lambda v: f"{v:.0f}x",
        )
        r += 2

    # ── IRR × DLOM (비상장 전용) ──
    if ctx.result.sensitivity_irr_dlom:
        r = _write_sensitivity_table(
            ws, r,
            f"{'② ' if method == 'sotp' else '① '}FI IRR × DLOM → 주당가치 ({ctx.currency_sym})",
            ctx.result.sensitivity_irr_dlom,
            "IRR \\ DLOM", lambda v: f"{v:.0f}%", lambda v: f"{int(v)}%",
        )
        r += 2

    # ── WACC × Terminal Growth (DCF/SOTP) ──
    if ctx.result.sensitivity_dcf:
        n = sum(1 for x in [ctx.result.sensitivity_multiples, ctx.result.sensitivity_irr_dlom] if x)
        label_n = n + 1
        r = _write_sensitivity_table(
            ws, r,
            f"{'③' if label_n == 3 else '②' if label_n == 2 else '①'} WACC × 영구성장률 → DCF EV ({ctx.unit})",
            ctx.result.sensitivity_dcf,
            "WACC \\ Tg", lambda v: f"{v:.1f}%", lambda v: f"{v:.1f}%",
            ref_value=ctx.result.total_ev if method in ("sotp", "dcf_primary") else None,
        )
        r += 2

    # ── 주방법론 전용 민감도 (DDM Ke×g, RIM Ke×Tg, NAV 재평가×할인, Multiples 배수×할인) ──
    if ctx.result.sensitivity_primary:
        row_fmt, col_fmt, corner = _sensitivity_format(method)
        n = sum(1 for x in [ctx.result.sensitivity_multiples, ctx.result.sensitivity_irr_dlom, ctx.result.sensitivity_dcf] if x)
        label_n = n + 1
        numbering = {1: "①", 2: "②", 3: "③", 4: "④"}.get(label_n, "")
        r = _write_sensitivity_table(
            ws, r,
            f"{numbering} {ctx.result.sensitivity_primary_label}",
            ctx.result.sensitivity_primary,
            corner, row_fmt, col_fmt,
        )
        r += 2

    # ── 참조값 ──
    ref_label, ref_value = _get_ref_label_value(ctx)
    write_cell(ws, r, 1, f"참조: {ref_label} = {ref_value}",
               font=Font(italic=True, size=9, color="566573"))


def _sensitivity_format(method: str):
    """방법론별 민감도 테이블 행/열 포맷."""
    if method == "ddm":
        return lambda v: f"{v:.1f}%", lambda v: f"{v:.1f}%", "Ke \\ Growth"
    elif method == "rim":
        return lambda v: f"{v:.1f}%", lambda v: f"{v:.1f}%", "Ke \\ Tg"
    elif method == "nav":
        return lambda v: f"{v:,.0f}", lambda v: f"{v:.0f}%", "재평가 \\ 할인율"
    elif method == "multiples":
        return lambda v: f"{v:.1f}x", lambda v: f"{v:.0f}%", "멀티플 \\ 할인율"
    return lambda v: f"{v}", lambda v: f"{v}", "Row \\ Col"


def _write_sensitivity_table(ws, r: int, title: str, data: list,
                              corner_label: str, row_fmt, col_fmt,
                              ref_value: int | None = None) -> int:
    """범용 2차원 민감도 테이블 작성. 작성 후 마지막 행 번호 반환."""
    lookup = {(x.row_val, x.col_val): x.value for x in data}
    row_range = sorted(set(x.row_val for x in data))
    col_range = sorted(set(x.col_val for x in data))

    if not row_range or not col_range:
        return r

    write_cell(ws, r, 1, title, font=SECTION_FONT)
    r += 1

    # 헤더
    write_cell(ws, r, 1, corner_label, fill=GRAY_FILL, font=HEADER_FONT)
    for j, col_v in enumerate(col_range, 2):
        write_cell(ws, r, j, col_fmt(col_v), fill=GRAY_FILL, font=HEADER_FONT)
        ws.column_dimensions[get_column_letter(j)].width = 12

    sens_start = r + 1
    for row_v in row_range:
        r += 1
        write_cell(ws, r, 1, row_fmt(row_v), fill=GRAY_FILL, font=HEADER_FONT)
        for j, col_v in enumerate(col_range, 2):
            val = lookup.get((row_v, col_v), 0)
            if ref_value is not None:
                fill = GREEN_FILL if val >= ref_value else RED_FILL
            else:
                fill = GREEN_FILL if val > 0 else RED_FILL
            write_cell(ws, r, j, val, fmt=NUM_FMT, fill=fill)
    sens_end = r

    # Heatmap
    if col_range and sens_end >= sens_start:
        end_col = get_column_letter(1 + len(col_range))
        ws.conditional_formatting.add(
            f"B{sens_start}:{end_col}{sens_end}", ColorScaleRule(
            start_type='min', start_color='FADBD8',
            mid_type='percentile', mid_value=50, mid_color='F5F6FA',
            end_type='max', end_color='D5F5E3',
        ))

    return r


def _get_ref_label_value(ctx: _Ctx) -> tuple[str, str]:
    if ctx.method == "ddm" and ctx.result.ddm:
        return "DDM 주당가치", f"{ctx.result.ddm.equity_per_share:,}{ctx.currency_sym}"
    elif ctx.method == "rim" and ctx.result.rim:
        return "RIM 주당가치", f"{ctx.result.rim.per_share:,}{ctx.currency_sym}"
    elif ctx.method == "nav" and ctx.result.nav:
        return "NAV 주당가치", f"{ctx.result.nav.per_share:,}{ctx.currency_sym}"
    elif ctx.method == "multiples" and ctx.result.multiples_primary:
        return "Multiples 주당가치", f"{ctx.result.multiples_primary.per_share:,}{ctx.currency_sym}"
    elif ctx.result.dcf:
        return "DCF EV", f"{ctx.result.dcf.ev_dcf:,}{ctx.unit}"
    else:
        return "Total EV", f"{ctx.result.total_ev:,}{ctx.unit}"


# ═════════════════════════════════════════════════════════════════
# Sheet 7: Dashboard
# ═════════════════════════════════════════════════════════════════


def _sheet_dashboard(ctx: _Ctx):
    ws = ctx.wb.create_sheet("Dashboard")
    ws.sheet_properties.tabColor = NAVY
    ws.column_dimensions['A'].width = 30
    ws.column_dimensions['B'].width = 20
    ws.column_dimensions['C'].width = 16
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 18
    ws.column_dimensions['F'].width = 18

    method_labels = {
        "sotp": "SOTP (Sum-of-the-Parts)",
        "dcf_primary": "DCF (Discounted Cash Flow)",
        "ddm": "DDM (배당할인모델)",
        "rim": "RIM (잔여이익모델)",
        "nav": "NAV (순자산가치)",
        "multiples": "Multiples (상대가치평가)",
    }
    method_desc = method_labels.get(ctx.method, ctx.method.upper())

    write_cell(ws, 1, 1, f"{ctx.vi.company.name} 기업가치평가 Dashboard",
               font=Font(bold=True, size=16, color=NAVY))
    write_cell(ws, 2, 1, f"분석일: {ctx.vi.company.analysis_date}  |  {method_desc}",
               font=NOTE_FONT)

    r = 4

    # ── 핵심 결론 ──
    primary_value, primary_label = _get_primary_value(ctx)
    write_cell(ws, r, 1, primary_label,
               font=Font(bold=True, size=14, color=NAVY))
    write_cell(ws, r, 2, f"{primary_value:,}{ctx.currency_sym}",
               font=Font(bold=True, size=18, color="27AE60"), fill=GREEN_FILL)

    # ── 시나리오 요약 (있을 때만) ──
    sc_header_row = None
    if ctx.sc_codes and ctx.result.scenarios:
        r += 2
        write_cell(ws, r, 1, "시나리오별 주당 가치", font=SECTION_FONT); r += 1
        sc_sum_headers = ["시나리오", "주당가치", "확률", "가중기여"]
        for c, h in enumerate(sc_sum_headers, 1):
            write_cell(ws, r, c, h)
        style_header_row(ws, r, 4)
        sc_header_row = r

        for sc_code in ctx.sc_codes:
            r += 1
            sc = ctx.vi.scenarios[sc_code]
            sr = ctx.result.scenarios[sc_code]
            write_cell(ws, r, 1, f"{sc_code}: {sc.name}")
            write_cell(ws, r, 2, sr.post_dlom, fmt=NUM_FMT,
                       fill=GREEN_FILL if sr.post_dlom > 0 else RED_FILL)
            write_cell(ws, r, 3, f"{sc.prob}%")
            write_cell(ws, r, 4, sr.weighted, fmt=NUM_FMT)

        r += 1
        write_cell(ws, r, 1, "합계", bold=True)
        write_cell(ws, r, 2, ctx.result.weighted_value, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)
        write_cell(ws, r, 3, "100%", bold=True)
        write_cell(ws, r, 4, ctx.result.weighted_value, fmt=NUM_FMT, bold=True)

    # ── 방법론별 밸류에이션 요약 ──
    r += 2
    ev_data_start = None
    ev_data_end = None

    if ctx.method == "ddm" and ctx.result.ddm:
        ddm = ctx.result.ddm
        write_cell(ws, r, 1, "DDM 밸류에이션 요약", font=SECTION_FONT); r += 1
        items = [("주당 배당금 (DPS)", f"{ddm.dps:,.0f}")]
        if ddm.buyback_per_share > 0:
            items.append(("자사주매입/주", f"{ddm.buyback_per_share:,.0f}"))
            items.append(("Total Payout/주", f"{ddm.total_payout:,.0f}"))
        items += [
            ("배당 성장률", f"{ddm.growth:.2f}%"),
            ("자기자본비용 (Ke)", f"{ddm.ke:.2f}%"),
            ("주당 내재가치 (DDM)", f"{ddm.equity_per_share:,}"),
        ]
        for label, val in items:
            write_cell(ws, r, 1, label)
            is_result = "내재가치" in label
            write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else BLUE_FILL, bold=is_result)
            r += 1

    elif ctx.method == "rim" and ctx.result.rim:
        rim = ctx.result.rim
        write_cell(ws, r, 1, "RIM 밸류에이션 요약", font=SECTION_FONT); r += 1
        items = [
            ("장부가치 (BV₀)", f"{rim.bv_current:,}"),
            ("자기자본비용 (Ke)", f"{rim.ke:.2f}%"),
            ("PV(잔여이익)", f"{rim.pv_ri_sum:,}"),
            ("PV(Terminal)", f"{rim.pv_terminal:,}"),
            ("자기자본가치", f"{rim.equity_value:,}"),
            ("주당 내재가치 (RIM)", f"{rim.per_share:,}"),
        ]
        for label, val in items:
            write_cell(ws, r, 1, label)
            is_result = "내재가치" in label
            write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else BLUE_FILL, bold=is_result)
            r += 1

    elif ctx.method == "nav" and ctx.result.nav:
        nav = ctx.result.nav
        write_cell(ws, r, 1, "NAV 밸류에이션 요약", font=SECTION_FONT); r += 1
        items = [
            ("총자산 (장부)", f"{nav.total_assets:,}"),
            ("(+) 재평가 조정", f"{nav.revaluation:,}"),
            ("(-) 총부채", f"{nav.total_liabilities:,}"),
            ("순자산가치 (NAV)", f"{nav.nav:,}"),
            ("주당 NAV", f"{nav.per_share:,}"),
        ]
        for label, val in items:
            write_cell(ws, r, 1, label)
            is_result = "주당" in label
            write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else BLUE_FILL, bold=is_result)
            r += 1

    elif ctx.method == "multiples" and ctx.result.multiples_primary:
        mp = ctx.result.multiples_primary
        write_cell(ws, r, 1, "Multiples 밸류에이션 요약", font=SECTION_FONT); r += 1
        items = [
            ("방법론", mp.primary_multiple_method),
            ("적용 멀티플", f"{mp.multiple:.1f}x"),
            ("Equity Value", f"{mp.equity_value:,}"),
            ("주당 가치", f"{mp.per_share:,}"),
        ]
        for label, val in items:
            write_cell(ws, r, 1, label)
            is_result = "주당" in label
            write_cell(ws, r, 2, val, fill=GREEN_FILL if is_result else BLUE_FILL, bold=is_result)
            r += 1

    elif ctx.method == "dcf_primary" and ctx.result.dcf:
        dcf = ctx.result.dcf
        write_cell(ws, r, 1, "DCF 밸류에이션 요약", font=SECTION_FONT); r += 1
        items = [
            ("PV(FCFF)", f"{dcf.pv_fcff_sum:,}"),
            ("PV(Terminal)", f"{dcf.pv_terminal:,}"),
            ("DCF EV", f"{dcf.ev_dcf:,}"),
            ("WACC", f"{dcf.wacc:.2f}%"),
            ("Terminal Growth", f"{dcf.terminal_growth:.1f}%"),
        ]
        for label, val in items:
            write_cell(ws, r, 1, label)
            is_ev = label == "DCF EV"
            write_cell(ws, r, 2, val, fill=GREEN_FILL if is_ev else BLUE_FILL, bold=is_ev)
            r += 1

    else:
        # SOTP (기본) — Mixed Method 대응
        has_mixed_dash = ctx.result.sotp and any(
            getattr(s, "method", "ev_ebitda") != "ev_ebitda"
            for s in ctx.result.sotp.values()
        )
        section_title = "SOTP 밸류에이션 구성 (Mixed)" if has_mixed_dash else f"Enterprise Value 구성 ({ctx.unit})"
        write_cell(ws, r, 1, section_title, font=SECTION_FONT); r += 1
        ev_data_start = r
        active_segs = []
        if ctx.result.sotp:
            active_segs = [c for c in ctx.seg_codes if ctx.result.sotp.get(c) and ctx.result.sotp[c].ev > 0]
            for code in active_segs:
                s = ctx.result.sotp[code]
                method = getattr(s, "method", "ev_ebitda")
                m_label = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E"}.get(method, "")
                write_cell(ws, r, 1, f"{ctx.seg_names[code]} ({m_label} {s.multiple:.1f}x)")
                write_cell(ws, r, 2, s.ev, fmt=NUM_FMT)
                r += 1
        ev_data_end = r - 1
        write_cell(ws, r, 1, "Total EV", bold=True)
        write_cell(ws, r, 2, ctx.result.total_ev, fmt=NUM_FMT, bold=True, fill=GREEN_FILL)

    # ── 핵심 재무지표 ──
    r += 2
    cons_by = ctx.cons[ctx.by]
    total_da = cons_by["dep"] + cons_by["amort"]
    ebitda = cons_by["op"] + total_da
    write_cell(ws, r, 1, f"핵심 재무지표 ({ctx.by})", font=SECTION_FONT); r += 1

    # Mixed SOTP: 유효 순차입금 표시
    _is_mixed_dash = bool(ctx.vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in ctx.vi.segments.values()
    )
    kpis = [
        ("매출액", cons_by["revenue"]),
        ("영업이익", cons_by["op"]),
        ("EBITDA", ebitda),
    ]
    if _is_mixed_dash:
        fin_debt_d = sum(
            ctx.vi.segment_net_debt[c]
            for c, info in ctx.vi.segments.items()
            if info.get("method") in ("pbv", "pe") and c in ctx.vi.segment_net_debt
        )
        eff_nd_d = ctx.vi.net_debt - fin_debt_d
        kpis.append(("순차입금 (연결)", ctx.vi.net_debt))
        kpis.append(("유효 순차입금 (제조)", eff_nd_d))
    else:
        kpis.append(("순차입금", ctx.vi.net_debt))
    kpis.append(("부채비율", f"{cons_by['de_ratio']:.1f}%"))
    if ctx.result.dcf:
        kpis.append(("DCF EV", ctx.result.dcf.ev_dcf))
    if ebitda > 0 and ctx.result.total_ev > 0:
        kpis.append(("EV/EBITDA (implied)", f"{ctx.result.total_ev / ebitda:.1f}x"))

    for label, val in kpis:
        write_cell(ws, r, 1, label)
        if isinstance(val, str):
            write_cell(ws, r, 2, val)
        else:
            write_cell(ws, r, 2, val, fmt=NUM_FMT)
        r += 1

    # ── 교차검증 ──
    cv_header_row = None
    if ctx.result.cross_validations:
        r += 1
        write_cell(ws, r, 1, "멀티플 교차검증 (Cross-Validation)", font=SECTION_FONT); r += 1
        cv_headers = ["방법론", "지표값", "배수", "EV", "Equity Value", f"주당 가치 ({ctx.currency_sym})"]
        cv_widths = [20, 18, 10, 18, 18, 18]
        for c, h in enumerate(cv_headers, 1):
            write_cell(ws, r, c, h)
            ws.column_dimensions[get_column_letter(c)].width = cv_widths[c - 1]
        style_header_row(ws, r, len(cv_headers))
        cv_header_row = r

        for cv in ctx.result.cross_validations:
            r += 1
            write_cell(ws, r, 1, cv.method)
            write_cell(ws, r, 2, cv.metric_value, fmt=NUM_FMT)
            write_cell(ws, r, 3, f"{cv.multiple:.1f}x" if cv.multiple > 0 else "-")
            write_cell(ws, r, 4, cv.enterprise_value, fmt=NUM_FMT)
            write_cell(ws, r, 5, cv.equity_value, fmt=NUM_FMT,
                       fill=GREEN_FILL if cv.equity_value > 0 else RED_FILL)
            write_cell(ws, r, 6, cv.per_share, fmt=NUM_FMT,
                       fill=GREEN_FILL if cv.per_share > 0 else RED_FILL)

    # ── 시장가격 비교 ──
    if ctx.result.market_comparison and ctx.result.market_comparison.market_price > 0:
        mc = ctx.result.market_comparison
        r += 2
        write_cell(ws, r, 1, "시장가격 비교", font=SECTION_FONT); r += 1
        write_cell(ws, r, 1, "내재가치 (주당)")
        write_cell(ws, r, 2, mc.intrinsic_value, fmt=NUM_FMT); r += 1
        write_cell(ws, r, 1, "현재 시장가")
        write_cell(ws, r, 2, mc.market_price, fmt=NUM_FMT); r += 1
        write_cell(ws, r, 1, "괴리율")
        gap_fill = RED_FILL if abs(mc.gap_ratio) > 0.5 else GREEN_FILL
        write_cell(ws, r, 2, f"{mc.gap_ratio:.1%}", fill=gap_fill)
        if mc.flag:
            r += 1
            write_cell(ws, r, 1, mc.flag, font=Font(bold=True, color="E74C3C"))

    # ── Monte Carlo ──
    if ctx.result.monte_carlo:
        mc = ctx.result.monte_carlo
        r += 2
        write_cell(ws, r, 1, f"Monte Carlo 시뮬레이션 ({mc.n_sims:,}회)", font=SECTION_FONT); r += 1
        mc_items = [
            ("Mean (평균)", mc.mean), ("Median (중위수)", mc.median),
            ("Std (표준편차)", mc.std),
            ("5th Percentile", mc.p5), ("25th Percentile", mc.p25),
            ("75th Percentile", mc.p75), ("95th Percentile", mc.p95),
            ("Min", mc.min_val), ("Max", mc.max_val),
        ]
        for label, val in mc_items:
            write_cell(ws, r, 1, label)
            fill = GREEN_FILL if label.startswith("Med") else None
            write_cell(ws, r, 2, val, fmt=NUM_FMT, fill=fill)
            write_cell(ws, r, 3, ctx.currency_sym)
            r += 1

        # 히스토그램
        if mc.histogram_bins:
            r += 1
            write_cell(ws, r, 1, "주당가치 분포 (히스토그램)", font=SECTION_FONT); r += 1
            write_cell(ws, r, 1, f"구간 ({ctx.currency_sym})")
            write_cell(ws, r, 2, "빈도")
            style_header_row(ws, r, 2)
            hist_start = r + 1
            for bin_val, cnt in zip(mc.histogram_bins, mc.histogram_counts):
                r += 1
                write_cell(ws, r, 1, bin_val, fmt=NUM_FMT)
                write_cell(ws, r, 2, cnt, fmt=NUM_FMT)
            hist_end = r

            hist_chart = BarChart()
            hist_chart.type = "col"
            hist_chart.style = 10
            hist_chart.title = "Monte Carlo — 주당가치 분포"
            hist_chart.y_axis.title = "빈도"
            hist_chart.x_axis.title = f"주당가치 ({ctx.currency_sym})"

            cats_h = Reference(ws, min_col=1, min_row=hist_start, max_row=hist_end)
            vals_h = Reference(ws, min_col=2, min_row=hist_start, max_row=hist_end)
            hist_chart.add_data(vals_h, titles_from_data=False)
            hist_chart.set_categories(cats_h)
            hist_chart.width = 22
            hist_chart.height = 13
            hist_chart.legend = None
            hist_chart.gapWidth = 10
            s_h = hist_chart.series[0]
            s_h.graphicalProperties.solidFill = "2E86C1"

            r += 2
            ws.add_chart(hist_chart, f"A{r}")
            r += 16

    # ── Charts ──

    # Chart 1: 시나리오별 주당 가치 (시나리오 있을 때만)
    if sc_header_row and ctx.sc_codes:
        chart1 = BarChart()
        chart1.type = "col"
        chart1.style = 10
        chart1.title = f"시나리오별 주당 가치 ({ctx.currency_sym})"
        chart1.y_axis.title = ctx.currency_sym

        cats1 = Reference(ws, min_col=1, min_row=sc_header_row + 1, max_row=sc_header_row + len(ctx.sc_codes))
        vals1 = Reference(ws, min_col=2, min_row=sc_header_row, max_row=sc_header_row + len(ctx.sc_codes))
        chart1.add_data(vals1, titles_from_data=True)
        chart1.set_categories(cats1)
        chart1.shape = 4
        chart1.width = 18
        chart1.height = 12

        sc_colors = ["1B2A4A", "27AE60", "E74C3C", "F39C12", "8E44AD"]
        s1 = chart1.series[0]
        s1.graphicalProperties.solidFill = sc_colors[0]
        for idx in range(1, len(ctx.sc_codes)):
            pt = DataPoint(idx=idx)
            pt.graphicalProperties.solidFill = sc_colors[idx % len(sc_colors)]
            s1.data_points.append(pt)

        chart1.legend = None
        s1.dLbls = DataLabelList()
        s1.dLbls.showVal = True
        s1.dLbls.showSerName = False
        s1.dLbls.numFmt = '#,##0'

        r += 2
        ws.add_chart(chart1, f"A{r}")

    # Chart 2: EV 구성 (SOTP only)
    if ev_data_start is not None and ev_data_end is not None and ev_data_end >= ev_data_start:
        chart2 = BarChart()
        chart2.type = "col"
        chart2.style = 10
        chart2.title = f"사업부별 Enterprise Value ({ctx.unit})"
        chart2.y_axis.title = ctx.unit

        cats2 = Reference(ws, min_col=1, min_row=ev_data_start, max_row=ev_data_end)
        vals2 = Reference(ws, min_col=2, min_row=ev_data_start, max_row=ev_data_end)
        chart2.add_data(vals2, titles_from_data=False)
        chart2.set_categories(cats2)
        chart2.shape = 4
        chart2.width = 18
        chart2.height = 12
        chart2.legend = None

        seg_colors = ["1B2A4A", "2E86C1", "27AE60", "F39C12", "8E44AD"]
        s2 = chart2.series[0]
        for idx, color in enumerate(seg_colors[:ev_data_end - ev_data_start + 1]):
            pt = DataPoint(idx=idx)
            pt.graphicalProperties.solidFill = color
            s2.data_points.append(pt)

        s2.dLbls = DataLabelList()
        s2.dLbls.showVal = True
        s2.dLbls.showSerName = False
        s2.dLbls.numFmt = '#,##0'

        r += 16
        ws.add_chart(chart2, f"A{r}")

    # ── Football Field ──
    r += 16
    _write_football_field(ws, r, ctx)


def _get_primary_value(ctx: _Ctx) -> tuple[int, str]:
    """방법론별 핵심 결과값."""
    if ctx.result.weighted_value > 0 and ctx.result.scenarios:
        return ctx.result.weighted_value, "확률가중 적정 주당 가치"

    if ctx.method == "ddm" and ctx.result.ddm:
        return ctx.result.ddm.equity_per_share, "DDM 적정 주당 가치"
    elif ctx.method == "rim" and ctx.result.rim:
        return ctx.result.rim.per_share, "RIM 적정 주당 가치"
    elif ctx.method == "nav" and ctx.result.nav:
        return ctx.result.nav.per_share, "NAV 적정 주당 가치"
    elif ctx.method == "multiples" and ctx.result.multiples_primary:
        return ctx.result.multiples_primary.per_share, "Multiples 적정 주당 가치"
    elif ctx.method == "dcf_primary" and ctx.result.dcf:
        return ctx.result.dcf.ev_dcf, f"DCF Enterprise Value ({ctx.unit})"
    else:
        return ctx.result.total_ev, f"Enterprise Value ({ctx.unit})"


def _write_football_field(ws, r: int, ctx: _Ctx):
    """Football Field 차트 (교차검증/시나리오 기반)."""
    write_cell(ws, r, 1, "Football Field — 밸류에이션 범위", font=SECTION_FONT); r += 1
    # Football Field 데이터는 H-L열(col 8~12)에 배치
    FF_COL_START = 8
    ff_headers = ["방법론", "하단", "주당가치", "상단", "범위"]
    for c, h in enumerate(ff_headers):
        write_cell(ws, r, FF_COL_START + c, h)
    # 헤더 스타일 (H~L열)
    for col_idx in range(FF_COL_START, FF_COL_START + len(ff_headers)):
        cell = ws.cell(row=r, column=col_idx)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = GRAY_FILL
    ff_header_row = r

    ff_colors_list = []
    ff_color_palette = ["1B2A4A", "2E86C1", "27AE60", "F39C12", "E74C3C", "8E44AD", "17A589"]

    # Football Field 데이터는 H-L열(col 8~12)에 배치 — A-F 교차검증 열과 충돌 방지
    FF_COL_LABEL = 8   # H: 방법론
    FF_COL_LO = 9      # I: 하단
    FF_COL_VAL = 10     # J: 주당가치
    FF_COL_HI = 11      # K: 상단
    FF_COL_RANGE = 12   # L: 범위 (차트용, 숨김)

    ff_entries = []
    if ctx.result.cross_validations:
        for cv in ctx.result.cross_validations:
            ff_entries.append((cv.method, cv.per_share))
    elif ctx.result.scenarios:
        for sc_code in ctx.sc_codes:
            sr = ctx.result.scenarios[sc_code]
            sc = ctx.vi.scenarios[sc_code]
            ff_entries.append((f"{sc_code}: {sc.name}", sr.post_dlom))
    else:
        primary_val, primary_label = _get_primary_value(ctx)
        ff_entries.append((primary_label, primary_val))

    for i, (label, val) in enumerate(reversed(ff_entries)):
        lo = max(round(val * 0.8), 0)
        hi = round(val * 1.2) if val > 0 else 0

        r += 1
        write_cell(ws, r, FF_COL_LABEL, label)
        write_cell(ws, r, FF_COL_LO, lo, fmt=NUM_FMT)
        write_cell(ws, r, FF_COL_VAL, val, fmt=NUM_FMT, fill=BLUE_FILL)
        write_cell(ws, r, FF_COL_HI, hi, fmt=NUM_FMT)
        write_cell(ws, r, FF_COL_RANGE, max(hi - lo, 0), fmt=NUM_FMT)
        ff_colors_list.append(ff_color_palette[i % len(ff_color_palette)])

    ff_data_end = r
    ws.column_dimensions[get_column_letter(FF_COL_LABEL)].width = 24
    ws.column_dimensions[get_column_letter(FF_COL_LO)].width = 14
    ws.column_dimensions[get_column_letter(FF_COL_VAL)].width = 14
    ws.column_dimensions[get_column_letter(FF_COL_HI)].width = 14
    ws.column_dimensions[get_column_letter(FF_COL_RANGE)].width = 2  # 숨김 (차트 데이터용)

    if not ff_entries:
        return

    # Stacked bar chart
    chart3 = BarChart()
    chart3.type = "bar"
    chart3.style = 10
    chart3.title = "Football Field — 밸류에이션 범위"
    chart3.x_axis.numFmt = '#,##0'

    cats3 = Reference(ws, min_col=FF_COL_LABEL, min_row=ff_header_row + 1, max_row=ff_data_end)
    vals_lo = Reference(ws, min_col=FF_COL_LO, min_row=ff_header_row + 1, max_row=ff_data_end)
    vals_range = Reference(ws, min_col=FF_COL_RANGE, min_row=ff_header_row + 1, max_row=ff_data_end)

    chart3.add_data(vals_lo, titles_from_data=False)
    chart3.add_data(vals_range, titles_from_data=False)
    chart3.set_categories(cats3)
    chart3.grouping = "stacked"
    chart3.width = 20
    chart3.height = 10
    chart3.gapWidth = 80

    s3_lo = chart3.series[0]
    s3_lo.graphicalProperties.solidFill = "E8EAED"
    s3_lo.graphicalProperties.line.solidFill = "D5D8DC"

    s3_hi = chart3.series[1]
    for ci, color in enumerate(ff_colors_list):
        pt = DataPoint(idx=ci)
        pt.graphicalProperties.solidFill = color
        s3_hi.data_points.append(pt)

    s3_hi.dLbls = DataLabelList()
    s3_hi.dLbls.showVal = True
    s3_hi.dLbls.showSerName = False
    s3_hi.dLbls.showCatName = False
    s3_hi.dLbls.numFmt = '#,##0'
    chart3.legend = None

    r += 2
    ws.add_chart(chart3, f"A{r}")
