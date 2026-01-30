import asyncio
from datetime import datetime, timezone

import pytest

from tactus.adapters.channels.ipc import IPCControlChannel
from tactus.protocols.control import (
    ControlOption,
    ControlRequest,
    ControlRequestType,
    ControlResponse,
)


class DummyWriter:
    def __init__(self):
        self.closed = False
        self.waited = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


@pytest.mark.asyncio
async def test_initialize_sets_up_server(monkeypatch, tmp_path):
    socket_path = tmp_path / "control.sock"

    async def fake_start_unix_server(handler, path=None):
        assert path == str(socket_path)
        return DummyServer(handler)

    class DummyServer:
        def __init__(self, handler):
            self.handler = handler
            self.closed = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

    monkeypatch.setattr(asyncio, "start_unix_server", fake_start_unix_server)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.path.exists", lambda *_: False)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.makedirs", lambda *_args, **_kw: None)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.chmod", lambda *_args, **_kw: None)

    channel = IPCControlChannel(socket_path=str(socket_path), procedure_id="proc")
    await channel.initialize()

    assert channel._initialized is True
    assert channel._server is not None


@pytest.mark.asyncio
async def test_initialize_noop_when_already_initialized(monkeypatch, tmp_path):
    socket_path = tmp_path / "control.sock"
    channel = IPCControlChannel(socket_path=str(socket_path), procedure_id="proc")
    channel._initialized = True

    async def fake_start_unix_server(*_args, **_kwargs):
        raise AssertionError("start_unix_server should not be called")

    monkeypatch.setattr(asyncio, "start_unix_server", fake_start_unix_server)
    await channel.initialize()


@pytest.mark.asyncio
async def test_initialize_removes_existing_socket(monkeypatch, tmp_path):
    socket_path = tmp_path / "control.sock"
    removed = []

    async def fake_start_unix_server(handler, path=None):
        return DummyServer(handler)

    class DummyServer:
        def __init__(self, handler):
            self.handler = handler

        def close(self):
            return None

        async def wait_closed(self):
            return None

    monkeypatch.setattr(asyncio, "start_unix_server", fake_start_unix_server)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.path.exists", lambda *_: True)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.unlink", lambda path: removed.append(path))
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.makedirs", lambda *_args, **_kw: None)
    monkeypatch.setattr("tactus.adapters.channels.ipc.os.chmod", lambda *_args, **_kw: None)

    channel = IPCControlChannel(socket_path=str(socket_path), procedure_id="proc")
    await channel.initialize()

    assert removed == [str(socket_path)]


@pytest.mark.asyncio
async def test_send_returns_failure_when_no_clients():
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    request = ControlRequest(
        request_id="req-1",
        procedure_id="proc",
        procedure_name="Proc",
        invocation_id="inv-1",
        request_type=ControlRequestType.INPUT,
        message="Provide input",
        started_at=datetime.now(timezone.utc),
        options=[ControlOption(label="ok", value="ok")],
    )

    result = await channel.send(request)

    assert result.success is False
    assert result.error_message == "No clients connected"


def test_capabilities_defaults():
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    caps = channel.capabilities
    assert caps.supports_input is True
    assert caps.is_synchronous is True


