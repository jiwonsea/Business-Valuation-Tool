"""K-0F: weekly-run state lives in one SQLite file written by one writer.

What is pinned down here (scheduler/run_state.py and its use in
scheduler/weekly_run.py):

* one writer: between processes, between threads, and after a process died;
* every start has an end: a normal end, or the mark the next writer leaves;
* fail closed: a damaged, foreign or unknown file is refused and left byte
  for byte as it was; a failed write is never reported as recorded;
* no credential or path reaches the database or the exported event file;
* run_weekly() called directly behaves exactly as before and records nothing.

Everything happens under tmp_path. Nothing here reads the repository's .env,
touches its runs/, logs/, .cache/ or .git, calls the network or a real codex;
a fixture compares runs/ and logs/ before and after every test.
Child processes import scheduler.run_state only (never weekly_run, which
loads .env) and are ended through the Popen object that started them.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import json
import logging
import os
import queue
import sqlite3
import subprocess
import sys
import threading
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scheduler import run_state as rs

REPO_ROOT = Path(__file__).resolve().parent.parent
CHILD_TIME_LIMIT_S = 30

# Credential-shaped values. They are made up for this file and exist nowhere else.
TOKEN_NAME = "Zq7Lm2Xc9Vb4Nn6Hh1Jk8Pd3Fs5Gt0Ry2Wu4Ei6Oa"  # a 40-character token
TOKEN_TAIL = "Kp3Vx8Bn2Mq7Zc4Lh9Jd5Fg1Sr6Tw0Ye3Ui7Oa2Pb"
TOKEN_CLASS = "Hx4Kd9Tn2Wq7Zb5Lm1Jc8Pf3Vs6Gr0Yu4Ei2Oa7Nh"  # 40 letters and digits
SECRET_QUERY = "Q1w2E3r4T5y6U7i8O9p0A1s2D3f4G5h6"
SECRET_BEARER = "B9n8M7v6C5x4Z3l2K1j0H9g8F7d6S5a4"
SECRET_SK = "Xy12Ab34Cd56Ef78Gh90Ij12Kl34Mn56"
SECRET_PASSWORD = "Pw9Lk8Jh7Gf6Ds5Aq4Zw3Xe2Cr1Vt0Bn"
SECRET_ENV = "En7Vr6Tb5Yn4Um3Ik2Ol1Pp0Aq9Sw8De"
SECRET_URL = "Ur5Lq4Wp3Eo2Ri1Tu0Yy9Tt8Rr7Ee6Ww"
WINDOWS_PATH = "C:\\Users\\k0f-windows-account\\private\\report.xlsx"
POSIX_PATH = "/home/k0f-posix-account/private/report.xlsx"
LONG_NAME = " ".join(["Acme"] * 22) + " " + TOKEN_TAIL  # the token starts at 110


# ── small tools ──────────────────────────────────────────────────────────────


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(folder: Path) -> dict | None:
    """Relative path -> sha256 for every file under ``folder``; None if absent."""
    if not folder.exists():
        return None
    return {
        p.relative_to(folder).as_posix(): digest(p)
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def rows(db: Path, query: str, args: tuple = ()) -> list:
    """Read through a read-only connection, as any reader must."""
    con = sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return con.execute(query, args).fetchall()
    finally:
        con.close()


def code_of(excinfo) -> str:
    return excinfo.value.reason_code


def abandon(writer) -> None:
    """What the OS does for a dead process: connection and lock gone, no record."""
    writer._con.close()
    rs._unlock_file(writer._lock_fd)
    os.close(writer._lock_fd)
    writer._closed = True  # a later close() has nothing left to do


def assert_every_start_has_an_end(db: Path, *, runs: int, steps: int) -> None:
    """Scan the whole database. Expected counts are part of the check, so an
    empty or half-recorded database cannot pass by having nothing to look at."""
    run_rows = rows(db, "SELECT run_id, status FROM runs")
    step_rows = rows(db, "SELECT step_id, run_id, kind, state FROM steps")
    events = rows(db, "SELECT seq, run_id, step_id, event FROM events ORDER BY seq")
    assert (len(run_rows), len(step_rows)) == (runs, steps)
    assert [r for r in run_rows if r[1] == "RUNNING"] == []
    assert [s for s in step_rows if s[3] == "STARTED"] == []
    seqs = [e[0] for e in events]
    assert seqs == sorted(set(seqs))
    assert len(events) == 2 * runs + 2 * steps
    for run_id, status in run_rows:
        mine = [(seq, name) for seq, owner, sid, name in events if owner == run_id]
        names = [name for _, name in mine]
        ends = [n for n in names if n in ("run_ended", "run_interrupted")]
        assert names[0] == "run_started" and names.count("run_started") == 1
        assert len(ends) == 1 and names[-1] == ends[0]  # the end is the last event
        assert (ends[0] == "run_interrupted") == (status == "INTERRUPTED")
    for step_id, run_id, kind, state in step_rows:
        mine = [(seq, name) for seq, owner, sid, name in events if sid == step_id]
        assert {owner for _, owner, sid, _ in events if sid == step_id} == {run_id}
        starts = [seq for seq, name in mine if name == "step_started"]
        ends = [(seq, n) for seq, n in mine if n in ("step_ended", "step_interrupted")]
        assert len(starts) == 1 and len(ends) == 1 and len(mine) == 2
        assert starts[0] < ends[0][0]
        assert (ends[0][1] == "step_ended") == (state == "ENDED")
        assert (state == "UNKNOWN_DELIVERY") <= (kind == "delivery")
        assert not (kind == "delivery" and state == "INTERRUPTED")
        run_seqs = [
            seq for seq, owner, sid, _ in events if owner == run_id and sid is None
        ]
        assert min(run_seqs) < starts[0] and ends[0][0] < max(run_seqs)


class Clock:
    """An injected clock: the wall clock and the monotonic clock move apart on demand."""

    def __init__(self) -> None:
        self.moment = datetime(2026, 11, 17, 1, 2, 3, 456000, tzinfo=timezone.utc)
        self.mono = 1000.0

    def now(self) -> datetime:
        return self.moment

    def monotonic(self) -> float:
        return self.mono

    def tick(self, seconds: float, wall: float | None = None) -> None:
        self.mono += seconds
        self.moment += timedelta(seconds=seconds if wall is None else wall)


class FailingConnection:
    """Stands in for the writer's connection and fails the statements a test names."""

    def __init__(self, real, fail, error: BaseException | None = None) -> None:
        self._real = real
        self._fail = fail
        self._error = error or sqlite3.OperationalError("disk I/O error")
        self.statements: list[str] = []

    def execute(self, statement, *args):
        self.statements.append(statement)
        if self._fail(statement, args[0] if args else ()):
            raise self._error
        return self._real.execute(statement, *args)

    def __getattr__(self, name):
        return getattr(self._real, name)


def break_writes(writer, fail=lambda statement, args: True, error=None):
    proxy = FailingConnection(writer._con, fail, error)
    writer._con = proxy
    return proxy


