# Plan E1: LLM 호출 계측 (관측 전용) — v2 **설계 확정본**

**Status:** ✅ **IMPLEMENTED** (스코프 B) — **유료 측정 미실행.** 실측(KR/US)은 별도 비용 산정·승인 후 진행.
**확정 스코프:** **B + F1~F4 / F9 수정 + F10(단일 attempt 이벤트)**
**근거 문서:** `HANDOFF_CODEX_e1_instrumentation.md` (코드 대조 결과 F1~F9 전부 타당 판정)
**분리 근거:** `PLAN_three_statement.md` v7의 C3(quota reservation)가 3-statement와 무관한 **기존 전역 LLM 인프라 문제**임이 드러났다. E1(계측) / E2(예산·예약)를 별도 PLAN·별도 세션으로 분리한다.

## 🔴 E1의 유일한 규칙: **동작을 바꾸지 않는다**

| | |
|---|---|
| **In scope** | 관측(observation) 추가 **오직 그것뿐** |
| **Out of scope** | quota 정책 / 캐시 동작 / fallback 동작 / retry 횟수 / 예약(reservation) / 열화(degradation) |

**E1이 끝나면 우리는 처음으로 "실제로 몇 콜을 쓰는가"를 안다.** 그 숫자 없이는 E2(예산)도 3-statement 예산표도 전부 추측이다.

---

## 0. 확정 결정 로그 (Codex 8차)

| Q | 쟁점 | 결정 |
|---|---|---|
| **Q1** | api_guard 데코레이터 계측 (원안 태스크 4) | ❌ **삭제. `pipeline/api_guard.py` diff 0줄.** HTTP attempt 계측은 `_ask_anthropic()` / `_ask_openrouter()` **내부에서만**. 데코레이터 계측은 중복 집계 + 비-LLM provider 오염만 만든다 |
| **Q2** | 전송 전 차단(quota/circuit) 분류 | ✅ **`blocked` 별도 이벤트.** `sent: bool`보다 집계 기준이 명확. `ask()` / `ask_structured()`의 `_ask_*` 호출 경계에서 `ApiGuardError`를 잡아 기록하되 **기존 fallback·재발생 동작은 그대로 유지** |
| **Q3** | `ask_structured()` fallback + discovery 2경로 | ✅ **In scope.** step enum에 **`discovery_analyze` 추가**, `summarize_key_issues()`는 **`news_summary`**로 분류 |
| **Q4** | `research_note` / `two_pass` (프로덕션 호출부 없음) | ✅ **계측·mock 테스트에는 포함, 유료 측정에서는 제외.** `two_pass`도 프로덕션 호출부가 생기기 전까지 mock 전용 |
| **Q5** | 캐시 격리 | ✅ **directory-level** (`.cache/llm/<namespace>/`). **namespace 미설정 시 기존 경로·캐시 키와 완전히 동일**해야 한다 |
| **Q6** | 유료 측정 범위 | ⚠️ **조건부.** 최소 표본 = **KR 1 + US 1**. 단 **계측 구현 + mock 검증이 먼저**. 유료 측정은 **모델별 예상 attempt·토큰·비용표를 제시하고 별도 승인**을 받은 뒤에만 |
| **F10** | `attempt_start`/`attempt_end` = attempt당 2건 → DoD #4 위반 | ✅ **terminal 단일 attempt 이벤트로 변경.** 요청 직전 시각은 로컬 변수로 들고, 성공·timeout·HTTP 오류가 결정된 뒤 **latency와 함께 1건만** 기록 |

**비용 상한:** 지금 고정 금액으로 승인할 근거가 **없다**. `api_guard.py:575`의 `_LLM_COST_PER_CALL_USD = 0.02`는 **토큰·모델을 반영하지 않는 플랫 추정치**이므로 **승인 근거로 사용 금지**. 측정 러너는 모델 단가를 **하드코딩하지 않고**, 검증된 예상 attempt·비용 상한을 **입력받아 승인**하는 방식이다.

---

## 1. 왜 필요한가 — 현재는 아무것도 모른다 (코드 대조 완료)

### 1-1. 기존 카운터로는 복원 불가 — **추측이 아니라 증명됨**

