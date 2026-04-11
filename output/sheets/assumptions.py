"""Sheet 1: Assumptions — WACC/Ke params, method-specific assumptions, scenarios."""

from ._ctx import Ctx
from ..excel_styles import (
    NAVY, BLUE_FILL, YELLOW_FILL, GREEN_FILL, RED_FILL,
    HEADER_FONT, SECTION_FONT, TITLE_FONT, NOTE_FONT,
    NUM_FMT, PCT_FMT,
    style_header_row, write_cell,
)


def sheet_assumptions(ctx: Ctx):
    ws = ctx.wb.active or ctx.wb.create_sheet("Assumptions")
    ws.title = "Assumptions"
    ws.sheet_properties.tabColor = NAVY
    ws.column_dimensions['A'].width = 28
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 40

    write_cell(ws, 1, 1, f"{ctx.vi.company.name} 기업가치평가 — 핵심 가정값", font=TITLE_FONT)
    # Show combined methodology when DCF cross-validation exists
    method_label = ctx.method.upper()
    if ctx.method == "sotp" and ctx.result.dcf is not None:
        method_label = "SOTP + DCF"
    write_cell(ws, 2, 1, f"분석일: {ctx.vi.company.analysis_date}  |  방법론: {method_label}",
               font=NOTE_FONT)

    r = 4

    # ── WACC / Ke (common) ──
    w = ctx.result.wacc
    wp = ctx.vi.wacc_params

    if ctx.method in ("ddm", "rim"):
        # DDM/RIM: only Ke is key
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
        # SOTP/DCF/NAV/Multiples: full WACC
        write_cell(ws, r, 1, "WACC 구성요소", font=SECTION_FONT); r += 1
        # Market-specific descriptions
        mkt = ctx.vi.company.market
        rf_note = "한국 국고채 10Y" if mkt == "KR" else "US Treasury 10Y"
        erp_note = "한국 시장 6~8% 중간값" if mkt == "KR" else "US ERP (Damodaran)"
        # Peer description from profile peers
        peer_segments = set()
        for p in ctx.vi.peers:
            peer_segments.add(p.segment_code)
        bu_note = f"{'+'.join(sorted(peer_segments))} Peer 평균" if peer_segments else "Peer 평균"
        wacc_params = [
            ("무위험이자율 (Rf)", f"{wp.rf:.2f}%", rf_note),
            ("주식위험프리미엄 (ERP)", f"{wp.erp:.2f}%", erp_note),
            ("Unlevered Beta (βu)", f"{wp.bu:.3f}", bu_note),
            ("D/E Ratio", f"{wp.de:.1f}%", f"{ctx.by}년말 실적"),
            ("법인세율", f"{wp.tax:.1f}%", "한국 실효세율" if mkt == "KR" else "실효세율"),
            ("Levered Beta (βL)", f"{w.bl:.3f}", "βu × [1+(1-t)×D/E]"),
            ("자기자본비용 (Ke)", f"{w.ke:.2f}%",
             "Rf + βL × ERP" + (f" + SP {wp.size_premium:.1f}%" if wp.size_premium > 0 else "")),
            ("세전 타인자본비용 (Kd)", f"{wp.kd_pre:.2f}%", "신용등급 기반"),
            ("세후 타인자본비용", f"{w.kd_at:.2f}%", "Kd × (1-t)"),
            ("자기자본 비중", f"{wp.eq_w:.1f}%", f"{ctx.by}년말"),
            ("WACC", f"{w.wacc:.2f}%", "Ke×E% + Kd(세후)×D%"),
        ]
        # Insert size premium row after Ke if applicable
        if wp.size_premium > 0:
            ke_idx = next(i for i, p in enumerate(wacc_params) if p[0].startswith("자기자본비용"))
            wacc_params.insert(ke_idx + 1, (
                "  비상장/규모 프리미엄 (SP)", f"{wp.size_premium:.2f}%", "비상장 할인 반영"
            ))
        for label, val, note in wacc_params:
            write_cell(ws, r, 1, label)
            write_cell(ws, r, 2, val, fill=BLUE_FILL)
            write_cell(ws, r, 3, note)
            r += 1

    # ── Method-specific additional assumptions ──
    r += 1

    if ctx.method == "sotp":
        # Per-segment multiples (Mixed SOTP support)
        write_cell(ws, r, 1, "부문별 적용 멀티플", font=SECTION_FONT); r += 1
        for code in ctx.seg_codes:
            seg_info = ctx.vi.segments.get(code, {})
            method = seg_info.get("method", "ev_ebitda")
            method_label = {"ev_ebitda": "EV/EBITDA", "pbv": "P/BV", "pe": "P/E", "ev_revenue": "EV/Revenue"}.get(method, method)
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

    # ── DCF cross-validation assumptions (show when DCF result exists) ──
    if ctx.method == "sotp" and ctx.result.dcf is not None:
        dcf_p = ctx.vi.dcf_params
        write_cell(ws, r, 1, "DCF 교차검증 가정", font=SECTION_FONT); r += 1
        dcf_items = [
            ("영구성장률 (TGR)", f"{dcf_p.terminal_growth:.1f}%", "Gordon Growth"),
            ("Capex / D&A", f"{dcf_p.capex_to_da:.2f}x", "유지보수 투자"),
            ("ΔNWC / ΔRevenue", f"{dcf_p.nwc_to_rev_delta:.1%}", "운전자본 변동"),
        ]
        if dcf_p.terminal_ev_ebitda is not None:
            dcf_items.append(("Exit Multiple (EV/EBITDA)", f"{dcf_p.terminal_ev_ebitda:.1f}x",
                              "터미널밸류 교차검증"))
        if dcf_p.ebitda_growth_rates:
            rates_str = " → ".join(f"{g:.0%}" for g in dcf_p.ebitda_growth_rates)
            dcf_items.append(("EBITDA 성장률 경로", rates_str, "5개년 fade"))
        for label, val, note in dcf_items:
            write_cell(ws, r, 1, label)
            write_cell(ws, r, 2, val, fill=GREEN_FILL)
            write_cell(ws, r, 3, note)
            r += 1
        r += 1

    # ── Scenario assumption summary (only when available) ──
    is_listed = ctx.vi.company.legal_status == "상장"
    has_dlom = any(ctx.vi.scenarios[c].dlom > 0 for c in ctx.sc_codes) if ctx.sc_codes else False

    if ctx.sc_codes:
        r += 1
        section_title = "시나리오 확률" + (" / DLOM" if not is_listed and has_dlom else "")
        write_cell(ws, r, 1, section_title, font=SECTION_FONT); r += 1
        write_cell(ws, r, 1, "항목")
        for i, sc_code in enumerate(ctx.sc_codes, 2):
            write_cell(ws, r, i, f"{sc_code}: {ctx.vi.scenarios[sc_code].name}")
        style_header_row(ws, r, 1 + len(ctx.sc_codes)); r += 1

        # Always display probability
        write_cell(ws, r, 1, "확률")
        for i, sc_code in enumerate(ctx.sc_codes, 2):
            write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].prob}%", fill=BLUE_FILL)
        r += 1

        # DLOM -- only for unlisted companies
        if not is_listed:
            write_cell(ws, r, 1, "DLOM")
            for i, sc_code in enumerate(ctx.sc_codes, 2):
                write_cell(ws, r, i, f"{ctx.vi.scenarios[sc_code].dlom}%", fill=BLUE_FILL)
            r += 1

        # Method-specific driver assumptions
        _write_assumption_drivers(ws, r, ctx)
        r += 1  # Skip at least 1 row even if no drivers

        # IRR (private companies with CPS only)
        if any(ctx.vi.scenarios[c].irr is not None for c in ctx.sc_codes):
            write_cell(ws, r, 1, "FI IRR")
            for i, sc_code in enumerate(ctx.sc_codes, 2):
                irr = ctx.vi.scenarios[sc_code].irr
                write_cell(ws, r, i, f"{irr}%" if irr else "-", fill=BLUE_FILL)
            r += 1

    # ── Financial Instruments (CPS/RCPS) ──
    has_cps = ctx.vi.cps_principal > 0
    has_rcps = ctx.vi.rcps_principal > 0
    if has_cps or has_rcps:
        r += 1
        write_cell(ws, r, 1, "금융상품 (CPS/RCPS)", font=SECTION_FONT); r += 1
        if has_cps:
            write_cell(ws, r, 1, f"CPS 원금 ({ctx.unit})")
            write_cell(ws, r, 2, ctx.vi.cps_principal, fmt=NUM_FMT, fill=BLUE_FILL)
            write_cell(ws, r, 3, "전환우선주"); r += 1
            write_cell(ws, r, 1, "CPS 만기 (년)")
            write_cell(ws, r, 2, f"{ctx.vi.cps_years}년", fill=BLUE_FILL); r += 1
            write_cell(ws, r, 1, "CPS 배당률")
            rate = ctx.vi.cps_dividend_rate
            write_cell(ws, r, 2, f"{rate:.1f}%" if rate > 0 else "무배당 (zero-coupon)",
                       fill=BLUE_FILL); r += 1
        if has_rcps:
            write_cell(ws, r, 1, f"RCPS 원금 ({ctx.unit})")
            write_cell(ws, r, 2, ctx.vi.rcps_principal, fmt=NUM_FMT, fill=YELLOW_FILL)
            write_cell(ws, r, 3, "상환전환우선주"); r += 1
            write_cell(ws, r, 1, "RCPS 만기 (년)")
            write_cell(ws, r, 2, f"{ctx.vi.rcps_years}년", fill=YELLOW_FILL); r += 1
            write_cell(ws, r, 1, "RCPS 배당률")
            write_cell(ws, r, 2, f"{ctx.vi.rcps_dividend_rate:.1f}%", fill=YELLOW_FILL)
            write_cell(ws, r, 3, "배당 지급 중 → 상환액 ≠ 단순 복리"); r += 1

    # ── Other parameters ──
    r += 1
    write_cell(ws, r, 1, "기타 파라미터", font=SECTION_FONT); r += 1
    # Mixed SOTP: display effective net debt
    _is_mixed = bool(ctx.vi.segment_net_debt) and any(
        info.get("method") in ("pbv", "pe") for info in ctx.vi.segments.values()
    )
    write_cell(ws, r, 1, f"순차입금 ({ctx.unit})")
    write_cell(ws, r, 2, ctx.vi.net_debt, fmt=NUM_FMT, fill=BLUE_FILL)
    r += 1
    if ctx.vi.eco_frontier > 0:
        write_cell(ws, r, 1, f"에코프론티어 파생상품부채 ({ctx.unit})")
        write_cell(ws, r, 2, ctx.vi.eco_frontier, fmt=NUM_FMT, fill=BLUE_FILL)
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


def _write_assumption_drivers(ws, r: int, ctx: Ctx):
    """Display per-scenario key driver assumptions on the Assumptions sheet."""
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
