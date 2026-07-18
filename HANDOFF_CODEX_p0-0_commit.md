# 핸드오프 (CODEX): P0-0 커밋 실행 — **동시 작업 확인 후에만**

**상태:** P0-0 구현·검증 완료 (CODEX 5차 `P0-0 승인` 판정). **커밋만 남았다.**
**단, 이 저장소에서 다른 Cowork 세션이 동시에 작업 중이다.** 커밋 전에 §1을 반드시 통과시켜라.
**작성 시각 기준 HEAD:** `a522485 feat(scripts): 피어 전수 감사 스크립트 + 2026-07-11 리포트`

---

## 0. 이 세션에서 실제로 일어난 일 (사고 포함)

| # | 사건 | 상태 |
|---|---|---|
| 1 | P0-0 구현 (provenance 계약 + models 필드 5개 + migration 컬럼 3개 + 테스트 36건) | 완료·검증됨 |
| 2 | **`.git/index.lock` 스테일 락** 생성 (샌드박스가 `.git`에 쓰기는 되나 삭제 불가) | 사용자가 수동 삭제함 |
| 3 | **인덱스가 꼬여 있었다** — `nvda_ttm.yaml`·`nvda_fy27e.yaml`·`test_quality_trading_exclusion.py`·`audit_peers.py` 삭제 + `engine/quality.py` 172줄 삭제가 **스테이징돼 있었다** | `git reset`(mixed)로 해소. 인덱스 백업: `%TEMP%\git-index.bak` |
| 4 | **`schemas/models.py`가 잘렸다** — 꼬리 4줄 소실, `ast.parse` 실패(`'(' was never closed`) | **복구 완료** (§2). HEAD 꼬리와 바이트 동일 확인 |
| 5 | `git diff --check` 실패 | `core.whitespace=cr-at-eol` 로컬 설정 + `migrations_backtest.sql` LF 복원으로 해소 |

**#4가 중요하다.** 내 마지막 검증(1시간 전) 시점엔 `models.py`가 멀쩡했다. 그 사이에 잘렸다.
이 저장소는 Windows 마운트에서 **대형 파일 in-place 편집이 조용히 truncate된다**(CLAUDE.md §Session Safety).
이번 세션에서만 **3번** 발생했다: `schemas/provenance.py`, `tests/test_provenance.py`, `schemas/models.py`.

> **`ast.parse`만으로는 못 잡는다.** `tests/test_provenance.py`는 `LEGACY_VER`에서 잘렸는데도
> 문법상 유효해서 syntax check를 통과했다. **`pytest` 실행까지 해야 잡힌다.**

---

## 1. [필수 선행] 동시 작업 확인

다른 Cowork 세션이 **같은 작업 트리**에서 돌고 있다. 확인된 증거:

- 최근 60분 내 수정: `HANDOFF_CODEX_r16_profile_curation.md`, `HANDOFF_CODEX_r18_peer_generation.md`,
  `NEXT_SESSION_r18_peer_generation.md`, `DEBATE_e1_round1.md`, `valuation-results/2026-07-12(...)/_weekly_summary.json`
- **`tests/test_telemetry.py` 신규 등장** — 5건 실패 중 (= 저쪽의 WIP, 아직 안 끝났다)
- `schemas/models.py`에 저쪽 헝크 3개가 있다 (§3 헝크 맵 참조)

### 실행할 것

```bash
# (a) 지금도 누가 파일을 쓰고 있는가
find . -newermt '-10 minutes' -type f \
  -not -path './.git/*' -not -path './.cache/*' -not -name '*.pyc' -not -path '*/__pycache__/*'

# (b) 락 잔여물
ls -la .git/index.lock 2>/dev/null && echo "!! 다른 git 프로세스가 돌고 있다 — 중단"
```

**(a)에 `.pytest_cache` / `.ruff_cache` 외의 소스 파일이 나오면 커밋하지 말고 대기하라.**
**(b)에 `index.lock`이 있으면 절대 커밋하지 말라.**

---

## 2. [필수 선행] 무결성 재확인 — 지문 대조

내가 검증을 끝낸 시점의 blob 지문이다. **하나라도 다르면 그 사이 누가 건드린 것이고, 내 검증 결과는 무효다.**

```bash
git hash-object schemas/provenance.py schemas/models.py tests/test_provenance.py db/migrations_backtest.sql
```

| 파일 | blob sha1 | bytes | lines |
|---|---|---:|---:|
| `schemas/provenance.py` | `11907ad0ee67ffa50e1b4daca48c939dbcdacddf` | 11,803 | 269 |
| `tests/test_provenance.py` | `5bbe6d0b67b0609bcac4b2070b6908c0214cf3b9` | 9,900 | 291 |
| `schemas/models.py` | `40639aed1d82fbbe2fd7f2d0645bef6e8ef69898` | 41,012 | 1,132 |
| `db/migrations_backtest.sql` | `95cffb1060eae99377b9b1ff4ad3261a4b2e5177` | 4,716 | 112 |

