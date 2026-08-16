# PROMPT — Forward window 롤링 (2026Q2+) + 가정 리프레시 세션

> 새 Cowork/Claude 세션에 이 파일 내용을 그대로 붙여넣거나 "PROMPT_assumptions_refresh.md 실행"으로 시작.
> 작성: 2026-07-03 세션 (opex fix + 2026Q1 윈도 연장 + seed-implied shares 완료 직후).

---

## 컨텍스트 (3줄)

earnings-forecast-engine의 `forecast_window`가 아직 2026Q1 시작인데 2026Q1은 이미 실적 발표됨(매출 52.6조 +60% QoQ, GP 79.3%, EPS 57,175 — DART 캐시 존재). forward 윈도를 2026Q2 시작으로 롤링하고 4분기 가정 벡터(bear/base/bull)를 리서치 기반으로 재작성해야 함. 현재 9Q backtest 기준선: rev MAPE 8.99% · EPS MAPE 10.39% · bias −3.58% · MASE/Theil EPS 0.28 · 컨센 skill +0.54, surprise 4/4 (N=4) — **이 백테스트 수치는 이번 세션에서 절대 변하면 안 됨** (forward 윈도만 변경).

## 할 일

1. **리서치 (WebSearch, 출처 명시):** 2026Q2~2027Q1 분기별 — TrendForce DRAM/NAND contract price 전망, HBM4 램프·가격, SK하이닉스 2026Q1 실적발표 가이던스(bit growth, capex), 슈퍼사이클 지속/조정 시나리오. 참고: 1Q26 실측은 conventional DRAM +93~98%, NAND +55~60% (supply shortage), SK blended DRAM ASP +mid-60%, DRAM bits flat, HBM share ~45%로 희석.
2. **profile 갱신 (`profiles/sk_hynix.yaml`):**
   - `forecast_window.start_quarter: "2026Q2"` (seed = 2026Q1 실적, DART 캐시 OK).
   - `assumptions.{bear,base,bull}`의 dram/nand/other 4-원소 배열을 2026Q2~2027Q1 벡터로 교체 — 출처 주석 필수, DRAFT 표기 (사용자 확정 대상; 직전 세션들은 위임 확정이었음 — 위임 여부는 사용자에게 확인).
   - `historical_drivers`는 백테스트용이므로 유지. 단 forward margin carryover(`build_margin_carryover`)가 2026Q1 seed까지의 드라이버를 소비하는지 `cli.py` 배선 확인.
   - 시나리오 rationale 문자열도 슈퍼사이클 국면에 맞게 갱신 (bear = 조정 시나리오가 실질적 리스크).
   - overlays 재검토: 2026Q2 overlay는 기간 종료 → 2026Q3/Q4/2027Q1 대상 신규 overlay 초안 (as_of = 세션 날짜, lookahead 가드 주의).
3. **검증:** `DART_API_KEY=x python -m pytest -q` (98+ passed 유지) · `python cli.py --company sk_hynix --dry-run --skip-pdf` · 오프라인 9Q backtest 재현이 기준선과 bit-identical인지 확인 (백테스트 경로 불변 증명). anchor GP 테스트(`test_anchor_quarter_reproduces_actual_gross_margin`) green 유지.
4. **문서:** README(forward 윈도 표기), CLAUDE.md Open Problems 항목 해소 반영.

## 주의 (이 세션들에서 실측된 함정)

- **Cowork mount staleness:** file-tool로 기존 파일 edit 후 bash가 truncated 버전을 읽는 현상 빈발. 해결 = 전체 내용을 **새 경로**에 Write → `cp`로 canonical 덮어쓰기 → `__pycache__` 삭제. 기존 파일을 bash python으로 직접 패치하는 것도 안전 (bash 읽기·쓰기는 일관).
- 오프라인 yahoo 캐시는 오늘 날짜 키: `cp reports/.cache/yahoo_000660_KS_20260624.json reports/.cache/yahoo_000660_KS_$(date +%Y%m%d).json`.
- DART 2026 미래 분기 프로브는 sandbox에서 네트워크 차단 → 진단/테스트는 `fetch_quarterly_actuals_series(..., skip_unavailable=True)` 경로 사용 (이미 배선됨). cli 라이브는 호스트에서.
- `pip install -r requirements.txt --break-system-packages` (scipy 포함됨).
- 백테스트 EPS 브리지는 seed-implied 주식수 사용 (`engine/backtest.py::implied_basic_shares`); profile `share_count`(705,656,476)는 forward 전용.

## 호스트 전용 후속 (Cowork 밖, 별도)

1. **라이브 실행 + README 데모 갱신:** `python cli.py --company sk_hynix` → 새 리포트 확인 → README Sample Output 링크를 새 날짜 파일로 교체(.gitignore 예외도 함께), "opex 수정 이전 실행분" 경고 제거.
2. **BVT elasticity:** BVT DCF 음수 공정가치 교정 → EBITDA/FCFF ±x% 민감도로 (%FV)/(%EPS) 실측 → `valuation.fair_value_elasticity` 확정 (현 1.2 DRAFT).
3. **KR broker 컨센 (README P1):** 네이버 금융/FnGuide — sandbox 차단이라 호스트에서. vintage 누적 설계 포함 (스냅샷 날짜 키 캐시 패턴 재사용).
4. **커밋 (git add -p, 묶음 제안):**
   - opex 모델: `schemas/models.py` `engine/margin_model.py` `engine/opex_model.py` `tests/test_margin_model.py` `scripts/diagnose_opex.py` `PLAN_opex_model.md`
   - 2026Q1 연장 + shares: `engine/backtest.py` `pipeline/dart_fetcher.py` `scripts/diagnose_divergence.py` `tests/test_backtest.py` `profiles/sk_hynix.yaml`
   - 위생: `.gitattributes` `.gitignore` `pipeline/_ssl_setup.py` `requirements.txt`
   - 문서: `README.md` `CLAUDE.md` `PROMPT_assumptions_refresh.md` + 이전 세션 HANDOFF/PLAN 잔여물
   - `.gitattributes` 첫 커밋 시 일회성 LF renormalization diff 예상.
