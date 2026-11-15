"""Auto data collection -> YAML profile generation + AI-driven analysis."""

from __future__ import annotations

import logging
import os
import re
import tempfile
from copy import deepcopy

logger = logging.getLogger(__name__)
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from schemas.models import ValidationReport, ValuationInput, ValuationResult


@dataclass
class AnalyzeResult:
    """Rich return type for auto_analyze() — preserves attribute access."""

    vi: ValuationInput
    result: ValuationResult
    excel_path: str
    summary_md: str
    validation_report: "ValidationReport | None" = None


# Project root (relative to this file's parent directory, not cli.py)
_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_SCENARIO_VALIDATION_RETRIES = 1
_SCENARIO_VALIDATION_RETRY_CAP = 2

# ── no_result failure contract (K-0C) ────────────────────────────────────────
# auto_analyze() returned None for several unrelated reasons and a dozen
# optional steps swallowed their exception; the caller could tell none of them
# apart. A caller that passes ``diagnostics`` now gets the reason: the dict is
# bound to the current context for the duration of that one call and the
# helpers below write to it. With nothing bound (cli, direct calls of the
# functions in this module) every helper does nothing. No helper may raise or
# change what a function returns or writes.

DIAGNOSTICS_CONTRACT = "k0c-1"

IDENTITY_NOT_FOUND = "IDENTITY_NOT_FOUND"  # identify() returned nothing
IDENTITY_MISMATCH = "IDENTITY_MISMATCH"  # resolved, but not as the selected ticker
FINANCIALS_EMPTY = "FINANCIALS_EMPTY"  # fetch_financials() returned nothing
RECONCILIATION_BLOCKED = "RECONCILIATION_BLOCKED"  # hard block, no draft written
DRAFT_NO_YEARS = "DRAFT_NO_YEARS"  # defensive: financials without a year
DRAFT_NOT_WRITTEN = "DRAFT_NOT_WRITTEN"  # no draft and nobody said why
REASON_NOT_REPORTED = "REASON_NOT_REPORTED"  # empty result without a reason
# What auto_analyze() may report for an empty result. scheduler/weekly_run.py
# keeps its own copy (it imports only auto_analyze from here); a test compares.
NO_RESULT_REASONS = frozenset(
    {
        IDENTITY_NOT_FOUND,
        IDENTITY_MISMATCH,
        FINANCIALS_EMPTY,
        RECONCILIATION_BLOCKED,
        DRAFT_NO_YEARS,
        DRAFT_NOT_WRITTEN,
        REASON_NOT_REPORTED,
    }
)

_DIAGNOSTICS: ContextVar[dict | None] = ContextVar("k0c_diagnostics", default=None)

_INVALID = "<invalid>"
_IDENTIFIER_LIMIT = 120
_TICKER_SHAPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.\-]{0,11}")
_CORP_CODE_SHAPE = re.compile(r"\d{8}")
_CIK_SHAPE = re.compile(r"\d{1,10}")
_MARKETS = frozenset({"KR", "US", "JP"})
_LEGAL_STATUSES = frozenset({"상장", "비상장", "listed", "unlisted", "OTC"})

_KR_TICKER = re.compile(r"(\d{6})(?:\.(?:KS|KQ))?")
_JP_TICKER = re.compile(r"(\d{4})(?:\.T)?")
_US_CLASS_TICKER = re.compile(r"([A-Z]{1,5})[.\-]([A-Z])")


def _diag_bind(diagnostics: dict | None) -> dict:
    """Reset the caller's dict (or a throwaway one) for one auto_analyze() call."""
    target = diagnostics if diagnostics is not None else {}
    try:
        target["contract"] = DIAGNOSTICS_CONTRACT
        target["stage"] = "start"
        target["reason_code"] = None
        target["reason_detail"] = {}
        target["degraded"] = []
    except Exception:
        pass  # an unwritable mapping gets no diagnostics, the run is unaffected
    return target


def _diag_stage(stage: str) -> None:
    """Note the stage now running; it is what remains if an exception escapes."""
    try:
        diagnostics = _DIAGNOSTICS.get()
        if diagnostics is not None:
            diagnostics["stage"] = stage
    except Exception:
        pass


def _diag_reason(reason_code: str, detail=None) -> None:
    """Why an empty result is about to be returned. The first reason is kept.

    ``detail`` is a dict or a zero-argument callable building one; it is only
    evaluated when a caller is listening, and a failure in it is swallowed.
    """
    try:
        diagnostics = _DIAGNOSTICS.get()
        if diagnostics is None or diagnostics.get("reason_code"):
            return
        diagnostics["reason_code"] = reason_code
        diagnostics["reason_detail"] = (detail() if callable(detail) else detail) or {}
    except Exception:
        pass


def _diag_degraded(
    step: str,
    exc: BaseException | None = None,
    *,
    with_message: bool = True,
    fields=None,
) -> None:
    """An optional step raised and the run carries on with its fallback.

    ``fields`` is a dict or a zero-argument callable building one. Like the
    detail of _diag_reason() it is evaluated here, inside the guard, and only
    when a caller is listening: nothing is computed for the diagnostics at the
    call site.
    """
    try:
        diagnostics = _DIAGNOSTICS.get()
        if diagnostics is None:
            return
        entry: dict = {"step": step}
        if exc is not None:
            entry["error_type"] = type(exc).__name__
            if with_message:
                from discovery.discovery_engine import redact_text

                entry["message"] = redact_text(exc)
        entry.update((fields() if callable(fields) else fields) or {})
        diagnostics["degraded"].append(entry)
    except Exception:
        pass


def _diag_identifier(value: object) -> str | None:
    """A selection-stage identifier (company name, selected ticker): copied.

    These already appear verbatim in the weekly summary, so they are only
    folded to one line and cut. Masking them would mangle real names.
    """
    if value is None:
        return None
    try:
        return " ".join(str(value).split())[:_IDENTIFIER_LIMIT]
    except Exception:
        return None


def _diag_checked(value: object, shape) -> str | None:
    """An identifier the summary never held before: kept only in its normal shape."""
    if value is None:
        return None
    try:
        text = str(value).strip()
    except Exception:
        return _INVALID
    if not text:
        return None
    if isinstance(shape, frozenset):
        return text if text in shape else _INVALID
    return text if shape.fullmatch(text) else _INVALID


def _comparable_ticker(value: object) -> str | None:
    """Normal form used only to compare a selected ticker with a resolved one.

    None for "no ticker": None, a non-string NaN (float, Decimal, numpy), an
    empty or blank string. Any other string is a symbol, including "N/A" or
    "NONE". Only the notations that name the same listing are folded together:
    005930.KS = 005930, 7203.T = 7203, BRK-B = BRK.B. Dots and hyphens are not
    dropped in general.
    """
    if value is None:
        return None
    try:
        if not isinstance(value, str) and value != value:  # NaN of any numeric type
            return None
        text = "".join(str(value).split()).upper()
    except Exception:
        return None
    if not text:
        return None
    for pattern, form in (
        (_KR_TICKER, r"\1"),
        (_JP_TICKER, r"\1"),
        (_US_CLASS_TICKER, r"\1.\2"),
    ):
        match = pattern.fullmatch(text)
        if match:
            return match.expand(form)
    return text


def _ticker_mismatch(expected: object, resolved: object) -> str | None:
    """None when the resolved company is confirmed as the selected listing.

    Without a selected ticker there is nothing to confirm (cli runs, unlisted
    targets). A different share class or an ADR of the same issuer is a
    mismatch too: the selection named one listing and another one came back.
    """
    want = _comparable_ticker(expected)
    if want is None:
        return None
    have = _comparable_ticker(resolved)
    if have is None:
        return "resolved_ticker_missing"
    return None if have == want else "ticker_differs"


