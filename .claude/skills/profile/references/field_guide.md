# 업종별 필수/선택 필드 맵

## 공통 필수 (모든 프로필)
```yaml
company:
  name, legal_status, shares_total, shares_ordinary, analysis_date
segments:
  최소 1개 부문 (code → {name, multiple})
segment_data:
  base_year 포함 최소 1년
consolidated:
  base_year 포함 최소 1년 (revenue, op, net_income, assets, liabilities, equity, dep, amort)
wacc_params:
  rf, erp, bu, de, tax, kd_pre, eq_w
dcf_params:
  ebitda_growth_rates (리스트 5개), tax_rate, terminal_growth
base_year: int
```

## 업종별 추가 필드

### 다부문 기업 (SOTP)
- `segments`: 2개 이상 부문, 각각 `multiple` 설정
- `segment_data`: 부문별 revenue, op, assets 필수
- `peers`: 부문별 최소 2~3개 Peer (segment_code 매칭)
- `multiples`: segment_code → EV/EBITDA (segments의 multiple과 동일하게 설정)

### 금융업종 (DDM/RIM)
```yaml
wacc_params:
  is_financial: true   # Hamada 스킵
  eq_w: 100.0          # Ke = WACC
  bu: 0.65             # Equity Beta (시장 관찰값)
```
- DDM: `ddm_params.dps`, `ddm_params.dividend_growth` 필수
- RIM: `rim_params.roe_forecasts` (리스트), `rim_params.terminal_growth`, `rim_params.payout_ratio`
- 교차검증: `pbv_multiple`, `pe_multiple` 권장
- `valuation_method: "ddm"` 또는 `"rim"` 명시 가능 (없으면 ROE-Ke 스프레드로 자동 판단)

### 성장/테크 (DCF Primary)
- `dcf_params`: 성장률 초기 높게 → 점진 하락 패턴
- `ev_revenue_multiple`: 적자 기업 교차검증 필수
- `ps_multiple`: P/S 교차검증 (Optional)

### 지주사/리츠 (NAV)
- `nav_params.revaluation`: 투자자산 재평가 조정액
- 리츠: `pffo_multiple`, `ffo` 추가 (P/FFO 교차검증)

### 비상장 기업 (시나리오 중심)
- `scenarios`: Base/Bull/Bear 최소 3개
- `cps_principal`, `cps_years`: CPS/RCPS 있으면 필수
- `net_debt`, `eco_frontier`: 순차입금, 에코프론티어 등 조정항목
- 각 시나리오의 `dlom`: 비상장 할인율 (상장=0, 비상장=15~30% 통상)

## 템플릿 참조
기본 템플릿: `profiles/_template.yaml`
금융업종 샘플: `profiles/kb_financial.yaml`
다부문 비상장 샘플: `profiles/sk_ecoplant.yaml`
