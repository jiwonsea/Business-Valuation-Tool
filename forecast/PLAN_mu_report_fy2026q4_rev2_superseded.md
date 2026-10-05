# PLAN — Micron (MU) 리서치 리포트 · FY2026 Q4 기준 · 한/영 2판 **rev-2**

> 작성 2026-09-27 KST · 작성 Claude · 검토 Codex (P2 재검토) · 승인 Jiwon (P3)
> 근거: START "MU research report (based on FY2026 Q4)" 2026-09-25 · 선행 배치 MU Freeze A (`f8cfd47`, FROZEN sha256 `eab1184f…629f9a`, frozen_at 2026-09-25 08:54:41 KST)
> 직전 판: rev-1 → `forecast/PLAN_mu_report_fy2026q4_rev1_superseded.md` (sha256 `d4d41b9a…74fb0`) · 판정서 `forecast/REVIEW_CODEX_mu_report_plan_r1.md` (sha256 `f42c7fda…cbaf3`, CHANGES REQUESTED)
> 🔴 **투자 자문 아님.** 본 계획과 모든 산출물(한국어판·영어판)은 투자 자문이 아니며 특정 증권의 매매를 권유하지 않는다.
> 🔴 **코드·리포트·가정 YAML 미착수.** rev-2는 계획 문서 1개 개정 + rev-1 보존 사본 1개만 만든다.

---

## §-1. 리비전 이력

| rev | 일자 | 판정 | 내용 |
|---|---|---|---|
| rev-1 | 2026-09-26 | CHANGES REQUESTED (r1) | 최초 작성. P0 인벤토리 · D1–D9 · 게이트 G-1~G-18 |
| **rev-2** | **2026-09-27** | (Codex 재검토 대기) | r1의 Q-1~Q-12 · R-1~R-10 전건 반영. 신설: §4-1 FY26 4-레이어 · §4-3 3표 행·식·가용성 계약 · §4-4 행별 계산 경로 · §4-5 밸류에이션 정의 · §4-6 canonical manifest · §5 게이트 G-3 허용오차 · G-13b · G-14 확장 · G-19 브릿지 범위 · G-20 입력 provenance · G-21 형식별 QA · 부록 A 파일별 인벤토리 |

---

## §R. r1 판정 회신 — 번호 순 전건

### R-a. Q-1 ~ Q-12

| # | r1 판정 | rev-2 조치 | 반영 위치 |
|---|---|---|---|
| Q-1 | CHANGES REQUESTED | E2-A 시작 조건을 **P3 승인 + E1 핸드오프 완료**로 고정. 프린트 전 **허용 입력 allowlist(경로+SHA)** 와 **금지 입력 목록**을 고정하고, 모든 입력을 단일 함수 `read_input()`로만 읽어 접근 로그를 남기며 G-20이 로그를 검사한다. post-print 슬롯은 E2-A에서 **테스트 fixture만** 사용 | §2 D1 · §4-7 · §5 G-20 |
| Q-2 | CHANGES REQUESTED | FY26은 **4개 레이어**로 분리: `FY26E-PREREG_A` · `FY26A-8K` · `FY26A-10K` · (FY27/28은 RLE). FY23A–FY25A 3개 역사연도 유지. FY26E를 소거하지 않고 주표 옆 열 + 브리지 표로 보존. 판 번호 규칙 명시(10-K 반영 = 제2판, 별도 파일) | §4-1 |
| Q-3 | PASS | 유지. 부록 비교표: FY27 Q1–Q3 {Freeze A 프로파일 경로 vs RLE} × {매출·OPM·GAAP EPS} + 정보 컷오프 2개 명시. Freeze A 프로파일 경로는 **RLE 입력으로 쓰지 않는다** | §4-4 · §3 부록 |
| Q-4 | PASS | 유지. YAML 머리 필수 키 `scope: report_layer` · `information_cutoff` · `sources` · `units` · `week_basis` · `confidence` · `input_sha256` 추가 | §2 D2 · §4-7 |
| Q-5 | CHANGES REQUESTED | "불가 시 강등" 삭제. **경로 확정**: FY27 분기 매출·OP·NI·EPS = 메모리 내 `GenericProfile` → `run_generic_forecast()`. GM·opex 브리지, FY28, capex·D&A·SBC·OCF·FCF·순현금 = 리포트 레이어 **명시적 순수식**. 행별 식·입력 fact·검증 항등식 표 | §4-4 |
| Q-6 | PASS | 유지. 표지 핵심 수치표의 FY27E·FY28E 비GAAP 칸 = `UNAVAILABLE_WITHOUT_ASSUMPTIONS` | §3 표지 · §4-3 |
| Q-7 | PASS | 유지. FY27 컨센서스 = `UNAVAILABLE_FOR_COMPARISON`. gap·beat/miss·색상·방향 문장 금지(G-17b) | §2 D6 · §5 |
| Q-8 | CHANGES REQUESTED | BU: **동일 4-BU 정의 비교 가능 기간 ≥ 2**일 때만 "추이", 1개면 "단일 기간 믹스". 실측: 재편 후 보도자료 4건에 FQ4-24~FQ3-26 **8개 분기**가 존재 → 추이 허용. DRAM/NAND: 원문이 숫자를 준 **매출·QoQ%만 차트**, `low-60s` 등 언어적 구간은 **범주형 표**로만(숫자화 금지). 대체 차트 ③′ 고정 | §3 차트 · §4-8 |
| Q-9 | PASS | 유지. 신규 `forecast/**` 텍스트 = LF, 기존 파일 개행 불변 | §5 G-18 |
| Q-10 | CHANGES REQUESTED | 기준가(거래일·통화·분할 기준)·주식수·시가총액·EV 구성(현금·시장성투자·총차입·SCA 예치금)·EBITDA·FCF·분모 basis·배수별 식·`N/M` 조건·히트맵 계산 경로를 고정 | §4-5 |
| Q-11 | CHANGES REQUESTED | 바이너리 "Jiwon 판단" 삭제. **E4 커밋 후보에 KO/EN PDF · 공유 XLSX · 차트 PNG 원본을 명시**. HTML base64 내장 여부와 무관하게 PNG 원본 유지. add/commit은 Jiwon 승인 후 호스트에서만 | §2 D7 · §6 |
| Q-12 | CHANGES REQUESTED | 패리티를 **canonical manifest**(`fact_id → raw_value · display_value{ko,en} · unit · period · basis · label · source_id · lineage`) 참조 비교로 교체. 표 셀·본문 placeholder·차트 series 모두 manifest 참조. 숫자 토큰 검사는 **보조 게이트**. 의도된 차이는 명시 allowlist | §4-6 · §5 G-15 |

### R-b. R-1 ~ R-10

| # | 요구 | rev-2 반영 |
|---|---|---|
| R-1 | P0 인벤토리 파일별 완결 | **부록 A 전면 재작성**: 지정 파일 30개를 파일별 1행(바이트·SHA 앞 12자리·구성 요소·재사용 판정). `valuation-results/`는 부록 A-2 **보조 선례**로 분리. SK XLSX = 3시트 얕은 자동 산출물 명시 |
| R-2 | 프린트·SCORED를 입력 게이트로 | §1 상태 갱신(2026-09-27 10:00 KST 프린트 전, SCORED 부재). E2-B 시작 조건 4개 고정 → §6 |
| R-3 | FY26 표시 구조 | §4-1 4-레이어, 연간 차트 FY26 이중 표시(브리지 inset), 53주 각주 양쪽 |
| R-4 | 3표 행·식·가용성 계약 | §4-3 (행 목록·레이어별 가용성·순현금 roll-forward·ROE 정의) |
| R-5 | 역사 항등식 허용오차 | §5 G-3 허용오차 식. 플러그 금지 |
| R-6 | 차트-표 동일성 | §5 **G-13b** 신설 |
| R-7 | 출처 범위를 본문 숫자까지 | §5 **G-14** 확장(표·본문·캡션·각주·표지·일정 날짜, 계산값 lineage) |
| R-8 | +$0.27 적용 범위 스키마 차단 | §4-6 fact 제약 + §5 **G-19** |
| R-9 | 형식별 QA | §5 **G-21** (PDF·XLSX·HTML·MD). SK 2026-09-13 PDF의 브라우저 날짜·`file:///` 잔존 재발 방지 항목화 |
| R-10 | 프리프린트 작업과 공개 행위 분리 | §6: E2-A = 로컬 생성까지. add/commit/push 없음. E4 승인 파일 목록·SHA 확인 후에만 커밋 후보. push 별도 승인 |

