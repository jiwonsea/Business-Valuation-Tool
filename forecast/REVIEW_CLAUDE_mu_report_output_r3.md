# REVIEW — Claude: MU 리포트 E2-A′ 산출물 r3 (rev-4 ed1 추가분)

- 검토자: Claude (E3, 범위 = **E2-A′**, `HANDOFF_CODEX_mu_report_exec.md` 부록 R4)
- 검토일: 2026-09-28 KST
- 기준: PLAN rev-4 `d007f554f68643891d7586f8c43c4254886f3826f54417c4e3144239f2a8e646` · HANDOFF `2f657886f34ed349c00c06c1a0291149a5f5da5b2222ec7a6c6472cff2fd1d25` · 직전 리뷰 r2(E2-A PASS, E2-B 조건 C-1·C-2)
- 전체 판정: **CONDITIONAL PASS** — 구현 6개 항목과 테스트 결과는 재현했다. 다만 **E2-B 착수 전에 고쳐야 할 결함 2건**(F-2·F-3)과 설명이 필요한 범위 이탈 1건(F-1)이 있다.
- 🔴 투자 자문 아님. This review is not investment advice.

## 1. 독립 재실행

| 항목 | 방법 | 결과 |
|---|---|---|
| 파일 SHA | 보고된 20개 파일 재계산 | **전부 일치** |
| 기준 문서 | PLAN rev-4 · HANDOFF · FROZEN `eab1184f…` · 프로파일 `faa60912…` | 전부 일치. FROZEN·프로파일은 변경 없음 |
| `test_mu_report.py` | 코드와 E2-A 입력 20개를 격리 환경(Python 3.11, WeasyPrint 70.0, Noto CJK)으로 복사해 실행 | **43 passed** — 보고와 일치 |
| `forecast/tests/` 전체 | 같은 환경 | 465 passed · 2 skipped · 1 deselected · 1 xfailed · **1 failed** — 실패 1건은 `test_disclosure_loader`의 `fitz`(PyMuPDF) 미설치로, 이번 변경과 무관한 환경 차이다. 보고(465 passed, 3 skipped)와 모순 없음 |
| `verify_anchor.py` · FROZEN 게이트 | — | **이 환경에서 재현 불가**(git 체크아웃·전체 데이터 캐시 필요). 호스트 재확인 필요(§4) |
| 재고 원문 대조 | 두 10-K htm에서 `Inventories` 행을 직접 파싱 | FY2022·FY2023(`mu-20230831.htm`), FY2024·FY2025(`mu-20250828.htm`) 값이 추출본과 **일치**. 좌표 T20/R7도 일치 |
| 재고일수 식 | 역사 manifest를 생성해 FY2023–FY2025 세 값을 손으로 재계산(평균 재고 ÷ COGS × 364) | **3건 모두 일치**. FY2023–FY2025 `period_weeks = 52` 확인 |
| i18n 고지 문안 | `disclaimer.conflict`·`conflict_short` KO/EN 4개 문자열 | 계획 D9와 **글자 그대로 일치** |
| 시장 데이터 박스 | i18n `market_data.rows` | 4행만 존재. 52주·거래량·유동비율 키 0 |
| P/B | `valuation.trailing_pb` | `UNAVAILABLE` 전파, BVPS ≤ 0 → `N/M`, RLE 기간 fact 없음 |
| 쪽 번호·목차 | `render.py` CSS | `counter(page)/counter(pages)`, `target-counter(attr(href), page)`를 직접 사용한다(우회 없음) |
| 확인 레코드 | `forecast/inputs/` | 실제 `mu_fy2026q4_conflict_confirmation.yaml` **없음**(지시대로) · `forecast/reports/mu_report_*` 0개 |

## 2. 지적

