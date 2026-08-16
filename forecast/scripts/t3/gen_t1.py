"""T-1 벤더파이낸싱 익스포저 — 1일 타임박스 (계획 rev-3b §0.3)

착수조건(= Codex P1-3): ① counterparty-project dedupe ② realized/committed/negotiating 3분류
③ 매출 인식기간 정의.  실패조건(Codex P2-2): 밴드 **폭**이 아니라 **하단이 T-4 판정 임계를 넘는지**.
사전등록 §0.4-2: 3분류가 안 되면 즉시 정성 강등, 정밀해 보이는 밴드를 만들지 않는다.

사실은 전부 정보원장 A(INFO_CUTOFF_A 이내)에서 인용. 신규 조회 없음.
출력은 콘솔 비의존, 개행 LF 고정.
"""
from __future__ import annotations
import hashlib, os, sys
import bvt_dcf as B
from bvt_dcf import _ev
from t3_reverse_dcf import ANCHORS, BASE_YEAR, SHARES, UNIT, PRICE_NOW
from t3_final import TOL, tgt

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


# ── 원장 A 인용 (금액 $M) ─────────────────────────────────────────────────────
# (항목, counterparty, project, 단계, 금액, 매출 리드스루 여부, 근거일)
ITEMS = [
    ("OpenAI 지분투자", "OpenAI", "OpenAI 법인", "realized", 30_000, False, "원장 §6-1"),
    ("Nebius 9.3% 지분", "Nebius", "Nebius 법인", "realized", 4_060, False, "2026-07-20~21"),
    ("NAVER ~4.5% 지분", "NAVER", "NAVER AI팩토리", "committed(조건부)", 1_000, False, "2026-07-27"),
    ("오하이오 10GW DC 채무보증", "OpenAI/SoftBank", "오하이오 10GW DC", "negotiating", 250_000, False, "2026-07-27 WSJ"),
    ("OpenAI향 칩 매출 금융", "OpenAI", "(칩 조달 전반)", "negotiating", 350_000, True, "2026-07-27 WSJ"),
]
SUPPLY = [("Amkor 애리조나 선급", "Amkor", "애리조나 패키징", "committed", 1_500, "2026-07-23")]
EXCLUDED = [
    ("SK그룹 $500B+ LOI", "**NVDA 지분투자 없음** — LOI 단계, 익스포저 아님 (원장 2026-07-24)"),
    ("KAIST 연구소 $300M", "연구 지원, 벤더파이낸싱 성격 아님"),
]
BS = {"시장성 지분증권": 30_237, "비시장성 증권": 43_364, "지분증권 합계": 73_601,
      "TTM 매출": 253_491, "Q1 비시장성 취득": 18_582, "Q1 FCF": 48_554,
      "Q1 지분평가익(세전)": 15_929, "Q1 GAAP NI": 58_321}

FY = ANCHORS["FY27E"]
eb, da, rev, wc, p, nd = (FY["ebitda_base"], FY["da_base"], FY["revenue"],
                          FY["wacc"], FY["dcf_p"], FY["net_debt"])
T = tgt(FY, PRICE_NOW)
GM = B.solve_implied_growth_multiplier(T, eb, da, rev, wc, p, BASE_YEAR, TOL)
# T-3 내재 성장경로의 매출 (엔진이 revenue_growth_rates 를 ebitda 로 폴백 → 동일 배수)
REVPATH, _r = [], rev
for _g in p["ebitda_growth_rates"]:
    _r = _r * (1 + _g * GM)
    REVPATH.append(_r)
CUM_REV = sum(REVPATH)

w("# T-1 벤더파이낸싱 익스포저 — 1일 타임박스 결과")
w("")
w("> 2026-08-10 실행 · 계획 `PLAN_nvda_2026-08_deep_dive.md` rev-3b **§0.3 T-1** · "
  "사실은 전부 **정보원장 A**(컷오프 이내)에서 인용, 신규 조회 없음.")
