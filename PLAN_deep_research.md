# PLAN: Deep-Research 파이프라인 — 자동 경로를 심층 리서치 수준으로

**v4 (2026-07-11) — CODEX 3차 평가 반영. 시나리오 배수 결정론화 · P1 3범주 분리 · 방법론 라우팅 확정 · migration 대상 정정.**
대상 브랜치 main · 상태 **P0-0 착수 가능**

v1 → v2: 순현금 주당 환산 누락으로 P0 가격 주장 반증 (§0)
v2 → v3: 골든의 부문 영업이익이 균등배분 산물임을 발견 → 세그먼트 3레이어, G-PRICE 폐기 (§0)
v3 → v4: VS-1e의 LLM 시나리오 배수 생성이 P1 위반 → 결정론 규칙으로 대체 (§2.6). P1을 3범주로 재정의 (§1)

---

## 0. 개정 이력 — 두 번의 반증

### v1의 오류: 순현금에 현혹됨

v1은 "P0(순차입금·베타·rf·게이트·peer)만으로 NVDA 괴리가 −70% → 30% 이내"라고 주장했다. CODEX가 검산해 반증:

| 단계 | WACC | 주당가치 | 괴리 |
|---|---:|---:|---:|
| 원본 (`--company NVDA --auto`) | 16.39% | $63 | −68.9% |
| + 순현금 교정 (−41,865) | 16.39% | **$64** | −68.4% |
| + βL 1.50 | 12.50% | $91 | −55.0% |
| + rf 4.56 / ERP 4.6 | 11.46% | $104 | −48.6% |
| + WACC 11.0% | 11.00% | **$109** | **−46.1%** |

순현금 $41.9B는 **주당 $1.75**다(41,865 $M ÷ 24.2B주). 절대금액에 현혹돼 주당 환산을 하지 않았다.

### v2의 오류: 골든이 재현 가능하다고 가정함

v2는 "공시 세그먼트를 XBRL에서 추출하면 $175 골든에 도달한다"고 설계했다. **재현 불가능하다.**

NVIDIA의 **reportable segment는 2개**다 (Compute & Networking / Graphics — FY2026 10-K, Q1 FY27에도 유지).
Q1 FY27부터 바뀐 Data Center / Edge Computing은 **reportable segment가 아니라 market-platform 표시**다.
골든 `nvda_ttm.yaml`은 **5개 세그먼트**
(Data Center / Gaming / ProViz+Auto / 자율주행 / 군사AI)를 쓴다.

더 나쁜 사실 — 골든의 부문 영업이익을 검산했다:

| 부문 | 매출 | 영업이익 | 영업이익률 |
|---|---:|---:|---:|
| SEG1 Data Center | 221,737 | 141,912 | **64.0%** |
| SEG2 Gaming | 20,269 | 12,972 | **64.0%** |
| SEG3 ProViz+Auto | 11,402 | 7,297 | **64.0%** |
| 연결 TTM | 253,491 | 162,285 | **64.0%** |

전부 동일하다. **부문 영업이익은 공시가 아니라 연결 영업이익률을 매출에 균등 배분한 값이다.**
NVIDIA는 market-platform별로 **매출만** 공시하고 영업이익은 공시하지 않는다.

결론 두 가지:
1. **$175 골든의 부문 EBITDA는 만들어낸 숫자다.** 이 PLAN이 세운 원칙 P1("LLM/사람이 숫자 생성 금지")을
   골든 자신이 위반한다. 골든은 실질적으로 **부문별 멀티플만 다른 EV/Revenue 블렌드**이며, SOTP의 외피를 쓴
   revenue-weighted 배수 평가다.
2. 따라서 **`|괴리|≤30%` 같은 가격 수렴 기준을 acceptance gate로 두면, 만들어낸 숫자를 재현하도록 시스템을
   튜닝하게 된다.** CODEX가 "사후 확인이라는 설명과 무관하게 시장가 맞추기를 유도한다"고 지적한 그대로다.

**v3의 핵심 전환: 목표를 "골든 가격 재현"에서 "공시 가능한 것만으로 방어 가능한 평가"로 바꾼다.**
$175는 목표가 아니라 **참고 상한**이다. 공시만으로 도달할 수 없다면, 도달하지 않는 것이 정직하다.

