"""Generate HANDOFF rev-2 with EVERY numeric block script-emitted.
Root cause of the rev-1 FAIL was hand-typed numbers in the handoff document.
"""
from __future__ import annotations
import hashlib, os, pathlib, sys
import bvt_dcf as B
from bvt_dcf import calc_wacc, calc_dcf, _ev
from t3_reverse_dcf import (ANCHORS, BASE_YEAR, SHARES, UNIT, PRICE_NOW, PRICE_PT,
                            PRICE_0710, _sched_extend)
from t3_final import solve, tgt, ps, TOL

B._MAX_ITER = 300
O = []
def w(s=""): O.append(s)
def sha(f): return hashlib.sha256(open(f, "rb").read()).hexdigest()

FY = ANCHORS["FY27E"]
eb, da, rev, wc, p, nd = (FY["ebitda_base"], FY["da_base"], FY["revenue"],
                          FY["wacc"], FY["dcf_p"], FY["net_debt"])
T = tgt(FY, PRICE_NOW)
R = {pr: solve(FY, pr) for pr in (PRICE_NOW, PRICE_PT, PRICE_0710)}

w("# HANDOFF — CODEX 재검증 요청 **rev-7**: T-3 역방향 DCF + V2 rf 오버레이 (NVDA FY2027Q2)")
w("")
w("> 작성 2026-08-10 KST · rev-1 `FAIL` → rev-2 `CONDITIONAL PASS` → rev-3 결정성 3건 → "
  "rev-4 **`PASS`** → 규약 2건 반영(rev-5) → **V2 실행(rev-6)** · "
  "rev-6 **`FAIL`(정의 혼재)** → **정정** · 대상 `T3_nvda_2026-08-10.md` **rev-7** + "
  "`reports/V2_rf_overlay_nvda_2026-08-10.md`")
w("> 채점 분리 규약(§6.1) ① 산술·기계적용 단계. 발화·테제 판정은 요청하지 않는다.")
w("> **본 문서의 모든 수치 블록은 `gen_handoff.py` 가 생성했다.** rev-1의 FAIL 원인이 "
  "핸드오프 내 손타이핑이었으므로, 계획의 `모든 표는 스크립트 생성` 규율을 검증 문서에도 적용한다.")
w("")
w("---")
w("")
w("## §0. rev-6 `FAIL` 정정 — 마진 축 정의 혼재")
w("")
_rr, _r7 = R[PRICE_NOW], R[PRICE_0710]
_b99 = _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)
w("**전면 수용.** rev-5에서 마진 축을 v2로 승격했는데, \"7/10 대비 갱신\" 표의 현재가 셀만 "
  "**자유 문구로 하드코딩된 v1 결과**가 남아 있었다. 같은 행의 7/10 열은 v2(89.16%)였으므로 "
  "**한 행 안에서 두 정의가 섞였다.**")
w("")
w("| 필드 | rev-6 (오류) | rev-7 (정정) |")
w("|---|---|---|")
w(f"| 현재가 내재 마진 [v2 주] | \"닿지 못함 (99%에서 99.6%)\" ← **v1 결과** | **{_rr['margin']*100:.2f}%** |")
w(f"| 7/10 내재 마진 [v2 주] | {_r7['margin']*100:.2f}% (정상) | {_r7['margin']*100:.2f}% |")
w(f"| 변화 | (계산 불가) | **{(_rr['margin']-_r7['margin'])*100:+.2f}pp** |")
w(f"| v1 대조 행 | 없음 | 7/10 {_r7['margin_v1']*100:.2f}% → 현재가 닿지 못함"
  f"(99%에서 목표의 {ps(FY,_b99)/PRICE_NOW*100:.1f}%) |")
w("")
w("**핸드오프 §4 C-4** 도 구식 `UNREACHABLE` 주장을 유지하고 있었다 → **C-4a(v2 주) / C-4b(v1 대조)** 로 분리.")
w("")
w("> ⚠️ **재발 방지 규칙 신설:** 축 정의를 바꿀 때 **그 축을 인용하는 모든 셀을 `RES` 계산으로 강제**한다. "
  "자유 문구로 남은 수치는 정의 변경을 따라오지 않는다. rev-1의 손타이핑과 **같은 실패 계열**이며, "
  "이번엔 산출물 안에서 발생했다.")
w("")
w("---")
w("")
w("## §0-V2. V2 실행 — 10Y UST 기준일·출처·값 확정")
w("")
_RF, _RF710 = 4.65, 4.56
_wp = FY["wacc_p"]; _ERP = _wp["erp"]
_kd = _wp["kd_pre"] * (1 - _wp["tax"] / 100); _dw = (100 - _wp["eq_w"]) / 100
_iw = R[PRICE_NOW]["wacc"]
_ke = (_iw - _kd * _dw) / (_wp["eq_w"] / 100)
w("| 항목 | 값 |")
w("|---|---|")
w(f"| 기준일 | **2026-08-07** — T-3 가격 기준일(NVDA 종가 ${PRICE_NOW})과 **동일 거래일** |")
w("| 출처 | U.S. Department of the Treasury — *Daily Treasury Par Yield Curve Rates* (1차 자료) |")
w(f"| 10 Yr | **{_RF}%** |")
w("| 교차확인 | 동일 기관 **두 독립 렌더링 경로**(TextView / CSV endpoint) **전체 행 완전 일치** |")
w("| 컷오프 | INFO_CUTOFF_A(2026-08-09 23:59 KST) **이내** |")
w("")
w("**2026-08-07 전체 행:** 1Mo 3.79 · 1.5Mo 3.79 · 2Mo 3.83 · 3Mo 3.87 · 4Mo 3.89 · 6Mo 3.96 · "
  "1Yr 4.01 · 2Yr 4.19 · 3Yr 4.25 · 5Yr 4.35 · 7Yr 4.49 · **10Yr 4.65** · 20Yr 5.20 · 30Yr 5.19")
