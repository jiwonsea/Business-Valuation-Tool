# MU FY2026Q4 ed1 — R17 수정·E2B 재렌더 검토 r4

판정: **PASS — R17 F1–F5·P1–P6 및 실행한 사전/사후 게이트.** 별도 E3 배포 승인이나 투자 자문을 의미하지 않는다.

최종 재렌더 시작: **2026-10-04T23:29:20.634374+09:00**, 제한 시각 2026-10-05 14:42 KST 이전. 이해관계 확인 레코드 blob SHA는 `393cb05876f6f5aabf6fbdb98778c69b8c5d06b6`이다. 최종 실행의 failures는 `{}`이다.

## §1. F·P 항목별 수정과 증거

| 항목 | 수정 및 검증 증거 |
|---|---|
| F1 EPS 귀인·적중 수 | SCORED의 Unicode 음수 `−`를 숫자 파서가 잃던 문제를 수정했다. 원시 귀인 값은 `0.843 / -0.730 / 0.103 / 0.086 / 0.302` USD/share로 보존하고, KO/EN 표시를 `+$0.84 / −$0.73 / +$0.10 / +$0.09 = +$0.30`으로 통일했다. 적중 수 원시 값 4는 정수 표시 `4/4 적중` / `4/4 hit`이다. KO PDF 5쪽 및 fact↔표시 문자열 테스트에서 확인했다. 반올림 전 네 귀인 합은 0.302이다. |
| F2 법인세·운전자본·배당 부호 | RLE 계산 입력의 양수 tax/investment/dividend 규약은 그대로 두고, 재무표용 manifest fact를 현금 차감 부호로 만들었다. base FY27E/FY28E 법인세 `-30,794 / -29,553`, 운전자본 투자 `-4,882 / 0`, 배당 `-690 / -690`이다. bear/base/bull 모두 원시 fact=-엔진 입력, USD million 단위와 표시 문자열을 대조했다. CFO=NI+D&A+SBC+부호 적용 운전자본을 다시 검사했고 FY27E base CFO 표시 `205,589`는 유지된다. KO PDF 10–11쪽. 음의 0은 `0`으로 표시한다. |
| F3 FQ4 정성 값·기간 | E2B가 핀된 발표 후 `remarks.pdf`를 실제로 읽고 p.7의 문구를 바인딩하도록 수정했다. source_id=`SRC-REMARKS-FQ4FY26`, PDF 바이트 SHA=`2821d4ccaae50b40dcd28cd4e766c69c509e73d666e4109d5907c7205a03b700`. DRAM 가격 high-teens percentage range↑·비트 mid-single-digit percentage range↑, NAND 가격 approximately 30%↑·비트 approximately 10%↑이다. 원시 categorical 값은 준비문 정규화 텍스트의 정확한 부분 문자열이며, KO 표시만 번역했다. 기간 열 `FQ4-26`을 명시했다. 리허설의 FQ3 값도 별도 `FQ3-26` 기간을 유지한다. KO PDF 7쪽. |
| F4 히트맵 축·기준점 | y축을 수동 설정한 뒤 공통 숫자 formatter가 덮어써 0–4 인덱스를 보이던 원인을 수정했다. 히트맵에는 그 공통 formatter를 적용하지 않는다. 양 축 눈금은 `-4/-2/0/+2/+4%p`; x=FY27 FQ2–FQ4 주당 성장 오프셋, y=FY27 GM 오프셋, 둘 다 기준 경로 대비라고 표시한다. 중앙 0/0 셀을 주황 테두리로 강조하고 캡션에 기준 경로·고정 기준 주가·RLE 재계산을 명시했다. KO/EN PDF 13쪽. |
| F5 주식수·시가총액·P/B | fact의 기간·라벨을 FY2026Q4 / FQ4 diluted weighted-average shares로 바로잡았다. KO `희석 가중평균 주식수(FQ4)`, EN `Diluted weighted-average shares (FQ4)`, 값 `1,147M`이다. 시가총액 산식은 `1,097.39 USD/share × 1,147 million shares = 1,258,706.33 USD million`, 표시 `USD 1,258,706 million`이다. 기말 실제 발행주식수 기준 시가총액이 아니라는 각주와 P/B 캡션의 같은 주식수 기준을 추가했다. 기존 fact ID는 호환성을 위해 유지하되 물리 단위·기간·라벨을 테스트한다. KO/EN PDF 1·14쪽. |
| P1 KO 변경 표·G-15b | A3/A4/A14 원안·변경 셀을 한국어로 렌더했다. 서술 YAML 문장은 수정하지 않았다. G-15b는 허용 용어와 source ID를 제외한 뒤 표를 셀별로 검사한다. 기존 산출물의 실제 RED 증명과 원인은 §2에 기록했다. KO PDF 17쪽. |
| P2 입력/규칙 등급 | R9의 E·D·J 매핑을 렌더러에 적용했다. 예: A2=`E·D / J`, A4=`D / J`, A11=`E / J`, A14=`E(하한) / J`, A15–A17=`E / —`. 신뢰도 low는 표 위에 한 번만 제시하고, 열 제목은 입력/규칙 등급으로 변경했다. KO PDF 16쪽. |
| P3 사전등록 범위 밖 표시 | FY26E PREREG_A 표의 내부 `NOT_IN_SOURCE` 대신 KO `—(사전등록 범위 밖)`, EN `— (not pre-registered)`와 공통 각주를 렌더했다. 내부 상태 계약은 유지한다. 양 언어 Markdown에 `NOT_IN_SOURCE`가 없음을 테스트했다. |
| P4 가이던스·마진 브리지 | EX991 전망을 fact로 추출해 FQ1 FY27 GAAP/비GAAP 표를 추가했다. 매출 `61,500±1,500` USD million, GM `85.95% / 86.25%`, opex `2,310 / 2,060` USD million, EPS `$37.84±$1.00 / $38.15±$1.00`, 희석주식수 `1,150M`. 브리지는 FQ3→FQ4 FY26 실제와 FY26A→FY27E base의 GM·opex 금액·매출 대비 opex 비율을 시작/종료/변화 fact로 표시한다. GM 기여 `+2.2 / +5.2%p`, opex 비율 감소에 의한 OM 기여 `-1.9 / +2.4%p`이다. 실제 OM 변화=GM 변화+opex 비율 기여를 원시 값으로 대조했다. KO PDF 6·12쪽. |
| P5 숫자 서식·원시 튜플 | 숫자 표시 경로를 공통 `_fact_display`에 연결해 SCORED opex를 `3,296 / 1,860`으로 표시한다. 숫자 token의 후행 쉼표를 제거해 `(786,)`가 `(786)`으로 표시된다. G-24에 Python singleton tuple 패턴 검출을 추가하고 `(786,)`를 넣으면 실패하는 테스트를 작성했다. 통화 값은 동일한 USD/share 서식으로 표시한다. |
| P6 논거 제목 | `h4` 스타일에 10pt·굵기 700을 적용했다. 서술 문장 변경 없이 논거 제목이 굵게 보인다. 최종 양 PDF 3–4쪽의 실제 font span이 `Noto-Sans-CJK-KR-Bold`임을 확인했다. |

