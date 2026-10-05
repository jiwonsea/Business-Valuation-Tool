# MU FY2026Q4 ed1 — R19 XLSX 문구·G-24·E4 검토 r6

판정: **구현·재렌더·전체 게이트·테스트 PASS / E4 명칭 검사 CHANGES.** 지정된 survey_r4는 제외했다. 나머지 후보 중 계획 문서 4개에도 동일한 재배포 플랫폼 명칭이 있어, “다른 후보에 없음”을 확인할 수 없다. 이 문서들은 R19 수정 허용 경로 밖이므로 수정하지 않았으며 E4 승인 대상을 보류한다. 커밋·push를 수행하지 않았다.

최종 렌더 시작: **2026-10-05T12:18:13.934831+09:00**, 제한 시각 **2026-10-05 14:42 KST 이전**. 첫 R19 렌더는 12:15:27.684294 KST에 시작했다. E3 배포 승인 및 E4 목록 승인과는 별도다.

## §1. 수정·증거

### XLSX Summary 실제판 연결

- `forecast/scripts/mu_report/render.py`: 실제 E2-B ed1에만 새 Summary를 적용한다. 기존 fixture 및 E2-A DRYRUN 출력 경로·표시는 유지한다.
- PDF와 동일한 KO/EN locale 키로 제목, 판 라벨, 작성자, 실제 발행일, 자료 기준일, 정보 컷오프, 완결성, 면책 두 키(`not_advice`, `third_party`) 및 확인 레코드 기반 이해관계 고지를 채운다.
- Summary의 B4:B12는 KO, E4:E12는 EN이다. 표지 날짜와 고지 문자열을 그대로 사용하며 숫자나 서술을 재작성하지 않는다. 행 13은 기존 G-21이 요구하는 출처·단위 메타데이터다.
- Facts!K2의 남아 있던 FIXTURE 자료 기준일도 실제판의 EN `ed1.cover.as_of`로 교체했다.
- 실제판 XLSX에 확인 레코드·렌더 날짜가 누락되면 생성을 거부한다. fixture/DRYRUN에는 이 새 필수 인자를 요구하지 않는다.
- 기존 셀 스타일을 유지하면서 긴 한·영 고지가 줄바꿈되도록 병합·너비·높이를 조정했다. 읽기 전용 XLSX 이미지 확인에서 잘림·겹침·한글 깨짐을 발견하지 않았다.

### 강화 G-24 — 구 산출물 RED 선행

`gates.py`에 모든 worksheet의 모든 문자열 셀을 검사하는 `gate_g24_xlsx_labels()`를 추가했다. 숨김 시트와 문자열 내부의 토큰도 검사한다. FIXTURE·DRY RUN·E2-A fixture 검출 시 시트명·셀 좌표를 포함해 실패한다. E2-B build의 기존 PDF G-24에 실제 XLSX 경로를 연결했다.

**builder 수정 전에 당시 현재 R18 XLSX에서 다음 실패를 확인했다.** 재렌더 후에도 보존본으로 같은 실패를 재현했다.

```text
G-24 XLSX rehearsal labels remain:
['Summary!A1: FIXTURE', 'Summary!B3: E2-A fixture',
 'Summary!B8: FIXTURE', 'Facts!K2: FIXTURE']
```

당시 XLSX SHA-256: `14e088c3f9e7f65e228f46633da602fcaefb607a8d4ea35dacf064da428b9e9e`.
최종 XLSX에서 위 검사 결과는 빈 목록이며 G-24 PASS다.

### 수치·서술·규칙 불변

보존 R18 XLSX와 최종 XLSX의 **Facts A:G 전체(헤더 + 759행)를 직접 대조해 정확히 일치**했다. 숫자 저장 정밀도까지 포함한 실제 파일 셀 비교다. manifest 전체 바이트와 759개 fact·26개 source도 불변이다. 차트 원본 16개는 모두 바이트 일치하고, XLSX 외 본체 8개도 모두 바이트 일치한다.

| 수정하지 않은 입력 | SHA-256 |
|---|---|
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d` |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` |
| `forecast/reports/mu_fy2026q4_SCORED.md` | `0f6e6a951dc57d95b8846dbc8588d42b2ac2925f1c52b54cc80e9a2a027af4f9` |

