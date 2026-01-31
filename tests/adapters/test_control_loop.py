from datetime import datetime, timezone

import pytest

import asyncio


from tactus.adapters.control_loop import ControlLoopHandler
from tactus.protocols.control import (
    ChannelCapabilities,
    ControlResponse,
    DeliveryResult,
    ControlRequestItem,
)
from tactus.core.exceptions import ProcedureWaitingForHuman


class DummyExecutionContext:
    def __init__(self):
        self._pos = 7
        self.current_run_id = "runid1234abcd"

    def next_position(self):
        self._pos += 1
        return self._pos


class DummyStorage:
    def __init__(self):
        self.state = {}

    def get_state(self, procedure_id):
        return self.state.get(procedure_id)

    def set_state(self, procedure_id, state):
        self.state[procedure_id] = state


class DummyChannel:
    def __init__(self, channel_id, capabilities):
        self._channel_id = channel_id
        self._capabilities = capabilities

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def capabilities(self):
        return self._capabilities

    async def initialize(self):
        return None

    async def shutdown(self):
        return None

    async def send(self, request):
        raise AssertionError("send should not be called")

    async def receive(self):
        if False:
            yield None

    async def cancel(self, external_message_id, reason):
        return None


class TrackingChannel(DummyChannel):
    def __init__(self, channel_id, capabilities):
        super().__init__(channel_id, capabilities)
        self.initialized = 0
        self.shutdowns = 0

    async def initialize(self):
        self.initialized += 1

    async def shutdown(self):
        self.shutdowns += 1


