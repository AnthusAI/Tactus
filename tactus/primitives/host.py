"""
Host Primitive - brokered host capabilities for the runtime container.

This primitive is intended to be used inside the sandboxed runtime container.
It delegates allowlisted operations to the trusted host-side broker via the
`TACTUS_BROKER_SOCKET` transport.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from tactus.broker.client import BrokerClient


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

    def _run_coro(self, coro):
        """
        Run an async coroutine from Lua's synchronous context.

        Mirrors the approach used by `ToolHandle` for async tool handlers.
        """
        try:
            asyncio.get_running_loop()

            import threading

            result_container = {"value": None, "exception": None}

            def run_in_thread():
                try:
                    result_container["value"] = asyncio.run(coro)
                except Exception as e:
                    result_container["exception"] = e

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if result_container["exception"]:
                raise result_container["exception"]
            return result_container["value"]

        except RuntimeError:
            return asyncio.run(coro)

    def _lua_to_python(self, obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "items") and not isinstance(obj, dict):
            return {k: self._lua_to_python(v) for k, v in obj.items()}
        if isinstance(obj, dict):
            return {k: self._lua_to_python(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._lua_to_python(v) for v in obj]
        return obj

    def call(self, name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """
        Call an allowlisted host tool via the broker.

        Example (Lua):
            local result = Host.call("host.ping", {value = 1})
        """
        if not isinstance(name, str) or not name:
            raise ValueError("Host.call requires a non-empty tool name string")

        args_dict = self._lua_to_python(args) or {}
        if not isinstance(args_dict, dict):
            raise ValueError("Host.call args must be an object/table")

        if self._client is not None:
            return self._run_coro(self._client.call_tool(name=name, args=args_dict))

        if self._registry is not None:
            try:
                return self._registry.call(name, args_dict)
            except KeyError as e:
                raise RuntimeError(f"Tool not allowlisted: {name}") from e

        raise RuntimeError("Host.call requires TACTUS_BROKER_SOCKET to be set")
