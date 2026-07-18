# Phase 2 본구현 범위 제안 — P1 10년 시계열 + P2 historical band (1단계)

2026-07-18 (Claude) | 상태: **범위·acceptance criteria 제안 — Codex 정책 회신 대기 (코드 변경 0)**
계약: `HANDOFF_CODEX_phase2_parser_contract_2026-07-18.md` §7(최종 GO) · 소비 계약 =
`STATEMENT_CONTRACT`/`extract_reported_values`/`select_point_in_time`만 (§7.2-5: original ·
available_at≤t · 보간/소급 금지 · LTM P/B·P/S만 · "12M Forward" 금지)
선행: `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md` §4(P1/P2 정의·하드 제약) ·
`HANDOFF_CODEX_next_scope_decision_2026-07-17.md` §6.3-3(point-in-time 원칙) ·
`pilot_multiyear_quality_report_v2.md`

> 루프 위치: **정책 논쟁 단계.** 본 문서는 구현 전 범위 계약 확정용이다. Codex는 §5 질의에
> 1번부터 번호를 붙여 회신하라. 확정 전 코드 수정 금지(본 세션 쓰기 = 본 문서뿐).

## 1. 세션 시작 검증 기록

1. `git log --oneline -15`: HEAD=**11dc9f0** — §7 판정 기록의 기준 HEAD와 일치. 이후 커밋 0.
2. 중복 착수 확인: `pipeline/`·`engine/`·`schemas/`에 시계열/밴드 구현체 없음.
   `select_point_in_time`/`extract_reported_values` 소비자는 현재 파서·테스트뿐 — 본구현 미착수 상태 확정.
3. 파서 계약 4파일(§3)은 여전히 미커밋(커밋 단위 ④, 사용자 결정 대기) — 본 제안은 그 위에 쌓인다.
4. 명명 충돌 주의: `schemas/history.py`·`output/sheets/history.py`는 **P3(내재가치 이력)** 소유.
   본 작업은 `timeseries`/`band` 명명으로 분리(§3).

## 2. 범위 제안

### 2.1 포함 (1단계)

1. **P1 10년 시계열**: 회사×연도×계정의 point-in-time 관측 시리즈.
   - 계정 = **`STATEMENT_CONTRACT` 8계정만** (revenue/operating_income/net_income/
     interest_expense/total_assets/total_liabilities/total_equity/capex) + 주식수(발행−자기,
     stockTotqySttus). 재무값 접근은 `extract_reported_values`(basis="original") +
     `select_point_in_time` 경유만 — legacy `parse_financial_statements`/`ACCOUNT_MAP` 직접 소비 0.
   - 결측 = 결측(관측 제외). 보간·현재 snapshot 소급·재작성값 대체 일절 금지.
2. **P2 historical band**: 시리즈로부터 **LTM P/B·P/S** 관측치(연 1회, t=사업보고서 접수일)
   → 밴드 통계(min/p25/median/p75/max, n_obs, 결측 연도 목록). 현재 배수의 밴드 내 위치 표출.
   - 분자 = 접수일 **raw close**(수정주가 금지) × 당시 유통주식수. corporate action으로 raw
     복원 불확실 시 해당 연도 관측 제외 + 경고 (§6.3-3).
   - 라벨은 전부 `require_allowed_multiple_label` 통과 강제.
3. **표출 = reporting-only**: Excel 시트/console report에 참고 밴드로만 렌더.
   `run_valuation` 입력으로 불소비 (Phase 1 DEBATE에서 engine 연결 REJECT 유지).
4. 1단계 검증 대상 = **파일럿 3사(삼성전자·SK hynix·LG전자)×10년, 신규 DART 콜 0**
   (`research/pilot_v2/raw_payloads.json` 스냅샷 전량 재사용). 가격 시리즈만 yfinance(quota 무관).

### 2.2 제외 (명시 — 차기 세션 프롬프트 요구사항)

1. **미커버 필드 eps/bps/dps/roic/fcf — 제외.** 근거: (a) 1차 허용 배수 LTM P/B·P/S의
   분모는 equity·revenue로 계약 내 완결 — P/B는 시총/자본총계 직접 계산, 주당 지표 파생
   불필요. (b) 추가하려면 `STATEMENT_CONTRACT`/`ACCOUNT_ALIASES` 확장 + dps는 별도
   endpoint = **방금 승인된 파서 계약의 재개봉**. 별도 미니 게이트(별칭·fixture·quota 산정)로
   Phase 2b 분리 제안.
2. **D&A 주석 원문 경로 — 제외.** 소비처가 EBITDA(op+dep+amort) 파생 = EV/EBITDA 계열인데
   이는 §7.2-5 허용 배수 밖. 허용 배수 확장 결정 전에는 죽은 코드가 된다.
3. **신규 회사 실수집 — 제외** (2단계). 회사당 20콜(2 endpoint×10년) 예산 규칙만 §5-3에서 확정.
4. **DB persist — 제외.** 밴드는 실행 시 재계산(입력이 point-in-time이라 결정론적).
   P3 저장 계약과의 통합은 별도 판단.
5. forward 계열 일체("12M Forward" 등) — 계약대로 금지 유지.

## 3. 변경 파일 범위 (제안)

