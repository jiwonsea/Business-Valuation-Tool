# 선행 미커밋 트랙 커밋 플랜 — 작업 트리 전수 조사 + 트랙별 manifest
2026-07-18 (Claude) | 상태: **분석·플랜 문서 — 코드 변경 0, git 쓰기 0 (조회는 `GIT_OPTIONAL_LOCKS=0`)**
기준 HEAD: **2693260** (Phase 2 ⑤까지 커밋 완료, `HANDOFF_CODEX_phase2_impl_scope_2026-07-18.md` §12.5)
실행 주체: **호스트** (커밋·staging은 호스트 전용 — §12.1 교훈)

## 0. ⚠ 즉시 조치 + 개행 노이즈 주의

1. **index.lock 재발**: 본 세션 초입 샌드박스 `git status`가 `.git/index.lock`을 다시
   생성했고 마운트 제한으로 삭제 불가. 호스트에서 제거:
   `del F:\dev\Portfolio\business-valuation-tool\.git\index.lock`
   (0 byte + 다른 git 프로세스 없음 확인 후). 이후 샌드박스 git 조회는 전부
   `GIT_OPTIONAL_LOCKS=0` 프리픽스로 실행했음 — 재발 없음. **차기 세션도 동일 프리픽스 필수.**
2. **샌드박스 `M` 카운트는 과대 표시**: 샌드박스 git은 `core.autocrlf` 미설정이라 CRLF
   작업 트리 vs LF HEAD blob 차이가 전부 `M`으로 보인다. 실측: M 164 중 **내용 diff는
   51뿐, 113은 순수 개행 노이즈** (CR 제거 후 byte 동일 — 전수 cmp로 확인). 호스트
   (autocrlf=true 추정, ①~⑤ 커밋이 깨끗이 된 근거)에서는 이 113개가 clean으로 보일
   것. **커밋 대상 판단은 호스트 `git status`가 기준.** 아래 manifest는 내용 diff 51 +
   untracked 114만 다룬다.

## 1. 전수 조사 요약

- 내용 diff 있는 tracked 파일: **51** (목록은 §2 트랙 귀속에 전부 포함)
- untracked: **114** (기능 파일 + 문서 + 잔재물 혼재, §2·§4에서 분리)
- Phase 2(⑤) 파일: 전부 HEAD와 내용 동일 — 잔여 작업 없음 확인.
- `cli.py`·`output/excel_builder.py` 잔여 diff에 band/timeseries 관련 hunk **0**
  (⑤ 몫 완전 소진 확인) — 잔여분은 아래 T5·T6 소속.

## 2. 트랙별 커밋 단위 제안 (T1~T11)

파일 귀속은 diff 내용 실측 기반. "전체" = 해당 파일의 현재 diff 전부가 이 트랙 소속.

### T1 — Part B: units·SOTP 가드레일 + 세그먼트 PBV/PE (최대 단위)
근거 diff: `monte_carlo.py` seg_book_equity/seg_net_income + pbv|pe · `sensitivity.py`
세그먼트 자동선택/pbv_pe_ev 하위호환 · `units.py` 표시단위 재정의 · `market_comparison.py`
단위 오염 경고 · `scenario.py` receivable_recovery_value · `test_engine.py` +289줄
(units/recovery/pbv·pe/MC 테스트 — 전부 이 우산).
- 전체: `engine/monte_carlo.py` `engine/sensitivity.py` `engine/units.py`
  `engine/market_comparison.py` `engine/scenario.py` `engine/normalize.py`(주석 개정 —
  Blume 문구는 T3와 겹치나 diff가 작아 T1 동반 커밋 허용) `pipeline/reconciliation.py`
  (mixed-units 수정) `output/sheets/financials.py` `output/sheets/scenarios.py`
  `output/sheets/sensitivity.py` `output/sheets/valuation.py`(DDM sensitivity 제거)
  `tests/test_engine.py` `tests/test_reconciliation.py`
- untracked: `tests/test_scenario_spread_guardrail.py` ·
  `HANDOFF_CLAUDE_bvt_units_sotp_guardrails.md` · `HANDOFF_CODEX_bvt_partB_round2/3/3b.md`
