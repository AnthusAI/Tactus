"""
DSPy-based Agent implementation for Tactus.

This module provides an Agent implementation built on top of DSPy primitives
(Module, Signature, History, Prediction). It maintains the same external API
as the original pydantic_ai-based Agent while using DSPy for LLM interactions.

The Agent uses:
- Module with chain_of_thought strategy for reasoning
- History for conversation management
- Tool handling similar to DSPy's ReAct pattern
- Unified mocking via Mocks {} primitive
"""

import logging
from typing import Any, Dict, List, Optional


from tactus.dspy.history import TactusHistory, create_history
from tactus.dspy.module import TactusModule, create_module
from tactus.dspy.prediction import wrap_prediction, TactusPrediction

logger = logging.getLogger(__name__)


class DSPyAgentHandle:
    """
    A DSPy-based Agent handle that provides the turn() method.

    This is a drop-in replacement for the pydantic_ai AgentHandle,
    using DSPy primitives for LLM interactions.

    Example usage in Lua:
        Agent("assistant", {
            system_prompt = "You are a helpful assistant",
            tools = { search, calculator }
        })

        Procedure "main" {
            function(input)
                -- Basic call (callable syntax)
                Assistant()

                -- Call with overrides
                Assistant({
                    tools = { "search" },
                    message = input.query
                })
            end
        }
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
        initial_message: Optional[str] = None,
        registry: Any = None,
        mock_manager: Any = None,
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
            initial_message: Initial message to send on first turn if no inject
            registry: Optional Registry instance for accessing mocks
            mock_manager: Optional MockManager instance for checking mocks
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
        self.initial_message = initial_message
        self.registry = registry
        self.mock_manager = mock_manager
        self.kwargs = kwargs

        # Initialize conversation history
        self._history = create_history()

        # Track conversation state
        self._turn_count = 0

        # Build the internal DSPy module
        self._module = self._build_module()

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
                "strategy": "chain_of_thought",
            },
        )

    def turn(
        self,
        opts: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Execute an agent turn.

        Args:
            opts: Optional dict with per-turn overrides:
                - inject: str - Message to inject for this turn
                - tools: List[str] - Tool names to use
                - temperature: float - Override temperature
                - max_tokens: int - Override max_tokens
                - context: Dict - Additional context

        Returns:
            ResultPrimitive-compatible object from agent turn
        """
        opts = opts or {}

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
            model_for_litellm = self.model.replace(":", "/") if ":" in self.model else self.model
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
        user_message = opts.get("inject")

        # Use initial_message on first turn if no inject provided
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        opts.get("tools")
        opts.get("toolsets")
        context = opts.get("context")
        opts.get("temperature")
        opts.get("max_tokens")

        # Determine effective tools for this turn

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

        # Configure LM settings for this turn

        # Execute the module
        try:
            # For now, use the basic module call
            # In a full implementation, this would handle tool calls via ReAct
            dspy_result = self._module.module(**prompt_context)

            # Wrap the result
            result = wrap_prediction(dspy_result)

            # Check if we have tool_calls to execute
            if hasattr(result, "tool_calls") and result.tool_calls and self._tool_primitive:
                # Parse and execute tool calls
                # This is a simple implementation - proper tool handling would use ReAct
                if "done" in str(result.tool_calls).lower():
                    # Extract reason from the tool call or response
                    reason = "Task completed"
                    if hasattr(result, "response"):
                        reason = result.response

                    # Record that the done tool was called
                    logger.info(f"Recording done tool call with reason: {reason}")
                    # Record the call so Tool.called("done") returns true
                    self._tool_primitive.record_call(
                        "done",
                        {"reason": reason},
                        {"status": "completed", "reason": reason, "tool": "done"},
                        agent_name=self.name,
                    )

            # Add to history
            if user_message:
                self._history.add({"role": "user", "content": user_message})
            if hasattr(result, "response"):
                self._history.add({"role": "assistant", "content": result.response})

            return result

        except Exception as e:
            logger.error(f"Agent '{self.name}' turn failed: {e}")
            raise

    def __call__(self, inputs: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute an agent turn using the callable interface.

        This is the unified callable interface that allows:
            result = worker({message = "Hello"})

        The 'message' field is mapped to the 'inject' parameter for turn().

        Args:
            inputs: Input dict with fields matching input_schema.
                   Default field 'message' is used as the user message.
                   Additional fields are passed as context.

        Returns:
            Result object with response and other fields

        Example (Lua):
            result = worker({message = "Process this task"})
            print(result.response)
        """
        inputs = inputs or {}

        # Convert Lua table to dict if needed
        if hasattr(inputs, "items"):
            try:
                inputs = dict(inputs.items())
            except (AttributeError, TypeError):
                pass

        # Extract message field (the main input)
        message = inputs.get("message")

        # Build turn options
        opts = {}
        if message:
            opts["inject"] = message

        # Pass remaining fields as context
        context = {k: v for k, v in inputs.items() if k != "message"}
        if context:
            opts["context"] = context

        # Call turn() with the mapped options
        return self.turn(opts)

    def _get_mock_response(self, opts: Dict[str, Any]) -> Optional[TactusPrediction]:
        """
        Check if this agent has a mock configured and return mock response.

        Uses the same mock logic as tools and modules: static (returns), temporal, and conditional.

        Args:
            opts: The turn options

        Returns:
            TactusPrediction if mocked, None otherwise
        """
        agent_name = self.name

        # Check if agent has a mock in the registry
        if agent_name not in self.registry.mocks:
            return None

        # Use mock_manager to get the response (handles static/temporal/conditional logic)
        try:
            mock_data = self.mock_manager.get_mock_response(agent_name, opts)
            if mock_data is not None:
                return self._wrap_mock_response(mock_data, opts)
        except Exception:
            # If mock_manager throws an error (e.g., error simulation), let it propagate
            raise

        return None

    def _wrap_mock_response(
        self, mock_data: Dict[str, Any], opts: Dict[str, Any]
    ) -> TactusPrediction:
        """
        Wrap mock data as a TactusPrediction.

        Also handles special mock behaviors like recording done tool calls.

        Args:
            mock_data: The mock response data
            opts: The turn options

        Returns:
            TactusPrediction wrapping the mock data
        """
        from tactus.dspy.prediction import create_prediction

        # Create prediction from mock data
        result = create_prediction(**mock_data)

        # Check if mock simulates a done tool call
        # This allows mocks to trigger Tool.called("done") behavior
        # Use getattr since _tool_primitive is set externally by runtime
        tool_primitive = getattr(self, "_tool_primitive", None)
        if "tool_calls" in mock_data and tool_primitive:
            tool_calls = mock_data.get("tool_calls", "")
            if "done" in str(tool_calls).lower():
                # Extract reason from mock response
                reason = mock_data.get("response", "Task completed (mocked)")

                # Record that the done tool was called
                logger.debug(f"Mock recording done tool call with reason: {reason}")
                tool_primitive.record_call(
                    "done",
                    {"reason": reason},
                    {"status": "completed", "reason": reason, "tool": "done"},
                    agent_name=self.name,
                )

        # Update history with mock response (to maintain conversation state)
        user_message = opts.get("inject")
        if self._turn_count == 1 and not user_message and self.initial_message:
            user_message = self.initial_message

        if user_message:
            self._history.add({"role": "user", "content": user_message})
        if "response" in mock_data:
            self._history.add({"role": "assistant", "content": mock_data["response"]})

        return result

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
        initial_message=config.get("initial_message"),
        registry=registry,
        mock_manager=mock_manager,
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
                "initial_message",
            ]
        },
    )
