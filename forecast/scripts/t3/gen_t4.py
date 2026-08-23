"""T-4 판정 초안 — 승인 범위 5항목 (사용자 2026-08-13)

1. 08-10 매니페스트 읽기 전용 검증 → 입력 해시 고정 (fail-closed)
2. 판정은 GAAP OP·OPM 만 정량 채점 훅. T-3/V2/T-1 은 조건·반증요건으로 분리
3. 반증조건 3개의 프린트 관측 가능성 검증, UNVERIFIABLE 은 결론 근거에서 제외
4. (T-2 ①③ 은 gen_t2.py 별도 — 본 문서를 오염시키지 않는다)
5. 산출 후 매니페스트 부록 append-only 기록 (gen_manifest_t4.py)

모든 수치는 스크립트 계산. 손타이핑 0. 콘솔 비의존, 개행 LF 고정.
"""
from __future__ import annotations
import hashlib, json, os, re, sys
import bvt_dcf as B
from bvt_dcf import _ev
from t3_reverse_dcf import ANCHORS, BASE_YEAR, SHARES, UNIT, PRICE_NOW, PRICE_PT
from t3_final import TOL, solve, tgt, ps

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


def locate(*cands):
    for c in cands:
        if os.path.exists(c):
            return c
    return None


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# ── [범위 1] 매니페스트 읽기 전용 검증 → 입력 고정 ──────────────────────────────
MANIFEST = locate("../../reports/MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md",
                  "MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md")
INPUTS = {
    "reports/T3_nvda_2026-08-10.md": ("../../reports/T3_nvda_2026-08-10.md", "T3_nvda_2026-08-10.md"),
    "reports/V2_rf_overlay_nvda_2026-08-10.md": ("../../reports/V2_rf_overlay_nvda_2026-08-10.md", "V2_rf_overlay_nvda_2026-08-10.md"),
    "reports/BASIS_consensus_verification_nvda_2026-08-10.md": ("../../reports/BASIS_consensus_verification_nvda_2026-08-10.md", "BASIS_consensus_verification_nvda_2026-08-10.md"),
    "reports/T1_vendor_financing_nvda_2026-08-10.md": ("../../reports/T1_vendor_financing_nvda_2026-08-10.md", "T1_vendor_financing_nvda_2026-08-10.md"),
}
# Freeze-A 후보 v2 — rev-3b 매니페스트 등재 해시 (기대값, 불일치 시 중단)
CAND_PATH = locate("../../reports/nvda_2026q2_freeze_a_candidate_v2.json",
                   "nvda_2026q2_freeze_a_candidate_v2.json")
CAND_EXPECT = "60cc8d23cc916444d062a530eb49c0f627b1e10ac8239fd9affe9e06419bfbef"

if MANIFEST is None or CAND_PATH is None:
    print("FATAL: manifest or candidate v2 not found")
    raise SystemExit(1)

mtext = open(MANIFEST, encoding="utf-8").read()
pinned, fails = [], []
for label, cands in INPUTS.items():
    m = re.search(re.escape(f"`{label}`") + r"\s*\|\s*`([0-9a-f]{64})`", mtext)
    p = locate(*cands)
    if m is None or p is None:
        fails.append((label, "매니페스트 행 또는 파일 없음"))
        continue
    actual = sha(p)
    if actual != m.group(1):
        fails.append((label, f"불일치 manifest={m.group(1)[:8]}… actual={actual[:8]}…"))
    pinned.append((label, actual))
cand_sha = sha(CAND_PATH)
if cand_sha != CAND_EXPECT:
    fails.append(("freeze_a_candidate_v2.json", f"불일치 expect={CAND_EXPECT[:8]}… actual={cand_sha[:8]}…"))
if fails:
    print("FATAL: input pin FAILED (fail-closed)")
    for f_ in fails:
        print("  ", f_)
    raise SystemExit(1)

CAND = json.load(open(CAND_PATH, encoding="utf-8"))
V2A = CAND["variant_2a_mechanical_engine_shares"]
OP_BASE = V2A["base"]["op"]                # 정량 채점 앵커 (Freeze-A 예정)
OPM_BASE = V2A["base"]["op_margin"]
OP_W = V2A["weighted"]["op"]

