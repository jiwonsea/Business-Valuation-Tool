# HANDOFF — 디바이스 브리지 방어 도구 `bridge_ops` (2026-08-12, rev-3 · 구현 착수)

**상태: §A 종결.** Codex CONDITIONAL 판정(2026-08-12)의 조건을 전부 반영했다. **이 문서 기준으로 §B 구현에 착수한다.** 단 §A-6에 **Codex 권고를 그대로 받지 않고 수정한 항목이 1건(Q3)** 있으니 그 절을 먼저 읽고, 이의가 있으면 구현 전에 제기할 것.

**리비전 이력**
- rev-1 → rev-2: 적대적 리뷰에서 blocking 4건 포함 10건 반영. rev-1 폐기.
- rev-2 → rev-3: Codex 판정 반영. Q1·Q2·Q5·Q6 APPROVE, Q3·Q4·Q7 CONDITIONAL 해소, 추가 보완 10건 편입. **rev-2 폐기.**

---

## §0. 이 문서의 성격

- 시제품 `scripts/bridge_ops.sh`가 리포에 있다(untracked, 2026-08-12). **이 문서는 그것을 Python으로 재작성해 pytest 게이트에 편입하는 명세다.** 시제품은 §B-6에서 폐기한다.
- `CLAUDE.md`에 "Device Bridge Limits" 절이 이미 추가되어 있다(modified, uncommitted). 본 작업 커밋에 포함한다.
- **너(Codex)는 Windows 호스트에서 돌고 브리지를 겪지 않는다.** 이 명세의 핵심 난제는 "겪을 수 없는 실패를 어떻게 테스트하는가"이고, §A-3 불변식과 §B 테스트가 전부 그 문제를 겨냥한다.

---

## §1. 계측된 사실 (설계의 전제)

`device_bash` 호출은 매번 새 bwrap 샌드박스다. `ps -o cmd= -p 1`:

```
bwrap --new-session --die-with-parent --unshare-net --unshare-pid --proc /proc -- /usr/bin/bash -c ...
```

| # | 사실 | 측정 방법 | 관측값 |
|---|---|---|---|
| F1 | 호출당 하드 타임아웃 | `sleep 40` / `sleep 60` | 40s 통과, 60s → `Command timed out after 45000ms` |
| F2 | 백그라운드 프로세스 미생존 | 90초 루프를 `nohup … &`로 띄우고 40초 뒤 폴링 | 로그가 `tick 2`에서 정지(호출 종료 시점) |
| F3 | 호출 간 상태 없음 | 매 호출 PID 1 = bwrap | cwd·env·셸 상태 이월 없음 |
| F4 | 호출은 직렬화 | 동시 2건 발사 | 07:16:09–13 종료 후 07:16:15 시작 |
| F5 | 마운트 unlink 금지 | `rm -f <mount>/x.tmp` | `Operation not permitted`, 파일 잔존 |
| F5' | 마운트 overwrite 허용 | `echo > x.tmp` 2회 | 정상 반영 |
| F6 | **F1×F5 연쇄 = 영구 고장** | `.git/index.lock` 나이 확인 | 2026-08-09 14:34 생성 0바이트 락이 **08-12까지 3일간** 모든 git 차단 |
| **F11** | **🚨 인덱스를 건드리는 git은 매번 락을 남긴다** | 락 청소 → `git status --porcelain` → 재확인 | **새 0바이트 `index.lock` 재생성**(14:02). 반면 `git rev-parse HEAD` 뒤에는 락 0개 |
| F7 | orphan git 임시객체 | `find .git/objects -name 'tmp_obj_*'` | 11개 잔존 |
| F8 | 디스크는 VM 쪽이 좁다 | `df -h` | 마운트(F:) 805G 여유 / VM `/sessions` 9.8G 중 1.4G(86%) |
| F9 | FUSE 비용 | `du -sh` 리포 88M·1660파일 | 5.8s(≈3.5ms/파일) |
| F10 | tar 비용 | `tar -czf` incl. `.git` | 15.1s = 45초 예산의 34% |

**F6이 사용자가 체감한 "끊김"의 정체다.** 브리지는 살아 있었고, 3일 전 죽은 프로세스의 잔해가 계속 작업을 깨고 있었다.

