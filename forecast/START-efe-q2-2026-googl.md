# START — EFE Q2 2026 실적 예측: Alphabet (GOOGL)

> **필독 선행**: `START-efe-q2-2026-00-COMMON.md` (공통 프로토콜). 이 파일은 GOOGL 고유 항목만.
> **실행 위치**: `earnings-forecast-engine` 새 세션. 프로파일: `profiles/googl.generic.yaml` (기존 존재).

## 종목 팩트
- 티커 GOOGL · CIK **0001652044** · **12월 결산**(오프셋 없음) · 대상 분기 **2026 Q2**(6월 종료).
- 발표 일정: **미확정 — 예비 소스 상충(7/22 vs 7/23 vs 7/28)**. 착수 시 IR/나스닥 캘린더로 확정하고 그 시각 이전에 동결.
- 예비 컨센서스 참고치(**반드시 재확인**): EPS ~$2.89(Alphastreet 프리뷰). Cloud 성장률·capex 가이던스가 실제 스톡 무버.

## 프로파일 상태
- `googl.generic.yaml` 존재하나 **actuals가 gap-ridden → backtest REFUSE**. `scripts/build_generic_actuals.py`로 EDGAR companyfacts 기반 무결성 재구축 후에만 백테스트. (COMMON §1 데이터 무결성 규칙 전부 적용.)
- 과거 BVT 쪽 googl.yaml에서 **주식수 Class-A-only 파싱으로 2x 버그**(5.82B→12.1B 정정) 이력 — generic 프로파일도 희석주식수 basis 재확인.

## 세그먼트 구조 (예측 (b)에 반영)
Google Search & other · YouTube ads · Google Network · **Google Cloud**(성장·수익성 전환 스토리) · Subscriptions/Platforms/Devices · Other Bets(적자, 옵션가치). 마진은 Services vs Cloud vs Other Bets 믹스.

## 이 종목의 예측 난점 / 스윙 팩터 (사전등록 (f)에 반영)
- **EPS 왜곡: OI&E(기타영업외손익)의 지분투자 평가손익.** 비상장 지분 mark-to-market이 순이익을 크게 흔든다 — "EPS may mislead"의 실체. 우리 generic의 **OP→NI 전환 레버**가 주 오차원. 영업이익 기반 예측이 더 정직 → (d) 컨센 갭에서 OP도 별도 비교.
- 클라우드 성장 감속/가속(예비 소스 30%+~63% 편차 — 재확인)과 **AI capex 가이던스 대폭 상향** 여부: 마진·현금흐름 서사가 EPS보다 반응이 크다 → (c) 가이던스 방향 예측 비중 높게.
- 반독점(검색 기본계약·크롬/안드로이드 구제안) 코멘트: 실적 자체보다 콜 Q&A 리스크 → (e).

## 특별 지시
- (a)~(f) 전부 동결. 특히 (d)에서 **매출·OP·EPS 3층 컨센 갭**을 각각 기록(EPS만 보면 OI&E에 속는다).
- 세그먼트 매출은 컨센 대비 Search/Cloud 각각의 방향을 명시.
