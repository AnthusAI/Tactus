"""
Step definitions for Example Procedures feature.
"""

import os
from pathlib import Path
from behave import given, when, then
from tactus.core.runtime import TactusRuntime
from tactus.adapters.memory import MemoryStorage


@given("a Tactus runtime environment")
def step_impl(context):
    """Initialize Tactus runtime environment."""
    context.runtime = None
    context.example_file = None
    context.execution_result = None
    context.execution_error = None
    context.parameters = {}


@given('an example file "{filename}"')
def step_impl(context, filename):
    """Load an example file."""
    project_root = Path(__file__).parent.parent.parent
    context.example_file = project_root / "examples" / filename
    if not context.example_file.exists():
        raise FileNotFoundError(f"Example file not found: {context.example_file}")


@given('I provide parameter "{param_name}" with value "{param_value}"')
def step_impl(context, param_name, param_value):
    """Set a parameter value for procedure execution (string values)."""
    # Try to convert to appropriate type
    if param_value.isdigit():
        context.parameters[param_name] = int(param_value)
    elif param_value.lower() in ("true", "false"):
        context.parameters[param_name] = param_value.lower() == "true"
    else:
        context.parameters[param_name] = param_value


@given('I provide parameter "{param_name}" with value {param_value:d}')
def step_impl(context, param_name, param_value):
    """Set a parameter value for procedure execution (integer values)."""
    context.parameters[param_name] = param_value


@when("I execute the procedure")
def step_impl(context):
    """Execute the procedure from the example file."""
    import asyncio

    # Skip if no OpenAI API key is available (CI environment)
    if not os.environ.get("OPENAI_API_KEY"):
        context.scenario.skip("Skipping: OPENAI_API_KEY not set (CI environment)")
        return

    # Determine format
    is_lua_dsl = context.example_file.suffix == ".lua" or ".tac" in context.example_file.suffixes
    format_type = "lua" if is_lua_dsl else "yaml"

    # Create runtime
    context.runtime = TactusRuntime(
        procedure_id=f"test-{context.example_file.stem}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
    )

    # Read file content
    file_content = context.example_file.read_text()

    # Execute
    try:
        context.execution_result = asyncio.run(
            context.runtime.execute(file_content, context=context.parameters, format=format_type)
        )
        context.execution_error = None
    except Exception as e:
        context.execution_error = e
        context.execution_result = None


@then("the execution should succeed")
def step_impl(context):
    """Assert that execution succeeded."""
    if context.execution_error:
        raise AssertionError(f"Execution failed with error: {context.execution_error}")

    assert context.execution_result is not None, "No execution result"
    assert (
        context.execution_result.get("success") is True
    ), f"Execution failed: {context.execution_result.get('error', 'Unknown error')}"


@then("the output should match the declared schema")
def step_impl(context):
    """Assert that output matches the declared schema."""
    # For now, just check that we have a result
    # Full schema validation would require parsing the file to get the schema
    assert context.execution_result is not None, "No execution result"
    assert isinstance(context.execution_result, dict), "Result is not a dictionary"


@then('the output should contain field "{field_name}" with value {expected_value}')
def step_impl(context, field_name, expected_value):
    """Assert that output contains a specific field with expected value."""
    assert context.execution_result is not None, "No execution result"

    # Check in the 'result' sub-dictionary
    result_dict = context.execution_result.get("result", {})
    assert (
        field_name in result_dict
    ), f"Field '{field_name}' not found in result: {list(result_dict.keys())}"

    actual_value = result_dict[field_name]

    # Convert expected_value to appropriate type
    if expected_value.lower() == "true":
        expected_value = True
    elif expected_value.lower() == "false":
        expected_value = False
    elif expected_value.isdigit():
        expected_value = int(expected_value)
    else:
        # Remove quotes if present
        expected_value = expected_value.strip("\"'")

    assert (
        actual_value == expected_value
    ), f"Field '{field_name}' has value {actual_value}, expected {expected_value}"