| 자료 | 한계 | 검증 |
|---|---|---|
| `.cache/api_usage.json` | provider별 aggregate `calls`/`cache_hits`만. step·company·run 구분 없음 | — |
| **`calls` 카운터** | **retry의 실제 HTTP 전송을 확정적으로 누락한다** | `api_guard.py:521-559` — retryable 실패 시 `record_success`/`record_failure` **둘 다 호출 안 됨**, `func()`만 재호출(`:526`). HTTP 2회 → `calls` **+1** |
| **`cache_hits` 카운터 (LLM)** | **구조적으로 영구히 0** | `record_cache_hit()` 호출부는 `dart_client.py:46` / `macro_data.py:70` / `market_signals.py:58` **셋뿐**. `ai/analyst.py:_get_cached()`는 `ApiGuard`를 건드리지 않는다 |
| `logs/weekly_*.log` | 최근 다수가 0바이트. 내용 있는 2026-07-11 로그는 discovery 단계에서 종료 → valuation step attribution 없음 | — |

**→ 과거 로그로 소급 실측은 불가능하다. 계측을 넣고 controlled run을 새로 돌려야 한다.**

### 1-2. "콜/기업" 숫자가 코드 3곳에서 서로 다르다

| 출처 | 콜/기업 | 구성 |
|---|---|---|
| `CLAUDE.md` + `.claude/rules/ai.md` | **≤4** | classify + peers_batch + wacc + scenarios |
| `api_guard.py:632` `estimate_weekly_cost` | **6** | identify + classify + peers + wacc + scenarios + research_note |
| `scheduler/weekly_run.py:417` | **6** | classify + peers_batch + wacc + scenarios + news_summary + profile_gen |

일일 한도도 불일치: 문서 **50콜/일** vs `PROVIDER_DEFAULTS`(`api_guard.py:153-170`) **openrouter 200 / anthropic 200**.
셋 다 **logical call** 기준이라 parse_repair·retry·fallback이 곱해지는 **실제 HTTP attempt와는 아예 다른 차원**이다.

### 1-3. 메서드 단위 계측으로는 놓치는 것

```python
# ai/analyst.py  _ask_json
response = ask_structured(...)          # ① 1차 호출
try:    return _parse_json(response)
except (json.JSONDecodeError, ValueError):
    response = ask_structured(...)      # ② ★ parse repair = 두 번째 실제 호출
    return _parse_json(response)
```
```python
# ai/llm_client.py  ask_structured()   ← analyst의 모든 step이 타는 경로
try:    return _ask_openrouter(...)     # ① OpenRouter attempt
except (...):
    if os.getenv("ANTHROPIC_API_KEY"):
        return _ask_anthropic(...)      # ② ★ 다른 provider에 두 번째 HTTP attempt
```

- `AIAnalyst` 메서드마다 세면 → **parse repair와 provider fallback을 놓친다**
- `ask()`에서 **call stack으로 step을 추론하면** → 중첩 fallback에서 깨진다

**→ 2계층 계측 + `contextvars`가 유일한 답이다.**

**최악 케이스:** 1 logical step = `parse_repair 2` × `provider 2` × `retry (OR 3 / Anthropic 6)` → **이론상 최대 18 HTTP attempt**. 이 수를 관측할 수단이 지금까지 **전무했다**.

---

## 2. 설계 (확정 · 구현 완료)

```
┌─ Workflow layer (ai/analyst.py, discovery/discovery_engine.py) ──
│  무엇을 하려 했는가:  run_id / company / step / operation / cache hit·miss
│  → CallContext 를 contextvars 에 설정
└──────────────────────────────────────────────────────────────────
                    │  contextvars 로 자동 전파
                    │  (중첩 fallback에서도 같은 logical context 유지)
                    ▼
┌─ Transport layer (ai/llm_client.py) ─────────────────────────────
│  실제로 무엇이 나갔는가:  provider / model / attempt_no / tokens / latency / outcome
│  → HTTP attempt 마다 terminal 이벤트 **1건** (F10)
└──────────────────────────────────────────────────────────────────
```

### 2-1. `CallContext` (`ai/telemetry.py`)

