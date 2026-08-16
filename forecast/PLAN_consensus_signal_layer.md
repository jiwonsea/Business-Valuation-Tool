# PLAN — 컨센서스 시그널 레이어 (Consensus Signal Layer)

> **이 문서는 EFE 세션이 zero-context로 이어받는 핸드오프 plan입니다.**
> career 포트폴리오 세션(2026-05-30)에서 설계·합의됨. 코드는 본 EFE repo에서만 작성합니다.

---

## 0. 한 줄 요약

EFE에 **"실적 공시·IR 텍스트를 읽어 컨센서스가 어디로 움직일지 예측하고, 콜 사전 브리핑(무엇을 주목·질문할지)을 자동 생성하는"** 정성→신호 레이어를 추가한다. 별도 repo를 만들지 않고 EFE의 fetcher·backtest·output 배관을 재사용한다.

## 1. 왜 별도 repo가 아니라 EFE 안인가 (결정 근거)

- EFE는 이미 새 기능에 필요한 배관을 전부 보유: `pipeline/dart_fetcher.py`, `pipeline/consensus_loader.py`, `engine/consensus_diff.py`, `engine/backtest.py`, `output/*`(HTML/MD/xlsx/PDF). 별도 repo면 이 전부를 중복 복제하게 된다.
- 개념적으로 EFE의 thesis를 완성한다: **내 숫자(forecast) vs 컨센서스(diff) vs 컨센서스가 어디로 갈지(NLP signal)** — 세 시야를 한 엔진에. EFE가 *earnings forecast* → *earnings intelligence* 로 일관되게 깊어진다.
- repo 수는 목적이 아님. 얇은 repo 2개보다 깊은 repo 1개가 면접 스토리·포트폴리오 정합에 유리(career 메모리: "repo 둘 다 풍성하면 포트폴리오 과잉" 학습과 정합).

## 2. 현재 EFE 상태 (선행 작업이 있다)

- EFE 코어는 **scaffold만 완료** — 엔진 함수 대부분이 `raise NotImplementedError("Codex: implement...")` 스텁. (`engine/consensus_diff.py` 등 확인됨)
- 따라서 본 plan은 2단계로 sequencing한다. **Phase A(EFE 코어 살리기)가 Phase B(신규 레이어)의 선행조건.** 신규 레이어가 `dart_fetcher`·`backtest`·`output`에 의존하기 때문.

## 3. 스코프 가드레일 (반드시 지킬 것)

- **1종목만**: SK하이닉스 `000660.KS` / corp_code `00164779`. EFE가 이미 커버 중인 종목과 일치.
- **MVP + backtest 1사이클까지**가 목표. 다종목·웹UI·DB·스케줄러는 코어가 증명되기 전까지 **금지**(BVT가 22k LOC로 비대해진 전례 회피).
- 산출물 = 콜 사전 브리핑 1건 + 신호 backtest 표 1건이면 자소서·면접 증빙으로 충분.

---

## Phase 0 — 데이터 가용성 프로빙 (가장 위험한 가정, 코딩 전 반드시)

신규 레이어 전체가 외부 텍스트 데이터에 의존하므로, **착수 전 반나절** 실제 접근성을 확인하고 결과를 `docs/data_sources.md`에 추가한다.

### 프로빙 대상
1. **DART 공시 원문 텍스트** — 사업보고서·분기보고서의 "이사의 경영진단 및 분석의견(MD&A)" 섹션, 주요사항보고서. `dart_fetcher`의 httpx/캐시 패턴 재사용. (원문 HTML/XML 텍스트 추출 가능 여부 확인 — 재무 숫자가 아니라 **서술 텍스트**가 필요)
2. **IR 실적발표 자료** — SK하이닉스 IR 사이트 분기 실적 PDF. 텍스트 레이어 추출 가능 여부(pymupdf).
3. **컨센서스 리비전 시계열** — yfinance `earnings_estimate`는 현재 스냅샷만 제공, *과거 추정치 변화*는 sparse. 네이버 금융/FnGuide 확인.

### 산출물 / Acceptance
- KR 소스별 접근 가능 여부 + SK하이닉스 확보 가능 분기 수(텍스트 샘플 N) 표로 기록.
- **backtest 타깃 변수 확정** (아래 §Phase B 백테스트 설계 참조).
- 통과 못 하면: "콜 예측"을 "공시 텍스트 기반 신호 + 주가반응 backtest"로 축소(타깃을 가격 반응으로 고정).

---

## Phase A — EFE 코어 end-to-end (선행, 기존 대기 중 Codex 작업)

`AGENTS.md` §작업 순서 1~11을 SK하이닉스로 실제 한 번 완주한다. **이건 우회가 아니라 신규 레이어의 공통 토대.**

### Acceptance
- `python cli.py --company sk_hynix --dry-run` → fixture로 리포트 생성(외부 API 없이).
- `python cli.py --company sk_hynix` → 실데이터 HTML 산출물 브라우저 점검.
- `pytest -q` 전체 green.
- 8Q backtest 실행(매출 MAPE < 10%, EPS MAPE < 25% 미달 시 가정 재검토).

최소한 `pipeline/dart_fetcher`·`pipeline/consensus_loader`·`engine/backtest`·`output/*`가 동작해야 Phase B 착수 가능.

---

## Phase B — 컨센서스 시그널 레이어 (신규)

EFE 구조 규칙(engine=순수함수, IO=pipeline/ai, 입출력 Pydantic)에 맞춰 모듈 추가. LLM 호출은 `ai/`로 분리하고 **결정론적 검증(validators)을 engine에 둔다** — BVT 패턴 차용으로 "LLM 래퍼" 비판 방어.

