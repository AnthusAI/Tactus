"""
Step definitions for Example Procedures feature.
"""

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
    examples_dir = project_root / "examples"

    # Try exact match first
    context.example_file = examples_dir / filename
    if context.example_file.exists():
        return

    # Extract the base name without extension for fuzzy matching
    base_name = filename.replace(".tac", "").replace(".lua", "")

    # Split into words for matching
    base_words = set(base_name.replace("-", " ").split())

    # Try to find file with word-based matching
    best_match = None
    best_score = 0

    for example_file in examples_dir.glob("*.tac"):
        file_base = example_file.stem  # filename without extension

        # Exact substring match (highest priority)
        if base_name in file_base or file_base.endswith(base_name):
            context.example_file = example_file
            return

        # Word-based matching (fallback)
        file_words = set(file_base.replace("-", " ").split())
        overlap = base_words & file_words
        score = len(overlap)

        if score > best_score:
            best_score = score
            best_match = example_file

    # Use best match if we found at least 2 matching words
    if best_match and best_score >= 2:
        context.example_file = best_match
        return

    # Not found
    raise FileNotFoundError(f"Example file not found: {filename}\nSearched in: {examples_dir}")


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
    from tactus.core.config_manager import ConfigManager
    from tactus.core.mocking import MockManager
    from tactus.testing.mock_tools import (
        MockToolRegistry,
        MockedToolPrimitive,
        create_default_mocks,
    )

    # Example procedures are validated in mocked mode so the BDD suite is deterministic
    # and does not require network access or real API keys.
    mock_registry = MockToolRegistry()
    for tool_name, response in create_default_mocks().items():
        mock_registry.register(tool_name, response)
    tool_primitive = MockedToolPrimitive(mock_registry)

    # Determine format
    is_lua_dsl = context.example_file.suffix == ".lua" or ".tac" in context.example_file.suffixes
    format_type = "lua" if is_lua_dsl else "yaml"

    # Load configuration cascade (includes sidecar .tac.yml if present)
    config_manager = ConfigManager()
    merged_config = config_manager.load_cascade(context.example_file)

    # Get tool_paths and mcp_servers from merged config
    tool_paths = merged_config.get("tool_paths")
    mcp_servers = merged_config.get("mcp_servers", {})
    if not tool_paths:
        project_root = Path(__file__).parent.parent.parent
        tool_paths = [str(project_root / "examples" / "tools")]

    # Create runtime with config
    context.runtime = TactusRuntime(
        procedure_id=f"test-{context.example_file.stem}",
        storage_backend=MemoryStorage(),
        hitl_handler=None,
        chat_recorder=None,
        mcp_server=None,
        mcp_servers=mcp_servers,
        tool_primitive=tool_primitive,
        tool_paths=tool_paths,
        external_config=merged_config,
        source_file_path=str(context.example_file),
    )
    context.runtime.mock_manager = MockManager()
    context.runtime.mock_all_agents = True

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
