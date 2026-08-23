# HANDOFF — Phase A (EFE core end-to-end, SK Hynix)

> Codex CLI 핸드오프. **이전 세션과 무관, 캐시 없이 처음부터 읽어라.**
> 경로: `F:/dev/Portfolio/earnings-forecast-engine` (ASCII). 한글 홈경로(`C:\Users\...`)에서 호출 금지.
> 작성: Claude 세션 2026-05-30. 분업 원칙 — **본문 구현은 Codex, scaffold·픽스처·검증은 Claude.**
> 표준 가이드는 `AGENTS.md`, 로직 스펙은 `docs/methodology.md`. 본 문서는 그 위에 **Phase A 실착수에 필요한 검증된 사실**만 더한다.

---

## 0. 목표 (Acceptance — 이 4개가 done 조건)

1. `python cli.py --company sk_hynix --dry-run` → `tests/fixtures/`만으로 리포트 생성(외부 API 0회).
2. `python cli.py --company sk_hynix` → 실데이터 HTML 산출물(`reports/`), 브라우저 점검 가능.
3. `pytest -q` 전체 green (현재 3 passed / 15 skipped → skip 해제하며 구현).
4. 8Q backtest 실행: 매출 MAPE < 10%, EPS MAPE < 25%, hit ratio > 60% (`docs/methodology.md §11`). 미달 시 보고만(가정 수정은 사용자 몫).

## 1. 스코프 가드레일 (엄수)

- **SK하이닉스 1종목** (`000660.KS` / corp_code `00164779`)만. 다종목·웹UI·DB·스케줄러 금지.
- engine = 순수함수(IO·전역상태·로깅 없음). HTTP/yfinance는 `pipeline/`. Pydantic in/out, DataFrame 반환 금지.
- 모든 `open()`에 `encoding='utf-8'`. 가정 수치는 `profiles/sk_hynix.yaml`만, 코드 하드코딩 금지.
- `interpretation`/`thesis` 필드는 **빈 채로** 둔다(자동 생성 금지).

## 2. 이미 끝난 것 (다시 하지 마라)

| 항목 | 상태 | 위치 |
|---|---|---|
| `schemas/models.py` | 완성 | 그대로 사용. 변경 시 의존 모듈 전체 검토 |
| `.env` (DART_API_KEY) | 발급·입력 완료 | repo 루트 `.env` (커밋 금지, 값 출력 금지) |
| SSL CA-bundle ASCII 복사본 | 준비됨 | `C:\temp\earnings_forecast\cacert.pem` |
| yfinance 실데이터 픽스처 | 캡처 완료 | `tests/fixtures/sk_hynix_yahoo_estimates.json` |
| DART 실데이터 픽스처(2024 연간/3분기) | 캡처 완료 | `tests/fixtures/sk_hynix_2024q4_dart.json`(11011), `sk_hynix_2024q3_dart.json`(11014) |
| conftest 픽스처 배선 | 완료 | `sk_hynix_dart_raw`, `sk_hynix_dart_q3_raw`, `sk_hynix_yahoo_raw` |
| 프로브 참고 구현 | 작성됨 | `C:\temp\earnings_forecast\probe_yahoo.py`, `probe_dart.py` (재사용·확장 가능) |

## 3. ⚠️ 필수: SSL 셋업을 fetcher import보다 먼저

한글 홈경로 때문에 `curl_cffi`(yfinance 백엔드)가 CA 번들 경로를 못 읽어 **모든 TLS 호출이 silent-fail** 한다. `pipeline/yahoo_fetcher.py`·`pipeline/dart_fetcher.py`는 **yfinance/httpx import 이전에** 아래를 보장할 것 (모듈 상단 또는 공용 `pipeline/_ssl_setup.py`로 분리해 최상단 import):

