# START — EFE P0 정책 변경 분리 커밋

> 새 세션용 자립 프롬프트. **이 파일 하나만 읽고 시작할 수 있다.**
> 작성 2026-08-07 · 선행: `POLICY_p0_fact_ledger_2026-08-07.md` (rev.3, Codex FINAL APPROVED)

---

## 0. 목표

EFE 워크트리에 **P0 정책 변경(문서)과 무관한 AMD/SNDK/SPCX 작업이 섞여 있다.** P0 문서 정정만 분리해 커밋하고, 동결 규약 위반 잔재 1건을 정리한다.

**코드 커밋은 이미 끝났다** — 손대지 말 것.

| 커밋 | 리포 | 내용 |
|---|---|---|
| `ae2ba41` | BVT | corp-action 레지스터 (P0-5) |
| `2e09c74` | EFE | base/weighted 병기·gap-of-gap 분리 (P0-4) |
| `239ecec` | EFE | `RecurringFairValueBlock` 골격 (P0-2) |

남은 것은 **P0-1(사실 원장)·P0-3(유효세율) 문서 정정의 커밋**뿐이다.

---

## 1. 검증된 현재 상태 (2026-08-07 확인 완료 — 재조사 불필요)

### 1-1. P0 문서 정정은 **완료됐으나 미커밋**

| 파일 | git 상태 | 반영 내용 |
|---|---|---|
| `reports/sk_hynix_q2_2026_scorecard.md` | ` M` | **§10 append 완료** (241행 `<!-- SK_HYNIX_Q2_2026_ERRATA_START -->`). 10-1 해석 반전 · 10-2 채점 무영향 · 10-3 파생 교훈 · **10-4 유효세율 §4 H3 무효화** · **10-5 base·weighted 병기**. §5 원문(123~125행)은 **직접 수정 없이 보존** — 규약 준수 확인 |
| `HANDOFF_CODEX_efe_q2_2026_skhynix.md` | ` M` | 34행 주가 정정(`−9.61%, 1,401,000원`), 98행 유효세율 `23.4587%`, 666행 서사 반전, **716행 조정 EPS 105,318원** |
| `START-skhynix-report-2026q2.md` | `??` | 주가·해석 정정 (원래 untracked) |

⇒ **이 3개만 커밋하면 P0-1·P0-3이 닫힌다.**

### 1-2. AMD FROZEN 워크트리 변경 = **동결 규약 위반 잔재, 버려야 한다**

`reports/amd_q2_2026_forecast_FROZEN.md`가 ` M` 상태이며 `[PRE-PRINT ERRATA]` **69줄이 직접 append**돼 있다. 이는 규약 위반이다.

> `PROMPT_autofreeze_COMMON.md:51` — **"FROZEN 파일은 freeze 후 어떤 편집도 금지. 정정·보완은 `*_errata.md` 형제 파일로."**

**내용 손실 위험 없음 — 검증 완료.** 같은 내용이 `reports/amd_q2_2026_errata.md`에 **이미 커밋**돼 있다(`5f02652 docs(amd): preserve pre-print errata in post-print commit`).

```
FROZEN 워크트리 추가분 45줄 중 errata 파일에 없는 줄: 2개
  (1) "## [PRE-PRINT ERRATA] — …"        → errata는 "## PRE-PRINT ERRATA — …" (대괄호 없는 형식)
  (2) 서두 문구 1줄                       → errata는 "이 문서는 앵커가 아니다" 서두를 별도로 씀
실질 내용(E-1·E-2·E-3, HEAD sha ae3203e…, forecast sha 30539b14…)은 전부 보존됨
```

⇒ **`git checkout -- reports/amd_q2_2026_forecast_FROZEN.md`** 로 되돌리면 `tests/test_frozen_integrity.py` 실패가 해소된다. **이것이 EFE 전체 테스트의 유일한 실패 원인이다** (320 passed, 1 failed).

### 1-3. 나머지 미커밋 = **P0와 무관한 별건. 손대지 말 것**

```
 M CLAUDE.md
 M HANDOFF_CODEX_efe_2026aug_{amd,sndk,spcx}.md
?? HANDOFF_CODEX_efe_hardening_2026-08.md · HANDOFF_P0_approval_checklist.md
?? PROPOSAL_policy_{resolver,selection_rules}_v1.yaml
?? START-efe-aug2026-{00-COMMON-DELTA,amd,sndk,spcx,vst}.md
?? START-efe-q2-2026-skhynix-T3a-gate.md
?? inputs/amd_q2_2026_actual{,.filled}.yaml
?? profiles/gev_q3_2026.dev.generic.yaml
?? reports/{sndk_fy2026q4,spcx_q2_2026}_SCORED.md
?? scripts/score_{amd_q2_2026,sndk_fy2026q4}.py
?? tests/test_{score_amd_scaffold,sndk_fy2026q4_score}.py
?? POLICY_p0_fact_ledger_2026-08-07.md        ← 정책 문서 (커밋 B 후보)
?? tests/test_frozen_integrity.py             ← 동결 게이트 (커밋 B 후보)
```

