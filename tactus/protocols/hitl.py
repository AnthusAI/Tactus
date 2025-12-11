"""
HITL (Human-in-the-Loop) handler protocol for Tactus.

Defines the interface for managing human interactions during workflow execution.
Implementations can use any UI (web, CLI, API, etc.).
"""

from typing import Protocol, Optional
from tactus.protocols.models import HITLRequest, HITLResponse


class HITLHandler(Protocol):
    """
    Protocol for HITL handlers.

    Implementations manage human interactions (approval, input, review, escalation).
    This allows Tactus to work with any UI or interaction system.
    """

    def request_interaction(self, procedure_id: str, request: HITLRequest) -> HITLResponse:
        """
        Request human interaction (blocking).

        This method should:
        1. Present the request to a human (via UI, CLI, API, etc.)
        2. Wait for response (with timeout handling)
        3. Return HITLResponse with the human's answer

        For exit-and-resume patterns, this may raise
        ProcedureWaitingForHuman to signal workflow suspension.

        Args:
            procedure_id: Unique procedure identifier
            request: HITLRequest with interaction details

        Returns:
            HITLResponse with human's answer

        Raises:
            ProcedureWaitingForHuman: (Optional) To trigger exit-and-resume
            HITLError: If interaction fails
        """
        ...

    def check_pending_response(self, procedure_id: str, message_id: str) -> Optional[HITLResponse]:
        """
        Check if there's a response to a pending HITL request.

        Used during resume flow to check if human has responded while
        procedure was suspended.

        Args:
            procedure_id: Unique procedure identifier
            message_id: Message/request ID to check

        Returns:
            HITLResponse if response exists, None otherwise
        """
        ...

    def cancel_pending_request(self, procedure_id: str, message_id: str) -> None:
        """
        Cancel a pending HITL request.

        Optional method for implementations that support cancellation.

        Args:
            procedure_id: Unique procedure identifier
            message_id: Message/request ID to cancel
        """
        ...
