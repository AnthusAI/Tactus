import io

import pytest

from tactus.sandbox import entrypoint
from tactus.sandbox.protocol import ExecutionResult, ExecutionStatus


def test_read_request_from_stdin_empty(monkeypatch):
    monkeypatch.setattr(entrypoint.sys, "stdin", io.StringIO(""))
    assert entrypoint.read_request_from_stdin() is None


def test_read_request_from_stdin_invalid(monkeypatch):
    monkeypatch.setattr(entrypoint.sys, "stdin", io.StringIO("{bad json}\n"))
    assert entrypoint.read_request_from_stdin() is None


def test_read_request_from_stdin_valid(monkeypatch):
    monkeypatch.setattr(entrypoint.sys, "stdin", io.StringIO('{"execution_id":"1"}\n'))
    assert entrypoint.read_request_from_stdin() == {"execution_id": "1"}


def test_write_result_to_stdout(monkeypatch):
    buffer = io.StringIO()
    monkeypatch.setattr(entrypoint.sys, "stdout", buffer)
    result = ExecutionResult(status=ExecutionStatus.SUCCESS, result={"ok": True})
    entrypoint.write_result_to_stdout(result)
    output = buffer.getvalue()
    assert "<<<TACTUS_RESULT_START>>>" in output
    assert "<<<TACTUS_RESULT_END>>>" in output


def test_entrypoint_log_level_branches(monkeypatch):
    import importlib

    monkeypatch.setenv("TACTUS_LOG_LEVEL", "debug")
    import tactus.sandbox.entrypoint as entrypoint_mod

    importlib.reload(entrypoint_mod)

    monkeypatch.setenv("TACTUS_LOG_LEVEL", "info")
    importlib.reload(entrypoint_mod)


@pytest.mark.asyncio
async def test_execute_procedure_uses_log_handler(monkeypatch):
    class FakeRuntime:
        def __init__(self, **kwargs):
            self.log_handler = kwargs.get("log_handler")

        async def execute(self, source, context, format):
            return {"result": "ok"}

    class FakeLogHandler:
        def __init__(self):
            self.flushed = False

        async def flush(self):
            self.flushed = True

    monkeypatch.setattr("tactus.core.TactusRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        "tactus.adapters.http_callback_log.HTTPCallbackLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.broker_log.BrokerLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.cost_collector_log.CostCollectorLogHandler",
        FakeLogHandler,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.broker.BrokerControlChannel.from_environment",
        classmethod(lambda cls: None),
        raising=False,
    )

    result = await entrypoint.execute_procedure("print('hi')", params={}, format="lua")
    assert result == {"result": "ok"}


@pytest.mark.asyncio
async def test_execute_procedure_skips_flush_without_method(monkeypatch):
    class FakeRuntime:
        def __init__(self, **_kwargs):
            pass

        async def execute(self, source, context, format):
            return {"result": "ok"}

    class FakeLogHandler:
        pass

    monkeypatch.setattr("tactus.core.TactusRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        "tactus.adapters.http_callback_log.HTTPCallbackLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.broker_log.BrokerLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.cost_collector_log.CostCollectorLogHandler",
        FakeLogHandler,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.broker.BrokerControlChannel.from_environment",
        classmethod(lambda cls: None),
        raising=False,
    )

    result = await entrypoint.execute_procedure("print('hi')", params={}, format="lua")
    assert result == {"result": "ok"}


@pytest.mark.asyncio
async def test_execute_procedure_prefers_http_callback(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, **kwargs):
            captured["log_handler"] = kwargs.get("log_handler")
            captured["hitl_handler"] = kwargs.get("hitl_handler")

        async def execute(self, source, context, format):
            return {"result": "ok"}

    class FakeLogHandler:
        async def flush(self):
            return None

    monkeypatch.setattr("tactus.core.TactusRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        "tactus.adapters.http_callback_log.HTTPCallbackLogHandler.from_environment",
        lambda: FakeLogHandler(),
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.broker_log.BrokerLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.broker.BrokerControlChannel.from_environment",
        classmethod(lambda cls: None),
        raising=False,
    )

    result = await entrypoint.execute_procedure("print('hi')", params={}, format="lua")
    assert result == {"result": "ok"}
    assert isinstance(captured["log_handler"], FakeLogHandler)
    assert captured["hitl_handler"] is None


@pytest.mark.asyncio
async def test_execute_procedure_uses_broker_log_handler(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, **kwargs):
            captured["log_handler"] = kwargs.get("log_handler")

        async def execute(self, source, context, format):
            return {"result": "ok"}

    class FakeLogHandler:
        async def flush(self):
            return None

    monkeypatch.setattr("tactus.core.TactusRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        "tactus.adapters.http_callback_log.HTTPCallbackLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.broker_log.BrokerLogHandler.from_environment",
        lambda: FakeLogHandler(),
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.broker.BrokerControlChannel.from_environment",
        classmethod(lambda cls: None),
        raising=False,
    )

    result = await entrypoint.execute_procedure("print('hi')", params={}, format="lua")
    assert result == {"result": "ok"}
    assert isinstance(captured["log_handler"], FakeLogHandler)


