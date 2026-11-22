"""K-0G: the minimal monitor page built from the run-state database.

What is pinned down here (tools/monitor/build.py):

* the page never blocks a run: the database is read through
  run_state.read_runs / read_run only, nothing in its folder is changed and a
  writer keeps recording while and after a page is built;
* the default is "unknown": a database that cannot be read shows a reason
  code, a value outside the fixed lists shows "알 수 없음", and neither is ever
  shown or counted as "정상";
* no value from the database becomes markup: the result is read back with the
  standard library HTML parser, and what was injected must still be there as
  text while the sets of tags and attributes stay inside the allow-lists;
* the page is replaced atomically, and when that fails the previous page is
  left byte for byte as it was;
* times: what Python decides at build time, with an injected clock. The
  "stale page" decision exists only in the page's script and is NOT reachable
  from here (it is shown with a real browser in tmp/k0g/evidence).

Everything happens under tmp_path. Sample databases are made with
run_state.open_writer() and an injected clock; values the writer would refuse
are planted with sqlite3 in those throwaway files (the tests are the only
place where SQL is written). Nothing here reads the repository's .env, touches
its runs/, logs/, .cache/ or .git, calls the network or a real codex; a
fixture compares runs/ and logs/ before and after every test.
"""

from __future__ import annotations

import ast
import base64
import hashlib
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

import pytest

from scheduler import run_state as rs
from tools.monitor import build as mon

REPO_ROOT = Path(__file__).resolve().parent.parent
UTC = timezone.utc

ALLOWED_TAGS = frozenset(
    "html head meta title style body header main section footer h1 h2 p table "
    "thead tbody tr th td span strong code ul li script".split()
)
ALLOWED_ATTRS = frozenset(
    "lang charset http-equiv content class id hidden scope data-since data-limit-s".split()
)
KIND_WORDS = ("정상", "주의", "막힘", "미확정", "알 수 없음")
UNKNOWN = "알 수 없음"
UTC_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


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


class Clock:
    """An injected clock for the writer and for the page."""

    def __init__(self, moment: datetime | None = None) -> None:
        self.moment = moment or datetime(2026, 11, 14, 0, 0, 0, tzinfo=UTC)
        self.mono = 1000.0

    def now(self) -> datetime:
        return self.moment

    def monotonic(self) -> float:
        return self.mono

    def tick(self, seconds: float) -> None:
        self.mono += seconds
        self.moment += timedelta(seconds=seconds)


class Node:
    def __init__(self, tag: str, attrs: list, parent: "Node | None") -> None:
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children: list = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()

    def find_all(self, tag: str) -> list:
        return [node for node in self.walk() if node.tag == tag and node is not self]

    def with_class(self, name: str) -> list:
        return [
            node
            for node in self.walk()
            if name in (node.attrs.get("class") or "").split()
        ]

    def raw_text(self) -> str:
        """Every character below this node, hidden or not."""
        return "".join(
            child if isinstance(child, str) else child.raw_text()
            for child in self.children
        )

    def text(self) -> str:
        """What a reader sees before any script runs: hidden parts left out."""
        parts = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif "hidden" not in child.attrs and child.tag not in ("script", "style"):
                parts.append(child.text())
        return " ".join("".join(parts).split())


class Dom(HTMLParser):
    """The page as the standard library parser reads it. Nesting must be exact:
    the generator's own markup is well formed, so a stray tag is a finding."""

    VOID = frozenset({"meta"})

    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [], None)
        self._at = self.root
        self.comments: list = []
        self.declarations: list = []
        self.repeated_attrs: list = []
        self.feed(text)
        self.close()
        assert self._at is self.root, f"<{self._at.tag}> was never closed"

    def handle_starttag(self, tag, attrs):
        names = [name for name, _ in attrs]
        if len(names) != len(set(names)):
            self.repeated_attrs.append(tag)
        node = Node(tag, attrs, self._at)
        self._at.children.append(node)
        if tag not in self.VOID:
            self._at = node

    def handle_startendtag(self, tag, attrs):
        raise AssertionError(f"self-closing <{tag}/> is not written by the generator")

    def handle_endtag(self, tag):
        assert tag == self._at.tag, f"</{tag}> closes <{self._at.tag}>"
        self._at = self._at.parent

    def handle_data(self, data):
        self._at.children.append(data)

    def handle_comment(self, data):
        self.comments.append(data)

    def handle_decl(self, decl):
        self.declarations.append(decl)

    def handle_pi(self, data):
        raise AssertionError("a processing instruction in the page")

    def unknown_decl(self, data):
        raise AssertionError("a CDATA section or unknown declaration in the page")

    # -- queries --

    def nodes(self) -> list:
        return [node for node in self.root.walk() if node is not self.root]

    def by_id(self, name: str) -> Node:
        found = [node for node in self.nodes() if node.attrs.get("id") == name]
        assert len(found) == 1, f"id={name!r} appears {len(found)} times"
        return found[0]

    def rows(self, section: str) -> list:
        """The body rows of the table in a section, as lists of cell nodes."""
        return [
            [cell for cell in row.children if isinstance(cell, Node)]
            for body in self.by_id(section).find_all("tbody")
            for row in body.children
            if isinstance(row, Node)
        ]

    def cells(self, section: str) -> list:
        return [[cell.text() for cell in row] for row in self.rows(section)]


def assert_safe_markup(dom: Dom) -> None:
    """Only the generator's own tags and attributes, one script, one style."""
    nodes = dom.nodes()
    assert {node.tag for node in nodes} <= ALLOWED_TAGS
    assert {name for node in nodes for name in node.attrs} <= ALLOWED_ATTRS
    assert dom.repeated_attrs == []
    assert dom.comments == []
    assert [d.lower() for d in dom.declarations] == ["doctype html"]
    scripts = [node for node in nodes if node.tag == "script"]
    styles = [node for node in nodes if node.tag == "style"]
    assert len(scripts) == 1 and scripts[0].attrs == {}
    assert len(styles) == 1 and styles[0].attrs == {}
    assert scripts[0].raw_text() == mon._SCRIPT
    assert styles[0].raw_text() == mon._STYLE
    for node in nodes:
        since = node.attrs.get("data-since")
        if since is not None:
            assert UTC_STAMP.fullmatch(since), since
            assert node.attrs["data-limit-s"] in {
                str(mon.STALE_AFTER_S),
                str(mon.NO_RUN_AFTER_S),
                str(mon.RUNNING_SUSPECT_AFTER_S),
            }
        for name in ("class", "id"):
            value = node.attrs.get(name)
            if value is not None:
                assert re.fullmatch(r"[a-z][a-z0-9\- ]*", value), (name, value)
        if node.tag == "meta":
            assert set(node.attrs) in (
                {"charset"},
                {"http-equiv", "content"},
            )


def tags_shown(dom: Dom) -> list:
    """The text of every classification tag on the page, in order."""
    return [node.text() for node in dom.root.with_class("tag")]


def render(db: Path, moment: datetime, out: Path | None = None):
    """Build the page; (exit code, parsed page, page text)."""
    out = out or db.parent / "monitor.html"
    code = mon.build(db, out, now=lambda: moment)
    text = out.read_bytes().decode("utf-8")
    dom = Dom(text)
    assert_safe_markup(dom)
    return code, dom, text


def plant(db: Path, statement: str, args: tuple = ()) -> None:
    """Change the throwaway database behind the writer's back (CHECKs off)."""
    con = sqlite3.connect(db)
    try:
        con.execute("PRAGMA ignore_check_constraints=ON")
        con.execute(statement, args)
        con.commit()
    finally:
        con.close()


def abandon(writer) -> None:
    """What the OS does for a dead process: connection and lock gone, no record."""
    writer._con.close()
    rs._unlock_file(writer._lock_fd)
    os.close(writer._lock_fd)
    writer._closed = True


def utc_stamp(moment: datetime) -> str:
    """The form the page uses in data-since."""
    return moment.astimezone(UTC).isoformat(timespec="milliseconds")[:-6] + "Z"


# ── fixtures and sample databases ────────────────────────────────────────────


@pytest.fixture(autouse=True)
def repository_folders_are_never_touched(tmp_path):
    """The default database path points into tmp_path, and the repository's own
    runs/ and logs/ are the same before and after each test."""
    watched = [REPO_ROOT / "runs", REPO_ROOT / "logs"]
    before = [tree_digest(folder) for folder in watched]
    elsewhere = tmp_path / "default-runs" / "state.db"
    saved = rs.DEFAULT_DB_PATH
    rs.DEFAULT_DB_PATH = elsewhere
    try:
        yield elsewhere
    finally:
        rs.DEFAULT_DB_PATH = saved
    assert [tree_digest(folder) for folder in watched] == before
    assert not elsewhere.parent.exists()  # no test fell back on a default path


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "runs" / "state.db"


@pytest.fixture
def opened():
    """open_writer() whose writers are closed when the test ends."""
    made = []

    def _open(path, clock):
        writer = rs.open_writer(path, now=clock.now, monotonic=clock.monotonic)
        made.append(writer)
        return writer

    yield _open
    for writer in made:
        writer.close()


WEEK_NAMES = ("삼성전자", "SK-Hynix", "Apple Inc.")


def full_week(db: Path, clock: Clock, names=WEEK_NAMES, dry_run=False) -> str:
    """One clean week: 2 discoveries, the valuations, 1 file, 4 deliveries."""
    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    rec = writer.start_run(markets=["KR", "US"], max_per_market=3, dry_run=dry_run)
    for market in ("KR", "US"):
        step = rec.start("discovery", market)
        clock.tick(2)
        rec.end(step, "ok", news_count=40, discovered=8, path="news_llm")
    for name in names:
        step = rec.start("valuation", name, ticker="005930", market="KR")
        clock.tick(65)
        rec.end(step, "success", degraded=[])
    step = rec.start("delivery", "excel_upload")
    rec.end(step, "ok", eligible=len(names), uploaded=len(names))
    step = rec.start("artifact", "summary_file")
    rec.end(step, "ok")
    for target in ("email", "wordpress", "naver"):
        step = rec.start("delivery", target)
        clock.tick(1)
        rec.end(step, "ok")
    rec.end_run(
        "COMPLETED",
        errors=0,
        valuations_total=len(names),
        valuations_by_status={"success": len(names)},
    )
    assert not rec.broken
    writer.close()
    return rec.run_id


