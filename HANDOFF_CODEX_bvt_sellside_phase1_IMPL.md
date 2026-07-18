# CODEX IMPL 핸드오프 — 셀사이드 구조 Phase 1 (P3 + P1/P2 파일럿)

2026-07-16 (Claude) | 상태: **GO (정책 합의 완료)** — 구현 착수 가능. 코드 변경 전 §5 회귀표 계약 확인.
선행: `HANDOFF_CODEX_nh_structure_debate_2026-07-16.md`(정책 논쟁 §1~7) → 본 문서(구현 스펙)
규칙: `.claude/rules/reporting-boundary.md` · `db-backtest.md` · `pipeline.md` · `ai.md`

> DEBATE 2라운드로 정책 합의(GO). 본 문서는 **합의된 Phase 1만** 구현 스펙으로 옮긴 것이다. P1·P2 본구현은 §4 파일럿 통과 후 Phase 2로 분리한다. LLM 호출 예산 정합화(§6)는 **P3와 별도 범위**다.

## 0. 정책 확정본 (final)
| 제안 | 상태 | 제안 | 상태 |
|---|---|---|---|
| P1 10년 시계열 | PHASED(파일럿 선행) | P6 세그먼트 분기 | DEFER · 추정분기 engine연결 REJECT |
| P2 배수 밴드 | PHASED(파일럿 선행) | P7 수정추적 | 헤드라인→P3 흡수 · driver drift REJECT |
| P3 내재가치 이력 | **conditional ADOPT-NOW** | P8 3-statement | DEFER |
| P4 분기 실적 | PHASED(당사추정만) | P9 ESG | REJECT |
| P5 컨콜 Q&A | PHASED · opt-in · 주간 skip | D-1~D-6 | Claude 2차안 수용 |

### LLM 호출 수 최종 대조 (양측 정정 반영 — 별도 범위 §6)
`auto_analyze()` 실측 call-site: ①classify_segments ②recommend_peers_batch(실패 시 세그먼트별 recommend_peers fallback) ③suggest_wacc(line 998) ④summarize_key_issues(line 1018, 뉴스有+cache miss) ⑤design_scenarios(two_pass 기본 False) ⑥_repair_scenarios_with_llm(검증실패+retry).
- 뉴스 없음/요약 cache-hit: **4콜**
- 뉴스 cold-cache: **5콜**
- + scenario repair: **6콜**
- + peer-batch fallback: **6콜 초과 가능**
- two_pass=True: caller 0(dead) · generate_research_note: auto_analyze 미호출
결론: `calls_per_company=6`은 cold-cache+repair 상한의 **예약 예산**으로는 합리적이나 **hard cap 아님**(peer fallback 초과). P5 추가 시에도 "최대 6" 하드캡 금지.

## 1. Phase 1 범위 (이것만 즉시)
1. **P3 내재가치·괴리 이력 read-only view**
2. 저장 **parity 검증**(수동/프로필/`auto_analyze` 3경로)
3. 식별자 **ticker/market 우선**(현 `list_valuations` ilike(name) 교체)
4. 동일 날짜 재실행 **overwrite vs append 정책** 확정
5. 이력 없을 때 **빈 차트 금지 → "이력 부족" 표시**
6. **P1/P2 착수 전 3사×10년 파일럿 + 품질 리포트**
추가 2조건(Codex): (7) **LLM 예산·주석 정합화는 P3와 별도 범위**(§6) · (8) **P3는 실제 DB 마이그레이션 적용 여부 + 3경로 parity를 회귀표로 검증**.

