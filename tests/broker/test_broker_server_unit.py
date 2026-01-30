import asyncio
import os
import sys
from types import SimpleNamespace

import anyio
import pytest

from tactus.broker.server import (
    HostToolRegistry,
    OpenAIChatBackend,
    OpenAIChatConfig,
    _BaseBrokerServer,
    _flatten_exceptions,
)


class FakeByteStream:
    def __init__(self):
        self.sent: list[bytes] = []

    async def send(self, data: bytes) -> None:
        self.sent.append(data)

    async def aclose(self) -> None:
        return None


def _decode_messages(chunks: list[bytes]) -> list[dict]:
    data = b"".join(chunks)
    messages = []
    idx = 0
    while idx < len(data):
        length = int(data[idx : idx + 10].decode("ascii"))
        idx += 11  # 10 digits + newline
        payload = data[idx : idx + length]
        idx += length
        messages.append(__import__("json").loads(payload.decode("utf-8")))
    return messages


def test_flatten_exceptions():
    exc = BaseExceptionGroup("group", [ValueError("a"), TypeError("b")])
    leaves = _flatten_exceptions(exc)
    assert len(leaves) == 2
    assert any(isinstance(e, ValueError) for e in leaves)


def test_host_tool_registry_default():
    registry = HostToolRegistry.default()
    assert registry.call("host.ping", {"ok": True})["ok"] is True
    assert registry.call("host.echo", {"x": 1})["echo"] == {"x": 1}


def test_openai_chat_backend_get_client_returns_none():
    backend = OpenAIChatBackend()
    assert backend._get_client() is None


@pytest.mark.asyncio
async def test_openai_chat_backend_sets_env_and_includes_optional_kwargs(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content="ok", tool_calls=[SimpleNamespace(id="t")])
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=message)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))
    monkeypatch.delenv("OPENAI_KEY", raising=False)

    backend = OpenAIChatBackend(OpenAIChatConfig(api_key_env="OPENAI_KEY"), api_key="secret")
    result = await backend.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.2,
        max_tokens=5,
        stream=False,
        tools=[{"type": "function", "function": {"name": "tool", "parameters": {}}}],
        tool_choice="auto",
    )

    assert os.environ["OPENAI_KEY"] == "secret"
    assert result.choices[0].finish_reason == "stop"
    assert calls[0]["temperature"] == 0.2
    assert calls[0]["max_tokens"] == 5
    assert calls[0]["tools"][0]["function"]["name"] == "tool"
    assert calls[0]["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_openai_chat_backend_streaming_and_no_tool_calls(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content="ok", tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=message)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))

    backend = OpenAIChatBackend()
    result = await backend.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    )

    assert result.choices[0].message.content == "ok"
    assert calls[0]["stream"] is True


@pytest.mark.asyncio
async def test_openai_chat_backend_non_streaming_without_tool_calls(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        message = SimpleNamespace(content="ok", tool_calls=[])
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason="stop", message=message)])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))

    backend = OpenAIChatBackend()
    result = await backend.chat(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
    )

    assert result.choices[0].message.content == "ok"
    assert calls[0]["stream"] is False


@pytest.mark.asyncio
async def test_base_server_serve_requires_start():
    server = _BaseBrokerServer()
    with pytest.raises(RuntimeError):
        await server.serve()


@pytest.mark.asyncio
async def test_base_server_aclose_handles_closed_resource_group():
    server = _BaseBrokerServer()

    class DummyListener:
        async def aclose(self):
            return None

    async def raise_group():
        raise BaseExceptionGroup("group", [anyio.ClosedResourceError()])

    server._listener = DummyListener()
    server._serve_task = asyncio.create_task(raise_group())

    await server.aclose()


@pytest.mark.asyncio
async def test_base_server_aclose_handles_cancelled_task():
    server = _BaseBrokerServer()

    class DummyListener:
        async def aclose(self):
            return None

    async def raise_cancelled():
        raise asyncio.CancelledError

    server._listener = DummyListener()
    server._serve_task = asyncio.create_task(raise_cancelled())

    await server.aclose()


