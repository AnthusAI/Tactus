"""Integration tests for require() with Python stdlib modules."""

import json
import pytest
from tactus.core.lua_sandbox import LuaSandbox


class TestRequirePythonModule:
    """Test require() with Python stdlib modules."""

    def test_require_stdlib_json(self, tmp_path):
        """Test require('tactus.io.json') works."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should be able to require the json module
        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            return {
                has_read = json.read ~= nil,
                has_write = json.write ~= nil,
                has_encode = json.encode ~= nil,
                has_decode = json.decode ~= nil
            }
        """
        )
        assert result["has_read"] == True  # noqa: E712
        assert result["has_write"] == True  # noqa: E712
        assert result["has_encode"] == True  # noqa: E712
        assert result["has_decode"] == True  # noqa: E712

    def test_json_write_and_read(self, tmp_path):
        """Test writing and reading JSON files."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Write a JSON file
        sandbox.execute(
            """
            local json = require("tactus.io.json")
            json.write("test.json", {name = "Alice", age = 30})
        """
        )

        # Verify file was created
        json_file = tmp_path / "test.json"
        assert json_file.exists()

        # Read and verify content
        with open(json_file) as f:
            data = json.load(f)
        assert data == {"name": "Alice", "age": 30}

        # Read from Lua
        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            return json.read("test.json")
        """
        )
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_json_encode_decode(self, tmp_path):
        """Test JSON encode/decode functions."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Encode to string
        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            return json.encode({key = "value", number = 42})
        """
        )
        assert isinstance(result, str)
        data = json.loads(result)
        assert data == {"key": "value", "number": 42}

        # Decode from string
        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            return json.decode('{"key": "value"}')
        """
        )
        assert result["key"] == "value"

    def test_tac_preferred_over_python(self, tmp_path):
        """Test that .tac files are preferred when both exist."""
        # Create a .tac file in user's directory
        (tmp_path / "mymodule.tac").write_text(
            """
            return {
                type = "tac_module"
            }
        """
        )

        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should load the .tac version
        result = sandbox.execute('local m = require("mymodule"); return m')
        assert result["type"] == "tac_module"

    def test_exception_propagation(self, tmp_path):
        """Test that Python exceptions become Lua errors."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Try to read nonexistent file
        with pytest.raises(Exception) as exc_info:
            sandbox.execute(
                """
                local json = require("tactus.io.json")
                json.read("nonexistent.json")
            """
            )

        # Should contain error about file not found
        assert (
            "nonexistent.json" in str(exc_info.value).lower()
            or "no such file" in str(exc_info.value).lower()
        )

    def test_path_validation_in_stdlib(self, tmp_path):
        """Test that file I/O is restricted to base_path."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Try to write outside base_path
        with pytest.raises(Exception) as exc_info:
            sandbox.execute(
                """
                local json = require("tactus.io.json")
                json.write("../../../etc/passwd", {evil = true})
            """
            )

        # Should be blocked with permission error
        assert (
            "permission" in str(exc_info.value).lower() or "denied" in str(exc_info.value).lower()
        )

    def test_user_cannot_require_arbitrary_python(self, tmp_path):
        """Test that user code cannot require arbitrary Python modules."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should not be able to require Python os module via tactus prefix
        result = sandbox.execute(
            """
            local status, err = pcall(function()
                return require("tactus.os")
            end)
            return status
        """
        )
        # pcall should catch the error (module not found)
        assert result == False  # noqa: E712

        # Should not be able to require Python sys module via tactus prefix
        result = sandbox.execute(
            """
            local status, err = pcall(function()
                return require("tactus.sys")
            end)
            return status
        """
        )
        assert result == False  # noqa: E712

    def test_pcall_catches_python_errors(self, tmp_path):
        """Test that Lua pcall() can catch Python exceptions."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            local status, err = pcall(function()
                return json.read("nonexistent.json")
            end)
            return {status = status, has_error = err ~= nil}
        """
        )

        assert result["status"] == False  # noqa: E712
        assert result["has_error"] == True  # noqa: E712

    def test_type_conversion_dict_to_lua_table(self, tmp_path):
        """Test Python dict -> Lua table conversion."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Create JSON file
        json_file = tmp_path / "data.json"
        json_file.write_text('{"name": "Bob", "scores": [95, 87, 92]}')

        result = sandbox.execute(
            """
            local json = require("tactus.io.json")
            local data = json.read("data.json")
            return {
                name = data.name,
                first_score = data.scores[1],
                count = #data.scores
            }
        """
        )

        assert result["name"] == "Bob"
        assert result["first_score"] == 95
        assert result["count"] == 3

    def test_type_conversion_lua_table_to_dict(self, tmp_path):
        """Test Lua table -> Python dict conversion."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        sandbox.execute(
            """
            local json = require("tactus.io.json")
            json.write("output.json", {
                message = "Hello",
                items = {"apple", "banana", "cherry"}
            })
        """
        )

        json_file = tmp_path / "output.json"
        with open(json_file) as f:
            data = json.load(f)

        assert data["message"] == "Hello"
        assert data["items"] == ["apple", "banana", "cherry"]
