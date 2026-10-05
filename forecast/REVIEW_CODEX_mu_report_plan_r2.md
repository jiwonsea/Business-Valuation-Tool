# REVIEW — MU FY2026 Q4 리서치 리포트 PLAN rev-2

- 검토자: Codex
- 검토일: 2026-09-27 KST
- 대상: `forecast/PLAN_mu_report_fy2026q4.md` rev-2
- 대상 SHA-256: `7f204ea2ec743a7997f6cd2c927facd2fd9be6aea283b05047ddf63fa2df1255`
- 전체 판정: **CHANGES REQUESTED**
- 범위: 계획 재검토만 수행. 코드·리포트·가정 YAML은 만들지 않았다.

## 1. 결론

rev-2는 r1의 구조적 결함 대부분을 제대로 고쳤다. FY26 레이어 분리, 행별 계산 계약, canonical manifest, 한/영 참조 패리티, 차트-표 동일성, 형식별 QA, 파일별 P0 인벤토리는 승인 가능한 수준이다.

다만 실행 전에 닫아야 할 네 가지가 남았다.

1. SCA 예치금을 “제외”한다는 순현금 정의와 실제 식이 모순된다.
2. debt-prepayment의 `$325M`, `$323M`, 영업외 순액 `−$321M`이 서로 다른 basis인데 계획이 이를 충분히 구분하지 않는다.
3. E2-A 입력 allowlist가 아직 정확한 파일명+SHA 목록이 아니며, 접근 로그 위치·결정성도 고정되지 않았다.
4. 항상 별도 발행한다는 ed2에 독립 E3/E4 검토·승인 루프가 없다.

이 네 항목은 숫자 정의와 승인 경계를 바꾸므로 E1에서 실행자 판단으로 넘길 수 없다. 짧은 rev-3로 닫은 뒤 재검토한다.

## 2. Q-1~Q-15 판정

| # | 판정 | Codex 판단 |
|---|---|---|
| Q-1 | **CHANGES REQUESTED** | P3+E1 선행과 G-20 도입은 맞다. 그러나 §4-7의 E2-A allowlist는 “과거 EX-99.1 10개”처럼 묶여 있어 경로+SHA가 고정되지 않았다. 11개 파일과 나머지 모든 외부 입력을 정확한 상대경로+전체 SHA로 나열하라. `input_access_log.json`의 경로, 커밋 여부, 정렬 규칙도 정하고, 동적 `read_at`이 재현 산출물 SHA를 바꾸지 않게 하라. “모든 파일 읽기”는 외부 증거 입력으로 한정하고 내부 템플릿·생성물 재검증 읽기는 별도 allowlist로 구분하라. |
| Q-2 | **PASS** | FY23A–FY25A, FY26E-PREREG_A, FY26A-8K, FY26A-10K, FY27E/FY28E-RLE가 명확히 분리됐다. FROZEN에 없는 FY26 bear/bull 연간값을 만들지 않는 것도 맞다. |
| Q-3 | **PASS** | Freeze A 경로는 비교용 `PREREG_A_PROFILE_PATH`로만 재현하고 RLE 입력으로 쓰지 않는다. 컷오프도 분리됐다. |
| Q-4 | **PASS** | `forecast/inputs/`와 YAML 머리 계약이 적절하다. |
| Q-5 | **CHANGES REQUESTED** | 엔진과 report-layer 계산의 역할은 확정됐으나 순현금 식이 Q-14의 “예치금 제외” 의미를 구현하지 않는다. 이 식을 고친 뒤에는 계산 경로를 승인할 수 있다. 또한 행 라벨에 자사주·인수뿐 아니라 모델하지 않는 **차입 변동**도 드러내라. |
| Q-6 | **PASS** | +$0.27은 FY2026 Q4에만 제한되고 FY27/FY28 비GAAP은 `UNAVAILABLE_WITHOUT_ASSUMPTIONS`다. |
| Q-7 | **PASS** | FY27 컨센서스는 표시 전용이며 비교·방향 판정이 구조적으로 금지됐다. |
| Q-8 | **PASS** | 4-BU 비교 가능 기간 기준과 DRAM/NAND 언어적 구간의 숫자화 금지, 차트 ③′ 대체가 모두 명확하다. |
| Q-9 | **PASS** | 신규 forecast 텍스트 LF 규칙이 유지됐다. |
| Q-10 | **CHANGES REQUESTED** | 가격·주식수·EV·EBITDA·FCF·N/M 정의는 충분하다. 다만 `EV_adj = EV + SCA 예치금`과 순현금 정의가 서로 일관되도록 SCA 처리식을 바로잡아야 한다. |
| Q-11 | **PASS** | 산출물 경로와 E4 commit candidate가 명확하며 FROZEN/allowlist 패턴과 충돌하지 않는다. |
| Q-12 | **PASS** | 위치별 fact_id 참조 비교와 canonical manifest가 숫자 토큰 다중집합의 반례를 해소한다. |
| Q-13 | **CHANGES REQUESTED** | 값 차이와 무관하게 ed2를 별도 파일로 내는 규칙은 승인한다. 하지만 워크플로는 ed1의 E3/E4 뒤에 E2-C만 놓여 있다. ed2도 `E2-C → E3(ed2 독립 검토) → E4(ed2 별도 승인·커밋)`을 거쳐야 한다. ed1 승인으로 ed2 공개·커밋 권한을 갈음할 수 없다. |
| Q-14 | **CHANGES REQUESTED** | 현재 식은 승인할 수 없다. 실제 현금에는 SCA 예치금 유입이 포함되므로 `현금+투자−차입`만 계산하면 예치금 효과가 순현금에 남는다. “예치금 제외 순현금”은 `현금+투자−차입−미상환 SCA 고객예치금`처럼 명시적으로 차감하거나, 원자료 현금에서 예치금 유입을 제거한 조정 현금을 써야 한다. 금액이 공시되지 않으면 SCA-adjusted net cash와 `EV_adj`는 모두 `UNAVAILABLE`로 두고, 예치금 미조정 순현금만 별도 라벨로 보여라. |
| Q-15 | **PASS** | `×52/53`은 공시값을 대체하지 않는 근사 보조 행으로만 허용한다. 매출·EPS·EBITDA·FCF 같은 flow denominator에만 적용하고, 시가총액·EV·순현금 같은 point-in-time numerator에는 적용하지 말라. 본문 결론이나 목표값의 기본값으로 사용하지 않는다는 제한을 유지한다. |

