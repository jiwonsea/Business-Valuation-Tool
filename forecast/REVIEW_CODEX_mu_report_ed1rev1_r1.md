# MU FY2026 Q4 ed1 개정 1 — R20 실행 리뷰 r1

> **PASS (R20-1–3 사전 준비·비렌더 검증). STOPPED_PRE_RENDER_R20.**
> 새 PDF·HTML·Markdown·XLSX·차트 이미지 파일은 생성하지 않았다. 이해관계 레코드를 열거나 갱신하지 않았고 git 쓰기·push를 하지 않았다. 이번 판정은 발행 승인이나 렌더 후 게이트 PASS를 뜻하지 않는다.
>
> 기준: 로컬 커밋 `cbacb4d`; 서술 r3 SHA-256 `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f`. 실행일 2026-10-05 KST. 본 문서는 투자 자문이 아니다.

## 1. 항목별 수정 및 수정 전 보존

### 1.1 수정 전에 보존한 ed1 rev0

코드 수정 **전에** 커밋의 ed1 파일 25개(본 파일 9개 + KO/EN PNG 16개)를 작업 트리와 바이너리 대조한 뒤, `logs/_mu_report_runs/ed1_rev0_committed/`에 원본 그대로 복사했다. `forecast/reports/` 아래 상대 경로를 보존했다. 마지막 재검증도 **25/25 PASS**: 커밋 바이트 = 현 ed1 바이트 = 보존본 바이트, 불일치 0건. 줄바꿈·파일명·기존 산출물은 바꾸지 않았다.

`_assets` 디렉터리 전체를 복사했으므로 기존 미추적 페이지 QA 이미지 126개도 함께 보존했다(총 151개 파일). 아래 SHA 승인 대조 대상은 **커밋에 들어 있는 25개**이며, 추가 QA 이미지는 새 E4 후보가 아니다. 보존 경로는 gitignore 대상이다.

다음 파일명 앞에는 `forecast/reports/`를 붙이며, 보존본에서는 그 접두사를 `logs/_mu_report_runs/ed1_rev0_committed/`로 바꾼다.

| 커밋 파일 / 보존 상대 경로 | 바이트 | SHA-256 (커밋·현 파일·보존본 동일) |
|---|---:|---|
| `mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png` | 54,478 | `d69430ea4339d456ca05be74ae8d0f30c62b292d3ef5fa707d39b4ecdb270f25` |
| `mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png` | 49,312 | `2636e62e1c82df11331c2f5710e6d1c416262bc54d07c801e12fdd63ec0104b2` |
| `mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png` | 24,872 | `227ffde29da2ae523fed036dd84208b7e6827e2f540d1c59d5d4b638e517b50b` |
| `mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png` | 21,443 | `2fcaf2996163053c8cc72e458a13de859dc55e12286ba03d5c3e9d371c346aa9` |
| `mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png` | 45,378 | `27e7cfd681daebe67e2278aed5aa6afe8ffef0fb532e646f5693d8c0a3c808ea` |
| `mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png` | 41,558 | `5b33e070265eef7e4198cc5ab273b81486bf5b90067f3ed8081ff6bb5dca3576` |
| `mu_report_fy2026q4_ed1_assets/04_beat_history_en.png` | 26,699 | `085a16edf597842d78ecba2545c321f05daa2262399da1f3637823dd7c1f4638` |
| `mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png` | 23,551 | `cceefb7c18ba77dfd838fff296d4b2059e969dca30b6b1fbb324995ce4902b42` |
| `mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png` | 50,125 | `dd82634eca3346a37fdd6164a5f44696c206aeaecb9e103c74428cf92445565d` |
| `mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png` | 48,207 | `7a5cbe1f72a09e145dbb9ce6ab818723e9ade7e8bde6011cceccda95aae9adf8` |
| `mu_report_fy2026q4_ed1_assets/06_annual_income_en.png` | 32,389 | `78dea8b9997e713fc103e57dd32e040afdab65a72fac518b5af974a5bd8cd3dc` |
| `mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png` | 28,176 | `4390091c0cc03c0791f07cdcb9f7dd6231a4d6f9fabcb882ae2aec003a434b71` |
| `mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png` | 47,620 | `fd819824abb8cc8d27172249e0c8c61838707b1403a0ebfb7f9c91d40640aeea` |
| `mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png` | 42,764 | `1ead96ea05256a65cf22b0f72bd95574141f845c901215537f836b3b58a5830d` |
| `mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png` | 32,935 | `1ee978d72fba7f4ba25afbc490f98bcaefc07e8706ed2b4ebff2ab0f9c0840f0` |
| `mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png` | 32,851 | `0a7230adfea1ddd412548080dc7ac4ea32a278aca2f6a91d7defa0003f576517` |
| `mu_report_fy2026q4_ed1_data.xlsx` | 36,032 | `7536749decdfe5661ba3746793a884dab7cbee062c268c57b9e2b39709712212` |
| `mu_report_fy2026q4_ed1_en.html` | 46,477 | `1a710f098cad03549c6572f6d00301455453e0536318bc89e80cd24f4b038182` |
| `mu_report_fy2026q4_ed1_en.md` | 27,929 | `d22250400d1858a7d65081277cb75d4e58b0458d16258a8854faeb8c9c184682` |
| `mu_report_fy2026q4_ed1_en.pdf` | 626,312 | `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6` |
| `mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |
| `mu_report_fy2026q4_ed1_ko.html` | 46,603 | `4992b1483a6ee4433e87f86678d021e79ac8fa4b5ff248f98f0cf4607b71ce7a` |
| `mu_report_fy2026q4_ed1_ko.md` | 28,103 | `495bcbd936758494954ac81a5e96f4cf75e9fbc0813d546d2da14c7d48333313` |
| `mu_report_fy2026q4_ed1_ko.pdf` | 806,139 | `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a` |
| `mu_report_fy2026q4_ed1_manifest.json` | 394,803 | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` |