def blocked_weeks(db: Path, clock: Clock) -> tuple[str, str]:
    """An older run whose process died, then a run that failed in every way."""
    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    dead = writer.start_run(markets=["KR"], max_per_market=1, dry_run=False)
    assert dead.start("discovery", "KR") is not None
    assert dead.start("valuation", "Dead Co", ticker="DEAD", market="US") is not None
    assert dead.start("delivery", "email") is not None
    abandon(writer)
    clock.tick(7 * 86400)

    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    assert writer.recovered == (dead.run_id,)
    rec = writer.start_run(markets=["KR", "US"], max_per_market=3, dry_run=False)
    step = rec.start("discovery", "KR")
    rec.end(
        step,
        "failed",
        reason_code="DISCOVERY_EXCEPTION",
        severity="failure",
        error_type="TimeoutError",
    )
    step = rec.start("discovery", "US")
    rec.end(step, "empty", reason_code="NEWS_EMPTY", severity="empty", news_count=0)
    step = rec.start("valuation", "Blocked Draft Co", ticker="BLKD", market="US")
    rec.end(
        step, "draft_blocked", reason_code="RECONCILIATION_BLOCKED", severity="failure"
    )
    step = rec.start("valuation", "No Result Co", ticker="NORS", market="US")
    rec.end(step, "no_result", reason_code="IDENTITY_NOT_FOUND", severity="failure")
    step = rec.start("valuation", "Failed Co", ticker="FAIL", market="US")
    rec.end(
        step,
        "failed",
        reason_code="VALUATION_EXCEPTION",
        severity="failure",
        error_type="ZeroDivisionError",
        stage="valuation",
    )
    step = rec.start("valuation", "Degraded Co", ticker="DGRD", market="US")
    rec.end(
        step,
        "success",
        reason_code="ENRICHMENT_DEGRADED",
        severity="degraded",
        degraded=["peers", "wacc"],
    )
    step = rec.start("delivery", "excel_upload")
    rec.end(step, "partial", eligible=2, uploaded=1)
    step = rec.start("artifact", "summary_file")
    rec.end(step, "failed")
    step = rec.start("delivery", "email")
    rec.end(step, "raised", error_type="SMTPAuthenticationError")
    step = rec.start("delivery", "wordpress")
    rec.end(step, "no_result")
    assert rec.start("delivery", "naver") is not None  # open when the run fails
    rec.end_run("FAILED", reason_code="RUN_EXCEPTION", error_type="RuntimeError")
    assert not rec.broken
    writer.close()
    return dead.run_id, rec.run_id


def run_row(**over) -> dict:
    row = {
        "run_id": "wr-20261114T000000Z-0123abcd",
        "status": "COMPLETED",
        "started_at": "2026-11-14T00:00:00.000+00:00",
        "started_at_kst": "2026-11-14T09:00:00.000+09:00",
        "ended_at": "2026-11-14T00:10:00.000+00:00",
        "ended_at_kst": "2026-11-14T09:10:00.000+09:00",
        "duration_ms": 600000,
        "reason_code": None,
        "pid": 4321,
        "dry_run": False,
        "max_per_market": 3,
        "markets": ["KR", "US"],
        "facts": {"errors": 0},
        "exported_seq": 7,
    }
    row.update(over)
    return row


def step_row(**over) -> dict:
    row = {
        "step_id": 1,
        "run_id": "wr-20261114T000000Z-0123abcd",
        "kind": "valuation",
        "target": "Acme Corp",
        "state": "ENDED",
        "outcome": "success",
        "reason_code": None,
        "severity": None,
        "started_at": "2026-11-14T00:01:00.000+00:00",
        "started_at_kst": "2026-11-14T09:01:00.000+09:00",
        "ended_at": "2026-11-14T00:02:00.000+00:00",
        "ended_at_kst": "2026-11-14T09:02:00.000+09:00",
        "duration_ms": 60000,
        "facts": {},
    }
    row.update(over)
    return row


def fake_readers(monkeypatch, runs, steps=(), detail="from runs"):
    """Stand in for the two read functions: no file is involved."""
    calls = []

    def read_runs(db_path, *, limit=50):
        calls.append(("read_runs", limit))
        return runs() if callable(runs) else runs

    def read_run(db_path, run_id):
        calls.append(("read_run", run_id))
        if detail == "from runs":
            return {"run": runs[0], "steps": list(steps)}
        return detail() if callable(detail) else detail

    monkeypatch.setattr(rs, "read_runs", read_runs)
    monkeypatch.setattr(rs, "read_run", read_run)
    return calls


AFTER_THE_WEEK = datetime(2026, 11, 14, 6, 0, 0, tzinfo=UTC)


# ── 1. a clean week ──────────────────────────────────────────────────────────


def test_a_clean_week_is_shown_as_normal_in_every_row(db):
    run_id = full_week(db, Clock())
    code, dom, _ = render(db, AFTER_THE_WEEK)

    assert code == 0
    assert "읽음" in dom.by_id("state").text()
    runs = dom.cells("runs")
    assert len(runs) == 1
    kind, status, started, took, reason, dry, valuations = runs[0]
    assert kind == "정상" and "완료" in status and "COMPLETED" in status
    assert started == "2026-11-14 09:00:00 KST"  # UTC + 9 hours
    assert took == "3분 22초"  # 2 + 2 + 3 * 65 + 3 seconds on the injected clock
    assert (reason, dry) == ("-", "-")
    assert valuations == "3건 (success 3)"

    steps = dom.cells("steps")
    assert len(steps) == 10
    assert [row[0] for row in steps] == ["정상"] * 10
    assert [row[2] for row in steps[2:5]] == list(WEEK_NAMES)
    assert dom.by_id("step-counts").text() == (
        "단계 10개: 정상 10, 주의 0, 막힘 0, 미확정 0, 알 수 없음 0"
    )
    assert run_id in dom.by_id("steps").text()
    last = dom.by_id("last-status").text()
    assert last.startswith("정상") and "완료" in last


def test_a_dry_run_is_marked_and_still_counts_as_the_last_run(db):
    full_week(db, Clock(), dry_run=True)
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert dom.cells("runs")[0][5] == "dry-run"
    assert "마지막 실행 시작 후 6시간 0분" in dom.by_id("last-age").text()


# ── 2. the classification table (policy 4.1, 4.2) ────────────────────────────

RUN_CASES = [
    ({}, "ok"),
    ({"facts": {}}, "ok"),
    ({"facts": {"errors": None}}, "warn"),  # the key is there: it must be 0
    ({"facts": {"errors": False}}, "warn"),
    ({"facts": {"errors": 0.0}}, "warn"),
    ({"facts": {"errors": []}}, "warn"),
    ({"facts": {"errors": {}}}, "warn"),
    ({"reason_code": "SELECTION_EMPTY"}, "warn"),
    ({"reason_code": "<invalid>"}, "warn"),
    ({"reason_code": 0}, "warn"),
    ({"facts": {"errors": 2}}, "warn"),
    ({"facts": {"errors": True}}, "warn"),
    ({"facts": {"errors": "0"}}, "warn"),
    ({"facts": '{"errors": 0}'}, "warn"),
    ({"facts": None}, "warn"),
    ({"facts": [0]}, "warn"),
    ({"status": "COMPLETED_WITH_ERRORS"}, "warn"),
    ({"status": "FAILED"}, "blocked"),
    ({"status": "INTERRUPTED"}, "blocked"),
    ({"status": "RUNNING", "ended_at": None}, "open"),
]
NOT_A_STATUS = [
    None,
    "",
    "<invalid>",
    "<masked>",
    "completed",
    "COMPLETED ",
    " COMPLETED",
    "COMPLETED\n",
    "DONE",
    "OK",
    0,
    1,
    True,
    1.0,
    ["COMPLETED"],
    {"COMPLETED": 1},
    b"COMPLETED",
]


@pytest.mark.parametrize("over, expected", RUN_CASES)
def test_run_classification_table(over, expected):
    kind, label = mon.classify_run(run_row(**over), AFTER_THE_WEEK)
    assert kind == expected
    assert label and isinstance(label, str)


@pytest.mark.parametrize("status", NOT_A_STATUS, ids=repr)
def test_a_status_outside_the_list_is_unknown_and_never_normal(status):
    kind, label = mon.classify_run(run_row(status=status), AFTER_THE_WEEK)
    assert (kind, label) == ("unknown", UNKNOWN)


STEP_TABLE = {
    "discovery": {"ok": "ok", "empty": "warn", "failed": "blocked"},
    "valuation": {
        "success": "ok",
        "draft_blocked": "blocked",
        "no_result": "blocked",
        "failed": "blocked",
    },
    "artifact": {"ok": "ok", "failed": "blocked"},
    "delivery": {
        "ok": "ok",
        "partial": "warn",
        "no_result": "warn",
        "raised": "blocked",
    },
}
EVERY_OUTCOME = sorted({name for names in STEP_TABLE.values() for name in names})


def test_the_step_table_mirrors_the_writers_lists():
    """If run_state grows a kind or an outcome, this file must grow a row."""
    assert set(STEP_TABLE) == set(rs._KINDS)
    for kind, outcomes in STEP_TABLE.items():
        assert set(outcomes) == set(rs._OUTCOMES[kind])


@pytest.mark.parametrize("kind", sorted(STEP_TABLE))
@pytest.mark.parametrize("outcome", EVERY_OUTCOME + [None, "<invalid>", "", "OK", 1])
def test_ended_step_classification_table(kind, outcome):
    expected = STEP_TABLE[kind].get(outcome, "unknown")
    got, label = mon.classify_step(step_row(kind=kind, outcome=outcome))
    assert got == expected
    assert (label == UNKNOWN) == (expected == "unknown")


@pytest.mark.parametrize("kind", sorted(STEP_TABLE) + ["report", None, "<invalid>"])
@pytest.mark.parametrize("outcome", [None, "ok", "success", "raised", "<invalid>"])
@pytest.mark.parametrize(
    "state, expected",
    [("STARTED", "open"), ("INTERRUPTED", "blocked"), ("UNKNOWN_DELIVERY", "blocked")],
)
def test_a_step_that_did_not_end_is_never_normal(kind, outcome, state, expected):
    got, _ = mon.classify_step(step_row(kind=kind, outcome=outcome, state=state))
    assert got == expected


@pytest.mark.parametrize(
    "over",
    [
        {"state": None},
        {"state": "ended"},
        {"state": "DONE"},
        {"state": "<invalid>"},
        {"state": 1},
        {"state": ["ENDED"]},
        {"kind": "report"},
        {"kind": None},
        {"kind": "<invalid>"},
        {"kind": "Valuation"},
        {"kind": 3},
    ],
    ids=repr,
)
def test_a_step_outside_the_lists_is_unknown_and_never_normal(over):
    assert mon.classify_step(step_row(**over)) == ("unknown", UNKNOWN)


