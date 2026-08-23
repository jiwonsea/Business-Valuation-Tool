# MANIFEST ADDENDUM — NVDA 2026-08-14 (Freeze-A)

> `MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md` 에 이어 append. **기존 매니페스트 무수정** (P0 정책).
> 모든 해시는 `scripts/t3/gen_manifest_fa.py` 가 파일에서 직접 계산 — 손타이핑 0.
> 재현: `cd scripts/t3 && LC_ALL=C PYTHONIOENCODING=ascii python3 gen_manifest_fa.py`

**Freeze-A 판정: PASS** (계획 §3.1, 08-13 예정분 1일 지연 수행). 검증 4축 — ⑴ 고정 해시(v2=rev-3b 등재값·v1=supersedes 기록 일치) ⑵ 결정성(샌드박스 격리 ×2 + 디바이스 격리, 전부 `60cc8d23…` 비트 동일·LF) ⑶ 산출 수치(variant_2a 3시나리오+가중 독립 재계산 전항 일치, T-4 채점 훅 소비값 3개 일치) ⑷ fail-closed(1바이트 변조 → 종료 1·미생성, 양성 대조 비트 동일). 동결 원본 무수정 — 실행은 전부 격리 사본.

| 파일 | sha256 | bytes | 비고 |
|---|---|---:|---|
| `reports/FREEZE_A_verification_nvda_2026-08-14.md` | `a0ea3f047aa4f2e55bafdafd1b728e262ae7c28e664fbf482ed759d956d3beef` | 4,925 | Freeze-A 검증 — 후보 v2 variant_2a 재현 **PASS** (해시·결정성 3회·수치 독립재계산·fail-closed). 관찰 1건: 생성기 ASCII 콘솔 종료 1(JSON 기록 후 print 단계, 산출물 무영향) |
| `reports/nvda_2026q2_freeze_a_candidate_v2.json` | `60cc8d23cc916444d062a530eb49c0f627b1e10ac8239fd9affe9e06419bfbef` | 8,390 | 동결 후보 v2 — **무수정 재확인** (Freeze-A CANONICAL = variant_2a 확정 유지) |
| `scripts/nvda_2026q2_freeze_a_candidate_v2.py` | `ca8c1dd528f56f527ce8d85027bbdd2652e5cd7dfb1b845f3b4f701c3311f10c` | 5,913 | 후보 v2 생성기 — 무수정, 격리 재실행 3회 전부 60cc8d23… 비트 동일 |
| `scripts/t3/gen_freeze_a.py` | `c53eecda599e49a29cd4eff42b0c6da431aaafaf9bf193c52b42e1c6d49bb88f` | 10,431 | Freeze-A 검증 보고서 생성기 (검사 8건 내장, 실패 시 보고서 미생성) |

**다음 (계획 §7):** 13F 수신 확인 → T-2 ② (06-30 스냅샷만) — 새 세션 권장(감사 경계 분리, 사용자 지시) · 08-14~26 원장 B 축적·§3.3 트리거 감시 · 08-27 Freeze-B/프린트. 별도 작업 유지: ERP 갱신 · NVDA 산출물 git 커밋 결정.

---

*본 문서는 투자 자문이 아니며, 모델 방법론 검증 목적의 내부 분석이다.*