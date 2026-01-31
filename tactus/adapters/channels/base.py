"""
Base classes for control channel implementations.

Provides InProcessChannel for channels that work with asyncio in-process.
A DaemonChannel base class may be added later if needed for channels
requiring separate processes (e.g., Discord WebSocket gateway).
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

from tactus.protocols.control import (
    ControlRequest,
    ControlResponse,
    ChannelCapabilities,
    DeliveryResult,
)

logger = logging.getLogger(__name__)


class InProcessChannel(ABC):
    """
    Base class for control channels that run in-process with asyncio.

    Suitable for:
    - Host app channels (CLI, IDE server, Jupyter)
    - HTTP webhooks (Slack, Teams)
    - Queue polling (SQS, Redis)
    - Email (SMTP send)
    - WebSocket clients (Tactus Cloud)

    These channels coexist with the asyncio event loop and don't need
    separate processes.

    Subclasses must implement:
    - channel_id property
    - capabilities property
    - send() method

    Default implementations provided for:
    - initialize() - no-op
    - receive() - yields from internal response queue
    - cancel() - no-op
    - shutdown() - no-op

    The response queue pattern:
    - External handlers (webhooks, stdin readers, etc.) call push_response()
    - receive() yields from the queue
    - This bridges sync/async boundaries cleanly
    """

    def __init__(self):
        """Initialize the channel with an internal response queue."""
        self._response_queue: asyncio.Queue[ControlResponse] = asyncio.Queue()
        self._shutdown_event = asyncio.Event()

    @property
    @abstractmethod
    def channel_id(self) -> str:
        """Unique identifier for this channel."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> ChannelCapabilities:
        """Return channel capabilities."""
        ...

    async def initialize(self) -> None:
        """
        Initialize the channel.

        Default: no-op. Override for auth handshakes, connections, etc.
        """
        logger.info("%s: initializing...", self.channel_id)
        logger.info("%s: ready", self.channel_id)

    @abstractmethod
    async def send(self, request: ControlRequest) -> DeliveryResult:
        """
        Send a control request to this channel.

        Subclass must implement channel-specific send logic.

        Args:
            request: ControlRequest with full context

        Returns:
            DeliveryResult with delivery status
        """
        ...

    async def receive(self) -> AsyncIterator[ControlResponse]:
        """
        Yield responses as they arrive from the internal queue.

        External handlers (webhooks, stdin readers, etc.) call push_response()
        to add responses to the queue.

        Override for polling-based channels that need custom receive logic.

        Yields:
            ControlResponse as they are received
        """
        while not self._shutdown_event.is_set():
            try:
                # Use wait_for with timeout to check shutdown periodically
                response = await asyncio.wait_for(
                    self._response_queue.get(),
                    timeout=0.5,
                )
                logger.info(
                    "%s: received response for %s",
                    self.channel_id,
                    response.request_id,
                )
                yield response
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """
        Cancel or update a request when resolved via another channel.

        Default: no-op. Override for channels that support message updates
        (e.g., editing Slack messages, updating UI).

        Args:
            external_message_id: Channel-specific message ID
            reason: Reason for cancellation
        """
        logger.debug(
            "%s: cancelling %s: %s",
            self.channel_id,
            external_message_id,
            reason,
        )

    async def shutdown(self) -> None:
        """
        Clean shutdown of the channel.

        Default: sets shutdown event to stop receive loop.
        Override for additional cleanup (close connections, etc.).
        """
        logger.info("%s: shutting down", self.channel_id)
        self._shutdown_event.set()

    def push_response(self, response: ControlResponse) -> None:
        """
        Push a response to the internal queue.

        Called by external handlers (webhooks, stdin readers, etc.) when
        a response is received. This bridges sync/async boundaries.

        Thread-safe: can be called from non-async contexts.

        Args:
            response: ControlResponse to add to queue
        """
        try:
            self._response_queue.put_nowait(response)
        except Exception as error:
            logger.error("%s: failed to queue response: %s", self.channel_id, error)

    def push_response_threadsafe(
        self, response: ControlResponse, loop: asyncio.AbstractEventLoop
    ) -> None:
        """
        Push a response to the queue from another thread.

        Use this when calling from a background thread (e.g., stdin reader).

        Args:
            response: ControlResponse to add to queue
            loop: The event loop to use for thread-safe call
        """
        loop.call_soon_threadsafe(self._response_queue.put_nowait, response)
