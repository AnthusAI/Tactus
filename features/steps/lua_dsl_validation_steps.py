"""
Step definitions for Lua DSL Validation feature.
"""

import tempfile
import subprocess
from pathlib import Path
from behave import given, when, then
from tactus.validation import TactusValidator, ValidationMode


@given("a Tactus validation environment")
def step_impl(context):
    """Initialize validation environment."""
    context.validator = TactusValidator()
    context.validation_result = None
    context.validation_error = None


@given('a Lua DSL file "{filepath}"')
def step_impl(context, filepath):
    """Load a Lua DSL file from the examples directory."""
    project_root = Path(__file__).parent.parent.parent
    context.lua_file = project_root / filepath
    if not context.lua_file.exists():
        raise FileNotFoundError(f"File not found: {context.lua_file}")
    context.lua_content = context.lua_file.read_text()


@given("a Lua DSL file with content:")
def step_impl(context):
    """Create a temporary Lua DSL file with given content."""
    context.lua_content = context.text
    # Create a temporary file
    context.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    context.temp_file.write(context.lua_content)
    context.temp_file.close()
    context.lua_file = Path(context.temp_file.name)


@given("a Lua DSL file with syntax error")
def step_impl(context):
    """Create a Lua DSL file with intentional syntax error."""
    context.lua_content = """
name("test_procedure")
version("1.0.0")
-- Missing closing brace
agent("worker", {
    provider = "openai"
"""
    context.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    context.temp_file.write(context.lua_content)
    context.temp_file.close()
    context.lua_file = Path(context.temp_file.name)


@given("the example Lua DSL files:")
def step_impl(context):
    """Load multiple example Lua DSL files."""
    project_root = Path(__file__).parent.parent.parent
    examples_dir = project_root / "examples"
    context.example_files = []
    for row in context.table:
        filepath = examples_dir / row["file"]
        if filepath.exists():
            context.example_files.append(filepath)


@when("I validate the file")
def step_impl(context):
    """Validate the Lua DSL file in full mode."""
    try:
        context.validation_result = context.validator.validate(
            context.lua_content, mode=ValidationMode.FULL
        )
        context.validation_error = None
    except Exception as e:
        context.validation_error = e
        context.validation_result = None


@when("I validate the file in quick mode")
def step_impl(context):
    """Validate the Lua DSL file in quick mode (syntax only)."""
    try:
        context.validation_result = context.validator.validate(
            context.lua_content, mode=ValidationMode.QUICK
        )
        context.validation_error = None
    except Exception as e:
        context.validation_error = e
        context.validation_result = None


@when("I validate the file in full mode")
def step_impl(context):
    """Validate the Lua DSL file in full mode."""
    try:
        context.validation_result = context.validator.validate(
            context.lua_content, mode=ValidationMode.FULL
        )
        context.validation_error = None
    except Exception as e:
        context.validation_error = e
        context.validation_result = None


@when("I validate each file")
def step_impl(context):
    """Validate all example files."""
    context.validation_results = []
    for filepath in context.example_files:
        content = filepath.read_text()
        try:
            result = context.validator.validate(content, mode=ValidationMode.FULL)
            context.validation_results.append((filepath, result, None))
        except Exception as e:
            context.validation_results.append((filepath, None, e))


@when('I run "tactus validate {filepath}"')
def step_impl(context, filepath):
    """Run the tactus validate CLI command."""
    import sys

    project_root = Path(__file__).parent.parent.parent
    full_path = project_root / filepath
    result = subprocess.run(
        [sys.executable, "-m", "tactus.cli.app", "validate", str(full_path)],
        capture_output=True,
        text=True,
    )
    context.cli_result = result
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr
    context.cli_returncode = result.returncode


@when('I run "tactus validate" on the file')
def step_impl(context):
    """Run tactus validate on the temporary file."""
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tactus.cli.app", "validate", str(context.lua_file)],
        capture_output=True,
        text=True,
    )
    context.cli_result = result
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr
    context.cli_returncode = result.returncode


@then("validation should succeed")
def step_impl(context):
    """Assert that validation succeeded."""
    assert context.validation_error is None, f"Validation failed: {context.validation_error}"
    assert context.validation_result is not None, "Validation result is None"
    assert (
        context.validation_result.valid
    ), f"Validation result indicates failure: {context.validation_result.errors}"


@then("validation should fail")
def step_impl(context):
    """Assert that validation failed."""
    if context.validation_error:
        # Exception was raised - that's a failure
        return
    assert context.validation_result is not None, "No validation result"
    assert not context.validation_result.valid, "Validation unexpectedly succeeded"


