"""V2 — 10Y UST 기준일 확정 및 rf 오버레이 (BVT 트랙, 앵커 불변)

계획 §5 V2. Codex rev-4 회신 권고에 따라 **T-3 가격 기준일(2026-08-07) 시점의 rf**를 공식
소스로 고정하고, **7/10 as-run 앵커는 바꾸지 않은 채** rf sensitivity / overlay 로만 기록한다.

정책은 t3_final.py docstring 을 따른다 (TOL=1e-5). 출력은 콘솔 비의존, 개행 LF 고정.
"""
from __future__ import annotations
import hashlib, os, sys
import bvt_dcf as B
from bvt_dcf import calc_wacc, calc_dcf, _ev
from t3_reverse_dcf import ANCHORS, BASE_YEAR, SHARES, UNIT, PRICE_NOW, PRICE_PT
from t3_final import TOL, tgt, ps

B._MAX_ITER = 300
O = []
VERBOSE = os.environ.get("T3_VERBOSE", "") == "1" or "--print" in sys.argv
if VERBOSE:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        VERBOSE = False


def w(s=""):
    O.append(s)
    if VERBOSE:
        try:
            print(s)
        except Exception:
            pass


# ── 관측치 (원문 전체 행에서 전사) ────────────────────────────────────────────
# 출처: U.S. Department of the Treasury — Daily Treasury Par Yield Curve Rates
# 두 개의 독립 렌더링 경로에서 **동일한 전체 행**을 확인했다 (TextView / CSV endpoint).
UST_20260807 = {
    "1 Mo": 3.79, "1.5 Month": 3.79, "2 Mo": 3.83, "3 Mo": 3.87, "4 Mo": 3.89,
    "6 Mo": 3.96, "1 Yr": 4.01, "2 Yr": 4.19, "3 Yr": 4.25, "5 Yr": 4.35,
    "7 Yr": 4.49, "10 Yr": 4.65, "20 Yr": 5.20, "30 Yr": 5.19,
}
# INFO_CUTOFF_A = 2026-08-09 23:59 KST → 08/10·08/11 관측치는 **컷오프 이후**다.
UST_10Y_PRE = {"08/03/2026": 4.70, "08/04/2026": 4.63, "08/05/2026": 4.63, "08/06/2026": 4.69}
UST_10Y_POST = {"08/10/2026": 4.72, "08/11/2026": 4.70}
UST_10Y_OTHER = UST_10Y_PRE
RF = UST_20260807["10 Yr"]
RF_710 = 4.56   # 7/10 as-run (profiles/nvda_fy27e.yaml wacc_params.rf)

FY = ANCHORS["FY27E"]
eb, da, rev, wc, p, nd = (FY["ebitda_base"], FY["da_base"], FY["revenue"],
                          FY["wacc"], FY["dcf_p"], FY["net_debt"])
wp = FY["wacc_p"]
ERP = wp["erp"]
T = tgt(FY, PRICE_NOW)
IW = B.solve_implied_wacc(T, eb, da, rev, p, BASE_YEAR, TOL)
KD_AT = wp["kd_pre"] * (1 - wp["tax"] / 100)
DW = (100 - wp["eq_w"]) / 100
KE = (IW - KD_AT * DW) / (wp["eq_w"] / 100)
BETA = (KE - RF) / ERP


def beta(rf, erp=ERP):
    return (KE - rf) / erp


w("# V2 — 10Y UST 기준일 확정 및 rf 오버레이 (NVDA T-3)")
w("")
w("> 2026-08-10 실행 · 계획 `PLAN_nvda_2026-08_deep_dive.md` rev-3b **§5 V2** · "
  "T-3 산출물 `reports/T3_nvda_2026-08-10.md` 의 자기비판 1건을 해소한다.")
w("> **투자 자문 아님 — 모델 방법론 검증 목적의 내부 분석.**")
w("> **앵커 불변:** 7/10 as-run 프로파일(`rf 4.56%`)은 **바꾸지 않는다.** "
  "본 문서는 rf sensitivity / overlay 기록이다 (Codex rev-4 권고).")
w("")
w("---")
w("")
w("## 1. 기준일·출처·값 확정")
w("")
w(f"| 항목 | 값 |")
w(f"|---|---|")
w(f"| **기준일** | **2026-08-07** — T-3 가격 기준일(NVDA 종가 ${PRICE_NOW})과 **동일 거래일** |")
w(f"| **출처** | U.S. Department of the Treasury — *Daily Treasury Par Yield Curve Rates* (1차 자료) |")
w(f"| **10 Yr** | **{RF}%** |")
w(f"| **교차확인** | 동일 기관의 **두 독립 렌더링 경로**(TextView HTML / CSV endpoint)에서 "
  "**전체 행이 완전 일치** |")
