"""
Step definitions for running `tactus info`.
"""

import subprocess
import sys
from behave import when


@when('I run "tactus info" on the file')
def step_run_tactus_info(context):
    """Run tactus info on the current Lua DSL file."""
    workflow_path = None
    if hasattr(context, "lua_file"):
        workflow_path = str(context.lua_file)
    elif hasattr(context, "workflow_file"):
        workflow_path = str(context.workflow_file)

    if not workflow_path:
        raise AssertionError("No workflow file available for CLI info")

    result = subprocess.run(
        [sys.executable, "-m", "tactus.cli.app", "info", workflow_path],
        capture_output=True,
        text=True,
    )
    context.cli_returncode = result.returncode
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr
