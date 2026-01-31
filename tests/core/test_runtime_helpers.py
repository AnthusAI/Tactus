import builtins
import importlib.machinery
import importlib.util
from types import SimpleNamespace

import pytest

from tactus.core.registry import (
    AgentDeclaration,
    AgentOutputSchema,
    HITLDeclaration,
    MessageHistoryConfiguration,
    OutputFieldDeclaration,
    ProcedureRegistry,
)
from tactus.core.runtime import TactusRuntime
from tactus.core import runtime as runtime_module


class DummyState:
    def all(self):
        return {"status": "ok"}


def _runtime():
    runtime = TactusRuntime(procedure_id="proc", hitl_handler=object())
    runtime.config = {}
    return runtime


def test_map_type_string_defaults():
    runtime = _runtime()

    assert runtime._map_type_string("string") is str
    assert runtime._map_type_string("number") is float
    assert runtime._map_type_string("int") is int
    assert runtime._map_type_string("bool") is bool
    assert runtime._map_type_string("unknown") is str


def test_create_pydantic_model_from_output():
    runtime = _runtime()

    schema = {
        "name": {"type": "string", "required": True},
        "count": {"type": "number", "required": False},
    }

    Model = runtime._create_pydantic_model_from_output(schema, "Output")

    model = Model(name="Ada")
    assert model.name == "Ada"
    assert model.count is None


def test_create_output_model_from_schema_required_and_default():
    runtime = _runtime()

    schema = {
        "title": {"type": "string", "required": True},
        "rating": {"type": "number", "required": False, "default": 4.5},
    }

    Model = runtime._create_output_model_from_schema(schema, model_name="OutputModel")
    model = Model(title="Hello")

    assert model.title == "Hello"
    assert model.rating == 4.5


def test_maybe_transform_script_mode_source_wraps_body():
    runtime = _runtime()

    source = """
input {
    name = field.string{required = true}
}

return { greeting = "hi" }
"""

    transformed = runtime._maybe_transform_script_mode_source(source)

    assert "Procedure {" in transformed
    assert "function(input)" in transformed
    assert 'return { greeting = "hi" }' in transformed


def test_runtime_imports_yaml_fallback_when_parser_missing(monkeypatch):
    import tactus.core.runtime as runtime_module

    original_import = builtins.__import__
    module_name = "tactus.core.runtime_missing_yaml"
    loader = importlib.machinery.SourceFileLoader(module_name, runtime_module.__file__)
    spec = importlib.util.spec_from_loader(module_name, loader)
    module = importlib.util.module_from_spec(spec)

    def fake_import(name, *args, **kwargs):
        if name == "tactus.core.yaml_parser":
            raise ImportError("missing yaml parser")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert module.ProcedureYAMLParser is None
    assert module.ProcedureConfigError is module.TactusRuntimeError


def test_maybe_transform_script_mode_source_skips_procedure():
    runtime = _runtime()

    source = """
main = Procedure {
    function(input)
        return { ok = true }
    end
}
"""

    assert runtime._maybe_transform_script_mode_source(source) == source


def test_maybe_transform_script_mode_source_skips_named_function():
    runtime = _runtime()

    source = """
function helper()
    return 1
end
"""

    assert runtime._maybe_transform_script_mode_source(source) == source


def test_maybe_transform_script_mode_tracks_long_string_and_unbalanced_end():
    runtime = _runtime()

    source = """
Specifications([[
Scenario: Example
]])
print("hi")
end
"""

    transformed = runtime._maybe_transform_script_mode_source(source)
    assert isinstance(transformed, str)


def test_maybe_transform_script_mode_long_string_single_line():
    runtime = _runtime()

    source = """
Specifications([[Scenario: Single line]])
return { ok = true }
"""

    transformed = runtime._maybe_transform_script_mode_source(source)
    assert "Procedure {" in transformed


def test_maybe_transform_script_mode_negative_function_depth():
    runtime = _runtime()

    source = """
end
return { ok = true }
"""

    transformed = runtime._maybe_transform_script_mode_source(source)
    assert "Procedure {" in transformed


def test_process_template_missing_key_returns_template():
    runtime = _runtime()
    runtime.config = {}

    result = runtime._process_template("Hello {missing}", {})

    assert result == "Hello "


def test_process_template_skips_non_dict_defaults():
    runtime = _runtime()
    runtime.config = {"input": {"topic": "AI"}}

    result = runtime._process_template("Topic {input.topic}", {})

    assert result == "Topic "


def test_format_output_schema_for_prompt():
    runtime = _runtime()
    runtime.config = {
        "output": {
            "summary": {"type": "string", "required": True, "description": "Short"},
            "score": {"type": "number", "required": False},
        }
    }

    formatted = runtime._format_output_schema_for_prompt()

    assert "Expected Output Format" in formatted
    assert "summary" in formatted
    assert "score" in formatted


def test_process_template_with_context_and_state():
    runtime = _runtime()
    runtime.config = {"input": {"topic": {"default": "AI"}}}
    runtime.state_primitive = DummyState()

    result = runtime._process_template(
        "Topic {input.topic} status {state.status} user {user}",
        {"user": "Ada"},
    )

    assert result == "Topic AI status ok user Ada"


