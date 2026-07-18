# `PLAN_deep_research.md` 설계 평가

평가 기준일: 2026-07-11  
범위: 현재 작업 트리와 읽기 전용 NVDA 골든 산출물 검증. 코드 수정 없음.

## 1. 사실 주장 판정표

| ID | 판정 | 근거 |
|---|---|---|
| R1 | **확인** | SEC는 현금 태그 우선순위상 `CashAndCashEquivalentsAtCarryingValue`가 있으면 결합 태그를 보지 않고 차입금에서 그 값만 차감한다(`pipeline/edgar_parser.py:48-51,81-96,140-143`). DART도 현금·단기금융상품만 차감한다(`pipeline/dart_parser.py:152-185`). 자동 프로필 `net_debt=435`와 골든 `-41,865`의 방향 전환도 확인된다(`profiles/nvda.yaml:138`, `valuation-results/2026-07-10-nvda-deep-dive/nvda_ttm.yaml:204`). |
| R2 | **확인** | 미국/일본/한국의 rf·ERP가 조건식 상수다(`pipeline/profile_generator.py:197-204`). 현재 값에는 관측일·출처가 없다. |
| R3 | **확인** | yfinance 레버드 베타를 조정 없이 Hamada로 언레버링한다(`pipeline/profile_generator.py:211-223,261-267`). 품질 점수는 범위 기반 점수일 뿐 실행 차단이 아니며(`engine/quality.py:560-568`), 현 investability gate에도 베타 항목이 없다(`engine/investability_gate.py:159-175`). |
| R4 | **부분수정** | SEC 파서는 `fp=FY`, 10-K 연간값만 추출한다(`pipeline/edgar_parser.py:65-106`); 분기/TTM 부재는 맞다. 다만 stale 상한은 6개월이 아니라 결산 후 다음 10-K 전까지 **최대 약 12개월+공시 지연**이므로 표현을 고쳐야 한다. |
| R5 | **부분수정** | `MAIN` 하나인 자동 프로필(`profiles/nvda.yaml:20-29`)은 단일 성장/기술 기업이므로 DCF로 라우팅된다(`engine/method_selector.py:236-245,262-263`). 다만 `--auto`에는 LLM 세그먼트 분류 경로가 이미 있어(`pipeline/profile_generator.py:675-682`) “미추출이 항상 MAIN을 만든다”가 아니라 **공시 기반 추출 부재와 분류 실패/비-AI draft의 폴백 문제**다. |
| R6 | **부분수정** | 생성기가 실제 `MAIN: 10.0` TODO를 쓴다(`pipeline/profile_generator.py:493-502`). 현재 gate는 placeholder를 `block` 판정하지만(`engine/investability_gate.py:140-146,159-175`), 실행부는 결과를 `draft=True`로만 바꾸고(`valuation_runner.py:525-549`) Excel/DB 저장은 계속한다(`pipeline/profile_generator.py:1140-1158`). 즉 “판정 자체가 없음”은 틀리지만 실질적인 배포 차단 부재는 맞다. |
| R7 | **확인** | 프롬프트가 LLM에 `ev_ebitda` 숫자를 요구하고(`ai/prompts.py:115,154`), 생성기가 이를 그대로 적용한다(`pipeline/profile_generator.py:699-708`). 골든에도 Intel Arc, 롯데칩스, Xilinx와 2024 consensus 문구가 남아 있다(`nvda_ttm.yaml:217,244,260,298`). P1 원칙의 근거는 유효하다. |
| R8 | **확인** | 프로덕션 후보는 `pipeline/peer_fetcher.py:20-38`에서 `get_quote_summary()` REST를 호출하지만, 호출 검색 결과는 함수 정의와 테스트뿐이다. 실제 yfinance 대안은 `calibration/peer_fetcher.py:45-78`이고 현재는 보고서/스크립트에서만 사용된다. “7종 전부 빈 값”은 핸드오프 실측으로 수용하되 네트워크 상태에 따라 재검증 가능한 운영 관측치다. |
| R9 | **부분수정** | 정상화 순이익 필드/경로가 없고 multiples 경로는 `net_income`을 직접 쓴다(`valuation_runner.py:1527,1550-1558`). 다만 $15,936M은 TTM GAAP NI $159,613M의 **약 10.0%**이지 27%가 아니다(`_verified_data.md:27,75`); GAAP-비GAAP 차이의 대부분이라는 설명으로 수정해야 한다. |
| R10 | **부분수정** | 자동 핵심 재무 숫자에 accession/url/as-of를 붙이는 evidence ledger는 없다. 다만 peer의 단일 `source` 필드(`schemas/models.py:779`), reconciliation의 `as_of`(`pipeline/reconciliation.py:102`), Raw Data 시트(`output/sheets/raw_data.py:65`)가 있어 “출처 추적이 전혀 없음”은 과장이다. **material field 단위 1차 출처 추적이 없음**이 정확하다. |

