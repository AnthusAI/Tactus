"""
Step definitions for chat assistant feature.
"""

from behave import given, when, then
from features.steps.support.harnesses import ChatAssistantHarness
import ast


@given('a workspace at "{path}"')
def step_workspace_at(context, path):
    """Set up workspace for chat assistant."""
    context.workspace_root = path
    context.chat = ChatAssistantHarness(workspace_root=path)


@given("the chat assistant is configured with:")
def step_configure_assistant(context):
    """Configure assistant with parameters from table."""
    config = {row["parameter"]: row["value"] for row in context.table}
    context.chat.configure(config)


@when('I send the message "{message}"')
def step_send_message(context, message):
    """Send a message to the assistant."""
    context.chat.send_message(message)


@then("the assistant should respond")
def step_assistant_responds(context):
    """Verify assistant generated a response."""
    assert context.chat.has_response(), "No response from assistant"


@then("the response should contain text")
def step_response_contains_text(context):
    """Verify response has text content."""
    response = context.chat.get_response()
    assert response, "Response is empty"
    assert len(response.strip()) > 0, "Response contains no text"


@then("no tools should be called")
def step_no_tools_called(context):
    """Verify no tools were invoked."""
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) == 0, f"Expected no tool calls, but got: {tool_calls}"


@then('the assistant should call tool "{tool_name}"')
def step_tool_called(context, tool_name):
    """Verify a specific tool was called."""
    assert context.chat.tool_was_called(
        tool_name
    ), f"Tool '{tool_name}' was not called. Called: {context.chat.get_tool_calls()}"


@then("the tool should be called with:")
def step_tool_called_with(context):
    """Verify tool was called with specific parameters."""
    expected_params = {row["parameter"]: row["value"] for row in context.table}

    # Get the last tool call
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) > 0, "No tool calls found"

    last_call = tool_calls[-1]
    actual_params = last_call["params"]

    for param, expected_value in expected_params.items():
        assert (
            param in actual_params
        ), f"Parameter '{param}' not found in tool call. Available: {actual_params.keys()}"

        actual_value = actual_params[param]

        # Handle list parameters (like view_range)
        if expected_value.startswith("["):
            expected_value = ast.literal_eval(expected_value)

        assert (
            actual_value == expected_value
        ), f"Parameter '{param}': expected {expected_value}, got {actual_value}"


@then("the tool result should contain line numbers")
def step_tool_result_has_line_numbers(context):
    """Verify tool result includes line numbers."""
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) > 0, "No tool calls found"

    last_call = tool_calls[-1]
    result = last_call["result"]

    # Check for line number format: "1: content"
    lines = result.split("\n")
    has_line_numbers = any(
        line.strip() and line.split(":")[0].strip().isdigit() for line in lines if ":" in line
    )

    assert has_line_numbers, f"Tool result does not contain line numbers:\n{result}"


@then("the response should describe the file contents")
def step_response_describes_file(context):
    """Verify response mentions file contents."""
    response = context.chat.get_response()
    assert response, "No response from assistant"
    # Basic check - response should be non-empty
    assert len(response.strip()) > 0, "Response is empty"


@then("the tool result should show directories and files")
def step_tool_result_shows_dirs_and_files(context):
    """Verify tool result shows directory listing."""
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) > 0, "No tool calls found"

    last_call = tool_calls[-1]
    result = last_call["result"]

    # Check for [DIR] or [FILE] markers
    has_markers = "[DIR]" in result or "[FILE]" in result
    assert has_markers, f"Tool result does not show directory markers:\n{result}"


@then("the response should list the files")
def step_response_lists_files(context):
    """Verify response mentions files."""
    response = context.chat.get_response()
    assert response, "No response from assistant"
    assert len(response.strip()) > 0, "Response is empty"


@then("the tool result should contain exactly {count:d} lines")
def step_tool_result_line_count(context, count):
    """Verify tool result has specific number of lines."""
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) > 0, "No tool calls found"

    last_call = tool_calls[-1]
    result = last_call["result"]

    lines = [line for line in result.split("\n") if line.strip()]
    actual_count = len(lines)

    assert actual_count == count, f"Expected {count} lines, got {actual_count}:\n{result}"


@then('the tool result should contain "{text}"')
def step_tool_result_contains(context, text):
    """Verify tool result contains specific text."""
    tool_calls = context.chat.get_tool_calls()
    assert len(tool_calls) > 0, "No tool calls found"

    last_call = tool_calls[-1]
    result = last_call["result"]

    assert text in result, f"Tool result does not contain '{text}':\n{result}"
