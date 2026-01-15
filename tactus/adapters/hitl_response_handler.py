"""
HITL Response Handler for processing responses from notification channels.

Provides a framework-agnostic handler that deployers can integrate with
their HTTP server (FastAPI, Flask, AWS Lambda, etc.).
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from tactus.protocols.models import HITLResponse
from tactus.protocols.notification import (
    NotificationChannel,
    PendingNotification,
    HITLResponsePayload,
    HITLResponseResult,
)
from tactus.protocols.storage import StorageBackend

logger = logging.getLogger(__name__)


class HITLResponseHandler:
    """
    Handles incoming HITL responses from notification channels.

    Deployers integrate this with their HTTP framework of choice.
    The handler is responsible for:
    1. Validating signatures (optional)
    2. Checking first-response-wins semantics
    3. Storing the response
    4. Cancelling notifications on other channels

    Example FastAPI integration:
        handler = HITLResponseHandler(storage, channels)

        @app.post("/hitl/response/{request_id}")
        async def hitl_response(request_id: str, body: dict):
            payload = HITLResponsePayload(**body)
            result = await handler.handle_response(request_id, payload)
            if result.success:
                # Optionally trigger procedure resume here
                pass
            return result.model_dump()

    Example Flask integration:
        handler = HITLResponseHandler(storage, channels)

        @app.route("/hitl/response/<request_id>", methods=["POST"])
        def hitl_response(request_id):
            payload = HITLResponsePayload(**request.json)
            result = asyncio.run(handler.handle_response(request_id, payload))
            return jsonify(result.model_dump())

    Example AWS Lambda integration:
        handler = HITLResponseHandler(storage, channels)

        def lambda_handler(event, context):
            request_id = event["pathParameters"]["request_id"]
            body = json.loads(event["body"])
            payload = HITLResponsePayload(**body)
            result = asyncio.run(handler.handle_response(request_id, payload))
            return {
                "statusCode": 200 if result.success else 400,
                "body": json.dumps(result.model_dump()),
            }
    """

    # Storage key prefix for pending notifications (must match MultichannelHITLHandler)
    PENDING_KEY_PREFIX = "hitl_pending:"

    def __init__(
        self,
        storage: StorageBackend,
        channels: List[NotificationChannel],
        signing_secret: Optional[str] = None,
    ):
        """
        Initialize response handler.

        Args:
            storage: Storage backend for loading/updating pending notifications
            channels: List of notification channels (for cancellation)
            signing_secret: Optional secret for verifying request signatures
        """
        self.storage = storage
        self.channels = {c.channel_id: c for c in channels}
        self.signing_secret = signing_secret

        logger.info(
            f"HITLResponseHandler initialized with channels: "
            f"{list(self.channels.keys())}"
        )

    async def handle_response(
        self,
        request_id: str,
        payload: HITLResponsePayload,
        signature: Optional[str] = None,
        raw_body: Optional[bytes] = None,
    ) -> HITLResponseResult:
        """
        Process an incoming HITL response.

        Steps:
        1. Validate signature (if signing enabled)
        2. Load pending notification
        3. Check if already responded (first wins)
        4. Store response
        5. Cancel notifications on other channels

        Args:
            request_id: The request ID from the URL path
            payload: The response payload from the channel
            signature: Optional signature header for verification
            raw_body: Optional raw request body for signature verification

        Returns:
            HITLResponseResult with success status and details
        """
        logger.info(
            f"Processing HITL response for request {request_id} "
            f"from channel {payload.channel_id}"
        )

        # Verify signature if signing is enabled
        if self.signing_secret:
            if not signature or not raw_body:
                logger.warning(f"Missing signature for request {request_id}")
                return HITLResponseResult(
                    success=False,
                    error="Missing signature",
                )
            if not self._verify_signature(raw_body, signature):
                logger.warning(f"Invalid signature for request {request_id}")
                return HITLResponseResult(
                    success=False,
                    error="Invalid signature",
                )

        # Load pending notification
        pending = self._load_pending(request_id)
        if not pending:
            logger.warning(f"Unknown request ID: {request_id}")
            return HITLResponseResult(
                success=False,
                error="Unknown request",
            )

        # Check if already responded (first wins)
        if pending.responded:
            logger.info(
                f"Request {request_id} already responded via {pending.response_channel}"
            )
            return HITLResponseResult(
                success=False,
                error="Already responded",
                already_responded=True,
            )

        # Create HITLResponse
        response = HITLResponse(
            value=payload.value,
            responded_at=datetime.now(timezone.utc),
            timed_out=False,
        )

        # Update pending notification
        pending.responded = True
        pending.response = response
        pending.response_channel = payload.channel_id
        self._store_pending(pending)

        logger.info(
            f"HITL response recorded for request {request_id}: "
            f"value={payload.value}, channel={payload.channel_id}"
        )

        # Cancel notifications on other channels
        await self._cancel_other_channels(pending, payload.channel_id)

        return HITLResponseResult(
            success=True,
            procedure_id=pending.procedure_id,
            response=response,
        )

    async def _cancel_other_channels(
        self, pending: PendingNotification, responded_channel: str
    ) -> None:
        """
        Cancel notifications on channels that didn't respond.

        Args:
            pending: The pending notification
            responded_channel: Channel that provided the response
        """
        reason = f"Resolved via {responded_channel}"

        for delivery in pending.deliveries:
            if delivery.success and delivery.channel_id != responded_channel:
                channel = self.channels.get(delivery.channel_id)
                if channel:
                    try:
                        await channel.cancel_notification(
                            delivery.external_message_id, reason
                        )
                        logger.debug(
                            f"Cancelled notification on {delivery.channel_id}: "
                            f"{delivery.external_message_id}"
                        )
                    except Exception:
                        logger.exception(
                            f"Failed to cancel notification on {delivery.channel_id}"
                        )

    def _verify_signature(self, raw_body: bytes, signature: str) -> bool:
        """
        Verify webhook signature.

        Uses HMAC-SHA256 with the signing secret.

        Args:
            raw_body: Raw request body bytes
            signature: Signature from request header

        Returns:
            True if signature is valid
        """
        if not self.signing_secret:
            return True

        expected = hmac.new(
            self.signing_secret.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, signature)

    def _load_pending(self, request_id: str) -> Optional[PendingNotification]:
        """Load pending notification from storage backend."""
        parts = request_id.split(":", 1)
        if len(parts) != 2:
            return None

        procedure_id = parts[0]
        key = f"{self.PENDING_KEY_PREFIX}{request_id}"

        state = self.storage.get_state(procedure_id) or {}
        if key in state:
            return PendingNotification.model_validate(state[key])
        return None

    def _store_pending(self, pending: PendingNotification) -> None:
        """Store pending notification in storage backend."""
        key = f"{self.PENDING_KEY_PREFIX}{pending.request_id}"
        state = self.storage.get_state(pending.procedure_id) or {}
        state[key] = pending.model_dump(mode="json")
        self.storage.set_state(pending.procedure_id, state)

    def get_pending_response(self, request_id: str) -> Optional[HITLResponse]:
        """
        Get response for a pending request if available.

        Utility method for checking if a response has been received
        without going through the full handle_response flow.

        Args:
            request_id: The request ID to check

        Returns:
            HITLResponse if available, None otherwise
        """
        pending = self._load_pending(request_id)
        if pending and pending.responded:
            return pending.response
        return None


def create_signature(body: bytes, secret: str) -> str:
    """
    Create a signature for a request body.

    Utility function for channels that need to sign their callbacks.

    Args:
        body: Request body bytes
        secret: Signing secret

    Returns:
        HMAC-SHA256 signature as hex string
    """
    return hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
