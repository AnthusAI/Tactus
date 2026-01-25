"""
DSPy History integration for Tactus.

This module provides the History primitive that maps to DSPy History,
enabling multi-turn conversation management in Tactus procedures.
"""

from typing import Any, Dict, List, Optional

import dspy


class TactusHistory:
    """
    A Tactus wrapper around DSPy History.

    This class provides a convenient API for managing conversation history
    that can be passed to DSPy Modules. It maintains a list of messages
    and provides methods for adding, retrieving, and clearing messages.

    Example usage in Lua:
        -- Create a history
        local history = History()

        -- Add messages
        history.add({ question = "What is 2+2?", answer = "4" })
        history.add({ question = "And 3+3?", answer = "6" })

        -- Get all messages
        local messages = history.get()

        -- Pass to a Module
        local result = qa_module({ question = "What is 4+4?", history = history })

        -- Clear history
        history.clear()
    """

    def __init__(self, messages: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize a TactusHistory.

        Args:
            messages: Optional initial list of messages
        """
        self._messages: List[Dict[str, Any]] = messages or []

    def add(self, message: Dict[str, Any]) -> None:
        """
        Add a message to the history.

        Args:
            message: A dict with keys 'role' and 'content', or a TactusMessage object
                    e.g., {"role": "user", "content": "What is 2+2?"}
                    e.g., Message {role = "user", content = "What is 2+2?"}

        Raises:
            ValueError: If message lacks required keys or invalid role
        """
        # Check if it's a TactusMessage (has to_dict method)
        if hasattr(message, "to_dict") and callable(message.to_dict):
            message = message.to_dict()
        # Convert Lua tables to dict if needed
        elif hasattr(message, "items"):
            # It's a Lua table or similar mapping
            try:
                message = dict(message.items())
            except (AttributeError, TypeError):
                pass

        # Check for required keys
        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary or TactusMessage")

        if "role" not in message:
            raise ValueError("role is required")

        if "content" not in message:
            raise ValueError("Message must include 'content' key")

        # Validate role
        # Note: "tool" role is required for OpenAI function calling responses
        valid_roles = ["system", "user", "assistant", "tool"]
        if message["role"] not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of {valid_roles}")

        # Convert legacy formats if needed
        if "question" in message and "answer" in message:
            message = {
                "role": "user",
                "content": message.get("question", ""),
            }
        elif "answer" in message:
            message = {
                "role": "assistant",
                "content": message.get("answer", ""),
            }

        self._messages.append(message)

    def get(
        self, context_window: Optional[int] = None, token_limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages from history, optionally filtered by context window and token limit.

        Args:
            context_window: Maximum number of recent messages to retrieve
            token_limit: Maximum number of tokens to include

        Returns:
            List of message dictionaries
        """
        messages = self._messages.copy()

        # Apply context window
        if context_window is not None:
            messages = messages[-context_window:]

        # Simple token estimation (approximation)
        if token_limit is not None:
            token_count = 0
            filtered_messages = []
            for msg in reversed(messages):
                # Basic token estimation: 1 token per 4 characters
                msg_tokens = len(msg.get("content", "")) // 4 + len(msg.get("role", "")) // 4 + 4

                if token_count + msg_tokens <= token_limit:
                    filtered_messages.insert(0, msg)
                    token_count += msg_tokens
                else:
                    break

            messages = filtered_messages

        return messages

    def clear(self) -> None:
        """Clear all messages from the history."""
        self._messages.clear()

    def to_dspy(self) -> dspy.History:
        """
        Convert to a DSPy History object.

        Returns:
            A dspy.History instance suitable for passing to DSPy Modules
        """
        return dspy.History(messages=self._messages)

    def count_tokens(self) -> int:
        """
        Estimate total tokens in the history.

        Returns:
            Estimated token count
        """
        return sum(
            len(msg.get("content", "")) // 4 + len(msg.get("role", "")) // 4 + 4
            for msg in self._messages
        )

    def __len__(self) -> int:
        """Return the number of messages in history."""
        return len(self._messages)

    def __iter__(self):
        """Iterate over messages in history."""
        return iter(self._messages)

    @classmethod
    def from_dspy(cls, dspy_history: dspy.History) -> "TactusHistory":
        """
        Create a TactusHistory from a DSPy History.

        Args:
            dspy_history: A dspy.History instance

        Returns:
            A TactusHistory instance
        """
        return cls(messages=dspy_history.messages)


def create_history(messages: Optional[List[Dict[str, Any]]] = None) -> TactusHistory:
    """
    Create a new TactusHistory.

    This is the main entry point used by the DSL stubs.

    Args:
        messages: Optional initial list of messages

    Returns:
        A TactusHistory instance
    """
    return TactusHistory(messages=messages)
