"""Tests for IDE assistant file tools."""

import sys
from pathlib import Path

import pytest

backend_path = Path(__file__).resolve().parents[2] / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

from assistant_tools import (  # noqa: E402
    FileToolsError,
    PathSecurityError,
    validate_path,
    read_file,
    list_files,
    search_files,
    write_file,
    edit_file,
    delete_file,
    move_file,
    copy_file,
)


@pytest.fixture
def workspace_root(tmp_path):
    return str(tmp_path.resolve())


def test_validate_path_allows_inside_workspace(workspace_root, tmp_path):
    target = validate_path(workspace_root, "nested/file.txt")
    assert target == tmp_path / "nested" / "file.txt"


def test_validate_path_rejects_outside_workspace(workspace_root):
    with pytest.raises(PathSecurityError):
        validate_path(workspace_root, "/etc/passwd")


def test_read_file_missing_raises(workspace_root):
    with pytest.raises(FileToolsError):
        read_file(workspace_root, "missing.txt")


def test_read_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        read_file(workspace_root, "/etc/passwd")


def test_read_file_directory_raises(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()
    with pytest.raises(FileToolsError):
        read_file(workspace_root, "folder")


def test_read_file_reads_content(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    assert read_file(workspace_root, "file.txt") == "hello"


def test_write_file_creates_and_updates(workspace_root, tmp_path):
    result = write_file(workspace_root, "file.txt", "hello")
    assert result["created"] is True
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == "hello"

    result = write_file(workspace_root, "file.txt", "updated")
    assert result["created"] is False
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == "updated"


def test_list_files_with_entries(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    entries = list_files(workspace_root, ".")
    names = {entry["name"] for entry in entries}

    assert {"file.txt", "folder"}.issubset(names)


def test_list_files_missing_directory_raises(workspace_root):
    with pytest.raises(FileToolsError):
        list_files(workspace_root, "missing")


def test_list_files_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        list_files(workspace_root, "/etc")


def test_list_files_stat_failure_skips_entry(workspace_root, monkeypatch, caplog):
    class BadEntry:
        name = "bad.txt"

        def stat(self):
            raise OSError("stat failed")

        def is_dir(self):
            return False

        def is_file(self):
            return True

        def relative_to(self, root):
            return Path("bad.txt")

    monkeypatch.setattr(Path, "iterdir", lambda self: iter([BadEntry()]))

    with caplog.at_level("WARNING"):
        entries = list_files(workspace_root, ".")

    assert entries == []
    assert "Failed to stat" in caplog.text


def test_list_files_not_directory_raises(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(FileToolsError):
        list_files(workspace_root, "file.txt")


def test_search_files_matches_pattern(workspace_root, tmp_path):
    (tmp_path / "a.tac").write_text("x", encoding="utf-8")
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    (tmp_path / "dir.tac").mkdir()

    matches = search_files(workspace_root, "*.tac")

    assert matches == ["a.tac"]


def test_search_files_missing_directory_raises(workspace_root):
    with pytest.raises(FileToolsError):
        search_files(workspace_root, "*.tac", path="missing")


def test_search_files_not_directory_raises(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("y", encoding="utf-8")
    with pytest.raises(FileToolsError):
        search_files(workspace_root, "*.txt", path="file.txt")


def test_search_files_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        search_files(workspace_root, "*.tac", path="/etc")


def test_search_files_glob_failure_raises(workspace_root, monkeypatch):
    monkeypatch.setattr(
        Path,
        "glob",
        lambda self, pattern: (_ for _ in ()).throw(OSError("boom")),
    )

    with pytest.raises(FileToolsError):
        search_files(workspace_root, "*.tac")


def test_edit_file_replaces_content(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello world", encoding="utf-8")

    result = edit_file(workspace_root, "file.txt", "world", "there")

    assert result["replacements"] == 1
    assert (tmp_path / "file.txt").read_text(encoding="utf-8") == "hello there"


def test_edit_file_missing_string_raises(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    with pytest.raises(FileToolsError):
        edit_file(workspace_root, "file.txt", "missing", "new")


def test_edit_file_missing_file_raises(workspace_root):
    with pytest.raises(FileToolsError):
        edit_file(workspace_root, "missing.txt", "old", "new")


def test_edit_file_not_file_raises(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()
    with pytest.raises(FileToolsError):
        edit_file(workspace_root, "folder", "old", "new")


def test_edit_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        edit_file(workspace_root, "/etc/passwd", "old", "new")


def test_delete_file_removes(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    result = delete_file(workspace_root, "file.txt")

    assert result["deleted"] is True
    assert not (tmp_path / "file.txt").exists()


def test_delete_file_directory_raises(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()

    with pytest.raises(FileToolsError):
        delete_file(workspace_root, "folder")


def test_delete_file_missing_raises(workspace_root):
    with pytest.raises(FileToolsError):
        delete_file(workspace_root, "missing.txt")


def test_delete_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        delete_file(workspace_root, "/etc/passwd")


def test_move_file_moves(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    result = move_file(workspace_root, "file.txt", "moved/file.txt")

    assert result["moved"] is True
    assert (tmp_path / "moved" / "file.txt").exists()


def test_move_file_destination_exists_raises(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "dest.txt").write_text("exists", encoding="utf-8")

    with pytest.raises(FileToolsError):
        move_file(workspace_root, "file.txt", "dest.txt")


def test_move_file_missing_source_raises(workspace_root):
    with pytest.raises(FileToolsError):
        move_file(workspace_root, "missing.txt", "dest.txt")


def test_move_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        move_file(workspace_root, "/etc/passwd", "dest.txt")


def test_copy_file_copies(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")

    result = copy_file(workspace_root, "file.txt", "copy.txt")

    assert result["copied"] is True
    assert (tmp_path / "copy.txt").read_text(encoding="utf-8") == "hello"


def test_copy_file_source_directory_raises(workspace_root, tmp_path):
    (tmp_path / "folder").mkdir()

    with pytest.raises(FileToolsError):
        copy_file(workspace_root, "folder", "copy.txt")


def test_copy_file_missing_source_raises(workspace_root):
    with pytest.raises(FileToolsError):
        copy_file(workspace_root, "missing.txt", "copy.txt")


def test_copy_file_destination_exists_raises(workspace_root, tmp_path):
    (tmp_path / "file.txt").write_text("hello", encoding="utf-8")
    (tmp_path / "copy.txt").write_text("exists", encoding="utf-8")

    with pytest.raises(FileToolsError):
        copy_file(workspace_root, "file.txt", "copy.txt")


def test_copy_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        copy_file(workspace_root, "/etc/passwd", "copy.txt")


def test_write_file_outside_workspace_raises(workspace_root):
    with pytest.raises(PathSecurityError):
        write_file(workspace_root, "/etc/passwd", "data")


def test_write_file_failure_raises(workspace_root, monkeypatch):
    monkeypatch.setattr(
        "builtins.open", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fail"))
    )

    with pytest.raises(FileToolsError):
        write_file(workspace_root, "file.txt", "data")
