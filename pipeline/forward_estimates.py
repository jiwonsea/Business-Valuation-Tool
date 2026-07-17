"""Collect dated analyst-consensus snapshots outside valuation runtime."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

from schemas.models import ForwardAnchor, ForwardEstimateMetric

_ROOT = Path(__file__).resolve().parent.parent


def _atomic_json(path: Path, payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise OSError(f"forward snapshot verification failed: {path}")
    return digest


def _frame_rows(frame) -> dict[str, dict]:
    return {
        str(index): {
            str(key): None if value != value else value.item() if hasattr(value, "item") else value
            for key, value in row.items()
        }
        for index, row in frame.iterrows()
    }


def collect_forward_anchor(
    ticker: str,
    analysis_date: date,
    *,
    target_fiscal_year: int | None = None,
    revenue_divisor: float = 1_000_000,
    revenue_unit: str = "$M",
) -> ForwardAnchor:
    """Fetch consensus and map relative rows using the provider fiscal-year end."""
    import yfinance as yf

    security = yf.Ticker(ticker)
    info = security.info
    next_end_raw = info.get("nextFiscalYearEnd")
    if not next_end_raw:
        raise ValueError("yfinance did not provide nextFiscalYearEnd")
    next_end = datetime.fromtimestamp(int(next_end_raw), timezone.utc).date()
    target_fiscal_year = target_fiscal_year or next_end.year
    if target_fiscal_year == next_end.year:
        relative_period = "0y"
        fiscal_end = next_end
    elif target_fiscal_year == next_end.year + 1:
        relative_period = "+1y"
        # Yahoo exposes no explicit period end for +1y. Do not fabricate one by
        # calendar arithmetic or promote the relative row to an FY label.
        fiscal_end = None
    else:
        raise ValueError("target fiscal year is not available in 0y/+1y consensus")

    revenue_rows = _frame_rows(security.revenue_estimate)
    earnings_rows = _frame_rows(security.earnings_estimate)
    revenue_row = revenue_rows.get(relative_period) or {}
    earnings_row = earnings_rows.get(relative_period) or {}
    retrieved_at = datetime.now(timezone.utc)
    payload = {
        "ticker": ticker,
        "provider": "yfinance",
        "as_of": analysis_date.isoformat(),
        "retrieved_at": retrieved_at.isoformat(),
        "relative_period": relative_period,
        "fiscal_period": f"FY{str(target_fiscal_year)[-2:]}" if fiscal_end else None,
        "fiscal_period_end": fiscal_end.isoformat() if fiscal_end else None,
        "revenue_estimate": revenue_rows,
        "earnings_estimate": earnings_rows,
    }
    path = _ROOT / ".cache" / "forward_estimates" / f"{ticker}_{analysis_date}.json"
    digest = _atomic_json(path, payload)

    revenue = None
    if revenue_row.get("avg") is not None and revenue_row.get("numberOfAnalysts"):
        revenue = ForwardEstimateMetric(
            value=float(revenue_row["avg"]) / revenue_divisor,
            unit=revenue_unit,
            n_analysts=int(revenue_row["numberOfAnalysts"]),
        )
    eps = None
    if earnings_row.get("avg") is not None and earnings_row.get("numberOfAnalysts"):
        eps = ForwardEstimateMetric(
            value=float(earnings_row["avg"]),
            unit="USD/share",
            n_analysts=int(earnings_row["numberOfAnalysts"]),
        )
    return ForwardAnchor(
        provider="yfinance",
        as_of=analysis_date,
        retrieved_at=retrieved_at,
        relative_period=relative_period,
        fiscal_period=payload["fiscal_period"],
        fiscal_period_end=fiscal_end,
        source_hash=digest,
        revenue=revenue,
        eps=eps,
    )
