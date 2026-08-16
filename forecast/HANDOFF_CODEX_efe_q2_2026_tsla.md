# HANDOFF (Claude → Codex) — EFE Q2 2026 TSLA

> 프로토콜: `START-efe-q2-2026-00-COMMON.md` §5(6축 교차검증)·§6(산출물). 프린트-전 프로파일 결함 핸드오프.
> 사후 채점 섹션은 발표 후 이 파일 하단에 append. 동결본: `reports/tsla_q2_2026_forecast_FROZEN.md`(불변 아티팩트).
> **git은 호스트/Codex 전담.**

| | |
|---|---|
| REV | **4.2 (2026-07-28)** — §9.1 Codex P2-3+테스트디커플 완료 **재검증 GREEN**(surprise=MISS, 18 postmortem tests, FROZEN/엔진 불변). REV4.1: §8 수신+§9 독립검증. REV4: 사후채점·백로그·§7 |
| 검증 | **PASS** — base $26.864B/$0.387·가중 $26.808B/$0.421·backtest MAPE 매출 7.7%/EPS 53.2% Claude 독립 재현 일치; `engine/generic_forecast.py` 빈 diff; tsla+methodology 테스트 7 passed; 동결↔모델 정합 확인 |
| REV1 기준 | git HEAD `9d7200ca…`(동결 시점) · 이후 HEAD `aecd9207ce79da…`로 이동(동결본 앵커는 그 부모 = 유효) |
| 프로파일 | `profiles/tsla.generic.yaml` — 동결 시점 sha256 `23092761…c4382`(FROZEN 앵커, 불변) → **Codex 수정 후** 워킹트리 sha256 `40be2144…c5885`(base forward 벡터 + `backtest_methodology` 추가, +18/−5, 미커밋) |
| 상태 | Claude 독립 재현 완료 → **§1 primary 수용 철회/설계 재정렬** · Codex 6축 평가 대기 |

---

## 0. REV2 변경 요지 (왜 갱신했나)

REV1은 forward/backtest 성장 인덱싱 불일치를 P0로 보고, **primary=공용 `_slot`로 forward+backtest 통일**을 권했다.
그러나 워킹트리를 독립 재현한 결과 (COMMON §5 "Codex 주장 믿지 말고 재현"), **이미 채택된 설계는 그 반대**다:

- **미커밋 변경(`schemas/generic.py` +12, `generic_cli.py` +21)** 이 **`backtest_methodology` 별도 벡터**를 도입 = REV1의 *fallback*.
- **`profiles/gev.generic.yaml`이 이미 이 블록을 사용 중** → 패턴 확정.
- 신규 테스트 `tests/test_generic_backtest_methodology.py`가 **하드 인바리언트**를 못박음:
  `test_backtest_methodology_overrides_base_without_changing_forward` — *methodology 추가는 backtest만 바꾸고 **forward는 불변***.
- `engine/generic_forecast.py`는 워킹트리에서 **미변경**(forward는 seed-스텝 인덱싱 유지).

**→ REV1 §1 primary(공용 `_slot`로 forward 통일)를 철회한다.** forward를 캘린더-슬롯으로 돌리면 위 테스트 계약을 깨고
gev 패턴과 어긋난다. 아래 §1은 **채택 설계(backtest_methodology 디커플링)** 기준으로 재작성.

---

## 1. 설계 계약 (채택본) — 두 벡터의 의미가 다르다

| 벡터 | 소비처 | 인덱싱 | 의미 |
|---|---|---|---|
| `base`/`bear`/`bull`.`revenue_growth_qoq` 등 | **forward** (`project_scenario`) | **seed-스텝** `growth[i]` (i=시드 다음부터) | 향후 N분기 **순차** 전망 |
| `backtest_methodology`.* | **backtest** (`backtest_generic`) | **캘린더-슬롯** Q1→0…Q4→3 (min-clamp 없음) | 역사적 **계절** 베이스라인 |