---

## 1. 설계 원칙

> **P1. 숫자는 출처가 있거나, 가정으로 선언되거나, 둘 다 아니면 금지.**
> v3 초안의 "사람도 숫자 생성 금지"는 P6/L3의 `manual_override`와 모순이었다. 세 범주로 분리한다.
>
> | 범주 | 예 | 규칙 |
> |---|---|---|
> | **① 관측치** | 공시 재무, 시장가, peer EV/EBITDA, rf, raw beta, 애널리스트 컨센서스 | **입력 가능. provenance 필수** (`source, accession/url, as_of`). LLM 생성 **금지** |
> | **② 명시적 가정** | 시나리오 확률, 영구성장률, 옵셔널리티 매출, DLOM, 정상화 판단 | **허용.** 단 ①과 **필드·저장소에서 분리**하고 **민감도 분석 필수**. LLM은 *제안*만 하고 근거(`rationale`)를 남긴다. 사람이 승인 |
> | **③ 근거 없는 배분·창작** | 부문 영업이익 균등배분, 조회 실패 peer의 추정 멀티플, "2024 consensus" 같은 미검증 수치 | **전면 금지.** 사람·LLM 모두 |
>
> 골든의 64% 균등배분은 ③이다. 옵셔널리티 매출은 ②로 선언하면 허용된다 — 단 관측치인 척하면 안 된다.

> **P1-a. LLM의 허용 역할.** 세그먼트 분류, peer *후보 티커* 제시, 시나리오 *서사*, 적용 가능한 관측 집합 *선택*, 가정의 *근거 서술*. **어떤 수치도 직접 생성하지 않는다.**

> **P2. 앵커는 하나가 아니다.** FY확정 / TTM / 가이던스 / 컨센서스를 병렬 실행하고, 시장가가 어느 앵커에 서 있는지를 읽는다.

> **P3. 조용한 실패도, 조용한 교정도 금지.** raw beta 2.2를 몰래 1.45로 바꾸는 것은 조용한 실패의 다른 얼굴이다. 원값·조정값·출처·민감도를 모두 보존한다.

> **P4. `engine/`은 순수 함수 유지.** 예외적으로 `engine/method_selector.py`의 **라우팅 분기**는 변경한다(§2.7). 밸류에이션 수식이 아니라 방법론 *선택* 로직이며 순수 함수로 남는다.

> **P5. 계보 없는 숫자는 저장하지 않는다.** 모든 material 필드에 `(value, source, accession/url, as_of, normalization_version)`.

> **P6. 공시되지 않은 배분은 생성하지 않는다.** 영업이익이 부문별로 공시되지 않으면 부문별 EV/EBITDA SOTP를 **하지 않는다.** 매출만 공시되면 EV/Revenue까지만 한다. 배분을 쓰려면 P1 범주 ②(명시적 가정)로 **선언 + 민감도**가 있어야 하고, 자동 경로는 절대 생성하지 않는다.

---

## 2. 계약 확정안

### 2.1 순차입금 taxonomy (v2 유지)

| 항목 | 처리 |
|---|---|
| 현금성자산 | **차감** |
| 단기투자·시장성 **채무**증권 (`ShortTermInvestments`, `AvailableForSaleSecuritiesDebtSecuritiesCurrent`, `MarketableSecuritiesCurrent`) | **차감** (NVDA $37,098M) |
| 제한현금 | 차감 안 함 |
| 시장성 **지분**증권 | 차감 안 함 — 별도 "상방 브리지"로만 표시 |
| 비시장성 증권 | 차감 안 함 (NVDA 1분기 +$21.1B = Bear의 순환거래 익스포저 그 자체) |

태그 중복 우선순위: 결합 태그가 있으면 제한현금 제외 후 사용, 개별 태그 우선. **구성요소를 `net_debt_components`에 전부 저장하고 합계와 대조.** 단순 합산 금지.

### 2.2 세그먼트 3-레이어 계약 (**신규 — v2의 최대 결함 수정**)

공시 수준에 따라 **할 수 있는 평가가 다르다.** 레이어를 섞지 않는다.