---

## §0. 요지

1. **발행 형태**: 프린트 후 `Review & Outlook` 1판(D1 ⓑ). 프린트 전에는 **프린트 정보를 쓰지 않는 인프라**만 만든다 — 단 **P3 승인과 E1 핸드오프 이후에만**(Q-1).
2. **FY26은 네 가지 값이 공존한다** — Freeze A 추정, 8-K 잠정, 10-K 확정, 그리고 FY27·FY28의 리포트 레이어 추정. 한 열 이름으로 합치지 않는다(§4-1).
3. **모든 수치는 manifest의 fact 하나에서 나온다.** 표·본문·차트·두 언어판이 같은 fact_id를 참조하고, 게이트가 그 참조를 비교한다(§4-6).
4. **밸류에이션은 암시 배수 + 민감도**, 목표주가·투자의견 없음. 배수별 식과 `N/M` 조건을 고정했다(§4-5).
5. **Freeze A는 한 자리도 바꾸지 않는다.** +$0.27 비GAAP 브릿지는 `FY2026Q4`에만 존재하도록 스키마로 막는다(§4-6, G-19).

---

## §1. 상태와 P0 결과

### 1-0. 현재 상태 (2026-09-27 10:00 KST 확인)

| 항목 | 상태 | 근거 |
|---|---|---|
| FQ4 FY26 프린트 | **미발생.** 콜 2026-09-30 14:30 MT(= 10-01 05:30 KST) 확정, PR 16:01 ET(= 10-01 05:01 KST) 추정 | 발행사 공지(2026-08-26), FROZEN 헤더 |
| `forecast/reports/mu_fy2026q4_SCORED.md` | **부재** | `forecast/reports/` 나열 |
| 기준 주가 캡처 | 부재 | — |
| P3 승인 · E1 핸드오프 | 미완료 | — |

→ 날짜가 아니라 **§6 입력 게이트**로 다음 단계 진입을 판정한다.

### 1-1. P0에서 START 전제와 다른 점 (rev-1 유지 + 정정 1건)

| # | 사실 | 영향 |
|---|---|---|
| P0-1 | `forecast/reports/sk_hynix_20260913.*`은 `forecast/cli.py` 자동 산출물이다. XLSX는 `forecast`·`scenarios`·`backtest` **3시트, 수식 0**, PDF 7쪽은 Chrome 인쇄(1쪽 머리 `26. 9. 13. 오전 3:56`, `file:///` 잔존) | 형식 모델로 쓰지 않음. 차트 개념 2종(fan·beat/miss)만 참고. PDF 결함은 G-21 재발 방지 항목 |
| P0-2 | 셀사이드 형식의 최신 완성본은 `valuation-results/2026-08-26-nvda-q2-preview/`(NVDA, PDF 33쪽 WeasyPrint, 3개년 XLSX 4시트)와 `…/2026-08-07-hynix-q2-update/`(PDF 19쪽, XLSX 8시트)다 | **보조 선례**(부록 A-2). 지정 추적 파일 인벤토리(부록 A-1)를 대체하지 않는다 |
| P0-3 | `valuation-results/`는 gitignore, 추적 0 | 산출 위치 = `forecast/` 하위 추적 경로(D7) |
| P0-4 | 선례는 한국어 단일판 | 한/영 패리티 = 신규 설계(§4-6) |
| P0-5 | 리포는 public | 푸시 = 전문 공개. 푸시는 E4 이후 별도 결정 |
| P0-6 | `valuation_bridge.py`는 컨센서스 EPS gap × 탄력도 구조, MU 컨센서스 `UNAVAILABLE` | 브리지 미사용 |
| **P0-7 (정정)** | rev-1은 과거 EX-99.1을 "10개"로 적었으나, `logs/_claude_scratch/`의 10개 + `logs/mu_ho5_S2_release.html`(FQ3 FY26) = **11개**다. START의 "11개"가 맞다 | E2-A 입력 allowlist에 11개 전부 등재 |
| P0-8 (신규) | FQ3 FY26 비GAAP 조정표에 **"Loss on debt prepayments $325M"** 이 있다 — FROZEN (f-3)이 "미확인"으로 둔 `Other non-operating` −$321M의 주 원인 | 리포트 §7 마진 브리지에 원문 인용. **FROZEN은 수정하지 않는다** |

---

## §2. 결정 사항 D1–D9

### D1. 발행 시점·형태 — **ⓑ 단독, 프린트 전 인프라 선행 (Q-1 반영)**

| 블록 | 시작 조건 (전부 충족) | 내용 | 입력 |
|---|---|---|---|
| **E2-A** | ① P3 승인 ② `HANDOFF_CODEX_mu_report_exec.md` 확정 | 역사 FY23A–FY25A 3표, 분기 추이 FY23Q1–FY26Q3, BU 8분기, 차트·표·렌더러·게이트·테스트, 밸류에이션 틀 | **§4-7 E2-A 허용 입력만.** post-print 슬롯은 `forecast/tests/fixtures/mu_report/` 가짜 값 fixture로만 채워 파이프라인을 시험 |
| **E2-B** | §6의 **4개 입력 게이트** 전부 | FQ4·FY26A-8K, FQ1 FY27 가이던스, RLE FY27E·FY28E, 본문, 렌더 | E2-A 허용 + post-print 입력 |
| **E2-C** | 10-K 원본 확보·SHA 기록 | `FY26A-10K` 반영 **제2판** | + 10-K |

- 프리뷰판(ⓐ)은 내지 않는다(rev-1 사유 유지).
- E2-A는 **로컬 생성까지만**. add/commit/push 없음(R-10).

### D2. 예측 범위 — FY27E 분기 4개 + FY28E 연간 1행 (rev-1 유지)

- FQ1 FY27 앵커 = 회사 가이던스(프린트). FQ2–FQ4 FY27 = RLE YAML. FY28 = 연간 단일 행.
- **YAML**: `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` (Q-4 PASS). 필수 머리 키:

```yaml
scope: report_layer            # 엔진 프로파일 아님. forecast/profiles/ 스캔·FROZEN allowlist 대상 아님
information_cutoff: "<KST ISO>" # 프린트 후 입력 기준 시각
sources: [<source_id>, ...]     # 각 가정의 근거 source_id
units: {money: USD_million, shares: million, ratio: fraction}
week_basis: {FY2027: "52w (13w x 4) ASSUMED", FY2028: "52w ASSUMED"}
confidence: low
input_sha256: {<path>: <sha256>, ...}  # 이 YAML이 참조한 입력 파일 핀
```

- `test_valuation_allowlist.py`의 스캔 범위는 `forecast/profiles/` + `forecast/reports/*_FROZEN.md`이며 `forecast/inputs/`는 스캔하지 않음을 코드에서 확인했다(`_profile_files(profiles_dir)`).

### D3. 밸류에이션 — 암시 배수 + 민감도, 역방향 DCF 제외, 목표주가·투자의견 없음

Q-10 PASS 부분(역방향 DCF 제외·금지 필드) 유지. 정의는 §4-5로 고정.

### D4. 3표 깊이 — §4-3 계약으로 대체

### D5. 출력 형식 — md(생성물)·html·pdf × 한/영 + 공유 xlsx 1개 + PNG 원본 (rev-1 유지, 파일명은 §2 D7)

