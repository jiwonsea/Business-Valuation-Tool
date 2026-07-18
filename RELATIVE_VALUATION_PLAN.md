# Relative Valuation Layer — 구현 계획 (PER/PBR/PEG/PEGY + Justified Multiples)

> 상태(업데이트): **전 Tier 구현 + 파이프라인 배선 + 콘솔 출력 완료.** engine/relative_metrics.py, schemas(RelativeValuation), valuation_runner(_build_relative_valuation 배선), output/console_report(진단 패널) 모두 반영. 테스트 통과(relative 21 + gate 12). 남은 선택 확장: yfinance earningsGrowth/dividendYield 캡처(현재는 model EBITDA CAGR 폴백).
> 작성 기준 커밋: 세션 시작 시점. 실행 전 `git log --oneline -15`로 backlog 재검증할 것 (CLAUDE.md 규칙).

## 0. 설계 원칙 (왜 이렇게 넣는가)

이 툴은 내재가치(DCF/SOTP/rNPV/DDM/RIM/NAV) 엔진이고, CLAUDE.md 철학은
"reverse-DCF로 시장 가정을 해독한다"(Damodaran)이다. 따라서 상대가치 지표는
**새 primary method가 아니라 진단·정합성 레이어**로 들어간다.

- 라이브 주가에서 역산하는 진단용 배수(P/E, P/B, EV/EBITDA, EV/Sales, 배당수익률)
- PEG/PEGY는 성장주에만 의미. 금융·시클리컬·저성장 구간에서는 숫자 대신 `NA`/`CAUTION`.
- **Justified multiple**(정당배수)이 이 코드베이스의 핵심 추가값 — ke·g·ROE·payout이 이미
  전부 있어 재사용 가능하고, reverse-DCF 철학과 정확히 일치.

단위 규약: growth·ROE·ke·배당수익률은 **퍼센트**(예: 12.5). 금액 지표는 모델 display unit.

---

## 1. Tier 1 — 현재가 기준 진단 배수 (효용 高 / 난이도 低)  ✅ 코어 완료

`engine/relative_metrics.py`:
- `trailing_pe(price, eps)`, `forward_pe(price, forward_eps)`
- `price_to_book(price, bvps)` — 자본잠식(BVPS<0) → NA
- `ev_ebitda(market_cap, net_debt, ebitda)`, `ev_sales(market_cap, net_debt, revenue)`
- `dividend_yield(dps, price)` — 무배당 0.0은 OK(정보성)

피어 비교는 기존 `engine/peer_analysis.calc_peer_stats`(median/IQR)를 재사용 → "피어 대비 싸다/비싸다".

## 2. Tier 3 — Justified Multiples + 판정 (분석가치 最高)  ✅ 코어 완료

- `justified_pe(payout%, g%, ke%)` = payout·(1+g)/(ke−g), ke−g<0.5% → NA
- `justified_pb(roe%, g%, ke%)` = (ROE−g)/(ke−g) — RIM과 자연스럽게 페어링
- `multiple_verdict(name, actual, justified, band=0.15)` → 저평가/적정/고평가/판단불가 + gap%

입력 소스: ke=`engine/wacc.py`, g=`engine/growth.py`, ROE=`valuation_runner.py`(이미 계산),
payout=`RIMParams.payout_ratio` 또는 배당/순이익.

## 3. Tier 2 — PEG / PEGY (오해 소지 큼 → 가드레일 필수)  ✅ 코어 완료

- `peg(pe, growth%, *, is_financial, is_cyclical, growth_source, min_growth_pct=2.0)`
- `pegy(pe, growth%, dividend_yield%, ...)` — 분모 = 성장률+배당수익률 (KR 배당주 적합)
- 가드레일: 이익≤0 → NA / 성장률≤2% → NA / 금융업 → CAUTION(PBR-ROE 권장) /
  시클리컬 → CAUTION(through-cycle). 성장률 출처를 note에 명시.

## 4. 섹터별 지표 매핑 (method_selector 패턴 준용)

| 유형 | 우선 지표 | 회피/주의 |
|------|-----------|-----------|
| 금융 | P/B + ROE (RIM) | PEG(CAUTION) |
| 성장/테크 | P/E, PEG, EV/Sales | — |
| 시클리컬(auto/steel/semi 등) | through-cycle EV/EBITDA | trailing PER, PEG |
| 배당주 | PEGY, 배당수익률 | 단순 PEG |

`engine/distress.py:_CYCLICAL_KEYWORDS`를 재사용해 `is_cyclical` 판정.

