# C 연구 핸드오프 — P1/P2 승격 게이트 1단계 실행 결과 (파일럿 v2 + 충돌 분류)

2026-07-18 (Claude) | 상태: **1차 작업 완료 — 회귀표 9/9 PASS · Codex 교차검증 대기**
계약: `HANDOFF_CODEX_next_scope_decision_2026-07-17.md` §6.3 (완화 없음, 그대로 실행)
선행: 동 문서 §7(quota 중단 기록) · `HANDOFF_CODEX_dart_remarks_fix_2026-07-17.md` §9 · `pilot_multiyear_quality_report.md`(v1)

> 루프 위치: **연구 산출물 제출 단계.** Codex는 §5 교차검증 요청에 1번부터 번호를 붙여
> 독립 재현으로 회신하라. 주장(콜 수·분류 합계·재현성)은 값·grep·재실행으로 검증할 것.

## 1. 실행 기록

1. 세션 시작 검증: `git log -15` + `pipeline/dart_client.py`(행 필터·fail-closed parser 반영 확인)
   + `pipeline/api_guard.py` L632 주석(Reserved budget 문구 반영 확인) — 선행 2건 모두 **미커밋 상태로 존재**.
2. DART quota 사전검사: `.cache/api_usage.json` 날짜 리셋 후 remaining **100 ≥ 60** 확인.
3. 실행 환경 분리: Cowork 샌드박스 프록시가 opendart.fss.or.kr을 차단(CONNECT 403)
   → 수집(`--collect`)/분석(`--analyze`) 분리 설계, **수집은 사용자가 호스트에서 1회 실행**,
   분석·분류·리포트는 스냅샷 기반 오프라인(네트워크 0)으로 수행.
4. 수집: `python scripts/pilot_multiyear_quality_v2.py --collect` (호스트, 2026-07-18)
   → `calls_made=60 dart_calls_delta=60 remaining=40`, 실패 0, 재시도 0
   (`guard.configure("dart", max_retries=0)`로 in-process 자동 재시도 봉인 — 60콜 = 실 HTTP 시도 60).
5. 분석: `python scripts/pilot_multiyear_quality_v2.py --analyze` — 스냅샷만 사용, API 호출 0.

## 2. 산출물

| 파일 | 내용 |
|---|---|
| `scripts/pilot_multiyear_quality_v2.py` | 수집/분석 분리 파일럿 v2 (650줄 — newline 수정 후, CRLF, 관찰 전용) |
| `research/pilot_v2/raw_payloads.json` | 원시 payload 스냅샷 (60콜 전체 + call log + quota 전/후) |
| `research/pilot_v2/conflict_classification.md` / `.csv` | **산출물 1** — 충돌 17건 계정별 분류표 (9필드 계약 포맷) |
| `pilot_multiyear_quality_report_v2.md` | **산출물 2** — 파일럿 v2 리포트 (hynix 정규화 재측정 포함) |

## 3. 핵심 결과

1. **충돌 세트 v1 완전 재현**: 17/214 (7.9%) = SK hynix 8/72 + LG 9/70 + 삼성 0/72 — 계정·연도 단위 동일.
2. **분류 합계 = 충돌 수**: restatement **17** · mapping_error 0 · unit_error 0 · unresolved 0 (17=17 검증 OK).
   - SK hynix FY2019 5계정 + FY2021 2계정: 익년 보고서가 동일 계정의 comparative를 일괄 수정 (±0.02~2.77%).
     net_income은 CIS(2,016,391→2,009,078)·SCE(2,013,288→2,005,975) 동시 재작성 — 제표 짝맞춤 증거.
   - LG FY2020/2021/2023 revenue·op·interest_expense: 동일 접수번호에서 동시 재작성.
     FY2020 폭(revenue −8.23%, op +22.23%)은 2021년 MC(모바일) 사업 종료에 따른
     중단영업 재분류 패턴과 정합. op 계정명 별칭 변경(`영업이익`→`영업이익(손실)`) 동반 — 증거란 기록.
   - 분류 규칙(스크립트 docstring에 명문): 제표(sj_div) 짝맞춤 기반. 동일 제표 짝의 값이 다르면
     restatement, 교차 제표 소싱/순서 의존 아티팩트만 mapping_error, ~1000x는 unit_error, 그 외 unresolved.
     **규칙 개정 이력**: 초안은 hynix net_income(다중 후보)·LG op(별칭 변경) 2건을 mapping_error로
     과잉 판정 → 제표 짝맞춤으로 정밀화하여 restatement 확정. Codex는 이 2건을 중점 재현하라.
3. **SK hynix 주식수 정규화 재측정: 0% → 100%** (10/10년). 비고행 수정의 실 API 실효성 검증 완료.
   LG 80%→90%(API 오류 1→0, 원천 결측 1 잔존), 삼성 100% 유지.
4. **백로그 3번(실 API 보완 1콜) 동시 충족**: 스냅샷 FY2025 hynix = 발행 728,002,365 /
   자기 26,310,845 — §9-3 기대값과 정확히 일치. 별도 콜 불필요 (60콜에 포함, 추가 카운트 0).
