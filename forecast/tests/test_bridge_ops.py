from __future__ import annotations

import errno
import io
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bridge_ops  # noqa: E402


def test_is_bridge_mount_posix_and_windows_forms() -> None:
    assert bridge_ops.is_bridge_mount("/sessions/abc/mnt/repo")
    assert bridge_ops.is_bridge_mount(r"C:\sessions\abc\mnt\repo")
    assert bridge_ops.is_bridge_mount(r"\\?\C:\sessions\abc\mnt\repo")
    assert not bridge_ops.is_bridge_mount(r"F:\dev\repo")


def test_remove_uses_unlink_when_allowed(tmp_path: Path) -> None:
    target = tmp_path / "file.lock"
    target.write_text("", encoding="utf-8")
    assert bridge_ops.Remover(tmp_path).remove(target) is None
    assert not target.exists()


def test_remove_falls_back_and_preserves_relative_path(tmp_path: Path) -> None:
    target = tmp_path / ".git" / "refs" / "heads" / "main.lock"
    target.parent.mkdir(parents=True)
    target.write_text("", encoding="utf-8")

    def denied(_: Path) -> None:
        raise PermissionError(errno.EPERM, "denied")

    moved = bridge_ops.Remover(tmp_path, unlink_fn=denied, time_fn=lambda: 0).remove(target)
    assert moved is not None
    assert moved.relative_to(tmp_path).as_posix().endswith(".git/refs/heads/main.lock")
    assert not target.exists()


def test_remove_disambiguates_collisions(tmp_path: Path) -> None:
    first_target = tmp_path / "one" / "same.lock"
    second_target = tmp_path / "two" / "same.lock"
    first_target.parent.mkdir()
    second_target.parent.mkdir()
    first_target.write_text("one", encoding="utf-8")
    second_target.write_text("two", encoding="utf-8")

    def denied(_: Path) -> None:
        raise PermissionError(errno.EPERM, "denied")

    remover = bridge_ops.Remover(tmp_path, unlink_fn=denied, time_fn=lambda: 0)
    first = remover.remove(first_target)
    second = remover.remove(second_target)
    assert first != second
    assert first.name == second.name == "same.lock"
    assert first.read_text(encoding="utf-8") == "one"
    assert second.read_text(encoding="utf-8") == "two"


