"""
Control loop protocol for omnichannel controller interactions.

Defines the interface for control channels that enable both human-in-the-loop (HITL)
and model-in-the-loop (MITL) interactions. Controllers can be humans or AI models.

The control loop uses a publish-subscribe pattern with namespace-based routing:
- Tactus runtimes (publishers) emit control requests to namespaces
- Controllers (subscribers) subscribe to namespace patterns
- Subscribers can be observers (read-only) or responders (can provide input)
"""

from typing import Protocol, Optional, List, Dict, Any, AsyncIterator, runtime_checkable
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import Enum


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ControlRequestType(str, Enum):
    """Types of control requests."""

    APPROVAL = "approval"
    INPUT = "input"
    SELECT = "select"  # Single or multiple choice selection
    REVIEW = "review"
    ESCALATION = "escalation"
    UPLOAD = "upload"  # File upload
    INPUTS = "inputs"  # Batched inputs (multiple requests in one)
    CUSTOM = "custom"  # Custom component type (uses metadata.component_type for routing)


class ControlOption(BaseModel):
    """An option for a control request."""

    label: str = Field(..., description="Display label for the option")
    value: Any = Field(..., description="Value to return if selected")
    style: str = Field(
        default="default", description="Style hint: primary, danger, secondary, default"
    )
    description: Optional[str] = Field(
        default=None, description="Optional description for the option"
    )

    model_config = {"arbitrary_types_allowed": True}


class ConversationMessage(BaseModel):
    """A message in the conversation history."""

    role: str = Field(..., description="Message role: agent, user, tool, system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When the message was created")
    tool_name: Optional[str] = Field(default=None, description="Tool name if role is 'tool'")
    tool_input: Optional[Dict[str, Any]] = Field(default=None, description="Tool input parameters")
    tool_output: Optional[Any] = Field(default=None, description="Tool output/result")

    model_config = {"arbitrary_types_allowed": True}


class ControlInteraction(BaseModel):
    """A prior control interaction in the same invocation."""

    request_type: str = Field(..., description="Type of the original request")
    message: str = Field(..., description="The original request message")
    response_value: Any = Field(..., description="The response value")
    responded_by: Optional[str] = Field(
        default=None, description="Who responded (user ID or channel)"
    )
    responded_at: datetime = Field(..., description="When the response was received")
    channel_id: str = Field(..., description="Channel that provided the response")

    model_config = {"arbitrary_types_allowed": True}


class BacktraceEntry(BaseModel):
    """Single entry in the execution backtrace."""

    checkpoint_type: str = Field(
        ..., description="Type of checkpoint (e.g., 'hitl', 'llm', 'tool')"
    )
    line: Optional[int] = Field(default=None, description="Source line number")
    function_name: Optional[str] = Field(default=None, description="Function/procedure name")
    duration_ms: Optional[float] = Field(default=None, description="Duration at this checkpoint")

    model_config = {"arbitrary_types_allowed": True}


class RuntimeContext(BaseModel):
    """
    Context automatically captured from the Tactus runtime.

    Includes source location, execution position, and backtrace.
    This context is universally available regardless of how procedures are stored.
    """

    source_line: Optional[int] = Field(
        default=None, description="Line number where request originated"
    )
    source_file: Optional[str] = Field(default=None, description="Source file path (if available)")
    checkpoint_position: int = Field(default=0, description="Position in execution log")
    procedure_name: str = Field(default="", description="Name of the running procedure")
    invocation_id: str = Field(default="", description="Unique identifier for this execution")
    started_at: Optional[datetime] = Field(default=None, description="When execution began")
    elapsed_seconds: float = Field(default=0.0, description="Time since execution started")
    backtrace: List[BacktraceEntry] = Field(
        default_factory=list,
        description="Execution path to reach this point",
    )

    model_config = {"arbitrary_types_allowed": True}


class ContextLink(BaseModel):
    """
    Application-provided context reference.

    Allows host applications to inject domain-specific context
    with optional deep links back to the source system.
    """

    name: str = Field(..., description="Display label (e.g., 'Evaluation', 'Customer')")
    value: str = Field(..., description="Display value (e.g., 'Monthly QA Review')")
    url: Optional[str] = Field(default=None, description="Optional deep link URL")

    model_config = {"arbitrary_types_allowed": True}


