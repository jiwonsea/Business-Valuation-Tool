# Codex 핸드오프 — PART B Round 3: as-of 가격 우선순위 + 역방향 DCF 진단 가드

> **실행 위치**: `F:\dev\Portfolio\business-valuation-tool`
> **재현 프로필**: `profiles/nexus.yaml` (SOTP, `ev_revenue` + `pbv` 혼합, `analysis_date: 2026-07-10`, `market_price: 1505`)
> **선행**: PART B Round 1~2 완료·검증됨 (`BACKLOG_bvt_partB_closure.md`)
> **후속**: 이 라운드 완료 후 PART A 재평가

## 작업 규칙
- working tree에 **미커밋 작업 다수**. `git checkout -- <f>` / `git restore` / `git reset --hard` **금지**.
- 파일 수정 직후 `ast.parse` + 줄 수 확인.
- 🔴 **작업 종료 직후 NUL 스캔 필수** — Round 2에서 `CLAUDE.md`·`profiles/nexus.yaml`·`engine/units.py`·`.claude/rules/engine.md` 4개가 **NUL 패딩으로 깨졌다**(`nexus.yaml`은 `yaml.reader.ReaderError`로 로드 불가 상태였음). 짧은 내용으로 덮어쓰면서 이전 파일의 잔여 바이트를 truncate하지 않은 것이 원인.
  ```bash
  python -c "
  import os
  bad=[p for r,d,f in os.walk('.') if '__pycache__' not in r and '.git' not in r
       for p in [os.path.join(r,x) for x in f] if p.endswith(('.py','.yaml','.md','.sql'))
       and open(p,'rb').read().count(b'\x00')]
  print('NUL:', bad or 'clean')"
  ```
- 완료 후 `python verify_partB_round2.py`, `python verify_partB_excel.py`, `pytest tests/ --deselect tests/test_engine.py::TestScenarioDriverRoundTrip` 전량 통과.
- **구현 전 정책 제안 먼저.**

---

# B3-1. 프로필의 `market_price`를 실시간 가격이 덮어쓴다 → **as-of 보고서 재현 불가** (P1)

## 증상

`profiles/nexus.yaml`은 as-of를 **명시**한다:
```yaml
company:
  analysis_date: '2026-07-10'
market_price: 1505          # 2026-07-10 종가
```
그런데 온라인 실행 시 Excel `Raw Data`에는 **1,558원**(실행 시점 실시간가)이 기록됐다. 결과적으로 **재무 기준일은 7/10, 가격만 7/13**이 되어 시장 프리미엄·괴리율·역방향 진단·품질 점수(시장가격 정합 축)가 **조용히 전부 달라진다.** 같은 프로필을 다른 날 돌리면 다른 보고서가 나온다.

## 근본 원인 — `cli.py:86-89`

```python
# Manual/profile market price override -- used offline (sandbox) when the
# live fetch is unavailable. A live price, if fetched above, takes precedence.
if not price and getattr(vi, "market_price", None) and vi.market_price > 0:
    price = float(vi.market_price)
```
`market_price`를 **"오프라인 폴백"**으로만 취급한다. 그러나 **프로필에 명시된 `market_price`는 as-of 선언**이다 — 작성자가 특정 기준일 가격으로 모델을 고정하겠다고 밝힌 것이다.

## 요구사항

1. **우선순위를 역전하라**: 프로필 `market_price`가 있으면 그것을 사용한다. 실시간 조회는 **값이 없을 때만** 채운다.
2. 실시간 조회를 강제하려면 **`--live-price` 플래그**를 추가하라 (주간 자동 파이프라인·`--company` 경로는 이 플래그를 쓰거나, `market_price`가 없으므로 기존대로 동작).
3. **두 값이 다르면 로그로 남겨라**:
   `as-of 1,505원 사용 (analysis_date 2026-07-10) — 실시간 1,558원은 무시됨. 실시간을 쓰려면 --live-price`
4. Excel `Raw Data`에 **가격 기준일**을 명시하라. 현재 `분석일 2026-07-10`과 `현재 주가 1,558`이 같은 시트에 아무 설명 없이 공존한다.
5. **하위호환**: `--company` 자동수집 경로와 주간 파이프라인(`scheduler/`)은 프로필에 `market_price`가 없으므로 영향 없어야 한다. 48개 프로필 중 `market_price`가 있는 것이 몇 개인지 먼저 조사하고, **산출값 diff를 보고하라** (이 프로필들은 값이 **의도적으로 바뀔 수 있다** — 실시간가 대신 as-of를 쓰게 되므로. diff-0을 강제하지 말고, 어느 프로필이 왜 바뀌는지 설명하라).

---

# B3-2. DCF 교차검증을 **skip해놓고** 역방향 DCF 진단을 돌린다 (P1)

