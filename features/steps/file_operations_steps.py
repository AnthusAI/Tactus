"""
File operations feature step definitions.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from behave import given, then, when

from tactus.primitives.file import FilePrimitive

from features.environment import ensure_temp_dir


def _state(context):
    if not hasattr(context, "file_state"):
        context.file_state = {}
    return context.file_state


def _file(context) -> FilePrimitive:
    return _state(context)["file"]


@given("the file primitive is initialized")
def step_impl(context):
    workspace = ensure_temp_dir(context)
    state = _state(context)
    state["workspace"] = workspace
    state["file"] = FilePrimitive(base_path=str(workspace.resolve()))
    state["results"] = []
    state["last_filename"] = None
    state["last_written_content"] = None
    state["expected_file_count"] = 0


@given("a temporary workspace directory")
def step_impl(context):
    ensure_temp_dir(context)


@given('a file "{filename}" with content:')
def step_impl(context, filename):
    content = textwrap.dedent(context.text or "")
    state = _state(context)
    state["last_filename"] = filename
    state["last_written_content"] = content
    _file(context).write(filename, content)


@given('a file "{filename}" with content "{content}"')
def step_impl(context, filename, content):
    state = _state(context)
    state["last_filename"] = filename
    state["last_written_content"] = content
    _file(context).write(filename, content)


@when('I read the file "{filename}"')
def step_impl(context, filename):
    context.file_content = _file(context).read(filename)


@then("the content should match the original text")
def step_impl(context):
    expected = _state(context).get("last_written_content")
    assert context.file_content == expected


@when('I write "{text}" to file "{filename}"')
def step_impl(context, text, filename):
    state = _state(context)
    state["last_filename"] = filename
    state["last_written_content"] = text
    _file(context).write(filename, text)


@then('the file "{filename}" should exist')
def step_impl(context, filename):
    assert _file(context).exists(filename)


@then('its content should be "{expected}"')
def step_impl(context, expected):
    filename = _state(context).get("last_filename")
    content = _file(context).read(filename)
    assert content == expected


@when('I append "{text}" to file "{filename}"')
def step_impl(context, text, filename):
    state = _state(context)
    state["last_filename"] = filename
    current = _file(context).read(filename)
    new_content = current.rstrip("\n") + "\n" + text
    _file(context).write(filename, new_content)
    state["last_written_content"] = new_content


@then("the file should contain both lines:")
def step_impl(context):
    filename = _state(context).get("last_filename")
    expected = textwrap.dedent(context.text or "").strip()
    actual = _file(context).read(filename).strip()
    assert actual == expected


@when('I read JSON from "{filename}"')
def step_impl(context, filename):
    content = _file(context).read(filename)
    context.json_result = json.loads(content)


@then("I should have a parsed object")
def step_impl(context):
    assert isinstance(context.json_result, dict)


@then('the object should have field "{field}" with value "{value}"')
def step_impl(context, field, value):
    target = context.json_result.get(field)
    try:
        expected = json.loads(value)
    except json.JSONDecodeError:
        expected = value
    assert target == expected


@given("a data structure:")
def step_impl(context):
    _state(context)["data_structure"] = {row["field"]: row["value"] for row in context.table}


@when('I write it as JSON to "{filename}"')
def step_impl(context, filename):
    data = _state(context)["data_structure"]
    payload = json.dumps(data)
    state = _state(context)
    state["last_filename"] = filename
    _file(context).write(filename, payload)


@then("the file should contain valid JSON")
def step_impl(context):
    filename = _state(context).get("last_filename")
    content = _file(context).read(filename)
    json.loads(content)


@then("reading it back should give the same structure")
def step_impl(context):
    filename = _state(context).get("last_filename")
    content = _file(context).read(filename)
    expected = _state(context).get("data_structure")
    assert json.loads(content) == expected


@when('I try to read a non-existent file "{filename}"')
def step_impl(context, filename):
    try:
        _file(context).read(filename)
        context.file_error = None
    except Exception as exc:
        context.file_error = exc


@then("a file not found error should be raised")
def step_impl(context):
    assert isinstance(context.file_error, FileNotFoundError)


@then("the workflow can handle the error gracefully")
def step_impl(context):
    assert context.file_error is not None


@given('files in directory "{folder}/":')
def step_impl(context, folder):
    workspace = _state(context)["workspace"]
    target_dir = Path(workspace, folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    for row in context.table:
        (target_dir / row["filename"]).write_text(row["content"], encoding="utf-8")
    _state(context)["expected_file_count"] = len(context.table.rows)


@when('I process all files in "{folder}/"')
def step_impl(context, folder):
    workspace = _state(context)["workspace"]
    target_dir = Path(workspace, folder)
    results = []
    for path in sorted(target_dir.iterdir()):
        if path.is_file():
            results.append(path.read_text(encoding="utf-8"))
    _state(context)["results"] = results


@then("each file should be read and processed")
def step_impl(context):
    expected = _state(context).get("expected_file_count", 0)
    assert len(_state(context)["results"]) == expected


@then("results should be collected")
def step_impl(context):
    results = _state(context)["results"]
    assert all(bool(result) for result in results)
