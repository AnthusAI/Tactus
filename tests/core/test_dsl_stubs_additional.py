import pytest

from tactus.core.dsl_stubs import create_dsl_stubs, lua_table_to_dict
from tactus.core.registry import RegistryBuilder
from tactus.primitives.handles import AgentHandle
from tactus.primitives.tool_handle import ToolHandle


class BrokenLuaTable:
    def keys(self):
        raise TypeError("boom")

    def items(self):
        raise TypeError("boom")


class FakeRuntime:
    def __init__(self, toolset_registry=None):
        self.toolset_registry = toolset_registry or {}


class FakeToolPrimitive:
    def __init__(self, runtime, tool_fn):
        self._runtime = runtime
        self._tool_fn = tool_fn

    def _extract_tool_function(self, toolset, name):
        return self._tool_fn

    def set_tool_registry(self, registry):
        self._registry = registry


def test_lua_table_to_dict_falls_back_on_errors():
    table = BrokenLuaTable()
    assert lua_table_to_dict(table) is table


def test_procedure_uses_run_and_dependencies_and_stub_calls():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    stub = stubs["Procedure"]({"run": run_fn, "dependencies": {"db": {"type": "sql"}}})
    state_schema = builder.registry.named_procedures["main"]["state_schema"]
    assert state_schema["_dependencies"] == {"db": {"type": "sql"}}

    stub.registry[stub.name] = lambda: "called"
    assert stub() == "called"

    stub.registry.pop(stub.name)
    with pytest.raises(RuntimeError, match="not initialized"):
        stub()


def test_procedure_strips_none_entries_from_array_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    stubs["Procedure"]({1: run_fn})
    proc = builder.registry.named_procedures["main"]
    assert proc["input_schema"] == {}
    assert proc["output_schema"] == {}


def test_procedure_type_and_missing_function_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="first argument must be a string"):
        stubs["Procedure"](123)

    with pytest.raises(TypeError, match="requires a function"):
        stubs["Procedure"]({"input": {}})


def test_procedure_old_style_registers_named():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn(input_data=None):
        return input_data

    stubs["Procedure"]("helper", {"input": {"value": {}}}, run_fn)
    assert "helper" in builder.registry.named_procedures


def test_procedure_old_style_missing_run_and_stub_calls():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="requires a function in old syntax"):
        stubs["Procedure"]("old", {}, None)

    stub = stubs["Procedure"]("old", {}, lambda: "ok")
    stub.registry[stub.name] = lambda: "called"
    assert stub() == "called"

    stub.registry.pop(stub.name)
    with pytest.raises(RuntimeError, match="not initialized"):
        stub()

    stubs["Procedure"]("old2", None, lambda: "ok")
    assert "old2" in builder.registry.named_procedures


def test_toolset_old_and_new_syntax():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Toolset"]("legacy", {"tools": ["a"]})
    assert builder.registry.toolsets["legacy"]["tools"] == ["a"]

    register = stubs["Toolset"]("curried")
    register({"tools": ["b"]})
    assert builder.registry.toolsets["curried"]["tools"] == ["b"]


def test_toolset_empty_config_normalizes_to_dict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Toolset"]("empty_old", {})
    assert builder.registry.toolsets["empty_old"] == {}

    register = stubs["Toolset"]("empty_new")
    register({})
    assert builder.registry.toolsets["empty_new"] == {}


def test_prompt_hitl_and_settings_register():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Prompt"]("welcome", "Hello")
    assert builder.registry.prompts["welcome"] == "Hello"

    stubs["Hitl"]("approval", {"type": "approval", "message": "ok"})
    assert "approval" in builder.registry.hitl_points

    stubs["default_provider"]("openai")
    stubs["default_model"]("gpt-4o")
    stubs["return_prompt"]("return")
    stubs["error_prompt"]("error")
    stubs["status_prompt"]("status")
    stubs["async"](True)
    stubs["max_depth"](3)
    stubs["max_turns"](7)

    assert builder.registry.default_provider == "openai"
    assert builder.registry.default_model == "gpt-4o"
    assert builder.registry.return_prompt == "return"
    assert builder.registry.error_prompt == "error"
    assert builder.registry.status_prompt == "status"
    assert builder.registry.async_enabled is True
    assert builder.registry.max_depth == 3
    assert builder.registry.max_turns == 7