실제 코드 변경은 `render.py`, `gates.py`, `build.py`, `forecast/tests/test_mu_report.py`에 한정한다. 허용된 산출물·logs 보존/검증 파일·본 리뷰 외 파일은 수정하지 않았다.

## §2. 게이트

최종 명령: `python -m forecast.scripts.mu_report.build --phase E2-B --edition 1`.
최종 상태 **PASS**, failures `{}`.

- 사전: G-1 핀, G-2 FROZEN 표시, G-3 역사 항등식, G-3f SCORED 바인딩, G-7 template/IO, G-9 cutoff, G-12 manifest, G-14 provenance, G-15 구조, G-17 순현금 설정, G-18 hygiene, G-19 bridge, G-20 phase audit 및 narrative contract 통과.
- 사후: G-4 inventory, G-5 P/B, G-6 KO/EN 시장 데이터, G-8 KO/EN theme, G-10 narrative, G-11 placeholder, G-12b disclaimer, G-12c conflict, G-13/G-13b/G-13c KO/EN, G-15 parity, G-15b localized UI, G-16 caption 16개, G-17 KO/EN labels·순현금, G-17b KO/EN consensus, G-18 hygiene, G-21 formats/목차, G-23 availability, **G-24 PDF/XLSX markup and labels**, G-25 cover dates 통과.
- G-23 required failures 0; 미가용 감사 위치 84개로 R18과 동일.
- 이해관계 blob `393cb05876f6f5aabf6fbdb98778c69b8c5d06b6`은 변경하지 않았다. 최종 렌더 시작은 확인 후 24시간 미만이다.
- 최종 실행 감사: `logs/_mu_report_runs/e2b_20261005T121813+0900.json`; SHA-256 `e9a5d9aea19fd66c23cf0eb9d31add4897e1c6543827938c4caca1e74bd8493e`.

첫 R19 렌더에서 강화 G-24는 통과했으나 G-21이 `Summary lacks source metadata`로 실패했다. 실제판 Summary 교체 시 이전 출처·단위 행이 빠진 것이 원인이었다. 행 13을 복원하고 실제판 unit test에 G-21의 worksheet 메타데이터 검사를 추가한 뒤 최종 재렌더에서 통과했다. 게이트를 완화하지 않았다.

XLSX 시각 QA는 `logs/_mu_report_runs/ed1_r4_rejected/qa/summary_after.png`로 확인했다. PDF KO 17쪽·EN 18쪽은 R18 검증본과 SHA가 완전히 같으므로 R18의 전 페이지 시각 QA를 그대로 적용한다. PDF 본문·레이아웃을 새로 변경했다고 주장하지 않는다.

## §3. 산출물 SHA 및 보존

실제 최종 파일 바이트의 SHA-256이다.

