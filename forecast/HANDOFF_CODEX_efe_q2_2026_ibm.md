# HANDOFF (Codex) — EFE Q2 2026 IBM 프린트-전 동결

세션: 2026-07-22 (Cowork/Claude). 목적: IBM 2026 Q2 실적 **발표 전** EFE 예측 동결 + 신규 generic 프로파일 신설.
계약: COMMON `START-efe-q2-2026-00-COMMON.md` + 종목 `START-efe-q2-2026-ibm.md`. 6축 교차검증 요청.

---

## R. Codex 리뷰 반영 (2026-07-22, rev1)
Codex canonical 검증 완료 → 반영본. **커밋 전 이 절 먼저 확인.**
- **[정정] 데이터 오기 $1M 1건 수정**: WebFetch 요약이 FY2024 매출을 62,753으로 잘못 전사 → canonical 62,754. `2024Q4` 매출 17,553 → **17,554**, 테스트 `FY_REVENUE[2024]` 62753 → **62754**. 프로파일 sha256 `cc7921b3…67ee` → **`b727f85c5d36d6f0feb6f75abfff713225505885731d97a3e96dcf22016c72fb`**. 헤드라인 예측·백테스트 MAPE **불변**(seed 기반; 2024Q4는 백테스트만, 0.006%). FROZEN 문서에 ERRATUM 기재.
- **[정정] 커밋 범위 주장 수정**: "additive/무수정"은 **이 세션이 작성한 파일(아래 5개)에 한정**한 것이지, 저장소 워킹트리 전체가 clean이라는 뜻이 **아님**. 현재 HEAD는 `9d7200c`가 아니라 **`e66bee5`**이며 IBM 외 미커밋 변경이 다수 존재 → 커밋 시 **`git add -A` 금지**, 아래 명시 경로만 stage.
- **[수용] Codex 4개 권고**: (1) _slot는 별도 generic-backtest 워크스트림에서 8프로파일 회귀표와 처리(§4·§7-1). (2) operating EPS 브릿지는 회사별 비GAAP 정의 → 엔진 미탑재, 리포트 계층 유지(§7-2). (3) FY2026=Q2~Q4 집계 문제는 별도 annualization 수정, Q1 actual 수기 가산은 임시(§7-3). (4) IBM $1M만 우선 정정(본 rev1).
- **테스트**: `pytest tests/test_ibm_generic.py` **5 passed**(핸드오프 원문 "6/6"은 오기 — 실제 5개). Codex 전체 스위트 **222 passed**.

---

## 0. 한 줄 요약
신규 `profiles/ibm.generic.yaml`(EDGAR 무결성 actuals 13분기) + `tests/test_ibm_generic.py`(5/5) + `reports/ibm_q2_2026_forecast_FROZEN.md`((a)~(f)) 완료. **엔진 코드·메모리 경로 무수정**(순수 additive). 백테스트 공유버그 1건 **NOTICED BUT NOT TOUCHING**(아래 §4) — Codex 판단 요청.

## 1. 산출물 (미커밋 — 호스트 커밋 요청)
| 파일 | 상태 | sha256 |
|---|---|---|
| `profiles/ibm.generic.yaml` | 신규(rev1 정정) | `b727f85c5d36d6f0feb6f75abfff713225505885731d97a3e96dcf22016c72fb` |
| `tests/test_ibm_generic.py` | 신규(rev1 정정) | (커밋 시 산출) |
| `reports/ibm_q2_2026_forecast_FROZEN.md` | 신규(동결 증빙 + ERRATUM) | — |
| `reports/ibm_generic_forecast.md` | 신규(엔진 산출) | — |
| `HANDOFF_CODEX_efe_q2_2026_ibm.md` | 신규(본 문서) | — |

