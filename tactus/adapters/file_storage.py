"""
File-based storage backend for Tactus.

Stores procedure metadata and execution log as JSON files on disk.
"""

import json
from pathlib import Path
from typing import Any, Optional
from datetime import datetime

from tactus.protocols.models import (
    ProcedureMetadata,
    CheckpointEntry,
    ExecutionRun,
    Breakpoint,
    SourceLocation,
)


class FileStorage:
    """
    File-based storage backend.

    Stores each procedure's metadata in a separate JSON file:
    {storage_dir}/{procedure_id}.json
    """

    def __init__(self, storage_dir: str = "~/.tactus/storage"):
        """
        Initialize file storage.

        Args:
            storage_dir: Directory to store procedure files
        """
        self.storage_dir = Path(storage_dir).expanduser()

        # Try to create directories, but don't fail if we can't
        # This allows read-only testing and defers errors to write operations
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass  # Defer error to actual write operations

        # Create subdirectories for tracing
        self.traces_dir = self.storage_dir / "traces"
        self.runs_dir = self.traces_dir / "runs"
        self.breakpoints_dir = self.traces_dir / "breakpoints"
        self.index_file = self.traces_dir / "index.json"

        # Try to create subdirectories, but defer errors to write operations
        try:
            self.traces_dir.mkdir(parents=True, exist_ok=True)
            self.runs_dir.mkdir(parents=True, exist_ok=True)
            self.breakpoints_dir.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass  # Defer error to actual write operations

    def _get_file_path(self, procedure_id: str) -> Path:
        """Get the file path for a procedure."""
        return self.storage_dir / f"{procedure_id}.json"

    def _read_file(self, procedure_id: str) -> dict:
        """Read procedure file, return empty dict if not found."""
        file_path = self._get_file_path(procedure_id)
        if not file_path.exists():
            return {}

        try:
            with open(file_path, "r") as file_handle:
                return json.load(file_handle)
        except (json.JSONDecodeError, IOError) as error:
            raise RuntimeError(f"Failed to read procedure file {file_path}: {error}")

    def _write_file(self, procedure_id: str, data: dict) -> None:
        """Write procedure data to file."""
        file_path = self._get_file_path(procedure_id)

        try:
            with open(file_path, "w") as file_handle:
                json.dump(data, file_handle, indent=2, default=str)
        except (IOError, OSError) as error:
            raise RuntimeError(f"Failed to write procedure file {file_path}: {error}")

    def _deserialize_result(self, result: Any) -> Any:
        """Deserialize checkpoint result, reconstructing Pydantic models."""
        if result is None:
            return None
        # Check if result is a serialized Pydantic model
        if isinstance(result, dict) and result.get("__pydantic__"):
            from tactus.protocols.models import HITLResponse

            model_name = result.get("__model__")
            # Remove metadata fields
            data = {k: v for k, v in result.items() if not k.startswith("__")}
            # Reconstruct based on model name
            if model_name == "HITLResponse":
                # Need to parse datetime string back to datetime
                if "responded_at" in data and isinstance(data["responded_at"], str):
                    data["responded_at"] = datetime.fromisoformat(data["responded_at"])
                return HITLResponse(**data)
            # Add other model types as needed
        return result

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """Load procedure metadata from file."""
        data = self._read_file(procedure_id)

        if not data:
            # Create new metadata
            return ProcedureMetadata(procedure_id=procedure_id)

        # Convert stored execution log back to CheckpointEntry objects
        execution_log = []
        for entry_data in data.get("execution_log", []):
            # Rebuild SourceLocation if present
            source_location = None
            if entry_data.get("source_location"):
                source_location = SourceLocation(**entry_data["source_location"])

            execution_log.append(
                CheckpointEntry(
                    position=entry_data["position"],
                    type=entry_data["type"],
                    result=self._deserialize_result(entry_data["result"]),
                    timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                    duration_ms=entry_data.get("duration_ms"),
                    input_hash=entry_data.get("input_hash"),
                    run_id=entry_data["run_id"],
                    source_location=source_location,
                    captured_vars=entry_data.get("captured_vars"),
                )
            )

        return ProcedureMetadata(
            procedure_id=procedure_id,
            execution_log=execution_log,
            replay_index=data.get("replay_index", 0),
            state=data.get("state", {}),
            lua_state=data.get("lua_state", {}),
            status=data.get("status", "RUNNING"),
            waiting_on_message_id=data.get("waiting_on_message_id"),
        )

    def _serialize_result(self, result: Any) -> Any:
        """Serialize checkpoint result, handling Pydantic models."""
        if result is None:
            return None
        # Check if result is a Pydantic model (has model_dump method)
        if hasattr(result, "model_dump"):
            return {
                "__pydantic__": True,
                "__model__": result.__class__.__name__,
                **result.model_dump(),
            }
        return result

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """Save procedure metadata to file."""
        # Convert to serializable dict
        data = {
            "procedure_id": metadata.procedure_id,
            "execution_log": [
                {
                    "position": entry.position,
                    "type": entry.type,
                    "result": self._serialize_result(entry.result),
                    "timestamp": entry.timestamp.isoformat(),
                    "duration_ms": entry.duration_ms,
                    "input_hash": entry.input_hash,
                    "run_id": entry.run_id,
                    "source_location": (
                        entry.source_location.model_dump() if entry.source_location else None
                    ),
                    "captured_vars": entry.captured_vars,
                }
                for entry in metadata.execution_log
            ],
            "replay_index": metadata.replay_index,
            "state": metadata.state,
            "lua_state": metadata.lua_state,
            "status": metadata.status,
            "waiting_on_message_id": metadata.waiting_on_message_id,
        }

        self._write_file(procedure_id, data)

    def update_procedure_status(
        self, procedure_id: str, status: str, waiting_on_message_id: Optional[str] = None
    ) -> None:
        """Update procedure status."""
        procedure_metadata = self.load_procedure_metadata(procedure_id)
        procedure_metadata.status = status
        procedure_metadata.waiting_on_message_id = waiting_on_message_id
        self.save_procedure_metadata(procedure_id, procedure_metadata)

    def get_state(self, procedure_id: str) -> dict[str, Any]:
        """Get mutable state dictionary."""
        procedure_metadata = self.load_procedure_metadata(procedure_id)
        return procedure_metadata.state

    def set_state(self, procedure_id: str, state: dict[str, Any]) -> None:
        """Set mutable state dictionary."""
        procedure_metadata = self.load_procedure_metadata(procedure_id)
        procedure_metadata.state = state
        self.save_procedure_metadata(procedure_id, procedure_metadata)

    # Tracing & Debugging Methods

    def _load_index(self) -> dict[str, Any]:
        """Load the run index."""
        if not self.index_file.exists():
            return {}

        try:
            with open(self.index_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_index(self, index: dict[str, Any]) -> None:
        """Save the run index."""
        try:
            with open(self.index_file, "w") as file_handle:
                json.dump(index, file_handle, indent=2, default=str)
        except (IOError, OSError) as error:
            raise RuntimeError(f"Failed to write index file: {error}")

    def _update_index(self, run: ExecutionRun) -> None:
        """Update index with run metadata."""
        index = self._load_index()

        index[run.run_id] = {
            "procedure_name": run.procedure_name,
            "file_path": run.file_path,
            "start_time": run.start_time.isoformat(),
            "status": run.status,
        }

        self._save_index(index)

    def save_run(self, run: ExecutionRun) -> None:
        """
        Save complete run data.

        Args:
            run: Execution run to save
        """
        run_path = self.runs_dir / f"{run.run_id}.json"

        # Convert to dict with proper serialization
        data = run.model_dump()

        # Convert datetime objects to ISO strings
        if isinstance(data.get("start_time"), datetime):
            data["start_time"] = data["start_time"].isoformat()
        if data.get("end_time") and isinstance(data.get("end_time"), datetime):
            data["end_time"] = data["end_time"].isoformat()

        # Convert checkpoint timestamps
        for checkpoint in data.get("execution_log", []):
            if isinstance(checkpoint.get("timestamp"), datetime):
                checkpoint["timestamp"] = checkpoint["timestamp"].isoformat()

        try:
            with open(run_path, "w") as file_handle:
                json.dump(data, file_handle, indent=2, default=str)
        except (IOError, OSError) as error:
            raise RuntimeError(f"Failed to save run {run.run_id}: {error}")

        # Update index
        self._update_index(run)

    def load_run(self, run_id: str) -> ExecutionRun:
        """
        Load complete run data.

        Args:
            run_id: Run identifier

        Returns:
            Execution run

        Raises:
            FileNotFoundError: If run not found
        """
        run_path = self.runs_dir / f"{run_id}.json"

        if not run_path.exists():
            raise FileNotFoundError(f"Run {run_id} not found")

        try:
            with open(run_path, "r") as file_handle:
                data = json.load(file_handle)
        except (json.JSONDecodeError, IOError) as error:
            raise RuntimeError(f"Failed to load run {run_id}: {error}")

        # Convert timestamps back to datetime objects
        if data.get("start_time"):
            data["start_time"] = datetime.fromisoformat(data["start_time"])
        if data.get("end_time"):
            data["end_time"] = datetime.fromisoformat(data["end_time"])

        # Convert checkpoint timestamps and rebuild CheckpointEntry objects
        execution_log = []
        for checkpoint_data in data.get("execution_log", []):
            if checkpoint_data.get("timestamp"):
                checkpoint_data["timestamp"] = datetime.fromisoformat(checkpoint_data["timestamp"])

            # Rebuild SourceLocation if present
            if checkpoint_data.get("source_location"):
                checkpoint_data["source_location"] = SourceLocation(
                    **checkpoint_data["source_location"]
                )

            execution_log.append(CheckpointEntry(**checkpoint_data))

        data["execution_log"] = execution_log

        # Rebuild Breakpoint objects
        breakpoints = []
        for breakpoint_data in data.get("breakpoints", []):
            breakpoints.append(Breakpoint(**breakpoint_data))

        data["breakpoints"] = breakpoints

        return ExecutionRun(**data)

    def list_runs(self, procedure_name: Optional[str] = None) -> list[ExecutionRun]:
        """
        List all runs, optionally filtered by procedure name.

        Args:
            procedure_name: Optional procedure name filter

        Returns:
            List of execution runs, sorted by start time (newest first)
        """
        index = self._load_index()

        # Filter by procedure name if specified
        if procedure_name:
            run_ids = [
                run_id
                for run_id, info in index.items()
                if info.get("procedure_name") == procedure_name
            ]
        else:
            run_ids = list(index.keys())

        # Load all matching runs
        runs = []
        for run_id in run_ids:
            try:
                runs.append(self.load_run(run_id))
            except (FileNotFoundError, RuntimeError):
                # Skip corrupted or missing runs
                continue

        # Sort by start time (newest first)
        runs.sort(key=lambda r: r.start_time, reverse=True)

        return runs

    def save_breakpoints(self, procedure_name: str, breakpoints: list[Breakpoint]) -> None:
        """
        Save breakpoints for a procedure.

        Args:
            procedure_name: Procedure name
            breakpoints: List of breakpoints
        """
        bp_path = self.breakpoints_dir / f"{procedure_name}.json"

        data = [bp.model_dump() for bp in breakpoints]

        try:
            with open(bp_path, "w") as file_handle:
                json.dump(data, file_handle, indent=2)
        except (IOError, OSError) as error:
            raise RuntimeError(f"Failed to save breakpoints for {procedure_name}: {error}")

    def load_breakpoints(self, procedure_name: str) -> list[Breakpoint]:
        """
        Load breakpoints for a procedure.

        Args:
            procedure_name: Procedure name

        Returns:
            List of breakpoints
        """
        bp_path = self.breakpoints_dir / f"{procedure_name}.json"

        if not bp_path.exists():
            return []

        try:
            with open(bp_path, "r") as file_handle:
                data = json.load(file_handle)
        except (json.JSONDecodeError, IOError):
            return []

        return [Breakpoint(**bp_data) for bp_data in data]
