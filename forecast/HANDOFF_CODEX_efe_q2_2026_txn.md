# HANDOFF → Codex — EFE Q2 2026 TXN 프린트-전 동결 (빌드 핸드오프)

세션: 2026-07-22 (Cowork sandbox). 작성자: Claude. base HEAD `9d7200ca62af5b421cfc8db985ffa09e85fadbb1` (main).
목적: TXN 2026 Q2 실적 **프린트 전** EFE 예측 동결 + 신규 프로파일/무결성 actuals/테스트 구축. 이 문서는 **Claude→Codex 빌드 핸드오프**(6축 리뷰 + git 커밋 + 호스트 EDGAR 재수집용). 채점(사후 귀인)은 발표 후 별도.

> **계약 리마인더(COMMON §5):** Codex는 "diff 0 / pytest 통과 / NUL clean"을 **그대로 믿지 말고 독립 재현**하라. 아래 수치·검증은 전부 샌드박스(CPython 3.11.15/linux) 기준. git(add/commit/stage)은 **호스트/Codex 전담**(사용자 git 미사용).

---

## 1. 산출물 (전부 디스크 기록 완료, 미커밋)

| 파일 | 상태 | 요지 |
|---|---|---|
| `profiles/txn.generic.yaml` | **NEW** | 125행. sha256 `b1123dba7ab13903580ae659b4577c1a905c09b3ed5f7e4dc6f9c1b9f7b37a72`. FYE 12월, split 없음. actuals 21분기 2021Q1..2026Q1. regime_break 2025Q1. |
| `reports/.cache/edgar_companyfacts_CIK0000097476.json` | **NEW (파생 캐시)** | sha256 `4edb96fc9473c825d5472ec7fbf1808975318ff1a7858d2389b5b76c42c58f04`. web_fetch companyconcept 전사, **as-filed 원본 accession only**. `_derived_note` 내장. **호스트에서 풀블롭으로 대체 요망(§5).** |
| `tests/test_txn_profile.py` | **NEW** | 104행, 7 테스트(헤더계약·21분기연속성·EPS파생정합·FY합항등식·캐시존재·regime윈도·forward Q2앵커). |
| `reports/txn_q2_2026_forecast_FROZEN.md` | **NEW (deliverable)** | 127행. (a)~(f) + GM 분해 + Q3 가이던스 예측 + ex-ante 무결성. 동결 2026-07-22T06:30:36Z / 15:30 KST. |
| `reports/txn_generic_forecast.md` | NEW (생성물) | `generic_cli.py` MD 출력. |
| `reports/txn_generic_forecast.json` | NEW (생성물) | `--json` 출력(signal 블록 포함). |

**Scope: 순수 additive.** generic 경로만. `cli.py`·`engine/backtest.py`·`engine/segment_revenue.py`·`margin_model.py`·`schemas/models.py`·9Q 불변식 **일절 미변경**. `generic_cli.py`·`schemas/generic.py`·`engine/generic_forecast.py`·`scripts/build_generic_actuals.py` **코드 미변경**(신규 프로파일이 소비만).

### 제안 git 커밋 (호스트)
```
git add profiles/txn.generic.yaml tests/test_txn_profile.py \
        reports/txn_q2_2026_forecast_FROZEN.md \
        reports/txn_generic_forecast.md reports/txn_generic_forecast.json \
        reports/.cache/edgar_companyfacts_CIK0000097476.json \
        HANDOFF_CODEX_efe_q2_2026_txn.md
# 파생 캐시는 .gitignore 여부 확인 — reports/.cache가 무시되면 캐시는 커밋 제외(정상),
# 단 CI/오프라인 재현을 위해 커밋할지는 IBM/NVDA 선례에 맞춰 결정.
```
정리: 샌드박스가 리포 루트에 만든 tarball은 `_to_delete/`(`_efe_export.tar.gz`, `_efe_cache.tar.gz`)로 이동해 둠 — 삭제 요망. (기존 `_cowork_src.tar.gz`도 동 폴더에 있었음.)

---

## 2. 데이터 provenance & 무결성 (독립 재현 필수)

**출처:** SEC EDGAR companyconcept (CIK 0000097476), as-filed 원본 accession. 샌드박스 프록시가 `data.sec.gov`를 **프로세스에 403**(httpx 확인) → `web_fetch` 툴로 5개 개념 전사: `RevenueFromContractWithCustomerExcludingAssessedTax`, `NetIncomeLoss`, `WeightedAverageNumberOfDilutedSharesOutstanding`, `CostOfGoodsAndServicesSold`(GM 분석용, 프로파일 미포함), `EarningsPerShareDiluted`(provenance). → 파생 캐시 블롭(companyfacts 형태)으로 저장 → `build_standalone_quarters` + `verify()`로 조립·검증.