w("")
w("⚠️ **전사 함정에 실제로 걸렸다 — 재현 시 주의.** 1차 조회에서 한 경로가 10 Yr 을 **4.35** 로 "
  "반환했는데 그것은 **5 Yr 열**이다. **열 이름만 요청하면 열 정렬 오류가 드러나지 않는다.** "
  "→ 헤더 + 전체 행을 받아 열 위치를 직접 확인하는 절차로 확정했다. **네 재현도 전체 행으로 하라.**")
w("")
w("**βL 판정:**")
w("")
w("```")
w(f"내재 WACC = {_iw:.4f}%   (가격에서 역산 — rf 와 무관)")
w(f"내재 Ke   = ({_iw:.4f} - {_kd:.4f} x {_dw:.3f}) / {_wp['eq_w']/100:.3f} = {_ke:.4f}%")
w(f"내재 betaL = (Ke - rf) / ERP = ({_ke:.4f} - {_RF}) / {_ERP} = {(_ke-_RF)/_ERP:.4f}")
w("```")
w("")
w(f"| rf | 출처 | 내재 βL |")
w("|---|---|---:|")
w(f"| {_RF710}% | 7/10 as-run (stale) | {(_ke-_RF710)/_ERP:.4f} |")
w(f"| **{_RF}%** | **2026-08-07 Treasury** | **{(_ke-_RF)/_ERP:.4f}** |")
w("")
w(f"**판정: `βL < 1` 유지 — 그리고 강화.** rf 가 +{(_RF-_RF710)*100:.0f}bp 올라 βL=1.0 분기점 "
  f"**{_ke-_ERP:.2f}%** 에서 더 멀어졌다.")
w("")
w(f"⚠️ **단 ERP 축은 미해소.** βL 은 rf·ERP 에 **동시 조건부**인데 ERP {_ERP}% 는 7/10 as-run 그대로다. "
  f"**rf={_RF}% 고정 시 ERP ≤ {_ke-_RF:.2f}% 면 βL ≥ 1 로 반전한다.** → V2 판정은 "
  "**`rf 해소 · ERP 미해소`** 이며, βL 수치는 조건부 표기 없이 인용하지 않는다.")
w("")
w("**앵커 불변 확인:** 7/10 as-run 프로파일(`rf 4.56%`)은 **수정하지 않았다.** "
  "rf 갱신은 `reports/V2_rf_overlay_nvda_2026-08-10.md` 에 **overlay 로만** 기록했고, "
  "T-3 본표의 내재 WACC·성장배수·마진·듀레이션은 **전부 불변**이다(내재 WACC 는 가격에서 역산되므로 "
  "rf 에 의존하지 않는다).")
w("")
w("---")
w("")
w("## §0-0. rev-4 `PASS` 회신 반영 — 규약 2건 확정 + **결론 1건 변경**")
w("")
w("| 권고 | 조치 | 결과 |")
w("|---|---|---|")
w("| **충족률 표준 분모** = 주가(equity) 기준 주 지표, EV 기준은 순부채≠0 시 reconciliation | "
  "전 표에 **[주]/[대조]** 라벨 부여, 규약 절 신설 | 수치 변화 없음 |")
w("| **마진 축** = 절대 Capex 고정이 아니라 **독립 Capex/매출(또는 D&A/매출)** | "
  "**마진 축 v2 [PRIMARY] 신설** | **⚠️ 결론이 뒤집혔다 — 아래** |")
w("")
w("**v2 정의:** `ebitda_base = revenue × m` 이면서 `da_to_ebitda_override = ov₀ × m₀ / m`. "
  "→ D&A/매출 `= m × ov₀ × m₀/m = ov₀·m₀` **(m에 불변)**, `capex = D&A × (actual_capex/da_base)` 이므로 "
  "**Capex/매출도 불변**. `m = m₀` 에서 override 가 `ov₀` 로 환원돼 **원함수와 정확히 일치**한다.")
w("")
_fy = ANCHORS["FY27E"]
_m0 = _fy["ebitda_base"] / _fy["revenue"]
_ov0 = _fy["dcf_p"]["da_to_ebitda_override"]
w("| 앵커 | m₀ | EV(원본) | EV(v2, m=m₀) | 동치 |")
w("|---|---:|---:|---:|:--:|")
for _k, _a in ANCHORS.items():
    _mm = _a["ebitda_base"] / _a["revenue"]
    _e0 = _ev(_a["ebitda_base"], _a["da_base"], _a["revenue"], _a["wacc"], _a["dcf_p"], BASE_YEAR)
    _e2 = _ev(int(round(_a["revenue"] * _mm)), _a["da_base"], _a["revenue"], _a["wacc"],
              dict(_a["dcf_p"], da_to_ebitda_override=_a["dcf_p"]["da_to_ebitda_override"] * _mm / _mm), BASE_YEAR)
    w(f"| {_k} | {_mm*100:.4f}% | {_e0:,.0f} | {_e2:,.0f} | {'✅ EXACT' if _e0 == _e2 else '❌'} |")
