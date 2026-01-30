"""
LLMClassifier - Classification using Language Models with retry logic.

This classifier uses an LLM (via agent_factory) to classify text, with built-in
retry logic that provides conversational feedback when the model returns invalid
classifications.
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional

from ..core.base import BaseClassifier
from ..core.models import ClassifierResult

logger = logging.getLogger(__name__)


class LLMClassifier(BaseClassifier):
    """
    LLM-based classifier with automatic retry and validation.

    Uses conversational feedback to help the LLM self-correct when it
    returns invalid classifications.

    Example:
        classifier = LLMClassifier(
            classes=["Yes", "No"],
            prompt="Did the agent greet the customer?",
            agent_factory=my_agent_factory,
        )
        result = classifier.classify("Hello, how can I help you today?")
        # result.value = "Yes"
        # result.confidence = 0.95
    """

    def __init__(
        self,
        classes: List[str],
        prompt: str,
        agent_factory: Callable[[Dict[str, Any]], Any],
        target_classes: Optional[List[str]] = None,
        max_retries: int = 3,
        temperature: float = 0.3,
        model: Optional[str] = None,
        confidence_mode: str = "heuristic",
        name: Optional[str] = None,
    ):
        """
        Initialize LLMClassifier.

        Args:
            classes: List of valid classification values
            prompt: Classification instruction/prompt
            agent_factory: Factory function to create Agent instances
            target_classes: Classes considered "positive" for precision/recall
            max_retries: Maximum retry attempts on invalid output
            temperature: LLM temperature for classification
            model: Specific model to use (optional)
            confidence_mode: "heuristic" or "none"
            name: Optional name for this classifier
        """
        self.classes = classes
        self.target_classes = target_classes or []
        self.name = name
        self.prompt = prompt
        self.agent_factory = agent_factory
        self.max_retries = max_retries
        self.temperature = temperature
        self.model = model
        self.confidence_mode = confidence_mode

        # Build classification system prompt
        self._system_prompt = self._build_system_prompt()

        # Create agent for classification
        self._agent = self._create_agent()

        # Track statistics
        self.total_calls = 0
        self.total_retries = 0

    def _build_system_prompt(self) -> str:
        """Build the classification system prompt."""
        classes_str = ", ".join(f'"{c}"' for c in self.classes)

        return f"""You are a classification assistant. Your task is to classify input according to the following instruction:

{self.prompt}

VALID CLASSIFICATIONS: {classes_str}

IMPORTANT RULES:
1. You MUST respond with EXACTLY one of the valid classifications listed above.
2. Start your response with the classification on its own line.
3. Then provide a brief explanation on the following lines.

RESPONSE FORMAT:
<classification>
<explanation>

Example:
Yes
The text clearly indicates agreement because...
"""

    def _create_agent(self) -> Any:
        """Create the internal Agent for classification."""
        if self.agent_factory is None:
            raise RuntimeError("LLMClassifier requires agent_factory")

        agent_config = {
            "system_prompt": self._system_prompt,
            "temperature": self.temperature,
        }
        # Optional stable name for mocking/traceability. When set, the DSL wrapper
        # renames the internal _temp_agent_* handle so it can be mocked via:
        #   Mocks { <name> = { message = "...", tool_calls = {...} } }
        if self.name:
            agent_config["name"] = self.name
        if self.model:
            agent_config["model"] = self.model

        return self.agent_factory(agent_config)

    def classify(self, input_text: str) -> ClassifierResult:
        """
        Classify the input text with retry logic.

        Args:
            input_text: The text to classify

        Returns:
            ClassifierResult with value, confidence, explanation
        """
        self.total_calls += 1

        # Reset agent conversation for fresh classification
        if hasattr(self._agent, "reset"):
            self._agent.reset()

        retry_count = 0
        last_response = None

        for attempt in range(self.max_retries + 1):
            # Build the message for this attempt
            if attempt == 0:
                message = f"Please classify the following:\n\n{input_text}"
            else:
                # Retry with feedback
                retry_count += 1
                self.total_retries += 1
                message = self._build_retry_feedback(last_response)
                logger.debug(f"Classification retry {retry_count}: {message[:100]}...")

            # Call the agent
            try:
                result = self._call_agent(message)
                last_response = result.get("response") or result.get("message") or str(result)
            except Exception as e:
                logger.error(f"Agent call failed: {e}")
                return ClassifierResult(
                    value="ERROR",
                    error=str(e),
                    retry_count=retry_count,
                )

            # Parse the response
            parsed = self._parse_response(last_response)

            # Check if classification is valid
            if parsed["value"] in self.classes:
                confidence = self._extract_confidence(last_response, parsed["value"])
                return ClassifierResult(
                    value=parsed["value"],
                    confidence=confidence,
                    explanation=parsed["explanation"],
                    retry_count=retry_count,
                    raw_response=last_response,
                )

            logger.debug(f"Invalid classification '{parsed['value']}', retrying...")

        # All retries exhausted
        logger.warning(f"Classification failed after {self.max_retries} retries")
        return ClassifierResult(
            value="ERROR",
            error=f"Max retries ({self.max_retries}) exceeded. Last response: {last_response[:200] if last_response else 'None'}",
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

    def _build_retry_feedback(self, last_response: str) -> str:
        """Build feedback message for retry."""
        classes_str = ", ".join(f'"{c}"' for c in self.classes)
        return f"""Your previous response was not a valid classification.

