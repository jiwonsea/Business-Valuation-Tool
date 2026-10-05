# REVIEW — MU FY2026 Q4 리서치 리포트 PLAN rev-1

- 검토자: Codex
- 검토일: 2026-09-28 KST
- 대상 바이트: `forecast/PLAN_mu_report_fy2026q4_rev1_superseded.md`
- 대상 SHA-256: `d4d41b9ae3d65de68e39120663f9f7c1f56770574ec9d84af90988b9c8374fb0` — 재계산 일치
- 경로 주의: 현재 `forecast/PLAN_mu_report_fy2026q4.md`는 rev-3이며 SHA-256이 `6a735087…f324`다. 본 판정은 요청된 rev-1 보존본에만 적용한다.
- 전체 판정: **CHANGES REQUESTED**
- 범위: 계획 검토만 수행했다. 빌드 코드·가정 YAML·리포트 산출물은 만들거나 수정하지 않았다.

## 1. 결론

발행 방향의 골격은 타당하다. 프린트 후 `Review & Outlook`을 본판으로 삼고, Freeze A와 리포트 레이어 추정을 분리하며, 목표주가·투자의견을 만들지 않는 선택은 유지할 수 있다.

그러나 rev-1은 실행자가 임의로 결정해야 할 핵심 계약을 닫지 못했다. 특히 프린트 전 입력 격리, FY26E 보존, RLE 계산 소유권, 3표의 행·식, 암시 배수 정의, 차트 가용성, 한/영 패리티가 불완전하다. 아래 Q-1~Q-12 및 §4의 필수 수정 사항을 반영한 다음 재검토해야 한다.

## 2. §1 P0 사실 독립 재검증

| # | 판정 | repo 재검증 결과 |
|---|---|---|
| P0-1 | **대체로 확인, 문구 수정 필요** | `forecast/cli.py`가 `md_builder`, `html_builder`, `static_charts`, `xlsx_writer`를 호출한다. SK 파일은 MD/HTML/PDF/XLSX와 PNG 2개이며 PDF는 7쪽, Headless Chrome/Skia 생성이고 각 페이지에 `26. 9. 13. 오전 3:56` 및 `file:///F:/...`가 남는다. XLSX는 `forecast`, `scenarios`, `backtest` 3시트이고 수식은 0개다. MD의 EPS MAPE와 backtest 행은 비어 있고 분기 라벨은 2025Q1–Q4다. 다만 “9개 절 중 서술 없음”은 문자 그대로는 틀리다. below-OP 및 이벤트 설명 문단이 있으므로 “셀사이드형 분석 서술이 부족한 자동 산출물”로 고쳐야 한다. |
| P0-2 | **확인, 범위 명시 필요** | NVDA 2026-08-26 산출물은 33쪽 WeasyPrint PDF, 본문·HTML·4시트 재무 XLSX와 rev-3 PLAN을 갖춘 완성형 선례다. SK하이닉스 2026-08-07은 19쪽 PDF와 8시트 XLSX다. 다만 `valuation-results/`에는 더 늦은 날짜의 주간·IPO 폴더도 있으므로 “최신 완성본”은 “확인한 셀사이드형 기업 리포트 중 최신”으로 한정해야 한다. |
| P0-3 | **PASS** | `.gitignore`가 `valuation-results/`를 무시하고 `git ls-files valuation-results`는 0건이다. |
| P0-4 | **PASS** | 확인한 NVDA·SK하이닉스 완성본은 한국어 단일판이며 영어판 패리티 선례는 없다. |
| P0-5 | **PASS** | rev-1 보존본과 MU START 파일은 실제 LF이고 `git check-attr`도 두 파일에 `eol: lf`를 반환한다. 루트 `CLAUDE.md`의 CRLF 지침과 별개로 신규 `forecast/**` 텍스트를 LF로 고정하는 결론은 현재 파일 관행과 맞다. |
| P0-6 | **PASS** | `forecast/engine/valuation_bridge.py`는 `eps_delta_pct = (model EPS - consensus EPS) / consensus EPS`, `fair_value_delta_pct = elasticity × eps_delta_pct` 구조다. 컨센서스가 `None`/0이면 delta들을 `None`으로 둔다. MU FROZEN은 컨센서스 비교를 `UNAVAILABLE`로 고정하고 마지막에 예측 출력을 밸류에이션 입력에 연결하지 않는다고 명시한다. 따라서 이 브리지를 쓰지 않는 결론이 맞다. |
| P0-7 | **PASS** | NVDA HTML·빌더는 NVIDIA 로고와 `#76B900` 팔레트를, SK 빌더는 SK 로고와 SK Red/Orange 팔레트를 사용한다. |
| P0-8 | **PASS** | `forecast/reports/sndk_fy2026q4_SCORED.md` 명명 선례가 있고, `forecast/reports/mu_fy2026q4_SCORED.md`는 현재도 없으며 Git 이력에도 없다. 따라서 rev-1 시점의 “프린트 전·MU SCORED 부재” 판단은 repo 상태와 일치한다. 다만 E2-B가 SCORED에 의존한다는 것은 관측 사실이 아니라 D1의 정책 결정이므로 사실 표와 결정 표를 구분해야 한다. |

