# Business Valuation Tool: 다음 세션

## 현재 상태 (2026-04-13 기준)
- 커밋: `ef75039` (main, origin 동기화 완료)
- 테스트: 576 pass / 2 fail (pre-existing `TestScenarioDriverRoundTrip`)
- 로고 삽입·US 파이프라인 실전 검증 완료 (04-13 run 성공)

---

## 세션 시작 프롬프트 (복사해서 사용)

---

[Business Valuation Tool] Phase 3 캘리브레이션 진입 전 테스트 정합성 복구

경로: `F:\dev\Portfolio\business-valuation-tool`
현재 상태: `ef75039`, 576 pass / 2 fail

## 배경
주간 파이프라인이 `profiles/msft.yaml`, `profiles/tsla.yaml`을 AI 생성 결과로 덮어쓰면서 시나리오 코드가 `Bull/Base/Bear`가 아닌 `A/B/C/D`로 바뀜. 반면 `tests/test_engine.py::TestScenarioDriverRoundTrip`의 2개 테스트는 `Bull/Base/Bear` 키를 하드코딩 → 주간 run 후마다 KeyError.

실패 테스트:
- `test_sotp_segment_multiples_differentiate_ev` (line 2340, msft.yaml)
- `test_yaml_segment_multiples_round_trip` (line 2419, msft.yaml)
- `test_dcf_growth_adj_differentiates_ev`는 tsla.yaml 기준 — 현재 pass 중이나 tsla.yaml이 재생성되면 동일 위험

관련 커밋: `57904bb chore(profiles): regenerate from 2026-04-13 pipeline run`

## 작업 1: 테스트 픽스처 분리 (primary)

**문제의 본질**: `profiles/`는 volatile(주간 AI 재생성). 테스트 고정 픽스처 아님.

**수정 방향 (선호 순)**:
1. `tests/fixtures/` 디렉토리 신설 → `msft_frozen.yaml`, `tsla_frozen.yaml` 복사본 고정 (Bull/Base/Bear 키로 수동 편집)
2. 3개 테스트가 `fixtures/` 경로를 로드하도록 수정
3. 주간 파이프라인이 `profiles/`만 덮어쓰도록 경계 유지 (이미 그럼)

**결정 포인트**: Bull/Base/Bear 하드코딩 vs. `list(vi.scenarios.values())` 상위 prob 3개로 유연화. 전자가 명시적이라 선호, 후자는 프로파일 무관 추상화. 시작 시 사용자에게 선택 확인.

## 작업 2: Phase 3 캘리브레이션 인프라 (secondary, 범위 확인 후 분리 세션 권장)

`memory/project_valuation_tool_audit.md` 참조. Phase 1-2 완료, Phase 3는 "캘리브레이션 인프라"로만 백로그 기록됨 — 구체 스펙 없음.

**먼저 해야 할 것**: Phase 3 요구사항 정의 (인터뷰 모드로 스펙 확정 → 별도 세션에서 구현). 이번 세션에서는 **작업 1만 완료 후 /clear** 권장.

## 완료 기준
- 576 pass → 578 pass (2건 복구) + 기존 passes 유지
- `profiles/msft.yaml` 재생성에 영향받지 않는지 확인 (픽스처가 `tests/fixtures/` 하위에 격리돼 있으면 구조적으로 보장)
- 커밋 + push

## 모드: normal
