# BVT 엔진·산출물 개선 — PART B Round 1~2 종결 보고

최종 2026-07-13 | 검증: `verify_partB_round2.py` (14/14) · `verify_partB_excel.py` (14/14) · `pytest 952 passed, 5 deselected`
회귀: 48개 프로필 중 실행가능 46개 — `unit_multiplier` / `weighted_value` / 시나리오 `post_dlom` / SOTP 세그먼트 EV **diff 0**

---

## ✅ 해소 완료

### Round 1 — 단위 계약 + SOTP 클램프 가시화
| # | 결함 | 수정 |
|---|---|---|
| P0 | `detect_unit()`이 매출 10,000~1,000,000(백만원) 구간을 **억원 단위로 오판** → 주당가치 **100배** (넥써쓰 106,526원 ← 실제 1,065원). 코스닥 대부분이 이 밴드 | KR 배율을 **1e6로 고정**. 억원은 표시 라벨 전용 |
| P0 | SOTP 시나리오 배수가 **조용히 클램프**(Bear×2.0)되어 Bull≈Base인 붕괴 모델을 만들면서도 정상 완료로 출력 | `logger.warning` + 리포트 상단 경고. 품질점수 연동(25→21). `curated` + `allow_wide_scenario_spread` 이중 opt-in |
| P1 | 단위 오염 경고가 **음수 내재가치**(distress — 엔진 정책상 정상)와 정상 고평가주를 오탐 | `intrinsic > 0` 가드 |
| P1 | Bull/Base 감점이 **시나리오 코드 이름에 의존** → A/B/C 프로필 6/48이 사각지대 | 확률 최대=Base, EV 최대=Bull 폴백 |
| P1 | 클램프(Bull/Bear ≤ 2.0)와 품질(Bull/Base ≥ 1.3)이 **수학적으로 충돌** → Base/Bear > 1.538이면 감점 회피 불가 | 임계 1.3 → **1.20** (한계 1.667로 완화) |

### Round 2 — Excel 산출물이 거짓 정보를 출력하던 문제
| # | 결함 | 수정 |
|---|---|---|
| P0 | **Sensitivity 시트 전멸** — `_seg_metric`이 pbv/pe에 0을 반환하는데 축을 자동 선택 → **열 축을 흔들어도 값 불변**. 축 범위가 가산식(`base + i`)이라 EV/Sales 0.45·PBR 0.70563에서 **음수 배수(−2.3x)** 생성 | pbv→`book_equity` / pe→`net_income_segment` **정식 축 지원**. **승법 격자**(×0.6~1.4, Base 포함, 양수 하한). `pbv_pe_ev` 병용 시 **ValueError**. 유효 축 <2면 표 미생성 |
| P0 | **Peer Comparison이 EV/EBITDA 중앙값 8.5x와 EV/Sales 0.45x를 직접 비교** → "중앙값 대비 **−94.7% 할인**, 레인지 밖" | `PeerCompany`의 기존 Optional 필드(`ev_revenue`/`pbv`/`trailing_pe`)를 **method별로 사용**. 불일치 peer는 통계 제외 + 경고. **혼합 SOTP에선 회사 단일 역산 배수 비활성** |
| P0 | **Relative Valuation이 거래 전 실적 ÷ 거래 후 자본구조** (P/B 4.07 = 시총 1,224.8억 ÷ 2025 자본 301억). 프로필에서 배수를 0으로 껐는데도 **그대로 출력** | 스위치 전부 0이면 **시트 미생성**. 기준일 정합성 필드 + 순차입금 괴리 휴리스틱. 음수 정당배수 N/A |
| **P1** | **MC가 PBV/PE 세그먼트를 조용히 건너뜀** → 혼합 프로필에서 **전 구간 음수 붕괴**(중앙값 **−401원**). 같은 프로필에서 SOTP와 MC가 **다른 모델**을 계산 | pbv → `book_equity × sampled PBR` 정식 가산. `effective_net_debt` 단정. **넥써쓰 MC 중앙값 350원 vs Base 364원 (3.8%)** ✅ |
| P1 | `console_report`가 `distress_max_discount`를 무시하고 **독립 재계산** → 모델은 할인 안 했는데 리포트는 "−10% 적용"이라고 **거짓 출력** | 콘솔 재계산 제거. 엔진이 실제 적용한 배수만 표시 |
| P1 | 시트마다 **주식수가 다름** (81,385,045 vs 81,383,610 = 자기주식 1,435) | 단일 분모 통일 + **불일치 시 강제 경고** |

### P2 (전부 완료)
1. `currency_unit` ↔ `unit_multiplier` 정합성 검증 (불일치 시 `ValueError`) — `schemas/models.py:86`
2. Bull 부재 시나리오 fallback 안전화 — `bull is base`면 **"업사이드 시나리오 부재"** 별도 경고 (스프레드 부족과 구분) — `engine/quality.py:676`
3. 밴드 예산 규칙 문서화: `(Base/Bear) × (Bull/Base) = Bull/Bear ≤ 2.0` → Base/Bear ≤ 1.667 — `.claude/rules/engine.md:71`
4. 클램프·wide-spread 허용 여부를 prediction snapshot에 영속화 — `db/backtest_repository.py:88`, `db/migrations_backtest.sql:27`

---

## ⚠️ 잔여 (PART A를 막지 않음)