### D6. 데이터 출처·기준일

| 데이터 | 1차 출처 | 상태 |
|---|---|---|
| FY23–FY25 3표 | 10-K htm `mu-20230831.htm`(FY23·FY22 비교) · `mu-20250828.htm`(FY25·FY24 비교, 3표 3개년 손익·현금흐름) + companyfacts `a8b088c2…` 대조 | 확보 |
| 분기 FY23Q1–FY26Q3 | companyfacts 3개월 기간 + Q4 = FY − 9M | 확보 |
| BU 4개 × 8분기 | 재편 후 보도자료 4건(FY25Q4 PR: FQ4-25·FQ3-25·FQ4-24 / FY26Q1 PR: FQ1-26·FQ4-25·FQ1-25 / FY26Q2 PR: FQ2-26·FQ1-26·FQ2-25 / FY26Q3 PR: FQ3-26·FQ2-26·FQ3-25) | 확보. 규칙 §4-8 |
| DRAM/NAND | 준비문 — 매출 $·비중·QoQ%는 숫자, 가격·비트는 언어적 구간 | FQ3 FY26 준비문만 보관. **FQ4 준비문은 프린트 후 Jiwon 다운로드**. 과거 준비문은 §4-8 규칙상 선택 |
| FQ4·FY26·FQ1 FY27 | 프린트 8-K EX-99.1 + 준비문, 10-K | **미확보 — Jiwon 다운로드 요청**(sandbox → sec.gov 불가) |
| 기준 주가·주식수 | §4-5 | 미확보 |
| 컨센서스 | FQ4 `UNAVAILABLE`(FROZEN) · FY27 `UNAVAILABLE_FOR_COMPARISON` | 표시 전용 |
| SCA 예치금 | 10-K/8-K 본문·주석 좌표 | 표준 XBRL 태그 없음(`CustomerDepositsNoncurrent` 부재 확인) |

### D7. 경로·범위 — 허용 경로 (이 밖을 건드려야 하면 즉시 중단·보고)

| 경로 | 주체 | 용도 |
|---|---|---|
| `forecast/PLAN_mu_report_fy2026q4.md` · `…_revN_superseded.md` | Claude | 계획 |
| `forecast/REVIEW_CODEX_mu_report_plan_rN.md` | Codex | P2 |
| `forecast/HANDOFF_CODEX_mu_report_exec.md` | Claude | E1 |
| `forecast/REVIEW_CLAUDE_mu_report_output_rN.md` | Claude | E3 |
| `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` | Codex | RLE 가정 |
| `forecast/scripts/mu_report/` (`inputs.py`·`facts.py`·`rle.py`·`build.py`·`charts.py`·`render.py`·`gates.py`·`i18n/{ko,en}.yaml`·`sources/*.json`) | Codex | 빌드. `sources/`는 `logs/` 원본의 **추출본**(원본 SHA 기록). `logs/` 자체 커밋 금지 |
| `forecast/reports/mu_report_fy2026q4_ed{N}_{ko,en}.{md,html,pdf}` · `mu_report_fy2026q4_ed{N}_data.xlsx` · `mu_report_fy2026q4_ed{N}_manifest.json` · `forecast/reports/mu_report_fy2026q4_ed{N}_assets/*.png` | Codex | 산출물(판 번호 포함 — 제2판이 제1판을 덮지 않는다) |
| `forecast/tests/test_mu_report.py` · `forecast/tests/fixtures/mu_report/**` | Codex | 신규 테스트·fixture |

**E4 커밋 후보(Q-11)**: 위 산출물 전부 — **KO/EN md·html·pdf, 공유 xlsx, manifest json, 차트 PNG 원본** — + 스크립트·YAML·테스트·fixture·PLAN/HANDOFF/REVIEW 문서. 실제 add/commit은 Jiwon 승인 후 호스트 PowerShell. 파일명 패턴은 `*_FROZEN.md`·`*_SCORED.md`와 겹치지 않는다.

**읽기 전용**: FROZEN · `mu.generic.yaml` · `forecast/engine/**` · `forecast/pipeline/**`(`edgar_fetcher.model_label_for_period` NOTICED BUT NOT TOUCHING) · SCORED(생기면) · `logs/**` · `valuation-results/**` · 루트 `engine/`·`profiles/`.

**시간 예산**: E2-A ≤ 2 세션 / E2-B ≤ 2 세션 / E3 ≤ 3 라운드. 초과 시 범위 축소안을 먼저 Jiwon에게.

### D8. 시각 정체성 — 발행사 로고·브랜드 팔레트 미사용, 중립 팔레트 (rev-1 유지)

### D9. 작성자·면책 — 작성자 "김지원", 면책 고정 키 2개 `disclaimer.not_advice`·`disclaimer.third_party` (rev-1 유지). 제3자 문구: *"공개 자료 기반 제3자 분석이며 Micron 및 계열사가 작성·검토·승인한 자료가 아니다."*

---

## §3. 보고서 구성과 차트

| § | 절 | 핵심 | 그림 |
|---|---|---|---|
| 표지 | 한 페이지 요약 | 3줄 관찰 · 핵심 수치표(**FQ4 FY26 PREREG_A vs A-8K**, FY26E-PREREG_A · FY26A-8K, FY27E-RLE, FY28E-RLE; FY27E·FY28E **비GAAP 칸 = `UNAVAILABLE_WITHOUT_ASSUMPTIONS`**) · as-of · 정보 컷오프 · 데이터 충족도 · 면책 | — |
| 1 | 회사 개요·읽는 규칙 | 4-BU · 회계연도↔달력 매핑 · 52/53주 · 라벨 범례(A-8K·A-10K·PREREG_A·RLE·CITED) | ② |
| 2 | 강세 vs 약세 | 같은 형식으로 병기, 각 논거에 반증 관측원 1개 | — |
| 3 | FQ4 FY26 — 사전등록 대 실적 | Freeze A 원값 · 가이던스 대비 라벨 · 채점은 SCORED 인용만 · 표면/주당 성장 · 컨센서스 `UNAVAILABLE` | ④ ⑤ |
| 4 | FY27 전망 | FQ1 가이던스 주당 정규화 · 가격 사이클 · SCA 함의 | ⑤ |
| 5 | 사업 구조 | BU 8→9분기 추이 · DRAM/NAND 매출(숫자) · 가격·비트 **범주형 표** · HBM 분기 매출 `NOT_DISCLOSED` | ② ③ |
| 6 | 재무제표 | §4-3 계약대로 | ① ⑥ ⑧ |
| 7 | 마진 브리지 | 매출→GM→opex→OP→below-OP(FQ3 debt prepayment $325M 인용)→세금→NI, GAAP↔비GAAP(FQ4만) | — |
| 8 | 시나리오 | bear/base/bull 가정표, 민감도(FQ4 = FROZEN (f-2) 인용, FY27E = RLE 재산출) | — |
| 9 | 밸류에이션 | §4-5 암시 배수 표 · 사이클 경고 · 히트맵 · 연결점·가정·출처 · 목표주가 미산출 사유 | ⑦ |
| 10 | 리스크·스윙 팩터 | FROZEN §(f) 요약(대상명 인용) | — |
| 11 | 촉매·일정 | 10-K · 2026-12-09 이후 자본환원 확대 · 리드스루 — 날짜마다 상태(`CONFIRMED`/`ESTIMATED`)와 source_id | — |
| 12 | 부록 | 방법론 · **FY27 경로 비교표(Freeze A 프로파일 vs RLE, 컷오프 2개)** · 출처 원장 · 정직성 라벨 · 게이트 결과표 · 자기 제약 표 · 면책 | — |

**차트 8종 — 데이터 충족 기준 고정(Q-8)**

