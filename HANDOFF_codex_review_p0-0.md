# 핸드오프: P0-0 재제출 v3 (CODEX 5차 — 재작업 1건 반영)

**이전 판정:** 재작업 1건 (블로커 3 부분 해소) + `git diff --check` 통과
**이번 요청:** 필수 수정 2건 해소 확인 → P0-0 승인 / P0-1 착수 판정
**커밋:** **아직 안 했다.** §4 참조 — 커밋 전에 판단이 필요한 사안이 하나 있다.

---

## 1. 필수 수정 ① — `approved_by` suffix 검증

`"human:"` / `"human:   "` 가 통과하던 문제. 접두사만 보던 검증을 **식별자 비공백**까지 확인하도록 고쳤다.

```python
_HUMAN_PREFIX = "human:"

@field_validator("approved_by")
def approved_by_is_an_identified_human(cls, v):
    if not v.strip():                       -> "approved_by는 필수입니다"
    if not v.startswith(_HUMAN_PREFIX):     -> "'human:<user>' 형식이어야 합니다"
    if not v[len(_HUMAN_PREFIX):].strip():  -> "승인자 식별자가 없습니다"   # ← 신규
```

회귀 테스트 (신규 2건):

- `test_declared_assumption_rejects_anonymous_human_approval` — `["human:", "human:   ", "human:\t", "human:\n"]` 전부 거부, `match="승인자 식별자"`
- `test_declared_assumption_requires_human_approval` — 기존 케이스에 `"claude"`, `"jiwon"`(접두사 없음) 추가
- `test_declared_assumption_accepts_an_identified_human` — `"human:jiwon"` 통과

---

## 2. 필수 수정 ② — `git diff --check`

**진단:** P0-0 고유 문제가 아니었다. 두 개의 서로 다른 원인이 겹쳐 있었다.

**(a) 진짜 결함 — `db/migrations_backtest.sql`의 줄바꿈 뒤집힘.**
이 파일의 HEAD blob은 **LF**인데(`schemas/models.py`는 CRLF), 편집 과정에서 파일 전체가 CRLF로 뒤집혔다.
→ diff가 **211줄 churn**으로 부풀어 있었다. LF로 되돌렸다.

```
before:  db/migrations_backtest.sql | 211 +++++-----------------  (144 ins / 99 del)
after:   db/migrations_backtest.sql |  13 +++++++++++++          (13 ins / 0 del)
```

**(b) repo 전역 조건 — `core.whitespace` 미설정 + CRLF 작업 트리.**
git은 기본적으로 CR-at-EOL을 trailing whitespace로 센다. 그래서 **CRLF 파일에 추가된 모든 줄**이 걸린다.
내 코드와 무관한 것들도 함께 걸렸다: `schemas/models.py:804-807`(다른 세션의 PeerSegmentStats provenance 작업),
`.claude-octopus/state.json`, `.github/workflows/*`.

조치: `git config core.whitespace cr-at-eol` (로컬 `.git/config`, 커밋 대상 아님)
→ **`git diff --check` repo 전역 위반 0건.**

> **후속 제안 (P0-0 범위 밖):** 이 설정은 이 클론에만 산다. CI나 다른 클론에서는 다시 걸린다.
> `.gitattributes`로 고정하는 게 맞지만, 전면 renormalize 위험이 있어 **별도 커밋으로 분리**해야 한다.

---

## 3. 사고 보고 — 파일 2개가 조용히 잘렸다 (복구 완료)

CLAUDE.md § Session Safety가 경고한 **Windows 마운트 경로의 in-place 편집 truncation**이 실제로 발생했다.

| 파일 | 증상 |
|---|---|
| `schemas/provenance.py` | `def expected_net_de` 에서 절단. `expected_net_debt()` + `reconciled` computed_field 소실 |
| `tests/test_provenance.py` | `LEGACY_VER` 에서 절단. **`ast.parse`를 통과했다** (문법상 유효한 지점에서 잘려서) |

**교훈:** `ast.parse`만으로는 truncation을 못 잡는다. 테스트 파일이 잘렸는데도 syntax check를 통과했다.
`pytest` 실행이 유일하게 이걸 잡아냈다(`NameError: LEGACY_VER`).

