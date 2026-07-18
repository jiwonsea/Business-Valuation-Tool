# HANDOFF — CODEX: PLAN_E1 (LLM 호출 계측) 설계 평가 + 스코프 판정 요청

**작성일:** 2026-07-12
**대상 문서:** `PLAN_E1_llm_instrumentation.md`
**요청:** ① 아래 F1~F9(플랜 누락·모순) 판정 ② E1 스코프 A/B/C 중 확정 ③ 유료 측정 범위·비용 상한 승인

---

## ✅ 판정 결과 (Codex 8차, 2026-07-12) — **CLOSED**

**F1~F9 전부 타당 판정. 최종 스코프 = B + F1~F4/F9 수정 + F10(단일 attempt 이벤트).**
**Q1~Q5 승인, Q6 조건부 승인.** 확정 설계·구현 상태는 **`PLAN_E1_llm_instrumentation.md` v2**가 기준이다 (이 문서는 근거 기록용).

**Codex가 추가로 잡아낸 모순 — F10 (이 문서가 놓친 것):**
> 원안 스키마는 `attempt_start` / `attempt_end`를 방출 → **HTTP attempt 1회당 이벤트 2건**.
> F1(api_guard 이중 계상)을 고쳐도 **DoD("attempt마다 정확히 1건")는 여전히 깨진다.**
> → **terminal 단일 `attempt` 이벤트**로 변경. 요청 직전 시각을 로컬 변수로 들고, 성공·timeout·HTTP 오류가 결정된 뒤 latency와 함께 **1건만** 기록.

**비용 상한:** 고정 금액 승인 근거 없음. `_LLM_COST_PER_CALL_USD = 0.02`(`api_guard.py:575`)는 토큰·모델 미반영 플랫값이므로 **승인 근거로 사용 금지**. 측정 러너는 단가를 하드코딩하지 않고 **검증된 예상 attempt·비용 상한을 입력받아 승인**한다.

**현재 상태:** Round 1~4의 R1~R15 보강 완료. 전체 suite는 알려진 AI 재생성 fixture 그룹 5개를 제외하고 **801 passed, 5 deselected**. `_is_draft_profile` 테스트는 후계 API `evaluate_investability()`로 이관했고, profile 원문 TODO/placeholder가 production gate에 전달되며 gate draft는 quality F/0으로 일관되게 반영된다. **유료 측정은 미실행 — 별도 비용 산정·승인 후 진행.**

> **E1 스코프 예외:** `draft=raw.get("draft", False)` 전달은 관측 코드가 아니라 안전 게이트 기능 수정이다. profiles 전수 기준 현재 `draft: true` 입력은 0건이라 기존 valuation 출력 영향은 0건이지만, 향후 gate가 표시한 draft를 로더가 보존하는 데 필수다. E1 계측 변경과 별도 안전 게이트 트랙(R12~R14)으로 구분한다.