1. **Supabase 마이그레이션 미적용** — `db/migrations_backtest.sql` 변경은 파일에만 있다. SQL Editor 또는 `supabase db push`로 적용해야 클램프 이력이 실제로 저장된다.
2. **콘솔 배수 반올림** — Excel은 `0.45` / `0.70563`을 정확히 표시하지만, `console_report`의 SOTP 표는 여전히 `0.5x` / `0.7x`로 반올림한다. 화면 표시 한정 (계산·Excel 영향 없음).
3. **`_SOTP_MAX_RATIO = 2.0`의 경험적 근거 부재** — 임의 상수인데 손으로 근거를 단 시나리오까지 무차별 삭감한다(넥써쓰: Bull 3.0 → 1.6). 백테스트나 레퍼런스를 붙이지 않으면 다음 사람도 같은 마찰에 막힌다.

---

## 🔴 프로세스 결함 — Codex 세션 종료 후 **NUL 스캔 필수**

Round 2 산출물에서 **파일 4개가 NUL 패딩으로 손상**됐다. 이미 `gotchas-tools.md`에 등재된 함정인데 **재발**했고, 이번엔 `CLAUDE.md`까지 물었다.

| 파일 | NUL | 영향 |
|---|---|---|
| `profiles/nexus.yaml` | 88 | **`yaml.reader.ReaderError` → `cli.py` 크래시.** Codex가 보고한 실행 결과는 디스크에 없는 상태에서 나온 것 |
| `CLAUDE.md` | 28,673 | 프로젝트 지시 파일 |
| `engine/units.py` | 315 | `ValueError: source code string cannot contain null bytes` |
| `.claude/rules/engine.md` | 362 | — |

전부 **말미 패딩**(짧은 내용으로 덮어쓰면서 이전 파일의 잔여 바이트를 truncate하지 않음)이라 NUL 제거만으로 복구됐다. 본문 유실 0.

**절차화**: Codex 작업 종료 직후 반드시 실행.
```bash
python -c "
import os
bad=[p for r,d,f in os.walk('.') if '__pycache__' not in r and '.git' not in r
     for p in [os.path.join(r,x) for x in f] if p.endswith(('.py','.yaml','.md','.sql'))
     and open(p,'rb').read().count(b'\x00')]
print('NUL 오염:', bad or 'clean')"
```

---

## 검증 재현
```bash
python verify_partB_round2.py    # 엔진 (MC 수용 기준 |median − Base|/Base < 15% 포함)
python verify_partB_excel.py     # Excel 산출물 (P0-2/P0-3/P2 표시 결함)
python -m pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip
```

---

# 🆕 PART A 검증에서 새로 드러난 BVT 결함 2건 (다음 라운드)

## B3-1. **프로필의 `market_price`를 실시간 가격이 덮어쓴다 → as-of 보고서 재현 불가** (P1)

`cli.py:86-88`:
```python
# Manual/profile market price override -- used offline (sandbox) when the
# live fetch is unavailable. A live price, if fetched above, takes precedence.
if not price and getattr(vi, "market_price", None) and vi.market_price > 0:
    price = float(vi.market_price)
```

`profiles/nexus.yaml`은 `analysis_date: 2026-07-10`과 `market_price: 1505`를 **명시**했는데, 온라인 실행 시 실시간가 **1,558원**이 이겨서 Excel에 기록됐다. **재무 기준일은 7/10인데 가격만 7/13** — 시장 프리미엄·괴리율·역방향 진단이 전부 조용히 달라진다. 정식 보고서는 as-of 재현이 불가능하다.

**설계 판단**: 프로필에 `market_price`가 **명시적으로 적혀 있다면 그것은 as-of 선언**이다. 실시간 조회는 **값이 없을 때만** 채워야 한다.

**요구사항**
1. 우선순위를 **역전**하라: 프로필 `market_price` > 실시간. 실시간을 강제하려면 `--live-price` 플래그.
2. 프로필 값과 실시간 값이 다르면 **양쪽을 로그로 남겨라** (`"as-of 1,505원 사용 (실시간 1,558원 무시) — analysis_date 2026-07-10"`).
3. Excel `Raw Data`에 **가격 기준일**을 명시하라. 지금은 `분석일 2026-07-10`과 `현재 주가 1,558`이 한 시트에 공존한다.

## B3-2. 혼합 SOTP에서 **DCF 교차검증이 실패했는데도 "시장 내재 WACC"를 출력한다** (P1)

`profiles/nexus.yaml` 실행 로그:
```
SOTP DCF cross-validation skipped (ebitda<=0 or wacc<=tg)
...
[역방향 DCF 진단] 괴리율 73.8% (시장가 프리미엄)
  시장 내재 WACC : 2.32%
```
DCF 교차검증을 **건너뛴 상태**에서 역방향 DCF 진단이 돌아 `시장 내재 WACC 2.32%`를 낸다. 영업이익 14억짜리 전환기 기업에서 이 값은 **아무 의미가 없고**, "WACC를 과대추정했다"는 오진 권고까지 붙는다. (직전 라운드에도 2.58%로 같은 문제가 있었다.)

**요구사항**: DCF 교차검증이 skip됐거나 SOTP가 mixed-method면 **역방향 DCF 진단 패널 자체를 끄고 사유를 출력**하라. Peer 역산 패널을 끈 것(P0-2)과 같은 원칙이다.

## B3-3. 산출물 버전 관리 (프로세스)
`valuation-results/`의 날짜형 첨부(`_eb_metrics.txt`, `*_2026-07-13.xlsx`)가 **PART B 이전 스냅샷**으로 남아 있었다. 엔진을 고치면 **산출물도 함께 갱신**되어야 한다 — 그렇지 않으면 리뷰어가 낡은 Excel의 `P/B 4.07`·`정당 P/B −0.71`을 보고 이미 고친 결함을 다시 지적한다(실제로 발생).

→ `regen_nexus_artifacts.py` 추가. 엔진 수정 후 반드시 재실행할 것.
