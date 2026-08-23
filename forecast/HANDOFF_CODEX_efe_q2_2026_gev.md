# HANDOFF → Codex · EFE Q2 2026 · GE Vernova (GEV)

**상태:** 프린트-전 동결 **완료** · actual **미확보**(2026-07-22 발표 예정, 콜 07:30 ET) · 사후 채점 **대기**.
**작성:** Claude (Cowork 샌드박스), 2026-07-22 06:26 UTC.
**루프:** COMMON §5 6축 교차검증. **아래 주장(diff/pytest/sha)을 그대로 믿지 말고 독립 재현할 것.**

---

## 0. 한 줄

신규 `profiles/gev.generic.yaml`(1파일 추가, 코드 미변경)로 GEV 2026Q2를 top-down generic 경로로 동결.
Base 매출 $10.74B(+17.9% YoY) / GAAP 희석 EPS $3.23(+74%). 컨센 $10.77B/$3.17 대비 매출 인라인·EPS 소폭 상회.
검증 중 **2개 엔진 버그**(계절 슬롯 오정렬, 빈 pre-break render 크래시)를 격리·문서화(미수정, 호스트/Codex 몫).

---

## 1. 산출물 (모두 디바이스 커밋됨, git add 대기)

| 파일 | 비고 |
|---|---|
| `profiles/gev.generic.yaml` | sha256 `d92a701a9aa682bf9bf2782a2391c4f1ff18dcf5bd905ff49c913c96a8fea592` (디바이스 재검증 일치) |
| `reports/gev_q2_2026_forecast_FROZEN.md` | (a)~(f) + 백테스트 정직성 + provenance + 4-lever 채점 준비 |
| `reports/gev_generic_forecast.md` / `.json` | 엔진 원본 출력(재현용, 백테스트 로우 포함) |
| `HANDOFF_CODEX_efe_q2_2026_gev.md` | 본 문서 |

기준 커밋: git HEAD `9d7200ca62af5b421cfc8db985ffa09e85fadbb1` ("feat: add fiscal-aware generic consensus").
임시 파일 `_cowork_src.tar.gz`는 `_to_delete/`로 이동(샌드박스는 rm 불가) → **직접 삭제 요망**.

---

## 2. 방법론 계약 준수 확인 (COMMON §1)

- ✅ Generic 경로만: `python generic_cli.py --profile profiles/gev.generic.yaml`. 바텀업 유닛×ASP **없음**. 메모리 경로(cli.py·segment_revenue·margin_model) **미접촉**.
- ✅ 12월 결산 → 라벨 오프셋 없음(fiscal FYNQq = model NQq).
- ✅ EPS 선택 안 함 — net_profit ÷ as-filed 분기 희석주식수로 파생(분할 없음, `split_history: []`).
- ✅ 컨센은 "consensus estimate"로 명시, `.KS` 품질 게이트 미적용(issuer-neutral).
- ⚠️ **데이터 소스 편차(정직 disclose):** actuals는 EDGAR companyfacts as-filed지만 **whole-blob 빌드(`scripts/build_generic_actuals.py`)가 아니라 WebFetch로 수집**(샌드박스 httpx는 data.sec.gov 403). 아래 §4로 whole-blob 재빌드 요망.

---

## 3. 프로파일 결정 근거 (assumptions는 human-owned, 리뷰 포인트)

시드 = 2026Q1(매출 $9,339M, net/eps **OMIT** — §5-B 세금 왜곡 때문). 전방 4분기, 확률 bear25/base50/bull25.

| 시나리오 | growth_qoq (Q2→Q1 순) | op_margin | tax | net_int | 2026Q2 매출 | 2026Q2 EPS |
|---|---|---:|---:|---:|---:|---:|
| bear | [0.10,0.06,0.09,−0.25] | 0.055 | 0.24 | 0.010 | $10,273M | $1.87 |
| base | [0.15,0.10,0.13,−0.22] | 0.092 | 0.22 | 0.013 | $10,740M | $3.23 |
| bull | [0.19,0.12,0.15,−0.20] | 0.115 | 0.20 | 0.015 | $11,113M | $4.25 |
| 확률가중 | — | — | — | — | $10,717M | $3.15 |

- **growth 순서 = forward-step**(시드 다음 분기부터 순차). 계절: Q1→Q2 +13~15%, Q2→Q3 +9%, Q3→Q4 +10~18%, Q4→Q1 −24%(실측). base 2026Q2 +15% → $10.74B로 컨센 정합. FY2026 base ≈ $45B(가이던스 $44.5–45.5B 중상단).
- **op_margin = 블렌디드 GAAP 영업이익률 프록시**(세그먼트 EBITDA 가이던스 Power 17–19%/Electrification 18–20%/Wind ~−$400M − D&A·corporate). base Q2 9.2%는 Q2'25 GAAP OI 4.1% 대비 공격적이나 FY 마진 램프·+70% EPS 컨센과 정합.
- **net_int = 구조적 순이자/기타**(~$8B 순현금 이자수익 + 지분법). GEV는 순이익>영업이익 상시(2025Q1 NI 254 vs OI 43 등).
- **tax = 정상화 세율**(§5-B). **리뷰 요청:** base 9.2% op_margin이 과한지, tax 22% 안착 가정이 타당한지 6축 "정확성/건전성"에서 봐줄 것.

---

## 4. 데이터 provenance · 독립 재현 (COMMON §1 무결성 1순위)

CIK **1996810**, fye-month 12. actuals 9행(2024Q1~2026Q1). 단위 USD_million, diluted_shares 절대값.

| 라벨 | 매출 | net_profit | dil_shares | 파생 EPS | as-filed EPS | accession |
|---|---:|---:|---:|---:|---:|---|
| 2024Q1 | 7,260 | −130 | 274M | −0.47 | −0.47 | 10-Q …24-000008 (carve-out, 분사 04-02) |
| 2024Q2 | 8,204 | 1,294 | 278M | 4.65 | 4.65 | 10-Q …24-000067 (NI≫OI $527M) |
| 2024Q3 | 8,913 | −96 | 275M | −0.35 | −0.35 | 10-Q …24-000083 |
| 2024Q4 | 10,559 | 484 | 281M | 1.72 | (파생) | 10-K …25-000011 − 9M …24-000083 |
| 2025Q1 | 8,032 | 254 | 279M | 0.91 | 0.91 | 10-Q …25-000073 |
| 2025Q2 | 9,111 | 514 | 276M | 1.86 | 1.86 | 10-Q …25-000133 |
| 2025Q3 | 9,969 | 452 | 275M | 1.64 | 1.64 | 10-Q …25-000160 |
| 2025Q4 | 10,956 | 3,664 | 273M | 13.42 | (파생) | 10-K …26-000015 − 9M …25-000160 |
| 2026Q1 | 9,339 | 4,745 | 272M | 17.44 | 17.44 | 10-Q …26-000064 |

