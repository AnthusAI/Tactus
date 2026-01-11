"""
Container execution manager for sandboxed procedure execution.

Handles spawning Docker containers, passing execution requests,
and collecting results via stdio communication.
"""

import asyncio
import json
import logging
import shutil
import ssl
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import SandboxConfig
from .protocol import (
    ExecutionRequest,
    ExecutionResult,
    RESULT_END_MARKER,
    RESULT_START_MARKER,
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

    def _build_docker_command(
        self,
        working_dir: Path,
        mcp_servers_path: Optional[Path] = None,
        extra_env: Optional[Dict[str, str]] = None,
        execution_id: Optional[str] = None,
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

        cmd = [
            "docker",
            "run",
            "--rm",  # Remove container after exit
            "-i",  # Interactive (keep stdin open)
            "--name",
            container_name,
        ]

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

        # User-configured additional env vars
        for key, value in self.config.env.items():
            if key in self._BLOCKED_CONTAINER_ENV_KEYS:
                logger.warning(f"[SANDBOX] Refusing to pass secret env var into container: {key}")
                continue
            cmd.extend(["--env", f"{key}={value}"])

        # Extra env vars for this run
        if extra_env:
            for key, value in extra_env.items():
                cmd.extend(["--env", f"{key}={value}"])

        # Working directory inside container
        cmd.extend(["-w", "/workspace"])

        # Image name
        cmd.append(self.config.image)

        return cmd

    async def run(
        self,
        source: str,
        params: Optional[Dict[str, Any]] = None,
        source_file_path: Optional[str] = None,
        working_dir: Optional[Path] = None,
        format: str = "lua",
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
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

        Returns:
            ExecutionResult with status, result/error, and metadata.
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        broker_server = None

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

                broker_server = TcpBrokerServer(
                    host=self.config.broker_bind_host,
                    port=self.config.broker_port,
                    ssl_context=ssl_context,
                    openai_backend=OpenAIChatBackend(),
                    event_handler=event_handler,
                )
                await broker_server.start()
                if broker_server.bound_port is None:
                    raise SandboxError("Failed to determine TCP broker listen port")

                scheme = "tls" if broker_transport == "tls" else "tcp"
                broker_env = {
                    "TACTUS_BROKER_SOCKET": f"{scheme}://{self.config.broker_host}:{broker_server.bound_port}"
                }
            else:
                raise SandboxError(
                    f"Unsupported sandbox.broker_transport: {self.config.broker_transport!r}"
                )

            docker_cmd = self._build_docker_command(
                working_dir=working_dir,
                mcp_servers_path=mcp_path if mcp_path.exists() else None,
                extra_env=broker_env,
                execution_id=execution_id,
            )

            logger.debug(f"Docker command: {' '.join(docker_cmd)}")

            # Create execution request
            request = ExecutionRequest(
                source=source,
                working_dir="/workspace",
                params=params or {},
                execution_id=execution_id,
                source_file_path=source_file_path,
                format=format,
            )

            # Run container
            result = await self._run_container(
                docker_cmd,
                request,
                timeout=self.config.timeout,
                event_handler=event_handler,
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
            if broker_server is not None:
                try:
                    await broker_server.aclose()
                except Exception:
                    logger.debug("[BROKER] Failed to close broker server", exc_info=True)

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
        event_handler: Optional[Callable[[Dict[str, Any]], None]] = None,
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
            openai_backend = OpenAIChatBackend()
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
                writer: asyncio.StreamWriter, req: dict[str, Any]
            ) -> None:
                req_id = req.get("id") or ""
                method = req.get("method")
                params = req.get("params") or {}

                if not isinstance(req_id, str) or not isinstance(method, str):
                    await send_event(
                        writer,
                        {
                            "id": str(req_id) if req_id else "",
                            "event": "error",
                            "error": {"type": "BadRequest", "message": "Missing id/method"},
                        },
                    )
                    return

                if method == "events.emit":
                    event = params.get("event") if isinstance(params, dict) else None
                    if isinstance(event, dict) and event_handler is not None:
                        try:
                            event_handler(event)
                        except Exception:
                            logger.debug("[BROKER] event_handler raised", exc_info=True)
                    await send_event(writer, {"id": req_id, "event": "done", "data": {"ok": True}})
                    return

                if method == "tool.call":
                    name = params.get("name") if isinstance(params, dict) else None
                    args = params.get("args") if isinstance(params, dict) else None
                    if args is None:
                        args = {}

                    if not isinstance(name, str) or not name:
                        await send_event(
                            writer,
                            {
                                "id": req_id,
                                "event": "error",
                                "error": {
                                    "type": "BadRequest",
                                    "message": "params.name must be a string",
                                },
                            },
                        )
                        return
                    if not isinstance(args, dict):
                        await send_event(
                            writer,
                            {
                                "id": req_id,
                                "event": "error",
                                "error": {
                                    "type": "BadRequest",
                                    "message": "params.args must be an object",
                                },
                            },
                        )
                        return

                    try:
                        result = tool_registry.call(name, args)
                    except KeyError:
                        await send_event(
                            writer,
                            {
                                "id": req_id,
                                "event": "error",
                                "error": {
                                    "type": "ToolNotAllowed",
                                    "message": f"Tool not allowlisted: {name}",
                                },
                            },
                        )
                        return
                    except Exception as e:
                        logger.debug("[BROKER] tool.call error", exc_info=True)
                        await send_event(
                            writer,
                            {
                                "id": req_id,
                                "event": "error",
                                "error": {"type": type(e).__name__, "message": str(e)},
                            },
                        )
                        return

                    await send_event(
                        writer, {"id": req_id, "event": "done", "data": {"result": result}}
                    )
                    return

                if method != "llm.chat":
                    await send_event(
                        writer,
                        {
                            "id": req_id,
                            "event": "error",
                            "error": {
                                "type": "MethodNotFound",
                                "message": f"Unknown method: {method}",
                            },
                        },
                    )
                    return

                provider = (
                    params.get("provider") if isinstance(params, dict) else None
                ) or "openai"
                if provider != "openai":
                    await send_event(
                        writer,
                        {
                            "id": req_id,
                            "event": "error",
                            "error": {
                                "type": "UnsupportedProvider",
                                "message": f"Unsupported provider: {provider}",
                            },
                        },
                    )
                    return

                model = params.get("model") if isinstance(params, dict) else None
                messages = params.get("messages") if isinstance(params, dict) else None
                stream = bool(params.get("stream", False)) if isinstance(params, dict) else False
                temperature = params.get("temperature") if isinstance(params, dict) else None
                max_tokens = params.get("max_tokens") if isinstance(params, dict) else None

                if not isinstance(model, str) or not model:
                    await send_event(
                        writer,
                        {
                            "id": req_id,
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
                            "id": req_id,
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
                        full_text = ""
                        async for chunk in stream_iter:
                            try:
                                delta = chunk.choices[0].delta
                                text = getattr(delta, "content", None)
                            except Exception:
                                text = None

                            if not text:
                                continue

                            full_text += text
                            await send_event(
                                writer, {"id": req_id, "event": "delta", "data": {"text": text}}
                            )

                        await send_event(
                            writer,
                            {
                                "id": req_id,
                                "event": "done",
                                "data": {
                                    "text": full_text,
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
                            "id": req_id,
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
                            "id": req_id,
                            "event": "error",
                            "error": {"type": type(e).__name__, "message": str(e)},
                        },
                    )

        else:

            async def handle_broker_request(
                writer: asyncio.StreamWriter, req: dict[str, Any]
            ) -> None:
                raise RuntimeError("Broker requests are not expected in non-stdio transports")

        # Start container process
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        logger.debug(f"[SANDBOX] Spawned container process pid={process.pid}")

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
            logger.debug(f"[SANDBOX] Sent ExecutionRequest bytes={len(request_line)}")

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
                        logger.info(f"[container] {line}")

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
                if task is None:
                    continue
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            raise

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
