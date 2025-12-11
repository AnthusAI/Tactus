"""
JSON operations feature step definitions.
"""

import json
import textwrap

from behave import given, then, when

from tactus.primitives.json import JsonPrimitive
from tactus.primitives.state import StatePrimitive


def _json_state(context):
    if not hasattr(context, "json_state"):
        context.json_state = {}
    return context.json_state


def _ensure_state(context):
    if not hasattr(context, "state") or context.state is None:
        context.state = StatePrimitive()
    return context.state


@given("the JSON primitive is initialized")
def step_impl(context):
    _json_state(context)["primitive"] = JsonPrimitive()


@given("a JSON string:")
def step_impl(context):
    _json_state(context)["json_input"] = textwrap.dedent(context.text or "")


@given("an invalid JSON string:")
def step_impl(context):
    _json_state(context)["json_input"] = textwrap.dedent(context.text or "")
    _json_state(context)["invalid"] = True


@when("I parse the JSON")
def step_impl(context):
    primitive = _json_state(context)["primitive"]
    data = primitive.decode(_json_state(context)["json_input"])
    context.json_result = data


@when("I try to parse the JSON")
def step_impl(context):
    primitive = _json_state(context)["primitive"]
    try:
        context.json_result = primitive.decode(_json_state(context)["json_input"])
        context.json_error = None
    except Exception as exc:
        context.json_result = None
        context.json_error = exc


@then("I should have a Python dict")
def step_impl(context):
    assert isinstance(context.json_result, dict)


@then('field "{field}" should equal "{value}"')
def step_impl(context, field, value):
    assert context.json_result[field] == value


@then('field "{field}" should equal {number:d}')
def step_impl(context, field, number):
    assert context.json_result[field] == number


@then('field "{field}" should be true')
def step_impl(context, field):
    assert context.json_result[field] is True


@then('field "{field}" should be a list')
def step_impl(context, field):
    assert isinstance(context.json_result[field], list)


@then("the list should have {count:d} elements")
def step_impl(context, count):
    items = context.json_result.get("items") or []
    assert len(items) == count


@then("the first element should be {value:d}")
def step_impl(context, value):
    items = context.json_result.get("items") or []
    assert items[0] == value


@then('I should be able to access "{path}"')
def step_impl(context, path):
    keys = path.split(".")
    data = context.json_result
    for key in keys:
        data = data[key]
    assert data is not None


@then('"{path}" should equal "{expected}"')
def step_impl(context, path, expected):
    keys = path.split(".")
    data = context.json_result
    for key in keys:
        data = data[key]
    assert data == expected


@then("a JSON parse error should be raised")
def step_impl(context):
    assert context.json_error is not None


@then("the workflow can handle the error")
def step_impl(context):
    assert context.json_error is not None


@given("a Python dict:")
def step_impl(context):
    _json_state(context)["python_dict"] = {row["key"]: row["value"] for row in context.table}


@when("I convert to JSON")
def step_impl(context):
    primitive = _json_state(context)["primitive"]
    data = _json_state(context)["python_dict"]
    context.json_string = primitive.encode(data)


@then("the result should be valid JSON string")
def step_impl(context):
    json.loads(context.json_string)


@then("parsing it back should give the original data")
def step_impl(context):
    parsed = json.loads(context.json_string)
    assert parsed == _json_state(context)["python_dict"]


@given("a JSON string with nested objects:")
def step_impl(context):
    _json_state(context)["json_input"] = textwrap.dedent(context.text or "")


@given("a data structure with nested objects")
def step_impl(context):
    _json_state(context)["pretty_data"] = {
        "user": {
            "id": 1,
            "profile": {
                "name": "Ada",
                "skills": ["python", "lua"],
            },
        }
    }


@when("I convert to JSON with pretty=true")
def step_impl(context):
    data = _json_state(context)["pretty_data"]
    context.pretty_json = json.dumps(data, indent=2)


@then("the output should be formatted with indentation")
def step_impl(context):
    assert '\n  "' in context.pretty_json


@then("it should be human-readable")
def step_impl(context):
    assert context.pretty_json.startswith("{\n  ")


@given("a JSON schema:")
def step_impl(context):
    _json_state(context)["schema"] = json.loads(textwrap.dedent(context.text or ""))


def _validate(schema, data):
    if schema.get("type") == "object":
        if not isinstance(data, dict):
            return False
        required = schema.get("required", [])
        for key in required:
            if key not in data:
                return False
        properties = schema.get("properties", {})
        for key, subschema in properties.items():
            if key in data:
                if subschema.get("type") == "string" and not isinstance(data[key], str):
                    return False
                if subschema.get("type") == "number" and not isinstance(data[key], (int, float)):
                    return False
        return True
    return False


@when("I validate JSON data against the schema")
def step_impl(context):
    schema = _json_state(context)["schema"]
    valid_data = {"name": "Alice", "age": 30}
    invalid_data = {"age": "unknown"}
    context.validation_results = {
        "valid": _validate(schema, valid_data),
        "invalid": _validate(schema, invalid_data),
    }


@then("valid data should pass validation")
def step_impl(context):
    assert context.validation_results["valid"] is True


@then("invalid data should fail validation")
def step_impl(context):
    assert context.validation_results["invalid"] is False


@when('I set state "{key}" to parsed JSON:')
def step_impl(context, key):
    data = json.loads(textwrap.dedent(context.text or ""))
    _ensure_state(context).set(key, data)
    _json_state(context)["state_key"] = key


@then("I can access {path} directly")
def step_impl(context, path):
    key = _json_state(context)["state_key"]
    data = _ensure_state(context).get(key)
    parts = path.split(".")
    if parts and parts[0] == key:
        parts = parts[1:]
    for part in parts:
        data = data.get(part)
    assert data is not None


@then('converting state "{key}" back to JSON should work')
def step_impl(context, key):
    data = _ensure_state(context).get(key)
    json.dumps(data)


@then('state "{key}" should be a dict')
def step_impl(context, key):
    value = _ensure_state(context).get(key)
    assert isinstance(value, dict)
