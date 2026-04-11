# Business Valuation Tool: rNPV 품질 점수 개선 (2026-04-11)

## 배경
rNPV P0~P3 완료. NVO 캘리브레이션 후 $35 vs 시장 $38 (-6.7% 괴리).
현재 품질 점수 **53/100 (D)** — 교차검증 수렴도 3/25가 주 원인.

문제: 현재 quality scoring은 모든 교차검증 방법의 CV(변동계수)로 수렴도를 판단.
rNPV $35, DCF $92, EV/Revenue $39, P/E $67, P/BV $40 → CV=44.8%.
그러나 DCF $92는 pharma pipeline 기업에 부적합한 방법론(EBITDA 기반 TV가 파이프라인 가치 미반영).
rNPV 전용 scoring이 필요 — 방법론 적합성을 반영해야 함.

## 태스크

### 1. rNPV 전용 quality scoring 로직
- `engine/quality.py`의 `calc_quality_score()` 분석 후, rNPV일 때 교차검증 수렴도 계산 방식 변경
- rNPV 기업에서 DCF는 참고용(교차검증 가중치 하향), EV/Revenue와 P/BV가 더 적합한 비교 대상
- 교차검증 항목별 가중치 차등 적용 또는 rNPV 전용 수렴도 공식

### 2. rNPV-specific quality dimensions 추가
- 파이프라인 다양성 (약물 수, phase 분포)
- PoS 그라운딩 (커스텀 PoS vs 디폴트 사용 비율)
- Reverse rNPV 정합성 (implied parameters가 합리적 범위 내인지)
- 시나리오 커버리지 (pos_override 사용 여부)

### 3. 콘솔/Excel 품질 리포트 업데이트
- 품질 breakdown에 rNPV 전용 항목 표시

## 참고 파일
- engine/quality.py — calc_quality_score()
- engine/rnpv.py, engine/reverse_rnpv.py
- schemas/models.py — QualityScore
- output/console_report.py (품질 출력 부분)
- profiles/nvo.yaml (테스트 프로필)

## 현재 NVO 품질 내역
- 교차검증 수렴도: 3/25 (CV=44.8%)
- WACC 적정성: 25/25
- 시나리오 정합성: 25/25
- 시장가격 정합: 0/25 (yfinance SSL 에러로 가격 미조회)

## 테스트: 449/449 pass

## 모드: normal
