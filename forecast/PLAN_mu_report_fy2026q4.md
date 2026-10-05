# PLAN — Micron (MU) 리서치 리포트 · FY2026 Q4 기준 · 한/영 2판 **rev-4.4**

> 작성 2026-09-28 KST (rev-4) · 작성 Claude · 검토 Codex (r4) · 승인 Jiwon
> 직전 판: rev-3 → `forecast/PLAN_mu_report_fy2026q4_rev3_superseded.md` (sha256 `ab4dd6fe…e38636`) · 판정서 `forecast/REVIEW_CODEX_mu_report_plan_r3.md` (sha256 `cd2301be…0d4c`, PASS) · Jiwon P3 승인
> rev-4 근거: 셀사이드 구성 조사 — `forecast/HANDOFF_CODEX_mu_report_survey_r4.md` · `forecast/REVIEW_CODEX_mu_report_survey_r1.md`·`_r2.md` · `forecast/REVIEW_CLAUDE_mu_report_survey_r1.md`·`_r2.md` (합의 종결)
> 근거: START "MU research report (based on FY2026 Q4)" 2026-09-25 · 선행 배치 MU Freeze A (`f8cfd47`, FROZEN sha256 `eab1184f…629f9a`, frozen_at 2026-09-25 08:54:41 KST)
> 직전 판: rev-2 → `forecast/PLAN_mu_report_fy2026q4_rev2_superseded.md` (sha256 `21037cf6…0c2299`) · 판정서 `forecast/REVIEW_CODEX_mu_report_plan_r2.md` (sha256 `3a8050cc…d0470`, CHANGES REQUESTED)
> 그 전 판: rev-1 → `forecast/PLAN_mu_report_fy2026q4_rev1_superseded.md` (sha256 `921dd2f9…268968`) · 판정서 `forecast/REVIEW_CODEX_mu_report_plan_r1.md` (sha256 `f42c7fda…cbaf3`)
> 🔴 **투자 자문 아님.** 본 계획과 모든 산출물(한국어판·영어판)은 투자 자문이 아니며 특정 증권의 매매를 권유하지 않는다.
> 🔴 **rev-4는 계획 문서만 개정한다.** 이 개정으로 만드는 파일은 rev-3 보존 사본 1개뿐이다. 빌드 코드·테스트·i18n 변경은 rev-4 승인 뒤 `HANDOFF_CODEX_mu_report_exec.md` **부록**(S5)으로 지시한다. 빌드 코드는 이미 rev-3 기준으로 E2-A까지 구현돼 있다.

---

## §-1. 리비전 이력

| rev | 일자 | 판정 | 내용 |
|---|---|---|---|
| rev-1 | 2026-09-26 | CHANGES REQUESTED (r1) | 최초 작성. P0 인벤토리 · D1–D9 · 게이트 G-1~G-18 |
| rev-2 | 2026-09-27 | CHANGES REQUESTED (r2) | r1의 Q-1~Q-12 · R-1~R-10 전건 반영. 신설: §4-1 FY26 4-레이어 · §4-3 3표 행·식·가용성 계약 · §4-4 행별 계산 경로 · §4-5 밸류에이션 정의 · §4-6 canonical manifest · §5 게이트 G-3 허용오차 · G-13b · G-14 확장 · G-19 브릿지 범위 · G-20 입력 provenance · G-21 형식별 QA · 부록 A 파일별 인벤토리 |
| rev-3 | 2026-09-27 | PASS (r3) · Jiwon P3 승인 | r2의 C-1~C-4 반영: SCA 순현금·EV 식 교정(§4-3·§4-5) · debt-prepayment 3개 basis 분리(§1 P0-8·§3·§4-6) · 입력 allowlist 전체 경로+SHA와 접근 기록 규칙(§4-7·D7) · ed2 독립 E3/E4 루프(§6). Q-15 적용 범위 명시(§4-5) |
| rev-4 | 2026-09-28 | PASS (r4) · Jiwon 승인 | 셀사이드 구성 조사(표본 14건) 합의 반영. ed1 추가: 시장 데이터 박스(최소) · 이해관계 고지 `disclaimer.conflict`와 G-12c · 쪽 번호 · 목차 · trailing P/B · 회사 재고일수. ed2 예약: 일별 역사적 P/E·P/B 밴드 · 공시 실제치 기반 피어 비교(J-1, §7 개정, G-22·G-22b). §R3 · 부록 B 신설 |
| rev-4.1 | 2026-09-28 | PASS (R5-0 ⓐ) | J-6: D8 시각 정체성 개정 — Micron 계열 **청색 강조색 + 텍스트 표기**, 로고 이미지·상표 서체 모방 없음. 그 외 변경 없음. 보존 사본 `…_rev4_superseded.md` |
| rev-4.2 | 2026-09-28 | (Codex 확인 대기) | D7: 발표 전 내부 리허설(HANDOFF 부록 R5) 산출물의 **쓰기 예외 경로** `logs/_mu_report_runs/dryrun_<UTC>/` 추가. 그 외 변경 없음. 보존 사본 `…_rev4.1_superseded.md` |
| rev-4.3 | 2026-10-01 | PASS (pins r1) | J-7: 발표 후 입력 **예약 경로를 회사·분기 폴더로 이동** — `logs/mu_postprint_*` → `logs/mu/fy2026q4/postprint/*`(§4-7·§6). 기존 E2-A 입력 20개의 경로·SHA는 **변경 없음**(이동은 ed1 E4 이후 별도 정리). 그 외 변경 없음. 보존 사본 `…_rev4.2_superseded.md` |
| **rev-4.4** | **2026-10-05** | (E4 전 정리) | public 리포 규칙 정리: J-3 행의 조사 표본 재배포 플랫폼 **명칭을 일반 표현으로 대체**(출처 명칭은 `logs/`에만). 내용·결정 변경 없음. 보존 사본 `…_rev4.3_superseded.md`(로컬 전용, 커밋 제외). 같은 개정에서 SEC User-Agent 문자열의 개인 이메일을 `<SEC UA 연락처>`로 대체(현행·rev1–3 보존본; 보존본 SHA 참조 갱신) |

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

## §R2. r2 판정 회신 (Q-1 · Q-5 · Q-10 · Q-13 · Q-14 · R-4, C-1~C-4)

| # | r2 판정 | rev-3 조치 | 위치 |
|---|---|---|---|
| Q-1 | CHANGES REQUESTED | 외부 증거 입력을 **정확한 상대경로 + 전체 SHA-256**으로 나열(E2-A 20개). 묶음·glob 표현 삭제. E2-B·E2-C 입력은 **예약 경로**를 지금 고정하고, SHA는 입력 게이트 통과 시 `input_pins.yaml`에 기록한 뒤 Codex 확인을 받아야 해당 단계가 시작된다. 외부 증거 / 내부 템플릿 / 생성물 재검증 읽기를 3종으로 구분. 커밋되는 감사 기록에는 시각을 넣지 않고(결정적), 시각이 있는 실행 로그는 커밋하지 않는 경로로 분리 | §4-7 · D7 |
| Q-5 | CHANGES REQUESTED | 순현금 식을 C-1대로 교정. RLE roll-forward 행 이름에 **차입 변동 미모델**을 추가 | §4-3 · §4-4 |
| Q-10 | CHANGES REQUESTED | `EV_adj`와 `NetCash_ex_SCA`가 **같은 공시 fact** `bs.sca_customer_deposits`를 공유. 공시값이 없으면 둘 다 `UNAVAILABLE` | §4-5 |
| Q-13 | CHANGES REQUESTED | ed2 = `E2-C → E3-ed2 → E4-ed2`. ed2 파일 목록·SHA에 대한 Jiwon 별도 승인. push도 판별로 별도 승인. ed1 승인이 ed2 권한을 갈음하지 않음 | §6 |
| Q-14 | CHANGES REQUESTED | `NetCash_unadjusted`(예치금 미조정)을 주 행으로, `NetCash_ex_SCA = NetCash_unadjusted − 미상환 SCA 고객예치금`을 공시값이 있을 때만 보조 행으로. 없으면 `UNAVAILABLE` | §4-3 · §4-5 |
| Q-15 | PASS (조건) | `×52/53`은 **flow 분모(매출·EPS·EBITDA·FCF)에만** 적용, point-in-time 분자(시가총액·EV·순현금)에는 적용하지 않음. 본문 결론·기본값으로 쓰지 않음 | §4-5 |
| R-4 | CHANGES REQUESTED | C-1 반영(위) | §4-3 |
| C-2 | — | `$325M`(비GAAP 조정표) · `$323M`(10-Q 부채 주석, 영업외 인식 손실) · `−$321M`(GAAP 손익계산서 영업외 순액)을 **별도 fact 3개**로. $2M 차이는 원문 basis 차이로 남기고 조정하지 않는다 | §1 · §3 · §4-6 |

10-Q 원문 확인(2026-09-27): *"In connection with these prepayments, we recognized losses in other non-operating income (expense) of $323 million and $500 million for the third quarter and first nine months of 2026, respectively."* (`logs/mu_ho5_S3_10q.html`, Debt Activity)

---

## §R3. 셀사이드 구성 조사 회신 (rev-4)

### R3-a. 절차

1. Claude와 Codex가 같은 표본(R-01~R-14, 형식 기준 문서 G-01·G-02)을 **서로의 판정을 보지 않고** 독립 추출·분류했다. Claude 판정은 SHA로 봉인했다(`_matrix.md` `67c294ce…f776`, C2에서 재계산해 일치 확인).
2. 두 판정을 대조해 쟁점 D-1~D-11, 셀 쟁점 C-1~C-7을 번호로 붙이고 2라운드 만에 **전건 종결**했다. 셀 값은 원본 쪽을 다시 보고 사실로 정했다(Codex 셀 수정 6건, Claude 판독 철회 1건).
3. 빈도는 기술 통계일 뿐이다. 요소를 추가(➕)한 근거는 빈도가 아니라 **기존 fact로 계산 가능한지, 게이트로 막을 수 있는지**다.
4. 조사 자료의 투자의견·목표주가·추정치·컨센서스·배수 **숫자는 어디에도 기록하지 않았다.** 이 계획에서 리포트는 R-ID로만 부르고, 발행사명은 `logs/sellside_survey/mu_fy2026q4/_ledger.md`(gitignore)에만 둔다.

### R3-b. Jiwon 결정 (2026-09-28)

