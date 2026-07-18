# CODEX 핸드오프 — P0-1 커밋 완료 / P0-2 착수 설계 요청

**직전 상태:** P0-1 최종 승인 → 커밋 `1c9ca8a` (P0-0 `e168b9c` 위)
**요청:** ① P0-1 커밋 범위 확인, ② P0-2(베타 정상화) 설계 판정 — 특히 **기존 코드의 §2.3 위반 4건 처리 방침**

---

## 1. P0-1 커밋 결과 (`1c9ca8a`)

```
feat(engine): 순차입금 정상화 게이트 — 독립 원천 대조 + reconciled 소비 (P0-1)
 11 files changed, 1229 insertions(+), 6 deletions(-)
```

| 파일 | 줄수 | 비고 |
|---|---|---|
| `engine/normalize.py` | +151 | 신규 (pure). 4-상태 게이트 |
| `tests/test_normalize.py` | +519 | 신규. 34 tests |
| `pipeline/edgar_parser.py` | +131 | Path A(개별) / Path B(결합) 이원 수집 |
| `pipeline/dart_parser.py` | +75 | 구성요소만. 독립 합계 `None` |
| `valuation_runner.py` | +123 | 게이트 4함수 + `load_profile`·`run_valuation` 양쪽 적용 |
| `db/backtest_repository.py` | +47 | P0-0 컬럼 쓰기 경로 + 마이그레이션 미적용 폴백 |
| `schemas/provenance.py` | +31/-3 | 허용오차 5단위 + `reconciliation_delta` |
| `pipeline/data_fetcher.py` | +31 | US yfinance 1차 경로에 EDGAR 원장 보강 |
| `pipeline/profile_generator.py` | +23 | YAML 원장 기록 (헝크 선별) |
| `schemas/models.py` | +6/-1 | `net_debt_legacy` (헝크 선별) |
| `HANDOFF_CODEX_p0-1.md` | +98 | 설계·검증 기록 |

**헝크 선별 결과 (지시대로 수행):**
`schemas/models.py`·`pipeline/profile_generator.py`·`valuation_runner.py` 3개 파일에서
peer provenance(`premium_pct`/`band_position`/`rationale`) · `investability_blockers` ·
`profile_text`/`draft`/`generated`/`curated` · `_profile_is_protected()` WIP를 **전부 제외**했다.
커밋 후에도 이 3파일은 작업 트리에서 `M`으로 남아 있다 — 남은 건 그 WIP뿐이며 정상이다.

- `git show --stat` : 위 표와 동일 (P0-1 외 헝크 0건)
- `git show --check`: 위반 0건
- 커밋 후 재검증: `test_normalize` 34 + `test_provenance` 36 passed · R10 SK에코플랜트 **35,066원** 유지

**환경 메모 (커밋 절차):** 이 클론은 HEAD 블롭의 줄바꿈이 **파일별로 섞여 있다**
(CRLF: `models.py`·`valuation_runner.py`·`profile_generator.py`·`data_fetcher.py`·`backtest_repository.py` /
LF: `provenance.py`·`edgar_parser.py`·`dart_parser.py`). 파일별 HEAD 관례에 맞춰 스테이징해야
줄바꿈 플립 없이 커밋된다. `.gitattributes` 도입은 여전히 **단독 커밋** 사안으로 남아 있다.

---

## 2. P0-2 착수 — 현행 코드의 §2.3 위반 4건

대상: `pipeline/profile_generator.py::_estimate_wacc_params` (현행 211~300행) → 신규 `engine/normalize.py` 확장.
PLAN §2.3의 핵심 금칙은 **"자동 클램프/대체 코드 작성 금지. override는 사람이 하고 {원값, 대체값, 사유, WACC 민감도}를 산출물에 명시"** 인데, 현행 코드는 정반대로 동작한다.

