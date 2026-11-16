"""A selection that carries a ticker is identified with it (K-0C follow-up).

Backstory: the weekly selection names KR companies in English with a 6-digit
stock code, and the lookup compared that name with the Korean registry names
by substring only. ``Samsung Electronics`` matched nothing, ``SK Hynix`` and
``LG Electronics`` resolved to other listed companies (``SK``, ``LG``), and
K-0C then blocked them as IDENTITY_NOT_FOUND / IDENTITY_MISMATCH.

A caller that selected a ticker now passes it along.

KR: among the registry rows that carry a stock code, the rows whose registered
Korean or English name is the selected name are looked for first -- the name
as written, then the same letters, then the same with legal-form words
dropped. The row carrying the selected stock code is the company. When none
of them carries it, name and code disagree and the company the name states
comes back, which the caller then rejects. A name that is nobody's registered
name goes to the old name lookup: the stock code alone identifies nothing,
because one selected code in six was another company's when the past
selections were replayed.

US: the row whose ticker is the selected one comes first, unless the old
result already starts with it.

A lookup without a ticker is unchanged.

Everything here is synthetic: the registry is XML built in the test and the
EDGAR list is a dict. Nothing may reach the network, ``.cache/`` or the API
guard's usage file; the ``world`` fixture fails the test if a replaced
boundary is reached unexpectedly.
"""

from __future__ import annotations

import importlib
import os
from decimal import Decimal
from xml.etree import ElementTree

import pytest

# ── synthetic registry ───────────────────────────────────────────────────────

# (corp_name, stock_code, corp_eng_name, modify_date); corp_code is the index.
REGISTRY = [
    ("삼성전자", "005930", "SAMSUNG ELECTRONICS CO,.LTD", "20251201"),  # 0
    ("SK", "003600", "SK Holdings Co., Ltd.", "20170630"),  # 1: merged predecessor
    ("SK", "034730", "SK Inc.", "20240328"),  # 2
    ("SK하이닉스", "000660", "SK hynix Inc.", "20240328"),  # 3
    ("LG", "003550", "LG Corp.", "20240101"),  # 4
    ("LG전자", "066570", "LG ELECTRONICS INC.", "20260324"),  # 5
    ("현대자동차", "005380", "HYUNDAI MOTOR CO", "20260331"),  # 6
    ("현대차증권", "001500", "HYUNDAI MOTOR SECURITIES CO., LTD.", "20240101"),  # 7
    ("현대코퍼레이션", "011760", "HYUNDAI CORPORATION", "20230216"),  # 8
    ("HD현대", "267250", "HD HYUNDAI CO.,LTD.", "20260401"),  # 9
    ("OCI", "456040", "OCI Company Ltd.", "20251117"),  # 10
    ("OCI홀딩스", "010060", "OCI Holdings Company Ltd.", "20260327"),  # 11
    ("케이티앤지", "033780", "KT&G Corporation", "20250917"),  # 12
    ("삼성전자판매", "", "SAMSUNG ELECTRONICS SALES CO., LTD.", "20200101"),  # 13
    ("한빛", "", "Hanbit Co., Ltd.", "20200101"),  # 14: unlisted namesake
    ("한빛소프트", "047080", "HANBIT SOFT INC.", "20240101"),  # 15
    ("삼성에피스홀딩스", "0126Z0", "SAMSUNG EPIS HOLDINGS CO., LTD.", "20251101"),  # 16
    # two pairs whose English names differ only in the legal form
    ("제이에스", "037110", "JS Company Limited", "20240101"),  # 17
    ("제이에스코퍼레이션", "194370", "JS Corporation", "20240101"),  # 18
    ("SG세계물산", "004060", "SG CORPORATION", "20240101"),  # 19
    ("SG", "255220", "SG CO., LTD.", "20240101"),  # 20
    ("기아", "000270", "KIA CORPORATION", "20240101"),  # 21
    ("두리건설", "111110", " ", "20240101"),  # 22: no English name on file
    # two companies whose English names differ in spacing only
    ("에이엘티", "172670", "ALT Co.,Ltd.", "20240101"),  # 23
    ("알트", "459550", "ALT  Co., Ltd.", "20240101"),  # 24
    # an English name registered as one word, next to a company called Sewon
    ("세원물산", "024830", "SewonCorporation", "20240101"),  # 25
    ("폴라리스세원", "234100", "Sewon Co.,Ltd", "20240101"),  # 26
]


def written(name: str) -> str:
    return " ".join(name.split()).casefold()


def registry(rows) -> ElementTree.Element:
    root = ElementTree.Element("result")
    for index, (name, stock_code, eng_name, modified) in enumerate(rows):
        item = ElementTree.SubElement(root, "list")
        ElementTree.SubElement(item, "corp_code").text = f"{index:08d}"
        ElementTree.SubElement(item, "corp_name").text = name
        ElementTree.SubElement(item, "corp_eng_name").text = eng_name
        # the real file pads an absent stock code with a blank
        ElementTree.SubElement(item, "stock_code").text = stock_code or " "
        ElementTree.SubElement(item, "modify_date").text = modified
    return root


