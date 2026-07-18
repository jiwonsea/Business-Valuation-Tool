# HANDOFF — Codex Debate: 하우스키핑 결정 3건 + Phase 2b 착수 순서

작성: 2026-07-18 (Claude, 하우스키핑 세션). 루프: `.claude/rules/codex-cross-review.md` 준수.
선행: HEAD `a60f5b8` · pytest 1093 passed · NUL clean. 상세 이력: `HANDOFF_CODEX_commit_plan_pretracks_2026-07-18.md` §9~§10.

이 문서는 **결정 debate 요청**이다. 코드 작업 지시가 아니다. Codex는 아래 안건별로 평가 회신만 하라 (회신 형식은 §5).

🔴 공통 제약 (위반 시 회신 무효)
- `git restore / checkout -- / reset --hard / stash` 금지 — 잔여 dirty는 의도된 보류분.
- 이 debate 단계에서 파일 수정 금지. 조회는 read-only로만.
- git 조회 시 `GIT_OPTIONAL_LOCKS=0` 프리픽스 필수.

## §0 이번 세션에서 이미 확정·실행된 것 (debate 대상 아님)

1. verify_partB_excel.py · verify_partB_round2.py **폐기(삭제) 완료** — 기대값 stale (Nexus drift 4건, 0.45x 반올림 2건). cross-review 규칙 §말미 "완료 후 실행 목록"에서도 제거됨.
2. CLAUDE.md Session Safety 절 갱신 완료 — stale 문구 재서술 + `GIT_OPTIONAL_LOCKS=0` 규칙 명문화.

## §1 안건 A — T11 profiles 처리 (수정 12 + 신규 13 YAML)

### 선택지
1. `chore(profiles)` 커밋 1개로 스냅샷 정리 (호스트에서).
2. 계속 보류 (미커밋 유지).
3. `.gitignore`로 추적 제외 (AI-regenerated 산출물로 간주).

### Claude 입장: **선택지 1 (chore 커밋)**, 조건부.
근거:
- profiles는 이미 추적 중인 파일군이고 (`profiles/sk_ecoplant.yaml`은 README/CLAUDE.md 커맨드 예시), `065b9c7`에서 curated profiles를 feat로 커밋한 전례가 있다. 지금 와서 제외하면 이력이 반쪽이 된다.
- weekly 파이프라인이 rewrite하는 drift 문제는 **테스트 격리**(tests/fixtures/ 분리, 안건 C-1)로 푸는 것이 맞지, 추적 제외로 풀 문제가 아니다. 추적 제외하면 신규 13개(nexus.yaml 포함 — Phase 2 검증의 실측 대상)의 재현 기준점이 사라진다.
- 조건: 커밋 전 신규 13개 각각 `yaml.safe_load` 로드 확인 + NUL 스캔 (nexus.yaml은 과거 NUL 오염으로 로드 불가였던 전례 있음).
- 반대 논거 (Codex가 반박할 지점): AI-regenerated 파일의 커밋은 매주 노이즈 diff를 만든다. 이를 감수할 가치가 있는가? snapshot 커밋 주기를 정할 것인가?

## §2 안건 B — §4 잔재물 삭제 + .gitignore

### 대상 (실측 2026-07-18)
- 루트 따옴표 한글 파일 4개: `대상` `목적` `부모` `자기소개서에` (셸 리다이렉션 사고 잔재로 추정) + `type` (Windows `type` 명령 오타 잔재 추정)
- 루트 png 5개: `_hx_44_check.png` `_hx_p4_check.png` `_hx_seg.png` `_nvda_p2_check.png` `_p3.png`
- 디렉토리: `tmp/` `graphify-out/` `.playwright-mcp/` `.agents/`
- 루트 스크립트: `regen_nexus_artifacts.py`
- scripts/ 미추적 6개: `fill_peers.py` `nexus_dart_extract.py` `pilot_multiyear_quality.py`(v2는 추적됨) `r16_profile_delta.py` `verify_nvda_phaseA.py` `verify_nvda_phaseA_v2.py`

