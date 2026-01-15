"""
Slack notification channel for HITL interactions.

Uses Slack's Block Kit for rich, interactive messages with buttons.

Requirements:
    pip install slack-sdk

Configuration:
    notifications:
      channels:
        slack:
          enabled: true
          token: ${SLACK_BOT_TOKEN}
          default_channel: "#tactus-alerts"
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from tactus.protocols.models import HITLRequest
from tactus.protocols.notification import (
    ChannelCapabilities,
    NotificationDeliveryResult,
)

logger = logging.getLogger(__name__)

try:
    from slack_sdk.web.async_client import AsyncWebClient
    from slack_sdk.errors import SlackApiError

    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False
    AsyncWebClient = None
    SlackApiError = Exception


class SlackNotificationChannel:
    """
    Slack notification channel using Block Kit.

    Sends rich, interactive messages to Slack channels with approve/reject
    buttons for approval requests.

    Note: For interactive buttons to work, you need to:
    1. Create a Slack app with "Interactivity" enabled
    2. Set your interactivity endpoint to handle button clicks
    3. Use SlackInteractivityHandler to process button payloads
    """

    def __init__(
        self,
        token: str,
        default_channel: str = "#general",
        enabled: bool = True,
        **kwargs: Any,
    ):
        """
        Initialize Slack notification channel.

        Args:
            token: Slack Bot OAuth token (xoxb-...)
            default_channel: Default channel for notifications
            enabled: Whether this channel is enabled
            **kwargs: Additional configuration (ignored)
        """
        if not SLACK_AVAILABLE:
            raise ImportError(
                "slack-sdk is required for Slack notifications. "
                "Install with: pip install tactus[slack]"
            )

        self.client = AsyncWebClient(token=token)
        self.default_channel = default_channel
        self._enabled = enabled

        logger.info(f"SlackNotificationChannel initialized for {default_channel}")

    @property
    def channel_id(self) -> str:
        """Return channel identifier."""
        return "slack"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Return channel capabilities."""
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_interactive_buttons=True,
            supports_file_attachments=True,
            max_message_length=40000,
        )

    async def send_notification(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send HITL notification to Slack.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks

        Returns:
            NotificationDeliveryResult with delivery status
        """
        try:
            blocks = self._build_blocks(procedure_id, request_id, request, callback_url)

            response = await self.client.chat_postMessage(
                channel=self.default_channel,
                blocks=blocks,
                text=f"[{request.request_type.upper()}] {request.message}",
            )

            message_ts = response.get("ts", "")
            channel = response.get("channel", self.default_channel)

            logger.info(
                f"Sent Slack notification for {request_id} to {channel}: {message_ts}"
            )

            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id=f"{channel}:{message_ts}",
                delivered_at=datetime.now(timezone.utc),
                success=True,
            )

        except SlackApiError as e:
            error_msg = str(e.response.get("error", str(e)))
            logger.error(f"Slack API error for {request_id}: {error_msg}")
            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=error_msg,
            )
        except Exception as e:
            logger.exception(f"Failed to send Slack notification for {request_id}")
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
        Update Slack message to show it was resolved.

        Args:
            external_message_id: Format: "channel:timestamp"
            reason: Reason for cancellation
        """
        try:
            parts = external_message_id.split(":", 1)
            if len(parts) != 2:
                logger.warning(f"Invalid Slack message ID: {external_message_id}")
                return

            channel, ts = parts

            # Update the message to show it's resolved
            await self.client.chat_update(
                channel=channel,
                ts=ts,
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":white_check_mark: *Resolved* - {reason}",
                        },
                    }
                ],
                text=f"Resolved - {reason}",
            )

            logger.debug(f"Updated Slack message {external_message_id} as resolved")

        except Exception:
            logger.exception(f"Failed to update Slack message {external_message_id}")

    def _build_blocks(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> List[Dict[str, Any]]:
        """
        Build Slack Block Kit message.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks

        Returns:
            List of Block Kit blocks
        """
        blocks = []

        # Header with emoji based on request type
        emoji = self._get_emoji(request.request_type)
        blocks.append(
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {request.request_type.title()} Required",
                    "emoji": True,
                },
            }
        )

        # Main message
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": request.message,
                },
            }
        )

        # Context with procedure ID
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Procedure: `{procedure_id}` | Request: `{request_id}`",
                    }
                ],
            }
        )

        # Divider before actions
        blocks.append({"type": "divider"})

        # Add interactive elements based on request type
        if request.request_type == "approval":
            blocks.append(self._build_approval_actions(request_id, callback_url))
        elif request.request_type == "input" and request.options:
            blocks.append(
                self._build_options_actions(request_id, callback_url, request.options)
            )
        elif request.request_type == "review":
            blocks.append(self._build_review_actions(request_id, callback_url))

        return blocks

    def _build_approval_actions(
        self, request_id: str, callback_url: str
    ) -> Dict[str, Any]:
        """Build approval buttons."""
        return {
            "type": "actions",
            "block_id": f"approval_{request_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "hitl_approve",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": True,
                        }
                    ),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "hitl_reject",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": False,
                        }
                    ),
                },
            ],
        }

    def _build_options_actions(
        self, request_id: str, callback_url: str, options: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build options buttons."""
        elements = []
        for i, option in enumerate(options[:5]):  # Slack max 5 buttons per action
            label = option.get("label", f"Option {i + 1}")
            value = option.get("value", label)
            elements.append(
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": label[:75],  # Slack max 75 chars
                        "emoji": True,
                    },
                    "action_id": f"hitl_option_{i}",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": value,
                        }
                    ),
                }
            )

        return {
            "type": "actions",
            "block_id": f"options_{request_id}",
            "elements": elements,
        }

    def _build_review_actions(
        self, request_id: str, callback_url: str
    ) -> Dict[str, Any]:
        """Build review buttons."""
        return {
            "type": "actions",
            "block_id": f"review_{request_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve", "emoji": True},
                    "style": "primary",
                    "action_id": "hitl_review_approve",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": {"decision": "approved"},
                        }
                    ),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Request Changes", "emoji": True},
                    "action_id": "hitl_review_changes",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": {"decision": "changes_requested"},
                        }
                    ),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject", "emoji": True},
                    "style": "danger",
                    "action_id": "hitl_review_reject",
                    "value": json.dumps(
                        {
                            "request_id": request_id,
                            "callback_url": callback_url,
                            "value": {"decision": "rejected"},
                        }
                    ),
                },
            ],
        }

    def _get_emoji(self, request_type: str) -> str:
        """Get emoji for request type."""
        return {
            "approval": ":question:",
            "input": ":pencil:",
            "review": ":mag:",
            "escalation": ":rotating_light:",
        }.get(request_type.lower(), ":bell:")