> **문서 주의 (해소됨, 2026-07-12):** `PLAN_E1_llm_instrumentation.md` v2는 한때 184번째 줄에서 절단됐으나 **복구 완료(현재 315줄, §6 + 부록까지 완결)**. 절단 원인은 Windows 마운트(`F:\`) 파일을 Linux 셸로 read→write 라운드트립한 것이며, **셸이 방금 쓰인 파일을 부분적으로만 읽어** 잘린 내용을 덮어썼다. 같은 시점 셸은 `ai/llm_client.py`를 263줄(구문 오류), `discovery/discovery_engine.py`를 420줄로 보고했으나 **실제 파일은 각각 394·441줄로 온전했다 — 셸 뷰가 거짓이었다.**
> 🔴 **규칙: 파일 무결성 판단은 파일 도구(Read) 기준으로 한다. 마운트 경로 파일을 셸로 in-place 재작성하지 않는다.** (PLAN v2 부록 참조)

---

## 0. 요약

플랜의 **라인 참조는 전부 정확**하고 **동기(motivation)도 실측으로 뒷받침된다.** 그러나 **계측 지점 설계에 자기모순 1건(F1)과 스키마 오분류 1건(F2)이 있고, 프로덕션 LLM 호출 사이트 2곳(discovery)이 통째로 누락(F4)**되어 있다. 원안대로 구현하면 DoD("모든 HTTP attempt에 정확히 이벤트 1건, 누락·중복 0")를 **구현 즉시 위반**한다.

---

## 1. 검증됨 — 플랜 주장이 맞다

| ID | 플랜 주장 | 판정 |
|---|---|---|
| V1 | 라인 참조 (`analyst.py` 78/164/183/191/223/409/530, `llm_client.py` 63/114/202-221/216, `api_guard.py` 281/521) | ✅ **전부 정확** |
| V2 | "`record_success()`가 최종 1회만 증가 → retry의 실제 HTTP attempt를 반영한다는 보장이 없다" | ✅ **보장이 없는 정도가 아니라, 확정적으로 누락된다** |
| V3 | "`.cache/api_usage.json`은 aggregate만" | ⚠️ **더 나쁨 — LLM cache_hits는 구조적으로 항상 0** |
| V4 | "`generate_research_note`가 `_cached_json_step`을 안 거친다" | ✅ 정확 (`ask()` + `MODEL_HEAVY`, raw text라 parse repair 없음) |

**V2 증명 (`pipeline/api_guard.py:521-559`)**
retryable 실패 시 `record_success`/`record_failure` **둘 다 호출되지 않는다**. `func()`만 재호출된다(`:526`).
→ HTTP 2회 전송 → `counters.calls` **+1** (최종 성공 시 `:527`). 재시도분은 **증발**한다.
→ 즉 `.cache/api_usage.json`의 `calls`는 "HTTP 요청 수"가 아니라 **"`_ask_*` 함수 호출의 최종 결과 수"**다.

**V3 증명**
`record_cache_hit()` 호출부는 `dart_client.py:46`, `macro_data.py:70`, `market_signals.py:58` **셋뿐**. `ai/analyst.py:_get_cached()`는 `ApiGuard`를 전혀 건드리지 않는다.
→ `api_usage.json`의 `openrouter.cache_hits` / `anthropic.cache_hits`는 **영구히 0**. 캐시 히트율 데이터는 aggregate조차 존재하지 않는다.

---

## 2. 플랜 누락·모순 (전부 수정 확정)

### 🔴 F1 — 태스크 4(api_guard 계측)가 태스크 3과 **이중 계상**된다

`@api_guard("anthropic")`는 `_ask_anthropic` **함수 전체**를 감싼다. 재시도 루프는 같은 `func(*args, **kwargs)`를 **재호출**한다(`api_guard.py:526`).

→ attempt 이벤트를 `_ask_*` **안에** 넣기만 하면 **retry마다 자연스럽게 1건씩** 발생한다. 여기에 데코레이터 계측을 더하면 **HTTP 1회당 이벤트 2건**.

부수 효과: `api_guard` 데코레이터는 dart/yahoo/fred/naver 등 **비-LLM 프로바이더 10종이 공유**한다. LLM 텔레메트리를 심으면 provider 필터가 필요하고, 토큰·모델은 데코레이터 레이어에서 **보이지도 않는다**.

> **판정: 태스크 4 삭제. `pipeline/api_guard.py` 무수정.** `attempt_no`는 `_ask_*` 진입 시 contextvar 카운터를 증가시켜 얻는다.

### 🔴 F2 — "전송되지 않은 호출"을 attempt로 집계한다

`guard.check(provider)`는 `func()` 호출 **이전**에 `QuotaExceededError`/`CircuitOpenError`를 던진다(`api_guard.py:523`). **HTTP는 나가지 않는다.**

그런데 원안 §2-2는 이 둘을 `attempt_end.outcome`의 값(`quota_exceeded`, `circuit_open`)으로 넣었다.
→ **전송 안 된 이벤트가 attempt로 집계**된다.
→ 플랜 §6이 스스로 못박은 E2 원칙 — *"quota·비용 관점의 사용량은 **실제로 전송된 HTTP attempt**"* — 과 **정면 충돌**한다.

> **판정: `blocked` 별도 이벤트로 분리.** `attempt`는 **HTTP가 실제로 나간 경우에만**. timeout처럼 불분명한 건 보수적으로 attempt 계상.

### 🔴 F3 — `ask_structured()`의 fallback이 계측 표에 없다 (프로덕션의 **주** 경로)

원안 §2-3은 fallback 지점으로 `llm_client.py:216`만 지목했다. 그건 **`ask()` 안의** fallback이다.
`ask_structured()`는 **자기만의 별도 fallback**을 `:244-248`에 가진다.

| 경로 | 사용처 |
|---|---|
| `ask_structured()` → fallback `:248` | **`_ask_json` → analyst의 모든 step** (identify/classify/peers/peers_batch/wacc/scenarios/scenarios_draft/scenarios_refined) |
| `ask()` → fallback `:216` | `generate_research_note` + discovery 2곳 |

→ `is_fallback=True` 마킹을 `:248`에 넣지 않으면 **프로덕션 fallback의 대부분을 놓친다.**

### 🔴 F4 — `discovery/discovery_engine.py`가 대상 파일 목록에 **아예 없다**

| 위치 | 함수 | 원안 상태 |
|---|---|---|
| `discovery_engine.py:193` | `summarize_key_issues()` → `ask()` | step enum에 `news_summary`는 **있는데 설정하는 코드가 없다** |
| `discovery_engine.py:395` | `NewsDiscoveryEngine._analyze_with_ai()` → `ask()` | step enum에 **아예 없다** |

둘 다 transport 이벤트는 나가지만 `CallContext`가 비어 **`step=None`**. weekly run의 **discovery 단계 LLM 콜이 통째로 미분류**된다.

### 🟡 F5 — `generate_research_note`는 **프로덕션 호출부가 없다**

repo 전수 grep 결과 **정의부 1곳뿐**. 그런데 `api_guard.estimate_weekly_cost:632`는 이걸 "6콜/기업"에 포함시킨다.
> 계측 대상으로는 유지, **예산표·유료 측정에서는 제외**.

### 🟡 F6 — `two_pass=True` 호출부가 없다 (dead path)

외부 호출부 0건 → 원안 측정 매트릭스 #6은 **프로덕션이 타지 않는 경로를 유료로 측정**한다.
> **mock 전용.**

### 🟡 F7 — "콜/기업" 숫자가 코드 **3곳에서 서로 다르다** (= E1의 존재 이유)

| 출처 | 콜/기업 | 구성 |
|---|---|---|
| `CLAUDE.md` + `.claude/rules/ai.md` | **≤4** | classify + peers_batch + wacc + scenarios |
| `api_guard.py:632` `estimate_weekly_cost` | **6** | identify + classify + peers + wacc + scenarios + research_note |
| `scheduler/weekly_run.py:417` | **6** | classify + peers_batch + wacc + scenarios + news_summary + profile_gen |

일일 한도도 불일치: 문서 **50콜/일** vs `PROVIDER_DEFAULTS` **openrouter 200 / anthropic 200**.
**어느 숫자도 실측이 아니고, 서로 맞지도 않는다.** 게다가 셋 다 **logical call** 기준이라 실제 HTTP attempt와는 별개 차원이다.

### 🟡 F8 — weekly_run의 "quota safety net"은 실효가 없다 (E2 범위)

```python
# scheduler/weekly_run.py:416
effective_budget = max(llm_budget, WEEKLY_LLM_BUDGET)   # ← max()
```
남은 quota가 0이어도 `WEEKLY_LLM_BUDGET`이 **바닥으로 깔린다**. remaining을 **상한으로 쓰지 않는다.**

### 🟡 F9 — 캐시 격리는 key-level이 아니라 **dir-level**이어야 안전

원안은 `_cache_key()`에 `BVT_CACHE_NS`를 넣자고 한다. 그러면 파일명만 바뀌고 **같은 디렉터리에 사용자 캐시와 섞인다** → 정리 시 사용자 파일 삭제 위험(플랜 §3-1이 가장 경계한 바로 그 사고).
> **판정: `_LLM_CACHE_DIR`을 `.cache/llm/<ns>/`로 분기.** 정리 = 해당 디렉터리 rmtree. 기본값(ns 미설정) = 현행 경로·키 그대로.

---

## 3. 스코프 옵션 (판정: **B**)

| | 범위 | 얻는 것 | 못 얻는 것 | 리스크 |
|---|---|---|---|---|
| **A. 최소**<br>transport-only | `llm_client.py` `_ask_*` 내부 attempt 이벤트 + JSONL sink | 총 HTTP attempt, provider, model, 토큰, latency, retry, fallback | step/company 귀속, cache hit/miss | 거의 0 |
| **✅ B. 표준**<br>= 원안 − F1 + F2/F3/F4 | A + `telemetry.py`(contextvars) + `analyst.py` + `discovery_engine.py` 2곳 + `blocked`. **`api_guard.py` 무수정** | 위 전부 + step·company 귀속 + 캐시 히트율 | — | 낮음 |
| **C. 원안** | B + api_guard 데코레이터 계측 | (B와 동일) | — | 🔴 **F1 이중 계상 → DoD 즉시 위반** |

---

## 4. Codex 답변 (Q1~Q6 → PLAN v2 §0에 확정 반영)

- **Q1** api_guard 무수정 → ✅ 승인
- **Q2** `blocked` 별도 이벤트 → ✅ 승인 (`ask()`/`ask_structured()` 경계에서 포착, re-raise 유지)
- **Q3** `ask_structured()` fallback + discovery 2경로 → ✅ In scope (`discovery_analyze` 추가, `news_summary` 분류)
- **Q4** `research_note`·`two_pass` → ✅ mock 전용, 유료 제외
- **Q5** dir-level 캐시 격리 → ✅ 승인 (ns 미설정 시 완전 동일)
- **Q6** KR 1 + US 1 → ⚠️ 조건부 (mock 우선, 비용표 제시 후 별도 승인)

**추가 DoD:** provider 청구서 대조는 불가하므로
> `JSONL attempt 수 − api_usage.json calls 증가분 == retry + parse_repair + fallback 수`
가 성립하는지 검증한다. 성립하면 V2가 **정량적으로** 확정된다.

---

## 부록 A — LLM 호출 사이트 전수 census (repo grep)

| # | 파일:라인 | 진입 함수 | 호출 | 모델 | 캐시 | 원안 커버 |
|---|---|---|---|---|---|---|
| 1 | `ai/analyst.py:169` | `_ask_json` (primary) | `ask_structured` | step별 | `_cached_json_step` | ✅ |
| 2 | `ai/analyst.py:183` | `_ask_json` (**parse repair**) | `ask_structured` | 동일 | 캐시 우회 | ✅ (원안의 핵심 발견) |
| 3 | `ai/analyst.py:540` | `generate_research_note` | `ask` | `MODEL_HEAVY` | 직접 `_get_cached` | ✅ (**프로덕션 호출부 없음 — F5**) |
| 4 | `discovery/discovery_engine.py:193` | `summarize_key_issues` | `ask` | 기본 | 직접 `_get_cached` | 🔴 **누락 (F4)** |
| 5 | `discovery/discovery_engine.py:395` | `_analyze_with_ai` | `ask` | 기본 | 없음 | 🔴 **누락 (F4)** |

**Transport (모든 호출이 수렴)**

- `ai/llm_client.py:63` `_ask_anthropic` — `@api_guard("anthropic")`, max_retries=**5**
- `ai/llm_client.py:114` `_ask_openrouter` — `@api_guard("openrouter")`, max_retries=**2**
- fallback: `ask():216` / `ask_structured():248` (**둘 다** — F3)

**최악 케이스 HTTP attempt (1 logical step 기준)**
`parse_repair 2배` × `fallback 2 provider` × `retry (OR 3회 + Anthropic 6회)` → 이론상 **1 step = 최대 18 attempt**. 이 수를 관측할 수단이 지금까지 **전무했다**. E1의 요점이 여기 있다.

## 부록 B — 프로덕션 step 실체 (`pipeline/profile_generator.py:641-844`)

`classify_segments`(:677) → `recommend_peers_batch`(:691) **또는** `recommend_peers` per-segment(:727, **N콜 — 배치 실패 시 fallback**) → `suggest_wacc`(:762) → `summarize_key_issues`(:782, **discovery**) → `design_scenarios`(:844)

> `:727` per-segment fallback 경로 = **세그먼트 수만큼 콜이 늘어난다**. 어떤 예산표에도 반영돼 있지 않다. 유료 측정 시 이 분기를 반드시 밟아봐야 한다.
