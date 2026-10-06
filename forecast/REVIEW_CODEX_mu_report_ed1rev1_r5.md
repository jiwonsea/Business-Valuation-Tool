# MU FY2026 Q4 ed1 개정 1 — R24 최종 검토 r5

판정: **PASS**. P1–P5 완료, 발행 렌더 **1/1회**, 렌더 후 게이트 **62 PASS / 0 FAIL**, 전체 forecast 테스트 **577 PASS / 3 SKIP / 1 XFAIL / 0 FAIL**(network 분리 실행 합산). KO 24쪽·EN 26쪽 전 쪽 이미지와 XLSX Summary 미리보기를 확인했다. 아래 E4는 **후보 목록만**이며 staging·commit·amend·push를 실행하지 않았다.

근거: R24 핸드오프 `2b346dd3e16594d9d509e9e2edd0fb812c146fe1429d48f712a356a2eaf5e423`. 사용자의 “Run R24”를 부록 머리의 실행 승인으로 확인했다. 서술 YAML·숫자·RLE 규칙·이해관계 레코드·로고는 변경하지 않았다. 이는 발행물 표시 검증이며 새로운 실적 채점 또는 투자 자문이 아니다.

## §1. P1–P5 조치 및 증거

| ID | 조치 | 렌더 후 증거 |
|---|---|---|
| P1 | 발표 후 변경표 마지막 헤더를 KO `쪽`, EN `Page`로 표시했다. 표 셀에 `word-break:keep-all; overflow-wrap:normal; hyphens:none`을 적용했다. 기존 13/22/23/35/7% 열 폭·마지막 열 가운데 정렬은 유지했다. i18n YAML 원문은 변경하지 않았다. | KO p.23 [ko-23.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/ko-23.png>), EN p.25 [en-25.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/en-25.png>). 짧은 헤더가 한 단어로 보이고 표는 본문 폭 안에 있다. R23 실제 페이지 헤더/부록 표 폭 검사 PASS. |
| P2 | Summary A1의 16pt 글꼴을 유지하고 제목 행을 `font_size × 1.5 + 8 = 32pt`로 설정했다. A1 수직 가운데 정렬. 기존 기본 행 높이(명시값 없음, 기본 15pt)로 발생한 제목 잘림을 해소했다. | [summary_xlsx.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/summary_xlsx.png>). 제목 전체가 보인다. Summary/Facts의 모든 셀 값·수식은 R24 시작 전과 완전히 동일하다. |
| P3 | GAAP opex 예측 라벨만 KO `해당 없음(가이던스 없음)`, EN `n/a (no guidance)`로 바꿨다. 결과 `서술 실패` / `Narrative failure` 유지. 아래 지정 각주를 각 언어 1회 표시했다. | KO p.9 [ko-09.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/ko-09.png>), EN p.10 [en-10.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/en-10.png>). manifest raw의 `(d-1)` 원문을 보존하여 G-3f 계약을 유지했다. |
| P4 | 부록 적용 값의 비율만 소수에서 %로 표시(소수 둘째 자리)하고 상태 코드에 독자용 KO/EN 매핑을 적용했다. 금액·주식수·EPS·DPS와 raw·XLSX는 그대로다. G-15b에 원시 상태 코드 금지 검사를 추가했다. | KO p.22–23 [ko-22.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/ko-22.png>) · [ko-23.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/ko-23.png>), EN p.24–25 [en-24.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/en-24.png>) · [en-25.png](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/qa_pages/r24/en-25.png>). `84.95%, 13.67%, 3.45%, −0.23%, 17.29%, 4.32%, 19.05%` 표시 확인. |
| P5 | 기존 QA 네 폴더를 logs로 **이동**했고 198개 파일 전후 SHA가 전부 일치했다. r1–r4 리뷰는 수정하지 않았다. 이번 QA도 logs 아래 저장했다. | assets에는 발행 PNG **32개**, 하위 디렉터리 **0개**만 남았다. 이동표는 아래. |

P3 각주는 핸드오프 지정 문장을 그대로 사용했다.

> GAAP 영업비용은 회사 가이던스가 없어 라벨 채점 대상이 아니다. 실제가 사전등록 기준보다 77% 많아 서술 실패로 기록했다(SCORED §4).

> GAAP opex had no company guidance, so it is not label-scored; actual exceeded the pre-registered base by 77%, recorded as a narrative failure (SCORED §4).

