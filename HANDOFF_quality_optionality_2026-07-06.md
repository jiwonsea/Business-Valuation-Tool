# HANDOFF — 옵셔널리티 인지 품질 수렴도 + Meta 프로파일 + GOOGL 주식수 플래그

세션: 2026-07-06 (Cowork). 9개 기업(삼성·SK하이닉스·M7) 밸류에이션 신뢰성 점검 중 도출.
전체 신뢰성 평가: `docs/RELIABILITY_REVIEW_2026-07-06.md`.

## 1. 변경: 옵셔널리티 종목 수렴도 계산에서 DCF 제외 (`engine/quality.py`)

**문제.** 옵셔널리티/하이퍼그로스 종목(NVDA 등)에서 교차검증 방법이 두 갈래로 분열:
DCF·EV/EBITDA(성장옵션 미포착 → 낮음) vs EV/Revenue·P/E·P/BV(성장 프리미엄 반영 → 높음).
NVDA CV=41.9% → 수렴도 3/25 → 품질 53(D). 근본원인은 **옵셔널리티 미반영**(멀티플 배정은 증상).

**해결.** rNPV가 이미 쓰던 선례(`_RNPV_EXCLUDED_CV_METHODS = {"DCF (FCFF)"}`,
"EBITDA-based TV misses pipeline option value")를 일반 SOTP로 확장:
- 신규 `_has_optionality_segments(result)` — SOTP 세그먼트에 `method=="ev_revenue"`가 있으면 True.
  (`infer_valuation_bucket(has_optionality_segments=...)`와 동일 판별.)
- 신규 상수 `_OPTIONALITY_EXCLUDED_CV_METHODS = {"DCF (FCFF)"}`.
- `_cv_convergence_score(cross_vals, exclude_methods=None)` — 파라미터 추가. 제외 후에도
  방법이 2개 미만이면 전체 집합으로 폴백(안전). 극단값 네이밍 루프도 `considered` 기준으로 수정.
- `calc_quality_score`의 비-rNPV 분기에서 옵셔널리티면 exclude 전달.

**효과.** NVDA 53(D)→58(C). 비옵셔널리티(MSFT·AAPL·AMZN·삼성·SK하이닉스) **점수 완전 불변**(가드).
이미 수렴한 옵셔널리티(TSLA·GOOGL·META)는 경고만, 수치 불변.

**검증.** `pytest tests/test_engine.py` = 278 pass / 1 fail. 그 1건은
`TestFullPipeline::test_sk_ecoplant_profile`(WACC 8.79 vs 8.02 기대) — **이 변경과 무관**,
pristine `quality.py`(git HEAD)에서도 동일 실패(프로파일 드리프트, CLAUDE.md 기지 이슈).

**후속(Codex).** (a) `tests/`에 옵셔널리티 exclude 단위테스트 추가 권장
(`_cv_convergence_score(cv, exclude_methods={"DCF (FCFF)"})`가 제외·폴백·경고를 올바로 처리하는지).
(b) `prediction_snapshots` 재저장 시 옵셔널리티 종목 cv_convergence가 상향됨 — 백테스트 버킷
해석에 반영. (c) exclude 대상을 EV/EBITDA까지 넓힐지는 데이터로 결정(현재는 DCF만, 보수적).

## 2. 신규: `profiles/meta.yaml` (BVT 9/9 완성)

M7 중 유일하게 없던 Meta 추가. 실적 앵커=보고치(FY2025 매출 $201.0B·순이익 $60.5B·EPS $23.49;
FY24/FY23 포함). 세그먼트: FoA(광고, EV/EBITDA) + Reality Labs(적자, ev_revenue 옵셔널리티)
+ AI 수익화(ev_revenue). SOTP $674/주, 품질 70(B), 옵셔널리티 exclude 정상 작동.
**주의:** 대차대조표 세부·세그먼트 자산배분 일부는 근사치(헤더 코멘트). 라이브 주가 오프라인 미포함.

## 3. 플래그(미수정): GOOGL 주식수 오류 — 내재가치 ~2배 과대

`profiles/googl.yaml` `shares_total: 5,822,000,000`은 **Class A만**. Alphabet 2025 희석주식수
**13.08B**, 희석 EPS **$10.81**(SEC/보고). 프로파일 순이익 $132B ÷ 5.82B = 내재EPS $22.7(실제 2배).
∴ 내재가치 $409는 ~2.1배 과대, 보정 시 ~$185–195.
**수정 권장:** `shares_total`/각 시나리오 `shares` → ~12,100,000,000(보통) 또는 13.08B(희석).
단, `--auto` 재생성 시 파이프라인이 주식수를 다시 채우므로 pipeline 소스(주식수 파서)도 점검할 것.

