# AUDIT — 콘솔 비의존·개행 고정 감사 (P-6, 2026-08-14)

> 채택 근거: Codex 판정 P-6 **ADOPT (P1)**, "스캔은 읽기 전용; 수정은 별도 승인". 사용자 승인 2026-08-14. 트리거 결함: Freeze-A 관찰(후보 v2 생성기 ASCII 콘솔 종료 1).
> 스캔 원본: `reports/scan_console_safety_2026-08-14.json` `5afae6dab8a6d926…` — 전체 139개 .py 중 플래그 18건. 휴리스틱 스캔이므로 오탐/미탐 가능 — 수정 착수 전 파일별 재확인 필요.

검사 항목: ⑴ `print(` 라인의 비ASCII 문자 (ASCII 콘솔 크래시 위험) ⑵ `open(..., 'w')` 에 `newline=` 부재 (Windows CRLF 오염 위험) ⑶ 콘솔 가드(`reconfigure`/`errors=replace`)·VERBOSE 옵트인 유무.

| 파일 | 비ASCII print | w() newline 부재 | 가드 | 분류 |
|---|---:|---:|:--:|---|
| `scripts/nvda_2026q2_freeze_a_candidate.py` | 0 | 1 | — | 동결·해시 고정 — **무수정** (관찰만 기록) |
| `scripts/nvda_2026q2_freeze_a_candidate_v2.py` | 0 | 1 | — | 동결·해시 고정 — **무수정** (관찰만 기록) |
| `scripts/t3/gen_freeze_a.py` | 1 | 0 | ✅ | 동결·해시 고정 — **무수정** (관찰만 기록) |
| `scripts/t3/gen_handoff_t4.py` | 1 | 0 | ✅ | 동결·해시 고정 — **무수정** (관찰만 기록) |
| `scripts/t3/t3_reverse_dcf.py` | 11 | 1 | — | 동결·해시 고정 — **무수정** (관찰만 기록) |
| `scripts/score_amd_q2_2026.py` | 1 | 0 | — | 채점 고정분 — 수정 시 P0 규약 검토 필요, 보류 |
| `scripts/score_txn_q2_2026.py` | 6 | 0 | — | 채점 고정분 — 수정 시 P0 규약 검토 필요, 보류 |
| `ai/extractor.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `generic_cli.py` | 4 | 0 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `output/html_builder.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `output/md_builder.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `pipeline/dart_fetcher.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `pipeline/disclosure_loader.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `pipeline/edgar_fetcher.py` | 0 | 1 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `pipeline/yahoo_fetcher.py` | 0 | 3 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `scripts/diagnose_opex.py` | 2 | 0 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `scripts/verify_9q_sha.py` | 2 | 0 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |
| `tests/test_frozen_integrity.py` | 2 | 0 | — | 활성 비동결 — **수정 후보** (별도 승인 대상) |

## 분류 요약

- **동결·해시 고정 5건 — 무수정.** `t3_reverse_dcf.py`(비ASCII print 11·newline 부재 1)와 후보 v1/v2 생성기(newline 부재)는 이미 검증된 산출물의 생성 경로다 — 재실행 시 UTF-8 콘솔·격리 디렉터리 규약으로 대응 (Freeze-A 보고서 §2 관찰과 동일 처리). `gen_freeze_a.py`·`gen_handoff_t4.py` 의 플래그는 가드된 실패-경로 print 로 산출물 무영향.
- **채점 고정분 2건 — 보류.** `score_amd`·`score_txn` 은 P0 커밋 고정 이력이 있어 수정 자체가 규약 검토 사안.
- **활성 비동결 11건 — 수정 후보 목록.** `generic_cli.py`(비ASCII print 4) · `pipeline/` 5개·`output/` 2개·`ai/extractor.py`(newline 부재 — 산출 파일 CRLF 오염 경로) · `scripts/diagnose_opex.py`·`scripts/verify_9q_sha.py`·`tests/test_frozen_integrity.py`(비ASCII print). **이 목록의 실제 수정은 본 감사 범위 밖 — 별도 승인 후 착수.**

## 권고 (수정 승인 시 우선순위)

1. `output/`·`ai/extractor.py`·`pipeline/` 의 `newline=` 부재 — **산출 파일 오염**(CRLF) 경로라 콘솔 크래시보다 우선. `open(..., 'w', encoding='utf-8', newline='\n')` 통일.
2. `generic_cli.py` 등 비ASCII print — 크래시는 콘솔 환경 의존이므로 차순위. CONVENTIONS_rev_audit.md §2 의 신규 생성기 요건(가드·errors=replace) 적용.
3. 동결·채점 고정분은 영구 무수정 — 관찰 기록으로 종결.

---

*본 문서는 투자 자문이 아니며, 프로세스 감사 문서이다.*