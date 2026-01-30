from pathlib import Path

import pytest

from tactus.adapters.memory import MemoryStorage
from tactus.core.execution_context import BaseExecutionContext
from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.primitives.procedure import ProcedureHandle
from tactus.protocols.models import CheckpointEntry, SourceLocation


class FakeLogHandler:
    def __init__(self):
        self.events = []

    def log(self, event):
        self.events.append(event)


def test_checkpoint_replay_and_run_id():
    storage = MemoryStorage()
    log_handler = FakeLogHandler()
    ctx = BaseExecutionContext("proc", storage, log_handler=log_handler)
    counter = {"count": 0}

    def fn():
        counter["count"] += 1
        return counter["count"]

    assert ctx.checkpoint(fn, "demo") == 1
    assert counter["count"] == 1
    assert ctx.metadata.replay_index == 1
    assert len(log_handler.events) == 1

    ctx.metadata.replay_index = 0
    assert ctx.checkpoint(fn, "demo") == 1
    assert counter["count"] == 1

    ctx.set_run_id("run-1")
    ctx.metadata.replay_index = 0
    assert ctx.checkpoint(fn, "demo") == 2

    ctx.set_run_id("run-2")
    ctx.metadata.replay_index = 0
    assert ctx.checkpoint(fn, "demo") == 3
    assert counter["count"] == 3


def test_checkpoint_records_source_context(tmp_path: Path):
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    source_file = tmp_path / "test.tac"
    source_file.write_text("line1\nline2\nline3\nline4\n")

    def fn():
        return "ok"

    result = ctx.checkpoint(
        fn,
        "demo",
        source_info={"file": str(source_file), "line": 2, "function": "main"},
    )

    assert result == "ok"
    entry = ctx.metadata.execution_log[0]
    assert isinstance(entry, CheckpointEntry)
    assert entry.source_location is not None
    assert entry.source_location.file == str(source_file)
    assert "line2" in (entry.source_location.code_context or "")


def test_checkpoint_waiting_for_human_records_entry():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    def fn():
        raise ProcedureWaitingForHuman("waiting", "msg-1")

    with pytest.raises(ProcedureWaitingForHuman):
        ctx.checkpoint(fn, "hitl_input")

    assert len(ctx.metadata.execution_log) == 1
    entry = ctx.metadata.execution_log[0]
    assert entry.result is None


def test_checkpoint_hitl_replay_with_missing_result_executes():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.set_run_id("run-1")
    ctx.metadata.execution_log.append(
        CheckpointEntry(
            position=0,
            type="hitl_input",
            result=None,
            timestamp=ctx.get_started_at(),
            duration_ms=0.0,
            run_id=ctx.current_run_id,
            source_location=None,
        )
    )
    ctx.metadata.replay_index = 0
    calls = {"count": 0}

    def fn():
        calls["count"] += 1
        return "ok"

    result = ctx.checkpoint(fn, "hitl_input")

    assert result == "ok"
    assert calls["count"] == 1


def test_checkpoint_updates_existing_hitl_entry_on_wait():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.set_run_id("run-1")
    ctx.metadata.execution_log.append(
        CheckpointEntry(
            position=0,
            type="hitl_input",
            result=None,
            timestamp=ctx.get_started_at(),
            duration_ms=0.0,
            run_id=ctx.current_run_id,
            source_location=None,
        )
    )
    ctx.metadata.replay_index = 0

    def fn():
        raise ProcedureWaitingForHuman("waiting", "msg-1")

    with pytest.raises(ProcedureWaitingForHuman):
        ctx.checkpoint(fn, "hitl_input")

    assert len(ctx.metadata.execution_log) == 1


def test_wait_for_human_defaults_without_handler():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    response = ctx.wait_for_human("input", "Message", 5, "default", None, {})
    assert response.value == "default"
    assert response.timed_out is True


def test_checkpoint_log_handler_error_is_swallowed():
    storage = MemoryStorage()

    class BoomLogHandler:
        def log(self, _event):
            raise RuntimeError("boom")

    ctx = BaseExecutionContext("proc", storage, log_handler=BoomLogHandler())

    assert ctx.checkpoint(lambda: "ok", "demo") == "ok"


def test_checkpoint_clear_methods():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    ctx.checkpoint(lambda: "a", "demo")
    ctx.checkpoint(lambda: "b", "demo")
    assert len(ctx.metadata.execution_log) == 2

    ctx.checkpoint_clear_after(1)
    assert len(ctx.metadata.execution_log) == 1

    ctx.checkpoint_clear_all()
    assert ctx.metadata.execution_log == []
    assert ctx.metadata.replay_index == 0


def test_sleep_uses_checkpoint(monkeypatch):
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    slept = {"called": False}

    def fake_sleep(_seconds):
        slept["called"] = True

    monkeypatch.setattr("time.sleep", fake_sleep)

    ctx.sleep(1)

    assert slept["called"] is True


def test_input_summary_and_prior_hitl():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.set_procedure_metadata(input_data="value")
    assert ctx.get_input_summary() == {"value": "value"}

    ctx.set_procedure_metadata(input_data={"key": "val"})
    assert ctx.get_input_summary() == {"key": "val"}

    ctx.metadata.execution_log.append(
        CheckpointEntry(
            position=0,
            type="hitl_input",
            result="x",
            timestamp=ctx.get_started_at(),
            duration_ms=1.0,
            source_location=SourceLocation(file="file", line=1, function=None, code_context=None),
        )
    )
    interactions = ctx.get_prior_control_interactions()
    assert interactions
    assert interactions[0]["type"] == "hitl_input"