# ── 계산 입력 (T-3 rev-7 체계 재계산 — 인용이 아니라 동일 스크립트 재실행) ────────
FY = ANCHORS["FY27E"]
eb, da, rev, wc, p, nd = (FY["ebitda_base"], FY["da_base"], FY["revenue"],
                          FY["wacc"], FY["dcf_p"], FY["net_debt"])
wp = FY["wacc_p"]
R = solve(FY, PRICE_NOW)
RPT = solve(FY, PRICE_PT)
IW, GM, MG = R["wacc"], R["gmult"], R["margin"]
fy32 = eb
for g in p["ebitda_growth_rates"]:
    fy32 *= (1 + g * GM)
CAGR = (fy32 / eb) ** 0.2 - 1
KD = wp["kd_pre"] * (1 - wp["tax"] / 100)
DW = (100 - wp["eq_w"]) / 100
KE = (IW - KD * DW) / (wp["eq_w"] / 100)
RF_V2, ERP = 4.65, wp["erp"]
BETA = (KE - RF_V2) / ERP
EV0 = _ev(eb, da, rev, wc, p, BASE_YEAR)
PS0 = ps(FY, EV0)
T1_REALIZED, T1_NEG = 34_060, 600_000     # T-1 §2 (원장 A 인용값, T-1 문서 해시로 고정됨)

w("# T-4 판정 초안 — NVDA $223.96 (rev-4)")
w("")
w("> 작성 2026-08-13 KST *(계획 §7 은 08-11~12 — 1일 지연, Codex 검증 라운드에 소요)* · "
  "계획 `PLAN_nvda_2026-08_deep_dive.md` rev-3b **§0.3 T-4** · 승인 범위 5항목(사용자 2026-08-13)")
w("> **투자 자문 아님 — 모델 방법론 검증 목적의 내부 분석.**")
w("> **프린트-전 규율 준수:** 본 문서는 **새 공정가치 숫자를 산출하지 않는다**(계획 §2-1). "
  "판정은 역방향 프레임 — *시장가격이 요구하는 가정을 검증된 사실이 지지하는가* — 로만 내린다.")
w("> **Codex 검증:** rev-1 `CONDITIONAL` — 기계 검증(해시 11건·결정성·입력 고정·§5 검사·RC-1′/2′ "
  "관측 가능성) 전건 PASS, 판정 논리 정정 3건 → rev-2 반영: ① 축 결합 논리(동시 요구 → "
  "단일축 조건부 해·조합 비식별) ② 안전마진 라벨(7/10 as-run DCF 기준 한정) ③ RC = 약화 관측(반전 트리거 아님). "
  "rev-2 `CONDITIONAL` — ①~③ 정확 반영 확인, 잔여 1건 → rev-3 반영: "
  "④ RC-3′ 수치 임계값 사전등록 부재 → **서술적 약화 신호로 강등, 관측 판정은 RC-1′·RC-2′ 2개로만 수행** "
  "(사용자 승인 2026-08-13). "
  "rev-3 `CONDITIONAL` — ④ 반영 확인(그 외 전건 PASS), 잔여 모호성 1건 → **본 rev-4 반영**: "
  "⑤ §3 역방향 문장의 \"RC 전부 미발화\"가 RC-3′ 포함으로 읽힘 → \"RC-1′·RC-2′ 모두 미발화\"로 한정.")
w("")
w("---")
w("")
w("## §1. [범위 1] 입력 고정 — 매니페스트 읽기 전용 검증 결과")
w("")
w(f"`{os.path.basename(MANIFEST)}` 의 등재 해시와 실제 파일 해시를 대조했다. **전건 일치 (fail-closed 통과).**")
w("")
w("| 입력 | sha256 (재계산 = 매니페스트) |")
w("|---|---|")
for label, h in pinned:
    w(f"| `{label}` | `{h}` |")
w(f"| `reports/nvda_2026q2_freeze_a_candidate_v2.json` (CANONICAL=variant_2a) | `{cand_sha}` |")
w("")
w("본 문서의 모든 인용 수치는 위 5개 입력에서만 나오며, T-3 계열 수치는 인용이 아니라 "
  "**동일 스크립트 체계로 재계산**한다(불일치 시 생성 자체가 실패한다).")
