"""Opt-in, observation-only telemetry for LLM calls."""

from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal
from uuid import uuid4

import portalocker


Operation = Literal["primary", "parse_repair", "validator_repair"]


@dataclass(frozen=True)
class CallContext:
    run_id: str
    company: str | None
    step: str
    operation: Operation = "primary"


_ctx: ContextVar[CallContext | None] = ContextVar("llm_call_ctx", default=None)
_attempt_no: ContextVar[int] = ContextVar("llm_attempt_no", default=0)
_is_fallback: ContextVar[bool] = ContextVar("llm_is_fallback", default=False)
_write_lock = threading.Lock()
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def enabled() -> bool:
    return os.getenv("BVT_TELEMETRY", "0").lower() in {"1", "true", "yes", "on"}


def current_context() -> CallContext | None:
    return _ctx.get()


@contextmanager
def call_context(
    company: str | None,
    step: str,
    operation: Operation = "primary",
    run_id: str | None = None,
) -> Iterator[None]:
    parent = _ctx.get()
    context = CallContext(
        run_id=run_id
        or (parent.run_id if parent else None)
        or os.getenv("BVT_RUN_ID")
        or uuid4().hex,
        company=company,
        step=step,
        operation=operation,
    )
    token = _ctx.set(context)
    attempt_token = _attempt_no.set(0)
    try:
        yield
    finally:
        _attempt_no.reset(attempt_token)
        _ctx.reset(token)


@contextmanager
def operation(value: Operation) -> Iterator[None]:
    context = _ctx.get()
    if context is None:
        yield
        return
    token = _ctx.set(replace(context, operation=value))
    try:
        yield
    finally:
        _ctx.reset(token)


@contextmanager
def fallback(value: bool = True) -> Iterator[None]:
    token = _is_fallback.set(value)
    try:
        yield
    finally:
        _is_fallback.reset(token)


def next_attempt_no() -> int:
    value = _attempt_no.get() + 1
    _attempt_no.set(value)
    return value


def current_attempt_no() -> int:
    return _attempt_no.get()


def is_fallback() -> bool:
    return _is_fallback.get()


def emit(event: str, **fields: object) -> None:
    if not enabled():
        return
    context = _ctx.get()
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "run_id": context.run_id if context else uuid4().hex,
        "company": context.company if context else None,
        "step": context.step if context else "unknown",
        "operation": context.operation if context else "primary",
        **fields,
    }
    configured_path = os.getenv("BVT_TELEMETRY_PATH")
    path = Path(configured_path) if configured_path else _PROJECT_ROOT / ".cache" / "llm_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    with _write_lock:
        with portalocker.Lock(
            str(path), mode="a", encoding="utf-8", newline="", timeout=10
        ) as handle:
            handle.write(line)
            handle.flush()


def emit_blocked(provider: str, model: str, outcome: str) -> None:
    emit(
        "blocked",
        provider=provider,
        model=model,
        attempt_no=current_attempt_no(),
        is_fallback=is_fallback(),
        input_tokens=None,
        output_tokens=None,
        cache_read_tokens=None,
        latency_ms=None,
        outcome=outcome,
        est_cost_usd=None,
    )
