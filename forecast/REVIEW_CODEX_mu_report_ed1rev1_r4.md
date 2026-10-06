# MU FY2026 Q4 ed1 개정 1 — R23 검증 r4

판정: **CHANGES REQUESTED — 자동 게이트 62 PASS / 0 FAIL, 잔여 표시 문제 2건(§2.2). E4 보류.**

투자 자문이 아니다. R23-1·W1–W11·서술 r4 연결을 구현하고 발행 렌더 **1회/최대 2회**를 실행했다. 남은 표시 문제는 수정·재렌더하지 않고 목록으로 보고한다. 서술 원문·수치·추정 규칙·이해관계 레코드·git은 수정하지 않았다. 테스트용 임시 fixture PDF/차트, 완성 PDF의 이미지 변환, XLSX 읽기 전용 미리보기는 발행 렌더 횟수에 포함하지 않는다.

## 1. R23-1 Bold 오탐 수정

원인: pdfplumber의 char 하나가 `fl` 두 글자를 담는 합자인데, 종전 검사는 문자열 offset을 char 배열 offset으로 사용했다. 앞선 합자 및 목표 내부 합자 이후 폰트 범위가 한 글자씩 어긋났다.

변경: 각 char.text를 글자 단위로 확장하면서 **원래 char의 fontname을 각 글자에 보존**하고, 공백을 제외한 목표 문자열과 대응 글자의 Bold 폰트를 검사한다. 게이트를 우회하거나 문자열 존재 검사로 약화하지 않았다.

| 검증 | 결과 |
|---|---|
| 수정 전 신규 회귀 기준선 | 5 FAIL / 1 PASS(Bold 양성·표 분리·변경표 분류 KO/EN·신규 절 계약 실패) |
| 수정 전 실제 R22 EN PDF | `Strategic customer agreements (SCAs) put a price floor under part of revenue.` → `PDF text lacks a real Bold font run`, exit 1 |
| 수정 후 **같은 R22 PDF 바이트** | 같은 문장 PASS, p.6, exit 0. 원본 PDF SHA `0f00d5a4ff668526a77aeff0cc1c3d18c87ca7b34b7dd0e110a40bdc3d5d4523` |
| 합자 양성/음성 | 목표 앞 및 목표 내부에 fl 합자 배치. Bold이면 PASS, Regular이면 GateError. 두 경우 모두 통과 |
| 새 KO/EN PDF | 워드마크·강세/약세 소제목·claim·리스크 **30/30** Bold 대상 통과 |

R23 시작·종료의 보호 입력을 다시 SHA-256 대조했다.

| 경로 | SHA-256 | 결과 |
|---|---|---|
| forecast/HANDOFF_CODEX_mu_report_exec.md | `f36d90038668986afe2c342c8cf4dd9d4979b645d190a9a38e20320c905877e5` | 일치·불변 |
| forecast/inputs/mu_fy2026q4_narrative_ed1.yaml | `8fee9e26f59222ae062a83c450759e91fb90f6a69e1cbceea156f549478bbec0` | 일치·불변 |
| forecast/inputs/mu_fy2026q4_report_assumptions.yaml | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` | 일치·불변 |
| forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` | 일치·불변 |

HEAD `9e4c667b1750e129027a31b730ed338289f0e9b4` 불변. 기존 무관한 CLAUDE.md 수정 및 다른 작업의 untracked 파일은 건드리지 않았으며 E4 목록에서도 제외했다. RLE 구현 파일은 이번 diff에 없고, canonical fact **878/878 객체 전체 일치**(raw_value·display·단위·기간·basis·source_id·status·lineage/extraction 포함), 추가/삭제/변경 **0**. `logs/_mu_report_runs/ed1_rev0_committed/` **25/25** 보존본을 R20 원본 SHA 목록과 다시 비교해 모두 일치했다(전체 목록은 리뷰 r1 §1).

## 2. W1–W11 조치·증거

### 2.1 항목별 결과

