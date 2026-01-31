import asyncio
import builtins
import sys
import types

import dspy
import pytest

from tactus.dspy.agent import DSPyAgentHandle, create_dspy_agent
from tactus.protocols.cost import CostStats, UsageStats
from tactus.protocols.models import AgentStreamChunkEvent, AgentTurnEvent, CostEvent


class DummyLogHandler:
    def __init__(self, supports_streaming=True):
        self.supports_streaming = supports_streaming
        self.events = []

    def log(self, event):
        self.events.append(event)


class DummyTool:
    def __init__(self, func, name, desc, args=None):
        self.func = func
        self.name = name
        self.desc = desc
        self.args = args


class DummyToolset:
    def __init__(self, tools=None):
        self.tools = tools


class DummyToolPrimitive:
    def __init__(self):
        self.calls = []

    def record_call(self, tool_name, tool_args, tool_result, agent_name=None):
        self.calls.append((tool_name, tool_args, tool_result, agent_name))


class DummyToolCalls:
    def __init__(self, tool_calls):
        self.tool_calls = tool_calls

    def __str__(self) -> str:
        return str(self.tool_calls)


class DummyChunkDelta:
    def __init__(self, content):
        self.content = content


class DummyChunkChoice:
    def __init__(self, content):
        self.delta = DummyChunkDelta(content)


class DummyChunk:
    def __init__(self, content):
        self.choices = [DummyChunkChoice(content)]


class FakeResponse:
    def __init__(self, cost=None, duration_ms=None):
        self._hidden_params = {
            "response_cost": cost,
            "_response_ms": duration_ms,
        }


def _make_agent(monkeypatch, **kwargs):
    monkeypatch.setattr(
        DSPyAgentHandle,
        "_build_module",
        lambda self: types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok")),
    )
    return DSPyAgentHandle(name="agent", model="openai/gpt-4o-mini", **kwargs)


def _patch_import_for(module_name, monkeypatch, error=True):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == module_name:
            if error:
                raise ImportError("blocked")
            return original_import(name, globals, locals, fromlist, level)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


class TestToolsetConversion:
    def test_convert_toolsets_import_error(self, monkeypatch):
        agent = _make_agent(monkeypatch, toolsets=[DummyToolset({})])
        _patch_import_for("dspy.adapters.types.tool", monkeypatch, error=True)

        assert agent._convert_toolsets_to_dspy_tools_sync() == []

    def test_convert_toolsets_builds_tools_and_skips_missing(self, monkeypatch):
        tool_schema = types.SimpleNamespace(json_schema={"properties": {"x": {"type": "int"}}})
        tool = types.SimpleNamespace(
            name="add",
            description="Add numbers",
            function_schema=tool_schema,
            function=lambda x: x,
        )
        toolset = DummyToolset({"add": tool})
        empty_toolset = types.SimpleNamespace()

        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset, empty_toolset])
        dspy_tools = agent._convert_toolsets_to_dspy_tools_sync()

        assert len(dspy_tools) == 1
        assert dspy_tools[0].name == "add"
        assert dspy_tools[0].args == {"x": {"type": "int"}}

    def test_convert_toolsets_handles_bad_tool(self, monkeypatch):
        class BadTool:
            name = "boom"

            @staticmethod
            def function():
                return None

            @property
            def description(self):
                raise RuntimeError("boom")

        toolset = DummyToolset({"boom": BadTool()})
        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset])
        assert agent._convert_toolsets_to_dspy_tools_sync() == []

    def test_convert_toolsets_skips_non_dict_tools(self, monkeypatch):
        toolset = DummyToolset(tools=[])
        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset])

        assert agent._convert_toolsets_to_dspy_tools_sync() == []

    def test_convert_toolsets_with_schema_without_properties(self, monkeypatch):
        tool_schema = types.SimpleNamespace(json_schema={"type": "object"})
        tool = types.SimpleNamespace(
            name="noop",
            description="No props",
            function_schema=tool_schema,
            function=lambda: None,
        )
        toolset = DummyToolset({"noop": tool})
        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset])
        dspy_tools = agent._convert_toolsets_to_dspy_tools_sync()

        assert dspy_tools[0].args is None

    def test_convert_toolsets_with_properties(self, monkeypatch):
        tool_schema = types.SimpleNamespace(json_schema={"properties": {"x": {"type": "int"}}})
        tool = types.SimpleNamespace(
            name="with_props",
            description="Has props",
            function_schema=tool_schema,
            function=lambda x: x,
        )
        toolset = DummyToolset({"with_props": tool})
        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset])
        dspy_tools = agent._convert_toolsets_to_dspy_tools_sync()

        assert dspy_tools[0].args == {"x": {"type": "int"}}

    def test_convert_toolsets_without_function_schema(self, monkeypatch):
        tool = types.SimpleNamespace(
            name="no_schema",
            description="No schema",
            function=lambda: None,
        )
        toolset = DummyToolset({"no_schema": tool})
        module = types.SimpleNamespace(Tool=DummyTool)
        monkeypatch.setitem(sys.modules, "dspy.adapters.types.tool", module)

        agent = _make_agent(monkeypatch, toolsets=[toolset])
        dspy_tools = agent._convert_toolsets_to_dspy_tools_sync()

        assert dspy_tools[0].args is None


