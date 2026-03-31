# DB Skill

## Description
TRIGGER when: 사용자가 "저장된 결과", "히스토리", "DB 조회", "과거 분석 찾아줘", "이전에 분석한", "삭제해줘", "DB 상태" 등 Supabase에 저장된 밸류에이션/프로필/AI분석 데이터를 조회하거나 관리하려 할 때.
DO NOT TRIGGER when: 새 밸류에이션 실행 (→ /valuation), 프로필 생성 (→ /profile), 기업간 비교 분석 (→ /compare).

## Overview
Supabase에 저장된 밸류에이션 결과, AI 분석 이력, YAML 프로필을 조회/관리한다. `db/repository.py`의 CRUD 함수를 사용.

## Available Operations
1. **조회** — 기업명/시장/날짜별 필터링
2. **상세** — 특정 밸류에이션의 input_data/result_data 전체 확인
3. **삭제** — 특정 밸류에이션 삭제 (CASCADE로 ai_analyses도 삭제)
4. **AI 분석 이력** — 단계별(identify, classify, peers, wacc, scenarios) 결과 확인

## File References
- [references/api_functions.md](references/api_functions.md) — repository.py 함수 시그니처와 사용 예시

## Gotchas
- `SUPABASE_URL`, `SUPABASE_KEY` 미설정 시 모든 함수가 `None` 또는 `[]` 반환. 에러 아님. 사용자에게 "`.env`에 Supabase 키를 설정하세요" 안내.
- `get_client()`는 `@lru_cache` 싱글턴. 환경변수를 세션 중간에 바꿔도 반영 안 됨. 재시작 필요.
- `save_valuation()`은 `(company_name, analysis_date)` 기준 upsert. 같은 날 같은 기업 재분석 시 덮어쓴다.
- `save_profile()`은 `(company_name, file_name)` 기준 upsert. 파일명이 같으면 덮어쓴다.
- `delete_valuation()`은 CASCADE — `ai_analyses` 레코드도 함께 삭제됨. 사용자 확인 후 실행.
- `list_valuations()`의 `company_name` 필터는 `ilike` (부분 일치, 대소문자 무시). "SK"로 검색하면 "SK에코플랜트", "SK하이닉스" 모두 매칭.