class RespondingChannel(DummyChannel):
    def __init__(self, channel_id, capabilities, response):
        super().__init__(channel_id, capabilities)
        self._response = response

    async def send(self, request):
        return DeliveryResult(
            channel_id=self._channel_id,
            external_message_id="msg",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def receive(self):
        yield self._response


class FailingSendChannel(DummyChannel):
    async def send(self, request):
        raise RuntimeError("boom")


class NoResponseChannel(DummyChannel):
    async def send(self, request):
        return DeliveryResult(
            channel_id=self._channel_id,
            external_message_id="msg",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def receive(self):
        if False:
            yield None


class SuccessChannel(DummyChannel):
    async def send(self, request):
        return DeliveryResult(
            channel_id=self._channel_id,
            external_message_id=f"msg-{self._channel_id}",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def receive(self):
        if False:
            yield None


def test_build_request_with_context_and_options():
    execution_context = DummyExecutionContext()
    handler = ControlLoopHandler(channels=[], execution_context=execution_context)

    runtime_context = {
        "source_line": 12,
        "source_file": "workflow.tac",
        "checkpoint_position": 4,
        "procedure_name": "Example",
        "invocation_id": "inv-1",
        "started_at": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
        "elapsed_seconds": 10.5,
        "backtrace": [{"checkpoint_type": "llm", "line": 99, "function_name": "main"}],
    }
    application_context = [{"name": "Customer", "value": "ACME", "url": "http://x"}]

    request = handler._build_request(
        procedure_id="proc-1",
        request_type="approval",
        message="Approve?",
        options=[{"label": "Yes", "value": True, "style": "primary"}],
        metadata={"info": "x"},
        procedure_name="Proc",
        invocation_id="inv-1",
        runtime_context=runtime_context,
        application_context=application_context,
    )

    assert request.request_id.startswith("proc-1:runid123:pos")
    assert request.request_type.value == "approval"
    assert request.options[0].label == "Yes"
    assert request.options[0].value is True
    assert request.runtime_context is not None
    assert request.runtime_context.source_line == 12
    assert request.runtime_context.backtrace[0].checkpoint_type == "llm"
    assert request.application_context[0].name == "Customer"


def test_build_request_without_execution_context_uses_uuid_and_defaults(monkeypatch):
    handler = ControlLoopHandler(channels=[])

    class DummyUUID:
        hex = "abc123def456"

    monkeypatch.setattr("tactus.adapters.control_loop.uuid.uuid4", lambda: DummyUUID())

    request = handler._build_request(
        procedure_id="proc-uuid",
        request_type="approval",
        message="Approve?",
        options=[{"label": "Yes"}],
    )

    assert request.request_id == "proc-uuid:unknown:abc123def456"
    assert request.options[0].value == "Yes"
    assert request.options[0].style == "default"


def test_build_request_runtime_context_started_at_datetime():
    handler = ControlLoopHandler(channels=[])
    started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

    request = handler._build_request(
        procedure_id="proc-ctx",
        request_type="approval",
        message="Approve?",
        runtime_context={"started_at": started_at},
    )

    assert request.runtime_context.started_at == started_at


def test_build_request_inputs_metadata_items():
    handler = ControlLoopHandler(channels=[])

    request = handler._build_request(
        procedure_id="proc-2",
        request_type="inputs",
        message="Provide inputs",
        metadata={
            "items": [
                {
                    "item_id": "item-1",
                    "label": "Name",
                    "request_type": "input",
                    "message": "Enter name",
                    "options": [],
                    "default_value": "Jane",
                    "required": True,
                    "metadata": {},
                }
            ]
        },
    )

    assert request.request_type.value == "inputs"
    assert len(request.items) == 1
    assert request.items[0].item_id == "item-1"
    assert request.items[0].default_value == "Jane"


def test_get_eligible_channels_respects_capabilities():
    handler = ControlLoopHandler(
        channels=[
            DummyChannel("approval", ChannelCapabilities(supports_approval=True)),
            DummyChannel("input", ChannelCapabilities(supports_approval=False)),
        ]
    )

    request = handler._build_request(
        procedure_id="proc-3",
        request_type="approval",
        message="Approve?",
    )

    eligible = handler._get_eligible_channels(request)
    assert [channel.channel_id for channel in eligible] == ["approval"]


@pytest.mark.parametrize(
    "request_type,capabilities,expected",
    [
        ("input", ChannelCapabilities(supports_input=True), True),
        ("review", ChannelCapabilities(supports_review=True), True),
        ("escalation", ChannelCapabilities(supports_escalation=True), True),
        ("custom", ChannelCapabilities(), True),
    ],
)
def test_channel_supports_request_variants(request_type, capabilities, expected):
    handler = ControlLoopHandler(channels=[])
    request = handler._build_request("p", request_type, "m")

    assert handler._channel_supports_request(DummyChannel("c", capabilities), request) is expected


def test_check_pending_response_and_cancel():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)

    response = ControlResponse(
        request_id="req-1",
        value="ok",
        responded_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
    )

    storage.set_state(
        "proc-4",
        {f"{handler.PENDING_KEY_PREFIX}req-1": {"response": response.model_dump(mode="json")}},
    )

    found = handler.check_pending_response("proc-4", "req-1")
    assert found is not None
    assert found.value == "ok"

    handler.cancel_pending_request("proc-4", "req-1")
    assert storage.get_state("proc-4") == {}


def test_store_pending_records_state():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    request = handler._build_request("proc-5", "approval", "m")
    deliveries = [
        DeliveryResult(
            channel_id="a",
            external_message_id="msg-a",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )
    ]

    handler._store_pending(request, deliveries)

    state = storage.get_state("proc-5")
    key = f"{handler.PENDING_KEY_PREFIX}{request.request_id}"
    assert key in state
    assert state[key]["deliveries"][0]["external_message_id"] == "msg-a"


@pytest.mark.asyncio
async def test_initialize_channels_only_runs_once():
    channel = TrackingChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])

    await handler.initialize_channels()
    await handler.initialize_channels()

    assert channel.initialized == 1


@pytest.mark.asyncio
async def test_shutdown_channels_no_channels():
    handler = ControlLoopHandler(channels=[])

    await handler.shutdown_channels()


@pytest.mark.asyncio
async def test_shutdown_channels_calls_channel_shutdowns():
    channel = TrackingChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])

    await handler.shutdown_channels()

    assert channel.shutdowns == 1


@pytest.mark.asyncio
async def test_fanout_sends_all_channels():
    channels = [
        SuccessChannel("a", ChannelCapabilities()),
        SuccessChannel("b", ChannelCapabilities()),
    ]
    handler = ControlLoopHandler(channels=channels)
    request = handler._build_request("p", "approval", "m")

    results = await handler._fanout(request, channels)

    assert {result.channel_id for result in results} == {"a", "b"}


