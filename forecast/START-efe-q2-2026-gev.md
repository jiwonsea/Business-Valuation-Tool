# START — EFE Q2 2026 실적 예측: GE Vernova (GEV)

> **필독 선행**: `START-efe-q2-2026-00-COMMON.md`. 이 파일은 GEV 고유 항목만.
> **실행 위치**: `earnings-forecast-engine` 새 세션. 프로파일: **신규 `profiles/gev.generic.yaml` 신설**.

## 종목 팩트
- 티커 GEV · CIK **미확정 → SEC ticker map(https://www.sec.gov/files/company_tickers.json)으로 반드시 해석.** · **12월 결산** · 대상 분기 **2026 Q2**.
- 발표 일정: **2026-07-22 (장 시작 전/오전, US)** — 확인됨. KST로는 **오늘 저녁~밤 발표** 가능 → **가능한 한 빨리 동결**(이미 발표됐다면 그 시각을 기록하고, actual을 보기 전 예측을 먼저 확정·타임스탬프).
- **2024년 4월 GE 분사** → 독립 상장 실적 이력이 **~9개 분기뿐.**

## ⚠️ 이 종목의 구조적 제약 (정직하게 disclose)
- **백테스트 윈도가 매우 짧다.** 독립 분기 실측 ~9개 → 나이브 RW 베이스라인·계절 슬롯 매칭이 빈약 → **skill 지표(MASE/Theil) 신뢰도 낮음.** COMMON §3 채점에서 이 한계를 명시(N 표기, "표본 부족" 경고). 분사 전 GE Power/Renewable/Grid 세그먼트 히스토리를 pro-forma로 붙일지 여부는 provenance를 갈라 기록(as-reported standalone vs pro-forma 혼용 금지).

## 세그먼트 구조 (예측 (b))
**Power**(가스터빈·서비스, 캐시카우) · **Wind**(적자 축소 중, 변동 큼) · **Electrification**(그리드·전동화, 고성장). 마진 변곡·수주(backlog)가 서사.

## 예측 난점 / 스윙 팩터 (사전등록 (f))
- **Wind 손익 변동**(적자 폭)이 below-OP/OP 레버 오차 주범.
- **Power 서비스 마진**·**Electrification 수주→매출 전환 속도**.
- **FY 가이던스 상향** 여부(수주·백로그 기반) — 스톡 무버 → (c).
- 대형 프로젝트 충당금/일회성 — below-OP 블록.

## 특별 지시
- (a) EPS 밴드 넓게(짧은 이력·높은 변동). (d) 컨센 갭은 세그먼트 매출·마진 중심.
- 채점 리포트에 **"윈도 N=~9, skill 지표는 방향 참고용"**을 반드시 라벨.
