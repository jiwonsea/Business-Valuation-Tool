# HANDOFF → Codex — MU FY2026 Q4 사후 채점 (독립 채점 → 대조 → SCORED)

> 작성 Claude · 2026-10-01 KST · 대상 FROZEN `forecast/reports/mu_fy2026q4_forecast_FROZEN.md` (sha256 `eab1184f721cd69460ffc4ddefd9851c59815207c35975db0dd1a2962b629f9a`)
> 🔴 **투자 자문 아님.** 사후 채점 기록이며 매매 판단 근거가 아니다.
> 🔴 **FROZEN·프로파일 불변.** 이 단계는 문서만 만든다. 코드·YAML·FROZEN·프로파일은 수정하지 않는다. git 쓰기 금지.
> 근거: FROZEN §(f-5) 사후 채점 예약 · `forecast/PLAN_efe_2026sep_mu.md` 일정표("사후 채점 + HO-4", T+1) · 리포트 계획 rev-4.3 §6 E2-B 입력 게이트 ②(SCORED 존재 + commit·SHA)

---

## 1. 목적과 순서

FQ4 FY26 실적으로 Freeze A를 FROZEN §(f-5)의 7개 항목대로 채점한다. 이 결과(`mu_fy2026q4_SCORED.md`)가 리포트 E2-B의 입력 게이트다.

| 단계 | 담당 | 산출물 |
|---|---|---|
| S1 독립 채점 | **Codex** | `forecast/REVIEW_CODEX_mu_fy2026q4_scoring_r1.md` (§1–§9) + 결론 SHA |
| S1′ 독립 채점 | **Claude** (병렬) | `forecast/REVIEW_CLAUDE_mu_fy2026q4_scoring_r1.md` + 결론 SHA |
| S2 대조 | 양측 | 각자 상대 문서를 **자기 SHA 기록 후에만** 열고, 불일치 항목을 §10에 판정 |
| S3 SCORED 작성 | Claude | `forecast/reports/mu_fy2026q4_SCORED.md` (합의 값만) |
| S4 SCORED 검증 | Codex | 재현·대조 PASS/CHANGES |
| S5 커밋 | Jiwon | 호스트 PowerShell (게이트 ②는 commit 해시가 필요) |

- **블라인드**: S1에서 Claude 문서를 읽지 않는다. Claude도 Codex 문서를 읽지 않는다.

## 2. 허용 입력 (읽기 전용)

| 입력 | sha256 | 용도 |
|---|---|---|
| `logs/mu/fy2026q4/postprint/ex991.htm` | `5dad1ce5c2dd8958dad947ab1f12a1015bfcc29c7e8a29e48379e983f425120e` | FQ4 실적(provisional) · FQ1 FY27 Business Outlook |
| `logs/mu/fy2026q4/postprint/8k_index.html` | `bda394e8b8f41e492a0051b11b92a9469c2bdac5d280e273763b8946519861e4` | accession `0000723125-26-000018` · Accepted 2026-09-30 16:02:22 ET |
| `logs/mu/fy2026q4/postprint/remarks.pdf` | `2821d4ccaae50b40dcd28cd4e766c69c509e73d666e4109d5907c7205a03b700` | DRAM/NAND 가격·비트 서술(SF4) · 세율·주식수 서술 |
| FROZEN | `eab1184f…9f9a` | 예측값·라벨·임계값 — **동결 당시 값만** 쓴다 |
| `forecast/profiles/mu.generic.yaml` | `faa60912…dfd6` | 시나리오 경로 확인(참고) |
| `forecast/CONSENSUS_efe_2026sep_mu_FY26Q4_2026-09-25.md` | — | 표시만. 서프라이즈 판정 **산출 금지**(FROZEN §(d-2)) |

- 첫 저장본 `logs/_to_delete/**`는 입력이 아니다.
- 10-K는 아직 없다. G0-A의 `FY − 9M` 대조는 **`PENDING_10K`**로 두고 E2-C에서 확정한다(FROZEN §(f-5)-1: PR = provisional, 10-K = confirm).
- 셀사이드 조사 표본(`logs/sellside_survey/**`)의 수치는 쓰지 않는다.

## 3. 채점 항목 (FROZEN §(f-5) 순서)

### 3-1. 전사 + G0 (§(f-1))
1. EX-99.1 손익표에서 매출·매출원가·GAAP GM·opex·영업이익·영업외 라인 전부·세전·세금·순이익·희석주식수·GAAP/비GAAP 희석 EPS를 옮긴다. 각 값에 **표 이름·행 이름**을 붙인다.
2. **원문 항등식**으로 전사를 검증한다: 매출 − 원가 = 매출총이익, 총이익 − opex = 영업이익, 영업이익 + 영업외 = 세전, 세전 − 세금 = 순이익, |NI ÷ 희석주식수 − EPS| ≤ $0.01(G0-C).
3. G0-A(분기말 2026-09-03 헤더) · G0-B(14주 문장) · G0-C · G0-D(GAAP·비GAAP 열 머리) 판정. 실패 지표는 채점 무효.

