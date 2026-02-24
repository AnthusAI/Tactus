"""
Test security aspects of the Lua sandbox, particularly file I/O restrictions.
"""

import os
import tempfile
from pathlib import Path

import pytest

from tactus.core.lua_sandbox import LuaSandbox


class TestLuaSandboxSecurity:
    """Test security features of the Lua sandbox."""

    def test_base_path_fixed_at_initialization(self):
        """Test that base_path is fixed at initialization and doesn't change with cwd."""
        # Create a temporary directory structure
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Start in dir1
            original_cwd = os.getcwd()
            try:
                os.chdir(dir1)

                # Initialize sandbox in dir1
                sandbox = LuaSandbox()

                # Verify base_path is set to dir1 (resolve symlinks for comparison)
                assert Path(sandbox.base_path).resolve() == dir1.resolve()

                # Change working directory to dir2
                os.chdir(dir2)

                # Verify base_path is still dir1 (not dir2)
                assert Path(sandbox.base_path).resolve() == dir1.resolve()
                assert Path(sandbox.base_path).resolve() != dir2.resolve()

                # Call set_execution_context which triggers _setup_safe_globals
                # and _setup_file_io_libraries again
                sandbox.set_execution_context(None)

                # Verify base_path is STILL dir1 (security fix verification)
                assert Path(sandbox.base_path).resolve() == dir1.resolve()
                assert Path(sandbox.base_path).resolve() != dir2.resolve()

            finally:
                os.chdir(original_cwd)

    def test_file_io_libraries_use_fixed_base_path(self):
        """Test that file I/O libraries use the fixed base_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Create test files
            (dir1 / "test1.txt").write_text("dir1 content")
            (dir2 / "test2.txt").write_text("dir2 content")

            original_cwd = os.getcwd()
            try:
                # Initialize sandbox in dir1
                os.chdir(dir1)
                sandbox = LuaSandbox()

                # Inject File primitive for testing
                from tactus.primitives.file import FilePrimitive

                file_primitive = FilePrimitive(sandbox.base_path)
                sandbox.inject_primitive("File", file_primitive)

                # Verify we can read test1.txt from dir1
                result = sandbox.eval('File.read("test1.txt")')
                assert result == "dir1 content"

                # Change to dir2
                os.chdir(dir2)

                # Call set_execution_context (which re-runs _setup_file_io_libraries)
                sandbox.set_execution_context(None)

                # Re-inject File primitive with the sandbox's base_path
                # (which should still be dir1)
                file_primitive = FilePrimitive(sandbox.base_path)
                sandbox.inject_primitive("File", file_primitive)

                # Should still read from dir1, not dir2
                result = sandbox.eval('File.read("test1.txt")')
                assert result == "dir1 content"

                # Should NOT be able to read test2.txt (it's in dir2, not dir1)
                with pytest.raises(Exception):  # Should raise error about file not found
                    sandbox.eval('File.read("test2.txt")')

            finally:
                os.chdir(original_cwd)

    def test_csv_library_uses_fixed_base_path(self):
        """Test that CSV library uses the fixed base_path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            dir1 = Path(tmpdir) / "dir1"
            dir2 = Path(tmpdir) / "dir2"
            dir1.mkdir()
            dir2.mkdir()

            # Create CSV files
            (dir1 / "data1.csv").write_text("name,value\ntest1,100\n")
            (dir2 / "data2.csv").write_text("name,value\ntest2,200\n")

            original_cwd = os.getcwd()
            try:
                # Initialize sandbox in dir1
                os.chdir(dir1)
                sandbox = LuaSandbox()

                # Verify we can read data1.csv from dir1
                result = sandbox.execute(
                    """
                    local csv = require("tactus.io.csv")
                    local data = csv.read("data1.csv")
                    return data
                """
                )
                assert len(result) == 1
                assert result[1]["name"] == "test1"  # Lua tables are 1-indexed

                # Change to dir2
                os.chdir(dir2)

                # Call set_execution_context (which re-runs _setup_safe_globals)
                sandbox.set_execution_context(None)

                # Should still read from dir1, not dir2
                result = sandbox.execute(
                    """
                    local csv = require("tactus.io.csv")
                    local data = csv.read("data1.csv")
                    return data
                """
                )
                assert len(result) == 1
                assert result[1]["name"] == "test1"  # Lua tables are 1-indexed

                # Should NOT be able to read data2.csv (it's in dir2, not dir1)
                with pytest.raises(Exception):  # Should raise error about file not found
                    sandbox.execute(
                        """
                        local csv = require("tactus.io.csv")
                        return csv.read("data2.csv")
                    """
                    )

            finally:
                os.chdir(original_cwd)