## 4. 공통 후속(호스트)
- 라이브 주가 주입 → `시장가격 정합`(0/25) 회복 + gap_diagnostics/reverse-DCF 작동.
- 빈티지 프로파일(analysis_date 2026-04) `--auto` 재생성(2026-07 실적/주가).
- 커밋: `engine/quality.py`, `profiles/meta.yaml`, `docs/RELIABILITY_REVIEW_2026-07-06.md`, 본 파일.

## 세션 중 기록: mount 동기화 이슈
Cowork bash mount가 편집된 기존 파일을 stale/truncated로 서빙해 `engine/quality.py`가 한때
잘림. git HEAD에서 복원 후 프로그램적 재적용(assert 매칭) → cp로 재동기화하여 정합 확인 완료.
현재 on-disk 파일 무결(파싱 OK, `format_quality_report` 보존, NVDA 재현).

---

## 개정 2 (2026-07-06 오후) — 라이브 주가 · 빈티지 · 옵셔널리티 일반화

사용자 피드백 반영: (1) 라이브 주가는 가져올 수 있으니 주입, (2) 빈티지 갱신,
(3) 옵셔널리티가 NVDA 전용이 아니므로 일반화.

**5. 옵셔널리티 판별 일반화 (`engine/quality.py`, 근본 개선).**
1차의 구조적 판별(`ev_revenue 세그먼트 보유`)은 NVDA·GOOGL·META·TSLA만 잡고 AAPL·MSFT·AMZN 누락.
→ `_cv_convergence_score`에 **경제적 신호 기반 자동 제외** 추가: DCF per-share가 시장배수
(P/E·EV/Revenue·P/BV) 중앙값의 **70% 미만**이면 DCF를 수렴도에서 제외(`_dcf_ratio < 0.7`).
성장 프리미엄을 현금흐름법이 재현 못하는 구조를 데이터로 탐지 → 빅테크 전반 일관 적용.
발화 확인: AAPL(40%)·AMZN(33%)·NVDA(36%)·삼성(38%)·TSLA(3%). 구조적 param도 유지(belt&suspenders).
`_make_cvs`가 `Method{i}` 이름을 쓰므로 기존 8개 cv 단위테스트 불변. 338 pass.

**6. 프로파일 market_price 주입 (오프라인 시장정합).**
- `schemas/models.py`: `ValuationInput.market_price: Optional[float] = None` 신설.
- `valuation_runner.load_profile`: `market_price=raw.get("market_price")` 전달.
- `cli._fetch_and_compare_market_price`: 라이브 조회 실패 시 `vi.market_price` 사용(라이브 우선).
- 9개 프로파일에 `market_price:`(2026-07 라이브) + `analysis_date: '2026-07-06'` 주입.
효과: 전 종목 `시장가격 정합` 3~20점 + 괴리율 + 역방향 DCF 진단 작동.

**7. GOOGL 주식수 수정 + mc_enabled 드리프트 정정.**
`shares_total` 5.82B(Class A)→~12.1B(총). 내재가치 $409→**$197**(시장가 $359 대비 −45%).
현재 googl.yaml의 `mc_enabled:` 빈값(null, AI 재생성 잔여)도 `true`로 정정(안 하면 pydantic bool 에러).

**개정2 검증.** 9/9 실행, 품질 전반 상승(삼성72·SK하이닉스78·AAPL78·MSFT84·GOOGL83·AMZN78·
NVDA72·TSLA71·META90). `pytest tests/test_quality.py tests/test_engine.py` = 338 pass,
1 fail = `test_sk_ecoplant_profile`(WACC, 무관·기존).

**개정2 후속(Codex).** (a) `market_price` 수동값은 stale → 호스트 라이브 우선 유지.
(b) GOOGL 재생성 시 주식수 파서가 Class A만 잡는지 점검(재발 방지). (c) `_dcf_ratio` 임계 0.7은
경험적 — 백테스트 데이터로 캘리브레이션 여지. (d) 옵셔널리티 exclude 단위테스트 추가 권장.

**mount 이슈 회피.** 개정2의 Python 편집은 Edit 툴 대신 **git-fresh 소스 + 프로그램적 str.replace
(assert 매칭) + 직접 write**로 적용해 mount stale/truncation을 원천 차단. 프로파일도 동일.
