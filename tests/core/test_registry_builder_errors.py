"""Tests for registry builder error paths."""

from tactus.core.registry import RegistryBuilder


class _DuplicateKeysDict(dict):
    def keys(self):
        return ["main", "main"]


def test_register_hitl_invalid_adds_error():
    builder = RegistryBuilder()
    builder.register_hitl("approval", {"type": "approval"})
    assert any("Invalid HITL point" in msg.message for msg in builder.validation_messages)


def test_register_dependency_invalid_adds_error():
    builder = RegistryBuilder()
    builder.register_dependency("db", {"config": {"dsn": "postgres://"}})
    assert any("Invalid dependency" in msg.message for msg in builder.validation_messages)


def test_register_agent_mock_invalid_adds_error():
    builder = RegistryBuilder()
    builder.register_agent_mock("agent", {"tool_calls": "bad"})
    assert any("Invalid agent mock config" in msg.message for msg in builder.validation_messages)


def test_register_specification_invalid_adds_error():
    builder = RegistryBuilder()
    builder.register_specification("spec", [{"when": "procedure_completes"}])
    assert any("Invalid specification" in msg.message for msg in builder.validation_messages)


def test_set_message_history_config_and_warning_path():
    builder = RegistryBuilder()
    builder.set_message_history_config({"source": "shared"})
    builder._add_warning("heads up")
    assert builder.registry.message_history_config == {"source": "shared"}
    assert any(msg.level == "warning" for msg in builder.validation_messages)


def test_validate_flags_multiple_main_procedures():
    builder = RegistryBuilder()
    builder.registry.named_procedures = _DuplicateKeysDict(
        {"main": {"input_schema": {}, "output_schema": {}}}
    )
    builder.registry.script_mode = True
    result = builder.validate()
    assert result.valid is False
    assert any("Multiple unnamed Procedures" in msg.message for msg in result.errors)
