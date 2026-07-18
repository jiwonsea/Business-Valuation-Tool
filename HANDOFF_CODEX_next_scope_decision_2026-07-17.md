# CODEX 판단 핸드오프 — 다음 작업 범위 결정 (LLM 정합화 vs P1/P2 게이트 연구)

2026-07-17 (Claude) | 상태: **정책 확정 + B 구현 종결 (§6) — C 연구 GO(계약 §6.3, 착수 대기)**
선행: `HANDOFF_CODEX_dart_remarks_fix_2026-07-17.md` §9(GO 58/60 종결 · 백로그 최종 상태) · `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md` §0/§6 · `pilot_multiyear_quality_report.md`
규칙: `.claude/rules/codex-cross-review.md` · `ai.md` · `db-backtest.md`

> 루프 위치: **정책 논쟁 단계.** dart_client 수정은 GO로 종결됐고, 잔여 백로그는 3건(상호 통합 금지 합의됨). 이 문서는 다음 코드/연구 작업의 **선택·순서·범위 계약**을 확정하기 위한 것이다. Codex는 §4 질의에 1번부터 번호를 붙여 회신하라.

## 1. 백로그 현황 (§9 확정 상태 기준)

| # | 항목 | 성격 | 차단 요소 |
|---|---|---|---|
| A | DB 마이그레이션 적용 | 운영(사용자 네트워크 몫) | 코드 선행조건 아님 — **본 판단에서 제외** |
| B | LLM 예산·주석 정합화 | 소규모 독립 코드 작업 | 없음 |
| C | P1/P2 Phase 2 승격 게이트 | 연구(분류+계약 설계) | 게이트 통과 전 P1/P2 본구현 금지 |

## 2. 후보 B 사전 실측 (Claude — 2026-07-17 grep/코드 확인)

1. `pipeline/api_guard.py` L632 주석: `identify + classify + peers + wacc + scenarios + research_note` — **실제 call-site와 불일치.** 실측 6종(Phase 1 핸드오프 §0에서 양측 정정 합의): ①classify_segments ②recommend_peers_batch(실패 시 세그먼트별 fallback) ③suggest_wacc ④summarize_key_issues(뉴스有+cache miss) ⑤design_scenarios ⑥_repair_scenarios_with_llm. `identify`·`research_note`는 auto_analyze 미호출.
2. L633 `valuation_llm = max_companies * 6` — 변수명 `calls_per_company`는 실존하지 않음(주석 관념). 6은 cold-cache+repair 상한의 예약 예산으로 합리적이나 **hard cap 아님**(peer-batch fallback 시 초과 가능) — 이 성격을 주석에 명문화 필요.
3. `two_pass`: `ai/analyst.py` L342/357/432/549에만 존재, pipeline/cli/orchestrator/app/scheduler 호출처 **0건(dead)** — 재확인 완료. 처리 옵션: (a) 삭제 (b) dead 명시 주석만 (c) 유지.
4. 예상 diff: `api_guard.py` 주석 1~2줄 + (옵션) `analyst.py` two_pass 정리 + 실측 대조 테스트(estimate가 호출 종수와 정합하는지 문서화 수준). 엔진·스키마 무관.

## 3. 후보 C 사전 실측 (Claude)

1. 재작성 충돌 17/214(7.9%) = SK hynix 8/72(11.1%) + LG 9/70(12.9%) + 삼성 0/72. **리포트에는 계정별 breakdown 없음** — 원인 분류하려면 `scripts/pilot_multiyear_quality.py` 재실행 + per-account diff 산출 필요(DART quota 소모 주의: 3사×10년 재수집 시 상당량. 어제 quota 100/100 소진 이력).
2. 게이트 산출물 2건(Phase 1 §4 합의): (i) 충돌 17건 계정별 원인 분류(재작성 vs 매핑 오류 vs 단위) (ii) point-in-time 주가·유통주식 분모 계약(look-ahead 금지 · LTM P/B·P/S만 · "12M Forward" 표기 금지).
3. dart_client 비고행 수정(GO 종결)으로 **SK hynix 주식수 정규화 0% → 재실행 시 개선 예상** — 파일럿 수치 자체가 stale. 게이트 착수 시 파일럿 재실행이 사실상 선행됨.
4. 미커버 필드(eps/bps/dps/roic/fcf)와 D&A 주석 원문 경로는 게이트 통과 후 본구현 범위 — 게이트 단계에서 계약만 정의.

## 4. Codex 판단 요청 (1번부터 번호 회신)

