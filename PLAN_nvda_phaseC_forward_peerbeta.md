# PLAN v3 — NVDA Phase C: Forward(FY27E) 앵커 + 적격 Peer Beta Snapshot

2026-07-17 | v3: Codex 최종 승인·구현 및 C-1~C-12 검증 완료
선행: `ROUND3_POLICY_APPROVED_nvda_autoprofile.md` (§2 peer 원칙 · §7 Phase 정의 · §9 성공기준) → Phase A(`4da07e6` 등) → Phase B(`8ae6aab`)
Codex 최종 판정: **승인·구현 완료.** 조건부 승인 사항은 구현 계약과 회귀검증에 반영됐다.

> 🔴 불변 원칙 (ROUND3 §2·§7): **peer는 검증·차단 근거이지 가격 상향 수단이 아니다. forward는 예측이지 실적이 아니다.**
> 🔴 완료 기준에 "$138 도달·시장가 근접" 없음 (§7 Phase C).

## 구현 결과 (2026-07-17)

- yfinance 실측상 FY27E는 `+1y`가 아니라 `0y` 행이다. 수집기는
  `nextFiscalYearEnd`로 상대 행을 매핑한다. 자동 매출 $392,965M은 수동 참조
  $391,300M 대비 +0.43%다.
- 적격 peer 최소 표본은 **5개**, quantile은 `(n-1)*p` 선형보간으로 확정했다.
- raw beta가 `outlier_high/low`이면 Blume 소비 여부와 무관하게 investability
  **block**이다.
- 실제 NVDA 판정은 raw βL 2.040, 적격 US peer 6개, Tukey 범위
  1.630~2.776, `validated`다. WACC·가격·시나리오 계산은 변하지 않았다.
- C-1~C-12 모두 PASS, 후속 fixture 포함 전체 회귀 `992 passed, 5 deselected`.

---

## 0. Codex Round 1 → Claude 독립 재현 결과 (믿지 않고 검증함)

| Codex 주장 | 재현 방법 | 결과 |
|---|---|---|
| `BetaObservation.dataset_mismatches()`가 window_start/end·as_of까지 엄격 비교 | `schemas/provenance.py` L380-396 직접 확인 | **사실.** 6필드(window_start/end·frequency·benchmark·calculation_method·as_of) 전부 `!=` 비교. peer별 공통 거래일 차이로 정상 snapshot이 전부 mismatch 나는 지적 타당 → peer 비교에 `matches_dataset()` 사용 금지 계약 필요 (§2 쟁점 4 개정) |
| yfinance `+1y` ↔ FY27E 대응 미실증 | 샌드박스에서 `yf.Ticker('NVDA').revenue_estimate` 시도 | **재현 불가 확인** (Yahoo 프록시 403 차단). 대응 실증은 호스트 파이프라인 실행 시점으로 이연 → 실증 전 FY 재명명 금지 계약 채택 (§2 쟁점 2 개정) |
| quantile 계산법 미고정 위험 | 코드베이스 선례 조사 | 사내 선례 존재: `engine/peer_analysis.py` L85-86 (median-of-halves). 단 Codex 권고(선형보간)를 채택하고 stdlib `statistics.quantiles(method="inclusive")`로 고정 — n=5에서 Q1/Q3가 정확히 2·4번째 관측치로 떨어져 결정적 (§2 쟁점 5 개정) |
| `regress_beta` 비유한 beta 가능성 | `engine/beta_regression.py` L19-31 확인 | 비유한 수익률·비유한 beta 모두 **이미 raise** (fail-closed 기존 보장). 동률 beta는 허용(중복 제거 없음) |

**판정 요약: Codex 6개 조건 전부 수용** (반박 0건 — 전 항목이 코드 근거 또는 재현 불가 확인으로 뒷받침됨). 단 Q1==Q3 fallback은 Codex가 규칙 명시를 요구만 했으므로 Claude가 아래에 구체안을 제시한다(쟁점 5).

---

## 1. 착수 전 재검증 결과 (2026-07-17, 본 세션 독립 실행 — v1 §0 유지)

