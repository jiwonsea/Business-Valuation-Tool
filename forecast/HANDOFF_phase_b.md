# HANDOFF — Phase B 컨센서스 시그널 레이어 (Codex 구현)

> **STATUS: DORMANT (2026-07-31).** 코드는 온전하나 **활성 프로파일 0개** — `signal_layer` 섹션을 가진 프로파일이 `4ebeb7c`(2026-07-10) 이후 없어 `--signal-backtest`/`--call-brief`는 진입 즉시 `return 2`. 삭제가 의도적 은퇴였는지 롤포워드 중 부수 유실이었는지는 미판정. 재활성화는 프로파일 복원 + 실제 deck/DART fixture + 추출 완전성 계약을 **한 작업**으로 묶어 진행한다. 근거: `HANDOFF_CODEX_doc_ingest_2026-07-31.md`.

> **이전 세션과 무관, 캐시 없이 읽어라.** 경로 `F:/dev/Portfolio/earnings-forecast-engine` (ASCII).
> Claude가 scaffold(스키마·시그니처·프롬프트·fixture·테스트)를 작성했다. Codex는 아래 명세대로 **함수 본문만** 채운다.
> **YAML·주석·name_kr·프롬프트 문구 보존 — 코드만 수정.** 프롬프트 변경 시 `ai/prompts.py:PROMPT_VERSION` 올릴 것.
> 분업: 구현=Codex / 검증·방법론=Claude / 가정·라벨·해석=사용자.

## 0. 무엇을 만드나
공시·IR 텍스트 → 구조화 신호 → (1) forward **콜 사전 브리핑**, (2) 신호가 실적발표 전후 **CAR**를 예측하는지 **backtest**.
산출물 = 콜 브리핑 1건 + 신호 backtest 표 1건. **SK하이닉스 1종목, MVP.** 다종목·DB·스케줄러·웹UI·프로덕션 스크레이퍼 금지.

## 1. 구현 대상 (NotImplementedError 스텁)
| 파일:함수 | 계층 | 핵심 |
|---|---|---|
| `ai/extractor.py:_call_anthropic` | IO | Haiku 4.5 호출 + JSON 파싱 (캐시·키 로직은 이미 구현됨, 건드리지 말 것) |
| `pipeline/disclosure_loader.py:load_ir_decks` | IO | deck PDF → pymupdf 텍스트 |
| `pipeline/disclosure_loader.py:fetch_dart_mdna` | IO | DART 공개뷰어 MD&A 텍스트 (키 불요) |
| `engine/signal_extractor.py:build_extracted_signal` | 순수 | raw dict 검증·정규화 |
| `engine/signal_extractor.py:signal_score` | 순수 | salience 가중 톤 점수 |
| `engine/signal_predictor.py:build_call_brief` | 순수 | 브리핑 조립 |
| `engine/signal_backtest.py:run_signal_backtest` | 순수 | CAR event study |
| `output/call_brief_builder.py:*` | IO | 브리핑·backtest 표 렌더 (4함수) |

`pipeline/yahoo_fetcher.py:fetch_earnings_dates`, `cli.py`(모드 배선·fixture 로더), 스키마, 프롬프트, fixture는 **이미 구현됨**. 그대로 사용.

## 2. §validation — `build_extracted_signal`
입력 `raw`(ai.prompts.OUTPUT_SCHEMA_HINT 형태) + `document` + `model_id` + `extracted_at` → `ExtractedSignal`.
- 필수 키 `topics`/`guidance_tone`/`surprise_candidates` 없으면 `ValueError`(silent default 금지).
- `guidance_tone` ∈ {up,flat,down} 아니면 `ValueError`.
- 각 topic: `salience`를 [0,1] **clamp**; `polarity` ∈ {positive,neutral,negative} 아니면 `ValueError`; `topic` 빈 문자열이면 drop.
- topic을 lowercased 텍스트로 **dedup**(최대 salience 유지), `salience` **내림차순 정렬**.
- `period_label`·`source`는 **document에서** 가져옴(모델이 자기 provenance를 못 정함).
- 테스트: `tests/test_signal_extractor.py::test_build_*`.