### 1.2 R20-1의 9건

| 항목 | 구현·비렌더 확인 |
|---|---|
| 1 숫자 정렬 | 공용 HTML 표 변환에서 모든 숫자 셀을 오른쪽 정렬. 첫 열 숫자도 동일 규칙. `1,147M`, `USD 1,258,706 million`, 가격, %p, 음수 및 연도 테스트 |
| 2 회사·약어 | 1절 회사 4문단을 표·차트보다 앞에 연결. 표지·목차 뒤 본문 진입 전에 “약어와 출처” 상자, 부록에 같은 목록 |
| 3 논거 | 강세/약세 소제목과 claim 굵게. 강세1은 회사 진술 표; 강세2=C12, 강세3=C16, 약세1=C10, 약세2=C16, 약세3=C14를 각각 claim 바로 아래 배치 |
| 4 판정 기준 | r3 `fq4_reading` 3항 상자. SCORED 요약 아래 6열·5행 지표별 판정 표. 기존 SCORED §4를 인용하며 **새 채점 없음** |
| 5 GM·가격/비트 | 4절 `gm_compression` 3문단, C9는 4·5절에 연결. 5절 기존 정성 표는 C10 + r3 `price_bit_note`로 교체. DRYRUN의 기존 정성 표는 유지 |
| 6 각주 | Freeze A: “사전등록(Freeze A)은 FQ4 분기와 FY26 매출·순이익·EPS만 예측했다.” RLE: “RLE 규칙은 손익·현금흐름 일부만 추정하고 재무상태표는 추정하지 않는다(부록 규칙표 A11–A16).” KO/EN 연결 |
| 7 리스크 | 10절 각 리스크 제목 굵게 |
| 8 표지 | “MICRON TECHNOLOGY · NASDAQ: MU” 굵은 텍스트 워드마크와 청색 강조. 판 표시 “제1판 개정 1 / Edition 1, Revision 1”. 로고 이미지·상표 서체 모방 없음 |
| 9 출처 | r3의 `src` 풀네임 유지. 서술 문장 및 YAML 파일은 수정하지 않음 |

숫자·RLE 규칙 보존: 가정 YAML SHA `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` 유지. 기존 manifest **759개 fact의 raw_value 전부 동일**. 새 계산·출처 연결 fact를 더한 메모리 manifest는 878개이며, 기존 값을 덮어 바꾸지 않았다. 시나리오 확률 삭제·확률가중 금지와 “순현금(SCA 예치금 미조정)” 라벨도 유지했다.

## 2. 차트 16개 정의·데이터 출처

KO/EN 각각 16개 정의(기존 8 + 신규 C9–C16 8)가 준비됐다. 아래는 **이미지 파일 생성 결과가 아니라** 비렌더 데이터 계약 목록이다. 기존 물리 ID와 그림 번호의 순서는 서로 다르며 유지했다. 캡션은 단위·기준·출처 ID·기준일 `2026-10-04`를 포함한다.