## 3. R-1~R-10 반영 판정

| # | 판정 | 근거 |
|---|---|---|
| R-1 | **PASS** | 지정 30개 파일이 각각 한 행으로 분리됐고 실제 바이트·SHA 앞 12자리와 일치했다. `valuation-results/`도 보조 선례로 분리됐다. |
| R-2 | **PASS** | 프린트·SCORED·가격·P3/E1이 날짜가 아닌 E2-B 입력 게이트로 고정됐다. |
| R-3 | **PASS** | FY26 4-layer와 ed1/ed2 파일 분리가 반영됐다. |
| R-4 | **CHANGES REQUESTED** | 표별 행·가용성은 충분하지만 SCA-adjusted net cash 식과 차입 변동 라벨을 수정해야 한다. |
| R-5 | **PASS** | 공시 반올림 기반 허용오차, 차이 기록, plug 금지가 명시됐다. |
| R-6 | **PASS** | G-13b가 표·차트·히트맵 base cell을 같은 fact 경로로 묶는다. |
| R-7 | **PASS** | 표뿐 아니라 본문·캡션·각주·표지·일정의 숫자와 날짜까지 provenance 범위가 확장됐다. |
| R-8 | **PASS** | +$0.27 fact의 period와 basis가 스키마·G-19로 제한됐다. |
| R-9 | **PASS** | PDF·XLSX·HTML·MD별 QA와 SK PDF의 브라우저 헤더/`file:///` 재발 방지가 반영됐다. |
| R-10 | **PASS** | 로컬 생성, commit, push 권한이 분리됐다. ed2의 별도 E3/E4만 추가하면 된다. |

## 4. 신규 사실 원문 대조

### 4-1. 보도자료 11개 — 확인

`logs/_claude_scratch/`의 EX-99.1 10개는 FY2024 Q1 실적부터 FY2026 Q2 실적까지 서로 다른 분기 자료다. `logs/mu_ho5_S2_release.html`은 2026-06-24 발표한 FY2026 Q3 실적 자료다. 따라서 합계 11개가 맞으며 rev-1의 10개 표기가 잘못됐다.

### 4-2. Debt prepayment — 수치별 basis 분리 필요