def test_request_interaction_uses_running_loop(monkeypatch):
    handler = ControlLoopHandler(channels=[])

    async def fake_async(_request):
        return ControlResponse(request_id="req", value="ok")

    class DummyLoop:
        def __init__(self):
            self._closed = False

        def is_closed(self):
            return self._closed

        def run_until_complete(self, coro):
            return asyncio.run(coro)

    dummy_loop = DummyLoop()

    monkeypatch.setattr(handler, "_request_interaction_async", fake_async)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: dummy_loop)
    monkeypatch.setattr("nest_asyncio.apply", lambda: None)

    response = handler.request_interaction("proc", "approval", "msg")
    assert response.value == "ok"


def test_request_interaction_uses_new_loop(monkeypatch):
    handler = ControlLoopHandler(channels=[])

    async def fake_async(_request):
        return ControlResponse(request_id="req", value="ok")

    created_loops: list[asyncio.AbstractEventLoop] = []
    original_new_event_loop = asyncio.new_event_loop

    def create_loop():
        loop = original_new_event_loop()
        created_loops.append(loop)
        return loop

    monkeypatch.setattr(handler, "_request_interaction_async", fake_async)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: (_ for _ in ()).throw(RuntimeError()))
    monkeypatch.setattr(asyncio, "new_event_loop", create_loop)

    response = handler.request_interaction("proc", "approval", "msg")
    assert response.value == "ok"
    assert created_loops


def test_request_interaction_restores_previous_event_loop(monkeypatch):
    handler = ControlLoopHandler(channels=[])

    async def fake_async(_request):
        return ControlResponse(request_id="req", value="ok")

    previous_event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(previous_event_loop)

    monkeypatch.setattr(handler, "_request_interaction_async", fake_async)
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: (_ for _ in ()).throw(RuntimeError()))

    response = handler.request_interaction("proc", "approval", "msg")
    assert response.value == "ok"
    assert asyncio.get_event_loop() is previous_event_loop

    previous_event_loop.close()
    asyncio.set_event_loop(None)


@pytest.mark.asyncio
async def test_wait_for_first_response_returns_response():
    response = ControlResponse(request_id="req", value="ok", channel_id="chan")
    channel = RespondingChannel("chan", ChannelCapabilities(is_synchronous=True), response)

    handler = ControlLoopHandler(channels=[channel])
    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[channel],
        deliveries=[],
    )

    assert result == response


@pytest.mark.asyncio
async def test_wait_for_first_response_timeout_returns_none():
    channel = NoResponseChannel("chan", ChannelCapabilities(is_synchronous=False))
    handler = ControlLoopHandler(channels=[channel], immediate_response_timeout=0.01)

    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[channel],
        deliveries=[],
    )

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_first_response_handles_timeout_error(monkeypatch):
    channel = NoResponseChannel("chan", ChannelCapabilities(is_synchronous=False))
    handler = ControlLoopHandler(channels=[channel], immediate_response_timeout=0.01)

    async def fake_wait(*_args, **_kwargs):
        raise asyncio.TimeoutError

    monkeypatch.setattr(asyncio, "wait", fake_wait)

    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[channel],
        deliveries=[],
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_first_from_channel_handles_exception():
    class FailingReceiveChannel(DummyChannel):
        async def receive(self):
            raise ValueError("boom")
            if False:
                yield None

    channel = FailingReceiveChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])

    result = await handler._get_first_from_channel(channel)

    assert result is None


@pytest.mark.asyncio
async def test_send_with_error_handling_returns_failure():
    channel = FailingSendChannel("fail", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])
    request = handler._build_request("p", "approval", "m")

    result = await handler._send_with_error_handling(channel, request)

    assert result.success is False
    assert "boom" in (result.error_message or "")


@pytest.mark.asyncio
async def test_request_interaction_async_no_channels():
    handler = ControlLoopHandler(channels=[])
    request = handler._build_request("p", "approval", "m")

    with pytest.raises(RuntimeError, match="No control channels"):
        await handler._request_interaction_async(request)


@pytest.mark.asyncio
async def test_wait_for_first_response_returns_none_when_no_responses():
    channel = DummyChannel("empty", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel], immediate_response_timeout=0.01)

    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[channel],
        deliveries=[],
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_first_from_channel_handles_errors():
    class ErrorChannel(DummyChannel):
        async def receive(self):
            if False:
                yield None
            raise RuntimeError("bad")

    channel = ErrorChannel("err", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])

    result = await handler._get_first_from_channel(channel)

    assert result is None


