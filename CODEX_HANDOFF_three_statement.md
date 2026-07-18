# CODEX HANDOFF — 3-Statement PLAN v7 리뷰

**대상:** `PLAN_three_statement.md` (v7)
**요청:** 적대적 설계 리뷰. **코드 작성 금지.**
**리포:** `F:\dev\Portfolio\business-valuation-tool`

---

## 0. 리뷰 범위

**지적 범위를 좁히지 말 것.** 라운드 수는 리뷰 기준과 무관하다. **치명 / 중요 / 개선 / 관찰** 4단계로 전부 적어라. "개선"과 "관찰"도 아끼지 말 것.

---

## 1. 6차 리뷰 지적 → v7 반영

### 먼저, v6의 과잉 주장을 철회한다

6차 중요1이 정확했다. v6는 **"주간 파이프라인이 이미 quota를 위반 중"**이라고 단정했는데, `calls_per_company = 6`은 **예산 추정용 상수이지 실측 소비량이 아니다.**

v7 §0에 다음을 명시했다:
- ✅ 확정: scheduler가 6콜/기업을 **예산 추정에 사용한다**
- ✅ 확정: `10 × 6`이라는 **scheduler의 가정**이 내부 50콜 정책과 충돌한다
- ✅ 확정: `max(llm_budget, WEEKLY_LLM_BUDGET)`은 **실제 잔여를 무시하는 가상 예산이다**
- ❌ 미확정: 실제 주간 실행이 **항상** 6콜을 소비한다
- ❌ 미확정: 최근 run이 **정말 60콜을 소비했다**

→ **태스크 E를 E1(실측 계측) / E2(reservation 설계)로 분리.**

### 반영 표