77%는 SCORED §4의 기존 +77%를 인용한 것이다. 새 계산이나 판정 변경이 아니다. 원문 fact `scored.verdict.4.4.FQ4FY26`의 raw에는 `(d-1)`가 남아 있으며 표시 행에서만 제거했다.

P4 표시 대상: A2 성장률, A2prime 관측 방향, A3 GM, A5 영업이익 아래 차감 비율, A6 세율, A7 민감도 축소 비율, A8 성장률, A9 GM, A11 연간/분기 비율, A12 SBC 비율, A13 k, A14 민감도 비율. `11500/13500/12500/12500` 같은 금액과 분기 DPS `0.15`는 %로 변환하지 않았다. 적용 값의 `FQ1 weekly direction <= -0.02`는 같은 임계값을 KO `FQ1 주당 성장률 ≤ −2%`, EN `FQ1 weekly growth ≤ −2%`로 표시했다. 저장된 규칙 문자열/숫자는 불변이다.

| raw 상태 | KO 표시 | EN 표시 |
|---|---|---|
| AVAILABLE | 가용 | available |
| AVAILABLE_BACKSOLVED | 역산 가용 | available (backsolved) |
| PASS_GAAP | GAAP 기준 통과 | GAAP pass |
| NOT_ACTIVATED | 미발동 | not activated |
| UNAVAILABLE | 추정하지 않음 | not estimated |
| UNAVAILABLE_WITHOUT_ASSUMPTIONS | 가정이 없어 추정하지 않음 | not estimated (no assumption) |

G-15b는 두 언어의 표시 본문/표에서 `AVAILABLE`, `AVAILABLE_BACKSOLVED`, `UNAVAILABLE_WITHOUT_ASSUMPTIONS`, `NOT_ACTIVATED`, `PASS_GAAP`의 원시 코드 노출을 실패시킨다. 단독 `UNAVAILABLE`는 기존 정보 경계 설명과 G-17 필수 라벨에 쓰이므로 전역 금지하지 않았다. 부록 규칙표에서는 이 코드도 위 표의 독자용 표현으로 변환한다. G-23의 기존 미가용 항목/정보 경계 5곳은 허용 상태 그대로이며 required 실패는 없다.

### QA 보존 및 입력 불변

이동 전 접두사는 `forecast/reports/mu_report_fy2026q4_ed1_assets/`, 이동 후 접두사는 `logs/_mu_report_runs/qa_pages/`이다.

| 원래 폴더 | 이동 후 폴더 | 파일 수 | SHA 불일치 |
|---|---|---:|---:|
| pages/ | logs/_mu_report_runs/qa_pages/pages/ | 42 | 0 |
| pages_final/ | logs/_mu_report_runs/qa_pages/pages_final/ | 39 | 0 |
| pages_r18/ | logs/_mu_report_runs/qa_pages/pages_r18/ | 45 | 0 |
| pages_r23/ | logs/_mu_report_runs/qa_pages/pages_r23/ | 72 | 0 |
| 합계 | 이동, 삭제 아님 | 198 | 0 |

r1–r4의 종전 QA 링크는 이동 전 경로이므로 이 표로 새 위치를 찾는다. 리뷰 본문/바이트를 고치지 않았으며 아래 SHA도 유지했다. 신규 QA는 `logs/_mu_report_runs/qa_pages/r24/`에 KO 24개·EN 26개 150dpi 페이지 이미지, 전 쪽 모음 13개, XLSX 미리보기를 보관했다. [cbacb4d ed1 rev0 보존본](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1_rev0_committed/>) 25개도 R20 SHA 목록과 **25/25 일치**하여 별도 보존되어 있다.

