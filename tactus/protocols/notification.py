"""
Notification channel protocol for omnichannel HITL notifications.

Defines the interface for notification channel plugins that can send
HITL requests to external systems (Slack, Discord, Teams, etc.).
"""

from typing import Protocol, Optional, List, Dict, Any, runtime_checkable
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from tactus.protocols.models import HITLRequest, HITLResponse


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


class ChannelCapabilities(BaseModel):
    """Advertised capabilities of a notification channel."""

    supports_approval: bool = Field(default=True, description="Can handle approval requests")
    supports_input: bool = Field(default=True, description="Can handle input requests")
    supports_review: bool = Field(default=True, description="Can handle review requests")
    supports_escalation: bool = Field(default=True, description="Can handle escalation alerts")
    supports_interactive_buttons: bool = Field(
        default=False, description="Can render interactive buttons for responses"
    )
    supports_file_attachments: bool = Field(
        default=False, description="Can include file attachments"
    )
    max_message_length: Optional[int] = Field(
        default=None, description="Maximum message length (None = unlimited)"
    )

    model_config = {"arbitrary_types_allowed": True}


class NotificationDeliveryResult(BaseModel):
    """Result of sending a notification to a channel."""

    channel_id: str = Field(..., description="Channel identifier (e.g., 'slack', 'discord')")
    external_message_id: str = Field(
        ..., description="Channel-specific message ID for tracking/cancellation"
    )
    delivered_at: datetime = Field(..., description="When the notification was delivered")
    success: bool = Field(..., description="Whether delivery succeeded")
    error_message: Optional[str] = Field(
        default=None, description="Error message if delivery failed"
    )

    model_config = {"arbitrary_types_allowed": True}


class PendingNotification(BaseModel):
    """Tracks a pending HITL notification across multiple channels."""

    request_id: str = Field(..., description="Unique request identifier")
    procedure_id: str = Field(..., description="Procedure that initiated the request")
    request: HITLRequest = Field(..., description="The original HITL request")
    deliveries: List[NotificationDeliveryResult] = Field(
        default_factory=list, description="Delivery results for each channel"
    )
    created_at: datetime = Field(
        default_factory=utc_now, description="When the notification was created"
    )
    callback_url: str = Field(..., description="URL where channels should POST responses")
    responded: bool = Field(default=False, description="Whether a response was received")
    response: Optional[HITLResponse] = Field(default=None, description="The response if received")
    response_channel: Optional[str] = Field(
        default=None, description="Which channel provided the response"
    )

    model_config = {"arbitrary_types_allowed": True}


class HITLResponsePayload(BaseModel):
    """Payload sent by notification channels when a user responds."""

    channel_id: str = Field(..., description="Channel that received the response")
    value: Any = Field(..., description="The response value from the user")
    responder_id: Optional[str] = Field(
        default=None, description="Channel-specific user identifier"
    )
    responder_name: Optional[str] = Field(default=None, description="Display name of the responder")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional channel-specific metadata"
    )

    model_config = {"arbitrary_types_allowed": True}


class HITLResponseResult(BaseModel):
    """Result of processing an HITL response."""

    success: bool = Field(..., description="Whether the response was processed successfully")
    error: Optional[str] = Field(default=None, description="Error message if processing failed")
    procedure_id: Optional[str] = Field(
        default=None, description="Procedure ID if response was accepted"
    )
    response: Optional[HITLResponse] = Field(
        default=None, description="The HITLResponse if accepted"
    )
    already_responded: bool = Field(
        default=False, description="True if another channel already responded"
    )

    model_config = {"arbitrary_types_allowed": True}


@runtime_checkable
class NotificationChannel(Protocol):
    """
    Protocol for notification channel plugins.

    Each implementation handles a specific platform (Slack, Discord, Teams, etc.).
    Channels can be notification-only (fire-and-forget like email) or interactive
    (can receive responses via buttons).
    """

    @property
    def channel_id(self) -> str:
        """
        Unique identifier for this channel.

        Examples: 'slack', 'discord', 'teams', 'email'
        """
        ...

    @property
    def capabilities(self) -> ChannelCapabilities:
        """
        Return channel capabilities.

        Used for routing decisions (e.g., don't send approval requests
        to channels that can't handle interactive responses).
        """
        ...

    async def send_notification(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send HITL request notification to this channel.

        The channel should:
        1. Format the request appropriately for the platform
        2. Include callback_url in any interactive elements
        3. Return a delivery result with the external message ID

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier for this HITL interaction
            request: HITLRequest with interaction details
            callback_url: URL where responses should be POSTed

        Returns:
            NotificationDeliveryResult with delivery status and message ID
        """
        ...

    async def cancel_notification(
        self,
        external_message_id: str,
        reason: str = "Resolved via another channel",
    ) -> None:
        """
        Cancel or update a notification (e.g., mark as resolved, disable buttons).

        Called when a response is received from another channel.

        Args:
            external_message_id: Channel-specific message ID from delivery result
            reason: Reason for cancellation (for display)
        """
        ...


class NotificationChannelConfig(BaseModel):
    """Base configuration for notification channels."""

    enabled: bool = Field(default=False, description="Whether this channel is enabled")

    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}


class NotificationsConfig(BaseModel):
    """Top-level notifications configuration."""

    enabled: bool = Field(default=False, description="Enable notification system")
    callback_base_url: Optional[str] = Field(
        default=None,
        description="Base URL for response callbacks (e.g., 'https://my-tactus.example.com')",
    )
    signing_secret: Optional[str] = Field(
        default=None, description="Secret for signing/verifying response webhooks"
    )
    channels: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Per-channel configuration"
    )

    model_config = {"arbitrary_types_allowed": True}