@pytest.mark.parametrize(
    "kind, outcome",
    [(k, o) for k, table in STEP_TABLE.items() for o, v in table.items() if v == "ok"],
)
@pytest.mark.parametrize(
    "over",
    [
        {"reason_code": "ENRICHMENT_DEGRADED"},
        {"reason_code": "<invalid>"},
        {"reason_code": ""},
        {"severity": "degraded"},
        {"severity": "<invalid>"},
        {"facts": {"degraded": ["peers"]}},
        {"facts": {"degraded": "peers"}},
        {"facts": {"degraded": None, "stage": "x"}, "severity": "degraded"},
        {"facts": None},
        {"facts": "{}"},
        {"facts": []},
    ],
    ids=repr,
)
def test_a_good_outcome_is_normal_only_when_nothing_is_attached(kind, outcome, over):
    clean = step_row(kind=kind, outcome=outcome)
    assert mon.classify_step(clean)[0] == "ok"
    assert mon.classify_step(dict(clean, facts={"degraded": []}))[0] == "ok"
    assert mon.classify_step(dict(clean, **over))[0] == "warn"


# ── 3. what "blocked" looks like, through a real database ────────────────────


def test_blocked_runs_and_steps_are_shown_as_blocked(db):
    clock = Clock()
    dead_id, failed_id = blocked_weeks(db, clock)
    clock.tick(600)
    code, dom, text = render(db, clock.now())

    assert code == 0
    runs = dom.cells("runs")
    assert [row[0] for row in runs] == ["막힘", "막힘"]
    assert "실패" in runs[0][1] and "FAILED" in runs[0][1]
    assert "RUN_EXCEPTION" in runs[0][4] and "RuntimeError" in runs[0][4]
    assert "중단됨" in runs[1][1] and "INTERRUPTED" in runs[1][1]
    assert runs[1][4] == "NO_END_RECORDED"
    assert dom.by_id("last-status").text().startswith("막힘")

    steps = dom.cells("steps")  # the newest run only
    assert failed_id in dom.by_id("steps").text() and dead_id not in text
    by_target = {row[2]: row for row in steps}
    assert len(steps) == len(by_target) == 11
    shown = [(row[1].split()[0], row[2], row[0]) for row in steps]
    assert shown == [
        ("수집", "KR", "막힘"),
        ("수집", "US", "주의"),
        ("평가", "Blocked Draft Co", "막힘"),
        ("평가", "No Result Co", "막힘"),
        ("평가", "Failed Co", "막힘"),
        ("평가", "Degraded Co", "주의"),
        ("전달", "엑셀 업로드", "주의"),
        ("산출물", "요약 파일", "막힘"),
        ("전달", "메일", "막힘"),
        ("전달", "WordPress", "주의"),
        ("전달", "네이버 블로그", "막힘"),
    ]
    failed = by_target["Failed Co"]
    assert "VALUATION_EXCEPTION" in failed[4]
    assert "ZeroDivisionError" in failed[6] and "FAIL" in failed[6]
    assert (
        "peers" in by_target["Degraded Co"][6] and "wacc" in by_target["Degraded Co"][6]
    )
    open_delivery = by_target["네이버 블로그"]
    assert (
        "전달 여부 불명" in open_delivery[3] and "UNKNOWN_DELIVERY" in open_delivery[3]
    )
    assert open_delivery[4] == "RUN_ENDED_WITH_OPEN_STEP"
    assert "SMTPAuthenticationError" in by_target["메일"][6]
    assert dom.by_id("step-counts").text() == (
        "단계 11개: 정상 0, 주의 4, 막힘 7, 미확정 0, 알 수 없음 0"
    )


def test_steps_of_a_run_whose_process_died_are_blocked_not_open(db):
    clock = Clock()
    writer = rs.open_writer(db, now=clock.now, monotonic=clock.monotonic)
    dead = writer.start_run(markets=["KR"], max_per_market=1, dry_run=False)
    assert dead.start("valuation", "Dead Co", ticker="DEAD", market="US") is not None
    assert dead.start("delivery", "email") is not None
    abandon(writer)
    clock.tick(60)
    rs.open_writer(db, now=clock.now, monotonic=clock.monotonic).close()  # recovery

    code, dom, _ = render(db, clock.now())
    assert code == 0
    assert dom.cells("runs")[0][0] == "막힘"
    steps = dom.cells("steps")
    assert [(row[0], row[2]) for row in steps] == [
        ("막힘", "Dead Co"),
        ("막힘", "메일"),
    ]
    assert "중단됨" in steps[0][3] and "전달 여부 불명" in steps[1][3]
    assert [row[4] for row in steps] == ["NO_END_RECORDED"] * 2


# ── 4. the database cannot be read ───────────────────────────────────────────


def assert_not_read(code, dom, reason: str) -> None:
    assert code == 2
    state = dom.by_id("state").find_all("p")[0].text()
    assert state.startswith("막힘") and "읽지 못했다" in state
    assert dom.by_id("state-code").text() == reason
    assert dom.rows("runs") == [] and dom.rows("steps") == []
    assert "읽지 못해 표시할 수 없다" in dom.by_id("runs").text()
    assert "읽지 못해 표시할 수 없다" in dom.by_id("steps").text()
    assert UNKNOWN in dom.by_id("last-age").text()
    assert "data-since" not in dom.by_id("last-age").attrs
    assert tags_shown(dom) == ["막힘"]  # the only verdict on the page
    assert dom.root.with_class("ok") == []  # and nothing is marked as normal


def test_no_database_file(db, tmp_path):
    db.parent.mkdir()
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "DB_UNAVAILABLE")
    assert sorted(p.name for p in db.parent.iterdir()) == ["monitor.html"]


def test_a_file_that_is_not_a_database(db):
    db.parent.mkdir()
    db.write_bytes(b"this is not a database at all\n" * 400)
    before = digest(db)
    with pytest.raises(rs.RunStateUnavailable) as refusal:
        rs.read_runs(db)
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, refusal.value.reason_code)
    assert refusal.value.reason_code in ("DB_CORRUPT", "DB_FOREIGN")
    assert digest(db) == before


def test_someone_elses_database_and_an_empty_file(db):
    db.parent.mkdir()
    db.write_bytes(b"")
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "DB_FOREIGN")
    db.unlink()
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE runs (run_id TEXT)")
    con.commit()
    con.close()
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "DB_FOREIGN")


def test_another_schema_version(db):
    full_week(db, Clock())
    plant(db, "PRAGMA user_version=99")
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "SCHEMA_UNSUPPORTED")


def test_an_unsupported_sqlite(db, monkeypatch):
    full_week(db, Clock())
    monkeypatch.setattr(rs, "_MIN_SQLITE", (99, 0, 0))
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "SQLITE_UNSUPPORTED")


@pytest.mark.parametrize(
    "damage, error",
    [
        ("DROP TABLE steps", "OperationalError"),
        ("DROP TABLE runs", "OperationalError"),
        ("UPDATE runs SET facts = 'not json at all'", "JSONDecodeError"),
        ("UPDATE runs SET markets = '{'", "JSONDecodeError"),
        ("UPDATE steps SET facts = '[1,' WHERE step_id = 3", "JSONDecodeError"),
    ],
)
def test_a_file_with_the_right_header_and_broken_content(db, damage, error):
    """The read functions check the header only: what is behind it can raise
    anything. The page says READ_FAILED and the class name, nothing more."""
    full_week(db, Clock())
    plant(db, damage)
    with pytest.raises(Exception) as raw:
        rs.read_run(db, rs.read_runs(db)[0]["run_id"])
    assert type(raw.value).__name__ == error
    assert not isinstance(raw.value, rs.RunStateUnavailable)

    code, dom, text = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "READ_FAILED")
    assert dom.by_id("state-class").text() == error
    assert str(raw.value) not in text and WEEK_NAMES[0] not in text


def test_the_second_read_does_not_find_the_run(db, monkeypatch):
    full_week(db, Clock())
    monkeypatch.setattr(rs, "read_run", lambda db_path, run_id: None)
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "READ_INCONSISTENT")
    assert WEEK_NAMES[0] not in text


@pytest.mark.parametrize(
    "runs, detail",
    [
        (None, None),
        ("runs", None),
        ({"run_id": "x"}, None),
        ([["not", "a", "dict"]], None),
        ([run_row(), "second is not a dict"], "from runs"),
        ([run_row()], "not a dict"),
        ([run_row()], {"run": run_row()}),
        ([run_row()], {"run": None, "steps": []}),
        ([run_row()], {"run": run_row(), "steps": None}),
        ([run_row()], {"run": run_row(), "steps": [None]}),
        ([run_row()], {"run": run_row(), "steps": ["step"]}),
    ],
    ids=str,
)
def test_a_reply_of_the_wrong_shape_is_a_failed_read(db, monkeypatch, runs, detail):
    db.parent.mkdir()
    fake_readers(monkeypatch, runs, detail=detail)
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "READ_FAILED")


def test_an_exception_text_never_reaches_the_page_or_the_log(
    db, tmp_path, monkeypatch, caplog
):
    db.parent.mkdir()
    secret = f"k0g-secret-text {tmp_path} C:\\Users\\someone\\private.txt"

    def raising():
        raise ValueError(secret)

    fake_readers(monkeypatch, raising)
    with caplog.at_level(logging.DEBUG):
        code, dom, text = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "READ_FAILED")
    assert dom.by_id("state-class").text() == "ValueError"
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "READ_FAILED" in logged
    for place in (text, logged):
        assert "k0g-secret-text" not in place
        assert str(tmp_path) not in place and tmp_path.as_posix() not in place
        assert "someone" not in place


@pytest.mark.parametrize(
    "name", ["<b>Bad</b>", "X" * 32, "has space", "", "한글Error", "Odd-Name"]
)
def test_an_exception_class_name_is_shown_only_in_its_shape(db, monkeypatch, name):
    db.parent.mkdir()
    odd = type(name, (Exception,), {})

    def raising():
        raise odd("x")

    fake_readers(monkeypatch, raising)
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, "READ_FAILED")
    assert dom.by_id("state").with_class("state-class") == []
    assert [n for n in dom.nodes() if n.attrs.get("id") == "state-class"] == []
    if name:
        assert name not in text


@pytest.mark.parametrize(
    "code_value", ["<b>code</b>", "lower_case", "X" * 32, "", None, 5, "WITH SPACE"]
)
def test_a_reason_code_is_shown_only_in_its_shape(db, monkeypatch, code_value):
    db.parent.mkdir()

    def raising():
        failure = rs.RunStateUnavailable("DB_CORRUPT")
        failure.reason_code = code_value
        raise failure

    fake_readers(monkeypatch, raising)
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert_not_read(code, dom, UNKNOWN)
    assert "DB_CORRUPT" not in text


