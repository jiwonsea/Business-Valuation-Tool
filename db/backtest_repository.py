"""Backtest-specific Supabase CRUD — prediction snapshots and backtest outcomes."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from .client import get_client

logger = logging.getLogger(__name__)


# ── Prediction Snapshots ──


def save_prediction_snapshot(
    vi,  # ValuationInput
    result,  # ValuationResult
    valuation_id: str,
) -> Optional[str]:
    """Capture prediction snapshot at valuation time. Upsert on valuation_id."""
    client = get_client()
    if not client:
        return None

    # Extract scenario values
    scenario_values = {}
    for code, sc_input in vi.scenarios.items():
        sc_result = result.scenarios.get(code)
        if sc_result is None:
            continue
        scenario_values[code] = {
            "name": sc_input.name,
            "prob": sc_input.prob,
            "pre_dlom": sc_result.pre_dlom,
            "post_dlom": sc_result.post_dlom,
            "growth_adj_pct": sc_input.growth_adj_pct,
            "wacc_adj": sc_input.wacc_adj,
            "terminal_growth_adj": sc_input.terminal_growth_adj,
            "market_sentiment_pct": sc_input.market_sentiment_pct,
        }

    mc = result.market_comparison
    row = {
        "valuation_id": valuation_id,
        "company_name": vi.company.name,
        "ticker": vi.company.ticker or "",
        "market": vi.company.market,
        "currency": vi.company.currency,
        "unit_multiplier": vi.company.unit_multiplier,
        "legal_status": vi.company.legal_status,
        "analysis_date": vi.company.analysis_date.isoformat(),
        "predicted_weighted_value": result.weighted_value,
        "predicted_gap_ratio": mc.gap_ratio if mc else None,
        "price_at_prediction": mc.market_price if mc else None,
        "wacc_pct": result.wacc.wacc,
        "primary_method": result.primary_method,
        "market_signals_version": getattr(result, "market_signals_version", 0) or 1,
        "scenario_values": scenario_values,
    }

    try:
        resp = (
            client.table("prediction_snapshots")
            .upsert(row, on_conflict="valuation_id")
            .execute()
        )
        uid = resp.data[0]["id"]
        logger.info("Upserted prediction snapshot %s for %s", uid, vi.company.name)
        return uid
    except Exception:
        try:
            resp = client.table("prediction_snapshots").insert(row).execute()
            uid = resp.data[0]["id"]
            logger.info(
                "Inserted prediction snapshot %s for %s (fallback)",
                uid,
                vi.company.name,
            )
            return uid
        except Exception:
            logger.exception(
                "Failed to save prediction snapshot for %s", vi.company.name
            )
            return None


def list_prediction_snapshots(
    limit: int = 100,
    offset: int = 0,
    listed_only: bool = False,
) -> list[dict]:
    """List prediction snapshots with pagination."""
    client = get_client()
    if not client:
        return []

    query = (
        client.table("prediction_snapshots")
        .select("*")
        .order("analysis_date", desc=True)
        .range(offset, offset + limit - 1)
    )
    if listed_only:
        query = query.in_("legal_status", ["상장", "listed"])

    try:
        return query.execute().data
    except Exception:
        logger.exception("Failed to list prediction snapshots")
        return []


def get_snapshot_by_valuation(valuation_id: str) -> Optional[dict]:
    """Get snapshot for a given valuation."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("prediction_snapshots")
            .select("*")
            .eq("valuation_id", valuation_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Failed to get snapshot for valuation %s", valuation_id)
        return None


# ── Backtest Outcomes ──


def save_backtest_outcome(data: dict) -> Optional[str]:
    """Save backtest outcome. Upsert on snapshot_id."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("backtest_outcomes")
            .upsert(data, on_conflict="snapshot_id")
            .execute()
        )
        uid = resp.data[0]["id"]
        logger.info("Upserted backtest outcome %s", uid)
        return uid
    except Exception:
        logger.exception("Failed to save backtest outcome")
        return None


def update_backtest_prices(outcome_id: str, price_data: dict) -> bool:
    """Partial update of prices for an existing outcome row."""
    client = get_client()
    if not client:
        return False

    price_data["price_fetched_at"] = datetime.utcnow().isoformat()

    try:
        client.table("backtest_outcomes").update(price_data).eq(
            "id", outcome_id
        ).execute()
        return True
    except Exception:
        logger.exception("Failed to update backtest prices for %s", outcome_id)
        return False


def get_outcome_by_snapshot(snapshot_id: str) -> Optional[dict]:
    """Get outcome for a given snapshot."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("backtest_outcomes")
            .select("*")
            .eq("snapshot_id", snapshot_id)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.exception("Failed to get outcome for snapshot %s", snapshot_id)
        return None


def list_outcomes_needing_refresh(today: date) -> list[dict]:
    """List outcomes with NULL prices for past-due horizons.

    Returns outcomes where at least one horizon has passed but price is NULL.
    """
    client = get_client()
    if not client:
        return []

    try:
        # Get all outcomes, filter in Python (Supabase doesn't support
        # complex date arithmetic in PostgREST filters easily)
        resp = (
            client.table("backtest_outcomes")
            .select("*, prediction_snapshots!inner(analysis_date)")
            .is_("price_t3m", "null")  # At least one NULL
            .order("created_at", desc=False)
            .limit(200)
            .execute()
        )

        results = []
        for row in resp.data:
            analysis_date_str = row.get("analysis_date", "")
            try:
                ad = date.fromisoformat(analysis_date_str)
            except (ValueError, TypeError):
                continue

            from dateutil.relativedelta import relativedelta

            needs_refresh = False
            if row.get("price_t3m") is None and ad + relativedelta(months=3) <= today:
                needs_refresh = True
            if row.get("price_t6m") is None and ad + relativedelta(months=6) <= today:
                needs_refresh = True
            if row.get("price_t12m") is None and ad + relativedelta(months=12) <= today:
                needs_refresh = True

            if needs_refresh:
                results.append(row)

        return results
    except Exception:
        logger.exception("Failed to list outcomes needing refresh")
        return []
