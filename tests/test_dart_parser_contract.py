"""Parser data-contract tests (Phase 2 gate, HANDOFF §7.2 — conditions 1-5).

Fixture provenance: tests/fixtures/dart_pilot_v2_subset.json is extracted
offline from research/pilot_v2/raw_payloads.json (DART snapshot 2026-07-18).
Zero new DART calls; real filing rows including the SCE hazard rows.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from pipeline.dart_parser import (
    ACCOUNT_ALIASES,
    ACCOUNT_MAP,
    CAPEX_ALIASES,
    CAPEX_MAP,
    STATEMENT_CONTRACT,
    AmbiguousAccountError,
    extract_reported_values,
    parse_financial_statements,
)
from schemas.point_in_time import (
    available_at_from_rcept_no,
    require_allowed_multiple_label,
    select_point_in_time,
)

FIXTURE = Path(__file__).parent / "fixtures" / "dart_pilot_v2_subset.json"


@pytest.fixture(scope="module")
def payloads() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ── §7.2-1: statement contract (SCE 혼입 차단) ──


class TestStatementContract:
    def test_contract_covers_every_mapped_key(self):
        keys = set(ACCOUNT_MAP.values()) | set(CAPEX_MAP.values())
        assert keys == set(STATEMENT_CONTRACT), (
            "every mappable internal key must declare its allowed statements"
        )

    def test_sce_net_income_rows_are_never_candidates(self, payloads):
        # Real SK hynix FY2019 filing: SCE carries its own 당기순이익 rows,
        # including a non-controlling-interest-only line of 3,103 MKRW.
        items = payloads["sk_hynix_fy2019"]
        sce_values = {
            r["thstrm_amount"]
            for r in items
            if r["sj_div"] == "SCE" and ACCOUNT_MAP.get(r["account_nm"]) == "net_income"
        }
        assert sce_values, "fixture must retain the SCE hazard rows"

        result = parse_financial_statements(items, 2019)
        assert result["net_income"] == 2_016_391  # CIS value, MKRW

    def test_sce_first_row_order_does_not_flip_selection(self, payloads):
        # Pre-contract, payload row order (CIS before SCE) protected the result
        # by accident. The contract must protect it regardless of order.
        items = payloads["sk_hynix_fy2019"]
        reordered = [r for r in items if r["sj_div"] == "SCE"] + [
            r for r in items if r["sj_div"] != "SCE"
        ]
        result = parse_financial_statements(reordered, 2019)
        assert result["net_income"] == 2_016_391

    def test_row_in_disallowed_statement_is_dropped_not_taken(self):
        # revenue is IS·CIS only — an SCE-only candidate must yield a gap,
        # never a silently accepted number.
        items = [
            {
                "account_nm": "매출액",
                "sj_div": "SCE",
                "thstrm_amount": "1,000,000,000",
                "rcept_no": "20240101000001",
            }
        ]
        result = parse_financial_statements(items, 2023)
        assert "revenue" not in result


# ── §7.2-2: priority + ambiguity fail-closed ──


class TestSelectionPriority:
    def test_is_outranks_cis(self):
        items = [
            {
                "account_nm": "영업이익",
                "sj_div": "CIS",
                "thstrm_amount": "2,000,000,000",
            },
            {
                "account_nm": "영업이익",
                "sj_div": "IS",
                "thstrm_amount": "1,000,000,000",
            },
        ]
        # Different statements, different values: NOT ambiguous — contract
        # order (IS first) decides deterministically.
        result = parse_financial_statements(items, 2023)
        assert result["op"] == 1_000  # IS row, MKRW

    def test_identical_same_statement_duplicates_pass(self):
        items = [
            {
                "account_nm": "당기순이익",
                "sj_div": "CIS",
                "thstrm_amount": "1,000,000,000",
            },
            {
                "account_nm": "당기순이익(손실)",
                "sj_div": "CIS",
                "thstrm_amount": "1,000,000,000",
            },
        ]
        result = parse_financial_statements(items, 2023)
        assert result["net_income"] == 1_000

    def test_conflicting_same_statement_candidates_fail_closed(self):
        items = [
            {
                "account_nm": "당기순이익",
                "sj_div": "CIS",
                "thstrm_amount": "1,000,000,000",
            },
            {
                "account_nm": "당기순이익(손실)",
                "sj_div": "CIS",
                "thstrm_amount": "2,000,000,000",
            },
        ]
        with pytest.raises(AmbiguousAccountError):
            parse_financial_statements(items, 2023)

    def test_extract_reported_values_is_also_fail_closed(self):
        items = [
            {
                "account_nm": "당기순이익",
                "sj_div": "CIS",
                "thstrm_amount": "1,000,000,000",
                "rcept_no": "20240101000001",
            },
            {
                "account_nm": "당기순이익(손실)",
                "sj_div": "CIS",
                "thstrm_amount": "2,000,000,000",
                "rcept_no": "20240101000001",
            },
        ]
        with pytest.raises(AmbiguousAccountError):
            extract_reported_values(items, 2023)


# ── §7.2-3: alias registry + cross-year fixture ──


class TestAliasRegistry:
    def test_derived_maps_match_registry(self):
        assert ACCOUNT_MAP == {
            alias: key for key, aliases in ACCOUNT_ALIASES.items() for alias in aliases
        }
        assert CAPEX_MAP == {alias: "capex" for alias in CAPEX_ALIASES}

    def test_alias_drift_across_years_maps_to_same_key(self, payloads):
        # Real LG filings: FY2020 uses 영업이익, FY2021 uses 영업이익(손실) —
        # the registry must make the series continuous.
        r2020 = parse_financial_statements(payloads["lg_fy2020"], 2020)
        r2021 = parse_financial_statements(payloads["lg_fy2021"], 2021)
        assert r2020["op"] == 3_194_987
        assert r2021["op"] == 3_863_774

    def test_matched_spelling_is_recorded_in_provenance(self, payloads):
        values = extract_reported_values(payloads["lg_fy2021"], 2021)
        op_2021 = [v for v in values if v.account == "op" and v.basis == "original"]
        assert len(op_2021) == 1
        assert op_2021[0].account_nm == "영업이익(손실)"


# ── §7.2-4: original vs restated preserved separately ──


class TestBasisSeparation:
    def test_following_filing_yields_both_bases_distinctly(self, payloads):
        # The FY2021 LG filing restated FY2020 op (3,194,987 -> 3,905,108,
        # MC-business discontinued-operations reclassification; pilot v2
        # conflict table). Both values must survive, on separate bases.
        vals_2020 = extract_reported_values(payloads["lg_fy2020"], 2020)
        vals_2021 = extract_reported_values(payloads["lg_fy2021"], 2021)

        original = [
            v for v in vals_2020 if v.account == "op" and v.fiscal_year == 2020
        ][0]
        restated = [
            v for v in vals_2021 if v.account == "op" and v.fiscal_year == 2020
        ][0]

        assert original.basis == "original"
        assert original.value_mkrw == 3_194_987
        assert restated.basis == "restated_comparative"
        assert restated.value_mkrw == 3_905_108
        # available_at follows each filing's own receipt date
        assert original.available_at == date(2021, 3, 16)
        assert restated.available_at == date(2022, 3, 16)

    def test_reported_value_is_frozen(self, payloads):
        v = extract_reported_values(payloads["lg_fy2020"], 2020)[0]
        with pytest.raises(Exception):
            v.value_mkrw = 0  # Pydantic frozen — mutate via model_copy only

    def test_missing_rcept_no_fails_closed(self):
        items = [
            {"account_nm": "매출액", "sj_div": "IS", "thstrm_amount": "1,000,000,000"}
        ]
        with pytest.raises(ValueError):
            extract_reported_values(items, 2023)


# ── §7.2-5: point-in-time rules ──


class TestPointInTime:
    @pytest.fixture()
    def series(self, payloads):
        return extract_reported_values(
            payloads["lg_fy2020"], 2020
        ) + extract_reported_values(payloads["lg_fy2021"], 2021)

    def test_uses_first_disclosure_only(self, series):
        # Even after the restating filing exists, point-in-time keeps the
        # original disclosure for FY2020.
        picked = select_point_in_time(series, "op", 2020, date(2022, 6, 30))
        assert picked is not None
        assert picked.basis == "original"
        assert picked.value_mkrw == 3_194_987

    def test_no_lookahead_before_filing_date(self, series):
        # FY2020 annual report was received 2021-03-16; before that the value
        # did not exist for any evaluator.
        assert select_point_in_time(series, "op", 2020, date(2021, 3, 15)) is None
        assert select_point_in_time(series, "op", 2020, date(2021, 3, 16)) is not None

    def test_missing_stays_missing(self, series):
        # No FY2019 observation in this set -> None, never interpolated.
        assert select_point_in_time(series, "op", 2019, date(2026, 1, 1)) is None

    def test_available_at_from_rcept_no(self):
        assert available_at_from_rcept_no("20210316000661") == date(2021, 3, 16)
        for bad in ("", "2021-03-16", "20210316", "abcdefgh123456"):
            with pytest.raises(ValueError):
                available_at_from_rcept_no(bad)

    def test_multiple_scope_ltm_only(self):
        assert require_allowed_multiple_label("P/B") == "P/B"
        assert require_allowed_multiple_label("P/S") == "P/S"
        for forbidden in ("12M Forward P/E", "Forward P/S", "P/E", "FY27E P/S"):
            with pytest.raises(ValueError):
                require_allowed_multiple_label(forbidden)


# ── Regression guard: contract change must not shift the pilot v2 baseline ──

SNAPSHOT = Path(__file__).parent.parent / "research" / "pilot_v2" / "raw_payloads.json"


@pytest.mark.skipif(not SNAPSHOT.exists(), reason="pilot v2 snapshot not present")
def test_full_snapshot_parity_with_pre_contract_selection():
    """Across all 30 real payloads the contract changes no selected value.

    The pilot v2 conflict analysis (17/17 restatement, 0 parser defects) was
    measured under first-match semantics; the contract must formalize — not
    alter — those selections. Reference below reproduces the pre-contract
    first-match loop byte-for-byte.
    """
    from pipeline.dart_parser import _to_millions

    core = (
        "revenue",
        "op",
        "net_income",
        "interest_expense",
        "assets",
        "liabilities",
        "equity",
        "capex",
    )

    def pre_contract(items):
        res, capex = {}, None
        for it in items:
            nm = it.get("account_nm", "")
            key = ACCOUNT_MAP.get(nm)
            if key and key not in res:
                res[key] = _to_millions(it.get("thstrm_amount", ""))
            if capex is None and nm in CAPEX_MAP:
                capex = _to_millions(it.get("thstrm_amount", ""))
        if capex is not None:
            res["capex"] = abs(capex)
        return res

    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    checked = 0
    for blob in snap["companies"].values():
        for year, fin in blob["financial"].items():
            items = fin.get("items")
            if items is None:
                continue
            new = parse_financial_statements(items, int(year))
            old = pre_contract(items)
            for key in core:
                assert new.get(key) == old.get(key), (key, year)
            checked += 1
    assert checked == 30