| 보호 대상 | SHA-256(변경 없음) |
|---|---|
| narrative r4 | `8fee9e26f59222ae062a83c450759e91fb90f6a69e1cbceea156f549478bbec0` |
| report assumptions | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` |
| conflict confirmation | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` |
| 리뷰 r1 | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` |
| 리뷰 r2 | `3e17e43411db57df3ececdb6467826a6398cb5c4b4b13919daa8f363efd4efc7` |
| 리뷰 r3 | `04e20fbcf118242729a62e5b265076ac55ef8b047f834cc93d62b55c60c6f190` |
| 리뷰 r4 | `94150bca97f8a9f526f0f974b1a1d4e1b149bb631fd63b62077f8eeacef6aaef` |

R24의 소스 수정은 `render.py`, `narrative.py`, `gates.py` 및 신규 `test_mu_report_r24.py`에 한정된다. 서술 YAML은 수정하지 않았다. report/PDF/spreadsheets 스킬은 기존 발행 파이프라인을 유지하며 PDF 전 쪽·XLSX 미리보기 및 불변성을 검증하는 데 사용했다. XLSX는 기존 템플릿 작성 경로를 유지하고 artifact-tool은 읽기 전용 검증/미리보기에만 사용하여 재저장·재계산에 의한 값 변화가 없도록 했다.

## §2. 게이트 및 테스트

### 렌더 및 시간 제약

발행 명령:

```powershell
python -X utf8 -m forecast.scripts.mu_report.build --phase E2B --edition 1
```

- 시작: **2026-10-05T22:29:55.182665+09:00**, 제한 **2026-10-06 19:07 KST 이전** 충족.
- 이해관계 레코드: `not_held`, `ed1`, `confirmed_at_kst: 2026-10-05T19:07:00+09:00`. 유효한 24시간 창 안에서 시작; 레코드 갱신 없음.
- 레코드 git blob SHA: `5248dd717931e990b427df597b7e433a13f359a4`.
- 발행 렌더 **1회**, 종료 코드 **0**, status **PASS**, failures `{}`. 테스트의 fixture/DRYRUN/레이아웃 검사 렌더와 발행 렌더를 구분했다. 발행물 추가 렌더 없음.
- 사전 E2B 게이트가 모두 통과한 뒤 발행 렌더가 시작되었다. 아래 62개는 **렌더 후 게이트**이며 사전 검사 횟수와 혼합하지 않았다.
- 실행 증거: [logs/_mu_report_runs/e2b_20261005T222955+0900.json](<F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/e2b_20261005T222955+0900.json>) — SHA-256 `feeebfcefccac46d488ebfc2cb873cc902116c69e0f9612915161e69638d3e1f`.

렌더 후 PASS 목록(62):

```text
G-10 narrative contract
G-11 ed1 placeholders
G-12b disclaimers
G-12c conflict
G-13 charts en
G-13 charts ko
G-13b chart identity en
G-13b chart identity ko
G-13c chart semantics en
G-13c chart semantics ko
G-15 parity
G-15b localized UI
G-16 caption en/01_quarterly_revenue_margin
G-16 caption en/02_business_unit_mix
G-16 caption en/03b_guidance_beat_history
G-16 caption en/04_beat_history
G-16 caption en/05_scenario_fan
G-16 caption en/06_annual_income
G-16 caption en/07_valuation_heatmap
G-16 caption en/08_cash_flow_capex_net_cash
G-16 caption en/09_gm_beat_compression
G-16 caption en/10_price_bit_ranges
G-16 caption en/11_eps_error_waterfall
G-16 caption en/12_fq1_guidance_comparison
G-16 caption en/13_scenario_sensitivity_eps
G-16 caption en/14_opex_net_capex_trend
G-16 caption en/15_operating_income_waterfall
G-16 caption en/16_sca_structure
G-16 caption ko/01_quarterly_revenue_margin
G-16 caption ko/02_business_unit_mix
G-16 caption ko/03b_guidance_beat_history
G-16 caption ko/04_beat_history
G-16 caption ko/05_scenario_fan
G-16 caption ko/06_annual_income
G-16 caption ko/07_valuation_heatmap
G-16 caption ko/08_cash_flow_capex_net_cash
G-16 caption ko/09_gm_beat_compression
G-16 caption ko/10_price_bit_ranges
G-16 caption ko/11_eps_error_waterfall
G-16 caption ko/12_fq1_guidance_comparison
G-16 caption ko/13_scenario_sensitivity_eps
G-16 caption ko/14_opex_net_capex_trend
G-16 caption ko/15_operating_income_waterfall
G-16 caption ko/16_sca_structure
G-17 corrected net-cash label
G-17 labels en
G-17 labels ko
G-17b consensus en
G-17b consensus ko
G-18 hygiene
G-21 formats
G-23 availability audit
G-24 PDF/XLSX markup and labels
G-25 cover dates
G-4 inventory days
G-5 trailing P/B
G-6 market data en
G-6 market data ko
G-8 theme en
G-8 theme ko
R22 presentation/glyph/bbox/Bold
R23 header/table/font geometry
```

G-24는 PDF/XLSX 양쪽의 markup/발행 라벨을 확인했고, R22 검사에 Bold·glyph·차트 bbox, R23 검사에 실제 페이지 헤더·부록 표 폭·최소 글꼴 크기가 포함된다. G-15b에는 P4의 두 언어 원시 상태 코드 검사도 포함된다.

### 테스트: 실패 증명 → 수정 → 전체 회귀

`forecast/tests/test_mu_report_r24.py` 17개를 수정 전 실행해 **17 FAIL**을 확인했다. 그중 P1 헤더/CSS 2개, P2 행 높이 1개, P3 표시/raw 보존 2개, P4 %/상태 표시 2개, 5종 raw 상태 × 2언어 금지 10개다. 최초 테스트 setup의 누락 인자는 바로잡고 유효한 baseline을 다시 실행했으며, **제품 결함 증명은 그 후의 17 FAIL 실행**을 기준으로 했다.

| 실행 | 결과 |
|---|---|
| R24 신규 대상 테스트 — 수정 후 | 17 PASS(5.33초); 비율 임계값 표시까지 보완 후 17 PASS(7.24초) |
| 발행 전 전체 forecast, network 제외 | 576 PASS / 3 SKIP / 1 deselected / 1 XFAIL, 260.42초 |
| 발행 후 전체 forecast, network 제외 | 576 PASS / 3 SKIP / 1 deselected / 1 XFAIL, 268.10초 |
| network 제외된 실제 DART 테스트 별도 실행 | 1 PASS, 0.68초 |
| 발행 후 전체 합계(중복 없이) | **577 PASS / 3 SKIP / 1 XFAIL / 0 FAIL**, network 미실행 없음 |

```powershell
python -X utf8 -m pytest forecast/tests/ -q -m 'not network' -p no:cacheprovider --basetemp=forecast/tests/.tmp_r24_prerender
python -X utf8 -m pytest forecast/tests/ -q -m 'not network' -p no:cacheprovider --basetemp=forecast/tests/.tmp_r24_postrender
python -X utf8 -m pytest forecast/tests/test_disclosure_loader.py::test_fetch_dart_mdna_nonempty -q -m network -p no:cacheprovider --basetemp=forecast/tests/.tmp_r24_network
```

기존 렌더 테스트·E2-A/DRYRUN 계약·실제 YAML RLE 재현·FROZEN 무결성·재무 항등식·F1/F2/F5 표시 문자열 대조도 전체 회귀 대상에 포함됐다. SKIP은 Windows symlink 권한, Windows process-group 미지원, gitignore된 파생 EDGAR 캐시 부재의 3개다. XFAIL은 기존 FYE-August Q1 EDGAR 기간 라벨 문제(`NOTICED BUT NOT TOUCHING`)이며 R24 범위 밖이다. 테스트 종료 후 이번 테스트가 생성한 정확한 임시 폴더 `.tmp_r24_prerender`, `.tmp_r24_postrender` 두 개만 정리했다(재생성 가능한 fixture). 발행물·QA·보존본은 삭제하지 않았다. 소스 `git diff --check`도 통과했다.

### 숫자 및 시각 보존

- manifest fact **878/878** 객체(raw·display·provenance 포함)가 R24 시작 전과 같다. 추가/삭제/변경 **0**.
- manifest 및 input_manifest 바이트/SHA도 R23 상태와 동일하다.
- 발행 차트 PNG **32/32**가 R23과 바이트 단위로 동일하다. 차트 원천/숫자/추정 규칙 변경 **0**.
- XLSX의 Summary/Facts 모든 셀 값·수식이 baseline과 동일하다. ZIP 구성 중 변경은 `xl/styles.xml`, `xl/worksheets/sheet1.xml` 두 개(제목 정렬·행 높이)뿐이다. Facts XML, workbook metadata, 다른 XML 모두 불변이다.
- KO 24쪽·EN 26쪽을 150dpi로 변환하고 13개 전 쪽 모음으로 **50/50쪽 확인**했다. 해당 수정 부분은 개별 확대 이미지도 확인했다. 새 missing-glyph 실패, 겹친 헤더, 변경표 끝 열 잘림, A1 제목 잘림은 발견되지 않았다. PDF 변환기의 언어명 ToUnicode 지원 경고는 페이지 누락/glyph 결함이 아니며 변환은 종료 코드 0, 페이지 이미지 50개다.

## §3. 최종 산출물 SHA 및 쪽수

| 종류 | 파일 | bytes | SHA-256 | PDF 쪽수 |
|---|---|---:|---|---:|
| html_en | [forecast/reports/mu_report_fy2026q4_ed1_en.html](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.html>) | 65,935 | `bc07ad11860e429746109855ebe370af4c2cae7796e58ebf37f8776bba292241` | — |
| html_ko | [forecast/reports/mu_report_fy2026q4_ed1_ko.html](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.html>) | 65,942 | `abe5261d462b2faf995c1ab6a66311ec50c70898a26db65884ec89f7fe1bf30e` | — |
| input_manifest | [forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json>) | 5,546 | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` | — |
| manifest | [forecast/reports/mu_report_fy2026q4_ed1_manifest.json](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_manifest.json>) | 458,631 | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` | — |
| md_en | [forecast/reports/mu_report_fy2026q4_ed1_en.md](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.md>) | 41,717 | `42871bf0fe1ec50f989cb91237e5de917dea6a4011ad59850400c63b01378f49` | — |
| md_ko | [forecast/reports/mu_report_fy2026q4_ed1_ko.md](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.md>) | 41,809 | `b2ca803b2b368695857560bbc827991afcf8390a04ea90ed03433bc2227db82d` | — |
| pdf_en | [forecast/reports/mu_report_fy2026q4_ed1_en.pdf](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.pdf>) | 619,569 | `154cf9aae1dbb94d9d005c4f3ce2cb63c10fb70b28b4f5c0d1be90ae73bb1fd8` | 26 |
| pdf_ko | [forecast/reports/mu_report_fy2026q4_ed1_ko.pdf](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.pdf>) | 607,214 | `8419b2cb364a0bde4f3b5dbb0c49fd390bde1d59839887d1255890d21c21d114` | 24 |
| xlsx | [forecast/reports/mu_report_fy2026q4_ed1_data.xlsx](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_data.xlsx>) | 40,816 | `9df8bf80d8ef11998b5ab248ec9b697f32292cf4ebcfd593cc3fb7dd30139a03` | — |

발행 PNG 32개의 최종 SHA는 중복하지 않고 §5 E4 목록에 전부 기록한다. 신규 QA와 실행 로그는 gitignore 대상이며 발행 산출물 목록에 넣지 않았다.

## §4. 잔여 및 ed2 이월

P1–P5와 전 쪽 시각 검증에서 **새 잔여 결함 없음**. R23의 VIS-1(변경표 헤더)·VIS-2(XLSX 제목)도 해소했다. 따라서 R24 때문에 추가하는 ed2 시각 결함 목록은 비어 있다. 기존 10-K/잠정 판정 확정·ed2 입력 준비는 이번 작업에 포함하지 않았다.

Windows 환경 SKIP 3개와 기존 EDGAR 기간 라벨 XFAIL은 §2에 공개했다. 그것을 숨기거나 ed1 숫자·규칙을 바꾸어 해소하지 않았다. 이후 발견되는 시각 결함은 부록 지시에 따라 ed2로 넘기며 **더 이상의 ed1 발행 렌더는 하지 않는다**.

## §5. 최종 E4 후보 목록 — 64개

R20–R24 누적 개정 범위의 최종 파일이다. **add 59개 / add -f 5개**, 합계 64개. `git check-ignore --no-index` 기준으로 add는 ignore 불일치, add -f는 ignore 일치로 구분했다. 이미 tracked인 발행 파일도 이 분류에서는 ignore 규칙에 맞으므로 add -f 그룹에 적었다. 명령 실행/공개 승인이 아니라 **최종 후보 목록**이다.

표의 파일 63개는 저장 직전 실제 SHA를 다시 계산하여 **63/63 일치**했다. 이 리뷰 자체는 SHA 자기참조를 피하기 위해 SELF로 적었으며, 저장 후의 실제 SHA를 외부 계산하여 최종 응답에 전달한다. 리뷰 저장 후 해당 SHA를 본문에 다시 삽입하지 않는다.

### add — 59개 (gitignore NO)

| # | 저장소 상대 경로 | SHA-256 |
|---|---|---|
| 1 | [forecast/scripts/mu_report/build.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/build.py>) | `4a631e8058b99663df468c907807188dc30770c2eb1a9c58810894d28bf5d4aa` |
| 2 | [forecast/scripts/mu_report/charts.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/charts.py>) | `b8ccfa36a719261890fc572dc2f1d4f5b7aa84036794b436fb07c04154127940` |
| 3 | [forecast/scripts/mu_report/gates.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/gates.py>) | `16c1a98c88aaa7bbf2638ddc0154c7e577b90c5b0617a68a2174d090532ac4d4` |
| 4 | [forecast/scripts/mu_report/i18n/ko.yaml](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/i18n/ko.yaml>) | `9094af9374df44a030638b9417526f964d11691c7c54ce1551cbffe992a268c3` |
| 5 | [forecast/scripts/mu_report/i18n/en.yaml](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/i18n/en.yaml>) | `0fcecbce01bd21ab3143c8e13b399cd53ae4580afe840b33e189c1f8f1d199cb` |
| 6 | [forecast/scripts/mu_report/narrative.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/narrative.py>) | `459ecfe7a1bda40813803219a1cba102171ab7b012564451ee2a947be09bebf7` |
| 7 | [forecast/scripts/mu_report/render.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/render.py>) | `3d2fb9171e31074fe714035b9e16fe7ff62894081b45b61eec6e21b5abe89fe5` |
| 8 | [forecast/scripts/mu_report/revision.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/revision.py>) | `1fd81ddb250f8a9eede0eb2f8075d9a9486c87dc98c9e975ce98dd052c33a4f0` |
| 9 | [forecast/scripts/mu_report/theme.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/theme.py>) | `a4348a379bfe532f0951731e9f7cefba8759cc7c9c87453695cc65036f85eacf` |
| 10 | [forecast/scripts/mu_report/presentation.py](<F:/dev/Portfolio/business-valuation-tool/forecast/scripts/mu_report/presentation.py>) | `3d74cba4ae0c238b9219d196b8caa6f43e38df734d78a0f7a0bc6bd5fdc8acfc` |
| 11 | [forecast/tests/test_mu_report.py](<F:/dev/Portfolio/business-valuation-tool/forecast/tests/test_mu_report.py>) | `23ffeab7ed3243f1c4476685d0d3f4634b6eca6b8db89b5b3aab304e5eef3607` |
| 12 | [forecast/tests/test_mu_report_revision.py](<F:/dev/Portfolio/business-valuation-tool/forecast/tests/test_mu_report_revision.py>) | `69be43a29c180fc0a454b3792fe743dbc48d2460d84f490e9ca81a2a70088a26` |
| 13 | [forecast/tests/test_mu_report_r22.py](<F:/dev/Portfolio/business-valuation-tool/forecast/tests/test_mu_report_r22.py>) | `637ce25d9060c50e9766e77ada8d3a9f9c51fb52035466c1eab94c5322bd95d3` |
| 14 | [forecast/inputs/mu_fy2026q4_narrative_ed1.yaml](<F:/dev/Portfolio/business-valuation-tool/forecast/inputs/mu_fy2026q4_narrative_ed1.yaml>) | `8fee9e26f59222ae062a83c450759e91fb90f6a69e1cbceea156f549478bbec0` |
| 15 | [forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml](<F:/dev/Portfolio/business-valuation-tool/forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml>) | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` |
| 16 | [forecast/HANDOFF_CODEX_mu_report_exec.md](<F:/dev/Portfolio/business-valuation-tool/forecast/HANDOFF_CODEX_mu_report_exec.md>) | `2b346dd3e16594d9d509e9e2edd0fb812c146fe1429d48f712a356a2eaf5e423` |
| 17 | [forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md](<F:/dev/Portfolio/business-valuation-tool/forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md>) | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` |
| 18 | [forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md](<F:/dev/Portfolio/business-valuation-tool/forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md>) | `3e17e43411db57df3ececdb6467826a6398cb5c4b4b13919daa8f363efd4efc7` |
| 19 | [forecast/reports/mu_report_fy2026q4_ed1_en.md](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.md>) | `42871bf0fe1ec50f989cb91237e5de917dea6a4011ad59850400c63b01378f49` |
| 20 | [forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json>) | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` |
| 21 | [forecast/reports/mu_report_fy2026q4_ed1_ko.md](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.md>) | `b2ca803b2b368695857560bbc827991afcf8390a04ea90ed03433bc2227db82d` |
| 22 | [forecast/reports/mu_report_fy2026q4_ed1_manifest.json](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_manifest.json>) | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` |
| 23 | [forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png>) | `0d81bf0ea955806405a3c79025a400ce78a4c94fe5bb8f4bbb93dc5e4c43daf4` |
| 24 | [forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png>) | `cfc15956d840c83b995c74c3a97abd6c16ac1c65d8c6720f84441d5622c347d3` |
| 25 | [forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png>) | `ec94fae022078834c5431fd831d961425c0784b99bdc96a81967cbe82948066f` |
| 26 | [forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png>) | `3dc5b42fa1ba5e70f614b5453ddf0a23ede14b749c55c7e93bc7eab13f43e43c` |
| 27 | [forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png>) | `5293ee3d52a1e147a789af18fe75fe6722385a34028ce4cb3dfbdb648165b1c6` |
| 28 | [forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png>) | `21742589936c8f57c1e85828dac92d9afcdd568ee848d47c4e8b89bfea63ad9b` |
| 29 | [forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png>) | `15615ee6f5da56340aa50b47f0079be4449bf17b19c0c1589f722b2c207c0c9d` |
| 30 | [forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png>) | `5c704ad775dd26a47c6b1a91873c802b6d8fb7e9f3eead7535798c5aa03b41bc` |
| 31 | [forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png>) | `a2de9a1056c01c0481d44412c586efb07ecf31a70ee39ea0bf1dcdac534dbf33` |
| 32 | [forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png>) | `8471ecf6a18964cd7255a233c6e719de365b522032647d85b5a57f74b6f90ec7` |
| 33 | [forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png>) | `194bffb4f48012917d14a79f458291f9a06ea05c264310ea57617f33ab6273ff` |
| 34 | [forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png>) | `301f02fbdeebdfd21a09ba7e641afb111043e243481e2f2c0a59b70249d76eaa` |
| 35 | [forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png>) | `7c4e1fd8ea4fd0bbb8d616a90dbfada9d60e580d2a515fed87649c9dcb957820` |
| 36 | [forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png>) | `a49225fa6b4ef170a395603b4ee6d6f3ddf95a7e650d9a1b741d654293bbc92f` |
| 37 | [forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png>) | `b355d23388822f7d68b9753301d3dc48d03ae6a39615dbb8097b72d9357a88a6` |
| 38 | [forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png>) | `d24399953905dd871ddce23ad0bcc56e1a006b971da9f075e7581782978daa18` |
| 39 | [forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png>) | `0d8f96523ab26dbe3fbe5d975ffd9fabac4f9cd07d506496b0f22d3efa4573e3` |
| 40 | [forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png>) | `ea43ff2e7c5fba4e85c7d23691e3694faf9fa863f21d54144b9d81cfd3ebcf54` |
| 41 | [forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png>) | `176a93460b799c0e6e53d14e482dd6929a3222d97ff10485e2fcc184157b1fc1` |
| 42 | [forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png>) | `377405fb5dcfdf9598a6cdc683cf48182a6d31da7defb231c0f9c1f9e52f6aba` |
| 43 | [forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png>) | `7fe2010ed6027340f18871c7945a127ee30786b4bc37c491112f27ca3b88a775` |
| 44 | [forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png>) | `86fc1f00a1065d534c7ef9d8eb827d8a2800e367fbdd9f2765fee4abeb7b8433` |
| 45 | [forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png>) | `13bd0f4e23f91653acef27e6bae812baaf5b7fb1f362f08665c90dbc27822bd1` |
| 46 | [forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png>) | `e9e12fa1940e73a72388c92a316ac7de7f5cc22b1e2f0d44e737edb4990cd89b` |
| 47 | [forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png>) | `17c241b5a44da12f0c99fb38d30d7b33442e4ea3e2b8a3901907ee613d86d016` |
| 48 | [forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png>) | `9bae3dee7107e6ce14846fd7d3c1432885c0c512ddebe553a22e2d618fb82eda` |
| 49 | [forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png>) | `877c273477940b13dd8d15fded1b5dd5ee144ddbac36ed56c47a326d14400450` |
| 50 | [forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png>) | `faafbd56b788c9f0632364d732feebba2c26fd85945d205390c831b42cbc01a6` |
| 51 | [forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png>) | `8f83baf1a9abec00ef9c095a95a828ea8c451d9fe65cabebebf64b8dd48f4daf` |
| 52 | [forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png>) | `1ed6dd7efdec6a750bd7818c07b71b963e5b774df0d1c68352b99b2932c03c62` |
| 53 | [forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png>) | `9509d1c16b1bdfec50f52777e99ab333933b9479d39d505f9fcf1e87ef6f89c7` |
| 54 | [forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png>) | `61922b5d70585e0534f28b08c0e5c975f3acdfaf77ef22e0921f9a75d8ce219e` |
| 55 | [forecast/tests/test_mu_report_r23.py](<F:/dev/Portfolio/business-valuation-tool/forecast/tests/test_mu_report_r23.py>) | `93e2f0a04b649b8e3b455f0a2c1bdf78e3c30dd25b09b927a654de240a487aec` |
| 56 | [forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md](<F:/dev/Portfolio/business-valuation-tool/forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md>) | `04e20fbcf118242729a62e5b265076ac55ef8b047f834cc93d62b55c60c6f190` |
| 57 | [forecast/REVIEW_CODEX_mu_report_ed1rev1_r4.md](<F:/dev/Portfolio/business-valuation-tool/forecast/REVIEW_CODEX_mu_report_ed1rev1_r4.md>) | `94150bca97f8a9f526f0f974b1a1d4e1b149bb631fd63b62077f8eeacef6aaef` |
| 58 | [forecast/tests/test_mu_report_r24.py](<F:/dev/Portfolio/business-valuation-tool/forecast/tests/test_mu_report_r24.py>) | `70e7fa36f95ee64b00ea22448169ecfd97bd9cfd9b263a812f535abdafa12851` |
| 59 | [forecast/REVIEW_CODEX_mu_report_ed1rev1_r5.md](<F:/dev/Portfolio/business-valuation-tool/forecast/REVIEW_CODEX_mu_report_ed1rev1_r5.md>) | SELF — 저장 후 외부 계산, 최종 응답 참조 |

### add -f — 5개 (gitignore YES)

| # | 저장소 상대 경로 | SHA-256 |
|---|---|---|
| 60 | [forecast/reports/mu_report_fy2026q4_ed1_data.xlsx](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_data.xlsx>) | `9df8bf80d8ef11998b5ab248ec9b697f32292cf4ebcfd593cc3fb7dd30139a03` |
| 61 | [forecast/reports/mu_report_fy2026q4_ed1_en.html](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.html>) | `bc07ad11860e429746109855ebe370af4c2cae7796e58ebf37f8776bba292241` |
| 62 | [forecast/reports/mu_report_fy2026q4_ed1_en.pdf](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_en.pdf>) | `154cf9aae1dbb94d9d005c4f3ce2cb63c10fb70b28b4f5c0d1be90ae73bb1fd8` |
| 63 | [forecast/reports/mu_report_fy2026q4_ed1_ko.html](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.html>) | `abe5261d462b2faf995c1ab6a66311ec50c70898a26db65884ec89f7fe1bf30e` |
| 64 | [forecast/reports/mu_report_fy2026q4_ed1_ko.pdf](<F:/dev/Portfolio/business-valuation-tool/forecast/reports/mu_report_fy2026q4_ed1_ko.pdf>) | `8419b2cb364a0bde4f3b5dbb0c49fd390bde1d59839887d1255890d21c21d114` |

제외 목록:

- `forecast/HANDOFF_CODEX_mu_report_survey_r4.md`.
- `forecast/PLAN_mu_report_fy2026q4_rev4_superseded.md`, `forecast/PLAN_mu_report_fy2026q4_rev4.1_superseded.md`, `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md`, `forecast/PLAN_mu_report_fy2026q4_rev4.3_superseded.md`.
- `logs/**` 전체: rev0 보존 25개, 이동 QA 198개, R24 신규 QA·미리보기·runtime. 모두 gitignore 대상이며 E4에 포함하지 않는다.
- 테스트 임시 fixture, 무관한 기존 수정/미추적 파일(`CLAUDE.md`, 다른 핸드오프·프로파일·문서 등). 기존 사용자 변경은 보존했다.

`forecast/reports/mu_report_fy2026q4_ed1_assets/`에는 §5의 PNG 32개 이외의 QA 폴더/파일이 없다. narrative r4·최신 R24 핸드오프·리뷰 r1–r5·이해관계 레코드를 포함했다. 기초 HEAD는 `9e4c667b1750e129027a31b730ed338289f0e9b4`이며 작업 후도 동일하다. **git 쓰기 0, 로고 이미지 0, 서술 YAML 변경 0, 숫자/규칙 변경 0, 레코드 갱신 0**.

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