def test_remove_never_escapes_repo(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.lock"
    outside.write_text("safe", encoding="utf-8")
    with pytest.raises(ValueError, match="escapes repo"):
        bridge_ops.Remover(tmp_path).remove(outside)
    assert outside.read_text(encoding="utf-8") == "safe"


def test_remove_never_escapes_repo_via_symlink(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-symlink.lock"
    outside.write_text("safe", encoding="utf-8")
    link = tmp_path / "link.lock"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable on Windows: {exc}")
    with pytest.raises(ValueError, match="escapes repo"):
        bridge_ops.Remover(tmp_path).remove(link)
    assert outside.read_text(encoding="utf-8") == "safe"


def test_remove_destination_must_be_inside_repo(tmp_path: Path) -> None:
    target = tmp_path / "x.lock"
    target.write_text("", encoding="utf-8")

    def denied(_: Path) -> None:
        raise PermissionError(errno.EPERM, "denied")

    remover = bridge_ops.Remover(tmp_path, unlink_fn=denied, trash_root=tmp_path.parent / "trash")
    with pytest.raises(ValueError, match="destination escapes"):
        remover.remove(target)


def test_remove_raises_and_names_leftover_copy(tmp_path: Path) -> None:
    target = tmp_path / "x.lock"
    target.write_text("", encoding="utf-8")

    def denied(_: Path) -> None:
        raise PermissionError(errno.EPERM, "denied")

    def decomposed(source: Path, destination: Path) -> None:
        destination.write_bytes(source.read_bytes())
        raise PermissionError(errno.EPERM, "source unlink denied")

    with pytest.raises(OSError, match="move decomposed; leftover copy at"):
        bridge_ops.Remover(tmp_path, unlink_fn=denied, move_fn=decomposed).remove(target)


def test_remove_detects_move_returning_with_source_and_copy(tmp_path: Path) -> None:
    target = tmp_path / "x.lock"
    target.write_text("data", encoding="utf-8")

    def denied(_: Path) -> None:
        raise PermissionError(errno.EPERM, "denied")

    def false_success(source: Path, destination: Path) -> None:
        destination.write_bytes(source.read_bytes())

    with pytest.raises(OSError, match="move decomposed; leftover copy at"):
        bridge_ops.Remover(tmp_path, unlink_fn=denied, move_fn=false_success).remove(target)


def test_remove_raises_when_move_also_denied(tmp_path: Path) -> None:
    target = tmp_path / "locked.lock"
    target.write_text("", encoding="utf-8")

    def denied(*args: object) -> None:
        raise PermissionError(errno.EACCES, "locked")

    with pytest.raises(PermissionError):
        bridge_ops.Remover(tmp_path, unlink_fn=denied, move_fn=denied).remove(target)


def _lock(repo: Path, name: str = "index.lock") -> Path:
    path = repo / ".git" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")
    return path


def test_lock_sweeper_mount_clears_fresh_lock(tmp_path: Path) -> None:
    target = _lock(tmp_path)
    err = io.StringIO()
    bridge_ops.LockSweeper(tmp_path, stderr=err, is_mount_fn=lambda _: True).sweep()
    assert not target.exists()
    assert "locks: cleared=1 kept=0" in err.getvalue()


def test_lock_sweeper_host_keeps_lock(tmp_path: Path) -> None:
    target = _lock(tmp_path)
    err = io.StringIO()
    bridge_ops.LockSweeper(tmp_path, stderr=err).sweep()
    assert target.exists()
    assert "host policy; use --stale-after to purge" in err.getvalue()


def test_locks_stale_after_purges_only_old_on_host(tmp_path: Path) -> None:
    old = _lock(tmp_path, "index.lock")
    fresh = _lock(tmp_path, "HEAD.lock")
    os.utime(old, (0, 0))
    os.utime(fresh, (950, 950))
    err = io.StringIO()
    bridge_ops.LockSweeper(tmp_path, time_fn=lambda: 1000, stderr=err).sweep(100)
    assert not old.exists()
    assert fresh.exists()
    assert f"locks: purged {old} (age=1000s >= 100s)" in err.getvalue()


def test_preflight_host_without_mount_and_git_returns_0(tmp_path: Path) -> None:
    out = io.StringIO()

    def missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError(errno.ENOENT, "missing")

    rc = bridge_ops.preflight(tmp_path, runner_fn=missing, stdout=out, stderr=io.StringIO())
    assert rc == 0
    assert out.getvalue().splitlines()[:2] == ["mount: n/a (host)", "git: n/a (git unavailable)"]


def test_preflight_dead_mount_returns_2() -> None:
    path = Path("/sessions/bridge-test/mnt/dead").resolve()
    out = io.StringIO()
    rc = bridge_ops.preflight(path, stdout=out, stderr=io.StringIO())
    assert rc == 2
    assert out.getvalue().strip() == f"mount: DEAD {path}"


def test_preflight_live_mount_reports_ok(tmp_path: Path) -> None:
    repo = tmp_path / "sessions" / "bridge" / "mnt" / "repo"
    repo.mkdir(parents=True)
    out = io.StringIO()
    rc = bridge_ops.preflight(
        repo,
        runner_fn=lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no HEAD"),
        stdout=out,
        stderr=io.StringIO(),
    )
    assert rc == 0
    assert out.getvalue().splitlines()[0] == f"mount: OK {repo.resolve()}"


def test_preflight_sweeps_after_git_probe(tmp_path: Path) -> None:
    events: list[str] = []
    out = io.StringIO()

    def runner(*args: object, **kwargs: object) -> object:
        events.append("git")
        _lock(tmp_path)
        return SimpleNamespace(returncode=0, stdout="a" * 40, stderr="")

    class Sweeper(bridge_ops.LockSweeper):
        def sweep(self, stale_after: float | None = None) -> tuple[int, int]:
            events.append("sweep")
            return super().sweep(stale_after)

    def factory(repo: Path, stderr: io.StringIO) -> Sweeper:
        return Sweeper(repo, stderr=stderr, is_mount_fn=lambda _: True)

    rc = bridge_ops.preflight(
        tmp_path, runner_fn=runner, stdout=out, stderr=io.StringIO(), sweeper_factory=factory
    )
    assert rc == 0
    assert events == ["git", "sweep"]
    assert not (tmp_path / ".git" / "index.lock").exists()
    assert f"git: OK {'a' * 40}" in out.getvalue()


def test_doctor_rc_matches_preflight_contract(tmp_path: Path) -> None:
    out = io.StringIO()
    rc = bridge_ops.doctor(
        tmp_path,
        runner_fn=lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no HEAD"),
        stdout=out,
        stderr=io.StringIO(),
    )
    assert rc == 0
    text = out.getvalue()
    assert "platform: " in text
    assert "bridge-mount: False" in text
    assert "repo: files=" in text
    assert "fuse-sample: " in text

    dead = (tmp_path / "sessions" / "bridge" / "mnt" / "missing").resolve()
    dead_out = io.StringIO()
    assert bridge_ops.doctor(dead, stdout=dead_out, stderr=io.StringIO()) == 2
    assert dead_out.getvalue().strip() == f"mount: DEAD {dead}"


def test_disk_warning_and_trash_size_blocks(tmp_path: Path) -> None:
    out = io.StringIO()
    usage = SimpleNamespace(total=100, used=95, free=1)
    bridge_ops._disk_lines(tmp_path, out, disk_usage_fn=lambda _: usage)
    assert out.getvalue().count("WARNING low space") == 2
    trash = tmp_path / "_to_delete" / "file"
    trash.parent.mkdir()
    trash.write_bytes(b"123")
    out = io.StringIO()
    bridge_ops._trash_size(tmp_path, out)
    assert out.getvalue().strip() == "trash: bytes=3"


class RecordingSweeper:
    def __init__(self) -> None:
        self.calls = 0

    def sweep(self) -> tuple[int, int]:
        self.calls += 1
        return 0, 0


def test_git_contract_and_finally_cleanup(tmp_path: Path) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    sweeper = RecordingSweeper()

    def runner(argv: object, **kwargs: object) -> object:
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=7)

    rc = bridge_ops.GitRunner(tmp_path, runner, sweeper).run(["status"])
    assert rc == 7
    assert sweeper.calls == 1
    assert calls[0][1]["capture_output"] is False
    assert calls[0][1]["stdout"] is None and calls[0][1]["stderr"] is None


def test_git_sweeper_report_goes_to_stderr_only(tmp_path: Path) -> None:
    out = io.StringIO()
    err = io.StringIO()

    def runner(*args: object, **kwargs: object) -> object:
        print("a" * 40, file=out)
        return SimpleNamespace(returncode=0)

    bridge_ops.GitRunner(tmp_path, runner_fn=runner, stderr=err).run(["rev-parse", "HEAD"])
    assert out.getvalue() == "a" * 40 + "\n"
    assert err.getvalue() == "locks: cleared=0 kept=0\n"


@pytest.mark.parametrize(
    ("exc", "expected"),
    [(FileNotFoundError(errno.ENOENT, "missing"), 127), (PermissionError(errno.EACCES, "denied"), 126)],
)
def test_git_exec_failures_map_and_cleanup(tmp_path: Path, exc: OSError, expected: int) -> None:
    sweeper = RecordingSweeper()
    err = io.StringIO()

    def runner(*args: object, **kwargs: object) -> object:
        raise exc

    assert bridge_ops.GitRunner(tmp_path, runner, sweeper, err).run([]) == expected
    expected_name = "ENOENT" if expected == 127 else "EACCES"
    assert err.getvalue().strip() == f"BRIDGE_EXEC_FAILED {expected_name} git"
    assert sweeper.calls == 1


class FakeProcess:
    pid = 123

    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        return 0


def test_run_budget_exceeded_returns_99_without_sleep() -> None:
    process = FakeProcess()
    times = iter([0.0, 35.0])
    policy = bridge_ops.Budget(time_fn=lambda: next(times), grace_s=0, waiter_fn=lambda p, t: None)
    err = io.StringIO()
    rc = bridge_ops.run_command(
        ["fake"], 35, policy, lambda *a, **k: process, err, platform_name="nt"
    )
    assert rc == 99
    assert process.terminated
    assert err.getvalue().strip() == "BRIDGE_BUDGET_EXCEEDED 35s/35s"


def test_run_child_99_has_no_budget_marker() -> None:
    process = FakeProcess()
    policy = bridge_ops.Budget(waiter_fn=lambda p, t: 99)
    err = io.StringIO()
    assert bridge_ops.run_command(["fake"], budget=policy, popen_fn=lambda *a, **k: process, stderr=err) == 99
    assert err.getvalue() == ""


@pytest.mark.parametrize(
    ("exc", "expected", "name"),
    [
        (FileNotFoundError(errno.ENOENT, "missing"), 127, "ENOENT"),
        (PermissionError(errno.EACCES, "denied"), 126, "EACCES"),
    ],
)
def test_run_exec_failures_map_to_126_127_with_marker(
    exc: OSError, expected: int, name: str
) -> None:
    err = io.StringIO()

    def popen(*args: object, **kwargs: object) -> object:
        raise exc

    assert bridge_ops.run_command(["missing"], popen_fn=popen, stderr=err) == expected
    assert err.getvalue().strip() == f"BRIDGE_EXEC_FAILED {name} missing"


def test_run_posix_process_lookup_race_still_returns_99() -> None:
    process = FakeProcess()
    times = iter([0.0, 1.0])
    policy = bridge_ops.Budget(time_fn=lambda: next(times), waiter_fn=lambda p, t: None)
    err = io.StringIO()

    def vanished(_: int) -> int:
        raise ProcessLookupError

    rc = bridge_ops.run_command(
        ["fake"], 1, policy, lambda *a, **k: process, err,
        platform_name="posix", getpgid_fn=vanished
    )
    assert rc == 99
    assert err.getvalue().strip() == "BRIDGE_BUDGET_EXCEEDED 1s/1s"


def test_run_posix_escalates_process_group_without_platform_mutation() -> None:
    process = FakeProcess()
    times = iter([0.0, 1.0])
    waits = iter([None, None])
    policy = bridge_ops.Budget(
        time_fn=lambda: next(times), grace_s=0, waiter_fn=lambda p, t: next(waits)
    )
    signals: list[tuple[int, int]] = []
    popen_kwargs: dict[str, object] = {}

    def popen(*args: object, **kwargs: object) -> FakeProcess:
        popen_kwargs.update(kwargs)
        return process

    rc = bridge_ops.run_command(
        ["fake"], 1, policy, popen, io.StringIO(),
        platform_name="posix", getpgid_fn=lambda _: 456,
        killpg_fn=lambda group, sig: signals.append((group, sig)),
    )
    assert rc == 99
    assert popen_kwargs == {"start_new_session": True}
    assert signals == [(456, bridge_ops.signal.SIGTERM), (456, bridge_ops.POSIX_SIGKILL)]


def test_run_kills_child_process_group() -> None:
    if os.name == "nt":
        pytest.skip("no process-group semantics on Windows")
    err = io.StringIO()
    rc = bridge_ops.run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        budget_s=0.05,
        budget=bridge_ops.Budget(grace_s=0),
        stderr=err,
        platform_name="posix",
    )
    assert rc == 99
    assert "BRIDGE_BUDGET_EXCEEDED" in err.getvalue()


