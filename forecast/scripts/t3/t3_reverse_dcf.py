"""T-3 REVERSE DCF — "what the market has priced in"
NVDA FY2027Q2 deep dive · plan PLAN_nvda_2026-08_deep_dive.md rev-3b §0.3

Decisions in force (user 2026-08-09):
  D1  V-SEG is STALE -> pre-print BVT (SOTP/V2/V4) halted. T-3 runs on the
      CONSOLIDATED DCF path only, which provably consumes no segment mapping
      (BVT attach_gap_diagnostic reads vi.consolidated[base_year] only).
  D2  Baseline parameter set = 7/10 AS-RUN (FY26 from git eaf2dfa; TTM & FY27E
      from the as-run profiles). Parameter drift reported as a separate axis.
  D3  target_EV = market_cap + net_debt (corrected) is PRIMARY;
      BVT's market_cap + max(net_debt, 0) reported alongside. BVT NOT patched.

Every table below is script-generated. No hand-typed numbers.
"""
from __future__ import annotations
import json
from bvt_dcf import (calc_wacc, calc_dcf, solve_implied_wacc, solve_implied_tgr,
                     solve_implied_growth_multiplier, _binary_search, _ev)

UNIT = 1_000_000
SHARES = 24_300_000_000          # valuation_shares, all three 7/10 anchors

PRICE_NOW = 223.96               # 2026-08-07 close (plan §1)
PRICE_PT = 302.83                # sell-side PT, 61 analysts, 2026-08-03
PRICE_0710 = 202.34              # 2026-07-09 close (7/10 reference)

# ---------------------------------------------------------------- ANCHORS ----
ANCHORS = {
    "FY26": dict(
        label="FY26 확정 (git eaf2dfa nvda.yaml, 7/10 as-run)",
        wacc_p=dict(rf=3.2, erp=5.5, bu=1.45, de=0.2, tax=13.0, kd_pre=3.8, eq_w=99.8),
        op=130387, dep=2843, amort=0, revenue=215938, net_debt=435,
        dcf_p=dict(ebitda_growth_rates=[0.10, 0.085, 0.07, 0.055, 0.04], tax_rate=7.9,
                   capex_to_da=1.52, nwc_to_rev_delta=0.05, terminal_growth=3.0,
                   actual_capex=6042, capex_fade_to=None, da_to_ebitda_override=0.0291),
        expect_ev=1_758_804, expect_wacc=11.17,
    ),
    "TTM": dict(
        label="TTM 2026-04 (nvda_ttm.yaml, 7/10 as-run)",
        wacc_p=dict(rf=4.56, erp=4.6, bu=1.45, de=4.3, tax=17.0, kd_pre=4.8, eq_w=95.9),
        op=162285, dep=3229, amort=0, revenue=253491, net_debt=-41865,
        dcf_p=dict(ebitda_growth_rates=[0.45, 0.25, 0.15, 0.10, 0.05], tax_rate=16.6,
                   capex_to_da=2.03, nwc_to_rev_delta=0.05, terminal_growth=3.0,
                   actual_capex=6553, capex_fade_to=None, da_to_ebitda_override=0.0195),
        expect_ev=3_350_317, expect_wacc=11.16,
    ),
    "FY27E": dict(
        label="FY27E (nvda_fy27e.yaml, 7/10 as-run) [PRIMARY]",
        wacc_p=dict(rf=4.56, erp=4.6, bu=1.45, de=3.4, tax=17.0, kd_pre=4.8, eq_w=96.7),
        op=256300, dep=4300, amort=0, revenue=391300, net_debt=-60000,
        dcf_p=dict(ebitda_growth_rates=[0.18, 0.13, 0.09, 0.06, 0.04], tax_rate=16.6,
                   capex_to_da=2.1, nwc_to_rev_delta=0.05, terminal_growth=3.0,
                   actual_capex=9000, capex_fade_to=None, da_to_ebitda_override=0.0165),
        expect_ev=3_601_474, expect_wacc=11.17,
    ),
}
BASE_YEAR = 2026


def prep(a):
    da = a["dep"] + a["amort"]
    return dict(a, da_base=da, ebitda_base=a["op"] + da,
                wacc=calc_wacc(**a["wacc_p"])["wacc"])


ANCHORS = {k: prep(v) for k, v in ANCHORS.items()}

