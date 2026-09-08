# 프로젝트 개선 계획 · CLAUDE 검토 요청

작성일: 2026-09-07 · 기준 HEAD: `6634c1f`
상태: **I-1~I-5 구현·교차검토 최종 GO / 사용자 승인으로 5개 커밋 분리·PR 준비 진행 / 최신 진행 기록 §20**

## 1. 목적과 진행 방식

기업가치평가와 실적추정의 신뢰성·재현성·운영 완성도를 높인다. 우선 확인된 보호 장치와 검증 누락을 닫고, 설치 경로를 검증한 후 다종목 확장으로 진행한다.

사용자 요청: 폴더 상세 조사 → 개선 계획 → 별도 CLAUDE 세션 검토 → 답변을 Codex에 전달 → 계획 확정 → 구현.

이 문서는 전체 로드맵과 첫 작업의 구체적 범위를 함께 제시한다. 로드맵 검토는 모든 단계의 일괄 구현 승인이 아니다. 첫 작업만 확정하여 구현하고, 이후 작업은 각각 독립 변경으로 진행한다.

## 2. 조사 범위와 현재 구조

- README, root/forecast AGENTS, pyproject 2개, CI, 최근 15개 커밋, 미커밋 상태, 주요 NEXT_SESSION 및 D10 계획·인수인계 문서를 확인했다.
- 가치평가: `schemas/` 입력 계약 → `valuation_runner.py` 방법론 분기 → `engine/` 계산 → `output/` 및 DB. `pipeline/`, `ai/`, `scheduler/`가 수집·자동화를 담당한다.
- 실적추정: `forecast/cli.py` → 수집·프로필 → 실적/시나리오/백테스트 → 컨센서스 비교 및 valuation bridge → 보고서.
- 두 모듈은 통합 설치되지만 탄력도 연결은 offline seed 방식이다. `engine/eps_elasticity.py`의 계산과 `forecast/engine/valuation_bridge.py`의 소비 계약이 존재한다. D10 배치 러너는 명세 rev-8이 종결된 상태이며 전제조건이 남아 있다.
- Git 추적 Python 파일 실측: `engine/` 32개·6,836줄, `pipeline/` 21개·7,225줄, `forecast/` 142개·22,548줄(테스트 포함), `calibration/` 14개·2,575줄(테스트 포함).
- 추적 YAML 프로필: root 48개 / forecast 17개. 파일 개수이며 회사 수·검증된 지원 종목 수와 같지 않다.
- 테스트 함수 정의: BVT 49개 테스트 파일·1,071개 함수, forecast 54개 파일·343개 함수. 파라미터화된 pytest 실행 건수와 구분한다.

전수 코드 감사나 최신 재무 가정 검증을 완료했다는 뜻은 아니다. 핵심 진입점·보호 장치·설정·기존 백로그를 조사하고 아래 항목을 직접 재현했다. 외부 재무 데이터 재수집, 유료 LLM 호출, 운영 DB 변경은 수행하지 않았다.

## 3. 실행 기준선

| 검증 | 결과 | 해석 |
|---|---|---|
| `python -m pytest tests/ forecast/tests/ -q --tb=short` | 1,465 passed / 3 skipped / 1 deselected / 1 warning, 47.62초 | 기존 두 스위트 통과 |
| `python -m pytest calibration/tests/ -q --tb=short` | 34 passed, 0.57초 | 기본 수집 및 CI에서 빠진 별도 스위트 |
| `python -m pytest forecast/tests/test_frozen_integrity.py -q -s --tb=short` | pytest 2 passed; 내부 게이트 지원 4/4 PASS, 지원 SKIP 0 | 구 규약 비대상 보고서 5건은 내부 SKIP |
| 추적 Python 중 root Ruff 적용 범위 lint/format | lint 통과 / 196개 파일 format 통과 | forecast와 .claude 제외 |
| 로컬 `ruff check .` | untracked `blog/lib/`에서 3건 | 현재 추적 코드의 CI 실패로 단정하면 안 됨 |
| 로컬 `ruff format --check .` | untracked blog 3개 + scripts 2개 | 기존 개인 작업; 일괄 수정 대상 아님 |

환경: 로컬 테스트는 Python 3.14 계열, CI 설정은 Python 3.11. 위 결과는 로컬 결과이며 원격 CI 통과를 새로 확인한 것은 아니다.

pytest skip 3건: Windows symlink 권한, Windows process-group 미지원, gitignored EDGAR 캐시 부재. deselect 1건은 기본 `not network` 설정에 따른다. 경고 1건은 Supabase의 gotrue deprecation이다.

## 4. 확인된 개선 항목

| ID | 우선순위 | 확인 사실 | 영향 및 권고 |
|---|---|---|---|
| I-1 | P1 · 첫 작업 | `forecast/tests/test_valuation_allowlist.py:_frozen_profile_names()`가 `split('_')[0]` 사용. 합성 `vst_v2_q2_2026_forecast_FROZEN.md`가 `vst.generic.yaml`로 해소됨 | underscore 티커 보고서가 다른 프로필의 보호 검사를 받을 수 있음. 현 9개 보고서 문제는 없으나 다종목 확장 전 교정 |
| I-2 | P1 · 다음 독립 작업 | root `testpaths`는 tests/forecast/tests만 포함. CI도 두 경로만 실행. `calibration/tests/` 34개 별도 통과 | 보정 로직 회귀가 기본 검증을 통과할 수 있음. 수집 설정과 CI에 추가 |
| I-3 | P1 · 설치 검증 | setuptools 현재 include 패턴으로 `backtest` 패키지가 선택되지 않음. `cli.py:267-268`은 이를 import | wheel 설치 후 backtest 기능 누락 위험. 소스·editable 설치 테스트가 가릴 수 있으므로 wheel 재현 후 최소 교정 |
| I-4 | P2 · 문서/연속성 | root TODO.md 없음. 기존 NEXT_SESSION 내용과 현 코드 불일치. README의 엔진 19개 및 6-method 설명은 현재 rNPV 포함 구조와 다름 | 다음 세션이 완료된 작업을 반복할 위험. 검증 근거를 가진 단일 백로그 및 핵심 문서 정합화 |
| I-5 | P2 · CI 품질 범위 | root Ruff는 forecast 제외, forecast CI는 pytest만 실행 | forecast에 자체 Ruff 규칙은 있지만 CI 검증 없음. 부채 수를 먼저 측정하고 별도 범위로 도입 |
| I-6 | P2 · 기능 확장 | D10 명세는 종결되었지만 P-1 filename guard, P-2 provenance 등 전제조건이 남음 | 명세를 다시 설계하기보다 선행조건 확인 후 offline 다종목 측정 구현 |
| I-7 | 정책 결정 | R10 이월 문서는 음수 equity 0원 하한과 EV 비례 NCI를 요청. 현 AGENTS는 음수 equity 보존을 명시 | 일반 회귀 수정으로 처리 불가. 원시 equity, 투자자 payoff, 표시값·가중값·MC 통계 계약을 먼저 결정 |

