"""
Broker log handler for container event streaming over UDS.

Used inside the runtime container to forward structured log events to the
host-side broker without requiring container networking.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Optional

from tactus.broker.client import BrokerClient
from tactus.protocols.models import LogEvent, CostEvent


class BrokerLogHandler:
    """
    Log handler that forwards events to the broker via Unix domain socket.

    The broker socket path is read from `TACTUS_BROKER_SOCKET`.
    """

    def __init__(self, client: BrokerClient):
        self._client = client
        self.cost_events: list[CostEvent] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_lock = threading.Lock()

    def _get_or_create_loop(self) -> asyncio.AbstractEventLoop:
        """Get the event loop, creating one if needed for cross-thread calls."""
        with self._loop_lock:
            if self._loop is None or self._loop.is_closed():
                try:
                    self._loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop - create a new one
                    self._loop = asyncio.new_event_loop()
            return self._loop

    @classmethod
    def from_environment(cls) -> Optional["BrokerLogHandler"]:
        client = BrokerClient.from_environment()
        if client is None:
            return None
        return cls(client)

    def log(self, event: LogEvent) -> None:
        # Track cost events for aggregation (mirrors IDELogHandler behavior)
        if isinstance(event, CostEvent):
            self.cost_events.append(event)

        # Serialize to JSON-friendly dict
        event_dict = event.model_dump(mode="json")

        # Normalize timestamp formatting for downstream consumers.
        iso_string = event.timestamp.isoformat()
        if not (iso_string.endswith("Z") or "+" in iso_string or iso_string.count("-") > 2):
            iso_string += "Z"
        event_dict["timestamp"] = iso_string

        # Best-effort forwarding; never crash the procedure due to streaming.
        try:
            # Try to get the running loop first
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - schedule and don't wait
                loop.create_task(self._client.emit_event(event_dict))
            except RuntimeError:
                # No running loop - we're being called from a sync thread.
                # Use asyncio.run() which creates a new event loop for this call.
                asyncio.run(self._client.emit_event(event_dict))
        except Exception:
            # Swallow errors; container remains networkless and secretless even if streaming fails.
            pass