---

## ✅ 이번 세션에서 완료된 것

- `engine/relative_metrics.py` — 순수함수 (Tier 1·2·3 전부). IO/pydantic 의존 없음.
- `tests/test_relative_metrics.py` — 21 테스트 **통과**.

## ⏳ 남은 통합 배선 (라이브 데이터 필요 → 아래 실행 프롬프트로 위임)

이 부분은 yfinance/DART 라이브 응답과 실제 프로파일로 검증해야 안전해서 코어와 분리한다.

1. **스키마** `schemas/models.py`
   - `RelativeMetric`/`MultipleVerdict`를 담을 `RelativeValuation(BaseModel)` 추가 (신규 필드 전부 Optional+default).
   - `ValuationResult`에 `relative_valuation: Optional[RelativeValuation] = None` 슬롯 추가.
2. **데이터 수집** `pipeline/yfinance_fetcher.py` / `pipeline/yahoo_finance.py`
   - `info.get`에서 `trailingEps`, `forwardEps`, `dividendYield`, `priceToBook`,
     `earningsGrowth`(또는 `earningsQuarterlyGrowth`)를 캡처. (현재 `trailingPE`/`forwardPE`만 수집)
   - 애널리스트 이익성장 컨센서스가 없으면 모델 EBITDA CAGR(`growth.calc_ebitda_growth`)로 폴백하고
     `growth_source` 문자열을 세팅.
3. **런너 배선** `valuation_runner.py`
   - 방법별 dispatch 후 공통 지점에서 `relative_metrics.*` 호출 → `ValuationResult.relative_valuation` 채움.
   - `is_financial`은 primary_method∈{ddm,rim} 또는 industry 키워드로, `is_cyclical`은 distress 키워드로.
   - **CLAUDE.md 이중경로 규칙**: `orchestrator.run_from_profile` **와** `profile_generator.auto_analyze`
     양쪽에 배선(한쪽만 하면 weekly 파이프라인에서 누락).
4. **출력** `output/console_report.py` + `output/sheets/` (Excel multiples 시트)
   - 진단 배수 패널 + 피어 median 대비 + justified 판정 표. NA/CAUTION은 숫자 대신 사유 표기.
5. **테스트**
   - 배선 후 `pytest tests/` 전체. `profiles/`는 AI가 덮어쓰므로 하드코딩 픽스처는 `tests/fixtures/`에 둘 것.
6. **주의(gotcha)**
   - `get_market_cap()`는 raw 통화단위(백만 아님) 반환 — EV 계산 시 스케일 일치 확인.
   - `.env` 없으면 라이브 수집 무음 실패 — 수집 필드는 전부 Optional 폴백 유지.

---

## 실행 프롬프트 (다음 세션/에이전트에 그대로 붙여넣기용)

```
목표: engine/relative_metrics.py(이미 구현·테스트 완료)를 파이프라인에 배선해
상대가치 진단 레이어를 리포트/Excel에 노출한다. 새 primary method는 만들지 말 것 —
진단·정합성 레이어로만 통합.

착수 전: git log --oneline -15 및 관련 파일 확인(CLAUDE.md 세션시작 backlog 규칙).

1) schemas/models.py: RelativeValuation(BaseModel) 추가(모든 필드 Optional+default),
   ValuationResult.relative_valuation Optional 슬롯 추가.
2) pipeline/yfinance_fetcher.py & yahoo_finance.py: trailingEps/forwardEps/dividendYield/
   priceToBook/earningsGrowth 캡처. 이익성장 컨센서스 없으면 growth.calc_ebitda_growth 폴백,
   growth_source 세팅.
3) valuation_runner.py: dispatch 후 공통 지점에서 relative_metrics 호출→result 채움.
   is_financial=primary∈{ddm,rim}/industry, is_cyclical=distress._CYCLICAL_KEYWORDS.
   orchestrator.run_from_profile와 profile_generator.auto_analyze 양쪽 모두 배선.
4) output/console_report.py + output/sheets(Excel multiples 시트): 배수 패널 + 피어 median 대비
   + justified 판정 표. NA/CAUTION은 사유 표기.
5) pytest tests/ 전체 통과 확인. 신규 픽스처는 tests/fixtures/에.

검증: 대표 프로파일 2종(예: 성장주 US 티커 + KR 금융 kb_financial)으로
python cli.py --profile ... 실행해 진단 패널이 뜨고 금융은 PEG가 CAUTION,
저성장은 NA로 표기되는지 확인.
```
