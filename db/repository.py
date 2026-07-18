"""Supabase CRUD -- valuation, AI analysis, and profile save/retrieve."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from schemas.models import ValuationInput, ValuationResult
from schemas.history import Provenance, ValuationHistoryRecord
from .client import get_client

logger = logging.getLogger(__name__)


def _serialize_date(obj):
    """Convert date objects to ISO string (for JSON serialization)."""
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ── Valuations ──


def save_valuation(
    vi: ValuationInput,
    result: ValuationResult,
) -> Optional[str]:
    """Save valuation input + result. Returns UUID on success."""
    client = get_client()
    if not client:
        return None

    mc = result.market_comparison
    row = {
        "company_name": vi.company.name,
        "ticker": vi.company.ticker,
        "market": vi.company.market,
        "legal_status": vi.company.legal_status,
        "valuation_method": result.primary_method,
        "analysis_date": vi.company.analysis_date.isoformat(),
        "base_year": vi.base_year,
        "total_ev": result.total_ev,
        "weighted_value": result.weighted_value,
        "wacc_pct": result.wacc.wacc,
        "market_price": mc.market_price if mc else None,
        "gap_ratio": mc.gap_ratio if mc else None,
        "input_data": vi.model_dump(mode="json"),
        "result_data": result.model_dump(mode="json"),
    }

    try:
        # History policy: every successful run is append-only, including reruns on
        # the same analysis date.  The history reader orders by created_at and can
        # therefore identify the latest run without erasing earlier assumptions.
        resp = client.table("valuations").insert(row).execute()
        uid = resp.data[0]["id"]
        logger.info("Inserted valuation %s for %s", uid, vi.company.name)
        return uid
    except Exception as exc:
        # Live databases may still have the legacy UNIQUE(company_name,
        # analysis_date) index until db/migrations.sql is applied.  Preserve the
        # pre-migration behaviour instead of dropping the valuation entirely.
        msg = str(exc)
        if "23505" in msg or "duplicate key" in msg.lower():
            try:
                resp = (
                    client.table("valuations")
                    .upsert(row, on_conflict="company_name,analysis_date")
                    .execute()
                )
                uid = resp.data[0]["id"]
                logger.warning(
                    "Valuation history migration is not applied; overwrote legacy "
                    "same-date row for %s",
                    vi.company.name,
                )
                return uid
            except Exception:
                pass
        logger.warning("Failed to save valuation for %s", vi.company.name)
        return None


def list_valuations(
    company_name: Optional[str] = None,
    market: Optional[str] = None,
    ticker: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List valuations."""
    client = get_client()
    if not client:
        return []

    query = (
        client.table("valuations")
        .select(
            "id, company_name, ticker, market, valuation_method, "
            "analysis_date, total_ev, weighted_value, wacc_pct, "
            "market_price, gap_ratio, created_at"
        )
        .order("created_at", desc=True)
        .limit(limit)
    )
    if ticker:
        query = query.eq("ticker", ticker)
    elif company_name:
        query = query.ilike("company_name", f"%{company_name}%")
    if market:
        query = query.eq("market", market)

    try:
        return query.execute().data
    except Exception:
        logger.warning("Failed to list valuations")
        return []


