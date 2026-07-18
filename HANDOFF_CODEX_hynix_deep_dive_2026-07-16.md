# CODEX 교차검증 요청 — SK하이닉스(000660) 밸류에이션 커레이션 + 심층보고서

2026-07-16 (Claude) | 상태: **검증 요청 — Claude 구축 완료, Codex 6축 독립 재현·반박 요망**
선행 필독: `.claude/rules/codex-cross-review.md` → `.claude/rules/engine.md` → `.claude/rules/reporting-boundary.md` → 본 문서

> 이 문서는 코드 개선 지시가 아니다. **엔진 코드는 한 줄도 수정하지 않았다** — 전부 `profiles/000660.yaml` 데이터 커레이션 + 신규 산출물이다. Codex는 §4 표를 **독립 재현**(재계산·재실행)하고, §3 판단 8건을 6축(정확성·건전성·회귀안전·범위규율·검증가능성·유지보수성)으로 평가·반박한다. **Claude 주장을 믿지 말고 재현하라** — 특히 DART 원문 대조와 세그먼트 추정 분할.

---

## 0. 착수 상태 — 무엇을 바꿨나

**엔진/코드 변경: 없음.** `git diff --stat`은 `profiles/000660.yaml` 단일 파일만 나와야 한다(그 외 변경은 이 작업 소관 아님).

- draft 스텁(grade F, draft:true, blocker 1) → **투자가능**(draft:false, grade **B 80/100**, blocker 0)으로 커레이션.
- 신규 산출물: `valuation-results/2026-07-16-hynix-deep-dive/` (보고서 md·PDF·차트6·실행로그·DART검증노트·프로필스냅샷).
- ⚠️ 작업트리에 **미커밋 작업 다수** → `git restore/checkout/reset --hard` **절대 금지**. `profiles/000660.yaml` 백업은 `/tmp/000660.bak.yaml`(샌드박스, 세션종료 시 소멸)에만 있으니 Codex는 로컬에서 별도 백업 후 검증할 것.

---

## 1. 근본 결함 — DCF 붕괴는 단일 노브 버그였다

원 스텁의 F등급·blocker("no DCF value to cross-check")는 **`dcf_params.da_to_ebitda_override: 0.9592`** 하나에서 파생됐다.

- 이 값이 D&A를 EBITDA의 **95.92%**(64.5조)로 강제 → OP 2.7조(세그먼트 합 47조와 단절) · capex = capex_ratio(actual_capex/da_base=2.05x) × 64.5조 = **132조** · FCFF **−65.8조** · DCF EV **−254조**.
- 게이트: `_check_dcf_vs_peer`가 DCF 없음/음수 → block → `apply_gate_to_profile`이 draft:true 주입 → `quality.py:69`가 draft면 grade F. **순환**: DCF 깨짐 → draft → F. 고치면 연쇄 해제.
- 실제 D&A/EBITDA = **0.234** (회사 공시 EBITDA 61.596조 − OP 47.206조 = D&A 14.3895조). override를 null로 제거 → 엔진이 `da_base/ebitda_base`로 0.234 자동 산출.

**Codex 검증 포인트**: override null 제거만으로 DCF 2026 op 51.9조·capex 31.4조·FCFF +31.1조로 정상화되는지, 그리고 이것이 세그먼트 OP 합(47.2조 성장분)과 정합하는지 재실행 확인.

---

## 2. 프로필 커레이션 변경 — 전 항목 DART 원문 대조

DART OpenAPI(corp_code 00164779, 사업보고서 접수 **20260317000635**, 결산 2025-12-31, 연결) 원문 대조. Chrome javascript_tool same-origin fetch 경로 사용(샌드박스 외부망 차단).

