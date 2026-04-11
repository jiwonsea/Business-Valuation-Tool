# Business Valuation Tool: 후속 작업 3건 (2026-04-11)

## 배경
rNPV quality scoring 개편 완료 (474/474 tests pass, 40 commits ahead of origin/main).
이번 세션에 이어서 아래 3건 순서대로 진행.

---

## 태스크 1 — NVO 실행 검증 + 시나리오 커버리지 추가

### 1a. NVO 실행해서 새 quality score 확인
```bash
python cli.py --profile profiles/nvo.yaml
```
- 예상: ~87/100 (A), 이전: 53/100 (D)
- 콘솔에 "교차검증 (rNPV 기준): ./25" breakdown 출력 확인
- `rnpv_weighted_cv`, `rnpv_pipeline_diversity`, `rnpv_pos_grounding` 세 항목 표시 확인

### 1b. 시나리오 커버리지 차원 추가 (소규모)
원래 태스크에서 누락된 항목: `pos_override` 사용 여부를 quality score에 반영.

현재 `rnpv_pos_grounding` (0-7)이 약물 수준의 PoS 커스텀을 측정하고,
`_scenario_consistency_score()` (0-25)가 시나리오 전반 품질을 측정하지만,
rNPV 특화 시나리오 품질(pos_override 사용 여부)은 별도로 없음.

**구현 방향** — `rnpv_pos_grounding` 버킷을 0-7에서 0-6으로 줄이고,
`rnpv_scenario_coverage` (0-1)를 추가해 cv_convergence 합계를 25 유지:
- `pos_override`가 1개 이상의 시나리오에 있으면: 1pt
- 없으면: 0pt + warning "시나리오 pos_override 없음 — 파이프라인 리스크 시나리오 미반영"

> **참고**: 합산이 25를 유지해야 하므로 점수 조정 필요.
> rnpv_weighted_cv (10) + rnpv_pipeline_diversity (8) + rnpv_pos_grounding (6) + rnpv_scenario_coverage (1) = 25

**수정 파일**: `engine/quality.py`, `schemas/models.py` (필드 추가), `tests/test_quality.py`

---

## 태스크 2 — Distress 엔진 Phase 2

`engine/distress.py` Phase 2 백로그:
1. **경기순환 산업 1년 적자 면제**: SIC/industry 코드 기준으로 cyclical 산업 판단 후, 1년 적자는 디폴트 트리거에서 제외
2. **35% → 25% 캡 하향 검토**: 현재 `distress_max_discount=0.35`. 실증 데이터 기반 적정 캡 재검토 — 우선 CLAUDE.md에 근거와 함께 기록
3. **세그먼트별 차등 할인**: 현재 모든 세그먼트에 동일 discount 적용. 부채가 특정 세그먼트에 집중된 경우 차등 적용 가능한지 설계

**참고 파일**: `engine/distress.py`, `tests/test_distress.py`

---

## 태스크 3 — origin/main push

40 commits ahead. push 전 체크리스트:
1. `pytest tests/ -q` → all pass 확인
2. `git log --oneline origin/main..HEAD` 로 커밋 목록 최종 확인
3. `git push origin main`

---

## 현재 상태
- 474/474 tests pass
- 40 commits ahead of origin/main
- 모드: normal