| # | 차트 | 데이터 | 충족 기준 → 미충족 시 |
|---|---|---|---|
| ① | 분기 매출·GM·OPM FY23Q1–FY26Q4 | companyfacts + PR | 항상 충족. FQ4 FY26 막대에 14주 표기 + 주당 환산 보조선 |
| ② | BU 믹스 추이 | §4-8 | 동일 4-BU 정의 기간 ≥ 2 → "추이"(현재 8개). 1개면 "단일 기간 믹스" 막대로 **개명** |
| ③ | DRAM vs NAND 매출($) | 준비문의 **숫자** 매출 | SHA 기록된 준비문 기간 ≥ 2(FQ3 + FQ4 FY26, E2-B에서 충족 예정) → 막대. 미달 → 표로 강등하고 **③′로 교체** |
| ③′ | (대체) GAAP GM 가이던스 대비 실적 11분기 | FROZEN (b-1) 10분기 + FQ4 A-8K | ③ 미충족 시에만 사용. 8종 최소 요건 유지 |
| ④ | 가이던스 대비 매출·EPS 상회 이력 | FROZEN (d-1) + FQ4 SCORED 인용 | 항상 |
| ⑤ | 시나리오 fan FQ4 FY26 – FQ4 FY27 | PREREG_A(FQ4) + RLE(FY27) | 두 레이어 선 스타일·범례 분리 |
| ⑥ | 연간 손익 FY23A–FY28E | §4-3 | **FY26은 PREREG_A와 A-8K 이중 표시(나란한 막대 + 브리지 inset)**, 53주 각주 **두 값 모두** |
| ⑦ | 암시 P/E 히트맵 | §4-5 | 가격 고정, 셀마다 동일 RLE 경로 재계산 |
| ⑧ | FCF·순 capex·순현금(예치금 제외) | §4-3 | 순현금 정의 캡션 명시 |

DRAM/NAND 가격·비트의 언어적 구간(`low-60s%`, `mid-single-digit` 등)은 **원문 문자열 그대로 범주형 표**에만 쓴다. 숫자 구간(예: 60–64%)으로 바꾸지 않는다.

---

## §4. 데이터 계약

### 4-1. FY26 4-레이어 (R-3, Q-2)

| 레이어 | 의미 | 값의 출처 | 표시 |
|---|---|---|---|
| `FY26E-PREREG_A` | Freeze A 당시 연간 추정 | **FROZEN 본문에 표시된 값만**: (a-4) base 매출 131,819 · GAAP NI 84,720 · GAAP EPS ≈ 73.9(분기 합산 근사). bear/bull 연간은 FROZEN에 없으므로 `NOT_IN_SOURCE` — 새로 계산하지 않는다 | 주표 옆 별도 열 + "Freeze A FY26E vs FY26A" 브리지 표 |
| `FY26A-8K` | 실적 발표 잠정 | FQ4 PR의 연간 열 | 제1판 주표 |
| `FY26A-10K` | 10-K 확정 | 10-K | **제2판**(E2-C)에서만 등장 |
| `FY27E-RLE` · `FY28E-RLE` | 리포트 레이어 추정 | §4-4 | 주표 |

- **판 번호 규칙**: 제1판 = `ed1`(8-K 기반). 10-K 반영 시 값 차이 유무와 관계없이 **제2판 `ed2`를 별도 파일로** 낸다(라벨 `A-8K`→`A-10K`가 바뀌므로). `ed2`는 8-K vs 10-K 차이표를 부록에 싣는다. `ed1` 파일은 덮어쓰지 않는다.
- 연간 표 열 순서(제1판): FY23A · FY24A · FY25A · **FY26E-PREREG_A** · **FY26A-8K** · FY27E-RLE · FY28E-RLE. FY26 두 열 모두 53주 각주.
- FY23은 regime break(2024Q1) 이전 — 재무제표에는 싣고 백테스트 표본에는 넣지 않는다.

### 4-2. 반올림 (rev-1 유지)

$M 정수 · EPS 소수 2자리 · 비율 소수 1자리. manifest에 전정밀도 보존, 표시만 반올림. PREREG_A 대조는 **FROZEN 표시 문자열 일치**(G-2).

### 4-3. 3표 행·식·가용성 계약 (R-4)

**원칙**: 역사 3표는 10-K 표의 **발행사 계정명(caption)** 을 그대로 쓴다. 한 해에 없는 계정은 `—`. 본문은 아래 **요약 행 집합**, XLSX는 전체 계정.

| 표 | 요약 행 (본문) | FY23A–FY25A | FY26E-PREREG_A | FY26A-8K | FY27E/FY28E-RLE |
|---|---|---|---|---|---|
| 손익 | 매출 · 매출원가 · 매출총이익 · R&D · SG&A · 구조조정/기타 영업손익 · 영업이익 · 이자수익 · 이자비용 · 기타 영업외 · 세전이익 · 법인세 · 지분법 · 순이익 · 희석주식수 · GAAP 희석 EPS | 10-K | 매출·NI·EPS만(나머지 `NOT_IN_SOURCE`) | PR 연간 손익 | 매출·원가·GM·opex(단일 행)·OP·below-OP(단일 행)·세전·법인세·NI·희석주식수·EPS. R&D/SG&A 분해 `UNAVAILABLE` |
| 재무상태 | 현금성자산 · 단기투자 · 매출채권 · 재고 · 유동자산 합계 · 장기 시장성투자 · 유형자산 · 자산총계 · 매입채무 등 · 단기차입 · 유동부채 합계 · 장기차입 · 부채총계 · 자본총계 | 10-K(FY25 10-K: FY25·FY24 / FY23 10-K: FY23) | `NOT_IN_SOURCE` | PR 재무상태표 | **순현금(예치금 제외)만**. 나머지 `UNAVAILABLE` |
| 현금흐름 | 순이익 · 감가상각·무형자산상각(D&A) · SBC · 운전자본 변동 · 영업CF · 유형자산 취득 · 정부 인센티브 수령 · 유형자산 처분 · 투자CF · 차입 변동 · 자사주(원천징수·프로그램) · 배당 · 재무CF · 환율 · 현금 증감 | 10-K | `NOT_IN_SOURCE` | PR 현금흐름표 | D&A · SBC · ΔNWC · 영업CF · 순 capex · 조정 FCF · 배당 · (자사주 `UNAVAILABLE`) |
| 비율 | GM · OPM · ETR · ROE · 순현금 · 순 capex/매출 · 조정 FCF | 계산 | 매출·NI 기반만 | 계산 | GM·OPM·ETR·순 capex/매출·FCF. **ROE `UNAVAILABLE`**(자본 roll-forward가 미모델 자사주에 의존) |

**정의 고정**

- **순 capex (회사 정의 "Investments in capital expenditures, net")** = 유형자산 취득 − 유형자산 처분대금 − 정부 인센티브 수령. FQ3 FY26 원문 대조: 7,826 − 9 − 733 = **7,084** ✓.
- **조정 FCF (회사 정의 "Adjusted free cash flow")** = 영업CF − 순 capex. FQ3 FY26: 25,388 − 7,084 = **18,304** ✓ (원문 18,304).
- **순현금(예치금 제외)** = 현금성자산 + 단기투자 + 장기 시장성투자 − (단기차입 + 장기차입). 제한현금은 포함하지 않는다 → 회사가 말하는 순현금($24.4B, 제한현금 포함)과 **다를 수 있으며 캡션에 명시**. SCA 고객 예치금은 **부채성**으로 보고 순현금에 넣지 않는다(회사: 예치금은 재무CF로 유입, 계약 후반부에 반환, FCF 영향 없음).
- **ROE** = NI ÷ 평균자본((기초+기말)/2). FY23A–FY26A-8K만.
- **RLE 순현금 roll-forward (자사주 전)**: `NetCash_t = NetCash_{t−1} + FCF_t − Dividends_t`. `Dividends_t` = 선언 주당배당 × 기말 희석주식수(YAML). **자사주·인수·차입 변동은 모델하지 않는다** → 행 이름을 "순현금(자사주·인수 전, 예치금 제외)"로 고정. 예치금 유입은 부채와 상쇄되므로 이 정의에서 0.

