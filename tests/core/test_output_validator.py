"""Tests for output validator."""

import pytest

from tactus.core.output_validator import OutputValidator, OutputValidationError
from tactus.core.dsl_stubs import FieldDefinition


def test_validate_without_schema_returns_output():
    validator = OutputValidator()
    assert validator.validate({"a": 1}) == {"a": 1}


def test_validate_without_schema_converts_lua_table():
    class LuaTable:
        def items(self):
            return [("a", 1)]

    validator = OutputValidator()
    assert validator.validate(LuaTable()) == {"a": 1}


def test_init_with_non_sized_schema_logs_field_count_zero():
    validator = OutputValidator(object())
    assert validator.schema is not None


def test_validate_scalar_schema_enum():
    schema = {"type": "string", "required": True, "enum": ["a", "b"]}
    validator = OutputValidator(schema)

    assert validator.validate("a") == "a"
    with pytest.raises(OutputValidationError):
        validator.validate("c")


def test_validate_scalar_schema_optional_allows_none():
    validator = OutputValidator({"type": "string", "required": False})
    assert validator.validate(None) is None


def test_validate_scalar_schema_lua_table_type_mismatch():
    class LuaTable:
        def items(self):
            return [("a", 1)]

    validator = OutputValidator({"type": "string", "required": True})
    with pytest.raises(OutputValidationError, match="Output should be string"):
        validator.validate(LuaTable())


def test_validate_scalar_schema_wrapped_result_preserves_wrapper():
    from tactus.protocols.result import TactusResult

    validator = OutputValidator({"type": "string", "required": True})
    wrapped = TactusResult(output="ok")

    validated = validator.validate(wrapped)
    assert isinstance(validated, TactusResult)
    assert validated.output == "ok"


def test_validate_object_schema_required_and_type():
    schema = {
        "name": {"type": "string", "required": True},
        "count": {"type": "number", "required": False},
    }
    validator = OutputValidator(schema)

    assert validator.validate({"name": "ok", "count": 2}) == {"name": "ok", "count": 2}

    with pytest.raises(OutputValidationError):
        validator.validate({"count": 2})


def test_validate_object_schema_type_mismatch():
    schema = {"count": {"type": "number", "required": True}}
    validator = OutputValidator(schema)

    with pytest.raises(OutputValidationError, match="should be number"):
        validator.validate({"count": "nope"})


def test_validate_object_schema_filters_extra_fields():
    schema = {"name": {"type": "string", "required": True}}
    validator = OutputValidator(schema)

    result = validator.validate({"name": "ok", "extra": 1})

    assert result == {"name": "ok"}


def test_validate_object_schema_enum_invalid():
    schema = {"status": {"type": "string", "required": True, "enum": ["ok"]}}
    validator = OutputValidator(schema)

    with pytest.raises(OutputValidationError, match="invalid value"):
        validator.validate({"status": "bad"})


def test_validate_object_schema_enum_valid():
    schema = {"status": {"type": "string", "required": True, "enum": ["ok"]}}
    validator = OutputValidator(schema)

    assert validator.validate({"status": "ok"}) == {"status": "ok"}


def test_validate_object_schema_allows_none_type():
    schema = {"name": {"type": None, "required": True}}
    validator = OutputValidator(schema)

    assert validator.validate({"name": "ok"}) == {"name": "ok"}


def test_validate_object_schema_old_syntax_errors():
    validator = OutputValidator({"name": {}})

    with pytest.raises(OutputValidationError, match="old type syntax"):
        validator.validate({"name": "ok"})


def test_check_type_unknown_type_returns_true():
    validator = OutputValidator({"type": "unknown"})
    assert validator._check_type("value", "unknown") is True


def test_check_type_none_is_allowed():
    validator = OutputValidator({"type": "string"})
    assert validator._check_type(None, "string") is True


def test_check_type_allows_lua_tables_for_object():
    class LuaTable:
        def items(self):
            return [("a", 1)]

    validator = OutputValidator({"type": "object"})
    assert validator._check_type(LuaTable(), "object") is True


def test_check_type_object_without_iterable_falls_back_to_isinstance():
    validator = OutputValidator({"type": "object"})
    assert validator._check_type(1, "object") is False


def test_validate_object_schema_converts_lua_tables():
    class LuaTable:
        def items(self):
            return [("name", "ok")]

    validator = OutputValidator({"name": {"type": "string", "required": True}})
    assert validator.validate(LuaTable()) == {"name": "ok"}


def test_validate_object_schema_rejects_non_mapping_output():
    validator = OutputValidator({"name": {"type": "string", "required": True}})
    with pytest.raises(OutputValidationError, match="Output must be an object/table"):
        validator.validate(["nope"])


def test_convert_lua_tables_recursive():
    validator = OutputValidator({"name": {"type": "object"}})
    data = {"a": [1, {"b": 2}]}
    assert validator._convert_lua_tables(data) == {"a": [1, {"b": 2}]}


def test_convert_lua_tables_converts_items_object():
    class LuaTable:
        def items(self):
            return [("a", 1)]

    validator = OutputValidator({"name": {"type": "object"}})
    assert validator._convert_lua_tables(LuaTable()) == {"a": 1}


def test_get_field_description_and_required_optional_fields():
    schema = {
        "required": FieldDefinition({"required": True, "description": "req"}),
        "optional": FieldDefinition({"required": False, "description": "opt"}),
    }
    validator = OutputValidator(schema)

    assert validator.get_field_description("required") == "req"
    assert "required" in validator.get_required_fields()
    assert "optional" in validator.get_optional_fields()


def test_get_field_description_missing_field_returns_none():
    validator = OutputValidator({"name": {"description": "ok"}})
    assert validator.get_field_description("missing") is None


def test_get_field_description_returns_value_for_dict_schema():
    validator = OutputValidator({"name": {"description": "ok"}})
    assert validator.get_field_description("name") == "ok"


def test_get_field_description_returns_none_for_dict_without_description():
    validator = OutputValidator({"name": {}})
    assert validator.get_field_description("name") is None


def test_get_field_description_returns_none_for_non_dict_schema():
    validator = OutputValidator({"name": "desc"})
    assert validator.get_field_description("name") is None


def test_validate_wrapped_result_preserves_wrapper():
    from tactus.protocols.result import TactusResult

    validator = OutputValidator({"name": {"type": "string", "required": True}})
    result = TactusResult(output={"name": "ok"})

    validated = validator.validate(result)
    assert isinstance(validated, TactusResult)
    assert validated.output == {"name": "ok"}