## 3. §signal-score — `signal_score`
연속 점수(IC용). 공식:
```
pos_neg = [t.salience for t in signal.topics if t.polarity in ("positive","negative")]
mag = mean(pos_neg) if pos_neg else (mean([t.salience for t in signal.topics]) if topics else 0.0)
score = tone_to_sign(signal.guidance_tone) * mag      # down -> 음수
```
빈 topics + flat → 0.0. 결정론(동일 입력 동일 출력).

## 4. §car — `run_signal_backtest` (방법론 핵심)
입력: `signals`(label→ExtractedSignal), `event_dates`(label→date), `stock_closes`/`market_closes`(date→close), `primary_days`,`secondary_days`.
```
공통 라벨 = set(signals) ∩ set(event_dates).  비면 ValueError.
정렬된 거래일 = sorted(stock_closes).
각 라벨:
  T0 = stock_closes에 존재하는 event_dates[label] 이상의 첫 거래일.
  r_t = close_t/close_{prev}-1 (stock·market 각각, 거래일 인접).
  AR_t = r_stock - r_market.
  CAR[T0->T+k] = Σ_{i=1..k} AR_{T0+i}   (T0 다음 거래일부터 k개; market_closes에도 같은 날 존재해야).
    윈도 불완전(거래일/가격 부족) → 해당 CAR None (조작 금지).
  signal_tone = signals[label].guidance_tone; predicted_sign = tone_to_sign(...); score = signal_score(...).
  realized_sign_t1 = sign(car_t1) (0이면 0); car_t1 None이면 realized None.
  direction_match_t1 = (car_t1 None or predicted_sign==0) ? None : (sign(car_t1)==predicted_sign).
집계:
  scored = direction_match_t1 not None 인 이벤트.
  directional_hit_ratio = mean(match) over scored (scored 없으면 0.0).
  IC = Spearman(score, car_t1) over (car_t1 not None) 이벤트, 쌍 < 3이면 None.
       구현: pandas.Series(scores).corr(pandas.Series(cars), method="spearman"). 신규 의존성 금지.
  sample_n = 점수화된 이벤트 수. window_primary = f"T+{primary_days}d".
  calibration(옵션): {"mean_abs_score": ...} 정도. 비워도 됨.
```
**비순환 (절대 규율)**: 이 함수에 실현 재무/회사 매출/QuarterlyActual을 **넣지 마라**. 시그니처에 그런 인자 추가 금지(테스트 `test_non_circular_signature`가 강제). 신호는 텍스트, CAR은 가격 — 독립.
**look-ahead**: 각 이벤트 신호는 그 T0의 **IR deck**(콜 당일 공개)에서만. DART MD&A(T0+2~4주)는 backtest에 **넣지 마라** — forward 브리핑 전용.
- 정답 fixture: `tests/fixtures/signal_backtest_fixture.json`. 앵커 이벤트 2024Q4 → `car_t1=0.05`, `car_t5=0.15`, hit_ratio=1.0, IC>0. (`tests/test_signal_backtest.py::test_exact_car_for_anchor_event`)

## 5. §call-brief — `build_call_brief`
입력: `signal`, `consensus`, `target_event_label`, `as_of`, `top_n_topics=5` → `CallBrief`.
- `top_topics = signal.topics[:top_n_topics]` (이미 정렬됨).
- `expected_qna`: 고salience 토픽·surprise_candidate마다 템플릿 질문 1개(LLM 없이). 예: 토픽 "HBM 수요/캐파" → `"HBM 캐파/수율 가이던스가 컨센 대비 어디인가?"`. surprise_candidate s → `f"{s} 관련 컨센 추정과의 괴리?"`.
- `dispersion_flags`: consensus 각 분기에 low/high 있으면 `(high-low)/|avg|`로 넓은 스프레드 flag; 분기 컨센 없으면 `"분기 컨센 부재"`. 그리고 `consensus.notes`의 yfinance .KS 신뢰불가 경고(결함 6)를 **반드시** 한 flag로 포함(브리핑이 컨센 수치를 신뢰하는 듯 보이면 안 됨).
- `predicted_revision_direction = signal.guidance_tone` (빈 signal이면 `"n_a"`).
- `confidence`: top 토픽 salience 함수(0~1 bound). 예 `min(1.0, mean(top3 salience))`.
- `interpretation = ""` (**사용자 작성, 자동 생성 금지** — ConsensusGap 규율 동일).
- 테스트: `tests/test_signal_predictor.py`.

