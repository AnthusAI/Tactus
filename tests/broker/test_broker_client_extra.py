import asyncio

import pytest

from tactus.broker import client as broker_client
from tactus.broker.stdio import STDIO_TRANSPORT_VALUE


class DummyWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.mark.asyncio
async def test_request_stdio_filters_events(monkeypatch):
    client = broker_client.BrokerClient(STDIO_TRANSPORT_VALUE)

    async def fake_request(self, req_id, method, params):
        yield {"id": "other", "event": "chunk"}
        yield {"id": req_id, "event": "done", "data": {"ok": True}}

    monkeypatch.setattr(
        broker_client, "_STDIO_TRANSPORT", type("T", (), {"request": fake_request})()
    )
    monkeypatch.setattr(broker_client.uuid, "uuid4", lambda: type("U", (), {"hex": "req"})())

    events = []
    async for event in client._request("llm.chat", {"k": "v"}):
        events.append(event)

    assert events == [{"id": "req", "event": "done", "data": {"ok": True}}]


@pytest.mark.asyncio
async def test_request_tcp_invalid_endpoint():
    client = broker_client.BrokerClient("tcp://localhost")

    with pytest.raises(ValueError):
        async for _ in client._request("llm.chat", {}):
            pass


@pytest.mark.asyncio
async def test_request_tcp_invalid_port():
    client = broker_client.BrokerClient("tcp://localhost:notaport")

    with pytest.raises(ValueError):
        async for _ in client._request("llm.chat", {}):
            pass


@pytest.mark.asyncio
async def test_request_tcp_tls(monkeypatch, tmp_path):
    cafile = tmp_path / "ca.pem"
    cafile.write_text("ca")
    monkeypatch.setenv("TACTUS_BROKER_TLS_CA_FILE", str(cafile))
    monkeypatch.setenv("TACTUS_BROKER_TLS_INSECURE", "1")

    client = broker_client.BrokerClient("tls://localhost:1234")
    monkeypatch.setattr(broker_client.uuid, "uuid4", lambda: type("U", (), {"hex": "req"})())

    reader = object()
    writer = DummyWriter()

    class DummySSL:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = None

        def load_verify_locations(self, cafile=None):
            return None

    monkeypatch.setattr(broker_client.ssl, "create_default_context", lambda: DummySSL())

    async def open_connection(host, port, ssl=None):
        assert host == "localhost"
        assert port == 1234
        assert ssl is not None
        return reader, writer

    async def read_message(_reader):
        return {"id": "req", "event": "done"}

    async def write_message(_writer, _payload):
        return None

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    monkeypatch.setattr(broker_client, "read_message", read_message)
    monkeypatch.setattr(broker_client, "write_message", write_message)

    events = []
    async for event in client._request("llm.chat", {"k": "v"}):
        events.append(event)

    assert events[-1]["event"] == "done"
    assert writer.closed is True


@pytest.mark.asyncio
async def test_request_unix_socket_filters(monkeypatch):
    client = broker_client.BrokerClient("/tmp/broker.sock")
    monkeypatch.setattr(broker_client.uuid, "uuid4", lambda: type("U", (), {"hex": "req"})())

    reader = object()
    writer = DummyWriter()

    async def open_connection(_path):
        return reader, writer

    messages = [
        {"id": "other", "event": "chunk"},
        {"id": "req", "event": "done"},
    ]

    async def read_message(_reader):
        return messages.pop(0)

    async def write_message(_writer, _payload):
        return None

    monkeypatch.setattr(asyncio, "open_unix_connection", open_connection)
    monkeypatch.setattr(broker_client, "read_message", read_message)
    monkeypatch.setattr(broker_client, "write_message", write_message)

    events = []
    async for event in client._request("tool.call", {"name": "x"}):
        events.append(event)

    assert events[-1]["event"] == "done"
    assert writer.closed is True
