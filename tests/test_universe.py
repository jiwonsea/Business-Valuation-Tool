"""Tests for scheduler/universe.py: the selection universe reader and validator (K-1B).

One fixture, tests/fixtures/universe_valid.yaml. Broken files are made from
it inside the tests; files that must exist on disk go under tmp_path.
profiles/ is not read and nothing here touches the network.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from engine.industry_codes import is_financial_code
from scheduler.universe import (
    PROBLEM_CODES,
    SECTORS,
    UNIVERSE_PATH,
    Universe,
    UniverseError,
    UniverseProblem,
    load_universe,
    parse_universe,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "universe_valid.yaml"
# Worked out by hand from the fixture, without the module (tmp/k1b/evidence/fixture_hash.py).
FIXTURE_HASH = "e60218c878a70fe35f8254de72e2f6a57e6a76072bde8981f2084b4db7a9a041"
DROP = object()


def _text() -> str:
    """The fixture with LF line ends, whatever the checkout wrote."""
    return FIXTURE.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _doc() -> dict:
    return yaml.safe_load(_text())


def _dump(doc: object) -> str:
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


def _apply(mapping: dict, changes: dict) -> None:
    for key, value in changes.items():
        if value is DROP:
            del mapping[key]
        else:
            mapping[key] = value


def _top(**changes: object) -> str:
    """The fixture with top-level keys changed (DROP removes one)."""
    doc = _doc()
    _apply(doc, changes)
    return _dump(doc)


def _entry(index: int, **changes: object) -> str:
    """The fixture with one entry's keys changed (DROP removes one)."""
    doc = _doc()
    _apply(doc["entries"][index], changes)
    return _dump(doc)


def _replaced(old: str, new: str) -> str:
    """The fixture text with one exact piece replaced."""
    text = _text()
    assert text.count(old) == 1, old
    return text.replace(old, new)


def _problems(text: str) -> tuple[UniverseProblem, ...]:
    with pytest.raises(UniverseError) as caught:
        parse_universe(text)
    return caught.value.problems


def _codes(text: str) -> list[str]:
    return [problem.code for problem in _problems(text)]


def _file_codes(path: Path) -> list[str]:
    with pytest.raises(UniverseError) as caught:
        load_universe(path)
    return [problem.code for problem in caught.value.problems]


# ---------------------------------------------------------------------------
# A valid file
# ---------------------------------------------------------------------------


class TestValidFile:
    def test_fixture_loads(self):
        universe = load_universe(FIXTURE)
        assert isinstance(universe, Universe)
        assert universe.schema_version == 1
        assert universe.as_of == dt.date(2026, 10, 1)
        assert universe.coverage == "full"
        assert universe.sources == ("test fixture, hand-written",)
        assert [(e.market, e.ticker) for e in universe.entries] == [
            ("KR", "005930"),
            ("KR", "105560"),
            ("KR", "247540"),
            ("US", "AAPL"),
            ("US", "JPM"),
            ("US", "BRK-B"),
        ]

    def test_every_field_of_a_full_entry(self):
        entry = load_universe(FIXTURE).entries[0]
        assert entry.model_dump() == {
            "ticker": "005930",
            "market": "KR",
            "name": "삼성전자",
            "sector": "information_technology",
            "is_financial": False,
            "semis_equipment": True,
            "exchange": "KOSPI",
            "basis": "kospi200",
            "dart_corp_code": "00126380",
            "industry_code": "KSIC:264",
        }

    def test_left_out_optional_fields_take_their_defaults(self):
        entry = load_universe(FIXTURE).entries[2]
        assert entry.ticker == "247540"
        assert entry.semis_equipment is False
        assert entry.exchange is None
        assert entry.dart_corp_code is None
        assert entry.industry_code is None

    def test_text_and_file_give_the_same_universe(self):
        assert parse_universe(_text()) == load_universe(FIXTURE)

    def test_the_fixture_survives_the_dump_the_other_tests_use(self):
        assert parse_universe(_dump(_doc())) == load_universe(FIXTURE)

    def test_result_cannot_be_changed(self):
        universe = load_universe(FIXTURE)
        assert isinstance(universe.entries, tuple)
        assert isinstance(universe.sources, tuple)
        with pytest.raises(ValidationError):
            universe.coverage = "pilot"
        with pytest.raises(ValidationError):
            universe.entries[0].sector = "energy"

    def test_line_endings_and_bom_do_not_matter(self, tmp_path):
        lf = _text().encode("utf-8")
        crlf = _text().replace("\n", "\r\n").encode("utf-8")
        variants = {"lf": lf, "crlf": crlf, "bom": b"\xef\xbb\xbf" + crlf}
        loaded = []
        for name, data in variants.items():
            path = tmp_path / f"{name}.yaml"
            path.write_bytes(data)
            loaded.append(load_universe(path))
        assert loaded[0] == loaded[1] == loaded[2] == load_universe(FIXTURE)
        assert {universe.content_hash() for universe in loaded} == {FIXTURE_HASH}

    def test_the_fixed_lists(self):
        assert SECTORS == (
            "energy",
            "materials",
            "industrials",
            "consumer_discretionary",
            "consumer_staples",
            "health_care",
            "financials",
            "information_technology",
            "communication_services",
            "utilities",
            "real_estate",
        )
        assert PROBLEM_CODES == (
            "UNREADABLE",
            "NOT_UTF8",
            "YAML_SYNTAX",
            "DUPLICATE_KEY",
            "SCHEMA",
            "TICKER_FORMAT",
            "DUPLICATE_TICKER",
            "DUPLICATE_CORP_CODE",
            "MARKET_FIELD_MISMATCH",
            "FINANCIAL_SECTOR_MISMATCH",
            "SEMIS_SECTOR_MISMATCH",
            "BASIS_REQUIRED",
        )

    @pytest.mark.parametrize("sector", SECTORS)
    def test_every_listed_sector_is_accepted(self, sector):
        # entries[2] is neither financial nor semis, so any sector is consistent.
        assert parse_universe(_entry(2, sector=sector)).entries[2].sector == sector


