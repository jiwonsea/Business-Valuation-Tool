# MU FY2026 Q4 ed1 개정 1 — R21 렌더 검증 r2

판정: **CHANGES REQUESTED — 자동 게이트 PASS / 시각 검증 FAIL 3건. E4 보류.**

투자 자문이 아니다. 사용자 지시대로 실패를 수정하지 않았고, 보고서 재렌더·git 쓰기·서술/숫자/RLE 규칙/이해관계 레코드 갱신을 하지 않았다. 이번 실행에서 발행 렌더는 아래 1회뿐이다. 테스트용 임시 fixture 생성과 기존 PDF의 QA용 이미지 변환은 발행 파일 재렌더가 아니다.

## 1. 렌더 명령·시각

```powershell
python -X utf8 -m forecast.scripts.mu_report.build --phase E2-B --edition 1
```

| 항목 | 확인 |
|---|---|
| 기준 커밋 | HEAD = origin/main = `9e4c667b1750e129027a31b730ed338289f0e9b4` |
| R20 리뷰 SHA-256 | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` 일치 |
| 서술 r3 SHA-256 | `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f` 일치 |
| 이해관계 레코드 | `not_held`, `ed1`, 확인 `2026-10-05T19:07:00+09:00` |
| 레코드 SHA-256 | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` |
| 레코드 Git blob SHA | `5248dd717931e990b427df597b7e433a13f359a4` — manifest/runtime와 일치 |
| 실제 렌더 시작 | **2026-10-05T19:12:03.608782+09:00** |
| 승인 기한 | 2026-10-06T19:07:00+09:00 **이전 충족** |
| 확인 후 경과 / 기한 잔여 | 00:05:03.608782 / 23:54:56.391218 |
| 종료 | exit 0, CLI `status: PASS`, `failures: {}` (자동 검사 결과) |
| runtime | `logs/_mu_report_runs/e2b_20261005T191203+0900.json` |
| runtime SHA-256 | `db353281ae50dc2826c0859ace4ccd06efed2ba04552b51935880f91c7dc2d5a` |

렌더 전후 scripts/i18n/tests/서술/가정/레코드/핸드오프/R20 리뷰 **22개 SHA 동일**. R20의 rev0 보존 25개는 `logs/_mu_report_runs/ed1_rev0_committed/`에 남아 있으며 R20 SHA 및 현재 HEAD의 Git blob 양쪽과 **25/25 일치**한다. 원격 조회·수정 없이 로컬 origin/main 참조를 확인했다.

## 2. 전체 게이트·시각 검증

### 2.1 자동 게이트

E2-B 사전 검사가 성공한 뒤에만 렌더 경로가 열렸고, 렌더 후 **60개 명명 검사 PASS, 실패 0건**. 자동 PASS를 시각적 출판 승인으로 해석하지 않는다.

| 게이트 | 결과·범위 |
|---|---|
| G-1·G-2 | PASS — 입력 경로/SHA, FROZEN 표시 불변 |
| G-3·G-3b·G-3c·G-3f | PASS — 손익/재무상태/현금흐름 항등식, SCORED 인용 원문 |
| G-4·G-5·G-6 | PASS — 재고일수, trailing P/B, KO/EN 시장 데이터 |
| G-7·G-8·G-9 | PASS — template/IO 경계, KO/EN theme, 정보 cutoff |
| G-10·G-11 | PASS — r3 서술 계약/신규 토큰, ed1 placeholder 경계 |
| G-12·G-12b·G-12c | PASS — fact manifest, 양언어 면책·미승인 고지, 레코드/실제 고지/24시간 유효성 |
| G-13·G-13b·G-13c | PASS — **16개/언어**, 이미지 수·fact identity·단위/순서/의미 계약 |
| G-14·G-15·G-15b | PASS — provenance, KO/EN 값/참조 동치, KO 문장·표 셀 UI |
| G-16 | PASS — 16개 × 2언어 = **32개 캡션** |
| G-17·G-17b | PASS — 양언어 라벨·컨센서스, `순현금(SCA 예치금 미조정)` |
| G-18·G-19·G-20 | PASS — 출처명/비밀정보 hygiene, bridge, E2-A/E2-B IO 감사 |
| G-21 | PASS — MD/HTML/PDF/XLSX, PDF font·footer·목차·쪽수 등 프로그램 검사 |
| G-23 | PASS — 필수 가용 셀 실패 `[]`, UNAVAILABLE 감사 **85개 위치** (문자열 위치 수, 셀 수 아님) |
| G-24 | PASS — PDF/XLSX 원시 마크업·FIXTURE/DRY RUN 문구·라벨 |
| G-25 | PASS — 표지 발행일/자료 기준일/정보 cutoff 날짜 |

