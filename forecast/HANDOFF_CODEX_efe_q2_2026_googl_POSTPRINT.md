# HANDOFF (Codex) — EFE Q2 2026 GOOGL 사후 채점 (POST-PRINT)

Date: 2026-07-22 (실적 발표 후, 콜 진행 중). 선행: `HANDOFF_CODEX_efe_q2_2026_googl.md`(동결), commit `aecd9207`.
프레임: **"사후 귀인 — 예측 신호 아님"**. 채점은 매출·OP·adj-EPS 기준, GAAP EPS는 OI&E 때문에 별도.

## 1. ACTUAL (Alphabet Q2 2026 earnings release, primary source, $M)
| 항목 | 값 |
|---|---:|
| Total revenues | **119,796** |
| Income from operations (OP) | **40,770** (op마진 34.0%) |
| Other income (expense), net | 97,983 |
| — Gain on equity securities, net | **99,031** (Anthropic·SpaceX 평가이익) |
| Income before taxes | 138,753 |
| Provision for income taxes | 26,560 (실효세율 **19.1%**) |
| Net income | **112,193** |
| Diluted EPS (GAAP) | **$9.11** |
| Diluted weighted-avg shares | **12,309M** |
| Google Services rev / OP | 94,540 / 39,544 |
| Google Cloud rev / OP | **24,768 / 8,814** (Cloud op마진 35.6%, YoY **+82%**) |
| Capex | 44,924 (YoY ~2×) |
| RPO | 514bn |
| 주가 반응 | 발표 직후 **flat** (콜 진행 중) |

파생: 2026Q1→Q2 매출 QoQ **+9.0%**. Ex-지분이익 영업 EPS ≈ **$2.61** (pretax 39,722 × (1−19.1%) / 12,309).

## 2. 채점: FROZEN 모델(가중) vs ACTUAL
| 층 | 모델 | Actual | 오차 | 비고 |
|---|---:|---:|---:|---|
| **매출** | 115,940 | 119,796 | **−3.2%** | 컨센(116,738)도 −2.6%. Actual이 컨센 상회(+2.6%). Cloud +82% 상방 미반영 |
| **영업이익(OP)** | 40,041 | 40,770 | **−1.8%** | ★거의 적중. OP기반 접근 정당성 입증 |
| **op마진** | 34.5% | 34.0% | +0.5pp | 소폭 과대 |
| **영업 EPS proxy** | 2.79 | 2.61(ex-gain) | +6.9% | 우리 세율 16% vs 실제 19.1% → proxy 소폭 상향편의. cf. Street adj 2.87 대비 −2.8% |
| **GAAP EPS** | (예측 안 함) 2.79 | **9.11** | −69.4% | **= OI&E 스윙 (f)-1 발화**. 평가이익 99,031 = OP의 2.4배 |
| **희석주식수** | 12,238 | 12,309 | −0.6% | 경미 |

**해석**: 매출은 컨센과 함께 하회(Cloud 초가속을 아무도 충분히 못 잡음); OP는 −1.8%로 최고의 층; 영업 EPS는 ±3~7% 존; GAAP EPS는 100% OI&E. **실제 ex-gain 영업 EPS $2.61은 Street adj 컨센 $2.87을 하회** — 즉 "청정 영업 기준으론 오히려 미스"(Q1 선례 반복). 우리 $2.79는 컨센보다 실제 $2.61에 더 가까웠음(|0.18| < |0.26|). 주가 flat = 시장이 $9.11 GAAP을 OI&E로 간파하고 영업·capex로 판단 → 위스퍼 $3.10 대비 "good but priced-in".

## 3. 4-lever generic 귀인
1. **매출 lever (−3.2%, 주 오차원)**: Google Cloud +82%(우리/컨센 ~60% 가정) 초과 가속. generic이 총매출 top-down이라 세그먼트 가속을 구조적으로 못 봄. QoQ +9.0% (계절 ~+6%·우리 +5.5% 초과).
2. **op마진 lever (+0.5pp)**: 34.5% vs 34.0% — 거의 정확, 소폭 과대.
3. **OP→NI 전환 lever**: (a) OI&E 지분이익 99,031 = GAAP 왜곡 전부(설계상 제외 → 리스크밴드, 앵커 수정 금지). (b) 세율 16% vs 실제 19.1% → 영업 EPS proxy +6.9% 상향편의(작은 앵커 수정 여지).
4. **주식수 lever (−0.6%)**: 무의미.

