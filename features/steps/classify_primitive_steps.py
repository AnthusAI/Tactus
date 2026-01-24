"""
Classify primitive feature step definitions.

These steps exercise the Python stdlib Classify primitive deterministically by
using a tiny in-memory mock agent (no real LLM calls).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from behave import given, then, when

from tactus.stdlib.classify.primitive import ClassifyHandle, ClassifyPrimitive


def _parse_list_literal(value: str) -> List[str]:
    parsed = ast.literal_eval(value)
    if not isinstance(parsed, list):
        raise AssertionError(f"Expected list literal, got: {type(parsed).__name__}")
    return [str(v) for v in parsed]


@dataclass
class _AgentCall:
    message: str


class _MockAgent:
    def __init__(self, responses: List[str], default_response: str):
        self._responses = list(responses)
        self._default_response = default_response
        self._idx = 0
        self.calls: List[_AgentCall] = []
        self.reset_count = 0

    def reset(self) -> None:
        self.reset_count += 1

    def __call__(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        message = str(inputs.get("message", ""))
        self.calls.append(_AgentCall(message=message))

        if self._idx < len(self._responses):
            resp = self._responses[self._idx]
            self._idx += 1
        else:
            # If a scenario doesn't configure explicit responses, return a stable,
            # valid value with an explanation line so explanation-related asserts pass.
            resp = self._default_response

        return {"response": resp}


def _state(context) -> Dict[str, Any]:
    if not hasattr(context, "classify_state"):
        context.classify_state = {}
    state = context.classify_state

    state.setdefault("config", {})
    state.setdefault("responses", None)
    state.setdefault("agent_configs", [])
    state.setdefault("agent", None)
    state.setdefault("result", None)
    state.setdefault("handle", None)
    state.setdefault("error", None)
    # Most scenarios in features/61_classify_primitive.feature expect one-shot
    # classification even when they don't explicitly set input. Scenarios that
    # want a reusable handle will set this flag via "no input is provided".
    state.setdefault("force_handle", False)
    return state


@given("the Classify primitive is available")
def step_given_classify_available(context):
    state = _state(context)
    # Reset any state left from earlier scenarios. The shared
    # "a Tactus workflow environment" step is defined elsewhere.
    state["config"] = {}
    state["responses"] = None
    state["agent_configs"] = []
    state["agent"] = None
    state["result"] = None
    state["handle"] = None
    state["error"] = None
    state["force_handle"] = False
    context.error = None

    def agent_factory(agent_config: Dict[str, Any]) -> _MockAgent:
        state["agent_configs"].append(dict(agent_config))
        default_label = state.get("default_label") or "Yes"
        agent = _MockAgent(
            responses=state["responses"] or [],
            default_response=f"{default_label}\nMocked explanation.",
        )
        state["agent"] = agent
        return agent

    state["primitive"] = ClassifyPrimitive(agent_factory=agent_factory)


@given("a Classify call with classes {classes}")
def step_given_classify_call_with_classes(context, classes):
    state = _state(context)
    parsed_classes = _parse_list_literal(classes)
    state["default_label"] = parsed_classes[0] if parsed_classes else "Yes"
    state["config"] = {
        "method": "llm",
        "classes": parsed_classes,
        # Many scenarios omit a prompt; provide a harmless default unless the scenario
        # explicitly tests missing prompt.
        "prompt": state.get("prompt") or "Classify the input.",
    }


@given('the prompt is "{prompt}"')
def step_given_prompt(context, prompt):
    state = _state(context)
    state["config"]["prompt"] = prompt


@given("no prompt is provided")
def step_given_no_prompt(context):
    state = _state(context)
    state["config"].pop("prompt", None)


@given("a Classify call without classes")
def step_given_classify_without_classes(context):
    state = _state(context)
    state["config"] = {
        "method": "llm",
        "prompt": "Classify the input.",
    }


@given('input is "{input_text}"')
def step_given_input_inline(context, input_text):
    state = _state(context)
    state["config"]["input"] = input_text
    state["force_handle"] = False


@given("no input is provided")
def step_given_no_input(context):
    state = _state(context)
    state["config"].pop("input", None)
    state["force_handle"] = True


@given("max_retries is {max_retries:d}")
def step_given_max_retries(context, max_retries):
    state = _state(context)
    state["config"]["max_retries"] = max_retries


@given("temperature is {temperature:f}")
def step_given_temperature(context, temperature):
    state = _state(context)
    state["config"]["temperature"] = float(temperature)


@given('model is "{model}"')
def step_given_model(context, model):
    state = _state(context)
    state["config"]["model"] = model


@given('confidence_mode is "{mode}"')
def step_given_confidence_mode(context, mode):
    state = _state(context)
    state["config"]["confidence_mode"] = mode


@given("the LLM will respond with {responses}")
def step_given_llm_response(context, responses):
    """
    Supports:
      the LLM will respond with "Yes"
      the LLM will respond with "Maybe" then "Yes"
      the LLM will respond with "Invalid" then "Unknown" then "Yes"
    """
    import re

    state = _state(context)

    # Prefer parsing quoted segments (so "A" then "B" becomes ["A", "B"]).
    quoted = re.findall(r'"([^"]*)"', responses)
    if quoted:
        state["responses"] = quoted
        return

    # Fall back to treating the entire capture as one response (strip wrapping quotes if present).
    raw = responses.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, str):
                state["responses"] = [parsed]
                return
        except Exception:
            pass

    state["responses"] = [raw]


@given('the LLM will always respond with "{response}"')
def step_given_llm_always_response(context, response):
    state = _state(context)
    # Provide enough responses for max_retries + 1 attempts across any scenario.
    max_retries = int(state["config"].get("max_retries", 3))
    state["responses"] = [response] * (max_retries + 2)


@given("the LLM will respond with:")
def step_given_llm_docstring(context):
    state = _state(context)
    state["responses"] = [context.text]


@when("Classify is invoked")
def step_when_classify_invoked(context):
    state = _state(context)
    state["error"] = None
    state["result"] = None
    state["handle"] = None

    try:
        # Default to one-shot classification unless the scenario explicitly
        # requests a reusable handle (see "no input is provided").
        if "input" not in state["config"] and not state.get("force_handle", False):
            state["config"]["input"] = "Example input"
        primitive: ClassifyPrimitive = state["primitive"]
        output = primitive(dict(state["config"]))
        if isinstance(output, ClassifyHandle):
            state["handle"] = output
        else:
            state["result"] = output
        # Integrate with shared error assertion steps.
        context.error = None
    except Exception as exc:  # noqa: BLE001 - behave wants raw exception message
        state["error"] = exc
        context.error = exc


@when('Classify is invoked with input "{input_text}"')
def step_when_classify_invoked_with_input(context, input_text):
    state = _state(context)
    state["config"]["input"] = input_text
    step_when_classify_invoked(context)


@when("Classify is invoked with empty input")
def step_when_classify_invoked_empty_input(context):
    state = _state(context)
    state["config"]["input"] = ""
    step_when_classify_invoked(context)


@then('the result value should be "{expected}"')
def step_then_result_value_equals(context, expected):
    state = _state(context)
    assert state["error"] is None, f"Expected no error, got: {state['error']}"
    assert state["result"] is not None, "No result available"
    assert state["result"]["value"] == expected, state["result"]


@then("the result value should be one of {classes}")
def step_then_result_value_one_of(context, classes):
    state = _state(context)
    assert state["error"] is None, f"Expected no error, got: {state['error']}"
    allowed = set(_parse_list_literal(classes))
    assert state["result"] is not None, "No result available"
    assert state["result"]["value"] in allowed, state["result"]


@then("the result should include confidence")
def step_then_result_has_confidence(context):
    state = _state(context)
    assert state["result"] is not None, "No result available"
    assert state["result"].get("confidence") is not None, state["result"]


@then("the result should include explanation")
def step_then_result_has_explanation(context):
    state = _state(context)
    assert state["result"] is not None, "No result available"
    explanation = state["result"].get("explanation")
    assert explanation, state["result"]


@then("the result should contain an error")
def step_then_result_has_error(context):
    state = _state(context)
    # Some failures return a result dict with error, others raise.
    if state["error"] is not None:
        return
    assert state["result"] is not None, "No result available"
    assert state["result"].get("error") is not None, state["result"]


@then('the error message should mention "{text}"')
def step_then_error_message_mentions(context, text):
    state = _state(context)
    assert state["error"] is not None, "Expected an error to be raised"
    assert text.lower() in str(state["error"]).lower(), str(state["error"])


@then("the retry_count should be {count:d}")
def step_then_retry_count(context, count):
    state = _state(context)
    assert state["result"] is not None, "No result available"
    assert int(state["result"].get("retry_count", -1)) == count, state["result"]


@then("the second LLM call should include:")
def step_then_second_llm_call_includes(context):
    state = _state(context)
    agent: Optional[_MockAgent] = state.get("agent")
    assert agent is not None, "Mock agent was not created"
    assert len(agent.calls) >= 2, f"Expected at least 2 LLM calls, got {len(agent.calls)}"
    second = agent.calls[1].message.lower()

    expected_parts = [row["content"] for row in context.table]  # type: ignore[attr-defined]
    for part in expected_parts:
        assert part.lower() in second, f"Missing '{part}' in second call: {agent.calls[1].message}"


@then("the result confidence should be greater than {threshold:f}")
def step_then_confidence_gt(context, threshold):
    state = _state(context)
    conf = state["result"].get("confidence")
    assert conf is not None, state["result"]
    assert conf > float(threshold), conf


@then("the result confidence should be between {min_v:f} and {max_v:f}")
def step_then_confidence_between(context, min_v, max_v):
    state = _state(context)
    conf = state["result"].get("confidence")
    assert conf is not None, state["result"]
    assert float(min_v) <= conf <= float(max_v), conf


@then("the result confidence should be less than {threshold:f}")
def step_then_confidence_lt(context, threshold):
    state = _state(context)
    conf = state["result"].get("confidence")
    assert conf is not None, state["result"]
    assert conf < float(threshold), conf


@then("the result confidence should be null")
def step_then_confidence_null(context):
    state = _state(context)
    assert state["result"] is not None, "No result available"
    assert state["result"].get("confidence") is None, state["result"]


@then('the explanation should contain "{text}"')
def step_then_explanation_contains(context, text):
    state = _state(context)
    explanation = (state["result"] or {}).get("explanation") or ""
    assert text.lower() in explanation.lower(), explanation


@then("the result should be a classification result")
def step_then_result_is_classification_result(context):
    state = _state(context)
    assert state["error"] is None, f"Expected no error, got: {state['error']}"
    assert state.get("handle") is None, f"Expected result, got handle: {state.get('handle')}"
    assert isinstance(state.get("result"), dict), state.get("result")
    assert "value" in state["result"], state["result"]


@then("not a ClassifyHandle")
def step_then_not_a_handle(context):
    state = _state(context)
    assert state.get("handle") is None, state.get("handle")


@then("the classification should still attempt")
def step_then_classification_attempted(context):
    state = _state(context)
    agent: Optional[_MockAgent] = state.get("agent")
    assert agent is not None, "Mock agent was not created"
    assert agent.calls, "Expected at least one LLM call"


@then("the result should be a ClassifyHandle")
def step_then_result_is_handle(context):
    state = _state(context)
    assert isinstance(state.get("handle"), ClassifyHandle), state.get("handle")


@then("the handle can be called multiple times")
def step_then_handle_callable(context):
    state = _state(context)
    handle: ClassifyHandle = state["handle"]
    out1 = handle("first")
    out2 = handle("second")
    assert out1 is not None and out2 is not None


@then("the internal agent should use temperature {temperature:f}")
def step_then_internal_agent_temperature(context, temperature):
    state = _state(context)
    assert state["agent_configs"], "No agent config captured"
    last = state["agent_configs"][-1]
    assert float(last.get("temperature")) == float(temperature), last


@then('the internal agent should use model "{model}"')
def step_then_internal_agent_model(context, model):
    state = _state(context)
    assert state["agent_configs"], "No agent config captured"
    last = state["agent_configs"][-1]
    assert last.get("model") == model, last
