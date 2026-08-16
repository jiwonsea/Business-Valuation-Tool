# AGENTS.md — Codex CLI 작업 가이드

본 문서는 Codex CLI가 본 repo에서 작업할 때 참고할 함수 시그니처·테스트 케이스·코딩 컨벤션을 정리합니다. Claude Code가 scaffold를 만들었고, Codex가 함수 본문을 채웁니다.

## 작업 환경
- 경로: `F:/dev/Portfolio/earnings-forecast-engine` (ASCII)
- Python 3.11+, Pydantic v2
- 한글 홈 경로(`C:\Users\김지원`)에서 Codex 호출 금지
- 임시 파일: `C:/temp/earnings_forecast/`

## 작업 순서 (권장)

1. **schemas/models.py** — 이미 완성. 변경 시 모든 의존 모듈 영향 검토.
2. **engine/segment_revenue.py** — DRAM/NAND/HBM 분해. 가장 핵심.
3. **engine/margin_model.py** + **engine/opex_model.py** — 마진 사이클.
4. **engine/tax_finance.py** + **engine/eps_bridge.py** — NI → EPS.
5. **engine/scenario.py** — 3-case 트리·확률 가중.
6. **pipeline/yahoo_fetcher.py** — yfinance 래퍼.
7. **pipeline/dart_fetcher.py** — DART httpx 호출.
8. **pipeline/ir_loader.py** — YAML → Pydantic.
9. **engine/consensus_diff.py** + **engine/backtest.py** — 검증 엔진.
10. **output/*.py** + **templates/** — 리포트 빌더.
11. **cli.py** — 진입점 결선.

## 함수 시그니처 핵심

각 엔진 모듈은 다음 규칙을 따릅니다:

- **입력·출력 모두 Pydantic 모델** — `pd.DataFrame` 반환 금지.
- **순수 함수** — 외부 IO·전역 상태·로깅 없음. 로깅은 호출부에서.
- **타입 힌트 필수** — `def f(x: Foo) -> Bar:` 형식.
- **docstring**: 한 줄 요약 + Args + Returns + Raises (필요 시).

### engine/segment_revenue.py
```python
def project_quarterly_revenue(
    prior_actual: QuarterlyActual,
    assumptions: SegmentAssumptions,
    n_quarters: int,
) -> list[QuarterlyForecast]:
    """이전 분기 실적에 세그먼트별 bit growth·ASP 가정을 적용해 N분기 forward 매출을 산출.

    DRAM (HBM + DDR blended) + NAND + Other 합산.
    """
```

### engine/margin_model.py
```python
def project_margins(
    revenue_forecast: list[QuarterlyForecast],
    prior_4q_avg_margins: MarginBaseline,
    assumptions: MarginAssumptions,
) -> list[QuarterlyForecast]:
    """ASP 사이클 함수 기반 GP/OP margin 산출. R&D는 capex와 5Y-lag 연동."""
```

### engine/eps_bridge.py
```python
def project_eps(
    op_forecast: list[QuarterlyForecast],
    finance_assumptions: FinanceAssumptions,
    share_count: SharesOutstanding,
) -> list[QuarterlyForecast]:
    """OP → NP → EPS. 유효세율·이자손익·발행주식수 반영."""
```

### engine/scenario.py
```python
def build_scenario_tree(
    bear_forecast: list[QuarterlyForecast],
    base_forecast: list[QuarterlyForecast],
    bull_forecast: list[QuarterlyForecast],
    probabilities: ScenarioProbabilities,
) -> ScenarioTree:
    """3-case 확률 가중. probabilities 합 = 1.0 검증 (오차 1e-6)."""
```

### engine/consensus_diff.py
```python
def compute_consensus_gap(
    model_forecast: ScenarioTree,
    consensus: ConsensusRecord,
) -> list[ConsensusGap]:
    """분기·연간 단위로 모델 (base case) vs Yahoo 컨센 gap %·방향 산출.

    `interpretation` 필드는 빈 문자열로 두고, 사용자가 후술 (자동 생성 금지).
    """
```

### engine/backtest.py
```python
def run_backtest(
    historical_actuals: list[QuarterlyActual],
    methodology_assumptions: SegmentAssumptions,
    lookback_quarters: int = 8,
) -> BacktestResult:
    """과거 N분기에 본 방법론을 retroactive 적용 → MAPE·hit_ratio·bias 계산.

    각 분기 시점의 직전 4Q 평균을 baseline으로 사용 (look-ahead bias 회피).
    """
```

### pipeline/yahoo_fetcher.py
```python
def fetch_consensus(ticker: str) -> dict:
    """yfinance Ticker(ticker)에서 earnings_estimate·revenue_estimate·earnings_history 수집.

    캐시: reports/.cache/yahoo_{ticker}_{YYYYMMDD}.json
    빈 값은 dict에 명시적 None.
    """

def fetch_history(ticker: str, period: str = "3y") -> dict:
    """직전 N년 분기 EPS 실제·컨센·surprise 시계열."""
```

### pipeline/dart_fetcher.py
```python
def fetch_quarterly_financials(
    corp_code: str,
    year: int,
    reprt_code: str,  # "11013"=Q1, "11012"=H1, "11014"=Q3, "11011"=Annual
) -> dict:
    """DART fnlttSinglAcntAll.json 호출. httpx retry/backoff 적용 (rate limit 분당 1000회).

    캐시: reports/.cache/dart_{corp_code}_{year}_{reprt_code}.json
    """
```

## 코딩 컨벤션

- **로깅**: `logging` 표준 라이브러리, `logger = logging.getLogger(__name__)`. `print` 금지.
- **에러**: 외부 API 실패는 raise — 호출부에서 처리. 엔진은 입력 검증만, 비즈니스 에러는 명시적 `ValueError`.
- **테스트**: 각 엔진 모듈마다 `tests/test_*.py`. fixture는 `tests/fixtures/` JSON.
- **임포트 순서**: 표준 라이브러리 → 서드파티 → 로컬 (`from schemas.models import ...`).
- **파일 인코딩**: 모든 `open()` 호출에 `encoding='utf-8'` 명시.
- **Pydantic v2**: `model_validate`, `model_dump` 사용. `dict()`/`parse_obj()` 금지 (v1 deprecated).

## 테스트 가이드

```bash
pytest -q                                  # 전체
pytest tests/test_segment_revenue.py -v    # 단일 모듈
pytest -k "scenario"                       # 키워드 매칭
```

각 테스트는:
1. fixture 로드
2. 함수 호출
3. 출력 타입·형태 검증
4. 수치 sanity check (예: 매출 > 0, 마진 -100% ~ 100% 범위)

## Codex REPL 시 주의

- 다른 회사 자소서 세션과 동시 진행 시 새 REPL 띄울 것 — 캐시 컨텍스트가 다른 프로젝트로 오염될 수 있음
- 핸드오프 첫 줄에 "F:/dev/Portfolio/earnings-forecast-engine 프로젝트, 이전 세션과 무관" 명시
- 결과 파일은 `C:/temp/earnings_forecast/`에 격리 저장 후 본 repo로 이동

## Plan Reference
원안: `C:\Users\김지원\.claude\plans\glittery-juggling-candle.md`

## Imported Claude Cowork project instructions