I-3에서 확정한 것은 **패키지 선택 누락**이다. 실제 wheel 빌드·외부 디렉터리 설치 실행은 아직 수행하지 않았으므로 설치 장애 전체 범위는 미확정이다. `calibration`도 include 범위 밖이며 배포 대상인지 결정해야 한다. forecast YAML 등 리소스 포함/경로 계약도 같은 검증에서 점검한다.

## 5. 완료된 백로그와 혼동 방지

- 자동 분석 DB 저장 누락은 현재 재구현 대상이 아니다. `pipeline/profile_generator.py:1002-1004`, `1522-1524`에 `_save_to_db` 호출이 존재한다. 실제 운영 DB 스키마 적용 여부는 이번 조사로 확인하지 않았다.
- 시나리오 차별화와 프로필 테스트 fixture 분리는 이미 구현되어 있다. 구 문서의 deselect/재구현 제안을 재개하지 않는다.
- 탄력도 계산의 비양수 base EV/equity 거부는 `engine/eps_elasticity.py`에 구현되어 있다. 이것은 모든 시나리오 음수 값을 0으로 만드는 정책과 다르다.
- HEAD `6634c1f`는 MC 음수 equity에 DLOM을 적용하지 않도록 수정한 커밋이다. 0원 하한 구현으로 해석하지 않는다.
- KR 순차입금 오염 백로그는 7월 이후 프로필 커밋이 있어 과거 mtime만으로 대상 확정 불가. 현재 파일·기준연도·provenance와 같은 시점 원천을 대조해야 한다. 이번 조사에서는 오염 여부를 판정하지 않았다.
- D10 rev-8 명세는 8차 검토로 종결됐다. 확장 전에 약 1,400줄 문서 전체를 다시 쓰는 작업을 시작하지 않는다.

## 6. 첫 구현 제안: I-1 FROZEN 해석 보호

목표: 잘못된 파일명 유도가 실존하는 다른 프로필을 가리켜도 성공 처리되지 않게 한다. 현재 보고서 매핑·allowlist·FROZEN 자료는 유지한다.

수정 대상 코드: `forecast/tests/test_valuation_allowlist.py` 1개. 검토 결과·완료 상태는 이 계획서에 기록한다. 기존 인수인계 문서 갱신은 필요 파일과 변경 문장을 먼저 확정한다.

권고 정책: 기존 명시 매핑 우선. 규약으로 확실히 해석할 수 없는 이름은 `UNRESOLVED`로 실패하고 명시 등재를 요구한다. `vst_v2`를 다른 프로필로 추정하여 자동 통과시키지 않는다. 아직 없는 보고서의 매핑을 미리 추가하지 않는다.

CLAUDE 검토 반영: `forecast/profiles/vst_v2.generic.yaml`은 실존하며 `vst_q2_2026_forecast_FROZEN.md:310`이 지정한 errata 프로필이다. 현재 명시 매핑에는 원래 `vst.generic.yaml`만 있으므로, `vst_v2.generic.yaml`의 valuation 오염은 FROZEN CONTAMINATED 검사가 아닌 allowlist exact equality의 UNEXPECTED HOLDER가 방어한다. 이번 변경은 이 errata 대응 관계를 확장하지 않으며 명시 매핑이나 allowlist를 수정하지 않는다.

주의: 이전 계획의 “stem 접두어 확인”을 단순 `startswith('vst_')`로 구현하면 `vst_v2_...`도 통과하므로 결함이 유지된다. 티커 경계와 허용 보고서 suffix 규약을 명확히 해야 한다. CLAUDE는 현 9개 보고서와 합성 케이스에 적용 가능한 판별 규칙을 검토해 달라. 확정 전에 최장 접두어 자동 선택으로 범위를 넓히지 않는다.

완료 기준:

1. 기존 9개 보고서 → 프로필 매핑 동일, 실제 스캔 17개 / valuation 보유 1개 / 실패 0개.
2. `vst_v2_...` + `vst.generic.yaml` 실존 케이스가 잘못 매핑되지 않고 명시 실패.
3. underscore 이름의 명시 매핑은 올바르게 해소됨(합성 데이터/monkeypatch로 검증).
4. 단일 토큰 정상 경로, 없는 프로필, 모호한 이름/비정상 suffix를 각각 검증.
5. allowlist exact equality 및 FROZEN contamination 검사가 약화되지 않음.
6. `test_frozen_integrity.py`, `VALUATION_ALLOWLIST`, 실제 profiles 및 FROZEN 파일 내용 불변. 지원 4/4 PASS / 지원 SKIP 0 유지.
7. 대상 파일 Ruff lint/format, 전체 BVT·forecast·calibration 테스트 통과. 기존 환경 skip은 사유와 함께 보고.
8. 파일 저장 후 Python 구문·NUL·줄바꿈·diff 확인. 기존 사용자 변경과 구분하여 보고.

## 7. 후속 구현 순서와 각각의 완료 기준

| 순서 | 작업 | 예상 파일 범위 | 완료 기준 |
|---|---|---|---|
| 2 | I-2 calibration 검증 편입 | `pyproject.toml`, `.github/workflows/ci.yml` | 기본 pytest와 BVT CI 명령 모두 34개 calibration 테스트 수집·실행, 기존 스위트 누락 없음 |
| 3 | I-3 설치 경로 재현·수정 | `pyproject.toml`, 설치 smoke 검사 및 CI 연결(재현 후 확정) | wheel 안의 필요한 모듈 확인, repo 밖 설치 경로에서 CLI import/핵심 offline 경로 통과. live API/운영 DB 사용 없이 검증 |
| 4 | I-4 현재 상태 정리 | `TODO.md` 신규, `README.md`, 필요한 project AGENTS 항목 | 완료/미완료/정책대기 구분과 각 근거 명시. dirty CLAUDE.md 직접 덮어쓰기 금지. 전역 AGENTS 수정 없음 |
| 5 | I-5 forecast CI lint | forecast Ruff 설정·CI·확정한 파일 집합 | 부채 기준선 측정 후 신규 위반 차단 범위 확정. 대규모 format diff와 기능 변경 분리 |
| 6 | I-6 D10 다종목 측정 | 기존 SPEC §13/§15가 지정하는 범위 | P-1~P-6 체크, provenance·tax_rate_basis·입력 SHA·실패 계약 검증, 기존 수치 및 FROZEN 불변 |

