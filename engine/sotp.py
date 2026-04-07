"""SOTP valuation engine: D&A allocation + EV calculation (mixed method support)."""

from schemas.models import DAAllocation, SOTPSegmentResult


def allocate_da(
    seg_data: dict[str, dict],
    total_da: int,
    segment_methods: dict[str, str] | None = None,
) -> dict[str, DAAllocation]:
    """Allocate D&A by tangible/intangible asset share -> compute segment EBITDA.

    Financial segments (method=pbv/pe) are excluded from D&A allocation.
    Total D&A is allocated 100% across manufacturing segments (preserves consolidated total).

    Args:
        seg_data: {code: {"op": int, "assets": int, ...}}
        total_da: Total D&A (in display unit)
        segment_methods: {code: "ev_ebitda"|"pbv"|"pe"} -- None defaults all to ev_ebitda

    Returns:
        {code: DAAllocation}
    """
    methods = segment_methods or {}

    # Only EV-based (manufacturing) segments are D&A allocation targets
    ev_codes = [c for c in seg_data if methods.get(c, "ev_ebitda") == "ev_ebitda"]
    ev_total_assets = sum(seg_data[c].get("assets", 0) for c in ev_codes) if ev_codes else 0

    results = {}
    for code, s in seg_data.items():
        method = methods.get(code, "ev_ebitda")
        if method == "ev_ebitda" and ev_total_assets > 0:
            share = s.get("assets", 0) / ev_total_assets
            da = round(total_da * share)
            ebitda = s.get("op", 0) + da
        else:
            # Financial segment: no D&A allocation, EBITDA = OP (not used in P/BV)
            share = 0
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
    ebitda_override: dict[str, int] | None = None,
    multiple_override: dict[str, float] | None = None,
    revenue_by_seg: dict[str, int] | None = None,
    revenue_override: dict[str, int] | None = None,
) -> tuple[dict[str, SOTPSegmentResult], int]:
    """Calculate SOTP EV (mixed method support).

    Without segments_info, uses EV/EBITDA-only logic (backward compatible).
    With segments_info, branches by method:
      - ev_ebitda: EBITDA x multiple -> EV
      - pbv: book_equity x multiple -> Equity (is_equity_based=True)
      - pe: net_income_segment x multiple -> Equity (is_equity_based=True)
      - ev_revenue: revenue x multiple -> EV (for pre-profit optionality segments)

    Args:
        ebitda_by_seg: {code: DAAllocation}
        multiples: {code: multiple}
        segments_info: {code: {"name", "multiple", "method", "book_equity", ...}}
        ebitda_override: {code: ebitda} -- per-scenario override for optionality segments
        multiple_override: {code: multiple} -- per-scenario multiple override
        revenue_by_seg: {code: revenue} -- base revenue for ev_revenue segments
        revenue_override: {code: revenue} -- per-scenario revenue override

    Returns:
        ({code: SOTPSegmentResult}, total_ev)
        total_ev = sum of EV-based + Equity-based values
    """
    result = {}
    for code, alloc in ebitda_by_seg.items():
        seg_info = (segments_info or {}).get(code, {})
        method = seg_info.get("method", "ev_ebitda")

        if method == "pbv":
            # multiple_override does NOT apply to equity-based segments
            m = multiples.get(code, 0)
            book_equity = seg_info.get("book_equity", 0)
            ev = round(book_equity * m) if book_equity > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=alloc.ebitda, multiple=m, ev=ev,
                method="pbv", is_equity_based=True,
            )
        elif method == "pe":
            m = multiples.get(code, 0)
            net_income = seg_info.get("net_income_segment", 0)
            ev = round(net_income * m) if net_income > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=alloc.ebitda, multiple=m, ev=ev,
                method="pe", is_equity_based=True,
            )
        elif method == "ev_revenue":
            # EV/Revenue for pre-profit optionality segments (FSD, Robotaxi, AI platform)
            # multiple_override applies (scenario-level multiple variation)
            m = (multiple_override or {}).get(code, multiples.get(code, 0))
            rev = (revenue_override or {}).get(code, (revenue_by_seg or {}).get(code, 0))
            ev = round(rev * m) if rev > 0 else 0
            result[code] = SOTPSegmentResult(
                ebitda=alloc.ebitda, multiple=m, ev=ev,
                method="ev_revenue", is_equity_based=False, revenue=rev,
            )
        else:
            # Standard EV/EBITDA — apply ebitda_override and multiple_override if provided
            # Negative EBITDA produces negative EV (restructuring/divestiture scenarios)
            m = (multiple_override or {}).get(code, multiples.get(code, 0))
            eb = (ebitda_override or {}).get(code, alloc.ebitda)
            ev = round(eb * m)
            result[code] = SOTPSegmentResult(
                ebitda=eb, multiple=m, ev=ev,
                method="ev_ebitda", is_equity_based=False,
            )

    total_ev = sum(r.ev for r in result.values())
    return result, total_ev