| ID | 구현·검증 결과 | 최종 PDF 쪽·150dpi 증거 |
|---|---|---|
| W1 | 시장 데이터 기준 3행에 USD/share · 2026-10-01 / million shares · FQ4 A-8K / USD million · 주가 × 주식수(EN price × shares) 복원. 값 셀 오른쪽 정렬·통화 기호 제거 유지. | [KO 1](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-01.png) · [EN 1](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-01.png) |
| W2 | nowrap을 숫자 td에만 적용, th 줄바꿈 허용. 실제 페이지 헤더 84개/언어의 TextBox가 자기 셀 안에 들어옴을 검사. FY26E PREREG_A와 FY26A A-8K 겹침 및 SCORED·배수 긴 헤더 잘림 해소. | [KO 14](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-14.png) · [EN 10](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-10.png) · [KO 17](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-17.png) · [EN 20](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-20.png) |
| W3 | 비율표도 손익·BS·CF와 같은 † 사전등록 범위 / ‡ RLE 미추정 범위 각주 기호 사용. | [KO 17](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-17.png) · [EN 19](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-19.png) |
| W4 | post-print-changes 판별을 일반 Item 표보다 앞에 배치. colgroup 적용: 규칙 16/28/20/10/26%, 변경 13/22/23/35/7%(사유 최대, 근거 쪽 가운데). 표 오른쪽 543.9213pt < 549.9pt. M1/X1 표시를 FQ1 GAAP GM/opex 가이던스로 풀이(아래 설명). | [KO 23](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-23.png) · [EN 25](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-25.png) · [KO 22](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-22.png) · [EN 24](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-24.png) |
| W5 | C11 y축 31.5–34.0, 축 생략 slash 표시, 시작/끝·기여 라벨 한 줄. 라벨 상호·막대 bbox 교차 0. raw 및 signed 기여 값 불변. | [KO 8](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-08.png) · [EN 9](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-09.png) |
| W6 | C15 데이터 라벨 정수 반올림, +114,291 / +14,382 / −2,189 등 표시. raw 소수 유지. 라벨 상호·막대 bbox 교차 0. | [KO 17](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-17.png) · [EN 19](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-19.png) |
| W7 | KO 상단 초과/범위 안/하단 미달/라벨 없음(가이던스 없음), EN Above high/In range/Below low/No label(no guidance) 표시. G-3f raw 인용 보존, G-15b는 두 언어의 원시 판정 코드 노출 거부. | [KO 9](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-09.png) · [EN 10](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-10.png) |
| W8 | 빈 줄에서 Markdown 표 닫기. 배수 표 아래 독립 한 줄 Trailing P/B: 9.10x · A-8K로 분리. 두 번째 헤더가 같은 표에 붙지 않음. | [KO 20](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-20.png) · [EN 22](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-22.png) |
| W9 | C6 FY26 PREREG_A·FY26A x축에 (53주)/(53 weeks) 병기. plot의 기존 53w 주석 제거. | [KO 13](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-13.png) · [EN 14](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-14.png) |
| W10 | C16 내부 암호문 부제 제거. 캡션 및 서술의 26건·2030년·35% 설명 유지. | [KO 5](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-05.png) · [EN 6](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-06.png) |
| W11 | 전 axes/twin/colorbar의 범례·tick을 8.5pt로 통일. PDF 너비를 보수적으로 환산한 최소 8.07643pt(요구 ≥7pt). 32개 차트 모두 검사. 긴 C8 범례는 세 열 대신 한 열. | [KO 3](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-03.png) · [EN 4](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-04.png) · [KO 7](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-07.png) · [EN 8](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-08.png) |

W4의 예시 “FQ1 실제 GM”을 그대로 쓰지 않은 이유: M1/X1은 **FQ1 가이던스 앵커**이므로 실제값이라는 라벨은 사실 오류를 만든다. 따라서 GAAP GM/opex **가이던스**로만 표시 풀이했다. YAML 원안·변경·사유·수치·규칙은 그대로다.

W5 EPS 원시 값: 32.57 → 32.87, +0.84 / −0.73 / +0.10 / +0.09 = +0.30. W6 영업이익 raw는 99,340 / +114,290.71230100188 / +14,382.255672305633 / −2,189 / 225,823.9679733075이며 표시만 정수로 반올림했다.

전 쪽 시각 확인: **KO 24/24, EN 26/26**, 차트 **32/32**. 150dpi 원본은 `F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/`의 `ko-01.png…ko-24.png`, `en-01.png…en-26.png`; 페이지 모음 13장 및 차트 모음 8장도 모두 확인했다. Poppler nameToUnicode 설치 경로 경고가 있었지만 변환 exit 0, 누락 페이지 0이며 글리프 missing 경고 게이트도 통과했다.

C14는 pin 원천 12분기 모두 가용, **제외 분기 없음**. 원천 누락 시 빈칸/NaN·추정/보간 금지 및 제외 사유 각주 계약 유지. C10 구간 환산표는 **J(판단)**임을 KO/EN 차트 각주에 그대로 유지한다.

