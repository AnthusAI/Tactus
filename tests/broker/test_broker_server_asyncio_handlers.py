import json
from types import SimpleNamespace

import pytest

from tactus.broker import server as broker_server


class DummyWriter:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


def decode_messages(buffer: bytes):
    messages = []
    idx = 0
    while idx < len(buffer):
        length = int(buffer[idx : idx + 10].decode("ascii"))
        idx += 11
        payload = buffer[idx : idx + length]
        idx += length
        messages.append(json.loads(payload.decode("utf-8")))
    return messages


@pytest.mark.asyncio
async def test_events_emit_asyncio_invalid_event():
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    await server._handle_events_emit_asyncio("req", {"event": "nope"}, writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["event"] == "error"
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_events_emit_asyncio_success_calls_handler():
    received = []

    server = broker_server._BaseBrokerServer(event_handler=lambda event: received.append(event))
    writer = DummyWriter()

    await server._handle_events_emit_asyncio("req", {"event": {"ok": True}}, writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["event"] == "done"
    assert received == [{"ok": True}]


@pytest.mark.asyncio
async def test_tool_call_asyncio_rejects_bad_inputs():
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    await server._handle_tool_call_asyncio("req", {"name": "", "args": {}}, writer)
    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"

    writer = DummyWriter()
    await server._handle_tool_call_asyncio("req", {"name": "ok", "args": "nope"}, writer)
    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_tool_call_asyncio_allows_allowlisted():
    registry = broker_server.HostToolRegistry({"host.echo": lambda args: {"ok": args}})
    server = broker_server._BaseBrokerServer(tool_registry=registry)
    writer = DummyWriter()

    await server._handle_tool_call_asyncio("req", {"name": "host.echo", "args": {"x": 1}}, writer)
    messages = decode_messages(writer.buffer)
    assert messages[0]["event"] == "done"
    assert messages[0]["data"]["result"]["ok"]["x"] == 1


@pytest.mark.asyncio
async def test_tool_call_asyncio_handles_tool_exception():
    def boom(_args):
        raise ValueError("boom")

    registry = broker_server.HostToolRegistry({"host.fail": boom})
    server = broker_server._BaseBrokerServer(tool_registry=registry)
    writer = DummyWriter()

    await server._handle_tool_call_asyncio("req", {"name": "host.fail", "args": {}}, writer)
    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_rejects_provider_and_model():
    server = broker_server._BaseBrokerServer()

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio(
        "req", {"provider": "other", "model": "m", "messages": []}, writer
    )
    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "UnsupportedProvider"

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio("req", {"provider": "openai"}, writer)
    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_rejects_messages_not_list():
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": "nope"}, writer
    )

    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_success():
    class DummyMessage:
        content = "hello"
        tool_calls = []

    class DummyChoice:
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def fake_chat(self, **kwargs):
        return DummyResult()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, writer
    )
    messages = decode_messages(writer.buffer)
    assert messages[0]["event"] == "done"
    assert messages[0]["data"]["text"] == "hello"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_streaming_with_tool_calls():
    class DummyDeltaCall:
        def __init__(self, index, tool_id=None, tool_type=None, name=None, arguments=None):
            self.index = index
            self.id = tool_id
            self.type = tool_type
            self.function = SimpleNamespace(name=name, arguments=arguments)

    async def fake_chat(self, **_kwargs):
        async def gen():
            delta_1 = SimpleNamespace(
                content="hi",
                tool_calls=[DummyDeltaCall(0, tool_id="t1", tool_type="function", name="tool")],
            )
            delta_2 = SimpleNamespace(
                content="!",
                tool_calls=[DummyDeltaCall(0, arguments='{"x":1}')],
            )
            for delta in [delta_1, delta_2]:
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

        return gen()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio(
        "req",
        {"provider": "openai", "model": "gpt", "messages": [], "stream": True},
        writer,
    )

    messages = decode_messages(writer.buffer)
    assert messages[-1]["event"] == "done"
    assert messages[-1]["data"]["text"] == "hi!"
    assert messages[-1]["data"]["tool_calls"][0]["id"] == "t1"
    assert messages[-1]["data"]["tool_calls"][0]["function"]["arguments"] == '{"x":1}'


@pytest.mark.asyncio
async def test_llm_chat_asyncio_streaming_tool_call_without_function():
    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None
            self.function = None

    async def fake_chat(self, **_kwargs):
        async def gen():
            delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
            yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

        return gen()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio(
        "req",
        {"provider": "openai", "model": "gpt", "messages": [], "stream": True},
        writer,
    )

    messages = decode_messages(writer.buffer)
    assert messages[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_handles_backend_error():
    async def fake_chat(self, **_kwargs):
        raise RuntimeError("boom")

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()

    writer = DummyWriter()
    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, writer
    )

    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_base_handle_connection_asyncio_dispatches_and_handles_errors(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    async def fake_read(_reader):
        return {"id": "req", "method": "events.emit", "params": {"event": {"ok": True}}}

    monkeypatch.setattr(broker_server, "read_message", fake_read)

    await server._handle_connection_asyncio(object(), writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["event"] == "done"
    assert writer.closed is True


@pytest.mark.asyncio
async def test_base_handle_connection_asyncio_rejects_unknown_method(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    async def fake_read(_reader):
        return {"id": "req", "method": "unknown", "params": {}}

    monkeypatch.setattr(broker_server, "read_message", fake_read)

    await server._handle_connection_asyncio(object(), writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "MethodNotFound"


@pytest.mark.asyncio
async def test_base_handle_connection_asyncio_missing_id(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    async def fake_read(_reader):
        return {"id": "", "method": None, "params": {}}

    monkeypatch.setattr(broker_server, "read_message", fake_read)

    await server._handle_connection_asyncio(object(), writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_base_handle_connection_asyncio_emits_error_on_exception(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    async def fake_read(_reader):
        raise ValueError("boom")

    monkeypatch.setattr(broker_server, "read_message", fake_read)

    await server._handle_connection_asyncio(object(), writer)

    messages = decode_messages(writer.buffer)
    assert messages[0]["error"]["type"] == "ValueError"
