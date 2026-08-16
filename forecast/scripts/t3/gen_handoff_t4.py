"""HANDOFF — Codex 적대적 검증 요청 생성기: T-4 판정 초안 rev-1 (+ T-2 ①③ · 매니페스트 부록)

규약 (handoff-script-generated-numbers):
- 손타이핑 0 — 모든 해시는 파일에서 계산, 모든 T-3 계열 수치는 동일 모듈로 재계산.
- 원장 A 인용 상수는 해시 고정된 T-1/T-2 문서의 인용값만 사용하며 [인용] 표기.
- 바이트 결정성: LF 고정, 콘솔 비의존(VERBOSE 옵트인), 최종 sha256 라인 ASCII.
- §5 의 UNVERIFIABLE 미유입 검사는 fail-closed — 검사 실패 시 본 문서는 생성되지 않는다.
"""
from __future__ import annotations
import hashlib, json, os, re, sys
import bvt_dcf as B
from bvt_dcf import _ev
from t3_reverse_dcf import ANCHORS, BASE_YEAR, PRICE_NOW, PRICE_PT
from t3_final import solve, ps

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


# ── 검증 대상 6 + 입력 5 ───────────────────────────────────────────────────────
TARGETS = [
    ("reports/T4_verdict_draft_nvda_2026-08-13.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13.md", "T4_verdict_draft_nvda_2026-08-13.md")),
    ("reports/T2_buckets_1_3_nvda_2026-08-13.md",
     ("../../reports/T2_buckets_1_3_nvda_2026-08-13.md", "T2_buckets_1_3_nvda_2026-08-13.md")),
    ("MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md",
     ("../../MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md", "MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md")),
    ("scripts/t3/gen_t4.py", ("gen_t4.py",)),
    ("scripts/t3/gen_t2.py", ("gen_t2.py",)),
    ("scripts/t3/gen_manifest_t4.py", ("gen_manifest_t4.py",)),
]
AUDIT = [
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md")),
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md")),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md")),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md")),
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md")),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md")),
]
INPUTS = [
    ("reports/MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md",
     ("../../reports/MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md", "MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md")),
    ("reports/nvda_2026q2_freeze_a_candidate_v2.json",
     ("../../reports/nvda_2026q2_freeze_a_candidate_v2.json", "nvda_2026q2_freeze_a_candidate_v2.json")),
    ("reports/T3_nvda_2026-08-10.md", ("../../reports/T3_nvda_2026-08-10.md", "T3_nvda_2026-08-10.md")),
    ("reports/V2_rf_overlay_nvda_2026-08-10.md",
     ("../../reports/V2_rf_overlay_nvda_2026-08-10.md", "V2_rf_overlay_nvda_2026-08-10.md")),
    ("reports/T1_vendor_financing_nvda_2026-08-10.md",
     ("../../reports/T1_vendor_financing_nvda_2026-08-10.md", "T1_vendor_financing_nvda_2026-08-10.md")),
]
H = {}
for label, cands in TARGETS + INPUTS + AUDIT:
    p = locate(*cands)
    if p is None:
        print(f"FATAL: {label} not found")
        raise SystemExit(1)
    H[label] = (sha(p), os.path.getsize(p), p)

T4_TEXT = open(H["reports/T4_verdict_draft_nvda_2026-08-13.md"][2], encoding="utf-8").read()
T2_TEXT = open(H["reports/T2_buckets_1_3_nvda_2026-08-13.md"][2], encoding="utf-8").read()
CAND = json.load(open(H["reports/nvda_2026q2_freeze_a_candidate_v2.json"][2], encoding="utf-8"))
V2A = CAND["variant_2a_mechanical_engine_shares"]
OP_BASE, OPM_BASE, OP_W = V2A["base"]["op"], V2A["base"]["op_margin"], V2A["weighted"]["op"]

# ── T-3 계열 수치 재계산 (gen_t4.py 와 동일 경로 — 인용 아님) ────────────────────
FY = ANCHORS["FY27E"]
eb, da, rev, wc, p, nd = (FY["ebitda_base"], FY["da_base"], FY["revenue"],
                          FY["wacc"], FY["dcf_p"], FY["net_debt"])