| 항목 | 기대 | 실측 | 판정 |
|---|---|---|---|
| HEAD | `8ae6aab` | `8ae6aab feat(nvda): complete Phase B TTM anchor` | PASS |
| nvda.yaml git object | 467행 · sha `bb276cf5` | lines 467 · sha `bb276cf56003` | PASS |
| financial_anchor / provenance | ttm / 5필드 | ttm / revenue·op·net_income·dep·capex | PASS |
| verify_nvda_phaseA_v2 (fresh bytecode) | ALL PASS | ALL PASS (WACC 11.52% · βL 1.6970 · CV 0/25 · gate 후 0/F) | PASS |
| verify_nexus_round4 --skip-pytest | ALL PASS · R-8 ENV SKIP | ALL PASS · R-9 45개 crash 0 | PASS |
| 넥써쓰 불변 | 18/445/891 · 362 · 36,211 · 51,687 | 일치 | PASS |
| git status | 미커밋 다수 보존 | 253 파일 | PASS (restore/reset 금지 유지) |

**정량분해 (v1 §1 유지):** 축 1 — TTM rev 253,491 vs FY27E 컨센서스 391,300 (+54%): 실적/예측 혼합 시 감사가능성 붕괴. `load_profile()`의 ttm merge 경로(`valuation_runner.py` L182-205)에 forward가 타면 안 됨. 축 2 — Phase A 확정 raw βL 2.040 → Blume 1.6968 → bu 1.694 (`consumed_blume`), 판정 결과와 무관하게 WACC 11.52%·βL 1.697 불변(C-8).

---

## 2. 확정 정책 (v1 정책안 + Codex Round 1 개정 반영)

### 쟁점 1 — Forward 앵커 배치: 별도 `forward_anchor` 블록 [v1 유지, Codex 이견 없음]

- `financial_anchor`에 `"forward"` 추가 금지. 신규 top-level `forward_anchor:` 블록, `ValuationInput.forward_anchor: Optional[ForwardAnchor] = None`.
- `load_profile()`은 이 블록을 consolidated/segment_data에 절대 merge하지 않는다(계약 주석 명시). 소비처: 리포트 표시 + verify C-6 수렴검사.

### 쟁점 2 — Forward provenance: metric별 분리 + 상대기간 보존 [🔄 Codex 개정 수용]

- **n_analysts를 top-level에 두지 않는다.** revenue와 EPS의 analyst 수가 다를 수 있으므로 metric별 자체 provenance:

```yaml
forward_anchor:
  basis: consensus_estimate          # required
  provider: yfinance                 # required
  as_of: "2026-07-XX"                # required
  retrieved_at: "2026-07-XX"         # required
  relative_period: "+1y"             # required — payload의 원 표기 그대로 보존
  fiscal_period_end: null            # 실증 전 null. 실증 후에만 기록 (아래 규칙)
  source_hash: <sha256>              # required — 원 payload 캐시의 해시
  revenue: {value: ..., n_analysts: ..., estimate_type: mean}   # 블록 존재 시 3필드 required
  eps:     {value: ..., n_analysts: ..., estimate_type: mean}
```

- 🔴 **FY 재명명 fail-closed**: yfinance `+1y`가 NVDA 비달력 회계연도(1월 말 결산) FY27과 대응함을 **실제 payload로 실증하기 전에는** `relative_period` 표기만 유지하고 FY27E로 명명하지 않는다. 실증 = payload(또는 동반 `earnings_dates`/`calendar`)에서 명시적 기간 종료일을 확보해 NVDA 회계달력과 대조 → 일치할 때만 `fiscal_period_end` 기록, 콘솔/Excel 라벨도 그때만 "FY27E"로 승격 (그 전에는 "컨센서스 +1y (예측치)"). 샌드박스 실증 불가 확인(§0)에 따라 이 검증은 호스트 수집 시점에 수행하고 결과를 provenance에 남긴다.
- **부분 snapshot 허용**: revenue+EPS만 기록. **op/NI 역산·보간 금지** (fabrication). `nvda_fy27e.yaml`의 op 256,300은 수동 큐레이션 영역으로 불변.
- 수집은 `pipeline/`에서만. 원 payload를 `.cache/forward_estimates/{ticker}_{as_of}.json` 저장 → sha256 → `source_hash`. 밸류에이션 런타임 네트워크 fetch 금지. n_analysts 미제공 metric은 해당 metric 기록 거부(fail-closed).

