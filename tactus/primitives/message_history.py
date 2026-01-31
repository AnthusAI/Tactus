"""
MessageHistory primitive for managing conversation history.

Provides Lua-accessible methods for manipulating message history,
aligned with pydantic-ai's message_history concept.
"""

from typing import Any, Optional

try:
    from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart
except ImportError:
    # Fallback types if pydantic_ai not available
    ModelMessage = dict
    ModelRequest = dict
    ModelResponse = dict
    TextPart = dict


class MessageHistoryPrimitive:
    """
    Primitive for managing conversation message history.

    Aligned with pydantic-ai's message_history concept.

    Provides methods to:
    - Append messages to history
    - Inject system messages
    - Clear history
    - Access full history
    - Save/load message history state
    """

    def __init__(self, message_history_manager=None, agent_name: Optional[str] = None):
        """
        Initialize MessageHistory primitive.

        Args:
            message_history_manager: MessageHistoryManager instance
            agent_name: Name of the agent this message history belongs to
        """
        self.message_history_manager = message_history_manager
        self.agent_name = agent_name

    def append(self, message_payload: dict[str, Any]) -> None:
        """
        Append a message to the message history.

        Args:
            message_payload: dict with 'role' and 'content' keys
                         role: 'user', 'assistant', 'system'
                         content: message text

        Example:
            MessageHistory.append({role = "user", content = "Hello"})
        """
        if not self.message_history_manager:
            return

        message_payload = self._normalize_message_payload(message_payload)
        role = message_payload.get("role", "user")
        content = message_payload.get("content", "")

        # Create a message dict and preserve extra fields
        message_entry = dict(message_payload)
        message_entry["role"] = role
        message_entry["content"] = content

        self.message_history_manager.add_message(self.agent_name, message_entry)

    def inject_system(self, text: str) -> None:
        """
        Inject a system message into the message history.

        This is useful for providing context or instructions
        for the next agent turn.

        Args:
            text: System message content

        Example:
            MessageHistory.inject_system("Focus on security implications")
        """
        self.append({"role": "system", "content": text})

    def clear(self) -> None:
        """
        Clear the message history for this agent.

        Example:
            MessageHistory.clear()
        """
        if not self.message_history_manager:
            return
        if self.agent_name:
            self.message_history_manager.clear_agent_history(self.agent_name)
        else:
            self.message_history_manager.clear_shared_history()

    def get(self) -> list[dict[str, Any]]:
        """
        Get the full message history for this agent.

        Aligned with pydantic-ai's message_history concept.

        Returns:
            List of message dicts with 'role' and 'content' keys

        Example:
            local messages = MessageHistory.get()
            for i, msg in ipairs(messages) do
                Log.info(msg.role .. ": " .. msg.content)
            end
        """
        if not self.message_history_manager:
            return []
        messages = self._get_history_ref()

        # Convert to Lua-friendly format
        result: list[dict[str, Any]] = []
        for message in messages:
            serialized_message = self._serialize_message(message)
            result.append(serialized_message)

        return result

    def replace(self, messages: list[Any]) -> None:
        """
        Replace the current message history with a new list.

        Args:
            messages: List of message dicts to set as the new history
        """
        if not self.message_history_manager:
            return

        normalized_messages = self._normalize_messages(messages)
        normalized_messages = [
            self.message_history_manager._ensure_message_metadata(message)
            for message in normalized_messages
        ]

        if self.agent_name:
            self.message_history_manager.histories[self.agent_name] = normalized_messages
        else:
            self.message_history_manager.shared_history = normalized_messages

    def reset(self, options: Optional[dict[str, Any]] = None) -> None:
        """
        Reset history while optionally keeping leading system messages.

        Args:
            options: Optional dict with keep mode:
                - "system_prefix" (default): keep leading system messages only
                - "system_all": keep all system messages
                - "none": clear all messages
        """
        if not self.message_history_manager:
            return

        keep_mode = "system_prefix"
        normalized_options = self._normalize_options(options)
        if normalized_options:
            keep_mode = normalized_options.get("keep", keep_mode)
        elif isinstance(options, str):
            keep_mode = options

        messages = self._get_history_ref()

        if keep_mode == "none":
            self.replace([])
            return
        if keep_mode == "system_all":
            system_messages = self.message_history_manager._filter_by_role(messages, "system")
            self.replace(system_messages)
            return

        system_prefix_messages = self.message_history_manager._filter_system_prefix(messages)
        self.replace(system_prefix_messages)

    def head(self, n: int) -> list[dict[str, Any]]:
        """Return the first N messages without mutating history."""
        if not self.message_history_manager:
            return []
        messages = self._get_history_ref()
        limit = max(int(n or 0), 0)
        return self._serialize_messages(messages[:limit])

    def tail(self, n: int) -> list[dict[str, Any]]:
        """Return the last N messages without mutating history."""
        if not self.message_history_manager:
            return []
        messages = self._get_history_ref()
        limit = max(int(n or 0), 0)
        return self._serialize_messages(messages[-limit:] if limit > 0 else [])

    def slice(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        """Return a slice of messages using 1-based start/stop indices."""
        if not self.message_history_manager:
            return []
        normalized_options = self._normalize_options(options)
        if not normalized_options:
            return []
        messages = self._get_history_ref()
        start = normalized_options.get("start")
        stop = normalized_options.get("stop")
        start_index = max(int(start or 1) - 1, 0)
        stop_index = int(stop) if stop is not None else None
        sliced = messages[start_index:stop_index]
        return self._serialize_messages(sliced)

    def tail_tokens(
        self, max_tokens: int, options: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Return the last messages that fit within the token budget."""
        if not self.message_history_manager:
            return []
        messages = self._get_history_ref()
        token_filtered_messages = self.message_history_manager._filter_tail_tokens(
            messages, max_tokens
        )
        return self._serialize_messages(token_filtered_messages)

    def keep_head(self, n: int) -> None:
        """Keep only the first N messages."""
        if not self.message_history_manager:
            return
        messages = self._get_history_ref()
        limit = max(int(n or 0), 0)
        self.replace(messages[:limit])

    def keep_tail(self, n: int) -> None:
        """Keep only the last N messages."""
        if not self.message_history_manager:
            return
        messages = self._get_history_ref()
        limit = max(int(n or 0), 0)
        self.replace(messages[-limit:] if limit > 0 else [])

    def keep_tail_tokens(self, max_tokens: int, options: Optional[dict[str, Any]] = None) -> None:
        """Keep only the last messages that fit within the token budget."""
        if not self.message_history_manager:
            return
        messages = self._get_history_ref()
        token_filtered_messages = self.message_history_manager._filter_tail_tokens(
            messages, max_tokens
        )
        self.replace(token_filtered_messages)

    def rewind(self, n: int) -> None:
        """Remove the last N messages from history."""
        if not self.message_history_manager:
            return
        messages = self._get_history_ref()
        count = max(int(n or 0), 0)
        if count <= 0:
            return
        self.replace(messages[:-count])

    def rewind_to(self, message_id: Any) -> None:
        """Rewind history back to a message id or checkpoint name."""
        if not self.message_history_manager:
            return

        target_message_id = message_id
        if isinstance(message_id, str):
            checkpoint_id = self.message_history_manager.get_checkpoint(message_id)
            target_message_id = checkpoint_id if checkpoint_id is not None else message_id

        try:
            target_message_id = int(target_message_id)
        except (TypeError, ValueError):
            return

        messages = self._get_history_ref()
        for index, message in enumerate(messages):
            message_id_value = (
                message.get("id") if isinstance(message, dict) else getattr(message, "id", None)
            )
            if message_id_value == target_message_id:
                self.replace(messages[: index + 1])
                return

    def checkpoint(self, name: Optional[str] = None) -> Optional[int]:
        """Return the id of the last message and optionally store a named checkpoint."""
        if not self.message_history_manager:
            return None

        messages = self._get_history_ref()
        if not messages:
            return None

        last_message = messages[-1]
        if isinstance(last_message, dict):
            last_message = self.message_history_manager._ensure_message_metadata(last_message)
            message_id = last_message.get("id")
        else:
            message_id = getattr(last_message, "id", None)

        if isinstance(name, str) and message_id is not None:
            self.message_history_manager.record_checkpoint(name, message_id)

        return message_id

    def _get_history_ref(self) -> list[Any]:
        """Get a direct reference to the underlying history list."""
        if not self.message_history_manager:
            return []
        if self.agent_name:
            return self.message_history_manager.histories.setdefault(self.agent_name, [])
        return self.message_history_manager.shared_history

    def _serialize_messages(self, messages: list[Any]) -> list[dict[str, Any]]:
        """Serialize message objects to Lua-friendly dicts."""
        result: list[dict[str, Any]] = []
        for message in messages:
            result.append(self._serialize_message(message))
        return result

    def _normalize_messages(self, messages: Any) -> list[Any]:
        """Normalize Python lists or Lua tables into a list of message dicts."""
        if messages is None:
            return []
        if isinstance(messages, list):
            return messages
        if isinstance(messages, tuple):
            return list(messages)
        if hasattr(messages, "items"):
            items = list(messages.items())
            if items and all(isinstance(key, int) for key, _ in items):
                items.sort(key=lambda pair: pair[0])
            return [value for _, value in items]
        return list(messages)

    def _normalize_message_payload(self, message_payload: Any) -> dict[str, Any]:
        """Normalize a single message payload into a dict."""
        if message_payload is None:
            return {}
        if isinstance(message_payload, dict):
            return message_payload
        if hasattr(message_payload, "items"):
            try:
                return dict(message_payload.items())
            except Exception:
                pass
        return {"role": "user", "content": str(message_payload)}

    def _normalize_message_data(self, message_data: Any) -> dict[str, Any]:
        """Compatibility alias for existing tests and external callers."""
        return self._normalize_message_payload(message_data)

    def _normalize_options(self, options: Any) -> dict[str, Any]:
        """Normalize options from Lua tables or dicts."""
        if options is None:
            return {}
        if isinstance(options, dict):
            return options
        if hasattr(options, "items"):
            try:
                return dict(options.items())
            except Exception:
                return {}
        return {}

    def _serialize_message(self, message: Any) -> dict[str, Any]:
        """Serialize a single message into a Lua-friendly dict."""
        if isinstance(message, dict):
            message = self.message_history_manager._ensure_message_metadata(message)
            serialized = dict(message)
            serialized["role"] = str(serialized.get("role", ""))
            serialized["content"] = str(serialized.get("content", ""))
            return serialized

        # Handle pydantic_ai ModelMessage objects
        try:
            serialized = {"role": getattr(message, "role", "")}
            serialized["content"] = str(getattr(message, "content", ""))
            message_id = getattr(message, "id", None)
            if message_id is not None:
                serialized["id"] = message_id
            created_at = getattr(message, "created_at", None)
            if created_at is not None:
                serialized["created_at"] = created_at
            return serialized
        except Exception:
            # Fallback: convert to string
            return {"role": "unknown", "content": str(message)}

    def load_from_node(self, node: Any) -> None:
        """
        Load message history from a graph node.

        Not yet implemented - placeholder for future graph support.

        Args:
            node: Graph node containing saved message history
        """
        # TODO: Implement when graph primitives are added
        pass

    def save_to_node(self, node: Any) -> None:
        """
        Save message history to a graph node.

        Not yet implemented - placeholder for future graph support.

        Args:
            node: Graph node to save message history to
        """
        # TODO: Implement when graph primitives are added
        pass
