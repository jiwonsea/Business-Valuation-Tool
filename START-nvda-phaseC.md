# START — NVDA Phase C: Forward(FY27E) 앵커 + 적격 Peer Beta Snapshot (BVT 새 세션)

> **실행 위치**: `F:\dev\Portfolio\business-valuation-tool`
> **선행 완료**: Phase A(입력·게이트·provenance 정상화) + Phase B(TTM/FY 앵커 정렬) — 커밋 `8ae6aab feat(nvda): complete Phase B TTM anchor`
> **필독 순서**: `ROUND3_POLICY_APPROVED_nvda_autoprofile.md` §2(peer 원칙)·§7(Phase 정의)·§9(성공기준) → `HANDOFF_CODEX_nvda_phaseB_ttm_IMPL.md` → `HANDOFF_CODEX_nvda_phaseB_closeout.md` → `profiles/nvda_fy27e.yaml`(forward 참조모델) → 본 문서
> **작업 표준**: Codex ↔ Claude 6축 교차검증 루프 (§6). **Codex 주장을 믿지 말고 독립 재현.**

---

## Step 0 — 착수 전 재검증 (선행 상태 확인 — 주장 믿지 말 것)

1. **Phase A+B 커밋 상태 확인** (working-tree read 말고 **git object로**):
   ```cmd
   git log --oneline -3
   git show 8ae6aab:profiles/nvda.yaml | python -c "import sys,yaml,hashlib; b=sys.stdin.buffer.read(); d=yaml.safe_load(b); print('lines',b.count(b'\n'),'sha',hashlib.sha256(b).hexdigest()[:12],'anchor',d.get('financial_anchor'),'prov',list(d['ttm_provenance']['fields']))"
   ```
   기대: `8ae6aab` HEAD · nvda.yaml 467행 · sha `bb276cf5...` · anchor `ttm` · provenance 5필드(revenue/op/net_income/dep/capex).
2. **불변 재검증** (fresh bytecode 필수 — stale가 이전 세션을 물었음):
   ```cmd
   for /r %f in (*.pyc) do @del "%f"
   set PYTHONUTF8=1 & set PYTHONDONTWRITEBYTECODE=1
   python scripts\verify_nvda_phaseA_v2.py
   python scripts\verify_nexus_round4.py --skip-pytest
   ```
   기대: Phase A ALL PASS · 넥써쓰 18/445/891 · 362 · Base equity 36,211 · net_debt 51,687 · R-8 ENV SKIP.
3. `git status` — 미커밋 작업 다수(~252) 보존 확인. 🔴 **`git restore/checkout/reset --hard` 금지.**

### 🔴 이번 프로젝트의 표준 교훈 (CLAUDE.md Session Safety 반영됨)
- **에이전트 샌드박스 read는 최근 기록 파일에 신뢰 불가** (Windows↔Linux 마운트 stale + stale `.pyc`). "truncation·필드 누락" 발견 시 **덮어쓰기 전에 git object / 로컬 호스트 read로 재확인**. 지난 세션 유령 truncation 다수·stale import(model_fields) 발생.

---

## Step 1 — Phase C가 푸는 문제 (두 축, 서로 독립)

Phase B로 **실적 앵커 시차**는 닫혔다(FY/TTM). Phase C는 과소평가 "해결"이 아니라 **두 개의 독립 정합성 축**을 추가한다:

### 축 1 — Forward(FY27E) 앵커
- TTM은 **제출된 실적** 롤업. Forward는 **컨센서스 예측**($391B FY27E 매출, `nvda_fy27e.yaml`). **성격이 다르다.**
- 목적: 실적(FY/TTM)과 **혼합하지 않고** forward를 별도 시나리오 앵커로 제공, 예측/실적 경계를 명시.

### 축 2 — 적격 Peer Beta Snapshot (P0-4)
- **peer beta는 자동 가격 상향 수단이 아니다** (ROUND3 §2). 회사 자체 beta(Phase A: βL 1.697, consumed_blume)의 **검증·차단 근거**로만 사용.
- 목적: 적격 peer 집합의 beta 분포를 스냅샷하여 회사 beta가 **범위 내(validated) / 이상치(gated)** 인지 판정. WACC를 바꾸지 않는다.

---

## Step 2 — 이미 존재하는 기준선

- `profiles/nvda_fy27e.yaml` — 수동 forward 참조모델. 자동 forward 산출의 수렴 척도.
- Phase A `beta_provenance` 7필드 패턴(raw_levered_beta/blume_adjusted/normalized_bu/window_start/window_end/frequency/calculation_method + source_hash) — **peer beta snapshot이 계승할 provenance 표준.**
- Phase B `financial_anchor: fy|ttm` 계약(`valuation_runner.py:~182`, `schemas/models.py ValuationInput`) — forward 앵커가 확장/공존할 지점.
- NVDA peer 재감사 이력(커밋 `a6b1356`: 실체 없는 피어·소멸 법인 제거) — **peer 적격 기준의 근거.**

---

## Step 3 — 설계 쟁점 (구현 전 정책 확정 — Codex 6축 평가)