### 2.2 남은 표시 문제 — 수정·추가 렌더하지 않음

| ID | 위치 | 관찰 | 범위·판정 |
|---|---|---|---|
| VIS-1 | EN p.25 발표 후 변경표 | 좁고 가운데 정렬된 마지막 헤더가 `Sourc / e page`로 단어 중간 줄바꿈됨. 글자 누락·셀 밖 잘림·겹침은 없지만 어색함. | W4 열 비율·가운데 정렬·폭 계약 및 W2 bbox 검사는 PASS. 시각적 완성도는 추가 검토 필요. [증거](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-25.png) |
| VIS-2 | XLSX Summary A1 | 워드마크 제목의 윗부분이 행 높이 경계에서 조금 잘려 보임. 문자열 자체는 완전하고 바뀌지 않음. | **NOTICED BUT NOT TOUCHING:** R22 XLSX와 동일 SHA의 기존 표시 문제. R23 수치/서술 변화나 새 결함은 아님. [읽기 전용 미리보기](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/summary_xlsx.png) |

자동 게이트가 PASS라고 시각상 완전 PASS로 결론 내리지 않는다. 사용자 지시 “남는 시각 결함은 목록만 보고”에 따라 두 번째 발행 렌더는 사용하지 않았다.

## 3. 서술 r4 신규 절·숫자 경계

| 항목 | 연결·검증 | 쪽·증거 |
|---|---|---|
| business_structure | KO/EN **각 4문단**을 5절 i18n 도입문 다음, 그림 앞에 원문 그대로 배치. 마지막 해석/Reading 문단은 기존 GM 해석 문단과 같은 p 스타일. | [KO 11](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-11.png) · [EN 12](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-12.png) |
| methodology | KO/EN **각 5문단**을 부록 약어 목록 뒤 “방법론과 정보 경계”에 원문 그대로 배치. ed1의 종전 고정 두 줄 및 중복 FY27 consensus UNAVAILABLE 고정문만 제외. fixture/DRYRUN 고정문 경로 유지. | [KO 24](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-24.png) · [EN 26](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-26.png) |
| 촉매 두 번째 행 | r4 YAML 변경 문구를 기존 촉매 연결로 그대로 렌더, G0-A/B 내부 코드 미노출. | [KO 21](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/ko-21.png) · [EN 23](F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/en-23.png) |
| 바인딩 | 새 절을 NEW_SECTIONS 및 서술 계약·KO/EN 숫자 parity에 추가. fact 바인딩 **19개 유지**, 새 fact 생성 0. | G-10·G-15 PASS |
| 회사 진술 숫자 | 회사 소개의 73%와 같은 **company statement + 본문 준비문 쪽수/src 표기** 경계로 취급. 준비문 p.4·p.7–8 등 원문 근거 병기를 그대로 렌더. 회사 진술 숫자에 임의 manifest fact 토큰을 붙이지 않음. | KO/EN 절별 numeric multiset 일치; EN의 18.0을 18.1로 바꾼 음성 테스트는 numeric parity 실패 |
| meta.sections | 렌더러는 해당 메타 목록을 사용하지 않음. YAML 수정 없이 계약의 NEW_SECTIONS로 새 절 포함. | 원문 SHA 불변 |

서술 오류를 고친 것이 아니라 사용자가 제공한 r4를 연결했다. narrative YAML은 위 SHA `8fee9e26…bec0` 그대로다. FY28E 매출 = FY27E 매출은 **A8 base 0.0**의 결과이며 A3 때문이 아니다; 기존 금액·규칙 불변.

## 4. 렌더·게이트·테스트

### 4.1 발행 렌더

```powershell
python -X utf8 -m forecast.scripts.mu_report.build --phase E2B --edition 1
```

| 항목 | 결과 |
|---|---|
| 실제 시작 | **2026-10-05T21:43:06.707094+09:00** |
| 기한 | 2026-10-06T19:07:00+09:00 이전 — 충족 |
| 이해관계 레코드 | not_held / ed1 / 2026-10-05T19:07:00+09:00, 시작 시 유효; 수정 없음 |
| 레코드 git blob | `5248dd717931e990b427df597b7e433a13f359a4` |
| 발행 횟수·종료 | **1/2**, exit 0, 자동 결과 PASS |
| runtime | `logs/_mu_report_runs/e2b_20261005T214306+0900.json` |
| runtime SHA-256 | `8e739728fbcef45a130db9045a33bed4bbdf299618b2089b02ff664c5ada82c6` |

