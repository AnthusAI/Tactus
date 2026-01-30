"""Tests for stdlib file, csv, and tsv helpers."""

from pathlib import Path

import pytest

import tactus.stdlib.io.file as file_io
import tactus.stdlib.io.csv as csv_io
import tactus.stdlib.io.tsv as tsv_io


class FakeContext:
    def __init__(self, base_path: Path):
        self.base_path = base_path

    def validate_path(self, path: str) -> str:
        p = Path(path)
        if p.is_absolute() or ".." in p.parts:
            raise PermissionError(f"Invalid path: {path}")
        return str(self.base_path / path)


@pytest.fixture
def io_context(tmp_path, monkeypatch):
    ctx = FakeContext(tmp_path)
    monkeypatch.setattr(file_io, "_ctx", ctx, raising=False)
    monkeypatch.setattr(csv_io, "_ctx", ctx, raising=False)
    monkeypatch.setattr(tsv_io, "_ctx", ctx, raising=False)
    return tmp_path


def test_file_read_write_exists(io_context):
    file_io.write("notes.txt", "hello")

    assert file_io.exists("notes.txt") is True
    assert file_io.read("notes.txt") == "hello"
    assert file_io.exists("missing.txt") is False


def test_file_exists_denies_invalid_path(io_context):
    assert file_io.exists("../secrets.txt") is False


def test_file_read_write_without_context(tmp_path, monkeypatch):
    monkeypatch.setattr(file_io, "_ctx", None, raising=False)
    monkeypatch.chdir(tmp_path)

    file_io.write("nested/notes.txt", "hello")
    assert file_io.read("nested/notes.txt") == "hello"


def test_csv_write_and_read(io_context):
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    csv_io.write("data.csv", data)

    rows = csv_io.read("data.csv")

    assert rows == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]


def test_csv_write_with_headers(io_context):
    data = [{"name": "Alice", "age": 30}]
    csv_io.write("data.csv", data, {"headers": ["age", "name"]})

    content = Path(io_context / "data.csv").read_text(encoding="utf-8")
    assert content.splitlines()[0] == "age,name"


def test_csv_write_empty_raises(io_context):
    with pytest.raises(ValueError):
        csv_io.write("empty.csv", [])


def test_tsv_write_and_read(io_context):
    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    tsv_io.write("data.tsv", data)

    rows = tsv_io.read("data.tsv")

    assert rows == [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]


def test_tsv_write_with_headers(io_context):
    data = [{"name": "Alice", "age": 30}]
    tsv_io.write("data.tsv", data, {"headers": ["age", "name"]})

    content = Path(io_context / "data.tsv").read_text(encoding="utf-8")
    assert content.splitlines()[0] == "age\tname"


def test_tsv_write_empty_raises(io_context):
    with pytest.raises(ValueError):
        tsv_io.write("empty.tsv", [])