def test_input_output_schema_register():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["input"]({"query": {"type": "string"}})
    stubs["output"]({"result": {"type": "string"}})

    assert builder.registry.top_level_input_schema["query"]["type"] == "string"
    assert builder.registry.top_level_output_schema["result"]["type"] == "string"


def test_field_builders_and_evaluators():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    field = stubs["field"]

    required = field["string"]({"required": True, "description": "name"})
    assert required["type"] == "string"
    assert required["required"] is True
    assert required["description"] == "name"

    with_default = field["number"]({"default": 3})
    assert with_default["default"] == 3

    evaluator = field["equals_expected"]("not-a-dict")
    assert evaluator["type"] == "equals_expected"

    bare_field = field["boolean"]()
    assert bare_field["type"] == "boolean"

    bare_eval = field["contains"]()
    assert bare_eval["type"] == "contains"


def test_model_hybrid_assignment_lookup_and_unhashable():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Model"]({"type": "http"})
    assert handle.name in builder.registry.models

    with pytest.raises(TypeError):
        stubs["Model"]("classifier", {"type": "http"})

    register = stubs["Model"]("classifier")
    register({"type": "http"})
    lookup = stubs["Model"]("classifier")
    assert lookup.name == "classifier"

    with pytest.raises(TypeError):
        stubs["Model"](["bad"], {"type": "http"})

    model = stubs["Model"]
    model.lookup._registry = 1
    accept = model("lookup")
    accept({"type": "http"})

    original_definer = model.definer
    model.definer = lambda *args, **kwargs: (_ for _ in ()).throw(
        TypeError("unhashable type: 'dict'")
    )
    handle = model({"type": "http"}, {"config": "x"})
    assert handle.name in builder.registry.models
    model.definer = original_definer


def test_specification_variants_and_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Specification"]("Feature: Sample\n  Scenario: ok\n")
    assert "Feature: Sample" in builder.registry.gherkin_specifications

    stubs["Specification"]({"from": "specs/example.feature"})
    assert "specs/example.feature" in builder.registry.specs_from_references

    stubs["Specification"]("story", [])
    assert any(spec.name == "story" for spec in builder.registry.specifications)

    with pytest.raises(TypeError, match="Specification expects"):
        stubs["Specification"]()


def test_evaluation_routes_configs():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Evaluation"]({"dataset": "foo", "evaluators": []})
    assert builder.registry.pydantic_evaluations["dataset"] == "foo"

    stubs["Evaluation"]({"runs": 3})
    assert builder.registry.evaluation_config["runs"] == 3


def test_tool_requires_config_and_validates_source():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="Curried Tool syntax is not supported"):
        stubs["Tool"]("name")

    with pytest.raises(TypeError, match="requires a configuration table"):
        stubs["Tool"]()

    with pytest.raises(TypeError, match="both 'use' and 'source'"):
        stubs["Tool"]({"use": "broker.host.ping", "source": "other"})

    with pytest.raises(TypeError, match="requires either a function"):
        stubs["Tool"]({"description": "missing"})


def test_tool_name_validation_and_source_runtime_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="Tool 'name' must be a string"):
        stubs["Tool"]({"name": 123, "use": "broker.host.ping"})

    with pytest.raises(TypeError, match="Tool 'name' cannot be empty"):
        stubs["Tool"]({"name": " ", "use": "broker.host.ping"})

    handle = stubs["Tool"]({"use": "broker.host.ping"})
    with pytest.raises(RuntimeError, match="tool primitive missing"):
        handle({})


def test_tool_function_registers_and_allows_calls():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args["x"] + 1

    handle = stubs["Tool"]({1: handler, "name": "adder"})
    assert handle.name == "adder"
    assert builder.registry.lua_tools["adder"]["handler"] is handler
    assert handle({"x": 2}) == 3


def test_tool_list_cleanup_and_handler_source_conflict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    stubs["Tool"]({1: handler})
    assert len(builder.registry.lua_tools) == 1

    with pytest.raises(TypeError, match="function and 'use"):
        stubs["Tool"]({1: handler, "use": "broker.host.ping"})