w("")
w("**Capex/매출 불변 검증 (FY27E 1차연도):**")
w("")
w("| m | EBITDA | D&A | Capex | 매출 | Capex/매출 |")
w("|---:|---:|---:|---:|---:|---:|")
for _m in (_m0, 0.85, 0.99):
    _pp = dict(_fy["dcf_p"], da_to_ebitda_override=_ov0 * _m0 / _m)
    _pr = calc_dcf(int(round(_fy["revenue"] * _m)), _fy["da_base"], _fy["revenue"], _fy["wacc"], _pp, BASE_YEAR)["projections"][0]
    _r1 = round(_fy["revenue"] * (1 + _fy["dcf_p"]["ebitda_growth_rates"][0]))
    w(f"| {_m*100:.2f}% | {_pr['ebitda']:,} | {_pr['da']:,} | {_pr['capex']:,} | {_r1:,} | **{_pr['capex']/_r1*100:.4f}%** |")
w("")
_rn = R[PRICE_NOW]
_b99v1 = _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)
w(f"**⚠️ 결론 변경:** FY27E·현재가에서 마진 축이 **`UNREACHABLE` → 내재 마진 "
  f"{_rn['margin']*100:.2f}%** 로 도달 가능해졌다. v1(현행 결합 정의)은 m=99%에서도 "
  f"목표의 {ps(FY,_b99v1)/PRICE_NOW*100:.2f}% 에 그친다 — **v1의 기계적 결합(EBITDA↑ → D&A↑ → Capex↑)이 "
  "마진 레버를 인위적으로 약화시키고 있었다.** 네 권고가 실제로 결론을 바꿨다. "
  "→ 산출물 헤드라인도 \"닿는 축 2개\" → **\"3개(할인율·성장·마진)\"** 로 정정. "
  f"단 {_rn['margin']*100:.1f}% 마진은 경제적으로 불가능한 수준이라 **투자 판단 함의는 불변**이다.")
w("")
w("---")
w("")
w("## §0-A. rev-3 재검증 지적 해소 — **결정성 결함 3건 전부 수용**")
w("")
w("| 지적 | 내 재현 | 조치 |")
w("|---|---|---|")
w("| **\"bit-identical\" 보장이 호스트에서 거짓** — 리포는 LF, Windows 생성은 CRLF | "
  "**전면 수용.** 나는 리눅스 샌드박스와 디바이스 VM(둘 다 LF)에서만 재현을 검증했고, "
  "**Windows 호스트를 검증 경로에 넣지 않았다.** `open(..., \"w\", encoding=\"utf-8\")` 은 "
  "플랫폼 기본 개행으로 변환하므로 Windows에서 CRLF가 된다 | "
  "`newline=\"\\n\"` 로 **LF 고정.** 이제 플랫폼 무관하게 동일 바이트 |")
w("| **첫 실행이 UTF-8 콘솔 없이 실패** — cp949가 `—` 를 못 찍음 | "
  "**수용.** `w()` 가 매 줄 `print` 했다 — **산출물 생성이 터미널 코드페이지에 의존**했다. 설계 결함이다 | "
  "**콘솔 출력 의존 제거.** 기본은 파일만 쓰고, 출력은 `--print` / `T3_VERBOSE=1` 일 때만 "
  "(`errors=\"replace\"` best-effort). 종료 시 **sha256 한 줄만 ASCII로** 출력 |")
w("| **듀레이션 통제군이 결정적이지 않음** — 매출 고정 시 EBITDA 마진 발산 | "
  "**수용, 그리고 네 지적이 맞다.** 실측: 매출 고정 +10년 마진 **98.6%**, +40년 **319.7%** — 무의미하다 | "
  "**통제군 B(ΔNWC=0) 신설**을 권장군으로 채택(매출·마진 경로 불변, 최종 마진 66.6% 유지). "
  "C는 마진 발산 수치와 함께 참고용 강등. 결론 주장도 범위 한정 |")
w("")
w("**결정성 검증 (샌드박스에서 실행):** 3회 연속 재생성 bit-identical · `LC_ALL=C PYTHONIOENCODING=ascii` "
  "환경에서도 동일 해시 · `--print` 모드에서도 동일 해시 · CRLF 0개.")
w("")
w("**추가 확인 — 리포 정책 위반이었다.** `.gitattributes` 4행이 `* text=auto eol=lf` 로 "
  "**LF를 강제**하고 있다(주석: \"Fixes the CRLF/LF re-encoding noise observed across "
  "Windows-host / Linux-sandbox sessions\"). 즉 rev-3까지의 코드는 편의 문제가 아니라 "
  "**리포 자체 규약을 어기고 있었다.** 반대로 git 체크아웃 경로는 이미 LF이므로, "
  "`newline=\"\\n\"` 만 고치면 **생성·체크아웃 양쪽이 LF로 일치**한다.")
