"""
Container execution manager for sandboxed procedure execution.

Handles spawning Docker containers, passing execution requests,
and collecting results via stdio communication.
"""

import asyncio
import logging
import os
import re
import shutil
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import SandboxConfig
from .docker_manager import DockerManager, calculate_source_hash
from .protocol import (
    ExecutionRequest,
    ExecutionResult,
    extract_result_from_stdout,
)

logger = logging.getLogger(__name__)

_CONTAINER_LOG_RE = re.compile(
    r"^(?P<asctime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) "
    r"\[(?P<level>[A-Z]+)\] "
    r"(?P<logger>[^:]+): "
    r"(?P<message>.*)$"
)

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


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

        # Parse image name and tag from config.image (e.g., "tactus-sandbox:local")
        image_parts = config.image.split(":")
        image_name = image_parts[0] if len(image_parts) > 0 else "tactus-sandbox"
        image_tag = image_parts[1] if len(image_parts) > 1 else "local"

        self.docker_manager = DockerManager(
            image_name=image_name,
            image_tag=image_tag,
        )

    def _ensure_sandbox_up_to_date(self, skip_for_ide: bool = False) -> None:
        """
        Automatically rebuild sandbox if code has changed.

        This enables fast, automatic rebuilds during development without
        requiring manual `tactus sandbox rebuild` commands. Uses source
        hash for change detection with Docker layer caching for speed.

        Can be disabled by setting TACTUS_AUTO_REBUILD_SANDBOX=false or
        when running from IDE (to avoid blocking UI).

        Args:
            skip_for_ide: If True, skip rebuild (used when called from IDE)

        Raises:
            RuntimeError: If rebuild is needed but fails.
        """
        # Skip auto-rebuild in IDE to avoid blocking UI
        if skip_for_ide:
            logger.debug("Auto-rebuild skipped for IDE execution")
            return

        # Check if auto-rebuild is disabled
        auto_rebuild = os.environ.get("TACTUS_AUTO_REBUILD_SANDBOX", "true").lower()
        if auto_rebuild not in ("true", "1", "yes"):
            logger.debug("Auto-rebuild disabled via TACTUS_AUTO_REBUILD_SANDBOX")
            return

        # Get current version and source hash
        from tactus import __version__

        # Calculate tactus root from this file's location
        # container_runner.py is in tactus/sandbox/, so root is 2 levels up
        tactus_root = Path(__file__).parent.parent.parent

        current_hash = calculate_source_hash(tactus_root)

        # Check if rebuild is needed
        if self.docker_manager.needs_rebuild(__version__, current_hash):
            logger.info("Code changes detected, rebuilding sandbox...")

            # Get paths
            dockerfile_path = tactus_root / "tactus" / "docker" / "Dockerfile"

            # Build with source hash
            success, msg = self.docker_manager.build_image(
                dockerfile_path=dockerfile_path,
                context_path=tactus_root,
                version=__version__,
                source_hash=current_hash,
                verbose=False,
            )

            if not success:
                raise RuntimeError(f"Failed to rebuild sandbox: {msg}")

            logger.info("Sandbox rebuilt successfully")
        else:
            logger.debug("Sandbox is up to date")

    def _find_tactus_source_dir(self) -> Optional[Path]:
        """
        Find the Tactus source directory for development mode.

        Searches in order:
        1. TACTUS_DEV_PATH environment variable
        2. Directory containing the tactus module (via __file__)
        3. Current working directory if it contains tactus/ subdirectory

        Returns:
            Path to Tactus repository root, or None if not found.
        """
        # Option 1: Explicit environment variable
        env_path = os.environ.get("TACTUS_DEV_PATH")
        if env_path:
            path = Path(env_path).resolve()
            if path.exists() and (path / "tactus").is_dir():
                return path

        # Option 2: Find via the tactus module location
        try:
            import tactus
            tactus_module_path = Path(tactus.__file__).resolve()
            # Go up from tactus/__init__.py to the repo root
            repo_root = tactus_module_path.parent.parent
            if (repo_root / "tactus").is_dir() and (repo_root / "pyproject.toml").exists():
                return repo_root
        except Exception:
            pass

        # Option 3: Check current working directory
        cwd = Path.cwd()
        if (cwd / "tactus").is_dir() and (cwd / "pyproject.toml").exists():
            return cwd

        return None

    def _build_docker_command(
        self,
        working_dir: Path,
        mcp_servers_path: Optional[Path] = None,
        extra_env: Optional[Dict[str, str]] = None,
        execution_id: Optional[str] = None,
        callback_url: Optional[str] = None,
        volume_base_dir: Optional[Path] = None,
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

        # Development mode: mount live Tactus source code
        if self.config.dev_mode:
            tactus_src_dir = self._find_tactus_source_dir()
            if tactus_src_dir:
                logger.info(f"[DEV MODE] Mounting live Tactus source from: {tactus_src_dir}")
                cmd.extend(["-v", f"{tactus_src_dir}/tactus:/app/tactus:ro"])
            else:
                logger.warning("[DEV MODE] Could not locate Tactus source directory, using baked-in version")

        # Additional user-configured volumes
        for volume in self.config.volumes:
            cmd.extend(["-v", self._normalize_volume_spec(volume, base_dir=volume_base_dir)])

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

    def _normalize_volume_spec(self, volume: str, base_dir: Optional[Path]) -> str:
        """
        Normalize a docker volume spec.

        Docker only accepts absolute host paths for bind mounts. For convenience,
        allow sidecar configs to use relative paths and normalize them here.

        Expected formats:
          - /abs/host:/container[:mode]
          - ./rel/host:/container[:mode]
          - ../rel/host:/container[:mode]
          - volume_name:/container[:mode]  (left unchanged)
        """
        # Basic split: host:container[:mode]
        parts = volume.split(":")
        if len(parts) < 2:
            return volume

        host = parts[0]
        container = parts[1]
        mode = parts[2] if len(parts) > 2 else None

        host_is_path = host.startswith(("/", "./", "../", "~"))
        if not host_is_path:
            # Named volume (or other special form) - leave unchanged
            return volume

        host_path = Path(host).expanduser()
        if not host_path.is_absolute():
            host_path = (base_dir or Path.cwd()) / host_path
        host_path = host_path.resolve()

        if mode:
            return f"{host_path}:{container}:{mode}"
        return f"{host_path}:{container}"

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
        # Ensure sandbox is up to date (auto-rebuild if code changed)
        # Skip for IDE to avoid blocking UI - IDE has its own rebuild mechanism
        skip_rebuild_for_ide = callback_url is not None
        self._ensure_sandbox_up_to_date(skip_for_ide=skip_rebuild_for_ide)

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

            # Resolve relative bind-mount paths in sandbox.volumes relative to the procedure file
            # when available (makes sidecar configs portable).
            volume_base_dir = None
            if source_file_path:
                try:
                    volume_base_dir = Path(source_file_path).resolve().parent
                except Exception:
                    volume_base_dir = None

            # Build docker command
            docker_cmd = self._build_docker_command(
                working_dir=working_dir,
                mcp_servers_path=mcp_path if mcp_path.exists() else None,
                execution_id=execution_id,
                callback_url=callback_url,
                volume_base_dir=volume_base_dir,
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

            self._handle_container_stderr(stderr)

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

    def _handle_container_stderr(self, stderr: str) -> None:
        """
        Forward container stderr into the host log UX.

        - raw: pass through container stderr as-is (CloudWatch-friendly)
        - rich/terminal: parse container log lines and re-emit with host formatting
        """
        if not stderr:
            return

        fmt = str(self.config.env.get("TACTUS_LOG_FORMAT", "rich")).strip().lower()

        # Raw mode: avoid double timestamps by forwarding container stderr directly.
        if fmt == "raw":
            sys.stderr.write(stderr)
            sys.stderr.flush()
            return

        # Rich/terminal: parse our container log format and re-emit.
        current: tuple[str, int, list[str]] | None = None  # (logger_name, levelno, lines)

        def flush_current() -> None:
            nonlocal current
            if current is None:
                return
            logger_name, levelno, lines = current
            message = "\n".join(lines).rstrip("\n")
            logging.getLogger(logger_name).log(levelno, message)
            current = None

        for line in stderr.splitlines():
            m = _CONTAINER_LOG_RE.match(line)
            if m:
                flush_current()
                levelno = _LEVEL_MAP.get(m.group("level"), logging.INFO)
                current = (m.group("logger"), levelno, [m.group("message")])
                continue

            # Continuation heuristic: keep multi-line LogEvent context attached.
            if current is not None and (
                line == ""
                or line.startswith((" ", "\t"))
                or line.startswith("Context:")
                or line.startswith("{")
                or line.startswith("[")
            ):
                current[2].append(line)
                continue

            # Otherwise treat as standalone stderr (warnings/tracebacks/etc).
            flush_current()
            logging.getLogger("container.stderr").warning(line)

        flush_current()

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
