from __future__ import annotations

import io

from rich.console import Console

from tactus.cli import app as cli_app


def test_print_available_tasks_includes_default_example() -> None:
    console = Console(file=io.StringIO(), force_terminal=False, color_system=None)

    cli_app._print_available_tasks(
        console,
        workflow_filename="workflow.tac",
        tasks=[],
        show_example_when_empty=True,
    )