@pytest.mark.parametrize("stop", [KeyboardInterrupt, SystemExit])
def test_a_stop_request_is_not_swallowed_and_nothing_is_written(db, monkeypatch, stop):
    db.parent.mkdir()
    out = db.parent / "monitor.html"
    out.write_bytes(b"the previous page")

    def raising():
        raise stop()

    fake_readers(monkeypatch, raising)
    with pytest.raises(stop):
        mon.build(db, out, now=lambda: AFTER_THE_WEEK)
    assert out.read_bytes() == b"the previous page"
    assert sorted(p.name for p in db.parent.iterdir()) == ["monitor.html"]


# ── 5. what was on the page before does not survive a failed read ────────────


@pytest.mark.parametrize("damage", ["delete", "garbage", "drop"])
def test_an_earlier_page_does_not_linger_when_the_database_goes_bad(db, damage):
    run_id = full_week(db, Clock())
    code, dom, first = render(db, AFTER_THE_WEEK)
    assert code == 0 and WEEK_NAMES[0] in first and run_id in first

    if damage == "delete":
        for leftover in db.parent.glob("state.db*"):
            leftover.unlink()
    elif damage == "garbage":
        db.write_bytes(b"\x00garbage" * 500)
    else:
        plant(db, "DROP TABLE runs")
    later = AFTER_THE_WEEK + timedelta(hours=1)
    code, dom, second = render(db, later)

    assert code == 2
    assert dom.by_id("state-code").text() in (
        "DB_UNAVAILABLE",
        "DB_CORRUPT",
        "DB_FOREIGN",
        "READ_FAILED",
    )
    for old in (*WEEK_NAMES, run_id, "COMPLETED", "3건"):
        assert old not in second
    assert dom.by_id("built").text() == "2026-11-14 16:00:00 KST"  # the new build


# ── 6. injection ─────────────────────────────────────────────────────────────

HOSTILE_NAMES = [
    "<script>alert(1)</script>",
    '"><img src=x onerror=alert(1)>',
    "' onmouseover='alert(1)",
    "</title><h1>big",
    "</td><p>out",
    "<!-- comment",
    "--> end",
    "&lt;b&gt; &amp; &#x41; &quot;",
    "javascript:alert(1)",
    "<invalid>",
    "<masked>",
    "]]> <![CDATA[x",
    "<style>*{display:none}</style>",
    "{{7*7}} ${7*7} %s",
]


def test_company_names_with_markup_stay_text(db):
    clock = Clock()
    run_id = full_week(db, clock, names=HOSTILE_NAMES)
    stored = [
        step["target"]
        for step in rs.read_run(db, run_id)["steps"]
        if step["kind"] == "valuation"
    ]
    assert stored == HOSTILE_NAMES  # the writer kept them verbatim: a real test

    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    steps = dom.cells("steps")
    assert len(steps) == 7 + len(HOSTILE_NAMES)
    assert [row[2] for row in steps[2 : 2 + len(HOSTILE_NAMES)]] == HOSTILE_NAMES
    assert "<script>alert(1)</script>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text
    assert dom.by_id("step-counts").text().startswith(f"단계 {len(steps)}개: 정상")


MASKED_BY_THE_WRITER = ["</title><h1>big</h1>", "</td></tr></table><p>out"]


def test_names_the_writer_masks_are_shown_as_its_marker(db):
    """Two slashes look like a path to run_state._label(): what is stored, and
    so what is shown, is the marker. The writer's rule is not this module's."""
    run_id = full_week(db, Clock(), names=MASKED_BY_THE_WRITER)
    stored = [
        step["target"]
        for step in rs.read_run(db, run_id)["steps"]
        if step["kind"] == "valuation"
    ]
    assert stored == ["<masked>"] * 2
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert [row[2] for row in dom.cells("steps")[2:4]] == ["<masked>"] * 2
    assert text.count("&lt;masked&gt;") == 2 and "big" not in text


@pytest.mark.parametrize(
    "name",
    MASKED_BY_THE_WRITER
    + [
        "https://example.test/a/b",
        "C:/Users/someone/x",
        "<a href='https://example.test/'>link</a>",
        "//example.test/x",
    ],
)
def test_a_name_that_did_not_pass_the_writer_is_shown_as_text(db, monkeypatch, name):
    """The page does not examine what a name says (policy P8): a value put
    into the database directly is shown, as text and never as a link."""
    db.parent.mkdir()
    fake_readers(monkeypatch, [run_row()], [step_row(target=name)])
    code, dom, _ = render(db, AFTER_THE_WEEK)  # render() checks tags and attributes
    assert code == 0
    assert dom.rows("steps")[0][2].raw_text() == name
    assert [node.tag for node in dom.rows("steps")[0][2].walk()] == ["td"]


INJECTED = "<img src=x onerror=alert(1)>\"'</script><script>alert(2)</script>"
PLANTS = [
    "UPDATE runs SET status = ?",
    "UPDATE runs SET reason_code = ?",
    "UPDATE runs SET started_at = ?",
    "UPDATE runs SET started_at_kst = ?",
    "UPDATE runs SET ended_at = ?",
    "UPDATE runs SET run_id = ?",
    "UPDATE steps SET kind = ?",
    "UPDATE steps SET state = ?",
    "UPDATE steps SET outcome = ?",
    "UPDATE steps SET reason_code = ?",
    "UPDATE steps SET severity = ?",
    "UPDATE steps SET started_at = ?",
    "UPDATE steps SET target = ?",
]


@pytest.mark.parametrize("statement", PLANTS)
def test_markup_planted_in_any_column_never_becomes_markup(db, statement):
    full_week(db, Clock())
    plant(db, statement, (INJECTED,))
    code, dom, text = render(db, AFTER_THE_WEEK)  # render() checks the markup
    assert code == 0
    assert "alert(2)" not in dom.root.find_all("script")[0].raw_text()
    column = statement.split("SET ")[1].split(" =")[0]
    if statement == "UPDATE steps SET target = ?":
        # a name is free text: it must be on the page, as text
        assert [row[2] for row in dom.cells("steps")][2:5] == [INJECTED] * 3
    else:
        # a code, a time or an id is shown only in its shape: this one is not
        assert "alert(1)" not in text
        if column in ("status", "kind", "state", "outcome"):
            assert (
                UNKNOWN in dom.by_id("runs" if "runs" in statement else "steps").text()
            )


@pytest.mark.parametrize(
    "statement, value, run_kind, step_kind",
    [
        (
            "UPDATE runs SET facts = ?",
            '{"errors": "<b>e</b>", "valuations_total": "<i>"}',
            "주의",
            "정상",
        ),
        (
            "UPDATE runs SET facts = ?",
            '{"valuations_total": 1, "valuations_by_status": {"<script>x</script>": 1}}',
            "정상",
            "정상",
        ),
        ("UPDATE runs SET facts = ?", '{"error_type": "<b>Err</b>"}', "정상", "정상"),
        (
            "UPDATE steps SET facts = ?",
            '{"ticker": "<b>T</b>", "market": "\\"><i>", "stage": "<u>s</u>",'
            ' "error_type": "<b>E</b>", "degraded": ["<s>d</s>"], "path": "<p>"}',
            "정상",
            "주의",
        ),
        (
            "UPDATE steps SET facts = ?",
            '{"<b>key</b>": "<b>value</b>"}',
            "정상",
            "정상",
        ),
        (
            "UPDATE steps SET facts = ?",
            '{"degraded": "<b>not a list</b>"}',
            "정상",
            "주의",
        ),
        ("UPDATE steps SET facts = ?", '"<b>a string</b>"', "정상", "주의"),
    ],
)
def test_markup_planted_in_facts_is_not_shown(
    db, statement, value, run_kind, step_kind
):
    full_week(db, Clock())
    plant(db, statement, (value,))
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    for piece in ("<b>", "<i>", "<u>", "<s>", "<script>x", "&lt;b&gt;", "&lt;script"):
        assert piece not in text
    assert dom.cells("runs")[0][0] == run_kind
    assert [row[0] for row in dom.cells("steps")] == [step_kind] * 10


def test_the_markers_of_the_writer_are_shown_as_text(db):
    full_week(db, Clock())
    plant(db, "UPDATE steps SET outcome = '<invalid>' WHERE step_id = 3")
    plant(db, "UPDATE steps SET target = '<masked>' WHERE step_id = 4")
    plant(db, "UPDATE steps SET reason_code = '<invalid>' WHERE step_id = 5")
    plant(db, 'UPDATE steps SET facts = \'{"ticker": "<invalid>"}\' WHERE step_id = 5')
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    steps = dom.cells("steps")
    assert steps[2][0] == UNKNOWN and "<invalid>" in steps[2][3]
    assert steps[3][2] == "<masked>"
    assert steps[4][0] == "주의" and steps[4][4] == "<invalid>"
    assert "<invalid>" in steps[4][6]
    assert text.count("&lt;invalid&gt;") == 3 and text.count("&lt;masked&gt;") == 1
    assert dom.by_id("step-counts").text() == (
        "단계 10개: 정상 8, 주의 1, 막힘 0, 미확정 0, 알 수 없음 1"
    )


def test_control_format_and_surrogate_characters_in_a_name(db, monkeypatch):
    db.parent.mkdir()
    name = "A\u2028B\u202eC\x00D\ud800E\u200bF\nG\x7fH\u2029I"
    fake_readers(monkeypatch, [run_row()], [step_row(target=name)])
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    bad = "\ufffd"
    shown = dom.rows("steps")[0][2].raw_text()
    assert shown == f"A{bad}B{bad}C{bad}D{bad}E{bad}F{bad}G{bad}H{bad}I"
    for raw in "\u2028\u2029\u202e\x00\ud800\u200b\x7f":
        assert raw not in text


@pytest.mark.parametrize("length", [120, 121, 5000])
def test_a_name_longer_than_the_writer_allows_is_not_cut_and_shown(
    db, monkeypatch, length
):
    db.parent.mkdir()
    name = "N" * length
    fake_readers(monkeypatch, [run_row()], [step_row(target=name)])
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    shown = dom.cells("steps")[0][2]
    assert shown == (name if length == 120 else UNKNOWN)
    assert ("N" * 100 in text) == (length == 120)


