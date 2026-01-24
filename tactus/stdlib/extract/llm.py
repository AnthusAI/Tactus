"""
LLMExtractor - Information extraction using Language Models with retry logic.

This extractor uses an LLM (via agent_factory) to extract structured data from text,
with built-in retry logic and JSON schema validation.
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional

from ..core.base import BaseExtractor
from ..core.models import ExtractorResult

logger = logging.getLogger(__name__)


class LLMExtractor(BaseExtractor):
    """
    LLM-based extractor with automatic retry and validation.

    Uses conversational feedback to help the LLM self-correct when it
    returns invalid or incomplete extractions.

    Example:
        extractor = LLMExtractor(
            fields={"name": "string", "age": "number", "email": "string"},
            prompt="Extract customer information from this text",
            agent_factory=my_agent_factory,
        )
        result = extractor.extract("John Smith is 34 years old. Contact: john@example.com")
        # result.fields = {"name": "John Smith", "age": 34, "email": "john@example.com"}
    """

    def __init__(
        self,
        fields: Dict[str, str],
        prompt: str,
        agent_factory: Callable[[Dict[str, Any]], Any],
        max_retries: int = 3,
        temperature: float = 0.3,
        model: Optional[str] = None,
        strict: bool = True,
        name: Optional[str] = None,
    ):
        """
        Initialize LLMExtractor.

        Args:
            fields: Dict mapping field names to their types
                   (e.g., {"name": "string", "age": "number", "items": "list"})
            prompt: Extraction instruction/prompt
            agent_factory: Factory function to create Agent instances
            max_retries: Maximum retry attempts on invalid output
            temperature: LLM temperature for extraction
            model: Specific model to use (optional)
            strict: If True, all fields must be extracted; if False, missing fields are OK
            name: Optional name for this extractor
        """
        self.fields = fields
        self.name = name
        self.prompt = prompt
        self.agent_factory = agent_factory
        self.max_retries = max_retries
        self.temperature = temperature
        self.model = model
        self.strict = strict

        # Build extraction system prompt
        self._system_prompt = self._build_system_prompt()

        # Create agent for extraction
        self._agent = self._create_agent()

        # Track statistics
        self.total_calls = 0
        self.total_retries = 0

    def _build_system_prompt(self) -> str:
        """Build the extraction system prompt."""
        fields_description = "\n".join(
            f"  - {name}: {type_}" for name, type_ in self.fields.items()
        )

        return f"""You are an information extraction assistant. Your task is to extract structured data according to the following instruction:

{self.prompt}

FIELDS TO EXTRACT:
{fields_description}

IMPORTANT RULES:
1. You MUST respond with a valid JSON object containing the extracted fields.
2. Include ONLY the specified fields in your response.
3. Use null for fields that cannot be extracted from the input.
4. For "number" fields, return numeric values (not strings).
5. For "list" fields, return JSON arrays.
6. For "boolean" fields, return true or false.
7. Do NOT include any explanation or text outside the JSON.

RESPONSE FORMAT:
{{
  "field1": "extracted value",
  "field2": 123,
  ...
}}
"""

    def _create_agent(self) -> Any:
        """Create the internal Agent for extraction."""
        if self.agent_factory is None:
            raise RuntimeError("LLMExtractor requires agent_factory")

        agent_config = {
            "system_prompt": self._system_prompt,
            "temperature": self.temperature,
        }
        if self.model:
            agent_config["model"] = self.model

        return self.agent_factory(agent_config)

    def extract(self, input_text: str) -> ExtractorResult:
        """
        Extract structured data from the input text with retry logic.

        Args:
            input_text: The text to extract from

        Returns:
            ExtractorResult with fields dict and validation info
        """
        self.total_calls += 1

        # Reset agent conversation for fresh extraction
        if hasattr(self._agent, "reset"):
            self._agent.reset()

        retry_count = 0
        last_response = None
        validation_errors = []

        for attempt in range(self.max_retries + 1):
            # Build the message for this attempt
            if attempt == 0:
                message = f"Please extract the following information:\n\n{input_text}"
            else:
                # Retry with feedback
                retry_count += 1
                self.total_retries += 1
                message = self._build_retry_feedback(last_response, validation_errors)
                logger.debug(f"Extraction retry {retry_count}: {message[:100]}...")

            # Call the agent
            try:
                result = self._call_agent(message)
                last_response = result.get("response") or result.get("message") or str(result)
            except Exception as e:
                logger.error(f"Agent call failed: {e}")
                return ExtractorResult(
                    fields={},
                    error=str(e),
                    retry_count=retry_count,
                )

            # Parse the response
            parsed, validation_errors = self._parse_response(last_response)

            # Check if extraction is valid
            if not validation_errors:
                return ExtractorResult(
                    fields=parsed,
                    retry_count=retry_count,
                    raw_response=last_response,
                )

            logger.debug(f"Invalid extraction: {validation_errors}")

        # All retries exhausted
        logger.warning(f"Extraction failed after {self.max_retries} retries")
        return ExtractorResult(
            fields=parsed if "parsed" in dir() else {},
            validation_errors=validation_errors,
            error=f"Max retries ({self.max_retries}) exceeded. Validation errors: {validation_errors}",
            retry_count=retry_count,
            raw_response=last_response,
        )

    def _call_agent(self, message: str) -> Dict[str, Any]:
        """Call the internal agent with a message."""
        input_dict = {"message": message}
        result = self._agent(input_dict)

        # Convert result to dict
        if hasattr(result, "to_dict"):
            return result.to_dict()
        if hasattr(result, "message"):
            return {"response": result.message}
        if hasattr(result, "response"):
            return {"response": result.response}
        if isinstance(result, dict):
            return result

        return {"response": str(result)}

    def _build_retry_feedback(self, last_response: str, errors: List[str]) -> str:
        """Build feedback message for retry."""
        errors_str = "\n".join(f"  - {e}" for e in errors)
        fields_str = ", ".join(f'"{f}"' for f in self.fields.keys())

        return f"""Your previous response was not valid JSON or had validation errors.

