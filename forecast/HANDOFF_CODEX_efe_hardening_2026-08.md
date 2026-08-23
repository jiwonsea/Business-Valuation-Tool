# HANDOFF — EFE 하드닝 제안 (2026Q2 채점 세션에서 도출)

**From**: Cowork (Claude) · 2026-08-05
**To**: Codex CLI (Windows host)
**선행**: `HANDOFF_CODEX_efe_q2_2026_skhynix.md` §9~§18 · `reports/sk_hynix_q2_2026_scorecard.md`

---

## §0. 이 문서의 성격

SK하이닉스 2026Q2 채점 세션(7/29~8/5)에서 **실제로 발생했거나 직전에 잡힌 결함**만을 근거로 한 하드닝 제안이다. 착상이나 희망사항은 넣지 않았다 — 각 항목에 **"이 세션에서 무엇이 터졌는가"**를 명시했다.

**전부 제안이며 사용자 승인 전 구현 금지.** 우선순위는 "이 결함이 다시 나면 얼마나 조용히 틀리는가"로 매겼다. 조용히 틀리는 것이 시끄럽게 실패하는 것보다 나쁘다 — 이번 세션의 반복 주제였다.

---

## §1. P0 — 조용한 폴백 전수 감사 (fail-closed 원칙)

**터진 것**: `cli.py:191-193`. `--dry-run`에서 seed 분기가 없으면 WARNING 한 줄 찍고 **최신 fixture로 대체 후 exit 0**. 결과적으로 프로파일이 요구한 것과 **다른 윈도(2025Q1–Q4)의 리포트를 성공처럼 생성**했다. CLAUDE.md가 이 명령을 검증 수단으로 명시하고 있어, **문서화된 검증 절차가 거짓 통과를 냈다.** (결함 D1)

T2에서 같은 계열의 결정을 fail-closed로 처리한 전례가 생겼다 — `amount_as_of`가 계산 기준일보다 늦으면 거부, `basis: pre_tax`인데 세율이 없으면 거부. **이 원칙을 코드베이스 전체에 소급 적용해야 한다.**

**작업**
```
[ ] 전 코드베이스에서 "값이 없을 때 대체값으로 진행"하는 경로를 열거
    (grep 후보: logger.warning + 계속 진행, try/except 후 기본값, `or <fallback>`,
     dict.get(k, default), skip_unavailable, `if not x: x = ...`)
[ ] 각 경로를 3분류: (i) 정당한 기본값 (ii) fail-closed 전환 대상 (iii) 판단 보류
[ ] 표로 보고. 구현은 사용자 승인 후.
```
**D1 본체는 별도 결정 사항** — (a) dry-run도 loud fail(단 fixture 갱신 없이는 상시 실패) vs (b) fixture를 2026Q1까지 갱신(분기마다 유지 부담). 감사 결과와 함께 재제안할 것.

---

## §2. P0 — `scripts/verify_anchor.py` (G1을 실행 가능하게)

**터진 것**: SK하이닉스 2026Q2 채점의 프로비넌스 등급("5종목과 동등")은 **"현재 코드로 7/10 앵커가 relative error 0으로 재현된다"**는 살아있는 속성에 전적으로 의존한다. 지금 이 확인은 **사람이 기억해서 손으로 돌리는 절차**다(§16.2 G1). 잊는 순간, 등급이 깨진 줄도 모른 채 스코어카드에는 "5종목과 동등"이 남는다. **최악의 실패 모드는 조용한 등급 증발이다.**

**작업**
```
[ ] scripts/verify_anchor.py 신설. verify_9q_sha.py 패턴 준용(KNOWN_GOOD 상수, exit code).
[ ] 앵커 레지스트리를 데이터로: {company, anchor_date, expected: {base_rev, wtd_rev, wtd_op, wtd_ni, wtd_eps}}
    SK하이닉스 2026Q2 값은 핸드오프 §12.2 참조. 상대오차 허용 1e-9.
[ ] 9Q sha 검증도 함께 호출해 단일 명령으로 G1 전체를 커버
[ ] exit 0 = 등급 유지 / exit 1 = 등급 하향 사유 발생 (메시지에 명시)
[ ] pytest에 포함할지는 별도 판단 — 오프라인 재현 가능 여부에 달림. 불가하면 수동 스크립트로 두되
    CLAUDE.md §Verification에 등재.
```
**주의**: T3b·T4는 **의도적으로** forward를 바꿔 앵커를 깬다. 스크립트는 "롤 이전 앵커"를 별도 항목으로 보존할 수 있어야 한다(레지스트리에 `superseded_by` 필드).