def test_tag_builder_escapes_text_and_attributes():
    assert (
        mon._tag("p", "<b> & \"x\" 'y'")
        == "<p>&lt;b&gt; &amp; &quot;x&quot; &#x27;y&#x27;</p>"
    )
    assert mon._tag("p", mon._tag("strong", "<")) == "<p><strong>&lt;</strong></p>"
    assert mon._tag("span", "x", class_='a"><b>') == (
        '<span class="a&quot;&gt;&lt;b&gt;">x</span>'
    )
    assert mon._tag("span", "x", hidden=True) == "<span hidden>x</span>"
    assert mon._tag("span", "x", hidden=False) == "<span>x</span>"
    assert mon._tag("p", "a", data_since="s", data_limit_s="7") == (
        '<p data-since="s" data-limit-s="7">a</p>'
    )
    assert mon._tag("meta", http_equiv="refresh", content="60") == (
        '<meta http-equiv="refresh" content="60">'
    )
    assert isinstance(mon._tag("p", "x"), mon._Html)
    assert mon._join("<a>", mon._Html("<b>"), "&", mon._tag("code", "'")) == (
        "&lt;a&gt;<b>&amp;<code>&#x27;</code>"
    )
    assert isinstance(mon._join("x"), mon._Html) and mon._join() == ""
    # markup glued to text with "+" is plain text again, and is escaped as such
    assert mon._join(mon._join("<") + "<") == "&amp;lt;&lt;"
    for bad in (
        lambda: mon._tag("p", "x", hidden="hidden"),
        lambda: mon._tag("p", "x", class_=mon._Html("tag")),
        lambda: mon._join("x", 5),
        lambda: mon._join(None),
        lambda: mon._tag("blink", "x"),
        lambda: mon._tag("img"),
        lambda: mon._tag("a", "x"),
        lambda: mon._tag("p", "x", onclick="alert(1)"),
        lambda: mon._tag("p", "x", style="color:red"),
        lambda: mon._tag("p", "x", href="http://example.invalid"),
        lambda: mon._tag("p", 5),
        lambda: mon._tag("p", None),
        lambda: mon._tag("p", "x", class_=5),
        lambda: mon._tag("meta", "content of a void element"),
    ):
        with pytest.raises((ValueError, TypeError)):
            bad()


# ── 7. values of any type ────────────────────────────────────────────────────

ODD_VALUES = [
    -1,
    2**70,
    float("nan"),
    1.5,
    ["x"],
    {"x": 1},
    b"bytes",
    "\ud800",
    "<b>x</b>",
    "x" * 1_000_000,
]
RUN_COLUMN_CELL = {
    "status": 1,
    "started_at": 2,
    "duration_ms": 3,
    "reason_code": 4,
    "dry_run": 5,
    "facts": 6,
}
STEP_COLUMN_CELL = {
    "kind": 1,
    "state": 3,
    "reason_code": 4,
    "duration_ms": 5,
    "facts": 6,
}


@pytest.mark.parametrize("value", ODD_VALUES, ids=lambda v: repr(v)[:24])
@pytest.mark.parametrize("column", sorted(run_row()))
def test_any_value_in_a_run_column_gives_a_page(db, monkeypatch, column, value):
    db.parent.mkdir()
    fake_readers(monkeypatch, [run_row(**{column: value})], [step_row()])
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0 and len(text) < 100_000
    row = dom.cells("runs")[0]
    if column == "status":
        assert row[0] == UNKNOWN
    if column in RUN_COLUMN_CELL and not (column == "facts" and type(value) is dict):
        assert row[RUN_COLUMN_CELL[column]].startswith(UNKNOWN), row
    if column in ("status", "reason_code", "facts") and type(value) is not dict:
        assert row[0] != "정상"
    if column == "started_at":
        assert UNKNOWN in dom.by_id("last-age").text()
        assert "data-since" not in dom.by_id("last-age").attrs
    if column == "run_id":
        assert UNKNOWN in dom.by_id("steps").find_all("p")[0].text()


@pytest.mark.parametrize("value", ODD_VALUES, ids=lambda v: repr(v)[:24])
@pytest.mark.parametrize("column", sorted(step_row()))
def test_any_value_in_a_step_column_gives_a_page(db, monkeypatch, column, value):
    db.parent.mkdir()
    fake_readers(monkeypatch, [run_row()], [step_row(**{column: value})])
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0 and len(text) < 100_000
    row = dom.cells("steps")[0]
    if column in ("kind", "state"):
        assert row[0] == UNKNOWN
    if column == "outcome":
        assert row[0] == UNKNOWN and row[3].startswith(UNKNOWN)
    if column in STEP_COLUMN_CELL and not (column == "facts" and type(value) is dict):
        assert row[STEP_COLUMN_CELL[column]].startswith(UNKNOWN), row
    if column in ("kind", "state", "outcome", "reason_code", "severity", "facts"):
        if not (column == "facts" and type(value) is dict):
            assert row[0] != "정상"
    if column == "target" and type(value) is not str:
        assert row[2] == UNKNOWN


@pytest.mark.parametrize(
    "value, shown",
    [(True, "dry-run"), (False, "-"), (1, UNKNOWN), (0, UNKNOWN), (None, UNKNOWN)],
)
def test_dry_run_is_a_flag_and_not_a_number(db, monkeypatch, value, shown):
    """What is checked is what read_runs() returned (it turns the stored value
    into a bool: what was in the file cannot be seen from here)."""
    db.parent.mkdir()
    fake_readers(monkeypatch, [run_row(dry_run=value)], [])
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0 and dom.cells("runs")[0][5] == shown


def test_a_missing_time_and_a_missing_duration_are_shown_as_absent(db, monkeypatch):
    db.parent.mkdir()
    run = run_row(started_at=None, duration_ms=None)
    fake_readers(monkeypatch, [run], [step_row(duration_ms=None)])
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert dom.cells("runs")[0][2:5] == ["-", "-", "-"]
    assert dom.cells("steps")[0][4:7] == ["-", "-", "-"]
    box = dom.by_id("last-age")
    assert UNKNOWN in box.text() and "data-since" not in box.attrs


@pytest.mark.parametrize(
    "facts, shown",
    [
        ({}, "-"),
        ({"valuations_total": 3}, "3건"),
        ({"valuations_total": 0, "valuations_by_status": {}}, "0건"),
        (
            {
                "valuations_total": 3,
                "valuations_by_status": {"success": 2, "failed": 1},
            },
            "3건 (failed 1, success 2)",
        ),
        (
            {
                "valuations_total": 2,
                "valuations_by_status": {"<invalid>": 1, "success": None},
            },
            "2건 (<invalid> 1, success ?)",
        ),
        ({"valuations_total": -1}, UNKNOWN),
        ({"valuations_total": True}, UNKNOWN),
        ({"valuations_total": "3"}, UNKNOWN),
        ({"valuations_total": 3, "valuations_by_status": []}, UNKNOWN),
        ({"valuations_total": 3, "valuations_by_status": {"other": 3}}, UNKNOWN),
        ({"valuations_total": 3, "valuations_by_status": {"success": "3"}}, UNKNOWN),
        ({"valuations_by_status": {"success": 3}}, UNKNOWN),
    ],
    ids=str,
)
def test_the_valuation_count_cell(db, monkeypatch, facts, shown):
    db.parent.mkdir()
    fake_readers(monkeypatch, [run_row(facts=facts)], [])
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert dom.cells("runs")[0][6] == shown


def test_what_is_shown_of_the_facts_of_a_step(db, monkeypatch):
    db.parent.mkdir()
    steps = [
        step_row(
            facts={
                "ticker": "005930",
                "market": "KR",
                "stage": "valuation",
                "error_type": "ValueError",
                "degraded": ["peers", "<invalid>", "bad one"],
            }
        ),
        step_row(
            kind="discovery",
            target="KR",
            outcome="ok",
            facts={"news_count": 40, "discovered": 8, "path": "news_llm"},
        ),
        step_row(
            kind="delivery",
            target="excel_upload",
            outcome="ok",
            facts={"eligible": 3, "uploaded": 2, "error_type": None},
        ),
        step_row(
            facts={"ticker": "TOO-LONG-TICKER-X", "market": 5, "zzz": 1, "yyy": 2}
        ),
        step_row(facts={"news_count": -4, "eligible": "3"}),
        # an empty list says "nothing degraded" and nothing else
        step_row(facts={"ticker": [], "market": {}, "uploaded": [], "degraded": []}),
    ]
    fake_readers(monkeypatch, [run_row()], steps)
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    notes = [row[6] for row in dom.cells("steps")]
    assert notes[0] == (
        "티커 005930 · 시장 KR · 멈춘 곳 valuation · 예외 종류 ValueError"
        f" · 품질 저하 peers, <invalid>, {UNKNOWN}"
    )
    assert notes[1] == "뉴스 40 · 후보 8 · 경로 news_llm"
    assert notes[2] == "대상 3 · 올림 2"
    assert notes[3] == f"티커 {UNKNOWN} · 시장 {UNKNOWN} · 외 2개 항목"
    assert notes[4] == f"뉴스 {UNKNOWN} · 대상 {UNKNOWN}"
    assert notes[5] == f"티커 {UNKNOWN} · 시장 {UNKNOWN} · 올림 {UNKNOWN}"
    kinds = [row[0] for row in dom.cells("steps")]
    assert kinds[0] == "주의" and kinds[5] == "정상"  # only a degraded item is attached


def test_only_the_first_steps_are_listed_and_all_are_counted(db, monkeypatch):
    db.parent.mkdir()
    total = mon.STEP_LIMIT + 7
    steps = [step_row(step_id=n, target=f"Co {n}") for n in range(total)]
    steps[-1] = step_row(step_id=total, target="Last Co", outcome="failed")
    fake_readers(monkeypatch, [run_row()], steps)
    code, dom, text = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert len(dom.rows("steps")) == mon.STEP_LIMIT == 200
    assert "Last Co" not in text
    assert dom.by_id("step-counts").text() == (
        f"단계 {total}개: 정상 {total - 1}, 주의 0, 막힘 1, 미확정 0, 알 수 없음 0"
    )
    assert (
        "7개" in dom.by_id("steps").text()
        and "표시하지 않" in dom.by_id("steps").text()
    )


def test_at_most_twenty_runs_are_asked_for_and_two_reads_are_made(db, monkeypatch):
    db.parent.mkdir()
    calls = fake_readers(monkeypatch, [run_row()], [step_row()])
    assert mon.build(db, db.parent / "monitor.html", now=lambda: AFTER_THE_WEEK) == 0
    assert calls == [("read_runs", 20), ("read_run", "wr-20261114T000000Z-0123abcd")]
    assert mon.RUN_LIMIT == 20


def test_twenty_five_runs_in_the_file_show_the_newest_twenty(db):
    clock = Clock()
    ids = []
    for _ in range(25):
        ids.append(full_week(db, clock, names=("Solo Co",)))
        clock.tick(7 * 86400)
    code, dom, text = render(db, clock.now())
    assert code == 0
    assert len(dom.rows("runs")) == 20
    assert ids[-1] in dom.by_id("steps").text()
    assert dom.cells("runs")[0][2] > dom.cells("runs")[19][2]  # newest first