Previous response: "{last_response[:200]}..."

VALID CLASSIFICATIONS ARE: {classes_str}

Please respond with EXACTLY one of these classifications, followed by your explanation.
Start your response with the classification on its own line."""

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse classification response to extract value and explanation."""
        if not response or not response.strip():
            return {"value": None, "explanation": None}

        lines = response.strip().split("\n")

        # First non-empty line should be the classification
        first_line = lines[0].strip()

        # Clean up common variations
        # Remove markdown formatting, quotes, punctuation
        cleaned = re.sub(r"[\*\"\'\`\:\.]", "", first_line).strip()

        # Check for exact match first
        for cls in self.classes:
            if cleaned.lower() == cls.lower():
                explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else None
                return {"value": cls, "explanation": explanation}

        # Check for prefix match (e.g., "Yes - the agent...")
        for cls in self.classes:
            if cleaned.lower().startswith(cls.lower()):
                explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else None
                return {"value": cls, "explanation": explanation}

        # Check for the classification anywhere in first line
        for cls in self.classes:
            # Only match whole tokens/phrases so we don't accept accidental
            # substrings (e.g., "Unknown" containing "No").
            if re.search(rf"(?i)(?<![A-Za-z0-9_]){re.escape(cls)}(?![A-Za-z0-9_])", cleaned):
                # Make sure it's not a partial match of another class
                is_partial = False
                for other_cls in self.classes:
                    if other_cls != cls and cls.lower() in other_cls.lower():
                        is_partial = True
                        break
                if not is_partial:
                    explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else None
                    return {"value": cls, "explanation": explanation}

        # Could not parse - return raw first line as value
        explanation = "\n".join(lines[1:]).strip() if len(lines) > 1 else None
        return {"value": first_line, "explanation": explanation}

    def _extract_confidence(self, response: str, classification: str) -> Optional[float]:
        """Extract confidence from response using heuristics."""
        if self.confidence_mode == "none":
            return None

        # Heuristic: Look for confidence indicators in the response
        response_lower = response.lower()

        # High confidence indicators
        high_indicators = [
            "definitely",
            "certainly",
            "clearly",
            "obviously",
            "absolutely",
            "100%",
            "very confident",
        ]
        for indicator in high_indicators:
            if indicator in response_lower:
                return 0.95

        # Medium-high confidence
        med_high_indicators = ["likely", "probably", "appears to be", "seems to be", "confident"]
        for indicator in med_high_indicators:
            if indicator in response_lower:
                return 0.80

        # Low confidence indicators
        low_indicators = [
            "possibly",
            "might be",
            "could be",
            "not sure",
            "uncertain",
            "difficult to tell",
        ]
        for indicator in low_indicators:
            if indicator in response_lower:
                return 0.50

        # Default confidence when no indicators found
        return 0.75

    def reset(self) -> None:
        """Reset the classifier state (clear agent conversation)."""
        if hasattr(self._agent, "reset"):
            self._agent.reset()

    def __repr__(self) -> str:
        return f"LLMClassifier(classes={self.classes}, calls={self.total_calls}, retries={self.total_retries})"
