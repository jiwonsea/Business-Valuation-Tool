# MU FY2026 Q4 ed1 개정 1 — R22 시각 수정·재렌더 검증 r3

판정: **CHANGES REQUESTED — 기존 자동 게이트 60 PASS, 신규 게이트 1 FAIL; 표시 잔여 결함 4그룹. E4 보류.**

투자 자문이 아니다. R22 범위의 표시 구현을 적용하고 발행 렌더 **1회**를 실행했다. 실패 이후 코드·산출물 수정이나 재렌더는 하지 않았다. 테스트용 임시 PDF/차트 및 기존 PDF의 QA 이미지 변환은 발행 렌더 횟수에 포함하지 않는다. 서술 원문·수치·RLE 계산 규칙·이해관계 레코드·git은 수정하지 않았다.

## 1. V1–V16 조치·증거

| 항목 | 결과 | 조치·남은 문제 | 새 PDF 쪽·캡처 |
|---|---|---|---|
| V1 | PASS | C9의 두 축 범례를 plot 밖 아래의 단일 범례로 통합. | [KO 10](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-10.png) · [EN 11](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-11.png) |
| V2 | PASS | 전체 32개 PNG 내부 제목 제거. 실제 그려지는 제목·라벨 bbox 검사 및 잘림 음성 테스트 추가. | [KO 6](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-06.png) · [EN 7](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-07.png) |
| V3 | PASS | C11 EN을 OP to NI로 변경. missing-glyph 경고는 GateError로 승격. 실제 차트 경고 0. | [KO 8](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-08.png) · [EN 9](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-09.png) |
| V4 | 시각 PASS / 자동 FAIL | 정적 Regular/Bold 폰트 파일을 명시하고 워드마크·소제목·claim·리스크에 700 적용. 실제 30개 대상은 Bold이나 자동 게이트는 합자 인덱스 오류(§2). | [KO 4](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-04.png) · [KO 20](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-20.png) · [EN 6](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-06.png) · [EN 21](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-21.png) |
| V5 | PASS | 각 언어 21회 배치를 16회로 줄이고 후속 5곳은 그림 참조만 표시. | [KO 6](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-06.png) · [KO 11](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-11.png) · [EN 7](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-07.png) · [EN 12](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-12.png) |
| V6 | PASS | 첫 등장 1–16 재번호, KO/EN·본문 참조·manifest.metadata.figure_numbers 일치. C-ID 파일명 유지. | [KO 3](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-03.png) · [EN 4](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-04.png) |
| V7 | PASS | C12 회사 가이던스 60,000–63,000 범위 막대와 61,500 점, 폭 .65. 보조축 제거, 주당 성장률을 데이터 라벨로. | [KO 4](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-04.png) · [EN 5](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-05.png) |
| V8 | PASS | C16 상단 주석을 두 패널 밖으로 이동. 주석/패널 bbox 교차 시 실패하는 검사 추가. | [KO 5](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-05.png) · [EN 6](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-06.png) |
| V9 | CHANGES | 표지 값 오른쪽 정렬, $ 제거, FY27/28 매출·EPS 행 분리 완료. 다만 시장 데이터 기준 열의 USD/share·million shares·USD million 단위가 빠져 있음(§2). | [KO 1](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-01.png) · [EN 1](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-01.png) |
| V10 | PASS | 워드마크 700, 실제 ul/li 목록 적용. ed1 고정 thesis 중복만 제외; 서술 YAML은 불변. | [KO 1](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-01.png) · [EN 1](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-01.png) |
| V11 | CHANGES | 숫자 열 헤더도 오른쪽 정렬. 그러나 th에도 nowrap이 적용되어 긴 EN 헤더 잘림 및 재무표 FY26 헤더끼리 겹침(§2). | [KO 14](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-14.png) · [EN 10](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-10.png) · [EN 19](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-19.png) |
| V12 | CHANGES | 재무표 셀은 —†/—‡로 줄이고 손익·BS·CF 아래 기호 각주 추가. 비율표 아래 설명에는 †/‡가 빠져 있음. | [KO 14](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-14.png) · [KO 17](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-17.png) · [EN 15](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-15.png) · [EN 18](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-18.png) |
| V13 | PASS | table/tr/figure 분리 금지, thead 반복. 내재 배수 표가 KO20/EN21 한 쪽에 들어감. 16개 그림 모두 캡션과 같은 쪽. | [KO 20](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-20.png) · [EN 21](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-21.png) |
| V14 | CHANGES | 규칙표를 항목·문장형 규칙·이름 붙은 값·근거 등급·풀네임 출처로 변경, A12_sbc 등 키/SRC-ID 제거. 매핑 누락 0. 발표 후 변경 표는 클래스 분기 오류로 사유 열 10%/쪽 열 26%가 적용되어 읽기 어려움; 표 전체도 본문 폭을 넘음. | [KO 22](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-22.png) · [KO 23](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-23.png) · [EN 23](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-23.png) · [EN 25](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-25.png) |
| V15 | PASS | 캡션 내부 SRC-/CITED 제거, 출처 풀네임과 근거 등급·회계 기준 표기. 원천 ID는 canonical provenance에 유지. | [KO 6](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-06.png) · [EN 7](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-07.png) |
| V16 | PASS | 꼬리 숫자를 4분기·Form 10-K·USD 786 million으로 명시. 영어 식도 문장형으로 정리, 원천 수치 불변. | [KO 23](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-23.png) · [KO 24](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-24.png) · [EN 25](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-25.png) · [EN 26](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-26.png) |

