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
        # Use Rich to format nicely
        if event.context:
            # Log with context as extra data
            self.console.log(event.message, **event.context)
        else:
            # Simple log message
            self.console.log(event.message)
