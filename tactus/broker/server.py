"""
Host-side broker server (local UDS transport).

This is intentionally narrow: it exposes only allowlisted operations required
by the runtime container.
"""

import asyncio
import json
import logging
import os
import ssl
from collections.abc import Awaitable, Callable
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


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


async def _write_event_anyio(stream: anyio.abc.ByteStream, event: dict[str, Any]) -> None:
    """Write an event using length-prefixed protocol."""
    await write_message_anyio(stream, event)


@dataclass(frozen=True)
class OpenAIChatConfig:
    api_key_env: str = "OPENAI_API_KEY"


class OpenAIChatBackend:
    """
    Minimal OpenAI chat-completions backend used by the broker.

    Credentials are read from the broker process environment.
    """

    def __init__(self, config: Optional[OpenAIChatConfig] = None):
        self._config = config or OpenAIChatConfig()

        # Lazy-init the client so unit tests can run without OpenAI installed/configured.
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        from openai import AsyncOpenAI

        api_key = os.environ.get(self._config.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing OpenAI API key in environment: {self._config.api_key_env}")

        self._client = AsyncOpenAI(api_key=api_key)
        return self._client

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool,
    ):
        client = self._get_client()

        kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if stream:
            return await client.chat.completions.create(**kwargs, stream=True)

        return await client.chat.completions.create(**kwargs)


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


