"""
Tests for safe file I/O libraries.

Tests path validation, read/write operations, and format-specific functionality
for all supported file formats: File, Csv, Tsv, Json, Parquet, Hdf5, Excel.
"""

import json
import os

import pytest

from tactus.utils.safe_file_library import (
    PathValidator,
    create_safe_csv_library,
    create_safe_excel_library,
    create_safe_file_library,
    create_safe_hdf5_library,
    create_safe_json_library,
    create_safe_parquet_library,
    create_safe_tsv_library,
)


class TestPathValidator:
    """Test path validation and security."""

    def test_valid_relative_path(self, tmp_path):
        """Valid relative paths within base should work."""
        validator = PathValidator(str(tmp_path))
        test_file = tmp_path / "test.txt"
        test_file.touch()

        result = validator.validate("test.txt")
        assert result == str(test_file)

    def test_valid_nested_path(self, tmp_path):
        """Nested paths within base should work."""
        validator = PathValidator(str(tmp_path))
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        test_file = subdir / "test.txt"
        test_file.touch()

        result = validator.validate("subdir/test.txt")
        assert result == str(test_file)

    def test_directory_traversal_blocked(self, tmp_path):
        """Directory traversal attempts should be blocked."""
        validator = PathValidator(str(tmp_path))

        with pytest.raises(PermissionError, match="Access denied"):
            validator.validate("../etc/passwd")

    def test_absolute_path_outside_blocked(self, tmp_path):
        """Absolute paths outside base should be blocked."""
        validator = PathValidator(str(tmp_path))

        with pytest.raises(PermissionError, match="Access denied"):
            validator.validate("/etc/passwd")

    def test_symlink_traversal_blocked(self, tmp_path):
        """Symlinks pointing outside base should be blocked."""
        validator = PathValidator(str(tmp_path))

        # Create a symlink pointing outside
        link_path = tmp_path / "evil_link"
        try:
            os.symlink("/etc", str(link_path))
            with pytest.raises(PermissionError, match="Access denied"):
                validator.validate("evil_link/passwd")
        except OSError:
            # Skip if symlink creation not supported
            pytest.skip("Symlink creation not supported")


class TestFileLibrary:
    """Test raw text file operations."""

    def test_read_file(self, tmp_path):
        """Read text file."""
        lib = create_safe_file_library(str(tmp_path))
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        content = lib["read"]("test.txt")
        assert content == "Hello, World!"

    def test_write_file(self, tmp_path):
        """Write text file."""
        lib = create_safe_file_library(str(tmp_path))

        lib["write"]("output.txt", "Test content")

        result = (tmp_path / "output.txt").read_text()
        assert result == "Test content"

    def test_exists_true(self, tmp_path):
        """File.exists returns True for existing file."""
        lib = create_safe_file_library(str(tmp_path))
        test_file = tmp_path / "exists.txt"
        test_file.touch()

        assert lib["exists"]("exists.txt") is True

    def test_exists_false(self, tmp_path):
        """File.exists returns False for non-existing file."""
        lib = create_safe_file_library(str(tmp_path))

        assert lib["exists"]("nonexistent.txt") is False

    def test_exists_outside_base_returns_false(self, tmp_path):
        """File.exists returns False for paths outside base (not error)."""
        lib = create_safe_file_library(str(tmp_path))

        assert lib["exists"]("../etc/passwd") is False

    def test_write_creates_parent_dirs(self, tmp_path):
        """Writing creates parent directories if needed."""
        lib = create_safe_file_library(str(tmp_path))

        lib["write"]("subdir/nested/file.txt", "content")

        assert (tmp_path / "subdir" / "nested" / "file.txt").read_text() == "content"

    def test_read_nonexistent_raises(self, tmp_path):
        """Reading non-existent file raises FileNotFoundError."""
        lib = create_safe_file_library(str(tmp_path))

        with pytest.raises(FileNotFoundError):
            lib["read"]("nonexistent.txt")


