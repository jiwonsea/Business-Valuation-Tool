# START — EFE Q2 2026 실적 예측: Tesla (TSLA)

> **필독 선행**: `START-efe-q2-2026-00-COMMON.md`. 이 파일은 TSLA 고유 항목만.
> **실행 위치**: `earnings-forecast-engine` 새 세션. 프로파일: `profiles/tsla.generic.yaml` (기존 존재).

## 종목 팩트
- 티커 TSLA · CIK **0001318605** · **12월 결산** · 대상 분기 **2026 Q2**.
- 발표 일정: **2026-07-22 장 마감 후**(콜 예정 확인됨). KST 기준 7/23 새벽 → **오늘 중 동결 필수.**
- **딜리버리는 이미 공개**(Q2 기록치, Electrek 프리뷰) → 매출 상단은 부분 관측 가능. **문제는 수익성.**

## 프로파일 상태 (⚠️ EFE 최저 신뢰 종목)
- `tsla.generic.yaml` 존재하나 메모리 노트상 **순이익/EPS 자체가 추정**(검토 릴리스 미포함)이라 신뢰도 최저. actuals backtest REFUSE → `build_generic_actuals.py`로 재구축하되 **as-filed EPS provenance**(10-K/10-Q 원문)를 반드시 확보. 과거 forward shares 3.5e9→3.538e9 정정 이력 — 주식수 basis 재확인.

## 세그먼트 구조 (예측 (b))
Automotive(차량 판매 + regulatory credits + 리스) · **Energy generation & storage**(급증, 마진 우호) · Services & other. 마진은 auto GM(ex-credit)이 핵심.

## 이 종목의 예측 난점 / 스윙 팩터 (사전등록 (f))
- **Automotive 총마진(크레딧 제외)**: 가격인하·ASP·믹스가 좌우. 여기가 최대 불확실.
- **Regulatory credits 규모**: 순이익에 직접, 변동성 극심 → OP→NI/below-OP 레버의 주 오차.
- **에너지 사업 매출·마진 급증**: 상방 서프라이즈 후보.
- **SBC·restructuring·1회성**: below-OP 블록.
- robotaxi/FSD/Optimus 코멘트: EPS가 아니라 **스토리**로 주가 반응 → (e) 콜 토픽에 명시(밸류에이션 옵션은 BVT 몫).

## 특별 지시
- EPS 포인트 추정의 **불확실 밴드를 넓게**(신뢰도 하) 잡고 (f)에 크레딧·auto GM 두 축을 명시적으로 사전등록.
- (d) 컨센 갭: 딜리버리가 공개됐으니 **매출보다 GM·EPS 갭**에 초점.
- 사후 채점 시 auto GM ex-credit와 credit 규모를 분리 귀인.
