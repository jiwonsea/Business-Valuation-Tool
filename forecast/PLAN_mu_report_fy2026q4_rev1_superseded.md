# PLAN — Micron (MU) 리서치 리포트 · FY2026 Q4 기준 · 한/영 2판 **rev-1**

> 작성 2026-09-26 KST · 작성 Claude · 검토 요청 대상 Codex (P2) · 승인 Jiwon (P3)
> 근거 프롬프트: START "MU research report (based on FY2026 Q4)" 2026-09-25 · 선행 배치 MU Freeze A (`f8cfd47`, FROZEN sha256 `eab1184f…629f9a`, frozen_at 2026-09-25 08:54:41 KST)
> 🔴 **투자 자문 아님.** 본 계획과 모든 산출물(한국어판·영어판)은 투자 자문이 아니며 특정 증권의 매매를 권유하지 않는다.
> 🔴 **코드·리포트 미착수.** 본 rev-1은 계획 문서 1개만 신설한다. 다른 파일은 읽기만 했다.

---

## §-1. 리비전 이력

| rev | 일자 | 판정 | 내용 |
|---|---|---|---|
| rev-1 | 2026-09-26 | (Codex 검토 대기) | 최초 작성. P0 선례 인벤토리(부록 A) · D1–D9 제안 · 허용 경로 · 게이트 G-1~G-18 |

> Codex 실패 패턴 3(항목 번호 누락) 방어: 회신은 **§9의 Q-1부터 번호 그대로** 판정해 달라. 번호가 빠지면 해당 항목은 미판정으로 본다.

---

## §0. 요지

1. **발행 형태**: 프린트(추정 2026-10-01 05:01 KST) **후** `Review & Outlook` 1판을 본판으로 낸다(D1 ⓑ). 프린트 전(9/27~9/30)에는 **프린트와 무관한 인프라만** 만든다 — 과거 3개년 재무제표·분기 추이·차트 틀·밸류에이션 틀·한/영 렌더러·게이트. 프린트 전 프리뷰판(ⓐ)은 **내지 않는다** — Freeze A 자체가 이미 봉인된 사전등록 문서이고, 프리뷰판은 그것의 재서술에 그친다.
2. **P0에서 드러난 사실 3건이 START의 전제를 바꾼다** (상세 §1):
   - (a) START가 지목한 `forecast/reports/sk_hynix_20260913.*` 은 셀사이드 형식 리포트가 아니라 `forecast/cli.py` 자동 산출 예측 페이지다(헤드라인 `Revenue MAPE 0.0%`, EPS MAPE 공란, 백테스트 표 빈칸). **실제 최신 형식 선례는 `valuation-results/2026-08-26-nvda-q2-preview/`(NVDA, 2026-08-26)와 `valuation-results/2026-08-07-hynix-q2-update/`(SK하이닉스, 2026-08-07)** 다.
   - (b) `valuation-results/` 는 **`.gitignore` 대상**이며 추적 파일 0개다. 선례 리포트는 **한 번도 커밋되지 않았다.** START의 "커밋" 요구를 지키려면 산출 위치를 추적 경로로 바꿔야 한다(D7).
   - (c) 리포는 **public** 이다(`PLAN_efe_2026sep_mu.md` D3-b, 2026-09-13 확인). 푸시 = 리포트 전문 공개다. 푸시 결정(E4 이후 별도)에 이 사실을 올린다.
3. **밸류에이션**: 목표주가·투자의견·적정가치·확률가중 주당가치는 **자료구조에 필드를 두지 않는다**(NVDA G-12a 상속). 주 표는 **시나리오별 암시 배수**(가격 ÷ 이익). 역방향 DCF는 rev-1 범위에서 **제외 제안**(D3) — MU용 BVT 프로파일이 없고, ERP 출처 문제(NVDA 부록 A `ERP-UNSOURCED`)가 그대로 재발한다.
4. **Freeze A 수치는 한 자리도 바꾸지 않는다.** FY27E·FY28E는 별도 YAML의 **리포트 레이어 추정**으로 분리 표기한다.

---

## §1. P0 결과 요약 — START 전제와 다른 점

| # | START 전제 | 실측 (2026-09-26, 읽기 전용) | 계획에 미치는 영향 |
|---|---|---|---|
| P0-1 | 형식 선례 = `forecast/reports/sk_hynix_20260913.*` | 해당 파일은 `forecast/cli.py` → `output/{md,html}_builder.py`·`static_charts.py` 자동 산출. 9개 절 중 서술 없음, 헤드라인 지표 결손, 백테스트 표 공란, 분기 라벨 2025Q1–Q4. PDF는 호스트 Chrome 인쇄(헤더에 `26. 9. 13. 오전 3:56` 잔존) | **형식 모델로 쓰지 않는다.** 차트 2종(fan · beat/miss)의 개념만 참고. 결손은 NOTICED BUT NOT TOUCHING |
| P0-2 | 최신 NVDA 선례 = `forecast/reports/T4_…`·`T3_…` 등 | 그것들은 **중간 산출물**(역방향 DCF·판정 초안). 최종 리포트는 `valuation-results/2026-08-26-nvda-q2-preview/NVIDIA_기업분석보고서_2026-08-26_김지원.{md,html,pdf}` + `NVIDIA_재무데이터_3개년_2026-08-26.xlsx` + `PLAN_nvda_report_2026-08-26.md`(rev-3) | **NVDA 08-26을 1순위 형식 선례로 삼는다.** T1–T4·V2·FREEZE_A·MANIFEST는 방법론 선례 |
| P0-3 | 산출물 커밋 | `valuation-results/` gitignore, `git ls-files valuation-results` = 0 | 산출 위치를 `forecast/` 하위 추적 경로로(D7) |
| P0-4 | 한/영 2판 | 선례는 **전부 한국어 단일판**. 영어판 선례 없음 | 한/영 패리티 설계는 **신규**(D5·G-15) |
| P0-5 | 개행 | 루트 `CLAUDE.md`·`codex-cross-review.md`는 "CRLF 유지", START·`forecast/*.md` 실측은 **LF**. NVDA G-10은 CR 금지 | `forecast/**` 신규 파일 = **LF**(현행 `forecast/*.md`와 일치). Q-9로 확인 요청 |
| P0-6 | 밸류에이션 경로 | `forecast/engine/valuation_bridge.py`는 **컨센서스 EPS gap × 탄력도** 구조. MU 컨센서스는 `UNAVAILABLE` → 브리지는 None을 낸다. FROZEN 말미: *"예측 출력은 밸류에이션 입력에 연결하지 않는다"* | 브리지 **미사용**. 밸류에이션은 가격 기준 암시 배수로(D3) |
| P0-7 | 발행사 로고 | SK하이닉스 08-07·NVDA 08-26 모두 **발행사 로고·브랜드 팔레트** 사용 | START는 증권사 브랜딩만 금지. 발행사 로고도 **쓰지 않을 것을 제안**(D8) |
| P0-8 | 사후 채점 문서 | 명명 선례 `sndk_fy2026q4_SCORED.md`. **`mu_fy2026q4_SCORED.md` 없음** — 2026-09-26 13:45 KST 현재 프린트 전 | D1 ⓑ는 채점 문서 생성에 **의존**. 본 리포트는 채점을 하지 않는다(§4-3) |

