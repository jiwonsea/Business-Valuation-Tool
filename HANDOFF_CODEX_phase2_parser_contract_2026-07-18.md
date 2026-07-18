# Phase 2 착수 1단계 — parser 데이터 계약 보강 (조건부 GO §7.2 이행)

2026-07-18 (Claude) | 상태: **1차 작업 완료 — 회귀표 8/8 PASS · Codex 교차검증 대기**
계약: `HANDOFF_CODEX_c_gate_research_2026-07-18.md` §7.2 조건 5개 (완화 없음, 그대로 구현)
선행: 동 문서 §3(파서 위험 신호)·§7.3(해시 = sha256 명기 규칙) · `pilot_multiyear_quality_report_v2.md` · `research/pilot_v2/conflict_classification.md`

> 루프 위치: **구현 산출물 제출 단계.** Codex는 §5 교차검증 요청에 1번부터 번호를 붙여
> 독립 재현으로 회신하라. 주장(diff·pytest·해시)은 값·grep·재실행으로 검증할 것. 해시는 전부 sha256.

## 1. 세션 시작 검증 기록

1. `git log --oneline -15` + `git status`: HEAD=1895fcc, 커밋 3분리(① dart_client+tests
   ② api_guard+analyst ③ 파일럿 v2 일체)는 **미실행 — 선행 세션 산출물 전부 미커밋 상태 그대로**.
   백로그 유효, 갱신 불요.
2. 필독 3종 완독. 파일럿 v2 산출물 3종의 작업 전 sha256이 §7.3 문서값과 일치함을 확인(기준선).
3. mtime 이상 2건(`ai/llm_client.py`·`pipeline/profile_generator.py`, 07-18 07:53) — 원인
   미확인 상태 유지, 사용자 확인 대기(본 작업 비차단). 본 세션은 두 파일 미접촉.
4. 사전 검증(구현 전): 스냅샷 30 payload 전수 스캔 — sj_div 결측 0 · 신규 계약 적용 시
   기존 선택값과 차이 0건 · 동일 statement 내 값 충돌(ambiguity) 0건 (thstrm/frmtrm 양측).
   → fail-closed가 실데이터에서 오발동하지 않고 sha256 불변이 구조적으로 보장됨을 먼저 확정.

## 2. 구현 내역 (§7.2 조건 ↔ 코드)

| §7.2 | 구현 | 위치 |
|---|---|---|
| 1. 계정별 허용 statement 고정 | `STATEMENT_CONTRACT`: revenue/op/net_income/interest→IS·CIS · assets/liabilities/equity→BS · capex→CF. 주 루프가 계약 외 statement 행(특히 SCE `당기순이익`, 비지배 단독 3,103 행 포함)을 후보에서 원천 배제. `_statement_of()`는 sj_div 우선, sj_nm 한글명 fallback, 무표기 행은 후보 불가 | `pipeline/dart_parser.py` |
| 2. 우선순위 명문화 + fail-closed | (a) statement 우선순위 = 계약 튜플 순서(IS가 CIS에 우선) (b) 동일 statement 내 후보 값 전원 동일 → payload 순 첫 행 (c) 값 상이 → `AmbiguousAccountError` (silent 선택 금지, `_parse_dart_number` 선례). 규칙은 모듈 docstring에 계약으로 명문화 | 동일 파일 `_select_by_contract()` |
| 3. 별칭 정식 registry + 연도 교차 fixture | `ACCOUNT_ALIASES`/`CAPEX_ALIASES`가 정본, `ACCOUNT_MAP`/`CAPEX_MAP`은 파생 뷰(기존 소비자 하위호환 — 이름·내용 동일). fixture는 `raw_payloads.json`에서 오프라인 추출(신규 DART 콜 0): hynix FY2019/2020 + LG FY2020/2021(`영업이익`↔`영업이익(손실)` 별칭 교차 실물) | `tests/fixtures/dart_pilot_v2_subset.json` |
| 4. 최초 공시/재작성 별도 보존 | `extract_reported_values()`: 동일 payload에서 basis="original"(thstrm, FY) / basis="restated_comparative"(frmtrm, FY-1) 분리 산출, 재작성값이 원본을 덮지 않음. `ReportedFinancialValue`는 frozen Pydantic(변경은 `model_copy`만) + `extra="forbid"`. 기존 스키마(`schemas/models.py`) 무변경 → YAML 하위호환 자명 | `schemas/point_in_time.py` (신규, models 역참조 금지 — provenance와 동일 규칙) |
| 5. point-in-time | `available_at_from_rcept_no()`(접수번호 14자리 검증, 선두 8자리=접수일, 위반 시 raise) · `select_point_in_time()`: basis="original"만 + `available_at<=t`만 + 무자격 시 None(보간·소급 금지) + 다중 원본 시 최초 공시 우선 · `require_allowed_multiple_label()`: LTM P/B·P/S만 허용, forward 계열 라벨 raise | 동일 파일 |