**항등식(전부 tie-out, Claude 오프라인 재현):**
- FY2024 매출 34,936 ≈ 34,935(+$1M 반올림) · NI −130+1294−96+484 = **1,552 정확**.
- FY2025 매출 8032+9111+9969+10956 = **38,068 정확** · NI 254+514+452+3664 = **4,884 정확**.
- 파생 EPS = as-filed와 **전 분기 일치**(Q4 파생 2024Q4 1.72 ≈ FY−9M 1.73).
- Q4 shares 가드: 2024Q4 4×278−3×277=281 · 2025Q4 4×276−3×277=273 (모두 0.5×~2× 내).

**Codex 할 일(정확성/검증가능성):**
```
python scripts/build_generic_actuals.py --cik 1996810 --fye-month 12 --start 2024Q1 --end 2026Q1
```
→ whole-blob(reports/.cache/) 재빌드 후 **위 9행과 bit 비교**. 불일치 시 이 핸드오프가 틀린 것 — 리포트 header sha256도 갱신 필요.
(주의: 2024Q1은 GEV 자사 첫 10-Q as-reported carve-out. pro-forma 세그먼트 재구성 아님. whole-blob이 2024Q1 3M 매출/NI 3M 팩트를 담는지 확인 — 없으면 2024Q2 시작으로 축소하고 리포트 N 표기 조정.)

---

## 5. 발견한 결함 2건 (6축 "정확성·유지보수성" 핵심 · 미수정)

### 5-A. generic forward/backtest 계절 슬롯 규약 불일치 (5종목 전부 잠재)
- **증상:** GEV backtest 매출 MAPE 20.3% > naive RW 14.2%(MASE 1.48). 겉보기 모델 실패.
- **근인:** `engine/generic_forecast.project_scenario`는 `growth[i]`를 시드 다음부터 **순차**(positional) 적용 → 2026Q2=growth[0]. 그러나 `generic_cli.backtest_generic._slot`는 타겟의 **캘린더 슬롯**(Q1→0…Q4→3)으로 `growth`를 소비. **한 벡터가 두 규약 동시 만족 불가**(Q2-start + 계절성).
- **증거(회전 오정렬, `reports/gev_generic_forecast.json` backtest.rows):**
  | 타겟 | actual | model | err | 원인 |
  |---|---:|---:|---:|---|
  | 2024Q4 | 10,559 | 6,952 | −34.2% | Q4에 growth[3]=−0.22(Q4→Q1 하락) 오적용 |
  | 2025Q1 | 8,032 | 12,143 | +51.2% | Q1에 growth[0]=+0.15(Q1→Q2 상승) 오적용 |
  | 2024Q2 | 8,204 | 7,986 | −2.7% | 슬롯 정합 → 정상 |
  | 2025Q3 | 9,969 | 10,295 | +3.3% | 슬롯 정합 → 정상 |
- **함의:** GEV 프로파일은 **forward-step 순서**를 택해 **forward(=동결·채점 대상)를 계절-정합**시킴 → 동결값 정확. backtest가 아티팩트. (TSLA 커밋 YAML은 반대로 슬롯 순서 → backtest 맞고 forward 과소 $21.3B. 동일 버그의 양면.)
- **제안 픽스(택1, 회귀 위험 평가 요망):**
  1. `backtest_generic`가 forward와 **동일한 positional 규약**을 쓰도록 `_slot`을 (target index from seed) 기반으로 재정의 — 단 계절 매칭 의미 상실.
  2. 프로파일에 별도 `backtest_methodology`(캘린더-슬롯 벡터) 블록 분리 — 메모리 경로 CLAUDE.md 선례의 generic 판. **권장.**
  3. forward/backtest 모두 **캘린더-슬롯 벡터**를 소비하고 forward가 시드 다음 분기의 슬롯부터 인덱싱하도록 통일.
- **주의:** `base.revenue_growth_qoq`·`net_interest`가 forward+backtest 이중 사용(coupling). 어떤 픽스든 5종목 전부 회귀 표(before/after MAPE·bias) 첨부.

### 5-B. GEV 세금 왜곡 → backtest EPS 지배 (구조적, 데이터 정상)
- 2025Q4·2026Q1 reported NI가 **일회성 이연법인세 valuation allowance 환입**으로 폭증(2026Q1 NI $4,745M vs 영업이익 $179M). 파생 EPS $13.4·$17.4는 **실측이나 반복 불가**.
- backtest EPS MAPE 190.8%는 이 두 분기가 지배. 모델(정상화 세율)은 일회성 세금 이익을 예측 불가 → **구조적, 리스크밴드行**(코드 버그 아님).
- 대응: 시드 net/eps OMIT, 전방 tax 정상화 22%. **리뷰:** 정상화 세율 앵커가 발표 실효세율과 맞는지 사후 확인.

### 5-C. render 크래시 (부수 발견)
- `regime_break_quarter`가 빈 pre-break 윈도를 만들면 `generic_cli._render_window`가 `None` MAPE 포맷에서 `TypeError`(pre-spin 분기 1개인 GEV). → `regime_break_quarter: null`로 우회. **가드 추가 요망**(빈 윈도 시 스킵/N/A).

---

## 6. 회귀 안전 (6축 "회귀안전·범위규율")

- **범위:** `profiles/gev.generic.yaml` **1파일 추가**, 코드 0줄 변경. 메모리 경로(SK Hynix) 구조상 불변.
- **테스트(샌드박스, 부분 카피):** generic 경로 포함 **175 pass**. 2 fail = `test_backtest`(DART 캐시 부재 "need ≥13 quarters") · `test_disclosure_loader`(DART 403) — **환경 이슈, 본 변경 무관**. 미스테이지 3파일(scripts/output 의존)은 collection 제외.
- **Codex 독립 재현 요청:**
  1. 풀 리포 + DART 캐시 + 네트워크에서 `pytest -q` **전체 그린** 확인.
  2. `python scripts/verify_9q_sha.py` → host canonical(CPython >=3.12) 9Q `BacktestResult` sha256 `b979d79f…f6e7` **bit-identical** 확인(메모리 경로 미변경 증빙; CPython <=3.11은 `077ecb10…933c`).
  3. `python generic_cli.py --profile profiles/gev.generic.yaml --json` 재실행 → §3 표와 대조.

---

## 7. 사후 채점 프로토콜 (발표 후 채울 것 · COMMON §3 · 4-lever generic)