```python
import os, shutil, certifi
_ASCII_CA = r"C:\temp\earnings_forecast\cacert.pem"
if not os.path.exists(_ASCII_CA):
    os.makedirs(os.path.dirname(_ASCII_CA), exist_ok=True)
    shutil.copy(certifi.where(), _ASCII_CA)
os.environ.setdefault("CURL_CA_BUNDLE", _ASCII_CA)
os.environ.setdefault("SSL_CERT_FILE", _ASCII_CA)
# 이 다음에야 yfinance / httpx import
```

검증됨: 위 셋업 후 `yf.Ticker("000660.KS")` 전 컨센 필드 정상 수신, DART httpx status=000.

## 4. yfinance 데이터 계약 (픽스처로 고정됨)

`fetch_consensus` → `to_consensus_record` (`pipeline/consensus_loader.py`).

- **yfinance 키 불필요** (비공식 스크레이퍼). 레이트리밋 대비 `reports/.cache/yahoo_{ticker}_{YYYYMMDD}.json` 캐시.
- `earnings_estimate`/`revenue_estimate` period 라벨 = **`0q`,`+1q`,`0y`,`+1y`** 상대값. **forward 분기 컨센은 2개뿐**(0q,+1q) + 연간 2개.
  - 상대→절대 매핑은 **실행일 의존**. 직전 actual이 2026Q1(`earnings_history` 최신 `2026-03-31`)이므로 2026-05-30 기준 `0q`=2026Q2, `+1q`=2026Q3, `0y`=FY2026, `+1y`=FY2027.
- **단위**: `revenue_estimate.avg`는 **KRW 절대값**(예 0q 81.8조 = `81815893820000`). 프로파일 `reporting_unit: KRW_billion` → `/1e9` 정규화는 `consensus_loader`가 수행.
- **EPS**: `earnings_estimate.avg`는 **원/주 절대값**(0q 69,422 / 0y 295,507). 분기 EPS가 수만원대인 점 유의(액면 5,000원, 미분할).
- NaN → 명시적 `None`. 누락 필드는 `ConsensusRecord.notes`에 기록.
- `consensus_diff`: 컨센 없는 forecast period는 `direction="n_a"`, `gap_*=None`.

## 5. DART 데이터 계약 (픽스처로 고정됨 — 가장 함정 많음)

`fetch_quarterly_financials` → `extract_quarterly_actual` (`pipeline/dart_fetcher.py`). 엔드포인트 `fnlttSinglAcntAll.json`, 파라미터 `crtfc_key, corp_code, bsns_year, reprt_code, fs_div="CFS"`(연결).

### 5-1. line item 매칭 규칙
- 손익은 **`sj_div == "CIS"`** (포괄손익계산서). `"IS"` 아님 — `("IS","CIS")` 둘 다 허용해 두라.
- `account_nm`에 접미사가 붙는다: `영업이익(손실)`, `당기순이익(손실)`, `매출총이익(손실)`, `법인세비용차감전순이익(손실)`. **exact match 금지** — `account_id`(표준코드, 예 `ifrs-full_Revenue`, `dart_OperatingIncomeLoss`) 우선, 보조로 `startswith`/`in`.
- 매출액=`매출액`, 매출원가=`매출원가`는 접미사 없음.
- 금액은 **KRW 절대값**(문자열, 콤마 없음). `int()` 후 `/1e9`로 KRW_billion. 빈 문자열/`-`는 None 처리.

### 5-2. ⭐ 분기 단독값 도출 규칙 (검증됨)
보고서별 `thstrm_amount` 의미가 다르다:

| reprt_code | 보고서 | `thstrm_amount` | `thstrm_add_amount` |
|---|---|---|---|
| 11013 | 1분기 | Q1 3개월(=누적) | (동일) |
| 11012 | 반기 | **Q2 3개월 단독** | H1 누적(6M) |
| 11014 | 3분기 | **Q3 3개월 단독** | 9M 누적 |
| 11011 | 사업(연간) | **연간 전체** | (빈값) |