```python
@dataclass(frozen=True)
class CallContext:
    run_id:    str          # 주간 실행 1회 = 1 run_id (BVT_RUN_ID 또는 uuid4)
    company:   str | None
    step:      str          # identify | classify | peers | peers_batch | wacc
                            # | scenarios | scenarios_draft | scenarios_refined
                            # | research_note | news_summary | discovery_analyze
    operation: Operation = "primary"   # primary | parse_repair | validator_repair

_ctx        : ContextVar[CallContext | None]
_attempt_no : ContextVar[int]     # logical call마다 0으로 리셋
_is_fallback: ContextVar[bool]
```

헬퍼: `call_context(company, step)` / `operation(value)` / `fallback()` / `next_attempt_no()` / `emit()` / `emit_blocked()`
킬스위치: **`BVT_TELEMETRY`** (기본 `0` = 비활성). sink 경로: **`BVT_TELEMETRY_PATH`** (기본 `.cache/llm_events.jsonl`).

**`contextvars`를 쓰는 이유:** `ask_structured()` 안에서 OpenRouter → Anthropic으로 fallback해도 **같은 logical context**가 유지된다. call stack 추론은 **쓰지 않는다.**

> **`validator_repair`는 아직 코드에 없다.** 3-statement PLAN(A2)에서 도입될 때 같은 `operation` 값으로 계측한다.

### 2-2. 이벤트 스키마 (F10 반영 — attempt는 **단일 terminal 이벤트**)

```
event: step_start | step_end | cache_hit | cache_miss | attempt | blocked

── logical (CallContext) ──
run_id, company, step, operation

── transport (attempt / blocked 에만) ──
provider           # openrouter | anthropic
model
attempt_no         # ★ logical call 전체 순번 (provider별 아님). blocked = None
is_fallback        # OpenRouter 실패 후 Anthropic?
input_tokens / output_tokens / cache_read_tokens
latency_ms         # attempt 에만 (요청 직전 → terminal 시점)
outcome            # attempt : success | http_error | timeout | parse_error
                   # blocked : quota_exceeded | circuit_open
est_cost_usd       # 모델별 토큰 단가 기준 (플랫 $0.02 사용 금지)
```

**`attempt` = 실제로 전송된 HTTP 1회.** timeout처럼 전송 여부가 불분명하면 **보수적으로 attempt로 계상**한다.
**`blocked` = 전송되지 않음.** E2의 "used = 실제로 전송된 attempt" 정의와 정합하도록 attempt 집계에서 **분리**한다.

**`attempt_no` 규칙:** logical transport 호출마다 0으로 초기화하고, 데코레이터 retry로 `_ask_*`가 재진입할 때 **같은 context의 카운터를 증가**시킨다. OpenRouter → Anthropic으로 넘어가도 **provider별 번호가 아니라 logical-call 전체 순번을 유지**한다.

### 2-3. 계측 삽입 지점 (구현 완료)

| 파일 | 지점 | 방출 |
|---|---|---|
| `analyst.py` `_cached_json_step()` | `_get_cached()` 직후 | `cache_hit` **또는** `cache_miss` + `step_start` / `step_end` |
| `analyst.py` `_ask_json()` | 1차 호출 | `operation="primary"` |
| **`analyst.py` `_ask_json()`** | **parse 실패 후 재호출** | 🔴 **`operation="parse_repair"`** |
| **`analyst.py` `generate_research_note()`** | 🔴 `_cached_json_step()`을 **안 거친다** | 별도 계측 (`step="research_note"`) |
| `analyst.py` 각 public step | `identify` / `classify` / `peers` / `peers_batch` / `wacc` / `scenarios` / `scenarios_draft` / `scenarios_refined` | `CallContext.step` 설정 |
| **`discovery/discovery_engine.py`** `summarize_key_issues()` | 🔴 **F4 — 원안에 없던 파일** | `step="news_summary"` + cache hit/miss |
| **`discovery/discovery_engine.py`** `_analyze_with_ai()` | 🔴 **F4** | `step="discovery_analyze"` |
| `llm_client.py` `_ask_anthropic()` | HTTP 요청 직전 시각 → terminal 시점 **1건** | `attempt` (성공 시 tokens + `cache_read_tokens`) |
| `llm_client.py` `_ask_openrouter()` | 동일 (transport/status/json/error/empty-choices 분기 전부) | `attempt` |
| **`llm_client.py` `ask()` fallback** | Anthropic fallback | `with fallback():` → `is_fallback=True` |
| **`llm_client.py` `ask_structured()` fallback** | 🔴 **F3 — 원안이 놓친 주 경로** (analyst 전 step) | `with fallback():` → `is_fallback=True` |
| `llm_client.py` `except ApiGuardError` (**Anthropic-only 분기 포함 — I1**) | **Q2** | `emit_blocked()` → **그대로 re-raise** |
| ~~`api_guard.py` decorator~~ | ❌ **Q1 — 미수정. telemetry 참조 0건** | — |

