# 프롬프트 — skill 지표 실측 해석 (세션 C 후속)

> 아래 "---" 블록을 새 focused 세션에 그대로 붙여넣어 시작.
> 선행: `PLAN_skill_metrics.md`(구현 완료), `HANDOFF_backtest_diag.md`(① 진단), CLAUDE.md.
> 이 세션의 산출물은 **해석 + 다음 워크스트림 결정**이지, 새 기능 구현이 아니다.

---

EFE backtest의 **naive-baseline skill 지표를 실측으로 읽고 해석**해줘. 직전 세션에서 `engine/skill_metrics.py`(MASE / Theil U2 / surprise-direction / RW 방향적중률 / 컨센서스 skill score)를 구현해 `BacktestResult.skill`에 배선하고 md/html/xlsx·README에 렌더까지 끝냈다. **이번 세션은 그 숫자를 해석해서 다음 타깃을 데이터로 정하는 것**이 전부다. 코드 수정은 해석에 꼭 필요한 최소한만.

## 0. 먼저: 실측 숫자 확보
샌드박스 fixture는 분기 수가 부족해 `skill=None`만 나온다. **실측은 Windows 호스트에서만** 나온다.
- 내가(사용자) 호스트에서 `python cli.py --company sk_hynix`를 돌려 `reports/sk_hynix_YYYYMMDD.{md,html,xlsx}`의 **Skill 섹션**을 붙여넣어 줄 것이다. (또는 그 md를 첨부.)
- 숫자를 받으면 그걸 1차 근거로 삼아라. 받기 전에는 해석을 지어내지 말 것.
- (참고) 세션 B 후 절대값: 매출 MAPE 9.51%, EPS MAPE 14.66%, bias_eps −10.55%.

## 1. 해석 규칙 (PLAN_skill_metrics §5 Acceptance)
- **skill 주장은 `MASE<1` 그리고 `Theil U2<1`일 때만.** 둘 중 하나라도 ≥1이면 "no edge"로 **정직하게** 결론.
- 방향 적중률은 **model vs RW를 나란히** 봐라. 둘이 비슷하면(예: 87.5% vs 87.5%) 구조적 상승 사이클의 "항상 up"이라 edge 아님.
- surprise-direction은 `ConsensusRecord.history`(과거 추정)만 사용된 값. **N을 반드시 함께** 보고, N이 작으면(<4) 참고용으로만.
- 8Q = 작은 표본. 점추정 과대해석 금지 — 방향성 결론까지만.

## 2. 분기점 (해석 결과 → 다음 워크스트림)
1. **EPS MASE ≥ 1 (RW에 짐) 이면 → 다음 세션은 verdict #2: tax/finance 진단.**
   bias_eps −10.6% + "actual·consensus 양쪽에서 발산"이 이미 여기를 가리킨다. FX·below-the-line를 고정세율과 분리, overlay/오차밴드 후보 검토. → `PLAN_tax_finance.md`를 plan mode로 작성하고 끝(구현은 또 다음 세션).
2. **EPS MASE < 1 그리고 Theil U2 < 1 이면 → 모델에 edge 있음.** 어느 분기/드라이버에서 우위가 나오는지 attribution으로 확인하고, 그 다음은 gross-margin 잔차(+3.2%) 또는 컨센서스 스케일(①-B 후속)로.
3. **매출은 skill, EPS는 no edge** 패턴이면 → 병목은 revenue→EPS 변환부(margin·tax/finance·share). tax/finance(1번)가 1순위.

## 3. 가드레일
- 해석 세션이다. **새 코드 작성 최소화** — 필요하면 읽기 전용 진단(`scripts/diagnose_divergence.py` 등)만.
- 가정 *수치* 변경은 제안(초안)까지만, 확정·소유는 사용자(CLAUDE.md).
- 결론은 `HANDOFF_*.md`에 before/after 한 줄 + 다음 타깃으로 남겨라. README의 "리포트 참조" 자리에 실측 MASE/Theil/surprise를 채울지 여부도 제안.
- 샌드박스 주의: 호스트-mount 편집 반영이 불안정할 수 있음(메모 `cowork-mount-stale-edits` 참고). 새 파일은 정상 인식, 기존 파일 편집은 new-file+`cp`로 강제 동기화.

## Acceptance
- 실측 skill 표를 규칙대로 읽어 **"naive 대비 우위 / no edge"를 분기·EPS 각각 명시.**
- 그 결론으로 **다음 워크스트림 1개**를 데이터 근거와 함께 확정 (가장 유력: tax/finance verdict #2).
- 필요 시 `PLAN_tax_finance.md` 초안 + `HANDOFF` 한 줄 갱신. 수치 변경은 사용자 확정 대기로 보고.
