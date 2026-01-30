import asyncio
import json

import pytest

from tactus.broker import server as broker_server


class DummyByteStream:
    def __init__(self):
        self.buffer = bytearray()
        self.closed = False

    async def send(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def receive(self, _n: int) -> bytes:
        return b""

    async def aclose(self) -> None:
        self.closed = True


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
async def test_control_request_rejects_invalid_payload():
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    await server._handle_control_request("req", {"request": "nope"}, stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_control_request_requires_handler():
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    await server._handle_control_request("req", {"request": {"ok": True}}, stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "NoControlHandler"


@pytest.mark.asyncio
async def test_control_request_success_delivers_response():
    async def handler(request):
        return {"echo": request}

    server = broker_server._BaseBrokerServer(control_handler=handler)
    stream = DummyByteStream()

    await server._handle_control_request("req", {"request": {"x": 1}}, stream)

    messages = decode_messages(stream.buffer)
    assert [msg["event"] for msg in messages] == ["delivered", "response"]
    assert messages[1]["data"]["echo"]["x"] == 1


@pytest.mark.asyncio
async def test_control_request_timeout_event():
    async def handler(_request):
        raise asyncio.TimeoutError

    server = broker_server._BaseBrokerServer(control_handler=handler)
    stream = DummyByteStream()

    await server._handle_control_request("req", {"request": {"x": 1}}, stream)

    messages = decode_messages(stream.buffer)
    assert [msg["event"] for msg in messages] == ["delivered", "timeout"]
    assert messages[1]["data"]["timed_out"] is True


@pytest.mark.asyncio
async def test_control_request_exception_surfaces_error():
    async def handler(_request):
        raise ValueError("boom")

    server = broker_server._BaseBrokerServer(control_handler=handler)
    stream = DummyByteStream()

    await server._handle_control_request("req", {"request": {"x": 1}}, stream)

    messages = decode_messages(stream.buffer)
    assert [msg["event"] for msg in messages] == ["delivered", "error"]
    assert messages[1]["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_anyio_tool_call_rejects_unallowed_tool():
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    await server._handle_tool_call("req", {"name": "host.missing", "args": {}}, stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "ToolNotAllowed"


@pytest.mark.asyncio
async def test_anyio_llm_chat_rejects_provider():
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    await server._handle_llm_chat(
        "req", {"provider": "other", "model": "gpt", "messages": []}, stream
    )

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "UnsupportedProvider"


@pytest.mark.asyncio
async def test_anyio_llm_chat_success():
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
    stream = DummyByteStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, stream
    )

    messages = decode_messages(stream.buffer)
    assert messages[0]["event"] == "done"
    assert messages[0]["data"]["text"] == "hello"


@pytest.mark.asyncio
async def test_anyio_events_emit_ignores_handler_exception():
    def boom(_event):
        raise ValueError("boom")

    server = broker_server._BaseBrokerServer(event_handler=boom)
    stream = DummyByteStream()

    await server._handle_events_emit("req", {"event": {"ok": True}}, stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_llm_chat_streaming_with_tool_calls():
    class DummyDeltaCall:
        def __init__(self, index, tool_id=None, tool_type=None, name=None, arguments=None):
            self.index = index
            self.id = tool_id
            self.type = tool_type
            self.function = type("Func", (), {"name": name, "arguments": arguments})()

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta_1 = type(
                    "Delta",
                    (),
                    {
                        "content": "hi",
                        "tool_calls": [
                            DummyDeltaCall(0, tool_id="t1", tool_type="function", name="tool")
                        ],
                    },
                )()
                delta_2 = type(
                    "Delta",
                    (),
                    {"content": "!", "tool_calls": [DummyDeltaCall(0, arguments='{"x":1}')]},
                )()
                for delta in [delta_1, delta_2]:
                    yield type("Chunk", (), {"choices": [type("Choice", (), {"delta": delta})()]})()

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    stream = DummyByteStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, stream
    )

    messages = decode_messages(stream.buffer)
    assert messages[-1]["event"] == "done"
    assert messages[-1]["data"]["text"] == "hi!"
    assert messages[-1]["data"]["tool_calls"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_handle_connection_rejects_missing_id_or_method(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    async def fake_read(_buffered_stream):
        return {"id": "", "method": None, "params": {}}

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)

    await server._handle_connection(stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"
    assert stream.closed is True


@pytest.mark.asyncio
async def test_handle_connection_rejects_unknown_method(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    async def fake_read(_buffered_stream):
        return {"id": "req", "method": "unknown", "params": {}}

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)

    await server._handle_connection(stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "MethodNotFound"


@pytest.mark.asyncio
async def test_handle_connection_dispatches_events_emit(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    async def fake_read(_buffered_stream):
        return {"id": "req", "method": "events.emit", "params": {"event": {"ok": True}}}

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)

    await server._handle_connection(stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["event"] == "done"


@pytest.mark.asyncio
async def test_handle_connection_emits_error_on_exception(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyByteStream()

    async def fake_read(_buffered_stream):
        raise ValueError("boom")

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)

    await server._handle_connection(stream)

    messages = decode_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_broker_server_start_rejects_long_socket_path(tmp_path):
    long_path = tmp_path / ("a" * 100)
    server = broker_server.BrokerServer(long_path)

    with pytest.raises(ValueError):
        await server.start()


@pytest.mark.asyncio
async def test_broker_server_aclose_unlinks_socket(tmp_path):
    socket_path = tmp_path / "broker.sock"
    socket_path.write_text("stub")

    class DummyServer:
        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    server = broker_server.BrokerServer(socket_path)
    server._server = DummyServer()

    await server.aclose()

    assert not socket_path.exists()


@pytest.mark.asyncio
async def test_tcp_broker_server_sets_bound_port():
    server = broker_server.TcpBrokerServer(host="127.0.0.1", port=0)

    await server.start()

    try:
        assert server.bound_port is not None
    finally:
        await server.aclose()
