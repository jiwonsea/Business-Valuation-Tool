"""The minimal monitor: one static page built from the run-state database (K-0G).

``python -m tools.monitor.build`` reads ``runs/state.db`` through the read
functions of ``scheduler.run_state`` and writes ``runs/monitor.html``: the most
recent runs, the steps of the newest one, how long ago it started, and a plain
statement that nobody is alerted when no run happens.

Rules this module keeps:

* The page takes no part in a run. Only ``read_runs`` and ``read_run`` are
  called: no query is written here, no connection is held, and the writer
  lock and the files of the run state are not touched by this module.
* The default is "unknown". When the database cannot be read the page says so
  with a reason code and shows no run. A value outside the fixed lists is
  shown as unknown and is never counted as normal.
* No value becomes markup. Markup is a fixed constant or comes from ``_tag``
  and ``_join``, which escape every piece that is not markup already.
* The page says when it was built, and the page itself (its script, in the
  viewer's browser) says when that was too long ago. Python cannot do that:
  at build time the page is always new.
* The page is replaced whole or not at all.

Exit codes of the command: 0 written and read; 2 written, but the run state
could not be read (the page shows why); 1 not written (the previous page is
still there and ages on its own).

Standard library only; importing this module creates no file and no folder.
"""

from __future__ import annotations

import base64
import hashlib
import html
import logging
import os
import re
import sys
import tempfile
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scheduler import run_state

logger = logging.getLogger(__name__)

PAGE_NAME = "monitor.html"
RUN_LIMIT = 20  # runs listed
STEP_LIMIT = 200  # step rows listed; every step is counted
RELOAD_S = 60  # the browser reads the file again
STALE_AFTER_S = 24 * 3600  # "stale page": decided by the script only
NO_RUN_AFTER_S = 8 * 24 * 3600  # the weekly schedule plus one day
RUNNING_SUSPECT_AFTER_S = 2 * 3600  # the time limit of the scheduled task
REPLACE_ATTEMPTS = 5
REPLACE_WAIT_S = 0.2

# Reason codes of this module (the others come from run_state).
READ_FAILED = "READ_FAILED"  # a read raised something else, or gave another shape
READ_INCONSISTENT = "READ_INCONSISTENT"  # the newest run was not found again
BUILD_FAILED = "BUILD_FAILED"  # a defect of this module, caught by the command

UNKNOWN = "알 수 없음"
ABSENT = "-"

# ── Markup: the only two builders ────────────────────────────────────────────

_TAGS = frozenset(
    "html head meta title style body header main section footer h1 h2 p table "
    "thead tbody tr th td span strong code ul li script".split()
)
_VOID = frozenset({"meta"})
_ATTRS = frozenset(
    "lang charset http-equiv content class id hidden scope data-since "
    "data-limit-s".split()
)


class _Html(str):
    """Markup that is already safe. Anything else is escaped on its way in."""


def _join(*parts: str) -> _Html:
    """The parts in a row. A part that is not markup already is escaped."""
    for part in parts:
        if not isinstance(part, str):
            raise TypeError("only text and markup can be put on the page")
    return _Html(
        "".join(
            part if isinstance(part, _Html) else html.escape(part, quote=True)
            for part in parts
        )
    )


def _tag(name: str, *children: str, **attrs: object) -> _Html:
    """One element. Text children and attribute values are always escaped.

    ``class_`` is the attribute ``class`` and ``data_since`` is ``data-since``;
    ``hidden=True`` is the bare attribute.
    """
    if name not in _TAGS:
        raise ValueError("not a tag of this page")
    opening = [name]
    for key, value in attrs.items():
        attr = key.rstrip("_").replace("_", "-")
        if attr not in _ATTRS:
            raise ValueError("not an attribute of this page")
        if attr == "hidden":
            if type(value) is not bool:
                raise TypeError("hidden is True or False")
            if value:
                opening.append("hidden")
            continue
        if type(value) is not str:  # markup is not an attribute value either
            raise TypeError("an attribute value is plain text")
        opening.append(attr + '="' + html.escape(value, quote=True) + '"')
    if name in _VOID:
        if children:
            raise ValueError("a void element has no content")
        return _Html("<" + " ".join(opening) + ">")
    return _Html("<" + " ".join(opening) + ">" + _join(*children) + "</" + name + ">")


_DOCTYPE = _Html("<!doctype html>\n")
_ELAPSED = _Html('<span class="elapsed"></span>')  # the script writes the age here
_BREAK = _Html("\n")

