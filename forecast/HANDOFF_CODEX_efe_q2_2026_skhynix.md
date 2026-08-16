# HANDOFF — EFE / SK하이닉스 2026Q2 사후채점 & 모델 보정

**From**: Cowork (Claude) · 2026-07-29 (실적발표·컨콜 당일)
**To**: Codex CLI (Windows host)
**Repo**: `F:\dev\Portfolio\earnings-forecast-engine` · HEAD `f49942a`
**선행 문서**: `reports/sk_hynix_q2_2026_scorecard.md` (본 핸드오프의 사실·수치 근거. 먼저 읽을 것)

---

## §0. 이 핸드오프의 성격

Cowork 세션에서 **실측 수집 + 채점 계산 + 진단 가설 수립**까지 완료했다. 코드는 한 줄도 건드리지 않았다.
Codex가 할 일은 **(1) 채점의 코드화·재현성 확보, (2) 진단 가설의 구현, (3) 6축 교차검증**이다.

**사용자 승인이 필요한 항목은 §7에 분리했다. §7 미결 상태에서 T2·T3·T4를 구현하지 말 것.**

---

## §1. 확정 사실 (2026-07-29 발표 + 컨콜)

```
매출        79조 3,187억   (+50.9% QoQ, +256.8% YoY)
영업이익    60조 5,426억   (+60.8% QoQ, +557.2% YoY)  OPM 76.33%
순이익      93조 9,226억   (+133% QoQ, +1,242% YoY)   NPM 118.4%
EPS         ≈133,100원     (회사 미공시 — NI ÷ 705,656,476주 파생)
H1 누계     매출 131.9조 / OP 98.2조  → 역산 Q1 OP 37.66조 (OPM 71.6%)
현금        88조 (+33.6조 QoQ) / 차입 18.6조 / 순현금 69.4조
D램 ASP     +약 30% QoQ      낸드 ASP  +50%대 중반 QoQ
```

컨콜: HBM4 2Q 양산 출하 개시→**하반기 본격 확대** · HBM4E 1H26 샘플 완료(1nm) · **2026 capex 40조원 후반(상향)** · M15X 가속 / 용인1팹 클린룸 2027 초 / P&T7 / 신규 낸드 M17 · 321단 낸드 연말 국내 캐파 ~50% · 고객 10여 곳 LTA · 2026 업계수요 D램 20%대 중반·낸드 10%대 후반, 공급 여전히 부족 · 하반기 출하·가격 **동반** 개선.

**컨센서스(KR 22개사, 7/27)**: 매출 83.646조 / OP 63.6594조. 개별 OP 추정 레인지 60.114조(메리츠, 최저)~71.446조(키움, 최고) — **실측은 컨센 하단 근처.**
**주가**: 7/28 약 −14% → 7/29 **−9.61%, 종가 1,401,000원** (장중 저가 1,246,000원, KOSPI −5.98%).

> ⚠️ **부분 확정**: 세전이익 **122조 7,084억원**, 법인세 **28조 7,858억원**은 회사 공시 수치 인용 보도로 확인됐다. 원장 나눗셈 기준 유효세율은 **23.4587%**다. 다만 당기·이연법인세 구분과 영업외손익 내역은 반기보고서 전까지 미확정이므로, 세율 앵커 16.4%와 below-OP 세무 기준은 변경하지 않는다.

---

## §2. 채점 대상 아티팩트 & 프로비넌스

| | |
|---|---|
| 예측 파일 | `reports/sk_hynix_20260710.{md,html,xlsx,pdf}` — **git 미추적** |
| mtime | 2026-07-10 09:01:03 UTC |
| 구동 프로파일 | `profiles/sk_hynix.yaml` @ `4ebeb7c` (2026-07-10 18:26 KST), sha256 `a90d840f61c39dec3c7853122884639d1a2efe7e97e77bcdc29b17d4f7dfbc90` |
| 워킹트리 | 프로파일 clean (7/10 이후 무변경 확인) |
| 리드타임 | 19일 |

**ex-ante 등급**: 5종목(`*_FROZEN.md` 규약)보다 **한 단계 낮음**. 예측 벡터는 커밋되어 있으나 산출물 자체는 미추적. **채점 문서에 이 한계를 반드시 명시할 것 (이미 스코어카드 §0에 기재).**

### 모델 출력 (2026Q2, KRW bn) — `reports/sk_hynix_20260710.xlsx`
```
scenarios : bear 69,170.87 / base 79,070.27 / bull 81,539.60 / weighted 77,212.75
forecast  : rev 77,212.75  op 60,426.29  ni 49,824.89  eps 70,607.86   (weighted)
base EPS  : 72,669.1  (md 컨센 갭 표)  → base OP 역산 61,972 (세율 .164, net_int -.008)
EPS band  : 54,516 ~ 86,699  (±22.79%, mad k=1.5)
```

---

## §3. 스코어카드 (계산 완료 — 재현만 하면 됨)

| 지표 | 모델(wtd) | 실측 | 오차 | 비고 |
|---|---:|---:|---:|---|
| 매출 | 77,213 | **79,319** | **−2.66%** | base 79,070 → **−0.31%** |
| 영업이익 | 60,426 | **60,543** | **−0.19%** | base 61,972 → +2.36% |
| OPM | 78.26% | **76.33%** | **+1.93pp** | 과대 |
| 순이익 | 49,825 | **93,923** | **−46.95%** | |
| EPS | 70,608 | **≈133,100** | **−46.95%** | base → −45.40% |

- 매출 시나리오 밴드 **PASS** (bear 69.2 < 79.3 < bull 81.5)
- EPS below-OP 밴드 **FAIL** (필요 반폭 88.5% vs 설정 22.79%)
- 컨센 대비 서프라이즈 방향 **HIT ×2**: 우리 매출 −5.47% vs 실측 −5.17%(gap-of-gap **0.30pp**) / 우리 OP −5.08% vs 실측 −4.90%(**0.18pp**)

---

## §4. 진단 가설 (Codex가 검증·반박할 대상)

### H1 — 매출 적중은 **상쇄오차**다 (P0, 가장 중요)
```
드라이버        모델 base      실측            판정
DDR ASP QoQ     +60%          D램 blended +30%   과대 ~2배
NAND ASP QoQ    +72%          +50%대 중반        과대
D램 bit QoQ     +5%           역산 +9~16%        과소 2~3배
NAND bit QoQ    +4%           상동               과소
```
매출 +50.9% QoQ ÷ blended ASP(+30~38%) → **implied bit +9~16% QoQ**. ASP 과대 × bit 과소가 상쇄되어 −0.31%가 나왔다.
**⭐ 신규 룰 후보**: *contract price 지수(TrendForce) ≠ 회사 실현 blended ASP.* LTA 비중이 큰 발행사는 계약가 변동의 일부만 분기 내 실현. **2026Q2 실측 pass-through ≈ 0.5.** 회사도 "2분기 출하 시점·포트폴리오 구성이 가격에 영향"(HBM4 물량 하반기 쏠림)이라고 명시.
→ **3Q 벡터는 이 두 오류를 상속 중이다.** 롤 전에 반드시 분해 보정.

### H2 — EPS −47%는 모델 실패가 아니라 **밴드 설계 실패** (P0)
below-OP 순유입 실측 **+33.38조** vs 모델 **−10.60조**. 원인: **키옥시아 SPC1 지분매각(6월 완료)** 누적투자이익 ~40조 영업외 인식(추정). 현금 +33.6조 QoQ와 정합.
설계 원칙("below-OP는 점추정 미포함, 별도 밴드")은 **옳았다** — 덕분에 "OP까지 정확, 그 아래가 튀었다"로 즉시 분해됐다. 실패는 **밴드가 담는 대상**에 있다: 8Q MAD 밴드는 반복성 FX·순금융만 담고, **일자가 확정된 대형 자산처분이익**은 통계 분산이 아니라 **식별 가능한 이벤트**다. SPC1 매각은 6월 완료 = **7/10 예측 시점에 인지 가능했다.**
**재발 3회 확정**: GEV(이연법인세 환입, NI≫OP) · GOOGL(OI&E 지분평가손익) · SK하이닉스(자산처분이익). → **구조적 결함.**

### H3 — 유효세율 (P2, **부분 해제**)
세전이익 **122조 7,084억원**, 법인세 **28조 7,858억원** 기준 유효세율은 원장 full precision으로 **28,785.8 / 122,708.4 = 23.4587%**다. 기존 추정 세율 행은 폐기한다.
**세율 앵커 16.4%는 반기보고서의 당기·이연법인세 구분 확인 전까지 변경 금지.** 확정된 것은 분기 실효세율과 파생계산이며, 반복 가능한 세무 기준은 아직 확정되지 않았다.