## 2. Q1~Q7 답변

### Q1. P0 스코프와 수치 검산

- `profiles/nvda.yaml`을 메모리에서만 복제해 동일 엔진으로 검산했다: 원본 $63/WACC 16.39%, 순현금만 교정 $64, βL≈1.50·WACC 12.50% $91, rf 4.56%·ERP 4.6%·WACC 11.46% $104.
- WACC를 정확히 11.0%로 맞춰도 $109, $202.34 대비 **−46.1%**다. 따라서 “P0만으로 −20%대”와 `|괴리|≤30%` 검수 기준은 반증된다.
- 원인은 순현금 효과가 주당 약 $1.75에 불과하고, FY26 단일세그먼트 DCF 앵커/방법론이 그대로이기 때문이다.
- P0에는 공시 기반 세그먼트 **검출/라우팅 최소 기능**을 앞당기되, 숫자 없는 세그먼트만 추가해서는 부족하다. TTM, 관측 배수, 시나리오별 배수까지 갖춘 수직 슬라이스를 별도 골든 단계로 둬야 한다.

### Q2. 순차입금 정의 변경의 폭발 반경

- 과거 DB 행은 당시 예측의 불변 스냅샷으로 보존하고 덮어쓰지 않는다. 신규 정의와 비교하려면 별도 재실행 cohort가 필요하다; 기존 백테스트 성과를 소급 변경하면 look-ahead/계보가 훼손된다.
- `net_borr` 병기만으로는 소비자가 어느 값을 사용했는지 모호하다. `net_debt_components`, `normalization_version`, `as_of/source`를 입력·snapshot에 저장하고 구버전은 legacy로 명시해야 한다.
- DB에는 이 버전/구성요소 컬럼(또는 명시적 JSON 계약) 마이그레이션이 필요하다. 프로필은 Optional 기본값으로 하위호환하고, 과거 프로필 일괄 재작성은 하지 않는다.
- 시장성 지분증권 $73.6B 제외에는 동의한다. 순환·전략 투자 성격은 영업 현금과 동급으로 볼 수 없으므로 기본 equity bridge에서 제외하고, 검증 가능한 유동 지분만 별도 상방 브리지로 보여주는 편이 안전하다.

### Q3. 베타 처리

- 보편적 `[0.3,2.0]` 이탈만으로 산업 평균에 조용히 대체하면 안 된다. NVDA 2.2는 관측된 주가 민감도일 수 있으므로 원값, 기간/빈도, 조정값과 WACC 민감도를 함께 보존한다.
- 우선순위는 검증된 raw equity beta → Blume 조정값 → 관측 peer median/산업 beta **교차검증**이다. peer 수집이 실패하면 산업 테이블을 독립 fallback으로 사용해 순환 의존을 끊는다.
- peer beta는 P0-5 관측치 수집 후 계산하되, 멀티플 선정과 분리된 동일 시점 데이터셋으로 만든다. 최소 N·분산·as-of를 통과하지 못하면 대체하지 않는다.
- 차단 조건은 “범위 이탈”이 아니라 출처/관측창 부재, raw-vs-reference 중대 불일치 미해결이다. override 시 원값과 영향 차이를 산출물에 명시한다.

### Q4. 주간 파이프라인과 게이트

