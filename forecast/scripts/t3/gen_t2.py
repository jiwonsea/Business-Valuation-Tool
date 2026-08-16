"""T-2 ①·③ 버킷 — 별도 진단 (승인 범위 4항목: T-4 의 GAAP 영업판정을 오염시키지 않는다)

계획 rev-3b §0.3 T-2 / §3.4(b). ② 버킷(시장성 마크)은 13F 수신(08-14) 후 별도.
N-2 규약: R2 3버킷은 NVDA 국소 적용만, generic 스키마 무변경 (사용자 2026-08-09).

모든 수치는 후보 v2 JSON(해시 검증) 또는 원장 A 인용값에서 스크립트 계산. 콘솔 비의존, LF 고정.
"""
from __future__ import annotations
import hashlib, json, os, sys

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


def locate(*cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return None


CAND_PATH = locate("../../reports/nvda_2026q2_freeze_a_candidate_v2.json",
                   "nvda_2026q2_freeze_a_candidate_v2.json")
CAND_EXPECT = "60cc8d23cc916444d062a530eb49c0f627b1e10ac8239fd9affe9e06419bfbef"
cand_sha = hashlib.sha256(open(CAND_PATH, "rb").read()).hexdigest()
if cand_sha != CAND_EXPECT:
    print("FATAL: candidate v2 hash mismatch (fail-closed)")
    raise SystemExit(1)
CAND = json.load(open(CAND_PATH, encoding="utf-8"))

NI_PCT = CAND["inputs"]["recurring_net_interest_pct_of_rev_q1"]   # 0.53667% of rev
REV_MID = CAND["inputs"]["guidance"]["revenue_mid_musd"]          # 91,000
REV_TOL = CAND["inputs"]["guidance"]["revenue_tol"]               # ±2%
# 원장 A 인용값 (T-1 문서와 동일 세트, 해시 고정됨)
Q1 = {"이자수익": 540, "이자비용": 102, "현금·채무증권": 50_335,
      "지분평가익(세전)": 15_929, "GAAP NI": 58_321, "매출": 81_615,
      "비시장성 잔액": 43_364, "비시장성 잔액(전기)": 22_251, "비시장성 취득": 18_582}
NI_Q1 = Q1["이자수익"] - Q1["이자비용"]        # +438
ANCHOR = {lab: REV_MID * (1 + t) * NI_PCT for lab, t in
          (("하단(-2%)", -REV_TOL), ("mid", 0.0), ("상단(+2%)", +REV_TOL))}

w("# T-2 ①·③ 버킷 — below-OP 진단 (T-4 비오염 · ② 는 13F 후)")
w("")
w("> 작성 2026-08-13 KST · 계획 rev-3b **§0.3 T-2 / §3.4(b)** · 승인 범위 4항목")
w("> **투자 자문 아님 — 모델 방법론 검증 목적의 내부 분석.**")
w("> **오염 방지 선언:** 본 문서는 **진단 전용**이다. T-4 의 정량 채점(GAAP OP·OPM)에 "
  "어떤 수치도 공급하지 않으며, Freeze-A CANONICAL(`variant_2a`, below-OP = 0 R2-blunt)을 "
  "변경하지 않는다. **N-2 보류 준수 — NVDA 국소 서술, generic 스키마 무변경.**")
w("")
w(f"입력 고정: 후보 v2 `{cand_sha[:16]}…` (해시 검증 통과 시에만 생성됨).")
w("")
w("---")
w("")
w("## 0. 3버킷 구조와 coverage 항등식")
w("")
w("```")
w("GAAP 세전이익 = GAAP 영업이익 + below-OP")
w("below-OP     = ①경상 순이자 + ②시장성 마크 + ③비시장성 마크·일회성")
w("```")
w("")
w("| 버킷 | 성격 | 처리 | 채점 |")
w("|---|---|---|---|")
w("| ① 경상 순이자 | 예측 가능·안정 | 현금잔액 × 단기금리 **앵커** | GAAP EPS **진단**에만 (OP 판정 무관) |")
w("| ② 시장성 마크 | 부분 관측 | **13F(06-30) 수신 후** — 08-14 별도 문서 | 밴드 coverage 만 |")
w("| ③ 비시장성·일회성 | 관측 불가 | **`UNFORECASTABLE` 선언** | point score 제외, coverage 실패는 기록 |")
w("")
w("**채점 시 ③ 산출 규약:** `③실측 = 세전이익실측 − 영업이익실측 − ①실측 − ②실측` (잔차 정의). "
  "①②③ 합이 below-OP 실측과 일치하는지(coverage)를 **먼저** 검증하고, 실패하면 실패로 기록한다 — "
  "임계는 Codex P1-5 규약대로 **절대오차를 기초 시장성 장부가·세전이익 대비 bp 로 병기**해 정의한다.")
w("")
w("---")
w("")
w("## 1. ① 경상 순이자 — 앵커")
w("")
w("| 항목 | 값 | 근거 |")
w("|---|---|---|")
w(f"| Q1 FY27 실측 | 이자수익 {Q1['이자수익']} − 이자비용 {Q1['이자비용']} = **+{NI_Q1} $M** | 원장 A |")
w(f"| 매출 대비 | **{NI_PCT*100:.4f}%** | 후보 v2 `recurring_net_interest_pct_of_rev_q1` |")
w(f"| 연환산 수익률 | {NI_Q1*4/Q1['현금·채무증권']*100:.2f}% (현금·채무증권 {Q1['현금·채무증권']:,} 대비) | 계산 |")
w("")
w("**Q2 앵커 (매출 가이드 ±2% 스케일):**")
w("")
w("| 매출 시나리오 | 매출($M) | ① 앵커($M) |")
w("|---|---:|---:|")
for lab, t in (("하단(-2%)", -REV_TOL), ("mid", 0.0), ("상단(+2%)", +REV_TOL)):
    rv = REV_MID * (1 + t)
    w(f"| {lab} | {rv:,.0f} | **{rv*NI_PCT:+,.1f}** |")
w("")
w(f"앵커 폭 {min(ANCHOR.values()):+,.1f} ~ {max(ANCHOR.values()):+,.1f} $M — "
  f"EPS 환산 약 ${min(ANCHOR.values())*0.83/24_490:.4f}~${max(ANCHOR.values())*0.83/24_490:.4f}/주 "
  "(세율 17%·엔진 주식수 24,490M 기준, 진단용 근사).")
w("")
w("⚠️ **한계 2건 (사전 기록):** ⑴ 금리 하락 시 수익률 3.48% 가정이 상방 편의 — 단 분기 내 "
  "재투자 롤이 완만해 ±수십 $M 수준. ⑵ 현금잔액 자체가 비시장성 취득(③ 유출)에 따라 변동 — "
  "①과 ③은 현금 사용을 통해 **약하게 결합**되어 있다. 진단 해석 시 유의.")
w("")
w("---")
w("")
w("## 2. ③ 비시장성 마크·일회성 — `UNFORECASTABLE` 선언")
w("")
w("| 항목 | 값 | 함의 |")
w("|---|---|---|")
w(f"| 잔액 | {Q1['비시장성 잔액(전기)']:,} → **{Q1['비시장성 잔액']:,} $M** (1분기 ×{Q1['비시장성 잔액']/Q1['비시장성 잔액(전기)']:.2f}) | **비정상 과정** — 계획 §3.4(b): 역사적 분위수 밴드 사용 금지 |")
w(f"| Q1 지분평가익(세전) | +{Q1['지분평가익(세전)']:,} $M = GAAP NI 의 **{Q1['지분평가익(세전)']/Q1['GAAP NI']*100:.1f}%** | 마크 1건이 분기 이익의 1/4 이상을 움직인다 |")
w(f"| Q1 매출 대비 below-OP | 약 **+{(NI_Q1+Q1['지분평가익(세전)'])/Q1['매출']*100:.1f}%** | 계획 §4 R2 행(+20.05%)과 정합 |")
w("")
w("**선언:** ③ 은 **예측하지 않는다.** 점추정·밴드·확률 어느 형태로도 산출하지 않으며, "
  "채점에서 point score 를 받지 않는다. 다만 **coverage 실패는 실패로 기록**한다 — "
  "\"예측 안 함\"이 \"채점 면제\"가 되지 않게 하기 위함이다(Codex 조건5).")
w("")
w("**근거 3줄:** ⑴ 관측 불가 — 비상장 지분의 분기 내 재평가는 공시 전 관측 수단이 없다. "
  "⑵ 비정상 — 잔액이 1분기에 2배가 된 과정에 정상성 가정을 씌울 수 없다. "
  "⑶ 자기참조 — 마크의 상당 부분이 NVDA 자신의 투자·계약 발표(Nebius 워런트 ~92% 평가익 등)에 "
  "내생적이라, 예측이 곧 자기 행동 예측이 된다.")
w("")
w("---")
w("")
w("## 3. T-4 비오염 확인 (승인 범위 4)")
w("")
w("| 확인 | 상태 |")
w("|---|---|")
w("| Freeze-A CANONICAL `variant_2a` (below=0) 무변경 | ✅ 본 문서는 JSON 을 읽기만 한다 |")
w("| T-4 정량 채점(GAAP OP·OPM)에 공급하는 수치 | **0건** — ①앵커·③선언 모두 below-OP 진단 |")
w("| generic 스키마 | 무변경 (N-2 보류 준수) |")
w("| ② 버킷 | **미작성** — 13F(08-14) 수신 후 06-30 스냅샷으로만, 07-26 복원 시도 안 함 |")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "T2_buckets_1_3_nvda_2026-08-13.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
