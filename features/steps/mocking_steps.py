"""
Gherkin steps for mock verification in BDD tests.

Provides steps to verify mock tool calls and their parameters.
"""

from behave import then
import json


@then('the mock "{tool_name}" should have been called {count:d} times')
def step_mock_called_n_times(context, tool_name, count):
    """Verify a mock was called a specific number of times."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    call_history = context.mock_manager.call_history.get(tool_name, [])
    actual_count = len(call_history)

    assert (
        actual_count == count
    ), f"Mock '{tool_name}' was called {actual_count} times, expected {count}"


@then('the mock "{tool_name}" should have been called')
def step_mock_called(context, tool_name):
    """Verify a mock was called at least once."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    call_history = context.mock_manager.call_history.get(tool_name, [])
    actual_count = len(call_history)

    assert actual_count > 0, f"Mock '{tool_name}' was never called"


@then('the mock "{tool_name}" should not have been called')
def step_mock_not_called(context, tool_name):
    """Verify a mock was never called."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        # If no mock manager, tool wasn't mocked so wasn't called
        return

    call_history = context.mock_manager.call_history.get(tool_name, [])
    actual_count = len(call_history)

    assert actual_count == 0, f"Mock '{tool_name}' was called {actual_count} times, expected 0"


@then('the mock "{tool_name}" should have received {param_name} "{param_value}"')
def step_mock_received_param(context, tool_name, param_name, param_value):
    """Verify a mock received a specific parameter value."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    call_history = context.mock_manager.call_history.get(tool_name, [])

    if not call_history:
        assert False, f"Mock '{tool_name}' was never called"

    # Check the last call
    last_call = call_history[-1]
    if param_name not in last_call.args:
        assert False, f"Mock '{tool_name}' did not receive parameter '{param_name}'"

    actual_value = last_call.args[param_name]

    # Try to parse JSON values
    try:
        expected = json.loads(param_value)
    except (json.JSONDecodeError, ValueError):
        expected = param_value

    assert (
        actual_value == expected
    ), f"Mock '{tool_name}' received {param_name}={actual_value}, expected {expected}"


@then('the mock "{tool_name}" should have received')
def step_mock_received_table(context, tool_name):
    """Verify a mock received specific parameters (from table)."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    call_history = context.mock_manager.call_history.get(tool_name, [])

    if not call_history:
        assert False, f"Mock '{tool_name}' was never called"

    # Check the last call
    last_call = call_history[-1]

    # Verify each row in the table
    for row in context.table:
        param_name = row["parameter"]
        expected_value = row["value"]

        if param_name not in last_call.args:
            assert False, f"Mock '{tool_name}' did not receive parameter '{param_name}'"

        actual_value = last_call.args[param_name]

        # Try to parse JSON values
        try:
            expected = json.loads(expected_value)
        except (json.JSONDecodeError, ValueError):
            expected = expected_value

        assert (
            actual_value == expected
        ), f"Mock '{tool_name}' received {param_name}={actual_value}, expected {expected}"


@then('the last mock call to "{tool_name}" should have returned')
def step_mock_returned(context, tool_name):
    """Verify what a mock returned (from text block)."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    call_history = context.mock_manager.call_history.get(tool_name, [])

    if not call_history:
        assert False, f"Mock '{tool_name}' was never called"

    # Check the last call's result
    last_call = call_history[-1]
    actual_result = last_call.result

    # Parse expected result from text
    expected_json = context.text.strip()
    try:
        expected = json.loads(expected_json)
    except json.JSONDecodeError as e:
        assert False, f"Invalid JSON in expected result: {e}"

    assert (
        actual_result == expected
    ), f"Mock '{tool_name}' returned {actual_result}, expected {expected}"


@then("all mocks should have been called")
def step_all_mocks_called(context):
    """Verify all registered mocks were called at least once."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        assert False, "No mock manager available in context"

    for tool_name, mock_config in context.mock_manager.mocks.items():
        if mock_config.enabled:
            call_history = context.mock_manager.call_history.get(tool_name, [])
            assert len(call_history) > 0, f"Mock '{tool_name}' was never called"


@then("no mocks should have been called")
def step_no_mocks_called(context):
    """Verify no mocks were called."""
    if not hasattr(context, "mock_manager") or context.mock_manager is None:
        # No mock manager means no mocks could have been called
        return

    total_calls = sum(len(calls) for calls in context.mock_manager.call_history.values())
    assert total_calls == 0, f"Expected no mock calls, but {total_calls} calls were made"
