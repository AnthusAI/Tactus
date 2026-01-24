"""
ExtractPrimitive - Smart information extraction with built-in retry and validation.

This primitive wraps the extraction infrastructure to provide:
- Automatic retry with conversational feedback
- JSON schema validation
- Type coercion for extracted fields
- Structured result format
"""

import logging
from typing import Any, Dict

from ..core.base import BaseExtractor, ExtractorFactory
from ..core.models import ExtractorResult
from .llm import LLMExtractor

logger = logging.getLogger(__name__)

__all__ = ["ExtractPrimitive", "ExtractHandle", "ExtractorResult"]

# Register the LLM extractor as the default method
ExtractorFactory.register("llm", LLMExtractor)


class ExtractHandle:
    """
    A reusable extractor handle for Lua interop.

    This is a wrapper around a BaseExtractor that handles
    Lua table conversion.

    Created by Extract { ... } and can be called multiple times.
    """

    def __init__(
        self,
        extractor: BaseExtractor,
        lua_table_from: Any = None,
    ):
        """
        Initialize ExtractHandle.

        Args:
            extractor: The underlying BaseExtractor instance
            lua_table_from: Function to convert Python dicts to Lua tables
        """
        self._extractor = extractor
        self.lua_table_from = lua_table_from

        # Expose extractor attributes
        self.fields = extractor.fields

        # For test access
        self._agent = getattr(extractor, "_agent", None)

    def __call__(self, input_value: Any) -> ExtractorResult:
        """
        Extract from the input.

        Args:
            input_value: Input text or dict with 'text' field

        Returns:
            ExtractorResult with fields dict and validation info
        """
        # Extract text from input
        if isinstance(input_value, dict):
            text = input_value.get("text") or input_value.get("input") or str(input_value)
        else:
            text = str(input_value)

        return self._extractor.extract(text)

    def reset(self):
        """Reset the extractor state."""
        self._extractor.reset()

    @property
    def total_calls(self) -> int:
        """Get total number of calls made."""
        return getattr(self._extractor, "total_calls", 0)

    @property
    def total_retries(self) -> int:
        """Get total number of retries."""
        return getattr(self._extractor, "total_retries", 0)

    def __repr__(self) -> str:
        return f"ExtractHandle(extractor={self._extractor})"


class ExtractPrimitive:
    """
    Smart extraction primitive with retry logic.

    Follows the Agent pattern - can be configured once and called multiple times,
    or used as a one-shot extractor.

    Example usage in Lua:
        -- One-shot extraction
        data = Extract {
            fields = {name = "string", age = "number", email = "string"},
            prompt = "Extract customer information",
            input = transcript
        }
        -- data.name = "John Smith"
        -- data.age = 34
        -- data.email = "john@example.com"

        -- Reusable extractor
        customer_extractor = Extract {
            fields = {name = "string", age = "number"},
            prompt = "Extract customer information"
        }
        data1 = customer_extractor(text1)
        data2 = customer_extractor(text2)
    """

    def __init__(
        self,
        agent_factory: Any,
        lua_table_from: Any = None,
        registry: Any = None,
        mock_manager: Any = None,
    ):
        """
        Initialize ExtractPrimitive.

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
        Create an extractor from configuration.

        This is called when Lua does: Extract { ... }

        Args:
            config: Extraction configuration
                - fields: Dict mapping field names to types (required)
                - prompt: Extraction instruction (required)
                - input: Optional input for one-shot extraction
                - method: Extraction method ("llm", default: "llm")
                - max_retries: Maximum retry attempts (default: 3)
                - temperature: Model temperature (default: 0.3)
                - model: Model to use (optional)
                - strict: Whether all fields are required (default: True)

        Returns:
            ExtractHandle if no input provided (reusable)
            dict if input provided (one-shot result)
        """
        # Convert Lua table to Python dict
        config = self._lua_to_python(config)

        # Validate required fields
        fields = config.get("fields")
        if not fields:
            raise ValueError("Extract requires 'fields' field")

        prompt = config.get("prompt")
        if not prompt:
            raise ValueError("Extract requires 'prompt' field")

        # Create the extractor using the factory
        extractor = self._create_extractor(config)

        # Wrap in handle for Lua interop
        handle = ExtractHandle(
            extractor=extractor,
            lua_table_from=self.lua_table_from,
        )

        # If input is provided, do one-shot extraction
        input_text = config.get("input")
        if input_text is not None:
            result = handle(input_text)
            # Return extracted fields as a flat dict for Lua convenience
            return self._to_lua_table(result.to_lua_dict())

        return handle

    def _create_extractor(self, config: Dict[str, Any]) -> BaseExtractor:
        """
        Create an extractor based on configuration.

        Args:
            config: Configuration dict

        Returns:
            BaseExtractor instance
        """
        method = config.get("method", "llm")

        if method == "llm":
            return LLMExtractor(
                fields=config["fields"],
                prompt=config["prompt"],
                agent_factory=self.agent_factory,
                max_retries=config.get("max_retries", 3),
                temperature=config.get("temperature", 0.3),
                model=config.get("model"),
                strict=config.get("strict", True),
                name=config.get("name"),
            )
        else:
            # Use the factory for other methods
            factory_config = {**config, "agent_factory": self.agent_factory}
            return ExtractorFactory.create(factory_config)

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
