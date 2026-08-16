"""MANIFEST ADDENDUM — 2026-08-14 개선 채택분 구현 (append-only). 기존 매니페스트 무수정."""
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
    ("docs/CONVENTIONS_verdict_authoring.md",
     ("../../docs/CONVENTIONS_verdict_authoring.md", "CONVENTIONS_verdict_authoring.md"),
     "P-1~P-4 규약: RC 3요소(관측원·임계값 사전등록·층 라벨)·역산 OR/비식별 서술·앵커 상대 라벨·"
     "pre-flight lint 경계(FAIL=구조 불변식만)"),
    ("docs/CONVENTIONS_rev_audit.md",
     ("../../docs/CONVENTIONS_rev_audit.md", "CONVENTIONS_rev_audit.md"),
     "P-5·P-8 규약: rev 갱신 5단계(_revN_superseded→덮어쓰기→supersede→§0 이력→diff 국한성)·"
     "크로스 환경 재생성 게이트(샌드박스 ×2 + 디바이스 ×1 비트 동일·CRLF 0)"),
    ("scripts/t3/preflight_lint.py", ("preflight_lint.py",),
     "P-4 구조 불변식 lint (L-1/3/6 FAIL·L-2/4/5 WARN). 검증: T-4 rev-4 무결(0/0), "
     "rev-1 에서 과거 결함 C-①(L-4)·C-②(L-5)·총칭(L-2) 검출, rev-3 에서 C-⑤ 검출"),
    ("reports/scan_console_safety_2026-08-14.json",
     ("../../reports/scan_console_safety_2026-08-14.json", "scan_console_safety_2026-08-14.json"),
     "P-6 스캔 원본 (디바이스 리포 139개 .py, 읽기 전용, 플래그 18건)"),
    ("reports/AUDIT_console_safety_nvda_2026-08-14.md",
     ("../../reports/AUDIT_console_safety_nvda_2026-08-14.md", "AUDIT_console_safety_nvda_2026-08-14.md"),
     "P-6 감사 보고서 — 동결 5건 무수정·채점 고정 2건 보류·활성 11건 수정 후보 목록화 "
     "(**수정은 별도 승인 대상**)"),
    ("scripts/t3/gen_audit_p6.py", ("gen_audit_p6.py",), "P-6 보고서 생성기"),
    ("HANDOFF_CODEX_efe_improvements_2026-08-14.md",
     ("../../HANDOFF_CODEX_efe_improvements_2026-08-14.md", "HANDOFF_CODEX_efe_improvements_2026-08-14.md"),
     "판단 요청 핸드오프 (Codex 판정의 대상 문서)"),
]

w("# MANIFEST ADDENDUM — 2026-08-14 (개선 채택분 구현: P-1~P-6·P-8)")
w("")
w("> `MANIFEST_ADDENDUM_nvda_2026-08-14_freeze_a.md` 에 이어 append. **기존 매니페스트 무수정** (P0 정책).")
w("> 모든 해시는 `scripts/t3/gen_manifest_conv.py` 가 파일에서 직접 계산 — 손타이핑 0.")
w("")
w("**Codex 판정 (2026-08-14):** P-1·P-2·P-3·P-4 `ADOPT P0` · P-5·P-6·P-8 `ADOPT P1` · "
  "P-7 `DEFER P2` (조건: 다음 신규 생성기와 함께 최소 genlib 도입 → 신규 2개 이상에서 인터페이스 검증 → "
  "기존 해시 고정 생성기는 영구 비이관). REJECT 없음. **사용자 승인 (2026-08-14): 구현 순서 ①~④ 전부.**")
w("")
w("**경계 준수 확인:** 계획 rev-3b 무개정 (08-28 T-4 최종은 현행 로컬 규약, 3요소 규격은 차기 템플릿부터) · "
  "기존 해시 고정 산출물·생성기 무수정 · P-6 은 읽기 전용 목록화까지 — 활성 스크립트 실수정은 "
  "별도 승인 대상으로 미착수 · genlib 미생성 (P-7 DEFER).")
w("")
w("| 파일 | sha256 | bytes | 비고 |")
w("|---|---|---:|---|")
for label, cands, note in FILES:
    p = locate(*cands)
    if p is None:
        w(f"| `{label}` | **파일 없음** | — | {note} |")
        continue
    w(f"| `{label}` | `{sha(p)}` | {os.path.getsize(p):,} | {note} |")
w("")
w("**lint 검증 기록 (P-4):** 현행 T-4 rev-4 → `RESULT PASS fail=0 warn=0`. 감사 사본 회귀 시험 — "
  "rev-1 → C-①(L-4 동시 성립)·C-②(L-5 앵커 부재)·총칭(L-2) 3건 검출, rev-3 → C-⑤(L-2 \"RC 전부\") 검출. "
  "즉 Codex 정정 5건 중 저술 시점 기계 검출 가능했던 유형을 실제 과거 문서에서 재현 검출함. "
  "오탐 교정 3건(인용문 내 총칭·부정문 내 \"고평가 확정\"·L-3 표식 규칙)은 lint 소스에 반영.")
w("")
w("**미착수 (별도 승인·별도 작업):** 활성 스크립트 콘솔/개행 수정 (AUDIT 권고 1·2) · P-7 genlib "
  "(다음 신규 생성기 시 재평가) · ERP 갱신 · NVDA 산출물 git 커밋 결정 · T-2 ② (새 세션).")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 프로세스 기록 문서이다.*")

OUTP = "MANIFEST_ADDENDUM_2026-08-14_conventions.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
