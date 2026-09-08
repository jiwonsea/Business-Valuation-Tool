"""Independent recomputation of the SK ecoplant 2026 Q2 valuation.

Audit companion to REVIEW_CLAUDE_sk_ecoplant_q2_audit_2026-08-30.md.
Reads nothing from the engine on purpose: every number is rebuilt from the
profile inputs so that engine defects cannot hide behind the engine itself.
"""

from __future__ import annotations

import copy

NET_DEBT = 3_736_671
NCI = 3_674_164
SHARES = 63_135_799
TOTAL_DA = 284_034

SEGMENT_ASSETS = {"HI": 494_371, "GAS": 1_652_565, "ALC": 1_348_099, "SOL": 1_205_254}
SEGMENT_OP = {"HI": 250_000, "GAS": 125_000, "ALC": 900_000, "SOL": -120_000}

SCENARIOS = {
    "Base": {
        "prob": 60,
        "dlom": 15,
        "rcps": 534_200,
        "multiples": {"HI": 8.0, "GAS": 10.0, "ALC": 6.0, "SOL": 0.10},
        "ebitda": {"HI": 280_000, "GAS": 220_000, "ALC": 1_050_000},
        "revenue": {"SOL": 4_013_285},
    },
    "Bull": {
        "prob": 20,
        "dlom": 10,
        "rcps": 534_200,
        "multiples": {"HI": 9.0, "GAS": 11.0, "ALC": 7.0, "SOL": 0.10},
        "ebitda": {"HI": 374_000, "GAS": 260_000, "ALC": 1_600_000},
        "revenue": {"SOL": 4_400_000},
    },
    "Bear": {
        "prob": 20,
        "dlom": 25,
        "rcps": 575_600,
        "multiples": {"HI": 7.0, "GAS": 8.5, "ALC": 4.5, "SOL": 0.05},
        "ebitda": {"HI": 200_000, "GAS": 170_000, "ALC": 550_000},
        "revenue": {"SOL": 3_600_000},
    },
}

REPORTED = {"Base": 43_032, "Bull": 141_423, "Bear": -39_382, "weighted": 46_228}
OTC_PRICE = 46_500


def scenario_ev(sc: dict) -> float:
    ev = sum(sc["ebitda"][c] * sc["multiples"][c] for c in sc["ebitda"])
    ev += sum(sc["revenue"][c] * sc["multiples"][c] for c in sc["revenue"])
    return ev


def per_share(sc: dict, nci: float = NCI, dlom: float | None = None) -> float:
    equity = scenario_ev(sc) - NET_DEBT - nci - sc["rcps"]
    pre = equity * 1_000_000 / SHARES
    d = sc["dlom"] if dlom is None else dlom
    # DLOM is not applied to negative equity (engine/scenario.py policy).
    return pre * (1 - d / 100) if equity > 0 else pre


def weighted(
    scenarios: dict, nci_proportional: bool = False, dlom: float | None = None
) -> float:
    ratio = NCI / scenario_ev(SCENARIOS["Base"])
    total = 0.0
    for sc in scenarios.values():
        nci = scenario_ev(sc) * ratio if nci_proportional else NCI
        total += per_share(sc, nci, dlom) * sc["prob"] / 100
    return total


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def check_reproduction() -> None:
    section("1. 리포트 수치 재현")
    total = 0.0
    for name, sc in SCENARIOS.items():
        ev = scenario_ev(sc)
        equity = ev - NET_DEBT - NCI - sc["rcps"]
        value = per_share(sc)
        total += value * sc["prob"] / 100
        delta = value - REPORTED[name]
        print(
            f"  {name:5s} EV={ev / 1e6:6.3f}조  Equity={equity / 1e6:7.3f}조  "
            f"주당={value:9,.0f}  리포트={REPORTED[name]:9,.0f}  차이={delta:+.0f}"
        )
    print(
        f"  확률가중 = {total:,.1f}원   리포트 = {REPORTED['weighted']:,}원   "
        f"차이 = {total - REPORTED['weighted']:+.1f}"
    )
    print("\n  기여도:")
    for name, sc in SCENARIOS.items():
        share = per_share(sc) * sc["prob"] / 100 / total * 100
        print(f"    {name:5s} 확률 {sc['prob']:2d}%  →  기여 {share:6.1f}%")


