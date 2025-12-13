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


class LogEvent(BaseModel):
    """A log event from procedure execution."""

    event_type: str = Field(default="log", description="Event type identifier")
    level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    message: str = Field(..., description="Log message")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    logger_name: Optional[str] = Field(None, description="Logger name")
    procedure_id: Optional[str] = Field(None, description="Procedure identifier")

    model_config = {"arbitrary_types_allowed": True}


class CostEvent(BaseModel):
    """Cost event for a single LLM call with comprehensive tracing data."""

    event_type: str = Field(default="cost", description="Event type")

    # Agent/Model Info
    agent_name: str = Field(..., description="Agent that made the call")
    model: str = Field(..., description="Model used")
    provider: str = Field(..., description="Provider (openai, bedrock, etc.)")

    # Token Usage (Primary Metrics)
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens")

    # Cost Calculation (Primary Metrics)
    prompt_cost: float = Field(..., description="Cost for prompt tokens")
    completion_cost: float = Field(..., description="Cost for completion tokens")
    total_cost: float = Field(..., description="Total cost")

    # Performance Metrics (Details)
    duration_ms: Optional[float] = Field(None, description="Call duration in milliseconds")
    latency_ms: Optional[float] = Field(None, description="Time to first token (if available)")

    # Retry/Validation Metrics (Details)
    retry_count: int = Field(default=0, description="Number of retries due to validation")
    validation_errors: list[str] = Field(
        default_factory=list, description="Validation errors encountered"
    )

    # Cache Metrics (Details)
    cache_hit: bool = Field(default=False, description="Whether cache was used")
    cache_tokens: Optional[int] = Field(None, description="Cached tokens used (if available)")
    cache_cost: Optional[float] = Field(None, description="Cost saved via cache")

    # Message Metrics (Details)
    message_count: int = Field(default=0, description="Number of messages in conversation")
    new_message_count: int = Field(default=0, description="New messages from this call")

    # Request Metadata (Details)
    request_id: Optional[str] = Field(None, description="Provider request ID (if available)")
    model_version: Optional[str] = Field(None, description="Specific model version")
    temperature: Optional[float] = Field(None, description="Temperature setting used")
    max_tokens: Optional[int] = Field(None, description="Max tokens setting")

    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    procedure_id: Optional[str] = Field(None, description="Procedure identifier")

    # Raw tracing data (for future analysis)
    raw_tracing_data: Optional[Dict[str, Any]] = Field(
        None, description="Any additional tracing data"
    )

    model_config = {"arbitrary_types_allowed": True}


class ExecutionSummaryEvent(BaseModel):
    """Summary event at the end of procedure execution."""

    event_type: str = Field(default="execution_summary", description="Event type identifier")
    result: Any = Field(..., description="Validated procedure result")
    final_state: Dict[str, Any] = Field(default_factory=dict, description="Final state dictionary")
    iterations: int = Field(default=0, description="Number of iterations executed")
    tools_used: list[str] = Field(default_factory=list, description="List of tool names used")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    procedure_id: Optional[str] = Field(None, description="Procedure identifier")

    # Cost tracking
    total_cost: float = Field(default=0.0, description="Total LLM cost")
    total_tokens: int = Field(default=0, description="Total tokens used")
    cost_breakdown: list[Any] = Field(default_factory=list, description="Per-call cost details")

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
