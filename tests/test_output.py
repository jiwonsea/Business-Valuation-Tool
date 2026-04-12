"""output package tests — dashboard + wp_poster + Excel sheet fixes."""


# ── dashboard._get_primary_value & _write_football_field ──


class TestGetPrimaryValue:
    """Verify _get_primary_value returns per-share for all methods."""

    def _make_ctx(self, method: str, result_kwargs: dict):
        """Build a minimal Ctx-like namespace for testing."""
        from types import SimpleNamespace

        defaults = dict(
            weighted_value=0,
            scenarios={},
            ddm=None,
            rim=None,
            nav=None,
            multiples_primary=None,
            dcf=None,
            cross_validations=[],
            total_ev=0,
        )
        defaults.update(result_kwargs)
        result = SimpleNamespace(**defaults)
        return SimpleNamespace(method=method, result=result, unit="백만원")

    def test_ddm_returns_per_share(self):
        from output.sheets.dashboard import _get_primary_value

        ddm = type("DDM", (), {"equity_per_share": 50_000})()
        ctx = self._make_ctx("ddm", {"ddm": ddm})
        val, label = _get_primary_value(ctx)
        assert val == 50_000
        assert "주당" in label

    def test_dcf_uses_cv_per_share_when_available(self):
        from output.sheets.dashboard import _get_primary_value

        dcf = type("DCF", (), {"ev_dcf": 999_000_000})()
        cv = type("CV", (), {"method": "DCF (FCFF)", "per_share": 120_000})()
        ctx = self._make_ctx("dcf_primary", {"dcf": dcf, "cross_validations": [cv]})
        val, label = _get_primary_value(ctx)
        assert val == 120_000
        assert "주당" in label

    def test_dcf_falls_back_to_ev_when_no_cv(self):
        from output.sheets.dashboard import _get_primary_value

        dcf = type("DCF", (), {"ev_dcf": 999_000_000})()
        ctx = self._make_ctx("dcf_primary", {"dcf": dcf, "cross_validations": []})
        val, label = _get_primary_value(ctx)
        assert val == 999_000_000
        assert "DCF Enterprise Value" in label


class TestFootballFieldNegativeValues:
    """Football field must not clamp negative per-share values to zero."""

    def _football_lo_hi(self, val: int) -> tuple[int, int]:
        """Replicate the lo/hi calculation from _write_football_field."""
        if val >= 0:
            lo = round(val * 0.8)
            hi = round(val * 1.2)
        else:
            lo = round(val * 1.2)
            hi = round(val * 0.8)
        return lo, hi

    def test_positive_value(self):
        lo, hi = self._football_lo_hi(100_000)
        assert lo == 80_000
        assert hi == 120_000
        assert hi > lo

    def test_negative_value_not_clamped(self):
        """Distressed company: per-share negative — range must be non-zero."""
        lo, hi = self._football_lo_hi(-50_000)
        assert lo < 0, "lo must remain negative"
        assert hi < 0, "hi must remain negative"
        assert lo < hi, "lo (more negative) must be less than hi (less negative)"
        assert abs(hi - lo) > 0, "range must be non-zero"

    def test_zero_value(self):
        lo, hi = self._football_lo_hi(0)
        assert lo == 0
        assert hi == 0


# ── wp_poster._build_post_content ──


