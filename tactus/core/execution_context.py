"""
Execution context abstraction for Tactus runtime.

Provides execution backend support with position-based checkpointing and HITL capabilities.
Uses pluggable storage and HITL handlers via protocols.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, List, Dict
from datetime import datetime, timezone
import time

from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.models import HITLRequest, HITLResponse, CheckpointEntry


class ExecutionContext(ABC):
    """
    Abstract execution context for procedure workflows.

    Provides position-based checkpointing and HITL capabilities. Implementations
    determine how to persist state and handle human interactions.
    """

    @abstractmethod
    def checkpoint(self, fn: Callable[[], Any], checkpoint_type: str) -> Any:
        """
        Execute fn with position-based checkpointing. On replay, return stored result.

        Args:
            fn: Function to execute (should be deterministic)
            checkpoint_type: Type of checkpoint (agent_turn, model_predict, procedure_call, etc.)

        Returns:
            Result of fn() on first execution, cached result from execution log on replay
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
        """Clear all checkpoints (execution log). Used for testing."""
        pass

    @abstractmethod
    def checkpoint_clear_after(self, position: int) -> None:
        """Clear checkpoint at position and all subsequent ones. Used for testing."""
        pass

    @abstractmethod
    def next_position(self) -> int:
        """Get the next checkpoint position."""
        pass


class BaseExecutionContext(ExecutionContext):
    """
    Base execution context using pluggable storage and HITL handlers.

    Uses position-based checkpointing with execution log for replay.
    This implementation works with any StorageBackend and HITLHandler,
    making it suitable for various deployment scenarios (CLI, web, API, etc.).
    """

    def __init__(
        self,
        procedure_id: str,
        storage_backend: StorageBackend,
        hitl_handler: Optional[HITLHandler] = None,
        strict_determinism: bool = False,
    ):
        """
        Initialize base execution context.

        Args:
            procedure_id: ID of the running procedure
            storage_backend: Storage backend for execution log and state
            hitl_handler: Optional HITL handler for human interactions
            strict_determinism: If True, raise errors for non-deterministic operations outside checkpoints
        """
        self.procedure_id = procedure_id
        self.storage = storage_backend
        self.hitl = hitl_handler
        self.strict_determinism = strict_determinism

        # Checkpoint scope tracking for determinism safety
        self._inside_checkpoint = False

        # Load procedure metadata (contains execution_log and replay_index)
        self.metadata = self.storage.load_procedure_metadata(procedure_id)

    def checkpoint(self, fn: Callable[[], Any], checkpoint_type: str) -> Any:
        """
        Execute fn with position-based checkpointing.

        On replay, returns cached result from execution log.
        On first execution, runs fn(), records in log, and returns result.
        """
        current_position = self.metadata.replay_index

        # Check if we're in replay mode (checkpoint exists at this position)
        if current_position < len(self.metadata.execution_log):
            # Replay mode: return cached result
            entry = self.metadata.execution_log[current_position]
            self.metadata.replay_index += 1
            return entry.result

        # Execute mode: run function with checkpoint scope tracking
        old_checkpoint_flag = self._inside_checkpoint
        self._inside_checkpoint = True

        try:
            start_time = time.time()
            result = fn()
            duration_ms = (time.time() - start_time) * 1000

            # Create checkpoint entry
            entry = CheckpointEntry(
                position=current_position,
                type=checkpoint_type,
                result=result,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
            )
        finally:
            # Always restore checkpoint flag, even if fn() raises
            self._inside_checkpoint = old_checkpoint_flag

        # Add to execution log
        self.metadata.execution_log.append(entry)
        self.metadata.replay_index += 1

        # Persist metadata
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

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
        Sleep with checkpointing.

        On replay, skips the sleep. On first execution, sleeps and checkpoints.
        """

        def sleep_fn():
            time.sleep(seconds)
            return None

        self.checkpoint(sleep_fn, "sleep")

    def checkpoint_clear_all(self) -> None:
        """Clear all checkpoints (execution log)."""
        self.metadata.execution_log.clear()
        self.metadata.replay_index = 0
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

    def checkpoint_clear_after(self, position: int) -> None:
        """Clear checkpoint at position and all subsequent ones."""
        # Keep only checkpoints before the given position
        self.metadata.execution_log = self.metadata.execution_log[:position]
        self.metadata.replay_index = min(self.metadata.replay_index, position)
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

    def next_position(self) -> int:
        """Get the next checkpoint position."""
        return self.metadata.replay_index

    def store_procedure_handle(self, handle: Any) -> None:
        """
        Store async procedure handle.

        Args:
            handle: ProcedureHandle instance
        """
        # Store in metadata under "async_procedures" key
        if "async_procedures" not in self.metadata:
            self.metadata["async_procedures"] = {}

        self.metadata["async_procedures"][handle.procedure_id] = handle.to_dict()
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

    def get_procedure_handle(self, procedure_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve procedure handle.

        Args:
            procedure_id: ID of the procedure

        Returns:
            Handle dict or None
        """
        async_procedures = self.metadata.get("async_procedures", {})
        return async_procedures.get(procedure_id)

    def list_pending_procedures(self) -> List[Dict[str, Any]]:
        """
        List all pending async procedures.

        Returns:
            List of handle dicts for procedures with status "running" or "waiting"
        """
        async_procedures = self.metadata.get("async_procedures", {})
        return [
            handle
            for handle in async_procedures.values()
            if handle.get("status") in ("running", "waiting")
        ]

    def update_procedure_status(
        self, procedure_id: str, status: str, result: Any = None, error: str = None
    ) -> None:
        """
        Update procedure status.

        Args:
            procedure_id: ID of the procedure
            status: New status
            result: Optional result value
            error: Optional error message
        """
        if "async_procedures" not in self.metadata:
            return

        if procedure_id in self.metadata["async_procedures"]:
            handle = self.metadata["async_procedures"][procedure_id]
            handle["status"] = status
            if result is not None:
                handle["result"] = result
            if error is not None:
                handle["error"] = error
            if status in ("completed", "failed", "cancelled"):
                handle["completed_at"] = datetime.now(timezone.utc).isoformat()

            self.storage.save_procedure_metadata(self.procedure_id, self.metadata)


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