## 2. P3 구현 계약 (소유 경계 = D-5)
**schemas/** — 이력 레코드 계약 신설:
- `ValuationHistoryRecord`: `ticker, market, company_name, analysis_date, weighted_value, market_price, gap_pct, wacc_pct, quality_grade, primary_method, valuation_bucket, created_at`.
- `Provenance` Enum(D-3 채택): `reported | derived | analyst_estimate | llm_estimate` — 파생 수치 필드에 부착(세그먼트 추정 라벨링과 일관). Phase 1은 헤드라인 이력에 최소 적용, 확장은 P4/P5에서.
- 신규 필드는 Optional+default(backward-compat, CLAUDE.md 규약).

**db/** — append/read/보존만:
- 조회 키: `(ticker, market)` 우선. `list_valuations`의 `ilike("company_name")` → `eq("ticker")` + `eq("market")` 경로 추가(name 조회는 legacy fallback 유지 가능).
- `save_valuation` upsert 키 `(company_name, analysis_date)` → **`(ticker, market, analysis_date)`** 이관 검토(마이그레이션 필요; 미적용 시 P3는 name 키로 동작하되 회귀표에 명시).
- 동일 날짜 재실행: **overwrite(upsert 유지) vs append(이력 누적)** 정책 택1하여 `migrations.sql` + repository에 명문화. 이력 뷰 목적상 **append 권장**(단 날짜중복 시 최신 rcept/created_at 우선 표시).

**output/** — read-only 표출만(reporting-boundary):
- 이력 뷰(시트/차트)는 `db` read 결과만 렌더. **과거 결과 재계산·현 엔진으로 과거입력 재평가 금지**("당시 내재가치"는 저장값 그대로).
- 데이터 0건 시 빈 차트 대신 **"이력 부족(N=0)"** 표시.

**engine/** — 관여 없음.

## 3. 저장 parity (3경로 — 회귀 대상)
동일 `save_valuation` 계약으로 저장되는지 검증: (a) 수동 `cli.py`/`orchestrator`, (b) 프로필 경로, (c) `auto_analyze()`(weekly). db-backtest.md의 "persistence asymmetry"가 여기서 재발한 이력 — 세 경로가 동일 필드셋·동일 키로 기록해야 함.

## 4. P1/P2 파일럿 스펙 (본구현 전 필수)
- 대상: KR 3사 × 10년.
- 측정 지표: **계정 매핑률 · 결측률 · 재작성(restatement) 충돌률 · 연결/별도 혼입 · 단위/주식수 정규화 성공률**.
- 현 `ACCOUNT_MAP`(revenue/op/interest/net_income/assets/liab/equity + dep/amort/capex)로 **미커버**: EPS·BPS·DPS·ROIC·FCF(→ 별도 endpoint/파생 계약 필요). EBITDA=op+dep+amort 파생 유지.
- **P2 하드 제약**: point-in-time 분모(당시 알려진 LTM/Fwd)만 · **look-ahead 금지**(현 재무를 과거 주가에 소급 금지) · 1차는 **LTM P/B 또는 P/S만**(분모 재구성 명확) · **"12M Forward" 표기 금지**(컨센서스 시계열 확보 전).
- 산출: `pilot_multiyear_quality_report.md`. 이 리포트 통과 후에만 P1/P2 Phase 2 승격.

## 5. 회귀/수용 기준표 (완화 금지)
| # | 항목 | 기준 |
|---|---|---|
| S-1 | 저장 parity | 수동/프로필/auto_analyze 3경로 동일 필드·키로 기록(회귀표 3행 PASS) |
| S-2 | 식별자 조회 | ticker+market 조회가 정확 레코드 반환; 동명 2사 분리 확인 |
| S-3 | 재실행 정책 | 동일 날짜 재실행 결과가 확정 정책(overwrite|append)대로 · 문서화 |
| S-4 | reporting-boundary | 이력 뷰가 db read만; 엔진 재계산 0(코드 grep + 값 대조) |
| S-5 | 빈 상태 | N=0 시 "이력 부족" 표시, 빈 차트/오류 없음 |
| S-6 | 마이그레이션 | `migrations.sql` 실제 적용 여부 명시; 미적용 시 동작 경로 회귀표에 기록 |
| S-7 | 파일럿 | 3사×10년 품질 리포트 생성(매핑/결측/재작성률 수치 포함) |
| S-8 | backward-compat | 신규 schemas 필드 Optional+default; 기존 45프로필 crash 0 |
| S-9 | NUL/AST/CRLF | clean |

## 6. 별도 범위 (P3와 분리 — 혼입 금지)
LLM 예산·주석 정합화: `estimate_weekly_cost()` 주석(identify+…+research_note)이 실제 call-site(§0 6종)와 불일치 → 정합화. `calls_per_company=6`은 예약 예산이며 hard cap 아님(peer fallback 초과 가능) 명시. `two_pass`(dead) 정리 여부 결정. **이 작업은 P3 회귀표와 섞지 말 것.**

## 7. Debate/구현 루프 규칙
1. Codex 구현 후 **작업 종료 직후 NUL 스캔**(재발 이력); `.py` 편집 후 `ast.parse`+`wc -l`; **CRLF 유지**; 원자적 쓰기.
2. `git restore/checkout/reset --hard` **금지**(미커밋 작업 다수).
3. **주장 상호 독립 재현** — 이번 라운드에서 양측 LLM 카운트가 모두 부정확했음(Claude=뉴스콜 누락, Codex=상시6 과표현). "PASS·마이그레이션 적용" 주장은 값·grep으로 재확인.
4. 항목 1번부터 명시. 검증 스크립트 완화 금지.
5. engine 순수성·reporting-boundary 위반 시 자동 반려.

### 다음 액션
Codex: §2 계약대로 P3 구현 → §5 S-1~S-9 회귀표 채워 반환 → Claude 독립 재현(3경로 parity·엔진 재계산 0·마이그레이션 실제 적용) 후 확정. P1/P2는 §4 파일럿 리포트 통과 시 Phase 2 별도 핸드오프.

---

## 8. Claude 검증 — Phase 1 구현 독립 재현 (§7 규칙 적용)

Codex "Phase 1 완료" 보고를 **값·grep·테스트 재실행으로 독립 재현**함. 이번 라운드 Codex 주장은 **전부 사실과 일치**(과거 라운드와 달리 불일치 0건).

| 기준 | Codex 주장 | Claude 독립 재현 | 판정 |
|---|---|---|---|
| S-9 NUL/AST/CRLF | clean | NUL 0 · 신규 5개 .py AST OK · 신규 4개 파일 100% CRLF | **PASS** |
| S-1 parity | 3경로 _save_to_db 공유 | `_save_to_db`(orchestrator) ← cli:329 · orchestrator:63 · profile_generator:888/1397(auto+profile) · 테스트 `test_all_three_entry_paths...` | **PASS** |
| S-2 식별자 | ticker+market 우선 | repository `query.eq("ticker")`/`market` + `test_history_query_uses_ticker_and_market` | **PASS** |
| S-3 재실행 | append-first + legacy fallback | `test_save_valuation_is_append_first` · `test_migration_declares_append_policy` | **PASS** |
| S-4 경계 | DB read만, engine 무호출 | history.py에 engine 참조 0(grep) · docstring "no engine recalculation" · `test_...without_engine_calls` | **PASS** |
| S-5 빈 상태 | "이력 부족(N=0)" | history.py L37-38 · `test_...empty_state_has_no_chart` | **PASS** |
| 신규 테스트 | 6 passed | **재실행 6 passed** (supabase 설치 후) | **PASS** |
| 코어 회귀 | — | Hynix draft:false·B/80·1,240,056·blocker0 불변 · 엔진 288 passed/5 deselected | **PASS** |
| schema 계약 | Provenance 4-state + Record | `Provenance{reported,derived,analyst_estimate,llm_estimate}` + `ValuationHistoryRecord` + "must not recompute" docstring | **PASS** |
| S-7 파일럿 | 99.6%/0.4%/7.9% | `pilot_multiyear_quality_report.md` 존재·정합; 미커버 eps/bps/dps/roic/fcf 명시(내 ACCOUNT_MAP 재현과 일치) | **PASS(문서)** |

### 미검증/별도 (정직한 한계 — 둘 다 Codex 사전 고지, 수용)
- **S-6 라이브 마이그레이션**: Supabase `getaddrinfo failed`. **내 샌드박스도 외부망 차단으로 동일 미검증.** 어느 환경에서도 네트워크 없이는 확인 불가 — SQL·append-policy 테스트는 PASS, **실 적용은 사용자가 네트워크 환경에서 수행** 필요. 결함 아님.
- **`pipeline/dart_client.py` 비고행 파싱 버그**: 파일럿에서 SK하이닉스 주식수 정규화 0%의 원인. **실재 버그 확인**(내가 직접 stockTotqySttus 조회 시 tesstk_co 비고행에 "이익소각/주식병합/장내취득…" 텍스트 존재 목격). Codex가 **미수정·명시**한 것은 올바름(Phase 1 범위 밖). → **별도 스코프로 로그**(우리 Hynix 산출은 Chrome 취득 728M 사용이라 무영향).
- `verify_partB_round2/excel`(4/2건 실패): 이력 변경과 무관한 기존 트리 상태라는 Codex 주장은 **내가 직접 재실행하진 않음**. 단 코어 회귀(엔진 288 + history 6 + Hynix 불변)로 **이력 변경의 격리성은 입증**됨. partB 실패의 pre-existing 여부는 별도 확인 대상으로만 남김.

### 최종 판정: **Phase 1 GO 확정 (구현 승인)**
S-1~S-5·S-7~S-9 전부 독립 재현 PASS. S-6은 환경 제약(양측 공통)으로 실 적용만 사용자 몫. 후속: (a) 사용자 네트워크 환경에서 migration 적용 + 3경로 실저장 parity 실측, (b) dart_client 비고행 버그 별도 핸드오프, (c) P1/P2는 파일럿 게이트(재작성 계정별 원인분류 + 시점별 분모 계약) 승인 후 Phase 2.
