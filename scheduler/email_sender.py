"""Send weekly valuation report email + error alerts.

Provider priority (auto-detected from env vars):
  1. Resend  — RESEND_API_KEY set  (recommended: resend.com, free 3K/month)
  2. Gmail SMTP — GMAIL_ADDRESS + GMAIL_APP_PASSWORD set

Resend env vars: RESEND_API_KEY, RESEND_FROM (e.g. "Valuation Bot <bot@yourdomain.com>"), GMAIL_RECIPIENT
Gmail env vars:  GMAIL_ADDRESS, GMAIL_APP_PASSWORD, GMAIL_RECIPIENT
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def _send_via_resend(subject: str, html_body: str, recipient: str) -> bool:
    """Send email via Resend API (resend.com). Returns True on success."""
    try:
        import resend
    except ImportError:
        logger.debug("resend package not installed — skipping Resend")
        return False

    api_key = os.getenv("RESEND_API_KEY", "")
    sender = os.getenv("RESEND_FROM", "Valuation Bot <onboarding@resend.dev>")
    if not api_key:
        return False

    resend.api_key = api_key
    try:
        resp = resend.Emails.send({
            "from": sender,
            "to": [recipient],
            "subject": subject,
            "html": html_body,
        })
        logger.info("Resend email sent: id=%s", resp.get("id", "?"))
        return True
    except Exception as e:
        logger.error("Resend send failed: %s", e)
        return False


def _send_via_gmail(subject: str, html_body: str, sender: str, password: str, recipient: str) -> bool:
    """Send email via Gmail SMTP. Returns True on success."""
    msg = MIMEMultipart("alternative")
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        logger.info("Gmail email sent to %s", recipient)
        return True
    except Exception as e:
        logger.error("Gmail send failed: %s", e)
        return False


def _get_recipient() -> str:
    """Resolve email recipient from env vars."""
    return (
        os.getenv("GMAIL_RECIPIENT", "")
        or os.getenv("GMAIL_ADDRESS", "")
    )


def send_weekly_email(summary: dict) -> bool:
    """Send weekly report email. Auto-selects Resend → Gmail SMTP.

    Args:
        summary: The full _weekly_summary.json content (with download_url in valuations).

    Returns:
        True if sent successfully, False otherwise.
    """
    from .delivery import build_gmail_html

    recipient = _get_recipient()
    if not recipient:
        logger.warning("No email recipient configured (GMAIL_RECIPIENT / GMAIL_ADDRESS).")
        return False

    label = summary.get("label", "Weekly Report")
    subject = f"[주간 밸류에이션] {label}"
    html_body = build_gmail_html(summary, gamma_urls={})

    # Try Resend first
    if os.getenv("RESEND_API_KEY"):
        if _send_via_resend(subject, html_body, recipient):
            return True

    # Fallback: Gmail SMTP
    address = os.getenv("GMAIL_ADDRESS", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if address and password:
        return _send_via_gmail(subject, html_body, address, password, recipient)

    logger.warning(
        "No email provider configured. Set RESEND_API_KEY (recommended) "
        "or GMAIL_ADDRESS + GMAIL_APP_PASSWORD."
    )
    return False


def send_error_alert(phase: str, error: str) -> bool:
    """Send error alert email when a publishing phase fails.

    Args:
        phase: The phase that failed (e.g., "WordPress", "YouTube", "Naver Blog").
        error: Error message or traceback.

    Returns:
        True if sent successfully, False otherwise.
    """
    recipient = _get_recipient()
    if not recipient:
        logger.warning("No email recipient — error alert not sent for %s", phase)
        return False

    subject = f"[자동 발행 실패] {phase}"
    body_html = (
        f"<p><b>Phase:</b> {phase}<br>"
        f"<b>Time:</b> {datetime.now().isoformat()}<br>"
        f"<b>Error:</b></p><pre>{error}</pre>"
    )
    body_plain = f"Phase: {phase}\nTime: {datetime.now().isoformat()}\nError:\n{error}\n"

    # Try Resend first
    if os.getenv("RESEND_API_KEY"):
        if _send_via_resend(subject, body_html, recipient):
            return True

    # Fallback: Gmail SMTP
    address = os.getenv("GMAIL_ADDRESS", "")
    password = os.getenv("GMAIL_APP_PASSWORD", "")
    if address and password:
        msg = MIMEMultipart("alternative")
        msg["From"] = address
        msg["To"] = recipient
        msg["Subject"] = subject
        msg.attach(MIMEText(body_plain, "plain", "utf-8"))
        try:
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
                server.starttls()
                server.login(address, password)
                server.sendmail(address, [recipient], msg.as_string())
            logger.info("Error alert sent for %s", phase)
            return True
        except Exception as e:
            logger.error("Failed to send error alert: %s", e)
            return False

    logger.warning("No email provider — error alert not sent for %s", phase)
    return False
