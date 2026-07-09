# Plan: 프로젝트 전체 평가 & 정리 (CODEX 핸드오프 — 새 세션 시드)

> 이 문서는 **새 세션의 첫 프롬프트로 붙여넣는 시드**다. 목적은 상대가치 기능 하나가 아니라
> **BVT 프로젝트 전체를 평가하고 개선**하는 것. 먼저 저장소를 재현 가능한 상태로 만든 뒤 평가한다.
> 컨벤션: `AGENTS.md`(=Codex용 컨텍스트, ~/.Codex/AGENTS.md 상속) + 루트 `*_PLAN.md`/`HANDOFF_*.md`.

---

## 0. 세션 시작 시 필수 (backlog validation)

`AGENTS.md`의 규칙대로, 착수 전 반드시:

```bash
git log --oneline -15          # 무엇이 이미 shipped 됐는지
git status --porcelain | wc -l  # 미커밋 규모 확인
```

최근 shipped (건드리지 말 것, 이미 검증 완료):
- `2918696` feat(relative-valuation) — 상대가치 진단 레이어. Codex 3건 지적 반영 완료.
- `1b8cc57` fix(db) — Supabase 폐기 대응, `logger.exception`→`logger.warning`.

---

## 1. 최우선 리스크 — 거대한 미커밋 작업 트리 (평가 전 반드시 정리)

**현재 상태:** tracked 수정 ~126개 + untracked 다수. HEAD(`ddef6ca`)는 옛 baseline이고,
그 위에 **상호의존적인 미완/미커밋 기능**이 쌓여 있다. 이게 프로젝트 최대 리스크다 —
Codex가 지난 라운드에서 헷갈린 근본 원인도 "커밋 ≠ 작업 트리" 였다.

**미커밋 작업의 정체 (루트 HANDOFF/PLAN 문서가 단서):**

| 클러스터 | 단서 문서 | 관련 파일(추정) | 상태 |
|---|---|---|---|
| JP/EDINET 지원 | `HANDOFF_edinet_japan.md` | `pipeline/edinet_client.py`(방금 커밋됨), `data_fetcher.py`(JP 분기), `profile_generator.py`(JP), `yfinance_fetcher.py`(JP), `method_selector.py` | 미커밋 |
| JP 프로필 큐레이션 | `HANDOFF_jp_profile_curation.md` | `tests/test_jp_profile_curation.py`(untracked), `profiles/7203_t.yaml`·`6758_t.yaml`·`hmc.yaml` | 미커밋 (테스트 2건 실패 중) |
| Quality/Optionality | `HANDOFF_quality_optionality_2026-07-06.md` | `engine/quality.py`(rNPV 재구성), optionality 관련 engine | 미커밋 |
| Peer calibration | (untracked) | `calibration/peer_deviation.py`·`peer_fetcher.py`·`peer_report.py` | 미커밋 (신규) |
| SaveTicker US 뉴스 | `CODEX_PLAN.md` | `discovery/saveticker_collector.py` | 미커밋 (신규) |
| Codex 신뢰성 자동화 | `PROMPT_codex_reliability_automation.md`, `PROMPT_codex_round2.md` | ? | 확인 필요 |

**권장 조치 — 축별 논리 커밋 (새 세션에서, 마운트 안정 시):**

각 클러스터마다 `git diff -w -- <경로>` 로 실제 변경을 읽고 → 자기완결(import closure)인지
확인 → 논리 단위 커밋. `profiles/*.yaml`(26개 수정)은 **AI 재생성물이라 대체로 노이즈** —
필요한 대표 케이스만 커밋하고 나머지는 정책 결정(커밋 vs `.gitignore`).

> ⚠️ 커밋 시 **staged blob 완결성 검증 필수** (아래 §3의 함정 참조). 지난 라운드에서
> 마운트가 `git add`에 잘린 뷰를 넘겨 `cli.py`·`yfinance_fetcher.py`가 truncated 커밋됐다.

---

## 2. 평가 축 (evaluation axes) — 우선순위 순

1. **자기완결성 / 재현성** — 모든 커밋이 clean checkout에서 import·실행되는가?
   정적 import-closure 체크(§4) + `git archive <sha> | tar` 후 `python cli.py --profile ...`.
2. **정확성 / 회귀** — `pytest tests/` 기준. 현재 알려진 실패:
   - `test_engine.py::...test_sk_ecoplant_profile` (WACC 정확값 단정 — 프로필 드리프트)
   - `test_jp_profile_curation.py` 2건 (`7203_t.yaml` base_year 2025 vs segment_data 2026)
   → 이게 **실제 버그인지, 프로필/픽스처 드리프트인지** 판정 필요.
3. **테스트 커버리지 & CI 가능성** — `pipeline/ai/db` 테스트가 **네트워크/외부 API 의존**이라
   오프라인/CI에서 못 돈다(httpx SOCKS, DART, Supabase). 순수 로직과 IO를 분리해
   **네트워크 없이 도는 테스트 세트**를 정의할 수 있는가? (엔진은 이미 순수함수 → 가능)
4. **아키텍처 무결성** — `engine/` 순수성(IO 금지) 실제 준수 여부, `ValuationInput→ValuationResult`
   계약, **이중 진입경로 DB 비대칭**(`run_from_profile`은 저장, `auto_analyze`는 저장 안 함 — AGENTS.md L149).