def _write_list(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def test_chunk_resumes_by_identity_and_retries_only_failure(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    state = tmp_path / "state.txt"
    _write_list(items, ["one", "two", "three"])
    seen: list[str] = []

    def first(argv: list[str], **kwargs: object) -> object:
        seen.append(argv[-1])
        return SimpleNamespace(returncode=1 if argv[-1] == "two" else 0)

    first_out = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], runner_fn=first, stdout=first_out) == 97
    assert first_out.getvalue().strip() == "CHUNK-FAILED 1/3"
    assert seen == ["one", "two", "three"]
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], runner_fn=first, stderr=err) == 97
    assert "CHUNK-RERUN-UNAPPROVED 1 item(s)" in err.getvalue()
    seen.clear()
    assert bridge_ops.run_chunk(
        items, state, ["cmd", "{}"], runner_fn=lambda argv, **k: (seen.append(argv[-1]) or SimpleNamespace(returncode=0)),
        assume_idempotent=True, stdout=io.StringIO()
    ) == 0
    assert seen == ["two"]


def test_chunk_fresh_state_ignores_stale_failed_file(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    state = tmp_path / "state"
    _write_list(items, ["one"])
    Path(f"{state}.failed").write_text("one\n", encoding="utf-8", newline="\n")
    out = io.StringIO()
    assert bridge_ops.run_chunk(
        items,
        state,
        ["cmd", "{}"],
        runner_fn=lambda *a, **k: SimpleNamespace(returncode=0),
        stdout=out,
    ) == 0
    assert out.getvalue().strip() == "CHUNK-DONE 1/1"


def test_chunk_stale_and_corrupt_state_refuse(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    state = tmp_path / "state.txt"
    _write_list(items, ["one"])
    state.write_text("# bridge_ops v1 items=1 sha256=" + "0" * 64 + "\n", encoding="utf-8")
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], stderr=err) == 97
    assert "CHUNK-STATE-STALE" in err.getvalue()
    _write_list(items, ["one", "onex"])
    header, _ = bridge_ops._fingerprint(["one", "onex"])
    state.write_bytes((header + "\none").encode("utf-8"))
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], stderr=err) == 97
    assert "CHUNK-STATE-CORRUPT line=2" in err.getvalue()

    state.write_bytes((header + "\none\n" + "x" * 20).encode("utf-8") + b"\xff\n")
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], stderr=err) == 97
    assert err.getvalue().strip() == "CHUNK-STATE-CORRUPT line=3"