| # | 결정 | 반영 |
|---|---|---|
| J-1 | 피어 비교 허용. 단, 피어 **공시 실제치**와 같은 기준일 시장가격에 기반한 지표만 쓴다. 피어 추정치·컨센서스·목표가는 쓰지 않는다 | §7 개정 · §3 9절(ed2) · §5 G-22·G-22b |
| J-2 | 작성자는 작성일 현재 MU 주식을 보유하지 않는다. 보유 상태는 판마다 발행 직전에 다시 확인한다 | D9 · §4-7 · §5 G-12c · §6 |
| J-3 | 해외 재배포 플랫폼의 재배포본(조사 표본 R-08·R-09)을 합법 공개 자료로 인정한다 | 부록 B-0 |
| J-4 | 증권사가 고객에게 배포한 매크로 자료는 적법하게 확보한 표본 외 참고 자료로만 둔다 | 부록 B-0(X-01·X-02) |
| J-5 | 조사 자료는 `logs/sellside_survey/{ticker}_fy{YYYY}q{N}/`에 저장한다(회사의 회계연도 기준) | 부록 B-0 |
| J-6 (rev-4.1) | 시각 정체성: 선례(NVDA·SK하이닉스)처럼 대상 회사에 맞춘 디자인. 단 **로고 이미지 없이** 청색 계열 강조색 + 텍스트 표기 | D8 |

### R3-c. 합의 결과 요약

