"""
Broker client for use inside the runtime container.

Uses a broker transport selected at runtime:
- `stdio` (recommended for Docker Desktop): requests are written to stderr with a marker and
  responses are read from stdin as NDJSON.
- Unix domain sockets (UDS): retained for non-Docker/host testing.
"""

import asyncio
import json
import os
import ssl
import sys
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from tactus.broker.protocol import read_message, write_message
from tactus.broker.stdio import STDIO_REQUEST_PREFIX, STDIO_TRANSPORT_VALUE


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class _StdioBrokerTransport:
    def __init__(self):
        self._write_lock = threading.Lock()
        self._pending: dict[
            str, tuple[asyncio.AbstractEventLoop, asyncio.Queue[dict[str, Any]]]
        ] = {}
        self._pending_lock = threading.Lock()
        self._reader_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

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
        while not self._stop.is_set():
            line = sys.stdin.buffer.readline()
            if not line:
                return
            try:
                event = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            req_id = event.get("id")
            if not isinstance(req_id, str):
                continue

            with self._pending_lock:
                pending = self._pending.get(req_id)
            if pending is None:
                continue

            loop, queue = pending
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except RuntimeError:
                # Loop is closed or unavailable; ignore.
                continue

    async def aclose(self) -> None:
        self._stop.set()
        thread = self._reader_thread
        if thread is None or not thread.is_alive():
            return
        try:
            await asyncio.to_thread(thread.join, 0.5)
        except Exception:
            return

    async def request(
        self, req_id: str, method: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        self._ensure_reader_thread()
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._pending_lock:
            self._pending[req_id] = (loop, queue)

        try:
            payload = _json_dumps({"id": req_id, "method": method, "params": params})
            with self._write_lock:
                sys.stderr.write(f"{STDIO_REQUEST_PREFIX}{payload}\n")
                sys.stderr.flush()

            while True:
                event = await queue.get()
                yield event
                if event.get("event") in ("done", "error"):
                    return
        finally:
            with self._pending_lock:
                self._pending.pop(req_id, None)


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
        req_id = uuid.uuid4().hex

        if self.socket_path == STDIO_TRANSPORT_VALUE:
            async for event in _STDIO_TRANSPORT.request(req_id, method, params):
                # Responses are already correlated by req_id; add a defensive filter anyway.
                if event.get("id") == req_id:
                    yield event
            return

        if self.socket_path.startswith(("tcp://", "tls://")):
            use_tls = self.socket_path.startswith("tls://")
            host_port = self.socket_path.split("://", 1)[1]
            if "/" in host_port:
                host_port = host_port.split("/", 1)[0]
            if ":" not in host_port:
                raise ValueError(
                    f"Invalid broker endpoint: {self.socket_path}. Expected tcp://host:port or tls://host:port"
                )
            host, port_str = host_port.rsplit(":", 1)
            try:
                port = int(port_str)
            except ValueError as e:
                raise ValueError(f"Invalid broker port in endpoint: {self.socket_path}") from e

            ssl_ctx: ssl.SSLContext | None = None
            if use_tls:
                ssl_ctx = ssl.create_default_context()
                cafile = os.environ.get("TACTUS_BROKER_TLS_CA_FILE")
                if cafile:
                    ssl_ctx.load_verify_locations(cafile=cafile)

                if os.environ.get("TACTUS_BROKER_TLS_INSECURE") in ("1", "true", "yes"):
                    ssl_ctx.check_hostname = False
                    ssl_ctx.verify_mode = ssl.CERT_NONE

            reader, writer = await asyncio.open_connection(host, port, ssl=ssl_ctx)
            await write_message(writer, {"id": req_id, "method": method, "params": params})

            try:
                while True:
                    event = await read_message(reader)
                    if event.get("id") != req_id:
                        continue
                    yield event
                    if event.get("event") in ("done", "error"):
                        return
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        await write_message(writer, {"id": req_id, "method": method, "params": params})

        try:
            while True:
                event = await read_message(reader)
                # Ignore unrelated messages (defensive; current server is 1-req/conn).
                if event.get("id") != req_id:
                    continue
                yield event
                if event.get("event") in ("done", "error"):
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
    ) -> AsyncIterator[dict[str, Any]]:
        params: dict[str, Any] = {
            "provider": provider,
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        if temperature is not None:
            params["temperature"] = temperature
        if max_tokens is not None:
            params["max_tokens"] = max_tokens
        return self._request("llm.chat", params)

    async def call_tool(self, *, name: str, args: dict[str, Any]) -> Any:
        """
        Call an allowlisted host tool via the broker.

        Returns the decoded `result` payload from the broker.
        """
        if not isinstance(name, str) or not name:
            raise ValueError("tool name must be a non-empty string")
        if not isinstance(args, dict):
            raise ValueError("tool args must be an object")

        async for event in self._request("tool.call", {"name": name, "args": args}):
            event_type = event.get("event")
            if event_type == "done":
                data = event.get("data") or {}
                return data.get("result")
            if event_type == "error":
                err = event.get("error") or {}
                raise RuntimeError(err.get("message") or "Broker tool error")

        raise RuntimeError("Broker tool call ended without a response")

    async def emit_event(self, event: dict[str, Any]) -> None:
        async for _ in self._request("events.emit", {"event": event}):
            pass