# ---------------------------------------------------------------------------
# Text stays text: what YAML turns an unquoted value into is refused
# ---------------------------------------------------------------------------


class TestTextIsNotCoerced:
    @pytest.mark.parametrize(
        ("old", "new", "where"),
        [
            # 000660 unquoted is the integer 432 to PyYAML.
            ('ticker: "005930"', "ticker: 000660", "entries[0].ticker"),
            # 00401731 unquoted is the integer 132057.
            (
                'dart_corp_code: "00688996"',
                "dart_corp_code: 00401731",
                "entries[1] (KR:105560).dart_corp_code",
            ),
            # ON unquoted is a boolean.
            ('ticker: "AAPL"', "ticker: ON", "entries[3].ticker"),
            ('name: "Apple Inc."', "name: 2026", "entries[3] (US:AAPL).name"),
        ],
    )
    def test_unquoted_value_that_yaml_reads_as_a_number_or_boolean(
        self, old, new, where
    ):
        problems = _problems(_replaced(old, new))
        assert [(p.code, p.where) for p in problems] == [("SCHEMA", where)]

    def test_yaml_really_reads_these_as_other_types(self):
        # The premise of the tests above; if PyYAML changes, they stop proving anything.
        assert yaml.safe_load("[000660, 00401731, ON]") == [432, 132057, True]

    def test_the_reader_sees_the_value_not_the_quotes(self):
        # Unquoted 005930 has a 9, is no octal number, and stays text: accepted,
        # and the same universe as the quoted form.
        assert yaml.safe_load("005930") == "005930"
        universe = parse_universe(_replaced('ticker: "005930"', "ticker: 005930"))
        assert universe.entries[0].ticker == "005930"
        assert universe.content_hash() == FIXTURE_HASH


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

_SOURCE_LINE = '  - "test fixture, hand-written"'
_SOURCES_BLOCK = "sources:\n" + _SOURCE_LINE + "\n"

