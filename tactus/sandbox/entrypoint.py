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
from typing import Any, Dict, Optional

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

_log_level_str = os.environ.get("TACTUS_LOG_LEVEL", "info").strip().lower()
_log_level = _LOG_LEVELS.get(_log_level_str, logging.INFO)

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


def read_request_from_stdin() -> Optional[Dict[str, Any]]:
    """Read the execution request from stdin as JSON."""
    import json

    try:
        # Read exactly one JSON message (the initial ExecutionRequest).
        # Keep stdin open for broker responses during execution.
        input_data = sys.stdin.readline()
        if not input_data.strip():
            logger.error("No input received on stdin")
            return None

        return json.loads(input_data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from stdin: {e}")
        return None


def write_result_to_stdout(result: ExecutionResult) -> None:
    """Write the execution result to stdout with markers."""
    from tactus.sandbox.protocol import wrap_result_for_stdout

    output = wrap_result_for_stdout(result)
    sys.stdout.write(output)
    sys.stdout.flush()


async def execute_procedure(
    source: str,
    params: Dict[str, Any],
    source_file_path: Optional[str] = None,
    format: str = "lua",
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

    Returns:
        Procedure execution result
    """
    from tactus.core import TactusRuntime
    from tactus.adapters.memory import MemoryStorage
    from tactus.adapters.broker_log import BrokerLogHandler
    from tactus.adapters.http_callback_log import HTTPCallbackLogHandler
    from tactus.adapters.cost_collector_log import CostCollectorLogHandler

    # Create a unique procedure ID
    import uuid

    procedure_id = str(uuid.uuid4())

    # Prefer HTTP callbacks when configured (IDE streaming with container networking).
    log_handler = HTTPCallbackLogHandler.from_environment()
    if log_handler:
        logger.info(
            f"[SANDBOX] Using HTTP callback log handler: {os.environ.get('TACTUS_CALLBACK_URL')}"
        )
    else:
        # Otherwise, try broker socket streaming (works without container networking, e.g. stdio/UDS).
        log_handler = BrokerLogHandler.from_environment()
        if log_handler:
            logger.info(
                f"[SANDBOX] Using broker log handler: {os.environ.get('TACTUS_BROKER_SOCKET')}"
            )
        else:
            # Provide cost collection + checkpoint event handling even without IDE callbacks.
            log_handler = CostCollectorLogHandler()
            logger.info("[SANDBOX] No callback configured; using CostCollectorLogHandler")

    # Create runtime with log handler for event streaming
    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=MemoryStorage(),
        mcp_servers=None,
        external_config={},
        source_file_path=source_file_path,
        log_handler=log_handler,  # Enable event streaming to IDE
    )

    # Execute procedure
    result = await runtime.execute(
        source=source,
        context=params,
        format=format,
    )

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
        logger.info(f"Executing procedure (id={request.execution_id})")

        # Execute procedure
        proc_result = await execute_procedure(
            source=request.source,
            params=request.params,
            source_file_path=request.source_file_path,
            format=request.format,
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
        logger.exception(f"Procedure execution failed: {e}")

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
