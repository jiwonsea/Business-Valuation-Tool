"""Peer 멀티플 자동 조회 — Yahoo Finance에서 실시간 데이터 수집.

engine/peer_analysis.py의 순수 함수 규칙을 유지하기 위해
IO(HTTP 요청)가 필요한 Peer 조회 로직을 pipeline 모듈에 분리.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schemas.models import PeerCompany

logger = logging.getLogger(__name__)


def fetch_peer_multiples(peers: list[PeerCompany]) -> list[PeerCompany]:
    """ticker가 있는 Peer의 멀티플을 Yahoo Finance에서 자동 조회.

    원본 리스트를 변경하지 않고, 업데이트된 새 리스트를 반환한다.
    조회 실패 시 기존 수동 데이터를 유지한다.
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
