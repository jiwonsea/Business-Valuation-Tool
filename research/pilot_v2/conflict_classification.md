# 재작성 충돌 계정별 분류표 (파일럿 v2)

- 스냅샷 수집일: 2026-07-18 · 계약: HANDOFF_CODEX_next_scope_decision_2026-07-17 §6.3
- 값 단위: 백만원(MKRW). original = FY 연차보고서 당기(thstrm), following comparative = 익년 연차보고서 전기(frmtrm).
- classification ∈ {restatement, mapping_error, unit_error, unresolved} — 규칙 기반, 판단 불가 시 unresolved(추측 금지).

| company | account | FY | original | following comp. | diff | diff% | class | evidence |
|---|---|---:|---:|---:|---:|---:|---|---|
| SK hynix | assets | 2019 | 64,789,494 | 65,248,350 | 458,856 | 0.71 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — BS: 64,789,494 -> 65,248,350 |
| SK hynix | equity | 2019 | 47,943,195 | 47,935,882 | -7,313 | -0.02 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — BS: 47,943,195 -> 47,935,882 |
| SK hynix | interest_expense | 2019 | 1,514,869 | 1,531,417 | 16,548 | 1.09 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — CIS: 1,514,869 -> 1,531,417 |
| SK hynix | liabilities | 2019 | 16,846,299 | 17,312,468 | 466,169 | 2.77 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — BS: 16,846,299 -> 17,312,468 |
| SK hynix | net_income | 2019 | 2,016,391 | 2,009,078 | -7,313 | -0.36 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — CIS: 2,016,391 -> 2,009,078; SCE: 2,013,288 -> 2,005,975; multi-candidate hazard (account_nm-only lookup also matches other statements): original[당기순이익(CIS)=2,016,391 / 당기순이익(SCE)=2,013,288 / 당기순이익(SCE)=2,016,391 / 당기순이익(SCE)=3,103 / 당기순이익(SCE)=2,013,288] following[당기순이익(CIS)=2,009,078 / 당기순이익(SCE)=2,005,975 / 당기순이익(SCE)=2,005,975 / 당기순이익(SCE)=3,103 / 당기순이익(SCE)=2,009,078] |
| SK hynix | op | 2019 | 2,712,718 | 2,719,179 | 6,461 | 0.24 | restatement | unit=MKRW; original filing rcept_no=20200330004441 (FY2019 annual), following filing rcept_no=20210330000776 (FY2020 annual); statement-matched pair(s) differ in the following filing — CIS: 2,712,718 -> 2,719,179 |
| SK hynix | assets | 2021 | 96,386,474 | 96,346,525 | -39,949 | -0.04 | restatement | unit=MKRW; original filing rcept_no=20220322000590 (FY2021 annual), following filing rcept_no=20230321001209 (FY2022 annual); statement-matched pair(s) differ in the following filing — BS: 96,386,474 -> 96,346,525 |
| SK hynix | liabilities | 2021 | 34,195,416 | 34,155,467 | -39,949 | -0.12 | restatement | unit=MKRW; original filing rcept_no=20220322000590 (FY2021 annual), following filing rcept_no=20230321001209 (FY2022 annual); statement-matched pair(s) differ in the following filing — BS: 34,195,416 -> 34,155,467 |
| LG Electronics | interest_expense | 2020 | 1,116,043 | 892,751 | -223,292 | -20.01 | restatement | unit=MKRW; original filing rcept_no=20210316000661 (FY2020 annual), following filing rcept_no=20220316000886 (FY2021 annual); statement-matched pair(s) differ in the following filing — IS: 1,116,043 -> 892,751 |
| LG Electronics | op | 2020 | 3,194,987 | 3,905,108 | 710,121 | 22.23 | restatement | unit=MKRW; original filing rcept_no=20210316000661 (FY2020 annual), following filing rcept_no=20220316000886 (FY2021 annual); statement-matched pair(s) differ in the following filing — IS: 3,194,987 -> 3,905,108; account label alias changed '영업이익' -> '영업이익(손실)' (both map to the same key) |
| LG Electronics | revenue | 2020 | 63,262,046 | 58,057,908 | -5,204,138 | -8.23 | restatement | unit=MKRW; original filing rcept_no=20210316000661 (FY2020 annual), following filing rcept_no=20220316000886 (FY2021 annual); statement-matched pair(s) differ in the following filing — IS: 63,262,046 -> 58,057,908 |
| LG Electronics | interest_expense | 2021 | 690,401 | 660,571 | -29,830 | -4.32 | restatement | unit=MKRW; original filing rcept_no=20220316000886 (FY2021 annual), following filing rcept_no=20230317000955 (FY2022 annual); statement-matched pair(s) differ in the following filing — IS: 690,401 -> 660,571 |
| LG Electronics | op | 2021 | 3,863,774 | 4,057,997 | 194,223 | 5.03 | restatement | unit=MKRW; original filing rcept_no=20220316000886 (FY2021 annual), following filing rcept_no=20230317000955 (FY2022 annual); statement-matched pair(s) differ in the following filing — IS: 3,863,774 -> 4,057,997 |
| LG Electronics | revenue | 2021 | 74,721,629 | 73,907,984 | -813,645 | -1.09 | restatement | unit=MKRW; original filing rcept_no=20220316000886 (FY2021 annual), following filing rcept_no=20230317000955 (FY2022 annual); statement-matched pair(s) differ in the following filing — IS: 74,721,629 -> 73,907,984 |
| LG Electronics | interest_expense | 2023 | 1,425,480 | 1,381,297 | -44,183 | -3.1 | restatement | unit=MKRW; original filing rcept_no=20240318000755 (FY2023 annual), following filing rcept_no=20250317001029 (FY2024 annual); statement-matched pair(s) differ in the following filing — IS: 1,425,480 -> 1,381,297 |
| LG Electronics | op | 2023 | 3,549,074 | 3,653,294 | 104,220 | 2.94 | restatement | unit=MKRW; original filing rcept_no=20240318000755 (FY2023 annual), following filing rcept_no=20250317001029 (FY2024 annual); statement-matched pair(s) differ in the following filing — IS: 3,549,074 -> 3,653,294 |
| LG Electronics | revenue | 2023 | 84,227,765 | 82,262,664 | -1,965,101 | -2.33 | restatement | unit=MKRW; original filing rcept_no=20240318000755 (FY2023 annual), following filing rcept_no=20250317001029 (FY2024 annual); statement-matched pair(s) differ in the following filing — IS: 84,227,765 -> 82,262,664 |

## 분류 합계

- 총 충돌: **17건**
- restatement: 17건
- mapping_error: 0건
- unit_error: 0건
- unresolved: 0건
- 합계 검증: 17 == 17 → OK
