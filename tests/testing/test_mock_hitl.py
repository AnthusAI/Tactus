"""Tests for mock HITL handler."""

from tactus.testing.mock_hitl import MockHITLHandler
from tactus.protocols.models import HITLRequest


def _request(request_type: str, message: str = "msg"):
    return HITLRequest(request_type=request_type, message=message)


def test_mock_hitl_default_responses():
    handler = MockHITLHandler()

    approval = handler.request_interaction("proc", _request("approval"))
    assert approval.value is True

    input_resp = handler.request_interaction("proc", _request("input"))
    assert input_resp.value == "test input"

    review = handler.request_interaction("proc", _request("review"))
    assert review.value == {"decision": "Approve"}

    notification = handler.request_interaction("proc", _request("notification"))
    assert notification.value is None

    escalation = handler.request_interaction("proc", _request("escalation"))
    assert escalation.value == {"escalated": True}


def test_mock_hitl_configured_responses():
    handler = MockHITLHandler()
    handler.configure_response("approval", False)
    handler.configure_message_response("Special case", "ok")

    approval = handler.request_interaction("proc", _request("approval"))
    assert approval.value is False

    msg_response = handler.request_interaction("proc", _request("input", message="Special case"))
    assert msg_response.value == "ok"


def test_mock_hitl_history_and_clear():
    handler = MockHITLHandler()
    handler.request_interaction("proc", _request("approval"))

    assert handler.get_requests_received()

    handler.clear_history()
    assert handler.get_requests_received() == []


def test_mock_hitl_pending_and_cancel():
    handler = MockHITLHandler()
    assert handler.check_pending_response("proc", "msg") is None
    handler.cancel_pending_request("proc", "msg")


def test_mock_hitl_unknown_request_type_defaults_to_none():
    handler = MockHITLHandler()

    response = handler.request_interaction("proc", _request("unknown"))

    assert response.value is None
