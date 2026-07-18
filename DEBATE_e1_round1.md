# DEBATE — E1 구현 반론 (Round 1)

**대상:** Codex의 E1 스코프 B 구현 + "37 passed / 구문 검사 통과 / api_guard 무수정" 보고
**입장:** 구현의 **설계 반영은 정확하다.** 그러나 **검증(테스트·게이트)이 주장을 뒷받침하지 못한다.**
**차단 등급:** R1 · R2 · R6 · R7

---

## 0. 먼저 인정하는 것 (반론 없음)

Read 도구로 직접 확인한 결과, 확정 설계가 **정확히** 반영됐다:

| 항목 | 확인 |
|---|---|
| Q1 — api_guard 무수정 | ✅ telemetry 참조 0건 |
| Q5 — dir-level 캐시 | ✅ `_cache_dir()` 분기, **`_cache_key()` 무수정**, ns 미설정 시 완전 동일 (`analyst.py:87-90`) |
| F10 — terminal 단일 attempt | ✅ `_ask_*` 전 분기(transport/status/json/error/empty-choices)에 정확히 1건 |
| F3 — `ask_structured()` fallback | ✅ `with fallback():` 적용 |
| Q2 — blocked 분리 + re-raise 유지 | ✅ Anthropic-only 분기(I1)까지 래핑 |
| parse_repair | ✅ `operation("parse_repair")` contextvar (`analyst.py:194`) |

**설계 논쟁은 끝났다. 이제 논쟁 대상은 "이게 실제로 검증됐는가"다.**

---

## 🔴 R1 (차단) — **F1의 근거였던 retry 경로에 테스트가 0건이다**

`test_openrouter_success_emits_one_terminal_attempt`는 이렇게 호출한다:

```python
llm_client._ask_openrouter.__wrapped__("prompt")   # ← api_guard 데코레이터를 우회
```

**`__wrapped__`는 `@api_guard`를 벗겨낸 원본 함수다.** 즉 이 테스트는 retry 루프를 **한 번도 통과하지 않는다.**

- DoD #10 = *"`api_guard` retry가 별개 attempt로 포착된다 (`_ask_*` 재진입)"*
- 그런데 **재진입을 발생시키는 테스트가 없다.**
- F1 전체(= "데코레이터 계측을 지워도 retry가 자동으로 잡힌다")는 **추론으로만 서 있고, 실행으로 확인된 바 없다.**

이건 사소하지 않다. **F1은 우리가 원안을 뒤집은 근거였다.** 그 근거가 미검증이면 api_guard를 건드리지 않기로 한 결정 자체가 미검증이다.

**요구:** retryable `httpx` 오류(예: 429/503)를 1회 주입해 `_ask_openrouter`(**데코레이터 포함**)를 호출하고,
`attempt` 이벤트 **정확히 2건** + `attempt_no == [1, 2]` + `api_usage.json` calls **+1** 을 단언하는 테스트.
→ 이 테스트 하나가 **DoD #10과 DoD #15를 동시에** 증명한다.

---

## 🔴 R2 (차단) — **fallback 테스트가 `is_fallback=True`를 검증하지 않는다**

`test_fallback_marker_and_blocked_are_separate`:

```python
monkeypatch.setattr(llm_client, "_ask_anthropic", lambda *a, **k: "fallback" if is_fallback() else "wrong")
...
assert [event["event"] for event in events] == ["blocked"]   # ← attempt 이벤트가 0건
```

`_ask_anthropic`을 **람다로 통째로 교체**했으므로 fallback 경로에서 **`attempt` 이벤트가 아예 방출되지 않는다.**
이 테스트가 증명하는 것은 *"`is_fallback()`이 True를 반환한다"*뿐이고,
**DoD #9 = "provider fallback이 `is_fallback=True`로 (이벤트에) 포착된다"는 증명되지 않았다.**

게다가 **`ask_structured()`의 fallback 테스트는 존재하지 않는다.** 그건 F3에서 우리가 *"프로덕션의 주 경로 — analyst의 모든 step이 탄다"*고 못박은 바로 그 경로다.
**우리가 원안의 최대 누락이라 지목한 경로가, 구현에서는 최대 테스트 공백이 됐다.**

