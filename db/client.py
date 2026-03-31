"""Supabase client singleton (thread-safe)."""

from __future__ import annotations

import os
import threading
from typing import Optional

from supabase import Client, create_client

_client: Optional[Client] = None
_lock = threading.Lock()


def get_client() -> Optional[Client]:
    """Create Supabase client from environment variables. Returns None if keys are missing.

    Reuses the client if already created (double-checked locking for thread safety).
    Does not permanently cache None, so it retries if keys are set later.
    """
    global _client
    if _client is not None:
        return _client

    with _lock:
        if _client is not None:
            return _client

        url = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_KEY", "")
        if not url or not key:
            return None

        _client = create_client(url, key)
        return _client


def is_configured() -> bool:
    """Check if Supabase connection is configured."""
    return get_client() is not None
