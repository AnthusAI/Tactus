import asyncio
from datetime import datetime, timezone

import pytest

from tactus.adapters.channels.sse import SSEControlChannel
from tactus.protocols.control import (
    ContextLink,
    ControlRequest,
    ControlRequestItem,
    ControlRequestType,
    ControlOption,
    RuntimeContext,
    BacktraceEntry,
)


def _make_request():
    return ControlRequest(
        request_id="req-1",
        procedure_id="proc",
        procedure_name="proc-name",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="Need input",
        runtime_context=RuntimeContext(
            source_line=10,
            source_file="/tmp/test.tac",
            checkpoint_position=2,
            procedure_name="proc",
            invocation_id="inv",
            started_at=datetime.now(timezone.utc),
            elapsed_seconds=5,
            backtrace=[
                BacktraceEntry(
                    checkpoint_type="agent_turn",
                    line=1,
                    function_name="f",
                    duration_ms=12,
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_send_emits_event():
    events = []

    async def emitter(event):
        events.append(event)

    channel = SSEControlChannel(event_emitter=emitter)
    result = await channel.send(_make_request())
    assert result.success is True
    assert events[0]["event_type"] == "hitl.request"


@pytest.mark.asyncio
async def test_send_handles_emitter_error():
    async def emitter(_event):
        raise RuntimeError("boom")

    channel = SSEControlChannel(event_emitter=emitter)
    result = await channel.send(_make_request())
    assert result.success is False
    assert "boom" in result.error_message


def test_handle_ide_response_queues():
    channel = SSEControlChannel()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        channel.handle_ide_response("req-1", "ok")
    finally:
        loop.close()
        asyncio.set_event_loop(None)
    response = channel._response_queue.get_nowait()
    assert response.request_id == "req-1"
    assert response.value == "ok"


def test_get_next_event_empty_returns_none():
    channel = SSEControlChannel()
    assert channel.get_next_event() is None


def test_capabilities_defaults():
    channel = SSEControlChannel()
    caps = channel.capabilities
    assert caps.supports_input is True
    assert caps.supports_inputs is True


@pytest.mark.asyncio
async def test_initialize_noop():
    channel = SSEControlChannel()
    await channel.initialize()


@pytest.mark.asyncio
async def test_get_next_event_returns_event():
    channel = SSEControlChannel()
    await channel.send(_make_request())

    event = channel.get_next_event()
    assert event["event_type"] == "hitl.request"


def test_build_hitl_event_includes_items_and_context():
    channel = SSEControlChannel()
    request = _make_request()
    request.options = [ControlOption(label="Yes", value=True, style="primary")]
    request.items = [
        ControlRequestItem(
            item_id="item-1",
            label="Name",
            request_type=ControlRequestType.INPUT,
            message="Enter name",
            options=[],
            default_value="Ada",
            required=True,
            metadata={"hint": "full name"},
        )
    ]
    request.application_context = [ContextLink(name="Account", value="42", url="http://x")]

    event = channel._build_hitl_event(request)

    assert event["options"][0]["label"] == "Yes"
    assert event["items"][0]["item_id"] == "item-1"
    assert event["application_context"][0]["name"] == "Account"


def test_serialize_runtime_context_none():
    channel = SSEControlChannel()
    assert channel._serialize_runtime_context(None) is None


@pytest.mark.asyncio
async def test_cancel_queues_event_when_no_emitter():
    channel = SSEControlChannel()
    await channel.cancel("req-1", "done")

    event = channel.get_next_event()
    assert event["event_type"] == "hitl.cancel"


@pytest.mark.asyncio
async def test_cancel_emits_event_with_emitter():
    events = []

    async def emitter(event):
        events.append(event)

    channel = SSEControlChannel(event_emitter=emitter)
    await channel.cancel("req-2", "done")
    assert events[0]["event_type"] == "hitl.cancel"


@pytest.mark.asyncio
async def test_handle_ide_response_with_running_loop():
    channel = SSEControlChannel()
    channel.handle_ide_response("req-2", "ok")
    await asyncio.sleep(0)

    response = await channel._response_queue.get()
    assert response.request_id == "req-2"
    assert response.value == "ok"


def test_handle_ide_response_put_error():
    channel = SSEControlChannel()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:

        def raise_error(_response):
            raise RuntimeError("queue failed")

        channel._response_queue.put_nowait = raise_error
        channel.handle_ide_response("req-3", "ok")
    finally:
        loop.close()
        asyncio.set_event_loop(None)


@pytest.mark.asyncio
async def test_shutdown_sets_event():
    channel = SSEControlChannel()
    await channel.shutdown()
    assert channel._shutdown_event.is_set() is True
