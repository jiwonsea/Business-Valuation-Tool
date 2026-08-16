# HANDOFF → Codex — EFE 2026-08 배치 / **VST (Vistra Corp.) 2026 Q2**

상태: **프린트 전 동결 완료 · 발표 대기** (§4는 2026-08-07 발표 후 append)

---

## §1 컨텍스트

| | |
|---|---|
| 종목 / 분기 | Vistra Corp. (VST) · CIK 0001692819 · 12월 결산 · **2026 Q2** |
| 발표 | 2026-08-07 (금) 개장 전 릴리스 예상 **20:00 KST**(직전 3분기 모두 07:00 ET 배포) + 콜 10:00 a.m. ET |
| 동결 시각 | **2026-08-05 00:52:12 KST / 2026-08-04T15:52:12Z** (데드라인 8/7 19:00 KST 대비 −66h) |
| git HEAD | `3190cd64f2bd25c80bf0a2ea2e91f7d17cb7e5fb` |
| 프로파일 sha256 | `e5ab8b21c3612b7d6d11bede7b56f7b2d297ee54f5795fe9906ef92a1fd80a6b` (`profiles/vst.generic.yaml`) |
| 테스트 sha256 | `69939ea903b188b445727c300cb48ef649a4d8f69f61f1daf1f752911a153a63` (`tests/test_vst_profile.py`) |
| FROZEN | `reports/vst_q2_2026_forecast_FROZEN.md` |
| 회귀 | `pytest -q` **241 passed, 1 deselected** · 9Q sha `077ecb10…933c` **MATCH**(sandbox, CPython 3.11.15) |
| 변경 파일 | 신규 3개(profile / test / FROZEN) + 생성물 `reports/vst_generic_forecast.{md,json}`. **기존 파일 무수정.** |

**NOTICED BUT NOT TOUCHING:** `schemas/generic.py`는 `extra="forbid"`라 제안 플래그 `gaap_op_is_noisy` / `scored_target`을 YAML에 넣을 수 없다. 스키마 미변경, 제안만 §6에 상정.

---

## §2 데이터 무결성 로그

- **출처**: EDGAR companyfacts **companyconcept 슬라이스**(Revenues / OperatingIncomeLoss / EarningsPerShareDiluted / WeightedAverageNumberOfDilutedSharesOutstanding / NetIncomeLossAvailableToCommonStockholdersDiluted), CIK 1692819. **WebFetch 도구로만 접근**(샌드박스 프로세스는 `data.sec.gov` 403). 보조: IR 보도자료 8종(adj EBITDA·세그먼트·가이던스·헤지 커버리지는 XBRL에 없음).
- **분기 수**: **13** (2023Q1~2026Q1, 연속). `backtest_generic` 최소 13분기 요건 충족 → N=12 백테스트 성립.
- **Q4 복원**: 동일 회계연도 10-K 연간 − Q3 10-Q 9M (accession 혼합 없음).
- **FY 합 tie-out**: 매출 2024 ✓ / 2025 ✓ / 2023 −$1M(반올림). 영업이익 2024 ✓ / 2025 ✓ / **2023 +$3M**(2023Q3 as-filed 분기 834 ↔ 9M−6M 파생 837; **미해소, 기록만**). NI-to-common 2023·2024·2025 전부 ✓.
- **EPS 항등식**: 파생 EPS(`net_profit ÷ as-filed 희석주식수`) ↔ as-filed EPS 6개 분기 전부 ±0.01 이내.
- **net_profit CONTRACT**: 보통주 귀속 순이익(우선주배당·비지배지분 차감 후). 따라서 forward `net_interest_pct_of_revenue`가 이자비용 + 기타손익 + **우선주배당**을 함께 흡수한다. TXN 라운드에서 확정된 `eps_numerator_basis` 논의(IAC)와 같은 계열의 문제 — VST는 우선주가 있어 **처음부터 IAC 기준으로 적재**했다.
- **§7 원문 인용 계약**: 7항 중 **1(부분: SHA-256 없음)·3·5·6 충족, 2·4(부분)·7 미충족**. → **"바이트 보존 미완 — 호스트 필요"**. 호스트가 `reports/.cache/src/` 원본 + SHA-256 + sidecar로 완결할 것.
- **알려진 결함 3건**(FROZEN 말미 동일): ① 2023Q1~Q3 `net_profit`은 EPS×주식수 역산(항등식 자명, 독립검증 아님) ② Q4 주식수 `4×FY−3×mean(Q1..Q3)` 공식이 손실분기 반희석 탓에 2024Q4·2025Q4 과대 ③ 2024년 분기 adj EBITDA는 Sunset 세그먼트 폐지로 basis 노이즈 ±$300M → **계절 형태는 2025년을 1순위 채택**.