**F11이 설계를 바꾼다.** 락은 "죽은 프로세스의 흔적"이 아니라 **마운트에서 git이 정상 동작할 때조차 남는 상시 부산물**이다. 따라서 ① 마운트에서 **락 나이로 유효성을 판정하면 안 되고**(모든 락이 항상 방금 만든 것처럼 보인다), ② 락 청소는 **git 실행 뒤에** 와야 하며, ③ 상태 확인이 목적이면 `status` 대신 `rev-parse`를 쓴다.

### 별건 — MCP 트랜스포트 단절 (코드로 못 고침)

같은 세션 07:22경 `mcp__remote-devices__*` 툴 전체가 사라져 `device_bash`가 `No such tool available`로 실패했다. 디바이스 VM은 **계속 살아 있었고**(uptime 1:32 연속, 마운트·파일 무손상), **`RefreshMcpTools(server="remote-devices")` 한 번**으로 37개 툴이 상태 손실 없이 복귀했다. → 세션 측 동작이라 **리포 코드로 해결 불가**. §C 비목표. **구현하지 말 것.**

---

## §2. 확정된 설계 결정 (재논의 대상 아님)

| 축 | 결정 | 출처 | 함의 |
|---|---|---|---|
| 범위 | EFE 리포 전용 | 사용자 | 형제 리포 배포·동기화 금지 |
| 구현 | Python + pytest 게이트 | 사용자 | `scripts/bridge_ops.py` + `tests/test_bridge_ops.py`. bash 시제품 폐기 |
| 강제 | 도구 + 문서 규율 | 사용자 | git hook·강제 래퍼 금지 |
| 삭제 전략 | unlink 시도 → EPERM 시 `_to_delete/` 이동 폴백 | Q1 APPROVE | 마운트 감지로 전략 고정하지 않음 |
| 종료코드 | 97/98/99 + 126/127 | Q2 APPROVE | §A-5 표 |
| chunk 재실행 승인 | `--assume-idempotent`, **단 재개 시에만 필수** | Q3 CONDITIONAL(수정) | §A-6 참조 |
| 락 정책 | 마운트=사후 무조건 청소 / 호스트=보존+경고, `locks --stale-after N`에서만 age 삭제 | Q4 CONDITIONAL | §B-1 |
| 가짜 git | `runner_fn` 주입 | Q6 APPROVE | PATH shim 금지 |

---

# §A. 확정 설계

## §A-1. 아키텍처

`scripts/bridge_ops.py` — **stdlib 전용**(브리지가 깨진 상태에서 `pip install`이 못 도는 게 정확히 이 도구가 필요한 상황이다).

```
python scripts/bridge_ops.py [--repo PATH] preflight
python scripts/bridge_ops.py [--repo PATH] doctor
python scripts/bridge_ops.py [--repo PATH] locks [--stale-after SECONDS]
python scripts/bridge_ops.py [--repo PATH] git <args...>
python scripts/bridge_ops.py [--repo PATH] run --budget 35 -- <cmd...>
python scripts/bridge_ops.py [--repo PATH] chunk --list L --state S [--assume-idempotent] -- <cmd... {} ...>
python scripts/bridge_ops.py [--repo PATH] chunk --list L --state S --shell --command "<template using BRIDGE_ITEM>"
```

**`--repo` 해석 순서:** `--repo` → `$BRIDGE_REPO` → 스크립트 파일의 부모의 부모. `git rev-parse --show-toplevel`은 **쓰지 않는다**(F11 — 락을 남기고, git 없는 환경에서 죽는다). `Path.resolve()`로 정규화해 보관하고, 이후 모든 격리 검사의 기준이 된다.