첫 작업이 확정되더라도 2~6번을 한 번에 수정하지 않는다. 각 독립 변경의 검증 결과를 확인한 뒤 진행한다. 기존 루트 대형 파일을 분리하는 리팩터링은 구체적 결함이나 테스트 경계 개선 효과를 입증한 경우에만 별도 제안한다.

## 8. 정책 검토로 분리할 항목

음수 equity / NCI:

- 원시 순자산 잔여값, 유한책임 payoff, 보고서 표시값이 같은 필드를 써야 하는지부터 결정한다.
- 0원 하한이 필요하더라도 기존 raw equity와 MC 전체 분포 통계 보존 규칙을 조용히 변경하지 않는다.
- NCI EV 비례 근사는 승인된 기업별 적용 범위, Base EV가 0 이하일 때의 처리, 시나리오·MC·민감도·출력의 일관성이 필요하다.
- 과거 문서의 42,098원/46,485원 등은 과거 수동 교정 결과이다. 현재 코드의 새로운 회귀 기대값으로 바로 사용하지 않는다.
- 이는 가치평가 정책 검토이며 이 문서는 새로운 방법론이나 투자 판단을 확정하지 않는다.

데이터 갱신:

- 현재 프로필의 as-of, 결산연도, 원천 및 normalization 상태를 먼저 집계한다.
- 네트워크 감사는 대상·원천·호출 수·비용을 확정한 뒤 수행한다. 전체 `--auto` 재생성은 범위에 넣지 않는다.
- 운영 DB migration은 코드 호출 유무와 별도로 스키마 상태를 확인해야 한다.

## 9. 작업 폴더 보호

조사 시작 시 tracked 변경은 `CLAUDE.md` 2줄 추가이며, `.agents/`, blog, profiles, 연구 스크립트, 많은 HANDOFF/REPLY/PLAN 파일이 untracked 상태였다. 이를 삭제·이동·일괄 format·stage하지 않는다. 이번에 새로 작성한 파일은 본 계획서뿐이다(테스트 임시 파일/캐시 제외).

구현은 승인된 파일만 변경한다. `git restore`, 강제 reset, 임의 stash, 실제 프로필 재생성 및 FROZEN 변경은 하지 않는다. 로컬 미커밋 자료를 “잡파일”로 판단하여 정리하지 않는다. 원격 커밋·PR·merge·배포는 이번 계획 작성 단계에서 실행하지 않는다.

## 10. CLAUDE에게 요청하는 검토

**읽기 전용으로 검토하고 구현하지 말 것.** 사용자에게 아래 형식으로 답변해 달라. 비밀값이나 .env 내용은 출력하지 말 것.

1. 판정: `GO` / `CONDITIONAL GO` / `NO-GO`.
2. 확인 사실 오류: 파일·함수 또는 실행 결과를 근거로 지적. 과거 인수인계의 주장만 반복하지 말 것.
3. [필수] / [권고] 수정: 중요도와 최소 수정안을 구분.
4. 첫 작업 I-1의 안전한 filename 판별 규칙: 9개 기존 매핑 유지 및 underscore 오해석 거부가 실제로 동시에 가능한지 검토. 단순 접두어 검사 함정 확인.
5. I-1과 I-2 중 첫 구현 우선순위 유지/변경 의견.
6. I-3의 배포 계약: checkout/editable 전용인지 wheel 설치도 지원할지, backtest/calibration 및 데이터 리소스 포함 범위 의견.
7. I-7은 일반 버그 수정과 분리한다는 판단에 동의하는지, 사용자 결정이 필요한 쟁점.
8. 확정 가능 범위: 이번 첫 구현의 허용 파일·변경·완료 기준을 한 묶음으로 회신.

검토 답변을 받은 Codex는 필수 수정 반영 및 정책 충돌 해소 후 사용자에게 첫 구현 계획 확정을 요청한다. 확정 전 제품 코드 수정은 시작하지 않는다.

## 11. CLAUDE 회신 반영 및 I-1 실행 기록

사용자가 전달한 CONDITIONAL GO의 §8 범위에 따라 I-1만 진행한다. 허용 코드 파일은 `forecast/tests/test_valuation_allowlist.py` 하나이며 이 계획서에 결과를 기록한다. I-2 이후 로드맵은 미착수 상태다.

- 필수 1: 기존 `test_unresolvable_frozen_report_is_rejected`를 규약 비대상 사유에 맞게 수정했다. 프로필 파일 부재 테스트는 별도로 추가했다.
- 필수 2: `frozen_profiles`와 해석 함수 반환 타입을 `dict[str, str | None]`으로 명시했다. 미해소 파일명에 추정 이름을 저장하지 않는다. 실제 보고서 개수 9개 단언은 유지했다.
- 필수 3: 실존 `vst_v2` errata 프로필과 현재 방어 경계를 §6에 기록했다.
- 판별 계약: 명시 매핑 우선 → 소문자 영숫자 ticker + `q[1-4]_YYYY` 또는 `fyYYYYq[1-4]` + `_forecast_FROZEN.md` 전체 일치 → 그 외 None. 새 티커 문자/기간 표기는 명시 등재가 필요함을 주석으로 남겼다.
- 회귀 검증: 기존 구현에 테스트를 먼저 적용하여 9 failed / 12 passed를 확인했다. 교정 후 21개 통과(기존 10개 + 신규 파라미터화 실행 11개).
- 줄바꿈: 검토 회신은 CRLF 유지를 요청했지만 실제 대상 파일 기준선은 LF 248개 / CRLF 0개였다. 불필요한 전체 줄바꿈 변환 없이 기존 LF를 유지한다.
- 후속 I-2 완료 기준에 import file mismatch 없음 및 기존 수집 수 +34를 포함한다. calibration lint는 이미 적용되어 있으며 누락은 테스트 실행이다.
- 후속 I-3의 checkout/editable 전용 계약은 CLAUDE의 권고로 기록한다. 이번에 wheel 지원 포기나 패키지 설정 변경을 확정하지 않는다.

