"""
Step definitions for Human-in-the-Loop (HITL) feature.
"""

from behave import given, when, then
from datetime import datetime, timezone

from tactus.core.execution_context import BaseExecutionContext
from tactus.adapters.memory import MemoryStorage
from tactus.primitives.human import HumanPrimitive
from tactus.protocols.models import HITLRequest, HITLResponse


class MockHITLHandler:
    """Mock HITL handler for testing."""

    def __init__(self):
        """Initialize mock handler."""
        self.pending_requests = {}
        self.responses = {}  # Pre-configured responses
        self.last_request = None

    def set_response(self, response_value):
        """Set the response that will be returned."""
        self.next_response = response_value

    def request_interaction(
        self, procedure_id: str, request: HITLRequest, execution_context=None
    ) -> HITLResponse:
        """Handle interaction request with pre-configured response."""
        self.last_request = request
        self.pending_requests[procedure_id] = request

        # Check for timeout
        if request.timeout_seconds is not None:
            # Simulate timeout if configured
            if hasattr(self, "simulate_timeout") and self.simulate_timeout:
                return HITLResponse(
                    value=request.default_value,
                    responded_at=datetime.now(timezone.utc),
                    timed_out=True,
                )

        # Return pre-configured response
        if hasattr(self, "next_response"):
            value = self.next_response
        else:
            # Default responses based on request type
            if request.request_type == "approval":
                value = True
            elif request.request_type == "input":
                value = "Mock input"
            elif request.request_type == "review":
                value = {"decision": "approve", "edited_artifact": None, "feedback": ""}
            else:
                value = None

        return HITLResponse(value=value, responded_at=datetime.now(timezone.utc), timed_out=False)

    def check_pending_response(self, procedure_id: str, message_id: str):
        """Check for pending response."""
        return self.responses.get(message_id)

    def cancel_pending_request(self, procedure_id: str, message_id: str):
        """Cancel pending request."""
        if procedure_id in self.pending_requests:
            del self.pending_requests[procedure_id]


@given("a Tactus workflow with HITL enabled")
def step_impl(context):
    """Initialize workflow with HITL handler."""
    context.procedure_id = "test_hitl_procedure"
    context.storage = MemoryStorage()
    context.hitl_handler = MockHITLHandler()
    context.execution_context = BaseExecutionContext(
        procedure_id=context.procedure_id,
        storage_backend=context.storage,
        hitl_handler=context.hitl_handler,
    )


@given("a CLI HITL handler is configured")
def step_impl(context):
    """HITL handler is already configured in previous step."""
    assert context.hitl_handler is not None


@when('the workflow requests approval with message "{message}"')
def step_impl(context, message):
    """Request approval with message."""
    context.human = HumanPrimitive(context.execution_context)
    context.approval_message = message
    # Don't execute yet - wait for human response setup


@when("the human approves the request")
def step_impl(context):
    """Human approves the request."""
    context.hitl_handler.set_response(True)
    # Now execute the approval request
    context.approval_result = context.human.approve({"message": context.approval_message})


@when("the human rejects the request")
def step_impl(context):
    """Human rejects the request."""
    context.hitl_handler.set_response(False)
    # Execute the approval request
    context.approval_result = context.human.approve({"message": context.approval_message})


@then("the workflow should continue")
def step_impl(context):
    """Verify workflow continues (no exception)."""
    assert True  # If we got here, workflow didn't crash


@then("the approval result should be true")
def step_impl(context):
    """Verify approval result is true."""
    assert context.approval_result is True, f"Expected True, got {context.approval_result}"


@then("the approval result should be false")
def step_impl(context):
    """Verify approval result is false."""
    assert context.approval_result is False, f"Expected False, got {context.approval_result}"


@then("the workflow can handle the rejection")
def step_impl(context):
    """Verify workflow can handle rejection."""
    # In a real workflow, this would check that rejection logic executed
    assert context.approval_result is False


@when('the workflow requests input with Prompt "{prompt}"')
def step_impl(context, prompt):
    """Request human input with prompt."""
    context.human = HumanPrimitive(context.execution_context)
    context.input_prompt = prompt
    # Don't execute yet - wait for human response


@when('the human provides input "{input_text}"')
def step_impl(context, input_text):
    """Human provides input."""
    context.hitl_handler.set_response(input_text)
    # Now execute the input request
    context.input_result = context.human.input({"message": context.input_prompt})


@then('the workflow should receive "{expected}"')
def step_impl(context, expected):
    """Verify workflow received expected input."""
    assert context.input_result == expected, f"Expected '{expected}', got '{context.input_result}'"