전체 E2B 사전 게이트 통과: G-1/2/3/3f/7/9/12/14/18/19/20, G-13/13b/13c/16 데이터 계약, G-10/11/15/15b/23 메모리 검사 및 G-17 라벨 설정. 렌더 전 NOT_APPLICABLE/DEFERRED/PENDING 항목은 아래 실제 산출물 검사에서 실행했다. **G-3f는 unchanged SCORED raw manifest를 검사**하며 번역된 표시 코드로 바꾸지 않았다.

렌더 후 **62 실행 단위 PASS**, failures=`{}`:

| 번호 | 실행 단위 | 결과 |
|---|---|---|
| 1 | G-10 narrative contract | PASS |
| 2 | G-11 ed1 placeholders | PASS |
| 3 | G-12b disclaimers | PASS |
| 4 | G-12c conflict | PASS |
| 5 | G-13 charts en | PASS |
| 6 | G-13 charts ko | PASS |
| 7 | G-13b chart identity en | PASS |
| 8 | G-13b chart identity ko | PASS |
| 9 | G-13c chart semantics en | PASS |
| 10 | G-13c chart semantics ko | PASS |
| 11 | G-15 parity | PASS |
| 12 | G-15b localized UI | PASS |
| 13 | G-16 caption en/01_quarterly_revenue_margin | PASS |
| 14 | G-16 caption en/02_business_unit_mix | PASS |
| 15 | G-16 caption en/03b_guidance_beat_history | PASS |
| 16 | G-16 caption en/04_beat_history | PASS |
| 17 | G-16 caption en/05_scenario_fan | PASS |
| 18 | G-16 caption en/06_annual_income | PASS |
| 19 | G-16 caption en/07_valuation_heatmap | PASS |
| 20 | G-16 caption en/08_cash_flow_capex_net_cash | PASS |
| 21 | G-16 caption en/09_gm_beat_compression | PASS |
| 22 | G-16 caption en/10_price_bit_ranges | PASS |
| 23 | G-16 caption en/11_eps_error_waterfall | PASS |
| 24 | G-16 caption en/12_fq1_guidance_comparison | PASS |
| 25 | G-16 caption en/13_scenario_sensitivity_eps | PASS |
| 26 | G-16 caption en/14_opex_net_capex_trend | PASS |
| 27 | G-16 caption en/15_operating_income_waterfall | PASS |
| 28 | G-16 caption en/16_sca_structure | PASS |
| 29 | G-16 caption ko/01_quarterly_revenue_margin | PASS |
| 30 | G-16 caption ko/02_business_unit_mix | PASS |
| 31 | G-16 caption ko/03b_guidance_beat_history | PASS |
| 32 | G-16 caption ko/04_beat_history | PASS |
| 33 | G-16 caption ko/05_scenario_fan | PASS |
| 34 | G-16 caption ko/06_annual_income | PASS |
| 35 | G-16 caption ko/07_valuation_heatmap | PASS |
| 36 | G-16 caption ko/08_cash_flow_capex_net_cash | PASS |
| 37 | G-16 caption ko/09_gm_beat_compression | PASS |
| 38 | G-16 caption ko/10_price_bit_ranges | PASS |
| 39 | G-16 caption ko/11_eps_error_waterfall | PASS |
| 40 | G-16 caption ko/12_fq1_guidance_comparison | PASS |
| 41 | G-16 caption ko/13_scenario_sensitivity_eps | PASS |
| 42 | G-16 caption ko/14_opex_net_capex_trend | PASS |
| 43 | G-16 caption ko/15_operating_income_waterfall | PASS |
| 44 | G-16 caption ko/16_sca_structure | PASS |
| 45 | G-17 corrected net-cash label | PASS |
| 46 | G-17 labels en | PASS |
| 47 | G-17 labels ko | PASS |
| 48 | G-17b consensus en | PASS |
| 49 | G-17b consensus ko | PASS |
| 50 | G-18 hygiene | PASS |
| 51 | G-21 formats | PASS |
| 52 | G-23 availability audit | PASS |
| 53 | G-24 PDF/XLSX markup and labels | PASS |
| 54 | G-25 cover dates | PASS |
| 55 | G-4 inventory days | PASS |
| 56 | G-5 trailing P/B | PASS |
| 57 | G-6 market data en | PASS |
| 58 | G-6 market data ko | PASS |
| 59 | G-8 theme en | PASS |
| 60 | G-8 theme ko | PASS |
| 61 | R22 presentation/glyph/bbox/Bold | PASS |
| 62 | R23 header/table/font geometry | PASS |

