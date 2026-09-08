# Project backlog

기준: 2026-09-08, PR #28의 검증 head `7f676bf`. 과거 인수인계는 이력으로 보존하며, 아래 항목을 재개할 때 최신 코드와 Git 이력을 다시 대조한다. 검토·검증 상세는 [개선 계획서](PLAN_project_improvements_2026-09-07.md)에 기록한다.

## 완료

| 항목 | 근거와 완료 범위 |
|---|---|
| I-1 FROZEN 파일명 해석 보호 | [테스트 및 검사 함수](forecast/tests/test_valuation_allowlist.py): 명시 매핑 우선, 비규약 이름은 UNRESOLVED. 계획서 §11~12 구현·검증 및 사후 GO. PR #28, `87d69c3`. |
| I-2 calibration 기본 검증 편입 | [pytest 설정](pyproject.toml), [CI](.github/workflows/ci.yml): 기본 수집과 BVT CI에 calibration 포함. 계획서 §12~13 수집 +34 및 사후 GO. PR #28, `86b0a6e`. |
| I-3 checkout/editable 설치 계약 | [패키지 설정](pyproject.toml), [README](README.md): backtest/calibration 포함, calibration.tests 제외. 계획서 §14~15 탐색 검증 및 사후 GO. PR #28, `8e4935a`. |
| 자동 분석 DB 저장 호출 연결 | [profile_generator.py](pipeline/profile_generator.py)의 두 `_save_to_db` 호출 확인. 호출 연결은 존재하며 운영 DB 스키마 적용·실제 저장 성공은 별도 확인 대상. |
| 시나리오 차별화 검사 | [scenario_validator.py](engine/scenario_validator.py)의 `validate_scenario_differentiation` 및 [profile_generator.py](pipeline/profile_generator.py)의 호출 확인. 재구현 대상 아님. |
| 변동 프로필에서 테스트 fixture 분리 | `2203856`, [msft_frozen.yaml](tests/fixtures/msft_frozen.yaml), [tsla_frozen.yaml](tests/fixtures/tsla_frozen.yaml). 기존 round-trip 테스트에 대한 완료이며 모든 프로필 사용 테스트의 포괄 감사는 아님. |
| 탄력도 비양수 base EV/equity 거부 | `1de124a`, [eps_elasticity.py](engine/eps_elasticity.py). 시나리오 가치를 0원으로 하한 처리하는 정책과 구분. |
| MC 음수 equity의 DLOM 제외 | `6634c1f`, [monte_carlo.py](engine/monte_carlo.py). 음수 equity 자체는 보존. |
| D10 rev-8 명세 검토 종결 | `REPLY_CODEX_d10a_spec_review_r8.md`, `SPEC_d10a_batch_runner.md`. 명세 종결이며 배치 구현 완료를 의미하지 않음. |

패키지 포함 회귀 검사는 setuptools 일반/namespace-aware **탐색 결과**와 테스트 패키지 제외를 기준으로 삼는다. Flat-layout editable import는 저장소 루트 노출 때문에 include 누락 상태에서도 성공할 수 있다. I-3 smoke는 기존 의존성을 공유했으며 신규 PC의 의존성 해석이나 standalone wheel 지원을 검증하지 않았다(계획서 §14~15).

## I-4 사후 검토 반영 완료

- [x] I-4 문서 정합: PR #28, `543fe3a`. 본 TODO 작성, README의 방법·파일·테스트 수와 실행 범위 교정. 검증 결과와 검토용 프롬프트는 계획서 §16 참조.
- [x] I-4 CLAUDE 읽기 전용 사후 검토: 필수 교정 후 2026-09-08 사용자 전달 최종 GO로 확정. 코드 변경 0, 근거 대조 통과. 계획서 §17 참조.

## 미완료