설계 결정 3건 (Codex 검토 대상):
1. IS > CIS 우선순위 근거: 전용 손익계산서가 동일 라인을 재게시하는 포괄손익계산서에 우선.
   다른 statement 간 값 상이는 ambiguity가 아님(우선순위로 결정론적 해소) — ambiguity는
   동일 statement 내로 한정.
2. `parse_financial_statements`(legacy dict 경로)는 빈 금액→0 코어스 등 기존 값 의미론을
   보존(회귀 0 목표). 신규 API `extract_reported_values`는 빈/'-'를 결측 처리(0 날조 금지).
3. `select_point_in_time` 다중 원본(재제출 연차보고서) 시 최초 available_at 우선 = 최초 공시값.

## 3. 변경 파일 (본 세션 쓰기 전량)

| 파일 | 상태 | 비고 |
|---|---|---|
| `pipeline/dart_parser.py` | 수정 (468줄) | LF 유지 — 세션 시작 시점부터 LF인 예외 파일, 전면 개행 diff 방지 |
| `schemas/point_in_time.py` | 신규 (157줄, CRLF) | |
| `tests/test_dart_parser_contract.py` | 신규 (271줄, CRLF, 20 tests) | |
| `tests/fixtures/dart_pilot_v2_subset.json` | 신규 (CRLF) | 스냅샷 오프라인 추출 |
| 본 문서 | 신규 (CRLF) | |

## 4. 회귀표 (완화 없음, 해시 = sha256)

| # | 기준 | 실측 | 판정 |
|---|---|---|---|
| 1 | 전체 pytest 무회귀 (deselect 규칙 유지) | 1036 passed / 5 deselected / 1 failed — 실패는 `test_market_signals.py::test_fred_series_missing_values`, `.cache/market_signals/fred/DFF.json` unlink `PermissionError`. 샌드박스 마운트가 unlink 자체를 금지(`rm`도 동일 실패)하는 환경 결함이며 해당 테스트는 변경 코드와 import 관계 0. 호스트 재확인을 §5-1로 요청 | PASS* |
| 2 | 파일럿 v2 `--analyze` 산출물 sha256 불변 | report `324f8afe53de9037149a1b8dc7bed3545d5ea367b4dbb2a7ac5ffc71497b783a` · cls.md `06971373b6662008d5b7b3659623f7c29aafd1c610e1b5d3c5025bc90fef997e` · cls.csv `db15163cfbf7a52d303886afad94f0acd328068e7dae0c887a429e35716d8105` — 3종 모두 작업 전 기준선과 동일. snapshot `c1ab94c753ec4b5633ccaed9b69c446c66f6f8b7082256180d847bf0980fb099` 무변경(읽기만) | PASS |
| 3 | 신규 fixture 단위 테스트 (SCE 혼입·별칭 교차·ambiguity 각 ≥1) | 20/20 pass: SCE 차단 3(재배열 포함) · 우선순위/ambiguity 4 · 별칭 registry 3 · basis 분리 3 · point-in-time 5 · 스냅샷 30 payload 전수 parity 1 · 계약 커버리지 1 | PASS |
| 4 | 신규 DART 콜 0 | 네트워크 호출 0 — fixture·검증 전부 스냅샷 재사용 | PASS |
| 5 | engine 순수성 | `engine/` 무변경. 신규/수정 모듈에 IO import 0 (`httpx`/`requests` 등 없음) | PASS |
| 6 | NUL/AST/CRLF | 저장소 전체 NUL scan(cross-review §1 스크립트) clean · 3개 .py AST OK + 줄수 확인 · 신규 파일 CRLF, `dart_parser.py`는 기존 LF 유지 | PASS |
| 7 | 커밋 아님 | git 쓰기 명령 0 (읽기 전용 log/status만) | PASS |
| 8 | 소급 0 · 보간 금지 · LTM만 · "12M Forward" 금지 | `select_point_in_time` original-only + `available_at<=t` 게이트 + 무자격 None · `require_allowed_multiple_label` LTM P/B·P/S 허용목록 — 전부 테스트로 고정 | PASS |

실측 하이라이트 (스냅샷 실데이터):
- hynix FY2019 `net_income`: SCE 행을 payload 선두로 재배열해도 CIS 2,016,391 선택
  (행 순서 우연 보호 → 계약 보호로 전환 확인).
- LG op: FY2020 원본 3,194,987(접수 2021-03-16) / FY2021 보고서의 재작성 comparative
  3,905,108(접수 2022-03-16, 별칭 `영업이익(손실)` 기록) 분리 보존.
  `select_point_in_time(…, 2020, t=2022-06-30)` = **3,194,987 (original)** — 재작성값 미소비.
  t=2021-03-15(접수 전) = None (look-ahead 차단).

## 5. Codex 교차검증 요청 (1번부터 번호 회신, 독립 재현)