### 2-4. Sink

```
.cache/llm_events.jsonl     # append-only JSONL. 1줄 = 1이벤트
```

- **append-only** → `api_guard.py:281`의 read-modify-write lost-update 문제와 **원천적으로 무관**
- `portalocker` + append 모드 → **프로세스 간 안전** (다중 프로세스 테스트로 검증)
- 분석은 **오프라인 집계** (`scripts/e1_measure.py` / pandas / jq)
- **SQLite 전환은 E2에서** (reservation 상태기계가 필요해질 때). E1은 관측만이므로 JSONL로 충분

### 2-5. 구현 중 확인된 세부

- **I1.** `ask()`/`ask_structured()`의 **Anthropic-only 분기**에는 원래 `try/except`가 없었다. `blocked` 포착을 위해 래핑하되 **잡고 → 기록 → 그대로 re-raise**하여 동작을 보존한다.
- **I2.** `guard.check()`는 **retry 루프의 매 회차마다** 호출된다. 즉 attempt N회를 보낸 **뒤에** quota가 소진되어 `blocked`가 날 수 있다. `blocked` 단독으로는 "처음부터 차단"과 "재시도 중 차단"이 구분되지 않으므로 **같은 `run_id`·`step`의 attempt 이벤트와 offline join**으로 판별한다.
- **I3.** `summarize_key_issues()`는 `ai.analyst._get_cached/_set_cached`를 직접 import한다 → dir-level 네임스페이스가 함수 경유로 자동 적용된다.

---

## 3. 측정 절차 — **순서 고정 (Q6). 아직 미실행.**

### 3-1. 🔴 캐시 격리 — 사용자 캐시를 절대 삭제하지 않는다

**directory-level** (Q5):
```
.cache/llm/            ← 사용자 캐시 (namespace 미설정 시 = 현행 경로·키 완전 동일)
.cache/llm/<ns>/       ← 측정용. 정리 = 이 디렉터리만 rmtree
```
`_LLM_CACHE_DIR`을 분기한다. **`_cache_key()` 자체는 건드리지 않는다.**

### 3-2. 🔴 유료 호출 전 승인 게이트 (`scripts/e1_measure.py`)

러너는 **모델 단가를 하드코딩하지 않는다.** 검증된 **예상 attempt·모델·비용 상한을 입력받아** 제시하고 승인을 받는다.
```
예상 attempt: N (최악 케이스 M)
모델별 내역: Haiku × a, Sonnet × b
비용 상한:   $X.XX  (입력값)
계속할까요? (y/N)
```
**승인 없이 유료 호출을 실행하지 않는다.** 플랫 $0.02/call은 승인 근거로 쓰지 않는다.

### 3-3. 실행 순서

| # | 단계 | 유료 | 상태 |
|---|---|---|---|
| **1** | **mock 검증** — attempt / blocked / fallback / parse_repair / 캐시 불변 / 다중 프로세스 | ❌ | ✅ **완료 (37 passed)** |
| **2** | cold 실행 — **KR 1 + US 1** (DART vs EDGAR, `discovery_llm`은 KR만) | ✅ | ⏸ **승인 대기** |
| **3** | warm 실행 — 동일 namespace 즉시 재실행 → 캐시 히트율 | ✅ | ⏸ |
| **4** | partial-expiry — **선택한 step 하나만** 캐시 제거 | ✅ | ⏸ |
| **5** | **중단 조건** — 예상치와 실제치가 크게 다르면 **즉시 중단** | — | — |

