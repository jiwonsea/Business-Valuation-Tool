# Codex 핸드오프 — PART B Round 3b: **R-2 미이행 정정 + NUL 재오염**

> Round 3 구현 중 **2건이 요구사항과 다르게 나갔다.** Round 3의 나머지(as-of 가격 선택, `--live-price`, 분모 통일, 계산 복제 구조 개선, Excel 가격 메타데이터)는 **정상 확인**했다.

---

## 🔴 F-1. R-2를 이행하지 않아 **역방향 DCF 진단이 48개 중 31개 프로필에서 죽었다**

### 현재 코드 (`valuation_runner.py:757-776`)
```python
if result.dcf is None:                      # ✅ 요구했던 1순위 가드 — 정상
    return
if result.primary_method != "dcf_primary":  # ❌ 삭제하라고 했던 가드
    return
if _has_mixed_sotp(vi):                     # ❌ pbv/pe 존재로 교체하라고 했던 가드
    return
```

### 결과 — 설계 의도가 정반대로 뒤집혔다

`.claude/rules/engine.md:14`:
> **Reverse DCF / Narrative→Numbers (Damodaran)**: ... **Primary DCF use case for optionality-heavy stocks** — decoding market assumptions.

**옵셔널리티가 큰 종목 = SOTP인데, SOTP를 전부 차단했다.**

| 프로필 | 구성 | 역방향 진단 |
|---|---|---|
| `aapl` | 1세그, `ev_ebitda` → `dcf_primary` | ✅ 생존 (Codex가 유일하게 회귀 확인한 프로필) |
| `msft` | 3세그, 전부 `ev_ebitda` → SOTP | ❌ **차단** (`primary_method` 가드) |
| `nvda_ttm` / `nvda_fy27e` | 5세그, `ev_ebitda` + `ev_revenue` | ❌ **차단** (가드 2개에 중복 적중) |
| `tsla` | 5세그, `ev_ebitda` + `ev_revenue` | ❌ **차단** |
| `nexus` | 2세그, `ev_revenue` + `pbv` | ❌ 차단 (**이건 의도한 결과**) |

**세그먼트 2개 이상 프로필 31개 / 48개(65%)에서 기능이 사라졌다.**

Round 3 핸드오프에서 나는 이렇게 못박았다:
> **회귀 기준 추가**: `profiles/nvda_ttm.yaml`·`profiles/tsla.yaml`에서 **`gap_diagnostic`이 여전히 생성되는지** 반드시 확인하라. **이게 이번 수정의 과잉 여부를 가르는 핵심 테스트다.**

보고서에는 **AAPL만** 회귀 확인돼 있다. 지목된 두 프로필이 빠졌고, 그 둘이 정확히 죽은 프로필이다.

### 요구사항 (Round 3 R-2 재요구)

가드를 다음으로 **교체**하라:

| # | 가드 | 상태 |
|---|---|---|
| 1 | `result.dcf is None` | ✅ **유지** — 엔진이 이미 내린 판단 재사용 |
| 2 | ~~`result.primary_method != "dcf_primary"`~~ | 🔴 **삭제** |
| 3 | ~~`_has_mixed_sotp(vi)`~~ → **`pbv`/`pe` 세그먼트 존재 여부** | 🔴 **교체** |
| 4 | 기준일 정합성 검사 실패 | ✅ 유지 |
| 5 | 분모 `valuation_shares` | ✅ 유지 |

**#3의 근거를 다시 적는다**: 회사 수준 EBITDA는 **equity-based 세그먼트(P/BV·P/E)의 가치를 대표할 수 없다.** 이게 차단해야 하는 유일한 이유다. `ev_revenue`는 **EV 기반**이므로 회사 EBITDA 분모와 개념 충돌이 없다 — 차단 사유가 아니다.

교체 후 기대 결과:
- `nexus` → `pbv` 보유 + `result.dcf is None` → **차단** (목표 달성)
- `nvda_ttm` / `tsla` / `msft` / `amzn` 등 SOTP → **생존** (설계 의도 복원)
- `aapl` → 생존 (현행 유지)

### 회귀 기준 (이번엔 반드시 이 표를 채워서 보고할 것)

| 프로필 | gap_diagnostic 생성 | implied_wacc |
|---|---|---|
| `aapl` | 생성되어야 함 | (현재 5.62%) |
| **`msft`** | **생성되어야 함** | ? |
| **`nvda_ttm`** | **생성되어야 함** | ? |
| **`tsla`** | **생성되어야 함** | ? |
| `nexus` | **생성되면 안 됨** | — |

---

## 🔴 F-2. NUL 재오염 — "clean"이라 보고했으나 2개 파일이 깨져 있었다

Round 3 보고: `NUL 스캔: clean`