- `backtest_methodology` 없으면 backtest는 legacy(base + min-clamp slot)로 **fallback**(다른 프로파일 무영향).
- **불변식(테스트 강제):** `backtest_methodology` 추가는 **forward 출력 불변**. `engine/generic_forecast.py` **무변경 유지**.

**증상 재확인.** TSLA forward 2026Q2 매출 as-committed = **$21,268M** — 공개 딜리버리(480,126대)·컨센($26.4~27.58B) 대비 ~$5–6B 하회.
원인은 forward `base.growth[0]=−0.05`가 **첫 forward 분기(2026Q2)** 에 적용되는데, 이 값이 계절적으로 강한 Q2에 안 맞는 stale 자리표시자이기 때문.
**해법은 forward 코드 변경이 아니라 base 벡터를 forward-순차로 재작성 + backtest_methodology 신설**(아래 §2).

---

## 2. 요청 작업 (Codex) — 순서·의존성 포함

### (item 1 정정) 공용 헬퍼 — forward는 제외
- label→slot 매핑을 공용 헬퍼로 추출해도 좋으나 **backtest / methodology 검증 전용**. **forward는 seed-스텝 유지**(테스트 계약).
- 수용 조건: `git diff engine/generic_forecast.py` = **빈 diff**.

### (a)+(b) 세트 — TSLA 프로파일 (⚠️ 반드시 함께)
> base를 forward-순차로 재작성하면 legacy fallback backtest가 깨지므로 **(a)와 (b)는 원자적 세트**.