### 4-4. 행별 계산 경로 (Q-5)

| 출력 행 | 경로 | 식 | 입력 fact | 검증 항등식 |
|---|---|---|---|---|
| FY27 Qi 매출 | 엔진 | `run_generic_forecast(GenericProfile(seed=FQ4 FY26 A-8K, window=2027Q1×4, growth=g_raw_i, op_margin=m_i, tax, net_int, shares))` | FQ4 A-8K 매출·NI · YAML g_week_i · 주수 | `rev_i = rev_{i−1}(1+g_raw_i)` 손계산 일치(1e-9 상대) |
| `g_raw_i` | RLE 순수식 | `g_raw_1 = (1+g_week_1)·13/14 − 1`(FQ1: FQ4 14주 → 13주), `g_raw_{2..4} = g_week_i` | YAML g_week · 주수 | FQ1 매출 = FQ1 가이던스 앵커(YAML에 앵커 식 명시) |
| `m_i` (op_margin) | RLE 순수식 | `m_i = GM_i − opex_i / rev_i` (rev_i는 성장 경로로 먼저 계산) | YAML GM_i · opex$_i | 엔진 OP == `rev_i·GM_i − opex_i` (1e-6 상대) |
| FY27 Qi OP·NI·EPS | 엔진 | 엔진 출력 그대로 | 위 | `NI = (OP + net_int·rev)(1−t)` 손계산 |
| FY27 Qi 매출원가·GM$ | RLE 순수식 | `GM$ = rev·GM`, `COGS = rev − GM$` | 엔진 rev · YAML GM | `GM$ − opex = OP_engine` |
| FY27 연간 | RLE 순수식 | 매출·원가·OP·NI = Σ4분기, EPS = NI ÷ 연평균 희석주식수(YAML) | 분기 행 | Σ분기 = 연간(정확) |
| FY28 연간 | RLE 순수식 | `rev = rev_FY27(1+g_FY28)`, `GM$ = rev·GM`, `OP = GM$ − opex$`, `pretax = OP + net_int·rev`, `NI = pretax(1−t)`, `EPS = NI/shares` | YAML g·GM·opex·net_int·t·shares | 동일 항등식 |
| D&A · SBC | YAML | 연도별 $ | YAML | — |
| ΔNWC | RLE 순수식 | `−k × (rev_t − rev_{t−1})` | YAML k | — |
| 영업CF | RLE 순수식 | `NI + D&A + SBC + ΔNWC` | 위 | — |
| 순 capex | YAML | 연도별 $ (회사: FY27 분기 capex > FQ4 수준) | YAML + 준비문 source_id | — |
| 조정 FCF | RLE 순수식 | 영업CF − 순 capex | 위 | 정의식 재계산 일치 |
| EBITDA | RLE 순수식 | GAAP OP + D&A | 위 | — |
| 순현금 | RLE 순수식 | §4-3 roll-forward | FY26A-8K 기말 순현금 | 역산 일치 |

- Freeze A 프로파일(`mu.generic.yaml`)은 **읽기만** 하며 RLE 입력이 아니다. 부록 FY27 경로 비교표의 Freeze A 쪽 값은 FROZEN에 표시된 값(FY27 Q1 매출 bear/base/bull)은 문자열로, 그 밖의 분기·지표는 `f8cfd47`의 프로파일로 엔진을 **결정적으로 재실행**한 값으로 채우고 레이블 `PREREG_A_PROFILE_PATH`를 붙인다.
- 엔진·스키마는 수정하지 않는다. `GenericProfile`은 `extra="forbid"`이므로 메모리 내 구성은 기존 필드만 쓴다.

### 4-5. 밸류에이션 정의 (Q-10)

| 요소 | 고정 정의 |
|---|---|
| 기준 주가 | **프린트 후 첫 정규장 종가 = 2026-10-01(목) Nasdaq 종가**, USD. 분할 기준: 조정 없음(프로파일 `split_history: []`, 기준일까지 분할 발생 시 E2-B 중단·보고). Jiwon이 **2경로** 캡처(날짜·시각 포함) → G-3e |
| 주식수(시가총액용) | 가장 최근 공시의 **발행주식수(시점 값)** — 10-K 표지 "shares outstanding as of <date>" 또는 그 전까지는 최신 10-Q 표지. 기준일과 다른 날짜임을 캡션에 명시 |
| 시가총액 | 기준 주가 × 위 발행주식수 |
| EV | 시가총액 + 총차입(단기+장기) − (현금성자산 + 단기투자 + 장기 시장성투자). **B/S 기준일 = FY26A-8K 기말(2026-09-03)** |
| SCA 예치금 처리 | EV에서 현금을 줄이는 방향으로 **부채성 조정**: 예치금 금액이 원문에 별도 수치로 있으면 `EV_adj = EV + 예치금`을 보조 행으로 표시. 원문 수치가 없으면 보조 행 = `UNAVAILABLE`(추정하지 않음) |
| EBITDA | GAAP 영업이익 + D&A(현금흐름표 "Depreciation expense and amortization of intangible assets") |
| FCF | §4-3 조정 FCF |
| 분모 basis | FY25A(52주) · FY26A-8K(**53주**) · FY27E-RLE bear/base/bull · FY28E-RLE bear/base/bull. FY26A는 보조 행으로 `×52/53` 비례 환산값을 **근사**로 병기 |
| P/E | 기준 주가 ÷ GAAP 희석 EPS. **EPS ≤ 0 → `N/M`** (FY23A) |
| EV/EBITDA | EV ÷ EBITDA. **EBITDA ≤ 0 → `N/M`** |
| EV/Sales | EV ÷ 매출. 매출 ≤ 0 → `N/M` |
| FCF 수익률 | 조정 FCF ÷ 시가총액. 음수도 표시(부호 유지). 시가총액 ≤ 0 → `N/M` |
| 히트맵 ⑦ | 가격 고정. 축 = {FY27 FQ2–FQ4 주당 성장 오프셋} × {FY27 GM}. **각 셀은 §4-4와 같은 코드 경로로 FY27 EPS를 재계산**한 뒤 P/E를 낸다. base 셀 == 본표 FY27E base P/E (G-13b) |
| 금지 필드 | `target_price` · `fair_value_per_share` · `expected_share_price` · `probability_weighted_share_price` · `expected_value` · `scenario_weighted_central_value` · `mc_mean` — manifest 스키마에 없음(G-12a) |
| 연결점 | 배수의 분모는 A 또는 RLE, 분자는 CITED 가격. 밸류에이션 엔진·`valuation_bridge.py`를 호출하지 않는다. Freeze A 확률가중 EPS에 배수를 곱한 주당값은 만들지 않는다 |

### 4-6. canonical manifest (Q-12, R-8)

```json
{
  "fact_id": "is.revenue.FY2026.A-8K",
  "raw_value": 131819.0,
  "display": {"ko": "131,819", "en": "131,819"},
  "unit": "USD_million",
  "period": "FY2026",
  "period_weeks": 53,
  "basis": "GAAP",
  "label": "A-8K",
  "source_id": "SRC-8K-FQ4FY26",
  "lineage": null,
  "information_cutoff": "…"
}
```

- 계산 fact는 `lineage = {"formula": "<식 id>", "inputs": [fact_id, …]}` 필수.
- **KO/EN 렌더는 manifest만 읽는다.** 표 셀·본문 `{{fact:…}}` 자리표시자·차트 series 점이 모두 fact_id로 기록된 **참조 로그**를 남긴다.
- **R-8 제약**: `fact_id` 접두사 `bridge.nongaap_fixed_027` 는 `period == "FY2026Q4"` · `basis == "PREREG_A_ASSUMPTION"` 인 레코드 **1개만** 허용. 다른 period에서 이 fact를 참조하거나 같은 접두사로 새 레코드를 만들면 G-19 실패. FY27E·FY28E 비GAAP EPS fact는 값 대신 `status = "UNAVAILABLE_WITHOUT_ASSUMPTIONS"`.
- 의도된 KO/EN 차이 allowlist: 날짜 표기 형식 · 절 번호 표기 · 천 단위 구분자 이외의 locale 서식 · accession·URL(동일해야 하나 위치 차이 허용). allowlist 밖의 차이는 실패.

