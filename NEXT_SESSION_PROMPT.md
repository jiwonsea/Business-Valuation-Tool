# Business Valuation Tool: 다음 세션

## 현재 상태 (2026-04-13 기준)
- 커밋: `2203856` (main, origin 동기화 완료)
- 테스트: 578 pass / 0 fail
- `TestScenarioDriverRoundTrip` 고정 fixture 분리 완료 (`tests/fixtures/msft_frozen.yaml`, `tsla_frozen.yaml`)
- 주간 파이프라인이 `profiles/*.yaml`을 덮어써도 테스트 영향 없음

---

## 세션 시작 프롬프트 (복사해서 사용)

---

[Business Valuation Tool] Phase 3 캘리브레이션 인프라 스펙 확정 (인터뷰 모드)

경로: `F:\dev\Portfolio\business-valuation-tool`
현재 상태: `2203856`, 578 pass

## 배경
Phase 1(엔진 감사) / Phase 2(distress 엔진, scenario 개선) 커밋 완료. Phase 3는 `memory/project_valuation_tool_audit.md`에 "캘리브레이션 인프라"로만 백로그 기록 — 구체 스펙 없음.

## 이번 세션 목표 (스펙 확정만, 구현 X)
AskUserQuestion 기반 인터뷰로 Phase 3 스펙을 `SPEC_phase3_calibration.md`에 확정.

## 인터뷰에서 반드시 물을 것
1. **캘리브레이션 대상**: (a) 시나리오 확률 조정, (b) segment multiple 보정, (c) WACC 파라미터 튜닝, (d) DCF growth 조정 — 무엇을 자동/반자동 튜닝할 것인가?
2. **정답 신호(ground truth)**: 실현 주가? 애널리스트 consensus? 과거 예측 오차? → 어느 지표를 loss로 쓸지
3. **캘리브레이션 범위**: 종목별 단일 튜닝 vs. 시장(KR/US)·섹터 단위 공통 파라미터 학습
4. **자동화 수준**: 수동 override 유지 vs. 파이프라인에서 자동 적용
5. **성공 기준**: 예측 오차 감소 %? 특정 벤치마크 일치?
6. **데이터 요구**: 과거 분석 결과 저장 여부, 신규 수집 필요한 데이터
7. **스코프 경계**: 이번 단계에서 하지 않을 것 (예: ML 모델, 실시간 재계산 등)

## 완료 기준
- `SPEC_phase3_calibration.md` 작성 + 커밋
- 구현은 **별도 세션**에서 clean context로 진행

## 모드: plan (인터뷰 + 스펙 작성만, 코드 X)
