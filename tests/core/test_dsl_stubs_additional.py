from types import SimpleNamespace

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


def test_lua_table_to_dict_handles_arrays_and_dicts():
    class FakeTable:
        def __init__(self, data):
            self._data = data

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

        def __getitem__(self, key):
            return self._data[key]

    array_table = FakeTable({1: "a", 2: "b"})
    assert lua_table_to_dict(array_table) == ["a", "b"]

    mixed_table = FakeTable({1: "a", 3: "b"})
    assert lua_table_to_dict(mixed_table) == {1: "a", 3: "b"}


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


def test_procedure_array_config_extracts_run_fn():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    stubs["Procedure"]({1: run_fn, "input": {"name": {}}})
    proc = builder.registry.named_procedures["main"]
    assert proc["input_schema"] == {"name": []}


def test_procedure_config_without_getitem_uses_run_key():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigNoGetItem:
        def __init__(self):
            self._data = {"run": lambda: "ok", "input": {"name": {}}}

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigNoGetItem())
    assert "main" in builder.registry.named_procedures


def test_procedure_getitem_keyerror_falls_back_to_run():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigKeyError:
        def __init__(self):
            self._data = {"run": lambda: "ok"}

        def __getitem__(self, _key):
            raise KeyError("missing")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigKeyError())
    assert "main" in builder.registry.named_procedures


def test_procedure_getitem_keyerror_uses_run_field():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    class ConfigKeyErrorRun:
        def __init__(self):
            self._data = {"run": run_fn, "input": {}}

        def __getitem__(self, _key):
            raise KeyError("missing")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigKeyErrorRun())
    assert "main" in builder.registry.named_procedures


def test_procedure_array_callable_cleanup_to_empty_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    class CallableOnlyConfig:
        def __init__(self):
            self._data = {1: run_fn}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](CallableOnlyConfig())
    proc = builder.registry.named_procedures["main"]
    assert proc["input_schema"] == {}


def test_procedure_getitem_skips_noncallable_then_callable():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    class ConfigMixed:
        def __init__(self):
            self._data = {1: "noop", 2: run_fn, "input": {}}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigMixed())
    assert "main" in builder.registry.named_procedures


def test_procedure_array_config_keeps_non_none_entries():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    stubs["Procedure"]({1: run_fn, 2: "extra", "input": {}})
    proc = builder.registry.named_procedures["main"]
    assert proc["input_schema"] == {}


def test_procedure_type_and_missing_function_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="first argument must be a string"):
        stubs["Procedure"](123)

    with pytest.raises(TypeError, match="requires a function"):
        stubs["Procedure"]({"input": {}})


def test_procedure_array_none_values_raise():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigNoneOnly:
        def __init__(self):
            self._data = {1: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    with pytest.raises(TypeError, match="requires a function"):
        stubs["Procedure"](ConfigNoneOnly())


def test_mocks_error_key_registers_tool_mock():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Mocks"]({"failing_tool": {"error": {"message": "boom"}}})

    assert builder.registry.mocks["failing_tool"]["error"] == {"message": "boom"}


def test_tool_config_array_only_handler_normalizes_schema():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    tool = stubs["Tool"]({1: handler})
    tool_entry = builder.registry.lua_tools[tool.name]
    assert tool_entry["input"] == {}
    assert tool_entry["output"] == {}


def test_tool_config_source_without_use_is_allowed():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = stubs["Tool"]({"source": "broker.host.ping"})
    tool_entry = builder.registry.lua_tools[tool.name]
    assert tool_entry["source"] == "broker.host.ping"


def test_tool_config_use_sets_source():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = stubs["Tool"]({"use": "broker.host.ping"})
    tool_entry = builder.registry.lua_tools[tool.name]
    assert tool_entry["source"] == "broker.host.ping"


def test_tool_config_use_and_source_conflict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="both 'use' and 'source'"):
        stubs["Tool"]({"use": "broker.host.ping", "source": "broker.host.ping"})


def test_tool_config_handler_key_is_accepted():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    tool = stubs["Tool"]({"handler": handler, "input": {}})
    tool_entry = builder.registry.lua_tools[tool.name]
    assert tool_entry["input"] == {}


def test_tool_config_array_only_handler_cleans_to_empty_dict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    class CallableOnlyConfig:
        def __init__(self):
            self._data = {1: handler}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    tool = stubs["Tool"](CallableOnlyConfig())
    tool_entry = builder.registry.lua_tools[tool.name]
    assert tool_entry["input"] == {}