---

## §3 FROZEN 요약 (a)~(f) + 밴드폭/base

| 항목 | bear | **base** | bull | 밴드폭÷base |
|---|---:|---:|---:|---:|
| **★ Ongoing adj EBITDA ($M)** | 1,480 | **1,680** | 1,950 | **27.98%** |
| 매출 GAAP ($M) | 4,230 | **4,800** | 5,527 | **27.02%** |
| GAAP 희석 EPS `LOW_CONFIDENCE` | 0.42 | **1.75** | 3.50 | **176%** → **"예측 불가"를 결론으로 채택**(DELTA §2.3) |
| 컨센기준 non-GAAP EPS | 1.12 | **1.75** | 2.55 | 81.7% |

- **(b)** 세그먼트 base: Retail 780 / Texas 260 / East 600 / West 60 / Corp −20. **채점은 Retail+Texas 합산($1,040M)** — 분기별 사내 헤지 배분 때문에 개별 세그는 신호가 아님. East(+43.5% YoY)가 최대 드라이버.
- **(c)** FY26 adj EBITDA 가이던스 **재확인 60%** / 상향·상단좁힘 30% / 하향 10%. 근거: Q1 콜에서 "Cogentrix 제외, 클로징 후 갱신" 명시 + 최근 2년 모두 **Q3에** 갱신. 신규 데이터센터 PPA 발표 35%.
- **(d)** **`MISS` 사전등록(컨센 하회)**. 컨센 non-GAAP EPS $2.43 vs 우리 $1.75(**−28.0%**). 컨센 역산 adj EBITDA **$1,965M** vs 우리 $1,680M(**−14.5%**). 3대 논거: ① 2026년 발전량 **96% 헤지** → 여름 상방의 P&L 전달 경로가 4% ② 컨센 함의 Q2 비중 **27.3%**는 2024(25.0%)·2025(22.8%) 어디에도 없음 ③ 회사가 Q1에 올리지 않고 재확인.
- **(e)** Q&A: PJM collar / 원전 PPA 파이프라인 / 헤지 커버리지·연도별 락인가격 / Cogentrix 클로징·자금조달 / 자사주 여력 / 신규 캐파 / 리테일 마진.
- **(f)** 스윙팩터: **①T1 미실현 MTM(±$1.4~1.5 EPS)** ②T3 PJM 규제(주가) ③T5 자사주(EPS 전용 레버) ④여름 날씨(96% 헤지가 차단한다는 가정 자체가 최대 단일 가정) ⑤세율(15.1~26%) ⑥T4 신규 PPA(주가 촉매).

### ★ R5 브릿지 (기준 혼용 방지 — 채점 시 필수)

```
컨센기준 EPS ≈ [ (Ongoing adj EBITDA − F) × (1 − t) − 우선주배당 ] ÷ 희석주식수
F = D&A + 이자비용 − 기타수익
캘리브레이션 2점: 2025Q2 → F = 858 ;  FY2025 → F/4 = 856   (일치 $2M 이내)
2026Q2 적용: F = 890, t = 0.19, 우선주 49, 주식수 338.0M
```
**컨센서스 $2.43은 GAAP이 아니다** — 전년 동기 비교치 $1.01 vs as-filed GAAP **$0.81**이 증거.

---

## §4 [발표 후 append — 2026-08-07]

*(미기입. actual 확보 후: 4-lever generic 귀인 잔차 0 · MASE/Theil · surprise HIT/MISS/NO_SURPRISE · 밴드 커버리지 · **실제 미실현 MTM 금액으로 §T1 재판정**.)*

---

## §5 개선 제안 (P0~P3)