w("> **투자 자문 아님 — 모델 방법론 검증 목적의 내부 분석.**")
w("")
w("## 0. 결론")
w("")
w("**착수조건 3건은 충족했다. 그러나 사전등록된 실패조건에 걸려 정량 밴드를 만들지 않는다.**")
w("")
w("| 조건 | 결과 |")
w("|---|---|")
w("| ① counterparty-project dedupe | **충족** — 명목 중복 없음. 단 **상관은 1에 가깝다**(§1) |")
w("| ② realized / committed / negotiating 3분류 | **충족** (§2) |")
w("| ③ 매출 인식기간 정의 | **충족** — 대부분 **FY2028 이후**로 밀린다 (§3) |")
w("| **실패조건 (Codex P2-2)** | ❌ **밴드 하단 = 0** — negotiating 이 압도적인데 구속력이 없다 (§4) |")
w("")
w("→ **정량 밴드 대신 2분할 보고:** **(A) realized 익스포저는 정량**, "
  "**(B) negotiating 은 정성 리스크**로 분리한다. 계획 §0.4-2 의 "
  "\"정밀해 보이는 밴드를 만들지 않는다\" 를 준수한다.")
w("")
w("---")
w("")
w("## 1. ① dedupe — 명목은 중복 없음, **상관은 1에 가깝다**")
w("")
w("| 항목 | counterparty | project | 단계 | 금액($M) | 매출 리드스루 |")
w("|---|---|---|---|---:|:--:|")
for n, c, pj, st, amt, lead, src in ITEMS:
    w(f"| {n} | {c} | {pj} | {st} | {amt:,} | {'✅' if lead else '—'} |")
w("")
w("**OpenAI 계열 3건이 dedupe 의 핵심이다.** 원장이 두 가지를 명시한다: "
  "① $250B 보증의 **대상은 DC 건설·리스이지 칩이 아니다** ② $350B 칩 매출 금융은 **별건**이다. "
  "→ **명목 금액은 중복 계상이 아니다.**")
w("")
w("⚠️ **그러나 독립 사건으로 취급하면 안 된다.** 세 건 모두 **OpenAI 의 자금조달 능력이라는 "
  "단일 실패점**에 걸려 있다. OpenAI 조달이 막히면 지분가치·보증 이행·칩 금융이 **동시에** 손상된다.")
w("")
w("> **dedupe 규칙 정식화:** **금액은 합산해도 되지만 분산은 합산하면 안 된다.** "
  "명목 exposure 는 Σ 로, 리스크는 **counterparty 단위 단일 사건**으로 집계한다. "
  "이 구분을 하지 않으면 \"$600B 익스포저가 3개로 분산돼 있다\" 는 잘못된 안심이 생긴다.")
w("")
_op = sum(a for n, c, pj, st, a, l, s in ITEMS if "OpenAI" in c)
_tot = sum(a for n, c, pj, st, a, l, s in ITEMS)
_opr = sum(a for n, c, pj, st, a, l, s in ITEMS if "OpenAI" in c and st == "realized")
_totr = sum(a for n, c, pj, st, a, l, s in ITEMS if st == "realized")
w("**OpenAI 단일 counterparty 집중도** — 분모를 두 가지로 나눠 본다:")
w("")
w("| 분모 | OpenAI | 전체 | 집중도 |")
w("|---|---:|---:|---:|")
w(f"| 명목 전체 | {_op:,} | {_tot:,} | **{_op/_tot*100:.1f}%** |")
w(f"| realized 만 | {_opr:,} | {_totr:,} | **{_opr/_totr*100:.1f}%** |")
w("")
w("명목 전체 기준 집중도가 99% 를 넘는 것은 **구속력 없는 negotiating 두 건이 분모를 지배**하기 때문이다. "
  "→ 이 숫자를 단독 인용하면 과장이다. **realized 기준 집중도가 실질 값**이며, 그것도 88% 대로 높다.")
w("")
w("**범위에서 제외한 항목:**")
w("")
for n, why in EXCLUDED:
    w(f"- **{n}** — {why}")
w("")
w("**공급측(별도 축, 수요 벤더파이낸싱과 성격이 다름):**")
w("")
for n, c, pj, st, amt, src in SUPPLY:
    w(f"- {n} — {c} · {st} · {amt:,} $M · {src}. **선급 = 현금 선지출, 능력은 후행**")
w("")
w("---")
w("")
w("## 2. ② 3분류")
w("")
w("| 단계 | 항목 | 금액($M) | 구속력 |")
w("|---|---|---:|---|")
tot = {}
for st in ("realized", "committed(조건부)", "negotiating"):
    subs = [(n, a) for n, c, pj, s, a, l, src in ITEMS if s == st]
    tot[st] = sum(a for _, a in subs)
    for n, a in subs:
        w(f"| {st} | {n} | {a:,} | "
          + ("B/S 계상 완료" if st == "realized" else
             "**조건부** — NAVER 의 별도 ≥$9B PF 확보가 선행조건, 2026-10-30 종결 예정"
             if st.startswith("committed") else "**없음** — 협의 단계, 금액·시점·조건 전부 미확정") + " |")
    w(f"| **{st} 소계** | | **{tot[st]:,}** | |")
