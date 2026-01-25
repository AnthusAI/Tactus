"""
Built-in step definitions for Tactus primitives.

Provides a comprehensive library of steps for testing:
- Tool calls
- State management
- Procedure completion
- Iterations and timing
- Parameters and context
- Regex pattern matching
- Fuzzy string matching
"""

import logging
import re
import ast
from typing import Any

from .registry import StepRegistry

logger = logging.getLogger(__name__)


def _parse_step_string_literal(value: str) -> tuple[str, bool]:
    """
    Parse an optional quoted string literal from a step capture group.

    Supports single-quoted or double-quoted Python-style escapes, e.g.:
      "Hello! I'm World"
      'He said: "hi"'
      "Line 1\\nLine 2"

    Returns:
      (parsed_value, was_quoted)
    """
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] in {"'", '"'} and stripped[-1] == stripped[0]:
        try:
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, str):
                return parsed, True
        except Exception:
            # Fall back to raw string if the literal is malformed.
            return stripped, True
    return value, False


def register_builtin_steps(registry: StepRegistry) -> None:
    """
    Register all built-in step definitions.

    Args:
        registry: StepRegistry to register steps with
    """
    # Tool-related steps
    register_tool_steps(registry)

    # State-related steps
    register_state_steps(registry)

    # Output-related steps
    register_output_steps(registry)

    # Completion steps
    register_completion_steps(registry)

    # Iteration/timing steps
    register_iteration_steps(registry)

    # Parameter/context steps
    register_parameter_steps(registry)

    # Agent steps
    register_agent_steps(registry)

    # Regex pattern matching steps
    register_regex_steps(registry)

    # Model-related steps
    register_model_steps(registry)

    # Fuzzy string matching steps
    register_fuzzy_steps(registry)


# Tool-related steps


def register_tool_steps(registry: StepRegistry) -> None:
    """Register tool-related step definitions."""

    registry.register(r"the (?P<tool>[-\w]+) tool should be called", step_tool_called)

    registry.register(r"the (?P<tool>[-\w]+) tool should not be called", step_tool_not_called)

    registry.register(
        r"the (?P<tool>[-\w]+) tool should be called at least (?P<n>\d+) time",
        step_tool_called_at_least,
    )

    registry.register(
        r"the (?P<tool>[-\w]+) tool should be called at least (?P<n>\d+) times",
        step_tool_called_at_least,
    )

    registry.register(
        r"the (?P<tool>[-\w]+) tool should be called exactly (?P<n>\d+) time",
        step_tool_called_exactly,
    )

    registry.register(
        r"the (?P<tool>[-\w]+) tool should be called exactly (?P<n>\d+) times",
        step_tool_called_exactly,
    )

    registry.register(
        r"the (?P<tool>[-\w]+) tool should be called with (?P<param>\w+)=(?P<value>.+)",
        step_tool_called_with_param,
    )

    registry.register(
        r'the tool "(?P<tool>[-\w]+)" returns (?P<value>.+)',
        step_mock_tool_returns,
    )


def step_tool_called(context: Any, tool: str) -> None:
    """Check if a tool was called."""
    assert context.tool_called(tool), f"Tool '{tool}' was not called"


def step_tool_not_called(context: Any, tool: str) -> None:
    """Check if a tool was not called."""
    assert not context.tool_called(tool), f"Tool '{tool}' was called but shouldn't be"


def step_tool_called_at_least(context: Any, tool: str, n: str) -> None:
    """Check if tool was called at least N times."""
    count = context.tool_call_count(tool)
    min_count = int(n)
    assert count >= min_count, f"Tool '{tool}' called {count} times, expected at least {min_count}"


def step_tool_called_exactly(context: Any, tool: str, n: str) -> None:
    """Check if tool was called exactly N times."""
    count = context.tool_call_count(tool)
    expected = int(n)
    assert count == expected, f"Tool '{tool}' called {count} times, expected exactly {expected}"


def step_tool_called_with_param(context: Any, tool: str, param: str, value: str) -> None:
    """Check if tool was called with specific parameter value."""
    calls = context.tool_calls(tool)
    assert calls, f"Tool '{tool}' was not called"

    # Check if any call has the parameter with the expected value
    found = any(call.get("args", {}).get(param) == value for call in calls)
    assert found, f"Tool '{tool}' was not called with {param}={value}"