전 쪽 시각 확인: **KO 24/24, EN 26/26**, 기존 C1–C8와 추가 C9–C16 PNG **32/32**. 원본 페이지 PNG는 `F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/`의 `ko-01.png…ko-24.png`, `en-01.png…en-26.png`이다. 110dpi 변환 후 전 페이지 모음 13장, 차트 모음 8장과 결함 쪽 원본을 확인했다. Poppler의 한글 설치 경로 nameToUnicode 경고는 있었으나 두 변환 모두 exit 0이며 50쪽 이미지가 빠짐없이 생성됐다.

R21의 C9 겹침·C10 내부 제목 잘림·C11 화살표 누락은 현재 그림에서 재현되지 않는다. C14 원천 검증 12분기는 모두 가용하여 제외 분기는 **없음**이며, 누락 시 NaN 빈칸 처리 및 추정·보간 금지 경로/각주를 유지한다. C10 구간 환산표는 J(판단), 회사 수치가 아님을 KO/EN 각주에 유지했다.

## 2. 게이트·테스트·실패 목록

### 2.1 실행·불변 조건

```powershell
python -X utf8 -m forecast.scripts.mu_report.build --phase E2-B --edition 1
```

| 항목 | 결과 |
|---|---|
| 실제 렌더 시작 | **2026-10-05T20:54:31.385866+09:00** |
| 제한 | 2026-10-06T19:07:00+09:00 이전; **충족**(22:12:28.614134 잔여) |
| 이해관계 확인 | not_held / ed1 / 2026-10-05T19:07:00+09:00; 경과 1:47:31.385866, 24시간 내 |
| 레코드 Git blob | `5248dd717931e990b427df597b7e433a13f359a4` |
| 종료 | exit 1, `GATE_FAILURES_NO_FIX` |
| runtime | `logs/_mu_report_runs/e2b_20261005T205431+0900.json` |
| runtime SHA-256 | `2b27aca2f8d83932c4b7763ddd012b18aa92f7ff15ecfd4c4ce0f2390811e7e3` |
| HEAD | `9e4c667b1750e129027a31b730ed338289f0e9b4` 불변; git 쓰기 없음 |
| 서술 r3 | `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f` 불변 |
| 가정 YAML | `292f4dce0ef5242e8072ce14d87320e022aa68ecb828712a8dd647752592c539` 불변 |
| 이해관계 레코드 | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` 불변 |
| R22 핸드오프 | `dce1129d74303e2ecbc28c2d98ce5618de967f46655e65665e9a8754084a3a38` 일치·불변 |
| canonical fact | R21 렌더 직전 baseline 대비 **878/878 전체 객체 일치**(raw_value, display, unit, period, basis, source_id, status, lineage/extraction 포함), 추가/삭제/변경 0 |
| rev0 보존 | `logs/_mu_report_runs/ed1_rev0_committed/` 25/25 SHA 일치 |

렌더 전 E2B 전체 사전 게이트 통과. 렌더 후 기존 60개 실행 단위는 모두 PASS: G-4/5/6/8/10/11/12b/12c/13/13b/13c/15/15b/16(32개)/17/17b/17 순현금 라벨/18/21/23/24/25. G-15 raw fact·참조 위치·KO/EN 숫자 multiset 일치, G-23 required_available_failures=[]이다.

G-23의 unavailable_count=7은 현재 literal UNAVAILABLE 검출 수이며 **—‡ 셀의 총수는 아니다**. 표시 축약 뒤 이 집계가 누락 셀 전수인 것처럼 해석하면 안 된다. required 셀 검사와 878개 canonical fact 불변 확인은 별도로 통과했다.

### 2.2 신규 검사와 회귀 테스트

`forecast/tests/test_mu_report_r22.py` **12개**:

- KO/EN 각 16개 그림 1회·첫 등장 순서 검사(2).
- KO/EN 표지 행·통화 기호·짧은 누락 마커 검사(2).
- 숫자 헤더 및 실제 목록 HTML 검사(1).
- KO/EN 부록·캡션 내부 키/ID 노출 검사(2).
- missing-glyph 경고 실패/정상 경로 검사(1).
- 잘린 글자 및 panel과 겹치는 figure 주석 음성 검사(1).
- KO/EN 실제 16개씩, 총 32개 차트 라벨 bbox·주석/범례 비겹침 검사(2).
- 실제 테스트 PDF의 Bold 텍스트 run 및 일반체 거부 검사(1).

수정 전 최초 문자열 회귀 검사 **7 failed**로 현 산출물의 중복 그림·표지 혼합 행·왼쪽 헤더/원시 목록·SRC/부록 키 노출을 확인했다. 수정 후 신규 12개 모두 PASS. Matplotlib가 보존하지만 실제 그리지 않는 축 한계 밖 tick은 검사에서 제외하고, 화면에 그리는 Text 및 figure 주석/범례는 검사한다.

기존 테스트 중 변경된 표시 계약($/내부 수식→단위 분리/문장식)과 중복 그림 제거 기대값만 갱신했다. 기존 데이터·수치 검증과 DRYRUN 테스트는 삭제·제외하지 않았다.

| 실행 | 결과 |
|---|---|
| 렌더 전 MU 3개 파일(신규 bbox 음성 테스트 추가 전) | 121 passed / 42.72s |
| 렌더 직전 신규 파일 | 12 passed / 10.98s |
| 렌더 후 forecast 전체 | 544 passed, 3 skipped, 1 deselected, 1 xfailed / 117.15s |
| 기본 설정에서 제외된 DART network 테스트 별도 | 1 passed / 0.52s |
| 최종 합계 | **545 passed, 3 skipped, 1 xfailed; 미검사 deselected 0** |

기존 skip: Windows symlink 권한, Windows process group, gitignored EDGAR 파생 cache 부재. 기존 xfail: FYE-August Q1 label 계약 불일치. 범위 밖이라 수정하지 않았다. 테스트 임시 폴더 6개는 정리했고 QA 캡처와 발행 파일은 보존했다.

완성 리뷰·scripts/i18n·관련 테스트 텍스트 20개 검사: LF, CR 0, NUL 0. 자기참조 SHA 대신 완성 리뷰의 외부 해시를 확인했다.

XLSX는 기존 생성 경로를 유지하고 Artifact Tool로 읽기 전용 재가져오기·오류 검색·Summary 화면 확인을 수행했다. 수식 오류값 0, 저장/재계산 변경 없음. [Summary 캡처](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/summary_xlsx.png). PDF 스킬의 전 쪽 시각 검증과 실제 글꼴 확인을 적용했으며, 이 검증에서 아래 자동 검사의 빈틈과 잔여 표시 결함을 발견했다.

### 2.3 남은 실패 — 수정하지 않음

1. **신규 자동 게이트 FAIL (V4):** `R22 presentation/glyph/bbox/Bold`가 EN p.6의 “Strategic customer agreements (SCAs) put a price floor under part of revenue.”에서 정지했다. 읽기 전용 진단으로 PDF의 `fl` 합자는 char 객체 1개지만 text 길이 2임을 확인했다. 게이트는 문자열 offset을 char 배열 offset으로 사용하므로 다음 일반체 캡션까지 잘못 검사한다. 같은 검사로 EN의 SCA price ceilings / One-offs / Rising investment / SCA structure도 오탐했다. 코드 변경 없이 진단에서 각 char.text를 문자별로 확장한 font 대응은 **KO15/EN15 대상 모두 Bold**였다(`*-Noto-Sans-KR-Bold`). 이는 시각 Bold 미적용과 구별되지만, 원래 게이트 FAIL을 PASS로 바꾸지 않았다. 신규 테스트는 앞선 본문 합자/다중 문자 char를 다루지 못했다.
2. **V9 단위 누락:** 표지 시장 데이터의 주가·희석주식수·시가총액 기준 열이 단위 없는 날짜/근거/식만 담는다. $와 M을 제거하면서 주가 USD/share 및 주식수 million shares를 기준 열에 옮기지 못했다. 시가총액 USD million은 아래 설명에만 남아 있다. 핵심 수치 표의 매출/EPS 단위·값 정렬·분리 행은 정상.
3. **V11 긴 헤더 잘림/겹침:** `.wide-number`의 nowrap이 th에도 적용된다. EN10 Absolute percentage error, EN19 Change / operating-margin contribution이 오른쪽 셀을 벗어나 잘리며, KO14–17/EN15–18 FY26E PREREG_A 헤더는 인접 FY26A 헤더와 겹친다. EN10 header text x1=550.8pt, EN19=554.1pt, 오른쪽 셀 경계=543.9pt로 재확인했다.
4. **V12 비율표 기호 각주 미완료:** KO17/EN18 셀에는 —†/—‡가 있지만 아래 설명은 †/‡ 접두 없이 나온다. 앞의 손익·BS·CF 각주는 기호가 정상이다. 가용/미가용 raw fact를 바꾸지는 않았다.
5. **V14 변경 표 열 폭·표 외곽:** Item/항목을 먼저 판별하는 분기가 모든 5열 변경 표에도 `appendix-rules`를 부여하여 `post-print-changes` 분기가 도달되지 않는다. 따라서 사유 10%·쪽 26%가 적용돼 KO23/EN25 문장이 지나치게 좁게 줄바꿈되고 쪽 숫자는 여전히 맨 끝이다. 규칙표 및 변경 표의 오른쪽 외곽은 581.4pt로 본문 오른쪽 549.9pt를 31.5pt 넘는다. 내부 키 제거/출처 풀네임화는 됐지만 V14 전체를 PASS로 볼 수 없다. M1/X1 등의 원안 기호와 일부 EN 상태 코드도 독자용 풀이가 더 필요하다.

따라서 **재렌더 1회에서 중단**, 발행/커밋 승인 요청으로 넘기지 않는다. 게이트 오탐 또는 시각 결함을 수정하려면 별도 지시가 필요하다.

## 3. 산출물 SHA·쪽수

| 산출물 | 쪽수 | SHA-256 |
|---|---|---|
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | — | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | — | `e669c2c4d464f9347c0d27fdc296456a14eba267d9ac9d62a8592db87bec1f07` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | — | `a455be6decef98c0ec6fc437ee387638db616ff2573cec5ba95bc3186305322b` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 26 | `0f00d5a4ff668526a77aeff0cc1c3d18c87ca7b34b7dd0e110a40bdc3d5d4523` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | — | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | — | `71653c67647eae55c3aabac99de18b58f6d10c0c2543ec108d2a7ac3e5d6bf22` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | — | `f237728d22aed5764384e8108d417912831902c2f108c9a15f4903ac8a4b0d58` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 24 | `c6169c903873f34d30308df4ce8d687b1792a02bbb8fa20b17b40fc40e3c2534` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | — | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` |