wp = FY["wacc_p"]
R = solve(FY, PRICE_NOW)
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
ERP_FLIP = KE - RF_V2                      # ERP <= 이 값이면 βL >= 1
EV0 = _ev(eb, da, rev, wc, p, BASE_YEAR)
PS0 = ps(FY, EV0)
GAP = (PRICE_NOW / PS0 - 1) * 100
MODEL_CAGR = ((1.18 * 1.13 * 1.09 * 1.06 * 1.04) ** 0.2 - 1) * 100
# [인용] 원장 A 인용값 — T-1 문서(해시 위 표) 등재값. 재계산 대상 아님.
T1_REALIZED, T1_NEG, T1_OPENAI_CONC = 34_060, 600_000, 88.1

# ── §5 기계 검사: UNVERIFIABLE 미유입 (fail-closed) ─────────────────────────────
m5 = re.search(r"## §5\..*?(?=\n---\n)", T4_TEXT, re.S)
if m5 is None:
    print("FATAL: T4 §5 section not found")
    raise SystemExit(1)
S5 = m5.group(0)
FORBIDDEN = ["UNVERIFIABLE", "600,000", "34,060", "CAGR", "βL", "§0.4-1", "BASIS_UNKNOWN"]
REQUIRED_S5 = [f"{OP_BASE:,.0f}", f"{OPM_BASE*100:.3f}", f"{OP_W:,.0f}"]
EXCL_ITEMS = ["out-year 컨센", "negotiating", "(d) 컨센 HIT/MISS", "βL 절대수준"]
checks = []
for tok in FORBIDDEN:
    checks.append((f"§5 정량 훅에 `{tok}` 부재", tok not in S5))
for tok in REQUIRED_S5:
    checks.append((f"§5 정량 훅 수치 `{tok}` = 후보 v2 재계산값", tok in S5))
for item in EXCL_ITEMS:
    checks.append((f"§2 제외표에 \"{item}\" 등재", item in T4_TEXT.split("## §3")[0]))
checks.append(("T-2 §3 \"T-4 정량 채점에 공급 수치 0건\" 선언 존재", "0건" in T2_TEXT and "비오염" in T2_TEXT))
if not all(ok for _, ok in checks):
    print("FATAL: UNVERIFIABLE non-ingestion check FAILED (fail-closed)")
    for name, ok in checks:
        if not ok:
            print("  FAIL:", name)
    raise SystemExit(1)

# ═══════════════════════════════════════════════════════════════════════════════
w("# HANDOFF — Codex 적대적 검증 요청: T-4 판정 초안 **rev-4** (NVDA, 2026-08-13)")
w("")
w("> 역할 분담(사용자 확정): **이 세션 저술 · Codex 적대적 검증.** "
  "rev-1 `CONDITIONAL`(①~③) → rev-2 `CONDITIONAL`(①~③ 확인, 잔여 ④) → rev-3 `CONDITIONAL`"
  "(④ 확인·diff 국한성·수치 불변·F-2 파괴시험 전건 PASS, 잔여 ⑤ 문구 1건) → 본 rev-4 는 "
  "**⑤ 반영판**이다. 요청 초점: **⑤ 한 문장의 반영 확인 + 그 외 무변경 확인.**")
w("> 본 핸드오프의 모든 해시는 `scripts/t3/gen_handoff_t4.py` 가 파일에서 계산했고, "
  "T-3 계열 수치는 동일 모듈(`t3_final.solve` 등)로 **재계산**했다 — 손타이핑 0. "
  "[인용] 표기 3건만 T-1 문서(해시 고정) 등재값이다.")
w("")
w("---")
w("")
w("## §0. 정정 이력 (Codex 지적 → 반영 위치)")
w("")
w("| # | Codex 지적 | 반영 | 상태 |")
w("|---|---|---|---|")
w("| C-① | \"β<1 **그리고** 20% CAGR 동시 성립\"은 T-3 자기 체계와 모순 — 각 역산 축은 "
  "**단일-변수 조건부 해** | rev-2: §3 축 해석 주 신설 + 근거 2 재작성(OR·조합 비식별) | "
  "✅ rev-2 에서 Codex 확인 |")
