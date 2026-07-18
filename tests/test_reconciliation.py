"""Cross-source reconciliation tests (Workstream BVT-1 / A4).

Covers: relative-diff convention, per-check thresholds (shares 25% /
market cap 25% / unit 100%), warn-by-default orchestration, graceful skips,
and the profile_generator hard-block integration with a synthetic 2x-shares
fixture.
"""

import yaml

import pipeline.profile_generator as pg
from pipeline.data_fetcher import CompanyIdentity
from pipeline.reconciliation import (
    Finding,
    ReconciliationReport,
    check_market_cap,
    check_share_count,
    check_unit_consistency,
    reconcile_market_data,
    relative_diff,
)


# ═══════════════════════════════════════════════════════════
# Synthetic fixtures (million KRW / raw share counts)
# ═══════════════════════════════════════════════════════════

PRICE = 100_000.0  # KRW
TRUE_SHARES = 70_000_000
MARKET_CAP = PRICE * TRUE_SHARES  # 7,000,000,000,000 KRW (raw)
# fetch_shares() emits market_cap in 백만원 / $M, NOT raw currency
# (pipeline/yfinance_fetcher.py divides marketCap by 1e6). The fixture must
# mirror that contract -- the old raw-unit fixture is what let the ~1e6x
# reconciliation bug ship (every auto-fetched profile hard-blocked).
MARKET_CAP_M = MARKET_CAP / 1_000_000  # 7,000,000 백만원


def make_financials(**overrides) -> dict:
    cons = {
        "revenue": 10_000_000,
        "op": 1_000_000,
        "net_income": 800_000,
        "assets": 20_000_000,
        "liabilities": 12_000_000,
        "equity": 8_000_000,
        "dep": 500_000,
        "amort": 100_000,
        "gross_borr": 5_000_000,
        "net_borr": 4_000_000,
        "de_ratio": 62.5,
        "capex": 700_000,
    }
    cons.update(overrides)
    return {2025: cons}


def make_shares_info(shares_total: int = TRUE_SHARES, **overrides) -> dict:
    info = {
        "shares_total": shares_total,
        "shares_ordinary": shares_total,
        "shares_preferred": 0,
        "treasury_shares": 0,
        "price": PRICE,
        "market_cap": MARKET_CAP_M,
        "currency": "KRW",
        "beta": 1.1,
    }
    info.update(overrides)
    return info


# ═══════════════════════════════════════════════════════════
# relative_diff
# ═══════════════════════════════════════════════════════════


class TestRelativeDiff:
    def test_equal_values(self):
        assert relative_diff(100.0, 100.0) == 0.0

    def test_two_x_is_100_pct(self):
        assert relative_diff(200.0, 100.0) == 1.0
        assert relative_diff(100.0, 200.0) == 1.0  # symmetric

    def test_25_pct(self):
        assert abs(relative_diff(125.0, 100.0) - 0.25) < 1e-12

    def test_missing_or_nonpositive_returns_none(self):
        assert relative_diff(None, 100.0) is None
        assert relative_diff(100.0, None) is None
        assert relative_diff(0.0, 100.0) is None
        assert relative_diff(-5.0, 100.0) is None


# ═══════════════════════════════════════════════════════════
# Individual checks
# ═══════════════════════════════════════════════════════════


class TestCheckShareCount:
    def test_exact_match_ok(self):
        f = check_share_count(TRUE_SHARES, TRUE_SHARES)
        assert f is not None and f.severity == "ok"

    def test_within_block_threshold_warns(self):
        # 15% mismatch: above warn floor (10%), below block line (25%)
        f = check_share_count(TRUE_SHARES * 1.15, TRUE_SHARES)
        assert f.severity == "warn"

    def test_2x_mismatch_blocks(self):
        f = check_share_count(TRUE_SHARES * 2, TRUE_SHARES)
        assert f.severity == "block"
        assert f.rel_diff_pct == 100.0

    def test_just_above_25_pct_blocks(self):
        f = check_share_count(TRUE_SHARES * 1.26, TRUE_SHARES)
        assert f.severity == "block"

    def test_exactly_25_pct_does_not_block(self):
        # Threshold is strict-greater: 25.0% stays a warning
        f = check_share_count(TRUE_SHARES * 1.25, TRUE_SHARES)
        assert f.severity == "warn"

    def test_missing_side_skips(self):
        assert check_share_count(None, TRUE_SHARES) is None
        assert check_share_count(TRUE_SHARES, None) is None


class TestCheckMarketCap:
    def test_match_ok(self):
        f = check_market_cap(MARKET_CAP, MARKET_CAP * 1.01)
        assert f.severity == "ok"

    def test_30_pct_blocks(self):
        f = check_market_cap(MARKET_CAP * 1.30, MARKET_CAP)
        assert f.severity == "block"

    def test_missing_skips(self):
        assert check_market_cap(None, MARKET_CAP) is None
        assert check_market_cap(0, MARKET_CAP) is None


