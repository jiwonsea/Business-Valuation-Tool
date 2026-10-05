# MU FY2026 Q4 report E2B R16 review — r3

판정: **PASS**. ed1 KO/EN 최종 재렌더는 2026-10-04 17:00:59 KST에 시작되어 2026-10-05 14:42 KST 기한을 충족했다. 최종 렌더 후 게이트 실패는 0건이다. 서술 YAML은 수정하지 않았고 SHA-256 `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d`를 유지했다. git 쓰기는 하지 않았다.

## §1. 결함별 수정

| 결함 | 수정 및 검증 결과 |
|---|---|
| D1 표지 시장 데이터 | 기준 주가 `$1,097.39`, FQ4 희석주식수 `1,147M`, 계산 시가총액 `$1,258,706M`, FY 종료일 `2026-09-03`을 manifest fact로 채웠다. 두 가격 캡처는 E2-B 감사 읽기에 모두 포함됐다. |
| D2 표지 메타 | 발행일을 실제 최종 렌더일 `2026-10-04`, 자료 기준일을 `2026-10-01(주가) · 2026-09-30(실적)`, 정보 컷오프를 `2026-10-04 KST`로 렌더했다. G-25가 날짜 형식을 확인한다. |
| D3 표지 핵심 수치 | FQ4 PREREG_A/A-8K, FY26E/FY26A, FY27E/FY28E RLE 행을 동일 숫자 서식으로 구성했다. 모든 숫자는 manifest 참조로 렌더된다. |
| D4 SCORED 인용 | 3절에 매출·GAAP EPS·비GAAP EPS·GAAP opex의 실제/사전등록/오차/APE, 4개 라벨, 밴드, 4-lever, SF7을 추가했다. 새 G-3f가 pinned SCORED 원문을 재파싱해 각 fact의 값과 `SRC-SCORED-FQ4FY26` 출처를 대조한다. |
| D5 재무표 | EX-99.1의 FY26A 손익·재무상태·현금흐름, RLE YAML의 FY27E/FY28E를 채웠다. 세부 RLE가 제공되지 않은 R&D·SG&A 등과 컨센서스처럼 계약상 실제 미가용인 칸만 남겼다. |
| D6 차트 | ①②③b④에 FQ4 실제, ⑤에 FQ4 실제점과 FY27 bear/base/bull 무가중 3경로, ⑥·⑧에 FY26A 및 FY27E/FY28E를 연결했다. 차트 placeholder slot은 0개다. |
| D7 밸류에이션 | 기준 주가로 P/E·EV/EBITDA·EV/Sales·FCF yield, trailing P/B, 5×5 P/E 민감도 히트맵을 계산해 표와 차트 ⑦에 채웠다. |
| D8 원시 마크업 | inline Markdown을 HTML의 heading/strong/em/code로 변환하고 `####`도 별도 heading으로 처리했다. G-24는 양 PDF에서 `####`, `**`, backtick, brace, `source_id:`를 검사한다. |
| D9 부록 | YAML 사전 전체 덤프를 없애고 A1–A17별 규칙·핵심 입력·식·등급·출처 표로 축약했다. 특히 A11 분기 roll-forward의 장황한 내부 사전을 핵심 rate/합계/기말 PP&E로 줄였다. |
| D10 KO 부록 | 사후 변경 사유와 A11 해석을 한국어로 렌더하고 DRAM/NAND 정성 fact의 KO 표시도 번역했다. 기존 G-15b가 차트 UI와 영문 헤더만 검사해 본문 영어 문장을 놓친 것이 원인이었다. 강화판은 허용 용어를 제거한 뒤 연속 영단어 5개 이상을 실패시킨다. |
| G-21 KO 목차 | 마지막 목차 항목에서 본문 쪽수보다 footer 총쪽수를 선택하던 `page_numbers[-1]` 오류를 첫 목차 쪽수 선택으로 고쳤다. 최종 KO 16쪽·EN 18쪽의 목차와 실제 절 시작 쪽이 일치한다. |

