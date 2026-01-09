"""
tactus.io.json - JSON file operations for Tactus.

Provides JSON read/write operations with automatic path validation
and sandboxing to the procedure's base directory.

Usage in .tac files:
    local json = require("tactus.io.json")

    -- Read JSON file
    local data = json.read("config.json")

    -- Write JSON file
    json.write("output.json", {name = "Alice", score = 95})

    -- Encode/decode strings
    local str = json.encode({key = "value"})
    local obj = json.decode('{"key": "value"}')
"""

import json
import os
import sys
from typing import Any, Optional

# Get context (injected by loader)
_ctx = getattr(sys.modules[__name__], "__tactus_context__", None)


def read(filepath: str) -> Any:
    """
    Read and parse a JSON file.

    Args:
        filepath: Path to JSON file (relative to working directory)

    Returns:
        Parsed JSON data (dict, list, or primitive)

    Raises:
        FileNotFoundError: If file does not exist
        json.JSONDecodeError: If file is not valid JSON
        PermissionError: If path is outside working directory
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def write(filepath: str, data: Any, indent: int = 2) -> None:
    """
    Write data to a JSON file.

    Args:
        filepath: Path to JSON file
        data: Data to write (dict, list, or primitive)
        indent: Indentation level (default 2)

    Raises:
        PermissionError: If path is outside working directory
        TypeError: If data is not JSON serializable
    """
    if _ctx:
        filepath = _ctx.validate_path(filepath)

    # Create parent directories
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def encode(data: Any, indent: Optional[int] = None) -> str:
    """
    Encode data to JSON string.

    Args:
        data: Data to encode
        indent: Optional indentation

    Returns:
        JSON string

    Raises:
        TypeError: If data is not JSON serializable
    """
    return json.dumps(data, indent=indent, ensure_ascii=False)


def decode(json_string: str) -> Any:
    """
    Decode JSON string to data.

    Args:
        json_string: JSON string to parse

    Returns:
        Parsed data

    Raises:
        json.JSONDecodeError: If string is not valid JSON
    """
    return json.loads(json_string)


# Explicit exports (only these functions exposed to Lua)
__tactus_exports__ = ["read", "write", "encode", "decode"]
