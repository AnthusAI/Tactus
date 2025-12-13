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

    def append(self, message_data: dict) -> None:
        """
        Append a message to the message history.

        Args:
            message_data: Dict with 'role' and 'content' keys
                         role: 'user', 'assistant', 'system'
                         content: message text

        Example:
            MessageHistory.append({role = "user", content = "Hello"})
        """
        if not self.message_history_manager or not self.agent_name:
            return

        role = message_data.get("role", "user")
        content = message_data.get("content", "")

        # Create a simple message dict
        message = {"role": role, "content": content}

        self.message_history_manager.add_message(self.agent_name, message)

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
        if not self.message_history_manager or not self.agent_name:
            return

        self.message_history_manager.clear_agent_history(self.agent_name)

    def get(self) -> list:
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
        if not self.message_history_manager or not self.agent_name:
            return []

        messages = self.message_history_manager.histories.get(self.agent_name, [])

        # Convert to Lua-friendly format
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append({"role": msg.get("role", ""), "content": str(msg.get("content", ""))})
            else:
                # Handle pydantic_ai ModelMessage objects
                try:
                    result.append(
                        {
                            "role": getattr(msg, "role", ""),
                            "content": str(getattr(msg, "content", "")),
                        }
                    )
                except Exception:
                    # Fallback: convert to string
                    result.append({"role": "unknown", "content": str(msg)})

        return result

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
