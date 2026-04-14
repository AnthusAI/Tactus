import warnings

import pytest

from tactus.primitives.file import FilePrimitive


class DummyExecutionContext:
    def __init__(self, inside=False):
        self._inside_checkpoint = inside


def test_read_write_exists_size(tmp_path):
    base = tmp_path / "workspace"
    primitive = FilePrimitive(base_path=str(base))

    exists_before_write = primitive.exists("data.txt")
    assert exists_before_write is False

    write_succeeded = primitive.write("data.txt", "hello")
    assert write_succeeded is True
    exists_after_write = primitive.exists("data.txt")
    assert exists_after_write is True
    file_contents = primitive.read("data.txt")
    assert file_contents == "hello"
    file_size = primitive.size("data.txt")
    assert file_size == 5


def test_read_missing_raises(tmp_path):
    primitive = FilePrimitive(base_path=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="File not found"):
        primitive.read("missing.txt")


def test_read_error_raises_ioerror(tmp_path, monkeypatch):
    primitive = FilePrimitive(base_path=str(tmp_path))

    def bad_open(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", bad_open)

    with pytest.raises(IOError, match="Failed to read file"):
        primitive.read("data.txt")


def test_size_missing_raises(tmp_path):
    primitive = FilePrimitive(base_path=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="File not found"):
        primitive.size("missing.txt")


def test_resolve_path_accepts_absolute(tmp_path):
    primitive = FilePrimitive(base_path=str(tmp_path))
    resolved = primitive._resolve_path(str(tmp_path / "abs.txt"))
    assert resolved == (tmp_path / "abs.txt").resolve()


def test_resolve_path_rejects_traversal(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    primitive = FilePrimitive(base_path=str(base))

    with pytest.raises(ValueError, match="Path traversal detected"):
        primitive._resolve_path("../outside.txt")


def test_determinism_warning_emitted(tmp_path):
    primitive = FilePrimitive(base_path=str(tmp_path), execution_context=DummyExecutionContext())

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        primitive.exists("data.txt")

    warning_messages = [str(w.message) for w in recorded]
    contains_determinism_warning = any(
        "DETERMINISM WARNING" in warning_message for warning_message in warning_messages
    )
    assert contains_determinism_warning


def test_repr_includes_base_path(tmp_path):
    primitive = FilePrimitive(base_path=str(tmp_path))
    base_path = str(tmp_path)
    primitive_repr = repr(primitive)
    assert base_path in primitive_repr


def test_write_error_raises_ioerror(tmp_path, monkeypatch):
    primitive = FilePrimitive(base_path=str(tmp_path))

    def bad_open(*_args, **_kwargs):
        raise OSError("boom")

    monkeypatch.setattr("builtins.open", bad_open)

    with pytest.raises(IOError, match="Failed to write file"):
        primitive.write("data.txt", "hello")