| C ID | 물리 ID / 그림 번호 | 차트 | 연결 fact 수 | 배치 | 캡션의 출처 |
|---|---|---|---:|---|---|
| 1 | `01_quarterly_revenue_margin` / 그림 5. | 분기 매출과 GAAP 마진 | 39 | 6절 | Micron 10-Q·8-K [SRC-COMPANYFACTS, SRC-EX991-FQ4FY26] |
| 2 | `02_business_unit_mix` / 그림 1. | 사업부별 매출 구성 | 36 | 1절 | Micron 실적자료 [SRC-BU×4, SRC-EX991-FQ4FY26] |
| 3 | `03b_guidance_beat_history` / 그림 4. | GAAP 매출총이익률 가이던스와 실제 | 22 | 5절 | Micron 분기 가이던스·실적자료 [SRC-FROZEN, SRC-SCORED-FQ4FY26] |
| 4 | `04_beat_history` / 그림 2. | 매출 가이던스 상회율과 GAAP EPS 상회액 | 22 | 3절 | Micron 분기 가이던스·실적자료 [SRC-FROZEN, SRC-GUIDANCE×10, SRC-SCORED-FQ4FY26] |
| 5 | `05_scenario_fan` / 그림 3. | FQ4 실제에서 FY27E 시나리오 | 13 | 4절 | Micron FQ4 실적·RLE [SRC-EX991-FQ4FY26, SRC-RLE-FY27] |
| 6 | `06_annual_income` / 그림 6. | 연간 매출·영업이익·순이익 | 20 | 6절 | Micron 10-K·8-K·RLE [SRC-10K-FY25, SRC-EX991-FQ4FY26, SRC-FROZEN, SRC-RLE-FY27] |
| 7 | `07_valuation_heatmap` / 그림 8. | 암시 P/E 민감도 | 25 | 9절 | 기준 주가·RLE [SRC-PRICE-1] |
| 8 | `08_cash_flow_capex_net_cash` / 그림 7. | 조정 FCF·순설비투자·순현금(SCA 예치금 미조정) | 18 | 6절 | Micron 10-K·8-K·RLE [SRC-10K-FY23, SRC-10K-FY25, SRC-EX991-FQ4FY26, SRC-RLE-FY27] |
| 9 (신규) | `09_gm_beat_compression` / 그림 9. | GM 상회 폭 압축 | 22 | 4·5절 | Micron 분기별 보도자료(8-K EX-99.1) [SRC-EX991-FQ4FY26, SRC-FROZEN, SRC-SCORED-FQ4FY26] |
| 10 (신규) | `10_price_bit_ranges` / 그림 10. | DRAM·NAND 가격·비트 변화(회사 공시 구간) | 16 | 약세1 바로 아래·5절 | Micron FQ3·FQ4 FY26 준비문 p.7 · J 환산 [SRC-REMARKS-FQ3-FY26, SRC-REMARKS-FQ4FY26] |
| 11 (신규) | `11_eps_error_waterfall` / 그림 11. | EPS 오차 4-lever 폭포 | 6 | 3절 | SCORED §6 [SRC-SCORED-FQ4FY26] |
| 12 (신규) | `12_fq1_guidance_comparison` / 그림 12. | FQ1 FY27 가이던스 vs 사전등록 예측 | 6 | 강세2 바로 아래·3절 | FROZEN §(c-2) · Micron FQ4 FY26 보도자료 [SRC-EX991-FQ4FY26, SRC-FROZEN] |
| 13 (신규) | `13_scenario_sensitivity_eps` / 그림 13. | FY27E 시나리오·민감도 EPS | 7 | 8절 | RLE A1–A7 [SRC-RLE-FY27] |
| 14 (신규) | `14_opex_net_capex_trend` / 그림 14. | 영업비용·순 capex 추이 | 32 | 약세3 바로 아래·10절 | Micron pin된 EX-99.1·10-K·10-Q · RLE [SRC-BU×4, SRC-EX991-FQ4FY26, SRC-GUIDANCE×7, SRC-RLE-FY27] |
| 15 (신규) | `15_operating_income_waterfall` / 그림 15. | FY26A → FY27E base 영업이익 브리지 | 5 | 7절 | Micron FQ4 FY26 보도자료 · RLE [SRC-EX991-FQ4FY26, SRC-RLE-FY27] |
| 16 (신규) | `16_sca_structure` / 그림 16. | SCA 구조 | 6 | 강세3·약세2 바로 아래 | Micron FQ4 FY26 준비문 p.3·p.8–9 [SRC-REMARKS-FQ4FY26] |

