"""Send weekly valuation report email via Gmail SMTP.

Uses smtplib (stdlib) — no external dependencies.
Env vars: GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GMAIL_RECIPIENT
"""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def send_weekly_email(summary: dict) -> bool:
    """Send weekly report email with Supabase download links.

    Args:
        summary: The full _weekly_summary.json content (with download_url in valuations).

    Returns:
        True if sent successfully, False otherwise.
    """
    address = os.getenv("GMAIL_ADDRESS", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    recipient = os.getenv("GMAIL_RECIPIENT", "") or address

    if not address or not password:
        logger.warning("GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set — skipping email.")
        return False

    from .delivery import build_gmail_html

    label = summary.get("label", "Weekly Report")
    subject = f"[주간 밸류에이션] {label}"
    html_body = build_gmail_html(summary, gamma_urls={})

    msg = MIMEMultipart("alternative")
    msg["From"] = address
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.starttls()
            server.login(address, password)
            server.sendmail(address, [recipient], msg.as_string())
        logger.info("Weekly email sent to %s", recipient)
        return True
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