### 쟁점 3 — Peer 적격 기준 [v1 유지 + KR 처리 확정]

적격 = 아래 전부 (후보 전원 `{name, ticker, qualified, exclusion_reason}` 기록):
1. **실체**: 독립 상장 법인 + 유효 ticker. 사업부/제품 라인 pseudo-peer·소멸 법인 제외 (`a6b1356` 재감사 기준 계승).
2. **방법 충족**: 주간 관측 ≥80주(`_MIN_OBSERVATIONS`), window end ≤ analysis_date−7일 이내 (Phase A staleness 동일).
3. **벤치마크 동일**: ^GSPC 회귀 가능 시장의 상장사만. **KR 피어(SK하이닉스·삼성전자)는 부적격 — 후보 목록과 제외 사유만 기록.** 🔄 현지 벤치마크 beta 병기는 **Phase C 범위 밖** (Codex: 표시만 해도 동일 분포로 오독될 위험 — 수용). ADR 우회 산정 금지.
4. **산업 일치**: core 사업(SEG1 중심) 매핑 피어, 세그먼트 코드 기록.

### 쟁점 4 — 방법 일치 + 🔄 window 비교 계약 (Codex 추가 지적 수용)

- peer beta는 `pipeline/beta_observation.collect_beta_observation()` + `engine/beta_regression.regress_beta()` + `BetaObservation.blume()` **그대로 재사용.** 새 회귀 코드 금지.
- 🔴 **peer 비교에 `matches_dataset()`/`dataset_mismatches()`를 사용하지 않는다.** 그 계약은 동일 회사·동일 데이터셋 identity 검증용이며 window_start/end·as_of까지 엄격 비교하므로(§0 재현), peer별 공통 거래일 차이로 정상 snapshot이 전부 탈락한다.
- **peer 비교 최소 계약 (신규, 별도 함수로 명시)**: 다음 4개 일치 필수 — `benchmark` · `frequency` · `calculation_method` · **analysis-date 정책** (모든 관측의 window_end가 동일 analysis_date 기준 ≤7일 이내). window_start/end의 peer 간 차이는 다음 허용 규칙: 각 peer의 window_end는 `analysis_date−7일` 이내(필수), window 길이는 목표 2y 대비 **관측수 ≥80주로 이미 하한 보장** — 시작일 자체의 일치는 요구하지 않되 각 peer의 실제 window를 provenance에 기록해 감사 가능하게 한다.
- 4필드 중 하나라도 불일치 → 해당 peer 제외(사유 기록). 회사 beta_provenance와 snapshot의 방법 불일치 → 비교 전체 거부(`method_mismatch`).

### 쟁점 5 — 판정 계약: n≥5 · 고정 quantile · 전 outlier block [🔄 Codex 개정 수용]

- 순수함수 `engine/peer_beta.py::judge_company_beta(company_raw_bl, snapshot) -> PeerBetaJudgement`.
- 비교 대상: **raw levered vs raw levered** (Blume 값은 참고 기록만).
- **n_qualified ≥ 5** (v1의 4에서 상향 — Codex 수용). n<5 → `insufficient_peers`, 판정 거부.
- **quantile 고정**: `statistics.quantiles(sorted_betas, n=4, method="inclusive")` (stdlib, 선형보간). n=5에서 Q1/Q3 = 정확히 2·4번째 관측치 — 결정적. numpy 금지(엔진 순수성·재현성).
- **동률**: 허용(중복 제거 없음). **비유한 beta**: 수집 단계에서 이미 raise(§0 재현 — `regress_beta` fail-closed)라 판정 함수 도달 불가지만, 방어적으로 비유한 입력 발견 시 raise.
- **Q1 == Q3 (IQR=0) fallback**: fence가 [Q1, Q3] 점으로 퇴화 — 임의 tolerance 발명 대신 `degenerate_distribution` 상태로 **판정 거부** (fail-closed). 실제로는 상이한 5개 상장사 beta가 소수점 4자리까지 전부 일치할 때만 발생.
- 판정: Tukey fence [Q1−1.5·IQR, Q3+1.5·IQR] 내 → `validated`; 위/아래 → `outlier_high`/`outlier_low`; 그 외 `insufficient_peers`/`method_mismatch`/`degenerate_distribution`.
- **테스트 fixture 필수 포함**: n=4(거부)·n=5 경계, fence 경계값(정확히 fence 위), IQR=0, 동률 다수, method 불일치.

