"""SOTP 밸류에이션 엔진: D&A 배분 + EV 산출."""

from schemas.models import DAAllocation, SOTPSegmentResult


def allocate_da(
    seg_data: dict[str, dict],
    total_da: int,
) -> dict[str, DAAllocation]:
    """유무형자산 비중으로 D&A 배분 → 부문별 EBITDA 산출.

    Args:
        seg_data: {code: {"op": int, "assets": int, ...}}
        total_da: 전체 D&A (백만원)

    Returns:
        {code: DAAllocation}
    """
    total_assets = sum(s["assets"] for s in seg_data.values())
    results = {}
    for code, s in seg_data.items():
        share = s["assets"] / total_assets if total_assets > 0 else 0
        da = round(total_da * share)
        ebitda = s["op"] + da
        results[code] = DAAllocation(
            asset_share=round(share * 100, 2),
            da_allocated=da,
            ebitda=ebitda,
        )
    return results


def calc_sotp(
    ebitda_by_seg: dict[str, DAAllocation],
    multiples: dict[str, float],
) -> tuple[dict[str, SOTPSegmentResult], int]:
    """SOTP EV 산출.

    Args:
        ebitda_by_seg: {code: DAAllocation} (allocate_da 결과)
        multiples: {code: EV/EBITDA 배수}

    Returns:
        ({code: SOTPSegmentResult}, total_ev)
    """
    result = {}
    for code, alloc in ebitda_by_seg.items():
        eb = alloc.ebitda
        m = multiples.get(code, 0)
        ev = round(eb * m) if eb > 0 else 0
        result[code] = SOTPSegmentResult(ebitda=eb, multiple=m, ev=ev)
    total_ev = sum(r.ev for r in result.values())
    return result, total_ev
