# START — NVDA Phase C 변경분 검토·커밋 (BVT 새 세션)

> **실행 위치**: `F:\dev\Portfolio\business-valuation-tool`
> **선행 완료**: Phase A(입력·게이트) → Phase B(TTM 앵커, 커밋 `8ae6aab`=HEAD) → **Phase C(forward+peer beta) 구현·검증 완료, 미커밋**. D1~D6 후속 조치까지 Claude 독립 재현 완료 (`PLAN_nvda_phaseC_forward_peerbeta.md` §6).
> **이 세션의 목적**: Phase C 변경분**만** 커밋. 신규 기능 구현 금지, 리팩토링 금지.
> **필독 순서**: `PLAN_nvda_phaseC_forward_peerbeta.md` (§2 확정 정책 · §6 독립 검증 + Codex 후속 조치) → 본 문서
> 🔴 **`git restore / checkout -- / reset --hard / stash` 전면 금지** — 작업트리에 Phase C 외 미커밋 작업 ~250파일 잔존.

---

## Step 0 — 착수 전 재검증 (주장 믿지 말 것, 전부 재실행)

```cmd
git log --oneline -3          :: 기대 HEAD: 8ae6aab (Phase C 커밋이 이미 있으면 백로그부터 갱신)
for /r %f in (*.pyc) do @del "%f"
set PYTHONUTF8=1 & set PYTHONDONTWRITEBYTECODE=1
python scripts\verify_nvda_phaseC.py
python -m pytest tests\ -q --deselect tests/test_engine.py::TestScenarioDriverRoundTrip
```

기대치 (2026-07-17 Claude 독립 재현 실측 — 이 수치와 다르면 원인 규명 전 커밋 금지):
- verify_nvda_phaseC: **C-1~C-12 ALL PASS** (C-6 auto=392,965 / manual=391,300)
- pytest: **992 passed, 5 deselected** (분해: Phase B 실측 979 + 신규 파일 7 + gate 2 + 후속 fixture 3 + forward 1)
- nvda.yaml: 596행 · CRLF · `peer_beta_snapshot.judgement.status: validated` (fence [1.6298, 2.7758], company 2.040) · `forward_anchor.relative_period: 0y` / FY27 / 2027-01-25
- 🔴 **교훈**: 이전 START 문서의 "pytest 1013 기준"은 근거 없는 수치였다. 기준 수치는 반드시 실측 문서 체인(`HANDOFF_CODEX_nvda_phaseB_closeout.md` L53의 979 → 992)으로 인용할 것.

---

## Step 1 — 커밋 범위 분류 (핵심 난제: 혼재 diff)

작업트리는 Phase C 이전의 미커밋 작업을 대량 포함한다. **파일 단위 `git add`는 그 파일의 HEAD 대비 diff 전체를 커밋한다** — Phase C 수정 파일 일부는 이전 세션의 미커밋 변경이 함께 실려 있다.

### 그룹 1 — 순수 Phase C 신규 (편승 없음, 그대로 add)
```
engine/peer_beta.py
pipeline/forward_estimates.py
pipeline/peer_beta_snapshot.py
scripts/rewrite_nvda_phaseC.py
scripts/verify_nvda_phaseC.py
tests/test_peer_beta.py
tests/test_forward_estimates.py
tests/test_nvda_phaseC.py
PLAN_nvda_phaseC_forward_peerbeta.md
START-nvda-phaseC.md               (세션 기록용 — 포함 여부는 사용자 판단)
```

### 그룹 2 — Phase C 수정이지만 **이전 미커밋 변경 혼재 가능** (add 전 diff 전수 검토)
```
schemas/models.py                  (Phase C: ForwardAnchor/PeerBeta* 모델)
valuation_runner.py                (Phase C: 두 블록 파싱 + gate 전달)
engine/investability_gate.py       (Phase C: peer_beta_range / 이전: profile_status 등)
profiles/nvda.yaml                 (Phase C: 두 블록 추가 / 이전: Phase A·B 변경 — HEAD가 이미 8ae6aab라 실질 Phase C만일 것, 확인)
output/console_report.py           (Phase C: forward/peer 표시)
output/sheets/assumptions.py       (Phase C: forward/peer 표시)
tests/test_investability_gate.py   (🔴 untracked이지만 파일 대부분이 이전 세션 작업 + Phase C 테스트 2개)
```
각 파일에 대해 `git diff HEAD -- <f>` (untracked는 전체)를 읽고 **Phase C 외 변경이 실리는지 목록화**하라. 혼재 발견 시 그 내용을 커밋 메시지에 명시하거나, 사용자에게 분리 여부를 물어라. hunk 단위 부분 add(`git add -p`)는 이 저장소에서 금지 — 검증된 전체 파일 상태와 커밋 내용이 달라져 C-검증이 무효화된다.

