"""
Session primitive for managing conversation history.

Provides Lua-accessible methods for manipulating chat session state.
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

    def append(self, message_data: dict) -> None:
        """
        Append a message to the session history.

        Args:
            message_data: Dict with 'role' and 'content' keys
                         role: 'user', 'assistant', 'system'
                         content: message text

        Example:
            Session.append({role = "user", content = "Hello"})
        """
        if not self.session_manager or not self.agent_name:
            return

        role = message_data.get("role", "user")
        content = message_data.get("content", "")

        # Create a simple message dict
        message = {"role": role, "content": content}

        self.session_manager.add_message(self.agent_name, message)

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
        if not self.session_manager or not self.agent_name:
            return

        self.session_manager.clear_agent_history(self.agent_name)

    def history(self) -> list:
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
        if not self.session_manager or not self.agent_name:
            return []

        messages = self.session_manager.histories.get(self.agent_name, [])

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
