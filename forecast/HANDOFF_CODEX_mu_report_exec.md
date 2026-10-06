# HANDOFF — Codex 실행 지시: MU FY2026 Q4 리서치 리포트 (E1 → E2-A)

> 작성 2026-09-27 KST · 작성 Claude (E1) · 실행 Codex (E2) · 승인 Jiwon
> 🔴 **권위 문서는 계획이다**: `forecast/PLAN_mu_report_fy2026q4.md` **rev-3**, sha256 `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324`. 이 핸드오프와 계획이 다르면 **계획이 이긴다** — 차이를 발견하면 실행을 멈추고 보고하라.
> 판정 이력: r1 `f42c7fda…cbaf3` → r2 `3a8050cc…d0470` → **r3 PASS** `cd2301bee6ac52201f2538aaf4d7c5b03f60b0b3855e158c10f6d4e6db070d4c`
> **P3 승인**: Jiwon, 2026-09-27 — D1–D9 원안 승인. 작성자 표기 "김지원" 확인(리포 public 인지 후).
> 🔴 **투자 자문 아님.** 모든 산출물(한·영)에 면책 2문장을 넣는다(계획 D9).
> 🔄 **2026-09-28 계획 rev-4 승인** — 추가 구현 지시는 **부록 R4**. 부록 범위에서는 rev-4(`d007f554…6e646`)가 권위 문서다.
> 🔄 **2026-09-28 계획 rev-4.1(D8 개정)** — 발표 전 내부 리허설과 테마는 **부록 R5**.

---

## §0. 이번 실행의 범위 — **E2-A만**

| 단계 | 지금 실행 | 이유 |
|---|---|---|
| **E2-A** | ✅ **실행** | 시작 조건(계획 §2 D1) ① P3 승인 ② 본 핸드오프 확정 — 충족 |
| E2-B | ❌ 금지 | 계획 §6 입력 게이트 4개 미충족(프린트 전, SCORED 없음, 가격 캡처 없음). 2026-09-27 17:55 KST 기준 FQ4 PR은 2026-10-01 05:01 KST(추정) |
| E2-C | ❌ 금지 | 10-K 없음, ed1 미커밋 |

**E2-A의 산출물은 코드·테스트·fixture·역사 추출본뿐이다.** `forecast/reports/` 아래에 리포트 파일을 **하나도 만들지 않는다.** 전체 파이프라인 시험은 fixture 값으로 `pytest`의 `tmp_path` 안에서만 돌린다(ed1로 오인될 파일을 남기지 않기 위해).

**git**: add/commit/push **금지**. 로컬 생성까지만(계획 R-10).

---

## §1. 먼저 할 일 (착수 전 확인 — 하나라도 다르면 중단·보고)

1. 계획 rev-3 SHA가 위 값과 같은지.
2. FROZEN `eab1184f721cd69460ffc4ddefd9851c59815207c35975db0dd1a2962b629f9a` · 프로파일 `faa60912b6a364eee67f87d9ba21221a6c6da02f22695c4d980200260982dfd6` 불변.
3. 계획 §4-7의 **E2-A 외부 입력 20개**가 경로·전체 SHA 모두 일치.
4. 기준 게이트: `python -m pytest forecast/tests/ -q` 그린 · `python forecast/scripts/verify_anchor.py` PASS · FROZEN 게이트 `checked == passed == 5`.
5. 렌더 도구 가용성: WeasyPrint(선례 NVDA 08-26이 호스트에서 WeasyPrint 69.0 사용) · matplotlib · openpyxl · 한글 폰트. **한글 폰트는 재배포 가능한 라이선스(예: Noto Sans KR/CJK, OFL)** 로 임베드한다. 없으면 설치 가능 여부를 보고하고 멈춘다 — 대체 폰트로 조용히 바꾸지 않는다.

---

## §2. 만들 파일 (계획 §2 D7 허용 경로 안에서만)

| 파일 | 내용 | 계획 근거 |
|---|---|---|
| `forecast/scripts/mu_report/__init__.py` | — | D7 |
| `forecast/scripts/mu_report/input_pins.yaml` | **E2-A 20개 핀**(경로·전체 SHA) + E2-B/E2-C **예약 경로**(SHA 칸 `null`). SHA를 Python 리터럴로 두지 않는다 | §4-7 |
| `forecast/scripts/mu_report/inputs.py` | `read_input(path, phase)` — allowlist·전체 SHA 확인 후 읽기. 감사 기록(시각 없음)과 실행 로그(시각 포함, `logs/_mu_report_runs/`) 분리 | §4-7 |
| `forecast/scripts/mu_report/extract.py` | 원문 → 추출본. 10-K 2개(3표), companyfacts(분기), 보도자료 11개(분기 손익·가이던스 표·BU 표·비GAAP 조정표·FCF 조정표), 10-Q(부채 주석 $323M), 준비문(DRAM/NAND 매출·비중·QoQ, 가격·비트 **언어적 구간 원문 문자열**) | §2 D6 · §4-3 · §4-8 · §4-6 C-2 |
| `forecast/scripts/mu_report/sources/*.json` | 추출본. 각 파일에 원본 경로·SHA·추출 좌표(표 번호·행·열 또는 문단 앵커) 기록 | D7 |
| `forecast/scripts/mu_report/facts.py` | canonical manifest 스키마·생성·검증. 금지 필드 부재, `bridge.nongaap_fixed_027` 제약, `UNAVAILABLE` 상태 레코드 | §4-6 · G-12a · G-19 |
| `forecast/scripts/mu_report/rle.py` | 리포트 레이어 순수식(§4-4 표 그대로) + 메모리 내 `GenericProfile` 호출. **엔진·스키마 수정 금지** | §4-4 |
| `forecast/scripts/mu_report/valuation.py` | §4-5 정의 그대로(암시 배수·`N/M`·EV·`EV_adj`·히트맵) | §4-5 |
| `forecast/scripts/mu_report/charts.py` | 차트 ①–⑧ (+③′) — manifest fact만 입력. 결정적 PNG(메타데이터 고정) | §3 · G-13b |
| `forecast/scripts/mu_report/render.py` | `i18n/{ko,en}.yaml` 템플릿 → md·html·pdf, 공유 xlsx. 위치별 fact 참조 로그 기록 | D5 · G-15 |
| `forecast/scripts/mu_report/i18n/ko.yaml` · `en.yaml` | 문장 템플릿. 숫자는 `{{fact:<fact_id>}}` 자리표시자만. 면책 고정 키 `disclaimer.not_advice` · `disclaimer.third_party` | D9 · G-7 |
| `forecast/scripts/mu_report/gates.py` | §5 게이트 전부 | §5 |
| `forecast/scripts/mu_report/build.py` | 진입점: `python forecast/scripts/mu_report/build.py --phase {E2-A,E2-B,E2-C} --edition {1,2}` (리포 루트에서, `verify_anchor.py`·`t3/` 선례와 같이 경로 실행. `forecast/scripts/`는 패키지가 아니다). **E2-A에서는 `--phase E2-A`만 허용하며 `forecast/reports/`에 쓰지 않는다** | D1 |
| `forecast/tests/test_mu_report.py` | 아래 §5 테스트 | D7 |
| `forecast/tests/fixtures/mu_report/**` | post-print 슬롯용 **가짜 값** fixture. 파일마다 머리에 `FIXTURE — NOT REAL DATA` 표기, 값은 실제와 혼동되지 않게(예: 매출 99,999) | §4-7 |

`forecast/inputs/mu_fy2026q4_report_assumptions.yaml`(실제 RLE 가정)은 **E2-A에서 만들지 않는다** — 값이 프린트 후 정보다(§4-7 금지 목록). 스키마·로더·검증은 fixture YAML로 만든다.

---

## §3. E2-A 작업 순서

1. **핀·입력 계층** — `input_pins.yaml` · `inputs.py`. 감사 기록 2회 생성 바이트 동일 확인.
2. **추출** — 역사 3표 FY23A–FY25A(10-K 발행사 계정명 그대로), 분기 FY23Q1–FY26Q3(Q4 = FY − 9M), BU 8분기(재편 후 보도자료, 동일 기간은 **최신 보도자료 값**, 차이는 기록), 가이던스 이력 10분기, debt-prepayment 3개 fact(−321 / 323 / 325, **합치거나 조정하지 않는다**), 회사 정의 순 capex·조정 FCF 구성 항목.
3. **manifest** — 추출본 → fact. 계산 fact는 `lineage` 필수. FY26E-PREREG_A는 **FROZEN 표시 문자열**만(bear/bull 연간 = `NOT_IN_SOURCE`).
4. **G-3 항등식** — 계획 §5 허용오차 식 그대로. 허용오차 안의 차이는 기록만, 초과는 fail closed. **보정 플러그 금지.**
5. **RLE·밸류에이션 코드** — fixture YAML로 §4-4의 모든 검증 항등식 통과. 히트맵 base 셀 == 본표 base.
6. **차트·렌더** — fixture 값으로 `tmp_path`에 KO/EN md·html·pdf·xlsx 생성 → G-13b · G-15 · G-21 통과.
7. **게이트 회귀표** — 게이트마다 {정상 PASS, 위반 주입 FAIL}.
8. **기존 게이트 재확인** — §1-4 전부.

---

## §4. 반드시 지킬 것 (계획에서 뽑은 실패 지점)

- **SCA 예치금**: 주 행 `NetCash_unadjusted`. `NetCash_ex_SCA`·`EV_adj`는 **같은 공시 fact** `bs.sca_customer_deposits`를 공유하고, 공시값이 없으면 둘 다 `UNAVAILABLE`. 추정 금지(§4-3 · §4-5).
- **RLE 순현금 행 이름**: "순현금(자사주·인수·차입변동 전, SCA 예치금 미조정)" — 문자열 고정.
- **+$0.27 브릿지**: `period == "FY2026Q4"` · `basis == "PREREG_A_ASSUMPTION"` 레코드 1개만. FY27E·FY28E 비GAAP = `UNAVAILABLE_WITHOUT_ASSUMPTIONS`(G-19).
- **`×52/53`**: flow 분모(매출·EPS·EBITDA·FCF) 보조 행만. 시가총액·EV·순현금 금지(Q-15).
- **언어적 구간**(`low-60s%` 등): 원문 문자열 그대로 범주형 표. 숫자화 금지.
- **FY27 컨센서스**: 표시 전용 `UNAVAILABLE_FOR_COMPARISON`. gap·beat/miss·색상·방향 문장 금지(G-17b).
- **금지 필드**: `target_price` · `fair_value_per_share` · `expected_share_price` · `probability_weighted_share_price` · `expected_value` · `scenario_weighted_central_value` · `mc_mean` — 스키마에 존재하지 않게(G-12a).
- **Freeze A**: 표시 문자열 일치(G-2). 프로파일 경로 재현은 `f8cfd47` 프로파일로 결정적 재실행, 레이블 `PREREG_A_PROFILE_PATH`, **RLE 입력으로 쓰지 않는다.**
- **HTML**: 외부 네트워크 의존 0(스크립트·스타일·이미지). SK 2026-09-13 HTML의 plotly CDN 같은 의존 금지.
- **PDF**: 브라우저 날짜 머리글·`file:///` 푸터 0(SK 2026-09-13 PDF 재발 방지).
- **개행**: 신규 텍스트 LF. 기존 파일 개행 불변.
- **밸류에이션 엔진·`valuation_bridge.py` 호출 금지.** 발행사 로고·브랜드 팔레트 금지(D8).

---

## §5. 테스트 요구 (`forecast/tests/test_mu_report.py`)

각 게이트에 **정상 PASS 1건 + 위반 주입 FAIL 1건 이상**. 최소 목록:

| 게이트 | 위반 주입 예 |
|---|---|
| G-1 | 입력 파일 1바이트 변경 → 중단 |
| G-2 | PREREG_A 표시값 1곳 변경 → 실패 |
| G-3 / 3b / 3c / 3d | 계정 1개를 허용오차 초과만큼 변경 → 실패 · 허용오차 이내 변경 → 통과 + 기록 |
| G-7 | 템플릿에 숫자 리터럴 삽입 · 스크립트에 직접 `open()` → 실패 |
| G-9 | PREREG_A 표에 post-print fact 삽입 → 실패 |
| G-12a | 금지 필드를 가진 fact 삽입 → 실패 |
| G-12b | 한 판에서 면책 키 제거 → 실패 |
| G-13b | 차트 series 점 1개 변경 → 실패 · 히트맵 base ≠ 본표 → 실패 |
| G-14 | 본문에 출처 없는 숫자·날짜 → 실패 · lineage 없는 계산 fact → 실패 |
| G-15 | EN 판에서 두 fact_id 위치 교환 → 실패(숫자 토큰 다중집합은 같아도) |
| G-17 / 17b | 라벨 누락 · FY27 컨센서스 gap 문장 → 실패 |
| G-18 | CRLF · NUL · 행말 공백 → 실패 |
| G-19 | FY2027 period의 `bridge.nongaap_fixed_027` → 실패 |
| G-20 | E2-A에서 예약 경로 읽기 → 실패 · 감사 기록 2회 생성 바이트 비동일 → 실패 |
| G-21 | PDF에 `file:///` · HTML에 외부 `<script src="https://…">` · XLSX 오류 셀 → 실패 |
| SCA | 예치금 fact `UNAVAILABLE` → `NetCash_ex_SCA`·`EV_adj` 모두 `UNAVAILABLE` |
| debt-prepayment | 세 fact 중 하나를 다른 값으로 합치는 시도 → 실패 |

기존 테스트는 수정하지 않는다. 필요하면 **멈추고 사유·diff를 보고**한다.

---

## §6. 보고 형식 (Codex → Claude)

새 문서 파일을 만들지 말고 **회신 메시지**로 보고한다(허용 경로 밖 파일 생성 방지). 포함 항목:

1. 생성·수정 파일 전체 목록 + 각 **전체 SHA-256** + 행 수.
2. `git --no-optional-locks status --short` 결과(허용 경로 밖 변경 0 확인).
3. 게이트 회귀표 — 게이트별 {정상 PASS, 위반 주입 FAIL}, **빈칸 없이**.
4. `python -m pytest forecast/tests/ -q` 전체 결과 · `test_mu_report.py` 단독 결과 · `verify_anchor.py` · FROZEN 게이트 SUMMARY.
5. NUL 검사 **4분할**: tracked / untracked / ignored / residual.
6. 역사 추출 대조표: FY23A–FY25A 매출·영업이익·순이익·희석 EPS, FY25 자산총계·부채총계·자본총계, FY25 영업CF — 각 **원문 좌표**와 companyfacts 값의 일치 여부.
7. G-3 허용오차 안에서 기록된 차이 목록(없으면 "0건").
8. BU 재작성 감지 결과(같은 기간 값이 보도자료 간에 다른 사례).
9. 멈춘 지점·판단이 필요한 항목.

Claude는 E3 전에 위 항목을 **독립 재실행**한다(보고서의 "PASS" 기재는 증거가 아니다).

---

## §7. 중단 조건

다음 중 하나면 즉시 멈추고 보고한다.
- 계획과 이 핸드오프가 충돌.
- 허용 경로 밖 파일을 만들거나 고쳐야 함(엔진·스키마·빌더·기존 테스트 포함).
- 입력 SHA 불일치, 항등식이 허용오차를 넘어 원문 재확인 후에도 남음.
- 한글 폰트·렌더 도구를 조용히 대체해야 하는 상황.
- 시간 예산(E2-A ≤ 2 세션) 초과.

---

## §8. 열린 항목 — Codex 확인 요청 1건

**RLE 가정값의 작성 주체.** 계획은 `forecast/inputs/mu_fy2026q4_report_assumptions.yaml`을 Codex가 만든다고 정했지만(D7), **가정값 자체**(FY27 주당 성장·GM·opex, capex, D&A, SBC, 운전자본 계수, FY28 성장, 배당, 주식수)를 누가 정하는지는 적지 않았다. Claude 제안: **E2-B 직전에 Claude가 가정값 표(값·근거 source_id·확신도)를 본 핸드오프의 부록으로 추가하고, Codex가 검토한 뒤 YAML로 옮긴다.** 게이트·경로는 바뀌지 않는다. 동의 여부를 E2-A 보고에 적어 달라. E2-A 작업은 이 항목과 무관하게 진행한다.

---

## 부록 R4. 계획 rev-4 ed1 추가분 구현 지시 (S5, 2026-09-28)

> 🔴 **이 부록의 범위에서는 계획 rev-4가 권위 문서다**: `forecast/PLAN_mu_report_fy2026q4.md` sha256 `d007f554f68643891d7586f8c43c4254886f3826f54417c4e3144239f2a8e646`. 판정 **r4 PASS** `forecast/REVIEW_CODEX_mu_report_plan_r4.md` `a0a95a2477a50a2244c3750a70beca3f83724a1acb0ba537b1a5d685ce65a976`. rev-3 보존 사본 `forecast/PLAN_mu_report_fy2026q4_rev3_superseded.md` `6a7350871ebc804e6b359240065662e31fd1411172face01217f24be6097f324`.
> **Jiwon 승인 (S4)**: 2026-09-28 11:10 KST — ① rev-4 승인 ② 이해관계 확인 레코드 `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`을 public 리포에 커밋하는 것 승인.
> 본문 §0–§8은 그대로 유효하다. 이 부록과 본문이 다르면 **이 부록(= rev-4)** 을 따르고, rev-4와 이 부록이 다르면 **rev-4**를 따른다. 차이를 발견하면 멈추고 보고한다.
> 🔴 **투자 자문 아님.**

### R4-0. 범위 — 단계 `E2-A′` (rev-4 ed1 추가분)

| 단계 | 지금 실행 | 이유 |
|---|---|---|
| **E2-A′** | ✅ **실행** | rev-4 승인 + 이 부록 확정. 계획 §6 E2-B 입력 게이트 ⑤의 "HANDOFF 부록(S5) 구현"이 바로 이 단계다 |
| E2-B | ❌ 금지 | ①–④ 미충족(프린트 전). ⑥ 확인 레코드도 아직 없다 |
| E2-C | ❌ 금지 | 본문 §0과 같다 |

