"""
CLI Log Handler for Rich-formatted logging.

Renders log events using Rich console for beautiful CLI output.
"""

import logging
from typing import Optional
from rich.console import Console

from tactus.protocols.models import LogEvent

logger = logging.getLogger(__name__)


class CLILogHandler:
    """
    CLI log handler using Rich formatting.

    Receives structured log events and renders them with Rich
    for beautiful console output.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize CLI log handler.

        Args:
            console: Rich Console instance (creates new one if not provided)
        """
        self.console = console or Console()
        logger.debug("CLILogHandler initialized")

    def log(self, event: LogEvent) -> None:
        """
        Render log event with Rich formatting.

        Args:
            event: Structured log event
        """
        # Handle ExecutionSummaryEvent specially (no message attribute)
        if event.event_type == "execution_summary":
            self.console.log(
                f"[green]✓[/green] Procedure completed: {event.iterations} iterations, {len(event.tools_used)} tools used"
            )
            return

        # Use Rich to format nicely for other events
        if hasattr(event, "context") and event.context:
            # Log with context formatted as part of the message
            import json

            context_str = json.dumps(event.context, indent=2)
            self.console.log(f"{event.message}\n{context_str}")
        else:
            # Simple log message
            self.console.log(event.message)