_SCHEMA_CASES = [
    pytest.param(lambda: "- a\n- b\n", id="top level is a list"),
    pytest.param(lambda: "", id="empty document"),
    pytest.param(lambda: "# only a comment\n", id="comment only"),
    pytest.param(lambda: "universe\n", id="top level is a scalar"),
    pytest.param(lambda: _top(schema_version=DROP), id="no schema_version"),
    pytest.param(lambda: _top(as_of=DROP), id="no as_of"),
    pytest.param(lambda: _top(coverage=DROP), id="no coverage"),
    pytest.param(lambda: _top(sources=DROP), id="no sources"),
    pytest.param(lambda: _top(entries=DROP), id="no entries"),
    pytest.param(lambda: _entry(0, ticker=DROP), id="no ticker"),
    pytest.param(lambda: _entry(0, market=DROP), id="no market"),
    pytest.param(lambda: _entry(0, name=DROP), id="no name"),
    pytest.param(lambda: _entry(0, sector=DROP), id="no sector"),
    pytest.param(lambda: _entry(0, is_financial=DROP), id="no is_financial"),
    pytest.param(lambda: _top(note="x"), id="unknown top-level key"),
    pytest.param(lambda: _entry(0, semis_equipmnt=True), id="misspelt entry key"),
    pytest.param(lambda: _entry(0, sector="tech"), id="sector outside the list"),
    pytest.param(lambda: _entry(0, sector="Financials"), id="sector in another case"),
    pytest.param(lambda: _entry(0, market="JP"), id="market outside the list"),
    pytest.param(lambda: _entry(0, market="kr"), id="market in lower case"),
    pytest.param(lambda: _top(coverage="partial"), id="coverage outside the list"),
    pytest.param(lambda: _top(coverage="Full"), id="coverage in another case"),
    pytest.param(lambda: _entry(3, exchange="AMEX"), id="exchange outside the list"),
    pytest.param(lambda: _entry(3, exchange="Nasdaq"), id="exchange in another case"),
    pytest.param(lambda: _entry(3, basis="nasdaq100"), id="basis outside the list"),
    pytest.param(lambda: _entry(3, basis="SP500"), id="basis in another case"),
    pytest.param(lambda: _top(schema_version=2), id="schema_version 2"),
    pytest.param(lambda: _top(schema_version=0), id="schema_version 0"),
    pytest.param(lambda: _top(schema_version=True), id="schema_version true"),
    pytest.param(lambda: _top(schema_version="1"), id="schema_version as text"),
    pytest.param(lambda: _top(schema_version=1.0), id="schema_version as float"),
    pytest.param(lambda: _top(as_of="2026-10-01"), id="as_of as quoted text"),
    pytest.param(
        lambda: _top(as_of=dt.datetime(2026, 10, 1, 9, 0)), id="as_of with a time"
    ),
    pytest.param(lambda: _top(as_of=20261001), id="as_of as an integer"),
    pytest.param(lambda: _top(as_of=None), id="as_of null"),
    pytest.param(lambda: _entry(0, is_financial=1), id="is_financial 1"),
    pytest.param(lambda: _entry(0, is_financial="yes"), id="is_financial as text"),
    pytest.param(lambda: _entry(0, is_financial=None), id="is_financial null"),
    pytest.param(lambda: _entry(0, semis_equipment=0), id="semis_equipment 0"),
    pytest.param(
        lambda: _entry(0, semis_equipment="true"), id="semis_equipment as text"
    ),
    pytest.param(lambda: _entry(0, semis_equipment=None), id="semis_equipment null"),
    pytest.param(lambda: _top(entries=[]), id="entries empty"),
    pytest.param(lambda: _top(entries={}), id="entries is a mapping"),
    pytest.param(lambda: _top(entries="005930"), id="entries is text"),
    pytest.param(lambda: _top(entries=["005930"]), id="an entry is text"),
    pytest.param(lambda: _top(sources=[]), id="sources empty"),
    pytest.param(lambda: _top(sources=[""]), id="a blank source"),
    pytest.param(lambda: _top(sources=[" x"]), id="a source with a leading blank"),
    pytest.param(lambda: _top(sources=["x "]), id="a source with a trailing blank"),
    pytest.param(lambda: _top(sources=["DART\nSEC"]), id="a source on two lines"),
    pytest.param(
        lambda: _top(sources=["ok", ""]), id="a blank source after a good one"
    ),
    pytest.param(lambda: _top(sources="one line"), id="sources is text"),
    pytest.param(lambda: _top(sources=[1]), id="a source is a number"),
    pytest.param(lambda: _top(sources=["DART\tSEC"]), id="a source with a tab"),
    pytest.param(
        lambda: _top(sources=["DART\rSEC"]), id="a source with a carriage return"
    ),
    pytest.param(lambda: _top(sources=["DART\x7fSEC"]), id="a source with DEL"),
    pytest.param(
        lambda: _replaced(_SOURCE_LINE, '  - "DART\\x85SEC"'), id="a source with NEL"
    ),
    pytest.param(
        lambda: _replaced(_SOURCE_LINE, '  - "DART\\u2028SEC"'),
        id="a source with a line separator",
    ),
    pytest.param(
        lambda: _replaced(_SOURCE_LINE, '  - "DART\\u2029SEC"'),
        id="a source with a paragraph separator",
    ),
    pytest.param(
        lambda: _replaced(_SOURCES_BLOCK, "sources: !!set {DART, SEC}\n"),
        id="sources is a set",
    ),
    pytest.param(
        lambda: _replaced(_SOURCES_BLOCK, "sources: !!set {}\n"),
        id="sources is an empty set",
    ),
    pytest.param(
        lambda: _text()[: _text().index("entries:\n")] + "entries: !!set {}\n",
        id="entries is an empty set",
    ),
    pytest.param(
        lambda: _text()[: _text().index("entries:\n")] + "entries: !!set {a, b}\n",
        id="entries is a set",
    ),
    pytest.param(lambda: _entry(0, name=""), id="blank name"),
    pytest.param(lambda: _entry(0, name=" 삼성전자"), id="name with a leading blank"),
    pytest.param(lambda: _entry(0, name="삼성전자 "), id="name with a trailing blank"),
    pytest.param(lambda: _entry(0, name="삼성\n전자"), id="name on two lines"),
    pytest.param(
        lambda: _entry(0, name="삼성전자\n"), id="name ending in a line break"
    ),
    pytest.param(lambda: _entry(0, name="삼성\t전자"), id="name with a tab"),
    pytest.param(
        lambda: _entry(0, name="삼성\r전자"), id="name with a carriage return"
    ),
    pytest.param(lambda: _entry(0, name="삼성\x7f전자"), id="name with DEL"),
    pytest.param(
        lambda: _replaced('name: "삼성전자"', 'name: "삼성\\x85전자"'),
        id="name with NEL",
    ),
    pytest.param(
        lambda: _replaced('name: "삼성전자"', 'name: "삼성\\u2028전자"'),
        id="name with a line separator",
    ),
    pytest.param(
        lambda: _replaced('name: "삼성전자"', 'name: "삼성\\u2029전자"'),
        id="name with a paragraph separator",
    ),
    pytest.param(
        lambda: _entry(0, name="\u00a0삼성전자"),
        id="name with a leading no-break space",
    ),
    pytest.param(lambda: _entry(0, name="   "), id="name of blanks only"),
    pytest.param(lambda: _entry(0, name=5), id="name is a number"),
    pytest.param(lambda: _entry(0, ticker=5930), id="ticker is a number"),
    pytest.param(
        lambda: _entry(0, dart_corp_code="1234567"), id="corp code of 7 digits"
    ),
    pytest.param(
        lambda: _entry(0, dart_corp_code="001263800"), id="corp code of 9 digits"
    ),
    pytest.param(
        lambda: _entry(0, dart_corp_code="0012638A"), id="corp code with a letter"
    ),
    pytest.param(lambda: _entry(0, dart_corp_code=126380), id="corp code is a number"),
    pytest.param(
        lambda: _entry(0, industry_code="264"), id="industry code without a system"
    ),
    pytest.param(
        lambda: _entry(0, industry_code="KSIC264"), id="industry code without a colon"
    ),
    pytest.param(
        lambda: _entry(0, industry_code="ksic:264"),
        id="industry code system in lower case",
    ),
    pytest.param(
        lambda: _entry(0, industry_code="NAICS:334413"),
        id="industry code of another system",
    ),
    pytest.param(
        lambda: _entry(0, industry_code="KSIC:2"), id="industry code of 1 digit"
    ),
    pytest.param(
        lambda: _entry(0, industry_code="KSIC:264000"), id="industry code of 6 digits"
    ),
    pytest.param(
        lambda: _entry(0, industry_code="KSIC:26A"), id="industry code with a letter"
    ),
    pytest.param(lambda: _entry(3, industry_code="SIC:1"), id="SIC of 1 digit"),
    pytest.param(lambda: _entry(3, industry_code="SIC:123456"), id="SIC of 6 digits"),
]


