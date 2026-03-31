# Valuation Skill

## Description
TRIGGER when: 사용자가 "밸류에이션 실행", "기업 분석", "기업가치 평가", "--profile", "--company" 언급 시.
DO NOT TRIGGER when: 프로필 생성 (→ /profile), 뉴스 분석 (→ /discover), 결과 검증 (→ /review), 보고서 출력 (→ /report).

## Overview
YAML 프로필 또는 기업명 입력으로 밸류에이션을 수행한다. 방법론은 기업 특성에 따라 자동 선택되며, 사용자가 오버라이드 가능.

## File References
이 폴더에 상세 가이드가 있다. 필요할 때만 읽을 것:
- [references/method_guide.md](references/method_guide.md) — 업종별 방법론 선택 기준 + SOTP/DCF/DDM/RIM/NAV 요약
- [references/unit_rules.md](references/unit_rules.md) — 금액 단위 자동 판단 로직 + 주당가치 변환 규칙

## Gotchas
- `* 1_000_000` 하드코딩 절대 금지 → `per_share()` 사용
- engine/ 함수는 순수 함수 (IO 금지)
- 시나리오/확률은 AI가 제안하되 최종 결정은 사용자
