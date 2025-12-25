"""
File-based storage backend for Tactus.

Stores procedure metadata and execution log as JSON files on disk.
"""

import json
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime

from tactus.protocols.models import ProcedureMetadata, CheckpointEntry


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
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, procedure_id: str) -> Path:
        """Get the file path for a procedure."""
        return self.storage_dir / f"{procedure_id}.json"

    def _read_file(self, procedure_id: str) -> dict:
        """Read procedure file, return empty dict if not found."""
        file_path = self._get_file_path(procedure_id)
        if not file_path.exists():
            return {}

        try:
            with open(file_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            raise RuntimeError(f"Failed to read procedure file {file_path}: {e}")

    def _write_file(self, procedure_id: str, data: dict) -> None:
        """Write procedure data to file."""
        file_path = self._get_file_path(procedure_id)

        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except (IOError, OSError) as e:
            raise RuntimeError(f"Failed to write procedure file {file_path}: {e}")

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """Load procedure metadata from file."""
        data = self._read_file(procedure_id)

        if not data:
            # Create new metadata
            return ProcedureMetadata(procedure_id=procedure_id)

        # Convert stored execution log back to CheckpointEntry objects
        execution_log = []
        for entry_data in data.get("execution_log", []):
            execution_log.append(
                CheckpointEntry(
                    position=entry_data["position"],
                    type=entry_data["type"],
                    result=entry_data["result"],
                    timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                    duration_ms=entry_data.get("duration_ms"),
                    input_hash=entry_data.get("input_hash"),
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

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """Save procedure metadata to file."""
        # Convert to serializable dict
        data = {
            "procedure_id": metadata.procedure_id,
            "execution_log": [
                {
                    "position": entry.position,
                    "type": entry.type,
                    "result": entry.result,
                    "timestamp": entry.timestamp.isoformat(),
                    "duration_ms": entry.duration_ms,
                    "input_hash": entry.input_hash,
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
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.status = status
        metadata.waiting_on_message_id = waiting_on_message_id
        self.save_procedure_metadata(procedure_id, metadata)

    def get_state(self, procedure_id: str) -> Dict[str, Any]:
        """Get mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state

    def set_state(self, procedure_id: str, state: Dict[str, Any]) -> None:
        """Set mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = state
        self.save_procedure_metadata(procedure_id, metadata)