### H4 — OPM +1.9pp 과대 (P2)
cross-stock "op_margin 앵커 과대" 편향과 **방향은 동일**하나 크기가 훨씬 작다(GEV 9.2→5.88, TSLA 6→1.4 vs SK 78.4→76.3). SK는 generic 경로가 아니라 **메모리 경로(세그먼트 GM 체인)**다.
→ **cross-stock 룰을 그대로 이식하지 말 것.** 별개 원인(초고마진 구간에서 GM 체인이 상단 수렴) 가설을 먼저 검증.

---

## §5. 작업 지시

### T1 (P0) — 채점 코드화
- `inputs/sk_hynix_q2_2026_actual.yaml` 신규: §1 실측 + 출처 URL + `eps_derived: true` 플래그 + 미확정 필드(pretax/tax/below_op)는 `null`.
- `scripts/score_sk_hynix_q2_2026.py` 신규.
  - ⚠️ `engine/generic_postmortem.py`는 **generic 전용 4레버**다. SK하이닉스는 **메모리 경로 5레버**(매출 / 매출총이익률 / opex 전환 / 세금·금융 / 주식수 — `reports/sk_hynix_20260710.html` attribution 워터폴 참조). **generic 스코어러를 억지로 재사용하지 말 것.** 기존 백테스트 귀인 함수를 재사용하되, 없으면 최소 구현.
  - 앵커 파일(`reports/sk_hynix_20260710.xlsx`) sha256 가드 + **읽기 전용**. `score_tsla_q2_2026.py` 패턴 준용.
  - 잔차 0 검증(레버 합 = 총 EPS 오차) 필수.
- 출력은 `reports/sk_hynix_q2_2026_scorecard.md`에 `--append` 멱등 마커로 붙일 것 (문서 본문은 수정 금지).
- **수용기준**: 잔차 |ε| < 1e-9 · 앵커 파일 무변경 · 신규 테스트 green.

### T2 (P0) — below-OP 이원화 (§7-Q1 승인 후)
`risk_band`(반복성, MAD 유지) 옆에 **`below_op_events`** 블록 신설:
```yaml
below_op_events:
  - id: "kioxia_spc1_disposal"
    as_of_date: "2026-06-30"          # 인지 시점 (lookahead 가드 대상)
    target_period_label: "2026Q2"
    kind: "asset_disposal_gain"
    amount_krw_bn: 40000              # 추정 — 반기보고서로 교체
    probability: 0.8
    confidence: "estimated"           # estimated | confirmed
    source: "메리츠증권 추정 2026-07-28"
```
- **overlay와 명확히 구분할 것**: overlay는 밸류에이션 레이어 전용 annotation(EPS 무영향). `below_op_events`는 **EPS 시나리오에 조건부로 들어간다** — 단, **점추정에는 넣지 말고 "이벤트 조정 EPS"를 별도 열/시나리오로 출력**(기본 EPS 점추정은 불변).
- `as_of_date < target 분기말` lookahead 가드는 overlay와 동일 로직 재사용.
- **회귀 불변식**: 이벤트 블록 부재 시 기존 출력과 **bit-identical**.

### T3 (P1) — ASP pass-through + bit 재보정 (§7-Q2 승인 후)
- 프로파일에 선택적 `asp_pass_through` 계수(세그먼트별) 도입. 부재 시 1.0 = 기존 동작 bit-identical.
- 2026Q3~2027Q2 벡터를 **ASP 하향 × bit 상향**으로 재보정. **매출 합계가 크게 흔들리지 않아야 한다** — 이번 분기가 증명한 것은 "매출 레벨은 맞고 분해가 틀렸다"이므로, 보정 후 2026Q2 재현 매출이 79.3조 ±1% 밖으로 나가면 보정이 잘못된 것이다. **이 재현 테스트를 수용기준으로 걸 것.**

### T4 (P1) — forward window 2026Q3 롤 (§7-Q3 승인 후)
- seed = 2026Q2 실적(매출 79,318.7 / OP 60,542.6). **EPS/NI는 키옥시아 오염 → seed에서 OMIT** (GEV 2025Q4·2026Q1 처리 전례 동일).
- ⚠️ **백테스트 커플링**: `run_backtest`가 base의 `bit_growth_qoq[0]` / `other[0]` / `margins` / `finance`를 methodology 가정으로 먹는다. T3가 bit[0]을 바꾸므로 **이번엔 회피 불가** → generic 경로에 이미 있는 **`backtest_methodology` 블록을 메모리 경로에도 이식**하는 것이 선결 조건. (generic: `schemas/generic.py`의 `backtest_methodology.revenue_growth_qoq`)
- **9Q 백테스트 bit-identical 유지**가 절대 조건. 검증: `scripts/verify_9q_sha.py` — host(CPython≥3.12)는 `b979d79f…f6e7` MATCH 기대.

### T5 (P2) — 세율: **아무것도 하지 말 것.** 반기보고서 대기. TODO 주석만.

### T6 (P2) — KR 컨센서스 vintage
7/27자 22개사 컨센(매출 83.646조 / OP 63.6594조, CV 3.9%/4.7%)이 한경 기사로 확보됐다 = **README P1 "KR 브로커 컨센서스" 워크스트림의 첫 실vintage.** `inputs/`에 vintage 레코드로 적재하고 수집 경로를 문서화. 컨센 skill 표본 N=4 → 5 확장 후보.

---

## §6. 6축 교차검증 요청 (구현 전 수행)

1. **사실·수치**: §1·§3 숫자가 1차 출처(회사 보도자료 / prnewswire 2Q26 릴리스)와 일치하는가. EPS 파생치의 분모(705,656,476주)가 2026Q2에도 유효한가 — 자사주·희석 변동 확인.
2. **회계 해석**: 키옥시아 이익이 **당기손익(영업외)** 인가 **기타포괄손익**인가. 지분 매각 차익 vs CB 평가이익의 구분. NI 118% 마진이 지배주주 귀속 기준인가 연결 총액 기준인가. → H2의 전제가 틀리면 T2 설계가 흔들린다.
3. **모델 커플링**: T3·T4가 `run_backtest`의 methodology 소비 경로를 통해 9Q 백테스트를 움직이는가. `backtest_methodology` 이식이 정말 선결 조건인가, 아니면 더 작은 수술이 있는가.
4. **통계**: T2로 밴드를 손댈 때 **1개 관측치에 과적합**하지 않는지. MAD 밴드 자체는 건드리지 않는 설계가 맞는가.
5. **대안 가설**: 매출 −0.31%가 상쇄오차가 아니라 진짜 정확도일 가능성? (D램 blended ASP +30%가 HBM 포함 blended인지 conventional만인지에 따라 implied bit가 달라진다 — **이 구분이 H1의 급소다. 반드시 확인.**)
6. **최소성**: T1~T4가 요청 범위를 넘지 않는가. 인접 코드 리팩터 금지, `NOTICED BUT NOT TOUCHING:` 로그로 대체.

---

## §7. 사용자 결정 필요 (Codex는 여기서 멈추고 질문할 것)

- **Q1 (T2)**: below-OP 이벤트 레지스터를 도입할 것인가? 도입 시 EPS **점추정은 불변**으로 두고 "이벤트 조정 EPS"를 별도 출력하는 안에 동의하는가?
- **Q2 (T3)**: ASP pass-through 계수 도입 및 3Q 벡터 재보정 — pass-through 초기값 **0.5**(2026Q2 실측)로 시딩할 것인가, 아니면 더 긴 표본으로 추정할 것인가?
- **Q3 (T4)**: forward window를 2026Q3로 롤할 것인가? 롤 시 3Q 매출 뷰를 **street 101조 수준으로 올릴 것인가, 우리 92.7조를 유지할 것인가** — 이건 가정값이므로 **사용자 몫**이다. (§5-T3 재보정이 자연스럽게 올려줄 가능성이 높으니, 먼저 T3를 돌려보고 결과를 보고 결정하는 순서를 권장)
- **Q4**: SK하이닉스에도 5종목과 동일한 `*_FROZEN.md` 규약(타임스탬프+HEAD+profile sha 헤더, git 추적)을 다음 분기부터 적용할 것인가?
- **Q5**: 현재 워킹트리가 매우 더럽다(9 modified + 20 untracked, 5종목 세션 잔재). **clean 커밋 베이스 확보가 T2~T4의 선결 조건**이다 — 먼저 커밋할 것인가?

---

## §8. 가드레일 (전 작업 공통)

- 9Q 백테스트 **bit-identical** — `verify_9q_sha.py`, host = `b979d79f…f6e7`.
- `reports/sk_hynix_20260710.*` 및 5종목 `*_FROZEN.md` **수정 금지**(사후 조작 = 채점 무효).
- 프로파일 값 변경은 **반드시 주석에 출처·일자·근거** 병기 (기존 CONFIRMED 주석 스타일 준수).
- `pytest -q` green + `python cli.py --company sk_hynix --dry-run` 정상.
- 신규 옵션 필드는 **부재 시 기존 동작과 bit-identical**.
- 코드·주석·설정은 영어, 사용자 대면 리포트만 한국어 (CLAUDE.md 규약).