수정 파일: `forecast/scripts/mu_report/{narrative.py,render.py,charts.py,gates.py,build.py,i18n/ko.yaml,i18n/en.yaml}`, `forecast/tests/test_mu_report.py`, 허용된 ed1 산출물과 본 리뷰. 새 각주가 표지를 두 쪽으로 밀던 렌더 회귀는 cover 여백·행간 조정으로 해소했고, 긴 EN 그림 8 제목은 줄바꿈해 잘림을 없앴다.

수정하지 않은 입력의 SHA-256:

| 입력 | SHA-256 |
|---|---|
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d` |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` |
| `forecast/reports/mu_fy2026q4_SCORED.md` | `0f6e6a951dc57d95b8846dbc8588d42b2ac2925f1c52b54cc80e9a2a027af4f9` |

실적 재채점, 확률가중, SCA 예치금 예측 및 git 쓰기는 하지 않았다.

## §2. 게이트 및 기존 산출물 RED 증명

### G-15b 원인·RED→GREEN

기존 G-15b는 표 셀을 따로 검사하지 않고 문서 전체에서 연속 영어 5단어 이상을 찾았다. 부분 번역·허용 용어 제거·한국어 삽입으로 영어 잔여 구간이 나뉘면 빠졌다. 수정 전 ed1에서 표의 영어 잔여 2곳(406·408행)을 먼저 확인하고 산출물을 보존했다. 강화된 실제 게이트를 보존본 KO Markdown에 실행한 결과:

```text
GateError: G-15b English sentence remains in KO table cell: line 406, column 3: point path as preregistered
```

셀별 4단어 이상 영어 구간 검사를 추가했고 본문 5단어 검사는 유지했다. source ID를 영어 문장으로 오인하지 않도록 `SRC-*`는 제외한다. 406행에서 즉시 실패하므로 같은 실행에서 408행까지 진행하지는 않는다. 두 유형은 각각 단위 테스트로 실패를 확인했다. 최종 KO 표의 원안·변경을 번역한 뒤 G-15b가 PASS했다.

### 전체 실행 결과

명령: `python -m forecast.scripts.mu_report.build --phase E2-B --edition 1`

- 최종 시작: `2026-10-04T23:29:20.634374+09:00`; 이해관계 유효시각 이전 및 24시간 미만 조건 만족.
- 사전 게이트: G-1 핀, G-2 FROZEN 표시, G-3 역사 항등식, G-3f SCORED 바인딩, G-7 template/IO, G-9 cutoff, G-12 manifest, G-14 provenance, G-15 구조, G-17 순현금 설정, G-18 hygiene, G-19 bridge, G-20 phase audit 및 narrative contract PASS.
- 사후 게이트: G-4 inventory, G-5 P/B, G-6 KO/EN 시장 데이터, G-8 KO/EN theme, G-10 narrative, G-11 placeholder, G-12b disclaimer, G-12c conflict, G-13/G-13b/G-13c KO/EN, G-15 parity, 강화 G-15b, G-16 caption 16개, G-17 KO/EN label·순현금, G-17b KO/EN consensus, G-18 hygiene, G-21 formats/목차, G-23 availability, 강화 G-24 PDF raw markup, G-25 cover date PASS.
- 결과: **PASS**, failures `{}`. G-23 required available failure 0, chart placeholder 0.
- runtime audit: `logs/_mu_report_runs/e2b_20261004T232920+0900.json`, SHA-256 `1be102af3a38768b80232f73cce8d83dd1d455933118e75f7b6539dc1ad42f4c`.
- PDF 시각 QA: 최종 KO 17쪽·EN 18쪽을 전부 PNG로 변환해 전체 페이지 overview를 확인하고, 표지·SCORED·현금흐름·히트맵·부록 등 주요 페이지를 원 크기로 확인했다. 표지 1쪽, 목차 2쪽이며 새 각주나 제목의 잘림·겹침·깨진 glyph를 발견하지 않았다.

G-23에는 미가용 위치 88개(미가용 fact 3개 및 KO/EN 표시 위치 85개)가 기록돼 있다. 이는 모든 미가용이 의도적이라는 판정은 아니다. 범위 밖 기존 표시 연결 누락은 다음과 같이 남겨 둔다.

- **NOTICED BUT NOT TOUCHING:** `forecast/scripts/mu_report/render.py:136` — 세전이익 RLE 셀이 `is.pretax_income.*`를 찾지만 실제 annual fact는 `is.pretax.*`여서 FY27E/FY28E 세전이익이 UNAVAILABLE로 표시된다.
- **NOTICED BUT NOT TOUCHING:** `forecast/scripts/mu_report/render.py:152` — 현금흐름 순이익 RLE 셀이 `cf.net_income.*`를 찾지만 실제 annual fact는 `is.net_income.*`여서 FY27E/FY28E 해당 셀이 UNAVAILABLE로 표시된다. CFO 계산 자체는 별도 fact와 F2 테스트에서 검증했다.

이 두 항목은 R17 지정 수정에 포함하지 않았고 현재 G-23 required set도 검사하지 않는다. 본 PASS는 지정 항목·현재 게이트의 통과 범위로 한정한다.

## §3. 산출물 SHA·쪽수 및 이전 버전 보존

아래 파일은 모두 `forecast/reports/` 아래에 있다. SHA-256은 최종 렌더 후 실제 바이트에서 다시 계산했다.