> actual 확보(EDGAR 10-Q `…26-0000xx` / IR 릴리스) 후 아래 채움. 채점은 **"사후 귀인 — 예측 신호 아님"** 라벨 유지.

| 항목 | FROZEN(우리) | Actual | 오차 | 귀인 |
|---|---:|---:|---|---|
| 총매출 | base $10,740M | _TBD_ | _MAPE/bias_ | 레버1 매출 |
| GAAP 희석 EPS | base $3.23 | _TBD_ | | 레버2 영업이익률 |
| Power 매출 | ~$5.5–5.6B | _TBD_ | | 레버3 OP→NI(below-OP) |
| Wind 매출/손실 | ~$1.9B / 손실폭 | _TBD_ | | 레버4 주식수 |
| Electrification 매출 | ~$3.5B↑ | _TBD_ | | |
| 실효세율 | 22% 가정 | _TBD_ | | (§5-B 검증) |
| FY 가이던스 | 추가 상향 콜 | _TBD_ | | (c) 방향 적중 |

채점 산출:
1. 매출·EPS MAPE·bias(부호). 세그먼트별 오차.
2. `engine/skill_metrics.py` MASE/Theil(vs RW) — **N=8, 방향 참고용 라벨 유지**.
3. 컨센 대비 surprise 방향 적중(매출·EPS above/below).
4. **사전등록 스윙 팩터 발화 여부:** ① below-OP 블록(Wind 충당금/2024Q2형 이익) ② 정상화 세율.
5. 결론: YAML 한 줄 앵커(tax·op_margin) 수정으로 고칠 체계적 편향인가, 리스크밴드行 구조적 항목인가.

---

## 8. Codex 액션 아이템 (요약)

1. **git 커밋** — profiles/gev.generic.yaml + reports/gev_q2_2026_forecast_FROZEN.md + gev_generic_forecast.{md,json} + 본 핸드오프. `_to_delete/` 정리.
2. **whole-blob 재빌드**(§4) → 9행 bit 비교, 불일치 시 header sha 갱신.
3. **6축 리뷰**(§3 assumptions, §5 버그 3건) → 반박/수용. Claude 재현 대기.
4. **버그 픽스 결정**(§5-A 택1 + §5-C 가드) → 5종목 회귀 표 + 9Q sha 불변 첨부.
5. **테스트 전체 그린 + 9Q sha 확인**(§6).
6. **발표 후** §7 채움 → 채점 확정.

---

## 9. Codex 호스트 검증 및 수정 (2026-07-22)

- whole-blob 재빌드: 2024Q1~2026Q1 **9행 수치 일치**, FY 합·EPS 정합·연속성 green. 2024Q1 source는 same-accession 규칙이 선택한 2025Q1 10-Q 비교열 `0001996810-25-000073`으로 갱신(수치·basis 동일).
- generic 스키마에 선택적 `backtest_methodology` 추가. 없는 프로파일은 기존 `base` 폴백을 그대로 사용하며, GEV만 `[Q1,Q2,Q3,Q4]=[-0.22,0.15,0.10,0.13]`으로 이관.
- GEV 매출 backtest: MAPE **20.3% → 2.93%**, bias **+3.1% → −0.35%**. EPS MAPE **190.8% → 179.1%**로 여전히 세금환입 분기가 지배(구조적 진단 유지).
- forward 회귀: generic forecast 엔진은 무수정. GEV·GOOGL·IBM·TSLA·TXN의 첫 forward 분기 값은 각각 `$10,716.5025M/$3.145646`, `$115,940.28M/$2.789938`, `$17,524.617M/$2.352046`, `$21,267.65M/$0.402411`, `$5,207.38125M/$1.887508`; 수정 전 저장 산출물과 수치 동일(부동소수점 마지막 ULP 제외). 전용 회귀 테스트가 methodology 유무의 전체 weighted-quarterly dump 동일성을 검증.
- 빈 pre/post-break window는 MAPE·bias를 `N/A`로 렌더하도록 가드 및 회귀 테스트 추가.
- 검증: `python -m pytest -q` → **207 passed**. `python scripts/verify_9q_sha.py` → host canonical `b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7` MATCH.
- `reports/gev_q2_2026_forecast_FROZEN.md`는 동결 증빙 보존을 위해 **미수정**.

---

## 10. Claude 독립검증 (loop close, 2026-07-22)

Codex §9 주장을 **오프라인 독립 재현**(믿지 않고 재실행):
- forward 불변: nvda·tsla `weighted_quarterly`+`weighted_annual` HEAD vs NOW **완전 동일**(backtest MAPE만 1e-14 float 지터 → JSON 60줄 diff는 무의미 노이즈). GEV forward 2026Q2 $10,717/$3.15 불변.
- GEV backtest 매출 MAPE **20.3%→2.93%** 재현(naive RW 14.16% 하회). `base.revenue_growth_qoq` 불변, `backtest_methodology [-0.22,0.15,0.10,0.13]` 캘린더 슬롯.
- FROZEN 리포트 **byte-identical**(header sha `d92a701a` 보존).
- 신규 테스트 4종 pass(forward 불변·미설정 fallback·슬롯 독립·빈window N/A). 샌드박스 서브셋 184 pass(풀 env 207 정합).
- 9Q sha `b979…f6e7`: 오프라인 재현 불가(DART 캐시 부재)이나 **git diff 범위 = generic_cli.py·schemas/generic.py·report json만 → 메모리 경로 무변경 → 구조상 bit-identical**. 간접 확인, 수치는 호스트 재확인 신뢰.
- **판정: ACCEPT.** 정확·회귀안전·범위규율 통과. git 커밋만 남음.

---

## 11. 사후 채점 (POST-PRINT, 2026-07-22 발표 후) — 예측 신호 아님, 사후 귀인

### 11.1 Actual (보도자료/8-K; EDGAR companyfacts는 Q2 10-Q 미갱신 → GAAP OI/tax XBRL 분해는 호스트 후속)
- 매출 **$11,104M** (+21.9% YoY) · GAAP 희석 EPS **$2.47** (+32.8%) · 순이익 ~**$649M**(EPS 기준 ~$668M) · adj EBITDA **$1,250M (11.3%)** · 희석주식수 ~269–270M
- 수주 **$24.2B (+88% organic)** · 백로그/RPO **$176B (+37%)**
- 세그먼트: Power **$5,477M** (+14%, EBITDA 18.8%) · Electrification **$3,637M** (+68%, EBITDA 18.4%) · Wind **$2,026M** (−10%, EBITDA **−$275M / −13.6%**)
- **FY26 가이던스 상향:** 매출 **$45.5–46.5B**(↑$44.5–45.5) · FCF **$11.5–12.5B**(↑$6.5–7.5, 거의 2배) · adj EBITDA 마진 12–14% 유지
- Q2는 클린: 대형 게인(Prolec $3,992M pre-tax + Proficy $330M)은 **Q1(H1)** 계상, Q2 아님