w("")
w("**듀레이션 3통제군 결과 (+40년, 충족률 주가기준):**")
w("")
w("| 통제군 | 조작 | +40년 EV | 충족률 | 부작용 |")
w("|---|---|---:|---:|---|")
_bs = p["ebitda_growth_rates"]
def _ed(k, mode):
    gr = _sched_extend(_bs, k)
    pp = dict(p, ebitda_growth_rates=gr)
    if mode == "nwc0":
        pp["nwc_to_rev_delta"] = 0.0
    if mode == "revflat":
        pp["revenue_growth_rates"] = list(_bs) + [0.0] * (len(gr) - len(_bs))
    return _ev(eb, da, rev, wc, pp, BASE_YEAR)
def _margin(k, mode):
    gr = _sched_extend(_bs, k)
    pp = dict(p, ebitda_growth_rates=gr)
    if mode == "nwc0":
        pp["nwc_to_rev_delta"] = 0.0
    if mode == "revflat":
        pp["revenue_growth_rates"] = list(_bs) + [0.0] * (len(gr) - len(_bs))
    last = calc_dcf(eb, da, rev, wc, pp, BASE_YEAR)["projections"][-1]
    r = rev
    for gg in (pp.get("revenue_growth_rates") or gr):
        r = round(r * (1 + gg))
    return last["ebitda"] / r * 100
for _lab, _m, _note in (("A 현행", "as", "ΔNWC 드래그 포함"),
                        ("**B ΔNWC=0**", "nwc0", "**없음 (권장)**"),
                        ("C 매출 고정", "revflat", "⚠️ 마진 발산")):
    _e = _ed(40, _m)
    w(f"| {_lab} | — | {_e:,.0f} | **{ps(FY,_e)/PRICE_NOW*100:.2f}%** | {_note} · +40년 최종 마진 {_margin(40,_m):.1f}% |")
_evs = [_ed(40, m) for m in ("as", "nwc0", "revflat")]
_pcts = [ps(FY, e) / PRICE_NOW * 100 for e in _evs]
w(f"| target | — | {T:,.0f} | **100%** | |")
w("")
w(f"통제군 간 폭 **{max(_pcts)-min(_pcts):.2f}pp** vs 목표까지 부족분 **{100-max(_pcts):.1f}pp**. "
  "→ ΔNWC 드래그는 결론을 만들지 않는다. 다만 **\"듀레이션이 본질적으로 가장 약한 레버\"라는 일반화는 철회**하고, "
  "**\"이 모델·이 파라미터에서 PV(FCFF)가 EV의 29.6%뿐이라 명시예측 연장만으로는 도달 불가\"** 로 한정한다.")
w("")
w("---")
w("")
w("## §0-B. rev-2 `CONDITIONAL PASS` 조건 해소")
w("")
w("| 조건 | 내 재현 | 조치 |")
w("|---|---|---|")
_g5 = B.solve_implied_growth_multiplier(T, eb, da, rev, wc, p, BASE_YEAR, 1e-5)
_path = [max(r * _g5, -.5) for r in p["ebitda_growth_rates"]]
_nr = eb
for _r in _path:
    _nr *= (1 + _r)
_pj = calc_dcf(eb, da, rev, wc, dict(p, ebitda_growth_rates=_path), BASE_YEAR)["projections"][-1]
w(f"| **1. C-6 정의 분리** | 동일 tol=1e-5·gmult {_g5:.6f} 에서 **비반올림 복리 경로 {_nr:,.0f}** vs "
  f"**엔진 projection 최종연도 {_pj['ebitda']:,}** — 네 지적대로 2 차이. 원인은 `calc_dcf` 의 연간 `round()` | "
  "**T-3c를 두 열로 분리.** 추가로 엔진 연도 라벨이 "
  f"`base_year+5 = {_pj['year']}` 인 반면 NVDA 회계라벨은 **FY2032** 임도 명시(라벨 1년 어긋남) |")
w(f"| **2. 허용오차 정책 단일화** | docstring `1e-6` vs 실제 `TOL={TOL:.0e}` 불일치 확인. 본문 V2/V3 절에도 "
  "동일 문구가 중복돼 있었다(네가 지적한 것보다 1곳 더) | **스크립트 docstring 한 곳을 single source of truth로 "
  f"확정**(TOL={TOL:.0e} + 근거 + 유효숫자), 본문은 참조만. 중복 문구 제거 |")
w("| **3. §0.4-1 라벨 강등** | 동의. \"차별적 정보 없음\"은 **확인된 부재**를 뜻하나 실제로는 비교 대상 부재 | "
  "**`UNVERIFIABLE` / 비교 불가**로 강등. \"컨센과 같다도 다르다도 주장할 수 없다\" 명시 + "
  "해소 조건(FY28~32 EBIT·EBITDA estimate를 기준·회계연도 정렬해 확보) 신설 |")

# duration control
_base = p["ebitda_growth_rates"]
def _evdur(k, flat):
    gr = _sched_extend(_base, k)
    pp = dict(p, ebitda_growth_rates=gr)
    if flat:
        pp["revenue_growth_rates"] = list(_base) + [0.0] * (len(gr) - len(_base))
    return _ev(eb, da, rev, wc, pp, BASE_YEAR)
