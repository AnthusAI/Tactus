import asyncio
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import anyio
import pytest

from tactus.broker import server as broker_server


class DummyAnyioStream:
    def __init__(self, fail_aclose=False):
        self.buffer = bytearray()
        self._fail_aclose = fail_aclose
        self.closed = False

    async def send(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def receive(self, _n: int) -> bytes:
        return b""

    async def aclose(self) -> None:
        self.closed = True
        if self._fail_aclose:
            raise RuntimeError("boom")


def decode_anyio_messages(buffer: bytes):
    messages = []
    idx = 0
    while idx < len(buffer):
        length = int(buffer[idx : idx + 10].decode("ascii"))
        idx += 11
        payload = buffer[idx : idx + length]
        idx += length
        messages.append(json.loads(payload.decode("utf-8")))
    return messages


class DummyWriter:
    def __init__(self, fail_close=False):
        self.buffer = bytearray()
        self._fail_close = fail_close

    def write(self, data: bytes) -> None:
        self.buffer.extend(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        if self._fail_close:
            raise RuntimeError("close failed")

    async def wait_closed(self) -> None:
        if self._fail_close:
            raise RuntimeError("wait failed")


def decode_asyncio_message(buffer: bytes):
    length = int(buffer[:10].decode("ascii"))
    payload = buffer[11 : 11 + length]
    return json.loads(payload.decode("utf-8"))


@pytest.mark.asyncio
async def test_openai_chat_backend_no_api_key_sets_no_env(monkeypatch):
    calls = []

    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(choices=[])

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    backend = broker_server.OpenAIChatBackend()
    await backend.chat(model="gpt-4o", messages=[], stream=False)

    assert os.environ.get("OPENAI_API_KEY") is None
    assert calls[0]["stream"] is False


@pytest.mark.asyncio
async def test_base_server_aclose_raises_on_unhandled_exception_group():
    server = broker_server._BaseBrokerServer()

    class DummyListener:
        async def aclose(self):
            return None

    async def raise_group():
        raise BaseExceptionGroup("group", [ValueError("boom")])

    server._listener = DummyListener()
    server._serve_task = asyncio.create_task(raise_group())

    with pytest.raises(BaseExceptionGroup):
        await server.aclose()


@pytest.mark.asyncio
async def test_handle_connection_wraps_tls(monkeypatch):
    server = broker_server._BaseBrokerServer()
    server.ssl_context = object()
    stream = DummyAnyioStream()
    wrapped = {}

    async def fake_wrap(byte_stream, ssl_context, server_side):
        wrapped["called"] = (byte_stream, ssl_context, server_side)
        return byte_stream

    async def fake_read(_buffered_stream):
        return {"id": "req", "method": "events.emit", "params": {"event": {"ok": True}}}

    monkeypatch.setattr(broker_server, "TLSStream", SimpleNamespace(wrap=fake_wrap))
    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)

    await server._handle_connection(stream)

    assert wrapped["called"][1] is server.ssl_context


@pytest.mark.asyncio
async def test_handle_connection_dispatches_control_and_tool(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyAnyioStream()
    called = {"control": 0, "tool": 0}

    async def fake_control(*_args, **_kwargs):
        called["control"] += 1

    async def fake_tool(*_args, **_kwargs):
        called["tool"] += 1

    async def fake_read(_buffered_stream):
        if called["control"] == 0:
            return {"id": "req", "method": "control.request", "params": {"request": {}}}
        return {"id": "req", "method": "tool.call", "params": {"name": "x", "args": {}}}

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)
    monkeypatch.setattr(server, "_handle_control_request", fake_control)
    monkeypatch.setattr(server, "_handle_tool_call", fake_tool)

    await server._handle_connection(stream)
    await server._handle_connection(stream)

    assert called["control"] == 1
    assert called["tool"] == 1


@pytest.mark.asyncio
async def test_handle_connection_handles_write_errors(monkeypatch):
    server = broker_server._BaseBrokerServer()
    stream = DummyAnyioStream(fail_aclose=True)

    async def fake_read(_buffered_stream):
        raise ValueError("boom")

    async def fake_write(*_args, **_kwargs):
        raise RuntimeError("write fail")

    monkeypatch.setattr(broker_server, "read_message_anyio", fake_read)
    monkeypatch.setattr(broker_server, "_write_event_anyio", fake_write)

    await server._handle_connection(stream)
    assert stream.closed is True


@pytest.mark.asyncio
async def test_handle_connection_asyncio_dispatches_methods(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()
    called = {"llm": 0, "tool": 0}

    async def fake_read(_reader):
        if called["llm"] == 0:
            return {"id": "req", "method": "llm.chat", "params": {}}
        return {"id": "req", "method": "tool.call", "params": {}}

    async def fake_llm(*_args, **_kwargs):
        called["llm"] += 1

    async def fake_tool(*_args, **_kwargs):
        called["tool"] += 1

    monkeypatch.setattr(broker_server, "read_message", fake_read)
    monkeypatch.setattr(server, "_handle_llm_chat_asyncio", fake_llm)
    monkeypatch.setattr(server, "_handle_tool_call_asyncio", fake_tool)

    await server._handle_connection_asyncio(object(), writer)
    await server._handle_connection_asyncio(object(), writer)

    assert called["llm"] == 1
    assert called["tool"] == 1


@pytest.mark.asyncio
async def test_handle_connection_asyncio_write_and_close_errors(monkeypatch):
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter(fail_close=True)

    async def fake_read(_reader):
        raise ValueError("boom")

    async def fake_write(_writer, _event):
        raise RuntimeError("write fail")

    monkeypatch.setattr(broker_server, "read_message", fake_read)
    monkeypatch.setattr(broker_server, "write_message", fake_write)

    await server._handle_connection_asyncio(object(), writer)


@pytest.mark.asyncio
async def test_events_emit_asyncio_handles_handler_exception():
    def boom(_event):
        raise ValueError("boom")

    server = broker_server._BaseBrokerServer(event_handler=boom)
    writer = DummyWriter()

    await server._handle_events_emit_asyncio("req", {"event": {"ok": True}}, writer)

    message = decode_asyncio_message(writer.buffer)
    assert message["event"] == "done"


@pytest.mark.asyncio
async def test_events_emit_asyncio_without_handler():
    server = broker_server._BaseBrokerServer(event_handler=None)
    writer = DummyWriter()

    await server._handle_events_emit_asyncio("req", {"event": {"ok": True}}, writer)

    message = decode_asyncio_message(writer.buffer)
    assert message["event"] == "done"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_streaming_handles_bad_chunk():
    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                yield SimpleNamespace(choices=[])

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    writer = DummyWriter()

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, writer
    )

    messages = decode_anyio_messages(writer.buffer)
    assert messages[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_non_streaming_tool_calls():
    class ToolCall:
        id = "t1"
        type = "function"
        function = SimpleNamespace(name="tool", arguments="{}")

    class DummyMessage:
        content = "hello"
        tool_calls = [ToolCall()]

    class DummyChoice:
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    writer = DummyWriter()

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, writer
    )

    message = decode_asyncio_message(writer.buffer)
    assert message["data"]["tool_calls"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_tool_call_asyncio_rejects_unallowlisted():
    server = broker_server._BaseBrokerServer()
    writer = DummyWriter()

    await server._handle_tool_call_asyncio("req", {"name": "host.missing", "args": {}}, writer)

    message = decode_asyncio_message(writer.buffer)
    assert message["error"]["type"] == "ToolNotAllowed"


@pytest.mark.asyncio
async def test_llm_chat_asyncio_non_streaming_handles_bad_response():
    class DummyResult:
        choices = []

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    writer = DummyWriter()

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, writer
    )

    message = decode_asyncio_message(writer.buffer)
    assert message["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_llm_chat_rejects_messages_not_list():
    server = broker_server._BaseBrokerServer()
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": "nope"}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_anyio_llm_chat_non_streaming_tool_calls():
    class ToolCall:
        id = "t1"
        type = "function"
        function = SimpleNamespace(name="tool", arguments="{}")

    class DummyMessage:
        content = "hello"
        tool_calls = [ToolCall()]

    class DummyChoice:
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["data"]["tool_calls"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_anyio_llm_chat_streaming_bad_chunk():
    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                yield SimpleNamespace(choices=[])

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_llm_chat_streaming_tool_call_without_function():
    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None
            self.function = None

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_llm_chat_streaming_tool_call_with_function():
    class DummyFunction:
        name = "tool"
        arguments = "{}"

    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = "t1"
            self.type = "function"
            self.function = DummyFunction()

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[-1]["event"] == "done"
    assert messages[-1]["data"]["tool_calls"][0]["function"]["name"] == "tool"


@pytest.mark.asyncio
async def test_anyio_llm_chat_streaming_tool_call_missing_name_and_args():
    class DummyFunction:
        name = None
        arguments = None

    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None
            self.function = DummyFunction()

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server._BaseBrokerServer(openai_backend=FakeBackend())
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_llm_chat_backend_error():
    async def fake_chat(self, **_kwargs):
        raise RuntimeError("boom")

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_anyio_llm_chat_non_streaming_handles_bad_response():
    class DummyResult:
        choices = []

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server._BaseBrokerServer()
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    stream = DummyAnyioStream()

    await server._handle_llm_chat(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, stream
    )

    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["event"] == "done"


@pytest.mark.asyncio
async def test_anyio_tool_call_rejects_bad_args_and_tool_exception():
    class BoomRegistry:
        def call(self, _name, _args):
            raise ValueError("boom")

    server = broker_server._BaseBrokerServer(tool_registry=BoomRegistry())
    stream = DummyAnyioStream()

    await server._handle_tool_call("req", {"name": "ok", "args": "nope"}, stream)
    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "BadRequest"

    stream = DummyAnyioStream()
    await server._handle_tool_call("req", {"name": "ok", "args": {}}, stream)
    messages = decode_anyio_messages(stream.buffer)
    assert messages[0]["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_broker_server_start_unlinks_existing_socket(monkeypatch):
    socket_path = Path("/tmp/broker_test.sock")
    socket_path.write_text("stub")

    class DummyServer:
        async def wait_closed(self):
            return None

        def close(self):
            return None

    async def fake_start_unix_server(*_args, **_kwargs):
        return DummyServer()

    monkeypatch.setattr(asyncio, "start_unix_server", fake_start_unix_server)

    server = broker_server.BrokerServer(socket_path)
    try:
        await server.start()
        assert not socket_path.exists()
    finally:
        await server.aclose()
        if socket_path.exists():
            socket_path.unlink()


@pytest.mark.asyncio
async def test_broker_server_aclose_logs_on_close_error(tmp_path):
    socket_path = tmp_path / "broker.sock"

    class DummyServer:
        def close(self) -> None:
            raise RuntimeError("boom")

        async def wait_closed(self) -> None:
            raise RuntimeError("boom")

    server = broker_server.BrokerServer(socket_path)
    server._server = DummyServer()

    await server.aclose()


@pytest.mark.asyncio
async def test_broker_server_aclose_recloses_server(monkeypatch, tmp_path):
    socket_path = tmp_path / "broker.sock"

    class DummyServer:
        def __init__(self):
            self.closed = False

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            return None

    async def fake_super_aclose(self):
        self._server = DummyServer()

    server = broker_server.BrokerServer(socket_path)
    monkeypatch.setattr(broker_server._BaseBrokerServer, "aclose", fake_super_aclose)

    await server.aclose()


@pytest.mark.asyncio
async def test_broker_server_aclose_handles_unlink_error(monkeypatch, tmp_path):
    socket_path = tmp_path / "broker.sock"
    socket_path.write_text("stub")

    original_unlink = Path.unlink

    def boom(self, *args, **kwargs):
        if self == socket_path:
            raise RuntimeError("unlink failed")
        return original_unlink(self, *args, **kwargs)

    server = broker_server.BrokerServer(socket_path)
    monkeypatch.setattr(Path, "unlink", boom)

    await server.aclose()


@pytest.mark.asyncio
async def test_broker_server_connection_handles_missing_id(monkeypatch, tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    writer = DummyWriter()

    async def fake_read_message(_reader):
        return {"id": "", "method": None, "params": {}}

    monkeypatch.setattr(broker_server, "read_message", fake_read_message)

    await server._handle_connection_asyncio(object(), writer)

    message = decode_asyncio_message(writer.buffer)
    assert message["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_broker_server_connection_dispatches_tool_call(monkeypatch, tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    writer = DummyWriter()
    called = {"tool": 0}

    async def fake_read_message(_reader):
        return {"id": "req", "method": "tool.call", "params": {"name": "host.ping", "args": {}}}

    async def fake_tool_call(*_args, **_kwargs):
        called["tool"] += 1

    monkeypatch.setattr(broker_server, "read_message", fake_read_message)
    monkeypatch.setattr(server, "_handle_tool_call_asyncio", fake_tool_call)

    await server._handle_connection_asyncio(object(), writer)

    assert called["tool"] == 1


@pytest.mark.asyncio
async def test_broker_server_connection_handles_errors(monkeypatch, tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    writer = DummyWriter(fail_close=True)

    async def fake_read_message(_reader):
        raise ValueError("boom")

    async def fake_write_message(_writer, _event):
        raise RuntimeError("write fail")

    monkeypatch.setattr(broker_server, "read_message", fake_read_message)
    monkeypatch.setattr(broker_server, "write_message", fake_write_message)

    await server._handle_connection_asyncio(object(), writer)


@pytest.mark.asyncio
async def test_broker_server_tool_call_asyncio_errors(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")

    errors = []

    async def write_event(event):
        errors.append(event)

    await server._handle_tool_call_asyncio("req", {"name": "", "args": {}}, write_event)
    await server._handle_tool_call_asyncio("req", {"name": "ok", "args": "nope"}, write_event)

    assert errors[0]["error"]["type"] == "BadRequest"
    assert errors[1]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_broker_server_tool_call_asyncio_unallowlisted(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_tool_call_asyncio("req", {"name": "missing", "args": {}}, write_event)
    assert events[0]["error"]["type"] == "ToolNotAllowed"


@pytest.mark.asyncio
async def test_broker_server_tool_call_asyncio_success(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_tool_call_asyncio("req", {"name": "host.ping", "args": {}}, write_event)

    assert events[-1]["event"] == "done"
    assert events[-1]["data"]["result"]["ok"] is True


@pytest.mark.asyncio
async def test_broker_server_tool_call_asyncio_exception(tmp_path):
    class BoomRegistry:
        def call(self, _name, _args):
            raise ValueError("boom")

    server = broker_server.BrokerServer(tmp_path / "broker.sock", tool_registry=BoomRegistry())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_tool_call_asyncio("req", {"name": "boom", "args": {}}, write_event)
    assert events[0]["error"]["type"] == "ValueError"


@pytest.mark.asyncio
async def test_broker_server_events_emit_asyncio_invalid_event(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_events_emit_asyncio("req", {"event": "nope"}, write_event)
    assert events[0]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_broker_server_events_emit_asyncio_without_handler(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_events_emit_asyncio("req", {"event": {"ok": True}}, write_event)
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_events_emit_asyncio_handler_exception(tmp_path):
    def boom(_event):
        raise RuntimeError("boom")

    server = broker_server.BrokerServer(tmp_path / "broker.sock", event_handler=boom)
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_events_emit_asyncio("req", {"event": {"ok": True}}, write_event)
    assert events[0]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_rejects_bad_inputs(tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio("req", {"provider": "other"}, write_event)
    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": None, "messages": []}, write_event
    )
    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": "nope"}, write_event
    )

    assert events[0]["error"]["type"] == "UnsupportedProvider"
    assert events[1]["error"]["type"] == "BadRequest"
    assert events[2]["error"]["type"] == "BadRequest"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_with_tools(tmp_path):
    class DummyDeltaCall:
        def __init__(self, index, tool_id=None, name=None, arguments=None):
            self.index = index
            self.id = tool_id
            self.type = "function"
            self.function = SimpleNamespace(name=name, arguments=arguments)

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(
                    content="hi",
                    tool_calls=[DummyDeltaCall(0, tool_id="t1", name="tool", arguments="{}")],
                )
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req",
        {
            "provider": "openai",
            "model": "gpt",
            "messages": [],
            "stream": True,
            "tools": [{"type": "function"}],
            "tool_choice": "auto",
            "temperature": 0.1,
            "max_tokens": 5,
        },
        write_event,
    )

    assert events[-1]["data"]["tool_calls"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_tool_call_missing_name_and_args(tmp_path):
    class DummyFunction:
        name = None
        arguments = None

    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None
            self.function = DummyFunction()

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_tool_call_missing_function_attr(tmp_path):
    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_bad_chunk(tmp_path):
    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                yield SimpleNamespace(choices=[])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_tool_call_without_function(tmp_path):
    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = None
            self.type = None
            self.function = None

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_streaming_tool_call_with_empty_function(tmp_path):
    class DummyDeltaCall:
        def __init__(self, index):
            self.index = index
            self.id = "t1"
            self.type = "function"
            self.function = ""

    class FakeBackend:
        async def chat(self, **_kwargs):
            async def gen():
                delta = SimpleNamespace(content=None, tool_calls=[DummyDeltaCall(0)])
                yield SimpleNamespace(choices=[SimpleNamespace(delta=delta)])

            return gen()

    server = broker_server.BrokerServer(tmp_path / "broker.sock", openai_backend=FakeBackend())
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": [], "stream": True}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_non_streaming_with_tools(tmp_path):
    calls = []

    class DummyMessage:
        content = "ok"
        tool_calls = []

    class DummyChoice:
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def fake_chat(self, **kwargs):
        calls.append(kwargs)
        return DummyResult()

    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req",
        {
            "provider": "openai",
            "model": "gpt",
            "messages": [],
            "tools": [{"type": "function"}],
            "tool_choice": "auto",
        },
        write_event,
    )

    assert calls[0]["tools"][0]["type"] == "function"
    assert calls[0]["tool_choice"] == "auto"
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_non_streaming_bad_response(tmp_path):
    class DummyResult:
        choices = []

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, write_event
    )

    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_non_streaming_tool_calls(tmp_path):
    class ToolCall:
        id = "t1"
        type = "function"
        function = SimpleNamespace(name="tool", arguments="{}")

    class DummyMessage:
        content = "hello"
        tool_calls = [ToolCall()]

    class DummyChoice:
        message = DummyMessage()

    class DummyResult:
        choices = [DummyChoice()]

    async def fake_chat(self, **_kwargs):
        return DummyResult()

    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req",
        {"provider": "openai", "model": "gpt", "messages": [], "stream": False},
        write_event,
    )

    assert events[-1]["data"]["tool_calls"][0]["id"] == "t1"


@pytest.mark.asyncio
async def test_broker_server_llm_chat_asyncio_error(tmp_path):
    async def fake_chat(self, **_kwargs):
        raise RuntimeError("boom")

    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    server._openai = type("FakeOpenAI", (), {"chat": fake_chat})()
    events = []

    async def write_event(event):
        events.append(event)

    await server._handle_llm_chat_asyncio(
        "req", {"provider": "openai", "model": "gpt", "messages": []}, write_event
    )

    assert events[0]["error"]["type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_tcp_broker_server_bound_port_failure(monkeypatch):
    class DummyListener:
        def extra(self, _attr):
            raise RuntimeError("boom")

        async def aclose(self):
            return None

        async def serve(self, _handler):
            return None

    async def fake_create_tcp_listener(*_args, **_kwargs):
        return DummyListener()

    monkeypatch.setattr(anyio, "create_tcp_listener", fake_create_tcp_listener)

    server = broker_server.TcpBrokerServer(host="127.0.0.1", port=0)
    await server.start()
    assert server.bound_port is None
    await server.aclose()


@pytest.mark.asyncio
async def test_tcp_broker_server_start_does_not_spawn_new_task(monkeypatch):
    class DummyListener:
        def extra(self, _attr):
            class DummySocket:
                def getsockname(self):
                    return ("127.0.0.1", 1234)

            return DummySocket()

        async def aclose(self):
            return None

        async def serve(self, _handler):
            return None

    async def fake_create_tcp_listener(*_args, **_kwargs):
        return DummyListener()

    monkeypatch.setattr(anyio, "create_tcp_listener", fake_create_tcp_listener)

    server = broker_server.TcpBrokerServer(host="127.0.0.1", port=0)
    server._serve_task = asyncio.create_task(asyncio.sleep(0.1))

    await server.start()
    await server.aclose()
