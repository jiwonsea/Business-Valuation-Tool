# REVIEW — `bridge_ops` rev-3 구현 검수 (2026-08-14)

**판정: REJECT — 수정 후 재검수.** 커밋 보류는 정확한 판단이었으나, 사유가 하나 더 있다. 기존 AMD SHA 실패와 무관하게 **구현 자체에 fail-closed를 무너뜨리는 확인된 결함이 4건** 있다.

**검수 방법.** 리눅스 컨테이너에 `scripts/bridge_ops.py` + `tests/test_bridge_ops.py` 사본을 올려 pytest 실행, CLI 직접 구동, 변이 주입(mutation)으로 테스트 유효성 확인. **아래 D1~D6은 전부 실제 실행으로 재현했다**(SPECULATIVE 표기된 것 제외).

**먼저, 확인된 것.** Remover 격리(`..`·절대경로·심볼릭 링크·`_to_delete` 자체를 밖으로 향하게 한 심링크까지 전부 차단), 신원 기반 재개(중간 실패 시 뒤 항목이 밀리지 않음), 지문 staleness(순서 민감 포함), §B-1 블록 순서(mount → `rev-parse` → 락 → 디스크 → trash), `--stale-after`의 `locks` 전용성, Q4 마운트/호스트 분기 — 전부 명세대로 동작한다. 설계 골격은 건전하다.

---

## D1 🚨 `--shell`이 **하지 않은 일을 완료로 기록한다** (INV-4 정면 위반)

`scripts/bridge_ops.py:456` — `runner_fn(" ".join(command), shell=True, ...)`

`--shell` 템플릿을 argparse `REMAINDER`로 받아 **공백으로 다시 이어붙인다.** 바깥 셸이 이미 따옴표를 벗겨냈으므로 원형 복원이 불가능하다. 결과적으로 명령이 변형되고, 변형된 명령이 대개 rc 0으로 끝나며, **항목은 완료로 상태파일에 기록된다.**

§B-5가 문서화한 바로 그 형태로 재현:

```
$ python scripts/bridge_ops.py --repo /tmp/p chunk --list L --state S --shell \
      -- sh -c 'echo "$BRIDGE_ITEM" > /tmp/p/out_$BRIDGE_ITEM.txt'
CHUNK-DONE 2/2        rc=0
$ cat S               → header + a + b      (둘 다 완료 기록)
$ cat /tmp/p/out_a.txt → (빈 파일)          ← 실제로는 아무것도 안 했다
```

이어붙인 문자열이 `sh -c echo "$BRIDGE_ITEM" > …`가 되어 안쪽 `sh`가 `echo`를 받고 항목은 `$0`로 밀린다. **`--shell`을 주입 위험 때문에 env 전달로 바꿨는데, 정작 템플릿 전달 경로에서 무결성이 깨졌다.**

`tests/test_bridge_ops.py:367`이 `calls[0][0] == 'echo "$BRIDGE_ITEM"'`를 어설션해 **살아남는 유일한 형태(한 단어짜리 argv)만 검증**하고 이 버그를 고착시킨다.

**수정:** 셸 템플릿을 **단일 인자**로 받는다 — `chunk --shell --command "<template>"`. 차선은 `shlex.join(command)` + 사용자 이중 따옴표 의무 문서화. 공백 join은 복구 불가능하므로 유지 금지.

## D2 🚨 POSIX 예산 킬이 rc 99 대신 트레이스백을 낸다

`scripts/bridge_ops.py:334,336` — `os.killpg(...)`에 `ProcessLookupError` 가드 없음.

`policy.wait()` 타임아웃과 `killpg` 사이에 자식이 스스로 종료하면 예외가 `run_command`를 뚫고 나가 rc 1 + **`BRIDGE_BUDGET_EXCEEDED` 마커 없음**이 된다. §A-5는 이 마커를 예산 킬의 **유일한 증거**로 규정했으므로, 호출자가 예산 초과를 영영 알 수 없다.

재현: 이미 종료된 프로세스 + `waiter_fn`이 `None` 반환 → `ProcessLookupError: [Errno 3] No such process`.

