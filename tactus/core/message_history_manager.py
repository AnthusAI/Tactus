"""
Message history management for per-agent conversation histories.

Manages conversation histories with filtering capabilities for
token budgets, message limits, and custom filters.

Aligned with pydantic-ai's message_history concept.
"""

from typing import Any, Optional

try:
    from pydantic_ai.messages import ModelMessage
except ImportError:
    # Fallback if pydantic_ai not available
    ModelMessage = dict

from .registry import MessageHistoryConfiguration


class MessageHistoryManager:
    """Manages per-agent message histories with filtering.

    Aligned with pydantic-ai's message_history concept - this manager
    maintains the message_history lists that get passed to agent.run_sync().
    """

    def __init__(self):
        """Initialize message history manager."""
        self.histories: dict[str, list[ModelMessage]] = {}
        self.shared_history: list[ModelMessage] = []

    def get_history_for_agent(
        self,
        agent_name: str,
        message_history_config: Optional[MessageHistoryConfiguration] = None,
        context: Optional[Any] = None,
    ) -> list[ModelMessage]:
        """
        Get filtered message history for an agent.

        This returns the message_history list that will be passed to
        pydantic-ai's agent.run_sync(message_history=...).

        Args:
            agent_name: Name of the agent
            message_history_config: Message history configuration (source, filter)
            context: Runtime context for filter functions

        Returns:
            List of messages for the agent (message_history for pydantic-ai)
        """
        if message_history_config is None:
            # Default: own history, no filter
            return self.histories.get(agent_name, [])

        # Determine source
        if message_history_config.source == "own":
            messages = self.histories.get(agent_name, [])
        elif message_history_config.source == "shared":
            messages = self.shared_history
        else:
            # Another agent's history
            messages = self.histories.get(message_history_config.source, [])

        # Apply filter if specified
        if message_history_config.filter:
            messages = self._apply_filter(messages, message_history_config.filter, context)

        return messages

    def add_message(
        self,
        agent_name: str,
        message: ModelMessage,
        also_shared: bool = False,
    ) -> None:
        """
        Add a message to an agent's history.

        Args:
            agent_name: Name of the agent
            message: Message to add
            also_shared: Also add to shared history
        """
        if agent_name not in self.histories:
            self.histories[agent_name] = []

        self.histories[agent_name].append(message)

        if also_shared:
            self.shared_history.append(message)

    def clear_agent_history(self, agent_name: str) -> None:
        """Clear an agent's history."""
        self.histories[agent_name] = []

    def clear_shared_history(self) -> None:
        """Clear shared history."""
        self.shared_history = []

    def _apply_filter(
        self,
        messages: list[ModelMessage],
        filter_spec: Any,
        context: Optional[Any],
    ) -> list[ModelMessage]:
        """
        Apply declarative or function filter.

        Args:
            messages: Messages to filter
            filter_spec: Filter specification (tuple or callable)
            context: Runtime context

        Returns:
            Filtered messages
        """
        # If it's a callable (Lua function), call it
        if callable(filter_spec):
            try:
                return filter_spec(messages, context)
            except Exception as e:
                # If filter fails, return unfiltered
                print(f"Warning: Filter function failed: {e}")
                return messages

        # Otherwise it's a tuple (filter_type, filter_arg)
        if not isinstance(filter_spec, tuple) or len(filter_spec) < 2:
            return messages

        filter_type = filter_spec[0]
        filter_arg = filter_spec[1]

        if filter_type == "last_n":
            return self._filter_last_n(messages, filter_arg)
        elif filter_type == "token_budget":
            return self._filter_by_token_budget(messages, filter_arg)
        elif filter_type == "by_role":
            return self._filter_by_role(messages, filter_arg)
        elif filter_type == "compose":
            # Apply multiple filters in sequence
            result = messages
            for f in filter_arg:
                result = self._apply_filter(result, f, context)
            return result
        else:
            # Unknown filter type, return unfiltered
            return messages

    def _filter_last_n(
        self,
        messages: list[ModelMessage],
        n: int,
    ) -> list[ModelMessage]:
        """Keep only the last N messages."""
        return messages[-n:] if n > 0 else []

    def _filter_by_token_budget(
        self,
        messages: list[ModelMessage],
        max_tokens: int,
    ) -> list[ModelMessage]:
        """
        Filter messages to stay within token budget.

        Uses a simple heuristic: ~4 characters per token.
        Keeps most recent messages that fit within budget.
        """
        if max_tokens <= 0:
            return []

        # Rough estimate: 4 chars per token
        max_chars = max_tokens * 4

        result = []
        current_chars = 0

        # Work backwards from most recent
        for message in reversed(messages):
            # Estimate message size
            message_chars = self._estimate_message_chars(message)

            if current_chars + message_chars > max_chars:
                # Would exceed budget, stop here
                break

            result.insert(0, message)
            current_chars += message_chars

        return result

    def _filter_by_role(
        self,
        messages: list[ModelMessage],
        role: str,
    ) -> list[ModelMessage]:
        """Keep only messages with specified role."""
        return [m for m in messages if self._get_message_role(m) == role]

    def _estimate_message_chars(self, message: ModelMessage) -> int:
        """Estimate character count of a message."""
        if isinstance(message, dict):
            # Dict-based message
            content = message.get("content", "")
            if isinstance(content, str):
                return len(content)
            elif isinstance(content, list):
                # Multiple content parts
                total = 0
                for part in content:
                    if isinstance(part, dict):
                        total += len(str(part.get("text", "")))
                    else:
                        total += len(str(part))
                return total
            return len(str(content))
        else:
            # Pydantic AI ModelMessage object
            try:
                # Try to access content attribute
                content = getattr(message, "content", "")
                return len(str(content))
            except Exception:
                # Fallback: convert to string
                return len(str(message))

    def _get_message_role(self, message: ModelMessage) -> str:
        """Get role from a message."""
        if isinstance(message, dict):
            return message.get("role", "")
        else:
            try:
                return getattr(message, "role", "")
            except Exception:
                return ""
