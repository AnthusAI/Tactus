"""
Storage backend protocol for Tactus.

Defines the interface for persisting procedure state, execution log, and metadata.
Implementations can use any storage backend (memory, files, databases, etc.).
"""

from typing import Protocol, Optional, Any
from tactus.protocols.models import ProcedureMetadata


class StorageBackend(Protocol):
    """
    Protocol for storage backends.

    Implementations provide persistence for procedure state and execution log.
    This allows Tactus to work with any storage system (memory, files, databases, etc.).

    Position-based checkpointing: All checkpoints are stored in ProcedureMetadata.execution_log
    as an ordered list. No named checkpoint methods needed.
    """

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """
        Load complete procedure metadata from storage.

        Args:
            procedure_id: Unique procedure identifier

        Returns:
            ProcedureMetadata with execution_log, state, replay_index, and status

        Raises:
            StorageError: If loading fails
        """
        ...

    def save_procedure_metadata(self, procedure_id: str, metadata: ProcedureMetadata) -> None:
        """
        Save complete procedure metadata to storage.

        Args:
            procedure_id: Unique procedure identifier
            metadata: ProcedureMetadata to persist (includes execution_log)

        Raises:
            StorageError: If saving fails
        """
        ...

    def update_procedure_status(
        self, procedure_id: str, status: str, waiting_on_message_id: Optional[str] = None
    ) -> None:
        """
        Update procedure status (and optionally waiting message ID).

        Args:
            procedure_id: Unique procedure identifier
            status: New status (RUNNING, WAITING_FOR_HUMAN, COMPLETED, FAILED)
            waiting_on_message_id: Optional message ID if waiting for human

        Raises:
            StorageError: If update fails
        """
        ...

    def get_state(self, procedure_id: str) -> dict[str, Any]:
        """
        Get mutable state dictionary.

        Args:
            procedure_id: Unique procedure identifier

        Returns:
            State dictionary
        """
        ...

    def set_state(self, procedure_id: str, state: dict[str, Any]) -> None:
        """
        Set mutable state dictionary.

        Args:
            procedure_id: Unique procedure identifier
            state: State dictionary to save

        Raises:
            StorageError: If saving fails
        """
        ...
