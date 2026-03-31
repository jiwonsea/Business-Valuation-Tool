"""SOTP 밸류에이션 엔진: D&A 배분 + EV 산출 (Mixed Method 지원)."""

from schemas.models import DAAllocation, SOTPSegmentResult


def allocate_da(
    seg_data: dict[str, dict],
    total_da: int,
    segment_methods: dict[str, str] | None = None,
) -> dict[str, DAAllocation]:
    """유무형자산 비중으로 D&A 배분 → 부문별 EBITDA 산출.

    금융 부문(method=pbv/pe)은 D&A 배분 대상에서 제외.
    전체 total_da를 제조 세그먼트 간에 100% 배분 (연결 합계 유지).

    Args:
        seg_data: {code: {"op": int, "assets": int, ...}}
        total_da: 전체 D&A (백만원)
        segment_methods: {code: "ev_ebitda"|"pbv"|"pe"} — None이면 전부 ev_ebitda

    Returns:
        {code: DAAllocation}
    """
    methods = segment_methods or {}

    # EV 기반(제조) 세그먼트만 D&A 배분 대상
    ev_codes = [c for c in seg_data if methods.get(c, "ev_ebitda") == "ev_ebitda"]
    ev_total_assets = sum(seg_data[c]["assets"] for c in ev_codes) if ev_codes else 0

    results = {}
    for code, s in seg_data.items():
        method = methods.get(code, "ev_ebitda")
        if method == "ev_ebitda" and ev_total_assets > 0:
            share = s["assets"] / ev_total_assets
            da = round(total_da * share)
            ebitda = s["op"] + da
        else:
            # 금융 부문: D&A 미배분, EBITDA = OP (P/BV에서는 사용 안 함)
            all_total_assets = sum(d["assets"] for d in seg_data.values())
            share = s["assets"] / all_total_assets if all_total_assets > 0 else 0
            da = 0
            ebitda = s["op"]

        results[code] = DAAllocation(
            asset_share=round(share * 100, 2),
            da_allocated=da,
            ebitda=ebitda,
        )
    return results


def calc_sotp(
    ebitda_by_seg: dict[str, DAAllocation],
    multiples: dict[str, float],
    segments_info: dict[str, dict] | None = None,
) -> tuple[dict[str, SOTPSegmentResult], int]:
    """SOTP EV 산출 (Mixed Method 지원).

    segments_info가 없으면 기존 EV/EBITDA 전용 로직 (하위호환).
    segments_info가 있으면 method별 분기:
      - ev_ebitda: EBITDA × multiple → EV
      - pbv: book_equity × multiple → Equity (is_equity_based=True)
      - pe: net_income_segment × multiple → Equity (is_equity_based=True)

    Args:
        ebitda_by_seg: {code: DAAllocation}
        multiples: {code: multiple}
        segments_info: {code: {"name", "multiple", "method", "book_equity", ...}}

    Returns:
        ({code: SOTPSegmentResult}, total_ev)
        total_ev = EV기반 + Equity기반 합산
    """
    result = {}
    for code, alloc in ebitda_by_seg.items():
        m = multiples.get(code, 0)
        seg_info = (segments_info or {}).get(code, {})
        method = seg_info.get("method", "ev_ebitda")

        if method == "pbv":
            book_equity = seg_info.get("book_equity", 0)
            ev = round(book_equity * m) if book_equity > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=alloc.ebitda, multiple=m, ev=ev,
                method="pbv", is_equity_based=True,
            )
        elif method == "pe":
            net_income = seg_info.get("net_income_segment", 0)
            ev = round(net_income * m) if net_income > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=alloc.ebitda, multiple=m, ev=ev,
                method="pe", is_equity_based=True,
            )
        else:
            # 기존 EV/EBITDA
            eb = alloc.ebitda
            ev = round(eb * m) if eb > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=eb, multiple=m, ev=ev,
                method="ev_ebitda", is_equity_based=False,
            )

    total_ev = sum(r.ev for r in result.values())
    return result, total_ev
