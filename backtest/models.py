"""Backtest data models."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class ScenarioSnapshot(BaseModel):
    """Per-scenario prediction snapshot captured at valuation time."""

    code: str
    name: str
    prob: float  # Probability (%)
    pre_dlom: int  # Per-share value before DLOM
    post_dlom: int  # Per-share value after DLOM
    growth_adj_pct: float = 0.0
    wacc_adj: float = 0.0
    terminal_growth_adj: float = 0.0
    market_sentiment_pct: float = 0.0


class BacktestRecord(BaseModel):
    """Single backtest observation pairing prediction with outcome."""

    snapshot_id: str
    valuation_id: str
    ticker: str
    market: str
    currency: str
    unit_multiplier: int
    company_name: str
    legal_status: str
    analysis_date: date
    predicted_value: int  # weighted_value (display unit, per-share)
    predicted_gap_ratio: Optional[float] = None
    price_at_prediction: Optional[float] = None  # T0 market price
    wacc_pct: Optional[float] = None

    # Actual prices (native currency)
    price_t0: Optional[float] = None
    price_t3m: Optional[float] = None
    price_t6m: Optional[float] = None
    price_t12m: Optional[float] = None

    # Scenario snapshots
    scenarios: list[ScenarioSnapshot] = []

    # Primary valuation method used (e.g., "sotp", "dcf_primary", "ddm", "rim", "rnpv")
    primary_method: Optional[str] = None

    # Phase 4: Market signals version for A/B comparison
    # 0 = pre-Phase 4 (no signals), 1 = Phase 4 (with market signals)
    market_signals_version: int = 0

    @property
    def predicted_value_native(self) -> float:
        """Convert predicted_value to native currency (comparable to market price)."""
        return float(self.predicted_value * self.unit_multiplier)

    @property
    def is_listed(self) -> bool:
        return self.legal_status in ("상장", "listed")

    def get_price(self, horizon: str) -> Optional[float]:
        """Get price for a given horizon key ('t0', 't3m', 't6m', 't12m')."""
        return getattr(self, f"price_{horizon}", None)

    def scenario_range_native(self) -> tuple[float, float] | None:
        """Min/max post_dlom in native currency. None if no scenarios."""
        if not self.scenarios:
            return None
        values = [s.post_dlom * self.unit_multiplier for s in self.scenarios]
        return (min(values), max(values))

    def scenario_pre_dlom_range_native(self) -> tuple[float, float] | None:
        """Min/max pre_dlom in native currency (for IPO-listed comparisons)."""
        if not self.scenarios:
            return None
        values = [s.pre_dlom * self.unit_multiplier for s in self.scenarios]
        return (min(values), max(values))