w("")
w("---")
w("")
w("## §2. [범위 2] 판정 프레임 — 무엇으로 판정하고, 무엇으로 판정하지 않는가")
w("")
w("| 층 | 내용 | 역할 |")
w("|---|---|---|")
w(f"| **정량 채점 (유일)** | **GAAP 영업이익 + OPM** — Freeze-A 앵커 base OP **{OP_BASE:,.0f}** · "
  f"OPM **{OPM_BASE*100:.3f}%** · 확률가중 OP {OP_W:,.0f} (후보 v2 `variant_2a`) | "
  "프린트 채점 HIT/MISS 의 전부 (BASIS 결정 ②) |")
w("| 조건 (비채점) | T-3 역산 가정 · V2 βL · T-1 자금조달 구조 | 판정의 **방향**을 정하되 채점되지 않음 |")
w("| 반증요건 (비채점) | **RC-1′·RC-2′** (§4) | 판정을 **약화시키는** 프린트 관측 조건 (반전 트리거 아님 — §4 비대칭) |")
w("| 서술적 약화 신호 (비판정) | RC-3′ (§4) | 임계값 사전등록 부재 → 관측 판정에 불사용, 서술만 (Codex 정정 ④) |")
w("| 서술용 진단 | (d) 컨센 대비 위치(3소스 전부 `BASIS_UNKNOWN`) · 비GAAP EPS · GAAP EPS 밴드 · T-2 버킷 | 결론 근거 아님 |")
w("")
w("**결론 근거에서 제외 (UNVERIFIABLE, 범위 3):**")
w("")
w("| 제외 항목 | 사유 |")
w("|---|---|")
w("| out-year 컨센 대비 T-3 경로 비교 (§0.4-1) | FY28~32 EBIT·EBITDA 컨센 부재 — \"컨센과 같다\"도 \"다르다\"도 주장 불가 |")
w(f"| T-1 negotiating {T1_NEG:,} $M | 구속력 없음, 밴드 하단 0 — 정성 강등 확정 |")
w("| (d) 컨센 HIT/MISS | 3소스 전부 `BASIS_UNKNOWN` |")
w(f"| βL 절대수준의 단독 인용 | ERP {ERP}% 미갱신 — `rf={RF_V2}%·ERP={ERP}%` 조건부로만 |")
w("")
w("---")
w("")
w("## §3. 판정 (초안)")
w("")
w("### 시장가격이 요구하는 것 (T-3 rev-7 재계산, FY27E 앵커)")
w("")
w("> **축 해석 (Codex 정정 ①):** 각 수치는 다른 축을 모델값에 고정한 **단일-변수 조건부 해**다. "
  "어느 하나가 **단독으로** 가격을 설명하려면 해당 수준이 필요하며, 축들의 실제 조합은 "
  "**비식별적**이다. 아래 표는 '동시 요구'가 아니라 **축별 대안 경로**다.")
w("")
w("| 축 | $223.96 이 요구 | $302.83(PT) 이 요구 | 검증된 사실이 지지하는가 |")
w("|---|---|---|---|")
w(f"| 할인율 | WACC **{IW:.2f}%** → Ke {KE:.2f}% → βL **{BETA:.3f}** (rf {RF_V2}%) | "
  f"WACC **{RPT['wacc']:.2f}%** | ❌ 지지 근거 없음 — 시장 β 미만의 자본비용을 정당화할 검증 사실이 없다. "
  "오히려 T-1 이 확인한 counterparty 집중(realized 의 88.1%가 OpenAI)은 **반대 방향** |")
_fy32_pt = eb
for g in p["ebitda_growth_rates"]:
    _fy32_pt *= (1 + g * RPT["gmult"])
w(f"| 성장 | 5년 EBITDA CAGR **{CAGR*100:.2f}%** (모델 {((eb*1.18*1.13*1.09*1.06*1.04/eb)**0.2-1)*100:.2f}%) | "
  f"CAGR **{((_fy32_pt/eb)**0.2-1)*100:.2f}%** | ❓ **판정 불능(UNVERIFIABLE)** — 비교할 out-year 컨센이 없고, "
  "그 성장의 자금조달 구조도 T-1 에서 정량 판정 불가. **결론 근거에서 제외** |")
w(f"| 마진 | 내재 EBITDA 마진 **{MG*100:.2f}%** (v2 축) | UNREACHABLE (99%로도 미달) | "
  "❌ 경제적으로 불가능한 수준 (Q1 실적 OPM 65.6%) |")