# ------------------------------------------------------- V1 REPRODUCTION -----
def v1_gate():
    rows, ok = [], True
    for k, a in ANCHORS.items():
        d = calc_dcf(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"],
                     a["dcf_p"], BASE_YEAR)
        w_ok = abs(a["wacc"] - a["expect_wacc"]) < 1e-9
        e_ok = d["ev_dcf"] == a["expect_ev"]
        ok &= w_ok and e_ok
        rows.append((k, a["wacc"], a["expect_wacc"], w_ok, d["ev_dcf"], a["expect_ev"], e_ok,
                     d["tv_ev_ratio"]))
    # 7/10 FY26 reverse-DCF values, from _run_fy26_baseline.txt
    a = ANCHORS["FY26"]
    tgt = PRICE_0710 * SHARES / UNIT + max(a["net_debt"], 0)
    iw = solve_implied_wacc(tgt, a["ebitda_base"], a["da_base"], a["revenue"], a["dcf_p"], BASE_YEAR)
    ig = solve_implied_growth_multiplier(tgt, a["ebitda_base"], a["da_base"], a["revenue"],
                                         a["wacc"], a["dcf_p"], BASE_YEAR)
    rev_ok = round(iw, 2) == 5.97 and round(ig, 2) == 4.94
    ok &= rev_ok
    return ok, rows, (iw, ig, rev_ok)


# ------------------------------------------------------------- AXES ----------
_MARGIN_LO, _MARGIN_HI = 0.05, 0.99
_DUR_LO, _DUR_HI = 0.0, 40.0


def _sched_extend(base_rates, extra_years):
    """Duration axis: extend the fade schedule by `extra_years` at the terminal-approach
    rate (the last explicit rate). Fractional years get a partial-weight final stub."""
    rates = list(base_rates)
    n_full = int(extra_years)
    frac = extra_years - n_full
    g_last = base_rates[-1]
    rates += [g_last] * n_full
    if frac > 1e-9:
        rates.append(g_last * frac)
    return rates


def solve_implied_margin(target_ev, a):
    """EBITDA-margin axis (C3). ebitda_base := revenue x m, da_base held so that
    capex_ratio = actual_capex / da_base is unchanged. Identity check: m0 = eb/rev
    must reproduce the unchanged EV exactly."""
    rev, da, p, w = a["revenue"], a["da_base"], a["dcf_p"], a["wacc"]

    def f(m):
        return _ev(int(round(rev * m)), da, rev, w, p, BASE_YEAR)
    return _binary_search(f, _MARGIN_LO, _MARGIN_HI, target_ev)


def solve_implied_duration(target_ev, a):
    """Duration axis: extra years of the terminal-approach growth rate."""
    eb, da, rev, w, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
    base_rates = p["ebitda_growth_rates"]

    def f(x):
        return _ev(eb, da, rev, w, dict(p, ebitda_growth_rates=_sched_extend(base_rates, x)),
                   BASE_YEAR)
    return _binary_search(f, _DUR_LO, _DUR_HI, target_ev)


# ------------------------------------------------- V5 MONOTONICITY CHECK -----
def monotone(f, lo, hi, n=25):
    xs = [lo + (hi - lo) * i / (n - 1) for i in range(n)]
    ys = [f(x) for x in xs]
    inc = all(ys[i] <= ys[i + 1] + 1e-6 for i in range(n - 1))
    dec = all(ys[i] >= ys[i + 1] - 1e-6 for i in range(n - 1))
    return ("increasing" if inc else "decreasing" if dec else "NON-MONOTONE"), ys[0], ys[-1]


