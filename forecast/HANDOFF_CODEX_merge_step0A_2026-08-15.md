# HANDOFF → Codex: BVT⇐EFE 병합 Step 0-A — EFE 최종 마감 (커밋·태깅·push)

작성: 2026-08-15 (Claude, Cowork 세션 A) · 기준: `PLAN_repo_merge_bvt_efe.md` v3 §3 Step 0-A (BVT 저장소 루트에 있음) · 루프: `.claude/rules/codex-cross-review.md` (BVT)
위임: PLAN상 승인 게이트 1(manifest include/exclude)은 사용자 게이트이나, **2026-08-15 사용자가 4개 결정항목 전부를 "Codex 핸드오프로 판단"으로 위임**했다. 결정 근거를 반드시 manifest에 기록하라 — 사용자·Claude가 사후 검증한다.

## 0. 필수 절차 (cross-review 루프)

**구현·커밋 전에 "정책 확정본"을 1번부터 연번으로 먼저 회신하라.** 확정본에는 아래 D-1~D-4 각각의 결정 + 근거 + 커밋 분할 계획이 들어가야 한다. 요구(R-*)에서 이탈할 경우 사전 통보 필수. 회신 파일: `REPLY_CODEX_merge_step0A_policy.md` (EFE 루트).
확정본에 대한 Claude 승인 후 실행하라. (사용자가 속도를 원하면 확정본 회신과 실행을 한 세션에 이어도 되나, 확정본 없는 실행 금지.)

## 1. 입력 문서

- `MANIFEST_efe_final_2026-08-15.md` (EFE 루트, Claude 초안) — 분류 원안 + 측정 근거 전문
- `PLAN_repo_merge_bvt_efe.md` v3 §3 Step 0-A (BVT 루트)
- 본 문서

## 2. 결정 항목 (D-1 ~ D-4)

### D-1. AMD FROZEN SHA 핀 모순 (차단 이슈 — 커밋 전 해결 필수)
`scripts/score_amd_q2_2026.py:77`의 `FROZEN_SHA256 = 9b49506d…9887e`가 `reports/amd_q2_2026_forecast_FROZEN.md` 현재 내용(sha `fe007377…7061`, HEAD `ae3203e` blob과 바이트 동일)과 불일치. `pytest tests/test_score_amd_scaffold.py` → `test_frozen_sha_guard_trips_on_drift` FAIL.

Claude 실측 (컨테이너 + 샌드박스):
- 핀 `9b49506d…`는 현재 내용의 LF 변형(`fe007377…`)과도 CRLF 변형(`74479ecd…`)과도 불일치 → 다른 내용에 대한 핀
- 타임라인: 스크립트 mtime 08-09 12:35 → FROZEN mtime 08-09 12:54 (내용은 HEAD로 회귀). 같은 시각대(12:51) BVT에 stale index.lock 생성 — 08-09 세션에서 되돌림 정황
- **단서**: `test_anchor_matches_published_frozen_numbers`는 **통과** — 스크립트의 FROZEN_ANCHOR 수치(11,650 / $1.075 / $1.66 / weighted 1.1086 등)와 현재 FROZEN 본문 토큰이 전부 일치. 즉 현재 내용이 의미상 의도된 기록일 가능성이 높고, 바이트 핀만 stale일 개연성
- 조사 리드: `HANDOFF_CODEX_efe_2026aug_amd.md`(tracked dirty, 62KB로 확장됨)에 transcription 이력이 있는지, host에 12:35~12:54 사이 버전의 사본이 있는지
- 선택지: (a) 핀을 `fe007377045df529a92e03b6f598bfd836aa68fb6cdee535caf3080de30a7061`로 re-pin (1줄) 후 include · (b) 의도된 다른 내용 복원 · (c) AMD 세트 4건 exclude로 연기. **가드 철학("re-transcribe deliberately") 위반 없는 쪽으로 결정하고 근거를 남겨라.**

### D-2. 경계 파일 2건
- `profiles/gev_q3_2026.dev.generic.yaml` — `.dev.` 스크래치 추정. Claude 권고 exclude.
- `inputs/amd_q2_2026_actual.filled.yaml` — 생성물 성격이나 스코어링 재현 기록. Claude 권고 include (약우세).

### D-3. manifest 전체 분류 최종화
Claude 원안: include 82 + tracked dirty 4 커밋 (superseded 리포트 3건 포함). 원안 수정 시 항목·사유를 manifest에 기입.

