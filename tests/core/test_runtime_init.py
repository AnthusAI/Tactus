from tactus.core.runtime import TactusRuntime


def test_runtime_init_uses_provided_hitl_handler(monkeypatch):
    sentinel = object()

    def boom(*_args, **_kwargs):
        raise AssertionError("load_default_channels should not be called")

    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", boom)

    runtime = TactusRuntime(procedure_id="proc", hitl_handler=sentinel)

    assert runtime.hitl_handler is sentinel


def test_runtime_init_auto_configures_control_loop(monkeypatch):
    class DummyHandler:
        def __init__(self, channels, storage):
            self.channels = channels
            self.storage = storage

    class DummyAdapter:
        def __init__(self, handler):
            self.handler = handler

    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda **_kw: ["chan"])
    monkeypatch.setattr("tactus.adapters.control_loop.ControlLoopHandler", DummyHandler)
    monkeypatch.setattr("tactus.adapters.control_loop.ControlLoopHITLAdapter", DummyAdapter)

    runtime = TactusRuntime(procedure_id="proc")

    assert isinstance(runtime.hitl_handler, DummyAdapter)
    assert isinstance(runtime.hitl_handler.handler, DummyHandler)
    assert runtime.hitl_handler.handler.channels == ["chan"]


def test_runtime_init_skips_when_no_channels(monkeypatch):
    monkeypatch.setattr("tactus.adapters.channels.load_default_channels", lambda **_kw: [])

    runtime = TactusRuntime(procedure_id="proc")

    assert runtime.hitl_handler is None
