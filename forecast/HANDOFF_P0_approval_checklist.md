# P0 실행 + 정책 승인 체크리스트 (사람 전용 작업)

- `DOC_REV: autopilot-rev3.4 / 2026-07-31 KST` (오토파일럿 3문서와 동일 rev)
- 목적: Codex가 P1 착수에 필요하다고 못박은 **사람 전용 승인 2건**을 실행 가능한 형태로 정리

---

## 0. 지금 막혀 있는 것 (Codex 관측 + 본 세션 확인)

| 항목 | 상태 |
|---|---|
| HEAD | `23b1d9769a9f6b57432d1749cde3d997f0b88c18` — origin/main 대비 **29커밋 앞섬** |
| 오토파일럿 3문서 | untracked |
| `config/` · `policy/` | 부재 — **정상**(P1 산출물) |
| 정책 상수 | 미승인 → 본 문서 §2 |
| 태그 우선순위 | 미제시 → **`PROPOSAL_policy_selection_rules_v1.yaml` 초안 제공** |
| `approver_fingerprints` | 미제시 → §3 |
| PAT | 미검증 → §4 |

---

## 1. P0 — 커밋 분류·푸시 (호스트에서 사람이 실행)

> ⚠ 이 세션의 device_bash는 마운트 리포에 **git 쓰기 명령을 실행하지 않는다**(index.lock 사고 이력). 아래는 호스트 터미널용.

### 1-a. 컨센서스 원수치 분리 (결정 완료: 구간화 공개)

```bash
mkdir -p reports/private reports/public
git mv reports/gev_q2_2026_forecast_FROZEN.md   reports/private/   # 원본 내용 무변경
git mv reports/tsla_q2_2026_forecast_FROZEN.md  reports/private/
git mv reports/ibm_q2_2026_scorecard.md         reports/private/
git mv reports/sk_hynix_q2_2026_scorecard.md    reports/private/
printf 'reports/private/\n' >> .gitignore
```

- **원본은 절대 편집하지 않는다** — `scripts/score_tsla_q2_2026.py`의 FROZEN 앵커 sha 가드(`10d1dca6…`)가 깨진다. 경로 상수만 갱신.
- 공개본(`reports/public/*.redacted.md`)은 P1의 `engine/disclosure.py` 구현 후 생성. **그때까지 공개본 없이 진행해도 무방.**

### 1-b. 분류별 푸시 순서

1. 코드·스키마·테스트 (`generic_cli.py`, `schemas/`, `engine/`, `tests/`, `scripts/`) — 안전, 먼저
2. SEC 원자료 파생 (`inputs/*_actual.yaml`, profiles의 구조 필드) — 안전
3. 세션 운영 문서 (`HANDOFF_*`, `START-*`, 오토파일럿 3문서 + 본 문서 + PROPOSAL 2종) — 프리뷰 기사 인용 여부만 훑고
4. `_to_delete/` — **푸시 금지**. `_to_delete/stranded_git_locks/` 포함해 직접 삭제

### 1-c. 완료 후

```bash
git rev-parse HEAD    # ← 이 SHA를 config/autopilot.yaml:required_commit 에 넣는다
git push origin main
```

---

## 2. 정책 상수 승인 — `PROPOSAL_policy_resolver_v1.yaml`

동봉 파일이 P1 §2의 전 상수를 담은 실제 YAML이다. **승인 = 그대로 `policy/resolver_policy_v1.yaml`로 이동 후 커밋.** 값을 바꾸고 싶으면 바꾼 뒤 이동.

결과를 가장 크게 흔드는 5개만 다시 짚는다:

