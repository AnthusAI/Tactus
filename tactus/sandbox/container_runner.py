"""
Container execution manager for sandboxed procedure execution.

Handles spawning Docker containers, passing execution requests,
and collecting results via stdio communication.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import ssl
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import SandboxConfig
from .docker_manager import (
    DockerManager,
    calculate_source_hash,
    resolve_dockerfile_path,
)
from .protocol import (
    ExecutionRequest,
    ExecutionResult,
    RESULT_END_MARKER,
    RESULT_START_MARKER,
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

    _BLOCKED_CONTAINER_ENV_KEYS = {
        # Keep sandbox containers secretless by default.
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AZURE_OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
    }

    def __init__(self, config: SandboxConfig):
        """
        Initialize container runner.

        Args:
            config: Sandbox configuration.
        """
        self.config = config

        # Parse image name and tag from config.image (e.g., "tactus-sandbox:local").
        image_name_parts = config.image.split(":")
        image_name = image_name_parts[0] if len(image_name_parts) > 0 else "tactus-sandbox"
        image_tag = image_name_parts[1] if len(image_name_parts) > 1 else "local"

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
        auto_rebuild_env_value = os.environ.get("TACTUS_AUTO_REBUILD_SANDBOX", "true").lower()
        auto_rebuild_enabled = auto_rebuild_env_value in ("true", "1", "yes")
        if not auto_rebuild_enabled:
            logger.debug("Auto-rebuild disabled via TACTUS_AUTO_REBUILD_SANDBOX")
            return

        # Get current version and source hash
        from tactus import __version__

        # Calculate tactus root from this file's location
        # container_runner.py is in tactus/sandbox/, so root is 2 levels up
        tactus_root = Path(__file__).parent.parent.parent

        dockerfile_path, build_mode = resolve_dockerfile_path(tactus_root)
        current_hash = None
        if build_mode == "source":
            current_hash = calculate_source_hash(tactus_root)
        else:
            logger.info("[SANDBOX] No source tree detected, using PyPI-based sandbox image build")

        # Check if rebuild is needed
        if self.docker_manager.needs_rebuild(__version__, current_hash):
            logger.info("Sandbox image missing or outdated, rebuilding...")

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
        Returns:
            List of command arguments for subprocess.
        """
        # Generate container name: tactus-sandbox-{execution_id}
        container_name = (
            f"tactus-sandbox-{execution_id}"
            if execution_id
            else f"tactus-sandbox-{uuid.uuid4().hex[:8]}"
        )

        docker_command = [
            "docker",
            "run",
            "--rm",  # Remove container after exit
            "-i",  # Interactive (keep stdin open)
            "--name",
            container_name,
        ]

        docker_command.extend(["--network", self.config.network])

        # Resource limits
        if self.config.limits.memory:
            docker_command.extend(["--memory", self.config.limits.memory])
        if self.config.limits.cpus:
            docker_command.extend(["--cpus", self.config.limits.cpus])

        # Working directory mount is handled by SandboxConfig.add_default_volumes()
        # which adds ".:/workspace:rw" to config.volumes (unless mount_current_dir=False)

        # Mount MCP servers if available
        if mcp_servers_path and mcp_servers_path.exists():
            docker_command.extend(["-v", f"{mcp_servers_path}:/mcp-servers:ro"])

        # Development mode: mount live Tactus source code
        if self.config.dev_mode:
            tactus_src_dir = self._find_tactus_source_dir()
            if tactus_src_dir:
                logger.info("[DEV MODE] Mounting live Tactus source from: %s", tactus_src_dir)
                docker_command.extend(["-v", f"{tactus_src_dir}/tactus:/app/tactus:ro"])
            else:
                logger.warning(
                    "[DEV MODE] Could not locate Tactus source directory, using baked-in version"
                )

        # Additional user-configured volumes
        for volume in self.config.volumes:
            docker_command.extend(
                ["-v", self._normalize_volume_spec(volume, base_dir=volume_base_dir)]
            )

        # User-configured additional env vars
        for key, value in self.config.env.items():
            if key in self._BLOCKED_CONTAINER_ENV_KEYS:
                logger.warning(
                    "[SANDBOX] Refusing to pass secret env var into container: %s",
                    key,
                )
                continue
            docker_command.extend(["--env", f"{key}={value}"])

        # Optional per-run callback URL for HTTP event streaming (IDE).
        if callback_url:
            docker_command.extend(["--env", f"TACTUS_CALLBACK_URL={callback_url}"])

        # Extra env vars for this run
        if extra_env:
            for key, value in extra_env.items():
                docker_command.extend(["--env", f"{key}={value}"])

        # Working directory inside container
        docker_command.extend(["-w", "/workspace"])

        # Image name
        docker_command.append(self.config.image)

        return docker_command

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
        volume_parts = volume.split(":")
        if len(volume_parts) < 2:
            return volume

        host_path_raw = volume_parts[0]
        container_path = volume_parts[1]
        mount_mode = volume_parts[2] if len(volume_parts) > 2 else None

        host_is_path = (
            host_path_raw.startswith(("/", "./", "../", "~"))
            or host_path_raw == "."
            or host_path_raw == ".."
        )
        if not host_is_path:
            # Named volume (or other special form) - leave unchanged
            return volume

        host_path = Path(host_path_raw).expanduser()
        if not host_path.is_absolute():
            host_path = (base_dir or Path.cwd()) / host_path
        host_path = host_path.resolve()

        if mount_mode:
            return f"{host_path}:{container_path}:{mount_mode}"
        return f"{host_path}:{container_path}"

    async def run(
        self,
        source: str,
        params: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        working_dir: Optional[Path] = None,
        format: str = "lua",
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
        callback_url: Optional[str] = None,
        run_id: Optional[str] = None,
        control_handler: Optional[Callable[[dict], Any]] = None,
        llm_backend_config: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute a procedure in a sandboxed container.

        Args:
            source: Procedure source code (.tac content)
            params: Input parameters for the procedure
            source_file_path: Original source file path (for error messages)
            working_dir: Working directory to use (default: temp directory)
            format: Source format ("lua" for .tac files, "yaml" for legacy)
            event_handler: Optional host callback for streaming events from the container
            callback_url: Optional HTTP callback URL for streaming events
            run_id: Optional run ID for checkpoint isolation across executions
            control_handler: Optional callback for handling container HITL requests
            llm_backend_config: Optional config for broker's LLM backend (provider-agnostic)

        Returns:
            ExecutionResult with status, result/error, and metadata.
        """
        # Ensure sandbox is up to date (auto-rebuild if code changed)
        # Skip for IDE to avoid blocking UI - IDE has its own rebuild mechanism
        skip_rebuild_for_ide_execution = (event_handler is not None) or (callback_url is not None)
        self._ensure_sandbox_up_to_date(skip_for_ide=skip_rebuild_for_ide_execution)

        execution_identifier = str(uuid.uuid4())[:8]
        start_timestamp = time.time()
        broker_server = None

        # Create temporary workspace if not provided
        temp_workspace_path = None
        if working_dir is None:
            temp_workspace_path = tempfile.mkdtemp(prefix="tactus-sandbox-")
            working_dir = Path(temp_workspace_path)

            # If we have a source file, copy its directory contents
            if source_file_path:
                source_parent_dir = Path(source_file_path).parent
                if source_parent_dir.exists():
                    for item in source_parent_dir.iterdir():
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

            # Configure broker transport for this run.
            broker_transport = (self.config.broker_transport or "stdio").lower()
            broker_env: dict[str, str]

            if broker_transport == "stdio":
                from tactus.broker.stdio import STDIO_TRANSPORT_VALUE

                broker_env = {"TACTUS_BROKER_SOCKET": STDIO_TRANSPORT_VALUE}
            elif broker_transport in ("tcp", "tls"):
                if self.config.network == "none":
                    raise SandboxError(
                        "sandbox.broker_transport requires container networking. "
                        "Set sandbox.network to 'bridge' (or another non-'none' mode)."
                    )

                from tactus.broker.server import OpenAIChatBackend, TcpBrokerServer

                ssl_context = None
                if broker_transport == "tls":
                    if not self.config.broker_tls_cert_file or not self.config.broker_tls_key_file:
                        raise SandboxError(
                            "sandbox.broker_transport='tls' requires "
                            "sandbox.broker_tls_cert_file and sandbox.broker_tls_key_file"
                        )
                    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                    ssl_context.load_cert_chain(
                        certfile=self.config.broker_tls_cert_file,
                        keyfile=self.config.broker_tls_key_file,
                    )

                # Extract OpenAI-specific config if provided
                openai_key = None
                if llm_backend_config:
                    openai_key = llm_backend_config.get("openai_api_key")

                broker_server = TcpBrokerServer(
                    host=self.config.broker_bind_host,
                    port=self.config.broker_port,
                    ssl_context=ssl_context,
                    openai_backend=OpenAIChatBackend(api_key=openai_key),
                    event_handler=event_handler,
                    control_handler=control_handler,
                )
                await broker_server.start()
                if broker_server.bound_port is None:
                    raise SandboxError("Failed to determine TCP broker listen port")

                scheme = "tls" if broker_transport == "tls" else "tcp"
                broker_env = {
                    "TACTUS_BROKER_SOCKET": (
                        f"{scheme}://{self.config.broker_host}:" f"{broker_server.bound_port}"
                    )
                }
            else:
                raise SandboxError(
                    f"Unsupported sandbox.broker_transport: {self.config.broker_transport!r}"
                )
            docker_cmd = self._build_docker_command(
                working_dir=working_dir,
                mcp_servers_path=mcp_path if mcp_path.exists() else None,
                extra_env=broker_env,
                execution_id=execution_identifier,
                callback_url=callback_url,
                volume_base_dir=volume_base_dir,
            )

            logger.debug("Docker command: %s", " ".join(docker_cmd))

            # Create execution request
            request = ExecutionRequest(
                source=source,
                working_dir="/workspace",
                params=params or {},
                execution_id=execution_identifier,
                run_id=run_id,
                source_file_path=source_file_path,
                format=format,
            )

            # Run container
            # If TCP broker is active, run it concurrently with the container
            if broker_transport in ("tcp", "tls") and broker_server is not None:

                async def run_broker_server():
                    """Serve broker connections until explicitly closed."""
                    try:
                        await broker_server.serve()
                    except Exception:
                        # Broker server was closed (expected on cleanup)
                        pass

                # Run broker and container concurrently
                broker_task = asyncio.create_task(run_broker_server())
                try:
                    result = await self._run_container(
                        docker_cmd,
                        request,
                        timeout=self.config.timeout,
                        event_handler=event_handler,
                        control_handler=control_handler,
                        llm_backend_config=llm_backend_config,
                    )
                finally:
                    # Cancel broker task when container finishes
                    broker_task.cancel()
                    try:
                        await broker_task
                    except asyncio.CancelledError:
                        pass
            else:
                result = await self._run_container(
                    docker_cmd,
                    request,
                    timeout=self.config.timeout,
                    event_handler=event_handler,
                    control_handler=control_handler,
                    llm_backend_config=llm_backend_config,
                )

            result.duration_seconds = time.time() - start_timestamp
            return result

        except asyncio.TimeoutError:
            return ExecutionResult.timeout(
                duration_seconds=time.time() - start_timestamp,
            )
        except Exception as e:
            logger.exception("Sandbox execution failed: %s", e)
            return ExecutionResult.failure(
                error=str(e),
                error_type=type(e).__name__,
                duration_seconds=time.time() - start_timestamp,
            )
        finally:
            if broker_server is not None:
                try:
                    await broker_server.aclose()
                except Exception:
                    logger.debug("[BROKER] Failed to close broker server", exc_info=True)

            # Cleanup temp directory
            if temp_workspace_path:
                try:
                    shutil.rmtree(temp_workspace_path)
                except Exception as e:  # pragma: no cover
                    logger.warning("Failed to cleanup temp dir: %s", e)  # pragma: no cover

    async def _run_container(
        self,
        docker_cmd: List[str],
        request: ExecutionRequest,
        timeout: int,
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
        control_handler: Optional[Callable[[dict], Any]] = None,
        llm_backend_config: Optional[Dict[str, Any]] = None,
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
        broker_transport = (self.config.broker_transport or "stdio").lower()

        stdio_request_prefix: str | None = None
        if broker_transport == "stdio":
            from tactus.broker.server import OpenAIChatBackend
            from tactus.broker.server import HostToolRegistry
            from tactus.broker.stdio import STDIO_REQUEST_PREFIX

            stdio_request_prefix = STDIO_REQUEST_PREFIX

            # Extract OpenAI-specific config if provided
            openai_key = None
            if llm_backend_config:
                openai_key = llm_backend_config.get("openai_api_key")

            openai_backend = OpenAIChatBackend(api_key=openai_key)
            tool_registry = HostToolRegistry.default()

            async def send_event(writer: asyncio.StreamWriter, event: dict[str, Any]) -> None:
                if writer.is_closing():
                    return
                try:
                    writer.write(
                        (
                            json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
                        ).encode("utf-8")
                    )
                    await writer.drain()
                except (BrokenPipeError, ConnectionResetError):
                    return

            async def handle_broker_request(
                writer: asyncio.StreamWriter, request_payload: dict[str, Any]
            ) -> None:
                request_id = request_payload.get("id") or ""
                request_method = request_payload.get("method")
                request_params = request_payload.get("params") or {}

                if not isinstance(request_id, str) or not isinstance(request_method, str):
                    await send_event(
                        writer,
                        {
                            "id": str(request_id) if request_id else "",
                            "event": "error",
                            "error": {"type": "BadRequest", "message": "Missing id/method"},
                        },
                    )
                    return

                if request_method == "events.emit":
                    event = (
                        request_params.get("event") if isinstance(request_params, dict) else None
                    )
                    if isinstance(event, dict) and event_handler is not None:
                        try:
                            event_handler(event)
                        except Exception:
                            logger.debug("[BROKER] event_handler raised", exc_info=True)
                    await send_event(
                        writer,
                        {"id": request_id, "event": "done", "data": {"ok": True}},
                    )
                    return

                if request_method == "control.request":
                    request_data = (
                        request_params.get("request") if isinstance(request_params, dict) else None
                    )
                    if control_handler is not None:
                        try:
                            # Send delivered event
                            await send_event(writer, {"id": request_id, "event": "delivered"})

                            # Call control handler and await response
                            response_data = await control_handler(request_data)

                            # Send response event
                            await send_event(
                                writer,
                                {
                                    "id": request_id,
                                    "event": "response",
                                    "data": response_data,
                                },
                            )
                        except asyncio.TimeoutError:
                            await send_event(
                                writer,
                                {
                                    "id": request_id,
                                    "event": "timeout",
                                    "data": {"timed_out": True},
                                },
                            )
                        except Exception as e:
                            logger.debug("[BROKER] control.request handler raised", exc_info=True)
                            await send_event(
                                writer,
                                {
                                    "id": request_id,
                                    "event": "error",
                                    "error": {"message": str(e)},
                                },
                            )
                    else:
                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "error",
                                "error": {"message": "No control handler configured"},
                            },
                        )
                    return

                if request_method == "tool.call":
                    tool_name = (
                        request_params.get("name") if isinstance(request_params, dict) else None
                    )
                    tool_args = (
                        request_params.get("args") if isinstance(request_params, dict) else None
                    )
                    if tool_args is None:
                        tool_args = {}

                    if not isinstance(tool_name, str) or not tool_name:
                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "error",
                                "error": {
                                    "type": "BadRequest",
                                    "message": "params.name must be a string",
                                },
                            },
                        )
                        return
                    if not isinstance(tool_args, dict):
                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "error",
                                "error": {
                                    "type": "BadRequest",
                                    "message": "params.args must be an object",
                                },
                            },
                        )
                        return

                    try:
                        result = tool_registry.call(tool_name, tool_args)
                    except KeyError:
                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "error",
                                "error": {
                                    "type": "ToolNotAllowed",
                                    "message": f"Tool not allowlisted: {tool_name}",
                                },
                            },
                        )
                        return
                    except Exception as e:
                        logger.debug("[BROKER] tool.call error", exc_info=True)
                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "error",
                                "error": {"type": type(e).__name__, "message": str(e)},
                            },
                        )
                        return

                    await send_event(
                        writer,
                        {"id": request_id, "event": "done", "data": {"result": result}},
                    )
                    return

                if request_method != "llm.chat":
                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "error",
                            "error": {
                                "type": "MethodNotFound",
                                "message": f"Unknown method: {request_method}",
                            },
                        },
                    )
                    return

                provider = (
                    request_params.get("provider") if isinstance(request_params, dict) else None
                ) or "openai"
                if provider != "openai":
                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "error",
                            "error": {
                                "type": "UnsupportedProvider",
                                "message": f"Unsupported provider: {provider}",
                            },
                        },
                    )
                    return

                model = request_params.get("model") if isinstance(request_params, dict) else None
                messages = (
                    request_params.get("messages") if isinstance(request_params, dict) else None
                )
                stream = (
                    bool(request_params.get("stream", False))
                    if isinstance(request_params, dict)
                    else False
                )
                temperature = (
                    request_params.get("temperature") if isinstance(request_params, dict) else None
                )
                max_tokens = (
                    request_params.get("max_tokens") if isinstance(request_params, dict) else None
                )

                if not isinstance(model, str) or not model:
                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "error",
                            "error": {
                                "type": "BadRequest",
                                "message": "params.model must be a string",
                            },
                        },
                    )
                    return
                if not isinstance(messages, list):
                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "error",
                            "error": {
                                "type": "BadRequest",
                                "message": "params.messages must be a list",
                            },
                        },
                    )
                    return

                try:
                    if stream:
                        stream_iter = await openai_backend.chat(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            stream=True,
                        )
                        accumulated_text = ""
                        async for chunk in stream_iter:
                            try:
                                delta = chunk.choices[0].delta
                                text = getattr(delta, "content", None)
                            except Exception:
                                text = None

                            if not text:
                                continue

                            accumulated_text += text
                            await send_event(
                                writer,
                                {
                                    "id": request_id,
                                    "event": "delta",
                                    "data": {"text": text},
                                },
                            )

                        await send_event(
                            writer,
                            {
                                "id": request_id,
                                "event": "done",
                                "data": {
                                    "text": accumulated_text,
                                    "usage": {
                                        "prompt_tokens": 0,
                                        "completion_tokens": 0,
                                        "total_tokens": 0,
                                    },
                                },
                            },
                        )
                        return

                    resp = await openai_backend.chat(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=False,
                    )
                    text = ""
                    try:
                        text = resp.choices[0].message.content or ""
                    except Exception:
                        text = ""

                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "done",
                            "data": {
                                "text": text,
                                "usage": {
                                    "prompt_tokens": 0,
                                    "completion_tokens": 0,
                                    "total_tokens": 0,
                                },
                            },
                        },
                    )
                except Exception as e:
                    logger.debug("[BROKER] llm.chat error", exc_info=True)
                    await send_event(
                        writer,
                        {
                            "id": request_id,
                            "event": "error",
                            "error": {"type": type(e).__name__, "message": str(e)},
                        },
                    )

        else:

            async def handle_broker_request(
                writer: asyncio.StreamWriter, req: dict[str, Any]
            ) -> None:
                raise RuntimeError(
                    "Broker requests are not expected in non-stdio transports"
                )  # pragma: no cover

        # Start container process
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.debug("[SANDBOX] Spawned container process pid=%s", process.pid)

        stdout_task: asyncio.Task[None] | None = None
        stderr_task: asyncio.Task[None] | None = None
        wait_task: asyncio.Task[int] | None = None

        try:
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None

            # Send request as a single JSON line, then keep stdin open for broker responses.
            request_line = (request.to_json() + "\n").encode("utf-8")
            process.stdin.write(request_line)
            await process.stdin.drain()
            logger.debug("[SANDBOX] Sent ExecutionRequest bytes=%s", len(request_line))

            stdout_bytes = bytearray()
            result_future: asyncio.Future[ExecutionResult] = (
                asyncio.get_running_loop().create_future()
            )

            async def stdout_loop() -> None:
                in_result = False
                result_lines: list[str] = []

                while True:
                    raw = await process.stdout.readline()
                    if not raw:
                        return

                    stdout_bytes.extend(raw)
                    line = raw.decode("utf-8", errors="replace").rstrip("\n")

                    if not in_result:
                        if line == RESULT_START_MARKER:
                            in_result = True
                            result_lines = []
                        continue

                    if line == RESULT_END_MARKER:
                        json_str = "\n".join(result_lines).strip()
                        try:
                            parsed = ExecutionResult.from_json(json_str)
                        except Exception:
                            in_result = False
                            continue

                        if not result_future.done():
                            result_future.set_result(parsed)

                        in_result = False
                        continue

                    result_lines.append(line)

            async def stderr_loop() -> None:
                while True:
                    raw = await process.stderr.readline()
                    if not raw:
                        return
                    line = raw.decode("utf-8", errors="replace").rstrip("\n")
                    if stdio_request_prefix is not None and line.startswith(stdio_request_prefix):
                        payload = line[len(stdio_request_prefix) :]
                        try:
                            req_obj = json.loads(payload)
                        except json.JSONDecodeError:
                            logger.debug("[BROKER] Failed to decode stdio broker request JSON")
                            continue
                        if isinstance(req_obj, dict):
                            await handle_broker_request(process.stdin, req_obj)
                        continue

                    if line:
                        logger.info("[container] %s", line)

            stdout_task = asyncio.create_task(stdout_loop())
            stderr_task = asyncio.create_task(stderr_loop())
            wait_task = asyncio.create_task(process.wait())

            loop = asyncio.get_running_loop()
            deadline = loop.time() + timeout
            stdin_closed = False

            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise asyncio.TimeoutError

                done, _pending = await asyncio.wait(
                    {wait_task, result_future},
                    timeout=remaining,
                    return_when=asyncio.FIRST_COMPLETED,
                )

                # Once we have a structured result, signal EOF to the container process.
                # Some runtimes (notably Docker Desktop attach mode) can keep the outer
                # process alive until stdin is closed.
                if result_future in done and not stdin_closed:
                    try:
                        process.stdin.close()
                        stdin_closed = True
                    except Exception:
                        stdin_closed = True

                if wait_task in done:
                    break

            if not stdin_closed:
                try:
                    process.stdin.close()
                except Exception:
                    pass

            try:
                await asyncio.wait_for(stdout_task, timeout=5)
            except asyncio.TimeoutError:
                stdout_task.cancel()
                try:
                    await stdout_task
                except Exception:
                    pass

            try:
                await asyncio.wait_for(stderr_task, timeout=5)
            except asyncio.TimeoutError:
                stderr_task.cancel()
                try:
                    await stderr_task
                except Exception:
                    pass

            stdout = stdout_bytes.decode("utf-8", errors="replace")

            # Extract result from stdout
            if result_future.done():
                return result_future.result()

            result = extract_result_from_stdout(stdout)
            if result is not None:
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
                    error=stdout.strip() or f"Container exited with code {process.returncode}",
                    exit_code=process.returncode or 1,
                )

        except asyncio.TimeoutError:
            # Kill the container
            try:
                try:
                    process.stdin.close()
                except Exception:
                    pass
                process.kill()
                await process.wait()
            except Exception:
                pass
            for task in (stdout_task, stderr_task, wait_task):
                if task is None:  # pragma: no cover
                    continue
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
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
        source_file_path: Optional[str] = None,
        working_dir: Optional[Path] = None,
        format: str = "lua",
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> ExecutionResult:
        """
        Synchronous wrapper for run().

        For use in non-async contexts.
        """
        return asyncio.run(
            self.run(
                source=source,
                params=params,
                source_file_path=source_file_path,
                format=format,
                working_dir=working_dir,
                event_handler=event_handler,
            )
        )