def test_tool_temp_name_binding_reregisters():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    bind = stubs["_tactus_register_binding"]

    tool = stubs["Tool"]({"use": "broker.host.ping"})
    old_name = tool.name

    assert old_name in builder.registry.lua_tools
    bind("renamed_tool", tool)

    assert "renamed_tool" in builder.registry.lua_tools
    assert old_name not in builder.registry.lua_tools


def test_tool_explicit_name_validation():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    with pytest.raises(TypeError, match="Tool 'name' must be a string"):
        stubs["Tool"]({"name": 123, 1: handler})

    with pytest.raises(TypeError, match="Tool 'name' cannot be empty"):
        stubs["Tool"]({"name": "   ", 1: handler})


def test_tool_explicit_name_applied():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = stubs["Tool"]({"name": "explicit_tool", "use": "broker.host.ping"})
    assert tool.name == "explicit_tool"


def test_tool_explicit_name_mismatch_raises():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    bind = stubs["_tactus_register_binding"]

    tool = stubs["Tool"]({"name": "explicit_tool", "use": "broker.host.ping"})
    with pytest.raises(RuntimeError, match="Tool name mismatch"):
        bind("renamed_tool", tool)


def test_curried_agent_inline_tools_requires_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    curried = stubs["Agent"]("alpha")
    with pytest.raises(ValueError, match="inline_tools"):
        curried({"inline_tools": {"handler": "nope"}})


def test_assignment_agent_inline_tools_requires_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"inline_tools": {"handler": "nope"}})


def test_agent_inline_tools_none_is_allowed():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Agent"]({"provider": "openai", "model": "gpt-4o", "inline_tools": None})


def test_curried_agent_inline_tools_none_is_allowed():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    curried = stubs["Agent"]("alpha")
    curried({"provider": "openai", "model": "gpt-4o", "inline_tools": None})


