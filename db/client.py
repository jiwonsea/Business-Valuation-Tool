"""Supabase 클라이언트 싱글턴."""

from __future__ import annotations

import os
from typing import Optional

from supabase import Client, create_client

_client: Optional[Client] = None


def get_client() -> Optional[Client]:
    """환경변수에서 Supabase 클라이언트를 생성. 키가 없으면 None 반환.

    클라이언트가 이미 생성되었으면 재사용. 키가 나중에 설정되더라도
    None을 영구 캐싱하지 않고 재시도한다.
    """
    global _client
    if _client is not None:
        return _client

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        return None

    _client = create_client(url, key)
    return _client


def is_configured() -> bool:
    """Supabase 연결이 설정되어 있는지 확인."""
    return get_client() is not None
