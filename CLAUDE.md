# CLAUDE.md — korean-valuation-tool

## Project Overview

한국/미국 기업 밸류에이션 플랫폼. YAML 프로필 기반 또는 기업명 입력 자동 수집 모드로, SOTP + DCF 교차검증 + 시나리오 분석을 수행한다.

## Architecture

```
schemas/models.py    — Pydantic 데이터 모델 (입출력 계약)
engine/              — 순수 계산 함수 (IO 없음, 상태 없음, 통화 무관)
  wacc.py            — WACC (CAPM)
  sotp.py            — D&A 배분 + SOTP EV
  dcf.py             — FCFF 기반 DCF
  scenario.py        — 시나리오별 Equity → 주당가치
  sensitivity.py     — 3종 2-way 민감도
pipeline/            — 데이터 수집 (KR: DART, US: SEC EDGAR)
  data_fetcher.py    — 자동 판별 통합 인터페이스 (핵심)
  dart_client.py     — DART OpenAPI (한국)
  edgar_client.py    — SEC EDGAR XBRL API (미국, API Key 불필요)
  edgar_parser.py    — XBRL → 연결 재무제표 dict
  yahoo_finance.py   — 주가/시가총액 (미국)
  market_data.py     — 38.co.kr/KRX (한국)
ai/                  — LLM 분석 보조 (Claude API)
output/              — Excel 7시트 빌더
profiles/            — YAML 기업 프로필
cli.py               — CLI 진입점 (--profile / --company 두 모드)
app.py               — Streamlit 웹 UI
```

## Commands

```bash
# 프로필 기반 밸류에이션 (검증: 39,892원)
python cli.py --profile profiles/sk_ecoplant.yaml
python cli.py --profile profiles/sk_ecoplant.yaml --excel

# 기업명/ticker 자동 수집 (KR/US 자동 판별)
python cli.py --company "AAPL"           # → 미국 Apple (SEC EDGAR)
python cli.py --company "삼성E&A"         # → 한국 (DART, API Key 필요)
python cli.py --company "MSFT"           # → 미국 Microsoft

# Streamlit UI
streamlit run app.py

# 의존성 설치
pip install pydantic pyyaml pandas numpy openpyxl httpx
pip install anthropic              # AI 기능용
pip install streamlit plotly       # UI용
pip install beautifulsoup4         # 한국 시장 데이터 스크래핑용
```

## Auto-Detection Logic

`--company` 모드의 KR/US 판별:
1. 한글 포함 → DART 검색 (한국)
2. 영문 대문자 1~5자 → SEC ticker 검색 (미국) 우선
3. 영문 일반 → SEC 검색 우선, 실패 시 DART fallback

## Key Design Decisions

- **engine/ 함수는 순수 함수**: IO 없음, 통화/국가 무관. KRW든 USD든 같은 엔진으로 계산.
- **Pydantic 모델**: 타입 안전성 + market/currency 필드로 KR/US 구분.
- **YAML 프로필**: 기업별 데이터를 코드에서 분리. 새 기업 분석 = 새 YAML 파일 작성.
- **SEC EDGAR API는 무료**: API Key 불필요, User-Agent 헤더만 필요. DART는 API Key 필요.
- **원본 검증**: SK에코플랜트 프로필 결과는 반드시 39,892원과 일치해야 함.

## Conventions

- 금액 단위: KR=백만원, US=$M (USD millions)
- YAML 프로필: profiles/ 디렉토리
- `.env` 파일은 절대 git에 커밋하지 않음