R23 실제 레이아웃: 헤더 **84개/언어**(페이지 반복 헤더 포함), 규칙표 KO22·23 / EN24·25, 변경표 KO23 / EN25의 오른쪽 모두 **543.9212598pt ≤ 549.9pt**. bbox 검사는 폰트 굵기·단어 중간 줄바꿈의 미관까지 판정하지 않으므로 §2.2를 별도로 남겼다.

G-23 required_available_failures=`[]`. 기존 unavailable 집계는 문자 그대로 UNAVAILABLE 위치 수이며 **—‡ 셀 전수**로 해석하지 않는다. required 렌더 셀 대조와 878 fact 불변 검사는 별도 통과.

### 4.2 테스트

```powershell
python -X utf8 -m pytest forecast/tests/ -q -m 'not network' -p no:cacheprovider --basetemp=forecast/tests/.tmp_r23_postrender
python -X utf8 -m pytest forecast/tests/test_disclosure_loader.py::test_fetch_dart_mdna_nonempty -q -m network -p no:cacheprovider --basetemp=forecast/tests/.tmp_r23_postrender_network
```

최종 렌더 후 현재 코드 전체 회귀: **559 passed / 3 skipped / 1 deselected / 1 xfailed**, 303.25초. 분리한 network 검사: **1 passed**, 0.75초. 합계 **560 PASS**, FAIL 0. 별도 신규 R23 파일 검사도 15 PASS.

skip 3건: Windows symlink 생성 권한 부재, Windows process-group 의미론 부재, gitignored derived EDGAR cache 부재. xfail 1건: 기존 `edgar_fetcher.model_label_for_period`의 FYE-August Q1 라벨 문제 — **NOTICED BUT NOT TOUCHING**, R23 범위 밖. network deselect 1건은 위 명시 실행으로 보완했다. FROZEN은 수정하지 않았고 전수 무결성 테스트도 통과.

신규 R23 테스트 **15개**: 합자 Bold 양성/음성(2), 표 blank-line 분리(1), 변경표 class·bbox KO/EN(2), 신규 절 계약(1), nowrap 헤더 overflow 거부(1), 실제 r4 문단·단위·판정 번역·각주 KO/EN(2), 완성 표 bbox KO/EN(2), 원시 판정 코드 거부(1), 회사 진술 숫자 parity 거부(1), C11/C15 라벨 상호·막대 교차·zoom/반올림(2). 기존 R22 차트 bbox 검사에도 전 범례/tick 최소 PDF 크기와 C6 두 53주 x축 라벨·C16 암호문 제거 확인 추가.

기존 E2-A/DRYRUN·렌더·RLE 실제 YAML 재현·FY26 재무 항등식·F1/F2/F5 표시 문자열·FROZEN 무결성 테스트를 제외하지 않았다. 내재 배수 분리 과정의 임시 fixture 쪽수 회귀는 독립 한 줄 P/B 표시로 원래 4쪽 계약을 보존했고, 구형 시장 기준 문자열 assertion만 R23의 승인된 단위 문자열로 갱신했다(수치 assertion 유지).

XLSX는 기존 파이프라인 산출물을 SpreadsheetFile로 **읽기 전용** import/inspect/render했다(재저장·재계산 안 함). Summary/Facts 두 시트, Facts **878행**, 수식 0, spreadsheet 오류 문자열 매치 0. Summary의 ed1 개정 1·면책·이해관계·자료 기준일 확인. XLSX SHA는 R22와 동일하여 수치·문구·서식도 바뀌지 않았다. 기존 XLSX 제목 높이 문제는 §2.2에만 보고한다.

## 5. 산출물 SHA·쪽수

