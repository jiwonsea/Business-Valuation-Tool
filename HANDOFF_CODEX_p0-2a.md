# P0-2a 베타 정상화 계약 — 승인·커밋 기록

**판정:** CODEX 승인 (4차 검토). 계약층 provenance 우회 경로 전부 폐쇄.
**범위:** 순수 계약 + 상태 + 프로즌 테스트. 소비 배선(P0-2b)은 여전히 **P0-4 이후**.

---

## 0. 4차 블로커 2건

| # | 지적 | 수정 |
|---|---|---|
| 1 | `method="declared_assumption"`인 산업 beta가 관측치로 소비 | `IndustryBetaEntry` validator에 **`source.method in OBSERVED_METHODS`** 추가. Damodaran 출처를 달아도 가정은 관측치가 아니다 → 생성 거부 |
| 2 | target(S&P 500)과 peer(KOSPI)의 다른 데이터셋을 직접 비교 | `BetaObservation.dataset_mismatches()` 신설. 게이트가 교차검증 **전에** target 관측과 peer 스냅샷의 관측창·빈도·벤치마크·계산법·기준일을 대조하고, 불일치하면 **stale peer와 동일하게 peer 근거에서 제외 + 경고**한다(상장사의 primary는 raw beta이므로 차단하지 않음). 같은 데이터셋이면 교차검증은 그대로 작동 |

**문서**: `PLAN_deep_research.md:134`의 §2.6 참조와 데이터셋 조항을 작업 트리에서 손봤으나, PLAN은 **untracked라 커밋 이력에 없다** (§5).

**재현**
```
declared_assumption 산업 beta        -> ValidationError (생성 거부)
S&P500 target vs KOSPI peer(median 0.5) -> consumed_raw, peer_median=None, peer_count=0 + 데이터셋 경고
같은 KOSPI 데이터셋                   -> blocked_reference_conflict (교차검증 정상 작동)
```

**검증**: 아래 §3 참조 (모든 수치는 최종값 기준).

---

## 1. 블로커 5건

| # | 지적 | 수정 |
|---|---|---|
| 1 | 대상 회사 beta의 look-ahead 허용 | **`BetaObservation.equity_beta.as_of == window_end` 강제** — 2020년에 끝난 관측창을 오늘 날짜로 포장하면 생성 실패. `freshness(evaluation_date)` 추가(허용 시차 `BETA_OBSERVATION_MAX_AGE_DAYS = 7`): 관측창이 평가일보다 미래면 `blocked_invalid_observation`, 시차 초과면 `blocked_stale_observation`. 게이트가 **peer보다 먼저** target을 검사한다 |
| 2 | stale peer가 유효한 fallback까지 차단 | 미래 스냅샷만 즉시 차단(look-ahead)하고, **stale은 peer 근거에서 제외**한다(`peer_median=None`, `peer_count=0`) → 상장사는 raw beta 소비 + "교차검증 불가" 경고, 비상장사는 fresh 산업 테이블로 fallback. **다른 근거가 없을 때만** `blocked_stale_peer_snapshot` |
| 3 | 동일 peer 4복제로 N=4 충족 | `BetaPeerMember.legal_entity_id` 신설(필수). 스냅샷 validator가 included 구성원의 **법인 ID 고유성 + 대소문자 무시 ticker 고유성**을 강제. 같은 법인 4개는 생성 실패 |
| 4 | D/E·세율 Source의 관측 자격·기준일 미검증 | `method in OBSERVED_METHODS` 강제(가정을 Source로 위장 불가). unlevered basis의 included 구성원은 D/E·세율 Source가 **둘 다 필수**이며, 각 Source의 `as_of`가 **스냅샷 기준일과 일치**해야 한다 |
| 5 | 산업 테이블 수집일 look-ahead | 생성 시 `source.as_of <= collected_at`(존재하지 않는 자료를 수집할 수 없다), 소비 시 `collected_at <= evaluation_date`(미래에 수집한 테이블은 look-ahead) → `blocked_invalid_industry_table` |

**문서**: PLAN §2.3 비상장 행의 peer 참조(§2.6 → §2.5)와 "고유 법인 N ≥ 4"도 작업 트리에서만 반영됐다 (§5).
(코드 쪽에서는 스냅샷 `as_of == window_end`를 강제한다 — 스냅샷 기준일이 관측창의 끝이 아니면 시간축이 무너진다.)

## 2. 적대적 입력 재현 (3차 지적 그대로)