---

## 2. 실행 계획

### 커밋 A — P0 문서 정정 (필수)

```bash
cd <EFE>
git add reports/sk_hynix_q2_2026_scorecard.md \
        HANDOFF_CODEX_efe_q2_2026_skhynix.md \
        START-skhynix-report-2026q2.md
git commit -m "fix(docs): correct 2026-07-29 price record and effective tax rate per P0 policy

- scorecard §10 append: reverse §5 interpretation, invalidate §4 H3 tax rate
- 7/29 close 1,401,000 (-9.61%), intraday low 1,246,000, KOSPI -5.98%
- effective tax rate 23.4587% (28,785.8/122,708.4, full precision)
- adjusted EPS 105,318 replaces the discarded 7.8% row
- §0-§9 body untouched; anchors (profile 4ebeb7c, sk_hynix_20260710.*) unchanged"
```

**`git add -A` 금지.** 위 3개만 명시적으로 스테이징한다.

### 정리 — AMD FROZEN 되돌리기 (필수)

```bash
git checkout -- reports/amd_q2_2026_forecast_FROZEN.md
```

§1-2의 검증 결과에 따라 내용 손실이 없다. **커밋 A와 별도 작업이며 커밋 대상이 아니다**(워크트리 원복이므로).

### 커밋 B — 정책·게이트 (선택, 판단 요망)

```bash
git add POLICY_p0_fact_ledger_2026-08-07.md tests/test_frozen_integrity.py
git commit -m "docs+test: add P0 fact-ledger policy and FROZEN integrity gate"
```

`test_frozen_integrity.py`는 P0-2 커밋(`239ecec`)에 포함되지 않았고 아직 untracked다. **게이트가 커밋되지 않으면 규약이 강제되지 않는다** — 커밋 A 이후 별도로 넣을 것을 권고한다.

---

## 3. 검증

| # | 항목 | 기대 |
|---|---|---|
| 1 | `git status --porcelain reports/amd_q2_2026_forecast_FROZEN.md` | **출력 없음** (원복 확인) |
| 2 | `pytest tests/ -q` (EFE) | **전량 green** — 기존 1 failed가 해소돼야 한다 |
| 3 | G1 게이트 | `python cli.py --company sk_hynix` → base rev `79,070.26666360501` / wtd EPS `70,607.8551553665` relative error 0 |
| 4 | 9Q SHA | `scripts/verify_9q_sha.py` → `b979d79f…f6e7` MATCH |
| 5 | 커밋 A diff | **3개 파일만**. AMD/SNDK/SPCX 파일이 섞이면 실패 |
| 6 | 스코어카드 §0~§9 | 커밋 A diff에서 **§10 append 외 변경 0** (`git show --stat` + `git diff HEAD~1 -- reports/sk_hynix_q2_2026_scorecard.md`로 확인) |

---

## 4. 금지 사항

- **`git add -A` / `git commit -a` 금지** — 워크트리에 별건이 20개 넘게 있다
- **`git restore` / `git checkout` / `git reset --hard`를 광범위하게 쓰지 말 것** — §2의 AMD FROZEN 1개 파일만 예외
- **`profiles/sk_hynix.yaml`(`4ebeb7c`) · `reports/sk_hynix_20260710.*` 불가침**
- **스코어카드 §0~§9 본문 직접 수정 금지** — 이미 §10 append로 처리됨
- **세율 앵커 16.4% 변경 금지** — 반기보고서까지 유지(G-b 승인 사항)
- **`amount = 62,165.8` 입력 금지** — 전체 영업외손익이지 키옥시아 단일 금액이 아니다(P0-2 NO-GO)

---

## 5. 참고 — 이번 사이클에서 확정된 표기 규약

`POLICY_p0_fact_ledger_2026-08-07.md` §11. 특히:

```
법인세 원장값 28,785.8 (십억원) = 28조 7,858억     ← 반올림 표기 금지
유효세율 = 28,785.8 / 122,708.4 = 0.2345870372     (라벨 23.46%, 계산엔 full precision)
조정 EPS = 70,608 + 45,348 × (1 − 0.2345870372) = 105,317.947 → 105,318
```

Claude가 초안에서 "28조 7,860억"으로 반올림 표기했던 것을 Codex 실행분이 **28조 7,858억**으로 바로잡았다. BVT 측 산출물(리포트·워크북·`facts.py`)도 2026-08-07 동일하게 정정 완료.

---

## 6. 다음 단계 (이 세션 범위 밖)

- 반기보고서(8월 중순) 공시 후: 법인세 당기/이연 구분, 키옥시아 처분/평가 분해 → P0-2 금액 입력, 세율 앵커 재검토
- EFE 2026Q1 EPS 오차 −17.1%가 키옥시아 FVPL 평가이익(10.19조)에서 왔는지 백테스트 레버 분해 (정책 §3-3, 현재 "강한 가설")
- AMD/SNDK/SPCX 미커밋 작업 별도 정리