최종 검증 (2026-09-07, 로컬 Python 3.14):

| 게이트 | 결과 |
|---|---|
| 전체 `python -m pytest tests/ forecast/tests/ calibration/tests/ -q --tb=short` | **1,510 passed / 3 skipped / 1 deselected / 1 warning**, 35.47초. 기존 1,465 + calibration 34 + 신규 11과 일치. import mismatch 없음 |
| 대상 allowlist 파일 | **21 passed** |
| 실제 매핑 기준선 직접 대조 | **9개 모두 동일**, 스캔 17 / 보유 1 / 대응 9 / 실패 0 |
| FROZEN integrity | **지원 4/4 PASS / 지원 SKIP 0**, 비대상 보고서 5건 내부 SKIP; pytest 2 passed |
| 대상 Ruff lint / format | 모두 통과 |
| 대상 Python 구문 / NUL / 줄바꿈 | ast.parse 성공 / NUL 0 / LF 352개, CRLF 0 (기존 LF 유지) |
| 보호 파일 SHA-256 대조 | **28개 모두 바이트 동일**: 기존 사용자 CLAUDE.md, integrity 테스트, forecast 프로필 17개, FROZEN 보고서 9개 |
| 코드 변경 범위 | `forecast/tests/test_valuation_allowlist.py`만 변경; 사용자 기존 `CLAUDE.md` +2줄 보존. 본 계획서는 별도 untracked 문서 |

skip 3건은 기존과 동일: Windows symlink 권한, Windows process-group 미지원, gitignored EDGAR 캐시 부재. deselect는 network 마커, warning은 gotrue deprecation이다. 새 회귀·실패 없음. 원격 CI 및 별도 CLAUDE 사후 재현은 아직 수행하지 않았다. 커밋·PR 생성은 하지 않았다.

CLAUDE 사후 검토용 프롬프트:

```text
@PLAN_project_improvements_2026-09-07.md
@forecast/tests/test_valuation_allowlist.py

§11 구현 결과를 이전 CONDITIONAL GO의 필수 3건 및 §8 허용 범위와 대조해 읽기 전용으로 검토해줘.
git diff에서 기존 CLAUDE.md +2줄은 제외하고, I-1 규약 해석·None 계약·두 실패 사유·새 회귀 테스트를 확인해줘.
기존 9개 매핑과 FROZEN 보호가 유지되는지 확인하고 GO 또는 남은 필수 수정사항을 회신해줘.
줄바꿈은 실측 기준선이 LF였으므로 LF를 보존했어. I-2 구현이나 다른 파일 수정은 시작하지 마.
```

## 12. I-1 사후 GO 및 I-2 실행 기록

사용자가 전달한 CLAUDE 사후 검토는 **GO / 남은 필수 수정 0건**이다. 검토자는 Python 3.10 VM에서 pytest를 재실행하지 않았고 코드·diff·보호 파일을 직접 확인했다. I-1 구현은 완료 상태이며 커밋되지 않은 채 보존한다.

검토된 다음 단계에 따라 I-2를 독립 변경으로 진행했다. 실제 설정 변경은 두 줄이다:

- `pyproject.toml`: 기본 `testpaths`에 `calibration/tests` 추가.
- `.github/workflows/ci.yml`: BVT job 명령을 `pytest tests/ calibration/tests/ -v --tb=short`로 변경. forecast job과 lint는 유지.

| 게이트 | 결과 |
|---|---|
| 기본 pytest 수집 | 변경 전 **1,479/1,480**, 변경 후 **1,513/1,514** (각각 network 1건 deselect) → 정확히 **+34** |
| BVT CI 범위 수집 | `tests/` **1,111** → `tests/ calibration/tests/` **1,145** → 정확히 **+34** |
| 기본 `python -m pytest -q --tb=short` | **1,510 passed / 3 skipped / 1 deselected / 1 warning**, 33.14초 |
| import file mismatch | 없음; 두 수집 명령 모두 exit 0 |
| TOML/YAML 파싱 및 CI 명령 확인 | 통과 |
| 파일 무결성 | pyproject 94줄 / CI 52줄, 각 파일 전체 CRLF 유지, NUL 0 |
| diff | 두 설정 파일 각 1줄 변경. 기존 I-1 변경 및 사용자 CLAUDE.md +2줄 보존 |

기존 skip 3건(Windows symlink 권한, process-group 미지원, EDGAR 캐시 부재)과 gotrue 경고는 동일하다. 검증용 일회성 스크립트에서 이름 없는 CI step을 직접 인덱싱해 KeyError가 발생했으나, `.get('name')`으로 검증 스크립트만 수정 후 파싱·명령 검사를 통과했다. 제품/테스트 실행 실패는 아니다.

위 결과는 로컬 Python 3.14 결과다. 원격 Linux/Python 3.11 CI 실행이나 커밋·PR은 수행하지 않았다. I-3 이후는 미착수다.

CLAUDE I-2 사후 검토용:

```text
@PLAN_project_improvements_2026-09-07.md
@pyproject.toml
@.github/workflows/ci.yml

§12의 I-2 변경을 읽기 전용으로 검토해줘.
허용 diff는 testpaths에 calibration/tests 추가 및 BVT CI pytest 경로에 calibration/tests/ 추가, 두 줄이야.
기존 I-1 테스트 파일 diff와 사용자 CLAUDE.md +2줄은 이번 변경에서 제외해줘.
기본 수집 +34, CI BVT 수집 +34, import mismatch 없음, forecast/lint 경로 유지 여부를 확인하고 GO 또는 필수 수정사항을 회신해줘.
파일 수정·커밋·I-3 구현은 하지 마.
```

## 13. I-2 사후 GO 및 I-3 결정 대기

사용자가 전달한 CLAUDE I-2 사후 검토는 **GO / 남은 필수 수정 0건**이다. 검토자는 diff 두 줄, forecast/lint/addopts 불변, CI 의존성 충족, 패키지 경로에 의한 테스트 basename 구분, 수집 수 정합과 파일 무결성을 확인했다. Python 3.10 VM에서 pytest를 재실행하지는 않았다.

I-1과 I-2는 구현 및 교차 검토 완료 상태다. 별도 커밋 분리 권고를 기록하되 커밋·PR은 아직 수행하지 않았다. untracked 계획서의 커밋 여부도 확정하지 않았다.