## 6. §io — extractor / disclosure_loader
- `ai/extractor.py:_call_anthropic`: docstring의 4스텝 그대로. `temperature=0`, system은 `cache_control:{"type":"ephemeral"}`, 문서는 **user turn에만**(주입 방지). 출력 텍스트를 JSON 파싱(코드펜스 방어적 제거), 실패 시 `ValueError`(빈 dict 반환 금지). `ensure_ssl_env()`는 모듈 임포트 시 이미 실행됨 — anthropic import는 그 이후.
- `load_ir_decks`: `import fitz`(pymupdf). 각 spec의 `decks_dir/filename` 열어 `"\n".join(page.get_text() ...)`. `count_kr_chars`로 `char_count_kr`. 파일 없으면 **warn + drop**(전체 크래시 금지, 단 드롭된 event를 로그로 — silent skip 금지). `doc_date`는 ISO 문자열 → `date`.
- `fetch_dart_mdna`: Phase 0 검증 경로(`docs/data_sources.md §2`). `dsaf001/main.do?rcpNo=` HTML JS트리에서 "이사의 경영진단 및 분석의견" 노드(dcmNo/eleId/offset/length) → `report/viewer.do`로 본문. httpx retry/backoff(dart_fetcher 패턴). `reports/.cache/mdna_{rcp_no}.json` 캐시. `char_count_kr==0`이면 `ValueError`(빈 문서 반환 금지).

## 7. §output — call_brief_builder (4함수)
- `render_call_brief_html/md`: 헤더(target+as_of) / top_topics 표 / expected_qna / dispersion_flags(+신뢰불가 caveat) / 예측방향+confidence / **빈 "분석가 해석" placeholder**. Korean 사용자 대면, `encoding='utf-8'`.
- `render_signal_backtest_html/md`: 이벤트별 표(event/T0/tone/predicted/CAR T+1d/CAR T+5d/hit) + footer(hit_ratio·IC·sample_n) + **소표본 disclaimer 필수**(N 8~12, 통계적 유의 주장 금지 — 정성 신호). HTML은 self-contained.

## 8. 검증 (구현 후 전부 통과)
```powershell
pytest -q                                                     # 신규 포함 green (xfail가 xpass되면 mark 제거)
python cli.py --call-brief --company sk_hynix --dry-run        # fixture, API 無
python cli.py --signal-backtest --company sk_hynix --dry-run   # fixture deck+가격
# 라이브(사용자: ANTHROPIC_API_KEY·deck 배치 후):
python cli.py --signal-backtest --company sk_hynix
python cli.py --call-brief --company sk_hynix
```
- 앵커 이벤트 CAR 정확(0.05/0.15). 비순환 시그니처 유지. 동일 입력 재실행 시 LLM 캐시 히트(재호출 0).
- `interpretation` 빈 문자열(테스트 강제). 과대주장 금지(소표본 disclaimer).
- **YAML 숫자·deck 매핑·rcpNo·target_event는 사용자 확정 대기** — Codex는 구조만, 값 변경 금지.

## 9. 주의 (한글 경로/환경)
- ASCII 경로만. 임시 deck는 `C:/temp/earnings_forecast/decks/`. SSL 셋업(`_ssl_setup`)은 httpx/anthropic import 전 — extractor·disclosure_loader 모두 이미 import 순서 맞춤. 깨지 말 것.
- `open()` 전부 `encoding='utf-8'`. Pydantic v2 `model_validate`/`model_dump`. engine 반환에 DataFrame 금지.
