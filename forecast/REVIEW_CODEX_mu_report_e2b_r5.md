# MU FY2026Q4 ed1 — R18 셀 연결·표기 정리·E2B 검토 r5

판정: **PASS — R18 지정 수정, 재렌더 및 실행한 전체 게이트/회귀 테스트.** E3 최종 배포 승인 또는 E4 커밋 승인을 대신하지 않는다.

최종 재렌더 시작은 **2026-10-05T11:20:15.519871+09:00**으로, 제한 시각 **2026-10-05 14:42 KST 이전**이다. 최초 R18 렌더도 11:16:15 KST에 시작했다. git add/commit/push는 실행하지 않았다.

## §1. 수정·증거

작업 시작 시 R18의 셀 연결·부록 표시 수정과 일부 테스트가 이미 미커밋 상태로 존재했다. 이를 되돌리거나 중복 구현하지 않고 확인했으며, 추가 변경·재렌더 전에 현재 R17 산출물의 실패를 재현했다.

### 세전이익·현금흐름 순이익

- 손익계산서 RLE 세전이익은 표 행 이름 `pretax_income`을 실제 fact `is.pretax.FY2027E.base` / `is.pretax.FY2028E.base`에 연결한다. 역사·사전등록·FY26 실제 열은 기존 이름을 유지한다.
- 현금흐름표 RLE 순이익은 존재하지 않는 `cf.net_income.*`가 아니라 `is.net_income.FY2027E.base` / `is.net_income.FY2028E.base`를 참조한다. 역사·FY26 실제 현금흐름 fact는 유지한다.
- G-23 required set에 위 **네 fact ID**를 추가했다(총 25개). 원시 fact의 AVAILABLE 여부뿐 아니라 KO/EN의 **실제 표 셀 표시가 그 fact.display와 일치하는지** 검사한다. 순이익은 손익 표와 현금흐름 표를 구분해 현금흐름 행까지 검사하며, 행의 8개 셀 구조도 검사한다.

| RLE 행 (USD million) | FY27E base | FY28E base | 최종 PDF |
|---|---:|---:|---|
| 세전이익 / Pretax income | 225,197 | 216,126 | KO/EN 10쪽 |
| 현금흐름 순이익 / Cash-flow net income | 194,404 | 186,572 | KO/EN 11쪽 |

이 값은 기존 manifest 값을 연결한 것이며 새 추정이 아니다. R17 보존본과 최종본의 **759개 fact·26개 source가 완전히 동일**하다. manifest 전체 SHA도 R17과 같은 `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812`이다.

### 부록 식·값 라벨

규칙표의 식을 출력할 때 `*`만 `×`로 표시한다. 예: `quarterly_dps × 4 × S1`. Markdown과 최종 HTML 모두에서 곱셈기호가 보존됨을 테스트했고 KO 16쪽·EN 17쪽 이미지에서도 확인했다. 값 칸의 내부 `key.value=` 접두는 KO `값:` / EN `value:`로 바꿨다. 식의 피연산자·숫자·순서·규칙은 바꾸지 않았고 서술 YAML도 수정하지 않았다.

### 회귀 테스트에서 발견한 XLSX 시각 비결정성

첫 전체 회귀에서 바이트 동일성 테스트 1건이 실패했다. 두 XLSX를 내부 항목별로 비교하니 **`docProps/core.xml`의 modified 시각만 1초 차이**였고 셀 데이터는 같았다. 설치된 저장 라이브러리의 `save_workbook()`가 지정한 modified 값을 저장 시 현재 시각으로 덮어씀을 확인했다.

기존 ZIP 메타데이터 정규화에 core modified 시각 정규화를 추가했다(`2000-01-01T00:00:00Z`). 기존 동일성 테스트는 저장 시각을 5초 다르게 만들어도 바이트가 같아야 하도록 보완했다. R17 XLSX와 최종 XLSX의 내부 항목 차이는 **core.xml 하나뿐**이며 모든 worksheet 내용은 동일하다. 이 수정은 테스트·E4 SHA 재현성 보완이며 수치·서술·규칙 변경이 아니다.

변경을 확인/검증한 경로: `forecast/scripts/mu_report/{render.py,narrative.py,gates.py}`, `forecast/tests/test_mu_report.py`, 허용된 ed1 산출물·보존본·본 리뷰. 계산 엔진과 가정 YAML은 변경하지 않았다.

