# Round 4 — 베타 관측치 블로커 (구현 착수 전)

2026-07-14 | Codex 블로커 2건 전부 독립 확인. **Phase A 범위 재정의 필요.**

---

## 1. ✅ 블로커 1 — yfinance beta는 `consumed_blume` 자격이 없다 (확정)

Codex: *"자동 생성기는 `yfinance info["beta"]`만 받는다. 관측창·빈도·벤치마크·계산법·기준일이 없어 P0-2a상 `BetaObservation`이 될 수 없다."*

**코드 원문이 이를 명시적으로 못박고 있다** — `schemas/provenance.py:305`:
> *"**관측창과 빈도를 알 수 없는 값은 §2.3 관측치가 아니다** — yfinance `info["beta"]`는 이 타입을 만들 수 없고, 게이트가 `blocked_no_provenance`로 차단한다."*

`BetaObservation` 필수 필드: `equity_beta(Source)` · `window_start` · `window_end` · `frequency` · `benchmark` · `observation_count` · `calculation_method`. `benchmark`/`calculation_method`는 빈 문자열이면 **ValidationError**.

**확인된 사실**
- `pipeline/profile_generator.py:262`는 `info.get("beta")`(스칼라)만 받는다
- **파이프라인에 가격 시계열 다운로드가 전혀 없다** (`grep history/download/period` → 0건)
- `normalize_beta`는 **아무도 호출하지 않는다** (P0-2b 미배선 확정)

**⇒ Blume에 넣을 적격 관측치가 애초에 존재하지 않는다.** 스칼라 beta를 `consumed_blume`으로 포장하면 **승인된 provenance 계약을 정면 위반**한다. Codex 정확.

---

## 2. ✅ 블로커 2 — 검증 스크립트 필드명 오류 (수정 완료)

| 내가 쓴 것 | 실제 필드 |
|---|---|
| `WACCResult.beta_l` | **`bl`** |
| `QualityScore.cross_validation` | **`cv_convergence`** |
| cli 재계산 (오프라인 None) | **$204 주입으로 gate 덮어쓰기 강제 재현** |

`scripts/verify_nvda_phaseA.py` 수정 완료. `QualityScore.draft` 필드도 관측하도록 추가.

---

## 3. 베이스라인 JSON이 증명한 것 (Codex B-1 주장 확정)

`valuation-results/nvda_phaseA_baseline.json`:
```json
"quality_after_gate": { "total": 0, "grade": "F" },   ← run_valuation 단계는 이미 0/F
"dcf_ev": 1527431,                                     ← 회귀 고정값 확인
"bu": 2.207                                            ← raw 소비 중
```

**run_valuation 단계에서 이미 0/F draft다.** CLI가 70/B를 보여준 건 `cli.py`가 market_comparison 후 `calc_quality_score`를 재호출해 **gate 결과를 덮어쓰기 때문** — Codex 진단 정확.
(필드명 오류로 `bl`/`cv_convergence`가 null로 찍혔으나, `total`/`grade`/`dcf_ev`/`bu`는 정상 캡처됨.)

---

## 4. 🔴 결론 — Phase A "베타" 부분은 데이터 인프라 없이는 정직하게 구현 불가

정직한 경로는 셋뿐이다:

| 경로 | 내용 | 비용 | 결과 |
|---|---|---|---|
| **(A) 회귀 수집기 추가** | NVDA + 벤치마크(S&P500) 가격 시계열 다운로드 → 회귀 beta 산출 → 적격 `BetaObservation` → `consumed_blume` | **신규 네트워크 의존 + 벤치마크 데이터 + 회귀 코드 + provenance** | NVDA β 2.211→1.811, $63→$78 |
| **(B) 베타 분리** | Phase A는 ERP·세율·`[T]`·gate·draft만. 베타는 관측치 없음 → **`blocked_no_provenance` → draft 유지**. 회귀 수집기는 별도 단계 | 국소 수정만 | NVDA β 그대로, $63→**$68** (ERP+세율만), **draft 표식** |
| (C) 스칼라를 그냥 Blume | — | 낮음 | **❌ 계약 위반. 금지** |

**(C)는 Codex가 막았고 옳다.**

### 핵심 판단 — 회귀 수집기는 Phase C 인프라와 겹친다

- 경로 (A)의 가격 시계열 회귀 수집기는 **Phase C(P0-4 peer beta snapshot)와 같은 종류의 인프라**다: dated market-data 수집 + provenance + look-ahead 차단.
- **둘을 따로 만들면 벤치마크 데이터·수집·provenance 코드를 두 번 짓는다.**
- `CLAUDE.md`가 경고: *"TTM·peer·전역 WACC 변경을 한 묶음으로 하면 위험"* — blast radius를 작게 유지하라.

### 그리고 (B)의 draft 결과는 정책과 정합한다

- 정책 성공기준: *"raw β 이상치가 무검증 소비되지 않을 것"*
- 관측치가 없으면 **차단 → draft**가 바로 그 정직한 결과다.
- P6 gate가 이미 draft를 처리하므로 **NVDA 자동 프로필이 draft로 남는 것이 옳다** (실제로 미완성이므로).
- β를 정직하게 낮추려면 **반드시 실제 관측치가 필요**하다 → 그건 인프라 단계의 일이다.

---

## 5. 권고 — Phase 재분할

| Phase | 내용 | NVDA | blast radius |
|---|---|---|---|
| **A (수정)** | ERP snapshot + 세율 17% + `[T]` 폴백 제거 + gate 순서 수정 + draft 배너/publish 차단 | $63 → **~$68** + **draft 표식** | 국소·저위험 |
| **A-β / C** | **가격 시계열 beta 회귀 수집기** → `BetaObservation` → `consumed_blume` (+ P0-4 peer snapshot 인프라와 통합) | +$13 | 데이터 인프라 |
| **B** | TTM 앵커 | +$30 | 파이프라인 |

**재분할 근거**
1. ERP·세율·`[T]`·gate 수정은 **데이터 수집 불필요**(ERP는 정적 커밋 파일, 세율은 가이던스 상수, 나머지는 순수 로직) → 즉시·저위험 배포
2. 베타 회귀 수집기는 **Phase C peer snapshot 인프라와 병합** → 중복 방지
3. Phase A 후 NVDA는 **draft로 남는다** — 이것이 정직한 결과 (미완성 프로필이므로)

**⚠️ 이렇게 하면 `consumed_blume`·`BetaStatus` 계약 개정은 Phase A가 아니라 A-β/C에서 이뤄진다.** (계약 변경을 데이터 인프라와 함께 묶는 것이 안전하다.)

---

## 6. 사용자 결정 필요

Codex 질문: *"가격 시계열 beta 회귀 수집기와 검증 스크립트 수정까지 Phase A 범위에 추가해 진행할까요?"*

→ **검증 스크립트는 이미 수정했다.**
→ **회귀 수집기 편입 여부는 blast radius 결정이다.** 아래 §7 참조.

---

## 7. 미확정 (사용자 승인 후 Codex 재핸드오프)

1. **회귀 수집기를 Phase A에 넣을 것인가(경로 A), 분리할 것인가(경로 B)?**
2. 경로 B면: Phase A 후 NVDA `bu`는 무엇을 쓰는가? (raw 유지 + draft 표식 vs 명시적 declared-assumption 기본값)
3. 벤치마크 지수 (S&P500 = `^GSPC`?), 관측창(2년 주간? 5년 월간?), 계산법 (OLS?) — 수집기 스펙
4. ERP snapshot 4.18%/rf 4.44% 원문 재확인 (여전히 Claude 미검증)
