"""BDD steps for IDE file tools."""

import os
import sys
import tempfile
from pathlib import Path
from behave import given, when, then

project_root = Path(__file__).resolve().parents[2]
backend_path = project_root / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from assistant_tools import (  # noqa: E402
    read_file,
    list_files,
    search_files,
    write_file,
    edit_file,
    delete_file,
    move_file,
    copy_file,
)
from text_editor_tool import view_file, str_replace_based_edit_tool  # noqa: E402


def _ensure_workspace(context):
    if hasattr(context, "workspace_root"):
        return
    temp_dir = tempfile.TemporaryDirectory()
    context._temp_workspace = temp_dir
    context.workspace_root = str(Path(temp_dir.name).resolve())


def _ensure_sample_file(context):
    _ensure_workspace(context)
    if not os.path.exists(_sample_path(context)):
        write_file(context.workspace_root, "sample.tac", "hello\nworld\n")


def _ensure_copied_file(context):
    _ensure_sample_file(context)
    if not os.path.exists(_copied_path(context)):
        copy_file(context.workspace_root, "sample.tac", "copies/sample_copy.tac")


def _ensure_moved_file(context):
    _ensure_sample_file(context)
    if not os.path.exists(_moved_path(context)):
        move_file(context.workspace_root, "sample.tac", "moved/sample_moved.tac")


def _sample_path(context):
    return os.path.join(context.workspace_root, "sample.tac")


def _moved_path(context):
    return os.path.join(context.workspace_root, "moved", "sample_moved.tac")


def _copied_path(context):
    return os.path.join(context.workspace_root, "copies", "sample_copy.tac")


@given("an IDE workspace with a sample file")
def step_create_workspace(context):
    _ensure_sample_file(context)


@when("I read the sample file")
def step_read_sample(context):
    context.read_content = read_file(context.workspace_root, "sample.tac")


@then("I should receive the file contents")
def step_verify_read(context):
    assert "hello" in context.read_content


@then("I can list files in the workspace")
def step_list_files(context):
    entries = list_files(context.workspace_root, ".")
    names = {entry["name"] for entry in entries}
    assert "sample.tac" in names


@when('I search for files with pattern "{pattern}"')
def step_search_files(context, pattern):
    context.search_results = search_files(context.workspace_root, pattern)


@then("I should see the sample file in results")
def step_verify_search(context):
    assert any(path.endswith("sample.tac") for path in context.search_results)


@when('I replace "{old}" with "{new}" in the sample file')
def step_edit_file(context, old, new):
    edit_file(context.workspace_root, "sample.tac", old, new)


@then('the file should contain "{text}"')
def step_verify_edit(context, text):
    content = read_file(context.workspace_root, "sample.tac")
    assert text in content


@when('I copy the sample file to "{dest}"')
def step_copy_file(context, dest):
    copy_file(context.workspace_root, "sample.tac", dest)


@when('I move the sample file to "{dest}"')
def step_move_file(context, dest):
    move_file(context.workspace_root, "sample.tac", dest)


@then("the copied file should exist")
def step_verify_copy(context):
    assert os.path.exists(_copied_path(context))


@then("the moved file should exist")
def step_verify_move(context):
    assert os.path.exists(_moved_path(context))


@when("I delete the copied file")
def step_delete_file(context):
    _ensure_copied_file(context)
    delete_file(context.workspace_root, "copies/sample_copy.tac")


@then("the copied file should be removed")
def step_verify_delete(context):
    assert not os.path.exists(_copied_path(context))


@when("I view the moved file")
def step_view_file(context):
    _ensure_moved_file(context)
    context.view_output = view_file(context.workspace_root, "moved/sample_moved.tac")


@then("the view should include line numbers")
def step_verify_view(context):
    assert "1: hi" in context.view_output or "1: hello" in context.view_output


@when("I view the workspace directory")
def step_view_directory(context):
    _ensure_moved_file(context)
    context.directory_output = str_replace_based_edit_tool(
        workspace_root=context.workspace_root,
        command="view",
        path=".",
    )


@then("the directory view should include the moved file")
def step_verify_directory_view(context):
    assert "moved/" in context.directory_output or "sample_moved.tac" in context.directory_output
