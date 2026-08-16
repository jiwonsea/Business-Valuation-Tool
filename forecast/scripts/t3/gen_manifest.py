"""MANIFEST ADDENDUM — NVDA 2026-08-10 실행 산출물 (P0 사실원장 정책: append-only)

기존 MANIFEST_nvda_2026-08-09.md / MANIFEST_ADDENDUM_..._rev3.md 는 수정하지 않는다.
본 스크립트는 08-10 실행분의 최종 해시를 파일에서 직접 계산해 기록한다 — 손타이핑 0.

주의: 대상 파일들과 같은 디렉터리 구조에서 실행해야 한다.
  cd scripts/t3 && python3 gen_manifest.py          (스크립트 해시는 cwd 에서)
대상 md 파일 경로는 ../../reports 및 ../../ 를 기본으로 하되, 없으면 cwd 에서 찾는다(샌드박스).
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
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def nul_clean(path):
    with open(path, "rb") as f:
        return b"\x00" not in f.read()


# (매니페스트 표기 경로, 후보 실경로들, 비고)
FILES = [
    ("reports/T3_nvda_2026-08-10.md",
     ("../../reports/T3_nvda_2026-08-10.md", "T3_nvda_2026-08-10.md"),
     "T-3 역방향 DCF rev-7 — Codex 검증 rev-1 FAIL→rev-4 PASS→rev-7 PASS"),
    ("reports/V2_rf_overlay_nvda_2026-08-10.md",
     ("../../reports/V2_rf_overlay_nvda_2026-08-10.md", "V2_rf_overlay_nvda_2026-08-10.md"),
     "V2 — 2026-08-07 UST 10Y 4.65% 확정, βL 0.874 (rf 해소·ERP 미해소)"),
    ("reports/BASIS_consensus_verification_nvda_2026-08-10.md",
     ("../../reports/BASIS_consensus_verification_nvda_2026-08-10.md",
      "BASIS_consensus_verification_nvda_2026-08-10.md"),
     "BASIS — 3/3 BASIS_UNKNOWN · 결정 ②((d) 영구 서술용 강등) · Codex PASS. "
     "⚠️ supersedes 초판 `a71ea3e9…be83`(결정 ②·재사용규칙 반영 전, 미배포 폐기)"),
    ("reports/T1_vendor_financing_nvda_2026-08-10.md",
     ("../../reports/T1_vendor_financing_nvda_2026-08-10.md",
      "T1_vendor_financing_nvda_2026-08-10.md"),
     "T-1 — 착수조건 3건 충족, 밴드 하단 34,060(realized)뿐 → 정성 강등"),
    ("HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md",
     ("../../HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md",
      "HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md"),
     "검증 요청 최종본 (rev-2~6 은 감사추적 보존)"),
    ("scripts/t3/bvt_dcf.py", ("bvt_dcf.py",), "BVT 엔진 포팅 (V1 게이트 검증)"),
    ("scripts/t3/t3_reverse_dcf.py", ("t3_reverse_dcf.py",), "앵커·축 정의"),
    ("scripts/t3/t3_final.py", ("t3_final.py",), "T-3 산출물 생성기"),
    ("scripts/t3/gen_handoff.py", ("gen_handoff.py",), "핸드오프 생성기"),
    ("scripts/t3/gen_v2.py", ("gen_v2.py",), "V2 생성기"),
    ("scripts/t3/gen_basis.py", ("gen_basis.py",), "BASIS 생성기"),
    ("scripts/t3/gen_t1.py", ("gen_t1.py",), "T-1 생성기"),
]

w("# MANIFEST ADDENDUM — NVDA 2026-08-10 실행 (T-3·V2·BASIS·T-1)")
w("")
w("> `MANIFEST_nvda_2026-08-09.md` 에 append. **기존 해시는 수정하지 않는다** (P0 사실원장 정책).")
w("> 본 부록의 모든 해시는 `scripts/t3/gen_manifest.py` 가 **파일에서 직접 계산**했다 — 손타이핑 0.")
w("> 재현: `cd scripts/t3 && LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest.py`")
w("")
w("**정보 컷오프:** INFO_CUTOFF_A(2026-08-09 23:59 KST) 불변. 08-10 산출물은 원장 A 사실 + "
  "컷오프 이내 1차 자료(2026-08-07 Treasury, NVDA 분기 보도자료)만 사용. "
  "컷오프 이후 관측치 노출은 각 문서의 '컷오프 위생' 절에 기록.")
w("")
w("**Codex 검증 이력:** T-3 rev-1 `FAIL` → rev-2 `CONDITIONAL PASS` → rev-4 `PASS` → "
  "rev-6 `FAIL`(정의 혼재) → **rev-7 `PASS`** · V2/BASIS 검증 `PASS`.")
w("")
w("| 파일 | sha256 | bytes | NUL | 비고 |")
w("|---|---|---:|:--:|---|")
missing = []
for label, cands, note in FILES:
    p = locate(*cands)
    if p is None:
        missing.append(label)
        w(f"| `{label}` | **파일 없음** | — | — | {note} |")
        continue
    w(f"| `{label}` | `{sha(p)}` | {os.path.getsize(p):,} | "
      f"{'clean' if nul_clean(p) else '⚠️ NUL'} | {note} |")
w("")
if missing:
    w(f"⚠️ 미발견 {len(missing)}건: " + ", ".join(f"`{m}`" for m in missing))
    w("")
w("**해시 정정 기록 (Codex 지적, 2026-08-12):** BASIS 문서의 세션 대화 인용 해시 "
  "`a71ea3e9…be83` 은 **결정 ②·재사용 규칙 반영 전 초판**이다. 유효 해시는 위 표의 값이며, "
  "이후 인용은 본 매니페스트를 기준으로 한다.")
w("")
w("**감사추적 보존 (무수정):** `HANDOFF_..._rev2.md` `2d9d1c13…` · `_rev3.md` `8bbb5355…` · "
  "`_rev4.md` `07502322…` · `_rev5.md` `bd315249…` · `_rev6.md` `1bffa4ca…` — "
  "각 rev 발주 시점 사본. 수정·삭제 금지.")
w("")
w("---")
w("")
w("*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*")

OUTP = "MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md"
with open(OUTP, "w", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(O))
print("sha256", hashlib.sha256(open(OUTP, "rb").read()).hexdigest(), OUTP)
