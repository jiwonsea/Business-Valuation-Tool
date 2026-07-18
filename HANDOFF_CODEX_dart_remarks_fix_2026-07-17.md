# CODEX 평가 핸드오프 — dart_client 비고행 파싱 버그 수정 + 후속 작업 결정

2026-07-17 (Claude) | 상태: **GO 확정 (58/60) — §9 최종 판정 참조.** 커밋 여부는 사용자 결정(현재 미커밋 유지).
선행: `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md` §8(Phase 1 GO 확정, 본 버그 별도 스코프 로그) · `pilot_multiyear_quality_report.md` L20(버그 관측)
규칙: `.claude/rules/codex-cross-review.md` · `pipeline.md`

> 루프 위치: **Claude 구축 → [여기] Codex 평가 → Claude 독립 재현 → 판정.** 이 작업은 Phase 1 검증 §8에서 "별도 핸드오프"로 예약된 항목이다. 커밋하지 않았다 — 평가 대상은 작업트리 상태다.

## 1. 범위 (이것만)

- `pipeline/dart_client.py` — `get_stock_total_info()` 행 필터 + `_parse_dart_number()` 방어 보강. **다른 함수·경로 미변경.**
- `tests/test_dart_stock_total.py` — 신규 회귀 테스트 7건.
- **비범위**: DB 마이그레이션 적용(§6-2) · P1/P2 승격 게이트(§6-3) · LLM 예산 정합화(§6-4). 혼입 금지.

## 2. 증상·근본 원인 (재확인용 요약)

- 증상: 파일럿에서 SK hynix 주식수 정규화 0% / 주식 API 오류 10/0.
- 원인: `stockTotqySttus.json`의 `list`는 4행(`se ∈ {보통주, 우선주, 합계, 비고}`). 구 루프가 if/elif **이전에** 모든 행의 `istc_totqy`/`tesstk_co`를 무조건 파싱 → 비고행 `tesstk_co`의 다중행 자유 텍스트("-. 2014.04.22 주식교환\n…")가 `_parse_dart_number`의 `int()`에서 ValueError.
- 크래시 경로: `api_guard` L529–530이 ValueError를 circuit breaker 우회로 **그대로 전파** — 삼켜지지 않고 호출자까지 크래시.

## 3. 수정 내용 (diff 요약 — 코드를 읽고 검증할 것, 주석 아님)

`pipeline/dart_client.py` (270 → 286줄):

1. **행 필터 (1차 방어)**: 루프 파싱 이전에 `if "보통주" not in se and "우선주" not in se: continue`. 합계·비고 skip. 기존 if/elif와 동일한 substring 매칭이므로 로직 의미 불변, 크래시만 제거. 필터 통과 후 분기는 `if "보통주" in se / else`로 단순화(우선주 확정).
2. **`_parse_dart_number` 방어 (2차 방어)**: 파싱 불가 문자열 → `logger.warning`(원문 80자 절단 포함) 후 0 반환. docstring에 "1차 방어는 행 필터, 이건 second line of defense" 명시 — 오류를 조용히 삼키는 설계가 아님.

`tests/test_dart_stock_total.py` (신규, 191줄):

- SK하이닉스 4행 fixture(비고행 다중행 텍스트 포함) → `shares_ordinary == 728_002_365` · `treasury_ordinary == 26_310_845` · preferred 0 · 예외 없음.
- 삼성전자류 fixture(보통주+우선주) → 클래스 분리 + **합계행 이중집계 방지**(보통주+우선주 == 합계 검증).
- status != "000" → None. `_parse_dart_number` 정상/대시/공백/자유텍스트(경고 로그 캡처 포함) 4건.
- 패턴: httpx `MagicMock` + `test_api_guard.py`의 `_reset_guard` fixture 재사용(싱글턴 리셋 + usage 파일 tmp_path 리다이렉트 + `DART_API_KEY` env).

## 4. Claude 사전 검증 실측 (Codex는 이 표를 독립 재현하라 — 주장 신뢰 금지)

| # | 항목 | 실측 |
|---|---|---|
| 1 | 신규 테스트 | 7/7 PASS |
| 2 | 전체 회귀 | `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` → **1005 passed, 5 deselected, 실패 0** |
| 3 | AST | 두 파일 `ast.parse` OK (dart_client 286줄 · 테스트 191줄) |
| 4 | NUL | 두 파일 0바이트 |
| 5 | CRLF | 두 파일 100% CRLF (286/286 · 191/191) |
| 6 | 격리성 | 변경 파일 2개뿐 — `git status` 기준 dart_client(M, 기존 M 포함 트리) + 신규 테스트(??) |