| 파일 | 상태 | 내용 |
|---|---|---|
| `schemas/point_in_time.py` | 수정 | `AnnualObservation`·`MultipleObservation`·`HistoricalBand` frozen 모델 추가 (models 역참조 금지 유지) |
| `pipeline/timeseries.py` | 신규 (IO) | 스냅샷/DART payload → `extract_reported_values` → 연도별 관측 조립 + yfinance 접수일 raw close. payload 캐시 `.cache/dart_history/`(rcept_no 단위, available_at 보존) |
| `engine/multiple_band.py` | 신규 (순수) | 관측→밴드 통계 순수 함수. IO import 0. docstring에 "reporting reference only — not a valuation input" 계약 명문 + 소비처 grep 테스트로 고정. **위치 대안 §5-1** |
| `output/sheets/relative.py` + `output/console_report.py` | 수정 | 밴드 렌더(현 배수 위치 포함). n_obs<5 시 "이력 부족(N=x)" 표시(P3 선례). 편집 전 `.claude/rules/output.md` 필독·console 동기화 규칙 준수 |
| `cli.py` | 수정 | 최소 통합: `--band` 플래그(KR + 스냅샷/캐시 보유 시만 활성) — 통합 방식 §5-2 |
| `tests/test_multiple_band.py` + `tests/fixtures/` | 신규 | §4 기준 전부 테스트 고정. fixture는 스냅샷 오프라인 추출(파서 계약 fixture 선례) |
| 본 문서 | 신규 | |

무변경 보장: `engine/` 기존 파일 · `schemas/models.py` · `db/` · `profiles/` ·
`pipeline/dart_parser.py`(계약 재개봉 없음 — `STATEMENT_CONTRACT`/`ACCOUNT_ALIASES` diff 0).

## 4. Acceptance criteria (회귀표 초안 — 채택 시 완화 금지, 해시 = sha256)

| # | 기준 |
|---|---|
| 1 | **계약 소비 한정**: 신규 코드의 재무값 접근 = `extract_reported_values`/`select_point_in_time`만. legacy `parse_financial_statements`/`ACCOUNT_MAP`/`CAPEX_MAP` 소비 0 (grep + 테스트 고정) |
| 2 | **original-only·look-ahead 차단 실증**: LG op FY2020 실물 케이스 — 밴드 관측치에 3,194,987(original)만 유입, 재작성 3,905,108 유입 0 · t=2021-03-15(접수 전) 관측 제외. hynix FY2019 net_income CIS 2,016,391 동일 (파서 계약 §4 하이라이트 재사용) |
| 3 | **보간·소급 0**: 결측 연도는 n_obs에서 제외(파일럿 실측 LG 원천 결측 1건이 실제로 빠짐을 fixture로 고정). 현재 snapshot 유입 경로 grep 0 |
| 4 | **라벨 계약**: 산출물(시트·console·모델)에 P/B·P/S 외 배수 라벨 0 · "Forward|Fwd|E" 계열 문자열 0 · 전 라벨 `require_allowed_multiple_label` 경유 |
| 5 | **가격 계약**: yfinance raw close(auto_adjust=False) 사용을 코드+테스트로 고정 · 접수일 비거래일 시 규칙(§5-4 확정치) 적용 · corporate action 미복원 연도 관측 제외+경고 |
| 6 | **파일럿 3사 E2E**: 신규 DART 콜 0(네트워크 mock/스냅샷)으로 3사×10년 밴드 산출, 관측 수가 파일럿 v2 매핑률·결측률과 정합 |
| 7 | **reporting-only**: `run_valuation`/`method_selector`/`valuation_runner` 경로에서 `multiple_band` import 0 (grep 테스트) · `engine/multiple_band.py` IO import 0 (기존 순수성 테스트 편입) |
| 8 | **무회귀**: 전체 pytest(deselect 규칙 유지) · `--band` 미지정 시 기존 Excel/console 산출물 byte 동일 · 파일럿 v2 산출물 3종 sha256 불변 |
| 9 | **파서 계약 불변**: `dart_parser.py`·`STATEMENT_CONTRACT`·`ACCOUNT_ALIASES` diff 0 |
| 10 | **표준**: NUL 스캔 clean · 신규/수정 .py AST+wc-l · 신규 파일 CRLF · git 쓰기 명령 0 |

## 5. Codex 정책 질의 (1번부터 번호 회신)

