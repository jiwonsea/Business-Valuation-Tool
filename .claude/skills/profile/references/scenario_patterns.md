# 시나리오 설계 패턴

## 확률 배분 규칙
- 합계 = 정확히 100% (허용 오차 0.1%p)
- Base Case를 가장 높은 확률로 (통상 40~60%)
- 극단 시나리오(Bull/Bear)는 각각 15~30%

## 상장사 패턴
```yaml
scenarios:
  Base:   {prob: 50, ipo: "상장", dlom: 0, shares: <총발행주식수>}
  Bull:   {prob: 25, ipo: "상장", dlom: 0, shares: <총발행주식수>}
  Bear:   {prob: 25, ipo: "상장", dlom: 0, shares: <총발행주식수>}
```
- 상장사는 `dlom: 0` (유동성 할인 없음)
- `shares`는 모든 시나리오 동일 (총발행주식수)
- 시나리오 차이: 멀티플, 성장률 가정 (별도 프로필로 분리 or desc에 기술)

## 비상장사 패턴 (CPS/RCPS 있는 경우)
```yaml
scenarios:
  A:  # IPO 성공
    prob: 20
    ipo: "성공"
    dlom: 0
    shares: <총발행주식수>       # CPS 전환 포함
    cps_repay: 0                 # 전환되므로 상환 없음
  B:  # IPO 불발 + FI 우호
    prob: 45
    ipo: "불발"
    irr: 5.0                    # FI 요구 수익률
    dlom: 20
    shares: <보통주만>           # CPS 상환 소멸
    cps_repay: null              # null = IRR 기반 자동 계산
    rcps_repay: 490000
  C:  # IPO 불발 + FI 분쟁
    prob: 35
    ipo: "불발"
    irr: 12.0
    dlom: 25
    shares: <보통주만>
    cps_repay: null
    rcps_repay: 575000
```

### 핵심 주의사항
- IPO 성공 시: `shares` = 총발행주식수 (CPS 전환), `cps_repay: 0`
- IPO 불발 시: `shares` = 보통주만 (CPS 소멸), `cps_repay: null` (IRR 기반 자동계산) 또는 직접 금액
- `irr` 필드: IPO 불발 시나리오에서만 사용. FI의 요구 수익률.
- `cps_repay: null` vs `cps_repay: 0`: null=IRR 기반 자동계산, 0=상환 없음

## 비상장사 패턴 (CPS 없는 단순 구조)
```yaml
scenarios:
  Base:  {prob: 50, ipo: "N/A", dlom: 20, shares: <총발행주식수>}
  Bull:  {prob: 25, ipo: "N/A", dlom: 15, shares: <총발행주식수>}
  Bear:  {prob: 25, ipo: "N/A", dlom: 25, shares: <총발행주식수>}
```
- `dlom`: 비상장 유동성 할인 (통상 15~30%)
- Bull은 DLOM 낮게, Bear는 DLOM 높게

## DLOM 범위 참고
| 상황 | DLOM 범위 |
|------|----------|
| 상장사 | 0% |
| 비상장 (IPO 가능성 높음) | 10~15% |
| 비상장 (일반) | 15~25% |
| 비상장 (유동성 매우 낮음) | 25~35% |
