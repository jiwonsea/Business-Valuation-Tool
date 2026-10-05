# MU FY2026 Q4 report R15 — E2-B ed1 렌더 리뷰 r2

> 결론: **GATE FAILURES — 산출물 유지, 수정·재렌더 없음.**
> 본 문서는 투자 자문이 아니다. ed1 KO/EN 렌더는 마감 전에 완료됐으나, 사후 게이트 2건(G-15, G-21)이 실패했다.

## 1. 렌더 명령·시각

| 항목 | 결과 |
|---|---|
| 기준 사전 게이트 리뷰 | `forecast/REVIEW_CODEX_mu_report_e2b_r1.md` |
| 기준 리뷰 SHA-256 | `c70e05261271a69c859466130d8034a4d9a6e9f637de5d68ba8c67b270f1db0b` — 일치 |
| 렌더 명령 | `python -m forecast.scripts.mu_report.build --phase E2B --edition 1` |
| 유효 렌더 시작 | `2026-10-04T15:13:03.862885+09:00` |
| R15 마감 | `2026-10-05T14:42:00+09:00` |
| 마감 판정 | PASS — 마감 약 23시간 29분 전 시작 |
| 이해관계 레코드 | `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` |
| 레코드 상태 | `not_held`, `edition: ed1`, `confirmed_at_kst: 2026-10-04T14:42:00+09:00` |
| 레코드 Git blob SHA | `393cb05876f6f5aabf6fbdb98778c69b8c5d06b6` |
| 레코드 SHA-256 | `1e8d4f98684f9bd4579bd7c79fffd51b06246446442b720b9819b8b7addf9d95` |
| 레코드 읽은 시각 | `2026-10-04T15:13:03.862885+09:00` |
| 감사 기록 | `logs/_mu_report_runs/e2b_20261004T151303+0900.json` |
| 감사 기록 SHA-256 | `f4b62543f18c4ae556bd0892c994b066c565c944df55c165471e8b0c5677e91a` |
| 렌더 종료 상태 | `GATE_FAILURES_NO_FIX` |

최초 동일 명령은 `2026-10-04 15:12 KST`에 렌더 진입 뒤 감사 기록 임시 파일의 권한 오류로 게이트 전에 중단됐다. 산출 경로 쓰기 권한을 허용해 같은 명령을 다시 실행했고, 위 시각에 유효 렌더를 시작했다. 두 번째 실행 뒤에는 코드·서술·숫자·규칙·산출물을 수정하지 않았고 재렌더하지 않았다.

## 2. 게이트 전체 결과

| 게이트 | 결과 | 확인 내용 |
|---|---|---|
| G-1 | PASS | E2-A/E2-B populated pin 경로·SHA 및 입력 읽기 |
| G-2 | PASS | Freeze A 표시값 |
| G-3 / G-3b / G-3c / G-3d | PASS | FY23A–FY25A 손익·재무상태·현금흐름 항등식과 company FCF |
| G-4 | PASS | 재고일수 |
| G-5 | PASS | trailing P/B 입력 날짜·산식 계약 |
| G-6 KO/EN | PASS | 시장 데이터 박스 |
| G-7 | PASS | 템플릿 숫자·직접 파일 IO 금지 |
| G-8 KO/EN | PASS | HTML 테마와 금지 스타일 |
| G-9 | PASS | PREREG_A/RLE 정보 계층 분리 |
| G-10 | PASS | 승인 서술 구조·12개 fact binding |
| G-11 | PASS | `section_stub`, fixture 문구, 미해결 fact token 없음 |
| G-12 | PASS | manifest 계약·금지 valuation 필드 |
| G-12b | PASS | KO/EN 면책문 |
| G-12c | PASS | 24시간·edition·KO/EN 표지/말미 및 PDF 전 쪽 conflict footer |
| G-13 KO/EN | PASS | 차트 계약 |
| G-13b KO/EN | PASS | 차트 fact identity |
| G-13c KO/EN | PASS | 차트 의미·축·단위 |
| G-14 | PASS | source SHA·as-of·path와 계산 lineage |
| **G-15 parity** | **FAIL** | `GateError: KO/EN normalized number multisets differ` |
| G-15b | PASS | KO/EN localized UI |
| G-16 KO/EN | PASS | 8개 차트 × 2개 언어, 총 16개 캡션 |
| G-17 KO/EN | PASS | 정정 라벨 및 `순현금(SCA 예치금 미조정)` / `Net cash (not adjusted for SCA deposits)` |
| G-17b KO/EN | PASS | consensus 표시 |
| G-18 | PASS | UTF-8/LF·trailing whitespace·텍스트 위생 |
| G-19 | PASS | 고정 비GAAP 브리지 계약 |
| G-20 | PASS | 결정적 입력 감사 목록 |
| **G-21** | **FAIL** | `GateError: TOC target page mismatch: 12. 부록` |

실패는 2건이다. G-15는 최종 KO/EN 문서의 정규화 숫자 multiset이 다르다는 판정이고, G-21은 KO PDF 목차의 `12. 부록` 기재 쪽과 실제 절 쪽이 일치하지 않는다는 판정이다. R15 지시에 따라 원인을 보정하거나 파일을 다시 만들지 않았다.

## 3. 렌더 산출물·SHA·쪽수