---

# §9. 결정 회신 (2026-08-02, 사용자 승인 완료)

Codex의 §7 질의에 대한 확정 답변. **이 섹션이 §7보다 우선한다.**

## §9.0 ⚠️ HEAD 정정 + T0 신설 (선결)

작성 시점 HEAD `f49942a`는 **stale**. 현재 HEAD = **`23b1d97`** (2026-08-01 20:49). 사이 3커밋:
```
aabf905 docs: correct disclosure test failure attribution
2a26780 docs: require auditable primary-source citations
23b1d97 docs: mark Phase B text ingestion dormant   ← cli.py +15/-2, pipeline/disclosure_loader.py, ai/extractor.py, pyproject.toml
```

**T0 (P0, T1보다 먼저) — 앵커 재현 게이트.**
채점 앵커는 7/10 산출물인데 그 사이 `cli.py`가 변경됐다. 현재 HEAD에서 앵커가 재현되지 않으면 채점의 근거가 약해진다.
```
python cli.py --company sk_hynix --dry-run
```
**기대치 (2026Q2)**: base rev `79,070.27` · weighted rev `77,212.75` · weighted OP `60,426.29` · weighted NI `49,824.89` · weighted EPS `70,607.86` · EPS 밴드 `54,516 ~ 86,699`
- **재현 성공** → T1 진행.
- **불일치** → **T1 중단.** `23b1d97`의 `cli.py` diff를 격리해 원인을 규명하고 보고할 것. 앵커를 현재 출력에 맞춰 고쳐 쓰는 것은 **금지**(사후 조작).
- 9Q 백테스트 sha도 함께 확인: `scripts/verify_9q_sha.py` → host 기대 `b979d79f…f6e7`.

## §9.1 Q1 (T1) — **승인**
범위(actual YAML / 채점 스크립트 / 테스트 / 스코어카드 멱등 append) 그대로. **단 T0 통과가 선행 조건.**

## §9.2 Q2 (T2) — **승인, 제안한 설계 그대로**
기본 EPS 점추정 **불변** + "이벤트 조정 EPS" **별도 출력**. 이 분리가 핵심인 이유: 점추정에 이벤트를 넣는 순간 "below-OP는 점추정에서 제외" 원칙이 무너지고, 이번 분기에 실제로 작동한 진단력(“OP까지 정확 / 그 아래가 튀었다”는 즉시 분해)을 잃는다. 회귀 불변식(이벤트 블록 부재 시 bit-identical) 유지.

## §9.3 Q3 (T3) — **0.5 즉시 시딩 기각. 8~10Q 실측 추정을 먼저 할 것.**

n=1 과적합 회피 + 사이클 국면별 계수 차이 확인이 목적. **T3를 T3a(추정) → T3b(구현)로 분할한다.**

### T3a — pass-through 실측 추정 (신규, T3b의 선결)
1. **데이터 수집**: SK하이닉스 분기 실적발표 자료의 공시 **"D램/낸드 ASP 전분기 대비 %"**, 2024Q1~2026Q2 (10개 분기). 1차 출처(회사 IR 자료·보도자료)만 사용. `inputs/sk_hynix_asp_disclosed.yaml`에 출처 URL·인용문과 함께 적재.
2. **대조군**: `profiles/sk_hynix.yaml`의 `historical_drivers[q].ddr_asp_qoq` / `nand_asp_qoq` (= TrendForce 계약가).
3. **추정**: 단순 비율(`realized/contract`)은 **하락 국면에서 분모가 0에 가까워지면 폭발**한다 — 쓰지 말 것. `log(1+realized) = β·log(1+contract)` 원점 통과 회귀 + **Theil-Sen 로버스트 대조**를 병행하고 둘 다 보고.
4. **국면 분리**: 급등 국면(2025Q3~2026Q2)과 완만/하락 국면의 β를 **따로** 추정. 두 β가 유의하게 다르면 **단일 상수 계수는 부적절**하다는 결론이며, 그 사실 자체를 보고할 것 (그 경우 T3b 설계를 국면 조건부로 바꿔야 한다).
5. **⚠️ 순환 경보 (반드시 처리)**: `historical_drivers["2026Q1"]`은 프로파일 주석대로 **SK 실측 blended ASP(+mid-60%)에서 역산된 값**이다. 이 분기를 대조군에 넣으면 **자기 자신과 회귀**하게 된다. **2026Q1은 추정 표본에서 제외**하고, 다른 분기에도 동일한 역산 오염이 있는지 주석을 전수 점검할 것.
6. **산출**: 추정 β(세그먼트별·국면별), 표본 수, 신뢰구간, 제외 분기와 사유. **여기서 멈추고 보고.** 사용자 확정 전에 T3b 진입 금지.

### T3b — 구현 (T3a 보고 + 사용자 확정 후)
기존 §5-T3 내용 유지. 수용기준(**보정 후 2026Q2 재현 매출이 79.3조 ±1% 이내**)은 그대로 필수.

## §9.4 Q4 (T4) — **Codex 권장 순서 채택**
T3b 결과를 본 뒤 롤 여부와 매출 뷰를 결정한다. **92.7조/101.2조는 지금 확정하지 않는다** — T3b가 bit를 올리면 자연히 움직일 값이므로, 지금 고정하면 T3b 결과를 사후정당화하게 된다.

## §9.5 Q5 (FROZEN 규약) — **적용. 2026Q3 예측부터.**
`reports/sk_hynix_q3_2026_forecast_FROZEN.md`에 5종목과 동일한 헤더(산출 타임스탬프 · git HEAD · profile sha256 · 컨센 기준선·출처일)를 내장하고 **git 추적**한다. 이번 분기 채점의 유일한 약점이 프로비넌스였고, 비용은 헤더 몇 줄이다. (자동화 편입은 별건 — `PROMPT_autofreeze_COMMON.md` 워크스트림에서 따로 다룬다.)

## §9.6 Q6 (워킹트리) — **Codex가 커밋한다. 단 아래 §10 계획대로만.**
"임의로 전체 커밋"이 위험하다는 Codex 판단은 옳다. 그래서 **경로를 명시한 커밋 계획을 제공**한다. §10 외의 파일을 커밋하지 말 것.

## §9.7 6축 교차검증 — **분할 실행 (Codex 제안 순서 수정)**
- **축 ①사실·②회계·⑤ASP 정의 → T1과 *동시*.** 이유: "D램 +30%가 HBM 포함 blended인지 conventional 한정인지"는 **T1의 actual YAML에 무엇을 어떤 정의로 기록할지를 이미 결정**한다. 뒤로 미루면 YAML을 다시 써야 한다.
- **축 ③커플링·④통계·⑥최소성 → T2 착수 직전.**

## §9.8 확정 실행 순서
```
T0 재현 게이트
  └ PASS → T1 (+ 6축 ①②⑤ 동시)  →  보고
       └ §10 커밋 계획 실행         →  보고
            └ 6축 ③④⑥            →  T2  →  보고
                 └ T3a 추정        →  보고 · 사용자 확정
                      └ T3b        →  보고
                           └ T4 (롤 여부·매출 뷰 = 사용자 결정)
```
각 단계 끝에서 **멈추고 보고**. 단계 건너뛰기 금지.

---

# §10. 커밋 계획 (사용자 승인 — 이 목록 밖의 파일 커밋 금지)

## 절대 규칙
- **`git add -A` / `git add .` / `git commit -a` 금지.** 반드시 **경로 명시** add.
- **`_to_delete/` 커밋 금지** — C7에서 `.gitignore`에 넣는다. 디렉터리 자체는 사용자가 직접 삭제한다(Cowork에서는 삭제 불가).
- **`.env` 커밋 금지** (기존 gitignore 확인만).
- 각 커밋 **직후 `pytest -q` green** 확인. 깨지면 그 커밋에서 멈추고 보고.
- C1·C2 이후 **forward 출력 회귀 0** 확인(nvda/tsla `weighted_quarterly`/`annual`이 커밋 전후 동일).
- 커밋 메시지는 기존 컨벤션(`fix:` `feat:` `docs:` `data:` `chore:`) 준수. **Co-Authored-By 트레일러 등 서명 추가 금지** (기존 히스토리에 없음).

## C1 — generic 계절 슬롯 픽스 (코드)
```
generic_cli.py
schemas/generic.py
tests/test_generic_backtest_methodology.py
```
`fix(generic): add calendar-slot backtest_methodology vector`
> forward 소비 경로는 불변, backtest만 캘린더 슬롯을 쓰도록 분리. GEV backtest 매출 MAPE 20.3%→2.93%, TSLA 11.7%→7.7%.