def test_agent_creation_runtime_context_records_created_agents(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": None}

    class DummyAgent:
        def __init__(self, name):
            self.name = name
            self.log_handler = None

    monkeypatch.setattr(
        "tactus.dspy.agent.create_dspy_agent",
        lambda name, *_args, **_kwargs: DummyAgent(name),
    )

    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    stubs["Agent"]({"provider": "openai", "model": "gpt-4o"})


def test_agent_binding_renames_and_updates_created_agents(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": None, "_created_agents": {}}

    class DummyAgent:
        def __init__(self, name):
            self.name = name
            self.log_handler = None

    monkeypatch.setattr(
        "tactus.dspy.agent.create_dspy_agent",
        lambda name, *_args, **_kwargs: DummyAgent(name),
    )

    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    bind = stubs["_tactus_register_binding"]

    agent_handle = stubs["Agent"]({"provider": "openai", "model": "gpt-4o", "system_prompt": "hi"})
    old_name = agent_handle.name

    assert old_name in builder.registry.agents
    assert old_name in runtime_context["_created_agents"]

    bind("renamed_agent", agent_handle)

    assert "renamed_agent" in builder.registry.agents
    assert "renamed_agent" in runtime_context["_created_agents"]

    assert "_created_agents" in runtime_context
    assert runtime_context["_created_agents"]


def test_classify_agent_factory_renames_handle(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    created = {}

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **_kwargs):
            self.agent_factory = agent_factory

        def __call__(self, _config):
            created["handle"] = self.agent_factory(
                {"name": "stable_agent", "provider": "openai", "model": "gpt-4o"}
            )
            return {"ok": True}

    monkeypatch.setattr("tactus.core.dsl_stubs.ClassifyPrimitive", FakeClassifyPrimitive)

    stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert created["handle"].name == "stable_agent"


def test_classify_agent_factory_without_name(monkeypatch):
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    created = {}

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **_kwargs):
            self.agent_factory = agent_factory

        def __call__(self, _config):
            created["handle"] = self.agent_factory({"provider": "openai", "model": "gpt-4o"})
            return {"ok": True}

    monkeypatch.setattr("tactus.core.dsl_stubs.ClassifyPrimitive", FakeClassifyPrimitive)

    stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert created["handle"].name.startswith("_temp_agent_")


def test_binding_callback_renames_agent_handle(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": None, "_created_agents": {}}

    class DummyAgent:
        def __init__(self, name):
            self.name = name
            self.log_handler = None

    monkeypatch.setattr(
        "tactus.dspy.agent.create_dspy_agent",
        lambda name, *_args, **_kwargs: DummyAgent(name),
    )

    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    handle = stubs["Agent"]({"provider": "openai", "model": "gpt-4o"})
    old_name = handle.name

    runtime_context["_created_agents"][old_name] = DummyAgent(old_name)
    builder.registry.agents[old_name] = SimpleNamespace(name=old_name)

    bind = stubs["_tactus_register_binding"]
    bind("renamed_agent", handle)

    assert handle.name == "renamed_agent"
    assert "renamed_agent" in runtime_context["_created_agents"]


def test_binding_callback_tool_name_mismatch_raises():
    builder = RegistryBuilder()
    runtime_context = {}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    bind = stubs["_tactus_register_binding"]

    tool = ToolHandle("fixed_name", lambda: None, None)
    with pytest.raises(RuntimeError, match="Tool name mismatch"):
        bind("other_name", tool)


def test_binding_callback_updates_created_agents_registry():
    builder = RegistryBuilder()
    runtime_context = {"_created_agents": {}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    bind = stubs["_tactus_register_binding"]

    agent = AgentHandle("_temp_agent_1234")
    agent._primitive = SimpleNamespace(name=agent.name)
    runtime_context["_created_agents"][agent.name] = agent._primitive

    bind("renamed", agent)

    assert agent.name == "renamed"
    assert "renamed" in runtime_context["_created_agents"]


def test_procedure_array_multiple_none_values_raise():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigNoneOnly:
        def __init__(self):
            self._data = {1: None, 2: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    with pytest.raises(TypeError, match="requires a function"):
        stubs["Procedure"](ConfigNoneOnly())


def test_procedure_getitem_typeerror_falls_back_to_run():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigTypeError:
        def __init__(self):
            self._data = {"run": lambda: "ok"}

        def __getitem__(self, _key):
            raise TypeError("bad")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigTypeError())
    assert "main" in builder.registry.named_procedures


def test_procedure_loop_exhausts_without_callable():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ConfigNoCallable:
        def __init__(self):
            self._data = {"run": lambda: "ok"}

        def __getitem__(self, _key):
            return "noop"

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigNoCallable())
    assert "main" in builder.registry.named_procedures


def test_procedure_array_cleanup_with_only_none_values():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run_fn():
        return "ok"

    class ConfigCallableWithNone:
        def __init__(self):
            self._data = {1: run_fn, 2: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigCallableWithNone())
    proc = builder.registry.named_procedures["main"]
    assert proc["input_schema"] == {}


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


def test_specification_table_without_from_registers_text():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Specification"]({"text": "Feature: Inline"})
    assert builder.registry.gherkin_specifications


def test_evaluation_routes_configs():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Evaluation"]({"dataset": "foo", "evaluators": []})
    assert builder.registry.pydantic_evaluations["dataset"] == "foo"

    stubs["Evaluation"]({"runs": 3})
    assert builder.registry.evaluation_config["runs"] == 3


def test_field_builder_handles_lua_table_and_empty_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class FakeTable:
        def __init__(self, data):
            self._data = data

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

        def __getitem__(self, key):
            return self._data[key]

    field_string = stubs["field"]["string"]
    assert field_string(FakeTable({"required": True}))["required"] is True
    assert field_string([])["type"] == "string"


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


def test_tool_config_without_callable_uses_handler_key():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"]({"handler": handler, "name": "helper"})
    assert handle({"x": 1}) == {"x": 1}


def test_tool_config_noncallable_item_with_source():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Tool"]({1: "noop", "use": "broker.host.ping", "name": "ping"})
    assert handle.name == "ping"


def test_tool_config_list_cleanup():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"]({1: handler, 2: None, "name": "clean"})
    assert handle.name == "clean"


def test_tool_list_cleanup_and_handler_source_conflict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    stubs["Tool"]({1: handler})
    assert len(builder.registry.lua_tools) == 1

    with pytest.raises(TypeError, match="function and 'use"):
        stubs["Tool"]({1: handler, "use": "broker.host.ping"})


def test_tool_extracts_handler_from_array_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(_input=None):
        return {"ok": True}

    handle = stubs["Tool"]({1: handler, "input": {}, "output": {}})
    assert handle.name in builder.registry.lua_tools


def test_agent_inline_tools_validation_errors():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"inline_tools": ["bad"]})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"inline_tools": "bad"})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]({"inline_tools": {"name": "inline"}})


def test_agent_inline_tools_allows_dict_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Agent"](
        {
            "system_prompt": "Hi",
            "inline_tools": [{"name": "inline", "handler": lambda *_args, **_kwargs: None}],
        }
    )
    assert handle.name in builder.registry.agents