def row_of(stock_code: str, rows=REGISTRY) -> dict:
    """What get_corp_info() returns for the one row carrying ``stock_code``."""
    found = [i for i, row in enumerate(rows) if row[1] == stock_code]
    assert len(found) == 1, found
    return {"corp_code": f"{found[0]:08d}", "stock_code": stock_code, "is_listed": True}


def stock(info: dict | None) -> str | None:
    return info["stock_code"] if info else None


# ── synthetic EDGAR list ─────────────────────────────────────────────────────

# Twelve companies whose name contains "on" come before the one whose ticker
# is ON, as a short ticker meets them in the real, market-cap ordered list.
EDGAR = [
    *[(1000 + i, f"ONW{i}", f"Onward Holdings {i} Inc") for i in range(12)],
    (2001, "ON", "Orbit Semiconductor Corp"),
    (2002, "BRK-B", "Hathaway Synthetic Inc"),
    (2002, "BRK-A", "Hathaway Synthetic Inc"),
    (2003, "GOOGL", "Alphabet Synthetic Inc."),
    (2003, "GOOG", "Alphabet Synthetic Inc."),
    (2004, "", "Tickerless Trust"),
    (2005, "AB-CD", "First Dash Corp"),  # not a share-class notation
    (2006, "AB.CD", "Second Dot Corp"),
    (2007, "XY-Z", "Class Hyphen Corp"),  # one share class, written both ways
    (2008, "XY.Z", "Class Dot Corp"),
    (2009, "DUP", "Dup Alpha Corp"),  # one ticker on two rows
    (2010, "DUP", "Dup Beta Corp"),
]


def tickers(results: list[dict]) -> list[str]:
    return [row["ticker"] for row in results]


# ── boundaries ───────────────────────────────────────────────────────────────

_MISSING = object()


class World:
    """Every boundary identify() can reach; closed unless a test opens it."""

    def __init__(self) -> None:
        self.returns: dict[str, object] = {}
        self.calls: list[tuple[str, object]] = []
        self.unexpected: list[str] = []
        self.dart = self.edgar = self.fetcher_module = self.DataFetcher = None

    def closed(self, name: str):
        def boundary(*args, **kwargs):
            value = self.returns.get(name, _MISSING)
            if value is _MISSING:
                # recorded as well as raised: _identify_kr / _identify_us
                # swallow exceptions, the fixture checks this list at teardown
                self.unexpected.append(name)
                raise AssertionError(f"unexpected call: {name}")
            self.calls.append((name, args[0] if args else None))
            return value(*args, **kwargs) if callable(value) else value

        return boundary

    def count(self, name: str) -> int:
        return sum(1 for called, _ in self.calls if called == name)

    def open_registry(self, rows=REGISTRY) -> None:
        self.returns["dart._load_corp_code_xml"] = lambda: registry(rows)
        self.returns["yf.resolve_kr_ticker"] = lambda code: f"{code}.KS"
        self.returns["yf.get_exchange_segment"] = lambda code: "KOSPI"

    def open_edgar(self, rows=EDGAR) -> None:
        data = {
            str(index): {"cik_str": cik, "ticker": ticker, "title": title}
            for index, (cik, ticker, title) in enumerate(rows)
        }

        class Response:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return data

        self.returns["edgar.get"] = lambda url, *args, **kwargs: Response()
        self.returns["yahoo.get_stock_info"] = {
            "exchange": "NMS",
            "exchange_code": "NMS",
        }
        self.returns["yf.fetch_market_data"] = {"industry": "Synthetic"}


