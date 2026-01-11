"""
DSPy Module integration for Tactus.

This module provides the Module primitive that maps to DSPy modules,
supporting various prediction strategies like Predict, ChainOfThought, etc.
"""

import logging
from typing import Any, Dict, Optional, Union

import dspy

from tactus.dspy.signature import create_signature

logger = logging.getLogger(__name__)


class RawModule(dspy.Module):
    """
    Minimal DSPy module for raw LM calls without delimiter formatting.

    This module provides the lightest-weight wrapper around LM calls while
    still enabling DSPy features like streaming, cost tracking, and retries.
    Unlike dspy.Predict which adds ~300-400 chars of delimiter formatting,
    this module passes messages directly to the LM.

    Benefits:
    - Minimal prompt overhead (no [[ ## field ## ]] delimiters)
    - Full streaming support via dspy.streamify()
    - Cost tracking and usage stats
    - Retry logic and error handling
    - Works with all DSPy infrastructure

    Usage:
        raw = RawModule(system_prompt="You are helpful")
        result = raw(user_message="Hello", history="")
    """

    def __init__(self, system_prompt: str = ""):
        """
        Initialize raw module.

        Args:
            system_prompt: System prompt to prepend to all conversations
        """
        super().__init__()
        self.system_prompt = system_prompt

    def forward(self, system_prompt: str, history, user_message: str, **kwargs):
        """
        Forward pass with minimal formatting.

        Args:
            system_prompt: System prompt (overrides init if provided)
            history: Conversation history (dspy.History, TactusHistory, or string)
            user_message: Current user message
            **kwargs: Additional args passed to LM

        Returns:
            dspy.Prediction with response field
        """
        # Use provided system_prompt or fall back to init value
        sys_prompt = system_prompt or self.system_prompt

        # Build messages array for direct LM call
        messages = []

        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        # Handle history - could be History object or string
        if history:
            # Check if it's a dspy.History or similar object
            if hasattr(history, 'messages'):
                # It's a History object - get the messages list
                history_messages = history.messages if isinstance(history.messages, list) else []
                messages.extend(history_messages)
            elif isinstance(history, str) and history.strip():
                # It's a formatted string - parse it
                for line in history.strip().split("\n"):
                    if line.startswith("User: "):
                        messages.append({"role": "user", "content": line[6:]})
                    elif line.startswith("Assistant: "):
                        messages.append({"role": "assistant", "content": line[11:]})

        # Add current user message
        if user_message:
            messages.append({"role": "user", "content": user_message})

        # Call LM directly through DSPy's infrastructure
        # This gives us streaming, retries, callbacks, etc.
        lm = dspy.settings.lm
        if lm is None:
            raise RuntimeError("No LM configured. Call dspy.configure(lm=...) first.")

        # Make the call - LM handles streaming automatically if enabled
        response = lm(messages=messages, **kwargs)

        # LM returns a list of strings - take the first one
        response_text = response[0] if isinstance(response, list) else str(response)

        # Return as Prediction for DSPy compatibility and streaming support
        return dspy.Prediction(response=response_text)


class TactusModule:
    """
    A Tactus wrapper around DSPy modules.

    This class creates callable DSPy modules based on the specified strategy.
    It handles both string and structured signatures and supports different
    DSPy module strategies.

    Supported strategies:
    - "predict": Uses dspy.Predict for direct prediction
    - "chain_of_thought": Uses dspy.ChainOfThought for reasoning
    - "react": Uses dspy.ReAct for reasoning + action (coming in Step 5.1)
    - "program_of_thought": Uses dspy.ProgramOfThought (coming in Step 5.2)
    """

    def __init__(
        self,
        name: str,
        signature: Union[str, Dict[str, Any], dspy.Signature],
        strategy: str = "predict",
        input_schema: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ):
        """
        Initialize a Tactus Module.

        Args:
            name: Name for this module (used for tracking/optimization)
            signature: Either a string ("question -> answer"), a dict with
                      input/output definitions, or a DSPy Signature
            strategy: The DSPy module strategy to use ("predict", "chain_of_thought")
            input_schema: Optional explicit input schema (derived from signature if not provided)
            output_schema: Optional explicit output schema (derived from signature if not provided)
            **kwargs: Additional configuration passed to the DSPy module
        """
        self.name = name
        self.strategy = strategy
        self.kwargs = kwargs

        # Resolve signature
        if isinstance(signature, str) or isinstance(signature, dict):
            self.signature = create_signature(signature)
        else:
            self.signature = signature

        # Store explicit schemas or derive from signature
        self.input_schema = input_schema or self._derive_input_schema()
        self.output_schema = output_schema or self._derive_output_schema()

        # Create the DSPy module based on strategy
        self.module = self._create_module()

    def _derive_input_schema(self) -> Dict[str, Any]:
        """Derive input schema from the DSPy signature."""
        schema = {}
        if hasattr(self.signature, "input_fields"):
            for field_name, field_info in self.signature.input_fields.items():
                schema[field_name] = {
                    "type": "string",
                    "required": True,
                    "description": getattr(field_info, "description", None) or field_name,
                }
        return schema

    def _derive_output_schema(self) -> Dict[str, Any]:
        """Derive output schema from the DSPy signature."""
        schema = {}
        if hasattr(self.signature, "output_fields"):
            for field_name, field_info in self.signature.output_fields.items():
                schema[field_name] = {
                    "type": "string",
                    "required": True,
                    "description": getattr(field_info, "description", None) or field_name,
                }
        return schema

    def _create_module(self) -> dspy.Module:
        """Create the appropriate DSPy module based on strategy.

        Passes through any extra kwargs to the DSPy module constructor,
        allowing access to DSPy-specific options like temperature, max_tokens,
        rationale_field (for ChainOfThought), etc.
        """
        if self.strategy == "predict":
            return dspy.Predict(self.signature, **self.kwargs)
        elif self.strategy == "chain_of_thought":
            return dspy.ChainOfThought(self.signature, **self.kwargs)
        elif self.strategy == "raw":
            # Raw module for minimal formatting - no signature needed
            # Extract system_prompt from signature if it was a string
            system_prompt = ""
            if isinstance(self.signature, str):
                # String signature might contain system prompt info
                # For now, system_prompt will come from agent config
                pass
            return RawModule(system_prompt=system_prompt)
        elif self.strategy == "react":
            # ReAct requires tools - will be implemented in Step 5.1
            raise NotImplementedError("ReAct strategy not yet implemented. Coming in Step 5.1.")
        elif self.strategy == "program_of_thought":
            # ProgramOfThought - will be implemented in Step 5.2
            raise NotImplementedError(
                "ProgramOfThought strategy not yet implemented. Coming in Step 5.2."
            )
        else:
            raise ValueError(
                f"Unknown strategy '{self.strategy}'. Supported: predict, chain_of_thought, raw"
            )

    def __call__(self, **kwargs: Any) -> dspy.Prediction:
        """
        Execute the module with the given inputs.

        Args:
            **kwargs: Input values matching the signature's input fields

        Returns:
            A DSPy Prediction object with output fields accessible as attributes
        """
        return self.module(**kwargs)