- 산출물은 **코드·i18n·테스트·fixture뿐**이다. 전체 렌더 시험은 fixture 값으로 `pytest`의 `tmp_path` 안에서만 돌린다. `forecast/reports/`에는 쓰지 않는다.
- 실제 확인 레코드 `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`은 **이 단계에서 만들지 않는다.** E2-B 직전에 Jiwon이 확인한 내용으로 만든다(계획 §4-7, 렌더 전 24시간 이내). 이 단계에서는 **fixture만** 만든다.
- **git**: add/commit/push 금지.
- **목표 시한**: 2026-09-30 24:00 KST까지 보고. 그때까지 끝나지 않으면 진행 상황을 보고한다. 이후 E2-B를 rev-3대로 갈지 rev-4대로 갈지는 Jiwon이 정한다(계획 §R3-c · §6).
- ed2 예약 항목(역사적 밴드·피어 비교·G-22·G-22b)은 **구현하지 않는다.**

### R4-1. 착수 전 확인 (하나라도 다르면 중단·보고)

1. 위 PLAN rev-4 · r4 판정서 · rev-3 사본의 SHA가 일치하는지 확인한다.
2. FROZEN과 프로파일 SHA가 본문 §1-2와 같은지 확인한다.
3. 기준선: `python -m pytest forecast/tests/ -q`가 그린인지(직전 보고 451 passed), `verify_anchor.py`가 PASS인지, FROZEN 게이트가 `checked == passed == 5`인지 확인한다. **현재 통과 수를 먼저 기록한다.**
4. `REVIEW_CLAUDE_mu_report_output_r2.md` §3의 E2-B 조건 C-1·C-2는 그대로 유효하다. 이 부록은 그 조건을 바꾸지 않는다.

### R4-2. 구현 항목 6개

각 항목의 **계획 근거 절**을 먼저 읽는다. fact_id 이름은 아래 예시를 따르되, 기존 명명 규칙(`facts.py`)과 충돌하면 기존 규칙을 따르고 보고한다.

#### ① 회사 재고일수 — 계획 §4-3

- **추출 (`extract.py`)**: 재무상태표 caption `Inventories`를 추가 추출한다. 기간과 출처는 다음과 같다(모두 기존 E2-A allowlist 입력이며 새 입력은 없다).
  - FY2022 기말·FY2023 기말: `logs/_claude_scratch/mu-20230831.htm` 재무상태표(당기·비교 열)
  - FY2024 기말·FY2025 기말: `logs/_claude_scratch/mu-20250828.htm` 재무상태표
  - FY2026 기말: E2-B의 A-8K(예약 경로). E2-A′에서는 fixture로만 채운다
  - 추출 좌표(표 번호·행·열)를 `sources/*.json`에 기록한다. `cogs`(Cost of goods sold)는 이미 추출돼 있으니 재사용한다.
- **계산 (`rle.py` 또는 리포트 레이어 순수 함수)**: `inventory_days = mean(inv_begin, inv_end) / cogs × (period_weeks × 7)`.
  - FY23A–FY26A-8K만 계산한다. FY26A-8K는 `period_weeks = 53`을 그대로 쓰고 52주로 환산하지 않는다.
  - 기초 재고가 없거나 범위가 다르면 `status = "UNAVAILABLE"`, `cogs ≤ 0`이면 `N/M`이다.
  - FY27E·FY28E(RLE)는 `UNAVAILABLE`(재고 미모델)이다.
- **fact**: `ratio.inventory_days.<FY>.<label>`. lineage는 `{"formula": "inventory_days_v1", "inputs": [bs.inventories.<FY-1>, bs.inventories.<FY>, is.cogs.<FY>, meta.period_weeks.<FY>]}`.
- **표시**: §3 6절 비율 표와 공유 xlsx 비율 시트. **업계 재고 수치는 어디에도 넣지 않는다.**

#### ② trailing P/B — 계획 §4-5

- **`valuation.py`**: `trailing_pb(price, equity_musd, shares_million) -> float | str`를 추가한다.
  - `bvps = equity_musd / shares_million`, `bvps ≤ 0`이면 `"N/M"`.
  - 입력 중 하나라도 `UNAVAILABLE`이면 결과도 `UNAVAILABLE`이다.
- **입력 fact**: 기준 주가(§4-5, CITED) · `bs.total_equity.FY2026.A-8K`(ROE와 **같은 fact**, caption `Total equity`) · §4-5 발행주식수 fact(시가총액과 **같은 fact**).
- **fact**: `val.pb_trailing.FY2026.A-8K` 한 개만 둔다. **RLE 기간 P/B fact를 만들지 않는다.** 히트맵 축에도 넣지 않는다.
- **표시**: §3 9절 암시 배수 표의 **보조 행**. 캡션에 기준 주가일·자본 기준일·주식수 기준일을 **각각** 적는다(G-16).
- 목표가·적정가 필드와 연결하지 않는다. G-12a 금지 필드 목록은 그대로다.

#### ③ 시장 데이터 박스(최소) — 계획 §3 표지 · §4-5

- **`render.py` 표지 블록**: 기준 주가 · 발행주식수(기준일 병기) · 시가총액 · 회계연도 종료일, 이 **4개 셀만** 둔다. 모두 기존 fact를 참조한다.
- 52주 범위 · 거래량 · 유동비율 **키를 i18n·템플릿에 만들지 않는다.**
- 구성 fact가 없으면 해당 셀만 `UNAVAILABLE`로 둔다. 다른 날짜 값으로 대체하지 않는다.
- i18n 키 예: `cover.market_data.title`, `cover.market_data.{price,shares,market_cap,fiscal_year_end}` — KO/EN 둘 다 만든다.

#### ④ 이해관계 고지 — 계획 D9 · §4-7 · §5 G-12c

- **i18n 키**: `disclaimer.conflict` · `disclaimer.conflict_short`. 문안은 계획 D9 표의 KO/EN 문자열을 **글자 그대로** 쓴다. `{{conflict.confirmed_at_kst}}` 자리표시자는 확인 레코드에서 채운다.
- **로더**: `load_conflict_confirmation(path, edition, now_kst)`.
  - 이 파일은 **내부 설정 읽기**다(계획 §4-7 표: git 추적 파일, 외부 allowlist 대상 아님). 그래도 직접 `open()`은 G-7 위반이므로, 기존 입력 계층에 내부 설정 읽기 경로를 두고 감사 기록에 `{path, git_blob_sha, kind: "internal_config"}`를 남긴다. 실행 로그에는 읽은 시각을 남긴다.
  - 필수 키는 `author` · `ticker` · `status`(열거형 `{not_held, held}`) · `confirmed_at_kst` · `edition`이다. 알 수 없는 키나 값이 있으면 실패한다.
  - `now_kst`는 **주입 인자**로 받는다(테스트에서 시계를 고정해 결정성 확보).
- **`gates.py::gate_g12c_conflict(record, edition, now_kst, rendered)`** — 계획 §5 G-12c 조건을 모두 검사한다:
  - 레코드가 존재하고 `status == not_held`인지
  - `now_kst − confirmed_at_kst`가 0 이상 24시간 이하인지(미래 시각도 실패)
  - `edition`이 빌드 판과 같은지
  - `disclaimer.conflict`가 KO/EN 표지와 말미에, `disclaimer.conflict_short`가 PDF **각 페이지 푸터**에 있는지
  - KO/EN이 **같은 레코드**(blob SHA)를 참조하는지
  - 하나라도 어긋나면 렌더 전에 중단한다(fail closed).
- **렌더**: PDF 푸터는 기존 면책 푸터에 `disclaimer.conflict_short`를 더한다. 푸터 문자열을 `render.py`에 하드코딩하지 말고 i18n 키에서 조합한다.
- **fixture**: `forecast/tests/fixtures/mu_report/conflict_confirmation_{ok,held,expired,future,edition_mismatch,missing_key}.yaml`. 머리에 `FIXTURE — NOT REAL DATA`를 표기한다.

#### ⑤ 쪽 번호 — 계획 §5 G-21

- PDF 푸터에 `현재쪽/전체쪽`을 넣는다(WeasyPrint `counter(page)` / `counter(pages)`). KO/EN 둘 다 넣는다.
- 렌더 후 PDF를 **다시 열어**(생성물 재검증 읽기) 실제 쪽수를 세고, 산출 manifest의 `document.total_pages`에 **locale별로** `{ko: N_ko, en: N_en}`로 기록한다. KO/EN 쪽수가 다를 수 있으므로 fact가 아니라 **생성물 메타데이터**다. G-15의 fact 참조 비교 대상이 아니며, 본문·표에 인용하지 않는다.
- **`qa_pdf` 확장**: 각 쪽 푸터의 현재쪽이 1..N으로 연속인지, 전체쪽 == N == PDF 실제 쪽수 == manifest 값인지 검사한다.
- md·html에는 쪽 번호를 넣지 않는다.

#### ⑥ 목차 — 계획 §3 목차 · §5 G-15·G-21

- 표지 다음 1쪽에 둔다. 항목은 12개 절(계획 §3)의 절 id·제목·순서다.
- **PDF**: WeasyPrint `target-counter(attr(href), page)`로 쪽 번호를 표시한다.
- **md·html**: 절 앵커 링크만 두고 쪽 번호는 넣지 않는다.
- **G-15**: KO/EN 목차의 절 id 순서와 앵커가 같은지 검사한다(제목 문자열은 locale별로 다름).
- **G-21**:
  - PDF: 목차 각 항목의 쪽 번호가 해당 절 제목이 실제로 처음 나오는 쪽과 같은지 역검증한다(쪽별 텍스트 추출).
  - html: 모든 목차 앵커가 해석되는지 확인한다.
  - md: 로컬 앵커 링크가 해석되는지 확인한다.

### R4-3. 게이트 회귀표에 추가할 행 (정상 PASS / 위반 주입 FAIL, 빈칸 금지)

| 게이트·항목 | 정상 | 위반 주입 예 |
|---|---|---|
| 재고일수 | fixture 값으로 식 재현 | 기초 재고 제거 → `UNAVAILABLE` · `cogs = 0` → `N/M` · FY26에 52주 환산값 삽입 → 실패 · FY27E에 값 삽입 → 실패 · 업계 재고 fact 삽입 → 실패 |
| trailing P/B | fixture 값으로 식 재현 · lineage 3입력 | 자본 fact `UNAVAILABLE` → `UNAVAILABLE` · 음수 자본 → `N/M` · `val.pb_trailing.FY2027.*` 생성 → 실패 · 캡션 날짜 3개 중 1개 제거 → G-16 실패 |
| 시장 데이터 박스 | 4셀 모두 fact 참조 | 템플릿에 52주·거래량 키 추가 → 실패 · 주식수 fact 제거 → 해당 셀만 `UNAVAILABLE`(다른 값 대입 시 실패) |
| G-12c | `ok` fixture | `held` · `expired`(24시간 초과) · `future` · `edition_mismatch` · `missing_key` 각각 → 실패 · 한 쪽 푸터에서 `conflict_short` 제거 → 실패 · KO/EN이 다른 레코드 참조 → 실패 |
| G-21 쪽 번호 | 연속·일치 | 푸터 전체쪽 ≠ 실제 쪽수 → 실패 · manifest `total_pages` 변조 → 실패 |
| G-15·G-21 목차 | 순서·앵커·쪽 일치 | EN 목차 두 절 순서 교환 → G-15 실패 · 목차 쪽 번호 1 변조 → G-21 실패 · 깨진 앵커 → 실패 |
| G-14 | 새 fact 모두 source·lineage 보유 | lineage 없는 `ratio.inventory_days` → 실패 |

- 기존 회귀표 행은 모두 유지하고, 전체 통과 수를 기준선과 함께 보고한다.
- 기존 테스트는 수정하지 않는다. 필요하면 **멈추고 사유와 diff를 보고한다.**

### R4-4. 허용 경로 (이 단계)

- 수정: `forecast/scripts/mu_report/{extract,facts,rle,valuation,render,gates,inputs,build}.py` · `forecast/scripts/mu_report/i18n/{ko,en}.yaml` · `forecast/scripts/mu_report/sources/*.json`(추출본 재생성) · `forecast/tests/test_mu_report.py`
- 생성: `forecast/tests/fixtures/mu_report/conflict_confirmation_*.yaml`
- **생성 금지**: `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`(E2-B 직전 Jiwon 확인 후) · `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` · `forecast/reports/**`
- **수정 금지**: FROZEN · 프로파일 · `forecast/engine/**` · `forecast/pipeline/**` · 계획 · 이 핸드오프 · 기존 테스트
- 모든 쓰기는 원자적으로 한다(temp → `os.replace`). `.py`를 쓸 때마다 `ast.parse`와 줄 수를 확인한다. 끝나면 NUL 스캔을 한다. 신규 텍스트는 LF다.

### R4-5. 보고 (회신 메시지, 새 문서 파일 만들지 않음)

본문 §6의 1–9번에 다음을 더한다.

10. 새 fact_id 목록과 각 lineage 식 id.
11. 재고일수 추출 좌표 표: FY2022–FY2025 `Inventories` 각각의 파일·표·행·열(값은 적어도 되고, 원문 대조 여부를 표시).
12. G-12c fixture 6종 결과표.
13. fixture 렌더 KO/EN PDF의 쪽수, 목차 역검증 결과, 푸터 `conflict_short` 존재 쪽 수 / 전체 쪽 수.
14. 기준선 대비 테스트 수 증감(`N passed → M passed`).

Claude는 E3 전에 위 항목을 **독립 재실행**한다.

### R4-6. 중단 조건

본문 §7에 더해 다음 경우에도 멈춘다.

- `Inventories` caption이 10-K 표에 없거나 두 10-K 간 범위(연결 범위)가 다르다.
- WeasyPrint `counter(pages)`나 `target-counter`가 호스트 버전에서 동작하지 않아 쪽 번호·목차를 다른 방법으로 **조용히** 바꿔야 한다.
- 확인 레코드의 시각 비교에 시스템 시계를 직접 써야 한다(주입 인자로 풀 수 없음).

---

## 부록 R5. 발표 전 내부 리허설 렌더 (DRY RUN) + D8 개정 테마 (2026-09-28)

> **권위 문서**: 계획 **rev-4.2** `forecast/PLAN_mu_report_fy2026q4.md` sha256 `32fc96edbaffa1c0952f9dc1d5a9f4b5eb2743ce41e482ea1b50b681689d5734`. rev-4.1은 rev-4에서 **D8만** 바꿨다(J-6, R5-0 ⓐ PASS). rev-4.2는 **D7에 리허설 쓰기 예외 경로**만 더했다(R5-0 ⓑ-1). 보존 사본: rev-4 `…_rev4_superseded.md` `d007f554…6e646` · rev-4.1 `…_rev4.1_superseded.md` `35dc207b…9bdf5`.
> **R5-0 ⓑ 반영(2026-09-28)**: ⓑ-1 D7 쓰기 예외(rev-4.2) · ⓑ-2 확인 레코드 로더 계약 유지(아래 R5-4) · ⓑ-3 G-3 적용 범위 명시(아래 R5-4).
> **Jiwon 결정 (2026-09-28)**: ① 발표 전 **내부 리허설 렌더(A안)** 승인. 배포용 프리뷰판(ⓐ)은 계속 제외(D1 유지) ② J-6 디자인: 청색 계열 강조색 + 텍스트 표기, **로고 이미지 없음**.
> 🔴 **투자 자문 아님.** 🔴 **리허설 산출물은 배포하지 않는다.**

### R5-0. 순서 — 실행 전에 Codex가 먼저 검토한다

1. **Codex 사전 검토**(회신 메시지): ⓐ rev-4.1 D8 개정이 다른 결정(D9 제3자 고지 · G-7 · G-15)과 충돌하지 않는지 ⓑ 이 부록의 범위(R5-1)와 게이트 예외(R5-4)가 타당한지. 이견이 있으면 번호를 붙여 적는다.
2. Claude가 이견에 답하고 부록을 고친다(필요할 때만).
3. Codex가 R5-2~R5-6을 실행하고 R5-7 형식으로 보고한다.
4. Claude가 쪽 이미지를 **독립 검수**한다.

### R5-1. 범위와 경계

| 항목 | 규칙 |
|---|---|
| 목적 | 본판(E2-B) 전에 **실제 역사 데이터**로 전체 렌더 경로를 한 번 돌린다. 레이아웃·폰트·쪽 넘김·차트 축·목차 쪽 번호·테마 결함을 발표 전에 찾는다 |
| 저장 | `logs/_mu_report_runs/dryrun_<UTC 타임스탬프>/`에만 저장한다. 파일명에 `DRYRUN`을 넣는다. **add·commit·push·복사·공유 금지.** `forecast/reports/**`에 쓰지 않는다 |
| 입력 | **E2-A allowlist 20개만** 쓴다(역사 실제치 + FROZEN의 PREREG_A). E2-B 예약 경로·가격 캡처·SCORED·RLE YAML은 읽지 않는다. `input_pins.yaml`은 수정하지 않는다 |
| 발표 후 칸 | A-8K · FQ1 FY27 가이던스 · SCORED · 기준 주가 · RLE는 전부 `UNAVAILABLE`로 둔다. 가짜 값(fixture)을 섞지 않는다. 섞으면 실제 데이터로 오인될 수 있다 |
| 렌더 경로 | **본판과 같은 `build.py` → `render.py` 경로**를 쓴다. 간이 렌더러를 따로 만들지 않는다. 진입점: `python forecast/scripts/mu_report/build.py --phase DRYRUN --edition dryrun` |
| 구조 | 계획 §3의 표지 + 목차 + **12개 절을 모두 유지**한다. 절을 삭제하지 않는다. 데이터가 없는 절·표·차트는 자리를 남기고 사유를 표시한다(R5-3) |
| 워터마크 | **모든 쪽**에 `PRE-PRINT DRY RUN · 배포 금지` / `PRE-PRINT DRY RUN · NOT FOR DISTRIBUTION`을 넣는다. 위치는 머리글(고정)과 본문 대각선(연한 색) 두 곳이다. 표지 제목 위에도 같은 문구를 둔다 |

### R5-2. 테마 (계획 D8 rev-4.1)

- **테마 설정 하나**(예: `forecast/scripts/mu_report/theme.py` 또는 `theme.yaml`)에 색·서체·간격을 모은다. KO/EN이 같은 테마를 쓴다. 색 값은 i18n에 두지 않는다. G-7은 이 파일을 설정 예외로 등재한다(사유 주석 포함).
- **색**:
  - 주 강조: 청색 계열 1개. 머리띠, 절 제목 막대, 표 머리 행, 차트 주 계열에 쓴다.
  - 보조: 청색의 명도 단계 2개 + 중립 회색 3단계.
  - 경고·약세: 채도가 낮은 주황 1개.
  - 본문 대비 4.5:1 이상. 그 대비값을 계산해 보고한다.
  - Micron 공식 색이라고 적지 않는다.
