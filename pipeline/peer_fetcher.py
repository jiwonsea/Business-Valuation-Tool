"""Automated peer multiple lookup -- real-time data collection from Yahoo Finance.

Separated peer lookup logic requiring IO (HTTP requests) into the pipeline module
to maintain the pure function rule of engine/peer_analysis.py.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import PeerCompany

logger = logging.getLogger(__name__)


def fetch_peer_multiples(peers: list[PeerCompany]) -> list[PeerCompany]:
    """Auto-fetch multiples for peers with tickers from Yahoo Finance.

    Returns a new updated list without modifying the original.
    On lookup failure, existing manual data is preserved.
    """
    from pipeline.yahoo_finance import get_quote_summary

    updated = []
    for p in peers:
        if p.ticker:
            try:
                data = get_quote_summary(p.ticker)
                if data:
                    p = p.model_copy(update={
                        "ev_ebitda": data.get("ev_ebitda") or p.ev_ebitda,
                        "market_cap": data.get("market_cap"),
                        "enterprise_value": data.get("enterprise_value"),
                        "trailing_pe": data.get("trailing_pe"),
                        "forward_pe": data.get("forward_pe"),
                        "beta": data.get("beta"),
                        "source": "yahoo",
                    })
            except Exception as e:
                logger.debug("Peer 멀티플 조회 실패 (%s): %s", p.ticker, e)
        updated.append(p)
    return updated