class TestWpPosterBuildContent:
    def _make_summary(self, valuations=None, discoveries=None):
        return {
            "label": "Apr 2nd week (4/11)",
            "valuations": valuations or [],
            "discoveries": discoveries or [],
        }

    def test_empty_us_valuations_returns_empty(self):
        from scheduler.wp_poster import _build_post_content

        result = _build_post_content(self._make_summary())
        assert result == ""

    def test_company_name_markdown_escaping(self):
        from scheduler.wp_poster import _build_post_content

        # Company name with paired asterisks — without escaping, markdown renders as <em>
        summary = self._make_summary(
            valuations=[
                {
                    "company": "*Corp* LLC",
                    "market": "US",
                    "status": "success",
                    "market_cap_usd": 5_000_000_000,
                    "summary_md": "Summary line.",
                    "download_url": "",
                }
            ]
        )
        html = _build_post_content(summary)
        # Escaped name renders as literal asterisks, not <em> inside the heading
        assert "<em>Corp</em>" not in html, (
            "Company name *Corp* LLC should be escaped, not rendered as <em>"
        )

    def test_script_injection_stripped(self):
        from scheduler.wp_poster import _build_post_content

        summary = self._make_summary(
            valuations=[
                {
                    "company": "TestCo",
                    "market": "US",
                    "status": "success",
                    "market_cap_usd": 1_000_000_000,
                    "summary_md": "<script>alert('xss')</script>Safe content",
                    "download_url": "",
                }
            ]
        )
        html = _build_post_content(summary)
        assert "<script>" not in html.lower()
        assert "alert" not in html

    def test_download_url_scheme_validation(self):
        from scheduler.wp_poster import _build_post_content

        for bad_url in [
            "javascript:alert(1)",
            "data:text/html,<h1>xss</h1>",
            "vbscript:x",
        ]:
            summary = self._make_summary(
                valuations=[
                    {
                        "company": "TestCo",
                        "market": "US",
                        "status": "success",
                        "market_cap_usd": 1_000_000_000,
                        "summary_md": "Summary.",
                        "download_url": bad_url,
                    }
                ]
            )
            html = _build_post_content(summary)
            assert bad_url not in html, f"Unsafe URL must be blocked: {bad_url}"

    def test_download_url_valid_https_passes(self):
        from scheduler.wp_poster import _build_post_content

        valid_url = "https://storage.supabase.com/file.xlsx"
        summary = self._make_summary(
            valuations=[
                {
                    "company": "TestCo",
                    "market": "US",
                    "status": "success",
                    "market_cap_usd": 1_000_000_000,
                    "summary_md": "Summary.",
                    "download_url": valid_url,
                }
            ]
        )
        html = _build_post_content(summary)
        assert valid_url in html

    def test_dead_label_statement_removed(self):
        """Line 51 dead statement is removed — no AttributeError or side effect."""
        import inspect
        from scheduler.wp_poster import _build_post_content

        src = inspect.getsource(_build_post_content)
        # The dead line was: summary.get("label", "Weekly Report")  [result discarded]
        # After fix it should not appear as a standalone expression
        lines = [ln.strip() for ln in src.split("\n")]
        dead_pattern = 'summary.get("label"'
        standalone = [ln for ln in lines if ln.startswith(dead_pattern)]
        assert not standalone, f"Dead statement still present: {standalone}"


# ── scenarios.py: has_dlom dead statement fix ──


class TestScenariosDlomGuard:
    """DLOM row must only appear for unlisted companies with actual DLOM set."""

    def test_dead_has_dlom_statement_removed(self):
        """any() result is now assigned to has_dlom — not discarded."""
        import inspect
        from output.sheets.scenarios import sheet_scenarios

        src = inspect.getsource(sheet_scenarios)
        lines = [ln.strip() for ln in src.split("\n")]
        # Standalone any() starting with 'any(ctx.vi.scenarios' must not exist
        dead = [ln for ln in lines if ln.startswith("any(ctx.vi.scenarios")]
        assert not dead, f"Dead statement still present: {dead}"

    def test_has_dlom_assigned(self):
        """has_dlom is assigned and used in conditional."""
        import inspect
        from output.sheets.scenarios import sheet_scenarios

        src = inspect.getsource(sheet_scenarios)
        assert "has_dlom = any(" in src, "has_dlom must be assigned"
        assert "not is_listed and has_dlom" in src, "DLOM row must be gated on has_dlom"


# ── sensitivity.py: _get_ref_label_value SOTP fix ──