class TestCsvLibrary:
    """Test CSV file operations."""

    def test_read_csv(self, tmp_path):
        """Read CSV with headers."""
        lib = create_safe_csv_library(str(tmp_path))
        csv_content = "name,score,category\nAlice,85,A\nBob,92,B"
        (tmp_path / "data.csv").write_text(csv_content)

        data = lib["read"]("data.csv")

        assert len(data) == 2
        assert data[0]["name"] == "Alice"
        assert data[0]["score"] == "85"
        assert data[1]["name"] == "Bob"

    def test_write_csv(self, tmp_path):
        """Write CSV from list of dicts."""
        lib = create_safe_csv_library(str(tmp_path))
        data = [
            {"name": "Alice", "score": "95"},
            {"name": "Bob", "score": "87"},
        ]

        lib["write"]("output.csv", data)

        content = (tmp_path / "output.csv").read_text()
        assert "name,score" in content
        assert "Alice,95" in content
        assert "Bob,87" in content

    def test_csv_roundtrip(self, tmp_path):
        """CSV read/write roundtrip preserves data."""
        lib = create_safe_csv_library(str(tmp_path))
        original = [
            {"name": "Alice", "score": "95"},
            {"name": "Bob", "score": "87"},
        ]

        lib["write"]("data.csv", original)
        result = lib["read"]("data.csv")

        # Result is a LuaList wrapper, compare the underlying data
        assert len(result) == len(original)
        for i, expected in enumerate(original):
            assert result[i] == expected

    def test_write_csv_with_explicit_headers(self, tmp_path):
        """Write CSV with explicit header order."""
        lib = create_safe_csv_library(str(tmp_path))
        data = [{"b": "2", "a": "1"}]

        lib["write"]("output.csv", data, {"headers": ["a", "b"]})

        content = (tmp_path / "output.csv").read_text()
        lines = content.strip().split("\n")
        assert lines[0] == "a,b"

    def test_read_empty_csv(self, tmp_path):
        """Reading empty CSV returns empty list."""
        lib = create_safe_csv_library(str(tmp_path))
        (tmp_path / "empty.csv").write_text("")

        data = lib["read"]("empty.csv")
        # data is a LuaList wrapper
        assert len(data) == 0


class TestTsvLibrary:
    """Test TSV file operations."""

    def test_read_tsv(self, tmp_path):
        """Read TSV with headers."""
        lib = create_safe_tsv_library(str(tmp_path))
        tsv_content = "name\tscore\tcategory\nAlice\t85\tA\nBob\t92\tB"
        (tmp_path / "data.tsv").write_text(tsv_content)

        data = lib["read"]("data.tsv")

        assert len(data) == 2
        assert data[0]["name"] == "Alice"

    def test_write_tsv(self, tmp_path):
        """Write TSV from list of dicts."""
        lib = create_safe_tsv_library(str(tmp_path))
        data = [{"name": "Alice", "score": "95"}]

        lib["write"]("output.tsv", data)

        content = (tmp_path / "output.tsv").read_text()
        assert "name\tscore" in content
        assert "Alice\t95" in content


class TestJsonLibrary:
    """Test JSON file operations."""

    def test_read_json_object(self, tmp_path):
        """Read JSON object."""
        lib = create_safe_json_library(str(tmp_path))
        (tmp_path / "data.json").write_text('{"name": "Alice", "score": 95}')

        data = lib["read"]("data.json")

        assert data["name"] == "Alice"
        assert data["score"] == 95

    def test_read_json_array(self, tmp_path):
        """Read JSON array."""
        lib = create_safe_json_library(str(tmp_path))
        (tmp_path / "data.json").write_text("[1, 2, 3]")

        data = lib["read"]("data.json")

        assert data == [1, 2, 3]

    def test_write_json(self, tmp_path):
        """Write JSON object."""
        lib = create_safe_json_library(str(tmp_path))
        data = {"name": "Alice", "scores": [95, 87, 92]}

        lib["write"]("output.json", data)

        content = (tmp_path / "output.json").read_text()
        parsed = json.loads(content)
        assert parsed == data

    def test_write_json_custom_indent(self, tmp_path):
        """Write JSON with custom indentation."""
        lib = create_safe_json_library(str(tmp_path))

        lib["write"]("output.json", {"a": 1}, {"indent": 4})

        content = (tmp_path / "output.json").read_text()
        assert "    " in content  # 4-space indent

    def test_json_roundtrip(self, tmp_path):
        """JSON read/write roundtrip preserves data."""
        lib = create_safe_json_library(str(tmp_path))
        original = {
            "string": "hello",
            "number": 42,
            "float": 3.14,
            "bool": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"a": "b"},
        }

        lib["write"]("data.json", original)
        result = lib["read"]("data.json")

        assert result == original


