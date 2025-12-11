"""
Execution context abstraction for Tactus runtime.

Provides execution backend support with checkpointing and HITL capabilities.
Uses pluggable storage and HITL handlers via protocols.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, List
from datetime import datetime, timezone

from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.models import HITLRequest, HITLResponse


class ExecutionContext(ABC):
    """
    Abstract execution context for procedure workflows.

    Provides checkpointing and HITL capabilities. Implementations
    determine how to persist state and handle human interactions.
    """

    @abstractmethod
    def step_run(self, name: str, fn: Callable[[], Any]) -> Any:
        """
        Execute fn with checkpointing. On replay, return stored result.

        Args:
            name: Unique checkpoint name
            fn: Function to execute (should be deterministic)

        Returns:
            Result of fn() on first execution, cached result on replay
        """
        pass

    @abstractmethod
    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
        metadata: dict,
    ) -> HITLResponse:
        """
        Suspend until human responds.

        Args:
            request_type: 'approval', 'input', 'review', or 'escalation'
            message: Message to display to human
            timeout_seconds: Timeout in seconds, None = wait forever
            default_value: Value to return on timeout
            options: For review requests: [{label, type}, ...]
            metadata: Additional context data

        Returns:
            HITLResponse with value and timestamp

        Raises:
            ProcedureWaitingForHuman: May exit to wait for resume
        """
        pass

    @abstractmethod
    def sleep(self, seconds: int) -> None:
        """
        Sleep without consuming resources.

        Different contexts may implement this differently.
        """
        pass

    @abstractmethod
    def checkpoint_clear_all(self) -> None:
        """Clear all checkpoints. Used for testing."""
        pass

    @abstractmethod
    def checkpoint_clear_after(self, name: str) -> None:
        """Clear checkpoint and all subsequent ones. Used for testing."""
        pass

    @abstractmethod
    def checkpoint_exists(self, name: str) -> bool:
        """Check if checkpoint exists."""
        pass

    @abstractmethod
    def checkpoint_get(self, name: str) -> Optional[Any]:
        """Get cached checkpoint value, or None if not found."""
        pass


class BaseExecutionContext(ExecutionContext):
    """
    Base execution context using pluggable storage and HITL handlers.

    This implementation works with any StorageBackend and HITLHandler,
    making it suitable for various deployment scenarios (CLI, web, API, etc.).
    """

    def __init__(
        self,
        procedure_id: str,
        storage_backend: StorageBackend,
        hitl_handler: Optional[HITLHandler] = None,
    ):
        """
        Initialize base execution context.

        Args:
            procedure_id: ID of the running procedure
            storage_backend: Storage backend for checkpoints and state
            hitl_handler: Optional HITL handler for human interactions
        """
        self.procedure_id = procedure_id
        self.storage = storage_backend
        self.hitl = hitl_handler

        # Load procedure metadata
        self.metadata = self.storage.load_procedure_metadata(procedure_id)

    def step_run(self, name: str, fn: Callable[[], Any]) -> Any:
        """Execute with checkpoint replay."""
        if self.storage.checkpoint_exists(self.procedure_id, name):
            # Replay: return cached result
            return self.storage.checkpoint_get(self.procedure_id, name)

        # Execute and cache
        result = fn()
        self.storage.checkpoint_save(self.procedure_id, name, result)
        return result

    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
        metadata: dict,
    ) -> HITLResponse:
        """
        Wait for human response using the configured HITL handler.

        Delegates to the HITLHandler protocol implementation.
        """
        if not self.hitl:
            # No HITL handler - return default immediately
            return HITLResponse(
                value=default_value, responded_at=datetime.now(timezone.utc), timed_out=True
            )

        # Create HITL request
        request = HITLRequest(
            request_type=request_type,
            message=message,
            timeout_seconds=timeout_seconds,
            default_value=default_value,
            options=options,
            metadata=metadata,
        )

        # Delegate to HITL handler (may raise ProcedureWaitingForHuman)
        return self.hitl.request_interaction(self.procedure_id, request)

    def sleep(self, seconds: int) -> None:
        """
        Sleep by creating a checkpoint.

        Note: This is a simple implementation. Production systems
        may want scheduled resume mechanisms.
        """
        import time

        checkpoint_name = f"sleep_{datetime.now(timezone.utc).isoformat()}"

        # Check if we already slept
        if not self.storage.checkpoint_exists(self.procedure_id, checkpoint_name):
            # First time - actually sleep
            time.sleep(seconds)
            # Save checkpoint
            self.storage.checkpoint_save(self.procedure_id, checkpoint_name, None)

    def checkpoint_clear_all(self) -> None:
        """Clear all checkpoints."""
        self.storage.checkpoint_clear_all(self.procedure_id)

    def checkpoint_clear_after(self, name: str) -> None:
        """Clear checkpoint and all subsequent ones."""
        self.storage.checkpoint_clear_after(self.procedure_id, name)

    def checkpoint_exists(self, name: str) -> bool:
        """Check if checkpoint exists."""
        return self.storage.checkpoint_exists(self.procedure_id, name)

    def checkpoint_get(self, name: str) -> Optional[Any]:
        """Get cached checkpoint value."""
        return self.storage.checkpoint_get(self.procedure_id, name)


class InMemoryExecutionContext(BaseExecutionContext):
    """
    Simple in-memory execution context.

    Uses in-memory storage with no persistence. Useful for testing
    and simple CLI workflows that don't need to survive restarts.
    """

    def __init__(self, procedure_id: str, hitl_handler: Optional[HITLHandler] = None):
        """
        Initialize with in-memory storage.

        Args:
            procedure_id: ID of the running procedure
            hitl_handler: Optional HITL handler
        """
        from tactus.adapters.memory import MemoryStorage

        storage = MemoryStorage()
        super().__init__(procedure_id, storage, hitl_handler)