1. **호스트 pytest 전체 재실행** (deselect 규칙 유지): 1037 passed 기대 —
   특히 `test_market_signals.py::test_fred_series_missing_values`가 호스트에서 통과함을 확인
   (회귀표 #1의 환경 결함 판정 반증/확정).
2. **`--analyze` 재실행 + sha256 3종 대조**: §4-2의 값과 일치 확인 (sha256 명기 규칙 §7.3).
3. **스냅샷 parity 독립 재현**: `pytest tests/test_dart_parser_contract.py -q` 20/20 +
   `test_full_snapshot_parity_with_pre_contract_selection`(30 payload, 계약 전후 선택값 diff 0).
4. **중점 감사**: (a) SCE 재배열 케이스(§4 하이라이트)의 계약 보호 (b) `AmbiguousAccountError`
   fail-closed 경로 (c) §2 설계 결정 3건(IS>CIS · legacy 0-코어스 보존 · 최초 공시 우선)의 타당성.
5. **판정**: §7.2 조건 5개 충족 여부 → Phase 2 본구현(10년 시계열·historical band) 최종 승인.

## 6. 후속 백로그 (불변 + 갱신)

1. ~~Codex 교차검증(§5)~~ — **완료·승인** (§7).
2. DB 마이그레이션 적용 — 사용자 네트워크 몫(불변).
3. 미커버 필드(eps/bps/dps/roic/fcf)·D&A 주석 원문 경로 — 본구현 범위, 게이트 통과로 착수 가능.
4. 커밋 단위(사용자 결정 대기): 기존 3분리 + ④ 본 세션(파서 계약 일체) 추가 제안.
5. ~~mtime 이상 2건~~ — **원인 규명·종결** (§7-4).

---

## 7. Codex 교차검증 회신 → Claude 독립 재현·대조 — 게이트 **최종 GO** 확정

2026-07-18. Codex 회신 5항목 전 PASS + **Phase 2 본구현 승인**. cross-review 루프에 따라
주장을 값·재실행으로 독립 재현한 대조 결과:

1. **pytest**: Codex "1042 passed / 0 failed / 0 deselected" — 산술 정합
   (본 세션 1036 passed + 5 deselected + 1 env-failed = 1042). 두 하위 주장 독립 재현:
   (a) `test_fred_series_missing_values` 호스트 통과 → 회귀표 #1의 샌드박스 환경 결함
   판정 **확정** (PASS* → PASS). (b) 과거 deselect 대상 `TestScenarioDriverRoundTrip`을
   샌드박스에서 재실행 → **5 passed 재현**. 단, 통과 원인은 현 `profiles/*.yaml` 상태가
   우연히 정합하기 때문이며 근본 원인(주간 파이프라인의 profiles 재생성 drift)은 미해소 —
   **CLAUDE.md의 deselect 규칙은 fixtures 분리 전까지 유지**(통과가 규칙 폐기 근거 아님).
2. **sha256 3종**: Codex 재실행 후에도 §4-2 값과 byte-identical — 본 세션 재검증으로 재확인.
3. **파서 계약 20/20 + 30 payload parity 0 diff**: 재현 일치.
4. **부수 발견 — mtime 이상 2건 원인 규명·종결**: 대조 중 HEAD가 1895fcc → **11dc9f0**로
   전진한 것을 발견. `git show` 확인 결과 author=사용자(jiwonsea), 2026-07-18 08:11,
   R18 트랙 커밋(`ai/llm_client.py` + `pipeline/profile_generator.py` + R18 핸드오프/테스트
   9파일, 본 세션 산출물 미포함). 07:53 mtime 갱신 = **동시 실행된 호스트 R18 작업**으로
   확정, 이후 사용자가 커밋. 무결성 이상 없음 — 백로그 종결. Codex의 "커밋하지 않았다"
   주장도 참(커밋 주체는 사용자·파일 범위 분리 확인).
5. **판정 기록**: §7.2 조건 5개 충족 — **Phase 2 본구현(10년 시계열·historical band) 승인**.
   차기 세션 시작 검증 기준 HEAD = 11dc9f0. 본 세션 4파일 + 본 문서는 여전히 미커밋
   (커밋 단위 ④, 사용자 결정 대기).

### 차기 세션 프롬프트 (Codex 제안 + 상태 반영 갱신)

> Phase 2 parser 계약 게이트가 Codex 교차검증에서 승인되었다
> (`HANDOFF_CODEX_phase2_parser_contract_2026-07-18.md` §7, HEAD=11dc9f0 기준).
> 10년 시계열·historical band 본구현을 시작하되, 먼저 acceptance criteria와 변경 파일
> 범위를 제안하라. 소비 계약: `STATEMENT_CONTRACT`/`extract_reported_values`/
> `select_point_in_time`만 사용(§7.2-5: original·available_at·보간 금지·LTM P/B·P/S만).
> 미커버 필드(eps/bps/dps/roic/fcf)·D&A 주석 경로 포함 여부를 범위 제안에 명시할 것.
