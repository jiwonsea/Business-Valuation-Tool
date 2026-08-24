import json
import multiprocessing
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest


@pytest.fixture(autouse=True)
def _isolate_api_guard_singleton():
    from pipeline.api_guard import ApiGuard

    ApiGuard._reset_singleton()
    yield
    ApiGuard._reset_singleton()


def _emit_many(path: str, count: int) -> None:
    import os

    os.environ["BVT_TELEMETRY"] = "1"
    os.environ["BVT_TELEMETRY_PATH"] = path
    from ai.telemetry import call_context, emit

    with call_context("worker", "test"):
        for index in range(count):
            emit("cache_miss", index=index)


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_cache_namespace_is_directory_only(monkeypatch):
    from ai import analyst

    original_key = analyst._cache_key("회사 A", "classify", "x")
    monkeypatch.delenv("BVT_CACHE_NS", raising=False)
    assert analyst._cache_dir() == analyst._LLM_CACHE_DIR
    assert analyst._cache_key("회사 A", "classify", "x") == original_key
    monkeypatch.setenv("BVT_CACHE_NS", "e1_test")
    assert analyst._cache_dir() == analyst._LLM_CACHE_DIR / "e1_test"
    assert analyst._cache_key("회사 A", "classify", "x") == original_key


def test_empty_cached_dict_keeps_legacy_cache_miss_behavior(monkeypatch, tmp_path):
    from ai import analyst

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    monkeypatch.setattr(analyst, "_get_cached", lambda *args, **kwargs: {})
    monkeypatch.setattr(analyst, "_set_cached", lambda *args, **kwargs: None)
    monkeypatch.setattr(analyst, "_save_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        analyst.AIAnalyst,
        "_ask_json",
        lambda *args, **kwargs: {"fresh": True},
    )

    result = analyst.AIAnalyst()._cached_json_step("Acme", "classify", lambda: "prompt")
    assert result == {"fresh": True}
    assert [event["event"] for event in _events(path)] == [
        "step_start",
        "cache_miss",
        "step_end",
    ]


def test_parse_repair_preserves_step_and_changes_operation(monkeypatch):
    from ai import analyst
    from ai.telemetry import call_context, current_context

    observed = []

    def fake_ask(*args, **kwargs):
        observed.append(current_context())
        return "not-json" if len(observed) == 1 else '{"ok": true}'

    monkeypatch.setattr(analyst, "ask_structured", fake_ask)
    with call_context("Acme", "classify"):
        result = analyst.AIAnalyst()._ask_json("p", "s", 20)

    assert result == {"ok": True}
    assert [item.operation for item in observed] == ["primary", "parse_repair"]
    assert {item.step for item in observed} == {"classify"}
    assert len({item.run_id for item in observed}) == 1


def test_openrouter_success_emits_one_terminal_attempt(monkeypatch, tmp_path):
    from ai import llm_client
    from ai.telemetry import call_context

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    response = SimpleNamespace(
        status_code=200,
        text="",
        raise_for_status=lambda: None,
        json=lambda: {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3},
        },
    )
    monkeypatch.setattr(llm_client._openrouter_client, "post", lambda *a, **k: response)

    with call_context("Acme", "wacc"):
        assert llm_client._ask_openrouter.__wrapped__("prompt") == "ok"

    attempts = [event for event in _events(path) if event["event"] == "attempt"]
    assert len(attempts) == 1
    assert attempts[0]["outcome"] == "success"
    assert attempts[0]["attempt_no"] == 1
    assert attempts[0]["input_tokens"] == 11
    response_meta = [
        event for event in _events(path) if event["event"] == "llm_response_meta"
    ]
    assert len(response_meta) == 1
    assert response_meta[0]["completion_tokens"] == 3
    assert response_meta[0]["stop_reason"] is None


def test_peers_batch_coverage_records_partial_response(monkeypatch, tmp_path):
    from pipeline.profile_generator import _emit_peers_batch_coverage

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))

    _emit_peers_batch_coverage("Acme", ["SEG1", "SEG2", "SEG3"], {"SEG1"}, False, 2)

    event = _events(path)[0]
    assert event["company"] == "Acme"
    assert event["step"] == "peers_batch"
    assert event["requested_segments"] == 3
    assert event["returned_segments"] == 1
    assert event["missing_codes"] == ["SEG2", "SEG3"]
    assert event["parse_failed"] is False
    assert event["fallback_calls"] == 2


