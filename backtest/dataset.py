"""Build backtest dataset from prediction snapshots and outcome prices."""

from __future__ import annotations

import logging
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

from .buckets import classify_bucket
from .models import BacktestRecord, ScenarioSnapshot

logger = logging.getLogger(__name__)


def _needs_price_refresh(outcome: dict, today: date) -> bool:
    """Check if an outcome row has NULL prices for past-due horizons."""
    analysis_date_str = outcome.get("analysis_date", "")
    try:
        ad = date.fromisoformat(analysis_date_str)
    except (ValueError, TypeError):
        return False

    if outcome.get("price_t3m") is None and ad + relativedelta(months=3) <= today:
        return True
    if outcome.get("price_t6m") is None and ad + relativedelta(months=6) <= today:
        return True
    if outcome.get("price_t12m") is None and ad + relativedelta(months=12) <= today:
        return True
    return False


def _parse_scenarios(scenario_values: dict) -> list[ScenarioSnapshot]:
    """Parse scenario_values JSONB into ScenarioSnapshot list."""
    scenarios = []
    for code, vals in scenario_values.items():
        if not isinstance(vals, dict):
            continue
        scenarios.append(
            ScenarioSnapshot(
                code=code,
                name=vals.get("name", code),
                prob=vals.get("prob", 0),
                pre_dlom=vals.get("pre_dlom", 0),
                post_dlom=vals.get("post_dlom", 0),
                growth_adj_pct=vals.get("growth_adj_pct", 0),
                wacc_adj=vals.get("wacc_adj", 0),
                terminal_growth_adj=vals.get("terminal_growth_adj", 0),
                market_sentiment_pct=vals.get("market_sentiment_pct", 0),
            )
        )
    return scenarios


def build_backtest_dataset(min_age_days: int = 90) -> list[BacktestRecord]:
    """Build backtest records from prediction snapshots.

    1. Paginate through prediction_snapshots (listed companies only)
    2. Filter by min_age_days
    3. Fetch/refresh outcome prices as needed
    4. Return assembled BacktestRecord list
    """
    from db.backtest_repository import (
        list_prediction_snapshots,
        get_outcome_by_snapshot,
        save_backtest_outcome,
        update_backtest_prices,
    )
    from .price_tracker import fetch_outcome_prices

    today = date.today()
    cutoff = today - relativedelta(days=min_age_days)
    records: list[BacktestRecord] = []

    # Paginate through snapshots
    offset = 0
    page_size = 100

    while True:
        snapshots = list_prediction_snapshots(
            limit=page_size, offset=offset, listed_only=True
        )
        if not snapshots:
            break

        for snap in snapshots:
            # Filter by age
            try:
                ad = date.fromisoformat(snap["analysis_date"])
            except (ValueError, TypeError):
                continue
            if ad > cutoff:
                continue

            # Skip if no ticker
            ticker = snap.get("ticker", "")
            if not ticker:
                continue

            snapshot_id = snap["id"]
            market = snap.get("market", "KR")

            # Check existing outcome
            outcome = get_outcome_by_snapshot(snapshot_id)

            if outcome is None:
                # Fetch prices and create outcome
                prices = fetch_outcome_prices(ticker, market, ad)
                outcome_data = {
                    "snapshot_id": snapshot_id,
                    "ticker": ticker,
                    "market": market,
                    "analysis_date": ad.isoformat(),
                    "price_t0": prices.get("price_t0"),
                    "price_t3m": prices.get("price_t3m"),
                    "price_t6m": prices.get("price_t6m"),
                    "price_t12m": prices.get("price_t12m"),
                    "date_t3m": prices.get("date_t3m", None),
                    "date_t6m": prices.get("date_t6m", None),
                    "date_t12m": prices.get("date_t12m", None),
                    "price_fetched_at": datetime.utcnow().isoformat(),
                    "fetch_errors": prices.get("fetch_errors", {}),
                }
                # Convert date objects to ISO strings for JSON
                for k in ("date_t3m", "date_t6m", "date_t12m"):
                    if isinstance(outcome_data[k], date):
                        outcome_data[k] = outcome_data[k].isoformat()
                save_backtest_outcome(outcome_data)
                outcome = outcome_data
            elif _needs_price_refresh(outcome, today):
                # Partial refresh for past-due horizons
                prices = fetch_outcome_prices(ticker, market, ad)
                update_data = {}
                for horizon_key in ("price_t3m", "price_t6m", "price_t12m"):
                    if (
                        outcome.get(horizon_key) is None
                        and prices.get(horizon_key) is not None
                    ):
                        update_data[horizon_key] = prices[horizon_key]
                        date_key = horizon_key.replace("price_", "date_")
                        d = prices.get(date_key)
                        if isinstance(d, date):
                            update_data[date_key] = d.isoformat()
                        elif d is not None:
                            update_data[date_key] = d
                if update_data:
                    # Merge fetch errors
                    existing_errors = outcome.get("fetch_errors", {})
                    new_errors = prices.get("fetch_errors", {})
                    if new_errors:
                        existing_errors.update(new_errors)
                        update_data["fetch_errors"] = existing_errors
                    update_backtest_prices(outcome["id"], update_data)
                    outcome.update(update_data)

            # Assemble BacktestRecord
            scenario_values = snap.get("scenario_values", {})
            scenarios = _parse_scenarios(scenario_values)

            record = BacktestRecord(
                snapshot_id=snapshot_id,
                valuation_id=snap.get("valuation_id", ""),
                ticker=ticker,
                market=market,
                currency=snap.get("currency", "KRW"),
                unit_multiplier=snap.get("unit_multiplier", 1_000_000),
                company_name=snap.get("company_name", ""),
                legal_status=snap.get("legal_status", "상장"),
                analysis_date=ad,
                predicted_value=snap.get("predicted_weighted_value", 0),
                predicted_gap_ratio=snap.get("predicted_gap_ratio"),
                price_at_prediction=snap.get("price_at_prediction"),
                wacc_pct=snap.get("wacc_pct"),
                price_t0=outcome.get("price_t0"),
                price_t3m=outcome.get("price_t3m"),
                price_t6m=outcome.get("price_t6m"),
                price_t12m=outcome.get("price_t12m"),
                scenarios=scenarios,
                primary_method=snap.get("primary_method"),
                valuation_bucket=classify_bucket(
                    primary_method=snap.get("primary_method"),
                    valuation_bucket=snap.get("valuation_bucket"),
                ),
                market_signals_version=snap.get("market_signals_version", 0),
            )
            records.append(record)

        offset += page_size

    logger.info("Built backtest dataset: %d records", len(records))
    return records