### 2.1 신규 차트 계산 확인

- **C9:** 실제 GAAP GM − 가이던스 중간값. FQ2/FQ3/FQ4 FY26 = +7.410000 / +3.560000 / +0.7561636763 %p; 서술 표시는 +7.41 / +3.56 / +0.76 %p. GM 전분기 변화는 별도 선, FQ1 FY27 가이던스 85.95%는 우측 축 점이다. 첫 관측 분기의 QoQ는 선행 관측점이 없어 빈칸으로 두고 각주에 밝혔다.
- **C10:** 회사 범주 원문 8개(FQ3·FQ4 × DRAM/NAND × 가격/비트)에서 승인 J 구간의 양 끝 16개만 연결. 원문을 정밀 측정값으로 취급하지 않는다. 범주 레이블이 숫자 축 포매터로 덮이지 않도록 범주 축은 별도로 유지했다.
- **C11:** SCORED §6 인용: 32.57 → 매출 +0.843 → OP margin −0.730 → OP→NI +0.103 → 주식수 +0.086 → 실제 32.87 USD/주. 공개 반올림 기여 합계는 +0.302, 총차는 +0.30이므로 마지막 막대는 실제 공시 EPS를 사용한다. 재채점·귀인 규칙 변경 없음.
- **C12:** FROZEN §(c-2)의 **예측 가이던스 중간값** bear/base/bull ≈39,600/48,750/57,300 USD 백만을 직접 읽었다. FROZEN 매출 경로나 사후 RLE 값으로 대체하지 않았다. 실제 가이던스 60,000–63,000, 중간값 61,500. 보조 주당 축은 각 값/13주 ÷ 실제 FQ4 54,229/14주 − 1로 동일 환산; 회사 중간값 +22.131644%.
- **C13:** 기존 RLE 그대로 재실행. bear/base/bull EPS 118.949491/169.046536/199.515746. 민감도 4행(둔화, 성장 없음, R8 원안, GM 원안) 165.556871/159.626542/170.139311/167.455276. 가정 파일 원본은 변경하지 않고 복제 입력으로 계산했다.
- **C15:** FY26A OP 99,340 + 매출 효과 114,290.712301 + GM 효과 14,382.255672 − opex 증가 2,189 = FY27E base OP **225,823.967973** USD 백만. 매출 효과=(R27−R26)×GM26; GM 효과=R27×(GM27−GM26); opex 효과=O26−O27. GM은 비율(fraction)이며 % 숫자로 중복 나누지 않는다.
- **C16:** 준비문에서 26건, 2030년까지 총매출 **>35%** SCA, SCA 매출 내부 가격 틀 75%/시장가 25%, 고객 약정 32,000/고객 예치금 12,700 USD 백만 확인. 비율과 금액은 독립 패널, 건수와 하한은 텍스트로 분리했다. EX-99.1의 비유동 고객계약부채 **12,895**는 별도 각주이며 예치금 12,700으로 치환하지 않았다.

C10의 KO 각주(정의에 그대로 포함):

> J(판단) 환산; 회사 수치 아님: low-single-digit = 1–3%; mid-single-digit = 4–6%; ≈10% = 9–11%; high-teens = 16–19%; ≈30% = 28–32%; low-60s = 60–63%; mid-80s = 84–86%

EN 각주에도 같은 7개 구간을 `J (judgement) conversion, not company figures`로 표시했다. 신규 사실을 추가한 회사 공시 수치가 아니라 **J(판단) 환산표**이다.

### 2.2 C14 분기 원천·제외 목록

실제 구간은 FY2024Q1–FY2026Q4의 **12개 분기 모두 원천 확인**: GAAP 영업비용 12개, 회사 조정 순 capex 12개. 회사 분기 보도자료의 `Quarterly Financial Results → Operating expenses`와 분기 `Capital expenditures, net` 행을 읽었다. 가이던스 대상 분기와 그 보도자료에 실린 실제 분기를 구분했으며, 연간 capex 전망/합계로 분기값을 추정하지 않았다.

**제외 분기: 없음. 사유: 모든 12개 실제 분기에 직접 공시 분기값이 있다.** 과거 분기에도 추정·보간을 사용하지 않았다. FY27 네 분기는 기존 A4/A14의 명시적 RLE 경로이며 실제 실선과 추정 점선을 분리한다.

단위: USD 백만.