class ControlRequestItem(BaseModel):
    """
    A single input item within a batched request.

    Used when request_type='inputs' to specify multiple inputs
    that should be collected together in a single interaction.
    """

    item_id: str = Field(..., description="Unique ID within batch (used as response key)")
    label: str = Field(..., description="Short semantic label for tabs/UI")
    request_type: ControlRequestType = Field(
        ..., description="Type of input (approval, input, select, etc.)"
    )
    message: str = Field(..., description="Message to display")
    options: List[ControlOption] = Field(
        default_factory=list,
        description="Options for select/review types",
    )
    default_value: Any = Field(default=None, description="Default value")
    required: bool = Field(default=True, description="Whether this item must be completed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific metadata",
    )

    model_config = {"arbitrary_types_allowed": True}


class ControlRequest(BaseModel):
    """
    A request for controller input.

    Includes rich context for decision-making: conversation history,
    prior interactions, input summary, and namespace for routing.
    """

    # Identity
    request_id: str = Field(..., description="Unique request identifier")
    procedure_id: str = Field(..., description="Procedure that initiated the request")
    procedure_name: str = Field(..., description="Human-readable procedure name")
    invocation_id: str = Field(..., description="Unique invocation identifier")

    # Routing
    namespace: str = Field(
        default="",
        description="Namespace for routing/authorization (e.g., 'operations/incidents/level3')",
    )

    # Subject identification
    subject: Optional[str] = Field(
        default=None,
        description="Human-readable subject identifier (e.g., 'John Doe', 'Order #12345')",
    )

    # Timing
    started_at: datetime = Field(..., description="When the invocation started")
    elapsed_seconds: int = Field(default=0, description="Seconds since invocation started")

    # The request itself
    request_type: ControlRequestType = Field(..., description="Type of interaction requested")
    message: str = Field(..., description="Message to display to the controller")
    label: Optional[str] = Field(
        default=None,
        description="Short semantic label for UI (e.g., tab name, chip label)",
    )
    options: List[ControlOption] = Field(
        default_factory=list,
        description="Options for the controller to choose from",
    )
    timeout_seconds: Optional[int] = Field(
        default=None,
        description="Timeout in seconds (None = wait forever)",
    )
    default_value: Any = Field(default=None, description="Default value on timeout")

    # For batched inputs (request_type='inputs')
    items: List[ControlRequestItem] = Field(
        default_factory=list,
        description="Individual input items (used when request_type='inputs')",
    )

    # Rich context
    input_summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary of key input fields for context",
    )
    conversation: List[ConversationMessage] = Field(
        default_factory=list,
        description="Full conversation history with tool calls",
    )
    prior_interactions: List[ControlInteraction] = Field(
        default_factory=list,
        description="Previous control interactions in this invocation",
    )

    # New context architecture (Phase 5)
    runtime_context: Optional[RuntimeContext] = Field(
        default=None,
        description="Automatically captured runtime context (source location, backtrace)",
    )
    application_context: List[ContextLink] = Field(
        default_factory=list,
        description="Host application-provided context links",
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context and metadata",
    )

    model_config = {"arbitrary_types_allowed": True}


class ControlResponse(BaseModel):
    """Response from a controller."""

    request_id: str = Field(..., description="Request ID this responds to")
    value: Any = Field(..., description="The response value from the controller")
    responded_at: datetime = Field(
        default_factory=utc_now, description="When the response was received"
    )
    timed_out: bool = Field(default=False, description="Whether the response timed out")
    channel_id: Optional[str] = Field(
        default=None, description="Channel that provided the response"
    )
    responder_id: Optional[str] = Field(
        default=None, description="Controller identifier (user ID, model ID)"
    )
    responder_name: Optional[str] = Field(default=None, description="Display name of the responder")

    model_config = {"arbitrary_types_allowed": True}


