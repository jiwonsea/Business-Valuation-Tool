# CLAUDE.md

## Project

한국/미국 기업 밸류에이션 플랫폼. 순수 함수 엔진 + Pydantic 스키마 + YAML 프로필 + AI 보조 분석. Python 3.11+.

## Architecture

```
ValuationInput (YAML) → run_valuation() → ValuationResult → print_report() / Excel
```

- `engine/` — 순수 함수 (IO 없음). `method_selector.py`가 기업 유형별 방법론 자동 분기.
- `schemas/models.py` — Pydantic 모델. 핵심 계약: `ValuationInput` → `ValuationResult`.
- `pipeline/` — 데이터 수집 (DART, SEC EDGAR, Yahoo Finance). IO는 여기서만.
- `ai/` — LLM 기반 부문 분류, Peer 추천, 시나리오 설계 (Claude Sonnet 4).
- `db/` — Supabase 연동. `client.py`(싱글턴), `repository.py`(CRUD), `migrations.sql`(DDL).
- `output/` — Excel 7시트 (가정, D&A, SOTP, 시나리오, DCF, 민감도, 교차검증).
- `scheduler/` — 주간 자동 뉴스 수집 + 밸류에이션. `weekly_run.py`(파이프라인), `scoring.py`(중요도).
- `cli.py` — CLI 진입점 + `run_valuation()` (SOTP/DCF 분기 실행).
- `orchestrator.py` — 프로필→밸류에이션→Excel 파이프라인 래퍼.
- `app.py` — Streamlit 웹 UI.

## Commands

```bash
python cli.py --profile profiles/sk_ecoplant.yaml        # 프로필 기반
python cli.py --profile profiles/sk_ecoplant.yaml --excel # Excel 출력
python cli.py --company "AAPL"                            # 자동 수집 (US)
python cli.py --company "삼성E&A"                          # 자동 수집 (KR, DART_API_KEY 필요)
python cli.py --company "MSFT" --auto                     # AI 분석 포함
python cli.py --discover --market KR                      # 뉴스 기반 기업 추천
python cli.py --weekly                                    # 주간 자동 분석 (KR+US, 3개)
python cli.py --weekly --markets KR --max-companies 5     # 시장/기업수 지정
python cli.py --weekly --dry-run                          # 발굴만, 밸류에이션 미실행
python -m scheduler.weekly_run                            # 모듈 직접 실행

streamlit run app.py                                      # 웹 UI
pytest tests/                                             # 테스트
pip install -e ".[dev,pipeline,ai,ui,db]"                  # 의존성 설치
```

## Workflow Rules

1. **생각과 실행 분리**: 비자명한 작업은 구조/방식을 먼저 제안하고, 확인 후 실행.
2. **방법론 자동 선택**: `engine/method_selector.py`가 부문 수, 업종, ROE/Ke에 따라 SOTP/DCF/DDM/RIM/NAV 분기. 금융주는 ROE-Ke 스프레드로 DDM/RIM 자동 판단. 수동 지정(`valuation_method`) 우선.
3. **괴리율 확인**: 상장사 밸류에이션 후 시장가 비교. ±50% 초과 시 데이터/가정 재확인.
4. **시나리오/확률**: AI가 제안하되, 최종 결정은 사용자.
5. **금액 단위**: 재무제표 규모 기반 자동 판단 (`engine/units.py`), 하드코딩 금지.

## Conventions

- `.env` 파일은 절대 git에 커밋하지 않음 (PreCommit 훅으로 차단).
- 환경변수: `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `DART_API_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `SUPABASE_URL`, `SUPABASE_KEY`
- `engine/` 함수는 순수 함수 (IO 없음, 상태 없음). `import httpx`, `requests` 등 금지.
- 입출력 계약: `ValuationInput` → `ValuationResult` (`schemas/models.py`).
- YAML 프로필 새 필드는 반드시 Optional + 기본값 (하위 호환).

## Testing

```bash
pytest tests/                    # 전체
pytest tests/test_engine.py -k "test_sk_wacc"  # 개별
```

- engine 순수 함수 테스트: 고정 입력 → 정확값 검증 OK.
- 파이프라인 E2E 테스트: 범위 기반 검증. 기업 유형별 방법론이 달라질 수 있으므로 정확값 regression 지양.

## Gotchas

- `* 1_000_000` 하드코딩 금지 → `engine.units.per_share()` 사용.
- 민감도 분석에 세그먼트 코드("HI", "ALC" 등) 하드코딩 금지.
- YAML 프로필의 새 필드는 반드시 Optional + 기본값 설정 (하위 호환).