class _BaseBrokerServer:
    def __init__(
        self,
        *,
        openai_backend: Optional[OpenAIChatBackend] = None,
        tool_registry: Optional[HostToolRegistry] = None,
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        self._listener = None
        self._openai = openai_backend or OpenAIChatBackend()
        self._tools = tool_registry or HostToolRegistry.default()
        self._event_handler = event_handler

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

    async def __aenter__(self) -> "_BaseBrokerServer":
        await self.start()
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
            req = await read_message_anyio(buffered_stream)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}

            if not req_id or not method:
                await _write_event_anyio(
                    byte_stream,
                    {
                        "id": req_id or "",
                        "event": "error",
                        "error": {"type": "BadRequest", "message": "Missing id/method"},
                    },
                )
                return

            if method == "events.emit":
                await self._handle_events_emit(req_id, params, byte_stream)
                return

            if method == "llm.chat":
                await self._handle_llm_chat(req_id, params, byte_stream)
                return

            if method == "tool.call":
                await self._handle_tool_call(req_id, params, byte_stream)
                return

            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "MethodNotFound", "message": f"Unknown method: {method}"},
                },
            )

        except Exception as e:
            logger.debug("[BROKER] Connection handler error", exc_info=True)
            try:
                await _write_event_anyio(
                    byte_stream,
                    {
                        "id": "",
                        "event": "error",
                        "error": {"type": type(e).__name__, "message": str(e)},
                    },
                )
            except Exception:
                pass
        finally:
            try:
                await byte_stream.aclose()
            except Exception:
                pass

    async def _handle_events_emit(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        event = params.get("event")
        if not isinstance(event, dict):
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
                self._event_handler(event)
        except Exception:
            logger.debug("[BROKER] event_handler raised", exc_info=True)

        await _write_event_anyio(byte_stream, {"id": req_id, "event": "done", "data": {"ok": True}})

    async def _handle_llm_chat(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        provider = params.get("provider") or "openai"
        if provider != "openai":
            await _write_event_anyio(
                byte_stream,
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

        model = params.get("model")
        messages = params.get("messages")
        stream = bool(params.get("stream", False))
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")

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
                stream_iter = await self._openai.chat(
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
                    await _write_event_anyio(
                        byte_stream, {"id": req_id, "event": "delta", "data": {"text": text}}
                    )

                await _write_event_anyio(
                    byte_stream,
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

            resp = await self._openai.chat(
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

            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "done",
                    "data": {
                        "text": text,
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    },
                },
            )
        except Exception as e:
            logger.debug("[BROKER] llm.chat error", exc_info=True)
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(e).__name__, "message": str(e)},
                },
            )

    async def _handle_tool_call(
        self, req_id: str, params: dict[str, Any], byte_stream: anyio.abc.ByteStream
    ) -> None:
        name = params.get("name")
        args = params.get("args") or {}

        if not isinstance(name, str) or not name:
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                },
            )
            return
        if not isinstance(args, dict):
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
            result = self._tools.call(name, args)
        except KeyError:
            await _write_event_anyio(
                byte_stream,
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
            await _write_event_anyio(
                byte_stream,
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(e).__name__, "message": str(e)},
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
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        super().__init__(
            openai_backend=openai_backend, tool_registry=tool_registry, event_handler=event_handler
        )
        self.socket_path = Path(socket_path)
        self._server: asyncio.AbstractServer | None = None

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
        logger.info(f"[BROKER] Listening on UDS: {self.socket_path}")

    async def aclose(self) -> None:
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
            req = await read_message(reader)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}

            async def write_event(event: dict[str, Any]) -> None:
                await write_message(writer, event)

            if not req_id or not method:
                await write_event(
                    {
                        "id": req_id or "",
                        "event": "error",
                        "error": {"type": "BadRequest", "message": "Missing id/method"},
                    }
                )
                return

            if method == "events.emit":
                await self._handle_events_emit_asyncio(req_id, params, write_event)
                return

            if method == "llm.chat":
                await self._handle_llm_chat_asyncio(req_id, params, write_event)
                return

            if method == "tool.call":
                await self._handle_tool_call_asyncio(req_id, params, write_event)
                return

            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "MethodNotFound", "message": f"Unknown method: {method}"},
                }
            )

        except Exception as e:
            logger.debug("[BROKER] Connection handler error", exc_info=True)
            try:
                await write_message(
                    writer,
                    {
                        "id": "",
                        "event": "error",
                        "error": {"type": type(e).__name__, "message": str(e)},
                    },
                )
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _handle_events_emit_asyncio(
        self,
        req_id: str,
        params: dict[str, Any],
        write_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        event = params.get("event")
        if not isinstance(event, dict):
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
                self._event_handler(event)
        except Exception:
            logger.debug("[BROKER] event_handler raised", exc_info=True)

        await write_event({"id": req_id, "event": "done", "data": {"ok": True}})

    async def _handle_tool_call_asyncio(
        self,
        req_id: str,
        params: dict[str, Any],
        write_event: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        name = params.get("name")
        args = params.get("args") or {}

        if not isinstance(name, str) or not name:
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.name must be a string"},
                }
            )
            return
        if not isinstance(args, dict):
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": "BadRequest", "message": "params.args must be an object"},
                }
            )
            return

        try:
            result = self._tools.call(name, args)
        except KeyError:
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "ToolNotAllowed",
                        "message": f"Tool not allowlisted: {name}",
                    },
                }
            )
            return
        except Exception as e:
            logger.debug("[BROKER] tool.call error", exc_info=True)
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(e).__name__, "message": str(e)},
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
        provider = params.get("provider") or "openai"
        if provider != "openai":
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {
                        "type": "UnsupportedProvider",
                        "message": f"Unsupported provider: {provider}",
                    },
                }
            )
            return

        model = params.get("model")
        messages = params.get("messages")
        stream = bool(params.get("stream", False))
        temperature = params.get("temperature")
        max_tokens = params.get("max_tokens")

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
                stream_iter = await self._openai.chat(
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
                    await write_event({"id": req_id, "event": "delta", "data": {"text": text}})

                await write_event(
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
                    }
                )
                return

            resp = await self._openai.chat(
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

            await write_event(
                {
                    "id": req_id,
                    "event": "done",
                    "data": {
                        "text": text,
                        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    },
                }
            )
        except Exception as e:
            logger.debug("[BROKER] llm.chat error", exc_info=True)
            await write_event(
                {
                    "id": req_id,
                    "event": "error",
                    "error": {"type": type(e).__name__, "message": str(e)},
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
        ssl_context: ssl.SSLContext | None = None,
        openai_backend: Optional[OpenAIChatBackend] = None,
        tool_registry: Optional[HostToolRegistry] = None,
        event_handler: Optional[Callable[[dict[str, Any]], None]] = None,
    ):
        super().__init__(
            openai_backend=openai_backend, tool_registry=tool_registry, event_handler=event_handler
        )
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.bound_port: int | None = None
        self._serve_task: asyncio.Task[None] | None = None

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
        logger.info(
            f"[BROKER] Listening on {scheme}: {self.host}:{self.bound_port if self.bound_port is not None else self.port}"
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
                pass

        await super().aclose()
