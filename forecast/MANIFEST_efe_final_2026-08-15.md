# MANIFEST: EFE 최종 마감 (Step 0-A) — 초안 v1

작성: 2026-08-15 (Claude, Cowork 세션 A) · 상태: **승인 게이트 1을 사용자가 Codex 판단으로 위임 (2026-08-15, 4개 결정항목 전부) → Codex 정책 확정본 대기.** 실행 지시는 `HANDOFF_CODEX_merge_step0A_2026-08-15.md` 참조. Codex는 §2·§3 결정과 최종 분류를 이 문서에 기입해 최종화한다.
기준: `PLAN_repo_merge_bvt_efe.md` v3 §3 Step 0-A · 측정: 샌드박스 (⚠️ 커밋 전 host `git status --short --untracked-files=all` 재확인 필수 — 단, 아래 tracked/untracked 분류는 CR-제거 내용 비교로 검증했으므로 CRLF 팬텀 아님)

## 0. 측정 요약 (2026-08-15 샌드박스, EFE HEAD `92eca68`)

- status 총 90줄 = tracked M 4 + untracked 86
- tracked M 4건: 전건 실제 수정 확인 (CR-제거 후 바이트 비교):
  - `CLAUDE.md` (9,274B → 11,837B) — Device Bridge Limits 섹션 등 추가
  - `HANDOFF_CODEX_efe_2026aug_amd.md` (19,390B → 62,319B)
  - `HANDOFF_CODEX_efe_2026aug_sndk.md` (25,911B → 35,814B)
  - `HANDOFF_CODEX_efe_2026aug_spcx.md` (24,984B → 33,635B)
- untracked 86건: NUL 스캔 clean · secret 패턴 스캔 clean
- 신규 테스트 검증 (컨테이너, 오프라인): 전체 스위트 **358 passed / 1 failed / 1 skipped(호스트 전용 FROZEN 게이트, 정상) / 1 deselected(network)** — 실패 1건은 §3 AMD 모순 (아래)
- `python scripts/verify_anchor.py` PASS — canonical 9Q SHA `077ecb10…933c` 일치, rev MAPE 8.99% · EPS MAPE 10.39% · bias −3.58% (CLAUDE.md 기준선 재현)

## 1. INCLUDE 권고 (82건 + tracked 4)

### 1a. tracked dirty 4건 (커밋 필수 — 태그가 최종 상태를 캡처해야 함)
위 4건. Step 0-A 커밋에 포함하지 않으면 `efe-final-standalone` 태그가 CLAUDE.md 최신본(Device Bridge Limits·bridge_ops 규칙)을 잃는다.

### 1b. 루트 프로세스 문서 33건 (.md)
HANDOFF_CODEX_* 15 (bridge_ops, efe_hardening, efe_improvements, hynix_q2, nvda plan_review, t3_reverse_dcf rev2–7, t4_verdict rev1–4) · HANDOFF_P0_approval_checklist · MANIFEST_ADDENDUM 3 · PLAN_nvda_2026-08_deep_dive · REPLY_nvda_2026-08_plan_codex · REVIEW 2 (bridge_ops_rev3, nvda_plan) · START-* 9 · T3_nvda_2026-08-10
사유: 저장소 관례 — HANDOFF/PLAN/REVIEW/START는 git·포트폴리오 내러티브용으로 보존 (CLAUDE.md Workflow 규칙). 기존 tracked 동류 다수.

### 1c. 정책 제안 YAML 2건
`PROPOSAL_policy_resolver_v1.yaml` · `PROPOSAL_policy_selection_rules_v1.yaml` — P0 승인 체크리스트와 세트.

### 1d. docs/ 2건
`docs/CONVENTIONS_rev_audit.md` · `docs/CONVENTIONS_verdict_authoring.md` — 방법론 문서, docs/ 관례.

### 1e. 코드·테스트 24건 (AMD 세트 제외)
- `scripts/bridge_ops.py` + `tests/test_bridge_ops.py` — PLAN 명시 include 유력. 테스트 통과 확인.
- `scripts/t3/` 19건 — NVDA T3/T4 생성 스크립트 (커밋되는 reports의 재현 코드).
- `scripts/nvda_2026q2_freeze_a_candidate.py`, `_v2.py`
- `scripts/score_sndk_fy2026q4.py` + `tests/test_sndk_fy2026q4_score.py` — 통과 확인.

