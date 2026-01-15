"""
Discord notification channel for HITL interactions.

Uses Discord embeds and button components for interactive messages.

Requirements:
    pip install discord.py

Configuration:
    notifications:
      channels:
        discord:
          enabled: true
          token: ${DISCORD_BOT_TOKEN}
          guild_id: "123456789"
          default_channel: "tactus-alerts"

Note: Discord buttons require running a bot that listens for interactions.
Unlike Slack, Discord doesn't POST to a webhook - your bot must be online
and listening via the Discord Gateway. For simpler deployments, consider
using Discord webhooks (fire-and-forget, no buttons).
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
    import discord
    from discord import Embed, Colour

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    discord = None
    Embed = None
    Colour = None


class DiscordNotificationChannel:
    """
    Discord notification channel using embeds.

    Sends rich embed messages to Discord channels. Interactive buttons
    require the Discord bot to be running and listening for interactions.

    For simpler deployments without a running bot, this channel can also
    use Discord webhooks (fire-and-forget mode, no buttons).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        guild_id: Optional[str] = None,
        default_channel: str = "general",
        webhook_url: Optional[str] = None,
        enabled: bool = True,
        **kwargs: Any,
    ):
        """
        Initialize Discord notification channel.

        Args:
            token: Discord bot token (for full bot mode with buttons)
            guild_id: Discord guild (server) ID
            default_channel: Default channel name for notifications
            webhook_url: Discord webhook URL (for simple webhook mode)
            enabled: Whether this channel is enabled
            **kwargs: Additional configuration (ignored)
        """
        if not DISCORD_AVAILABLE:
            raise ImportError(
                "discord.py is required for Discord notifications. "
                "Install with: pip install tactus[discord]"
            )

        self.token = token
        self.guild_id = guild_id
        self.default_channel = default_channel
        self.webhook_url = webhook_url
        self._enabled = enabled

        # Determine mode
        self.use_webhook = bool(webhook_url)
        if not self.use_webhook and not token:
            raise ValueError(
                "Discord channel requires either 'token' (bot mode) or "
                "'webhook_url' (webhook mode)"
            )

        mode = "webhook" if self.use_webhook else "bot"
        logger.info(f"DiscordNotificationChannel initialized in {mode} mode")

    @property
    def channel_id(self) -> str:
        """Return channel identifier."""
        return "discord"

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Return channel capabilities."""
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            # Buttons only available in bot mode with running bot
            supports_interactive_buttons=not self.use_webhook,
            supports_file_attachments=True,
            max_message_length=2000,
        )

    async def send_notification(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send HITL notification to Discord.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks

        Returns:
            NotificationDeliveryResult with delivery status
        """
        if self.use_webhook:
            return await self._send_via_webhook(
                procedure_id, request_id, request, callback_url
            )
        else:
            return await self._send_via_bot(
                procedure_id, request_id, request, callback_url
            )

    async def _send_via_webhook(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """Send via Discord webhook (fire-and-forget)."""
        import httpx

        embed_data = self._build_embed_dict(procedure_id, request_id, request)

        # Add callback info to embed for manual response
        embed_data["fields"].append(
            {
                "name": "Respond via",
                "value": f"Use your Tactus interface or API to respond to request `{request_id}`",
                "inline": False,
            }
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json={"embeds": [embed_data]},
                    params={"wait": "true"},  # Get message ID back
                    timeout=10.0,
                )

                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get("id", "")

                    logger.info(
                        f"Sent Discord webhook notification for {request_id}: {message_id}"
                    )

                    return NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id=f"webhook:{message_id}",
                        delivered_at=datetime.now(timezone.utc),
                        success=True,
                    )
                else:
                    error = f"Discord webhook returned {response.status_code}"
                    logger.error(f"{error}: {response.text}")
                    return NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id="",
                        delivered_at=datetime.now(timezone.utc),
                        success=False,
                        error_message=error,
                    )

        except Exception as e:
            logger.exception(f"Failed to send Discord webhook for {request_id}")
            return NotificationDeliveryResult(
                channel_id=self.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(e),
            )

    async def _send_via_bot(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send via Discord bot (supports buttons).

        Note: This creates a temporary client connection. For production,
        you should maintain a persistent bot connection and pass messages
        through it.
        """
        try:
            # Create temporary client
            intents = discord.Intents.default()
            client = discord.Client(intents=intents)

            result = None

            @client.event
            async def on_ready():
                nonlocal result
                try:
                    guild = client.get_guild(int(self.guild_id))
                    if not guild:
                        result = NotificationDeliveryResult(
                            channel_id=self.channel_id,
                            external_message_id="",
                            delivered_at=datetime.now(timezone.utc),
                            success=False,
                            error_message=f"Guild {self.guild_id} not found",
                        )
                        await client.close()
                        return

                    channel = discord.utils.get(
                        guild.text_channels, name=self.default_channel
                    )
                    if not channel:
                        result = NotificationDeliveryResult(
                            channel_id=self.channel_id,
                            external_message_id="",
                            delivered_at=datetime.now(timezone.utc),
                            success=False,
                            error_message=f"Channel {self.default_channel} not found",
                        )
                        await client.close()
                        return

                    embed = self._build_embed(procedure_id, request_id, request)
                    view = self._build_view(request_id, request, callback_url)

                    message = await channel.send(embed=embed, view=view)

                    result = NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id=f"{channel.id}:{message.id}",
                        delivered_at=datetime.now(timezone.utc),
                        success=True,
                    )

                    logger.info(
                        f"Sent Discord bot notification for {request_id}: {message.id}"
                    )

                except Exception as e:
                    result = NotificationDeliveryResult(
                        channel_id=self.channel_id,
                        external_message_id="",
                        delivered_at=datetime.now(timezone.utc),
                        success=False,
                        error_message=str(e),
                    )
                finally:
                    await client.close()

            await client.start(self.token)
            return result

        except Exception as e:
            logger.exception(f"Failed to send Discord bot notification for {request_id}")
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
        Update Discord message to show it was resolved.

        Args:
            external_message_id: Format: "channel_id:message_id" or "webhook:message_id"
            reason: Reason for cancellation
        """
        # For webhook mode, we can't easily update messages
        if external_message_id.startswith("webhook:"):
            logger.debug(
                f"Cannot update webhook message {external_message_id} - fire-and-forget mode"
            )
            return

        # For bot mode, would need persistent connection
        logger.debug(
            f"Skipping Discord message update for {external_message_id} - "
            f"would require persistent bot connection"
        )

    def _build_embed(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> "Embed":
        """Build Discord embed."""
        color = self._get_color(request.request_type)
        emoji = self._get_emoji(request.request_type)

        embed = Embed(
            title=f"{emoji} {request.request_type.title()} Required",
            description=request.message[:2000],
            color=color,
            timestamp=datetime.now(timezone.utc),
        )

        embed.add_field(name="Procedure", value=f"`{procedure_id}`", inline=True)
        embed.add_field(name="Request ID", value=f"`{request_id}`", inline=True)

        embed.set_footer(text="Tactus HITL Notification")

        return embed

    def _build_embed_dict(
        self, procedure_id: str, request_id: str, request: HITLRequest
    ) -> Dict[str, Any]:
        """Build Discord embed as dict (for webhook)."""
        color = self._get_color_int(request.request_type)
        emoji = self._get_emoji(request.request_type)

        return {
            "title": f"{emoji} {request.request_type.title()} Required",
            "description": request.message[:2000],
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fields": [
                {"name": "Procedure", "value": f"`{procedure_id}`", "inline": True},
                {"name": "Request ID", "value": f"`{request_id}`", "inline": True},
            ],
            "footer": {"text": "Tactus HITL Notification"},
        }

    def _build_view(
        self, request_id: str, request: HITLRequest, callback_url: str
    ) -> Optional["discord.ui.View"]:
        """Build Discord button view."""
        if request.request_type != "approval":
            return None

        view = discord.ui.View(timeout=None)

        # Create buttons that store callback info
        approve_button = discord.ui.Button(
            style=discord.ButtonStyle.success,
            label="Approve",
            custom_id=f"hitl_approve:{request_id}",
        )
        reject_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="Reject",
            custom_id=f"hitl_reject:{request_id}",
        )

        view.add_item(approve_button)
        view.add_item(reject_button)

        return view

    def _get_color(self, request_type: str) -> "Colour":
        """Get Discord color for request type."""
        colors = {
            "approval": Colour.gold(),
            "input": Colour.blue(),
            "review": Colour.purple(),
            "escalation": Colour.red(),
        }
        return colors.get(request_type.lower(), Colour.greyple())

    def _get_color_int(self, request_type: str) -> int:
        """Get Discord color as int for webhook."""
        colors = {
            "approval": 0xFFD700,  # Gold
            "input": 0x3498DB,  # Blue
            "review": 0x9B59B6,  # Purple
            "escalation": 0xE74C3C,  # Red
        }
        return colors.get(request_type.lower(), 0x95A5A6)  # Grey

    def _get_emoji(self, request_type: str) -> str:
        """Get emoji for request type."""
        return {
            "approval": ":question:",
            "input": ":pencil:",
            "review": ":mag:",
            "escalation": ":rotating_light:",
        }.get(request_type.lower(), ":bell:")