class TestParquetLibrary:
    """Test Parquet file operations."""

    def test_write_and_read_parquet(self, tmp_path):
        """Write and read Parquet file."""
        lib = create_safe_parquet_library(str(tmp_path))
        data = [
            {"name": "Alice", "score": 95},
            {"name": "Bob", "score": 87},
        ]

        lib["write"]("data.parquet", data)
        result = lib["read"]("data.parquet")

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[0]["score"] == 95

    def test_parquet_preserves_types(self, tmp_path):
        """Parquet preserves numeric types."""
        lib = create_safe_parquet_library(str(tmp_path))
        data = [
            {"int_val": 42, "float_val": 3.14, "str_val": "hello"},
        ]

        lib["write"]("data.parquet", data)
        result = lib["read"]("data.parquet")

        assert result[0]["int_val"] == 42
        assert abs(result[0]["float_val"] - 3.14) < 0.001
        assert result[0]["str_val"] == "hello"


class TestHdf5Library:
    """Test HDF5 file operations."""

    def test_write_and_read_hdf5(self, tmp_path):
        """Write and read HDF5 dataset."""
        lib = create_safe_hdf5_library(str(tmp_path))
        data = [1, 2, 3, 4, 5]

        lib["write"]("data.h5", "numbers", data)
        result = lib["read"]("data.h5", "numbers")

        assert result == data

    def test_hdf5_list_datasets(self, tmp_path):
        """List datasets in HDF5 file."""
        lib = create_safe_hdf5_library(str(tmp_path))

        lib["write"]("data.h5", "dataset1", [1, 2, 3])
        lib["write"]("data.h5", "dataset2", [4, 5, 6])

        datasets = lib["list"]("data.h5")

        assert "dataset1" in datasets
        assert "dataset2" in datasets

    def test_hdf5_overwrite_dataset(self, tmp_path):
        """Overwriting HDF5 dataset replaces data."""
        lib = create_safe_hdf5_library(str(tmp_path))

        lib["write"]("data.h5", "numbers", [1, 2, 3])
        lib["write"]("data.h5", "numbers", [4, 5, 6])

        result = lib["read"]("data.h5", "numbers")
        assert result == [4, 5, 6]

    def test_hdf5_2d_array(self, tmp_path):
        """HDF5 handles 2D arrays."""
        lib = create_safe_hdf5_library(str(tmp_path))
        data = [[1, 2, 3], [4, 5, 6]]

        lib["write"]("data.h5", "matrix", data)
        result = lib["read"]("data.h5", "matrix")

        assert result == data


class TestExcelLibrary:
    """Test Excel file operations."""

    def test_write_and_read_excel(self, tmp_path):
        """Write and read Excel file."""
        lib = create_safe_excel_library(str(tmp_path))
        data = [
            {"name": "Alice", "score": 95},
            {"name": "Bob", "score": 87},
        ]

        lib["write"]("data.xlsx", data)
        result = lib["read"]("data.xlsx")

        assert len(result) == 2
        assert result[0]["name"] == "Alice"
        assert result[0]["score"] == 95

    def test_excel_list_sheets(self, tmp_path):
        """List sheets in Excel file."""
        lib = create_safe_excel_library(str(tmp_path))
        data = [{"col": "value"}]

        lib["write"]("data.xlsx", data, {"sheet": "MySheet"})

        sheets = lib["sheets"]("data.xlsx")
        assert "MySheet" in sheets

    def test_excel_read_specific_sheet(self, tmp_path):
        """Read specific sheet from Excel file."""
        lib = create_safe_excel_library(str(tmp_path))

        # Create file with specific sheet
        lib["write"]("data.xlsx", [{"val": 1}], {"sheet": "Data"})

        result = lib["read"]("data.xlsx", {"sheet": "Data"})
        assert result[0]["val"] == 1

    def test_excel_empty_file(self, tmp_path):
        """Writing empty data creates valid Excel file."""
        lib = create_safe_excel_library(str(tmp_path))

        lib["write"]("empty.xlsx", [])

        result = lib["read"]("empty.xlsx")
        # result is a LuaList wrapper
        assert len(result) == 0


