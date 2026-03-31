# Valuation Skill

## Description
TRIGGER when: 사용자가 "밸류에이션 실행", "기업 분석", "기업가치 평가", "--profile", "--company" 언급 시.
DO NOT TRIGGER when: 뉴스 분석, 코드 리뷰, 테스트 관련 요청 시.

## Overview
YAML 프로필 또는 기업명 입력으로 밸류에이션을 수행한다. 방법론은 기업 특성에 따라 자동 선택되며, 사용자가 오버라이드 가능.

## Method Selection
- 다부문 기업 → SOTP (EV/EBITDA) + DCF 교차검증
- 단일부문 기업 → DCF primary + 멀티플 교차검증
- 금융회사 → P/BV 또는 DDM
- 성장/테크 → DCF + EV/Revenue

상세: [references/method_guide.md](references/method_guide.md)

## Unit Rules
금액 단위는 재무제표 규모에 따라 자동 결정. `engine/units.py`의 `detect_unit()` 사용.

상세: [references/unit_rules.md](references/unit_rules.md)

## Gotchas
- `* 1_000_000` 하드코딩 절대 금지 → `per_share()` 사용
- engine/ 함수는 순수 함수 (IO 금지)
- 시나리오/확률은 AI가 제안하되 최종 결정은 사용자
