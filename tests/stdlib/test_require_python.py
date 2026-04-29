"""Integration tests for require() with Python stdlib modules."""

import json
import pytest
from tactus.adapters.memory import MemoryStorage
from tactus.core.lua_sandbox import LuaSandbox
from tactus.core.runtime import TactusRuntime


class TestRequirePythonModule:
    """Test require() with Python stdlib modules."""

    def test_require_stdlib_json(self, tmp_path):
        """Test require('tactus.io.json') works."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should be able to require the json module
        result = sandbox.execute("""
            local json = require("tactus.io.json")
            return {
                has_read = json.read ~= nil,
                has_write = json.write ~= nil,
                has_encode = json.encode ~= nil,
                has_decode = json.decode ~= nil
            }
        """)
        assert result["has_read"] == True  # noqa: E712
        assert result["has_write"] == True  # noqa: E712
        assert result["has_encode"] == True  # noqa: E712
        assert result["has_decode"] == True  # noqa: E712

    def test_json_write_and_read(self, tmp_path):
        """Test writing and reading JSON files."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Write a JSON file
        sandbox.execute("""
            local json = require("tactus.io.json")
            json.write("test.json", {name = "Alice", age = 30})
        """)

        # Verify file was created
        json_file = tmp_path / "test.json"
        assert json_file.exists()

        # Read and verify content
        with open(json_file) as f:
            data = json.load(f)
        assert data == {"name": "Alice", "age": 30}

        # Read from Lua
        result = sandbox.execute("""
            local json = require("tactus.io.json")
            return json.read("test.json")
        """)
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_json_encode_decode(self, tmp_path):
        """Test JSON encode/decode functions."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Encode to string
        result = sandbox.execute("""
            local json = require("tactus.io.json")
            return json.encode({key = "value", number = 42})
        """)
        assert isinstance(result, str)
        data = json.loads(result)
        assert data == {"key": "value", "number": 42}

        # Decode from string
        result = sandbox.execute("""
            local json = require("tactus.io.json")
            return json.decode('{"key": "value"}')
        """)
        assert result["key"] == "value"

    def test_tac_preferred_over_python(self, tmp_path):
        """Test that .tac files are preferred when both exist."""
        # Create a .tac file in user's directory
        (tmp_path / "mymodule.tac").write_text("""
            return {
                type = "tac_module"
            }
        """)

        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should load the .tac version
        result = sandbox.execute('local m = require("mymodule"); return m')
        assert result["type"] == "tac_module"

    def test_host_module_preferred_over_local_tac_file(self, tmp_path):
        """Test explicit host capabilities cannot be shadowed by local .tac files."""

        (tmp_path / "plexus.tac").write_text("""
            return {
                source = "local_tac"
            }
        """)

        sandbox = LuaSandbox(
            base_path=str(tmp_path),
            python_modules={"plexus": {"source": lambda: "host_module"}},
        )

        result = sandbox.execute("""
            local plexus = require("plexus")
            return plexus.source()
        """)

        assert result == "host_module"

    def test_exception_propagation(self, tmp_path):
        """Test that Python exceptions become Lua errors."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Try to read nonexistent file
        with pytest.raises(Exception) as exc_info:
            sandbox.execute("""
                local json = require("tactus.io.json")
                json.read("nonexistent.json")
            """)

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
            sandbox.execute("""
                local json = require("tactus.io.json")
                json.write("../../../etc/passwd", {evil = true})
            """)

        # Should be blocked with permission error
        assert (
            "permission" in str(exc_info.value).lower() or "denied" in str(exc_info.value).lower()
        )

    def test_user_cannot_require_arbitrary_python(self, tmp_path):
        """Test that user code cannot require arbitrary Python modules."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Should not be able to require Python os module via tactus prefix
        result = sandbox.execute("""
            local status, err = pcall(function()
                return require("tactus.os")
            end)
            return status
        """)
        # pcall should catch the error (module not found)
        assert result == False  # noqa: E712

        # Should not be able to require Python sys module via tactus prefix
        result = sandbox.execute("""
            local status, err = pcall(function()
                return require("tactus.sys")
            end)
            return status
        """)
        assert result == False  # noqa: E712

    def test_pcall_catches_python_errors(self, tmp_path):
        """Test that Lua pcall() can catch Python exceptions."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        result = sandbox.execute("""
            local json = require("tactus.io.json")
            local status, err = pcall(function()
                return json.read("nonexistent.json")
            end)
            return {status = status, has_error = err ~= nil}
        """)

        assert result["status"] == False  # noqa: E712
        assert result["has_error"] == True  # noqa: E712

    def test_type_conversion_dict_to_lua_table(self, tmp_path):
        """Test Python dict -> Lua table conversion."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        # Create JSON file
        json_file = tmp_path / "data.json"
        json_file.write_text('{"name": "Bob", "scores": [95, 87, 92]}')

        result = sandbox.execute("""
            local json = require("tactus.io.json")
            local data = json.read("data.json")
            return {
                name = data.name,
                first_score = data.scores[1],
                count = #data.scores
            }
        """)

        assert result["name"] == "Bob"
        assert result["first_score"] == 95
        assert result["count"] == 3

    def test_type_conversion_lua_table_to_dict(self, tmp_path):
        """Test Lua table -> Python dict conversion."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        sandbox.execute("""
            local json = require("tactus.io.json")
            json.write("output.json", {
                message = "Hello",
                items = {"apple", "banana", "cherry"}
            })
        """)

        json_file = tmp_path / "output.json"
        with open(json_file) as f:
            data = json.load(f)

        assert data["message"] == "Hello"
        assert data["items"] == ["apple", "banana", "cherry"]

    def test_require_host_registered_python_module(self, tmp_path):
        """Test require('plexus') can resolve an explicit host module."""

        class Scores:
            def info(self, args):
                return {
                    "id": args["id"],
                    "name": "Compliance Tone",
                    "versions": ["v1", "v2"],
                }

        class Plexus:
            def __init__(self):
                self.score = Scores()

            def ping(self):
                return "pong"

        sandbox = LuaSandbox(base_path=str(tmp_path), python_modules={"plexus": Plexus()})

        result = sandbox.execute("""
            local plexus = require("plexus")
            local score = plexus.score.info({id = "score_1"})
            return {
                ping = plexus.ping(),
                score_id = score.id,
                score_name = score.name,
                first_version = score.versions[1],
                version_count = #score.versions
            }
        """)

        assert result["ping"] == "pong"
        assert result["score_id"] == "score_1"
        assert result["score_name"] == "Compliance Tone"
        assert result["first_version"] == "v1"
        assert result["version_count"] == 2

    def test_host_module_registration_does_not_evaluate_properties(self, tmp_path):
        """Test host object properties are not evaluated while building the Lua module."""

        class HostModule:
            @property
            def dangerous(self):
                raise AssertionError("property should not be evaluated")

            def safe(self):
                return "ok"

        sandbox = LuaSandbox(base_path=str(tmp_path), python_modules={"host": HostModule()})

        result = sandbox.execute("""
            local host = require("host")
            return {
                safe = host.safe(),
                dangerous_is_nil = host.dangerous == nil
            }
        """)

        assert result["safe"] == "ok"
        assert result["dangerous_is_nil"] == True  # noqa: E712

    def test_register_host_module_after_sandbox_creation(self, tmp_path):
        """Test a host module can be registered after sandbox initialization."""

        sandbox = LuaSandbox(base_path=str(tmp_path))
        sandbox.register_python_module("host", {"answer": lambda: 42})

        result = sandbox.execute("""
            local host = require("host")
            return host.answer()
        """)

        assert result == 42

    def test_reregister_host_module_clears_lua_require_cache(self, tmp_path):
        """Test re-registering a host module updates subsequent require() calls."""

        sandbox = LuaSandbox(base_path=str(tmp_path))
        sandbox.register_python_module("host", {"value": lambda: "first"})

        first = sandbox.execute("""
            local host = require("host")
            return host.value()
        """)

        sandbox.register_python_module("host", {"value": lambda: "second"})

        second = sandbox.execute("""
            local host = require("host")
            return host.value()
        """)

        assert first == "first"
        assert second == "second"

    def test_initial_host_modules_validate_reserved_namespace(self, tmp_path):
        """Test constructor-supplied modules cannot use tactus.*."""

        with pytest.raises(Exception) as exc_info:
            LuaSandbox(
                base_path=str(tmp_path),
                python_modules={"tactus.fake": {"value": lambda: 1}},
            )

        assert "reserved" in str(exc_info.value).lower()

    def test_host_module_name_must_be_dotted_identifier(self, tmp_path):
        """Test host module names cannot be path-like or empty."""

        sandbox = LuaSandbox(base_path=str(tmp_path))

        for name in ["", "plexus/tools", "plexus-tools", "1plexus"]:
            with pytest.raises(Exception) as exc_info:
                sandbox.register_python_module(name, {"value": lambda: 1})
            assert "module name" in str(exc_info.value).lower()

    def test_unregistered_host_module_is_not_available(self, tmp_path):
        """Test unknown non-stdlib modules remain unavailable."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        result = sandbox.execute("""
            local status, err = pcall(function()
                return require("not_registered")
            end)
            return {status = status, has_error = err ~= nil}
        """)

        assert result["status"] == False  # noqa: E712
        assert result["has_error"] == True  # noqa: E712

    def test_host_module_cannot_use_reserved_tactus_namespace(self, tmp_path):
        """Test hosts cannot override the reserved tactus.* namespace."""
        sandbox = LuaSandbox(base_path=str(tmp_path))

        with pytest.raises(Exception) as exc_info:
            sandbox.register_python_module("tactus.fake", {"value": lambda: 1})

        assert "reserved" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_runtime_register_python_module(self, tmp_path):
        """Test TactusRuntime exposes host modules to Lua execution."""

        class HostModule:
            def ping(self):
                return {"message": "pong"}

        runtime = TactusRuntime(
            procedure_id="host-module-test",
            storage_backend=MemoryStorage(),
            hitl_handler=object(),
            source_file_path=str(tmp_path / "procedure.tac"),
        )
        runtime.register_python_module("host", HostModule())

        result = await runtime.execute(
            """
            local host = require("host")
            local response = host.ping()
            return response.message
            """,
            format="lua",
        )

        assert result["success"] == True  # noqa: E712
        assert result["result"] == "pong"