| 변경하지 않은 입력 | SHA-256 |
|---|---|
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d` |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` |
| `forecast/reports/mu_fy2026q4_SCORED.md` | `0f6e6a951dc57d95b8846dbc8588d42b2ac2925f1c52b54cc80e9a2a027af4f9` |

## §2. 게이트

### 현재 산출물의 G-23 RED → 최종 GREEN

코드 추가 변경·재렌더 전 현재 KO/EN Markdown 및 manifest에 강화 G-23을 실행했다. 실제 파일은 수정하지 않았다.

```text
R17 CURRENT RED ko:
G-23 required rendered cell unavailable or mismatched: ko/is.pretax.FY2027E.base: UNAVAILABLE

R17 CURRENT RED en:
G-23 required rendered cell unavailable or mismatched: en/is.pretax.FY2027E.base: UNAVAILABLE
```

세전이익 표시만 메모리에서 기존 fact.display로 연결해 첫 실패를 건너뛰면, 현금흐름 순이익 누락도 독립적으로 실패한다.

```text
CF ISOLATED RED ko:
G-23 required rendered cell unavailable or mismatched: ko/is.net_income.FY2027E.base: UNAVAILABLE

CF ISOLATED RED en:
G-23 required rendered cell unavailable or mismatched: en/is.net_income.FY2027E.base: UNAVAILABLE
```

원시 fact 네 개는 R17에도 AVAILABLE이었다. 따라서 required fact만 추가하면 이 결함은 잡히지 않는다. 실제 rendered cell 검사를 함께 추가해 연결 누락을 차단했다. FY27/FY28 및 KO/EN 각각의 셀을 UNAVAILABLE로 치환하는 RED 테스트와 네 required fact 삭제 테스트도 통과했다.

### 최종 전체 게이트

명령: `python -m forecast.scripts.mu_report.build --phase E2-B --edition 1`

- 최종 결과 **PASS**, failures `{}`.
- 사전: G-1 핀, G-2 FROZEN 표시, G-3 역사 항등식, G-3f SCORED 바인딩, G-7 template/IO, G-9 cutoff, G-12 manifest, G-14 provenance, G-15 구조, G-17 순현금 설정, G-18 hygiene, G-19 bridge, G-20 phase audit 및 narrative contract PASS.
- 사후: G-4 inventory, G-5 P/B, G-6 KO/EN 시장 데이터, G-8 KO/EN theme, G-10 narrative, G-11 placeholder, G-12b disclaimer, G-12c conflict, G-13/G-13b/G-13c KO/EN, G-15 parity, G-15b localized UI, G-16 caption 16개, G-17 KO/EN labels·순현금, G-17b KO/EN consensus, G-18 hygiene, G-21 formats/목차, 강화 G-23, G-24 PDF raw markup, G-25 cover dates PASS.
- G-23 required failure **0**, chart placeholder **0**. 미가용 감사 위치는 R17의 88개에서 **84개**로 감소했다(미가용 fact 3개 + KO/EN 표시 위치 81개). 이번 수정은 두 행의 언어별 미가용 위치 4개를 해소한다.
- 이해관계 확인 blob: `393cb05876f6f5aabf6fbdb98778c69b8c5d06b6`. 최종 렌더 시작 시 레코드 유효시각 이전이며 확인 이후 24시간 미만이다.
- 실행 감사: `logs/_mu_report_runs/e2b_20261005T112015+0900.json`, SHA-256 `1547238b319aa79aa53c092272bf208e9a0bfaf219a058521afbf0123b659451`.
- 시각 QA: KO 17쪽·EN 18쪽 전 페이지를 이미지로 변환해 overview를 확인하고, 최종 세전이익·현금흐름·부록 페이지를 확대 확인했다. 곱셈기호·새 셀 표시가 보이고 잘림·겹침·깨진 glyph를 발견하지 않았다. 표지 1쪽·목차 2쪽·쪽수/절 전환 유지.
- Poppler의 Bulgarian/Greek/Thai nameToUnicode 경로 경고는 생성 종료 코드 0 및 KO/EN 표시 검사에 영향을 주지 않았다.