---

## §3. P1 — FROZEN 무결성 테스트

**터진 것 2건**
1. AMD FROZEN에 프린트 후 `[PRE-PRINT ERRATA]`가 append되어 **워킹트리 ≠ 커밋 blob** 상태로 방치됐다. FROZEN의 가치는 바이트 불변성인데 그것이 깨졌다(사후 분리·커밋으로 해소, `5f02652`).
2. `.gitignore`의 `reports/sk_hynix_20*.md` 때문에 **날짜 접두 파일명은 조용히 추적되지 않는다.** Q3 FROZEN을 `sk_hynix_20260930_*.md`로 지었다면 규약 도입 즉시 무력화됐을 것이다.

**작업**
```
[ ] tests/test_frozen_integrity.py 신설:
    - reports/*_FROZEN.md 전수: git 추적 중인가
    - git check-ignore 대상이 아닌가
    - 워킹트리 blob == HEAD blob (수정 없음)
    - 헤더의 profile sha256 == 해당 프로파일 파일의 현재 sha (불일치 시 fail + 파일명 출력)
[ ] 실패 메시지에 조치 안내: "FROZEN은 편집 금지. 정정은 *_errata.md 형제 파일로."
```
`PROMPT_autofreeze_COMMON.md`에 체크리스트는 이미 들어갔으나 **문서는 강제하지 못한다.** 테스트가 강제한다.

---

## §4. P1 — 사후채점 공통화: 정규화 열 + 축퇴 플래그

**터진 것**: 4레버 표의 `매출 −1.4469%`가 9분기 이력 비율 범위(0.761~1.213) 밖인 0.545로 나왔다. 원인은 버그가 아니라 **레버가 실측 EPS로 정규화되는데 이번 실측 EPS가 일회성으로 1.89배 부풀어 전 레버가 0.53배 압축**된 것이었다. 검산 없이 표만 봤다면 **분기 간 레버 크기를 그대로 비교**했을 것이다. 또한 EPS가 파생치라 **주식수 레버가 구조적으로 0**인데, 이를 "정확했다"로 오독할 여지가 있었다.

두 보완 모두 **SK하이닉스 스코어러에만** 들어갔다. `engine/generic_postmortem.py`(GEV·TSLA·TXN·IBM 등 generic 경로)는 **같은 함정을 그대로 안고 있다.**

**작업**
```
[ ] generic_postmortem에도 ÷모델EPS 정규화 열 추가 (두 열 정의 각주 포함)
[ ] EPS가 파생치인 경우 shares_lever_degenerate 플래그 + 경고 문구 공통화
[ ] 두 정규화 각각에 대해 잔차 0 검증
[ ] 회귀: 기존 스코어카드(TSLA·TXN·IBM) 재생성 시 기존 열 값 불변
```
GEV·TSLA 사후채점 문서를 소급 갱신할지는 별도 판단(**기존 스코어카드 본문 수정은 신중히** — 채점 기록물이다).

---

## §5. P2 — 인용 스키마 강제

**터진 것**: T1 초안의 actual YAML이 IR **목록 페이지 URL**에 영어 verbatim 인용문 여러 개를 매달았고, ASP 2건은 회사 1차 원문이 아니라 **국내 언론 2차 보도**에서 온 값인데 1차처럼 표기됐다. 리포에 `2a26780 docs: require auditable primary-source citations` 정책이 이미 있었지만 **문서 정책이라 강제되지 않았다.** 지적 후 `tier: primary|secondary` 분리로 해소.

**작업**
```
[ ] inputs/*.yaml 의 sources 항목에 tier: primary | secondary 필수화 (스키마 레벨)
[ ] quote 는 "해당 URL에서 확인 가능한 문장" 또는 빈 문자열+note 중 하나 (임의 생성 금지)
[ ] 수치를 뒷받침하지 않는 출처는 sources에 넣지 않음 (검증 규칙)
[ ] 기존 inputs/*.yaml 소급 점검 후 위반 목록 보고 (수정은 승인 후)
```

---

## §6. P2 — CLAUDE.md §Verification 정정

