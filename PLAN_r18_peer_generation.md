# PLAN R18 — 자동 생성 프로필 peers 0건 (진단 확정판)

작성: 2026-07-17 | 근거: 코드 정독 + `.cache/llm/` 100건 + `logs/weekly_20260627.log` 실측 (유료 호출 0건)
상태: **원인 확정 → CODEX 평가 대기**. 구현은 CODEX 평가 후.

## 1. 판정

**H3 변형 확정.** H1(AI 미호출) 기각, H2(validate_peers 전량 필터) 기각.

> AI 피어 단계는 정상 실행되어 결과를 캐시에 남겼으나, `auto_analyze()`가
> **YAML 보강 쓰기(`pipeline/profile_generator.py:1373`)에 도달하기 전에
> 비보호 LLM 호출 지점에서 사망**했다. 디스크에는 `auto_fetch()`가 먼저 써둔
> 스텁(`peers: []`)이 그대로 남았고, 이것이 `dcf_vs_peer` draft 34/45건의 원천이다.

## 2. 증거 (전부 무료 실측)

- **E1** `weekly_20260627.log` 11:41~11:42 kill chain:
  OpenRouter 403 `Key limit exceeded (total limit)` → circuit OPEN
  → Anthropic 직접 폴백 → **404 `model: claude-sonnet-4-20250514`**
  → anthropic circuit OPEN → `Valuation failed [CHTR]/[AAPL]/[SPCX]` (3사 동시 종료).
- **E2** 같은 시각 캐시: 3사 모두 classify→peers→wacc→key_issues 존재, **scenarios만 부재**.
  실행이 시나리오 단계 부근에서 끊겼음을 독립 확인.
- **E3** `profiles/aapl.yaml`·`chtr.yaml`·`spcx.yaml` = 주석·TODO가 살아있는
  `_generate_draft_profile()` 템플릿 원형. `auto_analyze`의 쓰기는 `yaml.dump`라
  주석이 소실되므로, **주석 보존 = 보강 쓰기 미도달**의 물증.
- **E4** 같은 시기 msft/googl/meta/amzn/tsla는 10KB+ 정상 보강 → 전역 배선 문제(H1) 아님.
- **E5** H2 반증: 캐시된 aapl/chtr 피어 JSON 6건을 `validate_peers()`에 통과 →
  세그먼트당 5~7건 생존, 전량 필터 사례 0건.
- **E6** `ai/llm_client.py:45` `MODEL_HEAVY = "claude-sonnet-4-20250514"` — **현재도 그대로.**
  OpenRouter 경유 시엔 `anthropic/claude-sonnet-4`로 치환되어 살지만(:183),
  Anthropic 직접 폴백은 죽은 date-suffix 스트링을 그대로 쏜다. 폴백 = 즉사 404.
- **E7** (T2) peers_batch 응답이 세그먼트를 체계적으로 누락:
  SpaceX 3→1, Tesla 3→1, UNH 2→1, Broadcom 2→2(유일 성공).
  `analyst.py:301` `max_tokens=2048`은 세그먼트 3~5개 × 피어 7건 분량을 못 담는다.
  → `batch_ok=False` → 세그먼트별 폴백 → 기업당 실 콜 수 = 예산표(≤4)의 2~3배.

## 3. 근본 원인 — 3계층

| 계층 | 원인 | 위치 |
|---|---|---|
| 인프라 | OpenRouter 키 total limit 소진(403) — **현재도 소진 상태(사용자 확인)** | 코드 밖 |
| 인프라 | Anthropic 폴백 모델이 퇴역 스트링 → 폴백 경로 전멸 | `ai/llm_client.py:45` |
| 코드 | `_repair_scenarios_with_llm` 호출이 try/except 밖 — auto_analyze 내 유일한 비보호 LLM 지점. 스텁 템플릿에 generic Base/Bull/Bear가 있어 검증→fail→repair 분기가 상시 발동 가능 | `profile_generator.py:1315` |
| 설계 | 보강 쓰기가 함수 종단 단일 지점 — 그 전 crash 시 AI 결과(피어·WACC·시나리오) 전량 유실 | `profile_generator.py:1373` |
| 설계 | batch max_tokens 부족 → 폴백 폭증 → quota 가속 소진 → 403 유발 가능성 (원인 루프) | `ai/analyst.py:301` |

## 4. 수정안 (CODEX 평가 요청 대상)

- **F1 (P0, 1줄)** `MODEL_HEAVY`를 유효 모델로 갱신. 후보: `claude-sonnet-5` 계열
  현행 스트링을 Anthropic 모델 목록에서 확인 후 확정. date-suffix 없는 alias 사용 검토.
