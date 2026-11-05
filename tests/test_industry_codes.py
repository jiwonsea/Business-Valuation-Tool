"""Authoritative industry-code classification uses explicit system prefixes."""

import pytest

from engine.industry_codes import is_financial_code


def test_sic_bank_is_financial():
    from engine.industry_codes import is_financial_code

    assert is_financial_code("SIC:6021") is True


@pytest.mark.parametrize(
    "code, expected",
    [
        ("SIC:6000", True),
        ("SIC:6798", True),
        ("SIC:6799", True),
        ("SIC:5999", False),
        ("SIC:6800", False),
        ("SIC:3571", False),
        ("KSIC:64110", True),
        ("KSIC:65110", True),
        ("KSIC:66199", True),
        ("KSIC:26410", False),
        ("KSIC:264", False),
        ("KSIC:64992", True),
        (None, None),
        ("NAICS:5221", None),
        ("", None),
        ("SIC:", None),
        ("SIC:bank", None),
        ("6021", None),
    ],
)
def test_industry_code_table(code, expected):
    assert is_financial_code(code) is expected