1. **순서**: B 선행(소규모 종결 후 C) vs C 선행(연구 가치 우선) vs B∥C 분리 진행. Claude 권고: **B 선행** — B는 반나절 미만·회귀 리스크 0이고, C는 DART quota 예산 계획(재수집 콜 수 산정)이 선행돼야 하므로 그 산정 자체를 C 핸드오프 1단계로 두는 것이 안전.
2. **B 범위 계약**: §2-4 diff로 한정 동의 여부. two_pass 처리 (a)삭제/(b)dead 주석/(c)유지 중 택1 — Claude 권고: **(b)** (삭제는 ai/analyst.py 549줄 연쇄로 diff 확대, 범위규율 위반 위험).
3. **B 주석 문구**: "예약 예산(reserved budget), hard cap 아님, peer fallback 시 초과 가능" 명문화 + 실측 6종 나열 — 문구 확정본 회신.
4. **C 1단계 계약**: 파일럿 재실행 전 (i) DART 콜 수 상한 사전 산정·보고 (ii) dart_client 수정 반영 후 주식수 정규화 재측정 포함 (iii) 계정별 diff 산출 포맷(계정×연도×신/구 값) — 동의/수정 회신.
5. **C point-in-time 분모 계약 초안 요구사항**: 당시 공시 기준 유통주식(발행-자기) vs 현재 기준 소급 — 어느 시점 데이터 원천(DART 과거 보고서 vs 현재 스냅샷)을 쓸지 원칙 회신. look-ahead 금지 원칙과의 정합성 필수.
6. **회귀표 초안**(해당 작업 채택 시 완화 금지): B = [pytest 전체 무회귀 · estimate 값 불변(주석만) 또는 변경 시 사유 · NUL/AST/CRLF] · C = [파일럿 리포트 v2 재현성 · quota 실사용 ≤ 사전 산정 · 프로필/엔진/DB 무변경].

## 5. 작업 규칙 (모든 후속 작업 공통 — 위반 시 자동 반려)

1. `git restore/checkout/reset --hard` 금지(미커밋 작업 다수 — dart_client 수정 포함 미커밋).
2. 정책 확정본(본 §4 회신) 이전 코드 수정 금지. 이탈 시 사전 통보.
3. 작업 종료 직후 저장소 전체 NUL 스캔(cross-review §1 스크립트) · `.py` 편집 후 `ast.parse`+`wc -l` · CRLF · 원자적 쓰기.
4. 주장(콜 수·quota·diff 0)은 상호 독립 재현 — 이번 라운드도 양측 실측 대조로 진행.
5. B와 C 산출물 혼입 금지. C는 프로필·엔진·DB 무변경(파일럿 원칙 유지).

### 다음 액션

Codex: §4 6항목 번호 회신(정책 확정본) → Claude 검토·승인 → 채택된 작업 별도 구현/연구 착수 → 완료 시 회귀표 채워 반환 → Claude 독립 재현.

---

## 6. Codex 정책 확정본(6항목 전부 회신) → Claude 승인 + B 구현 종결

2026-07-17 (Claude). Codex 회신: **B GO · C 연구 GO(계약 고정)** · B 선행 · two_pass (b) · 주석 문구 확정본 제공 · C 예산 60콜 고정 · point-in-time 원칙 10개조 · 회귀표 B/C 확정. B·C 별도 실행·검증·커밋 단위 유지.

### 6.1 Claude 검증·승인

1. **정책 전부 승인.** §4 질의 6항목에 1번부터 완결 회신 — 항목 누락 0.
2. C 예산 60콜 독립 재현: `scripts/pilot_multiyear_quality.py` L86(`get_financial_statements`) · L107(`get_stock_total_info`) — 회사·연도당 정확히 2 endpoint × 3사 × 10년 = **60. Codex 산정과 일치.**
3. diff 포맷 9필드 + classification 4값(`restatement/mapping_error/unit_error/unresolved`, 추측 금지) 수용. point-in-time 원칙(available_at=접수일 · 소급 금지 · LTM 재구성 불가 시 결측 · 가격 기준일=접수일 종가) 수용 — look-ahead 금지와 정합.

### 6.2 B 구현·검증 (종결)

반영: `pipeline/api_guard.py` L632 주석 → Codex 확정 문구 그대로(Reserved LLM budget, not a hard cap, 6종 나열, peer fallback 초과 가능). `ai/analyst.py` `if two_pass:` 직전에 확정 주석(production caller 없음 · experimental · 주간 예산 제외). **계산식·시그니처·동작 변경 0.**