| 6차 지적 | v7 |
|---|---|
| **치명1** reservation을 기존 `calls`에 미리 차감하면 `record_success()`(`api_guard.py:346`)와 **이중 계상** | **§4-2** `used` / `reserved` **분리**. `available = limit − used − reserved`. 예약 소비 = `reserved−1; used+1` |
| **치명2** `_load_usage`(`:266`)/`_save_usage`(`:281`)가 **잠금 안에서 최신 파일을 재읽기·merge 하지 않음** → cross-process lost update | **§4-4** 단일 locked transaction: `read latest → reset/check → reserve/update → atomic write`. **SQLite 대안 명시** |
| **치명3** `provider_remaining()` 단일 정수로 Anthropic(RPM/TPM)·OpenRouter(credit 금액)·내부 정책(50콜)을 표현 불가 | **§4-5** `PolicyBudget` / `ProviderRateWindow` / `SpendBudget` / `LocalUsage` / `Reservations` **5축 분리**. 같은 단위끼리 비교 후 **가장 제한적인 제약**으로 결정. **`provider_remaining() -> int` 금지** |
| **치명4** sweep 우선순위가 정책과 반대 (`no_transaction`이 `full_sweep`보다 먼저 → mandatory sweep이 영원히 실행 안 됨) | **§3-3** `eligible_regimes(policy, state)`를 **먼저** 만들고 그 안에서만 고정 순서. `mandatory`에서 `no_transaction` **후보 제외** |
| **치명5** L4 열화가 실행 가능한 경로가 아님 (캐시 없는데 hit 강제 불가 / `profile_gen` 스킵 시 입력 부재) | **§4-7** 레벨 추상 **폐기**. **step 단위 호출 그래프 + 캐시 miss 행동**(`skip`/`deterministic_fallback`/`abort`) 명시 |
| 중요2 lease + 반환 필요. `try/finally`로는 SIGKILL 처리 불가 | **§4-3** `Reservation`(id/provider/reserved/consumed/run_id/pid/created/expires/status) + **TTL 회수** |
| 중요3 retry를 예약 용량에 포함. `RESERVE_MARGIN`은 retry percentile에서 | **§4-6** `reserved = planned + retry_allowance`. 초기 **10~20% (5~10콜)**, 실측 보정 |
| 중요4 `Coords.ext`가 core dimension이면 위험 | **§2-1** `currency`/`restatement`를 **명시 필드로 승격**. `ext`는 **namespaced(`x.`) 실험 차원만** + key registry + duplicate validator + **미지원 key 에러** + factory 전용 |
| 중요5 Piecewise는 폭발하지 않음 (기간별 로컬이면) | **§2-3** 기간별 로컬 Piecewise. **5년 Cartesian product 금지** 규칙 명시. 공통 조건식 DAG 공유 + named expression |
| 중요6 covenant step은 v1 범위 밖 | **§3-5** `debt_rate` 외생 고정. covenant step = `unsupported_feature` → Excel value-only / Phase 2 |
| 중요7 mandatory/optional sweep을 별도 정책으로 | **§3-2** `sweep_policy` / `sweep_pct` / `sweep_base` / `annual_sweep_cap` |
| 중요8 candidate materiality는 aggregate도 봐야 (0.8% × 10 = 8%) | **§5-1** individual < 0.5% / aggregate candidate < 1% / aggregate unmapped < 1% / **critical concepts 0% tolerance** |
| 중요9 coverage는 statement별·critical line별 | **§5-2** IS/BS ≥98%, CF ≥95%, critical 100%. **영구 상수 아님 — fixture로 보정** |
| 중요10 Decimal→DCF 반올림 경계는 한 번만 | **§11** ForwardStatements·할인·TV까지 Decimal, **`DCFResult` 생성 직전 `ROUND_HALF_UP` → int** |
| 개선1 `ROUND_HALF_UP` 고정, 내장 `round()` 금지 | **§2-2** + DoD 정적 검사 |
| 개선2 날짜·lookup은 annual v1엔 불필요 | **§2-4** (stub/mid-year/일수기반 도입 시 IR 확장) |
| 개선3 summary는 3스키마가 아니라 **같은 스키마의 view** | **§5-4** `filter_summary()`. 🔴 **각 view에서 `status_summary` 재계산** |
| 개선4 entry-point 자체 gate (CLI 우회 방어) | **§5-5** WordPress/Naver/YouTube 각각 |
| 개선5 Storage upload도 권한 행렬에 | **§5-6** approved=public / review=private+signed / blocked=로컬만 |
| 관찰1 `industry_class` 출처 보존 | **§8** 공시 산업코드 → 검증된 profile industry → keyword classifier → unknown |
| 관찰2 평균잔액은 distress에서 이자 과소추정 | **§3-6** 고금리·대규모 draw 경고 + 민감도 + Assumptions 명시 |
| 관찰3 이메일은 builder 확장만 | **§5-7** 차단 아님, **표시** |

---

## 2. 집중 검토 요청

### R1. C3가 이제 실행 가능한가 (§4) — **최우선**

- **`used`/`reserved` 분리 + lease TTL + 단일 locked transaction**이면 충분한가? 아직 남은 race가 있는가?
- **SQLite로 가는 게 맞는가, JSON을 유지하는 게 맞는가?** 현재 `portalocker` + `os.replace` 구조를 살릴 수 있나?
- **5축 예산(§4-5)에서 "실행 가능량"을 어떻게 계산하는가?** `PolicyBudget`(50콜/일)과 `SpendBudget`(USD)과 `ProviderRateWindow`(RPM)는 **단위가 다르다.** "같은 단위끼리 비교 후 가장 제한적인 제약" — 구체적으로 어떻게?
- **`ProviderRateWindow`를 실제로 읽을 수 있는가?** Anthropic 응답 헤더를 파싱해 저장하는 구조가 현재 없다. **이걸 v1 범위에 넣어야 하는가, 아니면 `PolicyBudget`만으로 시작해야 하는가?**
- 🔴 **정직성 확인:** v7은 여전히 `PolicyBudget`(내부 50콜 정책)을 주 제약으로 쓴다. **"provider quota를 넘지 않는다"고 말할 수 없다.** 이 한계를 PLAN이 충분히 정직하게 표현했는가?

### R2. C2 sweep이 이제 닫혔는가 (§3)

