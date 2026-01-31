"""
Execution context abstraction for Tactus runtime.

Provides execution backend support with position-based checkpointing and HITL capabilities.
Uses pluggable storage and HITL handlers via protocols.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable
from datetime import datetime, timezone
import logging
import time
import uuid

from tactus.protocols.storage import StorageBackend
from tactus.protocols.hitl import HITLHandler
from tactus.protocols.models import (
    HITLRequest,
    HITLResponse,
    CheckpointEntry,
    SourceLocation,
    ExecutionRun,
)
from tactus.core.exceptions import ProcedureWaitingForHuman

logger = logging.getLogger(__name__)


class ExecutionContext(ABC):
    """
    Abstract execution context for procedure workflows.

    Provides position-based checkpointing and HITL capabilities. Implementations
    determine how to persist state and handle human interactions.
    """

    @abstractmethod
    def checkpoint(
        self,
        fn: Callable[[], Any],
        checkpoint_type: str,
        source_info: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute fn with position-based checkpointing. On replay, return stored result.

        Args:
            fn: Function to execute (should be deterministic)
            checkpoint_type: Type of checkpoint (agent_turn, model_predict, procedure_call, etc.)
            source_info: Optional dict with {file, line, function} for debugging

        Returns:
            Result of fn() on first execution, cached result from execution log on replay
        """
        pass

    @abstractmethod
    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: int | None,
        default_value: Any,
        options: list[dict] | None,
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
        hitl_handler: HITLHandler | None = None,
        strict_determinism: bool = False,
        log_handler=None,
    ):
        """
        Initialize base execution context.

        Args:
            procedure_id: ID of the running procedure
            storage_backend: Storage backend for execution log and state
            hitl_handler: Optional HITL handler for human interactions
            strict_determinism: If True, raise errors for non-deterministic operations outside checkpoints
            log_handler: Optional log handler for emitting events
        """
        self.procedure_id = procedure_id
        self.storage = storage_backend
        self.hitl = hitl_handler
        self.strict_determinism = strict_determinism
        self.log_handler = log_handler

        # Checkpoint scope tracking for determinism safety
        self._inside_checkpoint = False

        # Run ID tracking for distinguishing between different executions
        self.current_run_id: str | None = None

        # .tac file tracking for accurate source locations
        self.current_tac_file: str | None = None
        self.current_tac_content: str | None = None

        # Lua sandbox reference for debug.getinfo access
        self.lua_sandbox: Any | None = None

        # Rich metadata for HITL notifications
        self.procedure_name: str = procedure_id  # Use procedure_id as default name
        self.invocation_id: str = str(uuid.uuid4())
        self._started_at: datetime = datetime.now(timezone.utc)
        self._input_data: Any = None

        # Load procedure metadata (contains execution_log and replay_index)
        self.metadata = self.storage.load_procedure_metadata(procedure_id)

        # CRITICAL: Reset replay_index to 0 when starting a new execution
        # The replay_index tracks our position when replaying the execution_log
        # It must start at 0 for each new run, even though it was incremented during the previous run
        self.metadata.replay_index = 0

    def set_run_id(self, run_id: str) -> None:
        """Set the run_id for subsequent checkpoints in this execution."""
        self.current_run_id = run_id

    def set_tac_file(self, file_path: str, content: str | None = None) -> None:
        """
        Store the currently executing .tac file for accurate source location capture.

        Args:
            file_path: Path to the .tac file being executed
            content: Optional content of the .tac file (for code context)
        """
        self.current_tac_file = file_path
        self.current_tac_content = content

    def set_lua_sandbox(self, lua_sandbox: Any) -> None:
        """Store reference to Lua sandbox for debug.getinfo access."""
        self.lua_sandbox = lua_sandbox

    def set_procedure_metadata(
        self, procedure_name: str | None = None, input_data: Any = None
    ) -> None:
        """
        Set rich metadata for HITL notifications.

        Args:
            procedure_name: Human-readable name for the procedure
            input_data: Input data passed to the procedure
        """
        if procedure_name is not None:
            self.procedure_name = procedure_name
        if input_data is not None:
            self._input_data = input_data

    def checkpoint(
        self,
        fn: Callable[[], Any],
        checkpoint_type: str,
        source_info: dict[str, Any] | None = None,
    ) -> Any:
        """
        Execute fn with position-based checkpointing and source tracking.

        On replay, returns cached result from execution log.
        On first execution, runs fn(), records in log, and returns result.
        """
        logger.info(
            "[CHECKPOINT] checkpoint() called, type=%s, position=%s, current_run_id=%s, "
            "has_log_handler=%s",
            checkpoint_type,
            self.metadata.replay_index,
            self.current_run_id,
            self.log_handler is not None,
        )
        checkpoint_position = self.metadata.replay_index

        # Check if we're in replay mode (checkpoint exists at this position)
        if checkpoint_position < len(self.metadata.execution_log):
            checkpoint_entry = self.metadata.execution_log[checkpoint_position]
            logger.info(
                "[CHECKPOINT] Found existing checkpoint at position %s: type=%s, run_id=%s, "
                "result_type=%s",
                checkpoint_position,
                checkpoint_entry.type,
                checkpoint_entry.run_id,
                type(checkpoint_entry.result).__name__,
            )

            # CRITICAL: Only replay checkpoints from the CURRENT run
            # Each new run should execute fresh, not use cached results from previous runs
            if checkpoint_entry.run_id != self.current_run_id:
                logger.info(
                    "[CHECKPOINT] Checkpoint is from DIFFERENT run (checkpoint run_id=%s, "
                    "current run_id=%s), executing fresh (NOT replaying)",
                    checkpoint_entry.run_id,
                    self.current_run_id,
                )
                # Fall through to execute mode - this is a new run
            # Special case: HITL checkpoints may have result=None if saved before response arrived
            # In this case, re-execute to check for cached response from control loop
            elif checkpoint_entry.result is None and checkpoint_type.startswith("hitl_"):
                logger.info(
                    "[CHECKPOINT] HITL checkpoint at position %s has no result, re-executing "
                    "to check for cached response",
                    checkpoint_position,
                )
                # Fall through to execute mode - will check for cached response
            else:
                # Normal replay: return cached result from CURRENT run
                self.metadata.replay_index += 1
                logger.info(
                    "[CHECKPOINT] REPLAYING checkpoint at position %s, type=%s, run_id=%s, "
                    "returning cached result",
                    checkpoint_position,
                    checkpoint_entry.type,
                    checkpoint_entry.run_id,
                )
                return checkpoint_entry.result
        else:
            logger.info(
                "[CHECKPOINT] No checkpoint at position %s (only %s checkpoints exist), "
                "executing fresh",
                checkpoint_position,
                len(self.metadata.execution_log),
            )

        # Execute mode: run function with checkpoint scope tracking
        previous_checkpoint_state = self._inside_checkpoint
        self._inside_checkpoint = True

        # Capture source location if provided
        source_location = None
        if source_info:
            source_location = SourceLocation(
                file=source_info["file"],
                line=source_info["line"],
                function=source_info.get("function"),
                code_context=self._get_code_context(source_info["file"], source_info["line"]),
            )
        elif self.current_tac_file:
            # Use .tac file context if no source_info provided
            source_location = SourceLocation(
                file=self.current_tac_file,
                line=0,  # Will be improved with Lua line tracking
                function="unknown",
                code_context=None,  # Can be added later if needed
            )

        try:
            execution_start_time = time.time()
            result = fn()
            execution_duration_ms = (time.time() - execution_start_time) * 1000

            # Create checkpoint entry with source location and run_id (if available)
            checkpoint_entry = CheckpointEntry(
                position=checkpoint_position,
                type=checkpoint_type,
                result=result,
                timestamp=datetime.now(timezone.utc),
                duration_ms=execution_duration_ms,
                run_id=self.current_run_id,  # Can be None for backward compatibility
                source_location=source_location,
                captured_vars=(
                    self.metadata.state.copy() if hasattr(self.metadata, "state") else None
                ),
            )
        except ProcedureWaitingForHuman:
            # CRITICAL: For HITL checkpoints, we need to save the checkpoint BEFORE exiting
            # This enables transparent resume - on restart, we'll have a checkpoint at this position
            # with result=None, and the control loop will check for cached responses
            execution_duration_ms = (time.time() - execution_start_time) * 1000
            checkpoint_entry = CheckpointEntry(
                position=checkpoint_position,
                type=checkpoint_type,
                result=None,  # Will be filled in when response arrives
                timestamp=datetime.now(timezone.utc),
                duration_ms=execution_duration_ms,
                run_id=self.current_run_id,
                source_location=source_location,
                captured_vars=(
                    self.metadata.state.copy() if hasattr(self.metadata, "state") else None
                ),
            )
            # Only append if checkpoint doesn't already exist (from previous failed attempt)
            if checkpoint_position < len(self.metadata.execution_log):
                # Checkpoint already exists - update it
                logger.debug(
                    "[CHECKPOINT] Updating existing HITL checkpoint at position %s " "before exit",
                    checkpoint_position,
                )
                self.metadata.execution_log[checkpoint_position] = checkpoint_entry
            else:
                # New checkpoint - append and increment
                logger.debug(
                    "[CHECKPOINT] Creating new HITL checkpoint at position %s before exit",
                    checkpoint_position,
                )
                self.metadata.execution_log.append(checkpoint_entry)
                self.metadata.replay_index += 1

            self.storage.save_procedure_metadata(self.procedure_id, self.metadata)
            # Restore checkpoint flag and re-raise
            self._inside_checkpoint = previous_checkpoint_state
            raise
        finally:
            # Always restore checkpoint flag, even if fn() raises
            self._inside_checkpoint = previous_checkpoint_state

        # Add to execution log (or update if checkpoint already exists from HITL exit)
        if checkpoint_position < len(self.metadata.execution_log):
            # Checkpoint already exists (saved during HITL exit) - update it with the result
            logger.debug(
                "[CHECKPOINT] Updating existing HITL checkpoint at position %s with result",
                checkpoint_position,
            )
            self.metadata.execution_log[checkpoint_position] = checkpoint_entry
        else:
            # New checkpoint - append to log
            self.metadata.execution_log.append(checkpoint_entry)
        self.metadata.replay_index += 1

        # Emit checkpoint created event if we have a log handler
        if self.log_handler:
            try:
                from tactus.protocols.models import CheckpointCreatedEvent

                event = CheckpointCreatedEvent(
                    checkpoint_position=checkpoint_position,
                    checkpoint_type=checkpoint_type,
                    duration_ms=execution_duration_ms,
                    source_location=source_location,
                    procedure_id=self.procedure_id,
                )
                logger.debug(
                    "[CHECKPOINT] Emitting CheckpointCreatedEvent: position=%s, type=%s, "
                    "duration_ms=%s",
                    checkpoint_position,
                    checkpoint_type,
                    execution_duration_ms,
                )
                self.log_handler.log(event)
            except Exception as exception:
                logger.warning("Failed to emit checkpoint event: %s", exception)
        else:
            logger.warning("[CHECKPOINT] No log_handler available to emit checkpoint event")

        # Persist metadata
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

        return result

    def _get_code_context(
        self, file_path: str, line_number: int, context_lines: int = 3
    ) -> str | None:
        """Read source file and extract surrounding lines for debugging."""
        try:
            with open(file_path, "r") as source_file:
                lines = source_file.readlines()
                start_index = max(0, line_number - context_lines - 1)
                end_index = min(len(lines), line_number + context_lines)
                return "".join(lines[start_index:end_index])
        except Exception:
            return None

    def wait_for_human(
        self,
        request_type: str,
        message: str,
        timeout_seconds: int | None,
        default_value: Any,
        options: list[dict] | None,
        metadata: dict,
    ) -> HITLResponse:
        """
        Wait for human response using the configured HITL handler.

        Delegates to the HITLHandler protocol implementation.
        """
        message_preview = message[:50] if message else "None"
        logger.debug(
            "[HITL] wait_for_human called: type=%s, message=%s, hitl_handler=%s",
            request_type,
            message_preview,
            self.hitl,
        )
        if not self.hitl:
            # No HITL handler - return default immediately
            logger.warning(
                "[HITL] No HITL handler configured - returning default value: %s",
                default_value,
            )
            return HITLResponse(
                value=default_value, responded_at=datetime.now(timezone.utc), timed_out=True
            )

        # Create HITL request
        hitl_request = HITLRequest(
            request_type=request_type,
            message=message,
            timeout_seconds=timeout_seconds,
            default_value=default_value,
            options=options,
            metadata=metadata,
        )

        # Delegate to HITL handler (may raise ProcedureWaitingForHuman)
        # Pass self (execution_context) for deterministic request ID generation
        return self.hitl.request_interaction(
            self.procedure_id, hitl_request, execution_context=self
        )

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
        async_procedure_handles = self._get_async_procedures()
        async_procedure_handles[handle.procedure_id] = handle.to_dict()
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

    def get_procedure_handle(self, procedure_id: str) -> dict[str, Any] | None:
        """
        Retrieve procedure handle.

        Args:
            procedure_id: ID of the procedure

        Returns:
            Handle dict or None
        """
        return self._get_async_procedures().get(procedure_id)

    def list_pending_procedures(self) -> list[dict[str, Any]]:
        """
        List all pending async procedures.

        Returns:
            List of handle dicts for procedures with status "running" or "waiting"
        """
        async_procedures = self._get_async_procedures()
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
        async_procedures = self._get_async_procedures()
        if procedure_id in async_procedures:
            handle = async_procedures[procedure_id]
            handle["status"] = status
            if result is not None:
                handle["result"] = result
            if error is not None:
                handle["error"] = error
            if status in ("completed", "failed", "cancelled"):
                handle["completed_at"] = datetime.now(timezone.utc).isoformat()

            self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

    def _get_async_procedures(self) -> dict[str, Any]:
        """Return the async procedures map stored on metadata."""
        if isinstance(self.metadata, dict):
            return self.metadata.setdefault("async_procedures", {})
        store = getattr(self.metadata, "__dict__", None)
        if store is None:
            return {}
        if "async_procedures" not in store:
            store["async_procedures"] = {}
        return store["async_procedures"]

    def save_execution_run(
        self, procedure_name: str, file_path: str, status: str = "COMPLETED"
    ) -> str:
        """
        Convert current execution to ExecutionRun and save for tracing.

        Args:
            procedure_name: Name of the procedure
            file_path: Path to the .tac file
            status: Run status (COMPLETED, FAILED, etc.)

        Returns:
            The run_id of the saved run
        """
        # Generate run ID
        run_id = str(uuid.uuid4())

        # Determine start time from first checkpoint or now
        start_time = (
            self.metadata.execution_log[0].timestamp
            if self.metadata.execution_log
            else datetime.now(timezone.utc)
        )

        # Create ExecutionRun
        run = ExecutionRun(
            run_id=run_id,
            procedure_name=procedure_name,
            file_path=file_path,
            start_time=start_time,
            end_time=datetime.now(timezone.utc),
            status=status,
            execution_log=self.metadata.execution_log.copy(),
            final_state=self.metadata.state.copy() if hasattr(self.metadata, "state") else {},
            breakpoints=[],
        )

        # Save to storage
        self.storage.save_run(run)

        return run_id

    def get_subject(self) -> str | None:
        """
        Return a human-readable subject line for this execution.

        Returns:
            Subject line combining procedure name and current checkpoint position
        """
        checkpoint_position = self.next_position()
        if self.procedure_name:
            return f"{self.procedure_name} (checkpoint {checkpoint_position})"
        return f"Procedure {self.procedure_id} (checkpoint {checkpoint_position})"

    def get_started_at(self) -> datetime | None:
        """
        Return when this execution started.

        Returns:
            Timestamp when execution context was created
        """
        return self._started_at

    def get_input_summary(self) -> dict[str, Any] | None:
        """
        Return a summary of the initial input to this procedure.

        Returns:
            Dict of input data, or None if no input
        """
        if self._input_data is None:
            return None

        # If input_data is already a dict, return it
        if isinstance(self._input_data, dict):
            return self._input_data

        # Otherwise wrap it in a dict
        return {"value": self._input_data}

    def get_conversation_history(self) -> list[dict] | None:
        """
        Return conversation history if available.

        Returns:
            List of conversation messages, or None if not tracked
        """
        # For now, return None - could be extended to track agent conversations
        # in future implementations
        return None

    def get_prior_control_interactions(self) -> list[dict] | None:
        """
        Return list of prior HITL interactions in this execution.

        Returns:
            List of HITL checkpoint entries from execution log
        """
        if not self.metadata or not self.metadata.execution_log:
            return None

        # Filter execution log for HITL checkpoints
        hitl_checkpoints = [
            {
                "position": entry.position,
                "type": entry.type,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "duration_ms": entry.duration_ms,
            }
            for entry in self.metadata.execution_log
            if entry.type.startswith("hitl_")
        ]

        return hitl_checkpoints if hitl_checkpoints else None

    def get_lua_source_line(self) -> int | None:
        """
        Get the current source line from Lua debug.getinfo.

        Returns:
            Line number or None if unavailable
        """
        if not self.lua_sandbox:
            return None

        try:
            # Access Lua debug module to get current line
            debug_module = self.lua_sandbox.globals().debug
            if debug_module and hasattr(debug_module, "getinfo"):
                # getinfo(2) gets info about the calling function
                # We need to go up the stack to find the user's code
                for level in range(2, 10):
                    try:
                        debug_info = debug_module.getinfo(level, "Sl")
                        if debug_info:
                            current_line = debug_info.get("currentline")
                            source_name = debug_info.get("source", "")
                            # Skip internal sources (start with @)
                            if (
                                current_line
                                and current_line > 0
                                and not source_name.startswith("@")
                            ):
                                return int(current_line)
                    except Exception:
                        break
        except Exception as exception:
            logger.debug("Could not get Lua source line: %s", exception)

        return None

    def get_runtime_context(self) -> dict[str, Any]:
        """
        Build RuntimeContext dict for HITL requests.

        Captures source location, execution position, elapsed time, and backtrace.

        Returns:
            Dict with runtime context fields
        """
        # Calculate elapsed time
        elapsed_seconds = 0.0
        if self._started_at:
            elapsed_seconds = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        # Get current source location
        source_line = self.get_lua_source_line()

        # Build backtrace from execution log
        backtrace = []
        if self.metadata and self.metadata.execution_log:
            for entry in self.metadata.execution_log:
                backtrace_entry = {
                    "checkpoint_type": entry.type,
                    "duration_ms": entry.duration_ms,
                }
                if entry.source_location:
                    backtrace_entry["line"] = entry.source_location.line
                    backtrace_entry["function_name"] = entry.source_location.function
                backtrace.append(backtrace_entry)

        return {
            "source_line": source_line,
            "source_file": self.current_tac_file,
            "checkpoint_position": self.next_position(),
            "procedure_name": self.procedure_name,
            "invocation_id": self.invocation_id,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "elapsed_seconds": elapsed_seconds,
            "backtrace": backtrace,
        }


class InMemoryExecutionContext(BaseExecutionContext):
    """
    Simple in-memory execution context.

    Uses in-memory storage with no persistence. Useful for testing
    and simple CLI workflows that don't need to survive restarts.
    """

    def __init__(self, procedure_id: str, hitl_handler: HITLHandler | None = None):
        """
        Initialize with in-memory storage.

        Args:
            procedure_id: ID of the running procedure
            hitl_handler: Optional HITL handler
        """
        from tactus.adapters.memory import MemoryStorage

        storage = MemoryStorage()
        super().__init__(procedure_id, storage, hitl_handler)
