"""
Tool integration feature step definitions.
"""

from typing import Dict

from behave import given, then, when

from tactus.primitives.tool import ToolPrimitive

from features.steps.support import FakeToolServer, table_to_dict


def _tool_state(context):
    if not hasattr(context, "tool_state"):
        context.tool_state = {}
    return context.tool_state


@given("a Tactus workflow with MCP server configured")
def step_impl(context):
    state = _tool_state(context)
    state["server"] = FakeToolServer()
    state["results"] = []
    state["errors"] = []


@given("the tool primitive is initialized")
def step_impl(context):
    _tool_state(context)["primitive"] = ToolPrimitive()


def _record_call(state, name, params, result=None):
    tool = state.get("primitive")
    if tool is not None:
        tool.record_call(name, params, result)


@when('I call Tool "{name}" with parameters:')
def step_impl(context, name):
    state = _tool_state(context)
    params = table_to_dict(context.table)
    duration = state.get("long_task_duration")
    if name == "long_running_task":
        timeout = state.get("long_task_timeout")
        params.setdefault("timeout", timeout)
        if duration is not None:
            params.setdefault("duration", duration)
    try:
        result = state["server"].call(name, params)
        state["results"].append(result)
        state["errors"].append(None)
        _record_call(state, name, params, result)
        context.tool_result = result
        context.tool_error = None
        context.agent_response = result
        context.error = None
    except Exception as exc:
        state["errors"].append(exc)
        context.tool_error = exc
        context.tool_result = None
        context.error = exc
        context.agent_response = None


@then("the tool should execute successfully")
def step_impl(context):
    assert context.tool_error is None, f"Unexpected tool error: {context.tool_error}"
    assert context.tool_result is not None, "Expected a tool result"


@then("the result should contain weather data")
def step_impl(context):
    result = context.tool_result or {}
    assert "temperature" in result and "conditions" in result


@then("the tool call should fail")
def step_impl(context):
    assert context.tool_error is not None, "Expected tool call to fail"


@given('Tool "search_papers" returns paper IDs')
def step_impl(context):
    server = _tool_state(context)["server"]

    def search_papers(params):
        return [f"{params.get('query', 'paper')}-{idx}" for idx in range(1, 4)]

    server.register("search_papers", search_papers)


@when('I call "search_papers" with query "{query}"')
def step_impl(context, query):
    state = _tool_state(context)
    params = {"query": query}
    context.paper_ids = state["server"].call("search_papers", params)


@when('I call "get_paper_details" for each result')
def step_impl(context):
    state = _tool_state(context)
    details = []
    for paper_id in context.paper_ids:
        params = {"paper_id": paper_id}
        details.append(state["server"].call("get_paper_details", params))
        _record_call(state, "get_paper_details", params, details[-1])
    context.paper_details = details


@then("I should have detailed information for all papers")
def step_impl(context):
    assert len(context.paper_details) == len(context.paper_ids)
    for detail in context.paper_details:
        assert "paper_id" in detail and "title" in detail


@when('I call Tool "long_running_task" with timeout {timeout:d} seconds')
def step_impl(context, timeout):
    state = _tool_state(context)
    state["long_task_timeout"] = timeout
    # Trigger the actual invocation with explicit params
    params = {"timeout": timeout}
    if "long_task_duration" in state and state["long_task_duration"] is not None:
        params["duration"] = state["long_task_duration"]
    try:
        context.tool_result = state["server"].call("long_running_task", params)
        context.tool_error = None
        context.error = None
        context.agent_response = context.tool_result
        context.workflow_timed_out = False
    except Exception as exc:
        context.tool_result = None
        context.tool_error = exc
        context.error = exc
        context.agent_response = None
        context.workflow_timed_out = isinstance(exc, TimeoutError)


@when("the tool takes longer than {seconds:d} seconds")
def step_impl(context, seconds):
    _tool_state(context)["long_task_duration"] = seconds


@then("the call should timeout")
def step_impl(context):
    assert isinstance(context.tool_error, TimeoutError), "Expected timeout error"


def _parse_parameters(param_text: str) -> Dict[str, str]:
    params = {}
    for assignment in param_text.split(","):
        assignment = assignment.strip()
        if not assignment:
            continue
        key, _, value = assignment.partition("=")
        params[key.strip()] = value.strip()
    return params


@when("I call multiple tools in parallel:")
def step_impl(context):
    state = _tool_state(context)
    calls = []
    for row in context.table:
        params = _parse_parameters(row["parameters"])
        calls.append({"tool": row["tool"], "params": params})
    state["parallel_call_count"] = len(calls)
    context.parallel_results = state["server"].call_parallel(calls)
    for call, response in zip(calls, context.parallel_results[0]["responses"]):
        _record_call(state, call["tool"], call["params"], response["result"])


@then("all tools should execute concurrently")
def step_impl(context):
    results = context.parallel_results[0]["responses"]
    expected = _tool_state(context).get("parallel_call_count", 0)
    assert len(results) == expected


@then("results should be collected when all complete")
def step_impl(context):
    responses = context.parallel_results[0]["responses"]
    assert all("result" in response for response in responses)