I-3는 설치 계약 선택 전에는 구현하지 않는다. 권고 범위는 checkout/editable 지원을 명시하고 패키지 include에 backtest/calibration, exclude에 calibration.tests를 추가하는 것이다. wheel 독립 설치 지원을 선택하면 프로필 리소스 포함·탐색·출력 경로 및 저장소 밖 설치 검증까지 별도 계획으로 확장해야 한다. 사용자 선택을 받은 뒤 구체적 변경 파일과 완료 기준을 확정한다.

## 14. I-3 사용자 승인 및 실행 기록

사용자가 checkout/editable 권고 범위에 **“응. 진행.”**으로 승인했다. wheel 독립 설치 지원은 이번 범위에서 제외한다. §7 순서 3의 기존 wheel 검증 제안은 아래 editable 검증 계약으로 대체한다.

변경 범위:

- `pyproject.toml`: include에 `backtest*`, `calibration*` 추가; exclude에 `calibration.tests*` 추가. 기존 `forecast.tests*` 제외와 I-2 testpaths는 유지한다.
- `README.md` Quick Start: checkout 유지, editable 설치, repository root에서 명령 실행, checkout 없는 standalone wheel 설치 미지원 명시(5줄 추가).
- 본 계획서에 승인 및 검증 기록. 프로젝트 AGENTS에는 같은 내용을 중복 추가하지 않고 README를 설치 계약의 기준으로 둔다.

완료 검증:

| 게이트 | 결과 |
|---|---|
| 패키지 탐색 기준선 | 변경 전 backtest=False / calibration=False |
| 변경 후 일반 및 namespace-aware setuptools 탐색 | 두 패키지 포함 / forecast.tests 및 calibration.tests 제외 모두 PASS |
| checkout에서 backtest.dataset/backtest.report/calibration.report import | PASS |
| 임시 가상환경 editable 설치 | `venv --system-site-packages` 후 `pip install --no-deps --no-build-isolation --no-index -e <repo>` exit 0 |
| 저장소 밖 임시 cwd에서 설치 확인 | distribution direct_url의 editable=true 및 원본 checkout 경로 확인, backtest/calibration import PASS |
| 전체 `python -m pytest -q --tb=short` | **1,510 passed / 3 skipped / 1 deselected / 1 warning**, 32.66초 |
| 파일 무결성 | pyproject CRLF 94/94, README CRLF 213/213, NUL 0; diff whitespace 검사 통과 |

임시 가상환경은 검증 후 정리했다. 네트워크·운영 DB·유료 API는 사용하지 않았다. 설치 smoke는 기존 환경의 의존성을 공유했으므로 새로운 PC에서의 의존성 전체 설치 검증은 아니다. standalone wheel·원격 CI는 실행하지 않았다. 기존 skip/경고 사유는 §12와 같다. I-4 이후 및 커밋·PR은 미착수다.

CLAUDE I-3 사후 검토용:

```text
@PLAN_project_improvements_2026-09-07.md
@pyproject.toml
@README.md

사용자가 승인한 checkout/editable 범위의 I-3를 읽기 전용으로 검토해줘.
§14의 include backtest*/calibration*, exclude calibration.tests*, README 설치 계약만 이번 변경이야.
pyproject testpaths와 CI 변경은 I-2, allowlist 테스트 파일은 I-1, CLAUDE.md +2는 사용자 기존 변경이므로 분리해줘.
패키지 포함/제외, 기존 설치 명령과 문서의 정합, editable smoke 검증의 범위와 한계를 확인하고 GO 또는 필수 수정사항을 회신해줘.
파일 수정·커밋·I-4 구현은 하지 마.
```

## 15. I-3 사후 GO 및 I-4 제안

2026-09-07 사용자가 전달한 CLAUDE 사후 검토: **GO / 남은 필수 수정 0건**. 검토자는 작업 폴더의 diff, 패키지 목록, import 그래프, 문서 정합 및 파일 무결성을 읽기 전용으로 확인했다. 검토 VM(Python 3.10)에서 setuptools 탐색이나 pytest를 재실행하지 않았다.

검증 해석 보완: flat-layout editable 설치는 저장소 루트를 .pth로 노출할 수 있어 include 누락 상태에서도 import가 성공할 수 있다. 따라서 패키지 포함 회귀 검사의 기준은 import 성공이 아니라 §14의 setuptools 일반/namespace-aware 탐색 결과(before=False → after=True 및 tests 제외)다. editable import smoke는 설치 연결 확인을 보조한다.

I-1·I-2·I-3는 구현 및 사후 검토 완료, 커밋되지 않은 상태다. 권고 커밋 분리는 I-1 테스트 파일 / I-2 testpaths+CI / I-3 include·exclude+README이며, 공유 파일 pyproject.toml은 hunk 단위 분리가 필요하다. 커밋·PR은 수행하지 않았다.

I-4 제안 범위(구현 승인 전): TODO.md 신규 작성, README.md의 검증 가능한 구조·방법 설명 정합, 본 계획서 진행 기록. TODO에는 §5에서 확인한 완료 항목과 I-1~I-3를 근거 파일·커밋 또는 미커밋 상태와 함께 기록하고, I-4~I-7 및 미검증 운영 항목을 분리한다. README의 engine 파일 수는 git ls-files 기준 32개(__init__.py 포함)이며 현재 19 modules 표기는 오래되었다. rNPV 누락 및 다른 수치 주장은 코드와 추적 파일 기준을 확인한 뒤 교정한다. AGENTS.md와 사용자 CLAUDE.md 변경은 이번 제안에 포함하지 않는다.

완료 기준: 코드 변경 0, 문서 주장마다 근거 확인, 완료/미완료/정책 대기 구분, 기존 변경 보존, Markdown 링크·diff·인코딩 무결성 확인. 문서 전용 변경이므로 제품 테스트 재실행 대신 문서 검증을 수행한다. I-4 구현은 사용자 승인 후 진행한다.

## 16. I-4 사용자 승인 및 실행 기록

사용자가 §15의 문서 3개 범위에 “응. 진행.”으로 승인했다. TODO.md를 신규 작성하고 README.md 및 본 계획서만 변경했다. I-5 구현, 커밋·PR은 수행하지 않았다.