def test_chunk_corrupt_failed_file_reports_real_line(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    state = tmp_path / "state"
    _write_list(items, ["one", "two"])
    header, _ = bridge_ops._fingerprint(["one", "two"])
    state.write_text(header + "\n", encoding="utf-8", newline="\n")
    Path(f"{state}.failed").write_bytes(b"one\ninvalid-" + b"\xff\n")
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], stderr=err) == 97
    assert err.getvalue().strip() == "CHUNK-STATE-CORRUPT line=2"


def test_chunk_input_contract_and_blank_lines(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    state = tmp_path / "state.txt"
    _write_list(items, ["", "한글", "  "])
    out = io.StringIO()
    assert bridge_ops.run_chunk(
        items, state, ["cmd", "{}"], runner_fn=lambda *a, **k: SimpleNamespace(returncode=0), stdout=out
    ) == 0
    assert "CHUNK-DONE 1/1" in out.getvalue()
    _write_list(items, ["dup", "dup"])
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, tmp_path / "other", ["cmd", "{}"], stderr=err) == 97
    assert "CHUNK-INPUT-INVALID duplicate item: dup" in err.getvalue()

    _write_list(items, ["one"])
    err = io.StringIO()
    assert bridge_ops.run_chunk(items, tmp_path / "third", ["cmd"], stderr=err) == 97
    assert err.getvalue().strip() == "CHUNK-INPUT-INVALID no {} placeholder"