### 1f. reports/ 20건
NVDA 워크스트림 md 15 (AUDIT, BASIS, FREEZE_A_verification, MANIFEST 3, T1, T2, T3, T4_draft + superseded 3, V2, information_ledger_A) · `sndk_fy2026q4_SCORED.md` · `spcx_q2_2026_SCORED.md` · json 3 (`nvda_2026q2_freeze_a_candidate.json`, `_v2.json`, `scan_console_safety_2026-08-14.json`)
사유: reports/ tracked 87건 관례 + ex-ante 기록 보존 정책. .gitignore는 xlsx/html/pdf/캐시·dated sk_hynix만 제외 — 이들은 의도적 커밋 대상 범주. superseded 3건도 ex-ante 기록으로 보존 권고 (제외 원하면 exclude로 이동 가능).

### 1g. inputs/ 1건
`inputs/amd_q2_2026_actual.yaml` — inputs/ tracked 3건 관례, 스코어링 입력 기록.

## 2. 판단 필요 (사용자 결정)

| 파일 | 쟁점 | 권고 |
|---|---|---|
| `profiles/gev_q3_2026.dev.generic.yaml` | `.dev.` 개발 스크래치로 추정 | **exclude** (병합 후 forecast/에 미존재 — 필요 시 정식명으로 승격 후 include) |
| `inputs/amd_q2_2026_actual.filled.yaml` | 생성물(.filled) vs 입력 기록 | include 쪽 약우세 — 스코어링 재현 기록 |

## 3. ⚠️ 차단 이슈 — AMD 스코어링 세트 2건 (커밋 전 해결 필수)

`scripts/score_amd_q2_2026.py` + `tests/test_score_amd_scaffold.py`

**발견 (컨테이너 독립 재현)**: `test_frozen_sha_guard_trips_on_drift` FAIL. 스크립트의 `FROZEN_SHA256 = 9b49506d…9887e`가 `reports/amd_q2_2026_forecast_FROZEN.md` 현재 내용과 불일치.
- FROZEN 파일은 **clean** (HEAD `ae3203e` 08-05 blob과 바이트 동일, sha `fe007377…7061`)
- 핀 `9b49506d…`는 현재 내용의 LF 변형과도 CRLF 변형과도 불일치 → **다른 내용에 대해 핀** 됨
- 타임라인: 스크립트 작성 08-09 12:35 → FROZEN mtime 08-09 12:54 (내용은 HEAD와 동일로 회귀). 08-09 12:51에 BVT `.git/index.lock` 생성과 시간대 일치 — 08-09 세션에서 무언가 되돌려진 정황
- 가드 메시지 자체가 "re-transcribe deliberately" — **사람 결정 사안**

**선택지**:
- (a) 현 FROZEN 내용(`fe007377…`)이 의도된 기록이면 → 스크립트 핀만 `fe007377…`로 수정 후 include (1줄 수정, 테스트 재실행 green 확인 후 커밋)
- (b) 08-09 12:35~12:54 사이의 다른 FROZEN 내용이 의도된 기록이면 → 해당 내용 복원 필요 (호스트에서 출처 확인)
- (c) AMD 세트 4건(script/test/inputs 2) 전부 exclude — 결정을 병합 후로 연기 (untracked로 잔류, 병합 tree에서 빠짐)

## 4. EXCLUDE 권고

- `profiles/gev_q3_2026.dev.generic.yaml` (§2 결정 시)
- (참고) `_to_delete/efe_snapshot_20260815.tar.gz` — 본 세션이 만든 검증용 스냅샷, gitignored(`_to_delete/`), 커밋 대상 아님. 추후 폴더째 수동 삭제.

## 5. 커밋·태깅 실행 순서 (승인 후, host)

