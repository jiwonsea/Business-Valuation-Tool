# Business Valuation Tool: 다음 세션

## 현재 상태
- 504/504 tests pass
- origin/main 동기화 필요

## 완료된 작업 (2026-04-11 버그픽스 세션)

### 이전 세션 (C3/C5/H1/M3/M4/D1/D2/D3)
- C3: DART 비상장 기업 corp_code 조회 개선
- C5: SEC EDGAR 파서 안정성 수정
- H1: WACC size premium 처리
- M3/M4: 멀티플 엔진 수정
- D1/D2/D3: distress 엔진 수정

### 세션 2 (C1/C2/C4/H2/H3/H4)
- **C1** `pipeline/dart_parser.py`: CAPEX_MAP 추가 + CF문 capex 추출 (abs 처리)
- **C2** `pipeline/dart_parser.py`: estimate_borrowings() → parse_financial_statements() 내부 연결 (gross_borr/net_borr 자동 포함)
- **H4** `pipeline/profile_generator.py`: C1 연동 확인 — capex 3-year avg 자동 계산 정상 작동
- **H2** `engine/wacc.py`: Hamada D/E cap(_HAMADA_DE_CAP=200%) + distress premium scaling 이미 구현 확인
- **H3** `engine/distress.py`: Signal 2 loss streak 판단 기준 net_income<0 → EBITDA<0 변경 (일회성 손실 과대반응 방지)
- **C4** `pipeline/yfinance_fetcher.py`: 401/429 에러 시 지수 백오프 3회 재시도 + KR 시장데이터 실패 시 yahoo_finance 직접 API fallback

### 세션 3 — 5모델 cross review 수정 (2026-04-11)
- **HIGH** `pipeline/yfinance_fetcher.py`: KRX fallback `market_cap=0` 버그 수정 → `price × shares / 1M` 계산 (EV 왜곡 방지)
- **MEDIUM** `pipeline/profile_generator.py`: `suggest_method()` 호출에 `de_ratio` 누락 수정 (고레버리지 해운/항공 라우팅 일치)
- **MEDIUM** `db/storage.py`: 한글 전용 파일명 → `"file"` 정적 fallback을 MD5 hash 8자리로 교체 (overwrite 방지)
- **LOW** `pipeline/dart_parser.py`: `logging` 추가 + capex 미발견 시 `logger.debug` (진단 용이)

---

## 백로그

현재 미해결 항목 없음.

---

## 모드: normal