w(f"| 정보 컷오프 | INFO_CUTOFF_A(2026-08-09 23:59 KST) **이전** 관측치 → 컷오프 준수 |")
w("")
w("**2026-08-07 par yield curve 전체 행 (전사):**")
w("")
w("| " + " | ".join(UST_20260807.keys()) + " |")
w("|" + "---:|" * len(UST_20260807))
w("| " + " | ".join(f"**{v}**" if k == "10 Yr" else f"{v}" for k, v in UST_20260807.items()) + " |")
w("")
w("⚠️ **전사 함정 — 실제로 걸렸다.** 1차 조회에서 한 경로가 10 Yr 을 **4.35** 로 반환했는데, "
  "이는 **5 Yr 열**이다(위 행에서 5 Yr = 4.35). **열 이름만 요청하면 열 정렬이 어긋나도 드러나지 않는다.** "
  "→ **헤더 + 전체 행을 받아 열 위치를 직접 확인**해야 한다. 본 문서의 값은 그 절차로 확정했다.")
w("")
w("**인접 거래일 10 Yr — 컷오프 이내 (맥락용, 판정에는 미사용):**")
w("")
w("| " + " | ".join(UST_10Y_PRE.keys()) + " |")
w("|" + "---:|" * len(UST_10Y_PRE))
w("| " + " | ".join(str(v) for v in UST_10Y_PRE.values()) + " |")
w("")
w("⚠️ **컷오프 이후 관측치는 분리 격리한다.** `INFO_CUTOFF_A = 2026-08-09 23:59 KST` 이므로 "
  + ", ".join(f"**{k} {v}%**" for k, v in UST_10Y_POST.items()) +
  " 는 **컷오프 밖**이다. 조회 과정에서 함께 노출됐으나 **판정·민감도·오버레이 어디에도 사용하지 않는다.** "
  "(계획 §3.1: 해시는 숫자만 잠그고 판단은 못 잠근다 → 노출 사실 자체를 기록해 둔다.)")
w("")
w(f"7/10 as-run rf **{RF_710}%** → 2026-08-07 **{RF}%**, **{(RF-RF_710)*100:+.0f}bp**.")
w("")
w("---")
w("")
w("## 2. βL 결론 판정")
w("")
w("내재 βL 은 T-3의 내재 WACC 로부터 역산된다 (자본구조·Kd 불변 가정):")
w("")
w("```")
w(f"내재 WACC  = {IW:.4f}%      (가격 ${PRICE_NOW} 를 설명하는 할인율, rf 와 무관하게 결정됨)")
w(f"내재 Ke    = (WACC − Kd_at × D%) / E%")
w(f"           = ({IW:.4f} − {KD_AT:.4f} × {DW:.3f}) / {wp['eq_w']/100:.3f} = {KE:.4f}%")
w(f"내재 βL    = (Ke − rf) / ERP = ({KE:.4f} − {RF}) / {ERP} = {BETA:.4f}")
w("```")
w("")
w(f"| rf | 출처 | 내재 βL |")
w("|---|---|---:|")
w(f"| {RF_710}% | 7/10 as-run (stale) | {beta(RF_710):.4f} |")
w(f"| **{RF}%** | **2026-08-07 Treasury (확정)** | **{BETA:.4f}** |")
for d, v in UST_10Y_PRE.items():
    w(f"| {v}% | {d} (컷오프 이내, 참고) | {beta(v):.4f} |")
w("")
w(f"**판정: `βL < 1` 결론 — 유지. 그리고 stale rf 대비 오히려 강화됐다** "
  f"({beta(RF_710):.3f} → **{BETA:.3f}**). rf 가 {(RF-RF_710)*100:+.0f}bp 올라 βL=1.0 분기점 "
  f"**{KE-ERP:.2f}%** 에서 더 멀어졌다.")
w("")
w("---")
w("")
w("## 3. ⚠️ 미해소 조건 — ERP")
w("")
w(f"**βL 은 rf 와 ERP 에 *동시에* 조건부다.** V2는 rf 축만 해소했다. "
  f"ERP **{ERP}%** 는 여전히 **7/10 as-run 가정이며 갱신되지 않았다.**")
