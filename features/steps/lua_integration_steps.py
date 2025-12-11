"""
Step definitions for Lua Integration feature.
"""

from behave import given, when, then
from tactus.core.lua_sandbox import LuaSandbox
from tactus.primitives.state import StatePrimitive
from tactus.core.execution_context import InMemoryExecutionContext


@given("a Tactus workflow environment")
def step_impl(context):
    """Initialize workflow environment."""
    context.procedure_id = "test_lua_procedure"
    context.execution_context = InMemoryExecutionContext(procedure_id=context.procedure_id)


@given("a Lua sandbox is initialized")
def step_impl(context):
    """Initialize Lua sandbox."""
    context.lua = LuaSandbox()


@when("I execute Lua code:")
def step_impl(context):
    """Execute Lua code from docstring."""
    lua_code = context.text

    # Ensure state primitive is always available
    if not hasattr(context, "state") or context.state is None:
        context.state = StatePrimitive()
    context.lua.inject_primitive("state", context.state)

    if "agent:" in lua_code and not context.lua.get_global("agent"):
        # Create mock agent for testing
        class MockAgent:
            def call(self, prompt):
                return f"Mock response to: {prompt}"

        context.lua.inject_primitive("agent", MockAgent())

    try:
        result = context.lua.execute(lua_code)
        # Recursively convert Lua tables to Python dicts/lists
        context.result = _convert_lua_value(result)
        context.error = None
    except Exception as e:
        context.error = e
        context.result = None


def _convert_lua_value(value):
    """Recursively convert Lua values to Python types."""
    if hasattr(value, "__class__") and "LuaTable" in value.__class__.__name__:
        # Check if it's an array (sequential integer keys starting from 1)
        try:
            # Try to iterate as a list
            result_list = []
            for i in range(1, 1000):  # Arbitrary upper limit
                try:
                    item = value[i]
                    if item is None:
                        break
                    result_list.append(_convert_lua_value(item))
                except (KeyError, IndexError):
                    break

            if result_list:
                return result_list

            # Otherwise, treat as dict
            result_dict = {}
            for key in value:
                result_dict[key] = _convert_lua_value(value[key])
            return result_dict
        except Exception:  # noqa: E722
            # Fallback: return as is
            return value
    else:
        return value


@then("the result should be {expected:d}")
def step_impl(context, expected):
    """Verify result equals expected integer."""
    assert context.result == expected, f"Expected {expected}, got {context.result}"


@given("primitives are available in Lua environment")
def step_impl(context):
    """Inject primitives into Lua environment."""
    # Create state primitive
    context.state = StatePrimitive()

    # Inject into Lua
    context.lua.inject_primitive("state", context.state)


@then("the result should be a Python dict")
def step_impl(context):
    """Verify result is a Python dictionary."""
    assert isinstance(context.result, dict), f"Expected dict, got {type(context.result)}"


@then('it should have field "{field}" with value "{value}"')
def step_impl(context, field, value):
    """Verify dict has field with expected value."""
    assert field in context.result, f"Field '{field}' not found in result"
    actual = context.result[field]
    assert actual == value, f"Expected {field}={value}, got {actual}"


@then('field "{field}" should be a list with {count:d} elements')
def step_impl(context, field, count):
    """Verify field is a list with expected number of elements."""
    assert field in context.result, f"Field '{field}' not found"
    value = context.result[field]
    assert isinstance(value, (list, tuple)), f"Expected list, got {type(value)}"
    assert len(value) == count, f"Expected {count} elements, got {len(value)}"


@when('I execute Lua code that tries to access "{module}"')
def step_impl(context, module):
    """Execute Lua code that tries to access a blocked module."""
    lua_code = f"return {module}"
    try:
        context.result = context.lua.execute(lua_code)
        context.error = None
    except Exception as e:
        context.error = e
        context.result = None


@then("the code should be blocked")
def step_impl(context):
    """Verify code was blocked."""
    # Either error was raised or result is nil/None
    assert context.error is not None or context.result is None, "Expected code to be blocked"


@then("an error should be raised about restricted access")
def step_impl(context):
    """Verify error message mentions restricted access."""
    if context.error:
        error_msg = str(context.error).lower()
        # Check for various error indicators
        assert any(
            keyword in error_msg
            for keyword in ["nil", "attempt to call", "restricted", "not allowed", "error"]
        ), f"Error message doesn't indicate restricted access: {error_msg}"


@given('a Python function "{func_name}" is exported to Lua')
def step_impl(context, func_name):
    """Export a Python function to Lua."""

    def multiply(a, b):
        return a * b

    context.lua.inject_primitive(func_name, multiply)


@then("the result should be false")
def step_impl(context):
    """Verify result is false."""
    assert context.result is False, f"Expected False, got {context.result}"


@then("no Python exception should be raised")
def step_impl(context):
    """Verify no Python exception was raised."""
    assert context.error is None, f"Unexpected exception: {context.error}"


@then('the result should be "{expected}"')
def step_impl(context, expected):
    """Verify result equals expected string."""
    assert context.result == expected, f"Expected '{expected}', got '{context.result}'"


@then('state "{key}" should contain agent output')
def step_impl(context, key):
    """Verify state contains agent output."""
    value = context.state.get(key)
    assert value is not None, f"State '{key}' should not be None"
    # Agent output should be a non-empty string
    assert isinstance(value, str), f"Expected string, got {type(value)}"
    assert len(value) > 0, "Agent output should not be empty"
