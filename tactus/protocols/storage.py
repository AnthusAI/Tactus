"""
Storage backend protocol for Tactus.

Defines the interface for persisting procedure state, checkpoints, and metadata.
Implementations can use any storage backend (memory, files, databases, etc.).
"""

from typing import Protocol, Optional, Any
from tactus.protocols.models import ProcedureMetadata


class StorageBackend(Protocol):
    """
    Protocol for storage backends.

    Implementations provide persistence for procedure state and checkpoints.
    This allows Tactus to work with any storage system (memory, files, databases, etc.).
    """

    def load_procedure_metadata(self, procedure_id: str) -> ProcedureMetadata:
        """
        Load complete procedure metadata from storage.

        Args:
            procedure_id: Unique procedure identifier

        Returns:
            ProcedureMetadata with all state, checkpoints, and status

        Raises:
            StorageError: If loading fails
        """
        ...

    def save_procedure_metadata(self, metadata: ProcedureMetadata) -> None:
        """
        Save complete procedure metadata to storage.

        Args:
            metadata: ProcedureMetadata to persist

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

    def checkpoint_exists(self, procedure_id: str, name: str) -> bool:
        """
        Check if a checkpoint exists.

        Args:
            procedure_id: Unique procedure identifier
            name: Checkpoint name

        Returns:
            True if checkpoint exists
        """
        ...

    def checkpoint_get(self, procedure_id: str, name: str) -> Optional[Any]:
        """
        Get checkpoint value.

        Args:
            procedure_id: Unique procedure identifier
            name: Checkpoint name

        Returns:
            Checkpoint result value, or None if not found
        """
        ...

    def checkpoint_save(self, procedure_id: str, name: str, result: Any) -> None:
        """
        Save a checkpoint.

        Args:
            procedure_id: Unique procedure identifier
            name: Checkpoint name
            result: Result value to checkpoint

        Raises:
            StorageError: If saving fails
        """
        ...

    def checkpoint_clear_all(self, procedure_id: str) -> None:
        """
        Clear all checkpoints for a procedure.

        Args:
            procedure_id: Unique procedure identifier

        Raises:
            StorageError: If clearing fails
        """
        ...

    def checkpoint_clear_after(self, procedure_id: str, name: str) -> None:
        """
        Clear a checkpoint and all subsequent ones (by timestamp).

        Args:
            procedure_id: Unique procedure identifier
            name: Checkpoint name to clear from

        Raises:
            StorageError: If clearing fails
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