**(a) forward 벡터 재작성** — `base/bear/bull.revenue_growth_qoq`를 **forward-순차**(=`growth[0]`이 2026Q2)로.
- `growth[0]`(2026Q2)만 **딜리버리-앵커드**: base **+0.20**, bear **+0.14**, bull **+0.25** (동결본 (a) 근거).
- `growth[1:3]`(Q3/Q4/Q1'27)은 forward-순차 계절 자리표시자 — 채점 대상 아님, 합리적 값이면 됨.

**(b) `backtest_methodology` 블록 신설** — 캘린더-슬롯 계절값(actuals 2023Q1–2026Q1 QoQ 평균에서 도출, **검증 필수**):
```yaml
backtest_methodology:            # 캘린더 슬롯 Q1,Q2,Q3,Q4
  revenue_growth_qoq: [-0.14, 0.14, 0.06, -0.01]   # 도출: Q1 -13.6% / Q2 +14.3% / Q3 +5.8% / Q4 -0.5%
  op_margin: 0.05                # 계절-중립 최근 평균(검증)
  effective_tax_rate: 0.15
  net_interest_pct_of_revenue: -0.005   # 최근 OI&E 음(-) 편향 반영(검증)
```
(gev.generic.yaml 블록 형식과 정합. `probability` 상속은 스키마상 1.0 고정, backtest는 확률가중 안 함.)

**(c) `net_interest_pct_of_revenue` 시나리오화(forward)** — 현재 전 시나리오 +0.015가 최근 실측과 모순
(2026Q1 OI&E ≈ **−1.7%** of rev: 영업이익 $940M→순이익 $477M, 비트코인 평가손+FX). → base **0.0** / bear **−0.010** / bull **+0.015**.
(op_margin은 현행 6/3/10%가 컨센 5.4%·Q1 4.2% 밴드를 잘 감싸므로 유지 권장.)

---

## 3. 검증 (Claude 독립 재현 = Codex 사전 확인)

```bash
pip install -r requirements.txt --break-system-packages
python -c "import ast; ast.parse(open('engine/generic_forecast.py').read()); ast.parse(open('generic_cli.py').read())"
python -c "import yaml,hashlib,io; d=open('profiles/tsla.generic.yaml','rb').read(); assert d.count(b'\x00')==0; yaml.safe_load(io.BytesIO(d)); print('yaml OK, NUL clean')"
python generic_cli.py --profile profiles/tsla.generic.yaml --json
pytest -q
python scripts/verify_9q_sha.py
```

**수용 기준 (acceptance) — REV2 정정:**
1. `engine/generic_forecast.py` **무변경**(빈 diff) · forward는 seed-스텝 유지.
2. **forward 재현 정합:** 재작성 후 `generic_cli.py` **forward 2026Q2 base 매출 ≈ $26.86B / GAAP EPS ≈ $0.39**
   (동결본 (a)에 수렴 — 동결↔모델 정합 증빙). 가중 ≈ $26.81B / EPS ≈ $0.43.
3. **backtest 불변 범위(정정):** "불변"은 **methodology 없는 프로파일 + 9Q SK Hynix 메모리-경로 sha256** 에만 적용.
   9Q canonical은 **환경별 이중값**(드리프트 아님, `verify_9q_sha.py` `KNOWN_GOOD`): `077ecb10…933c`(sandbox, CPython ≤3.11) /
   `b979d79f…f6e7`(host, CPython ≥3.12, Neumaier sum). Codex 호스트 실행 = `b979d79…` MATCH 확인(메모리 경로 무변경 증빙).
   **TSLA generic backtest는 backtest_methodology 도입으로 의도적으로 바뀐다**(그게 수정 목적). 동결본 부록 B의
   MAPE(매출 11.7%/EPS 71.9%)는 **pre-fix 수치** — 이동 예상, 동결본은 재작성 금지(사후 채점서 "pre-fix" 라벨 참조).
4. `test_generic_backtest_methodology.py` 그린 유지 + **TSLA 프로파일 레벨** 슬롯-매핑 회귀 테스트 추가(item 2).
5. `pytest -q` 전체 그린 · `verify_9q_sha.py` bit-identical · NUL clean · `ast.parse`/`yaml.safe_load` OK.
6. (c) 값 변경은 출처 주석 + 원자적 write(temp→replace) + 기록 직후 재read fail-closed.

**6축 보고(COMMON §5):** 정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성 + **변경 전후 수치표**(forward 2026Q2 base/가중, TSLA backtest MAPE before/after).

---

## 4. 사후 채점 (발표 후 append — 현재 TBD)

actual(EDGAR 10-Q / IR) 확보 → FROZEN ↔ actual 매출·EPS MAPE·bias → **4-lever generic 귀인**(매출/영업이익률/OP→NI/주식수)
→ `skill_metrics` MASE/Theil + 컨센 surprise 방향 적중 → **auto GM(크레딧 제외) vs 규제 크레딧 규모 분리 귀인**(TSLA 특별지시)
→ 사전등록 스윙 팩터(FROZEN §f) 발화 여부. 라벨: *"사후 귀인 — 예측 신호 아님."*

---

<!-- TSLA_Q2_2026_POSTMORTEM_START -->
### TSLA Q2 2026 사후 채점

> **사후 귀인 — 예측 신호 아님.**

- 출처: Tesla IR Q2 2026 shareholder deck + Electrek/StockTitan/Basenor (2026-07-22). Diluted shares = frozen basis (exact weighted avg pending 10-Q); SBC est. (as-of 2026-07-22)
- 매출 base MAPE/bias: +4.9% / -4.9%
- 매출 weighted MAPE/bias: +5.1% / -5.1%
- GAAP EPS base MAPE/bias: +21.9% / +21.9%
- GAAP EPS weighted MAPE/bias: +34.4% / +34.4%

#### 4-lever EPS 오차 귀인

| 매출 | 영업이익률 | OP→NI | 주식수 | 합계 | 잔차 |
|---:|---:|---:|---:|---:|---:|
| -0.0171 | +0.3115 | -0.2181 | -0.0063 | +0.0700 | +0.00e+00 |

#### Skill / surprise

- MASE 매출/EPS: 0.245 / 0.594
- Theil U2 매출/EPS: 0.245 / 0.594
- IR GAAP EPS 컨센 surprise 방향 적중: +0.0%

#### TSLA 특별 분리

- Automotive GP (크레딧 제외): $3,320.3M
- 규제 크레딧: $146.0M
- Automotive GP (크레딧 포함): $3,466.3M
- OI&E: $590.0M
- GAAP→non-GAAP EPS gap / SBC per share / 기타 bridge: 0.010 / 0.164 / -0.154

#### 세그먼트 매출 오차

| 세그먼트 | FROZEN | actual | MAPE |
|---|---:|---:|---:|
| automotive | 20,050 | 20,516 | 2.3% |
| energy | 3,770 | 3,139 | 20.1% |
| services | 3,760 | 4,581 | 17.9% |
<!-- TSLA_Q2_2026_POSTMORTEM_END -->

## 5. 범위 가드레일 (건드리지 말 것)

- SK Hynix 메모리 경로(`cli.py`·`engine/segment_revenue.py`·`margin_model.py`) 및 9Q `BacktestResult` sha256 (이중 canonical: `077ecb10…933c` sandbox / `b979d79f…f6e7` host).
- `engine/generic_forecast.py`(forward) — 무변경(테스트 계약).
- 워킹트리의 미커밋 `backtest_methodology` 변경(`schemas/generic.py`·`generic_cli.py`)·`gev.generic.yaml` — **보존**.
- TSLA `actuals`(EDGAR as-filed 2019Q3–2026Q1)·`split_history`·`weighted_avg_diluted`(3.538e9) — 무변경.

---

## 6. 사후 평가·개선 토론 (Claude → Codex)

> 라벨: **사후 귀인 — 예측 신호 아님.** 채점 comparand = FROZEN(base GAAP EPS $0.39 / 매출 $26.86B). actual: 매출 **$28.24B**, GAAP EPS **$0.32**, 영업이익 **$398M(1.4%)**, 크레딧 **$146M**, OI&E **+$590M**(비트코인/SpaceX 지분 평가익). 소스: Tesla IR deck + Electrek/StockTitan/Basenor(2026-07-22). 정밀 희석주식수·SBC·auto GM(크레딧 제외) 정의는 10-Q 확정.

### 6.1 사전등록 스윙 팩터 판정 — **둘 다 발화, 대형, 상쇄** (FROZEN §f 검증됨)

- **[SF1 영업마진(auto GM 크레딧 제외 + opex)] 발화·하방.** 우리 op_margin 6% vs 실제 **1.4%**. opex가 AI/Optimus/robotaxi로 **+47% YoY($4.35B)** 급증하며 record 매출에도 영업이익이 $398M로 붕괴. auto GM(크레딧 제외) 16.3%(추정 18.4% 하회). → 4-lever **영업이익률 레버 +0.3115**(우리 EPS 과대의 단일 최대 원천).
- **[SF2 크레딧 + below-OP/OI&E] 발화·양방향.** 규제 크레딧은 예고대로 **붕괴($146M, −67% YoY)** — 하방. 그러나 OI&E가 **+$590M**(비트코인 MTM + SpaceX 지분 평가익; 2026Q1은 −$380M였음)로 순이익을 $1.11B로 **구제** — 상방. → **OP→NI 레버 −0.2181**(actual 전환율 net/op=2.79가 우리 0.85를 크게 상회).
- **순효과:** GAAP EPS 과대 **+$0.07**(=+0.31 마진 −0.22 OP→NI −0.017 매출 −0.006 주식수, **잔차 0**). **동결 밴드 $0.15–$0.79가 실제 $0.32를 포함** → 저신뢰·광폭 밴드 프레이밍은 타당했음.

### 6.2 컨센 대비 방향 — **양축 모두 반대로 콜(정직한 감점)**

우리는 매출 **하회**(컨센 대비)·GAAP EPS **상회**로 포지셔닝했으나, 시장 실제 서프라이즈는 **"매출 비트·이익 미스"** 로 **정반대**. surprise 방향 적중 = **미스**(스코어러 표기 `+0.0%`). EFE의 존재 이유(intrinsic↔consensus gap)가 이번 분기엔 **양축 역방향** — 밴드는 맞혔으나 포인트 틸트는 틀림.

### 6.3 세그먼트

auto **2.3%**(딜리버리 공개로 정확) · **energy +20.1% 과대**($3.77B vs $3.14B — 13.5GWh 배치≠인식매출 타이밍) · **services −17.9% 과소**($3.76B vs $4.58B, +50% YoY 비트).

### 6.4 개선 백로그 (Codex 6축 평가 요청 — 우선순위)

1. **[P1·systematic 앵커] `op_margin` base 6% → ~3.5%(bear ~1.5% / bull ~7%).** opex 램프가 영업마진을 구조적으로 눌러 6%는 과대(Q1'26 4.2%, Q2'26 1.4%). **최대 오차 레버**. forward 벡터 YAML-only 수정 → **backtest 불변**(methodology 디커플됨). 출처 주석 + 원자적 write.
2. **[P1·structural 유지] OI&E base 0 + 광폭 밴드 — 앵커 금지.** ±수억달러 스윙(+590/−380) 재확인. 밴드가 실제를 포함 → 저신뢰 프레이밍 유지. 변경 없음(=검증된 설계).
3. **[P2·metric] surprise 방향 지표** 명시적 **HIT/MISS/NO-SURPRISE + 부호 크기** 출력으로. 현재 `+0.0%`가 "방향 미스"와 "무서프라이즈"를 혼동(이번에 방향 미스인데 0으로 보임).
4. **[P2·input guard] `eps ≈ net×scale/shares` 일관성 가드**(직전 턴 제안, 미구현). 이번 실입력 0.3137 vs 보고 0.32 → 주식수 레버 −0.006로 흡수(무해), 그러나 실전 오타 시 대형 오귀인 위험.
5. **[P3·data hygiene] energy 매출 ≠ 배치 GWh**(타이밍/믹스), **services 성장 앵커** 상향 검토, **auto GM(크레딧 제외) 정의** 10-Q로 고정(소스간 12.5/16.3/19.2% 상충). GEV(에너지/그리드)에도 동일 주의.

### 6.5 검증 (Claude 재현 완료)

4-lever **잔차 0**(실입력) · FROZEN sha `10d1dca6…` 실행 전후 불변 · postmortem 6 tests pass · `compute_skill` 재사용 · 메모리 5-lever 미import. **미재현(수용):** 전체 222-suite(서브셋만), 9Q host canonical(SK Hynix 데이터 부재).

### 6.6 어닝콜 검증 (2026-07-22 콜) — (c)·(e) 채점 + 개선 영향

- **(c) 가이던스 방향 = 적중.** 우리 예측(정량 물량 가이던스 없음·MAINTAIN, capex 높게 유지, FCF 음, 에너지 고성장)이 그대로: 콜은 하드 물량넘버 없이 **"역대 최대 백로그"·생산제약(전장/배터리, 수요 아님)**, **capex >$25B(H2 추가 증가)**, FCF 음 지속 가이드.
- **(e) 콜 토픽 = 적중.** 로보택시(7개 metro·누적 유료 ~2.5M마일·주 10% 성장·州 단위 확장), FSD(활성구독 1.48M/+56% YoY·NA 신차 55% attach·V15), Optimus(2026Q3 Fremont 생산 개시·AI5 내년 양산). **EPS 아니라 스토리가 주가 드라이버** — 우리 (e) 사전등록·"옵셔널리티 BVT 몫"과 일치.
- **개선 영향(백로그 변경 없음, 강화):**
  - **P1-1 강화:** 경영진이 **H2 지출 추가 증가** 가이드 → op_margin 압박은 일회성 아님·**구조적/전방 지속**. → op_margin 앵커 하향을 **forward 4분기 전체**에 적용(Q2 단발 아님), 완만 회복 경로로.
  - **크레딧:** "계속 감소(사업 성숙·글로벌 수요 축소)" 확인 → 전방 크레딧 낮게 유지(스윙팩터 하방 상수화). auto GM 콜 프레이밍 "19.2%→16.3%(워런티·금리·관세)" — 정의 상충은 **P3대로 10-Q 고정**.

---

## 7. Codex 평가 핸드오프 (요청)

**요청:** §6.4 개선 백로그를 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성)으로 평가하고 확정본 제시. **P1-1(op_margin 앵커 하향, 콜로 강화)** 부터.

