import builtins
import importlib.machinery
import importlib.util

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


def test_process_template_missing_key_returns_template():
    runtime = _runtime()
    runtime.config = {}

    result = runtime._process_template("Hello {missing}", {})

    assert result == "Hello "


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