**NOTICED BUT NOT TOUCHING:** `forecast/scripts/mu_report/render.py:626` 및 `:631` — 공용 XLSX Summary의 비리허설 문구가 아직 FIXTURE/E2-A fixture라고 되어 있다. R18의 두 셀·부록 표시 범위 밖이므로 바꾸지 않았다. 기존 Facts 시트의 실제 fact 값과 이번 PDF 연결 수정은 별도 검증했다. 따라서 본 PASS는 R18·현재 게이트에 한정하며 XLSX 표지 문구까지 배포 적합하다고 주장하지 않는다.

## §3. 산출물 SHA·쪽수 및 보존

최종 렌더 후 실제 파일 바이트에서 다시 계산한 SHA-256이다.

| 전체 경로(저장소 루트 기준) | bytes | 쪽수 | SHA-256 |
|---|---:|---:|---|
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 35,054 | — | `14e088c3f9e7f65e228f46633da602fcaefb607a8d4ea35dacf064da428b9e9e` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 46,477 | — | `1a710f098cad03549c6572f6d00301455453e0536318bc89e80cd24f4b038182` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 27,929 | — | `d22250400d1858a7d65081277cb75d4e58b0458d16258a8854faeb8c9c184682` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 626,312 | 18 | `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | — | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 46,603 | — | `4992b1483a6ee4433e87f86678d021e79ac8fa4b5ff248f98f0cf4607b71ce7a` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 28,103 | — | `495bcbd936758494954ac81a5e96f4cf75e9fbc0813d546d2da14c7d48333313` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 806,139 | 17 | `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 394,803 | — | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` |

이전 R17 본체 9개와 차트 원본 16개는 `logs/_mu_report_runs/ed1_r3_rejected/`에 존재하는 보존본을 재사용했고, **재렌더 전에 9/9·16/16 바이트 일치**를 확인했다. 기존 파일을 덮어쓰지 않았다. 당시 실행 감사 JSON도 같은 디렉터리에 복사 보존했으며 SHA는 `1be102af3a38768b80232f73cce8d83dd1d455933118e75f7b6539dc1ad42f4c`이다.

보존 KO PDF(17쪽) SHA=`ae0eee432ddcf48596cd0a771fbecebd7eaa923d05f7ab751b5db0141f475e5d`, EN PDF(18쪽) SHA=`411ba6328c58528ffc495458888255dfe42be9897af335f6c1826001550d5e5b`. 이전 산출물은 복구 가능하며 삭제하지 않았다.

## §4. 테스트

| 실행 | 최종 결과 |
|---|---|
| `python -m pytest forecast/tests/test_mu_report.py -q --tb=short -p no:cacheprovider` | **74 passed**, 15.40s |
| `python -m pytest forecast/tests/ -q --tb=short -p no:cacheprovider` | **496 passed, 3 skipped, 1 deselected, 1 xfailed**, 58.91s |
| 최종 E2-B build | 전체 실행 게이트 **PASS**, failures `{}` |

- R18 KO/EN 테스트는 네 RLE 셀의 실제 ref position→fact ID, G-23 GREEN, FY27/FY28 셀 치환 RED, 부록 × 및 값/value 표시와 HTML 보존을 검사한다.
- 네 required fact 각각을 삭제하면 G-23이 실패하는 테스트를 추가했다.
- XLSX 바이트 동일성은 서로 다른 저장 시각으로 재현하도록 보완했다.
- 리허설·dry-run 관련 기존 테스트도 그대로 통과했다.
- 첫 실행의 임시 폴더 PermissionError는 동일 테스트를 필요한 파일 접근 권한으로 재실행해 해소했다. 첫 전체 회귀의 modified 시각 실패는 §1의 원인 확인·최소 수정 후 재검증했다. 최종 미해결 테스트 실패는 없다.
- skip은 Windows symlink/process-group 제약 및 gitignored EDGAR cache 부재다. xfail은 기존 FYE-August Q1 라벨 문제이며 변경하지 않았다.

## §5. E4 커밋 후보 목록

계획 rev-4.3 §2 D7 기준으로 **기존 후보 95개 + 본 리뷰 1개**를 열거한다. 경로는 저장소 루트 `F:/dev/Portfolio/business-valuation-tool/` 기준의 전체 상대경로이고 SHA-256은 실제 파일 전체 바이트의 값이다. 이 목록은 승인 후보일 뿐이며 실제 add/commit/push 권한이 아니다. 계획 보존본·선행 리뷰도 문서 후보에 포함했고 변경 없는 추적 파일의 재추가 필요 여부는 E4 승인 시 구분한다.

본 리뷰 `forecast/REVIEW_CODEX_mu_report_e2b_r5.md`도 문서 후보다. 파일 안에 자신의 전체 파일 SHA를 넣으면 바이트가 다시 변하는 자기참조가 생기므로, **본 리뷰의 최종 전체 바이트 SHA는 최종 응답에서 별도로 제공**한다. 아래 95개 SHA는 모두 직접 검증 가능하다.

`forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`은 계획에 명시된 public 커밋 후보이며 보유 상태 고지가 공개된다는 점도 E4 승인 범위에 포함한다. 이번 실행에서 확인 레코드를 갱신하지 않았다.

### 코드·소스 추출본·핀 (24개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/scripts/mu_report/__init__.py` | `257be815775597e3a96235f7e612f5f74f50a0e86c5a424a69e5c3984a90e9c8` |
| `forecast/scripts/mu_report/build.py` | `78e2a9caf773b9fc0d272e1ace836affec2161e6eaf166c3a93278a492017ed9` |
| `forecast/scripts/mu_report/charts.py` | `d19579dcdeb3c218f37b508c666208c3d89657f29a4ccc893f115083e7325631` |
| `forecast/scripts/mu_report/extract.py` | `0336ec14a21f748feb99f3fa351b27d85c560c67c3f4bc6938955140a106843e` |
| `forecast/scripts/mu_report/facts.py` | `62e4e490845228bfcda0f27006614c30f0373c4a4c2b45657b6c2f4e01224e48` |
| `forecast/scripts/mu_report/gates.py` | `2c3ded638cf9a00888a6d2907744a7586e1537db1c178056514b984cd04835de` |
| `forecast/scripts/mu_report/i18n/en.yaml` | `eeb3158ba2dd57e7518145a82d3b0209c8db01065c196a121c5212c42bf9f9b9` |
| `forecast/scripts/mu_report/i18n/ko.yaml` | `38d4dccec8514e0143d17084292c1ebdabf90c6e926113308a600b90e154adce` |
| `forecast/scripts/mu_report/input_pins.yaml` | `2ffa42bb1d75d3a6ca6e80eed594fe60c0b7f20b867babfebd3dc3e701e716c0` |
| `forecast/scripts/mu_report/inputs.py` | `5a204372f5848264da540628ba38be8f91c5d853aa349dd247e1e86ef6a00942` |
| `forecast/scripts/mu_report/narrative.py` | `f5ff8cfd930a5956293383a38744f0147a7f0179169fb6e4f6b726f79552e8cd` |
| `forecast/scripts/mu_report/render.py` | `8721559a3e5b0c397554a67096372f4a4d5e0c9b89708fd81b260cd6197c8854` |
| `forecast/scripts/mu_report/rle.py` | `555472f731d5fa45a428056fc337d298979216a5c3d59348a133faabe0740ea8` |
| `forecast/scripts/mu_report/sources/annual_financials.json` | `cdfe815a6eef30f8e4a5f7de4c6f850001e2ee31e976bf2da2cc43f0ba670ea0` |
| `forecast/scripts/mu_report/sources/business_units.json` | `95afe0c79fa8a5882231a5856aadc1238afeb34b393378b7239b2dc84bce5414` |
| `forecast/scripts/mu_report/sources/companyfacts_quarterly.json` | `cd61b3f6780f05f82ebff5dc4628fd3cc5b1074da27631db15b1bbd2e3ecc2c3` |
| `forecast/scripts/mu_report/sources/debt_fcf.json` | `0bff823759b06cd9bb40e0a35c5d95fe6c77e97570734bb62dd8c18eef2d07ec` |
| `forecast/scripts/mu_report/sources/freeze_prereg.json` | `52e0f30a87646bb13a83f59022386e20e0849e7c0c7c2873f09ba0ae72a45402` |
| `forecast/scripts/mu_report/sources/guidance_history.json` | `7b498fce0cf7c49fd6c9431812ae9a6f233ce39f338c220ce87df99569e9c9f0` |
| `forecast/scripts/mu_report/sources/input_audit.json` | `54d780ecce5090c1341fab1ceb0adeb183cd6ccaad688eca972d32d890b0f80d` |
| `forecast/scripts/mu_report/sources/prepared_remarks.json` | `05038ac125c6fd097e2bfdf347e510ff7ce0ab60cf6a23695e4181e3fb482936` |
| `forecast/scripts/mu_report/sources/release_tables.json` | `7c63641a7baa1d7d5711e3d25e6e88d97270ca797177aba3581d27d9fbb4b6f9` |
| `forecast/scripts/mu_report/theme.py` | `bf5c73e3a6691c7beb8402bfd7c1101aa730763fd03aa9c95a66225e551c6e75` |
| `forecast/scripts/mu_report/valuation.py` | `1c46a3e7e7c565978e60d7ca000286d0ac27561f07c88c3b3fd824d690e8097d` |