def _load_erp_snapshot(market: str, analysis_date: date) -> dict | None:
    """Load the newest dated ERP snapshot available at the analysis date."""
    directory = _PROJECT_ROOT / "references" / "market_assumptions"
    candidates: list[tuple[date, dict]] = []
    for path in directory.glob(f"{market.lower()}_erp_*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        as_of = date.fromisoformat(str(payload["as_of"]))
        if as_of <= analysis_date:
            candidates.append((as_of, payload))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _load_tax_snapshot(ticker: str, analysis_date: date) -> dict | None:
    directory = _PROJECT_ROOT / "references" / "company_assumptions"
    candidates: list[tuple[date, dict]] = []
    for path in directory.glob(f"{ticker.lower()}_tax_*.yaml"):
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        as_of = date.fromisoformat(str(payload["as_of"]))
        if as_of <= analysis_date:
            candidates.append((as_of, payload))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _profile_is_protected(path: Path) -> bool:
    """Return True when an existing profile must not be auto-overwritten."""
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        return True
    if raw.get("curated") is True:
        return True
    if raw.get("draft") is True or str(raw.get("generated", "")).lower() == "auto":
        return False
    legacy_stub = "auto-generated draft profile" in text.lower() and any(
        "todo" in line.lower()
        for line in text.splitlines()
        if line.lstrip().startswith("#")
    )
    return not legacy_stub


def _llm_quota_remaining() -> int:
    from pipeline.api_guard import ApiGuard

    usage = ApiGuard.get().get_usage_summary()
    return max(
        usage.get("openrouter", {}).get("remaining", 0),
        usage.get("anthropic", {}).get("remaining", 0),
    )


def _atomic_write_yaml(path: str, raw: dict) -> None:
    """Replace a YAML file atomically so shorter rewrites cannot leave stale bytes."""
    destination = os.path.abspath(path)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".tmp",
            dir=os.path.dirname(destination),
            delete=False,
        ) as tmp:
            yaml.dump(
                raw,
                tmp,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = tmp.name
        os.replace(temp_path, destination)
        temp_path = None
        delivered = Path(destination).read_text(encoding="utf-8")
        if not delivered.strip():
            raise RuntimeError(
                f"Atomic YAML write produced an empty file: {destination}"
            )
        if yaml.safe_load(delivered) != raw:
            raise RuntimeError(f"Atomic YAML write verification failed: {destination}")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _write_enrichment_checkpoint(path: str, raw: dict) -> None:
    """Persist enriched inputs as an overwriteable, non-publishable draft."""
    checkpoint = deepcopy(raw)
    checkpoint["draft"] = True
    checkpoint["generated"] = "auto"
    checkpoint["curated"] = False
    if checkpoint.get("scenarios"):
        checkpoint["scenario_validation"] = {"status": "pending"}
    _atomic_write_yaml(path, checkpoint)


def _strip_unsupported_drivers(
    ai_scenarios: list[dict], ai_news_drivers: list[dict], method: str
) -> tuple[list[dict], list[dict], list[str]]:
    """Drop `wacc_adj` from AI output for methods that consume no discount rate.

    Pure: returns new lists plus the places `wacc_adj` was dropped from. For a
    method in DISCOUNT_RATE_METHODS the inputs come back as they are.
    """
    from schemas.models import DISCOUNT_RATE_METHODS

    if method in DISCOUNT_RATE_METHODS:
        return ai_scenarios, ai_news_drivers, []

    dropped: list[str] = []
    scenarios = []
    for sc in ai_scenarios:
        sc = dict(sc)
        for field in ("drivers", "driver_rationale"):
            values = sc.get(field)
            if isinstance(values, dict) and "wacc_adj" in values:
                sc[field] = {k: v for k, v in values.items() if k != "wacc_adj"}
                dropped.append(f"scenarios.{sc.get('code', '?')}.{field}")
        scenarios.append(sc)
    news_drivers = []
    for nd in ai_news_drivers:
        nd = dict(nd)
        effects = nd.get("effects")
        if isinstance(effects, dict) and "wacc_adj" in effects:
            nd["effects"] = {k: v for k, v in effects.items() if k != "wacc_adj"}
            dropped.append(f"news_drivers.{nd.get('id', '?')}.effects")
        news_drivers.append(nd)
    return scenarios, news_drivers, dropped


def _repair_scenarios_safely(
    analyst,
    raw: dict,
    validation_report,
    method: str,
):
    """Attempt one LLM repair without allowing provider failure to abort persistence."""
    initial_report = validation_report
    original_scenarios = deepcopy(raw["scenarios"])
    try:
        repaired_scenarios = _repair_scenarios_with_llm(
            analyst=analyst,
            original=raw["scenarios"],
            errors=validation_report.errors,
            method=method,
        )
        raw["scenarios"] = repaired_scenarios
        validation_report, _ = _compute_scenario_validation(raw, method)
        original_error_set = {
            (error.path, error.code) for error in initial_report.errors
        }
        repeated_error_set = {
            (error.path, error.code) for error in validation_report.errors
        }
        if (
            validation_report.status == "fail"
            and repeated_error_set == original_error_set
        ):
            validation_report = validation_report.model_copy(
                update={"retryable": False}
            )
    except Exception as exc:
        raw["scenarios"] = original_scenarios
        validation_report = initial_report.model_copy(
            update={
                "status": "fail",
                "retryable": False,
                "retry_attempts": 1,
            }
        )
        logger.warning(
            "scenario repair failed",
            extra={
                "exception_type": type(exc).__name__,
                "error_codes": [error.code for error in validation_report.errors],
                "retry_attempts": 1,
            },
        )
    return validation_report


def _is_enrichment_draft(segments, peers, scenarios, validation_report) -> bool:
    """Keep incomplete or non-passing scenario enrichment non-publishable."""
    inputs_complete = bool(segments and peers and scenarios)
    validation_ok = validation_report is None or validation_report.status == "ok"
    return not (inputs_complete and validation_ok)


def _emit_peers_batch_coverage(
    company: str,
    requested_codes: list[str],
    returned_codes: set[str],
    parse_failed: bool,
    fallback_calls: int,
) -> None:
    """Emit batch coverage without changing the peer recommendation contract."""
    from ai.telemetry import call_context, emit

    with call_context(company, "peers_batch"):
        emit(
            "peers_batch_coverage",
            requested_segments=len(requested_codes),
            returned_segments=len(returned_codes),
            missing_codes=[
                code for code in requested_codes if code not in returned_codes
            ],
            parse_failed=parse_failed,
            fallback_calls=fallback_calls,
        )


def _compute_scenario_validation(raw: dict, method: str):
    from engine.scenario_validator import validate_scenario_differentiation
    from valuation_runner import load_profile, run_valuation

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".yaml",
            delete=False,
        ) as tmp:
            yaml.dump(
                raw, tmp, allow_unicode=True, default_flow_style=False, sort_keys=False
            )
            temp_path = tmp.name
        vi = load_profile(temp_path)
        result = run_valuation(vi)
        ev_by_scenario = {
            code: scenario.total_ev for code, scenario in result.scenarios.items()
        }
        report = validate_scenario_differentiation(
            raw.get("scenarios", {}), method, ev_by_scenario
        )
        return report, ev_by_scenario
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _repair_scenarios_with_llm(
    analyst, original: dict, errors: list, method: str
) -> dict:
    import json

    from ai.prompts import SYSTEM_ANALYST, SYSTEM_ANALYST_DRIVERS
    from ai.llm_client import MODEL_HEAVY

    payload = json.dumps({"scenarios": original}, ensure_ascii=False, indent=2)
    errors_json = json.dumps(
        [error.model_dump() for error in errors],
        ensure_ascii=False,
        indent=2,
    )
    prompt = f"""Validation failed. Fix only the invalid fields and keep all valid fields unchanged.

Rules:
- Return valid JSON only.
- Preserve scenario keys and all unchanged valid fields exactly.
- Keep the same valuation method: {method}.
- Do not add new assumptions unless required to satisfy validation.
- Bull, Base, and Bear must differ materially in at least two allowed drivers.
- Bull EV must exceed Bear EV by at least 1.3x.

Errors:
{errors_json}

Current scenario payload:
{payload}
"""
    repaired = analyst._ask_json(
        prompt,
        system=SYSTEM_ANALYST + "\n" + SYSTEM_ANALYST_DRIVERS,
        max_tokens=4096,
        model=MODEL_HEAVY,
    )
    if "scenarios" in repaired and isinstance(repaired["scenarios"], dict):
        return repaired["scenarios"]
    if isinstance(repaired, dict):
        return repaired
    raise ValueError("repair response did not contain a scenarios object")


def _fetch_industry_metadata(identity) -> dict:
    """Collect registry industry codes without replacing an existing industry label."""
    metadata = {
        "industry": getattr(identity, "industry", "") or "",
        "industry_code": None,
        "industry_code_label": None,
        "industry_source": None,
    }
    try:
        if identity.market == "US" and identity.cik:
            from pipeline.edgar_client import get_submissions

            response = get_submissions(identity.cik)
            code = response.get("sic")
            label = response.get("sicDescription")
            prefix, source = "SIC", "edgar_submissions"
        elif identity.market == "KR" and identity.corp_code:
            from pipeline.dart_client import get_single_company_info

            response = get_single_company_info(identity.corp_code)
            code = response.get("induty_code")
            label = response.get("induty_name")
            prefix, source = "KSIC", "dart_company"
        else:
            return metadata
        if not code:
            raise ValueError("Registry response has no industry code")
        metadata.update(
            industry=metadata["industry"] or label or "",
            industry_code=f"{prefix}:{code}",
            industry_code_label=label,
            industry_source=source,
        )
    except Exception as exc:
        # Authenticated HTTP exception text can contain an API key in its URL.
        logger.warning(
            "Authoritative industry unavailable for %s (%s)",
            identity.name,
            type(exc).__name__,
        )
        # Same rule for the diagnostics: the class name only, never the text.
        _diag_degraded("industry_metadata", exc, with_message=False)
    return metadata


