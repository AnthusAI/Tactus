"""
Session primitive for managing conversation history.

Provides Lua-accessible methods for manipulating chat session state.
"""

from typing import Any, Optional

try:
    from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart
except ImportError:
    # Fallback types when pydantic_ai is not available at runtime.
    ModelMessage = dict
    ModelRequest = dict
    ModelResponse = dict
    TextPart = dict


class SessionPrimitive:
    """
    Primitive for managing conversation session state.

    Provides methods to:
    - Append messages to history
    - Inject system messages
    - Clear history
    - Access full history
    - Save/load session state
    """

    def __init__(self, session_manager=None, agent_name: Optional[str] = None):
        """
        Initialize Session primitive.

        Args:
            session_manager: SessionManager instance
            agent_name: Name of the agent this session belongs to
        """
        self.session_manager = session_manager
        self.agent_name = agent_name

    def _has_session_context(self) -> bool:
        """
        Return True when this primitive is bound to a session manager and agent.
        """
        return bool(self.session_manager and self.agent_name)

    def _serialize_message(self, message: Any) -> dict[str, str]:
        """
        Convert a stored message into a Lua-friendly dict shape.
        """
        if isinstance(message, dict):
            return {
                "role": message.get("role", ""),
                "content": str(message.get("content", "")),
            }

        # Handle pydantic_ai ModelMessage objects.
        try:
            return {
                "role": getattr(message, "role", ""),
                "content": str(getattr(message, "content", "")),
            }
        except Exception:
            # Fallback: preserve content as a string with an unknown role.
            return {"role": "unknown", "content": str(message)}

    def append(self, message_payload: dict[str, Any]) -> None:
        """
        Append a message to the session history.

        Args:
            message_payload: dict with 'role' and 'content' keys
                         role: 'user', 'assistant', 'system'
                         content: message text

        Example:
            Session.append({role = "user", content = "Hello"})
        """
        if not self._has_session_context():
            return

        message_role = message_payload.get("role", "user")
        message_content = message_payload.get("content", "")

        # Create a simple message dict
        message_entry = {"role": message_role, "content": message_content}

        self.session_manager.add_message(self.agent_name, message_entry)

    def inject_system(self, text: str) -> None:
        """
        Inject a system message into the session.

        This is useful for providing context or instructions
        for the next agent turn.

        Args:
            text: System message content

        Example:
            Session.inject_system("Focus on security implications")
        """
        self.append({"role": "system", "content": text})

    def clear(self) -> None:
        """
        Clear the session history for this agent.

        Example:
            Session.clear()
        """
        if not self._has_session_context():
            return

        self.session_manager.clear_agent_history(self.agent_name)

    def history(self) -> list[dict[str, str]]:
        """
        Get the full conversation history for this agent.

        Returns:
            List of message dicts with 'role' and 'content' keys

        Example:
            local messages = Session.history()
            for i, msg in ipairs(messages) do
                Log.info(msg.role .. ": " .. msg.content)
            end
        """
        if not self._has_session_context():
            return []

        messages = self.session_manager.histories.get(self.agent_name, [])

        # Convert to Lua-friendly format
        serialized_messages: list[dict[str, str]] = [
            self._serialize_message(message) for message in messages
        ]

        return serialized_messages

    def load_from_node(self, node: Any) -> None:
        """
        Load session state from a graph node.

        Not yet implemented - placeholder for future graph support.

        Args:
            node: Graph node containing saved session state
        """
        # TODO: Implement when graph primitives are added
        pass

    def save_to_node(self, node: Any) -> None:
        """
        Save session state to a graph node.

        Not yet implemented - placeholder for future graph support.

        Args:
            node: Graph node to save session state to
        """
        # TODO: Implement when graph primitives are added
        pass