w("| C-② | \"안전마진 부재 확정\"은 절대 명제로 읽힘 | rev-2: \"**7/10 as-run DCF 기준**\" 재라벨 + "
  "상대 명제 명문화 | ✅ rev-2 에서 Codex 확인 |")
w("| C-③ | RC-1′/RC-2′ 는 약화 관측이지 반전 트리거 아님 | rev-2: \"뒤집는→약화\" 전면 교체 + "
  "1분기 관측 한계 명시 | ✅ rev-2 에서 Codex 확인 |")
w("| **C-④** | **RC-3′ \"유의하게 감소\"의 수치 임계값 미사전등록 — 라인이 공시돼도 기계적 판정 불가** | "
  "**rev-3 (본 판): RC-3′ 를 서술적 약화 신호로 강등, 관측 판정은 RC-1′·RC-2′ 2개로만 수행** "
  "(사용자 승인). 반영 위치: 헤더 이력 · §2 층 분리(반증요건 행에서 RC-3′ 를 별도 \"서술적 신호\" 행으로) · "
  "§3 약화 조건 문장 · §4 도입부 + RC-3′ 행(판정 불사용 사유 2건: 임계값 부재는 N=1·비정상 잔액이라 "
  "자의적 — T-2 ③ 논리 정합 · CFS 세분화 미보장) · §4 §0.4-4 대조(임계값 사전등록 시 복권 조건 명시) · "
  "§5 최종판 문장. 라인 부재 시 `UNVERIFIABLE` fail-closed 는 유지 | ✅ rev-3 에서 Codex 확인 |")
w("| **C-⑤** | **§3 역방향 문장 \"RC 전부 미발화\"가 RC-3′ 포함으로 읽힘 — RC-3′ 가 판정 경로에 잔존** | "
  "**rev-4 (본 판): \"역으로 RC-1′·RC-2′ 모두 미발화 + ERP ≥ 현행이면…\" 으로 한정** (Codex 권장 문구 채택) "
  "+ \"RC-3′ 는 이 역방향 경로에도 불포함\" 명시. 반영 위치: §3 약화 조건 문장 ⑵ 뒤 역방향 절 · 헤더 이력 | "
  "🔶 본 rev-4 검증 대상 |")
w("")
w("C-⑤ 외 수치·구조 변경 없음 — §4 재계산값은 rev-1~3 과 동일해야 한다(동일 모듈 재실행).")
w("")
w("## §1. 검증 대상 (6) · 입력 (5) · 감사추적 (6) — 최종 sha256")
w("")
w("| 구분 | 파일 | sha256 | bytes |")
w("|---|---|---|---:|")
for label, _ in TARGETS:
    h, n, _p = H[label]
    w(f"| 대상 | `{label}` | `{h}` | {n:,} |")
for label, _ in INPUTS:
    h, n, _p = H[label]
    w(f"| 입력 | `{label}` | `{h}` | {n:,} |")
for label, _ in AUDIT:
    h, n, _p = H[label]
    w(f"| 감사 | `{label}` | `{h}` | {n:,} |")
w("")
w("감사 사본 6건은 무수정 보존 — rev-3 사본과 현행 rev-4 의 diff 가 §0 C-⑤ 만 포함하는지로 "
  "\"그 외 무변경\"을 기계 확인할 수 있다.")
w("")
w("입력 5건 중 md 4건의 해시는 `MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md` 등재값과, "
  "후보 v2 는 rev-3b 등재 기대값과 일치해야 한다(§3 의 fail-closed 지점이 이를 강제).")
w("")
w("## §2. 재현 명령 (결정성 포함)")
w("")
w("```")
w("cd scripts/t3")
w("LC_ALL=C PYTHONIOENCODING=ascii python3 gen_t4.py          # ×2 동일해야 함")
w("LC_ALL=C PYTHONIOENCODING=ascii python3 gen_t2.py          # ×2 동일해야 함")
w("LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest_t4.py # ×2 동일해야 함")
w("```")
w("")
w("기대 산출 해시 = §1 대상 표의 값 (본 세션에서 샌드박스·디바이스 양쪽 ×2 비트 동일 확인, CRLF 0). "
  "주의: 생성물은 cwd 에 떨어진다 — 리포 사본과 diff 후 strays 는 "
  "`_to_delete/t3_stray_20260813/` 로 이동(마운트 unlink 불가).")
