from tactus.validation.validator import TactusValidator, ValidationMode


def test_model_assignment_registers_model():
    source = """
    my_model = Model {
        provider = "openai",
        name = "gpt-4o"
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.models


def test_toolset_declaration_registers():
    source = """
    my_toolset = Toolset {
        tools = {}
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "my_toolset" in result.registry.toolsets


def test_tool_method_call_is_not_treated_as_declaration():
    source = "Tool.called()"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.lua_tools == {}


def test_assignment_defaults_and_limits_set():
    source = """
    default_provider = "openai"
    default_model = "gpt-4o"
    max_turns = 7
    async = true
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.default_provider == "openai"
    assert result.registry.default_model == "gpt-4o"
    assert result.registry.max_turns == 7
    assert result.registry.async_enabled is True


def test_procedure_with_config_extracts_schemas():
    source = """
    Procedure {
        input = { name = "string" },
        output = { greeting = "string" },
        state = { count = "number" }
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "main" in result.registry.named_procedures


def test_procedure_with_function_only_table_registers_main():
    source = """
    Procedure {
        function(input)
            return { ok = true }
        end
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "main" in result.registry.named_procedures


def test_evaluation_non_dict_sets_empty_config():
    source = 'Evaluation("quick")'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.evaluation_config == {}


def test_evaluation_with_dataset_registers_evaluations():
    source = """
    Evaluation {
        dataset = {
            { name = "case", inputs = { query = "hi" } }
        },
        evaluators = {
            { type = "contains", value = "hi" }
        }
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "dataset" in result.registry.pydantic_evaluations


def test_default_settings_function_calls():
    source = """
    default_provider("openai")
    default_model("gpt-4o")
    return_prompt("ok")
    error_prompt("nope")
    status_prompt("status")
    async(true)
    max_depth(4)
    max_turns(9)
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.default_provider == "openai"
    assert result.registry.default_model == "gpt-4o"
    assert result.registry.return_prompt == "ok"
    assert result.registry.error_prompt == "nope"
    assert result.registry.status_prompt == "status"
    assert result.registry.async_enabled is True
    assert result.registry.max_depth == 4
    assert result.registry.max_turns == 9


def test_top_level_input_with_field_builder_schema():
    source = """
    input {
        name = field.string{
            required = true,
            default = "Ada",
            description = "Person name",
            enum = {"Ada", "Bob"}
        }
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    schema = result.registry.top_level_input_schema["name"]
    assert schema["type"] == "string"
    assert schema["required"] is True
    assert "default" not in schema
    assert schema["description"] == "Person name"
    assert schema["enum"] == ["Ada", "Bob"]


def test_top_level_input_builder_allows_default_when_not_required():
    source = """
    input {
        name = field.string{
            default = "Ada"
        }
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    schema = result.registry.top_level_input_schema["name"]
    assert schema["required"] is False
    assert schema["default"] == "Ada"


def test_old_type_syntax_in_field_reports_error():
    source = """
    input {
        name = { type = "string", required = true }
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Old type syntax detected" in err.message for err in result.errors)


def test_hex_number_assignment_parsed():
    source = "max_turns = 0x10"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.max_turns == "0x10"


def test_name_long_string_literal_reports_error():
    source = "name [[Morning Run]]"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Error processing name" in err.message for err in result.errors)


def test_evaluations_non_dict_registers_empty():
    source = 'Evaluations("quick")'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.pydantic_evaluations == {}


def test_assignment_agent_without_config_registers():
    source = "greeter = Agent()"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Invalid agent" in err.message for err in result.errors)


def test_assignment_agent_with_name_arg_registers():
    source = 'greeter = Agent("greeter")'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("lookup syntax is deprecated" in err.message for err in result.errors)


def test_agent_turn_method_chain_reports_error():
    source = 'Agent("helper").turn()'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("turn() method is deprecated" in err.message for err in result.errors)


def test_prompt_parses_escaped_string():
    source = 'Prompt "greeting" "Hello\\nWorld"'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.prompts["greeting"] == "Hello\nWorld"


def test_prompt_parses_single_quoted_string():
    source = "Prompt 'greeting' 'Hi\\tthere'"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.prompts["greeting"] == "Hi\tthere"


def test_prompt_parses_long_string_literal():
    source = 'Prompt "greeting" [[Hello\nWorld]]'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.prompts["greeting"] == "Hello\nWorld"


def test_toolset_tools_array_literal():
    source = """
    my_toolset = Toolset {
        tools = {"ping", "pong"}
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    tools = result.registry.toolsets["my_toolset"]["tools"]
    assert tools == ["ping", "pong"]


def test_toolset_tools_mixed_table():
    source = """
    my_toolset = Toolset {
        tools = {"ping", key = "pong"}
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    tools = result.registry.toolsets["my_toolset"]["tools"]
    assert tools["key"] == "pong"
    assert tools[1] == "ping"


def test_toolset_tools_empty_table():
    source = """
    my_toolset = Toolset {
        tools = {}
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    tools = result.registry.toolsets["my_toolset"]["tools"]
    assert tools == []


def test_indexed_field_in_table_is_ignored():
    source = """
    input {
        ["key"] = "value"
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None


def test_return_prompt_nil_assignment():
    source = "return_prompt = nil"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.return_prompt is None


def test_procedure_named_curried_registers():
    source = 'Procedure "custom" {}'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "custom" in result.registry.named_procedures


def test_procedure_invalid_argument_type_is_ignored():
    source = "Procedure(123)"
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "main" not in result.registry.named_procedures


def test_hitl_declaration_registers():
    source = """
    Hitl "approve" {
        type = "approval",
        message = "Proceed?"
    }
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "approve" in result.registry.hitl_points


def test_specification_structured_form_registers():
    source = """
    Specification("Demo", {
        { name = "happy", given = { ok = true } }
    })
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.specifications
