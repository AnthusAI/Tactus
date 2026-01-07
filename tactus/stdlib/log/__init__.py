"""Standard library logging tool for Tactus.

Provides a simple logging utility that agents can use to
record information during execution.
"""

import logging
from typing import Optional, Literal

# Get a logger for stdlib tools
logger = logging.getLogger("tactus.stdlib.log")


def log(
    message: str,
    level: Literal["debug", "info", "warning", "error"] = "info",
    context: Optional[dict] = None,
) -> dict:
    """Log a message with optional context.

    Args:
        message: The message to log
        level: Log level (debug, info, warning, or error)
        context: Optional dictionary of contextual data

    Returns:
        Dict with status and the logged message

    Examples:
        >>> log("Starting process")
        {'status': 'logged', 'level': 'info', 'message': 'Starting process'}

        >>> log("Error occurred", level="error", context={"code": 500})
        {'status': 'logged', 'level': 'error', 'message': 'Error occurred', 'context': {'code': 500}}
    """
    # Map string levels to logging constants
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
    }

    log_level = level_map.get(level, logging.INFO)

    # Format message with context if provided
    if context:
        full_message = f"{message} | Context: {context}"
    else:
        full_message = message

    # Log the message
    logger.log(log_level, full_message)

    # Return structured response
    result = {"status": "logged", "level": level, "message": message}

    if context:
        result["context"] = context

    return result


# Alias for backward compatibility if needed
__all__ = ["log"]
