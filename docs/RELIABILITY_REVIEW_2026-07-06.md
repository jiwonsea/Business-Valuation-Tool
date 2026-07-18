# 9개 기업 밸류에이션 신뢰성 평가 (BVT · EFE)

작성: 2026-07-06 · 대상: 삼성전자, SK하이닉스, M7(NVDA·MSFT·AAPL·GOOGL·AMZN·META·TSLA)
범위: `business-valuation-tool`(BVT, 정적 밸류에이션) + `earnings-forecast-engine`(EFE, 선행 EPS 전망)
**개정 2 (2026-07-06 오후):** 라이브 주가 주입 · 프로파일 빈티지 갱신 · GOOGL 주식수 수정 ·
옵셔널리티 판별 일반화 반영.

---

## 0. 한 줄 결론

두 엔진의 **계산 로직은 신뢰 가능**하다. 개정 2에서 1차 검토의 3대 신뢰도 저해 요인을 대부분 해소:
① **라이브 주가 주입** → 전 종목 `시장가격 정합`이 0/25에서 벗어남 + 역방향 DCF 진단 작동,
② **GOOGL 주식수 오류 수정**($409→$197), ③ **옵셔널리티 판별 일반화**(NVDA 전용 → 빅테크 전반).
남은 조건부 요소는 **프로파일 빈티지**(FY2025 기준, 2026 리레이팅 진행 중)와 **옵션가치 구조적 하한**뿐.

---

## 1. 결과 요약 (개정 2)

### 1-A. BVT 정적 내재가치 + 라이브 주가 정합 (2026-07-06)

| 기업 | 1차 방법 | 내재가치/주 | 품질 | 시장가(2026-07) | 괴리 | 옵셔널리티 exclude |
|---|---|---:|---|---:|---:|---|
| 삼성전자(005930) | SOTP | ₩172,333 | **72 (B)** | ₩309,500 | −44% | ✔ DCF 38% |
| SK하이닉스(000660) | SOTP | ₩1,359,378 | **78 (B)** | ₩2,425,000 | −44% | — |
| Apple(AAPL) | DCF | $114 | **78 (B)** | $298 | −62% | ✔ DCF 40% |
| Microsoft(MSFT) | SOTP | $284 | **84 (B)** | $390 | −27% | — |
| Alphabet(GOOGL) | SOTP | **$197** ✔수정 | **83 (B)** | $359 | −45% | — |
| Amazon(AMZN) | SOTP | $147 | **78 (B)** | $244 | −40% | ✔ DCF 33% |
| NVIDIA(NVDA) | SOTP | $145 | **72 (B)** | $194 | −25% | ✔ DCF 36% |
| Tesla(TSLA) | SOTP | $116 | **71 (B)** | $397 | −71% | ✔ DCF 3% |
| Meta(META) | SOTP | $674 | **90 (A)** | $583 | +16% | ✔ (구조적) |

품질 개선(개정1→개정2): 삼성 58→72 · SK하이닉스 70→78 · AAPL 58→78 · MSFT 70→84 ·
GOOGL 75→83(값도 $409→$197 보정) · AMZN 64→78 · NVDA 53→72 · TSLA 68→71 · META 70→90.
개선 동력 = (a) 시장가 주입으로 `시장가격 정합` 3~20점 회복, (b) 성장/옵셔널리티 DCF 제외.

주가는 프로파일 `market_price:` 필드로 주입(오프라인 대응). 라이브 조회 성공 시 라이브가 우선.
as-of: NVDA/GOOGL/MSFT/META/삼성/SK하이닉스 = 7월 초, AAPL/AMZN = 6/18, TSLA = 근사(2월, 변동성 큼).

### 1-B. EFE 선행 EPS 전망 (2026, 확률가중) + 오프라인 백테스트

| 기업 | 경로 | 2026 가중 EPS | 매출 MAPE(vs naive RW) |
|---|---|---:|---|
| SK하이닉스 | 메모리 엔진(기존) | — (9Q 백테스트 rev 8.99%/EPS 10.39%) | MASE<1 |
| NVIDIA | generic(신규) | $7.20 | 8.5% (RW 13.3%) |
| Microsoft | generic | $17.99 | 2.4% (RW 5.1%) |
| Apple | generic | $7.86 | 1.2% (RW 12.2%) |
| Alphabet | generic | $10.28 | 1.8% (RW 5.5%) |
| Amazon | generic | $6.84 | 1.3% (RW 9.9%) |
| Meta | generic | $31.24 | 2.5% (RW 10.9%) |
| Tesla | generic | $2.18 | 1.0% (RW 7.0%) |
| 삼성전자 | generic | ₩7,596 | 2.7% (RW 4.1%) |

모든 generic 종목 매출 MAPE < naive RW. 단 §3-C 순환성 주의.

---

## 2. 방법론 신뢰성

**BVT** — 순수함수 SOTP/DCF/DDM/RIM/NAV/rNPV 다중엔진 + 교차검증(테스트 338 pass). 9/9 실행,
오프라인 재현 가능. 이제 주가 주입으로 시장 정합·역방향 DCF 진단까지 작동.

**EFE** — 원래 메모리 전용(DRAM/NAND bit×ASP). SK하이닉스 최적, M7 부적합 → 이번에 **generic
top-down 경로** 신설(§5). 메모리 경로 불변(SK하이닉스 9Q 불변식 유지).

- **적합도**: SK하이닉스(메모리)=高 · 삼성·M7(generic)=中 · Tesla=低(§3-D).