@pytest.mark.asyncio
async def test_cancel_other_channels_calls_cancel():
    class CancelChannel(DummyChannel):
        def __init__(self, channel_id, capabilities):
            super().__init__(channel_id, capabilities)
            self.cancelled = []

        async def cancel(self, external_message_id, reason):
            self.cancelled.append((external_message_id, reason))

    channel_a = CancelChannel("a", ChannelCapabilities())
    channel_b = CancelChannel("b", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel_a, channel_b])
    request = handler._build_request("p", "approval", "m")
    deliveries = [
        DeliveryResult(
            channel_id="a",
            external_message_id="msg-a",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        ),
        DeliveryResult(
            channel_id="b",
            external_message_id="msg-b",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        ),
    ]

    await handler._cancel_other_channels(request, deliveries, winning_channel="a")

    assert channel_a.cancelled == []
    assert channel_b.cancelled[0][0] == "msg-b"


@pytest.mark.asyncio
async def test_cancel_with_error_handling_ignores_failure():
    class CancelFailChannel(DummyChannel):
        async def cancel(self, external_message_id, reason):
            raise RuntimeError("nope")

    handler = ControlLoopHandler(channels=[])

    await handler._cancel_with_error_handling(
        CancelFailChannel("c", ChannelCapabilities()), "x", "y"
    )


@pytest.mark.asyncio
async def test_request_interaction_async_stores_response():
    storage = DummyStorage()
    response = ControlResponse(request_id="req", value="ok", channel_id="chan")
    channel = RespondingChannel("chan", ChannelCapabilities(is_synchronous=True), response)
    handler = ControlLoopHandler(channels=[channel], storage=storage)

    request = handler._build_request("proc", "approval", "m")
    result = await handler._request_interaction_async(request)

    assert result.value == "ok"
    state = storage.get_state("proc")
    key = f"{handler.PENDING_KEY_PREFIX}{request.request_id}"
    assert key in state
    assert state[key]["response"]["value"] == "ok"


@pytest.mark.asyncio
async def test_request_interaction_async_no_response_raises(monkeypatch):
    storage = DummyStorage()
    channel = NoResponseChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(
        channels=[channel], storage=storage, immediate_response_timeout=0.01
    )

    async def fake_wait(*args, **kwargs):
        return None

    monkeypatch.setattr(handler, "_wait_for_first_response", fake_wait)

    request = handler._build_request("proc", "approval", "m")

    with pytest.raises(Exception) as exc:
        await handler._request_interaction_async(request)

    assert "ProcedureWaitingForHuman" in type(exc.value).__name__


@pytest.mark.asyncio
async def test_request_interaction_async_uses_cached_response():
    storage = DummyStorage()
    response = ControlResponse(request_id="req", value="cached", channel_id="chan")
    handler = ControlLoopHandler(
        channels=[DummyChannel("chan", ChannelCapabilities())], storage=storage
    )

    request = handler._build_request("proc", "approval", "m")
    storage.set_state(
        "proc",
        {
            f"{handler.PENDING_KEY_PREFIX}{request.request_id}": {
                "response": response.model_dump(mode="json")
            }
        },
    )

    result = await handler._request_interaction_async(request)

    assert result.value == "cached"


@pytest.mark.asyncio
async def test_request_interaction_async_no_eligible_channels():
    channel = DummyChannel("chan", ChannelCapabilities(supports_approval=False))
    handler = ControlLoopHandler(channels=[channel])
    request = handler._build_request("proc", "approval", "m")

    with pytest.raises(RuntimeError, match="No channels support"):
        await handler._request_interaction_async(request)


@pytest.mark.asyncio
async def test_request_interaction_async_all_deliveries_failed():
    channel = FailingSendChannel("chan", ChannelCapabilities(supports_approval=True))
    handler = ControlLoopHandler(channels=[channel])
    request = handler._build_request("proc", "approval", "m")

    with pytest.raises(RuntimeError, match="All channel deliveries failed"):
        await handler._request_interaction_async(request)


@pytest.mark.asyncio
async def test_wait_for_first_response_cancels_pending_tasks():
    class BlockingChannel(DummyChannel):
        async def receive(self):
            await asyncio.Event().wait()
            if False:
                yield None

    channel_done = DummyChannel("done", ChannelCapabilities(is_synchronous=True))
    channel_blocked = BlockingChannel("blocked", ChannelCapabilities(is_synchronous=False))
    handler = ControlLoopHandler(
        channels=[channel_done, channel_blocked], immediate_response_timeout=0.01
    )

    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[channel_done, channel_blocked],
        deliveries=[],
    )

    assert result is None