5. **파서 위험 신호 2건** (게이트 발견사항, 코드 변경 없음 — Phase 2 데이터 계약에 반영할 것):
   - `ACCOUNT_MAP` 주 루프가 sj_div 미필터(`dart_parser.py` L82-89) — SCE의 `당기순이익` 행
     (비지배지분 단독 행 3,103 포함)이 매핑 후보로 유입, 현재는 행 순서(CIS 선행)가 우연히 보호.
   - 계정명 별칭의 연도 간 변동(`영업이익`↔`영업이익(손실)`) — 별칭 커버리지가 시계열 일관성의 전제.

## 4. 회귀표 (§6.3-4 — 완화 없음)

| # | 기준 | 실측 | 판정 |
|---|---|---|---|
| 1 | 파일럿 v2 동일 입력 재현성 | `--analyze` 2회 재실행, 산출물 3종 `cmp` byte-identical | PASS |
| 2 | DART 실사용 ≤ 60 | calls_made=60, `.cache/api_usage.json` dart 0→60, remaining 40 | PASS |
| 3 | 추가 endpoint 0 | call log 60건 = fnlttSinglAcntAll 30 + stockTotqySttus 30, 실패 0, 기타 0 | PASS |
| 4 | hynix 주식수 정규화 재측정 | **100.0%** (v1 0.0%) | PASS |
| 5 | 17건 분류표 + 합계=충돌 수 | 17행 9필드, restatement 17/기타 0, 합계 17=17 | PASS |
| 6 | 프로필/엔진/DB 변경 0 | 본 세션 쓰기 = §2 산출물 4종 + 본 문서 + `.cache` 런타임뿐 | PASS* |
| 7 | 소급 사용 0 | 분석은 각 연도 보고서 자체 payload(rcept_no)만 사용, 현재 snapshot 미사용 | PASS |
| 8 | NUL/AST/CRLF | 저장소 전체 NUL clean(cross-review §1 스크립트) · 신규 .py AST OK(642줄) · 신규 파일 CRLF | PASS |
| 9 | 커밋 아님 | git 쓰기 명령 0 (읽기 전용 log/status만) | PASS |

*6 주석: `ai/llm_client.py`·`pipeline/profile_generator.py`의 mtime이 2026-07-18 07:53로 갱신됨
(본 세션·collect 스크립트 모두 미접촉 — 동시 실행된 호스트 프로세스로 추정). 무결성 점검
(AST·py_compile·NUL 0·CRLF) 전부 정상. 내용 손상 없음, 원인만 사용자 확인 요망.

## 5. Codex 교차검증 요청 (1번부터 번호 회신)

1. 콜 수 독립 재현: `research/pilot_v2/raw_payloads.json` meta의 call_log 60건 구성
   (endpoint별 30/30, 실패 0)과 `.cache/api_usage.json` dart.calls=60 대조.
2. 분류 독립 재현: `--analyze` 재실행 → 산출물 byte-identical 여부 + 분류 합계 17=17.
3. 중점 감사 2건: hynix net_income FY2019(제표 짝맞춤 CIS/SCE 동시 재작성 증거),
   LG op FY2020(별칭 변경 + IS 짝 diff) — restatement 판정의 타당성.
4. 파서 위험 신호 2건(§3-5)의 사실 확인 및 Phase 2 데이터 계약 반영 필요성 평가.
5. **게이트 판정**: 충돌 17건 전원 restatement(파서/단위 결함 0)·주식수 정규화 회복을 근거로
   P1/P2 Phase 2 본구현 승격 여부 — point-in-time 원칙(§6.3-3) 하에서 판단 회신.

## 6. 후속 백로그 (불변 + 갱신)

1. C 게이트 판정 — 본 문서 §5-5, Codex 교차검증 후 결정.
2. DB 마이그레이션 적용 — 사용자 네트워크 몫(불변).
3. ~~실 API 보완 1콜(hynix 주식수 대조)~~ — **본 수집으로 충족·종결** (§3-4).
4. 커밋 단위(사용자 결정 대기): ① dart_client+tests ② api_guard+analyst ③ 파일럿 v2 산출물 일체.

---

## 7. Codex 교차검증 회신 → Claude 대조·정정 — 게이트 **조건부 GO** 확정

2026-07-18. Codex 회신 5항목: ①콜 수 PASS ②분류 재현 PASS(줄바꿈 불일치 1건 지적)
③중점 감사 2건 PASS(restatement 타당) ④파서 위험 신호 사실 — Phase 2 필수 계약 승격
⑤게이트 **조건부 GO** (수집 가능성 승인, 현 parser 그대로 소비하는 본구현은 불승인).

### 7.1 지적 2번 정정 (Claude 인정 + 근본 원인 특정 + 수정)

