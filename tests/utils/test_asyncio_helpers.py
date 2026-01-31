import asyncio

from tactus.utils.asyncio_helpers import clear_closed_event_loop


def test_clear_closed_event_loop_ignores_missing_event_loop(monkeypatch):
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError()))

    clear_closed_event_loop()


def test_clear_closed_event_loop_resets_closed_loop():
    event_loop = asyncio.new_event_loop()
    event_loop.close()
    asyncio.set_event_loop(event_loop)

    clear_closed_event_loop()
    current_loop = asyncio.get_event_loop()
    assert current_loop is not event_loop
    assert not current_loop.is_closed()

    current_loop.close()
    asyncio.set_event_loop(None)


def test_clear_closed_event_loop_keeps_open_loop():
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    clear_closed_event_loop()

    assert asyncio.get_event_loop() is event_loop

    event_loop.close()
    asyncio.set_event_loop(None)


def test_clear_closed_event_loop_handles_loop_without_is_closed(monkeypatch):
    class LoopWithoutIsClosed:
        pass

    loop_instance = LoopWithoutIsClosed()
    monkeypatch.setattr(asyncio, "get_event_loop", lambda: loop_instance)
    monkeypatch.setattr(
        asyncio,
        "set_event_loop",
        lambda _loop: (_ for _ in ()).throw(AssertionError("set_event_loop should not run")),
    )

    clear_closed_event_loop()
