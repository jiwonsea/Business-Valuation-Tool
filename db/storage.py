"""Supabase Storage — Excel upload + signed URL generation."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from .client import get_client

logger = logging.getLogger(__name__)

BUCKET = "valuation-excels"
SIGNED_URL_EXPIRY = 30 * 24 * 3600  # 30 days


def ensure_bucket() -> bool:
    """Create the storage bucket if it doesn't exist. Returns True on success."""
    client = get_client()
    if not client:
        return False

    try:
        client.storage.get_bucket(BUCKET)
        return True
    except Exception:
        pass

    try:
        client.storage.create_bucket(
            BUCKET,
            options={"public": False, "file_size_limit": 50 * 1024 * 1024},
        )
        logger.info("Created storage bucket: %s", BUCKET)
        return True
    except Exception as e:
        logger.warning("Failed to create bucket '%s': %s", BUCKET, e)
        return False


def upload_excel(local_path: str, remote_path: str) -> str | None:
    """Upload Excel file to Supabase Storage.

    Args:
        local_path: Local filesystem path to the .xlsx file.
        remote_path: Destination path within the bucket (e.g. "2026-03-31/Samsung.xlsx").

    Returns:
        The remote path on success, None on failure.
    """
    client = get_client()
    if not client:
        return None

    path = Path(local_path)
    if not path.exists():
        logger.warning("File not found: %s", local_path)
        return None

    try:
        with open(path, "rb") as f:
            file_bytes = f.read()

        client.storage.from_(BUCKET).upload(
            remote_path,
            file_bytes,
            file_options={
                "content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "upsert": "true",
            },
        )
        logger.info("Uploaded %s -> %s/%s", path.name, BUCKET, remote_path)
        return remote_path
    except Exception as e:
        logger.warning("Upload failed [%s]: %s", path.name, e)
        return None


def get_download_url(
    remote_path: str, expires_in: int = SIGNED_URL_EXPIRY
) -> str | None:
    """Generate a signed download URL for a stored file.

    Args:
        remote_path: Path within the bucket.
        expires_in: URL validity in seconds (default: 30 days).

    Returns:
        Signed URL string, or None on failure.
    """
    client = get_client()
    if not client:
        return None

    try:
        resp = client.storage.from_(BUCKET).create_signed_url(remote_path, expires_in)
        url = resp.get("signedURL") or resp.get("signedUrl")
        return url
    except Exception as e:
        logger.warning("Signed URL generation failed [%s]: %s", remote_path, e)
        return None


def _sanitize_key(name: str) -> str:
    """Convert to ASCII-safe Supabase Storage key.

    Replaces non-ASCII characters (e.g., Korean) with underscores, then
    removes characters that Supabase Storage rejects or that break presigned URLs.
    """
    result = []
    for ch in name:
        if ord(ch) < 128 and (ch.isalnum() or ch in "-_."):
            result.append(ch)
        elif ch in " \t":
            result.append("_")
        else:
            result.append("_")  # Replace Korean and other non-ASCII with _
    sanitized = "".join(result)
    # Collapse consecutive underscores and strip leading/trailing ones
    while "__" in sanitized:
        sanitized = sanitized.replace("__", "_")
    stripped = sanitized.strip("_")
    if stripped:
        return stripped
    # All characters were non-ASCII (e.g., Korean-only filename): use short hash
    return hashlib.md5(name.encode("utf-8", errors="replace")).hexdigest()[:8]


def upload_and_get_url(
    local_path: str, week_label: str, remote_filename: str | None = None
) -> dict | None:
    """Upload an Excel file and return its download URL.

    Args:
        local_path: Local path to .xlsx file.
        week_label: Already-sanitized week folder key (no parentheses/spaces).
        remote_filename: Optional override for the storage filename.
            When provided, used as-is (caller is responsible for ASCII safety).
            When omitted, derived from local_path via _sanitize_key().

    Returns:
        {"remote_path": "...", "download_url": "https://..."} or None.
    """
    ensure_bucket()

    filename = (
        remote_filename if remote_filename else _sanitize_key(Path(local_path).name)
    )
    remote_path = f"{week_label}/{filename}"

    uploaded = upload_excel(local_path, remote_path)
    if not uploaded:
        return None

    url = get_download_url(remote_path)
    if not url:
        return None

    return {"remote_path": remote_path, "download_url": url}