- 주의: `tests/test_engine.py`는 T1·T2 테스트가 혼재할 수 있으나 전부 Part B 라운드
  산출물이므로 일괄 T1 귀속 권고 (hunk 분리 비용 > 이득).

### T2 — quality convergence fail-closed
- 전체: `engine/quality.py`(2개 미만 독립 방법 = 0/25) · `tests/test_quality.py`(+100)
- untracked: `HANDOFF_quality_optionality_2026-07-06.md`(관련 시 동반)

### T3 — 베타 관측·Blume shrinkage (Round 4)
- 전체: `schemas/provenance.py`(docstring 1줄) · untracked `engine/beta_regression.py`
  `pipeline/beta_observation.py` `tests/test_beta_regression.py`
  `tests/test_mc_determinism.py` `ROUND4_beta_observation_blocker.md`
  `HANDOFF_CODEX_bvt_round4_mc_determinism.md`
- 주의: `test_mc_determinism.py`가 T1의 `monte_carlo.py` 변경에 의존하면 T1 뒤에 커밋.

### T4 — relative valuation·peer provenance (sell-side)
근거 diff: `peer_analysis.py` explain_multiple · `peers.py` +281 implied-multiple 패널 ·
`dashboard.py` _fmt_multiple · `relative_metrics.py` justified P/B 가드.
- 전체: `engine/relative_metrics.py` `engine/peer_analysis.py` `output/sheets/relative.py`
  `output/sheets/peers.py` `output/sheets/dashboard.py` `tests/test_relative_metrics.py`
  `tests/test_output.py`(peer 패널 테스트) `tests/fixtures/relative_financial.yaml`
- untracked: `tests/test_relative_wiring.py` `tests/test_reporting_boundary.py`
  `.claude/rules/reporting-boundary.md` `RELATIVE_VALUATION_PLAN.md`
  `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md`

### T5 — valuation history (P3) + Excel 시트 확장 + draft 게시 차단
근거 diff: `db/repository.py` list_valuation_history + `schemas.history` import ·
`migrations.sql` history append-only · `excel_builder.py` history/raw_data/guides 시트 ·
`orchestrator.py` draft 시 DB 게시 차단.
- 전체: `db/repository.py` `db/migrations.sql` `output/excel_builder.py`(잔여 diff 전부)
  `orchestrator.py`
- untracked: `schemas/history.py` `output/sheets/history.py` `output/sheets/raw_data.py`
  `output/sheets/_guide.py` `tests/test_valuation_history.py`
- 주의: **`schemas/history.py`·`output/sheets/history.py`는 P3 소유물** (Phase 2 문서
  §1-4의 명명 충돌 경고 대상 — timeseries/band와 무관함이 확인됨).

### T6 — cli live market price 분리 리팩터
근거 diff: `_fetch_and_compare_market_price` → `_fetch_live_market_price` + 
`enrich_market_dependent_result`(valuation_runner — HEAD에 이미 존재) 소비.
- 전체: `cli.py`(잔여 diff 전부 — --band hunk는 ⑤로 소진됨)
- untracked: `tests/test_cli_market_price.py`

### T7 — backtest·peer calibration
- 전체: `db/backtest_repository.py` `db/migrations_backtest.sql`
  `tests/test_backtest_repository.py`
- untracked: `calibration/peer_deviation.py` `calibration/peer_fetcher.py`
  `calibration/peer_report.py` `tests/test_peer_calibration.py`
  `tests/fixtures/msft_peer_info.json` `tests/fixtures/tsla_peer_info.json`

### T8 — LLM ops (api_guard 잔여 예산 추정)
- 전체: `pipeline/api_guard.py`(estimate_remaining)
- untracked: `HANDOFF_CODEX_llm_ops_A_B_2026-07-18.md`