def step_mock_tool_returns(context: Any, tool: str, value: str) -> None:
    """Configure a runtime tool mock response for this scenario."""
    parsed_value, was_quoted = _parse_step_string_literal(value)
    if not was_quoted:
        try:
            parsed_value = ast.literal_eval(parsed_value)
        except Exception:
            # Treat unquoted values as plain strings (e.g., positive/neutral)
            pass

    if not hasattr(context, "mock_tool_returns"):
        raise AssertionError("Context does not support tool mocking")

    context.mock_tool_returns(tool, parsed_value)


def step_procedure_started(context: Any) -> None:
    """Mark that procedure context is ready (setup step)."""
    # This is a setup step - just verify context is ready
    # The actual execution happens in "When" steps
    assert context is not None, "Test context not initialized"


# State-related steps


def register_state_steps(registry: StepRegistry) -> None:
    """Register state-related step definitions."""

    registry.register(r"the state (?P<key>\w+) should be (?P<value>.+)", step_state_equals)

    registry.register(r"the state (?P<key>\w+) should exist", step_state_exists)

    registry.register(r"the state should contain (?P<key>\w+)", step_state_contains)


def step_state_equals(context: Any, key: str, value: str) -> None:
    """Check if state value equals expected."""
    actual = context.state_get(key)
    value, was_quoted = _parse_step_string_literal(value)
    # Convert to string for comparison
    actual_str = str(actual) if actual is not None else "None"
    if was_quoted:
        assert actual_str == value, f"State '{key}' is '{actual_str}', expected '{value}'"
        return
    assert actual_str == value, f"State '{key}' is '{actual_str}', expected '{value}'"


def step_state_exists(context: Any, key: str) -> None:
    """Check if state key exists."""
    exists = context.state_exists(key)
    assert exists, f"State key '{key}' does not exist"


def step_state_contains(context: Any, key: str) -> None:
    """Check if state contains key."""
    exists = context.state_exists(key)
    assert exists, f"State does not contain key '{key}'"


# Output-related steps


def register_output_steps(registry: StepRegistry) -> None:
    """Register output-related step definitions."""

    registry.register(r"the output should exist", step_output_value_exists)
    registry.register(r"the output should be (?P<value>.+)", step_output_value_equals)
    registry.register(
        r"the output should fuzzy match (?P<value>.+) with threshold (?P<threshold>[0-9]*\.?[0-9]+)",
        step_output_value_fuzzy_match,
    )
    registry.register(r"the output should fuzzy match (?P<value>.+)", step_output_value_fuzzy_match)

    registry.register(r"the output (?P<key>\w+) should be (?P<value>.+)", step_output_equals)

    registry.register(
        r"the output (?P<key>\w+) should not be (?P<value>.+)", step_output_not_equals
    )

    registry.register(r"the output (?P<key>\w+) should exist", step_output_exists)

    registry.register(r"the output should contain (?P<key>\w+)", step_output_contains)


def step_output_equals(context: Any, key: str, value: str) -> None:
    """Check if output value equals expected."""
    actual = context.output_get(key)
    value, was_quoted = _parse_step_string_literal(value)
    if was_quoted:
        actual_str = str(actual) if actual is not None else "None"
        assert actual_str == value, f"Output '{key}' is '{actual_str}', expected '{value}'"
        return

    # Handle boolean comparison specially
    if value.lower() in ("true", "false"):
        expected_bool = value.lower() == "true"
        if isinstance(actual, bool):
            assert actual == expected_bool, f"Output '{key}' is {actual}, expected {expected_bool}"
        else:
            actual_str = str(actual).lower()
            assert actual_str == value.lower(), f"Output '{key}' is '{actual}', expected '{value}'"
    else:
        # Try numeric comparison first
        try:
            expected_num = float(value)
            if isinstance(actual, (int, float)):
                assert (
                    actual == expected_num
                ), f"Output '{key}' is {actual}, expected {expected_num}"
            else:
                actual_num = float(actual)
                assert (
                    actual_num == expected_num
                ), f"Output '{key}' is {actual_num}, expected {expected_num}"
        except (ValueError, TypeError):
            # Fall back to string comparison
            actual_str = str(actual) if actual is not None else "None"
            assert actual_str == value, f"Output '{key}' is '{actual_str}', expected '{value}'"