def auto_fetch(
    company_query: str,
    market_hint: str | None = None,
    *,
    expected_ticker: str | None = None,
) -> dict:
    """Company name/ticker input -> auto-detect market -> collect financials -> return raw dict.

    Args:
        market_hint: "KR" or "US" — bypasses heuristic detection. Pass when the caller
            already knows the market (e.g. weekly discovery pipeline) to avoid
            Korean-named US companies (e.g. "테슬라") triggering DART lookups.
        expected_ticker: ticker the caller selected. When given, a company that
            resolves to a different ticker (or to none) is rejected before any
            financials are fetched: the name lookup can land on another listed
            company ("SK Hynix" -> "SK", "LG Electronics" -> "LG"). None = no check.

    Returns {} on failure, as before. The reason goes to the diagnostics a
    caller of auto_analyze() passed, if any (K-0C).
    """
    _diag_stage("identify")
    from pipeline.data_fetcher import DataFetcher

    fetcher = DataFetcher()

    # Step 1: Company identification
    print(f"\n[1/3] 기업 식별 중: '{company_query}'")
    identity = fetcher.identify(company_query, market_hint=market_hint)
    if not identity:
        print(f"  [ERROR] 기업을 찾을 수 없습니다: {company_query}")
        _diag_reason(
            IDENTITY_NOT_FOUND,
            lambda: {
                "query": _diag_identifier(company_query),
                "market_hint": _diag_checked(market_hint, _MARKETS),
                "expected_ticker": _diag_identifier(expected_ticker),
            },
        )
        return {}

    market_label = {
        "KR": "한국 (DART)",
        "US": "미국 (SEC EDGAR)",
        "JP": "일본 (EDINET)",
    }.get(identity.market, identity.market)
    print(f"  → {identity.name} | {market_label}")
    if identity.ticker:
        print(f"    Ticker: {identity.ticker}")
    if identity.cik:
        print(f"    CIK: {identity.cik}")
    if identity.corp_code:
        print(f"    DART corp_code: {identity.corp_code}")

    mismatch = _ticker_mismatch(expected_ticker, identity.ticker)
    if mismatch:
        print(
            "  [ERROR] 식별된 종목이 선정된 종목과 다릅니다 "
            f"(선정 {_diag_identifier(expected_ticker)} / "
            f"식별 {_diag_checked(identity.ticker, _TICKER_SHAPE)}) — 평가를 중단합니다."
        )
        _diag_reason(
            IDENTITY_MISMATCH,
            lambda: {
                "kind": mismatch,
                "query": _diag_identifier(company_query),
                "market_hint": _diag_checked(market_hint, _MARKETS),
                "expected_ticker": _diag_identifier(expected_ticker),
                "resolved_ticker": _diag_checked(identity.ticker, _TICKER_SHAPE),
                "resolved_market": _diag_checked(identity.market, _MARKETS),
                "resolved_corp_code": _diag_checked(
                    identity.corp_code, _CORP_CODE_SHAPE
                ),
                "resolved_cik": _diag_checked(identity.cik, _CIK_SHAPE),
            },
        )
        return {}

    # Step 2: Financial statement collection
    _diag_stage("financials")
    print("\n[2/3] 재무제표 수집 중...")
    financials = fetcher.fetch_financials(identity)
    if not financials:
        print("  [ERROR] 재무제표를 수집할 수 없습니다.")
        _diag_reason(
            FINANCIALS_EMPTY,
            lambda: {
                "resolved_market": _diag_checked(identity.market, _MARKETS),
                "resolved_ticker": _diag_checked(identity.ticker, _TICKER_SHAPE),
                "legal_status": _diag_checked(identity.legal_status, _LEGAL_STATUSES),
                "has_corp_code": bool(identity.corp_code),
                "has_cik": bool(identity.cik),
            },
        )
        return {}

    for year, data in sorted(financials.items(), reverse=True):
        rev = data.get("revenue", 0)
        op = data.get("op", 0)
        unit = (
            "$M"
            if identity.market == "US"
            else ("百万円" if identity.market == "JP" else "백만원")
        )
        print(f"  {year}: 매출 {rev:,}{unit}, 영업이익 {op:,}{unit}")

    # Step 3: Share count / market data
    _diag_stage("shares")
    print("\n[3/3] 시장 데이터 수집 중...")
    shares_info = fetcher.fetch_shares(identity)
    if shares_info.get("shares_total"):
        print(f"  총 주식수: {shares_info['shares_total']:,}")
    if shares_info.get("price"):
        currency = shares_info.get("currency", "")
        print(f"  현재가: {shares_info['price']:,.2f} {currency}")

    # Step 4: Auto-generate YAML profile
    _diag_stage("draft_profile")
    industry_metadata = _fetch_industry_metadata(identity)
    yaml_path = _generate_draft_profile(
        identity, financials, shares_info, industry_metadata=industry_metadata
    )
    if not yaml_path:
        # Kept only if the draft step gave no reason of its own (first one wins).
        _diag_reason(DRAFT_NOT_WRITTEN)

    print(f"\n{'=' * 60}")
    print(f"데이터 수집 완료: {identity.name}")
    print(f"시장: {identity.market} | 연도: {sorted(financials.keys())}")
    print(f"{'=' * 60}")
    if yaml_path:
        print(f"\n[Draft YAML 생성됨] {yaml_path}")
        print("  → 부문 데이터, 멀티플, 시나리오를 편집한 후:")
        print(f"    python cli.py --profile {yaml_path} --excel")

    return {
        "identity": identity,
        "financials": financials,
        "shares": shares_info,
        "yaml_path": yaml_path,
    }