### T9 — EDINET/일본 커버리지
- 전체: `pipeline/macro_data.py`(JP 성장률 1줄)
- untracked: `tests/test_edinet_client.py` `tests/test_jp_profile_curation.py`
  `tests/fixtures/edinet_toyota_mini.xbrl` `HANDOFF_edinet_japan.md`
  `HANDOFF_jp_profile_curation.md` `profiles/6758_t.yaml` `profiles/7203_t.yaml`
- 확인됨: `pipeline/edinet_client.py`는 tracked·clean (구현은 이미 커밋됨, 테스트만 잔류).

### T10 — 문서·규칙 일괄 (기능 트랙 미귀속분)
- 전체: `.claude/rules/scheduler.md`(weekly 출력 규칙 추가) ·
  `HANDOFF_CODEX_phase2_impl_scope_2026-07-18.md`(§12.5 추가분 — ⑤ 후속 docs) ·
  `HANDOFF_CODEX_p0-1.md`(1줄)
- untracked: `.claude/rules/`의 나머지 9개 rules 파일 · `AGENTS.md` ·
  `docs/RELIABILITY_REVIEW_2026-07-06.md` · 트랙 귀속이 불명확한 HANDOFF/PLAN/START/
  PROMPT/DEBATE/BACKLOG md 전부 (T1~T9에 명시된 것 제외).
- 권고: 트랙 소속이 명확한 handoff는 해당 트랙 커밋에 동반, 나머지는 docs 커밋 1개.

### T11 — profiles refresh (chore)
- `profiles/*.yaml` 수정 12개(005930·000660·003550·005380·066570·sk_ecoplant·aapl·
  amzn·gm·googl·msft·tsla) + untracked 13개(051900·090430·259960·456040·asml·avgo·
  chtr·hmc·meta·nexus·psky·spcx·unh).
- CLAUDE.md: profiles/는 AI-재생성 산출물(주간 파이프라인이 덮어씀). **chore 커밋 1개로
  일괄** 또는 커밋 제외 — 사용자 판단. 테스트 fixture로는 미사용(deselect 규칙 유지 중).

## 3. 권장 커밋 순서 + 검증

의존 사슬: T1(엔진 본체, test_engine 우산) → T2 → T3(MC 테스트가 T1 의존 가능) →
T4 → T5 → T6 → T7 → T8 → T9 → T10(docs) → T11(profiles chore).
- 각 커밋 후 `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip`
  1회 (호스트에선 deselect 불필요할 수 있음 — §7-1b 선례: 호스트에서 5건 통과).
- 중간 커밋 상태에서 일부 테스트가 미커밋 의존물을 참조해 실패하면 해당 테스트 파일을
  의존 트랙 쪽으로 이동 — 이 manifest는 정적 분석 기반이라 실행 순서 검증은 호스트 몫.
- 전 트랙 커밋 후 기대치: 신규 실패 0 (현 작업 트리 전체가 이미 호스트 1089/1093
  passed 상태로 검증된 몸통이므로, 분할 커밋의 위험은 '중간 상태'뿐).

## 4. 커밋 금지·정리 대상 (잔재물)

1. **쉘 리다이렉트 사고 잔재 (삭제 권고)**: `"대상"` `"목적"` `"부모"` `"자기소개서에"`
   (따옴표 포함 한글 파일명) · `type` — 내용 확인 후 삭제.
2. **스크린샷·임시물**: `_hx_44_check.png` `_hx_p4_check.png` `_hx_seg.png`
   `_nvda_p2_check.png` `_p3.png` · `tmp/` · `graphify-out/` · `.playwright-mcp/` ·
   `.agents/` — 삭제 또는 `.gitignore` 추가.
3. **로컬 상태**: `.claude-octopus/state.json`(M — 이미 ignore 대상 디렉터리 규칙 확인) ·
   `business-valuation-tool.code-workspace`(에디터 로컬 설정 +39줄 — gitignore 후보,
   커밋 원하면 별도 chore).
4. **일회성 검증 스크립트 (커밋 여부 사용자 판단)**: `verify_partB_excel.py`
   `verify_partB_round2.py` `regen_nexus_artifacts.py` `scripts/verify_nvda_phaseA*.py`
   `scripts/r16_profile_delta.py` `scripts/fill_peers.py` `scripts/nexus_dart_extract.py`
   `scripts/pilot_multiyear_quality.py`(v1 — v2는 ③으로 커밋됨).