---

## §2. 결정 사항 D1–D9 (Codex 판정 요청)

### D1. 발행 시점·형태 — **제안: ⓑ 단독 + 프린트 전 인프라 선행**

| 옵션 | 판단 |
|---|---|
| ⓐ 프린트 전 Preview | 정보 컷오프 = Freeze A. 그러나 Freeze A 문서가 이미 봉인·커밋된 사전등록이다. 프리뷰는 그 재서술이며, 남은 4일 안에 한/영 2판 + 게이트까지 통과시키면 봉인 규율(NVDA `seal.py` 엠바고 차단) 없이 급조된다. **불채택** |
| **ⓑ 프린트 후 Review & Outlook** | FQ4 실적 + FY26 연간(PR 잠정 → 10-K 확정) + FQ1 FY27 가이던스 반영. Freeze A를 "사전등록 예측 vs 실적"으로 제시(채점 결과는 SCORED 문서에서 인용만) |
| ⓒ 둘 다 | 산출물·게이트 2배. 이득 대비 비용 과다 |

**일정(제안, KST)**

| 블록 | 기간 | 내용 | 프린트 정보 사용 |
|---|---|---|---|
| E2-A | 09-27 ~ 09-30 | 과거 FY23A–FY25A 3표, 분기 추이 FY23–FY26Q3, 차트 틀, 암시 배수 틀, 한/영 렌더러, 게이트·테스트 | **금지** (G-9) |
| (외부 의존) | 10-01 ~ | EFE 사후 채점 `mu_fy2026q4_SCORED.md` — **별도 작업, 본 계획 범위 밖** | — |
| E2-B | SCORED 커밋 후 | FQ4·FY26 실적, FQ1 FY27 가이던스, 리포트 레이어 FY27E·FY28E, 본문 서술, 렌더 | 사용 |
| E2-C | 10-K 접수 후(선택) | FY26 잠정값 → 10-K 확정값 교체. 차이가 있으면 errata가 아니라 **판 번호 올림** | 사용 |

- **FY2026 라벨 변경(START §3과 다름 — Q-2)**: ⓑ에서는 FY2026이 추정이 아니라 **실적**이 된다. 따라서 연간 표는 **FY2023A · FY2024A · FY2025A · FY2026A(잠정, 8-K) → FY2027E · FY2028E**. START의 "3 historical + FY26E"는 ⓐ 전제의 문구로 보고, ⓑ에서는 FY26을 A로 올린다. FY23은 regime break(2024Q1) 이전 — 재무제표에는 싣고 백테스트 표본에는 넣지 않는다(START 동일).
- **SCORED 문서가 없으면 E2-B는 멈춘다.** 채점 수치를 리포트 스크립트가 재계산하지 않는다(START §1-5).

### D2. 예측 범위 — **제안: FY27E 분기 4개 + FY28E 연간만**

| 구간 | 출처 | 라벨 |
|---|---|---|
| FQ4 FY26 | Freeze A 원값(표시 반올림만) vs 실적 | `PREREG_A` / `ACTUAL` |
| FQ1 FY27 | 회사 가이던스(프린트) → 리포트 레이어 시나리오 | `REPORT_LAYER_ESTIMATE` |
| FQ2–FQ4 FY27 | 리포트 레이어 YAML(주당 성장·GM·opex·세율·주식수) | `REPORT_LAYER_ESTIMATE` · 확신도 **하** |
| FY28 | **연간 단일 행**(분기 분해 안 함 — 거짓 정밀도 회피) | `REPORT_LAYER_ESTIMATE` · 확신도 **하** |

- **Freeze A 프로파일의 FY27 Q1–Q3 경로는 쓰지 않는다.** FROZEN (c-3)가 "FY27 Q2~Q3는 동결 대상이 아니다"라고 적었고, 프린트 후에는 FQ1 가이던스라는 더 나은 앵커가 생긴다. 두 경로의 차이는 부록에 1표로만 병기(Q-3).
- **YAML 위치**: `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` (신규). 근거 — (i) `forecast/inputs/` 는 추적 경로이며 `*_actual.yaml` 선례가 있다 (ii) `forecast/profiles/` 에 두면 `test_valuation_allowlist.py`·프로파일 로더 스캔 대상이 된다 (iii) `forecast.md`의 "assumptions belong in profiles/*.yaml"과 문자상 충돌 — **Q-4로 판정 요청**.
- **계산 경로(Q-5)**: 리포트 레이어 손익은 `run_generic_forecast`를 **메모리 내 `GenericProfile`**(FQ4 실적을 seed로, `mu.generic.yaml` 은 읽기만)로 호출해 산출하는 안을 1순위로 제안한다. 엔진 계산을 리포트 스크립트가 복제하는 것은 `reporting-boundary.md`가 3회 반복 안티패턴으로 기록한 패턴이다. 단 엔진의 window·스키마가 8분기/연간 혼합을 받지 못하면 **엔진을 고치지 않고** 리포트 레이어 산술로 내리고, 그 사실을 본문 방법론에 적는다.
- 주수: FY2027·FY2028은 **52주(분기 13주) 가정** — 10-K 회계연도 주석으로 확인 전까지 `ASSUMED` 표기. FY26 53주·FQ4 14주 각주 유지.

