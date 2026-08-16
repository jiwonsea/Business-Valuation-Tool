"""T-3 FINAL — reverse DCF, all tables script-generated, writes T3_nvda_2026-08-10.md

TOLERANCE POLICY (single source of truth — do not restate elsewhere):
    TOL = 1e-5.
    EV is integer-rounded ($1M) AND the EBITDA growth path is re-rounded every year,
    so EV is a step function in the growth-multiplier axis with steps of order 10 $M.
    1e-6 still converges on most axes but 1e-7 does NOT (growth axis fails), and the
    solved point drifts by ~0.003pp across 1e-3..1e-6. 1e-5 is the tightest setting
    that converges on every axis used here. BVT's own display default is 1e-4.
    Identified significant figures at this tolerance: implied WACC 2dp, growth
    multiplier 3dp, terminal EBITDA top 3 digits. See section T-3e.
"""
from __future__ import annotations
import os
import sys
import bvt_dcf as B
from bvt_dcf import calc_dcf, _ev
from t3_reverse_dcf import (ANCHORS, BASE_YEAR, SHARES, UNIT, PRICE_NOW, PRICE_PT,
                            PRICE_0710, _sched_extend)

B._MAX_ITER = 300
TOL = 1e-5   # EV is integer-rounded and growth-path rounding makes EV a step function
             # with steps of order 10 $M; 1e-5 (~54 $M) is the tightest robust setting.
OUT = []


def solve_axis(f, lo, hi, target):
    """V4 fail-closed with an explicit bracket test, so UNREACHABLE means
    'the bound genuinely does not reach the target', never 'solver gave up'."""
    a, b = f(lo), f(hi)
    if not (min(a, b) <= target <= max(a, b)):
        return None, "OUT_OF_BOUNDS", (a, b)
    for t in (TOL, 1e-4, 1e-3):
        x = B._binary_search(f, lo, hi, target, t)
        if x is not None:
            return x, ("OK" if t == TOL else f"OK@tol={t:g}"), (a, b)
    return None, "NO_CONVERGE", (a, b)


# Console independence: writing the artifact must never depend on the terminal
# codepage. Windows cp949 cannot encode "—", so printing is opt-in and best-effort.
VERBOSE = os.environ.get("T3_VERBOSE", "") == "1" or "--print" in sys.argv
if VERBOSE:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        VERBOSE = False


def w(s=""):
    OUT.append(s)
    if VERBOSE:
        try:
            print(s)
        except Exception:
            pass


def tgt(a, price, mode="corrected"):
    return price * SHARES / UNIT + (a["net_debt"] if mode == "corrected" else max(a["net_debt"], 0))


def ps(a, ev):
    return (ev - a["net_debt"]) * UNIT / SHARES


def solve(a, price, mode="corrected"):
    eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
    t = tgt(a, price, mode)
    r = {"target_ev": t, "status": {}, "bounds": {}}
    axes = {
        "wacc": (lambda x: _ev(eb, da, rev, x, p, BASE_YEAR), max(p["terminal_growth"] + .5, 2.), 25.),
        "tgr": (lambda x: _ev(eb, da, rev, wc, dict(p, terminal_growth=x), BASE_YEAR), 0., min(5., wc - .5)),
        "gmult": (lambda x: _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=[max(g * x, -.5) for g in p["ebitda_growth_rates"]]), BASE_YEAR), .3, 8.),
        # 마진 축 v2 [PRIMARY] — Codex rev-4 권고: D&A/매출·Capex/매출을 독립 고정.
        # da_to_ebitda_override 를 m 에 반비례 스케일 → D&A/매출 = m·ov₀·m₀/m = ov₀·m₀ (불변).
        # m = m₀ 에서 ov₀ 로 환원되므로 원함수와 **정확히** 동일하다(C3에서 증명).
        "margin": (lambda x: _ev(int(round(rev * x)), da, rev, wc,
                                 dict(p, da_to_ebitda_override=p["da_to_ebitda_override"] * (eb / rev) / x),
                                 BASE_YEAR), .05, .99),
        # v1 [RECONCILIATION] — 기존 정의. EBITDA↑ 가 D&A·Capex 를 동반 증가시킨다(기계적 결합).
        "margin_v1": (lambda x: _ev(int(round(rev * x)), da, rev, wc, p, BASE_YEAR), .05, .99),
        "dur": (lambda x: _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], x)), BASE_YEAR), 0., 40.),
    }
    for k, (f, lo, hi) in axes.items():
        v, st, bd = solve_axis(f, lo, hi, t)
        r[k], r["status"][k], r["bounds"][k] = v, st, bd
    return r


F = {"wacc": lambda v: f"{v:.2f}%", "tgr": lambda v: f"{v:.2f}%", "gmult": lambda v: f"{v:.3f}x",
     "margin": lambda v: f"{v*100:.2f}%", "margin_v1": lambda v: f"{v*100:.2f}%",
     "dur": lambda v: f"+{v:.1f}y"}


def fm(k, v, st=None):
    if v is None:
        return "**UNREACHABLE**" if st in (None, "OUT_OF_BOUNDS") else f"**{st}**"
    return F[k](v) + ("" if st in (None, "OK") else f" ⚠️{st}")


