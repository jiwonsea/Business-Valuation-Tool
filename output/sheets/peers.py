"""Sheet 4: Peer Comparison — comparable company analysis."""

from openpyxl.utils import get_column_letter

from ._ctx import Ctx
from ..excel_styles import (
    BLUE_FILL,
    YELLOW_FILL,
    GREEN_FILL,
    RED_FILL,
    NOTE_FONT,
    SECTION_FONT,
    TITLE_FONT,
    MULT_FMT,
    NUM_FMT,
    style_header_row,
    write_cell,
)


def sheet_peers(ctx: Ctx):
    if not ctx.vi.peers and not ctx.result.peer_stats:
        return

    ws = ctx.wb.create_sheet("Peer Comparison")
    ws.sheet_properties.tabColor = "17A589"
    write_cell(
        ws, 1, 1, "유사기업 비교분석 (Comparable Company Analysis)", font=TITLE_FONT
    )

    r = 3
    has_extra = any(p.ticker for p in ctx.vi.peers)
    if has_extra:
        peer_headers = [
            "기업명",
            "Ticker",
            "매핑 부문",
            "EV/EBITDA",
            "EV/Sales",
            "P/E (TTM)",
            "P/BV",
            "Beta",
            "출처",
            "비고",
        ]
        col_widths = [20, 10, 16, 12, 12, 12, 10, 8, 8, 40]
    else:
        peer_headers = [
            "기업명",
            "매핑 부문",
            "EV/EBITDA",
            "EV/Sales",
            "P/E (TTM)",
            "P/BV",
            "비고",
        ]
        col_widths = [20, 18, 12, 12, 12, 10, 50]
    for c, h in enumerate(peer_headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = col_widths[c - 1]
    style_header_row(ws, r, len(peer_headers))

    for p in ctx.vi.peers:
        r += 1
        c = 1
        write_cell(ws, r, c, p.name)
        c += 1
        if has_extra:
            write_cell(ws, r, c, p.ticker or "-")
            c += 1
        write_cell(ws, r, c, ctx.seg_names.get(p.segment_code, p.segment_code))
        c += 1
        write_cell(
            ws,
            r,
            c,
            p.ev_ebitda if p.ev_ebitda is not None else "-",
            fmt=MULT_FMT if p.ev_ebitda is not None else None,
            fill=YELLOW_FILL if p.ev_ebitda is not None else None,
        )
        c += 1
        write_cell(
            ws,
            r,
            c,
            p.ev_revenue if p.ev_revenue is not None else "-",
            fmt="0.000x" if p.ev_revenue is not None else None,
            fill=YELLOW_FILL if p.ev_revenue is not None else None,
        )
        c += 1
        write_cell(
            ws,
            r,
            c,
            p.trailing_pe if p.trailing_pe is not None else "-",
            fmt=MULT_FMT if p.trailing_pe is not None else None,
        )
        c += 1
        write_cell(
            ws,
            r,
            c,
            p.pbv if p.pbv is not None else "-",
            fmt="0.000x" if p.pbv is not None else None,
        )
        c += 1
        if has_extra:
            write_cell(ws, r, c, f"{p.beta:.2f}" if p.beta else "-")
            c += 1
            write_cell(ws, r, c, p.source)
            c += 1
        write_cell(ws, r, c, p.notes)

    # Per-segment multiple statistics
    if ctx.result.peer_stats:
        r += 2
        write_cell(ws, r, 1, "부문별 Method-aligned 멀티플 통계", font=SECTION_FONT)
        r += 1
        stat_headers = [
            "부문",
            "평가방법",
            "Peer 수",
            "Min",
            "Q1",
            "Median",
            "Mean",
            "Q3",
            "Max",
            "적용 멀티플",
            "중앙값 대비",
            "밴드 위치",
            "선정 근거",
        ]
        for c, h in enumerate(stat_headers, 1):
            write_cell(ws, r, c, h)
            ws.column_dimensions[get_column_letter(c)].width = max(
                ws.column_dimensions[get_column_letter(c)].width or 0,
                [18, 14, 8, 8, 8, 8, 8, 8, 8, 12, 12, 16, 70][c - 1],
            )
        style_header_row(ws, r, len(stat_headers))

        for ps in ctx.result.peer_stats:
            r += 1
            write_cell(ws, r, 1, ps.segment_name)
            write_cell(ws, r, 2, ps.multiple_label)
            write_cell(ws, r, 3, ps.count)
            stat_fmt = MULT_FMT if ps.multiple_method == "ev_ebitda" else "0.000x"
            for col, value in enumerate(
                (
                    ps.multiple_min,
                    ps.multiple_q1,
                    ps.multiple_median,
                    ps.multiple_mean,
                    ps.multiple_q3,
                    ps.multiple_max,
                ),
                4,
            ):
                write_cell(
                    ws,
                    r,
                    col,
                    value if value is not None else "N/A",
                    fmt=stat_fmt if value is not None else None,
                    fill=GREEN_FILL if col == 6 and value is not None else None,
                )
            applied = ps.applied_multiple
            fill = GREEN_FILL if ps.count and abs(ps.premium_pct) <= 15 else YELLOW_FILL
            write_cell(ws, r, 10, applied, fmt=stat_fmt, fill=fill, bold=True)
            # Provenance: how far from median, where in the band, and why
            prem = getattr(ps, "premium_pct", 0.0)
            write_cell(
                ws,
                r,
                11,
                prem / 100 if ps.count else "N/A",
                fmt="+0.0%;-0.0%;0.0%" if ps.count else None,
                fill=GREEN_FILL if abs(prem) < 2 else YELLOW_FILL,
            )
            pos = getattr(ps, "band_position", "")
            write_cell(
                ws,
                r,
                12,
                pos,
                fill=RED_FILL if pos in ("레인지 밖", "Q3 초과", "Q1 미만") else None,
            )
            rationale = ps.warning or getattr(ps, "rationale", "")
            write_cell(ws, r, 13, rationale)

        r += 2
        r = _implied_multiple_check(ws, r, ctx)


def _implied_multiple_check(ws, r: int, ctx: Ctx) -> int:
    """Back-solve EV/EBITDA from price and from the analyst target, and put those
    next to the multiple the model actually applied.

    Three numbers, one question: is our applied multiple defensible against what
    the market and the sell-side are already paying?

    IMPORTANT: a target-price-implied multiple is circular as *justification* --
    the analyst's target already embeds the analyst's multiple. It is a sanity
    check on the applied multiple, never the source of it. That caveat is printed
    on the sheet.
    """
    methods = {
        info.get("method", "ev_ebitda") for info in ctx.vi.segments.values()
    }
    if len(methods) > 1:
        write_cell(ws, r, 1, "적용 멀티플 교차검증 — 역산", font=SECTION_FONT)
        r += 1
        write_cell(
            ws,
            r,
            1,
            "⚠ 혼합 SOTP는 회사 전체의 단일 내재 배수가 정의되지 않아 역산 패널을 생략합니다.",
            font=NOTE_FONT,
        )
        return r + 1

    relative = ctx.result.relative_valuation
    if relative is None or not relative.basis_aligned:
        write_cell(ws, r, 1, "적용 멀티플 교차검증 — 역산", font=SECTION_FONT)
        r += 1
        reason = (
            relative.basis_note
            if relative is not None
            else "상대가치 진단이 비활성화되었거나 기준 데이터가 부족함"
        )
        write_cell(ws, r, 1, f"⚠ 역산 패널 생략: {reason}", font=NOTE_FONT)
        return r + 1

    cons = ctx.cons.get(ctx.by, {})
    ebitda = cons.get("op", 0) + cons.get("dep", 0) + cons.get("amort", 0)
    if ebitda <= 0:
        return r

    co = ctx.vi.company
    um = co.unit_multiplier
    shares = ctx.vi.valuation_shares
    nd = ctx.vi.net_debt

    write_cell(ws, r, 1, "적용 멀티플 교차검증 — 역산 (Implied Multiple)", font=SECTION_FONT)
    r += 1
    write_cell(
        ws,
        r,
        1,
        f"기준: {ctx.by}년 EBITDA {ebitda:,}{ctx.unit} (= 영업이익 + 감가상각비 + 무형자산상각비), "
        f"순차입금 {nd:,}{ctx.unit}, 적용 주식수 {shares:,}주",
        font=NOTE_FONT,
    )
    r += 2

    headers = ["구분", "기준 주가/가치", "내재 EV", "내재 EV/EBITDA", "산식 / 해석"]
    widths = [26, 18, 18, 18, 70]
    for c, h in enumerate(headers, 1):
        write_cell(ws, r, c, h)
        ws.column_dimensions[get_column_letter(c)].width = max(
            ws.column_dimensions[get_column_letter(c)].width or 0, widths[c - 1]
        )
    style_header_row(ws, r, len(headers))

    def _implied_from_price(px: float) -> tuple[int, float]:
        ev = round(px * shares / um) + nd
        return ev, ev / ebitda

    model_mult = None
    equity_based = False

    # (a) what the model itself applied, blended across segments
    if ctx.result.sotp:
        tot_ev = 0
        tot_ebitda = 0
        for s in ctx.result.sotp.values():
            if getattr(s, "method", "ev_ebitda") == "ev_ebitda":
                tot_ev += s.ev
                tot_ebitda += s.ebitda
            else:
                equity_based = True
        if tot_ebitda > 0:
            model_mult = tot_ev / tot_ebitda
            r += 1
            write_cell(ws, r, 1, "모델 적용 (SOTP 가중평균)", bold=True)
            write_cell(ws, r, 2, "-")
            write_cell(ws, r, 3, tot_ev, fmt=NUM_FMT)
            write_cell(ws, r, 4, model_mult, fmt=MULT_FMT, fill=BLUE_FILL, bold=True)
            note = f"Σ부문EV {tot_ev:,} ÷ Σ부문EBITDA {tot_ebitda:,} — EBITDA 배수 부문만 집계"
            if equity_based:
                note += " (P/BV·P/E 부문은 지분가치 기반이라 제외)"
            write_cell(ws, r, 5, note)
    elif ctx.result.total_ev > 0:
        model_mult = ctx.result.total_ev / ebitda
        r += 1
        write_cell(ws, r, 1, "모델 적용 (내재)", bold=True)
        write_cell(ws, r, 2, "-")
        write_cell(ws, r, 3, ctx.result.total_ev, fmt=NUM_FMT)
        write_cell(ws, r, 4, model_mult, fmt=MULT_FMT, fill=BLUE_FILL, bold=True)
        write_cell(ws, r, 5, f"모델 EV {ctx.result.total_ev:,} ÷ EBITDA {ebitda:,}")

    # (b) what the market is paying right now
    mc = ctx.result.market_comparison
    price = (mc.market_price if mc else None) or ctx.vi.market_price
    market_mult = None
    if price and shares > 0:
        ev, market_mult = _implied_from_price(price)
        r += 1
        write_cell(ws, r, 1, "현재 주가 역산")
        write_cell(ws, r, 2, price, fmt=NUM_FMT)
        write_cell(ws, r, 3, ev, fmt=NUM_FMT)
        write_cell(ws, r, 4, market_mult, fmt=MULT_FMT, fill=YELLOW_FILL)
        write_cell(
            ws,
            r,
            5,
            "시가총액(주가×적용 주식수) + 순차입금 = EV → ÷EBITDA. 시장이 지금 지불 중인 배수",
        )

    # (c) what the sell-side target implies
    ms = ctx.vi.market_signals
    target = ms.target_mean if ms else None
    target_mult = None
    if target and shares > 0:
        ev, target_mult = _implied_from_price(target)
        r += 1
        n = (ms.analyst_count if ms else None) or "?"
        write_cell(ws, r, 1, f"컨센서스 목표주가 역산 (N={n})")
        write_cell(ws, r, 2, target, fmt=NUM_FMT)
        write_cell(ws, r, 3, ev, fmt=NUM_FMT)
        write_cell(ws, r, 4, target_mult, fmt=MULT_FMT, fill=YELLOW_FILL)
        write_cell(
            ws,
            r,
            5,
            "목표주가 × 적용 주식수 + 순차입금 = 목표 EV → ÷EBITDA. 셀사이드가 암묵적으로 쓰는 배수",
        )

    # Gap: model vs consensus
    if model_mult and target_mult:
        gap = model_mult / target_mult - 1
        r += 1
        write_cell(ws, r, 1, "격차 (모델 ÷ 컨센서스 − 1)", bold=True)
        write_cell(ws, r, 2, "-")
        write_cell(ws, r, 3, "-")
        write_cell(
            ws,
            r,
            4,
            gap,
            fmt="+0.0%;-0.0%;0.0%",
            fill=GREEN_FILL if abs(gap) <= 0.15 else RED_FILL,
            bold=True,
        )
        verdict = (
            "컨센서스와 정합 (±15% 내)"
            if abs(gap) <= 0.15
            else "컨센서스와 15% 초과 이격 — 적용 멀티플 또는 EBITDA 기준연도를 재검토"
        )
        write_cell(ws, r, 5, verdict)

    r += 2
    write_cell(
        ws,
        r,
        1,
        "⚠ 역산 멀티플의 한계: 목표주가는 이미 애널리스트가 고른 멀티플의 결과물이다. "
        "따라서 역산값을 '적용 멀티플의 근거'로 쓰면 순환논리가 된다. "
        "역산은 어디까지나 사후 검증(sanity check)이며, 근거는 위 표의 peer 통계와 프리미엄/할인 사유가 담당한다.",
        font=NOTE_FONT,
    )
    return r + 1