def list_valuation_history(
    *,
    ticker: Optional[str],
    market: Optional[str],
    company_name: Optional[str] = None,
    limit: int = 50,
) -> list[ValuationHistoryRecord]:
    """Load persisted headline history without rerunning the valuation engine.

    ``ticker + market`` is authoritative.  Name lookup exists only for legacy
    rows whose ticker was never stored.
    """
    client = get_client()
    if not client:
        return []

    select_fields = (
        "company_name,ticker,market,analysis_date,weighted_value,wacc_pct,"
        "market_price,gap_ratio,valuation_method,result_data,created_at"
    )
    query = (
        client.table("valuations")
        .select(select_fields)
        .order("analysis_date", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if ticker and market:
        query = query.eq("ticker", ticker).eq("market", market)
    elif company_name:
        query = query.eq("company_name", company_name)
        if market:
            query = query.eq("market", market)
    else:
        return []

    try:
        rows = query.execute().data
    except Exception:
        logger.warning("Failed to list valuation history")
        return []

    records: list[ValuationHistoryRecord] = []
    # Query the latest N efficiently, then return chronological order for charts.
    for row in reversed(rows):
        result_data = row.get("result_data") or {}
        quality = result_data.get("quality") or {}
        gap_ratio = row.get("gap_ratio")
        records.append(
            ValuationHistoryRecord(
                ticker=row.get("ticker"),
                market=row.get("market"),
                company_name=row.get("company_name"),
                analysis_date=row.get("analysis_date"),
                weighted_value=row.get("weighted_value"),
                market_price=row.get("market_price"),
                gap_pct=gap_ratio * 100 if gap_ratio is not None else None,
                wacc_pct=row.get("wacc_pct"),
                quality_grade=quality.get("grade"),
                primary_method=row.get("valuation_method"),
                valuation_bucket=result_data.get("valuation_bucket"),
                created_at=row.get("created_at"),
                provenance={
                    "weighted_value": Provenance.DERIVED,
                    "market_price": Provenance.REPORTED,
                    "gap_pct": Provenance.DERIVED,
                    "wacc_pct": Provenance.DERIVED,
                },
            )
        )
    return records


def get_valuation(valuation_id: str) -> Optional[dict]:
    """Get valuation detail (including input_data and result_data)."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("valuations")
            .select("*")
            .eq("id", valuation_id)
            .single()
            .execute()
        )
        return resp.data
    except Exception:
        logger.warning("Failed to get valuation %s", valuation_id)
        return None


def delete_valuation(valuation_id: str) -> bool:
    """Delete valuation (CASCADE deletes ai_analyses too)."""
    client = get_client()
    if not client:
        return False

    try:
        client.table("valuations").delete().eq("id", valuation_id).execute()
        return True
    except Exception:
        logger.warning("Failed to delete valuation %s", valuation_id)
        return False


# ── AI Analyses ──


def save_ai_analysis(
    company_name: str,
    step: str,
    result_data: dict,
    model: str = "claude-sonnet-4",
    valuation_id: Optional[str] = None,
) -> Optional[str]:
    """Save AI analysis result per step."""
    client = get_client()
    if not client:
        return None

    row = {
        "company_name": company_name,
        "step": step,
        "result_data": result_data,
        "model": model,
        "valuation_id": valuation_id,
    }

    try:
        resp = client.table("ai_analyses").insert(row).execute()
        uid = resp.data[0]["id"]
        logger.info("Saved AI analysis [%s] %s for %s", step, uid, company_name)
        return uid
    except Exception:
        logger.warning("Failed to save AI analysis [%s] for %s", step, company_name)
        return None


def list_ai_analyses(
    company_name: Optional[str] = None,
    valuation_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """List AI analysis results."""
    client = get_client()
    if not client:
        return []

    query = (
        client.table("ai_analyses")
        .select("id, valuation_id, company_name, step, result_data, model, created_at")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if company_name:
        query = query.ilike("company_name", f"%{company_name}%")
    if valuation_id:
        query = query.eq("valuation_id", valuation_id)

    try:
        return query.execute().data
    except Exception:
        logger.warning("Failed to list AI analyses")
        return []


# ── Profiles ──


def save_profile(
    company_name: str,
    profile_yaml: str,
    profile_data: dict,
    file_name: Optional[str] = None,
) -> Optional[str]:
    """Save YAML profile."""
    client = get_client()
    if not client:
        return None

    row = {
        "company_name": company_name,
        "file_name": file_name,
        "profile_yaml": profile_yaml,
        "profile_data": profile_data,
    }

    try:
        resp = (
            client.table("profiles")
            .upsert(row, on_conflict="company_name,file_name")
            .execute()
        )
        uid = resp.data[0]["id"]
        logger.info("Upserted profile %s for %s", uid, company_name)
        return uid
    except Exception:
        try:
            resp = client.table("profiles").insert(row).execute()
            uid = resp.data[0]["id"]
            logger.info("Inserted profile %s for %s (fallback)", uid, company_name)
            return uid
        except Exception:
            logger.warning("Failed to save profile for %s", company_name)
            return None


def list_profiles(
    company_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """List profiles."""
    client = get_client()
    if not client:
        return []

    query = (
        client.table("profiles")
        .select("id, company_name, file_name, created_at, updated_at")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if company_name:
        query = query.ilike("company_name", f"%{company_name}%")

    try:
        return query.execute().data
    except Exception:
        logger.warning("Failed to list profiles")
        return []


def get_profile(profile_id: str) -> Optional[dict]:
    """Get profile detail."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("profiles").select("*").eq("id", profile_id).single().execute()
        )
        return resp.data
    except Exception:
        logger.warning("Failed to get profile %s", profile_id)
        return None


# ── Discovery Runs ──


def save_discovery_run(run_data: dict) -> Optional[str]:
    """Create weekly analysis run record. Returns UUID on success."""
    client = get_client()
    if not client:
        return None

    try:
        resp = client.table("discovery_runs").insert(run_data).execute()
        uid = resp.data[0]["id"]
        logger.info("Created discovery run %s", uid)
        return uid
    except Exception:
        logger.warning("Failed to save discovery run")
        return None


def update_discovery_run(run_id: str, updates: dict) -> bool:
    """Update run record (status, results, etc.)."""
    client = get_client()
    if not client:
        return False

    try:
        client.table("discovery_runs").update(updates).eq("id", run_id).execute()
        return True
    except Exception:
        logger.warning("Failed to update discovery run %s", run_id)
        return False


def list_discovery_runs(limit: int = 10) -> list[dict]:
    """List recent weekly analysis runs."""
    client = get_client()
    if not client:
        return []

    try:
        resp = (
            client.table("discovery_runs")
            .select(
                "id, run_date, markets, news_count, status, "
                "companies_discovered, companies_analyzed, "
                "errors, duration_seconds, created_at"
            )
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data
    except Exception:
        logger.warning("Failed to list discovery runs")
        return []


# ── Delivery Log ──


def save_delivery_log(log_data: dict) -> Optional[str]:
    """Save weekly delivery record (Gamma URLs, Excel URLs, Gmail draft ID).

    Args:
        log_data: {"week_label", "gamma_urls", "excel_urls", "gmail_draft_id",
                    "discovery_run_id" (optional)}

    Returns:
        UUID on success, None on failure.
    """
    client = get_client()
    if not client:
        return None

    try:
        resp = client.table("delivery_log").insert(log_data).execute()
        uid = resp.data[0]["id"]
        logger.info("Saved delivery log %s for %s", uid, log_data.get("week_label"))
        return uid
    except Exception:
        logger.warning("Failed to save delivery log")
        return None


def get_latest_delivery(week_label: str) -> Optional[dict]:
    """Get delivery log for a specific week."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("delivery_log")
            .select("*")
            .eq("week_label", week_label)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return resp.data[0] if resp.data else None
    except Exception:
        logger.warning("Failed to get delivery log for %s", week_label)
        return None
