"""
Mock HITL handler for BDD testing.

Provides automatic responses for human interactions during tests,
allowing tests to run without human intervention.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from tactus.protocols.models import HITLRequest, HITLResponse


logger = logging.getLogger(__name__)


class MockHITLHandler:
    """
    HITL handler that provides automatic responses for tests.

    Useful for:
    - Running tests without human intervention
    - Deterministic test behavior
    - Fast test execution
    """

    def __init__(self, default_responses: Optional[Dict[str, Any]] = None):
        """
        Initialize mock HITL handler.

        Args:
            default_responses: Dict of request_id -> response value
                              If not provided, uses sensible defaults
        """
        self.default_responses = default_responses or {}
        self.requests_received: list[HITLRequest] = []

    def request_interaction(self, procedure_id: str, request: HITLRequest) -> HITLResponse:
        """
        Handle HITL request with automatic response.

        Args:
            procedure_id: Unique procedure identifier
            request: HITLRequest with interaction details

        Returns:
            HITLResponse with automatic answer
        """
        # Record the request
        self.requests_received.append(request)

        logger.debug(
            f"Mock HITL request: type={request.request_type}, " f"message={request.message[:50]}..."
        )

        # Determine response based on request type
        if request.request_type == "approval":
            value = self._get_response(request, default=True)
        elif request.request_type == "input":
            value = self._get_response(request, default="test input")
        elif request.request_type == "review":
            value = self._get_response(request, default={"decision": "Approve"})
        elif request.request_type == "notification":
            value = self._get_response(request, default=None)
        elif request.request_type == "escalation":
            value = self._get_response(request, default={"escalated": True})
        else:
            value = self._get_response(request, default=None)

        logger.info(f"Mock HITL response: {value}")

        return HITLResponse(
            value=value,
            responded_at=datetime.utcnow(),
            timed_out=False,
        )

    def _get_response(self, request: HITLRequest, default: Any) -> Any:
        """
        Get response for request, checking custom responses first.

        Args:
            request: The HITL request
            default: Default value if no custom response

        Returns:
            Response value
        """
        # Check if we have a custom response for this message
        # Use message as key for lookup
        message_key = request.message[:50]  # Use first 50 chars as key

        if message_key in self.default_responses:
            return self.default_responses[message_key]

        # Check for type-based default
        type_key = f"_type_{request.request_type}"
        if type_key in self.default_responses:
            return self.default_responses[type_key]

        # Use default
        return default

    def check_pending_response(self, procedure_id: str, message_id: str) -> Optional[HITLResponse]:
        """
        Check for pending response (not used in tests).

        Args:
            procedure_id: Unique procedure identifier
            message_id: Message/request ID to check

        Returns:
            None (tests don't have pending responses)
        """
        return None

    def cancel_pending_request(self, procedure_id: str, message_id: str) -> None:
        """
        Cancel pending request (not used in tests).

        Args:
            procedure_id: Unique procedure identifier
            message_id: Message/request ID to cancel
        """
        pass

    def get_requests_received(self) -> list[HITLRequest]:
        """
        Get all HITL requests received during test.

        Returns:
            List of HITLRequest objects
        """
        return self.requests_received

    def clear_history(self) -> None:
        """Clear request history."""
        self.requests_received.clear()