## 증상

`python cli.py --profile profiles/nexus.yaml` 실행 로그:
```
SOTP DCF cross-validation skipped (ebitda<=0 or wacc<=tg)
...
[역방향 DCF 진단] 괴리율 73.8% (시장가 프리미엄)
  진단: WACC 과대추정
  시장 내재 WACC : 2.32%
  [권고사항] wacc_params 검토: 현재 WACC=10.33%, 시장 내재 WACC≈2.3%
             베타(bu) 또는 ERP를 업계 컨센서스와 비교해 재보정
```
엔진이 **"DCF 교차검증을 건너뛴다"고 스스로 선언한 직후**, 같은 DCF 모델을 역방향으로 풀어 "시장 내재 WACC 2.32%"를 출력하고 **"WACC를 과대추정했으니 베타·ERP를 재보정하라"는 오진 권고**까지 붙인다.

영업이익 14억·EBITDA 31억짜리 전환기 기업에서 이 값은 아무 의미가 없다. 직전 라운드에도 **2.58%**로 같은 문제가 있었고, 보고서에 유출되면 그대로 사고다.

## 근본 원인 — `cli.py:125-147`

```python
def _attach_gap_diagnostic(vi, result) -> None:
    """Compute and attach GapDiagnostic when market-intrinsic gap exceeds threshold.

    Requires: result.market_comparison already set, DCF-based primary method.
    No-op for non-DCF methods (SOTP with only peer multiples, DDM, RIM).
    """
    ...
    if mc is None or mc.market_price <= 0: return
    if abs(mc.gap_ratio) < GAP_THRESHOLD: return
    ...
    if ebitda_base <= 0: return
    # ← primary_method 체크가 **없다**
```

**docstring이 존재하지 않는 가드를 문서화하고 있다.** 실제 가드는 `ebitda_base > 0` 뿐이다. nexus는 `primary_method="sotp"`이고 `ebitda_base = 1,400 + 1,700 = 3,100 > 0`이라 통과해버린다. `run_valuation`(`valuation_runner.py:1152-1163`)이 이미 `calc_dcf`에서 `ValueError`를 받아 `dcf_result = None`으로 두고 경고까지 남겼는데, `cli.py`는 그 사실을 모른 채 **독립적으로 역방향 DCF를 다시 푼다.**

이건 Round 2에서 고친 **`console_report`의 distress 재계산**과 **동일한 안티패턴**이다 — *리포트/CLI 레이어가 엔진 계산을 복제한다.*

## 부수 결함 — 기준일 혼용 (Round 2에서 이미 죽인 패턴)

`cli.py:140-153`
```python
cons = vi.consolidated.get(by, {})          # 2025 = 거래 전 (원스토어 미연결)
ebitda_base = cons.get("op",0) + da_base    # 거래 전 EBITDA 3,100
shares = vi.company.shares_outstanding      # 증자 후 주식수
net_debt = vi.net_debt                      # 신규 CB 231억 포함 (거래 후)
market_ev = market_cap_display + max(net_debt, 0)
```
**분자는 거래 후, 분모는 거래 전.** Round 2에서 `Relative Valuation`(P0-3)과 `Peer 역산 패널`(P0-2)을 끈 것과 정확히 같은 사유인데, 이 경로만 살아남았다.

## 추가 결함 — 분모 불일치

`cli.py:150`이 `vi.company.shares_outstanding`을 쓴다. 그러나 PART B Round 2에서 **단일 분모를 `vi.valuation_shares`로 통일**했다. 이 함수만 옛 분모를 쓴다.

## 요구사항

1. **docstring이 약속한 가드를 실제로 구현하라.** 다음 중 하나라도 참이면 역방향 DCF 진단을 **끄고 사유를 출력**:
   - `result.dcf is None` (= DCF 교차검증이 skip됨)  ← **가장 견고한 신호**
   - `result.primary_method`가 DCF 기반이 아님
   - SOTP가 **mixed-method** (`is_mixed_method`)
   - Round 2에서 도입한 **기준일 정합성 검사**에 걸림 (거래 전 실적 ÷ 거래 후 자본구조)
   **어느 조합을 쓸지 먼저 제안하라.** 나는 `result.dcf is None`을 1순위로 본다 — 엔진이 이미 내린 판단을 CLI가 재사용하는 것이고, 계산 복제를 없애는 방향이기 때문이다.
2. **`shares_outstanding` → `valuation_shares`**로 교체하고, 분모가 산출물 전체와 일치하는지 회귀 테스트로 못박아라.
3. **계산 복제 안티패턴 전수 감사**: `cli.py`·`output/` 레이어가 엔진 결과를 재사용하지 않고 **다시 계산하는 곳**이 또 있는지 훑어라. (지금까지 발견: `console_report`의 distress 재계산 → Round 2에서 수정 / `cli.py`의 역방향 DCF → 이번 건.) **이 패턴이 세 번째로 나온 것이므로, 구조적 방지책도 함께 제안하라.**