- **표지**(선례 NVDA·SK하이닉스 보고서의 **정보 구성**을 참고한다. 로고와 선례의 브랜드색은 쓰지 않는다):
  1. 머리띠: 리포트 종류(`Review & Outlook — FY2026 Q4`) · 발행일 자리 · DRY RUN 표시
  2. 회사 표기: `Micron Technology, Inc. (NASDAQ: MU)` — **본문 서체의 굵은 텍스트**. 바로 아래에 제3자 분석 한 줄
  3. 핵심 관찰 3줄 · 핵심 수치표 · 시장 데이터 박스(4칸) · as-of / 정보 컷오프 / 데이터 충족도
  4. 작성자 `김지원` · 면책 2키 + 이해관계 자리(R5-4 G-12c)
- **본문**: 절 제목 앞에 강조색 막대, 표는 얇은 가로선과 교차 행 음영, 숫자는 오른쪽 정렬·고정폭 숫자, 단위와 기준일은 표 제목 줄에 둔다.
- **차트 공통**: 제목, 축 단위, 범례, 캡션 5요소(번호·단위·출처·기준일·회계기준, G-16)를 모든 차트에 둔다. 격자는 연하게, 불필요한 테두리는 없앤다. 주 계열은 강조색, 비교 계열은 회색이나 명도 단계로 칠한다. 레이어(A / PREREG_A / RLE)는 **선 종류와 라벨로도** 구분한다.

### R5-3. 표·차트별 리허설 상태

| 요소 | 리허설에서 | 발표 후 칸 표시 |
|---|---|---|
| 3표 FY23A–FY25A · 분기 FY23Q1–FY26Q3 · BU 8분기 · 비율(재고일수 FY23–FY25 포함) | **실제값** | FY26A-8K 열·FY27E·FY28E 열 = `UNAVAILABLE` |
| FY26E-PREREG_A 열 | FROZEN 표시 문자열 그대로(G-2) | bear/bull 연간 = `NOT_IN_SOURCE` |
| ① 분기 매출·GM·OPM | 실제 FY23Q1–FY26Q3 | FQ4 FY26 자리 = 빈 막대 + `UNAVAILABLE` 라벨 |
| ② BU 믹스 추이 | 실제 8분기 | FQ4-26 자리 표시 |
| ③ DRAM/NAND | 준비문이 1기간뿐이라 충족 기준 미달 → **③′로 교체**(계획 §3 규칙). 실제 가이던스 대비 GM 10분기 | FQ4 자리 표시 |
| ④ 가이던스 대비 상회 이력 | FROZEN (d-1) 실제 | FQ4 SCORED 자리 = `UNAVAILABLE` |
| ⑤ 시나리오 fan | FQ4 FY26 PREREG_A 시나리오만 | RLE FY27 구간 = 음영 자리 + `UNAVAILABLE` |
| ⑥ 연간 손익 | FY23A–FY25A 실제 + FY26E-PREREG_A | FY26A-8K 막대·FY27E·FY28E = 자리 표시 |
| ⑦ 암시 P/E 히트맵 | **계산하지 않는다** | 패널 전체에 "기준 주가 미확보로 계산하지 않음(발표 후 첫 종가, 계획 §4-5)" |
| ⑧ FCF·순 capex·순현금 | 실제 FY23–FY25 + 분기 FQ3까지 | FQ4 자리 표시 |
| 9절 밸류에이션 | 절·표 틀 유지. 암시 배수·trailing P/B·시장 데이터 박스의 가격 의존 칸 = "기준 주가 미확보로 계산하지 않음" | — |
| 본문 문단 | 절마다 **목표 길이의 자리표시 문단**(`[DRY RUN 자리표시 문단 — E2-B에서 작성]` + 한국어·영어 더미 문장)을 둔다. 쪽 넘김을 시험하기 위해서다. 분석 문장·숫자를 새로 쓰지 않는다 | — |

- `UNAVAILABLE` 자리 표시는 차트 id·캡션·목차 항목을 **그대로 남긴다.** G-13의 존재 검사와 목차·앵커를 시험하기 위해서다.
- 자리표시 문단에는 숫자를 넣지 않는다(G-14).

### R5-4. 게이트 적용표 (리허설)

| 게이트 | 리허설 | 사유 |
|---|---|---|
| G-1 · G-20 | **적용**(E2-A allowlist 기준, 예약 경로 0건) | 입력 경계를 증명한다 |
| G-2 · G-3 · G-3b · G-3c · G-3d · G-9 · G-12a · G-12b · G-13 · G-13b · G-14 · G-15 · G-16 · G-17 · G-17b · G-18 · G-19 · G-21 | **적용** | 본판과 같은 경로를 시험하는 것이 목적이다 |
| G-3e 가격 2경로 · G-3f SCORED 대조 | **제외** | 입력이 발표 후에 생긴다 |
| G-12c 이해관계 | **리허설 분기**(본판 G-12c와 별도 함수): 실제 확인 레코드를 만들지 않는다. 표지·말미·푸터의 이해관계 자리에 `[DRY RUN — 발행 전 보유 확인 미실시]` / `[DRY RUN — pre-publication holding check not performed]`을 넣는다. 이 분기는 ① 대체 문구가 **모든 쪽**에 있는지 ② `disclaimer.conflict`·`conflict_short` 실문안이 **한 번도 렌더되지 않았는지** 검사한다 | 발행 확인으로 오인되지 않게 하기 위해서다. **계약 분리**: `build.py`만 `--phase DRYRUN --edition dryrun` 조합을 허용한다. `load_conflict_confirmation()`의 `edition`은 **계속 `{ed1, ed2}`만** 허용한다(열거형 확장 금지). DRYRUN 실행에 확인 레코드가 전달되면 실패한다. 본판 `gate_g12c_conflict`는 수정하지 않는다 |
| 기존 게이트(pytest·verify_anchor·FROZEN) | 실행 후 전후 비교 | 리허설이 저장소 상태를 바꾸지 않았음을 확인한다 |

### R5-5. 허용 경로

- **수정**: `forecast/scripts/mu_report/{build,render,gates,inputs,charts,facts}.py` · `i18n/{ko,en}.yaml` · 테마 설정 파일 1개(신규) · `forecast/tests/test_mu_report.py`(DRYRUN 모드·테마·워터마크·G-12c 리허설 모드 테스트 추가)
- **생성**: `logs/_mu_report_runs/dryrun_*/**`
- **금지**: `forecast/reports/**` · `forecast/inputs/**` · `input_pins.yaml` · FROZEN · 프로파일 · engine · pipeline · 계획 · 이 핸드오프 · 기존 테스트 변경
- 쓰기는 원자적으로 한다. `.py`는 `ast.parse`와 줄 수를 확인한다. 끝나면 NUL 스캔을 한다. 신규 텍스트는 LF다.

### R5-6. 추가 테스트 (위반 주입)

| 항목 | 위반 주입 |
|---|---|
| DRYRUN 경계 | `--phase DRYRUN`에서 `forecast/reports/`에 쓰기 → 실패 · 예약 경로 읽기 → 실패 · fixture 값 혼입 → 실패 |
| 워터마크 | 한 쪽에서 워터마크 제거 → 실패 |
| G-12c 리허설 분기 | 실문안 `disclaimer.conflict`가 렌더됨 → 실패 · 리허설 문구가 한 쪽에 없음 → 실패 · DRYRUN 실행에 확인 레코드를 넘김 → 실패 · 로더에 `edition: dryrun` 레코드 → 실패(계약 유지) |
| 테마 | 본문 대비 4.5:1 미만 색 → 실패 · i18n에 색 값 → G-7 실패 · 로고 이미지(`<img>` 또는 이미지 파일) 삽입 → 실패 |
| 자리 표시 | `UNAVAILABLE` 자리에 숫자 삽입 → G-14 실패 · ⑦ 패널에 값 → 실패 |

### R5-7. 보고 (회신 메시지)

1. 사전 검토(R5-0 ⓐ ⓑ) 결과와 이견
2. 산출 폴더 경로와 파일 목록(SHA 포함). KO/EN md·html·pdf·xlsx · 차트 PNG · manifest · 감사 기록
3. 게이트 결과표(R5-4 기준, 적용 게이트 전부 PASS/FAIL)
4. **쪽별 시각 검수표**(KO·EN 각각): 쪽 번호 · 내용 · 폰트(한글 누락·대체 여부) · 쪽 넘김(표·차트 잘림, 고아 제목) · 차트 축(단위·눈금·겹침) · 목차 쪽 번호 일치 · 워터마크 · 문제와 제안
5. 테마 색 값과 대비 계산 결과
6. 테스트 수 전후(`N passed → M passed`) · verify_anchor · FROZEN · NUL
7. 쪽 PNG(각 쪽 1장)를 같은 폴더 `pages/`에 둔다. **Claude가 이 이미지로 독립 검수한다**

---

## 부록 R6. RLE 가정 규칙 사전등록 v0 + 발표 전 본문 채우기 (2026-09-29)

> 작성 Claude · 검토 Codex · **승인 Jiwon(아래 ★ 판단값 포함)**. 본문 §8에서 합의한 순서("Claude가 가정값 표를 작성 → Codex 검토 → YAML")의 첫 단계다.
> 🔴 **투자 자문 아님.** 모든 값은 리포트 레이어 추정(RLE)이며 확신도는 **하(low)** 이다(계획 D2 YAML `confidence: low`).

### R6-0. 왜 지금 쓰는가 — "규칙은 발표 전, 숫자는 발표 후"

- RLE의 FY27 경로는 FQ1 FY27 **가이던스**(발표 시 공개)에 앵커를 둔다. 그래서 **숫자**는 발표 후에만 정해진다.
- 그러나 **숫자를 만드는 규칙**은 지금 정할 수 있다. 발표 전에 규칙을 고정하면, 실적을 본 뒤 가정을 입맛대로 고치는 **사후 조정(hindsight)** 을 막을 수 있다. Freeze A(사전등록)와 같은 원리를 RLE에도 적용하는 것이다.
- **발표 후에는 아래 "발표 후 입력" 열의 값만 넣는다.** 규칙을 바꾸려면 부록에 `사후 변경 — 사유`를 남기고 리포트 부록에도 공개한다.
- 권장: 이 부록의 SHA를 **발표(2026-10-01 05:01 KST) 전에** 호스트에서 커밋하거나 최소한 기록한다. 그래야 사전등록 시점이 증명된다(Jiwon 결정).

### R6-1. 기호

| 기호 | 뜻 | 확정 시점 |
|---|---|---|
| $G_1$, $G_1^{lo}$, $G_1^{hi}$ | FQ1 FY27 매출 가이던스 중간값·하단·상단(13주) | 발표 |
| $M_1$ · $X_1$ · $S_1$ | FQ1 FY27 GAAP GM 가이던스 · GAAP opex 가이던스 · 가이던스 주식수 | 발표 |
| $A_4$ | FQ4 FY26 실제 매출(14주, A-8K) | 발표 |
| $b_{med}$ | 사후 break 가이던스 상회율 중앙값 — FY24 Q2 … **FY26 Q4**(11개, 발표 후 FQ4 1개 추가) | 발표 |
| $b_{4}$ | 최근 4분기(FY26 Q1–Q4) 상회율 중앙값 | 발표 |
| FY26A 3표 | 8-K(FY26A-8K) 손익·재무상태·현금흐름 | 발표 |

상회율 = 실제 매출 ÷ 가이던스 중간값 − 1 (Freeze A §(d-1) 표와 같은 정의).

### R6-2. 가정 규칙표

| # | 가정 | bear (0.20) | **base (0.50)** | bull (0.30) | 근거(source) | 발표 후 입력 | ★ Jiwon 판단 |
|---|---|---|---|---|---|---|---|
| A1 | **FQ1 FY27 매출** | $G_1^{lo}$ | $G_1 \times (1+b_{med})$ | $G_1 \times (1+b_4)$ | Freeze A `ANCHOR` 규칙과 동일(FROZEN §(a-1)·프로파일 notes). 사후 break 10분기 전부 중간값 이상 | $G_1$ 범위, $A_4$, 가이던스 이력 | 확률 0.20/0.50/0.30 유지 여부 |
| A2 | **FQ2–FQ4 FY27 주당 성장** $g_{week}$ (13주) | −10% / −8% / −5% | **+3% / +2% / +1%** | +8% / +5% / +3% | 준비문: FQ4 GM "가격 상승률의 의미 있는 둔화" · 공급 부족 "calendar 2027 이후까지" · SCA 가격 천장 = CQ2 시장가, 체결 시 매출의 약 40%(FROZEN §(c-3)). Freeze A의 FY27 base 경로(+5/+3/+2%)를 한 분기 뒤로 민 모양 | 없음(규칙 고정) | ★ 경로 값 3개 × 3시나리오 |
| A2′ | **조건부 전환** | — | FQ1 가이던스의 **주당** 방향이 `DECLINE`(주당 ≤ −2%, Freeze A §(c-2) 밴드)이면 base 경로를 **0% / −3% / −3%**로 바꾼다. bull은 base의 원래 경로(+3/+2/+1%)로, bear는 그대로 둔다 | 같은 밴드 | 주당 방향 = $\frac{G_1/13}{A_4/14}-1$ | $G_1$, $A_4$ | ★ 전환 여부 |
| A3 | **GAAP GM** | FQ1 = $M_1$ − 1pt, 이후 분기당 −2.5pt | FQ1 = $M_1$, **이후 보합** | FQ1 = $M_1$ + 1pt, 이후 분기당 +0.5pt(상한 90%) | Freeze A: base GM = 가이던스(보수적 선택, FROZEN §(b-1)) · 가이던스 반폭 ±1pt(§(d-0)) · bear 기울기는 Freeze A bear(85→75%, 3분기)의 연율 | $M_1$ | ★ bear 기울기 |
| A4 | **GAAP opex ($)** | base와 같음 | FQ1 = $X_1$. FY27 합계 $T = \text{FY26A opex} \times \tfrac{52}{53} + 1{,}000$. 나머지 $T - X_1$을 FQ2:FQ3:FQ4 = **30:33:37**로 배분(하반기 가중) | base와 같음 | 준비문: FY27 opex "약 $1B 증가, 하반기 가중". 🔴 준비문 문서 기본 basis는 비GAAP이므로 +$1B를 GAAP에 그대로 쓰는 것은 **가정**이다 | $X_1$, FY26A opex | ★ 배분 비율 |
| A5 | **영업외 순액** | 매출의 −0.228% | 같음 | 같음 | Freeze A `net_interest_pct_of_revenue`(사후 break 중앙값). 현금 증가에 따른 이자수익 증가는 반영하지 않는다(민감도 작음, FROZEN §(f-2) 5순위) | 없음 | — |
| A6 | **GAAP 유효세율** | 15.0% | FQ1 가이던스로 **역산 잔차**(Freeze A 방식). 역산할 수 없으면 15.0% | base − 0.5pt | FROZEN §(a-1)·SF6. 준비문 "around 15.0%"의 basis는 비GAAP(문서 기본 basis 문장) | FQ1 GAAP EPS 가이던스, $S_1$ | — |
| A7 | **희석주식수** | $S_1$, FY27 보합 | 같음 | 같음 | 준비문 주식수 가이드. 🔴 2026-12-09부터 **자본환원 확대("잉여현금 100% 환원")** 가 예고됐지만 자사주 매입은 **모델에 넣지 않는다**(계획 §8-7 순현금 roll-forward 한계와 같은 이유). EPS 상방 누락은 한계로 공시한다 | $S_1$ | ★ 자사주 미반영 유지 여부 |
| A8 | **FY28 매출 성장** | **−25%** | **0%** | +10% | 준비문: "industry supply to improve gradually in 2028" · 메모리 사이클 이력. FY28은 연간 1행만(계획 D2) | 없음 | ★ 세 값 |
| A9 | **FY28 GM** | FY27 FQ4 GM − 15pt | FY27 FQ4 GM − 3pt | FY27 FQ4 GM | 공급 완화 시 가격 정상화. bear는 Freeze A bear FY27 기울기의 연장 | 없음 | ★ 세 값 |
| A10 | **FY28 opex** | FY27 opex × 1.08 | 같음 | 같음 | R&D 확대 지속(준비문 "expand R&D") — 판단값 | 없음 | ★ 증가율 |
| A11 | **D&A** | base와 같음 | 유형자산 roll-forward: $PPE_t = PPE_{t-1} + \text{gross capex}_t - DA_t$, $DA_t = d \times$ 평균 PPE. $d$ = FY26A D&A ÷ 평균(FY25, FY26 PPE). FY26 PPE가 8-K에 없으면 FY25 값(8,352 ÷ 평균 43,170 = **19.3%**) | 같음 | 3표 실제치(10-K FY25, FY26A-8K) | FY26A D&A·PPE | — |
| A12 | **SBC** | base와 같음 | FY26A SBC ÷ FY26A GAAP opex 비율 × 해당 기간 opex | 같음 | 3표 실제치 | FY26A SBC | — |
| A13 | **운전자본** $\Delta NWC = -k\,\Delta rev$ | base와 같음 | $k$ = FY24A·FY25A·FY26A의 (매출채권+재고+매입채무+기타 유동부채 변동 합) ÷ Δ매출 **중앙값** (참고: FY24 ≈ 0.12, FY25 ≈ 0.05) | 같음 | 현금흐름표 실제치 | FY26A 현금흐름표 | — |
| A14 | **순 capex** | base와 같음 | 분기 = FQ4A 순 capex × **1.10 / 1.15 / 1.20 / 1.25**(FQ1→FQ4). FQ1 콜에서 FY27 capex 수치 가이드가 나오면 **그 값으로 대체**하고 source_id를 단다. FY28 = FY27 합계와 같음 | 같음 | 준비문: "FY27 분기 capex는 FQ4(약 $10B)보다 높음, 증가분의 절반 이상이 건설 capex". capex는 회사 정의상 정부 인센티브 차감 후(net) | FQ4A 순 capex, (있으면) FY27 가이드 | ★ 증가 배수 |
| A15 | **배당** | base와 같음 | 최근 선언 분기 주당배당 × 기말 희석주식수 | 같음 | 8-K | 선언 DPS | — |
| A16 | **SCA 예치금** | 예측하지 않음 | 공시값만(계획 §4-3). RLE 기간 `UNAVAILABLE` | — | 준비문: 예치금은 재무현금흐름, 계약 후반부 반환 | 10-K/8-K 공시 | — |
| A17 | **비GAAP (FY27E·FY28E)** | `UNAVAILABLE_WITHOUT_ASSUMPTIONS` | 같음 | 같음 | 계획 §4-6 · G-19 | — | — |

