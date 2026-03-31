# Profile Skill

## Description
TRIGGER when: 사용자가 "프로필 만들어", "YAML 생성", "가정값 수정", "시나리오 추가/변경", "템플릿", 새 기업 분석을 위한 프로필 작성을 요청할 때.
DO NOT TRIGGER when: 이미 완성된 프로필로 밸류에이션 실행 요청 시 (→ /valuation), 뉴스 기반 기업 추천 시 (→ /discover).

## Overview
YAML 프로필을 생성하거나 수정한다. 프로필은 `ValuationInput` 스키마의 YAML 표현이며, 밸류에이션 실행의 유일한 입력이다.

## Workflow
1. 사용자에게 기업명, 업종, 상장/비상장 확인
2. 업종 → `method_selector.py` 기준으로 방법론 판단 → 필요한 필드 결정
3. 재무 데이터 수집 (사용자 제공 or DART/SEC 자동)
4. YAML 초안 생성 → 사용자 확인 → 저장

## File References
이 폴더에 상세 가이드가 있다. 필요할 때만 읽을 것:
- [references/field_guide.md](references/field_guide.md) — 업종별 필수/선택 필드 맵
- [references/scenario_patterns.md](references/scenario_patterns.md) — 시나리오 설계 패턴과 확률 배분 규칙

## Gotchas
- 새 필드는 반드시 `Optional + 기본값`. 기존 프로필이 깨지지 않아야 한다.
- `shares` 필드: 시나리오별로 적용 주식수가 다를 수 있다 (CPS 전환 여부에 따라). `scenarios.*.shares`를 반드시 명시적으로 설정.
- 시나리오 확률 합계는 정확히 100%. `ValuationInput.validate_inputs()`가 0.1%p 허용 오차로 검증.
- 금융업종 프로필: `wacc_params.is_financial: true`, `eq_w: 100.0` (Ke=WACC). `bu`는 Equity Beta 직접 입력 (Hamada 미적용).
- `segment_data`의 연도 키와 `consolidated`의 연도 키는 반드시 `base_year`를 포함해야 한다. 누락 시 런타임 에러.
- `net_debt`는 표시 단위 기준 (백만원 프로필이면 백만원 단위). `* 1_000_000` 하드코딩 절대 금지.
- `peers` 리스트에서 `segment_code`는 `segments` 딕셔너리의 키와 정확히 일치해야 한다.
