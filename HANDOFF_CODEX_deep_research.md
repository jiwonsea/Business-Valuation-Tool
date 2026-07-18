# CODEX 핸드오프 — `PLAN_deep_research.md` 평가

업무: **설계 평가만. 구현 금지.** 코드를 고치지 말고, PLAN의 타당성·누락·리스크를 판정한다.

프로젝트: `F:\dev\Portfolio\business-valuation-tool`
평가 대상: `PLAN_deep_research.md` (2026-07-11 작성)
작성자 주장의 근거 파일: 아래 §1 전부 실제 확인함. 재확인은 CODEX 판단에 맡김.

---

## 0. 배경 (30초)

같은 날 같은 도구로 NVDA를 평가했는데 자동 경로는 **주당 $63(괴리 −70%)**, 사람이 한 심층 리서치는
**$175(−13.5%)** 및 **$207(+2.3%)**. 엔진은 스스로 `wacc_overestimated`를 진단했다.
**엔진이 아니라 입력이 틀렸다**는 것이 PLAN의 전제다. PLAN은 입력 계층(Research → Normalize → Anchor)을
신설해 이 격차를 구조적으로 없애자고 제안한다.

증거:
- 자동 실행 로그: 이 세션 콘솔 (요약: `[WACC] βL=2.211, WACC=16.39%`, `괴리율 -70.1%`, `Primary reason: wacc_overestimated`)
- 심층 리서치: `valuation-results/2026-07-10-nvda-deep-dive/` — `_run_ttm.txt`, `nvda_ttm.yaml`, `_verified_data.md`, `nvda_deep_dive_2026-07-10.md`

---

## 1. 검증해야 할 사실 주장 (PLAN §1)

각 항목에 대해 **확인 / 반증 / 부분수정** 중 하나로 판정할 것.

| # | 주장 | 확인 위치 |
|---|---|---|
| R1 | 순차입금이 `gross_borr − 현금성자산`이라 시장성 채무증권($37B)을 누락. NVDA 실제 순현금 −41,865를 +435로 뒤집음 | `pipeline/edgar_parser.py:142`, `pipeline/dart_parser.py:185`, `pipeline/profile_generator.py:330,374`. 대조: `nvda_ttm.yaml:97,204`, `_verified_data.md` "순현금 = 50,335 − 8,470" |
| R2 | `rf`·`erp`가 하드코딩 상수(시장 데이터 아님) | `pipeline/profile_generator.py:200-201` |
| R3 | raw yfinance beta를 조정 없이 unlever → βL 2.21(적정 0.3~2.0 이탈). `quality.py`는 경고만 하고 차단 안 함 | `profile_generator.py::_estimate_wacc_params`, `engine/quality.py` |
| R4 | 연간 실적만 수집. 분기/TTM 파싱 부재 → 앵커가 최대 6개월 stale | `pipeline/edgar_parser.py::_extract_annual` (분기 추출 함수 없음) |
| R5 | 세그먼트 미추출 → `MAIN` 1개 → 방법론이 DCF로 강제 라우팅 | `profile_generator.py` draft 출력, `profiles/nvda.yaml:21-24` |
| R6 | placeholder 멀티플 `10.0`이 아무 차단 없이 밸류에이션에 투입 | `engine/investability_gate.py:224,242` (`placeholder_multiples` 필드는 있으나 하드 게이트 아님) |
| R7 | peer `ev_ebitda`를 LLM이 생성 → 환각. 심층 리서치 프로필에도 잔존: **롯데칩스(실존하지 않음)**, **Xilinx(2022 피인수, 독립 멀티플 없음)**, **Intel Arc Graphics(제품명)**, 멀티플 출처 "2024 consensus"(2년 stale) | `ai/analyst.py::recommend_peers`, `ai/prompts.py:115,154`, `nvda_ttm.yaml:207-303` |
| R8 | `pipeline/peer_fetcher.py`는 (a) Yahoo quoteSummary v10 REST를 쓰는데 crumb 인증 요구로 **전 종목 빈 값**, (b) **프로덕션 호출부가 없음**(테스트 전용) | `pipeline/peer_fetcher.py`, `pipeline/yahoo_finance.py::get_quote_summary`. 실측: 이 세션에서 AMD/AVGO/QCOM/MRVL/TSM/MU/INTC 7종 전부 skip. 대체 경로 `calibration/peer_fetcher.py`(yfinance) 존재 |
| R9 | 순이익 정상화 부재 → TTM GAAP NI의 27%가 지분증권 평가이익. P/E 교차검증 오염 | `_verified_data.md` "GAAP−비GAAP 갭의 주인: 지분증권 순평가이익 15,936" |
| R10 | 자동 산출물에 1차 출처 추적 없음 | `_verified_data.md`에 대응하는 코드 경로 부재 |

**특히 R7은 PLAN의 설계 원칙 P1("LLM은 판단만, 숫자는 금지")의 근거다.**
이 주장이 반증되면 P0-5의 정당성이 흔들린다. 우선 확인할 것.

---

## 2. 평가 질문 (답을 요구함)

### Q1. P0 스코프가 맞는가

PLAN은 P0(순차입금·베타·rf·게이트·peer 관측치)만으로 NVDA 괴리가 **−70% → 30% 이내**로 들어온다고
주장한다. **이 수치 주장을 검산하라.**
- 순차입금 −41,865, βL 1.5 수준, WACC ~11%를 현재 엔진에 넣었을 때 나오는 주당가치를 추정.
- P0만으로 부족하다면(세그먼트가 MAIN 1개면 여전히 DCF_PRIMARY 라우팅), **P0에 세그먼트 추출(P2-1)을
  끌어와야 하는지** 판단. 이것이 이 핸드오프의 **가장 중요한 질문**이다.