**truncation 가드 (지문이 달라졌다면 반드시):**

```bash
python -c "import ast; [ast.parse(open(f,encoding='utf-8').read()) for f in ['schemas/models.py','schemas/provenance.py','tests/test_provenance.py']]; print('ast ok')"
tail -1 schemas/models.py     # 기대: valuation_bucket: str = "plain_operating"
python -m pytest tests/test_provenance.py -q          # 기대: 36 passed
python cli.py --profile profiles/sk_ecoplant.yaml     # 기대: 35,066원  ← R10
```

**`models.py`가 또 잘렸다면 `git checkout`/`git restore`/`git show HEAD:<f> > <f>` 절대 금지.**
꼬리 4줄만 잘리는 패턴이다. 바이트 단위로 이어 붙여라:

```python
FRAG = b'        None  # Reverse rNPV (when primary_method '
TAIL = (b'        None  # Reverse rNPV (when primary_method == "rnpv")\r\n'
        b'    )\r\n'
        b'    rnpv_tornado: list[RNPVTornadoItem] = []  # Per-drug peak sales tornado (rNPV only)\r\n'
        b'    valuation_bucket: str = "plain_operating"\r\n')
data = open('schemas/models.py','rb').read()
assert data.endswith(FRAG)
open('schemas/models.py','wb').write(data[:-len(FRAG)] + TAIL)
```

---

## 3. `schemas/models.py` 헝크 맵 — **P0-0은 2개뿐이다**

HEAD 기준 5개 헝크가 있다. **3개는 다른 세션 것이며 P0-0 커밋에 넣으면 안 된다.**

| 헝크 | 위치 | 내용 | P0-0? |
|---|---|---|:-:|
| 1 | `@@ -9,0 +10,9` | `from schemas.provenance import (...)` | ✅ **포함** |
| 2 | `@@ -794,0 +804,4` | `PeerSegmentStats`: `premium_pct` / `band_position` / `rationale` | ❌ 제외 (peer 배수 provenance) |
| 3 | `@@ -817,3 +830,6` | `ValuationInput`: `generated` / `curated` / `profile_text` | ❌ 제외 (r16 profile curation) |
| 4 | `@@ -879,0 +896,19` | `ValuationInput`: P0-0 필드 5개 + `assumption_sources` validator | ✅ **포함** |
| 5 | `@@ -1057,3 +1092,4` | `ValuationResult`: `investability_blockers` | ❌ 제외 (게이트 작업) |

---

## 4. 커밋 실행

§1·§2를 통과했을 때만.

```bash
git add schemas/provenance.py tests/test_provenance.py

git add -p schemas/models.py
#   헝크 1/5  (line ~10,  import)                 -> y
#   헝크 2/5  (line ~804, PeerSegmentStats)       -> n
#   헝크 3/5  (line ~830, generated/curated)      -> n
#   헝크 4/5  (line ~896, ValuationInput P0-0)    -> y
#   헝크 5/5  (line ~1092, investability_blockers)-> n

git diff --cached --stat
#   기대: schemas/models.py (+28) · schemas/provenance.py (+269) · tests/test_provenance.py (+291)
#   그 외 파일이 하나라도 보이면 중단
git diff --cached -- schemas/models.py | grep -E 'premium_pct|band_position|generated:|curated:|profile_text|investability_blockers'
#   기대: 아무것도 안 나옴. 나오면 중단하고 git reset 후 재시도

git commit -m "feat(schemas): add provenance contract for normalization (P0-0)"

git add db/migrations_backtest.sql
git commit -m "feat(db): add normalization columns to prediction_snapshots (P0-0)"

git log --oneline -2
python -m pytest tests/test_provenance.py -q      # 커밋 후에도 36 passed
```

---

## 5. 구현된 내용 요약 (커밋 대상)

### `schemas/provenance.py` (신규 269줄)

P1 3범주를 타입으로 강제한다. `models.py`를 import하지 않는다 (단방향).

- **`Source`** — P1 ① 관측치. `SourceKind`에서 `"manual"`·`"fallback constant"` **제외**
  (사람이 넣은 숫자는 가정이고, 관측 실패는 폴백이다).
  model_validator로 P5를 **타입에서 강제**: `observed` → `as_of` 필수 + (`accession`|`url`) 필수 /
  `derived` → `as_of` 필수 + (`accession`|`url`|`derived_from`) 필수.
- **`DeclaredAssumption`** — P1 ② 가정. `rationale` 비어있음 금지, `at` 필수,
  `proposed_by`(LLM 가능) / **`approved_by` 분리 — `"human:<식별자>"` 강제, 접두사만은 거부**.
  `sensitivity_required: Literal[True]` (민감도 면제 불가, §2.6).