| # | 필드 | before → after | 근거 (DART/IR) |
|---|---|---|---|
| 1 | `da_to_ebitda_override` | 0.9592 → **null** | 실제 D&A/EBITDA 0.234 자동산출 |
| 2 | `consolidated.2025.dep` | 13,930,130 → **14,389,500** | 회사공시 EBITDA 61.596조 − OP 47.206조 = D&A 14.39조 |
| 3 | `dcf_params.capex_fade_to` | null → **1.3** | capex/D&A 1.99x(2025 AI capex) → 1.3x 정규화 페이드 |
| 4 | `company.shares_total` | 690,455,268 → **728,002,365** | DART 발행주식총수(보통주) |
| 5 | `company.treasury_shares` | 0 → **26,310,845** | DART 자기주식수 → 유통 701,691,520 |
| 6 | `scenarios.*.shares` | 690,455,268 → **701,691,520** | 유통주식(발행−자기주식), per-share 분모 |
| 7 | `segment_data.2025` (DRAM/NAND/기타) | NAND>DRAM 오류 → DRAM 78%/NAND 20%/기타 2% | IR 제품믹스 기반 애널리스트 추정, 합계 연결실적 재조정 |
| 8 | `segment gross_profit` | 0 → GP 재배분 | DART 연결 매출총이익 58,690,790 기준(97,146,675 − 매출원가 38,455,885) |
| 9 | `segments.*.multiple` (base) | 9.1/8.6/10.3 → **9.5/8.0/10.0** | 피어 중앙값 + DRAM HBM 프리미엄 |
| 10 | `market_price` / `price_as_of` | 2,425,000(as-of 없음) → **1,842,000 / 2026-07-16** | Daum 금융 종가 |
| 11 | `peers` | 18개(가공 포함) → **13개** | Intel DRAM/NAND(사업철수)·자기참조 제거 |

**DART 원 단위 일치 확인분**: 매출 97,146,675 · 영업이익 47,206,319 · 부채총계 55,440,908 · capex 28,579,343(유형 27,518,924+무형 1,060,419) · 현금 14,923,766 · 매출총이익 58,690,790(매출원가 38,455,885) · 발행 728,002,365 · 자기주식 26,310,845. (모두 프로필/재조정값과 일치)

**재조정 항등식(Codex 재계산)**: 세그먼트 rev합 97,146,675 = 연결 · op합 47,206,319 = 연결 · gp합 58,690,790 = DART · asset합 176,107,659 = 연결. 전부 diff 0.

---

## 3. Codex 6축 평가 대상 — 판단 8건 (구현 아님, 판정 요망)

> 각 항목 **Claude 입장 + 근거**. Codex는 축별 점수 + [필수]/[권고] + 반박/수용.

**3-1. 세그먼트 DRAM/NAND 분할 = 추정치.** DART는 **반도체 단일 세그먼트**만 공시 → DRAM/NAND OP 분할은 원천 부재. Claude: 매출믹스(DRAM 78%/NAND 20%/기타 2%)는 IR HBM/eSSD 공시·업계구조 근거, OP마진(DRAM 55%/NAND 28%/기타 4.6%)은 애널리스트 가정으로 **보고서·프로필 주석에 '추정' 명시**, 합계는 연결실적 정확 재조정. Codex 쟁점: 마진 구조(DRAM 55% vs NAND 28%)가 방어가능한가? 자산비중(60/35/5%) → D&A 배분이 SOTP EBITDA에 영향하므로 재검토.

**3-2. D&A 14.39조 확정 방식.** Claude: DART fnlttSinglAcntAll(CFS)가 감가상각을 표준계정으로 태깅하지 않아(직접법 표시) 원 단위 미확보 → **회사 공시 EBITDA 61.596조 − OP 47.206조 = 14.3895조**로 역산. Codex 쟁점: 이 역산이 무형자산상각 포함 총 D&A로 타당한가? (주석 원문 확인 시 개선 여지)

**3-3. capex_fade_to 1.3.** Claude: 2025 capex/D&A 1.99x는 AI 확장 국면 → 5년 예측기간 1.3x로 선형 페이드. TV는 엔진이 유지보수 capex(=D&A)로 별도 정규화(dcf.py:151–157). Codex 쟁점: 1.3x 종착·페이드 속도의 근거 강도.

**3-4. 주식수 basis — 유통 701.69M.** Claude: per-share 분모 = 발행 728.0M − 자기주식 26.3M = 유통 701.69M(BPS 기준과 정합, Daum BPS 171,751×701.69M≈120.5조). 프로필 원값 690.5M은 EPS 가중평균 근사였던 것으로 추정. Codex 쟁점: 시가총액(Daum 1,313조÷1,842,000≈712.7M 상장주식)과 분모 불일치 → 괴리분석 정합성에 영향 없는가?