def check_da_allocation() -> None:
    section("2. E1 — D&A 배분 (ev_revenue 부문 제외 버그)")
    cur_den = sum(SEGMENT_ASSETS[c] for c in ("HI", "GAS", "ALC"))
    all_den = sum(SEGMENT_ASSETS.values())
    sheet_multiples = {"HI": 7.57, "GAS": 9.73, "ALC": 5.84}
    ev_cur = ev_fix = 0.0
    for c in ("HI", "GAS", "ALC"):
        da_cur = TOTAL_DA * SEGMENT_ASSETS[c] / cur_den
        da_fix = TOTAL_DA * SEGMENT_ASSETS[c] / all_den
        e_cur, e_fix = SEGMENT_OP[c] + da_cur, SEGMENT_OP[c] + da_fix
        ev_cur += e_cur * sheet_multiples[c]
        ev_fix += e_fix * sheet_multiples[c]
        print(
            f"  {c:4s} D&A {da_cur:9,.0f} → {da_fix:9,.0f}   "
            f"EBITDA {e_cur:10,.0f} → {e_fix:10,.0f}  ({(e_fix / e_cur - 1) * 100:+5.1f}%)"
        )
    print(
        f"  SOL  D&A {0:9,.0f} → {TOTAL_DA * SEGMENT_ASSETS['SOL'] / all_den:9,.0f}   (EV/Revenue 방식, EBITDA 미사용)"
    )
    sol_ev = 4_013_285 * 0.15
    print(
        f"\n  SOTP EV  {(ev_cur + sol_ev) / 1e6:.3f}조 → {(ev_fix + sol_ev) / 1e6:.3f}조  "
        f"({((ev_fix + sol_ev) / (ev_cur + sol_ev) - 1) * 100:+.1f}%)"
    )
    for label, ev in (("현행", ev_cur + sol_ev), ("정정", ev_fix + sol_ev)):
        eq_full = ev - NET_DEBT - NCI - 534_200
        print(
            f"  {label} 완전브리지 {eq_full * 1e6 / SHARES:9,.0f}원   "
            f"엑셀 부분브리지(순차입금만) {(ev - NET_DEBT) * 1e6 / SHARES:9,.0f}원"
        )


def check_spread_decomposition() -> None:
    section("3. V4 — Bull/Bear 스프레드 분해")
    base = SCENARIOS["Base"]
    for label, key in (
        ("EBITDA·매출만 변동 (배수 Base 고정)", "ebitda"),
        ("배수만 변동 (EBITDA Base 고정)", "multiples"),
    ):
        row = {}
        for name in ("Bull", "Bear"):
            sc = copy.deepcopy(base)
            if key == "ebitda":
                sc["ebitda"], sc["revenue"] = (
                    SCENARIOS[name]["ebitda"],
                    SCENARIOS[name]["revenue"],
                )
            else:
                sc["multiples"] = SCENARIOS[name]["multiples"]
            row[name] = scenario_ev(sc)
        print(
            f"  {label:36s} Bull={row['Bull'] / 1e6:6.2f}조  "
            f"Bear={row['Bear'] / 1e6:6.2f}조  배율={row['Bull'] / row['Bear']:.2f}x"
        )
    bull, bear = scenario_ev(SCENARIOS["Bull"]), scenario_ev(SCENARIOS["Bear"])
    print(
        f"  {'둘 다 변동 (실제)':36s} Bull={bull / 1e6:6.2f}조  "
        f"Bear={bear / 1e6:6.2f}조  배율={bull / bear:.2f}x"
    )
    print("\n  레버별 Bull/Bear 비율 (클램프 대상 여부):")
    for c in ("HI", "GAS", "ALC", "SOL"):
        m = SCENARIOS["Bull"]["multiples"][c] / SCENARIOS["Bear"]["multiples"][c]
        print(f"    segment_multiples[{c}]  {m:5.2f}x   클램프 ≤2.0x 적용")
    for c in ("HI", "GAS", "ALC"):
        e = SCENARIOS["Bull"]["ebitda"][c] / SCENARIOS["Bear"]["ebitda"][c]
        mark = "  ← 상한 없음" if e > 2.0 else "   상한 없음"
        print(f"    segment_ebitda[{c}]     {e:5.2f}x {mark}")