5. **밸류에이션 방법론 타당성** — SOTP/DCF/DDM/RIM/NAV/rNPV 선택 로직, distress cap,
   시나리오 차별화(이미 enforced — AGENTS.md L66, 재구축 금지), reverse-DCF 진단.
6. **데드코드 / 폐기 정리** — Supabase(일시정지/폐기), 미사용 경로, 중복 `_save_to_db`.
   "쓸 거냐 뺄 거냐" 정책 결정 필요.

---

## 3. 환경 함정 (지난 라운드에서 실제로 문제됨 — 반드시 숙지)

1. **FUSE/마운트 캐시 truncation (치명적).** 편집·`git add` 시 파일이 **중간에서 잘린 뷰**로
   보일 수 있고, 잘린 지점이 우연히 유효 Python이면 `ast.parse`를 통과한다. →
   **완결성은 parse가 아니라 end-marker로 검증**하라(파일 끝 함수/`__main__`/특정 문자열 존재).
   대량 파일 조작 후 `git show <sha>:<file> | wc -l` 로 커밋 블롭 길이 재확인.
2. **EOL 노이즈 (CRLF vs LF).** 작업 트리는 CRLF, HEAD 블롭은 LF라 diff가 전부 바뀐 것처럼
   보인다(예: 20줄 변경이 `682/682`로 표시). **리뷰·평가는 `git diff -w --ignore-cr-at-eol`** 로.
3. **`profiles/*.yaml`는 AI 재생성물.** 주간 파이프라인이 덮어쓰고 시나리오 코드가
   Bull/Base/Bear ↔ A/B/C/D 로 드리프트. 테스트가 `profiles/`를 하드코딩 키로 로드하면 깨짐 →
   테스트 소유 YAML은 `tests/fixtures/`로 (상대가치에서 이미 그렇게 함).
4. **네트워크 의존 테스트.** `test_ai/test_pipeline/test_edinet_client/test_backtest_repository/`
   `test_market_signals` 등은 httpx/DART/Supabase 필요. 오프라인에서 collection 에러.
   평가 시 `--ignore` 로 분리하고 **엔진/스키마/상대가치 테스트로 신호 확보**.
5. **Supabase 폐기.** `getaddrinfo failed` = 프로젝트 일시정지로 호스트 소멸. DB 기능은 현재
   무력. `1b8cc57`로 트레이스백은 제거됨(경고 한 줄). 되살리려면 `SUPABASE_URL/KEY` + `db/migrations*.sql`.
6. **Windows `python -c` + 한글 → cp949 에러.** 저장된 `.py`로 실행하거나 `PYTHONIOENCODING=utf-8`.

---

## 4. 검증 프로토콜 (마운트/EOL 노이즈 우회)

```bash
# (a) 커밋을 오브젝트 스토어에서 추출 → FUSE·작업트리 오염 없이 진짜 커밋 내용 검사
git archive <sha> | tar -x -C /tmp/verify && cd /tmp/verify

# (b) 전체 parse 무결성 (truncated 파일 색출)
for f in $(find . -name "*.py"); do python -c "import ast;ast.parse(open('$f').read())" || echo BAD $f; done

# (c) import-closure 정적 검사 (1차 import가 커밋 안에서 다 해소되는지)
#     — from . import X / 상대 import(레벨>1)까지 처리해야 정확 (지난번 스크립트 버그 주의)

# (d) 런타임 스모크
python -m pytest tests/test_relative_metrics.py tests/test_relative_wiring.py -q   # 29 passed 기준선
python cli.py --profile profiles/aapl.yaml    # no-op 아님(전체 리포트) 확인

# (e) 실제 변경만 보기 (EOL 노이즈 제거)
git diff -w --ignore-cr-at-eol <base> <sha> -- <file>
```

---

## 5. 산출물 (이 평가가 만들어야 할 것)

1. **Findings 목록** — severity(Blocking/High/Med/Low) + 파일:라인 + 재현 + 근거.
   (지난 상대가치 라운드의 Codex 리포트 형식이 좋은 템플릿.)
2. **미커밋 정리 커밋 플랜** — 축별 커밋 순서 + 각 커밋의 import-closure 확인.
3. **우선순위 개선 백로그** — 방법론 타당성 > 자기완결성 > 테스트 격리 > 데드코드 순 권장.
4. (선택) **네트워크 없는 테스트 세트 정의** — CI 가능하게.

---

## 6. 참고 파일 지도 (AGENTS.md 요약)

- `engine/` 순수함수(IO 금지) · `schemas/models.py` 계약 · `pipeline/` IO 전담 ·
  `ai/` LLM · `db/` Supabase · `output/` Excel · `scheduler/`+`discovery/` 주간자동 ·
  `cli.py`/`orchestrator.py` 진입점.
- 방법론·gotcha 상세는 `AGENTS.md`(≈200줄) + `.claude/rules/*.md`(모듈별 스코프)에 있음 — **읽고 시작**.

---

### 새 세션 첫 프롬프트 예시

> "이 저장소(BVT) 전체를 평가하려 한다. `PROJECT_EVALUATION_BRIEF.md`를 먼저 읽어라.
> §0 backlog validation부터 하고, §1 미커밋 작업을 축별로 파악해 커밋 플랜을 제안하라
> (아직 커밋하지 말고 플랜만). 그 다음 §2 평가 축으로 Findings를 severity와 함께 정리하라.
> §3 함정과 §4 검증 프로토콜을 반드시 준수할 것 — 특히 완결성은 parse가 아니라 end-marker로 검증."
