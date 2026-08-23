"""Defensive helpers for the short-lived device bridge.

The former shell prototype's tarball command is intentionally not ported.
"""

from __future__ import annotations

import argparse
import errno
import hashlib
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import TextIO

EXEC_FAILED = "BRIDGE_EXEC_FAILED"
WINDOWS_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
POSIX_SIGKILL = getattr(signal, "SIGKILL", 9)


def _getpgid(pid: int) -> int:
    return os.getpgid(pid)


def _killpg(process_group: int, sig: int) -> None:
    os.killpg(process_group, sig)


def is_bridge_mount(path: Path | str) -> bool:
    """Return whether a path has the device bridge mount shape."""
    raw = str(path).replace("\\\\?\\", "")
    candidates = (PurePosixPath(raw.replace("\\", "/")).parts, PureWindowsPath(raw).parts)
    for parts in candidates:
        lowered = [part.lower().rstrip(":") for part in parts]
        try:
            index = lowered.index("sessions")
        except ValueError:
            continue
        if index + 3 < len(parts) and lowered[index + 2] == "mnt":
            return True
    return False


def _inside(path: Path, repo: Path) -> bool:
    try:
        path.resolve().relative_to(repo.resolve())
    except ValueError:
        return False
    return True


class Remover:
    """Remove repo-local files, falling back to a repo-local trash directory."""

    def __init__(
        self,
        repo: Path,
        unlink_fn: Callable[[Path], None] | None = None,
        move_fn: Callable[[Path, Path], object] | None = None,
        time_fn: Callable[[], float] = time.time,
        trash_root: Path | None = None,
    ) -> None:
        self.repo = repo.resolve()
        self.unlink_fn = unlink_fn or (lambda path: path.unlink())
        self.move_fn = move_fn or shutil.move
        self.time_fn = time_fn
        self.trash_root = trash_root

    def remove(self, path: Path) -> Path | None:
        """Remove a file or move it to trash when unlink is forbidden."""
        source = Path(path)
        resolved = source.resolve()
        if not _inside(resolved, self.repo):
            raise ValueError(f"path escapes repo: {source}")
        try:
            self.unlink_fn(source)
            return None
        except OSError as exc:
            if not isinstance(exc, PermissionError) and exc.errno != errno.EPERM:
                raise

        relative = resolved.relative_to(self.repo)
        root = self.trash_root or (
            self.repo / "_to_delete" / time.strftime("bridge_%Y%m%d", time.localtime(self.time_fn()))
        )
        destination = root / relative
        if not _inside(destination, self.repo):
            raise ValueError(f"trash destination escapes repo: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        candidate = destination
        suffix = 1
        while candidate.exists():
            candidate = destination.with_name(f"{destination.name}.{suffix}")
            suffix += 1
        try:
            self.move_fn(source, candidate)
        except Exception as exc:
            if candidate.exists() and source.exists():
                raise OSError(f"move decomposed; leftover copy at {candidate}") from exc
            raise
        if source.exists():
            if candidate.exists():
                raise OSError(f"move decomposed; leftover copy at {candidate}")
            raise OSError(f"move did not remove source: {source}")
        return candidate


class LockSweeper:
    """Collect and remove git locks according to host or bridge policy."""

    def __init__(
        self,
        repo: Path,
        remover: Remover | None = None,
        time_fn: Callable[[], float] = time.time,
        stderr: TextIO = sys.stderr,
        is_mount_fn: Callable[[Path | str], bool] = is_bridge_mount,
    ) -> None:
        self.repo = repo.resolve()
        self.remover = remover or Remover(self.repo, time_fn=time_fn)
        self.time_fn = time_fn
        self.stderr = stderr
        self.is_mount_fn = is_mount_fn

    def collect(self) -> list[Path]:
        git = self.repo / ".git"
        paths = [git / name for name in ("index.lock", "HEAD.lock", "config.lock")]
        paths.append(git / "objects" / "maintenance.lock")
        paths.extend((git / "refs" / "heads").glob("**/*.lock"))
        paths.extend((git / "objects").glob("**/tmp_obj_*"))
        return sorted({path for path in paths if path.exists()}, key=str)

    def sweep(self, stale_after: float | None = None) -> tuple[int, int]:
        cleared = 0
        kept = 0
        mounted = self.is_mount_fn(self.repo)
        for path in self.collect():
            if not mounted and stale_after is None:
                print(
                    f"locks: kept {path} (host policy; use --stale-after to purge)",
                    file=self.stderr,
                )
                kept += 1
                continue
            try:
                age = max(0, int(self.time_fn() - path.stat().st_mtime))
            except FileNotFoundError:
                continue
            if not mounted and age < stale_after:
                kept += 1
                continue
            self.remover.remove(path)
            cleared += 1
            if not mounted:
                print(
                    f"locks: purged {path} (age={age}s >= {int(stale_after)}s)",
                    file=self.stderr,
                )
        print(f"locks: cleared={cleared} kept={kept}", file=self.stderr)
        return cleared, kept


def _mount_line(repo: Path, stdout: TextIO) -> int:
    mounted = is_bridge_mount(repo)
    if mounted and not repo.exists():
        print(f"mount: DEAD {repo}", file=stdout)
        return 2
    if mounted:
        print(f"mount: OK {repo}", file=stdout)
    else:
        print("mount: n/a (host)", file=stdout)
    return 0


def _git_probe(repo: Path, runner_fn: Callable[..., object], stdout: TextIO) -> None:
    try:
        result = runner_fn(
            ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=False
        )
        sha = str(getattr(result, "stdout", "")).strip()
        if getattr(result, "returncode", 1) == 0 and len(sha) == 40:
            print(f"git: OK {sha}", file=stdout)
        else:
            reason = str(getattr(result, "stderr", "")).strip() or "HEAD unavailable"
            print(f"git: n/a ({reason})", file=stdout)
    except FileNotFoundError:
        print("git: n/a (git unavailable)", file=stdout)
    except OSError as exc:
        print(f"git: n/a ({exc})", file=stdout)


def _disk_lines(
    repo: Path,
    stdout: TextIO,
    disk_usage_fn: Callable[[Path], object] = shutil.disk_usage,
) -> None:
    for label, path in (("repo", repo), ("runtime", Path(__file__).resolve().parent)):
        try:
            usage = disk_usage_fn(path)
            percent = int(100 * usage.used / usage.total) if usage.total else 0
            print(f"disk {label}: free={usage.free} used={percent}%", file=stdout)
            if usage.free < 2 * 1024**3 or percent > 90:
                print(f"disk {label}: WARNING low space", file=stdout)
        except OSError as exc:
            print(f"disk {label}: n/a ({exc})", file=stdout)


def _trash_size(repo: Path, stdout: TextIO) -> None:
    root = repo / "_to_delete"
    try:
        size = sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) if root.exists() else 0
        print(f"trash: bytes={size}", file=stdout)
    except OSError as exc:
        print(f"trash: n/a ({exc})", file=stdout)