- TODO: I-1~I-3 사후 GO·미커밋 상태, §5의 완료 항목과 코드·커밋 근거, I-4 검토 대기, I-5~I-6 미완료, I-7 정책 및 운영 검증 대기를 분리했다. 패키지 회귀 검사는 import 성공보다 setuptools 탐색 결과를 기준으로 삼는다는 권고를 기록했다.
- README: 방법 수 6→7 및 rNPV 행·dispatch·선택 설명을 교정했다. engine/pipeline/ai/backtest는 git ls-files 기준 각각 32/21/6/7 Python 파일(__init__.py 포함)로 표기하고 목록은 발췌임을 명시했다. 근거는 해당 디렉터리, engine/method_selector.py, valuation_runner.py, engine/rnpv.py다.
- README: 범위가 불분명한 상단 LOC·테스트 통계를 제거하고 추적 root YAML 48개로 표기했다. 테스트 설명은 추적 test_*.py의 AST 내 test_ 함수 정의 수로 재측정했다: tests 49파일/1,071함수, forecast/tests 54/348, calibration/tests 3/34. 실행 건수와 구분하고 기본 실행 명령을 pyproject.toml의 세 스위트 수집과 맞췄다. 기존 1,070 합계의 상세 표는 제거했다. 최신 제품 실행 결과는 §14 기록으로 명시했으며 이번에 재실행한 것으로 표현하지 않았다.
- D10 상태 차이: SPEC §13은 P-1을 36ca806으로 완료 표기하지만 §11에서 현재 파일의 split 기반 결함을 재현했다. TODO에 현재 I-1 수정은 GO·미커밋임을 적고, I-6 재개 시 전제조건을 최신 코드와 다시 대조하도록 했다. 명세 자체는 수정하지 않았다.

검증: 작업 전 SHA-256 기준선과 대조해 대상 외 추적 파일 **869개 전부 불변**. 기존 I-1/I-2/I-3 코드·설정 변경과 사용자 CLAUDE.md 변경도 보존됐다. 문서 3개의 UTF-8 디코딩, NUL 0, replacement character 부재, fenced code block 짝, 상대 Markdown 링크 대상 존재를 확인했다. README는 전체 CRLF를 유지했고 TODO는 LF로 작성했다. 계획서의 기존 혼합 줄바꿈은 전체 정규화하지 않았다. README git diff --check 통과. 문서 전용 변경으로 제품 테스트·lint·빌드는 재실행하지 않았다. 원격 CI·네트워크·유료 API·운영 DB 호출 없음.

CLAUDE I-4 사후 검토용:

```text
@PLAN_project_improvements_2026-09-07.md
@TODO.md
@README.md

§16의 I-4 문서 정리를 읽기 전용으로 검토해줘.
이번 범위는 TODO 신규, README 구조·방법·테스트 설명 정합, 계획서 상태와 실행 기록이야.
README Quick Start의 checkout/editable 5줄은 I-3이고, 기존 테스트·설정 diff와 CLAUDE.md +2줄은 이번 변경이 아니야.
코드 변경 0, 각 주장에 근거 파일·커밋 또는 측정 범위가 있는지, 완료/미완료/정책 대기 구분과 D10 P-1 상태 차이 기록을 확인해줘.
GO 또는 필수 수정사항을 회신해줘. 파일 수정·커밋·I-5 구현은 하지 마.
```

## 17. I-4 CONDITIONAL GO 필수 교정 완료

2026-09-08 사용자 전달 교정 확인 회신: **GO — I-4 확정**. 아래 교정 당시 기록 이후 별도 재검토 GO가 도착했다.

2026-09-07 사용자의 CLAUDE 회신은 CONDITIONAL GO, 필수 1건이다. README의 section 기호가 ASCII 물음표로 손실된 점을 확인했다. 기존 U+FFFD 부재 검사는 이 손실을 잡지 못했다. 발생 경로의 정확한 인코딩은 별도로 입증하지 않았으며 cp949를 확정 원인으로 단정하지 않는다.

README의 `) ?14 for environment`를 바이트 단위로 `) section 14 for environment`로 교체했다. 그 치환 외 README 바이트 불변을 검증했고 전체 ASCII 물음표 바이트는 0개다. `section 14`의 실제 바이트는 `73 65 63 74 69 6f 6e 20 31 34`이다. 향후 문서 교정 검증은 UTF-8/NUL/U+FFFD 검사에 더해 의도한 문구의 바이트 일치와 새 ASCII 물음표 유입을 확인한다. 정상 문장부호인 물음표까지 일반적으로 금지하는 규칙은 아니다.

TODO에 커밋 전 링크 의존성 추적 범위를 사용자 결정으로 남겼다. README가 참조하는 TODO·PLAN과 TODO가 참조하는 미추적 자료를 어디까지 함께 추적할지, 로컬 참조를 코드 표기로 바꿀지 미정이다. 로컬 링크 존재 검사와 원격 checkout에서의 링크 유효성을 구분한다. 임의 stage·커밋은 수행하지 않았다.

사용자가 한 글자 교정 후 I-4 확정 가능하다고 전달한 조건을 충족했다. 별도 재검토 GO를 받은 것으로 표기하지 않는다. 다음 단계는 I-5 forecast Ruff 부채 측정이며 측정 전 CI 차단 범위를 확정하지 않는다. 이번 회신 반영에서는 I-5를 실행하지 않았다.

## 18. I-5 읽기 전용 부채 측정 (2026-09-08)

후속 상태: 사용자 조건부 (b) 범위를 §19에서 구현했다. **차단 규칙 4계열 E9/F63/F7/F82 / 잔여 lint 부채 215건·format 99파일은 미차단**이다. 아래는 교정 전 기준선이다.

기준 HEAD 6634c1f, I-1~I-4 미커밋 작업 트리, 로컬 Ruff 0.15.8. PATH에서 ruff를 찾지 못해 동일 패키지의 `python -m ruff`로 실행했다. forecast cwd에서 `check . --statistics`와 `format --check .`는 각각 exit 1(위반 발견)이다. --fix/format 쓰기 실행은 하지 않았다.

| 규칙 | 위반 건수 | 해당 파일 수 |
|---|---:|---:|
| E702 | 56 | 4 |
| I001 | 44 | 42 |
| E741 | 22 | 15 |
| E401 | 17 | 17 |
| F401 | 17 | 7 |
| B905 | 13 | 12 |
| F541 | 13 | 5 |
| F841 | 9 | 5 |
| UP037 | 9 | 2 |
| B007 | 4 | 2 |
| F821 | 4 | 1 |
| E701 | 3 | 2 |
| E731 | 3 | 1 |
| E402 | 1 | 1 |
| UP012 | 1 | 1 |
| UP015 | 1 | 1 |
| UP017 | 1 | 1 |
| UP035 | 1 | 1 |

