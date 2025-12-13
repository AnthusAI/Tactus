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

        # Create dependencies
        self.deps = AgentDeps(
            state_primitive=state_primitive,
            context=context,
            system_prompt_template=system_prompt_template,
            output_schema_guidance=output_schema_guidance,
        )

        # Create "done" tool first so we can include it in the Agent constructor
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

        # Create Pydantic AI Agent with all tools
        # Pydantic AI will use OPENAI_API_KEY from environment by default
        # If we need to pass it explicitly, we would use:
        # from pydantic_ai.models.openai import OpenAIChatModel
        # from pydantic_ai.providers.openai import OpenAIProvider
        # model_obj = OpenAIChatModel(model.split(':')[1], provider=OpenAIProvider(api_key=api_key))
        # For now, we assume OPENAI_API_KEY is set in environment
        self.agent = Agent(
            model, deps_type=AgentDeps, tools=all_tools, model_settings=model_settings
        )

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

    def turn(self) -> ResultPrimitive:
        """
        Execute one agent turn (synchronous wrapper for async Pydantic AI call).

        This method:
        1. Sends the current conversation to the LLM via Pydantic AI
        2. Handles tool calls automatically (Pydantic AI manages this)
        3. Records tool calls via tool_primitive
        4. Updates conversation history
        5. Returns a ResultPrimitive wrapping pydantic-ai's RunResult

        Returns:
            ResultPrimitive with access to data, usage, and messages
        """
        logger.debug(f"Agent '{self.name}' turn() called")

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
                _ = asyncio.get_running_loop()  # noqa: F841
                # We're in an async context - run in a thread with new event loop
                import threading

                result_container = {"value": None, "exception": None}

                def run_in_thread():
                    try:
                        result_container["value"] = asyncio.run(self._turn_async())
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
                return asyncio.run(self._turn_async())

        except Exception as e:
            logger.error(f"Agent '{self.name}' turn() failed: {e}", exc_info=True)
            raise

    async def _turn_async(self) -> ResultPrimitive:
        """
        Internal async method that performs the actual agent turn.

        Returns:
            ResultPrimitive wrapping pydantic-ai's RunResult
        """
        import time

        # Track start time for duration measurement
        start_time = time.time()

        # Prepare input message
        user_input = self.initial_message if not self.message_history else None
        if not user_input:
            # For subsequent turns, we need to continue the conversation
            # In Pydantic AI, we pass message_history to continue
            user_input = ""  # Empty input to continue conversation

        # Run agent with dependencies and message history
        if self.message_history:
            # Continue existing conversation
            result = await self.agent.run(
                user_input if user_input else "Continue",
                deps=self.deps,
                message_history=self.message_history,
                output_type=self.result_type,
            )
        else:
            # First turn - start new conversation
            result = await self.agent.run(
                self.initial_message or "Hello", deps=self.deps, output_type=self.result_type
            )

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Update message history
        new_messages = result.new_messages()
        self.message_history.extend(new_messages)

        # Record messages in chat recorder if available
        if self.chat_recorder:
            self._record_messages(new_messages)

        # Wrap result in ResultPrimitive for Lua access
        result_primitive = ResultPrimitive(result)

        # Extract all available tracing data
        tracing_data = result_primitive.extract_tracing_data()

        # Calculate and log comprehensive cost/metrics
        if self.log_handler:
            self._log_cost_event(result_primitive, duration_ms, new_messages, tracing_data)

        logger.debug(f"Agent '{self.name}' turn completed in {duration_ms:.0f}ms")
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

    def __repr__(self) -> str:
        return f"AgentPrimitive('{self.name}', {len(self.message_history)} messages)"