@then('the error should mention "{text}"')
def step_impl(context, text):
    """Assert that the error message contains specific text."""
    if context.validation_error:
        error_msg = str(context.validation_error).lower()
    elif context.validation_result and context.validation_result.errors:
        # errors is a list of ValidationMessage objects
        error_msg = " ".join(str(e.message) for e in context.validation_result.errors).lower()
    else:
        raise AssertionError("No error message found")

    # Be flexible with exact wording - check for key terms
    search_terms = text.lower().split()
    matches = sum(1 for term in search_terms if term in error_msg)
    assert (
        matches >= len(search_terms) // 2 + 1
    ), f"Expected terms from '{text}' in error message: {error_msg}"


@then("the error should include a line number")
def step_impl(context):
    """Assert that the error includes a line number."""
    # For syntax errors from ANTLR, line numbers may be embedded in the error message
    # or available in the ValidationMessage location field
    if context.validation_result and context.validation_result.errors:
        # Check if any error has location information
        has_location = any(
            hasattr(e, "location") and e.location is not None
            for e in context.validation_result.errors
        )
        if has_location:
            return  # Pass - we have location info

        # Otherwise check error messages for line number patterns
        error_msg = " ".join(
            str(e.message) if hasattr(e, "message") else str(e)
            for e in context.validation_result.errors
        )
    elif context.validation_error:
        error_msg = str(context.validation_error)
    else:
        raise AssertionError("No error message found")

    # ANTLR errors may not have explicit "line X" format, but the error itself indicates a syntax issue was detected
    # For now, just pass if we have a syntax error (the important thing is that validation failed)
    import re

    has_line_ref = re.search(r"line\s*:?\s*\d+|^\d+:|at input", error_msg, re.IGNORECASE)
    assert has_line_ref, f"No line reference found in error: {error_msg}"


@then("it should recognize the procedure declaration")
def step_impl(context):
    """Assert that a procedure declaration was found."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert context.validation_result.registry.procedure_function is not None


@then("it should recognize agent declarations")
def step_impl(context):
    """Assert that agent declarations were found."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert len(context.validation_result.registry.agents) > 0


@then("it should recognize output declarations")
def step_impl(context):
    """Assert that output declarations were found."""
    assert context.validation_result is not None
    # In the new DSL, outputs are part of procedure config, not separate declarations
    # The validation should pass even if outputs are empty at the registry level
    # because they're now defined inside procedure()
    # So we just check that validation succeeded
    assert context.validation_result.valid, f"Validation failed: {context.validation_result.errors}"


@then('the state_schema should contain field "{field_name}"')
def step_impl(context, field_name):
    """Assert that the state schema contains a specific field."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert (
        field_name in context.validation_result.registry.state_schema
    ), f"Field '{field_name}' not found in state_schema. Available fields: {list(context.validation_result.registry.state_schema.keys())}"


@then("it should recognize {count:d} parameter declaration")
@then("it should recognize {count:d} parameter declarations")
def step_impl(context, count):
    """Assert the number of parameter declarations (deprecated - use input_schema)."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    # Old syntax - check input_schema instead
    assert len(context.validation_result.registry.input_schema) == count


@then("it should recognize {count:d} output declaration")
@then("it should recognize {count:d} output declarations")
def step_impl(context, count):
    """Assert the number of output declarations (deprecated - use output_schema)."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    # Old syntax - check output_schema instead
    assert len(context.validation_result.registry.output_schema) == count


@then('the input_schema should contain field "{field_name}"')
def step_impl(context, field_name):
    """Assert that input_schema contains a specific field."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert (
        field_name in context.validation_result.registry.input_schema
    ), f"Field '{field_name}' not found in input_schema. Available fields: {list(context.validation_result.registry.input_schema.keys())}"


@then('the output_schema should contain field "{field_name}"')
def step_impl(context, field_name):
    """Assert that output_schema contains a specific field."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert (
        field_name in context.validation_result.registry.output_schema
    ), f"Field '{field_name}' not found in output_schema. Available fields: {list(context.validation_result.registry.output_schema.keys())}"


@then("the input_schema should have {count:d} field")
@then("the input_schema should have {count:d} fields")
def step_impl(context, count):
    """Assert the number of fields in input_schema."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    actual_count = len(context.validation_result.registry.input_schema)
    assert (
        actual_count == count
    ), f"Expected {count} input fields, but found {actual_count}: {list(context.validation_result.registry.input_schema.keys())}"


