"""
Log handler protocol for Tactus.

Defines the interface for handling log events during workflow execution.
Implementations can render logs differently (CLI with Rich, IDE with React, etc.).
"""

from typing import Protocol, Union
from tactus.protocols.models import LogEvent, ExecutionSummaryEvent


class LogHandler(Protocol):
    """
    Protocol for log handlers.

    Implementations handle log events from procedures, rendering them
    appropriately for different environments (CLI, IDE, API, etc.).
    """

    def log(self, event: Union[LogEvent, ExecutionSummaryEvent]) -> None:
        """
        Handle a log or summary event.

        Args:
            event: Structured event (LogEvent or ExecutionSummaryEvent)
        """
        ...
