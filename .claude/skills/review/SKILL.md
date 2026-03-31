# Review Skill

## Description
TRIGGER when: 사용자가 "결과 검증", "괴리율 확인", "sanity check", "결과가 이상해" 언급 시.
DO NOT TRIGGER when: 밸류에이션 실행 (→ /valuation), 프로필 생성 (→ /profile), 뉴스 분석 (→ /discover).

## Overview
밸류에이션 결과의 타당성을 검증한다. 시장가격 비교, 가정 점검, 교차검증 결과 분석.

## File References
- [references/sanity_checks.md](references/sanity_checks.md) — 항목별 검증 체크리스트와 임계값 기준

## Gotchas
- 비상장 기업은 시장가격 비교 불가 — 교차검증에 집중
- 괴리율 ±50% 초과 시 반드시 가정 재검토 제안
- WACC가 비정상적으로 높거나 낮으면 (< 5% 또는 > 20%) 경고
