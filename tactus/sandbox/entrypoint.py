"""
Container entrypoint for sandboxed procedure execution.

This module is run inside the Docker container. It:
1. Reads an ExecutionRequest from stdin (JSON)
2. Executes the procedure using TactusRuntime
3. Writes an ExecutionResult to stdout (JSON with markers)

Usage:
    python -m tactus.sandbox.entrypoint
"""

import asyncio
import logging
import os
import sys
import time
import traceback
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from tactus.sandbox.protocol import ExecutionResult

# Configure logging to stderr (stdout is reserved for result)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def read_request_from_stdin() -> Optional[Dict[str, Any]]:
    """Read the execution request from stdin as JSON."""
    import json

    try:
        # Read all of stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            logger.error("No input received on stdin")
            return None

        return json.loads(input_data)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from stdin: {e}")
        return None


def write_result_to_stdout(result: "ExecutionResult") -> None:
    """Write the execution result to stdout with markers."""
    from tactus.sandbox.protocol import wrap_result_for_stdout

    output = wrap_result_for_stdout(result)
    sys.stdout.write(output)
    sys.stdout.flush()


async def execute_procedure(
    source: str,
    params: Dict[str, Any],
    config: Dict[str, Any],
    mcp_servers: Dict[str, Any],
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
    from tactus.adapters.http_callback_log import HTTPCallbackLogHandler

    # Create a unique procedure ID
    import uuid

    procedure_id = str(uuid.uuid4())

    # Check for HTTP callback URL in environment (for IDE event streaming)
    log_handler = HTTPCallbackLogHandler.from_environment()
    if log_handler:
        logger.info(
            f"[SANDBOX] Using HTTP callback log handler: {os.environ.get('TACTUS_CALLBACK_URL')}"
        )

    # Create runtime with log handler for event streaming
    runtime = TactusRuntime(
        procedure_id=procedure_id,
        storage_backend=MemoryStorage(),
        mcp_servers=mcp_servers if mcp_servers else None,
        external_config=config,
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
            config=request.config,
            mcp_servers=request.mcp_servers,
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


def main() -> int:
    """Synchronous main entrypoint."""
    try:
        return asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Execution interrupted")
        return 130  # Standard interrupt exit code


if __name__ == "__main__":
    sys.exit(main())