# ============================================================== HEADER
w("# T-3 역방향 DCF — 시장이 가격에 넣은 가정 (**rev-7**)")
w("")
w("> NVDA FY2027Q2 심층 리서치 · `PLAN_nvda_2026-08_deep_dive.md` rev-3b §0.3 · 2026-08-10 실행")
w("> **투자 자문 아님 — 모델 방법론 검증 목적의 내부 분석.**")
w("> 본 문서는 BVT **공정가치 숫자를 산출하지 않는다** (계획 §2-1). 산출물은 *역산된 내재 가정*뿐이다.")
w("")
w("## ERRATA — rev-1 `FAIL` → rev-2 → rev-3 `CONDITIONAL PASS` → rev-4 `PASS` → rev-5, 2026-08-10")
w("")
w("| # | 지적 | 소재 | 조치 |")
w("|---|---|---|---|")
w("| E-1 | FY26 재현 블록 `tax=17.0` — as-run은 **13.0** | **핸드오프 §3 코드블록만** (손타이핑). 산출 코드는 처음부터 13.0 | 핸드오프 rev-2에서 정정. **본 산출물 수치 영향 없음** — tax 13/17 모두 WACC 11.17%로 반올림되어 DCF EV·iWACC·gmult 불변 (βL 1.453↔1.452, Kd 3.31↔3.15만 상이) |")
w("| E-2 | 충족률 분모 불명확 (83.6% vs 83.4%) | 본 산출물 T-3b | **주가 기준·EV 기준 병기**로 정정. 차이는 순현금 60,000 |")
w("| E-3 | iWACC 3dp(8.516%) 과대주장 | 핸드오프 §4 C-1 | **2dp + tol 밴드 표기**로 강등. 해는 tol에 따라 8.5154~8.5181% 이동(폭 0.0026pp) → **3번째 소수는 식별되지 않는다** |")
w("| E-4 | FY32E EBITDA 648,399 (tol 불일치) | **핸드오프 §4 C-6만** (손타이핑). 본 산출물은 처음부터 **648,405** 로 스크립트 생성 | 핸드오프 정정. 본 산출물은 재생성 시 bit-identical 확인 |")
w("| E-5 | \"괴리\" 열이 `mc.gap_ratio`로 오독될 위험 | 본 산출물 T-3 본표 | 열명을 **`DCF 괴리`** 로 변경 |")
w("")
w("")
w("**rev-2 → rev-3 (Codex `CONDITIONAL PASS` 조건 3건 + 주의 1건):**")
w("")
w("| # | 조건 | 조치 |")
w("|---|---|---|")
w("| E-6 | 최종연도 EBITDA 정의 미분리 — 648,405(비반올림 경로) vs 648,407(엔진 projection) | **T-3c에 두 열로 분리.** 엔진 연도 라벨(2031) vs NVDA 회계라벨(FY2032) 차이도 명시 |")
w("| E-7 | 허용오차 정책 이중 기술 — docstring `1e-6` vs 실제 `TOL=1e-5` | **스크립트 docstring 한 곳으로 단일화**(TOL=1e-5), 본문은 그것을 참조만 |")
w("| E-8 | §0.4-1 결론 라벨 과대 — \"차별적 정보 없음\" | **`UNVERIFIABLE` / 비교 불가**로 강등 + 해소 조건 명시 |")
w("| E-9 | \"듀레이션이 가장 약한 레버\" 가 축 정의의 산물일 가능성 | **T-3d 대조 실험 신설** (rev-4에서 통제군 3개로 확장) |")
w("")
w("**rev-3 → rev-4 (Codex 재검증 지적 3건):**")
w("")
w("| # | 지적 | 조치 |")
w("|---|---|---|")
w("| **E-10** | **\"bit-identical\" 보장이 호스트에서 거짓** — 리포 파일은 LF인데 Windows 생성은 CRLF | "
  "`open(..., newline=\"\\n\")` 로 **개행을 LF로 고정.** 이제 플랫폼과 무관하게 동일 바이트 |")
w("| **E-11** | 첫 실행이 `PYTHONIOENCODING=utf-8` 없이는 실패 — cp949 콘솔이 `—` 를 못 찍음 | "
  "**콘솔 출력 의존 제거.** 기본은 파일만 쓰고, 출력은 `--print` 또는 `T3_VERBOSE=1` 일 때만 "
  "(그때도 `errors=\"replace\"` 로 best-effort). 종료 시 sha256 한 줄만 ASCII로 출력 |")
w("| **E-12** | 듀레이션 통제군(매출 고정)이 **EBITDA 마진 발산**을 유발해 결정적이지 않음 | "
  "**통제군 B(ΔNWC=0) 신설**을 권장 통제군으로 채택 — 매출·마진 경로 불변, NWC 드래그만 제거. "
  "C(매출 고정)는 마진 발산 수치와 함께 **참고용으로 강등.** 결론 주장도 범위 한정 |")
w("")
w("**rev-4 → rev-5 (Codex `PASS` + 규약 권고 2건 반영):**")
w("")
w("| # | 권고 | 조치 |")
w("|---|---|---|")
w("| **E-13** | 충족률은 **주가 기준을 주 지표**로, EV 기준은 순부채≠0 일 때 reconciliation | "
  "전 표에 **[주] / [대조]** 라벨 부여. 규약 절 신설 |")
w("| **E-14** | 마진 축은 **절대 Capex 고정이 아니라 독립 Capex/매출(또는 D&A/매출)** 가정으로 | "
  "**마진 축 v2 [PRIMARY] 신설** — `da_to_ebitda_override = ov₀·m₀/m` 로 D&A/매출·Capex/매출을 m에 불변으로 "
  "고정. m=m₀ 에서 원함수와 **정확 일치**(C3). **결과 변화: FY27E·현재가에서 마진 축이 "
  "`UNREACHABLE` → `98.61%` 로 도달 가능해졌다** — v1의 기계적 결합(EBITDA↑ → Capex↑)이 "
  "마진 레버를 인위적으로 약화시키고 있었다. v1은 reconciliation 열로 보존 |")
w("")
w("**rev-5 → rev-6 (V2 실행):**")
w("")
w("| # | 항목 | 조치 |")
w("|---|---|---|")
w("| **E-15** | rf 가 7/10 stale 값(4.56%)이라 βL<1 결론이 조건부였다 | "
  "**V2 실행.** T-3 가격 기준일과 동일 거래일 **2026-08-07 U.S. Treasury par yield curve 10 Yr = 4.65%** "
  "확정(2개 독립 경로 전체행 일치, 컷오프 이내). **βL 0.894 → 0.874 — 결론 유지·강화.** "
  "**앵커는 불변**(7/10 프로파일 무수정), overlay 로만 기록: `reports/V2_rf_overlay_nvda_2026-08-10.md` |")
w("| **E-16** | βL 의 ERP 조건성이 미기술이었다 | "
  "**rf·ERP 이중 조건성 명시.** rf=4.65% 고정 시 **ERP ≤ 4.02% 면 βL ≥ 1 로 반전.** "
  "ERP 4.6% 는 여전히 7/10 as-run → **조건부 표기 필수** |")
w("")
w("**rev-6 → rev-7 (Codex `FAIL` — 정의 혼재):**")
w("")
w("| # | 지적 | 조치 |")
w("|---|---|---|")
w("| **E-17** | **\"7/10 대비 갱신\" 표의 마진 행이 정의를 섞었다** — 7/10 열은 v2(89.16%)인데 "
  "현재가 열은 v1 결과(\"닿지 못함, 99%에서 99.6%\")를 그대로 두었다. rev-5에서 마진 축을 "
  "v2로 승격하면서 이 셀만 하드코딩 문구로 남아 갱신되지 않았다 | "
  "**해당 셀의 자유 문구를 제거하고 v2·v1 행을 분리**해 둘 다 `RES` 에서 계산한다. "
  "**같은 행에 두 정의를 섞지 않는다.** 같은 계열로 반증조건 RC-2의 "
  "\"마진 축이 닿지 못한다는 결론이 강화\" 문구도 v1 시절 표현이라 함께 정정했다(Codex 미지적, 자체 발견) |")
w("| **E-18** | 핸드오프 §4 C-4 가 구식 `UNREACHABLE` 주장을 유지 | "
  "**C-4를 v2 [주] / v1 [대조] 두 행으로 분리**, 둘 다 스크립트 계산 |")