def test_chunk_shell_mode_uses_environment(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    _write_list(items, ["x; echo BAD && `bad`"])
    calls: list[tuple[str, dict[str, object]]] = []

    def runner(command: str, **kwargs: object) -> object:
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0)

    assert bridge_ops.run_chunk(
        items, tmp_path / "state", ['echo "$BRIDGE_ITEM"'], shell=True,
        runner_fn=runner, stdout=io.StringIO()
    ) == 0
    assert calls[0][0] == 'echo "$BRIDGE_ITEM"'
    assert calls[0][1]["env"]["BRIDGE_ITEM"] == "x; echo BAD && `bad`"
    err = io.StringIO()
    assert bridge_ops.run_chunk(
        items, tmp_path / "other", ["echo {}"], shell=True, stderr=err
    ) == 97
    assert err.getvalue().strip() == "CHUNK-INPUT-INVALID {} not allowed with --shell"


def test_chunk_shell_cli_parser_preserves_one_template() -> None:
    template = 'sh -c \'echo "$BRIDGE_ITEM" > "out_$BRIDGE_ITEM.txt"\''
    args = bridge_ops.build_parser().parse_args(
        [
            "chunk", "--list", "items", "--state", "state",
            "--shell", "--command", template,
        ]
    )
    assert args.shell_command == template
    assert args.command == []


def test_chunk_state_roundtrips_nonascii_and_crlf(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    items.write_bytes("한글 항목\r\npath with 'quotes'\r\n".encode())
    state = tmp_path / "state"
    seen: list[str] = []

    def runner(argv: list[str], **kwargs: object) -> object:
        seen.append(argv[-1])
        return SimpleNamespace(returncode=0)

    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], runner_fn=runner, stdout=io.StringIO()) == 0
    assert seen == ["한글 항목", "path with 'quotes'"]
    seen.clear()
    assert bridge_ops.run_chunk(items, state, ["cmd", "{}"], runner_fn=runner, stdout=io.StringIO()) == 0
    assert seen == []


def test_chunk_pauses_without_sleep(tmp_path: Path) -> None:
    items = tmp_path / "items.txt"
    _write_list(items, ["one"])
    out = io.StringIO()
    times = iter([0, 2])
    assert bridge_ops.run_chunk(
        items, tmp_path / "state", ["cmd", "{}"], budget_s=1,
        time_fn=lambda: next(times), stdout=out
    ) == 98
    assert out.getvalue().strip() == "CHUNK-PAUSED 0/1"