- **커밋은 아래 5개 경로만 명시 stage**(HEAD `e66bee5`; `git add -A` 금지 — IBM 외 미커밋 변경 다수):
  `git add profiles/ibm.generic.yaml tests/test_ibm_generic.py reports/ibm_q2_2026_forecast_FROZEN.md reports/ibm_generic_forecast.md HANDOFF_CODEX_efe_q2_2026_ibm.md`
- 리포 루트 `_to_delete/_efe_repo_stage.tgz` = 샌드박스 반입용 임시 tar(사용자 삭제 예정). 커밋 금지.

## 2. 데이터 provenance (독립 재현용 — Codex는 믿지 말고 재현할 것)
- 소스: EDGAR companyfacts, **CIK 0000051143**, `us-gaap:` `Revenues` / `NetIncomeLoss` / `WeightedAverageNumberOfDilutedSharesOutstanding` / `EarningsPerShareDiluted`(provenance).
- 수집 경로: 샌드박스 httpx는 `data.sec.gov` **403**(프로세스 프록시 차단), 브라우저 미연결 → **WebFetch 툴**로 companyconcept 슬라이스 수집(=[[sec-edgar-sandbox-access]] 패턴). whole-blob 정규 경로 미실행.
- **호스트 재생성(canonical, 자동검증 포함):**
  `python scripts/build_generic_actuals.py --cik 51143 --fye-month 12 --start 2023Q1 --end 2026Q1`
  → 이 스크립트의 FY 항등식·연속성·as-filed EPS 정합 검사로 아래 수기 블록을 **대조**할 것. 불일치 시 스크립트 출력이 정답.
- 무결성 규칙 적용: Q1–Q3 = 3M 직접(최earliest accession), **Q4 = FY(10-K) − 9M**(동일 회계연도 원본), Q4 희석주식수 = 4·FY_avg − 3·9M_avg. 무분할(split_history 빈값).

### 2.1 원자료 (USD millions / shares 절대수, as-filed)
| 분기 | 매출 | 순이익 | 희석주식수 | as-filed EPS | accession |
|---|--:|--:|--:|--:|---|
| 2023Q1 | 14252 | 927 | 917,845,279 | 1.01 | 0001558370-23-006656 |
| 2023Q2 | 15475 | 1583 | 919,452,496 | 1.72 | 0000051143-23-000021 |
| 2023Q3 | 14752 | 1704 | 923,673,300 | 1.84 | 0000051143-23-000032 |
| 2023Q4* | 17381 | 3288 | 927,324,236 | (FY 8.14) | 0000051143-24-000012 − 9M …32 |
| 2024Q1 | 14462 | 1605 | 933,431,312 | 1.72 | 0000051143-24-000025 |
| 2024Q2 | 15770 | 1834 | 934,397,595 | 1.96 | 0000051143-24-000039 |
| 2024Q3 | 14968 | −330 | 923,577,526 | −0.36 | 0000051143-24-000049 (연금 −$2.7B charge → 순손실) |
| 2024Q4* | 17554 | 2914 | 942,369,197 | (FY 6.43) | 0000051143-25-000015 − 9M …49 |
| 2025Q1 | 14541 | 1055 | 945,368,229 | 1.12 | 0000051143-25-000032 |
| 2025Q2 | 16977 | 2194 | 947,961,917 | 2.31 | 0000051143-25-000052 |
| 2025Q3 | 16331 | 1744 | 948,931,026 | 1.84 | 0000051143-25-000064 |
| 2025Q4* | 19686 | 5600 | 952,439,739 | (FY 11.17) | 0000051143-26-000010 − 9M …64 (FY NI에 이산 세금혜택) |
| 2026Q1 (seed) | 15917 | 1216 | 952,131,057 | 1.28 | 0000051143-26-000038 |

*Q4 = FY−9M 파생. 9M 희석주식수(FY2023/24/25): 920,323,692 / 935,425,233 / 947,420,391. FY 희석: 922,073,828 / 937,161,224 / 948,675,228.

