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
- 완료 후: `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` (verify_partB 스크립트 2종은 2026-07-18 폐기 — 기대값 stale)

## 리포트/엔진 경계
`.claude/rules/reporting-boundary.md` 참조 — CLI·`output/`이 엔진 계산을 **복제**하는 안티패턴이 3회 반복됐다(console distress · 역방향 DCF · reverse-rNPV). 새 계산을 추가하기 전에 **`ValuationResult`에 이미 있는지 먼저 확인**하라.