class TestToolExecution:
    def test_execute_tool_sync(self, monkeypatch):
        tool = types.SimpleNamespace(name="add", function=lambda x, y: x + y)
        toolset = DummyToolset({"add": tool})
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        assert agent._execute_tool("add", {"x": 1, "y": 2}) == 3

    def test_execute_tool_async_running_loop(self, monkeypatch):
        async def async_tool(x):
            return x + 1

        tool = types.SimpleNamespace(name="async", function=async_tool)
        toolset = DummyToolset({"async": tool})
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        class FakeLoop:
            def is_running(self):
                return True

            def run_until_complete(self, coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

        module = types.SimpleNamespace(apply=lambda: None)
        monkeypatch.setitem(sys.modules, "nest_asyncio", module)
        monkeypatch.setattr(asyncio, "get_event_loop", lambda: FakeLoop())

        assert agent._execute_tool("async", {"x": 2}) == 3

    def test_execute_tool_async_no_loop(self, monkeypatch):
        async def async_tool(x):
            return x * 2

        tool = types.SimpleNamespace(name="async", function=async_tool)
        toolset = DummyToolset({"async": tool})
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        _patch_import_for("nest_asyncio", monkeypatch, error=True)
        monkeypatch.setattr(
            asyncio, "get_event_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop"))
        )

        assert agent._execute_tool("async", {"x": 3}) == 6

    def test_execute_tool_async_not_running_loop(self, monkeypatch):
        async def async_tool(x):
            return x + 5

        tool = types.SimpleNamespace(name="async", function=async_tool)
        toolset = DummyToolset({"async": tool})
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        class FakeLoop:
            def is_running(self):
                return False

            def run_until_complete(self, coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()

        monkeypatch.setattr(asyncio, "get_event_loop", lambda: FakeLoop())

        assert agent._execute_tool("async", {"x": 1}) == 6

    def test_execute_tool_not_found_and_error(self, monkeypatch):
        def boom():
            raise ValueError("nope")

        tool = types.SimpleNamespace(name="boom", function=boom)
        toolset = DummyToolset({"boom": tool})
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        assert agent._execute_tool("boom", {}) == {"error": "nope"}
        assert agent._execute_tool("missing", {}) == {"error": "Tool 'missing' not found"}

    def test_execute_tool_skips_non_dict_tools(self, monkeypatch):
        toolset = DummyToolset(tools=[])
        agent = _make_agent(monkeypatch, toolsets=[toolset])

        assert agent._execute_tool("missing", {}) == {"error": "Tool 'missing' not found"}


class TestCostEvents:
    def test_emit_cost_event_with_cost(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
                    "cost": 0.9,
                    "model": "openai/gpt-4o",
                    "response": FakeResponse(cost=0.9, duration_ms=12),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        agent._emit_cost_event()

        assert isinstance(handler.events[-1], CostEvent)
        assert handler.events[-1].total_cost == 0.9
        assert handler.events[-1].duration_ms == 12

    def test_emit_cost_event_uses_hidden_params(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": FakeResponse(cost=1.2, duration_ms=7),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        agent._emit_cost_event()

        assert handler.events[-1].total_cost == 1.2

    def test_emit_cost_event_completion_cost_failure(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": object(),
                }
            ]

        def boom(*_args, **_kwargs):
            raise RuntimeError("fail")

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())
        monkeypatch.setattr("litellm.completion_cost", boom)

        agent._emit_cost_event()

        assert handler.events[-1].total_cost == 0.0

    def test_emit_cost_event_no_response(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": None,
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        agent._emit_cost_event()

        assert handler.events[-1].total_cost == 0.0

    def test_emit_cost_event_completion_cost_success(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": object(),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())
        monkeypatch.setattr("litellm.completion_cost", lambda *_args, **_kwargs: 1.0)

        agent._emit_cost_event()

        assert handler.events[-1].total_cost == 1.0

    def test_emit_cost_event_provider_from_model(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": 1.0,
                    "model": "openai/gpt-4o",
                    "response": FakeResponse(cost=1.0, duration_ms=3),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        agent._emit_cost_event()

        assert handler.events[-1].provider == "openai"

    def test_emit_cost_event_model_without_provider(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": 1.0,
                    "model": "gpt-4o",
                    "response": FakeResponse(cost=1.0, duration_ms=3),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        agent._emit_cost_event()

        assert handler.events[-1].provider == "unknown"


class TestTurns:
    def test_turn_without_streaming_records_done_tool(self, monkeypatch):
        class DummyModule:
            def __call__(self, **_kw):
                tool_calls = DummyToolCalls([{"name": "done", "args": {"reason": "ok"}}])
                return dspy.Prediction(response="ok", tool_calls=tool_calls)

        agent = _make_agent(monkeypatch)
        agent._module = types.SimpleNamespace(module=DummyModule())
        agent._tool_primitive = DummyToolPrimitive()
        agent._turn_count = 1

        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_without_streaming(
            {"message": "hi"}, {"history": [], "system_prompt": "", "user_message": "hi"}
        )

        assert result.output == "ok"
        assert agent._tool_primitive.calls[0][0] == "done"

    def test_turn_without_streaming_initial_message(self, monkeypatch):
        class DummyModule:
            def __call__(self, **_kw):
                tool_calls = DummyToolCalls([{"name": "noop", "args": {"x": 1}}])
                return dspy.Prediction(response="ok", tool_calls=tool_calls)

        agent = _make_agent(monkeypatch, initial_message="hello")
        agent._module = types.SimpleNamespace(module=DummyModule())
        agent._turn_count = 1

        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_without_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"
        assert agent.get_history()[0]["content"] == "hello"

    def test_turn_without_streaming_no_user_message(self, monkeypatch):
        class DummyModule:
            def __call__(self, **_kw):
                return dspy.Prediction(response="ok")

        agent = _make_agent(monkeypatch)
        agent._module = types.SimpleNamespace(module=DummyModule())
        agent._turn_count = 1

        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_without_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_turn_without_streaming_without_response(self, monkeypatch):
        class DummyModule:
            def __call__(self, **_kw):
                return dspy.Prediction()

        agent = _make_agent(monkeypatch)
        agent._module = types.SimpleNamespace(module=DummyModule())
        agent._turn_count = 1

        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_without_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == ""

    def test_turn_without_streaming_empty_tool_calls(self, monkeypatch):
        class DummyModule:
            def __call__(self, **_kw):
                tool_calls = DummyToolCalls([])
                return dspy.Prediction(response="ok", tool_calls=tool_calls)

        agent = _make_agent(monkeypatch)
        agent._module = types.SimpleNamespace(module=DummyModule())
        agent._turn_count = 1

        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_without_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_turn_with_streaming_emits_chunks_and_tools(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)
        agent._tool_primitive = DummyToolPrimitive()
        agent._turn_count = 1

        tool_calls = DummyToolCalls([types.SimpleNamespace(name="agent_tool", args={"x": 1})])
        final_prediction = dspy.Prediction(response="done", tool_calls=tool_calls)

        async def fake_stream():
            yield DummyChunk("a")
            yield "b"
            yield 123
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(
            agent, "_execute_tool", lambda name, args: {"ok": True, "name": name, "args": args}
        )
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "done"
        assert any(isinstance(e, AgentTurnEvent) and e.stage == "started" for e in handler.events)
        assert any(isinstance(e, AgentTurnEvent) and e.stage == "completed" for e in handler.events)
        assert any(isinstance(e, AgentStreamChunkEvent) for e in handler.events)
        assert agent._tool_primitive.calls[0][0] == "tool"

    def test_turn_with_streaming_fallback_on_no_result(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        async def fake_stream():
            if False:
                yield None

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_turn_without_streaming", lambda _opts, _ctx: "fallback")

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result == "fallback"

    def test_turn_with_streaming_auth_error(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class AuthenticationError(Exception):
            pass

        async def fake_stream():
            if False:
                yield None
            raise AuthenticationError("api_key missing")

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())

        from tactus.core.exceptions import TactusRuntimeError

        with pytest.raises(TactusRuntimeError):
            agent._turn_with_streaming({}, {"history": [], "system_prompt": "", "user_message": ""})

    def test_turn_with_streaming_exception_group(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        async def fake_stream():
            if False:
                yield None
            raise ExceptionGroup("oops", [ValueError("bad")])

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())

        with pytest.raises(ExceptionGroup):
            agent._turn_with_streaming({}, {"history": [], "system_prompt": "", "user_message": ""})


class TestCallAndExecute:
    def test_call_builds_opts_and_checkpoint(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeExecutionContext:
            def __init__(self):
                self.calls = []

            def checkpoint(self, fn, name):
                self.calls.append(name)
                return fn()

        agent.execution_context = FakeExecutionContext()
        monkeypatch.setattr(agent, "_execute_turn", lambda opts: {"response": "ok", "opts": opts})

        result = agent({"message": "hi", "temperature": 0.2, "extra": "x"})

        assert result["opts"]["message"] == "hi"
        assert result["opts"]["temperature"] == 0.2
        assert result["opts"]["context"] == {"extra": "x"}
        assert agent.output == "ok"

    def test_call_handles_string_and_none(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class Result:
            message = "done"

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: Result())

        assert agent("hi").message == "done"
        assert agent.output == "done"

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: None)
        assert agent({"message": "hi"}) is None
        assert agent.output is None

    def test_call_items_error_and_dict_result(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class BadItems:
            def __init__(self):
                self.calls = 0

            def items(self):
                self.calls += 1
                if self.calls == 1:
                    raise TypeError("nope")
                return []

            def get(self, _key, _default=None):
                return None

            def __contains__(self, _key):
                return False

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: {"response": "ok"})

        agent(BadItems())

        assert agent.output == "ok"

    def test_call_items_conversion_and_fallbacks(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class Result:
            @property
            def response(self):
                raise RuntimeError("boom")

            message = "ok"

        class Inputs:
            def items(self):
                return [("message", "hi"), ("extra", "x")]

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: Result())

        agent(Inputs())

        assert agent.output == "ok"

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: object())
        agent({"message": "hi"})

        assert agent.output.startswith("<")

        monkeypatch.setattr(
            agent, "_execute_turn", lambda _opts: {"response": 123, "message": None}
        )
        agent({"message": "hi"})

        assert agent.output.startswith("{")

    def test_call_without_items_attribute(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class NoItems:
            def items(self):
                return [("message", "hi")]

            def __contains__(self, _key):
                return False

            def get(self, _key, _default=None):
                return None

        monkeypatch.setattr(agent, "_execute_turn", lambda _opts: {"response": "ok"})

        inputs = NoItems()
        original_hasattr = builtins.hasattr

        def fake_hasattr(obj, name):
            if obj is inputs and name == "items":
                return False
            return original_hasattr(obj, name)

        monkeypatch.setattr(builtins, "hasattr", fake_hasattr)

        agent(inputs)

        assert agent.output == "ok"

    def test_execute_turn_configures_lm_and_streaming(self, monkeypatch):
        agent = _make_agent(
            monkeypatch,
            toolsets=[DummyToolset({})],
            tool_choice="auto",
            temperature=0.4,
            max_tokens=10,
            model_type="chat",
        )

        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: None)
        configure_calls = {}

        def fake_configure(model, **kwargs):
            configure_calls["model"] = model
            configure_calls["kwargs"] = kwargs

        monkeypatch.setattr("tactus.dspy.config.configure_lm", fake_configure)
        monkeypatch.setattr(agent, "_convert_toolsets_to_dspy_tools_sync", lambda: ["tool"])
        monkeypatch.setattr(agent, "_should_stream", lambda: True)
        monkeypatch.setattr(agent, "_turn_with_streaming", lambda _opts, ctx: ctx)

        result = agent._execute_turn({"message": "hi", "context": {"x": 1}})

        assert configure_calls["model"] == "openai/gpt-4o-mini"
        assert configure_calls["kwargs"]["tool_choice"] == "auto"
        assert result["tools"] == ["tool"]
        assert result["context"] == {"x": 1}

    def test_execute_turn_reraises(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: "lm")
        monkeypatch.setattr(agent, "_should_stream", lambda: False)
        monkeypatch.setattr(
            agent,
            "_turn_without_streaming",
            lambda _opts, _ctx: (_ for _ in ()).throw(ValueError("boom")),
        )

        with pytest.raises(ValueError, match="boom"):
            agent._execute_turn({"message": "hi"})

    def test_execute_turn_returns_mock(self, monkeypatch):
        agent = _make_agent(monkeypatch, registry=object(), mock_manager=True)
        sentinel = object()

        monkeypatch.setattr(agent, "_get_mock_response", lambda _opts: sentinel)

        assert agent._execute_turn({"message": "hi"}) is sentinel

    def test_execute_turn_mock_not_found(self, monkeypatch):
        registry = types.SimpleNamespace(agent_mocks={})
        agent = _make_agent(monkeypatch, registry=registry, mock_manager=True)

        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: "lm")
        monkeypatch.setattr(agent, "_should_stream", lambda: False)
        monkeypatch.setattr(agent, "_turn_without_streaming", lambda _opts, _ctx: "ok")

        assert agent._execute_turn({"message": "hi"}) == "ok"

    def test_execute_turn_without_overrides(self, monkeypatch):
        agent = _make_agent(monkeypatch, initial_message="hello")
        agent.model = "openai:gpt-4o-mini"
        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: None)
        monkeypatch.setattr("tactus.dspy.config.configure_lm", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(agent, "_convert_toolsets_to_dspy_tools_sync", lambda: [])
        monkeypatch.setattr(agent, "_should_stream", lambda: False)
        monkeypatch.setattr(agent, "_turn_without_streaming", lambda _opts, ctx: ctx)

        result = agent._execute_turn({})

        assert result["user_message"] == "hello"

    def test_execute_turn_with_no_optional_kwargs(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent.temperature = None
        agent.max_tokens = None
        agent.model_type = None
        agent.tool_choice = None

        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: None)
        configure_calls = {}

        def fake_configure(model, **kwargs):
            configure_calls["model"] = model
            configure_calls["kwargs"] = kwargs

        monkeypatch.setattr("tactus.dspy.config.configure_lm", fake_configure)
        monkeypatch.setattr(agent, "_should_stream", lambda: False)
        monkeypatch.setattr(agent, "_turn_without_streaming", lambda _opts, _ctx: "ok")

        assert agent._execute_turn({"message": "hi"}) == "ok"
        assert configure_calls["kwargs"] == {}


class TestStreamingBranches:
    def test_streaming_initial_message_and_no_tool_calls(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler, initial_message="hi")
        agent._turn_count = 1

        final_prediction = dspy.Prediction(response="done")

        async def fake_stream():
            yield DummyChunk("x")
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "done"
        assert agent.get_history()[0]["content"] == "hi"

    def test_streaming_tool_calls_missing_attr(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)
        agent._turn_count = 1

        final_prediction = dspy.Prediction(response="ok", tool_calls=[{"name": "noop"}])

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_tool_calls_and_done_record(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)
        agent._tool_primitive = DummyToolPrimitive()
        agent._turn_count = 1

        tool_calls = DummyToolCalls(
            [types.SimpleNamespace(name="agent_done", args={"reason": "ok"})]
        )
        final_prediction = dspy.Prediction(response="done", tool_calls=tool_calls)

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_execute_tool", lambda name, args: {"status": "ok"})
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "done"
        assert agent._tool_primitive.calls[0][0] == "done"
        assert agent._tool_primitive.calls[1][0] == "done"

    def test_streaming_timeout_branch(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        final_prediction = dspy.Prediction(response="ok")

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        import queue

        def raise_empty(self, *args, **kwargs):
            raise queue.Empty()

        monkeypatch.setattr(queue.Queue, "get", raise_empty)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_without_response_attr(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        final_prediction = dspy.Prediction()

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == ""

    def test_streaming_tool_calls_without_tool_primitive(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)
        agent._turn_count = 1

        tool_calls = DummyToolCalls([types.SimpleNamespace(name="agent_tool", args={})])
        final_prediction = dspy.Prediction(response="ok", tool_calls=tool_calls)

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_execute_tool", lambda name, args: {"status": "ok"})
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_empty_chunks(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        final_prediction = dspy.Prediction(response="ok")

        async def fake_stream():
            yield DummyChunk("")
            yield ""
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_non_exception_group_error(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        async def fake_stream():
            if False:
                yield None
            raise ValueError("boom")

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())

        with pytest.raises(ValueError, match="boom"):
            agent._turn_with_streaming({}, {"history": [], "system_prompt": "", "user_message": ""})

    def test_streaming_empty_chunk_message_branch(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        final_prediction = dspy.Prediction(response="ok")

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        import queue

        results = [("chunk", ""), ("done", None)]

        def fake_get(self, *args, **kwargs):
            return results.pop(0)

        monkeypatch.setattr(queue.Queue, "get", fake_get)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_unknown_chunk_type_skips(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        final_prediction = dspy.Prediction(response="ok")

        async def fake_stream():
            yield final_prediction

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())
        monkeypatch.setattr(agent, "_extract_last_call_stats", lambda: (UsageStats(), CostStats()))
        monkeypatch.setattr(agent, "_emit_cost_event", lambda: None)

        import queue

        results = [("noop", "data"), ("done", None)]

        def fake_get(self, *args, **kwargs):
            return results.pop(0)

        monkeypatch.setattr(queue.Queue, "get", fake_get)

        result = agent._turn_with_streaming(
            {}, {"history": [], "system_prompt": "", "user_message": ""}
        )

        assert result.output == "ok"

    def test_streaming_exception_group_without_exceptions(self, monkeypatch):
        handler = DummyLogHandler()
        agent = _make_agent(monkeypatch, log_handler=handler)

        class ExceptionGroup(Exception):
            pass

        async def fake_stream():
            if False:
                yield None
            raise ExceptionGroup("empty")

        monkeypatch.setattr(dspy, "streamify", lambda _module: lambda **_kw: fake_stream())

        with pytest.raises(ExceptionGroup):
            agent._turn_with_streaming({}, {"history": [], "system_prompt": "", "user_message": ""})


class TestMockingAndHistory:
    def test_get_mock_response_missing_registry(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        assert agent._get_mock_response({"message": "hi"}) is None

    def test_get_mock_response_temporal_index_and_non_dict(self, monkeypatch):
        temporal = ["raw", {"message": "second", "tool_calls": []}]
        mock_config = types.SimpleNamespace(
            message="default", tool_calls=[], data={}, temporal=temporal
        )
        registry = types.SimpleNamespace(agent_mocks={"agent": mock_config})

        agent = _make_agent(monkeypatch, registry=registry)
        agent._turn_count = 0
        result = agent._get_mock_response({})

        assert result.output == "default"

    def test_get_mock_response_when_message_matches(self, monkeypatch):
        temporal = [{"when_message": "hi", "message": "matched", "tool_calls": []}]
        mock_config = types.SimpleNamespace(
            message="default", tool_calls=[], data={}, temporal=temporal
        )
        registry = types.SimpleNamespace(agent_mocks={"agent": mock_config})

        agent = _make_agent(monkeypatch, registry=registry)
        agent._turn_count = 1

        result = agent._get_mock_response({"message": "hi"})

        assert result.output == "matched"

    def test_get_mock_response_with_output_schema_data(self, monkeypatch):
        temporal = [{"message": "hi", "tool_calls": [], "data": {"result": "ok"}}]
        mock_config = types.SimpleNamespace(
            message="default", tool_calls=[], data={}, temporal=temporal
        )
        registry = types.SimpleNamespace(agent_mocks={"agent": mock_config})

        agent = _make_agent(
            monkeypatch, registry=registry, output_schema={"result": {"type": "string"}}
        )
        agent._turn_count = 1

        result = agent._get_mock_response({"message": "hi"})

        assert result.output == "ok"

    def test_get_mock_response_index_overflow(self, monkeypatch):
        temporal = [{"message": "first", "tool_calls": []}]
        mock_config = types.SimpleNamespace(
            message="default", tool_calls=[], data={}, temporal=temporal
        )
        registry = types.SimpleNamespace(agent_mocks={"agent": mock_config})

        agent = _make_agent(monkeypatch, registry=registry)
        agent._turn_count = 5

        result = agent._get_mock_response({})

        assert result.output == "first"

    def test_get_mock_response_wrap_raises(self, monkeypatch):
        mock_config = types.SimpleNamespace(message="default", tool_calls=[], data={}, temporal=[])
        registry = types.SimpleNamespace(agent_mocks={"agent": mock_config})
        agent = _make_agent(monkeypatch, registry=registry)

        monkeypatch.setattr(
            agent,
            "_wrap_mock_response",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("boom")),
        )

        with pytest.raises(ValueError, match="boom"):
            agent._get_mock_response({})

    def test_wrap_mock_response_records_non_done_tool(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._tool_primitive = DummyToolPrimitive()

        result = agent._wrap_mock_response(
            {"message": "hello", "tool_calls": [{"tool": "search", "args": {"q": "x"}}]},
            {"message": "hi"},
        )

        assert result.output == "hello"
        assert agent._tool_primitive.calls[0][0] == "search"

    def test_wrap_mock_response_records_done_tool(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._tool_primitive = DummyToolPrimitive()

        result = agent._wrap_mock_response(
            {"response": "ok", "tool_calls": [{"tool": "done", "args": {"reason": "r"}}]},
            {"message": "hi"},
        )

        assert result.output == "ok"
        assert agent._tool_primitive.calls[0][2]["reason"] == "r"

    def test_wrap_mock_response_empty_response(self, monkeypatch):
        agent = _make_agent(monkeypatch, initial_message="hello")
        agent._turn_count = 1

        result = agent._wrap_mock_response({}, {})

        assert result.output == ""
        assert agent.get_history()[0]["content"] == "hello"

    def test_wrap_mock_response_non_list_tool_calls(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._tool_primitive = DummyToolPrimitive()

        result = agent._wrap_mock_response({"response": "ok", "tool_calls": {"tool": "noop"}}, {})

        assert result.output == "ok"
        assert agent._tool_primitive.calls == []

    def test_wrap_mock_response_tool_call_missing_tool_key(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._tool_primitive = DummyToolPrimitive()

        result = agent._wrap_mock_response(
            {"response": "ok", "tool_calls": [{"name": "noop"}]},
            {"message": "hi"},
        )

        assert result.output == "ok"
        assert agent._tool_primitive.calls == []

    def test_clear_history_resets_turns(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._history.add({"role": "user", "content": "hi"})
        agent._turn_count = 3

        agent.clear_history()

        assert agent.get_history() == []
        assert agent._turn_count == 0

    def test_history_property(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        assert agent.history is agent._history


class TestAgentUtilities:
    def test_usage_and_cost_properties(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._add_usage_and_cost(
            UsageStats(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            CostStats(
                total_cost=1.2, prompt_cost=0.4, completion_cost=0.8, model="m", provider="p"
            ),
        )

        assert agent.usage.total_tokens == 3
        assert agent.cost().total_cost == 1.2
        assert agent.cost().provider == "p"

    def test_add_usage_and_cost_without_model_provider(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._add_usage_and_cost(
            UsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            CostStats(total_cost=0.0),
        )

        assert agent.cost().model is None
        assert agent.cost().provider is None

    def test_extract_last_call_stats_hidden_params_and_failure(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": FakeResponse(cost=None, duration_ms=1),
                }
            ]

        def boom(*_args, **_kwargs):
            raise RuntimeError("fail")

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())
        monkeypatch.setattr("litellm.cost_calculator.cost_per_token", boom)

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 3
        assert cost.total_cost == 0.0

    def test_extract_last_call_stats_hidden_cost(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": FakeResponse(cost=0.5, duration_ms=5),
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 2
        assert cost.total_cost == 0.5
        assert cost.provider == "openai"

    def test_extract_last_call_stats_empty_history(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = []

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 0
        assert cost.total_cost == 0.0

    def test_extract_last_call_stats_cost_per_token_success(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": None,
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())
        monkeypatch.setattr(
            "litellm.cost_calculator.cost_per_token", lambda *_args, **_kwargs: (0.1, 0.2)
        )

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 2
        assert cost.total_cost == 0.30000000000000004

    def test_extract_last_call_stats_zero_tokens(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    "cost": None,
                    "model": "openai/gpt-4o",
                    "response": None,
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 0
        assert cost.total_cost == 0.0

    def test_extract_last_call_stats_with_cost(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    "cost": 1.5,
                    "model": "openai/gpt-4o",
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        usage, cost = agent._extract_last_call_stats()

        assert usage.total_tokens == 2
        assert cost.total_cost == 1.5
        assert cost.provider == "openai"

    def test_extract_last_call_stats_model_none(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class FakeLM:
            history = [
                {
                    "usage": {"prompt_tokens": 1, "completion_tokens": 0, "total_tokens": 1},
                    "cost": 1.0,
                    "model": None,
                }
            ]

        monkeypatch.setattr(dspy.settings, "lm", FakeLM())

        _, cost = agent._extract_last_call_stats()

        assert cost.model is None
        assert cost.provider is None

    def test_prediction_to_value_handles_bad_data(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class BadPrediction:
            def data(self):
                raise ValueError("bad data")

            @property
            def message(self):
                return "fallback"

        assert agent._prediction_to_value(BadPrediction()) == "fallback"

    def test_prediction_to_value_parses_json(self, monkeypatch):
        agent = _make_agent(monkeypatch, output_schema={"result": {"type": "object"}})

        class JsonPrediction:
            def data(self):
                return {"response": '{"ok": true}'}

            @property
            def message(self):
                return ""

        assert agent._prediction_to_value(JsonPrediction()) == {"ok": True}

    def test_prediction_to_value_returns_single_field(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class SimplePrediction:
            def data(self):
                return {"response": "ok"}

            @property
            def message(self):
                return "fallback"

        assert agent._prediction_to_value(SimplePrediction()) == "ok"

    def test_prediction_to_value_multiple_fields(self, monkeypatch):
        agent = _make_agent(monkeypatch)

        class MultiPrediction:
            def data(self):
                return {"response": "ok", "score": 1, "tool_calls": [{"id": "t"}]}

            @property
            def message(self):
                return ""

        assert agent._prediction_to_value(MultiPrediction()) == {"response": "ok", "score": 1}

    def test_prediction_to_value_uses_message_when_no_response(self, monkeypatch):
        agent = _make_agent(monkeypatch, output_schema={"answer": {"type": "string"}})

        class SimplePrediction:
            def data(self):
                return {}

            @property
            def message(self):
                return "raw"

        assert agent._prediction_to_value(SimplePrediction()) == "raw"

    def test_wrap_as_result_includes_usage(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        from tactus.dspy.prediction import TactusPrediction

        prediction = TactusPrediction(dspy.Prediction(response="hello"))

        result = agent._wrap_as_result(
            prediction,
            UsageStats(total_tokens=1),
            CostStats(total_cost=0.2),
        )

        assert result.output == "hello"
        assert result.usage.total_tokens == 1

    def test_module_to_strategy_variants(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        assert agent._module_to_strategy("Raw") == "raw"
        assert agent._module_to_strategy("ChainOfThought") == "chain_of_thought"

        with pytest.raises(ValueError, match="Unknown module"):
            agent._module_to_strategy("Nope")

    def test_build_module_signature_with_tools(self, monkeypatch):
        captured = {}

        def fake_create_module(_name, config):
            captured.update(config)
            return types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok"))

        monkeypatch.setattr("tactus.dspy.agent.create_module", fake_create_module)
        DSPyAgentHandle(name="agent", toolsets=[DummyToolset({})], model="openai/gpt-4o-mini")

        assert "tools" in captured["signature"]

    def test_build_module_signature_without_tools(self, monkeypatch):
        captured = {}

        def fake_create_module(_name, config):
            captured.update(config)
            return types.SimpleNamespace(module=lambda **_kw: dspy.Prediction(response="ok"))

        monkeypatch.setattr("tactus.dspy.agent.create_module", fake_create_module)
        DSPyAgentHandle(name="agent", model="openai/gpt-4o-mini")

        assert "tools" not in captured["signature"]

    def test_should_stream_variants(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        assert agent._should_stream() is False

        handler = DummyLogHandler(supports_streaming=False)
        agent.log_handler = handler
        assert agent._should_stream() is False

        handler.supports_streaming = True
        agent.disable_streaming = True
        assert agent._should_stream() is False

        agent.disable_streaming = False
        assert agent._should_stream() is True

    def test_emit_cost_event_no_handler_or_history(self, monkeypatch):
        agent = _make_agent(monkeypatch)
        agent._emit_cost_event()

        handler = DummyLogHandler()
        agent.log_handler = handler

        monkeypatch.setattr(dspy.settings, "lm", None)
        agent._emit_cost_event()

        assert handler.events == []


class TestCreateAgent:
    def test_create_dspy_agent_requires_model(self, monkeypatch):
        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: None)

        with pytest.raises(ValueError, match="LM not configured"):
            create_dspy_agent("agent", {"system_prompt": "hi"})

    def test_create_dspy_agent_uses_output_schema(self, monkeypatch):
        monkeypatch.setattr("tactus.dspy.config.get_current_lm", lambda: "lm")

        agent = create_dspy_agent(
            "agent",
            {
                "system_prompt": "hi",
                "model": "openai/gpt-4o-mini",
                "output": {"x": {"type": "string"}},
            },
        )

        assert agent.output_schema == {"x": {"type": "string"}}
