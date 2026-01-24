"""
Retry with Conversational Feedback

Provides intelligent retry logic that preserves conversation history
and gives the LLM feedback about previous attempts.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryWithFeedback:
    """
    Retry logic with conversational feedback.

    Unlike simple retry, this approach:
    1. Preserves conversation history across attempts
    2. Gives the LLM feedback about why the previous attempt failed
    3. Enables "self-healing" where the LLM learns from mistakes

    This is the core pattern used by Plexus LangGraphScore nodes
    for reliable classification.
    """

    def __init__(
        self,
        max_retries: int = 3,
        on_retry: Optional[Callable[[int, str, str], None]] = None,
    ):
        """
        Initialize retry handler.

        Args:
            max_retries: Maximum number of retry attempts
            on_retry: Optional callback called on each retry (attempt, error, feedback)
        """
        self.max_retries = max_retries
        self.on_retry = on_retry

    def execute(
        self,
        call_fn: Callable[[str], str],
        initial_message: str,
        validate_fn: Callable[[str], bool],
        build_feedback_fn: Callable[[str], str],
    ) -> Dict[str, Any]:
        """
        Execute with retry logic.

        Args:
            call_fn: Function to call the LLM (takes message, returns response)
            initial_message: Initial message to send
            validate_fn: Function to validate response (returns True if valid)
            build_feedback_fn: Function to build feedback message from failed response

        Returns:
            Dict with:
                - response: The successful response (or last failed response)
                - success: Whether validation passed
                - retry_count: Number of retries performed
                - history: List of all (message, response) pairs
        """
        history: List[Dict[str, str]] = []
        retry_count = 0
        current_message = initial_message
        last_response = None

        for attempt in range(self.max_retries + 1):
            # Call the LLM
            response = call_fn(current_message)
            last_response = response

            # Record in history
            history.append({"message": current_message, "response": response})

            # Validate the response
            if validate_fn(response):
                logger.debug(f"Valid response on attempt {attempt + 1}")
                return {
                    "response": response,
                    "success": True,
                    "retry_count": retry_count,
                    "history": history,
                }

            # Response invalid - prepare for retry
            if attempt < self.max_retries:
                retry_count += 1
                feedback = build_feedback_fn(response)
                current_message = feedback

                logger.debug(f"Retry {retry_count}: {feedback[:100]}...")

                if self.on_retry:
                    self.on_retry(retry_count, response, feedback)

        # All retries exhausted
        logger.warning(f"Validation failed after {self.max_retries} retries")
        return {
            "response": last_response,
            "success": False,
            "retry_count": retry_count,
            "history": history,
        }


def create_classification_validator(valid_classes: List[str]) -> Callable[[str], bool]:
    """
    Create a validator function for classification responses.

    Args:
        valid_classes: List of valid classification values

    Returns:
        Validator function that returns True if response contains valid class
    """
    valid_lower = {c.lower() for c in valid_classes}

    def validator(response: str) -> bool:
        if not response:
            return False

        # Check first line for classification
        first_line = response.strip().split("\n")[0].strip().lower()

        # Remove common formatting
        import re

        cleaned = re.sub(r"[\*\"\'\`\:\.]", "", first_line).strip()

        # Check for exact match
        if cleaned in valid_lower:
            return True

        # Check for prefix match
        for cls in valid_lower:
            if cleaned.startswith(cls):
                return True

        return False

    return validator


def create_classification_feedback(valid_classes: List[str]) -> Callable[[str], str]:
    """
    Create a feedback builder for classification retries.

    Args:
        valid_classes: List of valid classification values

    Returns:
        Function that builds feedback message from failed response
    """
    classes_str = ", ".join(f'"{c}"' for c in valid_classes)

    def build_feedback(response: str) -> str:
        return f"""Your previous response was not a valid classification.

Your response: "{response[:200]}..."

VALID CLASSIFICATIONS ARE: {classes_str}

Please respond with EXACTLY one of these classifications on the first line, followed by your explanation.
Do not include any other text on the first line."""

    return build_feedback