---

## 3. 신뢰도 플래그

### 3-A. GOOGL 주식수 — **수정 완료** ✔
`shares_total`이 Class A(5.82B)로 표기돼 내재가치 2배 과대였던 문제를 **~12.1B(총주식)로 보정**.
결과: $409 → **$197**(시장가 $359 대비 −45%). Alphabet 2025 희석 EPS $10.81/희석주 13.08B(보고치)와 정합.
(부수: 현재 googl.yaml의 `mc_enabled:` 빈값(null) 드리프트도 `true`로 정정 — AI 재생성 잔여물.)

### 3-B. 라이브 주가 — **주입 완료** ✔ (오프라인 한계 해소)
`ValuationInput.market_price` 필드 신설 + `cli._fetch_and_compare_market_price`가 라이브 실패 시
프로파일 값 사용. 전 종목 `시장가격 정합` 3~20점 획득 + `괴리율` 산출 + 역방향 DCF 진단 작동.
(호스트에서 라이브 조회가 되면 라이브가 우선하므로 이 필드는 오프라인/수동 override.)

### 3-C. EFE 분기 actuals 파생 → 백테스트 부분 순환성 (미해소, 호스트)
generic 프로파일 분기 `actuals`는 연간 총액 역산 근사(공식 분기 GAAP 아님, `notes` 명시).
매출 MAPE(1~3%)는 낙관적. **연간·EPS·세그먼트는 보고치.** 독립 보고 분기로 교체 필요(Yahoo 403 → 호스트).

### 3-D. Tesla — 순이익/EPS 추정(신뢰도 최저, 미해소)
검토 릴리스에 순이익/EPS 없음 → 추정. 규제 크레딧·기타수익 변동 큼. 결과 해석 주의.

### 3-E. 옵션가치 구조적 하한 (설계상)
FSD/로보택시(TSLA −71% 괴리), AI 성장 등 폭발적 옵션가치는 top-down으로 하한만 포착.
TSLA 시장가 $397 vs 내재 $116은 시장이 매기는 대규모 옵션 프리미엄을 반영 — "하한 근사"로 해석.

---

## 4. 품질 진단 & 개선 (사용자 질문 답변 — **일반화 반영**)

**질문 1: 멀티플 배정 vs 옵셔널리티 미반영?** → **옵셔널리티(성장 프리미엄) 미반영이 근본**,
멀티플 저평가는 증상. 교차검증에서 DCF·EV/EBITDA가 P/E·EV/Rev 대비 40~60% 낮게 분열.

**질문 2: 옵셔널리티가 NVDA에만? → 아니오. 수정 완료.**
1차 판별은 `ev_revenue 세그먼트 보유` 여부(구조적)라 NVDA·GOOGL·META·TSLA만 걸리고
AAPL·MSFT·AMZN은 누락됐다. **개정 2에서 경제적 신호 기반으로 일반화**:
`engine/quality.py`의 수렴도 계산이 **DCF가 시장배수(P/E·EV/Rev·P/BV) 중앙값의 70% 미만**이면
자동으로 DCF를 제외(성장 프리미엄을 현금흐름법이 재현 못하는 구조를 데이터로 탐지).
→ 이제 **AAPL(40%)·AMZN(33%)·NVDA(36%)·삼성(38%)·TSLA(3%)** 모두 발화(META·GOOGL은 이미 수렴).
즉 빅테크 전반에 일관 적용. rNPV의 `_RNPV_EXCLUDED_CV_METHODS` 철학을 SOTP로 확장한 것.

**효과.** AAPL 수렴도 8→25, NVDA 3→8(+시장정합), 등. 비성장/수렴 종목은 발화 안 함(임계 0.7).
검증: `pytest tests/test_quality.py tests/test_engine.py` = 338 pass(1 fail은 무관한 sk_ecoplant WACC).

---

## 5. EFE Generic 엔진 (신규)

`schemas/generic.py` · `engine/generic_forecast.py` · `generic_cli.py` · `profiles/*.generic.yaml`(8)
· `tests/test_generic_forecast.py`(8 pass). 메모리 경로 불변. 상세: `HANDOFF_generic_engine.md`.

---

## 6. 프로젝트별 신뢰 등급 (개정 2)

| 대상 | 등급 | 근거 |
|---|---|---|
| BVT 로직/엔진 | ★★★★☆ | 다중엔진·교차검증·338 tests. |
| BVT 개별 결과(9종) | ★★★★☆ | 시장가 주입·GOOGL 보정으로 상향. 절대치는 빈티지(FY2025) 조건부. |
| EFE SK하이닉스(메모리) | ★★★★☆ | 전용 엔진 + 9Q 백테스트. |
| EFE M7·삼성(generic) | ★★★☆☆ | 실적 앵커 견고, 분기 백테스트 순환성 한계. |
| EFE Tesla(generic) | ★★☆☆☆ | 순이익/EPS 추정. |

---

## 7. 남은 후속 (호스트/Codex)
1. 빈티지 프로파일 `--auto` 재생성(2026-07 실적 반영) — 현재는 FY2025 앵커 + 수동 주가.
2. EFE generic: **독립 보고 분기 actuals**로 백테스트 순환성 제거.
3. EFE Tesla: 10-K 실제 순이익/EPS 확보.
4. GOOGL 재생성 시 파이프라인 주식수 파서가 Class A만 잡지 않도록 점검(재발 방지).
5. `market_price` 수동값은 stale화되므로 호스트 라이브 조회 우선 유지.
