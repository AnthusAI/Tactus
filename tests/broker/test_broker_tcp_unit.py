import asyncio
import json

import pytest

from tactus.broker.client import BrokerClient


class _FakeReader:
    def __init__(self, lines: list[bytes]):
        self._lines = list(lines)

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if not self._lines:
            return b""
        return self._lines.pop(0)


class _FakeWriter:
    def __init__(self):
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


@pytest.mark.asyncio
async def test_tcp_transport_sends_request_and_yields_events(monkeypatch: pytest.MonkeyPatch):
    reader = _FakeReader(
        [
            json.dumps({"id": "req", "event": "delta", "data": {"text": "he"}}).encode("utf-8")
            + b"\n",
            json.dumps({"id": "req", "event": "done", "data": {"text": "hello"}}).encode("utf-8")
            + b"\n",
        ]
    )
    writer = _FakeWriter()

    async def fake_open_connection(host: str, port: int, ssl=None):
        assert host == "example.com"
        assert port == 1234
        assert ssl is None
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)

    client = BrokerClient("tcp://example.com:1234")

    async def fake_uuid():
        return "req"

    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("U", (), {"hex": "req"})())

    events = []
    async for event in client.llm_chat(
        provider="openai",
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        stream=True,
    ):
        events.append(event)

    assert [e["event"] for e in events] == ["delta", "done"]
    assert writer.closed is True
    sent = b"".join(writer.writes).decode("utf-8")
    assert '"method":"llm.chat"' in sent


@pytest.mark.asyncio
async def test_tls_transport_uses_ssl_context(monkeypatch: pytest.MonkeyPatch):
    reader = _FakeReader([b""])
    writer = _FakeWriter()

    async def fake_open_connection(host: str, port: int, ssl=None):
        assert host == "example.com"
        assert port == 443
        assert ssl is not None
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    monkeypatch.setenv("TACTUS_BROKER_TLS_INSECURE", "1")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("U", (), {"hex": "req"})())

    client = BrokerClient("tls://example.com:443")

    events = []
    async for event in client.llm_chat(
        provider="openai",
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "hi"}],
        stream=False,
    ):
        events.append(event)

    assert events == []