→ **분기 단독 도출**:
- Q1 = 11013 `thstrm_amount`
- Q2 = 11012 `thstrm_amount` (단독)  *(또는 11012 add − 11013 thstrm 으로 교차검증)*
- Q3 = 11014 `thstrm_amount` (단독)
- **Q4 = 11011 `thstrm_amount`(연간) − 11014 `thstrm_add_amount`(9M 누적)**
- 검증: 2024 매출 연간 66,192,960,000,000 − 9M 46,425,925,000,000 = Q4 **19,767,035,000,000** (19.77조).

### 5-3. EPS는 DART에서 직접
`기본주당분기순이익(손실)`·`희석주당분기순이익(손실)` 존재 (Q3: thstrm 8,344 / add 17,118 원). 분기보고서는 분기 EPS 직접 사용 가능 → `QuarterlyActual.eps_basic`은 NI/shares 계산 없이 DART 값으로 채울 수 있다(연간 11011은 연간 EPS이니 Q4는 NI/shares 또는 EPS 차감 도출).

### 5-4. 8Q backtest 라이브 fetch 범위
backtest_window 2024Q1~2025Q4 + 시드 4Q → **2023~2025 각 연도 × {11013,11012,11014,11011} = 12 보고서**. rate limit 분당 1000 → httpx retry/backoff + 동일 캐시 키. 캐시: `reports/.cache/dart_{corp_code}_{year}_{reprt_code}.json`.

## 6. 작업 순서 (AGENTS.md §작업순서 그대로, Phase A 주석)

1. `pipeline/ir_loader.py` — YAML→Pydantic. probabilities 합=1, 드라이버 list 길이 ≥ n_quarters 검증.
2. `engine/segment_revenue.py` — methodology §4. (가장 핵심) `_next_quarter_label` 포함. test skip 해제.
3. `engine/margin_model.py` + `engine/opex_model.py` — §5. GP cap [0,0.8].
4. `engine/tax_finance.py` + `engine/eps_bridge.py` — §5-3,§6.
5. `engine/scenario.py` — §7. 라벨 mismatch → ValueError.
6. `pipeline/yahoo_fetcher.py` + `pipeline/consensus_loader.py` — §4 계약. **SSL 셋업 먼저**.
7. `pipeline/dart_fetcher.py` — §5 계약. **SSL 셋업 먼저**.
8. `engine/consensus_diff.py` + `engine/backtest.py` — §8,§9. look-ahead 회피(T시점 T-4..T-1만).
9. `output/plotly_charts.py`·`static_charts.py`·`html_builder.py`·`md_builder.py`·`xlsx_writer.py`·`pdf_export.py` + `templates/` 신설(현재 없음). HTML <5MB, 시스템 폰트만.
10. `cli.py main` — docstring의 8단계 배선. `--dry-run`은 fixtures 경로, 실행은 pipeline 경로. PDF는 `--skip-pdf` 기본 우회 가능.
11. 각 단계마다 대응 `tests/test_*.py` skip 해제·구현 → `pytest -q` green 유지.

## 7. 사용자 결정 대기 (Codex는 진행하되 리포트에 플래그)

- **주식수**: yfinance `sharesOutstanding=709,854,891` vs 프로파일 placeholder `728,000,000`. DART 사업보고서 유통주식수로 확정 필요 — EPS 직결. 우선 DART 값 사용하고 gap 표기.
- **forecast_window 2026Q1 시작**이 이미 보고된 actual(2026Q1 발표됨)과 겹침. 사용자가 window를 2026Q2~로 옮길지 결정 — 우선 YAML 그대로 두고 컨센 매핑만 실행일 기준.
- **컨센 2분기 한계**: 4분기 forecast 중 2개만 gap 비교 가능 — 정상. 나머지 `n_a`.

## 8. 검증 명령

```
pytest -q
python cli.py --company sk_hynix --dry-run
python cli.py --company sk_hynix
```
완료 후: 산출물 `reports/`, 백테스트 표를 사용자에게 보고. methodology §11 기준 미달 항목은 가정 재검토 신호로만 보고(YAML 수정은 사용자).