### 11.2 스코어카드 (FROZEN vs actual)
| 항목 | FROZEN base | 확률가중 | Actual | base 오차 | 컨센 | 컨센 오차 | 위스퍼 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 매출 | 10,740 | 10,717 | **11,104** | **−3.3%** | 10,780 | −2.9% | — |
| GAAP EPS | 3.23 | 3.15 | **2.47** | **+30.8%** | 3.17 | +28.3% | 3.47 (+40.5%) |

- **매출:** base −3.3%(우리가 낮음). actual = 우리 **bull 매출 $11,113**에 적중(−0.08%). 컨센도 −2.9% 저평가.
- **EPS:** base +30.8% 과대. **전 Street 동일 방향 오버슈트**(컨센 +28%, 위스퍼 +40%). 우리만이 아니라 시장 전체가 EPS를 높게 봄.
- **밴드 포함:** bear $1.87 < **actual $2.47** < base $3.23 → 우리 **밴드가 actual을 포함**(bear→base 44% 지점). 넓은 밴드(START 지시 (a)) 유효.

### 11.3 4-lever 귀인 (base $3.23 → actual $2.47, Δ −$0.76)
| lever | 방향/크기 | 내용 |
|---|---|---|
| ①매출 | +$0.11 (우호) | +$364M(+3.4%). 우리가 저평가, actual=bull 매출 |
| ②영업이익률/전환 | **−$0.85 (지배적)** | base pretax margin 10.5% vs actual ~8.0%. **Wind 손실 −$275M**(모델 ~−$100M 대비 −$175M 초과) + 세그EBITDA→연결 GAAP 웨지(corporate·D&A). Power 18.8%·Elec 18.4%는 견조 |
| ③OP→NI(below-OP/세금) | ~0 | Q2 **클린**(게인은 Q1) → 2024Q2형 below-OP 구제 없음. 세금 정상화 ~우리 22% 근사 |
| ④주식수 | +$0.02 | ~269–270M vs 272M |

→ **EPS 미스의 압도적 원인 = ②(마진/전환), 그 안에서 Wind 손실 초과가 핵심.** "매출 비트인데 EPS 미스" = revenue↑ at Wind loss.

### 11.4 세그먼트 방향 판정
| 세그 | 우리 사전 뷰 | Actual | 판정 |
|---|---|---|---|
| Power | 인라인~소폭↑ | $5,477M(+14%) | ✅ 인라인(살짝 낮음) |
| Electrification | **최선호 상방** | $3,637M(+68%, 컨센 $3.45B 상회) | ✅ **상방 적중** |
| Wind | "핵심은 매출 아닌 **손실폭**" | 매출 $2,026M(컨센 상회) but 손실 −$275M | ✅ **정확** — 매출↑·손실↑ 트랩 |

### 11.5 사전등록 스윙팩터 발화 여부
- ① **below-OP/OP→NI 블록 → 발화 ✅** (정방향 예고 적중). Q2 클린 + Wind 초과손실이 마진 레버로 미스 주도. 우리가 (f)에 1순위로 박아둔 항목.
- ② **세금 → 미발화(중립)**. 정상화 세율 ~우리 가정 근사. valuation-allowance 왜곡은 올바르게 배제.

### 11.6 (c) 가이던스 콜 판정 → ✅✅ 적중
"추가 상향, 확신 중상" 콜 = 적중. 매출 상향 + **FCF 대폭 상향**(거의 2배) + 수주 +88%·백로그 $176B. **주가 스토리 = orders/FCF/guidance(EPS 아님)** 논지 확인.

### 11.7 종합 판정
- ✅ 매출 방향(base 저평가, bull 적중) · 세그먼트 방향(Elec 상방·Wind 손실·Power 인라인) · 가이던스 상향 · EPS 밴드 포함 · 스윙팩터 예고 = **강함**.
- ❌ EPS 포인트 +31% 과대 — **전 Street 동일 방향**. **체계적 = op_margin/net 전환 앵커 과대**.
- 교훈: **"어디서 미스날지"는 맞고 포인트만 틀림** = EFE 리스크-분해 방법론 검증 + 명확한 1개 수정 타깃(op_margin 앵커).

---

## 12. 모델 개선 DEBATE (Claude 개회 주장 → Codex 6축 반론 대기)

> 형식: [Claude 주장] / [예상 Codex 반론] / [Claude 재반박] / [제안 수렴]. Codex는 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성)으로 반박/수용.

### A. op_margin 앵커 과대 → **계절 op_margin 벡터로 재앵커** (체계적 편향)
- **[Claude]** base op_margin 9.2%(+net_int 1.3%)가 net margin 8.2%를 냈으나 actual 6.0%. op_margin을 **연결 adj EBITDA 마진(11.3% actual, FY 12–14%)에서 D&A+corporate+Wind 웨지(~5pp)** 를 뺀 값에 앵커. 스칼라 재앵커 아님 — 아래 반론 수용.
- **[예상 Codex]** (정확성) 1개 분기로 재앵커 위험. Q2는 계절적 저마진(Q4가 최강, EBITDA 12–14%는 FY·Q4 가중). 스칼라 하향 시 Q4 과소예측.
- **[Claude 재반박]** 동의 → **op_margin을 per-quarter 벡터**(스키마 이미 list 지원)로. FY EBITDA 램프에 맞춰 Q2 저·Q4 고. 백테스트는 §5-A `backtest_methodology`와 동일 계절 원리.
- **[제안 수렴]** op_margin/net_int을 **계절 벡터화** + 연결 adj-EBITDA-웨지 앵커 룰 문서화. 회귀표(5종 forward before/after) 첨부.

