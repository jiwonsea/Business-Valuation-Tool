# Codex 핸드오프 — Round 4: **Monte Carlo가 재현되지 않는다** (P1) + 잔여 정리

> 실행 위치: `F:\dev\Portfolio\business-valuation-tool` | 재현: `profiles/nexus.yaml`
> 작업 규칙: `git checkout/restore/reset --hard` 금지 · 원자적 쓰기 · **마지막 쓰기 이후 NUL 스캔 후 실제 출력 첨부**

---

## 🔴 R4-1. 같은 프로필·같은 코드·같은 seed인데 **MC 결과가 실행마다 다르다**

### 증상 (연속 2회 실행, 파일 변경 없음)

```
python cli.py --profile profiles/nexus.yaml --excel
  [Monte Carlo] 5th 145원 | Median 349원 | 95th 590원

python regen_nexus_artifacts.py        (같은 run_valuation 호출)
  P5 150원 | 중앙값 350원 | P95 598원 | 음수 0.1%
```
`MCInput(seed=42)`가 고정돼 있는데도 **분포가 바뀐다.** as-of 보고서(`price_as_of` 도입까지 한 마당에)가 실행할 때마다 다른 숫자를 낸다.

### 근본 원인 — `valuation_runner.py:2274`

```python
mc_mult_codes = set(seg_ebitdas.keys())      # ← set
...
multiple_params={
    c: (mults[c], mults[c] * vi.mc_multiple_std_pct / 100)
    for c in mc_mult_codes                    # ← set 순회
    if mults.get(c, 0) > 0
},
```

파이썬은 **문자열 해시를 프로세스마다 랜덤화**한다(`PYTHONHASHSEED` 미고정 시 기본 동작). 따라서 `set` 순회 순서가 실행마다 달라지고, `engine/monte_carlo.py`가 `multiple_params`를 순회하며 `rng.lognormal(...)`을 **호출하는 순서**가 바뀐다 → 동일 seed의 난수열이 **GAME과 ONESTORE에 서로 다르게 배정**된다.

세그먼트가 1개면 드러나지 않는다. **혼합 SOTP(2개 이상)에서만 터진다.**

> Codex 자신이 Round 1 리뷰 [필수 5]에서 이 증상을 정확히 짚었다:
> *"원인은 seed가 있어도 세그먼트 코드가 set 순회 순서에 따라 GAME/ONESTORE 난수열에 다르게 배정되기 때문이다. ... 'seed 42 재현 결과'라고 단정할 수 없다."*
> **그때 지적만 하고 고치지 않았다.** 이제 고쳐라.

### 요구사항
1. `mc_mult_codes`를 **결정적 순서**로 만들어라 (`sorted(...)` 또는 삽입 순서 보존 리스트). `seg_ebitdas`·`revenue_params`·`segment_methods` 등 **MC에 들어가는 모든 dict/set 구성 경로**를 함께 훑어라 — 한 곳만 고치면 다른 곳에서 재발한다.
2. **결정성 회귀 테스트**: 동일 프로필을 **별도 프로세스 2회** 실행해 `MCResult`의 `p5/median/p95/mean/std`가 **완전히 일치**하는지 검증하라. (같은 프로세스 내 2회 호출로는 이 버그가 안 잡힌다 — `PYTHONHASHSEED`는 프로세스 단위다. `subprocess`로 돌리거나 `PYTHONHASHSEED`를 다르게 준 2회 실행을 비교하라.)
3. 확인: `PYTHONHASHSEED=0`과 `PYTHONHASHSEED=1`에서 결과가 같아야 한다.

---

## 🟡 R4-2. 실행 로그(`_run_bvt.txt`)에 무효 상대가치가 남아 있다

Excel에서는 제거됐지만 **실행 로그에는 `P/B 4.07` · `EV/EBITDA 56.18` · `내재 WACC 2.34%`가 남아 있다**(PART B 이전 스냅샷). 보고서 자동화가 로그를 재사용하면 그대로 유출된다.

**요구**: `valuation-results/2026-07-13-nexus-onestore/_run_bvt.txt`를 현재 코드로 재생성하고, 로그가 산출물로 재사용될 수 있는 경로가 있는지 확인하라.

## 🟡 R4-3. Dashboard MC 패널이 **비활성 드라이버를 나열한다**

현재 SOTP는 `ev_revenue` + `pbv`인데, Dashboard의 MC 입력 목록에 **WACC 분포·terminal growth 분포**가 그대로 표시된다. 결과에 영향은 없지만 **독자는 작동하는 변수로 오해**한다.

**요구**: MC 입력 패널은 **실제로 샘플링된 드라이버만** 표시하라. DCF TV 리샘플링이 비활성(`wacc_for_dcf == 0`)이면 WACC/TG 행을 출력하지 마라.

## 🟡 R4-4. 접수된 계산 복제 잔여 (Round 3에서 자진 신고)

- `cli.py`의 reverse-rNPV 후처리
- `output/sheets/valuation.py`의 DDM 민감도 재계산 — `result.sensitivity_primary`가 이미 있는데 렌더러가 중복 계산

`.claude/rules/reporting-boundary.md`를 방금 만들었으니 **그 규칙에 맞춰 정리하라.**

## ⚪ R4-5. 잡정리
- `valuation_runner.py:74` 미사용 `apply_gate_to_profile` import (Ruff)
- `db/migrations_backtest.sql` Supabase 미적용 → `Failed to save valuation for 넥써쓰` 발생 중. `supabase db push` 필요 (외부 작업)

---

## 회귀 기준
| 항목 | 기준 |
|---|---|
| **MC 결정성** | `PYTHONHASHSEED`를 바꿔 별도 프로세스 2회 실행 → `p5/median/p95` **완전 일치** |
| nexus | Base 364원 / 확률가중 394원 / as-of 1,505원 / 역방향 WACC 미출력 |
| 핵심 산출물 | 46개 프로필 diff 0 (⚠️ **MC 값은 결정성 수정으로 바뀔 수 있다** — MC를 쓰는 프로필의 변경분을 표로 보고) |
| 파일 무결성 | **NUL 스캔 실제 출력** + 전 `.py` AST |
| 테스트 | `verify_partB_round2.py` / `verify_partB_excel.py` / `pytest` |