- 모든 식은 계획 §4-4 경로를 따른다(엔진 `run_generic_forecast` + 리포트 레이어 순수식). **Freeze A 프로파일을 RLE 입력으로 쓰지 않는다**. 규칙의 "모양"만 같은 원리로 가져왔다.
- 확률 0.20/0.50/0.30은 **판단값이며 보정되지 않았다**(Freeze A와 같은 한계).
- 민감도 축(히트맵 ⑦) = {A2 base 경로에 대한 주당 성장 오프셋} × {A3 FY27 GM}. 계획 §4-5와 같다.

### R6-3. Jiwon이 정할 것 (★)

1. 시나리오 확률 0.20/0.50/0.30 유지 여부
2. A2 FY27 주당 성장 경로 3×3 값과 A2′ 조건부 전환
3. A3 bear GM 기울기(분기당 −2.5pt)
4. A4 opex 하반기 배분(30:33:37)
5. A7 자사주 매입 미반영 유지(= 보수적, 한계로 공시)
6. A8–A10 FY28 세 가지(매출 성장·GM·opex)
7. A14 capex 증가 배수

제안값은 위 표와 같다. 바꾸고 싶은 값만 알려 주면 된다. 정해지면 이 부록을 v1로 올리고 SHA를 기록한다.

### R6-4. 발표 전에 본문에 채울 수 있는 것 (리허설·본판 공통)

리허설에서 2·8·10·11절이 자리표시로 남았다. 이 절들은 **발표 전 정보만으로** 채울 수 있다. 출처는 모두 E2-A allowlist 안에 있다.

| 절 | 발표 전 내용 | 출처 |
|---|---|---|
| 2 강세 vs 약세 | 강세: 공급 부족 CY2027 이후 지속 · SCA 16건(누적 약 $100B, 예치금 $22B) · HBM4 12-high 램프(HBM3E 대비 2배 속도). 약세: 가격 상승률 둔화 명시 · SCA 가격 천장(매출 약 40%) · 2028년 공급 점진 개선. 논거마다 **반증 관측원** 1개를 둔다(계획 §3) | FROZEN §(c-3)·§(e) · 준비문 |
| 8 시나리오 | ① **FQ4 FY26 PREREG_A 시나리오 표**(FROZEN §(a-1) 값 그대로, G-2) ② **RLE 가정 규칙표**(R6-2의 규칙 열. 값 칸은 발표 후 입력 전까지 `UNAVAILABLE`) | FROZEN · 본 부록 |
| 10 리스크·스윙 팩터 | FROZEN §(f-2) EPS 레버 순위표 · §(f-3) 스윙 팩터(대상명 인용) | FROZEN |
| 11 촉매·일정 | FQ4 발표·콜(`ESTIMATED`/`CONFIRMED_TEXT`) · 10-K 접수(`ESTIMATED`) · 2026-12-09 자본환원 확대(`CONFIRMED_TEXT`, 준비문) · HBM4E CY2027 하반기 양산 | FROZEN 헤더 · 준비문 |

- 서술 문장(KO/EN)은 **Claude가 초안을 쓰고** Codex가 i18n 템플릿(`{{fact:…}}` 자리표시자)으로 옮긴다. 숫자는 모두 manifest fact로 참조한다(G-14).
- 인용은 준비문 원문 15단어 미만, 따옴표·출처 표기를 지킨다.

### R6-5. 근거 상세와 자기 평가 (2026-09-29, Jiwon 질의 회신)

**근거 등급**
- **E**: 공시 원문이 방향과 크기를 모두 뒷받침한다.
- **D**: 공시는 방향만 뒷받침하고, 크기는 판단이다.
- **J**: 판단이며, 공시 근거가 약하거나 없다.

인용은 모두 E2-A 허용 입력에서 가져왔다(준비문 `logs/mu_ho5_Q3_remarks.pdf` = REM, FROZEN, companyfacts = CF). 조사 표본(셀사이드 리포트)의 숫자는 쓰지 않았다.

| # | 질문 | 근거 | 등급 | 자기 평가 · 제안 |
|---|---|---|---|---|
| 1 | 확률 0.20/0.50/0.30 | Freeze A 값을 그대로 가져왔다. Freeze A에서 bull > bear로 둔 이유는 사후 break 10분기 동안 가이던스 미달이 0건이었기 때문이다(FROZEN §(d-1)). 그 확률도 "판단값, 미보정"으로 공시돼 있다 | **J** | **FY27 경로에는 이 비대칭을 정당화할 기록이 없다.** 또 계획 §4-5는 확률가중 값(`scenario_weighted_central_value` 등)을 **금지**하므로 RLE 계산에 확률이 필요 없다. **제안: RLE에서 확률을 삭제**하고 bear/base/bull을 가중 없는 시나리오로만 제시한다 |
| 2 | FY27 성장 둔화 | ① REM: FQ4 GM 가이던스가 "meaningful moderation in the rate of price increases"를 반영한다 → 가격 상승률(2차 도함수)이 꺾였다는 회사 진술 ② REM: FQ3 DRAM 비트 출하 "low-single-digit" 증가, 가격 "low-60s%" 증가 → 매출 성장이 거의 전부 **가격**에서 왔다. 가격 상승률이 둔화하면 성장률도 따라서 둔화한다 ③ REM: SCA 전부 체결 시 매출의 약 40%가 "fixed prices or price ceilings at or close to current CQ2 market prices" → 이 부분은 가격 상방이 막힌다 ④ REM: "Technology transitions are driving slower bit growth" ⑤ 반대 근거: REM "tight beyond calendar 2027", 산업 DRAM 비트 CY2026 "low- to mid-20s" 증가(분기 약 5%) | 방향 **E** / 크기 **J** | **둔화 방향은 공시로 뒷받침된다.** 그러나 base +3/+2/+1%는 Freeze A 경로를 한 분기 밀어 만든 값이지 **분해해서 도출한 값이 아니다.** 비트가 분기 약 +5%(⑤) 늘면, 이 경로는 **분기 ASP 하락 약 −2~−4%를 암묵적으로 가정**한다. "tight beyond 2027"과 긴장 관계다. **제안(v1)**: $g_{week} = (1+b)(1+p) - 1$로 분해한다. $b$(비트) = 산업 비트 가이던스 기반, $p$(ASP) = 시나리오별 가정. 두 값을 따로 공시한다 |
| 3 | GM 비대칭(bull +0.5pt, bear −2.5pt) | **상방이 좁은 이유**: ① 현재 수준 86%(FQ4 가이던스) — 상한까지 여유가 좁다 ② REM: 제품 전환으로 "blended DRAM cost per bit to rise" → 원가 측 압력 ③ SCA 가격 천장(매출 약 40%)이 가격 상승을 제한한다. **하방이 완만한 이유**: ④ REM: SCA 하한가가 "a very robust gross margin … well above our peak quarterly margins in any past cycle"을 보장 → 매출 약 40%의 GM 하락이 막힌다 ⑤ CF 역사: 첫 하강 연도의 연간 GM 하락은 FY16 −12.0pt · FY19 −13.2pt · FY20 −15.2pt(분기 약 −3~−4pt). FY23은 −54pt(재고평가손 포함 꼬리) | 비대칭 방향 **E** / −2.5·+0.5 크기 **D** | −2.5pt는 "약 60%는 과거 하강 속도(분기 −3~−4pt), 약 40%는 하한 보호"의 **어림 가중**이다. 계산식으로 공시하지는 않았다. **제안**: 이 산식을 부록에 명시한다. FY23형 꼬리는 bear 밖이라고 적는다. 또 ②는 **base 보합 가정도 약하게 만든다**(원가 상승 + 가격 보합 = GM 소폭 하락). base를 분기 −0.5pt로 할지 검토한다 |
| 4 | opex 30:33:37 | REM: "increase by approximately $1 billion in fiscal 2027 … weighted to second half" | 총액 **D** / 배분 **J** | 배분 비율은 "하반기 > 상반기"를 만족하는 임의값이다. 영향: 연간 합계는 고정이라 **분기 EPS 경로에만** 작게 영향을 준다(GAAP opex $100M = EPS ∓$0.075, FROZEN §(f-2)). **제안**: 최소 가정인 **선형 증가**(FQ2<FQ3<FQ4 등차)로 바꾼다. 또 +$1B의 basis가 비GAAP일 수 있다는 점을 유지 공시한다 |
| 5 | 자사주 미반영 | REM: 2026-12-09부터 "increase our capital return … return 100% of our excess cash" — 규모·형태·시점이 없다. 주식수로 바꾸려면 매입 가격 가정이 필요하다. 그러면 발표 후 주가가 가정에 들어가 순환이 생긴다. 계획 §4-3의 순현금 roll-forward도 자사주를 제외한다 | 규칙 **E**(계획 정합) | 유지. EPS 상방이 빠지는 한계를 부록과 §8에 공시한다 |
| 6 | FY28 | ① REM: "industry supply to improve gradually in 2028" + "tight beyond calendar 2027" → FY28(2027-09~2028-08)은 공급 완화가 시작되는 구간이다 ② CF 역사 — 하강 첫해 매출: FY16 **−23.4%**, FY19 **−23.0%**, FY23 **−49.5%** / GM: 위 3번 ⑤ | bear 크기 **D** / base·bull **J** | bear −25%·GM −15pt는 과거 **통상 하강 첫해**(−23%, −12~−15pt)에 맞췄다. FY23형(−49%)은 꼬리로 두고 bear에 넣지 않았다. **base 0%·−3pt와 bull +10%는 판단값**이다. opex +8%는 FY27 증가율의 약 절반으로 잡은 **판단값**이다 |
| 7 | capex 배수 1.10→1.25 | REM: "quarterly capex in fiscal 2027 to be above fiscal Q4 levels"(FQ4 약 $10B) · 증가분의 절반 이상이 건설 capex | 하한 **E** / 배수 **J** | 공시는 **하한**(분기 > FQ4)만 준다. 배수는 판단이다. capex는 EPS가 아니라 **FCF·순현금에 크게** 영향을 준다. **제안**: base = 하한에 가까운 **FQ4 × 1.05 보합**(보수적). 콜에서 FY27 capex 수치 가이드가 나오면 그 값으로 대체한다(기존 규칙) |

**요약 — 등급 분포와 v1 제안**
- **E(공시 직접)**: A1 앵커 규칙 · A5 · A6 · A7(자사주 제외) · A11–A13 · A15–A17. 모두 기계적 규칙이거나 실제치다.
- **D(방향만 공시)**: A2 방향 · A3 비대칭 · A4 총액 · A8 bear · A14 하한.
- **J(판단)**: 확률 · A2 크기 · A4 배분 · A8–A10의 base/bull · A14 배수.
- v1 제안(Jiwon 승인 대상):
  - (a) 확률 삭제
  - (b) A2를 비트×ASP로 분해
  - (c) A3 bear 산식 명시 + base 원가 반영 검토
  - (d) A4 선형 증가
  - (e) A14 base 하한 근처

---

## 부록 R7. RLE 가정 근거 독립 재검증 (Codex, 2026-09-29)

> 🔴 **투자 자문 아님.** 이 단계는 **문서 산출물만** 만든다. 코드·YAML·계획은 수정하지 않는다.
> 기준 문서: 이 핸드오프(부록 R6 포함)와 계획 rev-4.2 `32fc96ed…5734`.

### R7-1. 목적

부록 R6의 RLE 가정 규칙 A1–A17과 Claude의 근거(R6-5)가 **공시로 뒷받침되는지**, **내적으로 일관되는지**, **더 나은 도출 방법이 있는지**를 Codex가 독립적으로 판정한다. Jiwon이 ★ 판단값을 정하기 전에 근거의 질을 검증하는 것이 목적이다.

### R7-2. 블라인드 순서

1. **V1 (독립 평가)**: R6-2(규칙표)와 R6-1(기호)만 읽는다. **R6-5(Claude 근거)는 읽지 않는다.** 가정마다 다음을 적는다.
   - 허용 입력에서 찾은 근거(원문 쪽·문장, 15단어 미만 인용)
   - 등급: E(방향·크기 모두 공시) / D(방향만) / J(판단)
   - 대안 도출 방법(있으면)
   - V1 파일을 저장하고 SHA를 기록한다.
2. **V2 (대조)**: 그다음 R6-5를 읽고 Claude 근거를 항목별로 판정한다.
   - **인용 원문 일치**: REM·FROZEN·CF에서 직접 확인한다.
   - **논리 타당성**
   - **등급 동의 여부**
   - **v1 제안 (a)–(e) 각각 수용/반박**

### R7-3. 허용 입력 (읽기만)

- E2-A allowlist 20개: 특히 `logs/mu_ho5_Q3_remarks.pdf`, `forecast/reports/mu_fy2026q4_forecast_FROZEN.md`, `forecast/reports/.cache/edgar_companyfacts_CIK0000723125.json`, 10-K 2개, 보도자료 11개
- `forecast/profiles/mu.generic.yaml`
- 조사 표본(`logs/sellside_survey/**`)의 **수치는 쓰지 않는다**(형식 조사 전용 규칙 유지).
- 웹 검색 결과를 근거로 쓰려면 URL·조회 시각을 남기고 **보조 근거**로만 표시한다(허용 입력이 아님).

### R7-4. 반드시 검사할 것

1. 모든 인용 문장의 **원문 일치**(공백 정규화 후 부분 문자열).
2. CF 역사 수치(FY16·FY19·FY20·FY23 매출·GM 변화율)의 **재계산**. companyfacts의 `frame` 표기와 회계연도의 대응도 확인한다.
3. **A2 암묵 ASP 검사**: 비트 증가 가정(산업 비트 가이던스를 분기로 환산)을 두면 base 경로 +3/+2/+1%가 함의하는 ASP 변화율을 계산한다. "tight beyond calendar 2027"과 정합한지 판정한다.
4. **A3 bear 산식 검사**: "약 60% 과거 하강 속도 + 약 40% 하한 보호" 어림이 −2.5pt/분기와 맞는지 계산한다. 하한 보호 비중 40%가 "SCA 전부 체결 시"라는 조건부 수치라는 점을 반영해 판정한다.
5. **내적 일관성**: 같은 시나리오 안에서 성장(A2)·GM(A3)·capex(A14)·FY28(A8–A10)이 같은 세계관인지 본다. 예를 들어 bull 성장 + bear GM 같은 조합이 없는지.
6. **계획 정합**: 계획 §4-4 경로·§4-5 금지 필드·§7 스코프(BU/HBM 수요 모델 금지)·D2 YAML 머리 키와 충돌하는지.
7. **민감도 순위**: 각 가정이 FY27E EPS·FCF에 주는 영향의 대략 순위. 근거가 약한(J) 가정 중 **영향이 큰 것**을 우선순위로 표시한다.

### R7-5. 산출물

| 파일 | 내용 |
|---|---|
| `forecast/REVIEW_CODEX_mu_report_rle_r1.md` | §1 V1 독립 평가표(A1–A17) → §2 V1 SHA → §3 V2 대조(R6-5 항목 1–7) → §4 v1 제안 (a)–(e) 판정 → §5 추가 제안 → §6 Jiwon에게 올릴 결정 목록 |

- 번호는 1번부터 빠짐없이 매긴다. LF, 원자적 쓰기, 종료 후 NUL 스캔. git 쓰기 금지.
- **허용 경로**: 위 파일 1개 생성뿐이다.

---

## 부록 R8. A2 — FY27 FQ2–FQ4 주당 매출 성장 경로 독립 도출 (Codex, 2026-09-30)

> 🔴 **투자 자문 아님.** 이 단계는 **문서 산출물 1개만** 만든다. 코드·YAML·계획은 수정하지 않는다.
> **시한**: FQ4 발표 **2026-10-01 05:01 KST 전**에 제출한다. RLE 규칙 사전등록이 목적이므로, 발표 뒤 정보가 섞이면 이 작업의 의미가 사라진다.
> 기준: 계획 rev-4.2 `32fc96ed…5734` · `forecast/REVIEW_CODEX_mu_report_rle_r1.md` `bc14b948…eee4b` · `forecast/REVIEW_CLAUDE_mu_report_rle_r1.md`

### R8-1. 과제

A2(FY27 FQ2·FQ3·FQ4의 **주당** 매출 성장 $g_{week}$, 각 13주)의 **bear / base / bull 경로**를 Codex가 **스스로 자료를 모아** 도출한다. FQ1은 A1(가이던스 앵커)로 이미 정해져 있다. 그 뒤 세 분기의 모양과 크기를 정하는 것이 과제다.

### R8-2. 🔴 "중립" 편향 금지

1. **0%·보합·중간값은 기본값이 아니다.** 불확실하다는 이유만으로 0%나 "변화 없음"을 고르지 않는다. 0%도 +3%나 −5%와 **똑같이 근거를 대야 하는 방향성 판단**이다. 비트가 늘어나는 세계에서 매출 0%는 가격 하락을 뜻한다(`REVIEW_CODEX_mu_report_rle_r1.md` §1.4 산술).
2. 증거가 **방향**을 가리키면, 크기도 그 방향을 반영해야 한다. 방향 증거를 인정하면서 크기만 0 쪽으로 줄이면(shrinkage), 그 줄인 폭과 이유를 수치로 밝힌다.
3. "중립"이라는 단어를 쓸 때는 **무엇에 대해 중립인지**(매출 수준 / 최근 성장 추세 / 가격 / 비트)를 반드시 적는다.
4. base는 "가장 그럴듯한 경로"이지 "가장 안전해 보이는 경로"가 아니다. base를 bear 쪽으로 기울였다면, 그렇게 판단한 **증거**가 있어야 한다.

### R8-3. 블라인드

- **Claude의 기존 제안값**(부록 R6 A2)과 **Jiwon의 선호**는 이 과제의 **입력이 아니다.** 결론(§R8-6의 1–4)을 저장하고 SHA를 기록한 **뒤에** 비교한다(§R8-6의 5). R6·R7에서 이미 본 값은 앵커로 쓰지 않는다고 스스로 선언한다.
- Jiwon의 선호는 Codex 제출 후 Claude가 공유한다.

### R8-4. 반드시 수행할 분석 (최소 4개 참조군)