## 5. 본 세션 표준 준수

- git 쓰기 명령 0 (status/log/show/ls-files/config 조회만, 전부 lock-safe 프리픽스는
  초회 status 1건 제외 — 그 1건이 §0-1의 index.lock 원인).
- 코드 파일 쓰기 0. 본 문서 1파일만 신규 (CRLF).
- 저장소 NUL 스캔·문서 무결성은 세션 말미 검증 결과를 §6에 기록.

## 6. 검증 기록

- 저장소 NUL 스캔 (py/md/yaml, 생성물 디렉터리 제외): **clean 0건**.
- 본 문서: 155줄 전부 CRLF · git 쓰기 명령 0 유지.
- `.git/index.lock` 잔존 (§0-1) — 호스트 제거 대기.

---
## 7. Codex 핸드오프 — 호스트 검증·커밋 실행 요청 (1번부터 번호 회신)

> 루프 위치: **Claude 분석 → Codex 독립 재현·실행 단계.** 본 문서 §1~§4는 샌드박스
> 정적 분석 산출물이다. Codex는 아래 요청을 **믿지 말고 독립 재현**한 뒤 1번부터
> 번호를 붙여 회신하라 (항목 누락·번호 건너뜀 금지 — 과거 2회 발생).

### 7.1 작업 규칙 (필수 — 위반 시 즉시 중단·보고)
- `git checkout -- <f>` / `git restore` / `git reset --hard` **절대 금지** (미커밋 작업
  다수 — 복구 불가).
- 커밋은 **선별 staging**(`git add <파일 목록>`)만. `git add -A`/`git add .` 금지
  (§4 잔재물·타 트랙 혼입 방지).
- 파일 수정 발생 시(원칙적으로 본 작업은 수정 0) `ast.parse` + 줄수 확인 · CRLF 유지.
- 작업 종료 직후 NUL 스캔 직접 실행·결과 원문 보고 (`.claude/rules/codex-cross-review.md`
  §1의 스크립트).
- 회귀표(§7.3)는 빈칸 없이 전부 채워서 보고. 이탈·생략은 사전 통보.

### 7.2 실행 요청
1. **index.lock 제거**: `.git/index.lock`이 0 byte이고 다른 git 프로세스가 없음을 확인
   후 삭제. 삭제 전 크기·mtime 보고.
2. **호스트 dirty 대조**: 호스트 `git status --porcelain` 실측 → (a) 내용 diff 51
   목록(§1·§2)과의 차집합 보고, (b) CRLF-only 113개가 호스트에서 실제로 clean인지
   확인 (불일치 시 커밋 전 원인 규명 — autocrlf 설정 차이 가능성).
3. **트랙 귀속 독립 검증** (특히 공유 파일): `tests/test_engine.py` +289줄이 전부
   Part B 우산(T1)인지 · `cli.py`·`output/excel_builder.py` 잔여 diff에 T5/T6 외
   hunk가 없는지 diff 원문으로 확인. 귀속 오류 발견 시 §2 수정안을 먼저 회신하고
   커밋 중단.
4. **T1~T11 순서 커밋 실행** (§3): 트랙당 1커밋, 커밋 후 즉시
   `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` +
   `verify_partB_round2.py`·`verify_partB_excel.py`(존재 시). 중간 상태 실패 시
   해당 테스트 파일의 트랙 재배치로 해결하고 재배치 내역 보고 (코드 수정 금지).
   T11(profiles)·§4 잔재물 삭제는 **사용자 확인 후에만** 실행.
5. **최종 검증**: 전 트랙 커밋 후 전체 pytest(기대: 기존 통과 수 이상, 신규 실패 0) ·
   NUL 스캔 clean · `git status`에 §4 잔재물과 T11 외 잔여 dirty 0 확인.
6. **판정 회신**: 커밋 해시 표(트랙별) + §7.3 회귀표 실측 + 발견 이슈.