@pytest.mark.asyncio
async def test_wait_for_first_response_handles_task_exception(monkeypatch):
    handler = ControlLoopHandler(channels=[DummyChannel("chan", ChannelCapabilities())])

    async def boom(_channel):
        raise RuntimeError("boom")

    monkeypatch.setattr(handler, "_get_first_from_channel", boom)

    result = await handler._wait_for_first_response(
        request=handler._build_request("p", "approval", "m"),
        channels=[DummyChannel("chan", ChannelCapabilities())],
        deliveries=[],
    )

    assert result is None


def test_store_pending_no_storage():
    handler = ControlLoopHandler(channels=[])
    request = handler._build_request("proc", "approval", "m")

    handler._store_pending(request, [])


def test_store_response_no_storage():
    handler = ControlLoopHandler(channels=[])
    request = handler._build_request("proc", "approval", "m")
    response = ControlResponse(request_id=request.request_id, value="ok")

    handler._store_response(request, response)


def test_store_response_updates_existing_pending():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    request = handler._build_request("proc", "approval", "m")
    response = ControlResponse(request_id=request.request_id, value="ok", channel_id="chan")

    storage.set_state(
        "proc",
        {
            f"{handler.PENDING_KEY_PREFIX}{request.request_id}": {
                "request": request.model_dump(mode="json")
            }
        },
    )

    handler._store_response(request, response)

    state = storage.get_state("proc")
    pending = state[f"{handler.PENDING_KEY_PREFIX}{request.request_id}"]
    assert pending["response"]["value"] == "ok"


def test_check_pending_response_no_storage():
    handler = ControlLoopHandler(channels=[])

    assert handler.check_pending_response("proc", "msg") is None


def test_cancel_pending_request_no_storage():
    handler = ControlLoopHandler(channels=[])

    handler.cancel_pending_request("proc", "msg")


def test_control_loop_adapter_request_interaction_object():
    from tactus.adapters.control_loop import ControlLoopHITLAdapter

    calls = {}

    class DummyHandler:
        def __init__(self):
            self.execution_context = "old"

        def request_interaction(self, **kwargs):
            calls.update(kwargs)
            return ControlResponse(
                request_id="req",
                value="ok",
                channel_id="chan",
                responded_at=datetime.now(timezone.utc),
            )

    class DummyCtx:
        procedure_name = "Proc"
        invocation_id = "inv"

        def get_subject(self):
            return "subject"

        def get_started_at(self):
            return datetime(2024, 1, 1, tzinfo=timezone.utc)

        def get_input_summary(self):
            return {"a": 1}

        def get_conversation_history(self):
            return [{"role": "user", "content": "hi"}]

        def get_prior_control_interactions(self):
            return [{"request_id": "r1"}]

        def get_runtime_context(self):
            return {"source_file": "x.tac"}

    class RequestObj:
        request_type = "approval"
        message = "ok?"
        options = None
        timeout_seconds = None
        default_value = None
        metadata = {"namespace": "ns"}

    handler = DummyHandler()
    adapter = ControlLoopHITLAdapter(handler, execution_context=DummyCtx())

    response = adapter.request_interaction("proc-1", RequestObj())

    assert response.value == "ok"
    assert calls["procedure_name"] == "Proc"
    assert calls["invocation_id"] == "inv"
    assert calls["namespace"] == "ns"
    assert calls["subject"] == "subject"
    assert calls["input_summary"] == {"a": 1}
    assert calls["runtime_context"] == {"source_file": "x.tac"}
    assert handler.execution_context == "old"


def test_control_loop_adapter_request_interaction_dict():
    from tactus.adapters.control_loop import ControlLoopHITLAdapter

    class DummyHandler:
        def __init__(self):
            self.execution_context = None
            self.calls = []

        def request_interaction(self, **kwargs):
            self.calls.append(kwargs)
            return ControlResponse(request_id="req", value="ok", channel_id="chan")

    handler = DummyHandler()
    adapter = ControlLoopHITLAdapter(handler)

    response = adapter.request_interaction(
        "proc-1",
        {
            "request_type": "input",
            "message": "m",
            "options": [{"label": "x"}],
            "timeout_seconds": 5,
            "default_value": "d",
            "metadata": {"k": "v"},
        },
    )

    assert response.value == "ok"
    assert handler.calls[0]["request_type"] == "input"


