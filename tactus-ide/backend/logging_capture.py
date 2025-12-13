"""
Logging capture handler for IDE structured output.

Intercepts Python logging output and converts it to structured events.
"""

import logging
import json
import re
import queue
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from events import LogEvent


class CaptureHandler(logging.Handler):
    """
    Custom logging handler that captures log records and converts them to LogEvent objects.

    This handler intercepts logs from the Tactus runtime and converts them into
    structured events that can be streamed to the IDE frontend.
    """

    def __init__(self, event_queue: queue.Queue, procedure_id: Optional[str] = None):
        """
        Initialize capture handler.

        Args:
            event_queue: Thread-safe queue for collecting events
            procedure_id: Optional procedure identifier
        """
        super().__init__()
        self.event_queue = event_queue
        self.procedure_id = procedure_id

    def emit(self, record: logging.LogRecord) -> None:
        """
        Process a log record and convert it to a LogEvent.

        Args:
            record: Log record from Python logging
        """
        try:
            # Format the message
            message = self.format(record)

            # Try to extract context from structured messages
            context = self._extract_context(message)

            # If context was extracted, clean the message
            if context:
                message = self._clean_message(message)

            # Create LogEvent
            event = LogEvent(
                level=record.levelname,
                message=message,
                context=context,
                logger_name=record.name,
                procedure_id=self.procedure_id,
                timestamp=datetime.fromtimestamp(record.created),
            )

            # Add to queue
            self.event_queue.put(event)

        except Exception as e:
            # Don't let handler errors break logging
            print(f"Error in CaptureHandler: {e}")

    def _extract_context(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON context from structured log messages.

        Looks for patterns like:
        "Processing item\nContext: {...}"

        Args:
            message: Log message

        Returns:
            Extracted context dict or None
        """
        # Look for "Context: {json}" pattern
        context_pattern = r"Context:\s*(\{[^}]+\}|\[[^\]]+\])"
        match = re.search(context_pattern, message, re.DOTALL)

        if match:
            try:
                context_str = match.group(1)
                return json.loads(context_str)
            except json.JSONDecodeError:
                pass

        return None

    def _clean_message(self, message: str) -> str:
        """
        Remove context section from message.

        Args:
            message: Original message with context

        Returns:
            Cleaned message without context section
        """
        # Remove "Context: {...}" section
        context_pattern = r"\s*Context:\s*(\{[^}]+\}|\[[^\]]+\])"
        cleaned = re.sub(context_pattern, "", message, flags=re.DOTALL)
        return cleaned.strip()


class EventCollector:
    """
    Manages logging capture and event collection lifecycle.

    Sets up a CaptureHandler, attaches it to the logging system,
    and provides methods to retrieve collected events.
    """

    def __init__(self, procedure_id: Optional[str] = None, logger_name: str = "tactus"):
        """
        Initialize event collector.

        Args:
            procedure_id: Optional procedure identifier
            logger_name: Logger name to capture (default: 'tactus')
        """
        self.procedure_id = procedure_id
        self.logger_name = logger_name
        self.event_queue: queue.Queue = queue.Queue()
        self.handler: Optional[CaptureHandler] = None
        self.logger: Optional[logging.Logger] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start capturing logs."""
        with self._lock:
            if self.handler is not None:
                return  # Already started

            # Create handler
            self.handler = CaptureHandler(self.event_queue, self.procedure_id)
            self.handler.setLevel(logging.DEBUG)

            # Create formatter (simple format since we parse it)
            formatter = logging.Formatter("%(message)s")
            self.handler.setFormatter(formatter)

            # Attach to logger
            self.logger = logging.getLogger(self.logger_name)
            self.logger.addHandler(self.handler)

    def stop(self) -> None:
        """Stop capturing logs and clean up."""
        with self._lock:
            if self.handler and self.logger:
                self.logger.removeHandler(self.handler)
                self.handler = None
                self.logger = None

    def get_events(self, timeout: float = 0.1) -> list:
        """
        Get all available events from the queue.

        Args:
            timeout: Timeout for queue.get() in seconds

        Returns:
            List of LogEvent objects
        """
        events = []

        # Get all available events without blocking
        while True:
            try:
                event = self.event_queue.get(timeout=timeout)
                events.append(event)
            except queue.Empty:
                break

        return events

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