### 2.2 검증 결과 (Codex canonical 대조 완료)
- **FY 합계 항등식(매출·순이익) FY2023/24/25 정확 일치.** ⚠️ 단, 수기 원본은 FY2024 매출을 62,753으로 전사(WebFetch 요약 오기) → **canonical 62,754로 정정**(2024Q4 17,554). 정정 후 항등식 정확 일치. FY2023/2025 매출·전 분기 순이익은 canonical과 일치.
- as-filed EPS ↔ NI/shares 정합: 전 분기 |Δ|≤max(0.03, 3%) green.

## 3. 예측 (FROZEN 헤드라인)
- 확률: bear 0.30 / base 0.50 / bull 0.20 (하방 비대칭).
- **Q2 2026 확률가중**: 매출 **$17,525M (+3.2% YoY)** · **GAAP EPS $2.35** · **operating(비GAAP) EPS ~$2.95**(브릿지 +$0.60).
- 컨센(프린트-전 ≈7/13): 매출 ~$17.85B, operating EPS ~$3.01 → **매출·EPS 모두 소폭 하회**(확신 중).
- 엔진은 **GAAP** 산출; operating은 리포트 단계 브릿지. project_scenario 벡터는 **positional(시드→Q2→Q3→Q4→Q1)**.

## 4. ★ NOTICED BUT NOT TOUCHING — `generic_cli.backtest_generic._slot` 계절 오정렬
- **증상**: IBM 엔진 내장 백테스트 매출 MAPE **25.9%**(EPS 165.9%). 이상.
- **근인**: `_slot(label)=min(int(label[-1])-1, n-1)` 은 성장벡터를 **캘린더-분기**(Q1→0…Q4→3)로 슬롯매칭. 그러나 `engine/generic_forecast.project_scenario`는 벡터를 **positional(시드부터 순차)** 로 소비. IBM은 **12월 결산 + window `start_quarter=2026Q2`(시드 2026Q1)** 라 두 해석이 **정확히 1분기 회전 불일치**. 계절성이 큰 IBM에서 발화. NVDA(완만·단조)에선 은폐돼 통과했음.
- **영향 범위**: **이 배치 5종 전부**(GOOGL·TSLA·IBM·GEV·TXN) 12월결산 + Q2 window → 계절 강한 종목(TXN 반도체·IBM)에서 동일 발화 예상. forward **예측치는 positional로 정확**(헤드라인 무영향); 왜곡은 **백테스트 지표에 한정**.
- **왜 안 고쳤나**: `backtest_generic`은 generic 공유코드. `_slot` 수정은 NVDA/TSLA/삼성 등 기존 프로파일 백테스트 수치를 바꿔 회귀 위험 → COMMON "surgical/회귀안전" 원칙상 본 세션 범위 밖. **Codex 결정 요청.**
- **교정 대안(검토용, 미적용)**: (a) `_slot`을 window.start_quarter 기준 **positional 오프셋**으로 재정의(캘린더가 아니라 "시드 다음부터의 스텝"), 또는 (b) 벡터를 캘린더-정렬로 두고 `project_scenario`도 캘린더 인덱싱으로 통일. 둘 다 기존 프로파일 회귀표 필요.
- **독립 교정 백테스트(캘린더-정합, 본 세션 수기 산출)**: 매출 MAPE **1.4%** (naive RW 13.0%) · EPS MAPE **62.2%** (RW 138.3%, |EPS|>0.10 필터로 2024Q3 손실분기 제외). → 정렬만 맞으면 매출 skill 뚜렷. EPS 절대오차 큼 = IBM **GAAP EPS 변동성**(손실분기·Q4 세금 이산) 구조적.