## C2 — 픽스 반영 산출물 재생성
```
reports/nvda_generic_forecast.json   reports/nvda_generic_forecast.md
reports/tsla_generic_forecast.json   reports/tsla_generic_forecast.md
```
`chore(reports): regenerate nvda/tsla generic forecasts after slot fix`

## C3 — generic 사후채점 인프라
```
engine/generic_postmortem.py   schemas/postmortem.py
scripts/score_tsla_q2_2026.py
inputs/tsla_q2_2026_actual.yaml   inputs/tsla_q2_2026_actual.filled.yaml
tests/test_generic_postmortem.py   tests/test_tsla_postmortem.py
```
`feat(postmortem): add generic four-lever post-earnings scoring`

## C4 — 프로파일 (GEV 신규 / TSLA 갱신)
```
profiles/gev.generic.yaml
profiles/tsla.generic.yaml
tests/test_tsla_profile.py
reports/gev_generic_forecast.json   reports/gev_generic_forecast.md
```
`feat(profile): add GEV profile and refresh TSLA assumptions`
> ⚠️ **`profiles/gev_q3_2026.dev.generic.yaml`은 제외**했다(`.dev.` = 실험용). 커밋이 필요하다고 판단하면 **커밋하지 말고 사유와 함께 보고**할 것.

## C5 — 동결 예측 & 스코어카드
```
reports/gev_q2_2026_forecast_FROZEN.md
reports/tsla_q2_2026_forecast_FROZEN.md
reports/ibm_q2_2026_scorecard.md
reports/sk_hynix_q2_2026_scorecard.md
```
`docs: add Q2 2026 frozen forecasts and scorecards`
> ⚠️ **FROZEN 파일은 내용 수정 없이 그대로 커밋.** 커밋 과정에서 한 글자도 바꾸지 말 것. sk_hynix 스코어카드에 T1 결과를 append하는 것은 **이 커밋 이후 별도 커밋**으로.

## C6 — 핸드오프 / 프롬프트 세트 (문서)
```
HANDOFF_CODEX_efe_q2_2026_gev.md      HANDOFF_CODEX_efe_q2_2026_tsla.md
HANDOFF_CODEX_efe_q2_2026_skhynix.md  HANDOFF_CODEX_efe_q2_2026_ibm.md   (modified)
HANDOFF_nvda2.md                       (modified)
HANDOFF_CODEX_doc_ingest_2026-07-31.md
HANDOFF_CODEX_efe_autopilot.md         HANDOFF_CODEX_efe_autopilot_P1.md
HANDOFF_CODEX_stock_selection_mecaro_2026-07-31.md
PROMPT_autofreeze_COMMON.md            PROMPT_autoprep_COMMON.md
PROMPT_codex_stock_selection_verdict.md
START-efe-q2-2026-gev.md   START-efe-q2-2026-googl.md   START-efe-q2-2026-ibm.md
START-efe-q2-2026-tsla.md  START-efe-q2-2026-txn.md
```
`docs: add Q2 2026 session handoffs and prompt sets`
> ⚠️ `START-efe-q2-2026-00-COMMON.md`가 워킹트리에서 사라졌다(7/29에는 있었음). **커밋 전에 존재 여부를 확인**하고, 없으면 **복구하지 말고 사실만 보고**할 것.

## C7 — gitignore
```
.gitignore   ( + `_to_delete/` 한 줄)
```
`chore: ignore session scratch directory`

## 커밋 후 보고 형식
커밋별 `git show --stat` 요약 + 최종 `git status --porcelain`(잔여 항목이 `_to_delete/`와 `profiles/gev_q3_2026.dev.generic.yaml`뿐이어야 함) + `pytest -q` 결과.

---

# §11. 정정 사항 (2026-08-02, §9·§10 작성 직후 발견 — §10보다 우선)

## §11.1 C6의 `START-efe-q2-2026-00-COMMON.md` 경고 — **철회**
해당 파일은 **이미 git 추적 중이며 워킹트리 clean**이다(2026-08-01 11:42 갱신분이 커밋된 상태). §10-C6의 "사라졌다 / 존재 여부 확인" 지시는 **무시할 것.** C6 커밋 대상에서 제외한다(변경 없음).

## §11.2 ⚠️ `.gitignore`가 `reports/sk_hynix_20*.md`를 제외하고 있다 — 두 가지 결과

```
reports/sk_hynix_20*.md
reports/sk_hynix_20*.png
!reports/sk_hynix_20260624*
```

### (a) 프로비넌스 재평가 — T0의 의미가 커졌다
7/10 산출물의 미추적은 **규약 누락이 아니라 "커밋된 프로파일로 재생성 가능"이라는 근거의 명시적 정책**이었다. 따라서 **T0 재현 게이트는 단순 sanity check가 아니라 프로비넌스 등급을 결정하는 판정**이다.
- T0 **PASS** → 벡터(커밋) + 코드(커밋) → 산출물 결정론적 복원 ⇒ 미추적은 결함이 아님. **채점 등급을 5종목과 동등하게 상향**하고 그 근거를 스코어카드에 기록.
- T0 **FAIL** → 정책의 전제가 깨진 것. 등급 유지 + **별도 결함으로 기록**. 앵커 수정은 여전히 금지.

이 판정 결과를 **T1 보고에 반드시 포함**할 것. (스코어카드 §7에 이미 판정 분기를 기록해 두었다.)

### (b) 🚨 Q3 FROZEN 파일 명명 주의 (§9.5 관련)
`reports/sk_hynix_20260930_*.md` 같은 **날짜 접두 파일명을 쓰면 gitignore에 걸려 조용히 추적되지 않는다** — FROZEN 규약 도입의 목적이 그 자리에서 무력화된다.
- 파일명은 **`reports/sk_hynix_q3_2026_forecast_FROZEN.md`** 로 고정 (`sk_hynix_20*` 패턴 비매칭 확인 완료).
- 생성 직후 **`git check-ignore -v <path>` 로 무시되지 않음을 검증**하고, `git status`에 `??`로 뜨는 것을 눈으로 확인한 뒤 add 할 것.
- 이 검증을 2026Q3 동결 절차의 **체크리스트 항목으로 명문화**할 것.

---

# §12. T0 재설계 (2026-08-02, §9.0을 대체)

## §12.0 게이트 설계 오류 — 인정

**§9.0의 `--dry-run` 지시는 잘못됐다.** Codex의 원인 격리가 정확하다. `cli.py:151-173`에서 dry-run은 `tests/fixtures/sk_hynix_2024q{3,4}_dart.json` **2개 분기만** 로드하므로, `forecast_window.start_quarter: 2026Q2`가 요구하는 **2026Q1 seed를 물리적으로 가질 수 없다.** T0 FAIL은 코드 회귀도, 프로파일 문제도 아니고 **지시한 명령이 애초에 앵커를 재현할 수 없는 명령이었다는 뜻**이다. 재현 실패의 책임은 게이트 설계에 있다.

## §12.1 T0a 결과 — 이미 확보된 증거 (유효, 재실행 불필요)

| 증거 | 결과 | 무엇을 입증하나 |
|---|---|---|
| `verify_9q_sha.py` | `b979d79f…f6e7` **MATCH** (host canonical) | 백테스트 레그가 7/10과 **bit-identical** |
| rev MAPE 8.9875% / EPS MAPE 10.3856% / bias −3.5751% | 7/10 리포트(8.99% / 10.39% / −3.58%)와 일치 | 동일 |
| `f49942a..23b1d97`의 `cli.py` diff | **docstring only** | 코드 경로 무변화 |

⇒ **파이프라인의 백테스트 절반은 이미 검증됐다.** 미검증으로 남은 것은 **forward 절반**(2026Q1 seed → 2026Q2 투영) 하나뿐이다. T0를 처음부터 다시 하는 게 아니라 **남은 절반만** 채우면 된다.

## §12.2 T0b — 정정된 재현 경로 (live 모드)

`cli.py:175-183` (`else` 브랜치)는 `fetch_quarterly_actuals_series`를 쓴다 — **`verify_9q_sha.py`가 오프라인으로 성공시킨 바로 그 경로**다. 즉 **DART 레그는 커밋된 캐시로 충족되며 네트워크가 필요 없다.** 그리고 live 모드는 seed가 없으면 `raise`한다(`cli.py:191-193` — 조용한 대체는 dry-run 전용). 따라서:

```
python cli.py --company sk_hynix
```

**기대 (2026Q2)**: base rev `79,070.27` · weighted rev `77,212.75` · weighted OP `60,426.29` · weighted NI `49,824.89` · weighted EPS `70,607.86` · EPS 밴드 `54,516 ~ 86,699`
**허용 오차**: 부동소수 마지막 ULP 수준(상대 `1e-9`)까지만. 그 이상 벌어지면 FAIL.

