"""Persisted valuation-history contracts.

History records describe values saved at the original analysis time.  Consumers
must not recompute them with the current valuation engine.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Provenance(str, Enum):
    """Origin category for a persisted or modelled value."""

    REPORTED = "reported"
    DERIVED = "derived"
    ANALYST_ESTIMATE = "analyst_estimate"
    LLM_ESTIMATE = "llm_estimate"


class ValuationHistoryRecord(BaseModel):
    """Read-only headline snapshot loaded from the valuations table."""

    ticker: Optional[str] = None
    market: Optional[str] = None
    company_name: Optional[str] = None
    analysis_date: Optional[date] = None
    weighted_value: Optional[int] = None
    market_price: Optional[float] = None
    gap_pct: Optional[float] = None
    wacc_pct: Optional[float] = None
    quality_grade: Optional[str] = None
    primary_method: Optional[str] = None
    valuation_bucket: Optional[str] = None
    created_at: Optional[datetime] = None
    provenance: dict[str, Provenance] = Field(default_factory=dict)