### 7.3 회귀표 (빈칸 금지)
| # | 항목 | 실측 | 판정 |
|---|---|---|---|
| 1 | index.lock 제거 (크기/mtime 기록) | | |
| 2 | 호스트 내용 diff 51 정합 / CRLF 113 clean | | |
| 3 | 공유 파일 3종 귀속 검증 | | |
| 4 | 트랙별 커밋 해시 + 커밋별 pytest 결과 | | |
| 5 | 최종 전체 pytest (통과 수 명기) | | |
| 6 | NUL 스캔 원문 | | |
| 7 | 잔여 dirty = T11 + §4 잔재물만 | | |

---
## 8. Codex 1라운드 회신 → Claude 독립 재현·판정 — **수정 조건부 커밋 착수 GO**

2026-07-18. Codex 회신: §7.2-1·2 PASS(51개 정합·CRLF 113 호스트 clean·autocrlf=true
확인) · §7.2-3에서 귀속 오류 지적 후 규칙대로 커밋 중단. 지적 3건을 Claude가 독립
재현한 결과:

### 8.1 판정 (증거 기반)
1. **peer_stats 테스트 2건 → T4 이동: 인정.** 독립 재현 — 두 테스트 모두
   `calc_peer_stats(..., segment_methods={...})` kwarg를 소비하는데, 이 파라미터는
   HEAD `engine/peer_analysis.py` 시그니처에 **부재**(WT에서 추가됨). T1 시점 커밋 시
   TypeError로 중간 상태가 깨진다. Codex 지적 정확.
2. **`test_multiple_assumption_label_matches_lognormal_sampling` → T4 이동: 반박.**
   독립 재현 — 이 테스트의 의존은 (a) `valuation_runner._mc_raw_to_result` + Lognormal
   라벨(`valuation_runner.py:2328`, **HEAD와 byte 동일 — clean 파일**), (b)
   `MCInput.multiple_params`(HEAD `engine/monte_carlo.py:19`에 이미 존재)뿐.
   `peer_analysis` 의존 0. peer 계열 아님 — 이미 커밋된 라벨 동작의 테스트 고정이며
   MC 우산인 **T1 잔류**가 정확하다. (테스트명 유사성으로 인한 오분류로 추정.)
3. **`excel_builder.py`=T5 · `cli.py`=T6 정합 확인** — §2 유지.

### 8.2 §2 개정 (이 항목만, 나머지 불변)
- `tests/test_engine.py`의 diff 중 **peer_stats 2건 hunk만 T4**, 나머지(units ·
  market comparison · scenario · sensitivity · MC — lognormal 라벨 테스트 포함)는 T1.
- **스테이징 방식 (권고 a)**: `tests/test_engine.py` **파일 전체를 T4 커밋으로 이월**.
  T1 시점에 이 파일을 staging하지 않고, T1 커밋 메시지에
  `tests: follow in relative-valuation commit (shared test file)` 명시. T4에서 전체
  스테이징. 근거: hunk 수동 분리(`git add -p` + edit)는 오류 위험 대비 이득이 작고,
  중간 상태 무결성(실패 테스트 0)은 이월로 동일하게 보장된다.
- 대안 (b): Codex가 `git add -p`로 peer_stats 2건 hunk만 제외·분리 스테이징할 자신이
  있으면 T1/T4 분할 커밋 허용 — 단 T1 커밋 직후 `git stash` 없이
  `git diff --cached` 원문으로 분리 결과를 검증·보고할 것.

### 8.3 커밋 착수 GO (조건)
§8.2 반영을 조건으로 §7.2-4·5·6 실행을 승인한다. 추가 조건:
1. T1 커밋 전 `git diff --cached --stat` 보고 (staged 파일 목록이 §2 T1 목록과 일치
   확인 — test_engine.py 미포함(권고 a 채택 시)).
2. T4 커밋 전 동일 절차.
3. T11·§4 잔재물은 기존대로 사용자 확인 대기.
4. 회신은 §7.3 회귀표 빈칸 전부 + 트랙별 커밋 해시 표, 1번부터 번호.