### 신규 모듈
```
pipeline/disclosure_loader.py   # (IO) DART 공시 서술 텍스트 + IR PDF 원문 fetch/parse
ai/                             # (신규 디렉토리, BVT ai/ 미러)
├── extractor.py                #   LLM 구조화 추출 오케스트레이션 (temperature 0 + 캐시)
├── prompts.py                  #   추출 프롬프트 (토픽·가이던스 톤·surprise 후보)
└── validators.py               #   결정론적 후처리 검증 (스키마·범위·일관성)
engine/signal_extractor.py      # (순수) 추출 결과 정규화·점수화
engine/signal_predictor.py      # (순수) ExtractedSignal + 컨센 분산 → 주목 토픽 랭킹 + 리비전 방향 예측
engine/signal_backtest.py       # (순수) event study: 신호 vs 후속 주가반응/리비전
output/call_brief_builder.py    # 콜 사전 브리핑 렌더 (HTML primary + MD), output 스택 재사용
```

### schemas/models.py 확장 (Pydantic v2)
- `DisclosureDocument` — source(dart/ir), date, raw_text, period
- `ExtractedSignal` — topics: list[TopicEmphasis], guidance_tone(enum: up/flat/down), surprise_candidates: list[str], extracted_at
- `CallBrief` — top_topics, expected_qna, dispersion_flags, predicted_revision_direction, confidence
- `SignalBacktestResult` — directional_hit_ratio, information_coefficient, sample_n, calibration

### 백테스트 설계 (면접 방어력의 핵심)
- **가설**: 공시/IR 텍스트의 토픽 강조·가이던스 톤이 후속 주가 반응(또는 컨센 리비전)을 예측한다.
- **샘플**: SK하이닉스 직전 8~12분기 공시/IR 텍스트.
- **라벨 (Phase 0에서 확정)**:
  - 1차(권장, 측정 확실): 공시/실적 발표 직후 **초과수익률 T+1d / T+5d** (시장 또는 섹터 대비).
  - 2차(데이터 확보 시): **T+30d 컨센 EPS 리비전 부호**.
- **지표**: directional hit ratio, IC(rank correlation), 예측 신뢰도 calibration.
- **look-ahead bias 회피**: 각 시점에 그 시점까지 공개된 텍스트만 입력. (`backtest.py`의 직전 4Q baseline 규칙과 동일 철학)

### cli.py 신규 모드
```
python cli.py --call-brief --company sk_hynix          # 다음 분기 콜 사전 브리핑 생성
python cli.py --signal-backtest --company sk_hynix      # 신호 backtest 표
```

---

## 4. AI 협업 정직성 (README / docs/ai_collaboration.md 갱신)

- **사람(본인)**: 가설 설계, 토픽 추출 스키마 정의, backtest 라벨·방법론 정의, 결과 해석, thesis 작성.
- **AI 협업(Codex/Claude)**: 추출 프롬프트 작성, 텍스트 파싱·코드 구현, 테스트, 보일러플레이트.
- 이 분업 자체가 자소서 "AI 활용능력" 축 증빙. 자랑성 수사 자제, 차분히 분업 설명.

## 5. 컨벤션 리마인더 (EFE 규칙)

- Pydantic v2 (`model_validate`/`model_dump`), engine 반환에 DataFrame 금지.
- engine = 순수함수(IO·전역상태·로깅 없음), LLM/HTTP는 `pipeline`/`ai`에.
- 모든 `open()`에 `encoding='utf-8'`. 가정 수치는 `profiles/*.yaml`, 코드 하드코딩 금지.
- ASCII 경로만(Codex 한글 경로 silent fail). 임시작업 `C:/temp/earnings_forecast/` 격리.
- 출력 HTML primary + MD + xlsx. Plotly 단일 HTML < 5MB(폰트 임베드 금지).
- **자동 해석 금지** — `interpretation`/`thesis` 필드는 빈 채로 두고 사용자가 작성(`consensus_diff.py` 규칙과 동일).

## 6. 리스크 / 열린 질문

- KR 콜 transcript 희소 → 공시 MD&A + IR PDF 텍스트로 대체(Phase 0에서 확정).
- 컨센 리비전 과거 시계열 확보 어려움 → 1차 라벨을 주가 반응으로 고정.
- LLM 추출 재현성 → temperature 0 + 스키마 검증(validators) + 응답 캐시.

## 7. 완료 후 동기화 (career repo)

- `career/profile.md`·`portfolio-summary.md`·`facts-verified.md`에 본 레이어 항목 추가.
- career 메모리 `project_earnings_forecast_engine.md` 갱신(스캐폴드 → 코어+시그널 레이어).
- EFE README 피치를 "earnings forecast" → "earnings intelligence(forecast + 컨센 시그널)"로 확장.

---

## 8. EFE 세션 첫 프롬프트 (복붙용)

```
F:/dev/Portfolio/earnings-forecast-engine 프로젝트. 이전 세션과 무관, 캐시 없이 처음부터 읽어라.
PLAN_consensus_signal_layer.md 를 따라 작업한다.
먼저 Phase 0(데이터 가용성 프로빙)을 수행하고 결과를 docs/data_sources.md에 기록한 뒤,
backtest 타깃 변수를 확정하고 나에게 보고하라. Phase A/B는 그 다음 단계다.
스코프 가드레일(SK하이닉스 1종목, MVP+backtest까지, 플랫폼화 금지) 엄수.
```
