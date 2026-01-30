import asyncio
import threading
from datetime import datetime, timezone

import pytest

from tactus.adapters.channels.host import HostControlChannel
from tactus.protocols.control import ControlRequest, ControlRequestType


class DummyHostChannel(HostControlChannel):
    def __init__(self):
        super().__init__()
        self.displayed = False
        self.cancelled_reason = None

    @property
    def channel_id(self) -> str:
        return "dummy"

    def _display_request(self, request):
        self.displayed = True

    def _prompt_for_input(self, request):
        return "ok"

    def _show_cancelled(self, reason: str) -> None:
        self.cancelled_reason = reason


class ErrorHostChannel(DummyHostChannel):
    def _prompt_for_input(self, request):
        raise RuntimeError("boom")


class NoneHostChannel(DummyHostChannel):
    def _prompt_for_input(self, request):
        return None


def _make_request():
    return ControlRequest(
        request_id="req",
        procedure_id="proc",
        procedure_name="name",
        invocation_id="inv",
        started_at=datetime.now(timezone.utc),
        request_type=ControlRequestType.INPUT,
        message="Need input",
    )


@pytest.mark.asyncio
async def test_send_pushes_response():
    channel = DummyHostChannel()
    result = await channel.send(_make_request())
    assert result.success is True
    response = await asyncio.wait_for(channel._response_queue.get(), timeout=1.0)
    assert response.value == "ok"
    assert channel.displayed is True


def test_capabilities_defaults():
    channel = DummyHostChannel()
    caps = channel.capabilities
    assert caps.supports_input is True
    assert caps.is_synchronous is True


@pytest.mark.asyncio
async def test_cancel_sets_reason():
    channel = DummyHostChannel()
    await channel.cancel("req", "Responded elsewhere")
    assert channel.cancelled_reason == "Responded elsewhere"


@pytest.mark.asyncio
async def test_shutdown_cancels_thread():
    channel = DummyHostChannel()
    await channel.send(_make_request())
    await channel.shutdown()
    assert channel._cancel_event.is_set() is True


@pytest.mark.asyncio
async def test_shutdown_joins_input_thread():
    channel = DummyHostChannel()
    stop_event = threading.Event()

    def run():
        stop_event.wait()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    channel._input_thread = thread

    await channel.shutdown()
    stop_event.set()


@pytest.mark.asyncio
async def test_shutdown_skips_join_when_thread_not_alive():
    channel = DummyHostChannel()

    class DummyThread:
        def __init__(self):
            self.join_called = False

        def is_alive(self):
            return False

        def join(self, timeout=None):
            self.join_called = True

    thread = DummyThread()
    channel._input_thread = thread

    await channel.shutdown()

    assert thread.join_called is False


def test_input_thread_skips_response_when_cancelled():
    channel = DummyHostChannel()
    channel._current_request = _make_request()
    channel._cancel_event.set()
    channel._input_thread_main(channel._current_request)
    assert channel._response_queue.empty() is True


def test_input_thread_pushes_response_without_event_loop():
    channel = DummyHostChannel()
    request = _make_request()
    channel._event_loop = None
    channel._input_thread_main(request)
    response = channel._response_queue.get_nowait()
    assert response.value == "ok"


def test_input_thread_logs_error_when_prompt_fails():
    channel = ErrorHostChannel()
    channel._current_request = _make_request()
    channel._input_thread_main(channel._current_request)
    assert channel._response_queue.empty() is True


def test_input_thread_skips_response_when_none_returned():
    channel = NoneHostChannel()
    channel._current_request = _make_request()
    channel._input_thread_main(channel._current_request)
    assert channel._response_queue.empty() is True


def test_input_thread_error_skips_logging_when_cancelled():
    channel = ErrorHostChannel()
    channel._current_request = _make_request()
    channel._cancel_event.set()
    channel._input_thread_main(channel._current_request)
    assert channel._response_queue.empty() is True


def test_is_cancelled_reports_event():
    channel = DummyHostChannel()
    channel._cancel_event.set()
    assert channel.is_cancelled() is True
