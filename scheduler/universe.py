"""The selection universe: reader and validator for ``references/universe.yaml``.

The weekly target selection (S1) picks companies from this file. A file is
taken whole or refused whole: ``load_universe()`` returns a frozen
``Universe`` or raises ``UniverseError`` carrying every problem it found.
No other exception leaves this module for any file content. Nothing here
touches the network, the clock, the environment or the disk beyond reading
the one file it is given.

File format (``schema_version: 1``)::

    schema_version: 1
    as_of: 2026-11-27        # unquoted date: the day the list was true
    coverage: pilot          # pilot | full
    sources:
      - "where the list came from"
    entries:
      - ticker: "005930"     # quote it: unquoted 000660 is the integer 432 to YAML
        market: KR           # KR | US
        name: "삼성전자"
        sector: information_technology
        is_financial: false
        semis_equipment: true        # optional, default false
        exchange: KOSPI              # optional
        basis: kospi200              # optional; required when coverage is full
        dart_corp_code: "00126380"   # optional, KR only
        industry_code: "KSIC:264"    # optional, as engine/industry_codes.py reads it

Text fields take text only. PyYAML reads an unquoted ``000660`` as the
integer 432 and an unquoted ``ON`` as a boolean; turning those back into
text would name a different company, so they are refused. The reader sees
the value YAML produced, not the quotes: an unquoted ``005930`` happens to
stay text and is accepted.

``sector`` and ``is_financial`` are written by a person. They are not
derived from ``industry_code``, and the two can disagree: SIC 6324 (hospital
and medical service plans) lies in the range ``engine/industry_codes.py``
reads as financial, and a health insurer is not a financial company here.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Annotated, Literal, NamedTuple, get_args

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
)

UNIVERSE_PATH = Path(__file__).resolve().parent.parent / "references" / "universe.yaml"

Market = Literal["KR", "US"]
Sector = Literal[
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
]
Coverage = Literal["pilot", "full"]
Exchange = Literal["KOSPI", "KOSDAQ", "NYSE", "NASDAQ"]
Basis = Literal["kospi200", "sp500", "watchlist"]

SECTORS: tuple[str, ...] = get_args(Sector)

PROBLEM_CODES: tuple[str, ...] = (
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

# One line of text: not blank, no blank at either end, no control character
# (line break and tab included) and no Unicode line or paragraph separator.
# The whole value must match.
_Text = Annotated[
    str,
    Field(strict=True, pattern=r"^[^\s\p{Cc}](?:[^\p{Cc}\p{Zl}\p{Zp}]*[^\s\p{Cc}])?$"),
]
_CorpCode = Annotated[str, Field(strict=True, pattern=r"^[0-9]{8}$")]
_IndustryCode = Annotated[str, Field(strict=True, pattern=r"^(?:KSIC|SIC):[0-9]{2,5}$")]

# Matched with fullmatch: "AAPL\n" is not a ticker.
_TICKER_FORMS: dict[str, re.Pattern[str]] = {
    "KR": re.compile(r"[0-9]{6}"),
    "US": re.compile(r"[A-Z]{1,5}(?:-[A-Z])?"),
}
_MARKET_EXCHANGES: dict[str, tuple[str, ...]] = {
    "KR": ("KOSPI", "KOSDAQ"),
    "US": ("NYSE", "NASDAQ"),
}
_MARKET_BASES: dict[str, tuple[str, ...]] = {
    "KR": ("kospi200", "watchlist"),
    "US": ("sp500", "watchlist"),
}
_MARKET_CODE_SYSTEM: dict[str, str] = {"KR": "KSIC:", "US": "SIC:"}

# A ticker is shown in a problem's place only when it is plain to print.
_PLAIN_TICKER = re.compile(r"[0-9A-Za-z.\-]{1,12}")
_PLAIN_MARKET = re.compile(r"[A-Za-z]{1,4}")
_MERGE_TAG = "tag:yaml.org,2002:merge"


class UniverseEntry(BaseModel):
    """One company of the universe."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ticker: Annotated[str, Field(strict=True)]
    market: Market
    name: _Text
    sector: Sector
    is_financial: StrictBool
    semis_equipment: StrictBool = False
    exchange: Exchange | None = None
    basis: Basis | None = None
    dart_corp_code: _CorpCode | None = None
    industry_code: _IndustryCode | None = None