| 분기 / 기준 | 영업비용 | 순 capex | source_id |
|---|---:|---:|---|
| FY2024Q1 (A) | 1,093 | 1,734 | `SRC-GUIDANCE-cba05d3a7684` |
| FY2024Q2 (A) | 888 | 1,248 | `SRC-GUIDANCE-a635cd2a7c38` |
| FY2024Q3 (A) | 1,113 | 2,057 | `SRC-GUIDANCE-51fa896d882d` |
| FY2024Q4 (A) | 1,215 | 3,082 | `SRC-GUIDANCE-3faad63e6c8e` |
| FY2025Q1 (A) | 1,174 | 3,132 | `SRC-GUIDANCE-f1ece4749d1a` |
| FY2025Q2 (A) | 1,190 | 3,085 | `SRC-GUIDANCE-503fbf81dc7f` |
| FY2025Q3 (A) | 1,339 | 2,660 | `SRC-GUIDANCE-170cac3d1ae6` |
| FY2025Q4 (A) | 1,400 | 4,927 | `SRC-BU-34478c62e48f` |
| FY2026Q1 (A) | 1,510 | 4,505 | `SRC-BU-ee2e84a14aef` |
| FY2026Q2 (A) | 1,620 | 5,004 | `SRC-BU-18c8475fe645` |
| FY2026Q3 (A) | 1,738 | 7,084 | `SRC-BU-9f7e667a8224` |
| FY2026Q4 (A) | 3,296 | 10,774 | `SRC-EX991-FQ4FY26` |
| FY2027Q1 (RLE) | 2,310 | 11,500 | `SRC-RLE-FY27` |
| FY2027Q2 (RLE) | 2,413 | 13,500 | `SRC-RLE-FY27` |
| FY2027Q3 (RLE) | 2,654 | 12,500 | `SRC-RLE-FY27` |
| FY2027Q4 (RLE) | 2,976 | 12,500 | `SRC-RLE-FY27` |

| 실제 분기 | pin 원천 경로 | 확인 SHA-256 |
|---|---|---|
| FY2024Q1 | `logs/_claude_scratch/mu_G2024Q2_ex991.htm` | `cba05d3a7684f893b43a3a54ec2bf27145a4ed4ed2197ff94d8168464cab2abb` |
| FY2024Q2 | `logs/_claude_scratch/mu_G2024Q3_ex991.htm` | `a635cd2a7c38e53ca19d60c94cf65ec45cddc3f175cee20b6078a1f48088d94a` |
| FY2024Q3 | `logs/_claude_scratch/mu_G2024Q4_ex991.htm` | `51fa896d882da1544c4bdcf52c52ce1acc15ff4ba0f7ea413ef848d8a186a938` |
| FY2024Q4 | `logs/_claude_scratch/mu_FY2024Q4_ex991.htm` | `3faad63e6c8e3667a09e72916aa6a6e313ac3e205b24a3f625caa88b50bfe30a` |
| FY2025Q1 | `logs/_claude_scratch/mu_G2025Q2_ex991.htm` | `f1ece4749d1a645444f9e32c02e494c61ec7d2bcedac8949c1430e8faf715856` |
| FY2025Q2 | `logs/_claude_scratch/mu_G2025Q3_ex991.htm` | `503fbf81dc7fbf45c0a2bfe1f69a93b7b2fa352e490a3366738bf5262f65021a` |
| FY2025Q3 | `logs/_claude_scratch/mu_G2025Q4_ex991.htm` | `170cac3d1ae6d47c27ec6cdf619e67a5f00b5ccf49ecf9421d65d037fc00928a` |
| FY2025Q4 | `logs/_claude_scratch/mu_FY2025Q4_ex991.htm` | `34478c62e48f4184444c2cb72e4e4da28389026aa636297e80d33a79694efc58` |
| FY2026Q1 | `logs/_claude_scratch/mu_G2026Q2_ex991.htm` | `ee2e84a14aefe39c12f9808ef596f8819a10ce902d7c083947d9473c05fc640e` |
| FY2026Q2 | `logs/_claude_scratch/mu_G2026Q3_ex991.htm` | `18c8475fe645dacbdb048073869a393c3dc82d7440d89fe5cf25c7a457851927` |
| FY2026Q3 | `logs/mu_ho5_S2_release.html` | `9f7e667a8224193b438287d0186c7273262c79e98af71feb3613e0837347c392` |
| FY2026Q4 | `logs/mu/fy2026q4/postprint/ex991.htm` | `5dad1ce5c2dd8958dad947ab1f12a1015bfcc29c7e8a29e48379e983f425120e` |

