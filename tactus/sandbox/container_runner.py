"""
Container execution manager for sandboxed procedure execution.

Handles spawning Docker containers, passing execution requests,
and collecting results via stdio communication.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SandboxConfig
from .protocol import (
    ExecutionRequest,
    ExecutionResult,
    extract_result_from_stdout,
)

logger = logging.getLogger(__name__)


class SandboxError(Exception):
    """Raised when sandbox execution fails."""

    pass


class SandboxUnavailableError(SandboxError):
    """Raised when sandbox is required but Docker is unavailable."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(
            f"Docker sandbox unavailable: {reason}\n\n"
            "Cannot run procedure without container isolation.\n"
            "Either:\n"
            "  - Start Docker Desktop / Docker daemon\n"
            "  - Use --no-sandbox flag to explicitly run without isolation (security risk)\n"
            "  - Set sandbox.enabled: false in config to permanently disable (security risk)"
        )


class ContainerRunner:
    """
    Runs procedures inside Docker containers.

    Handles:
    - Building Docker command with appropriate mounts and env vars
    - Spawning container process
    - Communicating via stdio (stdin for request, stdout for result)
    - Streaming stderr for logs
    - Timeout handling
    """

    # Environment variables to pass through to the container
    PASSTHROUGH_ENV_VARS = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_DEFAULT_REGION",
        "AWS_SESSION_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
    ]

    def __init__(self, config: SandboxConfig):
        """
        Initialize container runner.

        Args:
            config: Sandbox configuration.
        """
        self.config = config

    def _build_docker_command(
        self,
        working_dir: Path,
        mcp_servers_path: Optional[Path] = None,
        extra_env: Optional[Dict[str, str]] = None,
        execution_id: Optional[str] = None,
        callback_url: Optional[str] = None,
    ) -> List[str]:
        """
        Build the docker run command.

        Args:
            working_dir: Host directory to mount as workspace
            mcp_servers_path: Optional path to MCP servers directory
            extra_env: Additional environment variables
            execution_id: Unique execution ID for container naming
            callback_url: Optional callback URL for event streaming to IDE

        Returns:
            List of command arguments for subprocess.
        """
        import platform

        # Generate container name: tactus-sandbox-{execution_id}
        container_name = (
            f"tactus-sandbox-{execution_id}"
            if execution_id
            else f"tactus-sandbox-{uuid.uuid4().hex[:8]}"
        )

        cmd = [
            "docker",
            "run",
            "--rm",  # Remove container after exit
            "-i",  # Interactive (keep stdin open)
            "--name",
            container_name,
        ]

        # Platform-specific networking for callback URL support
        if callback_url:
            system = platform.system()
            if system in ("Darwin", "Windows"):
                # macOS/Windows: Use host.docker.internal to reach host
                cmd.extend(["--add-host", "host.docker.internal:host-gateway"])
                cmd.extend(["--network", self.config.network])
            else:
                # Linux: Use host network mode for direct localhost access
                cmd.extend(["--network", "host"])
        else:
            cmd.extend(["--network", self.config.network])

        # Resource limits
        if self.config.limits.memory:
            cmd.extend(["--memory", self.config.limits.memory])
        if self.config.limits.cpus:
            cmd.extend(["--cpus", self.config.limits.cpus])

        # Mount working directory
        cmd.extend(["-v", f"{working_dir}:/workspace:rw"])

        # Mount MCP servers if available
        if mcp_servers_path and mcp_servers_path.exists():
            cmd.extend(["-v", f"{mcp_servers_path}:/mcp-servers:ro"])

        # Additional user-configured volumes
        for volume in self.config.volumes:
            cmd.extend(["-v", volume])

        # Pass through environment variables
        for var_name in self.PASSTHROUGH_ENV_VARS:
            value = os.environ.get(var_name)
            if value:
                cmd.extend(["--env", f"{var_name}={value}"])

        # User-configured additional env vars
        for key, value in self.config.env.items():
            cmd.extend(["--env", f"{key}={value}"])

        # Extra env vars for this run
        if extra_env:
            for key, value in extra_env.items():
                cmd.extend(["--env", f"{key}={value}"])

        # Add callback URL as environment variable for event streaming
        if callback_url:
            cmd.extend(["--env", f"TACTUS_CALLBACK_URL={callback_url}"])

        # Working directory inside container
        cmd.extend(["-w", "/workspace"])

        # Image name
        cmd.append(self.config.image)

        return cmd

    async def run(
        self,
        source: str,
        params: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        working_dir: Optional[Path] = None,
        format: str = "lua",
        callback_url: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a procedure in a sandboxed container.

        Args:
            source: Procedure source code (.tac content)
            params: Input parameters for the procedure
            config: Runtime configuration overrides
            mcp_servers: MCP server configurations
            source_file_path: Original source file path (for error messages)
            working_dir: Working directory to use (default: temp directory)
            format: Source format ("lua" for .tac files, "yaml" for legacy)
            callback_url: Optional callback URL for event streaming to IDE

        Returns:
            ExecutionResult with status, result/error, and metadata.
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Create temporary workspace if not provided
        temp_dir = None
        if working_dir is None:
            temp_dir = tempfile.mkdtemp(prefix="tactus-sandbox-")
            working_dir = Path(temp_dir)

            # If we have a source file, copy its directory contents
            if source_file_path:
                src_dir = Path(source_file_path).parent
                if src_dir.exists():
                    for item in src_dir.iterdir():
                        if item.is_file():
                            shutil.copy2(item, working_dir / item.name)
                        elif item.is_dir() and not item.name.startswith("."):
                            shutil.copytree(item, working_dir / item.name)

        try:
            # Get MCP servers path
            mcp_path = self.config.get_mcp_servers_path()

            # Build docker command
            docker_cmd = self._build_docker_command(
                working_dir=working_dir,
                mcp_servers_path=mcp_path if mcp_path.exists() else None,
                execution_id=execution_id,
                callback_url=callback_url,
            )

            logger.debug(f"Docker command: {' '.join(docker_cmd)}")

            # Create execution request
            request = ExecutionRequest(
                source=source,
                working_dir="/workspace",
                params=params or {},
                config=config or {},
                mcp_servers=mcp_servers or {},
                execution_id=execution_id,
                source_file_path=source_file_path,
                format=format,
            )

            # Run container
            result = await self._run_container(
                docker_cmd,
                request,
                timeout=self.config.timeout,
            )

            result.duration_seconds = time.time() - start_time
            return result

        except asyncio.TimeoutError:
            return ExecutionResult.timeout(
                duration_seconds=time.time() - start_time,
            )
        except Exception as e:
            logger.exception(f"Sandbox execution failed: {e}")
            return ExecutionResult.failure(
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=time.time() - start_time,
            )
        finally:
            # Cleanup temp directory
            if temp_dir:
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")

    async def _run_container(
        self,
        docker_cmd: List[str],
        request: ExecutionRequest,
        timeout: int,
    ) -> ExecutionResult:
        """
        Run the container and communicate via stdio.

        Args:
            docker_cmd: Docker command to execute
            request: Execution request to send
            timeout: Timeout in seconds

        Returns:
            ExecutionResult from container.
        """
        # Start container process
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Send request via stdin, collect output
            request_json = request.to_json()
            stdout_data, stderr_data = await asyncio.wait_for(
                process.communicate(input=request_json.encode()),
                timeout=timeout,
            )

            stdout = stdout_data.decode("utf-8", errors="replace")
            stderr = stderr_data.decode("utf-8", errors="replace")

            # Log stderr (container logs)
            if stderr:
                for line in stderr.strip().split("\n"):
                    logger.info(f"[container] {line}")

            # Extract result from stdout
            result = extract_result_from_stdout(stdout)
            if result:
                return result

            # No structured result found - check exit code
            if process.returncode == 0:
                # Success but no structured output - treat stdout as result
                return ExecutionResult.success(
                    result=stdout.strip() if stdout.strip() else None,
                )
            elif process.returncode == 137:
                # Exit code 137 = killed by OOM (128 + SIGKILL=9)
                return ExecutionResult.failure(
                    error=f"Container killed: out of memory (limit: {self.config.limits.memory})",
                    error_type="OutOfMemoryError",
                    exit_code=137,
                )
            elif process.returncode == 124:
                # Exit code 124 = timeout
                return ExecutionResult.failure(
                    error=f"Container killed: execution timeout ({self.config.timeout}s)",
                    error_type="TimeoutError",
                    exit_code=124,
                )
            else:
                # Failed without structured output
                return ExecutionResult.failure(
                    error=stderr.strip()
                    or stdout.strip()
                    or f"Container exited with code {process.returncode}",
                    exit_code=process.returncode or 1,
                )

        except asyncio.TimeoutError:
            # Kill the container
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
            raise

    def run_sync(
        self,
        source: str,
        params: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        mcp_servers: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        working_dir: Optional[Path] = None,
        format: str = "lua",
        callback_url: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Synchronous wrapper for run().

        For use in non-async contexts.
        """
        return asyncio.run(
            self.run(
                source=source,
                params=params,
                config=config,
                mcp_servers=mcp_servers,
                source_file_path=source_file_path,
                format=format,
                working_dir=working_dir,
                callback_url=callback_url,
            )
        )