| 레이어 | 공시 내용 | 허용 방법론 | NVDA 예시 |
|---|---|---|---|
| **L1 (기본)** | reportable segment: **매출 + 영업이익** (ASC 280) | **EV/EBITDA SOTP** — 진짜 SOTP | Compute & Networking / Graphics **2개** |
| **L2 (보조)** | market platform: **매출만** | **EV/Revenue** 만. EBITDA 배수 **금지** | Data Center / Gaming / ProViz / Auto / OEM |
| **L3 (옵셔널리티)** | 공시 없음 | **자동 생성 금지.** 기본 0. 사람이 넣으면 **P1 범주 ②(명시적 가정)** 로 선언 — 관측치 필드와 분리 저장 + 민감도 필수. 또는 reverse-DCF 진단으로만 | 자율주행 / 군사AI |

- **VS-1의 기본 산출물은 L1이다.** L1으로 SOTP를 돌리고, L2는 **보조 시각화/교차검증**으로 병기한다.
- L2에 EV/EBITDA를 적용하려면 부문 영업이익이 필요한데 그건 공시에 없다 → **P6 위반이므로 금지.**
- L3는 골든이 $175에 도달한 주요 동력이지만(옵셔널리티 EV 40,000 $M), **공시 근거가 0이다.**
  자동 경로는 이것을 만들지 않는다. 결과적으로 자동 경로의 결론은 골든보다 **보수적**일 것이며, 그것이 옳다.
- **NVDA 사실관계 (CODEX 3차 정정):** Q1 FY27부터 **market-platform 표시**가 Data Center / Edge Computing으로
  개편되었지만, **reportable segment는 Compute & Networking / Graphics로 유지**됐고 비교기간도 재작성되어
  **L1 연속성은 유지된다.** 개편된 것은 L2다.
  (근거: `https://www.sec.gov/Archives/edgar/data/1045810/000104581026000052/R20.htm`)
- 일반 규칙: 보고체계 개편으로 **소급 공시가 사라져 L1 시계열이 끊기면** TTM 세그먼트 SOTP를
  **생성하지 않는다**(§2.10 원칙과 동일). NVDA에는 해당하지 않는다.

### 2.3 베타 정책 (**상장/비상장 분리 — CODEX 지적 반영**)

v2의 "raw beta 없으면 차단"은 **비상장 기업을 전부 막는다.** 분리한다.

| 구분 | 1순위 | 교차검증 | 차단 조건 |
|---|---|---|---|
| **상장사** | 검증된 raw equity beta (관측창·빈도·출처 기록: 예 2Y weekly, yfinance) | Blume 조정값 **병기** + peer median unlevered beta | 출처/관측창 **부재**, 또는 raw-vs-reference **중대 불일치 미해결**. 대조는 **같은 basis끼리** 한다 — raw βL을 먼저 Hamada 언레버한 뒤 `target βU > peer median unlevered × 1.5`이면 불일치 (P0-2a 정정: levered vs unlevered 직접 비교는 레버리지가 높은 정상 기업을 오차단한다). 금융업은 equity basis끼리 비교 |
| **비상장사** | **peer median unlevered beta** (관측 peer, §2.5 유효성 기준 충족 시 — 고유 법인 N ≥ 4) | 산업 beta 테이블(Damodaran, 연 1회) | 유효 peer < 최소 N **이고** 산업 테이블에도 매핑 실패 |

- **범위 이탈([0.3, 2.0])은 차단 사유도, 자동 대체 사유도 아니다.** 경고 + 민감도 표시.
- 자동 클램프/대체 코드 **작성 금지.** override는 사람이 하고 `{원값, 대체값, 사유, WACC 민감도}`를 산출물에 명시.
- 순환 의존 차단: peer beta는 **§2.5 관측 스냅샷**(`BetaPeerSnapshot`)에서 오되, **멀티플 선정과 분리된 동일 시점 데이터셋**을 쓴다. 대상 회사 beta와 관측창·빈도·벤치마크·계산법·기준일이 다른 peer는 교차검증에서 제외한다 (서로 다른 데이터셋의 beta는 서로를 반증할 수 없다).

### 2.4 매크로 (rf / ERP) — **동일 기준일 강제 폐기**