def test_agent_direct_tools_non_list_skips_normalization():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Agent"](
        {"system_prompt": "Hi", "tools": "raw_tool", "provider": "openai", "model": "gpt-4o"}
    )
    assert handle.name.startswith("_temp_agent_")
    assert any("Invalid agent" in msg.message for msg in builder.validation_messages)


def test_agent_direct_tools_handle_and_schema_non_dicts():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = ToolHandle("ping", lambda args: "ok")
    handle = stubs["Agent"](
        {
            "system_prompt": "Hi",
            "tools": [tool, {"filter": "x"}, "raw"],
            "input": [],
            "output": [],
            "provider": "openai",
            "model": "gpt-4o",
        }
    )
    assert handle.name.startswith("_temp_agent_")
    assert any("Invalid agent" in msg.message for msg in builder.validation_messages)


def test_agent_tools_normalizes_handles_and_rejects_inline_tools():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool_handle = ToolHandle("demo", lambda _ctx: None)
    accept = stubs["Agent"]("agent1")
    handle = accept(
        {
            "provider": "openai",
            "model": "gpt-4o",
            "tools": [tool_handle, "raw"],
            "system_prompt": "hi",
            "input": {},
            "output": {},
        }
    )
    assert handle.name == "agent1"

    with pytest.raises(ValueError, match="inline tool definitions"):
        stubs["Agent"]({"tools": [{"handler": lambda _ctx: None}]})


def test_agent_rejects_session_alias():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="session"):
        stubs["Agent"]({"session": {"messages": []}})


def test_agent_immediate_creation_populates_runtime_context(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {
        "log_handler": object(),
        "tool_primitive": object(),
        "execution_context": object(),
    }
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    class DummyAgent:
        def __init__(self):
            self.log_handler = None
            self._tool_primitive = None

    def fake_create_agent(_name, _config, registry=None, mock_manager=None):
        return DummyAgent()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_agent)

    accept = stubs["Agent"]("demo")
    handle = accept(
        {
            "provider": "openai",
            "model": "gpt-4o",
            "system_prompt": "hi",
        }
    )

    assert handle.name == "demo"
    assert "demo" in runtime_context["_created_agents"]


def test_agent_immediate_creation_adds_created_agents_dict(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": object()}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    def fake_create_agent(_name, _config, registry=None, mock_manager=None):
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_agent)

    stubs["Agent"]("demo")({"provider": "openai", "model": "gpt-4o", "system_prompt": "hi"})
    assert "_created_agents" in runtime_context


def test_agent_immediate_creation_uses_existing_created_agents(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": object(), "_created_agents": {"existing": "sentinel"}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    def fake_create_agent(_name, _config, registry=None, mock_manager=None):
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_agent)

    stubs["Agent"]("demo")({"provider": "openai", "model": "gpt-4o", "system_prompt": "hi"})
    assert runtime_context["_created_agents"]["existing"] == "sentinel"
    assert "demo" in runtime_context["_created_agents"]


def test_agent_immediate_creation_without_log_handler(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"mock_manager": object()}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    captured = {}

    class DummyAgent:
        def __init__(self):
            self.log_handler = None
            self._tool_primitive = None

    def fake_create_agent(_name, config, registry=None, mock_manager=None):
        captured["config"] = config
        return DummyAgent()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_agent)

    accept = stubs["Agent"]("demo")
    handle = accept(
        {
            "provider": "openai",
            "model": "gpt-4o",
            "system_prompt": "hi",
        }
    )

    assert handle.name == "demo"
    assert "log_handler" not in captured["config"]


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


def test_tool_getitem_indexerror_falls_back_to_handler_key():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ToolConfigIndexError:
        def __init__(self):
            self._data = {"handler": lambda args: {"ok": True}}

        def __getitem__(self, _key):
            raise IndexError("missing")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](ToolConfigIndexError())
    assert handle.name in builder.registry.lua_tools


def test_tool_config_without_getitem_skips_array_scan():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    class ToolConfigNoGetItem:
        def __init__(self):
            self._data = {"handler": handler}

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](ToolConfigNoGetItem())
    assert handle.name in builder.registry.lua_tools


def test_tool_config_empty_list_raises():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(TypeError, match="requires either a function"):
        stubs["Tool"]([])


def test_tool_loop_exhausts_then_uses_handler_key():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ToolConfigNoCallable:
        def __init__(self):
            self._data = {"handler": lambda args: {"ok": True}}

        def __getitem__(self, _key):
            return "noop"

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](ToolConfigNoCallable())
    assert handle.name in builder.registry.lua_tools


