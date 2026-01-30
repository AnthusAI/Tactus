import builtins
import io

import pytest

from tactus.primitives.procedure_callable import ProcedureCallable


class DummyLua:
    def __init__(self, globals_table=None):
        self._globals = globals_table or {"state": {}}

    def table(self):
        return {}

    def globals(self):
        return self._globals


class DummyLuaSandbox:
    def __init__(self, globals_table=None):
        self.lua = DummyLua(globals_table=globals_table)


class DummyExecutionContext:
    def __init__(self, current_tac_file=None):
        self.current_tac_file = current_tac_file
        self.checkpoint_calls = []

    def checkpoint(self, func, checkpoint_type=None, source_info=None):
        self.checkpoint_calls.append(
            {"checkpoint_type": checkpoint_type, "source_info": source_info}
        )
        return func()


class DummyLuaTable:
    def __init__(self, items=None):
        self._items = items or {}

    def items(self):
        return self._items.items()


@pytest.fixture
def quiet_debug_log(monkeypatch):
    def _noop_open(*_args, **_kwargs):
        return io.StringIO()

    monkeypatch.setattr(builtins, "open", _noop_open)


def test_call_applies_state_defaults_and_converts_inputs(quiet_debug_log):
    captured = {}

    def procedure_function(params):
        captured["params"] = params
        return {"ok": True}

    sandbox = DummyLuaSandbox()
    execution_context = DummyExecutionContext(current_tac_file="flow.tac")
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={"count": {"default": 2}},
        execution_context=execution_context,
        lua_sandbox=sandbox,
        is_main=True,
    )

    result = callable_proc({"items": [1, 2]})

    assert result == {"ok": True}
    assert sandbox.lua.globals()["state"]["count"] == 2
    assert captured["params"]["items"][1] == 1
    assert captured["params"]["items"][2] == 2


def test_call_converts_empty_list_to_dict(quiet_debug_log):
    def procedure_function(params):
        return {"ok": params == {}}

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc([]) == {"ok": True}


def test_call_converts_empty_lua_table_to_dict(quiet_debug_log, monkeypatch):
    def procedure_function(params):
        return {"ok": params == {}}

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", lambda _t: [])

    assert callable_proc(DummyLuaTable({})) == {"ok": True}


def test_call_with_list_input_missing_required_raises(quiet_debug_log):
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={"required": {"required": True}},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    with pytest.raises(ValueError, match="requires input parameters"):
        callable_proc([1, 2, 3])


def test_call_uses_checkpoint_for_subprocedures(quiet_debug_log):
    def procedure_function(_params):
        return {"done": True}

    execution_context = DummyExecutionContext(current_tac_file="scene.tac")
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"done": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=DummyLuaSandbox(),
        is_main=False,
    )

    result = callable_proc({"value": 1})

    assert result == {"done": True}
    assert execution_context.checkpoint_calls
    source_info = execution_context.checkpoint_calls[0]["source_info"]
    assert source_info["file"] == "scene.tac"
    assert source_info["function"] == "helper"


def test_call_converts_lua_result_table(quiet_debug_log, monkeypatch):
    def procedure_function(_params):
        return DummyLuaTable({"ok": True})

    def fake_lua_table_to_dict(table):
        return dict(table.items())

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", fake_lua_table_to_dict)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc({}) == {"ok": True}


def test_call_converts_lua_input_table(quiet_debug_log, monkeypatch):
    captured = {}

    def procedure_function(params):
        captured["params"] = params
        return {"ok": True}

    def fake_lua_table_to_dict(table):
        return dict(table.items())

    monkeypatch.setattr("tactus.core.dsl_stubs.lua_table_to_dict", fake_lua_table_to_dict)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=procedure_function,
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    lua_params = DummyLuaTable({"x": 1})
    assert callable_proc(lua_params) == {"ok": True}
    assert captured["params"] == {"x": 1}


def test_validate_input_missing_required():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={"x": {"type": "number", "required": True, "description": "Value"}},
        output_schema={},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    with pytest.raises(ValueError, match="requires input parameters"):
        callable_proc({})


@pytest.mark.parametrize(
    "output_schema,result",
    [
        ({"type": "string", "required": True}, 1),
        ({"type": "number", "required": True}, "x"),
        ({"type": "boolean", "required": True}, "true"),
        ({"type": "object", "required": True}, ["x"]),
        ({"type": "array", "required": True}, {"x": 1}),
    ],
)
def test_validate_output_scalar_types(output_schema, result):
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: result,
        input_schema={},
        output_schema=output_schema,
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    with pytest.raises(ValueError, match="must return"):
        callable_proc({})


