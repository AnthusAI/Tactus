"""
Chat recorder protocol for Tactus.

Defines the interface for recording conversation history during workflow execution.
Implementations can store chat logs anywhere (memory, files, databases, APIs, etc.).
"""

from typing import Protocol, Optional, Dict, Any
from tactus.protocols.models import ChatMessage


class ChatRecorder(Protocol):
    """
    Protocol for chat recorders.

    Implementations record conversation history between agents, tools, and humans.
    This is optional - procedures can run without chat recording.
    """

    async def start_session(
        self, procedure_id: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new chat session for a procedure.

        Args:
            procedure_id: Unique procedure identifier
            context: Optional context data for the session

        Returns:
            Session ID

        Raises:
            ChatRecorderError: If session creation fails
        """
        ...

    async def record_message(self, message: ChatMessage) -> str:
        """
        Record a message in the current session.

        Args:
            message: ChatMessage to record

        Returns:
            Message ID

        Raises:
            ChatRecorderError: If recording fails
        """
        ...

    async def end_session(self, session_id: str, status: str = "COMPLETED") -> None:
        """
        End a chat session.

        Args:
            session_id: Session ID to end
            status: Final status (COMPLETED, FAILED, etc.)

        Raises:
            ChatRecorderError: If ending session fails
        """
        ...

    async def get_session_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> list[ChatMessage]:
        """
        Get messages from a session.

        Optional method for implementations that support retrieval.

        Args:
            session_id: Session ID
            limit: Optional limit on number of messages

        Returns:
            List of ChatMessage objects
        """
        ...