## 4. 재무제표(10-Q)로 잡을 수 있는 것 / 모델 개선안
- **Cloud 가속 (최대 미스)**: 10-Q 세그먼트표(Cloud 24,768 / OP 8,814 / 35.6%마진) + RPO 514bn(선행지표) → 총매출 성장 가정 상향 또는 **경량 세그먼트 오버레이(Cloud 성장 드라이버)** 검토. 단 generic top-down 설계 한계 = 구조적. `NOTICED`.
- **세율 앵커 16% → ~19%**: 10-Q 실효세율 reconciliation로 갱신(작은 EPS lever). 단 이번 19.1%는 지분이익 세금 포함 → ex-gain 실효세율 별도 확인 필요.
- **OI&E**: 10-Q "gain on equity securities" 라인 + 비상장 지분 주석(Anthropic/SpaceX) → 리스크밴드 계수. **앵커 수정 아님**(예측 불가). (f)-1 확정 발화.
- **Capex/FCF**: 10-Q 현금흐름표 FCF → (f)-2 검증(capex 44,924, YoY 2×).

## 5. Codex 실행 요청 (공동 작업)
1. **10-Q 발행 후(~2주)**: `pipeline/edgar_fetcher.fetch_companyfacts(1652044)` 전체 blob로 **2026Q2 as-filed 행 추가**(rev 119,796 / NI 112,193 / diluted 12,309 / as-filed EPS 9.11 / period_end 2026-06-30 / accn 10-Q). `scripts/build_generic_actuals.py --cik 1652044 --fye-month 12 --start 2024Q2 --end 2026Q2` → 9분기 무결성 재검(FY 항등식은 FY2026 미완이라 스킵). *릴리스 값은 이미 최종이나, actuals-block은 same-accession 규율상 companyfacts 기준으로 넣을 것.*
2. **skill_metrics**: 컨센 대비 surprise 방향 적중 산출(매출·OP·adj-EPS). GAAP EPS는 제외(OI&E). backtest N=7→8 갱신(EPS bias는 2026Q2 OI&E로 더 악화 예상 — 정상, 라벨 유지).
3. **세율 앵커** 검토(16%→~19%) — ex-gain 실효세율 확인 후 소폭 조정 여부 결정(human-owned, 단독 변경 금지).
4. 이 채점을 `HANDOFF_CODEX_efe_q2_2026_googl_POSTPRINT.md`(본 파일)로 커밋 + 메모리 갱신.
5. **6축 교차검증**: Cowork 채점 수치를 독립 재현(모델 40,041 vs actual 40,770 등).

## 6. 어닝콜 채점 (콜 종료, 2026-07-22)
콜 팩트 → 우리 (c)/(e) 예측 채점:
- **Capex 2026: $180-190bn → $195-205bn 상향**(60% 서버 / 40% DC·네트워킹), 2027 "increase significantly", TPU 시스템 매출 대부분 2027. → **(c) 적중**(유지~상향·bias 상향 정확).
- **FCF −$5.9bn**(OCF 39.1 − capex 44.9). → **(f)-2 적중**(FCF 급감).
- **영업이익률**: FY 가이드 없음, CFO Ashkenazi "3P 캐파 사용으로 3Q 단기 소폭 마진 압박". → **(c) 적중**(유지~신중 톤).
- **Cloud**: +82% $24.8bn, 백로그 +$50bn QoQ → **RPO $514bn**(24개월 내 ~50% 인식), 공급제약. → **(e)② 적중**.
- **AI 수익화**: AI Overviews+AI Mode 통합, **AI Mode 1B MAU**, Gemini 950M MAU, API 22B tokens/min(전분기 16B). → **(e)③ 적중**.
- **OI&E/Anthropic**: "unrealized gains on equity securities" 비영업 프레이밍. → **(e)④ 적중**.
- **반독점**: 콜에서 유의미 언급 없음 → (e) 부분(리스트했으나 비이벤트).
- **주가: 애프터마켓 −3.65% ($329.43)** — GAAP EPS $9.11·Cloud +82%에도 **capex 상향에 하락**. → **핵심 테제 적중**: "주가를 가르는 건 EPS가 아니라 capex/FCF 축"(위스퍼 $3.10 priced-in + capex 쇼크 = sell-the-news).