def test_tool_source_runtime_failures():
    builder = RegistryBuilder()

    runtime_missing = FakeToolPrimitive(None, lambda args: args)
    stubs = create_dsl_stubs(builder, tool_primitive=runtime_missing)
    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})
    with pytest.raises(RuntimeError, match="runtime not connected"):
        handle({})

    runtime = FakeRuntime()
    missing_toolset = FakeToolPrimitive(runtime, lambda args: args)
    stubs = create_dsl_stubs(builder, tool_primitive=missing_toolset)
    handle = stubs["Tool"]({"name": "pong", "use": "broker.host.ping"})
    with pytest.raises(RuntimeError, match="not resolved"):
        handle({})


def test_tool_source_argument_handling_and_fallbacks():
    runtime = FakeRuntime({"ping": object(), "pong": object()})
    primitive = FakeToolPrimitive(runtime, lambda args: args)
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder, tool_primitive=primitive)
    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})

    with pytest.raises(TypeError, match="args must be an object"):
        handle(123)

    def takes_dict(args):
        return args["x"] * 2

    primitive = FakeToolPrimitive(runtime, takes_dict)
    stubs = create_dsl_stubs(builder, tool_primitive=primitive)
    handle = stubs["Tool"]({"name": "pong", "use": "broker.host.ping"})
    assert handle({"x": 2}) == 4


def test_tool_source_async_handler_no_loop():
    async def tool_fn(args):
        return args["x"] + 1

    runtime = FakeRuntime({"ping": object()})
    primitive = FakeToolPrimitive(runtime, tool_fn)
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder, tool_primitive=primitive)
    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})

    assert handle({"x": 1}) == 2


@pytest.mark.asyncio
async def test_tool_source_async_handler_in_loop():
    async def tool_fn(args):
        return args["x"] + 1

    runtime = FakeRuntime({"ping": object()})
    primitive = FakeToolPrimitive(runtime, tool_fn)
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder, tool_primitive=primitive)
    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})

    assert handle({"x": 2}) == 3


@pytest.mark.asyncio
async def test_tool_source_async_handler_raises_in_thread():
    async def tool_fn(args):
        raise ValueError("boom")

    runtime = FakeRuntime({"ping": object()})
    primitive = FakeToolPrimitive(runtime, tool_fn)
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder, tool_primitive=primitive)
    handle = stubs["Tool"]({"name": "ping", "use": "broker.host.ping"})

    with pytest.raises(ValueError, match="boom"):
        handle({"x": 1})


def test_agent_tools_normalization_and_inline_tool_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = ToolHandle("ping", lambda args: "ok")
    handle = stubs["Agent"](
        {
            "system_prompt": "Hi",
            "tools": [tool],
        }
    )
    agent = builder.registry.agents[handle.name]
    assert agent.tools == ["ping"]

    with pytest.raises(ValueError, match="inline tool definitions"):
        stubs["Agent"](
            {
                "system_prompt": "Hi",
                "tools": [{"handler": lambda args: "nope"}],
            }
        )

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"system_prompt": "Hi", "inline_tools": ["bad"]})


def test_agent_curried_validations_and_normalization():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="toolsets"):
        stubs["Agent"]("curried")({"toolsets": []})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]("curried")({"inline_tools": ["bad"]})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]("curried")({"inline_tools": "bad"})

    with pytest.raises(ValueError, match="inline tool definitions"):
        stubs["Agent"]("curried")({"tools": [{"handler": lambda args: None}]})

    with pytest.raises(ValueError, match="session"):
        stubs["Agent"]("curried")({"session": "legacy"})

    tool = ToolHandle("ping", lambda args: "ok")
    handle = stubs["Agent"]("curried")(
        {
            "system_prompt": "Hi",
            "tools": [tool, {"filter": "x"}, "raw"],
            "input": {"text": {}},
            "output": {"result": {"type": "string"}},
        }
    )
    agent = builder.registry.agents[handle.name]
    assert agent.tools == ["ping", {"filter": "x"}, "raw"]
    assert agent.output is not None