| 분류 | 개수 | 항목 |
|---|--:|---|
| ✅ 이미 반영 | 32 | 부록 B-2 |
| ➕ ed1 | 5 | 시장 데이터 박스(최소) · 이해관계 고지 · 쪽 번호 · 목차 · trailing P/B (+ 분할 행 #29의 회사 재고일수 = ed1 항목 6개) |
| ➕ ed2 | 3 | 역사적 밴드(#25·#45) · 피어 비교 |
| ⛔ 의도적 제외 | 12 | 투자의견 · 목표주가 · 상승여력 · 목표 배수 근거 · 등급 체계 · DCF · SOTP · 사업부 추정 · 추정치 변경표 · 핵심 도표 모음 · 산포도 · 컨센서스 수정 이력 |
| ❓ 데이터 불가 | 1 | 콜 Q&A(준비문으로 대체) |
| 분할 행 | 2 | #8 작성자 ✅ / 연락처 ⛔ · #29 회사 재고일수 ➕ / 업계 재고 ❓ |
| 합계 | 55 | 기본 50 + 추가 5 |

- **추정치 변경표(⛔)**: Freeze A와 RLE는 정보 컷오프도 방법도 다르다. 이를 "이전→신규"로 보여 주면 같은 모델을 고친 것처럼 읽히므로 넣지 않는다. rev-3 §3 12절의 경로 비교표를 그대로 둔다.
- **판 배정 원칙**: ed1에는 **새 외부 입력이 없는** 항목만 넣는다. 예외는 J-2 확인 레코드(Jiwon 자기확인)다. 새 외부 입력과 교차회사 정규화가 필요한 항목은 ed2로 보낸다.
- **적용 조건**: rev-4 승인과 HANDOFF 부록(S5) 구현이 E2-B 입력 게이트 충족 전에 끝나지 않으면, E2-B는 rev-3대로 진행하고 ed1 추가 항목도 ed2로 넘어간다. 이 판단은 Jiwon이 한다(§6).

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
| P0-8 (rev-3 정정) | FROZEN (f-3)이 "미확인"으로 둔 FQ3 FY26 `Other non-operating income (expense), net` **−$321M**(GAAP 손익계산서 순액)의 주된 설명은 10-Q 부채 주석의 **debt-prepayment 인식 손실 $323M**(영업외 인식)이다. 보도자료 비GAAP 조정표의 `Loss on debt prepayments` **$325M**은 **다른 basis**(비GAAP 조정 항목)다 | 세 수치를 별도 fact로 리포트 §7에 인용하고 $2M 차이는 basis 차이로 남긴다. **FROZEN은 수정하지 않는다** |

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
| `forecast/scripts/mu_report/input_pins.yaml` | Codex (Codex 확인) | E2-B·E2-C 입력 핀(§4-7) |
| `forecast/reports/mu_report_fy2026q4_ed{N}_input_manifest.json` | Codex | 결정적 감사 기록(§4-7) |
| `logs/_mu_report_runs/*.json` | Codex | 시각 포함 실행 로그 — **커밋 안 함** |
| `logs/_mu_report_runs/dryrun_<UTC 타임스탬프>/**` (rev-4.2) | Codex | 발표 전 **내부 리허설** 산출물(KO/EN md·html·pdf·xlsx, 차트 PNG, manifest, 감사 기록, 쪽 PNG). `logs/**` 읽기 전용 규칙의 **유일한 쓰기 예외**다. 파일명에 `DRYRUN`. **커밋·복사·배포 금지.** 입력은 E2-A allowlist만 쓴다(HANDOFF 부록 R5) |
| `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` | Jiwon 확인 · Codex 템플릿 (rev-4) | J-2 발행 직전 보유 확인 레코드. **public 리포 커밋 대상**(§4-7, G-12c) |
| `forecast/HANDOFF_CODEX_mu_report_survey_r4.md` · `forecast/REVIEW_{CODEX,CLAUDE}_mu_report_survey_r{N}.md` | Claude·Codex (rev-4) | 셀사이드 구성 조사 기록. 원문 인용·발행사명 없음 |

**E4 커밋 후보(Q-11)**: 위 산출물 전부 — **KO/EN md·html·pdf, 공유 xlsx, manifest json, input_manifest json, 차트 PNG 원본** — + 스크립트·YAML·테스트·fixture·PLAN/HANDOFF/REVIEW 문서. 실제 add/commit은 Jiwon 승인 후 호스트 PowerShell. 파일명 패턴은 `*_FROZEN.md`·`*_SCORED.md`와 겹치지 않는다.

**읽기 전용**: FROZEN · `mu.generic.yaml` · `forecast/engine/**` · `forecast/pipeline/**`(`edgar_fetcher.model_label_for_period` NOTICED BUT NOT TOUCHING) · SCORED(생기면) · `logs/**`(예외: 위 표의 `logs/_mu_report_runs/*.json`·`logs/_mu_report_runs/dryrun_<UTC>/**` 쓰기) · `valuation-results/**` · 루트 `engine/`·`profiles/`.

**시간 예산**: E2-A ≤ 2 세션 / E2-B ≤ 2 세션 / E3 ≤ 3 라운드. 초과 시 범위 축소안을 먼저 Jiwon에게.

### D8. 시각 정체성 — 대상 회사 계열 강조색 + 텍스트 표기, 로고 이미지 없음 (rev-4.1, J-6)

- **강조색**: 청색 계열 1개(주 강조) + 중립 회색 단계. Micron의 **공식 색이라고 주장하지 않는다.** 정확한 브랜드 hex를 복제할 필요도 없다. 본문 텍스트 대비 WCAG AA(4.5:1) 이상을 지킨다. 차트 보조색은 색각 이상에서도 구분되는 팔레트를 쓰고, 색만으로 의미를 전달하지 않는다(선 종류·라벨 병기).
- **표지 표기**: `Micron Technology, Inc. (NASDAQ: MU)`를 **리포트 본문 서체**로 쓴 텍스트로만 표기한다. 로고 이미지, 상표 서체·자형 모방, 로고 형태의 그래픽은 쓰지 않는다. 회사명 바로 아래에 `disclaimer.third_party` 요지(제3자 분석 · 회사 미승인)를 한 줄로 둔다.
- **금지(유지)**: 증권사·은행의 레이아웃·로고·면책 문구 모방(조사 표본 포함), Micron 로고 이미지.
- **렌더 구현**: 스타일은 렌더러의 단일 테마 설정으로 두고 KO/EN이 같은 테마를 쓴다. 색 값은 i18n이 아니라 테마 설정에 둔다(G-7 숫자 리터럴 규칙의 설정 예외로 등재).

### D9. 작성자·면책 — 작성자 "김지원", 면책 고정 키 2개 `disclaimer.not_advice`·`disclaimer.third_party` (rev-1 유지). 제3자 문구: *"공개 자료 기반 제3자 분석이며 Micron 및 계열사가 작성·검토·승인한 자료가 아니다."*

**rev-4 추가 (J-2, ed1)** — 이해관계 고지 키 2개:

| 키 | KO | EN |
|---|---|---|
| `disclaimer.conflict` | 발행 직전 확인 시각({{conflict.confirmed_at_kst}}) 현재, 작성자 김지원은 Micron Technology, Inc. (MU) 주식을 보유하지 않습니다. | As of the pre-publication confirmation time ({{conflict.confirmed_at_kst}}), the author, Jiwon Kim, does not hold shares of Micron Technology, Inc. (MU). |
| `disclaimer.conflict_short` (PDF 푸터) | 작성자 MU 주식 미보유 - 발행 직전 재확인. | Author does not hold MU shares - reconfirmed before publication. |

- 두 키는 확인 레코드(§4-7)의 `status == not_held`일 때만 렌더한다. `held`이거나 레코드가 없거나 기한이 지났으면 **렌더를 중단한다**(G-12c). 보유 상태가 바뀌면 문안을 자동으로 추정하지 않고 Jiwon이 새 문안을 승인한다.
- 연락처는 싣지 않는다(비공개가 기본). Jiwon이 공개용 연락처를 명시적으로 승인하면 그때 설정값과 KO/EN 패리티 검사를 추가한다.

---

## §3. 보고서 구성과 차트

| § | 절 | 핵심 | 그림 |
|---|---|---|---|
| 표지 | 한 페이지 요약 | 3줄 관찰 · 핵심 수치표(**FQ4 FY26 PREREG_A vs A-8K**, FY26E-PREREG_A · FY26A-8K, FY27E-RLE, FY28E-RLE; FY27E·FY28E **비GAAP 칸 = `UNAVAILABLE_WITHOUT_ASSUMPTIONS`**) · as-of · 정보 컷오프 · 데이터 충족도 · 면책 · **(rev-4) 시장 데이터 박스(최소, §4-5) · 이해관계 고지 `disclaimer.conflict`** | — |
| 목차 (rev-4) | 표지 다음 1쪽 | 12개 절 제목·순서. **쪽 번호는 PDF에만**, md·html은 절 앵커 링크. KO/EN 절 순서·앵커 동일(G-15) | — |
| 1 | 회사 개요·읽는 규칙 | 4-BU · 회계연도↔달력 매핑 · 52/53주 · 라벨 범례(A-8K·A-10K·PREREG_A·RLE·CITED) | ② |
| 2 | 강세 vs 약세 | 같은 형식으로 병기, 각 논거에 반증 관측원 1개 | — |
| 3 | FQ4 FY26 — 사전등록 대 실적 | Freeze A 원값 · 가이던스 대비 라벨 · 채점은 SCORED 인용만 · 표면/주당 성장 · 컨센서스 `UNAVAILABLE` | ④ ⑤ |
| 4 | FY27 전망 | FQ1 가이던스 주당 정규화 · 가격 사이클 · SCA 함의 | ⑤ |
| 5 | 사업 구조 | BU 8→9분기 추이 · DRAM/NAND 매출(숫자) · 가격·비트 **범주형 표** · HBM 분기 매출 `NOT_DISCLOSED` | ② ③ |
| 6 | 재무제표 | §4-3 계약대로 | ① ⑥ ⑧ |
| 7 | 마진 브리지 | 매출→GM→opex→OP→below-OP(FQ3: 영업외 순액 −$321M 중 debt-prepayment 인식 손실 $323M[10-Q] · 비GAAP 조정 $325M[보도자료]을 basis별로 병기)→세금→NI, GAAP↔비GAAP(FQ4만) | — |
| 8 | 시나리오 | bear/base/bull 가정표, 민감도(FQ4 = FROZEN (f-2) 인용, FY27E = RLE 재산출) | — |
| 9 | 밸류에이션 | §4-5 암시 배수 표(**rev-4: trailing P/B 보조 행**) · 사이클 경고 · 히트맵 · 연결점·가정·출처 · 목표주가 미산출 사유 · **(ed2 예약) 일별 역사적 P/E·P/B 밴드 · 공시 실제치 기반 피어 비교표(J-1)** | ⑦ |
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
| ⑧ | FCF·순 capex·순현금(SCA 미조정 주 계열 + 공시 시 SCA 조정 보조 계열) | §4-3 | 두 순현금 정의와 SCA 공시 여부를 캡션에 명시 |

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
| 재무상태 | 현금성자산 · 단기투자 · 매출채권 · 재고 · 유동자산 합계 · 장기 시장성투자 · 유형자산 · 자산총계 · 매입채무 등 · 단기차입 · 유동부채 합계 · 장기차입 · 부채총계 · 자본총계 | 10-K(FY25 10-K: FY25·FY24 / FY23 10-K: FY23) | `NOT_IN_SOURCE` | PR 재무상태표 | **`NetCash_unadjusted` roll-forward만**(+ `NetCash_ex_SCA`는 공시 예치금이 있을 때만). 나머지 `UNAVAILABLE` |
| 현금흐름 | 순이익 · 감가상각·무형자산상각(D&A) · SBC · 운전자본 변동 · 영업CF · 유형자산 취득 · 정부 인센티브 수령 · 유형자산 처분 · 투자CF · 차입 변동 · 자사주(원천징수·프로그램) · 배당 · 재무CF · 환율 · 현금 증감 | 10-K | `NOT_IN_SOURCE` | PR 현금흐름표 | D&A · SBC · ΔNWC · 영업CF · 순 capex · 조정 FCF · 배당 · (자사주 `UNAVAILABLE`) |
| 비율 | GM · OPM · ETR · ROE · 순현금 · 순 capex/매출 · 조정 FCF · **재고일수(rev-4)** | 계산 | 매출·NI 기반만 | 계산 | GM·OPM·ETR·순 capex/매출·FCF. **ROE `UNAVAILABLE`**(자본 roll-forward가 미모델 자사주에 의존) · **재고일수 `UNAVAILABLE`**(재고 미모델) |

**정의 고정**

- **순 capex (회사 정의 "Investments in capital expenditures, net")** = 유형자산 취득 − 유형자산 처분대금 − 정부 인센티브 수령. FQ3 FY26 원문 대조: 7,826 − 9 − 733 = **7,084** ✓.
- **조정 FCF (회사 정의 "Adjusted free cash flow")** = 영업CF − 순 capex. FQ3 FY26: 25,388 − 7,084 = **18,304** ✓ (원문 18,304).
- **순현금 — 두 정의 (C-1)**
  - `NetCash_unadjusted` = 현금성자산 + 단기투자 + 장기 시장성투자 − (단기차입 + 장기차입). **주 행.** 라벨 "순현금(SCA 예치금 미조정)". 실제 현금에는 SCA 예치금 유입이 들어 있으므로 이 값은 예치금 효과를 **포함**한다.
  - `NetCash_ex_SCA` = `NetCash_unadjusted` − 미상환 SCA 고객예치금(`bs.sca_customer_deposits`). **보조 행, 공시값이 있을 때만.** 공시값이 없으면 `UNAVAILABLE`(추정 금지).
  - 제한현금은 두 정의 모두 제외 → 회사 발표 순현금($24.4B, 제한현금 포함)과 다를 수 있으며 캡션에 명시.
  - 근거: 회사는 예치금을 재무CF로 받고 계약 후반부에 반환하며 FCF에 영향이 없다고 밝혔다(FQ3 준비문) — 즉 부채성 현금이다.
- **ROE** = NI ÷ 평균자본((기초+기말)/2). FY23A–FY26A-8K만.
- **재고일수 (rev-4, ed1)** = 평균(기초 재고, 기말 재고) ÷ 매출원가 × (`period_weeks` × 7). FY23A–FY26A-8K만. 기초·기말 재고와 매출원가는 같은 연결 범위·회계기준이어야 한다. FY26A-8K는 53주를 그대로 반영하고 52주로 환산하지 않는다. 기초 재고가 없거나 범위가 다르면 `UNAVAILABLE`, 매출원가 ≤ 0이면 `N/M`. **업계 재고는 싣지 않는다**(합법·재현 가능한 입력 없음, 부록 B-2 #29).
- **RLE 순현금 roll-forward**: `NetCash_unadjusted_t = NetCash_unadjusted_{t−1} + FCF_t − Dividends_t`. 시작값 = FY26A-8K 기말 `NetCash_unadjusted`. `Dividends_t` = 선언 주당배당 × 기말 희석주식수(YAML). **자사주·인수·차입 변동·SCA 예치금 신규 유입/반환은 모델하지 않는다** → 행 이름 고정: "순현금(자사주·인수·차입변동 전, SCA 예치금 미조정)". RLE 기간의 `NetCash_ex_SCA`는 예치금 경로를 모델하지 않으므로 `UNAVAILABLE`.

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
| SCA 예치금 처리 | `EV`(주 행)는 `NetCash_unadjusted`와 같은 현금·투자·차입 항목을 쓴다. **부채성 조정** `EV_adj = EV + bs.sca_customer_deposits` — `NetCash_ex_SCA`와 **같은 공시 fact**를 공유한다. 공시값이 없으면 `EV_adj`·`NetCash_ex_SCA` **둘 다 `UNAVAILABLE`** |
| EBITDA | GAAP 영업이익 + D&A(현금흐름표 "Depreciation expense and amortization of intangible assets") |
| FCF | §4-3 조정 FCF |
| 분모 basis | FY25A(52주) · FY26A-8K(**53주**) · FY27E-RLE bear/base/bull · FY28E-RLE bear/base/bull. FY26A는 보조 행으로 `×52/53` 비례 환산값을 **근사**로 병기 — **flow 분모(매출·EPS·EBITDA·FCF)에만** 적용하고 point-in-time 분자(시가총액·EV·순현금)에는 적용하지 않는다. 본문 결론·기본값으로 쓰지 않는다(Q-15) |
| P/E | 기준 주가 ÷ GAAP 희석 EPS. **EPS ≤ 0 → `N/M`** (FY23A) |
| EV/EBITDA | EV ÷ EBITDA. **EBITDA ≤ 0 → `N/M`** |
| EV/Sales | EV ÷ 매출. 매출 ≤ 0 → `N/M` |
| FCF 수익률 | 조정 FCF ÷ 시가총액. 음수도 표시(부호 유지). 시가총액 ≤ 0 → `N/M` |
| **trailing P/B (rev-4, ed1)** | 기준 주가 ÷ (FY26A-8K 기말 자본총계 ÷ 위 발행주식수). **보조 행**이며 목표가·투자의견과 연결하지 않는다. RLE 기간 P/B는 만들지 않는다(자본 roll-forward 없음). 캡션에 기준 주가일·자본 기준일·주식수 기준일을 각각 적는다(G-16). 자본 또는 주식수 fact가 없으면 `UNAVAILABLE`, 주당장부가치 ≤ 0 → `N/M` |
| **시장 데이터 박스 (rev-4, ed1)** | 표지 블록. 기준 주가 · 발행주식수(기준일 병기) · 시가총액 · 회계연도 종료일 — **위 정의의 fact만** 재사용한다. 52주 범위·거래량·유동비율은 넣지 않는다(새 입력). 구성 fact가 없으면 해당 셀만 `UNAVAILABLE`이며 다른 날짜 값으로 대체하지 않는다 |
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
- **debt-prepayment 3개 fact (C-2)** — 합치거나 조정하지 않는다:

| fact_id | 값 ($M) | basis | source_id | 의미 |
|---|--:|---|---|---|
| `is.other_nonop_net.FY2026Q3.A` | −321 | GAAP 손익계산서 | `SRC-PR-FQ3FY26` (`logs/mu_ho5_S2_release.html`) | 영업외 순액 전체 |
| `note.debt_prepayment_loss.FY2026Q3.A` | 323 | 10-Q 부채 주석(영업외 인식 손실) | `SRC-10Q-FQ3FY26` (`logs/mu_ho5_S3_10q.html`) | −321의 주된 설명 |
| `recon.loss_on_debt_prepayments.FY2026Q3.NONGAAP_ADJ` | 325 | 비GAAP 조정표 | `SRC-PR-FQ3FY26` | 비GAAP 조정 항목 |

- **SCA 예치금 fact**: `bs.sca_customer_deposits.<기간>` — 원문 좌표가 있는 공시값만. 없으면 레코드 `status = "UNAVAILABLE"`이며 `NetCash_ex_SCA`·`EV_adj`가 이를 입력으로 받아 자동으로 `UNAVAILABLE`이 된다.
- **KO/EN 렌더는 manifest만 읽는다.** 표 셀·본문 `{{fact:…}}` 자리표시자·차트 series 점이 모두 fact_id로 기록된 **참조 로그**를 남긴다.
- **R-8 제약**: `fact_id` 접두사 `bridge.nongaap_fixed_027` 는 `period == "FY2026Q4"` · `basis == "PREREG_A_ASSUMPTION"` 인 레코드 **1개만** 허용. 다른 period에서 이 fact를 참조하거나 같은 접두사로 새 레코드를 만들면 G-19 실패. FY27E·FY28E 비GAAP EPS fact는 값 대신 `status = "UNAVAILABLE_WITHOUT_ASSUMPTIONS"`.
- 의도된 KO/EN 차이 allowlist: 날짜 표기 형식 · 절 번호 표기 · 천 단위 구분자 이외의 locale 서식 · accession·URL(동일해야 하나 위치 차이 허용). allowlist 밖의 차이는 실패.

### 4-7. 입력 provenance (Q-1 · C-3)

**읽기 3종 구분**

| 종류 | 정의 | 통제 |
|---|---|---|
| 외부 증거 입력 | 리포트 수치의 출처가 되는 파일 | `inputs.py::read_input(path, phase)`로만. 경로가 phase allowlist에 있고 **전체 SHA-256이 핀과 같아야** 읽는다. 직접 `open()` 금지(G-7) |
| 내부 템플릿·설정 | `forecast/scripts/mu_report/**`, `i18n/{ko,en}.yaml`, `forecast/inputs/mu_fy2026q4_report_assumptions.yaml`, `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`(rev-4), `forecast/tests/fixtures/mu_report/**` | git 추적 파일로 통제(커밋 SHA). 감사 기록에 경로와 blob SHA를 남기되 외부 allowlist 대상 아님 |
| 생성물 재검증 읽기 | 게이트가 방금 만든 `forecast/reports/mu_report_fy2026q4_ed{N}_*`를 다시 읽는 것 | 경로가 해당 판의 산출물 접두사에 한정. 외부 입력으로 취급하지 않음 |

**E2-A 외부 증거 입력 allowlist — 전체 경로 + 전체 SHA-256 (2026-09-27 측정)**

| # | 경로 (리포 루트 기준) | SHA-256 |
|--:|---|---|
| 1 | `forecast/reports/mu_fy2026q4_forecast_FROZEN.md` | `eab1184f721cd69460ffc4ddefd9851c59815207c35975db0dd1a2962b629f9a` |
| 2 | `forecast/profiles/mu.generic.yaml` | `faa60912b6a364eee67f87d9ba21221a6c6da02f22695c4d980200260982dfd6` |
| 3 | `forecast/PANEL_efe_2026sep_mu_G0H_2026-09-25.md` | `2890a2a218bbbb8f56775eb0c8d20967ee9546bd5c916c1c5ab7ac3e0039ef33` |
| 4 | `forecast/CONSENSUS_efe_2026sep_mu_FY26Q4_2026-09-25.md` | `65077ba1079a5f903230848a92aa214647a850048803d6cf33f56c5b53568d53` |
| 5 | `forecast/reports/.cache/edgar_companyfacts_CIK0000723125.json` | `a8b088c2111daef36536e53c81fef4c0f01220c64933e126a665b00a9257f882` |
| 6 | `logs/_claude_scratch/mu-20230831.htm` (FY2023 10-K) | `54bdb6a96570e56071b532434751c7d1ea6189e18b45e3aa2bf82101f38d69fb` |
| 7 | `logs/_claude_scratch/mu-20250828.htm` (FY2025 10-K) | `84ea0693543f8f86af6c981934f43320c5ccf230d5642d050598a535dacc5ad2` |
| 8 | `logs/_claude_scratch/mu_G2024Q2_ex991.htm` (FQ1 FY24 PR) | `cba05d3a7684f893b43a3a54ec2bf27145a4ed4ed2197ff94d8168464cab2abb` |
| 9 | `logs/_claude_scratch/mu_G2024Q3_ex991.htm` (FQ2 FY24 PR) | `a635cd2a7c38e53ca19d60c94cf65ec45cddc3f175cee20b6078a1f48088d94a` |
| 10 | `logs/_claude_scratch/mu_G2024Q4_ex991.htm` (FQ3 FY24 PR) | `51fa896d882da1544c4bdcf52c52ce1acc15ff4ba0f7ea413ef848d8a186a938` |
| 11 | `logs/_claude_scratch/mu_FY2024Q4_ex991.htm` (FQ4 FY24 PR) | `3faad63e6c8e3667a09e72916aa6a6e313ac3e205b24a3f625caa88b50bfe30a` |
| 12 | `logs/_claude_scratch/mu_G2025Q2_ex991.htm` (FQ1 FY25 PR) | `f1ece4749d1a645444f9e32c02e494c61ec7d2bcedac8949c1430e8faf715856` |
| 13 | `logs/_claude_scratch/mu_G2025Q3_ex991.htm` (FQ2 FY25 PR) | `503fbf81dc7fbf45c0a2bfe1f69a93b7b2fa352e490a3366738bf5262f65021a` |
| 14 | `logs/_claude_scratch/mu_G2025Q4_ex991.htm` (FQ3 FY25 PR) | `170cac3d1ae6d47c27ec6cdf619e67a5f00b5ccf49ecf9421d65d037fc00928a` |
| 15 | `logs/_claude_scratch/mu_FY2025Q4_ex991.htm` (FQ4 FY25 PR) | `34478c62e48f4184444c2cb72e4e4da28389026aa636297e80d33a79694efc58` |
| 16 | `logs/_claude_scratch/mu_G2026Q2_ex991.htm` (FQ1 FY26 PR) | `ee2e84a14aefe39c12f9808ef596f8819a10ce902d7c083947d9473c05fc640e` |
| 17 | `logs/_claude_scratch/mu_G2026Q3_ex991.htm` (FQ2 FY26 PR) | `18c8475fe645dacbdb048073869a393c3dc82d7440d89fe5cf25c7a457851927` |
| 18 | `logs/mu_ho5_S2_release.html` (FQ3 FY26 PR) | `9f7e667a8224193b438287d0186c7273262c79e98af71feb3613e0837347c392` |
| 19 | `logs/mu_ho5_S3_10q.html` (FQ3 FY26 10-Q) | `bf4c3fb1833243d1c41c0426c4e0332d3a2f61a2b44e534fe8ff13648f205e20` |
| 20 | `logs/mu_ho5_Q3_remarks.pdf` (FQ3 FY26 준비문) | `a3ce62b84a059e35fae80c2bfd5c89f9af334193fd6aceff698fc3008e7d4c27` |

(#8–#18 = 보도자료 11개. 파일명의 `G{분기}`는 "그 분기 가이던스를 담은 직전 분기 보도자료"라는 저장 규칙이며, 괄호가 실제 실적 분기다.)

**E2-B · E2-C 예약 경로 — SHA는 입력 게이트에서 기록**

| phase | 예약 경로 | SHA |
|---|---|---|
| E2-B | `logs/mu/fy2026q4/postprint/8k_index.html` · `logs/mu/fy2026q4/postprint/ex991.htm` · `logs/mu/fy2026q4/postprint/remarks.pdf` · `logs/mu/fy2026q4/postprint/price_2026-10-01_src1.<ext>` · `logs/mu/fy2026q4/postprint/price_2026-10-01_src2.<ext>` · `forecast/reports/mu_fy2026q4_SCORED.md`(+ 커밋 해시) | 확보 즉시 `forecast/scripts/mu_report/input_pins.yaml`에 **전체 SHA** 기록 → Codex 확인 후 E2-B 시작 |
| E2-C | `logs/mu/fy2026q4/postprint/fy26_10k.htm` | 동일 절차 → E2-C 시작 |

**이해관계 확인 레코드 (rev-4, J-2)** — `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`

```yaml
author: 김지원
ticker: MU
status: not_held        # 열거형 {not_held, held}
confirmed_at_kst: "<KST ISO>"
edition: ed1            # 빌드 대상 판과 같아야 한다
```

- Jiwon이 **판마다** 렌더 시작 전 24시간 안에 확인하고 기록한다. 빌더는 blob SHA와 읽은 시각을 감사 기록·실행 로그에 남긴다.
- 이 파일은 `forecast/inputs/`에 있어 **public 리포에 커밋된다**. 보유 상태 공시 자체가 목적이므로 이 점을 E4 승인 항목에 적는다.

**ed2 예약 입력 (역사적 밴드·피어 비교)** — 예약만 하고 경로는 아직 고정하지 않는다. §4-7 Q-1 규칙(정확 경로 + 전체 SHA, glob 금지)에 따라 **E2-C 착수 전 계획 개정으로 정확 경로를 고정**한다. 대상은 분할 조정 일별 종가, 과거 공시 원본(point-in-time TTM 분모), 피어별 규제 공시 원본, 피어 가격 2경로, 공식 환율이다. 피어 공시 원본의 좌표 규칙은 §7을 따른다.

- 예약 경로와 다른 이름으로 받은 파일은 **이름을 맞춘 뒤** 핀을 기록한다(allowlist에 새 경로를 즉석 추가하지 않는다). E2-B·E2-C allowlist = 이전 phase 목록 + 해당 phase 예약 경로.
- **금지(E2-A)**: 예약 경로 전부 · FY26 10-K · 가격 캡처 · RLE YAML의 post-print 값. E2-A는 post-print 슬롯을 `forecast/tests/fixtures/mu_report/`의 가짜 값으로만 채운다.

**접근 기록 (결정성)**

| 기록 | 경로 | 내용 | 커밋 |
|---|---|---|---|
| 감사 기록 | `forecast/reports/mu_report_fy2026q4_ed{N}_input_manifest.json` | `{path, sha256, phase, kind}` — **시각 없음**, 경로 기준 정렬, 중복 제거 → 같은 입력이면 바이트 동일 | **E4 커밋 후보** |
| 실행 로그 | `logs/_mu_report_runs/<run_id>.json` | 위 + `read_at` 시각·호출 순서 | 커밋 안 함(`logs/` gitignore) |

- G-20: 감사 기록의 모든 외부 입력이 해당 phase allowlist에 있고 SHA가 일치하며, E2-A 기록에 예약 경로가 **0건**. 감사 기록을 두 번 생성해 바이트 동일한지도 확인(결정성).

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
| **G-12c 이해관계 확인 (rev-4)** | 확인 레코드 존재 · `status == not_held` · `confirmed_at_kst`가 렌더 시작 전 24시간 이내 · `edition` == 빌드 판 · KO/EN 본문·PDF 푸터가 같은 레코드를 참조 · `disclaimer.conflict` 키가 표지·말미에, `disclaimer.conflict_short`가 PDF 각 페이지 푸터에 존재 | 중단(fail closed) |
| G-13 시각 요소 | 차트 8종(또는 ③′ 대체) 존재·참조 | 중단 |
| **G-13b 차트-표 동일성 (R-6)** | 모든 차트 series 점이 manifest fact(또는 lineage가 있는 derived fact)와 **값 일치**. 차트 전용 수치 금지. 히트맵 base 셀 == 본표 base P/E | 중단 |
| **G-14 출처·날짜 (R-7)** | 표·본문·캡션·각주·표지·일정 날짜의 **모든 숫자·날짜**가 fact_id 참조이거나 allowlist 리터럴(절 번호 등). 모든 fact가 URL·accession·SHA로 해석되는 `source_id`를 가짐. 계산 fact는 `lineage` 필수 | 중단 |
| **G-15 한/영 패리티 (Q-12)** | KO/EN 참조 로그 비교: 같은 위치(표 id·행·열 / placeholder 순번 / series·점 순번)가 **같은 fact_id**를 참조. fact의 value·unit·period·basis·label 일치. 보조: 정규화 숫자 토큰 다중집합 일치. 의도된 차이는 §4-6 allowlist | 중단 |
| G-16 캡션 | 번호·단위·출처·기준일·회계기준 5요소 | 중단 |
| G-17 라벨 | FY/FQ + 달력 병기 · 주수 각주(FY26 두 레이어 모두) · A-8K/A-10K/PREREG_A/RLE/CITED · 컨센서스 `UNAVAILABLE` | 중단 |
| G-17b 컨센서스 비교 금지 | FY27 컨센서스 fact를 입력으로 하는 gap·beat/miss·색상·방향 문장 0건 | 중단 |
| **G-22 peer-actual-only (rev-4, ed2)** | 모든 피어 숫자가 규제 공시 실제치 또는 그 lineage 계산 · 추정·컨센서스·목표가 필드 0개 · 가격일·기간 종료일·통화·회계기준 명시 · 배수 분자·분모의 범위 일치(세그먼트 실제치와 전사 시가총액 결합 금지) · 원문 좌표로 역추적 가능(§7) | 중단 |
| **G-22b peer-period-alignment (rev-4, ed2)** | TTM 종료일 차이가 120일을 넘는 셀이 비교 가능 값으로 렌더되면 실패 | 중단 |
| G-18 파일 위생 | 신규 텍스트 LF · NUL 0 · 행말 공백 0 · UTF-8 | 중단 |
| **G-19 브릿지 범위 (R-8)** | §4-6 제약 | 중단 |
| **G-20 입력 provenance (Q-1 · C-3)** | §4-7 감사 기록: allowlist·전체 SHA 일치 · E2-A 예약 경로 0건 · 2회 생성 바이트 동일 | 중단 |
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
| PDF (KO·EN) | 전 페이지 PNG 렌더 후 확인: 잘림·겹침·빈 페이지 0 · **브라우저 날짜 머리글·`file:///` 푸터 문자열 0**(SK 2026-09-13 재발 방지) · 한글 폰트 임베드 · `%%EOF` · **(rev-4) 모든 쪽 푸터 `현재쪽/전체쪽` == PDF 실제 쪽수 == manifest `document.total_pages` · 목차 쪽 번호·앵커 역검증** |
| XLSX | 수식 있으면 재계산 또는 cached value 존재 확인 · 오류 셀(`#REF!`·`#DIV/0!`·`#VALUE!`·`#N/A`) 0 · 시트마다 단위·출처·as-of 행 |
| HTML | 외부 네트워크 의존 0(`http(s)://` 스크립트·스타일·이미지 0 — 출처 링크 `<a href>`는 허용) · 내부 앵커·이미지 참조 해석 · 5MB 미만 |
| MD | 로컬 링크 해석 · 표마다 열 수 일치 |

- 🔴 E3에서 Claude는 NUL 스캔·pytest·SHA·G-13b·G-15를 **독립 재실행**한다. 보고서의 "PASS" 기재는 증거로 취급하지 않는다.

---

## §6. 워크플로 · 입력 게이트 · 커밋

| 단계 | 주체 | 산출 | 종료 조건 |
|---|---|---|---|
| P0·P1 | Claude | 본 PLAN | rev-3 작성 ✅ |
| P2 | Codex | `REVIEW_CODEX_mu_report_plan_r3.md` | r2 미결 항목 판정 |
| P3 | Jiwon | — | D1–D9 확정 |
| E1 | Claude | `HANDOFF_CODEX_mu_report_exec.md` | 확정 계획 → 실행 지시. 수치 블록은 스크립트 생성 |
| E2-A | Codex | §2 D7 경로 | E2-A 대상 게이트(G-1·3·7·9·12·13·13b·14·15·16·18·20·21) |
| **E2-B 입력 게이트 (R-2)** | — | — | **4개 모두**: ① FQ4 FY26 8-K/EX-99.1 및 준비문 원본 확보 + SHA 기록 ② `forecast/reports/mu_fy2026q4_SCORED.md` 존재 + commit·SHA 기록 ③ 기준 주가 2경로 캡처 확보 ④ P3 승인 + E1 완료 · **(rev-4 채택 시) ⑤ rev-4 승인 + HANDOFF 부록(S5) 구현 완료 ⑥ J-2 확인 레코드(G-12c)**. ⑤가 ①–④보다 늦으면 E2-B를 rev-3대로 진행할지 Jiwon이 정한다 |
| E2-B | Codex | 제1판 | §5 전 게이트 |
| E3 | Claude | `REVIEW_CLAUDE_mu_report_output_rN.md` | 독립 재현 |
| E4 | Jiwon | 호스트 PowerShell 커밋 | 승인된 파일 목록(§2 D7 커밋 후보) + SHA 확인 후. **push는 별도 승인 — 리포 public** |
| E2-C 입력 게이트 | — | — | ① FY26 10-K 원본 확보 + `input_pins.yaml` 전체 SHA 기록 + Codex 확인 ② ed1이 E4(커밋)까지 완료 |
| E2-C | Codex | 제2판(`ed2`) 전체 산출물 | §5 전 게이트 + 8-K vs 10-K 차이표 |
| **E3-ed2** | Claude | `REVIEW_CLAUDE_mu_report_output_ed2_rN.md` | ed1과 **독립된** 재현 검토(ed1 결과 재사용 금지) |
| **E4-ed2** | Jiwon | 호스트 PowerShell 커밋 | ed2 파일 목록·SHA에 대한 **별도 승인**. ed1 승인이 ed2를 갈음하지 않는다 |

**R-10**: E2-A·E2-B·E2-C 모두 로컬 생성까지. add/commit은 E4(ed1)·E4-ed2에서만, 각각 Jiwon 승인 후. **push는 판별로 별도 승인**(리포 public).

**Jiwon 요청 목록 (sandbox는 sec.gov·시세 사이트 불가)**

1. 프린트 직후: FQ4 FY26 8-K + EX-99.1 + 준비문 PDF (UA `Jiwon Sea <SEC UA 연락처>`) → `logs/mu/fy2026q4/postprint/` (rev-4.3)
2. 2026-10-01 Nasdaq 종가 2경로 캡처(날짜·시각 포함)
3. 10-K 접수 시 원본 htm
4. (선택) FY27 컨센서스 캡처 — 표시 전용
5. (선택) FQ4-24 이후 과거 준비문 PDF — 차트 ③ 기간 확장용
6. **(rev-4) 판마다 렌더 직전 24시간 안에** MU 보유 상태 확인 → `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`
7. **(rev-4, ed2)** 피어 규제 공시 원본 · 피어·MU 가격 2경로 · 공식 환율 · MU 일별 종가 — 정확 경로는 E2-C 착수 전 계획 개정으로 고정

---

## §7. 스코프 잠금

- 금지: FROZEN·MU 프로파일·엔진·빌더 수정 · 표기 없는 밸류에이션 배선 · `valuation_bridge.py` 호출 · 경쟁사 병렬 **예측·가치평가** 모델링 · 투자의견·목표주가 · BU/HBM 수요 모델 · 채점 재계산 · 언어적 구간의 숫자화.
- **피어 비교 예외 (rev-4, J-1, ed2)**: 피어의 규제 공시 실제치와 같은 기준일 시장가격만 사용한 운영·trailing 배수 비교표는 허용한다. 피어 추정치·컨센서스·목표가·리서치사 조정치는 금지한다. 회사별 기간 종료일·회계연도 주수·보고통화·회계기준·가격 기준일을 표시하고, 범위나 기간을 맞출 수 없는 셀은 `UNAVAILABLE_FOR_COMPARISON`, 비양수 분모는 `N/M`으로 둔다. 세그먼트 실제치와 전사 시가총액을 섞지 않는다.
  - **후보와 규칙**: 규칙 = 최근 회계연도 매출의 과반이 메모리(DRAM·NAND·HBM)이고, 규제 공시로 실제치 3표·주식수를 재현할 수 있어야 한다. 후보 SK hynix · SanDisk · Kioxia Holdings · Nanya Technology는 전사 비교 후보다. Samsung Electronics는 메모리 세그먼트 운영 지표만 조건부로 쓰고 배수에는 넣지 않는다. 후보마다 `포함 / 제외 / 운영 지표만`과 사유를 manifest 부록에 남긴다. 원본을 다 갖추지 못하면 다른 제공자의 추정치로 채우지 않고 `UNAVAILABLE_FOR_COMPARISON`으로 둔다.
  - **가격**: 시장별 2026-10-01 정규장 종가(Nasdaq·KRX·TSE·TWSE)를 쓰고, 개장 여부는 입력 게이트 전에 공식 거래소 캘린더로 확인한다. 휴장하면 전일 값으로 임의 대체하지 않고 Jiwon이 정한다. 각 가격 fact에 `exchange`·`local_trade_date`·`close_time_local`·`timezone`·`captured_at_kst`·`source_id`를 기록한다. 아시아 시장 종가가 같은 날 Nasdaq 종가보다 먼저 확정된다는 점을 캡션에 적는다.
  - **기간·통화·회계**: 기준일 당시 공개된 최신 TTM을 쓴다. 배수는 원통화로 계산하고, 절대액을 한 통화로 보여 줄 때만 같은 기준일 공식 환율을 쓰며 원통화도 함께 둔다. US GAAP·K-IFRS 등을 임의로 정상화하지 않는다.
  - **비영문 공시 좌표**: `source_id = {regulator, document_id, filing_date, url, local_path, sha256, language}`. fact마다 `source_coordinate`에 원문 표·주석명과 원문 계정명, 쪽 또는 HTML anchor, (있으면) XBRL tag·context를 기록한다(DART·EDINET·MOPS). KO/EN 표시명은 파생 라벨일 뿐 lineage 좌표가 아니다.
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
7. RLE 순현금은 자사주·인수·차입변동 전이며 SCA 예치금을 **조정하지 않은** 값이다. SCA 조정 순현금과 `EV_adj`는 예치금 공시값이 있을 때만 존재한다. 회사 발표 순현금(제한현금 포함)과 정의가 다르다.
8. FY26A는 53주 — 배수·성장률의 분모가 부풀어 있다(`×52/53` 근사 병기).
9. (rev-4) P/B는 FY26A-8K 기말 자본 기준 trailing 값 하나뿐이다. RLE 기간 P/B와 과거 배수 밴드(ed2 전)는 없다.
10. (rev-4) 재고일수는 회사 공시 재고로 계산한 FY23A–FY26A-8K 값이다. 업계 재고 수치는 없다.
11. (rev-4) 제1판에는 피어 비교가 없다. 피어 비교는 공시 실제치만으로 제2판에 예약돼 있다.

---

## §9. Codex 재검토 요청 (r4)

rev-4의 변경은 §R3 합의 결과를 옮긴 것뿐이다. rev-3에서 PASS한 항목은 바꾸지 않았다. 아래를 판정해 달라(`forecast/REVIEW_CODEX_mu_report_plan_r4.md`):

1. §R3·부록 B-2가 합의(`REVIEW_CLAUDE_mu_report_survey_r2.md` §3)와 한 건도 어긋나지 않는지
2. ed1 추가 6개가 새 외부 입력 없이 기존 fact·게이트로 닫히는지: §4-3 재고일수, §4-5 trailing P/B·시장 데이터 박스, D9·§4-7·G-12c, G-21 쪽 번호·목차
3. §6 E2-B 입력 게이트 ⑤·⑥과 "rev-4 미승인 시 rev-3로 진행" 규칙이 모순이 없는지
4. §7 피어 예외와 G-22·G-22b가 J-1 범위를 넘지 않는지, 그리고 ed2 예약 입력을 정확 경로 없이 둔 것이 Q-1 규칙과 충돌하지 않는지
5. 공개 리포 관점에서 부록 B에 원문 인용·발행사명·조사 자료 수치가 0건인지

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

## 부록 B. 셀사이드 구성 조사 (rev-4)

> 조사 자료의 투자의견·목표주가·추정치·컨센서스·배수 숫자는 싣지 않는다. 원문 인용은 없다. 발행사명·파일명은 `logs/sellside_survey/mu_fy2026q4/_ledger.md`(gitignore, SHA `7dca05e5…5c7b5c`)에만 있다. 셀의 `p`는 조사 자료의 쪽 번호다.

### B-0. 리포트 대장 (유형만)

| ID | 구분 | 발행사 유형 | 발행 | 유형 | 쪽 | 언어 | 확보 경로 유형 | 원본 SHA-256 |
|---|---|---|---|---|---|---|---|---|
| R-01 | 표본 · MU | 국내 증권사 | 2026-06 | 실적 리뷰(해외 종목) | 8 | ko | 공개 PDF | `96097844e7ba31291a2e7914f0de6e0fcb2f178e5243ae18f5463de89a79749c` |
| R-02 | 표본 · MU | 국내 증권사 | 2026-06 | 실적 리뷰(AI 요약) | 2 | ko | 공개 웹 → 인쇄 PDF | `b0edbb5cf9fecb9029bccf5d9733779d9912f4bab3093c573dd80540ba76e5e2` |
| R-03 | 표본 · 국내 피어 | 국내 증권사 | 2026-07 | 실적 리뷰 | 8 | ko | 공개 웹 → 인쇄 PDF | `32a8e684313db3fb30bad457d4f3584a1055965f308b668eac1cbf8e9d38c185` |
| R-04 | 표본 · 국내 피어 | 국내 증권사 | 2026-09 | 업데이트(추정 변경) | 8 | ko | 리서치 포털 공개 PDF | `dfdb8267e1accaa5be97aacca2ada4aaffd83cd1136d5371b14424ceaacbb555` |
| R-05 | 표본 · 업종 | 국내 증권사 | 2026-05 | 업종 전망 | 9 | ko | 공개 PDF | `47173a136b758eae6bf5fbc9737eed4874d98c755b8b0337f57b966d9e6d13ec` |
| R-06 | 표본 · 해외 | 해외 은행 리서치 | 2025-04 | 기업 요약 | 7 | en | 공개 PDF | `c841e658d2f246a0a96143ec0c0b5145cd2f4f27040750ec6bc7db1729440fd9` |
| R-07 | 표본 · 해외 | 해외 은행 리서치 | 2026-04 | 업종 | 13 | en | 공개 PDF | `8fd05bc755f64aef1d8cf0165e06b6a18fc6da0b2c7537efa0f864718965c010` |
| R-08 | 표본 · 해외 | 중국 증권사 | 2024-10 | 개시 | 39 | zh | 플랫폼 재배포(J-3) | `ac256dfb4e1edc245cb6ec2cae9a3daee1a4bd60a935b3403fc1aaa624a012ec` |
| R-09 | 표본 · 해외 | 중국 증권사 | 2026-05 | 개시·심층 | 31 | zh | 플랫폼 재배포(J-3) | `521dc1903810f0b64970dafdafdc2d19584279e170a4b00942c871c6d70d9a52` |
| R-10 | 표본 · 해외 | 국내 증권사 영문판 | 2026-06 | 기업 업데이트 | 8 | en | 공개 IR PDF | `2b548f5a3fb786d962d331ec1b7d79752517940149b40eb71709218d283bdd38` |
| R-11 | 표본 · 해외 | 미국 리서치 기관 | 2026-06 | 프리뷰 | 10 | en | 공개 웹 → 인쇄 PDF | `11722d649fb2361672200380b05cdfe784c94fae3b81814446b5ec79dc8b6058` |
| R-12 | 표본 · 해외 | 일본 증권사 | 2026-03 | 실적 해설(웹) | 3 | ja | 공개 웹 → 인쇄 PDF | `b42a38e33429d44ed51c01bb32b8db58195842dceb5b96556e1011d581dd67da` |
| R-13 | 표본 · 해외 | 일본 운용사 | 2026-06 | 시장 코멘트 | 2 | ja | 공개 PDF | `67459d3d2ef8c229752f26300ffdefcfb21dcfb8546ad01587b953f9262aa576` |
| R-14 | 표본 · 해외 | 대만 증권사 | 2025-09 | 콜 해설(웹) | — | zh-TW | 공개 웹 → txt(인쇄 차단) | `5a14f06c6abe2ac0022c4cca65890ab4f1a04a072de23fd8187c919f480bebd3` |
| G-01 | 형식 기준 | 국제 자격 단체 | 2024-07 | 가이드라인 | 2 | en | 공개 PDF | `1ea89045343e1a1076393cc5fc868a7d7c658df9396780230bbd10e3623180ed` |
| G-02 | 형식 기준 | 미국 리서치 기관 | 2014-09 | 해설서 | 2 | en | 공개 PDF | `2e1b89096f760148c8651fe04f6ae0de88ab8491c210be2f0e734fe605d42d45` |
| X-01 | 표본 외 | 해외 은행 | — | 매크로 전략 | 3 | ko | 고객 배포(J-4) | `6bd5c7684cd670d01168b2c151aa6c4be7a10a1bcfde0e6937a5cddd83aa40ab` |
| X-02 | 표본 외 | 해외 운용사 | — | 매크로 | 3 | ko | 고객 배포(J-4) | `bc6630470040aa5d2a337496d50bdd9334f914e4a0e2d003f8d4b18a6e11988e` |

- 빈도 표본 = R-01~R-14(n=14). G-01·G-02는 형식 기준 대조용, X-01·X-02는 표본 외 참고(J-4)라 빈도에서 뺀다.
- 두 매크로 자료(X)는 이 계획의 어떤 요소 판정에도 쓰지 않았다.

### B-1. 구성 요소 행렬 (합의본 = Codex C1-a 수정본, SHA `d2c6cfce…b88003`)

판독 규칙: 차트는 수치 축이나 정량 인코딩이 있는 시각화만 센다(사진·개념도·로드맵·표 제외). 막대+선 혼합 차트는 전체 수에서 1개, 유형별로는 각각 1개로 센다. 재무제표 연도 수는 3표 형식만 `A n+E m`으로 적는다. 밸류에이션 방법은 목표가 산정에 쓰였으면 `적용`, 표에 배수만 제시했으면 `나열`이다. Claude 독립 행렬(`_matrix.md` `67c294ce…f776`)은 교차검증 기록으로 `logs/`에 남긴다.

| # | 요소 | R-01 | R-02 | R-03 | R-04 | R-05 | R-06 | R-07 | R-08 | R-09 | R-10 | R-11 | R-12 | R-13 | R-14 | 빈도/중앙값 |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 표지: 투자의견 | - | - | 표p1 | 표p1 | 표p2,p7,p8 | 표p1 | 표p1 | 표p1 | 표p1 | 표p1 | - | - | - | - | 8/14 |
| 2 | 표지: 목표주가 | 표p1(외부 평균) | 표p1(외부 평균) | 표p1 | 표p1 | 표p2,p7,p8 | 표p1 | 표p1 | 표p1 | - | 표p1 | - | - | - | - | 9/14 |
| 3 | 표지: 현재가 | 표p1 | 표p1 | 표p1 | 표p1 | 표p2,p7,p8 | 표p1 | 표p1 | 표p1 | 표p1 | 표p1 | 표p7 | - | - | - | 11/14 |
| 4 | 표지: 상승여력 | - | - | - | 표p1 | 표p2 | - | - | 표p1 | - | 표p1 | - | - | - | - | 4/14 |
| 5 | 표지: 시장 데이터 박스 | 표p1 | 표p1 | 표p1 | 표p1 | 표p7,p8 | 표p1 | 표p1 | 표p1 | 표p1 | 표p1 | - | - | - | - | 10/14 |
| 6 | 표지: 핵심 재무 요약표 | 표p1,p3,p6 | 표p1,p2 | 표p1 | 표p1 | 표p2 | 표p2 | - | 표p1 | 표p1 | 표p1 | - | - | - | - | 9/14 |
| 7 | 표지: 요약 불릿 | 문p1 | 문p1 | 문p1 | - | 문p2 | - | 문p1 | 문p1 | 문p1 | 문p1 | - | - | 문p1 | - | 8/14 |
| 8 | 표지: 작성자·연락처 | 문p1 | - | 문p1 | 문p1 | 문p1 | 문p1 | 문p1 | 문p1 | 문p1 | 문p1 | - | - | - | - | 9/14 |
| 9 | 실적 리뷰: 실적 vs 자체추정 vs 컨센서스 vs 가이던스 표 | 표p1,p2 | 표p1 | 표p2 | - | - | - | - | - | - | - | 표p2 | 문p1,p2 | - | 문(txt) | 4/14(표 기준) |
| 10 | 실적 리뷰: 차이 원인 분석 | 문p1,p2 | 문p1 | 문p1 | - | - | - | - | - | 문p25 | - | 문p2,p3 | 문p1-p3 | 문p1 | 문(txt) | 7/14 |
| 11 | 실적 리뷰: 다음 분기 가이던스 해석 | 문p1,p2 | 문p1 | 문p1 | - | - | - | - | - | 문p25 | - | 문p3 | 문p1,p3 | 문p1 | 문(txt) | 7/14 |
| 12 | 실적 리뷰: 콜 핵심 문답 | 문p4,p5 | 문p1 | - | - | - | - | - | - | - | - | - | - | - | - | 2/14 |
| 13 | 추정: 추정치 변경표 | - | - | 표p2,p3 | 표p3 | - | - | 표p3 | - | - | 표p3 | 표p7 | - | - | - | 5/14 |
| 14 | 추정: 분기 추정 | - | - | 표p2-p4 | 표p4,p5 | - | - | - | 표p26,p27 | - | 표p2 | 표p7 | - | - | - | 5/14 |
| 15 | 추정: 연간 추정 | - | - | 표p1-p3,p6 | 표p1,p4,p5,p7 | 표p2,p7,p8 | 표p2 | 문p6,표p7 | 표p25-p29,p38 | 표p27,p30 | 표p2,p5 | 표p7 | - | - | - | 9/14 |
| 16 | 추정: 사업부·제품별 추정 | - | - | 표p2-p4 | 표p3-p5 | - | - | 표p3 | 표p25-p28,p38 | 표p27 | 표p2 | 표p7 | - | - | - | 7/14 |
| 17 | 추정: 가정 표 | - | - | 표p4 | 표p5 | - | - | - | 표p25,p38 | 문p27 | 표p2 | - | - | - | - | 4/14(표 기준) |
| 18 | 밸류에이션: 방법 P/E | 나열p6 | 나열p1,p6 | 나열p1,p6 | 나열p1,p2,p7 | 나열p2,p7,p8 | 나열p2 | 적용p7 | 적용p30,p31 | 나열p1,p28,p30 | 나열p1,p5 | 문p6 | - | 문p1 | - | 11/14 |
| 19 | 밸류에이션: 방법 EV/EBITDA | 나열p6 | - | 나열p1,p6 | 적용p2 | - | 나열p2 | - | 나열p32,p33 | 나열p30 | 나열p1,p5 | - | - | - | - | 8/14 |
| 20 | 밸류에이션: 방법 P/B | 나열p6 | - | 적용p1,p2 | 나열p1,p2,p7 | 나열p2,p3 | 적용p1,p2 | - | 나열p32,p33 | 나열p30 | 적용p3,p5 | - | - | - | - | 8/14 |
| 21 | 밸류에이션: 방법 DCF | - | - | - | - | - | - | - | 적용p34 | - | - | - | - | - | - | 1/14 |
| 22 | 밸류에이션: 방법 SOTP | - | - | - | 적용p2 | - | - | - | 적용p30,p31 | - | - | - | - | - | - | 2/14 |
| 23 | 밸류에이션: 목표 배수 근거 | - | - | 문p1,p2 | 문p2 | 문p3,p7,p8 | 문p1 | 문p6,p7 | 문p30-p34 | - | 문p3 | - | - | - | - | 7/14 |
| 24 | 밸류에이션: 민감도 | - | - | - | - | - | - | - | - | - | - | - | - | - | - | 0/14 |
| 25 | 밸류에이션: 역사적 밴드 차트 | - | - | 차p2 | 차p2 | 차p3 | - | - | 차p32,p33 | - | - | - | - | - | - | 4/14 |
| 26 | 밸류에이션: 피어 비교표 | - | - | - | 표p2 | 표p2 | - | 표p3,p7 | 표p31 | 표p28 | 표p3 | - | - | - | - | 6/14 |
| 27 | 산업: DRAM/NAND 가격 | 문p1,p2 | 문p1 | 표p4 | 표p3,p5 | 문p4,p8 | 문p1 | - | 차·문p24-p28 | 문p25,p27,p28 | 문p1,p2 | 문p3,p9 | 문p2,p3 | - | 문(txt) | 12/14 |
| 28 | 산업: 수급 | 문p1,p2,p4,p5 | 문p1 | 문p1,p4 | 문p1,p4,p5 | 문p2,p4,p5 | 문p1 | 문p5-p7 | 문p5-p29,p35 | 문p14-p28 | 문p1,p2 | 문p2-p4,p8,p9 | 문p3 | 문p1 | 문(txt) | 14/14 |
| 29 | 산업: 재고 | - | - | 표p6 | 표p7 | - | 표p2 | 문p7 | 문p24-p27 | 차·문p12,p13,p28 | 표p5 | - | - | - | - | 7/14 |
| 30 | 산업: 캐파 | 문p2,p4,p5 | 문p1 | 차·표p4 | 문p5,p6 | 문p2,p5,p6 | 문p1 | 문·차p5-p7 | 표·차p4,p15,p21,p25 | 문p7,p14-p28 | 문p1 | 문p3,p4,p8 | 문p3 | - | 문(txt) | 13/14 |
| 31 | 산업: 경쟁 구도 | 문p1,p4,p5 | 문p1 | 문p1,p4 | 문p1,p2,p6 | 문p3-p5 | 문p1 | 문p3,p5-p8 | 문p3-p24,p31,p35 | 문p4-p28 | 문p1,p3 | 문p5,p9 | 문p3 | 문p1 | 문(txt) | 14/14 |
| 32 | 재무제표: 손익(실적/추정 연도 수) | 표p3,p6 A5+E0 | - | 표p6 A2+E3 | 표p7 A1+E3 | - | - | - | 표p38 A1+E3 | 표p30 A1+E3 | 표p5 A1+E3 | - | - | - | - | 6/14 |
| 33 | 재무제표: 재무상태(연도 수) | 표p6 A5+E0 | - | 표p6 A2+E3 | 표p7 A1+E3 | - | - | - | 표p38 A1+E3 | 표p30 A1+E3 | 표p5 A1+E3 | - | - | - | - | 6/14 |
| 34 | 재무제표: 현금흐름(연도 수) | 표p6 A5+E0 | - | 표p6 A2+E3 | 표p7 A1+E3 | - | - | - | 표p38 A1+E3 | 표p30 A1+E3 | 표p5 A1+E3 | - | - | - | - | 6/14 |
| 35 | 재무제표: 주요 비율 | 표p6 | 표p1,p2 | 표p1,p6 | 표p1,p7 | 표p2,p7,p8 | 표p2 | 표p7 | 표p38 | 표p30 | 표p1,p5 | 표p2,p7 | 표p1,p2 | - | - | 12/14 |
| 36 | 재무제표: 주당 지표 | 표p1,p3,p6 | 표p1 | 표p1,p6 | 표p1,p7 | 표p2,p7,p8 | - | - | 표p38 | 표p30 | 표p1,p5 | 표p2,p7 | 표p1 | 차p1 | - | 11/14 |
| 37 | 리스크·촉매: 하방 리스크 | 문p2 | - | 문p1 | 문p1 | 문p7,p8 | 문p1 | 표p7 | 문p35 | 문p28,p29 | 문p1,p6 | 문p8 | 문p3 | 문p1 | - | 12/14 |
| 38 | 리스크·촉매: 상방 리스크 | 문p1,p2 | 문p1 | 문p1 | 문p1 | 문p2,p7,p8 | 문p1 | 표p7 | 문p1,p5,p32 | 문p1,p25-p28 | 문p1 | 문p2-p7 | 문p3 | 문p1 | 문(txt) | 14/14 |
| 39 | 리스크·촉매: 촉매 일정 | 문p4,p5 | - | 문p1 | 문p1,p6 | 문p2,p7,p8 | - | 표p7 | 표p32,p36 | 문p25,p26 | 문p1,p4 | 문p2,p8 | - | 문p1 | - | 10/14 |
| 40 | 시각 자료: 차트 수 | 3 | 3 | 7 | 3 | 16 | 2 | 6 | 45 | 12 | 2 | 5 | 0 | 2 | 0 | 중앙값 3 |
| 41 | 시각 자료: 유형 막대 | 2(p2) | 2(p2) | 4(p4,p5) | 0 | 6(p4,p6) | 0 | 1(p5) | 25 | 7(p11,p12,p19,p21,p22) | 0 | 2(p5) | 0 | 0 | 0 | 8/14; 중앙값 1.5 |
| 42 | 시각 자료: 유형 선 | 2(p1,p2) | 3(p1,p2) | 5(p2,p4,p7) | 3(p1,p2,p8) | 11(p3,p4,p7-p9) | 2(p1,p3) | 3(p5,p6) | 20 | 7(p11-p13) | 2(p1,p6) | 3(p3,p9) | 0 | 2(p1) | 0 | 12/14; 중앙값 3 |
| 43 | 시각 자료: 유형 팬 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/14; 중앙값 0 |
| 44 | 시각 자료: 유형 히트맵 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0/14; 중앙값 0 |
| 45 | 시각 자료: 유형 밴드 | 0 | 0 | 2(p2) | 1(p2) | 2(p3) | 0 | 0 | 4(p32,p33) | 0 | 0 | 0 | 0 | 0 | 0 | 4/14; 중앙값 0 |
| 46 | 시각 자료: 캡션 관행(출처·기준일) | 캡p1,p2 | 캡p1,p2 | 캡p2-p7 | 캡p1,p2,p6,p8 | 캡p3-p9 | 캡p1-p3 | 캡p1-p7 | 캡p3-p38 | 캡p4-p30 | 캡p1-p6 | 캡p2-p9 | - | 캡p1 | 문(txt) | 13/14 |
| 47 | 고지: 면책 | 문p7,p8 | 문p2 | 문p8 | 문p8 | 문p9 | 문p1,p3-p7 | 문p9-p13 | 문p39 | 문p31 | 문p6-p8 | 문p9 | 문p3 | 문p1,p2 | 문(txt) | 14/14 |
| 48 | 고지: 이해관계 고지 | 문p7 | - | 문p8 | 문p8 | 문p9 | 문p3,p4 | 문p10 | 문p39 | 문p31 | 문p6 | - | - | - | - | 9/14 |
| 49 | 고지: 등급 체계 설명 | - | - | 문p8 | 문p8 | 문p9 | 문p3 | 문p9 | 문p39 | 문p31 | 문p6 | - | - | - | - | 8/14 |
| 50 | 고지: 총 쪽수 | 8 | 2 | 8 | 8 | 9 | 7 | 13 | 39 | 31 | 8 | 10 | 3 | 2 | 웹/txt | 중앙값 8쪽 |

**추가 요소**

| # | 추가 요소 | R-01 | R-02 | R-03 | R-04 | R-05 | R-06 | R-07 | R-08 | R-09 | R-10 | R-11 | R-12 | R-13 | R-14 | 빈도 |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 51 | 목차 | - | - | - | - | - | - | - | 표p2 | 표p2 | - | - | - | - | - | 2/14 |
| 52 | 핵심 도표 모음 또는 도표 목차 | - | - | - | - | - | - | - | 표p3,p4 | 표p3 | - | - | - | - | - | 2/14 |
| 53 | 산포도 | - | - | - | - | - | - | 차p1,p2,p4 | - | - | - | - | - | - | - | 1/14(3개) |
| 54 | 컨센서스 수정 이력 표 | - | - | - | - | - | - | - | - | - | - | 표p7 | - | - | - | 1/14 |
| 55 | 회사 개요·사업 설명 | 문p1 | 문p1 | 문p1 | 문p1 | 문p2 | 문p1 | 문p5-p8 | 문p5-p24,p36 | 문p4-p10 | 문p1 | 문p2-p5 | 문p1 | 문p1 | 문(txt) | 14/14 |

### B-2. 합의 분류표

| # | 요소 | 빈도(C1-a) | 분류 | 판 | rev-4 위치 / 사유 |
|---:|---|---|---|---|---|
| 1 | 표지: 투자의견 | 8/14 | ⛔ | — | D3 |
| 2 | 표지: 목표주가 | 9/14 | ⛔ | — | D3 · §4-5 금지 필드 |
| 3 | 표지: 현재가 | 11/14 | ✅ | — | §3 표지 · §4-5 기준 주가 |
| 4 | 표지: 상승여력 | 4/14 | ⛔ | — | D3(목표주가 없음) |
| 5 | 표지: 시장 데이터 박스 | 10/14 | ➕ | ed1 | §3 표지 · §4-5 시장 데이터 박스(최소) |
| 6 | 표지: 핵심 재무 요약표 | 9/14 | ✅ | — | §3 표지 핵심 수치표 |
| 7 | 표지: 요약 불릿 | 8/14 | ✅ | — | §3 표지 3줄 관찰 |
| 8 | 표지: 작성자·연락처 | 9/14 | ✅ / ⛔ | — | 작성자 D9 / 연락처 비공개(기본) |
| 9 | 실적 리뷰: 실적 vs 자체추정 vs 컨센서스 vs 가이던스 표 | 4/14(표 기준) | ✅ | — | §3 3절 · §4-1 · G-2·G-3f |
| 10 | 실적 리뷰: 차이 원인 분석 | 7/14 | ✅ | — | §3 3절·7절 |
| 11 | 실적 리뷰: 다음 분기 가이던스 해석 | 7/14 | ✅ | — | §3 4절 · §4-4 |
| 12 | 실적 리뷰: 콜 핵심 문답 | 2/14 | ❓ | — | 준비문 요지로 대체(Q&A 원문 없음) |
| 13 | 추정: 추정치 변경표 | 5/14 | ⛔ | — | 컷오프·방법이 다른 레이어 — §3 12절 경로 비교표 유지 |
| 14 | 추정: 분기 추정 | 5/14 | ✅ | — | D2 |
| 15 | 추정: 연간 추정 | 9/14 | ✅ | — | D2 |
| 16 | 추정: 사업부·제품별 추정 | 7/14 | ⛔ | — | §7 BU/HBM 수요 모델 금지 |
| 17 | 추정: 가정 표 | 4/14(표 기준) | ✅ | — | §3 8절 · §4-4 |
| 18 | 밸류에이션: 방법 P/E | 11/14 | ✅ | — | §4-5 암시 P/E |
| 19 | 밸류에이션: 방법 EV/EBITDA | 8/14 | ✅ | — | §4-5 EV/EBITDA |
| 20 | 밸류에이션: 방법 P/B | 8/14 | ➕ | ed1 | §4-5 trailing P/B 보조 행 |
| 21 | 밸류에이션: 방법 DCF | 1/14 | ⛔ | — | D3 |
| 22 | 밸류에이션: 방법 SOTP | 2/14 | ⛔ | — | D3 · §7 |
| 23 | 밸류에이션: 목표 배수 근거 | 7/14 | ⛔ | — | D3 |
| 24 | 밸류에이션: 민감도 | 0/14 | ✅ | — | §3 8절·9절 · ⑦ · G-13b |
| 25 | 밸류에이션: 역사적 밴드 차트 | 4/14 | ➕ | ed2 | §3 9절 일별 밴드(point-in-time TTM) |
| 26 | 밸류에이션: 피어 비교표 | 6/14 | ➕ | ed2 | §7 피어 예외(J-1) · G-22·G-22b |
| 27 | 산업: DRAM/NAND 가격 | 12/14 | ✅ | — | §3 5절 범주형 표 |
| 28 | 산업: 수급 | 14/14 | ✅ | — | §3 2·4·5절 |
| 29 | 산업: 재고 | 7/14 | ➕ / ❓ | ed1 | §4-3 회사 재고일수 / 업계 재고 입력 없음 |
| 30 | 산업: 캐파 | 13/14 | ✅ | — | §3 · §4-3 순 capex |
| 31 | 산업: 경쟁 구도 | 14/14 | ✅ | — | §3 1·2·5절 정성 서술. 경쟁사 수치는 피어 표로만(G-14) |
| 32 | 재무제표: 손익(실적/추정 연도 수) | 6/14 | ✅ | — | §4-3 |
| 33 | 재무제표: 재무상태(연도 수) | 6/14 | ✅ | — | §4-3 |
| 34 | 재무제표: 현금흐름(연도 수) | 6/14 | ✅ | — | §4-3 |
| 35 | 재무제표: 주요 비율 | 12/14 | ✅ | — | §4-3 |
| 36 | 재무제표: 주당 지표 | 11/14 | ✅ | — | §4-3 · §4-5 |
| 37 | 리스크·촉매: 하방 리스크 | 12/14 | ✅ | — | §3 2·10절 |
| 38 | 리스크·촉매: 상방 리스크 | 14/14 | ✅ | — | §3 2절 |
| 39 | 리스크·촉매: 촉매 일정 | 10/14 | ✅ | — | §3 11절 상태·source_id |
| 40 | 시각 자료: 차트 수 | 중앙값 3 | ✅ | — | 차트 8종 · G-13 |
| 41 | 시각 자료: 유형 막대 | 8/14; 중앙값 1.5 | ✅ | — | ①②③⑥⑧ |
| 42 | 시각 자료: 유형 선 | 12/14; 중앙값 3 | ✅ | — | ①③′④⑤⑧ |
| 43 | 시각 자료: 유형 팬 | 0/14; 중앙값 0 | ✅ | — | ⑤ |
| 44 | 시각 자료: 유형 히트맵 | 0/14; 중앙값 0 | ✅ | — | ⑦ · G-13b |
| 45 | 시각 자료: 유형 밴드 | 4/14; 중앙값 0 | ➕ | ed2 | #25와 동일 |
| 46 | 시각 자료: 캡션 관행(출처·기준일) | 13/14 | ✅ | — | G-16 캡션 5요소 |
| 47 | 고지: 면책 | 14/14 | ✅ | — | D9 · G-12b |
| 48 | 고지: 이해관계 고지 | 9/14 | ➕ | ed1 | D9 `disclaimer.conflict` · G-12c |
| 49 | 고지: 등급 체계 설명 | 8/14 | ⛔ | — | D3(등급 없음) |
| 50 | 고지: 총 쪽수 | 중앙값 8쪽 | ➕ | ed1 | G-21 쪽 번호 · manifest `document.total_pages` |
| 51 | 목차 | 2/14 | ➕ | ed1 | §3 목차 |
| 52 | 핵심 도표 모음 또는 도표 목차 | 2/14 | ⛔ | — | 8개 차트 재게재는 중복 — 목차로 충분 |
| 53 | 산포도 | 1/14(3개) | ⛔ | — | 의미 있는 축에 피어 추정치 필요 — J-1 범위 밖 |
| 54 | 컨센서스 수정 이력 표 | 1/14 | ⛔ | — | D6 · G-17b 충돌 |
| 55 | 회사 개요·사업 설명 | 14/14 | ✅ | — | §3 1·5절 |

### B-3. 교차검증 기록

| 문서 | SHA-256 |
|---|---|
| `forecast/HANDOFF_CODEX_mu_report_survey_r4.md` | `9bc9832ae33df578e11298b4612cc8e7761214382a6c32736e58f3e2d0b35e92` |
| `forecast/REVIEW_CODEX_mu_report_survey_r1.md` | `ae00afd2ab168627eaedc83489f0389842bbb2bc122b0c1a975d67ec0232762a` |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r1.md` | `f6bf58960ff59dec333d515bbb78079bd3bf4bbe5fa737f415c68d41e070e14a` |
| `forecast/REVIEW_CODEX_mu_report_survey_r2.md` | `0f263d02a4e2e4f6d735b8fa3298eba99c4e7e2a3c6a674c18c75aab037d6c91` |
| `forecast/REVIEW_CLAUDE_mu_report_survey_r2.md` | `95a13a2f9f2ec5a02d7eff4f26cc40d9010df3ef6af0be941432a4d5e1f35336` |
| `logs/sellside_survey/mu_fy2026q4/_matrix_codex.md` (C1-a 수정본) | `d2c6cfcee10586f7ebfa458e64e28a950e8c55c043537c32ef7f659fc3b88003` |
| `logs/sellside_survey/mu_fy2026q4/_matrix.md` (Claude 봉인본) | `67c294cecc0700d439db2dd60e6c91b0b463c9fd1fffd52b7918756dbc02f776` |

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