def test_tool_array_cleanup_with_only_none_values():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    class ToolConfigCallableWithNone:
        def __init__(self):
            self._data = {1: handler, 2: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](ToolConfigCallableWithNone())
    assert handle.name in builder.registry.lua_tools


def test_tool_normalizes_empty_schemas():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"]({"name": "normalized", "handler": handler, "input": [], "output": []})
    tool_def = builder.registry.lua_tools[handle.name]
    assert tool_def["input"] == {}
    assert tool_def["output"] == {}


def test_tool_source_uses_source_key():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Tool"]({"name": "source_only", "source": "mcp.filesystem.read_file"})
    tool_def = builder.registry.lua_tools[handle.name]
    assert tool_def["source"] == "mcp.filesystem.read_file"


def test_tool_explicit_name_is_used():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"]({"name": "explicit", "handler": handler})
    assert handle.name == "explicit"


def test_mocks_registers_error_config():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Mocks"]({"tool": {"error": "boom"}})
    assert builder.registry.mocks["tool"]["error"] == "boom"


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

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]("curried")({"inline_tools": {"name": "inline"}})

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


def test_agent_curried_inline_tools_allows_dict_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Agent"]("curried_inline")(
        {
            "system_prompt": "Hi",
            "inline_tools": [{"name": "inline", "handler": lambda *_args, **_kwargs: None}],
        }
    )

    assert handle.name == "curried_inline"


def test_agent_curried_tools_non_list_skips_normalization():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Agent"]("curried_tools")(
        {"system_prompt": "Hi", "tools": "raw_tool", "provider": "openai", "model": "gpt-4o"}
    )
    assert handle.name == "curried_tools"
    assert any("Invalid agent" in msg.message for msg in builder.validation_messages)


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


