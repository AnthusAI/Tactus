"""Tests for broker log handler."""

import asyncio
import queue
import threading
from datetime import datetime


from tactus.adapters.broker_log import BrokerLogHandler
from tactus.protocols.models import LogEvent, CostEvent


class FakeBrokerClient:
    def __init__(self, socket_path, events):
        self.socket_path = socket_path
        self._events = events

    async def emit_event(self, event_dict):
        self._events.append(event_dict)


def test_from_environment_returns_none(monkeypatch):
    monkeypatch.delenv("TACTUS_BROKER_SOCKET", raising=False)
    assert BrokerLogHandler.from_environment() is None


def test_from_environment_returns_handler(monkeypatch):
    monkeypatch.setenv("TACTUS_BROKER_SOCKET", "/tmp/socket")
    handler = BrokerLogHandler.from_environment()

    assert isinstance(handler, BrokerLogHandler)


def test_supports_streaming_property():
    handler = BrokerLogHandler("/tmp/socket")
    assert handler.supports_streaming is True


def test_log_and_flush_sends_events(monkeypatch):
    events = []

    def fake_client_init(self, socket_path):
        self._inner = FakeBrokerClient(socket_path, events)

    async def fake_emit_event(self, event_dict):
        await self._inner.emit_event(event_dict)

    monkeypatch.setattr(
        "tactus.broker.client.BrokerClient.__init__",
        fake_client_init,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.broker.client.BrokerClient.emit_event",
        fake_emit_event,
        raising=False,
    )

    handler = BrokerLogHandler("/tmp/socket")

    event = LogEvent(level="INFO", message="hi")
    handler.log(event)

    cost = CostEvent(
        agent_name="agent",
        model="gpt-4o",
        provider="openai",
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        prompt_cost=0.01,
        completion_cost=0.02,
        total_cost=0.03,
    )
    handler.log(cost)

    asyncio.run(handler.flush())

    assert events
    assert handler.cost_events


def test_log_queue_full_drops_event(monkeypatch):
    handler = BrokerLogHandler("/tmp/socket")

    def raise_full(_item):
        raise queue.Full

    handler._queue.put_nowait = raise_full

    handler.log(LogEvent(level="INFO", message="hi"))


def test_log_appends_z_for_naive_timestamp(monkeypatch):
    handler = BrokerLogHandler("/tmp/socket")
    captured = {}

    def fake_put_nowait(item):
        captured.update(item)

    handler._queue.put_nowait = fake_put_nowait
    handler._ensure_worker_started = lambda: None

    event = LogEvent(level="INFO", message="hi", timestamp=datetime(2024, 1, 1))
    handler.log(event)

    assert captured["timestamp"].endswith("Z")


def test_flush_returns_when_not_started():
    handler = BrokerLogHandler("/tmp/socket")
    asyncio.run(handler.flush())


def test_flush_skips_join_when_no_worker_thread(monkeypatch):
    handler = BrokerLogHandler("/tmp/socket")
    handler._started = True

    class FakeQueue:
        def empty(self):
            return True

    handler._queue = FakeQueue()

    async def no_sleep(_interval):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    asyncio.run(handler.flush())


def test_flush_timeout_and_worker_warning(monkeypatch):
    handler = BrokerLogHandler("/tmp/socket")
    handler._started = True

    class FakeQueue:
        def empty(self):
            return False

        def qsize(self):
            return 1

    class FakeThread:
        def is_alive(self):
            return True

        def join(self, timeout=None):
            return None

    handler._queue = FakeQueue()
    handler._worker_thread = FakeThread()

    async def no_sleep(_interval):
        return None

    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    asyncio.run(handler.flush())


def test_worker_logs_exception_and_ignores_task_done_failure(monkeypatch):
    handler = BrokerLogHandler("/tmp/socket")
    handler._shutdown = threading.Event()

    class FakeQueue:
        def get(self, timeout=None):
            handler._shutdown.set()
            raise RuntimeError("boom")

        def task_done(self):
            raise ValueError("bad task")

    class FakeClient:
        def __init__(self, _socket_path):
            pass

        async def emit_event(self, _event_dict):
            return None

    handler._queue = FakeQueue()

    monkeypatch.setattr("tactus.broker.client.BrokerClient", FakeClient, raising=False)

    handler._worker()
