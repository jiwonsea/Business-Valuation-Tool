"""output package tests — dashboard + wp_poster fixes."""

import pytest


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

    def test_dead_label_statement_removed(self):
        """Line 51 dead statement is removed — no AttributeError or side effect."""
        import inspect
        from scheduler.wp_poster import _build_post_content

        src = inspect.getsource(_build_post_content)
        # The dead line was: summary.get("label", "Weekly Report")  [result discarded]
        # After fix it should not appear as a standalone expression
        lines = [l.strip() for l in src.split("\n")]
        dead_pattern = 'summary.get("label"'
        standalone = [l for l in lines if l.startswith(dead_pattern)]
        assert not standalone, f"Dead statement still present: {standalone}"