추가 재현: `python -m pytest forecast/tests/test_frozen_integrity.py forecast/tests/test_valuation_allowlist.py -q -p no:cacheprovider`는 **53 passed**였다.

## 3. §9 Q-1~Q-12 판정

| # | 판정 | 이유 및 rev-2 요구사항 |
|---|---|---|
| Q-1 | **CHANGES REQUESTED** | ⓑ 단독과 프린트 전 인프라 선행은 타당하다. 그러나 G-9는 산출값의 레이어 혼입만 검사하며 어떤 파일을 읽었는지 증명하지 못한다. 또한 §2 일정은 E2-A를 P3·E1 전에 시작할 수 있게 써 §6 단계 순서와 충돌한다. E2-A는 P3 승인과 E1 확정 뒤에만 시작하고, 허용 입력 경로+전체 SHA allowlist, 금지 입력 목록, 단일 read seam과 접근 로그를 고정하라. post-print 슬롯은 테스트 fixture만 허용해야 한다. |
| Q-2 | **CHANGES REQUESTED** | 프린트 후 FY26A-8K를 주 실적으로 올리는 것은 맞지만 START와 Freeze A가 고정한 FY26E를 소거하면 사전등록 대 실적 비교가 사라진다. FY23A–FY25A를 역사 3개년으로 유지하고 `FY26E-PREREG_A`, `FY26A-8K`, `FY26A-10K`를 별도 레이어로 병기하라. 10-K 반영은 기존 파일 덮어쓰기가 아니라 판 번호를 올리는 조건도 고정해야 한다. |
| Q-3 | **PASS** | 프린트 후 RLE의 seed를 FQ1 FY27 가이던스로 바꾸는 것이 합리적이다. Freeze A 프로파일 경로는 RLE 입력으로 재사용하지 말고, 부록에서 FY27 Q1–Q3의 매출·OPM·GAAP EPS와 두 정보 컷오프를 나란히 보여라. |
| Q-4 | **PASS** | `forecast/inputs/`가 맞다. 실제 valuation allowlist 스캔은 `forecast/profiles/`와 `forecast/reports/*_FROZEN.md`를 대상으로 하며 `forecast/inputs/`는 보지 않는다. YAML은 엔진 프로파일이 아닌 report-layer snapshot임을 나타내는 `scope`, cutoff, source, unit, week basis, confidence, input SHA를 가져야 한다. |
| Q-5 | **CHANGES REQUESTED** | “1순위, 불가 시 산술 강등”은 실행 계약이 아니다. `run_generic_forecast()`는 매출·OP·NI·EPS를 계산하지만 `gross_profit`과 `gp_margin`을 0으로 두며 B/S·C/F를 만들지 않는다. FY28 연간 단독 행도 분기 엔진 계약과 맞지 않는다. FY27 지원 행은 메모리 내 `GenericProfile` 호출, GM·opex bridge·FY28·capex·D&A·FCF·순현금은 리포트 레이어의 명시적 순수식으로 고정하고, 행별 입력 fact·식·검증 항등식을 적어야 한다. |
| Q-6 | **PASS** | +$0.27은 FQ4 FY26의 고정 PREREG 가정일 뿐 FY27/FY28 가정이 아니다. FY27E·FY28E 비GAAP EPS는 `UNAVAILABLE_WITHOUT_ASSUMPTIONS`가 맞다. 표지 핵심 수치표도 같은 상태를 명시해야 한다. |
| Q-7 | **PASS** | 14주 이슈가 없더라도 벤더의 fiscal-period mapping과 basis가 검증되지 않았다. FY27 컨센서스는 표시 전용으로 두고 gap, beat/miss, 색상, 방향 문장을 만들지 말며 `UNAVAILABLE_FOR_COMPARISON` 상태를 사용해야 한다. |
| Q-8 | **CHANGES REQUESTED** | BU 차트는 동일 4-BU 정의로 비교 가능한 기간이 최소 2개일 때만 “추이”로 부를 수 있다. 한 기간이면 single-period mix다. 또한 `low-60s`를 예시처럼 60–64%로 바꾸는 것은 원문에 없는 수치화다. 명시적 숫자 구간만 range band로 그리고 언어적 bucket은 범주형 표로 내려야 한다. 강등 시 8-chart 요건을 채울 대체 차트도 미리 고정하라. |
| Q-9 | **PASS** | 신규 `forecast/**` 텍스트 LF는 실제 파일 속성·바이트와 맞는다. 기존 파일의 개행은 변경하지 않는다. |
| Q-10 | **CHANGES REQUESTED** | 역방향 DCF 제외와 금지 필드 구조는 타당하지만 암시 배수가 재현 가능하지 않다. 기준가 거래일·통화·split basis, 희석주식수 기간, 시가총액 식, 현금·시장성투자·총차입·SCA 예치금 처리, EBITDA와 FCF 정의, 각 분모의 기간·52/53주 basis, P/E·EV/EBITDA·EV/Sales·FCF yield 식과 `N/M` 조건을 고정하라. 히트맵은 같은 계산 경로로 FY27 EPS와 암시 P/E를 재계산해야 한다. |
| Q-11 | **CHANGES REQUESTED** | 제안 파일명은 FROZEN/SCORED 정규식과 충돌하지 않는다. 그러나 `.gitignore`의 전역 `*.xlsx` 때문에 공유 XLSX는 현재 기본적으로 무시된다. 커밋 후보라면 좁은 exception 또는 승인된 명시적 force-add 정책이 필요하다. KO/EN PDF, 공유 XLSX, 감사 가능한 PNG 원본을 E4 후보로 명시하고, add/commit은 Jiwon 승인 후 호스트에서만 하며 push는 별도 승인으로 분리하라. |
| Q-12 | **CHANGES REQUESTED** | 숫자 토큰 다중집합과 fact_id 집합의 별도 비교는 값이 fact 사이에서 서로 바뀌어도 통과할 수 있다. canonical manifest를 `fact_id → raw_value, display_value{ko,en}, unit, period, basis, label, source_id, lineage`로 만들고 두 언어의 표 셀·본문 placeholder·차트 series가 같은 manifest 항목을 참조하는지 검증하라. 숫자 토큰 검사는 보조 게이트로만 남기고 locale 차이는 명시 allowlist로 처리해야 한다. |