### Q2. 순차입금 정의 변경의 폭발 반경

`net_debt` 정의를 바꾸면 과거 모든 프로필·백테스트와 불연속이 생긴다.
- `backtest/`, `calibration/`, `db/` 에 저장된 과거 밸류에이션의 재계산이 필요한가?
- PLAN의 완화책(`net_borr` 유지 + `net_debt_normalized` 병기)이 충분한가, 아니면 마이그레이션이 필요한가?
- **시장성 지분증권 제외**(NVDA $73.6B, 주당 +$3.0 포기)라는 보수적 선택에 동의하는가? 순환거래
  익스포저(`_verified_data.md`: 비시장성 증권 1분기 +$21.1B)를 감안하면 타당한가?

### Q3. 베타 처리 방식

PLAN은 Blume 조정 후 범위 이탈 시 **산업 평균으로 대체**를 제안하고, 산업 베타 테이블이 없다는 리스크를
인정하며 **peer βL 중앙값 unlever**를 대안으로 든다.
- 어느 쪽이 옳은가? peer 기반이면 P0-5(peer 관측치)에 **순환 의존**이 생기는데 순서를 어떻게 잡을 것인가?
- 범위 이탈 시 "대체"가 맞는가, 아니면 "차단"(밸류에이션 거부)이 맞는가? NVDA raw beta 2.2는 실제
  변동성의 반영이기도 하다 — 조용히 1.45로 바꾸는 것이 **또 다른 형태의 조용한 실패**는 아닌가?

### Q4. 하드 게이트가 주간 파이프라인을 죽이지 않는가

P0-4는 placeholder 멀티플·βL 이탈·stale 앵커에서 **Excel/DB 저장을 차단**한다.
- `scheduler/weekly_run.py`가 10개 기업을 도는데, 게이트가 절반을 막으면 주간 이메일이 빈다.
- 차단 vs 경고+플래그 저장 중 무엇이 옳은가? 저장하되 `investability: blocked` 플래그를 달고
  이메일에서 제외하는 절충은?

### Q5. TTM 앵커(P1)의 검산 규칙

PLAN은 "분기 합 = 연간이 안 맞으면 TTM 앵커를 생성하지 않는다"고 한다.
- SEC XBRL 분기 태깅의 실제 신뢰도는? (`companyconcept` frame `CY2026Q1` 커버리지)
- 허용 오차는 몇 %인가? 0%는 비현실적, 5%는 무의미할 수 있다.
- KR DART 분기보고서에서 동일 규칙이 성립하는가?

### Q6. 누락된 것

PLAN에 **없는데 있어야 하는 것**을 지적하라. 후보:
- 옵셔널리티 세그먼트(`SEG_OPT*`, `method: ev_revenue`) 자동 생성 — 심층 리서치는 자율주행·군사AI를
  수동으로 넣었다. 자동화 가능한가, 아니면 영원히 사람 몫인가?
- 시나리오별 `segment_multiples` — 심층 리서치의 핵심 장치인데 PLAN이 다루지 않음.
- 가이던스(Q2 $91B) 반영 경로.
- 자사주매입($80B 승인) → 주식수 감소 → 주당가치 상방.

### Q7. 순서

PLAN은 P0 → 골든 테스트 → P1을 권고한다. 동의하는가? 다른 순서가 낫다면 근거와 함께 제시.

---

## 3. 산출물 형식

`CODEX_EVAL_deep_research.md`로 저장:

1. **사실 주장 판정표** — R1~R10 각각 `확인 / 반증 / 부분수정` + 한 줄 근거(파일:라인)
2. **Q1~Q7 답변** — 각 5줄 이내. Q1은 수치 검산 포함 필수
3. **PLAN 수정 지시** — 추가/삭제/재배치할 작업 항목. P0 스코프 확정
4. **블로커** — 구현 착수 전에 반드시 해결해야 할 것 (있다면)
5. **판정** — `구현 착수 가능` / `수정 후 착수` / `재설계 필요` 중 하나

---

## 4. 제약

- **코드 수정 금지.** 이 핸드오프는 평가 요청이다. 구현은 평가 통과 후 별도 세션.
- `valuation-results/2026-07-10-nvda-deep-dive/`는 **읽기 전용 골든 픽스처**. 수정·삭제 금지.
- 재작업 금지 항목: `engine/quality.py`의 trading 배수 순환성 제외 — 2026-07-10 CODEX 평가에서 이미
  반영 완료(`_run_ttm.txt:90`에서 동작 확인). 다시 건드리지 말 것.
- 작업 트리에 **미커밋 변경이 대량으로 있다**(CLAUDE.md § Session Safety). `git checkout --`,
  `git restore`, `git reset --hard` 절대 금지.
- 이 세션에서 이미 들어간 미커밋 변경(평가 시 참고):
  - `pipeline/reconciliation.py` — market_cap 단위 버그 수정(1e6 rebase). 이게 없으면 US/KR 자동
    프로필이 전부 하드 블록됨
  - `output/sheets/raw_data.py`, `output/sheets/_guide.py` — Excel Raw Data 시트 + 시트별 가이드
  - `output/sheets/peers.py`, `engine/peer_analysis.py`, `schemas/models.py` — 적용 멀티플 선정 근거 + 역산 교차검증
  - `scripts/fill_peers.py` — LLM 없이 yfinance로 peer 멀티플 채우는 스크립트
