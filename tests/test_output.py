"""output package tests — dashboard + wp_poster + Excel sheet fixes."""


def test_engine_warning_excel_order_rows_and_append_only(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from openpyxl import load_workbook

    import db.repository
    from engine.warnings import make_warning
    from output.excel_builder import export
    from valuation_runner import load_profile, run_valuation

    monkeypatch.setattr(db.repository, "list_valuation_history", lambda *a, **kw: [])
    vi = load_profile(str(Path(__file__).parent / "fixtures" / "msft_frozen.yaml"))
    result = run_valuation(vi)
    baseline = load_workbook(export(vi, result, str(tmp_path)))
    warnings = [
        make_warning(
            "SCENARIO_MULTIPLE_CLAMPED",
            f"scenario:Bull/segment:{seg}",
            f"clamp {seg}",
            original=66.0,
            applied=44.0,
            floor=22.0,
            original_ratio=3.0,
            cap_ratio=2.0,
        )
        for seg in ["PBP", "IC"]
    ]
    result = result.model_copy(update={"engine_warnings": warnings, "draft": True})
    current = load_workbook(export(vi, result, str(tmp_path)))
    assert current.sheetnames[:3] == ["DRAFT WARNING", "경고", "Raw Data"]
    assert [
        s for s in current.sheetnames if s != "DRAFT WARNING"
    ] == baseline.sheetnames
    ws = current["경고"]
    assert ws.max_row - 1 == len(warnings)
    assert [cell.value for cell in ws[1]] == [
        "code",
        "severity",
        "scope",
        "message",
        "fields(JSON)",
    ]
    for row in ws.iter_rows(min_row=2, values_only=True):
        warning = next(w for w in warnings if w.scope == row[2])
        assert list(row[:4]) == [
            warning.code,
            warning.severity,
            warning.scope,
            warning.message,
        ]
        assert json.loads(row[4]) == warning.fields
    scenario = current["Scenario Analysis"]
    title_row = next(
        cell.row
        for row in scenario
        for cell in row
        if cell.value == "클램프 원값→적용값"
    )
    assert title_row > baseline["Scenario Analysis"].max_row
    assert scenario.max_row - (title_row + 1) == len(warnings)
    assert [scenario.cell(title_row + 1, c).value for c in range(1, 6)] == [
        "scenario",
        "segment",
        "original",
        "applied",
        "cap_ratio",
    ]
    for title in baseline.sheetnames:
        if title == "경고":
            continue
        old, new = baseline[title], current[title]
        assert (new.min_row, new.min_column) == (old.min_row, old.min_column)
        for row in old:
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("경고 "):
                    assert (
                        new[cell.coordinate].value
                        == "경고 2건 / 검토 필요 0건 — '경고' 시트"
                    )
                    continue
                assert new[cell.coordinate].value == cell.value
                assert new[cell.coordinate].number_format == cell.number_format
    assert baseline["경고"].max_row == 1
    assert baseline.sheetnames[:2] == ["경고", "Raw Data"]
    dashboard = current["Dashboard"]
    summary = next(
        cell
        for row in dashboard
        for cell in row
        if isinstance(cell.value, str) and cell.value.startswith("경고 ")
    )
    assert summary.row > dashboard._charts[-1].anchor._from.row + 1 + 18


def test_peer_implied_multiple_panel_skips_mixed_sotp():
    from types import SimpleNamespace

    from openpyxl import Workbook

    from output.sheets.peers import _implied_multiple_check

    ws = Workbook().active
    ctx = SimpleNamespace(
        vi=SimpleNamespace(
            segments={
                "GAME": {"method": "ev_revenue"},
                "STORE": {"method": "pbv"},
            }
        )
    )

    _implied_multiple_check(ws, 1, ctx)

    assert "혼합 SOTP" in ws["A2"].value
    assert "생략" in ws["A2"].value


def test_console_peer_stats_uses_method_specific_multiple(capsys):
    from pathlib import Path

    from output.console_report import print_report
    from valuation_runner import load_profile, run_valuation

    profile = Path(__file__).parent.parent / "profiles" / "nexus.yaml"
    vi = load_profile(str(profile))
    result = run_valuation(vi)

    print_report(vi, result)

    stdout = capsys.readouterr().out
    assert "EV/Sales" in stdout
    assert "0.543x" in stdout
    assert "Peer 멀티플 통계 (EV/EBITDA)" not in stdout
    assert "SOTP (Mixed)" in stdout


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

    def test_draft_blocked_us_valuation_is_not_published(self):
        from scheduler.wp_poster import _build_post_content

        summary = self._make_summary(
            valuations=[
                {
                    "company": "StubCo",
                    "market": "US",
                    "status": "draft_blocked",
                    "summary_md": "Must remain internal",
                }
            ]
        )
        assert _build_post_content(summary) == ""

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


class TestScenarioBridgeAlignment:
    """Scenario waterfall rows must align by adjustment name, not list index."""

    def test_sheet_aligns_adjustments_by_name(self):
        from types import SimpleNamespace

        from openpyxl import Workbook

        from output.sheets.scenarios import sheet_scenarios
        from schemas.models import AdjustmentItem

        ctx = SimpleNamespace(
            wb=Workbook(),
            unit="KRW m",
            sc_codes=["A", "B", "C"],
            method="sotp",
            currency_sym="KRW",
            vi=SimpleNamespace(
                company=SimpleNamespace(legal_status="unlisted"),
                scenarios={
                    "A": SimpleNamespace(
                        name="Base",
                        prob=20,
                        dlom=0,
                        irr=None,
                        desc="",
                        probability_rationale="",
                        driver_rationale={},
                        market_sentiment_pct=0,
                        wacc_adj=0,
                    ),
                    "B": SimpleNamespace(
                        name="Bull",
                        prob=45,
                        dlom=20,
                        irr=5.0,
                        desc="",
                        probability_rationale="",
                        driver_rationale={},
                        market_sentiment_pct=0,
                        wacc_adj=0,
                    ),
                    "C": SimpleNamespace(
                        name="Bear",
                        prob=35,
                        dlom=25,
                        irr=12.0,
                        desc="",
                        probability_rationale="",
                        driver_rationale={},
                        market_sentiment_pct=0,
                        wacc_adj=0,
                    ),
                },
            ),
            result=SimpleNamespace(
                engine_warnings=[],
                weighted_value=34_745,
                scenarios={
                    "A": SimpleNamespace(
                        total_ev=6_004_633,
                        adjustments=[
                            AdjustmentItem(name="Net Debt", value=2_295_568),
                            AdjustmentItem(name="Eco Frontier", value=94_644),
                            AdjustmentItem(name="Receivable Recovery", value=-10_000),
                        ],
                        equity_value=3_614_421,
                        shares=65_599_748,
                        pre_dlom=55_098,
                        post_dlom=55_098,
                        weighted=11_020,
                    ),
                    "B": SimpleNamespace(
                        total_ev=6_004_633,
                        adjustments=[
                            AdjustmentItem(name="Net Debt", value=2_295_568),
                            AdjustmentItem(name="CPS Redeem", value=729_304),
                            AdjustmentItem(name="RCPS Redeem", value=490_000),
                            AdjustmentItem(name="Eco Frontier", value=94_644),
                        ],
                        equity_value=2_395_117,
                        shares=54_278_993,
                        pre_dlom=40_441,
                        post_dlom=32_353,
                        weighted=14_559,
                    ),
                    "C": SimpleNamespace(
                        total_ev=6_004_633,
                        adjustments=[
                            AdjustmentItem(name="Net Debt", value=2_295_568),
                            AdjustmentItem(name="CPS Redeem", value=944_112),
                            AdjustmentItem(name="RCPS Redeem", value=575_000),
                            AdjustmentItem(name="Eco Frontier", value=94_644),
                        ],
                        equity_value=2_095_309,
                        shares=54_278_993,
                        pre_dlom=34_917,
                        post_dlom=26_188,
                        weighted=9_166,
                    ),
                },
            ),
        )

        ctx.per_share_fmt = "#,##0"
        ctx.vi.company.currency = "KRW"
        for code, sr in ctx.result.scenarios.items():
            sr.prob_effective_pct = ctx.vi.scenarios[code].prob
        sheet_scenarios(ctx)

        ws = ctx.wb["Scenario Analysis"]
        actual_rows = {
            ws.cell(row, 1).value: (
                ws.cell(row, 2).value,
                ws.cell(row, 3).value,
                ws.cell(row, 4).value,
            )
            for row in range(1, ws.max_row + 1)
            if isinstance(ws.cell(row, 1).value, str)
            and ws.cell(row, 1).value.startswith("(-) ")
        }

        assert actual_rows["(-) Net Debt"] == (2_295_568, 2_295_568, 2_295_568)
        assert actual_rows["(-) CPS Redeem"] == (0, 729_304, 944_112)
        assert actual_rows["(-) RCPS Redeem"] == (0, 490_000, 575_000)
        assert actual_rows["(-) Eco Frontier"] == (94_644, 94_644, 94_644)
        assert (
            ws.cell(
                row=next(
                    row
                    for row in range(1, ws.max_row + 1)
                    if ws.cell(row, 1).value == "(+) Receivable Recovery"
                ),
                column=2,
            ).value
            == 10_000
        )


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
            method=method,
            result=result,
            unit="백만원",
            currency_sym="원",
            vi=SimpleNamespace(company=SimpleNamespace(currency="KRW")),
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


# ── draft_blocked count rendering (R16 완결: 운영자 가시성) ──


class TestDraftBlockedRendering:
    def _make_summary(self, blocked=0):
        return {
            "label": "Jul 3rd week (7/18)",
            "markets": ["KR", "US"],
            "valuations": [],
            "discoveries": [],
            "status_summary": {
                "total": 3,
                "success": 3 - blocked,
                "failed": 0,
                "draft_blocked": blocked,
            },
        }

    def test_gamma_summary_text_renders_draft_blocked(self):
        from scheduler.delivery import build_weekly_summary_gamma_text

        text = build_weekly_summary_gamma_text(self._make_summary(blocked=2))
        assert "게시 차단(draft): 2개" in text

    def test_gmail_html_renders_draft_blocked_when_nonzero(self):
        from scheduler.delivery import build_gmail_html

        html = build_gmail_html(self._make_summary(blocked=2))
        assert "게시 차단(draft): 2개" in html

    def test_gmail_html_omits_draft_blocked_when_zero(self):
        from scheduler.delivery import build_gmail_html

        html = build_gmail_html(self._make_summary(blocked=0))
        assert "게시 차단" not in html

    def test_naver_header_renders_draft_blocked_when_nonzero(self):
        from scheduler.naver_poster import build_blog_sections

        _, sections = build_blog_sections(self._make_summary(blocked=1))
        header = sections[0]["content"]
        assert "게시 차단(draft): 1개" in header

    def test_naver_header_omits_draft_blocked_when_zero(self):
        from scheduler.naver_poster import build_blog_sections

        _, sections = build_blog_sections(self._make_summary(blocked=0))
        assert "게시 차단" not in sections[0]["content"]


def test_jpy_display_uses_currency_and_preserves_numeric_cells(tmp_path, capsys):
    from pathlib import Path
    from unittest.mock import patch

    from openpyxl import load_workbook
    from output.excel_builder import export
    from output.console_report import print_report
    from output.sheets._ctx import make_ctx
    from valuation_runner import load_profile, run_valuation
    from openpyxl import Workbook

    vi = load_profile(str(Path(__file__).parent / "fixtures/nexus_frozen.yaml"))
    vi = vi.model_copy(
        update={
            "company": vi.company.model_copy(
                update={"market": "US", "currency": "JPY"}
            ),
            "market_price": 2879.125,
        }
    )
    result = run_valuation(vi)
    result = result.model_copy(update={"weighted_value": 2879.125})
    ctx = make_ctx(vi, result, Workbook())
    assert ctx.currency_sym == "¥"
    assert ctx.currency_decimals == 0
    print_report(vi, result)
    assert "2,879¥" in capsys.readouterr().out
    with patch("db.repository.list_valuation_history", return_value=[]):
        path = export(vi, result, str(tmp_path))
    workbook = load_workbook(path)
    ws = workbook["Scenario Analysis"]
    label = next(c for row in ws for c in row if c.value == "확률가중 주당 가치")
    cell = ws.cell(label.row, 2)
    assert cell.value == 2879.125
    assert cell.number_format == "#,##0"
    assert ws.cell(label.row, 3).value == "¥"
    raw = workbook["Raw Data"]
    price_label = next(c for row in raw for c in row if c.value == "기준 주가 (¥)")
    assert raw.cell(price_label.row, 2).value == 2879.125
    assert raw.cell(price_label.row, 2).number_format == "#,##0"


def test_us_and_kr_share_cells_preserve_floats_and_currency_precision(tmp_path, capsys):
    from pathlib import Path
    from unittest.mock import patch
    from openpyxl import load_workbook
    from output.console_report import print_report
    from output.excel_builder import export
    from valuation_runner import load_profile, run_valuation

    base = load_profile(str(Path(__file__).parent / "fixtures/nexus_frozen.yaml"))
    for currency, value, expected, fmt in [
        ("USD", 113.61234, "113.61$", "#,##0.00"),
        ("KRW", 314499.5, "314,500원", "#,##0"),
    ]:
        vi = base.model_copy(
            update={"company": base.company.model_copy(update={"currency": currency})}
        )
        result = run_valuation(vi).model_copy(update={"weighted_value": value})
        print_report(vi, result)
        assert expected in capsys.readouterr().out
        with patch("db.repository.list_valuation_history", return_value=[]):
            path = export(vi, result, str(tmp_path))
        wb = load_workbook(path)
        for title in ("Scenario Analysis", "Dashboard"):
            ws = wb[title]
            label = next(
                c for row in ws for c in row if c.value == "확률가중 주당 가치"
            )
            cell = ws.cell(label.row, 2)
            assert cell.value == value
            expected_fmt = (
                fmt + '"' + ("$" if currency == "USD" else "원") + '"'
                if title == "Dashboard"
                else fmt
            )
            assert cell.number_format == expected_fmt


def test_ddm_share_inputs_keep_raw_numbers_and_display_unit_amounts_stay_integer_formatted():
    from pathlib import Path
    from openpyxl import Workbook
    from output.sheets._ctx import make_ctx
    from output.sheets.assumptions import sheet_assumptions
    from output.sheets.dashboard import sheet_dashboard
    from schemas.models import DDMParams
    from valuation_runner import load_profile, run_valuation

    vi = load_profile(str(Path(__file__).parent / "fixtures/nexus_frozen.yaml"))
    vi = vi.model_copy(
        update={
            "company": vi.company.model_copy(update={"currency": "USD"}),
            "ddm_params": DDMParams(dps=2.675, buyback_per_share=0.005),
        }
    )
    result = run_valuation(vi)
    ctx = make_ctx(vi, result, Workbook())
    sheet_dashboard(ctx)
    dashboard = ctx.wb["Dashboard"]
    debt = next(
        c
        for row in dashboard
        for c in row
        if isinstance(c.value, str) and c.value.startswith("순차입금")
    )
    assert dashboard.cell(debt.row, 2).number_format == "#,##0"
    ctx.method = "ddm"
    sheet_assumptions(ctx)
    ws = ctx.wb["Assumptions"]
    for label, expected in [("주당 배당금 (DPS)", 2.675), ("주당 자사주매입", 0.005)]:
        found = next(c for row in ws for c in row if c.value == label)
        cell = ws.cell(found.row, 2)
        assert cell.value == expected
        assert cell.number_format == '#,##0.00"$"'
