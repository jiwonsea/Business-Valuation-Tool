# HANDOFF — CODEX: R18 구현 착수 (정책 확정 완료)

**작성일:** 2026-07-17
**선행:** 평가 48/60 → Claude 판정(F1 반박) → 재평가 56/60 CONDITIONAL GO → 잔여 조건 2건 계약 확정 (`PLAN_r18_peer_generation.md` §9)
**단계:** 루프의 "Codex 구현". 완료 후 Claude가 독립 재현 + 회귀표로 검증한다.

---

## 1. 구현 범위 (이 순서대로)

### C1 — F1a: MODEL_HEAVY 핫픽스 (`ai/llm_client.py`)

1. `:45` `MODEL_HEAVY = "claude-sonnet-4-6"`.
2. `:183` OpenRouter 매핑 `MODEL_HEAVY: "anthropic/claude-sonnet-4.6"`.
3. env override: `BVT_ANTHROPIC_MODEL_HEAVY` / `BVT_OPENROUTER_MODEL_HEAVY` 분리.
   각 provider 경로는 자기 var만 읽는다. 미설정 시 pinned 기본값.
4. 형식 가드 fail-fast: Anthropic 경로에 `/` 포함 스트링 → `ValueError`,
   OpenRouter 경로에 `/` 미포함 스트링 → `ValueError`. 조용한 교차 전달 금지.
5. 테스트 (신규 `tests/test_llm_model_mapping.py` 권장):
   기본 heavy→Anthropic `claude-sonnet-4-6` / 기본 heavy→OpenRouter
   `anthropic/claude-sonnet-4.6` / override→각 provider 정상 전달 / 교차 유입 시 ValueError.
   **네트워크 호출 없이** 요청 payload 조립 지점을 검사할 것 (Fake/monkeypatch).

### C2 — F2: repair 비보호 호출 제거 (`pipeline/profile_generator.py:1314~1323`)

1. `_repair_scenarios_with_llm` 호출을 try/except로 감싼다.
2. 실패 시: 원본 `validation_report`를 `status="fail"` + 기존 errors 보존 +
   `retry_attempts=1` + `retryable=False`로 model_copy → 계속 진행 (전파 금지).
3. 로그: exception type + validation error codes + retry_attempts=1만.
   **prompt·API 응답 원문 기록 금지.**

### C3 — draft 해제 조건 강화 (`profile_generator.py:1369`)

```
raw["draft"] = not (
    bool(segments and peers_all and raw.get("scenarios"))
    and (validation_report is None or validation_report.status == "pass")
)
```
`fail`·`skipped`(quota) 모두 draft 유지. repair 실패 경로(C2)와 조합 테스트.

### C4 — F3: checkpoint 이중 쓰기 (`profile_generator.py` auto_analyze)

1. 피어·WACC·세그먼트·key_issues 보강 직후(시나리오 검증 **이전**),
   `checkpoint = copy.deepcopy(raw)`에 `draft: True` · `generated: "auto"` ·
   `curated: False` 강제 + 미검증 시나리오 포함 시
   `scenario_validation: {"status": "pending"}` → `_atomic_write_yaml(yaml_path, checkpoint)`.
2. 최종(2차) 쓰기는 현행 `:1373` 위치 유지 — 검증 완료 상태만 반영.
3. checkpoint metadata가 최종 raw에 누출되지 않아야 한다 (deepcopy 필수).
4. fault-injection 테스트 3종 (신규 `tests/test_auto_analyze_checkpoint.py` 권장, LLM은 Fake):
   ① repair 호출 실패 → 디스크 YAML에 peers 생존 + `draft: true`
   ② 2차 쓰기 실패 → 1차 checkpoint가 유효 YAML로 잔존
   ③ crash 후 재실행 → `_profile_is_protected()`가 checkpoint를 overwrite 허용으로 판정
      (멱등성 계약 고정 — `profile_generator.py:73`)

### C5 — F4 telemetry만 (산식 변경 금지)

1. **`ask_structured()` 반환형 불변.**
2. `ai/llm_client.py` 응답 지점: 기존 `ai/telemetry` call_context 위에
   `llm_response_meta` emit — `{provider, model, completion_tokens, stop_reason}`.
3. `profile_generator.py` peers 단계: `peers_batch_coverage` emit —
   `{requested_segments, returned_segments, missing_codes, parse_failed, fallback_calls}`.
4. `max_tokens=2048`(`ai/analyst.py:301`)은 **건드리지 않는다.** 산식은 T3 실측 후.

## 2. 하지 말 것

- `raw`를 직접 mutate하는 checkpoint (deepcopy 없이) — 누출 사고 방지.
- `BVT_MODEL_LIGHT` 도입 — 범위 밖.
- `ask_structured` 시그니처/반환형 변경.
- 유료 API 호출 일체 (테스트는 전부 Fake/monkeypatch).
- `git checkout -- <f>` / `git restore` / `git reset --hard` — **작업 트리 dirty, 기존 미커밋 변경 보존.**

## 3. 완료 보고 회귀표 (빈칸 없이)

| 검증 항목 | 기준 | 결과 |
|---|---|---|
| pytest baseline (구현 직전 호스트 실측) | 수치 기입 | |
| pytest 구현 후 | 새 실패 0 | |
| 매핑 테스트 4경로 (C1-5) | 전부 pass | |
| fault-injection 3종 (C4-4) | 전부 pass | |
| `profiles/nvda.yaml` | SHA-256 `097d2417acf64740121aeb6c63bc01a059b16d5fdf7551ba6d37daece8b44d63` 불변 | |
| NUL 스캔 (codex-cross-review.md 명령) | clean | |
| 수정 파일 `ast.parse` + 줄 수 | 전부 정상 | |

## 4. 작업 규칙

CRLF 유지 · 원자적 쓰기(`_atomic_write_yaml` 패턴) · 수정 직후 `ast.parse`+줄수 ·
engine/ 순수성 무관 트랙이나 규칙 동일 적용 · 요구 이탈 시 **구현 전 사전 통보** ·
항목 번호 1번부터 · 완료 보고에 §3 표 빈칸 없이.