1. **순수 밴드 모듈 위치**: (a) `engine/multiple_band.py`(순수 함수 규약 부합, 단 "engine 연결
   REJECT"와의 경계는 #7 grep으로 방어) vs (b) `backtest/` 인접 vs (c) 신규 최상위 `analysis/`.
   Claude 권고: **(a)** — 순수성 테스트 인프라 재사용, reporting-only는 소비처 테스트로 강제.
2. **CLI 통합**: `--band` 독립 플래그 vs `--excel` 시 KR 자동 포함. Claude 권고: **독립 플래그**
   (기존 산출물 byte 동일 회귀 #8 유지가 우선).
3. **2단계 quota 규칙**: 신규 회사 = 20콜/사, 실행 전 `targets×20 ≤ remaining` 사전 보고 +
   payload 캐시 필수(재수집 0) — 동의 여부.
4. **접수일 비거래일 가격 규칙**: 직전 거래일 close 사용(t 이전이므로 look-ahead 아님) 제안 —
   동의/수정.
5. **§2.2 제외 4건**(eps/bps/dps/roic/fcf · D&A 주석 · 신규 수집 · DB persist) 및 Phase 2b
   분리 — 동의 여부.
6. **판정**: §3 파일 범위 + §4 회귀표로 본구현 착수 승인 여부.

## 6. 백로그 (불변 + 갱신)

1. ~~본 범위 계약 Codex 회신~~ — **수정 조건부 승인·확정** (§7).
2. DB 마이그레이션 적용 — 사용자 네트워크 몫(불변).
3. 커밋 단위(사용자 결정 대기): ①~③ 기존 + ④ 파서 계약 + (구현 후) ⑤ Phase 2 본구현.
4. Phase 2b 후보: 미커버 필드·D&A 주석 경로(§2.2-1·2) · 신규 회사 수집(§2.2-3) ·
   `TestScenarioDriverRoundTrip` fixtures 분리(§7-1b, deselect 규칙 해제 조건).

---

## 7. Codex 정책 회신(6항목) → Claude 대조·확정 — **수정 조건부 착수 승인**

2026-07-18. Codex 회신: §5 질의 6항목 전부 번호 회신, 항목 누락 0. 대조 결과와 확정 사항:

1. **밴드 모듈 위치 (a) `engine/multiple_band.py` 동의** + 방어선 4개(IO/네트워크 import 0 ·
   valuation/방법론 선택 경로 import 0 · reporting-only 테스트 고정 · 기존 engine 파일 무수정).
   → 전부 §4 회귀표에 이미 반영(#7) + "기존 engine 파일 무수정"을 #7에 명문 추가.
2. **`--band` 독립 플래그 동의** + 동작 고정: `--band`=console · `--band --excel`=Excel 추가 ·
   `--excel`만=기존 동일 · 스냅샷/캐시 부재 시 **자동 네트워크 호출 금지, 경고 후 밴드 생략**.
   → §2.1-4·§3 CLI 행에 계약으로 편입.
3. **quota 규칙 조건부 동의 — 수정 채택**: "20콜/사"는 고정 상수가 아니라 **최소 예상치**로
   격하. 2단계 실수집 시 (i) endpoint별 예상 호출 수 사전 계산(보고서 목록 조회 비용 포함)
   (ii) 캐시 hit/miss별 실제 예상치 보고 (iii) **사용자 명시 승인 전 네트워크 호출 금지**
   (iv) 불변 rcept_no payload 영구 캐시(재수집 0) (v) "잔여 quota"를 신뢰성 있게 조회할 수
   없으면 잔여량 대신 **이번 실행 예상 호출 수**를 보고. → Phase 2b 계약으로 §6-4에 귀속.
4. **비거래일 가격 규칙 동의 + 강화 채택**: t 이전 최근 거래일 raw close · **접수일 이후 가격
   사용 금지** · 탐색 범위 **최대 7 calendar days**(초과 시 관측 제외+구조화 경고) ·
   `auto_adjust=False` · raw close와 주식수의 corporate-action 기준 불일치 시 제외.
   "복원 불확실" 주관 판단 금지 — **기계적 제외 사유를 enum으로 정의**
   (`PriceExclusionReason`: no_price_within_window / split_adjustment_detected /
   shares_basis_missing / shares_basis_mismatch). 전부 §4 #5에 반영.
5. **제외 범위 5건 동의** (eps/bps/dps/roic/fcf · D&A 주석 · 신규 실수집 · DB persist ·
   forward 전체) — Phase 2b 별도 계약·fixture. 변경 없음.
6. **판정: 수정 조건부 착수 승인** — 반영 조건 4건, Claude 대조:
   - (a) **계정 키 = 실제 내부 키** revenue/op/net_income/interest_expense/assets/liabilities/
     equity/capex. Claude 독립 재현: `dart_parser.py` `ACCOUNT_ALIASES`/`STATEMENT_CONTRACT`
     grep — **Codex 지적 사실, §2.1-1의 operating_income/total_assets 표기는 오기**. 정정 채택,
     암묵 변환 금지.
   - (b) **AC #4의 "E" 계열 문자열 grep 0 삭제** (오탐 과다 — 예: "Excel"·"KOSPI200E" 등).
     대체: 생성된 multiple label **전수를 `require_allowed_multiple_label()`로 검증**하는
     테스트. "Forward|Fwd" 리터럴 grep은 유지(오탐 낮음).
   - (c) 가격 제외 사유·비거래일 최대 탐색 범위 명문화 — 위 3·4항으로 반영 완료.
   - (d) **`--band` 미지정 Excel 검증**: openpyxl 산출물은 생성 메타데이터(timestamp 등)로
     byte 재현이 불안정할 수 있음 → **시트명·셀 값·수식 semantic equality**를 기본 검증으로
     하고, 결정론 확인 시에만 sha256 동일성 요구. console 출력은 byte 동일 유지.

### 7.1 확정 acceptance criteria (§4 개정 — 이후 완화 금지)

§4에서 다음만 개정, 나머지 불변:

- **#4 (개정)**: 산출물(시트·console·모델)에 P/B·P/S 외 배수 라벨 0 · "Forward|Fwd" 리터럴
  grep 0 · **생성 라벨 전수가 `require_allowed_multiple_label()` 통과** (테스트 고정).
- **#5 (구체화)**: yfinance raw close(`auto_adjust=False`) · t 이전 최근 거래일, 탐색 최대
  7 calendar days · 접수일 이후 가격 소비 경로 0 · 제외는 `PriceExclusionReason` enum 사유
  필수(주관 판단 금지) · 기준 불일치(shares_basis_mismatch) 제외 — 전부 테스트 고정.
- **#7 (명문 추가)**: 기존 `engine/` 파일 diff 0 (신규 `multiple_band.py`만 허용).
- **#8 (개정)**: `--band` 미지정 시 console byte 동일 + Excel은 **시트명·셀 값·수식 semantic
  equality** (결정론 실측 확인 시 sha256로 승격 가능).
- 계정 키 표기: 본 문서 §2.1-1의 계정명은 (a) 정정에 따라 실제 키로 읽는다.

**본 §7 확정으로 구현 착수.** 구현 산출물·회귀표 실측은 §8에 기록한다.

---

## 8. 구현 완료 — 회귀표 실측 (Codex 교차검증 대기)

2026-07-18 (Claude, 동일 세션). §7 확정 4조건 전부 반영. 테스트 31/31 + 전체 무회귀.

### 8.1 쓰기 전량 (본 세션 코드, sha256 = 최종 상태)

| 파일 | 상태 | 줄수 | sha256 |
|---|---|---|---|
| `schemas/point_in_time.py` | 수정 (157→321) | 321 | `5a8a6060…c36be91e` |
| `engine/multiple_band.py` | 신규 (순수) | 120 | `d5db19ec…ad7fd3fd` |
| `pipeline/timeseries.py` | 신규 (IO) | 357 | `6182127b…77377611` |
| `output/band_report.py` | **신규** (console, §8.2-1) | 59 | `ea481b5a…3e3924be` |
| `output/sheets/band.py` | **신규** (Excel 시트, §8.2-1) | 106 | `a227dfdf…d4165c05` |
| `output/excel_builder.py` | 수정 (+kwarg 2, opt-in 호출) | 96 | `96297b82…de29bdae` |
| `cli.py` | 수정 (--band, §8.2-3) | 373 | `46c3d0c9…afc3200378` 앞 16자 `46c3d0c968b1b8c1` |
| `tests/test_multiple_band.py` | 신규 (31 tests) | 456 | `c6886cdd…c5c40fa771` 앞 16자 `c6886cddb1455765` |

### 8.2 §3 제안 대비 이탈 (전부 범위 축소 방향)

1. **`relative.py`·`console_report.py` 무수정** — 밴드 렌더를 신규 모듈
   (`output/band_report.py`·`output/sheets/band.py`)로 분리. 기존 출력 파일 diff 0이
   되어 §7.1 #8(기본 출력 불변)이 구조적으로 보장됨. 대신 `excel_builder.py`에
   optional kwarg 2개(`band_reports`/`band_current`, 기본 None) + opt-in 시트 호출 추가.
2. **신규 fixture 파일 0** — 스냅샷(`raw_payloads.json`) read-only 재사용 + synthetic
   payload를 테스트 인라인으로 구성. 파일럿 실물 값(LG FY2020 revenue 원본/재작성)을
   테스트 상수로 고정.
3. **`--band`는 1단계 `--profile` 경로 전용** — `--company` 경로는 안내 출력 후 생략
   (§7-2 "캐시 부재 시 자동 네트워크 금지"와 정합; auto_fetch 경로는 밴드 컨텍스트 없음).
4. `cli.py`는 **LF 유지** — 세션 시작 시점부터 LF인 예외 파일(`dart_parser.py` 선례).
   Edit가 CRLF 파일(`excel_builder.py`·`point_in_time.py`)의 개행을 보존한 것과 동일
   메커니즘으로 확인. 신규 파일은 전부 CRLF.

### 8.3 설계 결정 4건 (Codex 검토 대상)

1. **주식수 = 발행보통주 − 자기보통주 (ordinary만)**: 관측 가격이 보통주 종가이므로
   분자·분모 기준 일치. 우선주 처리(삼성전자 005935 등)는 Phase 2b.
2. **provider `splits=None` → `SHARES_BASIS_MISMATCH`**: 가격 원천이 corporate-action
   기준을 전혀 수립할 수 없으면 해당 구간 전 연도 기계적 제외 (§7-4 주관 판단 금지의
   fail-closed 해석).
3. **yfinance 빈 splits Series = "없음"으로 간주** (unknown과 구분 불가한 원천 한계).
   split 존재 시 `(price_date, t]` 구간 검사로 `SPLIT_ADJUSTMENT_DETECTED`.
4. **가격 provider 1회 호출** (전 연도 span) 후 로컬 window 해석 — 연도별 호출 대비
   결정론·속도 우위, look-ahead는 `_resolve_price`의 `d <= t` 게이트로 차단.

### 8.4 회귀표 실측 (§4 + §7.1 개정판, 완화 없음)

| # | 기준 | 실측 | 판정 |
|---|---|---|---|
| 1 | 계약 소비 한정 | 신규 코드 AST 스캔: `parse_financial_statements`/`ACCOUNT_MAP`/`CAPEX_MAP` 식별자 0 (테스트 고정). 재무값 접근은 `extract_reported_values`+`select_point_in_time`만 | PASS |
| 2 | original-only·look-ahead 차단 실증 | LG P/S FY2020 분모 = **63,262,046**(original, rcept 20210316000661, t=2021-03-16) · 재작성 58,057,908은 pool에 존재하되 관측 유입 0 (테스트 고정) | PASS |
| 3 | 보간·소급 0 | LG FY2016 원천 결측(주식수 0) → `shares_basis_missing` 제외, n_obs 9 (파일럿 v2 "결측 1 잔존"과 정합, 테스트 고정). 보간 경로 부재 + 모델 validator가 결측 관측 생성 자체를 차단 | PASS |
| 4 | 라벨 계약 (§7.1 개정) | 생성 라벨 전수 `require_allowed_multiple_label()` 통과 테스트 + console 출력 `Forward\|Fwd` 부재 테스트 + P/E 등 범위 외 라벨 fail-closed | PASS |
| 5 | 가격 계약 (§7.1 구체화) | 7 calendar days window 경계 테스트 · 접수일 이후 가격 소비 0(전용 테스트) · 제외 4사유 enum 전부 개별 테스트(기계적 조건) · `auto_adjust=False`는 기본 provider 코드 고정. **실 yfinance 경로는 §9-4 호스트 확인 요청** | PASS* |
| 6 | 파일럿 3사 E2E (신규 DART 콜 0) | 삼성 10/10 · hynix 10/10 · LG 9/10(FY2016 제외) — P/B·P/S 동일, n_obs+제외=10 전사 성립. 전 과정 스냅샷+fake provider(네트워크 0) | PASS |
| 7 | reporting-only + 순수성 | `valuation_runner`/`orchestrator`/기존 `engine/*`에 `multiple_band` 참조 0 (소스 스캔 테스트) · `engine/multiple_band.py` IO import 0 · 기존 engine 파일 본 세션 쓰기 0 | PASS |
| 8 | 무회귀 (§7.1 개정) | 전체 pytest **1067 passed / 5 deselected / 1 failed** — 실패는 기지의 `test_fred_series_missing_values` 샌드박스 unlink `PermissionError`(§7-1a에서 호스트 통과 확정된 환경 결함, 변경 코드와 무관). Excel: 동일 입력 2회 export **byte-identical(sha256 동일 — 샌드박스 결정론 실측)** + semantic equality(전 시트·셀·서식) + 밴드 전달 시 기존 시트 전부 동일·`Historical Band` 1장만 추가. console: `console_report.py` 무수정 + `--band` 미지정 시 신규 코드 미실행 | PASS* |
| 9 | 파서 계약 불변 | `dart_parser.py`·`STATEMENT_CONTRACT`·`ACCOUNT_ALIASES` 본 세션 쓰기 0 · 파서 계약 테스트 20/20 유지 | PASS |
| 10 | 표준 | 저장소 전체 NUL 0 · 쓰기 8파일 AST OK + 줄수 확인 · 신규 파일 CRLF(예외: cli.py 기존 LF 유지) · git 쓰기 명령 0 (log/status/diff만) | PASS |

## 9. Codex 교차검증 요청 (1번부터 번호 회신, 독립 재현)

1. **호스트 pytest 전체** (deselect 규칙 유지): **1068 passed** 기대 (1067 + fred 1).
2. **파일럿 v2 산출물 sha256 4종 대조**: report `324f8afe…97b783a` · cls.md
   `06971373…fef997e` · cls.csv `db15163c…16d8105` · snapshot `c1ab94c7…80fb099`
   (본 세션 재실측 — 전부 불변, snapshot은 읽기만).
3. **밴드 테스트 독립 재현**: `pytest tests/test_multiple_band.py -q` 31/31 + §8.4-2·3의
   실물 값(LG 63,262,046 원본 소비·재작성 미유입·FY2016 제외) 재확인.
4. **실 yfinance 경로 1회 실측** (호스트, 네트워크): 파일럿 3사 중 프로필 보유 회사로
   `python cli.py --profile <파일럿 프로필> --band` — raw close(`auto_adjust=False`) 소비,
   접수일 비거래일 시 직전 거래일 선택, 범위 외 회사 경고 후 생략 경로 확인.
5. **중점 감사**: §8.3 설계 결정 4건(ordinary-only 주식수 · splits=None 해석 ·
   yfinance 빈 splits 간주 · provider 1회 호출)의 타당성 + 제외 판정 순서
   (rcept 부재→분모 결측→분모 비양수→주식수→splits 기준→가격 window→split 검출).
6. **판정**: §7.1 확정 acceptance criteria 충족 여부 → Phase 2 1단계 종결 +
   커밋 단위 ⑤ 승인.

---

## 10. Codex 구현 교차검증 회신 → 보류 조건 2건 수정 — 재검증 요청

2026-07-18. Codex 회신: §9-1~3 PASS(호스트 pytest **1073/0/0** — 샌드박스 기대 1068과의
차이 5 = 과거 deselect 대상 `TestScenarioDriverRoundTrip` 5건이 호스트에서 실행·통과,
§7-1b 기록과 정합. fred 포함 전부 통과) · sha256 4종 일치 · 51/51 재현. §9-4 미검증
(호스트 SSL) · §9-5 수정 필요 2건 → **종결·커밋 승인 보류**. 양건 모두 Claude 독립
재현으로 사실 확인 후 수정 완료:

### 10.1 지적 인정 + 수정 내역

1. **provider 1회 호출 주장 오류 인정** (§8.3-4 기재가 구현과 불일치 — label별
   `build_observations` 내부 호출로 회사당 2회였음). 수정: `fetch_price_data()` 신설,
   `build_band_reports()`가 회사당 **정확히 1회** 호출 후 결과 튜플을 P/B·P/S에 공유.
   `build_observations` 시그니처가 provider 대신 `price_data`를 받도록 변경.
   counting-provider 테스트로 호출 수 1 고정.
2. **`tk.splits` 빈 Series 간주 결함 인정** (원천 실패와 known-empty 구분 불가 —
   Codex가 실제 SSL 실패에서 관측한 그 경로). 수정: 권고안 그대로 —
   `history(auto_adjust=False, actions=True)` **단일 응답**에서 close와 `Stock Splits`
   열을 동시 추출(`_parse_history_frame`). 계약: 빈/실패 응답 → `({}, None)`(원천 실패,
   전 연도 `SHARES_BASIS_MISMATCH` fail-closed) · 열 부재 → `(closes, None)` ·
   열 존재+전부 0 → known-empty `[]`. 별도 splits 요청 소멸 → 1번 문제와 동시 해소.
   `({},None)` vs `({},[])` 사유 분리를 전용 테스트로 고정.
3. **§9-4 SSL 근본 원인 대응**: Codex의 `curl error 77`(certifi CAfile)은 저장소
   `_ssl_fix.py`가 정확히 고치는 증상(한글 사용자 경로의 CA 번들, "Import this module
   early in any entry point"). cli 경로만 적용되고 **provider 직접 호출 경로에는 미적용**
   이었음 → `yfinance_price_provider`가 yfinance import 직전 `import _ssl_fix`를 수행
   (ImportError 무시). Codex의 직접 함수 검증 방식에서도 이제 적용됨.

### 10.2 재검증 실측 (수정 후)

| 항목 | 실측 | 판정 |
|---|---|---|
| 밴드 테스트 | **34/34** (기존 31 + 신규 3: provider 1회 · 원천 실패/known-empty 분리 · `_parse_history_frame` 계약) + 파서 계약 20/20 | PASS |
| 전체 pytest (샌드박스, deselect 유지) | **1070 passed / 5 deselected / 1 failed** — 실패는 동일 fred unlink 환경 결함(호스트 통과 확정, §9-1) | PASS* |
| E2E parity | 삼성 10/10 · hynix 10/10 · LG 9/10 불변 (counting provider로 fetch 1회 확인) | PASS |
| 무결성 | 수정 2파일 AST OK · CRLF · NUL 0 · git 쓰기 0. `pipeline/timeseries.py` 404줄 sha256 `aae18307…d37d06a636` · `tests/test_multiple_band.py` 510줄 sha256 `80d0a77b…12e9b4854c` (§8.1 두 행은 본 값으로 대체) | PASS |

### 10.3 Codex 재검증 요청 (1번부터 번호 회신)

1. 호스트 pytest 전체: **1076 passed** 기대 (1073 + 신규 3).
2. `pytest tests/test_multiple_band.py -q` 34/34 + counting-provider 테스트로
   회사당 fetch 1회 독립 확인.
3. **§9-4 재실측** (핵심): `_ssl_fix` 적용이 provider에 내장됐으므로 동일한 직접 함수
   검증 재실행 — `from pipeline.timeseries import build_band_reports` 후 삼성전자
   실 yfinance 경로. 기대: SSL 해소 시 n_obs>0 + raw close 소비; SSL이 여전히 실패하면
   이제 `NO_PRICE_WITHIN_WINDOW`가 아니라 **`SHARES_BASIS_MISMATCH`(원천 실패)** 로
   찍혀야 함(§10.1-2의 구분 계약 검증 — 실패조차 계약대로 분류되는지 확인).
   DB 쓰기 없는 직접 호출 방식 유지 동의.
4. 판정: 보류 2조건 해소 여부 → Phase 2 1단계 종결 + 커밋 단위 ⑤ 승인.

---

## 11. Codex 3라운드 회신 — split 소급 조정 신규 결함 → 수정 — 재검증 요청

2026-07-18. Codex 회신: §10.3-1 PASS(호스트 **1076/0**, 기대 정확 일치) · -2 PASS(34/34 +
fetch 1회 고정 확인) · -3 **SSL 해소 PASS / 가격 기준 계약 FAIL** · 판정 보류.

### 11.1 실측 결함 (Codex 발견 — 인정)

삼성전자 실 yfinance: FY2016-17에서 Yahoo Close 41,200원 × DART 당시 주식수
122,697,651주 → P/B 0.026x (**~50배 왜곡**). 원인: **Yahoo 과거 Close는
`auto_adjust=False`여도 split(2018-05-04·05-16, 50:1) 기준으로 소급 조정**되는 반면
DART 주식수는 분할 전 기준. 기존 검사 `price_date < s <= t`는 접수일 이후 발생해 과거
가격에 소급 반영된 split을 탐지하지 못했다. §8.3-3의 "빈 splits=없음 간주"는 유지되나
split이 **실재할 때의 기준 판정이 불완전**했던 것.

### 11.2 수정 (fail-closed, 최소)

1. **판정 기준을 price_date가 아닌 회계연도말(FYE)로 교체**: `s > date(fy,12,31)`인
   split이 하나라도 알려져 있으면 해당 FY를 `SPLIT_ADJUSTMENT_DETECTED`로 제외.
   근거: 가격은 항상 최신 분할 기준(소급 조정), 주식수는 FYE 기준 → **FYE 이후 split
   존재 = 기준 불일치 확정**. split ≤ FYE면 주식수도 분할 후 기준이라 정합(삼성 FY2018+
   유지 — Codex 실측과 일치하는 복구 경계). FYE=12-31은 1단계 기계적 가정(파일럿 3사
   전부 12월 결산, docstring 명문).
2. **provider span을 오늘까지 확장** (`fetch_price_data`): 마지막 접수일 이후의 split도
   전체 과거 가격을 소급 조정하므로 action 기준은 조회 시점까지 알아야 함. t 이후 close는
   `_resolve_price`의 `d <= t` 게이트로 여전히 미소비.
3. 제외 판정 순서 갱신(§10.3-3의 기존 순서에서 split 검사가 가격 해석 **앞**으로 이동):
   rcept 부재 → 분모 결측 → 분모 비양수 → 주식수 → action 기준 불명 → **FYE 이후
   split** → 가격 window.

### 11.3 재검증 실측

| 항목 | 실측 | 판정 |
|---|---|---|
| 신규 회귀 테스트 4건 | 삼성 실 Yahoo 형태 재현(split 2018-05 주입 → FY2016-17 `SPLIT_ADJUSTMENT_DETECTED` 제외, FY2018-25 8건 유지) · split ≤ FYE면 10/10 유지 · 마지막 접수일 이후 split → 전 연도 제외 · fetch span ≥ 오늘 | PASS |
| 밴드 테스트 | **38/38** (34 + 신규 4) + 파서 계약 20/20 | PASS |
| 전체 pytest (샌드박스) | **1082 passed / 5 deselected / 2 failed** — 실패 2건 전부 동일 fred `.cache` unlink `PermissionError`(기지 환경 결함, 동일 파일·동일 원인; 호스트 1076 전부 통과 확인됨. 이번엔 `test_fred_series_success`까지 동일 사유로 걸림). test_output 일시 실패 2건은 샌드박스 `selenium` 미설치가 원인 — 설치 후 통과, 변경 코드와 무관 | PASS* |
| E2E parity (fake provider, split 없음) | 삼성 10/10 · hynix 10/10 · LG 9/10 불변 | PASS |
| 무결성 | `pipeline/timeseries.py` 425줄 sha256 `54bbf5be…e04388db` · `tests/test_multiple_band.py` 582줄 sha256 `6f217d83…bf5e0585` (§10.2 두 행 대체) · AST OK · CRLF · repo NUL 0 · git 쓰기 0 | PASS |

한계 기록(정직): 실 데이터 상 삼성 FY2016-17 관측은 **제외**되어 삼성 밴드는 n=8이 된다.
분할 전 진짜 raw close 복원(×50 역산)은 "corporate action 복원 불확실 시 제외" 계약상
1단계에서 하지 않음 — 복원 시도는 Phase 2b 후보(액션 비율 데이터 검증 계약 필요).

### 11.4 Codex 재검증 요청 (1번부터 번호 회신)

1. 호스트 pytest 전체: **1080 passed** 기대 (1076 + 신규 4).
2. `pytest tests/test_multiple_band.py -q` 38/38 독립 재현.
3. **실 yfinance 재실측** (§10.3-3과 동일 방식): 삼성전자 →
   기대: FY2016-17 `split_adjustment_detected` 제외 · FY2018+ 관측 유지 ·
   유지 연도의 P/B가 상식 범위(대략 1-2x대) · 0.026x 같은 왜곡 관측 0.
   hynix/LG(분할 무)도 1회씩: 전 연도 관측 + raw close 소비 확인.
4. 판정: §11.1 결함 해소 → Phase 2 1단계 종결 + 커밋 단위 ⑤ 승인.

---

## 12. Codex 최종 승인 — **Phase 2 1단계 종결** + 커밋 플랜 (호스트 실행)

2026-07-18. Codex 4라운드 회신: 호스트 **1089 passed** · 밴드 38/38 · 삼성 split 왜곡
제거 실측 확인 · hynix/LG 실 yfinance 정상 · **Phase 2 1단계 종결 + 커밋 단위 ⑤ 승인**.

산술 대조 (Claude): 1089 = 샌드박스 1082 passed + fred 2(호스트 통과) + deselect 5
(호스트 실행·통과) — **총 수집 수 정확 일치**, §11.4-1 기대치 1080은 fred/deselect
환경 차 미반영 오기였음 (구성 drift 아님).

### 12.1 ⚠ 샌드박스 git 잔류물 — 호스트에서 즉시 제거 필요

샌드박스 `git status`가 index 갱신 중 `.git/index.lock`을 생성했으나 마운트 unlink
제한으로 **삭제하지 못함** (0 byte, 2026-07-18 생성). 제거 전까지 모든 git 쓰기가
차단된다. 호스트에서: `del F:\dev\Portfolio\business-valuation-tool\.git\index.lock`
(파일이 0 byte이고 다른 git 프로세스가 없음을 확인 후). **교훈: 이 마운트에서는
샌드박스 git 명령이 read-only라도 index.lock 잔류 위험 — 커밋·staging은 호스트 전용.**

### 12.2 커밋 단위 ⑤ manifest (Phase 2 본구현 일체)

신규 6파일 (전량 ⑤, 선별 불요):

| 파일 | 최종 sha256 (앞 16) |
|---|---|
| `engine/multiple_band.py` | `d5db19eca3f1fe42` |
| `pipeline/timeseries.py` | `54bbf5beff1fd7da` |
| `output/band_report.py` | `ea481b5a5f796e18` |
| `output/sheets/band.py` | `a227dfdf55934738` |
| `tests/test_multiple_band.py` | `6f217d83ac789375` |
| `HANDOFF_CODEX_phase2_impl_scope_2026-07-18.md` | (본 문서, 커밋 시점 상태) |

공유 파일 3개 (선별 주의):

1. `schemas/point_in_time.py` — **④(파서 계약)와 공유.** ④ 커밋 전이면 파일 전체가
   untracked이므로 ④를 먼저 커밋(1단계 157줄 상태 재현 불요 시 ④+⑤ 통합도 가능,
   아래 권장 순서 참조). ⑤ 증분 = L159 이후 "Phase 2: multi-year observations +
   historical band" 섹션 + `from enum import Enum` import 1줄.
2. `output/excel_builder.py` — ⑤ hunk = export 시그니처 5줄(`band_reports`/
   `band_current` kwarg) + docstring 추가 + `if band_reports:` 3줄 블록. **그 외
   hunk(history sheet·guides·draft warning 등)는 선행 미커밋 트랙 소속** — ⑤에 혼입
   금지.
3. `cli.py` — ⑤ hunk = `--band` argparse 5줄 + company-mode 안내 2줄 + profile-mode
   밴드 블록(약 20줄, `# Historical band` 주석부터 `print_band_reports` 호출까지 +
   export 호출부 kwarg 2줄). 그 외 diff는 선행 트랙.

### 12.3 권장 커밋 순서 (의존 사슬 존중)

⑤는 ③·④ 산출물에 실행·테스트가 의존한다: `tests/test_multiple_band.py` →
`research/pilot_v2/raw_payloads.json`(③) · `extract_reported_values`(④). 순서:

1. ①② (dart_client+tests / api_guard+analyst) — 기존 결정대로.
2. ③ 파일럿 v2 일체 (`scripts/pilot_multiyear_quality_v2.py` ·
   `research/pilot_v2/*` · `pilot_multiyear_quality_report_v2.md` · C 게이트 핸드오프).
3. ④ 파서 계약 (`pipeline/dart_parser.py` 해당 hunk · `schemas/point_in_time.py` ·
   `tests/test_dart_parser_contract.py` · `tests/fixtures/dart_pilot_v2_subset.json` ·
   파서 계약 핸드오프).
4. ⑤ 본 단위 (§12.2). ①~④가 먼저 커밋되면 `cli.py`·`excel_builder.py`의 잔여 diff
   중 ⑤ 몫 식별이 크게 단순해짐 — 선행 트랙 hunk가 이미 소진되기 때문. 각 커밋 후
   `pytest` 1회로 커밋 상태 무결성 확인 권장.

제안 커밋 메시지 (⑤): `feat(band): Phase 2 P1/P2 — 10년 point-in-time 시계열 + LTM
P/B·P/S historical band (reporting-only, Codex 4라운드 GO)`

### 12.4 백로그 최종 상태

1. ~~Phase 2 1단계~~ — **종결·승인** (본 §12).
2. 커밋 실행 — 호스트 몫 (§12.1 lock 제거 → §12.3 순서).
3. DB 마이그레이션 적용 — 사용자 네트워크 몫(불변).
4. Phase 2b 후보(§6-4 + §11.3 한계): 미커버 필드(eps/bps/dps/roic/fcf) · D&A 주석 경로 ·
   신규 회사 수집(§10 quota 계약) · 분할 전 raw close 복원(액션 비율 검증 계약) ·
   非12월 결산 FYE 처리 · `TestScenarioDriverRoundTrip` fixtures 분리.

### 12.5 커밋 확정 — 세션 종결 (2026-07-18)

호스트에서 §12.3 순서대로 커밋 실행·최종 감사 완료 (실행 주체: 사용자/Codex, 호스트):

| 단위 | 커밋 | 내용 |
|---|---|---|
| ① | `fbec0b1` | DART 주식수 파싱 수정 |
| ② | `4ebe508` | LLM 예약 예산 주석 정합화 |
| ③ | `6c246cc` | 파일럿 v2 연구 산출물 |
| ④ | `2e51d3b` | point-in-time 파서 계약 |
| ⑤ | `2693260` | historical P/B·P/S 밴드 본구현 |

검증: 밴드 38/38 · 전체 **1093 passed** · staged diff clean · `.git/index.lock` 제거
확인 · staging 보조 파일 제거 · Phase 2 파일 미커밋 변경 0 · 타 트랙 작업 트리 변경
보존. **차기 세션 시작 검증 기준 HEAD = 2693260.** 본 §12.5 추가로 이 문서 자체만
커밋 이후 재수정 상태(문서 1파일, 코드 무변경)임을 명시한다.
