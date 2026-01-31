"""
Procedure Primitive - Enables procedure invocation and composition.

Provides Procedure.run() for synchronous invocation and Procedure.spawn()
for async invocation, along with status tracking and waiting.
"""

import logging
import uuid
import asyncio
import threading
from typing import Any, Optional, Callable
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

    def to_dict(self) -> dict[str, Any]:
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
        runtime_factory: Callable[[str, dict[str, Any]], Any],
        lua_sandbox: Any = None,
        max_depth: int = 5,
        current_depth: int = 0,
    ):
        """
        Initialize procedure primitive.

        Args:
            execution_context: Execution context for state management
            runtime_factory: Factory function to create TactusRuntime instances
            lua_sandbox: LuaSandbox instance for in-file procedure lookup
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth
        """
        self.execution_context = execution_context
        self.runtime_factory = runtime_factory
        self.lua_sandbox = lua_sandbox
        self.max_depth = max_depth
        self.current_depth = current_depth
        self.handles: dict[str, ProcedureHandle] = {}
        self._lock = threading.Lock()

        logger.info(
            "ProcedurePrimitive initialized (depth %s/%s)",
            current_depth,
            max_depth,
        )

    def __call__(self, name: str) -> Any:
        """
        Look up an in-file named procedure by name.

        Enables Lua syntax:
            local res = Procedure("my_proc")({ ... })

        Named procedures are injected into Lua globals by the runtime during initialization.
        """
        if not self.lua_sandbox or not hasattr(self.lua_sandbox, "lua"):
            raise ProcedureExecutionError("Procedure lookup is not available (lua_sandbox missing)")

        try:
            procedure_callable = self.lua_sandbox.lua.globals()[name]
        except Exception:
            procedure_callable = None

        if procedure_callable is None:
            raise ProcedureExecutionError(f"Named procedure '{name}' not found")

        return procedure_callable

    def run(self, name: str, params: Optional[dict[str, Any]] = None) -> Any:
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

        logger.info(
            "Running procedure '%s' synchronously (depth %s)",
            name,
            self.current_depth,
        )

        # Normalize params
        procedure_params = params or {}
        if hasattr(procedure_params, "items"):
            from tactus.core.dsl_stubs import lua_table_to_dict

            procedure_params = lua_table_to_dict(procedure_params)
            if isinstance(procedure_params, list) and len(procedure_params) == 0:
                procedure_params = {}

        # Wrap execution in checkpoint for durability
        def execute_procedure():
            try:
                # Load procedure source
                source = self._load_procedure_source(name)

                # Create runtime for sub-procedure
                runtime = self.runtime_factory(name, procedure_params)

                # Execute synchronously (runtime.execute is async, so we need to run it)
                async def run_subprocedure():
                    return await runtime.execute(
                        source=source, context=procedure_params, format="lua"
                    )

                try:
                    asyncio.get_running_loop()
                    has_running_loop = True
                except RuntimeError:
                    has_running_loop = False

                if has_running_loop:
                    result_holder: dict[str, Any] = {}
                    error_holder: dict[str, Exception] = {}

                    def run_in_thread():
                        try:
                            result_holder["result"] = asyncio.run(run_subprocedure())
                        except Exception as error:
                            error_holder["error"] = error

                    worker_thread = threading.Thread(target=run_in_thread, daemon=True)
                    worker_thread.start()
                    worker_thread.join()

                    if "error" in error_holder:
                        raise error_holder["error"]

                    result = result_holder.get("result")
                else:
                    result = asyncio.run(run_subprocedure())

                # Extract result from execution response
                if result.get("success"):
                    logger.info("Procedure '%s' completed successfully", name)
                    return result.get("result")
                else:
                    error_msg = result.get("error", "Unknown error")
                    logger.error("Procedure '%s' failed: %s", name, error_msg)
                    raise ProcedureExecutionError(f"Procedure '{name}' failed: {error_msg}")

            except ProcedureExecutionError:
                raise
            except ProcedureRecursionError:
                raise
            except Exception as error:
                logger.error("Error executing procedure '%s': %s", name, error)
                raise ProcedureExecutionError(f"Failed to execute procedure '{name}': {error}")

        # Auto-checkpoint sub-procedure call
        # Try to capture Lua source location if available
        source_info = None

        try:
            # Get debug.getinfo function from Lua globals
            lua_globals = self.lua_sandbox.lua.globals()
            if hasattr(lua_globals, "debug") and hasattr(lua_globals.debug, "getinfo"):
                # Try different stack levels to find the Lua caller
                debug_info = None
                for level in [1, 2, 3, 4]:
                    try:
                        info = lua_globals.debug.getinfo(level, "Sl")
                        if info:
                            lua_debug_info = dict(info.items()) if hasattr(info, "items") else {}
                            source = lua_debug_info.get("source", "")
                            line = lua_debug_info.get("currentline", -1)
                            # Look for a valid source location (not -1, not C function, not internal)
                            if (
                                line > 0
                                and source
                                and not source.startswith("=[C]")
                                and not source.startswith("[string")
                            ):
                                debug_info = lua_debug_info
                                break
                    except Exception:
                        continue

                if debug_info:
                    source_info = {
                        "file": self.execution_context.current_tac_file
                        or debug_info.get("source", "unknown"),
                        "line": debug_info.get("currentline", 0),
                        "function": debug_info.get("name", name),
                    }
        except Exception:
            pass

        # If we still don't have source_info, use fallback
        if not source_info:
            import inspect

            current_frame = inspect.currentframe()
            if current_frame and current_frame.f_back:
                caller_frame = current_frame.f_back
                # Use .tac file if available, otherwise use Python file
                source_info = {
                    "file": self.execution_context.current_tac_file
                    or caller_frame.f_code.co_filename,
                    "line": 0,  # Line number unknown without Lua debug
                    "function": name,
                }

        return self.execution_context.checkpoint(
            execute_procedure, "procedure_call", source_info=source_info
        )

    def spawn(self, name: str, params: Optional[dict[str, Any]] = None) -> ProcedureHandle:
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

        logger.info(
            "Spawning procedure '%s' asynchronously (id: %s)",
            name,
            procedure_id,
        )

        # Start async execution in thread
        procedure_params = params or {}
        thread = threading.Thread(
            target=self._execute_async, args=(handle, name, procedure_params), daemon=True
        )
        handle.thread = thread
        thread.start()

        return handle

    def _execute_async(self, handle: ProcedureHandle, name: str, params: dict[str, Any]):
        """Execute procedure asynchronously in background thread."""
        try:
            # Load procedure source
            source = self._load_procedure_source(name)

            # Create runtime for sub-procedure
            runtime = self.runtime_factory(name, params)

            # Execute in new event loop (thread-safe)
            event_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(event_loop)

            result = event_loop.run_until_complete(
                runtime.execute(source=source, context=params, format="lua")
            )

            event_loop.close()

            # Update handle
            with self._lock:
                if result.get("success"):
                    handle.status = "completed"
                    handle.result = result.get("result")
                    logger.info(
                        "Async procedure '%s' completed (id: %s)",
                        name,
                        handle.procedure_id,
                    )
                else:
                    handle.status = "failed"
                    handle.error = result.get("error", "Unknown error")
                    logger.error(
                        "Async procedure '%s' failed: %s",
                        name,
                        handle.error,
                    )

                handle.completed_at = datetime.now()

        except Exception as error:
            logger.error("Error in async procedure '%s': %s", name, error)
            with self._lock:
                handle.status = "failed"
                handle.error = str(error)
                handle.completed_at = datetime.now()

    def status(self, handle: ProcedureHandle) -> dict[str, Any]:
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
        logger.debug("Waiting for procedure %s", handle.procedure_id)

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
        logger.warning(
            "Procedure.inject() not fully implemented - message ignored: %s",
            message,
        )
        # TODO: Implement message injection mechanism

    def cancel(self, handle: ProcedureHandle):
        """
        Cancel running procedure.

        Args:
            handle: Procedure handle

        Note: Python threads cannot be forcefully cancelled,
        so this just marks the status.
        """
        logger.info("Cancelling procedure %s", handle.procedure_id)

        with self._lock:
            handle.status = "cancelled"
            handle.completed_at = datetime.now()

        # Note: Thread will continue running but result will be ignored

    def wait_any(self, handles: list[ProcedureHandle]) -> ProcedureHandle:
        """
        Wait for first completion.

        Args:
            handles: List of procedure handles

        Returns:
            First completed handle
        """
        logger.debug("Waiting for any of %s procedures", len(handles))

        while True:
            # Check if any completed
            with self._lock:
                for handle in handles:
                    if handle.status in ("completed", "failed", "cancelled"):
                        return handle

            # Sleep briefly before checking again
            import time

            time.sleep(0.1)

    def wait_all(self, handles: list[ProcedureHandle]) -> list[Any]:
        """
        Wait for all completions.

        Args:
            handles: List of procedure handles

        Returns:
            List of results
        """
        logger.debug("Waiting for all %s procedures", len(handles))

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

    def all_complete(self, handles: list[ProcedureHandle]) -> bool:
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
        from pathlib import Path

        search_paths: list[Path] = []
        seen: set[Path] = set()

        def add_path(path: Path) -> None:
            normalized = path.resolve() if path.is_absolute() else path
            if normalized in seen:
                return
            seen.add(normalized)
            search_paths.append(path)

        name_path = Path(name)

        def add_candidates(base: Path | None, rel: Path) -> None:
            candidate = (base / rel) if base is not None else rel
            add_path(candidate)
            if candidate.suffix != ".tac":
                add_path(Path(str(candidate) + ".tac"))

        # Absolute path: try as-is.
        if name_path.is_absolute():
            add_candidates(None, name_path)
        else:
            # Relative to current working directory (CLI usage).
            add_candidates(None, name_path)

            # Relative to the current .tac file directory and its parents (BDD/temp cwd usage).
            current_tac_file = getattr(self.execution_context, "current_tac_file", None)
            if current_tac_file:
                current_dir = Path(current_tac_file).parent
                add_candidates(current_dir, name_path)

                # Also try resolving from parent directories (helps when callers pass paths
                # relative to project root, but cwd is not the project root).
                for parent in list(current_dir.parents)[:5]:
                    add_candidates(parent, name_path)

            # Fallback: examples directory relative to repo root in common layouts.
            add_candidates(None, Path("examples") / name_path)

        for path in search_paths:
            try:
                if path.exists() and path.is_file():
                    logger.debug("Loading procedure from: %s", path)
                    return path.read_text()
            except Exception:
                continue

        searched = [str(p) for p in search_paths]
        raise FileNotFoundError(f"Procedure '{name}' not found. Searched: {searched}")