class TestSensitivityRefLabel:
    """SOTP valuation must show weighted per-share, not DCF EV, as reference."""

    def _make_ctx(self, method: str, weighted=40_000, total_ev=500_000, dcf_ev=300_000):
        from types import SimpleNamespace

        dcf = SimpleNamespace(ev_dcf=dcf_ev) if dcf_ev else None
        result = SimpleNamespace(
            weighted_value=weighted,
            total_ev=total_ev,
            dcf=dcf,
            ddm=None,
            rim=None,
            nav=None,
            multiples_primary=None,
        )
        return SimpleNamespace(
            method=method, result=result, unit="백만원", currency_sym="원"
        )

    def test_sotp_returns_weighted_value(self):
        from output.sheets.sensitivity import _get_ref_label_value

        ctx = self._make_ctx("sotp", weighted=40_000)
        label, value = _get_ref_label_value(ctx)
        assert "주당" in label, f"Expected per-share label, got: {label}"
        assert "40,000" in value, f"Expected weighted value in output, got: {value}"

    def test_sotp_with_dcf_cv_does_not_show_dcf_ev(self):
        """SOTP + DCF cross-validation must not show 'DCF EV' as reference."""
        from output.sheets.sensitivity import _get_ref_label_value

        ctx = self._make_ctx("sotp", weighted=40_000, dcf_ev=300_000)
        label, _ = _get_ref_label_value(ctx)
        assert label != "DCF EV", "SOTP should not show 'DCF EV' as reference label"

    def test_dcf_primary_shows_dcf_ev(self):
        from output.sheets.sensitivity import _get_ref_label_value

        ctx = self._make_ctx("dcf_primary", weighted=0, dcf_ev=500_000)
        label, _ = _get_ref_label_value(ctx)
        assert label == "DCF EV"


# ── rnpv.py: 4-fix cross-review corrections ──


class TestRnpvSheetFixes:
    """Structural checks for the 4 rnpv.py fixes from the cross-review session."""

    def _src(self):
        import inspect
        from output.sheets.rnpv import _sheet_pipeline_summary, _sheet_revenue_curves

        return inspect.getsource(_sheet_pipeline_summary) + inspect.getsource(
            _sheet_revenue_curves
        )

    def test_fx1_no_duplicate_import(self):
        """FX-1: style_header_row must not be re-imported inside _sheet_pipeline_summary."""
        import inspect
        from output.sheets.rnpv import _sheet_pipeline_summary

        src = inspect.getsource(_sheet_pipeline_summary)
        assert "from ..excel_styles import style_header_row" not in src, (
            "Duplicate inline import of style_header_row still present"
        )

    def test_fx2_rnpv_pct_uses_ne_zero(self):
        """FX-2: rnpv_pct guard must use != 0 so negative total_rnpv shows actual weights."""
        src = self._src()
        assert "total_rnpv != 0" in src, "rnpv_pct should guard with != 0, not > 0"
        assert "total_rnpv > 0" not in src, (
            "Old '> 0' guard still present — negative total_rnpv will show all-zero weights"
        )

    def test_fx3_equity_bridge_uses_pipeline_value(self):
        """FX-3: Equity Bridge must use pipeline_value, not enterprise_value."""
        import inspect
        from output.sheets.rnpv import _sheet_pipeline_summary

        src = inspect.getsource(_sheet_pipeline_summary)
        assert "rnpv.pipeline_value - ctx.vi.net_debt" in src, (
            "Equity Bridge should use pipeline_value explicitly"
        )
        assert "rnpv.enterprise_value - ctx.vi.net_debt" not in src, (
            "enterprise_value still used in Equity Bridge — use pipeline_value for clarity"
        )

    def test_fx4_peak_revenue_uses_all_drug_results(self):
        """FX-4: Peak Revenue summary must iterate rnpv.drug_results, not drugs_with_curves."""
        import inspect
        from output.sheets.rnpv import _sheet_revenue_curves

        src = inspect.getsource(_sheet_revenue_curves)
        # The Peak Revenue for-loop must reference drug_results
        lines = [ln.strip() for ln in src.split("\n")]
        peak_revenue_section = False
        found_drug_results = False
        for line in lines:
            if "Peak Revenue" in line:
                peak_revenue_section = True
            if peak_revenue_section and "for dr in rnpv.drug_results:" in line:
                found_drug_results = True
                break
        assert found_drug_results, (
            "Peak Revenue summary still uses drugs_with_curves — "
            "drugs without revenue_curve are excluded from summary"
        )