## 4. §9 밖 필수 수정 사항

### R-1. P0 인벤토리를 파일별로 완결할 것

부록 A는 여러 파일을 한 행으로 묶고, “원본 직접 열람”을 파일별 증거로 남기지 않는다. START가 지정한 SK md/html/pdf/xlsx/PNG/call brief/scorecard/START/HANDOFF, NVDA T1–T4/V2/FREEZE_A/MANIFEST/PLAN/HANDOFF revision, valuation plan/engine/test를 각각 한 행으로 분리해 크기·SHA·구성·재사용 판정을 기록하라. `valuation-results/`는 지정 추적 파일을 대체하지 않는 보조 선례로 분리한다.

### R-2. E2-B 시작을 날짜가 아닌 입력 게이트로 만들 것

다음 네 조건을 모두 요구하라: 원본 8-K/EX-99.1/준비문과 SHA, MU SCORED의 commit/SHA, 기준가 2경로 캡처, P3 승인과 E1 확정. 현재 SCORED가 없으므로 E2-B는 fail closed여야 한다.

### R-3. 3표의 행·식·가용성 계약을 만들 것

“전체 손익”과 “핵심 B/S·C/F”는 구현 명세가 아니다. FY23A–FY25A, FY26A-8K, FY27E/FY28E별 행 목록과 가용 상태를 고정하라. 순현금 roll-forward에는 OCF, capex, 투자자산 매매, 배당·자사주, 차입 변동, 인수, SCA 예치금 처리와 미입력 시 `UNAVAILABLE` 규칙이 필요하다. ROE의 평균자본/기말자본 basis도 정해야 한다.