class TestCheckUnitConsistency:
    def test_equal_ok(self):
        f = check_unit_consistency(
            10_000_000, 10_000_000, "revenue", 2025, "yfinance", "DART"
        )
        assert f.severity == "ok"

    def test_30_pct_warns_not_blocks(self):
        # Unit check blocks only above 100%
        f = check_unit_consistency(
            13_000_000, 10_000_000, "revenue", 2025, "yfinance", "DART"
        )
        assert f.severity == "warn"

    def test_million_vs_raw_blocks(self):
        # Classic unit error: one source in millions, the other raw
        f = check_unit_consistency(
            10_000_000, 10_000_000_000_000, "revenue", 2025, "yfinance", "DART"
        )
        assert f.severity == "block"

    def test_missing_skips(self):
        assert (
            check_unit_consistency(None, 10, "op", 2025, "a", "b") is None
        )


# ═══════════════════════════════════════════════════════════
# Orchestrator: reconcile_market_data
# ═══════════════════════════════════════════════════════════


class TestReconcileMarketData:
    def test_consistent_data_is_ok(self):
        report = reconcile_market_data(make_financials(), make_shares_info(), market="KR")
        assert report.status == "ok"
        assert not report.blocked
        # Identity checks ran and passed
        checks = {f.check for f in report.findings}
        assert "share_count" in checks
        assert "market_cap" in checks

    def test_synthetic_2x_shares_blocks(self):
        """The known bug class: registry shares 2x the market-implied count."""
        report = reconcile_market_data(
            make_financials(), make_shares_info(shares_total=TRUE_SHARES * 2), market="KR"
        )
        assert report.blocked
        blocked = {f.check for f in report.findings if f.severity == "block"}
        assert "share_count" in blocked
        assert "market_cap" in blocked

    def test_15_pct_shares_warns_not_blocks(self):
        report = reconcile_market_data(
            make_financials(),
            make_shares_info(shares_total=int(TRUE_SHARES * 1.15)),
            market="KR",
        )
        assert report.status == "warn"
        assert not report.blocked

    def test_missing_market_data_skips_gracefully(self):
        """Unlisted company: no price / market cap must never block."""
        info = make_shares_info(price=0, market_cap=0)
        report = reconcile_market_data(make_financials(), info, market="KR")
        assert report.status == "ok"
        assert {f.check for f in report.findings} & {"share_count", "market_cap"} == set()

    def test_empty_financials_no_crash(self):
        report = reconcile_market_data({}, make_shares_info(), market="KR")
        assert report.status in ("ok", "warn")

    def test_us_million_unit_market_cap_does_not_block(self):
        """Regression: real NVDA payload used to hard-block at 99,913,201.5%.

        market_cap comes back in $M while price/shares are raw -- if the
        reconciler forgets to rebase, the identity checks are off by ~1e6 and no
        US/KR auto-fetched profile can ever be persisted.
        """
        info = make_shares_info(
            shares_total=24_200_000_000,
            price=210.96,
            market_cap=5_109_662,  # $M, as yfinance_fetcher emits it
        )
        report = reconcile_market_data(make_financials(), info, market="US")
        assert not report.blocked
        share_check = next(f for f in report.findings if f.check == "share_count")
        assert share_check.rel_diff_pct < 1.0  # ~0.09%, not 99,913,201%

    def test_unit_check_runs_only_with_alt_source(self):
        fin = make_financials()
        report = reconcile_market_data(fin, make_shares_info(), market="KR")
        assert not any(f.check.startswith("unit_") for f in report.findings)

        alt = {2025: {"revenue": 10_000_000 * 1_000_000, "op": 1_000_000}}
        report2 = reconcile_market_data(
            fin, make_shares_info(), market="KR", alt_financials=alt
        )
        unit_rev = [f for f in report2.findings if f.check == "unit_revenue"]
        assert unit_rev and unit_rev[0].severity == "block"
        assert report2.blocked

    def test_op_exceeds_revenue_warns(self):
        fin = make_financials(op=15_000_000)
        report = reconcile_market_data(fin, make_shares_info(), market="KR")
        assert any(f.check == "op_exceeds_revenue" and f.severity == "warn" for f in report.findings)
        assert not report.blocked  # sanity warns never block

    def test_zero_liabilities_warns(self):
        fin = make_financials(liabilities=0)
        report = reconcile_market_data(fin, make_shares_info(), market="KR")
        assert any(f.check == "zero_liabilities" for f in report.findings)

    def test_treasury_exceeds_ordinary_warns(self):
        info = make_shares_info(treasury_shares=TRUE_SHARES + 1)
        report = reconcile_market_data(make_financials(), info, market="KR")
        assert any(f.check == "treasury_exceeds_ordinary" for f in report.findings)

    def test_report_to_dict_yaml_safe(self):
        report = reconcile_market_data(
            make_financials(), make_shares_info(shares_total=TRUE_SHARES * 2), market="KR"
        )
        d = report.to_dict()
        assert d["status"] == "block"
        assert "as_of" in d
        # Round-trips through YAML (persisted into the profile)
        dumped = yaml.dump(d, allow_unicode=True)
        assert yaml.safe_load(dumped)["status"] == "block"