### B. Wind = **별도 음수 오버레이** (최대 쟁점: generic 순수성 vs 정확성)
- **[Claude]** Wind는 매출 ~18% 비중에 −13.6% 마진(분기 −$275M, lumpy) — blended op_margin에 묻으면 GEV 최대 오차원. Power+Elec를 각 EBITDA 마진으로, **Wind 손실 라인을 시나리오-등록해 차감**하는 최소 오버레이.
- **[예상 Codex]** (범위규율/유지보수성) "순수 top-down, 세그먼트 분해 금지"(generic 경로 존재 이유 = "실제보다 정밀해 보이는 함정" 회피) 위반. 한 종목 위해 세그먼트 모델 추가 = 미끄러운 경사 + 유지비. (건전성) 8분기로 세그먼트 오버레이 과적합.
- **[Claude 재반박]** 바텀업 유닛×ASP와 **다름** — 구조적 손실 세그먼트 1개의 **공시·검증가능**(세그 EBITDA 공시) 보정. `backtest_methodology`처럼 **선택적·가산적 `loss_segment_overlay`**(구조적 적자+공시 세그먼트에만). 미설정 프로파일 불변.
- **[제안 수렴]** 논쟁 유지 — Codex가 (i) 순수성 위반 심각도 (ii) 대안(op_margin 벡터로 Wind 계절성 흡수 vs 명시 오버레이) 판정. **내 우선순위: A(벡터) 먼저, B는 A가 부족할 때만.**

### C. net_interest/below-OP → **steady + lumpy 분리** (구조적 → 밴드)
- **[Claude]** net_int +1.3% 상수는 형태 오류. GEV below-OP는 lumpy(Prolec/Proficy 게인, Wind 충당금)가 steady 이자수익을 압도. **steady 이자(+소) + 시나리오 lumpy(bull +게인/base 0/bear −충당금)** 로 분리. base 포인트 불변 → 밴드만 정직해짐.
- **[예상 Codex]** (건전성) 파라미터 추가 = 8분기 과적합. 시나리오 확률이 이미 포착.
- **[Claude 재반박]** 포인트 파라미터 추가 아님 — net_int을 2성분으로 **재라벨**(base 동일). 밴드 폭의 근거를 명시화. 저위험.
- **[제안 수렴]** base 불변 조건으로 채택 검토. 문서화 우선.

### D. 채점: **매출-스킬 vs EPS-스킬 티어 분리** (검증가능성)
- **[Claude]** 매출 모델 usable(MAPE ~3%, base −3.3%·bull 적중); EPS는 구조적 노이즈(below-OP/세금/Wind). skill 리포트에서 **분리 티어**로 보고 — EPS MAPE가 "모델 스킬" 판정을 오염시키지 않게.
- **[예상 Codex]** 대체로 동의 예상. (유지보수성) skill_metrics 리포트 라벨만.
- **[제안 수렴]** 저쟁점 — 채택.

### E. 넓은 EPS 밴드 **유지** (검증됨)
- actual $2.47 ∈ [bear $1.87, base $3.23]. 넓은 밴드가 actual 포함. **narrow 금지** — 양측 동의 예상.

### 메타 결론 (체계적 vs 구조적 분류 — COMMON §3-5)
- **체계적(YAML 앵커 수정 가능):** op_margin 레벨(A, 계절 벡터). ← 1순위, 다음 분기 즉시 개선.
- **구조적(리스크밴드行):** below-OP lumpiness(C). ← 밴드로.
- **쟁점(중간):** Wind 오버레이(B) — Codex 판정 대기.
- **불변 원칙:** forward 회귀 0 + 9Q sha `b979…f6e7` 유지 + FROZEN 미수정. 모든 변경은 §5-A 패턴(선택적·가산적·회귀표).

### Codex 액션 (debate 개시)
1. A/B/C 각 6축 반박/수용. 특히 **B(Wind 오버레이)의 범위규율 판정**이 핵심.
2. 수용안 → 5종 forward before/after 회귀표 + 9Q sha + pytest 첨부.
3. GEV 재채점 불필요(FROZEN 고정) — 개선은 **다음 분기(2026Q3) 예측부터** 적용.

---

## 13. Codex 6축 리뷰 (REVIEW-ONLY, 2026-07-22)

> 코드 변경 0. 구현은 디베이트 종결과 깨끗한 커밋 베이스 확보 후 별도 세션에서 진행.

### 13.1 요약 판정

| 논제 | 판정 | 핵심 |
|---|---|---|
| A. 계절 `op_margin` 벡터 | **REFINE 후 ACCEPT** | 스칼라 재앵커보다 정확하며 현 스키마가 이미 지원. 단일 Q2가 아니라 최소 8개 분기 연결 GAAP OP margin으로 보정 |
| B. Wind 음수 오버레이 | **REBUT / 보류** | 유닛×ASP 금지를 문자 그대로 위반하지는 않지만, 회사별 세그먼트 P&L을 generic 엔진에 넣어 top-down 단순성 계약을 실질적으로 약화 |
| C. steady + lumpy below-OP | **개념 ACCEPT, 구현 REFINE** | steady는 기존 필드 유지, lumpy는 base=0 및 사전근거가 있는 시나리오/리스크 주석으로 분리. 신규 계산 필드는 당장 불필요 |

### 13.2 A — 계절 `op_margin` 벡터

- **정확성:** Q2 저마진과 Q4 램프를 한 스칼라 9.2%로 동시에 설명할 수 없다. 분기 벡터가 더 정확하다.
- **건전성:** Q2 actual 하나에 맞춘 재앵커는 과적합이다. 최소 8개 분기의 연결 GAAP OP margin과 반복 계절성을 사용해야 한다. `adj EBITDA - 고정 5pp`는 보조 bridge일 뿐 직접 앵커로 쓰지 않는다.
- **회귀안전:** `GenericScenarioAssumptions.op_margin`은 이미 scalar/list를 지원하므로 GEV YAML만 변경 가능하다. 엔진·스키마 변경이 필요 없다.
- **범위규율:** `revenue x op_margin` top-down 계약을 그대로 유지한다.
- **검증가능성:** 공시 연결 GAAP 영업이익으로 분기별 직접 백테스트할 수 있다.
- **유지보수성:** 신규 필드와 회사별 코드가 없어 세 안 중 비용이 가장 낮다.

**권고:** 스칼라 하향이 아니라 시나리오별 계절 벡터. forward 벡터는 시드 다음 분기부터 positional, `backtest_methodology`는 Q1~Q4 calendar-slot이라는 서로 다른 규약을 명시·테스트한다.

### 13.3 B — Wind `loss_segment_overlay`

- **정확성:** Wind를 명시하면 설명력은 높아질 수 있으나 consolidated `op_margin`과 이중 차감될 위험이 있다.
- **건전성:** 한 분기의 초과손실을 구조적 오버레이로 일반화하기에는 표본이 부족하다.
- **회귀안전:** 신규 스키마·계산 순서·이중 차감 방지 규칙이 필요하다.
- **범위규율:** 바텀업 유닛×ASP 금지의 문자적 위반은 아니지만, 종목별 세그먼트 P&L 분해를 generic에 넣는 것은 사실상 회사별 모델의 시작점이다.
- **검증가능성:** 세그먼트 EBITDA는 공시되지만 연결 GAAP OP까지의 corporate·D&A 배분이 불완전하다.
- **유지보수성:** 종목별 예외 오버레이가 연쇄적으로 늘어날 가능성이 크다.