### 쟁점 5b — Gate 소비: outlier는 전부 block [🔄 v1 "warn" 폐기, Codex 수용]

- v1은 `consumed_blume`이면 warn을 제안했으나 **철회.** Codex 논거 수용: Blume shrinkage는 이상치 영향을 완화하는 **계산 정책**이지 peer 범위 검증 **통과 증거**가 아니다. "peer는 검증·차단 근거" 원칙과 일관되려면:
  - `outlier_high`/`outlier_low` → **severity "block"** — `consumed_raw`·`consumed_blume` 구분 없이.
  - `insufficient_peers`/`method_mismatch`/`degenerate_distribution` → "warn" (판정 불가를 침묵시키지 않음, 단 차단 근거로는 부족).
  - block이어도: beta·WACC 자동 교체 없음 · 가격 불변 · **profile `draft: true`만** (기존 `apply_gate_to_profile` 계약 — gate는 draft 플래그만 추가 가능). 해제는 사람이 근거 검토 후 수동 큐레이션으로만.
- **결과 예고 (은폐 금지)**: NVDA raw βL 2.040은 미국 반도체 peer 분포 상단을 넘을 가능성이 높다 → `outlier_high` block으로 nvda.yaml이 draft 유지될 수 있다. 이는 회귀가 아니라 정책의 의도된 작동이다 — nvda.yaml은 현재도 quality gate로 0/F draft(C-8)이므로 최종 상태 불변. C-5 검증은 "판정이 나되 WACC·가격·βL 불변"을 확인한다.

### 쟁점 6 — Snapshot provenance [v1 유지 + 🔄 Optional 계약 정정]

- 🔴 **"전부 Optional" 폐기 (Codex 수용)**: Optional은 **블록 레벨만** — `ValuationInput.forward_anchor: Optional[...] = None`, `peer_beta_snapshot: Optional[...] = None` (이것이 CLAUDE.md 하위호환 규칙의 정확한 적용 범위다). **블록이 존재하면 감사 필수 필드는 pydantic required** — 불완전 provenance는 `load_profile()`에서 ValidationError로 fail-closed.
  - `ForwardAnchor` required: basis/provider/as_of/retrieved_at/relative_period/source_hash + (metric 존재 시) value/n_analysts/estimate_type. `fiscal_period_end`만 Optional(실증 전 null 허용).
  - `PeerBetaEntry` required: name/ticker/segment_code/raw_levered_beta/blume_adjusted/window_start/window_end/frequency/benchmark/observation_count/calculation_method/source_hash.
  - `PeerBetaSnapshot` required: as_of/n_candidates/n_qualified/entries/exclusions/judgement/company_raw_bl. 집계 통계(median/q1/q3/min/max)는 n≥5일 때 required — n<5 거부 상태에서는 None 허용.
- 기존 45개 프로필은 두 블록이 없으므로 무영향 (C-10).

### 쟁점 7 — Forward 소비 범위 [v1 유지]

- 표시(콘솔/Excel — 실증 전 라벨 "컨센서스 +1y (예측치)") + verify C-6 수렴검사 전용. DCF/SOTP/시나리오 자동 주입 금지. `consolidated`/`ttm_anchor` = 제출 실적만, `forward_anchor` = 컨센서스만, 상호 복사 금지.

---

## 3. 구현 범위 (본 v2 승인 후 — Codex)

