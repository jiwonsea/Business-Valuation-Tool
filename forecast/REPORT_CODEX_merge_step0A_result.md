# REPORT → Claude: BVT⇐EFE 병합 Step 0-A 결과 (태그 전 S0-1~S0-5)

작성: 2026-08-16 (Codex) · 실행 환경: Windows host, CPython 3.14.3

태그 이후에만 확정 가능한 S0-6/S0-7은 승인 조건 A-2에 따라 BVT의 `REPORT_CODEX_merge_step0BC_result.md`에 기록한다. 이 파일은 태그 후 tracked 수정하지 않는다.

| # | 항목 | 명령 | 기준 | 결과 |
|---|---|---|---|---|
| S0-1 | host status 전문 | `git status --short --untracked-files=all` | manifest에 append | PASS — `MANIFEST_efe_final_2026-08-15.md` §6에 원출력 전문과 최종 분류를 기록했다. |
| S0-2 | NUL 스캔 | handoff 지정 Python 루프 | 0건 + 스캔 수 | PASS — `NUL: clean`; tracked 확장자 후보 323건. |
| S0-3 | pytest 분해 | `python -m pytest -q -p no:cacheprovider` | fail 0, 분해 기록 | PASS — 338 passed / 3 skipped / 1 deselected / 0 failed / 0 xfailed. |
| S0-4 | 9Q 앵커 | `$env:DART_API_KEY='cache-only'; python scripts/verify_anchor.py` | PASS + SHA 일치 | PASS — anchor reproduction, network calls 0; host canonical `b979d79f…f6e7` 일치. CPython 3.14의 문서화된 host canonical이며 CPython ≤3.11 canonical은 `077ecb10…933c`. |
| S0-5 | FROZEN 게이트 | `python -m pytest tests/test_frozen_integrity.py -q -s` | pass | PASS — checked 4 / supported skipped 0 / legacy SKIP 5 / failures 0; `2 passed in 1.47s`. |

## 1. S0-2 원출력

```text
NUL: clean
TRACKED_SCAN_CANDIDATES=323
```

## 2. S0-3 원출력

검증 worktree: detached `48be787908c42f433b82ddf6e63191a2f1110e16`. Gitignored host 기준 자산 `reports/sk_hynix_20260710.xlsx`(SHA-256 `e2ed59ed…66f95`)와 `reports/.cache/dart_*` 42건을 검증 worktree에 복사했다. 이 자산 없이 실행한 첫 완결 시도는 332 passed / 3 skipped / 1 deselected / 6 failed였으며, 6건 모두 누락된 XLSX/DART cache 때문이었다. 원본 저장소와 exclude 5건은 수정하지 않았다.

```text
........................................s.......................s....... [ 21%]
........................................................................ [ 42%]
........................................................................ [ 63%]
........................................................................ [ 84%]
........................s............................                    [100%]
SKIPPED [1] tests/test_bridge_ops.py:79: symlink creation unavailable on Windows
SKIPPED [1] tests/test_bridge_ops.py:415: no process-group semantics on Windows
SKIPPED [1] tests/test_txn_profile.py:84: derived EDGAR cache absent (gitignored) — rebuild to populate
338 passed, 3 skipped, 1 deselected in 24.45s
```

## 3. S0-4 원출력

```text
PASS: sk_hynix 2026Q2 anchor reproduced (relative tolerance 1e-09; network calls 0)
9Q SHA gate:
env: python 3.14.3 · pydantic 2.12.5 · win32
rev MAPE 8.9875% · EPS MAPE 10.3856% · bias -3.5751%
sha256   b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7
MATCH: host canonical (CPython >= 3.12 Neumaier sum(); measured 3.14.3/win32)
PASS: G1 anchor reproduction and canonical 9Q SHA
```

## 4. S0-5 원출력

```text
PASS: reports/amd_q2_2026_forecast_FROZEN.md - tracked, not ignored, HEAD-clean, freeze profile SHA matched at ae3203e1688c
SKIPPED: reports/gev_q2_2026_forecast_FROZEN.md - convention N/A (frozen before 2026-08-05)
SKIPPED: reports/googl_q2_2026_forecast_FROZEN.md - convention N/A (frozen before 2026-08-05)
SKIPPED: reports/ibm_q2_2026_forecast_FROZEN.md - convention N/A (frozen before 2026-08-05)
PASS: reports/sndk_fy2026q4_forecast_FROZEN.md - tracked, not ignored, HEAD-clean, freeze profile SHA matched at 0168c6525943
PASS: reports/spcx_q2_2026_forecast_FROZEN.md - tracked, not ignored, HEAD-clean, freeze profile SHA matched at 01de2a6795d1
SKIPPED: reports/tsla_q2_2026_forecast_FROZEN.md - convention N/A (frozen before 2026-08-05)
SKIPPED: reports/txn_q2_2026_forecast_FROZEN.md - convention N/A (frozen before 2026-08-05)
PASS: reports/vst_q2_2026_forecast_FROZEN.md - tracked, not ignored, HEAD-clean, freeze profile SHA matched at b4287cd648ef
SUMMARY: 검사 4건 / SKIP 5건
..
2 passed in 1.47s
```

## 5. 태그 전 이탈·주의

1. `pytest` 명령이 PATH에 없어 `python -m pytest`를 사용했다.
2. 첫 실행은 120초 제한으로 종료됐고, 두 번째 완결 실행에서 기준 자산 누락 6 fail을 발견했다. 자산을 검증 worktree에 공급한 세 번째 실행이 위 S0-3 결과다.
3. handoff가 기대값으로 적은 `077ecb10…933c`는 CPython ≤3.11 canonical이다. 현재 host CPython 3.14.3에서는 저장소 검증기가 승인하는 `b979d79f…f6e7`가 재현됐다.
