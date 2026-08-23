# NVDA 2026-08 심층 리서치 계획 rev-2 — Codex 판정서

> 평가일: 2026-08-09 KST  
> 평가 대상: `PLAN_nvda_2026-08_deep_dive.md` rev-2  
> 범위: 계획 평가만 수행. 코드·프로파일·동결 산출물은 변경하지 않음.

# §1. 재현 결과

## 1.1 §3-1 GAAP ↔ 비GAAP 브릿지 — 수치 일치, 결론은 조건부

**판정: 산술은 일치한다. 다만 “컨센서스 = 비GAAP”은 이 산술만으로 입증되지 않는다.**

- Q1 FY27 GAAP 유효세율은 `11,582 / 69,903 = 16.5687%`다. 지분증권 평가익 `15,929 × (1-tax) = 13,289.8`, GAAP ex-mark EPS는 `(69,903-15,929) × (1-tax) / 24,391 = $1.8462`로 계획의 `$1.846`과 일치한다.
- NVIDIA의 실제 조정표는 총 세전 조정 `15,663`, 조정 세효과 `2,890`, 비GAAP NI `45,548`, EPS `$1.87`을 제시한다. 따라서 차이 `517`은 단순 반올림이 아니라 평가익 외 인수관련·기타 조정과 조정항목의 한계세율 차이다. 실제 조정 세율은 `2,890/15,663 = 18.45%`로 GAAP 평균세율 16.57%와 다르다.
- FY27부터 SBC를 비GAAP에 포함하므로 과거의 큰 GAAP/non-GAAP 영업비용 차이는 줄었다. 그러나 Q2 회사 전망도 GAAP/비GAAP GM `74.9%/75.0%`, opex `$8.5B/$8.3B`로 완전히 같지는 않다. 따라서 V2의 GAAP 가이드 내재 OP를 “사실상 비GAAP”이라 부르는 것은 근사 표기여야 한다.
- 같은 회사 가이드로 비GAAP OP를 직접 계산하면 `91,000×75.0%-8,300=59,950`; below-OP 0, 세율 17%, Q1 주식수 적용 EPS는 `$2.040`이다. Q1 비GAAP other income `$457M`을 그대로 넣으면 `$2.056`이다. V2 `$2.030`과 가깝지만 동일 정의는 아니다.
- 결론적으로 `비GAAP ≈ GAAP − 세후 지분평가마크`는 **Q1에 대해 반증 가능한 근사식**으로 채택 가능하다. 반면 세 컨센 소스가 조정 EPS를 뜻하는지는 각 소스의 metric definition 없이는 확정할 수 없다. 숫자가 가깝다는 사실은 기준 증명이 아니다.