## 5. 검증 (독립 재현)
```
# 프로파일 로드 + forward + 백테스트(내장, 오정렬 수치 그대로 노출)
python generic_cli.py --profile profiles/ibm.generic.yaml
# 무결성 테스트 (연속성·FY항등식·EPS파생정합·백테스트 non-refuse)
python -m pytest tests/test_ibm_generic.py -q          # 5 passed
```
- 전체 스위트: 샌드박스 189 passed / 2 failed(라이브 네트워크 의존 `test_backtest.py::test_anchor_quarter_reproduces_actual_gross_margin`·`test_disclosure_loader.py::test_fetch_dart_mdna_nonempty` — httpx 403, 코드 무관·환경). **호스트 Codex 환경에서는 222 passed**(네트워크/DART 캐시 有).
- **9Q SK Hynix 불변식**: 메모리 경로 파일(`cli.py`·`engine/segment_revenue.py`·`margin_model.py`·`engine/backtest.py`·`schemas/models.py`·`profiles/sk_hynix.yaml`) **무수정** → sha256 `077ecb10…933c` 구성상 보존. 호스트에서 bit-identical 재확인 권장(샌드박스는 DART 캐시 없어 미실행).

## 6. Codex 6축 점검 요청
- **정확성**: §2.1 원자료를 canonical `build_generic_actuals.py`로 재생성해 대조(특히 Q4 파생·2024Q3 손실·2025Q4 세금혜택). base 시나리오 벡터의 계절 스텝 방향.
- **건전성**: op_margin=축약형 GAAP 순마진(비GAAP operating 아님) 라벨 일관성. operating 브릿지 +$0.60 근거(Q1'26 +0.63/Q2'25 +0.49).
- **회귀안전**: §4 `_slot` 수정 여부 결정. 수정 시 8개 기존 generic 프로파일 백테스트 before/after 회귀표 + 9Q sha256 확인.
- **범위규율**: additive만 했는지(diff = 신규 4파일). 메모리 경로 unil.
- **검증가능성**: 컨센 provenance(프린트-전 vintage·operating 기준) 명시됨. actuals accession 추적 가능.
- **유지보수성**: 라벨 계약(12월결산 identity), notes provenance.

## 7. 열린 질문 → Codex 결정 (rev1 반영, 종결)
1. `_slot` 계절 오정렬 → **별도 generic-backtest 워크스트림**에서 8프로파일 회귀표와 함께 처리(본 세션 미변경 확정). GEV/TXN 동결 전 결정하면 5종 일괄 적용 가능 — 권고 유지.
2. operating EPS 브릿지 → **엔진 미탑재, 리포트 계층 유지**(회사별 비GAAP 정의라 엔진 일반화 부적합).
3. FY2026=Q2~Q4 집계 → **별도 annualization 수정**으로 처리. Q1 actual 수기 가산은 **임시 조치로만** 유지.

## 8. 사후 채점 체크리스트 (발표 후)
1. actual(10-Q/IR): 매출·GAAP EPS·operating EPS·**세그먼트(특히 Infrastructure/IBM Z)**.
2. FROZEN↔actual: 매출·EPS MAPE·bias 부호; 세그먼트 오차.
3. 4-lever generic 귀인: 매출 / (reduced-form)마진 / OP→NI(below-OP 블록) / 주식수.
4. `engine/skill_metrics.py` MASE/Theil + operating EPS 컨센 surprise 방향 적중.
5. (f) 스윙 발화? z17 감속 / below-OP(연금·세금) / FX → YAML 앵커 수정 가능 편향인가, 구조적(리스크밴드)인가.
6. **7/14 정황 오염 주의**: 2차매체상 7/14 부정 사전신호(주가 급락) 관측됨. 예측 입력서 배제·프린트-전 컨센만 사용. 채점 라벨 = "정황 오염된 사후귀인 — 예측 신호 아님".

---

## 9. 사후 채점 (POST-PRINT, 2026-07-23 rev2) — Codex 토론용
발표 완료(7/22 장마감 정식; 실질 actual은 **7/14 IBM 공식 8-K 사전공시**로 기공개). 상세 채점표: `reports/ibm_q2_2026_scorecard.md`.