def _estimate_wacc_params(cons: dict, shares_info: dict, market: str, identity) -> dict:
    """Data-driven automatic WACC parameter estimation.

    Key principles:
    - D/E: interest-bearing debt (gross_borr) / market cap (not total liabilities / book equity)
    - Tax: min(max(effective_tax, 0), statutory_max)
    - Beta: yfinance -> Hamada unlevering
    - Kd: |interest_expense| / gross_borr
    - Equity weight: market_cap / (market_cap + gross_borr)
    """
    is_us = market == "US"
    is_jp = market == "JP"
    # Market-specific defaults
    rf = 4.25 if is_us else (1.00 if is_jp else 3.50)
    erp = 5.50 if is_us else (6.00 if is_jp else 7.00)
    statutory_tax = 21.0 if is_us else (30.0 if is_jp else 25.0)
    default_bu = 1.0 if is_us else (0.85 if is_jp else 0.75)
    default_kd = rf + 2.0

    market_price = shares_info.get("price", 0)
    shares_total = shares_info.get("shares_total", 0)
    gross_borr = cons.get("gross_borr", 0)
    interest_expense = cons.get("interest_expense", 0)

    # Fetch beta from yfinance
    levered_beta = shares_info.get("beta")  # Passed from fetch_shares
    if levered_beta is None:
        # Try directly from yfinance_fetcher
        try:
            from pipeline.yfinance_fetcher import fetch_market_data

            if identity.ticker:
                md = fetch_market_data(identity.ticker, market)
                if md:
                    levered_beta = md.get("beta")
        except Exception:
            pass

    # Market cap calculation (same unit as financial statements: million KRW / $M)
    # price * shares = raw currency -> / 1,000,000 -> financial statement unit
    market_cap = 0.0
    if market_price > 0 and shares_total > 0:
        market_cap = market_price * shares_total / 1_000_000

    # --- Tax rate: clamp effective tax rate ---
    from pipeline.macro_data import calc_effective_tax_rate

    effective_tax = calc_effective_tax_rate({0: cons})  # dummy year key
    analysis_date = getattr(identity, "analysis_date", None) or date.today()
    tax_snapshot = (
        _load_tax_snapshot(identity.ticker, analysis_date) if identity.ticker else None
    )
    forward_tax = shares_info.get("forward_tax_rate")
    if forward_tax is None and tax_snapshot:
        forward_tax = tax_snapshot["value_pct"]
    if forward_tax is not None:
        tax = float(forward_tax)
    elif effective_tax is not None:
        tax = min(max(effective_tax, 0.0), statutory_tax)
    else:
        tax = statutory_tax * 0.85  # Conservative default

    # --- D/E ratio: gross_borr / market_cap ---
    if market_cap > 0 and gross_borr > 0:
        de_ratio = round(gross_borr / market_cap * 100, 1)
    elif market_cap > 0:
        de_ratio = 0.0
    else:
        # Unlisted: use interest-bearing debt (gross_borr) / book equity
        # NOT total liabilities / book equity — that inflates D/E by including trade payables etc.
        equity_bv = cons.get("equity", 0)
        de_ratio = (
            round(gross_borr / equity_bv * 100, 1)
            if equity_bv > 0 and gross_borr > 0
            else 50.0
        )

    # --- Equity weight in capital structure ---
    if market_cap > 0:
        eq_w = round(market_cap / (market_cap + max(gross_borr, 0)) * 100, 1)
    else:
        eq_w = round(100 / (1 + de_ratio / 100), 1)

    erp_snapshot = _load_erp_snapshot(market, analysis_date)
    erp_provenance = None
    if erp_snapshot:
        erp = float(erp_snapshot["value_pct"])
        rf = float(erp_snapshot.get("risk_free_rate_pct", rf))
        source = erp_snapshot["source"]
        erp_provenance = {
            "status": "consumed_snapshot",
            "as_of": str(erp_snapshot["as_of"]),
            "method": erp_snapshot["method"],
            "provider": source["provider"],
            "url": source["url"],
        }

    beta_provenance = None
    if identity.ticker and market_cap > 0:
        try:
            from engine.normalize import resolve_beta
            from pipeline.beta_observation import collect_beta_observation

            observation, digest, _ = collect_beta_observation(
                identity.ticker, market, analysis_date
            )
            resolution = resolve_beta(
                evaluation_date=analysis_date,
                is_listed=True,
                observation=observation,
                de_ratio_pct=de_ratio,
                tax_rate_pct=tax,
                use_blume=True,
            )
            if not resolution.consumed:
                raise ValueError(resolution.reason)
            bu = round(float(resolution.normalized_value), 3)
            beta_provenance = {
                "status": resolution.status,
                "as_of": observation.window_end.isoformat(),
                "method": observation.calculation_method,
                "provider": observation.equity_beta.source,
                "url": observation.equity_beta.url,
                "source_hash": digest,
                "observation_count": observation.observation_count,
                "benchmark": observation.benchmark,
                "raw_levered_beta": resolution.raw_levered_beta,
                "blume_adjusted": resolution.blume_adjusted,
                "normalized_bu": resolution.normalized_value,
                "window_start": observation.window_start.isoformat(),
                "window_end": observation.window_end.isoformat(),
                "frequency": observation.frequency,
                "calculation_method": observation.calculation_method,
            }
        except Exception as exc:
            logger.warning(
                "Beta observation unavailable; profile remains draft: %s", exc
            )
            _diag_degraded("beta_observation", exc)
            bu = default_bu
            beta_provenance = {
                "status": "blocked_no_provenance",
                "method": "ols_weekly_log_returns_adjusted_close",
            }
    else:
        bu = default_bu

    # --- Kd_pre: |interest_expense| / gross_borr ---
    if gross_borr > 0 and interest_expense != 0:
        kd_pre = round(abs(interest_expense) / gross_borr * 100, 2)
        # Clamp to range: [rf, rf + 5%]
        kd_pre = max(rf, min(kd_pre, rf + 5.0))
    else:
        kd_pre = default_kd

    return {
        "rf": rf,
        "erp": erp,
        "bu": bu,
        "de": de_ratio,
        "tax": round(tax, 1),
        "kd_pre": kd_pre,
        "eq_w": eq_w,
        "beta_provenance": beta_provenance,
        "erp_provenance": erp_provenance,
        "tax_provenance": (
            {
                "status": "consumed_guidance",
                "as_of": str(tax_snapshot["as_of"]),
                "method": tax_snapshot["method"],
                "provider": tax_snapshot["source"]["provider"],
                "url": tax_snapshot["source"]["url"],
            }
            if tax_snapshot
            else None
        ),
    }