def test_decorated_retry_emits_each_attempt_but_counts_one_call(monkeypatch, tmp_path):
    from ai import llm_client
    from ai.telemetry import call_context
    from pipeline.api_guard import ApiGuard

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    guard = ApiGuard.get()
    guard._reset()
    guard.configure("openrouter", max_retries=1, base_delay=0, max_delay=0)
    monkeypatch.setattr(guard, "_save_usage", lambda *args, **kwargs: None)

    response = SimpleNamespace(
        status_code=200,
        text="",
        raise_for_status=lambda: None,
        json=lambda: {"choices": [{"message": {"content": "ok"}}]},
    )
    calls = 0

    def fake_post(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("temporary")
        return response

    monkeypatch.setattr(llm_client._openrouter_client, "post", fake_post)
    before = guard.get_usage_summary()["openrouter"]["calls"]
    with call_context("Acme", "wacc"):
        assert llm_client._ask_openrouter("prompt") == "ok"
    after = guard.get_usage_summary()["openrouter"]["calls"]

    attempts = [event for event in _events(path) if event["event"] == "attempt"]
    assert [event["attempt_no"] for event in attempts] == [1, 2]
    assert [event["outcome"] for event in attempts] == ["http_error", "success"]
    assert after - before == 1


@pytest.mark.parametrize("entrypoint", ["ask", "ask_structured"])
def test_provider_fallback_records_anthropic_attempt(monkeypatch, tmp_path, entrypoint):
    from ai import llm_client
    from ai.telemetry import call_context
    from pipeline.api_guard import ApiGuard

    path = tmp_path / f"{entrypoint}.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    guard = ApiGuard.get()
    guard._reset()
    guard.configure("openrouter", max_retries=0)
    guard.configure("anthropic", max_retries=0)
    monkeypatch.setattr(guard, "_save_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        llm_client._openrouter_client,
        "post",
        lambda *args, **kwargs: (_ for _ in ()).throw(httpx.ConnectError("down")),
    )
    usage = SimpleNamespace(
        input_tokens=7,
        output_tokens=2,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    response = SimpleNamespace(
        usage=usage,
        content=[SimpleNamespace(text="fallback")],
    )
    client = SimpleNamespace(messages=SimpleNamespace(create=lambda **kwargs: response))
    monkeypatch.setattr(llm_client, "_get_anthropic_client", lambda key: client)

    with call_context("Acme", "scenarios"):
        assert getattr(llm_client, entrypoint)("prompt") == "fallback"

    attempts = [event for event in _events(path) if event["event"] == "attempt"]
    assert [(event["provider"], event["attempt_no"]) for event in attempts] == [
        ("openrouter", 1),
        ("anthropic", 2),
    ]
    assert attempts[1]["is_fallback"] is True


def test_fallback_marker_and_blocked_are_separate(monkeypatch, tmp_path):
    from ai import llm_client
    from ai.telemetry import call_context, is_fallback
    from pipeline.api_guard import ApiGuardError

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setattr(
        llm_client,
        "_ask_openrouter",
        lambda *a, **k: (_ for _ in ()).throw(ApiGuardError("quota")),
    )
    monkeypatch.setattr(
        llm_client,
        "_ask_anthropic",
        lambda *a, **k: "fallback" if is_fallback() else "wrong",
    )

    with call_context("Acme", "scenarios"):
        assert llm_client.ask("prompt") == "fallback"

    events = _events(path)
    assert [event["event"] for event in events] == ["blocked"]
    assert events[0]["provider"] == "openrouter"


def test_blocked_outcomes_use_exception_types(caplog):
    from ai.llm_client import _blocked_outcome
    from pipeline.api_guard import ApiGuardError, CircuitOpenError, QuotaExceededError

    assert _blocked_outcome(CircuitOpenError("openrouter", 5)) == "circuit_open"
    assert _blocked_outcome(QuotaExceededError("openrouter", 2, 2)) == "quota_exceeded"
    assert _blocked_outcome(ApiGuardError("other")) == "unknown"
    assert "Unknown ApiGuardError subtype" in caplog.text


def test_blocked_event_keeps_attempt_position(monkeypatch, tmp_path):
    from ai.telemetry import call_context, emit_blocked, next_attempt_no

    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "1")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(path))
    with call_context("Acme", "wacc"):
        assert next_attempt_no() == 1
        emit_blocked("openrouter", "model", "quota_exceeded")

    assert _events(path)[0]["attempt_no"] == 1


def test_measurement_gate_records_approval_and_fails_on_attempt_overrun(tmp_path):
    path = tmp_path / "events.jsonl"
    code = (
        "from ai.telemetry import call_context,emit; "
        "c=call_context('Acme','test'); c.__enter__(); "
        "emit('attempt'); emit('attempt'); c.__exit__(None,None,None)"
    )
    result = subprocess.run(
        [
            sys.executable,
            "scripts/e1_measure.py",
            "--events",
            str(path),
            "--estimated-attempts",
            "1",
            "--estimated-cost-usd",
            "0.01",
            sys.executable,
            "-c",
            code,
        ],
        input="y\n",
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )

    events = _events(path)
    assert result.returncode == 2
    assert events[0]["event"] == "approval"
    assert events[0]["estimated_attempts"] == 1
    assert sum(event["event"] == "attempt" for event in events) == 2


def test_jsonl_sink_is_process_safe(monkeypatch, tmp_path):
    path = tmp_path / "events.jsonl"
    processes = [
        multiprocessing.Process(target=_emit_many, args=(str(path), 30))
        for _ in range(4)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0

    assert len(_events(path)) == 120