class Child:
    """A child Python process that reports one line once its writes are committed."""

    def __init__(self, code: str, *args) -> None:
        self.proc = subprocess.Popen(
            [sys.executable, "-c", code, *map(str, args)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def line(self) -> str:
        box: queue.Queue = queue.Queue()
        threading.Thread(
            target=lambda: box.put(self.proc.stdout.readline()), daemon=True
        ).start()
        try:
            text = box.get(timeout=CHILD_TIME_LIMIT_S)
        except queue.Empty:
            raise AssertionError("the child did not report within the time limit")
        if not text:
            self.proc.wait(timeout=CHILD_TIME_LIMIT_S)
            raise AssertionError(
                "the child ended early: " + self.proc.stderr.read()[-800:]
            )
        return text.strip()

    def kill(self) -> None:
        """End and reap the child through its own Popen object (never by pid)."""
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=CHILD_TIME_LIMIT_S)
        for stream in (self.proc.stdout, self.proc.stderr):
            stream.close()


CHILD_HOLDS_THE_SEAT = """
import sys, time
from scheduler import run_state as rs
writer = rs.open_writer(sys.argv[1])
rec = writer.start_run(markets=["KR"], max_per_market=1, dry_run=False)
assert rec.start("discovery", "KR") is not None
assert rec.start("valuation", "Child Co", ticker="CHLD", market="US") is not None
assert rec.start("artifact", "summary_file") is not None
assert rec.start("delivery", "email") is not None
print(rec.run_id, flush=True)  # everything above is committed
time.sleep(300)
"""

CHILD_STOPS_INSIDE_A_TRANSACTION = """
import sys, time
from scheduler import run_state as rs
writer = rs.open_writer(sys.argv[1])
rec = writer.start_run(markets=["US"], max_per_market=1, dry_run=False)
assert rec.start("valuation", "Committed Co", ticker="CMTD", market="US") is not None
con = writer._con
con.execute("BEGIN IMMEDIATE")
con.execute(
    "INSERT INTO steps (run_id, kind, target, state, started_at, started_at_kst, facts) "
    "VALUES (?, 'valuation', 'Uncommitted Co', 'STARTED', 'x', 'x', '{}')",
    (rec.run_id,),
)
con.execute(
    "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
    "VALUES (?, 99, 'step_started', 'x', 'x', '{}')",
    (rec.run_id,),
)
print(rec.run_id, flush=True)  # the run and one step are committed, the rest is not
time.sleep(300)
"""


def open_when_free(db: Path, **kwargs):
    """open_writer(), allowing the OS a moment to drop a dead process's lock."""
    deadline = datetime.now() + timedelta(seconds=10)
    while True:
        try:
            return rs.open_writer(db, **kwargs)
        except rs.RunStateUnavailable as exc:
            if exc.reason_code != "WRITER_BUSY" or datetime.now() > deadline:
                raise
            threading.Event().wait(0.05)


# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def repository_folders_are_never_touched(tmp_path):
    """Every default path points into tmp_path, and the repository's own runs/
    and logs/ folders are the same before and after each test: present or
    absent as before, same files, same content.

    The defaults are swapped by hand, not with monkeypatch: an autouse fixture
    that asked for monkeypatch would set it up before env_guard, and env_guard
    must outlive it.
    """
    watched = [REPO_ROOT / "runs", REPO_ROOT / "logs"]
    before = [tree_digest(folder) for folder in watched]
    elsewhere = tmp_path / "default-runs" / "state.db"
    weekly = sys.modules.get("scheduler.weekly_run")
    saved = [(rs, "DEFAULT_DB_PATH", rs.DEFAULT_DB_PATH)]
    if weekly is not None and hasattr(weekly, "_RUN_STATE_DB"):
        saved.append((weekly, "_RUN_STATE_DB", weekly._RUN_STATE_DB))
    for module, name, _ in saved:
        setattr(module, name, elsewhere)
    try:
        yield
    finally:
        for module, name, value in saved:
            setattr(module, name, value)
    assert [tree_digest(folder) for folder in watched] == before
    assert not elsewhere.parent.exists()  # and no test fell back on a default path


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "runs" / "state.db"


@pytest.fixture
def opened():
    """open_writer() whose writers are closed when the test ends."""
    made = []

    def _open(path, **kwargs):
        writer = rs.open_writer(path, **kwargs)
        made.append(writer)
        return writer

    yield _open
    for writer in made:
        writer.close()


def start(writer, **kwargs):
    kwargs.setdefault("markets", ["KR", "US"])
    kwargs.setdefault("max_per_market", 5)
    kwargs.setdefault("dry_run", False)
    return writer.start_run(**kwargs)


def one_finished_run(db: Path, steps: int = 3) -> str:
    """A database with one completed run; returns its run id."""
    writer = rs.open_writer(db)
    rec = start(writer)
    for index in range(steps):
        step = rec.start("valuation", f"Company {index}", ticker="AAPL", market="US")
        rec.end(step, "success", degraded=[])
    rec.end_run("COMPLETED", errors=0)
    writer.close()
    return rec.run_id


# ── 11. environment ──────────────────────────────────────────────────────────


def test_the_runtime_meets_what_the_module_relies_on(capsys):
    with capsys.disabled():
        print(
            f"\n[k0f] python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version} "
            f"threadsafety {sqlite3.threadsafety} os {os.name}"
        )
    assert sqlite3.sqlite_version_info >= (3, 22, 0)
    assert sqlite3.threadsafety != 0


@pytest.mark.parametrize(
    "name, value",
    [("sqlite_version_info", (3, 21, 0)), ("threadsafety", 0)],
)
def test_an_unsupported_sqlite_is_refused_before_anything_is_created(
    monkeypatch, tmp_path, name, value
):
    monkeypatch.setattr(rs.sqlite3, name, value)
    target = tmp_path / "never" / "state.db"

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(target)

    assert code_of(caught) == "SQLITE_UNSUPPORTED"
    assert caught.value.exit_code == 3
    assert not target.parent.exists()


def test_reading_is_refused_on_an_unsupported_sqlite(monkeypatch, db):
    one_finished_run(db)
    monkeypatch.setattr(rs.sqlite3, "sqlite_version_info", (3, 21, 0))

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.read_runs(db)

    assert code_of(caught) == "SQLITE_UNSUPPORTED"


# ── 1. opening and validating ────────────────────────────────────────────────


def test_importing_the_module_creates_no_file_and_no_folder(tmp_path):
    package = tmp_path / "copy" / "scheduler"
    package.mkdir(parents=True)
    source = package / "run_state.py"
    source.write_bytes(Path(rs.__file__).read_bytes())
    spec = importlib.util.spec_from_file_location("k0f_run_state_copy", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]

    assert module.DEFAULT_DB_PATH == tmp_path / "copy" / "runs" / "state.db"
    assert sorted(p.name for p in (tmp_path / "copy").iterdir()) == ["scheduler"]
    assert [p.name for p in package.iterdir() if p.is_file()] == ["run_state.py"]


def test_a_new_database_is_complete_and_marked(db, opened):
    writer = opened(db)
    writer.close()

    assert rows(db, "PRAGMA application_id") == [(rs.APPLICATION_ID,)]
    assert rows(db, "PRAGMA user_version") == [(rs.SCHEMA_VERSION,)]
    assert rows(db, "PRAGMA journal_mode") == [("wal",)]
    assert rows(db, "PRAGMA integrity_check") == [("ok",)]
    tables = {
        r[0] for r in rows(db, "SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"runs", "steps", "events"} <= tables
    names = {p.name for p in db.parent.iterdir()}
    assert {"state.db", "state.db.writer.lock"} <= names
    assert "state.db.new" not in names  # the scratch name does not outlive creation
    assert (db.parent / "state.db.writer.lock").stat().st_size == 0
    assert writer.recovered == ()


def test_reopening_keeps_what_was_recorded(db):
    run_id = one_finished_run(db, steps=2)

    writer = rs.open_writer(db)
    writer.close()

    assert writer.recovered == ()
    assert rows(db, "SELECT run_id, status FROM runs") == [(run_id, "COMPLETED")]
    assert_every_start_has_an_end(db, runs=1, steps=2)


def _garbage(db: Path) -> None:
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a database\n" * 400)


def _zero_bytes(db: Path) -> None:
    db.parent.mkdir(parents=True)
    db.write_bytes(b"")


def _foreign_with_a_table(db: Path) -> None:
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE theirs (x)")
    con.execute("INSERT INTO theirs VALUES (1)")
    con.commit()
    con.close()


def _foreign_and_empty(db: Path) -> None:
    """Someone else's database after they dropped everything: all three zeros."""
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE theirs (x)")
    con.execute("DROP TABLE theirs")
    con.commit()
    assert con.execute("SELECT count(*) FROM sqlite_master").fetchone() == (0,)
    con.close()
    assert db.stat().st_size > 0


def _foreign_application_id(db: Path) -> None:
    db.parent.mkdir(parents=True)
    con = sqlite3.connect(db)
    con.execute("PRAGMA application_id=12345")
    con.execute("PRAGMA user_version=1")
    con.execute("CREATE TABLE runs (x)")
    con.commit()
    con.close()


def _a_later_schema_version(db: Path) -> None:
    one_finished_run(db)
    con = sqlite3.connect(db)
    con.execute("PRAGMA user_version=2")
    con.commit()
    con.close()


def _truncated(db: Path) -> None:
    one_finished_run(db, steps=120)
    assert db.stat().st_size > 8 * 4096
    with open(db, "r+b") as handle:
        handle.truncate(db.stat().st_size // 2)


def _ours_with_a_damaged_page_in_rollback_mode(db: Path) -> None:
    """Our mark, a readable header and schema, one broken page in the middle,
    and rollback-journal mode: checking it must not switch it to WAL first."""
    one_finished_run(db, steps=120)
    con = sqlite3.connect(db, isolation_level=None)
    assert con.execute("PRAGMA journal_mode=DELETE").fetchone() == ("delete",)
    page_size = con.execute("PRAGMA page_size").fetchone()[0]
    pages = con.execute("PRAGMA page_count").fetchone()[0]
    con.close()
    assert pages > 8
    with open(db, "r+b") as handle:
        handle.seek(page_size * (pages // 2))
        handle.write(b"\xa5" * page_size)
    assert db.read_bytes()[18:20] == b"\x01\x01"  # still rollback-journal format


@pytest.mark.parametrize(
    "make, code",
    [
        (_garbage, "DB_CORRUPT"),
        (_zero_bytes, "DB_FOREIGN"),
        (_foreign_with_a_table, "DB_FOREIGN"),
        (_foreign_and_empty, "DB_FOREIGN"),
        (_foreign_application_id, "DB_FOREIGN"),
        (_a_later_schema_version, "SCHEMA_UNSUPPORTED"),
        (_truncated, "DB_CORRUPT"),
        (_ours_with_a_damaged_page_in_rollback_mode, "DB_CORRUPT"),
    ],
    ids=lambda value: getattr(value, "__name__", value).lstrip("_"),
)
def test_a_file_that_cannot_be_trusted_is_refused_and_left_as_it_was(db, make, code):
    make(db)
    before = digest(db)

    for _ in range(2):  # the second attempt proves the seat was given back
        with pytest.raises(rs.RunStateUnavailable) as caught:
            rs.open_writer(db)
        assert code_of(caught) == code

    assert digest(db) == before
    assert caught.value.exit_code == 3
    assert str(db.parent) not in str(caught.value)  # fixed text, no path


def _hot_journal_copy(folder: Path, mark_as_ours: bool) -> Path:
    """A database with a hot rollback journal: the image a crash leaves behind.

    A writer with a tiny cache spills changed pages into the file before it
    commits; copying file and journal at that moment gives the crash image.
    """
    source = folder / "source.db"
    con = sqlite3.connect(source, isolation_level=None)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute(
        "PRAGMA synchronous=OFF"
    )  # a fixture: nothing here must survive a crash
    con.execute("CREATE TABLE theirs (id INTEGER PRIMARY KEY, v TEXT)")
    con.executemany(
        "INSERT INTO theirs (v) VALUES (?)", [("x" * 900,) for _ in range(300)]
    )
    if mark_as_ours:
        con.execute(f"PRAGMA application_id={rs.APPLICATION_ID}")
        con.execute(f"PRAGMA user_version={rs.SCHEMA_VERSION}")
    con.execute("PRAGMA cache_size=5")
    con.execute("BEGIN IMMEDIATE")
    con.execute("UPDATE theirs SET v = replace(v, 'x', 'y')")
    target = folder / "runs" / "state.db"
    target.parent.mkdir()
    target.write_bytes(source.read_bytes())
    journal = folder / "runs" / "state.db-journal"
    journal.write_bytes((folder / "source.db-journal").read_bytes())
    con.execute("ROLLBACK")
    con.close()
    assert journal.stat().st_size > 1024
    return target


def test_the_hot_journal_fixture_really_is_hot(tmp_path):
    """Otherwise the next test would pass for the wrong reason."""
    target = _hot_journal_copy(tmp_path, mark_as_ours=False)
    before = digest(target)

    con = sqlite3.connect(target)  # a connection that may write
    con.execute("SELECT count(*) FROM theirs").fetchone()
    con.close()

    assert digest(target) != before  # merely reading rolled the journal back
    assert not Path(str(target) + "-journal").exists()


@pytest.mark.parametrize(
    "mark_as_ours", [False, True], ids=["foreign", "marked_as_ours"]
)
def test_a_file_with_a_hot_journal_is_not_touched(tmp_path, mark_as_ours):
    """Reading through a connection that may write would roll the journal back,
    changing a file before it is known to be ours and sound."""
    target = _hot_journal_copy(tmp_path, mark_as_ours)
    journal = Path(str(target) + "-journal")
    before = (digest(target), digest(journal))

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(target)

    assert code_of(caught) == "DB_UNAVAILABLE"
    assert (digest(target), digest(journal)) == before


def test_an_interrupted_creation_leaves_nothing_that_blocks_the_next_writer(db, opened):
    db.parent.mkdir(parents=True)
    leftovers = ["state.db.new" + suffix for suffix in ("", "-journal", "-wal", "-shm")]
    for name in leftovers:
        (db.parent / name).write_bytes(b"half of something")

    writer = opened(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    writer.close()

    assert not any((db.parent / name).exists() for name in leftovers)
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_a_scratch_name_left_beside_the_database_is_dropped_without_harm(db, opened):
    """Killed between os.link() and the removal of the scratch name."""
    run_id = one_finished_run(db, steps=2)
    os.link(db, db.parent / "state.db.new")

    writer = opened(db)
    writer.close()

    assert not (db.parent / "state.db.new").exists()
    assert rows(db, "SELECT run_id, status FROM runs") == [(run_id, "COMPLETED")]
    assert_every_start_has_an_end(db, runs=1, steps=2)


def test_a_new_database_is_already_in_wal_format_when_it_gets_its_real_name(
    db, opened, monkeypatch
):
    """Switching to WAL journals a transaction. Done on the real name, a kill
    inside it would leave a hot journal there and block every later writer."""
    seen = {}
    real = rs._open_for_writing

    def looking_first(path, examined):
        seen["format"] = Path(path).read_bytes()[18:20]
        seen["beside"] = sorted(p.name for p in Path(path).parent.iterdir())
        return real(path, examined)

    monkeypatch.setattr(rs, "_open_for_writing", looking_first)

    opened(db).close()

    assert seen["format"] == b"\x02\x02"  # WAL, before the writing connection exists
    assert "state.db-journal" not in seen["beside"]
    assert not any(name.startswith("state.db.new") for name in seen["beside"])


def test_a_database_that_vanishes_after_the_examination_is_not_recreated(
    db, monkeypatch
):
    one_finished_run(db)
    real = rs._examine

    def then_it_is_gone(path):
        header = real(path)
        for extra in Path(path).parent.glob("state.db*"):
            if extra.name != "state.db.writer.lock":
                extra.unlink()
        return header

    monkeypatch.setattr(rs, "_examine", then_it_is_gone)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(db)

    assert code_of(caught) == "DB_UNAVAILABLE"
    assert not db.exists()


def _scratch_removal_fails(db: Path, times: int, attempts: list):
    real_unlink = Path.unlink

    def unlink(self, missing_ok=False):
        if self.name == "state.db.new" and db.exists():
            attempts.append(self.name)
            if len(attempts) <= times:
                raise PermissionError(13, "in use")
        return real_unlink(self, missing_ok=missing_ok)

    return unlink


def test_a_scratch_name_held_for_a_moment_is_removed_on_a_later_attempt(
    db, opened, monkeypatch
):
    attempts: list = []
    monkeypatch.setattr(Path, "unlink", _scratch_removal_fails(db, 2, attempts))
    monkeypatch.setattr(rs.time, "sleep", lambda seconds: None)

    opened(db).close()

    assert len(attempts) == 3
    assert not (db.parent / "state.db.new").exists()


def test_a_scratch_name_that_stays_fails_this_open_and_the_next_one_removes_it(
    db, opened, monkeypatch
):
    """Left in place it would be a second name for the database file."""
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", _scratch_removal_fails(db, 10**6, []))
        patch.setattr(rs.time, "sleep", lambda seconds: None)
        with pytest.raises(rs.RunStateUnavailable) as caught:
            rs.open_writer(db)
        assert code_of(caught) == "DB_UNAVAILABLE"
        assert db.exists() and (db.parent / "state.db.new").exists()

    writer = opened(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    writer.close()

    assert not (db.parent / "state.db.new").exists()
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_creation_never_replaces_a_file_that_appeared_meanwhile(db, monkeypatch):
    """os.link() is what puts the new database in place, and it refuses a taken name."""
    db.parent.mkdir(parents=True)
    real_link = os.link

    def someone_else_gets_there_first(source, target):
        Path(target).write_bytes(b"theirs")
        return real_link(source, target)

    monkeypatch.setattr(rs.os, "link", someone_else_gets_there_first)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(db)

    assert code_of(caught) == "DB_UNAVAILABLE"
    assert db.read_bytes() == b"theirs"


def test_a_symbolic_link_to_the_database_leads_to_the_same_seat(db, opened, tmp_path):
    """The lock file is found through the real path. Named after the link, it
    would be a second lock for the same database."""
    first = opened(db)
    rec = start(first)
    rec.start("delivery", "email")
    link = tmp_path / "elsewhere" / "alias.db"
    link.parent.mkdir()
    try:
        os.symlink(db, link)
    except (OSError, NotImplementedError):
        pytest.skip("this account cannot create symbolic links")

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(link)

    assert code_of(caught) == "WRITER_BUSY"
    assert rows(db, "SELECT status FROM runs") == [("RUNNING",)]
    assert sorted(p.name for p in link.parent.iterdir()) == ["alias.db"]  # no lock here
    assert rec.start("discovery", "KR") is not None and not rec.broken


def test_a_database_file_with_a_second_name_is_refused(db, opened, tmp_path):
    """A hard link is a second door to the same file: its own lock file and
    its own -wal. No path can make the two one, so the file is refused."""
    first = opened(db)
    rec = start(first)
    rec.start("delivery", "email")
    alias = tmp_path / "alias.db"
    os.link(db, alias)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(alias)

    assert code_of(caught) == "DB_ALIASED"
    assert not Path(str(alias) + "-wal").exists()  # it was not even connected to
    assert rows(db, "SELECT status FROM runs") == [("RUNNING",)]
    assert rec.start("discovery", "KR") is not None and not rec.broken
    first.close()
    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(db)  # by either name, while there are two
    assert code_of(caught) == "DB_ALIASED"
    alias.unlink()
    second = opened(db)
    second.close()
    assert second.recovered == (rec.run_id,)
    assert_every_start_has_an_end(db, runs=1, steps=2)


def test_a_parent_that_is_a_file_is_reported_not_raised_raw(tmp_path):
    (tmp_path / "runs").write_bytes(b"a file where the folder should be")

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(tmp_path / "runs" / "state.db")

    assert code_of(caught) == "DB_UNAVAILABLE"


def test_every_code_has_a_fixed_text():
    for code in rs._MESSAGES:
        assert str(rs.RunStateError(code)).startswith(code + ": ")
    assert rs.RunStateUnavailable("WRITER_BUSY").exit_code == 3
    assert rs.RunStateRecordingFailed("RECORDING_FAILED").exit_code == 4


# ── 2. one writer ────────────────────────────────────────────────────────────


def test_a_second_writer_in_the_same_process_is_refused(db, opened):
    first = opened(db)
    rec = start(first)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(db)

    assert code_of(caught) == "WRITER_BUSY"
    step = rec.start("discovery", "KR")  # the first writer is unaffected
    rec.end(step, "ok")
    rec.end_run("COMPLETED")
    assert not rec.broken


def test_the_seat_is_free_again_after_close(db):
    rs.open_writer(db).close()
    second = rs.open_writer(db)
    second.close()
    second.close()  # closing twice is harmless


def test_another_process_holds_the_seat_and_a_dead_one_leaves_no_lock(db):
    child = Child(CHILD_HOLDS_THE_SEAT, db)
    try:
        run_id = child.line()

        with pytest.raises(rs.RunStateUnavailable) as caught:
            rs.open_writer(db)
        assert code_of(caught) == "WRITER_BUSY"
        # a reader is not a writer: it sees the live run while the child holds the seat
        assert [r["status"] for r in rs.read_runs(db)] == ["RUNNING"]
        with pytest.raises(AssertionError):
            assert_every_start_has_an_end(db, runs=1, steps=4)  # starts are open

        child.kill()
        writer = open_when_free(db)
    finally:
        child.kill()
    writer.close()

    assert writer.recovered == (run_id,)
    run = rs.read_run(db, run_id)
    assert (run["run"]["status"], run["run"]["reason_code"]) == (
        "INTERRUPTED",
        "NO_END_RECORDED",
    )
    assert {(s["kind"], s["state"], s["reason_code"]) for s in run["steps"]} == {
        ("discovery", "INTERRUPTED", "NO_END_RECORDED"),
        ("valuation", "INTERRUPTED", "NO_END_RECORDED"),
        ("artifact", "INTERRUPTED", "NO_END_RECORDED"),
        ("delivery", "UNKNOWN_DELIVERY", "NO_END_RECORDED"),
    }
    assert run["run"]["duration_ms"] is None  # nobody knows how long it ran
    assert_every_start_has_an_end(db, runs=1, steps=4)
    lines = (
        (db.parent / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
    )
    assert json.loads(lines[-1])["event"] == "run_interrupted"


def test_a_process_killed_inside_a_transaction_leaves_a_sound_file(db):
    child = Child(CHILD_STOPS_INSIDE_A_TRANSACTION, db)
    try:
        run_id = child.line()
        child.kill()
        writer = open_when_free(db)
    finally:
        child.kill()
    writer.close()

    assert rows(db, "PRAGMA integrity_check") == [("ok",)]
    assert writer.recovered == (run_id,)
    assert rows(db, "SELECT target, state FROM steps") == [
        ("Committed Co", "INTERRUPTED")
    ]
    assert rows(db, "SELECT count(*) FROM events WHERE step_id = 99") == [(0,)]
    assert_every_start_has_an_end(db, runs=1, steps=1)


# fork() is outside what this module supports: a process must not fork while
# it holds a writer (see the module docstring). What is pinned here is only
# that a copy of the writer in another process is inert. The other process is
# played by changing the pid the writer remembers.


@contextlib.contextmanager
def as_a_copy_in_another_process(writer):
    own = writer._pid
    writer._pid = -1  # no process has this pid
    try:
        yield
    finally:
        writer._pid = own


def test_a_copy_of_the_writer_in_another_process_records_nothing(db, opened, caplog):
    writer = opened(db)
    rec = start(writer)
    first = rec.start("discovery", "KR")
    events = rows(db, "SELECT count(*) FROM events")

    with as_a_copy_in_another_process(writer):
        with caplog.at_level(logging.ERROR, logger="scheduler.run_state"):
            assert rec.start("delivery", "email") is None  # so no delivery starts
            rec.end(first, "ok")
            rec.end_run("COMPLETED")

    assert rec.broken
    assert caplog.text.count("did not take the writer seat") == 1  # said once
    assert rows(db, "SELECT count(*) FROM events") == events
    assert rows(db, "SELECT status FROM runs") == [("RUNNING",)]
    assert rows(db, "SELECT kind, state FROM steps") == [("discovery", "STARTED")]


def test_a_copy_of_the_writer_in_another_process_starts_no_run(db, opened):
    writer = opened(db)

    with as_a_copy_in_another_process(writer):
        with pytest.raises(rs.RunStateUnavailable) as caught:
            start(writer)

    assert code_of(caught) == "START_NOT_RECORDED"
    assert rows(db, "SELECT count(*) FROM runs") == [(0,)]
    assert rows(db, "SELECT count(*) FROM events") == [(0,)]
    start(writer).end_run("COMPLETED")  # the process that took the seat still can
    assert rows(db, "SELECT status FROM runs") == [("COMPLETED",)]


def test_closing_a_copy_in_another_process_gives_nothing_back(db):
    writer = rs.open_writer(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    exported = db.parent / rec.run_id / "events.jsonl"
    try:
        with as_a_copy_in_another_process(writer):
            writer.close()
            writer.close()

        assert not exported.exists()  # no export
        with pytest.raises(rs.RunStateUnavailable) as caught:
            rs.open_writer(db)
        assert code_of(caught) == "WRITER_BUSY"  # no unlock
        # ... and the connection was not closed
        assert writer._con.execute("SELECT count(*) FROM runs").fetchone() == (1,)
    finally:
        writer.close()  # the process that took the seat gives it back
    assert exported.exists()
    rs.open_writer(db).close()


def test_a_copy_in_another_process_does_not_wait_for_the_writers_lock(db, opened):
    """In a forked child the lock may be held by a thread that is not there."""
    writer = opened(db)
    rec = start(writer)
    seen = []

    def use_the_copy():
        try:
            start(writer)
        except rs.RunStateUnavailable as exc:
            seen.append(exc.reason_code)
        seen.append(rec.start("discovery", "KR"))
        writer.close()
        seen.append("close returned")

    with as_a_copy_in_another_process(writer):
        assert writer._mutex.acquire(timeout=CHILD_TIME_LIMIT_S)
        try:
            thread = threading.Thread(target=use_the_copy, daemon=True)
            thread.start()
            thread.join(timeout=5)
            waited_for_the_lock = thread.is_alive()
        finally:
            writer._mutex.release()
        thread.join(timeout=CHILD_TIME_LIMIT_S)

    assert not waited_for_the_lock
    assert seen == ["START_NOT_RECORDED", None, "close returned"]


def test_pool_threads_write_through_one_recorder(db, opened):
    writer = opened(db)
    rec = start(writer)
    failures: list[BaseException] = []

    def work(thread: int) -> None:
        try:
            for index in range(15):
                step = rec.start(
                    "valuation", f"Co {thread}-{index}", ticker="AAPL", market="US"
                )
                assert step is not None
                rec.end(step, "success", degraded=[])
        except BaseException as exc:
            failures.append(exc)

    threads = [threading.Thread(target=work, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rec.end_run("COMPLETED")
    writer.close()

    assert failures == [] and not rec.broken
    seqs = [r[0] for r in rows(db, "SELECT seq FROM events ORDER BY seq")]
    assert seqs == list(range(1, 2 + 2 * 120 + 1))  # no gap, no repeat
    assert_every_start_has_an_end(db, runs=1, steps=120)


def test_every_statement_runs_under_the_writer_lock(db, opened):
    writer = opened(db)
    held: list[bool] = []
    real = writer._con

    class Watching:
        def execute(self, statement, *args):
            held.append(writer._mutex.locked())
            return real.execute(statement, *args)

        def __getattr__(self, name):
            return getattr(real, name)

    writer._con = Watching()
    writer._recover()
    recovering = len(held)
    rec = start(writer)
    starting = len(held)
    step = rec.start("discovery", "KR")
    rec.end(step, "ok")
    rec.end_run("COMPLETED")
    recording = len(held)
    writer.close()

    # recovery, the start of the run, the steps, and the export when closing
    assert 0 < recovering < starting < recording < len(held)
    assert all(held)


# ── 3. the state table: how each kind of start can end ───────────────────────

STEP_KINDS = [
    ("discovery", "KR", {}, "ok"),
    ("valuation", "Sample Co", {"ticker": "AAPL", "market": "US"}, "success"),
    ("artifact", "summary_file", {}, "ok"),
    ("delivery", "email", {}, "ok"),
]
UNFINISHED = {
    "discovery": "INTERRUPTED",
    "valuation": "INTERRUPTED",
    "artifact": "INTERRUPTED",
    "delivery": "UNKNOWN_DELIVERY",
}


@pytest.mark.parametrize("kind, target, facts, outcome", STEP_KINDS)
def test_cell_step_ends_normally(db, opened, kind, target, facts, outcome):
    writer = opened(db)
    rec = start(writer)
    step = rec.start(kind, target, **facts)
    rec.end(step, outcome)
    rec.end_run("COMPLETED")
    writer.close()

    assert rows(db, "SELECT kind, target, state, outcome, reason_code FROM steps") == [
        (kind, target, "ENDED", outcome, None)
    ]
    assert_every_start_has_an_end(db, runs=1, steps=1)


@pytest.mark.parametrize("kind, target, facts, outcome", STEP_KINDS)
def test_cell_step_open_when_the_run_fails(db, opened, kind, target, facts, outcome):
    writer = opened(db)
    rec = start(writer)
    rec.start(kind, target, **facts)
    rec.end_run("FAILED", reason_code=rs.RUN_EXCEPTION, error_type="KeyError")
    writer.close()

    assert rows(db, "SELECT state, outcome, reason_code FROM steps") == [
        (UNFINISHED[kind], None, "RUN_ENDED_WITH_OPEN_STEP")
    ]
    assert rows(db, "SELECT status, reason_code FROM runs") == [
        ("FAILED", "RUN_EXCEPTION")
    ]
    assert not rec.broken
    assert_every_start_has_an_end(db, runs=1, steps=1)


@pytest.mark.parametrize("kind, target, facts, outcome", STEP_KINDS)
def test_cell_step_whose_process_died(db, opened, kind, target, facts, outcome):
    first = rs.open_writer(db)
    rec = start(first)
    rec.start(kind, target, **facts)
    abandon(first)

    second = opened(db)
    second.close()

    assert second.recovered == (rec.run_id,)
    assert rows(db, "SELECT state, outcome, reason_code, duration_ms FROM steps") == [
        (UNFINISHED[kind], None, "NO_END_RECORDED", None)
    ]
    assert rows(db, "SELECT status, reason_code FROM runs") == [
        ("INTERRUPTED", "NO_END_RECORDED")
    ]
    assert_every_start_has_an_end(db, runs=1, steps=1)


@pytest.mark.parametrize("kind, target, facts, outcome", STEP_KINDS)
def test_cell_step_whose_start_could_not_be_recorded(
    db, opened, kind, target, facts, outcome
):
    first = rs.open_writer(db)
    rec = start(first)
    break_writes(
        first, lambda statement, args: statement.startswith("INSERT INTO steps")
    )

    step = rec.start(kind, target, **facts)

    assert step is None and rec.broken
    rec.end(step, outcome)  # a step that never started has no end to record
    rec.end_run("COMPLETED")  # and a broken record is not written to again
    abandon(first)
    second = opened(db)
    second.close()
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]
    assert rows(db, "SELECT status, reason_code FROM runs") == [
        ("INTERRUPTED", "NO_END_RECORDED")
    ]
    assert_every_start_has_an_end(db, runs=1, steps=0)


@pytest.mark.parametrize("kind, target, facts, outcome", STEP_KINDS)
def test_cell_step_whose_end_could_not_be_recorded(
    db, opened, kind, target, facts, outcome
):
    first = rs.open_writer(db)
    rec = start(first)
    step = rec.start(kind, target, **facts)
    break_writes(first, lambda statement, args: statement.startswith("UPDATE steps"))

    rec.end(step, outcome)

    assert rec.broken
    abandon(first)
    second = opened(db)
    second.close()
    assert rows(db, "SELECT state, outcome, reason_code FROM steps") == [
        (UNFINISHED[kind], None, "NO_END_RECORDED")
    ]
    assert_every_start_has_an_end(db, runs=1, steps=1)


@pytest.mark.parametrize("status", ["COMPLETED", "COMPLETED_WITH_ERRORS"])
def test_cell_run_ends_normally(db, opened, status):
    writer = opened(db)
    rec = start(writer, markets=["KR"], max_per_market=3, dry_run=True)
    rec.end_run(status, errors=2, zero_selection=False)
    writer.close()

    run = rs.read_runs(db)[0]
    assert (run["status"], run["reason_code"]) == (status, None)
    assert (run["markets"], run["max_per_market"], run["dry_run"]) == (["KR"], 3, True)
    assert run["pid"] == os.getpid()
    assert run["facts"] == {"errors": 2, "zero_selection": False}
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_cell_run_whose_start_cannot_be_recorded(db, opened):
    writer = opened(db)
    break_writes(
        writer, lambda statement, args: statement.startswith("INSERT INTO runs")
    )

    with pytest.raises(rs.RunStateUnavailable) as caught:
        start(writer)

    assert code_of(caught) == "START_NOT_RECORDED"
    writer.close()
    assert rows(db, "SELECT count(*) FROM runs") == [(0,)]
    assert rows(db, "SELECT count(*) FROM events") == [(0,)]


@pytest.mark.parametrize("failing", ["now", "monotonic"])
def test_a_clock_that_fails_at_the_start_leaves_no_start_in_the_file(
    db, opened, failing
):
    """A start reported as not recorded must not be in the file: whatever can
    fail is done before the commit."""
    armed = {"on": False}

    def now():
        if armed["on"] and failing == "now":
            raise RuntimeError("the wall clock failed")
        return datetime(2026, 11, 17, 1, 2, 3, tzinfo=timezone.utc)

    def monotonic():
        if armed["on"] and failing == "monotonic":
            raise RuntimeError("the monotonic clock failed")
        return 5.0

    writer = opened(db, now=now, monotonic=monotonic)
    armed["on"] = True

    with pytest.raises(rs.RunStateUnavailable) as caught:
        start(writer)

    assert code_of(caught) == "START_NOT_RECORDED"
    assert rows(db, "SELECT count(*) FROM runs") == [(0,)]
    assert rows(db, "SELECT count(*) FROM events") == [(0,)]
    armed["on"] = False
    rec = start(writer)  # nothing was left half-done
    rec.end_run("COMPLETED")
    writer.close()
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_cell_run_whose_end_cannot_be_recorded(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    break_writes(first, lambda statement, args: statement.startswith("UPDATE runs"))

    rec.end_run("COMPLETED")

    assert rec.broken
    abandon(first)
    second = opened(db)
    second.close()
    assert rows(db, "SELECT status, reason_code FROM runs") == [
        ("INTERRUPTED", "NO_END_RECORDED")
    ]
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_cell_another_writer_changes_nothing_in_the_file(db, opened):
    first = opened(db)
    rec = start(first)
    rec.start("discovery", "KR")
    before = rows(db, "SELECT seq, event FROM events ORDER BY seq")

    with pytest.raises(rs.RunStateUnavailable):
        rs.open_writer(db)

    assert rows(db, "SELECT seq, event FROM events ORDER BY seq") == before
    assert rows(db, "SELECT status FROM runs") == [("RUNNING",)]


def test_the_invariant_check_itself_notices_an_open_step(db, opened):
    writer = opened(db)
    rec = start(writer)
    rec.start("discovery", "KR")

    with pytest.raises(AssertionError):
        assert_every_start_has_an_end(db, runs=1, steps=1)

    rec.end_run("COMPLETED")
    writer.close()
    assert_every_start_has_an_end(db, runs=1, steps=1)
    with pytest.raises(AssertionError):
        assert_every_start_has_an_end(db, runs=1, steps=2)  # counts are checked too


# ── 5. failed writes and forbidden transitions ───────────────────────────────


def test_a_failed_write_latches_and_nothing_more_is_written(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    proxy = break_writes(first)

    assert rec.start("discovery", "KR") is None
    assert rec.broken
    attempted = len(proxy.statements)
    assert rec.start("delivery", "email") is None
    rec.end_run("COMPLETED")

    assert len(proxy.statements) == attempted  # the database was not even asked
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT event FROM events ORDER BY seq") == [
        ("run_started",),
        ("run_interrupted",),
    ]


def test_a_commit_that_fails_is_a_failed_write(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    break_writes(first, lambda statement, args: statement == "COMMIT")

    assert rec.start("discovery", "KR") is None

    assert rec.broken
    assert not first._con.in_transaction  # rolled back
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_a_run_closed_behind_the_writers_back_gets_no_more_steps(db, opened):
    """The writer does not go by its own memory alone."""
    first = rs.open_writer(db)
    rec = start(first)
    other = sqlite3.connect(db, isolation_level=None)
    other.execute(
        "UPDATE runs SET status = 'INTERRUPTED' WHERE run_id = ?", (rec.run_id,)
    )
    other.close()

    assert rec.start("delivery", "email") is None

    assert rec.broken
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]
    abandon(first)


def test_a_step_handle_carries_nothing_that_is_stored(db, opened):
    """end() reads kind, target and start facts back from the row. A handle
    that could be changed would be a way around the checks on what is stored."""
    writer = opened(db)
    rec = start(writer)
    step = rec.start("valuation", "Normal Co", ticker="AAPL", market="US")

    assert step._fields == ("step_id", "started")
    with pytest.raises(AttributeError):
        step.step_id = 99
    with pytest.raises(AttributeError):
        step.target = TOKEN_NAME
    rec.end(step._replace(started=TOKEN_NAME), "success", degraded=[])

    assert not rec.broken
    (stored,) = rs.read_run(db, rec.run_id)["steps"]
    assert (stored["target"], stored["state"], stored["duration_ms"]) == (
        "Normal Co",
        "ENDED",
        None,
    )
    assert stored["facts"] == {"ticker": "AAPL", "market": "US", "degraded": []}
    rec.end_run("COMPLETED")
    writer.close()
    stored_bytes = b"".join(p.read_bytes() for p in db.parent.rglob("*") if p.is_file())
    assert TOKEN_NAME.encode() not in stored_bytes


def test_a_handle_that_names_no_open_step_is_a_failed_write(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    rec.start("discovery", "KR")

    rec.end(rs._Step(10**6, 0.0), "ok")

    assert rec.broken
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT state FROM steps") == [("INTERRUPTED",)]


def test_a_thread_waiting_for_the_lock_does_not_write_after_a_failure(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    inside = threading.Event()
    release = threading.Event()

    def fail(statement, args):
        if statement.startswith("INSERT INTO steps") and "Fails" in args:
            inside.set()
            assert release.wait(CHILD_TIME_LIMIT_S)
            return True
        return False

    break_writes(first, fail)
    results: dict[str, object] = {}

    def failing():
        results["failing"] = rec.start("valuation", "Fails", ticker="AAA", market="US")

    def waiting():
        results["waiting"] = rec.start("valuation", "Waits", ticker="BBB", market="US")

    one = threading.Thread(target=failing)
    one.start()
    assert inside.wait(CHILD_TIME_LIMIT_S)  # the first thread is inside the lock
    two = threading.Thread(target=waiting)
    two.start()
    threading.Event().wait(0.2)  # let the second thread queue up on the lock
    release.set()
    one.join()
    two.join()

    assert results == {"failing": None, "waiting": None}
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]


def test_a_keyboard_interrupt_is_not_swallowed_and_does_not_latch(db, opened):
    writer = opened(db)
    rec = start(writer)
    proxy = break_writes(
        writer,
        lambda statement, args: statement.startswith("INSERT INTO steps"),
        KeyboardInterrupt(),
    )

    with pytest.raises(KeyboardInterrupt):
        rec.start("discovery", "KR")

    assert not rec.broken
    writer._con = proxy._real
    rec.end_run("FAILED", reason_code=rs.RUN_EXCEPTION, error_type="KeyboardInterrupt")
    writer.close()
    assert rows(db, "SELECT status FROM runs") == [("FAILED",)]
    assert_every_start_has_an_end(db, runs=1, steps=0)


@pytest.mark.parametrize(
    "call",
    [
        lambda rec: rec.start("discovery", "KR", surprise=1),
        lambda rec: rec.start("payment", "KR"),
        lambda rec: rec.start("delivery", "carrier_pigeon"),
        lambda rec: rec.start("artifact", "email"),
        lambda rec: rec.end(rec.start("discovery", "KR"), "ok", message="free text"),
        lambda rec: rec.end(rs.NO_RECORD.start("discovery", "KR"), "ok"),
        lambda rec: rec.end_run("RUNNING"),
        lambda rec: rec.end_run("COMPLETED", note="free text"),
    ],
    ids=[
        "unknown_start_fact",
        "unknown_kind",
        "unknown_delivery_target",
        "delivery_name_as_artifact",
        "unknown_end_fact",
        "handle_of_an_unrecorded_run",
        "not_an_end_status",
        "unknown_run_fact",
    ],
)
def test_a_call_the_contract_does_not_allow_is_a_failed_write(db, opened, call, caplog):
    first = rs.open_writer(db)
    rec = start(first)

    with caplog.at_level(logging.ERROR, logger="scheduler.run_state"):
        call(rec)  # never raises into the pipeline

    assert rec.broken
    # refused by the check written for it, not by whatever broke further on
    assert "(ValueError)" in caplog.text
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT status FROM runs") == [("INTERRUPTED",)]


def test_a_step_ends_once(db, opened):
    first = rs.open_writer(db)
    rec = start(first)
    step = rec.start("delivery", "email")
    rec.end(step, "ok")
    assert not rec.broken

    rec.end(step, "raised")

    assert rec.broken
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT state, outcome FROM steps") == [("ENDED", "ok")]
    assert rows(db, "SELECT count(*) FROM events WHERE event = 'step_ended'") == [(1,)]


def test_a_refused_statement_takes_the_whole_change_back(db, opened):
    """SQLite cancels only the statement that hit the constraint and leaves the
    transaction open; the code rolls back, so the UPDATE before it is undone."""
    first = rs.open_writer(db)
    rec = start(first)
    step = rec.start("delivery", "email")
    other = sqlite3.connect(db, isolation_level=None)
    other.execute(
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "VALUES (?, ?, 'step_interrupted', 'x', 'x', '{}')",
        (rec.run_id, step.step_id),
    )
    other.close()
    before = rows(db, "SELECT count(*) FROM events")

    rec.end(step, "ok")  # the UPDATE succeeds, the event INSERT is refused

    assert rec.broken
    assert not first._con.in_transaction
    assert rows(db, "SELECT state, outcome, ended_at FROM steps") == [
        ("STARTED", None, None)
    ]
    assert rows(db, "SELECT count(*) FROM events") == before
    abandon(first)


def test_the_code_refuses_a_second_end_before_the_file_has_to(db, opened, caplog):
    """Two guards say no to a second end: the transition check in the code and
    the unique index in the file. The code's check comes first."""
    first = rs.open_writer(db)
    rec = start(first)
    step = rec.start("delivery", "email")
    rec.end(step, "ok")

    with caplog.at_level(logging.ERROR, logger="scheduler.run_state"):
        rec.end(step, "raised")

    assert rec.broken
    assert "(ValueError)" in caplog.text and "IntegrityError" not in caplog.text
    abandon(first)


def test_the_code_refuses_a_second_run_end_before_the_file_has_to(db, opened, caplog):
    first = rs.open_writer(db)
    rec = start(first)
    rec.end_run("COMPLETED")

    with caplog.at_level(logging.ERROR, logger="scheduler.run_state"):
        rec.end_run("COMPLETED")

    assert rec.broken
    assert "(ValueError)" in caplog.text and "IntegrityError" not in caplog.text
    first.close()


def test_a_step_of_another_run_cannot_be_ended_here(db, opened):
    first = rs.open_writer(db)
    old = start(first)
    foreign_step = old.start("discovery", "KR")
    old.end_run("COMPLETED")  # closes the open step with it
    current = start(first)

    current.end(foreign_step, "ok")

    assert current.broken
    abandon(first)
    opened(db).close()
    assert rows(db, "SELECT state, outcome FROM steps") == [("INTERRUPTED", None)]


def test_nothing_starts_after_the_run_has_ended(db, opened):
    writer = opened(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    assert not rec.broken

    assert rec.start("delivery", "email") is None

    assert rec.broken
    writer.close()
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]
    assert_every_start_has_an_end(db, runs=1, steps=0)


def test_a_run_ends_once(db, opened):
    writer = opened(db)
    rec = start(writer)
    rec.end_run("COMPLETED")

    rec.end_run("FAILED", reason_code=rs.RUN_EXCEPTION)

    assert rec.broken
    writer.close()
    assert rows(db, "SELECT status FROM runs") == [("COMPLETED",)]
    assert rows(db, "SELECT count(*) FROM events WHERE event = 'run_ended'") == [(1,)]


def test_a_writer_has_one_open_run_at_a_time(db, opened):
    writer = opened(db)
    start(writer)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        start(writer)

    assert code_of(caught) == "START_NOT_RECORDED"
    assert rows(db, "SELECT count(*) FROM runs") == [(1,)]


def test_nothing_is_recorded_through_a_closed_writer(db, caplog):
    writer = rs.open_writer(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    writer.close()

    with caplog.at_level(logging.ERROR, logger="scheduler.run_state"):
        assert rec.start("discovery", "KR") is None
    assert rec.broken  # a failed write, not a silent skip
    assert "(ValueError)" in caplog.text  # the writer said so itself
    assert rows(db, "SELECT count(*) FROM steps") == [(0,)]


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "SELECT run_id, step_id, 'step_ended', 'x', 'x', '{}' FROM events "
        "WHERE event = 'step_ended'",
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "SELECT run_id, step_id, 'step_interrupted', 'x', 'x', '{}' FROM events "
        "WHERE event = 'step_ended'",
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "SELECT run_id, step_id, 'step_started', 'x', 'x', '{}' FROM events "
        "WHERE event = 'step_started'",
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "SELECT run_id, NULL, 'run_interrupted', 'x', 'x', '{}' FROM events "
        "WHERE event = 'run_ended'",
        "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
        "SELECT run_id, NULL, 'run_started', 'x', 'x', '{}' FROM events "
        "WHERE event = 'run_started'",
        "UPDATE steps SET state = 'SENT'",
        "UPDATE runs SET status = 'DONE'",
        "INSERT INTO events (run_id, event, ts, ts_kst, payload) "
        "SELECT run_id, 'note', 'x', 'x', '{}' FROM runs",
    ],
    ids=[
        "second_step_end",
        "interrupt_after_end",
        "second_step_start",
        "second_run_end",
        "second_run_start",
        "unknown_step_state",
        "unknown_run_status",
        "unknown_event",
    ],
)
def test_the_file_itself_refuses_what_the_code_must_never_write(db, statement):
    one_finished_run(db, steps=1)
    con = sqlite3.connect(db, isolation_level=None)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(statement)
    finally:
        con.close()
    assert_every_start_has_an_end(db, runs=1, steps=1)


def test_values_out_of_shape_do_not_fail_the_write(db, opened):
    writer = opened(db)
    rec = start(
        writer, markets=["KR", "not a market", 7], max_per_market=-1, dry_run="yes"
    )
    step = rec.start("valuation", 12345, ticker="not a ticker!", market="")
    rec.end(
        step,
        "exploded",
        reason_code="made up",
        severity="loud",
        degraded=["peers", "not_a_step", 3],
        error_type="not a class name",
        stage="nowhere",
    )
    other = rec.start("discovery", "K R")
    rec.end(other, "ok", news_count=-5, discovered=True, path="elsewhere")
    rec.end_run(
        "COMPLETED",
        errors="many",
        zero_selection="no",
        valuations_by_status={"success": 1, "weird": 2},
        summary_folder="../../etc",
        markets=[{"market": "KR", "reason_code": "nope", "selected": 1}, "junk"],
    )
    writer.close()

    assert not rec.broken
    run = rs.read_run(db, rec.run_id)
    assert run["run"]["markets"] == ["KR", "<invalid>", "<invalid>"]
    assert (run["run"]["max_per_market"], run["run"]["dry_run"]) == (None, False)
    valuation, discovery = run["steps"]
    assert valuation["target"] == "<invalid>"
    assert (valuation["outcome"], valuation["reason_code"], valuation["severity"]) == (
        "<invalid>",
        "<invalid>",
        "<invalid>",
    )
    assert valuation["facts"] == {
        "ticker": "<invalid>",
        "market": "<invalid>",
        "degraded": ["peers", "<invalid>", "<invalid>"],
        "error_type": "<invalid>",
        "stage": "<invalid>",
    }
    assert discovery["target"] == "<invalid>"
    assert discovery["facts"] == {
        "news_count": None,
        "discovered": None,
        "path": "<invalid>",
    }
    assert run["run"]["facts"] == {
        "errors": None,
        "zero_selection": None,
        "valuations_by_status": {"success": 1, "<invalid>": 2},
        "summary_folder": "<invalid>",
        "markets": [
            {
                "market": "KR",
                "reason_code": "<invalid>",
                "severity": None,
                "news_count": None,
                "discovered": None,
                "selected": 1,
                "selected_after_budget_trim": None,
            }
        ],
    }
    assert_every_start_has_an_end(db, runs=1, steps=2)


# ── 6. nothing secret is stored ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "name",
    [
        "SK-Hynix",
        "AT&T",
        "Basic Energy Services",
        "삼성E&A",
        "Novo Nordisk A/S",
        "Moody's Corporation",
        "Yum! Brands",
        "T. Rowe Price Group",
        "Berkshire Hathaway Inc. (Class B)",
    ],
)
def test_real_company_names_are_kept_as_they_are(name):
    assert rs._label(name) == name


@pytest.mark.parametrize(
    "value",
    [
        TOKEN_NAME,
        LONG_NAME,
        WINDOWS_PATH,
        POSIX_PATH,
        "~/secrets/report",
        "D:/data/report.xlsx",
        "reports/2026/q3.xlsx",
        "private/report.xlsx",
        "./report.xlsx",
        "../up/report",
        "C:report.xlsx",
        "see ./notes.txt",
        # one sample that only its own rule catches, per rule
        "reports/2026/q3",  # two slashes
        "/etc",  # starts with a slash
        "~secrets",  # starts with a tilde
        "./report",  # ./x
        "../report",  # ../x
        "(D:/data)",  # a drive letter inside brackets
        "Bearer abcdefghijklmnop1234",  # a 20-character bearer token
        "sk-abcdefghijklmnop12",  # an sk- token shorter than 32
        "\\\\server\\share\\file",
        "https://example.test/list.json?crtfc_key=" + SECRET_QUERY,
        "see crtfc_key=" + SECRET_QUERY,
        "Authorization: Bearer " + SECRET_BEARER,
        "bearer " + SECRET_BEARER,
        "sk-" + SECRET_SK,
        "password = hunter2",
        "sk-\x00" + SECRET_SK,  # a control character must not hide the shape
    ],
    ids=lambda value: value[:18].encode("unicode_escape").decode(),
)
def test_a_name_that_looks_like_a_credential_or_a_path_is_replaced_whole(value):
    assert rs._label(value) == "<masked>"


@pytest.mark.parametrize(
    "value",
    [
        "private/report",  # one slash, no extension: reads like a name ending in A/S
        "private/report.parquet",  # an extension of more than five characters
        "private/report.xlsx,",  # punctuation right after the extension
        "private/report.한글",  # an extension that is not ASCII
    ],
)
def test_what_the_name_filter_does_not_claim(value):
    """The filter covers the shapes it lists, not every path. These stay."""
    assert rs._label(value) == value


def test_a_name_is_examined_before_it_is_cut():
    assert len(LONG_NAME) > 120 and LONG_NAME.index(TOKEN_TAIL) < 120
    # cut first and the 32-character rule no longer sees the token: its head stays
    cut_first = LONG_NAME[:120]
    assert TOKEN_TAIL[:10] in cut_first
    assert not any(shape.search(cut_first) for shape in rs._UNWANTED_IN_NAME)

    assert rs._label(LONG_NAME) == "<masked>"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("line one\nline two", "line one line two"),
        ("  padded \t name  ", "padded name"),
        (" ".join(["word"] * 40), " ".join(["word"] * 40)[:120]),
        ("", "<invalid>"),
        ("\x00\x1f", "<invalid>"),
        (None, "<invalid>"),
        (12345, "<invalid>"),
        (["a list"], "<invalid>"),
        ("n" * 801, "<invalid>"),
    ],
    ids=[
        "two_lines",
        "padded",
        "cut_at_120",
        "empty",
        "controls_only",
        "none",
        "number",
        "list",
        "over_800",
    ],
)
def test_a_name_is_one_bounded_line(value, expected):
    assert rs._label(value) == expected


@pytest.mark.parametrize(
    "check, value, expected",
    [
        # exception class names: 31 characters, whatever the name ends with
        (rs._class_name, "KeyError", "KeyError"),
        (rs._class_name, "_Private2", "_Private2"),
        (rs._class_name, "A" * 31, "A" * 31),
        (rs._class_name, "A" * 32, "<invalid>"),
        (rs._class_name, TOKEN_CLASS, "<invalid>"),
        (rs._class_name, "A" * 40 + "Error", "<invalid>"),
        (rs._class_name, "A" * 40 + "Exception", "<invalid>"),
        (rs._class_name, "A" * 40 + "Warning", "<invalid>"),
        (rs._class_name, "ElementClickInterceptedException", "<invalid>"),  # 32
        (rs._class_name, "Bad Name", "<invalid>"),
        (rs._class_name, None, None),
        (rs._class_name, 404, "<invalid>"),
        # market codes: 16 characters
        (rs._market, "KR", "KR"),
        (rs._market, "M" * 16, "M" * 16),
        (rs._market, "M" * 17, "<invalid>"),
        (rs._market, "K R", "<invalid>"),
        (rs._market, None, "<invalid>"),
        # tickers: 12 characters
        (rs._ticker, "005930", "005930"),
        (rs._ticker, 5930, "5930"),
        (rs._ticker, "BRK.B", "BRK.B"),
        (rs._ticker, "T" * 12, "T" * 12),
        (rs._ticker, "T" * 13, "<invalid>"),
        (rs._ticker, "-AAPL", "<invalid>"),
        (rs._ticker, None, None),
        (rs._ticker, True, "<invalid>"),
        # values from fixed lists: a well-formed stranger is still refused
        (rs._reason, "NEWS_EMPTY", "NEWS_EMPTY"),
        (rs._reason, "NO_END_RECORDED", "NO_END_RECORDED"),
        (rs._reason, "WELL_FORMED_BUT_UNKNOWN", "<invalid>"),
        (rs._reason, None, None),
        (rs._reason, ["NEWS_EMPTY"], "<invalid>"),
        (rs._severity, "failure", "failure"),
        (rs._severity, "critical", "<invalid>"),
        (rs._stage, "identify", "identify"),
        (rs._stage, "result", "result"),
        (rs._stage, "wherever", "<invalid>"),
        (rs._discovery_path, "news_llm", "news_llm"),
        (rs._discovery_path, "somewhere", "<invalid>"),
        (rs._folder, "2026-11-14(Nov 2nd week)", "2026-11-14(Nov 2nd week)"),
        (rs._folder, "2026-11-14(Nov 2nd week)/..", "<invalid>"),
        (rs._folder, WINDOWS_PATH, "<invalid>"),
        # counts and flags
        (rs._count, 0, 0),
        (rs._count, 10**9, 10**9),
        (rs._count, 10**9 + 1, None),
        (rs._count, -1, None),
        (rs._count, True, None),
        (rs._count, 1.5, None),
        (rs._flag, False, False),
        (rs._flag, 0, None),
    ],
)
def test_what_each_field_accepts(check, value, expected):
    assert check(value) == expected


def test_lists_are_read_only_so_far():
    assert rs._degraded(["peers"] * 50) == ["peers"] * 20
    assert rs._degraded("peers") == []
    assert rs._markets(["KR"] * 20) == ["KR"] * 8
    assert rs._market_rows([{"market": "KR"}] * 20)[8:] == []


def test_no_field_that_cannot_be_listed_is_long_enough_for_a_token():
    """Every stored string is from a fixed list, a short shape, or a display name."""
    for value in (TOKEN_NAME, TOKEN_CLASS, SECRET_QUERY):  # 40, 40 and 32 characters
        assert rs._market(value) == "<invalid>"
        assert rs._ticker(value) == "<invalid>"
        assert rs._class_name(value) == "<invalid>"
        assert rs._reason(value) == "<invalid>"
        assert rs._severity(value) == "<invalid>"
        assert rs._stage(value) == "<invalid>"
        assert rs._discovery_path(value) == "<invalid>"
        assert rs._folder(value) == "<invalid>"
        assert rs._degraded([value]) == ["<invalid>"]
        assert rs._outcome("delivery", value) == "<invalid>"
        assert rs._label(value) == "<masked>"


# ── 7. the exported event file ───────────────────────────────────────────────


def export_path(db: Path, run_id: str) -> Path:
    return db.parent / run_id / "events.jsonl"


def test_the_export_is_the_database_line_for_line(db):
    run_id = one_finished_run(db, steps=3)
    data = export_path(db, run_id).read_bytes()
    lines = data.decode("utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert data.endswith(b"\n") and b"\r" not in data
    assert events == rs.read_events(db, run_id)
    assert [e["seq"] for e in events] == sorted({e["seq"] for e in events})
    assert events[0]["event"] == "run_started" and events[-1]["event"] == "run_ended"
    assert len(events) == 2 + 2 * 3
    assert all(e["schema"] == 1 and e["run_id"] == run_id for e in events)
    assert lines == [
        json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for e in events
    ]
    assert rows(db, "SELECT exported_seq FROM runs") == [(events[-1]["seq"],)]
    assert sorted(p.name for p in export_path(db, run_id).parent.iterdir()) == [
        "events.jsonl"
    ]


def test_exporting_again_gives_the_same_bytes(db, opened):
    run_id = one_finished_run(db, steps=4)
    target = export_path(db, run_id)
    first = target.read_bytes()
    target.unlink()

    writer = opened(db)
    with writer._mutex:
        writer._export_run(run_id)
    writer.close()

    assert target.read_bytes() == first


def test_a_deleted_export_is_not_recreated_behind_your_back(db):
    """exported_seq says it was exported; pruning old folders stays pruned."""
    run_id = one_finished_run(db)
    export_path(db, run_id).unlink()

    rs.open_writer(db).close()

    assert not export_path(db, run_id).exists()


def test_a_company_name_in_korean_is_exported_as_utf8(db):
    writer = rs.open_writer(db)
    rec = start(writer)
    step = rec.start("valuation", "삼성E&A", ticker="028050", market="KR")
    rec.end(step, "success", degraded=[])
    rec.end_run("COMPLETED")
    writer.close()

    data = export_path(db, rec.run_id).read_bytes()
    assert "삼성E&A".encode("utf-8") in data


def test_replace_is_retried_while_a_reader_holds_the_file(db, monkeypatch):
    attempts = []
    real_replace = os.replace

    def busy_twice(source, target):
        attempts.append(target)
        if len(attempts) <= 2:
            raise PermissionError(13, "held by a reader")
        return real_replace(source, target)

    monkeypatch.setattr(rs.os, "replace", busy_twice)
    monkeypatch.setattr(rs.time, "sleep", lambda seconds: None)

    run_id = one_finished_run(db)

    assert len(attempts) == 3
    assert export_path(db, run_id).exists()


def test_a_failed_export_changes_no_result_and_the_next_writer_makes_it_up(
    db, monkeypatch
):
    def always_busy(source, target):
        raise PermissionError(13, "held by a reader")

    monkeypatch.setattr(rs.time, "sleep", lambda seconds: None)
    with monkeypatch.context() as patch:
        patch.setattr(rs.os, "replace", always_busy)
        run_id = one_finished_run(db)  # close() does not raise

    folder = db.parent / run_id
    assert (
        sorted(p.name for p in folder.iterdir()) == []
    )  # no half file, no scratch file
    assert rows(db, "SELECT status, exported_seq FROM runs") == [("COMPLETED", None)]

    rs.open_writer(db).close()

    events = [
        json.loads(line)
        for line in export_path(db, run_id).read_text("utf-8").splitlines()
    ]
    assert events[-1]["event"] == "run_ended"
    assert rows(db, "SELECT exported_seq FROM runs") == [(events[-1]["seq"],)]


def test_when_the_export_ledger_cannot_be_updated_the_file_is_exported_again(db):
    writer = rs.open_writer(db)
    rec = start(writer)
    rec.end_run("COMPLETED")
    break_writes(
        writer,
        lambda statement, args: statement.startswith("UPDATE runs SET exported_seq"),
    )

    writer.close()  # cleanup: never raises

    target = export_path(db, rec.run_id)
    first = target.read_bytes()
    assert rows(db, "SELECT status, exported_seq FROM runs") == [("COMPLETED", None)]
    rs.open_writer(db).close()
    assert target.read_bytes() == first
    assert rows(db, "SELECT exported_seq FROM runs") != [(None,)]


@pytest.mark.skipif(
    os.name != "nt",
    reason="only Windows refuses os.replace() onto a file that another handle has open",
)
def test_an_open_reader_handle_keeps_the_old_file_whole(db, opened, monkeypatch):
    first = rs.open_writer(db)
    rec = start(first)
    rec.start("delivery", "email")
    abandon(first)
    rs.open_writer(db).close()  # recovery exports the interrupted run
    target = export_path(db, rec.run_id)
    old = target.read_bytes()
    con = sqlite3.connect(db, isolation_level=None)
    con.execute(
        "UPDATE runs SET exported_seq = NULL"
    )  # make the next writer export again
    con.close()
    monkeypatch.setattr(rs.time, "sleep", lambda seconds: None)

    with open(target, "rb") as held:
        rs.open_writer(db).close()  # the replace fails five times and is given up
        assert held.read() == old

    assert target.read_bytes() == old
    assert sorted(p.name for p in target.parent.iterdir()) == ["events.jsonl"]
    assert rows(db, "SELECT exported_seq FROM runs") == [(None,)]
    rs.open_writer(db).close()
    assert rows(db, "SELECT exported_seq FROM runs") != [(None,)]


def test_a_run_id_that_is_not_a_safe_folder_name_is_never_used_as_a_path(db, tmp_path):
    one_finished_run(db)
    con = sqlite3.connect(db, isolation_level=None)
    con.execute(
        "INSERT INTO runs (run_id, status, started_at, started_at_kst, pid, dry_run, "
        "markets, facts) VALUES ('../escaped', 'COMPLETED', 'x', 'x', 1, 0, '[]', '{}')"
    )
    con.execute(
        "INSERT INTO events (run_id, event, ts, ts_kst, payload) "
        "VALUES ('../escaped', 'run_started', 'x', 'x', '{}')"
    )
    con.close()
    before = sorted(p.name for p in tmp_path.iterdir())

    rs.open_writer(db).close()  # never raises; the odd row is skipped

    assert sorted(p.name for p in tmp_path.iterdir()) == before
    assert not (tmp_path / "escaped").exists()


# ── 8. time ──────────────────────────────────────────────────────────────────


def test_timestamps_are_one_instant_in_utc_and_kst(db):
    clock = Clock()
    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    rec = start(writer)
    clock.tick(2.5)
    step = rec.start("discovery", "KR")
    clock.tick(1.25)
    rec.end(step, "ok")
    clock.tick(0.25)
    rec.end_run("COMPLETED")
    writer.close()

    run = rs.read_run(db, rec.run_id)
    assert run["run"]["started_at"] == "2026-11-17T01:02:03.456+00:00"
    assert run["run"]["started_at_kst"] == "2026-11-17T10:02:03.456+09:00"
    assert run["run"]["ended_at"] == "2026-11-17T01:02:07.456+00:00"
    assert rec.run_id.startswith("wr-20261117T010203Z-")
    assert (run["steps"][0]["duration_ms"], run["run"]["duration_ms"]) == (1250, 4000)
    for event in rs.read_events(db, rec.run_id):
        assert datetime.fromisoformat(event["ts"]) == datetime.fromisoformat(
            event["ts_kst"]
        )
        assert event["ts"].endswith("+00:00") and event["ts_kst"].endswith("+09:00")


def test_durations_and_order_do_not_follow_the_wall_clock(db):
    clock = Clock()
    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    rec = start(writer)
    step = rec.start("discovery", "KR")
    clock.tick(3.0, wall=-7200)  # the wall clock is set back two hours
    rec.end(step, "ok")
    rec.end_run("COMPLETED")
    writer.close()

    events = rs.read_events(db, rec.run_id)
    assert [e["event"] for e in events] == [
        "run_started",
        "step_started",
        "step_ended",
        "run_ended",
    ]
    assert events[2]["ts"] < events[1]["ts"]  # time went backwards; the order did not
    assert events[2]["duration_ms"] == 3000


def test_a_clock_without_a_time_zone_is_refused(db):
    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.open_writer(db, now=lambda: datetime(2026, 11, 17, 1, 2, 3))

    assert code_of(caught) == "DB_UNAVAILABLE"
    rs.open_writer(db).close()  # the seat was given back


# ── 12. reading ──────────────────────────────────────────────────────────────

ODD_FOLDERS = [
    pytest.param("state#snapshot", id="hash"),
    pytest.param("100%done", id="percent"),
    pytest.param("my runs", id="space"),
    pytest.param("실행 기록", id="korean"),
    pytest.param(
        "what?now",
        id="question_mark",
        marks=pytest.mark.skipif(
            os.name == "nt", reason="Windows does not allow '?' in a file name"
        ),
    ),
]


@pytest.mark.parametrize("folder", ODD_FOLDERS)
def test_paths_with_characters_a_uri_treats_specially(tmp_path, folder):
    """Pasted into a URI as text, '#' cuts the path short: another file is
    opened (and created) and mode=ro is lost."""
    db = tmp_path / "base" / folder / "state.db"
    run_id = one_finished_run(db, steps=1)

    assert [r["run_id"] for r in rs.read_runs(db)] == [run_id]
    assert len(rs.read_events(db, run_id)) == 4
    assert rs.read_run(db, run_id)["steps"][0]["state"] == "ENDED"
    con = rs._open_reader(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            con.execute("INSERT INTO runs (run_id) VALUES ('written-by-a-reader')")
    finally:
        con.close()
    assert sorted(p.name for p in (tmp_path / "base").iterdir()) == [folder]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["base"]


def test_reading_does_not_create_a_missing_file(db):
    for read in (
        lambda: rs.read_runs(db),
        lambda: rs.read_run(db, "wr-x"),
        lambda: rs.read_events(db, "wr-x"),
    ):
        with pytest.raises(rs.RunStateUnavailable) as caught:
            read()
        assert code_of(caught) == "DB_UNAVAILABLE"
    assert not db.exists() and not db.parent.exists()


@pytest.mark.parametrize(
    "make, code",
    [
        (_foreign_with_a_table, "DB_FOREIGN"),
        (_zero_bytes, "DB_FOREIGN"),
        (_a_later_schema_version, "SCHEMA_UNSUPPORTED"),
        (_garbage, "DB_CORRUPT"),
    ],
    ids=lambda value: getattr(value, "__name__", value).lstrip("_"),
)
def test_reading_refuses_a_file_that_is_not_a_run_state_database(db, make, code):
    make(db)
    before = digest(db)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        rs.read_runs(db)

    assert code_of(caught) == code
    assert digest(db) == before


def test_what_the_reading_functions_return(db):
    first = one_finished_run(db, steps=1)
    second = one_finished_run(db, steps=2)

    listed = rs.read_runs(db)
    assert {r["run_id"] for r in listed} == {first, second}
    assert len(rs.read_runs(db, limit=1)) == 1
    assert rs.read_run(db, "wr-00000000T000000Z-00000000") is None
    detail = rs.read_run(db, second)
    assert sorted(detail) == ["run", "steps"]
    assert [s["target"] for s in detail["steps"]] == ["Company 0", "Company 1"]
    assert detail["steps"][0]["facts"] == {
        "ticker": "AAPL",
        "market": "US",
        "degraded": [],
    }
    assert isinstance(detail["run"]["markets"], list)
    assert isinstance(detail["run"]["dry_run"], bool)
    assert rs.read_events(db, "wr-00000000T000000Z-00000000") == []


def test_a_reader_sees_committed_rows_while_the_writer_is_inside_a_transaction(
    db, opened
):
    writer = opened(db)
    rec = start(writer)
    writer._con.execute("BEGIN IMMEDIATE")
    writer._con.execute(
        "INSERT INTO steps (run_id, kind, target, state, started_at, started_at_kst, facts) "
        "VALUES (?, 'discovery', 'KR', 'STARTED', 'x', 'x', '{}')",
        (rec.run_id,),
    )

    seen = rs.read_run(db, rec.run_id)

    writer._con.execute("ROLLBACK")
    assert seen["run"]["status"] == "RUNNING" and seen["steps"] == []


def test_an_open_reader_does_not_stop_the_writer(db, opened):
    writer = opened(db)
    rec = start(writer)
    reader = rs._open_reader(db)
    try:
        reader.execute("BEGIN")
        assert reader.execute("SELECT count(*) FROM runs").fetchone() == (1,)

        step = rec.start("discovery", "KR")
        rec.end(step, "ok")
        rec.end_run("COMPLETED")
    finally:
        reader.close()
    writer.close()

    assert not rec.broken
    assert_every_start_has_an_end(db, runs=1, steps=1)


# ── 9. wired into the weekly run ─────────────────────────────────────────────


def _module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


class Weekly:
    """Every side-effecting boundary of run_weekly() replaced by a recorder.

    ``on[name]`` runs when the boundary ``name`` is reached, before it answers;
    a value that is an exception is raised instead of being returned.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.results = tmp_path / "results"
        self.db = tmp_path / "runs" / "state.db"
        self.discovered: dict[str, object] = {"KR": [], "US": []}
        self.analysis: dict[str, object] = {}  # company name -> what auto_analyze does
        self.upload: object = (
            True  # True: all get a URL, "half", False, or an exception
        )
        self.mail: object = True
        self.wordpress: object = "https://wp.example/post/1"
        self.naver: object = None
        self.on: dict[str, object] = {}
        self.calls: list[str] = []
        self.alerts: list[tuple[str, str]] = []
        self.db_updates: list[tuple[str, dict]] = []
        self.writers: list = []
        self._lock = threading.Lock()
        self.wr = None

    def reach(self, name: str, answer: object = None) -> object:
        with self._lock:
            self.calls.append(name)
        hook = self.on.get(name)
        if hook is not None:
            hook()
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def called(self, prefix: str) -> list[str]:
        return [name for name in self.calls if name.startswith(prefix)]

    def discover(self, market: str) -> dict:
        companies = self.reach("discover:" + market, self.discovered.get(market, []))
        companies = [dict(c) for c in companies]
        news = [
            {
                "title": f"{c['name']} quarterly results",
                "description": "",
                "link": f"https://news.example/{market}/{index}",
                "pub_date": "2020-01-06T09:00:00",
                "source": "naver" if market == "KR" else "google_rss",
            }
            for index, c in enumerate(companies)
        ]
        return {
            "news_count": len(news),
            "analysis": "",
            "companies": companies,
            "scenarios": [],
            "news": news,
            "reason_code": None if companies else "NO_CANDIDATES",
            "reason_detail": {},
            "path": "news_llm",
            "path_fallback": None,
            "candidates_raw": len(companies),
            "candidates_filtered_out": 0,
        }

    def auto_analyze(self, query, output_dir=None, scored_data=None, diagnostics=None):
        name = (scored_data or {}).get("name", query)
        what = self.analysis.get(name, "success")
        if callable(what):
            what = what(diagnostics)
        what = self.reach("analyze:" + name, what)
        if what == "none":
            diagnostics["reason_code"] = "IDENTITY_NOT_FOUND"
            diagnostics["reason_detail"] = {}
            return None
        if what == "none-as-reported":  # whatever the callable put in diagnostics
            return None
        if what == "degraded":
            diagnostics["degraded"] = [{"step": "peers"}, {"step": "wacc"}]
        draft = what == "draft"
        return types.SimpleNamespace(
            result=types.SimpleNamespace(
                draft=draft,
                quality=None,
                investability_blockers=["auto_generated"] if draft else [],
            ),
            validation_report=None,
            excel_path=f"workbooks/{name[:20]}.xlsx",
            summary_md="",
        )

    def upload_excels(self, summary: dict, folder: str) -> None:
        self.reach(
            "excel_upload",
            self.upload if isinstance(self.upload, BaseException) else None,
        )
        eligible = [
            v
            for v in summary["valuations"]
            if v["status"] == "success" and v.get("excel_path")
        ]
        if self.upload is True:
            chosen = eligible
        elif self.upload == "half":
            chosen = eligible[: len(eligible) // 2]
        else:
            chosen = []
        for entry in chosen:
            entry["download_url"] = "https://storage.example/workbook.xlsx"

    def summary_on_disk(self) -> dict:
        (path,) = self.results.rglob("_weekly_summary.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def run_recorded(self, **kwargs) -> dict:
        kwargs.setdefault("markets", ["KR", "US"])
        return self.wr.run_weekly_recorded(**kwargs)

    def only_run(self) -> dict:
        (run,) = rs.read_runs(self.db)
        return rs.read_run(self.db, run["run_id"])

    def steps(self) -> list[tuple]:
        return sorted(
            (s["kind"], s["target"], s["state"], s["outcome"])
            for s in self.only_run()["steps"]
        )

    def break_recording(self, fail=lambda statement, args: True):
        return break_writes(self.writers[-1], fail)


class _FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 11, 14, 9, 0, 0)


@pytest.fixture
def env_guard():
    """The process environment after a test is what it was before it.

    Requested ahead of ``monkeypatch`` so that it is torn down after it. Only
    names are compared and reported, never values.
    """
    before = {key: hash(value) for key, value in os.environ.items()}
    yield
    after = {key: hash(value) for key, value in os.environ.items()}
    changed = sorted(
        key
        for key in set(before) | set(after)
        if key != "PYTEST_CURRENT_TEST" and before.get(key) != after.get(key)
    )
    assert changed == [], f"environment not restored for: {changed}"


@pytest.fixture
def weekly(env_guard, monkeypatch, tmp_path):
    h = Weekly(tmp_path)

    monkeypatch.setenv("BVT_TELEMETRY", "0")
    # _ssl_fix returns early when this is set. pipeline/yfinance_fetcher.py sets
    # it at import time whenever the certifi path is not ASCII, so pre-seed the
    # very value it would write and let monkeypatch restore the original state.
    ca_bundle = os.path.join(
        os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "python-ssl", "cacert.pem"
    )
    monkeypatch.setenv("CURL_CA_BUNDLE", os.environ.get("CURL_CA_BUNDLE") or ca_bundle)
    # scheduler.weekly_run and cli load the repository's .env on first import.
    try:
        import dotenv
    except ImportError:
        dotenv = None
    if dotenv is not None:
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    wr = importlib.import_module("scheduler.weekly_run")
    h.wr = wr
    for name in list(os.environ):
        upper = name.upper()
        if any(
            marker in upper
            for marker in (
                "OPENROUTER",
                "ANTHROPIC_API",
                "NAVER",
                "DART_API",
                "SUPABASE",
                "GMAIL",
                "RESEND",
                "DUMP_NEWS_TITLES",
                "BVT_TELEMETRY_PATH",
            )
        ):
            monkeypatch.delenv(name, raising=False)

    monkeypatch.setattr(wr, "_RESULTS_BASE", h.results)
    monkeypatch.setattr(wr, "_RUN_STATE_DB", h.db)
    monkeypatch.setattr(wr, "_LOCK_PATH", tmp_path / "logs" / ".weekly_run.lock")
    monkeypatch.setattr(wr, "_setup_logging", lambda: None)
    monkeypatch.setattr(wr, "datetime", _FixedDatetime)
    monkeypatch.setattr(
        wr, "_alert", lambda phase, error: h.alerts.append((phase, error))
    )
    monkeypatch.setattr(wr, "_save_run_start", lambda markets: "supabase-run")
    monkeypatch.setattr(wr, "_upload_excels_to_storage", h.upload_excels)
    monkeypatch.setitem(
        sys.modules,
        "db.repository",
        _module(
            "db.repository",
            update_discovery_run=lambda run_id, updates: h.db_updates.append(
                (run_id, updates)
            ),
        ),
    )
    monkeypatch.setattr(
        "discovery.discovery_engine.DiscoveryEngine.discover",
        lambda self, market="KR": h.discover(market),
    )
    guard = types.SimpleNamespace(get_usage_summary=lambda: {})
    monkeypatch.setattr(
        "pipeline.api_guard.ApiGuard.get", classmethod(lambda cls: guard)
    )
    monkeypatch.setattr(
        "pipeline.api_guard.estimate_weekly_cost",
        lambda markets, n: {
            "estimated_api_calls": {},
            "estimated_llm_calls": 0,
            "estimated_llm_cost_usd": 0.0,
            "remaining_quota": {"anthropic": 1000},
        },
    )
    monkeypatch.setattr(
        "scheduler.scoring._fetch_market_cap_usd", lambda ticker, market: None
    )
    monkeypatch.setitem(
        sys.modules,
        "pipeline.profile_generator",
        _module("pipeline.profile_generator", auto_analyze=h.auto_analyze),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.email_sender",
        _module(
            "scheduler.email_sender",
            send_weekly_email=lambda summary: h.reach("email", h.mail),
            send_error_alert=lambda phase, error: h.alerts.append((phase, error)),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.wp_poster",
        _module(
            "scheduler.wp_poster",
            post_to_wordpress=lambda s: h.reach("wordpress", h.wordpress),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "scheduler.naver_poster",
        _module(
            "scheduler.naver_poster", post_to_naver=lambda s: h.reach("naver", h.naver)
        ),
    )

    real_open_writer = rs.open_writer

    def remembering_open_writer(path, **kwargs):
        writer = real_open_writer(path, **kwargs)
        h.writers.append(writer)
        return writer

    monkeypatch.setattr(rs, "open_writer", remembering_open_writer)
    h.open_writer = real_open_writer

    yield h

    for writer in h.writers:
        writer.close()


KR_TWO = [
    {"name": "Alpha Electronics", "ticker": "005930", "reason": "earnings"},
    {"name": "Beta Chemical", "ticker": "051910", "reason": "guidance"},
]
US_ONE = [{"name": "Gamma Software", "ticker": "GAMA", "reason": "results"}]


def test_run_weekly_called_directly_records_nothing(weekly):
    weekly.discovered = {"KR": KR_TWO}

    summary = weekly.wr.run_weekly(markets=["KR"], dry_run=True)

    assert "local_run_id" not in summary
    assert "local_run_id" not in weekly.summary_on_disk()
    assert not weekly.db.parent.exists()  # no folder, no database, no lock file
    assert weekly.writers == []


def test_a_recorded_run_differs_from_an_unrecorded_one_by_one_key(weekly, monkeypatch):
    weekly.discovered = {"KR": KR_TWO, "US": US_ONE}
    weekly.analysis = {"Beta Chemical": "none"}

    plain = weekly.wr.run_weekly(markets=["KR", "US"])
    plain_saved = weekly.summary_on_disk()
    monkeypatch.setattr(weekly.wr, "_RESULTS_BASE", weekly.tmp / "results-recorded")
    weekly.results = weekly.tmp / "results-recorded"
    recorded = weekly.run_recorded(markets=["KR", "US"])
    recorded_saved = weekly.summary_on_disk()

    def comparable(summary: dict) -> dict:
        shown = {
            k: v for k, v in summary.items() if k not in ("local_run_id", "week_dir")
        }
        shown["valuations"] = sorted(shown["valuations"], key=lambda v: v["company"])
        shown["errors"] = sorted(
            shown["errors"], key=lambda e: json.dumps(e, sort_keys=True)
        )
        shown["discoveries"] = sorted(shown["discoveries"], key=lambda d: d["market"])
        return shown

    assert set(recorded) - set(plain) == {"local_run_id"} and set(plain) <= set(
        recorded
    )
    assert comparable(recorded) == comparable(plain)
    assert comparable(recorded_saved) == comparable(plain_saved)
    assert recorded_saved["local_run_id"] == weekly.only_run()["run"]["run_id"]
    assert rs._RUN_ID.fullmatch(recorded["local_run_id"])


def test_a_full_week_is_recorded_step_by_step(weekly):
    weekly.discovered = {"KR": KR_TWO, "US": US_ONE}
    weekly.analysis = {
        "Alpha Electronics": "degraded",
        "Beta Chemical": "none",
        "Gamma Software": RuntimeError("valuation exploded"),
    }
    weekly.wordpress = None
    weekly.naver = RuntimeError("selenium died")

    summary = weekly.run_recorded()

    assert weekly.steps() == [
        ("artifact", "summary_file", "ENDED", "ok"),
        ("delivery", "email", "ENDED", "ok"),
        ("delivery", "excel_upload", "ENDED", "ok"),
        ("delivery", "naver", "ENDED", "raised"),
        ("delivery", "wordpress", "ENDED", "no_result"),
        ("discovery", "KR", "ENDED", "ok"),
        ("discovery", "US", "ENDED", "ok"),
        ("valuation", "Alpha Electronics", "ENDED", "success"),
        ("valuation", "Beta Chemical", "ENDED", "no_result"),
        ("valuation", "Gamma Software", "ENDED", "failed"),
    ]
    recorded = weekly.only_run()
    by_target = {s["target"]: s for s in recorded["steps"]}
    assert by_target["Alpha Electronics"]["facts"] == {
        "ticker": "005930",
        "market": "KR",
        "degraded": ["peers", "wacc"],
        "error_type": None,
        "stage": None,
    }
    assert (
        by_target["Beta Chemical"]["reason_code"],
        by_target["Beta Chemical"]["severity"],
    ) == (
        "IDENTITY_NOT_FOUND",
        "failure",
    )
    assert by_target["Gamma Software"]["reason_code"] == "VALUATION_EXCEPTION"
    assert by_target["Gamma Software"]["facts"]["error_type"] == "RuntimeError"
    assert by_target["Gamma Software"]["facts"]["stage"] == "start"
    assert by_target["naver"]["facts"] == {"error_type": "RuntimeError"}
    assert by_target["excel_upload"]["facts"] == {"eligible": 1, "uploaded": 1}
    assert by_target["KR"]["facts"] == {
        "news_count": 2,
        "discovered": 2,
        "path": "news_llm",
    }
    run = recorded["run"]
    assert (run["status"], run["dry_run"], run["markets"]) == (
        "COMPLETED_WITH_ERRORS",
        False,
        ["KR", "US"],
    )
    assert run["facts"]["errors"] == len(summary["errors"]) > 0
    assert run["facts"]["valuations_by_status"] == {
        "success": 1,
        "no_result": 1,
        "failed": 1,
    }
    assert run["facts"]["valuations_total"] == 3
    assert run["facts"]["summary_folder"] == summary["folder_name"]
    assert (run["facts"]["targets_selected"], run["facts"]["zero_selection"]) == (
        3,
        False,
    )
    assert [row["market"] for row in run["facts"]["markets"]] == ["KR", "US"]
    assert summary["local_run_id"] == run["run_id"]
    assert weekly.called("email") == ["email"] and weekly.called("naver") == ["naver"]
    assert_every_start_has_an_end(weekly.db, runs=1, steps=10)
    assert (weekly.db.parent / run["run_id"] / "events.jsonl").exists()
    weekly.open_writer(weekly.db).close()  # the seat was given back


def test_a_dry_run_is_recorded_without_deliveries(weekly):
    weekly.discovered = {"KR": KR_TWO}

    weekly.run_recorded(markets=["KR", "US"], dry_run=True)

    assert weekly.steps() == [
        ("artifact", "summary_file", "ENDED", "ok"),
        ("discovery", "KR", "ENDED", "ok"),
        ("discovery", "US", "ENDED", "empty"),
    ]
    run = weekly.only_run()
    assert (run["run"]["status"], run["run"]["dry_run"]) == (
        "COMPLETED_WITH_ERRORS",
        True,
    )
    us = [s for s in run["steps"] if s["target"] == "US"][0]
    assert (us["reason_code"], us["severity"]) == ("NO_CANDIDATES", "empty")
    assert weekly.called("analyze:") == [] and weekly.called("email") == []
    assert_every_start_has_an_end(weekly.db, runs=1, steps=3)


def test_the_default_markets_are_recorded_as_the_run_uses_them(weekly):
    weekly.wr.run_weekly_recorded(dry_run=True)

    assert weekly.only_run()["run"]["markets"] == ["KR", "US"]
    assert sorted(weekly.called("discover:")) == ["discover:KR", "discover:US"]


def test_a_market_given_twice_gets_a_step_each_time(weekly):
    weekly.discovered = {"KR": KR_TWO}

    weekly.run_recorded(markets=["KR", "KR"], dry_run=True)

    assert [s[:2] for s in weekly.steps()].count(("discovery", "KR")) == 2
    assert_every_start_has_an_end(weekly.db, runs=1, steps=3)


def test_a_discovery_that_raises_is_recorded_as_failed(weekly):
    weekly.discovered = {"KR": KR_TWO, "US": RuntimeError("feed down")}

    weekly.run_recorded(dry_run=True)

    us = [s for s in weekly.only_run()["steps"] if s["target"] == "US"][0]
    assert (us["state"], us["outcome"], us["reason_code"], us["severity"]) == (
        "ENDED",
        "failed",
        "DISCOVERY_EXCEPTION",
        "failure",
    )
    assert us["facts"] == {"error_type": "RuntimeError"}


def test_a_week_blocked_by_the_draft_gate_starts_no_mail_and_no_posting(weekly):
    weekly.discovered = {"KR": KR_TWO}
    weekly.analysis = {"Alpha Electronics": "draft", "Beta Chemical": "draft"}

    weekly.run_recorded(markets=["KR"])

    assert weekly.steps() == [
        ("artifact", "summary_file", "ENDED", "ok"),
        ("delivery", "excel_upload", "ENDED", "no_result"),
        ("discovery", "KR", "ENDED", "ok"),
        ("valuation", "Alpha Electronics", "ENDED", "draft_blocked"),
        ("valuation", "Beta Chemical", "ENDED", "draft_blocked"),
    ]
    assert (
        weekly.called("email")
        == weekly.called("wordpress")
        == weekly.called("naver")
        == []
    )
    assert ("Draft Gate" in [phase for phase, _ in weekly.alerts]) is True


@pytest.mark.parametrize(
    "upload, outcome, facts",
    [
        (True, "ok", {"eligible": 2, "uploaded": 2}),
        ("half", "partial", {"eligible": 2, "uploaded": 1}),
        (False, "no_result", {"eligible": 2, "uploaded": 0}),
    ],
)
def test_what_the_excel_upload_step_reports(weekly, upload, outcome, facts):
    weekly.discovered = {"KR": KR_TWO}
    weekly.upload = upload

    weekly.run_recorded(markets=["KR"])

    step = [s for s in weekly.only_run()["steps"] if s["target"] == "excel_upload"][0]
    assert (step["outcome"], step["facts"]) == (outcome, facts)


def test_a_summary_that_cannot_be_written_is_a_failed_step_not_a_failed_run(
    weekly, monkeypatch
):
    weekly.discovered = {"KR": KR_TWO}
    real_open = open

    def no_summary(path, *args, **kwargs):
        if str(path).endswith("_weekly_summary.json"):
            raise OSError("disk full")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", no_summary)

    weekly.run_recorded(markets=["KR"], dry_run=True)

    assert ("artifact", "summary_file", "ENDED", "failed") in weekly.steps()
    assert weekly.only_run()["run"]["status"] == "COMPLETED"


def test_an_exception_from_the_run_is_recorded_and_raised_unchanged(weekly):
    weekly.discovered = {"KR": KR_TWO}
    weekly.upload = RuntimeError("storage exploded")

    with pytest.raises(RuntimeError, match="storage exploded"):
        weekly.run_recorded(markets=["KR"])

    run = weekly.only_run()
    assert (run["run"]["status"], run["run"]["reason_code"]) == (
        "FAILED",
        "RUN_EXCEPTION",
    )
    assert run["run"]["facts"] == {"error_type": "RuntimeError"}
    upload = [s for s in run["steps"] if s["target"] == "excel_upload"][0]
    assert (upload["state"], upload["reason_code"]) == (
        "UNKNOWN_DELIVERY",
        "RUN_ENDED_WITH_OPEN_STEP",
    )
    assert weekly.called("email") == []
    assert_every_start_has_an_end(weekly.db, runs=1, steps=4)
    weekly.open_writer(weekly.db).close()  # the seat was given back


def test_another_writer_means_the_week_does_not_start(weekly):
    weekly.discovered = {"KR": KR_TWO}
    holder = weekly.open_writer(weekly.db)
    try:
        with pytest.raises(rs.RunStateUnavailable) as caught:
            weekly.run_recorded(markets=["KR"])
    finally:
        holder.close()

    assert code_of(caught) == "WRITER_BUSY"
    assert weekly.calls == [] and weekly.alerts == [] and weekly.db_updates == []
    assert not weekly.results.exists()
    assert rows(weekly.db, "SELECT count(*) FROM runs") == [(0,)]


def test_a_database_that_cannot_be_trusted_means_the_week_does_not_start(weekly):
    _garbage(weekly.db)
    before = digest(weekly.db)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        weekly.run_recorded(markets=["KR"])

    assert code_of(caught) == "DB_CORRUPT"
    assert weekly.calls == [] and weekly.alerts == []
    assert digest(weekly.db) == before


def test_a_start_that_cannot_be_recorded_means_the_week_does_not_start(
    weekly, monkeypatch
):
    weekly.discovered = {"KR": KR_TWO}
    real = rs.open_writer

    def broken_from_the_start(path, **kwargs):
        writer = real(path, **kwargs)
        break_writes(writer)
        return writer

    monkeypatch.setattr(rs, "open_writer", broken_from_the_start)

    with pytest.raises(rs.RunStateUnavailable) as caught:
        weekly.run_recorded(markets=["KR"])

    assert code_of(caught) == "START_NOT_RECORDED"
    assert weekly.calls == []
    weekly.open_writer(weekly.db).close()


def test_when_recording_breaks_mid_run_no_delivery_starts(weekly):
    weekly.discovered = {"KR": KR_TWO, "US": US_ONE}
    weekly.on["analyze:Beta Chemical"] = weekly.break_recording

    with pytest.raises(rs.RunStateRecordingFailed) as caught:
        weekly.run_recorded()

    assert code_of(caught) == "RECORDING_FAILED" and caught.value.exit_code == 4
    # the valuations ran to the end and the summary is on disk, with the reason
    saved = weekly.summary_on_disk()
    assert sorted(v["company"] for v in saved["valuations"]) == [
        "Alpha Electronics",
        "Beta Chemical",
        "Gamma Software",
    ]
    assert [e for e in saved["errors"] if e.get("phase") == "run_state"] == [
        {
            "phase": "run_state",
            "reason_code": "RUN_STATE_WRITE_FAILED",
            "severity": "failure",
            "error": "run state recording failed; later deliveries were not started",
        }
    ]
    assert len(weekly.called("analyze:")) == 3
    # nothing was delivered
    for boundary in ("excel_upload", "email", "wordpress", "naver"):
        assert weekly.called(boundary) == []
    assert all("download_url" not in v for v in saved["valuations"])
    # Supabase still hears that the run had errors
    assert weekly.db_updates[-1][1]["status"] == "completed_with_errors"
    # the next writer closes what the broken record left open
    writer = weekly.open_writer(weekly.db)
    writer.close()
    assert len(writer.recovered) == 1
    assert weekly.only_run()["run"]["status"] == "INTERRUPTED"
    assert all(s["state"] != "STARTED" for s in weekly.only_run()["steps"])


def test_when_recording_breaks_at_one_delivery_the_later_ones_do_not_start(weekly):
    weekly.discovered = {"KR": KR_TWO}
    weekly.on["excel_upload"] = lambda: weekly.break_recording(
        lambda statement, args: (
            statement.startswith("INSERT INTO steps") and "email" in args
        )
    )

    with pytest.raises(rs.RunStateRecordingFailed):
        weekly.run_recorded(markets=["KR"])

    assert weekly.called("excel_upload") == ["excel_upload"]  # already under way
    assert (
        weekly.called("email")
        == weekly.called("wordpress")
        == weekly.called("naver")
        == []
    )
    assert ("delivery", "excel_upload", "ENDED", "ok") in weekly.steps()


def test_when_the_end_of_a_delivery_cannot_be_recorded_the_next_one_does_not_start(
    weekly,
):
    weekly.discovered = {"KR": KR_TWO}
    weekly.on["email"] = lambda: weekly.break_recording(
        lambda statement, args: statement.startswith("UPDATE steps")
    )

    with pytest.raises(rs.RunStateRecordingFailed):
        weekly.run_recorded(markets=["KR"])

    assert weekly.called("email") == ["email"]
    assert weekly.called("wordpress") == weekly.called("naver") == []
    writer = weekly.open_writer(weekly.db)
    writer.close()
    email = [s for s in weekly.only_run()["steps"] if s["target"] == "email"][0]
    assert (email["state"], email["reason_code"]) == (
        "UNKNOWN_DELIVERY",
        "NO_END_RECORDED",
    )


def test_when_only_the_end_of_the_run_cannot_be_recorded(weekly):
    weekly.discovered = {"KR": KR_TWO}
    weekly.on["naver"] = lambda: weekly.break_recording(
        lambda statement, args: statement.startswith("UPDATE runs")
    )

    with pytest.raises(rs.RunStateRecordingFailed):
        weekly.run_recorded(markets=["KR"])

    assert weekly.called("email") == ["email"] and weekly.called("naver") == ["naver"]
    assert rows(weekly.db, "SELECT status FROM runs") == [("RUNNING",)]
    weekly.open_writer(weekly.db).close()
    assert weekly.only_run()["run"]["status"] == "INTERRUPTED"


def test_the_failure_of_the_run_itself_wins_over_a_broken_record(weekly, monkeypatch):
    weekly.discovered = {"KR": KR_TWO}
    weekly.on["discover:KR"] = weekly.break_recording

    def explode(summary):
        raise KeyError("the run itself failed")

    monkeypatch.setattr(weekly.wr, "_draft_publish_state", explode)

    with pytest.raises(KeyError):
        weekly.run_recorded(markets=["KR"])

    assert weekly.writers[-1]._broken  # the record did break as well
    assert weekly.called("email") == []


def test_cleanup_that_fails_does_not_change_what_the_run_returned(weekly, monkeypatch):
    weekly.discovered = {"KR": KR_TWO}

    def no_unlock(fd):
        raise OSError("unlock failed")

    def no_replace(source, target):
        raise PermissionError(13, "held by a reader")

    monkeypatch.setattr(rs, "_unlock_file", no_unlock)
    monkeypatch.setattr(rs.os, "replace", no_replace)
    monkeypatch.setattr(rs.time, "sleep", lambda seconds: None)

    summary = weekly.run_recorded(markets=["KR"])

    assert summary["local_run_id"] == weekly.only_run()["run"]["run_id"]
    assert weekly.only_run()["run"]["status"] == "COMPLETED"
    assert weekly.called("email") == ["email"]


def test_cleanup_that_fails_does_not_replace_the_exception_of_the_run(
    weekly, monkeypatch
):
    weekly.discovered = {"KR": KR_TWO}
    weekly.upload = RuntimeError("storage exploded")

    def no_unlock(fd):
        raise OSError("unlock failed")

    monkeypatch.setattr(rs, "_unlock_file", no_unlock)

    with pytest.raises(RuntimeError, match="storage exploded"):
        weekly.run_recorded(markets=["KR"])


def test_end_facts_that_cannot_be_read_do_not_fail_a_finished_run(weekly, monkeypatch):
    weekly.discovered = {"KR": KR_TWO}

    def explode(summary):
        raise TypeError("unexpected summary")

    monkeypatch.setattr(weekly.wr, "_run_end_facts", explode)

    weekly.run_recorded(markets=["KR"], dry_run=True)

    run = weekly.only_run()["run"]
    assert (run["status"], run["facts"]) == ("COMPLETED", {})


def test_earlier_unfinished_runs_are_closed_before_the_week_starts(weekly):
    first = weekly.open_writer(weekly.db)
    rec = start(first)
    rec.start("delivery", "naver")
    abandon(first)
    weekly.discovered = {"KR": KR_TWO}

    weekly.run_recorded(markets=["KR"], dry_run=True)

    statuses = {r["run_id"]: r["status"] for r in rs.read_runs(weekly.db)}
    assert statuses[rec.run_id] == "INTERRUPTED" and len(statuses) == 2
    old = rs.read_run(weekly.db, rec.run_id)["steps"][0]
    assert (old["state"], old["reason_code"]) == ("UNKNOWN_DELIVERY", "NO_END_RECORDED")
    assert weekly.called("naver") == []  # recovery marks; it never sends again
    assert_every_start_has_an_end(weekly.db, runs=2, steps=3)


def test_no_credential_or_path_reaches_the_database_or_the_exported_file(
    weekly, monkeypatch
):
    error_class = type(TOKEN_CLASS + "Error", (Exception,), {})
    exception_class = type(TOKEN_CLASS + "Exception", (Exception,), {})
    warning_class = type(TOKEN_CLASS + "Warning", (Exception,), {})
    monkeypatch.setenv("DART_API_KEY", SECRET_ENV)
    monkeypatch.setenv("K0F_UNRELATED_SETTING", SECRET_ENV[::-1])
    weekly.discovered = {
        "KR": [
            {"name": "Normal Co", "ticker": "005930", "reason": "r"},
            {"name": TOKEN_NAME, "ticker": "000660", "reason": "r"},
            {"name": LONG_NAME, "ticker": "035420", "reason": "r"},
            {"name": WINDOWS_PATH, "ticker": "051910", "reason": "r"},
            {
                "name": "see crtfc_key=" + SECRET_QUERY,
                "ticker": "005380",
                "reason": "r",
            },
        ],
        "US": [
            {"name": POSIX_PATH, "ticker": "PATH", "reason": "r"},
            {
                "name": "https://example.test/a?token=" + SECRET_URL,
                "ticker": "URLS",
                "reason": "r",
            },
            {"name": "Raises Co", "ticker": "sk-" + SECRET_SK, "reason": "r"},
            {
                "name": "k0f-relative-folder/report.xlsx",
                "ticker": "RELA",
                "reason": "r",
            },
            {"name": "./k0f-dot-relative.xlsx", "ticker": "DOTR", "reason": "r"},
            {"name": "C:k0f-drive-relative.xlsx", "ticker": "DRIV", "reason": "r"},
        ],
        "XX": RuntimeError(
            "GET https://opendart.fss.or.kr/api/list.json?crtfc_key=" + SECRET_QUERY
        ),
    }

    def raises_with_odd_diagnostics(diagnostics):
        diagnostics["reason_code"] = "sk-" + SECRET_SK
        diagnostics["stage"] = TOKEN_NAME
        diagnostics["degraded"] = [
            {"step": TOKEN_TAIL, "message": "token=" + SECRET_BEARER},
            {"step": "peers", "error_type": TOKEN_CLASS, "message": POSIX_PATH},
        ]
        return error_class(
            "Authorization: Bearer " + SECRET_BEARER + " at " + WINDOWS_PATH
        )

    def empty_with_odd_diagnostics(diagnostics):
        diagnostics["reason_code"] = TOKEN_TAIL
        diagnostics["reason_detail"] = {"reported": "password=" + SECRET_PASSWORD}
        diagnostics["degraded"] = [{"step": "wacc", "message": "sk-" + SECRET_SK}]
        return "none-as-reported"

    weekly.analysis = {
        "Raises Co": raises_with_odd_diagnostics,
        "Normal Co": "degraded",
        TOKEN_NAME: empty_with_odd_diagnostics,
    }
    weekly.mail = RuntimeError("smtp password=" + SECRET_PASSWORD)
    weekly.wordpress = exception_class("https://wp.example/?token=" + SECRET_URL)
    weekly.naver = warning_class("selenium at " + POSIX_PATH)

    weekly.run_recorded(markets=["KR", "US", "XX"], max_per_market=8)

    # 1. the run really happened and really was recorded
    run = weekly.only_run()
    export = weekly.db.parent / run["run"]["run_id"] / "events.jsonl"
    assert weekly.db.is_file() and export.is_file()
    assert len(run["steps"]) == 3 + 11 + 1 + 4
    assert len(weekly.called("analyze:")) == 11
    files = sorted(p for p in weekly.db.parent.rglob("*") if p.is_file())
    stored = b"".join(p.read_bytes() for p in files)
    assert {p.name for p in files} >= {
        "state.db",
        "state.db.writer.lock",
        "events.jsonl",
    }
    assert (
        b"Normal Co" in stored and b"RuntimeError" in stored and b"<masked>" in stored
    )
    # 2. the injected values really went through the pipeline: the summary has them
    summary_text = json.dumps(weekly.summary_on_disk(), ensure_ascii=False)
    for carried in (
        TOKEN_NAME,
        TOKEN_CLASS + "Error",
        "k0f-relative-folder",
        "k0f-windows-account",
    ):
        assert carried in summary_text
    # 3. and none of them is in the database, its side files or the export
    needles = [
        TOKEN_NAME,
        TOKEN_TAIL,
        TOKEN_CLASS,
        SECRET_QUERY,
        SECRET_BEARER,
        SECRET_SK,
        SECRET_PASSWORD,
        SECRET_ENV,
        SECRET_ENV[::-1],
        SECRET_URL,
        "k0f-windows-account",
        "k0f-posix-account",
        "k0f-relative-folder",
        "k0f-dot-relative",
        "k0f-drive-relative",
        "crtfc_key",
        "opendart",
        "private",
        "xlsx",
        str(weekly.tmp),
        weekly.tmp.as_posix(),
    ]
    for needle in needles:
        for piece in {needle, needle[:16]}:
            for encoding in ("utf-8", "utf-16-le"):
                assert piece.encode(encoding) not in stored, piece[:6]
    # what is there instead
    targets = {s["target"] for s in run["steps"] if s["kind"] == "valuation"}
    assert targets == {"Normal Co", "Raises Co", "<masked>"}
    raised = [s for s in run["steps"] if s["target"] == "Raises Co"][0]
    assert raised["facts"]["error_type"] == "<invalid>"
    assert raised["facts"]["ticker"] == "<invalid>"
    by_target = {s["target"]: s for s in run["steps"] if s["kind"] == "delivery"}
    assert by_target["wordpress"]["facts"] == {"error_type": "<invalid>"}
    assert by_target["naver"]["facts"] == {"error_type": "<invalid>"}
    assert by_target["email"]["facts"] == {"error_type": "RuntimeError"}


def test_the_fixed_lists_match_the_contracts_they_copy(weekly):
    """run_state imports nothing from these modules, so the copies can drift."""
    from discovery import discovery_engine

    wr = weekly.wr
    assert rs._REASON_CODES == (
        set(discovery_engine.REASON_SEVERITY)
        | wr._ACCEPTED_NO_RESULT_REASONS
        | {wr.VALUATION_EXCEPTION, wr.ENRICHMENT_DEGRADED}
        | {rs.NO_END_RECORDED, rs.RUN_ENDED_WITH_OPEN_STEP, rs.RUN_EXCEPTION}
    )
    assert (
        set(discovery_engine.REASON_SEVERITY.values()) | {"failure", "degraded"}
        == rs._SEVERITIES
    )
    assert wr._DEGRADED_STEPS == rs._DEGRADED_STEPS
    assert wr._PRODUCER_STAGES | {"result"} == rs._STAGES
    assert {
        discovery_engine.PATH_SAVETICKER,
        discovery_engine.PATH_NEWS_LLM,
    } == rs._DISCOVERY_PATHS
    assert rs._OUTCOMES["valuation"] == {
        "success",
        "draft_blocked",
        "no_result",
        "failed",
    }
    assert all(len(code) < 32 for code in rs._REASON_CODES)


def test_small_helpers_of_the_wiring(weekly, tmp_path):
    wr = weekly.wr
    assert wr._discovery_outcome({"reason_code": None, "severity": None}) == "ok"
    assert (
        wr._discovery_outcome({"reason_code": "NO_CANDIDATES", "severity": "empty"})
        == "empty"
    )
    assert (
        wr._discovery_outcome({"reason_code": "NEWS_EMPTY", "severity": "failure"})
        == "failed"
    )
    assert wr._discovery_outcome({"reason_code": "X", "severity": None}) == "failed"
    assert [wr._upload_outcome(n, m) for n, m in ((2, 2), (2, 1), (2, 0), (0, 0))] == [
        "ok",
        "partial",
        "no_result",
        "no_result",
    ]
    summary = {"valuations": [], "errors": [], "scored_companies": []}
    assert wr._save_json_summary(dict(summary), tmp_path) is True
    assert (
        wr._save_json_summary(dict(summary), tmp_path / "missing" / "folder") is False
    )


@pytest.mark.parametrize(
    "error, code",
    [
        (rs.RunStateUnavailable("WRITER_BUSY"), 3),
        (rs.RunStateUnavailable("DB_CORRUPT"), 3),
        (rs.RunStateRecordingFailed("RECORDING_FAILED"), 4),
    ],
)
def test_main_ends_with_an_exit_code_when_run_state_stops_it(
    weekly, monkeypatch, error, code
):
    def stopped(**kwargs):
        raise error

    monkeypatch.setattr(weekly.wr, "run_weekly_recorded", stopped)
    monkeypatch.setattr(sys, "argv", ["weekly_run", "--markets", "KR", "--dry-run"])

    with pytest.raises(SystemExit) as caught:
        weekly.wr.main()

    assert caught.value.code == code
    assert not weekly.wr._LOCK_PATH.exists()  # the re-run guard was released


def test_main_goes_through_the_recorded_entry_point(weekly, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        weekly.wr, "run_weekly_recorded", lambda **kwargs: seen.update(kwargs)
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["weekly_run", "--markets", "KR,US", "--max-per-market", "2", "--dry-run"],
    )

    assert weekly.wr.main() is None

    assert seen == {"markets": ["KR", "US"], "max_per_market": 2, "dry_run": True}
    assert not weekly.wr._LOCK_PATH.exists()


def test_main_lets_any_other_exception_through_and_releases_the_guard(
    weekly, monkeypatch
):
    def explode(**kwargs):
        raise RuntimeError("not a run-state failure")

    monkeypatch.setattr(weekly.wr, "run_weekly_recorded", explode)
    monkeypatch.setattr(sys, "argv", ["weekly_run", "--markets", "KR"])

    with pytest.raises(RuntimeError):
        weekly.wr.main()

    assert not weekly.wr._LOCK_PATH.exists()


def test_main_records_a_real_run_end_to_end(weekly, monkeypatch):
    weekly.discovered = {"KR": KR_TWO}
    monkeypatch.setattr(sys, "argv", ["weekly_run", "--markets", "KR", "--dry-run"])

    weekly.wr.main()

    assert weekly.only_run()["run"]["status"] == "COMPLETED"
    assert weekly.only_run()["run"]["dry_run"] is True


def test_cli_weekly_goes_through_the_recorded_entry_point(weekly, monkeypatch):
    cli = importlib.import_module("cli")
    seen = {}

    def recorded(**kwargs):
        seen.update(kwargs)
        return {"recorded": True}

    def direct(*args, **kwargs):
        raise AssertionError("cli.py --weekly must not call run_weekly() directly")

    monkeypatch.setattr(weekly.wr, "run_weekly_recorded", recorded)
    monkeypatch.setattr(weekly.wr, "run_weekly", direct)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "cli.py",
            "--weekly",
            "--markets",
            "KR,US",
            "--max-per-market",
            "2",
            "--dry-run",
        ],
    )

    assert cli.main() == {"recorded": True}
    assert seen == {"markets": ["KR", "US"], "max_per_market": 2, "dry_run": True}


# ── 10. the weekly log ───────────────────────────────────────────────────────


def test_request_urls_stay_out_of_the_weekly_log(monkeypatch, tmp_path):
    try:
        import dotenv
    except ImportError:
        dotenv = None
    if dotenv is not None:
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setenv("CURL_CA_BUNDLE", os.environ.get("CURL_CA_BUNDLE") or "k0f-test")
    wr = importlib.import_module("scheduler.weekly_run")
    monkeypatch.setattr(wr, "_LOG_DIR", tmp_path)
    root = logging.getLogger()
    clients = [logging.getLogger("httpx"), logging.getLogger("httpcore")]
    saved_handlers = root.handlers[:]
    saved_levels = [root.level] + [client.level for client in clients]
    root.handlers[:] = []  # _setup_logging() leaves a configured root logger alone
    for client in clients:
        client.setLevel(logging.NOTSET)
    try:
        wr._setup_logging()
        ours = root.handlers[:]
        assert len(ours) == 2
        url = "https://opendart.fss.or.kr/api/list.json?crtfc_key=" + SECRET_QUERY
        clients[0].info('HTTP Request: GET %s "HTTP/1.1 200 OK"', url)
        clients[1].info("connect_tcp.started host='opendart.fss.or.kr' %s", url)
        logging.getLogger("scheduler.weekly_run").info("an ordinary line")
        clients[0].warning("a client warning without a url")
        for handler in ours:
            handler.flush()
            handler.close()
    finally:
        root.handlers[:] = saved_handlers
        root.setLevel(saved_levels[0])
        for client, level in zip(clients, saved_levels[1:]):
            client.setLevel(level)

    (log,) = tmp_path.glob("weekly_*.log")
    text = log.read_text(encoding="utf-8")
    assert "an ordinary line" in text and "a client warning without a url" in text
    assert (
        SECRET_QUERY not in text
        and "HTTP Request" not in text
        and "crtfc_key" not in text
    )