def test_control_loop_adapter_check_pending_response_and_cancel():
    from tactus.adapters.control_loop import ControlLoopHITLAdapter

    class DummyHandler:
        def check_pending_response(self, procedure_id, message_id):
            return None

        def cancel_pending_request(self, procedure_id, message_id):
            self.called = (procedure_id, message_id)

    handler = DummyHandler()
    adapter = ControlLoopHITLAdapter(handler)

    assert adapter.check_pending_response("proc", "msg") is None
    adapter.cancel_pending_request("proc", "msg")
    assert handler.called == ("proc", "msg")


def test_request_interaction_stores_response_and_pending():
    storage = DummyStorage()
    response = ControlResponse(
        request_id="req",
        value="ok",
        channel_id="chan",
        responded_at=datetime.now(timezone.utc),
    )
    channel = RespondingChannel("chan", ChannelCapabilities(), response)
    handler = ControlLoopHandler(
        channels=[channel], storage=storage, immediate_response_timeout=0.01
    )

    result = handler.request_interaction(
        procedure_id="proc",
        request_type="approval",
        message="ok?",
    )

    assert result.value == "ok"
    state = storage.get_state("proc")
    assert state
    assert any(key.startswith(handler.PENDING_KEY_PREFIX) for key in state)


def test_request_interaction_without_storage_response():
    response = ControlResponse(
        request_id="req",
        value="ok",
        channel_id="chan",
        responded_at=datetime.now(timezone.utc),
    )
    channel = RespondingChannel("chan", ChannelCapabilities(), response)
    handler = ControlLoopHandler(channels=[channel], immediate_response_timeout=0.01)

    result = handler.request_interaction(
        procedure_id="proc",
        request_type="approval",
        message="ok?",
    )

    assert result.value == "ok"


def test_request_interaction_stores_pending_on_no_response():
    storage = DummyStorage()
    channel = NoResponseChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(
        channels=[channel], storage=storage, immediate_response_timeout=0.01
    )

    with pytest.raises(ProcedureWaitingForHuman):
        handler.request_interaction(
            procedure_id="proc",
            request_type="approval",
            message="ok?",
        )

    state = storage.get_state("proc")
    assert state


def test_request_interaction_without_storage_no_response():
    channel = NoResponseChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel], immediate_response_timeout=0.01)

    with pytest.raises(ProcedureWaitingForHuman):
        handler.request_interaction(
            procedure_id="proc",
            request_type="approval",
            message="ok?",
        )


def test_build_request_with_inputs_items_and_runtime_context():
    handler = ControlLoopHandler(channels=[])
    handler.execution_context = DummyExecutionContext()

    request = handler._build_request(
        procedure_id="proc",
        request_type="inputs",
        message="m",
        metadata={
            "items": [
                {"item_id": "a", "label": "A", "request_type": "input", "message": "A?"},
                {"item_id": "b", "label": "B", "request_type": "input", "message": "B?"},
            ]
        },
        runtime_context={"started_at": "2024-01-01T00:00:00Z"},
    )

    assert isinstance(request.items[0], ControlRequestItem)
    assert request.items[0].label == "A"
    assert request.runtime_context.started_at is not None


def test_build_request_inputs_without_items_metadata():
    handler = ControlLoopHandler(channels=[])

    request = handler._build_request(
        procedure_id="proc",
        request_type="inputs",
        message="m",
        metadata={"note": "no items"},
    )

    assert request.items == []


def test_build_request_parses_runtime_context_started_at_string():
    handler = ControlLoopHandler(channels=[])

    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
        runtime_context={"started_at": "2024-01-01T01:02:03+00:00"},
    )

    assert request.runtime_context.started_at.year == 2024


def test_build_request_runtime_context_without_started_at():
    handler = ControlLoopHandler(channels=[])

    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
        runtime_context={"source_line": 12},
    )

    assert request.runtime_context.started_at is None


def test_build_request_with_missing_run_id():
    class NoRunContext:
        current_run_id = None

        def next_position(self):
            return 1

    handler = ControlLoopHandler(channels=[])
    handler.execution_context = NoRunContext()

    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
    )

    assert "unknown" in request.request_id


