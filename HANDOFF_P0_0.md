# 핸드오프: P0-0 구현 (데이터 계약 / 계보)

업무: `PLAN_deep_research.md` **P0-0만** 구현. 정상화 로직·파서·게이트는 **건드리지 않는다.**
승인: CODEX 3차 평가 — 판정 `P0-0 착수 가능` (블로커 4건 해소 완료)

프로젝트: `F:\dev\Portfolio\business-valuation-tool`

---

## 0. 세션 시작 시 읽을 것

1. `PLAN_deep_research.md` — **§1 (P1 3범주)**, **§2.1 (순차입금 taxonomy)**, **§2.2 (세그먼트 3레이어)**, **§3 P0-0**
2. `.claude/rules/db-backtest.md` — Supabase drift / persistence asymmetry
3. `CLAUDE.md` § Session Safety

**PLAN을 읽지 않고 필드만 보고 구현하지 말 것.** 필드 이름보다 *왜 분리하는지*가 계약의 본체다.

---

## 1. 범위 (파일 3개, 그 외 금지)

| 파일 | 작업 |
|---|---|
| `schemas/provenance.py` | **신규 생성** |
| `schemas/models.py` | `ValuationInput`에 필드 5개 추가 (전부 Optional/기본값) |
| `db/migrations_backtest.sql` | `prediction_snapshots`에 컬럼 3개 추가 |

**범위 밖 (다음 세션):** `db/repository.py`의 snapshot write 경로, `engine/normalize.py`,
파서(`edgar_parser`/`dart_parser`), 게이트, `profile_generator`.
→ **이번에 추가하는 컬럼은 당분간 기본값으로만 채워진다. 그게 정상이다.** 쓰기 경로를 만들지 말 것.

---

## 2. `schemas/provenance.py` (신규)

P1 3범주를 타입으로 강제하는 것이 목적이다. 관측치(①)와 선언된 가정(②)이 **같은 dict에 섞이면 계약이 무의미**하다.

```python
"""Provenance contract — every material number carries where it came from.

P1 (PLAN_deep_research.md §1):
  ① 관측치        -> Source(method="observed")     : 공시/시장데이터. LLM 생성 금지
  ② 명시적 가정   -> DeclaredAssumption            : 허용하되 ①과 분리 + 민감도 필수
  ③ 근거 없는 창작 -> 표현 불가 (타입 자체가 없다)
"""

NORMALIZATION_VERSION = "2026.07-nd1"   # 순차입금 정의 v1 (§2.1)
LEGACY_VERSION = "legacy"               # P0 이전에 생성된 모든 프로필/스냅샷

SourceKind = Literal[
    "SEC EDGAR", "DART", "EDINET", "yfinance", "FRED", "ECOS",
    "manual", "fallback constant",
]
Method = Literal["observed", "derived", "declared_assumption"]


class Source(BaseModel):
    value: float | int | str | None = None
    source: SourceKind
    accession: str | None = None      # SEC accession / DART rcept_no
    url: str | None = None
    as_of: date | None = None
    method: Method = "observed"
    stale: bool = False               # 허용 시차 초과 (§2.4: rf 7일 / ERP 45일)


class DeclaredAssumption(BaseModel):
    """P1 범주 ②. 관측치가 아니다 — 절대 Source로 표현하지 말 것."""
    value: float
    rationale: str                    # 필수. 빈 문자열 금지 (validator)
    declared_by: str = ""             # "llm" | "human:<user>"
    at: date | None = None
    sensitivity_required: bool = True


class NetDebtComponents(BaseModel):
    """§2.1. 합계만 저장하면 정의 오류를 영원히 못 잡는다."""
    cash: int = 0
    marketable_debt_securities: int = 0
    short_term_investments: int = 0
    restricted_cash_excluded: int = 0      # 차감하지 '않은' 금액 (기록용)
    equity_securities_excluded: int = 0    # 차감하지 '않은' 금액 (상방 브리지용)
    gross_borrowings: int = 0
    net_debt: int = 0                      # = gross_borrowings - (cash + mds + sti)
    reconciled: bool = False               # 구성요소 합 == net_debt 검증 통과 여부
```

요구사항:
- `DeclaredAssumption.rationale`에 **빈 문자열 금지** validator.
- `NetDebtComponents`에 `reconcile()` 메서드 또는 model_validator로 합계 대조 → `reconciled` 설정.
- **`Source`로 가정을 표현할 수 있는 우회로를 만들지 말 것.** `method="declared_assumption"`을
  `Source`에 넣는 것은 타입 혼선이다. `Method` Literal에 남겨두되, `assumption_sources`에는
  `observed`/`derived`만 들어가도록 validator로 막는다.

---

## 3. `schemas/models.py` — `ValuationInput` 필드 추가

`ValuationInput`(현재 L817~) 끝부분에 추가. **전부 Optional/기본값 → 기존 YAML 프로필이 그대로 로드돼야 한다.**

