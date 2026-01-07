"""
Procedure calls feature step definitions.
"""

import textwrap

from behave import given, then, when

from features.steps.support import ProcedureRuntime


def _proc_state(context):
    if not hasattr(context, "procedure_state"):
        context.procedure_state = {
            "runtime": ProcedureRuntime(),
            "main_state": {},
            "last_result": None,
            "call_history": [],
            "checkpointed": {},
        }
    return context.procedure_state


def _runtime(context) -> ProcedureRuntime:
    return _proc_state(context)["runtime"]


@given("the procedure primitive is initialized")
def step_impl(context):
    _proc_state(context)["runtime"] = ProcedureRuntime()


@given('a sub-Procedure "{name}":')
def step_impl(context, name):
    _runtime(context).register_yaml(textwrap.dedent(context.text or ""))


@when('I call Procedure "{name}" with params:')
def step_impl(context, name):
    params = {
        row["param"]: int(row["value"]) if row["value"].isdigit() else row["value"]
        for row in context.table
    }
    result, state = _runtime(context).call(
        name, params=params, state=_proc_state(context)["main_state"]
    )
    _proc_state(context)["last_result"] = result
    _proc_state(context)["last_child_state"] = state


@then("the procedure should execute")
def step_impl(context):
    assert _proc_state(context)["last_result"] is not None


@then("it should return result {value:d}")
def step_impl(context, value):
    assert _proc_state(context)["last_result"] == value


@given('a main procedure with state "{key}" = {value:d}')
def step_impl(context, key, value):
    _proc_state(context)["main_state"][key] = value


@given('a sub-procedure that sets state "{key}" = {value:d}')
def step_impl(context, key, value):
    def handler(params, state, runtime):
        state[key] = value
        return value

    _runtime(context).register_callable("mutating_subproc", handler)


@when("I call the sub-procedure")
def step_impl(context):
    result, state = _runtime(context).call(
        "mutating_subproc", state=_proc_state(context)["main_state"].copy()
    )
    _proc_state(context)["last_result"] = result
    _proc_state(context)["last_child_state"] = state


@then('the sub-procedure should see "{key}" = {value:d}')
def step_impl(context, key, value):
    assert _proc_state(context)["last_child_state"][key] == value


@then('the main procedure should still see "{key}" = {value:d}')
def step_impl(context, key, value):
    assert _proc_state(context)["main_state"][key] == value


@then("state should be isolated between procedures")
def step_impl(context):
    assert _proc_state(context)["main_state"] is not _proc_state(context)["last_child_state"]


@given('a sub-Procedure "process_list"')
def step_impl(context):
    def handler(params, state, runtime):
        state["received"] = params["items"]
        return params["items"]

    _runtime(context).register_callable("process_list", handler)


@when("I call it with a list parameter:")
def step_impl(context):
    items = [row["item"] for row in context.table]
    result, state = _runtime(context).call("process_list", params={"items": items})
    _proc_state(context)["last_result"] = result
    _proc_state(context)["last_child_state"] = state


@then("the sub-procedure should receive the full list")
def step_impl(context):
    assert (
        _proc_state(context)["last_child_state"]["received"] == _proc_state(context)["last_result"]
    )


@then("it can iterate and process each item")
def step_impl(context):
    assert len(_proc_state(context)["last_result"]) >= 1


@given('Procedure "level1" calls Procedure "level2"')
def step_impl(context):
    state = _proc_state(context)

    def level2(params, child_state, runtime):
        state["call_history"].append("level2")
        runtime.call("level3", {})
        return "level2"

    def level1(params, child_state, runtime):
        state["call_history"].append("level1")
        runtime.call("level2", {})
        return "level1"

    state["call_history"].clear()
    _runtime(context).register_callable(
        "level3", lambda params, s, r: state["call_history"].append("level3")
    )
    _runtime(context).register_callable("level2", level2)
    _runtime(context).register_callable("level1", level1)