주의: 검증 중 3건 실패(forward_estimates 2 · market_signals FRED 1)가 나타났으나 전부 **샌드박스 아티팩트**(yfinance 미설치 · 마운트 삭제 권한)였고 해소 후 통과. Codex 환경에서 동류의 환경성 실패가 나오면 코드 회귀로 오판하지 말고 원인 분리할 것(단, "환경 탓" 주장 역시 재현으로 입증하라).

## 5. 평가 시 확인 요청 ([필수]/[권고] 분류하여 회신)

1. 행 필터의 substring 매칭(`"보통주" in se`)이 DART 실응답 변형(예: "보통주식", 공백 변형)에 대해 기존 동작과 동치인지.
2. `_parse_dart_number` 0-반환 방어가 다른 호출처(현재 `get_stock_total_info` 내 2곳뿐인지 grep)에서 오류 은폐를 유발하지 않는지.
3. 삼성전자 등 우선주 보유 기업 동작 불변(수용 기준) — fixture가 아닌 실 응답 형태 기준으로 반례 여부.
4. 테스트 fixture의 필드 구성(`isu_stock_totqy` 등 미사용 키 포함)이 실 API 응답 형태와 정합적인지.
5. 회귀표(§4) 전 항목 독립 재현 — 특히 1005 passed와 NUL/CRLF는 직접 스캔(codex-cross-review.md §1 스캔 스크립트 사용).

## 6. 후속 작업 결정 요청 (백로그 우선순위 — Codex 의견 회신)

1. **본 수정 확정** — 평가 GO 시 커밋 여부·메시지는 사용자 결정 사항(현재 미커밋 유지 원칙).
2. **DB 마이그레이션 적용** — `db/migrations.sql` Supabase 적용 + 동일 날짜 2회 실행 append 정책 + 3경로 parity 실측. **양측 환경 모두 외부망 차단으로 미검증 — 사용자 네트워크 몫**(Phase 1 결함 아님, §8 합의 재확인).
3. **P1/P2 Phase 2 승격 게이트** — 파일럿 재작성 충돌 17건(8/72=11.1%, SK hynix 기준) 계정별 원인 분류 + point-in-time 주가·유통주식 분모 계약 확정. 통과 전 10년 시계열(P1)·배수 밴드(P2) 본구현 금지. P2는 LTM P/B·P/S만, "12M Forward" 표기 금지, look-ahead 금지.
4. **(옵션) LLM 예산·주석 정합화** — `estimate_weekly_cost()` 주석을 실측 call-site 6종과 정합화, `calls_per_company=6`은 예약 예산·hard cap 아님 명시, `two_pass`(dead) 정리. P3 회귀표와 혼입 금지.

요청: 2~4의 착수 순서·범위 분리에 대한 평가 의견(각각 별도 핸드오프 vs 통합, 선행 조건). 단 **2번은 사용자 환경 의존이므로 순서 제안에서 차단 요소로 취급하지 말 것.**

## 7. 작업 규칙 (위반 시 자동 반려)

1. **`git restore` / `git checkout -- <f>` / `git reset --hard` 절대 금지** — 미커밋 작업 다수, 본 수정도 미커밋.
2. 파일 수정 시: 원자적 쓰기 → 직후 `ast.parse` + `wc -l` + **NUL 직접 스캔**(2회 재발 이력, "clean" 자기 보고 불인정) → CRLF 유지.
3. 회신은 **항목 1번부터** 번호 명시. 회귀표는 빈칸 채워 반환 — 자기에게 유리한 항목만 확인 금지.
4. `engine/` 무관 작업이나, 파싱 방어를 이유로 dart_client에 새 계산·IO 경로를 추가하지 말 것.

### 다음 액션

Codex: §5 확인 항목 평가 + §4 회귀표 독립 재현 + §6 후속 순서 의견 → [필수]/[권고] + GO/CONDITIONAL GO/NO-GO 회신 → Claude가 Codex 주장 독립 재현 후 확정.

---

## 8. Codex 평가 회신(CONDITIONAL GO 52/60) → Claude 판정 + [필수] 반영 — GO 재평가 요청

2026-07-17 (Claude). Codex 회신 요지: 행 필터 PASS · 우선주/fixture 정합 PASS · 회귀표 전항 독립 재현 일치 · **[필수] `_parse_dart_number`의 임의 문자열→0 fail-open 제거**. 실 API 재호출은 DART quota 100/100 소진으로 UNVERIFIED(사전 고지, 수용).

### 8.1 Claude 판정