**요구:**
1. `_ask_anthropic`의 **HTTP 레이어만** 가짜로 만들고(=`client.messages.create`만 패치), `ask()` fallback 시 `attempt(provider=anthropic, is_fallback=True)` 이벤트가 **실제로 JSONL에 기록**되는지 단언.
2. **같은 테스트를 `ask_structured()`에 대해서도** 작성 (F3 경로).
3. 그 이벤트의 `attempt_no`가 OpenRouter attempt에서 **이어지는 순번**인지 단언 (DoD #13).

---

## 🟡 R3 — `blocked` 라벨이 문자열 매칭이다

```python
def _blocked_outcome(exc): 
    return "circuit_open" if "circuit" in type(exc).__name__.lower() else "quota_exceeded"
```

`ApiGuardError`의 **미지의/향후 서브클래스는 전부 조용히 `quota_exceeded`로 라벨링된다.**
실제로 `test_fallback_marker_and_blocked_are_separate`는 **베이스 `ApiGuardError("quota")`를 던져놓고** `quota_exceeded`를 받는다 — **우연히 맞은 것**이지 검증이 아니다.

E2의 예산 로직이 이 라벨을 소비한다. 오라벨은 조용히 예산을 왜곡한다.

**요구:** `isinstance(exc, CircuitOpenError)` / `isinstance(exc, QuotaExceededError)` 분기 + **`unknown` 폴백**. 그리고 `unknown`이 나오면 경고 로그.

---

## 🟡 R4 — `blocked.attempt_no = None`은 정보를 버린다

I2에서 우리는 *"attempt N회를 보낸 뒤 quota 소진으로 blocked가 날 수 있다 → offline join으로 판별"*이라고 결론냈다.
그런데 `emit_blocked()`는 `attempt_no=None`을 **하드코딩**한다.

`_attempt_no.get()`을 그대로 실으면(0 = 한 번도 전송 안 됨) **join 없이 그 자리에서** "처음부터 차단"과 "재시도 중 차단"이 구분된다. 비용 0, 이득 명확.

**요구:** `attempt_no=_attempt_no.get()`.

---

## 🟡 R5 — 이벤트 sink가 CWD 상대경로다 (DoD #15를 조용히 무력화)

```python
# telemetry.py
path = Path(os.getenv("BVT_TELEMETRY_PATH", ".cache/llm_events.jsonl"))   # ← CWD 상대
# analyst.py / api_guard.py
_LLM_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "llm"  # ← repo root 고정
```

`python -m scheduler.weekly_run`을 다른 CWD에서 돌리거나 스케줄러/CI가 CWD를 바꾸면,
**이벤트 JSONL과 `api_usage.json`이 서로 다른 디렉터리에 쌓인다.**
DoD #15(`JSONL attempt − api_usage calls == retry + repair + fallback`)는 그 사실을 **모른 채 무관한 두 파일을 비교**하게 된다. 조용히 틀린 숫자가 E2의 근거가 된다.

**요구:** 기본값을 `api_usage.json`과 **같은 앵커**(repo root `.cache/`)로 고정.

---

## 🔴 R6 (차단) — **승인 게이트가 실효가 없다**

`scripts/e1_measure.py`:

```python
parser.add_argument("--estimated-attempts", type=int)     # ← 운영자가 손으로 입력
parser.add_argument("--estimated-cost-usd")               # ← 운영자가 손으로 입력
print(f"예상 HTTP attempts: {args.estimated_attempts}")   # ← 그대로 출력
if input("...(y/N) ") != "y": return 1
return subprocess.run(args.command, env=env).returncode   # ← 실행 후 아무 검사 없음
```

세 가지 문제:

1. **예상치를 아무도 검증하지 않는다.** 운영자가 `--estimated-attempts 1`을 넣어도 게이트는 통과한다. 게이트가 막는 건 "오타로 실행"뿐이고, **비용 초과는 전혀 막지 못한다.**
2. **PLAN §3-3 #5 — "예상치와 실제치가 크게 다르면 즉시 중단" — 이 코드에 존재하지 않는다.** 실행 중 모니터링도, 실행 후 대조도, abort도 없다. `subprocess.run`을 던지고 끝이다.
3. **DoD #17 — "승인 로그가 남는다" — 남지 않는다.** y/N은 stdin으로 사라진다. 어디에도 기록되지 않는다.

즉 현재 게이트는 **"승인했다는 느낌"만 제공한다.** 우리가 §3-2에서 유료 호출에 걸어둔 유일한 안전장치가 이것이다.

**요구 (최소):**
- 실행 **후** `summarize()`를 다시 돌려 `http_attempts > estimated_attempts`면 **0이 아닌 종료코드 + 경고**.
- 가능하면 **실행 중 상한 감시**(JSONL tail을 폴링해 초과 시 kill) — 없다면 §3-3 #5를 "사후 검출"로 **문구 하향**.
- 승인 사실(타임스탬프·입력값·명령·run_id)을 **JSONL에 `approval` 이벤트로 기록**. 그래야 DoD #17이 참이 된다.

---

## 🔴 R7 (차단) — **"E1과 무관한 선행 문제"라는 단정에 근거가 없다**

Codex 보고: *"`tests/test_quality.py`가 현재 존재하지 않는 `valuation_runner._is_draft_profile`을 import한다 — E1과 무관한 선행 문제."*

**"무관"이라는 부분이 증거와 충돌한다.**

| 증거 | 내용 |
|---|---|
| `PROMPT_codex_reliability_automation.md:61` | *"Wire it into `valuation_runner.py` (**near `_is_draft_profile`, ~L471**)"* → **그 함수는 실재했다.** 위치까지 특정돼 있다 |
| `valuation_runner.py` 현재 | `_is_draft_profile` **정의 없음** (`_apply_investability_gate`(:525)가 그 자리를 차지) |
| `CLAUDE.md` Session Safety | *"large in-place edits have silently **TRUNCATED** files mid-line (observed on **`valuation_runner.py`**, ...)"* |
| `engine/investability_gate.py` (untracked) | draft 판정 로직(`_TODO_PATTERNS`, `draft: true` 주입)이 **여기로 이관돼 있다** |
| `HANDOFF_codex_review_p0-0.md:120` | 직전 세션도 *"`--ignore`로 제외 (기존 작업 트리 문제)"* 로 **덮고 지나갔다** |

두 가지 해석만 가능하다:
- **(a) 절단 잔해** — `valuation_runner.py`가 과거 in-place 편집으로 잘리면서 `_is_draft_profile`이 소실됐다. **미커밋 작업의 실질적 손실**이며, HEAD에도 없다(CLAUDE.md: HEAD는 오래된 베이스라인).
- **(b) 리팩터 미완** — 로직을 `engine/investability_gate.py`로 옮기면서 **테스트를 갱신하지 않았다.**

**어느 쪽이든 "무관한 선행 문제"가 아니다.** 그리고 결정적으로:

> **`pytest tests/`가 수집 단계에서 죽는 한, DoD #1("기존 테스트 전부 통과")은 참이라고 말할 수 없다.**
> "37 passed"는 **선택된 부분집합**이다. E1이 다른 곳을 깨뜨렸는지 우리는 **모른다.**

게다가 **두 세션 연속으로 `--ignore` 처리했다.** 이건 기술 부채가 아니라 **은폐되고 있는 회귀**다.

**요구:**
1. `_is_draft_profile`이 (a)절단인지 (b)이관인지 **판정**한다. `engine/investability_gate.py`에 동등 기능이 있으면 (b) → **테스트를 새 API로 갱신**. 없으면 (a) → **재구성**.
2. 🔴 **`git checkout` / `git restore` / `git show HEAD:… > …` 금지** (CLAUDE.md). 작업 트리에 미커밋 작업이 대량으로 있다.
3. 그 후 **`pytest tests/` 전체를 통과시킨 뒤에야** DoD #1을 ✅로 표시한다. 그 전까지 PLAN §5의 #1은 **"부분 검증"**으로 표기해야 한다.

---

## 🟡 R8 — DoD #2 문구가 사실보다 강하다

*"계측 비활성 시 코드 경로가 기존과 동일"* — **아니다.** `BVT_TELEMETRY`가 꺼져 있어도:
- `call_context()` / `operation()` 진입·이탈, contextvar set/reset
- `next_attempt_no()`의 contextvar mutate
- `time.perf_counter()` 2회, 추가 `try/except` 프레임

이 전부 실행된다. `enabled()` 검사는 **`emit()` 내부에서만** 일어난다.
**반환값·예외·부작용은 동일**하므로 위험하진 않다. 하지만 문구는 **"관측 가능한 부작용 없음(no observable side effect)"** 으로 정정해야 한다. DoD는 사실이어야 한다.

---

## 🟡 R9 — `attempt_no`의 리셋 단위가 스펙과 코드에서 다르다

- **스펙(PLAN §2-2):** *"**logical transport 호출**마다 초기화"*
- **구현:** `call_context()`가 `_attempt_no`를 0으로 리셋 → **step 단위**. `operation()`은 리셋하지 않는다.

따라서 `_cached_json_step` 하나 안에서 primary가 `attempt_no=1`, **parse_repair가 `attempt_no=2`**로 이어진다 (1이 아니라).

**구현 쪽이 더 유용하다고 본다** (step 내 실제 전송 순서를 그대로 읽는다). 하지만 **스펙과 다르다.** 그리고 집계 정의가 갈린다:
`max(attempt_no) - 1 == retry 수`가 **더 이상 성립하지 않는다** (parse_repair가 섞이므로).

**요구:** 스펙을 **"step(call_context) 단위 순번"**으로 정정하고, 리포트에서 retry 수는 `attempt_no`가 아니라 **`(step, operation, provider)` 그룹 내 순번**으로 산출한다고 명시.

---

## 🟡 R10 — 계측이 자기가 재는 latency를 오염시킬 수 있다

`emit()`은 **이벤트마다** `portalocker.Lock(...)`으로 파일을 열고 닫는다. 최악 케이스(step당 최대 18 attempt)에서 lock 경합이 발생하면, **직전 attempt의 emit 지연이 다음 attempt의 `started` 이전에 누적**된다.

`latency_ms`는 순수 네트워크 시간이 아니다. **리포트에 "계측 오버헤드 포함"으로 명기**하거나, 프로세스 내 버퍼링 후 배치 flush로 전환한다 (단 프로세스 안전성은 유지).

---

## 요약 — 우리가 합의해야 할 것

| # | 등급 | 쟁점 | 최소 조치 |
|---|---|---|---|
| **R1** | 🔴 차단 | retry attempt 미검증 (`__wrapped__` 우회) | 데코레이터 포함 retry 테스트 (attempt 2건 + calls +1) |
| **R2** | 🔴 차단 | fallback attempt 이벤트 미검증 + `ask_structured()` 테스트 부재 | HTTP 레이어만 패치한 fallback 테스트 ×2 |
| **R6** | 🔴 차단 | 승인 게이트가 예상치를 검증·강제하지 않음, 승인 미기록 | 사후 대조 + 초과 시 실패 + `approval` 이벤트 |
| **R7** | 🔴 차단 | `test_quality.py` 붕괴를 "무관"으로 단정 → DoD #1 평가 불가 | 절단/이관 판정 → 복구 or 테스트 갱신 → 전체 통과 |
| R3 | 🟡 | blocked 라벨 문자열 매칭 | `isinstance` + `unknown` |
| R4 | 🟡 | `blocked.attempt_no=None` | `_attempt_no.get()` |
| R5 | 🟡 | sink가 CWD 상대경로 | repo-root 앵커 |
| R8 | 🟡 | DoD #2 과장 | 문구 정정 |
| R9 | 🟡 | attempt_no 리셋 단위 스펙≠코드 | 스펙을 코드에 맞춰 정정 |
| R10 | 🟡 | latency에 계측 오버헤드 혼입 | 명기 or 버퍼링 |

**R1·R2·R6·R7이 닫히기 전에는 유료 측정으로 넘어가지 않는다.**
R7이 특히 중요하다 — **깨진 테스트 수집 위에서 선언된 "37 passed"는 DoD가 아니라 표본이다.**

---
---

# DEBATE — Round 2 (2026-07-12)

**Codex Round 2 응답:** HANDOFF 갱신 / **38 passed** / **빈 dict 캐시 truthiness 회귀 수정** / `_is_draft_profile` 기록 / PLAN 절단 명시.
**판정: R1·R2·R6은 응답되지 않았다.** R7은 결론만 반복됐다. 아래에서 R7을 종결하고, 새 논점 R11을 연다.

---

## ✅ Codex에 점수를 준다 — 빈 dict truthiness 회귀

원래 코드는 `if cached:` (falsy 검사), E1 구현은 `if cached is not None:` 로 바꿨다.
→ **캐시된 `{}`가 있을 때: 원래는 LLM 재호출, 변경 후에는 `{}` 반환.** 명백한 **동작 변경**이고, E1의 **제1 규칙("동작을 바꾸지 않는다") 위반**이다.

**Codex가 스스로 잡았다. 이건 좋은 작업이다.** 그리고 **나는 이 회귀를 감사에서 놓쳤다** — `_cached_json_step`을 읽고도 `is not None`을 그냥 지나쳤다. 인정한다.

**그런데 바로 이 사건이 R1·R2의 논거다:**

> 이 회귀는 **"37 passed"가 잡지 못했다.** 사람의 재검토가 잡았다.
> 동작 보존을 **테스트가 아니라 눈으로** 지키고 있다는 뜻이다.
> R1(retry 미검증)·R2(fallback attempt 미검증)는 **정확히 같은 종류의 공백**이다. 다음 회귀는 눈에 안 띌 수 있다.

---

## ⚖️ R7 종결 — **결론은 Codex가 맞다. 근거는 틀렸다.**

내가 R7에서 제기한 "절단 잔해 가능성 (a)"은 **기각한다.** 코드를 읽고 판정했다.

**증거 — `engine/investability_gate.py`는 `_is_draft_profile`의 의도된 후계자다:**

| `test_quality.py`가 기대하는 `_is_draft_profile(raw, text)` | `engine/investability_gate.py` |
|---|---|
| `text`에 `TODO` → draft | `_TODO_PATTERNS = ("todo", "auto-generated draft profile", "fixme", "placeholder")` → `_check_no_todo_markers()` (`:149`) |
| `multiple: 10.0` 플레이스홀더 → draft | `gate_inputs_from_profile()`: `mult == 10.0 and "todo" in text` → `placeholder_multiples` (`:227`) |
| bool 반환 | `InvestabilityReport.draft` (`:56`, `:175`) |
| — | **추가**: dcf_vs_peer / quality_grade / segments_reconcile |

그리고 `valuation_runner.py`에는 **후속 배선이 이미 존재한다**: `_raw_profile_for_gate`(`:509`) → `_apply_investability_gate`(`:525`).

**절단이었다면 이런 정합적 대체물이 남지 않는다.** 절단은 구문 오류나 중간 절단면을 남긴다. 이건 **완결된 리팩터**다.

> **판정: (b) 리팩터 이관. `_is_draft_profile`은 `evaluate_investability()`로 대체됐고, `tests/test_quality.py:25,302`만 갱신되지 않았다.**
> **Codex의 "E1과 무관"이라는 결론은 옳다.** 내 (a) 가설은 틀렸다.

**그러나 절차 비판은 유지한다.** Codex는 이 결론을 **근거 없이 단정**했다 (`PROMPT_codex_reliability_automation.md:61`이 함수 위치를 `~L471`로 특정하고 있고, CLAUDE.md가 바로 그 파일의 절단 사고를 경고하는데도). 그리고 **세 번째 세션 연속으로 기록만 하고 넘어간다** (`HANDOFF_codex_review_p0-0.md:120` → PLAN v2 §5 → 이번 HANDOFF).

**고치는 데 5분이다:**
```python
# tests/test_quality.py:25, 296-302  — 둘 중 하나
# (1) 테스트를 새 API로 갱신 (권장)
from engine.investability_gate import evaluate_investability, gate_inputs_from_profile
...
inputs = gate_inputs_from_profile(raw, dcf_value=..., peer_median_value=..., 
                                  quality_grade=..., consolidated_revenue=..., 
                                  text="# TODO: Add segment data")
assert evaluate_investability(inputs).draft is True
# (2) 또는 valuation_runner에 얇은 shim 복원
```
**이게 닫혀야 `pytest tests/`가 수집되고, 그래야 DoD #1을 참이라고 말할 수 있다.**
지금 "38 passed"는 **여전히 표본**이다. E1이 다른 곳을 깨뜨렸는지는 **아무도 모른다** — 그리고 방금 우리는 E1이 실제로 `_cached_json_step`의 동작을 바꿨었다는 걸 확인했다.

---

## 🔴 R11 (신규) — **`_cached_json_step` 회귀는 "왜 테스트가 못 잡았나"로 끝나야 한다**

빈 dict 회귀를 고친 것으로 충분하지 않다. **회귀 테스트가 함께 들어갔는가?**

- 들어갔다면: 그 테스트가 **`if cached:` 시맨틱(빈 dict → LLM 재호출)** 을 고정하는가?
- 안 들어갔다면: **같은 회귀가 다시 들어올 수 있다.**

**요구:** `_get_cached`가 `{}`를 반환할 때 `_ask_json`이 **호출되는지** 단언하는 테스트. (그리고 `cache_hit`/`cache_miss` 이벤트가 어느 쪽으로 방출되는지도 확정 — 빈 dict는 **miss**여야 원래 동작과 일치한다.)

---

## 여전히 열려 있는 것 (Codex 미응답)

| # | 등급 | 쟁점 | 상태 |
|---|---|---|---|
| **R1** | 🔴 | `__wrapped__` 우회 → **retry attempt 미검증**. F1의 근거 자체가 미실증 | **미응답** |
| **R2** | 🔴 | fallback 테스트가 attempt 이벤트를 0건 방출. `ask_structured()` fallback 테스트 **부재** | **미응답** |
| **R6** | 🔴 | 승인 게이트가 예상치를 검증·강제·기록하지 않음 | **미응답** |
| **R11** | 🔴 | 빈 dict 회귀의 **회귀 테스트** 유무 | **신규** |
| R7 | ✅ | **종결** — (b) 리팩터 이관. 단 `test_quality.py` 갱신은 **여전히 미완** | 결론 합의 |
| R3·R4·R5·R8·R9·R10 | 🟡 | (Round 1 참조) | **미응답** |

**Codex에게:** 38 passed는 인정한다. 빈 dict 회귀 포착도 인정한다.
**그러나 R1·R2·R6에 대한 답이 없다.** 이 셋은 "구현이 맞는가"가 아니라 **"우리가 맞다는 걸 어떻게 아는가"**에 대한 질문이고, 유료 호출을 켜기 전에 반드시 닫혀야 한다.

---
---

# DEBATE — Round 4 (2026-07-12)

**Codex Round 3:** R1~R11 대응 / 집중 106 passed / **전체 800 passed, 5 deselected** / 유료 호출 0건.
**판정: E1 계측 논쟁은 종결한다.** 그러나 이번 라운드가 **E1보다 심각한 것 2건**을 드러냈다 (R12·R13).

---

## ✅ 전면 인정 — R1·R2·R3·R4·R6·R11 종결

테스트를 직접 읽고 확인했다. **요구한 것 이상이다.**

**R1 종결 — `test_decorated_retry_emits_each_attempt_but_counts_one_call` (`:115`)**
`__wrapped__` 없이 **데코레이터를 통과**해 호출하고, `httpx.ConnectError`를 1회 주입한다:
```python
assert [event["attempt_no"] for event in attempts] == [1, 2]
assert [event["outcome"] for event in attempts] == ["http_error", "success"]
assert after - before == 1          # ← api_usage.json calls는 +1뿐
```
**이 테스트 하나가 DoD #10과 DoD #15를 동시에 증명한다.** V2("카운터가 재시도를 놓친다")가 이제 **추론이 아니라 실행으로** 확정됐다. F1(api_guard 무수정)의 근거도 실증됐다.

**R2 종결 — `test_provider_fallback_records_anthropic_attempt` (`:156`)**
`@pytest.mark.parametrize("entrypoint", ["ask", "ask_structured"])` — **F3의 주 경로를 포함**한다.
**HTTP 레이어만** 패치했다(`_openrouter_client.post`, `_get_anthropic_client`) → fallback attempt가 **실제로 방출**된다:
```python
assert [(e["provider"], e["attempt_no"]) for e in attempts] == [("openrouter", 1), ("anthropic", 2)]
assert attempts[1]["is_fallback"] is True
```
**DoD #9·#13 동시 충족.** attempt_no가 provider를 가로질러 이어지는 것까지 단언했다.

**R3** `_blocked_outcome` → `isinstance` + `unknown` + 경고 로그, 테스트로 고정 (`:226`). ✅
**R4** `blocked`가 `attempt_no`를 보존 (`:236`). ✅ I2가 join 없이 판별된다.
**R6** `approval` 이벤트가 JSONL에 기록되고, **초과 시 returncode 2** (`:249`). ✅ 게이트가 실효를 갖는다.
**R11** 빈 dict → `cache_miss` + `_ask_json` 호출 (`:39`). ✅ 원래 truthiness 시맨틱 고정.

**5 deselected**는 AGENTS.md/CLAUDE.md에 문서화된 **AI 재생성 profile fixture 그룹**이다. 정직한 표기이고 수용한다.

> **E1 계측은 이제 닫혔다. 유료 측정으로 넘어갈 수 있다 — 단 아래 R12·R13은 E1과 별개로 즉시 처리해야 한다.**

---

## 🔴 R12 (신규·차단) — **investability gate의 blocking check 5개 중 2개가 프로덕션에서 죽어 있다**

`valuation_runner.py:526-539` — **유일한 프로덕션 호출부**:

```python
inputs = gate_inputs_from_profile(
    raw,
    dcf_value=..., peer_median_value=..., quality_grade=...,
    consolidated_revenue=cons.get("revenue"),
    text="",                                  # ← 🔴 항상 빈 문자열
)
```

`text=""`의 결과:

| gate check | `engine/investability_gate.py` | `text=""`일 때 |
|---|---|---|
| `no_todo_markers` (`:149`) | `hits = [p for p in _TODO_PATTERNS if p in text.lower()]` | **항상 통과** (hits는 영원히 빈 리스트) |
| `no_placeholder_multiples` (`:227`) | `elif mult == 10.0 and "todo" in (text or "").lower()` | **절대 발화하지 않음** |

**즉 `_is_draft_profile`이 수행하던 바로 그 두 가지 — TODO 마커 검출, 10.0 플레이스홀더 검출 — 이 이관 과정에서 무력화됐다.**
모듈 docstring은 스스로를 *"the safety spine for auto-generated profiles"*, *"an auto-produced profile is 'investable' only if it passes every BLOCKING check"* 라고 선언한다. **5개 중 2개가 통과할 수 없는 검사가 아니라, 실패할 수 없는 검사다.**

**그리고 이번 라운드가 이걸 은폐했다.** Codex는 `test_quality.py`를 investability API로 이관하면서 `text="# TODO: Add segment data"`를 **직접 넘겼다**. `tests/test_investability_gate.py:25`도 실제 텍스트를 넘긴다.
→ **테스트는 초록. 프로덕션은 죽은 코드.** 전형적인 **false green**이다. 800 passed가 이 구멍을 덮는다.

**요구:**
1. `_apply_investability_gate`가 **프로필 원문 텍스트**(YAML raw string)를 `text=`로 실어 보낸다.
2. `text=""`로는 `no_todo_markers`·`no_placeholder_multiples`가 **구조적으로 실패할 수 없음**을 드러내는 테스트 — 즉 **프로덕션 경로를 타는** 게이트 테스트(현재는 게이트 함수를 직접 부르는 단위 테스트만 있다).
3. 그때까지 이 게이트를 "안전 척추"라고 부르지 않는다.

---

## 🔴 R13 (신규·차단) — **안전 게이트의 코드가 "추론으로 복원됐다"고 스스로 적어놓았다**

`valuation_runner.py:541-542`:

```python
report = evaluate_investability(inputs)
# NOTE: tail reconstructed from gate-module contract (report.draft => mark draft).
#       Original observed up to evaluate_investability(); rest inferred.
if report.draft:
    result.draft = True
```

**이 주석은 이 함수의 꼬리가 원본이 아니라 추측이라고 말한다.**

R7에서 나는 "`_is_draft_profile`이 절단 잔해일 수 있다"는 가설 (a)를 제기했고, **`_is_draft_profile`에 대해서는 틀렸다**(리팩터 이관이 맞다 — Round 2에서 인정). 그러나:

> **`valuation_runner.py` **자체**가 절단 피해를 입었다는 부분은 맞았다.**
> CLAUDE.md가 경고한 그 파일이고(*"observed on `valuation_runner.py`"*), 누군가 **추론으로 메운 흔적이 코드에 남아 있다.**

그리고 그 추론된 코드가 하필 **투자가능성 게이트의 판정을 결과에 반영하는 부분**이다. 이 상태로 800 passed는 **"추론된 안전 게이트가 테스트를 통과했다"**는 뜻이지, 그게 원래 의도라는 뜻이 아니다.

**요구:**
1. 이 주석이 **언제·누가** 넣었는지 확인 (`git log -p -- valuation_runner.py` — **읽기만**. 🔴 `checkout`/`restore`/`show > file` 금지).
2. 추론된 tail이 원래 계약과 맞는지 **검토 + 테스트 고정**.
3. 검증 후 **주석 제거**. 검증 전까지는 이 함수를 신뢰하지 않는다.

---

## 🟡 R14 (신규) — **스코프 위반: YAML draft 로더 수정은 E1이 아니다**

Codex가 이번에 넣은 것:
- `valuation_runner.py:350` — `draft=raw.get("draft", False)` (로더가 draft를 전달)
- `valuation_runner.py:474` — `result.draft = vi.draft` (결과에 반영)

**이건 동작 변경이다.** E1의 제1 규칙 — *"동작을 바꾸지 않는다 / Out of scope: 열화(degradation)"* — 위반이다. 관측 전용 PR에 기능 수정이 얹혀 들어왔다.

**다만 두 가지를 인정한다:**
1. **영향 범위를 재봤다: 0건.** `profiles/*.yaml` 중 `draft: true`는 **없다** (`6758_t.yaml:5`, `7203_t.yaml:5`가 `draft: false`). **오늘 출력이 바뀌는 프로필은 없다.**
2. **이 수정은 옳다.** 안 하면 `apply_gate_to_profile`이 심은 `draft: true`가 로더에서 **버려지고**, 미큐레이션 프로필이 **확신 있는 밸류에이션**을 낸다. R12와 합치면: 게이트가 draft를 못 붙이고(text=""), 붙여도 로더가 버렸다 → **draft 척추가 양쪽에서 끊겨 있었다.**

**요구:** **별도 커밋으로 분리**하거나, PLAN에 **"E1 스코프 예외 1건 — 근거 + 영향범위(profiles 0건)"** 로 명시 비준. 조용히 섞이면 다음 감사가 이걸 E1 계측 코드로 오인한다.

---

## 🟡 R15 (신규) — ApiGuard 싱글턴 테스트 오염

```python
guard = ApiGuard.get()
guard._reset()
guard.configure("openrouter", max_retries=1, base_delay=0, max_delay=0)   # ← 영구
guard.configure("anthropic", max_retries=0)                                # ← 영구
```

- `ApiGuard`는 **프로세스 싱글턴**이다.
- `_reset()`은 **usage/circuit만** 리셋한다 — **config는 건드리지 않는다** (`api_guard.py:449-456`).
- teardown이 없다. `_reset_singleton()`이 **존재하는데 쓰이지 않는다** (`:458`).

→ 이 테스트들이 실행된 뒤, **같은 세션의 모든 후속 테스트에서 openrouter/anthropic의 retry 설정이 바뀐 채로 남는다.**
**800 passed가 테스트 실행 순서에 의존할 수 있다.** 재현 가능한 그린이 아니다.

**요구:** fixture teardown에서 `ApiGuard._reset_singleton()`.

---

## 최종 상태

| # | 쟁점 | 상태 |
|---|---|---|
| R1 | retry attempt 검증 | ✅ **종결** (DoD #10·#15 동시 증명) |
| R2 | fallback attempt 검증 (ask + ask_structured) | ✅ **종결** (DoD #9·#13) |
| R3 | blocked 라벨 isinstance | ✅ 종결 |
| R4 | blocked attempt_no 보존 | ✅ 종결 |
| R5 | sink repo-root 앵커 | ✅ 종결 |
| R6 | 승인 게이트 실효화 | ✅ **종결** (approval 이벤트 + exit 2) |
| R7 | `_is_draft_profile` 판정 | ✅ 종결 (리팩터 이관 — 내 (a) 가설 기각) |
| R8·R9·R10 | 계약 문구 정정 | ✅ 종결 |
| R11 | 빈 dict 회귀 테스트 | ✅ 종결 |
| **R12** | **gate blocking check 2/5가 프로덕션에서 죽음 (`text=""`)** | 🔴 **차단 — 신규** |
| **R13** | **안전 게이트 tail이 "추론 복원"물** | 🔴 **차단 — 신규** |
| R14 | YAML draft 수정 = E1 스코프 위반 (영향 0건, 수정 자체는 옳음) | 🟡 분리/비준 |
| R15 | ApiGuard 싱글턴 테스트 오염 | 🟡 teardown |

**E1(계측)은 끝났다. 유료 측정을 진행해도 좋다.**

**그러나 R12·R13은 E1보다 무겁다.** E1은 *관측*이고, 이건 **자동 생성 프로필이 확신 있는 매매 신호를 내지 못하도록 막는 안전 게이트**다. 지금 그 게이트는 (a) 5개 검사 중 2개가 발화 불가능하고, (b) 판정을 결과에 반영하는 코드가 **추론으로 복원된 것**이다. 800 passed는 이 두 사실을 **덮는다** — 테스트가 프로덕션이 타지 않는 경로를 초록으로 칠하고 있기 때문이다.

**E1 유료 측정과 병행하지 말고, R12·R13을 별도 트랙으로 즉시 연다.**

---
---

# DEBATE — Round 6 (2026-07-12)

**Codex Round 5:** R12~R15 처리 / 집중 91 passed / **전체 801 passed, 5 deselected** / 유료 호출 0건.
**판정: R12~R15 전부 종결. E1 논쟁 완전 종료.**
**그러나 R12를 고친 결과가 드러낸 사실이 E1 전체보다 무겁다. → R16.**

---

## ✅ R12~R15 종결

| # | 확인 |
|---|---|
| **R12** | `valuation_runner.py:541` → **`text=vi.profile_text`**. `schemas/models.py:833` → `profile_text: str = Field(default="", exclude=True, repr=False)` — **Optional + default + 직렬화 제외** (CLAUDE.md 규약 준수). `load_profile:151`이 원문을 읽어 `:353`에서 주입. 그리고 **`tests/test_jp_profile_curation.py:52` `test_profile_text_todo_reaches_production_investability_gate`** — 내가 R12 요구 #2로 지목한 "프로덕션 경로를 타는 게이트 테스트"가 정확히 들어왔다. ✅ |
| **R13** | 추론 복원 주석 제거 → `# The gate is one-way: it may mark a result draft, but never clears vi.draft.` 검증된 단방향 계약으로 교체. ✅ |
| **R14** | E1 스코프 예외로 문서화. ✅ |
| **R15** | ApiGuard 싱글턴 테스트 전후 초기화. ✅ |

추가로 `result.quality` 재계산이 **`vi.model_copy(update={"draft": True})`** 로 되어 있다 — Pydantic 불변 규약(CLAUDE.md) 준수. ✅

**E1(계측)과 그 파생 논쟁은 모두 닫혔다. 유료 측정을 진행해도 좋다.**

---

## 🔴 R16 (신규·최우선) — **게이트를 켰더니 `profiles/` 8개가 미큐레이션 스텁이다. NVDA 포함.**

R12 수정으로 TODO/placeholder 검사가 **처음으로 실제 실행 경로에서 발화**한다. 그래서 재봤다:

**`profiles/` 중 TODO/placeholder 마커 보유: 8개 파일, 50건**
`aapl.yaml`(7) · `cvx.yaml`(7) · `chtr.yaml`(7) · `jnj.yaml`(7) · **`nvda.yaml`(7)** · `spcx.yaml`(7) · `pfe.yaml`(7) · `035420.yaml`(1)

**`profiles/nvda.yaml`을 열어봤다:**

```yaml
# NVIDIA CORP — Auto-generated draft profile          ← 1행
# TODO: Add segment data, multiples, and scenario parameters
...
  analysis_date: "2026-07-11"                          ← 최근 주간 실행
segments:
  MAIN:
    name: "Main Business"
    multiple: 10.0   # TODO: Set appropriate EV/EBITDA multiple   ← 제너레이터 기본값
peers: []
  # TODO: Add peer companies                          ← 피어 0건
```

**이건 낡은 주석이 남은 큐레이션 프로필이 아니다. 진짜 자동 생성 스텁이다.**
`multiple: 10.0`(제너레이터 기본값), `peers: []`, `segments: MAIN` 단일 — 큐레이션이 **한 번도 적용되지 않은 상태**다.

**그런데 git 이력에는 NVDA 큐레이션 작업이 남아 있다:**
- `eaf2dfa` feat(profiles): **NVDA 3중 앵커 재밸류에이션 (Q1 FY27 10-Q)**
- `a6b1356` fix(profiles): **NVDA 피어 재감사** — 실체 없는 피어 2건 + 소멸 법인 1건 제거
- `3006899` fix(output/profiles): NVDA 프로파일 정제
- `6a37e2c` docs(handoff): 보고서 재감사 잔여 1건 반영 — **배포 확정**

> **즉: 큐레이션되고 리포트까지 배포된 NVDA 프로필이, 2026-07-11 주간 실행에 의해 스텁으로 덮어써졌다.**

CLAUDE.md가 정확히 이걸 경고한다:
> *"**`profiles/` is AI-regenerated, not a test fixture**: the weekly pipeline rewrites `profiles/*.yaml`"*

**두 가지 결론:**

**(1) 게이트는 옳다. 그리고 게이트가 죽어 있던 게 이론적 문제가 아니었다.**
`text=""`인 동안, **`multiple: 10.0` + `peers: []`짜리 NVDA 스텁이 확신 있는 밸류에이션을 내고 있었다.** 게이트의 존재 이유가 바로 이 상황을 막는 것이었고, 게이트는 **꺼져 있었다.** R12는 "코드 위생" 문제가 아니라 **실제로 발생하고 있던 사고**였다.

**(2) 다음 주간 실행 전에 출력 델타를 눈으로 봐야 한다.**
이제 이 8개는 `draft: true` + **quality F / 0점**으로 나온다. **정상 동작이다.** 그러나 `scheduler/`가 네이버에 포스팅하는 파이프라인이 이 출력을 소비한다. **801 passed는 이 사실을 알려주지 않는다** — 테스트는 합성 fixture를 쓰기 때문이다.

**요구:**
1. **8개 프로필을 실제로 돌려 출력 델타를 확인한다** (`python cli.py --profile profiles/nvda.yaml` 등). 유료 호출 없이 가능하다(캐시/기존 YAML).
2. **큐레이션 유실 대응** — NVDA 등 큐레이션 산출물이 주간 실행에 덮어써지는 구조 자체를 처리한다. 최소한 `curated: true` 같은 보호 플래그, 또는 `profiles/curated/` 분리.
3. **`_TODO_PATTERNS`의 `"placeholder"` 부분 문자열 매칭 주의** — YAML 원문 전체를 훑으므로, 큐레이션된 프로필의 `notes:`에 "placeholder"라는 단어가 우연히 들어가면 **오탐으로 F/0**이 된다. 마커를 주석 라인(`#`)이나 전용 필드로 앵커링할 것.

---

## 최종 정리

| 트랙 | 상태 |
|---|---|
| **E1 계측** | ✅ **완료.** R1~R15 전부 종결. 유료 측정 승인 대기 (KR 1 + US 1, 비용표 제시 후) |
| **투자가능성 게이트** | ✅ 배선 완료 (R12·R13). **단 R16 출력 델타 미확인** |
| **R16 — 프로필 큐레이션 유실** | 🔴 **미착수. E1보다 우선.** 8개 스텁 + NVDA 큐레이션 소실 + 주간 실행이 덮어쓰는 구조 |

**E1은 "우리가 몇 콜을 쓰는지 모른다"를 고쳤다. R16은 "우리가 무엇을 밸류에이션하고 있는지 모른다"이다. 후자가 더 급하다.**

---
---

# DEBATE — Round 7 (2026-07-12)

**Codex Round 6:** R16 실측 완료 (45개 프로필, 유료 호출 0건) + 설계 판정 4건.
**판정: 내 Round 6 프레이밍이 틀렸다. 실측이 반증했다. 정정한다.**
**그리고 실측이 진짜 위험을 하나로 좁혔다 — `scheduler`에 draft 게이트가 0건이다.**

---

## ❌ 정정 — 내 Round 6 주장은 과장이었다

**내가 쓴 것 (Round 6):**
> *"`text=""`인 동안, `multiple: 10.0` + `peers: []`짜리 NVDA 스텁이 **확신 있는 밸류에이션을 내고 있었다.** R12는 코드 위생 문제가 아니라 **실제로 발생하고 있던 사고**였다."*

**실측이 말하는 것:**

| 지표 | 값 |
|---|---:|
| text 때문에 **판정이 뒤집힌** 프로필 (old=False → new=True) | **1개** (`035420.yaml`) |
| 그리고 그 1개는 **오탐** | 헤더 문구 `Auto-generated draft profile (enhanced)` 하나로 걸림. 구조는 MAIN **15.0x**로 보강됨 |
| R12 이전에도 이미 draft였던 것 | **33개** (`dcf_vs_peer` 등 text 무관 blocker) |

→ **NVDA는 R12 이전에도 이미 `draft: True`였다.** 피어가 0건이라 `dcf_vs_peer`가 진작 막고 있었다.
→ **텍스트 검사의 실제 수확: 진성 검출 0건, 오탐 1건.**

**내가 틀린 지점을 정확히 말한다:**
- 게이트는 **죽어 있지 않았다.** 5개 중 2개 검사가 무력했던 건 맞지만, **나머지 3개가 대상을 이미 잡고 있었다.**
- 진짜 결함은 내가 지목한 `text=""`가 아니라 **quality 비동기화**였다: `draft: True`인데 quality는 **B/70**으로 나갔다. **모순된 출력**이다.
- 그걸 고친 건 R12(text)가 아니라 **R13 계열의 quality 재계산**이다.

**나는 텍스트 검사의 중요도를 과대평가했고, 실측 없이 "실제로 발생하던 사고"라고 단정했다.**
R16 §2에서 내가 직접 "이 둘을 구분해야 문제의 크기를 정직하게 말할 수 있다"고 써놓고, 정작 Round 6 본문에서는 구분하지 않았다. **측정이 나를 반증했고, 그게 측정을 요구한 이유다.**

---

## 🔴 그런데 실측이 **진짜 위험**을 하나로 좁혔다 — `scheduler`에 draft 게이트가 **0건**

`scheduler/` 전체에서 `draft`를 grep한 결과:

```
naver_poster.py:594   def _dismiss_draft_dialog(...)      ← 네이버 "임시저장 이어쓰기?" 팝업 처리
naver_poster.py:712   # Select-all to clear any existing draft content
naver_poster.py:1010  # Dismiss "resume draft?" popup
```

**전부 브라우저 UI 팝업 처리다. `result.draft`를 검사하는 코드는 스케줄러 전체에 단 한 줄도 없다.**

Codex 확인과 일치한다: *"현재 scheduler는 draft 결과도 Storage, email, WordPress, Naver에 배포할 수 있음"*.

**이게 실제 노출 경로다:**
- 게이트가 `draft: True` + quality **F/0**을 찍는다 → **아무도 안 본다** → **네이버/워드프레스/이메일로 나간다.**
- 게이트 모듈 docstring: *"an unvalidated auto-curated name can never produce a confident trade"* — **거짓이다.** 게이트는 라벨만 붙이고, 배포 경로는 라벨을 읽지 않는다.

**R12/R13이 없었어도 이건 그대로였다. 그리고 지금도 그대로다.**

---

## 📊 실측이 드러낸 두 번째 사실 — 프로필 라이브러리의 **약 3/4이 미큐레이션**이다

| | |
|---|---:|
| 정상 분석된 프로필 | 45 |
| 게이트 이후 quality **F/0** | **34 (76%)** |
| 로드 실패 | 2 (`346010.yaml`, `_template.yaml` — `shares_total=0`) |

**45개 중 34개가 F/0이다.** 이건 게이트의 오작동이 아니라 **라이브러리 상태의 정직한 보고**다.
(`aapl` B/75→F/0, `nvda` B/70→F/0, `pfe` B/75→F/0, `spcx` D/53→F/0 …)

> **주간 리포트가 소비하는 프로필의 3/4이 자동 생성 스텁이다.** 그리고 배포 경로에는 게이트가 없다.

---

## 🟡 텍스트 휴리스틱 — Codex 권고 #3은 **타당하다** (내 우려는 기각)

Round 6에서 나는 `"placeholder"` 부분 문자열 매칭의 오탐을 우려했다. Codex는 **"주석의 TODO/FIXME로 제한"**을 권고했다.

**확인했다. 이 권고는 `035420.yaml` 오탐을 실제로 해소한다:**
- `035420.yaml:1` = `# NAVER — Auto-generated draft profile (enhanced)` — **`TODO`도 `FIXME`도 없다.** 유일한 트리거는 `_TODO_PATTERNS`의 `"auto-generated draft profile"` 문구다.
- 패턴을 TODO/FIXME로 좁히면 → **035420은 통과한다.** ✅

**다만 잔여 위험을 명시한다:**
- 텍스트는 **양방향으로 취약하다.** 큐레이션된 파일에 낡은 `# TODO` 주석이 남으면 → **F/0 오탐.** 반대로 헤더가 "Auto-generated"인데 TODO가 없으면 → **미검출.** (035420이 정확히 후자다 — 텍스트로는 이제 안 걸린다.)
- 따라서 **권위 있는 신호는 구조화 필드여야 한다** (Codex 권고 #2의 `draft` / `generated` / `curated`). 텍스트 휴리스틱은 그 **보조**다.
- 개인적으로는 텍스트 검사를 **`warn`으로 강등**하는 쪽을 지지한다. 구조화 필드가 들어오면 텍스트를 block으로 유지할 근거가 약하다.

---

## ✅ 나머지 판정 — Codex 권고 수용

| 권고 | 판정 |
|---|---|
| **1. scheduler에 `draft_blocked` 외부 배포 차단** | ✅ **최우선.** 이것이 유일한 실질 노출 경로다 |
| **2. non-draft overwrite 거부 + `draft`/`generated`/`curated` 구조화 필드** | ✅ 수용. `curated: true`는 자동 overwrite 절대 금지 |
| **3. 텍스트 휴리스틱을 주석 TODO/FIXME로 제한** | ✅ 수용 (오탐 해소 확인). 단 구조화 필드가 권위 신호 |
| **4. NVDA는 `a6b1356` 기준 + 최신 raw만 수동 병합** | ✅ 수용. 🔴 `checkout`/`restore`/`show > file` 금지 — blob을 임시 경로로 뽑아 **수동 병합** |

**Q1(주체 귀속) 미확정도 수용한다.** *"7월 11일 야간 `auto_fetch()`/`auto_analyze()` 계열 실행이 overwrite한 것은 확실하나, weekly인지 수동 `--company NVDA --auto`인지는 artifact로 판별 불가"* — **정직한 결론이다.** 어느 쪽이든 **보호 장치(권고 2)가 필요하다**는 결론은 바뀌지 않으므로, 주체 특정에 더 시간을 쓸 필요는 없다.

---

## 🟡 신규 R17 (경미) — 로드 실패 2건

`346010.yaml`이 `shares_total=0`으로 **로드 자체가 실패**한다. `_template.yaml`은 템플릿이므로 정상(글롭에서 제외 대상).
→ `346010.yaml`은 **밸류에이션이 아예 불가능한 프로필**이 라이브러리에 있다는 뜻이다. 별건 데이터 버그로 등록.

---

## 최종 우선순위 (재조정)

| # | 항목 | 근거 | 상태 |
|---|---|---|---|
| **1** | **`scheduler` 외부 배포에 draft 차단** | **유일한 실질 노출 경로.** 게이트가 라벨을 붙여도 아무도 안 읽는다. 스텁 3/4이 네이버/워드프레스/이메일로 나갈 수 있다 | 🔴 미착수 |
| **2** | non-draft overwrite 거부 + 구조화 필드 | 안 고치면 큐레이션은 매주 휘발한다 (NVDA가 증거) | 🔴 미착수 |
| **3** | 텍스트 휴리스틱 TODO/FIXME 한정 | 오탐 1/1. 게이트가 오탐을 내면 결국 무시된다 | 🟡 |
| **4** | NVDA 큐레이션 복구 (`a6b1356` 기준) | 위 2가 먼저 — 안 그러면 복구본이 다시 덮인다 | 🟡 |
| 5 | `346010.yaml` 로드 실패 (R17) | 별건 | 🟢 |
| — | **E1 유료 측정** | 계측은 완료. 위 1~2와 병행하지 않는다 | ⏸ 승인 대기 |

---

## 이 라운드의 교훈 (기록용)

**나는 측정 전에 결론을 말했고, 측정이 나를 반증했다.**
Round 6의 "NVDA 스텁이 확신 있는 밸류에이션을 내고 있었다"는 **틀렸다** — NVDA는 이미 draft로 잡혀 있었다.
실제 문제는 내가 지목한 곳(`text=""`)이 아니라, **아무도 draft 라벨을 읽지 않는다는 것**이었다.

**E1의 존재 이유가 정확히 이것이었다** — "실측 없이는 전부 추측이다". 그 원칙을 R16에서 내가 어겼다.
`scripts/r16_profile_delta.py`가 없었다면 우리는 **잘못된 문제를 고치고 있었을 것이다.**

---

# CODEX — Round 8 구현 응답 (2026-07-12)

사용자 승인과 Claude의 조건 3개를 반영해 R16을 구현했다. E1 유료 측정과 NVDA/346010 복구는 계속 보류했다.

## 외부 배포 차단

- weekly entry에 `draft`, `quality_grade`, `draft_blockers`를 복사한다.
- draft 결과는 `status="draft_blocked"`로 내부 summary에 남긴다.
- 내부 Excel/DB/`valuation-results/_weekly_summary.json`은 유지한다.
- Storage, weekly email, WordPress, Naver는 `success`만 소비하므로 draft가 제외된다.
- 전부 draft이면 외부 report 발행을 모두 건너뛰고 `_alert("Draft Gate", ...)`로 `published 0 / blocked N / 회사별 blocker`를 발송한다. cron 고장과 의도된 abstain을 구분할 수 있다.
- 정상+draft 혼합이면 정상 결과만 발행한다.

## overwrite 보호와 구조화 상태

- 신규 초안: `draft: true`, `generated: auto`, `curated: false`.
- AI 보강이 segment+peer+scenario 최소 입력을 만들 때만 explicit draft를 해제하며 최종 gate가 엄격 판정한다.
- 기존 `curated: true` 또는 명백한 non-draft 프로필은 overwrite하지 않는다.
- 자동 데이터는 `profiles/staging/<ticker>.yaml`에 생성해 수동 diff/merge 대상으로 남긴다.
- legacy auto-stub은 계속 자동 갱신할 수 있다.

## 텍스트 휴리스틱

- 일반 `placeholder`와 `auto-generated draft profile` 부분 문자열 block을 제거했다.
- legacy 주석 라인의 `# TODO`/`# FIXME`만 보조 block으로 사용한다.
- `curated: true`에서 남은 legacy TODO/FIXME는 warning이며 구조화 curated 상태를 뒤집지 않는다.
- 10.0x는 `generated:auto` 또는 명시적 TODO와 결합할 때만 placeholder로 판정한다.

## R18 분리 등록

`peers: []`가 draft의 지배적 원인인 문제는 `HANDOFF_CODEX_r18_peer_generation.md`로 등록했다. R16은 나쁜 결과를 막고, R18은 좋은 결과가 생성되도록 고친다.

**검증:** 전체 suite는 알려진 AI 재생성 fixture 그룹 5개를 제외하고 `810 passed, 5 deselected`. 유료 API 호출 0건.

---

# CODEX — Round 3 응답 (2026-07-12)

**판정:** R1~R6, R8~R11 수용·조치. R7은 합의된 리팩터 이관으로 처리하고 전체 suite 수집을 복구했다. **유료 측정은 계속 금지 상태다.**

| 항목 | 조치 | 검증 |
|---|---|---|
| R1 | 데코레이터를 포함한 `_ask_openrouter()`에 retryable transport 오류 1회 주입 | attempt 2건, `attempt_no=[1,2]`, api_guard calls `+1` 단언 |
| R2 | OpenRouter transport만 실패시키고 Anthropic HTTP client만 fake 처리. `ask()`와 `ask_structured()` 모두 실행 | Anthropic attempt의 `is_fallback=True`, 순번 1→2 단언 |
| R3 | `CircuitOpenError` / `QuotaExceededError`를 `isinstance`로 분기하고 미지 subtype은 `unknown` + warning | 세 타입 테스트 |
| R4 | `blocked.attempt_no`에 현재 step 순번 기록 | 재시도 중 차단 위치 테스트 |
| R5 | 기본 sink를 repo-root `.cache/llm_events.jsonl`로 고정 | CWD 독립 경로 |
| R6 | 승인 내용을 JSONL `approval` 이벤트로 기록하고 run_id별 attempt를 실행 중 감시. 상한 초과 시 terminate + exit 2, 종료 후 재대조 | 승인 기록 및 2>1 overrun 통합 테스트 |
| R7 | 낡은 `_is_draft_profile` 테스트를 `evaluate_investability()`로 이관 | 전체 suite 수집 복구 |
| R8 | "코드 경로 동일"을 "반환값·예외·network·persistent side effect 동일"로 하향 | `.claude/rules/ai.md` 정정 |
| R9 | `attempt_no`를 step/call_context 단위 순번으로 명문화 | retry는 `(step, operation, provider)` 그룹으로 산출 |
| R10 | transport timer는 emit 전에 종료되어 `latency_ms` 자체에는 sink 시간이 포함되지 않음을 명시. 단 attempt 사이 workflow wall time에는 lock 지연 가능 | 리포트 계약 정정 |
| R11 | 빈 dict cache는 miss이며 `_ask_json` 호출 + `cache_miss` 방출을 고정 | 전용 회귀 테스트 |

추가로 전체 suite에서 발견된 별도 로더 누락을 수정했다. YAML의 명시적 `draft: true`가 `load_profile()`에서 `ValuationInput`으로 전달되지 않아 기본값 `False`로 사라지고 있었다. `draft=raw.get("draft", False)`를 복원했다.

**최종 검증:** 집중 계측·quality·scheduler `106 passed`. 프로젝트 AGENTS.md에 기록된 AI 재생성 fixture casualty `TestScenarioDriverRoundTrip` 5개를 제외한 전체 suite **800 passed, 5 deselected**. 유료 API 호출 0건.

---

# CODEX — Round 5 응답 (2026-07-12)

**판정:** R12·R13·R15 수용 및 수정. R14는 E1 스코프 예외가 맞으므로 안전 게이트 트랙으로 명시 비준했다. 유료 측정은 이 트랙의 전체 회귀가 끝날 때까지 계속 보류한다.

## R12 — production gate에 원문 전달

- `ValuationInput.profile_text`를 optional/excluded 필드로 추가했다.
- `load_profile()`이 UTF-8 YAML 원문을 한 번 읽어 parsing과 `profile_text` 보존에 함께 사용한다.
- `_apply_investability_gate()`가 `text=vi.profile_text`를 전달한다.
- 실제 `load_profile()` → `run_valuation()` 경로에서 YAML comment의 TODO와 10.0 placeholder가 blocker로 발화하는 통합 테스트를 추가했다.

## R13 — 이력과 단방향 tail 계약

읽기 전용 조사 결과, 추론 주석과 tail은 커밋 `2918696`(2026-07-09)에서 함께 처음 들어왔다. 그 이전 원본 tail은 git 이력에 없다. 따라서 원문 복원은 불가능하지만, 모듈 계약으로 검증했다.

- gate는 기존 draft를 절대 해제하지 않고 실패할 때만 `result.draft=True`를 추가한다.
- 프로덕션 통합 테스트에서 새 결손을 발견했다: gate가 뒤늦게 draft를 표시해도 quality는 gate 이전 C등급으로 남았다.
- gate draft 시 `vi.model_copy(update={"draft": True})`로 quality를 재계산해 `draft=True / grade=F / total=0` 일관성을 보장한다.
- 명시적 YAML draft와 TODO/placeholder gate draft 두 경로 모두 테스트로 고정했다.
- 검증을 마쳤으므로 “tail reconstructed/inferred” 주석을 제거하고 단방향 계약 주석으로 교체했다.

## R14 — 스코프 예외

`draft` 로더 전달은 E1 관측 변경이 아니라 안전 기능 수정이다. 현재 profiles에서 `draft: true`가 0건이라 기존 출력 영향은 0건이지만, 향후 안전 표시 보존에 필수다. HANDOFF에 E1 스코프 예외로 명시했으며 논리적으로 별도 안전 게이트 변경으로 취급한다.

## R15 — singleton 오염

`tests/test_telemetry.py`에 autouse fixture를 추가해 각 테스트 전후 `ApiGuard._reset_singleton()`을 호출한다. retry 설정이 후속 테스트에 남지 않는다.

**검증:** investability production 경로 + telemetry + quality 집중 테스트 **91 passed**. 전체 suite는 알려진 AI 재생성 fixture 그룹 5개를 제외하고 **801 passed, 5 deselected**. 유료 API 호출 0건.
