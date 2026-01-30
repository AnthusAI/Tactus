import pytest

import dspy

from tactus.dspy.broker_lm import BrokeredLM, _split_provider_model


class DummyClient:
    def __init__(self, events):
        self._events = events

    async def llm_chat(self, **_kwargs):
        for event in self._events:
            yield event


class DummyStream:
    def __init__(self):
        self.sent = []

    async def send(self, chunk):
        self.sent.append(chunk)


class CapturingClient:
    def __init__(self, events):
        self._events = events
        self.calls = []

    async def llm_chat(self, **kwargs):
        self.calls.append(kwargs)
        for event in self._events:
            yield event


def test_split_provider_model_invalid():
    with pytest.raises(ValueError):
        _split_provider_model("gpt-4o")


def test_brokered_lm_requires_chat_model():
    with pytest.raises(ValueError):
        BrokeredLM(model="openai/gpt-4o", model_type="completion", socket_path="sock")


def test_brokered_lm_missing_socket(monkeypatch):
    monkeypatch.setattr("tactus.broker.client.BrokerClient.from_environment", lambda: None)

    with pytest.raises(RuntimeError):
        BrokeredLM(model="openai/gpt-4o")


@pytest.mark.asyncio
async def test_brokered_lm_streaming(monkeypatch):
    stream = DummyStream()
    tool_calls = [
        {
            "id": "call-1",
            "type": "function",
            "function": {"name": "done", "arguments": "{}"},
        }
    ]

    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {"tool_calls": tool_calls}},
        ]
    )

    with dspy.settings.context(send_stream=stream, caller_predict=object()):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["finish_reason"] == "tool_calls"
    tool_calls_out = response.choices[0]["message"]["tool_calls"]
    assert len(tool_calls_out) == 1
    tool_call = tool_calls_out[0]
    assert getattr(tool_call, "id", tool_call.get("id")) == "call-1"
    assert stream.sent


@pytest.mark.asyncio
async def test_brokered_lm_streaming_error():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "error", "error": {"message": "boom"}}])

    with dspy.settings.context(send_stream=DummyStream()):
        with pytest.raises(RuntimeError, match="boom"):
            await lm.aforward(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_brokered_lm_streaming_error_without_message():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "error", "error": {}}])

    with dspy.settings.context(send_stream=DummyStream()):
        with pytest.raises(RuntimeError, match="Broker LLM error"):
            await lm.aforward(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming(monkeypatch):
    tool_calls = [
        {
            "id": "call-2",
            "type": "function",
            "function": {"name": "done", "arguments": "{}"},
        }
    ]
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {
                "event": "done",
                "data": {"text": "ok", "tool_calls": tool_calls, "usage": {"total_tokens": 5}},
            }
        ]
    )

    with dspy.settings.context(send_stream=None, caller_predict=None):
        response = await lm.aforward(prompt="hi")

    assert response.choices[0]["finish_reason"] == "tool_calls"
    assert response.choices[0]["message"]["content"] == "ok"
    assert response.usage["total_tokens"] == 5


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming_error():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "error", "error": {"message": "bad"}}])

    with dspy.settings.context(send_stream=None):
        with pytest.raises(RuntimeError, match="bad"):
            await lm.aforward(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming_error_without_message():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "error", "error": {}}])

    with dspy.settings.context(send_stream=None):
        with pytest.raises(RuntimeError, match="Broker LLM error"):
            await lm.aforward(messages=[{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming_without_tool_calls():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "done", "data": {"text": "ok"}}])

    with dspy.settings.context(send_stream=None):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["finish_reason"] == "stop"
    assert "tool_calls" not in response.choices[0]["message"]


@pytest.mark.asyncio
async def test_brokered_lm_builds_messages_from_prompt():
    client = CapturingClient([{"event": "done", "data": {"text": "ok"}}])
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = client

    with dspy.settings.context(send_stream=None):
        await lm.aforward(prompt="hello", max_tokens=None, max_completion_tokens=55)

    assert client.calls
    assert client.calls[0]["messages"] == [{"role": "user", "content": "hello"}]
    assert client.calls[0]["max_tokens"] == 55


