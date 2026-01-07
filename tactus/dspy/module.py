"""
DSPy Module integration for Tactus.

This module provides the Module primitive that maps to DSPy modules,
supporting various prediction strategies like Predict, ChainOfThought, etc.
"""

from typing import Any, Dict, Union

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
        **kwargs: Any,
    ):
        """
        Initialize a Tactus Module.

        Args:
            name: Name for this module (used for tracking/optimization)
            signature: Either a string ("question -> answer"), a dict with
                      input/output definitions, or a DSPy Signature
            strategy: The DSPy module strategy to use ("predict", "chain_of_thought")
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

        # Create the DSPy module based on strategy
        self.module = self._create_module()

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
                f"Unknown strategy '{self.strategy}'. " f"Supported: predict, chain_of_thought"
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
) -> TactusModule:
    """
    Create a Tactus Module from configuration.

    This is the main entry point used by the DSL stubs.

    Args:
        name: Name for the module
        config: Configuration dict with:
            - signature: String or structured signature definition
            - strategy: Module strategy (default: "predict")
            - Other optional configuration

    Returns:
        A callable TactusModule instance
    """
    signature = config.get("signature")
    if signature is None:
        raise ValueError(
            f"Module '{name}' requires a 'signature'. " f'Example: signature = "question -> answer"'
        )

    strategy = config.get("strategy", "predict")

    # Extract any additional kwargs
    extra_kwargs = {k: v for k, v in config.items() if k not in ("signature", "strategy")}

    return TactusModule(
        name=name,
        signature=signature,
        strategy=strategy,
        **extra_kwargs,
    )
