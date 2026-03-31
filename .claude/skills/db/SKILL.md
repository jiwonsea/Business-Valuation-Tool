# DB Skill

## Description
TRIGGER when: user mentions "저장된 결과", "히스토리", "DB 조회", "과거 분석 찾아줘", "이전에 분석한", "삭제해줘", "DB 상태", "saved results", "history", "DB query", "previous analysis".
DO NOT TRIGGER when: new valuation execution (→ /valuation), profile creation (→ /profile), cross-company comparison (→ /compare).

## Overview
Queries and manages valuation results, AI analysis history, and YAML profiles stored in Supabase. Uses CRUD functions from `db/repository.py`.

## Available Operations
1. **Query** — Filter by company name / market / date
2. **Detail** — View full input_data/result_data for a specific valuation
3. **Delete** — Delete a specific valuation (CASCADE also deletes ai_analyses)
4. **AI analysis history** — View per-step (identify, classify, peers, wacc, scenarios) results

## File References
- [references/api_functions.md](references/api_functions.md) — repository.py function signatures and usage examples

## Gotchas
- If `SUPABASE_URL`, `SUPABASE_KEY` are not set, all functions return `None` or `[]`. Not an error. Guide user: "Set Supabase keys in `.env`".
- `get_client()` is `@lru_cache` singleton. Changing env vars mid-session won't take effect. Restart required.
- `save_valuation()` upserts on `(company_name, analysis_date)`. Re-analyzing same company on same day overwrites.
- `save_profile()` upserts on `(company_name, file_name)`. Same filename overwrites.
- `delete_valuation()` is CASCADE — `ai_analyses` records are also deleted. Execute only after user confirmation.
- `list_valuations()` `company_name` filter uses `ilike` (partial match, case-insensitive). Searching "SK" matches both "SK에코플랜트" and "SK하이닉스".