### D3. 밸류에이션 깊이 — **제안: ⓑ의 축소형 = 시나리오 암시 배수 + 민감도. 역방향 DCF 제외. 투자의견·목표주가 없음**

| 항목 | 제안 | 근거 |
|---|---|---|
| 주 표 | 기준가 1개(거래일·출처 고정) ÷ {FY25A, FY26A, FY27E bear/base/bull, FY28E bear/base/bull} → **P/E · EV/EBITDA · EV/Sales · FCF 수익률** | 할인율이 필요 없다 → ERP 출처 문제를 피한다 |
| 사이클 경고 | **피크 이익 × 배수 이중계산** 경고를 본문에 명시(SK하이닉스 08-07 §2-3 논리 상속). FY23A(적자, P/E `N/M`)·FY24A를 사이클 저점 참조로 함께 표시 | 메모리는 이익 변동이 배수 변동보다 크다 |
| 민감도 히트맵 | FY27E 암시 P/E를 {FY27 주당 성장} × {FY27 GM} 격자로 | 가격이 아니라 **가정이 움직이는 축** |
| 역방향 DCF | **rev-1 범위 제외.** 넣으려면 ① MU BVT 프로파일 신설(루트 `profiles/` = AI 재생성 영역, 범위 밖) ② 동일 거래일 rf·ERP 쌍의 1차 출처 확보가 선행돼야 한다 | NVDA 부록 A — ERP 4.60% `provenance=RESOLVED_JUDGMENT_ADJUSTMENT` |
| 금지 필드 | `target_price`, `fair_value_per_share`, `expected_share_price`, `probability_weighted_share_price`, `expected_value`, `scenario_weighted_central_value`, `mc_mean` — **자료구조에 존재하지 않음** | NVDA G-12a |
| 연결점 명시 | 암시 배수의 분모(이익)는 **리포트 레이어 추정**이며 Freeze A가 아니다. 가격 → 배수는 **서술 비율**이지 밸류에이션 엔진 입력이 아니다. `valuation_bridge.py`는 호출하지 않는다 | START §2 · FROZEN 말미 |

- 확률가중 EPS(Freeze A의 33.15)는 **EPS로서** 인용 가능하나, 그것에 배수를 곱한 주당값은 만들지 않는다.

### D4. 3표 깊이 — **제안: START 권고 채택 + 역사 FY23–FY26A 전체 3표**

- 역사(FY2023A–FY2026A): 손익·재무상태·현금흐름 **전체**(10-K 원본 계정). FY26A는 PR 요약 3표 → 10-K 확정 시 교체(E2-C).
- 예측(FY27E·FY28E): 손익 전체 + **핵심 항목만** — capex, D&A, FCF, 순현금, SCA 고객 예치금. generic 엔진은 B/S·C/F를 만들지 않으므로 **가정표를 공개**하고 파생 순현금은 `derived` 계보로 표기.
- 비GAAP: FQ4 브릿지는 **고정 +$0.27 가정**(FROZEN a-3) 라벨 그대로. FY27E 비GAAP은 SBC 미상 → `UNAVAILABLE_WITHOUT_ASSUMPTIONS` 로 두고 산출하지 않는 안을 제안(Q-6).

### D5. 출력 형식 — **제안: md(원본) · html · pdf × 한/영 + 데이터 xlsx 1개**

| 산출물 | 한국어 | 영어 | 비고 |
|---|---|---|---|
| md | `mu_report_fy2026q4_ko.md` | `mu_report_fy2026q4_en.md` | 생성물. 손편집 금지 |
| html | `…_ko.html` | `…_en.html` | 차트 base64 내장. 5MB 미만(`forecast.md`) |
| pdf | `…_ko.pdf` | `…_en.pdf` | 한글 폰트 임베드 · `%%EOF` + 전 페이지 렌더 확인(루트 CLAUDE.md 저장소 게이트) |
| xlsx | `mu_report_fy2026q4_data.xlsx` 1개 | (공유) | 시트명·열 머리 **한/영 병기**. 값은 한 번만 쓴다 → 패리티가 구조로 보장 |

- **단일 데이터 레이어**: `facts.py`(NVDA 선례) — 모든 수치는 fact 레코드(`fact_id, value, unit, period, basis, observed_at, information_cutoff, source_id, lineage, label{A|E|RLE|PREREG}`)로만 존재. 본문 문장은 `i18n/{ko,en}.yaml` 템플릿에 **fact_id 자리표시자**만 두고 렌더 시 채운다 → 숫자가 문자열 리터럴로 들어갈 길이 없다(G-7).
- PDF 렌더러(WeasyPrint vs headless Chrome)는 Codex 재량. 조건만 고정: 호스트에서 결정적 재생성, 브라우저 헤더/푸터 문자열 없음.

### D6. 데이터 출처·기준일