| 경로 | SHA-256 | 크기(byte) | 쪽수 |
|---|---|---:|---:|
| forecast/reports/mu_report_fy2026q4_ed1_en.html | `fcaa764101f150e929c417f9f811e126bfe90dfa3bf43dbd2b171de1c1c700e0` | 65654 | — |
| forecast/reports/mu_report_fy2026q4_ed1_ko.html | `76012e5c0c44123b89f7f2ea111f819a60d481bef520b0e4ee6a2c1c21b294ca` | 65611 | — |
| forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` | 5546 | — |
| forecast/reports/mu_report_fy2026q4_ed1_manifest.json | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` | 458631 | — |
| forecast/reports/mu_report_fy2026q4_ed1_en.md | `a089891ed3d00b5956dd1a7fef449363b365c6224ef09d04f0e2d4ec6c514524` | 41546 | — |
| forecast/reports/mu_report_fy2026q4_ed1_ko.md | `f9e1083fed2618e922c4f12770b6e71a66a465bd6bea045d5b3f26044078843e` | 41591 | — |
| forecast/reports/mu_report_fy2026q4_ed1_en.pdf | `c2991b9830d0b25480dd74464cc7b32f77cd44236767154a21bf403d88b0aecb` | 619483 | 26 |
| forecast/reports/mu_report_fy2026q4_ed1_ko.pdf | `a9ba6060ab7c357fd355d34de649030775e5a03745f9d517027297e05b215e44` | 607179 | 24 |
| forecast/reports/mu_report_fy2026q4_ed1_data.xlsx | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` | 40808 | — |

16종 × KO/EN = **32 PNG**의 경로·SHA는 아래 E4 목록에 전수 기록했다. 파일명(C-ID)은 유지, 본문 첫 등장 그림 1–16은 KO/EN 동일, 각 차트 한 번만 배치하는 계약도 통과했다.

## 6. E4 후보 목록 — 실행하지 않음

**62개 후보**: 아래 SHA를 기록한 61개 + 이 리뷰 r4 자체 1개. R20–R23 누적 변경/신규 파일 기준이며 narrative r4·핸드오프·리뷰 r1–r4·이해관계 레코드를 포함한다. **git 쓰기 없음. 최종 판정 CHANGES REQUESTED이므로 E4 진행 승인이 아니다.**

gitignore 열은 현재 규칙을 `git check-ignore --no-index`로 읽기 확인한 결과다. YES인 D7 산출물 5개도 후보지만 자동 stage 대상이 아니다; 향후 별도 승인 시 명시 포함 여부를 확인해야 한다. 트래킹된 파일에도 ignore 규칙이 매치될 수 있으므로 규칙 매치와 현재 tracked 여부는 같은 뜻이 아니다.

| 번호 | 후보 경로 | SHA-256 | gitignore |
|---|---|---|---|
| 1 | forecast/scripts/mu_report/build.py | `4a631e8058b99663df468c907807188dc30770c2eb1a9c58810894d28bf5d4aa` | NO |
| 2 | forecast/scripts/mu_report/charts.py | `b8ccfa36a719261890fc572dc2f1d4f5b7aa84036794b436fb07c04154127940` | NO |
| 3 | forecast/scripts/mu_report/gates.py | `9b6b2f980f12d599c9cfd8774081345e6f302673af61a42453b2c552f789bf9e` | NO |
| 4 | forecast/scripts/mu_report/i18n/ko.yaml | `9094af9374df44a030638b9417526f964d11691c7c54ce1551cbffe992a268c3` | NO |
| 5 | forecast/scripts/mu_report/i18n/en.yaml | `0fcecbce01bd21ab3143c8e13b399cd53ae4580afe840b33e189c1f8f1d199cb` | NO |
| 6 | forecast/scripts/mu_report/narrative.py | `ba7efa1de308529b643aa46ce5a465cb463dffe9afa53db85d081b1ef16fa813` | NO |
| 7 | forecast/scripts/mu_report/render.py | `9d8ce76a0a7d4e8f905004b41d099da9cfa0d39f33003093f2f9341cc3af66e7` | NO |
| 8 | forecast/scripts/mu_report/revision.py | `1fd81ddb250f8a9eede0eb2f8075d9a9486c87dc98c9e975ce98dd052c33a4f0` | NO |
| 9 | forecast/scripts/mu_report/theme.py | `a4348a379bfe532f0951731e9f7cefba8759cc7c9c87453695cc65036f85eacf` | NO |
| 10 | forecast/scripts/mu_report/presentation.py | `3d74cba4ae0c238b9219d196b8caa6f43e38df734d78a0f7a0bc6bd5fdc8acfc` | NO |
| 11 | forecast/tests/test_mu_report.py | `23ffeab7ed3243f1c4476685d0d3f4634b6eca6b8db89b5b3aab304e5eef3607` | NO |
| 12 | forecast/tests/test_mu_report_revision.py | `69be43a29c180fc0a454b3792fe743dbc48d2460d84f490e9ca81a2a70088a26` | NO |
| 13 | forecast/tests/test_mu_report_r22.py | `637ce25d9060c50e9766e77ada8d3a9f9c51fb52035466c1eab94c5322bd95d3` | NO |
| 14 | forecast/inputs/mu_fy2026q4_narrative_ed1.yaml | `8fee9e26f59222ae062a83c450759e91fb90f6a69e1cbceea156f549478bbec0` | NO |
| 15 | forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` | NO |
| 16 | forecast/HANDOFF_CODEX_mu_report_exec.md | `f36d90038668986afe2c342c8cf4dd9d4979b645d190a9a38e20320c905877e5` | NO |
| 17 | forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` | NO |
| 18 | forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md | `3e17e43411db57df3ececdb6467826a6398cb5c4b4b13919daa8f363efd4efc7` | NO |
| 19 | forecast/reports/mu_report_fy2026q4_ed1_data.xlsx | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` | YES |
| 20 | forecast/reports/mu_report_fy2026q4_ed1_en.html | `fcaa764101f150e929c417f9f811e126bfe90dfa3bf43dbd2b171de1c1c700e0` | YES |
| 21 | forecast/reports/mu_report_fy2026q4_ed1_en.md | `a089891ed3d00b5956dd1a7fef449363b365c6224ef09d04f0e2d4ec6c514524` | NO |
| 22 | forecast/reports/mu_report_fy2026q4_ed1_en.pdf | `c2991b9830d0b25480dd74464cc7b32f77cd44236767154a21bf403d88b0aecb` | YES |
| 23 | forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` | NO |
| 24 | forecast/reports/mu_report_fy2026q4_ed1_ko.html | `76012e5c0c44123b89f7f2ea111f819a60d481bef520b0e4ee6a2c1c21b294ca` | YES |
| 25 | forecast/reports/mu_report_fy2026q4_ed1_ko.md | `f9e1083fed2618e922c4f12770b6e71a66a465bd6bea045d5b3f26044078843e` | NO |
| 26 | forecast/reports/mu_report_fy2026q4_ed1_ko.pdf | `a9ba6060ab7c357fd355d34de649030775e5a03745f9d517027297e05b215e44` | YES |
| 27 | forecast/reports/mu_report_fy2026q4_ed1_manifest.json | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` | NO |
| 28 | forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png | `0d81bf0ea955806405a3c79025a400ce78a4c94fe5bb8f4bbb93dc5e4c43daf4` | NO |
| 29 | forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png | `cfc15956d840c83b995c74c3a97abd6c16ac1c65d8c6720f84441d5622c347d3` | NO |
| 30 | forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png | `ec94fae022078834c5431fd831d961425c0784b99bdc96a81967cbe82948066f` | NO |
| 31 | forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png | `3dc5b42fa1ba5e70f614b5453ddf0a23ede14b749c55c7e93bc7eab13f43e43c` | NO |
| 32 | forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png | `5293ee3d52a1e147a789af18fe75fe6722385a34028ce4cb3dfbdb648165b1c6` | NO |
| 33 | forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png | `21742589936c8f57c1e85828dac92d9afcdd568ee848d47c4e8b89bfea63ad9b` | NO |
| 34 | forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png | `15615ee6f5da56340aa50b47f0079be4449bf17b19c0c1589f722b2c207c0c9d` | NO |
| 35 | forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png | `5c704ad775dd26a47c6b1a91873c802b6d8fb7e9f3eead7535798c5aa03b41bc` | NO |
| 36 | forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png | `a2de9a1056c01c0481d44412c586efb07ecf31a70ee39ea0bf1dcdac534dbf33` | NO |
| 37 | forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png | `8471ecf6a18964cd7255a233c6e719de365b522032647d85b5a57f74b6f90ec7` | NO |
| 38 | forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png | `194bffb4f48012917d14a79f458291f9a06ea05c264310ea57617f33ab6273ff` | NO |
| 39 | forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png | `301f02fbdeebdfd21a09ba7e641afb111043e243481e2f2c0a59b70249d76eaa` | NO |
| 40 | forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png | `7c4e1fd8ea4fd0bbb8d616a90dbfada9d60e580d2a515fed87649c9dcb957820` | NO |
| 41 | forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png | `a49225fa6b4ef170a395603b4ee6d6f3ddf95a7e650d9a1b741d654293bbc92f` | NO |
| 42 | forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png | `b355d23388822f7d68b9753301d3dc48d03ae6a39615dbb8097b72d9357a88a6` | NO |
| 43 | forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png | `d24399953905dd871ddce23ad0bcc56e1a006b971da9f075e7581782978daa18` | NO |
| 44 | forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png | `0d8f96523ab26dbe3fbe5d975ffd9fabac4f9cd07d506496b0f22d3efa4573e3` | NO |
| 45 | forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png | `ea43ff2e7c5fba4e85c7d23691e3694faf9fa863f21d54144b9d81cfd3ebcf54` | NO |
| 46 | forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png | `176a93460b799c0e6e53d14e482dd6929a3222d97ff10485e2fcc184157b1fc1` | NO |
| 47 | forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png | `377405fb5dcfdf9598a6cdc683cf48182a6d31da7defb231c0f9c1f9e52f6aba` | NO |
| 48 | forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png | `7fe2010ed6027340f18871c7945a127ee30786b4bc37c491112f27ca3b88a775` | NO |
| 49 | forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png | `86fc1f00a1065d534c7ef9d8eb827d8a2800e367fbdd9f2765fee4abeb7b8433` | NO |
| 50 | forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png | `13bd0f4e23f91653acef27e6bae812baaf5b7fb1f362f08665c90dbc27822bd1` | NO |
| 51 | forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png | `e9e12fa1940e73a72388c92a316ac7de7f5cc22b1e2f0d44e737edb4990cd89b` | NO |
| 52 | forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png | `17c241b5a44da12f0c99fb38d30d7b33442e4ea3e2b8a3901907ee613d86d016` | NO |
| 53 | forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png | `9bae3dee7107e6ce14846fd7d3c1432885c0c512ddebe553a22e2d618fb82eda` | NO |
| 54 | forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png | `877c273477940b13dd8d15fded1b5dd5ee144ddbac36ed56c47a326d14400450` | NO |
| 55 | forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png | `faafbd56b788c9f0632364d732feebba2c26fd85945d205390c831b42cbc01a6` | NO |
| 56 | forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png | `8f83baf1a9abec00ef9c095a95a828ea8c451d9fe65cabebebf64b8dd48f4daf` | NO |
| 57 | forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png | `1ed6dd7efdec6a750bd7818c07b71b963e5b774df0d1c68352b99b2932c03c62` | NO |
| 58 | forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png | `9509d1c16b1bdfec50f52777e99ab333933b9479d39d505f9fcf1e87ef6f89c7` | NO |
| 59 | forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png | `61922b5d70585e0534f28b08c0e5c975f3acdfaf77ef22e0921f9a75d8ce219e` | NO |
| 60 | forecast/tests/test_mu_report_r23.py | `93e2f0a04b649b8e3b455f0a2c1bdf78e3c30dd25b09b927a654de240a487aec` | NO |
| 61 | forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md | `04e20fbcf118242729a62e5b265076ac55ef8b047f834cc93d62b55c60c6f190` | NO |
| 62 | forecast/REVIEW_CODEX_mu_report_ed1rev1_r4.md | SELF — 저장 후 외부에서 계산; 자기 SHA를 문서에 넣는 재귀는 피함 | NO |

