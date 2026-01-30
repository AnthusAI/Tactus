"""Tests for IDE text editor tool."""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

import text_editor_tool  # noqa: E402
from text_editor_tool import (  # noqa: E402
    view_file,
    view_directory,
    str_replace_based_edit_tool,
)
from assistant_tools import FileToolsError, PathSecurityError  # noqa: E402


@pytest.fixture
def workspace_root(tmp_path):
    return str(tmp_path.resolve())


def test_view_file_with_line_numbers(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one\ntwo\n", encoding="utf-8")

    output = view_file(workspace_root, "note.txt")

    assert output.splitlines() == ["1: one", "2: two"]


def test_view_file_with_range(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")

    output = view_file(workspace_root, "note.txt", [2, -1])

    assert output.splitlines() == ["2: two", "3: three"]


def test_view_file_invalid_range_raises(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one\n", encoding="utf-8")

    with pytest.raises(FileToolsError):
        view_file(workspace_root, "note.txt", [0, 1])


def test_view_file_range_exceeds_length_raises(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one\n", encoding="utf-8")

    with pytest.raises(FileToolsError):
        view_file(workspace_root, "note.txt", [3, 4])


def test_view_file_missing_raises(workspace_root):
    with pytest.raises(FileToolsError):
        view_file(workspace_root, "missing.txt")


def test_view_file_directory_path_raises(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()

    with pytest.raises(FileToolsError):
        view_file(workspace_root, "folder")


def test_view_file_unexpected_error_wrapped(workspace_root, tmp_path, monkeypatch):
    (tmp_path / "note.txt").write_text("one\n", encoding="utf-8")

    def raise_open(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr("builtins.open", raise_open)

    with pytest.raises(FileToolsError, match="Failed to read file"):
        view_file(workspace_root, "note.txt")


def test_view_directory_listing(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "note.txt").write_text("one", encoding="utf-8")

    output = view_directory(workspace_root, ".")

    assert "[DIR]  folder/" in output
    assert "[FILE] note.txt" in output


def test_view_directory_empty(workspace_root):
    output = view_directory(workspace_root, ".")

    assert "is empty" in output


def test_view_directory_missing_raises(workspace_root):
    with pytest.raises(FileToolsError):
        view_directory(workspace_root, "missing")


def test_view_directory_file_path_raises(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one", encoding="utf-8")

    with pytest.raises(FileToolsError):
        view_directory(workspace_root, "note.txt")


def test_view_directory_handles_entry_errors(workspace_root, tmp_path, monkeypatch):
    (tmp_path / "folder").mkdir()

    class FaultyEntry:
        name = "secret"

        def is_dir(self):
            raise OSError("nope")

    def fake_iterdir(_self):
        return [FaultyEntry()]

    monkeypatch.setattr(Path, "iterdir", fake_iterdir)

    output = view_directory(workspace_root, "folder")

    assert "[????] secret" in output


def test_view_directory_unexpected_error_wrapped(workspace_root, monkeypatch):
    def raise_validate(*_args, **_kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(text_editor_tool, "validate_path", raise_validate)

    with pytest.raises(FileToolsError, match="Failed to list directory"):
        view_directory(workspace_root, ".")


def test_str_replace_based_edit_tool_file(workspace_root, tmp_path):
    (tmp_path / "note.txt").write_text("one\n", encoding="utf-8")

    output = str_replace_based_edit_tool(workspace_root, "view", "note.txt")

    assert output.strip() == "1: one"


def test_str_replace_based_edit_tool_directory_with_range_error(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()

    output = str_replace_based_edit_tool(workspace_root, "view", "folder", [1, 2])

    assert "view_range parameter not supported" in output


def test_str_replace_based_edit_tool_directory_listing(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()
    (tmp_path / "note.txt").write_text("one", encoding="utf-8")

    output = str_replace_based_edit_tool(workspace_root, "view", ".")

    assert "[DIR]  folder/" in output
    assert "[FILE] note.txt" in output


def test_str_replace_based_edit_tool_path_neither_file_nor_dir(workspace_root, monkeypatch):
    class FakeTarget:
        def is_file(self):
            return False

        def is_dir(self):
            return False

    monkeypatch.setattr(text_editor_tool, "validate_path", lambda *_args, **_kwargs: FakeTarget())

    output = str_replace_based_edit_tool(workspace_root, "view", "unknown")

    assert "neither file nor directory" in output


def test_str_replace_based_edit_tool_handles_path_security_error(workspace_root, monkeypatch):
    def raise_path(*_args, **_kwargs):
        raise PathSecurityError("escape")

    monkeypatch.setattr(text_editor_tool, "validate_path", raise_path)

    output = str_replace_based_edit_tool(workspace_root, "view", "oops")

    assert output == "Error: escape"


def test_str_replace_based_edit_tool_handles_file_tools_error(workspace_root, monkeypatch):
    class FakeTarget:
        def is_file(self):
            return True

        def is_dir(self):
            return False

    def raise_file(_root, _path, _view_range=None):
        raise FileToolsError("bad file")

    monkeypatch.setattr(text_editor_tool, "validate_path", lambda *_args, **_kwargs: FakeTarget())
    monkeypatch.setattr(text_editor_tool, "view_file", raise_file)

    output = str_replace_based_edit_tool(workspace_root, "view", "note.txt")

    assert output == "Error: bad file"


def test_str_replace_based_edit_tool_handles_unexpected_error(workspace_root, monkeypatch):
    class FakeTarget:
        def is_file(self):
            return True

        def is_dir(self):
            return False

    def raise_boom(_root, _path, _view_range=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(text_editor_tool, "validate_path", lambda *_args, **_kwargs: FakeTarget())
    monkeypatch.setattr(text_editor_tool, "view_file", raise_boom)

    output = str_replace_based_edit_tool(workspace_root, "view", "note.txt")

    assert output == "Error: Unexpected error: boom"


def test_str_replace_based_edit_tool_invalid_command(workspace_root):
    output = str_replace_based_edit_tool(workspace_root, "edit", "note.txt")

    assert "not supported" in output
