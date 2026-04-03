"""
Host-side broker server (local UDS transport).

This is intentionally narrow: it exposes only allowlisted operations required
by the runtime container.
"""

import asyncio
import json
import logging
import os
import re
import ssl
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import anyio
from anyio.streams.buffered import BufferedByteReceiveStream
from anyio.streams.tls import TLSStream

from tactus.broker.protocol import (
    read_message,
    read_message_anyio,
    write_message,
    write_message_anyio,
)

logger = logging.getLogger(__name__)


try:
    from builtins import BaseExceptionGroup as BaseExceptionGroup
except ImportError:  # pragma: no cover - Python < 3.11 fallback

    class BaseExceptionGroup(Exception):
        """Minimal BaseExceptionGroup fallback for Python < 3.11."""

        def __init__(self, message: str, exceptions: list[BaseException]):
            super().__init__(message)
            self.exceptions = exceptions


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


async def _write_event_anyio(stream: anyio.abc.ByteStream, event: dict[str, Any]) -> None:
    """Write an event using length-prefixed protocol."""
    await write_message_anyio(stream, event)


async def _write_event_asyncio(writer: asyncio.StreamWriter, event: dict[str, Any]) -> None:
    """Write an event using length-prefixed protocol."""
    await write_message(writer, event)


def _flatten_exceptions(exc: BaseException) -> list[BaseException]:
    """Flatten BaseExceptionGroup into a list of leaf exceptions."""
    if isinstance(exc, BaseExceptionGroup):
        leaves: list[BaseException] = []
        for child in exc.exceptions:
            leaves.extend(_flatten_exceptions(child))
        return leaves
    return [exc]


@dataclass(frozen=True)
class OpenAIChatConfig:
    api_key_env: str = "OPENAI_API_KEY"


class OpenAIChatBackend:
    """
    Minimal OpenAI chat-completions backend used by the broker.

    Credentials can be provided directly or read from the broker process environment.
    """

    def __init__(self, config: Optional[OpenAIChatConfig] = None, api_key: Optional[str] = None):
        self._config = config or OpenAIChatConfig()
        self._api_key = api_key  # Direct API key (bypasses environment)

        # Lazy-init the client so unit tests can run without OpenAI installed/configured.
        self._client = None

    def _get_client(self):
        # We don't need to maintain a client - LiteLLM handles that
        return None

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ):
        # Use LiteLLM instead of raw OpenAI SDK for provider-agnostic support
        import litellm

        # Set API key from environment if configured
        api_key = self._api_key or os.environ.get(self._config.api_key_env)
        if api_key:
            os.environ[self._config.api_key_env] = api_key

        kwargs: dict[str, Any] = {"model": model, "messages": messages, "stream": stream}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if tools is not None:
            kwargs["tools"] = tools
            logger.info("[LITELLM_BACKEND] Sending %s tools to LiteLLM", len(tools))
            logger.info("[LITELLM_BACKEND] Tool schemas: %s", tools)
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice
            logger.info("[LITELLM_BACKEND] Setting tool_choice=%s", tool_choice)

        # Always use acompletion for consistency, LiteLLM handles both sync/async
        result = await litellm.acompletion(**kwargs)

        if stream:
            logger.info("[LITELLM_BACKEND] LiteLLM streaming response started")
        else:
            finish_reason = result.choices[0].finish_reason if result.choices else "NO_CHOICES"
            logger.info(
                "[LITELLM_BACKEND] LiteLLM response: finish_reason=%s",
                finish_reason,
            )
            if (
                result.choices
                and hasattr(result.choices[0].message, "tool_calls")
                and result.choices[0].message.tool_calls
            ):
                logger.info(
                    "[LITELLM_BACKEND] LiteLLM returned %s tool calls",
                    len(result.choices[0].message.tool_calls),
                )
            else:
                logger.info("[LITELLM_BACKEND] LiteLLM returned NO tool calls")

        return result


class HostToolRegistry:
    """
    Minimal deny-by-default registry for broker-executed host tools.

    Phase 1B starts with a tiny allowlist and expands deliberately.
    """

    def __init__(self, tools: Optional[dict[str, Callable[[dict[str, Any]], Any]]] = None):
        self._tools = tools or {}

    @classmethod
    def default(cls) -> "HostToolRegistry":
        def host_ping(args: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True, "echo": args}

        def host_echo(args: dict[str, Any]) -> dict[str, Any]:
            return {"echo": args}

        return cls({"host.ping": host_ping, "host.echo": host_echo})

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not allowlisted: {name}")
        return self._tools[name](args)


def _substitute_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\$\{(\w+)\}", lambda match: os.getenv(match.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _substitute_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_env_vars(v) for v in value]
    return value


def _load_broker_mcp_servers_from_user_config() -> dict[str, Any]:
    try:
        from tactus.core.config_manager import ConfigManager

        config_manager = ConfigManager()
        servers = config_manager.load_host_mcp_servers()
        if isinstance(servers, dict):
            return servers
    except Exception:
        logger.debug("[BROKER] Failed to load broker MCP servers from user config", exc_info=True)
    return {}


