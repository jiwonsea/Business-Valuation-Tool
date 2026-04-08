# Business Valuation Tool: 6-Model Cross Review P0 수정

## 배경
직전 세션(2026-04-09)에서 완료한 것:
- **OpenRouter 400 해결**: `anthropic/claude-haiku-4-5-20251001` → `anthropic/claude-haiku-4.5` 매핑 수정 + date suffix 자동 제거 + 에러 body 로깅
- **GOOGL DCF-SOTP 괴리 해결**: `capex_fade_to` 파라미터 추가 (DCFParams + engine/dcf.py + profile_generator.py 자동 감지). GOOGL -53.8% → -2.0%
- **6모델 Cross Review 완료**: Codex/Security/Finance/CodeReview/Python/TDD 병렬 리뷰 → P0 5건, P1 10건, P2 12건 도출
- 395/395 테스트 통과
- 미커밋 상태 (OpenRouter + capex_fade_to + 리뷰 리포트)

## 이번 세션 작업: P0 수정 (5건, 결과 정확도 직접 영향)

### P0-1. Mixed-method SOTP Monte Carlo net_debt 이중 차감 (Critical)
- **위치**: `valuation_runner.py:298,476,1166`
- **문제**: PBV/PE 세그먼트 equity에 이미 net_debt 포함 → MC가 full net_debt 다시 차감
- **수정**: `_run_monte_carlo()`에 `effective_net_debt` 전달, mixed-method일 때 사용
- **검증**: mixed-method 프로필(kb_financial 등)로 MC mean vs 시나리오 가중평균 비교

### P0-2. `segment_revenue` AI 시나리오 미저장 (Critical)
- **위치**: `pipeline/profile_generator.py:755-758`
- **문제**: `auto_analyze()`가 `segment_ebitda`/`segment_multiples`만 저장, `segment_revenue` 누락
- **수정**: structured per-segment scenario fields에 `segment_revenue` 포함
- **검증**: `--auto`로 ev_revenue 세그먼트 있는 기업 프로필 생성 → YAML에 segment_revenue 확인

### P0-3. MC가 음수 EBITDA 세그먼트 제외 — 상향 편향 (Critical)
- **위치**: `engine/monte_carlo.py:145-146`
- **문제**: `elif ebitda > 0` 조건이 적자 세그먼트를 skip → SOTP와 MC 불일치
- **수정**: SOTP `calc_sotp()`와 동일 규칙 적용 (음수 EBITDA도 포함)
- **검증**: 적자 세그먼트 포함 synthetic input으로 MC vs SOTP mean 비교 테스트

### P0-4. Cross-validation DCF 호출 미보호 — 비DCF 메서드 crash (High)
- **위치**: `valuation_runner.py:440,538,911,1001`
- **문제**: `calc_dcf()`가 `ebitda<=0` 또는 `WACC<=TG`에서 ValueError raise → 비DCF 메서드 중단
- **수정**: cross-validation DCF 호출을 `try/except ValueError`로 래핑, 로깅 후 skip
- **검증**: ebitda<=0인 프로필로 DDM/RIM/NAV 실행 → crash 없이 완료 확인

### P0-5. `rcps_repay=0` 명시 override 무시됨 (High)
- **위치**: `engine/scenario.py:39-43`
- **문제**: `sc.rcps_repay > 0` 조건 → explicit zero가 IRR fallback으로 빠짐
- **수정**: CPS 로직(line 30)과 동일하게 `is not None` 체크로 변경
- **검증**: `rcps_repay: 0` 시나리오에서 repay=0 확인하는 단위 테스트

## 추가: 이번 세션 커밋 대상
- 직전 세션 미커밋 변경사항 (OpenRouter + capex_fade_to)도 함께 커밋

## P1 백로그 (P0 이후, 시간 남으면)
- P1-4: `gap_diagnostics.py` 테스트 추가 (412줄 전체 미테스트)
- P1-9: `except (ValueError, Exception): pass` → 로깅 추가
- P1-10: engine/ 순수성 위반 수정 (peer_fetcher import 제거)
- P1-6: f-string YAML → `yaml.dump()` 전환

## 참고 파일
- `valuation_runner.py` — MC 호출, cross-validation DCF, mixed-method SOTP
- `engine/monte_carlo.py:131-146` — per-segment SOTP EV, 음수 EBITDA skip
- `engine/scenario.py:39-43` — RCPS repay override 조건
- `pipeline/profile_generator.py:744-758` — AI 시나리오 structured fields 저장
- `engine/dcf.py` — ValueError raise 조건 (line 32-40)

## 6모델 Cross Review 전체 리포트
P0/P1/P2 전체 목록은 이 세션 대화 히스토리 참조. 주요 도메인 발견:
- Finance: Terminal FCFF 재투자율 불일치, NOL 미반영, MC 로그정규 권장
- Security: Streamlit 인증 없음, prompt injection, ilike wildcard
- Architecture: valuation_runner 1260줄 → _finalize_result() 추출 권장

## 모드: normal