- rf(FRED `DGS10` / ECOS 국고채10Y)와 ERP(Damodaran 월간)는 **갱신 주기가 다르다.** 동일 기준일 강제는 비현실적.
- 각각 **자기 `as_of`를 기록**하고 **허용 시차**를 둔다: rf ≤ 7일, ERP ≤ 45일. 초과 시 `stale` 플래그.
- 실패 시 상수 폴백하되 `rf_source: "fallback constant"` + 기준일 + stale TTL을 반드시 기록.

### 2.5 peer 유효성 — **성공률 80% 폐기**

"조회 성공률 80%"는 후보 품질에 좌우된다(LLM이 롯데칩스를 넣으면 분모가 오염됨). 대체:

- **최소 유효 peer 수**: 부문당 **N ≥ 4** (사분위수가 의미를 갖는 최소치). 미달 시 해당 부문 멀티플은 `peer-derived` 자격 상실 → placeholder 취급 → 게이트 대상.
- **freshness**: 각 관측치 `as_of` ≤ 7일. 초과 시 제외.
- **유효성**: 티커 resolve · 상장 상태 · 독립 법인(피인수 제외) · EV/EBITDA > 0.
- **조회 실패 시 LLM 숫자로 폴백 금지 → 결측.** (Xilinx·Intel Arc·롯데칩스가 자동 탈락)
- LLM 출력은 `ticker + 선정 이유`만 허용. 프롬프트에서 `ev_ebitda` 필드 **제거**.

### 2.6 시나리오 계약 — **배수는 결정론, 확률은 선언된 가정** (신규)

v3 초안의 VS-1e는 `ai/prompts.py`에서 시나리오별 `segment_multiples`를 **LLM이 생성**하게 했다. **P1 직접 위반**이다. 폐기하고 결정론적 규칙으로 대체한다.

**시나리오별 부문 멀티플 (P1 범주 ① 파생 — LLM 관여 0):**

| 시나리오 | 규칙 | 출처 |
|---|---|---|
| Base | 관측 peer **median** | §2.5 관측 스냅샷 |
| Bull | 관측 peer **Q3** | 동일 스냅샷 |
| Bear | 관측 peer **Q1** | 동일 스냅샷 |

- 유효 peer N ≥ 4 (§2.5) 미달이면 사분위수가 의미 없다 → **시나리오별 배수를 생성하지 않고** 단일 배수 + 민감도로 대체.
- Bull/Bear 스프레드가 기존 `scenario_validator` 캘리브레이션(≤ 2x)을 넘으면 **경고**하되 관측치를 왜곡하지 않는다. 넘는다는 사실 자체가 peer 집합의 이질성 신호다.
- **LLM의 역할은 "어느 관측 집합을 쓸 것인가"의 선택과 서사뿐이다.** 예: "Bear에서는 커스텀 실리콘 잠식이 논점이므로 메모리/파운드리 peer를 제외한 부분집합" — 부분집합 *선택*은 허용, 숫자 *생성*은 금지.

**시나리오 확률 (P1 범주 ② — 명시적 가정):**

- 확률은 관측치가 아니다. **LLM 제안 허용**하되 `probability_rationale`(base rate + 조건부 분해)을 필수로 남기고, `assumptions` 영역에 **관측치와 분리 저장**한다.
- **민감도 필수**: 확률을 ±10%p 흔들었을 때 확률가중 가치의 변화를 산출물에 표시한다. 확률 하나로 결론이 뒤집히면 그 결론은 확률의 산물이지 분석의 산물이 아니다.
- 기존 검증(합계 100%, `scenario_validator`)은 유지.

**옵셔널리티 매출(L3), 영구성장률, DLOM도 동일하게 범주 ②** — 선언 + 분리 + 민감도.

### 2.7 방법론 라우팅 — L1 집중도 기준 (신규, CODEX 권고 채택)

"reportable segment가 2개니까 SOTP"는 형식적이다. NVDA는 Compute & Networking이 매출의 **~90%**다.

| 최대 L1 세그먼트 매출 비중 | Primary | 교차검증 |
|---|---|---|
| **≥ 90%** | consolidated **EV/EBITDA** 또는 **DCF** | L1 세그먼트 SOTP |
| **< 90%** | **L1 SOTP** 허용 | DCF / consolidated 배수 |