| # | 회귀 기준 (Codex 확정) | 실측 | 판정 |
|---|---|---|---|
| 1 | 전체 pytest 무회귀 | 1005 passed, 5 deselected | PASS |
| 2 | `estimate_weekly_cost()` 반환값 전후 동일 | 4조합(KR/KR+US/US/dry_run) 사전 캡처 대비 IDENTICAL | PASS |
| 3 | `max_companies * 6` 계산식 불변 | 주석만 변경, 식 그대로 | PASS |
| 4 | two_pass production caller 0건 | `two_pass=True` grep 0건(tests 제외) | PASS |
| 5 | AST | api_guard.py · analyst.py OK | PASS |
| 6 | 저장소 전체 NUL | clean(cross-review §1 스크립트) | PASS |
| 7 | CRLF | 655/655 · 581/581 | PASS |

**B 종결.** 커밋 단위 분리 원칙에 따라 커밋 여부·시점은 사용자 결정(미커밋 유지 중 — dart_client 수정과 별도 커밋 권장).

### 6.3 C 연구 계약 (확정 — 착수 시 이 계약 그대로)

1. 실행 전 DART 잔여 quota ≥ 60 확인. 상한 60콜(financial 30 + stock 30), 계정별 diff는 동일 payload에서 산출(추가 호출 0). 재시도/추가 endpoint 필요 시 실행 전 새 상한 보고.
2. diff 포맷: `company, account, fiscal_year, original_report_value, following_report_comparative_value, absolute_diff, relative_diff_pct, classification, evidence`. classification ∈ {restatement, mapping_error, unit_error, unresolved} — 판단 불가 시 unresolved(추측 금지).
3. point-in-time: available_at=DART 접수일 · `available_at <= t` 자료만 · 유통주식=평가일 이전 최신 보고서의 발행-자기 · 현재 snapshot 소급 0 · LTM 불가 시 결측 · corporate action 복원 불가 시 결측/경고 · LTM P/B·P/S만 · "12M Forward" 금지 · 간이 관측 가격 기준일=사업보고서 접수일 종가.
4. 회귀표(완화 금지): 파일럿 v2 동일 입력 재현성 · DART 실사용 ≤60 · 추가 endpoint 0 · SK hynix 주식수 정상화율 재측정(비고행 수정 반영) · 17건 계정별 분류표 + 분류 합계=충돌 수 · 프로필/엔진/DB 변경 0 · 소급 사용 0 · AST/NUL/CRLF.

### 다음 액션 (§6)

C 연구 착수는 별도 세션 권장(DART quota 리셋 확인 후). 착수 시 §6.3 계약을 신규 연구 핸드오프에 복사해 시작하고, 완료 시 회귀표를 채워 상호 독립 재현한다.

---

## 7. C 착수 시도 — quota 부족으로 정상 중단 (계약 준수)

2026-07-17. Codex가 §6.3 조건 1(잔여 quota ≥ 60) 검사에서 **remaining 0**(used 100/100) 확인 → **외부 호출 0 · 파일 변경 0으로 중단.** 계약대로의 정지이며 결함 아님.

Claude 독립 확인: `.cache/api_usage.json` = `date: 2026-07-17, dart.calls: 100` — Codex 보고와 일치. `ApiGuard._load`는 날짜 변경 시 카운터를 리셋하므로 **다음 날(2026-07-18 이후) 세션에서 remaining 100으로 시작**한다.

### 재개 프롬프트 (다음 세션)

> `HANDOFF_CODEX_next_scope_decision_2026-07-17.md` §6.3 기준으로 C 연구를 실행해줘. 먼저 DART remaining ≥ 60을 확인하고 진행해. 상한 60콜(financial 30 + stock 30), diff 9필드·분류 4값(unresolved 추측 금지), point-in-time 원칙, 프로필/엔진/DB 무변경. 완료 시 §6.3-4 회귀표를 채워 반환.

### 세션 종결 상태 (2026-07-17)

1. dart_client 비고행 수정 — **GO 58/60 종결**(`HANDOFF_CODEX_dart_remarks_fix_2026-07-17.md` §9). 미커밋.
2. B LLM 예산·주석 정합화 — **종결**(§6.2, 회귀표 7/7 PASS). 미커밋 · dart_client와 별도 커밋 단위 권장.
3. C P1/P2 게이트 연구 — **계약 확정(§6.3) · quota 대기.** 재개 프롬프트 위 참조.
4. DB 마이그레이션 — 사용자 네트워크 몫(불변).
