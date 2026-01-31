import pytest

from tactus.core import runtime as runtime_module


class DummyLua:
    def __init__(self):
        self.executed = []

    def execute(self, code):
        self.executed.append(code)

    def table(self):
        return {}


class DummyLuaSandbox:
    def __init__(self):
        self.lua = DummyLua()
        self.injected = {}
        self.globals = {}

    def inject_primitive(self, name, value):
        self.injected[name] = value

    def set_global(self, name, value):
        self.globals[name] = value


class DummyStep:
    def checkpoint(self, fn, source_info=None):
        return fn()


def test_inject_primitives_with_input_and_checkpoint():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.context = {"color": "blue", "items": [1, 2], "meta": {"a": 1}}
    runtime.config = {
        "input": {
            "color": {"default": "red", "enum": ["red", "blue"]},
            "items": {"default": []},
            "meta": {"default": {}},
        }
    }

    runtime.state_primitive = object()
    runtime.iterations_primitive = object()
    runtime.stop_primitive = object()
    runtime.tool_primitive = object()
    runtime.toolset_primitive = object()
    runtime.step_primitive = DummyStep()
    runtime.checkpoint_primitive = object()
    runtime.human_primitive = object()
    runtime.log_primitive = object()
    runtime.message_history_primitive = object()
    runtime.json_primitive = object()
    runtime.retry_primitive = object()
    runtime.file_primitive = object()
    runtime.procedure_primitive = object()
    runtime.system_primitive = object()
    runtime.host_primitive = object()

    runtime._inject_primitives()

    assert "input" in runtime.lua_sandbox.globals
    assert "Tool" in runtime.lua_sandbox.injected
    assert "Toolset" in runtime.lua_sandbox.injected
    assert "Checkpoint" in runtime.lua_sandbox.injected
    assert "Human" in runtime.lua_sandbox.injected


def test_inject_primitives_enum_invalid_raises():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.context = {"color": "green"}
    runtime.config = {"input": {"color": {"default": "red", "enum": ["red", "blue"]}}}

    with pytest.raises(ValueError):
        runtime._inject_primitives()


def test_inject_primitives_without_optional_primitives():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.context = {}
    runtime.config = {}
    runtime.state_primitive = None
    runtime.iterations_primitive = None
    runtime.stop_primitive = None
    runtime.tool_primitive = None
    runtime.toolset_primitive = None
    runtime.step_primitive = None
    runtime.checkpoint_primitive = None
    runtime.human_primitive = None
    runtime.log_primitive = None
    runtime.message_history_primitive = None
    runtime.json_primitive = None
    runtime.retry_primitive = None
    runtime.file_primitive = None
    runtime.procedure_primitive = None
    runtime.system_primitive = None
    runtime.host_primitive = None

    runtime._inject_primitives()

    assert "input" not in runtime.lua_sandbox.globals


def test_inject_primitives_skips_enum_when_key_missing():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()

    class WeirdInputConfig:
        def items(self):
            return [("color", {"default": "red", "enum": ["red"]})]

        def keys(self):
            return ["color"]

        def __contains__(self, _key):
            return False

    runtime.context = {}
    runtime.config = {"input": WeirdInputConfig()}
    runtime.state_primitive = None
    runtime.iterations_primitive = None
    runtime.stop_primitive = None
    runtime.tool_primitive = None
    runtime.toolset_primitive = None
    runtime.step_primitive = None
    runtime.checkpoint_primitive = None
    runtime.human_primitive = None
    runtime.log_primitive = None
    runtime.message_history_primitive = None
    runtime.json_primitive = None
    runtime.retry_primitive = None
    runtime.file_primitive = None
    runtime.procedure_primitive = None
    runtime.system_primitive = None
    runtime.host_primitive = None

    runtime._inject_primitives()


def test_inject_primitives_sleep_wrapper_calls_time(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.lua_sandbox = DummyLuaSandbox()
    runtime.context = {}
    runtime.config = {}
    runtime.state_primitive = None
    runtime.iterations_primitive = None
    runtime.stop_primitive = None
    runtime.tool_primitive = None
    runtime.toolset_primitive = None
    runtime.step_primitive = None
    runtime.checkpoint_primitive = None
    runtime.human_primitive = None
    runtime.log_primitive = None
    runtime.message_history_primitive = None
    runtime.json_primitive = None
    runtime.retry_primitive = None
    runtime.file_primitive = None
    runtime.procedure_primitive = None
    runtime.system_primitive = None
    runtime.host_primitive = None

    calls = {}

    def fake_sleep(seconds):
        calls["seconds"] = seconds

    monkeypatch.setattr(runtime_module.time, "sleep", fake_sleep)

    runtime._inject_primitives()
    runtime.lua_sandbox.globals["Sleep"](0)

    assert calls["seconds"] == 0
