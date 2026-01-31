"""
Control loop handler for omnichannel controller interactions.

Sends control requests to all enabled channels simultaneously and waits
for the first response. First response wins - other channels are cancelled.

Supports both human-in-the-loop (HITL) and model-in-the-loop (MITL) controllers.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from tactus.core.exceptions import ProcedureWaitingForHuman
from tactus.protocols.control import (
    ControlChannel,
    ControlRequest,
    ControlResponse,
    ControlRequestType,
    ControlOption,
    DeliveryResult,
    RuntimeContext,
    BacktraceEntry,
    ContextLink,
)
from tactus.protocols.storage import StorageBackend

logger = logging.getLogger(__name__)


class ControlLoopHandler:
    """
    Sends control requests to all enabled channels simultaneously.
    First response wins, others get cancelled.

    Controllers can be humans (HITL) or models (MITL).

    Architecture:
    1. Send to ALL enabled channels simultaneously
    2. Wait for first response from ANY channel
    3. Cancel other channels when one responds
    4. No special priority for any channel type

    For channels like CLI that can respond immediately, this returns quickly.
    For async-only scenarios (e.g., only remote channels), this raises
    ProcedureWaitingForHuman to trigger exit-and-resume pattern.

    Example:
        channels = [
            CLIControlChannel(),
            SSEControlChannel(sse_manager),
            TactusCloudChannel(api_url="wss://..."),
        ]
        handler = ControlLoopHandler(channels=channels, storage=storage_backend)
        runtime = TactusRuntime(control_handler=handler, ...)
    """

    # Storage key prefix for pending requests
    PENDING_KEY_PREFIX = "control_pending:"

    def __init__(
        self,
        channels: list[ControlChannel],
        storage: Optional[StorageBackend] = None,
        immediate_response_timeout: float = 0.5,
        execution_context=None,
    ):
        """
        Initialize control loop handler.

        Args:
            channels: List of enabled control channels
            storage: Storage backend for persisting pending requests (optional for sync-only)
            immediate_response_timeout: How long to wait for immediate responses (default 0.5s)
            execution_context: Optional execution context for deterministic request IDs
        """
        self.channels = channels
        self.storage = storage
        self.immediate_response_timeout = immediate_response_timeout
        self.execution_context = execution_context
        self._channels_initialized = False

        channel_ids = [c.channel_id for c in channels]
        logger.info(
            "ControlLoopHandler initialized with %s channels: %s",
            len(channels),
            channel_ids,
        )

    async def initialize_channels(self) -> None:
        """
        Initialize all channels.

        Called at procedure start for eager initialization.
        Initializes channels concurrently.
        """
        if self._channels_initialized:
            return

        if not self.channels:
            return

        initialize_tasks = [channel.initialize() for channel in self.channels]
        await asyncio.gather(*initialize_tasks, return_exceptions=True)
        self._channels_initialized = True

    async def shutdown_channels(self) -> None:
        """
        Shutdown all channels.

        Called at procedure end for cleanup.
        """
        if not self.channels:
            return

        shutdown_tasks = [channel.shutdown() for channel in self.channels]
        await asyncio.gather(*shutdown_tasks, return_exceptions=True)

    def request_interaction(
        self,
        procedure_id: str,
        request_type: str,
        message: str,
        options: Optional[list[dict[str, Any]]] = None,
        timeout_seconds: Optional[int] = None,
        default_value: Any = None,
        metadata: Optional[dict[str, Any]] = None,
        # Rich context
        procedure_name: str = "Unknown Procedure",
        invocation_id: Optional[str] = None,
        namespace: str = "",
        subject: Optional[str] = None,
        started_at: Optional[datetime] = None,
        input_summary: Optional[dict[str, Any]] = None,
        conversation: Optional[list[dict[str, Any]]] = None,
        prior_interactions: Optional[list[dict[str, Any]]] = None,
        # New context architecture
        runtime_context: Optional[dict[str, Any]] = None,
        application_context: Optional[list[dict[str, Any]]] = None,
    ) -> ControlResponse:
        """
        Request controller interaction by sending to all channels.

        This is the main entry point for control loop interactions.
        Sends to all enabled channels concurrently, waits for first response.

        For synchronous channels (like CLI), this may return immediately.
        For async-only scenarios, raises ProcedureWaitingForHuman.

        Args:
            procedure_id: Unique procedure identifier
            request_type: Type of interaction: 'approval', 'input', 'review', 'escalation'
            message: Message to display to the controller
            options: Options for the controller to choose from
            timeout_seconds: Timeout in seconds (None = wait forever)
            default_value: Default value on timeout
            metadata: Additional context and metadata
            procedure_name: Human-readable procedure name
            invocation_id: Unique invocation identifier
            namespace: Namespace for routing/authorization
            subject: Human-readable subject identifier
            started_at: When the invocation started
            input_summary: Summary of key input fields
            conversation: Full conversation history
            prior_interactions: Previous control interactions

        Returns:
            ControlResponse with controller's answer

        Raises:
            ProcedureWaitingForHuman: To trigger exit-and-resume for async channels
        """
        # Build control request
        request = self._build_request(
            procedure_id=procedure_id,
            request_type=request_type,
            message=message,
            options=options,
            timeout_seconds=timeout_seconds,
            default_value=default_value,
            metadata=metadata,
            procedure_name=procedure_name,
            invocation_id=invocation_id,
            namespace=namespace,
            subject=subject,
            started_at=started_at,
            input_summary=input_summary,
            conversation=conversation,
            prior_interactions=prior_interactions,
            runtime_context=runtime_context,
            application_context=application_context,
        )

        logger.info(
            "Control request %s for procedure %s: %s - %s...",
            request.request_id,
            procedure_id,
            request_type,
            message[:50],
        )

        # Run the async request flow
        # Check if we're already in an async context
        try:
            event_loop = asyncio.get_running_loop()
            if event_loop.is_closed():
                raise RuntimeError("Running event loop is closed")

            # Already in async context - create task and run it
            # This shouldn't normally happen since request_interaction is sync
            import nest_asyncio

            nest_asyncio.apply()
            return event_loop.run_until_complete(self._request_interaction_async(request))
        except RuntimeError:
            # Not in async context - create a temporary event loop.
            previous_event_loop: asyncio.AbstractEventLoop | None = None
            try:
                previous_event_loop = asyncio.get_event_loop()
            except RuntimeError:
                previous_event_loop = None
            else:
                if getattr(previous_event_loop, "is_closed", lambda: False)():
                    previous_event_loop = None

            event_loop = asyncio.new_event_loop()
            try:
                asyncio.set_event_loop(event_loop)
                return event_loop.run_until_complete(self._request_interaction_async(request))
            finally:
                event_loop.close()
                asyncio.set_event_loop(previous_event_loop)

    async def _request_interaction_async(self, request: ControlRequest) -> ControlResponse:
        """
        Async implementation of request_interaction.

        Sends to all channels, waits for first response.
        """
        # RESUME FLOW: Check if we already have a cached response from previous run
        if self.storage:
            cached_response = self.check_pending_response(request.procedure_id, request.request_id)
            if cached_response:
                logger.info("RESUME: Using cached response for %s", request.request_id)
                return cached_response

        # Initialize channels on first use
        await self.initialize_channels()

        if not self.channels:
            raise RuntimeError("No control channels available")

        # Filter channels that support this request type
        eligible_channels = self._get_eligible_channels(request)
        if not eligible_channels:
            raise RuntimeError(
                f"No channels support {request.request_type} requests. "
                f"Available channels: {[c.channel_id for c in self.channels]}"
            )

        # Send to all eligible channels concurrently
        deliveries = await self._fanout(request, eligible_channels)

        # Log delivery results
        successful = [delivery for delivery in deliveries if delivery.success]
        failed = [delivery for delivery in deliveries if not delivery.success]
        logger.info(
            "Control request %s: %s successful deliveries, %s failed",
            request.request_id,
            len(successful),
            len(failed),
        )
        for delivery in failed:
            logger.warning(
                "  Failed delivery to %s: %s",
                delivery.channel_id,
                delivery.error_message,
            )

        if not successful:
            raise RuntimeError("All channel deliveries failed")

        # Wait for responses from ALL eligible channels, even if delivery failed
        # (e.g., IPC channel with no clients can still get responses when clients connect)
        active_channels = eligible_channels

        # Wait for first response from any channel
        response = await self._wait_for_first_response(request, active_channels, deliveries)

        if response:
            # Store response for future resume
            if self.storage:
                self._store_response(request, response)
                logger.info(
                    "Stored response for %s (enables resume)",
                    request.request_id,
                )

            # Cancel all other channels
            await self._cancel_other_channels(
                request,
                deliveries,
                winning_channel=response.channel_id,
            )
            return response

        # No immediate response - save state and raise for exit-and-resume
        if self.storage:
            self._store_pending(request, deliveries)

        raise ProcedureWaitingForHuman(request.procedure_id, request.request_id)

    async def _fanout(
        self,
        request: ControlRequest,
        channels: list[ControlChannel],
    ) -> list[DeliveryResult]:
        """
        Send request to all channels concurrently.

        Args:
            request: The control request
            channels: Channels to send to

        Returns:
            List of delivery results
        """
        send_tasks = [self._send_with_error_handling(channel, request) for channel in channels]
        results = await asyncio.gather(*send_tasks)
        return list(results)

    async def _send_with_error_handling(
        self,
        channel: ControlChannel,
        request: ControlRequest,
    ) -> DeliveryResult:
        """
        Send with error handling - returns failed result instead of raising.
        """
        try:
            return await channel.send(request)
        except Exception as error:
            logger.exception("Failed to send to %s", channel.channel_id)
            return DeliveryResult(
                channel_id=channel.channel_id,
                external_message_id="",
                delivered_at=datetime.now(timezone.utc),
                success=False,
                error_message=str(error),
            )

    async def _wait_for_first_response(
        self,
        request: ControlRequest,
        channels: list[ControlChannel],
        deliveries: list[DeliveryResult],
    ) -> Optional[ControlResponse]:
        """
        Wait for first response from any channel.

        For synchronous channels (like CLI), this may return quickly.
        For async-only scenarios, returns None after timeout.

        Args:
            request: The control request
            channels: Active channels to listen to
            deliveries: Delivery results for building response

        Returns:
            ControlResponse if received, None otherwise
        """
        # Check if any channel is synchronous (can respond immediately)
        has_sync_channel = any(c.capabilities.is_synchronous for c in channels)

        # Use longer timeout if we have sync channels
        timeout = self.immediate_response_timeout if not has_sync_channel else 30.0

        # Create tasks for each channel's receive iterator
        receive_tasks: list[tuple[ControlChannel, asyncio.Task[Optional[ControlResponse]]]] = []
        for channel in channels:
            task = asyncio.create_task(
                self._get_first_from_channel(channel),
                name=f"receive_{channel.channel_id}",
            )
            receive_tasks.append((channel, task))

        try:
            # Wait for first completion
            done, pending = await asyncio.wait(
                [t for _, t in receive_tasks],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            # Return first successful response
            for task in done:
                try:
                    response = task.result()
                    if response:
                        return response
                except asyncio.CancelledError:
                    pass
                except Exception as error:
                    logger.debug("Task exception: %s", error)

            return None

        except asyncio.TimeoutError:
            # Cancel all tasks
            for _, task in receive_tasks:
                task.cancel()
            return None

    async def _get_first_from_channel(self, channel: ControlChannel) -> Optional[ControlResponse]:
        """Get first response from a channel's receive iterator."""
        try:
            async for response in channel.receive():
                logger.info(
                    "Received response from %s: %s",
                    channel.channel_id,
                    response.request_id,
                )
                return response
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.debug("Error receiving from %s: %s", channel.channel_id, error)
            return None
        return None

    async def _cancel_other_channels(
        self,
        request: ControlRequest,
        deliveries: list[DeliveryResult],
        winning_channel: Optional[str],
    ) -> None:
        """
        Cancel all channels except the one that responded.

        Args:
            request: The control request
            deliveries: Delivery results with external message IDs
            winning_channel: Channel that provided the response
        """
        reason = f"Responded via {winning_channel}" if winning_channel else "Request cancelled"

        tasks = []
        for delivery in deliveries:
            if delivery.success and delivery.channel_id != winning_channel:
                channel = self._get_channel_by_id(delivery.channel_id)
                if channel:
                    tasks.append(
                        self._cancel_with_error_handling(
                            channel,
                            delivery.external_message_id,
                            reason,
                        )
                    )

        if tasks:
            await asyncio.gather(*tasks)

    async def _cancel_with_error_handling(
        self,
        channel: ControlChannel,
        external_message_id: str,
        reason: str,
    ) -> None:
        """Cancel with error handling to prevent one failure from affecting others."""
        try:
            await channel.cancel(external_message_id, reason)
        except Exception:
            logger.exception("Failed to cancel on %s", channel.channel_id)

    def _get_eligible_channels(self, request: ControlRequest) -> list[ControlChannel]:
        """Get channels that support the given request type."""
        eligible: list[ControlChannel] = []
        for channel in self.channels:
            if self._channel_supports_request(channel, request):
                eligible.append(channel)
        return eligible

    def _channel_supports_request(
        self,
        channel: ControlChannel,
        request: ControlRequest,
    ) -> bool:
        """Check if a channel supports the given request type."""
        caps = channel.capabilities
        request_type = request.request_type

        if request_type == ControlRequestType.APPROVAL:
            return caps.supports_approval
        elif request_type == ControlRequestType.INPUT:
            return caps.supports_input
        elif request_type == ControlRequestType.REVIEW:
            return caps.supports_review
        elif request_type == ControlRequestType.ESCALATION:
            return caps.supports_escalation
        else:
            return True

    def _get_channel_by_id(self, channel_id: str) -> Optional[ControlChannel]:
        """Get channel by its ID."""
        for channel in self.channels:
            if channel.channel_id == channel_id:
                return channel
        return None

    def _build_request(
        self,
        procedure_id: str,
        request_type: str,
        message: str,
        options: Optional[list[dict[str, Any]]] = None,
        timeout_seconds: Optional[int] = None,
        default_value: Any = None,
        metadata: Optional[dict[str, Any]] = None,
        procedure_name: str = "Unknown Procedure",
        invocation_id: Optional[str] = None,
        namespace: str = "",
        subject: Optional[str] = None,
        started_at: Optional[datetime] = None,
        input_summary: Optional[dict[str, Any]] = None,
        conversation: Optional[list[dict[str, Any]]] = None,
        prior_interactions: Optional[list[dict[str, Any]]] = None,
        runtime_context: Optional[dict[str, Any]] = None,
        application_context: Optional[list[dict[str, Any]]] = None,
    ) -> ControlRequest:
        """Build a ControlRequest from the provided parameters."""
        # CRITICAL: Generate deterministic request_id based on checkpoint position AND run_id
        # Including run_id ensures different runs don't collide in the response cache
        # This allows resume flow to find cached responses within the same run, but not across runs
        checkpoint_position = None
        if self.execution_context and hasattr(self.execution_context, "next_position"):
            checkpoint_position = self.execution_context.next_position()

        # Get run_id from execution context to ensure cache isolation between runs
        run_id_prefix = "unknown"
        if self.execution_context and hasattr(self.execution_context, "current_run_id"):
            if self.execution_context.current_run_id:
                # Use first 8 chars of run_id for brevity
                run_id_prefix = self.execution_context.current_run_id[:8]

        if checkpoint_position is not None:
            # Deterministic ID: procedure_id:run_id:position
            request_id = f"{procedure_id}:{run_id_prefix}:pos{checkpoint_position}"
        else:
            # Fallback to random ID (backward compatibility for contexts without position tracking)
            request_id = f"{procedure_id}:{run_id_prefix}:{uuid.uuid4().hex[:12]}"

        # Convert options to ControlOption objects
        control_options: list[ControlOption] = []
        if options:
            for opt in options:
                control_options.append(
                    ControlOption(
                        label=opt.get("label", ""),
                        value=opt.get("value", opt.get("label", "")),
                        style=opt.get("style", "default"),
                        description=opt.get("description"),
                    )
                )

        # Extract items from metadata if this is an 'inputs' request
        items = []
        if request_type == "inputs":
            logger.debug(
                "Processing inputs request, metadata type: %s, value: %s",
                type(metadata),
                metadata,
            )
            if metadata and isinstance(metadata, dict) and "items" in metadata:
                from tactus.protocols.control import ControlRequestItem

                item_entries = metadata.get("items", [])
                logger.debug("Found %s items in metadata", len(item_entries))
                for item_dict in item_entries:
                    # Convert dict to ControlRequestItem
                    items.append(ControlRequestItem(**item_dict))

        # Convert runtime_context dict to RuntimeContext object
        runtime_ctx_obj = None
        if runtime_context:
            # Convert backtrace entries
            backtrace_entries = []
            for bt in runtime_context.get("backtrace", []):
                backtrace_entries.append(
                    BacktraceEntry(
                        checkpoint_type=bt.get("checkpoint_type", "unknown"),
                        line=bt.get("line"),
                        function_name=bt.get("function_name"),
                        duration_ms=bt.get("duration_ms"),
                    )
                )

            # Parse started_at if it's a string
            started_at_dt = None
            if runtime_context.get("started_at"):
                started_at_str = runtime_context["started_at"]
                if isinstance(started_at_str, str):
                    from dateutil.parser import parse

                    started_at_dt = parse(started_at_str)
                else:
                    started_at_dt = started_at_str

            runtime_ctx_obj = RuntimeContext(
                source_line=runtime_context.get("source_line"),
                source_file=runtime_context.get("source_file"),
                checkpoint_position=runtime_context.get("checkpoint_position", 0),
                procedure_name=runtime_context.get("procedure_name", ""),
                invocation_id=runtime_context.get("invocation_id", ""),
                started_at=started_at_dt,
                elapsed_seconds=runtime_context.get("elapsed_seconds", 0.0),
                backtrace=backtrace_entries,
            )

        # Convert application_context dicts to ContextLink objects
        app_ctx_objs: list[ContextLink] = []
        if application_context:
            for link in application_context:
                app_ctx_objs.append(
                    ContextLink(
                        name=link.get("name", ""),
                        value=link.get("value", ""),
                        url=link.get("url"),
                    )
                )

        return ControlRequest(
            request_id=request_id,
            procedure_id=procedure_id,
            procedure_name=procedure_name,
            invocation_id=invocation_id or procedure_id,
            namespace=namespace,
            subject=subject,
            started_at=started_at or datetime.now(timezone.utc),
            elapsed_seconds=(
                int(
                    (
                        datetime.now(timezone.utc) - (started_at or datetime.now(timezone.utc))
                    ).total_seconds()
                )
                if started_at
                else 0
            ),
            request_type=ControlRequestType(request_type),
            message=message,
            options=control_options,
            timeout_seconds=timeout_seconds,
            default_value=default_value,
            items=items,
            input_summary=input_summary or {},
            conversation=[],  # TODO: Convert conversation dicts
            prior_interactions=[],  # TODO: Convert prior_interactions dicts
            runtime_context=runtime_ctx_obj,
            application_context=app_ctx_objs,
            metadata=metadata or {},
        )

    def _store_pending(self, request: ControlRequest, deliveries: list[DeliveryResult]) -> None:
        """Store pending request in storage backend."""
        if not self.storage:
            return

        key = f"{self.PENDING_KEY_PREFIX}{request.request_id}"
        state = self.storage.get_state(request.procedure_id) or {}
        state[key] = {
            "request": request.model_dump(mode="json"),
            "deliveries": [d.model_dump(mode="json") for d in deliveries],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.storage.set_state(request.procedure_id, state)

    def _store_response(self, request: ControlRequest, response: ControlResponse) -> None:
        """Store response to a pending request (enables resume)."""
        if not self.storage:
            return

        key = f"{self.PENDING_KEY_PREFIX}{request.request_id}"
        state = self.storage.get_state(request.procedure_id) or {}

        # Add response to existing pending request (if it exists) or create new entry
        if key in state:
            state[key]["response"] = response.model_dump(mode="json")
            state[key]["responded_at"] = datetime.now(timezone.utc).isoformat()
        else:
            # Request wasn't pending (immediate response), still store for resume
            state[key] = {
                "request": request.model_dump(mode="json"),
                "response": response.model_dump(mode="json"),
                "responded_at": datetime.now(timezone.utc).isoformat(),
            }

        self.storage.set_state(request.procedure_id, state)

    def check_pending_response(
        self,
        procedure_id: str,
        request_id: str,
    ) -> Optional[ControlResponse]:
        """
        Check if there's a response to a pending control request.

        Used during resume flow to check if controller has responded.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Request ID (message_id in this context)

        Returns:
            ControlResponse if response exists, None otherwise
        """
        if not self.storage:
            return None

        key = f"{self.PENDING_KEY_PREFIX}{request_id}"
        state = self.storage.get_state(procedure_id) or {}

        if key in state:
            pending = state[key]
            if pending.get("response"):
                logger.info("Found response for request %s", request_id)
                return ControlResponse.model_validate(pending["response"])

        return None

    def cancel_pending_request(self, procedure_id: str, request_id: str) -> None:
        """
        Cancel a pending control request.

        Args:
            procedure_id: Unique procedure identifier
            request_id: Request ID to cancel
        """
        if not self.storage:
            return

        key = f"{self.PENDING_KEY_PREFIX}{request_id}"
        state = self.storage.get_state(procedure_id) or {}

        if key in state:
            del state[key]
            self.storage.set_state(procedure_id, state)
            logger.info("Cancelled control request %s", request_id)


class ControlLoopHITLAdapter:
    """
    Adapter that makes ControlLoopHandler compatible with the HITLHandler protocol.

    This allows the new ControlLoopHandler to work with existing runtime code
    that expects the old HITLHandler interface (request: HITLRequest parameter).

    The adapter converts between HITLRequest/HITLResponse and the expanded
    parameter format that ControlLoopHandler uses.
    """

    def __init__(self, control_handler: ControlLoopHandler, execution_context=None):
        """
        Initialize adapter.

        Args:
            control_handler: The ControlLoopHandler to wrap
            execution_context: ExecutionContext for gathering rich metadata
        """
        self.control_handler = control_handler
        self.execution_context = execution_context

    def request_interaction(self, procedure_id: str, request, execution_context=None):
        """
        Request interaction using HITLRequest format.

        Converts HITLRequest to ControlLoopHandler's expanded parameters.

        Args:
            procedure_id: Procedure identifier
            request: HITLRequest (old format) or dict with request details
            execution_context: Optional execution context for rich metadata

        Returns:
            HITLResponse (converted from ControlResponse)

        Raises:
            ProcedureWaitingForHuman: To trigger exit-and-resume
        """
        from tactus.protocols.models import HITLResponse

        # Extract request fields (handle both HITLRequest objects and dicts)
        if hasattr(request, "request_type"):
            request_type = request.request_type
            message = request.message
            options = request.options
            timeout_seconds = request.timeout_seconds
            default_value = request.default_value
            metadata = request.metadata or {}
        else:
            request_type = request.get("request_type")
            message = request.get("message")
            options = request.get("options")
            timeout_seconds = request.get("timeout_seconds")
            default_value = request.get("default_value")
            metadata = request.get("metadata", {})

        # Use provided execution_context or fall back to instance one
        execution_context_to_use = execution_context or self.execution_context

        # CRITICAL: Pass execution_context to control_handler for deterministic request IDs
        # This allows _build_request to use next_position() for stable request_id generation
        previous_execution_context = self.control_handler.execution_context
        if execution_context_to_use:
            self.control_handler.execution_context = execution_context_to_use

        # Gather rich context from execution context if available
        procedure_name = "Unknown Procedure"
        invocation_id = None
        subject = None
        started_at = None
        input_summary = None
        conversation = None
        prior_interactions = None

        if execution_context_to_use:
            procedure_name = getattr(execution_context_to_use, "procedure_name", procedure_name)
            invocation_id = getattr(execution_context_to_use, "invocation_id", invocation_id)

            # Try to get additional context if methods exist
            if hasattr(execution_context_to_use, "get_subject"):
                subject = execution_context_to_use.get_subject()
            if hasattr(execution_context_to_use, "get_started_at"):
                started_at = execution_context_to_use.get_started_at()
            if hasattr(execution_context_to_use, "get_input_summary"):
                input_summary = execution_context_to_use.get_input_summary()
            if hasattr(execution_context_to_use, "get_conversation_history"):
                conversation = execution_context_to_use.get_conversation_history()
            if hasattr(execution_context_to_use, "get_prior_control_interactions"):
                prior_interactions = execution_context_to_use.get_prior_control_interactions()

        # Get runtime context for HITL display (new context architecture)
        runtime_context = None
        if execution_context_to_use and hasattr(execution_context_to_use, "get_runtime_context"):
            runtime_context = execution_context_to_use.get_runtime_context()

        # Application context would be passed from the host application
        # For now, we don't have a way to pass it through, but the protocol supports it
        application_context = None

        try:
            # Call ControlLoopHandler with expanded parameters
            control_response = self.control_handler.request_interaction(
                procedure_id=procedure_id,
                request_type=request_type,
                message=message,
                options=options,
                timeout_seconds=timeout_seconds,
                default_value=default_value,
                metadata=metadata,
                # Rich context
                procedure_name=procedure_name,
                invocation_id=invocation_id,
                namespace=metadata.get("namespace", ""),
                subject=subject,
                started_at=started_at,
                input_summary=input_summary,
                conversation=conversation,
                prior_interactions=prior_interactions,
                # New context architecture
                runtime_context=runtime_context,
                application_context=application_context,
            )

            # Convert ControlResponse to HITLResponse
            return HITLResponse(
                value=control_response.value,
                responded_at=control_response.responded_at,
                timed_out=control_response.timed_out,
                responder_id=control_response.responder_id,
                channel=control_response.channel_id,
            )
        finally:
            # Restore original execution context
            if execution_context_to_use:
                self.control_handler.execution_context = previous_execution_context

    def check_pending_response(self, procedure_id: str, request_id: str):
        """
        Check for pending response.

        Delegates to ControlLoopHandler and converts response format.
        """
        from tactus.protocols.models import HITLResponse

        control_response = self.control_handler.check_pending_response(procedure_id, request_id)
        if control_response is None:
            return None

        return HITLResponse(
            value=control_response.value,
            responded_at=control_response.responded_at,
            timed_out=control_response.timed_out,
            responder_id=control_response.responder_id,
            channel=control_response.channel_id,
        )

    def cancel_pending_request(self, procedure_id: str, request_id: str) -> None:
        """Cancel pending request - delegates to ControlLoopHandler."""
        self.control_handler.cancel_pending_request(procedure_id, request_id)
