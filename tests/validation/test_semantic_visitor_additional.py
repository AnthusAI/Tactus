from tactus.validation.validator import TactusValidator, ValidationMode


def test_agent_lookup_syntax_is_deprecated():
    source = 'Agent("helper")'
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("lookup syntax is deprecated" in err.message for err in result.errors)


def test_agent_turn_method_is_deprecated():
    source = """
    greeter = Agent { system_prompt = "hi" }
    greeter.turn()
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("turn() method is deprecated" in err.message for err in result.errors)


def test_agent_run_method_is_deprecated():
    source = """
    agent = Agent { system_prompt = "hi" }
    agent.run()
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("run() method on agents is deprecated" in err.message for err in result.errors)


def test_name_and_version_calls_report_processing_error():
    source = """
    name "Demo"
    version "1.0.0"
    """
    result = TactusValidator().validate(source, mode=ValidationMode.FULL)

    assert result.valid is False
    assert any("Error processing name" in err.message for err in result.errors)
    assert any("Error processing version" in err.message for err in result.errors)