### 내부 입력 YAML (3개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` | `1e8d4f98684f9bd4579bd7c79fffd51b06246446442b720b9819b8b7addf9d95` |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d` |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` |

### 테스트·리허설 fixture (8개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/tests/fixtures/mu_report/conflict_confirmation_edition_mismatch.yaml` | `79bfea05ab526b553d6e05294d448cb69d48440aad66dc0ef1510eab7815a1b8` |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_expired.yaml` | `706e9fcf5d4b15264fc97c10cec5256b9f870d694e81e30fae7d804413d4493b` |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_future.yaml` | `47746fd6d7a1c943f7cee4259f8ab3f240d2f9ef3957f5975fda84ccbb29c8c1` |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_held.yaml` | `69a04cd362a3b0d1d29a7b16684826cae0b516a9e9cfed1b0e8d9d594cd1e972` |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_missing_key.yaml` | `9da0d970fdf5c4bd5f9f02782c5a6028a9989f19076ce850d5fe6cab1103b017` |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_ok.yaml` | `3100acb4a699fc2475d4ee5cebb092d881d701fd91c966005577bb6117d27e40` |
| `forecast/tests/fixtures/mu_report/fake_postprint.yaml` | `4ef1e65e6993e4e1daef321847a9d6495421a00d8e29d17b679396ecb4d8dca1` |
| `forecast/tests/test_mu_report.py` | `d42bd54aedb795c253dcde2eb93607753913635090bfe106edca50097c0e296a` |