- 구현: `engine/method_selector.py` 라우팅 분기 추가. **밸류에이션 수식 변경이 아니라 선택 로직이며, 순수 함수 원칙(P4)에 부합한다.**
- 임계값 90%는 **범주 ②(선언된 가정)** 다. 상수로 박지 말고 설정값으로 두고 근거를 기록한다.

### 2.8 게이트 상태 머신

| 상태 | 콘솔 | 진단 Excel | 투자 Excel | DB publish | 주간 이메일 추천 | 블로그 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| `published` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `draft` | ✓ | ✓ | ✗ | ✓(draft) | ✗ | ✗ |
| `blocked` | ✓ | ✓ | ✗ | ✓(blocked+사유) | ✗ (**사유는 표시**) | ✗ |
| `failed` | ✓ | ✗ | ✗ | ✓(에러) | 건수만 | ✗ |

- **배치는 멈추지 않는다.** 회사별 상태.
- 주간 이메일에 성공/차단/실패 건수 + 차단 사유. 투자가능 0건도 정상 결과로 전달.
- `--force`는 차단을 지우지 않는다. `override:{reason,user,at}` 기록 후 `published(overridden)`. **scheduler는 force 불허.**

### 2.9 골든 검수 — **G-PRICE 폐기, G-REPRO로 대체**

v2의 `|괴리| ≤ 30%`는 acceptance gate에서 **삭제한다.** 시장가 맞추기를 유도하기 때문이다.

| 골든 | 대상 | 기준 |
|---|---|---|
| **G-INPUT** (P0) | 입력 정확성 | net_debt 구성요소 합계 일치 · material 필드 provenance 완비 · beta 경로가 §2.3대로 · 유효 peer N/freshness 충족 · gate 상태가 기대값 |
| **G-REPRO** (VS-1) | **결정론적 재현성** | 프로즌 입력 프로필(`tests/fixtures/`) → 엔진 → **정확히 같은 출력**. 시장가와 무관 |
| **D-GAP** (진단) | 시장 괴리 | **acceptance 아님.** 리포트에 기록만. 괴리가 크면 `reverse-DCF`로 "시장이 무엇을 가정하는가"를 출력 |

- **NVDA 자동 경로의 예상 결과: L1 2세그먼트 SOTP + TTM + 관측 배수 → 골든($175)보다 보수적일 것.**
  L3 옵셔널리티(EV 40,000 $M ≈ 주당 $1.6)와 부문 배분 프리미엄이 빠지므로 당연하다.
  **이 차이를 실패로 보지 않는다.** 차이의 출처를 D-GAP에 설명하는 것이 산출물이다.
- **골든 목표값 역튜닝 금지.**

### 2.10 분기 검산 계약

- **SEC**: `frame=CY...`만 믿지 않는다. `accession + form + start/end + fp`를 묶어 duration 검증.
  NVDA는 비달력 결산(1월)이라 `CY2026Q1` 매핑이 깨진다. 비교표 중복·YTD/standalone 혼재 dedup.
- **DART**: 분기값이 누적(YTD)인 경우가 많다. `Q4 = FY − 3Q누적`, `Q2/Q3 standalone = 당기누적 − 직전누적` 변환 후 검산.
- **허용오차**: 매출 `max(1%, 단위 반올림 materiality)`, 영업이익·현금흐름 `max(2%, materiality)`.
  오차율 단독 판정 금지 — 절대 materiality + 동일 accession/회계범위를 **동시에** 요구.
- **검산 실패 시 TTM 앵커를 생성하지 않는다.**

---

## 3. 작업 분할

### P0-0 — 데이터 계약 / 계보 (선행)

| 파일 | 내용 |
|---|---|
| `schemas/provenance.py` (신규) | `Source(value, source, accession, url, as_of, method)` |
| `schemas/models.py` | `net_debt_components: dict` · `normalization_version: str` · `assumption_sources: dict[str, Source]` · `segment_disclosure_level: Literal["L1","L2","L3","none"]` · **`declared_assumptions: dict`**(P1 범주 ② 전용, 관측치와 분리). 전부 Optional → 하위호환 |
| **`db/migrations_backtest.sql`** | `prediction_snapshots`에 `normalization_version`, `net_debt_components`(JSON), `segment_disclosure_level` 추가. **`db/migrations.sql`이 아니다** (CODEX 지적) |
| — | **과거 프로필/DB 행 재작성 금지.** 구버전 = `normalization_version: "legacy"`. 소급 변경은 look-ahead 훼손 |