**빌드/검증 명령 (Codex 독립 재현):**
```
python scripts/build_generic_actuals.py --cik 97476 --fye-month 12 --start 2021Q1 --end 2026Q1
# 기대: "# VERIFIED: 21 contiguous quarters 2021Q1..2026Q1; FY sum identity + as-filed EPS coherence green"
# 출력 actuals 블록이 profiles/txn.generic.yaml의 actuals와 bit-identical해야 함.
```
**검증 통과 항목(빌드 시):** (1) 라벨 연속성 2021Q1..2026Q1, (2) FY합 항등식 — 4분기 매출/NI 합 = 10-K FY(2021~2025 전부 정확 일치), (3) as-filed EPS 정합성(|NI/shares − EPS| ≤ tol). Q4 = 10-K 연간 − 동일 FY 9M 10-Q(원본 filing, vintage 미혼합). 분할 없음 → split_history 빈값.

**⚠ 전사 gotcha (Codex 확인·타 종목 재사용):** web_fetch가 **Revenue 개념의 YTD facts start 날짜를 end로 붕괴**(`end|end`)시켜 전사함. 캘린더 구조(Q1/6M/9M/FY start = Jan 1)로 **결정적 재구성** + FY합 항등식이 최종 가드로 오류 포착(값 오류 시 verify FAIL). NI/shares/EPS 전사는 clean. → **파생 캐시의 개별 값은 호스트 풀블롭과 대조 권장.**

### 호스트 EDGAR 풀블롭 재수집 (COMMON §2/§4, 파생 캐시 대체)
```
rm reports/.cache/edgar_companyfacts_CIK0000097476.json   # 파생 캐시 삭제
# .env에 SEC_EDGAR_USER_AGENT 설정 후:
python -c "from pipeline.edgar_fetcher import fetch_companyfacts; fetch_companyfacts(97476)"
python scripts/build_generic_actuals.py --cik 97476 --fye-month 12 --start 2021Q1 --end 2026Q1
# 기대: 풀블롭 기반 actuals 블록이 현 프로파일과 bit-identical(전사 정확성 증명).
#       불일치 시 프로파일 actuals를 풀블롭 기준으로 교정.
```

---

## 3. 방법론 결정 & 근거 (6축 리뷰 대상)

