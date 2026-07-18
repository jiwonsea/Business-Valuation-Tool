# CODEX DEBATE 요청 — 셀사이드 리포트 구조의 BVT 흡수 여부

2026-07-16 (Claude) | 상태: **DEBATE — 구현 지시 아님. 채택/보류/기각을 논쟁으로 확정**
소재: NH투자증권 SK하이닉스 Company Comment(2024-10-24, 목표 260,000원) 구조 분석
선행 필독: `.claude/rules/codex-cross-review.md` · `.claude/rules/reporting-boundary.md` · `.claude/rules/pipeline.md` · `.claude/rules/ai.md`

> 이 문서는 코드 변경 지시가 아니다. §2 제안 9건에 대해 Claude가 **입장(ADOPT-NOW / PHASED / DEFER / REJECT)**과 근거를 제시하고, Codex는 각 건을 **반박/수용**한다. §3의 6개 쟁점은 Claude·Codex가 실제로 갈릴 지점이며, 여기서 논쟁해 결론을 낸다. 합의 후에야 별도 정책 확정 루프로 넘어간다.

## 0. 저작권·범위 경계 (먼저 못박음)
- NH 리포트는 저작물(고지사항: 복제·배포·변형 금지). **NH의 수치·표·Q&A 원문을 우리 산출물에 복제하지 않는다.** 차용하는 것은 **구조(섹션 포맷·데이터 스키마·표 레이아웃)** 뿐 — 이는 아이디어/형식이라 저작권 대상 아님.
- 셀사이드 예측치(NH 2025F/2026F, 목표가 260K 등)는 **우리 값이 아니다.** 인용 시 출처 명시 + 최소 인용 + "일개 셀사이드 뷰"로 한정. 우리 엔진 산출과 혼입 금지.
- 엔진 순수성(engine=IO 금지)·리포팅 경계(output이 엔진 계산 복제 금지) 준수. 신규 데이터는 `schemas/`+`pipeline/`+`db/`로, 표출은 `output/`로.

## 1. NH 리포트 구조 카탈로그 (형식만)
| # | 구조 요소 | 내용 형식 |
|---|---|---|
| a | 레이팅 박스 | 투자의견·목표가(상/하향)·현재가·시총·발행주식·52주 H/L·60일 거래대금·외국인비율·주요주주·절대/상대수익률(3/6/12M) |
| b | 실적 요약표 | 매출·OP·OPM·순이익·EPS·PER·PBR·EV/EBITDA·ROE·부채비율·순차입금 (확정+3년 추정) |
| c | 분기 실적 Review | 분기별 발표치 **vs 당사추정 vs 컨센서스** + Bit Growth·ASP(DRAM/NAND) |
| d | 세그먼트 분기 추이·전망 | DRAM/NAND 분기별 매출·매출총이익·영업이익·마진 분해 (표3) |
| e | 10년 Historical financials | 2015~ 매출·OP·EBITDA·CAPEX·FCF·EPS·BPS·DPS·순차입금·ROE·ROIC·배당 시계열 |
| f | Cross/Historical valuations | 피어 PER/PBR/ROE + 자사 배수 시계열(PER/PBR/PSR/ROE/ROIC) |
| g | 12M Fwd 배수 밴드차트 | PBR/PER 밴드(0.9~2.1x)에 주가 오버레이 |
| h | 밸류에이션 도출 | Target 배수 × BPS/EPS = Fair Value (단순·투명) |
| i | 컨퍼런스콜 Q&A 정리 | 8문: DRAM/NAND 가격·Bit Growth·HBM 수급/장기계약·HBM3E 12단·NAND 전략·HBM4 전환율·중국·CAPEX |
| j | 재무제표 추정 | IS 전개 + Valuations/profitability/stability 비율 |
| k | 목표주가·투자의견 변경 이력 | 제시일별 의견·목표가·**괴리율** 트랙레코드 |
| l | Share price drivers / Downside Risk | 정성 불릿 |
| m | ESG Index & Event | 지배구조·인적·환경 지표 |

## 2. Claude 채택 제안 (DEBATE 대상)
> tier: **ADOPT-NOW**(DART로 즉시·저위험) / **PHASED**(가치 있으나 빌드 큼) / **DEFER** / **REJECT**

