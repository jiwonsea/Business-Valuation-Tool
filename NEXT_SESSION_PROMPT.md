# Business Valuation Tool: Phase 3 — Calibration & Polish

## 배경
직전 세션(2026-04-07)에서 완료한 것:

### Infrastructure + Phase 2 잔여 (미커밋, 7 files modified)
- **Infrastructure**: GOOGL 3-segment 프로필 완성 (GS 14.0x/GC 20.0x/OB 5.0x ev_rev, peer 실데이터 기반), NVDA 검토 완료 (변경 불필요), OpenRouter $4.81 잔액 정상
- **Revenue Type 레이블**: SOTPSegmentResult.revenue_type 추가, console+Excel에 "(NTM)" 표시, is_mixed 조건 확장 (ev_revenue 포함), Equity Bridge pbv/pe 한정 분리
- **Distress Phase 2**: 경기순환 2년 적자 감면 (10%→5%), 세그먼트별 차등 할인 (healthy_segments half discount), 35% cap 유지 (실데이터 20-40% 범위 지지)
- **MC Phase 2**: Revenue 불확실성 샘플링 (mc_revenue_std_pct=30%), 시나리오별 MC (Bull/Bear 각각 2000회, MCScenarioSummary)
- 395/395 tests pass (394 기존 + 1 신규)

### TSLA 시나리오별 MC 결과
- Base: P5=$27, Mean=$35, P95=$45
- Bull: P5=$58, Mean=$82, P95=$109
- Bear: P5=$17, Mean=$21, P95=$27

### GOOGL 밸류에이션 결과
- Base $379, Bull $545, Bear $213, 확률가중 $379 (시장가 $300 대비 +26.3%)

## 미완료
1. **Supabase SQL 실행**: `db/migrations_backtest.sql` 하단 Schema updates (market_signals_version 컬럼 + unique indexes 2개) — 대시보드에서 수동 실행 필요
2. **커밋**: 이번 세션 변경사항 미커밋 상태

## 다음 작업 후보
1. **Calibration Infrastructure**: backtesting pipeline 활성화 — prediction_snapshots 자동 저장 + 3/6/12개월 후 주가 수집 + accuracy 리포트
2. **GOOGL 옵셔널리티 정밀화**: OB(Other Bets) 세그먼트 Waymo/Verily 분리 검토
3. **Console report 포맷 정리**: 세그먼트 이름이 길 때 컬럼 정렬 밀림 개선
4. **yfinance SSL 이슈**: Python 3.14 + 한글 경로에서 certifi cacert.pem 접근 실패 — peer 멀티플 자동 fetch 불가

## 참고 파일
- `valuation_runner.py` — _run_monte_carlo() (시나리오별 MC), apply_distress_discount(healthy_segments)
- `engine/monte_carlo.py` — MCInput.revenue_params, revenue_samples 샘플링
- `engine/distress.py` — cyclical 2-year 감면, apply_distress_discount(healthy_segments)
- `schemas/models.py` — MCScenarioSummary, SOTPSegmentResult.revenue_type, mc_revenue_std_pct
- `output/console_report.py` — is_mixed 확장, NTM 레이블, 시나리오별 MC 출력
- `profiles/googl.yaml` — 3-segment (GS/GC/OB), peer 실데이터 기반 멀티플
- `profiles/tsla.yaml` — revenue_type: ntm 추가됨

## 모드: normal