FY27E 네 분기의 원천은 기존 가정 YAML `SRC-RLE-FY27`, SHA `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539`이다.

C14 KO 각주:

> 실선=실제, 점선=RLE; 제외 분기: 없음(원천 12개 분기 확인). 원천 누락은 빈칸이며 추정·보간하지 않는다.

누락 시 동작도 별도로 테스트했다: FY2025Q2 순 capex 원천값을 제거한 모의 manifest에서는 그 셀이 NaN(빈 관측점)이고 선이 끊긴다. 해당 분기·계열·사유가 각주에 들어가며 각주를 제거하면 게이트가 실패한다. 이것은 누락 처리 검증용 입력이며 **실제 제외 목록에 해당 분기를 추가하지 않았다**.

## 3. 바인딩·게이트 판정

### 3.1 R20-3 바인딩

입력 r3 YAML SHA는 그대로이다. 승인 입력을 메모리에 읽은 후 새 절 5개(`abbreviations/company/fq4_reading/gm_compression/price_bit_note`)와 새 바인딩을 연결한다. 기존 12개 + R20 명시 6개 + 새 절이 이미 사용하는 `guidance.gm_gaap.FQ1FY27` 1개 = **19개 고유 바인딩**. 이 추가 GM 바인딩을 빼면 새 서술의 사용 토큰과 계약이 일치하지 않는다.

| 신규 사용 바인딩 | 재계산 값 | 단위·기준 |
|---|---:|---|
| derived.gm_beat.FQ2-26 | 7.4100000000 | %p, 실제−가이던스 |
| derived.gm_beat.FQ3-26 | 3.5600000000 | %p, 실제−가이던스 |
| derived.gm_beat.FQ4-26 | 0.7561636763 | %p, 실제−가이던스 |
| guidance.revenue_lo.FQ4FY26 | 49,000 | USD 백만, FROZEN 무차이 범위 |
| guidance.revenue_hi.FQ4FY26 | 51,000 | USD 백만, FROZEN 무차이 범위 |
| is.revenue.FY2026Q4.A-8K | 54,229 | USD 백만, 기존 실제 fact |
| guidance.gm_gaap.FQ1FY27 | 85.95 | %, 기존 회사 가이던스 fact |

### 3.2 사전 검증과 렌더 후 검증의 분리

실행:

```powershell
python -X utf8 -m forecast.scripts.mu_report.build --phase E2-B --edition 1 --preflight-only
```

exit 0; `STOPPED_PRE_RENDER_R20`; 차트 KO 16 / EN 16; `c14_missing=[]`; `required_available_failures=[]`.

| 게이트 | 이번 검증 결과 / 경계 |
|---|---|
| G-1·G-2·G-3·G-3f | PASS — 입력 SHA, Freeze A 표시값, 재무 항등식, 기존 SCORED 원천 |
| G-7·G-9·G-12·G-14·G-18·G-19·G-20 | PASS — IO/템플릿, 컷오프, manifest/provenance, 위생, 브리지, 단계 입력 감사 |
| G-10-data·G-11-data | PASS — 새 9개 서술 절 KO/EN 구조·토큰 순서, 19개 바인딩, 미해결 placeholder 없음 |
| G-13/13b/13c-data | PASS — 16개/언어, 값·fact·계열·기간 계약. C10 J 환산 및 C14 누락 정책 포함 |
| G-15·G-15b-data | PASS_IN_MEMORY — KO/EN 숫자·fact 참조와 한국어판 UI. 새 판 표시의 동치 표현만 정규화 |
| G-16-data·G-17 config·G-23-data | PASS — 그림 1–16 캡션, 순현금 라벨, 필수 사용 가능 셀 |
| G-4·G-5·G-6-data | 별도 읽기 전용 검사 PASS — 재고일수 계산, trailing P/B/기준일, 시장 데이터 4행 |
| G-8-in-memory·G-17/17b-data·G-25-data | 별도 메모리 검사 PASS — 색 대비/로고 금지, 라벨·컨센서스, 표지 날짜 형식 |
| G-12c | **PENDING_CONFLICT_CONFIRMATION** — 실제 레코드를 읽거나 갱신하지 않고 그 전에 종료 |
| G-12b 실제 페이지·G-13 실제 이미지·G-16 실제 배치·G-21·G-24·G-25 실제 표지 | **DEFERRED_RENDER** — 새 파일 없음. PDF/XLSX 원시 마크업, 페이지 푸터·폰트·페이지 수, 실제 이미지·전 쪽 시각 QA는 미실행 |

