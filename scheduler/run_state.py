"""Local source of truth for weekly-run state: one SQLite file, one writer.

``runs/state.db`` records when a weekly run, each market's discovery, each
company's valuation and each delivery step started and how it ended. The event
file ``runs/<run id>/events.jsonl`` is exported from the database and is never
read back; when the two differ the database is right.

Rules this module keeps (plan section 11.1, K-0F):

* One writer. ``open_writer()`` takes an OS file lock that the operating system
  drops when the process dies; a second writer is refused, it does not wait.
  The lock is found through the database's real path and a database file with
  a second name is refused. The seat belongs to the process that took it: a
  copy of the writer in a forked child records nothing, exports nothing and
  gives nothing back. A fork is not fenced: do not fork() while a writer is
  open (the caller's premise).
* Every start gets an end. A start whose end was never recorded (killed
  process, power loss, failed write) is closed as interrupted by the next
  writer, before that writer records anything of its own.
* Fail closed. A file that is damaged, belongs to something else or has an
  unknown schema version is neither overwritten nor deleted, and it is not
  even opened for writing: the writer is refused. A write that fails is never
  reported as recorded.
* No free text. Only codes from fixed lists, counts, flags and short
  shape-checked identifiers are stored: no messages, URLs, paths, prompts or
  environment values.

Standard library only; importing this module creates no file and no folder.
"""

from __future__ import annotations

import contextlib
import errno
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
APPLICATION_ID = 0x4B304601  # marks the file as a run-state database
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "runs" / "state.db"

# Reason codes this module adds. Everything else is carried over from the
# discovery (k0b-1) and valuation (k0c-1) contracts.
NO_END_RECORDED = "NO_END_RECORDED"  # closed by the next writer; cause unknown
RUN_ENDED_WITH_OPEN_STEP = "RUN_ENDED_WITH_OPEN_STEP"
RUN_EXCEPTION = "RUN_EXCEPTION"
# For summary["errors"] when recording broke during a run (used by weekly_run).
RUN_STATE_WRITE_FAILED = "RUN_STATE_WRITE_FAILED"

_MESSAGES = {
    "SQLITE_UNSUPPORTED": "this SQLite build is too old or single-threaded",
    "WRITER_BUSY": "another process holds the run-state writer lock",
    "LOCK_UNAVAILABLE": "the run-state writer lock file cannot be opened or locked",
    "DB_UNAVAILABLE": "the run-state database cannot be opened or written",
    "DB_CORRUPT": "the run-state database is damaged; it was left untouched",
    "DB_FOREIGN": "the file is not a run-state database; it was left untouched",
    "DB_ALIASED": "the run-state database file has more than one name; "
    "it was left untouched",
    "SCHEMA_UNSUPPORTED": "the run-state database has another schema version; "
    "it was left untouched",
    "START_NOT_RECORDED": "the start of the run could not be recorded",
    "RECORDING_FAILED": "a run-state write failed during the run; "
    "later deliveries were not started",
}


class RunStateError(Exception):
    """A run-state failure. The text is fixed per code: no path, no raw message."""

    exit_code = 1

    def __init__(self, reason_code: str) -> None:
        super().__init__(f"{reason_code}: {_MESSAGES[reason_code]}")
        self.reason_code = reason_code


class RunStateUnavailable(RunStateError):
    """Nothing was started (or read): no writer seat, or a file not to be trusted."""

    exit_code = 3


class RunStateRecordingFailed(RunStateError):
    """The run ran, but its record is incomplete."""

    exit_code = 4


# ── What may be stored ───────────────────────────────────────────────────────
# Keys are chosen by code, values by data. An unknown key is a programming
# error (ValueError, which becomes a failed write). A value outside what its
# field allows becomes "<invalid>" or None and never fails the write.
#
# Matching a grammar is not enough to be stored: a field whose values are known
# takes them from a fixed list, and a field that cannot be listed is too short
# to hold a credential.

_INVALID = "<invalid>"
_MASKED = "<masked>"
_TEXT_LIMIT = 120
_LABEL_INPUT_LIMIT = 800
_LIST_LIMIT = 20
_MARKET_LIMIT = 8
_COUNT_LIMIT = 10**9

# Fixed lists. The first two blocks mirror other modules without importing
# them; tests/test_run_state.py fails when they drift apart.
_REASON_CODES = frozenset(
    {
        # discovery contract k0b-1 (discovery/discovery_engine.py)
        "NEWS_EMPTY",
        "LLM_CALL_FAILED",
        "LLM_JSON_INVALID",
        "NO_CANDIDATES",
        "FILTERED_TO_ZERO",
        "DISCOVERY_EXCEPTION",
        "SELECTION_EMPTY",
        "REASON_NOT_REPORTED",
        # valuation contract k0c-1 (scheduler/weekly_run.py)
        "IDENTITY_NOT_FOUND",
        "IDENTITY_MISMATCH",
        "FINANCIALS_EMPTY",
        "RECONCILIATION_BLOCKED",
        "DRAFT_NO_YEARS",
        "DRAFT_NOT_WRITTEN",
        "VALUATION_EXCEPTION",
        "ENRICHMENT_DEGRADED",
        # this module
        NO_END_RECORDED,
        RUN_ENDED_WITH_OPEN_STEP,
        RUN_EXCEPTION,
    }
)
_SEVERITIES = frozenset({"failure", "empty", "degraded"})
_STAGES = frozenset(
    {
        "start",
        "identify",
        "financials",
        "shares",
        "draft_profile",
        "enrichment",
        "valuation",
        "export",
        "result",
    }
)
_DEGRADED_STEPS = frozenset(
    {
        "industry_metadata",
        "ttm_anchor",
        "beta_observation",
        "ai_module",
        "segments",
        "peers",
        "wacc",
        "news",
        "market_signals",
        "method_selection",
        "scenarios",
        "db_save_call",
    }
)
_DISCOVERY_PATHS = frozenset({"saveticker", "news_llm"})
_KINDS = ("discovery", "valuation", "artifact", "delivery")
_OUTCOMES = {
    "discovery": frozenset({"ok", "empty", "failed"}),
    "valuation": frozenset({"success", "draft_blocked", "no_result", "failed"}),
    "artifact": frozenset({"ok", "failed"}),
    "delivery": frozenset({"ok", "partial", "no_result", "raised"}),
}
_FIXED_TARGETS = {
    "artifact": frozenset({"summary_file"}),
    "delivery": frozenset({"excel_upload", "email", "wordpress", "naver"}),
}
_END_STATUSES = frozenset({"COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"})