_STYLE = _Html("""
body{font-family:system-ui,"Malgun Gothic",sans-serif;margin:1.5rem;color:#1a1a1a;background:#fff;line-height:1.5}
h1{font-size:1.4rem;margin:0 0 .5rem}
h2{font-size:1.1rem;margin:1.6rem 0 .5rem;border-bottom:1px solid #bbb}
p{margin:.3rem 0}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #bbb;padding:.3rem .5rem;text-align:left;vertical-align:top;font-size:.9rem}
th{background:#f0f0f0}
code{font-family:Consolas,monospace;font-size:.85em}
.note{color:#555;font-size:.85rem}
.tag{display:inline-block;padding:0 .4rem;border:1px solid;border-radius:.2rem;font-weight:bold;white-space:nowrap}
.ok{color:#0b5d1e;background:#e3f4e6}
.warn{color:#7a4b00;background:#fff1cc}
.blocked{color:#8a1010;background:#fde0e0}
.open{color:#0b3d8a;background:#e0ebfd}
.unknown{color:#333;background:#e6e6e6}
#freshness .over,#freshness .skew,#last-age .over,#last-age .skew{display:block;padding:.4rem .6rem;border:2px solid #8a1010;background:#fde0e0}
[hidden]{display:none!important}
""")

# What the script does, and nothing else: for every element with data-since it
# works out the age on the viewer's clock, shows one of .static/.under/.over/
# .skew, writes the age into .elapsed with textContent, and notes the time of
# the last pass. A box it cannot work out goes back to .static.
_SCRIPT = _Html("""
(function () {
  "use strict";
  var boxes = document.querySelectorAll("[data-since]");
  var ticked = document.getElementById("ticked");
  var states = ["static", "under", "over", "skew"];
  function two(n) { return (n < 10 ? "0" : "") + n; }
  function words(seconds) {
    var s = Math.floor(seconds);
    var d = Math.floor(s / 86400);
    var h = Math.floor(s % 86400 / 3600);
    var m = Math.floor(s % 3600 / 60);
    if (d > 0) { return d + "일 " + h + "시간"; }
    if (h > 0) { return h + "시간 " + m + "분"; }
    if (m > 0) { return m + "분 " + (s % 60) + "초"; }
    return s + "초";
  }
  function paint(box, state, text) {
    var i, found;
    for (i = 0; i < states.length; i += 1) {
      found = box.getElementsByClassName(states[i]);
      if (found.length) { found[0].hidden = states[i] !== state; }
    }
    found = box.getElementsByClassName("elapsed");
    for (i = 0; i < found.length; i += 1) { found[i].textContent = text; }
  }
  function update(box, now) {
    var since = Date.parse(box.getAttribute("data-since"));
    var limit = Number(box.getAttribute("data-limit-s"));
    var age = (now - since) / 1000;
    if (!isFinite(age) || !isFinite(limit) || limit <= 0) {
      paint(box, "static", "");
    } else if (age < 0) {
      paint(box, "skew", "");
    } else {
      paint(box, age > limit ? "over" : "under", words(age));
    }
  }
  function tick() {
    var now = Date.now();
    var i, moment;
    for (i = 0; i < boxes.length; i += 1) {
      try {
        update(boxes[i], now);
      } catch (first) {
        try { paint(boxes[i], "static", ""); } catch (second) { /* nothing is left to try */ }
      }
    }
    if (ticked) {
      moment = new Date(now);
      ticked.textContent = two(moment.getHours()) + ":" + two(moment.getMinutes()) +
        ":" + two(moment.getSeconds());
    }
  }
  setInterval(tick, 1000);  // first: later passes come even if this one fails
  tick();
}());
""")


def _allowed(body: str) -> str:
    """The CSP source that allows exactly this inline body."""
    digest = hashlib.sha256(body.encode("utf-8")).digest()
    return "'sha256-" + base64.b64encode(digest).decode("ascii") + "'"


_POLICY = (
    "default-src 'none'; script-src "
    + _allowed(_SCRIPT)
    + "; style-src "
    + _allowed(_STYLE)
    + "; base-uri 'none'; form-action 'none'"
)

# ── Values: nothing read from the database is trusted ────────────────────────
# A value is shown as it is only when it has the shape its place allows. None
# of the shapes is long enough for a 32-character token.

_CODE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,30}")
_REASON = re.compile(r"[A-Z][A-Z0-9_]{0,30}")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,30}")  # class names, stages, paths
_MARKET = re.compile(r"[A-Za-z0-9_\-]{1,16}")
_TICKER = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,11}")
_RUN_ID = re.compile(r"wr-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}")
# [0-9], not \d: \d also takes digits of other scripts.
_STAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}\+00:00"
)
_MARKERS = ("<invalid>", "<masked>")  # written by run_state in place of a value
_COUNT_LIMIT = 10**9
_NAME_LIMIT = 120  # run_state stores no longer name
_LIST_LIMIT = 20
_NOT_SHOWN = frozenset({"Cc", "Cf", "Cs", "Zl", "Zp"})  # controls, formats, halves
_REPLACEMENT = chr(0xFFFD)
_KST = timezone(timedelta(hours=9))


