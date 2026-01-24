"""
ClassifyPrimitive - Smart classification with built-in retry and validation.

This primitive wraps the classification infrastructure to provide:
- Automatic retry with conversational feedback
- Output validation against valid classes
- Confidence extraction from response or logprobs
- Structured result format (value, confidence, explanation)

The primitive supports multiple classification methods:
- "llm" (default): LLM-based classification with retry logic
- "fuzzy": String similarity based classification (coming soon)
"""

import logging
from typing import Any, Dict

from ..core.base import BaseClassifier, ClassifierFactory
from ..core.models import ClassifierResult
from .llm import LLMClassifier
from .fuzzy import FuzzyMatchClassifier

__all__ = ["ClassifyPrimitive", "ClassifyHandle", "ClassifierResult"]

logger = logging.getLogger(__name__)

# Register classifier methods with the factory
ClassifierFactory.register("llm", LLMClassifier)
ClassifierFactory.register("fuzzy", FuzzyMatchClassifier)


class ClassifyHandle:
    """
    A reusable classifier handle for Lua interop.

    This is a thin wrapper around a BaseClassifier that handles
    Lua table conversion.

    Created by Classify { ... } and can be called multiple times.
    """

    def __init__(
        self,
        classifier: BaseClassifier,
        lua_table_from: Any = None,
    ):
        """
        Initialize ClassifyHandle.

        Args:
            classifier: The underlying BaseClassifier instance
            lua_table_from: Function to convert Python dicts to Lua tables
        """
        self._classifier = classifier
        self.lua_table_from = lua_table_from

        # Expose classifier attributes
        self.classes = classifier.classes
        self.target_classes = classifier.target_classes

        # For test access
        self._agent = getattr(classifier, "_agent", None)

    def __call__(self, input_value: Any) -> ClassifierResult:
        """
        Classify the input.

        Args:
            input_value: Input text or dict with 'text' field

        Returns:
            ClassifierResult with value, confidence, explanation
        """
        # Extract text from input
        if isinstance(input_value, dict):
            text = input_value.get("text") or input_value.get("input") or str(input_value)
        else:
            text = str(input_value)

        return self._classifier.classify(text)

    def reset(self):
        """Reset the classifier state."""
        self._classifier.reset()

    @property
    def total_calls(self) -> int:
        """Get total number of calls made."""
        return getattr(self._classifier, "total_calls", 0)

    @property
    def total_retries(self) -> int:
        """Get total number of retries."""
        return getattr(self._classifier, "total_retries", 0)

    def __repr__(self) -> str:
        return f"ClassifyHandle(classifier={self._classifier})"