- 전체 배치 중단은 부적절하다. 회사별로 계산·진단·프로필은 보존하되 `investability=blocked`, blocker 목록, 단계별 상태를 저장하고 투자용 Excel/게시/이메일 추천 목록에서 제외한다.
- 감사용 진단 artifact와 투자 가능 artifact를 분리해야 한다. 현재 `draft=True`만 설정하고 Excel/DB를 계속 저장하는 구조는 소비자가 플래그를 무시할 수 있다.
- 주간 이메일에는 성공/차단/실패 건수와 차단 사유를 반드시 보여 빈 메일을 방지한다. 투자 가능 종목 0개도 정상 결과로 전달한다.
- `--force`는 차단을 지우지 말고 “수동 override” 상태·사유·사용자·시각을 남겨야 한다. 자동 scheduler에는 force를 허용하지 않는다.

### Q5. TTM 검산 규칙

- SEC Company Facts의 `frame=CY...`만 신뢰하면 비달력 결산사(NVDA 포함), 비교표 중복, YTD/standalone 혼합에서 깨진다. accession·form·start/end·fiscal period를 함께 묶고 duration을 검증해야 한다.
- 매출처럼 큰 양수 항목은 `max(1%, 단위 반올림 materiality)`, 영업이익/현금흐름은 `max(2%, materiality)`를 기본값으로 하되 회사별 태그 변경·재작성은 명시적 예외 처리한다.
- 0%는 불가능하고 일괄 5%는 너무 느슨하다. 오차율뿐 아니라 절대 materiality와 동일 accession/회계범위를 동시에 요구한다.
- DART는 분기값이 누적(YTD)인 경우가 많아 단순 4개 합이 성립하지 않는다. Q4=`FY−3Q 누적`, Q2/Q3 standalone=`당기 누적−직전 누적`으로 변환한 뒤 연결/별도·공시 버전을 맞춰 검산한다.

### Q6. 누락 항목

- 옵셔널리티는 LLM이 후보와 서사를 만들 수 있지만, 자동 `SEG_OPT*` 가치 숫자를 만들면 R7을 반복한다. 공시 매출/계약/가이던스가 없으면 0원 기본+수동 검토 또는 reverse-DCF 진단으로 제한한다.
- `segment_multiples`, `segment_revenue/ebitda`, method override의 Bull/Base/Bear 계약을 계획에 포함해야 한다. 이것이 TTM $175의 주요 차별화 장치다.
- Q2 $91B 가이던스는 actual TTM에 섞지 말고 guidance/forward anchor로 출처·범위·기간을 가진 별도 입력으로 반영한다.
- $80B 승인은 실제 매입이 아니다. 승인잔액·실제 분기 매입·평균 매입가로 희석주식수 전망을 만들고, 가격민감도와 SBC 상쇄를 함께 반영해야 한다.

### Q7. 실행 순서

- 먼저 버전·provenance 계약과 골든 기대값을 확정한 뒤, **P0 데이터 정상화 + 관측 peer + 최소 세그먼트 라우팅**을 한 수직 슬라이스로 만든다.
- 다음에 게이트를 scheduler/Excel/DB/게시 경계까지 연결하고, 회사별 차단 회귀를 검증한다. 게이트를 먼저 강제하면 기존 데이터 결손 때문에 배치가 대량 차단된다.
- 그 뒤 P1 분기/TTM을 US 1개(NVDA)에서 완주하고 KR 누적분기 규칙을 별도 확장한다. 이어 evidence ledger와 순이익 정상화를 붙인다.
- 즉 `계약/골든 → P0 수직 슬라이스 → 배포 게이트 → P1 US → P1 KR/P2`가 적절하며, 단순 P0 가격 골든 통과 후 P1 순서는 수정해야 한다.

## 3. PLAN 수정 지시

### P0 스코프 확정