**네트워크 관련 주의 — 무엇이 앵커에 영향을 주고 무엇이 안 주는가**
- `fetch_consensus(yahoo)`만 네트워크를 탄다. **컨센서스는 forward 블록에 들어가지 않는다** — 컨센 갭 표와 밸류에이션 브리지에만 쓰이고, 애초에 2026Q2는 `n_a`였다(yfinance `.KS` 파손).
- 따라서 **Yahoo가 403이거나 값이 7/10과 달라도 T0b 판정에는 무관**하다. Yahoo 레그 실패로 프로세스가 죽으면 그 사실만 보고하고 §12.3으로 넘어갈 것. **Yahoo 실패를 T0 FAIL로 판정하지 말 것.**
- DART 캐시가 2026Q2를 새로 담고 있어도 윈도는 프로파일에 핀되어 있다(`backtest_window.end_quarter: 2026Q1`, `forecast_window.start_quarter: 2026Q2`). 만약 그럼에도 백테스트 윈도가 움직이면 **그 자체가 중대 결함**이니 즉시 보고.

## §12.3 T0c — 폴백 (T0b가 네트워크로 막힐 때만)

forward 블록은 **`prior_actual`(2026Q1) + 커밋된 프로파일의 순수 함수**다. Yahoo 없이 그 부분만 직접 검증하는 일회성 하니스를 쓴다.
- 데이터 로딩은 **`scripts/verify_9q_sha.py`의 패턴을 그대로 복제**(`load_profile` → `fetch_quarterly_actuals_series`, 커밋된 DART 캐시).
- `cli.py:186-215`의 forward 체인(`_actual_for_quarter` → `MarginBaseline` → `build_margin_carryover` → `project_quarterly_revenue` → `project_margins` → EPS 브리지)을 동일 인자로 호출.
- 2026Q2 산출을 §12.2 기대치와 대조.
- **`scripts/`에 영구 커밋하지 말 것.** 검증용 임시 스크립트이며, 결과만 보고한다. (T0가 반복 필요한 절차로 판명되면 그때 정식 스크립트로 승격을 별도 제안할 것.)

## §12.4 프로비넌스 판정 (§11.2(a) 갱신)

- **T0b(또는 T0c) PASS** → 백테스트 레그(T0a, 검증됨) + forward 레그(검증됨) + 코드 무변화(docstring only) ⇒ 커밋된 프로파일·코드로부터 7/10 산출물이 **결정론적으로 복원됨**이 입증. `.gitignore` 정책의 전제가 성립하므로 **채점 등급을 5종목과 동등하게 상향**하고, 근거(sha·명령·수치)를 스코어카드에 기록.
- **FAIL** → 등급 하향 유지 + 별도 결함 기록. **앵커·프로파일 수정은 여전히 절대 금지.**
- Codex의 "현 시점에서 상향 불가" 판단은 **옳았다.** 그 보류를 §12.2/§12.3 결과가 나올 때까지 유지한다.

## §12.5 신규 결함 D1 — dry-run의 조용한 seed 대체 (Codex 발견, P2)

`cli.py:191-193`: live는 `raise`, dry-run은 **WARNING 한 줄 찍고 최신 fixture 분기로 대체 후 exit 0**.
결과적으로 `--dry-run`은 **프로파일이 요구한 것과 다른 윈도(2025Q1–Q4)의 리포트를 성공인 것처럼 생성**한다. CLAUDE.md §Verification은 이 명령을 검증 수단으로 명시하고 있으므로, **문서화된 검증 절차가 조용히 거짓 통과를 낼 수 있다.** 이번에 실제로 그렇게 됐다.

**P2 백로그 등록 (지금 고치지 말 것 — 별도 승인 사항)**. 후보 방향 두 가지를 보고에 함께 적을 것:
- (a) dry-run도 seed 부재 시 **loud fail** — 단 fixture 갱신 없이는 dry-run 자체가 상시 실패하게 된다.
- (b) fixture를 2026Q1까지 갱신 — 재현성은 회복되나 fixture 유지 부담이 분기마다 발생.
어느 쪽이든 **사용자 결정 사항**이며, 지금은 결함 기록만 한다.

## §12.6 정리 지시
- `reports/sk_hynix_20260802.*` 는 **잘못된 윈도(2025Q1–Q4)의 산출물**이다. gitignore 대상이라 커밋 위험은 없으나, 나중에 앵커로 오인될 소지가 있으니 **삭제할 것**. (Cowork 측에서는 디바이스 파일 삭제가 불가능하므로 Codex가 처리)
- 프로파일·앵커·FROZEN 파일 무수정 원칙 유지 — Codex가 지킨 그대로.

## §12.7 갱신된 실행 순서
```
T0b (live)  ─ 네트워크 차단 시 → T0c
   └ PASS → §12.4 등급 상향 판정 → T1 (+ 6축 ①②⑤) → 보고
   └ FAIL → 즉시 정지·보고 (앵커 수정 금지)
이후는 §9.8과 동일: 커밋(§10) → 6축③④⑥ → T2 → T3a → 확정 → T3b → T4
```

---

# §13. T0 종결 · T1 착수 지시 (2026-08-02)

## §13.1 T0 종결
**T0b PASS.** forward 레그가 앵커 원시 셀과 relative error 0으로 일치. 백테스트 윈도 9분기 유지. §12.4에 따라 **프로비넌스 등급을 5종목과 동등하게 상향 확정**했고, 근거를 `reports/sk_hynix_q2_2026_scorecard.md` **§8**에 기록했다. T0c 불필요. `reports/sk_hynix_20260802.*` 삭제 확인.
게이트 통과 사실은 **T1 산출물에 인용**할 것(§13.3).

## §13.2 T1 착수 — 승인. 6축 ①②⑤ 동시 실행.

기존 §5-T1 범위 유지. 아래는 T0 이후 확정된 **추가 요구사항**이며 §5-T1보다 우선한다.

### §13.2-A 🚨 주식수 레버 축퇴 (attribution 설계에 직결 — 반드시 반영)
actual EPS는 **회사 미공시 파생치**(`NI ÷ 705,656,476`)이고, 그 분모는 **모델이 쓰는 것과 동일한 프로파일 값**이다. 따라서:

```
EPS_error% ≡ NI_error%          (항등식)
주식수 레버 ≡ 0                  (구성상, 정보 없음)
```

- 5레버 중 **주식수 레버는 정보를 담지 않는다.** 값이 0으로 떨어지는 것을 "주식수 예측이 정확했다"로 읽으면 **오독**이다.
- 산출물에 `shares_lever_degenerate: true`를 명시하고, 스코어카드 append 본문에도 **"이 분기의 EPS 귀인은 실질적으로 NI 귀인"**이라고 적을 것.
- 반기보고서(8월 중순)에서 **실제 가중평균 주식수**가 나오면 파생 EPS와 주식수 레버를 **재계산**한다. `inputs/` YAML에 `revision_trigger: "2026 반기보고서 — 가중평균주식수 확정 시 EPS 파생치·주식수 레버 재계산"`을 남길 것.
- 채점 스크립트는 실제 주식수가 들어오면 **자동으로 반영되도록** 하드코딩하지 말 것(프로파일/입력에서 읽기).

### §13.2-B actual YAML 필수 규율
- **정의를 값과 함께 기록.** 특히 ASP는 `value` 옆에 `definition:` 필드 필수(§13.3-⑤ 결과를 여기에 반영).
- **미확정 필드는 추정치로 채우지 말고 `null` + `note`.** 대상: 세전이익 · 법인세 · 영업외손익 내역 · 실제 주식수 · D램/낸드 bit growth. 메리츠 추정(세전 101.8조, 키옥시아 ~40조)은 **`estimates:` 하위 블록에 출처·일자와 함께 분리 기록**하고 `actuals:`에 섞지 말 것.
- 모든 수치에 1차 출처 URL + 인용 문구.

## §13.3 6축 ①②⑤ — 확인 항목 구체화

### ① 사실
§1 수치를 회사 보도자료 / PR Newswire 2Q26 릴리스와 대조. 특히 **순이익 93조9,226억이 지배주주귀속인지 연결 총액인지** — 파생 EPS의 분자가 여기서 갈린다.

### ② 회계
- 키옥시아 이익이 **당기손익(영업외)** 인가 **기타포괄손익(OCI)** 인가. **OCI라면 H2 전체가 재검토 대상**이다(순이익에 안 들어가므로 NI−OP 갭의 설명이 달라진다).
- 지분 **매각 차익** vs **CB 평가이익**의 구분 — 전자는 비반복, 후자는 잔여 포지션이 있으면 재발 가능. T2 이벤트 레지스터의 `probability` 설계가 여기에 의존한다.
- 잔여 키옥시아 지분 유무 → 향후 분기 추가 인식 가능성.

