import asyncio
import json

import pytest

from tactus.broker.client import BrokerClient


def _encode_message(message: dict) -> bytes:
    """Encode a message with length prefix for the protocol."""
    json_bytes = json.dumps(message).encode("utf-8")
    length = len(json_bytes)
    length_prefix = f"{length:010d}\n".encode("ascii")
    return length_prefix + json_bytes


class _FakeReader:
    def __init__(self, messages: list[bytes]):
        self._buffer = b"".join(messages)
        self._pos = 0

    async def readline(self) -> bytes:
        await asyncio.sleep(0)
        if self._pos >= len(self._buffer):
            return b""
        newline_pos = self._buffer.find(b"\n", self._pos)
        if newline_pos == -1:
            result = self._buffer[self._pos :]
            self._pos = len(self._buffer)
            return result
        result = self._buffer[self._pos : newline_pos + 1]
        self._pos = newline_pos + 1
        return result

    async def readexactly(self, n: int) -> bytes:
        """Read exactly n bytes from the buffer."""
        await asyncio.sleep(0)
        if self._pos + n > len(self._buffer):
            raise asyncio.IncompleteReadError(self._buffer[self._pos :], n)
        result = self._buffer[self._pos : self._pos + n]
        self._pos += n
        return result


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
            _encode_message({"id": "req", "event": "delta", "data": {"text": "he"}}),
            _encode_message({"id": "req", "event": "done", "data": {"text": "hello"}}),
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
    assert '"method": "llm.chat"' in sent


@pytest.mark.asyncio
async def test_tcp_tool_call_returns_result(monkeypatch: pytest.MonkeyPatch):
    reader = _FakeReader(
        [
            _encode_message(
                {"id": "req", "event": "done", "data": {"result": {"ok": True, "echo": {"x": 1}}}}
            ),
        ]
    )
    writer = _FakeWriter()

    async def fake_open_connection(host: str, port: int, ssl=None):
        assert host == "example.com"
        assert port == 1234
        assert ssl is None
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("U", (), {"hex": "req"})())

    client = BrokerClient("tcp://example.com:1234")
    result = await client.call_tool(name="host.ping", args={"x": 1})

    sent = b"".join(writer.writes).decode("utf-8")
    assert '"method": "tool.call"' in sent
    assert result == {"ok": True, "echo": {"x": 1}}


@pytest.mark.asyncio
async def test_tcp_tool_call_raises_on_error(monkeypatch: pytest.MonkeyPatch):
    reader = _FakeReader(
        [
            _encode_message(
                {
                    "id": "req",
                    "event": "error",
                    "error": {"type": "ToolNotAllowed", "message": "no"},
                }
            ),
        ]
    )
    writer = _FakeWriter()

    async def fake_open_connection(host: str, port: int, ssl=None):
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("U", (), {"hex": "req"})())

    client = BrokerClient("tcp://example.com:1234")

    with pytest.raises(RuntimeError):
        await client.call_tool(name="host.not_allowed", args={})


@pytest.mark.asyncio
async def test_tls_transport_uses_ssl_context(monkeypatch: pytest.MonkeyPatch):
    # Provide a done event so the client can complete
    reader = _FakeReader(
        [
            _encode_message({"id": "req", "event": "done", "data": {"text": "response"}}),
        ]
    )
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

    assert len(events) == 1
    assert events[0]["event"] == "done"
