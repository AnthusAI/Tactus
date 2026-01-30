import ssl

import pytest

from tactus.broker.client import BrokerClient, close_stdio_transport


def test_from_environment_returns_none(monkeypatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)
    assert BrokerClient.from_environment() is None


def test_from_environment_returns_client(monkeypatch):
    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "stdio")
    client = BrokerClient.from_environment()
    assert client is not None
    assert client.socket_path == "stdio"


@pytest.mark.asyncio
async def test_request_invalid_tcp_endpoint():
    client = BrokerClient("tcp://localhost")
    with pytest.raises(ValueError):
        async for _ in client._request("llm.chat", {}):
            pass


@pytest.mark.asyncio
async def test_call_tool_validates_inputs():
    client = BrokerClient("stdio")
    with pytest.raises(ValueError):
        await client.call_tool(name="", args={})
    with pytest.raises(ValueError):
        await client.call_tool(name="tool", args="bad")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_llm_chat_passes_tools_and_tool_choice():
    class FakeClient(BrokerClient):
        def __init__(self):
            super().__init__("stdio")
            self.params = None

        async def _request(self, method, params):
            self.params = params
            yield {"event": "done"}

    client = FakeClient()
    async for _ in client.llm_chat(
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.5,
        max_tokens=10,
        stream=False,
        tools=[{"name": "tool"}],
        tool_choice="auto",
    ):
        pass

    assert client.params["tools"] == [{"name": "tool"}]
    assert client.params["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_request_invalid_tcp_port():
    client = BrokerClient("tcp://localhost:abc")
    with pytest.raises(ValueError):
        async for _ in client._request("llm.chat", {}):
            pass


@pytest.mark.asyncio
async def test_request_stdio_filters_request_id(monkeypatch):
    events = [
        {"id": "other", "event": "done"},
        {"id": "match", "event": "done"},
    ]

    async def fake_request(req_id, method, params):
        for event in events:
            yield event

    monkeypatch.setattr("tactus.broker.client._STDIO_TRANSPORT.request", fake_request)
    monkeypatch.setattr(
        "tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "match"})()
    )

    client = BrokerClient("stdio")
    results = []
    async for event in client._request("llm.chat", {}):
        results.append(event)

    assert results == [{"id": "match", "event": "done"}]


@pytest.mark.asyncio
async def test_request_unix_socket(monkeypatch):
    class FakeWriter:
        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def fake_open(_path):
        return object(), FakeWriter()

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, payload):
        assert payload["method"] == "llm.chat"

    monkeypatch.setattr("tactus.broker.client.asyncio.open_unix_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    client = BrokerClient("/tmp/socket")
    events = []
    async for event in client._request("llm.chat", {}):
        events.append(event)

    assert events == [{"id": "req", "event": "done"}]


@pytest.mark.asyncio
async def test_request_tls_sets_ssl_context(monkeypatch):
    class FakeSSLContext:
        def __init__(self):
            self.loaded = None
            self.check_hostname = True
            self.verify_mode = None

        def load_verify_locations(self, cafile=None):
            self.loaded = cafile

    class FakeWriter:
        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def fake_open(_host, _port, ssl=None):
        assert isinstance(ssl, FakeSSLContext)
        return object(), FakeWriter()

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, payload):
        assert payload["method"] == "llm.chat"

    monkeypatch.setenv("TACTUS_BROKER_TLS_CA_FILE", "/tmp/ca.pem")
    monkeypatch.setenv("TACTUS_BROKER_TLS_INSECURE", "1")
    monkeypatch.setattr("tactus.broker.client.ssl.create_default_context", FakeSSLContext)
    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    client = BrokerClient("tls://localhost:1234")
    events = []
    async for event in client._request("llm.chat", {}):
        events.append(event)

    assert events == [{"id": "req", "event": "done"}]


@pytest.mark.asyncio
async def test_request_tls_insecure_updates_ssl_context(monkeypatch):
    client = BrokerClient("tls://localhost:1234")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())
    monkeypatch.setenv("TACTUS_BROKER_TLS_INSECURE", "yes")
    ssl_module = ssl

    class FakeSSLContext:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = "unset"

        def load_verify_locations(self, cafile=None):
            return None

    async def fake_open(_host, _port, ssl=None):
        assert ssl.check_hostname is False
        assert ssl.verify_mode == ssl_module.CERT_NONE
        return (
            object(),
            type("W", (), {"close": lambda self: None, "wait_closed": lambda self: None})(),
        )

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.ssl.create_default_context", FakeSSLContext)
    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    async for _ in client._request("llm.chat", {}):
        pass


@pytest.mark.asyncio
async def test_request_tcp_strips_path_and_ignores_mismatch(monkeypatch):
    client = BrokerClient("tcp://localhost:1234/extra")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    class FakeWriter:
        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def fake_open(host, port, ssl=None):
        assert host == "localhost"
        assert port == 1234
        return object(), FakeWriter()

    messages = [
        {"id": "other", "event": "chunk"},
        {"id": "req", "event": "done"},
    ]

    async def fake_read(_reader):
        return messages.pop(0)

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    events = []
    async for event in client._request("llm.chat", {}):
        events.append(event)

    assert events == [{"id": "req", "event": "done"}]