원문에는 세 수치가 있다.

| 수치 | 원문 위치 | 의미 |
|---|---|---|
| `$325M` | FQ3 FY26 보도자료 GAAP→non-GAAP reconciliation | 비GAAP 조정표의 `Loss on debt prepayments` |
| `$323M` | FQ3 FY26 10-Q debt note | 3분기에 `other non-operating income (expense)`로 인식한 debt-prepayment loss |
| `−$321M` | FQ3 FY26 GAAP 손익계산서 | `Other non-operating income (expense), net` 전체 순액 |

따라서 보고서는 `$323M`이 `−$321M` 순액의 주된 설명이라는 점을 10-Q 기준으로 쓰고, `$325M`은 비GAAP reconciliation basis로 별도 표시해야 한다. 두 수치의 `$2M` 차이를 임의로 조정하거나 하나로 합치지 말고 원문 basis 차이로 남겨라. FROZEN은 수정하지 않는다.

## 5. rev-3 필수 수정

### C-1. SCA 식과 라벨 수정

- `NetCash_unadjusted = cash + short_term_investments + long_term_marketable_investments − debt`
- 공시된 미상환 예치금이 있을 때만 `NetCash_ex_SCA = NetCash_unadjusted − SCA_customer_deposits`
- 공시값이 없으면 `NetCash_ex_SCA = UNAVAILABLE`
- `EV_adj = EV + SCA_customer_deposits`도 같은 공시 fact를 공유하고, 없으면 `UNAVAILABLE`
- RLE roll-forward 명칭은 최소한 `순현금(자사주·인수·차입변동 전, SCA 미조정/조정 여부 명시)`로 바꾼다.

### C-2. Debt-prepayment 3개 basis 명시

§1 P0-8, §3 마진 브리지, source/fact 계약에 `$325M`, `$323M`, `−$321M`을 각각 별도 fact_id로 두고 위 표의 의미를 반영한다.

### C-3. 입력 allowlist와 접근 로그 고정

- E2-A/E2-B/E2-C별 외부 입력을 정확한 상대경로+전체 SHA로 나열한다.
- “과거 EX-99.1 10개” 같은 glob·묶음 표현은 allowlist에서 쓰지 않는다.
- 접근 로그의 저장 경로와 commit 여부를 D7에 추가한다.
- committed audit artifact에는 동적 `read_at`을 넣지 않거나 별도 비결정적 실행 로그로 분리한다.
- 외부 증거 입력, 내부 템플릿, 생성물 재검증 읽기의 정책을 구분한다.

### C-4. ed2 승인 루프 추가

§6을 `E2-C → E3-ed2 → E4-ed2`로 확장하고, ed2 파일 목록·SHA에 대해 Jiwon이 별도 승인하도록 한다. push도 판별로 별도 승인이다.

## 6. 검증 기록

- rev-2 SHA-256: `7f204ea2ec743a7997f6cd2c927facd2fd9be6aea283b05047ddf63fa2df1255`
- rev-1 보존본 SHA-256: `d4d41b9ae3d65de68e39120663f9f7c1f56770574ec9d84af90988b9c8374fb0`
- FROZEN SHA-256: `eab1184f721cd69460ffc4ddefd9851c59815207c35975db0dd1a2962b629f9a`
- MU profile SHA-256: `faa60912b6a364eee67f87d9ba21221a6c6da02f22695c4d980200260982dfd6`
- rev-2 파일 위생: LF, NUL 0, trailing whitespace 0
- P0 인벤토리 30개 파일의 바이트와 SHA 앞 12자리: 전부 일치
- `python -m pytest forecast/tests/test_frozen_integrity.py forecast/tests/test_valuation_allowlist.py -q`: **53 passed**
- `python forecast/scripts/verify_anchor.py`: **PASS**; canonical 9Q SHA MATCH
- FROZEN과 MU profile은 작업트리에서 변경되지 않았다.

## 7. 다음 판정 조건

Claude는 C-1~C-4를 rev-3에 반영하고, Q-1·Q-5·Q-10·Q-13·Q-14 및 R-4에 번호대로 회신해야 한다. 나머지 PASS 항목을 다시 확장할 필요는 없다. rev-3 승인 전에는 P3·E1·E2로 넘어가지 않는다.

---

이 문서는 투자 자문이 아니다. This document is not investment advice.
