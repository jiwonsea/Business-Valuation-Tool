"""Automated peer multiple lookup -- real-time data collection from Yahoo Finance.

Separated peer lookup logic requiring IO (HTTP requests) into the pipeline module
to maintain the pure function rule of engine/peer_analysis.py.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import PeerCompany

logger = logging.getLogger(__name__)

_MAX_WORKERS = 6  # Parallel Yahoo Finance lookups


def _fetch_single_peer(p: PeerCompany) -> PeerCompany:
    """Fetch multiples for a single peer (called in thread pool)."""
    if not p.ticker:
        return p
    try:
        from pipeline.yahoo_finance import get_quote_summary

        data = get_quote_summary(p.ticker)
        if data:
            p = p.model_copy(
                update={
                    "ev_ebitda": data.get("ev_ebitda") or p.ev_ebitda,
                    "market_cap": data.get("market_cap"),
                    "enterprise_value": data.get("enterprise_value"),
                    "trailing_pe": data.get("trailing_pe"),
                    "forward_pe": data.get("forward_pe"),
                    "beta": data.get("beta"),
                    "source": "yahoo",
                }
            )
    except Exception as e:
        logger.debug("Peer multiple lookup failed (%s): %s", p.ticker, e)
    return p


def fetch_peer_multiples(peers: list[PeerCompany]) -> list[PeerCompany]:
    """Auto-fetch multiples for peers with tickers from Yahoo Finance.

    Returns a new updated list without modifying the original.
    On lookup failure, existing manual data is preserved.
    Uses parallel requests for speed (up to _MAX_WORKERS concurrent).
    """
    if not peers:
        return []

    workers = min(len(peers), _MAX_WORKERS)
    updated: list[PeerCompany] = [None] * len(peers)  # type: ignore[list-item]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_idx = {
            pool.submit(_fetch_single_peer, p): i for i, p in enumerate(peers)
        }
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            updated[idx] = fut.result()

    return updated