def test_registry_to_config_includes_optional_fields():
    runtime = _runtime()

    agent_output = AgentOutputSchema(
        fields={
            "summary": OutputFieldDeclaration(name="summary", type="string", required=True),
        }
    )
    registry = ProcedureRegistry(
        description="Demo",
        input_schema={"topic": {"type": "string"}},
        output_schema={"summary": {"type": "string"}},
        state_schema={"count": {"type": "number"}},
        agents={
            "assistant": AgentDeclaration(
                name="assistant",
                provider="openai",
                model={"name": "gpt-4o"},
                system_prompt="Hi",
                tools=[],
                max_turns=7,
                disable_streaming=True,
                temperature=0.5,
                max_tokens=123,
                model_type="chat",
                inline_tools=[{"name": "tool"}],
                initial_message="Hello",
                output=agent_output,
                message_history=MessageHistoryConfiguration(source="shared", filter="keep"),
            )
        },
        hitl_points={
            "approve": HITLDeclaration(
                name="approve",
                type="approval",
                message="Ok?",
                timeout=10,
                default="yes",
                options=[{"label": "Yes", "value": "yes"}],
            )
        },
        prompts={"welcome": "Hi"},
        return_prompt="Return",
        error_prompt="Error",
        status_prompt="Status",
        default_provider="openai",
        default_model="gpt-4o-mini",
    )

    config = runtime._registry_to_config(registry)

    assert config["description"] == "Demo"
    assert config["input"]["topic"]["type"] == "string"
    assert config["output"]["summary"]["type"] == "string"
    assert config["state"]["count"]["type"] == "number"
    assert config["agents"]["assistant"]["provider"] == "openai"
    assert config["agents"]["assistant"]["model"]["name"] == "gpt-4o"
    assert config["agents"]["assistant"]["tools"] == []
    assert config["agents"]["assistant"]["inline_tools"] == [{"name": "tool"}]
    assert config["agents"]["assistant"]["initial_message"] == "Hello"
    assert config["agents"]["assistant"]["output_schema"]["summary"]["type"] == "string"
    assert config["agents"]["assistant"]["message_history"] == {
        "source": "shared",
        "filter": "keep",
    }
    assert config["hitl"]["approve"]["timeout"] == 10
    assert config["hitl"]["approve"]["default"] == "yes"
    assert config["hitl"]["approve"]["options"] == [{"label": "Yes", "value": "yes"}]
    assert config["prompts"]["welcome"] == "Hi"
    assert config["return_prompt"] == "Return"
    assert config["error_prompt"] == "Error"
    assert config["status_prompt"] == "Status"
    assert config["default_provider"] == "openai"
    assert config["default_model"] == "gpt-4o-mini"
    assert config["procedure"].startswith("-- Procedure function")


def test_registry_to_config_skips_empty_hitl_fields():
    runtime = _runtime()
    registry = ProcedureRegistry(
        hitl_points={"approve": HITLDeclaration(name="approve", type="approval", message="ok")}
    )

    config = runtime._registry_to_config(registry)

    assert config["hitl"]["approve"]["type"] == "approval"
    assert "timeout" not in config["hitl"]["approve"]


def test_create_runtime_for_procedure_inherits_context():
    runtime = TactusRuntime(
        procedure_id="root",
        storage_backend=object(),
        hitl_handler=object(),
        chat_recorder=object(),
        mcp_server=object(),
        openai_api_key="key",
        log_handler=object(),
        recursion_depth=2,
    )

    sub_runtime = runtime._create_runtime_for_procedure("child", {})

    assert sub_runtime.procedure_id.startswith("root_child_")
    assert sub_runtime.storage_backend is runtime.storage_backend
    assert sub_runtime.hitl_handler is runtime.hitl_handler
    assert sub_runtime.chat_recorder is runtime.chat_recorder
    assert sub_runtime.mcp_server is runtime.mcp_server
    assert sub_runtime.openai_api_key == "key"
    assert sub_runtime.log_handler is runtime.log_handler
    assert sub_runtime.recursion_depth == 3


def test_load_procedure_by_name_finds_file(tmp_path, monkeypatch):
    source = "main = Procedure { function(input) return { ok = true } end }"
    file_path = tmp_path / "demo.tac"
    file_path.write_text(source)

    runtime = _runtime()
    monkeypatch.chdir(tmp_path)

    assert runtime._load_procedure_by_name("demo") == source


def test_load_procedure_by_name_raises_when_missing(tmp_path, monkeypatch):
    runtime = _runtime()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError, match="Procedure 'missing' not found"):
        runtime._load_procedure_by_name("missing")