Previous response:
{last_response[:500]}

Errors:
{errors_str}

Please respond with ONLY a valid JSON object containing these fields: {fields_str}

Do NOT include any explanation or text outside the JSON object."""

    def _parse_response(self, response: str) -> tuple[Dict[str, Any], List[str]]:
        """
        Parse extraction response and validate against schema.

        Returns:
            Tuple of (extracted_fields, validation_errors)
        """
        if not response:
            return {}, ["Empty response"]

        # Try to extract JSON from response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if not json_match:
            # Try to find JSON with nested braces
            json_match = re.search(r"\{.*\}", response, re.DOTALL)

        if not json_match:
            return {}, ["No JSON object found in response"]

        try:
            parsed = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            return {}, [f"Invalid JSON: {e}"]

        # Validate fields
        validation_errors = []
        result = {}

        for field_name, field_type in self.fields.items():
            if field_name not in parsed:
                if self.strict:
                    validation_errors.append(f"Missing required field: {field_name}")
                result[field_name] = None
            else:
                value = parsed[field_name]
                validated, error = self._validate_field(field_name, value, field_type)
                if error:
                    validation_errors.append(error)
                result[field_name] = validated

        return result, validation_errors

    def _validate_field(
        self, field_name: str, value: Any, field_type: str
    ) -> tuple[Any, Optional[str]]:
        """
        Validate a field value against its type.

        Returns:
            Tuple of (validated_value, error_message or None)
        """
        if value is None:
            return None, None

        type_lower = field_type.lower()

        if type_lower == "string":
            return str(value), None

        elif type_lower == "number":
            if isinstance(value, (int, float)):
                return value, None
            try:
                return float(value), None
            except (ValueError, TypeError):
                return None, f"Field '{field_name}' must be a number, got: {type(value).__name__}"

        elif type_lower == "integer":
            if isinstance(value, int) and not isinstance(value, bool):
                return value, None
            try:
                return int(float(value)), None
            except (ValueError, TypeError):
                return None, f"Field '{field_name}' must be an integer, got: {type(value).__name__}"

        elif type_lower == "boolean":
            if isinstance(value, bool):
                return value, None
            if isinstance(value, str):
                if value.lower() in ("true", "yes", "1"):
                    return True, None
                if value.lower() in ("false", "no", "0"):
                    return False, None
            return None, f"Field '{field_name}' must be a boolean, got: {value}"

        elif type_lower in ("list", "array"):
            if isinstance(value, list):
                return value, None
            return None, f"Field '{field_name}' must be a list, got: {type(value).__name__}"

        elif type_lower in ("dict", "object"):
            if isinstance(value, dict):
                return value, None
            return None, f"Field '{field_name}' must be an object, got: {type(value).__name__}"

        else:
            # Unknown type, accept any value
            return value, None

    def reset(self) -> None:
        """Reset the extractor state (clear agent conversation)."""
        if hasattr(self._agent, "reset"):
            self._agent.reset()

    def __repr__(self) -> str:
        fields_str = ", ".join(self.fields.keys())
        return f"LLMExtractor(fields=[{fields_str}], calls={self.total_calls}, retries={self.total_retries})"
