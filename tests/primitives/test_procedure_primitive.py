from types import SimpleNamespace
from pathlib import Path
import threading
import time

import pytest

from tactus.primitives.procedure import (
    ProcedurePrimitive,
    ProcedureExecutionError,
    ProcedureRecursionError,
    ProcedureHandle,
)


class FakeRuntime:
    def __init__(self, result):
        self._result = result

    async def execute(self, source, context, format):
        return self._result


class ErrorRuntime:
    async def execute(self, source, context, format):
        raise RuntimeError("boom")


class FakeExecutionContext:
    def __init__(self):
        self.calls = []
        self.current_tac_file = None

    def checkpoint(self, fn, checkpoint_type, source_info=None):
        self.calls.append((checkpoint_type, source_info))
        return fn()


def test_call_requires_lua_sandbox():
    primitive = ProcedurePrimitive(FakeExecutionContext(), runtime_factory=lambda n, p: None)
    with pytest.raises(ProcedureExecutionError, match="lua_sandbox missing"):
        primitive("missing")

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: {}))
    primitive = ProcedurePrimitive(
        FakeExecutionContext(), runtime_factory=lambda n, p: None, lua_sandbox=sandbox
    )
    with pytest.raises(ProcedureExecutionError, match="not found"):
        primitive("missing")


def test_call_returns_named_procedure():
    proc = object()
    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: {"proc": proc}))
    primitive = ProcedurePrimitive(
        FakeExecutionContext(), runtime_factory=lambda n, p: None, lua_sandbox=sandbox
    )
    assert primitive("proc") is proc