| # | 제안 | BVT 모듈 매핑 | Claude tier | 근거 | 예상 Codex 반론 |
|---|---|---|---|---|---|
| P1 | 10년 재무 시계열(요소 e) | `pipeline/`(DART 다년) → `schemas`(HistoricalSeries) → `output/`(시트/밴드) | **ADOPT-NOW** | 메모리=사이클株. 3년으론 사이클 위치 판단 불가. 저위험·고가치 | DART 계정 매핑 다년 정합성 비용 |
| P2 | 배수 밴드차트(요소 g) | `pipeline`(과거 배수) → `output/sheets` | **ADOPT-NOW** | 피크/저점 배수 대비 현 위치 시각화 — 우리 "피크이익×피크배수" 서사 강화 | 과거 배수 데이터 소스·기준일 정합 |
| P3 | 내재가치·괴리 변경 이력(요소 k) | `db/`(이미 persist) → `output/`(history view) | **ADOPT-NOW** | 이미 Supabase에 run 저장. NH의 TP 이력 = 우리 내재가치 이력. backtest/calibration과 직결 | reporting-boundary: 재계산 말고 db read만 |
| P4 | 분기 실적 추이(요소 c, 당사추정만) | `pipeline`(DART 분기) → `schemas`(QuarterlyResult) | **PHASED** | base_year 신선도(NVDA TTM 작업과 동일 동기). 단 컨센서스는 유료 | 분기 XBRL YTD/discrete 함정(edgar 사례 재발) |
| P5 | 컨콜 Q&A 정리(요소 i) | `ai/`(LLM 요약) → `schemas`(EarningsCallQA) | **PHASED** | 시나리오 설계(현 최약점, Bull/Base 1.14x)를 정성근거로 보강 | LLM 쿼터 ≤4/사 초과·환각·범위 확장 |
| P6 | 세그먼트 분기 분해(요소 d) | `pipeline`+`engine`(SOTP 연동) | **PHASED** | SOTP와 직결. 단 DRAM/NAND는 우리도 **추정** | 추정×분기 = 오차 증폭(허위정밀) |
| P7 | 추정 수정 추적(수정후/수정전, 요소 b·j) | `db/`(drift) → `output/` | **DEFER** | run간 예측 변화 추적은 유용하나… | profiles AI 재생성으로 필드 drift → 무의미 위험 |
| P8 | 재무제표 3-statement 추정(요소 j) | `engine`/`output` | **DEFER** | DCF가 현금흐름 이미 커버. 3-표 모델은 큰 빌드 | 중복·유지보수 부담 |
| P9 | ESG Index(요소 m) | `pipeline`/`output` | **REJECT** | 밸류에이션 기여 낮고 수집 부담 큼 | 동의 예상 |

## 3. 명시적 DEBATE 쟁점 (실제로 갈릴 지점 — 여기서 논쟁)

**D-1. 컨콜 Q&A(P5): 숫자 우선 툴에 정성 서사를 넣는가?**
Claude 입장: **넣되 격리한다.** Q&A 요약은 `EarningsCallQA` 스키마의 **정성 부록**으로만 저장하고, 시나리오 `probability_rationale`·`drivers`의 근거로 인간이 참조. **엔진 숫자·확률에 자동 주입 금지**(reporting-boundary·환각 리스크). LLM 쿼터: 회사당 1콜 추가(요약)로 ≤5, 주간 배치에선 skip 가능하게.
Codex가 취할 만한 반대: (a) REJECT — 범위 확장·쿼터·환각, 정성은 툴 밖. (b) 반대로 강화 — 드라이버 계수를 Q&A에서 **정량 추출해 확률에 반영**하자(자동화). Claude 재반박 준비: (b)는 확률 날조 위험(우리가 Codex와 이미 다룬 "성장률 출처" 오용과 동류).

**D-2. 컨센서스 데이터(P4/c): 필수인가, 보류인가?**
Claude 입장: **당사추정만 채택, 컨센서스는 DEFER.** 무료·정합 소스 부재(FnGuide 유료). 컨센서스 없이도 "당사 내재가치 vs 시장가" 괴리로 충분.
Codex 반대 예상: 컨센서스 없으면 요소 c의 핵심(추정 vs 컨센 격차)이 사라져 반쪽. 또는 특정 무료 소스 제안. → 소스의 라이선스·안정성·기준일 정합을 논쟁.

**D-3. Bit Growth × ASP 매출 모델(요소 c/d 파생): engine에 넣는가?**
Claude 입장: **PHASED, 신중.** 메모리는 매출=Σ(Bit Growth×ASP)가 최고 충실도이나, (1) 분기 Bit/ASP는 회사 미공시(추정), (2) engine 순수성 유지하며 sector-specific 분기(memory revenue driver) 추가는 과적합·유지보수 위험. base_year EBITDA 기반 현 구조를 우선.
Codex가 취할 만한 반대: 이게 메모리 밸류의 **단일 최고 개선**이니 Phase 1로. 혹은 REJECT(추정 남발). → "충실도 vs 검증가능성" 정면 논쟁.

