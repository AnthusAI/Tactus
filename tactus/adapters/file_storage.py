"""
File-based storage backend for Tactus.

Stores procedure metadata and checkpoints as JSON files on disk.
"""

import json
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime

from tactus.protocols.models import ProcedureMetadata, CheckpointData


class FileStorage:
    """
    File-based storage backend.

    Stores each procedure's metadata in a separate JSON file:
    {storage_dir}/{procedure_id}.json
    """

    def __init__(self, storage_dir: str = "~/.tac/storage"):
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

        # Convert stored checkpoint data back to CheckpointData objects
        checkpoints = {}
        for name, ckpt_data in data.get("checkpoints", {}).items():
            checkpoints[name] = CheckpointData(
                name=name,
                result=ckpt_data["result"],
                completed_at=datetime.fromisoformat(ckpt_data["completed_at"]),
            )

        return ProcedureMetadata(
            procedure_id=procedure_id,
            checkpoints=checkpoints,
            state=data.get("state", {}),
            status=data.get("status", "RUNNING"),
            waiting_on_message_id=data.get("waiting_on_message_id"),
        )

    def save_procedure_metadata(self, metadata: ProcedureMetadata) -> None:
        """Save procedure metadata to file."""
        # Convert to serializable dict
        data = {
            "procedure_id": metadata.procedure_id,
            "checkpoints": {
                name: {
                    "name": ckpt.name,
                    "result": ckpt.result,
                    "completed_at": ckpt.completed_at.isoformat(),
                }
                for name, ckpt in metadata.checkpoints.items()
            },
            "state": metadata.state,
            "status": metadata.status,
            "waiting_on_message_id": metadata.waiting_on_message_id,
        }

        self._write_file(metadata.procedure_id, data)

    def checkpoint_save(self, procedure_id: str, name: str, result: Any) -> None:
        """Save a checkpoint."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints[name] = CheckpointData(
            name=name, result=result, completed_at=datetime.now()
        )
        self.save_procedure_metadata(metadata)

    def checkpoint_get(self, procedure_id: str, name: str) -> Optional[Any]:
        """Get checkpoint result."""
        metadata = self.load_procedure_metadata(procedure_id)
        checkpoint = metadata.checkpoints.get(name)
        return checkpoint.result if checkpoint else None

    def checkpoint_exists(self, procedure_id: str, name: str) -> bool:
        """Check if checkpoint exists."""
        metadata = self.load_procedure_metadata(procedure_id)
        return name in metadata.checkpoints

    def checkpoint_clear_all(self, procedure_id: str) -> None:
        """Clear all checkpoints."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints = {}
        self.save_procedure_metadata(metadata)

    def checkpoint_clear_after(self, procedure_id: str, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        # For file storage, we don't have ordering info
        # Just clear the named checkpoint
        metadata = self.load_procedure_metadata(procedure_id)
        if name in metadata.checkpoints:
            del metadata.checkpoints[name]
            self.save_procedure_metadata(metadata)

    def state_get(self, procedure_id: str, key: str, default: Any = None) -> Any:
        """Get state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state.get(key, default)

    def state_set(self, procedure_id: str, key: str, value: Any) -> None:
        """Set state value."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state[key] = value
        self.save_procedure_metadata(metadata)

    def state_delete(self, procedure_id: str, key: str) -> None:
        """Delete state key."""
        metadata = self.load_procedure_metadata(procedure_id)
        if key in metadata.state:
            del metadata.state[key]
            self.save_procedure_metadata(metadata)

    def state_clear(self, procedure_id: str) -> None:
        """Clear all state."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = {}
        self.save_procedure_metadata(metadata)

    def get_status(self, procedure_id: str) -> str:
        """Get procedure status."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.status

    def set_status(self, procedure_id: str, status: str) -> None:
        """Set procedure status."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.status = status
        self.save_procedure_metadata(metadata)

    def set_waiting_on_message(self, procedure_id: str, message_id: Optional[str]) -> None:
        """Set waiting on message ID."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.waiting_on_message_id = message_id
        self.save_procedure_metadata(metadata)

    def get_waiting_on_message(self, procedure_id: str) -> Optional[str]:
        """Get waiting on message ID."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.waiting_on_message_id

    def update_procedure_status(
        self, procedure_id: str, status: str, waiting_on_message_id: Optional[str] = None
    ) -> None:
        """Update procedure status."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.status = status
        metadata.waiting_on_message_id = waiting_on_message_id
        self.save_procedure_metadata(metadata)

    def get_state(self, procedure_id: str) -> Dict[str, Any]:
        """Get mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        return metadata.state

    def set_state(self, procedure_id: str, state: Dict[str, Any]) -> None:
        """Set mutable state dictionary."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.state = state
        self.save_procedure_metadata(metadata)
