# START — EFE Q2 2026 실적 예측: IBM

> **필독 선행**: `START-efe-q2-2026-00-COMMON.md`. 이 파일은 IBM 고유 항목만.
> **실행 위치**: `earnings-forecast-engine` 새 세션. 프로파일: **신규 `profiles/ibm.generic.yaml` 신설** (COMMON §1 데이터 무결성 풀 적용).

## 종목 팩트
- 티커 IBM · CIK **0000051143** · **12월 결산** · 대상 분기 **2026 Q2**.
- 발표 일정: **2026-07-22 장 마감 후**(콜 확인). KST 7/23 새벽 → **오늘 동결.**
- 신규 프로파일: EDGAR companyfacts whole-blob → split_history·Q4=연간−9M·NI÷희석주식수 파생 EPS(COMMON §1).

## 세그먼트 구조 (예측 (b))
**Software**(Red Hat, Automation, Data & AI/watsonx, Security) · **Consulting** · **Infrastructure**(zSystems 메인프레임 사이클·Distributed·Storage) · Financing. Software가 성장·마진 견인, Infrastructure는 메인프레임 출하 사이클에 크게 출렁.

## 이 종목의 예측 난점 / 스윙 팩터 (사전등록 (f))
- **GAAP vs 비GAAP(operating) EPS 브릿지가 함정.** 대규모 취득 무형자산 상각·연금 관련·workforce rebalancing 조정이 GAAP↔operating을 크게 벌린다. **어느 EPS를 예측하고 어느 컨센에 대조하는지 명확히**(둘 다 기록 권장). generic은 순이익 기반이므로 GAAP NI를 예측하되 컨센(대개 operating EPS)과의 정의 차이를 (d)에 명시.
- **FX**: 매출의 상당분이 해외 → 달러 강세/약세가 성장률에 수 %p. 스윙 팩터로 등록.
- **메인프레임 사이클 타이밍**: 신규 z 사이클 램프 위치가 Infrastructure 매출을 좌우.
- **FCF 가이던스**: IBM은 EPS보다 연간 FCF 가이던스가 서사 중심 → (c).

## 특별 지시
- (a) EPS는 **GAAP·operating 두 값** 병기, 컨센은 operating 기준임을 주의.
- Software 두자릿수 성장 지속 여부를 (b)·(d) 핵심으로.
- 신규 프로파일이므로 backtest 윈도 확보를 위해 최소 8~12개 분기 무결성 actuals 구축.
