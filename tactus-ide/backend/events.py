"""
Event models for IDE structured output.

These are IDE-specific models for capturing and structuring runtime output.
They are NOT part of core Tactus - core Tactus uses standard Python logging.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

# Import core event types from tactus.protocols
from tactus.protocols.models import AgentStreamChunkEvent  # noqa: F401

# Import test/evaluation events from tactus.testing


class BaseEvent(BaseModel):
    """Base event model for all IDE events."""

    event_type: str = Field(..., description="Type of event (log, execution, output, validation)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    procedure_id: Optional[str] = Field(None, description="Procedure identifier if available")


class LogEvent(BaseEvent):
    """Log message event."""

    event_type: str = "log"
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context data")
    logger_name: Optional[str] = Field(None, description="Logger name")


class ExecutionEvent(BaseEvent):
    """Execution lifecycle event."""

    event_type: str = "execution"
    lifecycle_stage: str = Field(
        ..., description="Lifecycle stage (start, complete, error, waiting)"
    )
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    exit_code: Optional[int] = Field(None, description="Exit code if completed")


class OutputEvent(BaseEvent):
    """Raw stdout/stderr output event."""

    event_type: str = "output"
    stream: str = Field(..., description="Output stream (stdout or stderr)")
    content: str = Field(..., description="Output content")


class ValidationEvent(BaseEvent):
    """Validation result event."""

    event_type: str = "validation"
    valid: bool = Field(..., description="Whether validation passed")
    errors: List[Dict[str, Any]] = Field(
        default_factory=list, description="List of validation errors"
    )


class LoadingEvent(BaseEvent):
    """Loading indicator event."""

    event_type: str = "loading"
    message: str = Field(..., description="Loading message to display")