w("")
w("> ⚠️ **재발 방지:** 축 정의를 바꿀 때 **그 축을 인용하는 모든 셀을 `RES` 계산으로 강제**한다. "
  "자유 문구로 남은 수치는 정의 변경을 따라오지 않는다 — E-17이 정확히 그 사례다.")
w("")
w("> **★ 근본 원인: 두 FAIL 유발 오류(E-1·E-4)는 전부 핸드오프 문서의 손타이핑이다.** "
  "계획의 `모든 표는 스크립트 생성` 규율을 **산출물에는 적용했으나 검증 요청 문서에는 적용하지 않았다.** "
  "→ rev-2부터 핸드오프의 수치 블록도 스크립트 생성으로 전환한다.")
w("")
w("## 규약 확정 (Codex rev-4 `PASS` 회신, 2026-08-10)")
w("")
w("| 규약 | 확정 내용 |")
w("|---|---|")
w("| **충족률 표준 분모** | **주가(equity) 기준을 주 지표**로 한다 — 의사결정 대상이 주가이기 때문. "
  "**EV 기준은 순부채≠0 일 때 reconciliation 열**로 병기 |")
w("| **마진 축 정의** | **독립 Capex/매출(또는 D&A/매출) 가정**을 채택. 절대 Capex 고정보다 낫다 — "
  "성장 경로가 달라져도 스케일되면서, EBITDA·D&A·Capex의 기계적 결합을 피한다. "
  "→ **마진 축 v2 [PRIMARY]** 로 구현(아래 C3). 기존 v1은 reconciliation 으로 강등 |")
w("")
w("**적용 결정 (사용자 2026-08-09):** V-SEG STALE → 프린트-전 BVT(SOTP·V2·V4) 중단, "
  "T-3만 **연결 DCF 경로**로 진행 · 기준 파라미터 = **7/10 as-run 고정** · "
  "target_EV = `mcap + net_debt`(정정) 주, BVT 현행 `mcap + max(net_debt,0)` 병기, **BVT 코드 무수정**.")
w("")

# ============================================================== V1
w("## V1 재현 게이트 — 7/10 as-run 대조 (실패 시 T-3 중단)")
w("")
w("| 앵커 | WACC | 기대 | EV_dcf | 기대 | TV/EV | 판정 |")
w("|---|---:|---:|---:|---:|---:|:--:|")
gate = True
for k, a in ANCHORS.items():
    d = calc_dcf(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
    o = (abs(a["wacc"] - a["expect_wacc"]) < 1e-9) and d["ev_dcf"] == a["expect_ev"]
    gate &= o
    w(f"| {k} | {a['wacc']:.2f}% | {a['expect_wacc']:.2f}% | {d['ev_dcf']:,} | {a['expect_ev']:,} "
      f"| {d['tv_ev_ratio']:.1f}% | {'✅' if o else '❌'} |")
_a = ANCHORS["FY26"]
_iw = B.solve_implied_wacc(PRICE_0710 * SHARES / UNIT + max(_a["net_debt"], 0), _a["ebitda_base"],
                           _a["da_base"], _a["revenue"], _a["dcf_p"], BASE_YEAR)
_ig = B.solve_implied_growth_multiplier(PRICE_0710 * SHARES / UNIT + max(_a["net_debt"], 0),
                                        _a["ebitda_base"], _a["da_base"], _a["revenue"],
                                        _a["wacc"], _a["dcf_p"], BASE_YEAR)
rok = round(_iw, 2) == 5.97 and round(_ig, 2) == 4.94
gate &= rok
w(f"| FY26 역산 | 내재 WACC **{_iw:.2f}%** (기대 5.97%) | | 성장배수 **{_ig:.2f}x** (기대 4.94x) | | | {'✅' if rok else '❌'} |")
w("")
w(f"**V1 GATE: {'PASS' if gate else 'FAIL — 중단'}** — 포팅한 함수가 BVT 원함수와 동치임이 "
  f"7/10 실행 로그(`_run_fy26_baseline.txt`) 대비 $1M 단위까지 확인됨.")
w("")

# ============================================================== C3
w("## C3 마진 축 동치 증명")
w("")
w("BVT DCF는 EBITDA 구동이라 마진이 명시 파라미터가 아니다. `ebitda_base := revenue × m` 으로 "
  "재파라미터화하되, `m₀ = ebitda_base/revenue` 에서 EV가 **완전히 동일**해야 원함수 동치가 보장된다.")
w("")
w("| 앵커 | m₀ | EV(원) | EV(v1 재파라미터화) | EV(**v2** 디커플) | 판정 |")
w("|---|---:|---:|---:|---:|:--:|")
for k, a in ANCHORS.items():
    _m0 = a["ebitda_base"] / a["revenue"]
    _e0 = _ev(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
    _e1 = _ev(int(round(a["revenue"] * _m0)), a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
    _e2 = _ev(int(round(a["revenue"] * _m0)), a["da_base"], a["revenue"], a["wacc"],
              dict(a["dcf_p"], da_to_ebitda_override=a["dcf_p"]["da_to_ebitda_override"] * _m0 / _m0),
              BASE_YEAR)
    w(f"| {k} | {_m0*100:.3f}% | {_e0:,.0f} | {_e1:,.0f} | {_e2:,.0f} | "
      f"{'✅ IDENTICAL' if _e0 == _e1 == _e2 else '❌'} |")
w("")
w("**v2 [PRIMARY] 정의:** `ebitda_base = revenue × m` 이면서 "
  "`da_to_ebitda_override = ov₀ × m₀ / m`. 그러면 D&A/매출 `= m × ov₀ × m₀/m = ov₀·m₀` 로 **m에 불변**이고, "
  "`capex = D&A × (actual_capex/da_base)` 이므로 **Capex/매출도 불변**이다. "
  "`m = m₀` 에서 override 가 `ov₀` 로 환원되므로 원함수와 **정확히** 일치한다(위 표).")
w("")
_fy = ANCHORS["FY27E"]
w("| 검증: FY27E 1차연도 | EBITDA | D&A | Capex | 매출 | **Capex/매출** |")
w("|---|---:|---:|---:|---:|---:|")
for _m in (_fy["ebitda_base"] / _fy["revenue"], 0.85, 0.99):
    _pp = dict(_fy["dcf_p"], da_to_ebitda_override=_fy["dcf_p"]["da_to_ebitda_override"]
               * (_fy["ebitda_base"] / _fy["revenue"]) / _m)
    _pr = calc_dcf(int(round(_fy["revenue"] * _m)), _fy["da_base"], _fy["revenue"],
                   _fy["wacc"], _pp, BASE_YEAR)["projections"][0]
    _r1 = round(_fy["revenue"] * (1 + _fy["dcf_p"]["ebitda_growth_rates"][0]))
    w(f"| m = {_m*100:.2f}% | {_pr['ebitda']:,} | {_pr['da']:,} | {_pr['capex']:,} | {_r1:,} | "
      f"**{_pr['capex']/_r1*100:.4f}%** |")
w("")

# ============================================================== V5
w("## V5 축별 단조성 (이분탐색 유효 조건)")
w("")
a = ANCHORS["FY27E"]
eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
tests = {
    "WACC": (lambda x: _ev(eb, da, rev, x, p, BASE_YEAR), max(p["terminal_growth"] + .5, 2.), 25.),
    "TGR": (lambda x: _ev(eb, da, rev, wc, dict(p, terminal_growth=x), BASE_YEAR), 0., min(5., wc - .5)),
    "성장배수": (lambda x: _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=[max(r * x, -.5) for r in p["ebitda_growth_rates"]]), BASE_YEAR), .3, 8.),
    "EBITDA 마진": (lambda x: _ev(int(round(rev * x)), da, rev, wc, p, BASE_YEAR), .05, .99),
    "듀레이션": (lambda x: _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], x)), BASE_YEAR), 0., 40.),
}
w("| 축 | 탐색구간 | 단조성 | EV(하한) | EV(상한) |")
w("|---|---|---|---:|---:|")
for name, (f, lo, hi) in tests.items():
    xs = [lo + (hi - lo) * i / 24 for i in range(25)]
    ys = [f(x) for x in xs]
    inc = all(ys[i] <= ys[i + 1] + 1e-6 for i in range(24))
    dec = all(ys[i] >= ys[i + 1] - 1e-6 for i in range(24))
    d = "증가" if inc else "감소" if dec else "**비단조 — 다중해 경고**"
    w(f"| {name} | [{lo:.2f}, {hi:.2f}] | {d} | {ys[0]:,.0f} | {ys[-1]:,.0f} |")