| 데이터 | 1차 출처 | 상태 (2026-09-26) |
|---|---|---|
| FY23–FY25 3표 | SEC companyfacts `CIK0000723125` (sha `a8b088c2…`, 최종 filed 2026-06-25) + 10-K htm `mu-20230831.htm`·`mu-20250828.htm` (`logs/_claude_scratch/`) | 확보. 연도 대조는 `fy` 필드가 아니라 **start/end 날짜**로(NVDA §2 규칙) |
| 분기 FY23Q1–FY26Q3 | companyfacts 3개월 기간 12개 + Q4 = FY − 9M | 확보 |
| BU 4개 | FQ3 FY26 PR(`0000723125-26-000013`) | 확보. **재편 이전 기간과 이어 붙이지 않는다**(§3 차트 ②) |
| DRAM/NAND 가격·비트 | 준비문(범위 서술 "low-60s%" 등) | 수치가 아니라 **범위 서술** → 차트 ③ 형식 제약(§3) |
| FQ4·FY26·FQ1 FY27 가이던스 | 프린트 8-K EX-99.1 + 준비문 + 10-K | **미확보 — Jiwon 다운로드 요청**(sandbox → sec.gov 불가, UA `Jiwon Sea <SEC UA 연락처>`) |
| 주가·시가총액 | 기준 거래일 1개 종가, 2경로 대조(NVDA G-3e) | **미확보.** 참고: Yahoo 캡처(2026-09-25 07:26 KST) `quote_context` = "At close 1,080.53" — 2차·페이지 문자열이므로 기준가로 쓰지 않는다. 프린트 후 거래일 종가를 Jiwon이 2경로로 캡처 |
| 컨센서스 | FQ4: `UNAVAILABLE`(FROZEN d-2) 유지 | **FY27 연간 컨센서스**는 14주 문제가 없다(분기 13주). 그래도 기간 매핑이 미검증이므로 **표시만, 판정 없음** (Q-7) |
| SCA 예치금·RPO | 10-Q/10-K 본문 수치 | companyfacts에 표준 태그 없음(확인: `CustomerDepositsNoncurrent` 부재) → 원문 좌표 인용 |

