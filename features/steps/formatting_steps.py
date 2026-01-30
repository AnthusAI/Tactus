"""
Step definitions for formatting feature.
"""

import subprocess
import tempfile
from pathlib import Path

from behave import given, then, when


@given("a formatting environment")
def step_impl(context):
    context.last_cli = None
    context.last_formatted_content = None


@given("a Lua DSL file with formatting issues")
def step_impl(context):
    # Intentionally inconsistent indentation (tabs + wrong nesting).
    context.lua_content = """-- formatting test

Procedure {
\toutput = {
\tgreeting=field.string{required=true},
\tcompleted=field.boolean{required=true},
\t},
\tfunction(input)
\tif 1<2 and 3>4 then
\treturn {greeting="hi",completed=true}
\tend
\tend
}
"""

    context.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    context.temp_file.write(context.lua_content)
    context.temp_file.close()
    context.lua_file = Path(context.temp_file.name)
    context.expected_formatted = """-- formatting test

Procedure {
  output = {
    greeting = field.string{required = true},
    completed = field.boolean{required = true}
  },
  function(input)
    if 1 < 2 and 3 > 4 then
      return {greeting = "hi", completed = true}
    end
  end
}
"""


@given("a Lua DSL file with Specifications content needing indentation")
def step_impl(context):
    context.lua_content = """Specifications([[
Feature: Simple State Management
  Test basic state and stage functionality without agents
]])\n"""

    context.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".tac", delete=False)
    context.temp_file.write(context.lua_content)
    context.temp_file.close()
    context.lua_file = Path(context.temp_file.name)

    context.expected_specifications_formatted = """Specifications([[
  Feature: Simple State Management
    Test basic state and stage functionality without agents
]])\n"""


@given("a non-Lua file")
def step_impl(context):
    context.lua_content = "not lua"
    context.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    context.temp_file.write(context.lua_content)
    context.temp_file.close()
    context.lua_file = Path(context.temp_file.name)


@given("a missing Lua file path")
def step_impl(context):
    temp_dir = tempfile.TemporaryDirectory(prefix="tactus_missing_")
    context.temp_dir_obj = temp_dir
    context.lua_file = Path(temp_dir.name) / "missing.tac"


@when('I run "tactus format" on the file')
def step_impl(context):
    import sys

    before = None
    if context.lua_file.exists():
        before = context.lua_file.read_text()
    result = subprocess.run(
        [sys.executable, "-m", "tactus.cli.app", "format", str(context.lua_file)],
        capture_output=True,
        text=True,
    )
    after = None
    if context.lua_file.exists():
        after = context.lua_file.read_text()

    context.last_cli = result
    context.last_formatted_content = after
    context._before_after = (before, after)
    context.cli_returncode = result.returncode
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr


@when('I run "tactus format --check" on the file')
def step_impl(context):
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactus.cli.app",
            "format",
            "--check",
            str(context.lua_file),
        ],
        capture_output=True,
        text=True,
    )
    context.last_cli = result
    context.cli_returncode = result.returncode
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr


@when('I run "tactus format --stdout" on the file')
def step_impl(context):
    import sys

    before = None
    if context.lua_file.exists():
        before = context.lua_file.read_text()
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tactus.cli.app",
            "format",
            "--stdout",
            str(context.lua_file),
        ],
        capture_output=True,
        text=True,
    )
    after = None
    if context.lua_file.exists():
        after = context.lua_file.read_text()

    context.last_cli = result
    context.cli_returncode = result.returncode
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr
    context._before_after = (before, after)


@then("the format command should succeed")
def step_impl(context):
    assert context.last_cli is not None, "No command was run"
    assert (
        context.last_cli.returncode == 0
    ), f"Command failed: {context.last_cli.returncode}\nSTDOUT:\n{context.last_cli.stdout}\nSTDERR:\n{context.last_cli.stderr}"


@then("the format command should fail")
def step_impl(context):
    assert context.last_cli is not None, "No command was run"
    assert context.last_cli.returncode != 0, "Command unexpectedly succeeded"


@then("the file should be formatted with 2-space indentation")
def step_impl(context):
    content = context.lua_file.read_text().splitlines()
    # Ensure no tabs remain at line starts and indentation uses multiples of 2.
    for line in content:
        stripped = line.lstrip(" \t")
        if stripped == "":
            continue
        leading = line[: len(line) - len(stripped)]
        assert "\t" not in leading, f"Found tab indentation: {line!r}"
        assert len(leading) % 2 == 0, f"Indentation is not a multiple of 2 spaces: {line!r}"

    assert (
        context.lua_file.read_text() == context.expected_formatted
    ), "Formatted output did not match expected canonical indentation"


@then("the file should be unchanged by the second run")
def step_impl(context):
    before, after = context._before_after
    assert (
        before == after
    ), "Second formatting run changed file content (formatter is not idempotent)"


@then("the Specifications content should be indented by 2 spaces")
def step_impl(context):
    assert (
        context.lua_file.read_text() == context.expected_specifications_formatted
    ), "Specifications content did not match expected indentation"


@then("the formatted output should be printed")
def step_impl(context):
    assert context.cli_stdout == context.expected_formatted, (
        "Formatted output did not match expected output\n"
        f"STDOUT:\n{context.cli_stdout}\n"
        f"EXPECTED:\n{context.expected_formatted}"
    )


@then("the file should be unchanged by the format output")
def step_impl(context):
    before, after = context._before_after
    assert before == after, "Formatting with --stdout modified the file"