### 3.1 문서·데이터·manifest

| 산출물 | 바이트 | SHA-256 | 쪽수 |
|---|---:|---|---:|
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 27,993 | `3d63209534a3b147043c5686a4bda07391b18a27cfce9db2ac727e541e2bb5c5` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 27,948 | `17fc3319f8d12395aec719b449eeeda36c1d56810474603fc7c811f7201296ee` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 44,119 | `65d2029b0a3c5e04bde7806d29f48c13f00003b536a94929f9cf40892b4677a2` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 44,087 | `ceba4da13b660e6c174f5ad17897bdf11f3194a4b348d8abd59fc53e517f2de8` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 646,053 | `3ab25867c1b8ce42569f2fcd45362941144a8e0fccabf29f109ef4865d1b149f` | 15 |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 589,319 | `daa3efa9e980a6c0351a613ebe78ad12372cdb1a481af60391cd1b21417749bb` | 15 |
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 21,777 | `f2a1e21e4ef2aef179c94d833eacd09b07614e7a49010f962c54f74daa3ec793` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 226,625 | `c4cce9dca1a2b27c6edbc71ab61ea6051aec076bfc0da17c74a5dff2d52b3a24` | — |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 5,546 | `0334e5a1466f4d6dac96d88f2b0a9175db1c2c1f7e967e012c3284be4fd22e94` | — |

manifest의 `total_pages`도 KO 15, EN 15로 실제 PDF와 일치한다.

### 3.2 차트 PNG

| 파일 | 바이트 | SHA-256 |
|---|---:|---|
| `01_quarterly_revenue_margin_en.png` | 58,548 | `5ff40a48713ff906fc89906ed8cf36fa89f391d0f009bb4eaa64663b225dde96` |
| `01_quarterly_revenue_margin_ko.png` | 53,238 | `f08261e93005aaf7c70c7837ef04f8297b10d7cb5cded544e407b1a9d4ca0c95` |
| `02_business_unit_mix_en.png` | 29,690 | `9136ce05d7bc556fb8b39d6b36f61c8facacafae8d3ccd0ca245c6f88ca8c016` |
| `02_business_unit_mix_ko.png` | 26,063 | `837d07fd9931189334201361a7a54390e310aed440e7e3f1eabec73d17d905f4` |
| `03b_guidance_beat_history_en.png` | 45,005 | `cb4c2b48ecda31b836fc07cf9becbff9cf13290f9c5de5b3ff3ba4dfbbca2364` |
| `03b_guidance_beat_history_ko.png` | 41,585 | `80261c203e389fe486673c14cb1a0010163d25094d970e3db94c23b309391f71` |
| `04_beat_history_en.png` | 28,076 | `e297742153df06d86036b4d2bcad9530cd343be7ab1049a0a83537f4a46449d8` |
| `04_beat_history_ko.png` | 24,769 | `ca6a06beb60f71a415d02b6a7215585d63f332c764af2e0a076aa555e866521c` |
| `05_scenario_fan_en.png` | 43,409 | `fe985f9833f8228c86d98d64e028294e2e8537afb6cbbbe0ee276bb6131aadda` |
| `05_scenario_fan_ko.png` | 40,415 | `bbec9c440974726ae807152983939d308d51ea4928056814e6b6067588ff8450` |
| `06_annual_income_en.png` | 34,144 | `5b90f57395bffae9831e14202eb0caa3bdc55bb8a1853e6cff09849e6abad410` |
| `06_annual_income_ko.png` | 29,850 | `1d553f1bfd234492f9fda5e85185361bf0a7e15fd7e210b9c5d7cda43fcfd073` |
| `07_valuation_heatmap_en.png` | 16,789 | `f18d0eb125e84ce24d724c6b613400cef28d23fe6a150c2cc6b74b26025040a5` |
| `07_valuation_heatmap_ko.png` | 14,497 | `841a5ba06c736acb061382acc493d36ba0c3f517dea8fe50c63cc355ad8109cc` |
| `08_cash_flow_capex_net_cash_en.png` | 35,690 | `76f3bd33a34a1f9ba657e38feab7c0b4215e88d3b0e5c1959a7359fe6e91b12c` |
| `08_cash_flow_capex_net_cash_ko.png` | 31,179 | `b5153f218c2c1b15e9b10cae123f851e0df0d0101e217483d1a4f143dacebd83` |

위 16개 파일의 공통 경로는 `forecast/reports/mu_report_fy2026q4_ed1_assets/`이다.

## 4. 테스트

| 검사 | 결과 |
|---|---|
| `python -m compileall -q forecast/scripts/mu_report` | PASS |
| `python -m pytest forecast/tests/ -q -p no:cacheprovider --basetemp ...` | **482 passed, 3 skipped, 1 deselected, 1 xfailed** |
| E2B CLI 렌더·사후 게이트 | 렌더 완료, **39개 세부 PASS 기록 / 2개 FAIL** |

skip 3건은 Windows symlink 권한, Windows process-group 미지원, gitignore된 derived EDGAR cache 부재다. xfail 1건은 기존 FYE-August Q1 라벨 이슈이며 이번 범위에서 수정하지 않았다.

최종 상태: **G-15와 G-21 검토 전 배포 불가. ed1 산출물은 실패 당시 상태로 보존했다.**