# Shapes for what cannot be listed. None is long enough for a 32-character token.
_MARKET = re.compile(r"[A-Za-z0-9_\-]{1,16}")
_TICKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,11}")
_CLASS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,30}")
_FOLDER = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}\([A-Za-z]{3} [0-9]{1,2}(?:st|nd|rd|th) week\)"
)
_RUN_ID = re.compile(r"wr-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")

# C0 and C1 controls and the two Unicode line separators (by code point, so
# that this source file holds no invisible characters).
_CONTROL = re.compile("[\\x00-\\x1f\\x7f-\\x9f" + chr(0x2028) + chr(0x2029) + "]")
# A display name that shows any of these is replaced whole, not partly masked.
_UNWANTED_IN_NAME = (
    # credentials
    re.compile(r"://"),  # a URL (the two-slash rule below catches it too)
    re.compile(r"[A-Za-z0-9_\-]{32,}"),
    re.compile(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/=\-]{16,}"),
    re.compile(r"(?i)\bsk-[A-Za-z0-9_\-]{16,}"),
    re.compile(
        r"(?i)(?:key|secret|token|password|passwd|authorization|credential|cookie)"
        r"[\w.\-]{0,40}\s*[:=]\s*\S"
    ),
    # file paths (they carry account names)
    re.compile(r"\\"),  # any backslash
    re.compile(r"/[^/]*/"),  # two slashes
    re.compile(r"^[/~]"),
    re.compile(r"(?:^|\s)\.{1,2}/"),  # ./x and ../x
    re.compile(r"(?i)\b[a-z]:/"),
    re.compile(r"(?i)(?:^|\s)[a-z]:\S"),  # C:/x and the drive-relative C:x
    re.compile(r"/[^/\s]*\.[A-Za-z0-9]{1,5}(?:\s|$)"),  # folder/name.ext
)


def _listed(value: object, allowed: frozenset, absent: str | None = None):
    """A value from a fixed list; None stays ``absent``; anything else is invalid."""
    if value is None:
        return absent
    if type(value) is str and value in allowed:
        return value
    return _INVALID


def _shaped(value: object, pattern: re.Pattern, absent: str | None = None):
    """A short identifier of a known shape; None stays ``absent``."""
    if value is None:
        return absent
    if type(value) is not str or len(value) > _TEXT_LIMIT:
        return _INVALID  # len() is O(1): an oversized value is never scanned
    return value if pattern.fullmatch(value) else _INVALID


def _market(value: object) -> str:
    return _shaped(value, _MARKET, absent=_INVALID)


def _market_or_none(value: object) -> str | None:
    return _shaped(value, _MARKET)


def _ticker(value: object) -> str | None:
    if type(value) is int and 0 <= value <= _COUNT_LIMIT:
        value = str(value)
    return _shaped(value, _TICKER)


def _folder(value: object) -> str | None:
    return _shaped(value, _FOLDER)


def _reason(value: object) -> str | None:
    return _listed(value, _REASON_CODES)


def _severity(value: object) -> str | None:
    return _listed(value, _SEVERITIES)


def _stage(value: object) -> str | None:
    return _listed(value, _STAGES)


def _discovery_path(value: object) -> str | None:
    return _listed(value, _DISCOVERY_PATHS)


def _class_name(value: object) -> str | None:
    """An exception class name, 31 characters at most.

    No exception for longer names: a 40-character token followed by "Error"
    reads like a class name too. A real name of 32 or more characters is
    stored as invalid; the summary file and the log still have it.
    """
    return _shaped(value, _CLASS_NAME)


def _count(value: object) -> int | None:
    if type(value) is not int:  # bool is not a count
        return None
    return value if 0 <= value <= _COUNT_LIMIT else None


def _flag(value: object) -> bool | None:
    return value if type(value) is bool else None


def _degraded(value: object) -> list:
    if type(value) is not list:
        return []
    return [
        _listed(item, _DEGRADED_STEPS, absent=_INVALID)
        for item in islice(value, _LIST_LIMIT)
    ]


def _markets(value: object) -> list:
    if type(value) is not list:
        return []
    return [_market(item) for item in islice(value, _MARKET_LIMIT)]


def _outcome(kind: str, value: object) -> str:
    return _listed(value, _OUTCOMES[kind], absent=_INVALID)


def _status_counts(value: object) -> dict:
    if type(value) is not dict:
        return {}
    counts: dict = {}
    for key, number in islice(value.items(), len(_OUTCOMES["valuation"]) + 1):
        counts[_outcome("valuation", key)] = _count(number)
    return counts


_MARKET_ROW = {
    "market": _market,
    "reason_code": _reason,
    "severity": _severity,
    "news_count": _count,
    "discovered": _count,
    "selected": _count,
    "selected_after_budget_trim": _count,
}


def _market_rows(value: object) -> list:
    if type(value) is not list:
        return []
    return [
        {key: check(row.get(key)) for key, check in _MARKET_ROW.items()}
        for row in islice(value, _MARKET_LIMIT)
        if type(row) is dict
    ]