**3-5. WACC 자본구조 eq_w 96.6% / D/E 3.5%.** Claude: 유지(SK하이닉스 순레버리지 급감, net_borr 9.8조). 다소 보수적(WACC 소폭 상향). Codex 쟁점: 순차입금/자기자본 book D/E는 8.2%인데 3.5% 사용 → WACC 과대(보수) 여부. **NVDA에서 WACC 표기누락이 [치명]이었으므로** 보고서 §4.1에 βL·Ke·Kd세후·블렌드 전개 명시했는지 확인.

**3-6. 시나리오 배수 클램프.** 강세(B) 원안 15/18/22x가 최저시나리오 대비 2.0x 상한에 걸려 14/17/20x로 엔진 클램프. Claude: 피크이익×피크배수 이중계산 억제로 수용, 보고서에 각주. Codex 쟁점: 클램프가 강세 시나리오 가치(1,662,322)를 왜곡하지 않는가.

**3-7. 셀사이드 컨센서스 목표가 ~3,390,935.** Investing.com 집계(37기관) 단일 출처. Claude: 현재가·모델 강세도 상회 → "낙관 편위" 관찰치로만, 집계기관·표본 상이 caveat 명시. Codex 쟁점: 단일 aggregator 인용의 적절성, 원천 소급 필요 여부.

**3-8. 기준가 1,842,000(−11.53% 당일).** Claude: 2026-07-16 종가(Daum), as-of 명시. 당일 급락(키옥시아 −15% 등 메모리 조정)은 스냅샷 변동성이나 종가 기준 일관. Codex 쟁점: 급락일 종가 vs 수일 평균 채택 여부.

---

## 4. 회귀/검증 기준표 (Codex 독립 재현 — 완화 금지)

| # | 항목 | 기준 | 재현 방법 |
|---|---|---|---|
| H-1 | 게이트 | draft:false · grade≥C(현 B/80) · blockers [] | `python cli.py --profile profiles/000660.yaml --json` |
| H-2 | 세그먼트 재조정 | rev 97,146,675 · op 47,206,319 · gp 58,690,790 · asset 176,107,659 (diff 0) | 합산 |
| H-3 | 🔴 WACC 재현 | βL 1.181 · Ke 10.88% · Kd세후 3.74% · WACC 10.64% | `1.15*(1+0.78*0.035)`; `3.2+βL*6.5`; `4.8*0.78`; `0.966*Ke+0.034*Kd` |
| H-4 | DCF 정상화 | 2026 op 51.9조 · capex 31.4조 · FCFF +31.1조 · EV 569.6조(>0) | JSON `dcf.projections[0]` |
| H-5 | DCF≈SOTP 수렴 | DCF EV 569,588,267 ≈ SOTP EV 569,850,300 (−0.05%) | JSON |
| H-6 | 확률가중 | A 1,458,535×.40 + B 1,662,322×.25 + C 784,440×.20 + D 561,157×.15 = **1,240,056** | 재계산 |
| H-7 | 시장정합 | 내재 1,240,056 vs 시장 1,842,000 → 괴리 −32.7% · as_of 2026-07-16 | JSON `market_comparison` |
| H-8 | DART 원단위 | §2 하단 8개 항목 원 단위 일치 | DART API 재fetch(로컬) |
| H-9 | 보고서 정합 | md/PDF 전 수치 = 엔진 JSON (날조 0, 세그먼트 '추정' 명시) | md ↔ `_run_hynix_2026-07-16.txt` 대조 |
| H-10 | NUL / YAML parse | clean · `yaml.safe_load` OK | §7 스캔 |

**완료 정의**: H-1~H-10 전항 PASS + §3 판단 8건 6축 판정 → 커레이션·보고서 확정.

---

## 5. 개념 자가점검 (CLAUDE.md 원칙 — Codex 재확인)

