# 세션 B 프롬프트 — gross-margin 앵커 재캘리브레이션

> 아래 블록을 새 focused 세션(Cowork/Codex)에 그대로 붙여넣어 시작.
> 선행: `HANDOFF_backtest_diag.md`(진단 verdict), `PLAN_backtest_honesty.md` workstream ① 세션 B.

---

EFE의 backtest gross-margin 계통 오차를 고쳐줘. **이 세션의 스코프는 gross margin 하나뿐.** tax/finance와 consensus는 손대지 마(별도 세션).

## 배경 (진단 결과, `HANDOFF_backtest_diag.md`)
- 8Q backtest에서 gross-margin 기여가 **모든 분기 양(+), 평균 +10.6%** → 모델 GP마진이 일관되게 실측보다 높음(단방향 계통 bias).
- **핵심 모순**: `profiles/sk_hynix.yaml` 주석은 anchor를 "DART 실측 2024Q1 blended GP 38.6%에 고정"한다는데, 진단상 2024Q1 gross-margin 기여가 +17.3% → 모델 GP마진 ≈ 45%. **앵커가 실측을 재현하지 못함.**
- 의심 메커니즘: `engine/margin_model.py::_cost_per_bit_margin` = `1 − (1−anchor)·cost_factor/asp_factor`. 앵커 분기부터 `margin_periods_since_anchor ≥ 1`이고 `asp_*` carryover > 1, `cost_decline_qoq_* > 0`이라 `cost_factor/asp_factor < 1` → 마진이 앵커값을 **첫 분기부터 초과**. (`engine/segment_revenue.build_margin_carryover` 및 backtest의 ASP 누적이 앵커 분기를 포함해 누적하는지 확인할 것.)

## 작업 순서 (goal-driven, failing-test 우선)
1. **baseline 고정**: 수정 전 `DART_API_KEY=<any> python scripts/diagnose_divergence.py --company sk_hynix` 실행, 8Q 표 + 매출/EPS MAPE를 기록(`pytest -q`도 green 확인).
2. **failing-test 작성**: "2024Q1(=앵커 분기) 모델 blended GP마진 == DART 실측(≈38.6%) ± tol". 현재 fail해야 정상. (`tests/test_margin_model.py` 또는 신규.)
3. **원인 격리**: 마진이 앵커를 초과하는 지점이 (a) periods_since_anchor 오프바이원(앵커 분기는 0이어야 하는데 1), (b) asp carryover가 앵커 분기 qoq를 포함, (c) `cost_decline_qoq_*`/`gm_*` 값 자체 과대 — 중 무엇인지 driver attribution으로 좁혀라. **추정으로 여러 줄 바꾸지 말 것.**
4. **수정**: 격리된 그 한 곳만 surgical하게. 가정 *수치*(gm_hbm/gm_ddr/gm_nand/cost_decline)를 바꿔야 하면 **직접 확정하지 말고** 출처 명시한 재캘리브레이션 **초안**을 제시하고 before/after attribution을 보여줘 — 수치 확정·소유는 사용자다(CLAUDE.md).
5. **재측정**: `scripts/diagnose_divergence.py` 재실행 → 목표 **gross-margin 기여 평균 ≈ 0**(±2~3%p), 단방향 bias 해소. `pytest -q` 전부 green.

## 가드레일
- 변경 라인은 전부 이 작업으로 추적. tax/finance·consensus·signal_backtest는 `NOTICED BUT NOT TOUCHING`으로만.
- 회귀(다른 분기 매출/EPS MAPE 악화) 시 중단·격리 후 보고.
- 샌드박스: cache hit로 오프라인 동작. `_ssl_setup` Windows-path는 host에서만 정상(샌드박스 import 우회 필요 시 별도 처리).
- 끝나면 `HANDOFF_backtest_diag.md`에 before/after 한 줄 추가 + 결과 요약.

## Acceptance
- 앵커 분기 GP마진이 실측과 일치(test green).
- 8Q gross-margin 기여 평균이 0 근처, 매출/EPS MAPE 회귀 없음(개선이면 더 좋음).
- 재캘리브레이션이 수치 변경을 수반하면 사용자 확정 대기 상태로 보고.
