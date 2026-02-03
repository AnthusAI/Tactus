from __future__ import annotations

import io
from pathlib import Path

from rich.console import Console

import tactus.sandbox
from tactus.cli import app as cli_app
from tactus.sandbox.protocol import ExecutionResult, ExecutionStatus


class _FakeRunner:
    def __init__(self, _config, *, result: ExecutionResult):
        self._result = result

    async def run(self, **_kwargs):
        return self._result


def _write_minimal_workflow(path: Path) -> None:
    path.write_text("return 1\n", encoding="utf-8")


def test_cli_run_sandbox_task_selection_required(monkeypatch, tmp_path) -> None:
    workflow_file = tmp_path / "workflow.tac"
    _write_minimal_workflow(workflow_file)

    monkeypatch.setattr(tactus.sandbox, "is_docker_available", lambda: (True, None))
    monkeypatch.setattr(
        cli_app,
        "console",
        Console(file=io.StringIO(), force_terminal=False, color_system=None),
    )

    result = ExecutionResult(
        status=ExecutionStatus.ERROR,
        result=None,
        error="Multiple tasks available; select one explicitly.",
        error_type="TaskSelectionRequired",
        metadata={"tasks": ["index", "run"]},
        exit_code=2,
    )
    monkeypatch.setattr(
        tactus.sandbox, "ContainerRunner", lambda cfg: _FakeRunner(cfg, result=result)
    )

    cli_app.run(
        workflow_file=workflow_file,
        task=None,
        storage="memory",
        storage_path=None,
        openai_api_key=None,
        verbose=False,
        debug=False,
        log_level=None,
        log_format="rich",
        param=None,
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        sandbox=True,
        sandbox_broker="tcp",
        sandbox_network=None,
        sandbox_broker_host=None,
    )


def test_cli_run_sandbox_task_selection_required_empty_task_list(monkeypatch, tmp_path) -> None:
    workflow_file = tmp_path / "workflow.tac"
    _write_minimal_workflow(workflow_file)

    monkeypatch.setattr(tactus.sandbox, "is_docker_available", lambda: (True, None))
    monkeypatch.setattr(
        cli_app,
        "console",
        Console(file=io.StringIO(), force_terminal=False, color_system=None),
    )

    result = ExecutionResult(
        status=ExecutionStatus.ERROR,
        result=None,
        error="Multiple tasks available; select one explicitly.",
        error_type="TaskSelectionRequired",
        metadata={"tasks": []},
        exit_code=2,
    )
    monkeypatch.setattr(
        tactus.sandbox, "ContainerRunner", lambda cfg: _FakeRunner(cfg, result=result)
    )

    cli_app.run(
        workflow_file=workflow_file,
        task=None,
        storage="memory",
        storage_path=None,
        openai_api_key=None,
        verbose=False,
        debug=False,
        log_level=None,
        log_format="rich",
        param=None,
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        sandbox=True,
        sandbox_broker="tcp",
        sandbox_network=None,
        sandbox_broker_host=None,
    )


def test_cli_run_sandbox_waiting_for_human(monkeypatch, tmp_path) -> None:
    workflow_file = tmp_path / "workflow.tac"
    _write_minimal_workflow(workflow_file)

    monkeypatch.setattr(tactus.sandbox, "is_docker_available", lambda: (True, None))
    monkeypatch.setattr(
        cli_app,
        "console",
        Console(file=io.StringIO(), force_terminal=False, color_system=None),
    )

    result = ExecutionResult(
        status=ExecutionStatus.CANCELLED,
        result=None,
        error="waiting",
        error_type="ProcedureWaitingForHuman",
        metadata={"waiting_for_human": True, "pending_message_id": "message-1"},
        exit_code=0,
    )
    monkeypatch.setattr(
        tactus.sandbox, "ContainerRunner", lambda cfg: _FakeRunner(cfg, result=result)
    )

    cli_app.run(
        workflow_file=workflow_file,
        task=None,
        storage="memory",
        storage_path=None,
        openai_api_key=None,
        verbose=False,
        debug=False,
        log_level=None,
        log_format="rich",
        param=None,
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        sandbox=True,
        sandbox_broker="tcp",
        sandbox_network=None,
        sandbox_broker_host=None,
    )


def test_cli_run_sandbox_waiting_for_human_without_message_id(monkeypatch, tmp_path) -> None:
    workflow_file = tmp_path / "workflow.tac"
    _write_minimal_workflow(workflow_file)

    monkeypatch.setattr(tactus.sandbox, "is_docker_available", lambda: (True, None))
    monkeypatch.setattr(
        cli_app,
        "console",
        Console(file=io.StringIO(), force_terminal=False, color_system=None),
    )

    result = ExecutionResult(
        status=ExecutionStatus.CANCELLED,
        result=None,
        error="waiting",
        error_type="ProcedureWaitingForHuman",
        metadata={"waiting_for_human": True},
        exit_code=0,
    )
    monkeypatch.setattr(
        tactus.sandbox, "ContainerRunner", lambda cfg: _FakeRunner(cfg, result=result)
    )

    cli_app.run(
        workflow_file=workflow_file,
        task=None,
        storage="memory",
        storage_path=None,
        openai_api_key=None,
        verbose=False,
        debug=False,
        log_level=None,
        log_format="rich",
        param=None,
        interactive=False,
        mock_all=False,
        real_all=False,
        mock=None,
        real=None,
        sandbox=True,
        sandbox_broker="tcp",
        sandbox_network=None,
        sandbox_broker_host=None,
    )