def create_module(
    name: str,
    config: Dict[str, Any],
    registry: Any = None,
    mock_manager: Any = None,
) -> "LuaCallableModule":
    """
    Create a Tactus Module from configuration.

    This is the main entry point used by the DSL stubs.

    Args:
        name: Name for the module
        config: Configuration dict with:
            - signature: String or structured signature definition
            - strategy: Module strategy (default: "predict")
            - input: Optional explicit input schema
            - output: Optional explicit output schema
            - Other optional configuration
        registry: Optional Registry instance for accessing mocks
        mock_manager: Optional MockManager instance for checking mocks

    Returns:
        A Lua-callable wrapper around a TactusModule instance
    """
    signature = config.get("signature")
    if signature is None:
        raise ValueError(
            f"Module '{name}' requires a 'signature'. Example: signature = \"question -> answer\""
        )

    strategy = config.get("strategy", "predict")

    # Extract optional input/output schemas
    input_schema = config.get("input")
    output_schema = config.get("output")

    # Extract any additional kwargs (excluding known fields)
    known_fields = {"signature", "strategy", "input", "output"}
    extra_kwargs = {k: v for k, v in config.items() if k not in known_fields}

    module = TactusModule(
        name=name,
        signature=signature,
        strategy=strategy,
        input_schema=input_schema,
        output_schema=output_schema,
        **extra_kwargs,
    )

    # Wrap in Lua-callable wrapper with mocking support
    return LuaCallableModule(module, registry=registry, mock_manager=mock_manager)


class LuaCallableModule:
    """
    Wrapper that makes TactusModule callable from Lua with mocking support.

    In Lua, you call a module like: qa({question = "What is 2+2?"})
    This passes a table as a single positional argument.

    This wrapper:
    1. Checks if the module is mocked (via Mocks {})
    2. If mocked, returns the mock response
    3. Otherwise, converts the input table to Python **kwargs for TactusModule.__call__
    """

    def __init__(self, module: TactusModule, registry: Any = None, mock_manager: Any = None):
        self.module = module
        self.registry = registry
        self.mock_manager = mock_manager

    @property
    def signature(self):
        """Expose the underlying module's signature for introspection."""
        return self.module.signature

    @property
    def name(self):
        """Expose the underlying module's name."""
        return self.module.name

    @property
    def strategy(self):
        """Expose the underlying module's strategy."""
        return self.module.strategy

    @property
    def input_schema(self):
        """Expose the underlying module's input schema."""
        return self.module.input_schema

    @property
    def output_schema(self):
        """Expose the underlying module's output schema."""
        return self.module.output_schema

    def __call__(self, inputs: Dict[str, Any]) -> Union[dspy.Prediction, Dict[str, Any]]:
        """
        Execute the module with inputs from a Lua table.

        Args:
            inputs: Dictionary of input values (from Lua table)

        Returns:
            A DSPy Prediction object or mock response dict
        """
        # Check for mock first
        if self.mock_manager and self.registry:
            mock_response = self._get_mock_response(inputs)
            if mock_response is not None:
                # Return mock response wrapped as a dict
                # (DSPy Prediction fields are accessed as attributes, but we can return a dict from mocks)
                return mock_response

        # No mock - call real DSPy module
        return self.module(**inputs)

    def _get_mock_response(self, inputs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Check if this module has a mock configured and return mock response.

        Uses the same mock logic as tools: static (returns), temporal, and conditional.

        Args:
            inputs: The input arguments to the module

        Returns:
            Mock response dict if mocked, None otherwise
        """
        module_name = self.module.name

        # Check if module has a mock in the registry
        if module_name not in self.registry.mocks:
            return None

        # Use mock_manager to get the response (handles static/temporal/conditional logic)
        try:
            return self.mock_manager.get_mock_response(module_name, inputs)
        except Exception:
            # If mock_manager throws an error (e.g., error simulation), let it propagate
            raise