### 선택지
1. 전부 삭제 + 재발성 디렉토리(`tmp/`, `graphify-out/`, `.playwright-mcp/`, `.agents/`, 루트 `_*.png`)는 `.gitignore` 추가.
2. 삭제만 (.gitignore 불변).
3. 보류.

### Claude 입장: **선택지 1**, 단 scripts/ 6개는 개별 판단.
근거:
- 따옴표 한글 파일·`type`·png·`tmp/`·`graphify-out/`은 명백한 일회성 잔재. 삭제 무손실.
- `.playwright-mcp/` `.agents/`는 도구 세션 아티팩트 — ignore가 정석.
- scripts/ 6개 중 **개별 판단 필요분**: `nexus_dart_extract.py`(Phase 2 실측 재현 스크립트 — 추적 가치 있을 수 있음), `pilot_multiyear_quality.py`(v2가 추적됨 → v1 폐기 타당), phaseA 계열 2개(phaseB/C가 추적됨 → A는 superseded 추정). Codex는 각 스크립트가 커밋된 상위 버전에 완전히 포섭되는지 diff로 확인 후 폐기/추적을 개별 판정하라.
- 반대 논거: 루트 `_*.png` glob ignore는 향후 정당한 산출물을 가릴 수 있다. ignore 패턴의 과잉 여부를 평가하라.

## §3 안건 C — Phase 2b 착수 순서 (범위 계약 문서 선행, 코드 선행 금지)

후보 (Phase 2 문서 `HANDOFF_CODEX_phase2_impl_scope_2026-07-18.md` §12.4):

1. B6 `TestScenarioDriverRoundTrip` fixtures 분리 — deselect 해제 조건.
2. B2 신규 회사 실수집 — quota 계약 확정본 있음 (§7-3 수정 채택본).
3. B1 미커버 필드 eps/bps/dps/roic/fcf — `STATEMENT_CONTRACT` 확장 = 파서 계약 재개봉.
4. B3 분할 전 raw close 복원 (삼성 FY2016-17 n=8→10).
5. B4 非12월 결산 FYE 일반화.
6. B5 D&A 주석 경로 — **허용 배수 확장(EV/EBITDA) 결정 전 착수 금지** (죽은 코드).

### Claude 입장: **B6 → B2 순서**.
근거:
- B6는 A급 소규모·계약 재개봉 없음·즉각 효용(deselect 규칙 해제, 안건 A의 drift 문제 해소와 직결). 첫 타깃으로 리스크 최소.
- B2는 유일하게 계약 확정본이 존재 → 계약 작성 비용 0. 단 네트워크 예산 게이트(최소 예상치 산정 → 캐시 hit/miss 보고 → 사용자 승인 전 네트워크 0) 엄수.
- B1은 fixture·별칭·quota 미니 게이트가 전부 미작성이라 착수 비용이 가장 크다. B3/B4는 B2 실수집 결과가 있어야 검증 표본이 생긴다 (순서 의존).
- 반대 논거: B6는 효용이 테스트 위생에 국한된다. B2를 먼저 해서 실데이터를 넓히는 것이 calibration에 더 급한가? Codex는 backtest/calibration 관점에서 우선순위를 재평가하라.

## §4 Phase 2 산출물 접근 계약 (Phase 2b 전체 불변 제약)

재무값은 `extract_reported_values`+`select_point_in_time`만 · 허용 배수 LTM P/B·P/S만 · forward 금지.

## §5 Codex 회신 형식 (필수)

1. 안건 A/B/C 각각: 판정 (GO / CONDITIONAL GO / NO-GO) + [필수]/[권고] 구분된 조건 목록. **번호는 1번부터** (과거 2회 누락 사고).
2. Claude 입장에 동의하지 않는 항목은 **독립 근거 제시** (파일·diff·수치 인용). "동의" 한 줄 회신 금지.
3. 안건 B의 scripts/ 6개는 **표로** (스크립트명 | superseded 여부 | diff 근거 | 폐기/추적 판정). 빈칸 금지.
4. 이 단계에서 파일 수정 금지. 수정 제안은 회신 텍스트로만.
5. 회신 후 Claude가 독립 재현·반박/수용 판정 → 확정본 합의 → 그 다음에야 실행 (커밋·삭제는 호스트).
