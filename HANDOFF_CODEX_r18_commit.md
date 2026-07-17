# HANDOFF — CODEX: R18 커밋 절차 (사용자 확정: E1 선행, R18 별도)

**작성일:** 2026-07-17
**결정:** 2커밋 분리. 커밋 1 = R18 파일들의 선행 트랙 잔여분(E1 + R16 등) / 커밋 2 = R18만.
**주의:** 작업 트리 272 엔트리 dirty. **이번 작업은 아래 명시된 파일만 커밋한다. 나머지는 건드리지 않는다.**

---

## 1. 원칙

1. **비파괴 staging만 사용한다.** `git add` / `git add -p` / `git restore --staged`(staging 해제만)만 허용.
   `git checkout -- <f>` · `git restore <f>`(작업 트리 대상) · `git reset --hard` · `git stash` **전부 금지.**
2. 선별 기준은 "E1이냐"가 아니라 **"R18이냐 아니냐"다.** 공유 파일에는 E1 외 R16 등 선행 잔여분이
   섞여 있을 수 있다 — 네가 방금 작성한 R18 diff(C1~C5)만 정확히 알면 역선별이 가능하다.
3. 각 커밋 직전 `git diff --cached` 전문 검토, 커밋 직후 게이트(§3) 통과 확인. 게이트 실패 시
   중단하고 보고 (commit --amend는 허용).

## 2. 절차

### 커밋 1 — 선행 트랙 잔여분 (R18 제외 전부)

대상 파일:
- `ai/telemetry.py`, `scripts/e1_measure.py` (E1 전용 — 전체 add)
- `ai/llm_client.py`, `ai/analyst.py`, `pipeline/profile_generator.py`, `tests/test_telemetry.py`
  — **`git add -p`로 R18 hunk를 제외한 나머지만** staging
- E1 관련 신규 테스트가 test_telemetry.py 외 별도 파일로 있으면 포함

R18 hunk 식별 목록 (커밋 1에서 **제외**할 것):
- llm_client: `MODEL_HEAVY = "claude-sonnet-4-6"` · `_OPENROUTER_MODEL_MAP` ·
  `_resolve_anthropic_model` / `_resolve_openrouter_model` + 호출부 · `llm_response_meta` emit 2곳
- profile_generator: `_write_enrichment_checkpoint` · `_repair_scenarios_safely` ·
  `_is_enrichment_draft` · `_emit_peers_batch_coverage` + 각 호출부(`:1087, :1395, :1425, :1460`)
- test_telemetry.py: `test_peers_batch_coverage_records_partial_response`
- analyst.py: R18 변경 없음 (전체가 커밋 1)

메시지 제안: `feat(ai): E1 LLM 텔레메트리 계측 + 선행 트랙 잔여분 정리 (R18 선행 상태)`

### 커밋 2 — R18 전체

- 커밋 1 후 위 4개 파일에 남은 diff 전부 + 신규 `tests/test_llm_model_mapping.py` ·
  `tests/test_auto_analyze_checkpoint.py` + R18 문서 4종
  (`PLAN_r18_peer_generation.md`, `HANDOFF_CODEX_r18_plan_eval.md`,
  `HANDOFF_CODEX_r18_verdict_round2.md`, `HANDOFF_CODEX_r18_impl.md`)

메시지 제안: `fix(ai/pipeline): R18 — peer 지속성 복구: Sonnet 4.6 핫픽스 + repair 격리 + checkpoint 이중 쓰기 + coverage telemetry`

## 3. 게이트 (각 단계 빈칸 없이 보고)

| 게이트 | 기준 |
|---|---|
| 커밋 1 직전 | `git diff --cached`에 R18 마커(§2 목록) 0건 |
| 커밋 1 직후 | 4개 공유 파일의 `git diff`(unstaged 잔여)가 **정확히 R18 변경만** 포함 |
| 커밋 2 직전 | `git diff --cached`가 R18 마커 전부 + 그 외 0건 |
| 커밋 2 직후 | 위 파일들 `git diff` empty · `git status`에서 위 파일들 clean |
| 최종 | 신규 테스트 3파일 재실행 pass (파일 무변경 확인용) · 작업 트리 나머지 dirty 유지 확인 |