def _generate_draft_profile(
    identity,
    financials: dict,
    shares_info: dict,
    industry_metadata: dict | None = None,
) -> str | None:
    """Auto-generate a draft YAML profile from collected data."""
    years = sorted(financials.keys())
    if not years:
        _diag_reason(DRAFT_NO_YEARS)
        return None

    latest = years[-1]
    cons = financials[latest]

    # ── Cross-source reconciliation gate (BVT-1 / A4) ──
    # Default: warn + persist findings under data_reconciliation:.
    # Hard block (no YAML written) only for shares 25% / market cap 25% /
    # unit 100% identity failures — see pipeline/reconciliation.py.
    from pipeline.reconciliation import reconcile_market_data

    recon = reconcile_market_data(financials, shares_info, market=identity.market)
    for finding in recon.findings:
        if finding.severity in ("warn", "block"):
            tag = "BLOCK" if finding.severity == "block" else "WARN"
            print(f"  [{tag}][정합성] {finding.message}")
    if recon.blocked:
        print(
            "  [ERROR] 데이터 정합성 하드 블록 — 프로필 생성 중단. "
            "소스 간 주식수/시가총액/단위 불일치를 확인하세요."
        )

        def _blocked_checks() -> dict:
            from discovery.discovery_engine import redact_text

            return {
                "checks": [
                    {
                        "check": _diag_identifier(finding.check),
                        "rel_diff_pct": finding.rel_diff_pct,
                        "message": redact_text(finding.message),
                    }
                    for finding in recon.findings
                    if finding.severity == "block"
                ]
            }

        _diag_reason(RECONCILIATION_BLOCKED, _blocked_checks)
        return None

    is_us = identity.market == "US"
    is_jp = identity.market == "JP"
    currency = "USD" if is_us else ("JPY" if is_jp else "KRW")
    unit = "$M" if is_us else ("百万円" if is_jp else "백만원")
    source_name = "SEC EDGAR" if is_us else ("EDINET" if is_jp else "DART")

    shares_total = shares_info.get("shares_total", 0)
    shares_ordinary = shares_info.get("shares_ordinary", shares_total)
    shares_preferred = shares_info.get("shares_preferred", 0)
    treasury_shares = shares_info.get("treasury_shares", 0)

    equity_bv = cons.get("equity", 0)
    cons.get("liabilities", 0)
    net_debt = cons.get("net_borr", 0)
    market_price = shares_info.get("price", 0)

    # Auto-estimate WACC parameters
    wacc_est = _estimate_wacc_params(cons, shares_info, identity.market, identity)
    rf = wacc_est["rf"]
    erp = wacc_est["erp"]
    bu = wacc_est["bu"]
    tax = wacc_est["tax"]
    kd_pre = wacc_est["kd_pre"]
    de_ratio = wacc_est["de"]
    eq_w = wacc_est["eq_w"]
    beta_provenance_block = yaml.safe_dump(
        {"beta_provenance": wacc_est.get("beta_provenance")},
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()
    erp_provenance_block = yaml.safe_dump(
        {"erp_provenance": wacc_est.get("erp_provenance")},
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()
    tax_provenance_block = yaml.safe_dump(
        {"tax_provenance": wacc_est.get("tax_provenance")},
        sort_keys=False,
        allow_unicode=True,
    ).rstrip()

    financial_anchor = "fy"
    ttm_blocks = ""
    if is_us and identity.cik:
        try:
            from pipeline.edgar_parser import parse_ttm_financials

            analysis_as_of = identity.analysis_date
            if isinstance(analysis_as_of, str):
                analysis_as_of = date.fromisoformat(analysis_as_of)
            ttm_result = parse_ttm_financials(
                identity.cik,
                latest,
                computed_as_of=analysis_as_of,
            )
            if ttm_result:
                ttm_anchor, ttm_provenance = ttm_result
                financial_anchor = "ttm"
                ttm_blocks = yaml.safe_dump(
                    {
                        "ttm_anchor": ttm_anchor,
                        "ttm_provenance": ttm_provenance,
                    },
                    sort_keys=False,
                    allow_unicode=True,
                ).rstrip()
        except Exception as exc:
            logger.warning("TTM anchor unavailable; FY fallback: %s", exc)
            _diag_degraded("ttm_anchor", exc)

    # Generate filename
    safe_name = re.sub(r"[^\w\-]", "_", identity.name.lower().replace(" ", "_"))
    if identity.ticker:
        safe_name = re.sub(r"[^\w\-]", "_", identity.ticker.lower())
    yaml_filename = f"profiles/{safe_name}.yaml"
    destination = _PROJECT_ROOT / yaml_filename
    if _profile_is_protected(destination):
        yaml_filename = f"profiles/staging/{safe_name}.yaml"
        logger.warning(
            "Protected profile not overwritten: %s; generated draft staged at %s",
            destination,
            _PROJECT_ROOT / yaml_filename,
        )
        print(
            f"  [WARN] 기존 큐레이션 프로필 보호: {destination.name} — "
            f"자동 초안은 {yaml_filename}에 저장합니다."
        )
    yaml_path = str(_PROJECT_ROOT / yaml_filename)

    # Consolidated financials YAML block (via yaml.dump for safe serialization)
    _cons_fields = [
        "revenue",
        "op",
        "net_income",
        "assets",
        "liabilities",
        "equity",
        "dep",
        "amort",
        "gross_borr",
        "net_borr",
        "de_ratio",
    ]
    cons_dict = {}
    for yr in years:
        d = financials[yr]
        cons_dict[yr] = {k: d.get(k, 0) for k in _cons_fields}
    cons_yaml = yaml.dump(
        cons_dict, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    # Indent to match top-level "consolidated:" key
    cons_block = "\n".join("  " + line for line in cons_yaml.strip().splitlines())

    net_debt = cons.get("net_borr", 0)

    # Auto-fetch macro data
    from pipeline.macro_data import get_terminal_growth, get_diluted_shares
    from engine.growth import generate_growth_rates

    terminal_growth = get_terminal_growth(identity.market)

    # Dynamically generate EBITDA growth rates (industry base-rate -> market convergence via linear decay)
    _industry = getattr(identity, "industry", "") or ""
    growth_rates = generate_growth_rates(
        financials,
        market=identity.market,
        industry=_industry,
    )
    growth_rates_str = "[" + ", ".join(f"{r:.2f}" for r in growth_rates) + "]"
    # Note: tax rate is already clamped in _estimate_wacc_params()

    # ── Auto-derive capex_to_da and da_to_ebitda from historical actuals ──
    # Prefer 3-year averages over single-year point-in-time ratios.
    capex_ratios = []
    da_ebitda_ratios = []
    for yr in years:
        d = financials[yr]
        da = d.get("dep", 0) + d.get("amort", 0)
        ebitda = d.get("op", 0) + da
        capex = d.get("capex", 0)
        if da > 0 and capex > 0:
            capex_ratios.append(capex / da)
        if ebitda > 0 and da > 0:
            da_ebitda_ratios.append(da / ebitda)

    # Capex/DA ratio: use historical average, fallback to 1.10
    if capex_ratios:
        capex_to_da_auto = round(sum(capex_ratios) / len(capex_ratios), 2)
        # Sanity clamp: 0.3x (light asset) ~ 5.0x (heavy capex like semiconductors)
        capex_to_da_auto = max(0.3, min(capex_to_da_auto, 5.0))
    else:
        capex_to_da_auto = 1.10  # Default: maintenance capex ≈ D&A

    # 3-year average DA/EBITDA ratio
    if da_ebitda_ratios:
        da_to_ebitda_avg = round(sum(da_ebitda_ratios) / len(da_ebitda_ratios), 4)
    else:
        da_to_ebitda_avg = None  # Will be computed inside DCF engine from latest year

    # Actual capex (latest year) — passed to DCFParams for precise first-year CapEx
    actual_capex_latest = cons.get("capex", 0) or 0

    # Auto capex_fade_to: when latest-year capex/DA spikes above historical avg,
    # fade back to historical average over projection period (investment cycle normalization)
    capex_fade_to_auto = None
    latest_da = cons.get("dep", 0) + cons.get("amort", 0)
    if actual_capex_latest > 0 and latest_da > 0:
        latest_ratio = actual_capex_latest / latest_da
        hist_avg = capex_to_da_auto if capex_ratios else 1.10
        # Trigger: latest ratio ≥ 3x AND at least 50% above historical average
        if latest_ratio >= 3.0 and latest_ratio > hist_avg * 1.5:
            capex_fade_to_auto = round(max(hist_avg, 1.2), 2)

    # Diluted shares (reflecting SBC/stock options) -- only if DART share data unavailable
    if identity.ticker and shares_preferred == 0 and treasury_shares == 0:
        diluted = get_diluted_shares(identity.ticker, identity.market)
        if diluted and diluted > shares_total:
            shares_total = diluted
            shares_ordinary = diluted

    # Outstanding ordinary shares (basis for per-share calculation)
    shares_outstanding = shares_ordinary - treasury_shares
    if shares_outstanding <= 0:
        shares_outstanding = shares_ordinary or shares_total

    # Auto-calculate cross-validation multiples (based on collected financials + market data)
    pe_multiple = 0.0
    ev_revenue_multiple = 0.0
    pbv_multiple = 0.0
    if market_price > 0 and shares_outstanding > 0:
        mcap = market_price * shares_outstanding / 1_000_000  # In million KRW / $M
        net_inc = cons.get("net_income", 0)
        revenue = cons.get("revenue", 0)
        if net_inc > 0:
            pe_multiple = round(mcap / net_inc, 1)
        if revenue > 0:
            ev = mcap + max(net_debt, 0)
            ev_revenue_multiple = round(ev / revenue, 1)
        if equity_bv > 0:
            pbv_multiple = round(mcap / equity_bv, 1)

    # Warning for potential financial subsidiary ownership
    fin_subsidiary_warn = ""
    if not is_us and de_ratio > 150:
        industry = getattr(identity, "industry", "") or ""
        warn_keywords = ["자동차", "건설", "지주", "종합상사", "금융"]
        if any(kw in identity.name or kw in industry for kw in warn_keywords):
            fin_subsidiary_warn = (
                "\n# ⚠ WARNING: D/E > 150% + 금융자회사 보유 가능 업종."
                "\n#   부문 분리 SOTP(Mixed Method) 검토 필요."
                "\n#   segments에 method: pbv, segment_net_debt 추가 고려."
            )

    industry_block = ""
    if industry_metadata is not None:
        industry_yaml = yaml.safe_dump(
            industry_metadata, sort_keys=False, allow_unicode=True
        ).rstrip()
        industry_block = "\n".join("  " + line for line in industry_yaml.splitlines())

    content = f"""# {identity.name} — Auto-generated draft profile
# Source: {source_name} | Generated by valuation-tool
# TODO: Add segment data, multiples, and scenario parameters{fin_subsidiary_warn}

draft: true
generated: auto
curated: false

company:
  name: "{identity.name}"
  legal_status: "{"상장" if is_us or identity.legal_status in ("상장", "listed") else "비상장"}"
  market: "{identity.market}"
  currency: "{currency}"
  currency_unit: "{unit}"
  ticker: {f'"{identity.ticker}"' if identity.ticker else "null"}
  cik: {f'"{identity.cik}"' if identity.cik else "null"}
  corp_code: {f'"{identity.corp_code}"' if identity.corp_code else "null"}
  shares_total: {shares_total}
  shares_ordinary: {shares_ordinary}
  shares_preferred: {shares_preferred}
  treasury_shares: {treasury_shares}
  analysis_date: "{date.today().isoformat()}"
{industry_block}

# TODO: Define business segments (REQUIRED for SOTP)
segments:
  MAIN:
    name: "Main Business"
    multiple: 10.0   # TODO: Set appropriate EV/EBITDA multiple

# TODO: Add segment-level financials (revenue, op, assets per segment)
segment_data:
  {latest}:
    MAIN: {{revenue: {cons.get("revenue", 0)}, gross_profit: 0, op: {cons.get("op", 0)}, assets: {cons.get("assets", 0)}}}

consolidated:
{cons_block}

wacc_params:
  rf: {rf}
  erp: {erp}
  bu: {bu}
  de: {de_ratio}
  tax: {tax}
  kd_pre: {kd_pre}
  eq_w: {eq_w}

{beta_provenance_block}
{erp_provenance_block}
{tax_provenance_block}

# TODO: Design scenarios appropriate for this company
scenarios:
  Base:
    name: "Base Case"
    prob: 50
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: 0
    terminal_growth_adj: 0
    desc: "Base case with consensus estimates"
  Bull:
    name: "Bull Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: 0
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: 20
    terminal_growth_adj: 0.3
    desc: "Upside scenario"
  Bear:
    name: "Bear Case"
    prob: 25
    ipo: "N/A"
    irr: null
    dlom: {"0" if identity.legal_status in ("상장", "listed") else "20"}
    cps_repay: 0
    rcps_repay: 0
    buyback: 0
    shares: {shares_outstanding}
    growth_adj_pct: -25
    terminal_growth_adj: -0.3
    desc: "Downside scenario"

dcf_params:
  ebitda_growth_rates: {growth_rates_str}
  tax_rate: {tax}
  capex_to_da: {capex_to_da_auto}{"  # auto-derived from " + str(len(capex_ratios)) + "-yr historical avg" if capex_ratios else "  # default (no capex data available)"}
  nwc_to_rev_delta: 0.05
  terminal_growth: {terminal_growth}
  actual_capex: {actual_capex_latest if actual_capex_latest > 0 else "null"}{"  # latest-year actual CapEx" if actual_capex_latest > 0 else ""}
  capex_fade_to: {capex_fade_to_auto if capex_fade_to_auto else "null"}{"  # auto: fade capex/DA " + f"{latest_ratio:.1f}x → {capex_fade_to_auto}x over projection" if capex_fade_to_auto else ""}
  da_to_ebitda_override: {round(da_to_ebitda_avg, 4) if da_to_ebitda_avg else "null"}{"  # 3-yr avg D&A/EBITDA" if da_to_ebitda_avg else "  # null = computed from latest year in DCF engine"}

# Cross-validation multiples (Trading Multiple -- reverse-engineered from current market price)
# Recommended to replace with independent peer-based multiples
pe_multiple: {pe_multiple}
ev_revenue_multiple: {ev_revenue_multiple}
pbv_multiple: {pbv_multiple}

cps_principal: 0
cps_years: 0
net_debt: {net_debt}
eco_frontier: 0
base_year: {latest}
financial_anchor: {financial_anchor}
{ttm_blocks}

peers: []
  # TODO: Add peer companies
  # - {{name: "Peer Co", segment_code: "MAIN", ev_ebitda: 10.0, notes: ""}}
"""
    # ── 순차입금 정규화 원장 (PLAN §2.1 / P0-1) ──
    # `net_debt:` 스칼라는 legacy 정의(gross − cash)로 남는다. 엔진은 reconciled is True일
    # 때만 아래 구성요소의 정의값을 소비한다 (engine/normalize.py).
    nd_components = cons.get("net_debt_components")
    if nd_components is not None:
        from engine.normalize import resolve_net_debt

        nd_res = resolve_net_debt(nd_components, net_debt)
        nd_payload = nd_components.model_dump(
            exclude={"reconciled", "reconciliation_delta"}
        )
        content += (
            "\n# 순차입금 정규화 원장 (PLAN §2.1 / P0-1)\n"
            f"# 게이트: {nd_res.status} — {nd_res.reason}\n"
            f"normalization_version: {nd_res.normalization_version}\n"
            + yaml.dump(
                {"net_debt_components": nd_payload},
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )
        )

    # Persist reconciliation results (audit trail; survives --auto enrichment
    # because auto_analyze round-trips the full YAML dict).
    recon_yaml = yaml.dump(
        {"data_reconciliation": recon.to_dict()},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    content += (
        "\n# Cross-source data reconciliation (auto-generated by pipeline/reconciliation.py)\n"
        + recon_yaml
    )

    Path(yaml_path).parent.mkdir(parents=True, exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)

    return yaml_filename


def auto_analyze(
    company_query: str,
    output_dir: str | None = None,
    scored_data: dict | None = None,
    *,
    diagnostics: dict | None = None,
):
    """AI-driven end-to-end automated analysis.

    1. Data collection (auto_fetch)
    2. AI designs segments / multiples / scenarios
    3. Enrich YAML profile
    4. Run valuation + Excel output

    Args:
        scored_data: Pre-computed data from scoring phase (market_cap_usd, etc.)
                     to avoid redundant API calls in the weekly pipeline.
        diagnostics: optional dict this call fills in (K-0C). Keys: ``contract``,
            ``stage`` (the stage running last, also when an exception escapes),
            ``reason_code`` / ``reason_detail`` (set whenever None is returned,
            one of NO_RESULT_REASONS) and ``degraded`` (optional steps that
            raised and were replaced by a fallback). Pass a fresh dict per
            call. The return value does not depend on it.
    """
    token = _DIAGNOSTICS.set(_diag_bind(diagnostics))
    try:
        result = _auto_analyze(company_query, output_dir, scored_data)
        if result is None:
            # Only lands if no step gave a reason (a replaced auto_fetch, say).
            _diag_reason(REASON_NOT_REPORTED, {"reported": None})
        return result
    finally:
        _DIAGNOSTICS.reset(token)


def _auto_analyze(
    company_query: str,
    output_dir: str | None,
    scored_data: dict | None,
):
    """Body of auto_analyze(); runs with the caller's diagnostics bound."""
    from valuation_runner import load_profile, run_valuation
    from output.console_report import print_report

    # Step 1: Data collection — pass market hint from scoring to avoid wrong registry lookups
    _market_hint = (scored_data or {}).get("market")
    fetch_result = auto_fetch(
        company_query,
        market_hint=_market_hint,
        expected_ticker=(scored_data or {}).get("ticker"),
    )
    if not fetch_result or not fetch_result.get("yaml_path"):
        print("[ERROR] 데이터 수집 실패. --auto 중단.")
        return None

    _diag_stage("enrichment")
    yaml_path = str(_PROJECT_ROOT / fetch_result["yaml_path"])
    identity = fetch_result["identity"]
    financials = fetch_result["financials"]

    # Step 2: AI analysis
    print(f"\n{'=' * 60}")
    print(f"[AI 분석 시작] {identity.name}")
    print(f"{'=' * 60}")

    try:
        from ai.analyst import AIAnalyst

        analyst = AIAnalyst()
    except Exception as e:
        print(f"[WARN] AI 모듈 로드 실패 ({e}). Draft YAML로 진행합니다.")
        _diag_degraded("ai_module", e)
        _diag_stage("valuation")
        vi = load_profile(yaml_path)
        result = run_valuation(vi)
        print_report(vi, result)
        _diag_stage("export")
        from output.excel_builder import export

        try:
            from orchestrator import _save_to_db

            _save_to_db(vi, result, yaml_path)
        except Exception as db_exc:
            logger.debug("auto_analyze DB save skipped")
            _diag_degraded("db_save_call", db_exc)
        path = export(vi, result, output_dir)
        print(f"\n[Excel] 저장 완료: {path}")
        from orchestrator import format_summary

        return AnalyzeResult(
            vi=vi,
            result=result,
            excel_path=str(path),
            summary_md=format_summary(vi, result),
        )

    latest = max(financials.keys())
    cons = financials[latest]

    # Revenue composition text
    revenue_text = (
        f"총 매출: {cons.get('revenue', 0):,}, 영업이익: {cons.get('op', 0):,}"
    )

    # AI Step 2: Segment classification
    print("[AI 2/6] 부문 분류 중...")
    try:
        seg_result = analyst.classify_segments(identity.name, revenue_text)
        segments = seg_result.get("segments", [])
        print(f"  → {len(segments)}개 부문 식별")
    except Exception as e:
        print(f"  [WARN] 부문 분류 실패: {e}")
        _diag_degraded("segments", e)
        segments = []

    # AI Step 3: Peer / multiple recommendation (batch)
    peers_all = []
    multiples_ai = {}
    if segments:
        print("[AI 3/6] Peer 기업 추천 중...")
        batch_ok = False
        batch_parse_failed = False
        batch_returned_codes = set()
        fallback_calls = 0
        try:
            batch_result = analyst.recommend_peers_batch(
                identity.name, segments, market=identity.market
            )
            for seg in segments:
                code = seg.get("code", "MAIN")
                seg_data = batch_result.get(code, {})
                if not seg_data or "peers" not in seg_data:
                    continue
                batch_returned_codes.add(code)
                for p in seg_data.get("peers", []):
                    peers_all.append(
                        {
                            "name": p["name"],
                            "segment_code": code,
                            "ev_ebitda": p.get("ev_ebitda", 10.0),
                            "notes": p.get("notes", ""),
                        }
                    )
                multiples_ai[code] = seg_data.get("recommended_multiple", 10.0)
                print(
                    f"  → {code}: {seg_data.get('recommended_multiple', '?')}x "
                    f"({len(seg_data.get('peers', []))} peers)"
                )
            batch_ok = len(multiples_ai) == len(segments)
        except Exception as e:
            batch_parse_failed = True
            logger.warning(
                "Batch peer recommendation failed: %s — falling back to per-segment", e
            )

        # Fallback: per-segment calls for any missing segments
        peer_failures: list = []
        peer_failure: Exception | None = None
        if not batch_ok:
            for seg in segments:
                code = seg.get("code", "MAIN")
                if code in multiples_ai:
                    continue
                fallback_calls += 1
                name = seg.get("name", "Main")
                try:
                    peer_result = analyst.recommend_peers(
                        identity.name,
                        code,
                        name,
                        seg.get("peer_group", ""),
                    )
                    for p in peer_result.get("peers", []):
                        peers_all.append(
                            {
                                "name": p["name"],
                                "segment_code": code,
                                "ev_ebitda": p.get("ev_ebitda", 10.0),
                                "notes": p.get("notes", ""),
                            }
                        )
                    multiples_ai[code] = peer_result.get("recommended_multiple", 10.0)
                    print(
                        f"  → {code}: {peer_result.get('recommended_multiple', '?')}x "
                        f"({len(peer_result.get('peers', []))} peers)"
                    )
                except Exception as e:
                    print(f"  [WARN] {code} Peer 추천 실패: {e}")
                    multiples_ai[code] = 10.0
                    peer_failures.append(code)
                    peer_failure = e
        if peer_failure is not None:
            # A failed batch that the per-segment calls repaired is not recorded:
            # only segments left with the 10.0 placeholder are.
            _diag_degraded(
                "peers",
                peer_failure,
                fields=lambda: {
                    "segments": [
                        re.sub(r"[^A-Za-z0-9_.\-]", "", str(code))[:40]
                        for code in peer_failures[:20]
                    ]
                },
            )

        requested_codes = [seg.get("code", "MAIN") for seg in segments]
        _emit_peers_batch_coverage(
            identity.name,
            requested_codes,
            batch_returned_codes,
            batch_parse_failed,
            fallback_calls,
        )

    # AI Step 4: WACC recommendation
    print("[AI 4/6] WACC 추정 중...")
    equity = cons.get("equity", 0)
    gross_borr_for_wacc = cons.get("gross_borr", 0)
    # Use interest-bearing debt / book equity (not total liabilities / equity)
    de_ratio = (
        round(gross_borr_for_wacc / equity * 100, 1)
        if equity > 0 and gross_borr_for_wacc > 0
        else 50.0
    )
    try:
        wacc_result = analyst.suggest_wacc(
            identity.name, de_ratio, "", market=identity.market
        )
        print(f"  → WACC ≈ {wacc_result.get('wacc_estimate', '?')}%")
    except Exception as e:
        print(f"  [WARN] WACC 추정 실패: {e}")
        _diag_degraded("wacc", e)
        wacc_result = {}

    # AI Step 5a: News collection -> key issues summary
    print("[AI 5/6] 관련 뉴스 수집 중...")
    news = None
    key_issues = ""
    try:
        from discovery.news_collector import NewsCollector
        from discovery.discovery_engine import summarize_key_issues

        collector = NewsCollector()
        news = collector.collect_for_company(identity.name, identity.market)
        if news:
            print(f"  → {len(news)}건 수집")
            key_issues = summarize_key_issues(news, identity.name, identity.market)
            if key_issues:
                print("  → 핵심 이슈 요약 완료")
        else:
            print("  → 관련 뉴스 없음 (범용 시나리오로 진행)")
    except Exception as e:
        print(f"  [WARN] 뉴스 수집 실패: {e}. 범용 시나리오로 진행합니다.")
        _diag_degraded("news", e)

    # Fetch market signals for scenario calibration (Phase 4)
    market_signals = None
    try:
        from pipeline.market_signals import fetch_market_signals

        print("[Signals] 시장 데이터 수집 중...")
        market_signals = fetch_market_signals(
            ticker=getattr(identity, "ticker", None),
            market=getattr(identity, "market", "KR"),
            company_name=identity.name,
            news=news if news else None,
        )
        if market_signals and market_signals.has_any():
            print("  → 시장 신호 수집 완료")
        else:
            print("  → 시장 신호 없음 (프롬프트 보강 없이 진행)")
            market_signals = None
    except Exception as e:
        print(f"  [WARN] 시장 신호 수집 실패: {e}. 기존 방식으로 진행합니다.")
        _diag_degraded("market_signals", e)

    # AI Step 5b: Scenario design (news-based key_issues + multi-driver)
    print("[AI 6/6] 시나리오 설계 중...")
    legal = identity.legal_status

    # Determine valuation method -> pass to AI for method-aware driver generation
    try:
        from engine.method_selector import suggest_method

        val_method = suggest_method(
            n_segments=len(segments) if segments else 1,
            legal_status=legal,
            industry=getattr(identity, "industry", "") or "",
            de_ratio=cons.get("de_ratio", 0.0),
        )
    except Exception as method_exc:
        _diag_degraded("method_selection", method_exc)
        val_method = "dcf_primary"

    try:
        # Pass industry + ev_rev for optionality pre-screen (no extra LLM call)
        _industry = getattr(identity, "industry", "") or ""
        # Infer EV/Revenue from scored_data market cap (if available) vs financial revenue
        _market_cap_usd = (scored_data or {}).get("market_cap_usd", 0)
        _revenue_usd = cons.get("revenue", 0)
        _ev_rev = (
            round(_market_cap_usd / (_revenue_usd * 1e6), 1)
            if _market_cap_usd and _revenue_usd
            else 0.0
        )
        _currency = "$M" if getattr(identity, "market", "KR") == "US" else "억원"
        _seg_codes = (
            [seg.get("code", f"S{i}") for i, seg in enumerate(segments)]
            if segments
            else None
        )
        sc_result = analyst.design_scenarios(
            identity.name,
            legal,
            key_issues,
            valuation_method=val_method,
            industry=_industry,
            ev_rev_multiple=_ev_rev,
            currency_unit=_currency,
            signals=market_signals,
            segment_codes=_seg_codes,
        )
        ai_scenarios = sc_result.get("scenarios", [])
        opt_segs = sc_result.get("optionality_segments", [])
        if opt_segs:
            print(
                f"  → 옵셔널리티 세그먼트 {len(opt_segs)}개 감지됨: {[s['name'] for s in opt_segs]}"
            )
        print(f"  → {len(ai_scenarios)}개 시나리오 (멀티 드라이버, {val_method})")
    except Exception as e:
        import traceback

        print(f"  [WARN] 시나리오 설계 실패: {e}")
        traceback.print_exc()
        _diag_degraded("scenarios", e)
        ai_scenarios = []
        opt_segs = []

    # Step 3: Enrich YAML
    print(f"\n[YAML 보강 중] {yaml_path}")
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Update segment information
    if segments:
        raw["segments"] = {}
        seg_data_update = {}
        for seg in segments:
            code = seg.get("code", "MAIN")
            raw["segments"][code] = {
                "name": seg.get("name", code),
                "multiple": multiples_ai.get(code, 10.0),
            }
            share = seg.get("revenue_share_pct", 100.0 / len(segments)) / 100
            seg_data_update[code] = {
                "revenue": round(cons.get("revenue", 0) * share),
                "gross_profit": 0,
                "op": round(cons.get("op", 0) * share),
                "assets": round(cons.get("assets", 0) * share),
            }
        raw["segment_data"] = {latest: seg_data_update}

    # Update WACC parameters
    if wacc_result:
        for key in ["rf", "erp", "bu", "kd_pre", "tax"]:
            if key in wacc_result:
                raw["wacc_params"][key] = wacc_result[key]

    # Save news key issues (for audit trail)
    if key_issues:
        raw["news_key_issues"] = key_issues

    # Update scenarios (multi-variable news drivers / backward-compatible with direct assignment)
    if ai_scenarios:
        # Outstanding ordinary shares (ordinary - treasury) basis
        _ord = raw["company"].get("shares_ordinary", raw["company"]["shares_total"])
        _trs = raw["company"].get("treasury_shares", 0)
        shares = _ord - _trs if _trs > 0 else _ord

        # Save news drivers (multi-variable approach -- when AI-generated)
        # Strip structured fields from effects (they belong on scenarios, not drivers)
        _STRUCTURED_EFFECT_KEYS = {"segment_multiples", "segment_ebitda"}
        ai_news_drivers = sc_result.get("news_drivers", []) if sc_result else []
        for nd in ai_news_drivers:
            if "effects" in nd:
                nd["effects"] = {
                    k: v
                    for k, v in nd["effects"].items()
                    if k not in _STRUCTURED_EFFECT_KEYS
                }
        # SOTP/NAV/Multiples consume no discount rate: wacc_adj is not persisted
        ai_scenarios, ai_news_drivers, dropped = _strip_unsupported_drivers(
            ai_scenarios, ai_news_drivers, val_method
        )
        if dropped:
            print(
                f"  [WARN] wacc_adj {len(dropped)}건 제거 — "
                f"{val_method}는 할인율을 소비하지 않음"
            )
        if ai_news_drivers:
            raw["news_drivers"] = ai_news_drivers

        raw["scenarios"] = {}
        for sc in ai_scenarios:
            code = sc.get("code", "A")
            sc_dict = {
                "name": sc.get("name", f"Scenario {code}"),
                "prob": sc.get("prob", 33),
                "ipo": "N/A",
                "irr": None,
                "dlom": sc.get("dlom", 0),
                "cps_repay": 0,
                "rcps_repay": 0,
                "buyback": 0,
                "shares": shares,
                "desc": sc.get("description", ""),
                "probability_rationale": sc.get("probability_rationale", ""),
            }
            # Multi-variable news driver approach (active_drivers)
            if "active_drivers" in sc:
                sc_dict["active_drivers"] = sc["active_drivers"]
            # Legacy direct assignment approach (fallback -- when no news_drivers)
            drivers = sc.get("drivers", {})
            for field in (
                "growth_adj_pct",
                "terminal_growth_adj",
                "market_sentiment_pct",
                "wacc_adj",
                "ddm_growth",
                "ev_multiple",
                "rim_roe_adj",
                "nav_discount",
            ):
                if field in drivers:
                    val = drivers[field]
                    # ddm_growth/ev_multiple: 0 means "not set" -> convert to None
                    if field in ("ddm_growth", "ev_multiple") and val == 0:
                        val = None
                    sc_dict[field] = val
            # Structured per-segment overrides (SOTP scenarios)
            for seg_field in ("segment_ebitda", "segment_multiples", "segment_revenue"):
                val = sc.get(seg_field) or drivers.get(seg_field)
                if val and isinstance(val, dict):
                    sc_dict[seg_field] = val
            # Per-driver rationale
            dr = sc.get("driver_rationale", {})
            if dr:
                sc_dict["driver_rationale"] = dr
            raw["scenarios"][code] = sc_dict

    # Warn if news existed but AI scenarios were not generated
    if key_issues and not ai_scenarios:
        print(
            "  [WARN] 뉴스 기반 이슈가 존재하나 AI 시나리오 생성 실패. 범용 시나리오가 유지됩니다."
        )

    # Apply optionality segments (AI-detected binary-outcome segments)
    if opt_segs:
        latest = max(
            raw.get("segment_data", {}).keys(), default=raw.get("base_year", 2025)
        )
        for opt_seg in opt_segs:
            code = opt_seg.get("code", "")
            if not code:
                continue
            # Add to segments with optionality flag + ev_revenue method
            raw.setdefault("segments", {})[code] = {
                "name": opt_seg.get("name", code),
                "multiple": opt_seg.get("multiple", 15.0),
                "optionality": True,
                "method": "ev_revenue",
            }
            # Add to segment_data with op=0, revenue from AI estimate
            base_rev = int(opt_seg.get("base_revenue", 0))
            for yr_data in raw.get("segment_data", {}).values():
                yr_data.setdefault(
                    code, {"revenue": base_rev, "gross_profit": 0, "op": 0, "assets": 0}
                )
            raw.setdefault("multiples", {})[code] = opt_seg.get("multiple", 15.0)
            # Write per-scenario revenue overrides — warn explicitly on code mismatch
            sc_revenue = opt_seg.get("scenario_revenue", {})
            valid_sc_codes = set(raw.get("scenarios", {}).keys())
            matched = 0
            for sc_code, rev_val in sc_revenue.items():
                if sc_code in valid_sc_codes:
                    raw["scenarios"][sc_code].setdefault("segment_revenue", {})[
                        code
                    ] = int(rev_val)
                    matched += 1
                else:
                    print(
                        f"  [WARN] 옵셔널리티 세그먼트 '{code}': scenario_revenue 키 '{sc_code}'가 "
                        f"시나리오 코드 {sorted(valid_sc_codes)}와 불일치 — 해당 값 무시됨"
                    )
            if sc_revenue and matched == 0:
                print(
                    f"  [WARN] 옵셔널리티 세그먼트 '{code}': 모든 scenario_revenue 키 불일치. "
                    f"AI 응답의 scenario_revenue 키가 scenarios[].code와 동일해야 함."
                )
        print(
            f"  → 옵셔널리티 세그먼트 YAML 반영 완료: {[s['code'] for s in opt_segs]}"
        )

    # Update peers
    if peers_all:
        raw["peers"] = peers_all

    # Recalculate growth rates using segment names as industry hint
    # (Segment names are richer than yfinance's generic "Auto Manufacturers" etc.)
    if segments:
        from engine.growth import generate_growth_rates
        from engine.method_selector import classify_industry

        seg_name_text = " ".join(s.get("name", "") for s in segments)
        # Only override if segment names provide a stronger classification signal
        seg_category = classify_industry(seg_name_text)
        id_category = classify_industry(getattr(identity, "industry", "") or "")
        if seg_category != "default" or id_category == "default":
            # Segment names give better signal, or identity industry is also generic
            updated_rates = generate_growth_rates(
                financials,
                market=identity.market,
                industry=seg_name_text,
            )
            rates_str = "[" + ", ".join(f"{r:.2f}" for r in updated_rates) + "]"
            raw.setdefault("dcf_params", {})["ebitda_growth_rates"] = updated_rates
            print(f"  [Growth rates updated from segments: {rates_str}]")

    _write_enrichment_checkpoint(yaml_path, raw)

    validation_report = None
    validation_retry_attempts = 0
    if raw.get("scenarios"):
        initial_report, _ = _compute_scenario_validation(raw, val_method)
        validation_report = initial_report
        retry_limit = min(
            _DEFAULT_SCENARIO_VALIDATION_RETRIES,
            _SCENARIO_VALIDATION_RETRY_CAP,
        )
        if (
            validation_report.status == "fail"
            and validation_report.retryable
            and retry_limit > 0
        ):
            if _llm_quota_remaining() < 1:
                validation_report = validation_report.model_copy(
                    update={
                        "status": "skipped",
                        "retryable": False,
                    }
                )
                logger.info(
                    "scenario_validation",
                    extra={
                        "status": validation_report.status,
                        "retry_attempts": 0,
                        "quota_skip_reason": "llm_quota_exhausted",
                        "error_codes": [
                            error.code for error in validation_report.errors
                        ],
                    },
                )
            else:
                validation_retry_attempts = 1
                validation_report = _repair_scenarios_safely(
                    analyst, raw, validation_report, val_method
                )
        if validation_report is not None:
            validation_report = validation_report.model_copy(
                update={"retry_attempts": validation_retry_attempts}
            )
            raw["scenario_validation"] = validation_report.model_dump()
            logger.info(
                "scenario_validation",
                extra={
                    "status": validation_report.status,
                    "retry_attempts": validation_retry_attempts,
                    "error_codes": [error.code for error in validation_report.errors],
                },
            )

    # Enable Monte Carlo simulation
    raw["mc_enabled"] = True

    # Persist market price + relative-valuation inputs so the diagnostic layer
    # (P/E, P/B, PEG/PEGY, justified multiples) is available on profile reruns.
    _shares_info = (
        fetch_result.get("shares", {}) if isinstance(fetch_result, dict) else {}
    )
    _mp = _shares_info.get("price")
    if _mp and not raw.get("market_price"):
        raw["market_price"] = _mp
    _rel_metrics = dict(_shares_info.get("rel_metrics") or {})
    if _rel_metrics:
        if _rel_metrics.get("earnings_growth") is not None:
            _rel_metrics.setdefault("growth_source", "analyst consensus")
        raw["relative_inputs"] = _rel_metrics

    # The initial file is always a draft. Clear that explicit marker only when
    # the enrichment produced the minimum curation inputs; the investability
    # gate performs the stricter value/reconciliation checks afterwards.
    raw["draft"] = _is_enrichment_draft(
        segments,
        peers_all,
        raw.get("scenarios"),
        validation_report,
    )
    raw["generated"] = "auto"
    raw.setdefault("curated", False)

    _atomic_write_yaml(yaml_path, raw)

    print("  → YAML 저장 완료")

    # Step 4: Run valuation
    print(f"\n{'=' * 60}")
    print("[밸류에이션 실행]")
    print(f"{'=' * 60}")

    _diag_stage("valuation")
    vi = load_profile(yaml_path)
    result = run_valuation(vi)

    # Auto-compare valuation gap for listed companies
    from cli import _fetch_and_compare_market_price

    result = _fetch_and_compare_market_price(vi, result)

    print_report(vi, result)

    _diag_stage("export")
    from output.excel_builder import export

    try:
        from orchestrator import _save_to_db

        _save_to_db(vi, result, yaml_path)
    except Exception as db_exc:
        logger.debug("auto_analyze DB save skipped")
        _diag_degraded("db_save_call", db_exc)
    path = export(vi, result, output_dir)
    print(f"\n[Excel] 저장 완료: {path}")

    from orchestrator import format_summary

    return AnalyzeResult(
        vi=vi,
        result=result,
        excel_path=str(path),
        summary_md=format_summary(vi, result),
        validation_report=validation_report,
    )