def test_the_newest_run_is_shown_as_the_second_read_saw_it(db, monkeypatch):
    """The two reads are not one snapshot: the later one wins for the first row."""
    db.parent.mkdir()
    earlier = run_row(status="RUNNING", ended_at=None, duration_ms=None, facts={})
    older = run_row(run_id="wr-20261107T000000Z-89abcdef", status="FAILED")
    later = run_row(status="COMPLETED")
    fake_readers(
        monkeypatch, [earlier, older], detail={"run": later, "steps": [step_row()]}
    )
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert [row[0] for row in dom.cells("runs")] == ["정상", "막힘"]
    assert dom.by_id("last-status").text().startswith("정상")


# ── 8. time, as Python decides it at build time ──────────────────────────────

START = datetime(2026, 11, 14, 0, 0, 0, tzinfo=UTC)


def timed_parts(box: Node) -> dict:
    return {
        name: box.with_class(name)[0] for name in ("static", "under", "over", "skew")
    }


def assert_timed_box(box: Node, since: datetime, limit: int) -> dict:
    assert box.attrs["data-since"] == utc_stamp(since)
    assert box.attrs["data-limit-s"] == str(limit)
    parts = timed_parts(box)
    assert "hidden" not in parts["static"].attrs
    for name in ("under", "over", "skew"):
        assert "hidden" in parts[name].attrs
        assert parts[name].raw_text().strip()
    return parts


@pytest.mark.parametrize(
    "after, flagged, words",
    [
        (timedelta(0), False, "0초"),
        (timedelta(hours=6), False, "6시간 0분"),
        (timedelta(days=8), False, "8일 0시간"),  # exactly the limit is not over it
        (timedelta(days=8, milliseconds=1), True, "8일 0시간"),
        (timedelta(days=8, seconds=1), True, "8일 0시간"),
        (timedelta(days=30, hours=5), True, "30일 5시간"),
    ],
)
def test_no_run_for_more_than_eight_days(db, after, flagged, words):
    full_week(db, Clock(START))
    code, dom, _ = render(db, START + after)
    assert code == 0
    box = dom.by_id("last-age")
    parts = assert_timed_box(box, START, mon.NO_RUN_AFTER_S)
    seen = box.text()
    assert ("무실행 의심" in seen) == flagged
    assert f"마지막 실행 시작 후 {words}" in seen
    assert "화면을 만든 시각 기준" in seen
    assert "무실행 의심" in parts["over"].raw_text()
    assert "무실행 의심" not in parts["under"].raw_text()
    assert mon.NO_RUN_AFTER_S == 8 * 86400


def test_a_last_run_that_starts_in_the_future_is_a_clock_mismatch(db):
    full_week(db, Clock(START))
    code, dom, _ = render(db, START - timedelta(seconds=1))
    assert code == 0
    box = dom.by_id("last-age")
    assert_timed_box(box, START, mon.NO_RUN_AFTER_S)
    seen = box.text()
    assert "시계 불일치" in seen
    assert "무실행 의심" not in seen and "시작 후" not in seen  # no elapsed time
    assert not re.search(r"\d+(초|분|시간|일)", seen)


@pytest.mark.parametrize(
    "stored",
    [
        "2026-11-14 00:00:00",
        "2026-11-14T00:00:00+00:00",
        "2026-11-14T00:00:00.000Z",
        "2026-11-14T09:00:00.000+09:00",
        "2026-13-14T00:00:00.000+00:00",
        "2026-11-14T25:00:00.000+00:00",
        "2026-11-14T00:00:00.000+00:00 ",
        "not-a-time",
        "",
        "9999-12-31T23:59:59.999+00:00",  # parses, but KST cannot express it
        "9999-12-31T15:00:00.000+00:00",
        "２０２６-11-14T00:00:00.000+00:00",  # full-width digits
    ],
)
def test_a_start_time_that_cannot_be_read_is_unknown_not_fresh(db, stored):
    full_week(db, Clock(START))
    plant(db, "UPDATE runs SET started_at = ?", (stored,))
    code, dom, text = render(db, START + timedelta(days=30))
    assert code == 0
    box = dom.by_id("last-age")
    assert "data-since" not in box.attrs and "data-limit-s" not in box.attrs
    assert UNKNOWN in box.text() and "무실행 의심" not in box.text()
    assert dom.cells("runs")[0][2] == UNKNOWN
    if stored.strip():
        assert stored.strip() not in text


@pytest.mark.parametrize(
    "stored, kst, since, words",
    [
        (
            "9999-12-31T14:59:59.999+00:00",
            "9999-12-31 23:59:59 KST",
            "9999-12-31T14:59:59.999Z",
            "시계 불일치",
        ),
        (
            "0001-01-01T00:00:00.000+00:00",
            "0001-01-01 09:00:00 KST",
            "0001-01-01T00:00:00.000Z",
            "무실행 의심",
        ),
    ],
)
def test_the_first_and_the_last_time_that_can_be_shown(db, stored, kst, since, words):
    full_week(db, Clock(START))
    plant(db, "UPDATE runs SET started_at = ?", (stored,))
    code, dom, _ = render(db, START)
    assert code == 0
    assert dom.cells("runs")[0][2] == kst
    box = dom.by_id("last-age")
    assert box.attrs["data-since"] == since and words in box.text()


def running_database(db, opened, clock):
    writer = opened(db, clock)
    rec = writer.start_run(markets=["KR"], max_per_market=1, dry_run=False)
    step = rec.start("valuation", "Still Going Co", ticker="STIL", market="US")
    assert step is not None
    return writer, rec


@pytest.mark.parametrize(
    "after, words",
    [
        (timedelta(minutes=35), "실행 중일 수 있음"),
        (timedelta(hours=2), "실행 중일 수 있음"),  # exactly the limit
        (timedelta(hours=2, seconds=1), "중단 의심"),
        (timedelta(days=3), "중단 의심"),
        (timedelta(seconds=-5), "시계 불일치"),
    ],
)
def test_a_run_without_an_end(db, opened, after, words):
    clock = Clock(START)
    running_database(db, opened, clock)
    code, dom, _ = render(db, START + after)
    assert code == 0
    kind, status = dom.cells("runs")[0][:2]
    assert kind == "미확정"
    everything = ("실행 중일 수 있음", "중단 의심", "시계 불일치")
    assert [w for w in everything if w in status] == [words]
    assert "RUNNING" in status
    box = dom.rows("runs")[0][1].with_class("timed")[0]
    parts = assert_timed_box(box, START, mon.RUNNING_SUSPECT_AFTER_S)
    assert "실행 중일 수 있음" in parts["under"].raw_text()
    assert "중단 의심" in parts["over"].raw_text()
    assert "시계 불일치" in parts["skew"].raw_text()
    last = dom.by_id("last-status").text()
    assert last.startswith("미확정") and words in last
    step = dom.cells("steps")[0]
    assert step[0] == "미확정" and "끝나지 않음" in step[3]
    assert dom.by_id("step-counts").text() == (
        "단계 1개: 정상 0, 주의 0, 막힘 0, 미확정 1, 알 수 없음 0"
    )
    assert mon.RUNNING_SUSPECT_AFTER_S == 7200


def test_a_running_run_whose_start_cannot_be_read(db, monkeypatch):
    db.parent.mkdir()
    run = run_row(status="RUNNING", started_at="garbage", ended_at=None, facts={})
    fake_readers(monkeypatch, [run], [])
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    kind, status = dom.cells("runs")[0][:2]
    assert kind == "미확정" and "시작 시각 알 수 없음" in status
    assert dom.rows("runs")[0][1].with_class("timed") == []


def test_the_page_carries_its_own_build_time_and_a_default_that_admits_nothing(db):
    full_week(db, Clock(START))
    built = datetime(2026, 11, 21, 7, 30, 15, 123456, tzinfo=UTC)
    code, dom, _ = render(db, built)
    assert code == 0
    assert dom.by_id("built").text() == "2026-11-21 16:30:15 KST"
    box = dom.by_id("freshness")
    parts = assert_timed_box(box, built, mon.STALE_AFTER_S)
    assert box.attrs["data-since"] == "2026-11-21T07:30:15.123Z"
    default = box.text()
    assert "동작하지 않" in default and "2026-11-21 16:30:15 KST" in default
    assert "오래된 화면" not in default  # Python cannot know: only the script says so
    assert "오래된 화면" in parts["over"].raw_text()
    assert "시계 불일치" in parts["skew"].raw_text()
    assert mon.STALE_AFTER_S == 86400


def test_the_build_time_is_given_in_another_zone(db):
    full_week(db, Clock(START))
    kst = timezone(timedelta(hours=9))
    code, dom, _ = render(db, datetime(2026, 11, 21, 16, 30, 15, tzinfo=kst))
    assert code == 0
    assert dom.by_id("built").text() == "2026-11-21 16:30:15 KST"
    assert dom.by_id("freshness").attrs["data-since"] == "2026-11-21T07:30:15.000Z"


def test_a_clock_without_a_time_zone_is_refused_and_nothing_is_written(db):
    full_week(db, Clock(START))
    out = db.parent / "monitor.html"
    with pytest.raises(ValueError):
        mon.build(db, out, now=lambda: datetime(2026, 11, 21, 7, 0, 0))
    assert not out.exists()


def test_the_page_reloads_itself_every_sixty_seconds(db):
    full_week(db, Clock(START))
    _, dom, _ = render(db, AFTER_THE_WEEK)
    metas = [node.attrs for node in dom.root.find_all("meta")]
    assert metas[0] == {"charset": "utf-8"}
    assert {"http-equiv": "refresh", "content": "60"} in metas
    assert mon.RELOAD_S == 60


# ── 9. what every page says ──────────────────────────────────────────────────


def test_every_page_says_that_nobody_is_alerted(db, opened, monkeypatch):
    pages = []
    db.parent.mkdir()
    pages.append(render(db, AFTER_THE_WEEK))  # no database
    rs.open_writer(db).close()
    pages.append(render(db, AFTER_THE_WEEK))  # no run
    full_week(db, Clock())
    pages.append(render(db, AFTER_THE_WEEK))  # a clean week
    assert [code for code, _, _ in pages] == [2, 0, 0]
    for _, dom, _ in pages:
        alert = dom.by_id("no-alert").text()
        assert "무실행 자동 알림" in alert and "미지원" in alert
        notes = dom.by_id("notes").text()
        assert "시작이 거절된 실행" in notes and "여기 나오지 않는다" in notes
        assert "dry-run도 실행으로 센다" in notes
        assert "알 수 없음은 정상으로 세지 않는다" in notes
        header = dom.root.find_all("header")[0].text()
        assert "python -m tools.monitor.build" in header
        assert "스크립트가 멈추면 마지막 표시가 그대로 남는다" in header
        assert dom.by_id("ticked").text() == "스크립트 미실행"


