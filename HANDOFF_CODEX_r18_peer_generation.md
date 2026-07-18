# HANDOFF — R18: 자동 프로필 peer 생성 실패

**상태:** 등록됨 — R16 완료 후 다음 트랙
**범위:** R16 배포 차단/overwrite 보호와 분리

## 문제

R16 실측에서 유효 프로필 45개 중 33개가 text와 무관하게 이미 draft였고, 지배적 blocker는 `dcf_vs_peer`의 peer median 부재다. 자동 초안은 `peers: []`로 시작하며 `recommend_peers_batch()`가 존재함에도 최종 프로필에 peer가 남지 않는 경로가 있다.

R16은 나쁜 결과의 외부 배포를 막는다. R18은 자동 파이프라인이 investable 후보를 만들 수 있도록 peer 생성·검증·지속 경로를 복구한다. 두 변경을 한 작업에 섞지 않는다.

## 다음 세션 조사 항목

1. `recommend_peers_batch()` 성공, per-segment fallback, quota skip, validator 제거를 각각 계측한다.
2. `peers_all`이 비는 모든 분기와 YAML persistence 전후를 테스트한다.
3. peer가 없으면 `draft: true` 유지 + 구체적 blocker를 기록한다.
4. 유효 peer 최소 수와 segment coverage acceptance criteria를 확정한다.
5. 주간 실측에서 `draft_blocked` 비율과 peer 실패 원인을 보고한다.

**백테스트 영향:** 현재 backtest는 quality/grade를 소비하지 않으므로 R16의 F/0 전환이 기존 backtest 결과를 오염시키지는 않는다.
