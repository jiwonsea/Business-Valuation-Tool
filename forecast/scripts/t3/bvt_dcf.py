"""Faithful standalone re-implementation of BVT engine/dcf.py + engine/wacc.py
+ engine/gap_diagnostics.py solvers.

Purpose: T-3 reverse DCF must invert the SAME function the 7/10 BVT model used.
This file is a READ-ONLY port; BVT repo is not modified.
Source of truth: business-valuation-tool/engine/{dcf,wacc,gap_diagnostics}.py
"""
from __future__ import annotations


# ---------------------------------------------------------------- wacc.py port
_HAMADA_DE_CAP = 200.0
_DISTRESS_PREMIUM_MAX = 3.0
_DISTRESS_DE_MAX = 500.0


def calc_wacc(rf, erp, bu, de, tax, kd_pre, eq_w, size_premium=0.0, is_financial=False):
    distress_premium = 0.0
    if is_financial:
        bl = bu
    else:
        hamada_de = min(de, _HAMADA_DE_CAP)
        bl = bu * (1 + (1 - tax / 100) * hamada_de / 100)
        if de > _HAMADA_DE_CAP:
            excess = min(de - _HAMADA_DE_CAP, _DISTRESS_DE_MAX - _HAMADA_DE_CAP)
            distress_premium = excess / (_DISTRESS_DE_MAX - _HAMADA_DE_CAP) * _DISTRESS_PREMIUM_MAX
    ke = rf + bl * erp + size_premium
    kd_at = kd_pre * (1 - tax / 100)
    dw = 100 - eq_w
    wacc = ke * eq_w / 100 + kd_at * dw / 100 + distress_premium
    return {"bl": round(bl, 3), "ke": round(ke, 2), "kd_at": round(kd_at, 2),
            "wacc": round(wacc, 2), "distress_premium": round(distress_premium, 2)}


# ----------------------------------------------------------------- dcf.py port
def calc_dcf(ebitda_base, da_base, revenue_base, wacc_pct, params, base_year=2025):
    wacc = wacc_pct / 100
    tg = params["terminal_growth"] / 100
    tax_rate = params["tax_rate"] / 100
    growth_rates = params.get("ebitda_growth_rates") or [0.08, 0.07, 0.06, 0.05, 0.03]

    rev_growth_rates = params.get("revenue_growth_rates") or growth_rates
    if len(rev_growth_rates) < len(growth_rates):
        rev_growth_rates = list(rev_growth_rates) + [rev_growth_rates[-1]] * (
            len(growth_rates) - len(rev_growth_rates))

    if ebitda_base <= 0:
        raise ValueError("EBITDA <= 0")
    if wacc <= tg:
        raise ValueError(f"WACC({wacc_pct}) <= TGR({params['terminal_growth']})")

    ov = params.get("da_to_ebitda_override")
    if ov is not None and ov > 0:
        da_to_ebitda = ov
    else:
        da_to_ebitda = da_base / ebitda_base if ebitda_base > 0 else 0.5

    if params.get("actual_capex") is not None and da_base > 0:
        capex_ratio = params["actual_capex"] / da_base
    else:
        capex_ratio = params["capex_to_da"]

    capex_fade_to = params.get("capex_fade_to")
    use_capex_fade = capex_fade_to is not None and capex_fade_to != capex_ratio

    actual_nwc, prior_nwc = params.get("actual_nwc"), params.get("prior_nwc")
    if actual_nwc is not None and prior_nwc is not None and revenue_base > 0:
        nwc_ratio = actual_nwc / revenue_base
    else:
        nwc_ratio = params["nwc_to_rev_delta"]

    projections = []
    prev_ebitda, prev_revenue = ebitda_base, revenue_base
    _use_actual_nwc = actual_nwc is not None and prior_nwc is not None
    prev_nwc = actual_nwc if _use_actual_nwc else round(revenue_base * nwc_ratio)

    for i, g in enumerate(growth_rates):
        ebitda = round(prev_ebitda * (1 + g))
        da = round(ebitda * da_to_ebitda)
        op = ebitda - da
        nopat = round(op * (1 - tax_rate)) if op > 0 else op
        if use_capex_fade:
            n_years = len(growth_rates)
            t = i / max(n_years - 1, 1)
            year_capex_ratio = capex_ratio + (capex_fade_to - capex_ratio) * t
        else:
            year_capex_ratio = capex_ratio
        capex = round(da * year_capex_ratio)
        revenue = round(prev_revenue * (1 + rev_growth_rates[i]))
        if _use_actual_nwc:
            nwc_current = round(revenue * nwc_ratio)
            delta_nwc = nwc_current - prev_nwc
            prev_nwc = nwc_current
        else:
            delta_nwc = round((revenue - prev_revenue) * nwc_ratio)
        fcff = nopat + da - capex - delta_nwc
        projections.append({"year": base_year + 1 + i, "ebitda": ebitda, "op": op,
                            "da": da, "nopat": nopat, "capex": capex,
                            "delta_nwc": delta_nwc, "fcff": fcff, "growth": g})
        prev_ebitda, prev_revenue = ebitda, revenue

    pv_fcff = 0
    for i, p in enumerate(projections):
        p["pv_fcff"] = round(p["fcff"] / (1 + wacc) ** (i + 1))
        pv_fcff += p["pv_fcff"]

    last = projections[-1]
    normalized_fcff = last["nopat"] - last["delta_nwc"] if last["nopat"] > 0 else last["fcff"]
    terminal_fcff = round(normalized_fcff * (1 + tg))
    terminal_value = round(terminal_fcff / (wacc - tg))
    n = len(projections)
    pv_terminal = round(terminal_value / (1 + wacc) ** n)
    ev_dcf = pv_fcff + pv_terminal
    return {"projections": projections, "pv_fcff_sum": pv_fcff,
            "terminal_value": terminal_value, "pv_terminal": pv_terminal,
            "ev_dcf": ev_dcf,
            "tv_ev_ratio": round(pv_terminal / ev_dcf * 100, 1) if ev_dcf > 0 else 0.0}