def test_binding_callback_updates_internal_registries_and_primitives():
    builder = RegistryBuilder()
    runtime_context = {"_created_agents": {}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    callback = stubs["_tactus_register_binding"]
    tool_registry = stubs["_registries"]["tool"]
    agent_registry = stubs["_registries"]["agent"]

    tool_handle = ToolHandle("_temp_tool_abc", lambda args: "ok")
    tool_registry[tool_handle.name] = tool_handle
    builder.registry.lua_tools[tool_handle.name] = {"description": "temp"}
    callback("final_tool", tool_handle)

    assert "final_tool" in tool_registry
    assert "final_tool" in builder.registry.lua_tools

    agent_handle = AgentHandle("_temp_agent_abc")
    agent_handle._primitive = SimpleNamespace(name=agent_handle.name)
    agent_registry[agent_handle.name] = agent_handle
    builder.registry.agents[agent_handle.name] = {"name": agent_handle.name}
    runtime_context["_created_agents"][agent_handle.name] = agent_handle._primitive
    callback("final_agent", agent_handle)

    assert "final_agent" in agent_registry
    assert "final_agent" in builder.registry.agents
    assert runtime_context["_created_agents"]["final_agent"] is agent_handle._primitive
    assert agent_handle._primitive.name == "final_agent"


def test_binding_callback_skips_missing_builder_entries():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    callback = stubs["_tactus_register_binding"]
    tool_registry = stubs["_registries"]["tool"]

    tool_handle = ToolHandle("_temp_tool_missing", lambda args: "ok")
    tool_registry[tool_handle.name] = tool_handle

    callback("final_tool", tool_handle)
    assert tool_handle.name == "final_tool"


def test_binding_callback_agent_missing_registry_entries():
    builder = RegistryBuilder()
    runtime_context = {"_created_agents": {"other": object()}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    callback = stubs["_tactus_register_binding"]
    agent_registry = stubs["_registries"]["agent"]

    agent_handle = AgentHandle("_temp_agent_missing")
    agent_registry[agent_handle.name] = agent_handle

    callback("renamed", agent_handle)
    assert agent_handle.name == "renamed"


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


def test_message_includes_metadata_in_dict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    message = stubs["Message"]({"role": "assistant", "content": "hi", "id": "m1"})
    assert message.to_dict()["id"] == "m1"


def test_message_to_dict_without_metadata():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    message = stubs["Message"]({"role": "user", "content": "hi"})
    assert message.to_dict() == {"role": "user", "content": "hi"}


def test_mocks_error_branch_registers():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Mocks"]({"boom": {"error": "fail"}})
    assert builder.registry.mocks["boom"]["error"] == "fail"


class LuaTable:
    def __init__(self, data):
        self._data = dict(data)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def keys(self):
        return list(self._data.keys())

    def items(self):
        return list(self._data.items())


def test_tool_array_config_extracts_handler_and_cleans_list():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"](LuaTable({1: handler}))
    assert isinstance(handle, ToolHandle)


def test_tool_array_config_with_keyerror_uses_source():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class ToolConfigKeyError:
        def __init__(self):
            self._data = {"use": "broker.host.ping"}

        def __getitem__(self, _key):
            raise KeyError("missing")

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](ToolConfigKeyError())
    assert isinstance(handle, ToolHandle)


def test_tool_array_config_cleans_empty_list_after_handler():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    class CallableOnlyConfig:
        def __init__(self):
            self._data = {1: handler}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    handle = stubs["Tool"](CallableOnlyConfig())
    assert isinstance(handle, ToolHandle)


def test_tool_config_normalizes_input_output_schema():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"](LuaTable({1: handler, "input": {"value": {}}, "output": {"ok": {}}}))
    assert handle.name in builder.registry.lua_tools
    tool_def = builder.registry.lua_tools[handle.name]
    assert tool_def["input"] == {"value": []}
    assert tool_def["output"] == {"ok": []}


def test_tool_use_and_source_validation():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Tool"]({"use": "broker.host.ping"})
    tool_def = builder.registry.lua_tools[handle.name]
    assert tool_def["source"] == "broker.host.ping"

    with pytest.raises(TypeError, match="both 'use' and 'source'"):
        stubs["Tool"]({"use": "broker.host.ping", "source": "other"})

    with pytest.raises(TypeError, match="Tool 'name' cannot be empty"):
        stubs["Tool"]({"use": "broker.host.ping", "name": " "})

    with pytest.raises(TypeError, match="Tool 'name' must be a string"):
        stubs["Tool"]({"use": "broker.host.ping", "name": 123})


def test_tool_source_only_registers():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    handle = stubs["Tool"]({"source": "mcp.filesystem.read_file"})
    tool_def = builder.registry.lua_tools[handle.name]
    assert tool_def["source"] == "mcp.filesystem.read_file"


def test_tool_handler_field_and_bad_array_getitem():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler(args):
        return args

    handle = stubs["Tool"]({"handler": handler})
    assert handle.name in builder.registry.lua_tools

    class BadTable:
        def __getitem__(self, _key):
            raise TypeError("boom")

        def keys(self):
            return []

        def items(self):
            return []

    with pytest.raises(TypeError, match="requires a configuration table"):
        stubs["Tool"](None)

    with pytest.raises(TypeError, match="requires either a function or"):
        stubs["Tool"](BadTable())


def test_agent_inline_tools_validation_and_tools_normalization():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]("bad")({"system_prompt": "hi", "inline_tools": ["nope"]})

    with pytest.raises(ValueError, match="inline_tools"):
        stubs["Agent"]("bad2")({"system_prompt": "hi", "inline_tools": "nope"})

    with pytest.raises(ValueError, match="inline tool definitions"):
        stubs["Agent"]("bad3")({"system_prompt": "hi", "tools": [{"handler": lambda: None}]})

    handle = ToolHandle("search", lambda *_args, **_kwargs: None)
    config = stubs["Agent"]("ok")({"system_prompt": "hi", "tools": [handle, "other"]})
    assert config.name == "ok"


def test_agent_session_alias_rejected():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    with pytest.raises(ValueError, match="session"):
        stubs["Agent"](
            {
                "system_prompt": "hi",
                "provider": "openai",
                "model": "gpt-4o",
                "session": "s",
            }
        )


def test_agent_immediate_creation_sets_log_handler_and_tool_primitive(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": object(), "tool_primitive": object()}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    created = {}

    def fake_agent(name, cfg, **_kwargs):
        created["cfg"] = cfg
        return SimpleNamespace()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    stubs["Agent"]("helper")({"system_prompt": "Hi", "provider": "openai", "model": "gpt-4o"})
    assert created["cfg"]["log_handler"] is runtime_context["log_handler"]


def test_agent_inline_creation_updates_created_agents(monkeypatch):
    builder = RegistryBuilder()
    runtime_context = {"log_handler": object(), "_created_agents": {}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    def fake_agent(name, cfg, **_kwargs):
        return SimpleNamespace(name=name)

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)

    handle = stubs["Agent"]({"system_prompt": "Hi", "provider": "openai", "model": "gpt-4o"})
    assert handle.name.startswith("_temp_agent_")
    assert handle.name in runtime_context["_created_agents"]


def test_agent_immediate_creation_sets_tool_primitive(monkeypatch):
    builder = RegistryBuilder()
    tool_primitive = object()
    runtime_context = {"tool_primitive": tool_primitive}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)

    created = {}

    def fake_agent(name, cfg, **_kwargs):
        created["agent"] = SimpleNamespace()
        return created["agent"]

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_agent)
    handle = stubs["Agent"]({"system_prompt": "Hi", "provider": "openai", "model": "gpt-4o"})
    assert handle._primitive._tool_primitive is tool_primitive


