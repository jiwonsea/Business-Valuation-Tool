"""Supabase CRUD — 밸류에이션, AI 분석, 프로필 저장/조회."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from schemas.models import ValuationInput, ValuationResult
from .client import get_client

logger = logging.getLogger(__name__)


def _serialize_date(obj):
    """date 객체를 ISO 문자열로 변환 (JSON 직렬화용)."""
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ── Valuations ──


def save_valuation(
    vi: ValuationInput,
    result: ValuationResult,
) -> Optional[str]:
    """밸류에이션 입력+결과를 저장. 성공 시 UUID 반환."""
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
        resp = (
            client.table("valuations")
            .upsert(row, on_conflict="company_name,analysis_date")
            .execute()
        )
        uid = resp.data[0]["id"]
        logger.info("Upserted valuation %s for %s", uid, vi.company.name)
        return uid
    except Exception:
        logger.exception("Failed to save valuation for %s", vi.company.name)
        return None


def list_valuations(
    company_name: Optional[str] = None,
    market: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """밸류에이션 목록 조회."""
    client = get_client()
    if not client:
        return []

    query = (
        client.table("valuations")
        .select("id, company_name, ticker, market, valuation_method, "
                "analysis_date, total_ev, weighted_value, wacc_pct, "
                "market_price, gap_ratio, created_at")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if company_name:
        query = query.ilike("company_name", f"%{company_name}%")
    if market:
        query = query.eq("market", market)

    try:
        return query.execute().data
    except Exception:
        logger.exception("Failed to list valuations")
        return []


def get_valuation(valuation_id: str) -> Optional[dict]:
    """밸류에이션 상세 조회 (input_data, result_data 포함)."""
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
        logger.exception("Failed to get valuation %s", valuation_id)
        return None


def delete_valuation(valuation_id: str) -> bool:
    """밸류에이션 삭제 (CASCADE로 ai_analyses도 삭제)."""
    client = get_client()
    if not client:
        return False

    try:
        client.table("valuations").delete().eq("id", valuation_id).execute()
        return True
    except Exception:
        logger.exception("Failed to delete valuation %s", valuation_id)
        return False


# ── AI Analyses ──


def save_ai_analysis(
    company_name: str,
    step: str,
    result_data: dict,
    model: str = "claude-sonnet-4",
    valuation_id: Optional[str] = None,
) -> Optional[str]:
    """AI 분석 단계별 결과 저장."""
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
        logger.exception("Failed to save AI analysis [%s] for %s", step, company_name)
        return None


def list_ai_analyses(
    company_name: Optional[str] = None,
    valuation_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """AI 분석 결과 목록 조회."""
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
        logger.exception("Failed to list AI analyses")
        return []


# ── Profiles ──


def save_profile(
    company_name: str,
    profile_yaml: str,
    profile_data: dict,
    file_name: Optional[str] = None,
) -> Optional[str]:
    """YAML 프로필 저장."""
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
        logger.exception("Failed to save profile for %s", company_name)
        return None


def list_profiles(
    company_name: Optional[str] = None,
    limit: int = 20,
) -> list[dict]:
    """프로필 목록 조회."""
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
        logger.exception("Failed to list profiles")
        return []


def get_profile(profile_id: str) -> Optional[dict]:
    """프로필 상세 조회."""
    client = get_client()
    if not client:
        return None

    try:
        resp = (
            client.table("profiles")
            .select("*")
            .eq("id", profile_id)
            .single()
            .execute()
        )
        return resp.data
    except Exception:
        logger.exception("Failed to get profile %s", profile_id)
        return None


# ── Discovery Runs ──


def save_discovery_run(run_data: dict) -> Optional[str]:
    """주간 분석 실행 기록 생성. 성공 시 UUID 반환."""
    client = get_client()
    if not client:
        return None

    try:
        resp = client.table("discovery_runs").insert(run_data).execute()
        uid = resp.data[0]["id"]
        logger.info("Created discovery run %s", uid)
        return uid
    except Exception:
        logger.exception("Failed to save discovery run")
        return None


def update_discovery_run(run_id: str, updates: dict) -> bool:
    """실행 기록 업데이트 (상태, 결과 등)."""
    client = get_client()
    if not client:
        return False

    try:
        client.table("discovery_runs").update(updates).eq("id", run_id).execute()
        return True
    except Exception:
        logger.exception("Failed to update discovery run %s", run_id)
        return False


def list_discovery_runs(limit: int = 10) -> list[dict]:
    """최근 주간 분석 실행 목록."""
    client = get_client()
    if not client:
        return []

    try:
        resp = (
            client.table("discovery_runs")
            .select("id, run_date, markets, news_count, status, "
                    "companies_discovered, companies_analyzed, "
                    "errors, duration_seconds, created_at")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return resp.data
    except Exception:
        logger.exception("Failed to list discovery runs")
        return []