class TestStructure:
    @pytest.mark.parametrize("make", _SCHEMA_CASES)
    def test_refused_as_schema(self, make):
        codes = _codes(make())
        assert codes, "at least one problem"
        assert set(codes) == {"SCHEMA"}

    def test_where_names_the_entry_and_the_field(self):
        (problem,) = _problems(_entry(1, sector="tech"))
        assert problem.where == "entries[1] (KR:105560).sector"
        assert problem.detail.startswith("literal_error")

    def test_where_of_a_top_level_field(self):
        (problem,) = _problems(_top(coverage="partial"))
        assert (problem.code, problem.where) == ("SCHEMA", "coverage")

    @pytest.mark.parametrize("text", ["- a\n- b\n", "", "universe\n", "2026\n"])
    def test_a_document_that_is_not_a_mapping_says_so(self, text):
        (problem,) = _problems(text)
        assert problem == ("SCHEMA", "document", "the top level is not a mapping")

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('ticker: "AAPL"', "ticker: !!binary QUFQTA=="),
            ('name: "Apple Inc."', "name: !!binary QXBwbGU="),
            ('"SIC:3571"', "!!binary U0lDOjM1NzE="),
            ('dart_corp_code: "00126380"', "dart_corp_code: !!binary MDAxMjYzODA="),
            (_SOURCE_LINE, "  - !!binary REFSVA=="),
        ],
        ids=["ticker", "name", "industry_code", "dart_corp_code", "source"],
    )
    def test_bytes_are_not_text(self, old, new):
        # Without strict text, pydantic would decode the bytes and accept them:
        # each of these decodes to a value of the right form.
        assert yaml.safe_load("!!binary QUFQTA==") == b"AAPL"
        assert yaml.safe_load("!!binary MDAxMjYzODA=") == b"00126380"
        assert yaml.safe_load("!!binary U0lDOjM1NzE=") == b"SIC:3571"
        assert _codes(_replaced(old, new)) == ["SCHEMA"]

    def test_where_of_a_list_item(self):
        (problem,) = _problems(_top(sources=["ok", " x"]))
        assert (problem.code, problem.where) == ("SCHEMA", "sources[1]")

    def test_a_ticker_that_is_not_plain_is_left_out_of_where(self):
        (problem,) = _problems(_entry(3, ticker="AAPL\n", sector="tech"))
        assert problem.where == "entries[3].sector"

    def test_a_market_that_is_not_plain_is_left_out_of_where(self):
        # The market is no listed value, so it is a problem itself; its text
        # (a line break and more) must not be carried into the place.
        (problem,) = _problems(_entry(3, market="US\nFORGED"))
        assert (problem.code, problem.where) == ("SCHEMA", "entries[3].market")

    def test_an_empty_list_is_one_problem(self):
        assert [(p.code, p.where) for p in _problems(_top(entries=[]))] == [
            ("SCHEMA", "entries")
        ]
        assert [(p.code, p.where) for p in _problems(_top(sources=[]))] == [
            ("SCHEMA", "sources")
        ]

    def test_when_every_entry_is_bad_only_the_entries_are_reported(self):
        # No extra "list too short" problem beside the real ones.
        doc = _doc()
        doc["entries"] = [
            dict(doc["entries"][0], sector="tech"),
            dict(doc["entries"][3], sector="tech"),
        ]
        assert [p.where for p in _problems(_dump(doc))] == [
            "entries[0] (KR:005930).sector",
            "entries[1] (US:AAPL).sector",
        ]

    @pytest.mark.parametrize(
        "field", ["exchange", "basis", "dart_corp_code", "industry_code"]
    )
    def test_an_optional_field_written_as_null_is_the_same_as_left_out(self, field):
        doc = _doc()
        doc["coverage"] = "pilot"  # full coverage needs a basis
        doc["entries"][4][field] = None
        universe = parse_universe(_dump(doc))
        assert getattr(universe.entries[4], field) is None

    @pytest.mark.parametrize(
        ("old", "new"),
        [
            ('name: "Apple Inc."', 'name: "Apple\\ud800Inc."'),
            ('ticker: "AAPL"', 'ticker: "\\ud800"'),
            ('  - "test fixture, hand-written"', '  - "\\udfff"'),
            ("    basis: watchlist\n", '    basis: watchlist\n    "\\ud800": 1\n'),
        ],
        ids=["in a name", "in a ticker", "in a source", "in a key"],
    )
    def test_text_that_is_not_valid_unicode_refuses_the_document(self, old, new):
        # A quoted YAML scalar can spell a lone surrogate; it cannot be stored or hashed.
        (problem,) = _problems(_replaced(old, new))
        assert (problem.code, problem.where) == ("SCHEMA", "document")
        str(problem).encode("utf-8")

    def test_every_schema_problem_is_reported(self):
        doc = _doc()
        doc["entries"][0]["sector"] = "tech"
        doc["entries"][3]["is_financial"] = "no"
        doc["coverage"] = "partial"
        problems = _problems(_dump(doc))
        assert sorted(p.where for p in problems) == [
            "coverage",
            "entries[0] (KR:005930).sector",
            "entries[3] (US:AAPL).is_financial",
        ]
        assert {p.code for p in problems} == {"SCHEMA"}

    def test_cross_rules_wait_for_a_valid_structure(self):
        # entries[0] breaks a cross rule (financial outside financials) and
        # entries[1] the structure: only the structure is reported.
        doc = _doc()
        doc["entries"][0]["is_financial"] = True
        doc["entries"][1]["sector"] = "tech"
        assert _codes(_dump(doc)) == ["SCHEMA"]


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