### 9.1 Actual (IBM 8-K/press, 2026-06-30; 10-Q/XBRL 미제출 — 값은 press 기준, EDGAR 확정 대기)
- 매출 **$17,109M**(세그 합; 헤드라인 $17.2B·+1% reported·~0% CC) · **GAAP EPS $2.27** · **operating EPS $2.93** · GAAP NI $2,166M · 희석 953.3M · Q2 FCF $2.54B(H1 $4.76B).
- 세그: Software **$7,761M(+5%)**[Red Hat +11 / Automation +4 / Data +19 / **TP −8**] · Consulting **$5,327M(flat/+1%cc)** · Infrastructure **$3,835M(−7%)**[**IBM Z −42** / Distributed +37] · Financing **$186M(+12%)**.
- 가이던스: FY26 CC 성장 **"4~5%"로 하향**(≥5%→); FCF +~$1B 재확인. FX ~중립.
- GAAP↔operating 브릿지 실제 **$0.66**(연금·workforce H1~$0.4B·취득무형).

### 9.2 채점 결과 (가중)
| 지표 | 가중 | actual | 오차 | 컨센 오차 | 판정 |
|---|--:|--:|--:|--:|---|
| 매출 | 17,524 | 17,109 | **+2.43%** | +4.33% | 컨센보다 정확·하회 방향 적중 |
| op EPS | 2.947 | 2.93 | **+0.58%** | +2.73% | 사실상 적중 |
| GAAP EPS | 2.356 | 2.27 | +3.79% | — | 소폭 과다 |
- surprise 방향 **2/2 적중**(컨센 대비 매출·op EPS 미스, 우리 사전 하회). 등록 스윙 **2/2 발화**(z17 / below-OP). 세그 Infra **+0.4% 적중**. **actual QoQ +7.49% = 우리 bear +7.5%** (base +10.5% 과다).

### 9.3 ★ 정황 오염 — clean skill 아님 (최우선 토론)
actual이 **동결 7일 전(7/14) IBM 공식 사전공시**로 공개됨 → blind ex-ante 실패. **단 우리 매출 +2.43% overshoot이 "미열람"의 물증**(열람 시 17.2/2.93 정확 적중했을 것). → 결론: **exclusion discipline은 지켜졌으나 IBM 건은 skill 점수로 카운트 불가**, "오염 환경 예측"으로 라벨. **잔여 4종(GOOGL/TSLA/GEV/TXN) 동결 전 8-K/사전공시 점검 게이트 필수**(§9.5-D).

### 9.4 개선점 제안 (Codex 판단 요청 — YAML앵커 vs 구조 vs 프로세스)
- **[P1·프로세스] ex-ante 무결성 게이트**: COMMON §2에 "동결 직전 EDGAR 8-K + IR 사전공시 스캔; pre-announcement 발견 시 해당 종목 **skill 채점 제외** 라벨" 추가. IBM이 정확히 이 케이스. **최우선.**
- **[P2·구조/리스크밴드] 메인프레임→부착SW 전이**: Infra(하드웨어)와 Software 내 **Transaction Processing**은 동일 사이클 구동인데 우리는 Infra만 스윙 등록. TP −8%가 Software 미스의 진원. generic은 세그 분해 없음 → 세그 오버레이 or 리스크밴드에 "메인프레임 사이클 β를 TP에 연동" 노트. 구조적, YAML 단독 불가.
- **[P3·YAML/확률] 다운사이클 계절 압축**: base Q1→Q2 +10.5%가 과다(실제=bear +7.5%). 순환주 피크 lap 국면에선 **base 계절 lift를 직전 regime로 하향 or bear 확률 상향**. 단 **1-print 과적합 경계** — 규칙화하려면 다분기 근거 필요. 잠정: IBM base growth[0] 재검토는 다음 refresh로.
- **[P4·브릿지 calib] operating 브릿지**: 0.60 vs 실제 0.66. 리포트 계층 유지(엔진 미탑재, Codex 기결정)하되 **trailing-4Q GAAP↔op 갭 평균**으로 앵커링 제안(현 수기 → 규칙).
- **[P5·데이터] 2026Q2 actuals 추가**: 10-Q/XBRL 제출 후 `build_generic_actuals.py --cik 51143 --fye-month 12 --start 2023Q1 --end 2026Q2` 로 append → 최초 **진짜 out-of-sample 백테스트 포인트** 확보. **press 8-K vintage로 미리 넣지 말 것**(vintage 혼합 금지, COMMON §1). GAAP NI 2,166 / 매출 17,109(세그합) / 희석 953.3M은 확정 대기.

