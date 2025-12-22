"""
Gherkin step definitions for configuring mocks in BDD tests.

These steps allow test scenarios to configure mock responses for
dependencies and HITL interactions using natural language.
"""

import json
import logging

from behave import given, when, then

logger = logging.getLogger(__name__)


# HTTP Dependency Mocking Steps


@given("the {dep_name} returns '{response}'")
def configure_http_mock_default(context, dep_name: str, response: str):
    """
    Configure HTTP dependency mock with default response.

    Example:
        Given the weather_api returns '{"temp": 72}'
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_http_response(dep_name, None, response)
    logger.debug(f"Configured default HTTP response for {dep_name}: {response[:50]}...")


@given("the {dep_name} returns '{response}' for {path}")
def configure_http_mock_path(context, dep_name: str, response: str, path: str):
    """
    Configure HTTP dependency mock for specific path.

    Example:
        Given the weather_api returns '{"temp": 72}' for /weather
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_http_response(dep_name, path, response)
    logger.debug(f"Configured HTTP response for {dep_name} {path}: {response[:50]}...")


@given("the {dep_name} returns '{response}' with status {status_code:d}")
def configure_http_mock_status(context, dep_name: str, response: str, status_code: int):
    """
    Configure HTTP dependency mock with specific status code.

    Example:
        Given the weather_api returns '{"error": "not found"}' with status 404
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_http_response(dep_name, None, response, status_code)
    logger.debug(
        f"Configured HTTP response for {dep_name} (status {status_code}): {response[:50]}..."
    )


# HITL Mocking Steps (Type-Based)


@given("Human.approve will return {value}")
def configure_hitl_approval_type(context, value: str):
    """
    Configure HITL mock for all approval requests.

    Example:
        Given Human.approve will return true
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    approved = value.lower() == "true"
    context.mock_registry.configure_hitl_response("approval", approved)
    logger.debug(f"Configured HITL approval response: {approved}")


@given("Human.input will return '{value}'")
def configure_hitl_input_type(context, value: str):
    """
    Configure HITL mock for all input requests.

    Example:
        Given Human.input will return 'test data'
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_hitl_response("input", value)
    logger.debug(f"Configured HITL input response: {value}")


@given("Human.review will return {value}")
def configure_hitl_review_type(context, value: str):
    """
    Configure HITL mock for all review requests.

    Example:
        Given Human.review will return '{"decision": "approve"}'
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    # Try to parse as JSON, otherwise treat as string
    try:
        parsed_value = json.loads(value)
    except json.JSONDecodeError:
        parsed_value = value

    context.mock_registry.configure_hitl_response("review", parsed_value)
    logger.debug(f"Configured HITL review response: {parsed_value}")


# HITL Mocking Steps (Message-Based)


@given("when asked \"{message_prefix}\" return the value '{value}'")
def configure_hitl_message_string(context, message_prefix: str, value: str):
    """
    Configure HITL mock for specific message (string value).

    Example:
        Given when asked "Enter city" return the value 'Seattle'
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_hitl_message_response(message_prefix, value)
    logger.debug(f"Configured HITL response for '{message_prefix}': {value}")


@given('when asked "{message_prefix}" return {value}')
def configure_hitl_message_approval(context, message_prefix: str, value: str):
    """
    Configure HITL mock for specific message (approval/boolean).

    Example:
        Given when asked "Approve payment" return true
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    # Handle boolean values
    if value.lower() in ("true", "false"):
        parsed_value = value.lower() == "true"
    else:
        parsed_value = value

    context.mock_registry.configure_hitl_message_response(message_prefix, parsed_value)
    logger.debug(f"Configured HITL response for '{message_prefix}': {parsed_value}")


# Runtime Configuration Steps (Can appear in When/And/Then)


@when("the user presses no")
def user_presses_no(context):
    """
    Configure HITL to reject (mid-scenario configuration).

    Example:
        When the user presses no
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_hitl_response("approval", False)
    logger.debug("Configured HITL approval response: False (user pressed no)")


@when("the user presses yes")
def user_presses_yes(context):
    """
    Configure HITL to approve (mid-scenario configuration).

    Example:
        When the user presses yes
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_hitl_response("approval", True)
    logger.debug("Configured HITL approval response: True (user pressed yes)")


@when("the user enters '{value}'")
def user_enters_value(context, value: str):
    """
    Configure HITL input (mid-scenario configuration).

    Example:
        When the user enters 'Seattle'
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    context.mock_registry.configure_hitl_response("input", value)
    logger.debug(f"Configured HITL input response: {value}")


# Assertions for Mock Interactions


@then("the {dep_name} should have been called")
def assert_dependency_called(context, dep_name: str):
    """
    Assert that a dependency was called during test.

    Example:
        Then the weather_api should have been called
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    mock = context.mock_registry.get_mock(dep_name)
    if not mock:
        raise AssertionError(f"Dependency '{dep_name}' not found in mock registry")

    if hasattr(mock, "calls") and len(mock.calls) == 0:
        raise AssertionError(f"Dependency '{dep_name}' was not called")

    logger.debug(f"Verified {dep_name} was called")


@then("the {dep_name} should not have been called")
def assert_dependency_not_called(context, dep_name: str):
    """
    Assert that a dependency was NOT called during test.

    Example:
        Then the payment_api should not have been called
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    mock = context.mock_registry.get_mock(dep_name)
    if not mock:
        # If mock doesn't exist, it wasn't called
        logger.debug(f"Verified {dep_name} was not called (not in registry)")
        return

    if hasattr(mock, "calls") and len(mock.calls) > 0:
        raise AssertionError(
            f"Dependency '{dep_name}' was called {len(mock.calls)} times, expected 0"
        )

    logger.debug(f"Verified {dep_name} was not called")


@then("the {dep_name} should have been called {count:d} times")
def assert_dependency_call_count(context, dep_name: str, count: int):
    """
    Assert that a dependency was called a specific number of times.

    Example:
        Then the weather_api should have been called 3 times
    """
    if not hasattr(context, "mock_registry"):
        raise RuntimeError("Mock registry not initialized in test context")

    mock = context.mock_registry.get_mock(dep_name)
    if not mock:
        raise AssertionError(f"Dependency '{dep_name}' not found in mock registry")

    if not hasattr(mock, "calls"):
        raise AssertionError(f"Dependency '{dep_name}' does not track calls")

    actual_count = len(mock.calls)
    if actual_count != count:
        raise AssertionError(
            f"Dependency '{dep_name}' was called {actual_count} times, expected {count}"
        )

    logger.debug(f"Verified {dep_name} was called {count} times")