CLI 결과의 기존 G-4/5/6/8 `NOT_APPLICABLE_PRE_RENDER` 상태는 렌더 후 경로 상태이다. 별도 검사에서는 같은 입력·메모리 문자열로만 위 표의 `*-data`를 확인했으며 실제 발행 산출물 통과로 올리지 않았다.

고의 실패 테스트: 신규 차트 하나씩 누락(8건), C10 승인 J 끝점 변조, C14 누락 각주 삭제, KO/EN 회사 문단 수 불일치는 모두 거부된다. 기존 8개 DRYRUN 계약은 유지한다.

**중지 조건:** R20 머리 지시대로 렌더 직전에 종료했다. 핸드오프에 기재된 기존 이해관계 확인 만료는 2026-10-05 14:42 KST이다. 사용자 재확인 후 Claude의 별도 레코드 갱신과 렌더 승인이 선행돼야 한다. 이번에는 레코드 시각을 임의 연장하지 않았다.

## 4. 산출물 SHA·쪽수

새 개정판 D7 파일은 **미생성**. 새 PDF 쪽수·새 PNG/HTML/XLSX SHA는 **DEFERRED_RENDER**이다. §1 SHA와 아래 쪽수는 오직 `cbacb4d` **ed1 rev0 보존본 및 그대로 남은 현 파일**을 뜻한다.

| 항목 | 상태 |
|---|---|
| 기존 KO PDF | SHA `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a`, 17쪽 유지 |
| 기존 EN PDF | SHA `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6`, 18쪽 유지 |
| 기존 나머지 23개 D7 파일 | §1 전부 바이트 동일 |
| 새 개정판 KO/EN PDF·HTML·MD 및 XLSX·manifest·PNG | 생성하지 않음. 파일명은 이후에도 ed1 유지, 판 표시만 개정 1 |
| 이번 결과 | 본 리뷰 1개 + 승인 범위 코드/테스트 변경 + rev0 복사 보존 |

## 5. 테스트

1. R20 새 비렌더 테스트: **30 passed in 4.72s**.
2. forecast 비렌더 선택 회귀: **521 passed, 3 skipped, 12 deselected, 1 xfailed in 59.66s**.
3. 기존 DRYRUN 관련 테스트 5개 전부 해당 선택 실행에 포함되어 통과(확인 레코드 분기, 실제 manifest, placeholder 주입, 경로 경계, 잘못된 edition 거부). 실제 리허설 파일 재생성은 하지 않았다.
4. `git diff --check` PASS(읽기 전용).
5. commit / 현 파일 / archive 재검증 25개, 불일치 0건; 기존 fact raw 759개 불일치 0건.

forecast 전체 실행 중 최초 발견한 회귀 3건은 수정 후 각각 다시 통과했다: G-16 오류 메시지의 기존 검증 구문 유지; 기존 12개 재계산 단위 테스트에는 확장 전 원본 YAML 입력 사용; C10 대체 이후 R17 기간 검증은 제거된 정성 표 문자열 대신 차트 fact 기간을 검사.

3개 skip은 Windows 심볼릭 링크 권한/프로세스 그룹 미지원 및 기존 EDGAR 파생 캐시 부재, 1개 xfail은 이미 알려진 FYE-August Q1 라벨 문제이다. 범위 밖 상태는 변경하지 않았다.

렌더 금지를 지키기 위해 다음 **11개 함수, 12개 테스트 항목**을 제외했다. 이를 “전체 렌더 테스트 통과”로 보고하지 않는다.

- `test_g13_and_g13b_chart_pass_and_violation`
- `test_g21_rendered_formats_pass`
- `test_g21_pdf_html_md_xlsx_violations`
- `test_renderer_parity_reference_contract`
- `test_xlsx_rebuild_is_byte_deterministic`
- `test_r4_rendered_bundle_pages_toc_and_conflict_footer`
- `test_r5_g13c_semantic_contract_and_violation`
- `test_r6_g13c_rejects_mixed_period_units_reverse_order_and_omission`
- `test_r16_e2b_markdown_and_chart_contracts_pass_together`
- `test_r19_ed1_xlsx_uses_cover_strings_without_changing_facts`
- `test_r19_ed1_xlsx_requires_confirmed_cover_context`

재현(제외 이름을 위 목록 그대로 사용):