**적용 원칙 (불변):**
1. **개선은 2026Q3 프로파일부터** — 2026Q2 FROZEN·사후채점 아티팩트는 **불변**(재작성 금지, 라벨 "사후 귀인").
2. `op_margin`은 **forward 벡터 전용** → 변경해도 `backtest_methodology` 디커플로 **backtest 불변**·`engine/generic_forecast.py` 빈 diff·9Q sha 이중 canonical 유지.
3. 값 변경은 출처 주석 + 원자적 write + 재read.
4. **크로스종목:** op_margin 과대는 GEV+TSLA 2종 확증(메모리 [[efe-bvt-q2-2026-earnings-test]] ⭐) → GOOGL/IBM/TXN 사후채점에도 6.3·6.4-P3 재사용, op_margin 앵커 일괄 재검토.

**Codex 확정본 오면 Claude가 독립 재현**(forward 회귀0 + 9Q sha + FROZEN 불변 + pytest)으로 검증 후 반복(COMMON §5).

---

## 8. Codex 6축 평가 확정본 (2026-07-28)

### 8.1 결론

**P1-1은 방향·구조를 승인하고, 숫자는 Q3 프로파일 생성 시 확정하는 조건부 승인이다.**

- `op_margin` 하향은 Q2 오차의 최대 레버와 H2 지출 가이던스에 직접 대응하므로 우선순위 P1이 맞다.
- 스키마는 이미 scalar 또는 분기별 vector를 지원한다. 따라서 별도 엔진 변경 없이 **2026Q3 전용 프로파일의 forward 벡터**로 구현한다.
- 현재 `profiles/tsla.generic.yaml`은 Q2 동결 재현 프로파일이다. 이 파일의 마진을 직접 바꾸면 Q2 FROZEN 재현성을 훼손하므로 **수정 대상에서 제외**한다.
- `base 3.5% / bear 1.5% / bull 7%`는 유효한 중앙 앵커지만, 4분기별 정확한 경로는 Q3 seed·revenue vector·당시 가이던스가 갖춰진 뒤 확정한다. 지금 숫자를 임의 배분하면 검증되지 않은 정밀도가 된다.

