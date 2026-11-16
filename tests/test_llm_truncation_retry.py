"""K-0D: a response cut off at max_tokens is told apart from malformed JSON.

What is pinned here
  * the transport functions hand response metadata (provider, model, stop
    reason, cap, output tokens) to callers through capture_response_meta();
    ask() and ask_structured() still return a plain str, and a call that
    raises leaves no metadata behind;
  * AIAnalyst._ask_json() retries a truncated response once with the same
    prompt and a doubled cap (ceiling 8192), and a malformed one once with the
    repair suffix at the same cap; the two are never chained, so one call
    makes two ask_structured() calls at most;
  * a truncated response is accepted only when the whole text is a JSON
    object or array;
  * with no metadata the behaviour is the one from before K-0D.

Two things are counted separately in every test
  * logical calls: ask_structured() calls made by ai.analyst (a recording
    pass-through), with their arguments;
  * boundary calls: what reached a provider (OpenRouter post / Anthropic
    messages.create), in order, with the cap each carried.

Isolation: the fakes sit at the provider boundary, so _ask_openrouter,
_ask_anthropic, @api_guard, the fallback in ask_structured() and the telemetry
calls all run for real. The Anthropic SDK itself (its own retries and HTTP) is
outside the boundary and not exercised. An unscripted request fails the test,
and so does a scripted reply that nobody asked for. ApiGuard's usage file, the
telemetry path and the LLM cache directory point into tmp_path; the cache and
database helpers fail when called unless a test replaces them. No network,
.env, database or repository cache file is touched.
"""

import inspect
import json
import logging
import os
import threading
import time
from types import SimpleNamespace

import httpx
import pytest

ROUTES = ("openrouter", "anthropic", "fallback")
SINGLE = ("openrouter", "anthropic")
ENTRYPOINTS = ("ask", "ask_structured")
# The provider that answers on each route, and how it reports the stop reason.
ANSWERING = {
    "openrouter": "openrouter",
    "anthropic": "anthropic",
    "fallback": "anthropic",
}
STOP = {"openrouter": "stop", "anthropic": "end_turn"}
CUT = {"openrouter": "length", "anthropic": "max_tokens"}
LIGHT_MODEL = {
    "openrouter": "anthropic/claude-haiku-4.5",
    "anthropic": "claude-haiku-4-5-20251001",
}

REPAIR_SUFFIX = "\n\n순수 JSON 객체만 출력하세요. 설명 텍스트 없이 JSON만 응답하세요."
CEILING = 8192

PROMPT = "PROMPT-BODY-51c9"
SYSTEM = "SYSTEM-BODY-22d0"
GOOD = '{"ok": true}'
# Response bodies carry a marker so that a leak into logs or errors is visible.
LEAK = "LEAK-7f3a"
CUT_JSON = '{"segments": [{"code": "' + LEAK
MALFORMED = LEAK + " is not json"
FENCED = '```json\n{"fenced": true}\n```'

_AUTO = object()


def or_raw(body):
    return SimpleNamespace(
        status_code=200, text="", raise_for_status=lambda: None, json=lambda: body
    )


