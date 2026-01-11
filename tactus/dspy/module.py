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
    Minimal DSPy module for raw LM calls without formatting delimiters.

    This module calls the LM directly without using dspy.Predict, eliminating
    the formatting delimiters like [[ ## response ## ]] that Predict adds.

    Key features:
    - No DSPy formatting delimiters in output
    - Works correctly with dspy.streamify() for streaming
    - Maintains DSPy's optimization and tracing capabilities
    - Supports dynamic signatures (with or without tool_calls)

    Usage:
        # Without tools
        raw = RawModule(signature="system_prompt, history, user_message -> response")
        result = raw(user_message="Hello", history="")

        # With tools
        raw = RawModule(signature="system_prompt, history, user_message, available_tools -> response, tool_calls")
        result = raw(user_message="Hello", history="", available_tools="...")
    """

    def __init__(
        self,
        signature: str = "system_prompt, history, user_message -> response",
        system_prompt: str = "",
    ):
        """
        Initialize raw module.

        Args:
            signature: DSPy signature string defining inputs and outputs
            system_prompt: System prompt to prepend to all conversations
        """
        super().__init__()
        self.system_prompt = system_prompt
        self.signature = signature
        # Parse signature to determine output fields
        self.output_fields = self._parse_output_fields(signature)

    def _parse_output_fields(self, signature: str) -> list:
        """Extract output field names from signature string."""
        if "->" not in signature:
            return ["response"]
        output_part = signature.split("->")[1].strip()
        return [field.strip() for field in output_part.split(",")]

    def forward(
        self, system_prompt: str, history, user_message: str, available_tools: str = "", **kwargs
    ):
        """
        Forward pass with direct LM call (no formatting delimiters).

        Args:
            system_prompt: System prompt (overrides init if provided)
            history: Conversation history (dspy.History, TactusHistory, or string)
            user_message: Current user message
            available_tools: Optional tools description (for agents with tools)
            **kwargs: Additional args passed to LM

        Returns:
            dspy.Prediction with response field (and tool_calls if signature includes it)
        """
        # Use provided system_prompt or fall back to init value
        sys_prompt = system_prompt or self.system_prompt

        # Build messages array for direct LM call
        messages = []

        # Add system prompt if provided
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})

        # Add history messages
        if history:
            if hasattr(history, "messages"):
                # It's a History object - use messages directly
                messages.extend(history.messages)
            elif isinstance(history, str) and history.strip():
                # It's a formatted string - parse it
                for line in history.strip().split("\n"):
                    if line.startswith("User: "):
                        messages.append({"role": "user", "content": line[6:]})
                    elif line.startswith("Assistant: "):
                        messages.append({"role": "assistant", "content": line[11:]})

        # Add current user message
        if user_message:
            # If tools are available, include them in the user message
            if available_tools and "available_tools" in self.signature:
                user_content = f"{user_message}\n\nAvailable tools:\n{available_tools}"
                messages.append({"role": "user", "content": user_content})
            else:
                messages.append({"role": "user", "content": user_message})

        # Get the configured LM
        lm = dspy.settings.lm
        if lm is None:
            raise RuntimeError("No LM configured. Call dspy.configure(lm=...) first.")

        # Call LM directly - streamify() will intercept this call if streaming is enabled
        response = lm(messages=messages, **kwargs)

        # Extract response text from LM result
        # LM returns a list of strings - take the first one
        response_text = response[0] if isinstance(response, list) else str(response)

        # Build prediction result based on signature
        prediction_kwargs = {"response": response_text}

        # If signature includes tool_calls, add a placeholder
        # (Real tool call parsing would happen here in a full implementation)
        if "tool_calls" in self.output_fields:
            prediction_kwargs["tool_calls"] = "No tools were used."

        # Return as Prediction for DSPy compatibility
        return dspy.Prediction(**prediction_kwargs)


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
            # Raw module for minimal formatting
            # Pass the signature so RawModule can support tool_calls when needed
            if isinstance(self.signature, str):
                signature_str = self.signature
            else:
                # It's a DSPy Signature object - reconstruct the signature string
                # from input_fields and output_fields
                input_names = list(self.signature.input_fields.keys())
                output_names = list(self.signature.output_fields.keys())
                signature_str = f"{', '.join(input_names)} -> {', '.join(output_names)}"
            return RawModule(signature=signature_str, system_prompt="")
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