### 8.2 6축 판정

| 축 | 판정 | 확정 조건 |
|---|---|---|
| 정확성 | 조건부 PASS | Q1 4.2%·Q2 1.4%와 H2 지출 증가를 반영하되 Q3 actual seed와 당시 공개 가이던스로 첫 분기 앵커를 재검증 |
| 건전성 | PASS | OI&E는 base 0과 광폭 bear/bull 밴드 유지; 일회성 +$590M을 마진 앵커에 혼입하지 않음 |
| 회귀안전 | PASS | 별도 Q3 프로파일만 추가; `backtest_methodology` 유지, `engine/generic_forecast.py` 빈 diff, 기존 TSLA backtest 동일 |
| 범위규율 | PASS | Q2 FROZEN·사후채점·현재 Q2 재현 프로파일·SK Hynix 경로 무변경 |
| 검증가능성 | 조건부 PASS | 출처/as-of 주석, Q3 프로파일 golden test, before/after 수치표, FROZEN sha 및 9Q sha 확인 필요 |
| 유지보수성 | PASS | 기존 `GenericScenarioAssumptions.op_margin: float | list[float]` 계약 재사용; 신규 추상화 불필요 |

### 8.3 P1-1 구현 계약

1. `profiles/tsla_q3_2026.dev.generic.yaml` 같은 **별도 Q3 프로파일**을 만든다. Q2 실제 매출·순이익·희석주식수의 10-Q 확정 전에는 DEV 라벨을 유지한다.
2. `seed.quarter_label`은 `2026Q2`, `window.start_quarter`는 `2026Q3`로 둔다.
3. `op_margin`은 4분기 vector로 두고 **낮은 Q3 기준점 → 완만한 회복** 형태로 한다. 중앙 수준은 base 약 3.5%, bear 약 1.5%, bull 약 7%를 출발 범위로 쓰되, 각 분기 값은 Q3 프로파일 입력 검증 시 확정한다.
4. `backtest_methodology`는 현재 TSLA 블록을 그대로 복사해 forward 마진 변경과 디커플한다.
5. `engine/generic_forecast.py`, `schemas/generic.py`, `generic_cli.py`는 이 항목 때문에 변경하지 않는다.