**터진 것**: CLAUDE.md는 `python cli.py --company sk_hynix --dry-run`을 검증 명령으로 명시하는데, **그 명령이 무엇을 검증할 수 있고 없는지**는 적혀 있지 않다. 이 누락이 T0 게이트 오설계로 직결됐다(fixtures 2분기만 로드 → forward 윈도 재현 불가).

**작업**
```
[ ] dry-run의 검증 범위 명시: "fixtures 2분기 기반. forward 윈도가 2025Q1 이후인 프로파일의
    forward 재현은 검증하지 못한다. forward 재현은 live 모드 사용."
[ ] live 모드가 DART 캐시로 오프라인 동작한다는 사실 명시(verify_9q_sha.py와 동일 경로)
[ ] G1 / verify_anchor.py 를 §Verification에 등재
```

---

## §7. P3 — 이월 항목 (이 세션에서 의도적으로 미착수)

| 항목 | 출처 | 비고 |
|---|---|---|
| `backtest_methodology` 메모리 경로 이식 | §9.3-T4 | **T3b 선결 조건.** generic엔 이미 있음(`schemas/generic.py`) |
| `risk_band` raw dict → typed model | Codex NOTICED (`pipeline/ir_loader.py:105`) | 인접 리팩터, T2와 무관 |
| cross-stock op_margin 앵커 과대 | 5종목 + SK(+1.9pp) | SK는 **경로가 다름**(메모리 GM 체인) → 룰 이식 금지 |
| 컨센 vintage N 확장 | §5-T6 | KR 22사 컨센 확보가 첫 실vintage |

---

## §8. 규율 (전 항목 공통)
- **제안 단계. 사용자 승인 전 구현 금지.** 각 항목은 독립 승인 대상이다.
- 승인 후에도 §10(원 핸드오프) 절대 규칙 유효: 경로 명시 add, `git add -A` 금지, 커밋별 `pytest -q` green, 서명 트레일러 금지.
- **모든 변경은 G1 통과 필수** — 앵커 relative error 0 + 9Q sha `b979d79f…f6e7` MATCH.
- FROZEN·앵커 산출물·기존 스코어카드 본문은 수정 금지(정정은 append 또는 형제 파일).
- 신규 옵션 필드는 **부재 시 기존 동작과 bit-identical**.
- 인접 코드 리팩터 금지 — `NOTICED BUT NOT TOUCHING: file:line 증상` 로그로 대체.

## §9. 권장 착수 순서
```
§2 verify_anchor.py  (다른 모든 변경의 안전망이 되므로 먼저)
  → §3 FROZEN 무결성 테스트
    → §1 폴백 감사 (보고까지) → D1 결정 → 구현
      → §4 사후채점 공통화
        → §5 인용 스키마 → §6 CLAUDE.md
```
§2를 먼저 하는 이유: 이후 모든 하드닝 작업이 앵커를 깨지 않았는지 자동 확인 가능해진다.

---

# §10. §2 `verify_anchor.py` 승인 + 설계 핀 (2026-08-07)

제안 범위 **승인**. 아래 5개 핀을 반영할 것. §2 본문보다 우선한다.

## §10.1 🚨 핀 1 — Yahoo 레그를 타지 말 것 (게이트 신뢰성의 핵심)

"오프라인 재현"이라 했는데, `python cli.py --company sk_hynix`(live)는 **DART는 커밋 캐시로 오프라인이지만 `fetch_consensus(yahoo)`는 네트워크를 탄다.** Yahoo `.KS`는 원래 파손 상태이고(2026Q2 컨센 `n_a`), **컨센서스는 앵커 5개 값에 전혀 들어가지 않는다.**

cli를 통째로 호출하면 **앵커와 무관한 네트워크 장애로 게이트가 빨간불**이 된다. 그런 게이트는 몇 번 헛울리면 사람들이 무시하기 시작하고, 그 순간 게이트가 없는 것보다 나빠진다.

```
[ ] cli.py 를 shell out 하지 말 것. §12.3(T0c) 패턴대로 forward 체인을 직접 호출:
    load_profile → fetch_quarterly_actuals_series(커밋 DART 캐시)
    → _actual_for_quarter(seed) → MarginBaseline → build_margin_carryover
    → project_quarterly_revenue → project_margins → EPS 브리지
[ ] 데이터 로딩은 scripts/verify_9q_sha.py 패턴 복제 (검증된 오프라인 경로)
[ ] 네트워크 호출 0건. 검증할 것.
```

