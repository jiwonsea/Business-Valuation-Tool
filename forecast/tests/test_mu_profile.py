"""MU (Micron) generic profile — EFE 2026-09 batch, target FQ4 FY2026 (14 weeks).

Pins the contracts the forecast depends on:
  1. actuals integrity (contiguity, FY ties, as-filed EPS/share counts);
  2. the FISCAL label contract of PREREG §5-b — implemented HERE, independent of
     forecast/pipeline/edgar_fetcher.model_label_for_period(), which mislabels
     FYE-August issuers (documented as a strict xfail below);
  3. the 53-week / 14-week normalisation of PLAN G0-B — no double correction;
  4. the regime break (2024Q1, PREREG LOCK d5918c8) and backtest integrity.

Values asserted here are SOURCE facts (filings), not model assumptions; every
scenario assumption lives in forecast/profiles/mu.generic.yaml.
본 테스트는 투자 자문이 아니다.
"""

from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from forecast.engine.generic_forecast import run_generic_forecast
from forecast.generic_cli import backtest_generic
from forecast.schemas.generic import GenericProfile

PROFILE_PATH = Path(__file__).resolve().parents[1] / "profiles" / "mu.generic.yaml"

# Source facts (8-K EX-99.1 annual columns and statements of operations).
FY_TIES = {  # fiscal year -> (revenue $M, net income $M)
    2024: (25111, 778),  # 0000723125-24-000023
    2025: (37378, 8539),  # 0000723125-25-000024
}
AS_FILED_EPS = [-1.12, 0.71, 0.30, 0.79, 1.67, 1.41, 1.68, 2.83, 4.60, 12.07, 24.67]
AS_FILED_Q4_DILUTED = {"2024Q4": 1_125_000_000, "2025Q4": 1_131_000_000}
DERIVED_Q4_DILUTED = {"2024Q4": 1_160_000_000, "2025Q4": 1_131_000_000}  # 4xFY - 3x9M
GUIDE_FQ4 = {"revenue_mid": 50000.0, "gaap_eps_mid": 30.73, "gaap_gm": 0.86, "gaap_opex": 1860.0}  # 0000723125-26-000013
TARGET_END = date(2026, 9, 3)
SEED_END = date(2026, 5, 28)


def _fiscal_label_aug(end: date) -> str:
    """PREREG §5-b: FY ends on the Thursday nearest Aug 31 (may be early Sept).

    Shift the period end back 7 days and read the month: Nov->Q1 (FY+1), Feb->Q2,
    May->Q3, Aug->Q4.
    """
    d = end - timedelta(days=7)
    quarter = {11: 1, 2: 2, 5: 3, 8: 4}.get(d.month)
    if quarter is None:
        raise ValueError(f"unexpected MU period end {end}")
    year = d.year + 1 if d.month == 11 else d.year
    return f"{year}Q{quarter}"


def _next(label: str) -> str:
    y, q = int(label[:4]), int(label[-1])
    return f"{y + 1}Q1" if q == 4 else f"{y}Q{q + 1}"


@pytest.fixture(scope="module")
def raw() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture(scope="module")
def profile(raw: dict) -> GenericProfile:
    return GenericProfile(**raw)


def _note(profile: GenericProfile, prefix: str) -> str:
    hits = [n for n in profile.notes if n.startswith(prefix)]
    assert len(hits) == 1, f"expected exactly one note starting with {prefix!r}"
    return hits[0]