def _label(value: object) -> str:
    """A company name for display: one line, bounded, never a credential or a path.

    Names are selection identifiers (the weekly summary already holds them
    verbatim) and partial masking would mangle real ones ("SK-Hynix"), so a
    name is kept as it is unless it looks like a credential or a file path,
    and then it is replaced whole. The whole value is examined before it is
    cut, so a secret that straddles the cut cannot leave its head behind.
    """
    if type(value) is not str or len(value) > _LABEL_INPUT_LIMIT:
        return _INVALID
    text = " ".join(_CONTROL.sub(" ", value).split())
    if not text:
        return _INVALID
    for shape in _UNWANTED_IN_NAME:
        if shape.search(value) or shape.search(text):
            return _MASKED
    return text[:_TEXT_LIMIT]


_RUN_END_FACTS = {
    "errors": _count,
    "targets_selected": _count,
    "targets_after_budget_trim": _count,
    "zero_selection": _flag,
    "valuations_total": _count,
    "valuations_by_status": _status_counts,
    "summary_folder": _folder,
    "error_type": _class_name,
    "markets": _market_rows,
}
_STEP_FACTS = {
    ("discovery", "start"): {},
    ("discovery", "end"): {
        "news_count": _count,
        "discovered": _count,
        "path": _discovery_path,
        "error_type": _class_name,
    },
    ("valuation", "start"): {"ticker": _ticker, "market": _market_or_none},
    ("valuation", "end"): {
        "degraded": _degraded,
        "error_type": _class_name,
        "stage": _stage,
    },
    ("artifact", "start"): {},
    ("artifact", "end"): {},
    ("delivery", "start"): {},
    ("delivery", "end"): {
        "eligible": _count,
        "uploaded": _count,
        "error_type": _class_name,
    },
}


def _facts(allowed: dict, given: dict) -> dict:
    unknown = sorted(set(given) - set(allowed))
    if unknown:
        raise ValueError(f"fact keys outside the allow-list: {unknown}")
    return {key: allowed[key](given[key]) for key in sorted(given)}


def _target(kind: str, value: object) -> str:
    if kind == "discovery":
        return _market(value)
    if kind == "valuation":
        return _label(value)
    if type(value) is not str or value not in _FIXED_TARGETS[kind]:
        raise ValueError(f"not a {kind} target")  # these names are chosen by code
    return value


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# ── Time ─────────────────────────────────────────────────────────────────────

_KST = timezone(timedelta(hours=9))


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> tuple[str, str]:
    """(UTC, KST) ISO strings of one instant, to the millisecond, with offsets."""
    if moment.tzinfo is None:
        raise ValueError("the clock must return an aware datetime")
    utc = moment.astimezone(timezone.utc)
    return (
        utc.isoformat(timespec="milliseconds"),
        utc.astimezone(_KST).isoformat(timespec="milliseconds"),
    )


def _elapsed_ms(started: float, ended: float) -> int:
    return max(int(round((ended - started) * 1000)), 0)


# ── The writer seat: an OS lock that dies with its process ───────────────────

_BUSY_ERRNOS = frozenset({errno.EACCES, errno.EAGAIN, errno.EWOULDBLOCK, errno.EDEADLK})