## 4. 이탈 규칙

hunk가 물리적으로 분리 불가능하게 얽힌 경우(동일 hunk 내 E1+R18 혼재): 임의로 자르지 말고
**해당 hunk 목록을 보고하고 중단**하라. 그 경우 해당 hunk만 커밋 1에 포함시키는 방향으로
재지시받는다 (커밋 2 단독 revert 가능성이 다소 줄지만 히스토리 정확성이 우선).


---

## 5. 승인 (2026-07-17 — 분리 불가 hunk 3건 처리)

Codex 보고 3건(llm_client Anthropic/OpenRouter 성공 응답 hunk, test_telemetry OpenRouter 성공
테스트 hunk)의 인접성을 독립 확인했다 (`llm_client.py:190↔191`, `test_telemetry.py:117↔123`).
3번 hunk가 §2 식별 목록에서 누락된 것은 이쪽 실수다 — 지적이 맞다.

**승인: 3개 hunk를 커밋 1에 포함하라.** 근거: 이 방향만 커밋 1이 자기완결이다
(emit과 assertion이 동반 → 커밋 1 시점 테스트 green). 반대 방향은 커밋 1에서 E1 attempt
emit이 빠져 해당 커밋이 red가 된다.

게이트 수정:
- 커밋 1 직전: `git diff --cached`의 R18 마커는 **정확히 위 3개 hunk의
  `llm_response_meta` 관련 부분만** 허용. 그 외 R18 마커(리졸버·가드·checkpoint·repair·
  draft 조건·coverage) 0건 유지.
- 커밋 1 메시지에 포함 사실 명시. 수정 제안:
  `feat(ai): E1 LLM 텔레메트리 계측 + llm_response_meta(R18 C5 일부, hunk 비분리) + 선행 트랙 잔여분`
- 커밋 2 게이트: "R18 마커 전부"에서 위 3건 제외한 나머지 전부로 교정.

나머지 절차·금지 규칙 동일. 진행하라.


---

## 6. 재승인 (2026-07-17 — test_telemetry.py 신규 파일 비분리)

**네 권장안(1번, 전체를 커밋 1)은 기각한다.** 근거 실측:
`tests/test_telemetry.py:131`이 `pipeline.profile_generator._emit_peers_batch_coverage`를
import한다 — 이 함수는 커밋 2 코드다. 전체 파일을 커밋 1에 넣으면
`test_peers_batch_coverage_records_partial_response`가 커밋 1 시점에 **ImportError로 red**가 된다.
§5 승인의 판단 기준(각 커밋 자기완결·green)을 네 권장안이 위반한다.

**승인: 옵션 2 — `tests/test_telemetry.py` 전체를 커밋 2로.**
- 커밋 1: E1 코드는 해당 경계에서 테스트 미동반(green, 커버리지만 공백). 메시지에 명시:
  `(telemetry 테스트는 신규 파일 비분리로 후속 커밋에 동반)`
- 커밋 2: R18 잔여 전부 + `test_telemetry.py` 전체 + 신규 테스트 2파일 + 문서 4종.
- §5에서 승인했던 3개 hunk 중 **3번(test_telemetry hunk)은 본 승인으로 대체**된다.
  1·2번(llm_client emit 인접 hunk)은 §5대로 커밋 1 유지.
- 게이트 교정: 커밋 1 직전 cached diff의 R18 마커 허용치 = llm_client의
  `llm_response_meta` emit 2곳**만**. 커밋 2 직후 최종 게이트에서 전체 테스트 3파일 실행 green.

`git add -N` + hunk 수동 편집(`e`)으로 신규 파일을 쪼개는 방법은 **금지 유지** — 임의 patch
편집 리스크가 분리 이득보다 크다.

부수 보고 승인: 고아 `.git/index.lock` 제거는 확인 절차(활성 프로세스 부재·전날 0-byte)가
적절했다. 진행하라.
