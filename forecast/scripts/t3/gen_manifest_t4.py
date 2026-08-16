"""MANIFEST ADDENDUM — NVDA 2026-08-13 T-4 초안·T-2 ①③ (append-only, 승인 범위 5항목)

기존 매니페스트(08-09 본문·rev3 부록·08-10 실행 부록)는 수정하지 않는다.
모든 해시는 파일에서 직접 계산 — 손타이핑 0.
"""
from __future__ import annotations
import hashlib, os, sys

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
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


FILES = [
    ("reports/T4_verdict_draft_nvda_2026-08-13.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13.md", "T4_verdict_draft_nvda_2026-08-13.md"),
     "T-4 판정 초안 **rev-4** — \"적정 상단~고평가 · 7/10 as-run DCF 기준 안전마진 부재 확정 · "
     "확신도 낮음\". 정정 ①~⑤ 반영: 단일축 조건부 해·as-run 기준 라벨·RC 약화-비반전·"
     "RC-3′ 서술 강등(판정 트리거는 RC-1′·RC-2′ 2개)·역방향 문장 RC-1′·RC-2′ 한정"),
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md"),
     "감사추적 — rev-1 원본 보존 (Codex CONDITIONAL 대상판, 수정·삭제 금지)"),
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md"),
     "감사추적 — rev-2 원본 보존 (Codex CONDITIONAL: ①~③ 반영 확인·잔여 ④, 수정·삭제 금지)"),
    ("reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md",
     ("../../reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md",
      "T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md"),
     "감사추적 — rev-3 원본 보존 (Codex CONDITIONAL: ④ 반영 확인·잔여 ⑤ 문구 1건, 수정·삭제 금지)"),
    ("reports/T2_buckets_1_3_nvda_2026-08-13.md",
     ("../../reports/T2_buckets_1_3_nvda_2026-08-13.md", "T2_buckets_1_3_nvda_2026-08-13.md"),
     "T-2 ①(경상 순이자 앵커 +488@mid)·③(UNFORECASTABLE 선언) — 진단 전용, T-4 비오염. ② 는 13F 후"),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md"),
     "감사추적 — rev-1 검증 발주 시점 사본 (Codex 판정: CONDITIONAL)"),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md"),
     "감사추적 — rev-2 검증 발주 시점 사본 (Codex 판정: CONDITIONAL, ①~③ 반영 확인)"),
    ("HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md",
      "HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md"),
     "감사추적 — rev-3 검증 발주 시점 사본 (Codex 판정: CONDITIONAL, ④ 반영 확인·잔여 ⑤)"),
    ("scripts/t3/gen_t4.py", ("gen_t4.py",), "T-4 생성기 rev-4 (입력 5건 해시 fail-closed 검증 내장)"),
    ("scripts/t3/gen_t2.py", ("gen_t2.py",), "T-2 ①③ 생성기 (후보 v2 해시 검증 내장)"),
    ("scripts/t3/gen_handoff_t4.py", ("gen_handoff_t4.py",),
     "핸드오프 생성기 (UNVERIFIABLE 미유입 기계 검사 F-5 내장)"),
]

w("# MANIFEST ADDENDUM — NVDA 2026-08-13 (T-4 초안 · T-2 ①③)")
w("")
w("> `MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md` 에 이어 append. **기존 매니페스트 무수정** (P0 정책).")
w("> 모든 해시는 `scripts/t3/gen_manifest_t4.py` 가 파일에서 직접 계산했다 — 손타이핑 0.")
w("> 재현: `cd scripts/t3 && LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest_t4.py`")
w("")
w("**승인 범위 (사용자 2026-08-13, 5항목):** ① 08-10 매니페스트 읽기 전용 검증·입력 고정 "
  "② T-4 초안(GAAP OP·OPM 만 정량 채점, T-3/V2/T-1 은 조건·반증요건) "
  "③ 반증조건 3개 관측 가능성 검증·UNVERIFIABLE 결론 제외 "
  "④ T-2 ①③ 별도 진단(T-4 비오염) ⑤ 본 부록 append-only 기록. **전항 이행.**")
w("")
w("**입력 고정 결과:** `gen_t4.py` 가 08-10 매니페스트 등재 해시 4건 + 후보 v2 `60cc8d23…bfef` 를 "
  "재계산 대조 — **전건 일치** (불일치 시 생성이 실패하는 fail-closed 구조).")
w("")
w("**Codex 검증 이력 (T-4):** rev-1 `CONDITIONAL` — 기계 검증(해시 11건·결정성·입력 고정·"
  "UNVERIFIABLE 미유입 검사·RC-1′/2′ 관측 가능성) 전건 PASS, 판정 논리 정정 3건 요구 → rev-2 반영: "
  "① 축 결합 논리(\"동시 성립\" → 단일-변수 조건부 해·조합 비식별) ② \"안전마진 부재 확정\" → "
  "\"7/10 as-run DCF 기준\" 한정 ③ RC-1′/2′ = 약화 관측(반전 트리거 아님). "
  "rev-2 `CONDITIONAL` — ①~③ 정확 반영·재생성 해시 일치 확인, 잔여 1건 → rev-3 반영: "
  "④ RC-3′ 수치 임계값 사전등록 부재 → 서술적 약화 신호로 강등, **관측 판정은 RC-1′·RC-2′ 2개로만** "
  "(사용자 승인 2026-08-13; 임계값 사전등록 대안은 N=1·비정상 잔액이라 기각). "
  "rev-3 `CONDITIONAL` — ④ 반영·diff 국한성·수치 불변·F-2 파괴시험 전건 PASS, 잔여 문구 1건 → "
  "**rev-4 반영**: ⑤ §3 역방향 문장 \"RC 전부 미발화\" → \"RC-1′·RC-2′ 모두 미발화\" (Codex 권장 문구 채택, "
  "RC-3′ 를 판정 경로에서 완전 제거). "
  "rev-1~3 원본은 `_rev1/_rev2/_rev3_superseded.md` 로 보존. 핸드오프 rev-4 는 본 부록 이후 생성 — "
  "해시는 핸드오프 자신의 §1 과 세션 보고에 기록.")
w("")
w("| 파일 | sha256 | bytes | NUL | 비고 |")
w("|---|---|---:|:--:|---|")
for label, cands, note in FILES:
    p = locate(*cands)
    if p is None:
        w(f"| `{label}` | **파일 없음** | — | — | {note} |")
        continue
    data = open(p, "rb").read()
    nul = "clean" if b"\x00" not in data else "NUL!"
    w(f"| `{label}` | `{sha(p)}` | {len(data):,} | {nul} | {note} |")
w("")
w("**미착수 (예정):** T-2 ② 시장성 마크 — 13F(06-30 기준) 수신 후 08-14 · "
  "Freeze-A — 08-13 후보 v2 `variant_2a` 재현 검증 · T-4 최종 — 08-28~29 (§6.1 3단 분리 채점 이후).")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