### ⑤ ASP 정의 — **급소. 여기가 T3a의 대조군 정의를 결정한다.**
"D램 ASP 전분기 대비 약 30%"가 **(a) HBM 포함 blended DRAM ASP** 인지 **(b) conventional DRAM 한정** 인지 확정하라.
- 우리 프로파일의 `historical_drivers[q].ddr_asp_qoq`는 주석상 **"일반 DRAM contract price"(= conventional)**다. 대조군이 정합하려면 공시치도 **(b)**여야 한다.
- **(a) blended로 판명되면** 직접 비교는 성립하지 않는다. blended = `hbm_share × HBM_ASP + (1−hbm_share) × DDR_ASP` 로 **분해한 뒤** conventional 성분을 뽑아야 하며, 그러면 **§4-H1의 implied bit 추정(+9~16%)도 재계산 대상**이 된다.
- 어느 쪽이든 **결론과 근거 인용문을 T1 보고에 명시**하고, actual YAML의 `definition:` 필드에 반영할 것. 확정 불가하면 **추정하지 말고 "확정 불가"로 보고** — T3a 착수 전에 해결하면 된다.

## §13.4 보고 후 정지
T1 산출물 + 6축 ①②⑤ 결과를 보고하고 **멈출 것.** 커밋(§10)은 그 다음 단계다. T2 이후는 여전히 착수 금지.

---

# §14. [A][B] 종결 · 커밋 승인 (2026-08-02)

## §14.1 [A] 매출 레버 — **해소. 방법론 동일 확인.**

Codex 설명이 정확하다. 독립 검산 결과 일치:

```
lever_rev / rev_err  =  (E_model / E_actual) × (R_actual / R_model)
                     =  0.53049 × 1.02727  =  0.5450          ✓ 보고치 −1.4469%와 정합
```

**축약(GM=0) 처리는 매출 레버를 바꾸지 않았다** — `OP-margin_m = GM_m × (OP/GP)_m` 이므로 첫 치환은 대수적으로 동일. 0.545의 원인은 **분모(실측 EPS)가 키옥시아 일회성으로 모델 대비 1.89배 부푼 것**이다. 나의 "실측 OP마진 앵커" 가설은 **오진이었다.** 9Q 비율 재계산도 사용자 값과 일치(범위 0.761321–1.213487, 평균 0.978619).

**결정적 확증**: 같은 레버를 **모델 EPS로 정규화**하면
```
매출레버 ÷ 모델EPS = −2.7275%  →  rev_err 대비 비율 1.0273  ← 9Q 범위(0.761~1.213) 안
```
즉 **operating 레버들은 9분기와 동일한 방식으로 계산되고 있다.** 검증 종료.

## §14.2 ⭐ 그러나 남는 방법론 함의 — 스코어카드 경고문 보강 (커밋 전 반영)

현재 §9 경고문은 **축약(GM 미식별)** 만을 비교 불가 사유로 든다. 실제로는 **더 큰 사유가 하나 더 있고, 그쪽이 본질적이다.**

> 레버는 **실측 EPS로 정규화**된다. 이번 분기 실측 EPS는 일회성 below-OP 이익으로 모델 대비 **1.89배**이므로, **모든 레버가 일률적으로 약 0.53배 압축**된다. 따라서 `매출 −1.4469%`를 2026Q1의 `매출 +3.78%`와 크기로 비교하면 안 된다 — 두 수는 분모가 다르다.

**지시**: `reports/sk_hynix_q2_2026_scorecard.md` §9의 경고 블록에 아래 두 가지를 추가하라. (본문 다른 부분·마커·앵커는 불변, `--append` 멱등 유지)

1. **정규화 압축 경고** — 위 문단 취지를 명시. "축약이라 비교 불가"와 **별개의 사유**임을 분명히 할 것.
2. **모델 EPS 정규화 병기 열** — 4레버 표에 `÷모델EPS` 열을 추가해 분기 간 비교가 가능한 값을 함께 제시:

| 레버 | ÷실측EPS (현 규약) | ÷모델EPS (비교용) |
|---|---:|---:|
| 매출 | −1.4469% | −2.7275% |
| OP마진 | +1.3448% | +2.5350% |
| 세금·금융 | −46.8490% | −88.3129% |
| 주식수 | 0.0000% | 0.0000% |
| 합계 | −46.9511% | −88.5054% |

> `÷모델EPS` 합계 −88.5054%는 "모델 EPS 대비 실측이 얼마나 벗어났는가"이고, `÷실측EPS` 합계 −46.9511%가 표준 오차율이다. **둘을 섞어 인용하지 말 것.** 표에 각 열의 정의를 한 줄씩 달 것.

값은 위 표를 그대로 쓰지 말고 **스크립트에서 재계산**해 하드코딩을 피하라(잔차 0 검증도 두 정규화 각각에 대해 수행).

## §14.3 T2 연결 고리 (지금 구현하지 말 것, 설계 메모)
이 압축은 T2의 "이벤트 조정 EPS"와 **같은 뿌리**다. T2 도입 후에는 **이벤트 조정 실측 EPS를 분모로 한 귀인**을 함께 낼 수 있고, 그러면 정규화 왜곡 없이 분기 간 비교가 복원된다. T2 설계 시 이 산출을 후보로 검토하라 — 단 **기본 규약(÷실측EPS)은 유지**하고 추가 열로만 제공.

## §14.4 [B] 인용 무결성 — **승인**
PR Newswire(primary) / 뉴스웨이(secondary, `tier` 명시) 분리, 6-K 제거, 미확인 인용문 공란 처리 모두 요구대로다. 이견 없음.

## §14.5 커밋 — **승인**
§14.2 반영 후 **§10 계획대로 C1~C7 실행.** §10의 절대 규칙(경로 명시 add, `git add -A` 금지, `_to_delete/` 미커밋, `.dev.` 프로파일 제외, 커밋별 pytest green, C1·C2 후 forward 회귀 0, 서명 트레일러 금지) 전부 유효.

**C3·C5 대상 갱신** (T1 산출물 추가):
- **C3**에 추가: `scripts/score_sk_hynix_q2_2026.py` · `inputs/sk_hynix_q2_2026_actual.yaml` · `tests/test_sk_hynix_q2_2026_score.py`
  → 커밋 메시지 조정: `feat(postmortem): add generic four-lever scoring and SK Hynix Q2 2026 scorer`
  → 또는 SK하이닉스분만 **C3b로 분리**해도 좋다(메모리 경로 vs generic 경로 구분이 히스토리에 남아 더 낫다). 판단은 Codex에 위임하되 **선택한 이유를 보고**할 것.
- **C5**의 `reports/sk_hynix_q2_2026_scorecard.md`는 §9 append + §14.2 보강까지 **반영된 최종본**으로 커밋.

보고 형식은 §10 말미 그대로(커밋별 `git show --stat`, 최종 `git status --porcelain`, `pytest -q`).

---

# §15. 커밋 완료 · 🚨 즉시 조치 필요 (2026-08-04)

## §15.1 커밋 검증 — 통과
`23b1d97` → `3190cd6`, 8커밋(C3b 분리 포함). 독립 확인:
- `.env` · `_to_delete/` · `*cacert.pem` **추적 0건**, `_to_delete/`는 `.gitignore:50`에 등록됨
- 계획 밖 파일 커밋 없음 · `profiles/gev_q3_2026.dev.generic.yaml` 제외 유지
- 스코어카드 §9에 축약·정규화압축 **2개 경고 분리 기재**, `÷실측EPS`/`÷모델EPS` 병기, 각 열 정의 명시, 잔차 0 / 1.11e-16
- **C3b 분리 판단 타당** — generic 4레버 엔진과 SK하이닉스 메모리 경로·출처 정책의 revert 경계가 히스토리에 남는다

T1 종결. 다음은 6축 ③④⑥ → T2.

## §15.2 🚨 미커밋 FROZEN 4건 — T2보다 우선

작업트리에 **오늘(2026-08-04) 생성된 동결 예측 4건이 미추적 상태**로 있다.

```
reports/amd_q2_2026_forecast_FROZEN.md          (2026-08-04)
reports/sndk_fy2026q4_forecast_FROZEN.md        (2026-08-04)
reports/spcx_q2_2026_forecast_FROZEN.md         (2026-08-04)
reports/vst_q2_2026_forecast_FROZEN.md          (2026-08-04)
profiles/{amd,sndk,spcx,vst}.generic.yaml       ← 구동 프로파일도 전부 미추적
tests/test_{amd,sndk,vst}_profile.py
reports/{amd,sndk,vst}_generic_forecast.{json,md}
```

**이번 세션의 결론이 정확히 이 지점을 겨눈다.** SK하이닉스 7/10 산출물이 미추적이었음에도 프로비넌스를 지켜낸 유일한 이유는 **커밋된 프로파일 + 커밋된 코드로 결정론적 재현이 가능**했기 때문이다(§8, §12). 위 4건은 **프로파일까지 미추적**이므로 그 방어선이 없다. 지금 상태에서 프린트가 나면 **ex-ante 주장을 입증할 수단이 존재하지 않는다.**

