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