w("")
w("## §3. fail-closed 지점 — 어디가 실패하도록 설계됐는가")
w("")
w("| # | 위치 | 무엇이 실패를 강제하는가 |")
w("|---|---|---|")
w("| F-1 | `gen_t4.py` [범위 1] | 08-10 매니페스트 등재 해시 4건을 정규식으로 파싱해 실제 파일 해시와 대조 — "
  "1건이라도 불일치·행 부재·파일 부재면 `SystemExit(1)`, 문서 미생성 |")
w("| F-2 | `gen_t4.py` [범위 1] | 후보 v2 `60cc8d23…bfef` 기대값 대조 — 불일치 시 중단 |")
w("| F-3 | `gen_t2.py` 서두 | 동일한 후보 v2 해시 게이트 |")
w("| F-4 | T-4 §4 RC-3′ | 프린트 PR 에 CFS 비시장성 취득 라인 부재 시 **RC-3′ 자체를 UNVERIFIABLE 로 강등**, "
  "판정은 RC-1′·RC-2′ 2개로만 갱신 (문서에 사전 등록) |")
w("| F-5 | `gen_handoff_t4.py` §5 검사 | UNVERIFIABLE 미유입 기계 검사 실패 시 본 핸드오프 미생성 |")
w("")
w("**제안 파괴 시험:** 후보 v2 JSON 사본의 1바이트를 바꾸고 gen_t4.py 를 실행하면 F-2 로 "
  "즉시 중단되어야 한다(임시 디렉터리에서 수행 권장 — 리포 원본 무수정).")
w("")
w("## §4. 판정 문장별 근거 · 반증조건 매핑")
w("")
w("판정문(T-4 §3, rev-2): **\"고평가 쪽 기울기 — 적정 상단 ~ 고평가. 7/10 as-run DCF 기준 "
  "안전마진 부재는 확정, 고평가 확신도는 낮음.\"** 문장 단위로 분해한다:")
w("")
w("| # | 판정 문장 | 근거 (재계산값) | 근거 출처 | 연동 반증조건 | 무엇이 관측되면 약화되는가 |")
w("|---|---|---|---|---|---|")
w(f"| V-1 | \"**7/10 as-run DCF 기준** 안전마진 부재는 확정\" (C-② 반영: 앵커 상대 명제) | "
  f"7/10 as-run 연결 DCF **${PS0:.2f}** vs 현재가 ${PRICE_NOW} "
  f"= **+{GAP:.1f}%** | 앵커 재계산 (`_ev`+`ps`, eaf2dfa as-run) — §2-1 준수: 기존 산출 인용, 새 공정가치 아님 | "
  "(없음 — 이미 관측된 가격 사실) | 가격 하락 또는 as-run 앵커 자체의 결함 발견 뿐 |")
w(f"| V-2 | \"고평가 쪽 **기울기**\" (방향, C-① 반영) | **단일축 조건부 해** (각각 타 축 모델값 고정, "
  f"단독 설명 시 필요 수준): βL **{BETA:.3f}**(<1, rf {RF_V2}%·ERP {ERP}%) **또는** 5y EBITDA CAGR "
  f"**{CAGR*100:.2f}%**(모델 {MODEL_CAGR:.2f}%의 {GM:.3f}배) **또는** 마진 **{MG*100:.2f}%**(경제적 불능) — "
  "**축 조합은 비식별** | `solve()` 재계산 (T-3 rev-7 체계) | "
  "**판정:** RC-1′ (성장 확인) · RC-2′ (마진 압력 부재) / **서술:** RC-3′ (자기조달 완화, C-④) | "
  "RC-1′·2′ 발화 시 기울기 약화(반전 아님). "
  f"ERP ≤ **{ERP_FLIP:.2f}%** 갱신 시 β<1 경로 소멸 |")
w(f"| V-3 | 〃 (반대 방향 사실) | T-1 realized **{T1_REALIZED:,}** $M = FY27E 매출의 "
  f"**{T1_REALIZED/rev*100:.1f}%** [인용] · realized 의 **{T1_OPENAI_CONC}%** OpenAI 집중 [인용] · "
  "CDS +14bp [인용] | T-1 문서 (해시 §1) — 자본비용을 **높이는** 방향 | RC-3′ (서술적 신호, C-④) | "
  "CFS 취득 라인 감소 관측 시 **서술적으로만** 약화 — 판정 트리거 아님 |")