w("")
w(f"**수요측 합계 {sum(tot.values()):,} $M.** 구성: realized **{tot['realized']/sum(tot.values())*100:.1f}%** · "
  f"committed(조건부) **{tot['committed(조건부)']/sum(tot.values())*100:.1f}%** · "
  f"negotiating **{tot['negotiating']/sum(tot.values())*100:.1f}%**.")
w("")
w("→ **negotiating 이 압도적이다.** 이 사실 하나가 §4 실패조건을 결정한다.")
w("")
w("---")
w("")
w("## 3. ③ 매출 인식기간 — **고객 capex 커밋 ≠ NVDA 인식매출**")
w("")
w("| 프로젝트 | 물리적 일정(원장) | NVDA 매출 인식 시점 |")
w("|---|---|---|")
w("| 오하이오 10GW DC | 총 >$500B · **1단계 ~800MW 2028** | 1단계도 **FY2029(달력 2028)** 이후. 10GW 전체는 다년 |")
w("| NAVER AI팩토리 | 55MW H1-2027 → 100MW 2027말 → **200MW 2028** | **FY2028~** 분산 |")
w("| OpenAI 칩 금융 $350B | 협의 단계, 일정 미공표 | **미정** |")
w("")
w("⚠️ **핵심: 리드스루가 발생한다 해도 대부분 FY2028 이후다.** "
  "즉 T-1 이 겨냥하는 구간은 **T-3 내재 성장경로의 FY28~FY32 구간과 정확히 겹친다.** "
  "이것이 T-1 이 T-3 에 주는 유일한 구조적 입력이다.")
w("")
w(f"**T-3 내재 경로 (성장배수 {GM:.3f}x) 의 매출:**")
w("")
w("| 연도 | FY28E | FY29E | FY30E | FY31E | FY32E | 5년 누적 |")
w("|---|---:|---:|---:|---:|---:|---:|")
w("| 매출($M) | " + " | ".join(f"{v:,.0f}" for v in REVPATH) + f" | **{CUM_REV:,.0f}** |")
w("")
_lead = sum(a for n, c, pj, st, a, l, src in ITEMS if l)
w(f"**매출 리드스루 가능 항목은 $350B(OpenAI 칩 금융) 하나뿐**이며, "
  f"이는 T-3 내재 경로의 5년 누적 매출 {CUM_REV:,.0f} $M 대비 **{_lead/CUM_REV*100:.1f}%** 다. "
  "$250B 보증은 **DC 건설·리스 대상이라 NVDA 매출로 직접 환산되지 않는다.**")
w("")
w("---")
w("")
w("## 4. ④ 실패조건 판정 — **밴드 하단 = 0**")
w("")
w("Codex P2-2 규율: **밴드 폭이 아니라 밴드 하단이 T-4 판정 임계를 넘는지**로 유용성을 판정한다.")
w("")
w("| | 하단 | 상단 |")
w("|---|---:|---:|")
w(f"| realized (B/S 계상 완료) | {tot['realized']:,} | {tot['realized']:,} |")
w(f"| + committed(조건부) | {tot['realized']:,} ← **조건 미충족 시 0** | {tot['realized']+tot['committed(조건부)']:,} |")
w(f"| + negotiating | {tot['realized']:,} ← **협의 결렬 시 0** | {sum(tot.values()):,} |")
w("")
w(f"**밴드 = [{tot['realized']:,} , {sum(tot.values()):,}] $M — 폭이 {sum(tot.values())/tot['realized']:.1f}배다.** "
  "하단은 **이미 B/S 에 있는 realized 뿐**이고, 하단을 넘는 부분은 전부 구속력이 없다.")
w("")
w("→ **판정: 정량 밴드로서 T-4 에 기여하지 못한다.** 상단은 협의 성사 여부라는 "
  "**단일 이진 사건**에 걸려 있어 확률을 붙이면 그것이 곧 결론이 된다(순환). "
  "**정성 강등한다.**")
