# HANDOFF — CODEX: LLM 운영 백로그 태스크 A(draft_blocked 렌더) + B(F1b sonnet-5) 검증·커밋

**작성일:** 2026-07-18 (Claude 세션, `9f70c65` 직후)
**트랙:** `NEXT_SESSION_llm_ops_residuals.md` 태스크 A + B(F1b). 게이트 3건도 이번 세션에서 판정 완료.
**요청:** ① 구현 독립 재현 ② NUL 스캔 ③ 커밋(2건 분리) ④ ask_structured 결정론 정책 확정본 회신
**루프 위치:** Claude 구축 → **Codex 검증** (`.claude/rules/codex-cross-review.md`. 내 주장도 믿지 말고 재현하라)

---

## 0. 게이트 판정 (증거 기반 — 백로그 전제 2건이 틀렸었다)

1. **Task Scheduler는 정상.** 7/18(토) 09:00 실제 주간 런 실행됨 (`logs/weekly_20260718.log` 8.5KB, 실제 HTTP 기록 + `_weekly_summary.json`의 Windows `week_dir` 경로). 주기 = **토요일** (7/11 토 12:41 → 7/18 토 09:00). "7/12~17 트리거 미발화"는 pytest 부산물(0바이트 로그) 오독 — 놓친 트리거 없음.
2. **OpenRouter 미충전.** 7/18 09:00 로그: `403 Key limit exceeded (total limit)`. → 태스크 C(T3 유료 측정)·D 계속 보류.
3. **가짜 아티팩트 정리 완료** (사용자 승인 후):
   - 삭제: `valuation-results/2026-07-1{2,3,4,5,7}(Jul 3rd week)/` **5개** (전부 mock 시그니처 `errors:["KR API 실패"]` + US `news_count:5` 확인) + 0바이트 `logs/weekly_*.log` 9개 (20260524, 0706, 0708, 0709, 0712~0715, 0717).
   - 백로그와의 차이: **7/16 폴더는 애초에 존재하지 않았고**(7/16은 hynix-deep-dive — 보존), **7/18 폴더는 실제 런 산출물이라 보존**.

## 1. 구현 diff (이번 세션분 — 정확히 이것만이 내 변경)

### 태스크 A — draft_blocked 카운트 렌더 (R16 완결)
1. `scheduler/delivery.py` `build_weekly_summary_gamma_text` (~:155): `- 게시 차단(draft): {n}개` 줄 추가 (무조건 렌더 — 기존 `실패:` 줄과 동일 관례).
2. `scheduler/delivery.py` `build_gmail_html` (~:395): ` · 게시 차단(draft): N개` 적색 span, **N>0일 때만** (기존 `실패:` 조건부 관례와 동일).
3. `scheduler/naver_poster.py` `build_blog_sections` (~:449): 헤더 라인에 ` | 게시 차단(draft): N개`, **N>0일 때만** (공개 블로그라 0일 때 노이즈 회피).
4. `tests/test_output.py`: `TestDraftBlockedRendering` 5건 신규 (렌더 3경로 × nonzero/zero).

### 태스크 B — F1b: sonnet-5 이행 + temperature 제거 (`ai/llm_client.py`)
1. `_OPENROUTER_DEFAULT_MODEL`: 퇴역 `anthropic/claude-sonnet-4` → `anthropic/claude-sonnet-5` (PLAN_r18 §8-2 잔여 관찰 1 편입분).
2. `MODEL_HEAVY`: `claude-sonnet-4-6` → **`claude-sonnet-5-20260630`** (pinned snapshot, latest alias 금지 준수). `_OPENROUTER_MODEL_MAP[MODEL_HEAVY]` → `anthropic/claude-sonnet-5`.
3. **temperature는 능력 기반 생략**: `_TEMPERATURE_UNSUPPORTED_PREFIXES = ("claude-sonnet-5", "anthropic/claude-sonnet-5", "claude-opus-4-7", "anthropic/claude-opus-4.7")` + `_supports_temperature(resolved_model)`. `_ask_anthropic`/`_ask_openrouter` 페이로드에서 미지원 모델일 때만 키 자체를 생략. **판정은 resolve 후의 provider별 ID 기준** → env override(`BVT_*_MODEL_HEAVY=claude-sonnet-4-6`)로 복귀 시 temperature 재전송됨.
4. `tests/test_llm_model_mapping.py`: 기존 매핑 기대값 2건 갱신 + 신규 4건 (heavy 생략 양 provider / light 유지 양 provider / 4.6 override 유지 / bare-ask 기본 slug 비퇴역).

