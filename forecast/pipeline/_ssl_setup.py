"""TLS CA bundle setup for libraries that fail on non-ASCII home paths."""

from __future__ import annotations

import os
import shutil

import certifi

ASCII_CA = r"C:\temp\earnings_forecast\cacert.pem"


def ensure_ssl_env() -> None:
    """Set CA bundle environment variables before http/yfinance imports.

    Windows-only: works around libraries that fail when the certifi bundle sits
    under a non-ASCII home path (e.g. Korean user names). On POSIX the default
    paths are ASCII already — and running this there would create a literal
    ``C:\\temp\\...`` file in the repo root (observed sandbox artifact).
    """
    if os.name != "nt":
        return
    if not os.path.exists(ASCII_CA):
        os.makedirs(os.path.dirname(ASCII_CA), exist_ok=True)
        shutil.copy(certifi.where(), ASCII_CA)
    os.environ.setdefault("CURL_CA_BUNDLE", ASCII_CA)
    os.environ.setdefault("SSL_CERT_FILE", ASCII_CA)
