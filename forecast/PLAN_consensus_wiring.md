# PLAN — consensus 배선 수정 (Workstream ②-후속 / ①-B 계열, 즉시 1순위)

> **zero-context 핸드오프 plan.** 작성 2026-06-19 (세션 C 해석 결과). 구현은 **사용자 승인 후 별도 focused 세션**에서.
> 코드/주석/식별자 = 영어, 사용자용 출력 = 한국어. 선행: `HANDOFF_backtest_diag.md` 세션 C(NOTICED 버그 + 실측), `PLAN_skill_metrics.md` §3.2(surprise-direction 정의).

---

## 0. 한 줄 요약

surprise-direction·consensus-skill 지표가 **모든 환경에서 N=0/None**으로 죽어 있다. 원인은 컨센 부재가 아니라 `pipeline/consensus_loader.py`가 `earnings_history` 행의 분기 필드를 `period`로 읽는데 캐시·yfinance는 **`quarter`**로 키하는 **필드명 불일치 1건**. 1-line 수정으로 vintage 컨센이 살아나 8Q 중 3분기가 측정된다(실측 in-memory 패치: skill_score +0.483, surprise 3/3, N=3). thesis-정의 지표("컨센과 intrinsic value의 gap")를 켜는 최저비용·최고레버리지 작업.

## 1. 왜 1순위 (데이터 근거)

- 세션 C 실측: 모델은 naive RW를 매출·EPS 모두 이김(MASE 0.65 / 0.49). 그러나 **컨센 대비 우위**는 프로젝트의 핵심 주장인데 현재 코드에선 *보이지 않는다* — N=0이라 README도 "보류"로 비워둠.
- in-memory 패치 결과 모델이 vintage 컨센을 EPS level(skill_score +0.483)·surprise 방향(3/3) 모두 이김. **단 N=3 < 4 → 참고용.** 수정 후 fixture/캐시 확대로 N을 키워야 "참고"가 "측정"이 된다.
- **호스트도 동일 실패.** 사용자의 호스트 실행도 surprise=N/A였을 것 → 측정 자체가 막혀 있으므로 다른 모델 개선(tax/finance)을 평가할 잣대도 반쪽. 측정 복구가 예측 개선에 선행하는 게 합리적.

## 2. 스코프 가드레일

- **Additive/수정 최소.** 핵심은 `consensus_loader.py`의 필드명 매핑 1건. 그 외엔 테스트·렌더·fixture만.
- **NOT TOUCHING:** `engine/skill_metrics.py`(정의 정확 — 입력만 비어 있었음), `engine/backtest.py`(배선 정상), forecast 수치 일체.
- **컨센 *forward* 스냅샷(①-B 3배 깨짐)은 본 PLAN 아님.** 본 PLAN은 *vintage history*(`earnings_history`, 비순환·현실적)만 복구. forward 스케일 가드/KR 소스 교체는 별개(README P1 로드맵).
- 가정 수치 변경 없음.

## 3. 설계 / 변경 항목

### 3.1 버그 수정 (1-line, 핵심)
- `pipeline/consensus_loader.py` history 루프: `row.get("period")` → yfinance/`yahoo_fetcher._records`가 산출하는 실제 키 사용.
  - **권장: 방어적 매핑** `row.get("period") or row.get("quarter")` — yfinance 버전에 따라 index명이 달라질 수 있으니 둘 다 수용(레거시 캐시 호환). 단일 키 하드코딩보다 안전.
  - 검증: `to_consensus_record(cache_raw)` → `history` 키 `{2025Q2, 2025Q3, 2025Q4, 2026Q1}` 채워짐.

### 3.2 회귀 가드 테스트 (failing-test 우선)
- **신규 `tests/test_consensus_loader.py`** (합성, 네트워크 무관):
  - `earnings_history` 행이 `quarter` 키일 때 history가 채워짐(현재 버그 재현 → 수정 후 green).
  - `period` 키(레거시)일 때도 채워짐(방어적 매핑 보증).
  - 분기 라벨 변환 정확(`2025-06-30` → `2025Q2`), `_clean` 통과.
  - 빈/누락 `earnings_history` → history `{}` graceful(기존 동작 불변).

### 3.3 surprise/consensus 렌더 검증
- 세션 B에서 md/html/xlsx에 skill 섹션은 이미 배선됨. history가 채워지면 `surprise_direction_accuracy`·`skill_score_eps_vs_consensus`·`n_surprise_scored`가 None→실값으로 바뀜. **N 작을 때 "표본 부족(N=3)" 경고가 출력에 뜨는지** 확인(PLAN_skill_metrics §3.2/§5). 없으면 그 주석만 추가.

### 3.4 N 확대 (선택, 사용자 판단)
- 현재 캐시 `earnings_history`는 4행(2025Q2–2026Q1)만. 8Q 전체 surprise 측정엔 더 깊은 vintage가 필요.
  - 후보 A: 호스트에서 과거 시점 yahoo 스냅샷 누적 수집(date-tagged 캐시 보존).
  - 후보 B: KR broker 컨센(네이버/FnGuide, README P1) — 더 신뢰도 높음.
  - **방향만 제시, 데이터 소싱은 사용자 소유.** N<4면 리포트·README에서 계속 "참고용"으로 표기.

## 4. 실행 순서

1. baseline: `pytest -q` green 확인. 현재 dry-run/캐시 backtest의 skill 섹션 1부 보관(surprise=None 상태 = before).
2. `tests/test_consensus_loader.py` 작성(현 버그 재현 → red).
3. `consensus_loader.py` 방어적 매핑 수정 → green.
4. 캐시 backtest 재측정: surprise/consensus가 실값(N=3)으로 렌더되는지 + "표본 부족" 경고 확인. 수기 1건 교차검증(skill_score = 1 − model_MAE/cons_MAE 손계산 일치 — 세션 C 실측 +0.483).
5. README "보류¹" → 실값으로 갱신할지 사용자 확정(N=3이면 "참고용" 명시).

## 5. Acceptance

- `consensus_loader`가 `quarter`/`period` 양쪽 키에서 history를 채운다(테스트로 보증).
- backtest 리포트의 surprise-direction·consensus-skill이 None→실값(N 표기). N<4 → "표본 부족" 경고.
- `pytest -q` 전부 green. forecast/MASE/Theil 수치 **불변**(컨센 배선은 별개 경로).
- 수치 변경 없음. N 확대(3.4)는 사용자 확정 대기.

## 6. 위험 / 가정

- yfinance 버전별 `earnings_history` index명 변동 → 방어적 매핑으로 흡수(단일 키 하드코딩 금지).
- N=3은 통계적으로 무의미 수준 — 점추정(surprise 100%, skill +0.48) **과대해석 금지**. 본 PLAN의 가치는 "지표를 켜는 것"이지 "우위를 입증하는 것"이 아니다. 입증은 N 확대 후.
- 샌드박스: DART 캐시로 오프라인 backtest 가능(세션 C 입증). yahoo today-날짜 캐시 alias + `C:\temp` ssl 우회 필요(세션 C HANDOFF 참조).

## 7. 변경 파일 요약 (구현 시)

수정: `pipeline/consensus_loader.py`(필드명 매핑 1건). 신규: `tests/test_consensus_loader.py`. 조건부: 렌더 "표본 부족" 경고(없을 시), README surprise 행.
NOT TOUCHING: `engine/skill_metrics.py`, `engine/backtest.py`, forecast 경로, forward 컨센 스케일(①-B).
