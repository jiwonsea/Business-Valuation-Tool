# BVT Restructure Plan — Local Data Collection / Remote Offline Valuation

> 상태: **PLAN ONLY (구현 전)** · 작성 세션: 2026-07-11 주간 루틴
> 목적: 원격 Claude Code 환경의 egress 정책이 모든 외부 데이터 소스를 차단하므로,
> 파이프라인을 "네트워크가 필요한 부분(로컬)"과 "오프라인으로 가능한 부분(원격)"으로 분리한다.

## 0. 배경 (왜 바꾸는가)

원격 Claude Code on the web 환경에서 도달성 테스트 결과:

- ✅ 허용: `api.anthropic.com`, PyPI/npm 등 패키지 레지스트리
- ❌ 차단(egress 403): NAVER API, Google News RSS, Yahoo Finance(RSS+data API),
  SEC EDGAR / data.sec.gov, DART API, OpenRouter, (Supabase 추정)

즉 **원격에서 오프라인으로 되는 것은 "기존 프로필 기반 밸류에이션 계산 + 리포트 생성"뿐**이다.
프록시 정책은 우회 불가(README: "do not retry or route around — report the blocked host").

## 1. 핵심 설계 원칙: Discovery Selection 보존 (사용자 지적 #3 반영)

현재 BVT는 **뉴스 분석 → 기업 선정 → 선정된 기업만 밸류에이션**하는 구조다.
따라서 원격에서 "아무 프로필이나" 평가하면 안 되고, **그 주에 선정된 기업 집합**을
로컬에서 만들어 원격으로 넘겨야 한다.

→ 로컬 산출물(handoff bundle) = **(a) 주간 선정 기업 매니페스트 + (b) 해당 기업들의 생성된 프로필**.
원격/CODEX는 이 매니페스트에 있는 기업만 평가한다.

## 2. Producer / Consumer 분리 (git이 전송 매체)

```
┌─────────────────────────────────────────┐        ┌──────────────────────────────────────────┐
│  LOCAL (네트워크 개방)                     │        │  REMOTE Claude Code 루틴 (제한 환경)        │
│  = Producer                              │        │  = Consumer / Orchestrator                 │
├─────────────────────────────────────────┤        ├──────────────────────────────────────────┤
│ Phase 1  뉴스 수집 + AI 발굴/선정          │        │ git pull                                    │
│ Phase 2  dedup + 중요도 스코어링           │        │ 매니페스트 로드 → 선정 기업 목록 확정         │
│ Phase 3a 재무데이터 수집 (DART/EDGAR/YF)   │  git   │ ── CODEX 평가 핸드오프 (§3) ──               │
│ Phase 3a LLM 프로필 생성                   │  ───►  │   선정 기업별 밸류에이션 실행                 │
│                                          │  push  │ 리포트/Excel + JSON 요약 생성                │
│ 산출: weekly_manifest.json + profiles/    │        │ 결과 git commit & push (valuation-results/) │
│ git commit & push                        │        │ ❌ Gmail / WordPress / Naver / Supabase 없음 │
└─────────────────────────────────────────┘        └──────────────────────────────────────────┘
```

- **로컬**: 기존 `python -m scheduler.weekly_run` 을 그대로 쓰되, "발굴+수집까지만" 수행하는
  모드로 끝내고 매니페스트를 커밋한다 (아래 §4.1).
- **원격**: 신규 `--offline` 모드로 네트워크 Phase 전부 스킵, 매니페스트 소비 (아래 §4.2).

## 3. CODEX 평가 핸드오프 인터페이스 (경계 정의)

> 사용자 지시: "PLAN 작성하고 **CODEX로 평가 핸드오프까지 진행**".
> 자동화 오케스트레이션은 Claude Code, **밸류에이션 실행(평가)은 CODEX**가 담당하는 경계를 명시한다.

### 3.1 CODEX에 넘기는 입력 (Input contract)

```
handoff/
  weekly_manifest.json        # 주간 선정 기업 + 메타 (market, ticker, 선정 사유, profile 경로)
  profiles/<slug>.yaml        # 선정 기업별 ValuationInput YAML (로컬에서 생성 완료)
```

`weekly_manifest.json` 스키마(초안):
```json
{
  "label": "Jul 2nd week (7/11)",
  "generated_at": "2026-07-11T00:00:00",
  "selected": [
    {"slug": "005930", "name": "삼성전자", "market": "KR",
     "ticker": "005930", "reason": "...", "profile": "profiles/005930.yaml"}
  ]
}
```