class TestLuaSandboxIntegration:
    """Test file I/O libraries work from Lua sandbox."""

    @pytest.mark.asyncio
    async def test_file_read_from_lua(self, tmp_path):
        """File.read() works from Lua code (using FilePrimitive)."""
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from file!")

        source = """
        main = Procedure("main", {
            input = {},
            output = {content = {type = "string"}}
        }, function()
            local content = File.read("test.txt")
            return {content = content}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-file-read", storage_backend=storage)

        # Change to tmp_path so file operations work
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await runtime.execute(source=source, context={}, format="lua")
        finally:
            os.chdir(original_cwd)

        assert result["success"] is True
        assert result["result"]["content"] == "Hello from file!"

    @pytest.mark.asyncio
    async def test_csv_read_from_lua(self, tmp_path):
        """csv.read() works from Lua code via require()."""
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        # Create test CSV
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("name,score\nAlice,95\nBob,87")

        source = """
        local csv = require("tactus.io.csv")

        main = Procedure("main", {
            input = {},
            output = {first_name = {type = "string"}, first_score = {type = "string"}}
        }, function()
            local data = csv.read("data.csv")
            -- Lua tables are 1-indexed
            local first = data[1]
            return {first_name = first.name, first_score = first.score}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-csv-read", storage_backend=storage)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await runtime.execute(source=source, context={}, format="lua")
        finally:
            os.chdir(original_cwd)

        assert result["success"] is True
        assert result["result"]["first_name"] == "Alice"
        assert result["result"]["first_score"] == "95"

    @pytest.mark.asyncio
    async def test_json_encode_decode_from_lua(self, tmp_path):
        """json.encode/decode works from Lua code via require()."""
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        source = """
        local json = require("tactus.io.json")

        main = Procedure("main", {
            input = {},
            output = {encoded = {type = "string"}, decoded_name = {type = "string"}}
        }, function()
            -- json module has encode/decode
            local data = {name = "Alice", count = 42}
            local json_str = json.encode(data)
            local decoded = json.decode(json_str)
            return {encoded = json_str, decoded_name = decoded.name}
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-json", storage_backend=storage)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await runtime.execute(source=source, context={}, format="lua")
        finally:
            os.chdir(original_cwd)

        assert result["success"] is True
        assert "Alice" in result["result"]["encoded"]
        assert result["result"]["decoded_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_directory_traversal_blocked_from_lua(self, tmp_path):
        """Directory traversal is blocked from Lua code."""
        from tactus.adapters.memory import MemoryStorage
        from tactus.core.runtime import TactusRuntime

        source = """
        main = Procedure("main", {
            input = {},
            output = {error = {type = "string"}}
        }, function()
            local ok, err = pcall(function()
                File.read("../../../etc/passwd")
            end)
            if ok then
                return {error = "No error - security breach!"}
            else
                return {error = tostring(err)}
            end
        end)
        """

        storage = MemoryStorage()
        runtime = TactusRuntime(procedure_id="test-traversal", storage_backend=storage)

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await runtime.execute(source=source, context={}, format="lua")
        finally:
            os.chdir(original_cwd)

        assert result["success"] is True
        # FilePrimitive uses "Path traversal detected" message
        assert "traversal" in result["result"]["error"].lower()