```powershell
python -X utf8 -m pytest forecast/tests/test_mu_report_revision.py -q -p no:cacheprovider
# forecast 선택 실행: 위 11개 이름 각각에 "not "을 붙여 " and "로 연결한 -k 식 사용
python -X utf8 -m pytest forecast/tests/ -q -p no:cacheprovider -k "<위 비렌더 제외식>"
git --no-optional-locks diff --check -- forecast/scripts/mu_report forecast/tests/test_mu_report.py
```

차트 함수 테스트는 모의 축으로 데이터·레이블·NaN을 확인하며 `savefig`를 호출하지 않는다. 메모리 Markdown/HTML 문자열 검사는 파일을 쓰거나 PDF·PNG·XLSX를 만들지 않는다.

## 6. E4 후보 목록 (커밋 미실행)

아래는 **후보**이며 승인/커밋/공개한 목록이 아니다. SHA는 현재 디스크 바이트 기준. 입력 r3와 R20 핸드오프는 이번 작업 전부터 변경된 파일로, 읽기만 했다. scripts/tests 외 다른 기존 변경은 포함하지 않는다.

| 경로 | 변경 책임 | gitignore | SHA-256 |
|---|---|---|---|
| `forecast/scripts/mu_report/build.py` | R20 수정 | 아니오 | `fcf14d6cd9ddf2e67a961dd5ac1420d916919c0ba2c074f319bac46d9e3a5983` |
| `forecast/scripts/mu_report/charts.py` | R20 수정 | 아니오 | `e16246cee7175f87b7894efaa61ef38432ddd637fd7468c46208a94251fbf751` |
| `forecast/scripts/mu_report/gates.py` | R20 수정 | 아니오 | `fc8d7c7c9bb5554c9e1a3131a4a8c7d3a7f79d6fcf0df70fae336e1da0b6983a` |
| `forecast/scripts/mu_report/i18n/ko.yaml` | R20 수정 | 아니오 | `238491820d4f48c258f1a87a9853c1a84554dd34c6f0f156e4fcc441e065633b` |
| `forecast/scripts/mu_report/i18n/en.yaml` | R20 수정 | 아니오 | `28adf176a496727a9dd9054f5591f80ea7163e7589d5c8d0cac06d107c182c2c` |
| `forecast/scripts/mu_report/narrative.py` | R20 수정 | 아니오 | `963732d9ded36c3327c0029c5d495d1ad66a61ed01677221c9ed448f63f6ee11` |
| `forecast/scripts/mu_report/render.py` | R20 수정 | 아니오 | `b3fa03d197a25748d73bc151b5d00a4c316bb8a684dd123350ca9d8872fd3175` |
| `forecast/scripts/mu_report/revision.py` | 신규 | 아니오 | `9587d9409dc5f5a60f05b195bf34b864803024f8f90b1b81847671f848e92f45` |
| `forecast/tests/test_mu_report.py` | R20 수정 | 아니오 | `1e66715930f9b6e246bcb41427477700cc5587fefdb1f90bfd720cda239e6cf5` |
| `forecast/tests/test_mu_report_revision.py` | 신규 | 아니오 | `c944823b5ae3cb0b9ad4386c5a1a96006a99910bdbb7348288f250203026c81c` |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | 사용자/Claude 선행 변경, 이번 작업 읽기만 | 아니오 | `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f` |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | 사용자/Claude 선행 변경, 이번 작업 읽기만 | 아니오 | `687ae66c15e60bb0df1616f6ef7774e4eb41f16db089bdcf19d2ffbc39ade5cc` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md` | 신규 실행 리뷰 | 아니오 | 자기참조 SHA는 본문에 넣지 않음; 최종 파일 외부 해시로 확인 |

후속 렌더 승인 이후에만 새 D7 산출물 9개와 KO/EN 16종 차트 이미지(총 32개), 실제 런타임 감사·전 쪽 QA를 재검증해 최종 E4 목록을 확정한다. 현재 남아 있는 **rev0 파일을 새 rev1 렌더 후보로 오인해 커밋하지 않는다**.

제외: `logs/_mu_report_runs/ed1_rev0_committed/**`와 기존 QA 페이지는 gitignore·보존 전용; survey_r4 핸드오프, rev-4~4.3 보존본, 이해관계 레코드 갱신, 관련 없는 CLAUDE.md 등 작업 트리 변경은 이번 E4 후보가 아니다. RLE 가정·SCORED·FROZEN·가격·원천 pin은 바꾸지 않았다.

---

본 문서는 투자 자문이 아니다. This document is not investment advice.