| # | 참조군 | 할 일 |
|---|---|---|
| 1 | **회사 가이던스 모멘텀** | FROZEN §(d-1)의 가이던스·실적 이력과 보도자료에서 **가이드된 주당 성장률의 추이**를 계산한다(예: FQ3 가이드 대비 FQ2 실적, FQ4 가이드 대비 FQ3 실적 — FQ4는 14주이므로 주당 정규화). 감속 비율을 구하고, 그 감속이 이어질 때의 FQ2–FQ4 경로를 계산한다 |
| 2 | **과거 상승 사이클 후반부 유추** | companyfacts 분기 매출로 MU의 **과거 상승 사이클 정점 전후 분기 성장률**(예: FY2017–FY2018 등)을 추출한다. 성장률이 어떤 속도로 감속했는지, 정점 직전 몇 분기가 양(+)이었는지 본다. 현재 구조(SCA·HBM)와 다른 점을 적는다 |
| 3 | **가격·비트 진단**(입력 아님) | 준비문의 산업 비트 가이던스와 FQ3 비트·가격 진술로, 후보 경로마다 **암묵 ASP 변화율**을 계산해 "tight beyond calendar 2027"·"meaningful moderation in the rate of price increases"와 어느 경로가 정합한지 판정한다. 계획 §7에 따라 이 분해는 **진단으로만** 쓴다 |
| 4 | **SCA 가격 구조** | 준비문의 SCA 천장(CQ2 시장가)·하한·고정가 서술과 "all planned SCAs" 조건을 반영한다. FY27에 가격 상방이 막히는 매출 비중이 **현재 기준으로 어느 범위인지**(조건부 40%를 그대로 쓰지 말 것) 판정하고 성장 경로에 미치는 방향을 적는다 |
| 5 (선택) | **외부 공개 자료** | 공개 산업 자료(예: 메모리 계약가 전망 보도자료, 경쟁 메모리사의 공개 실적 코멘트)를 쓸 수 있다. **보조 근거**로만 표시하고 URL·조회 시각·발행일을 남긴다. 셀사이드 조사 표본(`logs/sellside_survey/**`)의 수치는 쓰지 않는다. **정보 컷오프 = 2026-10-01 05:01 KST 이전 공개분**만 쓴다 |

### R8-5. 도출 규칙

1. 참조군마다 FQ2·FQ3·FQ4 경로 후보를 **숫자로** 낸다.
2. 참조군 간 차이를 표로 비교하고, base를 어떻게 합성했는지 **식이나 가중 이유**로 적는다(예: "1과 2의 평균, 3으로 정합성 확인"). 임의 반올림은 0.5%p 단위까지만 허용한다.
3. bear/bull은 base 대칭이 아니어도 된다. 비대칭이면 그 근거를 적는다. bear는 "가격 하락이 시작되는 세계", bull은 "공급 부족이 가격을 계속 끌어올리는 세계"처럼 **서술 가능한 세계관**이어야 한다.
4. 각 경로의 **등급**(E/D/J, 입력과 규칙 분리)과 **민감도**(base 대비 ±1%p/분기 변경 시 FY27E 매출·GAAP EPS 변화, 계획 §4-4 경로 기준 근사)를 적는다.
5. A3(GM)과의 **정합성**: 선택한 base 성장 경로가 함의하는 가격 방향이 GM 보합과 모순되지 않는지 확인하고, 모순이면 A3 base 조정 방향을 제안한다.

### R8-6. 산출물

`forecast/REVIEW_CODEX_mu_report_rle_r2.md`
1. 참조군별 분석(§R8-4 1–4, 5는 선택)
2. bear/base/bull 경로 표 + 합성 근거 + 등급
3. 민감도 · A3 정합성
4. "중립 편향 점검" 자기 선언(§R8-2 네 항목을 어떻게 지켰는지)
5. **(결론 저장·SHA 기록 후)** 기존 후보와 비교: ① 0/0/0% ② +3/+2/+1% ③ Codex 도출값 — 차이의 원인
6. 결론 SHA(5번 추가 **전**)와 최종 SHA

- 번호는 1번부터 빠짐없이 매긴다. LF · 원자적 쓰기 · NUL 스캔. git 쓰기는 하지 않는다.
- **허용 경로**: 위 파일 1개 생성뿐이다.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

---

## 부록 R9. RLE 가정 규칙 v1 확정 기록 (Claude, 2026-10-01)

> 🔴 **투자 자문 아님.** 확신도 하(low). 이 부록은 규칙만 기록한다. 숫자는 발표 후 입력값으로만 채운다.

### R9-0. 기록 시점 — 정직 공시

1. 이 부록은 **2026-10-01 09:25 KST**, 즉 FQ4 발표(05:01 KST) **이후**에 파일로 쓰였다. 계획한 "발표 전 SHA 기록"은 지키지 못했다.
2. 규칙 내용은 발표 전에 정해졌다. 근거 사슬은 다음과 같다.
   - `forecast/REVIEW_CLAUDE_mu_report_rle_r1.md` §3 v1 합의안(2026-09-29).
   - `forecast/REVIEW_CODEX_mu_report_rle_r2.md`(SHA `5bca5418…6cc`, 파일 시각 2026-09-30 10:28 KST).
   - Claude 검토 대화(2026-09-30)와 Codex 회신(2026-09-30 11:28 KST). 둘 다 A2 base +4.0/+3.5/+3.0%와 A3 base −0.5pt/분기를 권고했다.
   - Jiwon 승인(대화). 승인 시각은 파일로 증명되지 않는다.
3. 기록 시점에 `logs/mu_postprint_*` 파일은 없었다. Claude는 FQ4 실적·FQ1 가이던스를 보지 않았다.
4. 따라서 사전등록 증거는 **파일 시각이 아니라 대화 기록**이다. 리포트 부록에 이 한계를 그대로 공시한다.

### R9-1. 승인 내역 (Jiwon)

1. **A2 base**: FQ2/FQ3/FQ4 주당 성장 **+4.0% / +3.5% / +3.0%**.
   - 도출: R8 Codex 합성에서 가격×비트 후보(계획 §7 위반)를 빼고 40/25/15를 비례 재조정했다.
   - 등급: 입력 E/D, 규칙 J. SCA 후보가 과거 사이클 후보에서 파생되어 독립성이 약하다.
2. **A3 base**: FQ1 = $M_1$, 이후 분기당 **−0.5pt**. 등급: 방향 D, 크기 J.
   - 근거: A2 base의 암묵 ASP가 완만히 하락하고, 준비문은 비트당 원가 상승을 말한다.
3. **고정 방식**: SHA 기록만 한다. 커밋은 E4에서 한다.

### R9-2. v1 규칙표 (A2 base·A3 base 외에는 rle_r1 §3 합의 그대로)

| # | v1 규칙 | 등급(입력 / 규칙) |
|---|---|---|
| A1 | FQ1 = bear $G_1^{lo}$ · base $G_1(1+b_{med})$ · bull $G_1(1+b_4)$. 대안(base = $G_1$)은 민감도 행 | E / J |
| A2 | bear −10/−8/−5% · **base +4.0/+3.5/+3.0%** · bull +8/+5/+3% · 암묵 ASP 진단 각주(입력 아님) | E·D / J |
| A2′ | FQ1 주당 방향이 DECLINE이면 0/−3/−3% 경로를 **병렬 표시**(자동 전환 없음) | E / J |
| A3 | FQ1 = $M_1$(±1pt) · **base 분기당 −0.5pt** · bear −2.5pt/분기 · bull +0.5pt/분기(상한 90%) · FY23형 꼬리는 범위 밖 | E / J |
| A4 | $T$ = FY26A×52/53 + 1,000 · 30:33:37 · basis 가정 공시 | D / J |
| A5 | −0.228% × 매출 | E / J |
| A6 | 역산 잔차(같은 basis 확인 시만), 아니면 15% ± 1.5pt 민감도 | D / J |
| A7 | $S_1$ 보합 · 자사주 0 · 주식수 −1%/−3% 민감도 | E / J |
| A8–A10 | FY28 무가중 스트레스 범위: 매출 −25/0/+10% · GM −15/−3/0pt · opex +8% | D / J |
| A11 | 상각률 $d$(FY26A 갱신, 없으면 FY25 19.35%) ± 2pt | E / J |
| A12 | SBC/opex 최근 3년 중앙값 | E / J |
| A13 | BS 정의 k 재계산 후 사용(재현 전 보류) | E / J |
| A14 | FQ4A × 1.05 평평 · 시나리오 공통 · ±5/±10% 민감도 · FY27 가이드 나오면 대체 | E(하한) / J |
| A15–A17 | 변경 없음 | E / — |
| 확률 | 없음(삭제) | — |

### R9-3. 민감도 행 (리포트에 병기)

1. A2 **기존 둔화 후보** +3/+2/+1% (Claude R6 v0 원안; Jiwon이 지지 의견을 냈으나 채택되지 않음).
2. A2 **변화 없음** 0/0/0%. 암묵 ASP 약 −5%/분기를 각주로 단다.
3. A2 Codex R8 원안 +4.5/+4.0/+3.0%.
4. A3 **GM 보합**(상방 민감도).
5. 히트맵 ⑦ 축: A2 base 오프셋 × A3 FY27 GM(계획 §4-5).

### R9-4. 알려진 한계

1. **bull FQ4(+3%) = base FQ4(+3%)**: v1 bear/bull은 rle_r1 합의값을 그대로 두었다. base 상향으로 bull과 base가 FQ4에서 겹친다.
   - R8 Codex 대안(bear −5.5/−8.0/−5.5%, bull +11/+8/+6%)은 발표 전 제안이지만 승인되지 않았다.
   - 발표 후 바꾸면 `사후 변경 — 사유`로 기록하고 리포트에 공시해야 한다.
2. 가중치(40/25/15)는 J다. 가이던스 비중 20–70%에서 base는 약 +5.5/+5.0/+4.5% ~ +3.0/+2.0/+1.5%로 움직인다.
3. 사전등록 시점 증거가 대화 기록뿐이다(R9-0).

### R9-5. 다음 단계

1. Claude: 이 부록 SHA를 대화에 기록한다.
2. 발표 후: R6-1 기호 값을 `logs/mu_postprint_*` 원문에서 넣는다. 규칙은 바꾸지 않는다.
3. Codex: RLE YAML 작성 시 이 표를 그대로 옮긴다.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*

---

## 부록 R10. 발표 후 입력 경로 이동(rev-4.3) + E2-B 핀 기록 (Codex, 2026-10-01)

> 🔴 **투자 자문 아님.** 계획 rev-4.3 `99de31cb…4492`(보존 사본 `forecast/PLAN_mu_report_fy2026q4_rev4.2_superseded.md` = rev-4.2 `32fc96ed…5734`).

### R10-1. 배경 (J-7)

Jiwon 결정: 원자료는 **회사·분기 폴더**에 모은다. rev-4.3은 E2-B·E2-C 예약 경로만 `logs/mu_postprint_*` → `logs/mu/fy2026q4/postprint/*`로 바꾼다. E2-A 입력 20개는 **그대로**다(이동은 ed1 E4 이후 별도 작업).

### R10-2. 확보된 원본 (Jiwon 브라우저 저장, "HTML만", Claude 확인)

| 예약 경로 | sha256 | 확인 내용 |
|---|---|---|
| `logs/mu/fy2026q4/postprint/8k_index.html` | `bda394e8b8f41e492a0051b11b92a9469c2bdac5d280e273763b8946519861e4` | Accession `0000723125-26-000018` · Form 8-K · Filing Date 2026-09-30 · Accepted 2026-09-30 16:02:22 (ET, = 2026-10-01 05:02:22 KST) · Item 2.02·9.01 · 문서 13개 |
| `logs/mu/fy2026q4/postprint/ex991.htm` | `5dad1ce5c2dd8958dad947ab1f12a1015bfcc29c7e8a29e48379e983f425120e` | `<TYPE>EX-99.1` · `a2026q4ex991-pressrelease.htm` · "saved from url" 주석 없음(원본 바이트) |
| `logs/mu/fy2026q4/postprint/remarks.pdf` | `2821d4ccaae50b40dcd28cd4e766c69c509e73d666e4109d5907c7205a03b700` | "Fiscal Q4 2026 Earnings Call Prepared Remarks" · 10쪽 |
| `logs/mu/fy2026q4/postprint/price_2026-10-01_src1.<ext>` · `_src2.<ext>` | 미확보 | 2026-10-02 05:00 KST 이후 Jiwon 캡처. 확장자는 실제 파일에 맞춘다 |

- 첫 저장본("완전히" 저장, iXBRL 뷰어 화면)은 `logs/_to_delete/mu_fy2026q4_postprint_v0/`로 옮겼다. **입력으로 쓰지 않는다.**

### R10-3. Codex 작업

1. 계획 rev-4.3 diff가 **경로 3곳 + 리비전 행 + 제목**뿐인지 확인한다(`diff` rev4.2_superseded ↔ 현행).
2. `forecast/scripts/mu_report/input_pins.yaml` E2-B·E2-C 경로를 rev-4.3으로 바꾸고, 위 3개 SHA를 **직접 재계산해** 기록한다. 가격 2개·SCORED는 `null` 유지(가격 확장자는 확보 시 확정).
3. 코드·테스트에서 `mu_postprint` 문자열을 찾아 rev-4.3 경로로 맞춘다(`forecast/tests/test_mu_report.py:306` 포함). MU 테스트와 forecast 전체 테스트를 실행한다.
4. 산출물: `forecast/REVIEW_CODEX_mu_report_pins_r1.md` — §1 rev-4.3 diff 판정 · §2 SHA 재계산 결과 · §3 변경 파일 목록과 SHA · §4 테스트 결과.

- **허용 경로**: `input_pins.yaml`, `mu_postprint`를 담은 코드·테스트 파일, 위 리뷰 파일 1개. git 쓰기 금지. LF·NUL 0 확인.
- 🔴 이 단계에서 FQ4 실적 수치를 해석·채점하지 않는다. 채점은 별도 SCORED 핸드오프에서 한다.

---

## 부록 R11. E2-B 입력 게이트 ①–③ 핀 완료 (Codex, 2026-10-04)

> 🔴 **투자 자문 아님.** 계획 rev-4.3 §6 E2-B 입력 게이트.

### R11-1. 새로 확보된 입력

| 예약 경로 | sha256 | 확인 |
|---|---|---|
| `logs/mu/fy2026q4/postprint/price_2026-10-01_src1.png` | `94e27d513188a89d3f02cabfe56e59eefd51e84c58e90a876666aa7c9a1f2622` | Nasdaq Historical Quotes, 10/01/2026 행 Close **$1,097.39** · O 1,054.08 · H 1,098.90 · L 1,022.90. 🔴 상단 박스의 "$1,074.89 · Oct 1, 2026"은 **10/02 종가**(표기 오류) — 쓰지 않는다 |
| `logs/mu/fy2026q4/postprint/price_2026-10-01_src2.png` | `e21769878c2b21fb873b32cb0547cae1580c5c826324938c95fd9c8690f5fa6b` | Yahoo Finance Historical, Oct 1, 2026 행 Close **1,097.39** · Adj Close 1,097.39 · O/H/L 동일 |
| `forecast/reports/mu_fy2026q4_SCORED.md` | `0f6e6a951dc57d95b8846dbc8588d42b2ac2925f1c52b54cc80e9a2a027af4f9` | **commit `0303206`** (Jiwon 호스트, 2026-10-04). Codex 검증 PASS `c25a2f3c…7011` |

- 두 경로 종가 일치 → 기준 주가 **$1,097.39**(2026-10-01 Nasdaq 정규장 종가). 분할 없음.
- 🔴 SHA는 **디스크 파일 기준**이다. 대화 첨부본과 바이트 인코딩이 달라 Claude가 처음 보고한 `059e485b…`·`50e6c86f…`는 폐기한다(픽셀 비교 결과 두 이미지 내용은 동일).
- 캡처 시각: 2026-10-04 KST(Jiwon 브라우저). 두 화면 모두 다음 거래일(10/02) 행이 함께 보여 10/01 값이 확정 종가임을 뒷받침한다.

### R11-2. Codex 작업

1. 위 3개 SHA를 **직접 재계산**하고 `forecast/scripts/mu_report/input_pins.yaml` E2-B의 가격 2행(`<ext>` → `.png`)과 SCORED 행을 채운다. SCORED 행에 `commit: 0303206`을 기록할 수 있는 스키마가 없으면 주석 대신 리뷰 문서에 적고 스키마는 바꾸지 않는다.
2. `git cat-file -p 0303206:forecast/reports/mu_fy2026q4_SCORED.md | sha256sum`이 위 SHA와 같은지 확인한다.
3. 계획 rev-4.3 §6 E2-B 게이트 ①–⑥ 상태표를 작성한다(⑥ J-2 확인 레코드는 렌더 24시간 전 Jiwon 확인 대기).
4. MU 테스트 재실행. 산출물 `forecast/REVIEW_CODEX_mu_report_pins_r2.md`.

- **허용 경로**: `input_pins.yaml`, 위 리뷰 파일 1개. git 쓰기 금지. 🔴 RLE 가정 숫자 산출·E2-B 렌더는 하지 않는다(A3·A4 충돌 결정 대기).

---

## 부록 R12. RLE v1 사후 변경 — 사유 + 가정 YAML 작성 (2026-10-04)

> 🔴 **투자 자문 아님.** 이 부록은 **발표 후** 변경이다. 규칙 v1(R9)은 그대로 남기고, 아래 3건만 바꾼다. 리포트 부록에 이 표를 **그대로 공시**한다.
> 승인: Jiwon, 2026-10-04 (대화). 근거 입력: `remarks.pdf` `2821d4cc…b700` · `ex991.htm` `5dad1ce5…120e`.

### R12-1. 사후 변경 3건