| 경로(저장소 루트 기준) | bytes | PDF 쪽수 | SHA-256 |
|---|---:|---:|---|
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 36,032 | — | `7536749decdfe5661ba3746793a884dab7cbee062c268c57b9e2b39709712212` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 46,477 | — | `1a710f098cad03549c6572f6d00301455453e0536318bc89e80cd24f4b038182` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 27,929 | — | `d22250400d1858a7d65081277cb75d4e58b0458d16258a8854faeb8c9c184682` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 626,312 | 18 | `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | — | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 46,603 | — | `4992b1483a6ee4433e87f86678d021e79ac8fa4b5ff248f98f0cf4607b71ce7a` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 28,103 | — | `495bcbd936758494954ac81a5e96f4cf75e9fbc0813d546d2da14c7d48333313` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 806,139 | 17 | `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 394,803 | — | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` |

기존 R18 본체 9개 및 차트 16개를 **최종 덮어쓰기 전** `logs/_mu_report_runs/ed1_r4_rejected/`에 복사하고 9/9 본체 SHA 일치를 확인했다. 차트 16개도 최종본과 동일함을 확인했다. 이전 실행 감사 `e2b_20261005T112015+0900.json`도 보존했으며 SHA는 `1547238b319aa79aa53c092272bf208e9a0bfaf219a058521afbf0123b659451`이다. 삭제하지 않았고 복구 가능하다.

XLSX는 Summary·Facts 기준일 표시 변경으로 35,054 → 36,032 bytes가 됐다. 나머지 본체 8개는 R18과 완전히 동일하다. 검증 증거 `logs/_mu_report_runs/ed1_r4_rejected/qa/audit_r19.json` 및 이미지·검증 보조 파일은 E4에서 제외한다.

## §4. 테스트

| 실행 | 최종 결과 |
|---|---|
| `python -m pytest forecast/tests/test_mu_report.py -q --tb=short -p no:cacheprovider` | **80 passed**, 37.51s |
| `python -m pytest forecast/tests/ -q --tb=short -p no:cacheprovider` | **502 passed, 3 skipped, 1 deselected, 1 xfailed**, 116.15s |
| 최종 E2-B build | 전체 게이트 **PASS**, failures `{}` |
| 보존 R18 XLSX의 강화 G-24 | 예상대로 **RED**, 4셀 검출 |
| 최종 Facts A:G / 차트 / 비-XLSX 본체 | **759행 / 16개 / 8개 정확히 일치** |

R19 신규 6개 테스트: 숨김 시트의 세 금지 토큰 및 문자열 내부 FIXTURE 검출 4개, ed1 KO/EN 표지 문자열·Facts·G-21 메타데이터·G-24 통합 1개, 실제판 확인 문맥 필수 1개. 기존 fixture 바이트 결정성·fixture 렌더·DRYRUN 관련 테스트도 그대로 통과했다.

신규 raw_value 대조의 첫 실행에서는 XLSX 표준 숫자 직렬화의 끝자리 반올림 차이로 실패했다. raw manifest → XLSX 비교에만 `rel=1e-15, abs=1e-9`를 적용했으며, 실제 R18 → R19 Facts 셀 비교는 허용치 없이 정확 일치한다. 엔진 계산이나 fact 값을 변경하지 않았다.

skip 3개는 기존 Windows symlink/process-group 제약 및 gitignored EDGAR cache 부재다. xfail은 기존 FYE-August Q1 라벨 문제이며 수정하지 않았다. 유료 API·외부 자료 재수집·실적 재채점은 하지 않았다.

## §5. 최종 E4 후보 목록 — 명칭 검출 4개는 보류

### 제외·보류 판단

지정된 `forecast/HANDOFF_CODEX_mu_report_survey_r4.md`는 **후보 목록에서 제외**했다. 파일은 삭제/수정하지 않았다. SHA-256: `9bc9832ae33df578e11298b4612cc8e7761214382a6c32736e58f3e2d0b35e92`.

그 외 기존 후보 95개를 검사했다. UTF-8 텍스트는 내용 전체, PDF는 전 페이지 추출 텍스트, XLSX는 모든 시트 문자열 셀을 검사했다. PNG는 파일 바이트의 문자열 검사를 했고, 생성에 사용된 차트 텍스트 원천도 후보 텍스트 검사 범위에 포함했다. 동일한 플랫폼 명칭/도메인/영문 표기를 대조한 결과 **아래 계획 문서 4개에서 검출**됐다. public 리뷰에 해당 명칭 자체를 재기재하지 않는다.

| 보류 경로 | 검출 행 | 처리 |
|---|---:|---|
| `forecast/PLAN_mu_report_fy2026q4.md` | 96 | 수정 허용 범위 밖; E4 보류 |
| `forecast/PLAN_mu_report_fy2026q4_rev4.1_superseded.md` | 94 | 수정 허용 범위 밖; E4 보류 |
| `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md` | 95 | 수정 허용 범위 밖; E4 보류 |
| `forecast/PLAN_mu_report_fy2026q4_rev4_superseded.md` | 93 | 수정 허용 범위 밖; E4 보류 |

이 4개를 제외할지, 별도 허용 범위에서 정리할지 사용자에게 질의했으며 본 리뷰 작성 시 추가 승인은 받지 않았다. 따라서 **E4 전체 명칭 검사 CHANGES**이고 전체 목록을 무조건 커밋해도 된다고 승인하지 않는다. 나머지 91개에서는 같은 명칭이 검출되지 않았다. 아래는 최종 인벤토리 95개에 각 파일의 승인 가능/보류 상태를 명시한 목록이다. 본 리뷰 1개를 더하면 총 96개이고, 현재 검사 통과 대상은 91개 + 본 리뷰다.

### 경로·SHA·gitignore·상태

경로는 `F:/dev/Portfolio/business-valuation-tool/` 기준의 전체 상대경로다. `git --no-optional-locks check-ignore -v --no-index`로 각 경로의 적용 규칙을 확인했다. gitignore 대상은 **XLSX 1개·HTML 2개·PDF 2개, 총 5개**다. 나머지 90개 및 본 리뷰는 비대상이다. 이는 ignore 규칙 판정이지 추적 여부나 staging 상태 판정이 아니다. ignore 설정을 바꾸거나 force-add하지 않았다.

| 경로(저장소 루트 기준) | SHA-256 | gitignore 대상 | E4 상태 |
|---|---|---|---|
| `forecast/scripts/mu_report/__init__.py` | `257be815775597e3a96235f7e612f5f74f50a0e86c5a424a69e5c3984a90e9c8` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/build.py` | `91e7b3f40cbba0aec245e1795ef5d0fc897a23daef41270957ed26e67db12c9c` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/charts.py` | `d19579dcdeb3c218f37b508c666208c3d89657f29a4ccc893f115083e7325631` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/extract.py` | `0336ec14a21f748feb99f3fa351b27d85c560c67c3f4bc6938955140a106843e` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/facts.py` | `62e4e490845228bfcda0f27006614c30f0373c4a4c2b45657b6c2f4e01224e48` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/gates.py` | `1de5578cee7ad4968cafdc69dc3bc9501de0e84e7f32446a866b7225aca75b3d` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/i18n/en.yaml` | `eeb3158ba2dd57e7518145a82d3b0209c8db01065c196a121c5212c42bf9f9b9` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/i18n/ko.yaml` | `38d4dccec8514e0143d17084292c1ebdabf90c6e926113308a600b90e154adce` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/input_pins.yaml` | `2ffa42bb1d75d3a6ca6e80eed594fe60c0b7f20b867babfebd3dc3e701e716c0` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/inputs.py` | `5a204372f5848264da540628ba38be8f91c5d853aa349dd247e1e86ef6a00942` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/narrative.py` | `f5ff8cfd930a5956293383a38744f0147a7f0179169fb6e4f6b726f79552e8cd` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/render.py` | `a8d5c4fc3f54530b0a202d879ba47693c9fc8d395ff4f4cb23872b94f26f589f` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/rle.py` | `555472f731d5fa45a428056fc337d298979216a5c3d59348a133faabe0740ea8` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/annual_financials.json` | `cdfe815a6eef30f8e4a5f7de4c6f850001e2ee31e976bf2da2cc43f0ba670ea0` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/business_units.json` | `95afe0c79fa8a5882231a5856aadc1238afeb34b393378b7239b2dc84bce5414` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/companyfacts_quarterly.json` | `cd61b3f6780f05f82ebff5dc4628fd3cc5b1074da27631db15b1bbd2e3ecc2c3` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/debt_fcf.json` | `0bff823759b06cd9bb40e0a35c5d95fe6c77e97570734bb62dd8c18eef2d07ec` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/freeze_prereg.json` | `52e0f30a87646bb13a83f59022386e20e0849e7c0c7c2873f09ba0ae72a45402` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/guidance_history.json` | `7b498fce0cf7c49fd6c9431812ae9a6f233ce39f338c220ce87df99569e9c9f0` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/input_audit.json` | `54d780ecce5090c1341fab1ceb0adeb183cd6ccaad688eca972d32d890b0f80d` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/prepared_remarks.json` | `05038ac125c6fd097e2bfdf347e510ff7ce0ab60cf6a23695e4181e3fb482936` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/sources/release_tables.json` | `7c63641a7baa1d7d5711e3d25e6e88d97270ca797177aba3581d27d9fbb4b6f9` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/theme.py` | `bf5c73e3a6691c7beb8402bfd7c1101aa730763fd03aa9c95a66225e551c6e75` | 비대상 | 검사 통과 |
| `forecast/scripts/mu_report/valuation.py` | `1c46a3e7e7c565978e60d7ca000286d0ac27561f07c88c3b3fd824d690e8097d` | 비대상 | 검사 통과 |
| `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` | `1e8d4f98684f9bd4579bd7c79fffd51b06246446442b720b9819b8b7addf9d95` | 비대상 | 검사 통과 |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | `85e4d0c9bcf84adca608a7aaf1211a59f5c320bbc32c1ae299b172200792df0d` | 비대상 | 검사 통과 |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_edition_mismatch.yaml` | `79bfea05ab526b553d6e05294d448cb69d48440aad66dc0ef1510eab7815a1b8` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_expired.yaml` | `706e9fcf5d4b15264fc97c10cec5256b9f870d694e81e30fae7d804413d4493b` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_future.yaml` | `47746fd6d7a1c943f7cee4259f8ab3f240d2f9ef3957f5975fda84ccbb29c8c1` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_held.yaml` | `69a04cd362a3b0d1d29a7b16684826cae0b516a9e9cfed1b0e8d9d594cd1e972` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_missing_key.yaml` | `9da0d970fdf5c4bd5f9f02782c5a6028a9989f19076ce850d5fe6cab1103b017` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/conflict_confirmation_ok.yaml` | `3100acb4a699fc2475d4ee5cebb092d881d701fd91c966005577bb6117d27e40` | 비대상 | 검사 통과 |
| `forecast/tests/fixtures/mu_report/fake_postprint.yaml` | `4ef1e65e6993e4e1daef321847a9d6495421a00d8e29d17b679396ecb4d8dca1` | 비대상 | 검사 통과 |
| `forecast/tests/test_mu_report.py` | `c3b7812756dc23168e38fbb59192494b31a0632d5e2a2b7ce1661860b4548eae` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | `7536749decdfe5661ba3746793a884dab7cbee062c268c57b9e2b39709712212` | 대상 — `forecast/.gitignore:15:reports/*.xlsx` | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | `1a710f098cad03549c6572f6d00301455453e0536318bc89e80cd24f4b038182` | 대상 — `forecast/.gitignore:16:reports/*.html` | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | `d22250400d1858a7d65081277cb75d4e58b0458d16258a8854faeb8c9c184682` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | `beb73cec24fdb208700b6b4ea572c43c994f37a3766a359471443be01469d5e6` | 대상 — `forecast/.gitignore:17:reports/*.pdf` | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | `4992b1483a6ee4433e87f86678d021e79ac8fa4b5ff248f98f0cf4607b71ce7a` | 대상 — `forecast/.gitignore:16:reports/*.html` | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | `495bcbd936758494954ac81a5e96f4cf75e9fbc0813d546d2da14c7d48333313` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | `ee07871192dd7b58cb95dc26a05223625f87f3b7134c9d9cfeb2af1954dd462a` | 대상 — `forecast/.gitignore:17:reports/*.pdf` | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | `b6fe75edc3763a7abc97def2fa7cdbf1e096365187980bc02fdbabda15ba6812` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png` | `d69430ea4339d456ca05be74ae8d0f30c62b292d3ef5fa707d39b4ecdb270f25` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png` | `2636e62e1c82df11331c2f5710e6d1c416262bc54d07c801e12fdd63ec0104b2` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png` | `227ffde29da2ae523fed036dd84208b7e6827e2f540d1c59d5d4b638e517b50b` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png` | `2fcaf2996163053c8cc72e458a13de859dc55e12286ba03d5c3e9d371c346aa9` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png` | `27e7cfd681daebe67e2278aed5aa6afe8ffef0fb532e646f5693d8c0a3c808ea` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png` | `5b33e070265eef7e4198cc5ab273b81486bf5b90067f3ed8081ff6bb5dca3576` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png` | `085a16edf597842d78ecba2545c321f05daa2262399da1f3637823dd7c1f4638` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png` | `cceefb7c18ba77dfd838fff296d4b2059e969dca30b6b1fbb324995ce4902b42` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png` | `dd82634eca3346a37fdd6164a5f44696c206aeaecb9e103c74428cf92445565d` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png` | `7a5cbe1f72a09e145dbb9ce6ab818723e9ade7e8bde6011cceccda95aae9adf8` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png` | `78dea8b9997e713fc103e57dd32e040afdab65a72fac518b5af974a5bd8cd3dc` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png` | `4390091c0cc03c0791f07cdcb9f7dd6231a4d6f9fabcb882ae2aec003a434b71` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png` | `fd819824abb8cc8d27172249e0c8c61838707b1403a0ebfb7f9c91d40640aeea` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png` | `1ead96ea05256a65cf22b0f72bd95574141f845c901215537f836b3b58a5830d` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png` | `1ee978d72fba7f4ba25afbc490f98bcaefc07e8706ed2b4ebff2ab0f9c0840f0` | 비대상 | 검사 통과 |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png` | `0a7230adfea1ddd412548080dc7ac4ea32a278aca2f6a91d7defa0003f576517` | 비대상 | 검사 통과 |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | `bd7c9bb406da67fabb4b1bf5cef0465121c6414b0e5b27bb2023122a39dcb46e` | 비대상 | 검사 통과 |
| `forecast/PLAN_mu_report_fy2026q4.md` | `99de31cb5ccbb99aa9a4748ea955ea8cd946a64f6e1a379d9757a6add20d4492` | 비대상 | 보류 — 명칭 검출 96행 |
| `forecast/PLAN_mu_report_fy2026q4_rev1_superseded.md` | `d4d41b9ae3d65de68e39120663f9f7c1f56770574ec9d84af90988b9c8374fb0` | 비대상 | 검사 통과 |
| `forecast/PLAN_mu_report_fy2026q4_rev2_superseded.md` | `7f204ea2ec743a7997f6cd2c927facd2fd9be6aea283b05047ddf63fa2df1255` | 비대상 | 검사 통과 |
| `forecast/PLAN_mu_report_fy2026q4_rev3_superseded.md` | `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324` | 비대상 | 검사 통과 |
| `forecast/PLAN_mu_report_fy2026q4_rev4.1_superseded.md` | `35dc207b9d1cbb9a4b7c8352fa1199f75c0f64b2d6fb2b542b2f0a0f1249bdf5` | 비대상 | 보류 — 명칭 검출 94행 |
| `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md` | `32fc96edbaffa1c0952f9dc1d5a9f4b5eb2743ce41e482ea1b50b681689d5734` | 비대상 | 보류 — 명칭 검출 95행 |
| `forecast/PLAN_mu_report_fy2026q4_rev4_superseded.md` | `d007f554f68643891d7586f8c43c4254886f3826f54417c4e3144239f2a8e646` | 비대상 | 보류 — 명칭 검출 93행 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r1.md` | `0249ba02bd6c3665a7914dd802ce805e8bca88b8ab4034867765423fcbfd469a` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r2.md` | `22bbef4f0d289baedbf03a86dd5b0963df72c5e1f084a92dd1f522bce2093539` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r3.md` | `61dd170190095e9c1a8726e1249c4e7082183ae3a239360bf4409a717b270902` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r4.md` | `f3e3ac75ff87d1e16cba943b66fdbdfdd3b1ef9722484c53a848cb6cec1cf190` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r5.md` | `36b429f581e7732052d4bc79d642e3df147835d96d2b7872eac420cfb9eaa7ed` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r6.md` | `8775c96ed9c352eece06a9f6fd2c665d78d0b5383f8ad73a88126b8870de361b` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_output_r7.md` | `5b6edc261a2ba05a769cb814ebe465a2299b8e3f3050ceebe08abeca471fb87a` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_rle_r1.md` | `330db02cacc9a697d8563ea5c3f31ea6e83af18c73217b7d7ee4731348b2eb9f` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r1.md` | `f6bf58960ff59dec333d515bbb78079bd3bf4bbe5fa737f415c68d41e070e14a` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r2.md` | `95a13a2f9f2ec5a02d7eff4f26cc40d9010df3ef6af0be941432a4d5e1f35336` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r1.md` | `c70e05261271a69c859466130d8034a4d9a6e9f637de5d68ba8c67b270f1db0b` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r2.md` | `2a1dd4ab178bb2e9aee11311f75fc45d51f864d2cff413bcccd89b1ca65a2d3d` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r3.md` | `8273a1d1c6bb16c9ef3b7b1ebc1b87167a41ae6c596122aa0d7f16c38d7e62ef` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r4.md` | `23ad4173df2256f23fb7e0220e58d39587242102131bc1d99940450d9a457d46` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_pins_r1.md` | `94eeee88bab1c5a1888aacd5843cafabd892a0964dbe7bd632c13927622d2b9f` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_pins_r2.md` | `3b24da540e5701f6ba3f68d0689ba81600cd9006f74fce8a803f30966ffd0612` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_plan_r1_rerun_2026-09-28.md` | `0140a8c4a397af1e7a402172371a11602d09d88c53bbc0dd4eaa6414d431c321` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_plan_r2.md` | `3a8050cc9214fa3b97e6d4bb5a5ac31630e1cf0ce35e73f381acdeecd37d0470` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_plan_r3.md` | `cd2301bee6ac52201f2538aaf4d7c5b03f60b0b3855e158c10f6d4e6db070d4c` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_plan_r4.md` | `a0a95a2477a50a2244c3750a70beca3f83724a1acb0ba537b1a5d685ce65a976` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_rle_r1.md` | `bc14b9482aa06230cebefb8894cf751a1903c2122cf09bcd5036a284a9eaee4b` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_rle_r2.md` | `5bca5418ec2dfb0bbf9bc617ef09a7ee2a0de197747f18faf88ba1a0f804b6cc` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_rle_values_r1.md` | `57733f6d9131dfe4b3b96697f1530bdc3668ebcb2783cd7d6eee4cd3703b0ded` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_rle_values_r2.md` | `8012d34a8881567568b20fc440771156390f2426b942c36c8b9f33f0847fa74a` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_survey_r1.md` | `ae00afd2ab168627eaedc83489f0389842bbb2bc122b0c1a975d67ec0232762a` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_survey_r2.md` | `0f263d02a4e2e4f6d735b8fa3298eba99c4e7e2a3c6a674c18c75aab037d6c91` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r5.md` | `6f91cbe610529f55ee848e111b7cd324dbefc6c79133d61067587093ae4c8819` | 비대상 | 검사 통과 |
| `forecast/REVIEW_CODEX_mu_report_e2b_r6.md` | 최종 전체 파일 SHA는 최종 응답에서 별도 제공 | 비대상 | 본 리뷰; E4 보류 판정 포함 |

본 리뷰에 자신의 전체 파일 SHA를 넣으면 바이트가 다시 바뀌는 자기참조가 발생하므로, r5와 동일하게 최종 응답에서 제공한다. 위 95개 SHA는 각 실제 파일 전체 바이트를 다시 계산했다. 보류 4개는 목록에서 삭제했다고 간주하지 말고 E4 승인 시 명시적으로 결정해야 한다.

### 목록 제외 경로

- `forecast/HANDOFF_CODEX_mu_report_survey_r4.md`: R19의 명시적 제외.
- `logs/**`: 원본·가격 캡처·모든 실행 감사·거절 산출물 보존본·QA 이미지·검증 보조 파일. 특히 `logs/_mu_report_runs/ed1_r4_rejected/**`.
- `forecast/reports/mu_report_fy2026q4_ed1_assets/pages*/**`: PDF QA 페이지·overview; 후보는 루트의 차트 원본 16개만.
- `__pycache__/**`, `*.pyc`, 임시 파일, pytest cache.
- SCORED·FROZEN·프로파일: 선행 커밋된 읽기 전용 입력, 이번 E4 신규 후보 아님.
- 다른 회사·다른 기능의 dirty 파일.

E4는 보류 4개 처리와 정확한 파일 목록·SHA에 대한 Jiwon 승인 이후에만 진행한다. 본 작업에서 git 쓰기·커밋·push는 하지 않았다.

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