### 4-7. 입력 provenance (Q-1)

- 모든 파일 읽기는 `forecast/scripts/mu_report/inputs.py::read_input(path, phase)` 하나로만. 이 함수는 (i) 경로가 해당 phase allowlist에 있는지 (ii) SHA-256이 핀과 같은지 확인하고 (iii) `input_access_log.json`에 `{path, sha256, phase, read_at}`을 남긴다. 직접 `open()`은 G-7이 금지 리터럴로 잡는다.

| phase | 허용 입력 (경로 + SHA 핀) | 금지 |
|---|---|---|
| E2-A | FROZEN · `mu.generic.yaml` · PANEL · CONSENSUS · companyfacts 캐시 · `logs/_claude_scratch/mu-20230831.htm`·`mu-20250828.htm` · 과거 EX-99.1 10개 · `logs/mu_ho5_S2_release.html`·`S3_10q.html`·`Q3_remarks.pdf` · `forecast/tests/fixtures/mu_report/**` | `logs/mu_postprint_*` · `mu_fy2026q4_SCORED.md` · 가격 캡처 · FY26 10-K · 리포트 가정 YAML의 post-print 값 |
| E2-B | E2-A + post-print 8-K/EX-99.1 · FQ4 준비문 · SCORED(commit·SHA) · 가격 캡처 2경로 · RLE YAML | FY26 10-K |
| E2-C | E2-B + FY26 10-K | — |

- G-20: E2-A 실행 로그에 금지 입력이 **0건**이고, post-print 슬롯의 값이 fixture에서 왔음을 로그로 증명.

### 4-8. BU 데이터 규칙 (Q-8)

- 사용 기간 = **재편 후 보도자료에 실린 4-BU 값만**: FQ4-24 · FQ1-25 · FQ2-25 · FQ3-25 · FQ4-25 · FQ1-26 · FQ2-26 · FQ3-26 (+ E2-B에서 FQ4-26).
- 한 기간이 여러 보도자료에 나오면 **가장 최근 보도자료 값**을 쓰고, 값이 다르면 차이를 부록에 기록한다(재작성 감지).
- 재편 이전 BU 체계와 **이어 붙이지 않는다**.

---

## §5. 검증 게이트

모든 게이트는 **위반 주입 시 실패하는지**도 시험한다(회귀표 = 게이트별 {정상 PASS, 위반 주입 FAIL} 2열, 빈칸 없음).

| 게이트 | 검사 | 실패 시 |
|---|---|---|
| G-1 입력 핀 | §4-7 allowlist의 SHA 전수 대조 (FROZEN `eab1184f…629f9a` · 프로파일 `faa60912…dfd6` · companyfacts `a8b088c2…` 포함) | 중단 |
| G-2 Freeze A 대조 | PREREG_A 표시값 == FROZEN 표시 문자열. `PREREG_A_PROFILE_PATH` 값 == `f8cfd47` 프로파일 엔진 재실행값 | 중단 |
| **G-3 역사 항등식 (허용오차, R-5)** | 아래 식. 허용오차를 넘으면 fail closed. **보정 플러그 금지** | 중단 |
| G-3b B/S | 자산총계 = 부채총계 + 자본총계 (허용오차 동일 규칙) | 중단 |
| G-3c C/F | 영업CF + 투자CF + 재무CF + 환율 = 현금·현금성·제한현금 증감 | 중단 |
| G-3d 회사 정의 재현 | 순 capex · 조정 FCF를 원문 구성 항목으로 재계산 == 원문 값 | 중단 |
| G-3e 가격 2경로 | 기준 주가 두 경로 일치 | 중단 |
| G-3f SCORED 대조 | 인용 채점 값 == SCORED 원문 | 중단 |
| G-7 하드코딩 | 스크립트·i18n의 숫자 리터럴 전수, 사유 등재분만 허용 · 직접 `open()` 금지 | 중단 |
| G-9 컷오프 위생 | PREREG_A 표에 프린트 후 값 없음 · RLE가 PREREG_A를 입력으로 쓰지 않음 · 혼합 표 라벨 열 존재 | 중단 |
| G-12a 구조적 금지 | §4-5 금지 필드가 manifest 스키마에 없음 | 중단 |
| G-12b 면책 | 두 면책 키가 두 판 표지·말미·PDF 각 페이지 푸터에 존재 | 중단 |
| G-13 시각 요소 | 차트 8종(또는 ③′ 대체) 존재·참조 | 중단 |
| **G-13b 차트-표 동일성 (R-6)** | 모든 차트 series 점이 manifest fact(또는 lineage가 있는 derived fact)와 **값 일치**. 차트 전용 수치 금지. 히트맵 base 셀 == 본표 base P/E | 중단 |
| **G-14 출처·날짜 (R-7)** | 표·본문·캡션·각주·표지·일정 날짜의 **모든 숫자·날짜**가 fact_id 참조이거나 allowlist 리터럴(절 번호 등). 모든 fact가 URL·accession·SHA로 해석되는 `source_id`를 가짐. 계산 fact는 `lineage` 필수 | 중단 |
| **G-15 한/영 패리티 (Q-12)** | KO/EN 참조 로그 비교: 같은 위치(표 id·행·열 / placeholder 순번 / series·점 순번)가 **같은 fact_id**를 참조. fact의 value·unit·period·basis·label 일치. 보조: 정규화 숫자 토큰 다중집합 일치. 의도된 차이는 §4-6 allowlist | 중단 |
| G-16 캡션 | 번호·단위·출처·기준일·회계기준 5요소 | 중단 |
| G-17 라벨 | FY/FQ + 달력 병기 · 주수 각주(FY26 두 레이어 모두) · A-8K/A-10K/PREREG_A/RLE/CITED · 컨센서스 `UNAVAILABLE` | 중단 |
| G-17b 컨센서스 비교 금지 | FY27 컨센서스 fact를 입력으로 하는 gap·beat/miss·색상·방향 문장 0건 | 중단 |
| G-18 파일 위생 | 신규 텍스트 LF · NUL 0 · 행말 공백 0 · UTF-8 | 중단 |
| **G-19 브릿지 범위 (R-8)** | §4-6 제약 | 중단 |
| **G-20 입력 provenance (Q-1)** | §4-7 로그 | 중단 |
| **G-21 형식별 QA (R-9)** | 아래 | 중단 |
| 기존 게이트 | `python -m pytest forecast/tests/ -q` 그린 · FROZEN `checked == passed == 5`, `supported_skipped == 0`, `failures == []` · `python forecast/scripts/verify_anchor.py` PASS · `test_valuation_allowlist.py` PASS | 커밋 불가 |

**G-3 허용오차 (공시 $M 반올림 기준)**

- 덧셈·뺄셈 항등식: 반올림된 항이 $k$개면 허용오차 $= 0.5k$ $M. 예: `매출 − 원가 = GM` → $k=3$ → ±$1.5M.
- 분기 합산 = 연간: 분기 4개 + 연간 1개 → $k=5$ → ±$2.5M (Q4 = FY − 9M 도출 행은 정의상 정확 일치).
- EPS: $\left|\dfrac{NI}{S} - EPS\right| \le 0.005 + \dfrac{0.5\,(|EPS| + 1)}{S}$ ($S$ = 희석주식수, 백만 주, 공시 반올림 반영). FQ3 FY26 예: $S=1{,}145$ → 허용 ≈ 0.016.
- 허용오차 안의 차이는 기록만 하고 **값을 고치지 않는다.** 허용오차 초과는 원문 재확인 후에도 남으면 fail closed.