# ── 10. no run yet ───────────────────────────────────────────────────────────


def test_a_database_without_runs(db):
    rs.open_writer(db).close()
    code, dom, _ = render(db, AFTER_THE_WEEK)
    assert code == 0
    assert "읽음" in dom.by_id("state").text()
    assert dom.rows("runs") == [] and dom.rows("steps") == []
    assert "기록된 실행이 없다" in dom.by_id("runs").text()
    assert "기록된 실행이 없다" in dom.by_id("last-status").text()
    box = dom.by_id("last-age")
    assert UNKNOWN in box.text() and "data-since" not in box.attrs
    assert tags_shown(dom) == ["읽음"]  # read, and no verdict about any run


# ── 11. the page is replaced atomically ──────────────────────────────────────


@pytest.fixture
def previous_page(db):
    full_week(db, Clock())
    out = db.parent / "monitor.html"
    out.write_bytes(b"<!doctype html><title>the previous page</title>")
    return out


def folder_names(folder: Path) -> list:
    """What is in the folder besides the run state: the database, its side
    files and lock, and the folders of exported events."""
    return sorted(
        p.name
        for p in folder.iterdir()
        if "state.db" not in p.name and not p.name.startswith("wr-")
    )


def test_a_replace_that_is_always_refused_leaves_the_previous_page(
    db, previous_page, monkeypatch, caplog
):
    before = folder_names(db.parent)
    attempts, pauses = [], []

    def refuse(source, target):
        attempts.append((Path(source).name, Path(target).name))
        raise PermissionError(13, "held open by a browser", str(target))

    monkeypatch.setattr(os, "replace", refuse)
    monkeypatch.setattr(time, "sleep", pauses.append)
    with caplog.at_level(logging.DEBUG):
        code = mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)

    assert code == 1
    assert (
        previous_page.read_bytes() == b"<!doctype html><title>the previous page</title>"
    )
    assert folder_names(db.parent) == before  # no temporary file is left
    assert len(attempts) == mon.REPLACE_ATTEMPTS == 5
    assert pauses == [mon.REPLACE_WAIT_S] * 4 == [0.2] * 4
    assert {target for _, target in attempts} == {"monitor.html"}
    assert all(
        name.startswith("monitor.html.") and name.endswith(".tmp")
        for name, _ in attempts
    )
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "PermissionError" in logged
    assert "held open" not in logged and str(db.parent) not in logged


def test_a_replace_that_is_refused_twice_and_then_works(db, previous_page, monkeypatch):
    real, attempts, pauses = os.replace, [], []

    def refuse_twice(source, target):
        attempts.append(1)
        if len(attempts) <= 2:
            raise PermissionError(13, "held open")
        return real(source, target)

    monkeypatch.setattr(os, "replace", refuse_twice)
    monkeypatch.setattr(time, "sleep", pauses.append)
    code = mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)
    assert code == 0 and len(attempts) == 3 and pauses == [0.2, 0.2]
    assert WEEK_NAMES[0] in previous_page.read_text(encoding="utf-8")
    assert folder_names(db.parent) == ["monitor.html"]


@pytest.mark.parametrize(
    "error", [OSError(28, "disk full"), FileNotFoundError(2, "gone")]
)
def test_another_error_from_replace_is_not_retried(
    db, previous_page, monkeypatch, error
):
    attempts, pauses = [], []

    def fail(source, target):
        attempts.append(1)
        raise error

    monkeypatch.setattr(os, "replace", fail)
    monkeypatch.setattr(time, "sleep", pauses.append)
    code = mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)
    assert code == 1 and len(attempts) == 1 and pauses == []
    assert previous_page.read_bytes().endswith(b"the previous page</title>")
    assert folder_names(db.parent) == ["monitor.html"]


@pytest.mark.parametrize("broken", ["fsync", "write", "mkstemp"])
def test_a_failure_while_writing_leaves_the_previous_page(
    db, previous_page, monkeypatch, broken
):
    def fail(*args, **kwargs):
        raise OSError(28, "No space left on device")

    if broken == "fsync":
        monkeypatch.setattr(os, "fsync", fail)
    elif broken == "write":
        monkeypatch.setattr(os, "write", fail)
        monkeypatch.setattr(os, "fdopen", fail)
    else:
        monkeypatch.setattr(mon.tempfile, "mkstemp", fail)
    replaced = []
    real = os.replace
    monkeypatch.setattr(os, "replace", lambda *a: (replaced.append(a), real(*a)))
    code = mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)
    assert code == 1 and replaced == []
    assert previous_page.read_bytes().endswith(b"the previous page</title>")
    assert folder_names(db.parent) == ["monitor.html"]


def test_a_stop_request_while_writing_leaves_no_temporary_file(
    db, previous_page, monkeypatch
):
    def stop(*args):
        raise KeyboardInterrupt()

    monkeypatch.setattr(os, "replace", stop)
    with pytest.raises(KeyboardInterrupt):
        mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)
    assert previous_page.read_bytes().endswith(b"the previous page</title>")
    assert folder_names(db.parent) == ["monitor.html"]


@pytest.mark.skipif(
    os.name != "nt", reason="an open handle blocks a replace on Windows only"
)
def test_a_page_held_open_on_windows(db, previous_page, monkeypatch):
    pauses = []
    monkeypatch.setattr(time, "sleep", pauses.append)
    with open(previous_page, "rb"):
        code = mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK)
        assert code == 1 and pauses == [0.2] * 4
        assert folder_names(db.parent) == ["monitor.html"]
    assert previous_page.read_bytes().endswith(b"the previous page</title>")
    assert mon.build(db, previous_page, now=lambda: AFTER_THE_WEEK) == 0
    assert WEEK_NAMES[0] in previous_page.read_text(encoding="utf-8")


def test_the_page_is_utf8_without_a_mark_and_with_plain_newlines(db):
    full_week(db, Clock())
    out = db.parent / "monitor.html"
    assert mon.build(db, out, now=lambda: AFTER_THE_WEEK) == 0
    data = out.read_bytes()
    assert data.startswith(b"<!doctype html>\n")
    assert b"\r" not in data and not data.startswith(b"\xef\xbb\xbf")
    assert "삼성전자" in data.decode("utf-8")
    assert data.endswith(b"</html>\n")


# ── 12. the output folder ────────────────────────────────────────────────────


def test_a_missing_output_folder_is_made_and_the_database_is_not(tmp_path):
    db = tmp_path / "runs" / "state.db"
    code = mon.build(db, now=lambda: AFTER_THE_WEEK)  # the page goes next to it
    assert code == 2
    assert sorted(p.name for p in tmp_path.iterdir()) == ["runs"]
    assert sorted(p.name for p in db.parent.iterdir()) == ["monitor.html"]
    dom = Dom((db.parent / "monitor.html").read_text(encoding="utf-8"))
    assert dom.by_id("state-code").text() == "DB_UNAVAILABLE"


def test_only_the_last_folder_is_made(tmp_path, db):
    full_week(db, Clock())
    out = tmp_path / "missing" / "deeper" / "monitor.html"
    assert mon.build(db, out, now=lambda: AFTER_THE_WEEK) == 1
    assert not (tmp_path / "missing").exists()


def test_an_output_folder_that_is_a_file(tmp_path, db):
    full_week(db, Clock())
    (tmp_path / "taken").write_bytes(b"a file")
    assert (
        mon.build(db, tmp_path / "taken" / "monitor.html", now=lambda: AFTER_THE_WEEK)
        == 1
    )
    assert (tmp_path / "taken").read_bytes() == b"a file"


# ── 13 and 14. the database and its writer are left alone ────────────────────


def test_the_page_is_never_written_over_the_database(db, tmp_path):
    full_week(db, Clock())
    before = digest(db)
    same_file = (
        db,
        str(db),
        db.parent / "." / "state.db",
        db.parent / ".." / "runs" / "state.db",
    )
    for out in same_file:
        with pytest.raises(ValueError):
            mon.build(db, out, now=lambda: AFTER_THE_WEEK)
    with pytest.raises(ValueError):  # a database that happens to have the page's name
        mon.build(tmp_path / "monitor.html", now=lambda: AFTER_THE_WEEK)
    assert digest(db) == before and list(tmp_path.glob("*.html")) == []
    assert rs.read_runs(db)[0]["status"] == "COMPLETED"


def test_building_changes_nothing_that_belongs_to_the_run_state(db):
    run_id = full_week(db, Clock())
    events = db.parent / run_id / "events.jsonl"
    assert events.is_file()
    before = {
        p.relative_to(db.parent).as_posix(): digest(p)
        for p in db.parent.rglob("*")
        if p.is_file()
    }
    for _ in range(3):
        assert mon.build(db, now=lambda: AFTER_THE_WEEK) == 0
    after = {
        p.relative_to(db.parent).as_posix(): digest(p)
        for p in db.parent.rglob("*")
        if p.is_file()
    }
    assert {name: after[name] for name in before} == before
    assert set(after) - set(before) <= {"monitor.html", "state.db-shm", "state.db-wal"}
    assert "monitor.html" in after


def test_a_writer_keeps_recording_while_and_after_pages_are_built(db, opened):
    clock = Clock(START)
    writer, rec = running_database(db, opened, clock)
    lock = db.with_name(db.name + ".writer.lock")
    assert lock.is_file()

    code, dom, _ = render(db, START + timedelta(minutes=5))
    assert code == 0 and dom.cells("runs")[0][0] == "미확정"
    with pytest.raises(rs.RunStateUnavailable) as busy:  # the seat is still taken
        rs.open_writer(db)
    assert busy.value.reason_code == "WRITER_BUSY"

    step = rec.start("valuation", "Second Co", ticker="SCND", market="US")
    assert step is not None
    assert mon.build(db, now=lambda: START + timedelta(minutes=6)) == 0
    rec.end(step, "success", degraded=[])
    rec.end_run("COMPLETED", errors=0, valuations_total=2)
    assert not rec.broken
    writer.close()

    stored = rs.read_run(db, rec.run_id)
    assert stored["run"]["status"] == "COMPLETED"
    assert [s["state"] for s in stored["steps"]] == ["INTERRUPTED", "ENDED"]
    code, dom, _ = render(db, START + timedelta(minutes=7))
    assert code == 0 and "완료" in dom.cells("runs")[0][1]
    rs.open_writer(db).close()  # and the seat was given back


# ── 15. default paths and the command ────────────────────────────────────────


