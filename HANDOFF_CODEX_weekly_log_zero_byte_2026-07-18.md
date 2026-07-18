# HANDOFF — CODEX: weekly 로그 0바이트 진단·수정 검증 + 커밋

**작성일:** 2026-07-18 (Claude 세션)
**트랙:** R18 잔여 백로그 ④ "weekly 로그 7/12~17 0바이트 진단" — 진단 확정 + 수정 완료
**요청:** ① 진단·수정 독립 재현 ② 게이트 통과 확인 ③ 커밋
**루프 위치:** Claude 구축 → **Codex 검증** (`.claude/rules/codex-cross-review.md`. 내 주장도 믿지 말고 재현하라)

---

## 1. 확정 진단 (증거 포함 — 각각 독립 재현 가능)

**7/12 이후 "주간 런"은 실제로 한 번도 돌지 않았다. 매일 생긴 0바이트 로그와
`valuation-results/2026-07-1{2..8}(Jul 3rd week)/` 폴더는 전부 pytest 부산물이다.**

### 원인 A — 0바이트 로그 = pytest import 부작용
- `scheduler/weekly_run.py`(수정 전 :90)가 **모듈 import 시점에** `logging.basicConfig(handlers=[..., FileHandler(...)])` 실행.
- `FileHandler`는 생성 즉시(`delay=False`) 파일을 만든다. 그런데 pytest는 collection 전에
  root logger를 이미 구성하므로 `basicConfig`는 **no-op** → 핸들러는 버려지고 **빈 파일만 남는다**.
- `weekly_run`을 import하는 테스트 모듈 4개: `test_scheduler.py`, `test_market_from_ticker.py`,
  `test_output.py`, `test_top_news_for_company.py` → **pytest 실행 = 그날의 0바이트 로그 생성.**
- 교차 증거: 로그 mtime이 전부 개발 세션 활동과 일치 (7/13 00:02↔커밋 `1c9ca8a` 00:29,
  7/15 09:29↔`scripts/verify_nvda_phaseA.py` mtime 09:29, 7/18 07:47↔R18 세션).

### 원인 B — 가짜 결과 폴더 = 테스트 오염
- 7/12~7/18 모든 `_weekly_summary.json`이 동일: `errors:["KR API 실패"]`, US `news_count:5, companies:[]`, valuations 0.
- 이는 `tests/test_scheduler.py::TestWeeklyRun::test_discovery_error_isolation`의 mock과 **문자 그대로 일치**:
  `side_effect = [RuntimeError("KR API 실패"), {"news_count": 5, "companies": []}]`
- 테스트가 `_save_run_start`/`_finalize_run`/`score_companies`만 mock — `run_weekly` 본체의
  `week_dir.mkdir()` + `_save_json_summary()`는 mock하지 않아 **실제 `valuation-results/`에 기록**.

### 파생 사실 (코드 문제 아님 — 사용자 몫)
- **진짜 주간 런의 마지막 실행 = 7/11 12:41** (`logs/weekly_20260711.log` 66줄, 실제 HTTP 기록).
  이후 Windows Task Scheduler 트리거 미발화 (작업 비활성화 또는 트리거 시각 PC off). 호스트에서만 확인 가능.

## 2. 구현 diff (이번 세션분 — 정확히 이것만이 내 변경)

### `scheduler/weekly_run.py` (3 hunks, ~+30줄)
1. 모듈 레벨 `logging.basicConfig(...)` 블록 삭제 → `def _setup_logging()` 신설:
   - **가드**: `if logging.getLogger().handlers: return` (pytest/임베딩 환경에서 무개입, 파일 미생성)
   - `FileHandler(..., delay=True)` (첫 레코드 전 파일 미생성)
   - docstring에 0바이트 로그 사고 경위 기록
2. `run_weekly()` 진입부(markets 기본값 대입 직전)에 `_setup_logging()` 호출 — `cli.py --weekly` 경로 커버
3. `main()` 첫 줄에 `_setup_logging()` 호출 — `python -m scheduler` / Task Scheduler 경로 커버

### `tests/test_scheduler.py` (2 hunks)
- `test_dry_run_skips_valuation` · `test_discovery_error_isolation`: 시그니처에 `tmp_path` 추가,
  `with patch("scheduler.weekly_run._RESULTS_BASE", tmp_path), patch("discovery...DiscoveryEngine")...`
  로 실 디렉터리 오염 차단 (전자에 사유 주석 포함).