| # | 제안 | 분류 |
|---|---|---|
| **P0** | **앵커 계열 통계 게이트**: `backtest_methodology` 로드 시 앵커 후보 계열의 `stdev/mean`(CV)과 부호반전 여부를 계산해, 임계치 초과 시 **실패 또는 강제 라벨**. VST GAAP OP 마진 CV 0.70·부호반전 1회 vs adj EBITDA 마진 CV 0.23. → **YAML 한 줄 앵커 수정으로 고칠 체계적 편향이 아니라, 규칙 자체의 적용 조건 결함.** 엔진/스키마 변경 필요. | 구조 |
| **P1** | `schemas/generic.py`에 `scored_target: gaap_eps \| adjusted_ebitda`(기본 `gaap_eps`, 하위호환) 추가. 현재는 "채점 대상은 adj EBITDA"가 리포트 산문에만 존재해 **기계 검증이 불가능**하다. | 검증가능성 |
| **P2** | `net_interest_pct_of_revenue`가 이자+기타+**우선주배당**을 뭉뚱그려 흡수한다. TXN 라운드의 `eps_numerator_basis` 설계와 합쳐 **우선주 보유 이슈어(VST) 전용 분리 필드**로 정리. | 유지보수성 |
| **P2** | 2023Q1~Q3 `net_profit` 역산 → 호스트 whole-blob에서 NI-to-common 직접 태그로 교체(독립 검증 복원). Q4 주식수 공식의 반희석 왜곡도 동시 처리. | 데이터 무결성 |
| **P3** | **MTM은 리스크밴드行(구조적)** — 앵커로 고칠 수 없음. base 0 + 광폭 밴드가 정답이며, 사후에 밴드 커버리지만 캘리브레이션한다(DELTA §R2 유지). | 리스크밴드 |

---

## §6 Codex 6축 질의

> **주질의.** GEV에서 확정한 **"op_margin = 연결 GAAP OP 마진 앵커"(DELTA §R1)** 규칙은 파생 MTM이 GAAP 손익을 지배하는 머천트 IPP에서 **무효인가?** 무효라면 적용 조건을 어떻게 명문화하는가 —
> **(가)** 이슈어 유형 플래그(`gaap_op_is_noisy: true`) / **(나)** 규칙을 "현금기준 영업이익 앵커"로 일반화 / **(다)** **계열 통계 게이트**(앵커 후보 계열의 CV·부호반전을 로드 시 검증)?
> 이 세션은 **(다)**를 지지한다: GEV에서 GAAP이 옳았던 이유는 "GAAP이라서"가 아니라 그 계열이 `CV < 임계치`를 만족했기 때문이고, VST에서 틀린 이유도 같은 조건 위반이기 때문이다(0.70 vs 0.23). **(나)로 간다면 기존 5종(GOOGL·TSLA·IBM·GEV·TXN) forward 출력 불변을 회귀표(프로파일별 4분기 EPS + FY 가중, before/after)로 증명할 것을 요구한다.**
>
> 1. **정확성** — forward 손계산(`4,800.2 × 0.217 − 0.065×4,800.2 = 729.6 → ×0.81 = 591.0 → ÷338.0M = 1.748`)·FY합 항등식·파생EPS 대조가 원문 수치로 성립하는가? **2023Q3 영업이익 +$3M 불일치(as-filed 834 ↔ 9M−6M 837)를 미해소로 남긴 판단이 옳은가?**
> 2. **건전성** — 앵커 근거(2025년 Q2 비중 22.8%, 브릿지 F=890, 세율 19%, 헤지 96%)가 표본기간과 함께 명시됐는가? 발표 후 정보가 새어들지 않았는가? **"2024년(+$856M 대형 비트)이 아니라 2025년을 유사사례로 채택"한 것이 이 예측의 단일 최대 가정인데, 이 선택이 방어 가능한가?**
> 3. **회귀안전** — 9Q sha256 bit-identical(`077ecb10…933c` sandbox / `b979d79f…f6e7` host)인가? 기존 5종 forward 불변인가?
> 4. **범위규율** — 신규 3파일 외 변경이 없는가? `schemas/generic.py`를 건드리지 않고 `NOTICED BUT NOT TOUCHING`으로만 남긴 것이 적절한가?
> 5. **검증가능성** — `test_T1_gaap_op_margin_is_not_anchorable`(CV>0.5 · 부호반전 · 40pp 스프레드)과 `test_backtest_...records_the_eps_failure`(EPS MAPE>50% 이면서 naive RW 미만)가 T1 판정을 **실패하는 테스트**로 표현한 것이 적절한가? 임계치(0.5 / 50%)가 자의적이지 않은가?
> 6. **유지보수성** — 종목 고유 하드코딩이 generic 경로에 침투했는가? (주장: 없음 — 전부 프로파일 YAML + 전용 테스트)