| 항목 | 다음 작업과 완료 기준 | 근거 |
|---|---|---|
| I-1~I-5 PR 병합 | PR #27 병합 완료. PR #28의 기존 5개 커밋 분리와 두 CI job 성공을 확인했다. 사용자 승인으로 문서 기록 커밋 1개를 추가하며, 새 head의 CI 재실행 통과 후 merge commit으로 병합한다. | 계획서 §20 |
| I-4 링크 의존성 | 사용자 승인: TODO·PLAN 추적, 그 밖의 미추적 참조는 파일명 코드 표기. 실제 7개 파일·8개 링크를 변환했다. 추적 대상만으로 링크 해소되는지 커밋 검증에 포함. | README·본 문서의 상대 링크, 계획서 §20 |
| I-5 잔여 부채 | 부분 차단은 PR #28, `7f676bf`. 로컬 전체 1,510 passed, FROZEN 지원 4/4 및 Ubuntu/Python 3.11 CI 두 job 성공. 잔여 lint 215건·format 99파일은 미차단이며 기계적 정리는 별도 PR 범위. | [CI](.github/workflows/ci.yml), [forecast CLI](forecast/cli.py), 계획서 §19~20 |
| I-6 D10 다종목 측정 | §13의 P-1~P-6을 최신 코드·커밋으로 재검증한 후 §15의 offline 구현 범위를 확정. provenance, 입력 SHA, tax_rate_basis, 실패 계약과 기준선 보호. | `SPEC_d10a_batch_runner.md`, `HANDOFF_CODEX_d10p1_v1_derivation_2026-08-30.md` |

D10 P-1 상태는 문서 간 차이가 있다. 명세 §13은 `36ca806`으로 완료 표기하지만, I-1 조사에서는 기존 `split('_')[0]` 결함을 재현하고 수정했다(PR #28, `87d69c3`). 과거 완료 표기만으로 전제조건 전체를 통과 처리하지 않는다(계획서 §6·§11).

## 정책 대기 · 운영 상태 미검증

| 항목 | 필요한 확인 또는 결정 | 근거 |
|---|---|---|
| I-7 R10 음수 equity / NCI | raw equity·투자자 payoff·표시값·가중값·MC 통계 계약, 기업별 EV 비례 NCI 적용 범위와 비양수 Base EV 처리 결정. 과거 수동 교정 가격을 회귀 기대값으로 채택하지 않음. | `NEXT_SESSION_sk_ecoplant_r10_carryover.md`, [현행 규칙](AGENTS.md), 계획서 §8 |
| 운영 DB 저장·migration | 코드 연결과 별도로 운영 스키마 및 실제 저장 결과 확인. 이번 작업에서 DB 접속하지 않음. | [DB migration](db/migrations_backtest.sql), [저장 코드](db/backtest_repository.py), 계획서 §5 |
| KR 순차입금 데이터 | 현재 프로필의 기준연도·provenance를 같은 시점 원천과 대조해 대상부터 확정. 과거 snapshot만으로 현재 오염 판정 금지. | `NEXT_SESSION_kr_netcash_contamination.md`, 계획서 §5·§8 |
| LLM 운영 잔여 검증 | ChromeDriver·주간 fallback·프로필 복구·유료 측정 처분을 최신 상태로 재검증. 과거 날짜의 실행 지시를 그대로 반복하지 않음. | `NEXT_SESSION_llm_ops_wrapup.md` |
| 하우스키핑·연구 프로필 처분 | 기존 dirty/untracked 자료의 소유·결정을 재확인. 이번 작업에서 삭제·이동·일괄 stage하지 않음. | `NEXT_SESSION_housekeeping_phase2b.md`, 계획서 §9 |

## 다음 세션

I-1~I-5 구현·교차검토 완료. 승인된 커밋·PR 진행 상태는 계획서 §20을 기준으로 확인한다. 전체 lint/format 정리 완료로 해석하지 않는다. standalone wheel 설치, 유료 API, 운영 DB 검증은 수행하지 않았다. 제품 테스트의 로컬 결과는 계획서 §19에 있다.

Ruff 업그레이드 시 requirements-lock.txt와 CI forecast job의 명시 핀을 함께 갱신한다. 핀 추출 자동화는 이번 범위 밖이다.
