import importlib
import typing

import pytest

from tactus.primitives.handles import (
    _convert_lua_table,
    AgentHandle,
    ModelHandle,
    AgentLookup,
    ModelLookup,
)


class FakeLuaTable(dict):
    pass


class FakeAgent:
    def __init__(self):
        self.calls = []

    def __call__(self, inputs):
        self.calls.append(inputs)
        return {"response": "ok"}


class FakeModel:
    def __init__(self):
        self.calls = []

    def predict(self, data):
        self.calls.append(data)
        return {"label": "yes"}

    def __call__(self, data):
        self.calls.append(data)
        return {"label": "yes"}


class FakeExecutionContext:
    def __init__(self):
        self.calls = []
        self.lua_sandbox = None

    def checkpoint(self, fn, checkpoint_type, source_info=None):
        self.calls.append((checkpoint_type, source_info))
        return fn()


class DummyLuaInfo:
    def __init__(self, info):
        self._info = info

    def get(self, key, default=None):
        return self._info.get(key, default)


class DummyLua:
    def __init__(self, info):
        self._info = info

    def eval(self, _expr):
        return DummyLuaInfo(self._info)


class DummyLuaSandbox:
    def __init__(self, info):
        self.lua = DummyLua(info)


def test_convert_lua_table_variants():
    assert _convert_lua_table(None) is None
    assert _convert_lua_table("hello") == "hello"

    lua_array = FakeLuaTable({1: "a", 2: "b"})
    assert _convert_lua_table(lua_array) == ["a", "b"]

    lua_dict = FakeLuaTable({"a": FakeLuaTable({1: "x"})})
    assert _convert_lua_table(lua_dict) == {"a": ["x"]}


def test_convert_lua_table_empty_dict():
    lua_table = FakeLuaTable()
    assert _convert_lua_table(lua_table) == {}


def test_convert_lua_table_non_consecutive_int_keys():
    lua_table = FakeLuaTable({1: "a", 3: "b"})
    assert _convert_lua_table(lua_table) == {1: "a", 3: "b"}


def test_convert_lua_table_fallback_returns_value():
    class BadTable:
        def items(self):
            raise TypeError("boom")

    assert _convert_lua_table(BadTable()) is not None


def test_agent_handle_call_and_output():
    handle = AgentHandle("agent")
    with pytest.raises(RuntimeError):
        handle({"message": "hi"})

    agent = FakeAgent()
    handle._set_primitive(agent)
    result = handle("hello")
    assert agent.calls[0] == {"message": "hello"}
    assert handle.output == "ok"
    assert result["response"] == "ok"


def test_agent_handle_with_checkpoint():
    handle = AgentHandle("agent")
    agent = FakeAgent()
    context = FakeExecutionContext()
    handle._set_primitive(agent, execution_context=context)
    handle({"message": "hi"})
    assert context.calls[0][0] == "agent_turn"


def test_agent_handle_with_lua_source_info():
    handle = AgentHandle("agent")
    agent = FakeAgent()
    context = FakeExecutionContext()
    context.lua_sandbox = DummyLuaSandbox({"source": "flow.tac", "currentline": 12})
    handle._set_primitive(agent, execution_context=context)
    handle({"message": "hi"})

    assert context.calls[0][1]["line"] == 12


def test_agent_handle_with_missing_lua_source_info():
    handle = AgentHandle("agent")
    agent = FakeAgent()
    context = FakeExecutionContext()

    class FalsyLuaInfo:
        def __bool__(self):
            return False

    class FalsyLua:
        def eval(self, _expr):
            return FalsyLuaInfo()

    class FalsyLuaSandbox:
        def __init__(self):
            self.lua = FalsyLua()

    context.lua_sandbox = FalsyLuaSandbox()
    handle._set_primitive(agent, execution_context=context)
    handle({"message": "hi"})

    assert context.calls[0][1] is None


def test_agent_handle_source_info_exception(caplog):
    handle = AgentHandle("agent")
    agent = FakeAgent()
    context = FakeExecutionContext()

    class BrokenLua:
        def eval(self, _expr):
            raise RuntimeError("boom")

    class BrokenLuaSandbox:
        def __init__(self):
            self.lua = BrokenLua()

    context.lua_sandbox = BrokenLuaSandbox()
    handle._set_primitive(agent, execution_context=context)

    with caplog.at_level("DEBUG", logger="tactus.primitives.handles"):
        handle({"message": "hi"})
    assert any("Could not capture source location" in rec.message for rec in caplog.records)


