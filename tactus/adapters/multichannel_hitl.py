"""
Multichannel HITL handler for omnichannel notifications.

Fans out HITL requests to multiple notification channels and coordinates
responses using the first-response-wins pattern.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.protocols.models import HITLRequest, HITLResponse
from tactus.protocols.notification import (
    NotificationChannel,
    NotificationDeliveryResult,
    PendingNotification,
)
from tactus.protocols.storage import StorageBackend

logger = logging.getLogger(__name__)


class MultichannelHITLHandler:
    """
    HITL handler that fans out to multiple notification channels.

    Implements the HITLHandler protocol while coordinating multiple
    NotificationChannel plugins. Uses first-response-wins pattern.

    On request_interaction():
    1. Generates unique request_id
    2. Sends to all enabled channels concurrently
    3. Stores pending notification in storage
    4. Raises ProcedureWaitingForHuman to pause execution

    Response handling is done via HITLResponseHandler (separate component).

    Example:
        channels = [
            SlackNotificationChannel(token="...", default_channel="#alerts"),
            DiscordNotificationChannel(token="...", guild_id="..."),
        ]
        handler = MultichannelHITLHandler(
            channels=channels,
            storage=storage_backend,
            callback_base_url="https://my-tactus.example.com",
        )
        runtime = TactusRuntime(hitl_handler=handler, ...)
    """

    # Storage key prefix for pending notifications
    PENDING_KEY_PREFIX = "hitl_pending:"

    def __init__(
        self,
        channels: List[NotificationChannel],
        storage: StorageBackend,
        callback_base_url: str,
        signing_secret: Optional[str] = None,
    ):
        """
        Initialize multichannel HITL handler.

        Args:
            channels: List of enabled notification channels
            storage: Storage backend for persisting pending notifications
            callback_base_url: Base URL for response callbacks
                (e.g., "https://my-tactus.example.com")
            signing_secret: Optional secret for signing callback URLs
        """
        self.channels = channels
        self.storage = storage
        self.callback_base_url = callback_base_url.rstrip("/")
        self.signing_secret = signing_secret

        logger.info(
            f"MultichannelHITLHandler initialized with {len(channels)} channels: "
            f"{[c.channel_id for c in channels]}"
        )

    def request_interaction(
        self, procedure_id: str, request: HITLRequest
    ) -> HITLResponse:
        """
        Request human interaction by notifying all channels.

        Sends notifications to all enabled channels concurrently, stores
        the pending notification, and raises ProcedureWaitingForHuman to
        pause execution.

        Args:
            procedure_id: Unique procedure identifier
            request: HITLRequest with interaction details

        Returns:
            Never returns normally - always raises ProcedureWaitingForHuman

        Raises:
            ProcedureWaitingForHuman: To signal workflow suspension
        """
        request_id = self._generate_request_id(procedure_id)
        callback_url = f"{self.callback_base_url}/hitl/response/{request_id}"

        logger.info(
            f"HITL request {request_id} for procedure {procedure_id}: "
            f"{request.request_type} - {request.message[:50]}..."
        )

        # Send to all channels concurrently
        deliveries = asyncio.get_event_loop().run_until_complete(
            self._fanout(procedure_id, request_id, request, callback_url)
        )

        # Log delivery results
        successful = [d for d in deliveries if d.success]
        failed = [d for d in deliveries if not d.success]
        logger.info(
            f"HITL request {request_id}: {len(successful)} successful deliveries, "
            f"{len(failed)} failed"
        )
        for d in failed:
            logger.warning(f"  Failed delivery to {d.channel_id}: {d.error_message}")

        # Store pending notification
        pending = PendingNotification(
            request_id=request_id,
            procedure_id=procedure_id,
            request=request,
            deliveries=deliveries,
            created_at=datetime.now(timezone.utc),
            callback_url=callback_url,
        )
        self._store_pending(pending)

        # Raise to pause execution
        raise ProcedureWaitingForHuman(procedure_id, request_id)

    def check_pending_response(
        self, procedure_id: str, message_id: str
    ) -> Optional[HITLResponse]:
        """
        Check if there's a response to a pending HITL request.

        Used during resume flow to check if human has responded.

        Args:
            procedure_id: Unique procedure identifier
            message_id: Request ID (message_id in this context)

        Returns:
            HITLResponse if response exists, None otherwise
        """
        pending = self._load_pending(message_id)
        if pending and pending.responded and pending.response:
            logger.info(
                f"Found response for request {message_id} from {pending.response_channel}"
            )
            return pending.response
        return None

    def cancel_pending_request(self, procedure_id: str, message_id: str) -> None:
        """
        Cancel a pending HITL request.

        Removes the pending notification and cancels notifications on all channels.

        Args:
            procedure_id: Unique procedure identifier
            message_id: Request ID to cancel
        """
        pending = self._load_pending(message_id)
        if not pending:
            logger.warning(f"Cannot cancel unknown request {message_id}")
            return

        # Cancel on all channels
        asyncio.get_event_loop().run_until_complete(
            self._cancel_all_channels(pending, "Request cancelled")
        )

        # Remove from storage
        self._delete_pending(message_id)
        logger.info(f"Cancelled HITL request {message_id}")

    async def _fanout(
        self,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> List[NotificationDeliveryResult]:
        """
        Send notification to all channels concurrently.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Unique request identifier
            request: HITLRequest with interaction details
            callback_url: URL for response callbacks

        Returns:
            List of delivery results from all channels
        """
        # Filter channels that support this request type
        eligible_channels = [
            channel
            for channel in self.channels
            if self._channel_supports_request(channel, request)
        ]

        if not eligible_channels:
            logger.warning(
                f"No channels support {request.request_type} requests. "
                f"Available channels: {[c.channel_id for c in self.channels]}"
            )
            return []

        # Send to all eligible channels concurrently
        tasks = [
            self._send_with_error_handling(
                channel, procedure_id, request_id, request, callback_url
            )
            for channel in eligible_channels
        ]

        results = await asyncio.gather(*tasks)
        return list(results)

    async def _send_with_error_handling(
        self,
        channel: NotificationChannel,
        procedure_id: str,
        request_id: str,
        request: HITLRequest,
        callback_url: str,
    ) -> NotificationDeliveryResult:
        """
        Send notification with error handling.

        Wraps channel.send_notification() to catch exceptions and return
        a failed delivery result instead of propagating errors.
        """
        try:
            return await channel.send_notification(
                procedure_id=procedure_id,
                request_id=request_id,
                request=request,
                callback_url=callback_url,
            )
        except Exception as e:
            logger.exception(f"Failed to send notification to {channel.channel_id}")
            return NotificationDeliveryResult(
                channel_id=channel.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(e),
            )

    def _channel_supports_request(
        self, channel: NotificationChannel, request: HITLRequest
    ) -> bool:
        """
        Check if a channel supports the given request type.

        Args:
            channel: NotificationChannel to check
            request: HITLRequest to check support for

        Returns:
            True if channel can handle this request type
        """
        caps = channel.capabilities
        request_type = request.request_type.lower()

        if request_type == "approval":
            return caps.supports_approval
        elif request_type == "input":
            return caps.supports_input
        elif request_type == "review":
            return caps.supports_review
        elif request_type == "escalation":
            return caps.supports_escalation
        else:
            # Unknown type - allow all channels
            return True

    async def _cancel_all_channels(
        self, pending: PendingNotification, reason: str
    ) -> None:
        """
        Cancel notifications on all channels.

        Args:
            pending: The pending notification to cancel
            reason: Reason for cancellation
        """
        tasks = []
        for delivery in pending.deliveries:
            if delivery.success:
                channel = self._get_channel_by_id(delivery.channel_id)
                if channel:
                    tasks.append(
                        self._cancel_with_error_handling(
                            channel, delivery.external_message_id, reason
                        )
                    )

        if tasks:
            await asyncio.gather(*tasks)

    async def _cancel_with_error_handling(
        self, channel: NotificationChannel, external_message_id: str, reason: str
    ) -> None:
        """
        Cancel notification with error handling.

        Catches exceptions to prevent one channel's failure from affecting others.
        """
        try:
            await channel.cancel_notification(external_message_id, reason)
        except Exception:
            logger.exception(
                f"Failed to cancel notification on {channel.channel_id}: "
                f"{external_message_id}"
            )

    def _get_channel_by_id(self, channel_id: str) -> Optional[NotificationChannel]:
        """Get channel by its ID."""
        for channel in self.channels:
            if channel.channel_id == channel_id:
                return channel
        return None

    def _generate_request_id(self, procedure_id: str) -> str:
        """
        Generate unique request ID.

        Format: {procedure_id}:{uuid}
        """
        return f"{procedure_id}:{uuid.uuid4().hex[:12]}"

    def _store_pending(self, pending: PendingNotification) -> None:
        """Store pending notification in storage backend."""
        key = f"{self.PENDING_KEY_PREFIX}{pending.request_id}"
        state = self.storage.get_state(pending.procedure_id) or {}
        state[key] = pending.model_dump(mode="json")
        self.storage.set_state(pending.procedure_id, state)

    def _load_pending(self, request_id: str) -> Optional[PendingNotification]:
        """Load pending notification from storage backend."""
        # Extract procedure_id from request_id
        parts = request_id.split(":", 1)
        if len(parts) != 2:
            return None

        procedure_id = parts[0]
        key = f"{self.PENDING_KEY_PREFIX}{request_id}"

        state = self.storage.get_state(procedure_id) or {}
        if key in state:
            return PendingNotification.model_validate(state[key])
        return None

    def _delete_pending(self, request_id: str) -> None:
        """Delete pending notification from storage backend."""
        parts = request_id.split(":", 1)
        if len(parts) != 2:
            return

        procedure_id = parts[0]
        key = f"{self.PENDING_KEY_PREFIX}{request_id}"

        state = self.storage.get_state(procedure_id) or {}
        if key in state:
            del state[key]
            self.storage.set_state(procedure_id, state)

    def update_pending_with_response(
        self,
        request_id: str,
        response: HITLResponse,
        response_channel: str,
    ) -> Optional[PendingNotification]:
        """
        Update pending notification with response.

        Called by HITLResponseHandler when a response is received.
        Uses first-response-wins: returns None if already responded.

        Args:
            request_id: Request ID to update
            response: The response received
            response_channel: Channel that provided the response

        Returns:
            Updated PendingNotification if this was the first response,
            None if already responded
        """
        pending = self._load_pending(request_id)
        if not pending:
            return None

        if pending.responded:
            # Already responded - first response wins
            return None

        pending.responded = True
        pending.response = response
        pending.response_channel = response_channel
        self._store_pending(pending)

        return pending