추가로 최종 첫 렌더에서 드러난 G-4 FY26 재고일수 lineage를 `FY25 기말재고, FY26 기말재고, FY26 COGS, 53주` 네 입력으로 보완했다. 산식 값은 바꾸지 않았다.

## §2. 신설 게이트의 구 산출물 실패 증명

수정 전에 기존 ed1을 `logs/_mu_report_runs/ed1_r1_rejected/`로 이동해 보존하고 그 사본에 새 게이트를 실행했다.

- **G-23 RED**: 계획상 가용이어야 하는 21개 위치가 실패했다. 가격·주식수·시가총액·회계연도 종료일·자본·trailing P/B, FQ4 매출/GM/OP margin, FY26A 매출/순이익/EPS, FY27E/FY28E 매출·FCF·순현금 등이 포함됐다.
- **G-24 RED**: KO/EN 모두 PDF 3·4쪽에서 heading/bold 원시 표식, 13·14쪽에서 backtick/brace/`source_id:`가 검출됐다.
- **강화 G-15b RED**: KO판에서 `percentage range, driven by tight industry conditions and favorable mix` 영문 문장을 검출했다.
- **G-25 RED**: KO 표지의 발행일이 날짜가 아닌 자리표시 문구여서 실패했다.

즉, 네 게이트 모두 기존 결함을 실제로 재현한 뒤 수정본에 적용했다.

## §3. 전체 게이트

최종 실행: `python -m forecast.scripts.mu_report.build --phase E2-B --edition 1`

- 시작: `2026-10-04T17:00:59.637691+09:00`
- 이해관계 레코드 blob: `393cb05876f6f5aabf6fbdb98778c69b8c5d06b6`
- 결과: **PASS**, failures `{}`
- pre-render: G-1, G-2, G-3, G-3f, G-7, G-9, G-12, G-14, G-15 구조, G-17 설정, G-18, G-19, G-20 PASS
- post-render: G-4, G-5, G-6 KO/EN, G-8 KO/EN, G-10, G-11, G-12b, G-12c, G-13/G-13b/G-13c KO/EN, G-15, 강화 G-15b, G-16 16개 caption, G-17/G-17b, G-18, G-21, G-23, G-24, G-25 PASS
- G-23 감사: required failure 0, chart placeholder 0. 전체 미가용 위치 124개는 manifest 미가용 fact 3개와 KO/EN 표의 계약상 `NOT_IN_SOURCE`/`UNAVAILABLE` 위치를 포함한다. 전체 위치는 아래 runtime audit에 기록됐다.
- runtime audit: `logs/_mu_report_runs/e2b_20261004T170059+0900.json`, SHA-256 `7e0260e081ce9a11185044d22a2c2c9ec7ee887b0b026d18f262709276265f68`
- PDF 시각 QA: Poppler로 KO 16쪽·EN 18쪽 전 페이지를 PNG로 렌더해 표/차트/머리말/꼬리말/쪽수/절 전환을 확인했다. 잘림·겹침·깨진 glyph·원시 마크업은 없었다.

## §4. 산출물 SHA-256

| 파일 | bytes | SHA-256 |
|---|---:|---|
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 814,665 | `00106e6f00309d6c10c77792cecb26fbbff10fae4a34945c6ef97cc3d5dd5283` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 619,907 | `8752b13ee4d81cfdcadc84bee0cb1708fc37abcb31472ad53792b12298382d19` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 43,796 | `5dd8f5ed176bf2cce1e04f73a2bf3f4716700f13075a435212268c9748eac34e` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 43,694 | `155d779eb9660b79b79d6fd35972862ab16593fdefe4dbceee94ffadab29e479` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 26,318 | `52f134b89495ed4c7d7effed76f6f40efe75f245d258c1702cac0d7e2247244f` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 26,168 | `cd5365f69176c51922acc980eb1904499d96bfa15c5efd43b897d47fa0b14441` |
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 33,639 | `7f3e98e4b95b5ed78c1164a852afeb551638c29fb1dc066f525577c3b94ace21` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 374,308 | `297f94dea024b306df1a83597ed914381bc0b99cb81ff56c1715a2d4a42c9a4e` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |

차트 asset 16개의 SHA는 manifest의 chart fact/value 계약으로 검증했고, 파일별 SHA는 다음과 같다.

| asset | SHA-256 |
|---|---|
| `01_quarterly_revenue_margin_en.png` | `d69430ea4339d456ca05be74ae8d0f30c62b292d3ef5fa707d39b4ecdb270f25` |
| `01_quarterly_revenue_margin_ko.png` | `2636e62e1c82df11331c2f5710e6d1c416262bc54d07c801e12fdd63ec0104b2` |
| `02_business_unit_mix_en.png` | `227ffde29da2ae523fed036dd84208b7e6827e2f540d1c59d5d4b638e517b50b` |
| `02_business_unit_mix_ko.png` | `2fcaf2996163053c8cc72e458a13de859dc55e12286ba03d5c3e9d371c346aa9` |
| `03b_guidance_beat_history_en.png` | `27e7cfd681daebe67e2278aed5aa6afe8ffef0fb532e646f5693d8c0a3c808ea` |
| `03b_guidance_beat_history_ko.png` | `5b33e070265eef7e4198cc5ab273b81486bf5b90067f3ed8081ff6bb5dca3576` |
| `04_beat_history_en.png` | `085a16edf597842d78ecba2545c321f05daa2262399da1f3637823dd7c1f4638` |
| `04_beat_history_ko.png` | `cceefb7c18ba77dfd838fff296d4b2059e969dca30b6b1fbb324995ce4902b42` |
| `05_scenario_fan_en.png` | `dd82634eca3346a37fdd6164a5f44696c206aeaecb9e103c74428cf92445565d` |
| `05_scenario_fan_ko.png` | `7a5cbe1f72a09e145dbb9ce6ab818723e9ade7e8bde6011cceccda95aae9adf8` |
| `06_annual_income_en.png` | `78dea8b9997e713fc103e57dd32e040afdab65a72fac518b5af974a5bd8cd3dc` |
| `06_annual_income_ko.png` | `4390091c0cc03c0791f07cdcb9f7dd6231a4d6f9fabcb882ae2aec003a434b71` |
| `07_valuation_heatmap_en.png` | `73e989fe1218211cb249a4a10a1aa2776efc31ef809caa02df39f7297b6354a2` |
| `07_valuation_heatmap_ko.png` | `1d659bdaa9b9057de8846e2e050d869d3c31650c6ffab534491c1a77686f742f` |
| `08_cash_flow_capex_net_cash_en.png` | `1f8eaddf187dbfc7186b904b696a889eab0ecc0a561fb8dd8bb9ac74c8437189` |
| `08_cash_flow_capex_net_cash_ko.png` | `0a7230adfea1ddd412548080dc7ac4ea32a278aca2f6a91d7defa0003f576517` |

## §5. 테스트

- `python -m pytest forecast/tests/test_mu_report.py -q --basetemp ...` → **63 passed**. R16에 G-3f, FY28 annual RLE, G-23/24/25 RED·GREEN, 강화 G-15b, E2B KO/EN 차트·본문 통합 계약 테스트를 추가했다.
- `python -m pytest forecast/tests/ -q --basetemp ...` → **485 passed, 3 skipped, 1 deselected, 1 xfailed** (`53.56s`).
- skip 2건은 Windows symlink/process-group 제약, 1건은 gitignored EDGAR cache 부재다. xfail 1건은 기존 FYE-August Q1 라벨 이슈이며 이번 범위에서 수정하지 않았다.
- `.pytest_cache` 생성 권한 warning 1건이 있었으나 테스트 결과에는 영향이 없다.

이전 ed1 본체 9개와 당시 runtime log 및 asset 디렉터리는 `logs/_mu_report_runs/ed1_r1_rejected/`에 보존했다.