### 3-2. 포인트 오차와 밴드 커버리지 (§(a-1)·§(a-2)·§(f-4))
- base·확률가중 대비 매출·GAAP EPS·비GAAP EPS·GAAP GM·영업이익의 오차(절대·%). **비GAAP는 비GAAP끼리만**(+$0.27 브릿지 가정의 오차를 별도 행으로).
- 밴드 커버리지: 매출 [49,000, 58,223] · GAAP EPS [29.33, 36.66]. 밖이면 **밴드 실패**.
- 표면·**주당**(× 13/14 또는 ÷14·13) 성장률을 둘 다 적는다.

### 3-3. 가이던스 대비 라벨 (§(d-0)·§(d-1))
- 매출·GAAP EPS·비GAAP EPS·GAAP GM 각각 `ABOVE_HIGH`/`IN_RANGE`/`BELOW_LOW`를 **(d-0) 무차이 밴드 그대로** 판정하고, 예측 라벨과 적중 여부를 표로.
- 상회율(실적 ÷ 가이던스 중간값 − 1)을 계산해 10분기 기록 표의 11번째 행으로 덧붙인다(FROZEN 표는 수정하지 않고 SCORED에 새 표로).
- 컨센서스 = `UNAVAILABLE`. HIT/MISS/NO_SURPRISE를 산출하지 않는다.

### 3-4. RC-1·RC-2·RC-3 (§(f-4))
- 우선 outcome = **연결 GAAP 영업이익**. 동결 비교값(A 43,599 · B 11,781 · C 33,318)을 그대로 쓴다.
- RC-3: 매출 APE > 10% 또는 EPS APE > 25%면 재검토 트리거.
- 스킬 게이트는 **표본 1로 갱신하지 않는다**(`NO_OOS_SKILL_EVIDENCE` 유지).

### 3-5. 스윙 팩터 발화 (§(f-3))
- SF2+SF3(GM 라벨 판정 + 크기 서술) · SF4(서술, 준비문 근거) · SF5(신설 below-OP 라인 출현 여부 기록) · SF6(GAAP ETR·주식수 범위 밖 여부) · SF7(아래 3-7) · SF8(= 3-4).
- 층(판정/서술)을 FROZEN 표 그대로 지킨다.

### 3-6. 4-lever generic 귀인 (GAAP EPS)
- 매출 / 영업이익률 / OP→NI 전환(below-OP + 세율, 하위 분해 포함) / 주식수. 기여 합 = EPS 오차.
- 🔴 잔차 0은 대수적 보장이다. 정확성 근거는 3-1의 원문 항등식이다.
- 레버 순서(경로 의존)를 명시하고, 순서를 바꿨을 때의 차이를 한 줄로 적는다.

### 3-7. FQ1 FY27 가이던스 예측 (§(c-2), SF7)
- Business Outlook에서 매출 가이던스 중간값·범위, GAAP/비GAAP GM·EPS 가이던스를 옮긴다.
- **주당 방향** = $\frac{G_1/13}{A_4/14}-1$, 무차이 ±2.0% → `GROWTH`/`FLAT`/`DECLINE`. 예측 `FLAT`과 비교.
- 예측 가이던스 중간값(bear ≈ 39,600 · base ≈ 48,750 · bull ≈ 57,300)과의 오차.

### 3-8. lead_hours (FROZEN 머리 정의)
- `frozen_at` = 2026-09-25 08:54:41 KST.
- 최초 공개 시각: 와이어 원문을 입력으로 받지 않았으므로 **8-K Accepted(2026-10-01 05:02:22 KST)를 상한**으로 쓰고, 와이어 시각은 `UNVERIFIED`로 적는다. 두 값과 사용한 쪽을 명시한다.

## 4. 공통 규칙
1. 인용은 15단어 미만, 따옴표·쪽/행 표시.
2. 모든 수치에 출처(파일·표·행) 표시. 추정·가정은 `J` 표시.
3. 주수: FQ4 14주, FQ3·FY25 Q4 13주. 정규화한 값과 원값을 함께.
4. 리포트 RLE(HANDOFF 부록 R9)·FY27 경로는 **채점 대상이 아니다.** 언급하지 않는다.
5. LF, 원자적 쓰기, 종료 후 NUL 스캔.

## 5. Codex S1 산출물 구성 — `forecast/REVIEW_CODEX_mu_fy2026q4_scoring_r1.md`

§1 전사표 + 항등식 · §2 G0 판정 · §3 포인트 오차·밴드 · §4 가이던스 라벨 · §5 RC-1~3 · §6 SF 발화 · §7 4-lever 귀인 · §8 FQ1 가이던스·SF7 · §9 lead_hours · §10 (S2) Claude 대조 — **§1–§9 SHA 기록 후 작성**.

- **허용 경로**: 위 파일 1개 생성뿐.

---

*본 문서는 투자 자문이 아니다. This document is not investment advice.*
