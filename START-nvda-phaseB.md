# START — NVDA Phase B: TTM/Forward 재무 기준 정렬 (BVT 새 세션)
> **실행 위치**: `F:\dev\Portfolio\business-valuation-tool`
> **선행 완료**: NVDA Phase A (자동프로필 입력·게이트 정상화) — WACC 16.39%→11.52%, consumed_blume, ERP snapshot, 세율 17%, [T] 순환 제거, gate 순서 수정, provenance 7필드 영속화
> **필독 순서**: `ROUND3_POLICY_APPROVED_nvda_autoprofile.md` §7 (Phase 정의) → `HANDOFF_CODEX_nvda_phaseA_provenance_IMPL.md` → 본 문서
> **작업 표준**: Codex ↔ Claude 교차검증 루프 (아래 §6). **Codex 주장을 믿지 말고 독립 재현.**

---

## Step 0 — 착수 전 재검증 (선행 세션 상태 확인)

1. **Phase A가 실제로 반영됐는지 확인** — 프롬프트의 "완료" 주장을 믿지 말 것:
   ```cmd
   python scripts\verify_nvda_phaseA_v2.py
   ```
   기대: ALL PASS (provenance 7필드 포함). FAIL이 있으면 **Phase B 착수 전에 Phase A부터 닫는다.**
2. **넥써쓰 회귀 불변 확인** (과잉수정 검출 기준선):
   ```cmd
   python scripts\verify_nexus_round4.py --skip-pytest
   ```
   18/445/891 · 362 · Base equity 36,211 · net_debt 51,687 유지 확인.
3. `git log --oneline -10` + `git status` — Phase A 커밋 상태와 작업트리 확인. **미커밋 작업 다수 → git restore/checkout/reset 금지.**

---

## Step 1 — Phase B가 푸는 문제

Phase A 후에도 NVDA는 **$78, 괴리 −62%**다. Phase A는 "입력·게이트 정상화"였지 "과소평가 해결"이 아니다 (ROUND3 §7 명시).
잔여 과소평가의 **지배적 요인은 실적 앵커 시차**다:

| 구성 | 주당 | 근거 |
|---|---|---|
| Phase A (FY26 앵커 유지) | $78 | base_year FY2026 (2026-01 종료) |
| **Phase B (TTM 앵커)** | **~$93** | Q1 FY27 매출 +85% YoY 반영 |
| 심층리서치 수동 TTM 모델 | $175 | + 시나리오 가중 + SOTP 옵셔널리티 |

**정량 근거 (선행 세션 검증 완료)**: TTM 앵커 단독 효과 **+$30** = Phase A 전체(+$15)의 2배.

### 🔴 근본 갭 — 파이프라인이 10-Q를 못 읽는다

`pipeline/edgar_parser.py:161`은 **`form in ("10-K", "10-K/A")` 만 필터링**한다.
→ 분기(10-Q) 데이터를 수집하지 못하므로 **TTM(최근 4개 분기 롤업)을 자동 생성할 수 없다.**
현재 `base_year`는 항상 최근 **회계연도**로 고정된다 (`profile_generator.py:755`).

---

## Step 2 — 이미 존재하는 검증 기준 (수동 TTM 정답지)

`valuation-results/2026-07-10-nvda-deep-dive/_verified_data.md` §TTM에 **수동 롤업 공식과 값이 이미 있다**:

```
TTM (2025-04-27 ~ 2026-04-26):
  Revenue    253,491
  OpInc      162,285  (= FY26 130,387 − Q1FY26 21,638 + Q1FY27 53,536)
  GAAP NI    159,613
  비GAAP NI  143,451  (= 116,997 − 19,094 + 45,548)
  D&A          3,229  (= 2,843 − 611 + 997)
  capex        6,553  (= 6,042 − 1,279 + 1,790)
```

**TTM 롤업 공식 = FY 확정 − 직전연도 동분기 + 당해연도 최신분기.**
→ 자동 생성기가 이 공식을 재현하면 `_verified_data.md` 값과 대조 가능하다. **이것이 Phase B의 회귀 기준이다.**

또한 `nvda_ttm.yaml`(수동)과 `nvda_fy27e.yaml`(forward)이 이미 완성된 참조 모델로 존재한다 — 자동 생성 결과가 이들과 얼마나 수렴하는지가 성공 척도.

---

## Step 3 — 설계 쟁점 (Codex 논쟁 대상, 구현 전 정책 확정)

1. **10-Q 파싱 추가** — `edgar_parser.py`에 10-Q 폼 필터 + 분기 XBRL 태그(기간 구분 `CY2026Q1` 등) 파싱. 누적분기(YTD) vs 개별분기(discrete) 구분이 핵심 함정.
2. **TTM 롤업 순수 함수** — `engine/`에 `FY − prior_same_quarter + latest_quarter`. IO 금지, frozen fixture 테스트.
3. **FY/TTM 병행 산출** — base_year를 덮어쓸 것인가, 둘 다 산출 후 사용자 선택인가? (ROUND3 §7: "FY와 TTM 차이 명시")
4. **53주 회계연도 / 분기 중복 처리** — NVDA는 1월 말 결산. 분기 경계·중복 제거 정책.
5. **provenance** — TTM은 어느 분기들을 합쳤는지 (`included_quarters`, 각 rcept_no/기준일) 기록. Phase A의 beta/erp provenance 패턴 준수.
6. **forward(FY27E) 앵커** — 컨센서스 매출 $391B를 별도 시나리오로 넣을 것인가? (nvda_fy27e.yaml 참조). 이건 Phase B 범위인가 Phase C인가?
7. **비GAAP 정규화** — GAAP NI에 포함된 지분증권 평가이익(Q1FY27 $15.9B)을 TTM에서 제거하는가? (_verified_data.md는 비GAAP 143,451 사용)