# ------------------------------------------------- gap_diagnostics.py solvers
_WACC_LO, _WACC_HI = 2.0, 25.0
_TGR_LO, _TGR_HI = 0.0, 5.0
_GMULT_LO, _GMULT_HI = 0.3, 8.0
_TOLERANCE = 1e-4
_MAX_ITER = 60


def _binary_search(f, lo, hi, target, tol=None):
    tol = _TOLERANCE if tol is None else tol
    f_lo, f_hi = f(lo), f(hi)
    if f_lo < f_hi:
        if not (f_lo <= target <= f_hi):
            return None
        for _ in range(_MAX_ITER):
            mid = (lo + hi) / 2
            fm = f(mid)
            if abs(fm - target) / max(abs(target), 1e-6) < tol:
                return mid
            if fm < target:
                lo = mid
            else:
                hi = mid
    else:
        if not (f_hi <= target <= f_lo):
            return None
        for _ in range(_MAX_ITER):
            mid = (lo + hi) / 2
            fm = f(mid)
            if abs(fm - target) / max(abs(target), 1e-6) < tol:
                return mid
            if fm > target:
                lo = mid
            else:
                hi = mid
    return None


def _ev(eb, da, rev, wacc, params, base_year):
    try:
        return float(calc_dcf(eb, da, rev, wacc, params, base_year)["ev_dcf"])
    except (ValueError, ZeroDivisionError):
        return 0.0


def solve_implied_wacc(target_ev, eb, da, rev, params, base_year=2025, tol=None):
    lo = max(params["terminal_growth"] + 0.5, _WACC_LO)
    return _binary_search(lambda w: _ev(eb, da, rev, w, params, base_year),
                          lo, _WACC_HI, target_ev, tol)


def solve_implied_tgr(target_ev, eb, da, rev, wacc_pct, params, base_year=2025, tol=None):
    tgr_hi = min(_TGR_HI, wacc_pct - 0.5)
    if tgr_hi <= _TGR_LO:
        return None

    def f(tgr):
        p = dict(params, terminal_growth=tgr)
        return _ev(eb, da, rev, wacc_pct, p, base_year)
    return _binary_search(f, _TGR_LO, tgr_hi, target_ev, tol)


def solve_implied_growth_multiplier(target_ev, eb, da, rev, wacc_pct, params, base_year=2025, tol=None):
    base_rates = params.get("ebitda_growth_rates") or []
    if not base_rates:
        return None

    def f(mult):
        p = dict(params, ebitda_growth_rates=[max(r * mult, -0.5) for r in base_rates])
        return _ev(eb, da, rev, wacc_pct, p, base_year)
    return _binary_search(f, _GMULT_LO, _GMULT_HI, target_ev, tol)