| 파일 | bytes | 쪽수 | SHA-256 |
|---|---:|---:|---|
| `mu_report_fy2026q4_ed1_ko.pdf` | 827,157 | 17 | `ae0eee432ddcf48596cd0a771fbecebd7eaa923d05f7ab751b5db0141f475e5d` |
| `mu_report_fy2026q4_ed1_en.pdf` | 627,414 | 18 | `411ba6328c58528ffc495458888255dfe42be9897af335f6c1826001550d5e5b` |
| `mu_report_fy2026q4_ed1_ko.html` | 47,229 | — | `1e6463e82550a929ba0513e549901acd3881100e4bb64d83bc851c957ee98656` |
| `mu_report_fy2026q4_ed1_en.html` | 47,007 | — | `d96c8e026f0692cfbbf0de6feb2094fe192beddf852700e6ae248611aa710df5` |
| `mu_report_fy2026q4_ed1_ko.md` | 28,708 | — | `916de6eba80e6fdd2efcfca6c87cf4620584f761f1a2026ce496a12d36eacfcf` |
| `mu_report_fy2026q4_ed1_en.md` | 28,438 | — | `8c0632ed1513c6d6b9927e549c0573d9efcc4777ea0ffd44fc731a8220629652` |
| `mu_report_fy2026q4_ed1_data.xlsx` | 35,069 | — | `18fb805d6d7c43fc6b937b5b9ae879203c9118224ec0b1c66c2b431312f86431` |
| `mu_report_fy2026q4_ed1_manifest.json` | 394,803 | — | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` |
| `mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | — | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |

이전 ed1 본체 9개·당시 runtime JSON·asset 디렉터리는 재렌더 전에 `logs/_mu_report_runs/ed1_r2_rejected/`로 이동해 보존했다. 본체 **9/9 SHA가 R16 r3 리뷰에 기록된 값과 일치**하며 복구 가능한 원본이다.

| 보존본 | SHA-256 |
|---|---|
| KO PDF, 16쪽 | `00106e6f00309d6c10c77792cecb26fbbff10fae4a34945c6ef97cc3d5dd5283` |
| EN PDF, 18쪽 | `8752b13ee4d81cfdcadc84bee0cb1708fc37abcb31472ad53792b12298382d19` |
| `e2b_20261004T170059+0900.json` | `7e0260e081ce9a11185044d22a2c2c9ec7ee887b0b026d18f262709276265f68` |

## §4. 테스트

| 실행 | 결과 |
|---|---|
| `python -m pytest forecast/tests/test_mu_report.py -q --tb=short -p no:cacheprovider` — 최종 표시·스타일 수정 후 | **68 passed**, 12.98s |
| `python -m pytest forecast/tests/ -q --tb=short -p no:cacheprovider` — 본 수정 완료 후, 최종 cover 간격·EN 제목 줄바꿈·상승 화살표 추가 전 | **490 passed, 3 skipped, 1 deselected, 1 xfailed**, 64.18s |
| 최종 E2-B build — 위 표시·스타일 수정 후 | 모든 실행 게이트 **PASS**, failures `{}` |

추가한 R17 테스트:

- `test_r17_f1_scored_values_match_signed_displays`: SCORED 원시 fact·USD/share 단위·KO/EN 부호 포함 표시·4/4·천 단위 구분.
- `test_r17_f2_rle_cash_flow_signs_match_displays_and_totals`: 세 경로 두 연도의 tax/WC/dividend 원시 fact·USD million 단위·표시·CFO 합계.
- `test_r17_f5_market_data_labels_units_and_formula_match_facts`: 주식수 물리 의미·기간·단위·시가총액 산식·표지 문자열.
- `test_r17_table_cell_english_and_python_tuple_are_rejected`: 두 영어 표 셀 유형과 Python singleton tuple의 RED 검증.
- `test_r17_fq4_categories_guidance_and_bridge_are_source_bound`: 실제 remarks p.7 원문 일치·가이던스 수치·OM 기여 항등식·내부 상태/튜플 미노출·입력/규칙 등급.

리허설·dry-run 관련 기존 테스트도 report 테스트 및 전체 forecast 회귀에 포함돼 계속 통과했다. skip은 Windows symlink/process-group 제약 및 gitignored EDGAR cache 부재이며, xfail은 기존 FYE-August Q1 라벨 이슈다. 이번 수정에서 건드리지 않았다. 초기 로컬 테스트의 임시 디렉터리 권한 오류는 권한을 갖춘 동일 명령 재실행으로 해소했으며 최종 코드 테스트 실패는 없다.

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