---

## Step 4 — 성공 기준 (ROUND3 §9 원칙 계승)

- ❌ **"NVDA가 $175/$204에 도달"을 성공 기준으로 삼지 말 것.** 시장가 추종 금지.
- ✅ TTM 롤업이 `_verified_data.md` 수동값과 **±1% 이내 일치** (Revenue 253,491 / OpInc 162,285 / D&A 3,229 등)
- ✅ TTM 앵커에 사용된 분기들이 **provenance로 기록**될 것 (rcept_no·기준일·기간구분)
- ✅ FY와 TTM 차이가 **프로필·출력에 명시**될 것
- ✅ 자동 생성 TTM 프로필이 수동 `nvda_ttm.yaml`과 **주당 ±5% 이내** 수렴
- ✅ reverse DCF는 시장 내재 가정으로 보고하되 입력 오류 판정과 분리 (Phase A 계승)

---

## Step 5 — 회귀 기준표

| # | 항목 | 기준 |
|---|---|---|
| B-1 | 10-Q 파싱 | 최근 4개 분기 discrete 값 정확 추출 |
| B-2 | TTM 롤업 | `_verified_data.md` 수동값 ±1% (Revenue 253,491 / OpInc 162,285 / D&A 3,229) |
| B-3 | TTM provenance | included_quarters + rcept_no + 기간구분 기록 |
| B-4 | FY/TTM 병행 | 둘 다 산출, 차이 명시 |
| B-5 | 자동 TTM vs 수동 nvda_ttm | 주당 ±5% 수렴 |
| B-6 | 🔴 넥써쓰 불변 | 18/445/891 · 362 · Base equity 36,211 · net_debt 51,687 |
| B-7 | 🔴 Phase A 불변 | NVDA WACC 11.52% · βL 1.697 · consumed_blume · provenance 7필드 |
| B-8 | 기존 45개 프로필 | crash 0 (10-Q 파싱은 US EDGAR 한정, KR/JP 미영향) |
| B-9 | pytest | 974 passed 유지 (`--deselect ...TestScenarioDriverRoundTrip`) |
| B-10 | NUL / AST | clean |

---

## 6 — Codex ↔ Claude 교차검증 루프 (프로젝트 표준)

```
Claude 진단·정량분해 → Codex 6축 60점 평가 → Claude 독립 재현(믿지 말 것)
→ 반박/수용 판정 → Codex 정책 확정본(코드 수정 전) → Claude 승인
→ Codex 구현 → Claude 검증(독립 재현 + 회귀표) → 반복
```

### 🔴 이 루프에서 반드시 지킬 것 (실제 사고 이력)
1. **Codex 작업 종료 직후 NUL 스캔** (재발 이력 — CLAUDE.md·nexus.yaml·dashboard.py 손상):
   ```bash
   python -c "import os; print('NUL:', [p for r,d,f in os.walk('.') if '__pycache__' not in r and '.git' not in r for p in [os.path.join(r,x) for x in f] if p.endswith(('.py','.yaml','.md','.sql')) and open(p,'rb').read().count(b'\x00')] or 'clean')"
   ```
2. **Codex는 요구사항을 조용히 이탈한다** — Phase A provenance에서 7필드 누락 실제 발생. **구현 전 정책 확정본을 먼저 받고, 검증 스크립트를 완화하지 말 것.**
3. **항목 번호는 1번부터 명시하게 하라** (누락 방지).
4. **회귀표를 표로 못박아라** — 넥써쓰 불변·Phase A 불변을 과잉수정 검출용으로 반드시 포함.
5. **Codex 주장 전부 독립 재현** — "ALL PASS"·"pytest 974"·"NUL clean" 다수 검증했고 그중 여럿이 사실과 달랐다.
6. **샌드박스 마운트 stale** — 최근 수정 .py를 truncate/NUL로 서빙. 실행 검증이 안 되면 `verify_*.py` 스크립트를 만들어 **사용자에게 로컬 실행** 요청 (verify_nvda_phaseA_v2.py 패턴). 파일 편집은 bash `/tmp` 경유 원자적 쓰기 권장.

### 세션 안전
- 🔴 `git checkout/restore/reset --hard` 금지 — 작업트리에 미커밋 작업 다수. 파손 시 백업 후 재구성.
- `.py` 편집 후 즉시 `ast.parse` + `wc -l` (truncation 검출). CRLF 유지.

---

## 산출물
- `pipeline/edgar_parser.py` (10-Q 파싱) + `pipeline/edgar_client.py` (분기 조회)
- `engine/` TTM 롤업 순수 함수 + `tests/fixtures/` frozen 테스트
- `profiles/nvda.yaml` (TTM 앵커 반영 or FY/TTM 병행) + TTM provenance
- `scripts/verify_nvda_phaseB.py` (B-1~B-10 검증)
- 최종: Phase B COMPLETE 판정 → NVDA gap 완료 조건(A+B) 충족

## 완료 정의
B-1~B-10 전항 PASS + `_verified_data.md` 수동값 대조 통과 시 → **Phase B COMPLETE = NVDA autoprofile gap 해결.**
이후 Phase C(적격 peer beta snapshot, P0-4)는 별도. peer는 검증·차단 근거이지 가격 상향 수단이 아니다 (ROUND3 §2 계승).