class BrokerMCPManager:
    """
    Host-side MCP server manager for broker-proxied MCP tools.

    Spawns MCP servers via stdio and proxies list/call operations.
    """

    def __init__(self, server_configs: Optional[dict[str, dict[str, Any]]] = None):
        self._configs = server_configs or {}
        self._servers: dict[str, Any] = {}
        self._exit_stack = AsyncExitStack()
        self._mcp_server_stdio = None

    def _require_mcp_server_stdio(self):
        if self._mcp_server_stdio is not None:
            return self._mcp_server_stdio
        try:
            from pydantic_ai.mcp import MCPServerStdio
        except ImportError as import_error:
            raise RuntimeError(
                "Broker MCP support requires optional dependencies. "
                'Install with `pip install "pydantic-ai-slim[mcp]"`.'
            ) from import_error
        self._mcp_server_stdio = MCPServerStdio
        return MCPServerStdio

    async def _ensure_server(self, name: str):
        if name in self._servers:
            return self._servers[name]
        if name not in self._configs:
            raise KeyError(f"MCP server not configured: {name}")
        config = _substitute_env_vars(self._configs[name])
        MCPServerStdio = self._require_mcp_server_stdio()
        server = MCPServerStdio(
            command=config["command"],
            args=config.get("args", []),
            env=config.get("env"),
            cwd=config.get("cwd"),
            timeout=config.get("timeout", 5),
            read_timeout=config.get("read_timeout", 300),
            max_retries=config.get("max_retries", 1),
        )
        await self._exit_stack.enter_async_context(server)
        self._servers[name] = server
        logger.info("[BROKER] Started MCP server '%s' via stdio", name)
        return server

    async def list_tools(self, name: str) -> list[dict[str, Any]]:
        server = await self._ensure_server(name)
        tools = await server.list_tools()
        return [tool.model_dump() for tool in tools]

    async def call_tool(self, server_name: str, tool_name: str, tool_args: dict[str, Any]):
        server = await self._ensure_server(server_name)
        # Try the provided name first. If not found, attempt a prefixed/unprefixed variant.
        prefix = f"{server_name}_"
        try:
            result = await server.direct_call_tool(tool_name, tool_args or {})
            return _json_safe(result)
        except KeyError as error:
            # Fallback: flip prefix if this looks namespaced.
            alt_name = None
            if tool_name.startswith(prefix):
                alt_name = tool_name[len(prefix) :]
            else:
                alt_name = f"{prefix}{tool_name}"

            if alt_name and alt_name != tool_name:
                result = await server.direct_call_tool(alt_name, tool_args or {})
                return _json_safe(result)
            raise error

    async def aclose(self) -> None:
        await self._exit_stack.aclose()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