### 그룹 3 — 오늘 mtime이지만 Phase C 무관 가능성 (기본 제외, 편승 금지)
```
CLAUDE.md · pipeline/edgar_parser.py · profiles/000660.yaml · scripts/verify_nexus_round4.py
HANDOFF_CODEX_hynix_* · HANDOFF_CODEX_nh_* · HANDOFF_CODEX_nvda_phaseB_closeout.md · START-nvda-phaseB.md · *.png
```
🔴 `git add -A` / `git add .` **절대 금지.** 명시 파일 목록으로만 add.

---

## Step 2 — 커밋

1. Step 1 확정 목록만 `git add <files...>`.
2. `git status`로 staged 목록이 확정 목록과 1:1인지 대조.
3. 커밋 메시지(제안 — 혼재분 발견 시 본문에 추가):
```
feat(nvda): Phase C — forward(FY27E) anchor + qualified peer beta snapshot

- forward_anchor: yfinance 컨센서스(0y=FY27 실증), metric별 provenance, 실적과 구조 분리
- peer_beta_snapshot: 적격 US peer 6 (KR 2건 benchmark_mismatch 기록), Tukey fence 판정 validated
- judge_company_beta 순수함수 + investability gate peer_beta_range (outlier=block)
- WACC 11.52% · βL 1.697 · 가격 불변 (판정만 산출)
- C-1~C-12 ALL PASS · pytest 992 passed
```

## Step 3 — 커밋 직후 검증 (git object 기준 재고정)

```cmd
git log --oneline -2
git show HEAD:profiles/nvda.yaml | python -c "import sys,yaml,hashlib; b=sys.stdin.buffer.read(); d=yaml.safe_load(b); print('lines',b.count(b'\n'),'sha',hashlib.sha256(b).hexdigest()[:12],'anchor',d.get('financial_anchor'),'judge',d['peer_beta_snapshot']['judgement']['status'],'fwd',d['forward_anchor']['relative_period'])"
```
- 출력된 **신규 nvda.yaml 기준(행수·sha)을 다음 세션 문서에 기록** (Phase B의 bb276cf/467을 대체하는 새 baseline).
- fresh bytecode로 `verify_nvda_phaseC.py` + `verify_nvda_phaseA_v2.py` + `verify_nexus_round4.py --skip-pytest` 재실행 → 전부 PASS.
- NUL 스캔 (ROUND3 §11 스크립트) + `git status`로 잔여 미커밋 수가 "이전 −커밋분"과 일치하는지 확인 (파일 소실 검출).

## 회귀표 (커밋 전후 동일해야 함)

| # | 항목 | 기준 |
|---|---|---|
| K-1 | 🔴 넥써쓰 | 18/445/891 · 362 · Base equity 36,211 · net_debt 51,687 |
| K-2 | 🔴 Phase A | WACC 11.52% · βL 1.697 · consumed_blume |
| K-3 | Phase C 판정 | validated · fence [1.6298, 2.7758] · WACC·가격 불변 |
| K-4 | pytest | 992 passed, 5 deselected |
| K-5 | 45개 프로필 | crash 0 |
| K-6 | NUL/AST/CRLF | clean (커밋 후 git object로도 확인) |
| K-7 | 미커밋 보존 | Phase C 외 작업트리 파일 수 불변 |

## 완료 정의
Step 0 재검증 PASS → 범위 분류·혼재 목록화(필요 시 사용자 확인) → 커밋 → Step 3 전항 PASS + 신규 baseline 기록 → **Phase C 커밋 COMPLETE.**
