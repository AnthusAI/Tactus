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
            message: A dict with keys matching the signature fields
                    e.g., {"question": "What is 2+2?", "answer": "4"}
        """
        self._messages.append(message)

    def get(self) -> List[Dict[str, Any]]:
        """
        Get all messages in the history.

        Returns:
            List of message dictionaries
        """
        return self._messages.copy()

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
