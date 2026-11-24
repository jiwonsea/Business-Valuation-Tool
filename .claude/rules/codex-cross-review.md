---
paths: ["**/*.py", "**/*.yaml", "**/*.md"]
---

# Codex ↔ Claude Cross-Review Loop

BVT 엔진·모델 개선의 표준 절차. 2026-07-13 4라운드에서 확립. **핵심 원칙: Codex를 신뢰하지 말고 검증하라.**

## 루프
```
Claude 구축
  → Codex 평가 (6축 60점 · [필수]/[권고] · GO / CONDITIONAL GO / NO-GO)
  → Claude가 Codex 주장을 독립 재현  ⚠️ 믿지 말고 재계산·재실행
  → Claude 반박/수용 판정 + 조건부 승인
  → Codex 정책 확정본 회신  ⚠️ 코드 수정 전
  → Claude 정책 승인 (조건 명시)
  → Codex 구현
  → Claude 검증 (독립 재현 + 회귀표)
  → 반복
```

이 루프로 잠복 결함 10건 발견: 단위 100배 오판(주당 106,526원 vs 1,065원) · SOTP 클램프 무언의 삭감 · MC가 PBV 세그먼트 skip(중앙값 −401원) · MC 비결정성(PYTHONHASHSEED) · Peer가 EV/EBITDA와 EV/Sales 직접 비교("−94.7% 할인") · Sensitivity 음수 축·죽은 열축 · Relative Valuation 기준일 혼용 · console이 적용 안 한 distress 할인을 "적용했다"고 거짓 출력 · DCF skip해놓고 "시장 내재 WACC" 출력 · as-of 가격을 실시간가가 덮어씀.

## 🔴 Codex의 반복 실패 패턴 6가지 (전부 실제로 발생)

1. **NUL 오염** — 짧은 내용으로 기존 파일을 덮어쓸 때 잔여 바이트가 NUL로 남는다. **2라운드 연속 발생**했고 `CLAUDE.md`·`profiles/nexus.yaml`(로드 불가)·`engine/units.py`까지 깨졌다. **두 번 다 "NUL 스캔: clean"이라고 보고했다.**
   → **작업 종료 직후 직접 스캔할 것:**
   ```bash
   python -c "
   import os
   bad=[p for r,d,f in os.walk('.') if '__pycache__' not in r and '.git' not in r
        for p in [os.path.join(r,x) for x in f] if p.endswith(('.py','.yaml','.md','.sql'))
        and open(p,'rb').read().count(b'\x00')]
   print('NUL:', bad or 'clean')"
   ```
   → 파일 쓰기는 **원자적으로** (임시 파일 → `os.replace()`). `pipeline/profile_generator.py::_atomic_write_yaml` 참조.

2. **요구사항 조용한 이탈** — 명시한 요구(R-1·R-2)를 이행하지 않고 **보고서에 언급조차 없었다.** 회귀표를 역산해서 발견했다.
   → **구현 전 정책 확정본을 반드시 먼저 받아라.** 이탈 시 사전 통보를 규칙으로 못박아라.

3. **항목 번호 누락** — 목록이 "2."부터 시작하는 일이 2회. 그때마다 수정 항목 하나가 통째로 사라질 뻔했다 (MC의 PBV 포함, `result.dcf is None` 가드).
   → 확정본에 **1번부터 명시**하게 하라.

4. **자기에게 유리한 회귀만 확인** — "NVDA·TSLA의 `gap_diagnostic` 생존"을 **과잉 수정을 잡는 핵심 테스트**로 지목했는데, AAPL만 확인하고 넘어갔다. 그 둘이 정확히 죽은 프로필이었다.
   → 회귀 기준을 **표로 못박고 빈칸을 채워서 보고**하게 하라.

5. **주장 검증 필수** — "48개 프로필 diff 0", "pytest 통과", "NUL clean" 중 여러 건이 사실과 달랐다.

6. **docstring이 없는 가드를 문서화** — `_attach_gap_diagnostic`이 *"No-op for non-DCF methods"*라고 써놓고 실제 코드에는 그 체크가 없었다.
   → **주석 말고 코드를 읽어라.**

## 작업 규칙 (Codex 핸드오프에 항상 포함)
- working tree에 **미커밋 작업 다수** → `git checkout -- <f>` / `git restore` / `git reset --hard` **절대 금지**
- 파일 수정 직후 `ast.parse` + 줄 수 확인 (Windows 마운트에서 무언의 truncation 이력)
- CRLF 유지
- `engine/`은 순수 함수 (IO 금지) · Pydantic 입력 직접 mutate 금지 → `model_copy(update=...)`
- 완료 후: `pytest tests/` 전체 (deselect 불필요 — fixtures 분리 `2203856` 완료. verify_partB 스크립트 2종은 2026-07-18 폐기 — 기대값 stale)

## 호출 경로 (2026-11-25 기준)
- **계획·구현 검토**: 호스트 세션이 해당 worktree 루트에서 `codex exec --sandbox read-only -c model_reasoning_effort=high`를 직접 부른다.
- **파이프라인 관문(G3 가설·G4 결과)의 검토**: `tools/codex_bridge/direct_call.py`의 `run_codex_review()`만 쓴다 (번들 사본 · 고정 명령줄 · 스키마와 입력 해시 검증).
- **파일 큐 브리지 시제품(`tmp/codex_bridge/`)은 쓰지 않는다** (2026-11-25 Jiwon 결정, 자동 시작 해제). 호스트의 `codex`를 직접 부를 수 없는 세션에서 검토가 필요하면 브리지를 다시 켜지 말고 Jiwon에게 먼저 묻는다.

## NO-GO 자동 재검토 루프
2026-11-14 Jiwon 제안으로 채택. Codex가 NO-GO를 내면 사람을 기다리지 않고 고쳐서 다시 맡긴다.

1. **재현 먼저.** Codex의 [필수]를 Claude가 독립 재현한다. 재현되면 고치고, 재현되지 않으면 고치지 않고 반박으로 기록한다.
2. **좁게 다시 묻는다.** 재요청서는 이전 [필수]의 해소 여부와 수정이 만든 회귀만 묻는다. 범위를 넓히지 않는다.
3. **상한 3회.** 같은 대상에 3회까지다. 3회 뒤에도 NO-GO면 멈추고 쟁점 표를 Jiwon에게 올린다. 파이프라인 실행 중의 관문(G3·G4)은 2회 뒤 자동 BLOCKED다.
4. **바로 멈추는 경우.** [필수]가 정책·범위·비용 결정일 때, 같은 지적을 두고 Claude 재현과 Codex 주장이 두 번 엇갈릴 때, 고치려면 승인된 허용 파일 밖을 건드려야 할 때, 유료 호출·운영 DB·발행이 필요할 때.
5. **CONDITIONAL GO.** 조건이 "실행 후 확인"이면 진행하고 조건을 추적 목록에 남긴다. 조건이 수정 요구면 NO-GO와 같이 처리한다.
6. **GO의 한계는 그대로다.** Codex GO는 L1·L2 검증(결정적 검사 · 독립 재계산)을 대체하지 않고, Codex 주장은 계속 재현한다.
7. **기록.** 라운드마다 요청서·판정·소요·토큰을 남긴다.

## 리포트/엔진 경계
`.claude/rules/reporting-boundary.md` 참조 — CLI·`output/`이 엔진 계산을 **복제**하는 안티패턴이 3회 반복됐다(console distress · 역방향 DCF · reverse-rNPV). 새 계산을 추가하기 전에 **`ValuationResult`에 이미 있는지 먼저 확인**하라.