# ═══════════════════════════════════════════════════════════
# Report aggregation
# ═══════════════════════════════════════════════════════════


class TestReconciliationReport:
    def test_status_is_max_severity(self):
        report = ReconciliationReport()
        report.add(Finding(check="a", severity="ok", message=""))
        assert report.status == "ok"
        report.add(Finding(check="b", severity="warn", message=""))
        assert report.status == "warn"
        report.add(Finding(check="c", severity="block", message=""))
        assert report.status == "block"
        # Does not downgrade
        report.add(Finding(check="d", severity="ok", message=""))
        assert report.status == "block"

    def test_add_none_is_noop(self):
        report = ReconciliationReport()
        report.add(None)
        assert report.findings == [] and report.status == "ok"


# ═══════════════════════════════════════════════════════════
# profile_generator integration (hard block + persistence)
# ═══════════════════════════════════════════════════════════


def _make_identity() -> CompanyIdentity:
    # ticker=None: skips yfinance diluted-shares and beta lookups (no IO)
    return CompanyIdentity("TestCo", "KR", legal_status="비상장", corp_code="00000000")


def _patch_project_root(monkeypatch, tmp_path):
    (tmp_path / "profiles").mkdir()
    monkeypatch.setattr(pg, "_PROJECT_ROOT", tmp_path)
    # Hermetic: avoid FRED / Yahoo lookups inside _generate_draft_profile
    import pipeline.macro_data as macro_data

    monkeypatch.setattr(macro_data, "get_terminal_growth", lambda market="KR": 2.0)
    monkeypatch.setattr(macro_data, "get_diluted_shares", lambda ticker, market="US": None)


class TestProfileGeneratorGate:
    def test_2x_shares_blocks_profile_generation(self, monkeypatch, tmp_path, capsys):
        _patch_project_root(monkeypatch, tmp_path)
        result = pg._generate_draft_profile(
            _make_identity(),
            make_financials(),
            make_shares_info(shares_total=TRUE_SHARES * 2),
        )
        assert result is None
        assert list((tmp_path / "profiles").glob("*.yaml")) == []
        out = capsys.readouterr().out
        assert "BLOCK" in out and "하드 블록" in out

    def test_consistent_data_persists_reconciliation_section(
        self, monkeypatch, tmp_path
    ):
        _patch_project_root(monkeypatch, tmp_path)
        result = pg._generate_draft_profile(
            _make_identity(), make_financials(), make_shares_info()
        )
        assert result is not None
        yaml_file = tmp_path / result
        assert yaml_file.exists()
        raw = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        recon = raw["data_reconciliation"]
        assert recon["status"] == "ok"
        assert any(f["check"] == "share_count" for f in recon["findings"])
        assert raw["draft"] is True
        assert raw["generated"] == "auto"
        assert raw["curated"] is False

    def test_existing_curated_profile_is_staged_not_overwritten(
        self, monkeypatch, tmp_path
    ):
        _patch_project_root(monkeypatch, tmp_path)
        destination = tmp_path / "profiles" / "testco.yaml"
        original = "curated: true\ndraft: false\ncompany: {name: Curated}\n"
        destination.write_text(original, encoding="utf-8")

        result = pg._generate_draft_profile(
            _make_identity(), make_financials(), make_shares_info()
        )

        assert result == "profiles/staging/testco.yaml"
        assert destination.read_text(encoding="utf-8") == original
        staged = yaml.safe_load((tmp_path / result).read_text(encoding="utf-8"))
        assert staged["draft"] is True
        assert staged["generated"] == "auto"

    def test_warn_level_mismatch_still_persists(self, monkeypatch, tmp_path, capsys):
        _patch_project_root(monkeypatch, tmp_path)
        result = pg._generate_draft_profile(
            _make_identity(),
            make_financials(),
            make_shares_info(shares_total=int(TRUE_SHARES * 1.15)),
        )
        assert result is not None  # warn does NOT block
        raw = yaml.safe_load((tmp_path / result).read_text(encoding="utf-8"))
        assert raw["data_reconciliation"]["status"] == "warn"
        assert "WARN" in capsys.readouterr().out

    def test_unlisted_without_market_data_generates_profile(
        self, monkeypatch, tmp_path
    ):
        _patch_project_root(monkeypatch, tmp_path)
        info = make_shares_info(price=0, market_cap=0)
        result = pg._generate_draft_profile(_make_identity(), make_financials(), info)
        assert result is not None
        raw = yaml.safe_load((tmp_path / result).read_text(encoding="utf-8"))
        assert raw["data_reconciliation"]["status"] == "ok"
