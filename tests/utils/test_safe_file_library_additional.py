import os

import pytest

from tactus.utils.safe_file_library import (
    PathValidator,
    LuaList,
    create_safe_file_library,
    _lua_to_python,
)


def test_path_validator_allows_base_path(tmp_path):
    validator = PathValidator(str(tmp_path))
    resolved = validator.validate(".")
    assert resolved == os.path.realpath(str(tmp_path))


def test_path_validator_blocks_traversal(tmp_path):
    validator = PathValidator(str(tmp_path))
    with pytest.raises(PermissionError):
        validator.validate("../outside.txt")


def test_safe_file_library_exists_handles_permission_error(tmp_path):
    lib = create_safe_file_library(str(tmp_path))
    assert lib["exists"]("../outside.txt") is False


def test_lua_list_methods_and_indexing():
    lua_list = LuaList(["a", "b"])

    assert lua_list["len"]() == 2
    assert lua_list["get"](1) == "b"
    assert lua_list["get"](1.0) == "b"
    assert lua_list[1] == "b"
    assert lua_list[1.0] == "b"
    assert list(iter(lua_list)) == ["a", "b"]

    with pytest.raises(KeyError):
        _ = lua_list["unknown"]


def test_lua_to_python_converts_table_like_objects():
    class Table:
        def __init__(self, data):
            self._data = data

        def items(self):
            return list(self._data.items())

        def __getitem__(self, key):
            return self._data[key]

    array_table = Table({1: "a", 2: "b"})
    dict_table = Table({"x": 1, "y": 2})

    assert _lua_to_python(array_table) == ["a", "b"]
    assert _lua_to_python(dict_table) == {"x": 1, "y": 2}


def test_lua_to_python_handles_nested_lists():
    assert _lua_to_python({"a": [1, 2]}) == {"a": [1, 2]}


def test_lua_to_python_values_only_object():
    class ValuesOnly:
        def values(self):
            return [1, 2, 3]

    assert _lua_to_python(ValuesOnly()) == [1, 2, 3]


def test_csv_write_handles_lua_tables(tmp_path):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))

    class LuaHeaders:
        def values(self):
            return ["a", "b"]

    class LuaOptions:
        def items(self):
            return [("headers", LuaHeaders())]

    class LuaRow:
        def items(self):
            return [("a", "1"), ("b", "2")]

        def keys(self):
            return ["a", "b"]

    class LuaTable:
        def values(self):
            return [LuaRow()]

    lib["write"]("data.csv", LuaTable(), LuaOptions())

    content = (tmp_path / "data.csv").read_text()
    assert content.splitlines()[0] == "a,b"


def test_csv_write_errors_when_headers_missing(tmp_path):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))

    with pytest.raises(ValueError):
        lib["write"]("data.csv", ["not-dict"])


def test_csv_write_infers_headers_from_dict(tmp_path):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))
    lib["write"]("data.csv", [{"a": "1", "b": "2"}])

    content = (tmp_path / "data.csv").read_text()
    assert content.splitlines()[0] == "a,b"


def test_csv_write_infers_headers_from_weird_dict(tmp_path, monkeypatch):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))
    row = {"a": "1", "b": "2"}
    real_hasattr = hasattr

    def fake_hasattr(obj, name):
        if obj is row and name == "keys":
            return False
        return real_hasattr(obj, name)

    monkeypatch.setattr("builtins.hasattr", fake_hasattr)

    lib["write"]("data.csv", [row])

    content = (tmp_path / "data.csv").read_text()
    assert content.splitlines()[0] == "a,b"


def test_csv_write_converts_row_items(tmp_path):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))

    class Row:
        def items(self):
            return [("a", "1"), ("b", "2")]

        def keys(self):
            return ["a", "b"]

    lib["write"]("data.csv", [Row()])
    content = (tmp_path / "data.csv").read_text()
    assert content.splitlines()[1] == "1,2"