1. `schemas/models.py` — `ForwardAnchor`/`ForwardMetricEstimate`/`PeerBetaEntry`/`PeerBetaSnapshot`/`PeerBetaJudgement` (Optional은 블록 레벨만, §2 쟁점 6 계약)
2. `pipeline/forward_estimates.py`(신규) — yfinance 컨센서스 수집 + dated snapshot + source_hash + **+1y↔FY 대응 실증 로직** (실증 실패 시 fiscal_period_end=null 유지)
3. `pipeline/peer_beta_snapshot.py`(신규) — 적격 필터(4조건) + `collect_beta_observation` 재사용 + peer 비교 최소 계약(4필드) 검사
4. `engine/peer_beta.py`(신규) — `judge_company_beta` 순수함수 + fixture(경계·소표본·IQR=0·동률 포함)
5. `engine/investability_gate.py` — `peer_beta_range` finding (outlier=block · 판정불가=warn, 기존 6개 체크 불변)
6. `valuation_runner.py::load_profile` — 두 블록 파싱(merge 금지 계약 주석)
7. `output/console_report.py`(+Excel) — forward 라벨 (실증 전/후 구분)
8. `profiles/nvda.yaml` — 원자적 rewrite 스크립트(temp→fsync→os.replace→재read fail-closed). 수동 편집 금지.
9. `scripts/verify_nvda_phaseC.py` — C-1~C-12

## 4. 회귀표 (C-1~C-12, START 문서 채택 + v2 강화)

| # | 항목 | 기준 (v2 추가분 굵게) |
|---|---|---|
| C-1 | Forward 분리 | 미혼합 + **load_profile merge 경로 불통과 테스트** |
| C-2 | Forward provenance | provider·as-of·**metric별 n_analysts**·"consensus" + **실증 전 FY 재명명 없음** |
| C-3 | Peer 적격 | 4조건 필터 + **KR 피어 exclusion_reason 기록** |
| C-4 | Peer provenance | Phase A 패턴 + **matches_dataset 미사용, 4필드 비교 계약** |
| C-5 | 판정만 | validated/outlier 산출, WACC 11.52%·βL 1.697·가격 불변 |
| C-6 | 수렴 | 자동 수집 revenue vs `nvda_fy27e.yaml` 391,300 합리적 수렴(±10%) |
| C-7 | 🔴 넥써쓰 | 18/445/891 · 362 · 36,211 · 51,687 |
| C-8 | 🔴 Phase A | WACC 11.52% · βL 1.697 · consumed_blume · 7필드 |
| C-9 | 🔴 Phase B | fy/ttm 계약 · nvda.yaml `8ae6aab` bb276cf/467 (rewrite 후 신규 기준 재고정) |
| C-10 | 45개 프로필 | crash 0 (**블록 부재 시 완전 무영향**) |
| C-11 | pytest | 1013 passed + 신규 (deselect 유지) |
| C-12 | NUL/AST/CRLF | clean · git object 검증 |

## 5. 잔여 미결 (구현 중 확정, 정책 아님)

1. yfinance `+1y` 실증 결과 기록 위치(provenance 필드명) — 구현 시 Codex 재량.
2. 콘솔/Excel forward 표기 문구 — 한국어 사용자 대면 규칙 준수.

---
*v1 → v2 변경: Codex Round 1 조건 6건 전부 수용 (n≥5 · outlier 전부 block · metric별 provenance · +1y 실증 전 재명명 금지 · Optional 블록 레벨 한정 · matches_dataset 금지+4필드 비교 계약). 반박 0건. 구현은 본 v2 승인 후 시작.*

---

## 6. Claude 독립 검증 (2026-07-17, 구현 후 — Codex 주장 전부 재현 시도)

### 재현 성공 (Codex 보고 사실 확인)

