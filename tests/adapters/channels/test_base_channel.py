"""Tests for base channel behavior."""

import asyncio
import pytest
from datetime import datetime, timezone

from tactus.adapters.channels.base import InProcessChannel
from tactus.protocols.control import (
    ControlRequest,
    ControlResponse,
    ChannelCapabilities,
    DeliveryResult,
    ControlRequestType,
)


class DummyChannel(InProcessChannel):
    @property
    def channel_id(self) -> str:
        return "dummy"

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities()

    async def send(self, request: ControlRequest) -> DeliveryResult:
        return DeliveryResult(
            channel_id=self.channel_id,
            external_message_id="ext",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )


def _request():
    return ControlRequest(
        request_id="req",
        procedure_id="proc",
        procedure_name="proc",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="msg",
    )


def test_receive_and_shutdown():
    channel = DummyChannel()
    response = ControlResponse(request_id="req", value="ok")

    async def run():
        channel.push_response(response)
        async for item in channel.receive():
            assert item.request_id == "req"
            break
        await channel.shutdown()

    asyncio.run(run())


def test_send_returns_delivery_result():
    channel = DummyChannel()

    async def run():
        result = await channel.send(_request())
        assert result.success is True

    asyncio.run(run())


def test_initialize_logs_and_runs():
    channel = DummyChannel()

    async def run():
        await channel.initialize()

    asyncio.run(run())


def test_receive_cancellation_breaks_loop():
    channel = DummyChannel()

    async def consume():
        async for _ in channel.receive():
            pass

    async def run():
        task = asyncio.create_task(consume())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pytest.fail("receive() should swallow cancellation and exit cleanly")

    asyncio.run(run())


def test_push_response_handles_queue_error(monkeypatch):
    channel = DummyChannel()

    def raise_error(_):
        raise RuntimeError("queue failed")

    monkeypatch.setattr(channel._response_queue, "put_nowait", raise_error)
    channel.push_response(ControlResponse(request_id="req", value="ok"))


def test_receive_timeout_then_shutdown():
    channel = DummyChannel()

    async def run():
        task = asyncio.create_task(channel.receive().__anext__())
        await asyncio.sleep(0.6)
        await channel.shutdown()
        try:
            await task
        except StopAsyncIteration:
            return

    asyncio.run(run())


def test_cancel_noop_does_not_raise():
    channel = DummyChannel()

    async def run():
        await channel.cancel("req", "done")

    asyncio.run(run())