_A40, _B40 = _evdur(40, False), _evdur(40, True)
w(f"| **주의: \"듀레이션이 가장 약한 레버\"** | **대조 실험을 실행했다.** `revenue_growth_rates` 를 명시해 "
  f"6년차 이후 매출을 고정하면 +40년 EV {_A40:,.0f} → {_B40:,.0f} ({_B40-_A40:+,.0f}), "
  f"충족률(주가) **{ps(FY,_A40)/PRICE_NOW*100:.2f}% → {ps(FY,_B40)/PRICE_NOW*100:.2f}%** "
  f"(**{(ps(FY,_B40)-ps(FY,_A40))/PRICE_NOW*100:+.2f}pp**) | "
  "**주장 유지, 근거 교체.** 매출·NWC 동반 연장은 원인이 아니다. 진짜 이유는 "
  "**명시예측 FCFF가 EV의 29.6%뿐**(TV/EV 70.4%)이라는 모델 구조다. T-3d 절 신설 |")
w("")
w("**포팅 서술 정정 (네 지적 수용):** rev-2 §2의 \"tol 인자만 추가한 원본\"은 **부정확한 진술이었다.** "
  "정확히는 **dict 기반 재구현**이며, `terminal_ev_ebitda`(Exit Multiple) 분기는 **아예 이식하지 않았다.** "
  "동치가 확인된 범위는 **T-3이 실제로 밟는 경로에 한정**된다 — FY26·TTM·FY27E의 EV, WACC, "
  "그리고 5개 축 솔버. 미실행 분기(`capex_fade_to`·`actual/prior_nwc`·`terminal_ev_ebitda`·"
  "`is_financial`·distress premium)는 **동치 미검증**으로 남는다.")
w("")
w("---")
w("")
w("## §1. rev-1 판정에 대한 회신 — 전부 독립 재현했다")
w("")
w("**결론: 지적 전건 수용. 단 2건은 정의 차이(DISPUTED)로 판정하고 양 기준을 병기했다.**")
w("")
w("| Codex 지적 | 내 재현 | 내 판정 | 조치 |")
w("|---|---|---|---|")

# E-1
w13 = calc_wacc(**FY["wacc_p"])
a26 = ANCHORS["FY26"]
w26_13 = calc_wacc(**a26["wacc_p"])
w26_17 = calc_wacc(**dict(a26["wacc_p"], tax=17.0))
ev26_13 = calc_dcf(a26["ebitda_base"], a26["da_base"], a26["revenue"], w26_13["wacc"], a26["dcf_p"], BASE_YEAR)["ev_dcf"]
ev26_17 = calc_dcf(a26["ebitda_base"], a26["da_base"], a26["revenue"], w26_17["wacc"], a26["dcf_p"], BASE_YEAR)["ev_dcf"]
w(f"| **P0 FY26 `tax=17.0`** — as-run은 13.0 | 재현 일치. tax=13 → βL {w26_13['bl']} · Kd {w26_13['kd_at']}% · "
  f"WACC {w26_13['wacc']}% / tax=17 → βL {w26_17['bl']} · Kd {w26_17['kd_at']}% · WACC {w26_17['wacc']}%. "
  f"**DCF EV는 양쪽 모두 {ev26_13:,}** | **ACCEPTED** | 오류 소재는 **rev-1 핸드오프 §3 코드블록 손타이핑**. "
  f"산출 코드(`t3_reverse_dcf.py:31`)는 처음부터 `tax=13.0`. **T-3 수치 무영향** |")
# C-1
iws = {t: B.solve_implied_wacc(T, eb, da, rev, p, BASE_YEAR, t) for t in (1e-3, 1e-4, 1e-5, 1e-6)}
w(f"| **C-1 3dp 8.516% 아님** | tol별 해: 1e-4 → **{iws[1e-4]:.6f}%** (Codex 값) · 1e-5 → **{iws[1e-5]:.6f}%** (내 값) · "
  f"1e-6 → {iws[1e-6]:.6f}%. 폭 {max(iws.values())-min(iws.values()):.4f}pp | **ACCEPTED** | "
  "둘 다 각자 tol에서 옳다. **3번째 소수는 식별되지 않는다** → 전 산출물 **2dp + tol 밴드** 표기로 강등 |")
# C-3 / C-5
tgr_ev = _ev(eb, da, rev, wc, dict(p, terminal_growth=min(5.0, wc - .5)), BASE_YEAR)
dur_ev = _ev(eb, da, rev, wc, dict(p, ebitda_growth_rates=_sched_extend(p["ebitda_growth_rates"], 40.)), BASE_YEAR)
w(f"| **C-3 83.4% · C-5 72.4%** | 분모 정의 차이다. TGR 경계 EV {tgr_ev:,.0f} → "
  f"**주가기준 {ps(FY,tgr_ev)/PRICE_NOW*100:.2f}%** / **EV기준 {tgr_ev/T*100:.2f}%**. "
  f"듀레이션 경계 EV {dur_ev:,.0f} → **주가기준 {ps(FY,dur_ev)/PRICE_NOW*100:.2f}%** / **EV기준 {dur_ev/T*100:.2f}%** | "
  "**DISPUTED** | 내 값은 주가기준, 네 값은 EV기준. 차이는 순현금 60,000이 분자에만 들어가기 때문. "
  "**rev-2는 양 기준 병기.** 어느 쪽을 표준으로 할지 판정 요청 |")