| 항목 | 독립 재현 결과 |
|---|---|
| C-1~C-12 | `scripts/verify_nvda_phaseC.py` 로컬 fresh bytecode 실행 → **ALL PASS** (C-7/C-8은 스크립트가 nexus/phaseA verify를 subprocess 재실행, exit 0) |
| pytest | **988 passed, 5 deselected 독립 재현** (sandbox, 전체 의존성 설치 후). 🔴 START 문서 C-11의 "1013"은 **부정확** — Phase B closeout 실측 기준은 **979**(`HANDOFF_CODEX_nvda_phaseB_closeout.md` L53). 988 = 979 + 7(test_peer_beta 4·test_forward_estimates 1·test_nvda_phaseC 2) + 2(test_investability_gate peer_beta 추가). **테스트 소실 없음, 완전 분해.** |
| 판정 수치 | snapshot 6개 raw beta에서 Q1 2.059578·median 2.144695·Q3 2.346086·fence [1.629817, 2.775848] **독립 재계산 완전 일치**. 수기 (n-1)p 보간 ≡ `statistics.quantiles(method="inclusive")` 수치 검증. 2.040 ∈ fence → validated 확인 |
| ARM 민감도 | 감사 목록(`a6b1356`) 외 신규 피어 ARM(2.585) **제외 시에도** n=5, fence [1.828, 2.412] → **validated 불변** (판정이 ARM 포함에 좌우되지 않음) |
| C-5 불변 | forward/peer 블록 제거 사본과 `run_valuation` 비교 — wacc·scenarios 동일 (verify + `test_nvda_phaseC.py` 이중 확인) |
| FY27 실증 | `relative_period: 0y` + `fiscal_period_end: 2027-01-25`가 `info.nextFiscalYearEnd` payload 유래로 코드 확인 (`forward_estimates.py` L54-61). metric별 n_analysts 51/50, source_hash 64자, 캐시 원자적 기록(temp→fsync→replace→재해시) |
| 계약 | 블록 레벨 Optional + 내부 required(validator: qualified→10필드 필수, unqualified→사유 필수, n_analysts>0, revenue∨eps 필수) · `load_profile` merge 금지 주석+구조 · gate outlier=block(consumed_blume 무관)/판정불가=warn/미제공=warn-pass |
| 무결성 | 변경 .py 8종 + 신규 5종 ast.parse OK · NUL 0 · nvda.yaml CRLF 596행 · HEAD `8ae6aab` 무변경 · 미커밋 263파일 보존 |

### 잔여 이탈 (경미 — 판정·가격 영향 없음, 커밋 전 처리 권고)

| # | 이탈 | 정책 근거 | 영향 |
|---|---|---|---|
| D1 | `degenerate_distribution`(IQR=0 판정 거부) **미구현** — Q1==Q3이면 outlier→block으로 귀결 | §2 쟁점 5 | 정책보다 보수적 방향이나 계약과 상이. 실발생 확률 극저 |
| D2 | 필수 fixture 3종 누락: fence 정확 경계값·IQR=0·동률 다수 | §2 쟁점 5 | 테스트 커버리지 계약 미충족 |
| D3 | 삼성전자(005930.KS) 후보 목록 부재 — SK하이닉스만 exclusion 기록 | §2 쟁점 3 | 감사 기록 불완전 |
| D4 | ARM이 감사 목록(`a6b1356`) 외 신규 추가, `core_business_match: True` 선언만 존재 | §2 쟁점 3-4 | 판정 불변(위 민감도)이나 적격 근거 문서화 필요 |
| D5 | `+1y` 분기가 fiscal_end를 연도 산술 외삽(`next_end.replace(year+1)`) — 미실증 명명 금지 위반 경로. `fiscal_period_end`가 required라 +1y에서 null 유지 불가 | §2 쟁점 2 | NVDA는 0y 경로라 미사용. 코드 경로만 존재 |
| D6 | 신규 .py 5종 LF (규칙: 작업트리 CRLF 유지) | Session Safety | git blob LF 정규화로 diff 무해 |

**종합: Phase C 핵심 계약(혼합 금지·판정만·WACC/가격 불변·provenance) 전부 검증됨. D1~D5는 커밋 전 소규모 후속 수정 또는 커밋 후 백로그 등재 중 택일 — 어느 쪽도 판정·수치에 영향 없음.**

### Codex 후속 조치 완료 (2026-07-17)

- D1: `degenerate_distribution` 상태와 fail-closed 판정 구현.
- D2: fence 정확 경계, IQR=0, 동률 다수 fixture 추가.
- D3: 삼성전자 후보와 `benchmark_mismatch` 제외 기록 추가.
- D4: 적격 peer마다 `qualification_reason`을 필수 기록하고 ARM 근거 명시.
- D5: `+1y`에서 회계연도 종료일 외삽과 FY 승격을 금지. 종료일·FY 라벨은
  명시적 검증이 가능한 `0y` 경로에서만 기록.
- D6: Phase C 신규 Python 파일을 CRLF로 정규화하고 AST/NUL 재검증.
- 최종 재검증: C-1~C-12 ALL PASS, `992 passed, 5 deselected`.