@pytest.mark.asyncio
async def test_brokered_lm_non_openai(monkeypatch):
    lm = BrokeredLM(model="other/model", socket_path="sock")

    with dspy.settings.context(send_stream=None):
        with pytest.raises(ValueError):
            await lm.aforward(prompt="hi")


@pytest.mark.asyncio
async def test_brokered_lm_builds_empty_messages_when_no_prompt():
    client = CapturingClient([{"event": "done", "data": {"text": "ok"}}])
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = client

    with dspy.settings.context(send_stream=None):
        await lm.aforward(prompt=None, messages=None)

    assert client.calls
    assert client.calls[0]["messages"] == []


@pytest.mark.asyncio
async def test_brokered_lm_streaming_skips_empty_deltas():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": ""}},
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert stream.sent
    assert response.choices[0]["message"]["content"] == "Hi"


@pytest.mark.asyncio
async def test_brokered_lm_streaming_without_tool_calls():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["finish_reason"] == "stop"
    assert response.choices[0]["message"]["content"] == "Hi"


@pytest.mark.asyncio
async def test_brokered_lm_streaming_non_dict_choice(monkeypatch):
    class DummyMessage:
        def __init__(self, content):
            self.content = content

    class DummyChoice:
        def __init__(self, message):
            self.message = message

    class DummyResponse:
        def __init__(self, choices):
            self.choices = choices

    def fake_stream_chunk_builder(_chunks):
        return DummyResponse([DummyChoice(DummyMessage("Howdy"))])

    monkeypatch.setattr(
        "tactus.dspy.broker_lm.litellm.stream_chunk_builder", fake_stream_chunk_builder
    )

    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == "Howdy"


@pytest.mark.asyncio
async def test_brokered_lm_streaming_without_choices(monkeypatch):
    class DummyResponse:
        choices = []

    def fake_stream_chunk_builder(_chunks):
        return DummyResponse()

    monkeypatch.setattr(
        "tactus.dspy.broker_lm.litellm.stream_chunk_builder", fake_stream_chunk_builder
    )

    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == ""


@pytest.mark.asyncio
async def test_brokered_lm_streaming_missing_message(monkeypatch):
    class DummyChoice:
        def __init__(self):
            self.message = None

    class DummyResponse:
        def __init__(self):
            self.choices = [DummyChoice()]

    def fake_stream_chunk_builder(_chunks):
        return DummyResponse()

    monkeypatch.setattr(
        "tactus.dspy.broker_lm.litellm.stream_chunk_builder", fake_stream_chunk_builder
    )

    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "delta", "data": {"text": "Hi"}},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == ""


@pytest.mark.asyncio
async def test_brokered_lm_streaming_no_events():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([])

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == ""


@pytest.mark.asyncio
async def test_brokered_lm_streaming_exhausts_without_done():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "noop"}])

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == ""


@pytest.mark.asyncio
async def test_brokered_lm_streaming_handles_unknown_event():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient(
        [
            {"event": "noop"},
            {"event": "done", "data": {}},
        ]
    )

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_brokered_lm_streaming_done_without_chunks():
    stream = DummyStream()
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "done", "data": {}}])

    with dspy.settings.context(send_stream=stream):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["message"]["content"] == ""


@pytest.mark.asyncio
async def test_brokered_lm_non_streaming_without_done_event():
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    lm._client = DummyClient([{"event": "noop"}])

    with dspy.settings.context(send_stream=None):
        response = await lm.aforward(messages=[{"role": "user", "content": "hi"}])

    assert response.choices[0]["finish_reason"] == "stop"


def test_brokered_lm_forward_uses_syncify(monkeypatch):
    lm = BrokeredLM(model="openai/gpt-4o", socket_path="sock")
    captured = {}

    def fake_syncify(fn):
        def wrapper(**kwargs):
            captured["fn"] = fn
            captured["kwargs"] = kwargs
            return "ok"

        return wrapper

    monkeypatch.setattr("tactus.dspy.broker_lm.syncify", fake_syncify)

    result = lm.forward(prompt="hi", messages=[{"role": "user", "content": "x"}], temperature=0.1)

    assert result == "ok"
    assert captured["fn"].__self__ is lm
    assert captured["fn"].__func__ is lm.aforward.__func__
    assert captured["kwargs"]["prompt"] == "hi"