### D-4. 커밋 분할
권장 예시: ① 코드+테스트(bridge_ops, t3, score, freeze) ② reports/inputs/profiles ③ 프로세스 문서(HANDOFF/PLAN/REVIEW/START/MANIFEST/docs/PROPOSAL) ④ tracked dirty 4건 + manifest·본 handoff·REPLY. 최종안은 확정본에.

## 3. 실행 요구 (R-1 ~ R-8, 확정본 승인 후 host에서)

- **R-1**: host에서 `git status --short --untracked-files=all` 전문 재측정 → manifest §0에 "host 최종" 블록으로 append. 샌드박스 대비 증감 있으면 명시.
- **R-2**: D-1 결정 반영 (수정 파일은 원자적 쓰기 + `ast.parse` + 줄수 확인).
- **R-3**: include 세트를 D-4 분할대로 커밋. **파괴적 git 금지** (`checkout --`/`restore`/`reset --hard`/`stash`). EFE는 `.gitattributes` LF 정규화 — 새 파일 그대로 커밋하면 됨(renormalize 금지).
- **R-4**: 커밋 직후 **NUL 스캔** (codex-cross-review.md의 스크립트 그대로, 원출력 첨부 — "clean이라고 보고"가 아니라 스캔 출력 자체를 붙여라. 과거 2회 허위 clean 보고 이력).
- **R-5**: `pytest -q -p no:cacheprovider` 전체 실행 — pass/fail/skip/deselect/xfail **분해 수치** + summary 원출력. 기대: fail 0 (D-1 (c) 선택 시 그 사유로 fail 0). `python scripts/verify_anchor.py` 원출력 (기대: PASS, canonical SHA `077ecb10…933c`).
- **R-6**: `python -m pytest tests/test_frozen_integrity.py -q -s` (host, Git checkout 필수) 원출력.
- **R-7**: `git tag efe-final-standalone && git push origin main --tags`. 기록: `git rev-parse efe-final-standalone^{commit}` = `<EFE_FINAL>`, `^{tree}`, `git ls-files | wc -l`, `git rev-list --count HEAD`.
- **R-8**: 회귀표(아래) **빈칸 없이** 채워 `REPORT_CODEX_merge_step0A_result.md`(EFE 루트)로 회신. 각 칸에 실행 명령 + 원출력.

| # | 항목 | 명령 | 기준 | 결과 |
|---|---|---|---|---|
| S0-1 | host status 전문 | `git status --short -uall` | manifest에 append | |
| S0-2 | NUL 스캔 | 루프 스크립트 | 0건 + 스캔 수 | |
| S0-3 | pytest 분해 | `pytest -q -p no:cacheprovider` | fail 0, 분해 기록 | |
| S0-4 | 9Q 앵커 | `python scripts/verify_anchor.py` | PASS + SHA 일치 | |
| S0-5 | FROZEN 게이트 | `pytest tests/test_frozen_integrity.py -q -s` | pass | |
| S0-6 | 태그·push | R-7 명령 4종 | `<EFE_FINAL>`·tree·counts 기록 | |
| S0-7 | working tree 마감 | `git status --short -uall \| wc -l` | exclude 잔류분만 (목록 일치) | |

## 4. 금지·주의 (전부 실제 사고 이력 기반)

1. 파괴적 git 금지 — 특히 D-1 조사 중 `git checkout -- reports/amd_q2_2026_forecast_FROZEN.md` 류 절대 금지 (현재 clean이지만 원칙 유지).
2. 파일 쓰기는 원자적(임시파일→`os.replace`), 직후 `ast.parse`+줄수 — Windows 마운트 무언 truncation 3회 이력.
3. NUL 스캔은 작업 종료 직후 실제 실행·원출력 첨부 — 허위 "clean" 보고 2회 이력.
4. 회귀표 빈칸 금지 — 자기에게 유리한 회귀만 확인한 이력.
5. 목록은 1번부터 연번 — 항목 소실 2회 이력.
6. `.env`·비밀 값 출력/커밋 금지 (Claude가 untracked 전건 secret 스캔 clean 확인했으나 커밋 diff에서 재확인).
7. push 후 결함 발견 시 reset/force-push 금지 — revert 커밋만.
8. (참고) BVT `.git/index.lock` 0바이트 stale(08-09 12:51 생성)이 잔존 — **이번 Step 0-A(EFE) 범위 아님.** Step 0-B에서 host가 제거 예정이니 건드리지 말 것.

## 5. 완료 후

Claude(Cowork)가 독립 재검증한다: `<EFE_FINAL>` 태그 스냅샷을 컨테이너로 가져와 pytest·verify_anchor·NUL·sha 재실행, 회귀표 역산 대조. 불일치 시 반박 회신 후 재작업.