### P0 — 정상화 (가격 안 봄)

> **LLM 의존도**: P0-4의 peer *후보 선정*에만 LLM을 쓴다. 프로필에 `peer_tickers`가 이미 있거나
> `scripts/fill_peers.py`로 티커를 직접 주면 **P0 전체가 LLM 없이 동작한다.** ("LLM 불필요"는 그 조건에서만 참)

| # | 파일 | 내용 |
|---|---|---|
| P0-1 순차입금 | `engine/normalize.py`(신규,pure) · `pipeline/edgar_parser.py:140-143` · `pipeline/dart_parser.py:152-185` | §2.1. `net_borr`는 legacy 보존, 엔진 소비값은 `net_debt_normalized` |
| P0-2 베타 | `engine/normalize.py` · `profile_generator.py:211-267` | §2.3. **상장/비상장 분리. 클램프·자동대체 금지** |
| P0-3 매크로 | `pipeline/macro_data.py` | §2.4. 각자 `as_of` + 허용 시차 |
| P0-4 peer 관측치 | `pipeline/peer_fetcher.py` · `ai/prompts.py:115,154` | §2.5. 죽은 Yahoo REST → `calibration/peer_fetcher.py`(yfinance) 위임 |
| P0-5 세그먼트 공시수준 탐지 | `pipeline/edgar_parser.py` · `engine/investability_gate.py` | **L1/L2/L3 판정만.** 값 추출은 VS-1. reportable segment가 있는데 `MAIN` 1개로 떨어지면 차단 |

**검수: G-INPUT.**

### 게이트 배포 연결 (P0 직후)

`engine/investability_gate.py` · `valuation_runner.py:525-549` · `profile_generator.py:1140-1158` · `scheduler/weekly_run.py` · `scheduler/delivery.py` → §2.8 상태 머신.

**검증 방법 수정 (CODEX 지적):** `cli.py --weekly --dry-run`은 **discovery만 하고 valuation을 건너뛴다** → 게이트 회귀를 검증하지 못한다. **프로즌 fixture 3~5개 회사로 실제 valuation을 태우는 E2E 테스트**(`tests/test_gate_e2e.py`)를 만든다. 일부 blocked, 일부 published인 배치가 **끝까지 진행되는지** 확인.

### VS-1 — 가격 수직 슬라이스 (US, NVDA)

**L1 기본. L2 보조. L3 없음.**

| # | 파일 | 내용 |
|---|---|---|
| VS-1a 분기/TTM | `pipeline/interim.py`(신규) · `edgar_parser.py` | §2.10 계약 |
| VS-1b **L1 세그먼트** | `edgar_parser.py` | XBRL `StatementBusinessSegmentsAxis` → reportable segment **매출 + 영업이익**. NVDA = 2개 |
| VS-1c **L2 보조** | `edgar_parser.py` | market-platform **매출만** → EV/Revenue 보조 레이어. **EBITDA 배수 금지** |
| VS-1d 관측 배수 적용 | `profile_generator.py` | P0-4 통계 → L1 부문 멀티플. placeholder 10.0 제거 |
| VS-1e **시나리오 배수 (결정론)** | `profile_generator.py` · `engine/peer_analysis.py` | §2.6: Base=median · Bull=Q3 · Bear=Q1, **관측 스냅샷에서 직접 산출**. **`ai/prompts.py`에서 `segment_multiples` 생성 경로를 만들지 않는다** — v3 초안의 P1 위반 수정. 필드는 이미 있음(`ScenarioParams:312`) |
| VS-1f 방법론 라우팅 | `engine/method_selector.py` | §2.7 L1 집중도 ≥90% → consolidated primary, SOTP는 교차검증 |

**검수: G-REPRO + D-GAP 기록.** 가격 수렴은 acceptance가 아니다.

### P1.5 — 가이던스 앵커