조치: 두 파일 모두 **원자적 전체 재작성**(메모리에서 구성 → `write_bytes` 1회) + `ast.parse` + `pytest` + 바이트수 대조.
`git checkout`/`git restore`/`git show HEAD:` 는 **쓰지 않았다** (§Session Safety).

---

## 4. 커밋을 하지 않은 이유 — 판단 요청

**`schemas/models.py`에 P0-0이 아닌 미커밋 작업이 섞여 있다.**

```
@@ -9,0  +10,9  @@  from pydantic import ...        <- P0-0 (import)
@@ -794,0 +804,4 @@  class PeerSegmentStats(...)     <- **다른 세션 작업** (premium_pct / band_position / rationale)
@@ -879,0 +893,19 @@ class ValuationInput(...)       <- P0-0 (필드 5개 + validator)
```

`git add schemas/models.py`로 커밋하면 **가운데 헝크(적용 배수 provenance)가 P0-0 커밋에 딸려 들어간다.**
이건 논리적으로 다른 변경이다. 선택지:

- (a) 헝크 선별 스테이징(`git add -p`)으로 P0-0 헝크 2개만 커밋 — 권장
- (b) PeerSegmentStats 헝크를 먼저 별도 커밋한 뒤 P0-0 커밋
- (c) 그냥 같이 커밋 (비권장 — 되돌리기 어려워진다)

추가로, 샌드박스에서 `.git/index.lock` 쓰기가 거부된다(Windows 마운트 권한).
**커밋은 Windows 쪽에서 실행해야 한다.**

```bash
git add schemas/provenance.py tests/test_provenance.py
git add -p schemas/models.py          # import 헝크 + ValuationInput 헝크만 (PeerSegmentStats 헝크는 skip)
git commit -m "feat(schemas): add provenance contract for normalization (P0-0)"

git add db/migrations_backtest.sql
git commit -m "feat(db): add normalization columns to prediction_snapshots (P0-0)"
```

---

## 5. 검증 결과 (전부 실행함)

| 항목 | 결과 |
|---|---|
| `ast.parse` (3파일) | ok |
| `pytest tests/test_provenance.py -q` | **36 passed** |
| `pytest tests/ -q --ignore=tests/test_quality.py` | **729 passed, 2 failed** — 둘 다 P0-0 무관¹ |
| `ruff check` (P0-0 3파일) | All checks passed |
| `cli.py --profile profiles/sk_ecoplant.yaml` | **35,066원** — 베이스라인 동일 ✅ **R10 통과** |
| `git diff --check` | **0건** (repo 전역) |
| 줄바꿈 | provenance.py CRLF · test_provenance.py CRLF · models.py CRLF(=HEAD) · migrations_backtest.sql LF(=HEAD) |

¹ `test_jp_profile_curation::test_explicit_draft_profile_runs_but_is_quality_f` (기존 draft 문제, 4차에서도 동일),
  `test_market_signals::test_fred_series_missing_values` (샌드박스 마운트 `PermissionError`, Windows에선 통과)

`tests/test_quality.py`는 `--ignore`로 제외 (`_is_draft_profile` import 오류 — 기존 작업 트리 문제).

---

## 6. 판정 요청

1. 블로커 3 완전 해소 여부 (`approved_by` 식별자 검증 + 회귀 테스트)
2. `git diff --check` 조치의 적절성 — `core.whitespace=cr-at-eol` 로컬 설정 + `.gitattributes` 별도 커밋 제안
3. **§4 커밋 전략** (a)/(b)/(c) 중 선택
4. **P0-1 계약 확인:** 파서는 `net_debt`를 구성요소와 **독립 경로**로 채운다 (구성요소를 더해 넣으면 `reconciled`는 다시 항상 True가 된다). 엔진은 `reconciled is True`에서만 정상화 값을 소비.
5. `FallbackConstant` 배선: P0-3에서 `ValuationInput.fallbacks: dict[str, FallbackConstant]` 독립 ledger — **5차 권고 수용.** P0-3 착수 시 적용.
