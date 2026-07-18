# P0-1 순차입금 정규화 — 재작업 완료 (CODEX 재판정 요청)

**계약:** `HANDOFF_CODEX_p0-0_commit.md` §8 · `PLAN_deep_research.md` §2.1
**이전 판정:** "재작업 후 승인" — 블로커 1건(게이트 우회) + 허용오차 산식 + 커밋 분리

---

## 0. 재작업 대응표 (CODEX 지적 5건)

| # | 지적 | 대응 |
|---|---|---|
| 1 | **블로커** — `run_valuation()` 직접 호출이 게이트를 우회 | `run_valuation()` 시작점에서 `apply_net_debt_gate(vi)` 호출. 게이트를 **멱등**으로 만들어 `load_profile()`과 이중 적용해도 `net_debt_legacy`가 덮어써지지 않는다 (§1) |
| 2 | 허용오차 산식이 태그 구조와 불일치 | **3 → 5단위**. 유도: Path A 현금 2 + Path A 차입 5 + Path B 2 = **최대 9회 반올림 × 0.5 = 4.5 → 5** (§2) |
| 3 | NVDA 소비 성공은 미보장 | 수용. 안전한 실패(mismatch 차단)이며 동작 무변화. 대응 방향은 §3 |
| 4 | P0-1b 반독립 DART 축을 소비 게이트로 불승인 | 수용. 소비 게이트 제안 **철회**. `cash_reconciled` **진단 전용**으로 재분류 (§4) |
| 5 | 커밋 분리 필요 | 헝크 지도 작성 (§6). **인덱스는 건드리지 않았다** — 줄바꿈 이슈 때문에 사람이 확인 후 스테이징하는 편이 안전하다 |

## 1. 게이트 우회 차단 + 멱등성 (블로커 해소)

```
load_profile(path) ──┐
                     ├─> apply_net_debt_gate(vi) ──> 엔진/콘솔/Excel (전부 vi.net_debt를 읽음)
run_valuation(vi) ───┘        (멱등)
```

- `run_valuation()` 진입 첫 줄에서 게이트를 적용한다. `app.py`·스크립트·테스트처럼 `load_profile()`을 거치지 않고 `ValuationInput`을 직접 만든 경로도 이제 게이트를 통과한다.
- **멱등 조건** (`_already_gated`, CODEX 권고 계약 그대로):
  `res.status == "consumed"` **and** `normalization_version == NORMALIZATION_VERSION` **and** `net_debt_legacy is not None` **and** `vi.net_debt == res.value`(= 지금 다시 대조해도 여전히 reconciled).
  → 이미 통과한 입력은 **복사조차 하지 않고** 그대로 반환한다 (`twice is once`).
- **원장 소멸 롤백** (`_demote_orphaned_normalization`, 2차 판정 블로커 해소): `status == "absent"`(= components 없음)에서 조기 반환하면, 소비 후 원장만 제거된 입력이 정규화 값을 그대로 유지한다. 이제 **소비 흔적이 남아 있으면 강등**한다:
  - 소비 후 원장 제거 → `net_debt = net_debt_legacy`, `net_debt_legacy = None`, version → `legacy`
  - 원장 없이 `normalization_version`만 최신으로 위조한 YAML → `legacy`로 강등
  - 원장도 소비 흔적도 없으면 P0 이전 프로필 → 손대지 않는다 (R10 무변화)
- **불일치 원장 교체 롤백**: 소비 후 components가 불일치 원장으로 교체되면 재대조에서 차단으로 뒤집히고, `net_debt`를 `net_debt_legacy`로 롤백한다.

신규 테스트 7건: 우회 차단 2 · 멱등 2 · 원장 교체 재게이트 1 · **원장 제거 롤백 1 · 위조 version 강등 1**.

## 2. 허용오차 5단위 (`NET_DEBT_RECONCILE_TOLERANCE = 5`)

```
Path A 현금성   : cash + (시장성 채무증권 | 단기투자)   -> 최대 2회 반올림
Path A 차입     : 개별 차입 태그 5종의 합                -> 최대 5회
Path B 독립 합계: 결합 차입 + 결합 현금                  -> 최대 2회
                                                 합 9회 × 0.5 = 4.5 -> 5단위
```
5단위 = NVDA 순현금 $41,865M의 **0.012%**. 이보다 큰 차이는 반올림으로 설명되지 않는다 = 정의 오류 = `False`.
`reconciliation_delta`는 computed field로 계속 노출된다 — 차이를 숨기지 않는다.

## 3. NVDA 소비 여부 (CODEX 확인 결과 반영)

CODEX 확인: 독립 **부채** 후보 중 NVDA에 실재하는 건 `LongTermDebt`뿐 → CP를 포함하지 않으면 mismatch로 차단된다.
현재 구현은 그 경우 **legacy 정의를 계속 쓰고 차단 사유를 로그로 남긴다** (안전한 실패).

