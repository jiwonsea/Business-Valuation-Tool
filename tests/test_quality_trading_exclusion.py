# -*- coding: utf-8 -*-
"""Trading-multiple circularity exclusion in quality convergence scoring.

CODEX finding (d), 2026-07-10: market-derived (trading) multiples reproduce the
market price by construction, so their mutual agreement must not count as
independent cross-validation convergence (it double-rewards the market price
already scored by the market-alignment bucket).
"""

from engine.quality import (
    _TRADING_MULT_METHODS,
    _cv_convergence_score,
    _trading_anchored_methods,
)
from schemas.models import CrossValidationItem


def _cv(method: str, per_share: int) -> CrossValidationItem:
    return CrossValidationItem(
        method=method,
        metric_value=1.0,
        multiple=1.0,
        enterprise_value=1,
        equity_value=1,
        per_share=per_share,
    )


def _nvda_like():
    """SOTP/DCF independent + three trading multiples pinned to market price."""
    return [
        _cv("SOTP (EV/EBITDA)", 119),
        _cv("DCF (FCFF)", 138),
        _cv("EV/Revenue", 203),
        _cv("P/E", 203),
        _cv("P/BV", 203),
    ]


class TestTradingAnchoredDetection:
    def test_detects_price_pinned_multiples(self):
        assert _trading_anchored_methods(_nvda_like(), 202.34) == {
            "EV/Revenue",
            "P/E",
            "P/BV",
        }

    def test_no_market_price_returns_empty(self):
        assert _trading_anchored_methods(_nvda_like(), 0.0) == set()
        assert _trading_anchored_methods(_nvda_like(), -1.0) == set()

    def test_peer_multiples_outside_tolerance_kept(self):
        # >5% from market price -> treated as independent [P] estimates
        cvs = [_cv("P/E", 180), _cv("P/BV", 230), _cv("SOTP (EV/EBITDA)", 150)]
        assert _trading_anchored_methods(cvs, 202.34) == set()

    def test_non_multiple_methods_never_tagged(self):
        cvs = [_cv("SOTP (EV/EBITDA)", 202), _cv("DCF (FCFF)", 203)]
        assert _trading_anchored_methods(cvs, 202.34) == set()
        assert "SOTP (EV/EBITDA)" not in _TRADING_MULT_METHODS


class TestConvergenceWithTradingExclusion:
    def test_trading_excluded_scores_independent_set(self):
        cvs = _nvda_like()
        trading = _trading_anchored_methods(cvs, 202.34)
        score, warns = _cv_convergence_score(cvs, trading_methods=trading)
        # Only SOTP(119) + DCF(138) remain: genuine two-method convergence
        assert score > 0
        assert any("순환성" in w for w in warns)

    def test_dcf_auto_exclusion_skipped_when_trading_removed(self):
        # Legacy path would drop DCF (ratio 138/203 < 0.7); with the trading
        # cluster removed DCF must stay -- otherwise fallback re-adds circularity.
        cvs = _nvda_like()
        score, warns = _cv_convergence_score(
            cvs, trading_methods={"EV/Revenue", "P/E", "P/BV"}
        )
        assert not any("성장/옵셔널리티 괴리" in w for w in warns)
        assert score > 0

    def test_fallback_when_too_few_methods_remain(self):
        cvs = [_cv("SOTP (EV/EBITDA)", 119), _cv("EV/Revenue", 203), _cv("P/E", 203)]
        score, warns = _cv_convergence_score(
            cvs, trading_methods={"EV/Revenue", "P/E", "P/BV"}
        )
        assert any("폴백" in w for w in warns)
        assert score >= 0  # falls back to full set instead of scoring 0

    def test_legacy_behavior_unchanged_without_trading(self):
        cvs = _nvda_like()
        score_new, warns_new = _cv_convergence_score(cvs, trading_methods=None)
        # Pre-patch semantics: DCF auto-exclusion fires against multiple cluster
        assert any("성장/옵셔널리티" in w for w in warns_new)
        assert score_new >= 0