PNG 32개 개별 SHA는 §5에 기록했다. KO 26→24쪽, EN 27→26쪽(R21 대비). 이미지 내부 제목/중복 그림은 제거됐지만 전체 PASS 산출물은 아니므로 현재 파일은 **검토용·승인 보류** 상태다. XLSX 및 input_manifest는 R21과 바이트 동일하다.

## 4. R22-2 범위 밖 — 보고만

- §5 사업 구조는 연결 문장 1개와 그림/가격·비트 해석으로 구성돼 회사 사업 자체 설명이 얇다. 위치: [KO 11](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-11.png), [EN 12](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-12.png). 서술 r3 YAML은 그대로 두었다.
- 부록 방법론과 정보 경계는 층 구분과 컨센서스 미가용을 적은 짧은 문단뿐이다. 위치: [KO 24](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/ko-24.png), [EN 26](F:/dev/Portfolio/business-valuation-tool/logs/_mu_report_runs/ed1rev1_r22_20261005T205431/pages/en-26.png). 방법론 서술을 확장하지 않았다.
- FY27E/FY28E base 매출 raw_value는 각각 **274784.139585 USD million**으로 정확히 같고 표시는 274,784이다. 직접 규칙은 **A8_fy2028_revenue_growth.base=0.0**, 즉 FY28E=FY27E×(1+0.0)이다. R22의 “A3 flat”은 매출 같음의 직접 원인이 아니다(A3는 GAAP GM 경로). A3·A8이나 결과는 변경하지 않았다.

