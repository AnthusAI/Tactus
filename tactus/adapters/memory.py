"""
In-memory storage backend for Tactus.

Simple implementation that stores all data in memory (RAM).
Useful for testing and simple CLI workflows that don't need persistence.
"""

from typing import Optional, Any, Dict
from datetime import datetime, timezone

from tactus.protocols.models import ProcedureMetadata, CheckpointData


class MemoryStorage:
    """
    In-memory storage backend.

    All data stored in Python dicts - lost when process exits.
    """

    def __init__(self):
        """Initialize in-memory storage."""
        self._procedures: Dict[str, ProcedureMetadata] = {}

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """Load procedure metadata from memory."""
        if procedure_id not in self._procedures:
            # Create new metadata if doesn't exist
            self._procedures[procedure_id] = ProcedureMetadata(procedure_id=procedure_id)
        return self._procedures[procedure_id]

    def save_procedure_metadata(self, metadata: ProcedureMetadata) -> None:
        """Save procedure metadata to memory."""
        self._procedures[metadata.procedure_id] = metadata

    def update_procedure_status(
        self, procedure_id: str, status: str, waiting_on_message_id: Optional[str] = None
    ) -> None:
        """Update procedure status."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.status = status
        metadata.waiting_on_message_id = waiting_on_message_id
        self.save_procedure_metadata(metadata)

    def checkpoint_exists(self, procedure_id: str, name: str) -> bool:
        """Check if checkpoint exists."""
        metadata = self.load_procedure_metadata(procedure_id)
        return name in metadata.checkpoints

    def checkpoint_get(self, procedure_id: str, name: str) -> Optional[Any]:
        """Get checkpoint value."""
        metadata = self.load_procedure_metadata(procedure_id)
        checkpoint = metadata.checkpoints.get(name)
        return checkpoint.result if checkpoint else None

    def checkpoint_save(self, procedure_id: str, name: str, result: Any) -> None:
        """Save a checkpoint."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints[name] = CheckpointData(
            name=name, result=result, completed_at=datetime.now(timezone.utc)
        )
        self.save_procedure_metadata(metadata)

    def checkpoint_clear_all(self, procedure_id: str) -> None:
        """Clear all checkpoints (but preserve state)."""
        metadata = self.load_procedure_metadata(procedure_id)
        metadata.checkpoints.clear()
        # Note: state is NOT cleared - only checkpoints
        self.save_procedure_metadata(metadata)

    def checkpoint_clear_after(self, procedure_id: str, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        metadata = self.load_procedure_metadata(procedure_id)

        if name not in metadata.checkpoints:
            return

        target_time = metadata.checkpoints[name].completed_at

        # Keep only checkpoints older than target
        metadata.checkpoints = {
            k: v for k, v in metadata.checkpoints.items() if v.completed_at < target_time
        }
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