**G-21 형식별 QA**

| 형식 | 검사 |
|---|---|
| PDF (KO·EN) | 전 페이지 PNG 렌더 후 확인: 잘림·겹침·빈 페이지 0 · **브라우저 날짜 머리글·`file:///` 푸터 문자열 0**(SK 2026-09-13 재발 방지) · 한글 폰트 임베드 · `%%EOF` |
| XLSX | 수식 있으면 재계산 또는 cached value 존재 확인 · 오류 셀(`#REF!`·`#DIV/0!`·`#VALUE!`·`#N/A`) 0 · 시트마다 단위·출처·as-of 행 |
| HTML | 외부 네트워크 의존 0(`http(s)://` 스크립트·스타일·이미지 0 — 출처 링크 `<a href>`는 허용) · 내부 앵커·이미지 참조 해석 · 5MB 미만 |
| MD | 로컬 링크 해석 · 표마다 열 수 일치 |

- 🔴 E3에서 Claude는 NUL 스캔·pytest·SHA·G-13b·G-15를 **독립 재실행**한다. 보고서의 "PASS" 기재는 증거로 취급하지 않는다.

---

## §6. 워크플로 · 입력 게이트 · 커밋

| 단계 | 주체 | 산출 | 종료 조건 |
|---|---|---|---|
| P0·P1 | Claude | 본 PLAN | rev-2 작성 ✅ |
| P2 | Codex | `REVIEW_CODEX_mu_report_plan_r2.md` | Q·R 전건 판정 |
| P3 | Jiwon | — | D1–D9 확정 |
| E1 | Claude | `HANDOFF_CODEX_mu_report_exec.md` | 확정 계획 → 실행 지시. 수치 블록은 스크립트 생성 |
| E2-A | Codex | §2 D7 경로 | E2-A 대상 게이트(G-1·3·7·9·12·13·13b·14·15·16·18·20·21) |
| **E2-B 입력 게이트 (R-2)** | — | — | **4개 모두**: ① FQ4 FY26 8-K/EX-99.1 및 준비문 원본 확보 + SHA 기록 ② `forecast/reports/mu_fy2026q4_SCORED.md` 존재 + commit·SHA 기록 ③ 기준 주가 2경로 캡처 확보 ④ P3 승인 + E1 완료 |
| E2-B | Codex | 제1판 | §5 전 게이트 |
| E3 | Claude | `REVIEW_CLAUDE_mu_report_output_rN.md` | 독립 재현 |
| E4 | Jiwon | 호스트 PowerShell 커밋 | 승인된 파일 목록(§2 D7 커밋 후보) + SHA 확인 후. **push는 별도 승인 — 리포 public** |
| E2-C | Codex | 제2판 | 10-K 확보 후, 동일 게이트 |

**R-10**: E2-A·E2-B·E2-C 모두 로컬 생성까지. add/commit/push는 E4에서만, Jiwon 승인 후.

**Jiwon 요청 목록 (sandbox는 sec.gov·시세 사이트 불가)**

1. 프린트 직후: FQ4 FY26 8-K + EX-99.1 + 준비문 PDF (UA `Jiwon Sea <SEC UA 연락처>`) → `logs/mu_postprint_*`
2. 2026-10-01 Nasdaq 종가 2경로 캡처(날짜·시각 포함)
3. 10-K 접수 시 원본 htm
4. (선택) FY27 컨센서스 캡처 — 표시 전용
5. (선택) FQ4-24 이후 과거 준비문 PDF — 차트 ③ 기간 확장용

---

## §7. 스코프 잠금

- 금지: FROZEN·MU 프로파일·엔진·빌더 수정 · 표기 없는 밸류에이션 배선 · `valuation_bridge.py` 호출 · 경쟁사 병렬 모델링 · 투자의견·목표주가 · BU/HBM 수요 모델 · 채점 재계산 · 언어적 구간의 숫자화.
- 허용 경로 밖 변경 필요 시 **즉시 중단·보고**. 기존 테스트 변경은 사유·diff 보고 후 승인.
- git: VM에서는 `GIT_OPTIONAL_LOCKS=0` / `--no-optional-locks` 읽기만.

---

## §8. 알려진 한계 (부록에 그대로 옮긴다)

1. 백테스트는 in-sample, 스킬 근거 아님(FROZEN `NO_OOS_SKILL_EVIDENCE`).
2. 비GAAP은 FQ4 FY26의 **고정 +$0.27 가정**에만 존재. FQ3 실제 갭 0.44. FY27E·FY28E 비GAAP `UNAVAILABLE_WITHOUT_ASSUMPTIONS`.
3. FY27E·FY28E는 리포트 레이어 추정, 확신도 하. FY27·FY28 주수는 52주 `ASSUMED`.
4. HBM 분기 매출 `NOT_DISCLOSED`.
5. DRAM/NAND 가격·비트는 발행사의 언어적 구간 — 숫자로 바꾸지 않는다.
6. 암시 배수는 사이클 고점 부근 이익을 분모로 쓴다. FY23A(`N/M`)·FY24A 저점 참조와 함께 읽어야 한다.
7. RLE 순현금은 자사주·인수 전 값이며 SCA 예치금을 제외한다. 회사 발표 순현금과 정의가 다르다.
8. FY26A는 53주 — 배수·성장률의 분모가 부풀어 있다(`×52/53` 근사 병기).

---

## §9. Codex 재검토 요청 (r2)

r1의 Q-1~Q-12 · R-1~R-10 반영 여부를 판정하고, 아래 신규 판단 3건을 추가로 판정해 달라.

| # | 질문 | Claude 제안 |
|---|---|---|
| Q-13 | 10-K 반영을 값 차이와 무관하게 **항상 제2판(별도 파일)** 으로 내는 규칙 | 예 — 라벨이 바뀌므로 |
| Q-14 | SCA 예치금을 순현금에서 제외하고, EV에는 원문 수치가 있을 때만 보조 행으로 가산하는 처리 | 예 |
| Q-15 | FY26A 배수 분모에 `×52/53` 비례 환산을 **근사 보조 행**으로 병기하는 것 (주 행은 공시값) | 예 |

---

## 부록 A. P0 인벤토리 (R-1)

### A-1. 지정 추적 파일 — 파일별 (2026-09-27 재열람, SHA 앞 12자리)