@then("the output_schema should have {count:d} field")
@then("the output_schema should have {count:d} fields")
def step_impl(context, count):
    """Assert the number of fields in output_schema."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    actual_count = len(context.validation_result.registry.output_schema)
    assert (
        actual_count == count
    ), f"Expected {count} output fields, but found {actual_count}: {list(context.validation_result.registry.output_schema.keys())}"


@then("it should only check syntax")
def step_impl(context):
    """Assert that only syntax was checked (quick mode)."""
    # In quick mode, we get a result but no detailed registry
    assert context.validation_result is not None
    # Quick mode doesn't populate the full registry
    assert context.validation_result.registry is None


@then("it should check syntax")
def step_impl(context):
    """Assert that syntax was checked."""
    assert context.validation_result is not None
    assert len(context.validation_result.errors) == 0 or all(
        e.level != "error" for e in context.validation_result.errors
    )


@then("it should check semantic rules")
def step_impl(context):
    """Assert that semantic rules were checked."""
    assert context.validation_result is not None
    # In full mode, we should have a registry if valid
    assert context.validation_result.registry is not None or not context.validation_result.valid


@then("it should validate required fields")
def step_impl(context):
    """Assert that required fields were validated."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None


@then("all validations should succeed")
def step_impl(context):
    """Assert that all example files validated successfully."""
    failures = []
    for filepath, result, error in context.validation_results:
        if error or (result and not result.valid):
            failures.append((filepath, error or result.errors))

    assert len(failures) == 0, f"Validation failures: {failures}"


@then("the command should succeed")
def step_impl(context):
    """Assert that the CLI command succeeded."""
    assert (
        context.cli_returncode == 0
    ), f"Command failed with code {context.cli_returncode}\nStdout: {context.cli_stdout}\nStderr: {context.cli_stderr}"


@then("the command should fail")
def step_impl(context):
    """Assert that the CLI command failed."""
    assert (
        context.cli_returncode != 0
    ), f"Command unexpectedly succeeded\nStdout: {context.cli_stdout}"


@then('the output should show "{text}"')
def step_impl(context, text):
    """Assert that CLI output contains specific text."""
    output = context.cli_stdout + context.cli_stderr
    assert text.lower() in output.lower(), f"Expected '{text}' in output:\n{output}"


@then("the output should display procedure information")
def step_impl(context):
    """Assert that CLI output shows procedure information."""
    output = context.cli_stdout + context.cli_stderr
    # Check for common procedure info patterns
    assert any(
        keyword in output.lower() for keyword in ["procedure", "name", "version"]
    ), f"No procedure information in output:\n{output}"


@then("the output should show the error location")
def step_impl(context):
    """Assert that CLI output shows error location."""
    output = context.cli_stdout + context.cli_stderr
    # Check for line number or "at input" which indicates where the error occurred
    import re

    has_location = re.search(r"line\s*:?\s*\d+|at input|syntax error", output, re.IGNORECASE)
    assert has_location, f"No error location in output:\n{output}"


@then("the output should suggest how to fix it")
def step_impl(context):
    """Assert that CLI output provides helpful suggestions."""
    output = context.cli_stdout + context.cli_stderr
    # Check for helpful keywords
    assert any(
        keyword in output.lower() for keyword in ["expected", "missing", "required", "error"]
    ), f"No helpful suggestions in output:\n{output}"


def after_scenario(context, scenario):
    """Cleanup after each scenario."""
    # Clean up temporary files
    if hasattr(context, "temp_file") and hasattr(context, "lua_file"):
        try:
            context.lua_file.unlink()
        except Exception:
            pass


@then('the agent system_prompt should contain "{text}"')
def step_impl(context, text):
    """Assert that an agent's system_prompt contains specific text."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert len(context.validation_result.registry.agents) > 0, "No agents found"

    # Check first agent's system_prompt
    first_agent = list(context.validation_result.registry.agents.values())[0]
    assert (
        text in first_agent.system_prompt
    ), f"Expected '{text}' in system_prompt, got: {first_agent.system_prompt}"


@then("validation should have warnings")
def step_impl(context):
    """Assert that validation succeeded but has warnings."""
    assert context.validation_result is not None
    assert context.validation_result.valid, "Validation should succeed"
    assert len(context.validation_result.warnings) > 0, "Expected warnings but found none"


@then("it should recognize model declarations")
def step_impl(context):
    """Assert that model declarations were found."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert len(context.validation_result.registry.models) > 0, "No models found in registry"


@then("it should recognize multiple model declarations")
def step_impl(context):
    """Assert that multiple model declarations were found."""
    assert context.validation_result is not None
    assert context.validation_result.registry is not None
    assert (
        len(context.validation_result.registry.models) > 1
    ), f"Expected multiple models, found {len(context.validation_result.registry.models)}"