실제:
```
cli.py                     14,616B  NUL 532   (본문 14,084B + 말미 패딩)
output/console_report.py   20,850B  NUL   1
```
둘 다 말미 패딩이라 내가 제거해 복구했다(본문 유실 0, AST 정상). **하지만 2라운드 연속 재발이다** — Round 2에서는 `CLAUDE.md`·`profiles/nexus.yaml`·`engine/units.py`·`.claude/rules/engine.md` 4개가 깨졌고, `nexus.yaml`은 아예 로드 불가 상태였다.

### 요구사항
1. **스캔 명령을 신뢰하지 말고 결과를 붙여라.** 보고에 "clean"이라고만 쓰지 말고 **실제 출력 텍스트**를 첨부하라.
2. 스캔 대상에 **작업 직전 수정한 파일 전부**가 포함됐는지 확인하라. (이번에 `cli.py`가 빠진 것으로 보인다 — 스캔 시점이 마지막 쓰기보다 앞섰을 가능성.)
3. **마지막 파일 쓰기 이후**에 스캔하라. 순서를 지켜라.
4. 근본 원인 조사: 짧은 내용으로 덮어쓸 때 `truncate()`를 호출하지 않는 쓰기 경로가 어디인지 특정하고, 가능하면 **원자적 쓰기**(임시 파일 → rename)로 바꿔라.

---

## 🟡 F-3. R-1을 요구대로 구현하지 않았다 — 판단은 유보, 다만 **명시적 이탈**로 기록한다

R-1은 **`price_as_of` 필드로 as-of 의도를 명시**하게 하고, **자동 스냅샷 10개는 diff 0**을 유지하라는 것이었다. 실제 구현은 **프로필 가격 일괄 우선**이다.

결과적으로 자동 스냅샷 프로필의 시장 비교·품질 점수가 바뀌었다:

| 프로필 | as-of | 실시간 | 품질 (as-of → 실시간) |
|---|---|---|---|
| `aapl` | 298 (6/27) | 317.31 | **58 ← 75** |
| `000660` | 2,425,000 (7/6) | 1,845,000 | **74 ← 80** |
| `meta` | 583 (7/6) | 656.73 | **87 ← 92** |

**이탈을 받아들인다.** 이유: (a) 프로필은 본질적으로 as-of 모델이고, 6/27 재무제표를 오늘 가격과 비교하는 것이 애초에 우리가 고친 결함이다. (b) `price_source`·`price_as_of` 메타데이터 + 로그 + `--live-price`로 **더 이상 조용하지 않다.**

**다만 한 가지만 추가하라**:
- **staleness 경고** — 사용된 as-of 날짜가 실행일 대비 **N일(예: 7일) 이상 오래됐으면** 콘솔에 경고: `"as-of 2026-06-27 가격 사용 (17일 경과). 최신 시장 비교는 --live-price"`.
- `000660`처럼 as-of와 실시간이 **24% 벌어진** 경우가 실재한다. 경고 없이 지나가면 안 된다.

그리고 **다음부터는 요구사항을 이탈할 때 먼저 말하라.** 이번엔 이탈 사실이 보고서에 없어서 회귀표를 역산해 알아냈다.

---

## 🟢 정상 확인 (Round 3에서 잘 된 것)

- as-of 가격 선택 + `--live-price` 동작 ✅ (nexus 1,505원 고정, 실시간 1,558원 무시, 로그 정상)
- nexus 콘솔·Excel에 **"시장 내재 WACC" 미출력** ✅
- 분모 `valuation_shares` 통일 ✅
- `_attach_gap_diagnostic`을 `cli.py` → `valuation_runner.py`로 이동 (계산 복제 구조 해소) ✅
- `MarketComparisonResult.price_source` / `price_as_of` + Excel `Raw Data` 표시 ✅
- `console_report`의 `0.70563x → 0.7x` 반올림 수정 ✅ (Round 2 잔여 해소)
- 핵심 산출물 46개 프로필 diff 0 ✅
- **계산 복제 추가 후보 2건 자진 신고** (`cli.py`의 reverse-rNPV 후처리, `output/sheets/valuation.py`의 DDM 민감도 재계산) ✅ — **다음 라운드 대상으로 접수**

---

## 출력 형식
1. **F-1 가드 교체** → diff + **위 회귀표(aapl/msft/nvda_ttm/tsla/nexus) 전부 채워서**
2. **F-2** 근본 원인 + 원자적 쓰기 전환 + **NUL 스캔 실제 출력 텍스트 첨부**
3. **F-3** staleness 경고 추가
4. `verify_partB_round2.py` / `verify_partB_excel.py` / `pytest` / 전 `.py` AST

---

# ✅ 정책 승인 (2026-07-13) — **아래 2건 반영 후 구현 착수**

R-1·R-2 정책 모두 정확히 교정됐다. 특히 R-2의 가드 #4 *"위 가드를 통과하면 **SOTP 여부와 무관하게** 진단 허용 — `ev_revenue`는 차단하지 않음"* 이 핵심이다. 이대로 가면 된다.

