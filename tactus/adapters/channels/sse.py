"""
SSE Control Channel for IDE integration.

Server-Sent Events channel that pushes HITL requests to connected IDEs
and receives responses via HTTP POST callbacks.
"""

import asyncio
import logging
import queue
from typing import Any, Optional
from datetime import datetime, timezone

from tactus.adapters.channels.base import InProcessChannel
from tactus.protocols.control import (
    ControlRequest,
    ControlResponse,
    ChannelCapabilities,
    DeliveryResult,
)

logger = logging.getLogger(__name__)


class SSEControlChannel(InProcessChannel):
    """
    Server-Sent Events channel for IDE HITL integration.

    Reuses existing Flask SSE infrastructure. Sends hitl.request events
    to connected IDE clients, receives responses via POST /hitl/response.

    Architecture:
    - send(): Pushes hitl.request event to SSE manager
    - receive(): Yields responses from internal queue
    - handle_ide_response(): Called by Flask POST endpoint to enqueue responses
    """

    def __init__(self, event_emitter: Optional[Any] = None):
        """
        Initialize SSE control channel.

        Args:
            event_emitter: Optional callable to emit SSE events.
                          If None, uses a queue that can be consumed externally.
        """
        super().__init__()
        self._event_emitter = event_emitter
        # Use thread-safe queue.Queue for sync access from Flask SSE stream
        self._event_queue: queue.Queue[dict[str, Any]] = queue.Queue()

    @property
    def channel_id(self) -> str:
        return "sse"

    @property
    def capabilities(self) -> ChannelCapabilities:
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_review=True,
            supports_escalation=True,
            supports_select=True,
            supports_upload=True,
            supports_inputs=True,  # Batched inputs support
            supports_interactive_buttons=True,
            max_message_length=None,  # No length limit for IDE
        )

    async def initialize(self) -> None:
        """Initialize SSE channel (no-op, Flask SSE already running)."""
        logger.info("%s: initializing...", self.channel_id)
        # No auth or connection needed - Flask SSE already set up
        logger.info("%s: ready", self.channel_id)

    async def send(self, request: ControlRequest) -> DeliveryResult:
        """
        Send HITL request as SSE event to connected IDEs.

        Creates a hitl.request event with rich context and pushes to SSE stream.
        """
        logger.info(
            "%s: sending notification for %s",
            self.channel_id,
            request.request_id,
        )

        try:
            # Build SSE event payload
            event_payload = self._build_hitl_event(request)

            # Emit event to SSE stream
            if self._event_emitter:
                await self._event_emitter(event_payload)
            else:
                # Queue for external consumption if no emitter (thread-safe)
                self._event_queue.put(event_payload)

            return DeliveryResult(
                channel_id=self.channel_id,
                external_message_id=request.request_id,
                delivered_at=datetime.now(timezone.utc),
                success=True,
            )

        except Exception as error:
            logger.error(
                "%s: failed to send notification: %s",
                self.channel_id,
                error,
            )
            return DeliveryResult(
                channel_id=self.channel_id,
                external_message_id=request.request_id,
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(error),
            )

    def _build_hitl_event(self, request: ControlRequest) -> dict:
        """
        Build SSE event payload from ControlRequest.

        Returns dict that will be serialized to JSON and sent as SSE event.
        """
        event_payload = {
            "event_type": "hitl.request",  # Frontend expects event_type, not type
            "request_id": request.request_id,
            # Identity
            "procedure_id": request.procedure_id,
            "procedure_name": request.procedure_name,
            "invocation_id": request.invocation_id,
            # Context
            "subject": request.subject,
            "started_at": request.started_at.isoformat() if request.started_at else None,
            "input_summary": request.input_summary,
            # The question
            "request_type": request.request_type,
            "message": request.message,
            "default_value": request.default_value,
            "timeout_seconds": request.timeout_seconds,
            # Options
            "options": (
                [
                    {
                        "label": opt.label,
                        "value": opt.value,
                        "style": opt.style,
                        "description": opt.description,
                    }
                    for opt in request.options
                ]
                if request.options
                else []
            ),
            # For batched inputs requests
            "items": (
                [
                    {
                        "item_id": item.item_id,
                        "label": item.label,
                        "request_type": item.request_type,
                        "message": item.message,
                        "options": (
                            [
                                {
                                    "label": opt.label,
                                    "value": opt.value,
                                    "style": opt.style,
                                    "description": opt.description,
                                }
                                for opt in item.options
                            ]
                            if item.options
                            else []
                        ),
                        "default_value": item.default_value,
                        "required": item.required,
                        "metadata": item.metadata,
                    }
                    for item in request.items
                ]
                if request.items
                else []
            ),
            # Rich context for decision-making
            "conversation": request.conversation,
            "prior_interactions": request.prior_interactions,
            # New context architecture (Phase 5)
            "runtime_context": self._serialize_runtime_context(request.runtime_context),
            "application_context": (
                [
                    {
                        "name": link.name,
                        "value": link.value,
                        "url": link.url,
                    }
                    for link in request.application_context
                ]
                if request.application_context
                else []
            ),
            # Additional metadata
            "metadata": request.metadata,
        }

        return event_payload

    def _serialize_runtime_context(self, runtime_context) -> Optional[dict]:
        """Serialize RuntimeContext to dict for SSE payload."""
        if not runtime_context:
            return None

        return {
            "source_line": runtime_context.source_line,
            "source_file": runtime_context.source_file,
            "checkpoint_position": runtime_context.checkpoint_position,
            "procedure_name": runtime_context.procedure_name,
            "invocation_id": runtime_context.invocation_id,
            "started_at": (
                runtime_context.started_at.isoformat() if runtime_context.started_at else None
            ),
            "elapsed_seconds": runtime_context.elapsed_seconds,
            "backtrace": (
                [
                    {
                        "checkpoint_type": bt.checkpoint_type,
                        "line": bt.line,
                        "function_name": bt.function_name,
                        "duration_ms": bt.duration_ms,
                    }
                    for bt in runtime_context.backtrace
                ]
                if runtime_context.backtrace
                else []
            ),
        }

    def handle_ide_response(self, request_id: str, value: Any) -> None:
        """
        Handle response from IDE (called by Flask POST endpoint).

        Bridges sync Flask handler to async channel protocol by pushing
        to the internal response queue.

        Args:
            request_id: The request being responded to
            value: The response value from the IDE
        """
        logger.info("%s: received response for %s", self.channel_id, request_id)

        response = ControlResponse(
            request_id=request_id,
            value=value,
            responded_at=datetime.now(timezone.utc),
            timed_out=False,
            channel_id=self.channel_id,
        )

        # Push to queue from sync context (Flask thread)
        # Get the running event loop and schedule the put operation
        try:
            event_loop = asyncio.get_event_loop()
            if event_loop.is_running():
                # Schedule the coroutine in the running loop
                asyncio.run_coroutine_threadsafe(self._response_queue.put(response), event_loop)
            else:
                # If no loop is running, use put_nowait (shouldn't happen)
                self._response_queue.put_nowait(response)
        except Exception as error:
            logger.error(
                "%s: failed to queue response for %s: %s",
                self.channel_id,
                request_id,
                error,
            )

    def get_next_event(self, timeout: float = 0.001) -> Optional[dict]:
        """
        Get next SSE event from queue (for external consumption).

        Used when no event_emitter is provided - allows Flask endpoint
        to consume events from this channel.

        Args:
            timeout: Timeout in seconds

        Returns:
            Event dict or None if queue is empty
        """
        try:
            event_payload = self._event_queue.get(timeout=timeout)
            return event_payload
        except queue.Empty:
            return None

    async def cancel(self, external_message_id: str, reason: str) -> None:
        """
        Cancel/dismiss HITL request in IDE.

        Sends a hitl.cancel event to dismiss the prompt.
        """
        logger.debug(
            "%s: cancelling %s: %s",
            self.channel_id,
            external_message_id,
            reason,
        )

        cancel_event = {
            "event_type": "hitl.cancel",  # Frontend expects event_type, not type
            "request_id": external_message_id,
            "reason": reason,
        }

        if self._event_emitter:
            await self._event_emitter(cancel_event)
        else:
            self._event_queue.put(cancel_event)

    async def shutdown(self) -> None:
        """Shutdown SSE channel."""
        logger.info("%s: shutting down", self.channel_id)
        self._shutdown_event.set()
