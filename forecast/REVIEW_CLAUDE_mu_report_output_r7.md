# REVIEW — Claude: MU 리포트 DRY RUN r7 (r6 종결)

- 검토자: Claude (E3) · 검토일: 2026-09-29 KST
- 대상: `logs/_mu_report_runs/dryrun_20260929T091023Z/` — KO PDF `8cc41b9ed43e…`, EN PDF `edd8adffdabf…`. 쪽 PNG 5·7·9·11쪽(`…_ko_page_07.png` `7b7f8f00…`, `_09` `3d0854d4…`, `_11` `61bb40cb…`)을 직접 확인했다.
- 변경 파일 11개의 SHA가 Codex 보고와 **일치**한다. `forecast/**` NUL clean. `forecast/reports/`·`forecast/inputs/` 변경 0건.
- 전체 판정: **PASS — 발표 전 내부 리허설 종결.**
- 🔴 투자 자문 아님. This review is not investment advice.

## 1. r6 지적 확인

| # | 확인 | 판정 |
|---|---|---|
| R-1 | ⑧(9쪽)이 FY23A–FY25A 연간 3계열 막대 + FY26A-8K·FY27E·FY28E 자리로 바뀌었다. 막대 값을 비율 표와 대조했다(조정 FCF −5,407 / 436 / 3,673 · 순 capex 6,966 / 8,071 / 13,852 · SCA 미조정 순현금 −2,892 / −4,245 / −2,641) | 해소 |
| R-2 | 7쪽 NAND 비트 출하 = `mid-single-digit percentage range`. 추출본 `prepared_remarks.json`에서도 `low-single-digit`·`mid-single-digit`로 원문과 같다 | 해소 |
| R-3 | 11쪽 중복 재고일수 표 삭제 | 해소 |
| R-4 | 그림 번호가 등장 순서다(5쪽 그림 2, 7쪽 그림 4, 9쪽 그림 7) | 해소 |
| R-5 | 캡션이 `그림 N. <제목> — 단위 · 출처 · 기준일 · 회계기준` 형식 | 해소 |
| R-6 | ④ 패널별 축 제목(%, USD per share), x축 제목은 아래 패널에만 | 해소 |
| R-7 | 텍스트 열 왼쪽·숫자 열 오른쪽 정렬 | 해소 |
| R-8 | 분기 라벨 `FQn-YY` 통일(5·7쪽) | 해소 |
| R-9 | FY23A ROE = −12.4%(FY22 말 자본을 FY23 10-K 비교 열에서 추출). 값의 크기가 FY23 순손실 ÷ 평균 자본과 맞는다 | 해소 |
| R-10 | ⑦ 자리 패널 축 제목 수정(보고 기준, 이번 검수 범위 밖 쪽) | 보고 수용 |

## 2. E2-B로 넘길 메모 (차단 아님)

1. ⑧·비율 표의 행 이름 `조정 전 순현금`은 계획 §4-3 라벨 "순현금(SCA 예치금 미조정)"으로 맞춘다. `조정 FCF`의 "조정"과 겹쳐 오독될 수 있다.
2. r2 §3의 C-1(빌드 경로 게이트 완결성)·C-2(의도된 KO/EN 차이 allowlist)는 계속 E2-B 조건이다.
3. 리허설 폴더 `logs/_mu_report_runs/dryrun_*`는 배포하지 않는다. 본판 산출물은 E2-B에서 `forecast/reports/mu_report_fy2026q4_ed1_*`로 새로 만든다.