def _lock_file(fd: int) -> None:
    """Take the exclusive lock without waiting; OSError when someone holds it.

    flock(), not lockf(): a lockf() lock does not stop a second open in the
    same process and is dropped when any descriptor of the file is closed.
    """
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(fd: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _quietly(action) -> None:
    """Cleanup that must not replace a result: run it, log a failure, move on."""
    try:
        action()
    except Exception as exc:
        logger.error("Run state cleanup failed: %s", type(exc).__name__)


# ── The file: schema, creation, examination ──────────────────────────────────

_MIN_SQLITE = (3, 22, 0)  # read-only connections to a WAL database
_BUSY_TIMEOUT_S = 5.0

_SCHEMA = (
    """
    CREATE TABLE runs (
      run_id          TEXT PRIMARY KEY,
      status          TEXT NOT NULL CHECK (status IN
                        ('RUNNING','COMPLETED','COMPLETED_WITH_ERRORS',
                         'FAILED','INTERRUPTED')),
      started_at      TEXT NOT NULL,
      started_at_kst  TEXT NOT NULL,
      ended_at        TEXT,
      ended_at_kst    TEXT,
      duration_ms     INTEGER,
      reason_code     TEXT,
      pid             INTEGER NOT NULL,
      dry_run         INTEGER NOT NULL CHECK (dry_run IN (0, 1)),
      max_per_market  INTEGER,
      markets         TEXT NOT NULL,
      facts           TEXT NOT NULL,
      exported_seq    INTEGER
    )
    """,
    """
    CREATE TABLE steps (
      step_id         INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id          TEXT NOT NULL REFERENCES runs(run_id),
      kind            TEXT NOT NULL CHECK (kind IN
                        ('discovery','valuation','artifact','delivery')),
      target          TEXT NOT NULL,
      state           TEXT NOT NULL CHECK (state IN
                        ('STARTED','ENDED','INTERRUPTED','UNKNOWN_DELIVERY')),
      outcome         TEXT,
      reason_code     TEXT,
      severity        TEXT,
      started_at      TEXT NOT NULL,
      started_at_kst  TEXT NOT NULL,
      ended_at        TEXT,
      ended_at_kst    TEXT,
      duration_ms     INTEGER,
      facts           TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE events (
      seq             INTEGER PRIMARY KEY AUTOINCREMENT,
      run_id          TEXT NOT NULL REFERENCES runs(run_id),
      step_id         INTEGER,
      event           TEXT NOT NULL CHECK (event IN
                        ('run_started','run_ended','run_interrupted',
                         'step_started','step_ended','step_interrupted')),
      ts              TEXT NOT NULL,
      ts_kst          TEXT NOT NULL,
      payload         TEXT NOT NULL
    )
    """,
    "CREATE INDEX events_by_run ON events (run_id, seq)",
    "CREATE INDEX steps_by_run ON steps (run_id, step_id)",
    # One start and one end per run and per step, enforced by the file itself:
    # a second one fails the whole transaction.
    "CREATE UNIQUE INDEX one_start_per_run ON events (run_id) "
    "WHERE event = 'run_started'",
    "CREATE UNIQUE INDEX one_end_per_run ON events (run_id) "
    "WHERE event IN ('run_ended','run_interrupted')",
    "CREATE UNIQUE INDEX one_start_per_step ON events (step_id) "
    "WHERE event = 'step_started'",
    "CREATE UNIQUE INDEX one_end_per_step ON events (step_id) "
    "WHERE event IN ('step_ended','step_interrupted')",
)


def _check_environment() -> None:
    """Refuse a SQLite that cannot keep this module's promises."""
    if sqlite3.sqlite_version_info < _MIN_SQLITE or sqlite3.threadsafety == 0:
        raise RunStateUnavailable("SQLITE_UNSUPPORTED")


def _uri(path: Path, mode: str) -> str:
    """A file: URI for sqlite3.connect(uri=True) that survives '#', '?' and '%'.

    Pasting the path into the URI as text lets a '#' in a folder name cut the
    rest off: another file is opened and the mode is lost.
    """
    return path.resolve().as_uri() + "?mode=" + mode


def _rollback(con: sqlite3.Connection) -> None:
    try:
        if con.in_transaction:
            con.execute("ROLLBACK")
    except sqlite3.Error:
        pass


def _header(con: sqlite3.Connection) -> tuple[int, int]:
    """(application_id, user_version)."""
    return (
        con.execute("PRAGMA application_id").fetchone()[0],
        con.execute("PRAGMA user_version").fetchone()[0],
    )


def _refusal(header: tuple[int, int]) -> str | None:
    """Why a file with this header is not ours to use, or None."""
    application_id, version = header
    if application_id != APPLICATION_ID:
        return "DB_FOREIGN"  # includes an empty file: emptiness proves nothing
    if version != SCHEMA_VERSION:
        return "SCHEMA_UNSUPPORTED"
    return None


_RETRY_ATTEMPTS = 5
_RETRY_WAIT_S = 0.2


def _retried(action) -> None:
    """Run ``action``, again after a pause while it fails with PermissionError.

    On Windows a file cannot be replaced or removed while another handle (a
    reader, a scanner) has it open. The last failure is raised.
    """
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            action()
            return
        except PermissionError:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            time.sleep(_RETRY_WAIT_S)


_SCRATCH_SIDE_FILES = ("-journal", "-wal", "-shm")


def _build_new(path: Path) -> None:
    """Create a complete run-state database at ``path``. Never over a file.

    The database is finished under a scratch name and then given its real
    name with os.link(), which fails if the name is taken. A process that dies
    half-way leaves scratch names only, so a file found at ``path`` without
    our mark was never made here.

    The switch to WAL is made under the scratch name too. It is a transaction
    with a rollback journal: made on the real name, a kill inside it would
    leave a hot journal beside the database, and every later writer would be
    refused by the read-only examination.
    """
    scratch = path.with_name(path.name + ".new")
    con = sqlite3.connect(str(scratch), isolation_level=None)
    try:
        con.execute("BEGIN IMMEDIATE")
        for statement in _SCHEMA:
            con.execute(statement)
        con.execute(f"PRAGMA application_id={APPLICATION_ID}")
        con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
        con.execute("COMMIT")
        if con.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
            raise sqlite3.OperationalError("journal_mode is not wal")
    finally:
        con.close()
    # Closing the last connection folds the WAL into the file and removes it.
    for suffix in _SCRATCH_SIDE_FILES:
        if os.path.lexists(str(scratch) + suffix):
            raise sqlite3.OperationalError("the new database is not self-contained")
    os.link(scratch, path)
    # The database is in place under two names now; the scratch name has to go
    # (a file with a second name is refused). If it cannot be removed even
    # after waiting, this open fails and the next writer removes it first.
    _retried(scratch.unlink)


def _remove_scratch(path: Path) -> None:
    """Drop what an interrupted _build_new() left. Only our own scratch names."""
    for suffix in ("",) + _SCRATCH_SIDE_FILES:
        path.with_name(path.name + ".new" + suffix).unlink(missing_ok=True)


def _examine(path: Path) -> tuple[int, int]:
    """Decide whose file this is, and whether it is sound, without writing.

    Through a read-only connection: a connection that may write rolls a hot
    journal back as soon as it reads, which changes a file not yet known to
    be ours.
    """
    try:
        con = sqlite3.connect(_uri(path, "ro"), uri=True, timeout=_BUSY_TIMEOUT_S)
    except sqlite3.Error as exc:
        raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    try:
        header = _header(con)
        refusal = _refusal(header)
        if refusal:
            raise RunStateUnavailable(refusal)
        if con.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise RunStateUnavailable("DB_CORRUPT")
    except sqlite3.OperationalError as exc:  # locked, unreadable, hot journal
        raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    except sqlite3.DatabaseError as exc:  # not a database, malformed image
        raise RunStateUnavailable("DB_CORRUPT") from exc
    finally:
        _quietly(con.close)
    return header


def _open_for_writing(path: Path, examined: tuple[int, int]) -> sqlite3.Connection:
    """The one read-write connection, for a file _examine() has accepted."""
    try:
        con = sqlite3.connect(
            _uri(path, "rw"),  # rw, not rwc: a file that vanished is not recreated
            uri=True,
            isolation_level=None,  # explicit BEGIN/COMMIT; same on Python 3.11-3.14
            check_same_thread=False,  # every use is under RunStateWriter._mutex
            timeout=_BUSY_TIMEOUT_S,
        )
    except sqlite3.Error as exc:
        raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    try:
        try:
            if _header(con) != examined:
                raise RunStateUnavailable("DB_UNAVAILABLE")
            mode = con.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                raise RunStateUnavailable("DB_UNAVAILABLE")
            con.execute("PRAGMA synchronous=FULL")
            con.execute("PRAGMA foreign_keys=ON")
        except sqlite3.OperationalError as exc:
            raise RunStateUnavailable("DB_UNAVAILABLE") from exc
        except sqlite3.DatabaseError as exc:
            raise RunStateUnavailable("DB_CORRUPT") from exc
    except BaseException:
        _rollback(con)
        _quietly(con.close)
        raise
    return con


# ── Export ───────────────────────────────────────────────────────────────────


def _event_objects(con: sqlite3.Connection, run_id: str) -> list[dict]:
    """The events of one run, oldest first: what each exported line holds."""
    objects = []
    for seq, step_id, event, ts, ts_kst, payload in con.execute(
        "SELECT seq, step_id, event, ts, ts_kst, payload FROM events "
        "WHERE run_id = ? ORDER BY seq",
        (run_id,),
    ).fetchall():
        line = json.loads(payload)
        line.update(
            schema=SCHEMA_VERSION,
            seq=seq,
            run_id=run_id,
            step_id=step_id,
            event=event,
            ts=ts,
            ts_kst=ts_kst,
        )
        objects.append(line)
    return objects


# ── The writer ───────────────────────────────────────────────────────────────


class _Step(NamedTuple):
    """What start() hands back and end() takes: a row id and a clock reading.

    Immutable, and it carries nothing that is stored: end() reads the kind,
    the target and the start facts back from the row, where they were
    validated, so a handle cannot bring an unchecked value into the file.
    """

    step_id: int
    started: float


_NOT_RECORDED = object()


class RunStateWriter:
    """The one writer of a run-state database. Get it from open_writer()."""

    def __init__(self, path, lock_fd, con, now, monotonic) -> None:
        self._path = path
        self._lock_fd = lock_fd
        self._con = con
        self._now = now or _utc_now
        self._monotonic = monotonic or time.monotonic
        # One connection, shared by the pool threads of run_weekly(): every use
        # of it happens under this lock, one transaction at a time.
        self._mutex = threading.Lock()
        self._open_run: str | None = None
        self._broken = False
        self._closed = False
        self._pid = os.getpid()  # the process that took the seat
        self.recovered: tuple[str, ...] = ()

    def _foreign(self) -> bool:
        """True in a process that did not take the seat: a copy after a fork().

        Such a copy records nothing, exports nothing and gives nothing back.
        It is asked before the lock is taken: in a forked child the lock may
        be held by a thread that does not exist there.
        """
        return os.getpid() != self._pid

    # -- transactions --

    def _event(self, con, run_id, step_id, event, stamp, payload) -> None:
        con.execute(
            "INSERT INTO events (run_id, step_id, event, ts, ts_kst, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, step_id, event, stamp[0], stamp[1], _json(payload)),
        )

    def _transaction(self, work):
        """work(con) inside one BEGIN IMMEDIATE ... COMMIT. Caller holds _mutex."""
        self._con.execute("BEGIN IMMEDIATE")
        try:
            result = work(self._con)
            self._con.execute("COMMIT")
        except BaseException:
            _rollback(self._con)
            raise
        return result

    def _record(self, work):
        """One recorded change of the open run, or _NOT_RECORDED. Never raises.

        Everything happens under the one lock, in this order: is the record
        already broken, are the values acceptable, is the transition allowed,
        the change and its event, the commit. The first failure latches under
        the same lock, so a thread that was waiting for the lock finds the
        record broken and writes nothing: a record that went on after a gap
        would show ends without starts. The run stays RUNNING in the file and
        the next writer closes it.

        A copy of the writer in another process is turned away before the
        lock; what it latches is its own memory, the file is not touched.
        """
        if self._foreign():
            if not self._broken:
                self._broken = True
                logger.error(
                    "Run state: this process did not take the writer seat. "
                    "Nothing is recorded here and later deliveries will not start."
                )
            return _NOT_RECORDED
        with self._mutex:
            if self._broken:
                return _NOT_RECORDED
            try:
                if self._closed:
                    raise ValueError("the writer is closed")
                return self._transaction(work)
            except Exception as exc:
                self._broken = True
                logger.error(
                    "Run state recording failed (%s). Nothing more is recorded "
                    "for this run and later deliveries will not start.",
                    type(exc).__name__,
                )
                return _NOT_RECORDED

    # -- recovery --

    def _close_open_steps(self, con, stamp, reason_code, run_id=None) -> None:
        """Close every STARTED step (of one run, or of all): its end is unknown."""
        query = (
            "SELECT step_id, run_id, kind, target FROM steps WHERE state = 'STARTED'"
        )
        args: tuple = ()
        if run_id is not None:
            query += " AND run_id = ?"
            args = (run_id,)
        for step_id, owner, kind, target in con.execute(
            query + " ORDER BY step_id", args
        ).fetchall():
            # Something may have been sent: never INTERRUPTED, never sent again.
            state = "UNKNOWN_DELIVERY" if kind == "delivery" else "INTERRUPTED"
            con.execute(
                "UPDATE steps SET state = ?, reason_code = ?, ended_at = ?, "
                "ended_at_kst = ? WHERE step_id = ? AND state = 'STARTED'",
                (state, reason_code, stamp[0], stamp[1], step_id),
            )
            self._event(
                con,
                owner,
                step_id,
                "step_interrupted",
                stamp,
                {
                    "kind": kind,
                    "target": target,
                    "state": state,
                    "reason_code": reason_code,
                },
            )

    def _recover(self) -> None:
        """Close every start that has no end. Runs before anything else is written."""

        def work(con):
            stamp = _stamp(self._now())
            self._close_open_steps(con, stamp, NO_END_RECORDED)
            run_ids = [
                row[0]
                for row in con.execute(
                    "SELECT run_id FROM runs WHERE status = 'RUNNING' "
                    "ORDER BY started_at, run_id"
                ).fetchall()
            ]
            for run_id in run_ids:
                con.execute(
                    "UPDATE runs SET status = 'INTERRUPTED', reason_code = ?, "
                    "ended_at = ?, ended_at_kst = ? "
                    "WHERE run_id = ? AND status = 'RUNNING'",
                    (NO_END_RECORDED, stamp[0], stamp[1], run_id),
                )
                self._event(
                    con,
                    run_id,
                    None,
                    "run_interrupted",
                    stamp,
                    {"status": "INTERRUPTED", "reason_code": NO_END_RECORDED},
                )
            return tuple(run_ids)

        with self._mutex:
            self.recovered = self._transaction(work)

    # -- the run --

    def start_run(self, *, markets, max_per_market, dry_run) -> RunRecorder:
        """Record the start of a run. RunStateUnavailable if it cannot be recorded."""
        try:
            if self._foreign():
                raise ValueError("the writer belongs to another process")
            with self._mutex:
                if self._closed or self._broken or self._open_run is not None:
                    raise ValueError("the writer cannot start a run")
                # Everything that can fail comes before the commit: a start that
                # is reported as not recorded must not be in the file.
                started = self._monotonic()
                moment = self._now()
                stamp = _stamp(moment)
                run_id = (
                    "wr-"
                    + moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                    + "-"
                    + secrets.token_hex(4)
                )
                facts = {
                    "markets": _markets(markets),
                    "max_per_market": _count(max_per_market),
                    "dry_run": bool(_flag(dry_run)),
                    "pid": os.getpid(),
                }

                def work(con):
                    con.execute(
                        "INSERT INTO runs (run_id, status, started_at, "
                        "started_at_kst, pid, dry_run, max_per_market, markets, "
                        "facts) VALUES (?, 'RUNNING', ?, ?, ?, ?, ?, ?, '{}')",
                        (
                            run_id,
                            stamp[0],
                            stamp[1],
                            facts["pid"],
                            int(facts["dry_run"]),
                            facts["max_per_market"],
                            _json(facts["markets"]),
                        ),
                    )
                    self._event(
                        con,
                        run_id,
                        None,
                        "run_started",
                        stamp,
                        {"status": "RUNNING", "facts": facts},
                    )

                self._transaction(work)
                self._open_run = run_id
        except Exception as exc:
            raise RunStateUnavailable("START_NOT_RECORDED") from exc
        return RunRecorder(self, run_id, started)

    def _start_step(self, run_id, kind, target, given):
        def work(con):
            # The run must be open in the file (not only in this object's memory):
            # after end_run(), or if something else closed the run meanwhile,
            # no step is added to a closed run.
            in_file = con.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if in_file != ("RUNNING",):
                raise ValueError("the run is not open in the file")
            if kind not in _KINDS:
                raise ValueError("unknown step kind")
            shown = _target(kind, target)
            facts = _facts(_STEP_FACTS[(kind, "start")], given)
            stamp = _stamp(self._now())
            step_id = con.execute(
                "INSERT INTO steps (run_id, kind, target, state, started_at, "
                "started_at_kst, facts) VALUES (?, ?, ?, 'STARTED', ?, ?, ?)",
                (run_id, kind, shown, stamp[0], stamp[1], _json(facts)),
            ).lastrowid
            self._event(
                con,
                run_id,
                step_id,
                "step_started",
                stamp,
                {"kind": kind, "target": shown, "state": "STARTED", "facts": facts},
            )
            return _Step(step_id, self._monotonic())

        return self._record(work)

    def _end_step(self, run_id, step, outcome, reason_code, severity, given):
        def work(con):
            if type(step) is not _Step:
                raise ValueError("not a step of a recorded run")
            # Only a STARTED step of this run can end, and only once. What was
            # validated at the start is read back from the row.
            row = con.execute(
                "SELECT kind, target, facts FROM steps "
                "WHERE step_id = ? AND run_id = ? AND state = 'STARTED'",
                (step.step_id, run_id),
            ).fetchone()
            if row is None:
                raise ValueError("the step is not an open step of this run")
            kind, target, stored = row
            facts = {**json.loads(stored), **_facts(_STEP_FACTS[(kind, "end")], given)}
            shown = _outcome(kind, outcome)
            reason = _reason(reason_code)
            level = _severity(severity)
            stamp = _stamp(self._now())
            duration = None
            if type(step.started) in (int, float):
                duration = _elapsed_ms(step.started, self._monotonic())
            changed = con.execute(
                "UPDATE steps SET state = 'ENDED', outcome = ?, reason_code = ?, "
                "severity = ?, ended_at = ?, ended_at_kst = ?, duration_ms = ?, "
                "facts = ? WHERE step_id = ? AND run_id = ? AND state = 'STARTED'",
                (
                    shown,
                    reason,
                    level,
                    stamp[0],
                    stamp[1],
                    duration,
                    _json(facts),
                    step.step_id,
                    run_id,
                ),
            ).rowcount
            if changed != 1:
                raise ValueError("the step row did not change")
            self._event(
                con,
                run_id,
                step.step_id,
                "step_ended",
                stamp,
                {
                    "kind": kind,
                    "target": target,
                    "state": "ENDED",
                    "outcome": shown,
                    "reason_code": reason,
                    "severity": level,
                    "duration_ms": duration,
                    "facts": facts,
                },
            )

        return self._record(work)

    def _end_run(self, run_id, started, status, reason_code, given):
        def work(con):
            if status not in _END_STATUSES:
                raise ValueError("not an end status")
            facts = _facts(_RUN_END_FACTS, given)
            reason = _reason(reason_code)
            stamp = _stamp(self._now())
            duration = _elapsed_ms(started, self._monotonic())
            # A step still open here has no end of its own any more.
            self._close_open_steps(con, stamp, RUN_ENDED_WITH_OPEN_STEP, run_id)
            changed = con.execute(
                "UPDATE runs SET status = ?, reason_code = ?, ended_at = ?, "
                "ended_at_kst = ?, duration_ms = ?, facts = ? "
                "WHERE run_id = ? AND status = 'RUNNING'",
                (status, reason, stamp[0], stamp[1], duration, _json(facts), run_id),
            ).rowcount
            if changed != 1:
                raise ValueError("the run is not open")
            self._event(
                con,
                run_id,
                None,
                "run_ended",
                stamp,
                {
                    "status": status,
                    "reason_code": reason,
                    "duration_ms": duration,
                    "facts": facts,
                },
            )
            # Under the same lock as the change: no step can start after this.
            self._open_run = None

        return self._record(work)

    # -- export --

    def _export_run(self, run_id: str) -> int | None:
        """Rewrite runs/<run id>/events.jsonl from the database; the last seq."""
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("run id is not a safe folder name")
        events = _event_objects(self._con, run_id)
        if not events:
            return None
        data = "".join(_json(event) + "\n" for event in events).encode("utf-8")
        folder = self._path.parent / run_id
        folder.mkdir(exist_ok=True)
        target = folder / "events.jsonl"
        scratch = folder / "events.jsonl.tmp"
        try:
            with open(scratch, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            _retried(lambda: os.replace(scratch, target))
        except BaseException:
            _quietly(lambda: scratch.unlink(missing_ok=True))
            raise
        return events[-1]["seq"]

    def _export_pending(self) -> None:
        """Export every finished run whose file is behind the database.

        Caller holds _mutex. A failure here is not a recording failure: the
        database is the source of truth and the next writer exports again.
        Never raises.
        """
        try:
            pending = self._con.execute(
                "SELECT r.run_id, r.exported_seq, "
                "(SELECT max(e.seq) FROM events e WHERE e.run_id = r.run_id) "
                "FROM runs r WHERE r.status != 'RUNNING' "
                "ORDER BY r.started_at, r.run_id"
            ).fetchall()
        except Exception as exc:
            logger.error("Run state export failed: %s", type(exc).__name__)
            return
        for run_id, exported, last in pending:
            if last is None or (exported is not None and exported >= last):
                continue
            try:
                seq = self._export_run(run_id)
                self._transaction(
                    lambda con, seq=seq, run_id=run_id: con.execute(
                        "UPDATE runs SET exported_seq = ? WHERE run_id = ?",
                        (seq, run_id),
                    )
                )
            except Exception as exc:
                logger.error("Run state export failed: %s", type(exc).__name__)

    # -- closing --

    def close(self) -> None:
        """Stop recording, export what finished, close the file, give up the seat.

        Cleanup only: it never raises and never changes what the run returned
        or raised; each step is tried even if the one before it failed. Safe
        to call twice.
        """
        if self._foreign():
            # A copy holds no seat: no export, no unlock, and the connection
            # it inherited is not closed (SQLite forbids that in a child).
            return
        with self._mutex:
            if self._closed:
                return
            self._closed = True  # nothing is recorded from here on
            if not self._broken:
                self._export_pending()
            _quietly(self._con.close)
            _quietly(lambda: _unlock_file(self._lock_fd))
            _quietly(lambda: os.close(self._lock_fd))


class RunRecorder:
    """What run_weekly() records through. No method raises.

    A failed write is not reported as recorded: ``broken`` turns True, start()
    returns None from then on, and the entry point ends with
    RunStateRecordingFailed once the run is over.
    """

    def __init__(self, writer: RunStateWriter, run_id: str, started: float) -> None:
        self._writer = writer
        self._started = started
        self.run_id = run_id

    @property
    def broken(self) -> bool:
        return self._writer._broken

    def start(self, kind: str, target: object, **facts) -> _Step | None:
        """Record that a step started; None when that could not be recorded."""
        step = self._writer._start_step(self.run_id, kind, target, facts)
        return None if step is _NOT_RECORDED else step

    def end(
        self,
        step: _Step | None,
        outcome: object,
        *,
        reason_code: object = None,
        severity: object = None,
        **facts,
    ) -> None:
        """Record how a started step ended. A step that is None is skipped."""
        if step is not None:
            self._writer._end_step(
                self.run_id, step, outcome, reason_code, severity, facts
            )

    def end_run(self, status: str, *, reason_code: object = None, **facts) -> None:
        """Record the end of the run, closing any step still open."""
        self._writer._end_run(self.run_id, self._started, status, reason_code, facts)


class _NoRecord:
    """The recorder of a run that is not recorded: run_weekly() called directly."""

    run_id = None
    broken = False
    _STEP = object()

    def start(self, kind: str, target: object, **facts) -> object:
        return self._STEP  # not None: an unrecorded run delivers as before

    def end(self, step: object, outcome: object, **facts) -> None:
        return None

    def end_run(self, status: str, **facts) -> None:
        return None


NO_RECORD = _NoRecord()


def open_writer(db_path, *, now=None, monotonic=None) -> RunStateWriter:
    """Take the writer seat of ``db_path`` and close every start left without an end.

    Order: the SQLite build, the parent folder, the real path of the database,
    the OS lock (no waiting), a new database if there is no file, a read-only
    examination of the file, and only then the read-write connection. On any
    failure the lock is released and RunStateUnavailable says why; the database
    file is never deleted or overwritten, and a file that is not ours is never
    opened for writing.

    ``now`` returns an aware datetime and ``monotonic`` seconds as a float;
    both are injectable so tests do not depend on the wall clock.
    """
    _check_environment()
    try:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        # One name for the lock file, the scratch files, the examination and
        # the connection. A symbolic link to the database must lead to the
        # same lock file as the database itself.
        path = Path(db_path).resolve()
    except (OSError, RuntimeError) as exc:
        raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    try:
        lock_fd = os.open(
            str(path.with_name(path.name + ".writer.lock")),
            os.O_RDWR | os.O_CREAT,
            0o644,
        )
    except OSError as exc:
        raise RunStateUnavailable("LOCK_UNAVAILABLE") from exc
    try:
        _lock_file(lock_fd)
    except OSError as exc:
        _quietly(lambda: os.close(lock_fd))
        code = "WRITER_BUSY" if exc.errno in _BUSY_ERRNOS else "LOCK_UNAVAILABLE"
        raise RunStateUnavailable(code) from exc
    con = None
    try:
        try:
            _remove_scratch(path)
            if not os.path.lexists(path):
                _build_new(path)
            names = os.stat(path).st_nlink
        except (OSError, sqlite3.Error) as exc:
            raise RunStateUnavailable("DB_UNAVAILABLE") from exc
        if names != 1:
            # A hard link is a second door to the same file with its own lock
            # file and its own -wal: no path can make the two one.
            raise RunStateUnavailable("DB_ALIASED")
        con = _open_for_writing(path, _examine(path))
        writer = RunStateWriter(path, lock_fd, con, now, monotonic)
        try:
            writer._recover()
        except Exception as exc:
            # Unfinished starts that cannot be closed: do not run on top of them.
            raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    except BaseException:
        if con is not None:
            _quietly(con.close)
        _quietly(lambda: _unlock_file(lock_fd))
        _quietly(lambda: os.close(lock_fd))
        raise
    with writer._mutex:
        writer._export_pending()
    return writer


# ── Reading (for the monitor, K-0G) ──────────────────────────────────────────


def _open_reader(db_path) -> sqlite3.Connection:
    """A connection that cannot write. A missing file is not created."""
    _check_environment()
    path = Path(db_path)
    if not path.is_file():
        raise RunStateUnavailable("DB_UNAVAILABLE")
    try:
        con = sqlite3.connect(_uri(path, "ro"), uri=True, timeout=_BUSY_TIMEOUT_S)
    except sqlite3.Error as exc:
        raise RunStateUnavailable("DB_UNAVAILABLE") from exc
    try:
        try:
            con.execute("PRAGMA query_only=ON")
            refusal = _refusal(_header(con))
        except sqlite3.OperationalError as exc:
            raise RunStateUnavailable("DB_UNAVAILABLE") from exc
        except sqlite3.DatabaseError as exc:
            raise RunStateUnavailable("DB_CORRUPT") from exc
        if refusal:
            raise RunStateUnavailable(refusal)
    except BaseException:
        _quietly(con.close)
        raise
    return con


_RUN_COLUMNS = (
    "run_id",
    "status",
    "started_at",
    "started_at_kst",
    "ended_at",
    "ended_at_kst",
    "duration_ms",
    "reason_code",
    "pid",
    "dry_run",
    "max_per_market",
    "markets",
    "facts",
    "exported_seq",
)
_STEP_COLUMNS = (
    "step_id",
    "run_id",
    "kind",
    "target",
    "state",
    "outcome",
    "reason_code",
    "severity",
    "started_at",
    "started_at_kst",
    "ended_at",
    "ended_at_kst",
    "duration_ms",
    "facts",
)


def _run_dict(row: tuple) -> dict:
    run = dict(zip(_RUN_COLUMNS, row))
    run["dry_run"] = bool(run["dry_run"])
    run["markets"] = json.loads(run["markets"])
    run["facts"] = json.loads(run["facts"])
    return run


def _step_dict(row: tuple) -> dict:
    step = dict(zip(_STEP_COLUMNS, row))
    step["facts"] = json.loads(step["facts"])
    return step


def read_runs(db_path, *, limit: int = 50) -> list[dict]:
    """The most recent runs, newest first."""
    with contextlib.closing(_open_reader(db_path)) as con:
        rows = con.execute(
            f"SELECT {', '.join(_RUN_COLUMNS)} FROM runs "
            "ORDER BY started_at DESC, run_id DESC LIMIT ?",
            (max(int(limit), 0),),
        ).fetchall()
        return [_run_dict(row) for row in rows]


def read_run(db_path, run_id: str) -> dict | None:
    """One run with its steps in start order, or None."""
    with contextlib.closing(_open_reader(db_path)) as con:
        row = con.execute(
            f"SELECT {', '.join(_RUN_COLUMNS)} FROM runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        steps = con.execute(
            f"SELECT {', '.join(_STEP_COLUMNS)} FROM steps WHERE run_id = ? "
            "ORDER BY step_id",
            (run_id,),
        ).fetchall()
        return {"run": _run_dict(row), "steps": [_step_dict(step) for step in steps]}


def read_events(db_path, run_id: str) -> list[dict]:
    """The events of one run, oldest first: the objects the export writes."""
    with contextlib.closing(_open_reader(db_path)) as con:
        return _event_objects(con, run_id)
