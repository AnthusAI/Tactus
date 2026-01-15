"""
DSPy-based Agent implementation for Tactus.

This module provides an Agent implementation built on top of DSPy primitives
(Module, Signature, History, Prediction). It maintains the same external API
as the original pydantic_ai-based Agent while using DSPy for LLM interactions.

The Agent uses:
- Configurable DSPy module (default: Predict for simple pass-through, or ChainOfThought for reasoning)
- History for conversation management
- Tool handling similar to DSPy's ReAct pattern
- Unified mocking via Mocks {} primitive
"""

import logging
from typing import Any, Dict, List, Optional

from tactus.dspy.history import TactusHistory, create_history
from tactus.dspy.module import TactusModule, create_module
from tactus.dspy.prediction import TactusPrediction, wrap_prediction
from tactus.protocols.cost import CostStats, UsageStats
from tactus.protocols.result import TactusResult

logger = logging.getLogger(__name__)


class DSPyAgentHandle:
    """
    A DSPy-based Agent handle that provides the callable interface.

    This is a drop-in replacement for the pydantic_ai AgentHandle,
    using DSPy primitives for LLM interactions.

    Example usage in Lua:
        worker = Agent {
            system_prompt = "You are a helpful assistant",
            tools = {search, calculator}
        }

        -- Call the agent directly
        worker()
        worker({message = input.query})
    """

    def __init__(
        self,
        name: str,
        system_prompt: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        toolsets: Optional[List[str]] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        model_type: Optional[str] = None,
        module: str = "Raw",
        initial_message: Optional[str] = None,
        registry: Any = None,
        mock_manager: Any = None,
        log_handler: Any = None,
        disable_streaming: bool = False,
        **kwargs: Any,
    ):
        """
        Initialize a DSPy-based Agent.

        Args:
            name: Agent name (used for tracking/logging)
            system_prompt: System prompt for the agent
            model: Model name (in LiteLLM format, e.g., "openai/gpt-4o")
            provider: Provider name (deprecated, use model instead)
            tools: List of tools available to the agent
            toolsets: List of toolset names to include
            input_schema: Optional input schema for validation (default: {message: string})
            output_schema: Optional output schema for validation (default: {response: string})
            temperature: Model temperature (default: 0.7)
            max_tokens: Maximum tokens for response
            model_type: Model type for DSPy (e.g., "chat", "responses" for reasoning models)
            module: DSPy module type to use (default: "Raw", case-insensitive). Options:
                - "Raw": Minimal formatting, direct LM calls (lowest token overhead)
                - "Predict": Simple pass-through prediction (no reasoning traces)
                - "ChainOfThought": Adds step-by-step reasoning before response
            initial_message: Initial message to send on first turn if no inject
            registry: Optional Registry instance for accessing mocks
            mock_manager: Optional MockManager instance for checking mocks
            log_handler: Optional log handler for emitting streaming events
            disable_streaming: If True, disable streaming even when log_handler is present
            **kwargs: Additional configuration
        """
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.provider = provider
        self.tools = tools or []
        self.toolsets = toolsets or []
        # Default input schema: {message: string}
        self.input_schema = input_schema or {"message": {"type": "string", "required": False}}
        # Default output schema: {response: string}
        self.output_schema = output_schema or {"response": {"type": "string", "required": False}}
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.model_type = model_type
        self.module = module
        self.initial_message = initial_message
        self.registry = registry
        self.mock_manager = mock_manager
        self.log_handler = log_handler
        self.disable_streaming = disable_streaming
        self.kwargs = kwargs

        # Initialize conversation history
        self._history = create_history()

        # Track conversation state
        self._turn_count = 0

        # Cumulative cost/usage stats (monotonic across turns)
        self._cumulative_usage = UsageStats()
        self._cumulative_cost = CostStats()

        # Build the internal DSPy module
        self._module = self._build_module()

    @property
    def usage(self) -> UsageStats:
        """Return cumulative token usage incurred by this agent so far."""
        return self._cumulative_usage

    def cost(self) -> CostStats:
        """Return cumulative cost incurred by this agent so far."""
        return self._cumulative_cost

    def _add_usage_and_cost(self, usage_stats: UsageStats, cost_stats: CostStats) -> None:
        """Accumulate a per-call UsageStats/CostStats into agent totals."""
        self._cumulative_usage.prompt_tokens += usage_stats.prompt_tokens
        self._cumulative_usage.completion_tokens += usage_stats.completion_tokens
        self._cumulative_usage.total_tokens += usage_stats.total_tokens

        self._cumulative_cost.total_cost += cost_stats.total_cost
        self._cumulative_cost.prompt_cost += cost_stats.prompt_cost
        self._cumulative_cost.completion_cost += cost_stats.completion_cost

        # Preserve "latest known" model/provider for introspection
        if cost_stats.model:
            self._cumulative_cost.model = cost_stats.model
        if cost_stats.provider:
            self._cumulative_cost.provider = cost_stats.provider

    def _extract_last_call_stats(self) -> tuple[UsageStats, CostStats]:
        """
        Extract usage+cost from DSPy's LM history for the most recent call.

        Returns zeroed stats if no LM history is available (e.g., mocked calls).
        """
        import dspy

        # Default to zero (e.g., mocks or no LM configured)
        usage_stats = UsageStats()
        cost_stats = CostStats()

        lm = dspy.settings.lm
        if lm is None or not hasattr(lm, "history") or not lm.history:
            return usage_stats, cost_stats

        last_call = lm.history[-1]

        # Usage
        usage = last_call.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", 0) or 0)
        usage_stats = UsageStats(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

        # Model/provider
        model = last_call.get("model", self.model or None)
        provider = None
        if model and "/" in str(model):
            provider = str(model).split("/")[0]

        # Cost: prefer the history value, fallback to hidden params / LiteLLM calc
        total_cost = last_call.get("cost")
        if total_cost is None:
            response = last_call.get("response")
            if response and hasattr(response, "_hidden_params"):
                total_cost = response._hidden_params.get("response_cost")

            if total_cost is None and total_tokens > 0:
                try:
                    # We already have token counts, so compute cost from tokens to avoid relying
                    # on provider-specific response object shapes.
                    from litellm.cost_calculator import cost_per_token

                    prompt_cost, completion_cost = cost_per_token(
                        model=str(model) if model is not None else "",
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        call_type="completion",
                    )
                    total_cost = float(prompt_cost) + float(completion_cost)
                except Exception as e:
                    logger.warning(f"[COST] Agent '{self.name}': failed to calculate cost: {e}")
                    total_cost = 0.0
            elif total_cost is None:
                total_cost = 0.0

        total_cost = float(total_cost or 0.0)

        # Approximate prompt/completion split by token ratio
        if total_tokens > 0 and total_cost > 0:
            prompt_cost = total_cost * (prompt_tokens / total_tokens)
            completion_cost = total_cost * (completion_tokens / total_tokens)
        else:
            prompt_cost = 0.0
            completion_cost = 0.0

        cost_stats = CostStats(
            total_cost=total_cost,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            model=str(model) if model is not None else None,
            provider=provider,
        )

        return usage_stats, cost_stats

    def _prediction_to_value(self, prediction: TactusPrediction) -> Any:
        """
        Convert a Prediction into a stable `result.output`.

        Default behavior:
        - Prefer the `response` field when present (string)
        - Otherwise fall back to `prediction.message`
        - If an output schema is configured, attempt to parse JSON into a dict/list
        - If multiple output fields exist, return a dict (excluding internal fields)
        """
        try:
            data = prediction.data()
        except Exception:
            data = {}

        filtered = {k: v for k, v in data.items() if k not in {"tool_calls"}}

        if "response" in filtered and isinstance(filtered["response"], str) and len(filtered) <= 1:
            text = filtered["response"]
        else:
            text = prediction.message

        # If output schema is configured, prefer structured JSON when possible
        if self.output_schema and isinstance(text, str) and text.strip():
            import json

            try:
                parsed = json.loads(text)
                return parsed
            except Exception:
                pass

        # If multiple non-internal output fields exist, return structured dict
        if len(filtered) > 1:
            return filtered

        if len(filtered) == 1:
            return next(iter(filtered.values()))

        return text

    def _wrap_as_result(
        self, prediction: TactusPrediction, usage_stats: UsageStats, cost_stats: CostStats
    ) -> TactusResult:
        """Wrap a Prediction into the standard TactusResult."""
        return TactusResult(
            output=self._prediction_to_value(prediction),
            usage=usage_stats,
            cost_stats=cost_stats,
        )

    def _module_to_strategy(self, module: str) -> str:
        """
        Map DSPy module name to internal strategy name.

        Args:
            module: DSPy module name (e.g., "Predict", "ChainOfThought")

        Returns:
            Internal strategy name for create_module()

        Raises:
            ValueError: If module name is not recognized
        """
        mapping = {
            "predict": "predict",
            "chainofthought": "chain_of_thought",
            "raw": "raw",
            # Future modules can be added here:
            # "react": "react",
            # "programofthought": "program_of_thought",
        }
        strategy = mapping.get(module.lower())
        if strategy is None:
            raise ValueError(f"Unknown module '{module}'. Supported: {list(mapping.keys())}")
        return strategy

    def _build_module(self) -> TactusModule:
        """Build the internal DSPy module for this agent."""
        # Create a signature for agent turns
        # Input: system_prompt, history, user_message, available_tools
        # Output: response and tool_calls (if tools are needed)
        # Include tools in the signature if they're available
        if self.tools or self.toolsets:
            signature = (
                "system_prompt, history, user_message, available_tools -> response, tool_calls"
            )
        else:
            signature = "system_prompt, history, user_message -> response"

        return create_module(
            f"{self.name}_module",
            {
                "signature": signature,
                "strategy": self._module_to_strategy(self.module),
            },
        )

    def _should_stream(self) -> bool:
        """
        Determine if streaming should be enabled for this agent.

        Streaming is enabled when:
        - log_handler is available (for emitting events)
        - log_handler supports streaming events
        - disable_streaming is False
        - No structured output schema (streaming only works with plain text)

        Returns:
            True if streaming should be enabled
        """
        # Must have log_handler to emit streaming events
        if self.log_handler is None:
            logger.debug(f"[STREAMING] Agent '{self.name}': no log_handler, streaming disabled")
            return False

        # Allow log handlers to opt out of streaming (e.g., cost-only collectors)
        supports_streaming = getattr(self.log_handler, "supports_streaming", True)
        if not supports_streaming:
            logger.debug(
                f"[STREAMING] Agent '{self.name}': log_handler supports_streaming=False, streaming disabled"
            )
            return False

        # Respect explicit disable flag
        if self.disable_streaming:
            logger.debug(
                f"[STREAMING] Agent '{self.name}': disable_streaming=True, streaming disabled"
            )
            return False

        # Note: We intentionally allow streaming even with output_schema.
        # Streaming (UI feedback) and validation (post-processing) are orthogonal.
        # Stream raw text to UI during generation, then validate after completion.

        logger.info(f"[STREAMING] Agent '{self.name}': streaming ENABLED")
        return True

    def _emit_cost_event(self) -> None:
        """
        Emit a CostEvent based on the most recent LLM call in the LM history.

        Extracts usage and cost information from DSPy's LM history and emits
        a CostEvent for tracking in the IDE.
        """
        if self.log_handler is None:
            return

        import dspy
        from tactus.protocols.models import CostEvent

        # Get the current LM
        lm = dspy.settings.lm
        if lm is None or not hasattr(lm, "history") or not lm.history:
            logger.debug(f"[COST] Agent '{self.name}': no LM history available")
            return

        # Get the most recent call
        last_call = lm.history[-1]

        # Extract usage information
        usage = last_call.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)

        # Extract cost information
        total_cost = last_call.get("cost")
        logger.debug(f"[COST] Agent '{self.name}': raw cost from history = {total_cost}")

        # If cost is None (happens with streamify()), calculate it using LiteLLM
        if total_cost is None:
            response = last_call.get("response")
            if response and hasattr(response, "_hidden_params"):
                total_cost = response._hidden_params.get("response_cost")
                logger.debug(f"[COST] Agent '{self.name}': cost from _hidden_params = {total_cost}")

            # If still None, calculate manually using litellm.completion_cost
            if total_cost is None and response:
                try:
                    import litellm

                    total_cost = litellm.completion_cost(completion_response=response)
                    logger.debug(f"[COST] Agent '{self.name}': calculated cost = {total_cost}")
                except Exception as e:
                    logger.warning(f"[COST] Agent '{self.name}': failed to calculate cost: {e}")
                    total_cost = 0.0
            elif total_cost is None:
                total_cost = 0.0
                logger.warning(f"[COST] Agent '{self.name}': no cost information available")

        # Calculate per-token costs (approximate)
        # Note: LiteLLM provides total cost, we can approximate prompt/completion split
        # based on token ratios
        if total_tokens > 0 and total_cost > 0:
            prompt_cost = total_cost * (prompt_tokens / total_tokens)
            completion_cost = total_cost * (completion_tokens / total_tokens)
        else:
            prompt_cost = 0.0
            completion_cost = 0.0

        # Extract duration from response metadata
        response = last_call.get("response")
        duration_ms = None
        if response and hasattr(response, "_hidden_params"):
            duration_ms = response._hidden_params.get("_response_ms")

        # Extract model info
        model = last_call.get("model", self.model or "unknown")

        # Parse provider from model string (e.g., "openai/gpt-4o" -> "openai")
        provider = "unknown"
        if "/" in str(model):
            provider = str(model).split("/")[0]

        # Create and emit cost event
        cost_event = CostEvent(
            agent_name=self.name,
            model=model,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            prompt_cost=prompt_cost,
            completion_cost=completion_cost,
            total_cost=total_cost,
            duration_ms=duration_ms,
        )

        self.log_handler.log(cost_event)
        logger.info(f"[COST] Agent '{self.name}': ${total_cost:.6f} ({total_tokens} tokens)")

    def _turn_with_streaming(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        """
        Execute an agent turn with streaming enabled.

        Uses DSPy's streamify() to wrap the module for streaming output.
        Runs in a separate thread to avoid event loop conflicts.
        Chunks are emitted as AgentStreamChunkEvent for real-time display in the UI.

        Args:
            opts: Turn options
            prompt_context: Prepared prompt context for the module

        Returns:
            TactusResult with value, usage, and cost_stats
        """
        import asyncio
        import threading
        import queue
        from tactus.protocols.models import AgentTurnEvent, AgentStreamChunkEvent

        logger.info(f"[STREAMING] Agent '{self.name}' starting streaming turn")

        # Emit turn started event so the UI shows a loading indicator
        self.log_handler.log(
            AgentTurnEvent(
                agent_name=self.name,
                stage="started",
            )
        )
        logger.info(f"[STREAMING] Agent '{self.name}' emitted AgentTurnEvent(started)")

        # Queue for passing chunks from streaming thread to main thread
        chunk_queue = queue.Queue()
        result_holder = {"result": None, "error": None}

        def run_streaming_in_thread():
            """Run DSPy streaming in a separate thread with its own event loop."""
            import dspy as dspy_thread  # Import in thread context

            async def async_streaming():
                """Async function that runs the streaming module."""
                try:
                    # Create a streaming version of the module using DSPy's streamify
                    # NOTE: streamify() automatically enables streaming on the LM
                    # We do NOT need to use settings.context(stream=True) - that actually breaks it!
                    streaming_module = dspy_thread.streamify(self._module.module)
                    logger.info(f"[STREAMING] Agent '{self.name}' created streaming module")

                    # Call the streaming module - it returns an async generator
                    stream = streaming_module(**prompt_context)

                    chunk_count = 0
                    async for value in stream:
                        chunk_count += 1
                        value_type = type(value).__name__

                        # Check for final Prediction first
                        if isinstance(value, dspy_thread.Prediction):
                            # Final prediction - this is the result
                            logger.info(
                                f"[STREAMING] Agent '{self.name}' received final Prediction"
                            )
                            result_holder["result"] = value
                        # Check for ModelResponseStream (the actual streaming chunks!)
                        elif hasattr(value, "choices") and value.choices:
                            delta = value.choices[0].delta
                            if hasattr(delta, "content") and delta.content:
                                logger.info(
                                    f"[STREAMING] Agent '{self.name}' chunk #{chunk_count}: '{delta.content}'"
                                )
                                chunk_queue.put(("chunk", delta.content))
                        # String chunks (shouldn't happen with DSPy but handle it anyway)
                        elif isinstance(value, str):
                            logger.info(
                                f"[STREAMING] Agent '{self.name}' got STRING chunk, len={len(value)}"
                            )
                            if value:
                                chunk_queue.put(("chunk", value))
                        else:
                            logger.warning(
                                f"[STREAMING] Agent '{self.name}' got unexpected type: {value_type}"
                            )

                    logger.info(
                        f"[STREAMING] Agent '{self.name}' stream finished, processed {chunk_count} values"
                    )

                except Exception as e:
                    logger.error(f"[STREAMING] Agent '{self.name}' error: {e}", exc_info=True)
                    result_holder["error"] = e
                finally:
                    # Signal end of stream
                    chunk_queue.put(("done", None))

            # Run the async function in this thread's new event loop
            asyncio.run(async_streaming())

        # Start streaming in a separate thread
        streaming_thread = threading.Thread(target=run_streaming_in_thread, daemon=True)
        streaming_thread.start()

        # Consume chunks from the queue and emit events in the main thread
        accumulated_text = ""
        emitted_count = 0
        logger.info(f"[STREAMING] Agent '{self.name}' consuming chunks from queue")

        while True:
            try:
                msg_type, msg_data = chunk_queue.get(timeout=120.0)  # 2 minute timeout
                if msg_type == "done":
                    break
                elif msg_type == "chunk" and msg_data:
                    accumulated_text += msg_data
                    emitted_count += 1
                    event = AgentStreamChunkEvent(
                        agent_name=self.name,
                        chunk_text=msg_data,
                        accumulated_text=accumulated_text,
                    )
                    logger.info(
                        f"[STREAMING] Agent '{self.name}' emitting chunk {emitted_count}, len={len(msg_data)}"
                    )
                    self.log_handler.log(event)
            except queue.Empty:
                logger.warning(f"[STREAMING] Agent '{self.name}' timeout waiting for chunks")
                break

        # Wait for thread to complete
        streaming_thread.join(timeout=5.0)

        logger.info(f"[STREAMING] Agent '{self.name}' finished, emitted {emitted_count} events")

        # Check for errors
        if result_holder["error"] is not None:
            raise result_holder["error"]

        # If streaming failed to produce a result, fall back to non-streaming
        if result_holder["result"] is None:
            logger.warning(f"Streaming produced no result for agent '{self.name}', falling back")
            return self._turn_without_streaming(opts, prompt_context)

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if hasattr(result_holder["result"], "response"):
            assistant_msg = {"role": "assistant", "content": result_holder["result"].response}
            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

        # Wrap the result with message tracking
        wrapped_result = wrap_prediction(
            result_holder["result"],
            new_messages=new_messages,
            all_messages=self._history.get(),
        )

        # Handle tool calls if present
        if hasattr(wrapped_result, "tool_calls") and wrapped_result.tool_calls:
            tool_primitive = getattr(self, "_tool_primitive", None)
            if tool_primitive and "done" in str(wrapped_result.tool_calls).lower():
                reason = (
                    wrapped_result.response
                    if hasattr(wrapped_result, "response")
                    else "Task completed"
                )
                logger.info(f"Recording done tool call with reason: {reason}")
                tool_primitive.record_call(
                    "done",
                    {"reason": reason},
                    {"status": "completed", "reason": reason, "tool": "done"},
                    agent_name=self.name,
                )

        # Emit turn completed event
        self.log_handler.log(
            AgentTurnEvent(
                agent_name=self.name,
                stage="completed",
            )
        )
        logger.info(f"[STREAMING] Agent '{self.name}' emitted AgentTurnEvent(completed)")

        # Extract usage and cost stats
        usage_stats, cost_stats = self._extract_last_call_stats()

        # Emit cost event with usage and cost information
        self._emit_cost_event()

        # Wrap as TactusResult with value, usage, and cost
        return self._wrap_as_result(wrapped_result, usage_stats, cost_stats)

    def _turn_without_streaming(
        self,
        opts: Dict[str, Any],
        prompt_context: Dict[str, Any],
    ) -> TactusResult:
        """
        Execute an agent turn without streaming.

        This is the standard execution path that waits for the full response.

        Args:
            opts: Turn options
            prompt_context: Prepared prompt context for the module

        Returns:
            TactusResult with value, usage, and cost_stats
        """
        # Execute the module
        dspy_result = self._module.module(**prompt_context)

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if hasattr(dspy_result, "response"):
            assistant_msg = {"role": "assistant", "content": dspy_result.response}
            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

        # Wrap the result with message tracking
        wrapped_result = wrap_prediction(
            dspy_result,
            new_messages=new_messages,
            all_messages=self._history.get(),
        )

        # Handle tool calls if present
        if hasattr(wrapped_result, "tool_calls") and wrapped_result.tool_calls:
            tool_primitive = getattr(self, "_tool_primitive", None)
            if tool_primitive and "done" in str(wrapped_result.tool_calls).lower():
                reason = (
                    wrapped_result.response
                    if hasattr(wrapped_result, "response")
                    else "Task completed"
                )
                logger.info(f"Recording done tool call with reason: {reason}")
                tool_primitive.record_call(
                    "done",
                    {"reason": reason},
                    {"status": "completed", "reason": reason, "tool": "done"},
                    agent_name=self.name,
                )

        # Extract usage and cost stats
        usage_stats, cost_stats = self._extract_last_call_stats()

        # Emit cost event with usage and cost information
        self._emit_cost_event()

        # Wrap as TactusResult with value, usage, and cost
        return self._wrap_as_result(wrapped_result, usage_stats, cost_stats)

    def __call__(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute an agent turn using the callable interface.

        This is the unified callable interface that allows:
            result = worker({message = "Hello"})

        Args:
            inputs: Input dict with fields matching input_schema.
                   Default field 'message' is used as the user message.
                   Additional fields are passed as context.
                   Can also include per-turn overrides like:
                   - tools: List[Any] - Tool/toolset references and toolset expressions to use
                   - temperature: float - Override temperature
                   - max_tokens: int - Override max_tokens

        Returns:
            Result object with response and other fields

        Example (Lua):
            result = worker({message = "Process this task"})
            print(result.response)
        """
        logger.debug(f"Agent '{self.name}' invoked via __call__()")
        # Convenience: allow shorthand string calls in Lua:
        #   worker("Hello") == worker({message = "Hello"})
        if isinstance(inputs, str):
            inputs = {"message": inputs}

        inputs = inputs or {}

        # Convert Lua table to dict if needed
        if hasattr(inputs, "items"):
            try:
                inputs = dict(inputs.items())
            except (AttributeError, TypeError):
                pass

        # Extract message field (the main input)
        message = inputs.get("message")

        # Build turn options (keeping per-turn overrides like tools, temperature, etc.)
        opts = {}
        if message:
            opts["message"] = message

        # Pass remaining fields - some are per-turn overrides, others are context
        override_keys = {"tools", "temperature", "max_tokens"}
        for key in override_keys:
            if key in inputs:
                opts[key] = inputs[key]

        # Everything else goes into context
        context = {k: v for k, v in inputs.items() if k not in ({"message"} | override_keys)}
        if context:
            opts["context"] = context

        # Execute the turn (inlined from old turn() method)
        self._turn_count += 1
        logger.debug(f"Agent '{self.name}' turn {self._turn_count}")

        # Check for mock first (before any LLM calls)
        if self.mock_manager and self.registry:
            mock_response = self._get_mock_response(opts)
            if mock_response is not None:
                logger.debug(f"Agent '{self.name}' returning mock response")
                return mock_response

        # Auto-configure LM if not already configured
        from tactus.dspy.config import get_current_lm, configure_lm

        if get_current_lm() is None and self.model:
            # Convert model format from "provider:model" to "provider/model" for LiteLLM
            # Only replace the FIRST colon (provider separator), not all colons
            # Bedrock model IDs like "us.anthropic.claude-haiku-4-5-20251001-v1:0" have a version suffix
            model_for_litellm = self.model.replace(":", "/", 1) if ":" in self.model else self.model
            logger.info(f"Auto-configuring DSPy LM with model: {model_for_litellm}")

            # Build kwargs for configure_lm
            config_kwargs = {}
            if self.temperature is not None:
                config_kwargs["temperature"] = self.temperature
            if self.max_tokens is not None:
                config_kwargs["max_tokens"] = self.max_tokens
            if self.model_type is not None:
                config_kwargs["model_type"] = self.model_type

            configure_lm(model_for_litellm, **config_kwargs)

        # Extract options
        user_message = opts.get("message")

        # Use initial_message on first turn if no inject provided
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        context = opts.get("context")

        # Build the prompt context
        prompt_context = {
            "system_prompt": self.system_prompt,
            "history": self._history.to_dspy(),
            "user_message": user_message or "",
        }

        # Add available tools if agent has them
        if self.tools or self.toolsets:
            # Format tools for the prompt
            tool_descriptions = []
            if self.toolsets:
                # Convert toolsets to strings if they're not already
                toolset_names = [str(ts) if not isinstance(ts, str) else ts for ts in self.toolsets]
                tool_descriptions.append(f"Available toolsets: {', '.join(toolset_names)}")
                tool_descriptions.append(
                    "Use the 'done' tool with a 'reason' parameter to complete the task."
                )
            prompt_context["available_tools"] = (
                "\n".join(tool_descriptions) if tool_descriptions else "No tools available"
            )

        # Add any injected context (user_message is already in prompt_context)
        if context:
            prompt_context["context"] = context

        # Check if we should use streaming
        if self._should_stream():
            logger.debug(f"Agent '{self.name}' using streaming mode")
            return self._turn_with_streaming(opts, prompt_context)

        # Non-streaming execution
        logger.debug(f"Agent '{self.name}' using non-streaming mode")

        try:
            return self._turn_without_streaming(opts, prompt_context)
        except Exception as e:
            logger.error(f"Agent '{self.name}' turn failed: {e}")
            raise

    def _get_mock_response(self, opts: Dict[str, Any]) -> Optional[TactusPrediction]:
        """
        Check if this agent has a mock configured and return mock response.

        Agent mocks are stored in registry.agent_mocks (not registry.mocks which is for tools).
        Agent mock configs specify tool_calls, message, data, and usage.

        Args:
            opts: The turn options

        Returns:
            TactusPrediction if mocked, None otherwise
        """
        agent_name = self.name

        # Check if agent has a mock in the registry (agent_mocks, not mocks)
        if not self.registry or agent_name not in self.registry.agent_mocks:
            return None

        # Get agent mock config from registry.agent_mocks
        mock_config = self.registry.agent_mocks[agent_name]

        temporal_turns = getattr(mock_config, "temporal", None) or []
        if temporal_turns:
            injected = opts.get("message")

            selected_turn = None
            if injected is not None:
                for turn in temporal_turns:
                    if isinstance(turn, dict) and turn.get("when_message") == injected:
                        selected_turn = turn
                        break

            if selected_turn is None:
                idx = self._turn_count - 1  # 1-indexed turns
                if idx < 0:
                    idx = 0
                if idx >= len(temporal_turns):
                    idx = len(temporal_turns) - 1
                selected_turn = temporal_turns[idx]

            turn = selected_turn
            if isinstance(turn, dict):
                message = turn.get("message", mock_config.message)
                tool_calls = turn.get("tool_calls", mock_config.tool_calls)
                data = turn.get("data", mock_config.data)
            else:
                message = mock_config.message
                tool_calls = mock_config.tool_calls
                data = mock_config.data
        else:
            message = mock_config.message
            tool_calls = mock_config.tool_calls
            data = mock_config.data

        # Convert AgentMockConfig to format expected by _wrap_mock_response.
        # Important: we do NOT embed `data`/`usage` inside the prediction output by default.
        # The canonical agent payload is `result.output`:
        # - If the agent has an explicit output schema, we allow structured output via `data`.
        # - Otherwise, `result.output` is the plain response string.
        mock_data = {
            "response": message,
            "tool_calls": tool_calls,
        }

        if self.output_schema and data:
            mock_data["data"] = data

        try:
            return self._wrap_mock_response(mock_data, opts)
        except Exception:
            # If wrapping throws an error, let it propagate
            raise

    def _wrap_mock_response(self, mock_data: Dict[str, Any], opts: Dict[str, Any]) -> TactusResult:
        """
        Wrap mock data as a TactusResult.

        Also handles special mock behaviors like recording done tool calls.

        Args:
            mock_data: The mock response data. Can contain either 'message' or 'response'
                      field for the text response. If 'message' is present and 'response'
                      is not, it will be normalized to 'response' to match the agent's
                      output signature.
            opts: The turn options

        Returns:
            TactusResult with value, usage, and cost_stats (zeroed for mocks)
        """
        from tactus.dspy.prediction import create_prediction

        response_text = None
        if "response" in mock_data and isinstance(mock_data.get("response"), str):
            response_text = mock_data["response"]
        elif "message" in mock_data and isinstance(mock_data.get("message"), str):
            response_text = mock_data["message"]
        else:
            response_text = ""

        # Track new messages for this turn
        new_messages = []

        # Determine user message
        user_message = opts.get("message")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        # Add user message to new_messages if present
        if user_message:
            user_msg = {"role": "user", "content": user_message}
            new_messages.append(user_msg)
            self._history.add(user_msg)

        # Add assistant response to new_messages
        if response_text:
            assistant_msg = {"role": "assistant", "content": response_text}
            new_messages.append(assistant_msg)
            self._history.add(assistant_msg)

        prediction_fields: Dict[str, Any] = {}

        tool_calls_list = mock_data.get("tool_calls", [])
        if tool_calls_list:
            prediction_fields["tool_calls"] = tool_calls_list

        # If the agent has an explicit output schema, allow structured output via mock `data`.
        # Otherwise default to plain string output.
        data = mock_data.get("data")
        if self.output_schema and isinstance(data, dict) and data:
            prediction_fields.update(data)
        else:
            prediction_fields["response"] = response_text

        # Add message tracking to prediction
        prediction_fields["__new_messages__"] = new_messages
        prediction_fields["__all_messages__"] = self._history.get()

        # Create prediction from normalized mock data
        result = create_prediction(**prediction_fields)

        # Record all tool calls from the mock
        # This allows mocks to trigger Tool.called(...) behavior
        # Use getattr since _tool_primitive is set externally by runtime
        tool_primitive = getattr(self, "_tool_primitive", None)
        if tool_calls_list and tool_primitive:
            if isinstance(tool_calls_list, list):
                for tool_call in tool_calls_list:
                    if isinstance(tool_call, dict) and "tool" in tool_call:
                        tool_name = tool_call["tool"]
                        tool_args = tool_call.get("args", {})

                        # For done tool, extract reason for result
                        if tool_name == "done":
                            reason = tool_args.get(
                                "reason",
                                response_text or "Task completed (mocked)",
                            )
                            tool_result = {"status": "completed", "reason": reason, "tool": "done"}
                        else:
                            # For other tools, use a generic result
                            tool_result = {"tool": tool_name, "args": tool_args}

                        logger.debug(f"Mock recording {tool_name} tool call")
                        tool_primitive.record_call(
                            tool_name,
                            tool_args,
                            tool_result,
                            agent_name=self.name,
                        )

        # Return as TactusResult with zeroed usage/cost (mocks don't incur costs)
        return self._wrap_as_result(result, UsageStats(), CostStats())

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history.clear()
        self._turn_count = 0

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history."""
        return self._history.get()

    @property
    def history(self) -> TactusHistory:
        """Get the history object."""
        return self._history


def create_dspy_agent(
    name: str,
    config: Dict[str, Any],
    registry: Any = None,
    mock_manager: Any = None,
) -> DSPyAgentHandle:
    """
    Create a DSPy-based Agent from configuration.

    This is the main entry point for creating DSPy agents.

    Args:
        name: Agent name
        config: Configuration dict with:
            - system_prompt: System prompt
            - model: Model name (LiteLLM format)
            - tools: List of tools
            - toolsets: List of toolset names
            - module: DSPy module type (default: "Predict"). Options: "Predict", "ChainOfThought"
            - Other optional configuration
        registry: Optional Registry instance for accessing mocks
        mock_manager: Optional MockManager instance for checking mocks

    Returns:
        A DSPyAgentHandle instance

    Raises:
        ValueError: If no LM is configured (either via config or globally)
    """
    # Check if LM is configured either in config or globally
    from tactus.dspy.config import get_current_lm

    if not config.get("model") and not get_current_lm():
        raise ValueError("LM not configured. Please configure an LM before creating an agent.")

    return DSPyAgentHandle(
        name=name,
        system_prompt=config.get("system_prompt", ""),
        model=config.get("model"),
        provider=config.get("provider"),
        tools=config.get("tools", []),
        toolsets=config.get("toolsets", []),
        output_schema=config.get("output_schema") or config.get("output"),
        temperature=config.get("temperature", 0.7),
        max_tokens=config.get("max_tokens"),
        model_type=config.get("model_type"),
        module=config.get("module", "Raw"),
        initial_message=config.get("initial_message"),
        registry=registry,
        mock_manager=mock_manager,
        log_handler=config.get("log_handler"),
        disable_streaming=config.get("disable_streaming", False),
        **{
            k: v
            for k, v in config.items()
            if k
            not in [
                "system_prompt",
                "model",
                "provider",
                "tools",
                "toolsets",
                "output_schema",
                "output",
                "temperature",
                "max_tokens",
                "model_type",
                "module",
                "initial_message",
                "log_handler",
                "disable_streaming",
            ]
        },
    )