---

## §7 Codex 6축 검토 — 2026-08-05 발표 전

### 총평

**조건부 통과.** FROZEN의 핵심 채점값과 `MISS` 사전등록을 뒤집을 결함은 발견하지 못했다. 다만 최신 공식 Q1 2026 릴리스가 2026년 헤지 커버리지를 약 **98%**로 제시했는데 본문은 Q3 2025의 구버전 **96%**를 사용한 데이터 오류 1건이 있었다. 규칙 (i)에 따라 FROZEN 본문은 유지하고 append 정정 및 `profiles/vst_v2.generic.yaml`을 `e4a35a7`에 분리했다. 원본 sha256은 `e5ab8b21c3612b7d6d11bede7b56f7b2d297ee54f5795fe9906ef92a1fd80a6b`, v2는 `a37ccfb7e6581d3c8e5be7838b7f82cf50386876ba08b1793a7a3110c2b8d872`이며 forward 출력은 동일하다.

### 주질의 — 계열 통계 게이트

**(다)를 채택하되, `CV > 0.5` 단독 hard-fail은 기각한다.** 종목 유형 플래그 (가)는 사람이 새 이슈어를 사전에 정확히 분류해야 하고 동일 이슈어 안의 계열별 차이도 놓치므로 불필요한 수동 지식이 된다. 관측 불가능한 “현금기준 OP”를 만드는 (나)는 조정 웨지를 모델 오차로 되돌린다. 데이터에서 후보 계열의 앵커 가능성을 검사하는 (다)가 가장 재사용 가능하다.

다만 “GEV에서 GAAP이 옳았던 이유가 낮은 CV 하나 때문”이라는 강한 명제는 현재 증거로는 **미입증**이다. GEV 한 사례와 VST 한 반례는 방향을 제시할 뿐 임계치를 식별하지 못한다. CV는 평균이 0에 가까울 때 폭주하고, 구조적 추세·계절성·일회성 outlier·부호 반전의 경제적 원인을 구분하지 못한다. 따라서 규칙은 다음처럼 명문화하는 것이 적절하다.

1. 최소 8~12분기의 동일 basis 계열을 요구한다.
2. `abs(mean)`이 작은 계열에는 CV 판정을 금지하고 별도 scale-normalized dispersion을 쓴다.
3. CV, 부호 반전, peak-to-trough, outlier 집중도, basis 변경을 **경보 묶음**으로 기록한다.
4. 경보가 발생하면 자동 실패가 아니라 `ANCHOR_REVIEW_REQUIRED`로 강등하고, 계절 naive 대비 out-of-sample MASE/Theil 및 절대오차로 후보 계열을 비교한다.
5. 임계치는 기존 이슈어 전체의 walk-forward 결과로 보정하며 프로파일별 예외 플래그는 최후 수단으로만 둔다.

따라서 `CV 0.5`는 현재 VST의 위험을 포착하는 **사전등록 경보값**으로는 유효하지만 보편적 경계로는 자의적이다. `EPS MAPE 50%`도 마찬가지로 `LOW_SKILL` 라벨의 운영 기준일 뿐 앵커 원인 판정값이 아니다. 특히 EPS가 0에 가까운 분기에는 MAPE가 불안정하므로 MAE/MASE/Theil과 함께 보아야 한다.

### 1. 정확성 — 통과(기록 결함 유지)

- forward 손계산은 engine과 일치한다: base EPS 약 `$1.748`.
- FY 매출·NI 합과 as-filed EPS 대조는 명시된 허용오차 내 성립한다.
- 2023Q3 OP `$834M`과 누적 차감 `$837M`의 `$3M` 차이는 임의로 한쪽을 덮어쓰지 않고 accession·산식과 함께 미해소로 남기는 편이 옳다. 분기 as-filed 값과 누적 보고값이 충돌하는 상황에서 조정 근거가 없기 때문이다.
- 최신 헤지 커버리지 오류 1건은 위 append/v2로 정정했다. 전망 숫자에는 영향이 없다.

