# DB Repository 함수 시그니처

## 연결 확인
```python
from db.client import is_configured
if not is_configured():
    print("Supabase 미연결 — .env에 SUPABASE_URL, SUPABASE_KEY 설정 필요")
```

## Valuations

### 저장 (upsert)
```python
from db.repository import save_valuation
val_id: str | None = save_valuation(vi: ValuationInput, result: ValuationResult)
# upsert 키: (company_name, analysis_date)
```

### 목록 조회
```python
from db.repository import list_valuations
rows: list[dict] = list_valuations(
    company_name="SK",       # ilike 부분 일치 (Optional)
    market="KR",             # 정확 일치 (Optional)
    limit=20,                # 기본 20
)
# 반환 컬럼: id, company_name, ticker, market, valuation_method,
#            analysis_date, total_ev, weighted_value, wacc_pct,
#            market_price, gap_ratio, created_at
```

### 상세 조회
```python
from db.repository import get_valuation
row: dict | None = get_valuation(valuation_id="uuid-string")
# input_data (JSONB), result_data (JSONB) 포함
```

### 삭제
```python
from db.repository import delete_valuation
ok: bool = delete_valuation(valuation_id="uuid-string")
# CASCADE: ai_analyses도 함께 삭제
```

## AI Analyses

### 저장
```python
from db.repository import save_ai_analysis
aid: str | None = save_ai_analysis(
    company_name="KB금융지주",
    step="classify",          # identify | classify | peers | wacc | scenarios | research_note
    result_data={"sector": "은행", ...},
    model="claude-sonnet-4",
    valuation_id="uuid",      # Optional
)
```

### 목록 조회
```python
from db.repository import list_ai_analyses
rows: list[dict] = list_ai_analyses(
    company_name="KB",        # ilike (Optional)
    valuation_id="uuid",      # 정확 일치 (Optional)
    limit=50,
)
```

## Profiles

### 저장 (upsert)
```python
from db.repository import save_profile
pid: str | None = save_profile(
    company_name="SK에코플랜트",
    profile_yaml=yaml_text,   # YAML 원문
    profile_data=vi.model_dump(mode="json"),  # 파싱된 dict
    file_name="sk_ecoplant.yaml",  # upsert 키의 일부
)
```

### 목록 조회
```python
from db.repository import list_profiles
rows: list[dict] = list_profiles(company_name="SK", limit=20)
# 반환: id, company_name, file_name, created_at, updated_at
```

### 상세 조회
```python
from db.repository import get_profile
row: dict | None = get_profile(profile_id="uuid-string")
# profile_yaml (TEXT), profile_data (JSONB) 포함
```
