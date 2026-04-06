"""API Guard -- Rate limiting, circuit breaker, and exponential backoff.

Three-layer defense for external API calls:
1. Hard Quota: Daily call limits per provider (persistent JSON file)
2. Circuit Breaker: CLOSED -> OPEN -> HALF_OPEN state machine
3. Exponential Backoff: Graduated retry with jitter for transient errors
"""

from __future__ import annotations

import functools
import json
import logging
import os
import random
import tempfile
import threading
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ApiGuardError(Exception):
    """Base exception for API guard errors."""


class QuotaExceededError(ApiGuardError):
    """Daily API quota exceeded."""

    def __init__(self, provider: str, calls: int, limit: int):
        self.provider = provider
        self.calls = calls
        self.limit = limit
        super().__init__(
            f"{provider}: daily quota exceeded ({calls}/{limit})"
        )


class CircuitOpenError(ApiGuardError):
    """Circuit breaker is open -- API calls blocked."""

    def __init__(self, provider: str, cooldown_remaining: float):
        self.provider = provider
        self.cooldown_remaining = cooldown_remaining
        super().__init__(
            f"{provider}: circuit OPEN (cooldown {cooldown_remaining:.0f}s remaining)"
        )


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_RETRYABLE_CODES = (429, 500, 502, 503, 504)


@dataclass
class ProviderConfig:
    """Per-provider guard configuration."""

    name: str
    daily_limit: int = 100
    failure_threshold: int = 3
    cooldown_seconds: float = 60.0
    max_retries: int = 3
    base_delay: float = 2.0
    max_delay: float = 60.0
    retryable_codes: tuple[int, ...] = _DEFAULT_RETRYABLE_CODES


PROVIDER_DEFAULTS: dict[str, ProviderConfig] = {
    "dart": ProviderConfig("dart", daily_limit=100, failure_threshold=3, cooldown_seconds=60, max_retries=3, base_delay=2.0),
    "edgar": ProviderConfig("edgar", daily_limit=100, failure_threshold=3, cooldown_seconds=60, max_retries=3, base_delay=2.0),
    "yahoo": ProviderConfig("yahoo", daily_limit=100, failure_threshold=5, cooldown_seconds=120, max_retries=3, base_delay=1.0),
    "yfinance": ProviderConfig("yfinance", daily_limit=200, failure_threshold=5, cooldown_seconds=120, max_retries=2, base_delay=1.0),
    "krx": ProviderConfig("krx", daily_limit=50, failure_threshold=3, cooldown_seconds=60, max_retries=2, base_delay=2.0),
    "fred": ProviderConfig("fred", daily_limit=20, failure_threshold=3, cooldown_seconds=300, max_retries=2, base_delay=2.0),
    "naver": ProviderConfig("naver", daily_limit=50, failure_threshold=3, cooldown_seconds=60, max_retries=2, base_delay=1.0),
    "google_rss": ProviderConfig("google_rss", daily_limit=50, failure_threshold=3, cooldown_seconds=60, max_retries=2, base_delay=1.0),
    "openrouter": ProviderConfig("openrouter", daily_limit=200, failure_threshold=3, cooldown_seconds=120, max_retries=2, base_delay=5.0, max_delay=30.0),
    "anthropic": ProviderConfig("anthropic", daily_limit=200, failure_threshold=3, cooldown_seconds=120, max_retries=5, base_delay=10.0, max_delay=120.0),
    "supabase": ProviderConfig("supabase", daily_limit=200, failure_threshold=5, cooldown_seconds=30, max_retries=3, base_delay=1.0),
}


# ---------------------------------------------------------------------------
# Circuit breaker state
# ---------------------------------------------------------------------------


@dataclass
class _CircuitState:
    status: str = "closed"  # "closed" | "open" | "half_open"
    consecutive_failures: int = 0
    last_failure_time: float = 0.0