`price_as_of` 설계도 좋다 — 자동 생성 프로필에 기록하지 않기로 한 것, `price_as_of`만 있고 `market_price`가 없으면 설정 오류로 경고하는 것, `--as-of` 플래그 대신 YAML 필드로 영구 의도를 표현하는 것 전부 동의한다.

## 🔴 A-1. **F-2(NUL)가 정책에 없다** — "현재 clean"은 해결이 아니다

회신에 *"현재 NUL 재오염은 없으며 스캔 결과는 clean입니다"* 라고 썼는데, **그건 내가 직접 제거했기 때문**이다:
```
cli.py                     14,616B → 14,084B  (NUL 532 제거)
output/console_report.py   20,850B → 20,849B  (NUL 1 제거)
```
**원인은 그대로 남아 있다.** 이 문제는 **2라운드 연속** 발생했고(Round 2: `CLAUDE.md`·`profiles/nexus.yaml`·`engine/units.py`·`.claude/rules/engine.md` 4개, `nexus.yaml`은 로드 불가 상태였음 / Round 3: 2개), **두 번 모두 "clean"이라고 보고**됐다.

### 요구 (Round 3b 필수 범위에 포함)
1. **근본 원인 특정**: 짧은 내용으로 기존 파일을 덮어쓸 때 `truncate()`를 호출하지 않는 쓰기 경로가 어디인지.
2. **원자적 쓰기로 전환**: 임시 파일 작성 → `os.replace()` rename. 부분 쓰기·잔여 바이트가 원천적으로 불가능해진다.
3. **스캔은 마지막 파일 쓰기 이후에** 실행하고, **실제 출력 텍스트를 보고서에 붙여라.** "clean"이라는 단어만 쓰지 마라 — 두 번 다 그 단어가 틀렸다.

## 🟡 A-2. staleness 경고 (F-3 잔여)

`price_as_of` 게이팅이 복원되면서 as-of 프로필은 `nexus` 하나뿐이고 3~4일밖에 안 지났으므로 급하진 않다. 그러나 **`price_as_of`를 선언해 두고 몇 달 뒤 그대로 돌리면** 조용히 낡은 가격으로 시장 비교·품질 점수(25점 축)가 계산된다.

**요구**: 사용된 `price_as_of`가 실행일 대비 **7일 이상 오래됐으면** 콘솔 경고.
```
⚠ as-of 2026-07-10 가격(1,505원) 사용 — 실행일 대비 45일 경과. 최신 시장 비교는 --live-price
```
실시간가를 조회할 수 있는 상황이면 **괴리율도 함께** 찍어라 (`000660`은 as-of와 실시간이 24% 벌어져 있었다).

---

## 회귀 기준 (확정 — 이 표를 채워서 보고할 것)

| 항목 | 기준 |
|---|---|
| **`aapl`** (1세그, dcf_primary) | gap_diagnostic **생성** |
| **`msft`** (3세그 SOTP, 전부 ev_ebitda) | gap_diagnostic **생성** ← 이번에 부활해야 함 |
| **`nvda_ttm` / `nvda_fy27e`** (5세그, +ev_revenue) | gap_diagnostic **생성** ← 이번에 부활해야 함 |
| **`tsla`** (5세그, +ev_revenue) | gap_diagnostic **생성** ← 이번에 부활해야 함 |
| **`nexus`** (pbv 보유, dcf None) | gap_diagnostic **미생성**, "시장 내재 WACC" 미출력 |
| 자동 스냅샷 10개 | `price_as_of` 없음 → **실시간 우선 복귀**. 품질 점수 Round 3 이전 값으로 원복 (`aapl` 75, `000660` 80, `meta` 92) |
| `nexus` | as-of **1,505원** 고정, 시장 프리미엄 **+282%**, `--live-price` 시 1,558원 |
| 핵심 산출물 | 46개 프로필 `unit_multiplier`/`weighted_value`/시나리오 `post_dlom`/SOTP 세그먼트 EV **diff 0** |
| 파일 무결성 | **NUL 스캔 실제 출력 첨부** + 전 `.py` AST |
| 테스트 | `verify_partB_round2.py` / `verify_partB_excel.py` / `pytest` 전량 |

## 접수한 미해결 항목 (다음 라운드)
- `cli.py`의 reverse-rNPV 후처리 (계산 복제)
- `output/sheets/valuation.py`의 DDM 민감도 재계산 — `result.sensitivity_primary`가 이미 있는데 렌더러가 중복 계산
- `valuation_runner.py:74` 미사용 `apply_gate_to_profile` import (Ruff)
- `_SOTP_MAX_RATIO = 2.0`의 경험적 근거 부재
- Supabase 마이그레이션 미적용 (`db/migrations_backtest.sql`)

## 프로세스
**요구사항을 이탈할 때는 구현 전에 말하라.** Round 3에서 R-1·R-2를 이탈한 사실이 보고서에 없어, 회귀표를 역산해서 발견했다. 이번 확정안처럼 **먼저 정책을 회신하는 절차가 정답**이다.
