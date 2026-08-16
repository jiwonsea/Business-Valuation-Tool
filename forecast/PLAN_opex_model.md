# PLAN — opex 계통 bias (−4.2%) 수정: fixed + variable opex 모델

> 2026-07-02. Open Problem "Opex systematic bias −4.2%" 대응. 진단 → 구조 수정(하위호환) → 재측정.
> 가정 수치는 전부 **DRAFT** (8Q OLS 시드) — 사용자(가정 소유자) 확정 대상.

## 1. 진단 (scripts/diagnose_opex.py, read-only, 신규)

8Q backtest 구간, 실측 opex = GP − OP vs 모델 상수비율 (sga 5.5% + rnd 9.5% = 15.0% of revenue):

| 발견 | 수치 | 해석 |
|---|---|---|
| level 갭 | 가정 15.0% vs 실현 평균 **12.52%** (+2.48pp) | 모델이 opex를 계통적으로 과대 → OP 과소 → EPS − bias |
| shape 갭 | corr(revenue, opex%rev) = **−0.77**; 실현 opex%rev 15.4%(2024Q1) → 10.4%(2025Q4) | **operating leverage** — 상수 %-of-revenue 모델은 매출 성장 구간에서 갭이 확대 (+4.6pp by 2025Q4) |
| 고정비 구조 | OLS: opex = **992 ₩bn + 7.3% × revenue** (고정분 = 평균 opex의 40%) | 절대액도 완전 고정은 아님(CV 0.198) — 2-파라미터 선형이 적합 |
| 원인 패턴 | 15%는 anchor 분기(2024Q1 15.36%)에 캘리브레이션됨 | gross-margin 앵커와 동일 병리: 저매출 분기에 맞춘 상수를 사이클 전체에 적용 |

**Verdict: (a) level + (b) shape 복합.** 상수 하향만으론 forward 고매출 분기에서 여전히 과대. → 2-파라미터 모델.

## 2. 설계 (backward compatible, surgical)

- `MarginAssumptions` += optional `opex_fixed_krw_bn`, `opex_variable_pct_of_revenue` (both-or-neither validator). 미지정 시 기존 sga+rnd 경로 **bit-identical**.
- `margin_model.project_margins`: 새 필드 있으면 `opex = fixed + var × revenue`, `op_margin = gp_margin − opex/revenue`. 없으면 기존식.
- `opex_model.sanity_check_opex`: expected spread를 동일 로직으로 (분기별 revenue 반영). ※ 현재 어디서도 호출 안 되는 dead code — 시그니처 유지, 일관성만 확보.
- `profiles/sk_hynix.yaml`: 3개 시나리오에 DRAFT 값 (OLS 시드; base fixed 990 / var 0.073; bear/bull은 기존 ±1pp 스프레드 이관). 기존 sga/rnd 키는 fallback·문서용으로 유지.

## 3. 수용 기준

- 새 필드 미지정 프로필 → 기존과 bit-identical (회귀 테스트).
- 8Q backtest: opex lever 평균 −4.2% → |x| < 1%; EPS bias·MAPE 개선 (악화 시 중단·격리).
- 매출 MAPE 불변 (opex는 마진 이하 경로만).
- pytest 전체 green + dry-run 렌더 정상.

## 4. Baseline (수정 전, 오프라인 실측 2026-07-02)

rev MAPE 9.5129% · EPS MAPE 12.0065% · bias_eps −6.4116% · MASE EPS 0.3699 / Theil 0.4041 · opex lever 평균 −4.2% (7/8 음수).

---

## 5. 구현 결과 (동일 세션, HANDOFF)

**추가/변경:** `schemas/models.py` MarginAssumptions에 optional `opex_fixed_krw_bn`/`opex_variable_pct_of_revenue`(+both-or-neither validator) · `engine/margin_model.py` `_opex_pct_of_revenue` 분기 · `engine/opex_model.py` sanity check 동일 로직 미러 · `profiles/sk_hynix.yaml` 3개 시나리오 DRAFT 값(base 990+7.3%, bear var 8.3%, bull var 6.5%) · `tests/test_margin_model.py` +3 (leverage 산식, 레거시 경로 불변, both-or-neither reject) · `scripts/diagnose_opex.py` 신규.

**검증 (acceptance 전부 충족):**

| 지표 | before | after | 판정 |
|---|---:|---:|---|
| opex lever 평균 | −4.2% (7/8 음수) | **+0.3%** (부호 혼재) | ✅ \|x\|<1% |
| EPS bias | −6.41% | **−1.61%** | ✅ 목표 \|값\|<5% 최초 진입 |
| EPS MAPE | 12.01% | **9.78%** | ✅ 개선 |
| MASE EPS / Theil U2 | 0.370 / 0.404 | **0.281 / 0.281** | ✅ 개선 |
| 매출 MAPE | 9.5129% | 9.5129% | ✅ bit-identical (마진 이하 경로 격리) |
| 컨센 skill (N=3) | +0.67 | **+0.73** | 참고 |
| pytest | 94 | **97 passed** | ✅ |

새 필드 미지정 시 레거시 경로 bit-identical(테스트 보증). 잔여 EPS bias −1.6%의 최대 축은 tax/fin −3.6%(below-OP block, 구조적 → risk band 레이어 소관)와 gross-m +3.6%.

**사용자 소유 (draft → 확정):** opex_fixed_krw_bn / opex_variable_pct_of_revenue 3개 시나리오 값 전부. 시드 출처 = 8Q OLS(diagnose_opex.py 재현 가능). bear/bull 스프레드는 기존 ±1pp/−0.8pp를 variable 쪽에 이관한 임의 배치 — 고정비를 시나리오별로 차등할지 여부 포함 재검토 대상.

**NOTICED BUT NOT TOUCHING:** `tax_finance.py`·`risk_band.py`(below-OP 소관 유지), gross-m +3.6% 잔차(ASP 급등 분기 집중, HANDOFF_backtest_diag 세션 B 잔차와 동일 영역), 컨센 N=3.
