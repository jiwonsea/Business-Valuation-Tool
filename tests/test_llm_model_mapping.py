from types import SimpleNamespace

import pytest


def _anthropic_client(captured):
    usage = SimpleNamespace(
        input_tokens=4,
        output_tokens=2,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )

    def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            usage=usage,
            content=[SimpleNamespace(text="ok")],
            stop_reason="end_turn",
        )

    return SimpleNamespace(messages=SimpleNamespace(create=create))


def _openrouter_response(captured):
    def post(*args, **kwargs):
        captured.update(kwargs["json"])
        return SimpleNamespace(
            status_code=200,
            text="",
            raise_for_status=lambda: None,
            json=lambda: {
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )

    return post


def test_default_heavy_maps_to_anthropic(monkeypatch):
    from ai import llm_client

    captured = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.delenv("BVT_ANTHROPIC_MODEL_HEAVY", raising=False)
    monkeypatch.setattr(
        llm_client, "_get_anthropic_client", lambda key: _anthropic_client(captured)
    )

    assert (
        llm_client._ask_anthropic.__wrapped__("prompt", model=llm_client.MODEL_HEAVY)
        == "ok"
    )
    assert captured["model"] == "claude-sonnet-5-20260630"


def test_default_heavy_maps_to_openrouter(monkeypatch):
    from ai import llm_client

    captured = {}
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("BVT_OPENROUTER_MODEL_HEAVY", raising=False)
    monkeypatch.setattr(
        llm_client._openrouter_client, "post", _openrouter_response(captured)
    )

    assert (
        llm_client._ask_openrouter.__wrapped__("prompt", model=llm_client.MODEL_HEAVY)
        == "ok"
    )
    assert captured["model"] == "anthropic/claude-sonnet-5"


def test_provider_specific_heavy_overrides(monkeypatch):
    from ai import llm_client

    anthropic = {}
    openrouter = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("BVT_ANTHROPIC_MODEL_HEAVY", "claude-sonnet-custom")
    monkeypatch.setenv("BVT_OPENROUTER_MODEL_HEAVY", "anthropic/claude-sonnet-custom")
    monkeypatch.setattr(
        llm_client, "_get_anthropic_client", lambda key: _anthropic_client(anthropic)
    )
    monkeypatch.setattr(
        llm_client._openrouter_client, "post", _openrouter_response(openrouter)
    )

    llm_client._ask_anthropic.__wrapped__("p", model=llm_client.MODEL_HEAVY)
    llm_client._ask_openrouter.__wrapped__("p", model=llm_client.MODEL_HEAVY)

    assert anthropic["model"] == "claude-sonnet-custom"
    assert openrouter["model"] == "anthropic/claude-sonnet-custom"


def test_cross_provider_model_formats_fail_fast(monkeypatch):
    from ai import llm_client

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    with pytest.raises(ValueError, match="must not contain"):
        llm_client._ask_anthropic.__wrapped__("p", model="anthropic/claude-sonnet-4.6")
    with pytest.raises(ValueError, match="must contain"):
        llm_client._ask_openrouter.__wrapped__("p", model="invalid-model")


# ── F1b: sonnet-5 rejects non-default temperature — param must be omitted ──


def test_heavy_omits_temperature_both_providers(monkeypatch):
    from ai import llm_client

    anthropic = {}
    openrouter = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("BVT_ANTHROPIC_MODEL_HEAVY", raising=False)
    monkeypatch.delenv("BVT_OPENROUTER_MODEL_HEAVY", raising=False)
    monkeypatch.setattr(
        llm_client, "_get_anthropic_client", lambda key: _anthropic_client(anthropic)
    )
    monkeypatch.setattr(
        llm_client._openrouter_client, "post", _openrouter_response(openrouter)
    )

    llm_client._ask_anthropic.__wrapped__(
        "p", model=llm_client.MODEL_HEAVY, temperature=0.3
    )
    llm_client._ask_openrouter.__wrapped__(
        "p", model=llm_client.MODEL_HEAVY, temperature=0.3
    )

    assert "temperature" not in anthropic
    assert "temperature" not in openrouter


def test_light_keeps_temperature_both_providers(monkeypatch):
    from ai import llm_client

    anthropic = {}
    openrouter = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setattr(
        llm_client, "_get_anthropic_client", lambda key: _anthropic_client(anthropic)
    )
    monkeypatch.setattr(
        llm_client._openrouter_client, "post", _openrouter_response(openrouter)
    )

    llm_client._ask_anthropic.__wrapped__(
        "p", model=llm_client.MODEL_LIGHT, temperature=0
    )
    llm_client._ask_openrouter.__wrapped__(
        "p", model=llm_client.MODEL_LIGHT, temperature=0
    )

    # Haiku 4.5 still supports temperature — ask_structured determinism intact
    assert anthropic["temperature"] == 0
    assert openrouter["temperature"] == 0


def test_heavy_env_override_to_sonnet_46_keeps_temperature(monkeypatch):
    from ai import llm_client

    anthropic = {}
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("BVT_ANTHROPIC_MODEL_HEAVY", "claude-sonnet-4-6")
    monkeypatch.setattr(
        llm_client, "_get_anthropic_client", lambda key: _anthropic_client(anthropic)
    )

    llm_client._ask_anthropic.__wrapped__(
        "p", model=llm_client.MODEL_HEAVY, temperature=0.3
    )
    assert anthropic["temperature"] == 0.3


def test_openrouter_default_model_is_not_retired(monkeypatch):
    from ai import llm_client

    # Retired slug anthropic/claude-sonnet-4 must not be the bare-ask default
    assert llm_client._OPENROUTER_DEFAULT_MODEL == "anthropic/claude-sonnet-5"

    captured = {}
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    monkeypatch.setattr(
        llm_client._openrouter_client, "post", _openrouter_response(captured)
    )
    llm_client._ask_openrouter.__wrapped__("p")  # bare call, model=""
    assert captured["model"] == "anthropic/claude-sonnet-5"
    assert "temperature" not in captured