lint 합계 **219건 / 중복 제거 61파일**. JSON 결과와 git ls-files 대조에서 미추적 파일의 진단은 0건이다. Ruff는 104건을 기본 fix 가능, 추가 25건을 unsafe fix 가능으로 표시했다(실행하지 않음). 나머지 90건은 이 fix 표시 밖이다. fix 가능 표시가 의미 보존을 검증했다는 뜻은 아니다.

format: **99파일 변경 필요 / 43파일 이미 정렬**, 총 Python 142파일. lint/format 영향 파일 합집합은 **106개**. show-files의 143개는 Python 142개와 TOML 1개다. 전체 정리 비용은 이 파일 범위를 기준으로 판단해야 하며 자동 수정 후 잔여 위반 수는 아직 측정하지 않았다.

설정 적용 실험:

- 루트 `python -m ruff check . --show-files`: 203개, forecast 경로 0개. 루트 exclude가 하위 탐색을 막는다. 이 총수에는 로컬 작업 자료가 포함될 수 있어 CI 파일 수로 해석하지 않는다.
- forecast cwd의 동일 명령: 143개. `check cli.py --show-settings`는 forecast/pyproject.toml, target py311, line-length 100을 표시했다.
- 루트에서 파일을 명시한 `check forecast/cli.py --show-settings`도 같은 forecast 설정을 사용하며 B905/E702가 활성화된다. 루트 E402/E702 ignore가 병합되지 않는다.
- 충돌이 아니라 탐색 범위와 파일별 설정 선택의 차이다. forecast job에서 working-directory를 forecast로 두고 검사하면 독립 설정으로 실행 가능하다. 공식 근거: https://docs.astral.sh/ruff/configuration/ (가장 가까운 설정 선택, 부모 설정 자동 병합 없음, 명시 파일과 exclude 동작).
- requirements-lock.txt는 0.15.8이지만 forecast job은 현재 `.[dev,forecast]`만 설치하며 dev 범위는 ruff>=0.4,<1이다. 어떤 방식을 택하든 재현 가능한 CI 기준선을 위해 Ruff 버전 고정 범위도 구현안에 포함해야 한다.

최소 규칙 후보를 실제 실행: forecast cwd `python -m ruff check . --select E9,F63,F7,F82 --statistics` → exit 1, **F821 4건/1파일**. forecast/cli.py:591,599의 인자·반환 annotation에 쓰인 QuarterlyActual 이름이며 import는 다른 함수 내부(146행)에 있다. 이번 측정은 실제 실행 장애를 재현한 것이 아니다. 타입 이름 해석을 확인하는 수정·검증이 필요하며 코드에는 손대지 않았다.

선택지와 예상 비용(파일 범위 기준, 소요시간 보장 아님):

| 선택 | 구현·검토 비용 | 보호 범위와 한계 |
|---|---|---|
| (a) 신규 위반만 차단 | 중간: base/head Ruff JSON 비교 로직·테스트·CI·동일 버전 실행 및 비교 기준 설계. 코드 부채는 유지 가능. | 줄 이동, 삭제, 규칙 버전 변화, base ref 확보를 처리해야 함. 단순 총건수 비교는 기존 위반 감소가 새 위반을 가릴 수 있음. formatter의 기존 부채도 별도 비교 설계 필요. |
| (b) 부분 규칙 차단 — 권고 | 낮음: 후보 E9/F63/F7/F82, 현재 annotation F821 4건이 있는 cli.py 1파일 원인 교정·검증 + CI 연결·Ruff 버전 고정. 전체 format 게이트는 보류. | 구문/일부 명확한 오류 계열부터 차단. 나머지 lint 및 format 부채는 남는다. F821를 조용히 ignore하는 제안이 아님. |
| (c) 전량 정리 후 차단 | 높음: 현 lint/format 합집합 106파일, lint 219건 및 format 99파일의 diff 검토·전체 테스트·FROZEN 게이트. | 현재 규칙과 format 전체 차단 가능. 기계적 format과 의미에 영향 있는 교정은 분리해야 함. |

`ruff check --diff`는 수정 예정 diff를 출력하는 옵션으로, Git 기준 신규 위반만 비교하는 기능이 아니다(로컬 --help 및 공식 configuration 문서 확인). (a)를 선택한다면 별도의 baseline 비교가 필요하다.

측정용 JSON 캡처 첫 시도는 subprocess의 기본 cp949 디코딩으로 실패했다. 제품 실패가 아니며 `encoding='utf-8'` 명시 후 동일 읽기 전용 측정을 완료했다. 향후 캡처에도 인코딩을 명시한다. 측정 중 제품 테스트는 실행하지 않았다. TODO와 본 계획서에만 결과를 기록했으며 CI·코드 수정과 커밋·stage는 하지 않았다. 사용자 선택 전 (a)/(b)/(c) 구현은 시작하지 않는다.

## 19. I-5 (b) 부분 규칙 차단 실행 기록

2026-09-08 사용자가 전달한 (b) 동의 및 구현 조건을 적용했다. 제품·설정 변경은 forecast/cli.py와 .github/workflows/ci.yml 두 파일이며 TODO·본 계획서에 결과를 기록했다.

- forecast/cli.py: `from typing import TYPE_CHECKING`과 조건부 QuarterlyActual import만 4줄 추가. 기존 함수 내부 import와 annotation은 보존했다. Git 추적 Python 파일 전체에서 get_type_hints 문자열 검색 결과 0건이며, `python -c "import forecast.cli"`는 통과했다. 동적·외부 호출까지 부재를 증명하는 검사는 아니다.
- CI forecast-test job: 의존성 설치 다음에 `pip install ruff==0.15.8` 추가. requirements-lock.txt의 Ruff 핀과 일치함을 검증했다. lock 버전 변경 시 이 명시 핀도 함께 갱신해야 한다. 이어 working-directory: forecast, `ruff check . --select E9,F63,F7,F82` step 추가. 기존 BVT job은 수정하지 않았다(I-2의 calibration 경로 diff는 그대로 보존).
- 전체 format, I001/F401 등의 규칙 확대, autofix는 하지 않았다. **차단 규칙 4계열 / 잔여 lint 215건·format 99파일 미차단**이며, 전체 lint CI 완료를 뜻하지 않는다.

