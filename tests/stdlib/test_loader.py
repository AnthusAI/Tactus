"""Unit tests for StdlibModuleLoader."""

import pytest
from pathlib import Path
from tactus.core.lua_sandbox import LuaSandbox
from tactus.stdlib.loader import StdlibModuleLoader, TactusStdlibContext


class TestStdlibModuleLoader:
    """Test the Python stdlib module loader."""

    def test_loader_initialization(self, tmp_path):
        """Test that loader initializes correctly."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))

        assert loader.lua_sandbox == sandbox
        assert loader.base_path == str(tmp_path)
        assert loader.stdlib_path.exists()
        assert loader.loaded_modules == {}

    def test_stdlib_path_detection(self, tmp_path):
        """Test that stdlib path is correctly detected."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))

        # Should point to tactus/stdlib
        assert loader.stdlib_path.name == "stdlib"
        assert loader.stdlib_path.parent.name == "tactus"

    def test_reject_non_tactus_paths(self, tmp_path):
        """Test that non-tactus.* paths return None."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        # Should return None for non-tactus modules
        result = loader_func("os")
        assert result is None

        result = loader_func("sys")
        assert result is None

        result = loader_func("mymodule")
        assert result is None

    def test_reject_path_traversal(self, tmp_path):
        """Test that path traversal attempts are blocked."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        # Should return None for path traversal attempts
        result = loader_func("tactus../../../etc/passwd")
        assert result is None

        result = loader_func("tactus.io.../../core/runtime")
        assert result is None

    def test_load_valid_module(self, tmp_path):
        """Test loading a valid Python stdlib module."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        # Load the json module
        result = loader_func("tactus.io.json")

        assert result is not None
        # Should be a Lua table with functions
        assert "read" in result
        assert "write" in result
        assert "encode" in result
        assert "decode" in result

    def test_module_caching(self, tmp_path):
        """Test that modules are cached after first load."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        # Load module twice
        result1 = loader_func("tactus.io.json")
        result2 = loader_func("tactus.io.json")

        # Should be the same object (cached)
        assert result1 is result2
        assert "tactus.io.json" in loader.loaded_modules

    def test_nonexistent_module(self, tmp_path):
        """Test that nonexistent modules return None."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        result = loader_func("tactus.io.nonexistent")
        assert result is None

    def test_loader_wraps_module_load_errors(self, tmp_path, monkeypatch):
        """Test that module load failures are wrapped for Lua."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        loader_func = loader.create_loader_function()

        def boom(_name, _path):
            raise RuntimeError("boom")

        monkeypatch.setattr(loader, "_load_python_module", boom)

        with pytest.raises(RuntimeError, match="Failed to load module"):
            loader_func("tactus.io.json")

    def test_load_module_import_spec_failure(self, tmp_path, monkeypatch):
        """Test that spec loading failures raise ImportError."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))
        fake_path = tmp_path / "fake.py"
        fake_path.write_text("x = 1")

        monkeypatch.setattr(
            "importlib.util.spec_from_file_location",
            lambda _name, _path: None,
        )

        with pytest.raises(ImportError, match="Could not load spec"):
            loader._load_python_module("tactus.io.fake", fake_path)

    def test_explicit_exports(self, tmp_path):
        """Test that __tactus_exports__ limits exposed functions."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))

        # Create a test module with explicit exports
        test_module = type("TestModule", (), {})()
        test_module.__name__ = "test_module"

        def public_func():
            pass

        def another_func():
            pass

        def _private_func():
            pass

        # Set __module__ to match test_module.__name__
        public_func.__module__ = "test_module"
        another_func.__module__ = "test_module"
        _private_func.__module__ = "test_module"

        test_module.public_func = public_func
        test_module.another_func = another_func
        test_module._private_func = _private_func
        test_module.__tactus_exports__ = ["public_func"]

        exports = loader._get_module_exports(test_module)

        # Should only export public_func
        assert "public_func" in exports
        assert "another_func" not in exports
        assert "_private_func" not in exports

    def test_skip_imported_functions(self, tmp_path):
        """Test that imported functions are skipped."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        loader = StdlibModuleLoader(sandbox, str(tmp_path))

        test_module = type("TestModule", (), {})()
        test_module.__name__ = "test_module"

        def external_func():
            pass

        external_func.__module__ = "other_module"
        test_module.external_func = external_func

        exports = loader._get_module_exports(test_module)
        assert "external_func" not in exports


class TestTactusStdlibContext:
    """Test the TactusStdlibContext."""

    def test_context_initialization(self, tmp_path):
        """Test context initialization."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        context = TactusStdlibContext(str(tmp_path), sandbox)

        assert context.base_path == str(tmp_path)
        assert context._lua_sandbox == sandbox
        assert context._path_validator is None

    def test_path_validator_lazy_creation(self, tmp_path):
        """Test that path validator is created lazily."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        context = TactusStdlibContext(str(tmp_path), sandbox)

        # Should be None initially
        assert context._path_validator is None

        # Access should create it
        validator = context.path_validator
        assert validator is not None
        assert context._path_validator is validator

    def test_validate_path(self, tmp_path):
        """Test path validation."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        context = TactusStdlibContext(str(tmp_path), sandbox)

        # Create a test file
        test_file = tmp_path / "test.json"
        test_file.write_text("{}")

        # Should validate successfully
        result = context.validate_path("test.json")
        assert Path(result).name == "test.json"

    def test_reject_path_outside_base(self, tmp_path):
        """Test that paths outside base are rejected."""
        sandbox = LuaSandbox(base_path=str(tmp_path))
        context = TactusStdlibContext(str(tmp_path), sandbox)

        # Should raise PermissionError
        with pytest.raises(PermissionError):
            context.validate_path("../../../etc/passwd")


def test_python_to_lua_fallback_value(tmp_path):
    sandbox = LuaSandbox(base_path=str(tmp_path))
    loader = StdlibModuleLoader(sandbox, str(tmp_path))
    marker = object()
    assert loader._python_to_lua(marker) is marker