class ClassifyPrimitive:
    """
    Smart classification primitive with retry logic.

    Follows the Agent pattern - can be configured once and called multiple times,
    or used as a one-shot classifier.

    Example usage in Lua:
        -- One-shot classification
        result = Classify {
            classes = {"Yes", "No"},
            prompt = "Did the agent greet the customer?",
            input = transcript
        }

        -- Reusable classifier
        classifier = Classify {
            classes = {"positive", "negative", "neutral"},
            prompt = "What is the sentiment?"
        }
        result1 = classifier(text1)
        result2 = classifier(text2)

        -- With target classes for metrics
        classifier = Classify {
            classes = {"Yes", "No", "NA"},
            target_classes = {"Yes"},
            prompt = "Did the agent comply?"
        }
    """

    def __init__(
        self,
        agent_factory: Any,
        lua_table_from: Any = None,
        registry: Any = None,
        mock_manager: Any = None,
    ):
        """
        Initialize ClassifyPrimitive.

        Args:
            agent_factory: Factory function to create Agent instances
            lua_table_from: Function to convert Python dicts to Lua tables
            registry: Optional registry for accessing mocks
            mock_manager: Optional mock manager for testing
        """
        self.agent_factory = agent_factory
        self.lua_table_from = lua_table_from
        self.registry = registry
        self.mock_manager = mock_manager

    def __call__(self, config: Dict[str, Any]) -> Any:
        """
        Create a classifier from configuration.

        This is called when Lua does: Classify { ... }

        Args:
            config: Classification configuration
                - classes: List of valid classification values (required)
                - prompt: Classification prompt/instruction (required for LLM)
                - input: Optional input for one-shot classification
                - method: Classification method ("llm" or "fuzzy", default: "llm")
                - target_classes: Classes for precision/recall metrics (optional)
                - max_retries: Maximum retry attempts (default: 3)
                - temperature: Model temperature (default: 0.3)
                - model: Model to use (optional)
                - confidence_mode: "heuristic" or "none" (default: "heuristic")

        Returns:
            ClassifyHandle if no input provided (reusable)
            dict if input provided (one-shot result)
        """
        # Convert Lua table to Python dict
        config = self._lua_to_python(config)

        # Debug: log the config
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"[Classify] Received config: {config}")

        method = config.get("method", "llm")

        # Validate required fields based on method
        if method == "llm":
            classes = config.get("classes")
            if not classes:
                raise ValueError("Classify requires 'classes' field")
            prompt = config.get("prompt")
            if not prompt:
                raise ValueError("Classify requires 'prompt' field")
        elif method == "fuzzy":
            # Fuzzy mode can use either 'expected' (binary) or 'classes' (multi-class)
            if not config.get("expected") and not config.get("classes"):
                raise ValueError(
                    "Classify with method='fuzzy' requires either 'expected' "
                    "(for binary Yes/No) or 'classes' (for multi-class matching)"
                )
        else:
            # Unknown method - let factory handle validation
            pass

        # Create the classifier using the factory
        classifier = self._create_classifier(config)

        # Wrap in handle for Lua interop
        handle = ClassifyHandle(
            classifier=classifier,
            lua_table_from=self.lua_table_from,
        )

        # If input is provided, do one-shot classification
        input_text = config.get("input")
        if input_text is not None:
            result = handle(input_text)
            return self._to_lua_table(result.to_dict())

        return handle

    def _create_classifier(self, config: Dict[str, Any]) -> BaseClassifier:
        """
        Create a classifier based on configuration.

        Args:
            config: Configuration dict

        Returns:
            BaseClassifier instance
        """
        method = config.get("method", "llm")

        if method == "llm":
            return LLMClassifier(
                classes=config["classes"],
                prompt=config["prompt"],
                agent_factory=self.agent_factory,
                target_classes=config.get("target_classes"),
                max_retries=config.get("max_retries", 3),
                temperature=config.get("temperature", 0.3),
                model=config.get("model"),
                confidence_mode=config.get("confidence_mode", "heuristic"),
                name=config.get("name"),
            )
        else:
            # Use the factory for other methods
            # Add agent_factory to config for methods that need it
            factory_config = {**config, "agent_factory": self.agent_factory}
            return ClassifierFactory.create(factory_config)

    def _lua_to_python(self, value: Any) -> Any:
        """Convert Lua table to Python dict recursively."""
        if value is None:
            return None

        try:
            from lupa import lua_type

            if lua_type(value) == "table":
                # Check if it's an array (1-indexed sequential keys)
                result = {}
                max_int_key = 0
                has_string_keys = False

                for k, v in value.items():
                    if isinstance(k, int):
                        max_int_key = max(max_int_key, k)
                    else:
                        has_string_keys = True
                    result[k] = self._lua_to_python(v)

                # If all keys are sequential integers 1..n, convert to list
                if not has_string_keys and max_int_key == len(result):
                    return [result[i] for i in range(1, max_int_key + 1)]

                return result
            return value
        except ImportError:
            return value

    def _to_lua_table(self, value: Any) -> Any:
        """Convert Python value to Lua table."""
        if self.lua_table_from is None:
            return value
        if isinstance(value, dict):
            return self.lua_table_from(value)
        return value