def test_validate_output_missing_required():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"value": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    with pytest.raises(ValueError, match="missing required output"):
        callable_proc({})


def test_validate_output_scalar_optional_allows_none():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: None,
        input_schema={},
        output_schema={"type": "string", "required": False},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc({}) is None


def test_validate_output_scalar_success():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: "ok",
        input_schema={},
        output_schema={"type": "string", "required": True},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc({}) == "ok"


def test_validate_output_non_scalar_schema_uses_dict(quiet_debug_log):
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"type": "custom"},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc({}) == {"ok": True}


def test_validate_output_non_dict_raises():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: "bad",
        input_schema={},
        output_schema={"value": {"required": True}},
        state_schema={},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    with pytest.raises(ValueError, match="must return dict"):
        callable_proc({})


def test_initialize_state_skips_non_default():
    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={"count": {"default": 2}, "note": {"type": "string"}},
        execution_context=DummyExecutionContext(current_tac_file="flow.tac"),
        lua_sandbox=DummyLuaSandbox(),
        is_main=True,
    )

    assert callable_proc._initialize_state() == {"count": 2}


def test_call_subprocedure_uses_lua_debug_info(quiet_debug_log):
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
                return DebugInfo({"source": "helper.tac", "currentline": 5, "name": "caller"})
            return None

    class Globals:
        def __init__(self, debug):
            self._store = {"state": {}}
            self.debug = debug

        def __getitem__(self, key):
            return self._store[key]

    class LuaWithDebug(DummyLua):
        def __init__(self, debug):
            self._globals = Globals(debug)

        def globals(self):
            return self._globals

    class SandboxWithDebug:
        def __init__(self, debug):
            self.lua = LuaWithDebug(debug)

    sandbox = SandboxWithDebug(Debug())
    execution_context = DummyExecutionContext(current_tac_file="flow.tac")

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=sandbox,
        is_main=False,
    )

    assert callable_proc({"x": 1}) == {"ok": True}
    source_info = execution_context.checkpoint_calls[0]["source_info"]
    assert source_info["file"] == "flow.tac"
    assert source_info["line"] == 5


def test_call_subprocedure_handles_debug_errors(quiet_debug_log):
    class Debug:
        def getinfo(self, _level, _spec):
            raise RuntimeError("boom")

    sandbox = DummyLuaSandbox({"state": {}, "debug": Debug()})
    execution_context = DummyExecutionContext(current_tac_file=None)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=sandbox,
        is_main=False,
    )

    assert callable_proc({"x": 1}) == {"ok": True}
    assert execution_context.checkpoint_calls


def test_call_subprocedure_handles_debug_level_errors(quiet_debug_log):
    class Debug:
        def getinfo(self, level, _spec):
            if level == 1:
                raise RuntimeError("boom")
            return None

    class Globals:
        def __init__(self, debug):
            self._store = {"state": {}}
            self.debug = debug

        def __getitem__(self, key):
            return self._store[key]

    class LuaWithDebug(DummyLua):
        def __init__(self, debug):
            self._globals = Globals(debug)

        def globals(self):
            return self._globals

    class SandboxWithDebug:
        def __init__(self, debug):
            self.lua = LuaWithDebug(debug)

    sandbox = SandboxWithDebug(Debug())
    execution_context = DummyExecutionContext(current_tac_file=None)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=sandbox,
        is_main=False,
    )

    assert callable_proc({"x": 1}) == {"ok": True}


def test_call_subprocedure_handles_globals_failure(quiet_debug_log):
    class LuaWithFailingGlobals(DummyLua):
        def globals(self):
            raise RuntimeError("no globals")

    class SandboxWithFailingGlobals:
        def __init__(self):
            self.lua = LuaWithFailingGlobals()

    sandbox = SandboxWithFailingGlobals()
    execution_context = DummyExecutionContext(current_tac_file=None)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=sandbox,
        is_main=False,
    )

    assert callable_proc({"x": 1}) == {"ok": True}


def test_call_subprocedure_fallback_without_frame(quiet_debug_log, monkeypatch):
    execution_context = DummyExecutionContext(current_tac_file=None)

    callable_proc = ProcedureCallable(
        name="helper",
        procedure_function=lambda _params: {"ok": True},
        input_schema={},
        output_schema={"ok": {"required": True}},
        state_schema={},
        execution_context=execution_context,
        lua_sandbox=DummyLuaSandbox(),
        is_main=False,
    )

    def fake_currentframe():
        class Frame:
            f_back = None

        return Frame()

    monkeypatch.setattr("inspect.currentframe", fake_currentframe)
    assert callable_proc({"x": 1}) == {"ok": True}
    assert execution_context.checkpoint_calls[0]["source_info"] is None
