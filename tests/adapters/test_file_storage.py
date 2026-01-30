from __future__ import annotations

import builtins
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from tactus.adapters.file_storage import FileStorage
from tactus.protocols.models import (
    HITLResponse,
    ProcedureMetadata,
    ExecutionRun,
    CheckpointEntry,
    SourceLocation,
    Breakpoint,
)


def test_init_ignores_permission_errors(monkeypatch, tmp_path):
    calls = {"count": 0}

    def boom(*_args, **_kwargs):
        calls["count"] += 1
        raise PermissionError("nope")

    monkeypatch.setattr("pathlib.Path.mkdir", boom)

    storage = FileStorage(str(tmp_path / "storage"))

    assert storage.storage_dir.name == "storage"
    assert calls["count"] >= 1


def test_read_file_invalid_json_raises(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    path = storage._get_file_path("proc")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json")

    with pytest.raises(RuntimeError, match="Failed to read procedure file"):
        storage._read_file("proc")


def test_write_file_error_raises(monkeypatch, tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))

    def boom(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(builtins, "open", boom)

    with pytest.raises(RuntimeError, match="Failed to write procedure file"):
        storage._write_file("proc", {"ok": True})


def test_serialize_and_deserialize_hitl_response(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    responded_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    response = HITLResponse(value="ok", responded_at=responded_at)

    serialized = storage._serialize_result(response)
    assert serialized["__pydantic__"] is True

    deserialized = storage._deserialize_result(serialized)
    assert isinstance(deserialized, HITLResponse)
    assert deserialized.responded_at == responded_at


def test_deserialize_hitl_response_parses_responded_at_string(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    responded_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
    serialized = {
        "__pydantic__": True,
        "__model__": "HITLResponse",
        "value": "ok",
        "responded_at": responded_at.isoformat(),
    }

    deserialized = storage._deserialize_result(serialized)
    assert isinstance(deserialized, HITLResponse)
    assert deserialized.responded_at == responded_at


def test_deserialize_unknown_pydantic_payload_returns_original(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    payload = {"__pydantic__": True, "__model__": "OtherModel", "value": "x"}

    assert storage._deserialize_result(payload) == payload


def test_serialize_and_deserialize_none(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    assert storage._serialize_result(None) is None
    assert storage._deserialize_result(None) is None


def test_update_procedure_status_round_trips(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    metadata = ProcedureMetadata(procedure_id="proc")
    storage.save_procedure_metadata("proc", metadata)

    storage.update_procedure_status("proc", "WAITING", waiting_on_message_id="msg-1")

    loaded = storage.load_procedure_metadata("proc")
    assert loaded.status == "WAITING"
    assert loaded.waiting_on_message_id == "msg-1"


def test_load_index_invalid_json_returns_empty(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    storage.index_file.parent.mkdir(parents=True, exist_ok=True)
    storage.index_file.write_text("{bad json")

    assert storage._load_index() == {}


def test_save_index_error_raises(monkeypatch, tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))

    def boom(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(builtins, "open", boom)

    with pytest.raises(RuntimeError, match="Failed to write index file"):
        storage._save_index({"run": {}})


def test_save_run_error_raises(monkeypatch, tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    run = ExecutionRun(
        run_id="run-1",
        procedure_name="proc",
        file_path="x.tac",
        start_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
        status="done",
        execution_log=[],
        breakpoints=[],
    )

    def boom(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(builtins, "open", boom)

    with pytest.raises(RuntimeError, match="Failed to save run run-1"):
        storage.save_run(run)


def test_save_run_converts_datetime_fields(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
    checkpoint_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)

    class FakeRun:
        def __init__(self):
            self.run_id = "run-2"
            self.procedure_name = "proc"
            self.file_path = "proc.tac"
            self.status = "done"
            self.start_time = start_time
            self.end_time = end_time

        def model_dump(self):
            return {
                "run_id": "run-2",
                "procedure_name": "proc",
                "file_path": "proc.tac",
                "start_time": start_time,
                "end_time": end_time,
                "status": "done",
                "execution_log": [{"timestamp": checkpoint_time}],
                "breakpoints": [],
            }

    storage.save_run(FakeRun())
    saved = json.loads((storage.runs_dir / "run-2.json").read_text())

    assert saved["start_time"] == start_time.isoformat()
    assert saved["end_time"] == end_time.isoformat()
    assert saved["execution_log"][0]["timestamp"] == checkpoint_time.isoformat()


def test_save_run_skips_datetime_conversion_when_not_datetime(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))

    class FakeRun:
        def __init__(self):
            self.run_id = "run-4"
            self.procedure_name = "proc"
            self.file_path = "proc.tac"
            self.status = "done"
            self.start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
            self.end_time = None

        def model_dump(self):
            return {
                "run_id": "run-4",
                "procedure_name": "proc",
                "file_path": "proc.tac",
                "start_time": "already-string",
                "end_time": None,
                "status": "done",
                "execution_log": [{"timestamp": "already-string"}],
                "breakpoints": [],
            }

    storage.save_run(FakeRun())
    saved = json.loads((storage.runs_dir / "run-4.json").read_text())

    assert saved["start_time"] == "already-string"
    assert saved["execution_log"][0]["timestamp"] == "already-string"


def test_load_run_missing_raises(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))

    with pytest.raises(FileNotFoundError, match="Run missing not found"):
        storage.load_run("missing")


def test_load_run_invalid_json_raises(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    run_path = storage.runs_dir / "run.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text("{bad json")

    with pytest.raises(RuntimeError, match="Failed to load run run"):
        storage.load_run("run")


def test_load_run_parses_timestamps_and_source_location(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    run_path = storage.runs_dir / "run-3.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
    checkpoint_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    run_path.write_text(
        json.dumps(
            {
                "run_id": "run-3",
                "procedure_name": "proc",
                "file_path": "proc.tac",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "status": "done",
                "execution_log": [
                    {
                        "position": 1,
                        "type": "checkpoint",
                        "result": {"ok": True},
                        "timestamp": checkpoint_time.isoformat(),
                        "run_id": "run-3",
                        "source_location": {"file": "proc.tac", "line": 5},
                    }
                ],
                "breakpoints": [],
            }
        )
    )

    loaded = storage.load_run("run-3")

    assert loaded.start_time == start_time
    assert loaded.end_time == end_time
    assert loaded.execution_log[0].timestamp == checkpoint_time
    assert loaded.execution_log[0].source_location.file == "proc.tac"


def test_load_run_missing_start_time_raises(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    run_path = storage.runs_dir / "run-5.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps(
            {
                "run_id": "run-5",
                "procedure_name": "proc",
                "file_path": "proc.tac",
                "start_time": "",
                "status": "done",
                "execution_log": [
                    {
                        "position": 1,
                        "type": "checkpoint",
                        "result": {"ok": True},
                        "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "run_id": "run-5",
                    }
                ],
                "breakpoints": [],
            }
        )
    )

    with pytest.raises(ValidationError):
        storage.load_run("run-5")


def test_load_run_missing_checkpoint_timestamp_raises(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    run_path = storage.runs_dir / "run-6.json"
    run_path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps(
            {
                "run_id": "run-6",
                "procedure_name": "proc",
                "file_path": "proc.tac",
                "status": "done",
                "execution_log": [
                    {
                        "position": 1,
                        "type": "checkpoint",
                        "result": {"ok": True},
                        "run_id": "run-6",
                    }
                ],
                "breakpoints": [],
            }
        )
    )

    with pytest.raises(ValidationError):
        storage.load_run("run-6")


def test_save_and_load_run_with_timestamps_and_breakpoints(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2024, 1, 2, tzinfo=timezone.utc)
    checkpoint_time = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    source_location = SourceLocation(file="proc.tac", line=10, function="main")
    checkpoint = CheckpointEntry(
        position=0,
        type="explicit_checkpoint",
        result={"ok": True},
        timestamp=checkpoint_time,
        run_id="run-1",
        source_location=source_location,
    )
    breakpoint = Breakpoint(
        breakpoint_id="bp-1",
        file="proc.tac",
        line=12,
        condition="x == 1",
        enabled=True,
        hit_count=2,
    )

    run = ExecutionRun(
        run_id="run-1",
        procedure_name="proc",
        file_path="proc.tac",
        start_time=start_time,
        end_time=end_time,
        status="done",
        execution_log=[checkpoint],
        breakpoints=[breakpoint],
    )

    storage.save_run(run)
    loaded = storage.load_run("run-1")

    assert loaded.start_time == start_time
    assert loaded.end_time == end_time
    assert loaded.execution_log[0].timestamp == checkpoint_time
    assert loaded.execution_log[0].source_location.file == "proc.tac"
    assert loaded.breakpoints[0].breakpoint_id == "bp-1"


def test_list_runs_skips_corrupt_entries(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    storage.index_file.parent.mkdir(parents=True, exist_ok=True)
    storage.index_file.write_text(json.dumps({"missing": {"procedure_name": "proc"}}))

    assert storage.list_runs("proc") == []


def test_save_breakpoints_error_raises(monkeypatch, tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))

    def boom(*_args, **_kwargs):
        raise OSError("nope")

    monkeypatch.setattr(builtins, "open", boom)

    with pytest.raises(RuntimeError, match="Failed to save breakpoints"):
        storage.save_breakpoints("proc", [])


def test_load_breakpoints_invalid_json_returns_empty(tmp_path):
    storage = FileStorage(str(tmp_path / "storage"))
    path = storage.breakpoints_dir / "proc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{bad json")

    assert storage.load_breakpoints("proc") == []