class TestReading:
    def test_missing_file(self, tmp_path):
        assert _file_codes(tmp_path / "nothing.yaml") == ["UNREADABLE"]

    def test_a_directory(self, tmp_path):
        assert _file_codes(tmp_path) == ["UNREADABLE"]

    def test_where_and_detail_of_an_unreadable_file(self, tmp_path):
        with pytest.raises(UniverseError) as caught:
            load_universe(tmp_path / "nothing.yaml")
        assert caught.value.problems == (
            ("UNREADABLE", "nothing.yaml", "FileNotFoundError"),
        )

    def test_a_path_with_a_nul_in_it(self, tmp_path):
        # read_bytes() raises ValueError here, not an OSError.
        with pytest.raises(UniverseError) as caught:
            load_universe(tmp_path / "a\x00b.yaml")
        assert caught.value.problems == (("UNREADABLE", "path", "ValueError"),)

    def test_a_value_that_is_no_path(self):
        with pytest.raises(UniverseError) as caught:
            load_universe(123)
        assert caught.value.problems == (("UNREADABLE", "path", "TypeError"),)

    def test_where_of_a_file_that_is_not_utf8(self, tmp_path):
        path = tmp_path / "cp949.yaml"
        path.write_bytes(_text().encode("cp949"))
        with pytest.raises(UniverseError) as caught:
            load_universe(path)
        assert caught.value.problems == (
            ("NOT_UTF8", "cp949.yaml", "the file is not UTF-8"),
        )

    def test_cp949_file(self, tmp_path):
        path = tmp_path / "cp949.yaml"
        path.write_bytes(_text().encode("cp949"))
        assert _file_codes(path) == ["NOT_UTF8"]

    def test_nul_padded_file(self, tmp_path):
        path = tmp_path / "nul.yaml"
        path.write_bytes(_text().encode("utf-8") + b"\x00" * 16)
        assert _file_codes(path) == ["YAML_SYNTAX"]

    def test_truncated_file_is_refused(self, tmp_path):
        # Cut in the middle of the last entry: required keys are gone.
        path = tmp_path / "cut.yaml"
        data = _text().encode("utf-8")
        path.write_bytes(data[: data.index(b'name: "BERKSHIRE')])
        assert set(_file_codes(path)) == {"SCHEMA"}

    @pytest.mark.parametrize(
        "text",
        [
            "entries: [1, 2\n",
            "schema_version: 1\n\tas_of: 2026-10-01\n",
            "schema_version: 1\n---\nschema_version: 1\n",
            "a: b: c\n",
        ],
        ids=[
            "open bracket",
            "tab indentation",
            "two documents",
            "nested plain mapping",
        ],
    )
    def test_text_that_is_not_one_yaml_document(self, text):
        assert _codes(text) == ["YAML_SYNTAX"]

    def test_repeated_key_in_an_entry(self):
        text = _replaced(
            '    name: "KB금융"\n', '    name: "KB금융"\n    name: "다른 이름"\n'
        )
        (problem,) = _problems(text)
        assert problem.code == "DUPLICATE_KEY"
        assert "name" in problem.detail
        assert re.fullmatch(r"line \d+", problem.where)

    def test_repeated_top_level_key(self):
        (problem,) = _problems(_text() + "coverage: pilot\n")
        assert problem.code == "DUPLICATE_KEY"
        assert "coverage" in problem.detail
        # The repeated key is on the line added after the fixture's last one.
        assert problem.where == f"line {len(_text().splitlines()) + 1}"

    def test_yaml_alone_would_keep_the_last_of_a_repeated_key(self):
        # The premise of DUPLICATE_KEY.
        assert yaml.safe_load("a: 1\na: 2\n") == {"a": 2}

    def test_a_date_that_does_not_exist(self):
        # PyYAML raises ValueError here, not a YAMLError.
        with pytest.raises(ValueError):
            yaml.safe_load("as_of: 2026-02-30")
        (problem,) = _problems(_replaced("as_of: 2026-10-01", "as_of: 2026-02-30"))
        assert problem == ("YAML_SYNTAX", "document", "ValueError")

    def test_a_merge_key_is_refused(self):
        # With a merge key an entry would take fields that are not written in it.
        text = _text() + (
            "  - <<: {market: US, sector: energy, is_financial: false}\n"
            '    ticker: "CVX"\n'
            '    name: "Chevron"\n'
            "    basis: sp500\n"
        )
        assert yaml.safe_load(text)["entries"][6]["sector"] == "energy"
        (problem,) = _problems(text)
        assert problem.code == "YAML_SYNTAX"
        assert "merge key" in problem.detail

    def test_an_alias_is_refused(self):
        text = (
            _replaced('  - ticker: "BRK-B"', '  - &last\n    ticker: "BRK-B"')
            + "  - *last\n"
        )
        assert len(yaml.safe_load(text)["entries"]) == 7
        (problem,) = _problems(text)
        assert problem.code == "YAML_SYNTAX"
        assert "alias" in problem.detail

    def test_a_quoted_merge_key_is_an_unknown_key(self):
        text = _replaced(
            "    basis: watchlist\n",
            '    basis: watchlist\n    "<<": {sector: energy}\n',
        )
        assert _codes(text) == ["SCHEMA"]

    @pytest.mark.parametrize(
        "text",
        [
            "\x00",
            "a: !!python/object/apply:os.system ['echo x']\n",
            "a: !!timestamp 'not a date'\n",
            "a: !!int 'x'\n",
            "a: !!float 'x'\n",
            "? [a, b]\n: c\n",
            "{a: 1}: b\n",
            "&a [*a]\n",
            "a: " + "[" * 3000 + "]" * 3000 + "\n",
            "a: 2026-13-45\n",
            "a: 2026-01-01 25:61:61\n",
        ],
        ids=[
            "NUL",
            "python tag",
            "timestamp tag on text",
            "int tag on text",
            "float tag on text",
            "list as a key",
            "mapping as a key",
            "self-referring alias",
            "3000 levels deep",
            "month 13",
            "hour 25",
        ],
    )
    def test_whatever_the_yaml_reader_raises_is_a_yaml_syntax_problem(self, text):
        assert _codes(text) == ["YAML_SYNTAX"]

    @pytest.mark.parametrize(
        "text",
        [
            "a: !!binary aGVsbG8=\n",
            "a: !!set {x, y}\n",
            "- !!omap [a: 1]\n",
            "a: !!pairs [b: 1]\n",
            "~\n",
            "3.5\n",
        ],
        ids=["binary", "set", "omap", "pairs", "null", "float"],
    )
    def test_yaml_values_of_other_types_are_schema_problems(self, text):
        assert set(_codes(text)) == {"SCHEMA"}


# ---------------------------------------------------------------------------
# Rules across fields and entries
# ---------------------------------------------------------------------------