def or_reply(text, finish, tokens):
    return or_raw(
        {
            "choices": [{"message": {"content": text}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 5, "completion_tokens": tokens},
        }
    )


def an_reply(text, stop, tokens):
    usage = SimpleNamespace(
        input_tokens=5,
        output_tokens=tokens,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return SimpleNamespace(
        usage=usage, content=[SimpleNamespace(text=text)], stop_reason=stop
    )


def boundary_for(route, caps):
    """Boundary calls a route needs for logical calls carrying ``caps``."""
    if route == "fallback":
        return [(p, cap) for cap in caps for p in ("openrouter", "anthropic")]
    return [(route, cap) for cap in caps]


class Harness:
    """Scripted provider boundary; fails closed."""

    def __init__(self, monkeypatch, guard, events_path):
        self.monkeypatch = monkeypatch
        self.guard = guard
        self.events_path = events_path
        self.route = None
        self.queues = {"openrouter": [], "anthropic": []}
        self.requests = []  # every request that reached a provider, in order
        self.logical = []  # every ask_structured() call made by ai.analyst
        self.unexpected = []  # anything that was reached without being scripted

    def closed(self, name):
        def _closed(*args, **kwargs):
            self.unexpected.append(name)
            raise AssertionError(f"unexpected call: {name}")

        return _closed

    # ── provider boundary ──

    def _serve(self, provider, request):
        self.requests.append(request)
        if not self.queues[provider]:
            self.unexpected.append(f"{provider} request")
            raise AssertionError(f"unscripted {provider} request")
        reply = self.queues[provider].pop(0)
        if callable(reply):
            reply = reply()
        if isinstance(reply, BaseException):
            raise reply
        return reply

    def post(self, url, **kwargs):
        payload = kwargs["json"]
        messages = payload["messages"]
        return self._serve(
            "openrouter",
            {
                "provider": "openrouter",
                "model": payload["model"],
                "max_tokens": payload["max_tokens"],
                "prompt": messages[-1]["content"],
                "system": messages[0]["content"] if len(messages) == 2 else "",
            },
        )

    def create(self, **kwargs):
        system = kwargs.get("system")
        return self._serve(
            "anthropic",
            {
                "provider": "anthropic",
                "model": kwargs["model"],
                "max_tokens": kwargs["max_tokens"],
                "prompt": kwargs["messages"][0]["content"],
                "system": system[0]["text"] if system else "",
            },
        )

    # ── scripting ──

    def use(self, route):
        self.route = route
        if route in ("openrouter", "fallback"):
            self.monkeypatch.setenv("OPENROUTER_API_KEY", "test")
        if route in ("anthropic", "fallback"):
            self.monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
        return self

    def push(self, provider, reply):
        self.queues[provider].append(reply)
        return self

    def answer(self, text, *, cut=False, reason=_AUTO, tokens=7, before=None):
        """Queue one LLM answer on the current route.

        On the fallback route OpenRouter refuses the connection first and
        Anthropic answers. ``before`` runs when the answering request arrives.
        """
        provider = ANSWERING[self.route]
        if reason is _AUTO:
            reason = (CUT if cut else STOP)[provider]
        if self.route == "fallback":
            self.push("openrouter", httpx.ConnectError("openrouter down"))
        build = or_reply if provider == "openrouter" else an_reply
        reply = build(text, reason, tokens)
        if before is None:
            return self.push(provider, reply)

        def hooked():
            before()
            return reply

        return self.push(provider, hooked)

    def telemetry_on(self):
        self.monkeypatch.setenv("BVT_TELEMETRY", "1")
        return self.events_path

    # ── reading ──

    def boundary(self):
        return [
            (request["provider"], request["max_tokens"]) for request in self.requests
        ]

    def logical_caps(self):
        return [call["max_tokens"] for call in self.logical]

    def logical_prompts(self):
        return [call["prompt"] for call in self.logical]


@pytest.fixture
def env_guard():
    """The process environment after a test is what it was before it.

    Only names are compared and reported, never values.
    """
    before = {key: hash(value) for key, value in os.environ.items()}
    yield
    after = {key: hash(value) for key, value in os.environ.items()}
    changed = sorted(
        key
        for key in set(before) | set(after)
        if key != "PYTEST_CURRENT_TEST" and before.get(key) != after.get(key)
    )
    assert changed == [], f"environment not restored for: {changed}"


@pytest.fixture(scope="module", autouse=True)
def attempt_counter_guard():
    """This module leaves ai.telemetry's attempt counter where it found it."""
    from ai.telemetry import current_attempt_no

    before = current_attempt_no()
    yield
    assert current_attempt_no() == before


@pytest.fixture
def harness(env_guard, monkeypatch, tmp_path):
    from ai import analyst, llm_client, telemetry
    from pipeline import api_guard

    # The transport functions advance telemetry's attempt counter even with
    # telemetry off. Outside a call_context that would outlive the test.
    attempt_token = telemetry._attempt_no.set(telemetry._attempt_no.get())

    for name in (
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_MODEL",
        "BVT_ANTHROPIC_MODEL_HEAVY",
        "BVT_OPENROUTER_MODEL_HEAVY",
        "BVT_RUN_ID",
        "BVT_CACHE_NS",
        "API_GUARD_OPENROUTER_DAILY_LIMIT",
        "API_GUARD_ANTHROPIC_DAILY_LIMIT",
    ):
        monkeypatch.delenv(name, raising=False)
    # Telemetry is off unless a test turns it on; even then it writes here.
    events_path = tmp_path / "events.jsonl"
    monkeypatch.setenv("BVT_TELEMETRY", "0")
    monkeypatch.setenv("BVT_TELEMETRY_PATH", str(events_path))

    # ApiGuard persists its counters; keep them out of the repository's .cache.
    api_guard.ApiGuard._reset_singleton()
    guard_dir = tmp_path / "api_guard"
    monkeypatch.setattr(api_guard, "_CACHE_DIR", guard_dir)
    monkeypatch.setattr(api_guard, "_USAGE_FILE", guard_dir / "api_usage.json")
    monkeypatch.setattr(api_guard, "_USAGE_LOCK", guard_dir / "api_usage.lock")
    guard = api_guard.ApiGuard.get()
    for provider in ("openrouter", "anthropic"):
        guard.configure(
            provider,
            daily_limit=1000,
            failure_threshold=50,
            max_retries=0,
            base_delay=0,
            max_delay=0,
        )

    h = Harness(monkeypatch, guard, events_path)
    monkeypatch.setattr(llm_client._openrouter_client, "post", h.post)
    monkeypatch.setattr(
        llm_client,
        "_get_anthropic_client",
        lambda key: SimpleNamespace(messages=SimpleNamespace(create=h.create)),
    )

    # Step cache and database: reached only by the tests that replace these.
    monkeypatch.setattr(analyst, "_LLM_CACHE_DIR", tmp_path / "llm_cache")
    for name in ("_get_cached", "_set_cached", "_save_analysis"):
        monkeypatch.setattr(analyst, name, h.closed(name))

    # Logical calls: record, then hand over to the real ask_structured().
    real_ask_structured = analyst.ask_structured

    def recording_ask_structured(prompt, **kwargs):
        h.logical.append({"prompt": prompt, **kwargs})
        return real_ask_structured(prompt, **kwargs)

    monkeypatch.setattr(analyst, "ask_structured", recording_ask_structured)

    yield h
    # Restore shared state first: the assertions below may stop the teardown.
    telemetry._attempt_no.reset(attempt_token)
    api_guard.ApiGuard._reset_singleton()
    assert h.unexpected == [], f"reached without being scripted: {h.unexpected}"
    leftovers = {name: len(queue) for name, queue in h.queues.items() if queue}
    assert leftovers == {}, f"scripted replies nobody asked for: {leftovers}"
    # _ask_json() passes ask_structured() the same keywords as before K-0D.
    assert all(
        set(call) == {"prompt", "system", "model", "max_tokens"} for call in h.logical
    ), h.logical
    assert not (tmp_path / "llm_cache").exists()


def ask_json(max_tokens=1024):
    from ai import analyst

    return analyst.AIAnalyst()._ask_json(PROMPT, SYSTEM, max_tokens)


def analyst_log(caplog):
    """Messages logged by ai.analyst only (the fallback route logs elsewhere too)."""
    return "\n".join(
        record.getMessage() for record in caplog.records if record.name == "ai.analyst"
    )


def notes_of(exc):
    return list(getattr(exc, "__notes__", []))


def open_circuit(guard, provider):
    circuit = guard._circuits[provider]
    circuit.status = "open"
    circuit.last_failure_time = time.time()


def fail_record_success_once(h, provider, error=None):
    """Make ApiGuard's bookkeeping fail right after the transport returned.

    By then the transport function has published its metadata, so this is the
    one way an answer can be discarded after it was published.
    """
    real = h.guard.record_success
    armed = [True]

    def record_success(name):
        if name == provider and armed:
            armed.clear()
            raise (
                error if error is not None else RuntimeError("usage bookkeeping failed")
            )
        return real(name)

    h.monkeypatch.setattr(h.guard, "record_success", record_success)


def _events(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


# ── response metadata reaches the caller ─────────────────────────────────────


@pytest.mark.parametrize("entrypoint", ["ask", "ask_structured"])
@pytest.mark.parametrize("route", ROUTES)
def test_metadata_of_the_answering_provider_reaches_the_caller(
    harness, route, entrypoint
):
    from ai import llm_client

    h = harness.use(route).answer("hello", tokens=11)
    with llm_client.capture_response_meta() as captured:
        text = getattr(llm_client, entrypoint)(
            "p", system="s", model=llm_client.MODEL_LIGHT, max_tokens=321
        )

    assert text == "hello"
    assert type(text) is str  # string consumers get exactly what they got before
    provider = ANSWERING[route]
    meta = captured.meta
    assert (meta.provider, meta.model, meta.stop_reason) == (
        provider,
        LIGHT_MODEL[provider],
        STOP[provider],
    )
    assert (meta.max_tokens, meta.output_tokens, meta.truncated) == (321, 11, False)
    assert h.boundary() == boundary_for(route, [321])


@pytest.mark.parametrize("route", ROUTES)
def test_metadata_marks_a_response_cut_off_at_the_cap(harness, route):
    from ai import llm_client

    harness.use(route).answer("partial", cut=True, tokens=64)
    with llm_client.capture_response_meta() as captured:
        llm_client.ask_structured("p", max_tokens=64)

    assert captured.meta.stop_reason == CUT[ANSWERING[route]]
    assert captured.meta.truncated is True


@pytest.mark.parametrize(
    ("provider", "stop_reason", "expected"),
    [
        ("anthropic", "max_tokens", True),
        ("anthropic", "end_turn", False),
        ("anthropic", "stop_sequence", False),
        ("anthropic", "tool_use", False),
        ("anthropic", "pause_turn", False),
        ("anthropic", "refusal", False),
        ("anthropic", "model_context_window_exceeded", False),
        ("anthropic", "length", False),  # OpenRouter's marker, not Anthropic's
        ("anthropic", None, False),
        ("openrouter", "length", True),
        ("openrouter", "stop", False),
        ("openrouter", "tool_calls", False),
        ("openrouter", "content_filter", False),
        ("openrouter", "error", False),
        ("openrouter", "max_tokens", False),  # Anthropic's marker, not OpenRouter's
        ("openrouter", None, False),
        ("someone_else", "max_tokens", False),
        ("someone_else", "length", False),
        ("anthropic", "MAX_TOKENS", False),
        ("anthropic", 0, False),
        ("openrouter", 7, False),
    ],
)
def test_truncation_is_one_marker_per_provider(provider, stop_reason, expected):
    from ai.llm_client import ResponseMeta

    meta = ResponseMeta(
        provider=provider,
        model="m",
        stop_reason=stop_reason,
        max_tokens=10,
        output_tokens=10,
    )
    assert meta.truncated is expected


def test_capture_sees_only_the_response_made_inside_its_block(harness):
    from ai import llm_client

    h = harness.use("anthropic")
    h.answer("first", cut=True).answer("second").answer("third", tokens=3)

    llm_client.ask_structured("outside any block", max_tokens=50)
    with llm_client.capture_response_meta() as idle:
        pass
    assert idle.meta is None  # nothing left over from the earlier response

    with llm_client.capture_response_meta() as outer:
        with llm_client.capture_response_meta() as inner:
            llm_client.ask_structured("inner", max_tokens=60)
        assert inner.meta.max_tokens == 60
        assert outer.meta is None  # the inner block took it
        llm_client.ask_structured("outer", max_tokens=70)
    assert (outer.meta.max_tokens, outer.meta.output_tokens) == (70, 3)
    assert inner.meta.max_tokens == 60  # a finished capture keeps what it saw


def test_outer_capture_is_untouched_by_an_inner_block_that_raised(harness):
    from ai import llm_client

    h = harness.use("anthropic")
    h.answer("first", tokens=5).push("anthropic", RuntimeError("provider exploded"))
    h.answer("after")

    with llm_client.capture_response_meta() as outer:
        llm_client.ask_structured("a", max_tokens=50)
        with pytest.raises(RuntimeError, match="provider exploded"):
            with llm_client.capture_response_meta() as inner:
                llm_client.ask_structured("b", max_tokens=60)
        # Checked before the outer block makes another call: a later success
        # would hide a capture that was not put back.
        assert inner.meta is None
        assert (outer.meta.max_tokens, outer.meta.output_tokens) == (50, 5)
        llm_client.ask_structured("c", max_tokens=70)
    assert outer.meta.max_tokens == 70


# A call that raises leaves no metadata behind — on both public entry points.


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
@pytest.mark.parametrize("route", SINGLE)
def test_capture_stays_empty_when_the_request_fails(harness, route, entrypoint):
    from ai import llm_client

    harness.use(route).push(route, RuntimeError("provider exploded"))
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(RuntimeError, match="provider exploded"):
            getattr(llm_client, entrypoint)("p", max_tokens=50)
    assert captured.meta is None


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_capture_is_emptied_when_a_later_call_in_the_block_is_blocked(
    harness, entrypoint
):
    from ai import llm_client
    from pipeline.api_guard import QuotaExceededError

    h = harness.use("anthropic")
    h.guard.configure("anthropic", daily_limit=1)
    h.answer("first", cut=True)
    with llm_client.capture_response_meta() as captured:
        getattr(llm_client, entrypoint)("p", max_tokens=50)
        assert captured.meta.truncated is True
        with pytest.raises(QuotaExceededError):
            getattr(llm_client, entrypoint)("p", max_tokens=50)
    assert captured.meta is None  # not the first call's metadata
    assert h.boundary() == [("anthropic", 50)]


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_answer_discarded_after_publishing_is_replaced_by_the_fallbacks(
    harness, entrypoint
):
    """OpenRouter answers, ApiGuard's bookkeeping fails, Anthropic answers."""
    from ai import llm_client

    h = harness.use("fallback")
    h.push("openrouter", or_reply("from openrouter", "length", 9))
    h.push("anthropic", an_reply("from anthropic", "end_turn", 4))
    fail_record_success_once(h, "openrouter")
    with llm_client.capture_response_meta() as captured:
        text = getattr(llm_client, entrypoint)("p", max_tokens=50)

    assert text == "from anthropic"
    assert (captured.meta.provider, captured.meta.truncated) == ("anthropic", False)
    assert h.boundary() == [("openrouter", 50), ("anthropic", 50)]


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_answer_discarded_after_publishing_leaves_nothing_when_fallback_fails(
    harness, entrypoint
):
    from ai import llm_client

    h = harness.use("fallback")
    h.push("openrouter", or_reply("from openrouter", "length", 9))
    h.push("anthropic", RuntimeError("anthropic exploded"))
    fail_record_success_once(h, "openrouter")
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(RuntimeError, match="anthropic exploded"):
            getattr(llm_client, entrypoint)("p", max_tokens=50)

    assert captured.meta is None  # not OpenRouter's discarded answer
    assert h.boundary() == [("openrouter", 50), ("anthropic", 50)]


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_direct_answer_discarded_after_publishing_leaves_nothing(harness, entrypoint):
    from ai import llm_client

    h = harness.use("anthropic").answer("from anthropic", cut=True)
    fail_record_success_once(h, "anthropic")
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(RuntimeError, match="usage bookkeeping failed"):
            getattr(llm_client, entrypoint)("p", max_tokens=50)

    assert captured.meta is None
    assert h.boundary() == [("anthropic", 50)]


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_capture_is_emptied_at_the_start_of_each_call(harness, entrypoint):
    """A later call that publishes nothing must not inherit earlier metadata."""
    from ai import llm_client

    h = harness.use("anthropic").answer("first", cut=True)
    with llm_client.capture_response_meta() as captured:
        getattr(llm_client, entrypoint)("p", max_tokens=50)
        assert captured.meta.truncated is True
        # A stand-in transport, as other tests install, publishes nothing.
        h.monkeypatch.setattr(
            llm_client, "_ask_anthropic", lambda *args, **kwargs: "plain"
        )
        assert getattr(llm_client, entrypoint)("p", max_tokens=50) == "plain"
    assert captured.meta is None


def test_transport_publishes_only_after_the_body_was_read(harness):
    """Called directly, a transport function that cannot read the body publishes nothing."""
    from ai import llm_client

    h = harness.use("fallback").push("openrouter", or_raw({"choices": [{}]}))
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(KeyError):
            llm_client._ask_openrouter("p", max_tokens=50)
    assert captured.meta is None

    reply = an_reply("unused", "max_tokens", 50)
    reply.content = []
    h.push("anthropic", reply)
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(IndexError):
            llm_client._ask_anthropic("p", max_tokens=50)
    assert captured.meta is None


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
@pytest.mark.parametrize(
    ("route", "provider"),
    [
        ("openrouter", "openrouter"),
        ("anthropic", "anthropic"),
        ("fallback", "openrouter"),
    ],
)
def test_interrupt_after_publishing_leaves_nothing(
    harness, route, provider, entrypoint
):
    """KeyboardInterrupt is not an Exception; the metadata must go all the same."""
    from ai import llm_client

    h = harness.use(route)
    build = or_reply if provider == "openrouter" else an_reply
    h.push(provider, build("published", CUT[provider], 9))
    interrupt = KeyboardInterrupt()
    fail_record_success_once(h, provider, interrupt)
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(KeyboardInterrupt) as caught:
            getattr(llm_client, entrypoint)("p", max_tokens=50)

    assert caught.value is interrupt
    assert captured.meta is None
    assert h.boundary() == [(provider, 50)]  # and no fallback was started


@pytest.mark.parametrize("entrypoint", ENTRYPOINTS)
def test_failed_fallback_raises_the_same_exception_with_the_same_chaining(
    harness, entrypoint
):
    """ask() chains the fallback's failure to OpenRouter's; ask_structured() does not."""
    from ai import llm_client

    first = httpx.ConnectError("openrouter down")
    second = ValueError("bad request shape")
    harness.use("fallback").push("openrouter", first).push("anthropic", second)
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(ValueError) as caught:
            getattr(llm_client, entrypoint)("p", max_tokens=50)

    error = caught.value
    assert error is second
    assert error.__context__ is first
    if entrypoint == "ask":
        assert error.__cause__ is first
        assert error.__suppress_context__ is True
    else:
        assert error.__cause__ is None
        assert error.__suppress_context__ is False
    assert captured.meta is None


def test_entry_points_keep_their_names_and_signatures():
    from ai import llm_client

    assert llm_client.ask.__name__ == "ask"
    assert llm_client.ask_structured.__name__ == "ask_structured"
    assert llm_client.ask.__doc__.startswith("Single prompt -> text response.")
    assert llm_client.ask_structured.__doc__.startswith("Request structured response")
    # names, kinds, defaults and annotations, as they were before K-0D
    assert str(inspect.signature(llm_client.ask)) == (
        "(prompt: str, system: str = '', model: str = '', "
        "max_tokens: int = 4096, temperature: float = 0.3) -> str"
    )
    assert str(inspect.signature(llm_client.ask_structured)) == (
        "(prompt: str, system: str = '', model: str = '', max_tokens: int = 4096) -> str"
    )


def test_captures_open_in_two_threads_at_once_do_not_mix():
    """Both captures are open while each thread publishes a response.

    The two threads publish through _publish_response_meta(), the function the
    transport functions use, instead of calling ask_structured(): no fixture
    and no transport is involved, so a worker that outlived a failed run of
    this test could not reach a provider.
    """
    from ai import llm_client

    def published(max_tokens):
        return llm_client.ResponseMeta(
            provider="anthropic",
            model="m",
            stop_reason="end_turn",
            max_tokens=max_tokens,
            output_tokens=1,
        )

    worker_open = threading.Event()
    released = threading.Event()
    parent_published = []  # filled once the parent has published
    seen = {}

    def worker():
        with llm_client.capture_response_meta() as captured:
            worker_open.set()
            if not released.wait(10) or not parent_published:
                return  # timed out, or the parent never got that far
            seen["before_own_publish"] = captured.meta
            llm_client._publish_response_meta(published(111))
        seen["worker"] = captured.meta

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        with llm_client.capture_response_meta() as mine:
            assert worker_open.wait(10)
            # the worker's capture is open at this point
            llm_client._publish_response_meta(published(222))
            parent_published.append(True)
            released.set()
            thread.join()  # the worker only waits for `released`, which is set
            # the worker has published by now; it must not have landed here
            assert mine.meta.max_tokens == 222
    finally:
        # No timeout: the worker's only wait is bounded and already released,
        # so this returns, and the worker has ended before the test does.
        released.set()
        thread.join()

    assert seen["before_own_publish"] is None  # the parent's did not land there
    assert seen["worker"].max_tokens == 111


def test_response_to_a_call_made_in_another_thread_stays_in_that_thread(harness):
    """Through the real entry point: the worker's response is the worker's."""
    from ai import llm_client

    h = harness.use("anthropic").answer("for the worker", tokens=5)
    seen = {}

    def worker():
        # Calls at once, with nothing to wait for: it cannot still be running
        # when join() returns, so it never outlives the fixture.
        with llm_client.capture_response_meta() as captured:
            llm_client.ask_structured("w", max_tokens=111)
        seen["worker"] = captured.meta

    with llm_client.capture_response_meta() as mine:
        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()

    assert (seen["worker"].max_tokens, seen["worker"].output_tokens) == (111, 5)
    assert mine.meta is None
    assert h.boundary() == [("anthropic", 111)]


# ── paths that must not change ───────────────────────────────────────────────


@pytest.mark.parametrize("route", ROUTES)
def test_complete_response_is_one_request(harness, caplog, route):
    h = harness.use(route).answer(GOOD)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        assert ask_json(1024) == {"ok": True}

    assert h.logical_caps() == [1024]
    assert h.logical_prompts() == [PROMPT]
    assert h.boundary() == boundary_for(route, [1024])
    assert analyst_log(caplog) == ""


@pytest.mark.parametrize("route", ROUTES)
def test_malformed_response_is_repaired_at_the_same_cap(harness, caplog, route):
    h = harness.use(route).answer(MALFORMED).answer(GOOD)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        assert ask_json(1024) == {"ok": True}

    assert h.logical_caps() == [1024, 1024]
    assert h.logical_prompts() == [PROMPT, PROMPT + REPAIR_SUFFIX]
    assert [call["system"] for call in h.logical] == [SYSTEM, SYSTEM]
    assert h.boundary() == boundary_for(route, [1024, 1024])
    assert [
        request["prompt"]
        for request in h.requests
        if request["provider"] == ANSWERING[route]
    ] == [
        PROMPT,
        PROMPT + REPAIR_SUFFIX,
    ]
    assert "JSON 파싱 실패 — 재시도 중" in analyst_log(caplog)
    assert "LLM 응답 잘림" not in caplog.text


@pytest.mark.parametrize("route", ROUTES)
def test_malformed_twice_is_a_plain_value_error_after_two_calls(harness, route):
    h = harness.use(route).answer(MALFORMED).answer(MALFORMED)
    with pytest.raises(ValueError) as caught:
        ask_json(1024)

    assert type(caught.value) is ValueError  # not the truncation error
    assert str(caught.value).startswith("JSON 파싱 실패: ")
    assert h.logical_caps() == [1024, 1024]
    assert h.boundary() == boundary_for(route, [1024, 1024])


def test_without_metadata_the_behaviour_is_the_old_one(harness):
    """A stand-in for ask_structured() publishes nothing: no cap is raised."""
    from ai import analyst, llm_client

    calls = []

    def fake(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return CUT_JSON if len(calls) == 1 else GOOD

    harness.monkeypatch.setattr(analyst, "ask_structured", fake)
    assert ask_json(1024) == {"ok": True}

    expected = {
        "system": SYSTEM,
        "model": llm_client._ANTHROPIC_DEFAULT_MODEL,
        "max_tokens": 1024,
    }
    assert calls == [(PROMPT, expected), (PROMPT + REPAIR_SUFFIX, expected)]
    assert harness.requests == []


OTHER_REASONS = [
    ("anthropic", "stop_sequence"),
    ("anthropic", "tool_use"),
    ("anthropic", "pause_turn"),
    ("anthropic", "refusal"),
    ("anthropic", "model_context_window_exceeded"),
    ("anthropic", "length"),  # the other provider's marker
    ("anthropic", "something_new"),
    ("anthropic", 7),
    ("anthropic", None),
    ("openrouter", "tool_calls"),
    ("openrouter", "content_filter"),
    ("openrouter", "error"),
    ("openrouter", "max_tokens"),  # the other provider's marker
    ("openrouter", "something_new"),
    ("openrouter", 7),
    ("openrouter", None),
    ("fallback", "refusal"),
    ("fallback", None),
]


@pytest.mark.parametrize(("route", "reason"), OTHER_REASONS)
def test_other_stop_reasons_take_the_old_path(harness, route, reason):
    h = harness.use(route).answer(GOOD, reason=reason)
    assert ask_json(1024) == {"ok": True}
    assert h.logical_caps() == [1024]

    h.answer(MALFORMED, reason=reason).answer(GOOD)
    assert ask_json(1024) == {"ok": True}
    assert h.logical_caps() == [1024, 1024, 1024]
    assert h.logical_prompts() == [PROMPT, PROMPT, PROMPT + REPAIR_SUFFIX]
    assert h.boundary() == boundary_for(route, [1024, 1024, 1024])


# ── the truncation path ──────────────────────────────────────────────────────


@pytest.mark.parametrize("cap", [512, 1024, 2048, 4096])
@pytest.mark.parametrize("route", ROUTES)
def test_truncated_response_is_retried_once_with_a_doubled_cap(
    harness, caplog, route, cap
):
    h = harness.use(route).answer(CUT_JSON, cut=True, tokens=cap).answer(GOOD)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        assert ask_json(cap) == {"ok": True}

    assert h.logical_caps() == [cap, cap * 2]
    assert h.logical_prompts() == [PROMPT, PROMPT]  # no repair suffix
    assert [call["system"] for call in h.logical] == [SYSTEM, SYSTEM]
    assert len({call["model"] for call in h.logical}) == 1
    # every boundary call of a logical call carries that call's cap
    assert h.boundary() == boundary_for(route, [cap, cap * 2])
    assert {request["prompt"] for request in h.requests} == {PROMPT}
    assert analyst_log(caplog).count("LLM 응답 잘림") == 1
    assert "JSON 파싱 실패" not in caplog.text
    assert LEAK not in caplog.text
    assert PROMPT not in caplog.text


@pytest.mark.parametrize("route", ROUTES)
def test_truncated_twice_fails_after_exactly_two_calls(harness, caplog, route):
    from ai.llm_client import TruncatedResponseError

    h = harness.use(route)
    h.answer(CUT_JSON, cut=True, tokens=1024).answer(CUT_JSON, cut=True, tokens=2048)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        with pytest.raises(TruncatedResponseError) as caught:
            ask_json(1024)

    assert isinstance(caught.value, ValueError)  # existing handlers still catch it
    assert h.logical_caps() == [1024, 2048]
    assert h.boundary() == boundary_for(route, [1024, 2048])
    message = str(caught.value)
    assert "max_tokens=2048" in message
    assert f"provider={ANSWERING[route]}" in message
    for text in (message, caplog.text):
        assert LEAK not in text
        assert PROMPT not in text
    assert "JSON 파싱 실패" not in message


@pytest.mark.parametrize("route", ROUTES)
def test_malformed_answer_to_the_truncation_retry_is_not_repaired(harness, route):
    """The old parse error comes up unchanged; there is no third call."""
    h = harness.use(route).answer(CUT_JSON, cut=True).answer(MALFORMED)
    with pytest.raises(ValueError) as caught:
        ask_json(1024)

    assert type(caught.value) is ValueError
    assert str(caught.value).startswith("JSON 파싱 실패: ")
    assert h.logical_caps() == [1024, 2048]
    assert h.logical_prompts() == [PROMPT, PROMPT]
    assert h.boundary() == boundary_for(route, [1024, 2048])


@pytest.mark.parametrize("text", [GOOD + "\n   \n\t", "\n" + GOOD, '[{"ok": true}]'])
@pytest.mark.parametrize("route", ROUTES)
def test_truncated_response_that_is_whole_json_is_accepted(
    harness, caplog, route, text
):
    h = harness.use(route).answer(text, cut=True, tokens=1024)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        assert ask_json(1024) == json.loads(text)

    assert h.logical_caps() == [1024]
    assert h.boundary() == boundary_for(route, [1024])
    assert analyst_log(caplog) == ""


FRAGMENTS = {
    # text of a cut-off response -> what _parse_json() extracts from it
    "leading object": ('{"meta": 1}\n{"segments": ["a", "b', {"meta": 1}),
    "example block": (
        '예시:\n```json\n{"example": 1}\n```\n결과:\n```json\n{"segments": ["a", "b',
        {"example": 1},
    ),
    "complete block, prose cut": (
        '```json\n{"partial": false}\n```\n설명: 이 결과는',
        {"partial": False},
    ),
    "cut number": ("12", 12),
}


@pytest.mark.parametrize("kind", sorted(FRAGMENTS))
@pytest.mark.parametrize("route", ROUTES)
def test_part_extracted_from_a_truncated_response_is_not_accepted(harness, route, kind):
    from ai import analyst

    text, extracted = FRAGMENTS[kind]
    # The extraction really does succeed on this text; otherwise the test
    # would pass for the wrong reason.
    assert analyst._parse_json(text) == extracted

    h = harness.use(route).answer(text, cut=True).answer(GOOD)
    assert ask_json(1024) == {"ok": True}
    assert h.logical_caps() == [1024, 2048]
    assert h.logical_prompts() == [PROMPT, PROMPT]
    assert h.boundary() == boundary_for(route, [1024, 2048])


@pytest.mark.parametrize("cap", [4097, 6000, 8191])
def test_raised_cap_stops_at_the_ceiling(harness, cap):
    h = harness.use("anthropic").answer(CUT_JSON, cut=True).answer(GOOD)
    assert ask_json(cap) == {"ok": True}
    assert h.logical_caps() == [cap, CEILING]
    assert h.boundary() == [("anthropic", cap), ("anthropic", CEILING)]


@pytest.mark.parametrize("cap", [CEILING, CEILING + 1, 10000])
@pytest.mark.parametrize("route", ROUTES)
def test_no_retry_when_the_cap_cannot_be_raised(harness, caplog, route, cap):
    from ai.llm_client import TruncatedResponseError

    h = harness.use(route).answer(CUT_JSON, cut=True, tokens=cap)
    with caplog.at_level(logging.WARNING, logger="ai.analyst"):
        with pytest.raises(TruncatedResponseError) as caught:
            ask_json(cap)

    assert h.logical_caps() == [cap]
    assert h.boundary() == boundary_for(route, [cap])
    assert f"max_tokens={cap}" in str(caught.value)
    assert LEAK not in str(caught.value)
    assert analyst_log(caplog) == ""  # nothing is retried, so nothing is announced


def test_complete_fenced_json_cut_off_at_the_ceiling_is_refused(harness):
    """Before K-0D this returned the fenced object after one call."""
    from ai import analyst
    from ai.llm_client import TruncatedResponseError

    assert analyst._parse_json(FENCED) == {"fenced": True}
    h = harness.use("openrouter").answer(FENCED, cut=True)
    with pytest.raises(TruncatedResponseError):
        ask_json(CEILING)
    assert h.logical_caps() == [CEILING]


@pytest.mark.parametrize("route", ROUTES)
def test_truncated_answer_to_the_repair_request(harness, route):
    from ai.llm_client import TruncatedResponseError

    h = harness.use(route)
    h.answer(MALFORMED).answer(GOOD + "\n\n", cut=True)
    assert ask_json(1024) == {"ok": True}

    h.answer(MALFORMED).answer(CUT_JSON, cut=True)
    with pytest.raises(TruncatedResponseError) as caught:
        ask_json(1024)
    assert LEAK not in str(caught.value)

    h.answer(MALFORMED).answer(FENCED, cut=True)
    with pytest.raises(TruncatedResponseError):
        ask_json(1024)

    assert h.logical_caps() == [1024] * 6  # the repair path never raises the cap
    assert h.logical_prompts() == [PROMPT, PROMPT + REPAIR_SUFFIX] * 3
    assert h.boundary() == boundary_for(route, [1024] * 6)


@pytest.mark.parametrize("text", [GOOD + "\n \n", '[{"ok": true}]'])
@pytest.mark.parametrize("route", ROUTES)
def test_truncated_but_whole_answer_to_the_truncation_retry_is_accepted(
    harness, route, text
):
    """The raised cap was hit again, but the text is a closed object or array."""
    h = harness.use(route).answer(CUT_JSON, cut=True).answer(text, cut=True)
    assert ask_json(1024) == json.loads(text)
    assert h.logical_caps() == [1024, 2048]
    assert h.boundary() == boundary_for(route, [1024, 2048])


# json.loads() refuses these without a JSONDecodeError: an integer beyond the
# interpreter's digit limit (plain ValueError) and nesting too deep to parse
# (RecursionError). Cut off or not, such text was not read as an object or array.
UNREADABLE_JSON = {
    "huge integer": "[" + "1" * 5000 + "]",
    "deep nesting": "[" * 100000 + "]" * 100000,
}


def _unreadable_json(kind):
    """The text, once this interpreter is seen to refuse it the way the test assumes."""
    text = UNREADABLE_JSON[kind]
    try:
        json.loads(text)
    except json.JSONDecodeError:
        pytest.skip("this interpreter reports the text as an ordinary JSON error")
    except (ValueError, RecursionError):
        return text
    pytest.skip("this interpreter parses the text")


@pytest.mark.parametrize("kind", sorted(UNREADABLE_JSON))
@pytest.mark.parametrize("route", ROUTES)
def test_truncated_json_that_cannot_be_read_is_retried_with_a_raised_cap(
    harness, route, kind
):
    text = _unreadable_json(kind)
    h = harness.use(route).answer(text, cut=True).answer(GOOD)
    assert ask_json(4096) == {"ok": True}
    assert h.logical_caps() == [4096, CEILING]
    assert h.logical_prompts() == [PROMPT, PROMPT]
    assert h.boundary() == boundary_for(route, [4096, CEILING])


@pytest.mark.parametrize("kind", sorted(UNREADABLE_JSON))
def test_truncated_json_that_cannot_be_read_as_the_second_response(harness, kind):
    from ai.llm_client import TruncatedResponseError

    text = _unreadable_json(kind)
    h = harness.use("anthropic")
    h.answer(CUT_JSON, cut=True).answer(text, cut=True)  # after the raised cap
    with pytest.raises(TruncatedResponseError):
        ask_json(1024)
    h.answer(MALFORMED).answer(text, cut=True)  # after the repair request
    with pytest.raises(TruncatedResponseError):
        ask_json(1024)
    assert h.logical_caps() == [1024, 2048, 1024, 1024]


@pytest.mark.parametrize("kind", sorted(UNREADABLE_JSON))
def test_truncated_json_that_cannot_be_read_at_the_ceiling(harness, kind):
    from ai.llm_client import TruncatedResponseError

    text = _unreadable_json(kind)
    h = harness.use("openrouter").answer(text, cut=True)
    with pytest.raises(TruncatedResponseError):
        ask_json(CEILING)
    assert h.logical_caps() == [CEILING]


SECOND_BODY_MISSING = [
    # first answer, first cut, second cut, error, caps
    (MALFORMED, False, False, AttributeError, [1024, 1024]),
    (MALFORMED, False, True, "truncated", [1024, 1024]),
    (CUT_JSON, True, False, AttributeError, [1024, 2048]),
    (CUT_JSON, True, True, "truncated", [1024, 2048]),
]


@pytest.mark.parametrize(
    ("first", "first_cut", "second_cut", "error", "caps"), SECOND_BODY_MISSING
)
def test_second_response_without_a_body(
    harness, first, first_cut, second_cut, error, caps
):
    """OpenRouter content=None on the second response; never a third call."""
    from ai.llm_client import TruncatedResponseError

    expected = TruncatedResponseError if error == "truncated" else error
    h = (
        harness.use("openrouter")
        .answer(first, cut=first_cut)
        .answer(None, cut=second_cut)
    )
    with pytest.raises(expected) as caught:
        ask_json(1024)

    assert type(caught.value) is expected
    assert h.logical_caps() == caps
    assert h.boundary() == boundary_for("openrouter", caps)


EMPTY_BODIES = [
    # route, body, cut, caps, second prompt
    ("openrouter", "", True, [1024, 2048], PROMPT),
    ("openrouter", None, True, [1024, 2048], PROMPT),
    ("anthropic", "", True, [1024, 2048], PROMPT),
    ("fallback", "", True, [1024, 2048], PROMPT),
    ("openrouter", "", False, [1024, 1024], PROMPT + REPAIR_SUFFIX),
    ("anthropic", "", False, [1024, 1024], PROMPT + REPAIR_SUFFIX),
    ("fallback", "", False, [1024, 1024], PROMPT + REPAIR_SUFFIX),
]


@pytest.mark.parametrize(("route", "body", "cut", "caps", "second"), EMPTY_BODIES)
def test_empty_first_response(harness, route, body, cut, caps, second):
    h = harness.use(route).answer(body, cut=cut).answer(GOOD)
    assert ask_json(1024) == {"ok": True}
    assert h.logical_caps() == caps
    assert h.logical_prompts() == [PROMPT, second]
    assert h.boundary() == boundary_for(route, caps)


def test_missing_body_without_truncation_is_unchanged(harness):
    """OpenRouter content=None with a normal stop: AttributeError, no retry."""
    h = harness.use("openrouter").answer(None)
    with pytest.raises(AttributeError):
        ask_json(1024)
    assert h.logical_caps() == [1024]
    assert h.boundary() == [("openrouter", 1024)]


# ── responses the transport function cannot read ─────────────────────────────

UNREADABLE = [
    # HTTP 200 body from OpenRouter -> what _ask_openrouter raises on it
    ({"choices": [{}]}, KeyError),
    ({"choices": [{"message": None}]}, TypeError),
    ({"choices": [None]}, AttributeError),
    ({"choices": {"a": 1}}, KeyError),
    ({"choices": [{"message": {"content": "ok"}}], "usage": None}, AttributeError),
    ([], AttributeError),
]


@pytest.mark.parametrize(("body", "error"), UNREADABLE)
def test_unreadable_openrouter_body_on_the_first_request(harness, body, error):
    from ai import llm_client

    # Both keys are set: these errors must not start the Anthropic fallback.
    h = harness.use("fallback").push("openrouter", or_raw(body))
    with pytest.raises(error) as caught:
        ask_json(1024)
    assert type(caught.value) is error
    assert notes_of(caught.value) == []
    assert h.logical_caps() == [1024]
    assert h.boundary() == [("openrouter", 1024)]

    h.push("openrouter", or_raw(body))
    with llm_client.capture_response_meta() as captured:
        with pytest.raises(error):
            llm_client.ask_structured("p", max_tokens=50)
    assert captured.meta is None


@pytest.mark.parametrize(("body", "error"), UNREADABLE)
def test_unreadable_openrouter_body_on_the_truncation_retry(harness, body, error):
    h = harness.use("fallback")
    h.push("openrouter", or_reply(CUT_JSON, "length", 1024))
    h.push("openrouter", or_raw(body))
    with pytest.raises(error) as caught:
        ask_json(1024)

    assert type(caught.value) is error
    assert len(notes_of(caught.value)) == 1
    assert h.logical_caps() == [1024, 2048]
    assert h.boundary() == [("openrouter", 1024), ("openrouter", 2048)]


def test_anthropic_response_without_content_is_unchanged(harness):
    reply = an_reply("unused", "max_tokens", 1024)
    reply.content = []
    h = harness.use("anthropic").push("anthropic", reply)
    with pytest.raises(IndexError):
        ask_json(1024)
    assert h.logical_caps() == [1024]


# ── quota, circuit breaker, fallback, HTTP retry ─────────────────────────────


@pytest.mark.parametrize("route", SINGLE)
def test_quota_exhausted_before_the_truncation_retry(harness, route):
    from pipeline.api_guard import QuotaExceededError

    h = harness.use(route)
    h.guard.configure(route, daily_limit=1)
    h.answer(CUT_JSON, cut=True)
    with pytest.raises(QuotaExceededError) as caught:
        ask_json(1024)

    error = caught.value
    assert type(error) is QuotaExceededError  # the block is not relabelled
    assert (error.provider, error.calls, error.limit) == (route, 1, 1)
    assert h.boundary() == [
        (route, 1024)
    ]  # the first request was sent, the retry was not
    assert h.logical_caps() == [1024, 2048]
    notes = notes_of(error)
    assert len(notes) == 1
    assert "max_tokens=1024" in notes[0]
    assert f"stop_reason={CUT[route]}" in notes[0]
    assert LEAK not in notes[0]
    assert PROMPT not in notes[0]


@pytest.mark.parametrize("route", SINGLE)
def test_circuit_open_before_the_truncation_retry(harness, route):
    from pipeline.api_guard import CircuitOpenError

    h = harness.use(route)
    h.answer(CUT_JSON, cut=True, before=lambda: open_circuit(h.guard, route))
    with pytest.raises(CircuitOpenError) as caught:
        ask_json(1024)

    assert type(caught.value) is CircuitOpenError
    assert caught.value.provider == route
    assert h.boundary() == [(route, 1024)]
    assert h.logical_caps() == [1024, 2048]
    notes = notes_of(caught.value)
    assert len(notes) == 1
    assert "max_tokens=1024" in notes[0]


@pytest.mark.parametrize("route", SINGLE)
def test_transport_error_on_the_truncation_retry_keeps_its_type(harness, route):
    h = harness.use(route)
    h.answer(CUT_JSON, cut=True).push(route, RuntimeError("provider exploded"))
    with pytest.raises(RuntimeError, match="provider exploded") as caught:
        ask_json(1024)

    assert type(caught.value) is RuntimeError
    assert h.boundary() == [(route, 1024), (route, 2048)]
    assert len(notes_of(caught.value)) == 1


@pytest.mark.parametrize("error_type", [KeyboardInterrupt, SystemExit])
@pytest.mark.parametrize("route", SINGLE)
def test_interrupted_truncation_retry_carries_the_note_too(harness, route, error_type):
    """KeyboardInterrupt and SystemExit are not Exceptions; the note still applies."""
    error = error_type()
    h = harness.use(route).answer(CUT_JSON, cut=True).push(route, error)
    with pytest.raises(error_type) as caught:
        ask_json(1024)

    assert caught.value is error
    assert h.boundary() == [(route, 1024), (route, 2048)]
    notes = notes_of(error)
    assert len(notes) == 1
    assert "max_tokens=1024" in notes[0]
    assert LEAK not in notes[0]


@pytest.mark.parametrize(
    "error_type", [RuntimeError, KeyboardInterrupt], ids=["error", "interrupt"]
)
@pytest.mark.parametrize("route", SINGLE)
def test_failed_repair_request_carries_no_note(harness, route, error_type):
    """Unchanged path: only the truncation retry annotates what it raises."""
    error = error_type("provider exploded")
    h = harness.use(route).answer(MALFORMED).push(route, error)
    with pytest.raises(error_type) as caught:
        ask_json(1024)

    assert caught.value is error
    assert notes_of(error) == []
    assert type(error.__context__) is ValueError  # the parse error, as before
    assert h.boundary() == [(route, 1024), (route, 1024)]


@pytest.mark.parametrize("route", SINGLE)
def test_blocked_first_request_is_unchanged(harness, route):
    from pipeline.api_guard import QuotaExceededError

    h = harness.use(route)
    h.guard.configure(route, daily_limit=1)
    h.guard.record_success(route)  # the day's only call is already spent
    with pytest.raises(QuotaExceededError) as caught:
        ask_json(1024)

    assert type(caught.value) is QuotaExceededError
    assert h.requests == []  # nothing was sent
    assert h.logical_caps() == [1024]
    assert notes_of(caught.value) == []


def test_truncation_retry_can_be_answered_by_the_fallback_provider(harness):
    """OpenRouter answers cut off, then runs out of quota; Anthropic takes the retry."""
    from ai.llm_client import TruncatedResponseError

    h = harness.use("fallback")
    h.guard.configure("openrouter", daily_limit=1)
    h.push("openrouter", or_reply(CUT_JSON, "length", 1024))
    h.push("anthropic", an_reply(GOOD, "end_turn", 9))
    assert ask_json(1024) == {"ok": True}
    assert h.boundary() == [("openrouter", 1024), ("anthropic", 2048)]

    # The answering provider's own marker decides: Anthropic says max_tokens.
    h.guard.configure("openrouter", daily_limit=2)
    h.push("openrouter", or_reply(CUT_JSON, "length", 1024))
    h.push("anthropic", an_reply(CUT_JSON, "max_tokens", 2048))
    with pytest.raises(TruncatedResponseError) as caught:
        ask_json(1024)
    assert "provider=anthropic" in str(caught.value)
    assert h.boundary()[2:] == [("openrouter", 1024), ("anthropic", 2048)]
    assert h.logical_caps() == [1024, 2048, 1024, 2048]


@pytest.mark.parametrize("route", SINGLE)
def test_truncation_is_not_counted_as_a_transport_failure(harness, route):
    from ai.llm_client import TruncatedResponseError

    h = harness.use(route)
    h.answer(CUT_JSON, cut=True).answer(CUT_JSON, cut=True)
    with pytest.raises(TruncatedResponseError):
        ask_json(1024)

    assert h.guard._circuits[route].status == "closed"
    assert h.guard._circuits[route].consecutive_failures == 0
    assert h.guard.get_usage_summary()[route]["calls"] == 2


def test_http_retry_stays_inside_one_logical_call(harness):
    """@api_guard resends after a dropped connection; K-0D does not count that."""
    from ai import llm_client
    from ai.telemetry import call_context

    path = harness.telemetry_on()
    h = harness.use("openrouter")
    h.guard.configure("openrouter", max_retries=1)
    h.push("openrouter", httpx.ConnectError("blip"))
    h.answer(CUT_JSON, cut=True).answer(GOOD)

    with call_context("Acme", "classify"):
        assert ask_json(1024) == {"ok": True}

    assert h.logical_caps() == [1024, 2048]
    assert h.boundary() == [
        ("openrouter", 1024),
        ("openrouter", 1024),
        ("openrouter", 2048),
    ]
    assert h.guard.get_usage_summary()["openrouter"]["calls"] == 2
    attempts = [event for event in _events(path) if event["event"] == "attempt"]
    assert [
        (event["outcome"], event["operation"], event["attempt_no"])
        for event in attempts
    ] == [
        ("http_error", "primary", 1),
        ("success", "primary", 2),
        ("success", "truncation_retry", 3),
    ]

    # The metadata is that of the answer, not of the dropped attempt.
    h.push("openrouter", httpx.ConnectError("blip")).answer("text", cut=True, tokens=5)
    with llm_client.capture_response_meta() as captured:
        llm_client.ask_structured("p", max_tokens=50)
    assert (captured.meta.truncated, captured.meta.output_tokens) == (True, 5)


# ── telemetry, cache, callers ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("first", "operations"),
    [
        ("truncated", ["primary", "truncation_retry"]),
        ("malformed", ["primary", "parse_repair"]),
    ],
)
@pytest.mark.parametrize("route", ROUTES)
def test_one_attempt_event_per_boundary_call(harness, route, first, operations):
    """Counts fake boundary calls, not HTTP requests inside the Anthropic SDK."""
    from ai.telemetry import call_context

    path = harness.telemetry_on()
    h = harness.use(route)
    if first == "truncated":
        h.answer(CUT_JSON, cut=True)
    else:
        h.answer(MALFORMED)
    h.answer(GOOD)

    with call_context("Acme", "classify"):
        assert ask_json(1024) == {"ok": True}

    events = _events(path)
    attempts = [event for event in events if event["event"] == "attempt"]
    assert len(attempts) == len(h.requests) == len(boundary_for(route, [0, 0]))
    answered = [event for event in attempts if event["outcome"] == "success"]
    assert [event["operation"] for event in answered] == operations
    provider = ANSWERING[route]
    metas = [event for event in events if event["event"] == "llm_response_meta"]
    assert [event["operation"] for event in metas] == operations
    assert [event["stop_reason"] for event in metas] == [
        CUT[provider] if first == "truncated" else STOP[provider],
        STOP[provider],
    ]
    assert LEAK not in path.read_text(encoding="utf-8")


def test_telemetry_off_writes_no_event_file(harness):
    from ai.telemetry import call_context

    h = harness.use("openrouter").answer(CUT_JSON, cut=True).answer(GOOD)
    with call_context("Acme", "classify"):
        assert ask_json(1024) == {"ok": True}

    assert h.logical_caps() == [1024, 2048]
    assert not h.events_path.exists()


def _cached_step(harness):
    """Run _cached_json_step with its cache and database calls recorded."""
    from ai import analyst

    seen = []

    def lookup(*args, **kwargs):
        seen.append(("lookup", args))
        return None  # a cache miss

    def store(*args, **kwargs):
        seen.append(("cache", args))

    def save(*args, **kwargs):
        seen.append(("db", args))

    harness.monkeypatch.setattr(analyst, "_get_cached", lookup)
    harness.monkeypatch.setattr(analyst, "_set_cached", store)
    harness.monkeypatch.setattr(analyst, "_save_analysis", save)
    return analyst.AIAnalyst(), seen


def test_cached_step_stores_nothing_when_truncation_cannot_be_recovered(harness):
    from ai.llm_client import TruncatedResponseError

    h = harness.use("anthropic").answer(CUT_JSON, cut=True).answer(CUT_JSON, cut=True)
    analyst_, seen = _cached_step(harness)
    with pytest.raises(TruncatedResponseError):
        analyst_._cached_json_step("Acme", "classify", lambda: PROMPT)

    assert [kind for kind, _ in seen] == ["lookup"]  # a miss, then nothing stored
    assert h.logical_caps() == [1024, 2048]  # the step's default cap, then doubled
    assert h.logical_prompts() == [PROMPT, PROMPT]
    assert h.boundary() == [("anthropic", 1024), ("anthropic", 2048)]


def test_cached_step_stores_the_retried_result_once(harness):
    h = harness.use("anthropic").answer(CUT_JSON, cut=True).answer(GOOD)
    analyst_, seen = _cached_step(harness)
    result = analyst_._cached_json_step("Acme", "classify", lambda: PROMPT)

    assert result == {"ok": True}
    assert [kind for kind, _ in seen] == ["lookup", "cache", "db"]
    assert all(args[:3] == ("Acme", "classify", {"ok": True}) for _, args in seen[1:])
    assert h.logical_caps() == [1024, 2048]
    assert h.boundary() == [("anthropic", 1024), ("anthropic", 2048)]


def test_scenario_repair_call_shape_still_works(harness):
    """pipeline/profile_generator.py calls _ask_json() with these keywords."""
    from ai import analyst, llm_client

    h = harness.use("anthropic").answer(CUT_JSON, cut=True).answer(GOOD)
    result = analyst.AIAnalyst()._ask_json(
        PROMPT, system=SYSTEM, max_tokens=4096, model=llm_client.MODEL_HEAVY
    )

    assert result == {"ok": True}
    assert h.boundary() == [("anthropic", 4096), ("anthropic", CEILING)]
    assert [(r["model"], r["prompt"], r["system"]) for r in h.requests] == [
        (llm_client.MODEL_HEAVY, PROMPT, SYSTEM)
    ] * 2
