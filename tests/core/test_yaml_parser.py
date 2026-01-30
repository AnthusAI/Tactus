"""Tests for YAML parser validation."""

import yaml
import pytest

from tactus.core.yaml_parser import ProcedureYAMLParser, ProcedureConfigError


def _base_config():
    return {
        "name": "test",
        "version": "1.0.0",
        "procedure": "main",
        "default_provider": "openai",
        "agents": {"agent": {"system_prompt": "hi", "initial_message": "start"}},
    }


def test_parse_valid_config():
    config = _base_config()
    yaml_content = yaml.safe_dump(config)

    parsed = ProcedureYAMLParser.parse(yaml_content)

    assert parsed["name"] == "test"


def test_parse_valid_config_with_params_outputs_and_model_settings():
    config = _base_config()
    config["class"] = "LuaDSL"
    config["default_model"] = "gpt-4o"
    config["params"] = {"limit": {"type": "string"}}
    config["output"] = {"result": {"type": "number"}}
    config["agents"]["agent"]["provider"] = "openai"
    config["agents"]["agent"]["tools"] = ["done"]
    config["agents"]["agent"]["model"] = {
        "name": "gpt-4o",
        "temperature": 0.7,
        "top_p": 0.5,
        "max_tokens": 10,
        "openai_reasoning_effort": "low",
    }
    yaml_content = yaml.safe_dump(config)

    parsed = ProcedureYAMLParser.parse(yaml_content)

    assert parsed["params"]["limit"]["type"] == "string"
    assert parsed["output"]["result"]["type"] == "number"


def test_params_and_outputs_allow_missing_type():
    config = _base_config()
    config["params"] = {"limit": {"description": "ok"}}
    config["output"] = {"result": {"description": "ok"}}
    yaml_content = yaml.safe_dump(config)

    parsed = ProcedureYAMLParser.parse(yaml_content)

    assert parsed["params"]["limit"]["description"] == "ok"
    assert parsed["output"]["result"]["description"] == "ok"


def test_parse_invalid_yaml():
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(":")


def test_missing_required_fields():
    config = {"name": "test"}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_invalid_default_provider():
    config = _base_config()
    config["default_provider"] = "unknown"
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_dict_missing_name():
    config = _base_config()
    config["agents"]["agent"]["model"] = {"temperature": 0.7}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_unknown_setting():
    config = _base_config()
    config["agents"]["agent"]["model"] = {"name": "gpt-4o", "bad": 1}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_params_not_dict():
    config = _base_config()
    config["params"] = []
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_yaml_root_must_be_dict():
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse("- item")


def test_class_warning_for_non_lua_dsl(caplog):
    config = _base_config()
    config["class"] = "Other"
    yaml_content = yaml.safe_dump(config)

    with caplog.at_level("WARNING"):
        ProcedureYAMLParser.parse(yaml_content)

    assert "may not be compatible" in caplog.text


def test_param_definition_must_be_dict():
    config = _base_config()
    config["params"] = {"limit": "bad"}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_param_invalid_type():
    config = _base_config()
    config["params"] = {"limit": {"type": "bad"}}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_output_definition_must_be_dict():
    config = _base_config()
    config["output"] = {"result": "bad"}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["output"] = []
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_output_invalid_type():
    config = _base_config()
    config["output"] = {"result": {"type": "bad"}}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_default_model_validation():
    config = _base_config()
    config["default_model"] = 123
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["default_model"] = "   "
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_default_provider_validation():
    config = _base_config()
    config["default_provider"] = 123
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["default_provider"] = "   "
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agents_must_be_dict_and_not_empty():
    config = _base_config()
    config["agents"] = []
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["agents"] = {}
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_definition_must_be_dict():
    config = _base_config()
    config["agents"]["agent"] = "bad"
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_required_fields_missing():
    config = _base_config()
    config["agents"]["agent"] = {"system_prompt": "hi"}
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_string_empty():
    config = _base_config()
    config["agents"]["agent"]["model"] = "   "
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_name_type_and_empty():
    config = _base_config()
    config["agents"]["agent"]["model"] = {"name": 123}
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["agents"]["agent"]["model"] = {"name": "   "}
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


@pytest.mark.parametrize(
    "model_value",
    [
        {"name": "gpt-4o", "temperature": -0.1},
        {"name": "gpt-4o", "temperature": 3},
        {"name": "gpt-4o", "top_p": -0.1},
        {"name": "gpt-4o", "top_p": 2},
        {"name": "gpt-4o", "max_tokens": 0},
        {"name": "gpt-4o", "max_tokens": "bad"},
        {"name": "gpt-4o", "openai_reasoning_effort": "invalid"},
    ],
)
def test_agent_model_invalid_settings(model_value):
    config = _base_config()
    config["agents"]["agent"]["model"] = model_value
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_invalid_type():
    config = _base_config()
    config["agents"]["agent"]["model"] = ["gpt-4o"]
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_model_valid_without_reasoning_effort():
    config = _base_config()
    config["agents"]["agent"]["model"] = {"name": "gpt-4o", "temperature": 0.2}
    yaml_content = yaml.safe_dump(config)

    parsed = ProcedureYAMLParser.parse(yaml_content)

    assert parsed["agents"]["agent"]["model"]["temperature"] == 0.2


def test_agent_requires_provider_without_default():
    config = _base_config()
    del config["default_provider"]
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_provider_validation():
    config = _base_config()
    config["agents"]["agent"]["provider"] = 123
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["agents"]["agent"]["provider"] = "   "
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["agents"]["agent"]["provider"] = "other"
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_agent_tools_must_be_list():
    config = _base_config()
    config["agents"]["agent"]["tools"] = "bad"
    yaml_content = yaml.safe_dump(config)

    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_procedure_validation_errors():
    config = _base_config()
    config["procedure"] = None
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["procedure"] = 123
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)

    config["procedure"] = "   "
    yaml_content = yaml.safe_dump(config)
    with pytest.raises(ProcedureConfigError):
        ProcedureYAMLParser.parse(yaml_content)


def test_procedure_parentheses_warning(caplog):
    config = _base_config()
    config["procedure"] = "function(x"
    yaml_content = yaml.safe_dump(config)

    with caplog.at_level("WARNING"):
        ProcedureYAMLParser.parse(yaml_content)

    assert "unmatched parentheses" in caplog.text


def test_extract_agent_names_and_config():
    config = _base_config()
    names = ProcedureYAMLParser.extract_agent_names(config)
    assert names == ["agent"]
    assert ProcedureYAMLParser.get_agent_config(config, "agent") == config["agents"]["agent"]
    assert ProcedureYAMLParser.get_agent_config(config, "missing") is None