**유료 측정 제외 (Q4):** `research_note`(프로덕션 호출부 없음), `two_pass`(호출부 없음) → **mock 전용**.
**`profile_generator.py:727`의 per-segment peers fallback**(배치 실패 시 세그먼트 수만큼 콜 증가)은 어떤 예산표에도 없다 — **측정에서 반드시 이 분기를 밟아본다.**

### 3-4. 산출 리포트

```
기업당:
  logical_calls (step별)   vs   http_attempts (실측)   vs   blocked
  cache_hit_rate (step별)
  retry_rate / parse_repair_rate / fallback_rate
  input·output·cache_read tokens, latency p50·p95
  est_cost_usd (모델별 단가)
집계:
  실제 attempts/company  (cold / warm / partial-expiry 각각)
  → 이 숫자가 E2 예산 계약과 3-statement 예산표의 근거가 된다
```

---

## 4. 태스크 (구현 상태)

| # | 파일 | 작업 | 상태 |
|---|---|---|---|
| 1 | `ai/telemetry.py` 🆕 | `CallContext` / contextvars / 단일 terminal attempt / 별도 `blocked` / process-safe JSONL | ✅ |
| 2 | `ai/analyst.py` | step / cache hit·miss / **parse_repair** / **research_note** 계측 + **dir-level 캐시 namespace** | ✅ |
| 3 | `ai/llm_client.py` | provider retry·fallback별 **실제 HTTP attempt** + 토큰·latency. fallback 2곳 `is_fallback`. `blocked` (re-raise 유지) | ✅ |
| 4 | `discovery/discovery_engine.py` | `news_summary` / `discovery_analyze` context | ✅ |
| 5 | `scripts/e1_measure.py` 🆕 | 이벤트 집계 + **유료 실행 승인 게이트**(비용 상한 입력식) | ✅ |
| 6 | `tests/test_telemetry.py` 🆕 | attempt / blocked / fallback / parse repair / **캐시 불변** / **다중 프로세스** | ✅ |
| 7 | `.claude/rules/ai.md` | 계측 계약 문서화 | ✅ |
| ~~8~~ | ~~`pipeline/api_guard.py`~~ | ❌ **Q1 — 미수정. telemetry 참조 0건 확인** | ✅ |

---

## 5. Definition of Done

### 동작 불변 (최우선)
1. 집중 테스트 + scheduler 회귀 **37 passed**. Python 구문 검사 통과. `git diff --check` 통과.
2. 계측 비활성(`BVT_TELEMETRY` 미설정 = 기본 `0`) 시 **`emit()`이 즉시 return** → 코드 경로 사실상 기존과 동일.
3. quota 정책 / 캐시 / fallback / retry 횟수 **변경 0건**.
4. **`pipeline/api_guard.py`에 telemetry 참조 0건.**
5. `BVT_CACHE_NS` 미설정 시 **캐시 경로·키가 기존과 완전히 동일** (캐시 불변 테스트).

> ⚠️ **전체 `pytest tests/`는 수집 단계에서 중단된다** — `tests/test_quality.py`가 **현재 존재하지 않는** `valuation_runner._is_draft_profile`을 import한다. **E1과 무관한 선행 문제**이며 별도 처리 대상.

### 계측 완전성
6. 모든 HTTP attempt에 `attempt` 이벤트 **정확히 1건** (terminal 단일 이벤트).
7. 전송되지 않은 차단은 **`blocked`로만** 기록, attempt 집계에서 제외.
8. `parse_repair` 포착 (mock).
9. provider fallback이 `is_fallback=True`로 포착 — **`ask()`와 `ask_structured()` 둘 다** (mock).
10. `api_guard` retry가 **별개 attempt**로 포착 (`_ask_*` 재진입).
11. `generate_research_note` 포착 (`_cached_json_step` 우회 경로).
12. `discovery_engine`의 2개 경로 포착 (`news_summary`, `discovery_analyze`).
13. 중첩 fallback에서 `CallContext` 유지, `attempt_no`는 logical-call 전체 순번.
14. 다중 프로세스 동시 쓰기에서 JSONL 라인 무결 (portalocker).