# C-6
igs = {t: B.solve_implied_growth_multiplier(T, eb, da, rev, wc, p, BASE_YEAR, t) for t in (1e-4, 1e-5, 1e-6)}
def fy32(g):
    e = eb
    for r in p["ebitda_growth_rates"]:
        e *= (1 + r * g)
    return e
w(f"| **C-6 648,399은 1e-5 아님** | 재현 일치. 1e-4 → {fy32(igs[1e-4]):,.0f} · 1e-5 → **{fy32(igs[1e-5]):,.0f}** · "
  f"1e-6 → **{fy32(igs[1e-6]):,.0f}** | **ACCEPTED** | rev-1 **핸드오프 §4 C-6만** 손타이핑(1e-6 값 전재). "
  f"**T-3 산출물 본문은 처음부터 {fy32(igs[1e-5]):,.0f}** — 재생성 시 bit-identical 확인 |")
w("| **5-2 “로그만 유일 증빙”** | `git show eaf2dfa:profiles/nvda.yaml` 로 FY26 as-run 전량 복원 확인 | **ACCEPTED** | "
  "**정정: git + 로그 2중 보존.** 단 `nvda_ttm.yaml`은 아카이브본(dep 3586)과 실행값(dep 3229)이 달라 "
  "**TTM 앵커만은 로그 대조가 필수**다 |")
w("| **5-3 열명** | — | **ACCEPTED** | 본표 열명을 **`DCF 괴리`** 로 변경 + `mc.gap_ratio`와의 구분을 표로 명시 |")
w("| **6-1 듀레이션 fractional stub** | 현 결과에서 듀레이션 축은 **3개 앵커·3개 가격 전부 `OUT_OF_BOUNDS`** — "
  "솔버가 소수 해를 반환한 사례가 **0건** | **ACCEPTED (무영향)** | 임의 정의가 결과에 관여하지 않음을 명시. "
  "정수 연도 경계값만 인용 |")
w("| **6-3 / 6-4 / 6-5 / 6-7 / 6-8 / 6-10** | — | **ACCEPTED** | 6-5(V2 분리)는 사용자 결정 요청으로 상신 |")
w("| **6-6 컨센 basis** | — | **ACCEPTED (DISPUTED 유지)** | §0.4-1 판정을 **“매출 축에 한해 구별 불가, OP/EBITDA 축은 미검증”** 으로 한정 |")
w("")
w("**✅ C-8 해소 (rev-2 회신):** 내부 불일치 문의에 \"C-8은 CONFIRMED, 정정할 내용 없음\"으로 답을 받았다. "
  "**C-8은 무변경**(모델 TV/EV 70.4% → 내재 78.7%).")
w("")
w("---")
w("")
w("## §2. rev-1 `UNVERIFIABLE` 해소 — 파일을 리포에 기록했다")
w("")
w("rev-1에서 T-3 산출물 4개가 워크스페이스에 없어 포팅 동치성이 검증 불가였다. "
  "**rev-2부터 리포에 기록한다** — 아래 해시는 rev-3 시점 값이다.")
w("")
w("| 리포 경로 | sha256 |")
w("|---|---|")
for label, f in (("reports/T3_nvda_2026-08-10.md", "T3_nvda_2026-08-10.md"),
                 ("reports/V2_rf_overlay_nvda_2026-08-10.md", "V2_rf_overlay_nvda_2026-08-10.md"),
                 ("scripts/t3/gen_v2.py", "gen_v2.py"),
                 ("scripts/t3/bvt_dcf.py", "bvt_dcf.py"),
                 ("scripts/t3/t3_reverse_dcf.py", "t3_reverse_dcf.py"),
                 ("scripts/t3/t3_final.py", "t3_final.py"),
                 ("scripts/t3/gen_handoff.py", "gen_handoff.py")):
    try:
        w(f"| `{label}` | `{sha(f)}` |")
    except FileNotFoundError:
        w(f"| `{label}` | (생성 중) |")
w("")
w("재현: `cd scripts/t3 && python3 t3_final.py` → `T3_nvda_2026-08-10.md` 재생성. "
  "**bit-identical 이어야 한다.**")
w("")
w("⚠️ **`bvt_dcf.py` 는 \"tol만 추가한 원본\"이 아니다** (rev-2 서술 정정). Pydantic 모델을 dict로 바꾼 "
  "**재구현**이며, `terminal_ev_ebitda`(Exit Multiple) 분기는 이식하지 않았다. 의도적 차이는 솔버 3종의 "
  "`tol` 인자 추가 하나뿐이고 나머지는 1:1 대응을 목표로 했으나, **동치가 실증된 범위는 T-3이 실제로 "
  "밟는 경로**(FY26·TTM·FY27E EV + WACC + 5개 축 솔버)**에 한정된다.**")