## 5. E4 후보 목록 — 승인 보류

최종 관련 후보 **60개**(아래 59개 + 이 리뷰 1개). 전체 게이트/시각 PASS 이후 재확인할 후보일 뿐, 이번에는 승인 목록이 아니며 git 쓰기는 하지 않았다. R20부터 이어지는 관련 변경을 포함한다. 서술·레코드·핸드오프·이전 리뷰는 선행 변경/증거로 읽기만 했다. PNG는 이번에 내부 제목이 모두 제거돼 기존 C1–C8 16개도 후보에 포함한다.

gitignore 열은 `git check-ignore --no-index`의 **규칙 적용 여부**다. 이미 추적 중인 PDF/HTML/XLSX가 Git에서 빠진다는 의미가 아니다. 레코드를 포함하되 `input_pins.yaml` 등록이나 새 보유 확인을 하지 않았다.

| 경로 | gitignore 규칙 대상 | SHA-256 |
|---|---|---|
| `forecast/scripts/mu_report/build.py` | 아니오 | `3a7a5e973fd0fa4ca5c72fb4842ea6a7f5c465902dc001a9f9e0f06c78412552` |
| `forecast/scripts/mu_report/charts.py` | 아니오 | `fa55c60a08374fdbb683a5f534e777ceb8b3905e53fd14d94d7da9f95cbceb71` |
| `forecast/scripts/mu_report/gates.py` | 아니오 | `8ed4aa2981949a0609b6a48ff1ce01420aa603968ca26a91d094f50946498fed` |
| `forecast/scripts/mu_report/i18n/ko.yaml` | 아니오 | `9094af9374df44a030638b9417526f964d11691c7c54ce1551cbffe992a268c3` |
| `forecast/scripts/mu_report/i18n/en.yaml` | 아니오 | `0fcecbce01bd21ab3143c8e13b399cd53ae4580afe840b33e189c1f8f1d199cb` |
| `forecast/scripts/mu_report/narrative.py` | 아니오 | `c65942565e8525c7b1e5f4bcd8cea1cd403fe7448daa8e71e425c95b7a822044` |
| `forecast/scripts/mu_report/render.py` | 아니오 | `43e729fd3bbf8f8a14509110ef5b6ca404c6e3c69101ad99f6466e545d239504` |
| `forecast/scripts/mu_report/revision.py` | 아니오 | `4c3085d0ec48a9fe704f08307daf48f0a00e92fa8ac32604709ab654fb2476e7` |
| `forecast/scripts/mu_report/theme.py` | 아니오 | `a4348a379bfe532f0951731e9f7cefba8759cc7c9c87453695cc65036f85eacf` |
| `forecast/scripts/mu_report/presentation.py` | 아니오 | `3d74cba4ae0c238b9219d196b8caa6f43e38df734d78a0f7a0bc6bd5fdc8acfc` |
| `forecast/tests/test_mu_report.py` | 아니오 | `3a2ce7203088b1601ca964fd571c2c76ff3afee6c3450461ce9035417b26654c` |
| `forecast/tests/test_mu_report_revision.py` | 아니오 | `69be43a29c180fc0a454b3792fe743dbc48d2460d84f490e9ca81a2a70088a26` |
| `forecast/tests/test_mu_report_r22.py` | 아니오 | `34d1980497a719a0b09b81cef0e466bf94469d57dd08f07585db04beefb64777` |
| `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` | 아니오 | `52cdbbf211c7710b9210fcd0b3cd52d1c5485f7ff1b3e607f2d4f8606aa6a39f` |
| `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` | 아니오 | `49e9d7a0bef2471d6c4e872f9c15fbf9600f0335deef687ffea0cb0ee0843ad2` |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | 아니오 | `dce1129d74303e2ecbc28c2d98ce5618de967f46655e65665e9a8754084a3a38` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md` | 아니오 | `21a121ca135209248c56f985093b6500f9237c2c153dc5ef6d2ca485a7717613` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md` | 아니오 | `3e17e43411db57df3ececdb6467826a6398cb5c4b4b13919daa8f363efd4efc7` |
| `forecast/reports/mu_report_fy2026q4_ed1_data.xlsx` | 예 | `4bf278a465611c80cdc530204ce13115377c167c0e2b95e857e3748661e745c5` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.html` | 예 | `e669c2c4d464f9347c0d27fdc296456a14eba267d9ac9d62a8592db87bec1f07` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.md` | 아니오 | `a455be6decef98c0ec6fc437ee387638db616ff2573cec5ba95bc3186305322b` |
| `forecast/reports/mu_report_fy2026q4_ed1_en.pdf` | 예 | `0f00d5a4ff668526a77aeff0cc1c3d18c87ca7b34b7dd0e110a40bdc3d5d4523` |
| `forecast/reports/mu_report_fy2026q4_ed1_input_manifest.json` | 아니오 | `7412ffe8f4892526cecfe83bc797da1ff45ead2363a7ae51c2e25cec20ac033e` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.html` | 예 | `71653c67647eae55c3aabac99de18b58f6d10c0c2543ec108d2a7ac3e5d6bf22` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.md` | 아니오 | `f237728d22aed5764384e8108d417912831902c2f108c9a15f4903ac8a4b0d58` |
| `forecast/reports/mu_report_fy2026q4_ed1_ko.pdf` | 예 | `c6169c903873f34d30308df4ce8d687b1792a02bbb8fa20b17b40fc40e3c2534` |
| `forecast/reports/mu_report_fy2026q4_ed1_manifest.json` | 아니오 | `976f159a482d65a1788c3107d0a897ef05585b93917157bc03587f09e6e55c25` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_en.png` | 아니오 | `4cb2d69316f2884d62aca2a779379a430b232f013605dec8847c2cdc2435400f` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/01_quarterly_revenue_margin_ko.png` | 아니오 | `54962a82472f9a7b4c377fcf2b0d81f46918e8ee9f3e610461e08c6e4839a617` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_en.png` | 아니오 | `f9a26d72e804612c17fbc52fbb87dbd76edfd3911213e222fd777e95ee0f0c2b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/02_business_unit_mix_ko.png` | 아니오 | `ac6673ec2946b7bff0abc024eda654052e8dbea8919a0a45b4dde6a8f55be577` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_en.png` | 아니오 | `b4d375b06ec0b67b10796e79a34a4642cdf7cd626b1b975e5af9daf37b0a4278` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/03b_guidance_beat_history_ko.png` | 아니오 | `2520d2c694dddf315891acc6692327a2888bb1e4637a9229a7dc9873ed89ae96` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_en.png` | 아니오 | `2d18c30a944c805d4279ee5899516e55f20568db1696cf5f03376ebf3eeb57b0` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/04_beat_history_ko.png` | 아니오 | `b9015ee57ad4feb8949e72567c039ba9a2cd32cb986a83e7ef0f794a76f2e4be` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_en.png` | 아니오 | `750d144cf70feb8ce2c9e1168c5e6f1e0148dd92c16f455f8146af6f30e646af` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/05_scenario_fan_ko.png` | 아니오 | `f9d01357b0b65ca82fdf4d010ffc78c6c22110431561d234fe189d60e5cd2e4e` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_en.png` | 아니오 | `293b3e6fa519e813cd638a2c8571433c7a04d85e385c5ee481e52cbb80c14072` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/06_annual_income_ko.png` | 아니오 | `5c4e1ab8d08b162a5278cc264947ae4546c4d139257b1c8ca90f8adef102809c` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_en.png` | 아니오 | `bf6ed0e898d5923c49e358877dfac605d5305ceaa09b59b3b2550a24e6db7436` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/07_valuation_heatmap_ko.png` | 아니오 | `b0f491ab66f1540119d26a81a84fbfd44bab489c1d39c1205a3cc3f8fc246eb1` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_en.png` | 아니오 | `97790c08cb563dde15f40e6204e883320d48a22b53f03d499537cab3c98899e7` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/08_cash_flow_capex_net_cash_ko.png` | 아니오 | `01b6f2851524c4f1a3b726ee23df8d01dfc28db30241c19658d11bcc2260ff8b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_en.png` | 아니오 | `807c1e9f47cd85cd13b61eeb64327044f8f52fb52e895c46440bb55ed3746966` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/09_gm_beat_compression_ko.png` | 아니오 | `8669c2f2e49e2aa7f9502c715ed1812a1a052bde339c9e7a8e565a85749735df` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_en.png` | 아니오 | `010a8575fc633a7c3b1d45a28f0f3e364ba9a53a2da254726587c781ffc85da7` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/10_price_bit_ranges_ko.png` | 아니오 | `209a60fcfe4059fb3e1ab0e3299cdfc3a1cbb3f73042a0c416695076cffaecba` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_en.png` | 아니오 | `294070aa2fe4d85bfcec49f041ec4ea7ce4f7e62a22f8b3b4712f173adc7915c` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/11_eps_error_waterfall_ko.png` | 아니오 | `c956bd37b90b72da20df90b0f4cac7f9f9804aa740d0c46967cc506c94304cac` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_en.png` | 아니오 | `3ab01bf2fddb92cf65e4a213fcc3bd9d6ad8d0d4fc8979f5c43e627f10a9c085` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/12_fq1_guidance_comparison_ko.png` | 아니오 | `e797421ac0d5b26d0cb3dffe51e7388aa8a8634399fa276a64acc8e0cb1fd32b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_en.png` | 아니오 | `43d522994006a07a97e56d4e9be8c442f335570863f651ebee1d2b460d01bfbf` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/13_scenario_sensitivity_eps_ko.png` | 아니오 | `3f9706ef0073bd9069fa040527b9273b6f3354752151f2961ce7e52e01684185` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_en.png` | 아니오 | `c6a02db4cbaa2e1212510e70ca50990fe24bf02cd04d805b8090fa6a296818d5` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/14_opex_net_capex_trend_ko.png` | 아니오 | `3431cff875414ff7cbf630e52f534c0432ee3d55670e2df2c84237c0d1cb0f43` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_en.png` | 아니오 | `978a406fb9d69ac11f141bef2b6e963e9455f4888bfc21b737ad0ab9e415a4e6` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/15_operating_income_waterfall_ko.png` | 아니오 | `17beb41016e0fc04341806a008d5ab544233bea127deff7dc5e5a1fe2b076a3b` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_en.png` | 아니오 | `893f554bc035177882f394af6f380c73495961c45ac149805ffbe011af3cf33c` |
| `forecast/reports/mu_report_fy2026q4_ed1_assets/16_sca_structure_ko.png` | 아니오 | `9cc5de886af4bb953b193829757800fd17da9b29b93e09e707766c1b2de7db88` |
| `forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md` | 아니오 | 자기참조 SHA는 본문에 넣지 않음; 완성 후 외부 해시 확인 |

제외: RLE 가정 YAML·가격·원천 pin·SCORED·FROZEN(변경 없음), `logs/**` runtime/QA/rev0 보존, 이번 테스트 임시 폴더, 과거 assets/pages 계열 QA, survey_r4 핸드오프, rev-4~4.3 보존본, 관련 없는 기존 작업 트리 변경(CLAUDE.md 등). 원본 서술/수치/RLE 규칙/레코드/기존 리뷰/보존본은 보호 검증 대상으로 유지했다.

---

본 문서는 투자 자문이 아니다. This document is not investment advice.