def test_input_summary_none_and_no_prior_interactions():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    assert ctx.get_input_summary() is None
    assert ctx.get_prior_control_interactions() is None


def test_procedure_handles_and_status_updates():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class FakeHandle:
        def __init__(self, procedure_id, status):
            self.procedure_id = procedure_id
            self._status = status

        def to_dict(self):
            return {"procedure_id": self.procedure_id, "status": self._status}

    ctx.store_procedure_handle(FakeHandle("child-1", "running"))
    ctx.store_procedure_handle(FakeHandle("child-2", "waiting"))
    ctx.store_procedure_handle(FakeHandle("child-3", "completed"))

    pending = ctx.list_pending_procedures()
    assert len(pending) == 2

    ctx.update_procedure_status("child-1", "completed", result="ok")
    handle = ctx.get_procedure_handle("child-1")
    assert handle["status"] == "completed"
    assert handle["result"] == "ok"
    assert "completed_at" in handle

    ctx.update_procedure_status("child-2", "failed", error="boom")
    handle = ctx.get_procedure_handle("child-2")
    assert handle["error"] == "boom"


def test_get_subject_and_runtime_context():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.set_procedure_metadata(procedure_name="ProcName")

    ctx.checkpoint(lambda: "a", "demo")

    subject = ctx.get_subject()
    assert "ProcName" in subject
    assert "checkpoint 1" in subject

    runtime = ctx.get_runtime_context()
    assert runtime["procedure_name"] == "ProcName"
    assert runtime["checkpoint_position"] == 1


def test_get_runtime_context_backtrace_with_source_location():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.metadata.execution_log.append(
        CheckpointEntry(
            position=0,
            type="demo",
            result="x",
            timestamp=ctx.get_started_at(),
            duration_ms=1.0,
            source_location=SourceLocation(file="file", line=7, function="fn", code_context=None),
        )
    )

    runtime = ctx.get_runtime_context()
    backtrace = runtime["backtrace"]
    assert backtrace[0]["line"] == 7
    assert backtrace[0]["function_name"] == "fn"
    assert ctx.get_conversation_history() is None


def test_get_subject_without_procedure_name():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    subject = ctx.get_subject()
    assert subject.startswith("proc")


def test_get_subject_includes_procedure_prefix():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc-1", storage)
    ctx.procedure_name = None

    subject = ctx.get_subject()
    assert subject == "Procedure proc-1 (checkpoint 0)"


def test_get_lua_source_line_helpers():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    assert ctx.get_lua_source_line() is None

    class DebugModule:
        def __init__(self):
            self.calls = 0

        def getinfo(self, _level, _opts):
            self.calls += 1
            if self.calls == 3:
                return {"currentline": 12, "source": "main"}
            return {"currentline": 0, "source": "@internal"}

    class DummySandbox:
        def globals(self):
            return type("Globals", (), {"debug": DebugModule()})()

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() == 12


def test_get_lua_source_line_handles_missing_debug():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class DummySandbox:
        def globals(self):
            return type("Globals", (), {"debug": object()})()

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() is None


def test_get_lua_source_line_handles_empty_info():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class DebugModule:
        def getinfo(self, _level, _opts):
            return None

    class DummySandbox:
        def globals(self):
            return type("Globals", (), {"debug": DebugModule()})()

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() is None


def test_get_lua_source_line_skips_internal_sources():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class DebugModule:
        def __init__(self):
            self.calls = 0

        def getinfo(self, _level, _opts):
            self.calls += 1
            return {"currentline": 10, "source": "@internal"}

    class DummySandbox:
        def globals(self):
            return type("Globals", (), {"debug": DebugModule()})()

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() is None


def test_get_lua_source_line_handles_debug_errors():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class DebugModule:
        def getinfo(self, _level, _opts):
            raise RuntimeError("boom")

    class DummySandbox:
        def globals(self):
            return type("Globals", (), {"debug": DebugModule()})()

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() is None


def test_get_lua_source_line_handles_globals_error():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class DummySandbox:
        def globals(self):
            raise RuntimeError("boom")

    ctx.lua_sandbox = DummySandbox()
    assert ctx.get_lua_source_line() is None


def test_get_async_procedures_dict_metadata():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.metadata = {}

    assert ctx._get_async_procedures() == {}


def test_get_async_procedures_no_dict_store():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    class NoDict:
        __slots__ = ()

    ctx.metadata = NoDict()
    assert ctx._get_async_procedures() == {}


def test_update_procedure_status_missing_id_noop():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    ctx.update_procedure_status("missing", "completed")
    assert ctx.get_procedure_handle("missing") is None


def test_update_procedure_status_running_skips_completion_time():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)

    ctx.store_procedure_handle(
        ProcedureHandle(procedure_id="child", name="child", status="running")
    )
    ctx.update_procedure_status("child", "running", result="ok")

    handle = ctx.get_procedure_handle("child")
    assert handle["status"] == "running"
    assert handle["completed_at"] is None


def test_get_runtime_context_without_metadata_backtrace():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx.metadata.execution_log = []

    runtime = ctx.get_runtime_context()
    assert runtime["backtrace"] == []


def test_get_runtime_context_without_started_at():
    storage = MemoryStorage()
    ctx = BaseExecutionContext("proc", storage)
    ctx._started_at = None

    runtime = ctx.get_runtime_context()
    assert runtime["elapsed_seconds"] == 0.0
    assert runtime["started_at"] is None
