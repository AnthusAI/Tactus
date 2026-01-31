"""
Broker Control Channel for container-to-host HITL requests.

Used inside Docker containers to forward control requests through the broker
to the host's SSE channel (or other host-side control channels).
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

from tactus.adapters.channels.base import InProcessChannel
from tactus.protocols.control import (
    ChannelCapabilities,
    ControlRequest,
    ControlResponse,
    DeliveryResult,
)

logger = logging.getLogger(__name__)


class BrokerControlChannel(InProcessChannel):
    """
    Control channel that forwards requests through broker to host.

    Used when running inside a container with broker transport.
    The broker server on the host relays to the actual control channels
    (SSE, CLI, etc.) and returns responses.

    Architecture:
    - Container sends control.request via BrokerClient
    - Host broker receives and forwards to SSE channel
    - SSE channel delivers to IDE UI
    - User responds in IDE
    - Response flows back through broker to container
    """

    def __init__(self, client):
        """
        Initialize broker control channel.

        Args:
            client: BrokerClient instance for communication with host
        """
        super().__init__()
        from tactus.broker.client import BrokerClient

        if not isinstance(client, BrokerClient):
            raise TypeError(f"Expected BrokerClient, got {type(client)}")

        self._client = client

    @property
    def channel_id(self) -> str:
        return "broker"

    @property
    def capabilities(self) -> ChannelCapabilities:
        # Mirror SSE capabilities since broker relays to SSE
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_select=True,
            supports_upload=True,
            supports_inputs=True,  # Batched inputs
            supports_interactive_buttons=True,
            is_synchronous=False,  # Async relay through broker
        )

    async def initialize(self) -> None:
        """Initialize broker control channel (broker already connected)."""
        logger.info("%s: initializing...", self.channel_id)
        # Broker client already initialized by BrokerLogHandler setup
        logger.info("%s: ready (via broker)", self.channel_id)

    async def send(self, request: ControlRequest) -> DeliveryResult:
        """
        Send control request through broker to host.

        The request is serialized and sent via broker's control.request method.
        The host will relay to its SSE channel and return the response.
        """
        logger.info(
            "%s: sending control request %s via broker",
            self.channel_id,
            request.request_id,
        )

        try:
            # Serialize request to JSON-compatible dict
            request_data = request.model_dump(mode="json")

            # Send via broker and wait for response events
            async for event in self._client._request("control.request", {"request": request_data}):
                event_type = event.get("event")

                if event_type == "delivered":
                    # Request successfully delivered to host channels
                    logger.debug(
                        "%s: request %s delivered",
                        self.channel_id,
                        request.request_id,
                    )
                    continue

                elif event_type == "response":
                    # Got response from host
                    response_data = event.get("data", {})
                    response = ControlResponse(
                        request_id=request.request_id,
                        value=response_data.get("value"),
                        responded_at=datetime.now(timezone.utc),
                        timed_out=response_data.get("timed_out", False),
                        channel_id=response_data.get("channel_id", "sse"),
                        responder_id=response_data.get("responder_id"),
                    )
                    logger.info(
                        "%s: received response for %s",
                        self.channel_id,
                        request.request_id,
                    )
                    self._response_queue.put_nowait(response)
                    break

                elif event_type == "timeout":
                    # Host-side timeout
                    logger.warning(
                        "%s: timeout for %s",
                        self.channel_id,
                        request.request_id,
                    )
                    response = ControlResponse(
                        request_id=request.request_id,
                        value=request.default_value,
                        responded_at=datetime.now(timezone.utc),
                        timed_out=True,
                        channel_id="broker",
                    )
                    self._response_queue.put_nowait(response)
                    break

                elif event_type == "error":
                    # Delivery or processing error
                    error = event.get("error", {})
                    error_msg = error.get("message", "Unknown broker error")
                    logger.error(
                        "%s: error for %s: %s",
                        self.channel_id,
                        request.request_id,
                        error_msg,
                    )
                    raise RuntimeError(f"Broker control request failed: {error_msg}")

            return DeliveryResult(
                channel_id=self.channel_id,
                external_message_id=request.request_id,
                delivered_at=datetime.now(timezone.utc),
                success=True,
            )

        except Exception as error:
            logger.error(
                "%s: failed to send %s: %s",
                self.channel_id,
                request.request_id,
                error,
            )
            return DeliveryResult(
                channel_id=self.channel_id,
                external_message_id=request.request_id,
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(error),
            )

    @classmethod
    def from_environment(cls) -> Optional["BrokerControlChannel"]:
        """
        Create BrokerControlChannel from environment if broker is available.

        Checks for TACTUS_BROKER_SOCKET environment variable and creates
        a broker client if found.

        Returns:
            BrokerControlChannel instance if broker available, None otherwise
        """
        socket_path = os.environ.get("TACTUS_BROKER_SOCKET")
        if not socket_path:
            return None

        try:
            from tactus.broker.client import BrokerClient

            client = BrokerClient(socket_path)
            logger.info(
                "BrokerControlChannel: initialized from environment (socket=%s)",
                socket_path,
            )
            return cls(client)
        except Exception as error:
            logger.warning(
                "BrokerControlChannel: failed to initialize from environment: %s",
                error,
            )
            return None
