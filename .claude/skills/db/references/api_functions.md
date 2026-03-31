# DB Repository Function Signatures

## Connection Check
```python
from db.client import is_configured
if not is_configured():
    print("Supabase not connected — set SUPABASE_URL, SUPABASE_KEY in .env")
```

## Valuations

### Save (upsert)
```python
from db.repository import save_valuation
val_id: str | None = save_valuation(vi: ValuationInput, result: ValuationResult)
# upsert key: (company_name, analysis_date)
```

### List Query
```python
from db.repository import list_valuations
rows: list[dict] = list_valuations(
    company_name="SK",       # ilike partial match (Optional)
    market="KR",             # exact match (Optional)
    limit=20,                # default 20
)
# Returns columns: id, company_name, ticker, market, valuation_method,
#                  analysis_date, total_ev, weighted_value, wacc_pct,
#                  market_price, gap_ratio, created_at
```

### Detail Query
```python
from db.repository import get_valuation
row: dict | None = get_valuation(valuation_id="uuid-string")
# Includes input_data (JSONB), result_data (JSONB)
```

### Delete
```python
from db.repository import delete_valuation
ok: bool = delete_valuation(valuation_id="uuid-string")
# CASCADE: also deletes ai_analyses
```

## AI Analyses

### Save
```python
from db.repository import save_ai_analysis
aid: str | None = save_ai_analysis(
    company_name="KB Financial Group",
    step="classify",          # identify | classify | peers | wacc | scenarios | research_note
    result_data={"sector": "banking", ...},
    model="claude-sonnet-4",
    valuation_id="uuid",      # Optional
)
```

### List Query
```python
from db.repository import list_ai_analyses
rows: list[dict] = list_ai_analyses(
    company_name="KB",        # ilike (Optional)
    valuation_id="uuid",      # exact match (Optional)
    limit=50,
)
```

## Profiles

### Save (upsert)
```python
from db.repository import save_profile
pid: str | None = save_profile(
    company_name="SK Ecoplant",
    profile_yaml=yaml_text,   # raw YAML text
    profile_data=vi.model_dump(mode="json"),  # parsed dict
    file_name="sk_ecoplant.yaml",  # part of upsert key
)
```

### List Query
```python
from db.repository import list_profiles
rows: list[dict] = list_profiles(company_name="SK", limit=20)
# Returns: id, company_name, file_name, created_at, updated_at
```

### Detail Query
```python
from db.repository import get_profile
row: dict | None = get_profile(profile_id="uuid-string")
# Includes profile_yaml (TEXT), profile_data (JSONB)
```
