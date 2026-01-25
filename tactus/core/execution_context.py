"""
Execution context abstraction for Tactus runtime.

Provides execution backend support with position-based checkpointing and HITL capabilities.
Uses pluggable storage and HITL handlers via protocols.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, List, Dict
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
        source_info: Optional[Dict[str, Any]] = None,
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
        self.current_run_id: Optional[str] = None

        # .tac file tracking for accurate source locations
        self.current_tac_file: Optional[str] = None
        self.current_tac_content: Optional[str] = None

        # Lua sandbox reference for debug.getinfo access
        self.lua_sandbox: Optional[Any] = None

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

    def set_tac_file(self, file_path: str, content: Optional[str] = None) -> None:
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
        self, procedure_name: Optional[str] = None, input_data: Any = None
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
        source_info: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute fn with position-based checkpointing and source tracking.

        On replay, returns cached result from execution log.
        On first execution, runs fn(), records in log, and returns result.
        """
        logger.info(
            f"[CHECKPOINT] checkpoint() called, type={checkpoint_type}, position={self.metadata.replay_index}, "
            f"current_run_id={self.current_run_id}, has_log_handler={self.log_handler is not None}"
        )
        current_position = self.metadata.replay_index

        # Check if we're in replay mode (checkpoint exists at this position)
        if current_position < len(self.metadata.execution_log):
            entry = self.metadata.execution_log[current_position]
            logger.info(
                f"[CHECKPOINT] Found existing checkpoint at position {current_position}: "
                f"type={entry.type}, run_id={entry.run_id}, result_type={type(entry.result).__name__}"
            )

            # CRITICAL: Only replay checkpoints from the CURRENT run
            # Each new run should execute fresh, not use cached results from previous runs
            if entry.run_id != self.current_run_id:
                logger.info(
                    f"[CHECKPOINT] Checkpoint is from DIFFERENT run "
                    f"(checkpoint run_id={entry.run_id}, current run_id={self.current_run_id}), "
                    f"executing fresh (NOT replaying)"
                )
                # Fall through to execute mode - this is a new run
            # Special case: HITL checkpoints may have result=None if saved before response arrived
            # In this case, re-execute to check for cached response from control loop
            elif entry.result is None and checkpoint_type.startswith("hitl_"):
                logger.info(
                    f"[CHECKPOINT] HITL checkpoint at position {current_position} has no result, "
                    f"re-executing to check for cached response"
                )
                # Fall through to execute mode - will check for cached response
            else:
                # Normal replay: return cached result from CURRENT run
                self.metadata.replay_index += 1
                logger.info(
                    f"[CHECKPOINT] REPLAYING checkpoint at position {current_position}, "
                    f"type={entry.type}, run_id={entry.run_id}, returning cached result"
                )
                return entry.result
        else:
            logger.info(
                f"[CHECKPOINT] No checkpoint at position {current_position} "
                f"(only {len(self.metadata.execution_log)} checkpoints exist), executing fresh"
            )

        # Execute mode: run function with checkpoint scope tracking
        old_checkpoint_flag = self._inside_checkpoint
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
            start_time = time.time()
            result = fn()
            duration_ms = (time.time() - start_time) * 1000

            # Create checkpoint entry with source location and run_id (if available)
            entry = CheckpointEntry(
                position=current_position,
                type=checkpoint_type,
                result=result,
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
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
            duration_ms = (time.time() - start_time) * 1000
            entry = CheckpointEntry(
                position=current_position,
                type=checkpoint_type,
                result=None,  # Will be filled in when response arrives
                timestamp=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                run_id=self.current_run_id,
                source_location=source_location,
                captured_vars=(
                    self.metadata.state.copy() if hasattr(self.metadata, "state") else None
                ),
            )
            # Only append if checkpoint doesn't already exist (from previous failed attempt)
            if current_position < len(self.metadata.execution_log):
                # Checkpoint already exists - update it
                logger.debug(
                    f"[CHECKPOINT] Updating existing HITL checkpoint at position {current_position} before exit"
                )
                self.metadata.execution_log[current_position] = entry
            else:
                # New checkpoint - append and increment
                logger.debug(
                    f"[CHECKPOINT] Creating new HITL checkpoint at position {current_position} before exit"
                )
                self.metadata.execution_log.append(entry)
                self.metadata.replay_index += 1

            self.storage.save_procedure_metadata(self.procedure_id, self.metadata)
            # Restore checkpoint flag and re-raise
            self._inside_checkpoint = old_checkpoint_flag
            raise
        finally:
            # Always restore checkpoint flag, even if fn() raises
            self._inside_checkpoint = old_checkpoint_flag

        # Add to execution log (or update if checkpoint already exists from HITL exit)
        if current_position < len(self.metadata.execution_log):
            # Checkpoint already exists (saved during HITL exit) - update it with the result
            logger.debug(
                f"[CHECKPOINT] Updating existing HITL checkpoint at position {current_position} with result"
            )
            self.metadata.execution_log[current_position] = entry
        else:
            # New checkpoint - append to log
            self.metadata.execution_log.append(entry)
        self.metadata.replay_index += 1

        # Emit checkpoint created event if we have a log handler
        if self.log_handler:
            try:
                from tactus.protocols.models import CheckpointCreatedEvent

                event = CheckpointCreatedEvent(
                    checkpoint_position=current_position,
                    checkpoint_type=checkpoint_type,
                    duration_ms=duration_ms,
                    source_location=source_location,
                    procedure_id=self.procedure_id,
                )
                logger.debug(
                    f"[CHECKPOINT] Emitting CheckpointCreatedEvent: position={current_position}, type={checkpoint_type}, duration_ms={duration_ms}"
                )
                self.log_handler.log(event)
            except Exception as e:
                logger.warning(f"Failed to emit checkpoint event: {e}")
        else:
            logger.warning("[CHECKPOINT] No log_handler available to emit checkpoint event")

        # Persist metadata
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

        return result

    def _get_code_context(self, file_path: str, line: int, context_lines: int = 3) -> Optional[str]:
        """Read source file and extract surrounding lines for debugging."""
        try:
            with open(file_path, "r") as f:
                lines = f.readlines()
                start = max(0, line - context_lines - 1)
                end = min(len(lines), line + context_lines)
                return "".join(lines[start:end])
        except Exception:
            return None

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
        logger.debug(
            f"[HITL] wait_for_human called: type={request_type}, message={message[:50] if message else 'None'}, hitl_handler={self.hitl}"
        )
        if not self.hitl:
            # No HITL handler - return default immediately
            logger.warning(
                f"[HITL] No HITL handler configured - returning default value: {default_value}"
            )
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
        # Pass self (execution_context) for deterministic request ID generation
        return self.hitl.request_interaction(self.procedure_id, request, execution_context=self)

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

    def get_subject(self) -> Optional[str]:
        """
        Return a human-readable subject line for this execution.

        Returns:
            Subject line combining procedure name and current checkpoint position
        """
        checkpoint_pos = self.next_position()
        if self.procedure_name:
            return f"{self.procedure_name} (checkpoint {checkpoint_pos})"
        return f"Procedure {self.procedure_id} (checkpoint {checkpoint_pos})"

    def get_started_at(self) -> Optional[datetime]:
        """
        Return when this execution started.

        Returns:
            Timestamp when execution context was created
        """
        return self._started_at

    def get_input_summary(self) -> Optional[Dict[str, Any]]:
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

    def get_conversation_history(self) -> Optional[List[Dict]]:
        """
        Return conversation history if available.

        Returns:
            List of conversation messages, or None if not tracked
        """
        # For now, return None - could be extended to track agent conversations
        # in future implementations
        return None

    def get_prior_control_interactions(self) -> Optional[List[Dict]]:
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

    def get_lua_source_line(self) -> Optional[int]:
        """
        Get the current source line from Lua debug.getinfo.

        Returns:
            Line number or None if unavailable
        """
        if not self.lua_sandbox:
            return None

        try:
            # Access Lua debug module to get current line
            debug_mod = self.lua_sandbox.globals().debug
            if debug_mod and hasattr(debug_mod, "getinfo"):
                # getinfo(2) gets info about the calling function
                # We need to go up the stack to find the user's code
                for level in range(2, 10):
                    try:
                        info = debug_mod.getinfo(level, "Sl")
                        if info:
                            line = info.get("currentline")
                            source = info.get("source", "")
                            # Skip internal sources (start with @)
                            if line and line > 0 and not source.startswith("@"):
                                return int(line)
                    except Exception:
                        break
        except Exception as e:
            logger.debug(f"Could not get Lua source line: {e}")

        return None

    def get_runtime_context(self) -> Dict[str, Any]:
        """
        Build RuntimeContext dict for HITL requests.

        Captures source location, execution position, elapsed time, and backtrace.

        Returns:
            Dict with runtime context fields
        """
        # Calculate elapsed time
        elapsed = 0.0
        if self._started_at:
            elapsed = (datetime.now(timezone.utc) - self._started_at).total_seconds()

        # Get current source location
        source_line = self.get_lua_source_line()

        # Build backtrace from execution log
        backtrace = []
        if self.metadata and self.metadata.execution_log:
            for entry in self.metadata.execution_log:
                bt_entry = {
                    "checkpoint_type": entry.type,
                    "duration_ms": entry.duration_ms,
                }
                if entry.source_location:
                    bt_entry["line"] = entry.source_location.line
                    bt_entry["function_name"] = entry.source_location.function
                backtrace.append(bt_entry)

        return {
            "source_line": source_line,
            "source_file": self.current_tac_file,
            "checkpoint_position": self.next_position(),
            "procedure_name": self.procedure_name,
            "invocation_id": self.invocation_id,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "elapsed_seconds": elapsed,
            "backtrace": backtrace,
        }


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