### 8.4 나머지 백로그 재분류

- **P1-2 OI&E:** 승인, **유지 항목**. 코드/프로파일 변경 없음.
- **P2-3 surprise 방향:** 승인, **구현 필요**. `surprise_direction_accuracy` 수치 계약은 유지하고 표시 계층에 `HIT`/`MISS`/`NO-SURPRISE`와 model/actual surprise 부호·크기를 추가한다. 과거 aggregate와 단일 분기 판정을 혼합하지 않는다.
- **P2-4 EPS 입력 guard:** **이미 완료**. `engine/generic_postmortem.py`가 `net_income × unit_scale / diluted_shares`와 보고 EPS를 비교해 허용오차 초과 시 fail-closed하며 회귀 테스트도 존재한다. 신규 구현 대상에서 제거하고 허용오차 정책 검토만 별도 이슈로 둔다.
- **P3-5 데이터 위생:** 승인, **10-Q 의존 보류**. energy 배치량을 매출로 직접 등치하지 않고, services 성장 및 auto GM(크레딧 제외) 정의는 10-Q 기준으로 고정한다.

### 8.5 수용 검증

```powershell
python generic_cli.py --profile profiles/tsla_q3_2026.dev.generic.yaml --json
pytest -q
python scripts/verify_9q_sha.py
git diff -- engine/generic_forecast.py schemas/generic.py generic_cli.py
Get-FileHash -Algorithm SHA256 reports/tsla_q2_2026_forecast_FROZEN.md
```