def test_agent_handle_output_fallback_to_dict_message():
    handle = AgentHandle("agent")

    class DictAgent:
        def __call__(self, _inputs):
            return {"message": "hello"}

    handle._set_primitive(DictAgent())
    handle({"message": "hi"})
    assert handle.output == "hello"


def test_agent_handle_output_fallback_to_str():
    handle = AgentHandle("agent")

    class ObjAgent:
        def __call__(self, _inputs):
            return object()

    handle._set_primitive(ObjAgent())
    handle({"message": "hi"})
    assert handle.output is not None


def test_agent_handle_output_none_result():
    handle = AgentHandle("agent")

    class NoneAgent:
        def __call__(self, _inputs):
            return None

    handle._set_primitive(NoneAgent())
    result = handle({"message": "hi"})
    assert result is None
    assert handle.output is None


def test_agent_handle_output_dict_non_string_falls_back():
    handle = AgentHandle("agent")

    class DictAgent:
        def __call__(self, _inputs):
            return {"response": {"nested": True}}

    handle._set_primitive(DictAgent())
    result = handle({"message": "hi"})
    assert isinstance(handle.output, str)
    assert "nested" in handle.output
    assert result["response"] == {"nested": True}


def test_agent_handle_output_uses_attribute():
    handle = AgentHandle("agent")

    class AttrAgent:
        def __call__(self, _inputs):
            class Result:
                response = "from-attr"

            return Result()

    handle._set_primitive(AttrAgent())
    handle({"message": "hi"})
    assert handle.output == "from-attr"


def test_agent_handle_output_ignores_broken_attribute():
    handle = AgentHandle("agent")

    class BrokenResult:
        @property
        def response(self):
            raise RuntimeError("boom")

    class Agent:
        def __call__(self, _inputs):
            return BrokenResult()

    handle._set_primitive(Agent())
    handle({"message": "hi"})
    assert handle.output is not None


def test_model_handle_predict_and_call():
    handle = ModelHandle("model")
    with pytest.raises(RuntimeError):
        handle.predict({"x": 1})

    model = FakeModel()
    handle._set_primitive(model)
    assert handle.predict({"x": 1})["label"] == "yes"
    assert handle({"x": 2})["label"] == "yes"


def test_model_handle_call_missing_primitive():
    handle = ModelHandle("model")
    with pytest.raises(RuntimeError):
        handle({"x": 1})


def test_lookup_helpers():
    agent_handle = AgentHandle("agent")
    lookup = AgentLookup({"agent": agent_handle})
    assert lookup("agent") is agent_handle
    with pytest.raises(ValueError):
        lookup("missing")

    model_handle = ModelHandle("model")
    model_lookup = ModelLookup({"model": model_handle})
    assert model_lookup("model") is model_handle
    with pytest.raises(ValueError):
        model_lookup("missing")


def test_handle_and_lookup_repr():
    agent_handle = AgentHandle("agent")
    assert repr(agent_handle) == "AgentHandle('agent', disconnected)"
    agent_handle._set_primitive(FakeAgent())
    assert repr(agent_handle) == "AgentHandle('agent', connected)"

    model_handle = ModelHandle("model")
    assert repr(model_handle) == "ModelHandle('model', disconnected)"
    model_handle._set_primitive(FakeModel())
    assert repr(model_handle) == "ModelHandle('model', connected)"

    assert repr(AgentLookup({})) == "AgentLookup(0 agents)"
    assert repr(ModelLookup({})) == "ModelLookup(0 models)"


def test_type_checking_import_path():
    import tactus.primitives.handles as handles

    original = typing.TYPE_CHECKING
    import sys
    import types

    fake_agent_module = types.ModuleType("tactus.dspy.agent")
    fake_agent_module.DSPyAgentHandle = object
    fake_model_module = types.ModuleType("tactus.primitives.model")
    fake_model_module.ModelPrimitive = object

    original_agent = sys.modules.get("tactus.dspy.agent")
    original_model = sys.modules.get("tactus.primitives.model")

    try:
        typing.TYPE_CHECKING = True
        sys.modules["tactus.dspy.agent"] = fake_agent_module
        sys.modules["tactus.primitives.model"] = fake_model_module
        importlib.reload(handles)
    finally:
        typing.TYPE_CHECKING = original
        if original_agent is None:
            sys.modules.pop("tactus.dspy.agent", None)
        else:
            sys.modules["tactus.dspy.agent"] = original_agent
        if original_model is None:
            sys.modules.pop("tactus.primitives.model", None)
        else:
            sys.modules["tactus.primitives.model"] = original_model
        importlib.reload(handles)
