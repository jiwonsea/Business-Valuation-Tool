"""Post weekly valuation report to Naver Blog via Selenium.

Status: STUB — implementation pending (Step 6).
This module exists so weekly_run.py can import without error.

Env vars: NAVER_ID, NAVER_PW
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def post_to_naver(summary: dict) -> str | None:
    """Post weekly report to Naver Blog.

    Args:
        summary: The full _weekly_summary.json content.

    Returns:
        Post URL if successful, None otherwise.
    """
    logger.info("Naver Blog posting not yet implemented — skipping.")
    return None