w("")
w("| βL = 1.0 이 되는 조건 | 임계 | 실제 | 충족? |")
w("|---|---:|---:|:--:|")
w(f"| ERP={ERP}% 고정 시 rf | ≤ {KE-ERP:.2f}% | {RF}% | ❌ (βL<1) |")
w(f"| rf={RF}% 고정 시 ERP | ≤ {KE-RF:.2f}% | {ERP}% | ❌ (βL<1) |")
w("")
w(f"**ERP 민감도 (rf = {RF}% 고정):**")
w("")
w("| ERP | 내재 βL | |")
w("|---:|---:|---|")
for e in (3.50, 4.00, 4.02, 4.20, 4.60, 5.00, 5.50):
    b = beta(RF, e)
    w(f"| {e:.2f}% | {b:.3f} | {'**β ≥ 1 — 결론 반전**' if b >= 1.0 else ''} |")
w("")
w("**rf × ERP 격자:**")
w("")
_erps = [4.00, 4.60, 5.00, 5.50]
w("| rf \\ ERP | " + " | ".join(f"{e:.2f}%" for e in _erps) + " |")
w("|---:|" + "---:|" * len(_erps))
for rf in (round(KE - ERP, 2), RF_710, RF, 4.90, 5.00):
    cells = []
    for e in _erps:
        b = beta(rf, e)
        cells.append(f"**{b:.3f}**" if b >= 1.0 else f"{b:.3f}")
    lab = f"{rf:.2f}%" + (" ←분기점" if abs(rf - (KE - ERP)) < 0.005 else
                          " ←**확정**" if abs(rf - RF) < 1e-9 else "")
    w(f"| {lab} | " + " | ".join(cells) + " |")
w("")
w(f"→ **ERP {KE-RF:.2f}% 미만이면 βL ≥ 1 로 뒤집힌다.** 7/10 가정 {ERP}% 는 그보다 높으므로 "
  "현재 결론은 유지되나, **ERP 갱신 전까지 βL 수치는 `rf={:.2f}%·ERP={:.1f}% 조건부` 표기 없이 "
  "인용하지 않는다.**".format(RF, ERP))
w("")
w("---")
w("")
w("## 4. 오버레이 — rf 를 *모델* 쪽에도 반영하면 (참고, 앵커 불변)")
w("")
w("내재 WACC 는 가격에서 역산되므로 rf 와 무관하다. 반면 **모델 WACC 는 rf 를 입력으로 쓴다.** "
  "앵커를 바꾸지 않는다는 결정에 따라 아래는 **참고 수치일 뿐 T-3 본표를 대체하지 않는다.**")
w("")
w("| rf | 모델 Ke | 모델 WACC | 모델 EV | 모델 주가 | 내재−모델 갭 |")
w("|---:|---:|---:|---:|---:|---:|")
for rf in (RF_710, RF):
    w2 = calc_wacc(**dict(wp, rf=rf))
    d = calc_dcf(eb, da, rev, w2["wacc"], p, BASE_YEAR)
    w(f"| {rf}%{' (as-run)' if rf == RF_710 else ' (08-07)'} | {w2['ke']}% | {w2['wacc']}% | "
      f"{d['ev_dcf']:,} | ${ps(FY, d['ev_dcf']):.2f} | {IW-w2['wacc']:+.2f}pp |")
w("")
w("---")
w("")
w("## 5. V2 판정 요약")
w("")
w("| 항목 | 판정 |")
w("|---|---|")
w(f"| 10Y UST 기준일·출처·값 | **확정** — 2026-08-07 · U.S. Treasury par yield curve · **{RF}%** (2경로 전체행 일치) |")
w(f"| `βL < 1` 결론 | **유지 (강화)** — {beta(RF_710):.3f} → **{BETA:.3f}** |")
w(f"| rf 조건성 | **해소** — 분기점 {KE-ERP:.2f}% 대비 실제 {RF}% |")
w(f"| ERP 조건성 | **미해소** — ERP ≤ {KE-RF:.2f}% 면 반전. 7/10 as-run {ERP}% 그대로 |")
w("| 앵커 | **불변** — 7/10 as-run 프로파일 무수정, 본 문서는 overlay 기록 |")
w("")
w(f"**T-3 산출물 조치:** 자기비판 블록의 \"V2 미실행 → βL 수치 인용 금지\" 를 "
  f"**\"rf 해소({RF}%, βL {BETA:.3f}) · ERP 미해소\"** 로 갱신한다.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "V2_rf_overlay_nvda_2026-08-10.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