def test_csv_write_skips_items_branch_when_hasattr_false(tmp_path, monkeypatch):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))
    row = {"a": "1", "b": "2"}
    real_hasattr = hasattr

    def fake_hasattr(obj, name):
        if obj is row and name == "items":
            return False
        return real_hasattr(obj, name)

    monkeypatch.setattr("builtins.hasattr", fake_hasattr)

    lib["write"]("data.csv", [row])
    content = (tmp_path / "data.csv").read_text()
    assert content.splitlines()[1] == "1,2"


def test_tsv_write_infers_headers_from_dict(tmp_path):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))
    lib["write"]("data.tsv", [{"a": "1", "b": "2"}])

    content = (tmp_path / "data.tsv").read_text()
    assert content.splitlines()[0] == "a\tb"


def test_tsv_write_infers_headers_from_weird_dict(tmp_path, monkeypatch):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))
    row = {"a": "1", "b": "2"}
    real_hasattr = hasattr

    def fake_hasattr(obj, name):
        if obj is row and name == "keys":
            return False
        return real_hasattr(obj, name)

    monkeypatch.setattr("builtins.hasattr", fake_hasattr)

    lib["write"]("data.tsv", [row])

    content = (tmp_path / "data.tsv").read_text()
    assert content.splitlines()[0] == "a\tb"


def test_tsv_write_converts_row_items(tmp_path):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))

    class Row:
        def items(self):
            return [("a", "1"), ("b", "2")]

        def keys(self):
            return ["a", "b"]

    lib["write"]("data.tsv", [Row()])
    content = (tmp_path / "data.tsv").read_text()
    assert content.splitlines()[1] == "1\t2"


def test_tsv_write_missing_headers_raises(tmp_path):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))

    class Row:
        pass

    with pytest.raises(ValueError):
        lib["write"]("data.tsv", [Row()])


def test_tsv_write_skips_items_branch_when_hasattr_false(tmp_path, monkeypatch):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))
    row = {"a": "1", "b": "2"}
    real_hasattr = hasattr

    def fake_hasattr(obj, name):
        if obj is row and name == "items":
            return False
        return real_hasattr(obj, name)

    monkeypatch.setattr("builtins.hasattr", fake_hasattr)

    try:
        lib["write"]("data.tsv", [row])
    except OSError as exc:
        if exc.errno == 28:
            pytest.skip("No space left on device")
        raise
    content = (tmp_path / "data.tsv").read_text()
    assert content.splitlines()[1] == "1\t2"


def test_tsv_write_handles_lua_tables(tmp_path):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))

    class LuaHeaders:
        def values(self):
            return ["a", "b"]

    class LuaOptions:
        def items(self):
            return [("headers", LuaHeaders())]

    class LuaRow:
        def items(self):
            return [("a", "1"), ("b", "2")]

        def keys(self):
            return ["a", "b"]

    class LuaTable:
        def values(self):
            return [LuaRow()]

    lib["write"]("data.tsv", LuaTable(), LuaOptions())

    content = (tmp_path / "data.tsv").read_text()
    assert content.splitlines()[0] == "a\tb"


def test_lua_to_python_items_exception_falls_back():
    class BadItems:
        def items(self):
            raise TypeError("nope")

    obj = BadItems()
    assert _lua_to_python(obj) is obj


def test_lua_to_python_values_exception_falls_back():
    class BadValues:
        def values(self):
            raise TypeError("nope")

    obj = BadValues()
    assert _lua_to_python(obj) is obj


def test_lua_to_python_non_sequential_int_keys():
    class Table:
        def __init__(self, data):
            self._data = data

        def items(self):
            return list(self._data.items())

    table = Table({1: "a", 3: "b"})
    assert _lua_to_python(table) == {1: "a", 3: "b"}