def test_agent_curried_runtime_context_creation(monkeypatch):
    builder = RegistryBuilder()

    tool_primitive = type("ToolPrimitive", (), {})()
    execution_context = object()
    runtime_context = {"log_handler": "log", "tool_primitive": tool_primitive}

    import tactus.dspy.agent as dspy_agent

    created = {}

    class DummyAgent:
        def __init__(self):
            self.log_handler = None

    def fake_create(name, cfg, registry=None, mock_manager=None):
        created["config"] = cfg
        agent = DummyAgent()
        agent.log_handler = cfg.get("log_handler")
        return agent

    monkeypatch.setattr(dspy_agent, "create_dspy_agent", fake_create)

    runtime_context["execution_context"] = execution_context
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    handle = stubs["Agent"]("runtime")(
        {
            "system_prompt": "Hi",
            "tools": ["tool"],
            "provider": "openai",
            "model": "gpt-4o",
        }
    )

    assert created["config"]["toolsets"] == ["tool"]
    assert created["config"]["model"] == "openai:gpt-4o"
    assert created["config"]["log_handler"] == "log"
    assert handle._primitive is not None
    assert handle._execution_context is execution_context
    assert handle._primitive._tool_primitive is tool_primitive
    assert runtime_context["_created_agents"]["runtime"] is handle._primitive