**수정:** 두 `killpg` 호출을 `try/except ProcessLookupError: pass`로 감싸고, `os.killpg(os.getpgid(process.pid), ...)`를 쓴다.

**연관 (D5-1):** 이 브랜치 전체가 테스트에서 도달 불가다. `test_run_budget_exceeded_returns_99_without_sleep`가 `bridge_ops.os.name = "nt"`로 **Windows 분기만** 태우기 때문이다. 그래서 ① 리눅스에서 이 테스트는 `AttributeError: module 'subprocess' has no attribute 'CREATE_NEW_PROCESS_GROUP'`로 **실패**하고(리눅스 실측 `1 failed, 26 passed`), ② **도구가 실제로 도는 플랫폼의 킬 경로가 통째로 미검증**이다. 이 도구는 리눅스 브리지 샌드박스에서 도는 게 존재 이유이므로 이 공백이 가장 크다.

## D3 🚨 첫 실행에 `--assume-idempotent`를 요구한다 — §A-6 계약 위반

`scripts/bridge_ops.py:434-445` — `existed`(:422 계산)를 게이트 판정에 쓰지 않는다.

§A-6은 **"최초 실행(상태파일 부재)에는 요구하지 않는다"**가 명문이다. 상태파일이 없어도 묵은 `<state>.failed`가 남아 있으면(사용자가 state만 지운 경우, 지문 STALE 후 리셋한 경우) 첫 실행이 막힌다.

재현: state 없음 + 묵은 `.failed` → `CHUNK-RERUN-UNAPPROVED 1 item(s)`, rc 97.

§A-6이 막으려던 "플래그가 의례가 된다"가 그대로 발생한다.

**수정:** `if existed and reruns and not assume_idempotent:` — 또는 `not existed`면 `.failed`를 아예 읽지 않는다.

## D4 `CHUNK-STATE-CORRUPT line=<n>`이 줄 번호가 아니라 바이트 오프셋을 찍는다

`scripts/bridge_ops.py:370` — `exc.start + 1`. `UnicodeDecodeError.start`는 버퍼 바이트 인덱스다.

재현: 3번째 줄에 잘못된 UTF-8 바이트 → `CHUNK-STATE-CORRUPT line=103`. §B-0이 리터럴로 고정한 필드가 거짓값을 낸다.

**수정:** 바이트로 먼저 읽고 `line = data[:exc.start].count(b"\n") + 1`.

**같은 결함 유형:** `bridge_ops.py:439`는 `<state>.failed`의 **모든** 문제(UTF-8·빈 줄·중복)에 `line=1`을 하드코딩한다. §B-0 리터럴 아래 조작된 값을 넣지 말 것.

## D5 변이 주입에서 살아남은 테스트 — 없는 것과 같은 검증 4건

| 위치 | 변이 | 결과 |
|---|---|---|
| `bridge_ops.py:98-101` | 이동 분해 감지 `if source.exists():` → `if False:` | **통과** — INV-1 핵심 보장이 미검증 라인 위에 있다 |
| `bridge_ops.py:192` | 디스크 경고 조건 → `if False:` | **통과** — §B-1 4번 블록 무검증 |
| `bridge_ops.py:202` | `trash: bytes=` 출력 삭제 | **통과** — §B-1 5번 블록 무검증 |
| `bridge_ops.py:236,243-244` | doctor의 platform·파일수·fuse-sample 출력 삭제 | **통과** — Q7-10 지문 전체 무검증 |

- `test_doctor_rc_matches_preflight_contract`(test:202)는 호스트 `tmp_path`에서 `rc == 0`만 본다. **이름이 주장하는 DEAD→2 분기를 건드리지 않는다.** → `doctor(dead_mount) == 2`를 추가하고 지문 4줄을 어설션할 것.
- `test_chunk_stale_and_corrupt_state_refuse`(test:328-331)는 부분 행 검사(`:380`)를 삭제해도 통과한다. 잘린 `"on"`이 멤버십 검사(`:383`)에 걸려 **같은 메시지**가 나기 때문. → 잘린 행이 **유효한 항목**이 되도록(`items=["one","onex"]`, 상태 행 `one` 무개행) 바꿔야 Q7-7의 두 절반이 분리 검증된다.
- `test_remove_disambiguates_collisions`(test:44)는 **같은 경로를 두 번** 지운다(`.1` 접미 확인). §Q1이 요구한 시나리오는 **서로 다른 디렉터리의 동명 파일**이다.