**(c)/(e) 종합: 사실상 전 항목 적중, 반독점만 비이벤트.** 사전등록 (f)-2(capex/FCF가 EPS보다 스톡 무버)가 주가 −3.65%로 정확히 발화.

## 7. 개선점 (확정) — human/Codex owned, 단독 구현 금지 표기
1. **[최우선] Cloud 가속 블라인드스팟** (매출 −3.2% 주원인). generic 총매출 top-down은 Cloud +82%를 구조적으로 못 봄. 옵션: (a) **RPO/백로그를 선행지표로**(RPO $514bn, +$50bn QoQ, 24개월 ~50% 인식 → 분기 ~$32bn Cloud 런레이트 산출 가능); (b) 경량 2-세그먼트(Services/Cloud) 오버레이로 Cloud 성장 드라이버 명시. 단 "no 바텀업 false precision" 설계원칙과 트레이드오프 → **설계 논의 필요, `NOTICED`, 단독 구현 금지**.
2. **세율 앵커 16% → ~19% 검토** (op-EPS proxy +6.9% 상향편의 원인). 단 Q2 실효 19.1%엔 지분이익 세금 포함 → 10-Q에서 **ex-gain 실효세율** 확인 후 소폭 조정. **human-owned**.
3. **op_margin 앵커 34.5% ≈ 실제 34.0%** — 검증됨. 34.0%로 미세 하향 여지(선택). OP −1.8%는 유지 가치.
4. **OI&E = 리스크밴드, 앵커 아님** — $99bn 예측불가 확정. GAAP EPS는 포인트추정에 절대 미반영, 라벨/밴드로만. 방법론 검증 완료.
5. **capex/FCF = 실제 스톡 시그널** — BVT 밸류에이션 브리지 측에 capex/FCF 궤적을 핵심 민감도로 노출(EPS 아님). 크로스레포 노트.
6. **_slot 계절 phase (기존 오픈)** — 엔진 정렬 fix 시 계절 벡터 가능. 단 실제 QoQ +9.0%(Cloud발)라 계절 fix만으론 이번 미스 못 잡음 → Cloud 블라인드스팟이 상위.

## 8. Codex 평가 요청 (6축)
정확성(채점 수치 독립 재현: 모델 OP 40,041 vs actual 40,770, 매출 115,940 vs 119,796, ex-gain adj EPS 2.61 등), 건전성(OP/adj-EPS/GAAP 3분리 유지, OI&E 리스크밴드), 회귀안전(9Q sha·전체 그린), 범위규율(§7 중 단독 구현 금지 항목 준수), 검증가능성(§1 릴리스 수치 ↔ 10-Q 대조), 유지보수성. §5 실행요청(10-Q as-filed 2026Q2 행·skill_metrics surprise·세율)과 §7 개선점을 검토·확정 후 커밋. **Cowork 채점 주장 그대로 믿지 말고 독립 재현.**

## 9. Codex 독립 재현 및 실행 결과 (2026-07-28)

### 9.1 SEC same-accession actual
- SEC Company Facts 전체 blob를 live refresh하고 `build_standalone_quarters`로 재구성했다.
- 2026Q2는 **10-Q accession `0001652044-26-000071`**, filed 2026-07-23, period end 2026-06-30이다.
- same-accession 값: revenue **119,796**, net income **112,193**, diluted shares **12,309M**, as-filed diluted EPS **9.11**. 파생 EPS `112,193 / 12,309 = 9.1147`로 정합한다.
- SEC 10-Q 원문: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm

### 9.2 동결 모델 채점 독립 재현
| 층 | 동결 확률가중 | Actual | signed error | 판정 |
|---|---:|---:|---:|---|
| 매출 | 115,940 | 119,796 | **−3.219%** | 재현 |
| OP | 40,041 | 40,770 | **−1.788%** | 재현 |
| OP margin | 34.536% | 34.033% | **+0.503pp** | 재현 |
| 영업 EPS proxy | 2.79 | 2.610 | **+6.90%** | 재현 (`(138,753−99,031)×(1−19.1%)/12,309`) |
| GAAP EPS | 비교 제외 | 9.11 | N/A | OI&E 리스크밴드 |
| 희석주식수 | 12,238M | 12,309M | **−0.577%** | 경미 |