### 2. 건전성 — 조건부 통과

2025년을 2024년보다 우선한 선택은 **방어 가능하지만 결정적이지는 않다.** 2024년은 Energy Harbor 편입과 연말 nuclear PTC 인식이 섞인 구조 변화 연도이고, 회사도 FY2024 초과분 `$856M`의 주요 원인으로 이를 들었다. 2025년은 완전한 연간 perimeter에 더 가깝고 원 가이던스 중간값 대비 `$112M` 초과에 그쳐 계절 shape 기준으로 더 깨끗하다. 최신 2026Q1 기준 2026년 발전량 약 98% 헤지는 2025 유사사례 선택을 추가로 지지한다.

그러나 “미헤지 2%만이 상방 전달 경로”라는 표현은 너무 강하다. realized hedge price, basis/shape, 용량가격, 가동률, 리테일 마진, Lotus 3개월 편입도 adj EBITDA를 움직인다. 또 2026년은 PJM 용량가격 스텝업과 Lotus 때문에 2025년의 단순 반복도 아니다. 따라서 2025 shape 채택은 합리적 base 가정이고 `MISS`는 유지할 수 있지만, 독립적으로 MISS를 증명하지는 않는다. 이 부분은 방법론 이견으로 동결 유지하고 사후 채점한다.

앵커의 표본은 대부분 명시돼 있다(2025 Q2 share 22.8%, F calibration 2025Q2/FY2025, 세율 2025Q2·2026Q1). 발표 후 정보 유입 흔적은 발견하지 못했다.

### 3. 회귀안전 — 통과

- `python scripts/verify_9q_sha.py`: 호스트 정규 sha256 `b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7` MATCH.
- `python -m pytest -q`: **281 passed, 1 deselected** (Python 3.14.3, Pydantic 2.12.5).
- `b4287cd^..HEAD`에서 generic engine/schema와 기존 5종 프로파일은 diff 0이다. 따라서 GOOGL·TSLA·IBM·GEV·TXN forward는 코드·입력 바이트 불변으로 동일하다. 현재 4Q/FY 확률가중 EPS도 별도 추출해 재현했다.

### 4. 범위규율 — 통과

VST 동결 커밋 `b4287cd`는 profile/test/FROZEN/generic report 4파일뿐이며 generic engine/schema 변경은 없다. 데이터 정정 커밋 `e4a35a7`도 append와 v2 프로파일만 포함한다. 다른 세션 산출물은 건드리지 않았다.

### 5. 검증가능성 — 조건부 통과

두 테스트는 “현재 데이터와 판정의 연결을 보존하는 characterization test”로 적절하다. 다만 이름과 주석이 암시하듯 보편 규칙을 검증하는 테스트는 아니다. `CV > 0.5`, 40pp, `EPS MAPE > 50%`를 곧바로 production hard-fail 기준으로 승격하면 자의적이다. 향후 P0 구현 시 여러 이슈어의 walk-forward 분포에서 threshold를 보정하고 경계값 민감도 표를 남겨야 한다.

### 6. 유지보수성 — 통과

VST 고유 수치와 논리는 프로파일 및 전용 테스트에만 있고 generic 경로 침투는 없다. 이번 검토에서는 코드/테스트 결함을 발견하지 못했으므로 규칙 (iii)에 따른 코드 수정 커밋은 없다.

---

_작성: Claude (Cowork, claude-opus-5) · 2026-08-05 00:52 KST · git commit은 호스트/Codex 전담._

## §8 원문 보존 결과 — 2026-08-05

SEC companyconcept 5종과 10-Q/10-K 4건을 `reports/.cache/src/`에 원문 바이트 + `.meta.json` sidecar로 보존했다. sidecar의 크기와 SHA-256을 재계산해 9건 모두 일치했다. 상세 파일명·크기·해시는 FROZEN의 `VST_Q2_2026_SOURCE_PRESERVATION` append에 기록했다.

JSON과 SEC inline XBRL HTML은 고정 물리 페이지가 없어 page count를 `null`로 기록했다. 인앱 브라우저가 제공되지 않아 filing 표 시각 확인은 수행하지 못했고 sidecar에 명시했다. 따라서 원문 바이트·출처·해시 감사 사슬은 완결됐지만, §7 항목 7의 시각 확인은 여전히 미완이다.