**`is_bridge_mount(path) -> bool`** — 단일 술어로 노출하고 직접 테스트한다. 판정은 **문자열 glob이 아니라 경로 구성요소 비교**(Q7-3): `parts`가 `('/', 'sessions', <any>, 'mnt', …)` 패턴에 부합하는지. Windows `Path.resolve()` 결과(드라이브 문자, `\\?\` 접두, 대소문자)에서 오작동하지 않아야 하며, POSIX·Windows 두 표현 모두에 대한 테스트를 둔다. 이 술어는 **삭제 전략이 아니라 출력·rc·락 정책만** 지배한다(Q1 판정).

**계층**

- `Remover(unlink_fn, move_fn, repo)` — 주입된 `unlink_fn` 시도 → `PermissionError`/`OSError(EPERM)`면 `move_fn`으로 `_to_delete/bridge_YYYYMMDD/<원래 상대경로>` 이동. **상대경로 구조를 보존**해 동명 충돌을 막고(Q1 조건), 충돌 시 `.1`, `.2` 접미. **이동 목적지도 repo 내부임을 검증**한다.
- `LockSweeper(remover, policy)` — `.git/index.lock`, `HEAD.lock`, `config.lock`, `objects/maintenance.lock`, `refs/heads/**/*.lock`, `objects/**/tmp_obj_*` 수집. **보고는 stderr로만**(INV-2의 stdout 투명성 보호).
- `Budget(time_fn, grace_s, waiter_fn)` — 시간 판단·유예·**프로세스 대기 경계까지 전부 주입 가능**(Q7-9: `time_fn`만 가짜로 만들면 실제 프로세스를 기다리는 루프가 끝나지 않는다).
- `ChunkRunner` — 리스트/상태파일 기반 재개형 실행기.
- `GitRunner(runner_fn)` — Q6 ②. `runner_fn` 기본값은 `subprocess.run(..., capture_output=False)`이며 stdin/stdout/stderr를 상속시킨다.

## §A-2. 시제품에서 반드시 고칠 4개 결함

1. **`chunk`이 실패 항목을 완료로 기록한다**(rc 미확인 append) → fail-closed 위반.
2. **`chunk`이 `eval` + 문자열 치환을 쓴다** → 공백·따옴표에서 깨지고 주입 위험.
3. **`run`의 예산 초과가 rc를 그대로 흘린다** → 명령 자체 실패와 구분 불가.
4. **`preflight`가 락을 쓸어낸 뒤 자기가 `git status`를 불러 락을 되살린다**(F11).

## §A-3. 불변식

- **INV-1 (삭제는 실패하지 않는다, 그러나 성공을 위조하지도 않는다).** `Remover.remove(p)`는 unlink 성공 또는 `_to_delete/` **이동** 성공 중 하나로 끝난다. 대상·목적지 모두 `resolve()` 후 `is_relative_to(repo.resolve())` 참이어야 한다(`..`·절대경로·심볼릭 링크 탈출 차단). **`move`가 copy+unlink로 분해되어 원본 unlink에 실패하면 "이동 성공"이 아니다**(Q7-1) — 예외를 던지되 **남은 복사본 경로를 메시지에 담는다**. Windows에서 잠긴 파일은 unlink뿐 아니라 같은 볼륨 move도 실패할 수 있으며, 이때도 예외 전파다(Q7-2).
- **INV-2 (락 청소는 무조건, 그리고 나중에 돈다).** `git` 서브커맨드는 git의 성공·실패·예외와 무관하게 `finally`에서, **git 종료 후에** 청소한다(F11). git의 rc·stdout·stderr는 변형 없이 통과하며 자식 스트림을 **캡처하지 않고 상속**시킨다(`git add -p` 보호). 스위퍼 보고는 stderr로만.
- **INV-3 (테스트는 벽시계를 기다리지 않는다).** 시간·유예·프로세스 대기 경계가 전부 주입 가능하다. `tests/test_bridge_ops.py`의 **어떤 단일 테스트도 1초 이상 소요하지 않는다.**
- **INV-4 (chunk은 fail-closed, 재개는 신원 기반).** 항목은 rc == 0일 때만 완료로 기록된다. 상태파일은 **완료 항목 문자열의 집합**이며 재개는 **위치가 아니라 멤버십**으로 판정한다. 첫 줄에 리스트 지문(`# bridge_ops v1 items=<N> sha256=<hex>`)을 적고 불일치 시 재개를 거부한다. **상태파일이 손상되었으면**(부분 행·잘못된 UTF-8·헤더 이후 깨진 행) 조용히 완료 처리하지 말고 rc 97로 거부한다(Q7-7).
- **INV-5 (브리지 없이도 완주하되, 사망은 숨기지 않는다).** 마운트가 **애초에 구성되지 않은 경우**(호스트 정상)는 rc 0 + `mount: n/a (host)`. **마운트 경로 형태인데 도달 불가**(F6급)는 **rc 2** + `mount: DEAD <path>`. 두 분기를 각각 테스트한다. git 부재·HEAD 부재는 **브리지 실패가 아니므로 rc에 영향을 주지 않는다**(Q7-5) — 경고만 출력하고 mount/locks/disk 진단을 계속한다.

## §A-4. Codex 판정 요약 (2026-08-12, 종결)

Q1 APPROVE(조건: 이동 목적지 격리 + 상대경로 보존) · Q2 APPROVE · Q3 CONDITIONAL ② · Q4 CONDITIONAL(호스트 자동삭제 금지) · Q5 APPROVE · Q6 APPROVE ② · Q7 CONDITIONAL(보완 10건). 전부 §A-1~§A-3·§B에 반영 완료.

## §A-5. 종료코드 계약

| rc | 의미 | 발생 위치 |
|---|---|---|
| 0 | 정상 (chunk: DONE 포함) | 전부 |
| 2 | 마운트 구성됐으나 도달 불가 | `preflight`, `doctor` |
| 97 | chunk 입력 무효 / 상태파일 무효·손상 / 실패 항목 존재 | `chunk` |
| 98 | chunk 예산 소진, 재호출 필요 (PAUSED) | `chunk` |
| 99 | run 예산 초과로 자식 강제 종료 | `run` |
| 126 | 자식 실행 실패 (OS 수준, 예: 권한) | `git`, `run` |
| 127 | 실행 파일 없음 | `git`, `run` |
| 그 외 | 자식 프로세스의 rc 그대로 | `git`, `run` |

**모호성 해소 규칙(Q7-4 확장).** 자식이 스스로 99/126/127로 끝난 경우와 우리가 만든 rc를 **rc만으로 구분할 수 없다.** 따라서 **stderr 마커가 유일한 판정 근거**다:
- 예산 킬일 때만 `BRIDGE_BUDGET_EXCEEDED <elapsed>s/<budget>s`
- 실행 자체가 실패했을 때만 `BRIDGE_EXEC_FAILED <errno-name> <exe>`

이 계약을 테스트로 고정한다("자식이 스스로 99로 끝나면 마커가 없어야 한다").

## §A-6. ⚠️ Codex 권고에서 수정한 1건 — Q3

Codex 권고는 **`--assume-idempotent` 상시 필수**였다. 아래로 **수정**한다. 이의 있으면 구현 전에 제기할 것.

**수정안.** `--assume-idempotent`는 **재개 호출에서, 그리고 이전에 실패한 항목을 다시 실행하게 될 때만 필수**다. 최초 실행(상태파일 부재)에는 요구하지 않는다.

- **근거 1 — 재실행 위험은 "이전에 실패한 항목"에만 존재한다.** 완료 항목은 신원 기반으로 스킵되므로 재개해도 재실행되지 않는다(INV-4). 최초 실행은 재실행 자체가 없다. 상시 필수로 만들면 위험이 없는 99%의 호출에도 플래그를 붙이게 되고, 그러면 플래그는 **의례가 되어 승인의 의미를 잃는다**(fail-closed의 실질이 사라지는 전형적 실패).
- **근거 2 — Codex가 ③을 기각한 이유는 "실패를 기본 스킵"이었지 "실패를 기록"이 아니다.** 그래서 실패 기록만 살린다: `<state>.failed`에 실패 항목을 기록하되 **스킵 판단에는 절대 쓰지 않는다.** 오직 "이번 재개가 재실행을 유발하는가"를 판정하는 용도다.
- **동작.** 재개 시 `<state>.failed`와 남은 항목의 교집합이 비어 있지 않은데 `--assume-idempotent`가 없으면 → **rc 97 + `CHUNK-RERUN-UNAPPROVED <n> item(s)`**. 플래그가 있으면 진행.
- **문서화 의무.** `--help`와 CLAUDE.md에 계약을 명시: *"이 플래그는 '실패 항목을 다시 실행해도 부작용이 중복되지 않음을 호출자가 확인했다'는 승인이다. 도구는 부분 성공을 알 수 없다."*

---

# §B. 구현 명세

## §B-0. 실패 메시지 요구사항 (문자열 고정)

테스트가 문자열을 어설션하므로 **아래는 리터럴이다.** 임의 변형 금지.

| 상황 | 스트림 | 정확한 문자열 |
|---|---|---|
| 마운트 없음(호스트) | stdout | `mount: n/a (host)` |
| 마운트 사망 | stdout | `mount: DEAD <resolved-path>` |
| 마운트 정상 | stdout | `mount: OK <resolved-path>` |
| git 정상 | stdout | `git: OK <sha40>` |
| git 사용 불가 | stdout | `git: n/a (<reason>)` |
| 락 청소 결과 | stderr | `locks: cleared=<N> kept=<M>` |
| 호스트에서 락 보존 | stderr | `locks: kept <path> (host policy; use --stale-after to purge)` |
| `--stale-after`로 삭제 | stderr | `locks: purged <path> (age=<S>s >= <N>s)` |
| run 예산 초과 | stderr | `BRIDGE_BUDGET_EXCEEDED <elapsed>s/<budget>s` |
| 자식 실행 실패 | stderr | `BRIDGE_EXEC_FAILED <errno-name> <exe>` |
| chunk 일시정지 | stdout | `CHUNK-PAUSED <done>/<total>` |
| chunk 완료 | stdout | `CHUNK-DONE <total>/<total>` |
| chunk 실패 존재 | stdout | `CHUNK-FAILED <failed>/<total>` |
| 리스트 지문 불일치 | stderr | `CHUNK-STATE-STALE expected=<sha8> found=<sha8>` |
| 상태파일 손상 | stderr | `CHUNK-STATE-CORRUPT line=<n>` |
| 재실행 미승인 | stderr | `CHUNK-RERUN-UNAPPROVED <n> item(s)` |
| 입력 계약 위반 | stderr | `CHUNK-INPUT-INVALID <reason>` |
| Remover 복사본 잔존 | 예외 메시지 | `move decomposed; leftover copy at <path>` |

**pytest 마커 금지.** `pyproject.toml`의 `addopts = "-ra --strict-markers -m 'not network'"` 때문에 미등록 마커는 즉시 에러다. 필요하면 `markers`에 등록하고 보고서에 명시.

## §B-1. `preflight` / `doctor` / `locks`

**`preflight` 출력 순서(F11 반영, 이 순서가 요구사항이다):**
1. 마운트 생존 — §B-0 문자열. `mount: DEAD`면 rc 2로 즉시 종료
2. git — **`rev-parse HEAD`로만 확인**(F11). 성공 시 `git: OK <sha40>`, 실패·부재 시 `git: n/a (<reason>)` (rc 영향 없음, Q7-5)
3. **락·orphan 청소** — git 프로브 **뒤에** 배치. 정책은 아래
4. 디스크 — 리포 FS와 스크립트가 도는 FS **둘 다**. 여유 < 2GB 또는 사용률 > 90%면 경고 라인
5. `_to_delete` 누적 크기

**락 정책(Q4 확정).**
- `is_bridge_mount(repo)` 참 → **나이 무관 무조건 청소**(F11: 마운트에선 모든 락이 항상 신선해 보인다).
- 거짓(호스트) → **기본은 보존 + 경고.** 장시간 실행 중인 정상 git 락을 훼손하지 않기 위함.
- `locks --stale-after N` → 호스트에서도 age ≥ N인 락만 삭제. 권장 문서값 600. **`--stale-after`는 `locks` 서브커맨드 전용**이며 `preflight`/`git`에는 없다.
- 안전성 한계를 `--help`와 CLAUDE.md에 명시: *"호스트에서 age 기반 삭제는 장시간 git 작업을 깰 수 있다."*

**`doctor`(Q7-10).** `preflight`의 모든 블록 + 환경 지문(플랫폼, `is_bridge_mount` 결과, 리포 파일 수·용량, FUSE 왕복 지연 샘플). **rc 계약은 `preflight`와 동일**(DEAD=2, 그 외 0). 진단 개별 실패는 해당 줄에 `n/a (<reason>)`로 표기하고 rc를 바꾸지 않는다.

**실패 테스트**
- `test_preflight_host_without_mount_returns_0` — rc 0 + `mount: n/a (host)` (INV-5)
- `test_preflight_dead_mount_returns_2` — rc 2 + `mount: DEAD …` (INV-5)
- `test_preflight_sweeps_after_git_probe` — 락을 남기는 가짜 git을 주입해도 종료 후 락 0개 (F11, §A-2 결함 4)
- `test_preflight_on_mount_clears_fresh_lock` / `test_preflight_on_host_keeps_lock` — Q4 분기
- `test_locks_stale_after_purges_only_old_on_host` — age 경계 검증(`time_fn` 주입)
- `test_preflight_without_git_returns_0_with_na_line` — git 부재여도 rc 0 + `git: n/a (…)` (Q7-5)
- `test_doctor_rc_matches_preflight_contract` (Q7-10)
- `test_is_bridge_mount_posix_and_windows_forms` — 구성요소 비교 검증 (Q7-3)

## §B-2. `Remover`

**실패 테스트**
- `test_remove_uses_unlink_when_allowed`
- `test_remove_falls_back_to_trash_when_unlink_forbidden` — 주입된 `unlink_fn`이 `PermissionError(errno.EPERM)` → `_to_delete/bridge_*/<상대경로>`로 이동 (INV-1, F5)
- `test_remove_preserves_relative_path_and_disambiguates_collisions` — 서로 다른 디렉터리의 동명 파일 2개가 덮어쓰지 않는다 (Q1 조건)
- `test_remove_never_escapes_repo_via_dotdot_or_absolute`
- `test_remove_never_escapes_repo_via_symlink` — Windows에서 링크 권한 없으면 `pytest.skip(사유 명시)`
- `test_remove_destination_must_be_inside_repo` — 조작된 `_to_delete` 경로 거부
- `test_remove_raises_and_names_leftover_copy_when_move_decomposes` — copy+unlink 분해 후 원본 unlink 실패 → 예외 + `leftover copy at …` (Q7-1)
- `test_remove_raises_when_move_also_denied` — Windows 잠긴 파일 시나리오 (Q7-2)

## §B-3. `git` 서브커맨드

**실패 테스트**(주입은 `runner_fn`, Q6 ②)
- `test_git_locks_cleared_even_when_git_fails` (INV-2)
- `test_git_locks_cleared_when_git_raises`
- `test_git_returncode_passes_through`
- `test_git_exec_missing_returns_127_with_marker` / `test_git_exec_oserror_returns_126_with_marker` (Q7-4)
- `test_git_does_not_capture_child_streams` — `runner_fn`이 `capture_output=False` + 상속 인자로 호출됨을 검증 (INV-2)
- `test_git_sweeper_report_goes_to_stderr_only` — `bridge_ops git rev-parse HEAD`의 stdout이 SHA 한 줄뿐

## §B-4. `run` (워치독)

`--budget` 기본 35(45초 벽에서 10초 헤드룸). 초과 시 자식 종료 → 주입된 `grace_s`(기본 3) 후 강제 종료 → rc 99 + §B-0 마커.

**프로세스 트리 종료(플랫폼별, 명시 요구).** POSIX = `start_new_session=True` + `os.killpg(SIGTERM)` → grace 후 `SIGKILL`. Windows = `CREATE_NEW_PROCESS_GROUP` + `Popen.terminate()`(= `TerminateProcess`) 또는 `taskkill /T /F`. **Windows에는 TERM→KILL 에스컬레이션이 없으므로 grace는 무시되며, 이 사실을 코드 주석과 보고서에 남긴다.**

**대기 경계 주입(Q7-9).** 예산 판정 루프는 `time_fn`과 함께 `waiter_fn`(프로세스 poll/wait 추상)을 주입받는다. 가짜 시간만 넣고 실제 `wait()`를 부르면 테스트가 멈춘다.

**실패 테스트**
- `test_run_budget_exceeded_returns_99_without_real_sleep` — `time_fn`·`grace_s=0`·`waiter_fn` 주입, 소요 1초 미만 (INV-3)
- `test_run_emits_marker_only_on_budget_kill` — 자식이 스스로 99로 끝나면 마커 없음
- `test_run_passes_through_child_rc`
- `test_run_exec_failures_map_to_126_127_with_marker` (Q7-4)
- `test_run_kills_child_process_group` — POSIX 전용, Windows는 `pytest.skip("no process-group semantics on Windows")`

## §B-5. `chunk` (재개형 배치)

**입력 계약(Q7-6).**
- 빈 줄·공백 전용 줄은 **항목이 아니며 조용히 스킵**(총계에도 포함하지 않음).
- **중복 항목은 거부** — rc 97 + `CHUNK-INPUT-INVALID duplicate item: <item>`. 신원 기반 멤버십과 양립하지 않는다.
- 템플릿에 `{}`가 **0개면 거부**(`CHUNK-INPUT-INVALID no {} placeholder`). 1개 이상이면 **모든 자리를 치환**한다.

**`--shell` 모드(Q7-8).** 항목 문자열을 명령에 **삽입하지 않는다.** `--shell`에서는 `{}` 사용을 금지하고(`CHUNK-INPUT-INVALID {} not allowed with --shell`), 항목을 환경변수 **`BRIDGE_ITEM`**으로 전달한다. 템플릿은 공백 재조립이 불가능하도록 `--command`의 **단일 인자**로 받고 `"$BRIDGE_ITEM"`을 참조한다. 이로써 주입 경로와 템플릿 변형을 차단한다.

**파일 IO.** 리스트·상태·`.failed` 전부 `encoding="utf-8", newline="\n"`(CLAUDE.md: *"Explicit `encoding='utf-8'` on every file IO (Windows cp949 guard)"*). 리스트 읽을 때 각 줄 후행 `\r` 제거. 상태 append는 줄 단위 `flush()` + `os.fsync()`.

**상태파일.** 지문 헤더 1줄 + 완료 항목들. 재개는 멤버십 판정. 손상 감지 시 rc 97(§A-3 INV-4, Q7-7). 실패 항목은 `<state>.failed`에 기록하되 **스킵 판단에 쓰지 않는다**(§A-6).

**종료.** `CHUNK-DONE`(0) / `CHUNK-PAUSED`(98) / `CHUNK-FAILED`(97) / 입력·상태 무효(97) / 재실행 미승인(97).

**실패 테스트**
- `test_chunk_resumes_by_identity_never_repeats` (INV-4)
- `test_chunk_failed_item_not_marked_done_and_retried_on_resume` — 중간 항목 rc=1일 때 그 항목만 재시도되고 **뒤 항목이 밀리지 않는다** (위치 기반 포팅 차단)
- `test_chunk_resume_requires_assume_idempotent_only_when_retrying_failures` — 실패 없는 재개는 플래그 없이 진행, 실패 재시도는 rc 97 (§A-6)
- `test_chunk_stale_list_fingerprint_refuses_resume`
- `test_chunk_corrupt_state_line_refuses` — 부분 행·잘못된 UTF-8 → rc 97 (Q7-7)
- `test_chunk_rejects_duplicate_items` / `test_chunk_skips_blank_lines` / `test_chunk_rejects_missing_placeholder` (Q7-6)
- `test_chunk_shell_mode_uses_env_not_substitution` — `;`·`&&`·백틱 포함 항목이 셸에서 실행되지 않음 (Q7-8)
- `test_chunk_state_roundtrips_nonascii_and_crlf` — 한글 항목 + CRLF 리스트(cp949 기본이면 실패해야 하는 테스트)
- `test_chunk_handles_paths_with_spaces_and_quotes`
- `test_chunk_pauses_on_budget_without_real_sleep` (INV-3)

## §B-6. 마무리

1. `scripts/bridge_ops.sh` → `_to_delete/`로 이동(삭제 아님, F5). **`tarball` 서브커맨드는 포팅하지 않는다**(§C). `locks`는 §A-1대로 포팅. 이 결정을 `.py` 헤더 주석에 명시.
2. `CLAUDE.md`의 "Device Bridge Limits" 절 명령 예시를 `.py` 호출로 갱신 + **F11 한 줄 추가**("인덱스를 건드리는 git은 마운트에서 매번 락을 남긴다 — 청소는 git 뒤에") + 호스트 락 정책 안전성 한계 1줄. §1 별건(MCP → `RefreshMcpTools`) 문구 유지.
3. `CLAUDE.md` §Verification에 `python -m pytest tests/test_bridge_ops.py -q` 추가.
4. 커밋 1개. 메시지 제안: `tools: add bridge_ops preflight/watchdog/chunk runner for device-bridge limits`.

## §B-7. 수용 기준

- [ ] `pytest -q` 전체 green. 기준선: 2026-08-12 `tests/` 55파일 · `def test_` 309개(`grep -rh "^def test_" tests/*.py | wc -l`). `pytest tests/test_bridge_ops.py -q` 단독도 green.
- [ ] **신규 테스트 파일 단독 소요 5초 미만**(INV-3의 관측 가능한 증거). 전체 스위트 시간은 대상 아님.
- [ ] 신규 의존성 0(stdlib 전용). `requirements.txt` 무변경. 신규 pytest 마커 0(또는 등록 사실 보고).
- [ ] Windows 호스트에서 브리지 없이 `preflight`·`doctor`·`run`·`chunk`·`locks` 5개 모두 의도한 rc로 완주(`preflight`/`doctor`는 0, `mount: n/a (host)`).
- [ ] INV-1~5 각각에 대응 테스트 ≥1개, **구현 전 빨간불이었음**을 보고서에 명시.
- [ ] §B-0 표의 모든 문자열이 코드에 리터럴로 존재하고, 최소 한 개 테스트가 각각을 어설션.
- [ ] **커밋에는 아래 경로만**: `scripts/bridge_ops.py`, `tests/test_bridge_ops.py`, `CLAUDE.md`, `HANDOFF_CODEX_bridge_ops_2026-08-12.md`, `_to_delete/`로 옮겨진 `.sh`의 삭제 반영. **리포에는 이 작업과 무관한 modified/untracked 파일이 다수 있다 — 건드리지 말 것.** `git add -A` 금지. 커밋 후 `git status --porcelain`에 기존 잔여물이 남는 것은 **정상**이며 실패 조건이 아니다.
- [ ] `_to_delete/`는 `.gitignore:50`에 이미 등재 — 확인만.

## §B-8. 규율

- 경로 명시 `git add`, **`git add -A` 금지**, 커밋별 `pytest -q` green, **서명 트레일러 금지**.
- 인접 코드 리팩터 금지 — `NOTICED BUT NOT TOUCHING: file:line 증상` 로그로 대체.
- 코드·주석·설정은 영어, 사용자 대면 출력만 한국어(CLAUDE.md Conventions). **§B-0의 고정 문자열은 영어이므로 그대로.**
- 이 작업은 앵커·FROZEN 산출물을 건드리지 않는다. G1 게이트 대상 아님(건드렸다면 그 자체가 결함이니 보고).
- 커밋은 **구현·검증 완료 후 범위 재확인**하고 실행한다(Codex 제안 수용).

## §B-9. 권장 착수 순서

`Remover` → `LockSweeper` → `preflight`/`locks`/`doctor` → `GitRunner` → `Budget`+`run` → `ChunkRunner`. 앞 세 단계만으로도 F6(3일 묵은 락) 재발이 막히므로, 중간에 중단되더라도 가치가 남는다.

---

# §C. 비목표 (구현 금지)

- **MCP 트랜스포트 단절 자동 복구.** `RefreshMcpTools`는 세션 측 동작. 문서 규율만.
- **형제 리포 배포·동기화** (§2).
- **git hook / 강제 래퍼** (§2).
- **FUSE 성능 최적화·캐시 계층·`tarball` 헬퍼.** F9/F10은 계측 상수일 뿐.
- **`_to_delete/` 자동 비우기.** 마운트에서 진짜 삭제는 불가능 — Windows 탐색기에서 사람이 지운다(현재 29MB).

---

# §D. 보고 형식

1. §A-6(Q3 수정안)에 대한 수용 또는 반증 — **구현 전에 답할 것**
2. 구현 diff 요약
3. `pytest tests/test_bridge_ops.py -q` 및 `pytest -q` 실행 로그(소요 시간 포함)
4. §B-7 체크리스트 결과
5. 커밋 전 범위 재확인 결과(포함 경로 목록)