**판정:** 현재는 허용된 좁은 보정으로 인정하지 않는다. 먼저 Wind 계절성을 bear/base/bull `op_margin` 벡터에 흡수한다. 다음 조건을 모두 충족할 때만 재심사한다: (1) 여러 분기에서 반복 잔차의 주원인, (2) 사전 공시 데이터로 산정 가능, (3) 연결 마진과 이중 차감되지 않는 항등식, (4) GEV 전용이 아닌 일반화된 operating-adjustment 계약.

### 13.4 C — steady + lumpy below-OP

- **정확성:** 반복 이자수익과 일회성 처분손익의 분리는 타당하다. 다만 **Wind 영업손실은 below-OP가 아니라 op-margin 레버**이며, Prolec/Proficy 같은 처분손익만 below-OP lumpy다.
- **건전성:** lumpy를 포인트 예측에 넣으면 사후 과적합이다. base=0, 사전근거가 있는 tail만 허용한다.
- **회귀안전:** 물리 필드를 둘로 나누지 않아도 기존 시나리오별 `net_interest_pct_of_revenue`로 수치 효과를 표현할 수 있다.
- **범위규율:** OP→NI는 기존 4-lever generic 계약 안이다.
- **검증가능성:** steady는 반복성을 백테스트하고, lumpy는 사건·금액·근거일을 사전등록해야 한다.
- **유지보수성:** `steady 숫자 + lumpy risk annotation`이 신규 숫자 필드 두 개보다 단순하다.

현재 엔진은 `(OP + net_interest_pct x revenue) x (1-tax)`로 계산하므로 필드의 경제적 의미는 단순 이자보다 **below-OP pretax adjustment**에 가깝다. 당장은 steady에 기존 필드를 쓰고, lumpy는 base 0·근거 있는 bear/bull 시나리오 또는 리스크밴드 주석으로 둔다.

### 13.5 Codex 제안 수렴안

1. 2026Q3에는 **A만 우선 적용**: GEV 시나리오별 계절 `op_margin` 벡터.
2. C는 의미를 명확히 문서화하되 신규 계산 필드는 보류.
3. B는 2~3개 추가 분기의 반복 잔차 증거가 쌓인 뒤 재심사.
4. 매출 skill과 EPS skill은 별도 티어로 보고, 넓은 EPS 밴드는 유지.
5. 구현 시 기존 가드레일 준수: FROZEN 미수정, 5종 forward before/after, generic fallback 회귀, 9Q sha `b979...f6e7`, 전체 pytest.

---

## 14. DEBATE 수렴 (Claude 독립검증 + 반박/수용, 2026-07-22) → Codex 확정본 후보

**Claude 독립 재현(믿지 않고 재계산):** EDGAR에서 이미 수집한 9Q 연결 GAAP OperatingIncomeLoss로 앵커 검증.
- 9Q 연결 GAAP OP margin: 2024 −4.0/+6.4/−4.0/+5.6 · 2025 +0.5/+4.1/+3.7/+5.5 · 2026Q1 +1.9% (평균 +2.2%).
- **재현:** actual 매출 $11,104M·tax22% 고정, op_margin만 교체 → 9.2%(구 앵커)=EPS **$3.37**(여전히 오버슈트, 미스는 매출 아닌 앵커) / 6.5%(연결 GAAP OP)=EPS **$2.50 ≈ actual $2.47**. **EPS 미스 전량이 op_margin 앵커 오차로 설명됨.**
- **B 이중차감 확인:** 연결 GAAP OP 6.5%는 Power+Elec+Wind+corporate를 이미 net → Wind는 그 안에 포함 → 오버레이 추가 시 이중차감. **B 불필요가 수치로 성립.**

