"""
Core Pydantic models used across Tactus protocols.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class CheckpointData(BaseModel):
    """A single checkpoint in a procedure execution."""

    name: str = Field(..., description="Unique checkpoint name")
    result: Any = Field(..., description="Result value from the checkpointed step")
    completed_at: datetime = Field(..., description="Timestamp when checkpoint was created")

    model_config = {"arbitrary_types_allowed": True}


class ProcedureMetadata(BaseModel):
    """Complete metadata for a procedure run."""

    procedure_id: str = Field(..., description="Unique procedure identifier")
    checkpoints: Dict[str, CheckpointData] = Field(
        default_factory=dict, description="Map of checkpoint names to checkpoint data"
    )
    state: Dict[str, Any] = Field(default_factory=dict, description="Mutable state dictionary")
    lua_state: Dict[str, Any] = Field(
        default_factory=dict, description="Lua-specific state (preserved across execution)"
    )
    status: str = Field(
        default="RUNNING",
        description="Current procedure status (RUNNING, WAITING_FOR_HUMAN, COMPLETED, FAILED)",
    )
    waiting_on_message_id: Optional[str] = Field(
        default=None, description="Message ID if procedure is waiting for human response"
    )

    model_config = {"arbitrary_types_allowed": True}


class HITLResponse(BaseModel):
    """Response from a human interaction."""

    value: Any = Field(..., description="The response value from the human")
    responded_at: datetime = Field(..., description="When the human responded")
    timed_out: bool = Field(default=False, description="Whether the response timed out")

    model_config = {"arbitrary_types_allowed": True}


class HITLRequest(BaseModel):
    """Request for human interaction."""

    request_type: str = Field(
        ..., description="Type of interaction: 'approval', 'input', 'review', 'escalation'"
    )
    message: str = Field(..., description="Message to display to the human")
    timeout_seconds: Optional[int] = Field(
        default=None, description="Timeout in seconds (None = wait forever)"
    )
    default_value: Any = Field(default=None, description="Default value to return on timeout")
    options: Optional[list[Dict[str, Any]]] = Field(
        default=None, description="Options for review requests (list of {label, type} dicts)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional context and metadata"
    )

    model_config = {"arbitrary_types_allowed": True}


class ChatMessage(BaseModel):
    """A message in a chat session."""

    role: str = Field(..., description="Message role: USER, ASSISTANT, SYSTEM, TOOL")
    content: str = Field(..., description="Message content")
    message_type: str = Field(default="MESSAGE", description="Type of message")
    tool_name: Optional[str] = Field(
        default=None, description="Tool name if this is a tool message"
    )
    tool_parameters: Optional[Dict[str, Any]] = Field(
        default=None, description="Tool call parameters"
    )
    tool_response: Optional[Dict[str, Any]] = Field(default=None, description="Tool response data")
    parent_message_id: Optional[str] = Field(
        default=None, description="Parent message ID for threading"
    )
    human_interaction: Optional[str] = Field(
        default=None, description="Human interaction type (PENDING_APPROVAL, RESPONSE, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional message metadata"
    )

    model_config = {"arbitrary_types_allowed": True}