1. (사전) **BVT `.git/index.lock` 제거** — 2026-08-09 12:51부터 잔존한 0바이트 stale lock (샌드박스 확인). 마운트에서 삭제 불가 → host에서 삭제. ※ EFE 쪽 stale lock 1건은 bridge_ops preflight가 이미 정리함.
2. AMD 핀 이슈 해결 (§3 선택지 확정)
3. host에서 `git status --short --untracked-files=all` 전문을 이 manifest에 붙여 최종화
4. include 세트 커밋 (필요 시 논리 단위 분할: 코드+테스트 / reports / 프로세스 문서)
5. 신규 테스트 포함 전체 `pytest -q` green 확인 (호스트)
6. `git tag efe-final-standalone && git push origin main --tags`
7. `git rev-parse efe-final-standalone^{commit}` = **`<EFE_FINAL>`** / `^{tree}` 해시 + 최종 tracked 파일 수를 이 manifest와 회귀표에 기록

## 6. 부속 기록

### Codex 최종 결정 및 host 재측정 (2026-08-16)

- AMD FROZEN 416줄본(`[PRE-PRINT ERRATA]` 포함, SHA-256 `9b49506d…a887e`)은 유실 상태다. 현 tracked 트리는 347줄 pre-errata본(SHA-256 `fe007377…7061`)이다. 복구 또는 현 347줄본 재승인은 Phase 3 백로그로 넘긴다. 복구 단서는 `reports/amd_q2_2026_errata.md`와 `HANDOFF_CODEX_efe_2026aug_amd.md` §275·§9-5·§10-2다.
- 따라서 `scripts/score_amd_q2_2026.py`, `tests/test_score_amd_scaffold.py`, `inputs/amd_q2_2026_actual.yaml`, `inputs/amd_q2_2026_actual.filled.yaml`은 원자적으로 exclude한다. `profiles/gev_q3_2026.dev.generic.yaml`도 개발 스크래치로 exclude한다. 다섯 파일은 삭제·이동·수정하지 않고 제자리에 보존한다.
- 나머지 Claude include 원안과 tracked dirty 4건, merge handoff·정책 회신·승인서는 include한다. 결과 보고서는 태그 전 검증 결과(S0-1~S0-5)까지만 tracked로 포함하고, 태그 이후 S0-6/S0-7은 BVT 결과 보고서에 기록한다.

Host 최종 `git status --short --untracked-files=all` 원출력(커밋 전):