def test_binding_callback_renames_tool_and_agent():
    builder = RegistryBuilder()
    runtime_context = {"_created_agents": {}}
    stubs = create_dsl_stubs(builder, runtime_context=runtime_context)
    bind = stubs["_tactus_register_binding"]

    tool = ToolHandle("_temp_tool_abc123", lambda *_args, **_kwargs: None)
    builder.registry.lua_tools[tool.name] = {"name": tool.name}
    bind("search", tool)
    assert tool.name == "search"
    assert "search" in builder.registry.lua_tools

    agent = AgentHandle("_temp_agent_abc123")
    builder.registry.agents[agent.name] = {"name": agent.name}
    runtime_context["_created_agents"][agent.name] = SimpleNamespace(name=agent.name)
    bind("assistant", agent)
    assert agent.name == "assistant"
    assert "assistant" in builder.registry.agents
    assert "assistant" in runtime_context["_created_agents"]

    with pytest.raises(RuntimeError, match="Tool name mismatch"):
        bind("other", ToolHandle("named", lambda *_args, **_kwargs: None))


def test_classify_binding_callback_best_effort(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **kwargs):
            self.agent_factory = agent_factory

        def __call__(self, config):
            return self.agent_factory({"name": "named", "system_prompt": "Hi"})

    called = []

    def fake_binding_callback(*_args, **_kwargs):
        def binder(name, handle):
            called.append((name, handle.name))

        return binder

    monkeypatch.setattr(dsl_stubs, "ClassifyPrimitive", FakeClassifyPrimitive)
    monkeypatch.setattr(dsl_stubs, "_make_binding_callback", fake_binding_callback)
    stubs = dsl_stubs.create_dsl_stubs(builder)

    handle = stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert called == [("named", handle.name)]


def test_classify_agent_factory_without_name(monkeypatch):  # noqa: F811
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **kwargs):
            self.agent_factory = agent_factory

        def __call__(self, config):
            return self.agent_factory({"system_prompt": "Hi"})

    def fake_binding_callback(*_args, **_kwargs):
        def binder(*_args, **_kwargs):
            raise AssertionError("should not be called")

        return binder

    monkeypatch.setattr(dsl_stubs, "ClassifyPrimitive", FakeClassifyPrimitive)
    monkeypatch.setattr(dsl_stubs, "_make_binding_callback", fake_binding_callback)
    stubs = dsl_stubs.create_dsl_stubs(builder)

    handle = stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert handle.name.startswith("_temp_agent_")


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
            "invalid": {"conditional": ["bad", {"when": {"q": "x"}}]},
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


def test_procedure_array_only_function_cleans_to_empty_dict():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run():
        return {"ok": True}

    class CallableOnlyConfig:
        def __init__(self):
            self._data = {1: run}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](CallableOnlyConfig())
    assert "main" in builder.registry.named_procedures


def test_procedure_array_with_none_items_skips_empty_cleanup():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run():
        return {"ok": True}

    class ConfigWithNone:
        def __init__(self):
            self._data = {1: run, 2: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigWithNone())
    assert "main" in builder.registry.named_procedures


def test_procedure_array_with_extra_item_ignored():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def run():
        return {"ok": True}

    class ConfigWithExtra:
        def __init__(self):
            self._data = {1: run, 2: "extra"}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    stubs["Procedure"](ConfigWithExtra())
    assert "main" in builder.registry.named_procedures


def test_tool_handler_only_without_source_is_allowed():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    tool = stubs["Tool"]({1: handler})
    tool_entry = builder.registry.lua_tools[tool.name]
    assert "source" not in tool_entry


def test_mocks_with_error_config_registers_error():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    stubs["Mocks"]({"tool": {"error": "boom"}})

    assert builder.registry.mocks["tool"]["error"] == "boom"


def test_tool_config_array_with_none_items_skips_empty_cleanup():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    class ConfigWithNone:
        def __init__(self):
            self._data = {1: handler, 2: None}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    tool = stubs["Tool"](ConfigWithNone())
    assert tool.name in builder.registry.lua_tools