w("")
w("---")
w("")
w("## 5. 그래서 T-4 에 넘기는 것")
w("")
w("### (A) 정량 — realized 익스포저만 (전부 B/S 계상 완료, 원장 §0.2)")
w("")
w("| 지표 | 값 | 분모 대비 |")
w("|---|---:|---|")
w(f"| 지분증권 합계 | {BS['지분증권 합계']:,} | TTM 매출의 **{BS['지분증권 합계']/BS['TTM 매출']*100:.1f}%** |")
w(f"| 비시장성 증권 | {BS['비시장성 증권']:,} | 지분증권의 {BS['비시장성 증권']/BS['지분증권 합계']*100:.1f}% |")
w(f"| Q1 비시장성 취득 | {BS['Q1 비시장성 취득']:,} | Q1 FCF 의 **{BS['Q1 비시장성 취득']/BS['Q1 FCF']*100:.1f}%** |")
w(f"| Q1 지분평가익(세전) | {BS['Q1 지분평가익(세전)']:,} | Q1 GAAP NI 의 **{BS['Q1 지분평가익(세전)']/BS['Q1 GAAP NI']*100:.1f}%** |")
w(f"| 수요측 realized 지분 | {tot['realized']:,} | FY27E 매출({rev:,})의 **{tot['realized']/rev*100:.1f}%** |")
w("")
w("**이 수치들은 협의 성사 여부와 무관하게 이미 성립한다.** T-4 는 여기까지만 정량으로 쓴다.")
w("")
w("### (B) 정성 — negotiating 리스크")
w("")
w("- **단일 실패점:** OpenAI 자금조달. 수요측 명목 익스포저의 "
  f"**{_op/_tot*100:.1f}%** 가 이 한 counterparty 에 걸려 있다.")
w("- **시장이 이미 가격에 반영한 흔적:** 2026-07-27 $250B 보증 협의 보도 당일 "
  "**CDS +14bp(0.82%, 활성거래 개시 이후 최대 일간 변동) · 주가 −4.99%.** "
  "⚠️ 계획 §5 V4 규율대로 **CDS 가산과 Ke 가산을 병행하면 이중계상**이다 — 같은 사건이다.")
w("- **강세·약세가 같은 사실에 수렴:** Burry(숏 증량, \"부외 순환거래\") 와 "
  "Bernstein Rasgon(강세론자, $250B 백스톱 우려) 이 **같은 항목**을 지적한다.")
w("")
w("### (C) T-3 연결 — 정직한 답")
w("")
w("T-3 §0.4-1 이 남긴 질문은 \"현재가가 요구하는 20% EBITDA CAGR 의 자금조달 구조\" 였다. "
  "T-1 이 줄 수 있는 답은 다음까지다:")
w("")
w(f"- **확인 가능한 자기조달 비중은 한 자릿수 후반%** — 수요측 realized {tot['realized']:,} $M / "
  f"FY27E 매출 {rev:,} $M = **{tot['realized']/rev*100:.1f}%**.")
w(f"- **나머지는 미확정.** 리드스루 가능 최대치 $350B 는 T-3 내재 경로 5년 누적 매출의 "
  f"{_lead/CUM_REV*100:.1f}% 이지만 **구속력이 없어 하단 0** 이다.")
w("- → **\"자기 수요를 자기 대차대조표로 조달하는가\" 라는 테제는 현재 데이터로 "
  "정량 판정할 수 없다.** 확정 사실은 realized 뿐이고, 그것만으로는 20% CAGR 을 설명하지도 "
  "부정하지도 못한다.")
w("")
w("---")
w("")
w("## 6. 사전등록 조항 대조")
w("")
w("| 조항 | 판정 |")
w("|---|---|")
w("| §0.4-2 \"3분류를 못 하면 정성 강등\" | **3분류는 됐다.** 이 조항으로 강등된 것이 아니다 |")
w("| Codex P2-2 \"밴드 하단이 판정 임계를 넘는지\" | **넘지 못한다 → 이 조항으로 정성 강등** |")
w("| §0.3 \"1일 타임박스\" | 준수. 원장 내 사실만 사용, 신규 조회 0건 |")
w("| §0.3 \"T-3 을 막지 않는다\" | 준수. T-3 은 이미 종결(rev-7 PASS) |")
w("")
w("⚠️ **두 조항을 구분해 기록한다.** \"3분류 실패\" 와 \"밴드 하단 미달\" 은 다른 실패다. "
  "전자는 정보 부족, 후자는 **정보가 있어도 구속력이 없다**는 구조적 사실이다. "
  "프린트 후 협의가 확정되면 후자는 해소될 수 있으나 전자는 해당 없음이다.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "T1_vendor_financing_nvda_2026-08-10.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
