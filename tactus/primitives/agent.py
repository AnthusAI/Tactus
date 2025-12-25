"""
Agent Primitive - LLM agent with tool support using Pydantic AI.

Provides Agent.turn() for executing agent turns with LLM and tools.
"""

import logging
import asyncio
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.models import ModelMessage

from tactus.primitives.result import ResultPrimitive

logger = logging.getLogger(__name__)


@dataclass
class AgentDeps:
    """Dependencies available to the agent's system prompt."""

    state_primitive: Any  # StatePrimitive instance
    context: Dict[str, Any]  # Procedure context
    system_prompt_template: str  # Template string for system prompt
    output_schema_guidance: Optional[str] = None  # Optional output schema guidance


class AgentPrimitive:
    """
    Agent primitive for LLM interactions with tool support using Pydantic AI.

    Example usage (Lua):
        Greeter.turn()
        if Tool.called("done") then
            -- Agent called the done tool
        end
    """

    def __init__(
        self,
        name: str,
        system_prompt_template: str,
        initial_message: str,
        model: str,
        tools: List[Tool],
        tool_primitive: Any,
        stop_primitive: Any,
        iterations_primitive: Any,
        state_primitive: Any,
        context: Dict[str, Any],
        output_schema_guidance: Optional[str] = None,
        chat_recorder: Optional[Any] = None,
        result_type: Optional[type] = None,
        model_settings: Optional[Dict[str, Any]] = None,
        log_handler: Optional[Any] = None,
        procedure_id: Optional[str] = None,
        provider: Optional[str] = None,
        disable_streaming: bool = False,
        message_history_filter: Optional[Any] = None,
        toolsets: Optional[List] = None,
        user_dependencies: Optional[Dict[str, Any]] = None,
        deps_class: Optional[type] = None,
        execution_context: Optional[Any] = None,
    ):
        """
        Initialize agent primitive.

        Args:
            name: Agent name
            system_prompt_template: System prompt template (supports {state.*} and {context.*})
            initial_message: Initial message to start conversation
            model: Model string (e.g., 'openai:gpt-4o')
            tools: List of pydantic_ai.Tool instances
            tool_primitive: ToolPrimitive instance for tracking calls
            stop_primitive: StopPrimitive instance for stopping workflow
            iterations_primitive: IterationsPrimitive instance
            state_primitive: StatePrimitive instance for accessing state
            context: Procedure context dict
            output_schema_guidance: Optional output schema guidance text
            chat_recorder: Optional chat recorder
            result_type: Optional Pydantic model for structured output
            model_settings: Optional dict of model-specific settings (temperature, top_p, etc.)
            execution_context: Optional ExecutionContext for checkpointing
        """
        self.name = name
        self.system_prompt_template = system_prompt_template
        self.initial_message = initial_message
        self.model = model
        self.tool_primitive = tool_primitive
        self.stop_primitive = stop_primitive
        self.iterations_primitive = iterations_primitive
        self.state_primitive = state_primitive
        self.context = context
        self.output_schema_guidance = output_schema_guidance
        self.chat_recorder = chat_recorder
        self.result_type = result_type
        self.log_handler = log_handler
        self.procedure_id = procedure_id
        self.provider = provider
        self.model_settings = model_settings or {}
        self.disable_streaming = disable_streaming
        self.message_history_filter = message_history_filter
        self.user_dependencies = user_dependencies
        self.execution_context = execution_context

        # Create dependencies (with dynamic class if user dependencies exist)
        if deps_class:
            # Use provided deps class (already generated)
            from tactus.primitives.deps_generator import create_agent_deps_instance

            self.deps = create_agent_deps_instance(
                deps_class=deps_class,
                state_primitive=state_primitive,
                context=context,
                system_prompt_template=system_prompt_template,
                output_schema_guidance=output_schema_guidance,
                user_dependencies=user_dependencies,
            )
        elif user_dependencies:
            # Generate deps class dynamically
            from tactus.primitives.deps_generator import (
                generate_agent_deps_class,
                create_agent_deps_instance,
            )

            deps_class = generate_agent_deps_class(user_dependencies)
            self.deps = create_agent_deps_instance(
                deps_class=deps_class,
                state_primitive=state_primitive,
                context=context,
                system_prompt_template=system_prompt_template,
                output_schema_guidance=output_schema_guidance,
                user_dependencies=user_dependencies,
            )
        else:
            # No user dependencies - use base AgentDeps
            self.deps = AgentDeps(
                state_primitive=state_primitive,
                context=context,
                system_prompt_template=system_prompt_template,
                output_schema_guidance=output_schema_guidance,
            )

        # Create "done" tool if any tools are specified
        # For models without tool support, we don't add any tools (including done)
        if tools:

            async def done_tool(reason: str, success: bool = True) -> str:
                """Signal completion of the task."""
                if self.stop_primitive:
                    self.stop_primitive.request(reason if success else f"Failed: {reason}")
                if self.tool_primitive:
                    self.tool_primitive.record_call(
                        "done", {"reason": reason, "success": success}, "Done"
                    )
                return f"Done: {reason} (success: {success})"

            done_tool_instance = Tool(
                done_tool, name="done", description="Signal completion of the task"
            )

            # Combine all tools (MCP tools + done tool)
            all_tools = list(tools) + [done_tool_instance]
        else:
            # No tools for this agent (model doesn't support tool calling)
            all_tools = []

        # Store all tools for later reference (for per-turn filtering)
        self.all_tools = all_tools

        # Create Pydantic AI Agent with all tools
        # For Bedrock, we need to create a provider with region_name
        if provider and provider.lower() == "bedrock":
            import os
            from pydantic_ai.models.bedrock import BedrockConverseModel
            from pydantic_ai.providers.bedrock import BedrockProvider

            # Get region from environment (set by config loader)
            region_name = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

            # Extract model ID (remove provider prefix if present)
            model_id = model.split(":", 1)[1] if ":" in model else model

            logger.info(f"Creating Bedrock model '{model_id}' with region: {region_name}")
            bedrock_provider = BedrockProvider(region_name=region_name)
            bedrock_model = BedrockConverseModel(model_id, provider=bedrock_provider)

            # Pass tools/toolsets to Agent constructor
            # Empty lists are valid, but we only pass them if not empty
            # This avoids Bedrock rejecting requests for models that don't support tools
            agent_kwargs = {
                "deps_type": AgentDeps,
                "model_settings": model_settings,
            }
            if all_tools:
                agent_kwargs["tools"] = all_tools
                logger.info(f"Agent '{name}' passing {len(all_tools)} tools to Bedrock Agent")
            if toolsets and len(toolsets) > 0:  # Only pass if not empty
                agent_kwargs["toolsets"] = toolsets
                logger.info(f"Agent '{name}' passing {len(toolsets)} toolsets to Bedrock Agent")

            if not all_tools and (not toolsets or len(toolsets) == 0 or toolsets is None):
                logger.info(f"Agent '{name}' created with NO tools/toolsets for Bedrock")

            self.agent = Agent(bedrock_model, **agent_kwargs)
        else:
            # For OpenAI and other providers, use default behavior
            # Pydantic AI will use OPENAI_API_KEY from environment by default
            agent_kwargs = {
                "deps_type": AgentDeps,
                "model_settings": model_settings,
            }
            if all_tools:
                agent_kwargs["tools"] = all_tools
            if toolsets is not None:  # Check for None, not emptiness
                agent_kwargs["toolsets"] = toolsets

            self.agent = Agent(model, **agent_kwargs)

        # Add dynamic system prompt
        @self.agent.system_prompt
        def dynamic_system_prompt(ctx: RunContext[AgentDeps]) -> str:
            """Generate system prompt dynamically using current state and context."""
            deps = ctx.deps
            template = deps.system_prompt_template

            # Build template variables from state and context
            template_vars = {}
            if deps.state_primitive:
                template_vars["state"] = deps.state_primitive.all()
            if deps.context:
                template_vars.update(deps.context)

            # Format template with variables (supports dot notation like {state.key})
            from string import Formatter

            class DotFormatter(Formatter):
                def get_field(self, field_name, args, kwargs):
                    parts = field_name.split(".")
                    obj = kwargs
                    for part in parts:
                        if isinstance(obj, dict):
                            obj = obj.get(part, "")
                        else:
                            obj = getattr(obj, part, "")
                    return obj, field_name

            formatter = DotFormatter()
            try:
                prompt = formatter.format(template, **template_vars)
            except (KeyError, AttributeError) as e:
                logger.warning(
                    f"Template variable error in system prompt: {e}, using template as-is"
                )
                prompt = template

            # Append output schema guidance if provided
            if deps.output_schema_guidance:
                prompt = f"{prompt}\n\n{deps.output_schema_guidance}"

            return prompt

        # Conversation history
        self.message_history: List[ModelMessage] = []
        self._initialized = False

        logger.info(
            f"AgentPrimitive '{name}' initialized with {len(all_tools)} tools (including 'done')"
        )

    def turn(self, opts: Optional[Dict[str, Any]] = None) -> ResultPrimitive:
        """
        Execute one agent turn (synchronous wrapper for async Pydantic AI call).

        This method:
        1. Sends the current conversation to the LLM via Pydantic AI
        2. Handles tool calls automatically (Pydantic AI manages this)
        3. Records tool calls via tool_primitive
        4. Updates conversation history
        5. Returns a ResultPrimitive wrapping pydantic-ai's RunResult

        Args:
            opts: Optional dict with per-turn overrides:
                - inject: str - Message to inject for this turn
                - tools: List[str] - Tool names to use (None = use default, [] = no tools)
                - temperature: float - Override temperature for this turn
                - max_tokens: int - Override max_tokens for this turn
                - top_p: float - Override top_p for this turn

        Returns:
            ResultPrimitive with access to data, usage, and messages
        """
        logger.info(f"Agent '{self.name}' turn() called")

        # If execution_context is available, wrap with checkpoint
        if self.execution_context:
            return self.execution_context.checkpoint(lambda: self._execute_turn(opts), "agent_turn")
        else:
            return self._execute_turn(opts)

    def _execute_turn(self, opts: Optional[Dict[str, Any]] = None) -> ResultPrimitive:
        """Execute the agent turn logic (extracted for checkpointing)."""
        # Emit agent turn started event
        if self.log_handler:
            try:
                from tactus.protocols.models import AgentTurnEvent

                turn_event = AgentTurnEvent(
                    agent_name=self.name,
                    stage="started",
                    procedure_id=self.procedure_id,
                )
                self.log_handler.log(turn_event)
            except Exception as e:
                logger.warning(f"Failed to log agent turn started event: {e}")

        # Initialize conversation on first turn
        if not self._initialized:
            self._initialized = True

        # Increment iterations
        if self.iterations_primitive:
            self.iterations_primitive.increment()

        try:
            # Run the async turn method
            # Since we're in an async context (runtime.execute is async),
            # we need to handle this carefully.
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # We're in an async context - run in a thread with new event loop
                import threading
                import nest_asyncio

                # Try using nest_asyncio if available
                try:
                    nest_asyncio.apply(loop)
                    # Now we can use asyncio.run even in a running loop
                    return asyncio.run(self._turn_async(opts))
                except ImportError:
                    # nest_asyncio not available, fall back to threading
                    result_container = {"value": None, "exception": None}

                    def run_in_thread():
                        try:
                            # Create a new event loop for this thread
                            new_loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(new_loop)
                            try:
                                result_container["value"] = new_loop.run_until_complete(
                                    self._turn_async(opts)
                                )
                            finally:
                                new_loop.close()
                        except Exception as e:
                            result_container["exception"] = e

                    thread = threading.Thread(target=run_in_thread)
                    thread.start()
                    thread.join()

                    if result_container["exception"]:
                        raise result_container["exception"]
                    return result_container["value"]
            except RuntimeError:
                # No event loop running - safe to use asyncio.run()
                return asyncio.run(self._turn_async(opts))

        except Exception as e:
            logger.error(f"Agent '{self.name}' turn() failed: {e}", exc_info=True)
            raise

    def _get_tools_for_turn(self, opts: Optional[Dict[str, Any]]) -> Optional[List]:
        """
        Get tool list for this specific turn, respecting overrides.

        Args:
            opts: Optional dict with 'tools' key

        Returns:
            List of Tool instances to use for this turn, or None for default
        """
        if opts and "tools" in opts:
            tool_names = opts["tools"]
            if tool_names is None:
                # None means use default tools
                return None
            elif isinstance(tool_names, list):
                # Filter to requested tools
                return self._filter_tools_by_name(tool_names)

        # Default: use all configured tools (None = use agent's default)
        return None

    def _filter_tools_by_name(self, tool_names: List[str]) -> List:
        """
        Filter agent's tools to only those in tool_names list.

        Args:
            tool_names: List of tool names to include

        Returns:
            List of Tool instances matching the names
        """
        filtered = []

        for tool in self.all_tools:
            if tool.name in tool_names:
                filtered.append(tool)

        # Validate all requested tools exist
        found_names = {t.name for t in filtered}
        missing = set(tool_names) - found_names
        if missing:
            logger.warning(f"Agent '{self.name}': Requested tools not found: {missing}")

        return filtered

    def _get_user_input_for_turn(self, opts: Optional[Dict[str, Any]]) -> Optional[str]:
        """
        Get user input for this turn, respecting inject override.

        Args:
            opts: Optional dict with 'inject' key

        Returns:
            User input message for this turn
        """
        if opts and "inject" in opts:
            return opts["inject"]

        # Default behavior
        return self.initial_message if not self.message_history else None

    def _get_model_settings_for_turn(self, opts: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get model settings for this turn, merging in any overrides.

        Args:
            opts: Optional dict with model setting overrides

        Returns:
            Dict of model settings for this turn
        """
        # Start with default settings
        turn_model_settings = dict(self.model_settings)

        # Merge in any overrides
        if opts:
            for key in [
                "temperature",
                "max_tokens",
                "top_p",
                "presence_penalty",
                "frequency_penalty",
            ]:
                if key in opts:
                    turn_model_settings[key] = opts[key]

        return turn_model_settings

    async def _turn_async(self, opts: Optional[Dict[str, Any]] = None) -> ResultPrimitive:
        """
        Internal async method that performs the actual agent turn.

        Args:
            opts: Optional dict with per-turn overrides

        Returns:
            ResultPrimitive wrapping pydantic-ai's RunResult
        """
        import time

        # Track start time for duration measurement
        start_time = time.time()

        # Determine tools for this turn
        turn_tools = self._get_tools_for_turn(opts)

        # Determine input message for this turn
        user_input = self._get_user_input_for_turn(opts)
        if not user_input:
            # For subsequent turns, we need to continue the conversation
            # In Pydantic AI, we pass message_history to continue
            user_input = ""  # Empty input to continue conversation

        # Get model settings for this turn
        turn_model_settings = self._get_model_settings_for_turn(opts)

        # Check if we should use streaming (log handler present + no structured output + not disabled)
        # Streaming only works with text responses, not structured outputs
        # Some models don't support tools in streaming mode, so they can disable it
        # Works with both IDE and CLI log handlers
        should_stream = (
            self.log_handler is not None and self.result_type is None and not self.disable_streaming
        )
        logger.debug(
            f"Agent '{self.name}' streaming decision: should_stream={should_stream}, disable_streaming={self.disable_streaming}, log_handler={self.log_handler is not None}, result_type={self.result_type}"
        )

        if should_stream:
            # Streaming mode - works with both IDE and CLI
            result_primitive = await self._turn_async_streaming(
                start_time, user_input, turn_tools, turn_model_settings
            )
        else:
            # Non-streaming mode (structured output or streaming disabled)
            result_primitive = await self._turn_async_regular(
                start_time, user_input, turn_tools, turn_model_settings
            )

        return result_primitive

    async def _turn_async_regular(
        self,
        start_time: float,
        user_input: Optional[str],
        turn_tools: List,
        turn_model_settings: Dict[str, Any],
    ) -> ResultPrimitive:
        """
        Regular (non-streaming) agent turn for CLI mode.

        Args:
            start_time: Start time for duration measurement
            user_input: User input message
            turn_tools: List of tools to use for this turn
            turn_model_settings: Model settings to use for this turn

        Returns:
            ResultPrimitive wrapping pydantic-ai's RunResult
        """
        import time

        # Use context manager to override tools if specified
        if turn_tools is not None:
            logger.debug(
                f"Agent '{self.name}': Temporarily using {len(turn_tools)} tools for this turn"
            )
            agent_context = self.agent.override(tools=turn_tools)
        else:
            # No override - use a no-op context manager
            from contextlib import nullcontext

            agent_context = nullcontext()

        async with agent_context:
            # Run agent with dependencies and message history
            if self.message_history:
                # Apply filters to message history if configured
                filtered_history = self._apply_message_history_filter(self.message_history)

                # Continue existing conversation
                result = await self.agent.run(
                    user_input if user_input else "Continue",
                    deps=self.deps,
                    message_history=filtered_history,
                    output_type=self.result_type,
                    model_settings=turn_model_settings,
                )
            else:
                # First turn - start new conversation
                result = await self.agent.run(
                    self.initial_message or "Hello",
                    deps=self.deps,
                    output_type=self.result_type,
                    model_settings=turn_model_settings,
                )

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Update message history
        new_messages = result.new_messages()
        # Filter out any empty messages (workaround for pydantic-ai Bedrock bug)
        filtered_new_messages = [msg for msg in new_messages if self._message_has_content(msg)]
        self.message_history.extend(filtered_new_messages)

        # Record messages in chat recorder if available
        if self.chat_recorder:
            self._record_messages(filtered_new_messages)

        # Wrap result in ResultPrimitive for Lua access
        result_primitive = ResultPrimitive(result)

        # Extract all available tracing data
        tracing_data = result_primitive.extract_tracing_data()

        logger.info(f"Agent '{self.name}' turn completed in {duration_ms:.0f}ms")

        # Emit agent turn completed event BEFORE cost event
        if self.log_handler:
            try:
                from tactus.protocols.models import AgentTurnEvent

                turn_event = AgentTurnEvent(
                    agent_name=self.name,
                    stage="completed",
                    duration_ms=duration_ms,
                    procedure_id=self.procedure_id,
                )
                self.log_handler.log(turn_event)
            except Exception as e:
                logger.warning(f"Failed to log agent turn completed event: {e}")

        # Calculate and log comprehensive cost/metrics AFTER completion event
        if self.log_handler:
            self._log_cost_event(result_primitive, duration_ms, new_messages, tracing_data)

        return result_primitive

    async def _turn_async_streaming(
        self,
        start_time: float,
        user_input: Optional[str],
        turn_tools: List,
        turn_model_settings: Dict[str, Any],
    ) -> ResultPrimitive:
        """
        Streaming agent turn for IDE mode using event_stream_handler.

        This approach uses agent.run() with event_stream_handler instead of run_stream(),
        which allows us to stream text AND execute tool calls properly.

        Args:
            start_time: Start time for duration measurement
            user_input: User input message
            turn_tools: List of tools to use for this turn
            turn_model_settings: Model settings to use for this turn

        Returns:
            ResultPrimitive wrapping pydantic-ai's RunResult
        """
        import time
        from tactus.protocols.models import AgentStreamChunkEvent
        from pydantic_ai.messages import AgentStreamEvent, PartDeltaEvent, PartStartEvent
        from pydantic_ai.tools import RunContext
        from typing import AsyncIterable

        # Track accumulated text across the handler (will be stored in result for .text access)
        accumulated_text_container = {"text": ""}

        # Create event stream handler function
        async def stream_handler(
            ctx: RunContext[AgentDeps], events: AsyncIterable[AgentStreamEvent]
        ) -> None:
            """Handler function that processes streaming events."""
            from pydantic_ai.messages import FunctionToolCallEvent

            async for event in events:
                text_chunk = ""

                # Log tool calls for debugging
                if isinstance(event, FunctionToolCallEvent):
                    logger.info(f"Tool call event: {event.part.tool_name} (id: {event.call_id})")

                # Handle PartStartEvent - contains the first word/content
                if isinstance(event, PartStartEvent):
                    # PartStartEvent contains the initial part content
                    if hasattr(event.part, "content"):
                        text_chunk = event.part.content

                # Handle PartDeltaEvent - contains incremental text updates
                elif isinstance(event, PartDeltaEvent):
                    # PartDeltaEvent contains text deltas
                    if hasattr(event.delta, "content_delta"):
                        text_chunk = event.delta.content_delta
                    elif hasattr(event.delta, "content"):
                        text_chunk = event.delta.content

                # Emit chunk if we have text
                if text_chunk:
                    accumulated_text_container["text"] += text_chunk

                    try:
                        chunk_event = AgentStreamChunkEvent(
                            agent_name=self.name,
                            chunk_text=text_chunk,
                            accumulated_text=accumulated_text_container["text"],
                            procedure_id=self.procedure_id,
                        )
                        self.log_handler.log(chunk_event)
                    except Exception as e:
                        logger.warning(f"Failed to log stream chunk event: {e}")

        # Use context manager to override tools if specified
        if turn_tools is not None:
            logger.debug(
                f"Agent '{self.name}': Temporarily using {len(turn_tools)} tools for this turn"
            )
            agent_context = self.agent.override(tools=turn_tools)
        else:
            # No override - use a no-op context manager
            from contextlib import nullcontext

            agent_context = nullcontext()

        async with agent_context:
            # Run agent with event stream handler
            # Note: Passing event_stream_handler makes agent.run() use streaming internally
            if self.message_history:
                # Apply filters to message history if configured
                filtered_history = self._apply_message_history_filter(self.message_history)

                # Continue existing conversation
                result = await self.agent.run(
                    user_input if user_input else "Continue",
                    deps=self.deps,
                    message_history=filtered_history,
                    output_type=self.result_type,
                    event_stream_handler=stream_handler,
                    model_settings=turn_model_settings,
                )
            else:
                # First turn - start new conversation
                result = await self.agent.run(
                    self.initial_message or "Hello",
                    deps=self.deps,
                    output_type=self.result_type,
                    event_stream_handler=stream_handler,
                    model_settings=turn_model_settings,
                )

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Update message history
        new_messages = result.new_messages()
        # Filter out any empty messages (workaround for pydantic-ai Bedrock bug)
        filtered_new_messages = [msg for msg in new_messages if self._message_has_content(msg)]
        self.message_history.extend(filtered_new_messages)

        # Record messages in chat recorder if available
        if self.chat_recorder:
            self._record_messages(filtered_new_messages)

        # Wrap result in ResultPrimitive for Lua access
        result_primitive = ResultPrimitive(result)

        # Store the accumulated streamed text so it can be accessed via .text property
        result_primitive._streamed_text = accumulated_text_container["text"]

        # Extract all available tracing data
        tracing_data = result_primitive.extract_tracing_data()

        logger.info(f"Agent '{self.name}' turn completed in {duration_ms:.0f}ms")

        # Emit agent turn completed event BEFORE cost event
        if self.log_handler:
            try:
                from tactus.protocols.models import AgentTurnEvent

                turn_event = AgentTurnEvent(
                    agent_name=self.name,
                    stage="completed",
                    duration_ms=duration_ms,
                    procedure_id=self.procedure_id,
                )
                self.log_handler.log(turn_event)
            except Exception as e:
                logger.warning(f"Failed to log agent turn completed event: {e}")

        # Calculate and log comprehensive cost/metrics AFTER completion event
        if self.log_handler:
            self._log_cost_event(result_primitive, duration_ms, new_messages, tracing_data)

        return result_primitive

    def _log_cost_event(
        self,
        result_primitive: ResultPrimitive,
        duration_ms: float,
        new_messages: List[ModelMessage],
        tracing_data: Dict[str, Any],
    ):
        """
        Log comprehensive cost event with all available metrics.

        Args:
            result_primitive: ResultPrimitive with usage data
            duration_ms: Call duration in milliseconds
            new_messages: New messages from this turn
            tracing_data: Additional tracing data from RunResult
        """
        from tactus.utils.cost_calculator import CostCalculator
        from tactus.protocols.models import CostEvent

        try:
            # Calculate cost
            calculator = CostCalculator()
            usage = result_primitive.usage

            cost_info = calculator.calculate_cost(
                model_name=self.model,
                provider=self.provider,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cache_tokens=tracing_data.get("usage_cache_tokens"),
            )

            # Extract retry/validation info
            retry_count = tracing_data.get("retry_count", 0)
            validation_errors = tracing_data.get("validation_errors", [])
            if isinstance(validation_errors, str):
                validation_errors = [validation_errors]

            # Extract cache info
            cache_tokens = tracing_data.get("usage_cache_tokens") or tracing_data.get(
                "cache_tokens"
            )
            cache_hit = cache_tokens is not None and cache_tokens > 0

            # Convert response_data to plain dict for JSON serialization
            response_data = result_primitive.data
            if hasattr(response_data, "model_dump"):
                # It's a Pydantic model
                response_data = response_data.model_dump()
            elif hasattr(response_data, "__dict__"):
                # It's some other object
                response_data = dict(response_data.__dict__)
            elif isinstance(response_data, (dict, list)):
                # Already serializable
                pass
            elif isinstance(response_data, (str, int, float, bool)):
                # Primitive types - wrap in dict for consistent display
                response_data = {"value": response_data}
            elif response_data is None:
                response_data = None
            else:
                # Unknown type - convert to string
                response_data = {"value": str(response_data)}

            # Create comprehensive cost event
            cost_event = CostEvent(
                # Primary metrics
                agent_name=self.name,
                model=self.model,
                provider=cost_info["provider"],
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
                prompt_cost=cost_info["prompt_cost"],
                completion_cost=cost_info["completion_cost"],
                total_cost=cost_info["total_cost"],
                # Performance metrics
                duration_ms=duration_ms,
                latency_ms=tracing_data.get("latency_ms")
                or tracing_data.get("time_to_first_token"),
                # Retry metrics
                retry_count=retry_count,
                validation_errors=validation_errors,
                # Cache metrics
                cache_hit=cache_hit,
                cache_tokens=cache_tokens,
                cache_cost=cost_info.get("cache_cost"),
                # Message metrics
                message_count=len(result_primitive.all_messages()),
                new_message_count=len(new_messages),
                # Request metadata
                request_id=tracing_data.get("request_id"),
                model_version=tracing_data.get("model_version") or tracing_data.get("model_id"),
                temperature=self.model_settings.get("temperature"),
                max_tokens=self.model_settings.get("max_tokens"),
                procedure_id=self.procedure_id,
                # Raw tracing data
                raw_tracing_data=tracing_data,
                # Response data (converted to dict)
                response_data=response_data,
            )

            self.log_handler.log(cost_event)
            logger.info(
                f"💰 Agent '{self.name}' cost: ${cost_info['total_cost']:.6f} "
                f"({usage['total_tokens']} tokens, {duration_ms:.0f}ms)"
            )

        except Exception as e:
            logger.warning(f"Failed to log cost event: {e}", exc_info=True)

    def _record_messages(self, messages: List[ModelMessage]):
        """Record messages in chat recorder if available."""
        if not self.chat_recorder:
            return

        try:
            for message in messages:
                # Extract content and role from Pydantic AI message
                # ModelMessage structure varies, but typically has 'parts' or 'content'
                content = ""
                role = "assistant"

                if hasattr(message, "parts"):
                    # Multi-part message
                    for part in message.parts:
                        if hasattr(part, "text"):
                            content += part.text
                        elif hasattr(part, "content"):
                            content += str(part.content)
                elif hasattr(message, "content"):
                    content = str(message.content)
                elif hasattr(message, "text"):
                    content = message.text

                # Determine role
                if hasattr(message, "role"):
                    role = message.role
                elif hasattr(message, "source"):
                    role = message.source  # 'user' or 'assistant'

                # Record via chat recorder
                if hasattr(self.chat_recorder, "record_message") and content:
                    self.chat_recorder.record_message(
                        agent_name=self.name, role=role, content=content
                    )
        except Exception as e:
            logger.warning(f"Failed to record messages: {e}")

    async def flush_recordings(self):
        """Flush any queued chat recordings (async method)."""
        # This is a placeholder - actual implementation depends on chat_recorder
        pass

    def _message_has_content(self, msg: ModelMessage) -> bool:
        """
        Check if a message has non-empty content.

        This is a workaround for pydantic-ai Bedrock bug where tool response
        messages can have empty content arrays, causing ValidationException.

        Args:
            msg: Message to check

        Returns:
            True if message has content, False if empty
        """
        try:
            # Check if message has content attribute
            if hasattr(msg, "content"):
                content = msg.content
                # Check if content is a list/array
                if isinstance(content, (list, tuple)):
                    return len(content) > 0
                # Check if content is a string
                if isinstance(content, str):
                    return len(content.strip()) > 0
                # Other content types are considered non-empty
                return content is not None
            # No content attribute means it's probably empty
            return False
        except Exception:
            # If we can't determine, assume it has content
            return True

    def _apply_message_history_filter(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """
        Apply configured filter to message history.

        Args:
            messages: Full message history

        Returns:
            Filtered message history
        """
        if not self.message_history_filter:
            return messages

        # Filter is a tuple like ("last_n", 10) or ("compose", [filter1, filter2])
        if (
            not isinstance(self.message_history_filter, tuple)
            or len(self.message_history_filter) < 2
        ):
            logger.warning(f"Invalid filter format: {self.message_history_filter}")
            return messages

        filter_type = self.message_history_filter[0]
        filter_arg = self.message_history_filter[1]

        if filter_type == "last_n":
            # Keep only last N messages
            n = int(filter_arg)
            filtered = messages[-n:] if len(messages) > n else messages
            logger.debug(f"Applied last_n({n}) filter: {len(messages)} -> {len(filtered)} messages")
            return filtered

        elif filter_type == "by_role":
            # Keep only messages with specific role
            role = filter_arg
            filtered = [msg for msg in messages if getattr(msg, "role", None) == role]
            logger.debug(
                f"Applied by_role('{role}') filter: {len(messages)} -> {len(filtered)} messages"
            )
            return filtered

        elif filter_type == "token_budget":
            # Keep messages within token budget (simplified: just count messages)
            # TODO: Implement proper token counting
            max_tokens = int(filter_arg)
            # Rough estimate: ~100 tokens per message
            max_messages = max_tokens // 100
            filtered = messages[-max_messages:] if len(messages) > max_messages else messages
            logger.debug(
                f"Applied token_budget({max_tokens}) filter: {len(messages)} -> {len(filtered)} messages"
            )
            return filtered

        elif filter_type == "compose":
            # Apply multiple filters in sequence
            filtered = messages
            if isinstance(filter_arg, (list, tuple)):
                for sub_filter in filter_arg:
                    # Temporarily set the filter and apply recursively
                    old_filter = self.message_history_filter
                    self.message_history_filter = sub_filter
                    filtered = self._apply_message_history_filter(filtered)
                    self.message_history_filter = old_filter
            logger.debug(f"Applied compose filter: {len(messages)} -> {len(filtered)} messages")
            return filtered

        else:
            logger.warning(f"Unknown filter type: {filter_type}")
            return messages

    def __repr__(self) -> str:
        return f"AgentPrimitive('{self.name}', {len(self.message_history)} messages)"