```
target beta as_of=2027-01-01        -> blocked_invalid_observation
2020년 관측창 + as_of=오늘 포장      -> ValidationError (as_of != window_end)
stale peer + fresh 산업 테이블       -> consumed_industry_table   (fallback 유지)
stale peer + 상장사 raw beta         -> consumed_raw + "교차검증 불가" 경고
stale peer + 다른 근거 없음          -> blocked_stale_peer_snapshot
동일 법인 4복제                      -> ValidationError (peer 중복)
declared_assumption D/E Source       -> ValidationError (관측치 아님)
수집일 2027-01-20 산업 테이블         -> blocked_invalid_industry_table
```

## 3. 검증

| 항목 | 결과 |
|---|---|
| `pytest tests/test_beta.py -q` | **78 passed** |
| `pytest tests/ -q --ignore=tests/test_quality.py` | **863 passed, 2 failed** — FRED 2건(샌드박스 마운트 `PermissionError`) |
| `ruff check` (변경 3파일) | All checks passed |
| `cli.py --profile profiles/sk_ecoplant.yaml` | **35,066원** — 배선 전이므로 무변화 |

## 4. 상태 머신 (최종)

```
시간축   : target 관측창 미래         -> blocked_invalid_observation
           target 관측 stale(>7일)     -> blocked_stale_observation
           peer 스냅샷 미래            -> blocked_invalid_peer_snapshot
           peer 스냅샷 stale(>7일)     -> peer 근거에서 제외 (경고) — 최후에만 blocked_stale_peer_snapshot
           산업 테이블 미래/수집일 미래 -> blocked_invalid_industry_table
           산업 테이블 stale(>400일)    -> blocked_stale_industry_table
정합성   : peer basis != target        -> blocked_basis_mismatch
           NaN/Inf                    -> blocked_invalid_number
           D/E<0 · 세율∉[0,100] · 분모≤0 -> blocked_invalid_capital_structure
상장     : 관측 없음                  -> blocked_no_provenance
           D/E·세율 결측               -> blocked_no_capital_structure
           언레버 βU > median×1.5      -> blocked_reference_conflict  (고유 peer ≥ 4)
           그 외                      -> consumed_raw / consumed_raw_equity(금융업)
비상장   : 고유 peer >= 4            -> consumed_peer_median
           산업 테이블 fresh            -> consumed_industry_table
           근거 없음                   -> blocked_no_reference
```
범위 이탈([0.3, 2.0])은 어느 경로에서도 차단하지 않는다 — `sensitivity_required=True` + 경고만.

## 5. 문서 취급 (PLAN_deep_research.md)

`PLAN_deep_research.md`는 **untracked이며 이 리포지토리에서 버전 관리되지 않는다.**
따라서 P0-2a에서 "정정"이라고 적은 항목들 — §2.3의 same-basis 비교, 비상장 peer 참조 §2.6 → §2.5,
"다른 데이터셋 peer는 교차검증에서 제외" — 은 **작업 트리의 PLAN 파일과 이 핸드오프에만 남아 있고
커밋 이력에는 없다.** PLAN을 버전 관리하기로 하면 단독 docs 커밋으로 추가해야 한다 (별도 판단 사안).

계약의 단일 진실 원천은 **코드와 프로즌 테스트**다 (`schemas/provenance.py`, `engine/normalize.py`,
`tests/test_beta.py`). PLAN과 코드가 어긋나면 코드가 맞다.

## 6. 다음 단계

- **P0-4**: 멀티플과 분리된 peer beta 관측 스냅샷 수집 → `BetaPeerSnapshot`을 실제로 채운다.
  계약이 요구하는 것: 고유 `legal_entity_id`, 동일 관측창·빈도·벤치마크·계산법·기준일,
  D/E·세율 **관측** Source(`method in OBSERVED_METHODS`, `as_of == 스냅샷 as_of`),
  7일 이내 스냅샷, `as_of == window_end`, 멀티플 필드 금지.
  주의: yfinance `info["beta"]`는 계약상 관측치가 아니다 → **가격 시계열에서 직접 회귀**해야 한다.
- **P0-2b**: 소비 배선 + V1~V4 제거(`profile_generator._estimate_wacc_params`)
  + `ai/validators.py::validate_wacc` 클램프 제거. `publishable=False` → investability gate blocker.
- `engine/wacc.py::_HAMADA_DE_CAP`(200%)는 **미변경** — 리레버 시점의 별도 방법론 정책이며 별도 판정 대상.