def test_agent_curried_runtime_context_failure(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": "log"}

    import tactus.dspy.agent as dspy_agent

    def fake_create(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(dspy_agent, "create_dspy_agent", fake_create)

    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    handle = stubs["Agent"]("runtime")({"system_prompt": "Hi"})

    assert handle.name == "runtime"
    assert "_created_agents" not in runtime_context


def test_agent_assignment_runtime_context_creation(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": "log"}

    import tactus.dspy.agent as dspy_agent

    class DummyAgent:
        def __init__(self):
            self.log_handler = None

    def fake_create(name, cfg, registry=None, mock_manager=None):
        agent = DummyAgent()
        agent.log_handler = cfg.get("log_handler")
        return agent

    monkeypatch.setattr(dspy_agent, "create_dspy_agent", fake_create)

    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    handle = stubs["Agent"](
        {"system_prompt": "Hi", "input": {"text": {}}, "output": {"result": {"type": "string"}}}
    )

    assert handle._primitive is not None
    assert runtime_context["_created_agents"][handle.name] is handle._primitive


def test_agent_lookup_and_missing_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    existing = AgentHandle("existing")
    stubs["_registries"]["agent"]["existing"] = existing
    assert stubs["Agent"]("existing") is existing

    with pytest.raises(TypeError, match="requires a configuration table"):
        stubs["Agent"]()


def test_binding_callback_renames_tool_and_agent_handles():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]

    tool_handle = ToolHandle("_temp_tool_1234", lambda args: "ok")
    builder.registry.lua_tools[tool_handle.name] = {"description": "temp"}
    callback("renamed", tool_handle)

    assert "renamed" in builder.registry.lua_tools
    assert tool_handle.name == "renamed"

    with pytest.raises(RuntimeError, match="Tool name mismatch"):
        callback("other", ToolHandle("explicit", lambda args: "ok"))

    agent_handle = AgentHandle("_temp_agent_5678")
    builder.registry.agents[agent_handle.name] = object()
    runtime_context = {"_created_agents": {agent_handle.name: object()}}
    callback = create_dsl_stubs(builder, runtime_context=runtime_context)[
        "_tactus_register_binding"
    ]
    callback("agent", agent_handle)

    assert "agent" in builder.registry.agents
    assert agent_handle.name == "agent"
    assert "agent" in runtime_context["_created_agents"]


def test_signature_and_lm_helpers(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    import tactus.dspy as dspy

    signature_calls = []

    def fake_signature(*args, **kwargs):
        signature_calls.append((args, kwargs))
        return {"args": args, "kwargs": kwargs}

    monkeypatch.setattr(dspy, "create_signature", fake_signature)

    assert stubs["Signature"]("question -> answer")["args"][0] == "question -> answer"

    accept = stubs["Signature"]("qa")
    result = accept({})
    assert result["kwargs"]["name"] == "qa"
    assert result["args"][0] == {}

    assert stubs["Signature"]({"input": {"q": "str"}})["args"][0]["input"]["q"] == "str"

    with pytest.raises(TypeError, match="Signature expects"):
        stubs["Signature"](123)

    lm_calls = []

    def fake_lm(model, **cfg):
        lm_calls.append((model, cfg))
        return {"model": model, "cfg": cfg}

    monkeypatch.setattr(dspy, "configure_lm", fake_lm)
    monkeypatch.setattr(dspy, "get_current_lm", lambda: "current")

    configure = stubs["LM"]("openai/gpt")
    assert configure()["model"] == "openai/gpt"

    direct = stubs["LM"]("openai/gpt", {"temperature": 0.5})
    assert direct["cfg"]["temperature"] == 0.5

    assert stubs["get_current_lm"]() == "current"


def test_history_with_messages(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    import tactus.dspy as dspy

    monkeypatch.setattr(dspy, "create_history", lambda messages=None: {"messages": messages})

    messages = [{"role": "user", "content": "hi"}]
    assert stubs["History"](messages)["messages"] == messages


def test_message_repr_and_invalid_role():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="Invalid role"):
        stubs["Message"]({"role": "bad", "content": "oops"})

    message = stubs["Message"]({"role": "assistant", "content": "x" * 60})
    assert "..." in repr(message)


def test_mocks_register_agent_and_tool_configs():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Mocks"](None)

    stubs["Mocks"](
        {
            "agent": {
                "tool_calls": [{"tool": "done", "args": {"reason": "ok"}}],
                "message": "ok",
            },
            "skip": "ignore",
            "search": {"conditional": [{"when": {"q": "x"}, "returns": {"out": "y"}}]},
            "boom": {"error": "fail"},
            "noop": {"unused": True},
        }
    )

    assert "agent" in builder.registry.agent_mocks
    assert builder.registry.mocks["search"]["conditional_mocks"][0]["return"]["out"] == "y"
    assert builder.registry.mocks["boom"]["error"] == "fail"


def test_module_and_dspy_agent_creation(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    import tactus.dspy as dspy

    module_calls = []
    agent_calls = []

    def fake_module(name, cfg, registry=None, mock_manager=None):
        module_calls.append((name, cfg))
        return {"name": name, "cfg": cfg}

    def fake_agent(name, cfg, registry=None, mock_manager=None):
        agent_calls.append((name, cfg))
        return {"name": name, "cfg": cfg}

    monkeypatch.setattr(dspy, "create_module", fake_module)
    monkeypatch.setattr(dspy, "create_dspy_agent", fake_agent)

    assert stubs["Module"]("qa", {"signature": "q -> a"})["name"] == "qa"

    accept_module = stubs["Module"]("qa2")
    accept_module({"signature": "q -> a"})
    assert module_calls[-1][0] == "qa2"

    stubs["DSPyAgent"]({"name": "agent", "system_prompt": "Hi"})
    accept_agent = stubs["DSPyAgent"]()
    accept_agent({"system_prompt": "Hi"})
    assert agent_calls[0][0] == "agent"


def test_mcp_namespace_placeholder_tools():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["mcp"].filesystem.read_file
    assert handle.name == "mcp.filesystem.read_file"

    again = stubs["mcp"].filesystem.read_file
    assert handle is again

    with pytest.raises(RuntimeError, match="not connected"):
        handle({})

    tool_def = builder.registry.lua_tools["mcp.filesystem.read_file"]
    assert tool_def["source"] == "mcp.filesystem.read_file"


def test_evaluations_and_steps_register():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Evaluations"]({"dataset": "file.json"})
    assert builder.registry.pydantic_evaluations["dataset"] == "file.json"

    stubs["Specifications"]("Feature: Extra")
    assert "Feature: Extra" in builder.registry.gherkin_specifications

    stubs["Step"]("Given something", lambda: None)
    assert "Given something" in builder.registry.custom_steps


def test_classify_requires_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="Classify requires"):
        stubs["Classify"]()


def test_classify_uses_agent_factory(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **kwargs):
            self.agent_factory = agent_factory

        def __call__(self, config):
            handle = self.agent_factory({"name": "classified", "system_prompt": "Hi"})
            return {"config": config, "handle": handle}

    def fake_binding_callback(*args, **kwargs):
        def raiser(*args, **kwargs):
            raise RuntimeError("boom")

        return raiser

    monkeypatch.setattr(dsl_stubs, "ClassifyPrimitive", FakeClassifyPrimitive)
    monkeypatch.setattr(dsl_stubs, "_make_binding_callback", fake_binding_callback)
    stubs = dsl_stubs.create_dsl_stubs(builder)

    result = stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert result["handle"].name.startswith("_temp_agent_")