## 3. 이미 수행한 검증 (샌드박스 실측)

| 검증 | 결과 |
|---|---|
| `ast.parse` 양 파일 | OK (weekly_run 963줄 / test_scheduler 312줄) |
| 시뮬레이션 case1: root 선구성 후 import+`_setup_logging()` | 파일 0개 생성, 핸들러 무변화 |
| 시뮬레이션 case2: 빈 root에서 `_setup_logging()`+레코드 1건 | 첫 emit 시점에 파일 생성·기록 확인 |
| `pytest tests/test_scheduler.py` | 35 passed |
| + `test_market_from_ticker.py` + `test_top_news_for_company.py` | 58 passed (supabase 설치 후 전건) |
| 실행 후 부작용 | `valuation-results/` 무변경 (7/18 summary mtime 08:29 유지), 신규 로그 0건 |

주의: 검증 중 probe 1줄이 `logs/weekly_20260718.log`에 기록됐다가 0바이트로 원복함. 정상.

## 4. Codex 태스크

### T1 — 독립 재현 (호스트)
1. `pytest tests/` 전체 (기준: 11dc9f0 시점 1017 passed, 5 deselected — deselect는
   `--deselect tests/test_engine.py::TestScenarioDriverRoundTrip` 유지). **새 실패 0 확인.**
2. 실행 전후 `logs/` 목록 비교 → **새 0바이트 weekly 로그가 생기지 않아야 함** (수정의 핵심 효과).
3. 실행 전후 `valuation-results/` 목록·mtime 비교 → 무변경 확인.
4. (선택) §1 증거 스팟체크: `test_discovery_error_isolation`의 side_effect vs 아무
   `2026-07-1x(Jul 3rd week)/_weekly_summary.json` 대조.

### T2 — 게이트
- NUL 스캔 (rules 파일의 os.walk 스니펫 그대로) — **직접 실행, 보고서에 수치 첨부**
- `ast.parse` + `wc -l` — 로컬 인터프리터로 (셸 read 불신)

### T3 — 커밋
🔴 **비파괴 staging만**: `git add`만 허용. `git checkout --`/`git restore`(worktree)/`git reset --hard`/`git stash` 금지.

- 두 파일 모두 HEAD 대비 **CRLF 전면 churn + 선행 세션 미커밋분이 섞여 있다**
  (`git diff HEAD` = 사실상 전체 파일 / `git diff --ignore-cr-at-eol --stat HEAD` = weekly_run 175줄·8 hunks,
  test_scheduler 68줄·3 hunks. 이 중 이번 세션분은 §2의 3+2 hunks뿐).
- 라인엔딩 churn 때문에 `git add -p` hunk 분리가 **불가능**하다 (평문 diff가 단일 hunk).
  → **전례(`1895fcc` "hunk 비분리") 따라 두 파일 전체 커밋.** 단, 커밋 전에
  `git diff --ignore-cr-at-eol HEAD -- <두 파일>` 전문을 읽고 **§2 외 hunk가 어떤 선행 트랙
  잔여분인지 식별해 커밋 메시지에 명기**할 것 (아마 R16 draft gate 관련). 식별 불가능한
  의심 hunk 발견 시 커밋 중단하고 보고.
- 본 문서 + 커밋 대상: `scheduler/weekly_run.py`, `tests/test_scheduler.py`,
  `HANDOFF_CODEX_weekly_log_zero_byte_2026-07-18.md`. **다른 파일 절대 add 금지** (272+ dirty).

메시지 제안:
`fix(scheduler/tests): weekly 로그 0바이트 근절 — 로깅 lazy화(import 부작용 제거) + TestWeeklyRun 결과 디렉터리 오염 차단 (+ 선행 잔여분 hunk 비분리)`

## 5. 이 커밋에 포함하지 않는 것 (섞지 말 것)

| 항목 | 처리 |
|---|---|
| 가짜 아티팩트 정리 (7/12~18 폴더 7개 + 0바이트 로그) | 사용자 승인 대기 — 삭제하지 마라 |
| Task Scheduler 미발화 | 호스트 확인 — 사용자 몫 |
| T3 유료 측정 / F5 예산표 / F1b sonnet-5 / draft_blocked 렌더 / 035420.yaml | R18 잔여 백로그 별건 |
