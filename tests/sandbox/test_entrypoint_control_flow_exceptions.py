from __future__ import annotations

import asyncio

from tactus.core.exceptions import ProcedureWaitingForHuman, TaskSelectionRequired
from tactus.sandbox import entrypoint as sandbox_entrypoint
from tactus.sandbox.protocol import ExecutionResult, ExecutionStatus


def test_entrypoint_serializes_task_selection_required(monkeypatch) -> None:
    captured: list[ExecutionResult] = []

    def fake_read_request_from_stdin():
        return {
            "source": "return 1",
            "params": {},
            "execution_id": "test-exec",
            "format": "lua",
            "task_name": None,
        }

    async def fake_execute_procedure(**_kwargs):
        raise TaskSelectionRequired(["run", "index"])

    def fake_write_result_to_stdout(result: ExecutionResult) -> None:
        captured.append(result)

    monkeypatch.setattr(sandbox_entrypoint, "read_request_from_stdin", fake_read_request_from_stdin)
    monkeypatch.setattr(sandbox_entrypoint, "execute_procedure", fake_execute_procedure)
    monkeypatch.setattr(sandbox_entrypoint, "write_result_to_stdout", fake_write_result_to_stdout)

    exit_code = asyncio.run(sandbox_entrypoint.main_async())
    assert exit_code == 2
    assert captured
    assert captured[-1].status == ExecutionStatus.ERROR
    assert captured[-1].error_type == "TaskSelectionRequired"
    assert captured[-1].exit_code == 2
    assert captured[-1].metadata.get("tasks") == ["run", "index"]


def test_entrypoint_serializes_waiting_for_human(monkeypatch) -> None:
    captured: list[ExecutionResult] = []

    def fake_read_request_from_stdin():
        return {
            "source": "return 1",
            "params": {},
            "execution_id": "test-exec",
            "format": "lua",
            "task_name": None,
        }

    async def fake_execute_procedure(**_kwargs):
        raise ProcedureWaitingForHuman("procedure-1", "message-1")

    def fake_write_result_to_stdout(result: ExecutionResult) -> None:
        captured.append(result)

    monkeypatch.setattr(sandbox_entrypoint, "read_request_from_stdin", fake_read_request_from_stdin)
    monkeypatch.setattr(sandbox_entrypoint, "execute_procedure", fake_execute_procedure)
    monkeypatch.setattr(sandbox_entrypoint, "write_result_to_stdout", fake_write_result_to_stdout)

    exit_code = asyncio.run(sandbox_entrypoint.main_async())
    assert exit_code == 0
    assert captured
    assert captured[-1].status == ExecutionStatus.CANCELLED
    assert captured[-1].error_type == "ProcedureWaitingForHuman"
    assert captured[-1].metadata.get("waiting_for_human") is True
    assert captured[-1].metadata.get("procedure_id") == "procedure-1"
    assert captured[-1].metadata.get("pending_message_id") == "message-1"
