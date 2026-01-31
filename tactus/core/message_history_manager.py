"""
Message history management for per-agent conversation histories.

Manages conversation histories with filtering capabilities for
token budgets, message limits, and custom filters.

Aligned with pydantic-ai's message_history concept.
"""

from datetime import datetime, timezone
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
        self._next_message_id = 1
        self._checkpoints: dict[str, int] = {}

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
            selected_messages = self.histories.get(agent_name, [])
        elif message_history_config.source == "shared":
            selected_messages = self.shared_history
        else:
            # Another agent's history
            selected_messages = self.histories.get(message_history_config.source, [])

        # Apply filter if specified
        if message_history_config.filter:
            selected_messages = self._apply_filter(
                selected_messages, message_history_config.filter, context
            )

        return selected_messages

    def add_message(
        self,
        agent_name: Optional[str],
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
        message = self._ensure_message_metadata(message)

        if agent_name is None:
            self.shared_history.append(message)
            return

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
        filter_specification: Any,
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
        if callable(filter_specification):
            try:
                return filter_specification(messages, context)
            except Exception as exception:
                # If filter fails, return unfiltered
                print(f"Warning: Filter function failed: {exception}")
                return messages

        # Otherwise it's a tuple (filter_type, filter_arg)
        if not isinstance(filter_specification, tuple) or len(filter_specification) < 2:
            return messages

        filter_name = filter_specification[0]
        filter_value = filter_specification[1]

        if filter_name == "last_n":
            return self._filter_last_n(messages, filter_value)
        elif filter_name == "first_n":
            return self._filter_first_n(messages, filter_value)
        elif filter_name == "token_budget":
            return self._filter_by_token_budget(messages, filter_value)
        elif filter_name == "head_tokens":
            return self._filter_head_tokens(messages, filter_value)
        elif filter_name == "tail_tokens":
            return self._filter_tail_tokens(messages, filter_value)
        elif filter_name == "by_role":
            return self._filter_by_role(messages, filter_value)
        elif filter_name == "system_prefix":
            return self._filter_system_prefix(messages)
        elif filter_name == "compose":
            # Apply multiple filters in sequence
            filtered_messages = messages
            for filter_step in filter_value:
                filtered_messages = self._apply_filter(filtered_messages, filter_step, context)
            return filtered_messages
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

    def _filter_first_n(
        self,
        messages: list[ModelMessage],
        n: int,
    ) -> list[ModelMessage]:
        """Keep only the first N messages."""
        return messages[:n] if n > 0 else []

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

        filtered_messages = []
        current_character_count = 0

        # Work backwards from most recent
        for message in reversed(messages):
            # Estimate message size
            message_character_count = self._estimate_message_chars(message)

            if current_character_count + message_character_count > max_chars:
                # Would exceed budget, stop here
                break

            filtered_messages.insert(0, message)
            current_character_count += message_character_count

        return filtered_messages

    def _filter_head_tokens(
        self,
        messages: list[ModelMessage],
        max_tokens: int,
    ) -> list[ModelMessage]:
        """Keep earliest messages that fit within the token budget."""
        if max_tokens <= 0:
            return []

        max_chars = max_tokens * 4
        filtered_messages = []
        current_character_count = 0

        for message in messages:
            message_character_count = self._estimate_message_chars(message)
            if current_character_count + message_character_count > max_chars:
                break
            filtered_messages.append(message)
            current_character_count += message_character_count

        return filtered_messages

    def _filter_tail_tokens(
        self,
        messages: list[ModelMessage],
        max_tokens: int,
    ) -> list[ModelMessage]:
        """Keep latest messages that fit within the token budget."""
        return self._filter_by_token_budget(messages, max_tokens)

    def _filter_by_role(
        self,
        messages: list[ModelMessage],
        role: str,
    ) -> list[ModelMessage]:
        """Keep only messages with specified role."""
        return [m for m in messages if self._get_message_role(m) == role]

    def _filter_system_prefix(
        self,
        messages: list[ModelMessage],
    ) -> list[ModelMessage]:
        """Keep only the leading contiguous system messages."""
        system_prefix_messages: list[ModelMessage] = []
        for message in messages:
            if self._get_message_role(message) != "system":
                break
            system_prefix_messages.append(message)
        return system_prefix_messages

    def _ensure_message_metadata(self, message: ModelMessage) -> ModelMessage:
        """Ensure message has id and created_at metadata when dict-based."""
        if not isinstance(message, dict):
            return message

        if "id" not in message:
            message["id"] = self._next_message_id
            self._next_message_id += 1

        if "created_at" not in message:
            message["created_at"] = datetime.now(timezone.utc).isoformat()

        return message

    def record_checkpoint(self, name: str, message_id: int) -> None:
        """Record a named checkpoint pointing at a message id."""
        self._checkpoints[name] = message_id

    def get_checkpoint(self, name: str) -> Optional[int]:
        """Retrieve a checkpoint id by name."""
        return self._checkpoints.get(name)

    def next_message_id(self) -> int:
        """Return the next message id that will be assigned."""
        return self._next_message_id

    def _estimate_message_chars(self, message: ModelMessage) -> int:
        """Estimate character count of a message."""
        if isinstance(message, dict):
            # Dict-based message
            message_content = message.get("content", "")
            if isinstance(message_content, str):
                return len(message_content)
            elif isinstance(message_content, list):
                # Multiple content parts
                total_character_count = 0
                for part in message_content:
                    if isinstance(part, dict):
                        total_character_count += len(str(part.get("text", "")))
                    else:
                        total_character_count += len(str(part))
                return total_character_count
            return len(str(message_content))
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