class _BaseBrokerServer:
    def __init__(
        self,
        *,
        openai_backend: Optional[OpenAIChatBackend] = None,
        tool_registry: Optional[HostToolRegistry] = None,
        mcp_manager: Optional[BrokerMCPManager] = None,
        broker_mcp_servers: Optional[dict[str, dict[str, Any]]] = None,
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
        control_handler: Optional[Callable[[dict], Awaitable[dict]]] = None,
    ):
        self._listener = None
        self._serve_task: Optional[asyncio.Task[None]] = None
        self._openai = openai_backend or OpenAIChatBackend()
        self._tools = tool_registry or HostToolRegistry.default()
        if mcp_manager is None:
            if broker_mcp_servers is None:
                broker_mcp_servers = _load_broker_mcp_servers_from_user_config()
            mcp_manager = BrokerMCPManager(broker_mcp_servers) if broker_mcp_servers else None
        self._mcp_manager = mcp_manager
        self._event_handler = event_handler
        self._control_handler = control_handler

    async def start(self) -> None:
        raise NotImplementedError

    async def serve(self) -> None:
        """Serve connections (blocks until listener is closed)."""
        if self._listener is None:
            raise RuntimeError("Server not started - call start() first")
        await self._listener.serve(self._handle_connection)

    async def aclose(self) -> None:
        if self._listener is not None:
            await self._listener.aclose()
            self._listener = None

        task = self._serve_task
        self._serve_task = None
        if task is not None:
            try:
                await task
            except BaseExceptionGroup as eg:
                # AnyIO raises ClosedResourceError during normal listener shutdown.
                leaves = _flatten_exceptions(eg)
                if leaves and all(isinstance(e, anyio.ClosedResourceError) for e in leaves):
                    return
                raise
            except asyncio.CancelledError:
                logger.debug("[BROKER] Serve task cancelled during shutdown")

        if self._mcp_manager is not None:
            try:
                await self._mcp_manager.aclose()
            except Exception:
                logger.debug("[BROKER] Failed to close MCP manager", exc_info=True)

    async def __aenter__(self) -> "_BaseBrokerServer":
        await self.start()

        # AnyIO listeners (TCP/TLS) require an explicit serve loop. Run it in the background
        # so `async with TcpBrokerServer(...)` is sufficient to accept connections.
        if self._listener is not None:
            self._serve_task = asyncio.create_task(self.serve(), name="tactus-broker-serve")
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def _handle_connection(self, byte_stream: anyio.abc.ByteStream) -> None:
        # For TLS connections, wrap the stream with TLS
        # Note: TcpBrokerServer subclass can override self.ssl_context
        if hasattr(self, "ssl_context") and self.ssl_context is not None:
            byte_stream = await TLSStream.wrap(
                byte_stream, ssl_context=self.ssl_context, server_side=True
            )

        # Wrap the stream for buffered reading
        buffered_stream = BufferedByteReceiveStream(byte_stream)

        try:
            # Use length-prefixed protocol to handle arbitrarily large messages
            request_payload = await read_message_anyio(buffered_stream)
            request_id = request_payload.get("id")
            request_method = request_payload.get("method")
            request_params = request_payload.get("params") or {}

            if not request_id or not request_method:
                await _write_event_anyio(
                    byte_stream,
                    {
                        "id": request_id or "",
                        "event": "error",
                        "error": {"type": "BadRequest", "message": "Missing id/method"},
                    },
                )
                return

            if request_method == "events.emit":
                await self._handle_events_emit(request_id, request_params, byte_stream)
                return

            if request_method == "control.request":
                await self._handle_control_request(request_id, request_params, byte_stream)
                return

            if request_method == "llm.chat":
                await self._handle_llm_chat(request_id, request_params, byte_stream)
                return

            if request_method == "tool.call":
                await self._handle_tool_call(request_id, request_params, byte_stream)
                return

            if request_method == "mcp.list_tools":
                await self._handle_mcp_list_tools(request_id, request_params, byte_stream)
                return

            if request_method == "mcp.call_tool":
                await self._handle_mcp_call_tool(request_id, request_params, byte_stream)
                return

            await _write_event_anyio(
                byte_stream,
                {
                    "id": request_id,
                    "event": "error",
                    "error": {
                        "type": "MethodNotFound",
                        "message": f"Unknown method: {request_method}",
                    },
                },
            )

        except Exception as error:
            logger.debug("[BROKER] Connection handler error", exc_info=True)
            try:
                await _write_event_anyio(
                    byte_stream,
                    {
                        "id": "",
                        "event": "error",
                        "error": {"type": type(error).__name__, "message": str(error)},
                    },
                )
            except Exception:
                logger.debug(
                    "[BROKER] Failed writing error response to AnyIO stream", exc_info=True
                )
        finally:
            try:
                await byte_stream.aclose()
            except Exception:
                logger.debug("[BROKER] Failed closing AnyIO byte stream", exc_info=True)

    async def _handle_connection_asyncio(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle a single broker request over asyncio streams.

        UDS uses asyncio's StreamReader/StreamWriter APIs, while TCP uses AnyIO streams.
        """
        try:
            request_payload = await read_message(reader)
            request_id = request_payload.get("id")
            request_method = request_payload.get("method")
            request_params = request_payload.get("params") or {}

            if not request_id or not request_method:
                await _write_event_asyncio(
                    writer,
                    {
                        "id": request_id or "",
                        "event": "error",
                        "error": {"type": "BadRequest", "message": "Missing id/method"},
                    },
                )
                return

            if request_method == "events.emit":
                await self._handle_events_emit_asyncio(request_id, request_params, writer)
                return

            if request_method == "llm.chat":
                await self._handle_llm_chat_asyncio(request_id, request_params, writer)
                return

            if request_method == "tool.call":
                await self._handle_tool_call_asyncio(request_id, request_params, writer)
                return

            if request_method == "mcp.list_tools":
                await self._handle_mcp_list_tools_asyncio(request_id, request_params, writer)
                return

            if request_method == "mcp.call_tool":
                await self._handle_mcp_call_tool_asyncio(request_id, request_params, writer)
                return

            await _write_event_asyncio(
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
        except Exception as error:
            logger.debug("[BROKER] asyncio connection handler error", exc_info=True)
            try:
                await _write_event_asyncio(
                    writer,
                    {
                        "id": "",
                        "event": "error",
                        "error": {"type": type(error).__name__, "message": str(error)},
                    },
                )
            except Exception:
                logger.debug(
                    "[BROKER] Failed writing error response to asyncio stream",
                    exc_info=True,
                )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                logger.debug("[BROKER] Failed closing asyncio writer", exc_info=True)

    async def _handle_events_emit_asyncio(
        self, req_id: str, params: dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        event_payload = params.get("event")
        if not isinstance(event_payload, dict):
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.event must be an object"},
                },
            )
            return

        try:
            if self._event_handler is not None:
                self._event_handler(event_payload)
        except Exception:
            logger.debug("[BROKER] event_handler raised", exc_info=True)

        await _write_event_asyncio(writer, {"id": req_id, "event": "done", "data": {"ok": True}})

    async def _handle_llm_chat_asyncio(
        self, req_id: str, params: dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        provider_name = params.get("provider") or "openai"
        if provider_name != "openai":
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "UnsupportedProvider",
                        "message": f"Unsupported provider: {provider_name}",
                    },
                },
            )
            return

        model = params.get("model")
        messages = params.get("messages")
        stream = bool(params.get("stream", False))
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        tools = params.get("tools")
        tool_choice = params.get("tool_choice")

        if not isinstance(model, str) or not model:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.model must be a string"},
                },
            )
            return
        if not isinstance(messages, list):
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.messages must be a list"},
                },
            )
            return

        try:
            if stream:
                stream_iterator = await self._openai.chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    tools=tools,
                    tool_choice=tool_choice,
                )

                accumulated_text = ""
                tool_calls_accumulator: list[dict[str, Any]] = []
                async for chunk in stream_iterator:
                    try:
                        delta = chunk.choices[0].delta
                        delta_text = getattr(delta, "content", None)
                        delta_tool_calls = getattr(delta, "tool_calls", None)
                    except Exception:
                        delta_text = None
                        delta_tool_calls = None

                    if delta_text:
                        accumulated_text += delta_text
                        await _write_event_asyncio(
                            writer,
                            {
                                "id": req_id,
                                "event": "delta",
                                "data": {"text": delta_text},
                            },
                        )

                    # Accumulate tool calls from deltas
                    if delta_tool_calls:
                        logger.info(
                            "[LITELLM_BACKEND] Received delta_tool_calls: %s",
                            delta_tool_calls,
                        )
                        for tool_call_delta in delta_tool_calls:
                            tool_call_index = tool_call_delta.index
                            # Extend tool_calls_data list if needed
                            while len(tool_calls_accumulator) <= tool_call_index:
                                tool_calls_accumulator.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )

                            # Merge delta into accumulated tool call
                            if tool_call_delta.id:
                                tool_calls_accumulator[tool_call_index]["id"] = tool_call_delta.id
                            if tool_call_delta.type:
                                tool_calls_accumulator[tool_call_index][
                                    "type"
                                ] = tool_call_delta.type
                            if hasattr(tool_call_delta, "function") and tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "name"
                                    ] += tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "arguments"
                                    ] += tool_call_delta.function.arguments

                # Build final response data
                logger.info(
                    "[LITELLM_BACKEND] Streaming complete. tool_calls_data=%s, "
                    "full_text length=%s",
                    tool_calls_accumulator,
                    len(accumulated_text),
                )
                done_data = {
                    "text": accumulated_text,
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                if tool_calls_accumulator:
                    done_data["tool_calls"] = tool_calls_accumulator

                await _write_event_asyncio(
                    writer,
                    {
                        "id": req_id,
                        "event": "done",
                        "data": done_data,
                    },
                )
                return

            resp = await self._openai.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=tools,
                tool_choice=tool_choice,
            )
            text = ""
            tool_calls_data = None
            try:
                message = resp.choices[0].message
                text = message.content or ""

                # Extract tool calls if present
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls_data = []
                    for tc in message.tool_calls:
                        tool_calls_data.append(
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                        )
            except Exception:
                text = ""
                tool_calls_data = None

            # Build response data
            done_data = {
                "text": text,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            if tool_calls_data:
                done_data["tool_calls"] = tool_calls_data

            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "done",
                    "data": done_data,
                },
            )
        except Exception as error:
            logger.debug("[BROKER] llm.chat error", exc_info=True)
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )

    async def _handle_tool_call_asyncio(
        self, req_id: str, params: dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        tool_name = params.get("name")
        tool_args = params.get("args") or {}

        if not isinstance(tool_name, str) or not tool_name:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                },
            )
            return
        if not isinstance(tool_args, dict):
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                },
            )
            return

        try:
            result = self._tools.call(tool_name, tool_args)
        except KeyError:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "ToolNotAllowed",
                        "message": f"Tool not allowlisted: {tool_name}",
                    },
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] tool.call error", exc_info=True)
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_asyncio(
            writer, {"id": req_id, "event": "done", "data": {"result": result}}
        )

    async def _handle_mcp_list_tools_asyncio(
        self, req_id: str, params: dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        server_name = params.get("server")
        if not isinstance(server_name, str) or not server_name:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.server must be a string"},
                },
            )
            return

        if self._mcp_manager is None:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "MCPNotConfigured",
                        "message": "No broker MCP servers configured",
                    },
                },
            )
            return

        try:
            tools = await self._mcp_manager.list_tools(server_name)
        except KeyError as error:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "NotFound", "message": str(error)},
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] mcp.list_tools error", exc_info=True)
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_asyncio(
            writer, {"id": req_id, "event": "done", "data": {"tools": tools}}
        )

    async def _handle_events_emit(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        event_payload = params.get("event")
        if not isinstance(event_payload, dict):
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.event must be an object"},
                },
            )
            return

        try:
            if self._event_handler is not None:
                self._event_handler(event_payload)
        except Exception:
            logger.debug("[BROKER] event_handler raised", exc_info=True)

        await _write_event_anyio(byte_stream, {"id": req_id, "event": "done", "data": {"ok": True}})

    async def _handle_control_request(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        """Handle control.request method for HITL requests from container."""
        request_data = params.get("request")
        if not isinstance(request_data, dict):
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.request must be an object"},
                },
            )
            return

        if self._control_handler is None:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "NoControlHandler",
                        "message": "No control handler configured",
                    },
                },
            )
            return

        try:
            # Send delivered event
            await _write_event_anyio(byte_stream, {"id": req_id, "event": "delivered"})

            # Call control handler and await response
            response_data = await self._control_handler(request_data)

            # Send response event
            await _write_event_anyio(
                byte_stream, {"id": req_id, "event": "response", "data": response_data}
            )
        except asyncio.TimeoutError:
            await _write_event_anyio(
                byte_stream, {"id": req_id, "event": "timeout", "data": {"timed_out": True}}
            )
        except Exception as error:
            logger.debug("[BROKER] control.request handler raised", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )

    async def _handle_llm_chat(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        provider_name = params.get("provider") or "openai"
        if provider_name != "openai":
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "UnsupportedProvider",
                        "message": f"Unsupported provider: {provider_name}",
                    },
                },
            )
            return

        model = params.get("model")
        messages = params.get("messages")
        stream = bool(params.get("stream", False))
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        tools = params.get("tools")
        tool_choice = params.get("tool_choice")

        if not isinstance(model, str) or not model:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.model must be a string"},
                },
            )
            return
        if not isinstance(messages, list):
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.messages must be a list"},
                },
            )
            return

        try:
            if stream:
                stream_iterator = await self._openai.chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    tools=tools,
                    tool_choice=tool_choice,
                )

                accumulated_text = ""
                tool_calls_accumulator: list[dict[str, Any]] = []
                async for chunk in stream_iterator:
                    try:
                        delta = chunk.choices[0].delta
                        delta_text = getattr(delta, "content", None)
                        delta_tool_calls = getattr(delta, "tool_calls", None)
                    except Exception:
                        delta_text = None
                        delta_tool_calls = None

                    if delta_text:
                        accumulated_text += delta_text
                        await _write_event_anyio(
                            byte_stream,
                            {
                                "id": req_id,
                                "event": "delta",
                                "data": {"text": delta_text},
                            },
                        )

                    # Accumulate tool calls from deltas
                    if delta_tool_calls:
                        logger.info(
                            "[LITELLM_BACKEND] Received delta_tool_calls: %s",
                            delta_tool_calls,
                        )
                        for tool_call_delta in delta_tool_calls:
                            tool_call_index = tool_call_delta.index
                            # Extend tool_calls_data list if needed
                            while len(tool_calls_accumulator) <= tool_call_index:
                                tool_calls_accumulator.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )

                            # Merge delta into accumulated tool call
                            if tool_call_delta.id:
                                tool_calls_accumulator[tool_call_index]["id"] = tool_call_delta.id
                            if tool_call_delta.type:
                                tool_calls_accumulator[tool_call_index][
                                    "type"
                                ] = tool_call_delta.type
                            if hasattr(tool_call_delta, "function") and tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "name"
                                    ] += tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "arguments"
                                    ] += tool_call_delta.function.arguments

                # Build final response data
                logger.info(
                    "[LITELLM_BACKEND] Streaming complete. tool_calls_data=%s, "
                    "full_text length=%s",
                    tool_calls_accumulator,
                    len(accumulated_text),
                )
                done_data = {
                    "text": accumulated_text,
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                if tool_calls_accumulator:
                    done_data["tool_calls"] = tool_calls_accumulator

                await _write_event_anyio(
                    byte_stream,
                    {
                        "id": req_id,
                        "event": "done",
                        "data": done_data,
                    },
                )
                return

            resp = await self._openai.chat(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
                tools=tools,
                tool_choice=tool_choice,
            )
            text = ""
            tool_calls_data = None
            try:
                message = resp.choices[0].message
                text = message.content or ""

                # Extract tool calls if present
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls_data = []
                    for tc in message.tool_calls:
                        tool_calls_data.append(
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                        )
            except Exception:
                text = ""
                tool_calls_data = None

            # Build response data
            done_data = {
                "text": text,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            if tool_calls_data:
                done_data["tool_calls"] = tool_calls_data

            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "done",
                    "data": done_data,
                },
            )
        except Exception as error:
            logger.debug("[BROKER] llm.chat error", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )

    async def _handle_tool_call(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        tool_name = params.get("name")
        tool_args = params.get("args") or {}

        if not isinstance(tool_name, str) or not tool_name:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                },
            )
            return
        if not isinstance(tool_args, dict):
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                },
            )
            return

        try:
            result = self._tools.call(tool_name, tool_args)
        except KeyError:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "ToolNotAllowed",
                        "message": f"Tool not allowlisted: {tool_name}",
                    },
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] tool.call error", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_anyio(
            byte_stream, {"id": req_id, "event": "done", "data": {"result": result}}
        )

    async def _handle_mcp_list_tools(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        server_name = params.get("server")
        if not isinstance(server_name, str) or not server_name:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.server must be a string"},
                },
            )
            return

        if self._mcp_manager is None:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "MCPNotConfigured",
                        "message": "No broker MCP servers configured",
                    },
                },
            )
            return

        try:
            tools = await self._mcp_manager.list_tools(server_name)
        except KeyError as error:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "NotFound", "message": str(error)},
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] mcp.list_tools error", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_anyio(
            byte_stream, {"id": req_id, "event": "done", "data": {"tools": tools}}
        )

    async def _handle_mcp_call_tool_asyncio(
        self, req_id: str, params: dict[str, Any], writer: asyncio.StreamWriter
    ) -> None:
        server_name = params.get("server")
        tool_name = params.get("name")
        tool_args = params.get("args") or {}

        if not isinstance(server_name, str) or not server_name:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.server must be a string"},
                },
            )
            return
        if not isinstance(tool_name, str) or not tool_name:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                },
            )
            return
        if not isinstance(tool_args, dict):
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                },
            )
            return

        if self._mcp_manager is None:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "MCPNotConfigured",
                        "message": "No broker MCP servers configured",
                    },
                },
            )
            return

        try:
            result = await self._mcp_manager.call_tool(server_name, tool_name, tool_args)
        except KeyError as error:
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "NotFound", "message": str(error)},
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] mcp.call_tool error", exc_info=True)
            await _write_event_asyncio(
                writer,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_asyncio(
            writer, {"id": req_id, "event": "done", "data": {"result": result}}
        )

    async def _handle_mcp_call_tool(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        server_name = params.get("server")
        tool_name = params.get("name")
        tool_args = params.get("args") or {}

        if not isinstance(server_name, str) or not server_name:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.server must be a string"},
                },
            )
            return
        if not isinstance(tool_name, str) or not tool_name:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                },
            )
            return
        if not isinstance(tool_args, dict):
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                },
            )
            return

        if self._mcp_manager is None:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "MCPNotConfigured",
                        "message": "No broker MCP servers configured",
                    },
                },
            )
            return

        try:
            result = await self._mcp_manager.call_tool(server_name, tool_name, tool_args)
        except KeyError as error:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "NotFound", "message": str(error)},
                },
            )
            return
        except Exception as error:
            logger.debug("[BROKER] mcp.call_tool error", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                },
            )
            return

        await _write_event_anyio(
            byte_stream, {"id": req_id, "event": "done", "data": {"result": result}}
        )


class BrokerServer(_BaseBrokerServer):
    """
    Local broker server that listens on a Unix domain socket.

    Protocol (NDJSON):
      request: {"id":"...","method":"llm.chat","params":{...}}
      response stream:
        {"id":"...","event":"delta","data":{"text":"..."}}
        {"id":"...","event":"done","data":{...}}
      or:
        {"id":"...","event":"error","error":{"message":"...","type":"..."}}
    """

    def __init__(
        self,
        socket_path: Path,
        *,
        openai_backend: Optional[OpenAIChatBackend] = None,
        tool_registry: Optional[HostToolRegistry] = None,
        mcp_manager: Optional[BrokerMCPManager] = None,
        broker_mcp_servers: Optional[dict[str, dict[str, Any]]] = None,
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        super().__init__(
            openai_backend=openai_backend,
            tool_registry=tool_registry,
            mcp_manager=mcp_manager,
            broker_mcp_servers=broker_mcp_servers,
            event_handler=event_handler,
        )
        self.socket_path = Path(socket_path)
        self._server: Optional[asyncio.AbstractServer] = None

    async def start(self) -> None:
        # Most platforms enforce a short maximum length for AF_UNIX socket paths.
        # Keep a conservative bound to avoid opaque "AF_UNIX path too long" errors.
        if len(str(self.socket_path)) > 90:
            raise ValueError(
                f"Broker socket path too long for AF_UNIX: {self.socket_path} "
                f"(len={len(str(self.socket_path))})"
            )

        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()

        self._server = await asyncio.start_unix_server(
            self._handle_connection_asyncio, path=str(self.socket_path)
        )
        logger.info("[BROKER] Listening on UDS: %s", self.socket_path)

    async def aclose(self) -> None:
        server = getattr(self, "_server", None)
        if server is not None:
            try:
                server.close()
                await server.wait_closed()
            except Exception:
                logger.debug("[BROKER] Failed to close asyncio server", exc_info=True)
            finally:
                self._server = None

        await super().aclose()

        if self._server is not None:
            self._server.close()
            try:
                await self._server.wait_closed()
            finally:
                self._server = None

        try:
            if self.socket_path.exists():
                self.socket_path.unlink()
        except Exception:
            logger.debug("[BROKER] Failed to unlink socket path", exc_info=True)

    async def _handle_connection_asyncio(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            request_payload = await read_message(reader)
            request_id = request_payload.get("id")
            request_method = request_payload.get("method")
            request_params = request_payload.get("params") or {}

            async def write_event(event: dict[str, Any]) -> None:
                await write_message(writer, event)

            if not request_id or not request_method:
                await write_event(
                    {
                        "id": request_id or "",
                        "event": "error",
                        "error": {"type": "BadRequest", "message": "Missing id/method"},
                    }
                )
                return

            if request_method == "events.emit":
                await self._handle_events_emit_asyncio(request_id, request_params, write_event)
                return

            if request_method == "llm.chat":
                await self._handle_llm_chat_asyncio(request_id, request_params, write_event)
                return

            if request_method == "tool.call":
                await self._handle_tool_call_asyncio(request_id, request_params, write_event)
                return

            if request_method == "mcp.list_tools":
                await self._handle_mcp_list_tools_asyncio(request_id, request_params, write_event)
                return

            if request_method == "mcp.call_tool":
                await self._handle_mcp_call_tool_asyncio(request_id, request_params, write_event)
                return

            await write_event(
                {
                    "id": request_id,
                    "event": "error",
                    "error": {
                        "type": "MethodNotFound",
                        "message": f"Unknown method: {request_method}",
                    },
                }
            )

        except Exception as error:
            logger.debug("[BROKER] Connection handler error", exc_info=True)
            try:
                await write_message(
                    writer,
                    {
                        "id": "",
                        "event": "error",
                        "error": {"type": type(error).__name__, "message": str(error)},
                    },
                )
            except Exception:
                logger.debug(
                    "[BROKER] Failed writing error response to UDS asyncio writer",
                    exc_info=True,
                )
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                logger.debug("[BROKER] Failed closing UDS asyncio writer", exc_info=True)

    async def _handle_events_emit_asyncio(
        self,
        req_id: str,
        params: dict[str, Any],
        write_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        event_payload = params.get("event")
        if not isinstance(event_payload, dict):
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.event must be an object"},
                }
            )
            return

        try:
            if self._event_handler is not None:
                self._event_handler(event_payload)
        except Exception:
            logger.debug("[BROKER] event_handler raised", exc_info=True)

        await write_event({"id": req_id, "event": "done", "data": {"ok": True}})

    async def _handle_tool_call_asyncio(
        self,
        req_id: str,
        params: dict[str, Any],
        write_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        tool_name = params.get("name")
        tool_args = params.get("args") or {}

        if not isinstance(tool_name, str) or not tool_name:
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                }
            )
            return
        if not isinstance(tool_args, dict):
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                }
            )
            return

        try:
            result = self._tools.call(tool_name, tool_args)
        except KeyError:
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "ToolNotAllowed",
                        "message": f"Tool not allowlisted: {tool_name}",
                    },
                }
            )
            return
        except Exception as error:
            logger.debug("[BROKER] tool.call error", exc_info=True)
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                }
            )
            return

        await write_event({"id": req_id, "event": "done", "data": {"result": result}})

    async def _handle_llm_chat_asyncio(
        self,
        req_id: str,
        params: dict[str, Any],
        write_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        provider_name = params.get("provider") or "openai"
        if provider_name != "openai":
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "UnsupportedProvider",
                        "message": f"Unsupported provider: {provider_name}",
                    },
                }
            )
            return

        model = params.get("model")
        messages = params.get("messages")
        stream = bool(params.get("stream", False))
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")
        tools = params.get("tools")
        tool_choice = params.get("tool_choice")

        if not isinstance(model, str) or not model:
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.model must be a string"},
                }
            )
            return
        if not isinstance(messages, list):
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.messages must be a list"},
                }
            )
            return

        try:
            if stream:
                # Build kwargs for OpenAI chat call
                chat_kwargs = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                }
                if temperature is not None:
                    chat_kwargs["temperature"] = temperature
                if max_tokens is not None:
                    chat_kwargs["max_tokens"] = max_tokens
                if tools is not None:
                    chat_kwargs["tools"] = tools
                    logger.info("[BROKER_SERVER] Added %s tools to chat_kwargs", len(tools))
                else:
                    logger.warning("[BROKER_SERVER] No tools to add to chat_kwargs")
                if tool_choice is not None:
                    chat_kwargs["tool_choice"] = tool_choice
                    logger.info(
                        "[BROKER_SERVER] Added tool_choice=%s to chat_kwargs",
                        tool_choice,
                    )
                else:
                    logger.warning("[BROKER_SERVER] No tool_choice to add")

                logger.info(
                    "[BROKER_SERVER] Calling backend.chat() with %s kwargs: %s",
                    len(chat_kwargs),
                    list(chat_kwargs.keys()),
                )
                stream_iterator = await self._openai.chat(**chat_kwargs)

                accumulated_text = ""
                tool_calls_accumulator: list[dict[str, Any]] = []
                async for chunk in stream_iterator:
                    try:
                        delta = chunk.choices[0].delta
                        delta_text = getattr(delta, "content", None)
                        delta_tool_calls = getattr(delta, "tool_calls", None)
                    except Exception:
                        delta_text = None
                        delta_tool_calls = None

                    if delta_text:
                        accumulated_text += delta_text
                        await write_event(
                            {
                                "id": req_id,
                                "event": "delta",
                                "data": {"text": delta_text},
                            }
                        )

                    # Accumulate tool calls from deltas
                    if delta_tool_calls:
                        logger.info(
                            "[LITELLM_BACKEND] Received delta_tool_calls: %s",
                            delta_tool_calls,
                        )
                        for tool_call_delta in delta_tool_calls:
                            tool_call_index = tool_call_delta.index
                            # Extend tool_calls_data list if needed
                            while len(tool_calls_accumulator) <= tool_call_index:
                                tool_calls_accumulator.append(
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                )

                            # Merge delta into accumulated tool call
                            if tool_call_delta.id:
                                tool_calls_accumulator[tool_call_index]["id"] = tool_call_delta.id
                            if tool_call_delta.type:
                                tool_calls_accumulator[tool_call_index][
                                    "type"
                                ] = tool_call_delta.type
                            if hasattr(tool_call_delta, "function") and tool_call_delta.function:
                                if tool_call_delta.function.name:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "name"
                                    ] += tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    tool_calls_accumulator[tool_call_index]["function"][
                                        "arguments"
                                    ] += tool_call_delta.function.arguments

                # Build final response data
                logger.info(
                    "[LITELLM_BACKEND] Streaming complete. tool_calls_data=%s, "
                    "full_text length=%s",
                    tool_calls_accumulator,
                    len(accumulated_text),
                )
                done_data = {
                    "text": accumulated_text,
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                if tool_calls_accumulator:
                    done_data["tool_calls"] = tool_calls_accumulator

                await write_event(
                    {
                        "id": req_id,
                        "event": "done",
                        "data": done_data,
                    }
                )
                return

            # Build kwargs for OpenAI chat call
            chat_kwargs = {
                "model": model,
                "messages": messages,
                "stream": False,
            }
            if temperature is not None:
                chat_kwargs["temperature"] = temperature
            if max_tokens is not None:
                chat_kwargs["max_tokens"] = max_tokens
            if tools is not None:
                chat_kwargs["tools"] = tools
            if tool_choice is not None:
                chat_kwargs["tool_choice"] = tool_choice

            resp = await self._openai.chat(**chat_kwargs)

            text = ""
            tool_calls_data = None
            try:
                message = resp.choices[0].message
                text = message.content or ""

                # Extract tool calls if present
                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls_data = []
                    for tc in message.tool_calls:
                        tool_calls_data.append(
                            {
                                "id": tc.id,
                                "type": tc.type,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                        )
            except Exception:
                text = ""
                tool_calls_data = None

            # Build response data
            done_data = {
                "text": text,
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            if tool_calls_data:
                done_data["tool_calls"] = tool_calls_data

            await write_event(
                {
                    "id": req_id,
                    "event": "done",
                    "data": done_data,
                }
            )
        except Exception as error:
            logger.debug("[BROKER] llm.chat error", exc_info=True)
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(error).__name__, "message": str(error)},
                }
            )


class TcpBrokerServer(_BaseBrokerServer):
    """
    Broker server that listens on TCP (optionally TLS).

    Protocol is the same NDJSON framing used by the UDS broker.
    """

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        ssl_context: Optional[ssl.SSLContext] = None,
        openai_backend: Optional[OpenAIChatBackend] = None,
        tool_registry: Optional[HostToolRegistry] = None,
        mcp_manager: Optional[BrokerMCPManager] = None,
        broker_mcp_servers: Optional[dict[str, dict[str, Any]]] = None,
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
        control_handler: Optional[Callable[[dict], Awaitable[dict]]] = None,
    ):
        super().__init__(
            openai_backend=openai_backend,
            tool_registry=tool_registry,
            mcp_manager=mcp_manager,
            broker_mcp_servers=broker_mcp_servers,
            event_handler=event_handler,
            control_handler=control_handler,
        )
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.bound_port: Optional[int] = None
        self._serve_task: Optional[asyncio.Task[None]] = None

    async def start(self) -> None:
        # Create AnyIO TCP listener (doesn't block, just binds to port)
        self._listener = await anyio.create_tcp_listener(local_host=self.host, local_port=self.port)

        # Get the bound port
        try:
            sockname = self._listener.extra(anyio.abc.SocketAttribute.raw_socket).getsockname()
            self.bound_port = int(sockname[1])
        except Exception:
            self.bound_port = None

        scheme = "tls" if self.ssl_context is not None else "tcp"
        listen_port = self.bound_port if self.bound_port is not None else self.port
        logger.info(
            "[BROKER] Listening on %s: %s:%s",
            scheme,
            self.host,
            listen_port,
        )

        # Unlike asyncio's start_server(), AnyIO listeners don't automatically start
        # serving on enter; they require an explicit serve() loop. Run it in the
        # background for the duration of the async context manager.
        if self._serve_task is None or self._serve_task.done():
            self._serve_task = asyncio.create_task(self.serve(), name="tactus-broker-tcp-serve")

    async def aclose(self) -> None:
        task = self._serve_task
        self._serve_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("[BROKER] TCP serve task cancelled during shutdown")

        await super().aclose()
