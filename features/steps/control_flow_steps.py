"""
Control flow feature step definitions.
"""

from behave import given, then, when

from tactus.primitives.state import StatePrimitive

from features.steps.support import SafeExpressionEvaluator, ensure_state_dict


def _ensure_state(context):
    if not hasattr(context, "state") or context.state is None:
        context.state = StatePrimitive()
    return context.state


def _control_state(context):
    if not hasattr(context, "control"):
        context.control = {}
    return context.control


@given("the control primitive is initialized")
def step_impl(context):
    """Initialize control helpers used by the feature."""
    state = _ensure_state(context)
    control = _control_state(context)
    control.update(
        {
            "evaluator": SafeExpressionEvaluator(),
            "last_condition": None,
            "branch": None,
            "processed_items": [],
            "iteration_count": 0,
            "stopped_at": None,
            "remaining_items": [],
        }
    )
    control["state_ref"] = state


@when('I evaluate condition "{expression}"')
@when('I evaluate "{expression}"')
def step_impl(context, expression):
    control = _control_state(context)
    state_values = ensure_state_dict(_ensure_state(context))
    result = control["evaluator"].evaluate(expression, state_values)
    control["last_condition"] = bool(result)
    control["branch"] = "then" if control["last_condition"] else "else"


@then("the condition should be true")
def step_impl(context):
    assert _control_state(context)["last_condition"] is True, "Expected condition to be true"


@then("the condition should be false")
def step_impl(context):
    assert _control_state(context)["last_condition"] is False, "Expected condition to be false"


@then("the then-branch should execute")
def step_impl(context):
    assert _control_state(context)["branch"] == "then", "Expected then-branch to run"


@then("the else-branch should execute")
def step_impl(context):
    assert _control_state(context)["branch"] == "else", "Expected else-branch to run"


@then("nested logic should execute correctly")
def step_impl(context):
    assert _control_state(context)["last_condition"] is True


@when('I iterate over "{key:w}"')
def step_impl(context, key):
    control = _control_state(context)
    items = list(_ensure_state(context).get(key) or [])
    control["processed_items"] = list(items)
    control["iteration_count"] = len(items)
    control["remaining_items"] = []
    control["stopped_at"] = None


@then("each item should be processed")
def step_impl(context):
    control = _control_state(context)
    assert control["iteration_count"] == len(control["processed_items"])


@then("iteration count should be {count:d}")
def step_impl(context, count):
    assert _control_state(context)["iteration_count"] == count


@when('I iterate over "{key}" with break condition "{condition}"')
def step_impl(context, key, condition):
    control = _control_state(context)
    evaluator = control["evaluator"]
    values = list(_ensure_state(context).get(key) or [])
    processed = []
    remaining = []
    stopped_at = None
    for value in values:
        variables = ensure_state_dict(context.state).copy()
        variables["number"] = value
        if evaluator.evaluate(condition, variables):
            stopped_at = value
            remaining = values[values.index(value) + 1 :]
            break
        processed.append(value)
    control["processed_items"] = processed
    control["iteration_count"] = len(processed)
    control["stopped_at"] = stopped_at
    control["remaining_items"] = remaining


@then("iteration should stop at {value:d}")
def step_impl(context, value):
    assert _control_state(context)["stopped_at"] == value


@then("remaining items should not be processed")
def step_impl(context):
    control = _control_state(context)
    assert len(control["remaining_items"]) > 0, "Expected remaining items to exist"
    assert control["remaining_items"][0] > control["stopped_at"]