### 9.5 6축 토론 앵커 (Codex 응답 요청)
- **정확성**: 세그 합 17,109 vs 헤드라인 $17.2B 차(~$40M elim/rounding) — 10-Q로 확정. op EPS는 비GAAP(XBRL 부재), press 기준.
- **건전성**: bear가 실현됐는데 base 0.50 가중이 적정했나? 순환 피크-lap 시 확률 재배분 룰?
- **회귀안전**: §4 `_slot` 워크스트림에 이번 2026Q2 포인트를 회귀표 검증셋으로 포함.
- **범위규율**: 사후 산출물은 `reports/ibm_q2_2026_scorecard.md`(신규) + 본 §9. 프로파일/엔진 미변경.
- **검증가능성**: actual provenance = IBM 8-K(7/14 사전 + 7/22 정식). 10-Q XBRL 확정 시 재대조.
- **유지보수성**: P1 게이트를 COMMON에 반영하면 5종 배치 전체 일관.

### 9.6 열린 결정 (Codex → 다음 종목 전 확정 요망)
1. P1 ex-ante 게이트를 COMMON에 넣고 IBM을 "채점 제외(오염)"로 공식화? (권고: 예)
2. P3 계절 압축 — 이번엔 **문서화만**, 룰 변경은 보류(과적합)? (권고: 예)
3. P5 2026Q2 append 시점 — 10-Q XBRL 대기 확정? (권고: 예)

---

## 10. 개선점 정량 검증 + Codex 평가 요청 (rev3, 2026-07-24)
어닝콜 반영 완료. §9 개선점을 **데이터로 검증**했고, 채점의 핵심 함정 1건을 추가 발견함.

### 10.1 ★ 핵심 발견 — op EPS "적중"은 부분적 error-cancellation (과신 금지)
가중 op EPS 2.947 vs actual 2.93(+0.58%)의 우수함은 **두 반대부호 오차의 상쇄**다:
- GAAP EPS 오차 **+0.086**(과다; 매출/Software overshoot·마진 기인)
- 브릿지 오차 **−0.069**(과소; 0.591 vs 실제 0.660)
- 순 op 오차 **+0.017** — 즉 **~5.1x 크기의 오차가 상쇄**되어 op가 우연히 맞음.
→ **결론**: op EPS 정확도를 skill로 과대평가하지 말 것. 실제 신호는 (a) 매출 방향(하회) 적중, (b) 등록 스윙 발화이고, op 포인트 정확도는 상쇄 운이 섞임. **Codex 평가 시 이 상쇄를 명시적으로 감점/주석 처리 요청.**

### 10.2 P3(계절 압축) 검증 — 정량 근거 확보
Q1→Q2 QoQ: 2023 +8.58 / 2024 +9.04 / **2025 +16.75(z17 런치 UP-spike)** / 2026 actual +7.49.
- 우리 base +10.5%는 2025 spike를 포함해 상향된 값. **ex-spike norm(23·24 평균)= +8.81%.**
- 반사실: base 성장을 +8.81%로 두면 매출 오차 **+2.80% → +1.23%**로 축소. 잔여 **−1.2%가 진짜 메인프레임 서프라이즈**(air-pocket).
- **제안(과적합 회피형)**: "순환 피크 분기(z17 런치 같은)를 계절 base-rate에서 **1회성으로 제외**" — 1-print 튜닝이 아니라 **regime 이상치 배제** 원칙. Codex 판단 요청.

