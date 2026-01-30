import asyncio
import sys

import pytest

from tactus.broker.client import _StdioBrokerTransport
from tactus.broker.stdio import STDIO_REQUEST_PREFIX


class DummyLoop:
    def call_soon_threadsafe(self, func, *args):
        func(*args)


def test_read_loop_puts_events(monkeypatch):
    transport = _StdioBrokerTransport()
    queue = asyncio.Queue()
    transport._pending["req"] = (DummyLoop(), queue)

    lines = iter(
        [
            b"not json\n",
            b'{"id":"req","event":"done"}\n',
            b"",
        ]
    )

    monkeypatch.setattr(sys.stdin.buffer, "readline", lambda: next(lines))

    transport._read_loop()

    event = queue.get_nowait()
    assert event["event"] == "done"


def test_read_loop_ignores_closed_loop(monkeypatch):
    transport = _StdioBrokerTransport()
    queue = asyncio.Queue()

    class ClosedLoop:
        def call_soon_threadsafe(self, *_args, **_kwargs):
            raise RuntimeError("closed")

    transport._pending["req"] = (ClosedLoop(), queue)
    lines = iter([b'{"id":"req","event":"done"}\n', b""])
    monkeypatch.setattr(sys.stdin.buffer, "readline", lambda: next(lines))

    transport._read_loop()

    assert queue.empty()


def test_read_loop_ignores_non_string_id_and_missing_pending(monkeypatch):
    transport = _StdioBrokerTransport()
    lines = iter(
        [
            b'{"id":123,"event":"done"}\n',
            b'{"id":"missing","event":"done"}\n',
            b"",
        ]
    )

    monkeypatch.setattr(sys.stdin.buffer, "readline", lambda: next(lines))

    transport._read_loop()


def test_read_loop_exits_when_stopped(monkeypatch):
    transport = _StdioBrokerTransport()
    transport._stop.set()

    called = {"read": False}

    def fake_readline():
        called["read"] = True
        return b""

    monkeypatch.setattr(sys.stdin.buffer, "readline", fake_readline)

    transport._read_loop()

    assert called["read"] is False


def test_ensure_reader_thread_reuses_active_thread(monkeypatch):
    transport = _StdioBrokerTransport()

    class DummyThread:
        def is_alive(self):
            return True

    transport._reader_thread = DummyThread()
    transport._ensure_reader_thread()

    assert transport._reader_thread is not None


def test_ensure_reader_thread_starts_thread(monkeypatch):
    transport = _StdioBrokerTransport()
    started = {"called": False}

    class DummyThread:
        def __init__(self, *args, **kwargs):
            self._alive = False

        def is_alive(self):
            return self._alive

        def start(self):
            started["called"] = True
            self._alive = True

    monkeypatch.setattr("tactus.broker.client.threading.Thread", DummyThread)

    transport._ensure_reader_thread()

    assert started["called"] is True


@pytest.mark.asyncio
async def test_aclose_handles_join_error(monkeypatch):
    transport = _StdioBrokerTransport()

    class DummyThread:
        def is_alive(self):
            return True

        def join(self, _timeout=None):
            raise RuntimeError("boom")

    transport._reader_thread = DummyThread()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(asyncio, "to_thread", boom)

    await transport.aclose()


@pytest.mark.asyncio
async def test_request_writes_and_yields(monkeypatch):
    transport = _StdioBrokerTransport()
    written = []

    monkeypatch.setattr(transport, "_ensure_reader_thread", lambda: None)
    monkeypatch.setattr(sys.stderr, "write", lambda data: written.append(data))
    monkeypatch.setattr(sys.stderr, "flush", lambda: None)

    async def feed_events():
        await asyncio.sleep(0)
        loop, queue = transport._pending["req"]
        queue.put_nowait({"event": "chunk"})
        queue.put_nowait({"event": "done"})

    async def run_request():
        events = []
        async for event in transport.request("req", "tool.call", {"x": 1}):
            events.append(event)
        return events

    task = asyncio.create_task(feed_events())
    events = await run_request()
    await task

    assert events[0]["event"] == "chunk"
    assert events[-1]["event"] == "done"
    assert any(entry.startswith(STDIO_REQUEST_PREFIX) for entry in written)
    assert "req" not in transport._pending