FROZEN 파일의 가치는 전적으로 프로비넌스이며, **프린트 이후의 커밋은 그 가치를 복구하지 못한다.**

**지시 (T2 착수 전, 최우선)**
1. 4종목의 발표 예정일을 확인해 **가장 임박한 순서**로 보고.
2. §10과 동일한 절대 규칙(경로 명시 add, `git add -A` 금지, 커밋별 `pytest -q` green)으로 **FROZEN + 구동 프로파일 + 테스트 + 산출물을 종목별 커밋**.
   - 커밋 단위: 종목별 1커밋 권장(`feat(freeze): freeze AMD Q2 2026 forecast` 등). 프린트 후 종목별 채점·revert 경계가 깔끔해진다.
   - **FROZEN 본문은 한 글자도 수정하지 말 것.** 헤더의 타임스탬프·git HEAD·profile sha는 동결 시점 값이며, 커밋 시점 값으로 갱신하면 안 된다.
   - 헤더의 profile sha가 **현재 프로파일 파일의 sha와 일치하는지 검증**하고, 불일치하면 **커밋하지 말고 보고**(동결 후 프로파일이 수정됐다는 뜻이며 그 자체가 결함이다).
3. `git check-ignore -v`로 4개 FROZEN 파일이 **무시 대상이 아님을 확인**(§11.2(b) 함정 — 종목 접두라 `sk_hynix_20*` 패턴에는 안 걸리지만 절차로 고정).
4. 이미 프린트가 지난 종목이 있으면 **그 사실을 해당 FROZEN 파일 하단에 별도 마커로 기록**하고 채점 시 프로비넌스 등급을 낮춰 표기.

## §15.3 파생 조치 — 동결 절차에 커밋 게이트 편입
`PROMPT_autofreeze_COMMON.md` 워크스트림에 **"동결 = 파일 생성 + 커밋까지"** 를 정의로 못박을 것. 파일만 만들고 커밋하지 않은 상태는 **동결이 아니다.** 체크리스트 항목:
```
[ ] FROZEN 파일 생성 (헤더: 타임스탬프 · git HEAD · profile sha256 · 컨센 기준선/출처일)
[ ] git check-ignore -v 로 무시 대상 아님 확인
[ ] 구동 프로파일 + FROZEN 파일 동일 커밋 또는 인접 커밋으로 커밋
[ ] 커밋 해시를 FROZEN 파일 하단에 기록하지 말 것(순환) — 대신 커밋 메시지에 파일명 명시
[ ] 프린트 전 커밋 완료 확인
```

---

# §16. §15 종결 · 상시 게이트 G1 신설 (2026-08-05)

## §16.1 §15 종결
AMD FROZEN 워킹트리 = 커밋 blob 일치 확인(diff 없음), `reports/amd_q2_2026_errata.md` 추적 확인, `5f02652` 커밋. `ae3203e` 커밋은 프린트(16:00 ET) **3시간 29분 전** — 마진 충분. 4종목 동결 프로비넌스 전부 성립. 290 passed.

내 §15.2 "미커밋" 단정은 **낡은 스냅샷 기준의 오류**였다. 다른 세션이 이미 프린트 전 커밋을 마친 상태였고, Codex 검증을 수용한다.

## §16.2 ⭐ 상시 게이트 G1 — 앵커 재현 회귀 (신설, 이후 모든 작업에 적용)

이번 세션에서 확보한 것 중 가장 되돌리기 쉬운 자산이 **SK하이닉스 2026Q2 채점의 프로비넌스 등급**이다. 그 등급은 다음 한 문장에 전적으로 의존한다.

> 커밋된 프로파일 `4ebeb7c` + 현재 코드로 `python cli.py --company sk_hynix` 를 돌리면 7/10 앵커가 원시 셀 기준 relative error 0으로 재현된다.

즉 **이건 한 번 달성하고 끝나는 성취가 아니라, 코드가 바뀔 때마다 유지되어야 하는 살아있는 속성**이다. T2가 EPS 출력 포맷을 바꾸고, T3b가 `bit_growth_qoq[0]`을 바꾸고, T4가 윈도를 롤한다 — **어느 하나라도 앵커 재현을 깨면 §8의 등급이 조용히 증발한다.** 깨진 사실을 아무도 모른 채 스코어카드에는 "5종목과 동등"이 남아 있는 상태가 최악이다.

**G1 (상시)**: T2 이후 모든 변경은 완료 보고에 아래를 포함한다.
```
[ ] python cli.py --company sk_hynix  → 2026Q2가 §12.2 기대치와 relative error 0
      base rev 79,070.26666360501 · wtd rev 77,212.75104432012
      wtd OP 60,426.28566423651 · wtd NI 49,824.89024685436 · wtd EPS 70,607.8551553665
[ ] scripts/verify_9q_sha.py → b979d79f…f6e7 MATCH
[ ] 깨졌으면: 되돌리거나, 스코어카드 §8 등급을 즉시 하향하고 사유를 기록 (둘 중 하나. 방치 금지)
```
T3b·T4는 **의도적으로** forward를 바꾸므로 앵커가 깨진다. 그때는 "깨졌다"가 아니라 **"롤 이전 스냅샷으로 앵커를 고정하고 등급 근거를 그 시점 커밋으로 이전"** 하는 절차가 필요하다 — T4 착수 시 별도 설계할 것. **T2는 예외 없이 G1을 통과해야 한다**(이벤트 블록 부재 시 bit-identical 불변식과 동치).

## §16.3 6축 ③④⑥ — 확인 항목

- **③ 모델 커플링**: T2의 `below_op_events`가 `run_backtest`의 methodology 소비 경로에 닿는가(닿으면 안 된다 — 이벤트는 forward 전용). 9Q 백테스트 불변 확인. T3b가 요구하는 `backtest_methodology` 메모리 경로 이식이 T2보다 먼저여야 하는지 판단.
- **④ 통계**: T2 도입 시 기존 `risk_band`(mad k=1.5)를 **건드리지 않는** 설계가 맞는지. 관측치 1개(키옥시아)로 밴드 폭이나 방법을 재추정하려는 유혹을 명시적으로 기각할 것. 이벤트 `probability`는 통계 추정이 아니라 **판단값**이며 그렇게 표기할 것.
- **⑥ 최소성**: T2가 스키마·엔진·리포트 3곳을 동시에 건드릴 필요가 있는지. 최소 seam은 무엇인지. 인접 리팩터 금지, `NOTICED BUT NOT TOUCHING:` 로그로 대체.

## §16.4 T2 수용기준 (§5-T2 + §9.2 보강)
```
[ ] below_op_events 부재 시 전 출력 bit-identical (G1과 동치)
[ ] EPS 점추정 불변 — 이벤트 조정 EPS는 별도 열/시나리오로만
[ ] as_of_date < target 분기말 lookahead 가드 (overlay 로직 재사용)
[ ] confidence: estimated | confirmed 구분, 키옥시아는 estimated (반기보고서 전)
[ ] probability = 판단값임을 스키마 주석과 리포트 각주에 명시
[ ] G1 통과
```

---

# §17. 6축 ③④⑥ 수용 · T2 착수 승인 (2026-08-05)

③ seam 격리(cli.py:301 출력 레이어 전용, `run_backtest`·`engine/backtest.py` 무변경), ④ risk_band 불변 + 1건 재추정 명시적 기각, ⑥ 최소 변경 범위와 `NOTICED BUT NOT TOUCHING` 처리 — 모두 수용. **T2 착수 승인.** 아래 두 핀을 설계에 반영할 것.

## §17.1 핀 P1 — "이중 계산 방지"는 **근사**다. 문구를 정확히 쓸 것.

④의 논리(반복성 분산 vs 식별 가능 사건을 섞으면 이중 계산)는 옳다. 다만 **기존 밴드가 순수한 반복성 분산이 아니다.**

`profiles/sk_hynix.yaml`의 `risk_band` 주석에 이미 적혀 있다 — 8Q 표본에 **2025Q3 +3,407bn 같은 이상치가 포함**되어 있고, MAD를 고른 이유가 바로 "폭이 이상치에 끌려가지 않게" 하기 위해서였다. 즉 밴드는 **일회성 분산을 약하게(attenuated) 이미 머금고 있다.** 완전히 배타적인 두 레이어가 아니다.

- 실무적 영향은 작다(MAD의 강건성이 상한을 눌러준다) → **설계 변경 불필요.**
- 그러나 문서에 "이중 계산 방지" 또는 "두 레이어는 배타적"이라고 단정해 쓰면 **거짓**이 된다. 나중에 이 문장을 근거로 밴드를 손대려는 시도가 나온다.
- **표기**: "두 레이어는 **근사적으로** 분리된다. 기존 밴드 표본(8Q)에는 이상치가 포함되어 있으나 MAD의 이상치 저항성으로 그 기여가 제한된다. 잔여 중복은 0이 아니며 정량화하지 않는다." — 스키마 주석과 리포트 각주 양쪽에.