신규 derived GM beat는 +7.41/+3.56/+0.76%p 표시. 기존 fact **759개 raw_value 불일치 0건**, 새 manifest **878개**. C14 `c14_missing: []`: FY24–FY26 **12분기 원천 확인, 제외 분기 없음**. 실적은 실선, FY27 RLE는 점선이며 추정·보간은 하지 않았다. C10 각주에 승인 구간 환산표와 **J(저자 판단), 회사 수치 아님**을 그대로 표시한다. 확률/확률가중과 회사 로고 이미지는 쓰지 않는다.

### 2.2 시각 검증 실패 목록 — 수정하지 않음

PDF는 KO 1–26쪽·EN 1–27쪽 **전 53쪽**, 차트는 C1–C16 × KO/EN **32개**를 이미지로 확인했다. XLSX는 Artifact Tool로 기존 파일을 읽어 Summary 시각 확인 및 전체 workbook 오류값 검색(0건)을 했다. XLSX를 다시 저장하지 않았다. PDF/스프레드시트 스킬은 QA용 이미지 확인·워크북 읽기 검사에만 적용했고, 실패 후 교정 단계는 R21 지시에 따라 실행하지 않았다.

| ID | 위치·증거 | 실패 |
|---|---|---|
| V1 | C9 KO PDF p.12·13 / EN PDF p.13·14; `09_gm_beat_compression_ko.png`, `09_gm_beat_compression_en.png` | 오른쪽 위에서 왼쪽 축의 QoQ 범례와 오른쪽 축의 FQ1 FY27 guidance 범례가 **겹쳐 읽기 어려움**. PNG 자체 결함이 HTML/PDF에도 포함됨 |
| V2 | C10 EN PDF p.7·15; `10_price_bit_ranges_en.png` | 제목 `Figure 10. DRAM and NAND price and bit changes (company ranges)`의 오른쪽 끝 **잘림**. 이미지 우측 경계 밖으로 제목이 나감 |
| V3 | C11 EN PDF p.10; `11_eps_error_waterfall_en.png` | x축 `OP→NI`의 **→ 누락**, 표시가 `OPNI`로 보임. 렌더의 Noto Sans U+2192 missing-glyph 경고 2건과 일치 |

이는 자동 G-13/G-13c/G-15b/G-21이 잡지 못한 **시각 검증 실패**다. 자동 검사 실패를 3건이라고 바꾸거나, 전체 PASS로 보고하지 않는다. 실패 후 코드·폰트·스타일·숫자·문구를 고치거나 발행 산출물을 재생성하지 않았다.

QA 증거: `logs/_mu_report_runs/ed1rev1_r21_20261005T191203/`의 `pages/ko-01.png…ko-26.png`, `pages/en-01.png…en-27.png`, `pages_*.png` contact sheets, `charts_*.png`, `summary_xlsx.png`. 이미지 변환 도구의 nameToUnicode 리소스 경고는 환경 경고로 별도 취급했고, 전 쪽 생성/확인이 완료됐다. 모든 QA·runtime·보존 경로는 gitignore 대상이며 E4 제외.

## 3. 산출물 SHA·쪽수