1. **결함 인정**: "최초부터 CRLF·byte-identical" 주장은 샌드박스(Linux) 한정 실측이었다.
   실제 바이트 대조 결과 호스트(Windows) `--analyze` 산출물은 **전 행 `\r\r\n`(CR+CRLF)** —
   `Path.write_text`의 기본 `newline=None`이 Windows에서 `\n`→`os.linesep` 번역을 적용해
   `\r\n`이 `\r\r\n`으로 변형된 것이 근본 원인(Codex가 관측한 최초 해시 불일치의 실체).
   정규화(`\r\r\n`→`\r\n`) 후 내용은 완전 동일 — 데이터 차이 0.
2. **수정**: 스크립트의 모든 `write_text`에 `newline=""` 명시(개행 번역 억제) — 산출물 4종
   (report/md/csv/snapshot)이 플랫폼 무관 동일 바이트(CRLF)로 고정됨. 수정 후 샌드박스
   3회 연속 실행 해시 동일 실측:
   `33b7fcae…(report) · 96b0183a…(cls.md) · 82d54722…(cls.csv)`.
3. **Codex 재확인 요청**: 호스트에서 `--analyze` 1회 재실행 후 위 3개 해시와 일치 확인
   (이제 플랫폼 교차 byte-identical이어야 함). 회귀표 #1은 이 확인으로 최종 종결.

### 7.2 게이트 판정 기록 (조건부 GO — 본구현 착수 조건, 완화 금지)

Phase 2 본구현의 **첫 번째 필수 작업 = parser 데이터 계약 보강**. Codex 조건 그대로:

1. 계정별 허용 statement 고정: revenue/op/net_income/interest → IS·CIS ·
   assets/liabilities/equity → BS · capex → CF.
2. 동일 statement 내 중복 후보의 선택 우선순위 명문화 + ambiguity **fail-closed**.
3. 계정 별칭 정식 registry 관리 + 연도 교차 fixture 추가.
4. 최초 공시값과 후속 재작성값 **별도 보존** (point-in-time 계산은 평가 당시 이용
   가능했던 **최초 공시값** 사용).
5. 현재 snapshot 과거 소급 금지 · available_at=DART 접수일 버전 보존 · 결측 주식수
   보간 금지(관측 제외) · 가격=접수일 raw close + 당시 유통주식수 · 1차 범위 LTM
   P/B·P/S만 · "12M Forward" 표기 금지.

### 7.3 Codex 호스트 재검증 회신 → 해시 "불일치"의 실체 규명 — 회귀표 #1 **최종 종결**

2026-07-18 2라운드. Codex 회신: newline 수정 정상·연속 2회 byte-identical·`\r\r\n` 0·
DART 60 유지·분류 불변, 단 문서 기대 해시(`33b7fcae…` 등) 미재현 → "다른 revision 해시" 추정
+ 회귀표 #1 "플랫폼 교차 미확정" 정정 제안.

**Claude 대조 결과 — revision 차이 아님, 해시 알고리즘 상이가 원인 (표기 누락은 Claude 결함):**

1. §7.1의 해시 3종은 **MD5**였으나 알고리즘을 명기하지 않았고, Codex는 **SHA-256**으로
   대조했다. 32자리 vs 64자리 — 동일 파일이라도 일치할 수 없는 비교였다.
2. 현재 작업트리 파일(= Codex가 호스트에서 재생성한 산출물)에서 두 해시를 동시 산출한 결과:

   | 파일 | MD5 (§7.1 문서값) | SHA-256 (Codex 보고값) |
   |---|---|---|
   | report_v2.md | `33b7fcae8d90cd3248004301550bf202` 일치 | `324f8afe…97b783a` 일치 |
   | conflict_classification.md | `96b0183a6ee0ed1a6dfd30dafaedbf68` 일치 | `06971373…fef997e` 일치 |
   | conflict_classification.csv | `82d54722db462c63f4f82b8a8c84cb3a` 일치 | `db15163c…16d8105` 일치 |

   **동일 바이트가 양측 해시 세트를 모두 산출** — 호스트(Windows) 재생성본 = 샌드박스(Linux)
   생성본, byte-for-byte 동일.
3. 따라서 Codex의 "동일 revision 재대조 전까지 미확정" 제안은 본 대조로 이미 충족·해소됐다.
   **회귀표 #1 최종 판정: 플랫폼 교차(=이기종 OS 각각 생성) byte-identical 확정 PASS.**
   향후 핸드오프의 해시 표기는 알고리즘 명기(sha256 권장)를 규칙으로 한다.
4. 부수 정정: §2의 스크립트 줄 수 642 → **650**(newline 수정 반영 후) — §2 표 갱신 완료.

### 세션 종결 상태 (2026-07-18)

1. C 연구 1단계 — **완료·조건부 GO** (본 문서). 산출물 §2 + newline 수정 반영. 미커밋.
2. Phase 2 착수 시 첫 작업 = §7.2 parser 계약 보강(별도 핸드오프·커밋 단위).
3. DB 마이그레이션 — 사용자 네트워크 몫(불변).
4. mtime 이상 2건(§4 주석) — 사용자 확인 대기.
