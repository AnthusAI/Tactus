"""
IPC Control Channel - Unix socket communication for control loop.

This channel allows external control CLI apps to connect and respond to
control requests via Unix domain sockets using the broker protocol.
"""

import asyncio
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from tactus.broker.protocol import read_message, write_message
from tactus.protocols.control import (
    ControlRequest,
    ControlResponse,
    ChannelCapabilities,
    DeliveryResult,
)

logger = logging.getLogger(__name__)


class IPCControlChannel:
    """
    Control channel using Unix socket IPC with broker protocol.

    The runtime creates a Unix socket server that control CLI clients can
    connect to. Control requests are broadcast to all connected clients,
    and the first response wins (standard racing pattern).
    """

    def __init__(self, socket_path: Optional[str] = None, procedure_id: Optional[str] = None):
        """
        Initialize IPC control channel.

        Args:
            socket_path: Path to Unix socket (default: /tmp/tactus-control-{procedure_id}.sock)
            procedure_id: Procedure ID for default socket path
        """
        self.procedure_id = procedure_id or "default"
        self.socket_path = socket_path or f"/tmp/tactus-control-{self.procedure_id}.sock"
        self.channel_id = "ipc"

        self._server: Optional[asyncio.Server] = None
        self._clients: dict[str, asyncio.StreamWriter] = {}  # client_id -> writer
        self._response_queue: asyncio.Queue[ControlResponse] = asyncio.Queue()
        self._pending_requests: dict[str, ControlRequest] = {}  # request_id -> request
        self._initialized = False

    @property
    def capabilities(self) -> ChannelCapabilities:
        """IPC supports all request types and can respond synchronously."""
        return ChannelCapabilities(
            supports_approval=True,
            supports_input=True,
            supports_choice=True,
            supports_review=True,
            supports_escalation=True,
            is_synchronous=True,  # Humans respond in real-time via control CLI
        )

    async def initialize(self) -> None:
        """Start Unix socket server and accept connections."""
        if self._initialized:
            return

        logger.info("%s: initializing...", self.channel_id)

        # Remove old socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

        # Create parent directory if needed
        socket_dir = os.path.dirname(self.socket_path)
        os.makedirs(socket_dir, exist_ok=True)

        # Start Unix socket server
        self._server = await asyncio.start_unix_server(self._handle_client, path=self.socket_path)

        # Set socket permissions
        os.chmod(self.socket_path, 0o600)

        self._initialized = True
        logger.info(
            "%s: ready (listening on %s)",
            self.channel_id,
            self.socket_path,
        )

    async def send(self, request: ControlRequest) -> DeliveryResult:
        """
        Send control request to all connected clients.

        Args:
            request: ControlRequest object with all request details

        Returns:
            DeliveryResult with success/failure info
        """
        logger.info(
            "%s: sending notification for %s",
            self.channel_id,
            request.request_id,
        )

        # Create control request message from ControlRequest object
        request_payload = {
            "type": "control.request",
            "request_id": request.request_id,
            "procedure_id": request.procedure_id,
            "procedure_name": request.procedure_name,
            "invocation_id": request.invocation_id,
            "request_type": request.request_type,
            "message": request.message,
            "options": [{"label": opt.label, "value": opt.value} for opt in request.options],
            "default_value": request.default_value,
            "timeout_seconds": request.timeout_seconds,
            "metadata": request.metadata,
            "namespace": request.namespace,
            "subject": request.subject,
            "started_at": request.started_at.isoformat() if request.started_at else None,
            "input_summary": request.input_summary,
            "conversation": request.conversation,
            "prior_interactions": request.prior_interactions,
        }

        # Store pending request
        self._pending_requests[request.request_id] = request_payload

        # Send to all connected clients
        successful = 0
        failed = 0

        for client_id, writer in list(self._clients.items()):
            try:
                await write_message(writer, request_payload)
                successful += 1
            except Exception as error:
                logger.error(
                    "%s: failed to send to client %s: %s",
                    self.channel_id,
                    client_id,
                    error,
                )
                failed += 1
                # Remove dead client
                self._clients.pop(client_id, None)

        if successful == 0 and len(self._clients) == 0:
            logger.warning("%s: no clients connected", self.channel_id)

        # Return DeliveryResult
        return DeliveryResult(
            channel_id=self.channel_id,
            external_message_id=request.request_id,
            delivered_at=datetime.now(),
            success=successful > 0,
            error_message=None if successful > 0 else "No clients connected",
        )

    async def receive(self):
        """
        Yield responses from clients as they arrive.

        Yields:
            ControlResponse objects
        """
        while True:
            response = await self._response_queue.get()
            logger.info(
                "%s: received response for %s",
                self.channel_id,
                response.request_id,
            )
            yield response

    async def cancel(self, request_id: str, reason: str) -> None:
        """
        Cancel a pending request.

        Args:
            request_id: Request to cancel
            reason: Cancellation reason
        """
        logger.debug(
            "%s: cancelling %s (%s)",
            self.channel_id,
            request_id,
            reason,
        )

        # Remove from pending
        self._pending_requests.pop(request_id, None)

        # Send cancellation to all clients
        cancel_message = {"type": "control.cancelled", "request_id": request_id, "reason": reason}

        for client_id, writer in list(self._clients.items()):
            try:
                await write_message(writer, cancel_message)
            except Exception as error:
                logger.error(
                    "%s: failed to send cancellation to %s: %s",
                    self.channel_id,
                    client_id,
                    error,
                )

    async def shutdown(self) -> None:
        """Clean up and close server."""
        logger.info("%s: shutting down", self.channel_id)

        # Close all client connections
        for client_id, writer in list(self._clients.items()):
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as error:
                logger.error(
                    "%s: error closing client %s: %s",
                    self.channel_id,
                    client_id,
                    error,
                )

        self._clients.clear()

        # Close server
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Remove socket file
        if os.path.exists(self.socket_path):
            try:
                os.unlink(self.socket_path)
            except Exception as error:
                logger.error(
                    "%s: failed to remove socket file: %s",
                    self.channel_id,
                    error,
                )

        self._initialized = False

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """
        Handle a connected client.

        Args:
            reader: asyncio StreamReader
            writer: asyncio StreamWriter
        """
        client_id = str(uuid.uuid4())[:8]

        logger.info("%s: client connected (%s)", self.channel_id, client_id)

        # Register client
        self._clients[client_id] = writer

        try:
            # Send any pending requests to the new client
            for request_id, request_data in self._pending_requests.items():
                try:
                    await write_message(writer, request_data)
                except Exception as error:
                    logger.error(
                        "%s: failed to send pending request to %s: %s",
                        self.channel_id,
                        client_id,
                        error,
                    )

            # Read messages from client
            while True:
                try:
                    message = await read_message(reader)
                except asyncio.IncompleteReadError:
                    break
                except EOFError:
                    break

                # Handle message
                msg_type = message.get("type")

                if msg_type == "control.response":
                    # Parse response and queue it
                    response = ControlResponse(
                        request_id=message["request_id"],
                        value=message["value"],
                        responder_id=message.get("responder_id", client_id),
                        responded_at=(
                            datetime.fromisoformat(message["responded_at"])
                            if message.get("responded_at")
                            else datetime.now()
                        ),
                        timed_out=message.get("timed_out", False),
                        channel_id=self.channel_id,
                    )
                    await self._response_queue.put(response)
                    logger.info(
                        "%s: received response for %s",
                        self.channel_id,
                        response.request_id,
                    )

                    # Remove from pending
                    self._pending_requests.pop(response.request_id, None)

                elif msg_type == "control.list":
                    # Client requesting list of pending requests
                    list_response = {
                        "type": "control.list_response",
                        "requests": list(self._pending_requests.values()),
                    }
                    await write_message(writer, list_response)

                else:
                    logger.warning(
                        "%s: unknown message type from %s: %s",
                        self.channel_id,
                        client_id,
                        msg_type,
                    )

        except Exception as error:
            logger.error(
                "%s: error handling client %s: %s",
                self.channel_id,
                client_id,
                error,
            )

        finally:
            # Clean up
            self._clients.pop(client_id, None)
            logger.info("%s: client disconnected (%s)", self.channel_id, client_id)

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