w(f"| V-4 | \"고평가 **확신도는 낮음**\" (한계) | 성장 축 판정 불능 — out-year 컨센 부재(§0.4-1), "
  f"negotiating {T1_NEG:,} $M 구속력 없음 [인용] | T-3 §0.4-1 · T-1 §2 | (없음) | "
  "**어떤 RC 조합도 \"고평가 확정\" 으로 상향 불가** — 성장 축 UNVERIFIABLE 해소 전까지 |")
w("| V-5 | 약화 조건 문장 (§3 말미, C-③·C-④·C-⑤ 반영) | RC-1′·RC-2′ 발화 → 기울기 **약화** (반전 아님 — "
  "1분기 관측은 성장축 UNVERIFIABLE 미해소; RC-3′ 는 서술적 참고) · **RC-1′·RC-2′ 모두 미발화** + "
  "ERP ≥ 현행 → 기울기 강화(단 \"고평가 확정\" 상향 금지; RC-3′ 는 역방향 경로에도 불포함) | — | "
  "RC-1′·RC-2′ (판정) | **비대칭 명시**: RC 미발화는 고평가를 증명하지 않음(N=1 규약) — "
  "rev-4 는 C-⑤ 한 문장만 추가 반영 |")
w("")
w("## §5. UNVERIFIABLE 미유입 경로 — 기계 검사 결과")
w("")
w("정량 판정(=프린트 채점 훅, T-4 §5)이 소비하는 수치는 후보 v2 `variant_2a` 의 3개뿐이다: "
  f"base OP **{OP_BASE:,.0f}** · OPM **{OPM_BASE*100:.3f}%** · 확률가중 OP **{OP_W:,.0f}**. "
  "UNVERIFIABLE 4항목은 §2 제외표와 §3 [한계] 서술에만 존재한다. "
  "본 생성기가 T-4 §5 절 텍스트를 파싱해 검사했다 (실패 시 본 문서 미생성 — F-5):")
w("")
w("| 검사 | 결과 |")
w("|---|---|")
for name, ok in checks:
    w(f"| {name} | {'PASS' if ok else 'FAIL'} |")
w("")
w("검사의 한계(자가 신고): 토큰 부재 검사는 **표층 텍스트** 기준이다. 의미 수준의 유입 "
  "(예: UNVERIFIABLE 수치가 다른 이름으로 §5 에 재등장)은 Codex 의 독립 판독으로 보완돼야 한다.")
w("")
w("## §6. 검증 요청 (rev-4)")
w("")
w("| 축 | 요청 |")
w("|---|---|")
w("| **C-⑤ 반영 (핵심)** | §3 역방향 문장이 \"RC-1′·RC-2′ 모두 미발화\"로 한정됐는지 — 이로써 T-4 전문에서 "
  "RC-3′ 가 판정 경로(정방향·역방향 모두)에서 완전 제거됐는지 최종 확인 |")
w("| 무변경 확인 | rev-3 감사 사본과 diff — 변경이 C-⑤ 한 문장(및 rev 라벨·이력 표기)에 국한되는지. "
  f"§4 재계산값 동일성: WACC {IW:.2f}% → Ke {KE:.2f}% → βL {BETA:.3f} · CAGR {CAGR*100:.2f}% · "
  f"마진 {MG*100:.2f}% · ${PS0:.2f}/+{GAP:.1f}% · ERP 플립 {ERP_FLIP:.2f}% |")
w("| 결정성·해시 | §2 재현 ×2 = §1 해시 (기계 검증 본체는 rev-1~3 에서 PASS — 재확인은 이것으로 충분) |")
w("")
w("**자가 신고:** gen_manifest_t4.py 는 f-string 내 백슬래시 구문 오류 1건을 수정한 판이 최종이다"
  "(§1 해시가 최종판 기준). rev-1 의 V-5 자가수정 이력은 §0 C-③ 로 흡수됐다.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev4.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