제외: `forecast/HANDOFF_CODEX_mu_report_survey_r4.md`, `forecast/PLAN_mu_report_fy2026q4_rev4_superseded.md`, `rev4.1_superseded.md`, `rev4.2_superseded.md`, `rev4.3_superseded.md` 및 무관한 작업 파일. rev-4~4.3 보존본과 survey_r4 핸드오프를 다시 추가하지 않았다.

`logs/**`(rev0 보존 25개·runtime·과거 검토 증거)은 gitignore 대상, E4 제외. `forecast/reports/mu_report_fy2026q4_ed1_assets/pages_r23/**`의 QA 페이지·모음·XLSX 미리보기는 **gitignore NO**이지만 발행 D7 32차트 목록과 다른 검토 증거이므로 E4에서 명시 제외한다. 기존 pages/pages_final/pages_r18 등 QA 폴더도 제외. 테스트 임시 fixture 폴더는 E4 후보가 아니며 정리 후 재생성 가능하다.

report·PDF·spreadsheets 스킬은 기존 산출물 파이프라인을 유지하면서 PDF 전 쪽·차트·XLSX 읽기 전용 검증을 수행하는 데 적용했다. 로고 이미지 사용 0, 서술/수치/추정 규칙/레코드 변경 0, git 쓰기 0.

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