def check_probability_sensitivity() -> None:
    section("4. 확률배분 민감도")
    print("  Base 60% 고정, Bull/Bear만 이동:")
    for bull in (30, 25, 20, 15, 10):
        sc = copy.deepcopy(SCENARIOS)
        sc["Bull"]["prob"], sc["Bear"]["prob"] = bull, 40 - bull
        total = weighted(sc)
        print(
            f"    Bull {bull:2d}% / Bear {40 - bull:2d}%  →  {total:9,.0f}원  "
            f"({total / REPORTED['weighted'] * 100 - 100:+6.1f}%)"
        )
    print("\n  Base 확률만 이동 (Bull:Bear = 1:1):")
    for b in (80, 70, 60, 50, 40):
        sc = copy.deepcopy(SCENARIOS)
        rest = (100 - b) / 2
        sc["Base"]["prob"], sc["Bull"]["prob"], sc["Bear"]["prob"] = b, rest, rest
        print(f"    Base {b:2d}%  →  {weighted(sc):9,.0f}원")


def check_corrections() -> None:
    section("5. 구조 수정 효과 (V1 · V2 · V3)")
    variants = [
        ("현행", dict()),
        ("V2  DLOM 15% 고정", dict(dlom=15)),
        ("V1  NCI를 EV 비례", dict(nci_proportional=True)),
        ("V3  Bull ALC 7.0→6.0x", dict(bull_alc=6.0)),
        ("V1+V2+V3 누적", dict(dlom=15, nci_proportional=True, bull_alc=6.0)),
    ]
    for label, opts in variants:
        sc = copy.deepcopy(SCENARIOS)
        if "bull_alc" in opts:
            sc["Bull"]["multiples"]["ALC"] = opts.pop("bull_alc")
        ratio = NCI / scenario_ev(SCENARIOS["Base"])
        vals = {}
        for name, s in sc.items():
            nci = scenario_ev(s) * ratio if opts.get("nci_proportional") else NCI
            vals[name] = per_share(s, nci, opts.get("dlom"))
        total = sum(vals[n] * sc[n]["prob"] / 100 for n in sc)
        band = vals["Bull"] - vals["Bear"]
        print(
            f"  {label:24s} Base {vals['Base']:8,.0f} | Bull {vals['Bull']:8,.0f} | "
            f"Bear {vals['Bear']:8,.0f} | 가중 {total:8,.0f} | 밴드폭 {band:9,.0f}"
        )

    section("6. 수정 후 장외가 46,500원에 필요한 Bull 확률")
    sc = copy.deepcopy(SCENARIOS)
    sc["Bull"]["multiples"]["ALC"] = 6.0
    ratio = NCI / scenario_ev(SCENARIOS["Base"])
    vals = {n: per_share(s, scenario_ev(s) * ratio, 15) for n, s in sc.items()}
    for bull in range(10, 41, 5):
        total = (
            vals["Base"] * 0.6
            + vals["Bull"] * bull / 100
            + vals["Bear"] * (40 - bull) / 100
        )
        mark = "  ← 장외가" if abs(total - OTC_PRICE) < 2500 else ""
        print(f"    Bull {bull:2d}% / Bear {40 - bull:2d}%  →  {total:9,.0f}원{mark}")


def main() -> None:
    check_reproduction()
    check_da_allocation()
    check_spread_decomposition()
    check_probability_sensitivity()
    check_corrections()
    print()


if __name__ == "__main__":
    main()