- `eligible_regimes(policy, state)` → `first_consistent(eligible, FIXED_ORDER)` 2단 구조가 6차가 열거한 상황을 **전부** 덮는가?
- `optional` sweep의 "활성/비활성"을 **누가 결정하는가?** 사용자 입력? 프로필? LLM? (v7이 명시하지 않았다)
- `sweep_base: excess_fcff`일 때 **FCFF가 이자에 의존**하므로 또 순환이 생기지 않는가?
- `draw`와 `sweep`의 상호배타를 **강제**했다. 실무에서 같은 기간에 둘 다 발생하는 경우(분기별 변동)를 연간 모델이 뭉개는 건 **허용 가능한 근사인가?**

### R3. E1 계측 설계

- **step별 실측**을 어떻게 하는가? `ai/analyst.py`의 각 메서드에 계측을 붙이면 되는가, 아니면 `llm_client.ask()` 레벨에서 call stack으로 step을 추론해야 하는가?
- **과거 실행 로그**(`logs/weekly_*.log`, `.cache/api_usage.json`)로 **소급 실측**이 가능한가, 아니면 계측을 넣고 **새로 한 번 돌려야** 하는가?
- 캐시 히트가 콜을 얼마나 줄이는지 측정하려면 **cold/warm 양쪽**을 돌려야 하는가?

### R4. 태스크 순서

Codex 6차 권장: `E1 → E2 → A → B → C → D → C1/C2 구현`.
- **E를 별도 세션에서 먼저** 끝내라는 권고를 v7이 수용했다. **맞는가?**
- A/B/C는 E와 독립이므로 **병행 가능**한가, 아니면 정말 직렬이어야 하는가?
- **E2(reservation 구현)는 3-statement와 무관한 기존 파이프라인 버그 수정이다.** 이걸 이 PLAN에 묶는 게 맞는가, 아니면 **별도 PLAN으로 분리**해야 하는가?

### R5. 이제 착수 가능한가

4대 계약이 닫혔는가? 남았다면 **무엇이 남았는지** 지목하라.

---

## 3. 파일을 읽고 답할 것

1. **`pipeline/api_guard.py`** 전체 — `used`/`reserved` 분리를 **기존 구조에 어떻게 넣는가.** `ProviderConfig` / `_CircuitState` / decorator(`:521`)와의 상호작용.
2. **`ai/analyst.py`** — step별 계측 삽입 지점.
3. **`.cache/api_usage.json`** + **`logs/weekly_*.log`** — 소급 실측 가능성.
4. **`scheduler/delivery.py`** — `filter_summary()` view가 기존 builder를 얼마나 건드리는가. `status_summary` 재계산 지점.
5. **`schemas/models.py:743` `DCFProjection`** — Decimal 전환 범위.

---

## 4. 산출물 형식

```
## 치명 (구현하면 깨짐)
## 중요 (구현 중 처리)
## 개선 (더 나은 방법)      ← 아끼지 말 것
## 관찰 (판단 보류 / 추가 조사)
## R1~R5 답변
## §3 파일 확인 결과
## 최종 판정 — C1/C2/C3/C4 각각 닫혔는가 / 어느 태스크부터 착수 가능한가
```

---

## 5. 리포 제약

1. **미커밋 작업 대량.** `git checkout -- <f>` / `restore` / `reset --hard` **금지**.
2. Windows 마운트에서 **대용량 편집이 파일을 truncate한 전례**(`schemas/models.py` 포함) → **원자적 재작성 + `ast.parse` + `wc -l`**.
3. **`engine/`은 순수함수. IO 금지.** `fs_graph`/`fs_model`/`fs_solve`/`fs_eval`/`fs_checks`는 `engine/`, **`fs_compile`/`fs_layout`만 `output/`**.
4. `profiles/`는 AI가 덮어씀 → 픽스처는 `tests/fixtures/`.
5. `output/excel_builder.py:56-59` — `sheet_raw_data` index 0 트릭.
6. 신규 파일 **CRLF**.
