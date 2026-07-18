# CODEX 지시 — NVDA Phase B 클로징 + 위생 수정

2026-07-17 (Claude) | 상태: **Phase B 실질 완료. 아래는 마감·위생 작업 (신규 기능 아님).**
선행: `HANDOFF_CODEX_nvda_phaseB_verify2.md` → Codex B-3 원자 재기록 → **사용자 로컬 검증으로 무결성 확정**

## 0. 🟢 지상 진실 (먼저 읽을 것 — 유령 쫓지 말 것)

**`profiles/nvda.yaml`은 디스크에서 정상이다.** 사용자 로컬 확인:
```
lines 468 · sha bb276cf56003 · tail [multiples, scenario_validation, mc_enabled, market_price]
```
→ Codex의 B-3 원자 재기록은 **진짜로 성공**했다. capex 6,042 − 1,227 + 1,757 = 6,572 (실측), provenance 5필드, tail 보존.

### ⛔ Claude가 이전 라운드에 보고한 결함들은 **샌드박스 마운트 아티팩트였다 — 실제 디스크 결함 아님**
- "5번째/6번째 truncation", "financial_anchor 미등록(model_fields)" 등은 **에이전트 샌드박스의 stale/부분 read** 때문. 실제 파일은 온전했음.
- **증명**: 사용자 로컬 read(468/bb276cf/tail 완전) vs 샌드박스 read(425/55e2.../tail 유실)가 불일치. 마운트가 최근 기록 파일을 stale로 서빙.
- 👉 **Codex는 이 "truncation들"을 복구/재기록하지 말 것.** 파일은 이미 정상이다. **로컬 재read가 정본**이다.

## 1. 실제 마감 항목 (전부 로컬에서, fresh bytecode로)

**착수 전 필수** (양쪽 에이전트를 물었던 stale bytecode 방지):
```cmd
for /r %f in (*.pyc) do @del "%f"
for /d /r %d in (__pycache__) do @rd /s /q "%d" 2>nul
set PYTHONUTF8=1
set PYTHONDONTWRITEBYTECODE=1
```

### 1-1. CRLF 규약 확인 (실제 리스크)
`scripts/rewrite_nvda_ttm_provenance.py`가 `yaml.dump`로 기록 → **기본 LF**일 수 있음. 저장소 규약은 **CRLF**(CLAUDE.md).
```cmd
python -c "b=open('profiles/nvda.yaml','rb').read(); print('CRLF' if b'\r\n' in b else 'LF-ONLY', 'crlf=',b.count(b'\r\n'),'lf=',b.count(b'\n'))"
```
- LF-ONLY면 CRLF로 정규화(HEAD 블롭 대비 전체 줄 diff 방지). 재기록 시 `newline=''` + 명시적 CRLF 또는 사후 변환.

### 1-2. git diff 위생
```cmd
git diff -- profiles/nvda.yaml
```
- 의도한 Phase B 추가분(`financial_anchor`, `ttm_anchor`, `ttm_provenance`)만 있는지 확인.
- **Claude 재구성 잔재 없어야 함**: `Claude 재구성`, `Codex 확인 필요`, `# NOTE: ... truncation` 마커 검색 → 있으면 제거.
- `ttm_anchor` 값이 정답지와 일치: revenue 253491 / op 162285 / net_income 159613 / adjusted_net_income 143451 / dep 3229 / capex 6572.

### 1-3. 최종 전면 검증 (정본 판정)
```cmd
python scripts\verify_nvda_phaseA_v2.py
python scripts\verify_nvda_phaseB.py
python scripts\verify_nexus_round4.py --skip-pytest
python -m pytest tests\test_ttm.py -q
python -m pytest -q --deselect tests/test_engine.py::TestScenarioDriverRoundTrip
python -c "from valuation_runner import load_profile; vi=load_profile('profiles/nvda.yaml'); print('anchor',vi.financial_anchor,'base_rev',vi.consolidated[vi.base_year]['revenue'],'fy_audit_rev',vi.fy_base_financials['revenue'])"
```
기대: Phase A/B ALL PASS · test_ttm **5/5** · 전체 **979 passed** · 마지막 줄 `anchor ttm / base_rev 253491 / fy_audit_rev 215938` (B-4 앵커 소비 + FY 감사보존 동시 확인).

### 1-4. 넥써쓰 R-8 gap_diagnostic 2건 — 환경성 분리
nvda·tsla R-8은 **라이브 시장가/gap_diagnostic**이 필요해 오프라인에서 실패(환경성, 회귀 아님). 네트워크 로컬에서 PASS 확인하거나, `verify_nexus_round4`에서 **환경성 스킵/표기**하여 회귀로 오인되지 않게 문서화.

### 1-5. Phase B 커밋
작업트리 미커밋 다수. Phase B 산출물(신규: `engine/ttm.py`, `tests/test_ttm.py`, `scripts/verify_nvda_phaseB.py`, `scripts/rewrite_nvda_ttm_provenance.py`, fixtures; 수정: `edgar_parser.py`, `edgar_client.py`, `profile_generator.py`, `schemas/models.py`, `valuation_runner.py`, `output/console_report.py`, `profiles/nvda.yaml`)를 **논리적 커밋**으로 정리.
- ⚠️ pre-commit hook이 `.env`/시크릿 패턴에서 `exit 1`(이전 "Stop hook code 1" 원인 가능) — 스테이징에 시크릿 없는지 확인.
- 🔴 `git restore/checkout/reset --hard` **금지** (미커밋 작업 다수).

## 2. 프로세스 수정 (재발 방지)

### 2-1. write-verify fail-closed
`rewrite_nvda_ttm_provenance.py`는 이미 재read 검증 포함. **프로필 기록 경로 전반**에 다음 보장: 기록 직후 `wc -l` + `yaml.safe_load` + 앵커/필드 재확인, 실패 시 예외(fail-closed). (파이프라인 `_atomic_write_yaml`은 정상이나, 수동 편집은 이를 우회함 — **nvda.yaml 수동 편집 금지, 스크립트/원자경로만 사용**.)

### 2-2. CLAUDE.md Session Safety에 추가 (검증 규율)
> **에이전트 샌드박스 read는 최근 기록 파일에 대해 신뢰 불가** — Windows→Linux 마운트가 stale/부분 뷰(및 stale `.pyc`)를 서빙한다. "truncation·필드 누락" 발견 시 **파일을 덮어쓰기 전에 로컬(호스트)에서 재read/재컴파일로 검증**할 것. 이번 세션에서 유령 truncation 다수·stale import(model_fields) 발생. 정본은 항상 호스트 read.

## 3. 완료 정의
1-1~1-5 로컬 전항 PASS + diff 위생 통과 + 커밋 완료 → **Phase B COMPLETE = NVDA autoprofile gap(A+B) 종결.**
이후 Phase C(forward FY27E 앵커, 적격 peer beta snapshot)는 별도 — peer는 검증·차단 근거이지 가격 상향 수단 아님 (ROUND3 §2 계승).