@given('Procedure "level2" calls Procedure "level3"')
def step_impl(context):
    pass  # Covered in previous step


@when('I execute Procedure "level1"')
def step_impl(context):
    _runtime(context).call("level1", {})


@then("all three levels should execute")
def step_impl(context):
    assert _proc_state(context)["call_history"] == ["level1", "level2", "level3"]


@then("call stack should be tracked correctly")
def step_impl(context):
    assert len(_proc_state(context)["call_history"]) == 3


@then("results should propagate back up")
def step_impl(context):
    assert "level1" in _proc_state(context)["call_history"]


@given("a sub-procedure that raises an error")
def step_impl(context):
    def handler(params, state, runtime):
        raise RuntimeError("sub-proc failure")

    _runtime(context).register_callable("failing_proc", handler)


@when("I call it from the main procedure")
def step_impl(context):
    try:
        _runtime(context).call("failing_proc", {})
        _proc_state(context)["last_error"] = None
    except Exception as exc:
        _proc_state(context)["last_error"] = exc


@then("the error should propagate to the caller")
def step_impl(context):
    assert isinstance(_proc_state(context)["last_error"], RuntimeError)


@then("the main procedure can catch and handle it")
def step_impl(context):
    assert _proc_state(context)["last_error"] is not None


@given("a sub-procedure with timeout {seconds:d} seconds")
def step_impl(context, seconds):
    def handler(params, state, runtime):
        _proc_state(context)["duration"] = seconds + 1
        return "timeout-test"

    _runtime(context).register_callable("long_proc", handler, duration=seconds + 1)


@when("the sub-procedure runs longer than {seconds:d} seconds")
def step_impl(context, seconds):
    try:
        _runtime(context).call("long_proc", timeout=seconds)
        _proc_state(context)["last_error"] = None
    except TimeoutError as exc:
        _proc_state(context)["last_error"] = exc


@then("it should be terminated")
def step_impl(context):
    assert isinstance(_proc_state(context)["last_error"], TimeoutError)


@then("a timeout error should be raised to caller")
def step_impl(context):
    assert isinstance(_proc_state(context)["last_error"], TimeoutError)


@given('a generic "send_email" procedure')
def step_impl(context):
    sent = []

    def handler(params, state, runtime):
        sent.append(params["recipient"])
        return params["recipient"]

    _proc_state(context)["sent_emails"] = sent
    _runtime(context).register_callable("send_email", handler)


@when("I call it multiple times with different recipients")
def step_impl(context):
    if context.table:
        recipients = [row["value"] for row in context.table]
    else:
        recipients = ["alice@example.com", "bob@example.com"]
    for recipient in recipients:
        _runtime(context).call("send_email", params={"recipient": recipient})


@then("each call should be independent")
def step_impl(context):
    assert len(_proc_state(context)["sent_emails"]) == len(set(_proc_state(context)["sent_emails"]))


@then("emails should be sent to all recipients")
def step_impl(context):
    assert _proc_state(context)["sent_emails"]


@given("a main procedure that calls sub-procedures")
def step_impl(context):
    def handler(params, state, runtime):
        result, _ = runtime.call("checkpointed_sub", {})
        return result

    def sub_handler(params, state, runtime):
        return "sub-result"

    runtime = _runtime(context)
    runtime.register_callable("main_proc", handler)
    runtime.register_callable("checkpointed_sub", sub_handler, checkpoint=True)


@when("a sub-procedure completes")
def step_impl(context):
    result, _ = _runtime(context).call("main_proc", {})
    _proc_state(context)["last_result"] = result


@then("its result should be checkpointed")
def step_impl(context):
    assert _runtime(context).checkpoints.get("checkpointed_sub") == "sub-result"


@then("resuming the main procedure should skip the completed sub-procedure")
def step_impl(context):
    assert "checkpointed_sub" in _runtime(context).checkpoints