def step_output_value_exists(context: Any) -> None:
    """Check if scalar output exists (non-None)."""
    actual = context.output_value()
    assert actual is not None, "Output is missing"


def step_output_value_equals(context: Any, value: str) -> None:
    """Check if scalar output equals expected."""
    actual = context.output_value()
    value, was_quoted = _parse_step_string_literal(value)
    if was_quoted:
        actual_str = str(actual) if actual is not None else "None"
        assert actual_str == value, f"Output is '{actual_str}', expected '{value}'"
        return

    # Handle boolean comparison specially
    if value.lower() in ("true", "false"):
        expected_bool = value.lower() == "true"
        if isinstance(actual, bool):
            assert actual == expected_bool, f"Output is {actual}, expected {expected_bool}"
        else:
            actual_str = str(actual).lower() if actual is not None else "none"
            assert actual_str == value.lower(), f"Output is '{actual}', expected '{value}'"
        return

    # Try numeric comparison first
    try:
        expected_num = float(value)
        if isinstance(actual, (int, float)):
            assert actual == expected_num, f"Output is {actual}, expected {expected_num}"
        else:
            actual_num = float(actual)
            assert actual_num == expected_num, f"Output is '{actual}', expected {expected_num}"
        return
    except (ValueError, TypeError):
        pass

    actual_str = str(actual) if actual is not None else "None"
    assert actual_str == value, f"Output is '{actual_str}', expected '{value}'"