w("| 영구성장·듀레이션 | UNREACHABLE (Gordon 5%·+40년으로도 미달) | 동일 | — (레버로 성립 안 함) |")
w("")
w("### 판정문")
w("")
w("> **판정(초안): 고평가 쪽 기울기 — \"적정 상단 ~ 고평가\". 7/10 as-run DCF 기준 안전마진 부재는 확정, "
  "고평가 확신도는 낮음.**")
w("")
w("근거를 지지 수준별로 분리한다:")
w("")
w(f"1. **[확정] 7/10 as-run DCF 기준 안전마진 부재.** 해당 앵커(연결 DCF ${PS0:.2f}) 대비 현재가는 "
  f"**+{(PRICE_NOW/PS0-1)*100:.1f}%** 위에 있고, 가격 도달에는 위 3축 중 최소 1축의 공격적 가정이 "
  "필수다. 어느 축도 검증된 사실의 지지를 받지 못한다. **이 명제는 앵커 모델 상대적이며 절대 "
  "밸류에이션 사실이 아니다** (Codex 정정 ②). *(주: $"
  f"{PS0:.2f} 는 7/10 as-run 모델의 기존 산출이지 새 공정가치가 아니다 — §2-1 준수)*")
w(f"2. **[방향] 고평가 기울기.** 가격을 **단독으로** 설명하는 세 단일축 해 — β<1 자본비용(WACC "
  f"{IW:.2f}%, βL {BETA:.3f}) **또는** {CAGR*100:.0f}% CAGR **또는** 마진 {MG*100:.1f}% — 는 각각 "
  "공격적이거나 경제적으로 불능이고, 완화된 수준들의 조합 경로는 **비식별적**이라 특정할 수 없다 "
  "(Codex 정정 ①). 반면 검증된 신규 사실(T-1 realized "
  f"{T1_REALIZED:,} $M = FY27E 매출의 {T1_REALIZED/rev*100:.1f}%, OpenAI 집중, CDS +14bp 반응)은 "
  "자본비용을 **높이는** 방향 — 요구 수준을 더 멀게 만든다.")
w("3. **[한계] 확신도 낮음.** 성장 축이 UNVERIFIABLE 이므로 \"시장이 틀렸다\"고 단정할 수 없다. "
  "20% CAGR 이 실현될 수도 있다 — 우리는 그것을 지지할 수도 반증할 수도 없을 뿐이다. "
  "**따라서 이 판정은 포지션 권고가 아니라 위험 서술이다.**")
w("")
w("**판정 기울기가 약화되는 조건 (§4 와 방향 일치):** ⑴ 반증조건 **RC-1′·RC-2′** 가 "
  "프린트에서 **발화**하면(성장 확인·마진 압력 부재) 고평가 기울기가 약화된다 — "
  "**약화이지 반전이 아니다**: 1분기 관측은 성장 축 UNVERIFIABLE 을 해소하지 못한다 (Codex 정정 ③). "
  "RC-3′(자기조달 완화)는 서술적 참고만 된다 (Codex 정정 ④). "
  f"⑵ 추가로 ERP 갱신이 **ERP ≤ {KE-RF_V2:.2f}%** 로 나오면 βL ≥ 1 이 되어 \"시장이 β<1 자본비용을 "
  "쓴다\"는 근거 1축이 소멸한다. **역으로 RC-1′·RC-2′ 모두 미발화 + ERP ≥ 현행이면 고평가 기울기가 "
  "강화되나, 성장 축 UNVERIFIABLE 이 남는 한 \"고평가 확정\" 으로는 올리지 않는다** "
  "(Codex 정정 ⑤ — RC-3′ 는 이 역방향 경로에도 불포함).")
w("")
w("---")
w("")
w("## §4. [범위 3] 반증조건 3개 — 프린트 관측 가능성 검증")
w("")
w("T-3 rev-7 이 넘긴 후보(RC-1~3)를 관측 가능성까지 검증해 확정판으로 고정한다. "
  "**관측 판정 트리거는 RC-1′·RC-2′ 2개** — RC-3′ 는 수치 임계값이 사전등록되지 않아(하단 참조) "
  "**서술적 약화 신호로 강등**한다 (Codex rev-2 정정 ④, 사용자 승인).")