def _code(value: object, shape: re.Pattern = _CODE) -> str:
    """A short value in its shape, or one of the writer's markers; else unknown."""
    if type(value) is str and (value in _MARKERS or shape.fullmatch(value)):
        return value
    return UNKNOWN


def _reason(value: object) -> str:
    return ABSENT if value is None else _code(value, _REASON)


def _is_count(value: object) -> bool:
    return type(value) is int and 0 <= value <= _COUNT_LIMIT  # bool is not a count


def _number(value: object) -> str:
    return str(value) if _is_count(value) else UNKNOWN


def _name(value: object) -> str:
    """A company name: its length is checked and what cannot be shown is replaced.

    What the name says is not examined here. That is the writer's rule
    (run_state keeps credential- and path-shaped names out); a copy of it
    would drift. A name that is too long is not cut: its head could be
    anything.
    """
    if type(value) is not str or not 0 < len(value) <= _NAME_LIMIT:
        return UNKNOWN
    return "".join(
        _REPLACEMENT if unicodedata.category(char) in _NOT_SHOWN else char
        for char in value
    )


def _moment(value: object) -> datetime | None:
    """A UTC time as run_state writes it, or None. Never raises.

    A time that cannot be given in KST (the last hours of the year 9999) is
    not a time the page can show, so it is not accepted at all.
    """
    if type(value) is not str or not _STAMP.fullmatch(value):
        return None
    try:
        moment = datetime.fromisoformat(value)
        moment.astimezone(_KST)
    except (ValueError, OverflowError):
        return None
    return moment


def _two(number: int) -> str:
    return str(number).zfill(2)


def _kst(moment: datetime) -> str:
    """'2026-11-21 16:00:00 KST'. Written out by hand: %Y differs by platform."""
    local = moment.astimezone(_KST)
    day = "-".join((str(local.year).zfill(4), _two(local.month), _two(local.day)))
    clock = ":".join((_two(local.hour), _two(local.minute), _two(local.second)))
    return day + " " + clock + " KST"


def _utc_stamp(moment: datetime) -> str:
    """'2026-11-21T07:00:00.000Z' for data-since: made here, never copied."""
    utc = moment.astimezone(timezone.utc)
    day = "-".join((str(utc.year).zfill(4), _two(utc.month), _two(utc.day)))
    clock = ":".join((_two(utc.hour), _two(utc.minute), _two(utc.second)))
    return day + "T" + clock + "." + str(utc.microsecond // 1000).zfill(3) + "Z"


def _when(value: object) -> str:
    if value is None:
        return ABSENT
    moment = _moment(value)
    return UNKNOWN if moment is None else _kst(moment)


def _span(seconds: float) -> str:
    """'3일 4시간', '5시간 6분', '7분 8초' or '9초' (the script says the same)."""
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}일 {hours}시간"
    if hours:
        return f"{hours}시간 {minutes}분"
    if minutes:
        return f"{minutes}분 {secs}초"
    return f"{secs}초"


def _duration(value: object) -> str:
    if value is None:
        return ABSENT
    return _span(value / 1000) if _is_count(value) else UNKNOWN


def _age(since: datetime | None, moment: datetime, limit_s: int) -> tuple[str, float]:
    """under / over / skew of one instant against a limit; unknown without it.

    "Over" is strictly more than the limit. An instant in the future is a
    clock mismatch: it is never reported as recent.
    """
    if since is None:
        return "unknown", 0.0
    seconds = (moment - since).total_seconds()
    if seconds < 0:
        return "skew", seconds
    return ("over" if seconds > limit_s else "under"), seconds


def _facts(row: dict) -> dict | None:
    facts = row.get("facts")
    return facts if type(facts) is dict else None


# ── Classification: five kinds, and "normal" only when nothing is attached ───

KIND_LABELS = {
    "ok": "정상",
    "warn": "주의",
    "blocked": "막힘",
    "open": "미확정",
    "unknown": UNKNOWN,
}
_RUNNING_LABELS = {
    "under": "실행 중일 수 있음",
    "over": "중단 의심(종료 기록 없음)",
    "skew": "시계 불일치",
    "unknown": "끝나지 않음(시작 시각 알 수 없음)",
}
_STEP_KINDS = {
    "discovery": "수집",
    "valuation": "평가",
    "artifact": "산출물",
    "delivery": "전달",
}
_STEP_TABLE = {
    "discovery": {
        "ok": ("ok", "수집됨"),
        "empty": ("warn", "결과 없음"),
        "failed": ("blocked", "실패"),
    },
    "valuation": {
        "success": ("ok", "성공"),
        "draft_blocked": ("blocked", "초안에서 막힘"),
        "no_result": ("blocked", "결과 없음"),
        "failed": ("blocked", "실패"),
    },
    "artifact": {
        "ok": ("ok", "저장됨"),
        "failed": ("blocked", "저장 실패"),
    },
    "delivery": {
        "ok": ("ok", "전달됨"),
        "partial": ("warn", "일부만 전달됨"),
        "no_result": ("warn", "전달 결과 없음"),
        "raised": ("blocked", "예외"),
    },
}
_NOT_ENDED = {
    "STARTED": ("open", "끝나지 않음"),
    "INTERRUPTED": ("blocked", "중단됨"),
    "UNKNOWN_DELIVERY": ("blocked", "전달 여부 불명"),
}
_TARGETS = {
    "summary_file": "요약 파일",
    "excel_upload": "엑셀 업로드",
    "email": "메일",
    "wordpress": "WordPress",
    "naver": "네이버 블로그",
}
_VALUATION_OUTCOMES = frozenset(_STEP_TABLE["valuation"])