def test_tool_config_array_with_extra_item_ignored():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    class ConfigWithExtra:
        def __init__(self):
            self._data = {1: handler, 2: "extra"}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            return list(self._data.keys())

        def items(self):
            return list(self._data.items())

    tool = stubs["Tool"](ConfigWithExtra())
    assert tool.name in builder.registry.lua_tools


def test_tool_config_non_dict_raises_typeerror():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    class BadConfig:
        def __getitem__(self, _key):
            raise TypeError("nope")

        def keys(self):
            raise TypeError("nope")

        def items(self):
            raise TypeError("nope")

    with pytest.raises(TypeError, match="Tool requires either a function or 'use"):
        stubs["Tool"](BadConfig())


def test_tool_config_non_dict_with_handler_raises_attribute_error():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    def handler():
        return "ok"

    class BadConfig:
        def __init__(self):
            self._data = {1: handler}

        def __getitem__(self, key):
            return self._data[key]

        def __setitem__(self, key, value):
            self._data[key] = value

        def keys(self):
            raise TypeError("nope")

        def items(self):
            raise TypeError("nope")

    with pytest.raises(AttributeError):
        stubs["Tool"](BadConfig())


def test_tool_config_source_with_name_registers_source():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)

    tool = stubs["Tool"]({"name": "custom_tool", "source": "broker.ping"})

    assert tool.name == "custom_tool"
    assert builder.registry.lua_tools["custom_tool"]["source"] == "broker.ping"


def test_agent_binding_updates_created_agents_dict(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class DummyAgent:
        def __init__(self):
            self.name = "temp"

    def fake_create_dspy_agent(*args, **kwargs):
        return DummyAgent()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_dspy_agent)

    runtime_context = {"execution_context": None}
    stubs = dsl_stubs.create_dsl_stubs(builder, runtime_context=runtime_context)
    bind = stubs["_tactus_register_binding"]

    agent = stubs["Agent"]({"system_prompt": "Hi"})
    old_name = agent.name
    assert old_name in runtime_context["_created_agents"]

    bind("renamed_agent", agent)
    assert "renamed_agent" in runtime_context["_created_agents"]
    assert old_name not in runtime_context["_created_agents"]


def test_agent_creation_uses_existing_created_agents(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class DummyAgent:
        def __init__(self, name):
            self.name = name

    def fake_create_dspy_agent(name, *_args, **_kwargs):
        return DummyAgent(name)

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_dspy_agent)

    runtime_context = {"execution_context": None, "_created_agents": {"existing": "sentinel"}}
    stubs = dsl_stubs.create_dsl_stubs(builder, runtime_context=runtime_context)

    agent = stubs["Agent"]({"system_prompt": "Hi"})

    assert runtime_context["_created_agents"]["existing"] == "sentinel"
    assert runtime_context["_created_agents"][agent.name].name == agent.name


def test_agent_binding_skips_created_agents_init_when_present(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class DummyAgent:
        def __init__(self):
            self.name = "temp"

    def fake_create_dspy_agent(*args, **kwargs):
        return DummyAgent()

    monkeypatch.setattr("tactus.dspy.agent.create_dspy_agent", fake_create_dspy_agent)

    runtime_context = {"execution_context": None, "_created_agents": {}}
    stubs = dsl_stubs.create_dsl_stubs(builder, runtime_context=runtime_context)
    _ = stubs["Agent"]({"system_prompt": "Hi"})
    assert runtime_context["_created_agents"]


def test_binding_callback_allows_matching_tool_name():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    bind = stubs["_tactus_register_binding"]

    tool = stubs["Tool"]({"name": "explicit_tool", "use": "broker.host.ping"})
    bind(tool.name, tool)


def test_binding_callback_allows_matching_agent_name():
    builder = RegistryBuilder()
    stubs = create_dsl_stubs(builder)
    bind = stubs["_tactus_register_binding"]

    from tactus.primitives.handles import AgentHandle

    agent = AgentHandle("agent")
    bind(agent.name, agent)


def test_classify_agent_factory_handles_non_dict(monkeypatch):
    import tactus.core.dsl_stubs as dsl_stubs

    builder = RegistryBuilder()

    class FakeClassifyPrimitive:
        def __init__(self, agent_factory, **kwargs):
            self.agent_factory = agent_factory

        def __call__(self, config):
            return self.agent_factory("not-a-dict")

    monkeypatch.setattr(dsl_stubs, "ClassifyPrimitive", FakeClassifyPrimitive)
    stubs = dsl_stubs.create_dsl_stubs(builder)

    result = stubs["Classify"]({"classes": ["a"], "prompt": "p"})
    assert callable(result)