class _Guard:
    """Stands in for ApiGuard: no usage file, no circuit state, no retries."""

    class _Config:
        max_retries = 0
        retryable_codes = ()
        base_delay = 0.0
        max_delay = 0.0

    def _get_config(self, provider):
        return self._Config

    def check(self, provider) -> None:
        pass

    def record_success(self, provider) -> None:
        pass

    def record_failure(self, provider, exc) -> None:
        pass

    def record_cache_hit(self, provider) -> None:
        pass


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
def world(env_guard, monkeypatch):
    monkeypatch.setenv("BVT_TELEMETRY", "0")
    # pipeline/yfinance_fetcher.py sets this at import time whenever the certifi
    # path is not ASCII, whatever the current value. Pre-seed the very value it
    # would write, so that monkeypatch restores the original state afterwards.
    ca_bundle = os.path.join(
        os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData"), "python-ssl", "cacert.pem"
    )
    monkeypatch.setenv("CURL_CA_BUNDLE", os.environ.get("CURL_CA_BUNDLE") or ca_bundle)
    try:
        import dotenv
    except ImportError:
        dotenv = None
    if dotenv is not None:
        monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)

    # Only now the modules under test: nothing of pipeline/ is imported at the
    # top of this file.
    w = World()
    w.dart = importlib.import_module("pipeline.dart_client")
    w.edgar = importlib.import_module("pipeline.edgar_client")
    w.fetcher_module = importlib.import_module("pipeline.data_fetcher")
    w.DataFetcher = w.fetcher_module.DataFetcher
    yahoo = importlib.import_module("pipeline.yahoo_finance")
    edinet = importlib.import_module("pipeline.edinet_client")

    guard = _Guard()
    monkeypatch.setattr(
        "pipeline.api_guard.ApiGuard.get", classmethod(lambda cls: guard)
    )
    monkeypatch.setattr(
        w.dart, "_load_corp_code_xml", w.closed("dart._load_corp_code_xml")
    )

    class Client:
        get = staticmethod(w.closed("edgar.get"))

    monkeypatch.setattr(w.edgar, "_client", Client())
    for name in ("get_stock_info", "get_quote_summary"):
        monkeypatch.setattr(yahoo, name, w.closed(f"yahoo.{name}"))
    monkeypatch.setattr(edinet, "get_edinet_code", w.closed("edinet.get_edinet_code"))
    if w.fetcher_module.yfinance_fetcher is not None:
        for name in (
            "resolve_kr_ticker",
            "get_exchange_segment",
            "fetch_market_data",
            "fetch_financials",
        ):
            monkeypatch.setattr(
                w.fetcher_module.yfinance_fetcher, name, w.closed(f"yf.{name}")
            )

    yield w

    assert w.unexpected == [], f"un-mocked boundary was reached: {w.unexpected}"


@pytest.fixture
def kr(world):
    world.open_registry()
    return world


@pytest.fixture
def us(world):
    world.open_edgar()
    return world


# ── 1. the registry: a registered name and the selected stock code ───────────


@pytest.mark.parametrize(
    "name, code",
    [
        # the name as it is registered, Korean or English
        ("삼성전자", "005930"),
        ("SAMSUNG ELECTRONICS CO,.LTD", "005930"),
        ("sk  hynix inc.", "000660"),  # case and spacing aside
        ("OCI", "456040"),
        ("JS Corporation", "194370"),
        ("SG", "255220"),
        ("sg corporation", "004060"),
        ("ALT Co.,Ltd.", "172670"),
        ("ALT Co., Ltd.", "459550"),  # registered with two blanks
        # two rows are registered as SK: the code picks
        ("SK", "034730"),
        ("SK", "003600"),
        # the same letters, punctuation aside
        ("JS Corporation.", "194370"),
        ("Samsung Electronics Co., Ltd.", "005930"),
        ("KT & G Corporation", "033780"),
        # ... and spacing aside: registered as "SewonCorporation". The key of
        # the selected name ("sewon") is the other company's, which is why
        # the letters are compared before the key.
        ("Sewon Corporation", "024830"),
        ("Sewon", "234100"),
        # the name with its legal form dropped or changed
        ("Samsung Electronics", "005930"),
        ("SK Hynix", "000660"),
        ("LG Electronics", "066570"),
        ("KT&G", "033780"),
        ("Hyundai Motor", "005380"),
        ("Hyundai Motor Company", "005380"),
        ("Samsung Epis Holdings", "0126Z0"),
        # nobody is registered as "JS" or "JS Corp"; two rows are JS + a legal
        # form, and the name does not say which: the code picks
        ("JS", "037110"),
        ("JS", "194370"),
        ("JS Corp", "037110"),
        ("JS Corp", "194370"),
        ("ALT", "459550"),
    ],
)
def test_registered_name_and_stock_code_agree(kr, name, code):
    assert kr.dart.get_corp_info(name, stock_code=code) == row_of(code)
    assert kr.count("dart._load_corp_code_xml") == 1


@pytest.mark.parametrize(
    "name, code, named",
    [
        # the name as registered belongs to another listing than the code
        ("JS Corporation", "037110", "194370"),  # 037110 is "JS Company Limited"
        ("SG Corporation", "255220", "004060"),  # 255220 is "SG CO., LTD."
        ("SG", "004060", "255220"),
        ("OCI", "010060", "456040"),  # 010060 is OCI홀딩스
        ("삼성전자", "000660", "005930"),
        ("SK", "000660", "034730"),  # two rows named SK: the newer one
        ("ALT Co.,Ltd.", "459550", "172670"),  # spacing tells the two ALTs apart
        ("ALT Co., Ltd.", "172670", "459550"),
        # a full stop more or less does not turn it into the other company
        ("JS Corporation.", "037110", "194370"),
        ("SG Corporation.", "255220", "004060"),
        # the letters are 세원물산's ("SewonCorporation"), the code 폴라리스세원's
        ("Sewon Corporation", "234100", "024830"),
        ("Sewon", "024830", "234100"),  # and the other way round, by the key
        # the same with the legal form dropped
        ("HD Hyundai", "011760", "267250"),  # 011760 is 현대코퍼레이션
        ("LG Electronics", "003550", "066570"),  # 003550 is LG
        ("SK Hynix", "999999", "000660"),  # nobody's code
        ("Samsung Electronics", "005935", "005930"),  # a preferred share's code
    ],
)
def test_name_registered_to_another_listing_comes_back_as_that_listing(
    kr, name, code, named
):
    # Name and code disagree. The company the name states comes back with its
    # own stock code; the caller that selected `code` rejects it.
    assert kr.dart.get_corp_info(name, stock_code=code) == row_of(named)


