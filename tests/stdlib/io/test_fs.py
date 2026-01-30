"""Tests for tactus.io.fs helpers."""

import types

import pytest

import tactus.stdlib.io.fs as fs


@pytest.fixture
def fs_context(tmp_path, monkeypatch):
    ctx = types.SimpleNamespace(base_path=tmp_path)
    monkeypatch.setattr(fs, "_ctx", ctx, raising=False)
    return tmp_path


def test_list_dir_files_only(fs_context):
    (fs_context / "file.txt").write_text("hi", encoding="utf-8")
    (fs_context / "sub").mkdir()
    (fs_context / "sub" / "inner.txt").write_text("inside", encoding="utf-8")

    entries = fs.list_dir(".")

    assert entries == ["file.txt"]


def test_list_dir_dirs_only(fs_context):
    (fs_context / "sub").mkdir()
    (fs_context / "file.txt").write_text("hi", encoding="utf-8")

    entries = fs.list_dir(".", {"files_only": False, "dirs_only": True})

    assert entries == ["sub"]


def test_list_dir_includes_files_and_dirs(fs_context):
    (fs_context / "file.txt").write_text("hi", encoding="utf-8")
    (fs_context / "sub").mkdir()

    entries = fs.list_dir(".", {"files_only": False, "dirs_only": False})

    assert entries == ["file.txt", "sub"]


def test_list_dir_rejects_absolute_path(fs_context):
    with pytest.raises(PermissionError):
        fs.list_dir(str(fs_context))


def test_base_path_falls_back_to_cwd(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "_ctx", None, raising=False)
    monkeypatch.chdir(tmp_path)
    assert fs._base_path() == str(tmp_path)


def test_list_dir_rejects_traversal(fs_context):
    with pytest.raises(PermissionError):
        fs.list_dir("../outside")


def test_list_dir_missing_directory(fs_context):
    with pytest.raises(FileNotFoundError):
        fs.list_dir("missing")


def test_list_dir_skips_symlink_escape(fs_context):
    outside = fs_context.parent / "outside_target"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("nope", encoding="utf-8")

    link = fs_context / "link"
    link.symlink_to(outside, target_is_directory=True)

    entries = fs.list_dir(".", {"files_only": False, "dirs_only": False})
    assert "link" not in entries


def test_list_dir_rejects_symlink_target_outside_base(fs_context):
    outside = fs_context.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    link = fs_context / "outside_link"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PermissionError):
        fs.list_dir("outside_link")


def test_glob_matches_files(fs_context):
    (fs_context / "sub").mkdir()
    (fs_context / "sub" / "inner.txt").write_text("inside", encoding="utf-8")

    matches = fs.glob("sub/*.txt")

    assert matches == ["sub/inner.txt"]


def test_glob_matches_dirs(fs_context):
    (fs_context / "sub").mkdir()

    matches = fs.glob("sub*", {"files_only": False, "dirs_only": True})

    assert matches == ["sub"]


def test_glob_rejects_traversal(fs_context):
    with pytest.raises(PermissionError):
        fs.glob("../*.txt")


def test_glob_rejects_symlink_escape(fs_context):
    outside = fs_context.parent / "outside_glob"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("nope", encoding="utf-8")

    link = fs_context / "link"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PermissionError):
        fs.glob("link/*.txt")


def test_glob_skips_symlink_escape_target(fs_context):
    outside_file = fs_context.parent / "outside_match.txt"
    outside_file.write_text("nope", encoding="utf-8")

    link = fs_context / "hidden.txt"
    link.symlink_to(outside_file)

    matches = fs.glob("*.txt")
    assert matches == []


def test_glob_filters_directories(fs_context):
    (fs_context / "dir").mkdir()
    (fs_context / "file.txt").write_text("data", encoding="utf-8")

    matches = fs.glob("*", {"files_only": True, "dirs_only": False})
    assert "dir" not in matches


def test_glob_filters_files(fs_context):
    (fs_context / "dir").mkdir()
    (fs_context / "file.txt").write_text("data", encoding="utf-8")

    matches = fs.glob("*", {"files_only": False, "dirs_only": True})
    assert "file.txt" not in matches


def test_list_dir_sort_option_false(fs_context):
    (fs_context / "b.txt").write_text("b", encoding="utf-8")
    (fs_context / "a.txt").write_text("a", encoding="utf-8")

    entries = fs.list_dir(".", {"sort": False})
    assert set(entries) == {"a.txt", "b.txt"}


def test_glob_sort_option_false(fs_context):
    (fs_context / "b.txt").write_text("b", encoding="utf-8")
    (fs_context / "a.txt").write_text("a", encoding="utf-8")

    entries = fs.glob("*.txt", {"sort": False})
    assert set(entries) == {"a.txt", "b.txt"}