@pytest.mark.asyncio
async def test_send_removes_dead_clients(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    alive = DummyWriter()
    dead = DummyWriter()
    channel._clients = {"alive": alive, "dead": dead}

    async def fake_write_message(writer, _data):
        if writer is dead:
            raise RuntimeError("write failed")

    monkeypatch.setattr("tactus.adapters.channels.ipc.write_message", fake_write_message)

    request = ControlRequest(
        request_id="req-2",
        procedure_id="proc",
        procedure_name="Proc",
        invocation_id="inv-2",
        request_type=ControlRequestType.INPUT,
        message="Provide input",
        started_at=datetime.now(timezone.utc),
    )

    result = await channel.send(request)

    assert result.success is True
    assert "dead" not in channel._clients
    assert "alive" in channel._clients


@pytest.mark.asyncio
async def test_cancel_sends_cancel_message(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()
    channel._clients = {"client": writer}

    sent = []

    async def fake_write_message(_writer, data):
        sent.append(data)

    monkeypatch.setattr("tactus.adapters.channels.ipc.write_message", fake_write_message)

    await channel.cancel("req-3", "no longer needed")

    assert sent == [
        {"type": "control.cancelled", "request_id": "req-3", "reason": "no longer needed"}
    ]


@pytest.mark.asyncio
async def test_cancel_logs_error_when_write_fails(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    channel._clients = {"client": DummyWriter()}

    async def fake_write_message(_writer, _data):
        raise RuntimeError("write failed")

    monkeypatch.setattr("tactus.adapters.channels.ipc.write_message", fake_write_message)
    await channel.cancel("req-3", "no longer needed")


@pytest.mark.asyncio
async def test_receive_yields_response():
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    response_task = asyncio.create_task(channel.receive().__anext__())
    await channel._response_queue.put(
        ControlResponse(
            request_id="req-1",
            value="ok",
        )
    )
    response = await response_task
    assert response.request_id == "req-1"


@pytest.mark.asyncio
async def test_handle_client_accepts_responses(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()

    messages = [
        {
            "type": "control.response",
            "request_id": "req-4",
            "value": "ok",
            "responded_at": datetime.now(timezone.utc).isoformat(),
        },
        {"type": "control.list"},
    ]

    async def fake_read_message(_reader):
        if messages:
            return messages.pop(0)
        raise EOFError()

    sent = []

    async def fake_write_message(_writer, data):
        sent.append(data)

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)
    monkeypatch.setattr("tactus.adapters.channels.ipc.write_message", fake_write_message)

    await channel._handle_client(asyncio.StreamReader(), writer)

    response = channel._response_queue.get_nowait()
    assert response.request_id == "req-4"
    assert sent == [{"type": "control.list_response", "requests": []}]


@pytest.mark.asyncio
async def test_handle_client_unknown_message(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()

    messages = [{"type": "control.unknown"}]

    async def fake_read_message(_reader):
        if messages:
            return messages.pop(0)
        raise EOFError()

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)

    await channel._handle_client(asyncio.StreamReader(), writer)

    assert writer.closed is True
    assert writer.waited is True


@pytest.mark.asyncio
async def test_handle_client_pending_request_write_error(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()
    channel._pending_requests = {"req-1": {"type": "control.request", "request_id": "req-1"}}

    async def fake_read_message(_reader):
        raise EOFError()

    async def fake_write_message(_writer, _data):
        raise RuntimeError("write failed")

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)
    monkeypatch.setattr("tactus.adapters.channels.ipc.write_message", fake_write_message)

    await channel._handle_client(asyncio.StreamReader(), writer)


@pytest.mark.asyncio
async def test_handle_client_incomplete_read(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()

    async def fake_read_message(_reader):
        raise asyncio.IncompleteReadError(partial=b"", expected=1)

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)

    await channel._handle_client(asyncio.StreamReader(), writer)


@pytest.mark.asyncio
async def test_handle_client_logs_exception(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()

    async def fake_read_message(_reader):
        raise RuntimeError("boom")

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)

    await channel._handle_client(asyncio.StreamReader(), writer)


@pytest.mark.asyncio
async def test_handle_client_finally_close_error(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")

    class ErrorWriter(DummyWriter):
        def close(self):
            raise RuntimeError("close failed")

    writer = ErrorWriter()

    async def fake_read_message(_reader):
        raise EOFError()

    monkeypatch.setattr("tactus.adapters.channels.ipc.read_message", fake_read_message)

    await channel._handle_client(asyncio.StreamReader(), writer)


@pytest.mark.asyncio
async def test_shutdown_removes_socket_and_ignores_unlink_error(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")

    monkeypatch.setattr("tactus.adapters.channels.ipc.os.path.exists", lambda *_: True)
    monkeypatch.setattr(
        "tactus.adapters.channels.ipc.os.unlink",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("unlink failed")),
    )

    await channel.shutdown()


@pytest.mark.asyncio
async def test_shutdown_handles_writer_errors():
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")

    class ErrorWriter(DummyWriter):
        async def wait_closed(self):
            raise RuntimeError("close failed")

    channel._clients = {"client": ErrorWriter()}
    await channel.shutdown()


@pytest.mark.asyncio
async def test_shutdown_closes_clients_and_server(monkeypatch):
    channel = IPCControlChannel(socket_path="/tmp/unused.sock", procedure_id="proc")
    writer = DummyWriter()
    channel._clients = {"client": writer}

    class DummyServer:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            return None

    server = DummyServer()
    channel._server = server

    monkeypatch.setattr("tactus.adapters.channels.ipc.os.path.exists", lambda *_: False)

    await channel.shutdown()

    assert writer.closed is True
    assert writer.waited is True
    assert server.closed is True
    assert channel._clients == {}
