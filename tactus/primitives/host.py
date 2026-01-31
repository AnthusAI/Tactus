"""
Host Primitive - brokered host capabilities for the runtime container.

This primitive is intended to be used inside the sandboxed runtime container.
It delegates allowlisted operations to the trusted host-side broker via the
`TACTUS_BROKER_SOCKET` transport.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from tactus.broker.client import BrokerClient
from tactus.utils.asyncio_helpers import clear_closed_event_loop


class HostPrimitive:
    """Provides access to allowlisted host-side tools via the broker."""

    def __init__(self, client: Optional[BrokerClient] = None):
        self._client = client or BrokerClient.from_environment()
        self._registry = None
        if self._client is None:
            # Allow Host.call() to work in non-sandboxed runs (and in deterministic tests)
            # without requiring a broker transport, while still staying deny-by-default.
            from tactus.broker.server import HostToolRegistry

            self._registry = HostToolRegistry.default()

    def _run_coro(self, coroutine: Any) -> Any:
        """
        Run an async coroutine from Lua's synchronous context.

        Mirrors the approach used by `ToolHandle` for async tool handlers.
        """
        try:
            asyncio.get_running_loop()

            import threading

            thread_result = {"value": None, "exception": None}

            def run_in_thread():
                try:
                    thread_result["value"] = asyncio.run(coroutine)
                except Exception as error:
                    thread_result["exception"] = error

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if thread_result["exception"]:
                raise thread_result["exception"]
            return thread_result["value"]

        except RuntimeError:
            clear_closed_event_loop()
            return asyncio.run(coroutine)

    def _lua_to_python(self, value: Any) -> Any:
        if value is None:
            return None
        if hasattr(value, "items") and not isinstance(value, dict):
            return {k: self._lua_to_python(v) for k, v in value.items()}
        if isinstance(value, dict):
            return {k: self._lua_to_python(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._lua_to_python(v) for v in value]
        return value

    def call(self, name: str, args: Optional[dict[str, Any]] = None) -> Any:
        """
        Call an allowlisted host tool via the broker.

        Example (Lua):
            local result = Host.call("host.ping", {value = 1})
        """
        if not isinstance(name, str) or not name:
            raise ValueError("Host.call requires a non-empty tool name string")

        args_payload = self._lua_to_python(args) or {}
        if not isinstance(args_payload, dict):
            raise ValueError("Host.call args must be an object/table")

        if self._client is not None:
            return self._run_coro(self._client.call_tool(name=name, args=args_payload))

        if self._registry is not None:
            try:
                return self._registry.call(name, args_payload)
            except KeyError as error:
                raise RuntimeError(f"Tool not allowlisted: {name}") from error

        raise RuntimeError("Host.call requires TACTUS_BROKER_SOCKET to be set")