def classify_run(run: dict, moment: datetime) -> tuple[str, str]:
    """(kind, label) of a run. Whatever is not listed is unknown."""
    status = run.get("status")
    if type(status) is not str:
        return "unknown", UNKNOWN
    if status == "COMPLETED":
        facts = _facts(run)
        clean = (
            run.get("reason_code") is None
            and facts is not None
            and (
                "errors" not in facts
                or (type(facts["errors"]) is int and facts["errors"] == 0)
            )
        )
        return ("ok", "완료") if clean else ("warn", "완료(확인 필요)")
    if status == "COMPLETED_WITH_ERRORS":
        return "warn", "완료(오류 있음)"
    if status == "FAILED":
        return "blocked", "실패"
    if status == "INTERRUPTED":
        return "blocked", "중단됨(종료 기록 없음)"
    if status == "RUNNING":
        started = _moment(run.get("started_at"))
        return "open", _RUNNING_LABELS[
            _age(started, moment, RUNNING_SUSPECT_AFTER_S)[0]
        ]
    return "unknown", UNKNOWN


def _clean_step(step: dict) -> bool:
    facts = _facts(step)
    if facts is None or step.get("reason_code") is not None:
        return False
    if step.get("severity") is not None:
        return False
    degraded = facts.get("degraded", [])
    return type(degraded) is list and not degraded


def classify_step(step: dict) -> tuple[str, str]:
    """(kind, label) of a step. Whatever is not listed is unknown."""
    state, kind, outcome = step.get("state"), step.get("kind"), step.get("outcome")
    if type(state) is not str:
        return "unknown", UNKNOWN
    if state in _NOT_ENDED:
        return _NOT_ENDED[state]
    if state != "ENDED" or type(kind) is not str or type(outcome) is not str:
        return "unknown", UNKNOWN
    found = _STEP_TABLE.get(kind, {}).get(outcome)
    if found is None:
        return "unknown", UNKNOWN
    if found[0] == "ok" and not _clean_step(step):
        return "warn", found[1]
    return found


# ── Reading: all or nothing ──────────────────────────────────────────────────


def _read(db_path: Path) -> tuple[list, list, str | None, str | None]:
    """(runs, steps of the newest run, reason code, exception class name).

    The two reads are not one snapshot, and neither is read_run() in itself.
    The newest run is taken from the second read so that the first row and
    the step table say the same thing. When anything fails nothing is
    returned but the reason: half a reading is not shown.
    """
    try:
        runs = run_state.read_runs(db_path, limit=RUN_LIMIT)
        if type(runs) is not list or not all(type(run) is dict for run in runs):
            return [], [], READ_FAILED, None
        if not runs:
            return [], [], None, None
        detail = run_state.read_run(db_path, runs[0].get("run_id"))
        if detail is None:
            return [], [], READ_INCONSISTENT, None
        if (
            type(detail) is not dict
            or type(detail.get("run")) is not dict
            or type(detail.get("steps")) is not list
            or not all(type(step) is dict for step in detail["steps"])
        ):
            return [], [], READ_FAILED, None
    except run_state.RunStateUnavailable as exc:
        return [], [], _code(exc.reason_code, _REASON), None
    except Exception as exc:  # the read functions check the header only
        return [], [], READ_FAILED, type(exc).__name__
    return [detail["run"], *runs[1:]], detail["steps"], None, None


# ── The page ─────────────────────────────────────────────────────────────────

_REASON_NOTES = {
    "DB_UNAVAILABLE": "상태 파일이 없거나 열 수 없다. 주간 실행이 한 번도 기록되지 않았으면 파일이 없다.",
    "DB_CORRUPT": "상태 파일이 손상됐다.",
    "DB_FOREIGN": "그 자리에 있는 파일이 실행 상태 파일이 아니다.",
    "SCHEMA_UNSUPPORTED": "상태 파일의 스키마 버전이 이 프로그램이 아는 것과 다르다.",
    "SQLITE_UNSUPPORTED": "이 Python의 SQLite가 너무 오래됐거나 단일 스레드용이다.",
    READ_FAILED: "읽는 도중 예외가 났거나 읽은 값의 모양이 약속과 다르다. "
    "파일이 손상됐거나 내용이 바뀌었을 수 있다.",
    READ_INCONSISTENT: "실행 목록에 있던 가장 최근 실행을 다시 읽었을 때 찾지 못했다.",
}
_NOT_READ = "읽지 못해 표시할 수 없다."
_NO_RUNS = "기록된 실행이 없다."