- **F2 (P0, 소규모)** `:1315` repair 호출을 try/except로 감싸고 실패 시
  `validation_report`를 `retryable=False`로 보존한 채 진행 (쓰기 도달 보장).
- **F3 (P1, 구조)** `_atomic_write_yaml`을 **시나리오 검증 이전**(피어·WACC·세그먼트
  보강 직후)에 1차 실행 → 검증·repair 후 2차 실행. crash 시에도 피어는 살아남는다.
  draft 플래그 로직(`:1369`)과의 정합 주의: 1차 쓰기 시점엔 `draft: true` 유지.
- **F4 (P1)** `recommend_peers_batch` max_tokens를 세그먼트 수 기반 동적 산정
  (예: `min(1024 + 768*len(segments), 8192)`) + 응답 세그먼트 누락 시 누락분만 폴백
  (현행 로직 유지)하되 **폴백 콜 수를 telemetry로 계측**.
- **F5 (P2, 문서)** `.claude/rules/ai.md` quota 예산표를 실측 반영 개정
  (batch 실패 시 실 콜 수 = classify 1 + batch 1 + 세그먼트 N + wacc 1 + scenarios 1 + repair ≤1).
- **F6 (사용자 액션)** OpenRouter 크레딧 충전 또는 한도 상향. 코드로 해결 불가.

## 5. 순서

1. 본 PLAN → **CODEX 교차 평가** (`.claude/rules/codex-cross-review.md` 루프 준수,
   Codex 주장 독립 재현 필수)
2. F1·F2 구현 (최소 패치) → pytest 992 passed 유지 확인
3. F3·F4 구현 → 신규 테스트 (write-before-validate 경로, batch 부분 응답 폴백)
4. **T3 = E1 유료 측정** (KR 1 + US 1, `scripts/e1_measure.py`, `--cache-ns r18_diag`,
   승인 게이트 ~24 attempts / $0.60 상한) — **선행 조건: F1·F2 반영 + F6(크레딧) 해결.**
   E1 DoD #15~#18은 이 측정으로 닫는다.
5. 측정으로 배치/폴백 실 콜 수 확정 → F5 예산표 개정

## 6. 미해결 관찰 (R18 밖, 섞지 말 것)

- `logs/weekly_2026071{2..7}.log` 전부 0바이트 — 최근 주간 런이 로그 한 줄도 못 남기고
  종료 중일 가능성. 별도 진단 필요.
- 열린 백로그 #3 (`draft_blocked` 카운트 템플릿 렌더): `delivery.py:153-154`,
  `naver_poster.py:450` — R18과 독립, 소규모.
- `035420.yaml` 재생성: R18 해결 후 처리 (핸드오프 이관 사항).

## 7. 세션 안전 수칙 (재확인)