def test_the_default_paths_are_the_run_state_database_and_the_page_next_to_it(
    repository_folders_are_never_touched,
):
    default_db = repository_folders_are_never_touched
    try:
        assert mon.build(now=lambda: AFTER_THE_WEEK) == 2  # there is no database
        assert sorted(p.name for p in default_db.parent.iterdir()) == ["monitor.html"]
    finally:
        shutil.rmtree(default_db.parent, ignore_errors=True)


def test_the_unpatched_default_is_the_repository_runs_folder():
    source = Path(rs.__file__).read_text(encoding="utf-8")
    assert (
        'DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "runs" / "state.db"'
        in source
    )
    assert mon.PAGE_NAME == "monitor.html"


def test_the_command_returns_the_exit_code_of_the_build(
    repository_folders_are_never_touched, monkeypatch
):
    default_db = repository_folders_are_never_touched
    monkeypatch.setattr(sys, "argv", ["build.py"])
    try:
        assert mon.main() == 2
        rs.open_writer(default_db).close()
        assert mon.main() == 0
        assert (default_db.parent / "monitor.html").is_file()
        monkeypatch.setattr(
            os, "replace", lambda *a: (_ for _ in ()).throw(OSError(5, "x"))
        )
        assert mon.main() == 1
    finally:
        shutil.rmtree(default_db.parent, ignore_errors=True)


def test_a_defect_is_raised_by_build_and_is_exit_one_without_a_traceback_in_main(
    repository_folders_are_never_touched, tmp_path, monkeypatch, capsys, caplog
):
    default_db = repository_folders_are_never_touched
    secret = f"k0g-defect-text {tmp_path}"

    def broken(*args, **kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(mon, "_page", broken)
    monkeypatch.setattr(sys, "argv", ["build.py"])
    with pytest.raises(RuntimeError):
        mon.build(now=lambda: AFTER_THE_WEEK)
    with caplog.at_level(logging.DEBUG):
        assert mon.main() == 1
    assert not default_db.parent.exists()  # nothing was written, not even a folder
    said = capsys.readouterr()
    logged = "\n".join(record.getMessage() for record in caplog.records)
    assert "BUILD_FAILED" in logged and "RuntimeError" in logged
    for place in (logged, said.out, said.err):
        assert "k0g-defect-text" not in place and "Traceback" not in place
        assert str(tmp_path) not in place and tmp_path.as_posix() not in place


CHILD_RUNS_THE_COMMAND_TWICE = """
import sys
from pathlib import Path
from scheduler import run_state
import tools.monitor.build as build

run_state.DEFAULT_DB_PATH = Path(sys.argv[1]) / "runs" / "state.db"
sys.argv = ["build.py"]
first = build.main()

def broken(*args, **kwargs):
    raise ZeroDivisionError("k0g-defect-text " + str(run_state.DEFAULT_DB_PATH))

build._page = broken
print(first, build.main())
"""


def test_the_command_in_a_process_of_its_own_shows_no_traceback(tmp_path):
    """The same through a real interpreter, where logging is not captured:
    what reaches stderr is one line with the code and the class name."""
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [sys.executable, "-c", CHILD_RUNS_THE_COMMAND_TWICE, str(tmp_path)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-800:]
    assert done.stdout.split() == ["2", "1"]  # no database, then the defect
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == ["monitor.html"]
    lines = [line for line in done.stderr.splitlines() if line.strip()]
    assert (
        len(lines) == 3
    )  # each run says the state was not read; the second then fails
    assert "DB_UNAVAILABLE" in lines[0] and "DB_UNAVAILABLE" in lines[1]
    assert "BUILD_FAILED" in lines[2] and "ZeroDivisionError" in lines[2]
    assert "Traceback" not in done.stderr and "k0g-defect-text" not in done.stderr
    assert str(tmp_path) not in done.stderr and "File " not in done.stderr


@pytest.mark.parametrize("extra", [["--help"], ["--db", "x"], ["anything"]])
def test_the_command_takes_no_arguments(
    repository_folders_are_never_touched, monkeypatch, capsys, extra
):
    monkeypatch.setattr(sys, "argv", ["build.py", *extra])
    assert mon.main() == 1
    assert not repository_folders_are_never_touched.parent.exists()
    assert "usage" in capsys.readouterr().err


# ── 16. what is never on the page ────────────────────────────────────────────


def test_no_path_no_environment_value_and_no_outside_resource(
    db, tmp_path, monkeypatch
):
    monkeypatch.setenv("K0G_SENTINEL_ENV", "k0g-env-sentinel-7f3a91")
    pages = []
    db.parent.mkdir()
    pages.append(render(db, AFTER_THE_WEEK))
    blocked_weeks(db, Clock())
    pages.append(render(db, AFTER_THE_WEEK + timedelta(days=8)))
    assert [code for code, _, _ in pages] == [2, 0]
    for _, dom, text in pages:
        assert "k0g-env-sentinel" not in text and "state.db" not in text
        for path in (tmp_path, db, db.parent, REPO_ROOT, Path.cwd(), Path.home()):
            for form in (str(path), path.as_posix(), str(path).replace("\\", "\\\\")):
                assert form not in text
        # Outside resources are a matter of structure, not of words: there is
        # no attribute that takes an address (render() checked the allow-list),
        # no attribute value holds one, and the style loads nothing.
        nodes = dom.nodes()
        names = {name for node in nodes for name in node.attrs}
        assert not {"href", "src", "action", "style", "srcset", "data"} & names
        assert not [name for name in names if name.startswith("on")]
        assert not [
            v for node in nodes for v in node.attrs.values() if v and "://" in v
        ]
        assert "url(" not in mon._STYLE and "@import" not in mon._STYLE
        metas = [node.attrs for node in nodes if node.tag == "meta"]
        assert [meta.get("http-equiv") for meta in metas] == [
            None,
            "Content-Security-Policy",
            "refresh",
        ]
        assert metas[0] == {"charset": "utf-8"}
        assert metas[2]["content"] == "60"  # a number of seconds and no address


# ── 17. the shape of the module ──────────────────────────────────────────────

SOURCE = Path(mon.__file__)
ALLOWED_IMPORTS = {
    "__future__",
    "base64",
    "datetime",
    "hashlib",
    "html",
    "logging",
    "os",
    "pathlib",
    "re",
    "sys",
    "tempfile",
    "time",
    "unicodedata",
    "scheduler",
}
ALLOWED_RUN_STATE_NAMES = {
    "read_runs",
    "read_run",
    "RunStateUnavailable",
    "DEFAULT_DB_PATH",
}


def module_tree() -> ast.Module:
    return ast.parse(SOURCE.read_text(encoding="utf-8"))


def test_the_module_imports_the_standard_library_and_run_state_only():
    imported, from_scheduler = set(), []
    for node in ast.walk(module_tree()):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            imported.add(node.module.split(".")[0])
            if node.module.split(".")[0] == "scheduler":
                from_scheduler.append((node.module, [a.name for a in node.names]))
    assert imported <= ALLOWED_IMPORTS
    assert "sqlite3" not in imported and "subprocess" not in imported
    assert from_scheduler == [("scheduler", ["run_state"])]
    assert imported <= set(sys.stdlib_module_names) | {"scheduler"}


def test_only_the_two_read_functions_of_run_state_are_used():
    used = {
        node.attr
        for node in ast.walk(module_tree())
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "run_state"
    }
    assert used == ALLOWED_RUN_STATE_NAMES
    names = {node.id for node in ast.walk(module_tree()) if isinstance(node, ast.Name)}
    assert "run_state" in names and "rs" not in names
    assert not {"open_writer", "read_events", "getattr", "eval", "exec"} & names
    text = SOURCE.read_text(encoding="utf-8")
    for word in (
        "SELECT ",
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "PRAGMA",
        "events.jsonl",
        "writer.lock",
    ):
        assert word not in text, word
    for call in (
        "innerHTML",
        "document.write",
        "eval(",
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
    ):
        assert call not in mon._SCRIPT, call


def test_markup_is_marked_safe_only_for_constants_and_inside_the_builders():
    """_Html(...) says "this is markup already". It may wrap a string constant,
    and it may be called inside _tag and _join, which escape what they are
    given. Anywhere else it would let a value through unescaped."""
    tree = module_tree()
    inside = {}
    for function in ast.walk(tree):
        if isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(function):
                inside.setdefault(id(node), function.name)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_Html"
    ]
    assert (
        len(calls) >= 4
    )  # the builders and the constants: the check has something to see
    for call in calls:
        constant = (
            len(call.args) == 1
            and not call.keywords
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
        )
        assert constant or inside.get(id(call)) in ("_tag", "_join"), ast.dump(call)[
            :200
        ]
    # and no other way of building markup from pieces
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            literal = "".join(
                part.value for part in node.values if isinstance(part, ast.Constant)
            )
            assert "<" not in literal and ">" not in literal, literal
    assert issubclass(mon._Html, str)


def test_importing_the_module_creates_nothing(tmp_path):
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT), PYTHONDONTWRITEBYTECODE="1")
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            "import tools.monitor.build as b, os; print(sorted(os.listdir('.')))",
        ],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.returncode == 0, done.stderr[-800:]
    assert done.stdout.strip() == "[]"
    assert list(tmp_path.iterdir()) == []


# ── 18. the content security policy ──────────────────────────────────────────


def test_the_policy_allows_exactly_the_script_and_the_style_of_the_page(db):
    full_week(db, Clock())
    _, dom, _ = render(db, AFTER_THE_WEEK)
    policies = [
        node.attrs["content"]
        for node in dom.root.find_all("meta")
        if node.attrs.get("http-equiv") == "Content-Security-Policy"
    ]
    assert len(policies) == 1
    parts = dict(part.strip().split(" ", 1) for part in policies[0].split(";"))

    def allowed(body: str) -> str:
        return (
            "'sha256-"
            + base64.b64encode(hashlib.sha256(body.encode("utf-8")).digest()).decode()
            + "'"
        )

    script = dom.root.find_all("script")[0].raw_text()
    style = dom.root.find_all("style")[0].raw_text()
    assert parts == {
        "default-src": "'none'",
        "script-src": allowed(script),
        "style-src": allowed(style),
        "base-uri": "'none'",
        "form-action": "'none'",
    }
    assert "\r" not in script and "\r" not in style
    assert "</" not in script and "</" not in style and "<!--" not in script
    head = [n.tag for n in dom.root.find_all("head")[0].children if isinstance(n, Node)]
    assert head[:2] == ["meta", "meta"] and "style" in head[2:] and "script" not in head
    second = [n for n in dom.root.find_all("head")[0].children if isinstance(n, Node)][
        1
    ]
    assert second.attrs["http-equiv"] == "Content-Security-Policy"  # before any style