# ---------------------------------------------------------------------------
# ApiGuard singleton
# ---------------------------------------------------------------------------

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_USAGE_FILE = _CACHE_DIR / "api_usage.json"
_WARN_THRESHOLD = 0.8  # warn at 80% of daily limit


class ApiGuard:
    """Thread-safe API guard with quota, circuit breaker, and backoff."""

    _instance: ApiGuard | None = None
    _init_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: dict[str, ProviderConfig] = {}
        self._circuits: dict[str, _CircuitState] = {}
        self._usage: dict[str, Any] = {"date": "", "counters": {}}
        self._load_configs()
        self._load_usage()

    @classmethod
    def get(cls) -> ApiGuard:
        """Return thread-safe singleton instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = ApiGuard()
        return cls._instance

    # -- Configuration -------------------------------------------------------

    def _load_configs(self) -> None:
        """Load default configs with env var overrides."""
        for name, default in PROVIDER_DEFAULTS.items():
            cfg = ProviderConfig(
                name=default.name,
                daily_limit=default.daily_limit,
                failure_threshold=default.failure_threshold,
                cooldown_seconds=default.cooldown_seconds,
                max_retries=default.max_retries,
                base_delay=default.base_delay,
                max_delay=default.max_delay,
                retryable_codes=default.retryable_codes,
            )
            # Env var override for daily limit
            env_key = f"API_GUARD_{name.upper()}_DAILY_LIMIT"
            env_val = os.environ.get(env_key)
            if env_val and env_val.isdigit():
                cfg.daily_limit = int(env_val)
            self._configs[name] = cfg
            self._circuits[name] = _CircuitState()

    def configure(self, provider: str, **kwargs: Any) -> None:
        """Override provider config programmatically (for tests)."""
        with self._lock:
            cfg = self._get_config(provider)
            for key, val in kwargs.items():
                if hasattr(cfg, key):
                    setattr(cfg, key, val)

    def _get_config(self, provider: str) -> ProviderConfig:
        if provider not in self._configs:
            self._configs[provider] = ProviderConfig(name=provider)
            self._circuits[provider] = _CircuitState()
        return self._configs[provider]

    # -- Usage persistence ---------------------------------------------------

    def _load_usage(self) -> None:
        """Load usage from disk, reset if date changed."""
        today = date.today().isoformat()
        if _USAGE_FILE.exists():
            try:
                raw = json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
                if raw.get("date") == today:
                    self._usage = raw
                    return
            except (json.JSONDecodeError, OSError):
                pass
        self._usage = {"date": today, "counters": {}}

    def _save_usage(self) -> None:
        """Atomically persist usage to disk."""
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=str(_CACHE_DIR), suffix=".tmp"
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._usage, f, ensure_ascii=False, indent=2)
            # Atomic rename (Windows: need to remove target first)
            if _USAGE_FILE.exists():
                _USAGE_FILE.unlink()
            Path(tmp_path).rename(_USAGE_FILE)
        except OSError as exc:
            logger.debug("Failed to save API usage file: %s", exc)

    def _ensure_today(self) -> None:
        """Reset counters if date changed."""
        today = date.today().isoformat()
        if self._usage.get("date") != today:
            logger.info("Daily quota reset for %s", today)
            self._usage = {"date": today, "counters": {}}

    def _get_counter(self, provider: str) -> dict[str, int]:
        counters = self._usage.setdefault("counters", {})
        if provider not in counters:
            counters[provider] = {"calls": 0, "cache_hits": 0}
        return counters[provider]

    # -- Public API ----------------------------------------------------------

    def check(self, provider: str) -> None:
        """Check quota and circuit before making an API call.

        Raises:
            QuotaExceededError: Daily limit exceeded.
            CircuitOpenError: Circuit breaker is open.
        """
        with self._lock:
            self._ensure_today()
            cfg = self._get_config(provider)
            counter = self._get_counter(provider)

            # Quota check
            if cfg.daily_limit > 0 and counter["calls"] >= cfg.daily_limit:
                raise QuotaExceededError(provider, counter["calls"], cfg.daily_limit)

            # Circuit breaker check
            circuit = self._circuits[provider]
            if circuit.status == "open":
                elapsed = time.time() - circuit.last_failure_time
                if elapsed >= cfg.cooldown_seconds:
                    circuit.status = "half_open"
                    logger.info("%s: circuit -> HALF_OPEN (probe allowed)", provider)
                else:
                    raise CircuitOpenError(provider, cfg.cooldown_seconds - elapsed)

    def record_success(self, provider: str) -> None:
        """Record a successful API call."""
        with self._lock:
            self._ensure_today()
            cfg = self._get_config(provider)
            counter = self._get_counter(provider)
            counter["calls"] += 1

            # Warn at 80% threshold
            if cfg.daily_limit > 0:
                ratio = counter["calls"] / cfg.daily_limit
                if ratio >= _WARN_THRESHOLD and (counter["calls"] - 1) / cfg.daily_limit < _WARN_THRESHOLD:
                    logger.warning(
                        "%s: approaching daily limit (%d/%d = %.0f%%)",
                        provider, counter["calls"], cfg.daily_limit, ratio * 100,
                    )

            # Circuit breaker: success -> closed
            circuit = self._circuits[provider]
            if circuit.status in ("half_open", "closed"):
                if circuit.consecutive_failures > 0:
                    logger.info("%s: circuit -> CLOSED (recovered)", provider)
                circuit.status = "closed"
                circuit.consecutive_failures = 0

            self._save_usage()

    def record_failure(self, provider: str, error: Exception | None = None) -> None:
        """Record a failed API call."""
        with self._lock:
            self._ensure_today()
            cfg = self._get_config(provider)
            counter = self._get_counter(provider)
            counter["calls"] += 1

            circuit = self._circuits[provider]
            circuit.consecutive_failures += 1
            circuit.last_failure_time = time.time()

            if circuit.status == "half_open":
                circuit.status = "open"
                logger.warning(
                    "%s: circuit -> OPEN (half_open probe failed: %s)",
                    provider, error,
                )
            elif circuit.consecutive_failures >= cfg.failure_threshold:
                circuit.status = "open"
                logger.warning(
                    "%s: circuit -> OPEN after %d consecutive failures (cooldown=%ds)",
                    provider, circuit.consecutive_failures, cfg.cooldown_seconds,
                )

            self._save_usage()

    def record_cache_hit(self, provider: str) -> None:
        """Record a cache hit (does NOT count toward daily limit)."""
        with self._lock:
            self._ensure_today()
            counter = self._get_counter(provider)
            counter["cache_hits"] += 1

    def get_usage_summary(self) -> dict[str, Any]:
        """Return current usage counters and circuit states."""
        with self._lock:
            self._ensure_today()
            summary: dict[str, Any] = {}
            for name, cfg in self._configs.items():
                counter = self._get_counter(name)
                circuit = self._circuits.get(name, _CircuitState())
                summary[name] = {
                    "calls": counter["calls"],
                    "cache_hits": counter["cache_hits"],
                    "limit": cfg.daily_limit,
                    "remaining": max(0, cfg.daily_limit - counter["calls"]) if cfg.daily_limit > 0 else -1,
                    "circuit": circuit.status,
                }
            return summary

    def _reset(self) -> None:
        """Reset all state (test-only)."""
        with self._lock:
            self._usage = {"date": date.today().isoformat(), "counters": {}}
            for circuit in self._circuits.values():
                circuit.status = "closed"
                circuit.consecutive_failures = 0
                circuit.last_failure_time = 0.0

    @classmethod
    def _reset_singleton(cls) -> None:
        """Destroy singleton (test-only)."""
        cls._instance = None


# ---------------------------------------------------------------------------
# Retry with exponential backoff
# ---------------------------------------------------------------------------


def _is_retryable(exc: Exception, retryable_codes: tuple[int, ...]) -> bool:
    """Check if an exception should trigger a retry."""
    try:
        import httpx
        if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in retryable_codes
    except ImportError:
        pass
    return False


def _get_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header value from a 429 response."""
    try:
        import httpx
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            val = exc.response.headers.get("retry-after")
            if val and val.isdigit():
                return float(val)
    except ImportError:
        pass
    return None


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def api_guard(provider: str) -> Callable:
    """Decorator that wraps a function with quota check, circuit breaker, and retry.

    Usage:
        @api_guard("dart")
        def get_financial_statements(...):
            resp = httpx.get(...)
            resp.raise_for_status()
            return resp.json()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            guard = ApiGuard.get()
            cfg = guard._get_config(provider)

            last_exc: Exception | None = None

            for attempt in range(cfg.max_retries + 1):
                # Pre-call checks (quota + circuit)
                guard.check(provider)

                try:
                    result = func(*args, **kwargs)
                    guard.record_success(provider)
                    return result
                except Exception as exc:
                    last_exc = exc

                    if not _is_retryable(exc, cfg.retryable_codes) or attempt == cfg.max_retries:
                        guard.record_failure(provider, exc)
                        raise

                    # Retryable error -- backoff and retry
                    retry_after = _get_retry_after(exc)
                    if retry_after is not None:
                        delay = retry_after
                    else:
                        delay = min(
                            cfg.base_delay * (2 ** attempt) + random.uniform(0, 1),
                            cfg.max_delay,
                        )

                    logger.warning(
                        "%s: retry %d/%d after error (delay=%.1fs): %s",
                        provider, attempt + 1, cfg.max_retries, delay, exc,
                    )
                    time.sleep(delay)

            # Should not reach here, but just in case
            if last_exc is not None:
                raise last_exc

        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

# Average LLM cost per call (OpenRouter Claude Sonnet 4 pricing estimate)
_LLM_COST_PER_CALL_USD = 0.02


def estimate_weekly_cost(
    markets: list[str],
    max_companies: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Estimate API calls and LLM cost before running weekly pipeline.

    Returns:
        {
            "estimated_api_calls": {"dart": N, ...},
            "estimated_llm_calls": N,
            "estimated_llm_cost_usd": float,
            "remaining_quota": {"dart": N, ...},
        }
    """
    guard = ApiGuard.get()

    n_markets = len(markets)
    has_kr = "KR" in markets
    has_us = "US" in markets

    # Discovery phase: 4 queries per market
    news_naver = 4 if has_kr else 0
    news_google = 4 if has_us else 0

    # Scoring phase: ~1 yahoo call per discovered company (estimate ~5 unique)
    scoring_yahoo = max_companies * 2

    # Discovery LLM: 1 call per market
    discovery_llm = n_markets

    estimates: dict[str, int] = {
        "naver": news_naver,
        "google_rss": news_google,
        "yahoo": scoring_yahoo,
    }

    if not dry_run:
        # Valuation phase per company (estimates)
        kr_companies = max_companies // 2 + 1 if has_kr and has_us else (max_companies if has_kr else 0)
        us_companies = max_companies - kr_companies if has_kr and has_us else (max_companies if has_us else 0)

        estimates["dart"] = kr_companies * 4  # financial + company + stock + report
        estimates["edgar"] = us_companies * 2  # facts + submissions
        estimates["yfinance"] = max_companies * 2  # financials + market data
        estimates["fred"] = 1 if max_companies > 0 else 0

        # LLM calls per company: identify + classify + peers + wacc + scenarios + research_note
        valuation_llm = max_companies * 6
    else:
        valuation_llm = 0

    total_llm = discovery_llm + valuation_llm
    estimates["openrouter"] = total_llm

    # Remaining quota
    summary = guard.get_usage_summary()
    remaining: dict[str, int] = {}
    for prov, info in summary.items():
        remaining[prov] = info["remaining"]

    return {
        "estimated_api_calls": estimates,
        "estimated_llm_calls": total_llm,
        "estimated_llm_cost_usd": round(total_llm * _LLM_COST_PER_CALL_USD, 2),
        "remaining_quota": remaining,
    }