- **성장조정배수**: 본 보고서는 성장조정배수(EV/EBITDA÷g)를 결론에 사용하지 않음. `relative_valuation`의 PEG 0.14는 growth 221.9%(2023 저점→2025 피크 왜곡)라 **의도적으로 인용 배제**(개념 오용 회피). Codex 확인: 보고서에 PEG 근거로 저평가 주장 없음.
- **CV(교차검증) 정의**: "SOTP·DCF 2종 수렴 −0.05%"는 표본 2개라 정밀도 지표 아닌 **참고치**로 표기(NVDA 각주 관행 계승). Codex 확인: CV를 통계적 신뢰도로 오표기하지 않았는지.
- **WACC 블렌드**: Ke×eq_w + Kd세후×(1−eq_w) 전개를 보고서 §4.1에 명시(재현가능). Kd는 세후(3.74%), Ke는 CAPM. Codex 확인: 세전/세후 혼용 없음.
- **피크이익 리스크**: 시장 EV/EBITDA 21.1x가 **피크 EBITDA에 부여**됨을 §4.3에 명시 — 피크이익×피크배수 이중계산 위험을 결론에 반영.

---

## 6. 산출물

```
profiles/000660.yaml                                    # 커레이션 (유일 변경 파일)
valuation-results/2026-07-16-hynix-deep-dive/
  SK하이닉스_기업분석보고서_2026-07-16.md / .pdf          # 6p, NVDA 구조
  SK하이닉스_기업분석보고서_2026-07-16_김지원.pdf          # career 첨부용 사본
  charts/01_anchors_vs_price ~ 06_mc_range.png           # 6종
  _run_hynix_2026-07-16.txt                              # 콘솔 실행로그
  _verified_data.md                                      # DART 검증노트 + 전수검산
  _profile_snapshot_000660.yaml                          # 프로필 스냅샷
```

---

## 7. Codex 루프 규칙 (실제 사고 이력 — 반드시 준수)

1. **작업 종료 직후 NUL 스캔** (재발 이력: CLAUDE.md·프로필·엔진 손상, 2회 "clean" 오보):
   ```bash
   python -c "import os; print('NUL:', [p for r,d,f in os.walk('.') if '__pycache__' not in r and '.git' not in r for p in [os.path.join(r,x) for x in f] if p.endswith(('.py','.yaml','.md')) and open(p,'rb').read().count(b'\x00')] or 'clean')"
   ```
2. **YAML 편집 시 `yaml.safe_load` + 재조정 항등식 재확인**(§4 H-2). Windows 마운트 대용량 편집 mid-line truncation 이력 → 원자적 쓰기(read full→transform→write once).
3. **CRLF 유지**.
4. **`git restore/checkout/reset --hard` 금지** (미커밋 작업 다수). `profiles/000660.yaml`는 HEAD 구버전이 아니라 커레이션본이 정답.
5. **Claude 주장 전부 독립 재현** — DART 8항목은 로컬에서 OpenAPI 재fetch, WACC·확률가중·재조정은 재계산. "일치"·"PASS" 곧이곧대로 믿지 말 것.
6. **항목 1번부터 명시** (누락 방지).

### 다음 액션
Codex는 §4 H-1~H-10 독립 재현 + §3 판단 8건 6축 평가 → [필수]/[권고]·반박/수용 판정 → 회신. Claude가 수용분 반영. **엔진 코드 수정 제안 시 별도 정책 확정 루프**(reporting-boundary·engine 규칙)로 분리.

---

## 9. Claude 회신 — Codex 평가 반영 (2026-07-16, 배포본 확정)

Codex 6축 평가 수령. 핵심 결과 재현 확인(draft:false·B/80·WACC 10.64%·확률가중 1,240,056·괴리 −32.7%). 8개 판정 + 2개 결론 처리:

| Codex 판정 | 처리 | 반영 내용 (근거 = 엔진 재실행) |
|---|---|---|
| 1 DRAM/NAND 분할 (권고) | **수용** | §1에 "OP마진 55/28/4.6%·자산비중 60/35/5%는 외부 검증값 아닌 가정" 명시 + "DCF·확률가중 헤드라인은 연결 EBITDA 기반이라 분할 가정과 독립" 추가 |
| 2 D&A 14.3895조 (수용) | 유지 | — |
| 3 capex_fade_to=1.3 (필수) | **수용+반증** | §4.2에 **민감도표(1.0→811,265·1.3→797,721·1.6→784,177)** 추가. 종착 ±0.3x당 DCF 주당 **±1.7%**로 영향 제한적(TV는 유지보수 capex=D&A로 정규화, 페이드는 5년 명시기간만). SOTP 주방법이라 헤드라인 영향 더 작음 |
| 4 시가총액 불일치 (수용+정정) | **정정** | §4.3 EV "1,322조"→**"시총 1,292.5조+순차입 9.8조=EV 1,302.3조÷EBITDA 61.6조=21.1x, 유통주식 기준"**. 포털 1,313조는 상장주식수(발행) 관행이라 ~20조 차이 각주. 메타·부록 시총도 유통기준 통일 |
| 5 WACC 자본구조 (필수) | **수용+반증** | §4.1에 "de 3.5%=시장가치 기준 저레버리지 가정, 장부 D/E gross 20.5%·net 8.2%" 명시. 장부 gross까지 높여도 relevering으로 **WACC 10.49~10.64%(<15bp robust)**, 최보수 10.64% 채택 명기 |
| 6 클램프 (수용) | 유지 | Bull/Base 1.14x 약함은 §0·부록에 이미 명시 |
| 7 컨센서스 339만원 (권고) | **수용** | "3,390,935원"→**"약 339만원(최고 약 530만원; Investing.com 집계, 2026-07 기준)"** |
| 8 단일 종가 (수용+권고) | **수용** | §6에 "전일 종가 2,082,000 기준 괴리 −40.4%, 급락 전후 결론 방향 동일" 보조정보 추가 |
| 결론 1: SOTP↔DCF 과잉표현 | **수용** | §4.2 "독립 2개 방법 수렴"→**"독립 검증이 아니다 — 동일 실적·D&A 기저 공유, capex 가정 민감. 동일 입력 기반 참고 교차검증"** |
| 결론 2: 배포 전 필수 3건 | **완료** | 시총·주식수 기준(4), WACC D/E 구분(5), capex 민감도(3) 전부 반영 |

**미반영/보류**: 없음(권고 포함 전건 반영). PDF 재렌더 완료(6p, 육안검증 §4.1 WACC 공시·§4.2 민감도표·§4.3 EV 정정 확인).

**UNVERIFIED 대응**: Codex는 OpenDART 원문 재호출을 이번 세션에서 수행하지 않음(저장 노트까지만 대조). Claude는 **당 세션에서 Chrome same-origin으로 OpenDART API를 실 호출**(company·fnlttSinglAcntAll·stockTotqySttus)하여 §2 8항목을 원 단위 대조함 — 재현 시 로컬에서 동일 호출로 교차확인 권장.

---

## 10. Claude 회신 2차 — Codex CONDITIONAL GO 반영 (H-8 정정, 배포 확정)

Codex가 OpenDART API를 독립 재호출하여 H-8 FAIL(매출총이익 10백만원 불일치) 검출. **Claude가 same-origin으로 재fetch 독립 확인**: 매출총이익 = **58,690,790**백만원(= 매출 97,146,675 − 매출원가 38,455,885). 프로필 세그먼트 GP 합계 58,690,800은 표시값 "58.6908조" 반올림 산물로 10백만원 과대였음 — Codex 지적 타당.

| 배포 전 필수 | 처리 |
|---|---|
| 1. 세그먼트 GP 합계 → 58,690,790 | **완료**: SEG3 gross_profit 680,634 → 680,624. 합계 58,690,790 = DART 원문 일치. **GP는 엔진 미사용이라 밸류에이션 불변**(재실행: draft:false·B/80·1,240,056 동일) |
| 2. _verified_data.md·핸드오프 GP 정정 | **완료**: 58,690,800 → 58,690,790, 매출원가 38,455,885 병기(§2·§4 H-2·본 절) |
| 3. PDF p4 차트 라벨 겹침(권고) | **완료**: `05_scenarios.png` 재생성 — "확률가중 1,240,056" 라벨을 제목 아래 흰 박스로 분리, 제목 pad 확대. PDF 재렌더·육안 확인 |

**H-8 재판정**: PASS (GP 원문 일치). **전 H-1~H-10 PASS.** 6축 평가는 전 항목 수용/충족(최저 48/60, 평균 ~52/60). CONDITIONAL GO → **GO 조건 충족**.

**잔여(비차단)**: Bull/Base EV 스프레드 1.14x의 약한 경제적 차별성(§0·부록 기명시), 컨센서스 원 리서치 표본 미검증(관찰치로만 사용). 둘 다 배포 차단 아님.