### 최종 ed1 본체 (9개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | `14e088c3f9e7f65e228f46633da602fcaefb607a8d4ea35dacf064da428b9e9e` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | `1a710f098cad03549c6572f6d00301455453e0536318bc89e80cd24f4b038182` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | `d22250400d1858a7d65081277cb75d4e58b0458d16258a8854faeb8c9c184682` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | `4992b1483a6ee4433e87f86678d021e79ac8fa4b5ff248f98f0cf4607b71ce7a` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | `495bcbd936758494954ac81a5e96f4cf75e9fbc0813d546d2da14c7d48333313` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` |

### 차트 PNG 원본 (16개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png` | `d69430ea4339d456ca05be74ae8d0f30c62b292d3ef5fa707d39b4ecdb270f25` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png` | `2636e62e1c82df11331c2f5710e6d1c416262bc54d07c801e12fdd63ec0104b2` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png` | `227ffde29da2ae523fed036dd84208b7e6827e2f540d1c59d5d4b638e517b50b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png` | `2fcaf2996163053c8cc72e458a13de859dc55e12286ba03d5c3e9d371c346aa9` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png` | `27e7cfd681daebe67e2278aed5aa6afe8ffef0fb532e646f5693d8c0a3c808ea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png` | `5b33e070265eef7e4198cc5ab273b81486bf5b90067f3ed8081ff6bb5dca3576` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png` | `085a16edf597842d78ecba2545c321f05daa2262399da1f3637823dd7c1f4638` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png` | `cceefb7c18ba77dfd838fff296d4b2059e969dca30b6b1fbb324995ce4902b42` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png` | `dd82634eca3346a37fdd6164a5f44696c206aeaecb9e103c74428cf92445565d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png` | `7a5cbe1f72a09e145dbb9ce6ab818723e9ade7e8bde6011cceccda95aae9adf8` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png` | `78dea8b9997e713fc103e57dd32e040afdab65a72fac518b5af974a5bd8cd3dc` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png` | `4390091c0cc03c0791f07cdcb9f7dd6231a4d6f9fabcb882ae2aec003a434b71` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png` | `fd819824abb8cc8d27172249e0c8c61838707b1403a0ebfb7f9c91d40640aeea` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png` | `1ead96ea05256a65cf22b0f72bd95574141f845c901215537f836b3b58a5830d` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png` | `1ee978d72fba7f4ba25afbc490f98bcaefc07e8706ed2b4ebff2ab0f9c0840f0` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png` | `0a7230adfea1ddd412548080dc7ac4ea32a278aca2f6a91d7defa0003f576517` |