def _floats(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", text)]


# ---------------------------------------------------------------------------
# 1. Actuals integrity
# ---------------------------------------------------------------------------


def test_actuals_are_the_locked_post_break_window(profile: GenericProfile) -> None:
    labels = [a.quarter_label for a in profile.actuals]
    assert profile.regime_break_quarter == "2024Q1"
    assert labels[0] == profile.regime_break_quarter  # break quarter included (PREREG §6)
    assert labels[-1] == profile.seed.quarter_label == "2026Q3"
    assert len(labels) == 11  # H = 11 (PANEL 7d68cf4)
    for prev, cur in zip(labels, labels[1:]):
        assert _next(prev) == cur, f"non-contiguous {prev} -> {cur}"


def test_every_actual_is_a_13_week_quarter(profile: GenericProfile) -> None:
    ends = [a.period_end for a in profile.actuals]
    for prev, cur in zip(ends, ends[1:]):
        assert (cur - prev).days == 91, f"{prev} -> {cur} is not 13 weeks"


@pytest.mark.parametrize("fy", sorted(FY_TIES))
def test_fiscal_year_sums_tie_to_filings(profile: GenericProfile, fy: int) -> None:
    rows = [a for a in profile.actuals if a.quarter_label.startswith(str(fy))]
    assert len(rows) == 4
    rev, ni = FY_TIES[fy]
    assert sum(a.revenue_total for a in rows) == pytest.approx(rev, abs=0.5)
    assert sum(a.net_profit for a in rows) == pytest.approx(ni, abs=0.5)


def test_derived_eps_reproduces_as_filed_eps(profile: GenericProfile) -> None:
    scale = 1_000_000  # USD_million
    for row, eps in zip(profile.actuals, AS_FILED_EPS):
        assert round(row.net_profit * scale / row.diluted_shares, 2) == pytest.approx(eps, abs=0.006), row.quarter_label


def test_q4_diluted_shares_are_as_filed_not_derived(profile: GenericProfile) -> None:
    by_label = {a.quarter_label: a for a in profile.actuals}
    for label, shares in AS_FILED_Q4_DILUTED.items():
        assert by_label[label].diluted_shares == shares
    # The 2024Q4 derivation is basis-mixed (9M loss -> antidilutive); it must not leak in.
    assert by_label["2024Q4"].diluted_shares != DERIVED_Q4_DILUTED["2024Q4"]


# ---------------------------------------------------------------------------
# 2. Label contract (PREREG §5-b)
# ---------------------------------------------------------------------------


def test_stored_labels_match_fiscal_contract(profile: GenericProfile) -> None:
    for row in profile.actuals:
        assert _fiscal_label_for(row) == row.quarter_label


def _fiscal_label_for(row) -> str:  # noqa: ANN001 - thin helper for readability
    return _fiscal_label_aug(row.period_end)


@pytest.mark.parametrize(
    ("end", "label"),
    [
        (date(2023, 11, 30), "2024Q1"),  # break quarter
        (date(2024, 11, 28), "2025Q1"),  # the quarter the buggy builder calls 2024Q1
        (date(2026, 5, 28), "2026Q3"),  # seed
        (TARGET_END, "2026Q4"),  # 53-week FY ends in September
        (date(2026, 12, 3), "2027Q1"),
        (date(2020, 9, 3), "2020Q4"),  # previous 53-week FY
    ],
)
def test_fiscal_label_contract_edge_cases(end: date, label: str) -> None:
    assert _fiscal_label_aug(end) == label


@pytest.mark.xfail(strict=True, reason="edgar_fetcher.model_label_for_period mislabels FYE-August Q1 (PANEL §6) — NOTICED BUT NOT TOUCHING")
def test_edgar_fetcher_label_function_agrees_with_contract() -> None:
    from forecast.pipeline.edgar_fetcher import model_label_for_period

    assert model_label_for_period(date(2023, 11, 30), 8) == "2024Q1"


# ---------------------------------------------------------------------------
# 3. 53-week / 14-week normalisation (PLAN G0-B)
# ---------------------------------------------------------------------------


def test_target_is_a_14_week_quarter(profile: GenericProfile) -> None:
    assert profile.window.start_quarter == _next(profile.seed.quarter_label) == "2026Q4"
    assert (TARGET_END - SEED_END).days == 98  # 14 weeks
    assert _fiscal_label_aug(TARGET_END) == profile.window.start_quarter


@pytest.mark.parametrize("scenario", ["bear", "base", "bull"])
def test_week_normalisation_has_no_double_correction(profile: GenericProfile, scenario: str) -> None:
    growth = getattr(profile, scenario).revenue_growth_qoq
    norm = _note(profile, f"WEEK_NORM {scenario}:")
    weeks = [int(x) for x in re.search(r"weeks=\[([^\]]+)\]", norm).group(1).split(",")]
    seed_weeks = int(re.search(r"seed_weeks=(\d+)", norm).group(1))
    g_week = _floats(re.search(r"g_week=\[([^\]]+)\]", norm).group(1))
    assert weeks == [14, 13, 13, 13] and seed_weeks == 13

    # Position 0 (FQ4): anchored on the 14w guidance -> raw is primary, NOT re-scaled.
    anchor = _note(profile, f"ANCHOR {scenario}:")
    guide_mid = float(re.search(r"guide_mid=([\d.]+)", anchor).group(1))
    beat = float(re.search(r"beat=(-?[\d.]+)", anchor).group(1))
    fq4_rev = float(re.search(r"fq4_rev=([\d.]+)", anchor).group(1))
    assert fq4_rev == pytest.approx(guide_mid * (1 + beat), rel=1e-6)  # notes store fq4_rev to 2dp
    assert profile.seed.revenue_total * (1 + growth[0]) == pytest.approx(fq4_rev, rel=1e-5)  # growth stored to 6 s.f.
    assert fq4_rev != pytest.approx(guide_mid * (1 + beat) * 14 / 13, rel=1e-3)
    assert g_week[0] == pytest.approx((1 + growth[0]) * seed_weeks / weeks[0] - 1, abs=1e-6)

    # Positions 1..3: per-week assumptions converted with the week ratio.
    prev_weeks = [weeks[0], weeks[1], weeks[2]]
    for i in (1, 2, 3):
        assert growth[i] == pytest.approx((1 + g_week[i]) * weeks[i] / prev_weeks[i - 1] - 1, abs=1e-6)


def test_base_reproduces_gaap_guidance_at_guidance_mid_revenue(raw: dict) -> None:
    """ALGEBRAIC RECONCILIATION, not independent validation: the base ETR is
    back-solved from this very identity (notes TAX_BASIS). The test only pins that
    the stored residual still closes the identity after edits."""
    probe = copy.deepcopy(raw)
    seed = probe["seed"]["revenue_total"]
    probe["base"]["revenue_growth_qoq"][0] = GUIDE_FQ4["revenue_mid"] / seed - 1
    probe["base"]["op_margin"][0] = GUIDE_FQ4["gaap_gm"] - GUIDE_FQ4["gaap_opex"] / GUIDE_FQ4["revenue_mid"]
    q0 = run_generic_forecast(GenericProfile(**probe)).scenarios_quarterly["base"][0]
    assert q0.eps_diluted == pytest.approx(GUIDE_FQ4["gaap_eps_mid"], abs=0.005)


# ---------------------------------------------------------------------------
# 4. Scenarios and backtest
# ---------------------------------------------------------------------------


def test_probabilities_sum_to_one(profile: GenericProfile) -> None:
    assert profile.bear.probability + profile.base.probability + profile.bull.probability == pytest.approx(1.0)


def test_fq4_ordering_bear_base_bull(profile: GenericProfile) -> None:
    q = {s: run_generic_forecast(profile).scenarios_quarterly[s][0] for s in ("bear", "base", "bull")}
    assert q["bear"].revenue_total < q["base"].revenue_total < q["bull"].revenue_total
    assert q["bear"].eps_diluted < q["base"].eps_diluted < q["bull"].eps_diluted
    assert all(v.quarter_label == "2026Q4" for v in q.values())


def test_backtest_runs_over_the_post_break_window(profile: GenericProfile) -> None:
    bt = backtest_generic(profile)
    assert bt["n"] == 10, bt.get("note")
    windows = bt["windows"]
    assert windows["post_break"]["n"] == 10  # revenue / net income one-step pairs
    assert windows["post_break"]["n_eps"] == 10  # EPS pairs on as-filed shares (PANEL §8)
    assert windows["pre_break"]["n"] == 0  # no pre-break quarter was collected


def test_backtest_is_immune_to_forward_scenario_edits(raw: dict) -> None:
    before = backtest_generic(GenericProfile(**raw))
    edited = copy.deepcopy(raw)
    for scenario in ("bear", "base", "bull"):
        edited[scenario]["revenue_growth_qoq"] = [0.5, 0.5, 0.5, 0.5]
        edited[scenario]["op_margin"] = 0.1
    after = backtest_generic(GenericProfile(**edited))
    assert after["windows"]["post_break"]["revenue_mape"] == before["windows"]["post_break"]["revenue_mape"]
    assert after["windows"]["post_break"]["eps_mape"] == before["windows"]["post_break"]["eps_mape"]


# ---------------------------------------------------------------------------
# 5. Methodology disclosures that must not silently disappear
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prefix", "must_contain"),
    [
        ("BACKTEST_IN_SAMPLE:", "NOT skill evidence"),
        ("TAX_BASIS:", "back-solved residual"),
        ("PROBABILITIES:", "NOT empirically calibrated"),
        ("CONSENSUS_PATH:", "REFUSED"),
        ("NONGAAP_BRIDGE:", "ASSUMPTION"),
    ],
)
def test_methodology_disclosure_notes_are_present(profile: GenericProfile, prefix: str, must_contain: str) -> None:
    assert must_contain in _note(profile, prefix)