class ChannelCapabilities(BaseModel):
    """Advertised capabilities of a control channel."""

    supports_approval: bool = Field(default=True, description="Can handle approval requests")
    supports_input: bool = Field(default=True, description="Can handle input requests")
    supports_review: bool = Field(default=True, description="Can handle review requests")
    supports_escalation: bool = Field(default=True, description="Can handle escalation alerts")
    supports_select: bool = Field(default=True, description="Can handle select/choice requests")
    supports_inputs: bool = Field(default=True, description="Can handle batched input requests")
    supports_upload: bool = Field(default=False, description="Can handle file upload requests")
    supports_interactive_buttons: bool = Field(
        default=False,
        description="Can render interactive buttons for responses",
    )
    supports_file_attachments: bool = Field(
        default=False,
        description="Can include file attachments",
    )
    max_message_length: Optional[int] = Field(
        default=None,
        description="Maximum message length (None = unlimited)",
    )
    is_synchronous: bool = Field(
        default=False,
        description="True if channel provides immediate responses (like CLI)",
    )

    model_config = {"arbitrary_types_allowed": True}


class DeliveryResult(BaseModel):
    """Result of sending a control request to a channel."""

    channel_id: str = Field(..., description="Channel identifier")
    external_message_id: str = Field(
        ...,
        description="Channel-specific message ID for tracking/cancellation",
    )
    delivered_at: datetime = Field(..., description="When the request was delivered")
    success: bool = Field(..., description="Whether delivery succeeded")
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if delivery failed",
    )

    model_config = {"arbitrary_types_allowed": True}


@runtime_checkable
class ControlChannel(Protocol):
    """
    Protocol for control channel implementations.

    Control channels deliver requests to controllers (human or model) and
    receive responses. The architecture is transport-agnostic - channels
    decide how they communicate (WebSocket, SSE, polling, etc.).

    Lifecycle:
    1. initialize() - Called at procedure start (eager initialization)
    2. send() - Send control request to the channel
    3. receive() - Yield responses as they arrive
    4. cancel() - Cancel/update when resolved via another channel
    5. shutdown() - Clean up on procedure end
    """

    @property
    def channel_id(self) -> str:
        """
        Unique identifier for this channel.

        Examples: 'cli', 'ide', 'tactus_cloud', 'slack'
        """
        ...

    @property
    def capabilities(self) -> ChannelCapabilities:
        """
        Return channel capabilities.

        Used for routing decisions and UI adaptation.
        """
        ...

    async def initialize(self) -> None:
        """
        Initialize the channel.

        Called eagerly at procedure start to avoid blocking on slow
        initialization (OAuth handshakes, WebSocket connections, etc.)
        when a control request arrives.
        """
        ...

    async def send(
        self,
        request: ControlRequest,
    ) -> DeliveryResult:
        """
        Send a control request to this channel.

        Args:
            request: ControlRequest with full context

        Returns:
            DeliveryResult with delivery status and external message ID
        """
        ...

    async def receive(self) -> AsyncIterator[ControlResponse]:
        """
        Yield responses as they arrive.

        How responses arrive is channel-specific:
        - CLI: Background thread reading stdin
        - IDE/SSE: HTTP POST from extension
        - WebSocket: Messages from connected clients
        - Webhook: HTTP callbacks from external services

        Yields:
            ControlResponse as they are received
        """
        ...

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """
        Cancel or update a request when resolved via another channel.

        Args:
            external_message_id: Channel-specific message ID from DeliveryResult
            reason: Reason for cancellation (e.g., "Responded via tactus_cloud")
        """
        ...

    async def shutdown(self) -> None:
        """
        Clean shutdown of the channel.

        Called at procedure end or on error. Should clean up resources,
        close connections, etc.
        """
        ...


class ControlChannelConfig(BaseModel):
    """Base configuration for control channels."""

    enabled: bool = Field(default=False, description="Whether this channel is enabled")

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}


class ControlLoopConfig(BaseModel):
    """Top-level control loop configuration."""

    enabled: bool = Field(default=True, description="Enable control loop system")
    channels: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Per-channel configuration",
    )

    model_config = {"arbitrary_types_allowed": True}