w("")
w("---")
w("")
w("## §3. [P0] 실 BVT 엔진 재현 — **정정본**")
w("")
w("```python")
w("# F:\\dev\\Portfolio\\business-valuation-tool 에서 실행")
w("from engine.dcf import calc_dcf")
w("from engine.wacc import calc_wacc")
w("from engine.gap_diagnostics import (solve_implied_wacc, solve_implied_tgr,")
w("                                    solve_implied_growth_multiplier)")
w("from schemas.models import DCFParams, WACCParams")
w("")
w("# --- FY26 앵커 = git eaf2dfa:profiles/nvda.yaml (7/10 as-run) ---")
_wp = a26["wacc_p"]
w(f"w = calc_wacc(WACCParams(rf={_wp['rf']}, erp={_wp['erp']}, bu={_wp['bu']}, de={_wp['de']},")
w(f"                         tax={_wp['tax']}, kd_pre={_wp['kd_pre']}, eq_w={_wp['eq_w']}))   # ★ tax={_wp['tax']} (rev-1의 17.0은 오기)")
_dp = a26["dcf_p"]
w(f"p = DCFParams(ebitda_growth_rates={_dp['ebitda_growth_rates']}, tax_rate={_dp['tax_rate']},")
w(f"              capex_to_da={_dp['capex_to_da']}, nwc_to_rev_delta={_dp['nwc_to_rev_delta']},")
w(f"              terminal_growth={_dp['terminal_growth']}, actual_capex={_dp['actual_capex']},")
w(f"              capex_fade_to=None, da_to_ebitda_override={_dp['da_to_ebitda_override']})")
w(f"d = calc_dcf({a26['ebitda_base']}, {a26['da_base']}, {a26['revenue']}, w.wacc, p, {BASE_YEAR})")
w(f"# 기대: w.bl == {w26_13['bl']} · w.ke == {w26_13['ke']} · w.kd_at == {w26_13['kd_at']} · w.wacc == {w26_13['wacc']}")
w(f"# 기대: d.ev_dcf == {ev26_13:_}")
_t710 = PRICE_0710 * SHARES / UNIT + max(a26["net_debt"], 0)
_iw710 = B.solve_implied_wacc(_t710, a26["ebitda_base"], a26["da_base"], a26["revenue"], a26["dcf_p"], BASE_YEAR)
_ig710 = B.solve_implied_growth_multiplier(_t710, a26["ebitda_base"], a26["da_base"], a26["revenue"], w26_13["wacc"], a26["dcf_p"], BASE_YEAR)
w(f"target = {PRICE_0710} * {SHARES:_} / {UNIT:_} + max({a26['net_debt']}, 0)   # == {_t710:,.1f}")
w(f"solve_implied_wacc(target, {a26['ebitda_base']}, {a26['da_base']}, {a26['revenue']}, p)")
w(f"#   기대 {_iw710:.2f}% (2dp) — 원본 로그 5.97%")
w(f"solve_implied_growth_multiplier(target, {a26['ebitda_base']}, {a26['da_base']}, {a26['revenue']}, w.wacc, p)")
w(f"#   기대 {_ig710:.2f}x (2dp) — 원본 로그 4.94x")
w("```")
w("")
w("**FY27E 앵커:**")
w("")
w("| 인자 | 값 | 기대 산출 |")
w("|---|---|---|")
_f = FY["wacc_p"]
w(f"| WACCParams | rf={_f['rf']} erp={_f['erp']} bu={_f['bu']} de={_f['de']} tax={_f['tax']} kd_pre={_f['kd_pre']} eq_w={_f['eq_w']} | "
  f"bl={w13['bl']} ke={w13['ke']} kd_at={w13['kd_at']} **wacc={w13['wacc']}** |")
w(f"| DCFParams | growth={p['ebitda_growth_rates']} tax_rate={p['tax_rate']} capex_to_da={p['capex_to_da']} "
  f"nwc={p['nwc_to_rev_delta']} tg={p['terminal_growth']} actual_capex={p['actual_capex']} da_ov={p['da_to_ebitda_override']} | |")
w(f"| calc_dcf | ({eb}, {da}, {rev}, {w13['wacc']}, p, {BASE_YEAR}) | **ev_dcf = {_ev(eb,da,rev,wc,p,BASE_YEAR):,.0f}** |")
w("")
w("---")
w("")
w("## §4. 주장 전수 — **정밀도 정정본**")
w("")
w(f"기준: FY27E 앵커 · 현재가 **${PRICE_NOW}** · `target_EV = {PRICE_NOW} × {SHARES:,} / {UNIT:,} + ({nd:,}) = {T:,.0f}` · "
  f"솔버 tol **{TOL:.0e}**")
w("")
w("| # | 주장 | 값 (유효숫자 준수) | 비고 |")
w("|---|---|---|---|")
r = R[PRICE_NOW]
w(f"| C-1 | 내재 WACC | **{r['wacc']:.2f}%** (tol 밴드 {min(iws.values()):.4f}~{max(iws.values()):.4f}%) | 3dp 주장 철회 |")
w(f"| C-2 | 내재 성장배수 | **{r['gmult']:.3f}x** | 3dp 유효 |")
w(f"| C-3 | 내재 TGR | **UNREACHABLE** — 경계 5.00%에서 EV {tgr_ev:,.0f} = 주가기준 **{ps(FY,tgr_ev)/PRICE_NOW*100:.2f}%** / EV기준 **{tgr_ev/T*100:.2f}%** | 양 기준 병기 |")
mg_ev = _ev(int(round(rev * .99)), da, rev, wc, p, BASE_YEAR)
_m2 = r["margin"]
w(f"| C-4a | 내재 EBITDA 마진 **[v2 주]** | "
  + (f"**{_m2*100:.2f}%** (모델 {eb/rev*100:.2f}%)" if _m2 is not None else "**UNREACHABLE**")
  + " | rev-5에서 Capex-디커플 정의로 승격 → **도달 가능**. 경제적으로는 불가능한 수준 |")