@pytest.mark.parametrize(
    "name, code, by_name",
    [
        # short or former names: the code is in the registry and is not used
        ("현대차", "005380", "001500"),  # the name lookup lands on 현대차증권
        ("Kia Motors", "000270", None),
        ("Hyundai Motor Group", "005380", None),
        ("KEPCO", "005930", None),
        # the exact namesake is unlisted and does not count as a registered name
        ("한빛", "047080", None),
        # nothing left of the name to compare; the blank English name of
        # 두리건설 is not "the same name"
        ("주식회사", "111110", None),
        (" ", "111110", None),
        ("", "111110", "005930"),  # an empty query "matches" every row, as before
        # a code the registry does not carry
        ("삼성전자우", "005935", "005930"),
        ("LG에너지", "373220", "003550"),
        ("Nowhere Corp", "999999", None),
        ("Samsung Electronics Pref", "005935", None),
    ],
)
def test_stock_code_alone_identifies_nothing(kr, name, code, by_name):
    with_code = kr.dart.get_corp_info(name, stock_code=code)

    assert stock(with_code) == by_name
    assert with_code == kr.dart.get_corp_info(name)  # the old name lookup, as it was


@pytest.mark.parametrize(
    "rows, name, expected",
    [
        # name and code agree on two rows: the most recently modified one
        ([("다", "111111", "", "20170630"), ("다", "111111", "", "20240101")], "다", 1),
        ([("다", "111111", "", "20240101"), ("다", "111111", "", "20170630")], "다", 0),
        # the same date: the one that comes first in the registry
        ([("다", "111111", "", "20240101"), ("다", "111111", "", "20240101")], "다", 0),
        # the name picks among rows that share a code
        ([("가", "111111", "", "20170630"), ("나", "111111", "", "20240101")], "가", 0),
        ([("가", "111111", "", "20170630"), ("나", "111111", "", "20240101")], "나", 1),
    ],
)
def test_several_rows_with_the_same_stock_code(world, rows, name, expected):
    world.open_registry(rows)

    info = world.dart.get_corp_info(name, stock_code="111111")

    assert info["corp_code"] == f"{expected:08d}"


@pytest.mark.parametrize(
    "name, code",
    [
        # Left as it was. These names are nobody's registered name, so the old
        # substring lookup answers -- and when the (wrong) selected code is the
        # very one that lookup lands on, the result carries the selected code.
        ("SK Hynix Semiconductor", "003600"),  # "SK" is inside the name
        ("현대차", "001500"),  # 현대차증권 contains the name
    ],
)
def test_a_partial_name_match_on_the_selected_code_still_comes_back(kr, name, code):
    assert kr.dart.get_corp_info(name, stock_code=code) == row_of(code)
    assert kr.dart.get_corp_info(name, stock_code=code) == kr.dart.get_corp_info(name)


def test_every_listing_is_found_by_its_own_names_and_never_by_anothers(kr):
    listed = [(i, row) for i, row in enumerate(REGISTRY) if row[1]]
    same_name_pairs = 0
    for index, (korean, code, english, _) in listed:
        for name in (korean, english):
            if not name.strip():
                continue
            assert kr.dart.get_corp_info(name, stock_code=code)["corp_code"] == (
                f"{index:08d}"
            ), (name, code)
            # ... and with the stock code of every other listing
            for other_index, (other_korean, other_code, other_english, _) in listed:
                if other_index == index:
                    continue
                found = kr.dart.get_corp_info(name, stock_code=other_code)
                if written(name) in (written(other_korean), written(other_english)):
                    # two rows registered under one name: the code picks
                    same_name_pairs += 1
                    assert found["corp_code"] == f"{other_index:08d}", (
                        name,
                        other_code,
                    )
                else:
                    assert stock(found) != other_code, (name, other_code)
    assert same_name_pairs == 2  # SK 003600 and SK 034730, each way