| 상수 | 제안값 | 근거 / 바꿀 때 영향 |
|---|---|---|
| `r2.level_weights` | `[.4,.3,.2,.1]` | 최근 분기 가중. 평탄하게 하면 램프 기업(GEV·NVDA) 과소예측 재발 |
| `r3.bear/bull_quantile` | `.90 / .10` | 좁히면 GEV 29.8% 같은 세율 급등을 밴드가 못 담음 |
| `r4.band_quantile` | `.80` | below-OP 밴드 폭. TSLA OI&E 부호반전이 들어오려면 넓어야 함 |
| `r6.probabilities` | `.50/.25/.25` | 확률가중 산출에 직결. 분기별 재량 금지가 핵심이라 값 자체보다 **고정**이 중요 |
| `r7.fallback_band.eps.absolute_floor_usd` | `$0.25` | 전망 EPS가 0 근방일 때 밴드 붕괴 방지 |

## 2-b. 태그 우선순위 승인 — `PROPOSAL_policy_selection_rules_v1.yaml`

기존 `pipeline/edgar_fetcher.py`의 `*_CONCEPTS` 상수를 그대로 승계하고, **리졸버에 필요한데 지금 코드에 없는 3종을 추가**했다:

- `OperatingIncomeLoss` (R2의 연결 GAAP OP — **현재 fetcher에 없음**)
- `IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` (R3/R4 pretax)
- `IncomeTaxExpenseBenefit` (R3)

> ⚠ **구현 갭 1건 — Codex에 전달 필요.** companyfacts의 fact에는 `filed`(날짜)만 있고 **acceptance instant가 없다**(현재 `Fact` 데이터클래스도 `filed: date`). `accepted_at` 계약을 지키려면 `https://data.sec.gov/submissions/CIK##########.json`의 `filings.recent.acceptanceDateTime`(ISO8601 UTC, 예: `2026-05-08T20:35:07.000Z`)을 **accession으로 조인**해야 한다. 본 세션에서 해당 필드 존재를 실측 확인함. 구버전 필링이 `filings.files` 페이지로 넘어가는지는 미확인 — 구현 시 검증할 것.

## 3. `approver_fingerprints` — SSH 서명 키 등록

정책 승인 커밋에 서명하고, 그 서명자만 허용하기 위한 값이다.

```bash
ssh-keygen -t ed25519 -C "efe-policy-approver" -f ~/.ssh/efe_approver
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/efe_approver.pub
git config --global commit.gpgsign true
ssh-keygen -lf ~/.ssh/efe_approver.pub      # ← 출력의 SHA256:... 가 fingerprint
```

- 그 `SHA256:...` 값을 `config/autopilot.yaml:approver_fingerprints`에 넣는다(P1에서 생성).
- `~/.ssh/allowed_signers`에 `efe-policy-approver ssh-ed25519 AAAA...` 한 줄 + `git config gpg.ssh.allowedSignersFile`을 설정해야 `git verify-commit`이 통과한다.
- GitHub에도 같은 키를 **Signing key**로 등록하면 원격에서 Verified로 표시된다(필수는 아님).

## 4. PAT 검증 (P-3 전제)

- fine-grained PAT: 리포 `jiwonsea/earnings-forecast-engine` 단독, 권한 **Contents: Read and write**, 만료 설정.
- 스케줄 환경 시크릿으로 주입 후 **빈 브랜치 push로 1회 검증**(본 세션 실측: 기본 자격증명으로는 push 불가).
- 검증 실패 시 동결은 `FREEZE_UNPROVEN`이 되므로 파일럿 전에 반드시 통과시킬 것.

---

## 5. 순서

```
1-a·1-b·1-c (P0 푸시) → SHA 확보
        ↓
2·2-b (정책 2종 승인·커밋) + 3 (fingerprint) + 4 (PAT)
        ↓
Codex: P1 구현 (config/·policy/ 생성, required_commit 주입)
        ↓
파일럿 NVDA FY27 Q2 — 수집 8/23 06:00 KST, 동결 8/24 06:00 KST(T-72)
```

발표는 **2026-08-27 06:00 KST**. 오늘 기준 남은 시간이 넉넉하지는 않으므로, P0가 이번 주를 넘기면 파일럿은 다음 분기로 미루는 편이 낫다.
