"""
Procedure Primitive - Enables procedure invocation and composition.

Provides Procedure.run() for synchronous invocation and Procedure.spawn()
for async invocation, along with status tracking and waiting.
"""

import logging
import uuid
import asyncio
import threading
from typing import Any, Optional, Dict, List, Callable
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ProcedureHandle:
    """Handle for tracking async procedure execution."""

    procedure_id: str
    name: str
    status: str = "running"  # "running", "completed", "failed", "waiting"
    result: Any = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Lua access."""
        return {
            "procedure_id": self.procedure_id,
            "name": self.name,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class ProcedureExecutionError(Exception):
    """Raised when a procedure execution fails."""

    pass


class ProcedureRecursionError(Exception):
    """Raised when recursion depth is exceeded."""

    pass


class ProcedurePrimitive:
    """
    Primitive for invoking other procedures.

    Supports both synchronous and asynchronous invocation,
    enabling procedure composition and recursion.

    Example usage (Lua):
        -- Synchronous
        local result = Procedure.run("researcher", {query = "AI"})

        -- Asynchronous
        local handle = Procedure.spawn("researcher", {query = "AI"})
        local status = Procedure.status(handle)
        local result = Procedure.wait(handle)
    """

    def __init__(
        self,
        execution_context: Any,
        runtime_factory: Callable[[str, Dict[str, Any]], Any],
        max_depth: int = 5,
        current_depth: int = 0,
    ):
        """
        Initialize procedure primitive.

        Args:
            execution_context: Execution context for state management
            runtime_factory: Factory function to create TactusRuntime instances
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
        """
        self.execution_context = execution_context
        self.runtime_factory = runtime_factory
        self.max_depth = max_depth
        self.current_depth = current_depth
        self.handles: Dict[str, ProcedureHandle] = {}
        self._lock = threading.Lock()

        logger.info(f"ProcedurePrimitive initialized (depth {current_depth}/{max_depth})")

    def run(self, name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Synchronous procedure invocation with auto-checkpointing.

        Sub-procedure calls are automatically checkpointed for durability.
        On replay, the cached result is returned without re-executing.

        Args:
            name: Procedure name or file path
            params: Parameters to pass to the procedure

        Returns:
            Procedure result

        Raises:
            ProcedureRecursionError: If recursion depth exceeded
            ProcedureExecutionError: If procedure execution fails
        """
        # Check recursion depth
        if self.current_depth >= self.max_depth:
            raise ProcedureRecursionError(f"Maximum recursion depth ({self.max_depth}) exceeded")

        logger.info(f"Running procedure '{name}' synchronously (depth {self.current_depth})")

        # Normalize params
        params = params or {}

        # Wrap execution in checkpoint for durability
        def execute_procedure():
            try:
                # Load procedure source
                source = self._load_procedure_source(name)

                # Create runtime for sub-procedure
                runtime = self.runtime_factory(name, params)

                # Execute synchronously (runtime.execute is async, so we need to run it)
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    # We're already in an async context, use run_until_complete would fail
                    # Instead, we need to await it, but we're in a sync function
                    # Solution: Create a task and wait for it
                    result = asyncio.create_task(
                        runtime.execute(source=source, context=params, format="lua")
                    )
                    # This won't work in sync context - we need to handle this differently
                    # For now, use run_until_complete in a new loop
                    raise RuntimeError("Cannot run nested async in sync context")
                except RuntimeError:
                    # No running loop or nested loop issue - create new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        runtime.execute(source=source, context=params, format="lua")
                    )
                    loop.close()

                # Extract result from execution response
                if result.get("success"):
                    logger.info(f"Procedure '{name}' completed successfully")
                    return result.get("result")
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.error(f"Procedure '{name}' failed: {error_msg}")
                    raise ProcedureExecutionError(f"Procedure '{name}' failed: {error_msg}")

            except ProcedureExecutionError:
                raise
            except ProcedureRecursionError:
                raise
            except Exception as e:
                logger.error(f"Error executing procedure '{name}': {e}")
                raise ProcedureExecutionError(f"Failed to execute procedure '{name}': {e}")

        # Auto-checkpoint sub-procedure call
        return self.execution_context.checkpoint(execute_procedure, "procedure_call")

    def spawn(self, name: str, params: Optional[Dict[str, Any]] = None) -> ProcedureHandle:
        """
        Async procedure invocation.

        Args:
            name: Procedure name or file path
            params: Parameters to pass to the procedure

        Returns:
            Handle for tracking execution

        Raises:
            ProcedureRecursionError: If recursion depth exceeded
        """
        # Check recursion depth
        if self.current_depth >= self.max_depth:
            raise ProcedureRecursionError(f"Maximum recursion depth ({self.max_depth}) exceeded")

        # Create handle
        procedure_id = str(uuid.uuid4())
        handle = ProcedureHandle(procedure_id=procedure_id, name=name, status="running")

        # Store handle
        with self._lock:
            self.handles[procedure_id] = handle

        logger.info(f"Spawning procedure '{name}' asynchronously (id: {procedure_id})")

        # Start async execution in thread
        params = params or {}
        thread = threading.Thread(
            target=self._execute_async, args=(handle, name, params), daemon=True
        )
        handle.thread = thread
        thread.start()

        return handle

    def _execute_async(self, handle: ProcedureHandle, name: str, params: Dict[str, Any]):
        """Execute procedure asynchronously in background thread."""
        try:
            # Load procedure source
            source = self._load_procedure_source(name)

            # Create runtime for sub-procedure
            runtime = self.runtime_factory(name, params)

            # Execute in new event loop (thread-safe)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            result = loop.run_until_complete(
                runtime.execute(source=source, context=params, format="lua")
            )

            loop.close()

            # Update handle
            with self._lock:
                if result.get("success"):
                    handle.status = "completed"
                    handle.result = result.get("result")
                    logger.info(f"Async procedure '{name}' completed (id: {handle.procedure_id})")
                else:
                    handle.status = "failed"
                    handle.error = result.get("error", "Unknown error")
                    logger.error(f"Async procedure '{name}' failed: {handle.error}")

                handle.completed_at = datetime.now()

        except Exception as e:
            logger.error(f"Error in async procedure '{name}': {e}")
            with self._lock:
                handle.status = "failed"
                handle.error = str(e)
                handle.completed_at = datetime.now()

    def status(self, handle: ProcedureHandle) -> Dict[str, Any]:
        """
        Get procedure status.

        Args:
            handle: Procedure handle

        Returns:
            Status dictionary
        """
        with self._lock:
            return handle.to_dict()

    def wait(self, handle: ProcedureHandle, timeout: Optional[float] = None) -> Any:
        """
        Wait for procedure completion.

        Args:
            handle: Procedure handle
            timeout: Optional timeout in seconds

        Returns:
            Procedure result

        Raises:
            ProcedureExecutionError: If procedure failed
            TimeoutError: If timeout exceeded
        """
        logger.debug(f"Waiting for procedure {handle.procedure_id}")

        # Wait for thread to complete
        if handle.thread:
            handle.thread.join(timeout=timeout)

            # Check if still running (timeout)
            if handle.thread.is_alive():
                raise TimeoutError(f"Procedure {handle.name} timed out after {timeout}s")

        # Check final status
        with self._lock:
            if handle.status == "failed":
                raise ProcedureExecutionError(f"Procedure {handle.name} failed: {handle.error}")
            elif handle.status == "completed":
                return handle.result
            else:
                raise ProcedureExecutionError(
                    f"Procedure {handle.name} in unexpected state: {handle.status}"
                )

    def inject(self, handle: ProcedureHandle, message: str):
        """
        Inject guidance message into running procedure.

        Args:
            handle: Procedure handle
            message: Message to inject

        Note: This is a placeholder - full implementation requires
        communication channel with running procedure.
        """
        logger.warning(f"Procedure.inject() not fully implemented - message ignored: {message}")
        # TODO: Implement message injection mechanism

    def cancel(self, handle: ProcedureHandle):
        """
        Cancel running procedure.

        Args:
            handle: Procedure handle

        Note: Python threads cannot be forcefully cancelled,
        so this just marks the status.
        """
        logger.info(f"Cancelling procedure {handle.procedure_id}")

        with self._lock:
            handle.status = "cancelled"
            handle.completed_at = datetime.now()

        # Note: Thread will continue running but result will be ignored

    def wait_any(self, handles: List[ProcedureHandle]) -> ProcedureHandle:
        """
        Wait for first completion.

        Args:
            handles: List of procedure handles

        Returns:
            First completed handle
        """
        logger.debug(f"Waiting for any of {len(handles)} procedures")

        while True:
            # Check if any completed
            with self._lock:
                for handle in handles:
                    if handle.status in ("completed", "failed", "cancelled"):
                        return handle

            # Sleep briefly before checking again
            import time

            time.sleep(0.1)

    def wait_all(self, handles: List[ProcedureHandle]) -> List[Any]:
        """
        Wait for all completions.

        Args:
            handles: List of procedure handles

        Returns:
            List of results
        """
        logger.debug(f"Waiting for all {len(handles)} procedures")

        results = []
        for handle in handles:
            result = self.wait(handle)
            results.append(result)

        return results

    def is_complete(self, handle: ProcedureHandle) -> bool:
        """
        Check if procedure is complete.

        Args:
            handle: Procedure handle

        Returns:
            True if completed (success or failure)
        """
        with self._lock:
            return handle.status in ("completed", "failed", "cancelled")

    def all_complete(self, handles: List[ProcedureHandle]) -> bool:
        """
        Check if all procedures are complete.

        Args:
            handles: List of procedure handles

        Returns:
            True if all completed
        """
        return all(self.is_complete(handle) for handle in handles)

    def _load_procedure_source(self, name: str) -> str:
        """
        Load procedure source code by name.

        Args:
            name: Procedure name or file path

        Returns:
            Procedure source code

        Raises:
            FileNotFoundError: If procedure file not found
        """
        import os

        # Try different locations
        search_paths = [
            name,  # Exact path
            f"{name}.tac",  # Add extension
            f"examples/{name}",  # Examples directory
            f"examples/{name}.tac",  # Examples with extension
        ]

        for path in search_paths:
            if os.path.exists(path):
                logger.debug(f"Loading procedure from: {path}")
                with open(path, "r") as f:
                    return f.read()

        raise FileNotFoundError(f"Procedure '{name}' not found. Searched: {search_paths}")