### R-4. 역사 항등식 허용오차를 명시할 것

SEC 표는 $M 단위 반올림이다. G-3/G-3b/G-3c의 무허용 “fail closed”는 정상 공시를 실패시킬 수 있다. 항등식별 허용오차를 구성 항목 수와 표시 정밀도에 맞춰 고정하고, 차이를 맞추는 플러그는 금지하라.

### R-5. 차트와 표가 같은 fact를 소비하도록 검사할 것

G-13은 차트 존재·참조만 본다. 각 series point가 canonical 또는 derived fact와 일치하는 G-13b가 필요하다. 차트용 숫자 복사를 금지하라.

### R-6. provenance 범위를 모든 숫자로 넓힐 것

G-14는 표의 `source_id`만 검사한다. 본문·표지·캡션·각주·일정 날짜까지 검사하고 derived fact는 원자료 source와 계산 lineage를 모두 가져야 한다.

### R-7. +$0.27 적용 범위를 스키마로 막을 것

고정 bridge fact는 `period = FY2026Q4`, `basis = PREREG_A_ASSUMPTION`일 때만 허용하고 다른 기간 참조를 게이트 실패로 만들어라. 주의문만으로는 FY27/FY28 전파를 막지 못한다.

### R-8. 형식별 QA를 구체화할 것

- PDF: KO/EN 전 페이지 렌더, 잘림·겹침·빈 페이지·브라우저 헤더/푸터·로컬 URL 검사
- XLSX: 수식 재계산 또는 cached value, 오류 셀 0, 시트별 unit/source/as-of 검사
- HTML: 외부 네트워크 의존 0, 링크·이미지 검사
- MD: 로컬 링크와 표 열 수 검사

P0-1에서 확인한 SK PDF의 날짜·`file:///` 잔존을 명시적 회귀 사례로 넣어라.

### R-9. E2 생성과 공개 행위를 분리할 것

E2-A/B/C는 로컬 생성까지만 허용하고 add/commit/push를 하지 않는다. E4에서 승인 파일 목록과 SHA를 확인한 뒤에만 호스트 commit 후보가 되며 push는 별도 승인이다. XLSX ignore 예외도 이 단계에서만 적용해야 한다.

### R-10. P0 표현을 사실과 판단으로 분리할 것

P0-1의 “서술 없음”을 정확한 결손 설명으로 고치고, P0-2의 “최신” 범위를 한정하며, P0-8의 SCORED 의존성은 관측 사실이 아닌 정책으로 D1에만 남겨라.

## 5. 재검토 종료 조건

rev-2는 Q-1~Q-12를 번호 순서대로 답하고, R-1~R-10을 본문에 반영하거나 미반영 이유를 각 항목별로 적어야 한다. 그 전에는 P3 승인 요청이나 E1/E2 실행으로 넘어가지 않는다.

---

이 문서는 투자 자문이 아니다. This document is not investment advice.