1. **P0-0 데이터 계약/계보를 선행 추가**: `net_debt_components`, `normalization_version`, material field의 `source/accession/as_of`, raw/normalized 값을 정의한다. DB snapshot과 Excel이 같은 버전을 표시해야 한다.
2. **P0-1 순차입금**: 태그를 단순 합산하지 말고 중복 개념 우선순위와 구성요소 reconciliation을 설계한다. `net_borr`는 legacy, 엔진 소비값은 명시적 normalized 필드로 분리한다.
3. **P0-2 베타**: “범위 이탈 시 산업 평균 대체/클램프”를 삭제한다. 관측창 검증, Blume/reference 비교, 최소 N·분산 규칙, 수동 override provenance, WACC 민감도를 추가한다.
4. **P0-3 매크로**: FRED/ECOS 실패 상수에는 기준일·stale TTL·fallback 상태를 기록한다. ERP 업데이트 주기와 rf/ERP 동일 기준일 규칙을 명시한다.
5. **P0-4 게이트**: 회사별 상태 머신으로 재설계한다. 계산/감사 저장은 허용하되 투자 Excel·DB publication·이메일 추천·블로그 업로드는 차단하고 진단 artifact는 보존한다.
6. **P0-5 peer**: LLM 출력은 `ticker + 선정 이유`만 허용하고 실제 ticker resolution, 상장 상태, 독립 법인 여부, 관측일, 최소 peer N을 검증한다. 조회 실패 시 기존 LLM 숫자를 보존하지 말고 결측 처리한다.
7. **P2-1의 최소 부분을 P0-6으로 이동**: 공시 세그먼트 존재 여부 탐지와 `MAIN→DCF` 라우팅 경고/차단을 P0에 포함한다. 완전한 XBRL dimension 추출과 배분은 P2에 남긴다.

### 검수 기준 재작성

- P0 정상화 검수에서 `|괴리율|≤30%`를 삭제한다. 대신 구성요소 합계, provenance, beta 처리 경로, peer 관측 성공률, gate 상태 같은 입력 정확성 기준을 사용한다.
- NVDA FY26 단일세그먼트 DCF의 P0 참고 기준은 현재 검산상 약 **$91~109, 괴리 −55%~-46%**다. 가격 수렴을 실패로 보지 않는다.
- `|괴리|≤30%`는 **TTM + 공시 세그먼트 + 관측 배수 + 시나리오 배수** 수직 슬라이스의 통합 골든 기준으로 이동한다. 골든 결과 자체를 목표값에 맞추는 튜닝은 금지한다.
- 테스트를 US calendar/non-calendar, KR 누적분기, 현금성자산 태그 중복, peer 결측, 배치 일부 차단 사례로 확장한다.

### P1/P2 추가·재배치

- P1에 분기 duration/accession dedup, FY reconciliation의 상대+절대 허용오차, restatement 처리, US/KR 서로 다른 분기 변환 규칙을 추가한다.
- P2에 시나리오별 segment driver 3-layer 계약, guidance/forward anchor, buyback 기반 diluted-share forecast를 추가한다.
- evidence ledger는 P2 후순위가 아니라 P0-0의 최소 계약부터 시작하고, 완전한 `_verified_data.md` 렌더링만 P2에 둔다.
- 컨센서스 P3 전에도 회사 가이던스 anchor는 1차 출처이므로 별도 P1.5로 허용한다. 컨센서스와 실제/가이던스를 혼합하지 않는다.

## 4. 구현 전 블로커

1. **순차입금 taxonomy 미확정**: 현금, 단기투자, 시장성 채무증권, 제한현금, 전략적/시장성 지분증권의 포함·제외 및 중복 태그 우선순위를 표로 확정해야 한다.
2. **베타 정책 미확정**: 관측창/빈도, Blume 사용 위치, peer 최소 N, 산업 fallback 데이터와 갱신 주기, block/override 조건이 필요하다.
3. **게이트 배포 의미 미확정**: draft, blocked, diagnostic-only, published의 상태와 Excel/DB/storage/email/blog 각 소비자의 허용 행렬이 필요하다.
4. **골든 acceptance 분리 필요**: P0 입력 정확성과 P0+TTM/SOTP 가격 수렴을 같은 `≤30%` 기준으로 묶으면 목표값 역튜닝을 유도한다.
5. **분기 검산 계약 미확정**: SEC 비달력 결산과 DART 누적분기의 변환·허용오차·재작성 처리 규칙이 먼저 필요하다.

## 5. 판정

**수정 후 착수**

Research → Normalize → Anchor 방향, LLM 숫자 금지, 다중 앵커, evidence ledger의 큰 방향은 타당하다. 그러나 P0만으로 NVDA 괴리가 30% 이내로 수렴한다는 핵심 수치가 반증되었고, 베타의 조용한 대체·게이트의 배포 의미·순차입금 버전 계약이 미정이다. 위 블로커와 P0 검수 기준을 PLAN에 반영한 뒤 구현해야 한다.
