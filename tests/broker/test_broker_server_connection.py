import json

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


def decode_message(buffer: bytes):
    length = int(buffer[:10].decode("ascii"))
    payload = buffer[11 : 11 + length]
    return json.loads(payload.decode("utf-8"))


@pytest.mark.asyncio
async def test_broker_server_connection_handles_unknown_method(monkeypatch, tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    writer = DummyWriter()

    async def fake_read_message(_reader):
        return {"id": "req", "method": "unknown", "params": {}}

    monkeypatch.setattr(broker_server, "read_message", fake_read_message)

    await server._handle_connection_asyncio(object(), writer)

    message = decode_message(writer.buffer)
    assert message["event"] == "error"
    assert message["error"]["type"] == "MethodNotFound"


@pytest.mark.asyncio
async def test_broker_server_connection_dispatches_events_emit(monkeypatch, tmp_path):
    server = broker_server.BrokerServer(tmp_path / "broker.sock")
    writer = DummyWriter()
    called = {}

    async def fake_read_message(_reader):
        return {"id": "req", "method": "events.emit", "params": {"event": {"ok": True}}}

    async def fake_handle(req_id, params, write_event):
        called["req_id"] = req_id
        await write_event({"id": req_id, "event": "done", "data": {"ok": True}})

    monkeypatch.setattr(broker_server, "read_message", fake_read_message)
    monkeypatch.setattr(server, "_handle_events_emit_asyncio", fake_handle)

    await server._handle_connection_asyncio(object(), writer)

    message = decode_message(writer.buffer)
    assert called["req_id"] == "req"
    assert message["event"] == "done"
