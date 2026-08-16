# Data Sources

## Yahoo Finance (yfinance)

Python 라이브러리 `yfinance` 사용. ticker 형식: `000660.KS` (KOSPI), `8035.T` (TSE).

### 사용 필드

| `Ticker.X` | 용도 | 본 repo 매핑 |
|------------|------|--------------|
| `earnings_estimate` | 분기·연간 EPS 컨센 | `ConsensusRecord.eps_estimate_*` |
| `revenue_estimate` | 분기·연간 매출 컨센 | `ConsensusRecord.revenue_estimate_*` |
| `earnings_history` | 직전 4Q actual·estimate·surprise | `ConsensusRecord.history` |
| `info` | shares outstanding, market cap, currency | `SharesOutstanding`, KPI cards |
| `quarterly_financials` | 분기 P&L (백업 — DART 우선) | optional cross-check |

### Caveats

- `.KS` 한국 종목은 일부 필드가 sparse. 없는 값은 명시적 `None`.
- 컨센은 매일 갱신되지만 broker별 가중 방식 불투명. 학술용은 한국 broker 리포트(FnGuide·KISLINE) 권장 — 본 repo는 P1.
- Rate limit 명시되지 않으나 yfinance 자체가 unofficial scraper. 캐시 디렉토리 (`reports/.cache/`) 적극 활용.

## DART OpenAPI

