"""
Slack Interactivity Handler for processing button clicks.

When users click buttons in Slack messages, Slack POSTs to your
interactivity endpoint. This handler processes those payloads
and forwards responses to the Tactus callback URL.

Setup:
1. In Slack App settings, enable "Interactivity"
2. Set the Request URL to your interactivity endpoint
3. Wire this handler to that endpoint

Example FastAPI integration:
    from tactus.adapters.channels.slack_interactivity import SlackInteractivityHandler

    slack_handler = SlackInteractivityHandler(signing_secret="...")

    @app.post("/slack/interactivity")
    async def slack_interactivity(request: Request):
        # Slack sends as application/x-www-form-urlencoded with payload param
        form = await request.form()
        payload = json.loads(form.get("payload", "{}"))
        signature = request.headers.get("X-Slack-Signature")
        timestamp = request.headers.get("X-Slack-Request-Timestamp")
        body = await request.body()
        return await slack_handler.handle(payload, body, signature, timestamp)
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


class SlackInteractivityHandler:
    """
    Handles Slack interactive component payloads.

    Slack POSTs to your interactivity endpoint when users click buttons.
    This handler:
    1. Verifies the request signature
    2. Extracts the callback URL and value from the button
    3. Forwards the response to Tactus
    4. Returns an updated message to Slack
    """

    def __init__(self, signing_secret: Optional[str] = None):
        """
        Initialize interactivity handler.

        Args:
            signing_secret: Slack app signing secret for request verification
        """
        self.signing_secret = signing_secret

    async def handle(
        self,
        payload: Dict[str, Any],
        raw_body: Optional[bytes] = None,
        signature: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle Slack interactivity payload.

        Args:
            payload: Parsed payload from Slack
            raw_body: Raw request body for signature verification
            signature: X-Slack-Signature header
            timestamp: X-Slack-Request-Timestamp header

        Returns:
            Response dict for Slack (message update)
        """
        # Verify signature if signing secret is configured
        if self.signing_secret:
            if not self._verify_signature(raw_body, signature, timestamp):
                logger.warning("Invalid Slack signature")
                return {"response_action": "errors", "errors": {"general": "Invalid signature"}}

        # Extract action from payload
        actions = payload.get("actions", [])
        if not actions:
            logger.warning("No actions in payload")
            return {}

        action = actions[0]
        action_id = action.get("action_id", "")
        action_value = action.get("value", "{}")

        # Parse action value
        try:
            action_data = json.loads(action_value)
        except json.JSONDecodeError:
            logger.warning(f"Invalid action value: {action_value}")
            return self._error_response("Invalid action data")

        request_id = action_data.get("request_id")
        callback_url = action_data.get("callback_url")
        value = action_data.get("value")

        if not request_id or not callback_url:
            logger.warning("Missing request_id or callback_url")
            return self._error_response("Invalid action configuration")

        # Get user info
        user = payload.get("user", {})
        user_id = user.get("id")
        user_name = user.get("name") or user.get("username")

        # Forward to Tactus callback
        success = await self._forward_response(
            callback_url=callback_url,
            request_id=request_id,
            value=value,
            user_id=user_id,
            user_name=user_name,
        )

        if not success:
            return self._error_response("Failed to process response")

        # Return updated message
        return self._success_response(action_id, user_name, value)

    async def _forward_response(
        self,
        callback_url: str,
        request_id: str,
        value: Any,
        user_id: Optional[str],
        user_name: Optional[str],
    ) -> bool:
        """
        Forward response to Tactus callback URL.

        Args:
            callback_url: Tactus callback URL
            request_id: HITL request ID
            value: Response value
            user_id: Slack user ID
            user_name: Slack username

        Returns:
            True if forwarding succeeded
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    callback_url,
                    json={
                        "channel_id": "slack",
                        "value": value,
                        "responder_id": user_id,
                        "responder_name": user_name,
                        "metadata": {
                            "source": "slack_interactivity",
                            "request_id": request_id,
                        },
                    },
                    timeout=10.0,
                )

                if response.status_code == 200:
                    logger.info(f"Forwarded Slack response for {request_id}")
                    return True
                else:
                    logger.warning(
                        f"Callback returned {response.status_code} for {request_id}: "
                        f"{response.text}"
                    )
                    return False

        except Exception:
            logger.exception(f"Failed to forward Slack response for {request_id}")
            return False

    def _verify_signature(
        self,
        raw_body: Optional[bytes],
        signature: Optional[str],
        timestamp: Optional[str],
    ) -> bool:
        """
        Verify Slack request signature.

        Slack uses: v0=HMAC-SHA256(signing_secret, "v0:{timestamp}:{body}")

        Args:
            raw_body: Raw request body
            signature: X-Slack-Signature header
            timestamp: X-Slack-Request-Timestamp header

        Returns:
            True if signature is valid
        """
        if not self.signing_secret:
            return True

        if not raw_body or not signature or not timestamp:
            return False

        # Check timestamp to prevent replay attacks (5 min window)
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 60 * 5:
                return False
        except ValueError:
            return False

        # Compute expected signature
        sig_basestring = f"v0:{timestamp}:{raw_body.decode('utf-8')}"
        expected = (
            "v0="
            + hmac.new(
                self.signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(expected, signature)

    def _success_response(
        self, action_id: str, user_name: Optional[str], value: Any
    ) -> Dict[str, Any]:
        """
        Build success response for Slack.

        Returns a message update that replaces the original message
        with a resolved status.
        """
        # Determine what action was taken
        if "approve" in action_id:
            status = ":white_check_mark: Approved"
        elif "reject" in action_id:
            status = ":x: Rejected"
        elif "changes" in action_id:
            status = ":pencil: Changes Requested"
        else:
            status = ":white_check_mark: Responded"

        by_text = f" by {user_name}" if user_name else ""

        return {
            "response_type": "in_channel",
            "replace_original": True,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{status}{by_text}",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Response: `{json.dumps(value) if not isinstance(value, bool) else value}`",
                        }
                    ],
                },
            ],
        }

    def _error_response(self, error: str) -> Dict[str, Any]:
        """Build error response for Slack."""
        return {
            "response_type": "ephemeral",
            "text": f":warning: {error}",
        }
