"""
Container entrypoint for sandboxed procedure execution.

This module is run inside the Docker container. It:
1. Reads an ExecutionRequest from stdin (JSON)
2. Executes the procedure using TactusRuntime
3. Writes an ExecutionResult to stdout (JSON with markers)

Usage:
    python -m tactus.sandbox.entrypoint
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import traceback
from typing import Any, Optional

from tactus.sandbox.protocol import ExecutionResult

# Configure logging to stderr (stdout is reserved for result)
_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

_log_level_name = os.environ.get("TACTUS_LOG_LEVEL", "info").strip().lower()
_log_level = _LOG_LEVELS.get(_log_level_name, logging.INFO)

# CloudWatch-friendly, one line per record.
_log_fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

logging.basicConfig(
    level=_log_level,
    format=_log_fmt,
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Keep container stderr focused on procedure logs by default.
# Use `TACTUS_LOG_LEVEL=debug` to include internal runtime logs.
if _log_level > logging.DEBUG:
    logging.getLogger("tactus.core").setLevel(logging.WARNING)
    logging.getLogger("tactus.primitives").setLevel(logging.WARNING)
    logging.getLogger("tactus.stdlib").setLevel(logging.WARNING)


def read_request_from_stdin() -> Optional[dict[str, Any]]:
    """Read the execution request from stdin as JSON."""
    import json

    try:
        # Read exactly one JSON message (the initial ExecutionRequest).
        # Keep stdin open for broker responses during execution.
        input_line = sys.stdin.readline()
        if not input_line.strip():
            logger.error("No input received on stdin")
            return None

        return json.loads(input_line)
    except json.JSONDecodeError as error:
        logger.error("Failed to parse JSON from stdin: %s", error)
        return None


def write_result_to_stdout(result: ExecutionResult) -> None:
    """Write the execution result to stdout with markers."""
    from tactus.sandbox.protocol import wrap_result_for_stdout

    output = wrap_result_for_stdout(result)
    sys.stdout.write(output)
    sys.stdout.flush()


async def execute_procedure(
    source: str,
    params: dict[str, Any],
    source_file_path: Optional[str] = None,
    format: str = "lua",
    run_id: Optional[str] = None,
) -> Any:
    """
    Execute a procedure using TactusRuntime.

    Args:
        source: Procedure source code
        params: Input parameters
        config: Runtime configuration
        mcp_servers: MCP server configurations
        source_file_path: Original source file path
        format: Source format ("lua" or "yaml")
        run_id: Run ID for checkpoint isolation

    Returns:
        Procedure execution result
    """
    from tactus.core import TactusRuntime
    from tactus.adapters.memory import MemoryStorage
    from tactus.adapters.broker_log import BrokerLogHandler
    from tactus.adapters.http_callback_log import HTTPCallbackLogHandler
    from tactus.adapters.cost_collector_log import CostCollectorLogHandler
    from tactus.adapters.channels.broker import BrokerControlChannel

    # Create a unique procedure ID
    import uuid

    procedure_id = str(uuid.uuid4())

    # Prefer HTTP callbacks when configured (IDE streaming with container networking).
    log_handler = HTTPCallbackLogHandler.from_environment()
    if log_handler:
        logger.info(
            "[SANDBOX] Using HTTP callback log handler: %s",
            os.environ.get("TACTUS_CALLBACK_URL"),
        )
    else:
        # Otherwise, try broker socket streaming (works without container networking, e.g. stdio/UDS).
        log_handler = BrokerLogHandler.from_environment()
        if log_handler:
            logger.info(
                "[SANDBOX] Using broker log handler: %s",
                os.environ.get("TACTUS_BROKER_SOCKET"),
            )
        else:
            # Provide cost collection + checkpoint event handling even without IDE callbacks.
            log_handler = CostCollectorLogHandler()
            logger.info("[SANDBOX] No callback configured; using CostCollectorLogHandler")

    # Set up HITL control channel (broker-based in container mode)
    broker_channel = BrokerControlChannel.from_environment()
    hitl_handler = None
    if broker_channel:
        from tactus.adapters.control_loop import ControlLoopHandler, ControlLoopHITLAdapter

        control_handler = ControlLoopHandler(channels=[broker_channel])
        hitl_handler = ControlLoopHITLAdapter(control_handler)
        logger.info("[SANDBOX] Using broker control channel for HITL")
    else:
        logger.debug("[SANDBOX] No broker control channel available, HITL disabled")

    # Create runtime with log handler for event streaming
    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=MemoryStorage(),
        mcp_servers=None,
        external_config={},
        source_file_path=source_file_path,
        log_handler=log_handler,  # Enable event streaming to IDE
        hitl_handler=hitl_handler,  # Enable HITL control channel
        run_id=run_id,  # Pass run_id for checkpoint isolation
    )

    # Execute procedure
    result = await runtime.execute(
        source=source,
        context=params,
        format=format,
    )

    # CRITICAL: Flush pending log events before returning
    # This ensures all streaming events reach the broker before container exits.
    # Without this, fire-and-forget async tasks may be discarded.
    if hasattr(log_handler, "flush"):
        logger.info("[SANDBOX] Flushing pending log events...")
        await log_handler.flush()
        logger.info("[SANDBOX] Log events flushed")

    return result


async def main_async() -> int:
    """Main async entrypoint."""
    from tactus.sandbox.protocol import (
        ExecutionRequest,
        ExecutionResult,
    )

    start_time = time.time()

    # Read request from stdin
    request_data = read_request_from_stdin()
    if request_data is None:
        result = ExecutionResult.failure(
            error="Failed to read execution request from stdin",
            error_type="InputError",
        )
        write_result_to_stdout(result)
        return 1

    try:
        # Parse request
        request = ExecutionRequest(**request_data)
        logger.info("Executing procedure (id=%s)", request.execution_id)

        # Execute procedure
        proc_result = await execute_procedure(
            source=request.source,
            params=request.params,
            source_file_path=request.source_file_path,
            format=request.format,
            run_id=request.run_id,
        )

        # Create success result
        duration = time.time() - start_time
        result = ExecutionResult.success(
            result=proc_result,
            duration_seconds=duration,
        )

        write_result_to_stdout(result)
        return 0

    except Exception as e:
        logger.exception("Procedure execution failed: %s", e)

        duration = time.time() - start_time
        result = ExecutionResult.failure(
            error=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc(),
            duration_seconds=duration,
        )

        write_result_to_stdout(result)
        return 1
    finally:
        # Ensure stdio broker transport is closed cleanly to avoid pending-task warnings.
        try:
            from tactus.broker.client import close_stdio_transport

            await close_stdio_transport()
        except Exception:
            pass


def main() -> int:
    """Synchronous main entrypoint."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Execution interrupted")
        return 130  # Standard interrupt exit code


if __name__ == "__main__":
    sys.exit(main())
