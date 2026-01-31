import pytest

from tactus.core import runtime as runtime_module
from tactus.core.lua_sandbox import LuaSandboxError


class DummyLuaSandbox:
    def __init__(self):
        self.executed = []

    def execute(self, code):
        self.executed.append(code)
        return {"ran": True}


class DummyCallable:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    def __call__(self, params):
        self.calls.append(params)
        if self._error:
            raise self._error
        return self._result


class DummyLuaTable:
    def items(self):
        return [("a", 1)]


class DummyExecutionContext:
    def __init__(self):
        self.metadata = []

    def set_procedure_metadata(self, procedure_name=None, input_data=None):
        self.metadata.append((procedure_name, input_data))


def test_execute_workflow_named_main(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.execution_context = DummyExecutionContext()
    runtime.lua_sandbox = object()
    runtime.context = {"x": 1}

    main_callable = DummyCallable(result=DummyLuaTable())

    def fake_callable(**_kwargs):
        return main_callable

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable",
        lambda **_kwargs: fake_callable(),
    )
    monkeypatch.setattr(runtime_module, "lua_table_to_dict", lambda _obj: {"a": 1})

    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "main": {
                    "function": lambda _params: None,
                    "input_schema": {"x": {"default": 2}, "y": {"default": 3}},
                    "output_schema": {},
                    "state_schema": {},
                    "name": "main",
                }
            }
        },
    )()

    result = runtime._execute_workflow()

    assert result == {"a": 1}
    assert main_callable.calls == [{"x": 1, "y": 3}]


def test_execute_workflow_named_main_without_execution_context(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.execution_context = None
    runtime.lua_sandbox = object()
    runtime.context = {}

    main_callable = DummyCallable(result={"ok": True})

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable",
        lambda **_kwargs: main_callable,
    )

    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "main": {
                    "function": lambda _params: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                    "name": "main",
                }
            }
        },
    )()

    assert runtime._execute_workflow() == {"ok": True}


def test_execute_workflow_named_main_error(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.execution_context = object()
    runtime.lua_sandbox = object()

    main_callable = DummyCallable(error=ValueError("boom"))

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable",
        lambda **_kwargs: main_callable,
    )

    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "main": {
                    "function": lambda _params: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                    "name": "main",
                }
            }
        },
    )()

    with pytest.raises(LuaSandboxError):
        runtime._execute_workflow()


def test_execute_workflow_named_main_waits(monkeypatch):
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.execution_context = DummyExecutionContext()
    runtime.lua_sandbox = object()

    main_callable = DummyCallable(
        error=runtime_module.ProcedureWaitingForHuman("wait", pending_message_id="msg-1")
    )

    monkeypatch.setattr(
        "tactus.primitives.procedure_callable.ProcedureCallable",
        lambda **_kwargs: main_callable,
    )

    runtime.registry = type(
        "Registry",
        (),
        {
            "named_procedures": {
                "main": {
                    "function": lambda _params: None,
                    "input_schema": {},
                    "output_schema": {},
                    "state_schema": {},
                    "name": "main",
                }
            }
        },
    )()

    with pytest.raises(runtime_module.ProcedureWaitingForHuman):
        runtime._execute_workflow()


def test_execute_workflow_top_level_result():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = type("Registry", (), {"named_procedures": {}})()
    runtime._top_level_result = {"ok": True}

    assert runtime._execute_workflow() == {"ok": True}


def test_execute_workflow_missing_main_raises():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = type("Registry", (), {"named_procedures": {}})()

    with pytest.raises(RuntimeError):
        runtime._execute_workflow()


def test_execute_workflow_legacy_yaml():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = None
    runtime.config = {"procedure": "print('hi')"}
    runtime.lua_sandbox = DummyLuaSandbox()

    result = runtime._execute_workflow()

    assert result == {"ran": True}


def test_execute_workflow_legacy_yaml_errors():
    runtime = runtime_module.TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.registry = None
    runtime.config = {"procedure": "print('hi')"}

    class ErrorSandbox:
        def execute(self, _code):
            raise LuaSandboxError("boom")

    runtime.lua_sandbox = ErrorSandbox()

    with pytest.raises(LuaSandboxError):
        runtime._execute_workflow()