def step_output_value_fuzzy_match(context: Any, value: str, threshold: str = "0.8") -> None:
    """Check if scalar output is similar to expected value above a threshold.

    This is a deterministic, non-LLM fuzzy match based on string similarity.

    Default behavior:
    - Case-insensitive (compares lowercased text)
    - Punctuation-insensitive (strips punctuation)

    Multi-match syntax (best-effort):
      Then the output should fuzzy match any of ["Hello", "Hi", "Hey"] with threshold 0.9
    """
    import difflib

    def _normalize_text(text: str) -> str:
        # Lowercase + strip punctuation + collapse whitespace.
        normalized = re.sub(r"[^\w\s]", "", text.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    actual = context.output_value()
    assert actual is not None, "Output is missing"

    try:
        threshold_f = float(threshold)
    except ValueError:
        raise AssertionError(f"Invalid threshold: {threshold}")

    expected_raw, was_quoted = _parse_step_string_literal(value)
    expected_raw = expected_raw.strip() if not was_quoted else expected_raw

    expected_values: list[str]

    if expected_raw.lower().startswith("any of "):
        values_str = expected_raw[7:].strip()
        try:
            parsed = ast.literal_eval(values_str)
        except Exception:
            parsed = None

        expected_values = []
        if isinstance(parsed, (list, tuple)):
            for item in parsed:
                expected_values.append(item if isinstance(item, str) else str(item))
        else:
            parts = [p.strip() for p in values_str.split(",") if p.strip()]
            for part in parts:
                parsed_part, _ = _parse_step_string_literal(part)
                expected_values.append(parsed_part)

        if not expected_values:
            raise AssertionError(f"No expected values provided: {value}")
    else:
        expected_values = [expected_raw]

    actual_norm = _normalize_text(str(actual))
    best_ratio = -1.0
    best_expected = None

    for expected in expected_values:
        expected_norm = _normalize_text(expected)
        if expected_norm and (expected_norm in actual_norm or actual_norm in expected_norm):
            ratio = 1.0
        else:
            ratio = difflib.SequenceMatcher(None, actual_norm, expected_norm).ratio()

        if ratio > best_ratio:
            best_ratio = ratio
            best_expected = expected

    assert best_ratio >= threshold_f, (
        f"Output similarity is {best_ratio:.3f} (threshold {threshold_f:.3f}). "
        f"Output is '{actual}', best match was '{best_expected}'. "
        f"Expected: {expected_values}"
    )


def step_output_not_equals(context: Any, key: str, value: str) -> None:
    """Check if output value does not equal the specified value."""
    actual = context.output_get(key)
    value, was_quoted = _parse_step_string_literal(value)
    if was_quoted:
        actual_str = str(actual) if actual is not None else "None"
        assert actual_str != value, f"Output '{key}' is '{actual_str}', should not be '{value}'"
        return

    # Handle boolean comparison specially
    if value.lower() in ("true", "false"):
        expected_bool = value.lower() == "true"
        if isinstance(actual, bool):
            assert (
                actual != expected_bool
            ), f"Output '{key}' is {actual}, should not be {expected_bool}"
        else:
            actual_str = str(actual).lower()
            assert (
                actual_str != value.lower()
            ), f"Output '{key}' is '{actual}', should not be '{value}'"
    else:
        # Try numeric comparison first
        try:
            expected_num = float(value)
            if isinstance(actual, (int, float)):
                assert (
                    actual != expected_num
                ), f"Output '{key}' is {actual}, should not be {expected_num}"
            else:
                actual_num = float(actual)
                assert (
                    actual_num != expected_num
                ), f"Output '{key}' is {actual_num}, should not be {expected_num}"
        except (ValueError, TypeError):
            # Fall back to string comparison
            actual_str = str(actual) if actual is not None else "None"
            assert actual_str != value, f"Output '{key}' is '{actual_str}', should not be '{value}'"


def step_output_exists(context: Any, key: str) -> None:
    """Check if output key exists."""
    exists = context.output_exists(key)
    assert exists, f"Output key '{key}' does not exist"


def step_output_contains(context: Any, key: str) -> None:
    """Check if output contains key."""
    exists = context.output_exists(key)
    assert exists, f"Output does not contain key '{key}'"


# Completion steps


def register_completion_steps(registry: StepRegistry) -> None:
    """Register completion-related step definitions."""

    registry.register(r"the procedure has started", step_procedure_started)
    registry.register(r"the procedure should complete successfully", step_procedure_completes)

    registry.register(r"the procedure should fail", step_procedure_fails)

    registry.register(r"the stop reason should be (?P<reason>.+)", step_stop_reason_equals)

    registry.register(r"the stop reason should contain (?P<text>.+)", step_stop_reason_contains)


def step_procedure_completes(context: Any) -> None:
    """Check if procedure completed successfully."""
    assert context.stop_success(), "Procedure did not complete successfully"


def step_procedure_fails(context: Any) -> None:
    """Check if procedure failed."""
    assert not context.stop_success(), "Procedure completed successfully but should have failed"


def step_stop_reason_equals(context: Any, reason: str) -> None:
    """Check if stop reason equals expected."""
    actual = context.stop_reason()
    assert actual == reason, f"Stop reason is '{actual}', expected '{reason}'"


def step_stop_reason_contains(context: Any, text: str) -> None:
    """Check if stop reason contains text."""
    reason = context.stop_reason()
    assert text in reason, f"Stop reason '{reason}' does not contain '{text}'"


# Iteration/timing steps


def register_iteration_steps(registry: StepRegistry) -> None:
    """Register iteration and timing step definitions."""

    registry.register(
        r"the total iterations should be less than (?P<n>\d+)", step_iterations_less_than
    )

    registry.register(
        r"the total iterations should be between (?P<min>\d+) and (?P<max>\d+)",
        step_iterations_between,
    )

    registry.register(r"the agent should take at least (?P<n>\d+) turn", step_agent_turns_at_least)

    registry.register(r"the agent should take at least (?P<n>\d+) turns", step_agent_turns_at_least)


def step_iterations_less_than(context: Any, n: str) -> None:
    """Check if total iterations is less than N."""
    iterations = context.iterations
    max_iterations = int(n)
    assert (
        iterations < max_iterations
    ), f"Total iterations is {iterations}, expected less than {max_iterations}"


def step_iterations_between(context: Any, min: str, max: str) -> None:
    """Check if iterations is between min and max."""
    iterations = context.iterations
    min_val = int(min)
    max_val = int(max)
    assert (
        min_val <= iterations <= max_val
    ), f"Total iterations is {iterations}, expected between {min_val} and {max_val}"


def step_agent_turns_at_least(context: Any, n: str) -> None:
    """Check if agent took at least N turns."""
    turns = context.agent_turns()
    min_turns = int(n)
    assert turns >= min_turns, f"Agent took {turns} turns, expected at least {min_turns}"


# Parameter/context steps


def register_parameter_steps(registry: StepRegistry) -> None:
    """Register parameter and context step definitions."""

    registry.register(r"the (?P<param>\w+) parameter is (?P<value>.+)", step_parameter_equals)

    registry.register(
        r"the agent'?s? context should include (?P<text>.+)", step_agent_context_includes
    )

    # Input-setting steps (Given clauses to set procedure inputs)
    registry.register(r'the input (?P<key>\w+) is "(?P<value>.+)"', step_input_set_string)

    registry.register(r"the input (?P<key>\w+) is \[(?P<values>.+)\]", step_input_set_array)

    registry.register(r"the input (?P<key>\w+) is (?P<value>-?\d+\.?\d*)", step_input_set_number)


def step_parameter_equals(context: Any, param: str, value: str) -> None:
    """Check if parameter equals expected value."""
    params = context.get_params()
    actual = params.get(param)
    actual_str = str(actual) if actual is not None else "None"
    assert actual_str == value, f"Parameter '{param}' is '{actual_str}', expected '{value}'"


def step_agent_context_includes(context: Any, text: str) -> None:
    """Check if agent context includes text."""
    agent_context = context.agent_context()
    assert text in agent_context, f"Agent context does not include '{text}'"


def step_input_set_string(context: Any, key: str, value: str) -> None:
    """Set a string input parameter."""
    context.set_input(key, value)


def step_input_set_number(context: Any, key: str, value: str) -> None:
    """Set a numeric input parameter."""
    # Parse as float or int
    if "." in value:
        context.set_input(key, float(value))
    else:
        context.set_input(key, int(value))


def step_input_set_array(context: Any, key: str, values: str) -> None:
    """Set an array input parameter from comma-separated values."""
    import ast

    # Try to parse as Python literal first
    try:
        parsed = ast.literal_eval(f"[{values}]")
        context.set_input(key, parsed)
    except (ValueError, SyntaxError):
        # Fall back to comma-split for simple values
        items = [v.strip() for v in values.split(",")]
        # Try to convert to numbers if possible
        parsed_items = []
        for item in items:
            try:
                if "." in item:
                    parsed_items.append(float(item))
                else:
                    parsed_items.append(int(item))
            except ValueError:
                parsed_items.append(item)
        context.set_input(key, parsed_items)


# Agent steps


def register_agent_steps(registry: StepRegistry) -> None:
    """Register agent-related step definitions."""

    registry.register(r"the (?P<agent>\w+) agent takes turn", step_agent_takes_turn)

    registry.register(r"the (?P<agent>\w+) agent takes turns", step_agent_takes_turn)

    registry.register(
        r'the agent "(?P<agent>[^"]+)" responds with (?P<message>.+)',
        step_mock_agent_responds_with,
    )

    registry.register(
        r'the agent "(?P<agent>[^"]+)" calls tool "(?P<tool>[^"]+)" with args (?P<args>.+)',
        step_mock_agent_calls_tool_with_args,
    )

    registry.register(
        r'the agent "(?P<agent>[^"]+)" returns data (?P<data>.+)',
        step_mock_agent_returns_data,
    )

    registry.register(r"the message is (?P<message>.+)", step_set_scenario_message)

    registry.register(r"the procedure run", step_procedure_runs)

    registry.register(r"the procedure runs", step_procedure_runs)


def step_agent_takes_turn(context: Any, agent: str) -> None:
    """Execute agent turn(s)."""
    # This step actually executes the procedure
    # The agent parameter is informational - the procedure runs as defined
    context.run_procedure()


def step_mock_agent_responds_with(
    context: Any, agent: str, message: str, when_message: str | None = None
) -> None:
    """Configure a per-scenario mock agent response (temporal)."""
    message, _ = _parse_step_string_literal(message)
    when_message_parsed = None
    if when_message is not None:
        when_message_parsed, _ = _parse_step_string_literal(when_message)
    if not hasattr(context, "mock_agent_response"):
        raise AssertionError("Context does not support agent mocking")
    context.mock_agent_response(agent, message, when_message=when_message_parsed)


def step_set_scenario_message(context: Any, message: str) -> None:
    """Set the scenario's primary message for coordinating mocks with expectations."""
    message, _ = _parse_step_string_literal(message)
    if not hasattr(context, "set_scenario_message"):
        raise AssertionError("Context does not support scenario message")
    context.set_scenario_message(message)


def step_mock_agent_calls_tool_with_args(context: Any, agent: str, tool: str, args: str) -> None:
    """Configure a per-scenario mocked agent tool call (recorded into Tool primitive)."""
    args_str, _ = _parse_step_string_literal(args)
    try:
        parsed_args = ast.literal_eval(args_str)
    except Exception:
        raise AssertionError(f"Invalid tool args literal: {args}")

    if not isinstance(parsed_args, dict):
        raise AssertionError(f"Tool args must be an object/dict, got {type(parsed_args).__name__}")

    if not hasattr(context, "mock_agent_tool_call"):
        raise AssertionError("Context does not support agent tool call mocking")

    context.mock_agent_tool_call(agent, tool, parsed_args)


def step_mock_agent_returns_data(context: Any, agent: str, data: str) -> None:
    """Configure structured output mock data for an agent's next mocked turn."""
    data_str, _ = _parse_step_string_literal(data)
    try:
        parsed = ast.literal_eval(data_str)
    except Exception:
        raise AssertionError(f"Invalid data literal: {data}")

    if not isinstance(parsed, dict):
        raise AssertionError(f"Data must be an object/dict, got {type(parsed).__name__}")

    if not hasattr(context, "mock_agent_data"):
        raise AssertionError("Context does not support agent data mocking")

    context.mock_agent_data(agent, parsed)


def step_procedure_runs(context: Any) -> None:
    """Execute the procedure.

    Fails the step if the procedure has an execution error (e.g., undefined variables).
    """
    context.run_procedure()

    # Check for execution errors (e.g., Lua errors like undefined variables)
    # context is TactusTestContext when called from generated behave steps
    if hasattr(context, "execution_result") and context.execution_result:
        result = context.execution_result
        if not result.get("success", True):
            error = result.get("error", "Unknown error")
            raise AssertionError(f"Procedure execution failed: {error}")


# Regex pattern matching steps


def register_regex_steps(registry: StepRegistry) -> None:
    """Register regex pattern matching steps."""

    # Output regex matching
    registry.register(
        r'the output (?P<key>\w+) should match pattern "(?P<pattern>.+)"',
        step_output_matches_pattern,
    )

    # State regex matching
    registry.register(
        r'the state (?P<key>\w+) should match pattern "(?P<pattern>.+)"',
        step_state_matches_pattern,
    )

    # Stop reason regex matching
    registry.register(
        r'the stop reason should match pattern "(?P<pattern>.+)"',
        step_stop_reason_matches_pattern,
    )

    # Tool argument regex matching
    registry.register(
        r'the (?P<tool>[-\w]+) tool should be called with (?P<param>\w+) matching pattern "(?P<pattern>.+)"',
        step_tool_arg_matches_pattern,
    )


def step_output_matches_pattern(context: Any, key: str, pattern: str) -> None:
    """Check if output value matches regex pattern."""
    actual = context.output_get(key)
    actual_str = str(actual) if actual is not None else ""

    try:
        regex = re.compile(pattern)
        assert regex.search(
            actual_str
        ), f"Output '{key}' value '{actual_str}' does not match pattern '{pattern}'"
    except re.error as e:
        raise AssertionError(f"Invalid regex pattern '{pattern}': {e}")


def step_state_matches_pattern(context: Any, key: str, pattern: str) -> None:
    """Check if state value matches regex pattern."""
    actual = context.state_get(key)
    actual_str = str(actual) if actual is not None else ""

    try:
        regex = re.compile(pattern)
        assert regex.search(
            actual_str
        ), f"State '{key}' value '{actual_str}' does not match pattern '{pattern}'"
    except re.error as e:
        raise AssertionError(f"Invalid regex pattern '{pattern}': {e}")


def step_stop_reason_matches_pattern(context: Any, pattern: str) -> None:
    """Check if stop reason matches regex pattern."""
    actual = context.stop_reason()

    try:
        regex = re.compile(pattern)
        assert regex.search(actual), f"Stop reason '{actual}' does not match pattern '{pattern}'"
    except re.error as e:
        raise AssertionError(f"Invalid regex pattern '{pattern}': {e}")


def step_tool_arg_matches_pattern(context: Any, tool: str, param: str, pattern: str) -> None:
    """Check if tool was called with parameter matching regex pattern."""
    calls = context.tool_calls(tool)
    assert calls, f"Tool '{tool}' was not called"

    try:
        regex = re.compile(pattern)
        # Check if any call has the parameter matching the pattern
        found = False
        for call in calls:
            param_value = call.get("args", {}).get(param)
            if param_value is not None:
                param_str = str(param_value)
                if regex.search(param_str):
                    found = True
                    break

        assert found, f"Tool '{tool}' was not called with {param} matching pattern '{pattern}'"
    except re.error as e:
        raise AssertionError(f"Invalid regex pattern '{pattern}': {e}")


# Fuzzy string matching steps


def register_fuzzy_steps(registry: StepRegistry) -> None:
    """Register fuzzy string matching steps."""

    # Output fuzzy matching (default threshold)
    registry.register(
        r'the output (?P<key>\w+) should be similar to "(?P<text>.+)"',
        step_output_similar_default,
    )

    # Output fuzzy matching (custom threshold)
    registry.register(
        r'the output (?P<key>\w+) should be similar to "(?P<text>.+)" with (?P<threshold>\d+)% similarity',
        step_output_similar_threshold,
    )

    # State fuzzy matching (default threshold)
    registry.register(
        r'the state (?P<key>\w+) should be similar to "(?P<text>.+)"',
        step_state_similar_default,
    )

    # State fuzzy matching (custom threshold)
    registry.register(
        r'the state (?P<key>\w+) should be similar to "(?P<text>.+)" with (?P<threshold>\d+)% similarity',
        step_state_similar_threshold,
    )


def step_output_similar_default(context: Any, key: str, text: str) -> None:
    """Check if output is similar to expected text (80% default threshold)."""
    step_output_similar_threshold(context, key, text, "80")


def step_output_similar_threshold(context: Any, key: str, text: str, threshold: str) -> None:
    """Check if output is similar to expected text with custom threshold."""
    from rapidfuzz import fuzz

    actual = context.output_get(key)
    actual_str = str(actual) if actual is not None else ""

    threshold_val = int(threshold)
    similarity = fuzz.ratio(actual_str, text)

    assert similarity >= threshold_val, (
        f"Output '{key}' similarity is {similarity}% (expected >= {threshold_val}%)\n"
        f"  Actual: '{actual_str}'\n"
        f"  Expected: '{text}'"
    )


def step_state_similar_default(context: Any, key: str, text: str) -> None:
    """Check if state is similar to expected text (80% default threshold)."""
    step_state_similar_threshold(context, key, text, "80")


def step_state_similar_threshold(context: Any, key: str, text: str, threshold: str) -> None:
    """Check if state is similar to expected text with custom threshold."""
    from rapidfuzz import fuzz

    actual = context.state_get(key)
    actual_str = str(actual) if actual is not None else ""

    threshold_val = int(threshold)
    similarity = fuzz.ratio(actual_str, text)

    assert similarity >= threshold_val, (
        f"State '{key}' similarity is {similarity}% (expected >= {threshold_val}%)\n"
        f"  Actual: '{actual_str}'\n"
        f"  Expected: '{text}'"
    )


# Model-related steps


def register_model_steps(registry: StepRegistry) -> None:
    """Register model-related step definitions."""

    # Model prediction step (When clause)
    registry.register(r"the (?P<model>\w+) model predicts", step_model_predicts)


def step_model_predicts(context: Any, model: str) -> None:
    """Trigger model prediction by running the procedure.

    This step runs the procedure which should contain the model prediction.
    """
    # Model prediction happens during procedure execution
    context.run_procedure()