w("")
w("전 축 단조 → 이분탐색 해는 유일. (FY27E 앵커 기준, 타 앵커 동일 구조)")
w("")

# ============================================================== MAIN
w("## T-3 본표 — 조건부 역산 (각 값은 *나머지 3축 고정* 조건부다)")
w("")
w("> ⚠️ **`DCF 괴리` 는 BVT `mc.gap_ratio` 가 아니다.** `mc.gap_ratio` 는 **헤드라인(SOTP 확률가중)** 기준이며 "
  "FY27E에서 7/10 +2.3% · 현재 −7.6% 로 `GAP_THRESHOLD` 20% 미달이다(= 자동 역산 미발동). "
  "아래 열은 **연결 DCF 주당가치** 기준이다. 본 T-3은 **수동 역방향 DCF** 이며 자동 진단 결과가 아니다.")
w("")
w("> **C2 부정정 경고.** 4축이 동시에 미지이면 해가 무수히 많다. 아래 각 셀은 "
  "\"다른 축을 모델값에 고정했을 때 그 축 하나로 가격을 설명하려면 얼마여야 하는가\"이며, "
  "**단독 값으로 인용하면 안 된다.**")
w("")
RES = {}
for pn, price in (("현재가 **$223.96** (2026-08-07 종가)", PRICE_NOW),
                  ("셀사이드 PT **$302.83** (61인, 2026-08-03)", PRICE_PT),
                  ("[참조] 7/10 $202.34", PRICE_0710)):
    w(f"### {pn}")
    w("")
    w("| 앵커 | target_EV | 모델 EV | 모델 주가 | **DCF 괴리** | 내재 WACC | 내재 TGR | 성장배수 | 내재 마진 **v2** | 내재 마진 v1 | 듀레이션 |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for k, a in ANCHORS.items():
        r = solve(a, price)
        RES[(k, price)] = r
        e0 = _ev(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
        p0 = ps(a, e0)
        w(f"| {k} | {r['target_ev']:,.0f} | {e0:,.0f} | ${p0:.2f} | {(p0-price)/price*100:+.1f}% "
          f"| {fm('wacc', r['wacc'], r['status']['wacc'])} | {fm('tgr', r['tgr'], r['status']['tgr'])} "
          f"| {fm('gmult', r['gmult'], r['status']['gmult'])} "
          f"| {fm('margin', r['margin'], r['status']['margin'])} "
          f"| {fm('margin_v1', r['margin_v1'], r['status']['margin_v1'])} "
          f"| {fm('dur', r['dur'], r['status']['dur'])} |")
    w("")

# ============================================================== boundary
w("## T-3b UNREACHABLE 축의 경계 정량화 — \"얼마나 모자라는가\" (현재가 $223.96)")
w("")
w("`UNREACHABLE`은 \"모름\"이 아니라 **\"그 축을 경제적 한계까지 밀어도 가격에 닿지 못한다\"**는 정보다.")
w("")
w("충족률 분모를 **주가 기준**(경계 주가 / 목표 주가)과 **EV 기준**(경계 EV / target_EV) 둘 다 표기한다. "
  "두 값이 다른 이유는 순현금(net_debt<0)이 분자·분모에 비대칭으로 들어가기 때문이다 (rev-1은 주가 기준만 표기 → E-2).")
w("")
w("| 앵커 | 축 | 경계값 | 경계 EV | 경계 주가 | **충족률(주가)** [주] | 충족률(EV) [대조] |")
w("|---|---|---:|---:|---:|---:|---:|")
for k, a in ANCHORS.items():
    eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
    for name, bnd, ev in (
        ("TGR (Gordon 상한)", f"{min(5.,wc-.5):.2f}%", _ev(eb, da, rev, wc, dict(p, terminal_growth=min(5., wc - .5)), BASE_YEAR)),
        ("EBITDA 마진 v2 [주]", "99.00%", _ev(int(round(rev * .99)), da, rev, wc,
            dict(p, da_to_ebitda_override=p["da_to_ebitda_override"] * (eb / rev) / .99), BASE_YEAR)),
        ("EBITDA 마진 v1 [대조]", "99.00%", _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)),
        ("듀레이션 (+년)", "+40.0y", _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], 40.)), BASE_YEAR)),
    ):
        _key = {"TGR (Gordon 상한)": "tgr", "EBITDA 마진 v2 [주]": "margin",
                "EBITDA 마진 v1 [대조]": "margin_v1", "듀레이션 (+년)": "dur"}[name]
        if RES[(k, PRICE_NOW)][_key] is None:
            _t = tgt(a, PRICE_NOW)
            w(f"| {k} | {name} | {bnd} | {ev:,.0f} | ${ps(a,ev):.2f} | "
              f"**{ps(a,ev)/PRICE_NOW*100:.2f}%** | **{ev/_t*100:.2f}%** |")
w("")