## §10.2 핀 2 — 허용오차 1e-9의 **근거를 문서화**

`verify_9q_sha.py`에 선례가 있다: CPython ≥3.12의 Neumaier 보상합 때문에 **환경별로 마지막 ULP가 갈려 canonical sha가 2개**다(sandbox `077ecb10…` / host `b979d79f…`). 앵커 5개 값도 host에서 측정된 것이므로 샌드박스에서는 마지막 ULP가 다를 수 있다.

상대오차 1e-9는 ULP 차이(~1e-16)를 충분히 흡수하므로 **적절하다.** 문제는 나중에 누군가 "정확히 같아야지" 하며 완전일치로 조이는 것이다.
```
[ ] docstring에 명시: "1e-9는 임의값이 아니라 환경별 ULP 편차(verify_9q_sha.py의 이중
    canonical 참조)를 흡수하기 위한 하한이다. 완전일치로 조이지 말 것."
```

## §10.3 🚨 핀 3 — **레지스트리 자체가 앵커다.** 같은 프로비넌스 규율 적용

`79070.26666360501` 같은 숫자를 출처 없이 하드코딩하면, 이번 세션 내내 다룬 "앵커가 추적되지 않는 문제"를 **한 층 위에서 재생산**하는 것이다. 이 값들의 원본은 `reports/sk_hynix_20260710.xlsx`이고 그건 **gitignore 대상**이다.

각 엔트리에 다음을 함께 기록:
```yaml
- company: sk_hynix
  period: "2026Q2"
  expected: { base_revenue: 79070.26666360501, ... }
  source_artifact: "reports/sk_hynix_20260710.xlsx"   # gitignored — 재생성 가능
  driving_profile_commit: "4ebeb7c"
  measured_at: "2026-08-02"
  measured_env: "CPython 3.14.3 / win32"
  verified_at_commit: "23b1d97"
```
```
[ ] 위 메타 없이 expected 값만 있는 엔트리는 스키마에서 거부 (fail-closed)
```

## §10.4 핀 4 — expected 값 **덮어쓰기 금지** 규율

이 파일은 "기대값을 현재 출력에 맞춰 고치는 곳"이 되기 가장 쉬운 파일이다. 그렇게 되는 순간 게이트가 아니라 **거수기**가 된다.
```
[ ] docstring에 명시: "expected 값을 현재 출력에 맞춰 수정하는 것은 금지.
    앵커가 의도적으로 바뀌었다면 기존 엔트리에 superseded_by 를 달고 새 엔트리를 추가한다.
    제자리 덮어쓰기는 어떤 경우에도 하지 않는다."
[ ] verify_9q_sha.py 의 KNOWN_GOOD 주석 톤을 준용
```

## §10.5 핀 5 — `superseded_by` 의미 고정

지금 정의해두지 않으면 T3b·T4 착수 시 급하게 즉흥적으로 정하게 된다.
```
superseded_by: { at_commit: "<sha>", reason: "T4 forward window roll to 2026Q3", date: "..." }
```
- 이 필드가 있는 엔트리는 **재현 검증에서 SKIP**하고 **FAIL로 취급하지 않는다**(더 이상 재현될 것으로 기대하지 않는 앵커).
- 출력에 `SKIPPED (superseded at <sha>: <reason>)`로 표시. **조용히 건너뛰지 말 것.**
- 해당 채점의 프로비넌스 근거는 `verified_at_commit` 시점 커밋에 남는다 — 스코어카드에 그 커밋 해시를 함께 기록할 것.

## §10.6 실패 메시지 요구사항
exit 1 시 **무엇을 해야 하는지**까지 출력할 것 — 원 핸드오프 §16.2의 "되돌리거나 등급 하향, 방치 금지"를 사람이 기억하고 있을 거라 가정하지 말 것.
```
FAIL: sk_hynix 2026Q2 anchor drift (weighted_eps: expected 70607.8551553665, got ...)
  -> 되돌리거나, reports/sk_hynix_q2_2026_scorecard.md §8 등급을 하향하고 사유를 기록할 것.
  -> 의도된 변경이면 superseded_by 를 달고 새 엔트리를 추가할 것 (제자리 수정 금지).
```

## §10.7 커밋
`feat(verify): add anchor reproduction gate` 1커밋. §8 규율 유효. 다른 세션의 미커밋 변경 보존.
**자기 검증**: 이 스크립트 자체가 G1을 통과시켜야 하므로, 커밋 직전 `verify_anchor.py` 실행 결과(PASS)를 보고에 포함할 것.