### A — ACCEPT (Codex refinement 수용 + 1개 보강)
- 수용: 스칼라 재앵커 폐기, **분기 벡터**. 단일 웨지 공식(adj EBITDA−5pp) 폐기, **연결 GAAP OP margin 직접 앵커**(EBITDA bridge는 보조 설명). 두 벡터 규약 유지(forward=positional, backtest_methodology=calendar-slot, 재혼합 금지).
- **[Claude 보강]** 과거 9Q **평균은 +2.2%로 너무 낮음** — GEV는 마진 급램프(2.2% 추세 → Q2'26 ~6.5%). 따라서 **과거에서 계절 SHAPE(Q2>Q1, Q4 강), 레벨은 forward 궤적/직전 actual(~6.5%)에서** 취해야 함. "1개 분기 과적합"(Codex 우려)도 "평면 과거평균"(과소예측)도 아닌 **shape-from-history × level-from-forward**. 검증: 백테스트는 분기별 공시 GAAP OP로 직접(Codex 지적대로).

### B — CONCEDE (REBUT 수용, 철회)
- Codex의 이중차감 논리가 결정적. 추가로 **이게 원래 오차의 근인을 설명함**: 나는 op_margin을 **세그먼트 EBITDA(Power 17–19%/Elec 18–20%)에 앵커** → 그건 **Wind 적자 + corporate + D&A를 제외**한 값이라 구조적으로 높았음(9.2%). A를 **연결 GAAP OP에 올바로 앵커하면 Wind가 자동 흡수** → B는 잉여.
- 재검토 게이트(Codex 4조건: 다분기 반복 잔차·공시 사전산정·무이중차감 항등식·일반화 계약) 동의. 최소 2–3분기 잔차 증거 축적 후 재심.

### C — ACCEPT (Codex 정정 수용)
- **정정 수용:** Wind 영업손실 = **op-margin 레버**(→ A로 흡수), below-OP lumpy는 **Prolec/Proficy 처분이익류만**. 4-lever 귀인(§11.3)은 Wind를 레버②에 올바로 넣었으나, Thesis C 서술이 이를 흐렸음 — 정정.
- 신규 계산 필드 **보류**: steady=기존 `net_interest_pct_of_revenue`(실질은 "below-OP pretax adjustment", 필드명↔의미 문서화), lumpy **base 0**, bear/bull은 **공시 근거 사전존재 시만** 시나리오화, 그 외는 **리스크밴드 annotation**(숫자 아님).

### 수렴 설계 (2026Q3부터 적용 — GEV 재채점 없음)
1. **A만 구현:** GEV 시나리오별 **계절 op_margin 벡터**(shape=9Q 연결 GAAP OP, level=~6.5% Q2 기점 램프). net_int=steady below-OP.
2. **C=명세:** steady/lumpy 구분 문서화, 신규 필드 없음, lumpy base 0 + annotation.
3. **B=보류:** 2–3분기 잔차 재심.
4. 매출-skill / EPS-skill **별도 티어** 보고.
5. **EPS 밴드 축소 금지**(actual $2.47 ∈ [$1.87,$3.23] 검증).
- **불변 원칙:** forward 회귀 0 · 9Q sha `b979…f6e7` 유지 · FROZEN 미수정 · 5종 before/after 회귀표 · §5-A 선택적·가산적 패턴.
- **상태:** 디베이트 **수렴**. Codex 확정본(구현) 대기 — 단, **깨끗한 커밋 베이스 확보 후**(현재 미커밋 다종목 작업과 분리).

---

## 15. 어닝콜 개선점 확인 → §14 앵커 보강 (Codex 평가용, 2026-07-22 콜 종료 후)

**콜 팩트(트랜스크립트/highlights, source: Benzinga/Investing.com/Yahoo):**
- adj EBITDA **+61% → $1.2B**, **마진 +340bps**, 그러나 **EPS $2.47 lagged** — 경영진이 EBITDA→EPS 브릿지 명시 안 함.
- Wind EBITDA 손실 **−$275M(Q2) "in line"**, FY **~$400M** → **전반 집중(front-loaded)**, 균등 −$100M/분기 아님. Q3 Wind 매출 low-double-digit 감소 전망.
- CFO(Ken Parks): FCF가 **"higher taxes" YoY**로 압박 → 세금 정상화가 **상방**(구체 세율 미제시).
- 자사주: $10B 프로그램 중 누적 **$7B/12.4M주/평균 $560**, **$3B 잔여**; 2026 총 ~$4B 환원(배당 포함).
- 주가 프리마켓 **−3.1% → $1,045**(−$33.71).

**개선점 판정 (§14 수렴안 대비):**
1. **A(op_margin 앵커) — 콜이 실시간 입증.** "세그먼트/adj EBITDA는 +340bps인데 EPS lagged" = **세그먼트 EBITDA에 앵커하면 안 되고 연결 GAAP OP에 앵커해야** 함(§14 A-refinement 그대로). Prolec 인수 purchase-accounting 상각·D&A가 EBITDA→GAAP OP 웨지의 유력 구성 → 연결 GAAP OP 앵커가 이를 자동 포착. **설계 변경 없음, 강화.**
2. **A 계절 SHAPE — Wind 전반 집중 반영.** Wind를 flat −$100M/분기로 모델하지 말 것($275M이 Q2 한 분기). 연결 GAAP OP 앵커가 Wind 타이밍을 자동 흡수 → **B-hold 재확인**(Wind lumpy·사전산정 어려움, Codex 게이트 부합).
3. **세율 — 상방 감시.** CFO "higher taxes" → 정상화 세율이 우리 base 22%보다 **높을 수 있음**. Q3 base는 **23–25% 검토**, 10-Q(companyfacts 갱신 시) IncomeTaxExpenseBenefit로 확정.
4. **Lever-4 주식수 — 소폭 하향.** 자사주 지속($3B 잔여) → forward 희석주식수 **~270M 및 감소**(272M에서 넛지).
5. **C(below-OP) — 스펙 유지.** 콜에 이자수익 분해 없음 → steady=기존 net_int, lumpy base 0 유지. Prolec 상각은 below-OP 아니라 **op-margin 웨지**(→A). §14 C 정정과 일치.
6. **[thesis 검증, 모델 변경 아님]** 주가 −3.1% — 가이던스 상향+기록적 수주에도 **EPS 컨센/위스퍼($3.47) 미스로 fade**. §11 "beat-but-fade" 반응함수 적중. 채점 크레딧.

**순효과:** §14 A/B/C 수렴안 **변경 없이 강화**. 콜이 제공한 Q3 구체 앵커 = 세율 23–25%(상방)·주식수 ~270M 감소·Wind lumpy·연결 GAAP OP 앵커 검증.

**Codex 평가 요청:** (i) 위 Q3 앵커(세율 상방·주식수·Wind lumpy) 타당성 6축 확인, (ii) A 구현 시 op_margin을 **연결 GAAP OP 계절 벡터**로 확정하는 설계 승인, (iii) B-hold 유지 재확인(콜의 lumpy Wind가 hold 근거 강화). 구현은 **clean 커밋 베이스 확보 후·2026Q3부터**, 가드레일 불변(forward 회귀 0·9Q sha `b979…f6e7`·FROZEN 미수정·5종 회귀표).

---

## 16. Codex §15 평가 회신 → 최종 설계 확정 (Claude 10-Q 독립검증, 2026-07-24)

**Claude 독립검증 (Codex 수치를 믿지 않고 10-Q 원문 대조, source: gev_webcast_10q_07222026.pdf):**
Q2 2026(3개월) 연결 손익계산서 — 매출 11,104 · 매출총이익 2,360 · SG&A 1,372 · R&D 334 · **영업이익 653(5.88%)** · 이자·기타금융수익 73 · 비영업연금수익 119 · 기타수익 80 · **세전 925(8.33%)** · **법인세 276 → 유효세율 29.8%** · 순이익 649 · **GE Vernova 귀속 668** · 희석 EPS 2.47 · 희석주식수 270M. **below-OP 합 +272(+2.45%)**.
→ **Codex의 OP $653M/5.88%·세율 29.8%·주식수 270M 전부 정확.** 내 §15의 op 6.5%·세율 23–25%는 오차 — 수용·정정.

**FROZEN base 오차 재분해(actual 매출 고정):** op 9.2%→5.88%(EPS +약$1.0 과대) · below-OP 1.3%→2.45%(우리 과소계상, EPS −$0.35) · 세율 22%→29.8%(우리 과소계상, EPS +$0.30) · 주식수 272→270. op(과대)+세율(과소)이 EPS를 밀어올리고 below-OP(과소)가 일부 상쇄 → 순 과대. **op_margin이 최대 단일 원인이나 세율·below-OP도 유의미 → 세 레버 동시 보정 필요.**

### 최종 판정 (Codex 회신 수용 + 2개 보강)
- **A op_margin — ACCEPT (Codex 정정 수용).** 앵커 = **연결 GAAP OP margin 계절 벡터**. Q2 실측 **5.88%**(6.5% 아님). Q3는 Wind −$275M→**약 breakeven** 개선분(~+2.5pp) 반영해 Q2보다 높게(~7–8%). shape=과거, level=실측/forward. Power 17–18%·Elec(Q2 18.4%보다 소폭↑) EBITDA는 보조 교차확인.
- **세율 — ACCEPT REFINE (Codex 수용).** Q2 유효세율 **29.8%**(PPA 조정 + 세금혜택 없는 지역손실). **단일 base 앵커 금지 → Q3 23–30% 시나리오 범위**(PPA가 2027Q1까지 변동). 콜 "higher taxes"는 현금흐름 설명이지 P&L 세율 근거 아님(내 §15 오독 정정).
  - **[Claude 보강 ①] Wind↔세율 커플링:** 29.8%를 끌어올린 "세금혜택 없는 지역손실"은 상당부분 Wind 적자. Wind가 Q3 breakeven로 개선되면 **op-margin과 유효세율이 동반 개선** → 23–30% 범위에 **하향 드리프트** 편향(고정 29.8% 아님).
- **주식수 — ACCEPT.** Q2 희석가중 270M·분기말 266.3M. Q3 **268–270M 감소 민감도**로($3B 자사주 잔여) 고정 270M보다 표기.
- **C net_int — ACCEPT + 보강 ②.** steady=`net_interest_pct_of_revenue`, lumpy base 0 유지, GAAP OP·세율과 혼합 재앵커 금지(Codex). **[Claude 보강 ②]** Q2 steady below-OP(이자 73 + 비영업연금 119 ≈ +1.7%)가 우리 1.3% 가정보다 높음 → steady 앵커 **1.3%→~1.6%** 상향(lumpy(기타 80·처분이익류)는 여전히 base 0 + annotation).
- **B Wind 오버레이 — HOLD 재확인.** 연결 GAAP OP가 Wind·corporate·D&A 이미 포함(10-Q OP 653이 그 증거) → 오버레이=이중차감. 유지.
- **D/E** 유지: 매출/EPS skill 별도 티어 · EPS 밴드 축소 금지.

### 최종 승인 설계 = "연결 GAAP OP 계절 벡터" (2026Q3 프로파일)
| 레버 | Q3 앵커 | 근거 |
|---|---|---|
| op_margin(base) | ~7–8%(Q2 5.88% + Wind breakeven ~+2.5pp), 계절 shape | 연결 GAAP OP 실측 |
| tax | 23–30% 범위, 하향 드리프트(Wind개선) | Q2 29.8%, PPA 변동 |
| net_int steady | ~+1.6% | Q2 이자+연금 +1.7% |
| lumpy below-OP | base 0 + annotation | 처분이익류 예측불가 |
| 주식수 | 268–270M 감소 | Q2 270M, $3B 자사주 |
| EPS 밴드 | 광폭 유지 | actual $2.47∈[$1.87,$3.23] |

**구현 = HOLD (Claude 동의).** worktree가 다종목 변경으로 매우 더러움 → **clean 커밋 베이스 확보 후** Codex 구현, **2026Q3부터**. 가드레일 불변: forward 회귀 0 · 9Q sha(env별 canonical) · FROZEN 미수정 · 5종 before/after 회귀표 · §5-A 선택적·가산적 패턴.
**디베이트 완전 종결.** 남은 것은 clean base에서의 A 구현 1건뿐.

---

## 17. Claude 독립검증 — A DEV 프로파일 (2026-07-27)

**독립 재현(Codex 보고 불신, 원 worktree 코드+DEV 프로파일을 샌드박스에 stage해 직접 재실행):** `profiles/gev_q3_2026.dev.generic.yaml` sha `b0e9c40137e1ddf2bcc99fc479f99d4ba6f1d102128e2d0dcfa5e1f8709c1b35` 일치. `schemas/generic.py`에 `backtest_methodology.op_margin` 캘린더-슬롯 분리 확인. `generic_cli.py` 재실행 결과 **Codex 수치 전부 일치**:

| 항목 | Codex | Claude 재실행 |
|---|---|---|
| DEV weighted Q3 | $12.159B / $3.04 | **$12,159M / $3.04** ✓ |
| 2024Q2 backtest EPS | $1.58 (actual $4.65) | **$1.58** ✓ |
| 2025Q2 backtest EPS | $1.72 (actual $1.86) | **$1.72** ✓ |
| 2026Q2 backtest EPS | $2.05 (actual $2.47) | **$2.05** ✓ |
| EPS MAPE | 156.10%→70.23% | **70.23%** ✓ |
| 매출 MAPE | — | **2.96%** ✓ |

DEV 벡터: forward op_margin base/bear/bull [.075,.085,.035,.068]/[.055,.065,.020,.050]/[.095,.105,.050,.085]; backtest_methodology op_margin calendar [Q1..Q4] [-.005,.055,-.002,.056](=9Q 연결 GAAP OP 캘린더 평균).

**A 효능 판정:**
- **반복 가능한 Q2 오차 제거:** 2025Q2 +40.3%→**−7.5%**, 2026Q2 +25.9%→**−17.0%(크기)**. EPS MAPE **156%→70%(반감)**, 매출 MAPE 2.96%(불변). op_margin을 연결 GAAP OP에 앵커한 A가 **체계적 과대편향 제거** 확인.
- **2024Q2 미설명(의도대로):** model $1.58 vs actual $4.65 — 일회성 처분이익성 below-OP는 op_margin으로 불가. 잔여 70% MAPE의 지배원 → **C-레버(lumpy below-OP=리스크밴드/annotation)**, 구조적 분류대로.
- **2026Q2 소폭 언더슛(−17%):** steady net_int(~1.6%)가 그 분기 높은 below-OP(연금+기타 +2.45%) 과소계상 → C-레버 변동성(밴드 담당).

**정직한 캐비엇 (Codex 명시 + Claude 확인):**
1. **In-sample 캘린더 평균 fit이지 out-of-sample 예측 스킬 아님.** 편향 제거는 확인, 진짜 검증은 **2026Q3 실제 프린트(~10월)**.
2. 잔여 EPS MAPE 70%는 2024Q2 처분이익 분기 지배 → **향후 소개선: EPS-skill 지표에서 일회성 below-OP 분기 annotation/제외**(C+D 연계).

**가드레일:** Claude는 DEV forecast만 재실행. 5종 forward MATCH·9Q sha b979·214 pass는 Codex 보고 채택 — **A=새 파일·코드 0변경**이므로 타 종목·불변식 구성상 보장(schemas backtest_methodology 기존 존재 확인).

**판정: A DEV 검증 PASS. in-lab 검증 완결.** 남은 단일 트리거 = **2026Q3 out-of-sample 프린트**(START-Q3 세션, fresh 컨센으로 재동결)가 A의 예측 가치를 최종 판정. GEV Q2 2026 사이클(동결→채점→디베이트→A구현·검증) 전체 종료.
