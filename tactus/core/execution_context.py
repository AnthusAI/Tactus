"""
Execution context abstraction for Tactus runtime.

Provides execution backend support with position-based checkpointing and HITL capabilities.
Uses pluggable storage and HITL handlers via protocols.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
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
from tactus.core.exceptions import (
    ProcedureWaitingForChildren,
    ProcedureWaitingForHuman,
    ProcedureWaitingForTime,
)

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
    def await_children(self, request: dict) -> dict:
        """Resolve host-managed external children or suspend for a later replay."""
        pass

    @abstractmethod
    def defer(self, request: dict) -> dict:
        """Suspend until a durable, host-scheduled continuation is due."""
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
        child_wait_resolver: Optional[Callable[[dict], dict]] = None,
        clock: Optional[Callable[[], datetime]] = None,
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
        self.child_wait_resolver = child_wait_resolver
        self._clock = clock or (lambda: datetime.now(timezone.utc))
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
        self._initialize_run_metadata(procedure_id)
        self._load_and_reset_metadata(procedure_id)

    def _initialize_run_metadata(self, procedure_id: str) -> None:
        self.procedure_name = procedure_id
        self.invocation_id = str(uuid.uuid4())
        self._started_at = datetime.now(timezone.utc)
        self._input_data = None

    def _load_and_reset_metadata(self, procedure_id: str) -> None:
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
        logger.debug(
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
            logger.debug(
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
                logger.debug(
                    "[CHECKPOINT] Checkpoint is from DIFFERENT run (checkpoint run_id=%s, "
                    "current run_id=%s), executing fresh (NOT replaying)",
                    checkpoint_entry.run_id,
                    self.current_run_id,
                )
                # Fall through to execute mode - this is a new run
            # Suspend checkpoints re-execute on replay so their host integration can
            # observe new state instead of returning the pending marker as a result.
            elif (
                checkpoint_type in {"external_children_wait", "scheduled_continuation"}
                and isinstance(checkpoint_entry.result, dict)
                and checkpoint_entry.result.get("pending") is True
            ):
                logger.debug(
                    "[CHECKPOINT] External-child wait checkpoint at position %s is pending; "
                    "re-executing to resolve current host state",
                    checkpoint_position,
                )
            # Special case: HITL checkpoints may have result=None if saved before response arrived.
            # In this case, re-execute to check for cached response from control loop.
            elif checkpoint_entry.result is None and checkpoint_type.startswith("hitl_"):
                logger.debug(
                    "[CHECKPOINT] HITL checkpoint at position %s has no result, re-executing "
                    "to check for cached response",
                    checkpoint_position,
                )
                # Fall through to execute mode - will check for cached response
            else:
                # Normal replay: return cached result from CURRENT run
                self.metadata.replay_index += 1
                logger.debug(
                    "[CHECKPOINT] REPLAYING checkpoint at position %s, type=%s, run_id=%s, "
                    "returning cached result",
                    checkpoint_position,
                    checkpoint_entry.type,
                    checkpoint_entry.run_id,
                )
                return checkpoint_entry.result
        else:
            logger.debug(
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
        except (
            ProcedureWaitingForHuman,
            ProcedureWaitingForChildren,
            ProcedureWaitingForTime,
        ) as exception:
            # Suspend checkpoints must be persisted before exiting so replay can
            # re-resolve host state without retaining a process-local waiter.
            execution_duration_ms = (time.time() - execution_start_time) * 1000
            checkpoint_entry = CheckpointEntry(
                position=checkpoint_position,
                type=checkpoint_type,
                result=(
                    {"pending": True, "request": exception.request}
                    if isinstance(exception, (ProcedureWaitingForChildren, ProcedureWaitingForTime))
                    else None
                ),
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
            logger.debug("[CHECKPOINT] No log_handler available to emit checkpoint event")

        # Persist metadata
        self.storage.save_procedure_metadata(self.procedure_id, self.metadata)

        return result

    def _get_code_context(
        self, file_path: str, line_number: int, context_lines: int = 3
    ) -> Optional[str]:
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
        timeout_seconds: Optional[int],
        default_value: Any,
        options: Optional[List[dict]],
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

    def await_children(self, request: dict) -> dict:
        """Resolve external child snapshots through the injected host callback.

        Tactus validates and checkpoints the durable request, while the host owns
        child creation, polling, persistence, authorization, and resume scheduling.
        """
        # A resumed procedure re-executes its source. Inputs used to construct a
        # wait request may therefore have changed since the first attempt. The
        # checkpointed request is the durable boundary: it contains the exact
        # opaque child identities the host was asked to await, and must remain
        # authoritative until the wait reaches a terminal result.
        normalized_request = self._pending_external_children_request()
        if normalized_request is None:
            normalized_request = self._normalize_child_wait_request(request)

        def resolve_children() -> dict:
            if self.child_wait_resolver is None:
                raise RuntimeError("No external child wait resolver is configured")

            resolution = self.child_wait_resolver(normalized_request)
            children = self._normalize_child_wait_resolution(normalized_request, resolution)
            mode = normalized_request["mode"]
            complete = (
                all(child["terminal"] for child in children)
                if mode == "all"
                else any(child["terminal"] for child in children)
            )
            if not complete:
                raise ProcedureWaitingForChildren(self.procedure_id, normalized_request, children)
            return {"children": children, "complete": True}

        return self.checkpoint(resolve_children, "external_children_wait")

    def defer(self, request: dict) -> dict:
        """Checkpoint a host-neutral scheduled continuation.

        Tactus never sleeps or schedules a timer here. A host simply receives
        :class:`ProcedureWaitingForTime` from the runtime, releases the worker,
        and invokes a normal replay at or after ``resume_at``. The first
        request becomes durable; a replay with different stable inputs fails
        closed instead of silently retargeting the continuation.
        """
        supplied_request = self._normalize_scheduled_continuation_request(request)
        durable_request = self._scheduled_continuation_request_at_current_position()
        if durable_request is not None:
            if supplied_request != durable_request:
                raise ValueError(
                    "Scheduled continuation request conflicts with the durable checkpoint"
                )
            normalized_request = durable_request
        else:
            normalized_request = supplied_request

        resume_at = self._parse_scheduled_continuation_time(normalized_request["resume_at"])

        def resolve_continuation() -> dict:
            if self._now() < resume_at:
                raise ProcedureWaitingForTime(self.procedure_id, normalized_request, resume_at)
            return {"completed": True, **normalized_request}

        return self.checkpoint(resolve_continuation, "scheduled_continuation")

    def _pending_external_children_request(self) -> Optional[dict]:
        """Return the durable pending request at the current replay position.

        This deliberately mirrors :meth:`checkpoint`'s current-run boundary.
        A checkpoint from another run is not replayed, so it cannot supply a
        request to a new run. A malformed persisted request is a storage
        integrity problem and fails closed rather than allowing a changed input
        to redirect the host lookup to different children.
        """
        checkpoint_position = self.metadata.replay_index
        if checkpoint_position >= len(self.metadata.execution_log):
            return None

        checkpoint_entry = self.metadata.execution_log[checkpoint_position]
        if (
            checkpoint_entry.run_id != self.current_run_id
            or checkpoint_entry.type != "external_children_wait"
            or not isinstance(checkpoint_entry.result, dict)
            or checkpoint_entry.result.get("pending") is not True
        ):
            return None

        if "request" not in checkpoint_entry.result:
            raise ValueError("Pending external-child wait checkpoint has no request")
        return self._normalize_child_wait_request(checkpoint_entry.result["request"])

    def _scheduled_continuation_request_at_current_position(self) -> Optional[dict]:
        """Return the durable continuation request at the current replay position.

        The request remains authoritative after the continuation is completed,
        not merely while it is pending. Otherwise a changed call site could
        receive a cached completion result for a different continuation.
        """
        checkpoint_position = self.metadata.replay_index
        if checkpoint_position >= len(self.metadata.execution_log):
            return None

        checkpoint_entry = self.metadata.execution_log[checkpoint_position]
        if (
            checkpoint_entry.run_id != self.current_run_id
            or checkpoint_entry.type != "scheduled_continuation"
            or not isinstance(checkpoint_entry.result, dict)
        ):
            return None
        if checkpoint_entry.result.get("pending") is True:
            if "request" not in checkpoint_entry.result:
                raise ValueError("Pending scheduled continuation checkpoint has no request")
            return self._normalize_scheduled_continuation_request(
                checkpoint_entry.result["request"]
            )
        if checkpoint_entry.result.get("completed") is True:
            return self._normalize_scheduled_continuation_request(
                {key: checkpoint_entry.result.get(key) for key in ("key", "resume_at", "reason")}
            )
        raise ValueError("Scheduled continuation checkpoint has an invalid result")

    @staticmethod
    def _normalize_scheduled_continuation_request(request: Any) -> dict:
        if not isinstance(request, dict):
            raise ValueError("Scheduled continuation request must be a table")
        allowed_keys = {"key", "resume_at", "reason"}
        unexpected = set(request) - allowed_keys
        if unexpected:
            raise ValueError(
                "Scheduled continuation request has unsupported fields: " f"{sorted(unexpected)}"
            )
        key = request.get("key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Scheduled continuation request requires a nonempty string key")
        reason = request.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Scheduled continuation request requires a nonempty string reason")
        resume_at = request.get("resume_at")
        if not isinstance(resume_at, str) or not resume_at.strip():
            raise ValueError("Scheduled continuation request requires an ISO-8601 resume_at")
        parsed_resume_at = BaseExecutionContext._parse_scheduled_continuation_time(resume_at)
        return {
            "key": key.strip(),
            "resume_at": parsed_resume_at.isoformat().replace("+00:00", "Z"),
            "reason": reason.strip(),
        }

    @staticmethod
    def _parse_scheduled_continuation_time(resume_at: str) -> datetime:
        try:
            parsed = datetime.fromisoformat(resume_at.replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Scheduled continuation resume_at must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Scheduled continuation resume_at must include a timezone")
        return parsed.astimezone(timezone.utc)

    def _now(self) -> datetime:
        """Return a timezone-aware UTC clock value, failing closed on bad hosts."""
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Scheduled continuation clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    @staticmethod
    def _normalize_child_wait_request(request: Any) -> dict:
        if not isinstance(request, dict):
            raise ValueError("External child wait request must be a table")
        allowed_keys = {"children", "mode"}
        unexpected = set(request) - allowed_keys
        if unexpected:
            raise ValueError(
                f"External child wait request has unsupported fields: {sorted(unexpected)}"
            )
        children = request.get("children")
        if not isinstance(children, list) or not children:
            raise ValueError("External child wait request requires at least one child")
        mode = request.get("mode", "all")
        if mode not in {"all", "any"}:
            raise ValueError("External child wait mode must be 'all' or 'any'")

        normalized_children = []
        child_ids = set()
        for child in children:
            if not isinstance(child, dict):
                raise ValueError("Each external child reference must be a table")
            child_id = child.get("id")
            if not isinstance(child_id, str) or not child_id.strip():
                raise ValueError("Each external child reference requires a nonempty string id")
            if child_id in child_ids:
                raise ValueError(f"External child reference id '{child_id}' is duplicated")
            child_ids.add(child_id)
            normalized_children.append(dict(child))
        return {"children": normalized_children, "mode": mode}

    @staticmethod
    def _normalize_child_wait_resolution(request: dict, resolution: Any) -> list[dict]:
        if not isinstance(resolution, dict) or not isinstance(resolution.get("complete"), bool):
            raise ValueError("External child resolver must return children and boolean complete")
        children = resolution.get("children")
        if not isinstance(children, list):
            raise ValueError("External child resolver must return a children list")
        expected_ids = [child["id"] for child in request["children"]]
        results_by_id = {}
        for child in children:
            if not isinstance(child, dict):
                raise ValueError("Each external child result must be a table")
            child_id = child.get("id")
            if child_id not in expected_ids:
                raise ValueError(f"External child result id '{child_id}' was not requested")
            if child_id in results_by_id:
                raise ValueError(f"External child result id '{child_id}' is duplicated")
            if not isinstance(child.get("terminal"), bool):
                raise ValueError(f"External child result '{child_id}' requires boolean terminal")
            results_by_id[child_id] = dict(child)
        missing_ids = set(expected_ids) - set(results_by_id)
        if missing_ids:
            raise ValueError(f"External child resolver omitted results for: {sorted(missing_ids)}")
        return [results_by_id[child_id] for child_id in expected_ids]

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

    def get_procedure_handle(self, procedure_id: str) -> Optional[Dict[str, Any]]:
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

    def get_subject(self) -> Optional[str]:
        """
        Return a human-readable subject line for this execution.

        Returns:
            Subject line combining procedure name and current checkpoint position
        """
        checkpoint_position = self.next_position()
        if self.procedure_name:
            return f"{self.procedure_name} (checkpoint {checkpoint_position})"
        return f"Procedure {self.procedure_id} (checkpoint {checkpoint_position})"

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

    def get_conversation_history(self) -> Optional[List[dict]]:
        """
        Return conversation history if available.

        Returns:
            List of conversation messages, or None if not tracked
        """
        # For now, return None - could be extended to track agent conversations
        # in future implementations
        return None

    def get_prior_control_interactions(self) -> Optional[List[dict]]:
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
