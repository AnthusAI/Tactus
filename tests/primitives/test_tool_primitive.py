import importlib
import typing

import pytest

from tactus.primitives.tool import ToolCall, ToolPrimitive


class FakeTool:
    def __init__(self, name, function=None):
        self.name = name
        self.function = function


class FakeToolset:
    def __init__(self, tools):
        self.tools = tools


class FakeMCPToolset:
    def __init__(self):
        self.calls = []
        self.tool = None

    def get_tool(self, name):
        return self.tool

    def call_tool(self, name, args):
        self.calls.append((name, args))
        return {"ok": True}


class FakeRuntime:
    def __init__(self, toolset_registry=None):
        self.toolset_registry = toolset_registry or {}


class FakeLogHandler:
    def __init__(self):
        self.events = []

    def log(self, event):
        self.events.append(event)


def test_tool_call_to_dict_and_repr():
    call = ToolCall("tool", {"a": 1}, "ok")
    assert call.to_dict() == {"name": "tool", "args": {"a": 1}, "result": "ok"}
    assert "ToolCall(tool" in repr(call)


def test_tool_registry_lookup():
    tool = ToolPrimitive()
    tool.set_tool_registry({"done": "handle"})
    assert tool("done") == "handle"
    with pytest.raises(ValueError, match="not defined"):
        tool("missing")


def test_get_toolset_requires_runtime():
    tool = ToolPrimitive()
    assert tool._get_toolset("x") is None
    tool.set_runtime(object())
    assert tool._get_toolset("x") is None


def test_get_toolset_from_runtime():
    runtime = FakeRuntime(toolset_registry={"search": object()})
    tool = ToolPrimitive()
    tool.set_runtime(runtime)
    assert tool._get_toolset("search") is runtime.toolset_registry["search"]


def test_extract_tool_function_from_list():
    tool = ToolPrimitive()

    def fn(args):
        return args["x"]

    toolset = FakeToolset([FakeTool("t1", function=fn)])
    assert tool._extract_tool_function(toolset, "t1") is fn


def test_extract_tool_function_from_list_callable_tool():
    tool = ToolPrimitive()

    class CallableTool:
        def __init__(self, name):
            self.name = name

        def __call__(self, args):
            return args["x"] + 1

    toolset = FakeToolset([CallableTool("t1")])
    extracted = tool._extract_tool_function(toolset, "t1")
    assert extracted({"x": 2}) == 3


def test_extract_tool_function_from_dict():
    tool = ToolPrimitive()

    def fn(args):
        return args["x"]

    toolset = FakeToolset({"t1": FakeTool("t1", function=fn)})
    assert tool._extract_tool_function(toolset, "t1") is fn


def test_extract_tool_function_from_dict_callable_tool():
    tool = ToolPrimitive()

    class CallableTool:
        def __init__(self, name):
            self.name = name

        def __call__(self, args):
            return args["x"] * 2

    toolset = FakeToolset({"t1": CallableTool("t1")})
    extracted = tool._extract_tool_function(toolset, "t1")
    assert extracted({"x": 3}) == 6


def test_extract_tool_function_from_mcp_wrapper():
    tool = ToolPrimitive()
    toolset = FakeMCPToolset()
    wrapper = tool._extract_tool_function(toolset, "mcp")
    assert wrapper({"q": 1}) == {"ok": True}
    assert toolset.calls == [("mcp", {"q": 1})]


def test_extract_tool_function_from_mcp_get_tool():
    tool = ToolPrimitive()
    toolset = FakeMCPToolset()

    def fn(args):
        return args["x"]

    toolset.tool = fn
    assert tool._extract_tool_function(toolset, "mcp") is fn


def test_extract_tool_function_callable_toolset():
    tool = ToolPrimitive()

    def toolset(args):
        return args["x"]

    assert tool._extract_tool_function(toolset, "callable") is toolset


def test_extract_tool_function_toolset_function_attr():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.function = lambda args: args["x"]

    toolset = Toolset()
    assert tool._extract_tool_function(toolset, "fn")({"x": 2}) == 2


def test_extract_tool_function_fallback_call():
    class FallbackToolset:
        def call(self, name, args):
            return {"name": name, "args": args}

    tool = ToolPrimitive()
    wrapper = tool._extract_tool_function(FallbackToolset(), "fallback")
    assert wrapper({"x": 1}) == {"name": "fallback", "args": {"x": 1}}


