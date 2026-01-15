"""
Microsoft Teams notification channel for HITL interactions.

Uses Teams Incoming Webhooks with Adaptive Cards for rich messages.

Configuration:
    notifications:
      channels:
        teams:
          enabled: true
          webhook_url: ${TEAMS_WEBHOOK_URL}

To get a webhook URL:
1. In Teams, go to the channel > Connectors > Incoming Webhook
2. Create a webhook and copy the URL

Note: Teams webhooks are fire-and-forget. Interactive responses require
setting up a Teams bot with Bot Framework, which is more complex.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import httpx

from tactus.protocols.models import HITLRequest
from tactus.protocols.notification import (
    ChannelCapabilities,
    NotificationDeliveryResult,
)

logger = logging.getLogger(__name__)


class TeamsNotificationChannel:
    """
    Microsoft Teams notification channel using Adaptive Cards.

    Sends rich Adaptive Card messages to Teams channels via Incoming Webhooks.
    This is fire-and-forget mode - no interactive buttons. For interactive
    buttons, you would need to set up a Teams bot via Bot Framework.
    """

    def __init__(
        self,
        webhook_url: str,
        enabled: bool = True,
        **kwargs: Any,
    ):
        """
        Initialize Teams notification channel.

        Args:
            webhook_url: Teams Incoming Webhook URL
            enabled: Whether this channel is enabled
            **kwargs: Additional configuration (ignored)
        """
        self.webhook_url = webhook_url
        self._enabled = enabled

        logger.info("TeamsNotificationChannel initialized")

    @property
    def channel_id(self) -> str:
        """Return channel identifier."""
        return "teams"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Return channel capabilities."""
        return ChannelCapabilities(
            supports_approval=True,  # Can notify, just no interactive buttons
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_interactive_buttons=False,  # Webhooks don't support buttons
            supports_file_attachments=False,
            max_message_length=28000,  # Adaptive Card limit
        )

    async def send_notification(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send HITL notification to Teams.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks (for info only, no buttons)

        Returns:
            NotificationDeliveryResult with delivery status
        """
        try:
            card = self._build_adaptive_card(procedure_id, request_id, request)

            # Teams webhooks expect the card wrapped in a specific format
            payload = {
                "type": "message",
                "attachments": [
                    {
                        "contentType": "application/vnd.microsoft.card.adaptive",
                        "contentUrl": None,
                        "content": card,
                    }
                ],
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )

                # Teams returns 1 on success (yes, really)
                if response.status_code == 200:
                    # Teams doesn't return a message ID, generate one
                    message_id = f"teams_{request_id}_{int(datetime.now().timestamp())}"

                    logger.info(
                        f"Sent Teams notification for {request_id}: {message_id}"
                    )

                    return NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id=message_id,
                        delivered_at=datetime.now(timezone.utc),
                        success=True,
                    )
                else:
                    error = f"Teams webhook returned {response.status_code}"
                    logger.error(f"{error}: {response.text}")
                    return NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id="",
                        delivered_at=datetime.now(timezone.utc),
                        success=False,
                        error_message=error,
                    )

        except Exception as e:
            logger.exception(f"Failed to send Teams notification for {request_id}")
            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(e),
            )

    async def cancel_notification(
        self,
        external_message_id: str,
        reason: str = "Resolved via another channel",
    ) -> None:
        """
        Cancel notification (no-op for Teams webhooks).

        Teams webhooks don't support message updates.
        """
        logger.debug(
            f"Cannot update Teams webhook message {external_message_id} - "
            f"fire-and-forget mode"
        )

    def _build_adaptive_card(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> Dict[str, Any]:
        """
        Build Microsoft Adaptive Card.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details

        Returns:
            Adaptive Card as dict
        """
        color = self._get_color(request.request_type)
        emoji = self._get_emoji(request.request_type)

        card = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                # Header with colored container
                {
                    "type": "Container",
                    "style": color,
                    "items": [
                        {
                            "type": "TextBlock",
                            "text": f"{emoji} {request.request_type.upper()} REQUIRED",
                            "weight": "Bolder",
                            "size": "Medium",
                            "color": "Light" if color != "default" else "Default",
                        }
                    ],
                },
                # Message content
                {
                    "type": "TextBlock",
                    "text": request.message,
                    "wrap": True,
                    "spacing": "Medium",
                },
                # Facts (metadata)
                {
                    "type": "FactSet",
                    "facts": [
                        {"title": "Procedure", "value": procedure_id},
                        {"title": "Request ID", "value": request_id},
                        {
                            "title": "Time",
                            "value": datetime.now(timezone.utc).strftime(
                                "%Y-%m-%d %H:%M:%S UTC"
                            ),
                        },
                    ],
                    "spacing": "Medium",
                },
                # Instructions
                {
                    "type": "TextBlock",
                    "text": "Please respond via your Tactus interface or API.",
                    "wrap": True,
                    "isSubtle": True,
                    "spacing": "Medium",
                },
            ],
        }

        # Add options if present
        if request.options:
            options_text = "\n".join(
                f"• {opt.get('label', f'Option {i+1}')}"
                for i, opt in enumerate(request.options)
            )
            card["body"].insert(
                2,
                {
                    "type": "TextBlock",
                    "text": f"**Options:**\n{options_text}",
                    "wrap": True,
                    "spacing": "Small",
                },
            )

        return card

    def _get_color(self, request_type: str) -> str:
        """Get Adaptive Card container style for request type."""
        # Adaptive Card container styles: default, emphasis, good, attention, warning, accent
        colors = {
            "approval": "attention",  # Orange
            "input": "accent",  # Blue
            "review": "emphasis",  # Grey
            "escalation": "warning",  # Red/Yellow
        }
        return colors.get(request_type.lower(), "default")

    def _get_emoji(self, request_type: str) -> str:
        """Get emoji for request type."""
        # Teams supports some emoji in text
        return {
            "approval": "❓",
            "input": "✏️",
            "review": "🔍",
            "escalation": "🚨",
        }.get(request_type.lower(), "🔔")