모든 수치에 `source_id` + as-of. 2차 출처는 `(2차)` 표기. 확인 못 한 것은 "없다"가 아니라 "조회 범위에서 확인하지 못했다"(NVDA 부록 B #7).

### D7. 경로·범위 — **허용 경로 목록 (이 밖을 건드려야 하면 즉시 중단·보고)**

**신규 생성 허용**

| 경로 | 주체 | 용도 |
|---|---|---|
| `forecast/PLAN_mu_report_fy2026q4.md` (+ 개정 시 `_revN_superseded.md`) | Claude | 본 계획 |
| `forecast/REVIEW_CODEX_mu_report_plan_rN.md` | Codex | P2 |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | Claude | E1 |
| `forecast/REVIEW_CLAUDE_mu_report_output_rN.md` | Claude | E3 |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | Codex | 리포트 레이어 가정 (Q-4) |
| `forecast/scripts/mu_report/` (`facts.py`·`build.py`·`charts.py`·`gates.py`·`i18n/{ko,en}.yaml`·`sources/`) | Codex | 빌드. 선례 `forecast/scripts/t3/` (추적) |
| `forecast/scripts/mu_report/sources/*.json` | Codex | `logs/` 원본에서 뽑은 **추출본**만(원본 sha 기록). `logs/` 자체는 커밋 금지 |
| `forecast/reports/mu_report_fy2026q4_{ko,en}.{md,html,pdf}` · `mu_report_fy2026q4_data.xlsx` · `forecast/reports/mu_report_fy2026q4_assets/*.png` | Codex | 산출물. 이름이 `*_FROZEN.md`·`*_SCORED.md` 패턴과 겹치지 않음 → FROZEN 게이트·allowlist 스캔 무관 |
| `forecast/tests/test_mu_report.py` | Codex | 신규 테스트(기존 테스트 수정 아님) |

**읽기 전용**: `forecast/reports/mu_fy2026q4_forecast_FROZEN.md` · `forecast/profiles/mu.generic.yaml` · `forecast/engine/**` · `forecast/pipeline/**`(특히 `edgar_fetcher.model_label_for_period` — NOTICED BUT NOT TOUCHING) · `mu_fy2026q4_SCORED.md`(생기면) · `logs/**` · `valuation-results/**` · 루트 `engine/`·`profiles/`.

**블록 상한·시간 예산(제안)**: E2-A ≤ 2 세션 / E2-B ≤ 2 세션 / E3 리뷰 루프 ≤ 3 라운드. 초과 시 Jiwon에게 범위 축소안(영어판 PDF 생략 등)을 먼저 올린다.

### D8. 시각 정체성 — **제안: 발행사 로고·브랜드 팔레트 미사용, 중립 팔레트**

- 선례 둘은 발행사 로고를 썼다. MU 리포트는 (i) 리포가 public이라 공개 배포물이 되고 (ii) 발행사가 작성·승인한 자료로 오인될 여지를 줄이기 위해 로고를 쓰지 않는다. 표지에 NVDA 선례 문구 상속: *"공개 자료 기반 제3자 분석이며 Micron 및 계열사가 작성·검토·승인한 자료가 아니다."*
- 증권사 형식(표지 요약·핵심 수치표·목차)은 **구성만** 차용. 특정 증권사·은행의 레이아웃·면책 문구·애널리스트명은 쓰지 않는다(START §2).

### D9. 작성자 표기·면책 — **제안: 작성자 "김지원" + 두 언어 면책 고정 문안**

- 면책 문장은 i18n 템플릿의 **고정 키 2개**(`disclaimer.not_advice`, `disclaimer.third_party`)로 두고 G-12b가 두 판 모두에서 존재를 검사한다. 모든 표지·말미·PDF 각 페이지 푸터에 1회 이상.

---

## §3. 보고서 구성 (NVDA 08-26 목차를 기반으로 MU에 맞춤)

| § | 절 | 핵심 내용 | 그림 |
|---|---|---|---|
| 표지 | 한 페이지 요약 | 3줄 핵심 판단(판정 아닌 **관찰**) · 핵심 수치표(매출·GAAP/비GAAP EPS·GM·OPM — FQ4A, FY26A, FY27E, FY28E) · as-of · 정보 컷오프 · 결론별 데이터 충족도(NVDA §4-4) · 면책 | — |
| 1 | 회사 개요와 읽는 규칙 | 4개 BU · **회계연도↔캘린더 매핑 표**(FY/FQ + 달력 병기) · 52/53주 규칙 · A/E/RLE/PREREG 라벨 범례 | ② |
| 2 | 투자 논점 — 강세 vs 약세 | 양쪽 논거를 **같은 형식으로 나란히**. 각 논거에 반증 관측원 1개 | — |
| 3 | FQ4 FY26 — 사전등록 대 실적 | Freeze A bear/base/bull·확률가중(원값) · 가이던스 대비 라벨 · **채점 결과는 SCORED 인용만** · 헤드라인/주당 성장 병기 · 컨센서스 `UNAVAILABLE` | ④ ⑤ |
| 4 | FY27 전망 | FQ1 가이던스(주당 정규화 $g$) · 가격 사이클 판정 · SCA(천장 = CQ2 시장가, 매출 약 40%) 함의 | ⑤ |
| 5 | 사업 구조 | BU 추이(재편 이후 기간만) · DRAM/NAND 매출 · 가격·비트(범위 서술) · **HBM 분기 매출 `NOT_DISCLOSED`** | ② ③ |
| 6 | 재무제표 | FY23A–FY26A 3표 전체 + FY27E–FY28E 손익·핵심항목 · 비율(GM, OPM, ETR, ROE, 순현금, capex/매출, FCF) | ① ⑥ ⑧ |
| 7 | 마진 브리지 | 매출 → GM → opex → OP → below-OP → 세금 → NI, GAAP↔비GAAP 브리지 | — |
| 8 | 시나리오 | bear/base/bull 가정표 · 민감도(매출 1% · GM 1pt · 세율 1pt · 주식수 10M) — FQ4는 FROZEN (f-2) 인용, FY27E는 리포트 레이어 재산출 | — |
| 9 | 밸류에이션 | 암시 배수 표 · 사이클 경고 · 민감도 히트맵 · **연결점·가정·출처 명시** · 목표주가를 내지 않는 이유(NVDA §6-0 상속) | ⑦ |
| 10 | 리스크·스윙 팩터 | FROZEN §(f) 요약 — **SF 번호가 아니라 대상명**으로 인용 | — |
| 11 | 촉매·일정 | 10-K 접수 · 2026-12-09 CHIPS 2주년 후 자본환원 확대 · 리드스루(SK하이닉스 ~10/27, SNDK FQ1 FY27 ~11월 초) — 날짜는 전부 `ESTIMATED`/`CONFIRMED` 상태 표기 | — |
| 12 | 부록 | 방법론(generic top-down, in-sample 백테스트 한계, 주수 규약) · 출처 원장(accession·sha·as-of) · 정직성 라벨 · 게이트 결과표 · 스스로 건 제약 표(NVDA 부록 B 형식) · 면책 | — |

**차트 8종 (전부 facts 원장에서 생성, 캡션 = 번호·단위·출처·기준일·회계기준 — G-16)**

| # | 차트 | 데이터 | 형식 제약 |
|---|---|---|---|
| ① | 분기 매출·GM·OPM FY23Q1–FY26Q4 | companyfacts + PR | FQ4 FY26은 14주 — 막대에 주수 표기, 주당 환산 보조선 |
| ② | BU 믹스 누적 막대 | PR BU 표 | **현 4-BU 체계 공시 기간만.** 구 체계와 잇지 않는다. 재편 시점·재작성 범위는 E2-A에서 원문 확인(Q-8) |
| ③ | DRAM/NAND 가격·비트 변화 | 준비문 | 회사는 **범위 서술**만 준다 → 숫자 막대가 아니라 **범위 띠(예: 60–64%)** 로 그리고 "발행사 서술 범위" 라벨. 범위로도 못 그리면 표로 강등 |
| ④ | 가이던스 대비 실적 이력 | FROZEN (d-1) 10분기 + FQ4 실적 | FQ4 점은 SCORED 값 인용 |
| ⑤ | 시나리오 fan (FQ4 FY26 – FQ4 FY27) | Freeze A(FQ4) + RLE(FY27) | **두 레이어의 선 스타일·범례를 분리**(PREREG vs RLE) |
| ⑥ | 연간 손익 막대 FY23A–FY28E | 3표 + RLE | A/E 구분(채움 vs 빗금), FY26 53주 각주 |
| ⑦ | 밸류에이션 민감도 히트맵 | RLE 격자 | 셀 = 암시 P/E. 가격 1개 고정 |
| ⑧ | FCF·capex·순현금 | 3표 + RLE 핵심항목 | 순현금 정의(현금+단기·장기 시장성 투자 − 총차입) 캡션에 명시 |

---

## §4. 데이터 계약

### 4-1. 라벨 4종 (표·차트·xlsx 공통, 누락 시 G-9 실패)

| 라벨 | 의미 | 예 |
|---|---|---|
| `A` | 실적 (PR 잠정은 `A-8K`, 10-K 확정은 `A-10K`) | FY25A, FY26A-8K |
| `PREREG_A` | Freeze A 원값(표시 반올림만) | FQ4 base 매출 52,860 |
| `RLE` | 리포트 레이어 추정 (Freeze A와 분리) | FY27E base |
| `CITED` | 외부 인용(가이던스·컨센서스·주가) | FQ1 FY27 가이던스 |

### 4-2. 반올림 규칙 (G-2 판정 기준)

- $M 정수, EPS 소수 2자리, 비율 소수 1자리(% 표시). 원 fact 값은 원장에 전정밀도로 보존하고 **표시만** 반올림한다.
- Freeze A 대조는 **표시값 == FROZEN 본문 표시값**(문자열 일치)으로 한다. 재계산 후 비교하지 않는다.

### 4-3. 채점과의 경계

- 리포트는 **채점하지 않는다.** HIT/MISS·라벨·RC 판정·귀인은 `mu_fy2026q4_SCORED.md`에서 **fact 단위로 인용**하고 `source_id = SCORED@<commit>`. 채점 문서의 값과 리포트 값이 다르면 G-3f 실패.

---

## §5. 검증 게이트 (E2 생성 전·후, E3 재현)

START §5 게이트 7종을 NVDA 08-26 G-계열과 합쳐 번호를 고정한다. **각 게이트는 일부러 위반을 주입해 실패하는지도 시험한다**(NVDA §13-3 — 거짓 PASS 2건을 이 방식으로 잡았다).

| 게이트 | 검사 | 실패 시 |
|---|---|---|
| G-1 입력 핀 | FROZEN `eab1184f…629f9a` · 프로파일 `faa60912…dfd6` · companyfacts `a8b088c2…` · SCORED · 8-K/10-K/준비문·가격 캡처 sha256 대조 | 생성 중단 |
| G-2 Freeze A 대조 | 리포트의 PREREG_A 표시값 == FROZEN 표시값(§4-2). FROZEN·프로파일 sha 불변 | 중단 |
| G-3 역사 항등식 | 매출−원가=GM · GM−opex=OP · OP+below-OP=세전 · 세전−세금(+지분법)=NI · NI÷희석주식≈EPS(±$0.01) · Σ분기=연간(Q4=FY−9M) — **fail closed** | 중단 |
| G-3b B/S 항등식 | 자산 = 부채 + 자본 (3개년) | 중단 |
| G-3c C/F 항등식 | 영업+투자+재무(+환율) = 현금 증감 | 중단 |
| G-3e 가격 2경로 | 기준가 두 경로 값 일치 | 중단 |
| G-3f SCORED 대조 | 인용한 채점 값 == SCORED 원문 | 중단 |
| G-7 하드코딩 | 빌드 스크립트·i18n 템플릿의 숫자 리터럴 전수 추출, 사유 등재분만 허용 | 중단 |
| G-9 컷오프 위생 | ① PREREG_A 표에 프린트 후 값 없음 ② RLE가 PREREG_A를 입력으로 쓰지 않음(FQ4 실적 seed만) ③ 혼합 표에 라벨 열 존재 | 중단 |
| G-12a 구조적 금지 | D3 금지 필드가 원장 스키마에 없음 | 중단 |
| G-12b 금지어·면책 | 투자의견·목표주가 문구 스캔(보조) + 면책 2문장 두 판 모두 존재 | 중단 |
| G-13 시각 요소 | 차트 8종 존재, 각 1회 이상 참조 | 중단 |
| G-14 출처 추적 | 표의 모든 `source_id`가 URL·accession·sha로 해석 | 중단 |
| G-15 한/영 패리티 | 두 md에서 숫자 토큰을 추출해 **다중집합 일치**(표·본문·캡션). 추가로 fact_id 참조 집합 일치 | 중단 |
| G-16 캡션 | 번호·단위·출처·기준일·회계기준 5요소 | 중단 |
| G-17 라벨 | FY/FQ + 달력 병기, 주수 각주, A/PREREG_A/RLE/CITED, 컨센서스 `UNAVAILABLE` | 중단 |
| G-18 파일 위생 | LF · NUL 0 · 행말 공백 0 · UTF-8 유효 · html < 5MB · pdf `%%EOF` + 전 페이지 렌더 | 중단 |
| 기존 게이트 | `python -m pytest forecast/tests/ -q` green · FROZEN 게이트 `checked == passed == 5`, `supported_skipped == 0`, `failures == []` · `python forecast/scripts/verify_anchor.py` PASS · `test_valuation_allowlist.py` PASS | 커밋 불가 |

- 🔴 Codex 실패 패턴 1·5 방어: E3에서 Claude가 NUL 스캔·pytest·sha를 **독립 재실행**한다. 보고서의 "PASS" 기재는 증거로 취급하지 않는다.
- 회귀표(패턴 4 방어)는 **빈칸 없는 표**로 요구: 게이트별 {정상 PASS, 위반 주입 FAIL} 2열.

---

## §6. 워크플로 · 파일 · 종료 조건

| 단계 | 주체 | 산출 | 종료 조건 |
|---|---|---|---|
| P0 | Claude | 부록 A | ✅ 완료 (본 문서) |
| P1 | Claude | 본 PLAN rev-1 | ✅ 작성 |
| P2 | Codex | `REVIEW_CODEX_mu_report_plan_r1.md` | Q-1~Q-12 **번호 순 전건** PASS / CHANGES REQUESTED |
| P3 | Jiwon | — | D1–D9 확정 (특히 D1 FY26A 라벨, D7 경로, D8) |
| E1 | Claude | `HANDOFF_CODEX_mu_report_exec.md` | 확정 계획 → 실행 지시(정책 확정본 선행 — 교차검토 규칙) |
| E2-A/B/C | Codex | §D7 허용 경로 | §5 전 게이트 |
| E3 | Claude | `REVIEW_CLAUDE_mu_report_output_rN.md` | 수치 대조·패리티·차트·서술 정확성 독립 재현 |
| E4 | Jiwon | 호스트 PowerShell 커밋 | 파일 목록·sha 확인 후. **푸시는 별도 결정 — 리포 public** |

**Jiwon 요청 목록 (환경 제약 — sandbox는 sec.gov·시세 사이트 불가)**

1. 프린트 직후: FQ4 FY26 8-K 및 EX-99.1, 준비문 PDF (UA `Jiwon Sea <SEC UA 연락처>`) → `logs/mu_postprint_*` 저장 + sha
2. 기준 거래일 종가 캡처 2경로(예: 거래소 계열 시세 + 다른 집계원) — 날짜·시각 포함
3. 10-K 접수 시 원본 htm
4. (선택) FY27 연간 컨센서스 캡처 — 표시 전용

---

## §7. 스코프 잠금

- 금지: FROZEN·MU 프로파일·엔진·빌더 수정 · 표기 없는 밸류에이션 배선 · `valuation_bridge.py` 호출 · 경쟁사 병렬 모델링 · 투자의견·목표주가 · BU/HBM 수요 모델 신설 · 채점 재계산.
- 허용 경로 밖 변경이 필요해지면 **즉시 중단·보고**. 기존 테스트 변경은 사유·diff 보고 후 승인.
- git: VM에서는 `GIT_OPTIONAL_LOCKS=0` / `--no-optional-locks` 읽기만. add/commit은 호스트, Jiwon 승인 후.

---

## §8. 알려진 한계 (본문 부록에 그대로 옮긴다)

1. 백테스트는 **in-sample**이며 스킬 근거가 아니다(FROZEN SF8 `NO_OOS_SKILL_EVIDENCE`).
2. 비GAAP FQ4 EPS는 **고정 +$0.27 브릿지 가정**이다. FQ3 실제 갭은 0.44였다.
3. FY27E·FY28E는 리포트 레이어 추정이며 확신도 하. 사이클 레벨 피크아웃은 bear로만 표현된다.
4. HBM 분기 매출은 공시되지 않는다 — 분해하지 않는다.
5. DRAM/NAND 가격·비트는 발행사 **범위 서술**이며 시장 계약가가 아니다.
6. 암시 배수는 **피크 부근 이익**을 분모로 쓴다. 저점 참조(FY23A·FY24A)를 함께 보지 않으면 오독된다.
7. 컨센서스 FQ4 비교는 `UNAVAILABLE`, FY27 컨센서스는 표시 전용.

---

## §9. Codex 판정 요청 (번호 순 전건)

| # | 질문 | Claude 제안 |
|---|---|---|
| Q-1 | D1: ⓐ 불채택·ⓑ 단독·프린트 전 인프라 선행이 타당한가. 프린트 전 블록 E2-A에서 "프린트 정보 사용 금지"를 G-9로 기계 검사하는 것으로 충분한가 | 예 |
| Q-2 | ⓑ에서 연간 표를 FY23A–FY26A(잠정) + FY27E·FY28E로 바꾸는 것이 START §3 "FY23A–FY25A + FY26E–FY28E"의 취지에 맞는가 | 예 — FY26은 프린트 후 실적 |
| Q-3 | FY27 경로에서 Freeze A 프로파일 FY27 Q1–Q3 경로를 버리고 FQ1 가이던스 앵커 RLE로 대체하는 것, 차이를 부록 1표로만 병기하는 것 | 예 |
| Q-4 | 리포트 레이어 YAML 위치 `forecast/inputs/` vs `forecast/profiles/` (`forecast.md` 문구와 충돌 여부) | `inputs/` |
| Q-5 | RLE 계산 경로: `run_generic_forecast` 메모리 내 호출(엔진 무수정) 1순위, 불가 시 리포트 산술 강등 | 예 |
| Q-6 | FY27E 비GAAP EPS를 `UNAVAILABLE_WITHOUT_ASSUMPTIONS`로 두는 것 vs +$0.27 연장 가정 | 미산출 |
| Q-7 | FY27 연간 컨센서스: 14주 문제가 없으므로 비교 허용 여부. 기간 매핑 미검증을 이유로 표시 전용 유지 | 표시 전용 |
| Q-8 | 차트 ②(BU)·③(가격 범위 띠)의 형식 제약이 충분한가 — 특히 ③을 표로 강등할 기준 | 범위 띠, 불가 시 표 |
| Q-9 | 개행: `forecast/**` 신규 파일 LF (루트 CLAUDE.md의 CRLF 문구와의 관계) | LF |
| Q-10 | D3: 역방향 DCF 제외, 암시 배수 + 히트맵 + 금지 필드 구조 | 예 |
| Q-11 | D7: 산출물을 `forecast/reports/` 에 두는 것이 FROZEN 게이트·allowlist 스캔·`forecast.md` 규약과 충돌하지 않는지. PDF·xlsx 바이너리 커밋 허용 여부 | 충돌 없음(파일명 패턴 확인) · 바이너리는 Jiwon 판단 |
| Q-12 | G-15 패리티(숫자 토큰 다중집합 + fact_id 집합)가 한/영 수치 불일치를 잡기에 충분한가. 반례(단위 표기 차이: "조"/"B", 천 단위 구분자) 처리 규칙 | USD $M 단일 단위 · 구분자 정규화 후 비교 |

---

## 부록 A. P0 선례 인벤토리 (2026-09-26, 원본 직접 열람)

| 파일 | 구성요소 | 형식 | 차트 | 재사용 가능 스크립트 | 판정 |
|---|---|---|---|---|---|
| `valuation-results/2026-08-26-nvda-q2-preview/NVIDIA_기업분석보고서_2026-08-26_김지원.md` (952행) | 표지 메타표 · 목차 · §0 한 페이지 결론(결론별 데이터 충족도) · §1 회계연도↔캘린더 매핑 · §2 3개년 3표 + SBC·자사주·운전자본 · §3 27분기 추이 · §4 컨센서스 해부(가이던스 대비 8분기) · §5 사전등록 판정 · §6 역산(목표주가 미산출 사유) · §7 분포 · §8 이익의 질 · §9 리스크 · §10–11 체크리스트 · §13 사실 원장·게이트·계산규칙 · 부록 A ERP · 부록 B 자기 제약 13개 | md → html → pdf, 한국어 단일판 | 17종, 캡션 5요소 | `scripts/facts.py`(단일 원장·핀·금지필드) · `gate_report.py` · `charts.py` · `build_report.py` · `build_pdf.py` · `build_xlsx.py` · `seal.py` | **1순위 형식 선례.** 구조 상속, 발행사 로고 제외 |
| 同 `PLAN_nvda_report_2026-08-26.md` (rev-3, 596행) | 정정 이력 표 · 산출물 규격 · 입력 핀(리포 한정 경로) · fact 스키마 · G-9 실패조건 · 목차 · 데이터 원장·충족도 · 채점 규칙 · 밸류에이션 축 · 차트 명세 · 게이트 · 한계 · 재검증 요청 | md | — | — | 계획 문서 형식 선례 |
| 同 `NVIDIA_재무데이터_3개년_2026-08-26.xlsx` | 3개년 데이터 | xlsx | — | `build_xlsx.py` | 데이터 워크북 선례 |
| `valuation-results/2026-08-07-hynix-q2-update/SK하이닉스_기업분석보고서_2026-08-07.md` (552행) + pdf(19p, WeasyPrint) + 데이터 xlsx(8시트) | 투자 요약 · 이전판 브릿지 · 실적 · NI 브리지 · 미확정 항목 표 · 사업 동향 · 정상화 밸류에이션 · 민감도 · 역방향 진단 · 컨센서스 대조 · 테제 판정 · 리스크 트리거 · EFE 사후채점 · 부록(출처 등급·재현·면책) | md → html → pdf | 6종 | `build_pdf.py`·`charts.py`·`facts.py`·`mkxlsx.py` | 서술 흐름 참고. **확률가중 내재가치 표시는 NVDA 08-26 G-12a로 대체됨 — 상속하지 않음** |
| `forecast/reports/sk_hynix_20260913.{md,html,pdf,xlsx}` · `_fan.png` · `_beat_miss.png` | 헤드라인 지표 · 데이터 경고 · 컨센 gap · below-OP 밴드 · 오버레이 · 이벤트 EPS · 밸류 브리지 · 백테스트 · 가정 | `forecast/cli.py` 자동 산출 | fan · beat/miss | `forecast/output/{md_builder,html_builder,plotly_charts,static_charts}.py` | 셀사이드 형식 아님(§1 P0-1). 차트 개념만 참고 |
| `forecast/reports/sk_hynix_call_brief_2026060{4,5}.md` | 토픽 salience 표 · 예상 Q&A | 자동 산출 md | — | — | FROZEN §(e) Q&A로 대체 |
| `forecast/reports/sk_hynix_q2_2026_scorecard.md` (288행) | 사후 채점 형식 | md | — | `score_sk_hynix_q2_2026.py` | 채점 선례(본 리포트 범위 밖) |
| `forecast/START-skhynix-report-2026q2.md` (102행) | 확정 사실 · 급소(비반복 이익 제거·미확정 항목·자체 모델 인용 구분) · 모델 성적 정직 기술 · 논점 · 규율 | md | — | — | 규율 상속(미확정은 미확정으로) |
| `forecast/HANDOFF_CODEX_hynix_q2_2026_report_2026-08-07.md` (442행) | 사실 오류 3건 정정 · 정상화 방법론 · 항등식 검산표 · 교차검증 판정표 | md | — | — | "두 계산 경로 섞임" 교훈 → G-15·Q-5 |
| `forecast/reports/T4_verdict_draft_nvda_2026-08-13.md` (rev-4) | 입력 고정 · 판정 프레임(새 공정가치 미산출) · 반증조건 · 채점 훅 | md | — | `scripts/t3/gen_t4.py` | 판정 문장 규율 |
| `forecast/reports/T3_nvda_2026-08-10.md` (rev-7) | 조건부 역산(단일축) · UNREACHABLE 경계 · 허용오차 | md | — | `scripts/t3/{bvt_dcf,t3_reverse_dcf}.py` | D3에서 역방향 DCF 제외 근거 |
| `forecast/reports/V2_rf_overlay_nvda_2026-08-10.md` | rf 기준일·출처 확정, ERP 미해소 | md | — | `gen_v2.py` | ERP 문제 근거 |
| `forecast/reports/T1_vendor_financing_nvda_2026-08-10.md` · `T2_buckets_1_3_nvda_2026-08-13.md` | 테마 심층·below-OP 버킷, 오염 방지 선언 | md | — | `gen_t1.py`·`gen_t2.py` | 오염 방지 선언 형식 상속 |
| `forecast/reports/FREEZE_A_verification_nvda_2026-08-14.md` · `MANIFEST_nvda_2026-08-09.md` | 해시 고정·결정성 재현 3회·fail-closed | md | — | `gen_manifest*.py` | G-1 형식 |
| `forecast/PLAN_nvda_2026-08_deep_dive.md` (rev-3, 352행) · `HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev7.md` | 트랙 분리·사전등록 실패조건 · "모든 수치 블록 스크립트 생성" | md | — | `gen_handoff.py` | 핸드오프 수치도 스크립트 생성(E1에 적용) |
| `forecast/PLAN_valuation_bridge.md` · `engine/valuation_bridge.py` · `tests/test_valuation_allowlist.py` | 2층 분리 · 컨센 신뢰도 가드 · `valuation:` 보유 = `{sk_hynix.yaml}` 정확 일치 · FROZEN 대응 프로파일 보유 금지 · 스캔 = `forecast/profiles/` + `forecast/reports/*_FROZEN.md` | py/md | — | — | 브리지 미사용(P0-6), YAML은 `inputs/`(Q-4) |

**MU 입력 (읽기 전용, 열람 확인)**: `mu_fy2026q4_forecast_FROZEN.md`(sha `eab1184f…629f9a` 재계산 일치) · `mu.generic.yaml`(sha `faa60912…dfd6` 재계산 일치) · `PANEL_…_G0H_2026-09-25.md` · `PREREG_…_G0H_2026-09-16.md`(rev-16) · `SOURCE_LEDGER_…_2026-09-15.md`(rev-2) · `CONSENSUS_…_FY26Q4_2026-09-25.md`(rev-1) · `PLAN_efe_2026sep_mu.md`(rev-7) · `START-efe-sep2026-mu.md`(rev-7) · `logs/mu_ho5_*`(manifest 포함 24개) · `logs/_claude_scratch/`(10-K htm 2개 — FY2023·FY2025, 과거 EX-99.1 **10개** — START는 "11개"로 기재, 1개 차이는 E2-A에서 manifest로 확인, Yahoo 캡처) · companyfacts 캐시(sha `a8b088c2…` 재계산 일치; FY23–FY25 10-K 연간 계정·3개월 기간 12개 확인).

**데이터 가용성 점검(표시용, 원장 아님)**: companyfacts 10-K 연간 — 매출 FY23 15,540 / FY24 25,111 / FY25 37,378 ($M); 매출총이익 FY23 −1,416(음수) → FY23 P/E `N/M` 처리 필요.

---

*본 문서는 투자 자문이 아니다.*