| 검증 | 결과 |
|---|---|
| forecast cwd 선택 규칙 | exit 0, All checks passed |
| forecast 전체 lint | exit 1, 219→215건; F821 4건만 감소, 나머지 17규칙 건수 불변 |
| format 읽기 전용 재측정 | 99파일 변경 필요 / 43파일 유지, 기준선 동일 |
| forecast CLI import | exit 0 |
| 전체 기본 pytest | 권한 재실행 후 **1,510 passed / 3 skipped / 1 deselected / 1 warning**, 36.01초 |
| FROZEN 별도 게이트 | 2 tests passed; 지원 4/4 PASS, 지원 SKIP 0. 구 규약 비대상 보고서 5건 SKIP |
| ast.parse / CI YAML / Ruff 핀 | 통과. lock의 0.15.8과 CI 명시 핀 일치 |
| 파일 무결성 | cli.py LF 609→613 / CRLF 0 유지; CI CRLF 52→59 전체 유지; NUL 0, diff --check 통과 |
| 변경 범위 | 문서 기록 전 추적 파일 SHA-256 대조: cli.py·CI 두 파일만 변경. 이전 사용자 변경 및 I-1~I-4 보존 |

테스트 실행 환경 문제: 최초 샌드박스 실행은 tmp_path setup의 PermissionError로 147 errors, 1,364 passed / 2 skipped / 1 deselected / 3 warnings였다. 동일 명령을 권한 승인 경로로 샌드박스 밖에서 재실행해 위 전체 통과를 확인했다. 제품 수정으로 실패를 우회하지 않았다. 별도 FROZEN 실행은 pytest cache 디렉터리 생성 경고 1건이 있었지만 게이트는 통과했다. 최종 전체 테스트의 경고 1건은 기존 gotrue deprecation이며 skip 3건은 Windows symlink 권한·process-group 미지원·EDGAR 캐시 부재다.

로컬 Python 3.14 결과이며 원격 Linux/Python 3.11 CI는 실행하지 않았다. 커밋·stage·유료 API·운영 DB 작업은 수행하지 않았다.

CLAUDE I-5 사후 검토용:

```text
@PLAN_project_improvements_2026-09-07.md
@forecast/cli.py
@.github/workflows/ci.yml
@TODO.md

§19의 I-5 (b)를 읽기 전용으로 검토해줘.
허용 제품 diff는 cli.py의 TYPE_CHECKING import 4줄과 forecast job의 Ruff 0.15.8 설치 및 E9/F63/F7/F82 검사 step이야.
함수 내부 QuarterlyActual import 유지, get_type_hints 검색 범위, lock 버전 정합, working-directory, 기존 BVT job 보존을 확인해줘.
전체 lint는 215건과 format 99파일이 계속 미차단이야. 전체 테스트 1510 passed와 FROZEN 지원 4/4는 로컬 검증이며 원격 CI 결과가 아니야.
기존 I-1~I-4와 사용자 CLAUDE.md diff를 분리하고 GO 또는 필수 수정사항을 회신해줘.
파일 수정·커밋·규칙 확대·autofix는 하지 마.
```

## 20. I-5 최종 GO 및 커밋 결정 대기

2026-09-08 사용자 전달 CLAUDE 사후 검토: **GO / 남은 필수 수정 0건**. 검토 VM(Python 3.10)에서 pytest·Ruff를 재실행하지 않았으며 diff·설정·import 구조·무결성을 직접 확인했다. I-1~I-5 구현 및 교차검토 완료, 전부 미커밋이다.

권고 반영: TODO에 lock/CI Ruff 핀 동시 갱신과 첫 원격 Python 3.11 CI 로그 확인을 기록했다. 미래 CI 실패를 환경 문제라고 미리 단정하지 않는다.

승인 요청할 커밋안: ① I-1 allowlist 테스트 ② I-2 pyproject testpaths + BVT CI hunk ③ I-3 pyproject include/exclude + README Quick Start 5줄 ④ I-4 README 나머지 + TODO + 본 계획서 ⑤ I-5 forecast CLI + forecast CI hunk. 공유 파일은 hunk 단위로 분리하며 기존 CLAUDE.md 및 관련 없는 자료는 포함하지 않는다.

문서 추적 권고는 TODO+본 계획서를 포함하고, TODO가 참조하는 그 밖의 미추적 자료는 파일명 코드 표기로 바꾸는 최소안이다. 실제 Git 추적 여부를 커밋 직전에 확인하여 이미 추적된 링크는 유지한다. 사용자 결정 전 링크 변환·stage·커밋은 하지 않는다. 승인 후 5개 커밋 범위와 HEAD~5..HEAD의 CRLF 무시 diff/stat, 추적 대상만으로 상대 링크가 해소되는지를 검증한다. push·PR은 별도 요청 없이 수행하지 않는다.

### 승인 후 커밋 진행

사용자가 5개 conventional commit, 작업 브랜치→PR, TODO·PLAN 추적과 미추적 참조 코드 표기를 승인했다. core.autocrlf=true를 확인했다. PLAN을 LF로 정규화하고 키·토큰 패턴 및 비밀값 환경변수 할당 형태를 검사해 일치 0건을 확인했다(패턴 검사가 모든 비밀값 부재를 증명하는 것은 아니다). TODO는 실제 Git 추적 여부 기준으로 미추적 7개 파일·8개 링크를 코드 표기로 바꿨다. 이미 추적된 링크와 README→TODO/PLAN은 유지한다.

브랜치 chore/verified-quality-gates를 검증 기준 6634c1f에서 생성했다. 호스트에서 git add -p로 hunk 분리 후 각 staged stat을 CR 무시 유무 양쪽으로 비교했다. I-1 87d69c3(112+/8-), I-2 86b0a6e(2+/2-), I-3 8e4935a(7+/2-) 완료. 사용자 CLAUDE.md는 stage하지 않았다.

원격 확인 시 main은 552453c이며 선행 6634c1f는 main 미포함·기존 PR 없음이었다. 기존 fix/mc-negative-dlom을 base로 하는 PR과 main에 선행 커밋까지 포함하는 PR 중 사용자에게 확인을 요청했다. PR 생성·CI 결과는 확인 후 이 절에 기록한다.