회사 가이던스(NVDA Q2 $91B)는 1차 출처. 컨센서스(P3)보다 먼저. **actual TTM에 섞지 않는다.**

### P2

| # | 내용 |
|---|---|
| P2-1 | Evidence ledger 완성 → `_verified_data.md` 자동 렌더링 |
| P2-2 | 순이익 정상화 (지분증권 평가손익 제거. TTM 기준 GAAP NI의 **10.0%**). P/E 교차검증은 정상화 이익만 |
| P2-3 | buyback → 희석주식수 전망. **$80B는 승인이지 매입이 아니다.** 승인잔액·실제 분기매입·평균매입가 + SBC 상쇄 |
| P2-4 | L3 옵셔널리티: LLM은 후보·서사만. **가치 숫자 생성 금지.** 기본 0 + 수동 검토, 또는 reverse-DCF 진단 |
| P2-5 | KR 확장 — DART 누적분기 변환(§2.10) |

### P3 — 컨센서스 (보류)

소스 확보 후 결정. 컨센서스와 실제/가이던스를 혼합하지 않는다.

---

## 4. 실행 순서

```
P0-0 계약/골든 확정
  → P0 정상화 (G-INPUT)
  → 게이트 배포 연결 (E2E fixture 회귀)
  → VS-1 US/NVDA, L1 기본 (G-REPRO + D-GAP)
  → P1.5 가이던스 → P2 (KR · evidence · 순이익 · buyback · L3)
```

---

## 5. 비목표

- `engine/` 수식 변경. 엔진은 틀리지 않았다.
- `engine/quality.py` trading 배수 순환성 — 2026-07-10 완료. 재작업 금지.
- `valuation-results/2026-07-10-nvda-deep-dive/` 수정 — 읽기 전용.
- 과거 프로필/DB 일괄 재작성.
- **$175 재현.** 골든의 부문 EBITDA는 균등배분 산물이다. 재현 대상이 아니라 **비교 대상**이다.
- **가격 수렴을 acceptance 기준으로 삼는 모든 형태.**

---

## 6. 검증

```bash
# G-INPUT (P0)
python -m pytest tests/test_normalize.py tests/test_investability_gate.py -q
python cli.py --company NVDA --excel
#  확인: net_debt<0 · provenance 완비 · beta 경로 기록 · segment_disclosure_level=L1 · gate 상태
#  가격($91~109)은 검수 대상 아님

# 게이트 E2E (--weekly --dry-run 아님! valuation을 실제로 태움)
python -m pytest tests/test_gate_e2e.py -q

# G-REPRO (VS-1)
python -m pytest tests/test_vs1_repro.py -q   # 프로즌 프로필 → 결정론적 동일 출력

# 회귀
python -m pytest tests/ -q
```

신규 테스트:
- `tests/test_normalize.py` — 순차입금 구성요소·태그 중복, Blume **병기**(자동대체 없음 확인), TTM 파생+검산
- `tests/test_interim.py` — US **비달력 결산**(NVDA 1월), KR **누적분기 변환**, restatement, accession dedup
- `tests/test_segments.py` — **L1/L2/L3 판정**, L2에 EBITDA 배수 적용 시 **거부**되는지
- `tests/test_gate_e2e.py` — 상태 머신 × 소비자 행렬, **배치 일부 차단 시 나머지 진행**
- `tests/test_beta_policy.py` — 상장/비상장 분기, 관측창 부재 시 차단, 범위 이탈은 **차단하지 않음** (→ 실제 착지: `tests/test_beta.py`)
- `tests/test_scenario_multiples.py` — Base/Bull/Bear = median/Q3/Q1 결정론, **N<4일 때 시나리오 배수 미생성**, LLM 경로 부재 확인
- `tests/test_method_selector.py` — L1 집중도 ≥90% → consolidated primary (기존 파일 확장)
- `tests/fixtures/nvda_q1fy27.json` — SEC 8-K 프로즌 픽스처

**골든 픽스처 출처**: NVIDIA FY2026 10-K
`https://www.sec.gov/Archives/edgar/data/1045810/000104581026000021/nvda-20260125.htm`
(reportable segment = Compute & Networking / Graphics 확인 근거)