파일명은 ed1 그대로, 내부 판 표시 **제1판 개정 1 / Edition 1, Revision 1**. KO **26쪽**, EN **27쪽**; manifest의 쪽수와 PDF 실물 일치. 아래 41개는 실제 디스크 바이트 SHA-256이다. **검증 실패본이며 출판 승인본이 아니다.**

| 경로 | 쪽수/크기 | gitignore 규칙 대상 | SHA-256 |
|---|---|---|---|
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 40,808 bytes | 예 | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 59,190 bytes | 예 | `641b40e0283336be78d7cec52d466a60288e03d061f7315312a2e51b9fbcf4bd` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 38,472 bytes | 아니오 | `d2845de366ea52df39272881a5347c4190f124966347506e528b079b11d8cfe8` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 27쪽 | 예 | `e58af25ccf448f5c32852fa55df6163d1bfebc357c286f73aca2ea38c0573d06` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 bytes | 아니오 | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 59,238 bytes | 예 | `7fff91cf51d93eb8c211bcf1a1e21cc657a50d2a11966a3a54d97ca4404ff7ec` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 38,568 bytes | 아니오 | `e42fdf57789030a100afadddbc6123df8491f82c0bcfa7d69b2dab7b0dc9440e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 26쪽 | 예 | `57a823bb63159d89a732e246d864ee121c74fcafd97aab13e855cc24850edd7b` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 458,037 bytes | 아니오 | `616c28c50c75af9da947c443dda4b6ad063864747c140e626e9735bb536a256b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png` | 54,478 bytes | 아니오 | `d69430ea4339d456ca05be74ae8d0f30c62b292d3ef5fa707d39b4ecdb270f25` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png` | 49,312 bytes | 아니오 | `2636e62e1c82df11331c2f5710e6d1c416262bc54d07c801e12fdd63ec0104b2` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png` | 24,872 bytes | 아니오 | `227ffde29da2ae523fed036dd84208b7e6827e2f540d1c59d5d4b638e517b50b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png` | 21,443 bytes | 아니오 | `2fcaf2996163053c8cc72e458a13de859dc55e12286ba03d5c3e9d371c346aa9` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png` | 45,378 bytes | 아니오 | `27e7cfd681daebe67e2278aed5aa6afe8ffef0fb532e646f5693d8c0a3c808ea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png` | 41,558 bytes | 아니오 | `5b33e070265eef7e4198cc5ab273b81486bf5b90067f3ed8081ff6bb5dca3576` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png` | 26,699 bytes | 아니오 | `085a16edf597842d78ecba2545c321f05daa2262399da1f3637823dd7c1f4638` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png` | 23,551 bytes | 아니오 | `cceefb7c18ba77dfd838fff296d4b2059e969dca30b6b1fbb324995ce4902b42` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png` | 50,125 bytes | 아니오 | `dd82634eca3346a37fdd6164a5f44696c206aeaecb9e103c74428cf92445565d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png` | 48,207 bytes | 아니오 | `7a5cbe1f72a09e145dbb9ce6ab818723e9ade7e8bde6011cceccda95aae9adf8` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png` | 32,389 bytes | 아니오 | `78dea8b9997e713fc103e57dd32e040afdab65a72fac518b5af974a5bd8cd3dc` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png` | 28,176 bytes | 아니오 | `4390091c0cc03c0791f07cdcb9f7dd6231a4d6f9fabcb882ae2aec003a434b71` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png` | 47,620 bytes | 아니오 | `fd819824abb8cc8d27172249e0c8c61838707b1403a0ebfb7f9c91d40640aeea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png` | 42,764 bytes | 아니오 | `1ead96ea05256a65cf22b0f72bd95574141f845c901215537f836b3b58a5830d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png` | 32,935 bytes | 아니오 | `1ee978d72fba7f4ba25afbc490f98bcaefc07e8706ed2b4ebff2ab0f9c0840f0` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png` | 32,851 bytes | 아니오 | `0a7230adfea1ddd412548080dc7ac4ea32a278aca2f6a91d7defa0003f576517` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png` | 46,773 bytes | 아니오 | `dc388bcd1bed1390c97ec36bfadec817293c26aa4d02dd69584260f10f1e71fd` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png` | 39,716 bytes | 아니오 | `4c75c90b2572f7e8b863f211c2f310c30f774aa475c6c1555101bc941f1dd8f5` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png` | 39,554 bytes | 아니오 | `0b8bbc634d6b71b22578d339d050e3f8b58431eb87fce7c75eab5f788cac48a6` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png` | 34,455 bytes | 아니오 | `5578248ce1f167bcda6fe71348a8207b8ed5492639779b6806adc1b1c2fbfd95` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png` | 26,977 bytes | 아니오 | `dd0894379c3f9f7584849a15c383a8f4abcf47947e6d40ef90f26e6b022f8f7d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png` | 22,337 bytes | 아니오 | `e9e24580e7ce7a8677cc40d8f6356feac01aed188038ffe1feac02cc291da345` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png` | 41,939 bytes | 아니오 | `33796360a0f9ce5148ca12976acda8d35cd2c50e83abd06ebfbbb0020171994f` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png` | 37,014 bytes | 아니오 | `df81f76623fa4617d900edaaebad7fc7bbc0231c1a5019015c7ea8cf5ad2b0a7` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png` | 29,840 bytes | 아니오 | `478b27bf61c194b4e96f027498f413930c084a64c8816b6bf82cbee904e16a25` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png` | 23,310 bytes | 아니오 | `187f1203d9853a6574f780365d82fa9556ca62d40a8d5a426a4d2ed2b44e98d6` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png` | 47,111 bytes | 아니오 | `6299284ce08102b595f60443c194abe5c8236487764d42ed19366fa56ef623aa` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png` | 41,868 bytes | 아니오 | `749d0507248fa532f97f5ed59882e63b67088ead1dba2eaa5511820829edf2ea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png` | 31,333 bytes | 아니오 | `d8beb0bc19fa5d1bf9ef72d500e991cefe13e56636f54cba59a136603dd7db52` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png` | 26,593 bytes | 아니오 | `33d5c6e3c0cdde29d4a407c8c468ea8ec1c76f9b497bc8210ce20ec056b9e5e2` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png` | 31,381 bytes | 아니오 | `7781b86befe41c379cc6053fa5c58cea8135f557ee936719fad5513121cc60ff` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png` | 26,432 bytes | 아니오 | `25ba5680a9330f026bf136b047b71c4a68df5a33b3954198b13c485dc89563c2` |

기존 C1–C8 PNG 16개는 rev0와 **동일 SHA**이므로 §5 변경 후보에서 제외한다. 다른 D7 파일 9개와 새 C9–C16 PNG 16개는 후보에 포함한다.

## 4. 테스트

```powershell
python -X utf8 -m pytest forecast/tests/ -q -p no:cacheprovider
python -X utf8 -m pytest forecast/tests/test_disclosure_loader.py::test_fetch_dart_mdna_nonempty -q -p no:cacheprovider -m network
git --no-optional-locks diff --check -- forecast
```

| 실행 | 결과 |
|---|---|
| forecast 전체 기본 실행 | **532 passed, 3 skipped, 1 deselected, 1 xfailed, 2 warnings in 92.09s**, exit 0 |
| 기본 제외된 network 항목 별도 실행 | **1 passed in 1.33s**, exit 0 |
| 합계 | **533 passed, 3 skipped, 1 xfailed**, 최종 미실행 deselected 0건, 새 테스트 실패 0건 |
| R20 제외 렌더 항목 | **11개 함수 / 12개 테스트 항목 전부 기본 전체 실행에 포함, PASS** |
| DRYRUN 회귀 | 기존 E2-A 경로/fixture/placeholder/경계/edition 검증 포함 PASS |
| diff 공백 검사 | PASS, 읽기 전용 |

3개 skip은 기존 Windows symlink 권한, Windows process-group 의미 미지원, TXN EDGAR 파생 캐시 부재다. 1개 xfail은 기존 MU FYE-August Q1 라벨 문제다. 해결하지 않았다. 기본 실행의 1 deselected는 프로젝트 설정 `-m 'not network'`에 따른 DART 읽기 검사였으며 별도 실행했다. 이 검사는 입력 pin을 갱신하지 않으며 MU 실적 근거로 사용하지 않는다. 전체 범위는 이번 핸드오프의 forecast 테스트 전체이며 관련 없는 루트 valuation 테스트는 대상이 아니다.

경고 2건은 `test_r16_e2b_markdown_and_chart_contracts_pass_together`의 U+2192 누락으로 V3와 같은 원인이다. 통과 테스트가 시각 결함 부재를 입증하지 않는다. 부록 R20에서 보류한 정확한 렌더 함수는 아래와 같으며, 이번에는 제외식을 쓰지 않았다.

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

## 5. E4 후보 목록 — 실패로 진행 보류

**40개 후보 = 선행 R20 코드/테스트/입력/핸드오프/리뷰 14개 + 변경 D7 9개 + 신규 PNG 16개 + 본 리뷰 1개.** 현재 상태 기록이지 승인/커밋 명령이 아니다. V1–V3가 남아 있으므로 **E4 커밋·push 진행 보류**. git add/commit/amend/push 등 쓰기 작업을 실행하지 않았다.

아래 레코드·핸드오프·서술은 사용자/Claude 선행 변경이며 이번에는 읽기만 했다. scripts/tests는 R20 변경 그대로다. gitignore 열은 `check-ignore --no-index`의 **규칙 적용 여부**이며, 이미 추적된 PDF/HTML/XLSX가 Git에서 사라진다는 뜻이 아니다.

| 경로 | gitignore 규칙 대상 | SHA-256 |
|---|---|---|
| `forecast/scripts/mu_report/build.py` | 아니오 | `fcf14d6cd9ddf2e67a961dd5ac1420d916919c0ba2c074f319bac46d9e3a5983` |
| `forecast/scripts/mu_report/charts.py` | 아니오 | `e16246cee7175f87b7894efaa61ef38432ddd637fd7468c46208a94251fbf751` |
| `forecast/scripts/mu_report/gates.py` | 아니오 | `fc8d7c7c9bb5554c9e1a3131a4a8c7d3a7f79d6fcf0df70fae336e1da0b6983a` |
| `forecast/scripts/mu_report/i18n/ko.yaml` | 아니오 | `238491820d4f48c258f1a87a9853c1a84554dd34c6f0f156e4fcc441e065633b` |
| `forecast/scripts/mu_report/i18n/en.yaml` | 아니오 | `28adf176a496727a9dd9054f5591f80ea7163e7589d5c8d0cac06d107c182c2c` |
| `forecast/scripts/mu_report/narrative.py` | 아니오 | `963732d9ded36c3327c0029c5d495d1ad66a61ed01677221c9ed448f63f6ee11` |
| `forecast/scripts/mu_report/render.py` | 아니오 | `b3fa03d197a25748d73bc151b5d00a4c316bb8a684dd123350ca9d8872fd3175` |
| `forecast/scripts/mu_report/revision.py` | 아니오 | `9587d9409dc5f5a60f05b195bf34b864803024f8f90b1b81847671f848e92f45` |
| `forecast/tests/test_mu_report.py` | 아니오 | `1e66715930f9b6e246bcb41427477700cc5587fefdb1f90bfd720cda239e6cf5` |
| `forecast/tests/test_mu_report_revision.py` | 아니오 | `c944823b5ae3cb0b9ad4386c5a1a96006a99910bdbb7348288f250203026c81c` |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | 아니오 | `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f` |
| `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` | 아니오 | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | 아니오 | `daede0d1fe046cc49d5321058305f5d5d35d415107a60a66e7001009c359e869` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md` | 아니오 | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` |
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 예 | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 예 | `641b40e0283336be78d7cec52d466a60288e03d061f7315312a2e51b9fbcf4bd` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 아니오 | `d2845de366ea52df39272881a5347c4190f124966347506e528b079b11d8cfe8` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 예 | `e58af25ccf448f5c32852fa55df6163d1bfebc357c286f73aca2ea38c0573d06` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 아니오 | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 예 | `7fff91cf51d93eb8c211bcf1a1e21cc657a50d2a11966a3a54d97ca4404ff7ec` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 아니오 | `e42fdf57789030a100afadddbc6123df8491f82c0bcfa7d69b2dab7b0dc9440e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 예 | `57a823bb63159d89a732e246d864ee121c74fcafd97aab13e855cc24850edd7b` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 아니오 | `616c28c50c75af9da947c443dda4b6ad063864747c140e626e9735bb536a256b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png` | 아니오 | `dc388bcd1bed1390c97ec36bfadec817293c26aa4d02dd69584260f10f1e71fd` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png` | 아니오 | `4c75c90b2572f7e8b863f211c2f310c30f774aa475c6c1555101bc941f1dd8f5` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png` | 아니오 | `0b8bbc634d6b71b22578d339d050e3f8b58431eb87fce7c75eab5f788cac48a6` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png` | 아니오 | `5578248ce1f167bcda6fe71348a8207b8ed5492639779b6806adc1b1c2fbfd95` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png` | 아니오 | `dd0894379c3f9f7584849a15c383a8f4abcf47947e6d40ef90f26e6b022f8f7d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png` | 아니오 | `e9e24580e7ce7a8677cc40d8f6356feac01aed188038ffe1feac02cc291da345` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png` | 아니오 | `33796360a0f9ce5148ca12976acda8d35cd2c50e83abd06ebfbbb0020171994f` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png` | 아니오 | `df81f76623fa4617d900edaaebad7fc7bbc0231c1a5019015c7ea8cf5ad2b0a7` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png` | 아니오 | `478b27bf61c194b4e96f027498f413930c084a64c8816b6bf82cbee904e16a25` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png` | 아니오 | `187f1203d9853a6574f780365d82fa9556ca62d40a8d5a426a4d2ed2b44e98d6` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png` | 아니오 | `6299284ce08102b595f60443c194abe5c8236487764d42ed19366fa56ef623aa` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png` | 아니오 | `749d0507248fa532f97f5ed59882e63b67088ead1dba2eaa5511820829edf2ea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png` | 아니오 | `d8beb0bc19fa5d1bf9ef72d500e991cefe13e56636f54cba59a136603dd7db52` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png` | 아니오 | `33d5c6e3c0cdde29d4a407c8c468ea8ec1c76f9b497bc8210ce20ec056b9e5e2` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png` | 아니오 | `7781b86befe41c379cc6053fa5c58cea8135f557ee936719fad5513121cc60ff` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png` | 아니오 | `25ba5680a9330f026bf136b047b71c4a68df5a33b3954198b13c485dc89563c2` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md` | 아니오 | 자기참조 SHA는 본문에 넣지 않음; 완성 파일 외부 해시로 확인 |

제외: 원본과 동일한 기존 PNG 16개, RLE 가정 YAML·가격·원천 pin·SCORED·FROZEN(변경 없음), `logs/**`(runtime/QA/rev0 보존), 기존 `_assets/pages/**`·`pages_final/**`·`pages_r18/**` QA 파일, `forecast/HANDOFF_CODEX_mu_report_survey_r4.md`, rev-4~4.3 보존본, 관련 없는 CLAUDE.md 등 기존 작업 트리 변경. 오래된 QA 페이지를 이번 개정판 페이지로 취급하거나 커밋 후보에 넣지 않았다.

---

본 문서는 투자 자문이 아니다. This document is not investment advice.

