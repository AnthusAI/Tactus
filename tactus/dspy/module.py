"""
DSPy Module integration for Tactus.

This module provides the Module primitive that maps to DSPy modules,
supporting various prediction strategies like Predict, ChainOfThought, etc.
"""

from typing import Any, Dict, Optional, Union

import dspy

from tactus.dspy.signature import create_signature


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
        """Create the appropriate DSPy module based on strategy."""
        if self.strategy == "predict":
            return dspy.Predict(self.signature)
        elif self.strategy == "chain_of_thought":
            return dspy.ChainOfThought(self.signature)
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
                f"Unknown strategy '{self.strategy}'. Supported: predict, chain_of_thought"
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
