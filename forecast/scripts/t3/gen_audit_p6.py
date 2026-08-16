"""P-6 콘솔 비의존 감사 보고서 생성기 — 읽기 전용 스캔 결과의 목록화·분류.

스캔은 2026-08-14 디바이스 리포에서 수행(읽기 전용, os.walk + 정규식 휴리스틱). 결과 원본은
`reports/scan_console_safety_2026-08-14.json` 에 보존하며 본 생성기는 그 파일을 읽어 분류만 한다.
**본 감사는 목록화까지다 — 어떤 스크립트도 수정하지 않으며, 수정은 별도 승인 대상 (Codex 경계).**
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


SCAN = locate("../../reports/scan_console_safety_2026-08-14.json",
              "scan_console_safety_2026-08-14.json")
if SCAN is None:
    print("FATAL: scan json not found")
    raise SystemExit(1)
D = json.load(open(SCAN, encoding="utf-8"))
scan_sha = hashlib.sha256(open(SCAN, "rb").read()).hexdigest()

# 분류 규칙 (경로 접두 기준)
FROZEN_PREFIX = ("scripts/t3/", "scripts/nvda_2026q2_freeze_a_candidate")
PINNED_PREFIX = ("scripts/score_",)


def classify(f):
    if f.startswith(FROZEN_PREFIX):
        return "동결·해시 고정 — **무수정** (관찰만 기록)"
    if f.startswith(PINNED_PREFIX):
        return "채점 고정분 — 수정 시 P0 규약 검토 필요, 보류"
    return "활성 비동결 — **수정 후보** (별도 승인 대상)"


w("# AUDIT — 콘솔 비의존·개행 고정 감사 (P-6, 2026-08-14)")
w("")
w("> 채택 근거: Codex 판정 P-6 **ADOPT (P1)**, \"스캔은 읽기 전용; 수정은 별도 승인\". "
  "사용자 승인 2026-08-14. 트리거 결함: Freeze-A 관찰(후보 v2 생성기 ASCII 콘솔 종료 1).")
w(f"> 스캔 원본: `reports/scan_console_safety_2026-08-14.json` `{scan_sha[:16]}…` — "
  f"전체 {D['scanned_py']}개 .py 중 플래그 {len(D['findings'])}건. 휴리스틱 스캔이므로 "
  "오탐/미탐 가능 — 수정 착수 전 파일별 재확인 필요.")
w("")
w("검사 항목: ⑴ `print(` 라인의 비ASCII 문자 (ASCII 콘솔 크래시 위험) "
  "⑵ `open(..., 'w')` 에 `newline=` 부재 (Windows CRLF 오염 위험) "
  "⑶ 콘솔 가드(`reconfigure`/`errors=replace`)·VERBOSE 옵트인 유무.")
w("")
w("| 파일 | 비ASCII print | w() newline 부재 | 가드 | 분류 |")
w("|---|---:|---:|:--:|---|")
for f_ in sorted(D["findings"], key=lambda x: (classify(x["f"]), x["f"])):
    g = "✅" if f_.get("guard") else "—"
    w(f"| `{f_['f']}` | {f_['na_print']} | {f_['w_no_newline']} | {g} | {classify(f_['f'])} |")
w("")
w("## 분류 요약")
w("")
frozen = [f_ for f_ in D["findings"] if f_["f"].startswith(FROZEN_PREFIX)]
pinned = [f_ for f_ in D["findings"] if f_["f"].startswith(PINNED_PREFIX)]
active = [f_ for f_ in D["findings"] if not f_["f"].startswith(FROZEN_PREFIX + PINNED_PREFIX)]
w(f"- **동결·해시 고정 {len(frozen)}건 — 무수정.** `t3_reverse_dcf.py`(비ASCII print 11·newline 부재 1)와 "
  "후보 v1/v2 생성기(newline 부재)는 이미 검증된 산출물의 생성 경로다 — 재실행 시 UTF-8 콘솔·격리 "
  "디렉터리 규약으로 대응 (Freeze-A 보고서 §2 관찰과 동일 처리). `gen_freeze_a.py`·`gen_handoff_t4.py` 의 "
  "플래그는 가드된 실패-경로 print 로 산출물 무영향.")
w(f"- **채점 고정분 {len(pinned)}건 — 보류.** `score_amd`·`score_txn` 은 P0 커밋 고정 이력이 있어 "
  "수정 자체가 규약 검토 사안.")
w(f"- **활성 비동결 {len(active)}건 — 수정 후보 목록.** `generic_cli.py`(비ASCII print 4) · "
  "`pipeline/` 5개·`output/` 2개·`ai/extractor.py`(newline 부재 — 산출 파일 CRLF 오염 경로) · "
  "`scripts/diagnose_opex.py`·`scripts/verify_9q_sha.py`·`tests/test_frozen_integrity.py`(비ASCII print). "
  "**이 목록의 실제 수정은 본 감사 범위 밖 — 별도 승인 후 착수.**")
w("")
w("## 권고 (수정 승인 시 우선순위)")
w("")
w("1. `output/`·`ai/extractor.py`·`pipeline/` 의 `newline=` 부재 — **산출 파일 오염**(CRLF) 경로라 "
  "콘솔 크래시보다 우선. `open(..., 'w', encoding='utf-8', newline='\\n')` 통일.")
w("2. `generic_cli.py` 등 비ASCII print — 크래시는 콘솔 환경 의존이므로 차순위. "
  "CONVENTIONS_rev_audit.md §2 의 신규 생성기 요건(가드·errors=replace) 적용.")
w("3. 동결·채점 고정분은 영구 무수정 — 관찰 기록으로 종결.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 프로세스 감사 문서이다.*")

OUTP = "AUDIT_console_safety_nvda_2026-08-14.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