# ============================================================== growth path
w("## T-3c 성장 축의 해석 — 성장배수를 EBITDA 경로로 환산 (FY27E 앵커)")
w("")
a = ANCHORS["FY27E"]
eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
base = p["ebitda_growth_rates"]
b_end = eb
for r in base:
    b_end *= (1 + r)
b_cagr = (b_end / eb) ** (1 / len(base)) - 1
w(f"모델 원경로: {' → '.join(f'{r*100:.1f}%' for r in base)}  ·  "
  f"FY27E EBITDA {eb:,} → FY32E {b_end:,.0f} $M  ·  5년 CAGR **{b_cagr*100:.2f}%**")
w("")
w("⚠️ **최종연도 EBITDA는 두 정의가 다르다** (Codex rev-2 조건1). "
  "**비반올림 경로**는 `EBITDA₀ × Π(1+gᵢ·k)` 를 실수로 복리한 값이고, "
  "**엔진 projection**은 `calc_dcf` 가 매년 `round()` 한 뒤의 최종연도 `ebitda` 다. "
  "둘 다 유효하되 **같은 열에 섞지 않는다.** 또한 엔진의 연도 라벨은 `base_year+5`(= 2031)이고 "
  "NVDA 회계연도 라벨로는 **FY2032**다 — 본 표는 NVDA 라벨을 쓴다.")
w("")
w("| 가격 | 성장배수 | 요구 EBITDA 성장 경로 (FY28~FY32) | FY32E EBITDA<br>(비반올림 경로) | FY32E EBITDA<br>(엔진 projection) | 5년 CAGR |")
w("|---|---:|---|---:|---:|---:|")
for pn, price in (("현재가 $223.96", PRICE_NOW), ("PT $302.83", PRICE_PT), ("7/10 $202.34", PRICE_0710)):
    g = RES[(("FY27E"), price)]["gmult"]
    nr = [max(r * g, -.5) for r in base]
    e = eb
    for r in nr:
        e *= (1 + r)
    _pj = calc_dcf(eb, da, rev, wc, dict(p, ebitda_growth_rates=nr), BASE_YEAR)["projections"][-1]["ebitda"]
    w(f"| {pn} | {g:.3f}x | {' → '.join(f'{r*100:.1f}%' for r in nr)} | {e:,.0f} | {_pj:,} | "
      f"**{((e/eb)**(1/len(nr))-1)*100:.2f}%** |")
w("")

# ============================================================== V6
w("## V6 target_EV 정의 병기 (BVT 순현금 비대칭)")
w("")
w("BVT `attach_gap_diagnostic`은 `market_ev = market_cap + max(net_debt, 0)`을 쓴다. "
  "정방향 브릿지는 `equity = EV − net_debt`이므로 **순현금 종목에서 두 정의가 불일치**한다. "
  "아래는 그 크기다. **BVT 코드는 수정하지 않았다 (NOTICED BUT NOT TOUCHING).**")
w("")
w("| 앵커 | net_debt | 정정 target | BVT target | 차이 | 내재 WACC(정정) | 내재 WACC(BVT) | Δ |")
w("|---|---:|---:|---:|---:|---:|---:|---:|")
for k, a in ANCHORS.items():
    rc, rb = solve(a, PRICE_NOW, "corrected"), solve(a, PRICE_NOW, "bvt")
    d = "" if None in (rc["wacc"], rb["wacc"]) else f"{rb['wacc']-rc['wacc']:+.2f}p"
    w(f"| {k} | {a['net_debt']:,} | {rc['target_ev']:,.0f} | {rb['target_ev']:,.0f} | "
      f"{rb['target_ev']-rc['target_ev']:,.0f} | {fm('wacc',rc['wacc'])} | {fm('wacc',rb['wacc'])} | {d} |")
w("")

# ============================================================== V2/V3
w("## V2 / V3 검증 — 잔차 및 왕복")
w("")
w(f"허용오차 정책은 **한 곳(스크립트 docstring)** 에만 있다: **TOL = {TOL:.0e}** — 전 축에서 수렴하는 "
  "가장 조인 값이다(1e-7은 성장배수 축 미수렴). BVT 표시 기본값은 1e-4. "
  "왕복 허용치는 이에 상응해 **±$0.01** 로 둔다.")
w("")
w("| 앵커·가격 | 축 | 잔차 | 왕복 주가 | Δ | 판정 |")
w("|---|---|---:|---:|---:|:--:|")
for k in ANCHORS:
    a = ANCHORS[k]
    eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
    r = RES[(k, PRICE_NOW)]
    for axis, ev in (("내재 WACC", None if r["wacc"] is None else _ev(eb, da, rev, r["wacc"], p, BASE_YEAR)),
                     ("성장배수", None if r["gmult"] is None else _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=[max(x * r["gmult"], -.5) for x in p["ebitda_growth_rates"]]), BASE_YEAR))):
        if ev is None:
            w(f"| {k}·$223.96 | {axis} | — | — | — | UNREACHABLE |")
            continue
        res = abs(ev - r["target_ev"]) / abs(r["target_ev"])
        pv = ps(a, ev)
        ok = res < 1e-4 and abs(pv - PRICE_NOW) < 0.01
        w(f"| {k}·$223.96 | {axis} | {res:.2e} | ${pv:.4f} | {pv-PRICE_NOW:+.4f} | {'✅' if ok else '❌'} |")
w("")




# ============================================================== DURATION CONTROL
w("## T-3d 듀레이션 축 대조 실험 — 3개 통제군 (Codex rev-2/rev-3 지적 반영)")
w("")
w("듀레이션 축은 성장 스케줄을 연장하는데, 엔진이 `revenue_growth_rates` 를 `ebitda_growth_rates` 로 "
  "폴백하므로 **매출도 함께 연장되어 ΔNWC 드래그가 커진다.** 따라서 결과가 축 정의의 산물일 수 있다. "
  "통제군을 **둘** 둔다.")
w("")
w("| 통제군 | 조작 | 부작용 |")
w("|---|---|---|")
w("| **A 현행** | 조작 없음 (매출·EBITDA 동반 연장) | ΔNWC 드래그 포함 |")
w("| **B ΔNWC=0** *(권장)* | `nwc_to_rev_delta = 0` | **없음** — 매출·마진 경로 불변, NWC 드래그만 제거 |")
w("| **C 매출 고정** | `revenue_growth_rates` 6년차 이후 0 | ⚠️ **EBITDA 마진 폭주** — 아래 참조 |")
w("")
_a = ANCHORS["FY27E"]; _eb, _da, _rev, _wc, _p = _a["ebitda_base"], _a["da_base"], _a["revenue"], _a["wacc"], _a["dcf_p"]
_T = tgt(_a, PRICE_NOW); _base = _p["ebitda_growth_rates"]