| # | 등급 | 내용 | 요구 |
|---|---|---|---|
| **F-1** | 낮음(절차) | `charts.py`가 수정됐다(보고 파일 목록 1행). 그러나 부록 R4-4의 "수정" 목록에는 `charts.py`가 없다. 현재 코드로 보면 변경은 PNG 원자적 쓰기(temp → `os.replace`)로 추정되며, 계획 D7 허용 경로 안이라 산출물 위험은 낮다. 다만 "허용 경로 밖 신규 변경 0건" 보고와 부록 목록이 어긋난다 | 변경 내용(diff 요지)과 사유를 회신에 적는다. 되돌릴 필요는 없다 |
| **F-2** | **중간 — E2-B 전 필수** | `gate_g12c_conflict`가 **문안 자체를 검사하지 않는다.** 표지·말미는 확인 시각 문자열이 있는지만 보고, 푸터는 `rendered[locale]["conflict_short"]`로 **넘겨받은 문자열**이 각 쪽에 있는지만 본다. 재현: 표지 = `"random text <시각>"`, `conflict_short = "x"`, 쪽 텍스트 = `["x"]`로 넣으면 **G-12c가 통과한다.** 실제 렌더 경로는 올바른 문안을 넣지만, 게이트가 회귀를 잡지 못한다 | 기대 문자열을 게이트 안에서 **i18n 키 + 확인 레코드로 직접 조립**한다(`disclaimer.conflict`에 시각을 채운 전체 문장, `disclaimer.conflict_short`). 그 문자열이 표지·말미·**PDF에서 추출한 각 쪽 텍스트**에 있는지 검사한다. 위반 주입 테스트 2건을 추가한다: 표지에 시각만 있고 문장이 없음 → 실패, 푸터에 다른 문자열 → 실패 |
| **F-3** | **중간 — E2-B 전 필수** | 운영 i18n 템플릿에 **발행주식수 기준일이 fact_id로 박혀 있다**: `market.shares_outstanding.2026-09-01.CITED`, `meta.shares_date.2026-09-01.CITED`. 계획 §4-5에서 주식수는 "가장 최근 공시 표지의 as-of 날짜"라 E2-B 전에는 알 수 없는 값이다. 2026-09-01은 fixture 날짜로 보인다. 실제 날짜가 다르면 E2-B에서 fact를 찾지 못하거나, 날짜를 이 값에 맞추는 역방향 압력이 생긴다 | 템플릿 fact_id는 날짜 비의존으로 둔다(예: `market.shares_outstanding.CITED` + 날짜는 `meta.shares_date.CITED`의 **값**). 또는 빌드 시 manifest에서 해석한다. 날짜 문자열이 i18n에 있는지는 G-7로 검사한다. 기준 주가일 `2026-10-01`은 계획이 고정한 날짜라 예외다 |

## 3. 판정 이유 요약

- 6개 항목 모두 계획 rev-4의 식·조건과 일치하고, 재고 원문 값과 재고일수 계산을 독립적으로 재현했다.
- F-2는 J-2(이해관계 고지)를 지키는 fail-closed 게이트가 **형식만** 검사한다는 결함이다. 발행 통제의 핵심이므로 E2-B 입력 게이트 ⑤("HANDOFF 부록 구현 완료")의 충족 조건으로 둔다.
- F-3은 E2-B 첫 실행에서 발견될 결함이지만, 그때 고치면 가격 캡처 뒤 일정이 밀린다. 지금 고친다.

## 4. 호스트 재확인 (Jiwon)

이 환경은 git 체크아웃·전체 데이터 캐시가 없어 아래를 재현하지 못했다. 호스트에서 한 번 실행해 결과를 알려 달라.

```powershell
chcp 65001 > $null; $env:PYTHONIOENCODING='utf-8'
python -m pytest forecast/tests/ -q
python forecast/scripts/verify_anchor.py
pytest forecast/tests/test_frozen_integrity.py -q -s
```

## 5. Codex에게 (회신 메시지)

1. F-1 — `charts.py` 변경 요지와 사유
2. F-2 — `gate_g12c_conflict` 수정 + 위반 주입 테스트 2건
3. F-3 — 날짜 비의존 fact_id 또는 빌드 시 해석 + G-7 검사
4. 변경 파일 SHA · `test_mu_report.py` 결과 · 전체 테스트 결과 · NUL 스캔

위 1–4를 확인하면 E2-A′를 **PASS**로 닫고, 계획 §6 E2-B 입력 게이트 ⑤를 충족으로 기록한다.