def test_extract_tool_function_fallback_wrapper_raises():
    tool = ToolPrimitive()

    class Toolset:
        pass

    wrapper = tool._extract_tool_function(Toolset(), "missing")
    with pytest.raises(RuntimeError, match="not supported"):
        wrapper({"x": 1})


def test_extract_tool_function_list_no_match_uses_function_attr():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.tools = [FakeTool("other", function=lambda args: args["x"])]
            self.function = lambda args: args["x"] + 1

    toolset = Toolset()
    assert tool._extract_tool_function(toolset, "t1")({"x": 2}) == 3


def test_extract_tool_function_list_match_not_callable_falls_through():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.tools = [type("PlainTool", (), {"name": "t1"})()]
            self.function = lambda args: args["x"] + 1

    toolset = Toolset()
    assert tool._extract_tool_function(toolset, "t1")({"x": 2}) == 3


def test_extract_tool_function_dict_no_match_uses_callable_toolset():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.tools = {"other": FakeTool("other", function=lambda args: args["x"])}

        def __call__(self, args):
            return args["x"] * 3

    toolset = Toolset()
    assert tool._extract_tool_function(toolset, "t1")({"x": 2}) == 6


def test_extract_tool_function_dict_match_not_callable_falls_through():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.tools = {"t1": type("PlainTool", (), {})()}

        def __call__(self, args):
            return args["x"] * 4

    toolset = Toolset()
    assert tool._extract_tool_function(toolset, "t1")({"x": 2}) == 8


def test_extract_tool_function_mcp_without_get_tool():
    tool = ToolPrimitive()

    class Toolset:
        _tools = {}

        def call_tool(self, name, args):
            return {"name": name, "args": args}

    wrapper = tool._extract_tool_function(Toolset(), "mcp")
    assert wrapper({"q": 1}) == {"name": "mcp", "args": {"q": 1}}


def test_get_returns_tool_handle_from_runtime():
    tool = ToolPrimitive()

    class Toolset:
        def __init__(self):
            self.function = lambda args: args["x"] + 1

    runtime = FakeRuntime(toolset_registry={"inc": Toolset()})
    tool.set_runtime(runtime)

    handle = tool.get("inc")
    assert handle({"x": 2}) == 3


def test_get_raises_when_tool_missing():
    tool = ToolPrimitive()
    tool.set_runtime(FakeRuntime(toolset_registry={}))

    with pytest.raises(ValueError, match="not found"):
        tool.get("missing")


def test_record_call_and_accessors():
    log_handler = FakeLogHandler()
    tool = ToolPrimitive(log_handler=log_handler, agent_name="agent", procedure_id="proc")
    tool.record_call("search", {"q": "hi"}, "ok")

    assert tool.called("search") is True
    assert tool.last_result("search") == "ok"
    assert tool.last_call("search")["args"]["q"] == "hi"
    assert tool.get_call_count() == 1
    assert tool.get_call_count("search") == 1
    assert tool.get_all_calls()

    tool.reset()
    assert tool.get_call_count() == 0


def test_last_result_returns_none_when_missing():
    tool = ToolPrimitive()
    assert tool.last_result("missing") is None


def test_record_call_logs_warning_on_handler_failure(caplog):
    class ExplodingLogHandler:
        def log(self, event):
            raise RuntimeError("nope")

    tool = ToolPrimitive(log_handler=ExplodingLogHandler())
    with caplog.at_level("WARNING", logger="tactus.primitives.tool"):
        tool.record_call("search", {"q": "hi"}, "ok")
    assert any("Failed to log tool call event" in rec.message for rec in caplog.records)


def test_tool_repr_includes_call_count():
    tool = ToolPrimitive()
    assert repr(tool) == "ToolPrimitive(0 calls)"
    tool.record_call("search", {"q": "hi"}, "ok")
    assert repr(tool) == "ToolPrimitive(1 calls)"


def test_type_checking_import_path():
    import tactus.primitives.tool as tool_mod

    original = typing.TYPE_CHECKING
    try:
        typing.TYPE_CHECKING = True
        importlib.reload(tool_mod)
    finally:
        typing.TYPE_CHECKING = original
        importlib.reload(tool_mod)