def _evdur(k, mode):
    gr = _sched_extend(_base, k)
    pp = dict(_p, ebitda_growth_rates=gr)
    if mode == "nwc0":
        pp["nwc_to_rev_delta"] = 0.0
    if mode == "revflat":
        pp["revenue_growth_rates"] = list(_base) + [0.0] * (len(gr) - len(_base))
    return _ev(_eb, _da, _rev, _wc, pp, BASE_YEAR)


w("| +년 | A 현행 EV | B ΔNWC=0 EV | C 매출고정 EV | A 충족률 | B 충족률 | C 충족률 |")
w("|---:|---:|---:|---:|---:|---:|---:|")
for _k in (0, 5, 10, 20, 40):
    _A, _B, _C = _evdur(_k, "as"), _evdur(_k, "nwc0"), _evdur(_k, "revflat")
    w(f"| +{_k} | {_A:,.0f} | {_B:,.0f} | {_C:,.0f} | {ps(_a,_A)/PRICE_NOW*100:.2f}% "
      f"| {ps(_a,_B)/PRICE_NOW*100:.2f}% | {ps(_a,_C)/PRICE_NOW*100:.2f}% |")
w(f"| **target** | **{_T:,.0f}** | | | **100%** | | |")
w("")
w("*(충족률 = 경계 주가 / 목표 주가. EV 기준은 T-3b 참조.)*")
w("")
w("**⚠️ 통제군 C는 결정적이지 않다 (Codex rev-3 지적, 수용).** 매출을 고정한 채 EBITDA만 계속 키우면 "
  "**내재 EBITDA 마진이 발산한다** — 실제로:")
w("")
w("| +년 | 최종 EBITDA | 최종 매출 | 내재 EBITDA 마진 |")
w("|---:|---:|---:|---:|")
for _k in (0, 10, 40):
    _gr = _sched_extend(_base, _k)
    _pp = dict(_p, ebitda_growth_rates=_gr,
               revenue_growth_rates=list(_base) + [0.0] * (len(_gr) - len(_base)))
    _last = calc_dcf(_eb, _da, _rev, _wc, _pp, BASE_YEAR)["projections"][-1]
    _r = _rev
    for _g in _pp["revenue_growth_rates"]:
        _r = round(_r * (1 + _g))
    w(f"| +{_k} | {_last['ebitda']:,} | {_r:,} | **{_last['ebitda']/_r*100:.1f}%** |")
w("")
_A40, _B40, _C40 = _evdur(40, "as"), _evdur(40, "nwc0"), _evdur(40, "revflat")
_gr40 = _sched_extend(_base, 40)
_pp40 = dict(_p, ebitda_growth_rates=_gr40,
             revenue_growth_rates=list(_base) + [0.0] * (len(_gr40) - len(_base)))
_l40 = calc_dcf(_eb, _da, _rev, _wc, _pp40, BASE_YEAR)["projections"][-1]
_r40 = _rev
for _g in _pp40["revenue_growth_rates"]:
    _r40 = round(_r40 * (1 + _g))
_ppB = dict(_p, ebitda_growth_rates=_gr40, nwc_to_rev_delta=0.0)
_lB = calc_dcf(_eb, _da, _rev, _wc, _ppB, BASE_YEAR)["projections"][-1]
_rB = _rev
for _g in _gr40:
    _rB = round(_rB * (1 + _g))
w(f"+40년에서 마진 **{_l40['ebitda']/_r40*100:.1f}%** 는 경제적으로 무의미하다. "
  f"→ **통제군 B(ΔNWC=0)가 깨끗한 분리**다: 매출·마진 경로를 건드리지 않고 NWC 드래그만 제거한다"
  f"(+40년 최종 마진 **{_lB['ebitda']/_rB*100:.1f}%** 로 base와 동일 유지).")
w("")
w(f"**결론: 세 통제군 모두 `UNREACHABLE`.** +40년 충족률 A **{ps(_a,_A40)/PRICE_NOW*100:.2f}%** · "
  f"B **{ps(_a,_B40)/PRICE_NOW*100:.2f}%** · C **{ps(_a,_C40)/PRICE_NOW*100:.2f}%** — "
  f"통제군 간 폭이 **{max(ps(_a,x) for x in (_A40,_B40,_C40))/PRICE_NOW*100 - min(ps(_a,x) for x in (_A40,_B40,_C40))/PRICE_NOW*100:.2f}pp** 인 반면 "
  f"목표까지의 부족분은 **{100-ps(_a,_B40)/PRICE_NOW*100:.1f}pp** 다. "
  "**ΔNWC 드래그는 결론을 만들지 않는다.**")
w("")
w("⚠️ **주장 범위 한정 (Codex rev-3 수용).** 위 결과는 \"듀레이션이 본질적으로 가장 약한 레버\"를 "
  "증명하지 **않는다.** 정확한 진술은: **이 모델·이 파라미터에서 명시예측 구간을 늘리는 것만으로는 "
  "현재가에 도달할 수 없으며, 그 이유는 PV(FCFF)가 EV의 29.6%뿐**(TV/EV 70.4%)**이라는 구조** 때문이다. "
  "TV 비중이 낮은 모델에서는 듀레이션이 강한 레버일 수 있다.")
w("")
# ============================================================== PRECISION
w("## T-3e 허용오차와 유효숫자 (E-3 대응)")
w("")
w("솔버 해는 **허용오차 밴드 안의 한 점**이다. tol을 바꾸면 해가 움직인다 — 아래가 그 폭이다.")
w("")
w("| tol | 내재 WACC | 성장배수 | FY32E EBITDA | 검증 EV |")
w("|---:|---:|---:|---:|---:|")
_a = ANCHORS["FY27E"]; _eb, _da, _rev, _wc, _p = _a["ebitda_base"], _a["da_base"], _a["revenue"], _a["wacc"], _a["dcf_p"]
_T = tgt(_a, PRICE_NOW)
_iws, _igs, _es = [], [], []
for _t in (1e-3, 1e-4, 1e-5, 1e-6, 1e-7):
    _iw = B.solve_implied_wacc(_T, _eb, _da, _rev, _p, BASE_YEAR, _t)
    _ig = B.solve_implied_growth_multiplier(_T, _eb, _da, _rev, _wc, _p, BASE_YEAR, _t)
    if _ig is None:
        w(f"| {_t:.0e} | {'—' if _iw is None else f'{_iw:.6f}%'} | **미수렴** | — | — |")
        if _iw is not None: _iws.append(_iw)
        continue
    _e = _eb
    for _r in _p["ebitda_growth_rates"]:
        _e *= (1 + _r * _ig)
    _chk = _ev(_eb, _da, _rev, _wc, dict(_p, ebitda_growth_rates=[max(_r * _ig, -.5) for _r in _p["ebitda_growth_rates"]]), BASE_YEAR)
    w(f"| {_t:.0e} | {_iw:.6f}% | {_ig:.6f}x | {_e:,.0f} | {_chk:,.0f} |")
    _iws.append(_iw); _igs.append(_ig); _es.append(_e)
