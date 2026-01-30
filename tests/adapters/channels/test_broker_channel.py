from datetime import datetime, timezone

import pytest

from tactus.adapters.channels.broker import BrokerControlChannel
from tactus.broker.client import BrokerClient
from tactus.protocols.control import ControlRequest, ControlRequestType


class FakeBrokerClient(BrokerClient):
    def __init__(self, events):
        super().__init__("fake")
        self._events = events

    async def _request(self, method, params):
        for event in self._events:
            yield event


def _make_request():
    return ControlRequest(
        request_id="req-1",
        procedure_id="proc",
        procedure_name="proc-name",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="Need input",
    )


def test_init_rejects_non_client():
    with pytest.raises(TypeError):
        BrokerControlChannel(object())


def test_capabilities_flags():
    client = FakeBrokerClient([])
    channel = BrokerControlChannel(client)
    caps = channel.capabilities
    assert caps.supports_input is True
    assert caps.is_synchronous is False


@pytest.mark.asyncio
async def test_initialize_runs():
    client = FakeBrokerClient([])
    channel = BrokerControlChannel(client)
    await channel.initialize()


@pytest.mark.asyncio
async def test_send_handles_response_event():
    client = FakeBrokerClient(
        [
            {"event": "delivered"},
            {"event": "response", "data": {"value": "ok", "channel_id": "sse"}},
        ]
    )
    channel = BrokerControlChannel(client)
    result = await channel.send(_make_request())
    assert result.success is True
    response = await channel._response_queue.get()
    assert response.value == "ok"
    assert response.timed_out is False


@pytest.mark.asyncio
async def test_send_handles_timeout_event():
    client = FakeBrokerClient([{"event": "timeout"}])
    channel = BrokerControlChannel(client)
    result = await channel.send(_make_request())
    assert result.success is True
    response = await channel._response_queue.get()
    assert response.timed_out is True


@pytest.mark.asyncio
async def test_send_handles_error_event():
    client = FakeBrokerClient([{"event": "error", "error": {"message": "boom"}}])
    channel = BrokerControlChannel(client)
    result = await channel.send(_make_request())
    assert result.success is False
    assert "boom" in result.error_message


@pytest.mark.asyncio
async def test_send_delivered_only_returns_success():
    client = FakeBrokerClient([{"event": "delivered"}])
    channel = BrokerControlChannel(client)
    result = await channel.send(_make_request())
    assert result.success is True


@pytest.mark.asyncio
async def test_send_ignores_unknown_event():
    client = FakeBrokerClient(
        [
            {"event": "unknown"},
            {"event": "response", "data": {"value": "ok", "channel_id": "sse"}},
        ]
    )
    channel = BrokerControlChannel(client)
    result = await channel.send(_make_request())
    assert result.success is True


def test_from_environment(monkeypatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)
    assert BrokerControlChannel.from_environment() is None

    class FakeClient(BrokerClient):
        def __init__(self, socket_path):
            super().__init__(socket_path)

    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "/tmp/broker.sock")
    monkeypatch.setattr("tactus.broker.client.BrokerClient", FakeClient)
    channel = BrokerControlChannel.from_environment()
    assert channel is not None


def test_from_environment_handles_client_errors(monkeypatch):
    class BoomClient(BrokerClient):
        def __init__(self, socket_path):
            raise RuntimeError("boom")

    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "/tmp/broker.sock")
    monkeypatch.setattr("tactus.broker.client.BrokerClient", BoomClient)

    assert BrokerControlChannel.from_environment() is None