[https://opendart.fss.or.kr/](https://opendart.fss.or.kr/) 가입 후 API 키 발급. `.env` 에 `DART_API_KEY=...`.

### 사용 엔드포인트

| 엔드포인트 | 용도 |
|-----------|------|
| `fnlttSinglAcntAll.json` | 단일회사 전체 재무제표 (분기·반기·연간) |
| `list.json` | 공시 목록 (보고서명 필터링) |
| `company.json` | 회사 정보 (corp_code 조회) |

### corp_code 캐시

매번 조회 대신 종목별 corp_code를 캐싱:

| 회사 | corp_code |
|------|-----------|
| SK하이닉스 | `00164779` |
| 삼성전자 | `00126380` |

신규 종목 추가 시 `dart/company.json?stock_code=000000` 으로 조회 후 본 표에 추가.

### Reprt code

| 보고서 | reprt_code |
|--------|-----------|
| 1분기 | `11013` |
| 반기 | `11012` |
| 3분기 | `11014` |
| 사업 (연간) | `11011` |

### Rate limit

분당 1,000회. `httpx` retry/backoff 적용 (`pipeline/dart_fetcher.py`).

## Profile YAML (수동 입력)

`profiles/{company}.yaml` 의 `assumptions:` 섹션이 본인이 직접 작성하는 가정 수치. 출처는 같은 파일 `sources:` 섹션에 기록.

권장 소스:
- 회사 분기 컨퍼런스콜 transcript
- TrendForce·Counterpoint HBM·DRAM·NAND 가격 트래커
- 회사 IR 자료실 분기 자료
- 일본·미국 동종업체 IR (Tokyo Electron, Micron, ASML) — cross-check

---

# Phase 0 — 데이터 가용성 프로빙 (컨센서스 시그널 레이어)

> 프로빙 일자: **2026-05-30**. 대상: SK하이닉스 `000660.KS` / corp_code `00164779`.
> 방법: 실제 네트워크 호출(yfinance·httpx·pymupdf)로 접근성 측정. 측정 수치는 모두 재현 가능.
> 근거 plan: `PLAN_consensus_signal_layer.md` §Phase 0.

## 0. 요약 — 소스별 접근성

| 소스 | 용도(시그널 레이어) | 접근 | 확보 가능 샘플 | 키 필요 |
|------|---------------------|------|----------------|---------|
| yfinance `earnings_dates` | **이벤트 일자**(실적발표일) + surprise% | ✅ | ~24분기 (2020-07~2026-07) | 무 |
| yfinance `history` (주가) | **초과수익률 라벨** 재료 | ✅ | 5Y 일봉 ~1,220행 | 무 |
| `^KS11`(KOSPI)·`229200.KS`(KODEX 반도체) | 시장·섹터 벤치마크 | ✅ | 5Y 일봉 | 무 |
| yfinance `earnings_history` | 직전 actual/estimate/surprise | ✅ | 4분기 | 무 |
| yfinance `eps_trend`·`eps_revisions` | 컨센 리비전 | ⚠️ **현재기준 rolling만** | 90일 창(5점) / 현재 up·down 카운트 | 무 |
| **DART 분기·사업보고서 MD&A**(서술) | **시그널 추출 입력** | ✅ **키 없이 공개뷰어로 추출 검증됨** | 정기보고서 전체(분기·반기·연간, 다년) | 무(공개뷰어) / 권장(OpenAPI) |
| DART 보고서 PDF | 동상(레이아웃 보존) | ✅ pymupdf 텍스트레이어 정상 | 동상 | 무 |
| **SK하이닉스 IR 실적 deck** | T0정렬 시그널(최선) | ⚠️ **SPA/비공개 API** | 헤드리스 브라우저/수동 필요 → **P1** | — |
| 과거 컨센 EPS 리비전 시계열 | 2차 라벨(T+30d) | ❌ **무료 아카이브 없음** | 0 | (FnGuide/WISEreport 유료·인증) |

## 1. yfinance — 컨센서스·이벤트·주가 (전부 가용)

- `earnings_estimate` / `revenue_estimate`: 0q/+1q/0y/+1y 4행, avg·low·high·numberOfAnalysts·growth. 분기 애널 7명(EPS)·26명(매출), 연간 31~38명. currency=KRW.
- `earnings_history`: 직전 4분기(2025Q2~2026Q1) epsActual·epsEstimate·surprisePercent. (예: 2026Q1 surprise +41.6% — HBM 서프라이즈 반영)
- **`earnings_dates`**(핵심): 2020-07~2026-07 25행, 과거 ~24개 실적발표 **타임스탬프 + EPS Estimate/Reported/Surprise%**. → 이벤트 스터디 이벤트 일자 백본. PLAN 요구(8~12분기) 초과 확보.
- `history`: `000660.KS` 1,221행 / `^KS11` 1,222행 / `229200.KS`(KODEX 반도체) 1,201행, 모두 2021-05~2026-05. → T+1d/T+5d 윈도우·초과수익률 산출 충분.

### ⚠️ 컨센 리비전 시계열 한계 (백테스트 타깃 결정의 핵심)
- `eps_trend`은 **오늘 기준** current/7d/30d/60d/90d ago 5점만 제공 — *임의 과거 시점의 as-of 컨센서스 복원 불가*. (예: 0q EPS가 90일 전 41,228 → 현재 69,422로 상향됐음은 보이나, 2024-07-25 시점 컨센은 알 수 없음)
- `eps_revisions`도 **현재** up/down 애널 카운트 스냅샷만.
- 무료 범위에서 **과거 컨센 리비전 아카이브를 찾지 못함**(FnGuide·WISEreport는 유료/인증). → PLAN §6 리스크가 현실로 확정.

## 2. DART 서술 텍스트(MD&A) — 키 없이 추출 검증됨 ✅

- **OpenAPI 계약 확인**: `list.json`에 더미 키 → `{"status":"010","message":"등록되지 않은 인증키입니다."}`. 엔드포인트 정상, **유효 키만 있으면** 공시 목록 반환. (현재 `.env` 부재로 키 미설정)
- **공개 뷰어 경로(키 불요) — 실제 추출 성공**:
  - `dsaf001/main.do?rcpNo=<rcpNo>` HTML의 JS 트리(`node['text'/'dcmNo'/'eleId'/'offset'/'length']`)를 파싱 → 섹션 식별.
  - 본문: `report/viewer.do?rcpNo=&dcmNo=&eleId=&offset=&length=&dtd=dart3.xsd`.
  - **검증**: SK하이닉스 사업보고서(2023-03-21, `rcpNo=20230321001209`)의 **"IV. 이사의 경영진단 및 분석의견"**(dcmNo=9083795, eleId=28) → 본문 plain **12,421자 / 한글 6,592자** 추출. (목차: "1. 개요 2. 재무상태 및 영업실적 3. 유동성 관리정책 및 현황 4. 부외거래 …")
- **PDF 경로도 정상**: `pdf/download/pdf.do?rcp_no=&dcm_no=` → 406p·1.48MB, pymupdf 텍스트레이어 PRESENT(8p당 한글 2,487자, 스캔본 아님).
- 검증된 rcpNo: 사업보고서 `20230321001209` / 분기보고서 `20240814003052` / 영업(잠정)실적 공정공시 `20190725800037`.

### ⚠️ 텍스트–이벤트 정렬 주의 (look-ahead)
- 분기·사업보고서(MD&A 수록)는 **실적발표(T0) 약 2~4주 뒤** 제출. → 같은 분기 T0 주가반응을 MD&A로 설명하면 look-ahead 위반.
- T0에 동시 공개되는 텍스트는 **영업(잠정)실적 공정공시**(주로 수치 표 + 짧은 "기타 투자판단 참고사항" 자유서술)와 **IR 실적 deck/콜**.

## 3. SK하이닉스 IR 사이트 — SPA 게이팅, P1 보류 ⚠️

- `www.skhynix.com/ir/...`는 **Nuxt(Vue) SPA**, 콘텐츠는 런타임 XHR(백엔드 `homeapi.skhynix.com`)로 로드. payload.js는 빈 셸(68B).
- 실적 deck PDF URL은 정적 HTML/payload에 없음, 백엔드 엔드포인트 비공개·추측 불가(다수 경로 404).
- 결론: **헤드리스 브라우저(Playwright)로 렌더링하거나 8~12개 deck를 수동 1회 수집**해야 함. 프로덕션 스크레이퍼 구축은 스코프 밖 → **P1**.
- pymupdf 텍스트레이어 자체는 위 DART PDF로 검증됨(deck도 동일 디지털 PDF면 추출 가능 전망).

## 4. 환경 게이팅 — 한글 홈 경로 SSL 이슈 (전 세션·Codex 공통 영향) 🔧

- 증상: `curl_cffi`(yfinance 백엔드)가 **CA 번들 경로의 한글(`C:\Users\김지원`)을 못 읽어** `curl: (77) error setting certificate verify locations`로 **모든 TLS 호출 실패**.
- 워크어라운드(검증됨): certifi 번들을 ASCII 경로로 복사 후 환경변수 지정.
  ```python
  import certifi, shutil, os
  shutil.copy(certifi.where(), r"C:\temp\earnings_forecast\cacert.pem")
  os.environ["CURL_CA_BUNDLE"] = r"C:\temp\earnings_forecast\cacert.pem"
  os.environ["SSL_CERT_FILE"]  = r"C:\temp\earnings_forecast\cacert.pem"
  ```
- → `pipeline/yahoo_fetcher.py`·`dart_fetcher.py` 구현 시 이 셋업을 모듈 임포트 전에 보장할 것. (CLAUDE.md "한글 경로 silent fail" 경고의 구체 사례)

## 5. Backtest 타깃 변수 — 확정

**채택(1차·유일 백테스트 타깃): 실적발표 이벤트 전후 시장조정 초과수익률(CAR).**
- 이벤트 일자 T0 = yfinance `earnings_dates` 발표 타임스탬프(KST 환산).
- 라벨: `CAR[T0→T+1d]`(주), `CAR[T0→T+5d]`(부). `AR_t = R(000660.KS) − R(^KS11)`, 섹터조정(`229200.KS`)은 robustness.
- 지표: directional hit ratio, IC(rank corr), 신뢰도 calibration. (PLAN §Phase B 지표와 동일)
- 샘플: 과거 ~16~24분기 확보 가능(PLAN 요구 8~12 충족).
- look-ahead 회피: 각 T0에 그 시점까지 공개된 텍스트만 입력.

**기각: T+30d 컨센 EPS 리비전 부호(2차 라벨).** — 과거 컨센 리비전 아카이브가 무료 범위에 없음(§1). 대신 **현재** `eps_trend`/`eps_revisions`는 백테스트가 아닌 **forward 콜 브리핑의 라이브 신호**로만 사용.

**시그널 텍스트 소스 — 확정 (2026-05-30 사용자 결정: 옵션 A):**
- ✅ **채택**: T0정렬 = **IR 실적 deck/콜** → 같은 이벤트 CAR 예측. deck **8~12개를 1회 수동/Playwright 수집**(스코프 내, 프로덕션 스크레이퍼 금지). 인과 최단·면접 방어력 최강.
- ✅ 병행: **DART MD&A**(키 불요, 즉시)는 **forward 콜 브리핑의 주 서술 입력**으로 사용.
- ⛔ 기각(대안 B 기록): MD&A(Q)→Q+1 발표 CAR 예측은 3개월 갭으로 인과 약함 → 백테스트 본선에서 제외.

## 6. 미해결 의존성 / 후속

- **DART_API_KEY**: 블로커 아님(공개뷰어로 텍스트 확보 가능)이나, 안정성(rate limit·구조화 응답)을 위해 발급 권장. `.env` 신설 필요(`.env.example` 참조).
- **IR deck 수집 방식**(수동 N개 vs Playwright 1회): **확정 = 수동 N개** (2026-06-03 사용자 결정). 본인이 분기별 deck PDF 8~12개를 `C:/temp/earnings_forecast/decks/`에 배치, `profiles/sk_hynix.yaml:signal_layer.decks`에 event_label↔doc_date 매핑. 스크레이퍼 코드 없음(T0정렬 정확·인과 최강·스코프 내).
- **시그널 추출 LLM**(Phase B): **확정 = Claude Haiku 4.5** (`anthropic` SDK, 2026-06-03 사용자 승인). temperature 0 + 프롬프트 캐싱 + 응답 디스크 캐시(`reports/.cache/signal_*.json`)로 재현성. 키 `ANTHROPIC_API_KEY`(`--dry-run`은 fixture라 불요).
- **[2026-07-31 상태정정] 위 두 결정은 현재 미가동.** `profiles/` 12개 중 `signal_layer` 보유 0개(`4ebeb7c`에서 `sk_hynix.yaml`의 블록 제거) → deck 경로·MD&A 경로 모두 진입 불가, `reports/.cache/signal_*.json` 0건. Phase-B는 **동면(DORMANT)** 상태이며 추출 완전성 미검증 상태로 남아 있다(`pipeline/disclosure_loader.py` STATUS 참조).
- Phase A(EFE 코어) 8Q MAPE 백테스트의 actual 재무는 별개 트랙(DART OpenAPI 키 또는 yfinance `quarterly_financials`) — 본 Phase 0 시그널 타깃과 무관.
- **[별도 태스크] 컨센서스 소스 교체** (사용자 결정 2026-05-30): yfinance `.KS` 컨센은 신뢰불가로 검증됨 — 매출·EPS 쌍의 함의 순이익률이 FY26 63%·0q 60%로 물리적 불가능(SK 실측 최대 ~30%). Phase A에서는 리포트에 신뢰불가 경고만 표시하고 gap을 억제. 신뢰 대체원(FnGuide/WISEreport, 유료·인증)으로의 교체는 P1 별도 태스크로 분리 — Phase A 코어 green 이후 Phase B 근처에서 착수.
