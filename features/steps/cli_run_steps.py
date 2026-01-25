"""
Step definitions for running the CLI with `tactus run`.
"""

import shlex
import subprocess
import sys
from behave import when


@when('I run "tactus run {args}" on the file')
def step_run_tactus_on_file(context, args):
    """Run tactus CLI on the current file."""
    command = shlex.split(f"tactus run {args}")
    if len(command) < 2 or command[0] != "tactus" or command[1] != "run":
        raise AssertionError(f"Unexpected command format: {command}")

    workflow_path = None
    if hasattr(context, "lua_file"):
        workflow_path = str(context.lua_file)
    elif hasattr(context, "workflow_file"):
        workflow_path = str(context.workflow_file)

    if not workflow_path:
        raise AssertionError("No workflow file available for CLI run")

    cli_args = command[1:]
    if workflow_path not in cli_args:
        cli_args.insert(1, workflow_path)

    result = subprocess.run(
        [sys.executable, "-m", "tactus.cli.app", *cli_args],
        capture_output=True,
        text=True,
    )
    context.cli_returncode = result.returncode
    context.cli_stdout = result.stdout
    context.cli_stderr = result.stderr