class Universe(BaseModel):
    """A validated universe file. Entries keep the order of the file."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    as_of: Annotated[date, Field(strict=True)]
    coverage: Coverage
    sources: tuple[_Text, ...]
    entries: tuple[UniverseEntry, ...]

    @field_validator("sources", "entries", mode="before")
    @classmethod
    def _a_list_with_items(cls, value: object) -> object:
        # pydantic would turn a YAML !!set into a tuple: an empty set would be
        # an empty universe, and a set of sources has no order.
        if not isinstance(value, list):
            raise ValueError("a list is required")
        if not value:
            raise ValueError("at least one item is required")
        return value

    def content_hash(self) -> str:
        """sha256 of the validated content, the same on every platform.

        Comments, spacing, quoting, line endings, key order and the order of
        the entries do not enter; every validated value does, the order of
        ``sources`` included. A field left at its default is the same as a
        field left out, so a later optional field does not change the hash
        of a file that does not use it. The hash names the universe only:
        the code that reads it is named by the commit in the step key.
        """
        payload = self.model_dump(mode="json", exclude_defaults=True)
        payload["entries"] = sorted(
            payload["entries"], key=lambda entry: (entry["market"], entry["ticker"])
        )
        text = json.dumps(
            payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(text.encode("ascii")).hexdigest()


class UniverseProblem(NamedTuple):
    """One reason a universe file was refused."""

    code: str
    where: str
    detail: str


class UniverseError(Exception):
    """The universe file was refused. ``problems`` holds every reason found."""

    def __init__(self, problems: list[UniverseProblem]):
        self.problems: tuple[UniverseProblem, ...] = tuple(problems)
        super().__init__(
            "; ".join(f"{p.code} at {p.where}: {p.detail}" for p in self.problems)
        )


class _DuplicateKey(yaml.constructor.ConstructorError):
    """A mapping names the same key twice."""


class _UniqueKeyLoader(yaml.SafeLoader):
    """SafeLoader without aliases and merge keys, and with repeated keys refused.

    PyYAML keeps the last of a repeated key silently, and a merge key lets
    an entry take fields that are not written in it. With neither aliases
    nor merge keys, the keys of a mapping are exactly the keys written.
    """

    def compose_node(self, parent, index):
        if self.check_event(yaml.events.AliasEvent):
            event = self.peek_event()
            raise yaml.composer.ComposerError(
                None, None, "an alias is not accepted", event.start_mark
            )
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        if isinstance(node, yaml.MappingNode):
            seen = set()
            for key_node, _value_node in node.value:
                if key_node.tag == _MERGE_TAG:
                    raise yaml.constructor.ConstructorError(
                        None, None, "a merge key is not accepted", key_node.start_mark
                    )
                key = self.construct_object(key_node, deep=True)
                try:
                    repeated = key in seen
                    seen.add(key)
                except TypeError:  # an unhashable key; the base class reports it
                    continue
                if repeated:
                    raise _DuplicateKey(
                        None, None, f"key {key!r} is repeated", key_node.start_mark
                    )
        return super().construct_mapping(node, deep=deep)


def _line_of(error: Exception) -> str:
    mark = getattr(error, "problem_mark", None)
    return f"line {mark.line + 1}" if mark is not None else "document"


def _all_text_is_unicode(value: object) -> bool:
    """False when any text in the loaded document cannot be written as UTF-8.

    A double-quoted YAML scalar can spell a lone surrogate. Such text cannot
    be stored, printed or hashed, so the document is refused before any of
    it reaches a problem's place or the hash. The document has no aliases,
    so it is a tree and the walk ends.
    """
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True
    if isinstance(value, dict):
        return all(
            _all_text_is_unicode(key) and _all_text_is_unicode(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set, frozenset)):
        return all(_all_text_is_unicode(item) for item in value)
    return True


def _label(market: object, ticker: object) -> str:
    """`` (KR:005930)``, or nothing when the two are not plain to print."""
    if isinstance(market, str) and isinstance(ticker, str):
        if _PLAIN_MARKET.fullmatch(market) and _PLAIN_TICKER.fullmatch(ticker):
            return f" ({market}:{ticker})"
    return ""


def _schema_place(raw: dict, loc: tuple) -> str:
    """``entries[3] (KR:005930).sector`` for a pydantic error location."""
    place = ""
    for position, part in enumerate(loc):
        if isinstance(part, int):
            place += f"[{part}]"
        else:
            place += f".{part}" if place else str(part)
        if position == 1 and loc[0] == "entries" and isinstance(part, int):
            entries = raw.get("entries")
            if (
                isinstance(entries, list)
                and 0 <= part < len(entries)
                and isinstance(entries[part], dict)
            ):
                place += _label(
                    entries[part].get("market"), entries[part].get("ticker")
                )
    return place or "document"


def _cross_problems(universe: Universe) -> list[UniverseProblem]:
    """Rules that span fields or entries. Every violation is reported.

    A repeated ticker or corp code gives one problem at each entry after
    the first that carries it, naming the first.
    """
    problems = []
    first_ticker: dict[tuple[str, str], int] = {}
    first_corp_code: dict[str, int] = {}

    for index, entry in enumerate(universe.entries):
        where = f"entries[{index}]{_label(entry.market, entry.ticker)}"

        def add(code: str, detail: str, where: str = where) -> None:
            problems.append(UniverseProblem(code, where, detail))

        if not _TICKER_FORMS[entry.market].fullmatch(entry.ticker):
            add("TICKER_FORMAT", f"not a {entry.market} ticker")

        ticker_key = (entry.market, entry.ticker)
        if ticker_key in first_ticker:
            add("DUPLICATE_TICKER", f"also entries[{first_ticker[ticker_key]}]")
        else:
            first_ticker[ticker_key] = index

        if entry.dart_corp_code is not None:
            if entry.dart_corp_code in first_corp_code:
                add(
                    "DUPLICATE_CORP_CODE",
                    f"also entries[{first_corp_code[entry.dart_corp_code]}]",
                )
            else:
                first_corp_code[entry.dart_corp_code] = index
            if entry.market != "KR":
                add(
                    "MARKET_FIELD_MISMATCH", "dart_corp_code on an entry that is not KR"
                )

        if (
            entry.exchange is not None
            and entry.exchange not in _MARKET_EXCHANGES[entry.market]
        ):
            add(
                "MARKET_FIELD_MISMATCH",
                f"exchange {entry.exchange} is not a {entry.market} exchange",
            )
        if entry.basis is not None and entry.basis not in _MARKET_BASES[entry.market]:
            add(
                "MARKET_FIELD_MISMATCH",
                f"basis {entry.basis} is not a {entry.market} basis",
            )
        code_system = _MARKET_CODE_SYSTEM[entry.market]
        if entry.industry_code is not None and not entry.industry_code.startswith(
            code_system
        ):
            add(
                "MARKET_FIELD_MISMATCH",
                f"industry_code of a {entry.market} entry starts with {code_system}",
            )

        if entry.is_financial and entry.sector != "financials":
            add("FINANCIAL_SECTOR_MISMATCH", f"is_financial with sector {entry.sector}")
        if entry.semis_equipment and entry.sector != "information_technology":
            add("SEMIS_SECTOR_MISMATCH", f"semis_equipment with sector {entry.sector}")
        if universe.coverage == "full" and entry.basis is None:
            add("BASIS_REQUIRED", "coverage is full and basis is missing")

    return problems


def parse_universe(text: str) -> Universe:
    """Validate the text of a universe file. Raises ``UniverseError``, nothing else."""
    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)  # a SafeLoader subclass
        text_is_unicode = _all_text_is_unicode(raw)
    except _DuplicateKey as error:
        raise UniverseError(
            [UniverseProblem("DUPLICATE_KEY", _line_of(error), str(error.problem))]
        ) from None
    except Exception as error:
        # Whatever the YAML reader raises: yaml.YAMLError, ValueError for the
        # date 2026-02-30, RecursionError for a document nested too deep.
        problem = getattr(error, "problem", None)
        detail = type(error).__name__ + (
            f": {problem}" if isinstance(problem, str) else ""
        )
        raise UniverseError(
            [UniverseProblem("YAML_SYNTAX", _line_of(error), detail)]
        ) from None

    if not isinstance(raw, dict):
        raise UniverseError(
            [UniverseProblem("SCHEMA", "document", "the top level is not a mapping")]
        )
    if not text_is_unicode:
        raise UniverseError(
            [UniverseProblem("SCHEMA", "document", "text that is not valid Unicode")]
        )
    try:
        universe = Universe.model_validate(raw)
    except ValidationError as error:
        problems = [
            UniverseProblem(
                "SCHEMA",
                _schema_place(raw, item["loc"]),
                f"{item['type']}: {item['msg']}",
            )
            for item in error.errors()
        ]
        raise UniverseError(problems) from None

    problems = _cross_problems(universe)
    if problems:
        raise UniverseError(problems)
    return universe


def load_universe(path: Path | None = None) -> Universe:
    """Read and validate a universe file (default: the repository's).

    Raises ``UniverseError``, nothing else.
    """
    where = "path"
    try:
        target = UNIVERSE_PATH if path is None else Path(path)
        if target.name.isprintable() and target.name:
            where = target.name
        data = target.read_bytes()
    except Exception as error:
        # Whatever reading raises: OSError for a missing file or a folder,
        # ValueError for a path with a NUL in it, TypeError for no path at all.
        raise UniverseError(
            [UniverseProblem("UNREADABLE", where, type(error).__name__)]
        ) from None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UniverseError(
            [UniverseProblem("NOT_UTF8", where, "the file is not UTF-8")]
        ) from None
    return parse_universe(text)