class TestTickerFormat:
    @pytest.mark.parametrize(
        "ticker", ["24754", "2475400", "24754A", "247540.KQ", "A247540", ""]
    )
    def test_kr_ticker_refused(self, ticker):
        assert _codes(_entry(2, ticker=ticker)) == ["TICKER_FORMAT"]

    def test_kr_ticker_of_digits_outside_ascii_is_refused(self):
        # Six Arabic-Indic digits: str.isdigit() is true for them, [0-9] is not.
        ticker = "".join(chr(0x0660 + int(digit)) for digit in "247540")
        assert ticker.isdigit() and len(ticker) == 6
        (problem,) = _problems(_entry(2, ticker=ticker))
        assert (problem.code, problem.where) == ("TICKER_FORMAT", "entries[2]")

    @pytest.mark.parametrize(
        "ticker",
        [
            "aapl",
            "BRK.B",
            "TOOLONG",
            "ABCDEF",
            "A1",
            "BRK-BB",
            "-B",
            "AAPL ",
            "AAPL\n",
            "005930",
            "",
        ],
    )
    def test_us_ticker_refused(self, ticker):
        assert _codes(_entry(3, ticker=ticker)) == ["TICKER_FORMAT"]

    @pytest.mark.parametrize("ticker", ["000660", "373220"])
    def test_kr_ticker_accepted(self, ticker):
        assert parse_universe(_entry(2, ticker=ticker)).entries[2].ticker == ticker

    @pytest.mark.parametrize("ticker", ["A", "GOOGL", "BF-B", "ABCDE-Z", "ON"])
    def test_us_ticker_accepted(self, ticker):
        assert parse_universe(_entry(3, ticker=ticker)).entries[3].ticker == ticker


class TestDuplicates:
    def test_same_market_and_ticker_twice(self):
        (problem,) = _problems(_entry(2, ticker="005930"))
        assert problem.code == "DUPLICATE_TICKER"
        assert problem.where == "entries[2] (KR:005930)"
        assert "entries[0]" in problem.detail

    def test_same_corp_code_twice(self):
        (problem,) = _problems(_entry(2, dart_corp_code="00126380"))
        assert problem.code == "DUPLICATE_CORP_CODE"
        assert problem.where == "entries[2] (KR:247540)"
        assert "entries[0]" in problem.detail

    def test_three_copies_of_a_ticker_give_two_problems_naming_the_first(self):
        doc = _doc()
        doc["entries"][1]["ticker"] = "005930"
        doc["entries"][2]["ticker"] = "005930"
        assert _problems(_dump(doc)) == (
            ("DUPLICATE_TICKER", "entries[1] (KR:005930)", "also entries[0]"),
            ("DUPLICATE_TICKER", "entries[2] (KR:005930)", "also entries[0]"),
        )

    def test_three_copies_of_a_corp_code_give_two_problems_naming_the_first(self):
        doc = _doc()
        doc["entries"][1]["dart_corp_code"] = "00126380"
        doc["entries"][2]["dart_corp_code"] = "00126380"
        assert _problems(_dump(doc)) == (
            ("DUPLICATE_CORP_CODE", "entries[1] (KR:105560)", "also entries[0]"),
            ("DUPLICATE_CORP_CODE", "entries[2] (KR:247540)", "also entries[0]"),
        )


class TestMarketFields:
    @pytest.mark.parametrize(
        ("index", "change"),
        [
            (0, {"exchange": "NYSE"}),
            (0, {"exchange": "NASDAQ"}),
            (0, {"basis": "sp500"}),
            (0, {"industry_code": "SIC:3674"}),
            (3, {"exchange": "KOSPI"}),
            (3, {"exchange": "KOSDAQ"}),
            (3, {"basis": "kospi200"}),
            (3, {"industry_code": "KSIC:264"}),
            (3, {"dart_corp_code": "00000001"}),
        ],
    )
    def test_value_of_the_other_market(self, index, change):
        assert _codes(_entry(index, **change)) == ["MARKET_FIELD_MISMATCH"]

    @pytest.mark.parametrize(
        ("index", "change"),
        [
            (0, {"exchange": "KOSDAQ"}),
            (0, {"basis": "watchlist"}),
            (3, {"exchange": "NYSE"}),
            (3, {"basis": "watchlist"}),
            (3, {"industry_code": "SIC:100"}),
            (3, {"industry_code": "SIC:10"}),
            (3, {"industry_code": "SIC:12345"}),
            (0, {"industry_code": "KSIC:26110"}),
            (0, {"industry_code": "KSIC:26"}),
        ],
    )
    def test_value_of_its_own_market(self, index, change):
        entry = parse_universe(_entry(index, **change)).entries[index]
        for key, value in change.items():
            assert getattr(entry, key) == value


class TestSectorFlags:
    def test_financial_outside_financials(self):
        (problem,) = _problems(_entry(3, is_financial=True))
        assert problem.code == "FINANCIAL_SECTOR_MISMATCH"
        assert problem.where == "entries[3] (US:AAPL)"

    def test_financials_sector_without_the_flag_is_allowed(self):
        # A payments network or an exchange: the sector, not a balance-sheet financial.
        assert (
            parse_universe(_entry(4, is_financial=False)).entries[4].is_financial
            is False
        )

    def test_semis_outside_information_technology(self):
        (problem,) = _problems(_entry(1, semis_equipment=True))
        assert problem.code == "SEMIS_SECTOR_MISMATCH"
        assert problem.where == "entries[1] (KR:105560)"

    def test_semis_inside_information_technology(self):
        assert (
            parse_universe(_entry(3, semis_equipment=True)).entries[3].semis_equipment
            is True
        )


class TestBasis:
    def test_full_coverage_needs_a_basis_on_every_entry(self):
        (problem,) = _problems(_entry(2, basis=DROP))
        assert problem.code == "BASIS_REQUIRED"
        assert problem.where == "entries[2] (KR:247540)"

    def test_pilot_coverage_does_not(self):
        doc = _doc()
        doc["coverage"] = "pilot"
        for entry in doc["entries"]:
            del entry["basis"]
        universe = parse_universe(_dump(doc))
        assert universe.coverage == "pilot"
        assert [entry.basis for entry in universe.entries] == [None] * 6


