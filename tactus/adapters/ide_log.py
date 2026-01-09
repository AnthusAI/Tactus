"""
IDE Log Handler for event collection and streaming.

Collects log events in a queue for streaming to IDE frontend.
"""

import logging
import queue
from typing import List

from tactus.protocols.models import LogEvent

logger = logging.getLogger(__name__)


class IDELogHandler:
    """
    IDE log handler that collects events for streaming.

    Receives structured log events and stores them in a queue
    for retrieval and streaming to the IDE frontend.
    """

    def __init__(self):
        """Initialize IDE log handler."""
        self.events = queue.Queue()
        self.cost_events = []  # Track cost events for aggregation
        logger.debug("IDELogHandler initialized")

    def log(self, event: LogEvent) -> None:
        """
        Collect log event for streaming.

        Args:
            event: Structured log event
        """
        # Track cost events for aggregation
        from tactus.protocols.models import CostEvent, AgentStreamChunkEvent

        if isinstance(event, CostEvent):
            self.cost_events.append(event)

        # Debug logging for streaming events
        if isinstance(event, AgentStreamChunkEvent):
            logger.info(
                f"[IDE_LOG] Received AgentStreamChunkEvent: agent={event.agent_name}, chunk_len={len(event.chunk_text)}, accumulated_len={len(event.accumulated_text)}"
            )

        self.events.put(event)
        logger.debug(
            f"[IDE_LOG] Event queued: type={type(event).__name__}, queue_size={self.events.qsize()}"
        )

    def get_events(self, timeout: float = 0.1) -> List[LogEvent]:
        """
        Get all available events from the queue.

        Args:
            timeout: Timeout for queue.get() in seconds

        Returns:
            List of LogEvent objects
        """
        events = []
        while True:
            try:
                event = self.events.get(timeout=timeout)
                events.append(event)
            except queue.Empty:
                break
        return events