# ------------------------------------------------------------ MAIN -----------
def solve_all(a, price, target_mode="corrected"):
    eb, da, rev, w, p, nd = (a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"],
                             a["dcf_p"], a["net_debt"])
    mcap = price * SHARES / UNIT
    tgt = mcap + (nd if target_mode == "corrected" else max(nd, 0))
    out = {"price": price, "market_cap": mcap, "target_ev": tgt, "target_mode": target_mode}

    iw = solve_implied_wacc(tgt, eb, da, rev, p, BASE_YEAR)
    it = solve_implied_tgr(tgt, eb, da, rev, w, p, BASE_YEAR)
    ig = solve_implied_growth_multiplier(tgt, eb, da, rev, w, p, BASE_YEAR)
    im = solve_implied_margin(tgt, a)
    idur = solve_implied_duration(tgt, a)

    out["axes"] = {
        "implied_wacc_pct": iw,
        "implied_tgr_pct": it,
        "implied_growth_mult": ig,
        "implied_ebitda_margin": im,
        "implied_extra_years": idur,
    }

    # V2 residual + V3 round-trip, per solved axis
    checks = {}

    def _chk(name, ev_val):
        if ev_val is None:
            checks[name] = {"status": "UNREACHABLE"}
            return
        resid = abs(ev_val - tgt) / abs(tgt)
        ps = (ev_val - nd) * UNIT / SHARES
        checks[name] = {"status": "OK" if resid < 1e-4 and abs(ps - price) < 0.01 else "FAIL",
                        "residual": resid, "round_trip_ps": ps, "dps": ps - price}

    _chk("implied_wacc", None if iw is None else _ev(eb, da, rev, iw, p, BASE_YEAR))
    _chk("implied_tgr", None if it is None else _ev(eb, da, rev, w, dict(p, terminal_growth=it), BASE_YEAR))
    _chk("implied_growth_mult", None if ig is None else _ev(
        eb, da, rev, w, dict(p, ebitda_growth_rates=[max(r * ig, -0.5) for r in p["ebitda_growth_rates"]]), BASE_YEAR))
    _chk("implied_margin", None if im is None else _ev(int(round(rev * im)), da, rev, w, p, BASE_YEAR))
    _chk("implied_duration", None if idur is None else _ev(
        eb, da, rev, w, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], idur)), BASE_YEAR))
    out["checks"] = checks
    return out


def fmt(v, kind):
    if v is None:
        return "UNREACHABLE"
    return {"pct": f"{v:.2f}%", "x": f"{v:.2f}x", "m": f"{v*100:.2f}%", "y": f"{v:.2f}y"}[kind]