## §17.2 핀 P2 — 🚨 `valuation_bridge`는 **base EPS를 유지**한다 (이벤트 조정 EPS 주입 금지)

⑥의 "변경하지 않을 대상"에 `valuation overlay 계산`은 있으나 **`engine/valuation_bridge.py`가 어떤 EPS를 먹는지는 명시되지 않았다.** 여기가 조용히 틀린 숫자를 만들 수 있는 지점이다.

브리지는 `EPS gap × fair_value_elasticity(1.2) → 공정가치 delta`로 동작한다. 이벤트 조정 EPS(키옥시아 ~40조 포함)가 여기로 흘러 들어가면 **일회성 자산처분이익이 1.2배로 증폭되어 공정가치에 반영**된다. 명백히 틀린 결과다 — 반복되지 않는 처분이익은 DCF 가치를 그만큼 올리지 않는다(현금 유입분 이상은 더더욱).

**요구사항**
```
[ ] valuation_bridge 입력 EPS = 기존 base/weighted 점추정 (불변)
[ ] 이벤트 조정 EPS는 valuation 레이어에 절대 주입하지 않음
[ ] 위 사실을 valuation_bridge.py docstring과 리포트 밸류에이션 섹션 각주에 명시
[ ] 회귀 테스트: below_op_events 존재 시에도 fair-value delta 출력 불변
```
마지막 항목은 **T2의 필수 테스트**다. "부재 시 bit-identical"만으로는 이 경로를 잡지 못한다 — 이벤트가 **존재할 때** valuation이 안 움직이는지를 따로 봐야 한다.

> 배경: 이번 분기 실측이 정확히 이 함정을 보여줬다. 순이익 93.9조(NPM 118%)를 그대로 밸류에이션에 넣으면 터무니없는 공정가치가 나온다. 발표 당일 주가는 컨센서스 하회와 주주환원 구체안 부재, AI 투자 지속성·공급과잉 우려가 겹치며 −9.61% 하락했다. 일회성 키옥시아 이익이 주가 하락을 막지 못했다는 점에서도 이벤트 조정 EPS를 공정가치에 주입하면 안 된다.

## §17.3 T2 최종 수용기준 (§16.4 + P1·P2)
```
[ ] below_op_events 부재 시 전 출력 bit-identical
[ ] below_op_events 존재 시에도 fair-value delta·risk_band 출력 불변   ← P2, 신규
[ ] EPS 점추정 불변 — 이벤트 조정 EPS는 별도 열/시나리오로만
[ ] as_of_date < target 분기말 lookahead 가드
[ ] confidence: estimated | confirmed, 키옥시아 = estimated
[ ] probability = 판단값 명시 (스키마 주석 + MD/HTML 각주)
[ ] 밴드-이벤트 분리는 "근사"로 표기 (P1)
[ ] G1 통과 — 앵커 재현 relative error 0 + 9Q sha b979d79f…f6e7 MATCH
```

---

# §18. T2 검토 — 커밋 전 3건 보완 (2026-08-05)

seam 격리·P1·P2 반영·G1 통과(앵커 relative error 0, 9Q sha MATCH) 모두 확인. **출처를 "이벤트 존재 = KRX 공시(1차) / 금액 = 메리츠 추정(2차)"로 분리한 것은 요구 이상**이며 T1의 인용 규율이 정착된 결과다. 305 passed.

검산: `40,000bn × 0.8 ÷ 705,656,476 = 45,348원`, `70,608 + 45,348 = 115,956원` — 보고치와 일치. 아래 3건만 보완 후 커밋.

## §18.1 🚨 A — `as_of_date`가 이원화되어야 한다 (lookahead 급소)

현재 엔트리는 `as_of_date: 2026-06-24`(KRX 공시) 하나인데, **금액 40,000bn의 출처는 2026-07-28 메리츠 추정**이다. 즉:

| 구성요소 | 인지 가능 시점 | 출처 등급 |
|---|---|---|
| 이벤트 **존재** (SPC1 매각 완료) | **2026-06-24** | 1차 (KRX) |
| 이벤트 **금액** (~40조) | **2026-07-28** | 2차 (추정) |

한 엔트리가 **두 개의 서로 다른 인지 시점**을 담고 있고, 스키마는 이른 쪽만 기록한다. 이건 지금은 무해하지만 **다음 순간 터진다** — §4-H2의 "7/10 시점에 인지 가능했다"를 실증하려고 7/10 프로파일에 이 이벤트를 넣고 재현을 돌리는 순간, **7/28에만 알 수 있었던 금액이 7/10 예측에 주입**된다. 전형적 lookahead이며, 하필 우리가 이 세션 내내 방어해 온 바로 그 속성을 자기 손으로 깨는 경로다.

**요구사항**
```
[ ] 스키마에 amount_as_of (또는 amount_source_date) 필드 추가 — 금액 출처 일자
[ ] as_of_date 는 "이벤트 존재 인지 시점"으로 의미 고정 (docstring 명시)
[ ] lookahead 가드 확장: 금액이 수치에 반영될 때는 amount_as_of 도 검사
[ ] 키옥시아 엔트리: as_of_date 2026-06-24 / amount_as_of 2026-07-28
[ ] 리포트 각주에 두 일자를 모두 표기 — "존재는 6/24부터, 금액은 7/28부터 인지 가능"
```
이 구분이 있으면 §4-H2의 주장도 정확해진다: **"이벤트 발생은 사전 인지 가능했고, 규모는 아니었다."** 현재 스코어카드 §4-H2 표현("6월 완료 = 7/10 시점에 인지 가능")은 이 뉘앙스가 없으므로 **한 문장 정정**할 것.

## §18.2 B — 금액의 세전/세후 기준이 암묵적이다

구현은 `amount × probability ÷ shares`로 **세금을 적용하지 않는다**(= 순이익 레벨 금액으로 간주). 그런데 원출처는 "**영업외이익** 약 40조"로, 문자 그대로면 **세전**이다. 세율을 물리면 값이 크게 달라진다.

```
무세(현재)      +45,348원  ->  조정EPS 115,956원
세율 16.4% 적용  +37,911원  ->  조정EPS 108,519원
실측 23.4587% 적용  +34,709.9원  ->  조정EPS 105,318원
```

실측 세율 적용 시 이벤트 조정액은 무세 기준 **45,348원에서 34,709.9원으로 감소**한다. 계산은 `70,608 + 45,348 × (1 − 28,785.8 / 122,708.4) = 105,317.947…`로 원장 full precision을 유지한 뒤 최종 1회 반올림한다. 이 변화를 다른 방향의 레버로 표현하지 않는다. 다만 당기·이연법인세 구분이 확인되지 않았으므로 **세율 앵커 16.4%와 `basis=net_income_level`은 반기보고서 전까지 유지**한다.
```
[ ] 스키마에 basis: pre_tax | after_tax | net_income_level 필드 추가 (필수)
[ ] 키옥시아 = net_income_level 로 기록 + note: "원출처는 '영업외이익'(세전 시사)이나
    세무처리 미확정. 반기보고서 확인 시 basis 및 금액 재검토" + revision_trigger
[ ] basis=pre_tax 인 엔트리는 세율을 곱하도록 계산 분기 (지금 키옥시아엔 미적용)
[ ] 리포트 각주에 채택 basis 표기
```

## §18.3 C — 이항 사건에 기대값만 출력하고 있다

`0.8 × 40조`는 **실제로 일어날 수 없는 결과**다. 사건은 발생했거나 안 했거나 둘 중 하나다. 기대값 단독 제시는 독자가 115,956원을 "우리 전망치"로 읽게 만든다.

리포에 이미 bear/base/bull 관례가 있으니 그대로 따를 것.
```
미발생 (p=0)      70,608원   ← 기본 EPS 점추정
발생   (p=1)     127,293원
기대값 (p=0.8)   115,956원
```
```
[ ] 3행 표로 출력 (기대값 단독 출력 금지)
[ ] 각주: "확률은 판단값이며 기대값은 실현 불가능한 중간값이다"
```

**추가 표기 권고**: 이벤트(무세·p=1) 40,000bn은 실측 NI 갭(93,922.6 − 49,824.9 = **44,097.7bn**)의 **91%**만 설명한다. 잔여 ~4,098bn은 다른 below-OP 항목과 OP 미스다. 이 수치를 각주에 넣어 **이벤트가 전부를 설명하지 않음**을 못박을 것.

## §18.4 처리 후
A·B·C 반영 → G1 재확인(§16.2) → 커밋. 커밋 단위는 T2 1커밋 권장(`feat(risk): add below-OP event register with event-adjusted EPS`). §10 절대 규칙 유효.
