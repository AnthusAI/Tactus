"""
In-memory storage backend for Tactus.

Simple implementation that stores all data in memory (RAM).
Useful for testing and simple CLI workflows that don't need persistence.
"""

from typing import Optional, Any, Dict

from tactus.protocols.models import ProcedureMetadata


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

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """Save procedure metadata to memory."""
        self._procedures[procedure_id] = metadata

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
