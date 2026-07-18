"""One-line "how to build this sheet yourself" notes, written post-build.

Each sheet writes its title on row 1 and starts content on row 3 (Assumptions and
Dashboard use row 2 for the analysis-date line and start at row 4), so a single
note row can be dropped into the gap WITHOUT shifting anything. That matters:
Sensitivity/SOTP carry conditional formatting and Dashboard carries anchored
charts, both of which ``insert_rows()`` would silently break.

Guard: the note is only written if the target cell is empty.
"""

from ..excel_styles import NOTE_FONT

# sheet name -> (row, note)
GUIDES: dict[str, tuple[int, str]] = {
    "Assumptions": (
        3,
        "작성법: Raw Data §5 참조 → βL = βu×[1+(1−t)×D/E], Ke = Rf + βL×ERP, "
        "WACC = Ke×E% + Kd×(1−t)×D%. 멀티플은 Peer Comparison에서 확정한 값을 고정.",
    ),
    "Financial Summary": (
        2,
        "작성법: Raw Data §2 참조 → EBITDA = 영업이익 + 감가상각비 + 무형자산상각비. "
        "부문 D&A는 유무형자산 비중으로 배분한 뒤 부문 EBITDA를 만든다.",
    ),
    "SOTP Valuation": (
        2,
        "작성법: 부문 EBITDA(Financial Summary) × 적용 멀티플(Peer Comparison) = 부문 EV → "
        "합산 EV − 순차입금 = 지분가치 → ÷ 적용 주식수. P/BV·P/E 부문은 이미 지분가치이므로 순차입금 재차감 금지.",
    ),
    "DCF Valuation": (
        2,
        "작성법: FCFF = EBIT×(1−t) + D&A − Capex − ΔNWC → PV = FCFF/(1+WACC)^n, "
        "TV = FCFF_n×(1+g)/(WACC−g). TV 비중이 EV의 70%를 넘으면 가정을 다시 본다.",
    ),
    "DDM Valuation": (
        2,
        "작성법: 주당가치 = DPS×(1+g)/(Ke−g). Ke는 Assumptions, DPS·g는 Raw Data 기준.",
    ),
    "RIM Valuation": (
        2,
        "작성법: 가치 = 期初자본 + Σ PV(잔여이익), 잔여이익 = (ROE − Ke) × 期初자본.",
    ),
    "NAV Valuation": (
        2,
        "작성법: 순자산 + 재평가조정 − 지주할인. 할인율 가정이 결과를 좌우하므로 근거를 남긴다.",
    ),
    "Multiples Valuation": (
        2,
        "작성법: 적용 멀티플 × 기준 지표(EBITDA/매출/순이익) → EV 또는 지분가치. "
        "멀티플 선택 근거는 Peer Comparison에 기록.",
    ),
    "Peer Comparison": (
        2,
        "작성법: Raw Data §7의 peer 표에서 =MEDIAN/=QUARTILE로 통계를 직접 산출 → "
        "적용 멀티플을 정하고, 중앙값 대비 프리미엄/할인의 근거를 아래 '선정 근거' 열에 남긴다.",
    ),
    "Scenario Analysis": (
        2,
        "작성법: 시나리오별 드라이버를 밸류에이션 시트에 반영해 값을 재계산 → "
        "=SUMPRODUCT(확률, 시나리오가치)/100 로 확률가중 평균.",
    ),
    "Sensitivity": (
        2,
        "작성법: 축 변수 2개(예: 적용 멀티플 × WACC)를 잡고 [데이터] → [가상 분석] → [데이터 표]. "
        "행/열 입력 셀은 밸류에이션 시트의 가정 셀을 지정한다.",
    ),
    "Relative Valuation": (
        2,
        "작성법: Raw Data §1의 주가와 §2의 손익으로 PER/PBR/EV·EBITDA를 산출하고 peer 중앙값과 비교. "
        "결과가 아니라 진단용 시트다.",
    ),
    "Valuation History": (
        3,
        "작성법: DB에 저장된 당시 내재가치·시장가격을 읽기 전용으로 표시한다. 과거 입력을 현재 엔진으로 재계산하지 않는다.",
    ),
    "Dashboard": (
        3,
        "작성법: 결론 요약 시트. 여기서 새로 계산하지 말고 다른 시트 셀을 참조만 한다 (=시트!셀).",
    ),
    "rNPV Pipeline": (
        2,
        "작성법: 물질별 최고매출 × PoS → 연도별 위험조정 매출 → 할인. PoS는 임상단계별 기저율.",
    ),
    "Revenue Curves": (
        2,
        "작성법: 물질별 매출 곡선(출시→ramp-up→peak→LoE). rNPV Pipeline의 입력.",
    ),
}


def apply_guides(wb) -> None:
    """Write the per-sheet guide note into the reserved blank row."""
    for name, (row, text) in GUIDES.items():
        if name not in wb.sheetnames:
            continue
        ws = wb[name]
        cell = ws.cell(row=row, column=1)
        if cell.value:  # never clobber real content
            continue
        cell.value = text
        cell.font = NOTE_FONT