def test_check_pending_response_found_and_cancel_removes():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    response = ControlResponse(
        request_id="req",
        value="ok",
        channel_id="chan",
        responded_at=datetime.now(timezone.utc),
    )

    storage.set_state(
        "proc",
        {f"{handler.PENDING_KEY_PREFIX}msg": {"response": response.model_dump(mode="json")}},
    )

    found = handler.check_pending_response("proc", "msg")
    assert found.value == "ok"

    handler.cancel_pending_request("proc", "msg")
    assert handler.check_pending_response("proc", "msg") is None


def test_check_pending_response_returns_response_when_present():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    response = ControlResponse(
        request_id="msg",
        value="ok",
        channel_id="chan",
        responded_at=datetime.now(timezone.utc),
    )

    storage.set_state(
        "proc",
        {f"{handler.PENDING_KEY_PREFIX}msg": {"response": response.model_dump(mode="json")}},
    )

    found = handler.check_pending_response("proc", "msg")
    assert found is not None
    assert found.value == "ok"


def test_check_pending_response_returns_none_when_no_response():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    storage.set_state("proc", {f"{handler.PENDING_KEY_PREFIX}msg": {"request": {"x": 1}}})

    assert handler.check_pending_response("proc", "msg") is None


def test_cancel_pending_request_noop_when_missing():
    storage = DummyStorage()
    handler = ControlLoopHandler(channels=[], storage=storage)
    storage.set_state("proc", {"other": {"value": "x"}})

    handler.cancel_pending_request("proc", "missing")

    assert storage.get_state("proc") == {"other": {"value": "x"}}


def test_cancel_other_channels_skips_missing_channel():
    channel = DummyChannel("chan", ChannelCapabilities())
    handler = ControlLoopHandler(channels=[channel])
    deliveries = [
        DeliveryResult(
            channel_id="missing",
            external_message_id="msg",
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )
    ]

    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
    )

    asyncio.run(handler._cancel_other_channels(request, deliveries, None))


def test_wait_for_first_response_handles_cancelled_task(monkeypatch):
    handler = ControlLoopHandler(channels=[DummyChannel("chan", ChannelCapabilities())])
    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
    )

    async def fake_wait(tasks, timeout, return_when):
        task = next(iter(tasks))
        task.cancel()
        return {task}, set()

    monkeypatch.setattr(asyncio, "wait", fake_wait)

    response = asyncio.run(handler._wait_for_first_response(request, handler.channels, []))
    assert response is None


def test_wait_for_first_response_handles_cancelled_task_result(monkeypatch):
    handler = ControlLoopHandler(channels=[DummyChannel("chan", ChannelCapabilities())])
    request = handler._build_request(
        procedure_id="proc",
        request_type="approval",
        message="m",
    )

    async def fake_get_first_from_channel(_channel):
        raise asyncio.CancelledError

    monkeypatch.setattr(handler, "_get_first_from_channel", fake_get_first_from_channel)

    response = asyncio.run(handler._wait_for_first_response(request, handler.channels, []))
    assert response is None


def test_get_channel_by_id_returns_none():
    handler = ControlLoopHandler(channels=[])
    assert handler._get_channel_by_id("missing") is None


def test_adapter_check_pending_response_returns_hitl_response():
    from tactus.adapters.control_loop import ControlLoopHITLAdapter

    class DummyHandler:
        def check_pending_response(self, _procedure_id, _message_id):
            return ControlResponse(
                request_id="req",
                value="ok",
                channel_id="chan",
                responded_at=datetime.now(timezone.utc),
            )

        def cancel_pending_request(self, _procedure_id, _message_id):
            return None

    adapter = ControlLoopHITLAdapter(DummyHandler())
    response = adapter.check_pending_response("proc", "msg")
    assert response.value == "ok"


def test_control_loop_adapter_request_interaction_without_optional_methods():
    from tactus.adapters.control_loop import ControlLoopHITLAdapter

    class DummyHandler:
        def __init__(self):
            self.execution_context = None
            self.calls = []

        def request_interaction(self, **kwargs):
            self.calls.append(kwargs)
            return ControlResponse(request_id="req", value="ok", channel_id="chan")

    class MinimalCtx:
        procedure_name = "Proc"
        invocation_id = "inv"

    handler = DummyHandler()
    adapter = ControlLoopHITLAdapter(handler, execution_context=MinimalCtx())

    response = adapter.request_interaction(
        "proc-1",
        {"request_type": "input", "message": "m", "metadata": {}},
    )

    assert response.value == "ok"