---

# §11. §2 종결 · §3 승인 + 설계 핀 (2026-08-07)

## §11.1 §2 종결
`9dcb563` (3파일, 394줄 추가). 독립 확인: `verify_anchor.py`의 유일한 httpx 참조는 `pipeline.dart_fetcher.httpx.get` **몽키패치 = 네트워크 차단 강제 장치**이며 호출이 아니다 — 핀 1 요구 이상. 자기 실행 PASS, 312 passed, ruff 통과. **G1이 이제 단일 명령으로 검증 가능.**

## §11.2 §3 승인 — 단, 아래 3핀 없이는 테스트가 상시 빨간불이 된다

§2 핀 1과 **같은 함정**이 §3에 있다: 정당한 상태를 FAIL로 판정하면 테스트가 몇 번 헛울린 뒤 비활성화되고, 그 순간 없느니만 못해진다.

### 핀 A 🚨 — "헤더 profile sha == 현재 프로파일 sha"는 **틀린 검사다**

프로파일은 동결 이후에도 정당하게 진화한다. `profiles/gev.generic.yaml`이 Q3용으로 갱신되면, Q2 시점 sha를 담은 `gev_q2_2026_forecast_FROZEN.md` 헤더와 **당연히 어긋난다.** 이건 결함이 아니라 정상이다. 현재 파일과 대조하면 시간이 갈수록 전 종목이 빨간불이 된다.

```
[ ] 올바른 검사: 헤더 sha == 동결 커밋 시점의 프로파일 sha
    → git show <freeze_commit>:<profile_path> | sha256sum 과 대조
[ ] 동결 커밋을 알아내는 방법: FROZEN 파일을 처음 추가한 커밋
    (git log --diff-filter=A --format=%H -- <frozen_path> | tail -1)
[ ] 그 커밋을 특정할 수 없으면 FAIL 아니라 SKIP + 사유 출력
```
**부수 효과**: 이 검사가 통과하면 "동결 시점 프로파일이 커밋되어 있었다"까지 동시에 입증된다 — §15.2(원 핸드오프)에서 다룬 "동결 = 커밋까지" 규칙의 자동 검증이 된다.

### 핀 B — 규약 이전 동결 파일을 소급 FAIL 처리하지 말 것

`googl/ibm/tsla/txn/gev` FROZEN은 `*_FROZEN.md` 규약이 정식화되기 전 산출물이라 헤더 필드가 완전하지 않을 수 있다. 소급 실패는 노이즈다.
```
[ ] 규약 적용 기준일 또는 파일별 opt-in 목록으로 대상 한정
[ ] 대상 외 파일은 SKIP 하되 "convention N/A (frozen before <date>)"로 **명시 출력**
    — 조용히 건너뛰지 말 것. 커버리지 공백이 보여야 한다.
[ ] 최종 출력에 "검사 N건 / SKIP M건" 요약
```

### 핀 C — git 없는 환경에서 graceful skip
tarball 실행·샌드박스 등 `.git`이 없는 환경에서 에러로 죽지 말 것. `git` 부재 시 SKIP + 사유 출력. (단 **호스트에서는 반드시 실행**되도록 CLAUDE.md에 명시)

## §11.3 §3 수용기준
```
[ ] reports/*_FROZEN.md 전수: git 추적 · check-ignore 비대상 · 워킹트리 blob == HEAD blob
[ ] 헤더 profile sha == **동결 커밋 시점** 프로파일 sha (핀 A)
[ ] 규약 이전 파일은 SKIP + 명시 출력, 커버리지 요약 (핀 B)
[ ] git 부재 시 graceful skip (핀 C)
[ ] 실패 메시지: "FROZEN은 편집 금지. 정정은 *_errata.md 형제 파일로."
[ ] G1 통과 (verify_anchor.py 로 확인)
```
`test(freeze): add FROZEN integrity gate` 1커밋. §8 규율 유효.

## §11.4 이후
§1(폴백 감사, 보고까지) → D1 결정 → §4 → §5 → §6. 각 항목 개별 승인.
반기보고서(8월 중순) 공시 시 보류 항목 일괄 해소 — 유효세율(T5) · T2 `basis` · 주식수 레버 축퇴 · 4레버→5레버 복원 · 키옥시아 P&L/OCI.