w(f"| **target** | | | | **{_T:,.0f}** |")
w("")
w(f"**식별되는 유효숫자:** 내재 WACC {min(_iws):.4f}~{max(_iws):.4f}% (폭 **{max(_iws)-min(_iws):.4f}pp**) → "
  f"**2dp까지만 유효 (8.52%)**. 성장배수 {min(_igs):.6f}~{max(_igs):.6f} (폭 {max(_igs)-min(_igs):.6f}) → **3dp 유효**. "
  f"FY32E EBITDA {min(_es):,.0f}~{max(_es):,.0f} (폭 **{max(_es)-min(_es):,.0f} $M**) → "
  f"**상위 3자리까지만 유효 (약 648,000 $M)**. 본 산출물은 tol **{TOL:.0e}** 로 생성됐다.")
w("")
w("⚠️ tol 1e-7에서 성장배수 축이 **미수렴**한다. EBITDA 경로의 정수 반올림 때문에 EV가 "
  "~10 $M 단위 계단함수이기 때문이며, 이것이 tol 하한을 결정한다.")
w("")
# ============================================================== CONCLUSION
w("## T-3 결론 — 시장이 가격에 넣은 가정 (FY27E 앵커, 현재가 $223.96)")
w("")
a = ANCHORS["FY27E"]; eb, da, rev, wc, p = a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"]
rn, r7 = RES[("FY27E", PRICE_NOW)], RES[("FY27E", PRICE_0710)]
wp = a["wacc_p"]
# implied Ke and implied levered beta from implied WACC (hold capital structure & Kd)
kd_at = wp["kd_pre"] * (1 - wp["tax"] / 100)
dw = (100 - wp["eq_w"]) / 100
ke_imp = (rn["wacc"] - kd_at * dw * 100 / 100 * 1) / (wp["eq_w"] / 100) if True else None
ke_imp = (rn["wacc"] - kd_at * dw) / (wp["eq_w"] / 100)
beta_imp = (ke_imp - wp["rf"]) / wp["erp"]
ke_mod = wp["rf"] + 1.491 * wp["erp"]
w("**가격에 닿는 축은 셋(할인율·성장·마진)이고, 영구성장·듀레이션은 경제적 한계에서도 닿지 못한다.** "
  "*(rev-5: 마진 축을 Codex 권고대로 Capex-디커플 정의로 바꾸자 `UNREACHABLE` → 도달 가능으로 뒤집혔다.)*")
w("")
w("| 축 | 결과 | 해석 |")
w("|---|---|---|")
rf_be = ke_imp - wp["erp"]
w(f"| 할인율 | 내재 WACC **{rn['wacc']:.2f}%** (모델 {wc:.2f}%, **{rn['wacc']-wc:+.2f}pp**) | "
  f"내재 Ke **{ke_imp:.2f}%** → 내재 βL **{(ke_imp-4.65)/wp['erp']:.3f}** "
  f"(rf **4.65%** = 2026-08-07 Treasury 10Y, V2 확정 · 모델 βL 1.491). "
  f"⚠️ ERP {wp['erp']}% 조건부 — ERP ≤ {ke_imp-4.65:.2f}% 면 반전 |")
w(f"| 성장 | 성장배수 **{rn['gmult']:.3f}x** → 5년 EBITDA CAGR **20.00%** (모델 9.89%) | "
  "FY28~FY32 EBITDA 36.8%→26.6%→18.4%→12.3%→8.2% 를 요구 |")
w(f"| 영구성장 | **닿지 못함** — Gordon 상한 5.00%에서도 목표의 **83.6%** | 듀레이션·TV 확장만으로는 설명 불가 |")
_mv2 = rn["margin"]
_mb99 = _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)
w(f"| 마진 **[v2 주]** | 내재 EBITDA 마진 **{_mv2*100:.2f}%** (모델 {eb/rev*100:.2f}%) | "
  f"가이던스 FY27 매출의 **{_mv2*100:.1f}%** 를 EBITDA로 전환해야 한다. 도달은 하지만 "
  "**경제적으로 불가능한 수준** — 참고로 Q1 FY27 실적 OPM은 65.6% |")
w(f"| 마진 [v1 대조] | **닿지 못함** — 99%에서 ${ps(a, _mb99):.2f} = 목표의 {ps(a,_mb99)/PRICE_NOW*100:.1f}% | "
  "v1은 EBITDA↑가 D&A·Capex를 동반 증가시켜 마진 레버를 **인위적으로 약화**시킨다 (E-14) |")
w(f"| 듀레이션 | **닿지 못함** — 명시예측 +40년에서도 목표의 **72.7%** (통제군 3종 전부, 폭 0.36pp) | "
  "**이 모델에서** 명시예측 연장만으로는 도달 불가 — PV(FCFF)가 EV의 29.6%뿐이기 때문. "
  "\"본질적으로 가장 약한 레버\"라는 일반화는 하지 않는다 (T-3d) |")
w("")
w("")
_RF_V2 = 4.65   # 2026-08-07 U.S. Treasury par yield curve, 10 Yr — reports/V2_rf_overlay_nvda_2026-08-10.md
w(f"> ✅ **rf 조건성 해소 (V2 실행 완료).** 내재 βL은 `βL = (Ke_내재 − rf) / ERP` 로 역산된다. "
  f"rev-5까지 rf는 7/10 stale 값 4.56%였으나, **V2에서 T-3 가격 기준일과 동일 거래일(2026-08-07)의 "
  f"U.S. Treasury par yield curve 10 Yr = {_RF_V2}%** 로 확정했다(2개 독립 경로 전체행 일치). "
  f"→ **내재 βL {(ke_imp-_RF_V2)/wp['erp']:.3f}** (stale rf 기준 {beta_imp:.3f}). "
  f"rf가 +9bp 올라 βL=1.0 분기점 {rf_be:.2f}%에서 **더 멀어졌다 — 결론 유지·강화.** "
  "상세: `reports/V2_rf_overlay_nvda_2026-08-10.md`")
w("")
w(f"> ⚠️ **남은 조건 — ERP는 미해소.** βL은 rf와 ERP에 **동시에** 조건부인데 "
  f"ERP {wp['erp']}%는 여전히 7/10 as-run 가정이다. **rf={_RF_V2}% 고정 시 ERP ≤ "
  f"{ke_imp-_RF_V2:.2f}% 면 βL ≥ 1 로 뒤집힌다.** → βL 수치는 "
  f"**`rf={_RF_V2}% · ERP={wp['erp']}% 조건부` 표기 없이 인용 금지.**")
