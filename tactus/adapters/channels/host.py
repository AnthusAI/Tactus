"""
Host app control channel base class.

Provides the pattern for any app embedding Tactus to become a control channel.
The CLI is the simplest example, but this applies to any host app: web servers,
desktop apps, Jupyter notebooks, etc.

Key features:
- Interruptible via background thread pattern
- Can be cancelled if another channel responds first
- Races with remote channels - first response wins
"""

import asyncio
import logging
import threading
from abc import abstractmethod
from typing import Any, Optional
from datetime import datetime, timezone

from tactus.protocols.control import (
    ControlRequest,
    ControlResponse,
    ChannelCapabilities,
    DeliveryResult,
)
from tactus.adapters.channels.base import InProcessChannel

logger = logging.getLogger(__name__)


class HostControlChannel(InProcessChannel):
    """
    Base class for host app control channels.

    Any app embedding Tactus can extend this to become a control channel.
    The channel uses a background thread for input collection so it can
    be interrupted if another channel responds first.

    Subclasses must implement:
    - _prompt_for_input(): Display prompt and collect input (runs in thread)
    - _show_cancelled(): Display cancellation message

    The background thread pattern:
    1. send() displays the request and starts a background thread
    2. Thread calls _prompt_for_input() which blocks on user input
    3. If input received, push_response() adds to queue
    4. If cancel() called first, thread is interrupted via _cancel_event
    5. _show_cancelled() displays "Responded via {channel}" message
    """

    def __init__(self):
        """Initialize the host channel."""
        super().__init__()
        self._cancel_event = threading.Event()
        self._input_thread: Optional[threading.Thread] = None
        self._current_request: Optional[ControlRequest] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

    @property
    def capabilities(self) -> ChannelCapabilities:
        """Host channels support immediate synchronous responses."""
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_interactive_buttons=False,
            supports_file_attachments=False,
            max_message_length=None,
            is_synchronous=True,
        )

    async def send(self, request: ControlRequest) -> DeliveryResult:
        """
        Display the request and start background input collection.

        The actual prompt is displayed and input collected in a background
        thread so we can be interrupted if another channel responds first.

        Args:
            request: ControlRequest with full context

        Returns:
            DeliveryResult indicating successful delivery
        """
        logger.info(
            "%s: sending notification for %s",
            self.channel_id,
            request.request_id,
        )

        # Store for background thread access
        self._current_request = request
        self._cancel_event.clear()

        # Capture event loop for thread-safe response pushing
        self._event_loop = asyncio.get_event_loop()

        # Display the request (synchronous, before starting thread)
        self._display_request(request)

        # Start background thread for input collection
        self._input_thread = threading.Thread(
            target=self._input_thread_main,
            args=(request,),
            daemon=True,
        )
        self._input_thread.start()

        return DeliveryResult(
            channel_id=self.channel_id,
            external_message_id=request.request_id,
            delivered_at=datetime.now(timezone.utc),
            success=True,
        )

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """
        Cancel the prompt - another channel responded first.

        Sets the cancel event to interrupt the background thread,
        then displays a message indicating another channel responded.

        Args:
            external_message_id: Request ID (same as sent)
            reason: Reason for cancellation (e.g., "Responded via tactus_cloud")
        """
        logger.debug(
            "%s: cancelling %s: %s",
            self.channel_id,
            external_message_id,
            reason,
        )
        self._cancel_event.set()
        self._show_cancelled(reason)

    async def shutdown(self) -> None:
        """Clean shutdown - cancel any pending input."""
        await super().shutdown()
        self._cancel_event.set()
        if self._input_thread and self._input_thread.is_alive():
            self._input_thread.join(timeout=1.0)

    def _input_thread_main(self, request: ControlRequest) -> None:
        """
        Background thread main function.

        Collects input from the user and pushes the response to the queue.
        Can be interrupted via _cancel_event.

        Args:
            request: The control request to handle
        """
        try:
            # Collect input (may block)
            response_value = self._prompt_for_input(request)

            # Check if cancelled while waiting
            if self._cancel_event.is_set():
                return

            if response_value is not None:
                # Create response and push to queue
                response = ControlResponse(
                    request_id=request.request_id,
                    value=response_value,
                    responded_at=datetime.now(timezone.utc),
                    timed_out=False,
                    channel_id=self.channel_id,
                )

                # Push thread-safe
                if self._event_loop:
                    self.push_response_threadsafe(response, self._event_loop)
                else:
                    self.push_response(response)

        except Exception as error:
            if not self._cancel_event.is_set():
                logger.error("%s: input error: %s", self.channel_id, error)

    @abstractmethod
    def _display_request(self, request: ControlRequest) -> None:
        """
        Display the control request to the user.

        Called synchronously before starting input thread.
        Should display the message, options, context, etc.

        Args:
            request: The control request to display
        """
        ...

    @abstractmethod
    def _prompt_for_input(self, request: ControlRequest) -> Optional[Any]:
        """
        Collect input from the user.

        Runs in a background thread. Should check _cancel_event periodically
        if blocking on long operations. Returns None if cancelled.

        Args:
            request: The control request being handled

        Returns:
            The user's response value, or None if cancelled/interrupted
        """
        ...

    @abstractmethod
    def _show_cancelled(self, reason: str) -> None:
        """
        Show cancellation message.

        Called when another channel responds first.

        Args:
            reason: Reason for cancellation (e.g., "Responded via tactus_cloud")
        """
        ...

    def is_cancelled(self) -> bool:
        """
        Check if the current request has been cancelled.

        Call this periodically from _prompt_for_input() if your input
        method supports checking for interruption.

        Returns:
            True if cancelled, False otherwise
        """
        return self._cancel_event.is_set()