def test_lua_to_python_dict_passthrough():
    assert _lua_to_python({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}


def test_lua_to_python_dict_branch(monkeypatch):
    obj = {"a": 1}
    real_hasattr = hasattr

    def fake_hasattr(target, name):
        if target is obj and name in ("items", "values"):
            return False
        return real_hasattr(target, name)

    monkeypatch.setattr("builtins.hasattr", fake_hasattr)

    assert _lua_to_python(obj) == {"a": 1}


def test_hdf5_list_datasets(tmp_path):
    h5py = pytest.importorskip("h5py")
    numpy = pytest.importorskip("numpy")

    from tactus.utils.safe_file_library import create_safe_hdf5_library

    lib = create_safe_hdf5_library(str(tmp_path))
    file_path = tmp_path / "data.h5"

    try:
        with h5py.File(file_path, "w") as hdf5_file:
            hdf5_file.create_dataset("group/data", data=numpy.array([1, 2, 3]))
    except OSError as exc:
        if exc.errno == 28:
            pytest.skip("No space left on device")
        raise

    datasets = lib["list"]("data.h5")

    assert "group/data" in datasets


def test_csv_write_creates_parent_dirs(tmp_path):
    from tactus.utils.safe_file_library import create_safe_csv_library

    lib = create_safe_csv_library(str(tmp_path))
    lib["write"]("nested/output.csv", [{"name": "Alice"}])

    assert (tmp_path / "nested" / "output.csv").exists()


def test_tsv_write_creates_parent_dirs(tmp_path):
    from tactus.utils.safe_file_library import create_safe_tsv_library

    lib = create_safe_tsv_library(str(tmp_path))
    lib["write"]("nested/output.tsv", [{"name": "Alice"}])

    assert (tmp_path / "nested" / "output.tsv").exists()


def test_json_write_creates_parent_dirs(tmp_path):
    from tactus.utils.safe_file_library import create_safe_json_library

    lib = create_safe_json_library(str(tmp_path))
    lib["write"]("nested/output.json", {"name": "Alice"})

    assert (tmp_path / "nested" / "output.json").exists()


def test_parquet_write_creates_parent_dirs(tmp_path):
    pytest.importorskip("pyarrow")

    from tactus.utils.safe_file_library import create_safe_parquet_library

    lib = create_safe_parquet_library(str(tmp_path))
    lib["write"]("nested/output.parquet", [{"name": "Alice"}])

    assert (tmp_path / "nested" / "output.parquet").exists()


def test_hdf5_write_creates_parent_dirs(tmp_path):
    pytest.importorskip("h5py")
    pytest.importorskip("numpy")

    from tactus.utils.safe_file_library import create_safe_hdf5_library

    lib = create_safe_hdf5_library(str(tmp_path))
    lib["write"]("nested/output.h5", "data", [1, 2, 3])

    assert (tmp_path / "nested" / "output.h5").exists()


def test_excel_write_creates_parent_dirs(tmp_path):
    pytest.importorskip("openpyxl")

    from tactus.utils.safe_file_library import create_safe_excel_library

    lib = create_safe_excel_library(str(tmp_path))
    lib["write"]("nested/output.xlsx", [{"name": "Alice"}])

    assert (tmp_path / "nested" / "output.xlsx").exists()


def test_file_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_file_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.txt", "content")
    assert (tmp_path / "output.txt").read_text() == "content"


def test_csv_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_csv_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.csv", [{"name": "Alice"}])
    assert (tmp_path / "output.csv").exists()


def test_tsv_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_tsv_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.tsv", [{"name": "Alice"}])
    assert (tmp_path / "output.tsv").exists()


def test_json_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_json_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.json", {"name": "Alice"})
    assert (tmp_path / "output.json").exists()


def test_parquet_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    pytest.importorskip("pyarrow")

    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_parquet_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.parquet", [{"name": "Alice"}])
    assert (tmp_path / "output.parquet").exists()


def test_hdf5_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    pytest.importorskip("h5py")
    pytest.importorskip("numpy")

    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_hdf5_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.h5", "data", [1, 2, 3])
    assert (tmp_path / "output.h5").exists()


def test_excel_write_skips_parent_creation_when_dirname_empty(monkeypatch, tmp_path):
    pytest.importorskip("openpyxl")

    from tactus.utils import safe_file_library

    lib = safe_file_library.create_safe_excel_library(str(tmp_path))

    monkeypatch.setattr(safe_file_library.os.path, "dirname", lambda _path: "")
    monkeypatch.setattr(
        safe_file_library.os,
        "makedirs",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("makedirs called")),
    )

    lib["write"]("output.xlsx", [{"name": "Alice"}])
    assert (tmp_path / "output.xlsx").exists()
