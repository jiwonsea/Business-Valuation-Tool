# START (COMMON) — EFE Q2 2026 프린트-전 실적 예측 동결 + 사후 채점

> **실행 위치**: `F:\dev\Portfolio\earnings-forecast-engine` (새 세션)
> 이 파일은 5개 종목(GOOGL·TSLA·IBM·GEV·TXN) EFE 세션의 **공통 프로토콜**이다.
> 종목별 세부는 `START-efe-q2-2026-<티커>.md`에 있다. **먼저 이 파일을 읽고, 이어서 해당 종목 파일을 읽어라.**

---

## 0. 이번 작업의 목적 (왜 지금인가)

Q2 2026 실적이 **아직 발표되지 않았다**. 이 공백이 곧 우리 모델(EFE)의 예측 정확도를
객관적으로 검증할 유일한 창이다. 발표 후에 맞추는 건 사후확증이다.
→ **프린트 전에** 우리의 Q2 매출·EPS·주요 P&L 예측을 타임스탬프와 함께 **동결(freeze)** 하고,
컨센서스 대비 우리 위치를 기록한다. **발표 후** actual과 대조해 오차·귀인·백테스트 skill을 갱신하고,
"무엇을 고치면 다음 분기 예측이 나아질지"를 남긴다.

이건 밸류에이션이 아니다(그건 BVT 몫). 여기서 채점하는 건 **분기 실적 예측력**이다.

---

## 1. 방법론 계약 (절대 지킬 것)

- **Generic 경로만 사용.** `python generic_cli.py --profile profiles/<티커>.generic.yaml`.
  5종 모두 물리 드라이버의 독립 산업 피드가 없다(비트×ASP·wafer·구독자 같은 검증 가능한 외부 피드 부재).
  → **바텀업 유닛×ASP 모델 금지** (`PLAN_nvidia_application.md` §2 결정규칙). 매출성장벡터 × 영업이익률의
  top-down generic 모델이 "실제보다 정밀해 보이는" 함정을 피하는 정직한 형태다. SK Hynix 메모리 경로
  (`cli.py`·`engine/segment_revenue.py`·`margin_model.py`)는 **절대 건드리지 않는다.**
- **데이터 무결성 = 1순위 리스크 (NVDA-1 교훈).** 신규 프로파일(IBM·GEV·TXN)의 분기 `actuals`는
  반드시 EDGAR companyfacts 원문에서:
  - `pipeline/edgar_fetcher.py`의 **whole-blob CIK 캐시**로 회사 전체 companyfacts를 1회 수집(개념 슬라이스는 파생 캐시).
  - `split_history: [{date, ratio}]`를 프로파일에 명시하고 정규화 레이어에서 적용.
  - **Q4 = 연간(10-K) − 9M** (같은 accession). 분기 라벨 연속성 검증(Q3→Q1 조인 금지).
  - **EPS는 선택하지 말고 파생**: `eps_diluted = net_profit × unit_scale / split조정 희석주식수`. companyfacts는
    같은 기간에 as-filed 값과 소급 분할조정 비교치를 **둘 다** 담고 있어 naive 선택은 basis를 섞는다(NVDA에서 −45.8% bias의 주범).
  - 절대 서로 다른 공시 vintage를 섞어 YTD에서 Q2/Q3/Q4를 파생하지 말 것.
- **기존 generic actuals는 backtest를 REFUSE 상태다.** `googl.generic.yaml`·`tsla.generic.yaml` 포함 M7/삼성 프로파일은
  gap 있는 파생 actuals라 `backtest_generic`이 거부한다. → `scripts/build_generic_actuals.py`로 재구축한 뒤에만 백테스트.
- **회계연도**: 5종 모두 **12월 결산** → NVDA(1월)·MSFT(6월)·AAPL(9월) 같은 ~1개월 컨센서스 조인 오프셋이 **없다**.
  그래도 period-end ↔ 모델 라벨 매핑은 명시적으로 두고 테스트한다.
- **컨센서스 갭**: US 티커는 Yahoo 애널리스트 커버리지가 풍부하다. raw Yahoo 파싱을 재사용하되
  `.KS` 전용 품질 게이트(내재 순마진 >60% 체크 등)는 쓰지 말 것(issuer-neutral 임계값). 컨센서스는 미래치라 SEC 불가 —
  provider·as-of·애널리스트 수·컨센 종류를 기록하고 **"consensus estimate"로 명시**, 실적과 구분.

---

## 2. 프린트-전 동결 프로토콜 (발표 시각 이전에 완료)

산출물: `reports/<티커>_q2_2026_forecast_FROZEN.md` — 상단에 **동결 시각(UTC/KST)·`git rev-parse HEAD`·프로파일 sha256** 기재.
아래 (a)~(f)를 모두 담는다:

- **(a) 총매출·희석 EPS 포인트 추정 + bear/base/bull.** 단위·통화 명시.
- **(b) 세그먼트별 매출·마진 예측** — 비트/미스가 어디서 날지. 세그먼트 구조는 종목 파일 참조.
- **(c) 가이던스 방향 예측** — 차기 분기/FY 가이던스 상향·유지·하향. (주가는 EPS보다 가이던스에 반응하는 경우가 많다.)
- **(d) 컨센서스 대비 우리 위치** — above/below 여부, 근거, 확신도(상·중·하). 이게 EFE의 존재 이유(consensus↔intrinsic gap).
- **(e) 컨퍼런스콜 Q&A 예상 토픽** — 경영진이 집중 방어/강조할 지점.
- **(f) 우리를 틀리게 만들 스윙 팩터 1~2개 사전등록** — below-OP 블록(FX·평가손익·일회성), 세금, 크레딧, OI&E 등.
  나중에 변명이 아니라 사전 리스크로 박아둔다.

동결 직후 SendUserFile로 사용자에게 전달(발표 전 기록 증빙).

---

## 3. 사후 채점 프로토콜 (실적 발표 후)

1. actual 확보(EDGAR 10-Q / IR 릴리스). 샌드박스 외부망 차단 시 호스트 또는 Chrome `javascript_tool` same-origin fetch.
   → **원문에서 읽은 수치를 동결·핸드오프에 쓰려면 §7 원문 인용 계약을 반드시 충족할 것.**
2. FROZEN 예측 ↔ actual 대조: **매출·EPS MAPE, bias(부호)**. 세그먼트별 오차.
3. **4-lever generic 귀인** (매출 / 영업이익률 / OP→NI 전환 / 주식수) — 5-lever 메모리 버전을 재사용하지 말 것(generic엔 GP 분해가 없다). 어느 레버가 오차를 만들었나.
4. `engine/skill_metrics.py`로 MASE/Theil(vs 나이브 RW) + 컨센서스 대비 **surprise 방향 적중** 산출.
5. 결론: 사전등록한 스윙 팩터가 실제로 발화했나? YAML 한 줄 앵커 수정으로 고칠 수 있는 체계적 편향인가(tax·opex 앵커 선례), 아니면 리스크밴드로 보낼 구조적 항목인가?
6. `HANDOFF_CODEX_efe_q2_2026_<티커>.md`에 before/after 수치·귀인·개선안 기록. 채점은 **"사후 귀인 — 예측 신호 아님"** 라벨 유지.

**9Q SK Hynix 불변식**: 어떤 변경도 host canonical(CPython >=3.12) `BacktestResult` sha256 `b979d79f…f6e7`를 bit-identical 유지해야 한다(메모리 경로 미변경 증빙; CPython <=3.11 canonical은 `077ecb10…933c`).

---

## 4. 샌드박스 / 실행 gotcha

- Yahoo·DART는 샌드박스에서 403. **generic 경로는 YAML만으로 오프라인 실행 OK.** 라이브 컨센서스/EDGAR는 호스트 또는 Chrome same-origin.
- deps: `pip install -r requirements.txt --break-system-packages`. 세션마다 리셋.
- `.py`/`.md` 큰 편집 후 즉시 `python3 -c "import ast; ast.parse(open('<f>').read())"` + `wc -l` + NUL 스캔. Windows 마운트에서 mid-line truncation 이력 있음 → 원자적 재작성 우선.
- 단일 Plotly HTML < 5MB(시스템 폰트만). generic은 MD 출력이 기본.

---

## 5. Codex ↔ Claude 6축 교차검증 루프

```
Claude 진단·정량분해 → Codex 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성) 평가
→ Claude 독립 재현(Codex 주장 믿지 말 것) → 반박/수용 → Codex 확정본 → Claude 검증(독립 재현 + 회귀표) → 반복
```

- **Codex의 "diff 0 / pytest 통과 / NUL clean" 주장을 그대로 믿지 말고 독립 재현하라** — 실제로 여러 건 사실과 달랐다.
- git(add/commit/stage)은 **호스트/Codex 전담**(사용자는 git 미사용). 샌드박스 git read는 `GIT_OPTIONAL_LOCKS=0` 접두.
- 프로파일/스크립트 쓰기는 **원자적(temp→replace) + 기록 직후 재read fail-closed.** 수동 편집 금지.

## 6. 산출물
- `reports/<티커>_q2_2026_forecast_FROZEN.md` (프린트 전 동결)
- (신규 종목) `profiles/<티커>.generic.yaml` + `scripts/build_generic_actuals.py`로 만든 무결성 actuals + `tests/` 추가
- (발표 후) 사후 채점 md + `HANDOFF_CODEX_efe_q2_2026_<티커>.md`
- 검증: `pytest -q` 전체 그린 + 9Q sha256 일치 + `generic_cli.py --profile ...` before/after 기록