- `git checkout/restore/reset --hard` 금지 (미커밋 대량 작업 트리).
- `F:\` 마운트 read→write 라운드트립 금지. 무결성 판단은 파일 도구(Read) 기준.
- `.py` 수정 후 로컬 인터프리터로 `ast.parse` + `wc -l` 검증.


---

## 8. 개정 1 (2026-07-17 — CODEX 평가 CONDITIONAL GO 48/60 반영)

CODEX [필수] 1~11 중 **10건 수용, 필수 1 부분 반박** (독립 재현 결과는
`HANDOFF_CODEX_r18_verdict_round2.md` 참조). 본 개정으로 §4·§5를 다음과 같이 대체한다.

### 8-1. F1 수정 — Codex 안(claude-sonnet-5 즉시 전환) 반박

Codex가 놓친 사실 (2026-07-17 실측 재현):
- Anthropic 공식 문서: **Sonnet 5는 `temperature`/`top_p`/`top_k` 비기본값 설정 시 400 반환**
  (API parameter deprecations, Opus 4.7 이후 + Sonnet 5).
- OpenRouter `anthropic/claude-sonnet-5` 전 엔드포인트의 `supported_parameters`에도
  `temperature` 부재 (Models API 실측, snapshot `claude-sonnet-5-20260630`).
- 현행 `llm_client`는 **모든 호출에 `temperature=0.3`, `ask_structured`는 `temperature=0`**을
  명시 전송 (`llm_client.py:88,102,170,203,315,381,392,400`).
→ 스트링만 교체하면 Anthropic 직접 경로가 404에서 400으로 바뀔 뿐 여전히 전멸한다.

**확정안:**
- **F1a (P0 핫픽스):** `MODEL_HEAVY = "claude-sonnet-4-6"` — 퇴역 모델의 공식 권장 대체재
  (deprecation 문서 명시), Active(은퇴 ≥2027-02-17), temperature 지원 확인
  (OpenRouter `anthropic/claude-sonnet-4.6` supported_parameters 실측). 1줄 + 매핑 갱신.
- **F1b (후속, T3 이후):** claude-sonnet-5 이행 — temperature 파라미터 제거 리팩터 동반.
  `ask_structured`의 "temperature=0 결정론" 가정 재론 필요(방법론 사안)하므로 별도 트랙.
- 필수 2 수용: provider별 ID 분리(`claude-sonnet-4-6` ↔ `anthropic/claude-sonnet-4.6`),
  매핑 단위 테스트 추가, latest alias 금지.
- 권고 12 수용: `BVT_MODEL_HEAVY`/`BVT_MODEL_LIGHT` env override (기본값 pinned).

### 8-2. F2·F3 계약 확정 (필수 3~7 전부 수용)

- repair 실패 시: 예외 삼킴 + `status="fail"` 원본 errors 보존 + `retry_attempts=1`
  + `retryable=False` + **`raw["draft"]=True` 강제.**
- draft 해제 조건 강화(`:1369` 대체): `segments and peers_all and scenarios` **AND**
  `(validation_report is None or validation_report.status == "pass")`.
  `fail`·`skipped`(quota)는 draft 유지.
- F3 checkpoint 계약: 1차 쓰기 payload는 **별도 복사본**으로 `draft: true` ·
  `generated: auto` · `curated: false` 강제, 미검증 시나리오 포함 시
  `scenario_validation: {status: pending}` 기록. 2차 쓰기만 검증 완료 상태를 반영.
- 멱등성: `_profile_is_protected()`가 checkpoint(draft/auto)를 overwrite 허용으로
  판정하는 계약을 테스트로 고정.
- fault-injection 3종: ① repair 실패 → peers 디스크 생존 + draft:true
  ② 2차 쓰기 실패 → 1차 checkpoint 유효 YAML ③ crash 후 재실행 → checkpoint 정상 승격.

### 8-3. F4·F5 (필수 8·9 수용)

- F4: `1024+768*N` 산식 **철회.** 이번 트랙에서는 telemetry만 추가
  (requested/returned segments, 누락 코드, completion tokens, stop_reason, fallback count
  — 권고 14의 parse 실패 vs 부분 응답 구분 포함). 산식은 T3 실측 후 확정.
- F5: 논리 호출 상한 = classify 1 + batch 1 + fallback M(0≤M≤N) + wacc 1
  + key_issues 0~1 + scenarios 1 + repair 0~1 = **최악 N+6**
  (`summarize_key_issues`의 cache-miss `ask()` 호출 실측 확인). provider attempt는 별도 지표.

### 8-4. 회귀 기준 갱신 (필수 10)

- pytest baseline: Codex 주장 1005 passed는 **이 세션에서 미검증**(샌드박스 의존성 부재).
  구현 시작 시 호스트에서 전체 재실행 → 그 수치를 baseline으로 고정, 승인 기준은 "새 실패 0".
- `profiles/nvda.yaml` SHA-256 `097d2417...8b44d63` (17,903 bytes) 불변 — 양측 해시 일치 확인.
- NUL 스캔 clean, CRLF 유지, `ast.parse` + 줄 수 검증.

### 8-5. 구현 순서 (필수 11 수용, §5 대체)

1. F1a·F2 + draft 안전 조건 (8-2) → 호스트 pytest baseline 측정 + 새 실패 0
2. F3 + 무료 fault-injection 3종
3. F4 telemetry만 추가
4. 사용자 승인 + OpenRouter 크레딧(F6) → **T3 유료 측정**
5. T3 실측으로 F4 산식 확정 + F5 예산표(`.claude/rules/ai.md`) 개정
6. F1b (sonnet-5 + temperature 제거) 별도 트랙


---

## 9. 확정 (2026-07-17 — 재평가 56/60 CONDITIONAL GO, 잔여 조건 2건 계약 확정)

### 9-1. Provider별 env override 계약 (재평가 필수 2·4 반영)

- **분리 방식 채택:** `BVT_ANTHROPIC_MODEL_HEAVY` / `BVT_OPENROUTER_MODEL_HEAVY`.
  각 provider 경로는 자기 var만 읽고, 미설정 시 pinned 기본값
  (`claude-sonnet-4-6` / `anthropic/claude-sonnet-4.6`).
  근거: R18 자체가 "잘못된 모델 스트링의 조용한 provider 교차 전달" 사고였다.
  논리명+자동 매핑안은 매핑 dict 밖 임의 override에서 같은 사고를 재생산한다.
- **형식 가드 (fail-fast):** Anthropic 경로에 `/` 포함 스트링 유입 시,
  OpenRouter 경로에 `/` 미포함 스트링 유입 시 각각 즉시 `ValueError`.
  조용한 전달 금지 — 단위 테스트로 고정.
- `BVT_MODEL_LIGHT`류는 R18 범위에서 **제외** (필수 4 수용). heavy만.

### 9-2. F4 telemetry 전달 계약 (재평가 필수 3 반영)

- **`ask_structured()` 반환형 불변.** 공용 계약 무변경.
- LLM client 응답 지점에서 기존 `ai/telemetry` contextvars(call_context) 위에
  신규 이벤트 `llm_response_meta` emit: `{provider, model, completion_tokens, stop_reason}`.
- analyst/profile_generator 쪽에서 `peers_batch_coverage` emit:
  `{requested_segments, returned_segments, missing_codes, parse_failed(bool), fallback_calls}`
  (권고 14의 parse 실패 vs 부분 응답 구분 포함).
- 두 이벤트는 기존 run_id/step correlation으로 연결. JSONL sink 재사용.

### 9-3. 권고 5~7 수용

- F1a 매핑 테스트 3경로: 기본→Anthropic ID / 기본→OpenRouter slug / override→각 provider 정상 전달.
- repair 예외 로그: exception type + validation error codes + retry_attempts=1만.
  prompt·응답 원문 기록 금지.
- F3 checkpoint는 `copy.deepcopy(raw)`.

이로써 잔여 조건 2건 해소 — **구현 착수 승인.** 상세는 `HANDOFF_CODEX_r18_impl.md`.


---

## 10. 구현 검증 기록 (2026-07-17 — Claude 독립 재현, 루프 종결)

**판정: 승인.** Codex C1~C5 구현 보고의 전 항목을 독립 재현했다.

| 항목 | Codex 주장 | 독립 재현 결과 |
|---|---|---|
| 코드 실사 | C1~C5 구현 | 리졸버+가드(`llm_client.py:53-75`), repair 격리+원본 복원(`_repair_scenarios_safely`), draft 조건(`_is_enrichment_draft`), deepcopy checkpoint(`:125-133`, 검증 前 `:1395` 배치), telemetry emit(`llm_client.py:192,335` + coverage) 전부 확인 |
| 이탈 1건 ("pass"→"ok") | 실제 스키마 기준 교정 | **수용.** `engine/scenario_validator.py:263` 정상 리터럴 `"ok"` 실측 — 핸드오프 명세("pass")가 오류였다. 이탈 보고 방식도 규칙 준수 |
| NUL 스캔 | clean | 리포 전체 자체 스캔 clean |
| CRLF·ast·줄수 | 5개 파일 정상 | 전부 일치 (437/1507/107/98/332, lf_only=0, ast OK) |
| nvda.yaml 해시 | 불변 | `097d2417...8b44d63` 일치 |
| 신규 테스트 | 4+7 pass | **샌드박스 직접 실행 24/24 pass** (mapping 4 + telemetry 13 + checkpoint 7; socksio/portalocker는 샌드박스 환경 의존성) |
| pytest 1005→1017 | 새 실패 0 | 전체 suite는 샌드박스 재현 불가(호스트 전용 의존성). 단 **증가분 +12 = 매핑 4 + checkpoint 7 + telemetry 신규 1로 산술 정합.** 다음 호스트 세션에서 1회 재확인 권장 |

### 정책 노트
- `status == "warning"`도 draft 유지된다 (`"ok"`만 해제). 보수적 방향으로 의도 부합 — 추후 warning 완화 논의 시 이 지점.

### 잔여 관찰 (백로그, R18 밖)
1. `_OPENROUTER_DEFAULT_MODEL = "anthropic/claude-sonnet-4"`(`llm_client.py:40`) — 퇴역 모델 잔존.
   `model=""`로 bare `ask()` 호출 시(예: `summarize_key_issues`) OpenRouter 경로가 이 slug를 쓴다.
   기존 결함(범위 밖)이므로 **F1b(sonnet-5 이행) 트랙에 편입.**
2. growth rates 재계산(`profile_generator.py:1373-1393`)이 checkpoint(`:1395`) **앞**의 비보호 구간 —
   여기서 crash 시 여전히 피어 유실. 저위험이나 F1b 시 checkpoint를 이 앞으로 당기는 것 검토.
3. `logs/weekly_2026071{2..7}.log` 0바이트 건 — 별도 진단 (§6 유지).

### 다음 단계
1. 호스트에서 전체 pytest 1회 재확인 → 커밋
2. OpenRouter 크레딧 충전(F6, 사용자) → **T3 유료 측정** (E1 DoD #15~#18 + F4 산식 확정)
3. F5 예산표 개정 → F1b 트랙