class TestWholeFileOrNothing:
    def test_every_cross_problem_is_reported_at_once(self):
        doc = _doc()
        doc["entries"][0]["exchange"] = "NYSE"
        doc["entries"][1]["semis_equipment"] = True
        doc["entries"][3]["is_financial"] = True
        doc["entries"][5]["ticker"] = "BRK.B"
        problems = _problems(_dump(doc))
        assert [(p.code, p.where) for p in problems] == [
            ("MARKET_FIELD_MISMATCH", "entries[0] (KR:005930)"),
            ("SEMIS_SECTOR_MISMATCH", "entries[1] (KR:105560)"),
            ("FINANCIAL_SECTOR_MISMATCH", "entries[3] (US:AAPL)"),
            ("TICKER_FORMAT", "entries[5] (US:BRK.B)"),
        ]

    def test_the_problems_of_one_entry_come_in_the_order_of_the_rules(self):
        # entries[4] breaks every cross rule it can at once; entries[3] gives
        # it a ticker to repeat. The order is the order of the policy's table.
        doc = _doc()
        doc["entries"][3]["ticker"] = "aapl"
        doc["entries"][4].update(
            ticker="aapl",
            sector="energy",
            is_financial=True,
            semis_equipment=True,
            exchange="KOSPI",
            dart_corp_code="00126380",
            industry_code="KSIC:264",
        )
        del doc["entries"][4]["basis"]
        problems = _problems(_dump(doc))
        assert [(p.code, p.where) for p in problems] == [
            ("TICKER_FORMAT", "entries[3] (US:aapl)"),
            ("TICKER_FORMAT", "entries[4] (US:aapl)"),
            ("DUPLICATE_TICKER", "entries[4] (US:aapl)"),
            ("DUPLICATE_CORP_CODE", "entries[4] (US:aapl)"),
            ("MARKET_FIELD_MISMATCH", "entries[4] (US:aapl)"),
            ("MARKET_FIELD_MISMATCH", "entries[4] (US:aapl)"),
            ("MARKET_FIELD_MISMATCH", "entries[4] (US:aapl)"),
            ("FINANCIAL_SECTOR_MISMATCH", "entries[4] (US:aapl)"),
            ("SEMIS_SECTOR_MISMATCH", "entries[4] (US:aapl)"),
            ("BASIS_REQUIRED", "entries[4] (US:aapl)"),
        ]
        mismatches = [p.detail for p in problems if p.code == "MARKET_FIELD_MISMATCH"]
        assert [detail.split()[0] for detail in mismatches] == [
            "dart_corp_code",
            "exchange",
            "industry_code",
        ]

    def test_a_basis_of_the_other_market_comes_between_exchange_and_code(self):
        doc = _doc()
        doc["entries"][3].update(
            exchange="KOSPI", basis="kospi200", industry_code="KSIC:264"
        )
        details = [p.detail.split()[0] for p in _problems(_dump(doc))]
        assert details == ["exchange", "basis", "industry_code"]

    def test_one_bad_entry_among_thirty_refuses_the_file(self):
        doc = _doc()
        template = doc["entries"][3]
        for first in "QRSTUV":
            for second in "ABCD":
                doc["entries"].append(
                    {
                        **template,
                        "ticker": first + second,
                        "name": f"Company {first}{second}",
                    }
                )
        assert len(doc["entries"]) == 30
        assert len(parse_universe(_dump(doc)).entries) == 30

        doc["entries"][17]["is_financial"] = True
        (problem,) = _problems(_dump(doc))
        assert problem.code == "FINANCIAL_SECTOR_MISMATCH"
        assert problem.where.startswith("entries[17] ")

    def test_error_text_lists_every_problem(self):
        doc = _doc()
        doc["entries"][1]["semis_equipment"] = True
        doc["entries"][3]["is_financial"] = True
        with pytest.raises(UniverseError) as caught:
            parse_universe(_dump(doc))
        message = str(caught.value)
        assert "SEMIS_SECTOR_MISMATCH at entries[1] (KR:105560)" in message
        assert "FINANCIAL_SECTOR_MISMATCH at entries[3] (US:AAPL)" in message

    def test_every_code_in_use_is_listed(self):
        seen = set()
        texts = [
            "a: [1\n",
            _text() + "coverage: pilot\n",
            _top(coverage="partial"),
            _entry(2, ticker="24754"),
            _entry(2, ticker="005930"),
            _entry(2, dart_corp_code="00126380"),
            _entry(3, exchange="KOSPI"),
            _entry(3, is_financial=True),
            _entry(1, semis_equipment=True),
            _entry(2, basis=DROP),
        ]
        for text in texts:
            seen.update(_codes(text))
        assert seen == set(PROBLEM_CODES) - {"UNREADABLE", "NOT_UTF8"}


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