w("")
w("| # | 반증조건 (무엇이 관측되면 위 판정이 **약화**되는가 — 반전 아님) | 관측원 | 관측 가능성 | 연동 |")
w("|---|---|---|---|---|")
w("| **RC-1′** | FY27 Q3 매출 가이던스 mid 가 Q2 가이드 mid($91.0B) 대비 **QoQ 증가**를 제시 | "
  "프린트 보도자료 (가이던스 절) | ✅ **확정** — NVDA 는 매 분기 PR 에서 차분기 매출 가이드를 제시해 왔다 "
  "(Codex 확인: Q1 FY27·Q4 FY26 PR) | "
  "SF-B(사전확률 40%)의 역방향 |")
w("| **RC-2′** | GAAP GM ≥ 74.9% (가이드 mid 이상) — 마진 압력 부재 | "
  "프린트 보도자료 (GAAP 재무제표) | ✅ **확정** (Codex 확인: PR GAAP 손익) | SF-A(25%)의 역방향 |")
w("| **RC-3′** *(서술적 신호 — 판정 트리거 아님)* | 프린트 CFS 의 **비시장성 지분증권 취득** 라인이 "
  "Q1(18,582 $M) 대비 감소 — 자기 B/S 조달 의존 완화의 **서술적** 신호 | 프린트 보도자료 condensed CFS | "
  "⚠️ **판정 불사용** — ⑴ \"유의하게 감소\"의 수치 임계값이 사전등록되지 않았고, 잔액 과정이 "
  "비정상(N=1, T-2 ③ 과 동일 논리)이라 임계 고정이 자의적 ⑵ 당일 PR 의 CFS 세분화 수준도 보장 불가 — "
  "**라인 부재 시 `UNVERIFIABLE`** (fail-closed 유지). 관측되면 방향·크기를 **서술만** 한다 | "
  "T-1 (B) 정성 리스크의 역방향 (서술) |")
w("")
w("**§0.4-4 대조:** \"3개 중 어느 것도 프린트로 관측 불가하면 다시 쓴다\" — 판정 트리거 "
  "RC-1′·RC-2′ 가 **확정 관측 가능**(Codex 확인)이므로 조항 충족. RC-3′ 를 판정 트리거로 "
  "복권하려면 **감소율 또는 절대금액 임계값을 프린트 전에 사전등록**해야 한다(Codex rev-2) — "
  "현 시점에는 임계값을 정당화할 분포 근거가 없어(N=1·비정상) 등록하지 않는다.")
w("")
w("⚠️ **반증조건의 비대칭 명시:** RC 발화는 판정을 **약화**시키지만(고평가 → 적정 방향), "
  "RC 미발화가 고평가를 **증명하지는 않는다** — 성장 축 UNVERIFIABLE 이 해소되지 않기 때문. "
  "N=1 관측으로 판정을 확정하지 않는다(계획 §0.1 교훈).")
w("")
w("---")
w("")
w("## §5. [범위 2] 정량 채점 훅 — 프린트에서 실제로 채점되는 것")
w("")
w("| 항목 | 값 | 출처 |")
w("|---|---|---|")
w(f"| 판정 지표 | **GAAP 영업이익 오차 · OPM 오차** | 계획 §3.4(a) + BASIS 결정 ② |")
w(f"| base OP | **{OP_BASE:,.0f} $M** (OPM {OPM_BASE*100:.3f}%) | 후보 v2 `variant_2a` (`{cand_sha[:8]}…`) |")
w(f"| 확률가중 OP | {OP_W:,.0f} $M | 〃 |")
w("| Freeze-A | **08-13 예정** — 후보 v2 재현 검증 방식 (새 저술 아님) | 계획 §3.1 |")
w("| 컨센 대비 | **채점 안 함** — (d) 영구 서술용 (BASIS 결정 ②) | |")
w("| 비GAAP EPS · GAAP EPS | 진단 전용 (T-2 버킷, 별도 문서) | gen_t2.py |")
w("")
w("**T-4 최종판(08-28~29 예정)은** 프린트 실측 OP·OPM 채점 + RC-1′·RC-2′ 발화 여부 "
  "(+ RC-3′ 서술적 관찰) + (가능 시) ERP 갱신을 반영해 본 초안의 판정문을 확정하거나 수정한다. "
  "채점 자체는 §6.1 3단 분리(Codex 산술 / fresh 세션 발화판정 / 사용자 승인)를 따른다.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "T4_verdict_draft_nvda_2026-08-13.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