근거: [NVIDIA Q1 FY27 실적·전망·GAAP/non-GAAP 조정표](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-First-Quarter-Fiscal-2027/default.aspx), [FY27부터 SBC 정의 변경 공지](https://investor.nvidia.com/news/press-release-details/2026/NVIDIA-Announces-Financial-Results-for-Fourth-Quarter-and-Fiscal-2026/).

## 1.2 §3-2 자유도 및 `project_scenario` — 계산 순서는 일치, 실제 엔진 재현은 불일치

**판정: 매출→OP→below-OP 포함 세전이익→세금→NI→EPS라는 순서는 엔진과 일치한다. 후보 V2는 현재 프로파일을 넣은 실제 `project_scenario` 출력은 아니다.**

- `engine/generic_forecast.py`는 `revenue`, `op = revenue×op_margin`, `pretax = op + revenue×net_interest_pct`, `net = pretax×(1-tax)`, `eps = net×scale/shares` 순서다. 후보 스크립트도 같은 순서다.
- V2 base `rev 91,000`, `OP 59,659`, `OPM 65.5593%`, `EPS 2.03013`; 확률가중 `rev 91,000`, `OP 59,663.55`, `EPS 2.03066`은 JSON과 재계산이 일치한다. 후보 파일 SHA-256도 `65bfb0a3201f73127c1034780e5eb99bc908ee86aa9d6cbadebd6301f8a4b693`으로 일치한다.
- 그러나 엔진은 `profile.weighted_avg_diluted = 24,490M`을 사용한다. 후보 V2는 `SHARES_Q1 = 24,391M`을 별도로 사용해 base EPS를 `$2.0301`로 만들었다. 프로파일 주식수를 쓰면 `$2.0219`다. 즉 후보는 엔진 공식의 독립 계산이지 현재 엔진 경로의 bit-identical 실행이 아니다.
- “자유도 0”은 과장이다. 가이드의 `±2%`, GM `±50bp`, opex의 `approximately`, discrete tax, other income, 주식수에는 자유도가 남는다. V2는 이를 회사 범위 끝점·base 0·Q1 주식수라는 정책으로 닫았다. 정확한 표현은 **“R1~R3 정책을 추가로 고정하면 guided-quarter의 차별적 자유도가 실질적으로 매우 작다”**다.
- `$2.030`이 컨센 범위 안이라는 사실은 `NO_SURPRISE` 사전판정에는 충분하지만 “정의상”은 아니다. 세 컨센의 기준·빈티지·회계분기 정렬이 미확인이고, 실제 surprise는 발표치와 고정된 동질 기준을 비교해야 결정된다.
- CLAUDE.md의 `<5% every quarter = no view`는 한 분기·한 범위에 바로 적용할 수 없다. 이번 분기의 “차별적 뷰 없음”은 정직한 결과지만 계약 실패나 종목 실패를 자동 의미하지 않는다. 가이드 밖 Q3 가이던스·mark·valuation에 사전 정보 우위가 있을 때만 종목을 유지한다.

## 1.3 §3-3 프로파일·레버·주식수

| 항목 | 판정 |
|---|---|
| `op_margin: 0.62` 출처 | **프로비넌스 결함 확정.** 주석의 FY26 약 62%는 `130,387/215,938=60.38%`와 불일치하고 나열된 TTM/Q4/Q1 값과도 일치하지 않는다. |
| R1 매출·OPM 격차 | **일치.** `89,776.5→91,000`은 +1.36%가 필요하며, 현 값은 가이드 대비 **−1.3445%**다. OPM은 `62.0→65.5593%`, **−3.5593pp**다. |
| R3 세율 격차 | base 15% 대비 가이드 midpoint 17%는 **−2.00pp**다. 계획의 `−1.57pp`는 Q1 실제 16.57%와 비교한 값이라 “정당한 앵커 16~18%”의 단일 격차로 쓰면 모호하다. |
| R2 필드 범위 | 엔진상 이름은 `net_interest_pct_of_revenue`지만 세전 OP 아래 **전체 단일 블록**이다. Q1 `69,903−53,536=16,367`, 매출 대비 `20.053%`이므로 R2 적용 대상이 맞다. 다만 marketable/non-marketable 분리는 현 스키마로 표현되지 않는다. |
| 4-le버 분해 | **불일치.** 24,490M 주식수를 유지한 순차 기여는 매출 `+0.0268`, OPM `+0.1124`, below-OP `−0.0316`, 세율 `−0.0487`이고, 마지막에 24,391M으로 바꾼 주식수 효과가 `+0.0082`다. 합은 후보의 `+0.0671`과 정확히 일치한다. 계획의 세율 `−0.038`과 4레버 합 `+0.069`은 재현되지 않으며 주식수 convention 변경도 누락했다. |
| 24,490M 주식수 | Q1 실제 24,391M보다 크므로 다른 조건 동일 시 EPS를 낮추는 방향은 맞다. 다만 `$80B` 승인은 집행이 아니므로 Q2 가중평균 주식수를 자동 하향할 근거는 아니다. 실제 집행시점·SBC 희석과 함께 밴드화해야 한다. |

## 1.4 §3-4 엠바고

**판정: 외부 산출물의 백테스트 숫자에만 엠바고를 거는 축소는 타당하다. 다만 G-A와 실패모드가 맞지 않는다.**

- G-A bit-identical 검사는 데이터 추출과 실행의 결정성·환경 회귀를 잡는다. 잘못된 XBRL 태그 선택, Q4 복원 논리, fiscal label, 경제적 정의 오류는 같은 잘못을 동일하게 재현하므로 잡지 못한다.
- 따라서 정확성을 방어하려면 G-B `OperatingIncomeLoss`, FY 합계 tie-out, 표본 행 원문 대조, 라벨/접근번호 검사까지 묶어야 한다. G-A 단독을 “정확성 게이트”로 표현하면 안 된다.
- 계획 §0/§2에서 `MAPE 11.50%·MASE 0.592`를 결론 근거로 사용하면서 §3에서 외부 인용을 금지한 것은 내부 논증도 이미 그 수치에 의존한다는 모순이다. G-A 전에는 숫자를 제거하거나 `UNVERIFIED/PENDING G-A`로 표시하고 논증의 필수 전제로 쓰지 않아야 한다.

# §2. Q1~Q6 판정

| 질문 | 판정 | 근거·조건 |
|---|---|---|
| **Q1 자유도 소멸** | **조건부채택** | guided Q2에 규칙 예외를 만들지 말고 “차별적 뷰 없음”을 기록한다. 종목을 일괄 제외하지는 말되, **가이드 밖 핵심 변수에 사전 관측 가능한 edge가 있다는 선정 기준**을 추가한다. 없다면 EFE 종목에서는 제외하고 valuation/monitoring 대상으로만 남긴다. |
| **Q2 below-OP** | **조건부채택** | marketable/non-marketable 분할과 비정상 과정에 역사 분위수 미사용은 채택한다. 비시장성분은 point-error 순위에서 제외할 수 있으나 **전체 GAAP coverage 실패까지 삭제하면 안 된다**. “unforecastable” 별도 bucket과 범위·coverage를 함께 보고한다. |
| **Q3 naive-G** | **기각** | `mid×m̂`를 현재 한 건에서 mid와 비교해 skill을 주장하는 설계는 폐기한다. 12분기 자료가 있으면 각 시점 이전 자료만으로 `m̂`를 추정하는 **rolling-origin guidance-error benchmark**로 바꾼다. 유효 OOS가 부족하면 guidance mid·consensus를 단순 기준선으로만 병기하고 skill 주장은 하지 않는다. |
| **Q4 우발채무** | **조건부채택** | 협의 금액을 확정 채무나 base 현금유출로 넣지 않는다. 법적 구조·확률·손실률을 검증할 수 있을 때만 bear sensitivity로 표시한다. (iii) 한 경로만 사용하고 CDS·주가 반응은 방증으로만 두는 이중계상 차단은 채택한다. |
| **Q5 적대성** | **조건부채택** | Codex는 고정 규칙의 기계 적용·산술 재현 reviewer는 맡을 수 있다. 모호한 발화·테제 판정은 **동결 문서를 보지 않은 fresh session/reviewer가 source packet만 받아 판정**하고 사람이 최종 승인해야 한다. 분리하지 못하면 반드시 `SELF-SCORED`로 표기한다. |
| **Q6 효익/노력** | **기각** | 직접 기여 비율은 약 **35%**로 본다. §0 제목의 존재가 아니라 실제 작업시간 기준으로 보면 G-A~D, 이중 동결, 프로파일 교정, 백테스트, 스코어러가 절반 이상이다. 절단은 `naive-G → G-A/2c의 본 계획 분리 → 프린트 전 BVT → Freeze-B` 순이 적절하다. |

# §3. 계획의 신규 약점

## P0

1. **13F 기준일이 목표 분기말과 다르다.** 08-14 제출되는 Q2 13F는 **06-30 보유분**이며 목표 분기말은 07-26이다. 또한 13F는 Section 13(f) 대상 증권의 long position 중심이라 전체 시장성 증권 원장을 제공하지 않는다. 따라서 §5.2의 “07-26 평가액 산출”은 기계적으로 불가능하다. 13F는 06-30 수량의 부분 관측치로만 쓰고, 07-01~07-26 거래 불명 밴드를 둬야 한다. [SEC Form 13F FAQ](https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/frequently-asked-questions-about-form-13f)
2. **레버 분해가 주식수 변경을 숨기고 세율 기여를 잘못 계산했다.** §1.3의 정정 없이는 Freeze-A 변경 원인과 사후 attribution이 일치하지 않는다.

## P1

1. **해시는 숫자 후보만 잠그며 판단 누수 전체를 막지 못한다.** 이후 Freeze-A가 “근거가 있으면” 후보와 달라질 수 있고, T-1/T-3 테제·밴드·확률·Q3 가이드에는 별도 byte lock이 없다. 변경 로그에 `관측시각≤cutoff`, 원장 row id, 결정 규칙을 요구해야 한다.
2. **“컨센 = 비GAAP”은 basis 검증을 숫자 근접성으로 대체한다.** 소스별 fiscal label, metric definition, as-of timestamp가 확인되지 않으면 HIT/MISS 대신 `BASIS_UNKNOWN`이어야 한다. min/max band는 서로 다른 기준의 숫자를 섞는 문제를 해결하지 못한다.
3. **T-1은 분자 중복과 인과 방향 규칙이 없다.** 지분·보증·금융·선급이 같은 프로젝트/고객에 겹칠 수 있고, 고객 capex commitment가 NVDA 인식매출과 같지 않다. counterparty-project 단위 dedupe, realized/committed/negotiating 구분, 매출 인식기간을 먼저 정의하지 않으면 밴드는 정밀해 보여도 감사 불가능하다.
4. **“자유도 0→EFE 부가가치 없음” 실패조건은 논리 점프다.** actual이 consensus band 안에 든 한 건은 가이드의 정확성을 보일 뿐 EFE 전체 무가치를 검증하지 않는다. guided-quarter level edge와 unguided variable edge를 분리해 채점해야 한다.
5. **T-2 실패조건의 ±50% 분모가 불안정하다.** 실제 mark가 0 또는 작으면 상대오차가 폭발한다. 절대오차를 opening marketable carrying value 또는 pretax income 대비 bp로 함께 정의해야 테스트 가능하다.

## P2

1. **프린트 당일 손 전사 통제는 독립성이 부족하다.** 같은 사람이 입력하고 후일 대조하는 대신 2인/2-pass 독립 전사 후 필드별 diff를 먼저 실행하는 편이 낫다. provisional 표기는 유지한다.
2. **T-1 실패 밴드 `5%~60%`는 폭만 보고 정보가치를 판정한다.** 넓어도 하단 자체가 valuation thesis를 깨면 유용할 수 있다. 폭뿐 아니라 decision threshold crossing 여부를 함께 판정해야 한다.

# §4. 6+1축 회신

1. **정확성 — 조건부 미통과.** §3-1 산술과 §3-2 V2 숫자는 일치한다. 다만 엔진 주식수 불일치, 레버 세율 오류, R3 격차 표기 혼선, consensus basis 미확인이 남는다. 프로파일 62%는 출처 결함이 맞다.
2. **건전성 — 미통과.** 후보 JSON 해시는 확인됐고 숫자 소급변경 방지에는 유효하지만, 서술·확률·밴드·후보 이탈을 잠그지 못한다. 계획의 OpenAI 보증/금융, CDS, 주가 반응, 컨센 세 소스 등 핵심 사실은 표 안에 원문 URL·관측시각이 없어 계획 단독 재현성이 부족하다.
3. **회귀안전 — 조건부.** 현 기준선은 `verify_9q_sha.py` host SHA `b979d79f…f6e7` 일치, generic 관련 17 tests 통과다. 프로파일 변경은 NVDA forward를 의도적으로 바꾸므로 “기존 9종 전부 불변” 요구와 충돌한다. 수용 기준은 **SK 9Q SHA 불변 + NVDA 외 기존 generic 출력 불변 + 신규 옵션 부재 시 직렬화 JSON byte-identical + NVDA expected fixture 명시 변경**으로 재작성해야 한다. 구현 전에는 인증 불가다.
4. **범위규율 — 조건부 통과.** 계획은 P1-C 역사 분위수를 거부하고 P0-A/P1-A/하드닝을 명시 승인 없이 실행한다고 직접 쓰지는 않는다. 다만 marketable/non-marketable 신규 필드, 3지표, score script는 사실상 새 구현 범위다. 승인 후 별도 구현 계획과 테스트 수용기준이 필요하다.
5. **검증가능성 — 부분 통과.** SF-A/B는 기계 적용 가능하다. SF-C는 10-Q가 시장성 mark를 충분히 분해한다는 보장이 없고 ±50% 분모도 정의되지 않았다. T-1/T-3/T-4 실패조건은 현재 자연어 판정이 많다. 삭제한 잔차 0·5회 카운트·N=1 유의성 3건은 삭제가 맞다.
6. **유지보수성 — 조건부 통과.** NVDA 고유 로직은 프로파일 YAML과 optional attribution schema로 표현 가능하다. 다만 현재 `net_interest_pct` 단일 scalar에 2분할을 억지로 넣지 말고, generic engine의 기존 경로를 그대로 둔 채 **report/scoring용 optional components**로 추가해야 한다. 옵션 부재 byte test가 필수다.
7. **효익/노력 — 미통과.** reverse DCF·Q3 guide·이익의 질이 직접 기여도가 높다. naive-G, G-A/2c, 이중 동결의 정교화는 방법론 자산에는 유용하지만 `$223.96` 판단의 critical path가 아니다. 현 계획은 여전히 도구 검증과 투자판단을 한 일정에 과도하게 묶는다.

# §5. 일정 판정

- **08-13 G-D:** 자료 12건의 원문 확보 자체는 가능해 보이나, 현재 목적의 naive-G에는 불필요하다. rolling-origin으로 재설계할 때만 유지하고, 아니면 즉시 폐기한다. 드롭데드는 타당하다.
- **08-14 G-A:** 백테스트 외부 인용 제한의 1차 드롭데드로는 타당하다. Freeze-A 숫자·§0 작업의 차단 조건으로 사용하면 안 된다.
- **08-22 G-A:** G-A가 이중 동결 필요성과 인과적으로 연결되지 않는다. “G-A 미해소→Freeze-B 붕괴” 규칙은 질문이 잘못됐다. Freeze-B는 cutoff 후 사전 트리거가 실제 발생했는지와 변경 비용으로 독립 결정해야 한다.
- **Freeze-B 시각:** 표에는 `08-26 24:00`과 “데드라인 08-27 03:00”이 함께 있어 3시간 불일치한다. 하나로 고정해야 한다. 24:00는 날짜 표현도 모호하므로 `2026-08-27 03:00 KST`처럼 ISO 시각 하나만 써야 한다.
- **절단 순서:** naive-G 1순위와 프린트 전 BVT 절단은 맞다. 다음은 G-A/2c를 별도 EFE 하드닝 세션으로 분리하고, material trigger가 없으면 Freeze-B를 짧은 `NO_CHANGE` append로 대체한다. §0도 동일 우선순위가 아니다. T-3 reverse DCF와 T-4 판정을 우선하고, T-1은 dedupe 가능한 근거가 없으면 조기 정성 강등한다.

# §6. 최종 verdict

## CONDITIONAL

다음 조건 충족 후 실행 승인 가능하다.

1. 13F를 06-30 부분 관측치로 정정하고 07-26 보유량 복원 주장과 기계적 mark trigger를 삭제한다.
2. Freeze-A의 주식수 convention을 엔진과 통일하거나 의도적 override 필드로 명시하고, 레버 분해를 `+0.0268/+0.1124/−0.0316/−0.0487/+0.0082(주식수)`로 재산출한다.
3. “컨센 = 비GAAP”을 가설로 낮추고, 소스별 basis가 확인되지 않으면 `BASIS_UNKNOWN`으로 fail-closed한다.
4. naive-G를 폐기하거나 과거정보만 쓰는 rolling-origin guidance-error benchmark로 재설계한다.
5. 비시장성 mark를 point score에서 제외하더라도 전체 GAAP coverage와 `UNFORECASTABLE` bucket은 보존한다.
6. G-A/2c를 투자판단 critical path에서 분리하고, 실제 노력의 과반을 T-3→T-4→Q3 guide/T-2→T-1 순으로 재배분한다.
7. Freeze-B 단일 마감시각을 정하고, 08-22 G-A와 Freeze-B 붕괴의 잘못된 연동을 제거한다.

이 조건들은 프레임 전체를 기각하는 요구가 아니다. rev-2의 핵심 방향인 “guided Q2 포인트에 억지 edge를 만들지 않고, 가이드 밖 변수와 valuation으로 이동한다”는 채택한다. 다만 현 상태로는 산술·basis·13F 기준일 오류가 사후 채점과 투자판단 양쪽을 왜곡할 수 있어 무조건 승인할 수 없다.
