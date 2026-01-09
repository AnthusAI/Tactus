"""
tactus.io.file - Raw text file operations for Tactus.

Provides basic text file read/write operations with sandboxing
to the procedure's base directory.

Usage in .tac files:
    local file = require("tactus.io.file")

    -- Read text file
    local content = file.read("data.txt")

    -- Write text file
    file.write("output.txt", "Hello, world!")

    -- Check if file exists
    if file.exists("config.txt") then
        -- do something
    end
"""

import os
import sys

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def read(filepath: str) -> str:
    """
    Read entire file as text.

    Args:
        filepath: Path to text file (relative to working directory)

    Returns:
        File contents as string

    Raises:
        FileNotFoundError: If file does not exist
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write(filepath: str, content: str) -> None:
    """
    Write text to file.

    Args:
        filepath: Path to text file
        content: Text content to write

    Raises:
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    # Create parent directories
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def exists(filepath: str) -> bool:
    """
    Check if file exists.

    Args:
        filepath: Path to file

    Returns:
        True if file exists and is accessible, False otherwise
    """
    try:
        if _ctx:
            filepath = _ctx.validate_path(filepath)
        return os.path.exists(filepath)
    except PermissionError:
        return False


# Explicit exports
__tactus_exports__ = ["read", "write", "exists"]