if __name__ == "__main__":
    ok, rows, (iw710, ig710, rev_ok) = v1_gate()
    print("=" * 100)
    print("V1  재현 게이트 — 7/10 as-run 대조")
    print("=" * 100)
    print(f"{'anchor':<7} {'WACC':>7} {'expect':>7} {'':2} {'EV_dcf':>12} {'expect':>12} {'':2} {'TV/EV':>6}")
    for k, w, we, wok, ev, eve, eok, tv in rows:
        print(f"{k:<7} {w:>6.2f}% {we:>6.2f}% {'OK' if wok else 'X':>2} "
              f"{ev:>12,} {eve:>12,} {'OK' if eok else 'X':>2} {tv:>5.1f}%")
    print(f"7/10 FY26 역산: implied WACC {iw710:.2f}% (expect 5.97) · "
          f"growth_mult {ig710:.2f}x (expect 4.94) -> {'OK' if rev_ok else 'FAIL'}")
    print(f"\n>>> V1 GATE: {'PASS' if ok else 'FAIL — T-3 중단'}")
    if not ok:
        raise SystemExit(1)

    # C3 identity proof: margin reparameterisation is equivalent at m0
    print("\n" + "=" * 100)
    print("C3  마진 축 재파라미터화 동치 증명  (ebitda_base == revenue x m0 이면 EV 동일)")
    print("=" * 100)
    for k, a in ANCHORS.items():
        m0 = a["ebitda_base"] / a["revenue"]
        ev0 = _ev(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
        ev1 = _ev(int(round(a["revenue"] * m0)), a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
        print(f"{k:<7} m0={m0*100:6.3f}%  EV(orig)={ev0:>12,.0f}  EV(reparam)={ev1:>12,.0f}  "
              f"{'IDENTICAL' if ev0 == ev1 else 'MISMATCH'}")

    # V5 monotonicity
    print("\n" + "=" * 100)
    print("V5  축별 단조성 (이분탐색 유효 조건)")
    print("=" * 100)
    a = ANCHORS["FY27E"]
    eb, da, rev, w, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
    tests = {
        "WACC":     (lambda x: _ev(eb, da, rev, x, p, BASE_YEAR), max(p["terminal_growth"] + 0.5, 2.0), 25.0),
        "TGR":      (lambda x: _ev(eb, da, rev, w, dict(p, terminal_growth=x), BASE_YEAR), 0.0, min(5.0, w - 0.5)),
        "g-mult":   (lambda x: _ev(eb, da, rev, w, dict(p, ebitda_growth_rates=[max(r * x, -0.5) for r in p["ebitda_growth_rates"]]), BASE_YEAR), 0.3, 8.0),
        "margin":   (lambda x: _ev(int(round(rev * x)), da, rev, w, p, BASE_YEAR), 0.05, 0.99),
        "duration": (lambda x: _ev(eb, da, rev, w, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], x)), BASE_YEAR), 0.0, 40.0),
    }
    for name, (f, lo, hi) in tests.items():
        d, y0, y1 = monotone(f, lo, hi)
        print(f"  {name:<9} [{lo:>6.2f},{hi:>6.2f}] -> {d:<13} EV {y0:>14,.0f} .. {y1:>14,.0f}")

    # main solve
    results = {}
    print("\n" + "=" * 100)
    print("T-3  시장이 가격에 넣은 가정 — 조건부 역산 (나머지 3축 고정)")
    print("=" * 100)
    for pname, price in (("현재가", PRICE_NOW), ("셀사이드 PT", PRICE_PT), ("[ref] 7/10", PRICE_0710)):
        print(f"\n### {pname} ${price:.2f}")
        print(f"{'anchor':<7} {'target_EV':>12} {'모델EV':>12} {'모델주가':>9} {'괴리':>8} | "
              f"{'iWACC':>10} {'iTGR':>10} {'g-mult':>10} {'iMargin':>10} {'+years':>10}")
        for k, a in ANCHORS.items():
            r = solve_all(a, price, "corrected")
            ev0 = _ev(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
            ps0 = (ev0 - a["net_debt"]) * UNIT / SHARES
            ax = r["axes"]
            print(f"{k:<7} {r['target_ev']:>12,.0f} {ev0:>12,.0f} {ps0:>9.2f} "
                  f"{(ps0-price)/price*100:>7.1f}% | "
                  f"{fmt(ax['implied_wacc_pct'],'pct'):>10} {fmt(ax['implied_tgr_pct'],'pct'):>10} "
                  f"{fmt(ax['implied_growth_mult'],'x'):>10} {fmt(ax['implied_ebitda_margin'],'m'):>10} "
                  f"{fmt(ax['implied_extra_years'],'y'):>10}")
            results[f"{k}|{price}"] = r

    # V6 target-EV definition comparison
    print("\n" + "=" * 100)
    print("V6  target_EV 정의 병기  (정정 = mcap + net_debt · BVT현행 = mcap + max(net_debt,0))")
    print("=" * 100)
    print(f"{'anchor':<7} {'net_debt':>10} {'정정 target':>13} {'BVT target':>13} {'차이':>10} | "
          f"{'iWACC 정정':>11} {'iWACC BVT':>11} {'Δ':>7}")
    for k, a in ANCHORS.items():
        rc = solve_all(a, PRICE_NOW, "corrected")
        rb = solve_all(a, PRICE_NOW, "bvt")
        wc, wb = rc["axes"]["implied_wacc_pct"], rb["axes"]["implied_wacc_pct"]
        d = "" if (wc is None or wb is None) else f"{wb-wc:+.2f}p"
        print(f"{k:<7} {a['net_debt']:>10,} {rc['target_ev']:>13,.0f} {rb['target_ev']:>13,.0f} "
              f"{rb['target_ev']-rc['target_ev']:>10,.0f} | {fmt(wc,'pct'):>11} {fmt(wb,'pct'):>11} {d:>7}")

    # V2/V3 checks
    print("\n" + "=" * 100)
    print("V2/V3  잔차 < 1e-4  &  왕복 주가 ±$0.01  (FY27E · 현재가)")
    print("=" * 100)
    r = results[f"FY27E|{PRICE_NOW}"]
    for name, c in r["checks"].items():
        if c["status"] == "UNREACHABLE":
            print(f"  {name:<22} UNREACHABLE (V4 fail-closed)")
        else:
            print(f"  {name:<22} {c['status']:<5} residual={c['residual']:.2e}  "
                  f"round-trip=${c['round_trip_ps']:.4f} (Δ${c['dps']:+.4f})")

    with open("t3_results.json", "w", encoding="utf-8") as f:
        json.dump({"anchors": {k: {kk: vv for kk, vv in v.items() if kk != "dcf_p"}
                               for k, v in ANCHORS.items()},
                   "results": results}, f, ensure_ascii=False, indent=2, default=str)
    print("\n-> t3_results.json 기록 완료")
