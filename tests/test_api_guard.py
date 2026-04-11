"""Tests for pipeline.api_guard -- Hard Quota, Circuit Breaker, Exponential Backoff."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pipeline.api_guard import (
    ApiGuard,
    CircuitOpenError,
    QuotaExceededError,
    api_guard,
    estimate_weekly_cost,
)


@pytest.fixture(autouse=True)
def _reset_guard(tmp_path: Path):
    """Reset ApiGuard singleton and redirect usage file for each test."""
    import pipeline.api_guard as mod

    ApiGuard._reset_singleton()
    # Redirect usage file to tmp_path
    mod._CACHE_DIR = tmp_path
    mod._USAGE_FILE = tmp_path / "api_usage.json"
    mod._USAGE_LOCK = tmp_path / "api_usage.lock"
    yield
    ApiGuard._reset_singleton()


# ---------------------------------------------------------------------------
# Hard Quota
# ---------------------------------------------------------------------------


class TestHardQuota:
    def test_increments_counter_on_call(self, tmp_path: Path):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=10)
        guard.check("dart")
        guard.record_success("dart")

        summary = guard.get_usage_summary()
        assert summary["dart"]["calls"] == 1

    def test_raises_on_quota_exceeded(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=2)

        guard.check("dart")
        guard.record_success("dart")
        guard.check("dart")
        guard.record_success("dart")

        with pytest.raises(QuotaExceededError) as exc_info:
            guard.check("dart")
        assert exc_info.value.provider == "dart"
        assert exc_info.value.calls == 2
        assert exc_info.value.limit == 2

    def test_resets_on_new_day(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=2)
        guard.check("dart")
        guard.record_success("dart")
        guard.check("dart")
        guard.record_success("dart")

        # Simulate date change
        guard._usage["date"] = "1999-01-01"
        guard.check("dart")  # Should not raise
        guard.record_success("dart")
        assert guard.get_usage_summary()["dart"]["calls"] == 1

    def test_cache_hit_does_not_count(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=2)

        # Record 10 cache hits -- should not affect quota
        for _ in range(10):
            guard.record_cache_hit("dart")

        guard.check("dart")  # Should not raise
        guard.record_success("dart")

        summary = guard.get_usage_summary()
        assert summary["dart"]["calls"] == 1
        assert summary["dart"]["cache_hits"] == 10

    def test_persists_to_json_file(self, tmp_path: Path):

        guard = ApiGuard.get()
        guard.check("dart")
        guard.record_success("dart")

        usage_file = tmp_path / "api_usage.json"
        assert usage_file.exists()
        data = json.loads(usage_file.read_text(encoding="utf-8"))
        assert data["counters"]["dart"]["calls"] == 1

    def test_thread_safety(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=500)

        errors: list[Exception] = []

        def _call_n_times(n: int) -> None:
            for _ in range(n):
                try:
                    guard.check("dart")
                    guard.record_success("dart")
                except Exception as e:
                    errors.append(e)

        threads = [
            threading.Thread(target=_call_n_times, args=(20,)) for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert guard.get_usage_summary()["dart"]["calls"] == 200

    def test_warns_at_80_percent(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=10)

        # Make 7 calls (70%) -- no warning
        for _ in range(7):
            guard.check("dart")
            guard.record_success("dart")

        # 8th call (80%) should trigger warning
        with patch("pipeline.api_guard.logger") as mock_logger:
            guard.check("dart")
            guard.record_success("dart")
            mock_logger.warning.assert_called_once()
            assert "approaching daily limit" in mock_logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_closed_allows_calls(self):
        guard = ApiGuard.get()
        guard.check("dart")  # Should not raise
        guard.record_success("dart")

    def test_opens_after_threshold(self):
        guard = ApiGuard.get()
        guard.configure("dart", failure_threshold=3, cooldown_seconds=60)

        for _ in range(3):
            guard.check("dart")
            guard.record_failure("dart", RuntimeError("test"))

        with pytest.raises(CircuitOpenError):
            guard.check("dart")

    def test_open_raises_error(self):
        guard = ApiGuard.get()
        guard.configure("dart", failure_threshold=1, cooldown_seconds=300)

        guard.check("dart")
        guard.record_failure("dart", RuntimeError("test"))

        with pytest.raises(CircuitOpenError) as exc_info:
            guard.check("dart")
        assert exc_info.value.provider == "dart"
        assert exc_info.value.cooldown_remaining > 0

    def test_half_open_after_cooldown(self):
        guard = ApiGuard.get()
        guard.configure("dart", failure_threshold=1, cooldown_seconds=5)

        guard.check("dart")
        guard.record_failure("dart", RuntimeError("test"))

        # Simulate cooldown elapsed
        guard._circuits["dart"].last_failure_time = time.time() - 10

        guard.check("dart")  # Should not raise (half_open)
        assert guard._circuits["dart"].status == "half_open"

    def test_half_open_success_closes(self):
        guard = ApiGuard.get()
        guard.configure("dart", failure_threshold=1, cooldown_seconds=5)

        guard.check("dart")
        guard.record_failure("dart", RuntimeError("test"))
        guard._circuits["dart"].last_failure_time = time.time() - 10

        guard.check("dart")  # -> half_open
        guard.record_success("dart")  # -> closed
        assert guard._circuits["dart"].status == "closed"
        assert guard._circuits["dart"].consecutive_failures == 0

    def test_half_open_failure_reopens(self):
        guard = ApiGuard.get()
        guard.configure("dart", failure_threshold=1, cooldown_seconds=5)

        guard.check("dart")
        guard.record_failure("dart", RuntimeError("test"))
        guard._circuits["dart"].last_failure_time = time.time() - 10

        guard.check("dart")  # -> half_open
        guard.record_failure("dart", RuntimeError("test again"))  # -> open
        assert guard._circuits["dart"].status == "open"


# ---------------------------------------------------------------------------
# Exponential Backoff (via decorator)
# ---------------------------------------------------------------------------


class TestExponentialBackoff:
    def test_retries_on_429(self):
        """Decorator retries on 429 HTTPStatusError."""
        import httpx

        call_count = 0

        @api_guard("dart")
        def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                resp = httpx.Response(429, headers={"retry-after": "0"})
                raise httpx.HTTPStatusError(
                    "rate limited", request=MagicMock(), response=resp
                )
            return "ok"

        guard = ApiGuard.get()
        guard.configure("dart", max_retries=5, base_delay=0.01, max_delay=0.1)

        with patch("pipeline.api_guard.time.sleep"):
            result = flaky_call()

        assert result == "ok"
        assert call_count == 3

    def test_honors_retry_after_header(self):
        """Uses Retry-After header value as delay."""
        import httpx

        @api_guard("dart")
        def always_429():
            resp = httpx.Response(429, headers={"retry-after": "42"})
            raise httpx.HTTPStatusError(
                "rate limited", request=MagicMock(), response=resp
            )

        guard = ApiGuard.get()
        guard.configure("dart", max_retries=1, base_delay=1.0)

        with patch("pipeline.api_guard.time.sleep") as mock_sleep:
            with pytest.raises(httpx.HTTPStatusError):
                always_429()
            # First retry should use Retry-After=42
            mock_sleep.assert_called_once_with(42.0)

    def test_no_retry_on_400(self):
        """Non-retryable errors propagate immediately."""
        import httpx

        call_count = 0

        @api_guard("dart")
        def bad_request():
            nonlocal call_count
            call_count += 1
            resp = httpx.Response(400)
            raise httpx.HTTPStatusError(
                "bad request", request=MagicMock(), response=resp
            )

        guard = ApiGuard.get()
        guard.configure("dart", max_retries=3)

        with pytest.raises(httpx.HTTPStatusError):
            bad_request()
        assert call_count == 1  # No retry

    def test_jitter_bounds(self):
        """Backoff delay includes jitter in [0, 1) range."""
        import httpx

        delays: list[float] = []

        @api_guard("dart")
        def always_fail():
            resp = httpx.Response(500)
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=resp)

        guard = ApiGuard.get()
        guard.configure("dart", max_retries=3, base_delay=1.0, max_delay=100.0)

        with patch(
            "pipeline.api_guard.time.sleep", side_effect=lambda d: delays.append(d)
        ):
            with pytest.raises(httpx.HTTPStatusError):
                always_fail()

        # 3 retries: delays should be ~1, ~2, ~4 (plus jitter 0-1)
        assert len(delays) == 3
        assert 1.0 <= delays[0] < 3.0  # base_delay * 2^0 + jitter
        assert 2.0 <= delays[1] < 4.0  # base_delay * 2^1 + jitter
        assert 4.0 <= delays[2] < 6.0  # base_delay * 2^2 + jitter

    def test_max_delay_cap(self):
        """Delay is capped at max_delay."""
        import httpx

        delays: list[float] = []

        @api_guard("dart")
        def always_fail():
            resp = httpx.Response(500)
            raise httpx.HTTPStatusError("error", request=MagicMock(), response=resp)

        guard = ApiGuard.get()
        guard.configure("dart", max_retries=5, base_delay=10.0, max_delay=15.0)

        with patch(
            "pipeline.api_guard.time.sleep", side_effect=lambda d: delays.append(d)
        ):
            with pytest.raises(httpx.HTTPStatusError):
                always_fail()

        # All delays should be <= max_delay + 1 (jitter)
        for d in delays:
            assert d <= 16.0


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


class TestDecorator:
    def test_wraps_function_transparently(self):
        @api_guard("dart")
        def my_func(a: int, b: str = "x") -> str:
            """Docstring."""
            return f"{a}-{b}"

        assert my_func.__name__ == "my_func"
        assert my_func.__doc__ == "Docstring."

        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=100)
        assert my_func(1, b="y") == "1-y"

    def test_counts_successful_call(self):
        @api_guard("dart")
        def ok_call():
            return 42

        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=100)

        ok_call()
        ok_call()
        assert guard.get_usage_summary()["dart"]["calls"] == 2

    def test_propagates_non_retryable_error(self):
        @api_guard("dart")
        def raise_value_error():
            raise ValueError("bad value")

        with pytest.raises(ValueError, match="bad value"):
            raise_value_error()


# ---------------------------------------------------------------------------
# Cost Estimation
# ---------------------------------------------------------------------------


class TestCostEstimation:
    def test_returns_correct_structure(self):
        result = estimate_weekly_cost(["KR", "US"], max_companies=3)

        assert "estimated_api_calls" in result
        assert "estimated_llm_calls" in result
        assert "estimated_llm_cost_usd" in result
        assert "remaining_quota" in result
        assert isinstance(result["estimated_llm_cost_usd"], float)
        assert result["estimated_llm_calls"] > 0

    def test_reflects_remaining_quota(self):
        guard = ApiGuard.get()
        guard.configure("dart", daily_limit=100)

        # Use 30 calls
        for _ in range(30):
            guard.check("dart")
            guard.record_success("dart")

        result = estimate_weekly_cost(["KR"], max_companies=1)
        assert result["remaining_quota"]["dart"] == 70

    def test_dry_run_has_no_valuation_calls(self):
        result = estimate_weekly_cost(["KR"], max_companies=3, dry_run=True)
        assert result["estimated_llm_calls"] == 1  # discovery only
        assert result["estimated_api_calls"].get("dart", 0) == 0