---

## 회귀 기준

| 항목 | 기준 |
|---|---|
| 48개 프로필 | `unit_multiplier` / `weighted_value` / 시나리오 `post_dlom` / SOTP 세그먼트 EV **diff 0** — 단, **`market_price`가 명시된 프로필은 예외**(B3-1로 값이 의도적으로 바뀔 수 있음). 어느 프로필이 왜 바뀌는지 표로 제시 |
| `profiles/nexus.yaml` | 온라인 실행 시에도 **1,505원** 사용, 시장 프리미엄 **+282%** 유지 |
| `profiles/nexus.yaml` | 콘솔·Excel 어디에도 **"시장 내재 WACC"** 미출력 |
| 기존 DCF 프로필 | 역방향 진단이 **여전히 정상 작동**해야 한다 (가드가 과잉이면 안 됨). DCF 기반 프로필 하나로 회귀 확인 |
| 신규 테스트 | (a) `result.dcf is None`이면 gap_diagnostic 미생성 (b) 프로필 `market_price` > 실시간 (c) `--live-price`로 역전 (d) gap_diagnostic이 `valuation_shares` 사용 |

## 출력 형식
1. 정책 제안 (B3-2 가드 조합 / 계산 복제 구조적 방지책) — **코드 수정 전**
2. 승인 후 구현 → 파일:라인 diff
3. 회귀 증명 (위 표) + `verify_partB_round2.py` / `verify_partB_excel.py` / `pytest`
4. **NUL 스캔 결과**
5. 미해결 항목

---

# ⚠️ 정책 검토 (2026-07-13) — **조건부 승인. 아래 2건은 반드시 수정하고 착수할 것**

방향은 옳고, 계산 복제 방지책(`_attach_gap_diagnostic`을 `valuation_runner`로 이동, CLI는 호출만)은 특히 좋다. 그러나 **두 정책이 근거 데이터와 충돌한다.**

## 🔴 R-1. `market_price`의 **존재**로 as-of 의도를 판별할 수 없다 — `profile_generator`가 자동 기록한다

`pipeline/profile_generator.py:1183-1184`:
```python
_mp = _shares_info.get("price")
if _mp and not raw.get("market_price"):
    raw["market_price"] = _mp      # ← 자동수집 시 가격을 YAML에 박아넣는다
```

즉 `market_price`가 있는 11개 프로필 중 **10개는 사람이 선언한 as-of가 아니라 `--auto` 생성 시점의 자동 스냅샷**이다:

| 프로필 | analysis_date | market_price | 성격 |
|---|---|---|---|
| `nexus.yaml` | 2026-07-10 | 1,505 | **사람이 명시한 as-of** |
| `aapl` / `tsla` / `msft` / `googl` / `meta` / `amzn` / `000660` / `005930` / `nvda_ttm` / `nvda_fy27e` | 2026-06-27~07-10 | — | **자동 스냅샷** |

**우선순위를 "프로필 가격 우선"으로 일괄 역전하면, 이 10개는 앞으로 조용히 낡은 자동수집 가격과 비교하게 된다.** `--profile aapl.yaml`을 오늘 돌리면 6/27 가격으로 시장 비교·품질 점수(시장가격 정합 25점)·괴리율이 계산된다. 지금 고치려는 결함과 **방향만 반대인 같은 병**이다.

### 요구: **as-of 의도를 명시적 필드로 분리하라**

```yaml
market_price: 1505
price_as_of: '2026-07-10'    # ← 신규. 있으면 as-of 선언, 실시간가 무시
```

| `price_as_of` | 동작 |
|---|---|
| **있음** | 프로필 가격이 **권위**. 실시간가는 조회하되 **계산에 미사용**, 차이만 로그. `--live-price`로만 역전 |
| **없음** (자동 스냅샷) | **기존 동작 유지** — 실시간가 우선, 프로필 가격은 폴백. 단, 두 값이 유의미하게 다르면 **경고**("자동수집 스냅샷 298 vs 실시간 315 — as-of 고정을 원하면 `price_as_of` 선언") |

이렇게 하면:
- **10개 자동 프로필: diff 0** (회귀 부담 없음)
- **nexus: 진짜 as-of 재현성 확보**
- `profile_generator`가 앞으로도 `market_price`를 자동 기록해도 안전
- `--as-of` 플래그를 추가해 `price_as_of` 없이도 일시적으로 프로필 가격을 강제할 수 있게 하면 더 좋다