def preflight(
    repo: Path,
    runner_fn: Callable[..., object] = subprocess.run,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    sweeper_factory: Callable[..., LockSweeper] = LockSweeper,
) -> int:
    """Run the ordered bridge health checks."""
    repo = repo.resolve()
    rc = _mount_line(repo, stdout)
    if rc:
        return rc
    _git_probe(repo, runner_fn, stdout)
    sweeper_factory(repo, stderr=stderr).sweep()
    _disk_lines(repo, stdout)
    _trash_size(repo, stdout)
    return 0


def doctor(
    repo: Path,
    runner_fn: Callable[..., object] = subprocess.run,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run preflight plus a best-effort environment fingerprint."""
    rc = preflight(repo, runner_fn, stdout, stderr)
    if rc:
        return rc
    print(f"platform: {platform.platform()}", file=stdout)
    print(f"bridge-mount: {is_bridge_mount(repo)}", file=stdout)
    try:
        started = time.perf_counter()
        files = [path for path in repo.rglob("*") if path.is_file()]
        size = sum(path.stat().st_size for path in files)
        latency = time.perf_counter() - started
        print(f"repo: files={len(files)} bytes={size}", file=stdout)
        print(f"fuse-sample: {latency:.6f}s", file=stdout)
    except OSError as exc:
        print(f"repo: n/a ({exc})", file=stdout)
        print(f"fuse-sample: n/a ({exc})", file=stdout)
    return 0


def _exec_error(exc: OSError, exe: str, stderr: TextIO) -> int:
    name = errno.errorcode.get(exc.errno or 0, type(exc).__name__)
    print(f"{EXEC_FAILED} {name} {exe}", file=stderr)
    return 127 if isinstance(exc, FileNotFoundError) else 126


class GitRunner:
    """Run git transparently and always sweep locks afterward."""

    def __init__(
        self,
        repo: Path,
        runner_fn: Callable[..., object] = subprocess.run,
        sweeper: LockSweeper | None = None,
        stderr: TextIO = sys.stderr,
    ) -> None:
        self.repo = repo.resolve()
        self.runner_fn = runner_fn
        self.sweeper = sweeper or LockSweeper(self.repo, stderr=stderr)
        self.stderr = stderr

    def run(self, args: Sequence[str]) -> int:
        try:
            result = self.runner_fn(
                ["git", *args],
                cwd=self.repo,
                capture_output=False,
                stdin=None,
                stdout=None,
                stderr=None,
                check=False,
            )
            return int(result.returncode)
        except OSError as exc:
            return _exec_error(exc, "git", self.stderr)
        finally:
            self.sweeper.sweep()


@dataclass
class Budget:
    """Injectable watchdog timing policy."""

    time_fn: Callable[[], float] = time.monotonic
    grace_s: float = 3.0
    waiter_fn: Callable[[subprocess.Popen[object], float], int | None] | None = None

    def wait(self, process: subprocess.Popen[object], timeout: float) -> int | None:
        if self.waiter_fn:
            return self.waiter_fn(process, timeout)
        try:
            return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return None


def run_command(
    command: Sequence[str],
    budget_s: float = 35,
    budget: Budget | None = None,
    popen_fn: Callable[..., subprocess.Popen[object]] = subprocess.Popen,
    stderr: TextIO = sys.stderr,
    platform_name: str = os.name,
    getpgid_fn: Callable[[int], int] = _getpgid,
    killpg_fn: Callable[[int, int], None] = _killpg,
) -> int:
    """Run a command with a hard bridge-aware budget."""
    policy = budget or Budget()
    kwargs: dict[str, object] = {}
    if platform_name == "nt":
        kwargs["creationflags"] = WINDOWS_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        process = popen_fn(list(command), **kwargs)
    except OSError as exc:
        return _exec_error(exc, command[0], stderr)
    started = policy.time_fn()
    rc = policy.wait(process, budget_s)
    if rc is not None:
        return int(rc)
    elapsed = max(0.0, policy.time_fn() - started)
    if platform_name == "nt":
        # Windows has no TERM-to-KILL escalation; terminate is immediate and grace is ignored.
        process.terminate()
    else:
        try:
            process_group = getpgid_fn(process.pid)
            killpg_fn(process_group, signal.SIGTERM)
        except ProcessLookupError:
            process_group = None
        if policy.wait(process, policy.grace_s) is None and process_group is not None:
            try:
                killpg_fn(process_group, POSIX_SIGKILL)
            except ProcessLookupError:
                pass
    process.wait()
    print(f"BRIDGE_BUDGET_EXCEEDED {elapsed:g}s/{budget_s:g}s", file=stderr)
    return 99


class ChunkError(Exception):
    """A chunk input or state contract violation."""


def _decode_lines(path: Path) -> list[str]:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        line = data[: exc.start].count(b"\n") + 1
        raise ChunkError(f"CORRUPT line={line}") from exc
    return text.splitlines(keepends=True)


def _fingerprint(items: list[str]) -> tuple[str, str]:
    digest = hashlib.sha256("\n".join(items).encode("utf-8")).hexdigest()
    return f"# bridge_ops v1 items={len(items)} sha256={digest}", digest


def _read_items(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        items = [line.rstrip("\n").rstrip("\r") for line in handle]
    items = [item for item in items if item.strip()]
    seen: set[str] = set()
    for item in items:
        if item in seen:
            raise ChunkError(f"duplicate item: {item}")
        seen.add(item)
    return items


def _read_state(path: Path, header: str, digest: str, items: set[str]) -> set[str]:
    if not path.exists():
        return set()
    lines = _decode_lines(path)
    if not lines or not lines[0].endswith("\n"):
        raise ChunkError("CORRUPT line=1")
    found = lines[0].strip()
    if found != header:
        found_hash = found.split("sha256=")[-1][:8] if "sha256=" in found else "invalid"
        raise ChunkError(f"STALE expected={digest[:8]} found={found_hash}")
    completed: set[str] = set()
    for number, line in enumerate(lines[1:], 2):
        if not line.endswith("\n"):
            raise ChunkError(f"CORRUPT line={number}")
        item = line[:-1]
        if not item or item not in items or item in completed:
            raise ChunkError(f"CORRUPT line={number}")
        completed.add(item)
    return completed


def _read_failed(path: Path, items: set[str]) -> set[str]:
    lines = _decode_lines(path)
    failed: set[str] = set()
    for number, line in enumerate(lines, 1):
        if not line.endswith("\n"):
            raise ChunkError(f"CORRUPT line={number}")
        item = line[:-1]
        if not item or item not in items or item in failed:
            raise ChunkError(f"CORRUPT line={number}")
        failed.add(item)
    return failed


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{line}\n")
        handle.flush()
        os.fsync(handle.fileno())


def _truncate(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.flush()
        os.fsync(handle.fileno())


def run_chunk(
    list_path: Path,
    state_path: Path,
    command: Sequence[str],
    *,
    shell: bool = False,
    assume_idempotent: bool = False,
    budget_s: float = 35,
    runner_fn: Callable[..., object] = subprocess.run,
    time_fn: Callable[[], float] = time.monotonic,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    """Run resumable identity-based chunks."""
    try:
        items = _read_items(list_path)
    except (ChunkError, UnicodeDecodeError) as exc:
        print(f"CHUNK-INPUT-INVALID {exc}", file=stderr)
        return 97
    placeholder_count = sum(part.count("{}") for part in command)
    if shell and len(command) != 1:
        print("CHUNK-INPUT-INVALID --shell requires one --command template", file=stderr)
        return 97
    if shell and placeholder_count:
        print("CHUNK-INPUT-INVALID {} not allowed with --shell", file=stderr)
        return 97
    if not shell and not placeholder_count:
        print("CHUNK-INPUT-INVALID no {} placeholder", file=stderr)
        return 97
    header, digest = _fingerprint(items)
    existed = state_path.exists()
    try:
        completed = _read_state(state_path, header, digest, set(items))
    except ChunkError as exc:
        print(f"CHUNK-STATE-{exc}", file=stderr)
        return 97
    failed_path = Path(f"{state_path}.failed")
    if not existed:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        _append_line(state_path, header)
        if failed_path.exists():
            _truncate(failed_path)
    failed_before: set[str] = set()
    if existed and failed_path.exists():
        try:
            failed_before = _read_failed(failed_path, set(items))
        except ChunkError as exc:
            print(f"CHUNK-STATE-{exc}", file=stderr)
            return 97
    remaining = [item for item in items if item not in completed]
    reruns = set(remaining) & failed_before
    if existed and reruns and not assume_idempotent:
        print(f"CHUNK-RERUN-UNAPPROVED {len(reruns)} item(s)", file=stderr)
        return 97
    started = time_fn()
    failed_now: list[str] = []
    for item in remaining:
        if time_fn() - started >= budget_s:
            print(f"CHUNK-PAUSED {len(completed)}/{len(items)}", file=stdout)
            return 98
        env = None
        if shell:
            env = os.environ.copy()
            env["BRIDGE_ITEM"] = item
            result = runner_fn(command[0], shell=True, env=env, check=False)
        else:
            argv = [part.replace("{}", item) for part in command]
            result = runner_fn(argv, shell=False, check=False)
        if int(result.returncode) == 0:
            _append_line(state_path, item)
            completed.add(item)
        else:
            failed_now.append(item)
            if item not in failed_before and item not in failed_now[:-1]:
                _append_line(failed_path, item)
    if failed_now:
        print(f"CHUNK-FAILED {len(failed_now)}/{len(items)}", file=stdout)
        return 97
    print(f"CHUNK-DONE {len(items)}/{len(items)}", file=stdout)
    return 0


def _repo_from(args_repo: str | None) -> Path:
    return Path(args_repo or os.environ.get("BRIDGE_REPO") or Path(__file__).resolve().parents[1]).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("preflight")
    sub.add_parser("doctor")
    locks = sub.add_parser("locks")
    locks.add_argument(
        "--stale-after",
        type=float,
        help="Purge older host locks; this can break a long-running git operation.",
    )
    git = sub.add_parser("git")
    git.add_argument("args", nargs=argparse.REMAINDER)
    run = sub.add_parser("run")
    run.add_argument("--budget", type=float, default=35)
    run.add_argument("command", nargs=argparse.REMAINDER)
    chunk = sub.add_parser("chunk")
    chunk.add_argument("--list", required=True)
    chunk.add_argument("--state", required=True)
    chunk.add_argument("--budget", type=float, default=35)
    chunk.add_argument("--shell", action="store_true")
    chunk.add_argument(
        "--command",
        dest="shell_command",
        help="Single shell template; read each item from BRIDGE_ITEM.",
    )
    chunk.add_argument(
        "--assume-idempotent",
        action="store_true",
        help=("Approve retrying previously failed items after confirming duplicate side effects are impossible."),
    )
    chunk.add_argument("command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = _repo_from(args.repo)
    if args.action == "preflight":
        return preflight(repo)
    if args.action == "doctor":
        return doctor(repo)
    if args.action == "locks":
        LockSweeper(repo).sweep(args.stale_after)
        return 0
    if args.action == "git":
        return GitRunner(repo).run(args.args)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    if args.action == "run":
        if not command:
            print("run: missing command", file=sys.stderr)
            return 2
        return run_command(command, args.budget)
    if args.shell:
        if command:
            print("CHUNK-INPUT-INVALID --shell uses --command", file=sys.stderr)
            return 97
        command = [args.shell_command] if args.shell_command else []
    elif args.shell_command:
        print("CHUNK-INPUT-INVALID --command requires --shell", file=sys.stderr)
        return 97
    if not command:
        print("CHUNK-INPUT-INVALID missing command", file=sys.stderr)
        return 97
    return run_chunk(
        Path(args.list), Path(args.state), command, shell=args.shell,
        assume_idempotent=args.assume_idempotent, budget_s=args.budget,
    )


if __name__ == "__main__":
    raise SystemExit(main())