- **`FallbackConstant`** — §2.4 전용. `reason`·`as_of`·`ttl_days` 필수, `stale=True` 기본.
- **`NetDebtComponents`** — §2.1. `net_debt`는 **독립 관측 합계**이며 구성요소에서 유도하지 않는다.
  **`reconciled`는 `@computed_field` 3-상태**: `True`(일치) / `False`(불일치, 예외 안 던짐) /
  `None`(대조 불가 — 합계 미제공 또는 구성요소 한쪽 결측).
  computed라서 직렬화 왕복으로 `reconciled: true`를 **위조할 수 없다**.
- **`assert_observed_only()`** — 관측 원장에 가정이 섞이는 것을 차단.

### `schemas/models.py` — `ValuationInput` 필드 5개 (전부 Optional/기본값)

`normalization_version="legacy"` · `net_debt_components=None` · `assumption_sources={}` (observed/derived만 허용하는 validator) · `declared_assumptions={}` · `segment_disclosure_level="none"`.
기존 `net_debt` 스칼라는 legacy로 그대로 살아 있다. **동작 무변화** (SK에코플랜트 35,066원 유지).

### `db/migrations_backtest.sql` — 컬럼 3개

`normalization_version TEXT DEFAULT 'legacy'` · `net_debt_components JSONB DEFAULT '{}'` · `segment_disclosure_level TEXT DEFAULT 'none'`.
**과거 행 UPDATE 금지** — 기본값 `'legacy'`가 곧 "P0 이전 정의로 계산됨"이라는 정보다. 소급 재작성은 look-ahead를 훼손한다.
**쓰기 경로는 아직 없다** (P0-1 범위). 컬럼은 당분간 기본값으로만 채워진다 — 그게 정상이다.

### `tests/test_provenance.py` (신규 291줄, 36 passed)

Source 최소 provenance · manual/fallback 거부 · 익명 human 승인 거부 · 민감도 면제 거부 ·
`reconciled` 3-상태 (빈 객체 → `None`, 한쪽 결측 → `None`, 불일치 → `False`, NVDA 일치 → `True`) ·
직렬화 위조 차단 · `tests/fixtures/msft_frozen.yaml` 하위호환 (`legacy` / `net_debt==30_346`).

---

## 6. 검증 결과 (커밋 직전 기준)

| 항목 | 결과 |
|---|---|
| `pytest tests/test_provenance.py -q` | **36 passed** |
| `ruff check` (P0-0 3파일) | All checks passed |
| `cli.py --profile profiles/sk_ecoplant.yaml` | **35,066원** — 베이스라인 동일 (**R10 통과**) |
| `git diff --check` | 0건 |
| `pytest tests/ -q --ignore=tests/test_quality.py` | 728 passed, 8 failed — **전부 P0-0 무관**¹ |

¹ `test_telemetry.py` 5건 = **다른 세션의 WIP**(신규 파일) · `test_market_signals` FRED 2건 = 샌드박스 마운트 `PermissionError`(Windows에선 통과) · `test_jp_profile_curation` 1건 = 기존 draft 문제.
`tests/test_quality.py`는 `--ignore` (수집 단계에서 `_is_draft_profile` import 오류 — 기존 작업 트리 문제. `--deselect`로는 못 막는다).

---

## 7. 커밋 후 후속 (별도 작업, 별도 커밋)

1. **Supabase 마이그레이션 수동 적용** — SQL Editor에서 §5의 `ALTER TABLE` 3줄.
   **P0 이후 쓰기 경로를 붙이기 전에** 반드시. 적용 확인: `client.table('prediction_snapshots').select('normalization_version').limit(1).execute()` — 없으면 PostgREST 42703.
2. **`.gitattributes`** — `core.whitespace=cr-at-eol`은 이 클론에만 산다. CI/다른 클론엔 전파 안 된다.
   **전면 renormalize와 섞지 말 것.** 단독 커밋.
3. **작업 트리 쓰레기** — 루트에 깨진 리다이렉트 산물이 있다: `type`, `대상`, `목적`, `부모`, `자기소개서에`.
4. **`tests/test_quality.py`** 수집 오류 (`_is_draft_profile`) — 다른 세션 소관으로 보인다.

---

## 8. P0-1 계약 (CODEX 5차 확정)

- 파서는 `net_debt`를 **구성요소 합산과 독립된 원천**에서 수집한다.
  (구성요소를 더해서 넣으면 `reconciled`는 다시 항상 `True`가 되고 계약이 무의미해진다.)
- 엔진은 **`reconciled is True`일 때만** 정규화 값을 소비한다.
- `False`와 `None`은 **게이트 차단** 대상.
- 독립 합계를 구할 수 없으면 **임의 생성하지 말고 `None` 유지**.
- `FallbackConstant`는 P0-3에서 `ValuationInput.fallbacks: dict[str, FallbackConstant]` **독립 ledger**로 배선.
  (WACC 전용 구조에 넣으면 비-WACC 폴백 provenance를 표현할 수 없다.)

**P0-1 착수 프롬프트:**

> P0-1을 착수해줘. 파서가 net_debt와 구성요소를 독립 원천에서 수집하고,
> reconciled is True일 때만 엔진이 정규화 값을 소비하도록 구현·검증해줘.
