"""
Broker log handler for container event streaming.

Used inside the runtime container to forward structured log events to the
host-side broker for real-time streaming to the IDE frontend.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
from typing import Any, Optional

from tactus.protocols.models import LogEvent, CostEvent

logger = logging.getLogger(__name__)


class BrokerLogHandler:
    """
    Log handler that forwards events to the broker via background thread.

    Uses a dedicated thread with its own event loop to ensure events are
    sent in real-time, regardless of whether the main execution yields control.
    This enables true streaming of agent responses to the frontend.

    The broker socket path is read from `TACTUS_BROKER_SOCKET`.
    """

    def __init__(self, socket_path: str):
        self._socket_path = socket_path
        self.cost_events: list[CostEvent] = []

        # Thread-safe queue for events to send
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()

        # Background worker thread
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown = threading.Event()
        self._started = False
        self._start_lock = threading.Lock()

    @property
    def supports_streaming(self) -> bool:
        """Broker handler supports real-time streaming."""
        return True

    @classmethod
    def from_environment(cls) -> Optional["BrokerLogHandler"]:
        """Create handler from TACTUS_BROKER_SOCKET environment variable."""
        socket_path = os.environ.get("TACTUS_BROKER_SOCKET")
        if not socket_path:
            return None
        return cls(socket_path)

    def _ensure_worker_started(self) -> None:
        """Start background worker thread if not already running."""
        with self._start_lock:
            if not self._started:
                self._worker_thread = threading.Thread(
                    target=self._worker,
                    name="BrokerLogWorker",
                    daemon=True,
                )
                self._worker_thread.start()
                self._started = True
                logger.debug("[BROKER_LOG] Background worker started")

    def _worker(self) -> None:
        """
        Background thread that sends events to broker.

        Runs in its own event loop to avoid blocking the main execution.
        Creates a fresh BrokerClient connection for thread safety.
        """
        from tactus.broker.client import BrokerClient

        # Create fresh client in this thread's event loop
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)
        client = BrokerClient(self._socket_path)

        try:
            while not self._shutdown.is_set():
                try:
                    # Wait for event with timeout to check shutdown flag
                    event_payload = self._queue.get(timeout=0.05)

                    # Send event to broker
                    event_loop.run_until_complete(client.emit_event(event_payload))
                    self._queue.task_done()

                except queue.Empty:
                    continue
                except Exception as error:
                    # Best effort - don't crash worker on individual failures
                    logger.debug("[BROKER_LOG] Failed to emit event: %s", error)
                    try:
                        self._queue.task_done()
                    except ValueError:
                        pass
        finally:
            event_loop.close()
            logger.debug("[BROKER_LOG] Background worker stopped")

    def log(self, event: LogEvent) -> None:
        """
        Forward an event to the broker.

        Events are queued and sent by a background thread, enabling
        real-time streaming without blocking procedure execution.
        """
        # Track cost events for aggregation (mirrors IDELogHandler behavior)
        if isinstance(event, CostEvent):
            self.cost_events.append(event)

        # Serialize to JSON-friendly dict
        event_payload = event.model_dump(mode="json")

        # Normalize timestamp formatting for downstream consumers.
        iso_string = event.timestamp.isoformat()
        has_timezone_marker = (
            iso_string.endswith("Z") or "+" in iso_string or iso_string.count("-") > 2
        )
        if not has_timezone_marker:
            iso_string += "Z"
        event_payload["timestamp"] = iso_string

        # Ensure worker is running
        self._ensure_worker_started()

        # Queue event for background sending (non-blocking)
        try:
            self._queue.put_nowait(event_payload)
        except queue.Full:
            # Drop event if queue is full (shouldn't happen with unlimited queue)
            logger.debug("[BROKER_LOG] Queue full, dropping event")

    async def flush(self) -> None:
        """
        Wait for all queued events to be sent.

        Call this before procedure completion to ensure all events
        are delivered to the broker before the container exits.
        """
        if not self._started:
            return

        # Wait for queue to drain
        max_wait = 5.0  # Maximum wait time in seconds
        poll_interval = 0.05
        elapsed = 0.0

        while not self._queue.empty() and elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if not self._queue.empty():
            remaining = self._queue.qsize()
            logger.warning("[BROKER_LOG] Flush timeout with %s events remaining", remaining)

        # Signal worker to shutdown
        self._shutdown.set()

        # Wait for worker thread to finish
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
            if self._worker_thread.is_alive():
                logger.warning("[BROKER_LOG] Worker thread did not stop cleanly")