| # | v1 규칙 (발표 전) | 변경 (발표 후) | 사유 (원문 근거) | 등급 |
|---|---|---|---|---|
| A3 base | FQ1 = $M_1$, 이후 분기당 **−0.5pt** | FQ1 = $M_1$, 이후 **보합** (= R9-3에 발표 전 등록된 상방 민감도 행을 base로 승격). −0.5pt는 "사전등록 원안" 민감도 행으로 유지 | 준비문 p.9: FQ1이 FY27 GM의 **바닥**, 이후 분기 GM은 더 높다고 명시. 원안은 회사 진술과 방향이 반대. 새 숫자를 만들지 않고 발표 전 등록된 대안으로 교체 | 방향 E(회사 진술) / 크기 J(보합은 상승폭 미공시라 보수적) |
| A4 | $T$ = FY26A GAAP opex × 52/53 + 1,000 | $T$ = (FY26A **비GAAP** opex 6,841 + **2,500**) + 253 × 4 = **10,353**. FQ1 = $X_1$ = 2,310, 나머지 8,043을 30:33:37 → **2,413 / 2,654 / 2,976** | 준비문 p.9: FY27 opex 약 **$2.5B 증가**(문서 기본 basis = 비GAAP). GAAP 환산 가산 253 = FQ1 가이던스 GAAP−비GAAP opex 차(SBC R&D 166 + SG&A 87). FY26A GAAP의 일회성(특허 500 등)은 기준에서 제외됨 | 증가액 E(비GAAP) / GAAP 환산·배분 J |
| A14 | FQ4A × 1.05 평평 · 가이드 나오면 대체 | **대체 조항 적용**: FQ1 **11.5** · FQ2 **13.5** (상반기 25.0 − 11.5) · FQ3 **12.5** · FQ4 **12.5** ($B). FY27 = 50.0. FY28 = FY27 합계 | 준비문 p.10: FQ1 약 $11.5B, 상반기 약 $25B, 하반기 "더 높음". 하반기 = 상반기는 **하한**(FCF 과대 쪽 편향, 공시). ±5/±10% 민감도 유지 | FQ1·상반기 E / 하반기 J(하한) |

- 🔴 하반기 capex 하한 선택으로 FQ3·FQ4(12.5)가 FQ2(13.5)보다 낮게 보인다. 분기 배분이 아니라 **반기 합계**가 근거라는 점을 각주로 단다.
- 그 밖의 규칙(A1·A2·A2′·A5–A13·A15–A17)은 R9 그대로다. A2′는 FQ1 주당 방향 `GROWTH`(+22.13%, SCORED §8)라 병렬 경로를 그리지 않는다.

### R12-2. 발표 후 입력값 (R6-1 기호)

| 기호 | 값 | 출처 |
|---|---|---|
| $G_1$ / $G_1^{lo}$ / $G_1^{hi}$ | 61,500 / 60,000 / 63,000 | EX-99.1 Business Outlook |
| $M_1$ | 85.95% (GAAP) | 같음 |
| $X_1$ | 2,310 (GAAP) | 같음 |
| $S_1$ | 1,150M | 같음 각주 |
| GAAP EPS 가이던스 | $37.84 ± $1.00 | 같음 (A6 역산 잔차용) |
| $A_4$ | 54,229 (14주) | EX-99.1 |
| $b_{med}$ / $b_4$ | **+5.75% / +16.45%** | SCORED §4 (11분기·FY26 Q1–Q4) |
| FY26A 3표 | EX-99.1 손익·재무상태·현금흐름 | 10-K 전 provisional |

### R12-3. Codex 작업

1. `forecast/inputs/mu_fy2026q4_report_assumptions.yaml` 작성 — 계획 D2 머리 키(`confidence: low` 등) + R9 v1 표 + R12 변경 3건(`post_print_change` 블록: 원안·변경·사유·근거 쪽) + R12-2 입력값. 각 값에 `source_id`.
2. A6: GAAP EPS 가이던스 37.84와 $G_1$·$M_1$·$X_1$·A5·$S_1$로 세율 역산 잔차를 계산해 YAML과 리뷰에 기록(basis 동일성 확인; 실패 시 15% ± 1.5pt).
3. A13 k: BS 정의(`AR + Inventory − AP − 기타 영업 유동부채`)로 재계산 가능한지 판정. 3개년 BS가 allowlist에 없으면 `UNAVAILABLE`로 두고 사유 기록(추정 금지).
4. 숫자 산출 결과를 `forecast/REVIEW_CODEX_mu_report_rle_values_r1.md`에 표로: FY27E 분기 매출·GM·opex·영업이익·EPS(bear/base/bull) + 민감도 행(A2 기존 둔화 후보 +3/+2/+1, 0/0/0, Codex R8 원안, A3 −0.5pt 원안).
5. 테스트 실행. **렌더하지 않는다**(본문 2·8·10·11절은 Claude 작성 대기, J-2 레코드 대기).

- **허용 경로**: 위 YAML 1개, 리뷰 1개, YAML 로더 테스트가 요구하면 `forecast/tests/**` 최소 수정. git 쓰기 금지.

---

## 부록 R13. R12 검증 결과 반영 — A11 해석 확정 + 로더 계약 정렬 (Codex, 2026-10-04)

> 🔴 **투자 자문 아님.** 기준: YAML `2c467f10…92f1` · 리뷰 `57733f6d…0ded`.

### R13-1. Claude 독립 재계산 (R12 리뷰 대조)

A6 역산 세율 13.6742% · A1 base FQ1 65,036.25 · FY27E 매출/GAAP EPS — base 274,784.14 / 169.05 · bear 210,876.00 / 118.95 · bull 313,826.03 / 199.52 · A3 원안 민감도 EPS 167.46 · A13 k 3개년(3.448% / 0.432% / 13.414%, 중앙값 3.448%) — **전부 일치**.

### R13-2. A11 해석 확정 — `UNAVAILABLE` 해제

- Codex는 "roll-forward에 gross capex가 필요한데 가이드는 net"이라는 이유로 projected D&A를 `UNAVAILABLE`로 두었다.
- 그러나 FY25 10-K(`logs/_claude_scratch/mu-20250828.htm`, E2-A allowlist) 주석은 **자본적 지출 관련 정부 인센티브가 PP&E를 감액한다**고 적는다(p.87 부근, "reduced property, plant and equipment"). 즉 재무상태표 PP&E 자체가 **인센티브 차감 후** 잔액이다.
- 따라서 BS PP&E와 정합하는 roll-forward 입력은 **net capex**다. R6 표의 "gross capex"는 표기 오류로 보고, 다음처럼 확정한다(규칙 변경이 아니라 **해석 정정**, 부록 공시):
  $PPE_t = PPE_{t-1} + \text{net capex}_t - DA_t$, $DA_t = d \times \overline{PPE}$, $d$ = FY26A 17.294%.
- 한계(공시): 인센티브 수령과 PP&E 감액의 **시차**(비유동 미실현 정부 인센티브 계정 786)는 무시한다. J.

### R13-3. Codex 작업

1. YAML A11을 위 식으로 채우고(분기 $d/4$, 평균 PPE는 기초·기말 평균), FY27E 분기 D&A·PPE를 산출한다. `post_print_change`가 아니라 `interpretation_note`로 기록.
2. FY27E FCF(base/bear/bull): $CFO = NI + D\&A + SBC - k\,\Delta Rev$, $FCF = CFO - \text{net capex}$. 배당·순현금 roll-forward(A15·계획 §8-7)까지 표로.
3. `rle.py::load_assumptions_text()`를 **계획 D2 머리 계약 + 값별 `source_id` + `post_print_change`·`interpretation_note` 블록**을 읽도록 정렬한다. E2-A fixture는 새 계약 형식으로 갱신하거나, 구 형식은 명시적 오류로 거부한다(조용한 하위 호환 금지).
4. 테스트: 로더가 실제 YAML을 읽고 R12 값(base FY27 EPS 169.05 ±0.01 등)을 재현하는 테스트 1개 이상 추가. MU·forecast 전체 실행.
5. 산출물: `forecast/REVIEW_CODEX_mu_report_rle_values_r2.md` (§1 A11·D&A 표 · §2 FCF·순현금 · §3 로더 diff 요약 · §4 테스트).

- **허용 경로**: YAML, `forecast/scripts/mu_report/rle.py`, `forecast/tests/test_mu_report.py`, `forecast/tests/fixtures/mu_report/**`, 위 리뷰 1개. git 쓰기 금지. **렌더하지 않는다.**

---

## 부록 R14. 본문 서술 연결 + E2-B ed1 렌더 (Codex, 2026-10-04)

> 🔴 **투자 자문 아님.** 기준: RLE YAML `292f4dce…c539` · R13 리뷰 `8012d34a…fa74a` · 서술 초안 `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` `e64613ca…1dfe`.

### R14-0. R13 검증 (Claude 독립 재계산)
FY27E D&A 14,095.88(분기 2,922.61 / 3,327.93 / 3,737.25 / 4,108.09) · FCF bear/base/bull 100,181.18 / 155,589.28 / 189,282.74 · 기말 순현금(SCA 예치금 미조정) 167,765.18 / 223,173.28 / 256,866.74 · 기초 68,274(회사 준비문 p.9 "net cash $68.3B"와 일치) — **전부 일치. PASS.**
ΔNWC는 연간 매출 변화 × k(FY27E − FY26A 연간)로 적용했음을 부록 각주에 적는다.

### R14-1. 작업
1. **서술 연결**: `narrative_ed1.yaml`의 thesis·scenarios·risks·catalysts를 2·8·10·11절 본문으로 렌더한다(KO/EN 같은 구조). 나머지 절은 기존 표·차트 + 짧은 연결 문장. `section_stub`은 ed1 산출물에 **남기지 않는다**(남으면 게이트 실패로 추가).
2. **fact 바인딩**: `fact_bindings` 12개를 manifest fact로 생성(값은 원천에서 **재계산**해 초안 값과 대조, 불일치 시 중단·보고). 서술에 남은 미해결 `{{fact:…}}` 토큰 0 확인.
3. **라벨 정정(r7)**: 차트 ⑧·표의 "조정 전 순현금" → "순현금(SCA 예치금 미조정)" / EN "Net cash (not adjusted for SCA deposits)".
4. **부록**: R9 v1 규칙표 + R12 사후 변경 3건(원안·변경·사유·근거 쪽) + R13 A11 해석 정정 + R9-0 기록 시점 한계 문장(KO/EN).
5. **렌더 순서**: ①~⑤ 준비와 `--phase E2B` 사전 검사(게이트 G-1~G-21, 렌더 제외)까지 먼저 수행 → **`forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml`이 있고 `confirmed_at_kst`가 24시간 이내일 때만** ed1 KO/EN 렌더. 없으면 렌더하지 않고 멈춘다(레코드는 Jiwon 확인 후 Claude가 작성).
6. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r1.md` (§1 서술·바인딩 · §2 게이트 결과 · §3 렌더 산출물 목록·SHA · §4 테스트).

- 🔴 서술 문장 수정 금지. 사실 오류를 발견하면 고치지 말고 리뷰에 적어 Claude에게 넘긴다.
- **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, 계획 §2 D7의 산출물 경로, 위 리뷰 1개. git 쓰기 금지.

---

## 부록 R15. E2-B ed1 렌더 (Codex, 2026-10-04) — ⏰ 마감 2026-10-05 14:42 KST

> 🔴 **투자 자문 아님.** 기준: 사전 게이트 리뷰 `forecast/REVIEW_CODEX_mu_report_e2b_r1.md` `c70e0526…db0b`.

### R15-0. 확인
- R14 사전 게이트(G-1~G-21 비렌더 항목) 검토: **PASS**(Claude). fact 12개 원천 재계산 일치, 서술 무수정 확인.
- 이해관계 레코드 작성: `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` — `status: not_held`, `confirmed_at_kst: 2026-10-04T14:42:00+09:00`, `edition: ed1`. 근거는 Jiwon의 대화 진술(같은 시각). **렌더 시작은 2026-10-05 14:42 KST 이전**이어야 한다. 넘기면 렌더하지 말고 멈춘다(재확인 필요).

### R15-1. 작업
1. `build.py`의 E2B 분기에서 "independently reviewed" 차단을 **이 레코드에 한해** 해제하고, `gate_g12c_conflict`(24h·edition·KO/EN 표지·말미·PDF 모든 쪽 푸터)를 실제로 거치는 렌더 경로를 연다. 레코드 blob SHA·읽은 시각을 감사 기록에 남긴다.
2. ed1 KO/EN 렌더: md·html·pdf·공유 xlsx·manifest json·input_manifest json·차트 PNG(계획 §2 D7 경로).
3. 렌더 후 게이트 전부(G-4~G-6·G-8·G-10~G-13·G-15 parity·G-16·G-17·G-21 포함) 실행. 하나라도 실패하면 산출물을 그대로 두고 실패 목록을 보고한다(수정·재렌더는 Claude 검토 후).
4. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r2.md` (§1 렌더 명령·시각 · §2 게이트 전체 표 · §3 산출물 목록·SHA·쪽수 · §4 테스트).

- 🔴 서술·숫자·규칙 수정 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, 리뷰 1개. git 쓰기 금지.

---

## 부록 R16. E3 r1 — ed1 렌더 결함 수정 + 재렌더 (Codex, 2026-10-04)

> 🔴 **투자 자문 아님.** 기준: R15 리뷰 `forecast/REVIEW_CODEX_mu_report_e2b_r2.md` `2a1dd4ab…2d3d` · KO PDF `3ab25867…149f` · EN PDF `daa3efa9…49bb`.
> 판정(Claude E3, 쪽 이미지 전수 확인): **CHANGES REQUESTED — 배포 불가.** 게이트 2건 실패보다 **게이트가 못 잡은 결함**이 더 크다.

### R16-1. G-15 원인 — 서술 초안 (Claude 수정 완료)
KO/EN 숫자 차이는 코드가 아니라 **Claude 서술의 표기 차이**였다: KO "4분의 3"·"라벨 4개" vs EN "Three-quarters"·"all four"; EN "(1)/(2)"·"Layer 1/2"·"2H CY2027/2028" vs KO "①②"·"하반기". 서술 r2(`forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` `85e4d0c9…df0d`)로 고쳤고, 절별 KO/EN 숫자 multiset 차이 0을 확인했다. 서술 SHA 변경에 맞춰 바인딩 대조만 다시 하라.

### R16-2. 결함 목록 (게이트 통과했지만 배포 불가)

| # | 위치 | 결함 | 요구 |
|---|---|---|---|
| D1 | 표지 시장 데이터 박스 | 기준 주가·발행주식수·시가총액·회계연도 종료일 **UNAVAILABLE** | 기준 주가 $1,097.39(E2-B 핀 2경로)·FQ4 희석주식수 1,147M·시가총액·FY 종료 2026-09-03을 채운다 |
| D2 | 표지 메타 | "발행일: 보유 확인 후 확정", "자료 기준일: 발표 후 입력 포함", "정보 컷오프: 보고서 레이어 가정 기준일" — **자리표시 문구** | 실제 날짜: 발행일(렌더일), 자료 기준일 2026-10-01(주가)·2026-09-30(실적), 정보 컷오프 2026-10-04 KST |
| D3 | 표지 핵심 수치 | 매출 `54229`(천 단위 구분 없음), GAAP EPS가 PREREG 32.57만, FY27E 없음 | 계획 §(표지) 핵심 수치표: FQ4 PREREG_A vs A-8K, FY26E/FY26A, FY27E·FY28E RLE, 숫자 서식 통일 |
| D4 | 3절 "사전등록 대 실적" | **본문 한 문장, 표 없음** | SCORED 인용 표(라벨 4개·밴드·오차·4-lever·SF7)를 넣는다(G-3f: SCORED 원문 대조) |
| D5 | 6절 재무 3표·비율표 | **FY26A-8K·FY27E·FY28E 열 전부 UNAVAILABLE** (PDF 전체 UNAVAILABLE 249개) | 계획 §4-3 가용성 계약대로 FY26A(EX-99.1 3표), FY27E·FY28E(RLE YAML·R13 값) 채움. 계약상 진짜 미가용 칸만 UNAVAILABLE |
| D6 | 차트 ①②③b④⑤⑥⑧ | FQ4-26·FY26A·FY27E·FY28E 막대·점 **UNAVAILABLE** 표기 | 발표 후 값과 RLE 경로를 그린다. ⑤는 FQ4 실제점 + FY27 3경로 |
| D7 | 9절 밸류에이션·히트맵 ⑦·Trailing P/B | 전부 UNAVAILABLE | 기준 주가 확보됨 → 계획 §4-5 식으로 산출 |
| D8 | 2절 서술 | `####`, `**반증 관측원:**`, `*근거: …*`가 **마크다운 기호 그대로** 출력 | 서술 조립 시 마크다운을 HTML로 변환 |
| D9 | 12절 부록 규칙표 | YAML 사전이 **원문 문자열 그대로** 덤프(읽을 수 없음) | 규칙별 사람이 읽는 표(규칙·식·입력값·등급·출처)로 렌더 |
| D10 | KO판 부록 | 영어 문장 다수(사후 변경 사유, A11 해석, "Use net capex…") | KO판은 한국어. G-15b가 이를 통과시킨 원인도 보고 |