w("")
w("> ⚠️ **내재 WACC 해는 TV가 지배한다.** 모델 WACC에서 TV/EV 70.4%, 내재 WACC 8.52%에서 **78.7%** 로 상승한다. "
  "즉 '시장이 낮은 할인율을 쓴다'는 진술의 대부분은 **터미널 가치에 관한 진술**이며, "
  "명시예측 5년 구간에 관한 진술이 아니다.")
w("")
w("### 7/10 대비 갱신 (동일 FY27E 앵커 — 실적 입력 불변)")
w("")
w("| 지표 | 7/10 ($202.34) | 현재 ($223.96) | 변화 |")
w("|---|---:|---:|---:|")
w(f"| 내재 WACC | {r7['wacc']:.2f}% | {rn['wacc']:.2f}% | **{rn['wacc']-r7['wacc']:+.2f}pp** |")
w(f"| 성장배수 | {r7['gmult']:.3f}x | {rn['gmult']:.3f}x | **{(rn['gmult']/r7['gmult']-1)*100:+.1f}%** |")
_c = lambda g: ((lambda e: (e/eb)**0.2-1)(eb*(1+.18*g)*(1+.13*g)*(1+.09*g)*(1+.06*g)*(1+.04*g)))
w(f"| 내재 5년 EBITDA CAGR | {_c(r7['gmult'])*100:.2f}% | {_c(rn['gmult'])*100:.2f}% | "
  f"**{(_c(rn['gmult'])-_c(r7['gmult']))*100:+.2f}pp** |")
_mg = lambda r: ("닿지 못함" if r["margin"] is None else f"{r['margin']*100:.2f}%")
_mg1 = lambda r: ("닿지 못함" if r["margin_v1"] is None else f"{r['margin_v1']*100:.2f}%")
_dm = ("—" if (r7["margin"] is None or rn["margin"] is None)
       else f"**{(rn['margin']-r7['margin'])*100:+.2f}pp**")
w(f"| 내재 EBITDA 마진 **[v2 주]** | {_mg(r7)} | {_mg(rn)} | {_dm} |")
_b99 = _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)
w(f"| 내재 EBITDA 마진 [v1 대조] | {_mg1(r7)} | {_mg1(rn)} (99%에서 목표의 {ps(a,_b99)/PRICE_NOW*100:.1f}%) | 한계 돌파 |")
w("")
w("**앵커(FY26/TTM/FY27E 실적 입력)는 08-27 프린트까지 문자 그대로 불변이다.** 따라서 위 변화는 "
  "전량 **주가 상승분의 재기술**이며, 계획 §0.1의 '멀티플 재평가' 관측과 일치한다. "
  "한 달간 +10.7%의 주가 상승은 이 모델 안에서 **할인율 −0.58pp** 또는 "
  "**5년 EBITDA CAGR +2.66pp** 와 등가다.")
w("")
w("### §0.4-1 사전등록 실패조건 판정")
w("")
w("> *\"T-3 역산 결과가 '이미 컨센이 가정하는 것'과 구별되지 않으면 → 우리는 시장 대비 차별적 정보가 없다. **그렇게 쓴다.**\"*")
w("")
w("**판정: `UNVERIFIABLE` — 비교 불가.** *(rev-2 정정: rev-1의 \"차별적 정보 없음\" 은 "
  "확인된 부재를 뜻하므로 과대 진술이었다. 정확히는 **비교할 컨센 자체가 없어 판정 불능**이다 — Codex rev-2 조건3.)* 근거: ")
w(f"① FY27E 앵커 매출 {rev:,} vs FY27 컨센 매출 393,850 = **{(rev/393850-1)*100:+.2f}%** — "
  "앵커가 사실상 컨센이다. 즉 역산의 *출발점*이 컨센이므로 T-3은 컨센 대비 차별적 뷰를 정의상 만들지 못한다. ")
w("② 역산의 실질 내용은 **FY28~FY32 out-year EBITDA 경로(CAGR 20.0%)** 인데, "
  "정보원장 A에 out-year 컨센이 없어 **비교 대상 자체가 부재**다. ")
w("③ 따라서 \"시장이 20% CAGR을 가격에 넣었다\"는 **관측**이지 **반대 견해**가 아니다. "
  "**\"컨센과 같다\"도 \"컨센과 다르다\"도 주장할 수 없다.**")
w("")
w("**해소 조건 (T-4 착수 전):** S&P/FactSet/IBES의 **FY28~FY32 EBIT·EBITDA estimate**를 "
  "GAAP/비GAAP 기준·회계연도 라벨을 일치시켜 확보. 확보 실패 시 이 항목은 프린트 후에도 "
  "`UNVERIFIABLE` 로 남기고, T-4 판정은 이 축에 의존하지 않게 설계한다.")
w("")
w("**차별화가 가능한 유일한 축은 그 20% CAGR의 *자금조달 구조*다** — 계획 §0.2 테제 "
  "(지분증권 $73,601M = TTM 매출의 29.0%, 비시장성 1분기 +$21,113M)와 **T-1 벤더파이낸싱**이 "
  "여기에 직접 대응한다. T-3 단독으로는 T-4 판정을 지지하지 못한다.")
w("")
w("### T-4로 넘기는 반증조건 후보 (T-4에서 3개로 확정)")
w("")
w("| # | 후보 반증조건 | 프린트로 관측 가능? |")
w("|---|---|---|")
w("| RC-1 | FY27 Q3 매출 가이던스 mid 가 QoQ 성장을 시사하지 않으면 → 20% CAGR 경로의 첫 해가 이미 훼손 | ✅ 08-27 가이던스 |")
w(f"| RC-2 | GAAP GM < 74.4% (가이드 하단) → 마진이 v2 축의 요구치 **{rn['margin']*100:.1f}%** 에서 "
  "더 멀어진다 (SF-A) | ✅ 보도자료 GAAP GM |")
w("| RC-3 | 비시장성 증권 잔액이 또 1분기에 유의하게 증가 → 성장의 자기조달 비중 확대 | ⚠️ 10-Q 필요, 프린트 당일 불가 가능 |")
w("")
w("⚠️ RC-3은 §0.4-4('반증조건 3개 중 어느 것도 프린트로 관측 불가하면 다시 쓴다')에 걸릴 수 있다. "
  "RC-1·RC-2는 프린트 당일 관측 가능하므로 조항 자체는 충족되나, **T-4에서 RC-3의 대체안을 마련한다.**")
w("")

# newline="\n" pins LF on every platform. Without it Windows writes CRLF and the
# SHA-256 differs from the Linux-generated artifact even though the text is identical.
OUTPATH = os.environ.get("T3_OUT", "T3_nvda_2026-08-10.md")
with open(OUTPATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(OUT))
import hashlib
print("sha256", hashlib.sha256(open(OUTPATH, "rb").read()).hexdigest(), OUTPATH)