### PLAN·HANDOFF·REVIEW 문서 (35개)

| 전체 경로(저장소 루트 기준) | SHA-256 |
|---|---|
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | `bb4a8aef1d6e9951b8101f7d19764dd4ac80633b5d932ef30bfe42d5ffd2e866` |
| `forecast/HANDOFF_CODEX_mu_report_survey_r4.md` | `9bc9832ae33df578e11298b4612cc8e7761214382a6c32736e58f3e2d0b35e92` |
| `forecast/PLAN_mu_report_fy2026q4.md` | `99de31cb5ccbb99aa9a4748ea955ea8cd946a64f6e1a379d9757a6add20d4492` |
| `forecast/PLAN_mu_report_fy2026q4_rev1_superseded.md` | `d4d41b9ae3d65de68e39120663f9f7c1f56770574ec9d84af90988b9c8374fb0` |
| `forecast/PLAN_mu_report_fy2026q4_rev2_superseded.md` | `7f204ea2ec743a7997f6cd2c927facd2fd9be6aea283b05047ddf63fa2df1255` |
| `forecast/PLAN_mu_report_fy2026q4_rev3_superseded.md` | `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324` |
| `forecast/PLAN_mu_report_fy2026q4_rev4.1_superseded.md` | `35dc207b9d1cbb9a4b7c8352fa1199f75c0f64b2d6fb2b542b2f0a0f1249bdf5` |
| `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md` | `32fc96edbaffa1c0952f9dc1d5a9f4b5eb2743ce41e482ea1b50b681689d5734` |
| `forecast/PLAN_mu_report_fy2026q4_rev4_superseded.md` | `d007f554f68643891d7586f8c43c4254886f3826f54417c4e3144239f2a8e646` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r1.md` | `0249ba02bd6c3665a7914dd802ce805e8bca88b8ab4034867765423fcbfd469a` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r2.md` | `22bbef4f0d289baedbf03a86dd5b0963df72c5e1f084a92dd1f522bce2093539` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r3.md` | `61dd170190095e9c1a8726e1249c4e7082183ae3a239360bf4409a717b270902` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r4.md` | `f3e3ac75ff87d1e16cba943b66fdbdfdd3b1ef9722484c53a848cb6cec1cf190` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r5.md` | `36b429f581e7732052d4bc79d642e3df147835d96d2b7872eac420cfb9eaa7ed` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r6.md` | `8775c96ed9c352eece06a9f6fd2c665d78d0b5383f8ad73a88126b8870de361b` |
| `forecast/REVIEW_CLAUDE_mu_report_output_r7.md` | `5b6edc261a2ba05a769cb814ebe465a2299b8e3f3050ceebe08abeca471fb87a` |
| `forecast/REVIEW_CLAUDE_mu_report_rle_r1.md` | `330db02cacc9a697d8563ea5c3f31ea6e83af18c73217b7d7ee4731348b2eb9f` |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r1.md` | `f6bf58960ff59dec333d515bbb78079bd3bf4bbe5fa737f415c68d41e070e14a` |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r2.md` | `95a13a2f9f2ec5a02d7eff4f26cc40d9010df3ef6af0be941432a4d5e1f35336` |
| `forecast/REVIEW_CODEX_mu_report_e2b_r1.md` | `c70e05261271a69c859466130d8034a4d9a6e9f637de5d68ba8c67b270f1db0b` |
| `forecast/REVIEW_CODEX_mu_report_e2b_r2.md` | `2a1dd4ab178bb2e9aee11311f75fc45d51f864d2cff413bcccd89b1ca65a2d3d` |
| `forecast/REVIEW_CODEX_mu_report_e2b_r3.md` | `8273a1d1c6bb16c9ef3b7b1ebc1b87167a41ae6c596122aa0d7f16c38d7e62ef` |
| `forecast/REVIEW_CODEX_mu_report_e2b_r4.md` | `23ad4173df2256f23fb7e0220e58d39587242102131bc1d99940450d9a457d46` |
| `forecast/REVIEW_CODEX_mu_report_pins_r1.md` | `94eeee88bab1c5a1888aacd5843cafabd892a0964dbe7bd632c13927622d2b9f` |
| `forecast/REVIEW_CODEX_mu_report_pins_r2.md` | `3b24da540e5701f6ba3f68d0689ba81600cd9006f74fce8a803f30966ffd0612` |
| `forecast/REVIEW_CODEX_mu_report_plan_r1_rerun_2026-09-28.md` | `0140a8c4a397af1e7a402172371a11602d09d88c53bbc0dd4eaa6414d431c321` |
| `forecast/REVIEW_CODEX_mu_report_plan_r2.md` | `3a8050cc9214fa3b97e6d4bb5a5ac31630e1cf0ce35e73f381acdeecd37d0470` |
| `forecast/REVIEW_CODEX_mu_report_plan_r3.md` | `cd2301bee6ac52201f2538aaf4d7c5b03f60b0b3855e158c10f6d4e6db070d4c` |
| `forecast/REVIEW_CODEX_mu_report_plan_r4.md` | `a0a95a2477a50a2244c3750a70beca3f83724a1acb0ba537b1a5d685ce65a976` |
| `forecast/REVIEW_CODEX_mu_report_rle_r1.md` | `bc14b9482aa06230cebefb8894cf751a1903c2122cf09bcd5036a284a9eaee4b` |
| `forecast/REVIEW_CODEX_mu_report_rle_r2.md` | `5bca5418ec2dfb0bbf9bc617ef09a7ee2a0de197747f18faf88ba1a0f804b6cc` |
| `forecast/REVIEW_CODEX_mu_report_rle_values_r1.md` | `57733f6d9131dfe4b3b96697f1530bdc3668ebcb2783cd7d6eee4cd3703b0ded` |
| `forecast/REVIEW_CODEX_mu_report_rle_values_r2.md` | `8012d34a8881567568b20fc440771156390f2426b942c36c8b9f33f0847fa74a` |
| `forecast/REVIEW_CODEX_mu_report_survey_r1.md` | `ae00afd2ab168627eaedc83489f0389842bbb2bc122b0c1a975d67ec0232762a` |
| `forecast/REVIEW_CODEX_mu_report_survey_r2.md` | `0f263d02a4e2e4f6d735b8fa3298eba99c4e7e2a3c6a674c18c75aab037d6c91` |

### 커밋 제외 — 별도 표시

- `logs/**` 전체: 외부 원본·가격 캡처·시각 포함 실행 로그·리허설·거절 버전 보존본을 모두 제외한다. 특히 `logs/_mu_report_runs/ed1_r3_rejected/**` 및 이번 두 실행 로그는 후보가 아니다. 최종 실행 로그의 SHA는 §2에 감사용으로만 기록했다.
- `forecast/reports/mu_report_fy2026q4_ed1_assets/pages*/**`: PDF QA용 페이지 PNG·overview는 제외한다. 후보는 위에 열거한 **루트의 차트 PNG 원본 16개**다.
- `__pycache__/**`·`*.pyc`·임시 파일·pytest cache를 제외한다.
- `forecast/reports/mu_fy2026q4_SCORED.md`, FROZEN 및 프로파일은 이번 E4 신규 후보에서 제외한다. 이미 선행 커밋된 읽기 전용 입력이며 수정하지 않았다.
- 다른 회사·다른 기능의 dirty 파일은 후보에 넣지 않았다.

E4 진행은 Jiwon의 정확한 파일 목록·SHA 승인 이후에만 가능하고, push는 별도 승인 대상이다.

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