> 대안으로 `curated: true` 게이팅도 검토했으나, **11개 중 `curated`가 설정된 프로필이 0개**라 신호로 쓸 수 없다.

## 🔴 R-2. 가드 #2·#3이 **역방향 DCF를 설계 의도대로 쓰는 종목까지 죽인다**

`.claude/rules/engine.md:14`:
> **Reverse DCF / Narrative→Numbers (Damodaran)**: ... **Primary DCF use case for optionality-heavy stocks** — decoding market assumptions, not finding a 'correct' price target.

즉 역방향 DCF는 **옵셔널리티가 큰 종목**을 위해 만들어졌다. 그런 종목이 바로 SOTP다:

| 프로필 | 세그먼트 | methods |
|---|---|---|
| `nvda_ttm` / `nvda_fy27e` | 5개 | `ev_ebitda` + **`ev_revenue`** |
| `tsla` | 5개 | `ev_ebitda` + **`ev_revenue`** |
| `nexus` | 2개 | `ev_revenue` + **`pbv`** |

- **가드 #2 (`primary_method != "dcf"` → 차단)**: NVDA·TSLA는 SOTP다 → **차단됨.** 기능이 자기 주 용도에서 죽는다.
- **가드 #3 (mixed-method → 차단)**: `valuation_runner`의 mixed 판정은 *"default가 아닌 method가 하나라도 있으면"*(`ev_revenue` 포함)이다 → NVDA·TSLA **또 차단됨.**

### 요구: 차단 조건을 **equity-based 세그먼트 존재**로 좁혀라

| # | 가드 | 판정 |
|---|---|---|
| 1 | `result.dcf is None` (DCF 교차검증 skip) | ✅ **1순위 유지** — 엔진이 이미 내린 판단 재사용 |
| 2 | ~~`primary_method != "dcf"`~~ | ❌ **삭제** — 설계 의도(옵셔널리티 종목) 파괴 |
| 3 | ~~mixed-method SOTP~~ → **`pbv`/`pe` 세그먼트 존재** | ✅ **교체** — 회사 수준 EBITDA가 equity-based 세그먼트를 대표할 수 없다. `ev_revenue`는 EV 기반이므로 무해 |
| 4 | 기준일 정합성 검사 실패 | ✅ 유지 (Round 2 함수 공용 추출 좋다) |
| 5 | 통과 시에만 수행 + 분모 `valuation_shares` | ✅ 유지 |

결과: **nexus는 가드 1·3·4에 걸려 차단**(목표 달성), **NVDA·TSLA는 계속 작동**(설계 의도 보존).

**회귀 기준 추가**: `profiles/nvda_ttm.yaml`·`profiles/tsla.yaml`에서 **`gap_diagnostic`이 여전히 생성되는지** 반드시 확인하라. 이게 이번 수정의 과잉 여부를 가르는 핵심 테스트다.

## 🟡 R-3. 항목 번호가 또 1번부터 시작하지 않는다

제안서의 B3-2 목록이 **"2."부터 시작**하고, 본문은 *"nexus는 **1번**과 2·3·4번에 걸려"*라고 1번을 참조한다. 1번(`result.dcf is None`)이 **열거에서 누락**됐다.

지난 라운드에도 같은 번호 누락으로 **P1-1(MC PBV 포함)이 통째로 사라질 뻔했다.** 확정본에서 **1번부터 명시**하라.

---

## 나머지 승인

- `MarketComparisonResult`에 `price_source` / `price_as_of` 추가 → 좋다. Excel이 추론하지 않고 **실제 사용 가격의 출처·기준일을 표시**하는 방향이 맞다.
- `_attach_gap_diagnostic`을 `cli.py` → `valuation_runner.py`로 이동, CLI는 가격 선택 후 호출만 → **좋다. 계산 복제 안티패턴의 구조적 해법.**
- `cli.py`/`output/`의 엔진 직접 호출 전수 감사 + "필요한 표현" vs "금지할 재계산" 분류 → **좋다.** 이 패턴이 세 번 반복됐으므로 결과를 `.claude/rules/`에 규칙으로 남겨라.
- `--company` / weekly 경로 기존 동작 유지 → 좋다.

## 착수 조건
1. **R-1** (`price_as_of` 필드 도입) · **R-2** (가드 조건 교체) · **R-3** (번호 복원)을 반영한 **확정본 회신** (코드 X)
2. 승인 후 구현
3. 회귀: 자동 스냅샷 10개 **diff 0** / nexus 1,505원 고정·시장 프리미엄 +282% / **NVDA·TSLA gap_diagnostic 생존** / nexus "시장 내재 WACC" 미출력
4. **NUL 스캔** + `verify_partB_round2.py` + `verify_partB_excel.py` + `pytest`