| # | 파일 | 바이트 · SHA | 구성 요소 (실측) | 판정 |
|---|---|---|---|---|
| 1 | `forecast/reports/sk_hynix_20260913.md` | 4,477 · `b1bdbdb03d4d` | 93행 · 절 9개: Headline · Data Warnings · Consensus Gap · Below-OP 리스크 밴드 · Overlays · 이벤트 조정 EPS · 밸류에이션 브리지(FY25) · Backtest · 표 7 · 이미지 2 | 자동 산출. 형식 모델 아님 |
| 2 | `…/sk_hynix_20260913.html` | 18,689 · `dab0e1eb7950` | 제목 "SK Hynix report" · h2 7개 · **plotly CDN 외부 의존**(`cdn.plot.ly`) · 이미지 0 | G-21 HTML 외부 의존 금지의 반례 |
| 3 | `…/sk_hynix_20260913.pdf` | 416,400 · `24f509a0ad25` | 7쪽 · Skia/PDF(Chrome 인쇄) · 1쪽 머리 `26. 9. 13. 오전 3:56` · **`file:///` 잔존** | G-21 PDF 재발 방지 항목 |
| 4 | `…/sk_hynix_20260913.xlsx` | 6,681 · `988ec4ba987d` | **3시트**: forecast(8×5) · scenarios(5×5) · backtest(5×8), 수식 0 | 얕은 자동 산출물 |
| 5 | `…/sk_hynix_20260913_fan.png` | 36,533 · `f4875d625d49` | 1200×600 시나리오 fan | 차트 ⑤ 개념 참고 |
| 6 | `…/sk_hynix_20260913_beat_miss.png` | 17,845 · `1d91234eace6` | 1200×600 beat/miss | 차트 ④ 개념 참고 |
| 7 | `…/sk_hynix_call_brief_20260604.md` | 895 · `a21f2c78fd62` | 31행 · 주요 토픽 · 예상 Q&A · 컨센서스 플래그 · 분석가 해석 | Q&A 절 형식 참고(FROZEN (e)로 대체) |
| 8 | `…/sk_hynix_call_brief_20260605.md` | 895 · `1fc4e272f315` | #7과 동일 구조 | 동일 |
| 9 | `…/sk_hynix_q2_2026_scorecard.md` | 21,941 · `be9fef52912f` | 289행 · 프로비넌스 · 실측 · 포인트 오차 · 컨센 서프라이즈 · 판정 · 해석 H1–H4 · 시장 반응 · 정정 | 채점 형식(본 리포트는 채점하지 않음) |
| 10 | `forecast/START-skhynix-report-2026q2.md` | 7,475 · `2d261f3c7e35` | 103행 · 확정 사실 · 급소(비반복 이익·미확정 항목·자체 모델 인용 구분) · 모델 실적 정직 기술 · 논점 · 규율 | 규율 상속 |
| 11 | `forecast/HANDOFF_CODEX_hynix_q2_2026_report_2026-08-07.md` | 41,824 · `9dd2096634bb` | 443행 · 사실 오류 3건 · 정상화 방법론 · 항등식 · 판단 12건 · 회귀표 · 개선점 P0–P2 | "계산 경로 섞임" 교훈 → §4-4 |
| 12 | `forecast/reports/T1_vendor_financing_nvda_2026-08-10.md` | 9,543 · `16b029cc5a51` | 155행 · 결론 · dedupe · 3분류 · 인식기간 · 실패조건 · T-4 전달 · 사전등록 대조 | 오염 방지 선언 형식 |
| 13 | `…/T2_buckets_1_3_nvda_2026-08-13.md` | 4,483 · `65d8eda557ab` | 75행 · 3버킷·coverage 항등식 · 경상 순이자 · `UNFORECASTABLE` 선언 · 비오염 확인 | below-OP 표기 규율 |
| 14 | `…/V2_rf_overlay_nvda_2026-08-10.md` | 6,091 · `9d3a776d4ef9` | 123행 · rf 기준일·출처 · βL · **ERP 미해소** · 오버레이 | 역방향 DCF 제외 근거 |
| 15 | `…/T3_nvda_2026-08-10.md` | 27,185 · `a0844e0c7443` | 301행 · ERRATA 이력 · 재현 게이트 · 조건부 역산 본표 · UNREACHABLE 경계 · 현재가·셀사이드 PT 병기 | 가격 기준일 표기 형식 |
| 16 | `…/T4_verdict_draft_nvda_2026-08-13.md` | 11,490 · `b250f9b88760` | 105행(rev-4) · 입력 고정 · 판정 프레임(새 공정가치 미산출) · 반증조건 3 · 채점 훅 | 판정 문장 규율 |
| 17 | `…/FREEZE_A_verification_nvda_2026-08-14.md` | 4,925 · `a0ea3f047aa4` | 67행 · 고정 해시 · 결정성 3회 · 독립 재계산 · fail-closed | G-1·G-2 형식 |
| 18 | `…/MANIFEST_nvda_2026-08-09.md` | 1,076 · `7ad4f7b0b496` | 17행 · 동결 증빙 표 1개 | manifest 형식 |
| 19 | `forecast/PLAN_nvda_2026-08_deep_dive.md` | 31,160 · `e0c55630ea12` | 353행(rev-3) · 투자판단 트랙 · 사후 채점 · 테제 · T-1~T-4 · 사전등록 실패조건 · 정직하게 인정할 것 | 계획 형식 |
| 20 | `forecast/HANDOFF_CODEX_nvda_2026-08_t3_reverse_dcf_rev2.md` | 8,986 · `2d9d1c132a85` | 123행 · rev-1 회신 · UNVERIFIABLE 해소 · 실 엔진 재현 명령 · 주장 전수 | 재현 명령 블록 형식 |
| 21 | `…_rev3.md` | 11,317 · `8bbb53554356` | 134행 · rev-2 조건 해소 추가 | 누적 회신 형식 |
| 22 | `…_rev4.md` | 14,334 · `07502322fbee` | 159행 · 결정성 결함 3건 수용 | 결정성 요구 |
| 23 | `…_rev5.md` | 16,384 · `bd315249cc2c` | 186행 · 규약 2건 확정 + 결론 1건 변경 | 결론 변경 기록 형식 |
| 24 | `…_rev6.md` | 18,942 · `1bffa4ca01b4` | 223행 · V2 rf 오버레이 편입 | — |
| 25 | `…_rev7.md` | 20,387 · `ab9664a967f5` | 241행 · rev-6 FAIL 정정(마진 축 정의 혼재) | "정의 혼재" 교훈 → §4-5 정의 고정 |
| 26 | `forecast/PLAN_valuation_bridge.md` | 7,809 · `60e7fe2016f1` | 74행 · 2층 분리 · 컨센 신뢰도 가드 · 스키마 · acceptance | 브리지 미사용 근거 |
| 27 | `forecast/engine/valuation_bridge.py` | 5,673 · `94884b0890f8` | 124행 · `_overlay_risk_score` · `sensitivity_to_dcf` | 호출하지 않음 |
| 28 | `forecast/tests/test_valuation_allowlist.py` | 12,224 · `95e8e83789bb` | 352행 · 스캔 = `forecast/profiles/` + FROZEN · FROZEN 프로파일 valuation 금지 · FROZEN 10개 해석 | `forecast/inputs/` 비스캔 확인 |
| 29 | `forecast/reports/mu_fy2026q4_forecast_FROZEN.md` | `eab1184f…629f9a` | 381행 · (a)~(f) + 리드스루 | 읽기 전용 입력 |
| 30 | `forecast/profiles/mu.generic.yaml` | `faa60912…dfd6` | 169행 | 읽기 전용 입력 |

### A-2. 보조 선례 (`valuation-results/`, gitignore — 지정 인벤토리를 대체하지 않음)

| 파일 | 실측 | 참고 범위 |
|---|---|---|
| `2026-08-26-nvda-q2-preview/NVIDIA_기업분석보고서_2026-08-26_김지원.{md,html,pdf}` | PDF 33쪽 WeasyPrint, 1쪽 "EQUITY RESEARCH · PRE-PRINT SEALED", 브라우저 머리글 없음 · HTML h2 14개(한 페이지 결론 · 읽는 규칙 · 3개년 재무제표 · 27분기 추이 · 컨센서스 해부 · 사전등록 판정 · 역산 · 분포 · 이익의 질 · 리스크 · 체크리스트 · 결론) · 이미지 19 | 목차·표지·캡션 5요소 |
| 同 `NVIDIA_재무데이터_3개년_2026-08-26.xlsx` | 4시트: 손익계산서(28×5) · 재무상태표(20×5) · 현금흐름표(23×5) · 27분기 원장 | 3표 XLSX 구조 |
| 同 `NVIDIA_밸류에이션_모델_2026-08-26.xlsx` | 4시트: 사전등록·채점 · 가이던스 이력 · 역산 · fact 원장(453행) | fact 원장 시트 |
| 同 `scripts/`(facts · gate_report · charts · build_report · build_pdf · build_xlsx · seal 등) | — | 스크립트 구조 참고(복사 아닌 재구현) |
| `2026-08-07-hynix-q2-update/SK하이닉스_기업분석보고서_2026-08-07.{md,pdf}` + 데이터 xlsx | PDF 19쪽 WeasyPrint · XLSX 8시트(요약 · 분기실적 · 정상화이익력 · 민감도 · 시나리오 · 시장가역산 · EFE채점 · 출처), 수식 119 | 서술 흐름. **확률가중 내재가치 표시는 상속하지 않음** |

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
