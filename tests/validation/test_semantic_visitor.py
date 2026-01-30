from tactus.validation.validator import TactusValidator, ValidationMode


def test_default_provider_model_applied_to_agent():
    source = """
    default_provider = "openai"
    default_model = "gpt-4o"

    greeter = Agent {
        system_prompt = "Hello"
    }
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    agent = result.registry.agents["greeter"]
    assert agent.provider == "openai"
    assert agent.model == "gpt-4o"


def test_tool_name_mismatch_reports_error():
    source = """
    my_tool = Tool {
        name = "other",
        description = "Mismatch"
    }
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Tool name mismatch" in err.message for err in result.errors)


def test_assignment_procedure_registered():
    source = """
    main = Procedure {
        function(input)
            return { ok = true }
        end
    }
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "main" in result.registry.named_procedures


def test_specification_from_reference_registered():
    source = 'Specification { from = "specs.tac" }'

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.specs_from_references == ["specs.tac"]


def test_evaluations_registers_pydantic_config():
    source = """
    Evaluations {
        dataset = {
            { name = "case", inputs = { query = "x" } }
        },
        evaluators = {
            { type = "contains", value = "x" }
        }
    }
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "dataset" in result.registry.pydantic_evaluations


def test_curried_agent_syntax_reports_error():
    source = 'Agent "helper" { system_prompt = "hi" }'

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Curried syntax Agent" in err.message for err in result.errors)


def test_specifications_and_step_registration():
    source = """
    Specifications [[
        Feature: Demo
          Scenario: A
            Given something
    ]]
    Step("a custom step", function(ctx) return true end)
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert "Feature: Demo" in (result.registry.gherkin_specifications or "")
    assert "a custom step" in result.registry.custom_steps


def test_top_level_input_output_script_mode():
    source = """
    input { name = "Ada" }
    output { greeting = "Hello" }
    """

    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is True
    assert result.registry is not None
    assert result.registry.script_mode is True
    assert result.registry.top_level_input_schema.get("name") == "Ada"
    assert result.registry.top_level_output_schema.get("greeting") == "Hello"