### R16-3. 게이트 보강 (이번 결함 재발 방지)
1. **G-23 (신설) 가용성 계약**: ed1에서 계획 §4-3 가용성 표상 "가용"인 칸이 UNAVAILABLE이면 실패. UNAVAILABLE 개수와 위치 목록을 감사 기록에 남긴다.
2. **G-24 (신설) 원시 마크업**: PDF 텍스트에 `####`, `**`, `` ` ``, `{`·`source_id:` 같은 원시 기호가 있으면 실패.
3. **G-15b 강화**: KO판 본문에서 영어 문장(허용 용어 목록 밖 연속 영어 단어 5개 이상) 검출 시 실패.
4. **G-25 (신설) 표지 메타**: 발행일·자료 기준일·정보 컷오프가 날짜 형식이 아니면 실패.

### R16-4. 작업 순서와 기한
1. R16-2 D1–D10 수정 → R16-3 게이트 추가(먼저 **현재 산출물에서 실패하는지** 확인해 게이트가 진짜 결함을 잡는지 증명) → G-21 KO 목차 쪽 불일치 원인 수정.
2. 재렌더는 이해관계 레코드 유효시각 **2026-10-05 14:42 KST 이전**에 시작. 넘기면 렌더하지 말고 멈춘다(Jiwon 재확인 필요).
3. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r3.md` (§1 결함별 수정 · §2 신설 게이트의 구 산출물 실패 증명 · §3 전체 게이트 · §4 산출물 SHA · §5 테스트). 이전 ed1 산출물은 `logs/_mu_report_runs/ed1_r1_rejected/`로 옮겨 보존.

- 🔴 서술 문장 수정 금지(오류 발견 시 보고). 숫자는 manifest fact로만. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/ed1_r1_rejected/**`, 리뷰 1개. git 쓰기 금지.

---

## 부록 R17. E3 r2 — 사실 오류 5건 + 표현 결함 수정, 재렌더 (Codex, 2026-10-04)

> 🔴 **투자 자문 아님.** 기준: R16 리뷰 `REVIEW_CODEX_mu_report_e2b_r3.md` · KO PDF `00106e6f…5283`(16쪽) · EN PDF `8752b13e…2d19`(18쪽).
> 판정(Claude E3, KO 16쪽 전수 이미지 + EN 텍스트 대조): **CHANGES REQUESTED.** R16 결함 D1–D10은 대부분 해소됐다(시장 데이터·핵심 수치·3절 표·재무표·차트·밸류에이션·마크다운). 그러나 **숫자·부호가 틀린 곳**이 있어 배포 불가.

### R17-1. 사실 오류 (배포 차단)

| # | 위치 (KO/EN 공통) | 현재 | 정답 |
|---|---|---|---|
| F1 | 3절 "SCORED 인용 요약" | 4-lever 귀인 `$0.84 / $0.73 / $0.10 / $0.09 / $0.30` — **음수 부호 누락**; "가이던스 라벨: 4.00/4" | `+$0.84 / −$0.73 / +$0.10 / +$0.09 = +$0.30` (SCORED §6) · "4/4 적중" |
| F2 | 6절 손익·현금흐름 FY27E·FY28E | 법인세 **+30,794 / +29,553**, 운전자본 변동 **+4,882**, 배당 **+690 / +690** — 역사 열(법인세 −14,761, 배당 −610)과 **부호 규약 반대** | 역사 열과 같은 현금흐름 부호: 법인세 −30,794 / −29,553, 운전자본 −4,882 / 0, 배당 −690 / −690. CFO 합계 205,589는 이미 맞음(표시 부호만 문제) |
| F3 | 5절 "DRAM·NAND 정성 체크" | DRAM "low-60s %", NAND "mid-80s %" — **FQ3 준비문 값**이 기간 표시 없이 들어감 | FQ4 FY26 준비문 p.7: DRAM 가격 high-teens %↑·비트 mid-single-digit↑, NAND 가격 ≈30%↑·비트 ≈10%↑. 두 분기를 보이려면 열에 기간(FQ3/FQ4) 명시 |
| F4 | 9절 그림 8 히트맵 | y축 눈금이 **0–4 인덱스**, x축 성장 오프셋 단위 "pt" | y = FY27 GM 실제값(또는 ±pt 오프셋 명시), x = 주당 성장 오프셋 %p. 축 제목·단위·기준점(base) 표시 |
| F5 | 표지 시장 데이터 | "발행주식수 1,147M · 2026-09-03 기준" — 1,147M은 **FQ4 가중평균 희석주식수**이지 발행주식수가 아님. 시가총액 1,258,706 **단위 없음** | 라벨 "희석 가중평균 주식수(FQ4)", 시가총액 "USD million"과 산식(주가 × 희석주식수) 각주. P/B 캡션도 같은 기준 명시 |

### R17-2. 표현 결함

| # | 위치 | 결함 | 요구 |
|---|---|---|---|
| P1 | 12절 "발표 후 변경" 표 (KO판) | 원안·변경 칸이 **영어**("FQ1 = M1; then -0.5 percentage point…", "FQ4 actual net capex * 1.05…") | KO판 한국어. **G-15b가 표 셀을 검사하지 않은 원인**을 고치고, 현재 산출물에서 실패함을 먼저 증명 |
| P2 | 12절 사전 등록 규칙표 | "등급" 열이 전부 `low`(신뢰도) | R9 표의 **입력/규칙 등급(E·D·J)** 표시. 신뢰도 `low`는 표 머리 한 번 |
| P3 | 6절 FY26E PREREG_A 열 | `NOT_IN_SOURCE` 원시 열거값이 줄바꿈되어 노출 | KO "—(사전등록 범위 밖)", EN "— (not pre-registered)" + 각주 1개 |
| P4 | 7절 마진 브리지 · 4절 전망 | 각 한 문장뿐, 브리지 내용 없음 | 7절: FQ3→FQ4 FY26 실제와 FY26A→FY27E base의 GM·opex 기여 표(manifest fact). 4절: FQ1 FY27 가이던스 표(GAAP·비GAAP) |
| P5 | 서식 | "(786,)" 튜플 표기, SCORED 표 `3296`/`1860` 천 단위 구분 없음, `$` 표기 혼재 | 숫자 서식 함수 하나로 통일. 원시 Python 표기 검출을 G-24에 추가 |
| P6 | 2절 | 논거 제목이 본문과 같은 굵기 | 논거 제목 굵게(서술 문장 변경 없이 스타일만) |

### R17-3. 순서와 기한
1. F1–F5 → P1–P6 수정. F1·F2·F5는 **manifest fact 값과 표시 문자열을 비교하는 테스트**를 추가(부호·단위 포함).
2. 재렌더 시작은 이해관계 레코드 유효시각 **2026-10-05 14:42 KST 이전**. 넘기면 멈춘다.
3. 이전 산출물은 `logs/_mu_report_runs/ed1_r2_rejected/`로 보존.
4. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r4.md` (§1 F·P 항목별 수정과 증거 · §2 게이트 · §3 산출물 SHA·쪽수 · §4 테스트).

- 🔴 서술 YAML 문장 수정 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/ed1_r2_rejected/**`, 리뷰 1개. git 쓰기 금지.

---

## 부록 R18. E3 r3 — 마지막 정리 2건 + 재렌더 (Codex, 2026-10-05) — ⏰ 렌더 시작 14:42 KST 이전

> 🔴 **투자 자문 아님.** 기준: R17 리뷰 `REVIEW_CODEX_mu_report_e2b_r4.md` · KO PDF `ae0eee43…5e5d`(17쪽) · EN PDF `411ba632…5e5b`(18쪽).
> 판정(Claude E3): **F1–F5·P1–P6 해소 확인**(4-lever 부호·라벨 4/4·법인세/운전자본/배당 부호·FQ4 DRAM/NAND 범주·히트맵 축 −4~+4%p와 중앙 6.5x=표 6.49x·희석 가중평균 주식수 라벨·시가총액 단위·KO 부록 한국어·등급 E/D/J·`—(사전등록 범위 밖)`). 남은 것은 Codex가 스스로 보고한 **연결 누락 2건**과 부록 표기 1건뿐이다.

### R18-1. 작업
1. `render.py:136` 세전이익 RLE 셀 fact id `is.pretax_income.*` → 실제 `is.pretax.*`. `render.py:152` 현금흐름 순이익 RLE 셀 `cf.net_income.*` → `is.net_income.*`. 두 셀을 **G-23 required set에 추가**하고, 현재 산출물에서 G-23이 실패함을 먼저 증명한다.
2. 부록 규칙표 식 칸에서 `*`가 마크업 제거로 사라진 곳(`quarterly_dps 4 S1` 등)을 `×`로 표시. 값 칸의 `key.value=` 접두는 KO "값"/EN "value" 라벨로 바꾼다(숫자·내용 불변).
3. 재렌더(시작 **2026-10-05 14:42 KST 이전**, 넘기면 멈춤) → 전체 게이트 → 이전 산출물 `logs/_mu_report_runs/ed1_r3_rejected/` 보존.
4. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r5.md` (§1 수정·증거 · §2 게이트 · §3 산출물 SHA·쪽수 · §4 테스트 · §5 **E4 커밋 후보 목록**: 계획 §2 D7 기준 전체 경로 + SHA. `logs/**`는 제외하고 별도 표시).

- 🔴 서술·숫자·규칙 변경 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/ed1_r3_rejected/**`, 리뷰 1개. git 쓰기 금지.

---

## 부록 R19. XLSX 표지 문구 + E4 목록 정리 (Codex, 2026-10-05) — ⏰ 렌더 시작 14:42 KST 이전

> 🔴 **투자 자문 아님.** 기준: R18 리뷰 `REVIEW_CODEX_mu_report_e2b_r5.md` `6f91cbe6…8819`.
> 판정(Claude E3): PDF·HTML·MD **PASS**(세전이익·현금흐름 순이익 RLE 셀 채워짐 확인, E4 후보 경로·SHA 전수 일치). Jiwon 결정: XLSX 문구를 고친 뒤 커밋.

### R19-1. 작업
1. `render.py:626·631` 공용 XLSX Summary 시트의 FIXTURE/E2-A 문구를 ed1 실제 판 문구로 교체(KO/EN 판 라벨·면책 2키·이해관계 고지·자료 기준일, PDF 표지와 같은 문자열 사용). XLSX 전체 시트에서 `FIXTURE`·`DRY RUN`·`E2-A fixture` 문자열이 있으면 실패하는 검사를 G-24에 추가하고, **현재 XLSX에서 실패함을 먼저 증명**.
2. 재렌더(시작 **14:42 KST 이전**, 넘기면 멈춤) → 전체 게이트 → 이전 산출물 `logs/_mu_report_runs/ed1_r4_rejected/` 보존.
3. E4 후보 목록 갱신. 다음 1건은 **목록에서 제외**한다: `forecast/HANDOFF_CODEX_mu_report_survey_r4.md` — 재배포 플랫폼 명칭이 들어 있어 "조사 표본 출처 명칭은 `logs/`에만" 규칙(public 리포)에 걸린다. 다른 후보 파일에 같은 명칭이 없음을 검사해 기록.
4. 산출물: `forecast/REVIEW_CODEX_mu_report_e2b_r6.md` (§1 수정·증거 · §2 게이트 · §3 산출물 SHA · §4 테스트 · §5 **최종 E4 후보 목록**(경로·SHA, gitignore 대상 표시 열 포함)).

- 🔴 숫자·서술·규칙 변경 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/ed1_r4_rejected/**`, 리뷰 1개. git 쓰기 금지.

---

## 부록 R20. ed1 개정 1 — Jiwon 검토 9건 반영 (Codex, 2026-10-05)

> 🔴 **투자 자문 아님.** 기준: 커밋 `cbacb4d`(로컬, push 전) · 서술 r3 `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` `52cdbbf2…a39f`(Claude 작성 완료).
> 산출물 파일명은 ed1 그대로, 표지·메타의 판 표시만 "제1판 개정 1 / Edition 1, Revision 1"로 바꾼다. 이전 산출물은 `logs/_mu_report_runs/ed1_rev0_committed/`로 복사 보존.

### R20-0. 로고 결정 (J-6 유지)
- 조사 표본 중 MU·SK하이닉스 대상 리포트 8건의 표지를 확인했다. **모두 발행사 자신의 로고만 쓰고, 분석 대상 회사 로고는 표지 디자인에 쓰지 않았다**(대상 회사는 텍스트 표기). 예외 1건은 기사형 리포트의 스톡 사진 속 로고였다.
- 따라서 Micron 로고 이미지는 쓰지 않는다. 표지는 **Micron 계열 청색 톤 강화 + 굵은 텍스트 워드마크("MICRON TECHNOLOGY · NASDAQ: MU")**. 상표 서체 모방 금지.

### R20-1. 표현·구조 수정
| # | 위치 | 요구 |
|---|---|---|
| 1 | 표지 시장 데이터 표 | 숫자 열 **전부 오른쪽 정렬**(희석 가중평균 주식수·시가총액 포함). 표 전체에서 숫자 셀 정렬 규칙 하나로 통일하고 테스트 |
| 2 | 1절 | 서술 r3 `company` 4문단 렌더(표·차트 앞). 표지 뒤에 서술 `abbreviations`로 **"약어와 출처" 상자** 추가(부록에도 동일 목록) |
| 3 | 2절 | "강세 논거/약세 논거" 소제목과 각 논거 제목(claim)을 **굵게**. 논거마다 아래 R20-2의 근거 차트 1개를 바로 아래에 배치 |
| 4 | 3절 | 서술 r3 `fq4_reading` 3항을 **판정 기준 상자**로 렌더하고, 기존 SCORED 요약표 아래에 지표별 판정 표(지표·무차이 범위·실제·실제 라벨·예측 라벨·결과) 추가 |
| 5 | 4·5절 | 서술 r3 `gm_compression` 3문단 + 차트 C9. "DRAM·NAND 정성 체크" 표는 **차트 C10 + 서술 `price_bit_note`**로 교체(제목 "DRAM·NAND 가격·비트 변화(회사 공시 구간)") |
| 6 | 6절 표 | "—(사전등록 범위 밖)" 각주를 "사전등록(Freeze A)은 FQ4 분기와 FY26 매출·순이익·EPS만 예측했다"로 구체화. RLE 열 UNAVAILABLE 각주: "RLE 규칙은 손익·현금흐름 일부만 추정하고 재무상태표는 추정하지 않는다(부록 규칙표 A11–A16)" |
| 7 | 10절 | 리스크 항목 제목 **굵게** |
| 8 | 표지 | R20-0 |
| 9 | 출처 표기 | 서술 r3는 `src`를 "Micron FQ4 FY26 준비문 p.x" 등 풀네임으로 바꿨다. 그대로 렌더 |

### R20-2. 차트 추가 (8 → 16개, 모두 기존 pin 입력과 manifest fact만 사용)
| ID | 차트 | 데이터 | 배치 |
|---|---|---|---|
| C9 | **GM 상회 폭 압축**: 분기별 (실제 GAAP GM − 가이던스 중간값) 막대 + 실제 GM 전분기 변화 선, FQ1 FY27 가이던스 점 | `ratio.gross_margin.*` · `guidance.gm_gaap.*` | 4·5절 |
| C10 | **DRAM·NAND 가격·비트 구간 막대** (FQ3·FQ4 FY26) | 준비문 원문 구간 + 환산표(J): low-single-digit 1–3%, mid-single-digit 4–6%, ≈10% 9–11%, high-teens 16–19%, ≈30% 28–32%, low-60s 60–63%, mid-80s 84–86% | 2절(약세1)·5절 |
| C11 | **EPS 오차 4-lever 폭포**(PREREG_A 32.57 → 실제 32.87) | SCORED §6 | 3절 |
| C12 | **FQ1 FY27 가이던스 vs 사전등록 예측**(bear/base/bull 예측 중간값, 실제 가이던스 범위, 주당 성장 축 보조) | FROZEN §(c-2) · EX-99.1 | 2절(강세2)·3절 |
| C13 | **FY27E 시나리오·민감도 EPS 막대**(bear/base/bull + 민감도 4행) | RLE | 8절 |
| C14 | **opex·순capex 추이**(분기 실제 FY24–FQ4 FY26 + FY27E RLE 경로, 실제/추정 구분) | pin된 EX-99.1·10-K·10-Q 원천. **원천에 없는 분기는 그리지 말고 보고** | 2절(약세3)·10절 |
| C15 | **마진 브리지 폭포**(FY26A → FY27E base 영업이익: 매출·GM·opex) | manifest | 7절 |
| C16 | **SCA 구조**(체결 26건, 2030년까지 매출 35% 이상, 가격 틀 정해진 비중 75% / 시장가 25%, 고객 약정 $32B, 분기말 고객 예치금 잔액 $12.7B) | 준비문 p.3·p.8–9 (EX-99.1 비유동 고객계약부채 12,895는 별도 각주)  | 2절(강세3·약세2) |

- 모든 신규 차트는 G-13·G-13c·G-16(캡션·단위·기준·출처·기준일) 계약을 따른다. KO/EN 한 쌍씩.
- 2절 강세1(공급 진술)은 차트 대신 **회사 진술 요약 표**(연도·진술·쪽)로 둔다.

### R20-3. fact 바인딩 (서술 r3 신규 토큰)
`derived.gm_beat.FQ2-26` · `derived.gm_beat.FQ3-26` · `derived.gm_beat.FQ4-26`(= 실제 GAAP GM − 가이던스 중간값, %p, 원천 재계산: +7.41 / +3.56 / +0.76 근사) · `guidance.revenue_lo.FQ4FY26` 49,000 · `guidance.revenue_hi.FQ4FY26` 51,000 · `is.revenue.FY2026Q4.A-8K`(기존 id 확인). 서술 계약 게이트(`gate_narrative_contract`)를 새 절(`abbreviations`·`company`·`fq4_reading`·`gm_compression`·`price_bit_note`)과 바인딩 수에 맞춰 갱신.

### R20-4. 순서·제약
1. 수정·차트·게이트 → **렌더 직전 정지**. 이해관계 레코드가 2026-10-05 14:42에 만료됐으므로 **Jiwon 재확인 후 Claude가 레코드를 갱신**해야 렌더한다.
2. 렌더 후 전체 게이트 + KO/EN 전 쪽 이미지 확인.
3. 산출물: `forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md` (§1 항목별 수정 · §2 신규 차트 16개 목록·데이터 출처 · §3 게이트 · §4 산출물 SHA·쪽수 · §5 테스트 · §6 E4 후보 목록).
- 🔴 서술 문장 수정 금지(오류는 보고). 숫자·RLE 규칙 변경 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/ed1_rev0_committed/**`, 리뷰 1개. git 쓰기 금지.

---

## 부록 R21. ed1 개정 1 렌더 (Codex, 2026-10-05) — ⏰ 렌더 시작 2026-10-06 19:07 KST 이전

> 🔴 **투자 자문 아님.** 기준: R20 사전 검사 `forecast/REVIEW_CODEX_mu_report_ed1rev1_r1.md` `21a121ca…7613` (Claude 확인: 보존 25개 일치, 차트 16개/언어, gm_beat 바인딩 +7.41/+3.56/+0.76 재계산 일치, C14 제외 분기 없음).
> 원격 상태: `origin/main` = `9e4c667`(ed1 rev0 push 완료). 개정 1은 그 위의 새 커밋이 된다.

1. 이해관계 레코드 갱신 완료: `forecast/inputs/mu_fy2026q4_conflict_confirmation.yaml` — `not_held`, `confirmed_at_kst: 2026-10-05T19:07:00+09:00`, `edition: ed1`. 렌더 시작은 **2026-10-06 19:07 KST 이전**.
2. ed1 개정 1 KO/EN 렌더 → 렌더 포함 **전체** 게이트·테스트(R20에서 제외한 렌더 테스트 12항목 포함) → 신규 차트 16개 KO/EN 이미지 전 쪽 확인.
3. 산출물: `forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md` (§1 렌더 명령·시각 · §2 게이트 · §3 산출물 SHA·쪽수 · §4 테스트 · §5 E4 후보 목록 — 이번 개정에서 바뀐 파일 + 신규 파일, 레코드 포함).
- 🔴 실패 시 수정·재렌더 금지, 실패 목록만 보고. 서술·숫자·규칙 변경 금지. git 쓰기 금지.

---

## 부록 R22. ed1 개정 1 — 시각 결함 수정 + 재렌더 (Codex, 2026-10-05) — ⏰ 렌더 시작 2026-10-06 19:07 KST 이전

> 🔴 **투자 자문 아님.** 기준: R21 결과 `forecast/REVIEW_CODEX_mu_report_ed1rev1_r2.md` (CHANGES REQUESTED, V1–V3). Claude가 KO 26쪽 전체 + EN 일부를 별도 확인해 아래 V4–V16을 추가했다.
> 이해관계 레코드(`confirmed_at_kst: 2026-10-05T19:07:00+09:00`)는 그대로 유효. **렌더 시작이 2026-10-06 19:07 KST를 넘기면 렌더하지 말고 정지**(Jiwon 재확인 필요).

### R22-1. 수정 목록
| ID | 위치 | 결함 | 요구 |
|---|---|---|---|
| V1 | C9 KO p.12–13 / EN p.13–14 | 두 축 범례 겹침 | 범례 하나로 합쳐 차트 아래(plot 밖)에 배치 |
| V2 | C10 EN p.7·15 | 제목 오른쪽 잘림 | **차트 이미지 내부 제목 제거**(캡션이 이미 같은 제목을 가짐 — 전 차트 공통으로 내부 제목 제거) 또는 자동 줄바꿈. 전 차트 KO/EN에 대해 제목·라벨 bbox가 figure 안에 있는지 검사하는 테스트 추가 |
| V3 | C11 EN p.10 | `OP→NI`의 → 누락 | 화살표 글리프가 있는 폰트로 대체하거나 "OP to NI"/"영업이익→순이익"을 글리프 확인 후 사용. **렌더 로그의 missing-glyph 경고를 게이트 실패로 승격** |
| V4 | 2절·10절 | 소제목 "강세 논거/약세 논거", 각 논거 제목(claim), 리스크 제목이 **굵게 보이지 않음**(p.4 150dpi 확인: 일반체). Bold 폰트는 임베드돼 있으나 적용 안 됨 | CSS로 font-weight 700 적용 확인. 테스트: 해당 텍스트 run의 PDF 폰트가 `*-Bold`인지 pdfplumber로 검사 |
| V5 | 차트 중복 배치 | C9(p.12·13), C10(p.6·14), C12(p.4·10), C14(p.8·23), C16(p.5·7)이 **같은 그림이 두 번** 실림 | **각 차트는 한 번만** 싣는다(첫 배치 위치). 두 번째 위치에는 "(그림 n 참조)" 한 줄. 이에 따라 쪽수 감소 예상 |
| V6 | 그림 번호 | 본문 등장 순서와 번호 불일치(1→12→16→10→14→11→2…) | **본문 첫 등장 순서대로 그림 1…16 재번호**. KO/EN 동일 번호, 본문 "(그림 n)" 참조·목차·manifest 동기화. 차트 파일명(C-ID)은 유지 |
| V7 | C12 p.4 | "가이던스"가 막대가 아니라 작은 점으로만 보임; 주당 성장 보조축 점선이 막대 위를 가로질러 읽기 어려움 | 가이던스는 **범위 막대(EX-99.1 가이던스 하단–상단, 원천 값 그대로) + 중간값 표시**로 다른 막대와 같은 폭. 주당 성장은 막대 위 데이터 라벨(%)로 바꾸고 보조축 제거 |
| V8 | C16 KO p.5 | 왼쪽 패널 주석 텍스트 겹침 | 주석 위치 조정 또는 표로 분리. 텍스트 겹침 bbox 검사 테스트 |
| V9 | 표지 핵심 수치 | FY27E/FY28E 행만 값이 **왼쪽 정렬**·"값" 열에 들어감; EPS 표기 `32.57` vs `$32.87` 혼재 | 모든 숫자 셀 오른쪽 정렬(R20-1 #1 규칙 적용 누락). 통화 기호 규칙 하나로(단위는 "기준" 열에만, 값에는 `$` 없음). FY27E/FY28E는 매출·EPS 두 행으로 분리 |
| V10 | 표지 | 워드마크가 굵지 않음; "완결성:" 아래 `- ` 하이픈이 원시 마크다운처럼 보임; "사전등록 전망과 … 분리" 문장이 두 번 나옴 | 워드마크 700. 하이픈 목록은 실제 목록(ul)으로. 중복 문장 1개 삭제는 **서술이 아닌 템플릿 고정문** 범위일 때만; 서술 yaml 문장이면 수정하지 말고 보고 |
| V11 | 표 헤더 정렬 | "값" 헤더는 왼쪽, 값은 오른쪽 — 헤더와 열 정렬 불일치 | 숫자 열은 헤더도 오른쪽 정렬. 전 표 공통 |
| V12 | 6절 FY26E 표 | "—(사전등록 범위 밖)" 셀이 좁은 열에서 3줄로 어색하게 줄바꿈 | 셀은 "—" + 각주 기호(†)만, 설명은 표 아래 각주(R20-1 #6 문구). UNAVAILABLE 셀도 같은 방식(‡) |
| V13 | 쪽 나눔 | 내재 배수 표가 두 쪽에 걸쳐 나뉨 | 표 `break-inside: avoid`(긴 표는 헤더 반복). 그림+캡션도 분리 금지 |
| V14 | 부록 규칙표 p.24–25 | `A12_sbc`·`값: 0.190476; 값: 1972`·`SRC-HANDOFF-R9-R12` 등 **내부 키·ID 그대로** 노출, 일반 독자 판독 불가 | 열을 "항목(한글명) · 규칙(식을 문장으로) · 값 · 근거 등급 · 출처(풀네임)"로. 내부 키는 XLSX에만. 출처 ID→풀네임 매핑은 서술 `abbreviations`/기존 provenance 표를 쓰고, 매핑 없는 ID는 보고. "발표 후 변경" 표 "근거 쪽" 열 숫자가 표 오른쪽 끝에 떨어져 있음 → 열 폭 조정 |
| V15 | 차트 캡션 | `[SRC-REMARKS-FQ3-FY26, …]`·`CITED + J` 같은 내부 표기 노출(사용자 지적 "출처 모호"의 원인) | 캡션 출처는 풀네임만("Micron FQ4 FY26 준비문 p.7"). 등급은 "근거 등급: J(저자 판단)"처럼 풀어서. 내부 ID는 manifest에만 |
| V16 | 롤포워드 절 p.25 | 문장 끝 "(4)" "(10)" "(786)"의 의미 불명 | 단위/의미 표기(예: "USD 786 million") — 숫자 원천 그대로, 표기만 |

### R22-2. 범위 밖 (보고만)
- 5절이 한 문장뿐인 문제, 부록 "방법론과 정보 경계"가 얇은 문제는 **서술 범위** — Claude가 서술 r4로 보강할 수 있으니 수정하지 말고 위치만 보고.
- 표지 FY28E 매출 = FY27E 매출(274,784)은 A3 flat 규칙의 결과로 보인다. 계산상 맞는지 확인만 하고 결과를 보고(수치 변경 금지).

### R22-3. 순서·제약
1. 수정·테스트 → 렌더(시작 시각 ≤ 2026-10-06 19:07 KST) → 전체 게이트·테스트 → **KO/EN 전 쪽 이미지 확인**(V1–V16 각각 해당 쪽 캡처 경로를 리뷰에 기록).
2. 산출물: `forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md` (§1 V1–V16 항목별 조치·증거 쪽 · §2 게이트·신규 테스트 · §3 산출물 SHA·쪽수 · §4 R22-2 보고 · §5 E4 후보 목록).
- 🔴 서술 문장·숫자·RLE 규칙 변경 금지. 로고 이미지 금지(J-6). **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, 리뷰 1개. git 쓰기 금지.
- 시각 실패가 남으면 재렌더 반복하지 말고 실패 목록만 보고(렌더는 최대 2회).

---

## 부록 R23. ed1 개정 1 — 잔여 결함 + 서술 r4 + 재렌더 (Codex, 2026-10-05) — ⏰ 렌더 시작 2026-10-06 19:07 KST 이전

> 🔴 **투자 자문 아님.** 기준: R22 결과 `forecast/REVIEW_CODEX_mu_report_ed1rev1_r3.md` `04e20fbc…f190`. Claude가 KO 24쪽 전체를 따로 확인했다. **Bold는 시각상 적용됨**(p.4–6 논거 제목·리스크 제목) — Codex 진단(합자 `fl` offset 오류에 의한 게이트 오탐)에 동의.
> 서술 r4: `forecast/inputs/mu_fy2026q4_narrative_ed1.yaml` `8fee9e26…bec0` (r3 백업 `logs/_mu_report_runs/narrative_ed1_r3_backup.yaml`). KO/EN 숫자 multiset 일치, EN 한글 0 확인.
> R22-2 정정: FY28E 매출 = FY27E는 A3가 아니라 **A8 base 0.0** 때문(Codex 확인이 맞다).

### R23-1. 게이트 오탐 수정
- Bold 검사: 문자열 offset이 아니라 **char 단위로 텍스트를 맞춰** 검사(합자 char 1개 = 텍스트 n자 확장). 합자 포함 음성/양성 테스트 추가. 수정 후 R22 FAIL 문장이 PASS가 되는지 리뷰에 기록.

### R23-2. R22 잔여 (Codex 보고 2–5) — 모두 수정
| ID | 요구 |
|---|---|
| W1 (V9) | 표지 시장 데이터 "기준" 열에 단위 복원: 주가 `USD/share · 2026-10-01`, 주식수 `million shares · FQ4 A-8K`, 시가총액 `USD million · 주가 × 주식수` |
| W2 (V11) | 숫자 열 nowrap은 **td에만**. th는 줄바꿈 허용. 6절 표 FY26E PREREG_A / FY26A A-8K 헤더 겹침 해소, EN10·EN19 긴 헤더 잘림 해소. 헤더 bbox가 자기 셀 안에 있는지 검사 |
| W3 (V12) | 비율표 각주도 †/‡ 기호 접두 |
| W4 (V14) | 변경 표에 `post-print-changes` 분기가 실제 적용되게(판별 순서 수정). 사유 열을 가장 넓게, "근거 쪽"은 좁게·가운데. 규칙표·변경표 오른쪽 끝이 본문 폭(549.9pt) 안에 들어오게. 원안 기호 M1/X1 등은 풀이("FQ1 실제 GM" 등) |

### R23-3. Claude 추가 결함
| ID | 위치 (KO R22 산출물) | 요구 |
|---|---|---|
| W5 | 그림 7 EPS 4-lever 폭포 (p.8) | y축이 0부터라 ±$0.1–0.8 레버가 거의 안 보이고 상단 라벨이 겹침. **y축을 시작·끝 막대 근처로 확대**(예: 31.5–34.0, 축 생략 표시) 또는 시작/끝을 막대 대신 기준선으로. 라벨은 막대 옆 한 줄, 겹침 검사 |
| W6 | 그림 14 마진 브리지 (p.17) | 데이터 라벨 소수 2자리(`+114,290.71`) → **정수 반올림 표시**(raw는 manifest 유지). 라벨이 막대 위 다른 막대와 겹치지 않게 |
| W7 | 3절 SCORED 요약 판정표 (p.9) | KO판에 `ABOVE_HIGH`·`IN_RANGE`·`(d-1) "IN_RANGE 구성 상 동일"` 등 영문 코드 노출. 표시용 매핑: 상단 초과 / 범위 안 / 하단 미달 / 라벨 없음(가이던스 없음) 등. **원문 인용 게이트(G-3f)는 manifest raw로 유지**하고 표시만 번역. EN은 "Above high / In range / Below low". G-15b에 이 코드들 추가 |
| W8 | 9절 내재 배수 표 (p.20) | 표 끝에 `항목 / 값 / 기준 / Trailing P/B 9.10x A-8K`가 **헤더째 같은 표에 붙음**. Trailing P/B는 별도 작은 표 또는 표 아래 한 줄로 분리 |
| W9 | 그림 12 연간 막대 (p.12) | "53w" 라벨이 막대와 겹쳐 판독 불가 → x축 라벨에 "(53주)" 병기로 대체 |
| W10 | 그림 3 SCA (p.5) | 부제 `26 SCA · >35% · 2030` 암호문 → 부제 제거(캡션이 설명) 또는 "체결 26건 · 2030년까지 매출 35% 이상" |
| W11 | 그림 1·5 범례 | 범례 글자가 본문 대비 너무 작음(약 5pt 상당). 전 차트 범례·tick 최소 크기 통일(PDF 상 7pt 이상) |

### R23-4. 서술 r4 신규 절 반영
- `business_structure` (KO/EN 4문단) → **5절 사업 구조** 첫머리, i18n 고정문 "사업부 구성과 가격·출하 신호는…" 다음, 그림 앞. 마지막 문단('해석:')은 다른 절과 같은 해석 문단 스타일.
- `methodology` (KO/EN 5문단) → **부록 "방법론과 정보 경계"**의 기존 두 줄을 대체(약어 목록 뒤). 기존 "FY27 컨센서스 비교는 UNAVAILABLE" 문장은 r4 4번째 문단과 중복이므로 제거.
- 촉매 표 2번째 행 문구 변경(내부 용어 G0-A/B 제거) — 바인딩 변화 없음.
- 신규 절 숫자는 회사 진술(준비문 쪽수 병기)로 fact 토큰이 아니다. `gate_narrative_contract`에 두 절을 추가하고, G-15 숫자 parity 대상에 포함. 숫자 출처 검사가 manifest fact를 요구하면 **company 절의 "73%"와 같은 방식(회사 진술·src)으로 처리**하고, 처리 방식을 리뷰에 기록.
- 서술 meta.sections 목록은 렌더러가 쓰지 않으면 무시.

### R23-5. 순서·제약
1. 수정·테스트 → 렌더(시작 ≤ 2026-10-06 19:07 KST) → 전체 게이트·테스트 → **KO/EN 전 쪽 이미지 확인**(W1–W11·신규 절 각각 증거 쪽 기록).
2. 산출물: `forecast/REVIEW_CODEX_mu_report_ed1rev1_r4.md` (§1 R23-1 · §2 W1–W11 조치·증거 · §3 신규 절 · §4 게이트·테스트 · §5 산출물 SHA·쪽수 · §6 E4 후보 목록 — 서술 r4·핸드오프·리뷰 r1–r4 포함).
- 🔴 서술 문장·숫자·RLE 규칙 변경 금지(서술 오류는 보고). 로고 이미지 금지. **허용 경로**: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, 리뷰 1개. git 쓰기 금지.
- 렌더는 최대 2회. 남는 시각 결함은 목록만 보고.

---

## 부록 R24. ed1 개정 1 — 마지막 다듬기 (Codex, 2026-10-05) — ⏰ 렌더 시작 2026-10-06 19:07 KST 이전 · **Jiwon 승인 시에만 실행**

> 🔴 **투자 자문 아님.** 기준: R23 결과 `forecast/REVIEW_CODEX_mu_report_ed1rev1_r4.md` `94150bca…aef`. Claude가 KO 24쪽 전체 + EN p.9·10·25를 확인: W1–W11·신규 절 모두 반영 확인. 남은 것은 아래 다듬기뿐이며 **이번이 ed1 개정 1의 마지막 렌더**다. 이후 남는 결함은 ed2로 넘긴다.

| ID | 위치 | 요구 |
|---|---|---|
| P1 | 변경표 마지막 열(VIS-1) | 헤더를 짧게: KO `쪽`, EN `Page`. 단어 중간 줄바꿈 금지(`word-break: keep-all`, EN `hyphens: none`) |
| P2 | XLSX Summary A1(VIS-2) | 제목 행 높이를 글꼴 크기에 맞게 키워 잘림 해소. 값·수식 불변 |
| P3 | 3절 판정표 GAAP opex 행 (KO p.9 / EN p.10) | 예측 라벨 셀의 원문 인용 `(d-1) "범위 안 구성상 동일"`은 독자가 읽을 수 없다. 표시는 `해당 없음(가이던스 없음)` / `n/a (no guidance)`, 결과 `서술 실패` / `Narrative failure`는 유지하고 표 아래 각주 1줄: "GAAP 영업비용은 회사 가이던스가 없어 라벨 채점 대상이 아니다. 실제가 사전등록 기준보다 77% 많아 서술 실패로 기록했다(SCORED §4)." / "GAAP opex had no company guidance, so it is not label-scored; actual exceeded the pre-registered base by 77%, recorded as a narrative failure (SCORED §4)." **G-3f 원문 인용은 manifest raw로 유지**, 표시만 바꾼다. 77은 SCORED의 +77% 그대로(새 계산 아님) |
| P4 | 부록 규칙표 "적용 값" 열 | 비율 값은 **% 표시**(0.8495 → 84.95%, 0.136742 → 13.67%, 0.0344792 → 3.45%, −0.00228 → −0.23%) — 표시만, raw·XLSX는 소수 유지. 상태 코드 `AVAILABLE`/`UNAVAILABLE_WITHOUT_ASSUMPTIONS`/`가용성: 가정 부재로 미가용` 등은 KO "가용"/"가정이 없어 추정하지 않음", EN "available"/"not estimated (no assumption)"로 표시. G-15b에 원시 상태 코드 노출 금지 추가 |
| P5 | QA 캡처 위치 | `forecast/reports/mu_report_fy2026q4_ed1_assets/` 아래 `pages/`·`pages_final/`·`pages_r18/`·`pages_r23/`(gitignore 대상 아님)를 **`logs/_mu_report_runs/qa_pages/<원래 폴더명>/`으로 이동**(mv, 삭제 아님). 이번 렌더 QA 캡처도 logs 아래에 저장. 리뷰 r1–r4의 링크는 고치지 않고 이동 사실만 r5에 기록. assets 폴더에는 발행 PNG 32개만 남는지 확인 |

- 순서: 수정·테스트 → 렌더 1회(시작 ≤ 2026-10-06 19:07 KST) → 전체 게이트·테스트 → KO/EN 전 쪽 이미지 확인.
- 산출물: `forecast/REVIEW_CODEX_mu_report_ed1rev1_r5.md` (§1 P1–P5 조치·증거 쪽 · §2 게이트·테스트 · §3 산출물 SHA·쪽수 · §4 잔여(있으면 목록만, ed2 이월) · §5 **최종 E4 목록**(add / add -f 구분, SHA 포함)).
- 🔴 서술 YAML·숫자·RLE 규칙 변경 금지. 로고 이미지 금지. 허용 경로: `forecast/scripts/mu_report/**`, `forecast/tests/**`, D7 산출물 경로, `logs/_mu_report_runs/**`, 리뷰 1개. git 쓰기 금지.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