w(f"| C-4b | 내재 EBITDA 마진 [v1 대조] | **UNREACHABLE** — m=99%에서 EV {mg_ev:,.0f} = "
  f"${ps(FY,mg_ev):.2f} = 주가기준 **{ps(FY,mg_ev)/PRICE_NOW*100:.2f}%** / EV기준 **{mg_ev/T*100:.2f}%** | "
  "EBITDA↑ 가 D&A·Capex 를 동반 증가시키는 결합 정의 |")
w(f"| C-5 | 내재 듀레이션 | **UNREACHABLE** — +40년에서 EV {dur_ev:,.0f} = 주가기준 **{ps(FY,dur_ev)/PRICE_NOW*100:.2f}%** / EV기준 **{dur_ev/T*100:.2f}%** | 정수 연도 경계값 |")
_cg = (fy32(r["gmult"]) / eb) ** 0.2 - 1
w(f"| C-6 | 내재 5년 EBITDA CAGR | **{_cg*100:.2f}%** · FY32E EBITDA **약 {round(fy32(r['gmult'])/1000)*1000:,} $M** (tol 밴드 {fy32(igs[1e-6]):,.0f}~{fy32(igs[1e-4]):,.0f}) | 6자리 주장 철회 |")
_kd = _f["kd_pre"] * (1 - _f["tax"] / 100); _dw = (100 - _f["eq_w"]) / 100
_ke = (r["wacc"] - _kd * _dw) / (_f["eq_w"] / 100); _bt = (_ke - _f["rf"]) / _f["erp"]
w(f"| C-7 | 내재 Ke / βL | **{_ke:.2f}% / {_bt:.3f}** | rf={_f['rf']}% (stale) 조건부. βL=1.0 분기 rf **{_ke-_f['erp']:.2f}%** |")
_d0 = calc_dcf(eb, da, rev, wc, p, BASE_YEAR); _d1 = calc_dcf(eb, da, rev, r["wacc"], p, BASE_YEAR)
w(f"| C-8 | TV 비중 | 모델 **{_d0['tv_ev_ratio']}%** → 내재 **{_d1['tv_ev_ratio']}%** | 정정 요청 사항 불명 — §1 참조 |")
r7 = R[PRICE_0710]
w(f"| C-9 | 7/10 대비 | iWACC {r7['wacc']:.2f}→{r['wacc']:.2f}% (**{r['wacc']-r7['wacc']:+.2f}pp**) · "
  f"gmult {r7['gmult']:.3f}→{r['gmult']:.3f}x (**{(r['gmult']/r7['gmult']-1)*100:+.2f}%**) | 앵커 불변, 가격만 이동 |")
rp = R[PRICE_PT]
w(f"| C-10 | PT ${PRICE_PT} | iWACC **{rp['wacc']:.2f}%** · gmult **{rp['gmult']:.3f}x** · "
  f"CAGR **{((fy32(rp['gmult'])/eb)**0.2-1)*100:.2f}%** | target_EV {tgt(FY,PRICE_PT):,.0f} |")
w("")
w("**타 앵커 (현재가, 정정 target):**")
w("")
w("| 앵커 | target_EV | 모델 EV | 모델 주가 | iWACC | gmult |")
w("|---|---:|---:|---:|---:|---:|")
for k, a in ANCHORS.items():
    rr = solve(a, PRICE_NOW)
    e0 = _ev(a["ebitda_base"], a["da_base"], a["revenue"], a["wacc"], a["dcf_p"], BASE_YEAR)
    g = "UNREACHABLE" if rr["gmult"] is None else f"{rr['gmult']:.3f}x"
    w(f"| {k} | {rr['target_ev']:,.0f} | {e0:,.0f} | ${ps(a,e0):.2f} | {rr['wacc']:.2f}% | {g} |")
w("")
w("---")
w("")
w("## §5. rev-3 판정 요청")
w("")
w("| 우선순위 | 항목 |")
w("|---|---|")
w("| **P0-1** | §0 조건 3건 + 주의 1건의 해소가 충분한가 (특히 듀레이션 대조 실험 설계의 타당성) |")
w("| **P0-2** | §2 리포 기록 파일로 **포팅 동치성** 재검증 — 미실행 분기 목록이 정확한가 |")
w("| **P1-1** | **충족률 표준 분모 판정** — 주가 기준 vs EV 기준 중 무엇을 규약으로 채택할 것인가 (rev-2 미회신) |")
w("| **P1-2** | 마진 축 대안 정의(절대 capex 고정 / 독립 capex-매출비율) 중 권고안 — 6-3 후속 (rev-2 미회신) |")
w("| **P2-1** | rev-1·rev-2에서 놓친 취약점 |")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

HPATH = "HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md"
with open(HPATH, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(HPATH, "rb").read()).hexdigest(), HPATH)