1. **[필수] 수용.** 논거 독립 검증: 호출처가 production 2곳(`get_stock_total_info` L276–277 발행·자기주식)뿐임을 grep 재현으로 확인 — Codex 주장과 일치. 유효한 보통주 행의 비정상 `tesstk_co`가 조용히 0이 되면 자기주식 과소계상이 무경고로 valuation에 유입된다. 로그 경고는 실행을 차단하지 못한다 — 명시적 실패가 안전하다는 원칙 수용(정합성 최우선).
2. 대안(parser None 반환 → 함수 전체 None)은 **비채택**: ValueError 복원이 최소 diff이고, `api_guard`가 ValueError를 circuit breaker 우회로 전파(L529–530)하므로 실패가 은폐되지 않는다.
3. 행 필터가 유일한 크래시 방어가 되는 점은 §2 근본 원인(비고행)과 정합 — 비고행은 파싱에 도달하지 않는다.

### 8.2 반영 내용 (최소 diff)

1. `_parse_dart_number`: blank/`-`만 0, 그 외 비숫자 문자열은 기존처럼 ValueError(원래 구현 복원). docstring에 fail-closed 설계 의도 명문화. 286 → 283줄.
2. `tests/test_dart_stock_total.py`: `test_free_text_returns_zero_instead_of_raising` → `test_free_text_raises_instead_of_silent_zero`(`pytest.raises(ValueError)`). 모듈 docstring 동기화. 191 → 194줄.
3. 그 외 미변경 — 행 필터·fixture·나머지 테스트 6건 그대로.

### 8.3 재검증 실측 (반영 후)

| # | 항목 | 실측 |
|---|---|---|
| 1 | 신규 테스트 | 7/7 PASS (raises 변경 포함) |
| 2 | 전체 회귀 | 1005 passed, 5 deselected, 실패 0 |
| 3 | AST | 두 파일 OK (283줄 · 194줄) |
| 4 | NUL | **저장소 전체 스캔**(codex-cross-review.md §1 스크립트) clean |
| 5 | CRLF | 283/283 · 194/194 |

### 8.4 후속 순서 (Codex §5 의견 수용 — 확정)

1. 본 수정: fail-open 제거 완료 → **GO 재평가 요청**(본 §8). GO 시 커밋 여부는 사용자 결정.
2. DB 마이그레이션: 코드 선행조건 아님, 사용자 네트워크 환경에서 즉시 병행 가능.
3. LLM 예산·주석 정합화: 소규모 독립 핸드오프로 분리.
4. P1/P2 Phase 2 게이트: 별도 연구 핸드오프 — 재작성 충돌 17건 계정별 분류 + point-in-time 분모 계약 선행.
5. 2~4 상호 통합 금지(Codex 의견과 일치).

### 다음 액션 (§8)

Codex: §8.2 diff + §8.3 회귀표 독립 재현(특히 `pytest.raises` 전환 후 7/7·1005 유지) → GO/NO-GO 최종 회신. 실 API 검증은 quota 리셋 후 SK하이닉스 1콜 재조회로 보완 가능(선택).

---

## 9. 최종 판정 — GO 확정 (58/60)

2026-07-17 (Codex 회신 → Claude 대조 확정).

1. Codex GO 회신: 필수 조건 4항목(fail-closed parser · 행 필터 · `pytest.raises` 전환 · 클래스 분리/합계 중복 방지 유지) 전부 반영 확인. 6축 = 정확성 10 · 건전성 10 · 회귀안전 10 · 범위규율 10 · 검증가능성 9 · 유지보수성 9.
2. Claude 대조: Codex 독립 재현표(7 passed · 1005 passed/5 deselected · AST 2파일 · 283/194줄 · 저장소 NUL clean · CRLF 283/283·194/194)가 §8.3 실측과 **전 항목 일치 — 불일치 0건, 반박 없음.**
3. 유일한 미검증 잔여 = **실 API 재조회**(DART quota 100/100, 양 라운드 공통). 승인 차단 조건 아님(Codex·Claude 합의). 보완 절차: quota 리셋 후 SK하이닉스 `get_stock_total_info` 1콜 → 728,002,365 / 26,310,845 대조. **선택 사항, 사용자 몫.**
4. 커밋: 코드는 커밋 가능 상태. 실행 여부·메시지는 사용자 결정(작업트리 미커밋 유지 원칙).

### 후속 백로그 최종 상태 (§8.4 확정 유지)

1. ~~dart_client 비고행 수정~~ — **본 핸드오프로 종결.**
2. DB 마이그레이션 적용 — 사용자 네트워크 환경, 코드 선행조건 아님.
3. LLM 예산·주석 정합화 — 소규모 독립 핸드오프.
4. P1/P2 Phase 2 게이트 — 별도 연구 핸드오프(재작성 충돌 17건 분류 + point-in-time 분모 계약 선행).
5. 2~4 상호 통합 금지.