@pytest.mark.asyncio
async def test_handle_tool_call_invalid_name():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_tool_call("req", {"name": "", "args": {}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["event"] == "error"
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_handle_tool_call_unallowlisted():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_tool_call("req", {"name": "missing", "args": {}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["error"]["type"] == "ToolNotAllowed"


@pytest.mark.asyncio
async def test_handle_events_emit_invalid():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_events_emit("req", {"event": "bad"}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_handle_control_request_no_handler():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_control_request("req", {"request": {}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["error"]["type"] == "NoControlHandler"


@pytest.mark.asyncio
async def test_handle_control_request_success():
    async def handler(payload):
        return {"ok": True, "payload": payload}

    server = _BaseBrokerServer(control_handler=handler)
    stream = FakeByteStream()

    await server._handle_control_request("req", {"request": {"id": "x"}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["event"] == "delivered"
    assert messages[1]["event"] == "response"
    assert messages[1]["data"]["ok"] is True


@pytest.mark.asyncio
async def test_handle_llm_chat_invalid_provider_and_model():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_llm_chat("req", {"provider": "other"}, stream)
    messages = _decode_messages(stream.sent)
    assert messages[0]["error"]["type"] == "UnsupportedProvider"

    stream = FakeByteStream()
    await server._handle_llm_chat("req", {"provider": "openai", "model": 123}, stream)
    messages = _decode_messages(stream.sent)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_handle_tool_call_success():
    server = _BaseBrokerServer()
    stream = FakeByteStream()

    await server._handle_tool_call("req", {"name": "host.echo", "args": {"x": 1}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["event"] == "done"
    assert messages[0]["data"]["result"]["echo"]["x"] == 1


@pytest.mark.asyncio
async def test_handle_control_request_timeout():
    async def handler(payload):
        raise asyncio.TimeoutError()

    server = _BaseBrokerServer(control_handler=handler)
    stream = FakeByteStream()

    await server._handle_control_request("req", {"request": {"id": "x"}}, stream)

    messages = _decode_messages(stream.sent)
    assert messages[0]["event"] == "delivered"
    assert messages[1]["event"] == "timeout"


@pytest.mark.asyncio
async def test_handle_llm_chat_success_with_tool_calls():
    class FakeBackend:
        async def chat(self, **kwargs):
            message = SimpleNamespace(
                content="hello",
                tool_calls=[
                    SimpleNamespace(
                        id="tool-1",
                        type="function",
                        function=SimpleNamespace(name="tool", arguments="{}"),
                    )
                ],
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    server = _BaseBrokerServer(openai_backend=FakeBackend())
    stream = FakeByteStream()

    await server._handle_llm_chat(
        "req",
        {"provider": "openai", "model": "gpt-4o", "messages": [], "stream": False},
        stream,
    )

    messages = _decode_messages(stream.sent)
    assert messages[0]["event"] == "done"
    assert messages[0]["data"]["tool_calls"][0]["id"] == "tool-1"


@pytest.mark.asyncio
async def test_handle_llm_chat_streaming_chunks():
    class FakeBackend:
        async def chat(self, **kwargs):
            async def gen():
                for token in ["a", "b"]:
                    yield SimpleNamespace(
                        choices=[SimpleNamespace(delta=SimpleNamespace(content=token))]
                    )

            return gen()

    server = _BaseBrokerServer(openai_backend=FakeBackend())
    stream = FakeByteStream()

    await server._handle_llm_chat(
        "req",
        {"provider": "openai", "model": "gpt-4o", "messages": [], "stream": True},
        stream,
    )

    messages = _decode_messages(stream.sent)
    assert messages[-1]["event"] == "done"
    assert messages[-1]["data"]["text"] == "ab"