@pytest.mark.asyncio
async def test_request_tcp_write_message_type_error(monkeypatch):
    client = BrokerClient("tcp://localhost:1234")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    class FakeWriter:
        def close(self):
            return None

        async def wait_closed(self):
            return None

    async def fake_open(_host, _port, ssl=None):
        return object(), FakeWriter()

    async def fake_write(_writer, _payload):
        raise TypeError("bad payload")

    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    with pytest.raises(TypeError):
        async for _ in client._request("llm.chat", {}):
            pass


@pytest.mark.asyncio
async def test_request_tcp_close_error_is_ignored(monkeypatch):
    client = BrokerClient("tcp://localhost:1234")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    class FakeWriter:
        def close(self):
            raise RuntimeError("close failed")

        async def wait_closed(self):
            raise RuntimeError("close failed")

    async def fake_open(_host, _port, ssl=None):
        return object(), FakeWriter()

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    events = []
    async for event in client._request("llm.chat", {}):
        events.append(event)

    assert events == [{"id": "req", "event": "done"}]


@pytest.mark.asyncio
async def test_request_unix_close_error_is_ignored(monkeypatch):
    client = BrokerClient("/tmp/socket")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())

    class FakeWriter:
        def close(self):
            raise RuntimeError("close failed")

        async def wait_closed(self):
            raise RuntimeError("close failed")

    async def fake_open(_path):
        return object(), FakeWriter()

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.asyncio.open_unix_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    events = []
    async for event in client._request("llm.chat", {}):
        events.append(event)

    assert events == [{"id": "req", "event": "done"}]


@pytest.mark.asyncio
async def test_close_stdio_transport_handles_no_thread(monkeypatch):
    await close_stdio_transport()


@pytest.mark.asyncio
async def test_call_tool_error_and_no_response():
    class ErrorClient(BrokerClient):
        async def _request(self, method, params):
            yield {"event": "error", "error": {"message": "boom"}}

    client = ErrorClient("stdio")
    with pytest.raises(RuntimeError, match="boom"):
        await client.call_tool(name="tool", args={})

    class EmptyClient(BrokerClient):
        async def _request(self, method, params):
            if False:
                yield {"event": "done"}

    empty_client = EmptyClient("stdio")
    with pytest.raises(RuntimeError, match="ended without a response"):
        await empty_client.call_tool(name="tool", args={})


@pytest.mark.asyncio
async def test_call_tool_error_branch():
    class ErrorClient(BrokerClient):
        async def _request(self, method, params):
            yield {"event": "error", "error": {"message": "failed"}}

    client = ErrorClient("stdio")
    with pytest.raises(RuntimeError, match="failed"):
        await client.call_tool(name="tool", args={})


@pytest.mark.asyncio
async def test_call_tool_ignores_non_terminal_events():
    class ProgressClient(BrokerClient):
        async def _request(self, method, params):
            yield {"event": "progress"}
            yield {"event": "done", "data": {"result": "ok"}}

    client = ProgressClient("stdio")
    assert await client.call_tool(name="tool", args={}) == "ok"


@pytest.mark.asyncio
async def test_request_tls_insecure_env_true_branch(monkeypatch):
    client = BrokerClient("tls://localhost:1234")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())
    monkeypatch.setenv("TACTUS_BROKER_TLS_INSECURE", "1")
    ssl_module = ssl

    class FakeSSLContext:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = "unset"

        def load_verify_locations(self, cafile=None):
            return None

    async def fake_open(_host, _port, ssl=None):
        assert ssl.check_hostname is False
        assert ssl.verify_mode == ssl_module.CERT_NONE
        return (
            object(),
            type("W", (), {"close": lambda self: None, "wait_closed": lambda self: None})(),
        )

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.ssl.create_default_context", FakeSSLContext)
    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    async for _ in client._request("llm.chat", {}):
        pass


@pytest.mark.asyncio
async def test_request_tls_insecure_env_false_branch(monkeypatch):
    client = BrokerClient("tls://localhost:1234")
    monkeypatch.setattr("tactus.broker.client.uuid.uuid4", lambda: type("u", (), {"hex": "req"})())
    monkeypatch.delenv("TACTUS_BROKER_TLS_INSECURE", raising=False)

    class FakeSSLContext:
        def __init__(self):
            self.check_hostname = True
            self.verify_mode = "unset"

        def load_verify_locations(self, cafile=None):
            return None

    async def fake_open(_host, _port, ssl=None):
        assert ssl.check_hostname is True
        assert ssl.verify_mode == "unset"
        return (
            object(),
            type("W", (), {"close": lambda self: None, "wait_closed": lambda self: None})(),
        )

    async def fake_read(_reader):
        return {"id": "req", "event": "done"}

    async def fake_write(_writer, _payload):
        return None

    monkeypatch.setattr("tactus.broker.client.ssl.create_default_context", FakeSSLContext)
    monkeypatch.setattr("tactus.broker.client.asyncio.open_connection", fake_open)
    monkeypatch.setattr("tactus.broker.client.read_message", fake_read)
    monkeypatch.setattr("tactus.broker.client.write_message", fake_write)

    async for _ in client._request("llm.chat", {}):
        pass