def test_run_success_and_failure(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return FakeRuntime({"success": True, "result": 5})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")
    assert primitive.run("child", {"x": 1}) == 5

    def failing_factory(name, params):
        return FakeRuntime({"success": False, "error": "bad"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=failing_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")
    with pytest.raises(ProcedureExecutionError, match="bad"):
        primitive.run("child", {})


def test_run_converts_lua_params(monkeypatch):
    execution_context = FakeExecutionContext()
    captured = {}

    def runtime_factory(name, params):
        captured["params"] = params
        return FakeRuntime({"success": True, "result": "ok"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    class FakeLuaTable:
        def items(self):
            return [("x", 1)]

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", lambda _t: [])
    assert primitive.run("child", FakeLuaTable()) == "ok"
    assert captured["params"] == {}


def test_run_with_list_params_skips_conversion(monkeypatch):
    execution_context = FakeExecutionContext()
    captured = {}

    def runtime_factory(name, params):
        captured["params"] = params
        return FakeRuntime({"success": True, "result": "ok"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", [1, 2]) == "ok"
    assert captured["params"] == [1, 2]


@pytest.mark.asyncio
async def test_run_threaded_loop_error_propagates(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return ErrorRuntime()

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    with pytest.raises(ProcedureExecutionError, match="Failed to execute procedure"):
        primitive.run("child", {})


def test_run_recursion_limit():
    primitive = ProcedurePrimitive(
        FakeExecutionContext(), runtime_factory=lambda n, p: None, max_depth=1, current_depth=1
    )
    with pytest.raises(ProcedureRecursionError, match="Maximum recursion depth"):
        primitive.run("child", {})


def test_run_propagates_recursion_error(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        raise ProcedureRecursionError("too deep")

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    with pytest.raises(ProcedureRecursionError, match="too deep"):
        primitive.run("child", {})


def test_spawn_wait_and_status(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return FakeRuntime({"success": True, "result": "ok"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    handle = primitive.spawn("child", {})
    result = primitive.wait(handle, timeout=2.0)
    assert result == "ok"
    status = primitive.status(handle)
    assert status["status"] == "completed"

    handle2 = primitive.spawn("child", {})
    primitive.wait(handle2)
    assert primitive.wait_any([handle2]) == handle2
    assert primitive.wait_all([handle, handle2]) == ["ok", "ok"]

    primitive.cancel(handle2)
    assert primitive.is_complete(handle2) is True
    assert primitive.all_complete([handle, handle2]) is True


@pytest.mark.asyncio
async def test_run_uses_threaded_loop_when_running(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return FakeRuntime({"success": True, "result": "ok"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"


def test_wait_timeout_raises():
    execution_context = FakeExecutionContext()
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    handle = ProcedureHandle(procedure_id="id", name="child", status="running")
    handle.thread = threading.Thread(target=time.sleep, args=(1.0,), daemon=True)
    handle.thread.start()

    with pytest.raises(TimeoutError):
        primitive.wait(handle, timeout=0.01)


def test_wait_unexpected_state_raises():
    execution_context = FakeExecutionContext()
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    handle = ProcedureHandle(procedure_id="id", name="child", status="waiting")

    with pytest.raises(ProcedureExecutionError, match="unexpected state"):
        primitive.wait(handle)


def test_wait_failed_state_raises():
    execution_context = FakeExecutionContext()
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    handle = ProcedureHandle(procedure_id="id", name="child", status="failed", error="bad")

    with pytest.raises(ProcedureExecutionError, match="failed"):
        primitive.wait(handle)


def test_spawn_recursion_limit_raises():
    primitive = ProcedurePrimitive(
        FakeExecutionContext(), runtime_factory=lambda n, p: None, max_depth=1, current_depth=1
    )
    with pytest.raises(ProcedureRecursionError, match="Maximum recursion depth"):
        primitive.spawn("child", {})


def test_inject_logs_warning(caplog):
    primitive = ProcedurePrimitive(FakeExecutionContext(), runtime_factory=lambda n, p: None)
    handle = ProcedureHandle(procedure_id="id", name="child")
    with caplog.at_level("WARNING", logger="tactus.primitives.procedure"):
        primitive.inject(handle, "note")
    assert any("Procedure.inject() not fully implemented" in rec.message for rec in caplog.records)


def test_wait_any_waits_until_completion(monkeypatch):
    primitive = ProcedurePrimitive(FakeExecutionContext(), runtime_factory=lambda n, p: None)
    handle = ProcedureHandle(procedure_id="id", name="child", status="running")

    def fake_sleep(_seconds):
        handle.status = "completed"

    monkeypatch.setattr("time.sleep", fake_sleep)
    assert primitive.wait_any([handle]) == handle


def test_load_procedure_source_searches_paths(tmp_path):
    execution_context = FakeExecutionContext()
    execution_context.current_tac_file = str(tmp_path / "parent" / "main.tac")
    (tmp_path / "parent").mkdir()

    child_path = tmp_path / "child.tac"
    child_path.write_text("child")

    local_path = tmp_path / "parent" / "local.tac"
    local_path.write_text("local")

    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    assert primitive._load_procedure_source(str(child_path)) == "child"
    assert primitive._load_procedure_source("local") == "local"


def test_run_uses_lua_debug_info(monkeypatch):
    execution_context = FakeExecutionContext()
    execution_context.current_tac_file = "root.tac"

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    class DebugInfo:
        def __init__(self, payload):
            self._payload = payload

        def items(self):
            return self._payload.items()

    class Debug:
        def getinfo(self, level, _spec):
            if level == 1:
                return DebugInfo({"source": "=[C]", "currentline": 1})
            if level == 2:
                return DebugInfo({"source": "child.tac", "currentline": 7, "name": "caller"})
            return None

    class Globals:
        def __init__(self):
            self.debug = Debug()

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: Globals()))

    primitive = ProcedurePrimitive(
        execution_context, runtime_factory=runtime_factory, lua_sandbox=sandbox
    )
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1]["line"] == 7


def test_run_debug_info_failure_falls_back(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    class Debug:
        def getinfo(self, _level, _spec):
            raise RuntimeError("boom")

    class Globals:
        def __init__(self):
            self.debug = Debug()

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: Globals()))

    primitive = ProcedurePrimitive(
        execution_context, runtime_factory=runtime_factory, lua_sandbox=sandbox
    )
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1] is not None


def test_run_debug_info_missing_debug_falls_back(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    class Globals:
        pass

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: Globals()))

    primitive = ProcedurePrimitive(
        execution_context, runtime_factory=runtime_factory, lua_sandbox=sandbox
    )
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1] is not None


def test_run_debug_info_invalid_source_falls_back(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    class DebugInfo:
        def __init__(self, payload):
            self._payload = payload

        def items(self):
            return self._payload.items()

    class Debug:
        def getinfo(self, _level, _spec):
            return DebugInfo({"source": '[string "<python>"]', "currentline": 10})

    class Globals:
        def __init__(self):
            self.debug = Debug()

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: Globals()))

    primitive = ProcedurePrimitive(
        execution_context, runtime_factory=runtime_factory, lua_sandbox=sandbox
    )
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1] is not None


def test_run_debug_info_none_falls_back(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    class Debug:
        def getinfo(self, _level, _spec):
            return None

    class Globals:
        def __init__(self):
            self.debug = Debug()

    sandbox = SimpleNamespace(lua=SimpleNamespace(globals=lambda: Globals()))

    primitive = ProcedurePrimitive(
        execution_context, runtime_factory=runtime_factory, lua_sandbox=sandbox
    )
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1] is not None


def test_run_fallback_source_info_without_frame(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(_name, _params):
        return FakeRuntime({"success": True, "result": "ok"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    def fake_currentframe():
        class Frame:
            f_back = None

        return Frame()

    monkeypatch.setattr("inspect.currentframe", fake_currentframe)

    assert primitive.run("child", {}) == "ok"
    assert execution_context.calls[0][1] is None


def test_load_procedure_source_dedupes_paths(tmp_path, monkeypatch):
    execution_context = FakeExecutionContext()
    (tmp_path / "main").mkdir()
    execution_context.current_tac_file = str(tmp_path / "main" / "main.tac")
    (tmp_path / "proc.tac").write_text("proc")

    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)
    monkeypatch.chdir(tmp_path)

    assert primitive._load_procedure_source("proc") == "proc"


def test_load_procedure_source_skips_normalized_duplicates(tmp_path, monkeypatch):
    execution_context = FakeExecutionContext()
    current_dir = tmp_path / "main"
    current_dir.mkdir()
    execution_context.current_tac_file = str(current_dir / "main.tac")

    target_path = current_dir / "proc"
    target_path.write_text("proc")

    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)
    monkeypatch.chdir(tmp_path)

    def fake_resolve(self):
        return Path("/tmp/same")

    monkeypatch.setattr(Path, "resolve", fake_resolve)

    assert primitive._load_procedure_source("proc") == "proc"


def test_load_procedure_source_handles_read_errors(tmp_path, monkeypatch):
    execution_context = FakeExecutionContext()
    execution_context.current_tac_file = str(tmp_path / "main.tac")
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    bad_path = tmp_path / "bad.tac"
    bad_path.write_text("bad")
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    fallback_path = examples_dir / "bad.tac"
    fallback_path.write_text("ok")

    original_read_text = Path.read_text

    def fake_read_text(self, *args, **kwargs):
        if self.name == "bad.tac" and self.parent.name != "examples":
            raise OSError("boom")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)
    monkeypatch.chdir(tmp_path)

    assert primitive._load_procedure_source("bad") == "ok"


def test_load_procedure_source_uses_examples_fallback(tmp_path, monkeypatch):
    execution_context = FakeExecutionContext()
    execution_context.current_tac_file = None
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    example_path = examples_dir / "demo.tac"
    example_path.write_text("demo")

    monkeypatch.chdir(tmp_path)

    assert primitive._load_procedure_source("demo") == "demo"


def test_load_procedure_source_raises_when_missing(tmp_path):
    execution_context = FakeExecutionContext()
    execution_context.current_tac_file = None
    primitive = ProcedurePrimitive(execution_context, runtime_factory=lambda n, p: None)

    with pytest.raises(FileNotFoundError, match="Searched"):
        primitive._load_procedure_source(str(tmp_path / "missing"))


def test_execute_async_failure_updates_handle(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return FakeRuntime({"success": False, "error": "bad"})

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    handle = ProcedureHandle(procedure_id="id", name="child")
    primitive._execute_async(handle, "child", {})

    assert handle.status == "failed"
    assert handle.error == "bad"


def test_execute_async_exception_updates_handle(monkeypatch):
    execution_context = FakeExecutionContext()

    def runtime_factory(name, params):
        return ErrorRuntime()

    primitive = ProcedurePrimitive(execution_context, runtime_factory=runtime_factory)
    monkeypatch.setattr(primitive, "_load_procedure_source", lambda name: "source")

    handle = ProcedureHandle(procedure_id="id", name="child")
    primitive._execute_async(handle, "child", {})

    assert handle.status == "failed"
    assert "boom" in handle.error
