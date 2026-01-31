"""
IDE Log Handler for event collection and streaming.

Collects log events in a queue for streaming to IDE frontend.
"""

import logging
import queue

from tactus.protocols.models import CostEvent, LogEvent

logger = logging.getLogger(__name__)


class IDELogHandler:
    """
    IDE log handler that collects events for streaming.

    Receives structured log events and stores them in a queue
    for retrieval and streaming to the IDE frontend.
    """

    supports_streaming = True

    def __init__(self):
        """Initialize IDE log handler."""
        self.events: queue.Queue[LogEvent] = queue.Queue()
        self.cost_events: list[CostEvent] = []  # Track cost events for aggregation
        logger.debug("IDELogHandler initialized")

    def log(self, event: LogEvent) -> None:
        """
        Collect log event for streaming.

        Args:
            event: Structured log event
        """
        # CRITICAL DEBUG: Log every call to this method
        logger.info(
            "[IDE_LOG] log() called with event type: %s",
            type(event).__name__,
        )

        # Track cost events for aggregation
        from tactus.protocols.models import CostEvent, AgentStreamChunkEvent

        if isinstance(event, CostEvent):
            self.cost_events.append(event)

        # Debug logging for streaming events
        if isinstance(event, AgentStreamChunkEvent):
            logger.info(
                "[IDE_LOG] Received AgentStreamChunkEvent: agent=%s, "
                "chunk_len=%s, accumulated_len=%s",
                event.agent_name,
                len(event.chunk_text),
                len(event.accumulated_text),
            )

        self.events.put(event)
        # Use INFO level to ensure we see this in logs
        logger.info(
            "[IDE_LOG] Event queued: type=%s, queue_size=%s",
            type(event).__name__,
            self.events.qsize(),
        )

    def get_events(self, timeout: float = 0.1) -> list[LogEvent]:
        """
        Get all available events from the queue.

        Args:
            timeout: Timeout for queue.get() in seconds

        Returns:
            List of LogEvent objects
        """
        events: list[LogEvent] = []
        while True:
            try:
                event = self.events.get(timeout=timeout)
                events.append(event)
            except queue.Empty:
                break
        return events