### 정량 검증 — **실측 시 확인**
15. **`JSONL attempt 수 − api_usage.json calls 증가분 == retry + parse_repair + fallback 수`**
    → 성립하면 §1-1의 "카운터가 재시도를 놓친다"가 **정량적으로 확정**된다.

### 측정 — **미실행**
16. mock 검증(§3-3 #1) 완료 → ✅
17. **모델별 예상 attempt·비용 상한 제시 → 사용자 승인** → ⏸ **대기**
18. cold(KR+US) / warm / partial-expiry 실측 → ⏸ **대기**

---

## 6. E1 이후

| | |
|---|---|
| **E2** (별도 PLAN·별도 세션) | 예약·예산. `used`/`reserved`/**`in_flight`** 3상태 / **heartbeat + lease renewal** / **fallback provider permit** / **attempt가 used가 되는 시점** / SQLite / `PolicyBudget` 중심 v1 |
| **3-statement** | E1 실측치로 §4-7 예산표를 **확정**한 뒤 진행 |

**E2에서 반드시 다룰 것:**
- **heartbeat/renewal 없는 TTL은 위험하다** — 실행이 TTL보다 길어지면 살아있는 프로세스의 예약을 다른 프로세스가 회수해 **같은 quota를 이중 소비**한다.
- **fallback provider permit** — OpenRouter만 예약하면 Anthropic을 **무예약 소비**하고, 양쪽 최악치로 예약하면 정상 실행에서도 **quota를 과도하게 잠근다**.
- **"used"의 시점** — 사용량은 **실제로 전송된 HTTP attempt**(E1의 `attempt` 이벤트). 전송되지 않았으면(`blocked`) 소비하지 않고, timeout처럼 전송 여부가 불분명하면 **보수적으로 used 처리**한다.
- **provider rate window는 사전 예약 대상이 아니라 요청 직전 throttle 대상**이다.
- 🔴 **`weekly_run.py:416`의 `max(llm_budget, WEEKLY_LLM_BUDGET)`** — remaining이 0이어도 바닥이 깔려 **safety net이 실효 없다**. `.claude/rules/ai.md`의 auto-trim 설명과 코드가 다르다.
- 🔴 **§1-2 숫자 통일** — 문서 ≤4 / `estimate_weekly_cost` 6 / `weekly_run` 6 / `PROVIDER_DEFAULTS` 200. E1 실측치로 확정한다.

> 🔴 **정직한 표현:** E2 v1은 **BVT 내부 일일 호출 정책**을 초과하지 않는다. **"provider quota를 넘지 않는다"고 말할 수 없다** — Anthropic은 rate window, OpenRouter는 credit 금액이고, 우리 "50콜/일"은 내부 운영 정책이다. provider rate limit은 **요청 시점에 429/`Retry-After` 준수로** 별도 대응한다.

---

## 부록 — 🔴 이 저장소 편집 시 알려진 함정 (실제 사고 기록)

**`F:\` (Windows 마운트) 경로의 파일을 Linux 셸로 read→write 라운드트립하지 말 것.**

이 문서 v2는 한 번 **184번째 줄에서 물리적으로 절단**됐다. 원인은 파일 쓰기 자체가 아니라 **셸을 통한 후처리**였다: 파일 도구로 온전히 쓴 뒤 CRLF 변환을 위해 셸에서 `read() → write()` 했는데, **셸 쪽 마운트가 방금 쓰인 파일을 부분적으로만 읽어** 잘린 내용을 그대로 덮어썼다.

- 같은 시점에 셸에서는 `ai/llm_client.py`가 263줄(구문 오류), `discovery/discovery_engine.py`가 420줄(절단)로 보였지만, **실제 파일은 각각 394줄·441줄로 온전했다.** 셸 뷰가 거짓이었다.
- **교훈:** 파일 무결성 판단은 **파일 도구(Read)** 기준으로 한다. 셸 `wc -l` / `ast.parse` 결과가 절단을 시사하면 **먼저 Read로 교차 확인**한다.
- **교훈:** 마운트된 경로의 파일을 셸로 in-place 재작성하지 않는다. 줄바꿈 변환이 필요하면 **쓰는 시점에** 처리한다.