@pytest.mark.parametrize(
    "selected, registered",
    [
        ("SK Hynix", "SK hynix Inc."),
        ("Samsung Electronics", "SAMSUNG ELECTRONICS CO,.LTD"),
        ("samsung  electronics co., ltd.", "SAMSUNG ELECTRONICS CO,.LTD"),
        ("KT&G", "KT&G Corporation"),
        ("LS Corporation", "LS Corp."),
        ("LS Corporation", "LS"),
        (
            "Hyundai Engineering and Construction",
            "HYUNDAI ENGINEERING & CONSTRUCTION CO.,LTD",
        ),
        ("삼성전자 주식회사", "삼성전자"),
        ("(주)삼성전자", "삼성전자"),
        ("JS Corporation", "JS Company Limited"),  # why stricter comparisons go first
    ],
)
def test_names_that_compare_equal(world, selected, registered):
    key = world.dart._registered_name_key
    assert key(selected) == key(registered) != ""


@pytest.mark.parametrize(
    "selected, registered, same_letters",
    [
        ("JS Corporation.", "JS Corporation", True),
        ("Samsung Electronics Co., Ltd.", "SAMSUNG ELECTRONICS CO,.LTD", True),
        ("KT & G Corporation", "KT&G Corporation", True),
        ("Kakao Bank Corp", "KakaoBank Corp.", True),
        ("JS Corporation", "JS Company Limited", False),  # the legal form counts here
        ("JS Corp", "JS Corporation", False),
        ("Samsung Electronics", "SAMSUNG ELECTRONICS CO,.LTD", False),
        ("Sewon Corporation", "SewonCorporation", True),
        ("Sewon Corporation", "Sewon Co.,Ltd", False),
    ],
)
def test_names_with_the_same_letters(world, selected, registered, same_letters):
    letters = world.dart._name_letters
    assert (letters(selected) == letters(registered)) is same_letters


def test_same_letters_do_not_imply_the_same_key(world):
    # A legal-form word is dropped only where it stands as a word of its own.
    # So the two comparisons can point at different companies, and the
    # stricter one is asked first.
    letters, key = world.dart._name_letters, world.dart._registered_name_key

    assert letters("Sewon Corporation") == letters("SewonCorporation")
    assert key("Sewon Corporation") == key("Sewon Co.,Ltd") == "sewon"
    assert key("SewonCorporation") == "sewoncorporation"


@pytest.mark.parametrize(
    "selected, registered",
    [
        ("OCI", "OCI Holdings Company Ltd."),
        ("HD Hyundai", "HYUNDAI CORPORATION"),
        ("현대차", "현대자동차"),
        ("Kia Motors", "KIA CORPORATION"),
        ("KB Financial", "KB Financial Group Inc."),
        ("Samsung Electronics", "SAMSUNG ELECTRONICS SALES CO., LTD."),
    ],
)
def test_names_that_compare_different(world, selected, registered):
    key = world.dart._registered_name_key
    assert key(selected) != key(registered)


@pytest.mark.parametrize("name", ["", "  ", "Co., Ltd.", "주식회사", "(주)", "?!"])
def test_a_name_with_nothing_to_compare_has_an_empty_key(world, name):
    assert world.dart._registered_name_key(name) == ""


# ── 2. the registry, asked by name only: unchanged ───────────────────────────

NAME_ONLY = [
    ("삼성전자", {"corp_code": "00000000", "stock_code": "005930", "is_listed": True}),
    (
        "케이티앤지",
        {"corp_code": "00000012", "stock_code": "033780", "is_listed": True},
    ),
    ("삼성전자판매", {"corp_code": "00000013", "stock_code": None, "is_listed": False}),
    ("한빛", {"corp_code": "00000014", "stock_code": None, "is_listed": False}),
    # Pinned as they are, not as they should be: the name lookup is out of
    # scope here and its known misses are left for a follow-up.
    ("SK", {"corp_code": "00000001", "stock_code": "003600", "is_listed": True}),
    ("현대차", {"corp_code": "00000007", "stock_code": "001500", "is_listed": True}),
    ("SK Hynix", {"corp_code": "00000001", "stock_code": "003600", "is_listed": True}),
    (
        "SK Hynix Semiconductor",
        {"corp_code": "00000001", "stock_code": "003600", "is_listed": True},
    ),
    (
        "LG Electronics",
        {"corp_code": "00000004", "stock_code": "003550", "is_listed": True},
    ),
    (
        "SG Corporation",
        {"corp_code": "00000020", "stock_code": "255220", "is_listed": True},
    ),
    ("Samsung Electronics", None),
    ("JS Corporation", None),
    ("Nowhere Corp", None),
]


@pytest.mark.parametrize("name, expected", NAME_ONLY)
def test_name_only_lookup_is_what_it_was(kr, name, expected):
    # characterization: passes before and after the change
    info = kr.dart.get_corp_info(name)

    assert info == expected
    if expected is not None:
        assert list(info) == ["corp_code", "stock_code", "is_listed"]
    assert kr.dart.get_corp_code(name) == (expected or {}).get("corp_code")