@pytest.mark.asyncio
async def test_execute_procedure_sets_hitl_handler(monkeypatch):
    captured = {}

    class FakeRuntime:
        def __init__(self, **kwargs):
            captured["hitl_handler"] = kwargs.get("hitl_handler")

        async def execute(self, source, context, format):
            return {"result": "ok"}

    class FakeChannel:
        pass

    class FakeControlLoopHandler:
        def __init__(self, channels):
            self.channels = channels

    class FakeHITLAdapter:
        def __init__(self, handler):
            self.handler = handler

    class FakeCostHandler:
        async def flush(self):
            return None

    monkeypatch.setattr("tactus.core.TactusRuntime", FakeRuntime, raising=False)
    monkeypatch.setattr(
        "tactus.adapters.http_callback_log.HTTPCallbackLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.broker_log.BrokerLogHandler.from_environment",
        lambda: None,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.cost_collector_log.CostCollectorLogHandler",
        FakeCostHandler,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.channels.broker.BrokerControlChannel.from_environment",
        classmethod(lambda cls: FakeChannel()),
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.control_loop.ControlLoopHandler",
        FakeControlLoopHandler,
        raising=False,
    )
    monkeypatch.setattr(
        "tactus.adapters.control_loop.ControlLoopHITLAdapter",
        FakeHITLAdapter,
        raising=False,
    )

    result = await entrypoint.execute_procedure("print('hi')", params={}, format="lua")
    assert result == {"result": "ok"}
    assert isinstance(captured["hitl_handler"], FakeHITLAdapter)


@pytest.mark.asyncio
async def test_main_async_handles_execution_error(monkeypatch):
    captured = {}

    def fake_write(result):
        captured["status"] = result.status
        captured["error"] = result.error

    monkeypatch.setattr(
        entrypoint,
        "read_request_from_stdin",
        lambda: {"execution_id": "1", "source": "print('hi')", "params": {}, "format": "lua"},
    )
    monkeypatch.setattr(entrypoint, "write_result_to_stdout", fake_write)

    async def fake_execute(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(entrypoint, "execute_procedure", fake_execute)

    code = await entrypoint.main_async()
    assert code == 1
    assert captured["status"] == ExecutionStatus.ERROR
    assert "boom" in captured["error"]


@pytest.mark.asyncio
async def test_main_async_success_writes_result(monkeypatch):
    captured = {}

    def fake_write(result):
        captured["status"] = result.status
        captured["result"] = result.result

    monkeypatch.setattr(
        entrypoint,
        "read_request_from_stdin",
        lambda: {"execution_id": "1", "source": "print('hi')", "params": {}, "format": "lua"},
    )
    monkeypatch.setattr(entrypoint, "write_result_to_stdout", fake_write)

    async def fake_execute(*_args, **_kwargs):
        return {"ok": True}

    monkeypatch.setattr(entrypoint, "execute_procedure", fake_execute)

    async def fake_close():
        captured["closed"] = True

    monkeypatch.setattr("tactus.broker.client.close_stdio_transport", fake_close, raising=False)

    code = await entrypoint.main_async()
    assert code == 0
    assert captured["status"] == ExecutionStatus.SUCCESS
    assert captured["result"] == {"ok": True}
    assert captured["closed"] is True


@pytest.mark.asyncio
async def test_main_async_close_transport_failure(monkeypatch):
    monkeypatch.setattr(
        entrypoint,
        "read_request_from_stdin",
        lambda: {"execution_id": "1", "source": "print('hi')", "params": {}, "format": "lua"},
    )
    monkeypatch.setattr(entrypoint, "write_result_to_stdout", lambda _result: None)

    async def fake_execute(*_args, **_kwargs):
        return {"ok": True}

    async def boom_close():
        raise RuntimeError("close-fail")

    monkeypatch.setattr(entrypoint, "execute_procedure", fake_execute)
    monkeypatch.setattr("tactus.broker.client.close_stdio_transport", boom_close, raising=False)

    code = await entrypoint.main_async()
    assert code == 0


def test_main_handles_keyboard_interrupt(monkeypatch):
    def raise_keyboard():
        raise KeyboardInterrupt

    monkeypatch.setattr(entrypoint, "main_async", raise_keyboard)

    assert entrypoint.main() == 130


@pytest.mark.asyncio
async def test_main_async_handles_missing_input(monkeypatch):
    captured = {}

    def fake_write(result):
        captured["status"] = result.status
        captured["error"] = result.error

    monkeypatch.setattr(entrypoint, "read_request_from_stdin", lambda: None)
    monkeypatch.setattr(entrypoint, "write_result_to_stdout", fake_write)

    code = await entrypoint.main_async()
    assert code == 1
    assert captured["status"] == ExecutionStatus.ERROR
