"""
Tests for Model primitive schema validation.
"""

import pytest
from pydantic import BaseModel, ValidationError

from tactus.models.schema import resolve_schema, schema_dict_to_pydantic


class TestSchemaDictToPydantic:
    """Test converting inline schema dicts to Pydantic models."""

    def test_simple_types(self):
        """Test schema with simple types."""
        schema = {"text": "string", "count": "int", "score": "float"}
        Model = schema_dict_to_pydantic(schema, "TestModel")

        # Valid data
        instance = Model(text="hello", count=42, score=0.95)
        assert instance.text == "hello"
        assert instance.count == 42
        assert instance.score == 0.95

        # Invalid data - wrong type
        with pytest.raises(ValidationError):
            Model(text=123, count=42, score=0.95)

    def test_boolean_type(self):
        """Test boolean schema field."""
        schema = {"enabled": "bool"}
        Model = schema_dict_to_pydantic(schema, "BoolModel")

        instance = Model(enabled=True)
        assert instance.enabled is True

    def test_list_and_dict_types(self):
        """Test list and dict schema fields."""
        schema = {"items": "list", "metadata": "dict"}
        Model = schema_dict_to_pydantic(schema, "CollectionModel")

        instance = Model(items=[1, 2, 3], metadata={"key": "value"})
        assert instance.items == [1, 2, 3]
        assert instance.metadata == {"key": "value"}

    def test_nested_schema(self):
        """Test nested object schemas."""
        schema = {
            "user": {
                "name": "string",
                "age": "int",
            },
            "score": "float",
        }
        Model = schema_dict_to_pydantic(schema, "NestedModel")

        instance = Model(user={"name": "Alice", "age": 30}, score=0.95)
        assert instance.user.name == "Alice"
        assert instance.user.age == 30
        assert instance.score == 0.95

    def test_empty_schema(self):
        """Test empty schema returns None (no validation)."""
        Model = schema_dict_to_pydantic({}, "EmptyModel")
        assert Model is None

    def test_type_aliases(self):
        """Test type name aliases (str/string, int/integer, etc)."""
        schema = {
            "a": "str",  # alias for string
            "b": "integer",  # alias for int
            "c": "number",  # alias for float
            "d": "boolean",  # alias for bool
            "e": "array",  # alias for list
            "f": "object",  # alias for dict
        }
        Model = schema_dict_to_pydantic(schema, "AliasModel")

        instance = Model(a="text", b=1, c=2.5, d=False, e=[], f={})
        assert instance.a == "text"
        assert instance.b == 1

    def test_unknown_field_type(self):
        """Test that unknown field types (non-string, non-dict) default to Any."""
        schema = {
            "text": "string",
            "unknown": 123,  # Neither string nor dict
        }
        Model = schema_dict_to_pydantic(schema, "UnknownTypeModel")

        # Should accept any value for 'unknown' field
        instance = Model(text="hello", unknown="anything")
        assert instance.text == "hello"
        assert instance.unknown == "anything"

        # Can also accept non-string values
        instance2 = Model(text="hello", unknown=999)
        assert instance2.unknown == 999


class TestResolveSchema:
    """Test resolving schema specifications to Pydantic models."""

    def test_inline_dict_schema(self):
        """Test resolving inline dict schemas."""
        schema = {"text": "string", "label": "string"}
        Model = resolve_schema(schema, "InlineSchema")

        instance = Model(text="hello", label="greeting")
        assert instance.text == "hello"
        assert instance.label == "greeting"

    def test_python_class_reference(self):
        """Test resolving Python class references."""

        # Create a test Pydantic model
        class TestInput(BaseModel):
            value: int

        # Should be able to resolve by full path
        # (In real usage: "myproject.schemas.TestInput")
        # For test, we'll use __main__ or the actual module path
        Model = resolve_schema("tests.models.test_schema.TestInput", "RefSchema")
        # Just verify it doesn't error and returns a class
        assert Model is not None

    def test_none_schema(self):
        """Test None schema returns None (no validation)."""
        assert resolve_schema(None) is None
        assert resolve_schema({}) is None

    def test_invalid_type(self):
        """Test invalid schema type raises TypeError."""
        with pytest.raises(TypeError, match="Schema must be dict or string"):
            resolve_schema(123)

    def test_nonexistent_module_reference(self):
        """Test nonexistent Python module raises ImportError."""
        with pytest.raises(ImportError):
            resolve_schema("nonexistent.module.ClassName")

    def test_non_basemodel_reference(self):
        """Test non-Pydantic class reference raises TypeError."""
        with pytest.raises(TypeError, match="must be a Pydantic BaseModel"):
            resolve_schema("tests.models.test_schema.TestSchemaDictToPydantic")


# Make TestInput available for the reference test
class TestInput(BaseModel):
    """Test Pydantic model for reference resolution."""

    value: int
