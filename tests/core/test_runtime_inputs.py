"""
Tests for TactusRuntime input parameter handling.

Tests programmatic input passing via the context parameter to runtime.execute().
"""

import pytest
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


@pytest.fixture
def runtime():
    """Create a TactusRuntime instance for testing."""
    return TactusRuntime(
        procedure_id="test-inputs",
        storage_backend=MemoryStorage(),
    )


class TestStringInputs:
    """Tests for string input parameters."""

    @pytest.mark.asyncio
    async def test_string_input_required(self, runtime):
        """Test required string input is passed correctly."""
        source = """Procedure {
            input = {
                name = field.string{required = true}
            },
            output = {
                greeting = field.string{required = true}
            },
            function(input)
                return {greeting = "Hello, " .. input.name .. "!"}
            end
        }"""

        result = await runtime.execute(source, context={"name": "World"}, format="lua")

        assert result["success"]
        assert result["result"]["greeting"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_string_input_with_default(self, runtime):
        """Test string input with default value when not provided."""
        source = """Procedure {
            input = {
                name = field.string{default = "Default"}
            },
            output = {
                greeting = field.string{required = true}
            },
            function(input)
                return {greeting = "Hello, " .. input.name}
            end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["greeting"] == "Hello, Default"

    @pytest.mark.asyncio
    async def test_string_input_override_default(self, runtime):
        """Test context value overrides default."""
        source = """Procedure {
            input = {
                name = field.string{default = "Default"}
            },
            output = {
                greeting = field.string{required = true}
            },
            function(input)
                return {greeting = "Hello, " .. input.name}
            end
        }"""

        result = await runtime.execute(source, context={"name": "Custom"}, format="lua")

        assert result["success"]
        assert result["result"]["greeting"] == "Hello, Custom"


class TestNumberInputs:
    """Tests for number input parameters."""

    @pytest.mark.asyncio
    async def test_integer_input(self, runtime):
        """Test integer input parameter."""
        source = """Procedure {
            input = {
                count = field.number{required = true}
            },
            output = {
                doubled = field.number{required = true}
            },
            function(input)
            return {doubled = input.count * 2}
        end
        }"""

        result = await runtime.execute(source, context={"count": 21}, format="lua")

        assert result["success"]
        assert result["result"]["doubled"] == 42

    @pytest.mark.asyncio
    async def test_float_input(self, runtime):
        """Test float input parameter."""
        source = """Procedure {
            input = {
                value = field.number{required = true}
            },
            output = {
                result = field.number{required = true}
            },
            function(input)
            return {result = input.value * 2}
        end
        }"""

        result = await runtime.execute(source, context={"value": 3.14}, format="lua")

        assert result["success"]
        assert abs(result["result"]["result"] - 6.28) < 0.01

    @pytest.mark.asyncio
    async def test_number_default(self, runtime):
        """Test number input with default value."""
        source = """Procedure {
            input = {
                count = field.number{default = 10}
            },
            output = {
                value = field.number{required = true}
            },
            function(input)
            return {value = input.count}
        end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["value"] == 10


class TestBooleanInputs:
    """Tests for boolean input parameters."""

    @pytest.mark.asyncio
    async def test_boolean_true(self, runtime):
        """Test boolean true input."""
        source = """Procedure {
            input = {
                enabled = field.boolean{required = true}
            },
            output = {
                result = field.boolean{required = true}
            },
            function(input)
            return {result = input.enabled}
        end
        }"""

        result = await runtime.execute(source, context={"enabled": True}, format="lua")

        assert result["success"]
        assert result["result"]["result"] is True

    @pytest.mark.asyncio
    async def test_boolean_false(self, runtime):
        """Test boolean false input."""
        source = """Procedure {
            input = {
                enabled = field.boolean{required = true}
            },
            output = {
                result = field.boolean{required = true}
            },
            function(input)
            return {result = input.enabled}
        end
        }"""

        result = await runtime.execute(source, context={"enabled": False}, format="lua")

        assert result["success"]
        assert result["result"]["result"] is False

    @pytest.mark.asyncio
    async def test_boolean_default(self, runtime):
        """Test boolean input with default value."""
        source = """Procedure {
            input = {
                enabled = field.boolean{default = true}
            },
            output = {
                result = field.boolean{required = true}
            },
            function(input)
            return {result = input.enabled}
        end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["result"] is True


class TestArrayInputs:
    """Tests for array input parameters.

    Note: Lua/Python bridge (lupa) passes Python lists as POBJECT values.
    The # operator doesn't work directly on these - use iteration patterns instead.
    """

    @pytest.mark.asyncio
    async def test_array_input_index_access(self, runtime):
        """Test array input with direct index access.

        Arrays are now converted to Lua tables with 1-based indexing.
        """
        source = """Procedure {
            input = {
                items = field.array{required = true}
            },
            output = {
                first = field.number{required = true},
                second = field.number{required = true}
            },
            function(input)
            return {first = input.items[1], second = input.items[2]}
        end
        }"""

        result = await runtime.execute(source, context={"items": [10, 20, 30]}, format="lua")

        assert result["success"]
        assert result["result"]["first"] == 10
        assert result["result"]["second"] == 20

    @pytest.mark.asyncio
    async def test_array_default_empty_returns_ok(self, runtime):
        """Test array input with empty default - procedure completes."""
        source = """Procedure {
            input = {
                items = field.array{default = {}}
            },
            output = {
                ok = field.boolean{required = true}
            },
            function(input)
            return {ok = true}
        end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["ok"] is True

    @pytest.mark.asyncio
    async def test_string_array_access(self, runtime):
        """Test array of strings input with index access.

        Arrays are now converted to Lua tables with 1-based indexing.
        """
        source = """Procedure {
            input = {
                names = field.array{required = true}
            },
            output = {
                first = field.string{required = true}
            },
            function(input)
            return {first = input.names[1]}
        end
        }"""

        result = await runtime.execute(
            source, context={"names": ["Alice", "Bob", "Carol"]}, format="lua"
        )

        assert result["success"]
        assert result["result"]["first"] == "Alice"


class TestObjectInputs:
    """Tests for object/dict input parameters."""

    @pytest.mark.asyncio
    async def test_object_input(self, runtime):
        """Test object input parameter."""
        source = """Procedure {
            input = {
                config = field.object{required = true}
            },
            output = {
                value = field.string{required = true}
            },
            function(input)
            return {value = input.config.key}
        end
        }"""

        result = await runtime.execute(
            source, context={"config": {"key": "test_value"}}, format="lua"
        )

        assert result["success"]
        assert result["result"]["value"] == "test_value"

    @pytest.mark.asyncio
    async def test_object_default_empty(self, runtime):
        """Test object input with empty default."""
        source = """Procedure {
            input = {
                config = field.object{default = {}}
            },
            output = {
                ok = field.boolean{required = true}
            },
            function(input)
            return {ok = true}
        end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["ok"] is True

    @pytest.mark.asyncio
    async def test_nested_object(self, runtime):
        """Test nested object input."""
        source = """Procedure {
            input = {
                data = field.object{required = true}
            },
            output = {
                value = field.string{required = true}
            },
            function(input)
            return {value = input.data.nested.key}
        end
        }"""

        result = await runtime.execute(
            source, context={"data": {"nested": {"key": "deep_value"}}}, format="lua"
        )

        assert result["success"]
        assert result["result"]["value"] == "deep_value"


class TestMultipleInputs:
    """Tests for procedures with multiple inputs."""

    @pytest.mark.asyncio
    async def test_multiple_inputs_all_types(self, runtime):
        """Test procedure with multiple inputs of different types."""
        source = """Procedure {
            input = {
                name = field.string{required = true},
                count = field.number{default = 1},
                enabled = field.boolean{default = false}
            },
            output = {
                message = field.string{required = true}
            },
            function(input)
            local msg = "Name: " .. input.name .. ", Count: " .. tostring(input.count)
            if input.enabled then
                msg = msg .. ", Enabled"
            end
            return {message = msg}
        end
        }"""

        result = await runtime.execute(
            source, context={"name": "Test", "count": 5, "enabled": True}, format="lua"
        )

        assert result["success"]
        assert "Name: Test" in result["result"]["message"]
        assert "Count: 5" in result["result"]["message"]
        assert "Enabled" in result["result"]["message"]

    @pytest.mark.asyncio
    async def test_mixed_provided_and_defaults(self, runtime):
        """Test some inputs provided, others using defaults."""
        source = """Procedure {
            input = {
                required_val = field.string{required = true},
                optional_val = field.string{default = "default_option"},
                number_val = field.number{default = 100}
            },
            output = {
                result = field.string{required = true}
            },
            function(input)
            return {result = input.required_val .. "-" .. input.optional_val .. "-" .. tostring(input.number_val)}
        end
        }"""

        result = await runtime.execute(source, context={"required_val": "provided"}, format="lua")

        assert result["success"]
        assert result["result"]["result"] == "provided-default_option-100"


class TestInputValidation:
    """Tests for input validation behavior."""

    @pytest.mark.asyncio
    async def test_empty_context_with_defaults(self, runtime):
        """Test procedure runs with empty context when all inputs have defaults."""
        source = """Procedure {
            input = {
                value = field.string{default = "fallback"}
            },
            output = {
                result = field.string{required = true}
            },
            function(input)
            return {result = input.value}
        end
        }"""

        result = await runtime.execute(source, context={}, format="lua")

        assert result["success"]
        assert result["result"]["result"] == "fallback"

    @pytest.mark.asyncio
    async def test_no_input_schema(self, runtime):
        """Test procedure with no input schema works fine."""
        source = """Procedure {
            output = {
                result = field.string{required = true}
            },
            function(input)
            return {result = "no inputs needed"}
        end
        }"""

        result = await runtime.execute(source, format="lua")

        assert result["success"]
        assert result["result"]["result"] == "no inputs needed"

    @pytest.mark.asyncio
    async def test_extra_context_ignored(self, runtime):
        """Test extra context values not in schema are ignored."""
        source = """Procedure {
            input = {
                name = field.string{required = true}
            },
            output = {
                result = field.string{required = true}
            },
            function(input)
            return {result = input.name}
        end
        }"""

        result = await runtime.execute(
            source, context={"name": "test", "extra_field": "ignored", "another": 123}, format="lua"
        )

        assert result["success"]
        assert result["result"]["result"] == "test"