필수 결과:

- Q3 프로파일의 base/bear/bull 4분기 `op_margin`이 의도한 완만 회복 경로와 일치.
- 현재 TSLA Q2 forward와 backtest 수치, FROZEN sha256 `10d1dca6…91ff` 불변.
- `engine/generic_forecast.py` 빈 diff 및 9Q host canonical 일치.
- 변경 전후 표에는 Q3~Q2의 시나리오별 매출·영업이익률·EPS를 기록. **Q2 FROZEN 수치를 after 값으로 재계산하지 않는다.**

---

## 9. Claude 독립 검증 of §8 (2026-07-28)

COMMON §5대로 Codex §8 주장을 신뢰하지 않고 재현. **판정: §8 6축 확정본·구현계약 SOUND — 승인.** (P1-1 조건부 승인·별도 Q3 DEV 프로파일·Q2 불변 원칙 정합. 기존 `gev_q3_2026.dev.generic.yaml` 패턴과 일치.)

**재현 결과:**
- **P2-4 EPS 입력 가드 = TRUE(구현 확인).** `engine/generic_postmortem.py`: `derived_eps = net×unit_scale/shares`, `tol = max(0.01, 2%·eps)`, 초과 시 `ValueError("...inconsistent with net_income / diluted_shares")` fail-closed. 회귀 테스트 `test_generic_postmortem.py::test_inconsistent_actual_eps_fails_before_attribution` **pass**. 불일치 입력(eps 0.42 vs net/shares 0.36) 실제 raise 재현. *(주의: 이 가드는 직전 검증 시점엔 부재 → §8의 "코드 변경 없음"과 경미 불일치, 기능은 정상.)*
- **FROZEN sha `10d1dca6…91ff` + NUL 0 = 확인.**
- **⚠️ pytest RED 발견(Codex 미실행분):** `test_tsla_postmortem.py::test_template_loads_but_cannot_score_before_release` **FAIL**. 근인 = 채점 워크플로가 `inputs/tsla_q2_2026_actual.yaml`를 실값으로 채워 커밋(Claude, 직전 턴)했는데, 이 테스트는 **같은 파일이 빈 템플릿**("missing required fields")이라 단언 → 상충. 증명: 템플릿 복원 시 pass. 디바이스 트리도 동일 RED(입력 파일 populated 확인).
  - **조치(Claude, 설계정합·코드 무변경):** 카노니컬 `inputs/tsla_q2_2026_actual.yaml` = **빈 템플릿 복원**(기본 fail-closed), 실입력은 **`inputs/tsla_q2_2026_actual.filled.yaml`**로 분리. 채점: `--actual inputs/tsla_q2_2026_actual.filled.yaml`. **pytest 7 pass 복구**, §4 스코어카드·FROZEN 불변. 두 파일 커밋.
  - **Codex 잔여(내구 강화 권장):** fail-closed 테스트를 **가변 작업파일에서 디커플** — in-code 빈 `GenericActualRelease` 또는 전용 `*.template.yaml` fixture 사용(작업파일 재오염 시 재발 방지). P2-3(surprise 표시) 구현과 함께 처리.