### 10.3 P2(메인프레임→부착SW 전이) 검증 — 기계론, 통계 아님
IBM Z YoY **+51%(26Q1) → −42%(26Q2)** 와 Transaction Processing **+2%cc → −8%** 가 **동일 분기 동반 반전**. z17 사이클이 HW(Infra)와 부착SW(TP)를 동시 구동하는 기계론 확인(관측 2분기 → 통계량 아님, disclose). 우리는 (f)에서 Infra만 #1 스윙 등록 → **TP를 같은 β에 묶는 세그 노트 필요**(구조/리스크밴드; generic 세그 분해 없음).

### 10.4 P4(브릿지) 검증 — 방향 맞으나 2차
분기 GAAP→op 갭: 0.48(25Q1)/0.49(25Q2)/**0.63(26Q1)**/0.66(26Q2). 취득무형(Confluent/HashiCorp) 램프로 **상승 추세**. 동결시 최신치 0.63을 썼다면 0.60보다 근접. **단 10.1의 상쇄 때문에 브릿지만 올리면 op 오차가 되레 커짐** → **매출(P2/P3) 교정이 본질, 브릿지는 종속**. 제안: 브릿지 = trailing-1Q 실측 갭(현 수기 상수 → 규칙), 리포트 계층 유지.

### 10.5 개선 우선순위 (검증 후 확정)
| # | 개선 | 성격 | 검증 | 권고 |
|---|---|---|---|---|
| P1 | 동결 전 8-K/사전공시 게이트 | 프로세스 | IBM 케이스로 자명 | **즉시 COMMON 반영** |
| P3 | 순환 피크 분기 계절 base-rate 배제 | YAML/룰 | 오차 2.8→1.2% | 원칙 채택(1-print 튜닝 아님) |
| P2 | 메인프레임 β를 TP에 연동 | 구조/밴드 | 2분기 동행(기계론) | 세그 오버레이 시 반영 |
| P4 | 브릿지=trailing-1Q 실측 | 리포트 룰 | 추세 상승 확인 | 규칙화, 단 2차 |
| — | op 정확도 상쇄 주석 | 채점규율 | +0.086/−0.069 | **평가에 명시** |

### 10.6 Codex 6축 평가 요청 (이 핸드오프 대상)
- **정확성**: 10.1 상쇄 분해·10.2 반사실 재현 확인. 세그합 17,109 vs 헤드라인 17.2B는 10-Q로 확정.
- **건전성**: bear 실현인데 base 0.50 가중 적정성 + op 상쇄 리스크를 채점에 반영했는가.
- **회귀안전**: P2/P3/P4는 IBM 리포트/문서 계층 한정, 엔진·메모리·`_slot` 미변경(별도 워크스트림). 회귀 0.
- **범위규율**: 사후 산출 = `reports/ibm_q2_2026_scorecard.md` + 본 §9·§10. 프로파일 불변(sha b727f85c).
- **검증가능성**: 개선점 4건 전부 수치 반사실/기계론 제시. actual provenance = IBM 8-K(7/14+7/22), 10-Q XBRL 대기.
- **유지보수성**: P1을 COMMON에 넣으면 잔여 4종 일관. P3는 "regime 이상치 배제" 문구로 COMMON §1 계절 가이드에 추가 제안.

### 10.7 Codex 확정 요청 (최종)
1. IBM = **"오염(채점제외)" 공식 라벨** + op EPS 정확도 상쇄 주석 승인?
2. P3를 **"순환 피크 분기 배제" 원칙**으로 COMMON에 문서화(룰 아님)?
3. P1 게이트 문안을 Codex가 COMMON §2에 반영(호스트 커밋)?
4. 잔여 4종(GOOGL/TSLA/GEV/TXN) 동결 전 사전공시 스캔 + `_slot` 캘린더-정합 처리 동시 적용?