**의도적으로 안 한 것 (조용한 이탈 아님 — 명시):**
- `ask_structured`의 haiku 경로는 `temperature=0` **그대로 유지**. "temperature=0 결정론" 재론은 방법론 사안이라 §4의 정책 확정 요청으로 분리 (PLAN_r18 §8-1 확정안 준수).
- `db/repository.py:235` `model: str = "claude-sonnet-4"` — API 호출 아닌 DB 라벨 기본값. 스코프 밖으로 판단, 미변경 (커밋 시 함께 고칠지 Codex 의견 가능).
- `schemas/provenance.py:127` — 주석 예시 문자열일 뿐, 미변경.

## 2. 내 검증 실측 (Codex: 전부 독립 재현하고 표 빈칸을 채워 보고하라)

| 항목 | 내 실측 (샌드박스) | Codex 재현 |
|---|---|---|
| `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` | **1084 passed, 5 deselected** (기준 1068 + 신규 9 = 1077; **잔여 +7은 샌드박스/호스트 수집 차이 추정 — 호스트에서 반드시 재확인**) | |
| `tests/test_output.py` | 30 passed | |
| `tests/test_llm_model_mapping.py` | 8 passed | |
| `ast.parse` + 줄수 (5개 파일) | delivery 402 / naver_poster 1230 / llm_client 458 / test_output 581 / test_mapping 196 — 전부 OK | |
| NUL 스캔 (rules 스니펫) | 5개 파일 0바이트 | (전체 트리 스캔으로) |
| EOL | delivery·naver·llm_client·test_mapping CRLF 유지, test_output은 **원래 LF** — 유지됨 | |

샌드박스 pip 추가분(호스트 무관): selenium, pillow, openpyxl, supabase, yfinance, socksio, portalocker.

## 3. 신규 관찰 — 7/18 실런이 돌았는데 **발굴 기업 0건** (신규 백로그, 이번 커밋 스코프 밖)

`logs/weekly_20260718.log` 증거:
1. **[P0 후보] discovery LLM JSON 펜스 파싱 실패**: OpenRouter 403 → Anthropic haiku 폴백 → 응답이 ` ```json ` 펜스 포함 → `AI JSON 파싱 실패 [KR]/[US]` → 양 시장 `companies=[]` → 주간 런 전체가 빈손. 펜스 스트립(파서 전처리)은 소규모 수정. **사용자 승인 대기 중 — 구현하지 말 것.**
2. `Failed to save discovery run` (09:00:03) — DB 저장 실패, 원인 미진단.
3. SaveTicker 0건 → "feed shape likely changed" 폴백 발동 (폴백은 정상 작동).
4. 네이버 포스팅 중 chromedriver 크래시 (로그 말미 스택).

## 4. 요청사항 (1번부터, 전 항목 응답 필수 — 누락 시 사전 통보)

1. §1 diff 독립 재현 + §2 표 빈칸 채워 보고 (자기에게 유리한 회귀만 확인 금지 — 표 전 행).
2. **작업 종료 직후 NUL 전체 스캔** (rules 스니펫 그대로, 출력 첨부).
3. 커밋 2건 분리: ① `feat(scheduler): draft_blocked 카운트 렌더 (R16 완결)` ② `feat(ai): F1b — sonnet-5 이행 + temperature 능력 기반 생략`. 스테이징은 이번 세션 변경 파일 5개만 (working tree에 다른 미커밋 작업 대량 — `git add -A` 금지).
4. **정책 확정본 회신**: `ask_structured`의 결정론 요구를 sonnet-5 시대에 어떻게 정의할 것인가. 쟁점: (a) haiku 경로 temperature=0 유지가 충분한가, (b) heavy 모델로 structured 호출이 필요해질 때 결정론 대체 수단(seed 없음)은 무엇인가, (c) json_mode(OpenRouter)와 Anthropic 직접 경로의 펜스 응답 차이 — §3-1과 연동됨. **코드 수정 전 확정본 먼저.**
5. (선택) §3 신규 관찰 4건의 우선순위 설계 평가.

## 작업 규칙 (필수)
- `git checkout --` / `git restore` / `git reset --hard` / `git stash` **절대 금지** (HEAD는 옛 베이스라인, 미커밋 작업 대량).
- 파일 수정 직후 `ast.parse` + 줄수. 원자적 쓰기 (임시 파일 → `os.replace`).
- CRLF 유지 (단 `tests/test_output.py`는 원래 LF — 그대로 둘 것).
- `engine/` 순수 함수 · Pydantic 직접 mutate 금지.
- LLM 실호출 금지 (OpenRouter 403 상태, 사용자 `.cache/llm/` 미삭제).