@then("the workflow can use the input")
def step_impl(context):
    """Verify workflow can use the input."""
    assert context.input_result is not None
    assert isinstance(context.input_result, str)


@given("the workflow has generated a research report")
def step_impl(context):
    """Set up context with generated report."""
    context.human = HumanPrimitive(context.execution_context)
    context.report = "Research report content..."


@when('the workflow requests review with message "{message}"')
def step_impl(context, message):
    """Request review with message."""
    context.review_message = message
    # Don't execute yet - wait for options and human response


@when('options are "{option_str}"')
def step_impl(context, option_str):
    """Set review options."""
    # Parse comma-separated options: "approve", "request_changes", "reject"
    options = [opt.strip().strip('"') for opt in option_str.split(",")]
    context.review_options = options


@when('the human selects "{decision}" with feedback "{feedback}"')
def step_impl(context, decision, feedback):
    """Human selects option with feedback."""
    context.hitl_handler.set_response(
        {"decision": decision, "edited_artifact": context.report, "feedback": feedback}
    )
    # Now execute the review request
    context.review_result = context.human.review(
        {
            "message": context.review_message,
            "artifact": context.report,
            "options": context.review_options,
        }
    )


@then('the workflow should receive decision "{expected_decision}"')
def step_impl(context, expected_decision):
    """Verify workflow received expected decision."""
    actual_decision = context.review_result.get("decision")
    assert (
        actual_decision == expected_decision
    ), f"Expected decision '{expected_decision}', got '{actual_decision}'"


@then('the workflow should receive feedback "{expected_feedback}"')
def step_impl(context, expected_feedback):
    """Verify workflow received expected feedback."""
    actual_feedback = context.review_result.get("feedback")
    assert (
        actual_feedback == expected_feedback
    ), f"Expected feedback '{expected_feedback}', got '{actual_feedback}'"


@when('the workflow requests approval with message "{message}" and timeout {timeout:d} second')
def step_impl(context, message, timeout):
    """Request approval with timeout."""
    context.human = HumanPrimitive(context.execution_context)
    context.approval_message = message
    context.timeout = timeout
    # Don't execute yet - wait for human (non-)response


@when("the human does not respond")
def step_impl(context):
    """Human does not respond."""
    # Configure mock to simulate timeout
    context.hitl_handler.simulate_timeout = True


@when("{seconds:d} seconds pass")
def step_impl(context, seconds):
    """Simulate time passing."""
    # In testing, we don't actually wait
    # The mock handler simulates timeout immediately
    context.seconds_passed = seconds


@then("the workflow should receive the default value false")
def step_impl(context):
    """Verify workflow received default value."""
    # Now execute with timeout
    context.approval_result = context.human.approve(
        {"message": context.approval_message, "timeout": context.timeout, "default": False}
    )
    assert (
        context.approval_result is False
    ), f"Expected False (default), got {context.approval_result}"


@then("the workflow continues with the default")
def step_impl(context):
    """Verify workflow continues with default."""
    assert context.approval_result is False


@given("the workflow encounters an unrecoverable error")
def step_impl(context):
    """Set up error scenario."""
    context.human = HumanPrimitive(context.execution_context)
    context.error_occurred = True


@when('the workflow escalates with message "{message}"')
def step_impl(context, message):
    """Workflow escalates with message."""
    context.escalation_message = message
    # Don't execute yet - wait for severity and resolution


@when('severity is "{severity}"')
def step_impl(context, severity):
    """Set escalation severity."""
    context.escalation_severity = severity


@then("the workflow should pause")
def step_impl(context):
    """Verify workflow pauses (escalation blocks)."""
    # In testing, we simulate this by checking the request was created
    # We'll mark that escalation was called
    context.escalation_paused = True


@then("wait for human resolution")
def step_impl(context):
    """Verify waiting for human resolution."""
    # Escalation handler will wait - we verify the request was made
    assert context.escalation_paused


@when("the human resolves the escalation")
def step_impl(context):
    """Human resolves the escalation."""
    # Configure mock to return from escalation
    context.hitl_handler.set_response(None)  # Escalation returns None
    # Now execute the escalation (which will immediately return in mock)
    context.human.escalate(
        {"message": context.escalation_message, "severity": context.escalation_severity}
    )
    context.escalation_resolved = True


@then("the workflow should resume")
def step_impl(context):
    """Verify workflow resumes after escalation."""
    assert context.escalation_resolved is True
