# AI Collaboration

본 프로젝트는 사람(분석가)과 두 AI 도구(Claude Code · Codex CLI)의 협업으로 구축되었습니다. 면접·자소서·README 모든 곳에서 **실제 작동한 분업**을 동일하게 기술합니다 — 과장 없이, drill-down에 견디도록.

## 분업 기준 (실제 워크플로 기준)

### 사람 (본인) 담당 — 최종 책임·소유

- **전략 방향**: 무엇을 만들지, 어디까지가 스코프인지, 우선순위.
- **방법론 의사결정**: 마진 모델을 HBM-mix 브리지 → cost-per-bit operating-leverage로 진화시킬지, 백테스트 앵커를 단일 연속 체인으로 통합할지 등 **갈림길마다 본인이 결정**.
- **가정 수치 검토·확정·소유**: AI가 시장 데이터 기반 **초안**을 제시하면, 본인이 출처를 확인하고 조정·확정. **최종 수치와 그 방어는 본인 책임** (아래 "가정의 출처와 소유" 참조).
- **결과 해석**: Consensus gap 의 `interpretation`, 시나리오 확률 정당화, thesis 전문 (`docs/sk_hynix_thesis.md`).
- **면접 방어**: 모든 가정의 근거·취약점·under-identification 한계를 본인 언어로 설명.

### Claude Code 담당 — 리서치·검증·방법론 설계

- **시장 리서치 기반 가정 초안**: TrendForce/SK IR/DART 등 **독립 출처**에서 분기 ASP·HBM 비중·세그먼트 마진 후보를 조사하고 **출처 주석과 함께** 초안 제시 (`profiles/sk_hynix.yaml` 주석 참조). → 본인이 검토·확정.
- **검증·QA (핵심 기여)**: 각 구현을 실제로 돌려 교차검증. 테스트는 통과하나 산출 수치가 조작·무의미했던 **silent failure 다수 적발** (예: 합성 백테스트 history, 연간치를 분기 seed로 오용, EPS proxy가 엔진 우회, API 키 로그 누출).
- **방법론 설계·핸드오프**: 결함별 수정 스펙·공식·검증법을 `HANDOFF_phase_a_fixes.md`에 명세.
- **방법론 규율 강제**: 백테스트 **비순환**(앵커=관측 고정, driver=독립 출처, 실현 매출 미투입), curve-fitting 방지.

### Codex CLI 담당 — 코드 구현

- 함수 본문 구현·리팩토링, pytest 케이스, Pydantic 스키마, 파이프라인(httpx·yfinance) 래퍼, 템플릿.
- Phase B(시그널 레이어): LLM 추출 호출(`ai/extractor`)·PDF/MD&A 파싱(`pipeline/disclosure_loader`)·CAR event study(`engine/signal_backtest`) 본문 구현. 방법론 스펙은 `HANDOFF_phase_b.md`(Claude), 가정·라벨·해석은 본인.
  - **STATUS: DORMANT (2026-07-31)** — 활성 프로파일 0개(`signal_layer` 부재), `reports/.cache/signal_*.json` 0건 = 이 추출기가 실제 리포트를 만든 적 없음. 재활성화 조건은 `HANDOFF_phase_b.md` 상단 배너 참조.

## 가정의 출처와 소유 (정직성 핵심)

- 가정 수치는 **AI가 시장 데이터로 초안**, **본인이 검토·확정·소유**합니다. "초안"은 출발점이지 최종이 아닙니다.
- 일부 값은 **본질적으로 under-identified** 입니다 — 예: HBM/DDR 세그먼트 **총이익률은 회사가 비공시**. 앵커 분기의 실측 aggregate GP(DART)에 일치시키고, HBM 마진은 애널리스트 추정, DDR은 잔차로 둡니다. 이 한계는 숨기지 않고 thesis·면접에서 명시합니다.
- 백테스트는 **검증 지표이지 맞춤 대상이 아닙니다**: 입력(앵커·ASP)을 결과와 독립적으로 정한 뒤, MAPE는 그 가정이 현실을 재현하는지 **시험**합니다.

## 무엇을 검증할 수 있나

- `profiles/sk_hynix.yaml` 주석에 모든 가정의 **출처**가 기재됨 (DART 실측·TrendForce·SK IR).
- `interpretation`/thesis 필드는 항상 빈 채로 리턴 (테스트로 강제) — 자동 해석 금지.
- `HANDOFF_phase_a_fixes.md`에 결함 진단·수정 이력이 추적 가능.
- git history 로 누가 무엇을 했는지 확인 가능.

## 스코프 정직성 (과대주장 금지)

- 본 엔진의 **매출/마진 모델은 메모리 반도체에 특화**(DRAM/HBM/NAND, bit×ASP, cost-per-bit)입니다.
- **재사용 가능**: 파이프라인·시나리오·백테스트·방법론 규율은 산업 무관. 메모리 동종(삼성·Micron)은 새 profile로 거의 그대로 적용.
- **재모델링 필요**: 비메모리(파운드리·비반도체)는 매출/마진 엔진을 그 회사 경제학으로 새로 설계해야 함. "범용 실적 엔진"이 아니라 **"메모리 forward 모델 + 재사용 가능한 방법론·배관"**.

## CLAUDE.md / AGENTS.md / .codex/

본 repo 의 `CLAUDE.md`, `AGENTS.md`, `HANDOFF_*`, `.codex/`(생성 시)는 **의도적으로 공개 자산**입니다. AI 협업 워크플로 자체가 portfolio 의 일부입니다. BVT([business-valuation-tool](https://github.com/jiwonsea/Business-Valuation-Tool))와 동일 기준을 유지합니다.
