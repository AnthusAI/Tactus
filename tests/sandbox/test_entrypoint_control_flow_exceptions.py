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


def test_entrypoint_serializes_waiting_for_time_runtime_result(monkeypatch) -> None:
    captured: list[ExecutionResult] = []
    waiting_result = {
        "success": False,
        "status": "WAITING_FOR_TIME",
        "procedure_id": "procedure-1",
        "request": {
            "key": "retry-publication",
            "resume_at": "2026-08-01T14:30:00Z",
            "reason": "retry transient publication failure",
        },
        "resume_at": "2026-08-01T14:30:00Z",
        "reason": "retry transient publication failure",
        "continuation_key": "retry-publication",
        "message": "Procedure procedure-1 waiting until 2026-08-01T14:30:00Z",
        "session_id": None,
    }

    monkeypatch.setattr(
        sandbox_entrypoint,
        "read_request_from_stdin",
        lambda: {
            "source": "return 1",
            "params": {},
            "execution_id": "test-exec",
            "format": "lua",
            "task_name": None,
        },
    )
    monkeypatch.setattr(
        sandbox_entrypoint,
        "execute_procedure",
        lambda **_kwargs: _return(waiting_result),
    )
    monkeypatch.setattr(
        sandbox_entrypoint,
        "write_result_to_stdout",
        lambda result: captured.append(result),
    )

    exit_code = asyncio.run(sandbox_entrypoint.main_async())

    assert exit_code == 0
    assert captured[-1].status == ExecutionStatus.CANCELLED
    assert captured[-1].error_type == "ProcedureWaitingForTime"
    assert captured[-1].metadata == {
        "waiting_for_time": True,
        "procedure_id": "procedure-1",
        "request": waiting_result["request"],
        "resume_at": "2026-08-01T14:30:00Z",
        "reason": "retry transient publication failure",
        "continuation_key": "retry-publication",
    }


def test_entrypoint_serializes_waiting_for_children_runtime_result(monkeypatch) -> None:
    captured: list[ExecutionResult] = []
    children = [{"id": "child-1", "terminal": False, "status": "running"}]
    waiting_result = {
        "success": False,
        "status": "WAITING_FOR_CHILDREN",
        "procedure_id": "procedure-1",
        "request": {"children": [{"id": "child-1"}], "mode": "all"},
        "children": children,
        "message": "Procedure procedure-1 waiting for external children",
    }

    monkeypatch.setattr(
        sandbox_entrypoint,
        "read_request_from_stdin",
        lambda: {
            "source": "return 1",
            "params": {},
            "execution_id": "test-exec",
            "format": "lua",
            "task_name": None,
        },
    )
    monkeypatch.setattr(
        sandbox_entrypoint,
        "execute_procedure",
        lambda **_kwargs: _return(waiting_result),
    )
    monkeypatch.setattr(
        sandbox_entrypoint,
        "write_result_to_stdout",
        lambda result: captured.append(result),
    )

    assert asyncio.run(sandbox_entrypoint.main_async()) == 0
    assert captured[-1].status == ExecutionStatus.CANCELLED
    assert captured[-1].error_type == "ProcedureWaitingForChildren"
    assert captured[-1].metadata == {
        "waiting_for_children": True,
        "procedure_id": "procedure-1",
        "request": waiting_result["request"],
        "children": children,
    }


async def _return(value):
    return value