| # | 현행 코드 | §2.3 위반 내용 |
|---|---|---|
| V1 | `bu = default_bu` (US 1.0 / JP 0.85 / KR 0.75) — beta 관측 실패 시 **조용한 상수 대체** | 관측 실패를 상수로 덮는다. P1 범주 ③(근거 없는 창작)에 가깝다. 최소한 `FallbackConstant`로 표기돼야 한다 |
| V2 | `bu = max(bu, 0.1)` — **자동 클램프** | "범위 이탈은 차단 사유도 자동 대체 사유도 아니다" 위반 |
| V3 | `kd_pre = max(rf, min(kd_pre, rf + 5.0))` — **자동 클램프** | 동일. 관측된 이자비용/차입금 비율을 조용히 왜곡한다 |
| V4 | `tax = min(max(effective_tax, 0), statutory_tax)`, 실패 시 `statutory_tax * 0.85` | 클램프 + 근거 없는 0.85 계수 |

추가로 **상장/비상장 분리가 없다**: 현행은 시장 구분(US/JP/KR)만 하고, 비상장사는 `market_cap == 0` →
Hamada 분기 자체가 무력화돼 곧장 `default_bu`로 떨어진다. §2.3이 요구하는
"비상장 = peer median unlevered beta 1순위, 산업 테이블 교차검증"이 전혀 구현돼 있지 않다.

### 제안 설계 (판정 요청)

1. **`engine/normalize.py`에 `resolve_beta()` 추가** (pure, P0-1 게이트와 동일 패턴):
   - 상장: `raw equity beta` + **관측창/빈도/출처 필수**(없으면 관측치로 인정 안 함) → Hamada 언레버 → `blocked_no_provenance` / `blocked_reference_conflict`(raw βL > peer median × 1.5 미해결) / `consumed`
   - 비상장: `peer median unlevered beta`(유효 peer ≥ N) → 실패 시 산업 테이블 → 둘 다 실패 시 **차단**
   - 범위 이탈 [0.3, 2.0]: **경고 + 민감도 필수 표시**, 차단·대체 금지
2. **V1~V4 제거**: 클램프/상수 대체 코드를 지우고, 관측 실패는 `FallbackConstant`(§2.4 타입, 이미 존재)로 **표기**하거나 게이트가 차단한다. 다만 이는 **동작 변경**이라 R10(35,066원)이 깨질 수 있다.
3. **`beta_source` provenance**: `Source(value, source="yfinance", as_of, url, method="observed")` + 관측창/빈도를 어디에 담을지 — `Source`에 `window`/`frequency` 필드를 추가할지, `derived_from`에 문자열로 넣을지 **계약 판단 필요**.

### 판정 필요 항목 (P0-2 착수 전)

- **Q1. R10 베이스라인 취급**: V1~V4를 제거하면 SK에코플랜트(비상장, beta 관측 없음 → `default_bu=0.75` 의존)는 **차단되거나 값이 바뀐다.** R10을 "정상화 이전 값"으로 재기준(rebaseline)할지, 아니면 P0-2에서는 **게이트 판정만 기록하고 소비는 유예**(P0-1처럼 legacy 유지)할지.
- **Q2. peer median unlevered beta의 순환 의존**: §2.3은 "멀티플 선정과 분리된 동일 시점 데이터셋"을 요구한다. P0-4 peer 관측 스냅샷이 아직 없는데, P0-2를 먼저 하려면 임시 데이터셋이 필요하다. **P0-4를 먼저 하고 P0-2를 뒤로 미룰지** 순서 판정 요청.
- **Q3. 산업 beta 테이블**: Damodaran 연 1회 갱신 테이블을 리포지토리에 정적 파일로 넣을지(관측치인가? `FallbackConstant`인가?), 넣는다면 `as_of`/TTL 정책.
- **Q4. 관측창/빈도 메타데이터 위치**: `Source` 확장 vs 별도 `BetaObservation` 타입.

---

## 3. 남은 후속 (P0-1에서 이월)

- Supabase 마이그레이션(`db/migrations_backtest.sql` 3컬럼) 수동 적용 — 미적용이어도 스냅샷 저장은 죽지 않는다(P0 컬럼만 제외 + WARN).
- Windows에서 `python cli.py --company NVDA --auto` → 로그의 `순차입금 정규화 소비/차단` 확인. Path B 부채 축에 `LongTermDebt`만 존재하므로 **mismatch 차단이 정상**이다(설계 확정 사항).
- 별건: SK에코플랜트 품질 71→0(F)은 다른 세션 WIP investability gate(`DCF/peer-median 0.49`)가 stale `.pyc` 때문에 그동안 실행되지 않다가 이제 도는 것. P0-1 무관.
