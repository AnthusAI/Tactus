"""
Broker client for use inside the runtime container.

Uses a broker transport selected at runtime:
- `stdio` (recommended for Docker Desktop): requests are written to stderr with a marker and
  responses are read from stdin as NDJSON.
- Unix domain sockets (UDS): retained for non-Docker/host testing.
"""

import asyncio
import json
import logging
import os
import ssl
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from tactus.broker.protocol import read_message, write_message
from tactus.broker.stdio import STDIO_REQUEST_PREFIX, STDIO_TRANSPORT_VALUE

logger = logging.getLogger(__name__)


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class _StdioBrokerTransport:
    def __init__(self):
        self._write_lock = threading.Lock()
        self._pending_requests: dict[
            str, tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]
        ] = {}
        # Backward-compatible alias used in tests and older code paths.
        self._pending = self._pending_requests
        self._pending_lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        # Backward-compatible alias used in tests and older code paths.
        self._stop = self._shutdown_event

    def _ensure_reader_thread(self) -> None:
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return

        self._reader_thread = threading.Thread(
            target=self._read_loop,
            name="tactus-broker-stdio-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def _read_loop(self) -> None:
        while not self._shutdown_event.is_set():
            input_line = sys.stdin.buffer.readline()
            if not input_line:
                return
            try:
                event_payload = json.loads(input_line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            request_id_value = event_payload.get("id")
            if not isinstance(request_id_value, str):
                continue

            with self._pending_lock:
                pending_request = self._pending_requests.get(request_id_value)
            if pending_request is None:
                continue

            event_loop, response_queue = pending_request
            try:
                event_loop.call_soon_threadsafe(response_queue.put_nowait, event_payload)
            except RuntimeError:
                # Loop is closed or unavailable; ignore.
                continue

    async def aclose(self) -> None:
        self._shutdown_event.set()
        thread = self._reader_thread
        if thread is None or not thread.is_alive():
            return
        try:
            await asyncio.to_thread(thread.join, 0.5)
        except Exception:
            return

    async def request(
        self, request_id: str, method: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        self._ensure_reader_thread()
        event_loop = asyncio.get_running_loop()
        response_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._pending_lock:
            self._pending_requests[request_id] = (event_loop, response_queue)

        try:
            request_payload = _json_dumps({"id": request_id, "method": method, "params": params})
            with self._write_lock:
                sys.stderr.write(f"{STDIO_REQUEST_PREFIX}{request_payload}\n")
                sys.stderr.flush()

            while True:
                event_payload = await response_queue.get()
                yield event_payload
                if event_payload.get("event") in ("done", "error"):
                    return
        finally:
            with self._pending_lock:
                self._pending_requests.pop(request_id, None)


_STDIO_TRANSPORT = _StdioBrokerTransport()


async def close_stdio_transport() -> None:
    await _STDIO_TRANSPORT.aclose()


class BrokerClient:
    def __init__(self, socket_path: str | Path):
        self.socket_path = str(socket_path)

    @classmethod
    def from_environment(cls) -> Optional["BrokerClient"]:
        socket_path = os.environ.get("TACTUS_BROKER_SOCKET")
        if not socket_path:
            return None
        return cls(socket_path)

    async def _request(self, method: str, params: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        request_id = uuid.uuid4().hex

        if self.socket_path == STDIO_TRANSPORT_VALUE:
            async for event_payload in _STDIO_TRANSPORT.request(request_id, method, params):
                # Responses are already correlated by req_id; add a defensive filter anyway.
                if event_payload.get("id") == request_id:
                    yield event_payload
            return

        if self.socket_path.startswith(("tcp://", "tls://")):
            use_tls = self.socket_path.startswith("tls://")
            host_and_port = self.socket_path.split("://", 1)[1]
            if "/" in host_and_port:
                host_and_port = host_and_port.split("/", 1)[0]
            if ":" not in host_and_port:
                raise ValueError(
                    "Invalid broker endpoint: "
                    f"{self.socket_path}. Expected tcp://host:port or tls://host:port"
                )
            host, port_text = host_and_port.rsplit(":", 1)
            try:
                port = int(port_text)
            except ValueError as error:
                raise ValueError(f"Invalid broker port in endpoint: {self.socket_path}") from error

            ssl_context: ssl.SSLContext | None = None
            if use_tls:
                ssl_context = ssl.create_default_context()
                cafile = os.environ.get("TACTUS_BROKER_TLS_CA_FILE")
                if cafile:
                    ssl_context.load_verify_locations(cafile=cafile)

                if os.environ.get("TACTUS_BROKER_TLS_INSECURE") in ("1", "true", "yes"):
                    ssl_context.check_hostname = False
                    ssl_context.verify_mode = ssl.CERT_NONE

            reader, writer = await asyncio.open_connection(host, port, ssl=ssl_context)
            logger.info(
                "[BROKER_CLIENT] Writing message to broker, params keys: %s",
                list(params.keys()),
            )
            try:
                await write_message(writer, {"id": request_id, "method": method, "params": params})
            except TypeError as error:
                logger.error("[BROKER_CLIENT] JSON serialization error: %s", error)
                logger.error("[BROKER_CLIENT] Params: %s", params)
                raise

            try:
                while True:
                    event_payload = await read_message(reader)
                    if event_payload.get("id") != request_id:
                        continue
                    yield event_payload
                    if event_payload.get("event") in ("done", "error"):
                        return
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        await write_message(writer, {"id": request_id, "method": method, "params": params})

        try:
            while True:
                event_payload = await read_message(reader)
                # Ignore unrelated messages (defensive; current server is 1-req/conn).
                if event_payload.get("id") != request_id:
                    continue
                yield event_payload
                if event_payload.get("event") in ("done", "error"):
                    return
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    def llm_chat(
        self,
        *,
        provider: str,
        model: str,
        messages: list[dict[str, Any]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool,
        tools: Optional[list[dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        request_params: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if temperature is not None:
            request_params["temperature"] = temperature
        if max_tokens is not None:
            request_params["max_tokens"] = max_tokens
        if tools is not None:
            request_params["tools"] = tools
            logger.info("[BROKER_CLIENT] Adding %s tools to params", len(tools))
        else:
            logger.warning("[BROKER_CLIENT] No tools to add to params")
        if tool_choice is not None:
            request_params["tool_choice"] = tool_choice
            logger.info("[BROKER_CLIENT] Adding tool_choice=%s to params", tool_choice)
        return self._request("llm.chat", request_params)

    async def call_tool(self, *, name: str, args: dict[str, Any]) -> Any:
        """
        Call an allowlisted host tool via the broker.

        Returns the decoded `result` payload from the broker.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("tool name must be a non-empty string")
        if not isinstance(args, dict):
            raise ValueError("tool args must be an object")

        async for event_payload in self._request("tool.call", {"name": name, "args": args}):
            event_type = event_payload.get("event")
            if event_type == "done":
                data = event_payload.get("data") or {}
                return data.get("result")
            if event_type == "error":
                error_payload = event_payload.get("error") or {}
                raise RuntimeError(error_payload.get("message") or "Broker tool error")

        raise RuntimeError("Broker tool call ended without a response")

    async def emit_event(self, event: dict[str, Any]) -> None:
        async for _ in self._request("events.emit", {"event": event}):
            pass
