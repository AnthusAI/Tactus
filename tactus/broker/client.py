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
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from tactus.broker.stdio import STDIO_REQUEST_PREFIX, STDIO_TRANSPORT_VALUE


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class _StdioBrokerTransport:
    def __init__(self):
        self._write_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._reader: Optional[asyncio.StreamReader] = None

    async def _ensure_reader(self) -> None:
        if self._reader_task is not None:
            return

        # Attach stdin as an asyncio stream to avoid blocking threads that can hang
        # `asyncio.run()` shutdown (Docker sandbox relies on keeping stdin open).
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin.buffer)
        self._reader = reader
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        if self._reader is None:
            return
        while True:
            line = await self._reader.readline()
            if not line:
                return
            try:
                event = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue

            req_id = event.get("id")
            if not isinstance(req_id, str):
                continue
            queue = self._pending.get(req_id)
            if queue is None:
                continue
            queue.put_nowait(event)

    async def request(
        self, req_id: str, method: str, params: dict[str, Any]
    ) -> AsyncIterator[dict[str, Any]]:
        await self._ensure_reader()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._pending[req_id] = queue

        try:
            payload = _json_dumps({"id": req_id, "method": method, "params": params})
            async with self._write_lock:
                sys.stderr.write(f"{STDIO_REQUEST_PREFIX}{payload}\n")
                sys.stderr.flush()

            while True:
                event = await queue.get()
                yield event
                if event.get("event") in ("done", "error"):
                    return
        finally:
            self._pending.pop(req_id, None)


_STDIO_TRANSPORT = _StdioBrokerTransport()


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
            writer.write(
                (_json_dumps({"id": req_id, "method": method, "params": params}) + "\n").encode(
                    "utf-8"
                )
            )
            await writer.drain()

            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        return
                    event = json.loads(line.decode("utf-8"))
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
        writer.write(
            (_json_dumps({"id": req_id, "method": method, "params": params}) + "\n").encode("utf-8")
        )
        await writer.drain()

        try:
            while True:
                line = await reader.readline()
                if not line:
                    return
                event = json.loads(line.decode("utf-8"))
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

    async def emit_event(self, event: dict[str, Any]) -> None:
        async for _ in self._request("events.emit", {"event": event}):
            pass