```python
    # ── P0-0: normalization provenance (PLAN_deep_research.md §3) ──
    normalization_version: str = LEGACY_VERSION
    net_debt_components: Optional[NetDebtComponents] = None
    assumption_sources: dict[str, Source] = {}        # ① 관측치 전용
    declared_assumptions: dict[str, DeclaredAssumption] = {}  # ② 가정 전용
    segment_disclosure_level: Literal["L1", "L2", "L3", "none"] = "none"
```

- import: `from schemas.provenance import (...)`. **순환 import 주의** — `provenance.py`는
  `models.py`를 import하지 않는다 (단방향).
- `model_config`에 이미 있는 immutability 관례 유지. 필드 직접 대입 금지, `model_copy(update=...)`.
- **기존 필드 이름을 바꾸거나 `net_debt`를 제거하지 말 것.** `net_debt`는 legacy로 계속 살아 있고,
  정상화 값은 P0-1에서 별도로 들어온다. 이번엔 **자리만 만든다.**

---

## 4. `db/migrations_backtest.sql`

파일 하단의 `-- Schema updates (run if tables already exist)` 블록에 **추가**. RLS 블록보다 위.

```sql
-- P0-0: normalization provenance (PLAN_deep_research.md §3)
ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS normalization_version TEXT DEFAULT 'legacy';

ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS net_debt_components JSONB DEFAULT '{}';

ALTER TABLE prediction_snapshots
    ADD COLUMN IF NOT EXISTS segment_disclosure_level TEXT DEFAULT 'none';
```

- **`db/migrations.sql`이 아니다.** `prediction_snapshots`는 backtest 마이그레이션에 산다.
- **과거 행을 UPDATE하지 말 것.** 기본값 `'legacy'`가 곧 "P0 이전 정의로 계산됨"이라는 정보다.
  소급 재작성은 look-ahead를 훼손한다 (CODEX Q2).
- Supabase는 자동 적용되지 않는다. SQL Editor 수동 실행 — README/rules 관례 확인.

---

## 5. 테스트

`tests/test_provenance.py` (신규):

1. `Source`가 `method="declared_assumption"`으로 `assumption_sources`에 들어가면 **거부**
2. `DeclaredAssumption(rationale="")` → **ValidationError**
3. `NetDebtComponents` 합계 불일치 → `reconciled=False`
4. NVDA 실제값 재현: `cash=13_237, marketable_debt_securities=37_098, gross_borrowings=8_470`
   → `net_debt == -41_865`, `reconciled=True`
5. **하위호환**: `net_debt_components` 등이 전혀 없는 **기존 YAML 프로필**(`tests/fixtures/`의 것 아무거나)이
   `ValuationInput`으로 로드되고 `normalization_version == "legacy"`

**주의:** `profiles/`에서 픽스처를 읽지 말 것 — 주간 파이프라인이 덮어쓴다 (CLAUDE.md § Testing).

---

## 6. 검증

```bash
python -m pytest tests/test_provenance.py -q
python -m pytest tests/ -q          # 베이스라인 회귀 (기존 프로필 로드가 깨지면 실패)
ruff check .
python cli.py --profile profiles/sk_ecoplant.yaml   # 기존 프로필이 그대로 도는지 (스모크)
```

**완료 조건:** 전체 테스트 통과 · ruff clean · 기존 프로필/CLI 동작 무변화.
**P0-0은 동작을 바꾸지 않는다.** 무언가 값이 달라졌다면 범위를 넘은 것이다.

---

## 7. 안전 수칙 (CLAUDE.md § Session Safety)

- 작업 트리에 **미커밋 변경이 대량**으로 있다. `git checkout -- <f>`, `git restore`, `git reset --hard`,
  `git show HEAD:<f> > <f>` **절대 금지.** HEAD는 오래된 baseline이다.
- `.py` 편집 직후 즉시 무결성 확인: `python -c "import ast; ast.parse(open('<f>',encoding='utf-8').read())"` + `wc -l`.
  이 Windows 마운트 경로에서 대형 in-place 편집이 파일을 **중간에서 잘라먹은 전례**가 있다 (`schemas/models.py` 포함).
- `models.py`는 큰 파일이다. **원자적 rewrite**(전체 읽기 → 메모리 변환 → 1회 쓰기) 후 `ast.parse` 검증 권장.
- 작업 트리는 **CRLF**. 새 파일도 CRLF 유지.

---

## 8. 커밋

```
feat(schemas): add provenance contract for normalization (P0-0)
feat(db): add normalization columns to prediction_snapshots (P0-0)
```

---

## 9. 이 세션에서 하지 말 것

- `engine/normalize.py` 생성 (P0-1)
- 파서에서 순차입금 정의 변경 (P0-1)
- `db/repository.py`에 새 컬럼 쓰기 경로 추가 (P0 이후)
- 베타/매크로/peer/게이트 (P0-2~5)
- 기존 프로필 일괄 재작성
- **골든 산출물 `valuation-results/2026-07-10-nvda-deep-dive/` 수정** — 읽기 전용

---

## 10. 완료 보고 형식

1. 변경 파일
2. 추가된 필드/컬럼 목록
3. 추가한 테스트
4. 커밋 해시 2개
5. 남은 리스크 1-2줄
6. **다음 단계(P0-1) 착수 전 재확인이 필요한 계약이 있으면 지적**
