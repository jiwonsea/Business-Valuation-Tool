# Compare Skill

## Description
TRIGGER when: 사용자가 "비교해줘", "A vs B", "peer 대비 어떤지", "업종 평균 대비", "이전 분석과 비교", "멀티플 비교표" 등 기업간 또는 시점간 비교를 요청할 때.
DO NOT TRIGGER when: 단일 기업 밸류에이션 실행 (→ /valuation), 프로필 생성 (→ /profile).

## Overview
여러 기업 또는 동일 기업의 시점별 밸류에이션 결과를 비교한다. YAML 프로필, DB 저장 결과, 또는 현재 세션 결과를 비교 소스로 사용.

## Comparison Types
1. **횡단면 비교** — 동일 시점, 다른 기업 (Peer 비교)
2. **시계열 비교** — 동일 기업, 다른 시점 (가정 변화 추적)
3. **방법론 비교** — 동일 기업, 다른 방법론 결과 (교차검증 심화)

## Workflow
1. 비교 대상 확인 (프로필 파일 / DB 조회 / 현재 세션)
2. 비교 유형 결정 (횡단면 / 시계열 / 방법론)
3. 핵심 지표 추출 → 비교 테이블 생성
4. 차이 원인 분석 + 인사이트 제시

## File References
- [references/comparison_metrics.md](references/comparison_metrics.md) — 비교 가능한 지표 목록과 해석 가이드

## Gotchas
- 단위가 다른 기업 비교 시 반드시 단위 통일 후 비교. `currency_unit`이 "백만원" vs "억원"이면 절대값 비교 불가.
- DB 조회 시 `SUPABASE_URL`/`SUPABASE_KEY` 미설정이면 graceful skip. 에러 내지 말고 "DB 미연결" 안내.
- Peer 멀티플 비교 시 `peer_stats`의 `applied_multiple`과 `ev_ebitda_median`을 구분. applied는 실제 적용된 값, median은 통계값.
- 시계열 비교에서 `analysis_date`가 다르면 매크로 환경(금리, ERP)도 달라질 수 있음. WACC 변동 원인을 단순히 기업 요인으로 귀속하지 말 것.