OP/adj-EPS/GAAP의 3층 분리를 유지한다. $9.11 GAAP EPS는 $99,031M 지분증권 평가이익이 포함된 실제값으로 actuals/backtest에는 GAAP 라벨로 보존하지만, 동결 영업 EPS proxy의 성패 판단에는 사용하지 않는다.

### 9.3 9Q actuals 및 backtest N=8
- `build_generic_actuals.py --cik 1652044 --fye-month 12 --start 2024Q2 --end 2026Q2`: **9개 분기 연속성 green**.
- FY2025 항등식은 불변: revenue 402,837(10-K 402,836 대비 반올림 1), NI 132,170. FY2026은 4Q 미완이라 스크립트가 정상 스킵했다.
- 전방 seed는 2026Q1, `window.start_quarter`는 **2026Q2 그대로**다. Q3 재시드/롤은 하지 않았다.
- backtest N=8: revenue MAPE **4.976%**, bias **+0.982%**, naive RW MAPE **6.693%**, MASE **0.733**, Theil U2 **0.865**.
- GAAP EPS backtest: MAPE **19.157%**, bias **−18.755%**, naive RW MAPE **20.901%**, MASE **1.164**, Theil U2 **1.428**. 2026Q1·Q2 OI&E로 bias가 악화한 예상 결과이며 **모델실패가 아닌 구조적 라벨 차이**다.
- 현재 generic historical actual 계약에는 OP가 없어 **역사 OP MAPE는 산출 불가**다. OP는 위 2026Q2 동결 단일점 MAPE 1.788%로만 채점했다. 이번 사후채점 범위에서 스키마/엔진을 확장하지 않았다.
- backtest의 Q2 역사 예측 매출은 calendar-slot 규약으로 115,390.8(5.0% 성장)이며, 동결 forward 값 115,940(첫 step 5.5%)과 구분한다.

### 9.4 컨센 surprise 방향
| 층 | 모델 vs 컨센 | Actual vs 컨센 | 방향 적중 |
|---|---|---|---|
| 매출 | 115,940 < 116,738 | 119,796 > 116,738 | **미스** |
| OP | 직접 컨센 없음 | — | **N/A (미채점)** |
| adj/영업 EPS | 2.79 < 2.87 | 2.61 < 2.87 | **적중** |
| GAAP EPS | 설계상 제외 | OI&E 포함 9.11 | **제외** |

OP에 직접 컨센서스가 없다는 동결 문서의 계약을 유지했다. Q1 마진을 적용한 ~$42bn은 컨센서스가 아니므로 surprise 기준으로 대체하지 않았다.

### 9.5 세율·설계 판단
- 10-Q는 Q2 ETR **19.1%**가 전년 16.9%에서 상승한 주원인을 지분증권 미실현이익에 대한 법정세율 deferred-tax liability라고 명시한다.
- 공시는 ex-gain 영업 ETR을 별도 제공하지 않는다. 따라서 19.1%를 영업 proxy 앵커로 곧바로 이식할 근거가 부족하며 **16% 앵커는 human-owned 미변경**으로 유지한다.
- Cloud/RPO 오버레이와 세그먼트 설계는 `NOTICED`만 유지했고 구현하지 않았다.

### 9.6 회귀·provenance
- FROZEN 파일 SHA256 **`cdbccf30dc54006ab26431b84a7877eb105afc581a979e029e28fa96df87f2f8` 불변**. 헤더의 pre-print profile SHA `0990edd5…`도 소급 수정하지 않았다.
- post-actual `profiles/googl.generic.yaml` SHA256은 **`3560c62a135e600aacb4a7b73071adf0168e463393612d2927449df25428cf76`**로 변경됐다.
- SK Hynix 9Q host canonical SHA256 **`b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7` MATCH**.
- 국소 테스트: `tests/test_googl_profile.py tests/test_edgar_fetcher.py tests/test_skill_metrics.py` **26 passed**.
- 전체 suite: **225 passed, 1 failed**. 실패는 기존 미커밋 TSLA actual이 채워진 상태에서 발표 전 빈 템플릿을 기대하는 `tests/test_tsla_postmortem.py::test_template_loads_but_cannot_score_before_release`이며 GOOGL 변경과 무관하다. 따라서 전체 green으로 표기하지 않는다.
- actual/profile 변경 커밋: **`9ab839f`** (`data: add GOOGL 2026Q2 as-filed actual`). 동결 커밋 `aecd9207`과 분리했다.