@pytest.mark.parametrize("name, expected", NAME_ONLY)
def test_no_stock_code_is_the_name_only_lookup(kr, name, expected):
    assert kr.dart.get_corp_info(name, stock_code=None) == expected
    assert kr.dart.get_corp_info(name, stock_code="") == expected


# ── 3. DataFetcher.identify() for KR ─────────────────────────────────────────


def test_identify_kr_with_the_selected_ticker(kr):
    identity = kr.DataFetcher().identify(
        "Samsung Electronics", market_hint="KR", ticker="005930"
    )

    assert (identity.name, identity.market) == ("Samsung Electronics", "KR")
    assert (identity.ticker, identity.corp_code) == ("005930", "00000000")
    assert identity.legal_status == "상장"
    if kr.fetcher_module.yfinance_fetcher is not None:
        assert identity.exchange_segment == "KOSPI"
    assert kr.count("dart._load_corp_code_xml") == 1


@pytest.mark.parametrize(
    "name, ticker, resolved",
    [
        ("SK Hynix", "000660", "000660"),
        ("SK Hynix", " 000660 ", "000660"),
        ("SK Hynix", "000660.KS", "000660"),
        ("SK Hynix", "000660.kq", "000660"),
        ("Samsung Epis Holdings", "0126z0", "0126Z0"),  # the newer alphanumeric codes
    ],
)
def test_identify_kr_accepts_the_usual_notations(kr, name, ticker, resolved):
    identity = kr.DataFetcher().identify(name, market_hint="KR", ticker=ticker)

    assert identity.ticker == resolved