class TestContentHash:
    def test_fixture_hash_is_fixed(self):
        # The same value on Windows (CRLF checkout) and on the Linux CI (LF).
        digest = load_universe(FIXTURE).content_hash()
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert digest == FIXTURE_HASH

    def test_comments_spacing_and_quoting_do_not_enter(self):
        text = "# a note\n" + _text().replace("market: KR", 'market: "KR"').replace(
            "  - ticker", "\n  - ticker"
        )
        assert text != _text()
        assert parse_universe(text).content_hash() == FIXTURE_HASH

    def test_order_of_entries_does_not_enter(self):
        doc = _doc()
        doc["entries"].reverse()
        universe = parse_universe(_dump(doc))
        assert universe.entries[0].ticker == "BRK-B"
        assert universe.content_hash() == FIXTURE_HASH

    def test_order_of_keys_does_not_enter(self):
        text = yaml.safe_dump(_doc(), allow_unicode=True, sort_keys=True)
        assert parse_universe(text).content_hash() == FIXTURE_HASH

    def test_a_default_written_out_does_not_enter(self):
        doc = _doc()
        assert "semis_equipment" not in doc["entries"][3]
        doc["entries"][3]["semis_equipment"] = False
        doc["entries"][2]["exchange"] = None
        assert parse_universe(_dump(doc)).content_hash() == FIXTURE_HASH

    @pytest.mark.parametrize(
        "make",
        [
            pytest.param(lambda: _entry(2, sector="materials"), id="a sector"),
            pytest.param(lambda: _entry(2, name="에코프로"), id="a name"),
            pytest.param(lambda: _entry(3, semis_equipment=True), id="a semis flag"),
            pytest.param(lambda: _entry(4, is_financial=False), id="a financial flag"),
            pytest.param(
                lambda: _entry(2, exchange="KOSDAQ"), id="an optional field added"
            ),
            pytest.param(
                lambda: _entry(0, industry_code=DROP), id="an optional field removed"
            ),
            pytest.param(lambda: _entry(2, ticker="000660"), id="a ticker"),
            pytest.param(lambda: _top(as_of=dt.date(2026, 10, 2)), id="as_of"),
            pytest.param(lambda: _top(sources=["another source"]), id="sources"),
            pytest.param(
                lambda: _top(entries=_doc()["entries"][:5]), id="an entry removed"
            ),
        ],
    )
    def test_a_changed_value_changes_the_hash(self, make):
        assert parse_universe(make()).content_hash() != FIXTURE_HASH

    def test_coverage_enters(self):
        doc = _doc()
        doc["coverage"] = "pilot"
        assert parse_universe(_dump(doc)).content_hash() != FIXTURE_HASH

    def test_order_of_sources_enters(self):
        first = parse_universe(_top(sources=["one", "two"])).content_hash()
        second = parse_universe(_top(sources=["two", "one"])).content_hash()
        assert first != second

    def test_text_outside_ascii_hashes_the_same_everywhere(self):
        # The JSON that is hashed is ASCII only, so no platform encoding enters.
        universe = parse_universe(_entry(2, name="에코프로비엠 🙂 ß"))
        assert re.fullmatch(r"[0-9a-f]{64}", universe.content_hash())
        assert (
            universe.content_hash()
            == "8a412c0f11e48b82769d30635aa3528128e5478b79452ccd4a7c51bebec2969d"
        )


# ---------------------------------------------------------------------------
# Notation shared with the engine, the repository's file, side effects
# ---------------------------------------------------------------------------


class TestIndustryCodeNotation:
    def test_engine_reads_the_fixture_codes(self):
        codes = [
            e.industry_code for e in load_universe(FIXTURE).entries if e.industry_code
        ]
        assert codes == ["KSIC:264", "KSIC:64992", "SIC:3571", "SIC:6021"]
        assert [is_financial_code(code) for code in codes] == [False, True, False, True]


class TestRepositoryFile:
    def test_default_path_is_the_tracked_file(self):
        assert UNIVERSE_PATH == REPO_ROOT / "references" / "universe.yaml"

    def test_the_tracked_file_is_valid(self):
        universe = load_universe()
        assert universe == load_universe(UNIVERSE_PATH)
        assert len(universe.entries) >= 1
        assert re.fullmatch(r"[0-9a-f]{64}", universe.content_hash())

    def test_engine_reads_every_industry_code_of_the_tracked_file(self):
        for entry in load_universe().entries:
            if entry.industry_code is not None:
                assert is_financial_code(entry.industry_code) is not None, entry.ticker


class TestNoSideEffects:
    def test_import_reads_no_repository_file_and_load_needs_no_network(self, tmp_path):
        # A fresh interpreter (-B: no bytecode written). Sockets refuse for the
        # whole run. While scheduler.universe is imported, opening or reading a
        # file under references/ refuses too: importing must not read the data
        # file. (pydantic reads package metadata while a model class is built;
        # with a virtualenv inside the repository that is under the root, so
        # only references/ is fenced.)
        code = (
            "import builtins, io, os, pathlib, socket, sys\n"
            "import ssl, yaml, pydantic  # dependencies load before the guards:\n"
            "# ssl subclasses socket.socket, which is a plain function below\n"
            f"sys.path.insert(0, {str(REPO_ROOT)!r})\n"
            f"root = os.path.normcase({str(REPO_ROOT / 'references')!r}) + os.sep\n"
            "def refuse(*args, **kwargs):\n"
            "    raise AssertionError('refused by the test')\n"
            "socket.socket = refuse\n"
            "socket.create_connection = refuse\n"
            "def guarded(original):\n"
            "    def call(*args, **kwargs):\n"
            "        target = os.path.normcase(os.path.abspath(os.fspath(args[0]))) if args else ''\n"
            "        if target.startswith(root):\n"
            "            raise AssertionError('import read a file under references/')\n"
            "        return original(*args, **kwargs)\n"
            "    return call\n"
            "kept = (builtins.open, io.open, pathlib.Path.open, pathlib.Path.read_bytes, pathlib.Path.read_text)\n"
            "builtins.open, io.open = guarded(kept[0]), guarded(kept[1])\n"
            "pathlib.Path.open, pathlib.Path.read_bytes = guarded(kept[2]), guarded(kept[3])\n"
            "pathlib.Path.read_text = guarded(kept[4])\n"
            "import scheduler.universe as universe\n"
            "builtins.open, io.open, pathlib.Path.open, pathlib.Path.read_bytes, pathlib.Path.read_text = kept\n"
            "loaded = universe.load_universe()\n"
            "banned = ('httpx', 'requests', 'urllib3', 'dotenv', 'yfinance', 'scheduler.weekly_run', 'engine')\n"
            "print(len(loaded.entries) >= 1, sorted(name for name in banned if name in sys.modules))\n"
        )
        done = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        assert done.returncode == 0, done.stderr
        assert done.stdout.strip() == "True []"
        assert list(tmp_path.iterdir()) == []

    def test_the_module_names_no_environment_network_or_clock(self):
        source = (REPO_ROOT / "scheduler" / "universe.py").read_text(encoding="utf-8")
        words = (
            "os.environ",
            "getenv",
            "import os",
            "socket",
            "httpx",
            "requests",
            "urllib",
            "import time",
            "now(",
            "today(",
        )
        for word in words:
            assert word not in source, word