### 3.2 CODEX가 돌려주는 출력 (Output contract)

- 기업별 `ValuationResult` 요약 (`summary_md`) + 상태(success/no_result)
- `valuation-results/<week>/_weekly_summary.json` 와 동일 형식으로 산출 (기존 다운스트림 호환)

### 3.3 열린 질문 (구현 전 확정 필요) ⚠

1. **CODEX 실행 위치**: 로컬(네트워크 옆)인가, 별도 CI인가? → 밸류에이션은 오프라인이므로
   원격 Claude Code 내에서 그냥 Python으로 실행해도 되는데, 굳이 CODEX로 넘기는 이유/환경 확정 필요.
2. **호출 방식**: CODEX CLI 서브프로세스 호출 vs. API 호출 vs. 수동 핸드오프(파일 교환)?
3. **평가 로직 주체**: 기존 `engine/`+`valuation_runner.run_valuation()`(검증된 순수함수)을
   CODEX가 그대로 호출? 아니면 CODEX가 자체 재구현? → **기존 엔진 재사용 강력 권장**
   (밸류에이션 정합성/회귀 방지). CODEX는 "오케스트레이션/실행"만, 계산은 BVT 엔진.

## 4. 코드 변경 범위 (구현 시)

### 4.1 로컬 Producer 모드
- `scheduler/weekly_run.py`: `--collect-only` (가칭) 플래그 추가
  - Phase 1~3a(발굴+수집+프로필 생성)까지 수행
  - Phase 3(valuation)·3.5(Supabase)·5(Gmail)·6(WP/Naver) 스킵
  - `handoff/weekly_manifest.json` + `handoff/profiles/*.yaml` 산출 후 종료
- 기존 풀 파이프라인 동작은 유지(하위호환) — 신규 플래그일 때만 분기.

### 4.2 원격 Consumer 오프라인 모드
- `scheduler/weekly_run.py`: `--offline` 플래그 추가
  - 네트워크 Phase(1, 3a-fetch, 3.5, 5, 6) 전부 **호출하지 않음** (import도 지연/조건부)
  - `handoff/weekly_manifest.json` 로드 → 선정 기업 profiles 로드
  - `valuation_runner.run_valuation()` 로 계산 → 리포트/Excel/`_weekly_summary.json`
  - Gmail/WP/Naver/Supabase 코드 경로 **진입 자체 차단** (플래그 가드)
- (CODEX 경계) 4.1 산출물을 CODEX가 소비하는 경우, §3 인터페이스로 대체.

### 4.3 제거/비활성 (원격 루틴 한정)
- `email_sender` 호출 제거, `_alert()`의 Gmail 경로 무력화 (원격에선 recipient 없음 → 이미 skip).
- `_upload_excels_to_storage()` 는 `get_client() is None`이면 이미 no-op → 추가 조치 불필요.

### 4.4 DB(Supabase)
- **재설정하지 않음** (내 판단, 사용자 승인). 코드는 현행 graceful-degrade 유지.
- 향후 backtest/캘리브레이션 히스토리 필요 시 로컬에서만 재설정+실행.

## 5. Claude Code 자동화 루틴 (원격, #5)
- 주간 트리거 = 이 원격 세션이 하는 일: `git pull` → `weekly_run --offline` → 결과 `git commit & push`.
- **Gmail 없음.** 산출물은 `valuation-results/<week>/` 로 리포에 남긴다.
- 알림이 필요하면 Gmail 대신 (선택) PushNotification 또는 커밋 메시지로 대체.

## 6. 구현 순서 (다음 세션)
1. `--collect-only` (로컬 Producer) + 매니페스트 스키마 확정
2. `--offline` (원격 Consumer) — 네트워크 phase 가드 + 매니페스트 소비
3. CODEX 핸드오프 경계(§3.3 열린 질문 확정 후) 결선
4. 원격 자동화 루틴에 `--offline` 배선, Gmail 경로 제거
5. 테스트: 오프라인 모드가 네트워크 호출 0건인지 검증 (egress 로그로 확인)

## 7. 확정 필요 사항 (사용자 결정 대기)
- [ ] §3.3-1: CODEX 실행 위치/환경
- [ ] §3.3-2: CODEX 호출 방식
- [ ] §3.3-3: 평가 계산 주체 (기존 BVT 엔진 재사용 권장)
- [ ] §4.1: Producer 플래그명 (`--collect-only` OK?)
- [ ] §4.2: Consumer 플래그명 (`--offline` OK?)