def _badge(kind: str) -> _Html:
    return _tag("span", KIND_LABELS[kind], class_="tag " + kind)


def _labelled(label: str, code: str) -> _Html:
    return _join(label, " ", _tag("code", code))


def _unlisted(value: object) -> str:
    """A value outside its list: unknown, with the value only in a code shape."""
    shown = _code(value)
    return UNKNOWN if shown == UNKNOWN else _labelled(UNKNOWN, shown)


def _timed(
    since: datetime,
    limit_s: int,
    static: str,
    under: str,
    over: str,
    skew: str,
    *,
    tag: str = "span",
    **attrs: object,
) -> _Html:
    """A box the script keeps up to date; ``static`` is what Python could say."""
    return _tag(
        tag,
        _tag("span", static, class_="static"),
        _tag("span", under, class_="under", hidden=True),
        _tag("span", over, class_="over", hidden=True),
        _tag("span", skew, class_="skew", hidden=True),
        class_="timed",
        data_since=_utc_stamp(since),
        data_limit_s=str(limit_s),
        **attrs,
    )


def _header(moment: datetime) -> _Html:
    built = _kst(moment)
    freshness = _timed(
        moment,
        STALE_AFTER_S,
        "오래됨 판정이 동작하지 않는다(스크립트가 실행되지 않았다). "
        "만든 시각을 직접 확인한다: " + built,
        _join(
            "만든 지 ",
            _ELAPSED,
            ". " + str(STALE_AFTER_S // 3600) + "시간이 넘으면 오래됐다고 표시한다.",
        ),
        _join(
            _tag("strong", "오래된 화면"),
            ": 만든 지 ",
            _ELAPSED,
            ". 아래 내용은 지금 상태가 아닐 수 있다. 화면을 다시 만들어야 한다.",
        ),
        _join(
            _tag("strong", "시계 불일치"),
            ": 화면을 만든 시각이 이 PC의 시계보다 미래다. 새것으로 치지 않는다.",
        ),
        tag="p",
        id="freshness",
    )
    return _tag(
        "header",
        _tag("h1", "BVT 주간 실행 모니터"),
        _tag("p", "화면을 만든 시각: ", _tag("span", built, id="built")),
        freshness,
        _tag(
            "p",
            "다시 계산한 시각(이 PC의 시계): ",
            _tag("span", "스크립트 미실행", id="ticked"),
            class_="note",
        ),
        _tag(
            "p",
            "이 화면은 ",
            _tag("code", "python -m tools.monitor.build"),
            "를 실행할 때만 새로 만들어진다. 열어 둔 화면은 "
            + str(RELOAD_S)
            + "초마다 파일을 다시 읽는다.",
            class_="note",
        ),
        _tag(
            "p",
            "경과 시간과 오래됨 표시는 이 화면의 스크립트가 계산한다. 스크립트가 멈추면 "
            "마지막 표시가 그대로 남는다. 의심스러우면 만든 시각을 직접 본다.",
            class_="note",
        ),
    )


def _state_section(failure: str | None, failure_class: str | None) -> _Html:
    heading = _tag("h2", "상태 파일")
    if failure is None:
        read = _tag("span", "읽음", class_="tag ok")
        return _tag(
            "section", heading, _tag("p", read, " 상태 파일을 읽었다."), id="state"
        )
    parts = [
        heading,
        _tag(
            "p",
            _badge("blocked"),
            " 상태 파일을 읽지 못했다. 사유 코드: ",
            _tag("code", failure, id="state-code"),
        ),
        _tag("p", _REASON_NOTES.get(failure, "이 화면이 모르는 사유 코드다.")),
    ]
    if type(failure_class) is str and _WORD.fullmatch(failure_class):
        parts.append(
            _tag("p", "예외 종류: ", _tag("code", failure_class, id="state-class"))
        )
    return _tag("section", *parts, id="state")


def _run_status(run: dict, moment: datetime, label: str) -> str:
    """The status cell: its label and code; a running run gets a timed box."""
    status = run.get("status")
    if label == UNKNOWN:
        return _unlisted(status)
    since = _moment(run.get("started_at")) if status == "RUNNING" else None
    if since is None:
        return _labelled(label, status)
    state, seconds = _age(since, moment, RUNNING_SUSPECT_AFTER_S)
    static = label
    if state != "skew":
        static += " (시작 후 " + _span(seconds) + ", 화면을 만든 시각 기준)"
    box = _timed(
        since,
        RUNNING_SUSPECT_AFTER_S,
        static,
        _join(_RUNNING_LABELS["under"], " (시작 후 ", _ELAPSED, ")"),
        _join(_RUNNING_LABELS["over"], " (시작 후 ", _ELAPSED, ")"),
        _RUNNING_LABELS["skew"] + ": 시작 시각이 이 PC의 시계보다 미래다",
    )
    return _labelled(box, status)


def _run_reason(run: dict) -> str:
    reason = _reason(run.get("reason_code"))
    facts = _facts(run)
    if facts is None or facts.get("error_type") is None:
        return reason
    return reason + " · 예외 종류 " + _code(facts["error_type"], _WORD)


def _dry_run(value: object) -> str:
    if value is True:
        return "dry-run"
    return ABSENT if value is False else UNKNOWN


def _valuations(run: dict) -> str:
    """'3건 (failed 1, success 2)' from the facts of a finished run."""
    facts = _facts(run)
    if facts is None:
        return UNKNOWN
    total, by_status = facts.get("valuations_total"), facts.get("valuations_by_status")
    if total is None and by_status is None:
        return ABSENT
    if not _is_count(total) or type(by_status) not in (dict, type(None)):
        return UNKNOWN
    parts = []
    for key in by_status or {}:
        number = by_status[key]
        listed = type(key) is str and (key in _VALUATION_OUTCOMES or key == _MARKERS[0])
        if not listed or not (number is None or _is_count(number)):
            return UNKNOWN
        parts.append(key + " " + ("?" if number is None else str(number)))
    counted = str(total) + "건"
    return counted + " (" + ", ".join(sorted(parts)) + ")" if parts else counted


def _row(*cells: str) -> _Html:
    return _join(_tag("tr", *[_tag("td", cell) for cell in cells]), _BREAK)


def _table(titles: tuple, rows: list) -> _Html:
    head = _tag("tr", *[_tag("th", title, scope="col") for title in titles])
    return _tag("table", _tag("thead", head), _BREAK, _tag("tbody", *rows))


def _last_run_section(runs: list, failure: str | None, moment: datetime) -> _Html:
    unknown_age = _tag("p", "마지막 실행 시작 후 경과: " + UNKNOWN, id="last-age")
    if failure is not None:
        status = _tag(
            "p",
            "가장 최근 실행: " + UNKNOWN + "(상태 파일을 읽지 못했다)",
            id="last-status",
        )
        age = unknown_age
    elif not runs:
        status, age = _tag("p", _NO_RUNS, id="last-status"), unknown_age
    else:
        run = runs[0]
        kind, label = classify_run(run, moment)
        status = _tag(
            "p",
            _badge(kind),
            " ",
            _run_status(run, moment, label),
            " · 시작 ",
            _when(run.get("started_at")),
            id="last-status",
        )
        age = _last_age(_moment(run.get("started_at")), moment) or unknown_age
    alert = _tag(
        "p",
        "무실행 자동 알림: ",
        _tag("strong", "미지원"),
        ". 이 화면을 연 사람만 본다.",
        id="no-alert",
    )
    return _tag(
        "section", _tag("h2", "마지막 실행 이후"), status, age, alert, id="last-run"
    )


def _last_age(since: datetime | None, moment: datetime) -> _Html | None:
    if since is None:
        return None
    state, seconds = _age(since, moment, NO_RUN_AFTER_S)
    limit = "기준 " + str(NO_RUN_AFTER_S // 86400) + "일"
    elapsed = "마지막 실행 시작 후 " + _span(seconds)
    static = {
        "under": elapsed + " (화면을 만든 시각 기준)",
        "over": "무실행 의심: " + elapsed + " (화면을 만든 시각 기준. " + limit + ")",
        "skew": "시계 불일치: 마지막 실행의 시작 시각이 화면을 만든 시각보다 미래다",
    }[state]
    return _timed(
        since,
        NO_RUN_AFTER_S,
        static,
        _join("마지막 실행 시작 후 ", _ELAPSED),
        _join(
            _tag("strong", "무실행 의심"),
            ": 마지막 실행 시작 후 ",
            _ELAPSED,
            " (" + limit + ")",
        ),
        _join(
            _tag("strong", "시계 불일치"),
            ": 마지막 실행의 시작 시각이 이 PC의 시계보다 미래다",
        ),
        tag="p",
        id="last-age",
    )


def _runs_section(runs: list, failure: str | None, moment: datetime) -> _Html:
    heading = _tag("h2", "최근 실행 (최근 " + str(RUN_LIMIT) + "건)")
    if failure is not None or not runs:
        return _tag(
            "section", heading, _tag("p", _NOT_READ if failure else _NO_RUNS), id="runs"
        )
    rows = []
    for run in runs:
        kind, label = classify_run(run, moment)
        rows.append(
            _row(
                _badge(kind),
                _run_status(run, moment, label),
                _when(run.get("started_at")),
                _duration(run.get("duration_ms")),
                _run_reason(run),
                _dry_run(run.get("dry_run")),
                _valuations(run),
            )
        )
    titles = ("분류", "상태", "시작 (KST)", "소요", "사유 코드", "dry-run", "valuation")
    return _tag("section", heading, _table(titles, rows), id="runs")


def _step_kind(kind: object) -> str:
    if type(kind) is str and kind in _STEP_KINDS:
        return _labelled(_STEP_KINDS[kind], kind)
    return _unlisted(kind)


def _target(step: dict) -> str:
    kind, target = step.get("kind"), step.get("target")
    if kind == "discovery":
        return _code(target, _MARKET)
    if kind == "artifact" or kind == "delivery":
        if type(target) is str and target in _TARGETS:
            return _TARGETS[target]
        return _unlisted(target)
    return _name(target)


def _step_result(step: dict, label: str) -> str:
    state = step.get("state")
    if type(state) is str and state in _NOT_ENDED:
        return _labelled(label, state)
    if state != "ENDED":
        return _unlisted(state)
    outcome = step.get("outcome")
    return _unlisted(outcome) if label == UNKNOWN else _labelled(label, outcome)


def _degraded(value: object) -> str:
    if type(value) is not list:
        return UNKNOWN
    shown = ", ".join(_code(item, _WORD) for item in value[:_LIST_LIMIT])
    more = len(value) - _LIST_LIMIT
    return shown + " 외 " + str(more) + "개" if more > 0 else shown


_NOTES = (  # the facts of a step that are shown, in this order
    ("ticker", "티커", lambda value: _code(value, _TICKER)),
    ("market", "시장", lambda value: _code(value, _MARKET)),
    ("stage", "멈춘 곳", lambda value: _code(value, _WORD)),
    ("error_type", "예외 종류", lambda value: _code(value, _WORD)),
    ("degraded", "품질 저하", _degraded),
    ("news_count", "뉴스", _number),
    ("discovered", "후보", _number),
    ("path", "경로", lambda value: _code(value, _WORD)),
    ("eligible", "대상", _number),
    ("uploaded", "올림", _number),
)
_NOTE_KEYS = frozenset(key for key, _, _ in _NOTES)


def _step_notes(step: dict) -> str:
    facts = _facts(step)
    if facts is None:
        return UNKNOWN
    parts = [
        label + " " + show(facts[key])
        for key, label, show in _NOTES
        # nothing degraded is the usual case and is not worth a word
        if facts.get(key) is not None and not (key == "degraded" and facts[key] == [])
    ]
    others = sum(1 for key in facts if key not in _NOTE_KEYS)
    if others:
        parts.append("외 " + str(others) + "개 항목")
    return " · ".join(parts) if parts else ABSENT


def _steps_section(runs: list, steps: list, failure: str | None) -> _Html:
    heading = _tag("h2", "가장 최근 실행의 단계")
    if failure is not None or not runs:
        return _tag(
            "section",
            heading,
            _tag("p", _NOT_READ if failure else _NO_RUNS),
            id="steps",
        )
    run_id = runs[0].get("run_id")
    counts = dict.fromkeys(KIND_LABELS, 0)
    rows = []
    # Every step is counted; only the first STEP_LIMIT are listed.
    for number, step in enumerate(steps):
        kind, label = classify_step(step)
        counts[kind] += 1
        if number < STEP_LIMIT:
            rows.append(
                _row(
                    _badge(kind),
                    _step_kind(step.get("kind")),
                    _target(step),
                    _step_result(step, label),
                    _reason(step.get("reason_code")),
                    _duration(step.get("duration_ms")),
                    _step_notes(step),
                )
            )
    summary = (
        "단계 "
        + str(len(steps))
        + "개: "
        + ", ".join(
            KIND_LABELS[kind] + " " + str(count) for kind, count in counts.items()
        )
    )
    parts = [
        heading,
        _tag(
            "p",
            "실행 id: ",
            _tag(
                "code",
                run_id
                if type(run_id) is str and _RUN_ID.fullmatch(run_id)
                else UNKNOWN,
            ),
        ),
        _tag("p", summary, id="step-counts"),
    ]
    if rows:
        titles = ("분류", "종류", "대상", "결과", "사유 코드", "소요", "덧붙임")
        parts.append(_table(titles, rows))
    if len(steps) > STEP_LIMIT:
        parts.append(
            _tag(
                "p",
                "단계가 많아 앞의 "
                + str(STEP_LIMIT)
                + "개만 싣는다. 나머지 "
                + str(len(steps) - STEP_LIMIT)
                + "개는 표시하지 않았다(위의 개수에는 들어 있다).",
                class_="note",
            )
        )
    return _tag("section", *parts, id="steps")


def _notes() -> _Html:
    lines = (
        "시작이 거절된 실행(다른 실행이 진행 중이거나 상태 파일이 손상된 경우)은 "
        "기록되지 않아 여기 나오지 않는다.",
        "dry-run도 실행으로 센다.",
        "실행 프로세스가 살아 있는지는 이 화면이 알 수 없다. 시작 후 경과 시간으로만 말한다.",
        "분류: 정상 / 주의(끝났지만 확인할 것이 있다) / 막힘(실패했거나 끝을 기록하지 못했다) / "
        "미확정(아직 끝나지 않았다) / 알 수 없음(이 화면이 모르는 값이다). "
        "알 수 없음은 정상으로 세지 않는다.",
    )
    items = _tag("ul", *[_tag("li", line) for line in lines])
    return _tag("footer", _tag("h2", "안내"), items, id="notes")


def _page(
    runs: list,
    steps: list,
    failure: str | None,
    failure_class: str | None,
    moment: datetime,
) -> str:
    head = _tag(
        "head",
        _tag("meta", charset="utf-8"),
        # second in the head: a policy in a meta element does not reach back
        _tag("meta", http_equiv="Content-Security-Policy", content=_POLICY),
        _tag("meta", http_equiv="refresh", content=str(RELOAD_S)),
        _tag("title", "BVT 주간 실행 모니터"),
        _tag("style", _STYLE),
    )
    body = _tag(
        "body",
        _header(moment),
        _BREAK,
        _tag(
            "main",
            _state_section(failure, failure_class),
            _BREAK,
            _last_run_section(runs, failure, moment),
            _BREAK,
            _runs_section(runs, failure, moment),
            _BREAK,
            _steps_section(runs, steps, failure),
        ),
        _BREAK,
        _notes(),
        _BREAK,
        _tag("script", _SCRIPT),
    )
    return _join(_DOCTYPE, _tag("html", head, _BREAK, body, lang="ko"), _BREAK)


# ── Writing: the whole page or nothing ───────────────────────────────────────


def _swap(scratch: str, out_path: Path) -> None:
    """os.replace(), again after a pause while it fails with PermissionError.

    On Windows a file cannot be replaced while another handle has it open.
    The last failure is raised; any other error is raised at once.
    """
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(scratch, out_path)
            return
        except PermissionError:
            if attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_WAIT_S)


def _write(out_path: Path, data: bytes) -> None:
    """Put the page in place whole. On any failure the old page is untouched
    and the scratch file is removed."""
    out_path.parent.mkdir(exist_ok=True)  # this folder only, never its parents
    handle, scratch = tempfile.mkstemp(
        dir=out_path.parent, prefix=out_path.name + ".", suffix=".tmp"
    )
    try:
        try:
            stream = os.fdopen(handle, "wb")
        except BaseException:
            os.close(handle)
            raise
        with stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _swap(scratch, out_path)
    except BaseException:
        try:
            os.unlink(scratch)
        except OSError:
            pass  # it may be left behind; the page itself is not affected
        raise


def build(db_path=None, out_path=None, *, now=None) -> int:
    """Build the page; 0, 2 or 1 as the module docstring says.

    ``db_path`` defaults to run_state.DEFAULT_DB_PATH and ``out_path`` to
    monitor.html next to the database. ``now`` returns an aware datetime; it
    is injectable so tests do not depend on the wall clock. A defect of this
    module is raised, not turned into a page (main() turns it into exit 1),
    and so is a call that names the database itself as the page.
    """
    db = Path(run_state.DEFAULT_DB_PATH if db_path is None else db_path)
    out = db.with_name(PAGE_NAME) if out_path is None else Path(out_path)
    if out.resolve() == db.resolve():
        raise ValueError("the page cannot be written over the database")
    moment = datetime.now(timezone.utc) if now is None else now()
    if moment.utcoffset() is None:
        raise ValueError("the clock must return an aware datetime")
    runs, steps, failure, failure_class = _read(db)
    if failure is not None:
        logger.warning("Monitor: the run state was not read (%s).", failure)
    data = _page(runs, steps, failure, failure_class, moment).encode("utf-8")
    try:
        _write(out, data)
    except OSError as exc:
        logger.error("Monitor: the page was not written (%s).", type(exc).__name__)
        return 1
    return 0 if failure is None else 2


def main() -> int:
    """The command. It takes no arguments and shows no traceback: its output
    goes to the log of a scheduled task, and a traceback holds paths."""
    if len(sys.argv) > 1:
        print("usage: python -m tools.monitor.build  (no arguments)", file=sys.stderr)
        return 1
    try:
        return build()
    except Exception as exc:
        name = type(exc).__name__
        logger.error(
            "Monitor: %s (%s).", BUILD_FAILED, name if _WORD.fullmatch(name) else "?"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