## D6 누락된 명세 테스트 — 26 구현 / 약 41~43 명세

위험 순:

| 누락 | 위험 |
|---|---|
| `test_run_kills_child_process_group` (§B-4) | **최상** — D2가 그 직접 결과 |
| `test_run_exec_failures_map_to_126_127_with_marker` (§B-4) | 상 — `run`의 마커 계약 무검증(현재 동작은 정상 확인: `127 … ENOENT`, `126 … EACCES`) |
| `test_git_sweeper_report_goes_to_stderr_only` (§B-3) | 상 — INV-2 stdout 투명성(=`git add -p`·`rev-parse` 파이핑) 검증 0 |
| `test_remove_raises_when_move_also_denied` (Q7-2) | 상 — Windows 잠긴 파일 경로(현재 동작 정상 확인) |
| `test_chunk_corrupt_state_line_refuses`의 UTF-8 절반 | 상 — D4를 가린다 |
| `test_preflight_on_mount_clears_fresh_lock` / `_on_host_keeps_lock` | 중 — 정책은 `LockSweeper` 단위로만 검증, `preflight`가 실제 술어에 배선됐는지 미검증 |
| `test_chunk_handles_paths_with_spaces_and_quotes` | 하 |
| 다중 `{}` 치환 | 하 (동작 정상 확인) |
| `flush()`+`os.fsync()` | 하 (`os.fsync` 제거해도 통과) |

## D7 경미

- `bridge_ops.py:525` — 인자 누락(자식 exec 실패가 아님)에 `BRIDGE_EXEC_FAILED EINVAL <missing>`를 찍는다. §A-5에서 이 마커는 **exec 시도 실패의 유일한 증거**여야 하므로 오염이다.
- `bridge_ops.py:427` — `CHUNK-INPUT-INVALID ` 접두 else 분기는 죽은 코드(`_read_state`는 STALE/CORRUPT만 던진다).
- `bridge_ops.py:142` — `collect()` 직후 무조건 `path.stat()`. 그 사이 호스트 git이 락을 치우면 `FileNotFoundError`가 `preflight`를 뚫는다. **SPECULATIVE**(미재현).

---

## 기존 실패에 대한 판단 — 이건 네 책임 아님

`tests/test_score_amd_scaffold.py`의 AMD FROZEN SHA 불일치는 **기존 미결 항목이 맞다**(세션 메모리 기록: "score_amd SHA 핀이 규약위반 해시로 고착"). `NOTICED BUT NOT TOUCHING` 처리는 규율대로다. **이 건으로 커밋을 막을 필요는 없다** — 아래 재정의된 기준을 쓴다.

## 수정된 §B-7 커밋 기준

- [ ] D1~D4 수정 완료
- [ ] D5의 4개 변이가 **모두 테스트를 빨갛게** 만든다(변이 주입 결과를 보고서에 첨부)
- [ ] D6의 "상" 등급 5건 테스트 추가
- [ ] **리눅스에서 `pytest tests/test_bridge_ops.py -q` green** — Windows만이 아니라. 이 도구의 주 실행 환경은 리눅스 브리지 샌드박스다. Windows 전용 분기는 `os.name` 전역 변조가 아니라 **주입 가능한 플랫폼 술어**로 분기하고, POSIX 경로를 실제로 태우는 테스트를 별도로 둔다
- [ ] 전체 `pytest -q`: **AMD SHA 1건 외 실패 0** (기준선 동일성만 확인, green 요구 철회)
- [ ] 커밋 경로 4개 유지

---

**보고 시 포함:** D1~D4 각각의 수정 diff, D5 변이 주입 재실행 결과, 리눅스·Windows **양쪽** pytest 로그.
