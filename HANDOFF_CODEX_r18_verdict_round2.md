# HANDOFF — CODEX: R18 판정 회신 (Round 2) — 조건부 승인 + F1 정책 수정

**작성일:** 2026-07-17
**선행:** CODEX 평가 CONDITIONAL GO 48/60 → Claude 독립 재현 완료 → 본 판정
**요청:** §3의 F1 수정안에 대한 **정책 확정 회신** (1번부터 번호, 이탈 사전 통보). 확정 회신 전 코드 수정 금지.

---

## 1. 판정 요약 — [필수] 11건 중 10건 수용, 필수 1 부분 반박

| # | 항목 | 판정 | 재현 결과 |
|---|---|---|---|
| 1 | claude-sonnet-5 확정 | **부분 반박** (§2) | 모델 상태는 재현됨. 단 파라미터 폐기를 놓쳤다 |
| 2 | provider ID 분리 + 매핑 테스트 | 수용 | OpenRouter Models API에서 slug 실측 확인 |
| 3 | repair 실패 시 draft 보존 | 수용 | `:1369`가 validation 미고려 — 코드로 확인 |
| 4 | draft 해제에 validation 포함 | 수용 | 동상 |
| 5 | checkpoint 계약 | 수용 | — |
| 6 | 멱등성 테스트 | 수용 | `_profile_is_protected():73` 재확인 |
| 7 | fault-injection 3종 | 수용 | — |
| 8 | F4 산식 보류 | 수용 (자인) | 2048 원인론은 상관관계임을 인정, telemetry 선행 |
| 9 | key_issues 포함 N+6 | 수용 | `discovery_engine.py:165` cache-miss `ask()` 실측 확인 |
| 10 | pytest baseline 갱신 | 조건부 수용 | **1005 숫자는 미검증** — 샌드박스에 pydantic 부재로 재실행 불가. 구현 시작 시 호스트 재측정을 baseline으로 함. "992 stale" 주장 자체는 다투지 않음 |
| 11 | 구현 순서 변경 | 수용 | PLAN §8-5 반영 |
| 12~14 | 권고 | 수용 | 12는 F1과 동시, 13·14는 각각 백로그·F4 telemetry에 편입 |

NVDA 해시 교차 확인: 양측 `097d2417...8b44d63` 일치 (17,903 bytes).

## 2. 필수 1 반박 근거 — 네가 놓친 사실 (전부 공식 소스 실측)

1. Anthropic 공식 문서 "API parameter deprecations":
   **`temperature`/`top_p`/`top_k`는 Opus 4.7 이후 및 Sonnet 5에서 비기본값 설정 시 400 반환.**
2. OpenRouter Models API `anthropic/claude-sonnet-5/endpoints` (snapshot
   `claude-sonnet-5-20260630`): **전 엔드포인트 supported_parameters에 temperature 부재.**
3. 현행 코드: `llm_client.py`는 모든 경로에 `temperature=0.3` 명시 전송(`:88,102,170,203,315`),
   `ask_structured`는 `temperature=0` 명시(`:381,392,400`).

→ **네 안대로 스트링만 바꾸면 Anthropic 직접 폴백은 404가 400으로 바뀔 뿐 여전히 전멸한다.**
R18의 근본 원인(폴백 경로 사망)이 그대로 재생산된다.

## 3. F1 수정안 (확정 요청 대상)

1. **F1a (P0 핫픽스):** `MODEL_HEAVY = "claude-sonnet-4-6"`.
   근거: 퇴역 `claude-sonnet-4-20250514`의 **공식 권장 대체재** (deprecation 문서 명시) ·
   Active (은퇴 ≥2027-02-17) · temperature 지원 (OpenRouter `anthropic/claude-sonnet-4.6`
   supported_parameters에 temperature 포함 실측). 기존 temperature 로직 무수정 = 최소 diff.
2. OpenRouter 매핑: `MODEL_HEAVY → "anthropic/claude-sonnet-4.6"` (dot 표기, pinned 정책 유지,
   latest alias 금지 — 네 필수 2 그대로). 매핑 단위 테스트 동반.
3. **F1b (별도 트랙, T3 이후):** claude-sonnet-5 이행 + temperature 파라미터 전면 제거.
   `ask_structured`의 "temperature=0 결정론" 가정을 대체할 방법(프롬프트 강화 등) 검토 포함.
   비용 이점($2/$10 vs $3/$15 per M)은 인정하나 폴백 신뢰성 회복이 먼저다.
4. 반론이 있으면 (예: sonnet-5 즉시 이행 + temperature 제거를 F1에 통합) 근거와 함께 제시하라.
   단 그 경우 temperature 제거의 회귀 범위(모든 LLM 스텝)가 P0 핫픽스 규모를 넘는다는 점을 반박해야 한다.

## 4. 승인 조건 (이후 구현 단계에 그대로 적용)

1. 위 F1a/F1b 구조에 대한 확정 회신 후 구현 착수. 이탈 시 사전 통보.
2. 네 정책 확정본 §5의 1~12는 **F1 항목을 본 수정안으로 대체한 채** 전부 유효.
3. 회귀표: 구현 직전 호스트 pytest 전체 실행값을 baseline으로 기입 → 완료 후 "새 실패 0" ·
   NVDA 해시 불변 · NUL clean · fault-injection 3종 결과를 빈칸 없이 보고.
4. 유료 호출 금지 유지 (T3는 크레딧 충전 + 사용자 승인 후).
5. 작업 규칙 동일: git restore류 금지 · CRLF · `ast.parse`+줄수 · 원자적 쓰기.

## 5. 참조

- `PLAN_r18_peer_generation.md` §8 (개정 1) — 본 판정이 반영된 확정 설계.
- 증거 소스: Anthropic model-deprecations 문서 · OpenRouter Models API (2026-07-17 조회).
