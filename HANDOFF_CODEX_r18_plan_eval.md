# HANDOFF — CODEX: R18 PLAN 평가 요청 (peers 0건 근본 원인 확정판)

**작성일:** 2026-07-17
**평가 대상:** `PLAN_r18_peer_generation.md` (같은 날 작성, 진단 확정판)
**배경 문서:** `HANDOFF_CODEX_r18_peer_generation.md`(원 등록) · `DEBATE_e1_round1.md` Round 7 · `.claude/rules/codex-cross-review.md`
**단계:** 루프의 "Codex 평가" — **6축 60점 · [필수]/[권고] · GO / CONDITIONAL GO / NO-GO.**
**구현 금지:** 이 단계에서는 코드를 만지지 않는다. 평가 + 정책 확정본만 회신하라.

---

## 0. 한 줄 요약

R18은 "peer 생성 실패"가 아니었다. **AI가 만든 피어가 메모리·캐시까지 도달했는데,
`auto_analyze()`가 종단 YAML 쓰기(`pipeline/profile_generator.py:1373`) 전에
비보호 LLM 호출에서 사망해 `auto_fetch()`의 스텁(`peers: []`)이 디스크에 남았다** (H3 변형).
트리거는 OpenRouter 크레딧 403 → 죽은 `MODEL_HEAVY` 스트링(`claude-sonnet-4-20250514`)으로의
Anthropic 폴백 404 연쇄다. 상세 증거 E1~E7은 PLAN §2.

## 1. 독립 재현 지시 (⚠️ 우리 주장을 믿지 말고 직접 실행하라 — 전부 무료)

1. kill chain: `grep -n -E "Key limit exceeded|claude-sonnet-4-20250514|Valuation failed" logs/weekly_20260627.log`
2. 캐시 단면: `.cache/llm/`에서 Apple/Charter/SpaceX의 06-27자 파일 step 분포 확인 — scenarios 부재가 재현되는가
3. 스텁 물증: `profiles/aapl.yaml` 주석·TODO 보존 확인 + `_generate_draft_profile()` 템플릿(f-string, 주석 포함)과
   `_atomic_write_yaml`(yaml.dump, 주석 소실)의 출력 차이를 코드로 대조
4. H2 반증: 캐시된 aapl/chtr peers JSON을 `ai.validators.validate_peers(payload, "US")`에 통과 — 전량 필터가 재현 안 됨을 확인
5. 탈출 지점: `profile_generator.py` 1000~1373 구간에서 try/except 밖 LLM 호출을 전수 확인.
   **우리 판정은 `:1315 _repair_scenarios_with_llm`이 유일한 비보호 지점이라는 것이다 — 반례가 있으면 제시하라.**
6. T2: peers_batch 캐시 4건의 세그먼트 수 vs 같은 회사 classify 캐시의 세그먼트 수 대조 (SpaceX 3→1 등)

## 2. 평가 요청 항목 (PLAN §4 F1~F6)

| # | 항목 | 특히 따져볼 것 |
|---|---|---|
| 1 | F1 MODEL_HEAVY 갱신 | 모델 스트링 선택 근거. date-suffix alias 정책. OpenRouter 매핑(`llm_client.py:183`)과의 정합 |
| 2 | F2 `:1315` try/except | 실패 시 `validation_report` 처리 방식이 R16 draft 게이트와 충돌하지 않는가 |
| 3 | F3 이중 쓰기 (검증 前 1차) | **최대 쟁점.** 1차 쓰기 시점의 `draft: true` 유지 로직, `_profile_is_protected` overwrite 보호와의 상호작용, crash 후 재실행 시 멱등성. 2차 쓰기 실패 시 상태 |
| 4 | F4 batch max_tokens 동적 산정 | `min(1024 + 768*N, 8192)` 수치 근거가 약하다 — 대안 산식 또는 실측 후 결정 조건부로 제시 가능 |
| 5 | F5 quota 예산표 개정 | 실 콜 수 상한 산식 검증 (classify 1 + batch 1 + fallback ≤N + wacc 1 + scenarios 1 + repair ≤1) |
| 6 | 순서 (PLAN §5) | F1·F2 선행 → T3 측정(크레딧 충전 후) → F3·F4. 이 순서에 이견이 있으면 근거와 함께 |

## 3. 정책 확정본 요구 사항 (구현 전 필수 — 과거 실패 패턴 #2·#3 방지)

- 항목 번호는 **1번부터 빠짐없이.**
- 요구사항 이탈 시 **사전 통보** — 조용한 이탈은 NO-GO 사유다.
- 회귀 기준표를 빈칸 채워서 회신하라:

| 검증 항목 | 기준 | 결과(빈칸) |
|---|---|---|
| pytest 전체 | 992 passed, 5 deselected 유지 | |
| aapl/chtr/spcx 재실행 시 peers 보존 | F3 적용 후 crash 주입 테스트에서 peers 생존 | |
| 큐레이션 프로필 보호 | `profiles/nvda.yaml`(17.9KB, Phase A~C) 미변경 | |
| NUL 스캔 | 구현 후 clean (직접 스캔 명령은 codex-cross-review.md) | |

## 4. 작업 규칙 (항상 동일)

- **`git checkout -- <f>` / `git restore` / `git reset --hard` 절대 금지** — working tree에 미커밋 작업 다수.
- 파일 수정 직후 `ast.parse` + 줄 수 확인. CRLF 유지. 원자적 쓰기(`_atomic_write_yaml` 참조).
- `engine/` 순수 함수 유지 · Pydantic 입력 mutate 금지(`model_copy`).
- **T3 유료 측정은 이 평가 범위 밖이다.** 크레딧 충전(F6) 전에는 어떤 유료 호출도 하지 마라.

## 5. 회신 형식

1. 6축 60점 채점표 (축별 근거 1~2문장)
2. [필수] / [권고] 목록 (1번부터)
3. GO / CONDITIONAL GO / NO-GO + 조건
4. §1 독립 재현 결과 (명령별 관찰 요약 — 우리 증거와 불일치하는 점을 명시)
5. §3 정책 확정본