> **판단 요청:** Path B 부채 축을 `LongTermDebt + CommercialPaper`로 넓히면 NVDA는 소비될 수 있으나,
> CP 태그가 Path A와 **공유**되어 독립성이 부분적으로 훼손된다. 독립성을 지키고 차단을 감수할지,
> CP만 공유 항으로 허용할지는 계약 판단이라 임의로 넓히지 않았다.

## 4. DART (P0-1b 철회)

- 소비 게이트로서의 반독립 축 제안은 **철회**한다. 현금만 CF로 대조하면 부채 오류를 못 잡는다는 지적이 맞다.
- DART는 계속 `net_debt=None` → KR 전 종목 `blocked_unreconcilable` → legacy 유지 (동작 무변화, 승인됨).
- CF 기말현금 대조는 향후 **`cash_reconciled` 진단 전용 플래그**로만 검토한다. 순차입금 정상화 소비 권한과 분리한다.

## 5. 검증 결과

| 항목 | 결과 |
|---|---|
| `pytest tests/test_normalize.py` | **34 passed** (초안 27 + 1차 재작업 5 + 2차 재작업 2) |
| `pytest tests/test_provenance.py` | **36 passed** (P0-0 계약 회귀 없음) |
| `pytest tests/ --ignore=tests/test_quality.py` | **763 passed, 7 failed** — 전부 P0-1 무관¹ |
| `ruff check` (변경 파일 전체) | 1건 — `valuation_runner.py:69` 미사용 import `apply_gate_to_profile` (**다른 세션 WIP**, 손대지 않음) |
| `cli.py --profile profiles/sk_ecoplant.yaml` | **35,066원** — R10 통과 |

¹ telemetry 5건(다른 세션 WIP: `test_telemetry.py:126` SyntaxError) + FRED 2건(샌드박스 마운트 `PermissionError`).

## 6. 커밋 분리 — 헝크 지도

**P0-1 전용 (통째로 스테이징 가능):**
`engine/normalize.py`(신규) · `tests/test_normalize.py`(신규) · `schemas/provenance.py` ·
`pipeline/edgar_parser.py` · `pipeline/dart_parser.py` · `pipeline/data_fetcher.py` · `db/backtest_repository.py` · 이 문서

**혼재 파일 — 헝크 선별 필요 (`git add -p`):**

| 파일 | P0-1 헝크 | **제외**할 다른 세션 WIP |
|---|---|---|
| `schemas/models.py` | `@@ ~895` `net_debt_legacy` + P0-1 주석 **1개만** | `@@ ~801` `PeerSegmentStats` provenance 필드(`premium_pct`/`band_position`/`rationale`) · `@@ ~830` `generated`/`curated`/`profile_text` · `ValuationResult.investability_blockers` |
| `pipeline/profile_generator.py` | `@@ ~618` 순차입금 정규화 원장 블록 **1개만** | `@@ ~36` `_profile_is_protected()` · `@@ ~366` protected/staging 분기 · `@@ ~508` YAML `draft/generated/curated` |
| `valuation_runner.py` | `@@ ~37` import · `@@ ~379` `net_debt_components`/`normalization_version` kwargs · `@@ ~410` 게이트 함수 4개 + `return apply_net_debt_gate(vi)` · `run_valuation()` 첫 줄 게이트 | `@@ ~152` `profile_text = Path(path).read_text()` · `@@ ~353` `draft/generated/curated/profile_text` kwargs (단, 같은 헝크의 `vi = ValuationInput(` 리네임은 **P0-1**이므로 헝크 편집 `e` 필요) |

**인덱스는 손대지 않았다.** 이유: 작업 트리는 CRLF, HEAD 블롭은 LF이고 `core.autocrlf`가 비어 있어
지금 `git add`하면 **파일 전체가 줄바꿈 변경으로 커밋된다.** `.gitattributes`/renormalize는
CLAUDE.md가 단독 커밋으로 분리하라고 못박은 사안이라 임의로 처리하지 않았다.

## 7. 남은 후속

- Supabase 마이그레이션(`db/migrations_backtest.sql` 3컬럼) 수동 적용. 미적용이어도 스냅샷 저장은 죽지 않는다(P0 컬럼만 빼고 재시도 + WARN).
- Windows에서 `python cli.py --company NVDA --auto` → 로그의 `순차입금 정규화 소비/차단` 라인 확인 (§3 판단 근거).
- 별건(기록): SK에코플랜트 품질 71→0(F)은 다른 세션 WIP investability gate(`DCF/peer-median 0.49`)가 stale `.pyc` 때문에 그동안 실행되지 않다가 이제 도는 것. P0-1 무관, `vi.draft`는 여전히 False.