---

## 7. 원문 인용 계약 (PRIMARY-SOURCE CONTRACT) — 2026-07-31 신설

**왜:** 원문 추출은 **예외를 던지지 않고 반쯤 비어서 성공한다.** 표만 누락되고 헤더는 살아남는
경우가 전형이라 "읽었다"는 사실만으로는 아무것도 보장되지 않는다. 실제로 GEV `HANDOFF_..._gev.md` §16은
`gev_webcast_10q_07222026.pdf`를 근거로 Q3 설계값(OP 앵커·세율·주식수·below-OP)을 확정했으나
**그 파일이 폴더에 없어 한때 감사 사슬이 끊겼다.**
(근거·판정: `HANDOFF_CODEX_doc_ingest_2026-07-31.md`, Codex 6축 회신 Q3/Q5.)

**계약:** 원문에서 읽은 수치를 **FROZEN·핸드오프·설계 앵커**에 쓰려면 인용 블록에 아래 7항을 모두 적는다.
하나라도 없으면 그 수치는 **동결 근거로 쓰지 않는다**(참고 인용은 무방하되 "미검증"으로 표시).

1. **출처 식별** — 파일명 또는 URL, accession/rcpNo, 취득일시(KST), **문서 SHA-256**.
2. **분량** — 페이지 수, 전체 문자수, **페이지별 문자수**(0자 페이지가 스캔·추출실패 신호).
3. **추출기** — 이름과 **버전**(예: `pymupdf 1.24.x` / `pdfplumber 0.11.x` / `WebFetch(markdown 변환)`).
   변환 계층이 끼면 그 사실을 명시한다 — markdown 변환본은 원문이 아니다.
4. **섹션 앵커** — 기대 섹션 문자열과 **그것이 나온 페이지 번호**
   (예: 10-Q면 `CONDENSED CONSOLIDATED STATEMENTS OF INCOME`).
5. **수치별 좌표** — 동결에 쓰는 **각 핵심 수치마다**: 기간 · 행 라벨 · 값과 단위 · 원문 페이지 ·
   주변 행 또는 항등식 대조.
6. **재무 항등식 검증** — 최소: `매출 − 매출원가 = 매출총이익`, `GP − SG&A − R&D ≈ OP`,
   `OP + below-OP = 세전이익`, `세전 − 법인세 = 순이익`, `지배주주순이익 ÷ 희석주식수 ≈ 희석 EPS`.
   **반올림 차 ±1 단위는 허용하되 기록**한다(표 자체의 반올림).
7. **표 시각 확인** — 표가 핵심 근거면 해당 페이지를 렌더링해 눈으로 대조한다(텍스트 레이어만 믿지 않는다).

**원본 보존:** 인용 원본을 `reports/.cache/src/<티커>_<문서>_<YYYYMMDD>.<ext>`로 저장하고,
같은 이름의 `.meta.json`(위 1~4항 + 취득 명령)을 **sidecar로 함께** 둔다.
`.gitignore`가 `reports/.cache/`를 제외하므로 레포 비대·재배포 리스크는 없다.
→ **단, 그래서 이건 영구 감사 근거가 아니라 로컬 재검증 캐시다.** 삭제·이동될 수 있으므로
**감사 사슬의 실체는 sidecar에 적힌 SHA-256과 accession/URL**이다. 파일이 사라져도 그 둘로 재취득·재대조가 가능해야 한다.

**샌드박스 제약(실측 2026-07-31):** Cowork 샌드박스는 프로세스 레벨에서 `www.sec.gov`·`data.sec.gov`가
프록시 403(`CONNECT tunnel failed`)이라 **원문 바이트를 내려받아 SHA-256을 계산할 수 없다.**
WebFetch 도구는 동작하지만 **markdown 변환본**이라 바이트 동일성이 없다.
→ 샌드박스 세션은 1~7항 중 SHA-256을 제외하고 채운 뒤 **"바이트 보존 미완 — 호스트 필요"를 명시**하고,
호스트/Codex 세션이 원본 저장 + SHA-256을 완결한다.

**측정 스크립트 인코딩 규칙:** 재현 스크립트에 **한글 리터럴을 넣지 말 것.**
`'가' <= c <= '힣'` 같은 비교는 Windows(cp949) 경유 시 조용히 깨져 **0을 반환**한다
(2026-07-31 Codex 재현에서 실제 발생 — 문자수 비율은 일치했으나 한글자수만 0/0으로 어긋났다).
→ 코드포인트로 쓴다: `0xAC00 <= ord(c) <= 0xD7A3`. 스크립트 자체가 이 계약의 실패 사례가 되어선 안 된다.