```text
 M CLAUDE.md
 M HANDOFF_CODEX_efe_2026aug_amd.md
 M HANDOFF_CODEX_efe_2026aug_sndk.md
 M HANDOFF_CODEX_efe_2026aug_spcx.md
?? APPROVAL_CLAUDE_merge_step0A_policy.md
?? HANDOFF_CODEX_bridge_ops_2026-08-12.md
?? HANDOFF_CODEX_efe_hardening_2026-08.md
?? HANDOFF_CODEX_efe_improvements_2026-08-14.md
?? HANDOFF_CODEX_hynix_q2_2026_report_2026-08-07.md
?? HANDOFF_CODEX_merge_step0A_2026-08-15.md
?? HANDOFF_CODEX_nvda_2026-08_plan_review.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev2.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev3.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev4.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev5.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev6.md
?? HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md
?? HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev1.md
?? HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev2.md
?? HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev3.md
?? HANDOFF_CODEX_nvda_2026-08_t4_verdict_rev4.md
?? HANDOFF_P0_approval_checklist.md
?? MANIFEST_ADDENDUM_2026-08-14_conventions.md
?? MANIFEST_ADDENDUM_nvda_2026-08-13_t4.md
?? MANIFEST_ADDENDUM_nvda_2026-08-14_freeze_a.md
?? MANIFEST_efe_final_2026-08-15.md
?? PLAN_nvda_2026-08_deep_dive.md
?? PROPOSAL_policy_resolver_v1.yaml
?? PROPOSAL_policy_selection_rules_v1.yaml
?? REPLY_CODEX_merge_step0A_policy.md
?? REPLY_nvda_2026-08_plan_codex.md
?? REVIEW_bridge_ops_rev3_impl_2026-08-14.md
?? REVIEW_nvda_2026-08_plan_codex.md
?? START-efe-aug2026-00-COMMON-DELTA.md
?? START-efe-aug2026-amd.md
?? START-efe-aug2026-sndk.md
?? START-efe-aug2026-spcx.md
?? START-efe-aug2026-vst.md
?? START-efe-p0-commit-split.md
?? START-efe-q1-fvpl-attribution.md
?? START-efe-q2-2026-skhynix-T3a-gate.md
?? START-nvda-2026-08-10-execution.md
?? T3_nvda_2026-08-10.md
?? docs/CONVENTIONS_rev_audit.md
?? docs/CONVENTIONS_verdict_authoring.md
?? inputs/amd_q2_2026_actual.filled.yaml
?? inputs/amd_q2_2026_actual.yaml
?? profiles/gev_q3_2026.dev.generic.yaml
?? reports/AUDIT_console_safety_nvda_2026-08-14.md
?? reports/BASIS_consensus_verification_nvda_2026-08-10.md
?? reports/FREEZE_A_verification_nvda_2026-08-14.md
?? reports/MANIFEST_ADDENDUM_nvda_2026-08-09_rev3.md
?? reports/MANIFEST_ADDENDUM_nvda_2026-08-10_exec.md
?? reports/MANIFEST_nvda_2026-08-09.md
?? reports/T1_vendor_financing_nvda_2026-08-10.md
?? reports/T2_buckets_1_3_nvda_2026-08-13.md
?? reports/T3_nvda_2026-08-10.md
?? reports/T4_verdict_draft_nvda_2026-08-13.md
?? reports/T4_verdict_draft_nvda_2026-08-13_rev1_superseded.md
?? reports/T4_verdict_draft_nvda_2026-08-13_rev2_superseded.md
?? reports/T4_verdict_draft_nvda_2026-08-13_rev3_superseded.md
?? reports/V2_rf_overlay_nvda_2026-08-10.md
?? reports/nvda_2026q2_freeze_a_candidate.json
?? reports/nvda_2026q2_freeze_a_candidate_v2.json
?? reports/nvda_2026q2_information_ledger_A.md
?? reports/scan_console_safety_2026-08-14.json
?? reports/sndk_fy2026q4_SCORED.md
?? reports/spcx_q2_2026_SCORED.md
?? scripts/bridge_ops.py
?? scripts/nvda_2026q2_freeze_a_candidate.py
?? scripts/nvda_2026q2_freeze_a_candidate_v2.py
?? scripts/score_amd_q2_2026.py
?? scripts/score_sndk_fy2026q4.py
?? scripts/t3/bvt_dcf.py
?? scripts/t3/gen_audit_p6.py
?? scripts/t3/gen_basis.py
?? scripts/t3/gen_freeze_a.py
?? scripts/t3/gen_handoff.py
?? scripts/t3/gen_handoff_t4.py
?? scripts/t3/gen_improvements.py
?? scripts/t3/gen_manifest.py
?? scripts/t3/gen_manifest_conv.py
?? scripts/t3/gen_manifest_fa.py
?? scripts/t3/gen_manifest_t4.py
?? scripts/t3/gen_t1.py
?? scripts/t3/gen_t2.py
?? scripts/t3/gen_t4.py
?? scripts/t3/gen_v2.py
?? scripts/t3/preflight_lint.py
?? scripts/t3/t3_final.py
?? scripts/t3/t3_reverse_dcf.py
?? tests/test_bridge_ops.py
?? tests/test_score_amd_scaffold.py
?? tests/test_sndk_fy2026q4_score.py
```

- BVT 참고 (Step 0-B 입력): 실제 tracked dirty **10건** 확정 (CR-제거 내용 비교; 샌드박스 status의 180 M 중 170건은 CRLF 팬텀): `.claude/rules/codex-cross-review.md`, `.gitignore`, `CLAUDE.md`, `PLAN_deep_research.md`, `README.md`, `START-nexus-segment-rebuild.md`, `backtest/dataset.py`, `business-valuation-tool.code-workspace`, `db/backtest_repository.py`, `profiles/pfe.yaml` — PLAN §1.1 host 실측 "tracked 10"과 일치.
- BVT HEAD `ae2ba41` · EFE HEAD `92eca68` — PLAN §1.1과 일치 (이후 커밋 없음 확인).