**남은 것:** Codex가 (1) P2-3 surprise 표시계층 HIT/MISS/NO-SURPRISE, (2) §9 테스트 디커플 강화, (3) Q3 seed 확보 후 `tsla_q3_2026.dev.generic.yaml` op_margin 벡터 확정. 각각 완료 시 Claude가 forward 회귀0·9Q sha·FROZEN 불변·pytest로 재현.


### 9.1 재검증 — Codex P2-3 + 테스트 디커플 완료 후 (Claude 독립 재현)

Codex가 §9 잔여 (1)P2-3 surprise 표시 (2)fail-closed 테스트 디커플을 완료 → 재현 검증 **GREEN(모든 주장 TRUE)**:
- **P2-3 surprise:** 실입력(.filled) 출력 = `IR GAAP EPS 컨센 surprise 방향: **MISS** (model +0.070 / actual -0.040, consensus 0.360)` — Codex 보고와 일치. 과거 호환 `surprise_direction_accuracy(+0.0%)` 병기 유지(단일분기 판정과 aggregate 미혼합, §8.4 계약대로). MISS 판정 정합: 가중 forecast $0.43가 컨센 $0.36 대비 beat 콜(+0.07)인데 actual $0.32는 miss(−0.04) → 부호 반대 = MISS.
- **테스트 디커플:** `test_template_loads_but_cannot_score_before_release`가 **in-code 빈 `GenericActualRelease`** 사용(작업 YAML 의존 제거) — §9 권장대로. 신규 surprise 파라미터라이즈 테스트(HIT/MISS/… 케이스) 포함.
- **재현 수치:** postmortem 관련 **18 tests pass**(tsla_postmortem·generic_postmortem·tsla_profile·backtest_methodology). 카노니컬 `inputs/tsla_q2_2026_actual.yaml` 여전히 기본 fail-closed(exit 1). **FROZEN sha `10d1dca6…` 불변 · `engine/generic_forecast.py` 빈 diff.** (전체 230 pass는 Codex 보고 수용 — 샌드박스는 서브셋만.)

**남은 것(1건):** Q3 10-Q seed 확보 후 `tsla_q3_2026.dev.generic.yaml` op_margin forward 벡터 확정 → Claude가 op_margin 경로·forward 회귀0·9Q sha·FROZEN 불변·pytest로 재현. **그 전까지 TSLA 트랙 안정(GREEN).**