1. **Forward 앵커 배치** — `financial_anchor`에 `"forward"` 추가(예측을 base로 소비 → 위험) vs **별도 `forward_scenario` 블록**(실적과 분리, Bull 성향 시나리오로만). ROUND3 §7 "실적과 혼합 금지" 준수 방식 확정.
2. **Forward 데이터 출처·provenance** — 컨센서스는 SEC 불가(미래치). 출처(provider·as-of·analyst 수·컨센서스 종류) 기록, **"consensus estimate"로 명시**(감사가능 실적과 구분). fabrication 금지.
3. **Peer 적격 기준** — 산업 일치, 유동성, 데이터 충분성(Phase A ≥80주 계승?), 비상장·소멸·shell 제외. 기준을 명시·감사가능하게.
4. **Peer beta 산정 방법 일치** — Phase A와 동일(주간 로그수익률 OLS + Blume, 동일 window/benchmark)해야 비교 유효. 방법 불일치 시 비교 거부(fail-closed).
5. **검증 판정 계약** — peer beta 분포(median·범위·n_qualified) 대비 회사 beta가 within-range면 `validated`, 이상치면 `gated/flagged`. **WACC·가격 불변**, 판정만 산출. 어느 레이어(investability_gate?)가 소비하는지 확정.
6. **Peer beta snapshot provenance** — peer별(raw/blume/window/method/source_hash) + 집계(median/range/n). Phase A 패턴 계승.
7. **Forward가 밸류에이션에 미치는 범위** — forward는 리포트·시나리오 표시용인가, DCF 시나리오 입력인가? 실적 base와의 경계 규칙.

---

## Step 4 — 성공 기준 (ROUND3 §9 계승)

- ❌ **peer beta로 가격 상향 / 시장가 추종 금지.** peer는 검증·차단 근거일 뿐.
- ❌ forward 컨센서스를 실적 base와 혼합 금지.
- ✅ forward 앵커가 실적(FY/TTM)과 **구조적으로 분리**되고 "consensus estimate" + provenance로 명시.
- ✅ peer beta snapshot이 **판정(validated/gated)만** 산출, WACC·가격 불변.
- ✅ peer 적격 기준이 명시·감사가능, 방법 불일치 시 fail-closed.
- ✅ 자동 forward 산출이 수동 `nvda_fy27e.yaml`과 합리적 수렴.
- ✅ Phase A/B/넥써쓰 전 불변 유지 (과잉수정 검출).

---

## Step 5 — 회귀 기준표

| # | 항목 | 기준 |
|---|---|---|
| C-1 | Forward 분리 | forward가 base 실적과 미혼합, 별도 구조 |
| C-2 | Forward provenance | provider·as-of·analyst수·"consensus" 표기 |
| C-3 | Peer 적격 기준 | 산업/유동성/데이터/비-shell 필터 적용·기록 |
| C-4 | Peer beta provenance | peer별 + 집계, Phase A 패턴, 방법 일치 |
| C-5 | Peer = 판정만 | within-range/outlier 판정 산출, **WACC·가격 불변** |
| C-6 | Forward 자동 vs 수동 | `nvda_fy27e.yaml` 합리적 수렴 |
| C-7 | 🔴 넥써쓰 불변 | 18/445/891 · 362 · Base equity 36,211 · net_debt 51,687 |
| C-8 | 🔴 Phase A 불변 | WACC 11.52% · βL 1.697 · consumed_blume · provenance 7필드 |
| C-9 | 🔴 Phase B 불변 | financial_anchor fy/ttm · roll_ttm 정답지 · nvda.yaml `8ae6aab` bb276cf/467 |
| C-10 | 기존 45개 프로필 | crash 0 |
| C-11 | pytest | 1013 passed 기준 유지 (`--deselect ...TestScenarioDriverRoundTrip`) |
| C-12 | NUL/AST/CRLF | clean · git object로 검증 |

---

## Step 6 — Codex ↔ Claude 6축 교차검증 루프

```
Claude 진단·정량분해 → Codex 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성) 60점 평가
→ Claude 독립 재현(믿지 말 것) → 반박/수용 판정 → Codex 정책 확정본(코드 수정 전) → Claude 승인
→ Codex 구현 → Claude 검증(독립 재현 + 회귀표) → 반복
```

### 🔴 반드시 지킬 것 (실제 사고 이력)
1. **작업 종료 직후 NUL 스캔** + **`.py` 편집 후 즉시 `ast.parse`+`wc -l`** (mid-line truncate 검출).
2. **원자적 쓰기**(temp→fsync→os.replace) + **기록 직후 재read fail-closed**(Phase B `rewrite_nvda_ttm_provenance.py` 패턴). **프로필 수동 편집 금지.**
3. **CRLF 유지**(working tree) / git blob은 LF 정규화 — git object로 최종 검증.
4. **Codex 주장 전부 독립 재현** — "ALL PASS"·"pytest N"·"NUL clean" 다수가 사실과 달랐음. **커밋 있으면 git object로 검증**(working-tree 마운트 read보다 신뢰).
5. **항목 1번부터 명시**, 회귀표 표로 못박기(넥써쓰·A·B 불변 포함).
6. 🔴 `git restore/checkout/reset --hard` 금지 (미커밋 작업 다수).

---

## 산출물
- `schemas/models.py` — forward_scenario / peer_beta_validation 계약(전부 Optional 기본값, 하위호환)
- `pipeline/` — 컨센서스 forward 수집 + peer 적격 필터 + peer beta 산정(방법 Phase A 일치)
- `engine/` — peer beta 판정 순수함수(validated/gated) + frozen fixture 테스트
- `profiles/nvda.yaml` — forward_scenario + peer_beta_snapshot + provenance (원자적·재read 검증)
- `scripts/verify_nvda_phaseC.py` — C-1~C-12 검증

## 완료 정의
C-1~C-12 전항 PASS(로컬 fresh bytecode, git object 검증) + forward/peer가 **가격 상향 아닌 정합성·차단 근거**로만 작동 → **Phase C COMPLETE.**
peer는 검증·차단 근거이지 가격 상향 수단이 아니다 (ROUND3 §2). forward는 예측이지 실적이 아니다 (§7).