1. **Forward 캘리브레이션(채점 경로).** base 2026Q2: 매출 $5,225M / EPS $1.90 — 회사 가이던스 미드($5.20B/$1.91)에 앵커, 컨센($5.24B/$1.92) 소폭 하회. 확률가중 $5,207M/$1.89. Bear=가이던스 하단($5.0B/$1.68), Bull=상단($5.4B/$2.06). growth 벡터(base, forward순 Q2→Q3→Q4→Q1) `[0.083, 0.035, -0.030, 0.020]`, op_margin `[0.40,0.41,0.39,0.375]`(가동률 fall-through 75–85% ex-감가 근거), tax 0.13(Q2 가이드), net_interest **−0.018**(Q1'26 OP $1,808M→pretax $1,714M = 매출의 −1.95% 근거).
2. **regime_break_quarter = 2025Q1.** 2025에 (a) 300mm/CHIPS 감가상각으로 GM 구조 하향(~70%'22→~58%'25), (b) FY24 저점 후 수요 회복이 정렬. forward 윈도가 이 레짐을 연장 → post-break가 유의 skill 창. 펀더멘털 정당화(체리피킹 아님), 전 윈도 투명 보고.
3. **`_slot` 계절버그 처리 = IBM 세션 canonical 준수(공유코드 미수정).** `backtest_generic._slot`은 벡터를 캘린더-분기로 슬롯매칭, `project_scenario`(forward)는 positional → 12월결산+Q2윈도서 1분기 회전 불일치. **forward 포인트 추정은 정확**; 백테스트만 오정렬. **엔진 미수정(호스트 워크스트림)**, 대신 리포트에 **캘린더-정합 독립 재계산** 병기.
4. **GM 포인트 추정 = 애널리스트 레이어.** generic은 GP=0(의도적 미분해). GM 58.7%(+0.7pt) 추정과 감가상각(고정)/가동률(변동) 분해는 FROZEN 리포트 (b)에 별도 기재 — 모델 산출 아님을 명시.

---

## 4. 검증 결과 (샌드박스; Codex 독립 재현)

```
python -m pytest -q
#  → 193 passed  (baseline 186 + 신규 TXN 7). 네트워크 의존 2건도 DART 캐시 존재 시 green.
python scripts/verify_9q_sha.py
#  → sandbox (CPython 3.11/linux): 077ecb10986a5f2a7e81b31dc595ae47077b8ed7d6fb3ababfb1d5073891933c  MATCH
#  → host (CPython >=3.12/win32, Neumaier sum): b979d79fc380939d0bfd25a121543b67195e2beed47ef857c56ad79d0be1f6e7  MATCH
#     rev MAPE 8.9875% / EPS MAPE 10.3856% / bias -3.5751%  ← 메모리 경로 bit-identical(미변경 증빙)
python generic_cli.py --profile profiles/txn.generic.yaml --json
#  → 확률가중 FY EPS 2026=5.72(전방3분기), 2027=1.81; 백테스트 post-break N=5 매출 MAPE 6.2%(엔진 내장, _slot 오정렬 값)
```
- **디스크 무결성:** profiles/txn.generic.yaml·파생캐시 on-disk sha256 = 헤더 기재값과 일치(마운트 truncation 없음). NUL 0, UTF-8, 개행 정상.
- **캘린더-정합 독립 백테스트(버그 교정, Codex 재현용 로직: 타깃 캘린더분기 Q2→pos0·Q3→pos1·Q4→pos2·Q1→pos3):** full N=20 매출 MAPE **4.3%**(RW 5.6%, MASE **0.77**) / EPS 15.3%(RW 9.9%, MASE 1.55). post-break N=4 매출 **3.6%**(RW 7.6%, MASE **0.47**) / EPS 16.1%(MASE 1.16). → 매출은 RW 명확 하회, EPS는 단일 forward op_margin의 크로스-사이클 마진 이질성(backtest↔forward 커플링, _slot과 별개)으로 트레일.

### Codex 호스트 독립 재현 (2026-07-22)
- `SEC_EDGAR_USER_AGENT` 설정 후 `fetch_companyfacts(97476, use_cache=False)`로 3,997,542-byte SEC companyfacts 풀블롭을 재수집. 풀블롭 기반 21행의 값·기간·accession/source를 프로파일과 대조한 결과 **0 diff**. 2021–2025 Q4 매출(FY−9M) = 4,832 / 4,670 / 4,077 / 4,007 / 4,423 USD million.
- TXN 단독 테스트: 캐시 존재 시 **7 passed**, 신선 클론(캐시 부재) 시 **6 passed, 1 skipped**. 호스트 dirty tree 전체는 **207 passed**이며 TXN 기인 신규 실패 없음.
- 호스트 재생성 생성물의 Yahoo Q2 컨센서스는 매출 5,237.29 / EPS 1.94로 FROZEN 앵커 5,240 / 1.92와 전반적으로 정합(일일 스냅샷 차이).

---

## 5. 6축 리뷰 체크리스트 (Codex)

- **정확성:** ① 파생 캐시 값 vs 호스트 풀블롭(§2 재수집) — 특히 Revenue YTD(전사 붕괴 재구성분). ② FY합 항등식 재확인. ③ forward Q2 계산(EPS=NI×scale/shares, net_interest 부호) 손검산. ④ Q2 $5,207M/$1.89가 가이던스·컨센과 정합.
- **건전성:** 시나리오 확률합=1, 드라이버 방향성(가동률 fall-through, 감가상각 ~flat, tax 13%), regime_break 2025Q1 정당화, GM 분해 논리.
- **회귀안전:** 9Q sha `077ecb10…933c` bit-identical, 메모리/공유코드 미변경, 193 pass, 신규 테스트가 프로파일 무결성 가드.
- **범위규율:** additive-only, generic 경로 한정, `_slot`·기타 공유코드 미수정(호스트 몫으로 명시).
- **검증가능성:** 파생 캐시 재현 가능(build_generic_actuals verify), on-disk sha, source 문자열에 accession/as-filed EPS 보존.
- **유지보수성:** 프로파일 notes에 provenance·라벨계약·backtest커플링 경고, 테스트 커버리지, 본 핸드오프.

---

## 6. Known issues / open flags (호스트 워크스트림)

1. **`_slot` 계절 오정렬 (공유코드).** GEV/TXN/GOOGL/TSLA 공통(12월결산×Q2윈도). 근본 수정은 `generic_cli.backtest_generic`에 캘린더-정합 슬롯 매핑 도입 = 호스트 결정 사항(회귀 표 동반). 현재 "NOTICED BUT NOT TOUCHING". IBM 세션 [[efe-ibm-q2-2026]] 참조.
2. **backtest↔forward 마진 커플링.** 단일 forward op_margin이 사이클 마진 스윙(피크~50%→저점~34%) 미추종 → EPS 백테스트 과대. 구조적 한계, 리포트에 공개. 개선안: 백테스트에 별도 seasonal margin anchor(호스트 검토).
3. **파생 캐시 대체.** §2 풀블롭 재수집으로 전사 정확성 최종 확정 후 캐시 교체 권장.
4. **사후 채점(발표 후 별도 세션):** actual 확보 → 매출/EPS MAPE·bias·컨센 surprise → 4-lever generic 귀인 → **★GM 오차 = 감가상각(고정)/가동률(변동) 분해** → skill 갱신. 결과를 본 파일에 before/after로 추기.

_참고: FROZEN 리포트가 사용자 전달 완료(발표 ~14h 전 동결). 발표 = 2026-07-22 미국 장마감후(KST 7/23 새벽)._