def test_parse_declarations_registers_created_agents(monkeypatch):
    runtime = _runtime()

    class DummySandbox:
        def __init__(self):
            self.globals = {}
            self.assignment_callback = None

        def set_global(self, name, value):
            self.globals[name] = value

        def setup_assignment_interception(self, callback):
            self.assignment_callback = callback

        def execute(self, _source):
            return None

        class lua:
            @staticmethod
            def globals():
                return {}

    runtime.lua_sandbox = DummySandbox()

    def fake_stubs(builder, _tool_primitive, mock_manager=None, runtime_context=None):
        runtime_context["_created_agents"]["temp"] = object()
        return {
            "_registries": {},
            "_tactus_register_binding": lambda *_args, **_kwargs: None,
            "Agent": object(),
        }

    monkeypatch.setattr(runtime_module, "create_dsl_stubs", fake_stubs)
    monkeypatch.setattr(
        runtime_module.RegistryBuilder,
        "validate",
        lambda self: SimpleNamespace(valid=True, errors=[], warnings=[], registry=self.registry),
    )

    registry = runtime._parse_declarations("return {}")

    assert "temp" in runtime.agents
    assert registry is not None
    assert runtime.lua_sandbox.assignment_callback is not None


def test_parse_declarations_skips_binding_callback(monkeypatch):
    runtime = _runtime()

    class DummySandbox:
        def __init__(self):
            self.globals = {}
            self.assignment_callback = None

        def set_global(self, name, value):
            self.globals[name] = value

        def setup_assignment_interception(self, callback):
            self.assignment_callback = callback

        def execute(self, _source):
            return None

        class lua:
            @staticmethod
            def globals():
                return {}

    runtime.lua_sandbox = DummySandbox()

    def fake_stubs(builder, _tool_primitive, mock_manager=None, runtime_context=None):
        return {"_registries": {}, "Agent": object()}

    monkeypatch.setattr(runtime_module, "create_dsl_stubs", fake_stubs)
    monkeypatch.setattr(
        runtime_module.RegistryBuilder,
        "validate",
        lambda self: SimpleNamespace(valid=True, errors=[], warnings=[], registry=self.registry),
    )

    runtime._parse_declarations("return {}")

    assert runtime.lua_sandbox.assignment_callback is None


def test_parse_declarations_raises_on_lua_error(monkeypatch):
    runtime = _runtime()

    class DummySandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            raise runtime_module.LuaSandboxError("boom")

        class lua:
            @staticmethod
            def globals():
                return {}

    runtime.lua_sandbox = DummySandbox()

    monkeypatch.setattr(
        runtime_module,
        "create_dsl_stubs",
        lambda *args, **kwargs: {"_registries": {}, "_tactus_register_binding": None},
    )

    with pytest.raises(runtime_module.TactusRuntimeError, match="Failed to parse DSL"):
        runtime._parse_declarations("return {}")


def test_parse_declarations_auto_registers_plain_main(monkeypatch):
    runtime = _runtime()

    class DummySandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

        class lua:
            @staticmethod
            def globals():
                return {"main": lambda *_args, **_kwargs: None}

    runtime.lua_sandbox = DummySandbox()

    monkeypatch.setattr(
        runtime_module,
        "create_dsl_stubs",
        lambda *args, **kwargs: {"_registries": {}, "_tactus_register_binding": None},
    )
    monkeypatch.setattr(
        runtime_module.RegistryBuilder,
        "validate",
        lambda self: SimpleNamespace(valid=True, errors=[], warnings=[], registry=self.registry),
    )

    registry = runtime._parse_declarations("function main() end")

    assert "main" in registry.named_procedures


def test_parse_declarations_validation_errors(monkeypatch):
    runtime = _runtime()

    class DummySandbox:
        def set_global(self, _name, _value):
            return None

        def execute(self, _source):
            return None

        class lua:
            @staticmethod
            def globals():
                return {}

    runtime.lua_sandbox = DummySandbox()

    monkeypatch.setattr(
        runtime_module,
        "create_dsl_stubs",
        lambda *args, **kwargs: {"_registries": {}, "_tactus_register_binding": None},
    )
    monkeypatch.setattr(
        runtime_module.RegistryBuilder,
        "validate",
        lambda self: SimpleNamespace(
            valid=False,
            errors=[SimpleNamespace(message="bad")],
            warnings=[],
            registry=self.registry,
        ),
    )

    with pytest.raises(runtime_module.TactusRuntimeError, match="DSL validation failed"):
        runtime._parse_declarations("return {}")


@pytest.mark.asyncio
async def test_setup_models_registers_models(monkeypatch):
    runtime = _runtime()
    runtime.registry = SimpleNamespace(models={"demo": {"type": "x"}})
    runtime.execution_context = object()
    runtime.mock_manager = object()

    created = []

    class DummyModel:
        def __init__(self, model_name, config, context, mock_manager):
            created.append((model_name, config, context, mock_manager))

    monkeypatch.setattr("tactus.primitives.model.ModelPrimitive", DummyModel)

    await runtime._setup_models()

    assert runtime.models["demo"]
    assert created[0][0] == "demo"


@pytest.mark.asyncio
async def test_setup_models_raises_on_error(monkeypatch):
    runtime = _runtime()
    runtime.registry = SimpleNamespace(models={"demo": {"type": "x"}})

    class BoomModel:
        def __init__(self, *args, **kwargs):
            raise ValueError("boom")

    monkeypatch.setattr("tactus.primitives.model.ModelPrimitive", BoomModel)

    with pytest.raises(ValueError, match="boom"):
        await runtime._setup_models()
