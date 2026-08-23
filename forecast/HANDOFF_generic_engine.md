# HANDOFF — Generic (sector-agnostic) forecast engine + 8 M7/Samsung profiles

세션: 2026-07-06 (Cowork). 목표: SK하이닉스 전용 메모리 엔진을 건드리지 않고,
비메모리 대형주(M7 + 삼성 연결)를 EFE에서 전망 가능하게 만들기.

## 무엇을 왜 했나
메모리 엔진(`schemas/models.py`의 `SegmentAssumptions`, `engine/segment_revenue.py`,
`margin_model.py`)은 DRAM/NAND bit×ASP + HBM/DDR 원가체인에 하드코딩돼 있어
Microsoft/NVIDIA/Apple 등에 부적합. `nand_asp_qoq`를 MSFT에 쓰는 건 무의미.
→ **top-down generic 경로**를 병렬 신설(매출×성장×영업이익률→분기 EPS).

## 추가된 파일 (모두 additive, 기존 경로 불변)
- `schemas/generic.py` — `GenericProfile` 등 Pydantic v2 (`extra="forbid"`).
  스칼라/벡터 드라이버 정규화, `UNIT_SCALE`(USD_million/KRW_billion 등)로 EPS 단위 정합.
- `engine/generic_forecast.py` — 순수함수. `QuarterlyForecast`(기존 스키마) 재사용 →
  scenario 가중/연간집계 로직 공유. ASP 필드는 기본값으로 방치(무해).
- `generic_cli.py` — 오프라인 실행(YAML만, Yahoo/DART 불필요 → 샌드박스 OK).
  Korean MD 리포트(`reports/<co>_generic_forecast.md`) + **계절성 인지 1-step 백테스트**.
  `--json` 옵션.
- `profiles/{nvda,msft,aapl,googl,amzn,meta,tsla,samsung}.generic.yaml` — 8종.
- `tests/test_generic_forecast.py` — 8 tests (드라이버 정규화·재귀·가중·단위·검증). 전부 통과.

## 데이터 provenance (중요, hallucination 회피 원칙)
- **연간 총액·순이익·EPS·세그먼트 = 보고치**(FY2025, NVDA는 FY2026/Jan). 각 프로파일 헤더에 출처.
- **분기 `actuals` = 연간에서 역산한 근사치**(공식 분기 GAAP 아님). `notes`에 명시.
  → 백테스트 매출 MAPE(1~3%)는 **부분 순환성**이 있어 낙관적. EPS MAPE(8~18%)가 더 정직.
- **Tesla는 순이익/EPS 자체가 추정**(검토 릴리스에 없음) → 신뢰도 최저, `notes` 경고.
- 라벨은 캘린더 분기 근사. 회계연도 비-12월 기업(MSFT 6월·AAPL 9월·NVDA 1월)은 ~1개월 오프셋.

## 검증 (이 세션)
```
python -m pytest -q            # 97 pass (+8 generic = 105); 1 fail = tests/test_disclosure_loader.py::test_fetch_dart_mdna_nonempty
                               #   (라이브 DART 네트워크 의존 테스트, 코드무관)
                               # 2026-07-31~ : Phase-B 동면 조치로 @pytest.mark.network 부여 →
                               #   pyproject `addopts = -m 'not network'`에 의해 기본 실행에서 제외(전체 그린)
python generic_cli.py --profile profiles/nvda.generic.yaml   # 8종 모두 리포트 생성 OK
```
결과(2026 가중 EPS / 매출 MAPE vs naive RW): NVDA 7.20 / 8.5%(13.3%) · MSFT 17.99 / 2.4%(5.1%)
· AAPL 7.86 / 1.2%(12.2%) · GOOGL 10.28 / 1.8%(5.5%) · AMZN 6.84 / 1.3%(9.9%)
· META 31.24 / 2.5%(10.9%) · TSLA 2.18 / 1.0%(7.0%) · Samsung ₩7,596 / 2.7%(4.1%).
전 종목 매출 MAPE < naive RW.

## 호스트(Codex) 후속 (우선순위)
1. **독립 보고 분기 actuals로 교체** → 백테스트 순환성 제거. yfinance `income_stmt`(분기) 또는
   각사 IR 분기 프린트로 `actuals` 재작성. (샌드박스는 Yahoo 403이라 호스트 필수.)
2. **Tesla 실제 순이익/EPS** 10-K 확보 후 갱신.
3. generic 백테스트 고도화: 현재 `generic_cli.backtest_generic`은 1-step·계절슬롯 매칭.
   `engine/skill_metrics.py`(MASE/Theil) 재사용해 메모리 경로와 지표 통일 권장.
4. 리치 출력(HTML/Plotly/xlsx)은 메모리 경로 전용 — generic은 MD만. 필요 시 `output/*`에
   generic 분기 추가. (분리 유지가 안전.)
5. 커밋: 이 세션 파일들 `git add schemas/generic.py engine/generic_forecast.py generic_cli.py
   profiles/*.generic.yaml tests/test_generic_forecast.py reports/*_generic_forecast.md`.

## 주의 / 설계 계약
- generic ↔ memory 경로 **완전 분리**. `cli.py`·`run_backtest`·9Q 불변식 미변경.
- generic은 `QuarterlyForecast.gross_profit=0`(원가 미분해) — GP 마진 지표 무의미(의도적).
- 새 generic 프로파일 추가 시 `notes`에 각 수치 provenance 필수(연간=보고/분기=파생 구분).
