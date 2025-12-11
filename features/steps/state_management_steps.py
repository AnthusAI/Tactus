"""
Step definitions for State Management feature.
"""

import ast

from behave import given, then, when
from tactus.primitives.state import StatePrimitive


def _ensure_state(context):
    if not hasattr(context, "state") or context.state is None:
        context.state = StatePrimitive()
    return context.state


@given("a fresh Tactus workflow environment")
def step_impl(context):
    """Initialize fresh workflow context."""
    context.workflow = {}


@given("the state primitive is initialized")
def step_impl(context):
    """Initialize state primitive."""
    context.state = StatePrimitive()


@when('I set state "{key}" to "{value}"')
def step_impl(context, key, value):
    """Set a state value."""
    _ensure_state(context).set(key, value)


@when('I set state "{key}" to {value:d}')
def step_impl(context, key, value):
    """Set a numeric state value."""
    _ensure_state(context).set(key, value)


@then('state "{key}" should equal "{expected}"')
def step_impl(context, key, expected):
    """Verify state value matches expected."""
    actual = _ensure_state(context).get(key)
    assert actual == expected, f"Expected {expected}, got {actual}"


@when('I get state "{key}" with default "{default_value}"')
def step_impl(context, key, default_value):
    """Get state with default value."""
    context.result = _ensure_state(context).get(key, default_value)


@then('the result should equal "{expected}"')
def step_impl(context, expected):
    """Verify result matches expected."""
    assert context.result == expected, f"Expected {expected}, got {context.result}"


@then('state "{key}" should not exist')
def step_impl(context, key):
    """Verify key doesn't exist in state."""
    state = _ensure_state(context)
    assert key not in state._state, f"Key {key} should not exist"


@given('state "{key}" is {value:d}')
def step_impl(context, key, value):
    """Set numeric state value."""
    _ensure_state(context).set(key, value)


@given('state "{key}" contains {literal}')
def step_impl(context, key, literal):
    """Set state key to list/dict literal."""
    state = _ensure_state(context)
    try:
        value = ast.literal_eval(literal)
    except Exception as exc:
        raise AssertionError(f"Unable to parse literal '{literal}': {exc}") from exc
    state.set(key, value)


@when('I increment state "{key}"')
def step_impl(context, key):
    """Increment state by 1."""
    _ensure_state(context).increment(key)


@when('I increment state "{key}" by {amount:d}')
def step_impl(context, key, amount):
    """Increment state by specified amount."""
    _ensure_state(context).increment(key, amount)


@then('state "{key}" should equal {expected:d}')
def step_impl(context, key, expected):
    """Verify numeric state value."""
    actual = _ensure_state(context).get(key)
    assert actual == expected, f"Expected {expected}, got {actual}"


@when('I append "{value}" to state "{key}"')
def step_impl(context, key, value):
    """Append value to state list."""
    _ensure_state(context).append(key, value)


@then('state "{key}" should be a list with {count:d} elements')
def step_impl(context, key, count):
    """Verify list length."""
    actual = _ensure_state(context).get(key)
    assert isinstance(actual, list), f"Expected list, got {type(actual)}"
    assert len(actual) == count, f"Expected {count} elements, got {len(actual)}"


@then('state "{key}" should contain "{item1}", "{item2}", and "{item3}"')
def step_impl(context, key, item1, item2, item3):
    """Verify list contains specific items."""
    actual = _ensure_state(context).get(key)
    assert item1 in actual, f"{item1} not in list"
    assert item2 in actual, f"{item2} not in list"
    assert item3 in actual, f"{item3} not in list"


@given("I am building an AI research workflow")
def step_impl(context):
    """Set up research workflow context."""
    context.workflow_type = "ai_research"


@then('state "{key}" should have {count:d} items')
def step_impl(context, key, count):
    """Verify list item count."""
    actual = _ensure_state(context).get(key)
    assert len(actual) == count, f"Expected {count} items, got {len(actual)}"