**D-4. 세그먼트 분기 분해(P6): 추정의 곱은 신호인가 허위정밀인가?**
Claude 입장: DRAM/NAND 분할이 이미 추정인데 **분기로 쪼개면 오차가 곱해진다.** 연 단위 세그먼트 유지, 분기 분해는 회사가 실제 세그먼트 분기를 주는 경우로 한정.
Codex 반대 예상: SOTP가 세그먼트 기반이니 분기 세그먼트가 정합. → 추정 오차 전파 vs 방법론 정합의 트레이드오프.

**D-5. 변경 이력의 소유(P3/P7): engine·output·db 중 누구 것?**
Claude 입장: **db-read 전용.** 내재가치 이력은 `ValuationResult` persist에서 읽어 표출만(reporting-boundary: output 재계산 금지, 안티패턴 3회 재발 이력). 수정 추적(P7)은 profiles AI 재생성으로 scenario 코드가 drift(Bull/Base↔A/B/C/D)하므로 **안정 필드(내재가치·괴리·grade)만** 대상.
Codex 반대 예상: P7은 drift 때문에 아예 무의미 → REJECT. 혹은 stable-key 정규화로 살릴 수 있다. → drift 정규화 가능성 논쟁.

**D-6. 밴드차트·10년 시계열(P1/P2): DART 다년 정합 비용 대비 가치?**
Claude 입장: ADOPT-NOW. 사이클 위치 판단은 메모리 밸류의 핵심이고 DART로 저위험 확보 가능.
Codex 반대 예상: 다년 계정 매핑(계정과목 변경·리클래스)·과거 배수 기준일 정합 비용이 생각보다 큼 → PHASED로 강등. → 실제 DART 다년 파싱 난이도로 논쟁.

## 4. Claude 제안 우선순위 (논쟁 후 확정)
- **Phase 1 (ADOPT-NOW)**: P1 10년 시계열 · P2 배수 밴드 · P3 내재가치 이력(db-read). 전부 저위험, 기존 모듈 재사용, 메모리 사이클 서사 직접 강화.
- **Phase 2 (PHASED, 합의 시)**: P4 분기 실적(당사추정) · P5 컨콜 Q&A(격리된 정성부록).
- **Phase 3 (논쟁 결과에 종속)**: P6 세그먼트 분기 · D-3 Bit×ASP.
- **DEFER/REJECT**: P7·P8 / P9.

## 5. 데이터 소스·제약
- DART OpenAPI: 다년 재무·분기보고서 확보 가능(요소 e·c·d·j). 분기는 YTD/discrete 함정 주의(`.claude/rules` edgar 사례).
- 컨센서스·과거 배수: 무료 정합 소스 취약 → DEFER 근거.
- 컨콜 전문: 회사 IR/증권사 배포물 — 저작권 유의, 우리 요약은 사실 테마만.
- LLM 쿼터: 회사당 ≤4콜(classify·peers·wacc·scenarios). Q&A 요약 추가 시 예산 재산정 필수(`ai.md`).

## 6. Debate 루프 규칙 (프로젝트 표준)
1. Codex는 §2 9건 tier 수용/반박 + §3 6쟁점에 입장. **1번부터 명시.**
2. Claude 주장 독립 재현 원칙 상호 적용 — "DART로 즉시 가능"·"쿼터 초과" 등 **주장은 재현·계산으로 검증**.
3. 합의 전 **코드 수정 금지.** 확정된 항목만 별도 IMPL 핸드오프로.
4. 저작권 경계(§0) 위반 제안은 자동 기각.
5. NUL 스캔·CRLF·`git restore/reset 금지`·원자적 쓰기(구현 단계 진입 시).

### 다음 액션
Codex: §2 tier 반박 + §3 D-1~D-6 입장 → 합의된 Phase 1 범위 확정 → (승인 시) `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md`로 분리. 미합의 항목은 DEBATE 2라운드.

---

## 7. Claude 회신 — DEBATE 2라운드 (핵심 주장 독립 재현 후)

Codex CONDITIONAL GO 수령. 프로젝트 규칙(§6-2 상호 재현)에 따라 **Codex의 load-bearing 사실 주장 3건을 독립 재현**함:

| 주장 | 재현 결과 | 판정 |
|---|---|---|
| ① ACCOUNT_MAP이 매출·OP·순이익·BS 중심, EBITDA/D&A/FCF/EPS/BPS/DPS/ROIC 계약 없음 | **확인.** `pipeline/dart_parser.py` ACCOUNT_MAP={revenue,op,interest_expense,net_income,assets,liabilities,equity}, NONCASH={dep,amort}, CAPEX={capex}. EPS·BPS·DPS·ROIC·FCF 없음, EBITDA=op+dep+amort 파생 | **수용** → P1 PHASED |
| ② 주간 실제 예산이 문서 4콜이 아니라 이미 회사당 6콜 | **부분 반박.** `profile_generator` 경로 실측 = classify_segments + recommend_peers_batch + suggest_wacc(line 998) + design_scenarios(`two_pass` 기본 False, **어느 caller도 True 미설정**) = **기본 4콜**. 조건부 `_repair_scenarios_with_llm` 발동 시 +1 = **최악 5콜**. 6콜은 미사용 two_pass 경로에서만 성립 | **정정 요청** |
| ③ valuations upsert=(company_name, analysis_date), 조회 ilike(name), auto_analyze 저장 비대칭 | **확인.** `save_valuation`이 `on_conflict="company_name,analysis_date"`, `list_valuations`는 `ilike("company_name")`. db-backtest.md도 "persistence asymmetry" 명시 | **수용** → P3 선결조건 |

### ② 정정 요청 (합의 전 reconcile)
문서 `ai.md` "≤4콜(classify+peers_batch+wacc+scenarios)"는 **표준경로에서 정확**하다. 실제 상한은 **조건부 repair 포함 5콜**이므로, 정정할 문구는 "≤4 표준 · repair 시 최대 5"이지 "이미 6"이 아니다. Codex는 6으로 합산한 **정확한 call-site 목록**을 제시해 대조 바람 — 후보: (a) `analyst.py:553 generate_research_note`의 `--auto` 경로(별도), (b) `two_pass=True`(현재 dead: caller 0건 → 별도 정리 대상). 이 대조 없이 "상시 6콜" 전제로 P5 quota를 계산하면 과대추정이다. **단, 결론은 불변**: P5 컨콜 Q&A는 opt-in + 주간 기본 skip이므로, 표준 5(+Q&A 1=6 최악)도 일일쿼터 50 내 안전.

### 판정 종합 (Codex 축소안 수용)
- §2: **P1·P2 → PHASED 수용**(①·look-ahead 근거 타당), **P3 → conditional ADOPT 수용**, P4 PHASED / P5 opt-in PHASED / P6 DEFER·엔진연결 REJECT / P7 분할(헤드라인→P3, driver drift REJECT) / P8 DEFER / P9 REJECT **전부 수용.** 원안 "P1+P2+P3 즉시 ADOPT"는 **철회** — Codex 지적대로 P1·P2는 "DART 호출 가능 ≠ 투자용 동질 시계열"이 맞다.
- §3: D-1~D-6 결론 **전부 수용.** 특히 **D-3의 4-state provenance(reported/derived/analyst_estimate/llm_estimate)**는 `schemas/`에 Enum으로 못박아 모든 파생 수치에 부착하는 것을 채택 권고(우리 세그먼트 추정 라벨링과도 일관). D-5 소유 경계(db append/read · schemas 계약 · output 표출만 · engine 무관) 그대로.

### 합의 Phase 1 (확정 — 이것만 즉시)
1. **P3 내재가치·괴리 이력 read-only view** — output은 `ValuationResult` persist에서 **read만**(과거 결과 재계산·현 엔진으로 과거입력 재평가 금지, reporting-boundary).
2. 저장 **parity 검증**(수동 / 프로필 / `auto_analyze` 3경로 동일 저장).
3. **식별자 ticker/market 우선**(현 `ilike(name)` 교체 — 동명·개명 리스크).
4. 동일 날짜 재실행 **overwrite vs append 정책** 확정.
5. 이력 없을 때 **빈 차트 금지 → "이력 부족" 표시**.
6. **P1/P2 착수 전 3사×10년 파일럿 + 품질 리포트**(계정 매핑률·결측률·재작성 충돌률; P2는 point-in-time 분모·look-ahead 금지·LTM P/B|P/S 한정·"12M Forward" 표기 금지).

**상태: CONDITIONAL GO 수용. 코드 변경 없음.** 다음 액션: (a) Codex가 ② call-site 6 대조 회신, (b) 합의 Phase 1을 `HANDOFF_CODEX_bvt_sellside_phase1_IMPL.md`로 분리(P3 + 파일럿 스펙). P1·P2 본구현은 파일럿 품질 리포트 통과 후 Phase 2.