class Unprintable:
    """A ticker that is not a string must not be turned into one."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    def __str__(self) -> str:
        self.asked.append("str")
        raise ValueError("__str__ failed")

    def __repr__(self) -> str:
        self.asked.append("repr")
        raise ValueError("__repr__ failed")


@pytest.mark.parametrize(
    "ticker",
    [
        None,
        "",
        "   ",
        "AAPL",
        "12345",
        "0059300",
        "A05930",
        "005930.T",
        # the selection check folds .KS only on six digits, so this notation
        # would be rejected there even when the lookup found the company
        "0126Z0.KS",
        # digits, but not the ASCII ones the registry writes its codes in
        "００５９３０",
        "00593０",
        "٠٠٥٩٣٠.KS",
        5930,
        5930.0,
        float("nan"),
        Decimal("NaN"),
        ["005930"],
        pytest.param(Unprintable(), id="unprintable"),
    ],
)
def test_identify_kr_without_a_usable_ticker_is_the_name_lookup(kr, ticker):
    fetcher = kr.DataFetcher()

    # the same answers as before: no English name, the Korean name as stated
    assert (
        fetcher.identify("Samsung Electronics", market_hint="KR", ticker=ticker) is None
    )
    assert (
        fetcher.identify("삼성전자", market_hint="KR", ticker=ticker).ticker == "005930"
    )
    assert (
        fetcher.identify("SK Hynix", market_hint="KR", ticker=ticker).ticker == "003600"
    )
    if isinstance(ticker, Unprintable):
        assert ticker.asked == []


def test_identify_kr_returns_the_named_company_when_the_code_is_anothers(kr):
    # What auto_fetch() then blocks: selected 011760, resolved 267250.
    identity = kr.DataFetcher().identify(
        "HD Hyundai", market_hint="KR", ticker="011760"
    )

    assert (identity.ticker, identity.corp_code) == ("267250", "00000009")


def test_identify_without_a_market_hint_passes_the_ticker_on(kr, us):
    fetcher = kr.DataFetcher()

    # English name: EDGAR is asked first and has no such name or ticker
    assert fetcher.identify("Samsung Electronics", ticker="005930").ticker == "005930"
    assert (kr.count("edgar.get"), kr.count("dart._load_corp_code_xml")) == (1, 1)
    assert fetcher.identify("삼성전자", ticker="005930").corp_code == "00000000"
    assert (kr.count("edgar.get"), kr.count("dart._load_corp_code_xml")) == (1, 2)


def test_identify_without_a_market_hint_stops_where_the_ticker_is_found(kr, us):
    # Without a hint EDGAR is asked first and DART only when EDGAR has nothing.
    # "BRK.B" was not found there before (EDGAR writes BRK-B), so the registry
    # was read as well; with the selected ticker EDGAR answers and it is not.
    identity = kr.DataFetcher().identify("BRK.B", ticker="BRK.B")

    assert (identity.market, identity.ticker) == ("US", "BRK-B")
    assert (kr.count("edgar.get"), kr.count("dart._load_corp_code_xml")) == (1, 0)


def test_identify_without_a_market_hint_and_ticker_is_what_it_was(kr, us):
    # characterization: passes before and after the change
    assert kr.DataFetcher().identify("BRK.B") is None
    assert (kr.count("edgar.get"), kr.count("dart._load_corp_code_xml")) == (1, 1)


def test_lookups_with_a_ticker_stay_out_of_the_cache(kr):
    fetcher = kr.DataFetcher()

    assert fetcher.identify("SK", market_hint="KR", ticker="034730").ticker == "034730"
    assert fetcher.identify("SK", market_hint="KR").ticker == "003600"
    assert fetcher.identify("SK", market_hint="KR", ticker="034730").ticker == "034730"
    assert fetcher.identify("SK", market_hint="KR").ticker == "003600"  # from the cache
    # a query that merely looks like "name:ticker" is its own name-only lookup
    assert fetcher.identify("SK:034730", market_hint="KR").ticker == "003600"
    assert fetcher.identify("SK", market_hint="KR", ticker="003600").ticker == "003600"

    assert kr.count("dart._load_corp_code_xml") == 5
    assert sorted(fetcher._cache) == ["id:KR:SK", "id:KR:SK:034730"]


def test_name_only_answers_do_not_depend_on_the_order_of_calls(kr):
    first_named = kr.DataFetcher()
    first_tickered = kr.DataFetcher()

    by_name = first_named.identify("SK Hynix", market_hint="KR")
    first_named.identify("SK Hynix", market_hint="KR", ticker="000660")
    first_tickered.identify("SK Hynix", market_hint="KR", ticker="000660")
    after_ticker = first_tickered.identify("SK Hynix", market_hint="KR")

    assert (by_name.ticker, after_ticker.ticker) == ("003600", "003600")
    assert first_named.identify("SK Hynix", market_hint="KR") is by_name


def test_identify_without_ticker_is_what_it_was(kr, us):
    # characterization: passes before and after the change
    fetcher = kr.DataFetcher()

    assert fetcher.identify("Samsung Electronics", market_hint="KR") is None
    identity = fetcher.identify("삼성전자", market_hint="KR")
    assert (
        identity.name,
        identity.ticker,
        identity.corp_code,
        identity.legal_status,
    ) == (
        "삼성전자",
        "005930",
        "00000000",
        "상장",
    )
    unlisted = fetcher.identify("삼성전자판매", market_hint="KR")
    assert (unlisted.ticker, unlisted.legal_status) == (None, "비상장")
    # the first name that contains "on", not the company whose ticker is ON
    american = fetcher.identify("ON", market_hint="US")
    assert (american.ticker, american.cik) == ("ONW0", "1000")


def test_identify_jp_is_what_it_was(world):
    # characterization: the JP path takes no ticker and is not touched
    world.returns["edinet.get_edinet_code"] = lambda code: "E02144"
    world.returns["yf.fetch_market_data"] = {
        "name": "Synthetic Motor",
        "industry": "Autos",
    }

    identity = world.DataFetcher().identify("7203", market_hint="JP")

    assert (identity.name, identity.market, identity.ticker) == (
        "Synthetic Motor",
        "JP",
        "7203.T",
    )
    assert identity.edinet_code == "E02144"


def test_identify_jp_ignores_a_selected_ticker(world):
    world.returns["edinet.get_edinet_code"] = lambda code: "E02144"
    world.returns["yf.fetch_market_data"] = {
        "name": "Synthetic Motor",
        "industry": "Autos",
    }

    identity = world.DataFetcher().identify("7203", market_hint="JP", ticker="7203.T")

    assert (identity.ticker, identity.edinet_code) == ("7203.T", "E02144")


# ── 4. EDGAR ─────────────────────────────────────────────────────────────────


def test_search_company_without_ticker_is_what_it_was(us):
    # characterization: passes before and after the change.
    # Ten names that contain "on"; the company whose ticker is ON is cut off.
    assert tickers(us.edgar.search_company("ON")) == [f"ONW{i}" for i in range(10)]
    assert tickers(us.edgar.search_company("alphabet")) == ["GOOGL", "GOOG"]
    assert tickers(us.edgar.search_company("GOOG")) == ["GOOG"]
    assert tickers(us.edgar.search_company("AB.CD")) == ["AB.CD"]
    assert us.edgar.search_company("BRK.B") == []


@pytest.mark.parametrize("query", ["ON", "alphabet", "GOOG", "BRK.B", "Tickerless"])
def test_search_company_with_no_ticker_given_is_the_same_list(us, query):
    by_name = us.edgar.search_company(query)

    assert us.edgar.search_company(query, ticker=None) == by_name
    assert us.edgar.search_company(query, ticker="") == by_name


def test_search_company_puts_the_selected_ticker_first(us):
    results = us.edgar.search_company("ON", ticker="ON")

    assert results[0] == {
        "cik": "2001",
        "ticker": "ON",
        "name": "Orbit Semiconductor Corp",
    }
    assert tickers(results) == ["ON", *[f"ONW{i}" for i in range(9)]]
    assert us.count("edgar.get") == 1


@pytest.mark.parametrize(
    "query, ticker, expected",
    [
        ("on", "on", ["ON", *[f"ONW{i}" for i in range(9)]]),
        # EDGAR writes a share class with a hyphen
        ("BRK.B", "BRK.B", ["BRK-B"]),
        ("BRK-B", "brk-b", ["BRK-B"]),
        # both classes of one CIK stay, the selected one first, no row twice
        ("alphabet", "GOOG", ["GOOG", "GOOGL"]),
        ("alphabet", "GOOGL", ["GOOGL", "GOOG"]),
        ("GOOGL", "GOOGL", ["GOOGL"]),
        # a dot is a hyphen only in the share-class notation
        ("AB.CD", "AB.CD", ["AB.CD"]),
        ("AB-CD", "AB-CD", ["AB-CD"]),
        ("Onward", "AB.CD", ["AB.CD", *[f"ONW{i}" for i in range(9)]]),
        # one class written both ways: the row spelled as selected
        ("XY.Z", "XY.Z", ["XY.Z"]),
        ("Onward", "XY.Z", ["XY.Z", *[f"ONW{i}" for i in range(9)]]),
        ("Onward", "XY-Z", ["XY-Z", *[f"ONW{i}" for i in range(9)]]),
        # the old result already starts with the selected class: left alone
        ("Class", "XY.Z", ["XY-Z", "XY.Z"]),
        # one ticker on two rows: both stay when the result already starts
        # with it; otherwise the first is moved up and only that row leaves
        # its old place
        ("Dup", "DUP", ["DUP", "DUP"]),
        ("Corp", "DUP", ["DUP", "ON", "AB-CD", "AB.CD", "XY-Z", "XY.Z", "DUP"]),
        # not in the list: nothing new is found
        ("ZZZZ", "ZZZZ", []),
        ("Onward", "ZZZZ", [f"ONW{i}" for i in range(10)]),
        # a row without a ticker is nobody's selected ticker
        ("Tickerless", "  ", [""]),
    ],
)
def test_search_company_ticker_rules(us, query, ticker, expected):
    assert tickers(us.edgar.search_company(query, ticker=ticker)) == expected


@pytest.mark.parametrize(
    "ticker",
    [
        "BRK.B",
        "BRK-B",
        "brk.b",
        " BRK . B ",
        "AB.CD",
        "AB-CD",
        "A.B",
        "ABCDEF.G",
        "GOOGL",
        "005930",
        "005930.KS",
        "005930.kq",
        "7203",
        "7203.T",
        "N/A",
        "0126Z0",
        "",  # no ticker: None in both
        "   ",
        # digits that are not ASCII: both normal forms take them for digits
        "００５９３０",
        "００５９３０.KS",
        "٠٠٥٩٣٠.kq",
        "７２０３.T",
    ],
)
def test_edgar_compares_tickers_as_the_selection_check_does(world, ticker):
    profile_generator = importlib.import_module("pipeline.profile_generator")

    assert world.edgar._ticker_key(ticker) == profile_generator._comparable_ticker(
        ticker
    )


@pytest.mark.parametrize(
    "ticker, code",
    [
        ("005930", "005930"),
        ("005930.ks", "005930"),
        (" 0126z0 ", "0126Z0"),
        ("0126Z0.KS", None),  # the selection check folds the suffix on six digits only
        ("００５９３０", None),  # a registry code is written in ASCII digits
        ("００５９３０.KS", None),
        ("٠٠٥٩٣٠", None),
    ],
)
def test_a_stock_code_for_the_registry_is_ascii(world, ticker, code):
    # On purpose narrower than the normal forms above, which fold any digits:
    # what is looked up must be a code a registry row can carry, and a
    # notation the selection check takes for that same code.
    profile_generator = importlib.import_module("pipeline.profile_generator")

    assert world.fetcher_module._kr_stock_code(ticker) == code
    if code is not None:
        assert profile_generator._comparable_ticker(
            ticker
        ) == profile_generator._comparable_ticker(code)


def test_identify_us_with_the_selected_ticker(us):
    identity = us.DataFetcher().identify("ON", market_hint="US", ticker="ON")

    assert (identity.name, identity.market) == ("Orbit Semiconductor Corp", "US")
    assert (identity.ticker, identity.cik) == ("ON", "2001")
    assert us.count("edgar.get") == 1


def test_identify_us_class_ticker(us):
    identity = us.DataFetcher().identify("BRK.B", market_hint="US", ticker="BRK.B")

    assert (identity.ticker, identity.cik) == ("BRK-B", "2002")


@pytest.mark.parametrize(
    "ticker",
    [None, "", "  ", 7, float("nan"), pytest.param(Unprintable(), id="unprintable")],
)
def test_identify_us_without_a_usable_ticker_is_the_name_search(us, ticker):
    identity = us.DataFetcher().identify("ON", market_hint="US", ticker=ticker)

    assert identity.ticker == "ONW0"
    if isinstance(ticker, Unprintable):
        assert ticker.asked == []
